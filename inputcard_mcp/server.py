"""
inputcard_mcp.server — inputcard-mcp 的本地 stdio MCP 服务器。

无状态：每次工具调用，AI 携带完整文档（INP 文本 或 结构化 deck JSON），
服务返回处理后的结果或新文档。所有修改型工具都「收当前 INP → 返回新 INP」。

复用本程序后端能力（不重复实现）：
  - parse_inp_text()          INP 文本 → DeckData
  - generate_inp_from_deck()  DeckData → INP 文本（延迟导入，避免拉起时加载 pymcnp）
  - api_server.deck_from_json / deck_to_frontend_dict   dict ⇄ DeckData 双向转换

技术：mcp<2 的 FastMCP（v1 @mcp.tool 装饰器）。
"""

import logging
import os
import sys

# ── 路径引导：让本包能 import app 包（generator/models/xsdir_db）及 gui/backend（api_server）──
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.normpath(os.path.join(_HERE, ".."))
_APP_DIR = os.path.join(_PROJECT_DIR, "app")
_GUI_BACKEND = os.path.join(_PROJECT_DIR, "gui", "backend")
for _p in (_APP_DIR, _PROJECT_DIR, _GUI_BACKEND):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcp.server.fastmcp import FastMCP

# 轻量依赖：解析器只做 INP → DeckData；不触发 pymcnp/FreeCAD
from generator.parsers import parse_inp_text

# 复用 api_server 的 deck ⇄ JSON 与各段映射（与 GUI 同一实现；其模块级只 import 核心引擎，xsdir 惰性）
from api_server import (
    deck_from_json,
    deck_to_frontend_dict,
    _basic_from_dict, _cells_from_list, _materials_from_list,
    _sources_from_list, _tally_from_dict, _adv_from_dict,
)

# 后端语义段（= deck_from_json 的 8 类读取入口；AI 可写单位）
_SECTIONS = ("basic", "surfaces", "tr_cards", "cells", "materials", "sources", "tally", "advanced")


def _configure_logging():
    """让 MCP 传输默认不被服务端日志刷屏而卡死（见 diagnostics: stderr-hang）。

    mcp / anyio / httpx 等 logger 默认 INFO，会在**每个请求**都往 stderr 打一条
    "Processing request…"。Windows 管道缓冲很小（~12KB），在 stdio 客户端未消费
    stderr 时，server 阻塞在写 stderr → stdout 停 → 整个 MCP 传输卡死。
    这里把这类 logger 默认降到 WARNING（安静）。排查时设环境变量 INPUTCARD_MCP_LOG=DEBUG 放开。
    """
    level = logging.getLevelName(os.environ.get("INPUTCARD_MCP_LOG", "WARNING").upper())
    if not isinstance(level, int):
        level = logging.WARNING
    for name in ("mcp", "anyio", "httpx", "httpcore", "starlette", "uvicorn", "h11"):
        logging.getLogger(name).setLevel(level)


_configure_logging()

mcp = FastMCP("inputcard-mcp")


def _generate(deck, raw_overrides=None):
    """延迟导入 generate_inp_from_deck（其模块顶层会 import pymcnp，重量依赖）。"""
    from generator.inp_generator import generate_inp_from_deck
    return generate_inp_from_deck(deck, raw_overrides or {})


def _deck_to_sections(deck) -> dict:
    """DeckData → 8 段语义结构（snake_case，advanced 对应后端 adv）。

    与 list_section / patch_section / generate_document **同一结构**（asdict 口径）。
    另保留 universe_comments（U 分组注释），generate 时不会被丢。
    """
    import dataclasses
    d = dataclasses.asdict(deck)
    sec = {k: d.get(k) for k in ("basic", "surfaces", "tr_cards", "cells", "materials", "sources", "tally")}
    sec["advanced"] = d.get("adv")
    sec["universe_comments"] = d.get("universe_comments", {})
    return sec


def _sections_to_deck(sections: dict):
    """8 段语义结构 → DeckData（复用 deck_from_json；advanced 键转回 adv）。"""
    d = dict(sections or {})
    if "advanced" in d:
        d["adv"] = d.pop("advanced")
    return deck_from_json(d)


