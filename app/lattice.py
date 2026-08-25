"""
格阵 FILL 深度模块：解析、序列化、生成。
Deep module for MCNP lattice FILL cards.

覆盖三种 FILL 形态（CellData.fill 保留 FILL= 首行值；fill_grid 承载续行数据）：
  - 单宇宙填充：FILL=5           → fill="5"，fill_grid 空（走普通路径）
  - 翻译单填充：FILL=5 (dx dy dz) → fill="5"，fill_grid.kind="translated"
  - 格阵填充：  FILL=0:16 0:16 0:0 + 条目 → fill 范围串，fill_grid.kind="lattice"

格阵条目支持 MCNP 真实语法：
  - 裸 universe 号：1
  - 偏移条目：1 (9 0 9)（universe 在格位内再平移）
  - nR 重复：1 17r（元素级：把前一个条目再重复 n 次）

生成遵循 MCNP 规范：FILL= 首行 + 5 空格续行（每行 ≤80 列，不加 &）。

本模块只依赖 stdlib（dataclasses/re/json/typing），供解析器、生成器、
3D 展开与前端 TS 镜像（gui/src/utils/lattice.ts）消费。
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field, asdict


_RANGE_RE = re.compile(r'^[+-]?\d+\s*:\s*[+-]?\d+$')
_REPEAT_RE = re.compile(r'^(\d+)\s*[rR]$')
_INT_RE = re.compile(r'^[+-]?\d+$')

# 展开条目数上限（QA：极端 nR / 超大范围补 0 防内存爆炸；raw 兜底保留原始
# 简写，round-trip 字节不受截断影响）
MAX_EXPANDED_ENTRIES = 1_000_000


# ── 模型 ────────────────────────────────────────────────

@dataclass
class FillEntry:
    """单个格位条目：universe 号 + 可选 (dx dy dz) 偏移。"""
    u: str = ""
    dx: str = ""
    dy: str = ""
    dz: str = ""


@dataclass
class FillGrid:
    """格阵 FILL 卡结构（深模块；CellData.fill_grid 存其 to_json()）。"""
    lat: str = ""            # "1" | "2" | ""（非格阵时空）
    kind: str = "lattice"    # "lattice" | "translated"
    range_: list = field(default_factory=list)   # 范围 token，如 ["0:16","0:16","0:0"]
    dims: list = field(default_factory=list)     # 每轴格数，如 [17,17,1]
    cells: list = field(default_factory=list)    # list[FillEntry]，行主序（i 最快）
    raw: str = ""            # FILL= 之后的原始 token 流（round-trip 兜底 / 诊断）

    def to_json(self) -> str:
        return json.dumps({
            "lat": self.lat,
            "kind": self.kind,
            "range": self.range_,
            "dims": self.dims,
            "cells": [asdict(c) for c in self.cells],
            "raw": self.raw,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "FillGrid | None":
        if not s:
            return None
        try:
            d = json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(d, dict):
            return None
        cells = []
        for c in d.get("cells", []):
            if isinstance(c, dict):
                cells.append(FillEntry(
                    u=str(c.get("u", "")),
                    dx=str(c.get("dx", "")),
                    dy=str(c.get("dy", "")),
                    dz=str(c.get("dz", "")),
                ))
        return cls(
            lat=str(d.get("lat", "")),
            kind=str(d.get("kind", "lattice")),
            range_=[str(r) for r in d.get("range", [])],
            dims=[int(x) for x in d.get("dims", []) if str(x).lstrip("-").isdigit()],
            cells=cells,
            raw=str(d.get("raw", "")),
        )


# ── 解析 ────────────────────────────────────────────────

def _range_count(spec: str) -> int:
    """'a:b' → b-a+1（符号感知）；解析失败返回 0。"""
    m = re.match(r'^([+-]?\d+)\s*:\s*([+-]?\d+)$', spec)
    if not m:
        return 0
    return int(m.group(2)) - int(m.group(1)) + 1


def _dir_counts_from_range(token: str) -> tuple:
    """方向块数 -N:M 映射：token 'a:b' → (L, R) = (-a, b)；解析失败返回 (0, 0)。

    与 _range_count 的 dims = b-a+1 自洽（dims[axis] = L+R+1）：
      '-8:8' → (8, 8)（居中，dims=17）；'0:16' → (0, 16)（角起，dims=17）。
    expand_positions rect 中心 ((i-(nx-1)/2)·px) 代入 i=0 → -(L+R)/2·px、i=nx-1 → +(L+R)/2·px，
    -N:M 映射下格阵始终以几何中心居中于原点（项2 权威公式）。
    """
    m = re.match(r'^([+-]?\d+)\s*:\s*([+-]?\d+)$', token)
    if not m:
        return 0, 0
    return -int(m.group(1)), int(m.group(2))


def _parse_offset(stream: list[str], i: int) -> tuple[str, str, str, int]:
    """从 i 起解析 '(x y z)' 偏移（token 形如 '(9' '0' '9)' 或 '(9' '0' '9' ')'）。
    返回 (dx, dy, dz, new_i)；new_i 指向 ')' 之后。
    """
    rest = []
    j = i
    while j < len(stream):
        t = stream[j]
        rest.append(t)
        j += 1
        if t.endswith(")"):
            break
    nums = []
    for t in rest:
        tt = t.strip("()")
        if tt:
            nums.append(tt)
    if len(nums) >= 3:
        return nums[0], nums[1], nums[2], j
    return "", "", "", j


def parse_fill_entries(stream: list[str],
                       max_entries: int = MAX_EXPANDED_ENTRIES) -> list[FillEntry]:
    """条目 token 流 → 展开后的 FillEntry 列表（元素级 nR 重复 + (x y z) 偏移）。

    nR = 把前一个条目再重复 n 次（与 core._expand_repeat 的 nR→n+1 语义一致）。

    内存防护：展开结果封顶 max_entries（默认 MAX_EXPANDED_ENTRIES=1_000_000）。
    极端 nR 时截断、不抛异常；raw 在 parse_fill_tokens 中独立保留原始简写，
    round-trip 不受截断影响。
    """
    entries: list[FillEntry] = []
    i = 0
    while i < len(stream) and len(entries) < max_entries:
        tok = stream[i]
        m = _REPEAT_RE.match(tok)
        if m and entries:
            n = int(m.group(1))
            room = max_entries - len(entries)
            if room > 0:
                last = entries[-1]
                entries.extend(FillEntry(u=last.u, dx=last.dx, dy=last.dy, dz=last.dz)
                               for _ in range(min(n, room)))
            i += 1
            continue
        if not _INT_RE.match(tok):
            # 无法识别的 token（畸形卡）→ 原样跳过，raw 兜底保留
            i += 1
            continue
        u = tok
        dx = dy = dz = ""
        i += 1
        if i < len(stream) and stream[i].startswith("("):
            dx, dy, dz, i = _parse_offset(stream, i)
        entries.append(FillEntry(u=u, dx=dx, dy=dy, dz=dz))
    return entries


def parse_fill_tokens(tokens: list[str], lat: str = "") -> "FillGrid | None":
    """FILL= 之后全部 token → FillGrid；单宇宙填充（无格阵结构）返回 None。

    - 前导 1~3 个 'a:b' 范围 token → 格阵填充（kind="lattice"）
    - 首 token 为整数 + 后随 '(x y z)' → 翻译单填充（kind="translated"）
    - 其余 → 单宇宙填充，返回 None（fill 字段直接取首 token）
    """
    if not tokens:
        return None
    raw = " ".join(tokens)

    # 格阵：收集前导范围 token（≤3 个）
    ranges = []
    i = 0
    while i < len(tokens) and i < 3 and _RANGE_RE.match(tokens[i]):
        ranges.append(tokens[i])
        i += 1
    if ranges:
        dims = [_range_count(r) for r in ranges]
        entries = parse_fill_entries(tokens[i:])
        # MCNP 要求条目数 = 范围乘积；防御性截断/补 0（画布按 dims 消费）
        total = 1
        for d in dims:
            total *= d
        if total > 0 and len(entries) > total:
            entries = entries[:total]
        elif total > 0 and len(entries) < total:
            # 补 0 受 MAX_EXPANDED_ENTRIES 封顶（极端超大范围不爆内存；raw 兜底保真）
            room = MAX_EXPANDED_ENTRIES - len(entries)
            if room > 0:
                entries.extend(FillEntry(u="0")
                               for _ in range(min(total - len(entries), room)))
        return FillGrid(lat=lat, kind="lattice", range_=ranges,
                        dims=dims, cells=entries, raw=raw)

    # 翻译单填充：5 (dx dy dz)
    first = tokens[0]
    if _INT_RE.match(first) and len(tokens) >= 2 and tokens[1].startswith("("):
        dx, dy, dz, _ = _parse_offset(tokens, 1)
        return FillGrid(lat=lat, kind="translated",
                        cells=[FillEntry(u=first, dx=dx, dy=dy, dz=dz)], raw=raw)

    # 单宇宙填充
    return None


# ── 生成 ────────────────────────────────────────────────

def _pack_entries(entry_strs: list[str], max_chars: int = 75) -> list[str]:
    """条目字符串贪心打包成 ≤max_chars 的行（5 空格缩进后 ≤80 列）。"""
    rows = []
    cur: list[str] = []
    cur_len = 0
    for s in entry_strs:
        add = len(s) + (1 if cur else 0)
        if cur and cur_len + add > max_chars:
            rows.append(" ".join(cur))
            cur, cur_len = [], 0
            add = len(s)
        cur.append(s)
        cur_len += add
    if cur:
        rows.append(" ".join(cur))
    return rows


def format_fill_cards(fg: "FillGrid | None") -> list[str]:
    """生成 FILL 卡行列表。第一行无缩进（FILL=…），条目行为 '     …' 5 空格续行。

    调用方负责把第一行内联到 cell 行或作续行；条目行已是合法 MCNP 续行。
    fg 为 None → 返回空列表（单宇宙填充走 CellData.fill 普通路径）。

    用户复验修复（2026-08-24）：MCNP 规范 FILL 每行一个 j 行——行主序 i 最快，
    每行 = 固定 j 的一行 nx 个条目（17×17 → 每行 17 个、17 行）。**优先从 cells
    结构化展开**按 dims[0]=nx 分组；某行超 75 字符（含 5 空格缩进 ≤80 列）再按
    宽度拆子行（token 序不变）。raw 仅 cells 空或**截断**（len(cells) < dims 乘积，
    MAX_EXPANDED_ENTRIES 封顶致 cells 不完整）时兜底——截断数据展开会丢源 token，
    回落 raw 保 R1/保真。lat=2 六棱柱同样按 nx 行分组（token 序不变即 MCNP 合法，
    生成确定）。translated 单填充路径不变。
    """
    if fg is None:
        return []
    if fg.kind == "translated":
        e = fg.cells[0] if fg.cells else FillEntry()
        if e.dx or e.dy or e.dz:
            return [f"FILL={e.u}", f"     ({e.dx} {e.dy} {e.dz})"]
        return [f"FILL={e.u}"]

    # lattice
    range_str = " ".join(fg.range_) if fg.range_ else ""
    lines = [f"FILL={range_str}"]
    cells = fg.cells or []
    # 截断判定：dims 乘积 > cells 长度（MAX_EXPANDED_ENTRIES 封顶）→ cells 不完整
    truncated = False
    if fg.dims:
        _total = 1
        for _d in fg.dims:
            _total *= _d
        truncated = _total > len(cells)
    if not cells or truncated:
        # raw 兜底：cells 空（手工空格阵）或截断（数据不完整）→ 原样 token 回放
        if fg.raw:
            tokens = fg.raw.split()
            if len(fg.range_) > 0:
                tokens = tokens[len(fg.range_):]
            for row in _pack_entries(tokens):
                lines.append("     " + row)
        return lines
    # 结构化展开：按 dims[0]（nx）每行分组（行主序 i 最快 → 每行一个 j 行）
    nx = int(fg.dims[0]) if fg.dims else len(cells)
    if nx <= 0:
        nx = 1
    entry_strs = []
    for c in cells:
        s = c.u
        if c.dx or c.dy or c.dz:
            s += f" ({c.dx} {c.dy} {c.dz})"
        entry_strs.append(s)
    for start in range(0, len(entry_strs), nx):
        row_entries = entry_strs[start:start + nx]
        row_len = sum(len(s) + (1 if k else 0) for k, s in enumerate(row_entries))
        if row_len > 75:
            # 行超 75 字符（含 5 空格缩进 ≤80 列）→ 按宽度拆子行（token 序不变）
            for sub in _pack_entries(row_entries):
                lines.append("     " + sub)
        else:
            lines.append("     " + " ".join(row_entries))
    return lines


# ── 曲面预检测（阶段2 UI 画布：LatticeEditDialog 失焦校验）──
# 只认带符号整数曲面号交集；拒绝 #（补集）/ :（并集）/ 括号。自带曲面卡正则
# 解析（读 surfaces_text 定位对应曲面号定义），不依赖 freecad/parsers 模块。

_PLANE_AXIS = {"PX": "x", "PY": "y", "PZ": "z"}


def _parse_surface_cards(text: str) -> dict:
    """曲面卡文本 → {surface_number: (keyword, params_tokens)}。

    只识别 MCNP 曲面卡行（数字 + 关键字 + 参数）；跳过空行 / 注释行（C / $ 开头，
    及内联 $ 后缀）。支持 j*i 重复前缀与 *TRn 后缀（不影响关键字提取）。纯 stdlib。
    空文本或不可解析 → 返回空 dict（调用方据此报「未提供曲面定义」）。
    """
    surfaces = {}
    if not text:
        return surfaces
    for raw in text.splitlines():
        line = raw.split("$", 1)[0].strip()
        if not line or line[0] in ("C", "c", "$"):
            continue
        tokens = line.split()
        if len(tokens) < 2:
            continue
        first = tokens[0]
        # j*i 重复前缀（100*1 → 基础号 1）与前导 *（TR 变体）不影响号索引
        if "*" in first and first.split("*", 1)[0].isdigit():
            first = first.split("*", 1)[1]
        if first.startswith("*"):
            first = first[1:]
        try:
            num = int(first)
        except ValueError:
            continue
        surfaces[num] = (tokens[1].lstrip("*").upper(), tokens[2:])
    return surfaces


def _plane_normal(params: list) -> tuple | None:
    """P 卡参数 → 法向 (A,B,C)。支持系数形（A B C D）与三点形（p1 p2 p3）。
    跳过 *TRn 等非数值 token。参数不足返回 None。
    """
    nums = []
    for p in params:
        try:
            nums.append(float(p))
        except (ValueError, TypeError):
            continue
    if len(nums) >= 9:  # 三点形
        x1, y1, z1, x2, y2, z2, x3, y3, z3 = nums[:9]
        ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
        vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
        return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    if len(nums) >= 3:  # 系数形 A B C …
        return (nums[0], nums[1], nums[2])
    return None


def _check_axis_pairs(resolved: list, axes_required=None) -> tuple:
    """按轴检查成对（每轴一对±、号互异）。axes_required=None 时要求恰好 2 轴（2D 延伸）。"""
    by_axis = {"x": [], "y": [], "z": []}
    for num, sign, kw, _p in resolved:
        by_axis[_PLANE_AXIS[kw]].append((num, sign))
    used = [ax for ax in ("x", "y", "z") if by_axis[ax]]
    for ax in ("x", "y", "z"):
        pair = by_axis[ax]
        if len(pair) > 2:
            return False, f"轴 {ax.upper()} 有 {len(pair)} 个平面（六面体每轴至多一对±）"
        if len(pair) == 2:
            if {s for _, s in pair} != {1, -1}:
                return False, f"轴 {ax.upper()} 的两个平面必须一正一负（当前 {pair}）"
            if pair[0][0] == pair[1][0]:
                return False, f"轴 {ax.upper()} 的两个平面是同一曲面（退化零宽）"
    if axes_required is not None:
        if set(used) != set(axes_required):
            return False, f"需要每轴一对±（当前轴分布: {used}）"
    elif len(used) != 2:
        return False, f"4 平面 2D 延伸需两轴各一对±（当前轴分布: {used}）"
    return True, ""


def _resolve_surfaces(expr_ints: list, surfaces: dict) -> tuple:
    """逐号查曲面定义 → ([(num, sign, kw, params)], err)；缺失号 → (None, 中文错误)。"""
    resolved = []
    for num, sign in expr_ints:
        info = surfaces.get(num)
        if info is None:
            return None, f"曲面 {num} 未在曲面卡中定义"
        kw, params = info
        resolved.append((num, sign, kw, params))
    return resolved, ""


def _validate_lat1(expr_ints: list, surfaces: dict) -> tuple:
    """lat=1 六面体：单 RPP/BOX 宏体，或 6 平面（每轴一对±），或 4 平面（2D 延伸）。"""
    if len(expr_ints) == 1:
        num, _sign = expr_ints[0]
        kw, _p = surfaces.get(num, (None, []))
        if kw in ("RPP", "BOX"):
            return True, ""
        return False, f"lat=1 单宏体必须是 RPP/BOX 六面体宏（曲面 {num} 为 {kw or '未定义'}）"
    if len(expr_ints) not in (4, 6):
        return False, (
            f"lat=1 六面体需 1 个 RPP/BOX 宏体、6 个平面（每轴一对±）"
            f"或 4 个平面（2D 延伸）；当前 {len(expr_ints)} 个曲面"
        )
    resolved, err = _resolve_surfaces(expr_ints, surfaces)
    if err:
        return False, err
    for num, _sign, kw, _params in resolved:
        if kw not in _PLANE_AXIS:
            return False, f"曲面 {num} 类型 {kw} 不是六面体平面（需 PX/PY/PZ）"
    return _check_axis_pairs(
        resolved, axes_required=({"x", "y", "z"} if len(expr_ints) == 6 else None))


def _rhp_angle_deg(a: list, b: list) -> float:
    """两向量夹角（度）。任一零向量 → 0.0（由调用方先验 |R|>0）。"""
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    cosv = sum(a[i] * b[i] for i in range(3)) / (na * nb)
    cosv = max(-1.0, min(1.0, cosv))
    return math.degrees(math.acos(cosv))


def _validate_rhp_params(params: list) -> tuple:
    """RHP/HEX 单宏体参数合法性校验（项4，2026-08-24 破坏性变更）。

    规则：合法参数数 ∈ {9,12,15,18}；|H|>0；|R1|>0；H·R1≈0（⊥）；
    若给 R2（≥12 参）→ ⊥H 且 R1/R2 夹角 60°；若给 R3（≥15 参）→ ⊥H 且
    R2/R3 夹角 60°（R1/R3 = 120° 为六棱柱第三个面位方向，合法）。
    连续 60° 旋转语义与 _rhp_extent 的 Rodrigues 推断（R2=rot60(R1)、R3=rot120(R1)）
    一致——真实正六棱柱 R1/R2/R3 取 0°/60°/120°。*TRn 等非数值 token 跳过。
    """
    nums = []
    for p in params:
        try:
            nums.append(float(p))
        except (ValueError, TypeError):
            continue  # *TRn 等非数值 token 跳过
    if len(nums) not in (9, 12, 15, 18):
        return False, (f"RHP/HEX 宏体合法参数数为 9/12/15/18（V+H+R1[+R2[+R3]]）；"
                       f"当前 {len(nums)} 个")
    h = nums[3:6]
    r1 = nums[6:9]
    hnorm = math.sqrt(sum(x * x for x in h))
    r1norm = math.sqrt(sum(x * x for x in r1))
    if hnorm <= 1e-12:
        return False, "RHP/HEX 高度向量 H 长度必须 >0（当前 0）"
    if r1norm <= 1e-12:
        return False, "RHP/HEX 第一面位向量 R1 长度必须 >0（当前 0）"
    if abs(sum(h[i] * r1[i] for i in range(3))) / (hnorm * r1norm) > 1e-6:
        return False, "RHP/HEX 的 H 与 R1 必须垂直（当前夹角非 90°）"
    if len(nums) >= 12:
        r2 = nums[9:12]
        if abs(sum(h[i] * r2[i] for i in range(3))) / hnorm > 1e-6:
            return False, "RHP/HEX 的 R2 必须垂直 H"
        a12 = _rhp_angle_deg(r1, r2)
        if abs(a12 - 60.0) > 0.5:
            return False, f"RHP/HEX 的 R1/R2 夹角应 60°（当前 {a12:.1f}°）"
    if len(nums) >= 15:
        r3 = nums[12:15]
        if abs(sum(h[i] * r3[i] for i in range(3))) / hnorm > 1e-6:
            return False, "RHP/HEX 的 R3 必须垂直 H"
        a23 = _rhp_angle_deg(nums[9:12], r3)
        if abs(a23 - 60.0) > 0.5:
            return False, f"RHP/HEX 的 R2/R3 夹角应 60°（当前 {a23:.1f}°）"
    return True, ""


def _validate_lat2(expr_ints: list, surfaces: dict) -> tuple:
    """lat=2 六棱柱：单 RHP/HEX 宏体，或 6 个竖直 P 平面（法向水平面均布 6 向）+ 2 个 PZ 顶底。"""
    if len(expr_ints) == 1:
        num, _sign = expr_ints[0]
        kw, params = surfaces.get(num, (None, []))
        if kw in ("RHP", "HEX"):
            return _validate_rhp_params(params)
        return False, f"lat=2 单宏体必须是 RHP/HEX 六棱柱宏（曲面 {num} 为 {kw or '未定义'}）"
    if len(expr_ints) != 8:
        return False, (
            f"lat=2 六棱柱需 1 个 RHP/HEX 宏体，或 6 个竖直 P 平面 + 2 个 PZ（顶底），"
            f"共 8 个曲面；当前 {len(expr_ints)} 个"
        )
    pz = []    # (num, sign)
    sides = []  # (num, sign, params)
    resolved, err = _resolve_surfaces(expr_ints, surfaces)
    if err:
        return False, err
    for num, sign, kw, params in resolved:
        if kw == "PZ":
            pz.append((num, sign))
        elif kw == "P":
            sides.append((num, sign, params))
        else:
            return False, f"曲面 {num} 类型 {kw} 不是六棱柱平面（需 P 竖直侧平面或 PZ 顶底）"
    if len(pz) != 2:
        return False, f"lat=2 需要 2 个 PZ 顶底平面（当前 {len(pz)} 个）"
    if len(sides) != 6:
        return False, f"lat=2 需要 6 个 P 侧平面（当前 {len(sides)} 个）"
    if pz[0][0] == pz[1][0]:
        return False, "PZ 顶底平面不能是同一曲面（退化零高）"
    if pz[0][1] == pz[1][1]:
        return False, "PZ 顶底平面必须一正一负（一面从下方、一面从上方约束）"
    angles = []
    for num, _sign, params in sides:
        n = _plane_normal(params)
        if n is None:
            return False, f"曲面 {num} 的 P 卡参数不足（需 A B C D 或三点定义）"
        a, b, c = n
        scale = max(1.0, abs(a), abs(b), abs(c))
        if abs(c) / scale > 1e-6:
            return False, f"曲面 {num} 的 P 平面法向不水平（C≠0），六棱柱侧平面必须竖直"
        if abs(a) < 1e-12 and abs(b) < 1e-12:
            return False, f"曲面 {num} 的 P 平面法向为零向量"
        angles.append(math.degrees(math.atan2(b, a)) % 360.0)
    angles.sort()
    gaps = [((angles[(i + 1) % 6] - angles[i]) % 360.0) for i in range(6)]
    if any(abs(g - 60.0) > 0.5 for g in gaps):
        return False, "6 个 P 平面法向未均布 60°（非正六棱柱侧平面）"
    return True, ""


def validate_lattice_surfaces(surface_expr: str, lat: str, surfaces_text: str = "") -> tuple:
    """预检测格阵栅元的曲面表达式是否构成合法格元（lat=1 六面体 / lat=2 六棱柱）。

    只认带符号整数曲面号交集（如 '-10 20 -30 40'）；拒绝 '#'（补集）/ ':'（并集）/ 括号。
    曲面类型解析自带（读 surfaces_text 定位对应曲面号定义），不依赖 freecad/parsers。

    - lat="1"：合法 = 单 RPP/BOX 宏体；或 6 个 PX/PY/PZ 平面（每轴一对±）；
      或 4 个平面（2D 延伸，两轴各一对±，第三轴无界）。
    - lat="2"：合法 = 单 RHP/HEX 宏体；或 6 个竖直 P 平面（法向在水平面均布 6 向）
      + 2 个 PZ（顶底，一正一负）。

    返回 (True, "") 或 (False, 中文错误消息)。
    """
    lat = str(lat)
    if not surface_expr or not surface_expr.strip():
        return False, "曲面表达式为空"
    expr = surface_expr.strip()
    if any(ch in expr for ch in "#:()"):
        return False, "曲面表达式只能为带符号整数曲面号交集（不支持 # 补集 / : 并集 / 括号）"
    expr_ints = []
    for tok in expr.split():
        if not _INT_RE.match(tok):
            return False, f"非法曲面记号 {tok!r}（只接受带符号整数曲面号）"
        n = int(tok)
        expr_ints.append((abs(n), 1 if n >= 0 else -1))
    surfaces = _parse_surface_cards(surfaces_text)
    if not surfaces:
        return False, "未提供曲面卡定义（surfaces_text 为空），无法校验曲面类型"
    if lat == "1":
        return _validate_lat1(expr_ints, surfaces)
    if lat == "2":
        return _validate_lat2(expr_ints, surfaces)
    return False, f"不支持的 lat 类型 {lat!r}（仅支持 lat=1 六面体 / lat=2 六棱柱）"


# ── 阶段3：3D 预览 — universe 实例化 + 嵌套 fill 递归 ──
# 纯 stdlib 深模块函数，与前端 TS 镜像（gui/src/utils/lattice.ts）键名/公式逐字一致，
# 跨语言 golden（gui/src/utils/__golden__/latticeGolden.json）锁死。

MAX_LATTICE_DEPTH = 8          # 嵌套 fill 递归深度上限（超 → status="depth_limit"）
MAX_TOTAL_INSTANCES = 500_000  # 叶实例总数上限（超 → status="too_many"）
DETAIL_MAX_INSTANCES = 20_000  # 详细模式（逐 universe STL）上限，超 → 自动切色块总览


def _num(s) -> float:
    """数值字符串 → float；空/非法 → 0.0。"""
    if s is None or s == "":
        return 0.0
    try:
        return float(str(s))
    except (ValueError, TypeError):
        return 0.0


# ── 六棱柱蜂窝环（画布与 3D 共用权威，golden 锁死）──────────

def hex_ring_rows(rings: int) -> list:
    """蜂窝环行长度：rings=r → 2r+1 行，行长 r+1+min(j, 2r-j)。总和 = 1+3r(r+1)。"""
    rows = []
    for j in range(2 * rings + 1):
        rows.append(rings + 1 + min(j, 2 * rings - j))
    return rows


def hex_ring_cell_count(rings: int) -> int:
    """蜂窝总格数：1+3r(r+1)。"""
    return 1 + 3 * rings * (rings + 1)


def hex_center(col: int, row: int, pitch: float):
    """MCNP LAT=2 蜂窝格位中心（交叉验证自官方测试库 u233-comp-therm-001-case-6.i）。

    真实卡格元用 6 竖直平面（法向 0°/60°/120°，flat-top），基向量
      a1=(2a,0)（0° 方向）、a2=(a, a·√3)（60° 方向），a=apothem，pitch=2a=中心距。
    元素 (col,row) 位于 col·a1 + row·a2：
      x = (col + row/2)·pitch,  y = row·pitch·√3/2
    旧公式 x=col·p·√3/2, y=row·p+(col%2)·p/2 与此差 30° 旋转，已按 MCNP 修正
    （2026-08-25 交叉验证后替换；golden hexCenter/positions.hex 同步更新）。
    自洽：相邻 (0,0)→(1,0) 距=p，相邻 (0,0)→(0,1) 距=√((p/2)²+(p·√3/2)²)=p。
    """
    return (col * pitch + row * (pitch / 2.0),
            row * pitch * (math.sqrt(3.0) / 2.0))


# ── 格元范围（lattice_cell_extent：供 pitch/裁剪盒推导）────

def _float0(params) -> float | None:
    """曲面卡参数列表 → 第一个数值；无 → None。"""
    for p in params:
        try:
            return float(p)
        except (ValueError, TypeError):
            continue
    return None


def _nums_of(params) -> list:
    """曲面卡参数列表 → 可转数值的列表（跳过 *TRn 等非数值 token）。"""
    nums = []
    for p in params:
        try:
            nums.append(float(p))
        except (ValueError, TypeError):
            continue
    return nums


def _plane_const(params):
    """P 卡参数 → (法向 n, 常数 D)，满足 n·p = D（D 已按 MCNP 符号约定换算）。

    MCNP P 卡系数形 A B C D 定义 Ax+By+Cz+D = 0 → n·p = -D；
    三点形 (p1 p2 p3) → n = (p2-p1)×(p3-p1), D = n·p1。
    负侧（-surf）= n·p < D。参数不足返回 (None, None)。
    """
    nums = _nums_of(params)
    if len(nums) >= 4:  # 系数形 A B C D → n·p = -D
        return (nums[0], nums[1], nums[2]), -nums[3]
    if len(nums) >= 9:  # 三点形
        x1, y1, z1, x2, y2, z2, x3, y3, z3 = nums[:9]
        ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
        vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        return n, n[0] * x1 + n[1] * y1 + n[2] * z1
    return None, None


def _rpp_extent(params):
    if len(params) < 6:
        return None
    try:
        x1, x2, y1, y2, z1, z2 = [float(p) for p in params[:6]]
    except (ValueError, TypeError):
        return None
    return {"x_min": min(x1, x2), "x_max": max(x1, x2),
            "y_min": min(y1, y2), "y_max": max(y1, y2),
            "z_min": min(z1, z2), "z_max": max(z1, z2)}


def _box_extent(params):
    """BOX 宏体：center + 三基向量 → 8 角点 AABB。

    部分卡省略 v3（9 参数）→ 按 v3 = v1×v2 补全（右旋直角盒）。纯 stdlib。
    """
    if len(params) < 9:
        return None
    try:
        cx, cy, cz = [float(p) for p in params[:3]]
        v1 = [float(p) for p in params[3:6]]
        v2 = [float(p) for p in params[6:9]]
    except (ValueError, TypeError):
        return None
    if len(params) >= 12:
        try:
            v3 = [float(p) for p in params[9:12]]
        except (ValueError, TypeError):
            v3 = None
    else:
        v3 = None
    if v3 is None:
        v3 = [v1[1] * v2[2] - v1[2] * v2[1],
              v1[2] * v2[0] - v1[0] * v2[2],
              v1[0] * v2[1] - v1[1] * v2[0]]
    xs, ys, zs = [], [], []
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                xs.append(cx + a * v1[0] + b * v2[0] + c * v3[0])
                ys.append(cy + a * v1[1] + b * v2[1] + c * v3[1])
                zs.append(cz + a * v1[2] + b * v2[2] + c * v3[2])
    return {"x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys),
            "z_min": min(zs), "z_max": max(zs)}


def _rotate_about(v, axis, theta):
    """Rodrigues 旋转：向量 v 绕单位轴 axis 旋转 theta 弧度 → 新向量。

    v' = v·cosθ + (k×v)·sinθ + k·(k·v)(1-cosθ)
    """
    kx, ky, kz = axis
    c, s = math.cos(theta), math.sin(theta)
    dot = kx * v[0] + ky * v[1] + kz * v[2]
    cross = (ky * v[2] - kz * v[1],
             kz * v[0] - kx * v[2],
             kx * v[1] - ky * v[0])
    return [v[0] * c + cross[0] * s + kx * dot * (1.0 - c),
            v[1] * c + cross[1] * s + ky * dot * (1.0 - c),
            v[2] * c + cross[2] * s + kz * dot * (1.0 - c)]


def _rhp_extent(params):
    """RHP/HEX 宏体：六棱柱 AABB。h=全高向量（沿 ±h/2），v1/v2=外接半径向量（60° 夹角）。

    六个侧顶点 = center ± v1, ± v2, ± (v1-v2)。

    参数数支持（项4，2026-08-24）：
      9 参（V+H+R1）→ R2 按 MCNP 语义绕 H 转 60° 推断（Rodrigues）；
      12/15/18 参原样读取前 12 个（R2 显式给出；R3 冗余于 AABB，无需读取）。
    """
    if len(params) < 9:
        return None
    try:
        cx, cy, cz = [float(p) for p in params[:3]]
        h = [float(p) for p in params[3:6]]
        v1 = [float(p) for p in params[6:9]]
    except (ValueError, TypeError):
        return None
    v2 = None
    if len(params) >= 12:
        try:
            v2 = [float(p) for p in params[9:12]]
        except (ValueError, TypeError):
            v2 = None
    if v2 is None:
        # 9 参：R2 = R1 绕 H 转 60°（MCNP RHP 缺省推断，与 12 参路径 AABB 一致）
        hnorm = math.sqrt(h[0] * h[0] + h[1] * h[1] + h[2] * h[2])
        if hnorm <= 1e-12:
            return None
        axis = [h[0] / hnorm, h[1] / hnorm, h[2] / hnorm]
        v2 = _rotate_about(v1, axis, math.pi / 3.0)
    dirs = [v1, [-v1[0], -v1[1], -v1[2]],
            v2, [-v2[0], -v2[1], -v2[2]],
            [v1[0] - v2[0], v1[1] - v2[1], v1[2] - v2[2]],
            [v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]]]
    xs, ys, zs = [], [], []
    for d in dirs:
        xs.append(cx + d[0]); ys.append(cy + d[1]); zs.append(cz + d[2])
    xs.extend([cx - h[0] / 2.0, cx + h[0] / 2.0])
    ys.extend([cy - h[1] / 2.0, cy + h[1] / 2.0])
    zs.extend([cz - h[2] / 2.0, cz + h[2] / 2.0])
    return {"x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys),
            "z_min": min(zs), "z_max": max(zs)}


def _plane_box_extent(expr_ints, surfaces):
    """lat=1 6/4 平面盒：每轴 ± 平面 → 范围；缺轴/缺对 → 该轴 None（无界）。"""
    pos = {"x": [], "y": [], "z": []}
    neg = {"x": [], "y": [], "z": []}
    for num, sign in expr_ints:
        kw, params = surfaces.get(num, (None, []))
        if kw not in _PLANE_AXIS:
            return None
        ax = _PLANE_AXIS[kw]
        v = _float0(params)
        if v is None:
            return None
        if sign > 0:      # x > v → 下界候选
            pos[ax].append(v)
        else:             # x < v → 上界候选
            neg[ax].append(v)
    out = {}
    for ax in "xyz":
        lo = max(pos[ax]) if pos[ax] else None
        hi = min(neg[ax]) if neg[ax] else None
        out[ax + "_min"] = lo
        out[ax + "_max"] = hi
    return out


def _hex_plane_extent(expr_ints, surfaces):
    """lat=2 6 侧 P + 2 PZ：侧平面两两求交得六边形顶点 → x/y AABB；PZ 给 z 界。"""
    sides = []   # (angle, nx, ny, D) 半空间 n·p < D
    pz_lo, pz_hi = None, None
    for num, sign in expr_ints:
        kw, params = surfaces.get(num, (None, []))
        if kw == "P":
            n, D = _plane_const(params)
            if n is None:
                return None
            nx, ny, nz = n
            if abs(nz) > 1e-9:
                return None  # 侧平面须水平
            # 负侧 → n·p < D；正侧 → (-n)·p < -D
            eff_n = (-nx, -ny) if sign > 0 else (nx, ny)
            eff_D = (-D) if sign > 0 else D
            angle = math.degrees(math.atan2(eff_n[1], eff_n[0])) % 360.0
            sides.append((angle, eff_n[0], eff_n[1], eff_D))
        elif kw == "PZ":
            z0 = _float0(params)
            if z0 is None:
                return None
            if sign < 0:  # z < z0 → 上界
                pz_hi = z0 if pz_hi is None else min(pz_hi, z0)
            else:         # z > z0 → 下界
                pz_lo = z0 if pz_lo is None else max(pz_lo, z0)
        else:
            return None
    if len(sides) < 3:
        return None
    sides.sort(key=lambda s: s[0])
    verts = []
    m = len(sides)
    for i in range(m):
        _a1, nx1, ny1, D1 = sides[i]
        _a2, nx2, ny2, D2 = sides[(i + 1) % m]
        det = nx1 * ny2 - ny1 * nx2
        if abs(det) < 1e-12:
            return None
        x = (D1 * ny2 - ny1 * D2) / det
        y = (nx1 * D2 - D1 * nx2) / det
        verts.append((x, y))
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    return {"x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys),
            "z_min": pz_lo, "z_max": pz_hi}


def lattice_cell_extent(surface_expr: str, lat: str,
                        surfaces_text: str = "") -> dict | None:
    """格元曲面表达式 → 物理范围 {x_min,x_max,y_min,y_max,z_min,z_max}。

    - lat=1：单 RPP/BOX 宏体，或 6 平面（每轴一对±）、4 平面（2D，z 无界→None）。
    - lat=2：单 RHP/HEX 宏体，或 6 竖直 P 平面（两两求交得六边形 AABB）+ 2 PZ。
    无法解析（含 #/:/括号/缺曲面定义）返回 None。纯 stdlib，复用 _parse_surface_cards。
    """
    if not surface_expr or not str(surface_expr).strip():
        return None
    lat = str(lat)
    expr = str(surface_expr).strip()
    if any(ch in expr for ch in "#:()"):
        return None
    expr_ints = []
    for tok in expr.split():
        if not _INT_RE.match(tok):
            return None
        n = int(tok)
        expr_ints.append((abs(n), 1 if n >= 0 else -1))
    surfaces = _parse_surface_cards(surfaces_text)
    if not surfaces:
        return None
    if len(expr_ints) == 1:
        num, _sign = expr_ints[0]
        kw, params = surfaces.get(num, (None, []))
        if kw in ("RPP",):
            return _rpp_extent(params)
        if kw in ("BOX",):
            return _box_extent(params)
        if kw in ("RHP", "HEX"):
            return _rhp_extent(params)
    if lat == "1":
        return _plane_box_extent(expr_ints, surfaces)
    if lat == "2":
        return _hex_plane_extent(expr_ints, surfaces)
    return None


# ── 格位展开（expand_positions：universe 实例化坐标系权威）──

def _extent_span(extent: dict | None, axis: str, default: float = 1.0) -> float:
    """extent 轴跨度；无界/缺失 → default。"""
    if extent:
        lo = extent.get(axis + "_min")
        hi = extent.get(axis + "_max")
        if lo is not None and hi is not None:
            try:
                s = float(hi) - float(lo)
                if s > 0:
                    return s
            except (TypeError, ValueError):
                pass
    return default


def _lattice_pitch(extent: dict | None, lat: str):
    """extent → 每轴 pitch (px, py, pz)。

    rect：x/y/z 跨度（无界默认 1）；hex：中心距 = 竖直 flat-to-flat 跨度（R√3）。
    """
    px = _extent_span(extent, "x", 1.0)
    py = _extent_span(extent, "y", 1.0)
    pz = _extent_span(extent, "z", 1.0)
    if str(lat) == "2":
        p = py if py > 0 else (px if px > 0 else 1.0)
        px = p
        py = p
    return px, py, pz


def _cell_pz_bounds(surface_expr: str, surfaces_text: str = "") -> tuple:
    """扫描栅元曲面表达式中的 PZ 约束 → (z_lower, z_upper)；无 PZ 返回 (None, None)。

    -surf(PZ z0) → z < z0（上界）；+surf(PZ z0) → z > z0（下界）。
    """
    if not surface_expr or not str(surface_expr).strip():
        return None, None
    expr = str(surface_expr).strip()
    if any(ch in expr for ch in "#:()"):
        return None, None
    surfaces = _parse_surface_cards(surfaces_text)
    lo, hi = None, None
    for tok in expr.split():
        if not _INT_RE.match(tok):
            continue
        n = int(tok)
        kw, params = surfaces.get(abs(n), (None, []))
        if kw != "PZ":
            continue
        z0 = _float0(params)
        if z0 is None:
            continue
        if n > 0:  # z > z0 → 下界
            lo = z0 if lo is None else max(lo, z0)
        else:      # z < z0 → 上界
            hi = z0 if hi is None else min(hi, z0)
    return lo, hi


def _extent_center(extent: dict | None) -> list:
    """extent → 中心 [cx, cy, cz]（无界轴取 0）。"""
    c = []
    for ax in "xyz":
        if extent:
            lo = extent.get(ax + "_min")
            hi = extent.get(ax + "_max")
            if lo is not None and hi is not None:
                c.append((float(lo) + float(hi)) / 2.0)
                continue
        c.append(0.0)
    return c


def expand_positions(fg: "FillGrid | None", extent: dict | None,
                     trcl_rotation_deg: float = 0,
                     max_positions: int = MAX_EXPANDED_ENTRIES) -> list | None:
    """格阵 → 每格位中心 [{idx,u,x,y,z,dx,dy,dz}, ...]。

    - rect 中心 = ((i-(nx-1)/2)*px, (j-(ny-1)/2)*py, (k-(nz-1)/2)*pz)（pitch 来自 extent）
    - hex 用矩形盒模型 + hex_center 格位（角位 void 由 fill u="0" 承载，不排除）
    - TRCL 绕 Z 旋转（trcl_rotation_deg 度）
    - 格位总数超 max_positions → 返回 None（实例上限拒绝）
    与前端 lattice.ts hexGrid/hexCenter 键名/公式逐字一致。
    """
    if fg is None:
        return None
    dims = list(fg.dims or [1])
    while len(dims) < 3:
        dims.append(1)
    nx, ny, nz = int(dims[0]) or 1, int(dims[1]) or 1, int(dims[2]) or 1
    total = nx * ny * nz
    if total > max_positions:
        return None
    lat = str(fg.lat or "1")
    px = _extent_span(extent, "x", 1.0)
    py = _extent_span(extent, "y", 1.0)
    pz = _extent_span(extent, "z", 1.0)
    if lat == "2":
        hp = py if py > 0 else (px if px > 0 else 1.0)
        px = hp
        py = hp
    theta = math.radians(float(trcl_rotation_deg or 0))
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    out = []
    cells = fg.cells
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                idx = i + nx * (j + ny * k)  # 行主序 i 最快（rectGrid idxOf 一致）
                entry = cells[idx] if idx < len(cells) else FillEntry()
                if lat == "2":
                    hx, hy = hex_center(i, j, px)
                    cz = (k - (nz - 1) / 2.0) * pz
                else:
                    hx = (i - (nx - 1) / 2.0) * px
                    hy = (j - (ny - 1) / 2.0) * py
                    cz = (k - (nz - 1) / 2.0) * pz
                if theta:
                    x = hx * cos_t - hy * sin_t
                    y = hx * sin_t + hy * cos_t
                else:
                    x, y = hx, hy
                out.append({
                    "idx": idx,
                    "u": entry.u,
                    "x": x, "y": y, "z": cz,
                    "dx": _num(entry.dx), "dy": _num(entry.dy), "dz": _num(entry.dz),
                })
    return out


# ── 嵌套 fill 递归（compose_lattice_tree）──────────────

def _find_lattice_cell_num(fg, sub_by_u):
    """在 sub_by_u 中定位 fill_grid == fg 的格阵 cell 号（身份或 JSON 相等）。"""
    if fg is None:
        return None
    fg_json = None
    try:
        fg_json = fg.to_json()
    except Exception:
        pass
    for _u, cells in sub_by_u.items():
        for cell in cells:
            c_fg = cell.get("fill_grid")
            if c_fg is None or c_fg.kind != "lattice":
                continue
            if c_fg is fg:
                return cell.get("cellNum")
            if fg_json is not None:
                try:
                    if c_fg.to_json() == fg_json:
                        return cell.get("cellNum")
                except Exception:
                    continue
    return None


def detect_fill_cycle(sub_by_u: dict) -> dict:
    """DFS 判环：基于 sub_by_u fill 图的 universe 循环嵌套检测（项13，跨语言锁死 L6）。

    边 U→V：universe U 中任一 cell，其 fill_grid(kind=lattice/translated).cells[].u == V
            或 fill 单值 == V（V≠"0"/""）。
    递归栈成员表判环：chain = path[path.index(U):] + [U]；全图无环 → {"cycle":false,"chain":[]}。

    返回 {"cycle": bool, "chain": list[str]}，chain 形如 ["1","2","1"]。
    """
    graph = {}
    for u, cells in (sub_by_u or {}).items():
        targets = []
        for cell in cells or []:
            fg = cell.get("fill_grid")
            if fg is not None and fg.kind in ("lattice", "translated"):
                for e in (fg.cells or []):
                    v = str(getattr(e, "u", "") or "")
                    if v and v != "0":
                        targets.append(v)
            else:
                fv = str(cell.get("fill") or "").strip()
                if fv and fv != "0":
                    targets.append(fv)
        graph[str(u)] = targets

    visited = set()
    stack = []
    in_stack = set()

    def _dfs(u):
        stack.append(u)
        in_stack.add(u)
        for v in graph.get(u, []):
            if v in in_stack:
                idx = stack.index(v)
                return {"cycle": True, "chain": stack[idx:] + [v]}
            if v not in visited:
                res = _dfs(v)
                if res is not None:
                    return res
        stack.pop()
        in_stack.discard(u)
        visited.add(u)
        return None

    for u in sorted(graph):
        if u not in visited:
            res = _dfs(u)
            if res is not None:
                return res
    return {"cycle": False, "chain": []}


def compose_lattice_tree(outer_fg: "FillGrid | None", sub_by_u: dict,
                         extent: dict | None, trcl,
                         max_depth: int = MAX_LATTICE_DEPTH,
                         max_total: int = MAX_TOTAL_INSTANCES) -> dict:
    """嵌套 fill 递归：从外层格阵出发构建 NESTED TREE + FLAT leafInstances + 各格阵 positions。

    双形态返回：
      ① tree：NESTED 保层次（hover / U 分组 / 调试）
      ② leafInstances：[{path,u,cellNum,mat,x,y,z,depth}] FLAT 绝对坐标（InstancedMesh 直食）

    sub_by_u: {u_str: [cell_info]}，cell_info = {
        "cellNum", "material", "fill", "fill_grid"(FillGrid|None), "surface_expr",
        "lat", "trcl", "extent"(dict|None，格阵 cell 的调用方预计算范围)}
    递归规则：
      - 构建 universe U：若含格阵 cell（fill_grid.kind=="lattice"）→ 先递归展开子格阵
        （子元素裁各自格元盒、平移到父格位），再整体裁外层盒；
      - fill=X 单值列（含 translated 偏移）也递归；fill="0" 的 cell = 装配容器不产 STL；
      - 叶级 = material≠0 且无 fill（去重 (叶u,cellNum) 一个 STL 由前端负责）；
      - void 叶（material=0 无 fill）→ 产 {leaf, void:true} 透明占位（计入 count，规则4）。
    入口先 detect_fill_cycle → 命中返回 {status:"cycle", cycle:chain, ...}（不递归）。
    返回 {status:"ok"|"depth_limit"|"too_many"|"cycle", tree, leafInstances, count,
          lattices, detailViable[, cycle, chain]}。
    """
    if outer_fg is None:
        return {"status": "ok", "tree": [], "leafInstances": [], "count": 0,
                "lattices": [], "detailViable": True}
    cyc = detect_fill_cycle(sub_by_u)
    if cyc["cycle"]:
        return {"status": "cycle", "cycle": cyc["chain"],
                "tree": [], "leafInstances": [], "count": 0,
                "lattices": [], "detailViable": True}
    state = {
        "sub_by_u": sub_by_u,
        "max_depth": int(max_depth),
        "max_total": int(max_total),
        "status": "ok",
        "leaves": [],
        "lattices": [],
        "count": 0,
    }
    outer_num = _find_lattice_cell_num(outer_fg, sub_by_u)
    root_ctx = {"base": (0.0, 0.0, 0.0), "depth": 1, "path": "",
                "trcl": float(trcl or 0)}
    tree = _expand_lattice(outer_fg, extent, outer_num, root_ctx, state)
    return {
        "status": state["status"],
        "tree": tree,
        "leafInstances": state["leaves"],
        "count": state["count"],
        "lattices": state["lattices"],
        "detailViable": state["count"] <= DETAIL_MAX_INSTANCES,
    }


def _expand_lattice(fg, extent, cell_num, ctx, state) -> list:
    """展开一个格阵：返回该格阵的 NESTED 节点列表；同时填 state.lattices/leaves。"""
    positions = expand_positions(fg, extent, trcl_rotation_deg=ctx["trcl"])
    if positions is None:
        state["status"] = "too_many"
        return []
    lat = str(fg.lat or "1")
    px, py, pz = _lattice_pitch(extent, lat)
    entry = {
        "num": cell_num,
        "lat": lat,
        "kind": fg.kind,
        "dims": list(fg.dims),
        "range": list(fg.range_),
        "center": _extent_center(extent),
        "pitch": [px, py, pz],
        "height": pz,
        "trclRotationDeg": ctx["trcl"],
        "extent": dict(extent) if extent else None,
        "positions": positions,
        "universes": {},   # handler 填充 STL
    }
    # 同格阵 cell 可能被多个父格位引用（嵌套）→ 只登记一次（positions 相对自身原点，与父位无关）
    if cell_num is None or cell_num not in state.setdefault("_seen_lattices", set()):
        state["_seen_lattices"].add(cell_num)
        state["lattices"].append(entry)
    nodes = []
    bx, by, bz = ctx["base"]
    for pos in positions:
        u = str(pos.get("u", ""))
        if u in ("0", ""):
            continue  # 角位 void
        if state["count"] >= state["max_total"]:
            state["status"] = "too_many"
            break
        depth = ctx["depth"]
        if depth > state["max_depth"]:
            state["status"] = "depth_limit"
            break
        abs_x = bx + pos.get("x", 0.0) + pos.get("dx", 0.0)
        abs_y = by + pos.get("y", 0.0) + pos.get("dy", 0.0)
        abs_z = bz + pos.get("z", 0.0) + pos.get("dz", 0.0)
        idx = pos.get("idx", "")
        path = f"{ctx['path']}.{idx}" if ctx["path"] else str(idx)
        node = _expand_universe(u, (abs_x, abs_y, abs_z), depth, path, state)
        if node is not None:
            nodes.append(node)
    return nodes


def _expand_universe(u, base_xyz, depth, path, state) -> dict | None:
    """展开 universe u 的栅元 → 该格位的 NESTED 节点（无可渲染子节点 → None）。"""
    cells = state["sub_by_u"].get(str(u))
    if not cells:
        return None
    bx, by, bz = base_xyz
    node = {"u": str(u), "x": bx, "y": by, "z": bz,
            "depth": depth, "path": path, "children": []}
    for cell in cells:
        fg = cell.get("fill_grid")
        if fg is not None and fg.kind == "lattice":
            # 嵌套格阵：先递归展开子格阵，再整体裁外层盒
            sub_extent = cell.get("extent")
            sub_trcl = float(cell.get("trcl_deg") or 0)
            sub_num = cell.get("cellNum")
            sub_ctx = {"base": base_xyz, "depth": depth + 1,
                       "path": path, "trcl": sub_trcl}
            sub_nodes = _expand_lattice(fg, sub_extent, sub_num, sub_ctx, state)
            node["children"].extend(sub_nodes)
            continue
        # fill=X 单值列（含 translated 偏移）也递归
        if fg is not None and fg.kind == "translated":
            e = fg.cells[0] if fg.cells else FillEntry()
            target_u = e.u
            off = (_num(e.dx), _num(e.dy), _num(e.dz))
        else:
            target_u = cell.get("fill")
            off = (0.0, 0.0, 0.0)
        fv = str(target_u or "").strip()
        if fv:
            # 装配容器：fill 非空（含 fill="0"，规则1/7）→ 不自产 STL；指向真实
            # universe 才递归（fill="0"=void 填充，无 universe 可递归）。
            if fv != "0":
                nb = (bx + off[0], by + off[1], bz + off[2])
                sub_node = _expand_universe(fv, nb, depth + 1, path, state)
                if sub_node is not None:
                    node["children"].append(sub_node)
            continue
        mat_s = str(cell.get("material") or "").strip()
        if mat_s not in ("0", ""):
            # 叶级：material≠0 且无 fill（规则2）
            leaf = {
                "path": path,
                "u": str(u),
                "cellNum": cell.get("cellNum"),
                "mat": mat_s,
                "x": bx, "y": by, "z": bz,
                "depth": depth,
            }
            state["leaves"].append(leaf)
            state["count"] += 1
            node["children"].append({"leaf": True, **leaf})
        elif mat_s == "0":
            # 纯 void 叶（material=0 无 fill）→ 透明占位 leaf（规则4，计入 count，
            # detailViable 总览兜底；前端透明材质渲染、不参与取景 bbox）
            void_leaf = {
                "path": path,
                "u": str(u),
                "cellNum": cell.get("cellNum"),
                "mat": "0",
                "x": bx, "y": by, "z": bz,
                "depth": depth,
                "void": True,
            }
            state["leaves"].append(void_leaf)
            state["count"] += 1
            node["children"].append({"leaf": True, **void_leaf})
        # 其余（material 空串且无 fill）跳过
    return node if node["children"] else None
