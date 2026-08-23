"""
MCNP 生成器 API 服务 — 桥接 React 前端与 Python 后端
使用标准库 http.server，无需安装 Flask

启动: python api_server.py
监听: http://localhost:5001
"""

import json
import os
import sys
from http.server import ThreadingHTTPServer as HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# 将 app/ 和项目根目录都加入路径
PROJECT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_DIR = os.path.join(PROJECT_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from models import (
    BasicSettings, CellData, CellRow, FmeshDefinition, MaterialData, MaterialRow,
    PTRACSettings, SourceData, TallySettings, TallyDefinition, AdvancedSettings, DeckData
)
from generator.inp_generator import generate_inp_from_deck
from generator.parsers import parse_inp_text
from xsdir_db import DB as xsdir_db

PORT = 5001


def _meshtal_worker_cmd() -> list:
    """返回 meshtal worker 的 spawn 命令。

    - frozen：`[sys.executable, "--meshtal-worker"]` —— sidecar exe 入口
      mcnp_bridge.py 分派到 worker main（stdin JSON → stdout JSON），不传脚本路径，
      避免打包版 sys.executable 带参数运行冻结入口再启第二个 5001（端口冲突挂起）。
    - dev：`[sys.executable, mcnp_bridge.py, "--meshtal-worker"]` —— 同一入口分派，
      dev 真实解释器经 mcnp_bridge 走 worker。
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--meshtal-worker"]
    bridge = os.path.join(PROJECT_DIR, "gui", "backend", "mcnp_bridge.py")
    return [sys.executable, bridge, "--meshtal-worker"]


def _ptrac_worker_cmd() -> list:
    """返回 ptrac worker 的 spawn 命令（照 _meshtal_worker_cmd 打包/开发双模式）。

    - frozen：`[sys.executable, "--ptrac-worker"]` —— sidecar exe 入口分派，
      避免带脚本路径再启第二个 5001。
    - dev：`[sys.executable, mcnp_bridge.py, "--ptrac-worker"]` —— 同一入口分派。
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--ptrac-worker"]
    bridge = os.path.join(PROJECT_DIR, "gui", "backend", "mcnp_bridge.py")
    return [sys.executable, bridge, "--ptrac-worker"]


# ── preview-3d deck 指纹缓存（P0a：同 deck 二次打开免 FreeCAD 子进程）──
# 深模块见 app/preview_cache.py：put 把会话 STL 拷进缓存自有目录，clear-stl 删除
# 的是会话目录，缓存拷贝存活 → 关预览窗口后重开同一 deck 仍命中（≤1s）。
from preview_cache import PreviewCache
_PREVIEW_CACHE = PreviewCache()

# ── 3D 预览 STL 会话 ──
# 3D 预览生成的 STL 保留在此（不随请求清理），供截面复用（numpy 切平面）。
# 只在关掉 3D 预览窗口 / 主界面清空时调用 _clear_stl_session() 删除。
_STL_SESSION = {"dir": "", "cells": {}}  # cells: {number: {"material", "path"}}


def _clear_stl_session() -> None:
    """删除当前 STL 会话目录（关 3D 预览窗口 / 清空时调用）。

    与 preview_cache 联动：会话目录被清时同步驱逐指向它的缓存项，防悬挂。
    命中路径 _STL_SESSION 指向缓存目录时，本调用驱逐该缓存项并删除其目录，
    之后对已删目录的 rmtree 是无害空操作。
    """
    import shutil
    global _STL_SESSION
    d = _STL_SESSION.get("dir")
    if d:
        _PREVIEW_CACHE.evict_dir(d)
    if d and os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    _STL_SESSION = {"dir": "", "cells": {}}


# ===== 共享曲面解析（preview-3d / export-step / cross-section 共用） =====
import pymcnp.inp as _pi

_SURF_CLASSES = {}
for _name in dir(_pi):
    _obj = getattr(_pi, _name)
    if hasattr(_obj, '_KEYWORD') and hasattr(_obj, 'from_mcnp') and isinstance(_obj, type):
        _kw = (_obj._KEYWORD or '').upper()
        if _kw: _SURF_CLASSES[_kw] = _obj

def _plane_coeff_to_points(A: float, B: float, C: float, D: float) -> list:
    """平面 Ax+By+Cz=D → 3 个非共线点（pymcnp 的 P 类只支持三点定义）。

    校正三点法向与 (A,B,C) 同向，否则正侧会被翻转导致几何方向错误。
    """
    if abs(A) >= abs(B) and abs(A) >= abs(C):
        pts = [D / A, 0, 0, (D - B) / A, 1, 0, (D - C) / A, 0, 1]
    elif abs(B) >= abs(C):
        pts = [0, D / B, 0, 1, (D - A) / B, 0, 0, (D - C) / B, 1]
    else:
        pts = [0, 0, D / C, 1, 0, (D - A) / C, 0, 1, (D - B) / C]
    # 三点法向 n=(P2-P1)×(P3-P1)，若与 (A,B,C) 反向则交换 P2/P3 翻转
    import numpy as np
    p1, p2, p3 = np.array(pts[0:3]), np.array(pts[3:6]), np.array(pts[6:9])
    nrm = np.cross(p2 - p1, p3 - p1)
    if np.dot(nrm, np.array([A, B, C])) < 0:
        pts[3:6], pts[6:9] = pts[6:9], pts[3:6]
    return pts


def parse_surfaces(text: str) -> list:
    """将 MCNP 曲面文本解析为 pymcnp 表面对象列表（支持 TR 引用号）"""
    import re
    surfs = []
    for _line in text.strip().splitlines():
        _l = _line.strip()
        if not _l or _l.startswith("C") or _l.startswith("c"): continue
        _l = _l.split("$")[0].strip()  # 去掉行内注释
        if not _l: continue
        # 提取 TR 引用：后缀 *TRn（GEOUNED 常见）或 100* 前缀（transform=曲面号）
        tr_num = None
        m_tr = re.search(r"\s*\*\s*TR\s*(\d+)\s*$", _l, re.IGNORECASE)
        if m_tr:
            tr_num = int(m_tr.group(1))
            _l = _l[:m_tr.start()].rstrip()
        else:
            m_star = re.match(r"^(\d+)\s*\*\s*", _l)
            if m_star:
                tr_num = int(m_star.group(1))
                _l = _l[m_star.end():].lstrip()
        _p = _l.split()
        if len(_p) < 2: continue
        _kw_idx = 1
        if len(_p) > 2 and _SURF_CLASSES.get(_p[2].upper()): _kw_idx = 2
        _cls = _SURF_CLASSES.get(_p[_kw_idx].upper())
        if _cls is None: continue
        try:
            _s = _cls.from_mcnp(_l)
            if tr_num is not None:
                _s.transform = tr_num
            surfs.append(_s)
        except Exception:
            # P A B C D 系数形式：pymcnp 的 P 只支持三点定义，转一下再试
            if _p[_kw_idx].upper() == "P" and len(_p) == 6:
                try:
                    pts = _plane_coeff_to_points(float(_p[2]), float(_p[3]), float(_p[4]), float(_p[5]))
                    _l2 = f"{_p[0]} P " + " ".join(str(v) for v in pts)
                    _s = _cls.from_mcnp(_l2)
                    if tr_num is not None:
                        _s.transform = tr_num
                    surfs.append(_s)
                except Exception:
                    pass
    return surfs

def _model_box_from_cells_surfaces(data: dict):
    """由 cells/surfaces 推算模型包围盒（A1.2 匹配检测，请求未带 modelBox 时的契约分支）。

    契约 §4.6A「modelBox（或 surfaces/cells/tr_cards 由 handler 算）」——此前只实现了
    modelBox 直读，前端只发 cells/surfaces → match 恒 null → 不匹配横幅从未触发
    （绝不静默错位失效，2026-08-15 修复）。

    口径 = 可见外壳：只统计**非真空**栅元引用的曲面（与 preview-3d 实际渲染的 shell
    一致；真空外层球 so 1000/2000 不参与，否则模型盒会被撑成世界盒导致漏报）。
    范围 = model_extent_unpadded 的 max-abs（无 padding，保小模型真实范围）。
    """
    import re
    from freecad_preview import _pymcnp_surf_to_dict, model_extent_unpadded
    surfaces_text = str(data.get("surfaces") or "")
    cells = data.get("cells") or []
    if not surfaces_text or not cells:
        return None
    used = set()
    for c in cells:
        if str(c.get("material", "") or "").strip() == "0":
            continue  # 真空栅元不渲染外壳，不参与模型盒
        for tok in re.findall(r"-?\d+", str(c.get("surface_expr", "") or "")):
            used.add(tok.lstrip("-"))
    if not used:
        return None
    surf_dicts = []
    for s in parse_surfaces(surfaces_text):
        num = str(getattr(s, "number", "") or "").lstrip("-")
        if num in used:
            try:
                surf_dicts.append(_pymcnp_surf_to_dict(s))
            except Exception:
                continue
    ext = model_extent_unpadded(surf_dicts) if surf_dicts else 0.0
    if ext <= 0:
        return None
    return {"min": [-ext, -ext, -ext], "max": [ext, ext, ext]}

def parse_tr_cards(text: str) -> dict:
    """解析 TRn 变换卡文本为 {num: {translate, rotate}}"""
    import re
    tr_cards = {}
    for _line in text.strip().splitlines():
        _ls = _line.strip()
        if not _ls: continue
        m = re.match(r'^\*?TR(\d+)', _ls.upper())
        if not m: continue
        try:
            tn = int(m.group(1))
            if str(tn) in tr_cards: continue
            vals = [float(v) for v in _ls.split()[1:]]
            translate = vals[:3] if len(vals) >= 3 else [0, 0, 0]
            rotate = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            if len(vals) >= 9:
                import numpy as np
                rotate = [[vals[3], vals[4], vals[5]], [vals[6], vals[7], vals[8]]]
                if len(vals) >= 12:
                    rotate.append([vals[9], vals[10], vals[11]])
                else:
                    rotate.append(np.cross(rotate[0], rotate[1]).tolist())
            tr_cards[str(tn)] = {"translate": translate, "rotate": rotate}
        except: pass
    return tr_cards




def build_cells_data(cell_list: list, include_void: bool = True) -> list:
    """把前端栅元 JSON（CellRow 判别联合或旧平铺格式）解析为 FreeCAD CSG 需要的
    cells_data（跳过 raw 条件行；同一栅元号多定义只取第一个）。

    两遍处理：
      1. 先收集所有栅元（含真空）的 AST，供 #n 栅元补集引用解析；
      2. 再逐个解析 #n → 栅元 n 的完整几何补集，输出 cells_data。

    include_void=True（3D 预览）时保留真空栅元（材料 0），前端染成透明色；
    include_void=False（STEP 导出）时跳过真空栅元，但 #n 解析仍会用到其几何。
    pymcnp 几何 AST 解析失败时 ast 置 None（预览时该栅元不渲染）。
    """
    from pymcnp.types.Geometry import Geometry
    from freecad_preview import resolve_cell_complements, parenthesize_unions
    entries = []  # (number, mat_val, density, ast_node)
    seen_numbers = set()
    for cell in cell_list:
        if not isinstance(cell, dict):
            continue
        # CellRow 判别联合：raw 跳过；cell 用嵌套 cell
        if cell.get("kind") == "raw":
            continue
        if cell.get("kind") == "cell":
            cell = cell.get("cell") or {}
        expr = str(cell.get("surface_expr", "") or cell.get("surfaces", "")).strip()
        if not expr:
            continue
        number = cell.get("number", 0) or int(cell.get("num", 0) or 0)
        if number in seen_numbers:
            continue  # #ifdef 分支里同一栅元号两个定义，只取第一个
        seen_numbers.add(number)
        raw_mat_raw = cell.get("material") or cell.get("mat") or ""
        raw_mat = str(raw_mat_raw).strip().split()[0] if raw_mat_raw else ""
        mat_val = raw_mat or raw_mat_raw
        try:
            ast = Geometry.from_mcnp(parenthesize_unions(expr))
            ast_node = ast.ast
        except Exception:
            ast_node = None
        entries.append((number, mat_val, cell.get("density", ""), ast_node))

    # #n 栅元补集引用解析：先建 number → ast_node 映射（含真空栅元）
    cells_by_num = {num: node for num, _, _, node in entries}
    cells_data = []
    for number, mat_val, density, ast_node in entries:
        if not include_void and str(mat_val).split()[0] == "0":
            continue  # STEP 导出跳过真空；其几何已在上面的映射里用于 #n 解析
        if ast_node is not None:
            ast_node = resolve_cell_complements(ast_node, cells_by_num)
        # 包回 Geometry 对象（下游 _geometry_ast_to_json 用 c["ast"].ast）
        cells_data.append({
            "number": number,
            "material": mat_val,
            "ast": Geometry(ast_node) if ast_node is not None else None,
            "density": density,
        })
    return cells_data


def _deck_snapshot(surfs, cells_data, tr_cards) -> dict:
    """把预览请求解析出的曲面/栅元/TR 序列化为截面解析切片可用的 deck 快照。

    surfaces: [{number,type,params,transform}]（_pymcnp_surf_to_dict）
    cells:    [{number,material,ast}]（ast 为 _geometry_ast_to_json JSON 列表）
    tr_cards: parse_tr_cards 产出 dict
    """
    from freecad_preview import _pymcnp_surf_to_dict, _geometry_ast_to_json
    return {
        "surfaces": [_pymcnp_surf_to_dict(s) for s in surfs],
        "cells": [
            {
                "number": c.get("number"),
                "material": c.get("material", "0"),
                "ast": _geometry_ast_to_json(c["ast"].ast)
                if c.get("ast") is not None else None,
            }
            for c in cells_data
        ],
        "tr_cards": tr_cards,
    }


# ===== JSON → Dataclass 转换 =====

def _find_mcnp_exe() -> str:
    """查找 MCNP 可执行文件，返回第一个找到的完整路径（未找到返回空串）"""
    try:
        import os, winreg
        found = []; seen = set()
        def _add(p):
            if p and p not in seen: seen.add(p); found.append(p)
        # System PATH from registry
        system_paths = set()
        try:
            h = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
            system_paths.update(winreg.QueryValueEx(h, "Path")[0].split(";"))
            winreg.CloseKey(h)
            try:
                h = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
                up = winreg.QueryValueEx(h, "Path")[0]
                if up: system_paths.update(up.split(";"))
                winreg.CloseKey(h)
            except: pass
        except: pass
        # Search all PATH dirs
        all_paths = set()
        for p in os.environ.get("PATH","").split(os.pathsep):
            all_paths.add(p.strip().strip('"'))
        all_paths.update(p.strip().strip('"') for p in system_paths if p.strip())
        for d in all_paths:
            if not d or not os.path.isdir(d): continue
            for f in os.listdir(d):
                if f.lower() in ("mcnp6.exe","mcnp5.exe","mcnp6","mcnp5"): _add(os.path.join(d, f))
        # Registry
        try:
            for key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for subkey in [r"SOFTWARE\MCNP", r"SOFTWARE\Wow6432Node\MCNP"]:
                    try:
                        h = winreg.OpenKey(key, subkey)
                        pv = winreg.QueryValueEx(h, "InstallPath")[0]
                        for r, dd, ff in os.walk(pv):
                            for fn in ff:
                                if fn.lower() in ("mcnp6.exe","mcnp5.exe"): _add(os.path.join(r, fn))
                        winreg.CloseKey(h)
                    except: pass
        except: pass
        # Recursive search
        for base in ["D:/MCNP", "C:/Program Files/MCNP", "C:/MCNP"]:
            if base and os.path.isdir(base):
                for r, dd, ff in os.walk(base):
                    for fn in ff:
                        if fn.lower() in ("mcnp6.exe","mcnp5.exe","mcnp6","mcnp5"): _add(os.path.join(r, fn))
        return found[0] if found else ""
    except Exception:
        return ""


def _open_in_explorer(path: str) -> None:
    """在文件资源管理器中打开目录（Windows）。失败静默，不打断主流程。"""
    try:
        if not path:
            return
        os.makedirs(path, exist_ok=True)
        if os.path.isdir(path):
            os.startfile(path)  # type: ignore[attr-defined]
    except Exception:
        pass


def _basic_from_dict(d: dict) -> BasicSettings:
    return BasicSettings(
        title=d.get("title", ""), mode_n=d.get("mode_n", False), mode_p=d.get("mode_p", False),
        mode_e=d.get("mode_e", False), mode_h=d.get("mode_h", False), mode_he=d.get("mode_he", False),
        mode_d=d.get("mode_d", False), mode_t=d.get("mode_t", False), mode_a=d.get("mode_a", False),
        nps=d.get("nps", ""), ctme=d.get("ctme", ""), act=d.get("act", ""),
        print_pr=d.get("print_pr", ""), phys_fis=d.get("phys_fis", True),
    )

def _cells_from_list(arr: list) -> list[CellRow]:
    """前端 cells（CellRow 判别联合）→ 后端 CellRow[]。

    CellRow 的字段嵌在 c["cell"] 里（判别联合）；旧平铺格式字段在顶层。
    """
    out = []
    for c in arr:
        if not isinstance(c, dict):
            continue
        if c.get("kind") == "raw":
            out.append(CellRow(kind="raw", text=c.get("text", "")))
            continue
        cell_dict = c.get("cell") if isinstance(c.get("cell"), dict) else c
        out.append(CellRow(kind="cell", cell=CellData(
            number=cell_dict.get("number", 0), material=cell_dict.get("material", "0"), density=cell_dict.get("density", ""),
            surface_expr=cell_dict.get("surface_expr", ""), imp_n=cell_dict.get("imp_n", ""), imp_p=cell_dict.get("imp_p", ""),
            imp_e=cell_dict.get("imp_e", ""), vol=cell_dict.get("vol", ""), pwt=cell_dict.get("pwt", ""), ext=cell_dict.get("ext", ""),
            fcl=cell_dict.get("fcl", ""), u=cell_dict.get("u", ""), fill=cell_dict.get("fill", ""), lat=cell_dict.get("lat", ""),
            trcl=cell_dict.get("trcl", ""), tmp=cell_dict.get("tmp", ""), other_params=cell_dict.get("other_params", ""),
            render=cell_dict.get("render", True), comment=cell_dict.get("comment", ""),
        )))
    return out

def _materials_from_list(arr: list) -> list[MaterialData]:
    # 前端 deck 统一用 nuclides，导入路径会额外带 rows（api_server 405-407 映射）。
    # 这里兼容两者：rows 优先，nuclides 兜底；行按 kind 判别（nuclide | raw）。
    def _row(r: dict) -> MaterialRow:
        if isinstance(r, dict) and r.get("kind") == "raw":
            return MaterialRow(kind="raw", text=r.get("text", ""))
        return MaterialRow(kind="nuclide", zaid=r.get("zaid", ""), fraction=r.get("fraction", ""))
    return [MaterialData(
        number=m.get("number", 0),
        rows=[_row(r) for r in (m.get("rows") or m.get("nuclides") or [])],
        comment=m.get("comment", ""), options=m.get("options", ""), mt_card=m.get("mt_card", ""),
        formula=m.get("formula", ""),
    ) for m in arr]

def _sources_from_list(arr: list) -> list[SourceData]:
    return [SourceData(
        number=s.get("number", 0), par=s.get("par", ""), erg=s.get("erg", ""),
        pos_x=s.get("pos_x", ""), pos_y=s.get("pos_y", ""), pos_z=s.get("pos_z", ""),
        wgt=s.get("wgt", ""), cel=s.get("cel", ""), dir_=s.get("dir_", ""),
        probability=s.get("prob", ""), tme=s.get("tme", ""), vec=s.get("vec", ""),
        axs=s.get("axs", ""), rad=s.get("rad", ""), ext=s.get("ext", ""),
        sur=s.get("sur", ""), nrm=s.get("nrm", ""), tr=s.get("tr", ""),
        ccc=s.get("ccc", ""), ara=s.get("ara", ""), rate=s.get("rate", ""),
        sdef_extra=s.get("sdef_extra", ""),
    ) for s in arr]

def _fmesh_from_list(arr: list) -> list[FmeshDefinition]:
    """前端 fmesh_defs 列表 → FmeshDefinition（缺 key 容忍，照 FM multiplier 先例）。"""
    return [FmeshDefinition(
        number=f.get("number", 0), kind=f.get("kind", "FMESH"),
        particle=f.get("particle", ""), geom=f.get("geom", "xyz"),
        origin=f.get("origin", ""), imesh=f.get("imesh", ""), iints=f.get("iints", ""),
        jmesh=f.get("jmesh", ""), jints=f.get("jints", ""), kmesh=f.get("kmesh", ""),
        kints=f.get("kints", ""), emesh=f.get("emesh", ""),
        emints=f.get("emints", f.get("eints", "")),
        tmesh=f.get("tmesh", ""),
        tmints=f.get("tmints", f.get("t_ints", "")),
        mat=f.get("mat", ""), out=f.get("out", ""),
        factor=f.get("factor", ""),
        axs=f.get("axs", ""), vec=f.get("vec", ""), tr=f.get("tr", ""),
        raw=f.get("raw", ""),
    ) for f in arr]

def _ptrac_from_dict(d) -> PTRACSettings | None:
    """前端 tally.ptrac 对象 → PTRACSettings（缺 key 容忍；无/空 → None）。"""
    if not isinstance(d, dict):
        return None
    types = d.get("types") or d.get("type") or []
    if isinstance(types, str):
        types = [p.strip().upper() for p in types.replace(",", " ").split() if p.strip()]
    else:
        types = [str(p).strip().upper() for p in types if str(p).strip()]
    return PTRACSettings(
        enabled=bool(d.get("enabled", False)),
        file=str(d.get("file", "ASC") or "ASC"),
        write=str(d.get("write", "ALL") or "ALL"),
        max=str(d.get("max", "") or ""),
        types=types,
        nps=str(d.get("nps", "") or ""),
        cell=str(d.get("cell", "") or ""),
        surface=str(d.get("surface", "") or ""),
        value=str(d.get("value", "") or ""),
        event=str(d.get("event", "") or ""),
        buffer=str(d.get("buffer", "") or ""),
        filter=str(d.get("filter", "") or ""),
        tally=str(d.get("tally", "") or ""),
        meph=str(d.get("meph", "") or ""),
    )

def _tally_from_dict(d: dict) -> TallySettings:
    tallies = []
    for t in d.get("tallies", []):
        tallies.append(TallyDefinition(
            type=t.get("type", "F4"), number=t.get("number", 4),
            particles=t.get("particles") if isinstance(t.get("particles"), list) else [p.lower().strip() for p in t.get("particle", "n").replace(",", " ").split() if p.strip()], params=t.get("params", ""),
            generate_en=t.get("generate_en", t.get("enableEn", False)), generate_tn=t.get("generate_tn", t.get("enableTn", False)),
            multiplier=t.get("multiplier", ""),
        ))
    return TallySettings(tallies=tallies,
        fmesh_defs=_fmesh_from_list(d.get("fmesh_defs", [])),
        ptrac=_ptrac_from_dict(d.get("ptrac")),
        e_min=d.get("e_min", ""), e_max=d.get("e_max", ""), e_bins=d.get("e_bins", 0),
        e_log=d.get("e_log", False), e_custom_enabled=d.get("e_custom_enabled", False),
        e_custom_text=d.get("e_custom_text", ""),
        t0_min=d.get("t0_min", ""), t0_max=d.get("t0_max", ""), t0_bins=d.get("t0_bins", 0),
        t0_log=d.get("t0_log", False), t0_custom_enabled=d.get("t0_custom_enabled", False),
        t0_custom_text=d.get("t0_custom_text", ""), e_cards_text=d.get("e_cards_text", ""),
        t_cards_text=d.get("t_cards_text", ""),
        cut_n_t=d.get("cut_n_t", ""), cut_n_e=d.get("cut_n_e", ""), cut_n_wc1=d.get("cut_n_wc1", ""),
        cut_n_wc2=d.get("cut_n_wc2", ""), cut_n_swtm=d.get("cut_n_swtm", ""),
        cut_p_t=d.get("cut_p_t", ""), cut_p_e=d.get("cut_p_e", ""), cut_p_wc1=d.get("cut_p_wc1", ""),
        cut_p_wc2=d.get("cut_p_wc2", ""), cut_p_swtm=d.get("cut_p_swtm", ""),
        cut_e_t=d.get("cut_e_t", ""), cut_e_e=d.get("cut_e_e", ""), cut_e_wc1=d.get("cut_e_wc1", ""),
        cut_e_wc2=d.get("cut_e_wc2", ""), cut_e_swtm=d.get("cut_e_swtm", ""),
        cut_h_t=d.get("cut_h_t", ""), cut_h_e=d.get("cut_h_e", ""), cut_h_wc1=d.get("cut_h_wc1", ""),
        cut_h_wc2=d.get("cut_h_wc2", ""), cut_h_swtm=d.get("cut_h_swtm", ""),
        cut_he_t=d.get("cut_he_t", ""), cut_he_e=d.get("cut_he_e", ""), cut_he_wc1=d.get("cut_he_wc1", ""),
        cut_he_wc2=d.get("cut_he_wc2", ""), cut_he_swtm=d.get("cut_he_swtm", ""),
        cut_d_t=d.get("cut_d_t", ""), cut_d_e=d.get("cut_d_e", ""), cut_d_wc1=d.get("cut_d_wc1", ""),
        cut_d_wc2=d.get("cut_d_wc2", ""), cut_d_swtm=d.get("cut_d_swtm", ""),
        cut_t_t=d.get("cut_t_t", ""), cut_t_e=d.get("cut_t_e", ""), cut_t_wc1=d.get("cut_t_wc1", ""),
        cut_t_wc2=d.get("cut_t_wc2", ""), cut_t_swtm=d.get("cut_t_swtm", ""),
        cut_a_t=d.get("cut_a_t", ""), cut_a_e=d.get("cut_a_e", ""), cut_a_wc1=d.get("cut_a_wc1", ""),
        cut_a_wc2=d.get("cut_a_wc2", ""), cut_a_swtm=d.get("cut_a_swtm", ""),
    )

def _adv_from_dict(d: dict) -> AdvancedSettings:
    return AdvancedSettings(
        other_cards=d.get("other_cards", ""),
        phys_n_emax=d.get("phys_n_emax", ""), phys_n_emcnf=d.get("phys_n_emcnf", ""),
        phys_n_iunr=d.get("phys_n_iunr", ""), phys_n_dnb=d.get("phys_n_dnb", ""),
        phys_n_fisnu=d.get("phys_n_fisnu", ""),
        phys_p_emcpf=d.get("phys_p_emcpf", ""), phys_p_ides=d.get("phys_p_ides", ""),
        phys_p_nocoh=d.get("phys_p_nocoh", ""), phys_p_ispn=d.get("phys_p_ispn", ""),
        phys_p_nodop=d.get("phys_p_nodop", ""),
        phys_e_emax=d.get("phys_e_emax", ""), phys_e_ides=d.get("phys_e_ides", ""),
        phys_e_iphoto=d.get("phys_e_iphoto", ""), phys_e_ibad=d.get("phys_e_ibad", ""),
        phys_e_istrg=d.get("phys_e_istrg", ""), phys_e_bnum=d.get("phys_e_bnum", ""),
        phys_e_xnum=d.get("phys_e_xnum", ""), phys_e_rnok=d.get("phys_e_rnok", ""),
        phys_e_enum=d.get("phys_e_enum", ""), phys_e_numb=d.get("phys_e_numb", ""),
        phys_h_emax=d.get("phys_h_emax", ""), phys_h_ie=d.get("phys_h_ie", ""),
        phys_h_ipr=d.get("phys_h_ipr", ""), phys_h_rgas=d.get("phys_h_rgas", ""),
        phys_h_emin=d.get("phys_h_emin", ""), phys_h_ecut=d.get("phys_h_ecut", ""),
        phys_he_emax=d.get("phys_he_emax", ""), phys_he_ie=d.get("phys_he_ie", ""),
        phys_he_ipr=d.get("phys_he_ipr", ""), phys_he_rgas=d.get("phys_he_rgas", ""),
        phys_he_emin=d.get("phys_he_emin", ""), phys_he_ecut=d.get("phys_he_ecut", ""),
        source_mode=d.get("source_mode", "fixed"),
        sdef_par=d.get("sdef_par", ""), sdef_erg=d.get("sdef_erg", ""),
        sdef_pos_x=d.get("sdef_pos_x", ""), sdef_pos_y=d.get("sdef_pos_y", ""),
        sdef_pos_z=d.get("sdef_pos_z", ""), sdef_wgt=d.get("sdef_wgt", ""),
        sdef_dir=d.get("sdef_dir", ""), sdef_cel=d.get("sdef_cel", ""),
        sdef_tme=d.get("sdef_tme", ""), sdef_vec=d.get("sdef_vec", ""),
        sdef_axs=d.get("sdef_axs", ""), sdef_rad=d.get("sdef_rad", ""),
        sdef_ext=d.get("sdef_ext", ""), sdef_sur=d.get("sdef_sur", ""),
        sdef_nrm=d.get("sdef_nrm", ""), sdef_tr=d.get("sdef_tr", ""),
        sdef_ccc=d.get("sdef_ccc", ""), sdef_ara=d.get("sdef_ara", ""),
        sdef_rate=d.get("sdef_rate", ""), sdef_raw_text=d.get("sdef_raw_text", ""),
        sdef_extra=d.get("sdef_extra", ""),
        kcode_nsrc=d.get("kcode_nsrc", ""), kcode_rkk=d.get("kcode_rkk", ""),
        kcode_ikz=d.get("kcode_ikz", ""), kcode_kct=d.get("kcode_kct", ""),
        kcode_knrm=d.get("kcode_knrm", ""), ksrc_points=d.get("ksrc_points", ""),
        kcode_msrk=d.get("kcode_msrk", ""), kcode_mrkp=d.get("kcode_mrkp", ""),
        kcode_kc8=d.get("kcode_kc8", ""),
        hsrc_enabled=d.get("hsrc_enabled", False), hsrc_text=d.get("hsrc_text", ""),
        sdef_distributions=d.get("sdef_distributions", ""),
        ssw_surf=d.get("ssw_surf", ""), ssw_sym=d.get("ssw_sym", ""),
        ssw_pty=d.get("ssw_pty", ""), ssw_cel=d.get("ssw_cel", ""),
        ssr_surf=d.get("ssr_surf", ""), ssr_mode=d.get("ssr_mode", ""),
        ssr_cel=d.get("ssr_cel", ""), ssr_pty=d.get("ssr_pty", ""),
        ssr_col=d.get("ssr_col", ""), ssr_wgt=d.get("ssr_wgt", ""),
        ssr_tr=d.get("ssr_tr", ""), ssr_psc=d.get("ssr_psc", ""),
    )

def deck_from_json(data: dict) -> DeckData:
    """JSON → DeckData 转换"""
    return DeckData(
        basic=_basic_from_dict(data.get("basic", {})),
        surfaces=data.get("surfaces", ""), tr_cards=data.get("tr_cards", ""),
        cells=_cells_from_list(data.get("cells", [])),
        materials=_materials_from_list(data.get("materials", [])),
        sources=_sources_from_list(data.get("sources", [])),
        tally=_tally_from_dict(data.get("tally", {})),
        adv=_adv_from_dict(data.get("adv", {})),
    )


def _deck_to_frontend_dict(deck: DeckData) -> dict:
    """后端 DeckData → 前端 deck JSON（与 /api/parse-inp 的序列化一致）。

    供 /api/text-to-section 复用：把解析出的 deck 转成前端可 patch 的结构。
    """
    import dataclasses
    def to_dict(obj):
        if dataclasses.is_dataclass(obj):
            return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list):
            return [to_dict(x) for x in obj]
        return obj
    deck_dict = to_dict(deck)
    # 后端用 rows，前端用 nuclides → 加入映射（行含 kind 判别）
    for m in deck_dict.get("materials", []):
        if "rows" in m and "nuclides" not in m:
            m["nuclides"] = m["rows"]
    # cells: CellRow 判别联合（raw 行保留 text；cell 行嵌套 CellData，并补 camelCase 字段）
    for c in deck_dict.get("cells", []):
        if c.get("kind") == "raw":
            continue
        cell = c.get("cell") or {}
        cell["num"] = str(cell.get("number", ""))
        cell["surfaces"] = cell.get("surface_expr", "")
        cell["impN"] = cell.get("imp_n", "")
        cell["impP"] = cell.get("imp_p", "")
        cell["impE"] = cell.get("imp_e", "")
    # Tally: backend → frontend 字段名映射
    tally_raw = deck_dict.get("tally", {})
    deck_dict["tallies"] = [{
        "type": td.get("type", ""), "number": td.get("number", 0),
        "particle": " ".join(td.get("particles", [])),
        "params": td.get("params", ""),
        "enableEn": td.get("generate_en", False),
        "enableTn": td.get("generate_tn", False),
        "multiplier": td.get("multiplier", ""),
    } for td in tally_raw.get("tallies", [])]
    return deck_dict