# ── 把"该段整体替换"抽成单一实现（深模块，供 patch_section 与 workspace 共用）──
def _apply_section_patch(deck, section, data):
    if section == "basic":
        deck.basic = _basic_from_dict(data or {})
    elif section == "surfaces":
        deck.surfaces = data if isinstance(data, str) else str(data)
    elif section == "tr_cards":
        deck.tr_cards = data if isinstance(data, str) else str(data)
    elif section == "cells":
        deck.cells = _cells_from_list(data if isinstance(data, list) else [])
    elif section == "materials":
        deck.materials = _materials_from_list(data if isinstance(data, list) else [])
    elif section == "sources":
        deck.sources = _sources_from_list(data if isinstance(data, list) else [])
    elif section == "tally":
        deck.tally = _tally_from_dict(data or {})
    elif section == "advanced":
        deck.adv = _adv_from_dict(data or {})
    return deck


# ── 当前工作区（有状态会话）──────────────
# 程序前端把所有标签页合成的当前 deck 推到这里；MCP 工具在「不传 inp」时读写它。
_WORKSPACE = {"revision": 0, "sections": None, "deck_text": ""}


def _default_sections():
    from models import DeckData
    return _deck_to_sections(DeckData())


def _ws_sections() -> dict:
    if not isinstance(_WORKSPACE["sections"], dict):
        _WORKSPACE["sections"] = _default_sections()
    return _WORKSPACE["sections"]


def _ws_deck():
    return _sections_to_deck(_ws_sections())


def _set_ws_sections(sections):
    _WORKSPACE["sections"] = dict(sections or {})
    _WORKSPACE["revision"] += 1
    return _WORKSPACE["revision"]


def _ws_state():
    """给前端/AI 的当前工作区快照：sections + revision + 生成的 INP 文本。"""
    sec = _ws_sections()
    return {"revision": _WORKSPACE["revision"], "sections": sec}


# ─────────────────────────────── 文档级读写 ───────────────────────────────

@mcp.tool()
def read_document(inp: str | None = None) -> dict:
    """读取输入卡的**按语义段**结构（sections）。两种用法：
    - 传 inp（INP 文本）→ 解析并用该文档；
    - **不传 inp → 读「程序当前工作区」**（前端所有标签页推上来的当前 deck，即你正在编辑的程序内容）。
    返回 { sections, warnings }；sections 与 list_section/patch_section 同构。"""
    if inp:
        deck, warnings = parse_inp_text(inp)
        return {"sections": _deck_to_sections(deck), "warnings": warnings}
    return {"sections": _ws_sections(), "warnings": []}


@mcp.tool()
def generate_document(sections: dict) -> str:
    """从**按语义段的**结构生成 MCNP 输入卡文本（INP）。这是"写"入口；sections 与 read_document 的输出同构。"""
    deck = _sections_to_deck(sections)
    return _generate(deck, sections.get("rawOverrides") or sections.get("raw_overrides"))


@mcp.tool()
def validate_document(inp: str) -> dict:
    """校验 MCNP 输入卡：语法 + 解析警告。返回 ok / errors（语法）与 warnings（解析提示）。
    几何重合校验暂未含（需 FreeCAD），语法与解析检查为内置。"""
    from generator.parsers.validator import validate_inp_text
    errors = validate_inp_text(inp) or []
    _, warnings = parse_inp_text(inp)
    return {"ok": not errors, "errors": errors, "warnings": warnings}


@mcp.tool()
def list_section(inp: str | None = None, section: str | None = None) -> dict:
    """读取**某一个语义段**的结构化值。两种用法：
    - 传 inp（INP 文本）→ 解析并用该文档；
    - **不传 inp → 读「程序当前工作区」**的该段。
    section ∈ basic / surfaces / tr_cards / cells / materials / sources / tally / advanced。"""
    if section not in _SECTIONS:
        raise ValueError(f"未知 section: {section}（可选 {', '.join(_SECTIONS)}）")
    if inp:
        deck, _ = parse_inp_text(inp)
        d = _deck_to_sections(deck)
    else:
        d = _ws_sections()
    return d.get(section)


@mcp.tool()
def patch_section(inp: str | None = None, section: str | None = None, data: dict | None = None) -> str:
    """整体替换**某一个语义段**并返回新 INP 文本（全量覆盖一段）。两种用法：
    - 传 inp（INP 文本）→ 改该文档并生成；
    - **不传 inp → 改「程序当前工作区」**的该段，并更新工作区（前端界面随之变化）。
    section ∈ basic / surfaces / tr_cards / cells / materials / sources / tally / advanced。"""
    if section not in _SECTIONS:
        raise ValueError(f"未知 section: {section}（可选 {', '.join(_SECTIONS)}）")
    data = data or {}
    if inp:
        deck, _ = parse_inp_text(inp)
        deck = _apply_section_patch(deck, section, data)
        return _generate(deck)
    deck = _ws_deck()
    deck = _apply_section_patch(deck, section, data)
    _set_ws_sections(_deck_to_sections(deck))
    return _generate(deck)


# ── 快捷建栅元（add_shape）───────────────────────────────

def _next_surface_num(deck, base=101):
    """已有曲面卡的最大编号 + 1；无可解析则 base。"""
    maxn = 0
    for line in (deck.surfaces or "").split("\n"):
        s = line.split("$")[0].strip()
        if not s or s[:1].lower() == "c":
            continue
        m = _re_number(s)
        if m:
            maxn = max(maxn, int(m))
    return (maxn + 1) if maxn > 0 else base


def _next_cell_num(deck):
    maxn = 0
    for r in deck.cells:
        if r.kind == "cell" and r.cell.number > maxn:
            maxn = r.cell.number
    return maxn + 1


def _next_tr_num(deck):
    maxn = 0
    import re
    for line in (deck.tr_cards or "").split("\n"):
        m = re.match(r"\s*\*?\s*TR\s*(\d+)", line, re.I)
        if m:
            maxn = max(maxn, int(m.group(1)))
    return maxn + 1


import re


def _re_number(s):
    m = re.match(r"^(\d+)", s)
    return m.group(1) if m else None


def _fmt(v):
    if not isinstance(v, (int, float)):
        v = float(v)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.6f" % round(v, 6)).rstrip("0").rstrip(".")


def _fmt3(v):
    return ("%.3f" % round(float(v), 3)).rstrip("0").rstrip(".")


def _unit(v):
    import math
    l = math.sqrt(sum(x * x for x in v))
    return [x / l for x in v] if l > 1e-12 else [0, 0, 0]


def _apothem(radius):
    """外接半径 → apothem（RHP R1 长度 = 半径·√3/2）。"""
    import math
    return radius * math.sqrt(3) / 2