def _fmt_num(v) -> str:
    """pandas 数值 → 显示字符串（None/NaN → 空串）。"""
    if v is None:
        return ""
    try:
        if v != v:  # NaN
            return ""
    except Exception:
        pass
    s = str(v).strip()
    return "" if s in ("", "nan", "None") else s


# ===== HTTP 服务 =====

class MCNPHandler(BaseHTTPRequestHandler):
    """处理所有 API 请求"""

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        # Browser-friendly: handle GET the same as POST for API
        self.do_POST()

    def do_POST(self):
        parsed = urlparse(self.path)
        handlers = {
            "/api/generate": self._handle_generate,
            "/api/expand-formula": self._handle_expand_formula,
            "/api/parse-inp": self._handle_parse_inp,
            "/api/save-inp": self._handle_save_inp,
            "/api/choose-dir": self._handle_choose_dir,
            "/api/choose-file": self._handle_choose_file,
            "/api/run-mcnp": self._handle_run_mcnp,
            "/api/xsdir-check": self._handle_xsdir_check,
            "/api/import-step": self._handle_import_step,
            "/api/mcnp-detect": self._handle_mcnp_detect,
            "/api/check-freecad": self._handle_check_freecad,
            "/api/set-freecad-path": self._handle_set_freecad_path,
            "/api/choose-freecad-path": self._handle_choose_freecad_path,
            "/api/validate-inp": self._handle_validate_inp,
            "/api/validate-zaid": self._handle_validate_zaid,
            "/api/parse-outp": self._handle_parse_outp,
            "/api/parse-keff": self._handle_parse_keff,
            "/api/xsdir-search": self._handle_xsdir_search,
            "/api/generate-step": self._handle_generate_step,
            "/api/export-step": self._handle_export_step,
            "/api/preview-3d": self._handle_preview_3d,
            "/api/serve-file": self._handle_serve_file,
            "/api/cross-section": self._handle_cross_section,
            "/api/clear-stl": self._handle_clear_stl,
            "/api/section-to-text": self._handle_section_to_text,
            "/api/text-to-section": self._handle_text_to_section,
            "/api/meshtal-detect": self._handle_meshtal_detect,
            "/api/meshtal-parse": self._handle_meshtal_parse,
            "/api/meshtal-texture": self._handle_meshtal_texture,
            "/api/ptrac-detect": self._handle_ptrac_detect,
            "/api/ptrac-parse": self._handle_ptrac_parse,
            "/api/sweep-plan": self._handle_sweep_plan,
            "/api/sweep-run": self._handle_sweep_run,
            "/api/sweep-dashboard": self._handle_sweep_dashboard,
            "/api/diff-inp": self._handle_diff_inp,
            "/api/check-overlap": self._handle_check_overlap,
            "/api/quick-add-check": self._handle_quick_add_check,
        }
        handler = handlers.get(parsed.path)
        if handler:
            handler()
        else:
            self.send_response(404)
            self.end_headers()

    # ── 参数扫描（sweep）──
    def _handle_sweep_plan(self):
        """参数扫描规划：笛卡尔组合 + 应用到 deck 文本（不执行 MCNP）。"""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
            import sweep
            data = self._read_body() or {}
            deck_text = data.get("deck") or ""
            parameters = data.get("parameters") or []
            combos = sweep.cartesian(parameters)
            previews = [
                sweep.apply_parameters(deck_text, c, parameters)
                for c in combos[:3]
            ]
            self._ok({"count": len(combos), "combos": combos, "previews": previews})
        except Exception as e:
            self._err(str(e))

    def _handle_sweep_run(self):
        """参数扫描执行：逐组合写 INP → 调 MCNP → 提取 keff → 汇总 TSV。"""
        try:
            import subprocess
            import tempfile
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
            import sweep
            data = self._read_body() or {}
            deck_text = data.get("deck") or ""
            parameters = data.get("parameters") or []
            combos = sweep.cartesian(parameters)
            if len(combos) > 50:
                self._ok({"status": "error",
                          "message": f"组合数 {len(combos)} 超上限 50，请缩小参数范围"})
                return
            exe = _find_mcnp_exe()
            if not exe:
                self._ok({"status": "error", "message": "未检测到 MCNP 可执行文件"})
                return
            base_dir = tempfile.mkdtemp(prefix="mcnp_sweep_")
            records = []
            for i, combo in enumerate(combos, 1):
                inp = sweep.apply_parameters(deck_text, combo, parameters)
                run_dir = os.path.join(base_dir, sweep.run_dir_name(i))
                os.makedirs(run_dir, exist_ok=True)
                inp_path = os.path.join(run_dir, "sweep.i")
                with open(inp_path, "w", encoding="utf-8") as f:
                    f.write(inp)
                rec = {"index": i, "parameters": combo, "inputFile": inp_path,
                       "outputDir": run_dir, "exitCode": None, "keff": None}
                try:
                    proc = subprocess.run(
                        [exe, "i=sweep.i"], cwd=run_dir,
                        capture_output=True, text=True, timeout=300,
                    )
                    rec["exitCode"] = proc.returncode
                    rec["keff"] = sweep.parse_keff(
                        (proc.stdout or "") + "\n" + (proc.stderr or ""))
                except subprocess.TimeoutExpired:
                    pass
                # 收敛序列（仪表盘小图）：优先读 run 目录里的 mctal
                try:
                    import glob
                    mctal_paths = sorted(glob.glob(os.path.join(run_dir, "mctal*")))
                    if mctal_paths:
                        with open(mctal_paths[0], "r", encoding="utf-8",
                                  errors="replace") as f:
                            hist = sweep.parse_keff_history(f.read())
                        if hist:
                            rec["convergence"] = hist
                            if hist.get("std"):
                                rec["keffStd"] = hist["std"][-1]
                except Exception:
                    pass
                records.append(rec)
            tsv = sweep.build_summary_tsv(parameters, records)
            manifest = sweep.build_manifest("sweep.i", "mcnp", parameters, records)
            manifest_path = os.path.join(base_dir, "sweep-manifest.json")
            try:
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            self._ok({"status": "ok", "baseDir": base_dir, "records": records,
                      "summaryTsv": tsv, "manifest": manifest,
                      "manifestPath": manifest_path})
        except Exception as e:
            self._err(str(e))

    def _handle_sweep_dashboard(self):
        """读取历史扫描目录（sweep-manifest.json），补齐缺失的收敛序列后返回。"""
        try:
            data = self._read_body() or {}
            base_dir = data.get("baseDir", "")
            manifest_path = os.path.join(base_dir, "sweep-manifest.json")
            if not os.path.isfile(manifest_path):
                self._err(f"扫描清单不存在：{manifest_path}")
                return
            with open(manifest_path, "r", encoding="utf-8-sig") as f:
                manifest = json.load(f)
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
            import glob
            import sweep
            for rec in manifest.get("runs", []):
                if rec.get("convergence"):
                    continue
                run_dir = rec.get("outputDir", "")
                if not run_dir or not os.path.isdir(run_dir):
                    continue
                try:
                    mctal_paths = sorted(glob.glob(os.path.join(run_dir, "mctal*")))
                    if not mctal_paths:
                        continue
                    with open(mctal_paths[0], "r", encoding="utf-8",
                              errors="replace") as f:
                        hist = sweep.parse_keff_history(f.read())
                    if hist:
                        rec["convergence"] = hist
                        if hist.get("std"):
                            rec["keffStd"] = hist["std"][-1]
                except Exception:
                    continue
            self._ok({"status": "ok", "baseDir": base_dir, "manifest": manifest})
        except Exception as e:
            self._err(str(e))

    def _handle_diff_inp(self):
        """两段 INP 文本行级 diff（unified 格式 + 增删统计）。"""
        try:
            data = self._read_body() or {}
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
            from diff_inp import diff_stats, unified_diff_text
            text_a = data.get("text_a", "")
            text_b = data.get("text_b", "")
            diff = unified_diff_text(text_a, text_b)
            self._ok({
                "status": "ok",
                "diff": diff,
                "stats": diff_stats(diff),
            })
        except Exception as e:
            self._err(str(e))

    # ── 3D 重合检测（独立端点，不碰 preview-3d 契约）──
    def _handle_check_overlap(self):
        """重合检测：AABB 空间索引候选 + FreeCAD 精确布尔 + GQ/SQ 解析采样探针。

        入参与 preview-3d 同（surfaces/cells/tr_cards）；真空栅元参与检测。
        结果按 deck 指纹缓存（overlaps.json）。
        """
        try:
            data = self._read_body()
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", [])
            tr_text = data.get("tr_cards", "")
            fp = _PREVIEW_CACHE.fingerprint(surf_text, cell_list, tr_text)
            cached = _PREVIEW_CACHE.get_overlaps(fp)
            if cached is not None:
                self._ok(cached)
                return

            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
            from step_importer import StepImporter
            from freecad_preview import FreeCADEngine
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "ok", "overlaps": [], "truncated": False,
                          "unresolved": [],
                          "message": "未检测到 FreeCAD，请安装后重试"})
                return
            surfs = parse_surfaces(surf_text)
            if not surfs:
                self._ok({"status": "ok", "overlaps": [], "truncated": False,
                          "unresolved": [], "message": "未解析到有效曲面"})
                return
            tr_cards = parse_tr_cards(tr_text)
            cells_data = build_cells_data(cell_list, include_void=True)
            if not cells_data:
                self._ok({"status": "ok", "overlaps": [], "truncated": False,
                          "unresolved": [], "message": "没有可检测的栅元"})
                return
            engine = FreeCADEngine(freecad_bin)
            engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl",
                                  check_overlaps=True)
            engine.cleanup()
            report = {"status": "ok", "overlaps": engine.overlaps,
                      "truncated": engine.overlap_truncated,
                      "unresolved": engine.overlap_unresolved,
                      "zero_volume": engine.zero_volume}
            _PREVIEW_CACHE.put_overlaps(fp, report)
            self._ok(report)
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _handle_quick_add_check(self):
        """快捷建栅元重合检查：新栅元 vs 已有栅元 → 重叠列表 + 推荐补集方向。

        recommended ∈ "new_hole"（新 # 已有）| "existing_hole"（已有 # 新）。
        """
        try:
            data = self._read_body()
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", []) or []
            tr_text = data.get("tr_cards", "")
            new_cell = data.get("new_cell") or {}
            new_cells = data.get("new_cells") or ([new_cell] if new_cell else [])
            new_cells = [c for c in new_cells if c and c.get("surface_expr")]
            if not new_cells:
                self._ok({"status": "ok", "overlaps": [], "recommended": "new_hole",
                          "message": "新栅元缺少几何表达式"})
                return
            new_nums = [int(c.get("number", 0) or 0) for c in new_cells]

            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
            from step_importer import StepImporter
            from freecad_preview import FreeCADEngine
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "ok", "overlaps": [], "recommended": "new_hole",
                          "message": "未检测到 FreeCAD，请安装后重试"})
                return
            surfs = parse_surfaces(surf_text)
            tr_cards = parse_tr_cards(tr_text)
            all_cells = list(cell_list) + [
                {"kind": "cell", "cell": c} for c in new_cells]
            cells_data = build_cells_data(all_cells, include_void=True)
            engine = FreeCADEngine(freecad_bin)
            engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl",
                                  check_overlaps=True, focus_nums=new_nums)
            engine.cleanup()
            overlaps = engine.overlaps
            # 任一重合占比 >0.98（新栅元几乎完全在已有内）→ 已有让位
            recommended = "existing_hole" if any(
                float(o.get("volumeFraction", 0)) > 0.98 for o in overlaps
            ) else "new_hole"
            self._ok({"status": "ok", "overlaps": overlaps,
                      "recommended": recommended,
                      "truncated": engine.overlap_truncated,
                      "unresolved": engine.overlap_unresolved,
                      "zero_volume": engine.zero_volume})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _read_body(self) -> dict:
        content_len = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(content_len))

    def _ok(self, data: dict):
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", **data}, ensure_ascii=False).encode("utf-8"))

    def _err(self, msg: str, status=500, hint=""):
        import traceback
        tb = traceback.format_exc()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {"status": "error", "message": msg, "traceback": tb}
        # F4：hint 非空才带（对既有 25 端点加性兼容，响应字段零变化）
        if hint:
            payload["hint"] = hint
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    # ── 生成 ──
    def _handle_generate(self):
        try:
            data = self._read_body()
            deck = deck_from_json(data)
            # raw_overrides 是独立参数（DeckData 无此字段），必须单独传给生成器
            inp_text = generate_inp_from_deck(deck, data.get("raw_overrides") or {})
            self._ok({"inp": inp_text})
        except Exception as e:
            self._err(str(e))

    # ── 化学式展开 ──
    def _handle_expand_formula(self):
        try:
            data = self._read_body()
            text = data.get("formula", "").strip()
            if not text: raise ValueError("化学式为空")
            # is_weight：True=质量份额（MCNP 负号约定），False=原子份额（正号）。
            # 默认 True 保持向后兼容（前端未传/传 null 时行为与现状一致）。
            is_weight = data.get("is_weight", True)
            if is_weight is None:
                is_weight = True
            elif isinstance(is_weight, str):
                is_weight = is_weight.strip().lower() not in ("", "0", "false", "no")
            import pymcnp
            formulas = {}
            for line in text.split("\n"):
                for part in line.split(","):
                    part = part.strip()
                    if not part: continue
                    if ":" in part:
                        f, r = part.split(":", 1)
                        formulas[f.strip()] = float(r.strip())
                    else:
                        tok = part.split()
                        formulas[tok[0]] = float(tok[1]) if len(tok) > 1 else 1
            all_rows = []
            for sym, ratio in formulas.items():
                sub = pymcnp.inp.M_0.from_formula({sym: 1}, is_weight=is_weight, cutoff=1e-9)
                parts = str(sub).replace("&", " ").replace("\n", " ").split()
                for k in range(1, len(parts)-1, 2):  # 跳过 m1 标签
                    zaid = parts[k]
                    frac = float(parts[k+1]) * ratio
                    if xsdir_db.loaded and "." in zaid:
                        num = zaid.split(".")[0]
                        matches = [z for z in xsdir_db.zaids if z.split(".")[0] == num]
                        if matches: zaid = matches[0]
                    all_rows.append((zaid, frac))
            if not all_rows: raise ValueError("pymcnp 返回空")
            total = sum(abs(f) for _, f in all_rows)
            if total > 0 and abs(total-1) > 1e-9:
                all_rows = [(z, f/total) for z, f in all_rows]
            nuclides = [{"zaid": z.lstrip("0") or "0", "fraction": f"{frac:.6f}"} for z, frac in all_rows]
            self._ok({"nuclides": nuclides})
        except Exception as e:
            self._err(str(e))

    # ── INP 解析 ──
    def _handle_parse_inp(self):
        try:
            data = self._read_body()
            text = data.get("inp", "")
            if not text: raise ValueError("INP 内容为空")
            deck, warnings = parse_inp_text(text)
            import dataclasses
            def to_dict(obj):
                if dataclasses.is_dataclass(obj): return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
                if isinstance(obj, list): return [to_dict(x) for x in obj]
                return obj
            deck_dict = to_dict(deck)
            # 后端用 rows，前端用 nuclides → 加入映射（行含 kind 判别）
            for m in deck_dict.get("materials", []):
                if "rows" in m and "nuclides" not in m:
                    m["nuclides"] = m["rows"]
            # cells: CellRow 判别联合（raw 行保留 text；cell 行嵌套 CellData，并补 camelCase 字段）
            for c in deck_dict.get("cells", []):
                if c.get("kind") == "raw":
                    continue
                cell = c.get("cell") or {}
                cell["num"] = str(cell.get("number", ""))
                cell["surfaces"] = cell.get("surface_expr", "")
                cell["impN"] = cell.get("imp_n", "")
                cell["impP"] = cell.get("imp_p", "")
                cell["impE"] = cell.get("imp_e", "")
            # 源项模式：backend 的 adv.source_mode → 顶层 sourceMode
            adv = deck_dict.get("adv", {})
            deck_dict["sourceMode"] = {"distribution": "sdef", "fixed": "fixed", "kcode": "kcode", "surface": "surface"}.get(adv.get("source_mode", ""), "fixed")
            deck_dict["sdefFields"] = {k: v for k, v in adv.items() if k.startswith("sdef_")}
            deck_dict["kcodeFields"] = {k: v for k, v in adv.items() if k.startswith("kcode_")}
            deck_dict["ksrcPoints"] = adv.get("ksrc_points", "")
            deck_dict["sdefRawText"] = adv.get("sdef_raw_text", "")
            # 结构化分布 + 面源（新）
            try:
                deck_dict["distributions"] = json.loads(adv.get("sdef_distributions", "[]"))
            except Exception:
                deck_dict["distributions"] = []
            deck_dict["sswFields"] = {"surf": adv.get("ssw_surf", ""), "sym": adv.get("ssw_sym", ""),
                                      "pty": adv.get("ssw_pty", ""), "cel": adv.get("ssw_cel", "")}
            deck_dict["ssrFields"] = {"surf": adv.get("ssr_surf", ""), "mode": adv.get("ssr_mode", ""),
                                      "cel": adv.get("ssr_cel", ""), "pty": adv.get("ssr_pty", ""),
                                      "col": adv.get("ssr_col", ""), "wgt": adv.get("ssr_wgt", ""),
                                      "tr": adv.get("ssr_tr", ""), "psc": adv.get("ssr_psc", "")}
            # Tally: backend → frontend 字段名映射
            tally_raw = deck_dict.get("tally", {})
            raw_tallies = tally_raw.get("tallies", [])
            deck_dict["tallies"] = [{
                "type": td.get("type", ""),
                "number": td.get("number", 0),
                "particle": " ".join(td.get("particles", [])),
                "params": td.get("params", ""),
                "enableEn": td.get("generate_en", False),
                "enableTn": td.get("generate_tn", False),
                "multiplier": td.get("multiplier", ""),
            } for td in raw_tallies]
            deck_dict["_warnings"] = warnings
            self._ok({"deck": deck_dict})
        except Exception as e:
            self._err(str(e))

    # ── 片段互转：表单 → 文本 ──
    def _handle_section_to_text(self):
        """把某模块的表单数据生成该模块的 INP 文本（供切到文本模式时预填）。

        入参: {section: "materials"|"cells"|"tally", deck: {前端 deck}}
        返回: {text}
        """
        try:
            data = self._read_body()
            section = data.get("section", "")
            deck = deck_from_json(data.get("deck") or {})
            from generator.inp_generator import _generate_materials, _generate_cells
            text = ""
            if section == "materials":
                text = "\n".join(_generate_materials(deck.materials))
            elif section == "cells":
                text = "\n".join(_generate_cells(deck.cells))
            elif section == "tally":
                # 复用生成器的 F 卡 + En/Tn 段（与完整生成一致）
                from generator.inp_generator import _generate_tallies, _generate_en_cards, _generate_tn_cards
                text = "\n".join(_generate_tallies(deck.tally) + _generate_en_cards(deck.tally) + _generate_tn_cards(deck.tally))
            else:
                raise ValueError(f"不支持的 section: {section}")
            self._ok({"text": text})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── 片段互转：文本 → 表单 ──
    def _handle_text_to_section(self):
        """把某模块的 INP 文本解析回表单数据（供切回表单时回填）。

        入参: {section: "materials"|"cells"|"tally", text}
        返回: {data: 该模块的结构化数据}
          materials → {materials: [...]}
          cells     → {cells: [...]}
          tally     → {tallies: [...]}
        """
        try:
            data = self._read_body()
            section = data.get("section", "")
            text = data.get("text", "")
            if not text.strip():
                raise ValueError("文本为空")
            # 包最小假 INP 壳：标题 + 空栅元 + 空曲面 + 数据卡段 = 该模块文本
            # cells 的文本必须放入【栅元段】（否则落入数据段被 other_cards 兜底，用户栅元字段全丢）
            if section == "cells":
                shell = f"{text}\n\nC  surf\n1 pz -1e9\n\nMODE N\n"
            else:
                shell = f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"
            deck, _warnings = parse_inp_text(shell)
            d = _deck_to_frontend_dict(deck)
            if section == "materials":
                self._ok({"data": {"materials": d.get("materials", [])}})
            elif section == "cells":
                self._ok({"data": {"cells": d.get("cells", [])}})
            elif section == "tally":
                self._ok({"data": {"tallies": d.get("tallies", [])}})
            else:
                raise ValueError(f"不支持的 section: {section}")
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── MESHTAL：自动探测 ──
    def _handle_meshtal_detect(self):
        """扫描 output_dir 找 meshtal* / MSHT* 文件（大小写不敏感，按 mtime 降序）。"""
        import datetime, re as _re
        try:
            data = self._read_body()
            output_dir = data.get("outputDir", "D:/MCNP/new/claude")
            if not isinstance(output_dir, str) or not output_dir.strip():
                self._err("输出目录非法", hint="请确认输出目录路径正确")
                return
            files = []
            if os.path.isdir(output_dir):
                entries = []
                try:
                    with os.scandir(output_dir) as it:
                        for e in it:
                            if e.is_file() and _re.match(r'(?i)^(meshtal|MSHT)', e.name):
                                st = e.stat()
                                entries.append((st.st_mtime, {
                                    "path": e.path, "name": e.name, "size": st.st_size,
                                    "mtime": datetime.datetime.fromtimestamp(
                                        st.st_mtime, tz=datetime.timezone.utc
                                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                }))
                except OSError:
                    entries = []
                entries.sort(key=lambda x: x[0], reverse=True)
                files = [x[1] for x in entries]
            self._ok({"files": files, "outputDir": output_dir})
        except Exception as e:
            self._err(str(e), hint="扫描 meshtal 文件失败，请确认输出目录存在")

    # ── MESHTAL：解析（子进程 worker，元数据 + grid_bounds + match）──
    def _handle_meshtal_parse(self):
        """子进程 worker 解析 meshtal → 元数据；比对 deck↔meshtal（A1.2）。"""
        try:
            import subprocess
            data = self._read_body()
            path = data.get("path", "")
            if not path or not os.path.isfile(path):
                self._err("不是有效的 meshtal 文件",
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return
            worker = _meshtal_worker_cmd()
            proc = subprocess.run(
                worker,
                input=json.dumps({"mode": "parse", "path": path}),
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                self._err(f"meshtal 解析失败: {proc.stderr[-300:]}",
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return
            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                self._err(f"解析 worker 输出失败: {e}",
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return
            if result.get("status") != "ok":
                self._err(result.get("message", "meshtal 解析失败"),
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return

            # A1.2：deck↔meshtal 比对（纯函数，不阻塞）；两者皆缺 → match:null
            from meshtal.deck_match import AABB, check_match
            grid_box = None
            gb = result.get("grid_bounds")
            if gb:
                grid_box = AABB(tuple(gb["min"]), tuple(gb["max"]))
            model_box = None
            mb = data.get("modelBox")
            if mb is not None and mb.get("min") is not None and mb.get("max") is not None:
                model_box = AABB(tuple(mb["min"]), tuple(mb["max"]))
            else:
                # A1.2 契约缺口修复（2026-08-15）：前端只发 cells/surfaces/tr_cards，
                # 由 handler 推算模型盒（契约「或由 handler 算」分支此前未实现 → match 恒 null）
                mb2 = _model_box_from_cells_surfaces(data)
                if mb2 is not None:
                    model_box = AABB(tuple(mb2["min"]), tuple(mb2["max"]))
            match = None
            if grid_box is not None and model_box is not None:
                rep = check_match(grid_box, model_box)
                match = {
                    "matched": rep.matched,
                    "overlapFraction": rep.overlap_fraction,
                    "centerOffsetFrac": rep.center_offset_frac,
                    "reason": rep.reason,
                    "message": rep.message,
                }

            import datetime
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            self._ok({
                "file": {"path": path, "size": size,
                         "mtime": datetime.datetime.fromtimestamp(
                             mtime, tz=datetime.timezone.utc
                         ).strftime("%Y-%m-%dT%H:%M:%SZ")},
                "header": {"code": result.get("code"), "version": result.get("version"),
                           "histories": result.get("histories")},
                "grid_bounds": gb,
                "match": match,
                "tallies": result.get("tallies", []),
                "warnings": result.get("warnings", []),
            })
        except Exception as e:
            self._err(str(e), hint="解析 meshtal 文件失败，请确认是 MCNP 生成的 meshtal 文件")

    # ── MESHTAL：标量帧纹理（子进程 worker，Uint8 base64）──
    def _handle_meshtal_texture(self):
        """子进程 worker 取 (energy,time) 帧 → 降采样标量帧 Uint8 base64（非 RGBA）。"""
        try:
            import subprocess
            data = self._read_body()
            path = data.get("path", "")
            if not path or not os.path.isfile(path):
                self._err("不是有效的 meshtal 文件",
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return
            worker = _meshtal_worker_cmd()
            proc = subprocess.run(
                worker,
                input=json.dumps({
                    "mode": "texture", "path": path,
                    "tallyNumber": data.get("tallyNumber"),
                    "energyBin": data.get("energyBin", 0),
                    "timeBin": data.get("timeBin", 0),
                    "resolution": data.get("resolution", 128),
                    "normalize": data.get("normalize", "adaptive"),
                }),
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                self._err(f"meshtal 纹理提取失败: {proc.stderr[-300:]}",
                          hint="请重新选择计数与能量/时间范围")
                return
            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                self._err(f"解析 worker 输出失败: {e}",
                          hint="请重新选择计数与能量/时间范围")
                return
            if result.get("status") != "ok":
                self._err(result.get("message", "meshtal 纹理提取失败"),
                          hint="请重新选择计数与能量/时间范围")
                return
            self._ok({"frame": result["frame"]})
        except Exception as e:
            self._err(str(e), hint="提取体积纹理失败，请重新选择计数与能量/时间范围")

    # ── PTRAC：粒子径迹解析（子进程 worker，不阻塞 5001）──
    # ── PTRAC：自动探测（照 meshtal-detect，输出目录扫 ptrac 径迹文件）──
    def _handle_ptrac_detect(self):
        """扫描 output_dir 找 PTRAC 径迹文件（大小写不敏感，按 mtime 降序）。"""
        import datetime, re as _re
        try:
            data = self._read_body()
            output_dir = data.get("outputDir", "D:/MCNP/new/claude")
            if not isinstance(output_dir, str) or not output_dir.strip():
                self._err("输出目录非法", hint="请确认输出目录路径正确")
                return
            files = []
            if os.path.isdir(output_dir):
                entries = []
                try:
                    with os.scandir(output_dir) as it:
                        for e in it:
                            # MCNP 默认径迹文件名为 ptrac（无扩展名），也兼容 ptrac.* 重命名
                            if e.is_file() and _re.match(r'(?i)^ptrac(\..*)?$', e.name):
                                st = e.stat()
                                entries.append((st.st_mtime, {
                                    "path": e.path, "name": e.name, "size": st.st_size,
                                    "mtime": datetime.datetime.fromtimestamp(
                                        st.st_mtime, tz=datetime.timezone.utc
                                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                }))
                except OSError:
                    entries = []
                entries.sort(key=lambda x: x[0], reverse=True)
                files = [x[1] for x in entries]
            self._ok({"files": files, "outputDir": output_dir})
        except Exception as e:
            self._err(str(e), hint="扫描 PTRAC 文件失败，请确认输出目录存在")

    def _handle_ptrac_parse(self):
        """子进程 worker 解析 PTRAC → header/tracks/worldBox/stats/truncated（契约 v2 §3）。"""
        try:
            import subprocess
            data = self._read_body()
            path = data.get("path", "")
            if not path or not os.path.isfile(path):
                self._err("不是有效的 PTRAC 文件",
                          hint="请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")
                return
            worker = _ptrac_worker_cmd()
            proc = subprocess.run(
                worker,
                input=json.dumps({
                    "mode": "parse", "path": path,
                    "maxTracks": data.get("maxTracks", 500),
                    "maxPoints": data.get("maxPoints", 200000),
                }),
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                self._err(f"PTRAC 解析失败: {proc.stderr[-300:]}",
                          hint="请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")
                return
            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                self._err(f"解析 worker 输出失败: {e}",
                          hint="请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")
                return
            if result.get("status") != "ok":
                self._err(result.get("message", "PTRAC 解析失败"),
                          hint="请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")
                return
            self._ok({
                "header": result.get("header", {}),
                "tracks": result.get("tracks", []),
                "worldBox": result.get("world_box"),
                "stats": result.get("stats", {}),
                "truncated": result.get("truncated", False),
            })
        except Exception as e:
            self._err(str(e), hint="解析 PTRAC 文件失败，请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")

    # ── 保存 INP 到目录 ──
    def _handle_save_inp(self):
        try:
            data = self._read_body()
            inp_text = data.get("inp", "")
            filename = data.get("filename", "output.inp")
            output_dir = data.get("outputDir", "D:/MCNP/new/claude")
            run_bat = data.get("runBat", "")
            os.makedirs(output_dir, exist_ok=True)
            inp_path = os.path.join(output_dir, filename)
            with open(inp_path, "w", encoding="utf-8") as f:
                f.write(inp_text)
            if run_bat:
                bat_name = filename.rsplit(".", 1)[0] + ".bat"
                bat_path = os.path.join(output_dir, bat_name)
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(run_bat)
            self._ok({"path": inp_path})
            _open_in_explorer(output_dir)
        except Exception as e:
            self._err(str(e))

    # ── 选择目录 ──
    def _handle_choose_dir(self):
        """弹出系统原生目录选择窗口，返回所选路径（取消返回 cancelled）"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            data = self._read_body()
            initial = data.get("initialDir", "") or os.getcwd()
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                path = filedialog.askdirectory(title="选择输出目录", initialdir=initial)
            finally:
                root.destroy()
            self._ok({"path": path or "", "cancelled": not path})
        except Exception as e:
            self._err(f"无法打开系统目录选择器: {e}")

    # ── 选择文件（原生打开对话框，返回路径+内容）──
    def _handle_choose_file(self):
        """弹出系统原生文件选择窗口，返回所选文件路径和内容（取消返回 cancelled）"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                path = filedialog.askopenfilename(
                    title="选择 MCNP INP 文件",
                    filetypes=[("MCNP 输入卡", "*.inp *.i *.txt"), ("所有文件", "*.*")],
                )
            finally:
                root.destroy()
            if not path:
                self._ok({"path": "", "cancelled": True})
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self._ok({"path": path, "content": content, "cancelled": False})
        except Exception as e:
            self._err(f"无法打开系统文件选择器: {e}")

    # ── 运行 MCNP ──
    def _handle_run_mcnp(self):
        try:
            import subprocess, threading
            data = self._read_body()
            inp_text = data.get("inp", "")
            filename = data.get("filename", "output.inp")
            output_dir = data.get("outputDir", "D:/MCNP/new/claude")
            exe = data.get("mcnpExe", "") or ""
            if not inp_text.strip():
                raise ValueError("INP 内容为空")
            os.makedirs(output_dir, exist_ok=True)
            # 定位 MCNP 可执行文件（前端传的 > 自动检测）
            if not exe or not os.path.isfile(exe):
                exe = _find_mcnp_exe()
            if not exe or not os.path.isfile(exe):
                raise FileNotFoundError("未找到 mcnp6.exe，请检查 MCNP 安装或手动配置")
            # 保存 inp 和 run.bat（临时，跑完自动删除）
            inp_path = os.path.join(output_dir, filename)
            base = filename.rsplit(".", 1)[0]
            bat_path = os.path.join(output_dir, base + ".bat")
            saved_mtime = os.path.getmtime(inp_path) if os.path.exists(inp_path) else None
            with open(inp_path, "w", encoding="utf-8") as f:
                f.write(inp_text)
            # 显卡选择：本机 GPU0 是核显，GPU1 是独显（CUDA 只认 NVIDIA）。
            # CUDA_VISIBLE_DEVICES=1 让 MCNP 跳过核显直接用独显加速。
            gpu_device = os.environ.get("MCNP_GPU_DEVICE", "1")
            run_bat = (f"@echo off\r\nset CUDA_VISIBLE_DEVICES={gpu_device}\r\n"
                       f"call \"{exe}\" inp={filename} outp={base}.o\r\npause\r\n")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(run_bat)
            # 后台线程：在新控制台窗口里跑 run.bat（窗口可见，用户能看到 MCNP 在跑，
            # pause 让跑完的窗口停住）；MCNP 结束后自动删除临时 inp + bat。
            def _run_and_cleanup():
                try:
                    proc = subprocess.Popen(
                        ["cmd.exe", "/c", bat_path], cwd=output_dir,
                        creationflags=subprocess.CREATE_NEW_CONSOLE)
                    proc.wait()
                except Exception:
                    pass
                finally:
                    for p in (inp_path, bat_path):
                        try:
                            # 仅当文件没被新一轮运行改写过才删除（防竞态）
                            if not os.path.exists(p):
                                continue
                            if p == inp_path and saved_mtime is not None:
                                if abs(os.path.getmtime(p) - saved_mtime) > 1.0:
                                    continue
                            os.remove(p)
                        except OSError:
                            pass
            threading.Thread(target=_run_and_cleanup, daemon=True).start()
            self._ok({"status": "started", "path": inp_path, "exe": exe})
            _open_in_explorer(output_dir)
        except Exception as e:
            self._err(str(e))

    # ── xsdir 状态 ──
    def _handle_xsdir_check(self):
        try:
            if not xsdir_db.loaded:
                # Priority 1: environment variables (XSDIR, DATAPATH)
                env_path = ""
                for _var in ("XSDIR", "xsdir"):
                    _val = os.environ.get(_var, "")
                    if _val and os.path.isfile(_val):
                        env_path = _val; break
                if not env_path:
                    _dp = os.environ.get("DATAPATH", "")
                    if _dp:
                        _cand = os.path.join(_dp, "xsdir")
                        if os.path.isfile(_cand): env_path = _cand
                if env_path:
                    xsdir_db.load(env_path)
                else:
                    # Priority 2: hardcoded common paths
                    found = xsdir_db.find_xsdir()
                    if found:
                        xsdir_db.load(found)
            count = xsdir_db.count() if hasattr(xsdir_db, 'count') else 0
            self._ok({"loaded": xsdir_db.loaded, "count": count, "path": getattr(xsdir_db, 'path', None)})
        except Exception as e:
            self._ok({"loaded": False, "count": 0, "error": str(e)})

    # ── STEP 导入 ──
    def _handle_import_step(self):
        try:
            import os, tempfile
            from step_importer import (StepImporter, run_step_converter,
                                       MCNPOutputParser, geometry_deck_response,
                                       StepConversionError)
            data = self._read_body()
            step_data = data.get("data", "")
            step_path = data.get("path", "")
            settings = data.get("settings", {})
            material = settings.get("materialName", "MAT")
            density_val = settings.get("density", "-1.0")
            try:
                density = float(density_val)
            except Exception:
                density = -1.0

            # STEP 数据以文本传入时落盘为临时文件
            if step_data:
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".step", delete=False, mode="w", encoding="utf-8")
                tmp.write(step_data)
                tmp.close()
                step_path = tmp.name
            if not step_path or not os.path.isfile(step_path):
                self._ok({"status": "error", "message": "STEP 文件不存在"})
                return

            # 只走 GEOUNED 通道；失败抛 StepConversionError，真实原因回传给前端
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "error", "message": "需要 FreeCAD 才能导入 STEP"})
                return

            result_path = run_step_converter(
                "geouned", step_path, material, density, settings, freecad_bin)
            deck = MCNPOutputParser.parse(result_path, post_settings=settings)
            if not deck:
                self._ok({"status": "error", "message": "GEOUNED 输出无法解析"})
                return

            self._ok({"status": "ok", "deck": geometry_deck_response(
                deck.surfaces, deck.tr_cards,
                [{"number": c.number, "material": str(c.material),
                  "density": str(c.density) if c.density else "",
                  "surface_expr": c.surface_expr,
                  "comment": c.comment or ""}
                 for c in (deck.cells or [])])})
        except StepConversionError as e:
            self._ok({"status": "error", "message": str(e)})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── 生成 STEP（3D 预览用）──
    def _handle_generate_step(self):
        try:
            data = self._read_body()
            surfaces = data.get("surfaces", "")
            import tempfile, os, json
            # Import generate_step
            step_path = os.path.join(tempfile.gettempdir(), "mcnp_geometry.step")
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
                from generate_step import generate_step
                step_path = generate_step(surfaces.split("\\n") if surfaces else [])
            except ImportError:
                # Fallback: write surfaces as comments in STEP
                with open(step_path, "w") as f:
                    f.write('ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(());\n')
                    f.write('FILE_NAME("mcnp_geometry.step");\n')
                    f.write('FILE_SCHEMA(("CONFIG_CONTROL_DESIGN"));\nENDSEC;\nDATA;\n')
                    for line in surfaces.split("\n")[:100]:
                        f.write(f'# COMMENT: {line}\n')
                    f.write('ENDSEC;\nEND-ISO-10303-21;\n')
            self._ok({"step_file": step_path, "message": "STEP 文件已生成"})
        except Exception as e:
            self._err(str(e))

    # ── 导出 STEP（通过 FreeCAD CSG 生成真实几何）──
    def _handle_export_step(self):
        try:
            import os, base64
            from step_importer import StepImporter
            from freecad_preview import FreeCADEngine

            data = self._read_body()
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", [])
            tr_text = data.get("tr_cards", "")

            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "error", "message": "需要 FreeCAD"})
                return

            # 解析曲面（共享 parse_surfaces）
            surfs = parse_surfaces(surf_text)

            # 解析栅元（共享 build_cells_data；导出需几何可解析，剔除 ast=None；
            # 真空栅元不导出为实体——它们只参与 #n 补集解析，不进入 STEP）
            cells_data = [c for c in build_cells_data(cell_list, include_void=False)
                          if c["ast"] is not None]

            if not surfs or not cells_data:
                self._ok({"status": "error", "message": "没有可导出的栅元"})
                return

            # 解析 TR 卡（共享 parse_tr_cards）
            tr_cards = parse_tr_cards(tr_text)

            # 与 3D 预览同一条路线：build_geometry(fmt="step", single_file=True)
            # bound 用与预览一致的默认值(500)，避免巨大空盒导致几何不一致
            engine = FreeCADEngine(freecad_bin)
            result_map = engine.build_geometry(surfs, cells_data, tr_cards,
                                               bound=500, fmt="step", single_file=True)
            content = b''
            if result_map:
                step_file = list(result_map.values())[0]
                if os.path.isfile(step_file) and os.path.getsize(step_file) > 500:
                    with open(step_file, "rb") as f: content = f.read()
            engine.cleanup()
            if not content:
                self._ok({"status": "error", "message": "STEP 生成失败"})
                return
            b64 = base64.b64encode(content).decode()
            self._ok({"file": "mcnp_export.step", "data": b64, "message": "STEP 文件已导出"})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── MCNP 检测 ──
    def _handle_preview_3d(self):
        """3D 预览：解析曲面/栅元/TR → FreeCAD CSG → STL（同 deck 指纹缓存命中免 FreeCAD）"""
        global _STL_SESSION
        try:
            import tempfile, re, base64, shutil
            data = self._read_body()
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", [])
            tr_text = data.get("tr_cards", "")

            # 0. 指纹缓存：同 deck 命中免 FreeCAD 子进程（二次打开 ≤1s）
            fp = _PREVIEW_CACHE.fingerprint(surf_text, cell_list, tr_text)
            cached = _PREVIEW_CACHE.get(fp)
            if cached is not None:
                prev_dir = _STL_SESSION.get("dir")
                if prev_dir and prev_dir != cached["dir"]:
                    _clear_stl_session()  # 清上一会话（与命中缓存目录不同时）
                # 缓存目录作为本会话 STL 源（供 serve-file/截面复用）
                _STL_SESSION = {"dir": cached["dir"], "cells": cached["cells"]}
                # deck 快照（GQ/SQ 解析截面用）：缓存不存 deck，从请求重建
                try:
                    surfs_c = parse_surfaces(surf_text)
                    cells_c = build_cells_data(cell_list, include_void=False)
                    if surfs_c and cells_c:
                        _STL_SESSION["deck"] = _deck_snapshot(
                            surfs_c, cells_c, parse_tr_cards(tr_text))
                except Exception:
                    pass
                stl_files = {}
                stl_data = {}
                for num, info in cached["cells"].items():
                    p = info.get("path")
                    if p and os.path.isfile(p):
                        with open(p, "rb") as _f:
                            stl_data[str(num)] = base64.b64encode(_f.read()).decode()
                        stl_files[str(num)] = p
                self._ok({"stl_files": stl_files, "stl_data": stl_data,
                          "freecad": cached.get("freecad"), "count": len(stl_data)})
                return

            # 1. 检测 FreeCAD
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
            from step_importer import StepImporter
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"stl_files": {}, "message": "未检测到 FreeCAD，请安装后重试"})
                return

            # 2. 解析曲面（共享 parse_surfaces）
            surfs = parse_surfaces(surf_text)
            if not surfs:
                self._ok({"stl_files": {}, "message": "未解析到有效曲面"})
                return

            # 3. 解析 TR 卡（共享 parse_tr_cards）
            tr_cards = parse_tr_cards(tr_text)

            # 4. 构建栅元（共享 build_cells_data；ast 解析失败的不渲染但保留）
            # 真空栅元参与 #n 补集解析，但不生成 STL（透明不可见，且巨型边界
            # void 的 STL 会把前端相机拉远导致模型缩成针尖）。include_void=False
            # 时真空仍在 entries 映射里供 #n 解析，只是不输出。
            cells_data = build_cells_data(cell_list, include_void=False)
            if not cells_data:
                self._ok({"stl_files": {}, "message": "没有可预览的栅元（非 void）"})
                return

            # 5. FreeCAD CSG → STL
            from freecad_preview import FreeCADEngine
            engine = FreeCADEngine(freecad_bin)
            result = engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl")

            # STL 复制到会话专用目录（engine 析构会删它自己的临时目录，必须复制走）
            _clear_stl_session()  # 覆盖上一轮预览
            session_dir = tempfile.mkdtemp(prefix="mcnp_stl_session_")
            _STL_SESSION = {"dir": session_dir, "cells": {},
                            "deck": _deck_snapshot(surfs, cells_data, tr_cards)}
            # 会话路径 → base64（先读源文件，engine.cleanup() 之前）
            stl_files = {}
            stl_data = {}
            for cd in cells_data:
                num = cd.get("number")
                if num in result and os.path.isfile(result[num]):
                    src = result[num]
                    dst = os.path.join(session_dir, f"cell_{num}.stl")
                    try:
                        shutil.copy2(src, dst)
                        with open(src, "rb") as _f:
                            stl_data[str(num)] = base64.b64encode(_f.read()).decode()
                    except OSError:
                        continue
                    stl_files[str(num)] = dst
                    _STL_SESSION["cells"][num] = {
                        "material": cd.get("material", "0"),
                        "path": dst,
                    }
            engine.cleanup()  # 引擎临时目录可删，会话目录已独立
            # 存入指纹缓存：会话 STL 拷入缓存自有目录，clear-stl 删除会话目录不影响缓存
            _PREVIEW_CACHE.put(fp, {"dir": session_dir, "cells": _STL_SESSION["cells"], "freecad": freecad_bin})
            self._ok({"stl_files": stl_files, "stl_data": stl_data, "freecad": freecad_bin, "count": len(stl_data)})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _handle_serve_file(self):
        """服务 STL 文件供前端加载"""
        import os, urllib.parse
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        file_path = params.get("path", [None])[0]
        if not file_path or not os.path.exists(file_path):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(file_path)))
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def _handle_cross_section(self):
        """平面截面：从 3D 预览保留的 STL 会话切（numpy），不再调 FreeCAD CSG。

        前端传 cellNums（勾选且非真空的栅元号）+ plane；真空/未勾选栅元的
        STL 不参与。无会话时提示先做 3D 预览。
        """
        try:
            _app_dir = os.path.join(os.path.dirname(__file__), "..", "..", "app")
            if _app_dir not in sys.path: sys.path.insert(0, _app_dir)
            from stl_cross_section import cross_section_from_stl
            data = self._read_body()
            cell_nums = data.get("cellNums") or []
            plane = data.get("plane") or {"A": 0, "B": 0, "C": 1, "D": 0}
            A = float(plane.get("A", 0)); B = float(plane.get("B", 0))
            C = float(plane.get("C", 0)); D = float(plane.get("D", 0))

            if not _STL_SESSION.get("dir") or not _STL_SESSION.get("cells"):
                self._ok({"slices": [], "message": "请先生成 3D 预览（STL 会话为空）"})
                return

            # GQ/SQ 栅元走解析切片（精确轮廓，不依赖 STL 网格分辨率）；
            # deck 快照由 preview-3d 写入会话，缺失时回退 STL 切。
            deck = _STL_SESSION.get("deck") or {}
            deck_surfs = {}
            for s in deck.get("surfaces", []):
                try:
                    deck_surfs[int(s["number"])] = s
                except (KeyError, TypeError, ValueError):
                    continue
            deck_cells = {}
            for c in deck.get("cells", []):
                try:
                    deck_cells[int(c["number"])] = c
                except (KeyError, TypeError, ValueError):
                    continue
            deck_tr = deck.get("tr_cards", {})

            slices = []
            for num in cell_nums:
                num = int(num)
                info = _STL_SESSION["cells"].get(num)
                if not info:
                    continue
                material = info.get("material", "0")
                if str(material).split()[0] == "0":
                    continue  # 真空 STL 不参与截面

                ast = (deck_cells.get(num) or {}).get("ast")
                use_analytic = False
                if ast:
                    try:
                        from voxel_csg import _ast_surf_nums
                        use_analytic = any(
                            str(deck_surfs.get(n, {}).get("type", "")).upper()
                            in ("GQ", "SQ")
                            for n in _ast_surf_nums(ast)
                        )
                    except Exception:
                        use_analytic = False

                polys = []
                if use_analytic:
                    try:
                        from analytic_slice import analytic_cross_section
                        polys = analytic_cross_section(
                            ast, deck_surfs, deck_tr,
                            {"A": A, "B": B, "C": C, "D": D}, bound=500.0)
                    except Exception:
                        polys = []
                if not polys:
                    # 非 GQ/SQ 或解析失败：回退 STL 切（原行为）
                    path = info.get("path")
                    if path and os.path.isfile(path):
                        polys = cross_section_from_stl(path, A, B, C, D)
                if polys:
                    slices.append({"number": num, "material": material, "polygons": polys})
            self._ok({"slices": slices, "count": len(slices)})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _handle_clear_stl(self):
        """关 3D 预览窗口 / 主界面清空时调用：删除 STL 会话目录"""
        try:
            _clear_stl_session()
            self._ok({"status": "ok"})
        except Exception as e:
            self._err(str(e))

    def _handle_mcnp_detect(self):
        try:
            exe = _find_mcnp_exe()
            label = "MCNP6"
            if exe and "5" in os.path.basename(exe).lower(): label = "MCNP5"
            self._ok({"found": bool(exe), "exe": exe, "label": label if exe else "MCNP?"})
        except Exception as e:
            self._ok({"found": False, "exe": "", "label": "MCNP?", "error": str(e)})

    # ── FreeCAD 检测（统一走 freecad_locator seam）──

    def _handle_set_freecad_path(self):
        """保存用户手动指定的 FreeCAD 路径（校验存在且为 freecad.exe/freecadcmd.exe）"""
        try:
            data = self._read_body() or {}
            p = (data.get("path") or "").strip().strip('"')
            if not p or not os.path.isfile(p):
                self._ok({"status": "error", "message": "文件不存在"})
                return
            if os.path.basename(p).lower() not in ("freecad.exe", "freecadcmd.exe"):
                self._ok({"status": "error", "message": "请选择 FreeCAD.exe 或 FreeCADCmd.exe"})
                return
            from freecad_locator import save
            save(p)  # config.json + QSettings 双写
            self._ok({"status": "ok", "path": p})
        except Exception as e:
            self._ok({"status": "error", "message": str(e)})

    def _handle_choose_freecad_path(self):
        """弹出系统原生文件选择窗口选 FreeCAD.exe（取消返回 cancelled）"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                path = filedialog.askopenfilename(
                    title="选择 FreeCAD.exe",
                    filetypes=[("FreeCAD", "*.exe"), ("所有文件", "*.*")],
                )
            finally:
                root.destroy()
            if not path:
                self._ok({"path": "", "cancelled": True})
                return
            self._ok({"path": path, "cancelled": False})
        except Exception as e:
            self._ok({"path": "", "cancelled": True, "error": str(e)})

    def _handle_check_freecad(self):
        """重新定位 FreeCAD（清缓存后完整搜索），返回 {found, path}"""
        try:
            from freecad_locator import reset_cache, locate
            reset_cache()
            p = locate()
            self._ok({"found": bool(p), "path": p or ""})
        except Exception as e:
            self._ok({"found": False, "path": "", "error": str(e)})

    # ── INP 预校验 ──
    def _handle_validate_inp(self):
        try:
            data = self._read_body()
            from generator.parsers.validator import validate_inp_text
            errors = validate_inp_text(data.get("inp", ""))
            self._ok({"valid": len(errors) == 0, "errors": errors})
        except Exception as e:
            self._err(str(e))

    # ── ZAID 校验 ──
    def _handle_validate_zaid(self):
        from urllib.parse import parse_qs
        qs = parse_qs(urlparse(self.path).query)
        zaid = qs.get("zaid", [""])[0].strip()
        try:
            if not xsdir_db.loaded:
                env_path = os.environ.get("XSDIR", "") or os.environ.get("DATAPATH", "")
                if env_path and os.path.isfile(env_path):
                    xsdir_db.load(env_path)
                elif os.environ.get("DATAPATH", ""):
                    cand = os.path.join(os.environ["DATAPATH"], "xsdir")
                    if os.path.isfile(cand): xsdir_db.load(cand)
                else:
                    found = xsdir_db.find_xsdir()
                    if found: xsdir_db.load(found)
            in_db = xsdir_db.has_zaid(zaid) if xsdir_db.loaded else None
            self._ok({"zaid": zaid, "in_db": in_db, "loaded": xsdir_db.loaded})
        except Exception as e:
            self._err(str(e))

    # ── OUTP 解析 ──
    def _handle_parse_keff(self):
        """主动解析 mctal 的 keff 收敛序列（目录自动找 mctal* 文件）。"""
        try:
            import glob
            data = self._read_body() or {}
            path = str(data.get("path", "")).strip()
            if not path:
                self._err("缺少 mctal 文件路径或运行目录")
                return
            if os.path.isdir(path):
                candidates = sorted(glob.glob(os.path.join(path, "mctal*")))
                if not candidates:
                    self._err(f"目录中未找到 mctal 文件：{path}")
                    return
                mctal_path = candidates[0]
            else:
                mctal_path = path
            if not os.path.isfile(mctal_path):
                self._err(f"mctal 文件不存在：{mctal_path}")
                return
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
            from mctal_parser import parse_mctal
            with open(mctal_path, "r", encoding="utf-8", errors="replace") as f:
                result = parse_mctal(f.read())
            keff = result.get("keff") or {}
            if not keff.get("mean"):
                self._err(f"未在 mctal 中解析到 keff 收敛序列：{mctal_path}")
                return
            self._ok({
                "status": "ok",
                "path": mctal_path,
                "keff": {
                    "cycles": keff.get("cycles", []),
                    "mean": keff.get("mean", []),
                    "std": keff.get("std", []),
                    "combined": keff.get("combined"),
                },
            })
        except Exception as e:
            self._err(str(e), hint="keff 解析失败，请确认 mctal 文件有效")

    def _handle_parse_outp(self):
        try:
            data = self._read_body()
            text = data.get("outp", "")

            # 优先用内置 pymcnp（正确入口：Outp.from_mcnp(text).to_dataframe()）。
            # 注意：pymcnp.Outp(...) 是构造函数（header, blocks），不是解析入口；
            # 旧代码误用导致该接口恒报错。pymcnp 只覆盖 MCNP6.2 系布局。
            try:
                import pymcnp

                result = pymcnp.Outp.from_mcnp(text)
                df_map = result.to_dataframe()
                if df_map:
                    tallies = {}
                    nps = None
                    for tnum, df in df_map.items():
                        rows = []
                        flux_sum = 0.0
                        for _, row in df.iterrows():
                            try:
                                flux_sum += float(row.get("counts"))
                            except (TypeError, ValueError):
                                pass
                            rows.append({
                                "energy": _fmt_num(row.get("bins")),
                                "flux": _fmt_num(row.get("counts")),
                                "error": _fmt_num(row.get("errors")),
                            })
                        nps = int(df["nps"].iloc[0]) if len(df) else None
                        ttype = str(df["type"].iloc[0]) if len(df) else ""
                        tm = re.match(r"^\s*(\d+)", ttype)
                        tallies[str(tnum)] = {
                            "type": int(tm.group(1)) if tm else 0,
                            "rows": rows,
                            "total": {
                                "energy": "total",
                                "flux": "" if not rows else f"{flux_sum:.6e}",
                                "error": "",
                            },
                        }
                    self._ok({"nps": nps or 0, "tallies": tallies, "warnings": [], "parser": "pymcnp"})
                    return
            except Exception:
                pass  # pymcnp 缺失或布局不兼容 → 走自研容错解析

            # 兜底：格式容错解析（MCNP6.1 紧凑布局等 pymcnp 未覆盖格式）
            from outp_parser import parse_outp

            tallies, nps, warnings = parse_outp(text)
            self._ok({"nps": nps or 0, "tallies": tallies, "warnings": warnings, "parser": "builtin"})
        except Exception as e:
            self._err(str(e))

    # ── xsdir 搜索 ──
    def _handle_xsdir_search(self):
        from urllib.parse import parse_qs
        qs = parse_qs(urlparse(self.path).query)
        q = qs.get("q", [""])[0].strip()
        try:
            if not xsdir_db.loaded:
                self._ok({"loaded": False, "results": []})
                return
            results = []
            q_lower = q.lower()
            for zaid in xsdir_db.zaids:
                if q_lower in zaid.lower():
                    results.append({"zaid": zaid})
                    if len(results) >= 50: break
            if not results:
                from xsdir_db import SYMBOL_TO_Z
                z = SYMBOL_TO_Z.get(q.capitalize())
                if z:
                    for zaid in xsdir_db.zaids:
                        if zaid.startswith(str(z).zfill(3)) or zaid.startswith(str(z)):
                            results.append({"zaid": zaid})
                            if len(results) >= 50: break
            self._ok({"loaded": True, "results": results})
        except Exception as e:
            self._ok({"loaded": False, "results": [], "error": str(e)})

    def log_message(self, fmt, *args):
        if args:
            print(f"[API] {' '.join(str(a) for a in args)}")
        else:
            print(f"[API] {fmt}")


def main():
    server = HTTPServer(("0.0.0.0", PORT), MCNPHandler)
    print(f"[API] MCNP API 服务启动 → http://localhost:{PORT}/api/generate")
    print(f"   Python 后端路径: {APP_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.server_close()


if __name__ == "__main__":
    main()