@mcp.tool()
def add_shape(inp: str, shape: str, params: dict) -> dict:
    """快捷建栅元：在当前输入卡里追加一个规则几何体，返回更新后的 INP 文本与统计。
    shape ∈ rcc | rpp | sph | hex | tet。
      rcc: {cx,cy,cz,hx,hy,hz,radius,rings,segments}
      sph: {x,y,z,radius,shells}
      hex: {cx,cy,cz,hx,hy,hz,radius,rings,segments}   （RHP 六棱柱，轴向为 hx,hy,hz）
      rpp: {cx,cy,cz,L,W,H,nx,ny,nz}                    （轴对齐六面体，可选切分）
      tet: {p1:[x,y,z],p2,p3,p4}                         （四面体，4 顶点）
    默认材料 0（真空）；imp 留空。"""
    deck, _ = parse_inp_text(inp)
    surf = _next_surface_num(deck)
    cell = _next_cell_num(deck)
    tr = _next_tr_num(deck)
    surf_lines = []
    cell_exprs = []
    n_cells = 0

    if shape == "rcc" or shape == "hex":
        cx, cy, cz = float(params["cx"]), float(params["cy"]), float(params["cz"])
        hx, hy, hz = float(params["hx"]), float(params["hy"]), float(params["hz"])
        radius = float(params["radius"])
        rings = int(params.get("rings", 1) or 1)
        segs = int(params.get("segments", 1) or 1)
        u = _unit([hx, hy, hz])
        axlen = (hx * hx + hy * hy + hz * hz) ** 0.5
        body_radius = radius * _apothem(1) if shape == "hex" else radius
        if shape == "rcc":
            names = []
            for k in range(1, rings + 1):
                nr = surf
                surf += 1
                names.append(nr)
                r = (radius * k) / rings
                surf_lines.append(f"{nr} rcc {_fmt(cx)} {_fmt(cy)} {_fmt(cz)}  {_fmt(hx)} {_fmt(hy)} {_fmt(hz)}  {_fmt(r)}")
        else:
            names = []
            e1 = None
            import math
            zc = [0, 0, 1]
            xc = [1, 0, 0]
            def cross(a, b):
                return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
            e1 = cross(u, zc)
            if (e1[0] ** 2 + e1[1] ** 2 + e1[2] ** 2) < 1e-18:
                e1 = cross(u, xc)
            e1 = _unit(e1)
            for k in range(1, rings + 1):
                nr = surf
                surf += 1
                names.append(nr)
                apo = (radius * _apothem(1) * k) / rings
                surf_lines.append(
                    f"{nr} rhp {_fmt(cx)} {_fmt(cy)} {_fmt(cz)}  {_fmt(hx)} {_fmt(hy)} {_fmt(hz)}  "
                    f"{_fmt(e1[0] * apo)} {_fmt(e1[1] * apo)} {_fmt(e1[2] * apo)}")
        # 轴向切分平面
        pnums = []
        if segs > 1:
            for k in range(1, segs):
                nr = surf
                surf += 1
                pnums.append(nr)
                d = ((hx * u[0] + hy * u[1] + hz * u[2]) * 0 + (cx * u[0] + cy * u[1] + cz * u[2])) + (axlen * k) / segs
                surf_lines.append(f"{nr} p {_fmt(u[0])} {_fmt(u[1])} {_fmt(u[2])} {_fmt(d)}")
        # 栅元：环 × 段
        for i in range(1, rings + 1):
            ring_expr = f"-{names[0]}" if i == 1 else f"+{names[i-2]} -{names[i-1]}"
            for k in range(1, segs + 1):
                if segs > 1:
                    if k == 1:
                        seg_expr = f"-{pnums[0]}"
                    elif k == segs:
                        seg_expr = f"+{pnums[k-2]}"
                    else:
                        seg_expr = f"+{pnums[k-2]} -{pnums[k-1]}"
                else:
                    seg_expr = ""
                cell_exprs.append((cell, " ".join(x for x in [ring_expr, seg_expr] if x)))
                cell += 1
                n_cells += 1
    elif shape in ("sph",):
        x, y, z = float(params["x"]), float(params["y"]), float(params["z"])
        radius = float(params["radius"])
        shells = int(params.get("shells", 1) or 1)
        names = []
        for k in range(1, shells + 1):
            nr = surf
            surf += 1
            names.append(nr)
            r = (radius * k) / shells
            surf_lines.append(f"{nr} sph {_fmt(x)} {_fmt(y)} {_fmt(z)} {_fmt(r)}")
        for k in range(1, shells + 1):
            expr = f"-{names[0]}" if k == 1 else f"+{names[k-2]} -{names[k-1]}"
            cell_exprs.append((cell, expr)); cell += 1; n_cells += 1
    elif shape == "rpp":
        cx, cy, cz = float(params["cx"]), float(params["cy"]), float(params["cz"])
        L, W, H = float(params["L"]), float(params["W"]), float(params["H"])
        nx = int(params.get("nx", 1) or 1); ny = int(params.get("ny", 1) or 1); nz = int(params.get("nz", 1) or 1)
        nr = surf; surf += 1
        surf_lines.append(f"{nr} rpp {_fmt(cx-L/2)} {_fmt(cx+L/2)} {_fmt(cy-W/2)} {_fmt(cy+W/2)} {_fmt(cz-H/2)} {_fmt(cz+H/2)}")
        px, py, pz = [], [], []
        for k in range(1, nx):
            px.append(surf); surf_lines.append(f"{surf} px {_fmt(cx-L/2+L*k/nx)}"); surf += 1
        for k in range(1, ny):
            py.append(surf); surf_lines.append(f"{surf} py {_fmt(cy-W/2+W*k/ny)}"); surf += 1
        for k in range(1, nz):
            pz.append(surf); surf_lines.append(f"{surf} pz {_fmt(cz-H/2+H*k/nz)}"); surf += 1
        for i in range(1, nx+1):
            xe = [f"+{px[i-2]}" if i > 1 else "", f"-{px[i-1]}" if i < nx else ""]
            for j in range(1, ny+1):
                ye = [f"+{py[j-2]}" if j > 1 else "", f"-{py[j-1]}" if j < ny else ""]
                for k in range(1, nz+1):
                    ze = [f"+{pz[k-2]}" if k > 1 else "", f"-{pz[k-1]}" if k < nz else ""]
                    expr = " ".join(x for x in [f"-{nr}"] + xe + ye + ze if x)
                    cell_exprs.append((cell, expr)); cell += 1; n_cells += 1
    elif shape == "tet":
        pts = [params["p1"], params["p2"], params["p3"], params["p4"]]
        import math
        def sub(a, b): return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]
        def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
        def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
        def scale(a, s): return [a[0]*s, a[1]*s, a[2]*s]
        faces = [(0,1,2,3),(0,1,3,2),(0,2,3,1),(1,2,3,0)]
        exprs = []
        for a,b,c,d in faces:
            A,B,C,D = pts[a],pts[b],pts[c],pts[d]
            A = [float(v) for v in A]; B=[float(v) for v in B]; C=[float(v) for v in C]; D=[float(v) for v in D]
            n = cross(sub(B,A), sub(C,A))
            if dot(n, sub(D,A)) < 0:
                n = scale(n, -1)
            ln = math.sqrt(sum(x*x for x in n))
            n = [x/ln for x in n] if ln > 1e-12 else [0,0,0]
            dn = dot(n, A)
            nr = surf; surf += 1
            surf_lines.append(f"{nr} p {_fmt(n[0])} {_fmt(n[1])} {_fmt(n[2])} {_fmt(dn)}")
            exprs.append(f"+{nr}")
        cell_exprs.append((cell, " ".join(exprs))); cell += 1; n_cells += 1
    else:
        raise ValueError(f"未知 shape: {shape}（可选 rcc/rpp/sph/hex/tet）")

    # 追加曲面卡文本
    if surf_lines:
        deck.surfaces = (deck.surfaces.rstrip() + "\n" + "\n".join(surf_lines) + "\n") if deck.surfaces.strip() else ("\n".join(surf_lines) + "\n")
    # 追加栅元（CellRow）
    from models import CellData, CellRow
    for num, expr in cell_exprs:
        deck.cells.append(CellRow(kind="cell", cell=CellData(number=num, material="0", density="", surface_expr=expr)))
    new_inp = _generate(deck)
    return {"inp": new_inp, "surface_added": len(surf_lines), "cells_added": n_cells,
            "cell_numbers": [n for n, _ in cell_exprs], "shape": shape}


def _mcp_http_main(host="127.0.0.1", port=8100):
    """MCP over HTTP：uvicorn 跑 FastMCP 于 /mcp，外加 /workspace 供前端同步「当前工作区」。

    - /mcp（GET/POST，MCP 协议）：AI 客户端用 http://127.0.0.1:<port>/mcp 连接。
    - /workspace（GET/PUT，纯 JSON）：前端把当前全部标签页 deck 推上来(PUT)，读当前工作区(GET，供回显)。
    均共享同一进程的 _WORKSPACE → AI 经 /mcp 读写的就是前端推上来的「当前工作区」。
    """
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware

    async def get_ws(_request):
        # 回显给前端：revision（用于判断 AI 是否改动）+ sections + 前端形态 deck（loadDeck 用）
        return JSONResponse({
            "revision": _WORKSPACE["revision"],
            "sections": _ws_sections(),
            "deck": deck_to_frontend_dict(_ws_deck()),
        })

    async def put_ws(request):
        # 前端把当前全部标签页 deck 推上来（前端 JSON 形态），后端转成 sessions 作权威
        body = await request.json()
        if isinstance(body, dict):
            if body.get("deck"):
                _set_ws_sections(_deck_to_sections(deck_from_json(body["deck"])))
            elif "sections" in body:
                _set_ws_sections(body["sections"])
            else:
                _set_ws_sections(body)
        else:
            _set_ws_sections(body)
        return JSONResponse({"ok": True, "revision": _WORKSPACE["revision"]})

    app = Starlette(routes=[
        Route("/workspace", get_ws, methods=["GET"]),
        Route("/workspace", put_ws, methods=["PUT"]),
        Mount("/mcp", app=mcp.streamable_http_app()),
    ], middleware=[Middleware(CORSMiddleware, allow_origins=["*"],
                              allow_methods=["*"], allow_headers=["*"])])
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main():
    if "--mcp-http" in sys.argv:
        port = 8100
        for a in sys.argv:
            if a.startswith("--port="):
                port = int(a.split("=", 1)[1])
        _mcp_http_main(port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
