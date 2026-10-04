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
    """lat=1 六面体：单 RPP/BOX 宏体，或 4/6 张平面。

    2026 修正（对齐 C810 3-29「The hexahedra **need not be rectangular** … opposite sides
    have to be identical and parallel」）：不再要求 PX/PY/PZ **按轴**成对——只要**按书写顺序**
    (1,2)/(3,4)/(5,6) 三对反向平行、三个方向线性无关、半空间交集非空（凸）即可，
    斜的平行六面体是**合法** MCNP 格元。
    """
    if len(expr_ints) == 1:
        num, _sign = expr_ints[0]
        kw, _p = surfaces.get(num, (None, []))
        if kw in ("RPP", "BOX"):
            return True, ""
        return False, f"lat=1 单宏体必须是 RPP/BOX 六面体宏（曲面 {num} 为 {kw or '未定义'}）"
    if len(expr_ints) not in (4, 6):
        return False, (f"lat=1 六面体需 1 个 RPP/BOX 宏体、或 4/6 张平面（成对反向平行）；"
                       f"当前 {len(expr_ints)} 张面")
    facets, err = _cuboid_facets(expr_ints, surfaces)
    if facets is None:
        return False, err or "平面解析失败"
    pairs, perr = _cuboid_pairs(facets)
    if pairs is None:
        return False, perr or "平面不成对"
    # 4 张面（2D 延伸）：第三对无界 → 校验时用哑元 z 对（±1）只验证面内结构
    _para, msg = _parallelepiped(pairs, -1.0, 1.0)
    if _para is None:
        return False, msg or "六张面的半空间交集为空（面卡常数/正负号写反）"
    return True, ""


def _rhp_vectors_ok(h: list, r1: list, r2=None, r3=None) -> tuple:
    """RHP/HEX 三个面心矢量 → 是否构成**正/非正**六棱柱（C810 3-21）。

    放宽点（2026）：不再硬要求 R1/R2/R3 两两 60°——MCNP 允许**非正**六棱柱（三对面相同且平行，
    C810 3-29）⇒ 只要求：各自 ⊥H、非零、两两不平行，且六张 ±r_k 面（距离 |r_k|）的交
    是**非退化凸六边形**（用统一的 `_hex_polygon` + 半空间可行性判定）。
    """
    hn = math.sqrt(sum(t * t for t in h))
    if hn <= 1e-12:
        return False, "RHP/HEX 高度向量 H 长度必须 >0（当前 0）"
    for name, r in (("R1", r1), ("R2", r2), ("R3", r3)):
        if r is None:
            continue
        rn = math.sqrt(sum(t * t for t in r))
        if rn <= 1e-12:
            return False, f"RHP/HEX {name} 长度必须 >0（当前 0）"
        if abs(sum(h[i] * r[i] for i in range(3))) / (hn * rn) > 1e-6:
            return False, f"RHP/HEX 的 {name} 必须垂直 H"
    vecs = [r for r in (r1, r2, r3) if r is not None]
    if len(vecs) >= 2:
        for i in range(len(vecs)):
            for j in range(i + 1, len(vecs)):
                a = vecs[i]
                b = vecs[j]
                na = math.sqrt(sum(t * t for t in a))
                nb = math.sqrt(sum(t * t for t in b))
                cosv = sum(a[k] * b[k] for k in range(3)) / (na * nb)
                if abs(abs(cosv) - 1.0) < 1e-9:
                    return False, f"RHP/HEX 的 R{i + 1}/R{j + 1} 平行（六棱柱对面退化）"
    if len(vecs) == 2:
        # 只给 R1/R2：MCNP 按"绕轴 +60°"推断 R3 ⇒ 仅**正六棱柱**成立；非正六棱柱须显式给 R3。
        a12 = _rhp_angle_deg(r1, vecs[1])
        if abs(a12 - 60.0) > 0.5:
            return False, (f"RHP/HEX 只给 R1/R2 时夹角须 60°（MCNP 按 +60° 推断 R3）；"
                           f"当前 {a12:.1f}°。非正六棱柱请显式给出 R3（15 参）")
    # 六张面 ±r_k（距离 |r_k|）→ 凸六边形判定（与 lat=2 平面写法同一条 seam）
    if len(vecs) == 3:
        # 平铺条件：a1 = 2·R1、a2 = 2·R2 ⇒ R3 必须 = (a2 − a1)/2（方向与长度都锁死）
        t = (2.0 * vecs[1][0] - 2.0 * vecs[0][0], 2.0 * vecs[1][1] - 2.0 * vecs[0][1])
        tn = math.hypot(t[0], t[1])
        if tn <= 1e-12:
            return False, "RHP/HEX 的 R1 与 R2 共线（无法定出格矢）"
        r3n = math.sqrt(sum(x * x for x in vecs[2]))
        cos3 = abs((vecs[2][0] * t[0] + vecs[2][1] * t[1]) / (r3n * tn))
        if cos3 < 0.999 or abs(2.0 * r3n - tn) > 1e-6 * max(1.0, tn):
            return False, (f"RHP/HEX 的 R3 必须 = (a2−a1)/2 = ({t[0] / 2:.6g}, {t[1] / 2:.6g})"
                           f"（C810 3-29：第 5 面之外是 (-1,1,0)，否则格阵无法平铺）")
        facets = []
        for k, r in enumerate(vecs):
            rn = math.sqrt(sum(t * t for t in r))
            facets.append((0, r[0] / rn, r[1] / rn, rn))
            facets.append((0, -r[0] / rn, -r[1] / rn, rn))
        verts, center, apo = _hex_polygon(facets)
        if verts is None or not apo or apo <= 1e-12:
            return False, "RHP/HEX 三对面心矢量无法构成六棱柱（平行/退化）"
        if _hex_empty_intersection(facets, center):
            return False, "RHP/HEX 六张面的半空间交集为空（面心矢量方向/长度错）"
    return True, ""


def _validate_rhp_params(params: list) -> tuple:
    """RHP/HEX 单宏体参数合法性校验（安全门：参数数/|H|/|R1|/⊥H/凸六棱柱）。"""
    if len(params) not in (9, 12, 15, 18):
        return False, (f"RHP/HEX 宏体合法参数数为 9/12/15/18（V+H+R1[+R2[+R3]]）；"
                       f"当前 {len(params)}")
    nums = _nums_of(params)
    if len(nums) < 9:
        return False, "RHP/HEX 宏体数值参数不足（需 V(3)+H(3)+R1(3)）"
    h = nums[3:6]
    r1 = nums[6:9]
    r2 = nums[9:12] if len(nums) >= 12 else None
    r3 = nums[12:15] if len(nums) >= 15 else None
    return _rhp_vectors_ok(h, r1, r2, r3)


def _rhp_angle_deg(a: list, b: list) -> float:
    """两向量夹角（度）。任一零向量 → 0.0（由调用方先验 |R|>0）。"""
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    cosv = sum(a[i] * b[i] for i in range(3)) / (na * nb)
    cosv = max(-1.0, min(1.0, cosv))
    return math.degrees(math.acos(cosv))


def _validate_lat2(expr_ints: list, surfaces: dict) -> tuple:
    """lat=2 六棱柱：单 RHP/HEX 宏体，或 6 个竖直侧平面（P/PX/PY）+ 可选 2 个 PZ 顶底。

    对齐 C810 3-29 / MCNP6.3 p.295-296 的修正：
      - 侧平面接受 **P/PX/PY**（官方样例 u233 cell 19 就是 2 PX + 4 P；旧实现只认 P）；
      - 顶底 PZ **可以不给**（手册：棱柱可沿轴向无限；旧实现强制 8 个曲面）；
      - 侧面两两互反（第 2 面之外 = (-1,0,0)）且第 1/第 3 面相邻 60°——**曲面顺序即格阵基矢**，
        顺序错 ⇒ MCNP 里相邻格元与用户预期不符（预览也会整阵转 30°）；
      - 顶底必须是**最后两个列出**的曲面；
      - 半空间交集非空：面常数符号写反 ⇒ 六个半空间交为空集（MCNP 里该格元不存在），
        旧实现只看"法向均布 60°"，空集卡照样通过，而 3D 预览的 AABB 看不出差别。
    """
    if len(expr_ints) == 1:
        num, _sign = expr_ints[0]
        kw, params = surfaces.get(num, (None, []))
        if kw in ("RHP", "HEX"):
            return _validate_rhp_params(params)
        return False, f"lat=2 单宏体必须是 RHP/HEX 六棱柱宏（曲面 {num} 为 {kw or '未定义'}）"
    resolved, err = _resolve_surfaces(expr_ints, surfaces)
    if err:
        return False, err
    sides, pz = [], []      # [(书写序号, 曲面号, 正负号)]
    for idx, (num, sign, kw, _params) in enumerate(resolved):
        if kw == "PZ":
            pz.append((idx, num, sign))
        elif kw in ("P", "PX", "PY"):
            sides.append((idx, num, sign))
        else:
            return False, (f"曲面 {num} 类型 {kw} 不是六棱柱平面"
                           f"（需 P/PX/PY 竖直侧平面、或 PZ 顶底平面）")
    if len(sides) != 6:
        return False, (f"lat=2 六棱柱需 6 个竖直侧平面（P/PX/PY），当前 {len(sides)} 个"
                       f"（总曲面数 {len(expr_ints)}）")
    if len(pz) not in (0, 2):
        return False, f"lat=2 顶底为 0 个或 2 个 PZ（当前 {len(pz)} 个）"
    if len(pz) == 2:
        if pz[0][1] == pz[1][1]:
            return False, "PZ 顶底平面不能是同一曲面（退化零高）"
        if pz[0][2] == pz[1][2]:
            return False, "PZ 顶底平面必须一正一负（一面从下方、一面从上方约束）"
        if [i for i, _n, _s in pz] != [len(resolved) - 2, len(resolved) - 1]:
            return False, ("6 个侧面必须先列出、2 个 PZ 顶底必须是**最后两个**列出的曲面"
                           "（C810 3-29：曲面顺序决定格元索引的 (0,0,1)/(0,0,-1) 方向）")
    facets, ferr = _hex_side_facets([(n, s) for _i, n, s in sides], surfaces)
    if facets is None:
        return False, ferr or "侧平面解析失败"
    for k in (0, 2, 4):     # 1-2 / 3-4 / 5-6 必须互反
        dot = facets[k][1] * facets[k + 1][1] + facets[k][2] * facets[k + 1][2]
        if dot > -0.999:
            ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
            return False, (f"第 {k + 1} 与第 {k + 2} 个侧平面必须是一对反向平行面"
                           f"（C810 3-29：第 2 面之外是 (-1,0,0)）；当前法向夹角 {ang:.1f}°")
    ang13 = _angle_deg((facets[0][1], facets[0][2]), (facets[2][1], facets[2][2]))
    if min(abs(ang13), abs(ang13 - 180.0)) < 1e-6:
        return False, "第 1 与第 3 个侧平面平行（无法定出第二个格矢 a2）"
    # 三对面心距 + 格矢（C810 3-29：a1 = 第 1/2 面之间平移，a2 = 第 3/4 面之间平移）
    verts, center, apo = _hex_polygon(facets)
    if verts is None or not apo or apo <= 1e-12:
        return False, "侧平面存在平行/退化组合，无法构成六棱柱"
    cx, cy = center
    d = [abs(f[1] * cx + f[2] * cy - f[3]) for f in facets]
    for k in (0, 2):
        if min(d[k], d[k + 1]) <= 1e-12:
            return False, f"第 {k + 1}/{k + 2} 对面心距为零（退化棱柱）"
    a1 = (facets[0][1] * (d[0] + d[1]), facets[0][2] * (d[0] + d[1]))
    a2 = (facets[2][1] * (d[2] + d[3]), facets[2][2] * (d[2] + d[3]))
    if abs(a1[0] * a2[1] - a1[1] * a2[0]) <= 1e-12:
        return False, "第 1 与第 3 个侧平面方向线性相关（无法定出 2D 格阵）"
    # 配平条件（C810 3-29「must fill space exactly」）：第 5 面之外是 (-1,1,0) ⇒ 其外向法向
    # 必须 ∥ ±(a2 − a1)，且第 5/6 对面心距 = |a2−a1|/2。非正六边形同样受此约束，否则无法平铺。
    t = (a2[0] - a1[0], a2[1] - a1[1])
    tn = math.hypot(t[0], t[1])
    cos5 = abs((facets[4][1] * t[0] + facets[4][2] * t[1]) / tn)
    if cos5 < 0.999:
        ang = math.degrees(math.acos(max(-1.0, min(1.0, cos5))))
        return False, (f"第 5 个侧平面必须 ∥ (a2-a1)（C810 3-29：第 5 面之外是 (-1,1,0)，"
                       f"否则格阵无法平铺）；当前偏离 {ang:.1f}°")
    if abs(2.0 * d[4] - tn) > 1e-4 * max(1.0, tn):
        return False, (f"第 5/6 对面心距 {d[4]:.6g} ≠ |a2-a1|/2 = {tn / 2.0:.6g}"
                       f"（对面必须相同且平行）")
    if _hex_empty_intersection(facets, center):
        return False, ("6 个侧平面的半空间交集为空（面卡常数/正负号写反 ⇒ MCNP 里该格元不存在；"
                       "应为 `-侧平面` 且 P 卡常数 D = 面心距 × |n|）")
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

    MCNP P 卡系数形 A B C D 定义 Ax+By+Cz−D = 0 → n·p = +D；
    三点形 (p1 p2 p3) → n = (p2-p1)×(p3-p1), D = n·p1。
    负侧（-surf）= n·p < D。参数不足返回 (None, None)。
    """
    nums = _nums_of(params)
    if len(nums) >= 4:  # 系数形 A B C D → n·p = +D（MCNP Ax+By+Cz−D=0）
        return (nums[0], nums[1], nums[2]), nums[3]
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
    """RHP/HEX 宏体：六棱柱 AABB（C810 p.3-21 语义，与 `quadric.rhp_hex_vertices` 同源）。

    **r/s/t 是"面心矢量"（边心距）**，六个侧顶点由相邻两面求交得出；轴向范围取 V±H/2。

    ⚠ 2026-09-20 修正：旧实现把 ``±v1, ±v2, ±(v1-v2)`` 直接当"六个侧顶点"—— 那六个点其实是
    **面心**（半径 = 边心距），于是 AABB 的 y 跨度少 25%、极值方向错 30°（x 跨度恰好相同，
    所以格距 px 一直是对的，问题只在 y 与"谁是最外点"）。统一到唯一实现后与前端生成侧一致。

    参数数支持（项4，2026-08-24）：
      9 参（V+H+R1）→ R2 按 MCNP 语义绕 H 转 60° 推断（Rodrigues），R3 同法再转 60°；
      12/15 参原样读取（R2/R3 显式给出）。
    """
    if len(params) < 9:
        return None
    try:
        cx, cy, cz = [float(p) for p in params[:3]]
        h = [float(p) for p in params[3:6]]
        v1 = [float(p) for p in params[6:9]]
    except (ValueError, TypeError):
        return None
    hnorm = math.sqrt(h[0] * h[0] + h[1] * h[1] + h[2] * h[2])
    if hnorm <= 1e-12:
        return None
    axis = [h[0] / hnorm, h[1] / hnorm, h[2] / hnorm]

    def _explicit(idx):
        if len(params) < idx + 3:
            return None
        try:
            return [float(p) for p in params[idx:idx + 3]]
        except (ValueError, TypeError):
            return None

    v2 = _explicit(9) or _rotate_about(v1, axis, math.pi / 3.0)
    v3 = _explicit(12) or _rotate_about(v2, axis, math.pi / 3.0)
    try:                                          # 冻结包（app/ 在 sys.path 上）
        from quadric import rhp_hex_vertices
    except ImportError:                           # 测试/包导入
        from app.quadric import rhp_hex_vertices
    verts = rhp_hex_vertices(v1, v2, v3)
    xs = [cx + w[0] for w in verts]
    ys = [cy + w[1] for w in verts]
    zs = [cz + w[2] for w in verts]
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


# ── lat=2 格阵基矢（MCNP 权威：侧面**书写顺序**决定基矢，不写死 +x）────
#
# 权威 = C810 3-29 / MCNP6.3 p.295-296：LAT=2 时「on the opposite side of the first
# surface listed is element (1,0,0), opposite the second listed surface is (-1,0,0),
# then (0,1,0), (0,-1,0), (-1,1,0), (1,-1,0). These last two surfaces must be the
# base surfaces of the prism.」⇒
#   a1 = 2a·û₁（û₁ = 第 1 个列出侧面的**外向**单位法向）
#   a2 = 2a·û₂（û₂ = 第 3 个列出侧面的外向单位法向，与 û₁ 夹 60°）
#   pitch = |a1| = 2a = 相邻格元中心距（与朝向无关）⇒ 第 1、2 / 3、4 / 5、6 面必须互反。
# 官方样例 u233-comp-therm-001-case-6.i cell 19（`-30 29 -32 34 -33 35`）实测：
# a1=(1.45034, 0)、a2=(0.72517, 1.25603)、a=0.72517、pitch=1.45034。
# ⚠ 历史坑：把 a1 恒当 +x（`hex_center` 的 a1=(p,0)）只对「第 1 面法向 = ±x」的卡成立。
# 第 1 面法向不是 ±x 的**合法**卡（如面序 30°/90°/…）会整阵转 30°，且 pitch 取错轴
# （x 跨度 ≠ 中心距）——凡能拿到曲面卡的调用方都必须走 basis 路径。


def _angle_deg(v1, v2) -> float:
    """两向量夹角（度）；任一零向量 → 0.0。"""
    n1 = math.hypot(v1[0], v1[1])
    n2 = math.hypot(v2[0], v2[1])
    if n1 <= 1e-12 or n2 <= 1e-12:
        return 0.0
    c = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def _hex_side_facets(expr_ints, surfaces):
    """格元表达式 → (facets, err)。facets **保持书写顺序**，项 = (num, ux, uy, d)。

    (ux,uy) = 该侧面的外向单位法向，d = 面常数：格元内侧 = ``ux·x + uy·y < d``
    （MCNP 负侧语义：`-s` → 外向 = +n̂；`+s` → 外向 = −n̂）。
    接受 P/PX/PY（PX/PY 视为法向 (1,0)/(0,1) 特例——u233 cell 19 就是 2 PX + 4 P）；
    PZ 跳过（顶底由 `_hex_cap_bounds` 处理）。
    """
    out = []
    for num, sign in expr_ints:
        kw, params = surfaces.get(num, (None, []))
        if kw == "PZ":
            continue
        if kw == "P":
            n, D = _plane_const(params)
            if n is None:
                return None, f"曲面 {num} 的 P 卡参数不足（需 A B C D 或三点定义）"
        elif kw == "PX":
            v = _float0(params)
            if v is None:
                return None, f"曲面 {num} 的 PX 卡参数不足"
            n, D = (1.0, 0.0, 0.0), v
        elif kw == "PY":
            v = _float0(params)
            if v is None:
                return None, f"曲面 {num} 的 PY 卡参数不足"
            n, D = (0.0, 1.0, 0.0), v
        else:
            return None, f"曲面 {num} 类型 {kw or '未定义'} 不是六棱柱侧平面（需 P/PX/PY）"
        nx, ny, nz = n
        scale = max(1.0, abs(nx), abs(ny), abs(nz))
        if abs(nz) > 1e-9 * scale:
            return None, f"曲面 {num} 的平面法向不水平（C≠0），六棱柱侧平面必须竖直"
        norm = math.hypot(nx, ny)
        if norm <= 1e-12:
            return None, f"曲面 {num} 的平面法向在水平面内为零向量"
        ux, uy, d = nx / norm, ny / norm, D / norm
        if sign > 0:  # 正侧 n·p > D ⇔ 外向 (−n̂)·p < −d
            ux, uy, d = -ux, -uy, -d
        out.append((num, ux, uy, d))
    return out, ""


def _hex_cap_bounds(expr_ints, surfaces):
    """顶底 PZ → (zlo, zhi)（单侧/缺失 → 对应端 None）；PZ 参数非法 → None（整体失败）。"""
    lo = hi = None
    for num, sign in expr_ints:
        kw, params = surfaces.get(num, (None, []))
        if kw != "PZ":
            continue
        z0 = _float0(params)
        if z0 is None:
            return None
        if sign < 0:   # z < z0 → 上界
            hi = z0 if hi is None else min(hi, z0)
        else:          # z > z0 → 下界
            lo = z0 if lo is None else max(lo, z0)
    return (lo, hi)


def _hex_polygon(facets):
    """面表（≥3 项 (num,ux,uy,d)）→ (verts, center, apothem)；退化 → (None, None, None)。

    按方位角排序后相邻两面两两求交 ⇒ 凸多边形顶点；center = 顶点均值；
    apothem = 各面到 center 的平均距离（正六棱柱各面相等）。
    """
    fs = sorted(facets, key=lambda f: math.degrees(math.atan2(f[2], f[1])) % 360.0)
    m = len(fs)
    verts = []
    for i in range(m):
        _n1, ux1, uy1, d1 = fs[i]
        _n2, ux2, uy2, d2 = fs[(i + 1) % m]
        det = ux1 * uy2 - uy1 * ux2
        if abs(det) < 1e-12:
            return None, None, None
        verts.append(((d1 * uy2 - uy1 * d2) / det, (ux1 * d2 - d1 * ux2) / det))
    cx = sum(v[0] for v in verts) / m
    cy = sum(v[1] for v in verts) / m
    apo = sum(abs(ux * cx + uy * cy - d) for _n, ux, uy, d in fs) / m
    return verts, (cx, cy), apo


def _hex_empty_intersection(facets, center, rel_tol: float = 1e-6) -> bool:
    """6 个半空间的交是否为空（面常数符号/朝向写反 ⇒ 空集，MCNP 里该格元不存在）。"""
    for _n, ux, uy, d in facets:
        if ux * center[0] + uy * center[1] - d > rel_tol * max(1.0, abs(d)):
            return True
    return False


def _hex_facet_dirs(a1, a2) -> list:
    """六棱柱 6 个面的**外向**方向（未归一化）= {a1, a2, a2−a1, −a1, −a2, a1−a2}。"""
    return [(a1[0], a1[1]), (a2[0], a2[1]),
            (a2[0] - a1[0], a2[1] - a1[1]),
            (-a1[0], -a1[1]), (-a2[0], -a2[1]),
            (a1[0] - a2[0], a1[1] - a2[1])]


def _unit_dirs(dirs) -> list:
    """方向 → 单位向量（跳过零向量）。"""
    out = []
    for dx, dy in dirs:
        n = math.hypot(dx, dy)
        if n > 1e-12:
            out.append((dx / n, dy / n))
    return out


def hex_lattice_basis(surface_expr: str, lat: str,
                      surfaces_text: str = "", surfaces: dict | None = None) -> dict | None:
    """lat=2 格元 → MCNP 格阵基矢（由曲面**书写顺序**推出，见本节顶部权威说明）。

    返回 ``{a1, a2, pitch, apothem, center, basis_deg, a12_deg, facets, z, prism, source}``：
      - a1/a2 = 相邻格元中心偏移（= 2a·û₁ / 2a·û₂）；pitch = |a1|（中心距）
      - basis_deg = a1 方位角（度，供前端把程序化色块转到同一朝向）
      - facets = 6 个外向单位法向（供 `hex_half_extent` 反算 AABB）
      - prism = (V, H, R1) 形的 RHP 参数（可直接当裁剪实体/校验用）；z 无界 → None
      - source = "rhp"（单 RHP/HEX 宏体）| "planes"（6 个竖直侧平面）
    无法解析（非 6 面、退化、缺曲面卡、非竖直轴）→ None。
    """
    if str(lat) != "2" or not surface_expr or not str(surface_expr).strip():
        return None
    expr = str(surface_expr).strip()
    if any(ch in expr for ch in "#:()"):
        return None
    expr_ints = []
    for tok in expr.split():
        if not _INT_RE.match(tok):
            return None
        n = int(tok)
        expr_ints.append((abs(n), 1 if n >= 0 else -1))
    if surfaces is None:
        surfaces = _parse_surface_cards(surfaces_text)
    if not surfaces:
        return None

    # ── 单 RHP/HEX 宏体：R1/R2 就是面心矢量（MCNP 语义），a1 = 2R1、a2 = 2R2 ──
    if len(expr_ints) == 1:
        num = expr_ints[0][0]
        kw, params = surfaces.get(num, (None, []))
        if kw not in ("RHP", "HEX"):
            return None
        nums = _nums_of(params)
        if len(nums) < 9:
            return None
        v, h, r1 = nums[0:3], nums[3:6], nums[6:9]
        hnorm = math.sqrt(sum(t * t for t in h))
        if hnorm <= 1e-12 or math.hypot(r1[0], r1[1]) <= 1e-12:
            return None
        axis = [t / hnorm for t in h]
        if abs(axis[2]) < 1.0 - 1e-9:      # lat=2 棱柱轴须 ∥ z（本实现前置条件）
            return None
        r2 = nums[9:12] if len(nums) >= 12 else _rotate_about(r1, axis, math.pi / 3.0)
        a1 = (2.0 * r1[0], 2.0 * r1[1])
        a2 = (2.0 * r2[0], 2.0 * r2[1])
        zlo, zhi = sorted((v[2], v[2] + h[2]))
        return {"a1": a1, "a2": a2, "pitch": math.hypot(a1[0], a1[1]),
                "apothem": math.hypot(r1[0], r1[1]),
                "center": (v[0] + h[0] / 2.0, v[1] + h[1] / 2.0),
                "basis_deg": math.degrees(math.atan2(a1[1], a1[0])) % 360.0,
                "a12_deg": _angle_deg(a1, a2),
                "facets": _unit_dirs(_hex_facet_dirs(a1, a2)),
                "z": (zlo, zhi),
                "prism": ((v[0], v[1], zlo), (0.0, 0.0, zhi - zlo), (r1[0], r1[1], r1[2])),
                "source": "rhp"}

    # ── 6 个竖直侧平面：第 1/第 3 个的**外向**法向即 a1/a2 方向 ──
    facets, err = _hex_side_facets(expr_ints, surfaces)
    if facets is None or len(facets) != 6:
        return None
    verts, center, apo = _hex_polygon(facets)
    if verts is None or not apo or apo <= 1e-12:
        return None
    _n1, u1x, u1y, _d1 = facets[0]
    _n3, u3x, u3y, _d3 = facets[2]
    a1 = (2.0 * apo * u1x, 2.0 * apo * u1y)
    a2 = (2.0 * apo * u3x, 2.0 * apo * u3y)
    caps = _hex_cap_bounds(expr_ints, surfaces)
    if caps is None:
        return None
    zlo, zhi = caps
    # 三对面心矢量（RHP 语义：轴→面心，C810 3-21）。正六棱柱时 R2/R3 可由 R1 转 60° 推出
    # （9 参写法）；**非正六边形必须显式给 R2/R3**（15 参），否则合成出来的仍是正六棱柱。
    tri = [facets[0], facets[2], facets[4]]
    fvecs = []
    for f in tri:
        dk = abs(f[1] * center[0] + f[2] * center[1] - f[3])
        fvecs.append((dk * f[1], dk * f[2], 0.0))
    prism = None
    if zlo is not None and zhi is not None and zhi > zlo:
        prism = ((center[0], center[1], zlo), (0.0, 0.0, zhi - zlo), fvecs[0])
    return {"a1": a1, "a2": a2, "pitch": math.hypot(a1[0], a1[1]), "apothem": apo,
            "center": center,
            "basis_deg": math.degrees(math.atan2(a1[1], a1[0])) % 360.0,
            "a12_deg": _angle_deg(a1, a2),
            "facets": _unit_dirs(_hex_facet_dirs(a1, a2)),
            "facet_vecs": fvecs,
            "z": (zlo, zhi), "prism": prism, "source": "planes"}


def hex_position(basis: dict, col: float, row: float):
    """格位 (col,row) 相对格元中心的偏移 = col·a1 + row·a2（MCNP 权威映射）。"""
    a1, a2 = basis["a1"], basis["a2"]
    return (col * a1[0] + row * a2[0], col * a1[1] + row * a2[1])


def hex_prism_from_basis(basis: dict | None, zlo=None, zhi=None):
    """基矢 → RHP 裁剪实体 ``(V, H, R1)``；z 界优先取 ``basis["z"]``，缺失用 zlo/zhi。

    lat=2 格元常沿 z 无限（官方样例 u233 cell 19 就没有 PZ），此时格元的 z 跨度由
    extent / 嵌入窗口给出（`_resolved_extent`）——裁剪实体必须用那份 z 才是有限实体。
    z 仍无界/退化 → None（调用方回落 AABB 盒）。
    """
    if not basis:
        return None
    zl, zh = basis.get("z") or (None, None)
    if zl is None or zh is None:
        zl, zh = zlo, zhi
    try:
        zl, zh = float(zl), float(zh)
    except (TypeError, ValueError):
        return None
    if zh <= zl:
        return None
    cx, cy = basis.get("center") or (0.0, 0.0)
    a1 = basis.get("a1") or (0.0, 0.0)
    n = math.hypot(a1[0], a1[1])
    if n <= 1e-12:
        return None
    apo = float(basis.get("apothem") or (n / 2.0))
    v, h = (float(cx), float(cy), zl), (0.0, 0.0, zh - zl)
    r1 = (apo * a1[0] / n, apo * a1[1] / n, 0.0)
    # 非正六边形（R2/R3 不是 R1 转 60°/120°）→ 必须显式给三对面心矢量（15 参），
    # 否则 9 参写法会被 MCNP 按"绕轴 +60° 推断"建成正六棱柱（形状错）。
    fv = basis.get("facet_vecs")
    if fv and len(fv) >= 3:
        def _rot(p, deg):
            t = math.radians(deg)
            return (p[0] * math.cos(t) - p[1] * math.sin(t),
                    p[0] * math.sin(t) + p[1] * math.cos(t), 0.0)
        if (math.dist(fv[1], _rot(fv[0], 60.0)) < 1e-6 * max(1.0, apo)
                and math.dist(fv[2], _rot(fv[0], 120.0)) < 1e-6 * max(1.0, apo)):
            return (v, h, r1)
        return (v, h, r1, tuple(fv[1]), tuple(fv[2]))
    return (v, h, r1)


def hex_half_extent(pitch: float, basis: dict | None = None):
    """格距 pitch → 六棱柱 AABB 半宽 (hx, hy)。

    basis 给定 → 按**真实面法向**重构顶点取 AABB（x/y 不写死）；
    无 basis → 规范朝向（第 1 面法向 ∥ x）：hx = pitch/2（对边距）、hy = pitch/√3（外接半径）。
    """
    a = abs(float(pitch)) / 2.0
    if not basis:
        return a, a * 2.0 / math.sqrt(3.0)
    dirs = basis.get("facets") or _unit_dirs(_hex_facet_dirs(basis["a1"], basis["a2"]))
    if len(dirs) < 3:
        return a, a * 2.0 / math.sqrt(3.0)
    verts, center, _apo = _hex_polygon([(0, ux, uy, a) for ux, uy in dirs])
    if verts is None:
        return a, a * 2.0 / math.sqrt(3.0)
    return (max(abs(v[0] - center[0]) for v in verts),
            max(abs(v[1] - center[1]) for v in verts))


# ── lat=1 一般六面体（任意平行六面体，含斜的）基矢 + 自身形状实体 ──────
#
# 权威 = C810 3-29：LAT=1 的格元是**六面体**，「The hexahedra **need not be rectangular** …
# opposite sides have to be identical and parallel. A hexahedral lattice cell may be infinite
# in one or two of its dimensions.」⇒ 格元 = 三对相同且平行的面（任意平行六面体，斜的也合法）；
# 「beyond the first surface listed is (1,0,0)」⇒ a1 = 第 1/2 张面之间的距离 × 外向法向，同理 a2/a3。
# ⚠ MCNP 的 `BOX` 宏体只表达**直角**盒（C810：「Arbitrarily oriented **orthogonal** box (all
# corners are 90°)」）⇒ 非直角的平行六面体只能用 `ARB`（8 顶点 + 6 面码；worker 的
# `_convex_from_faces` 按体心定向，与面绕向无关）。

def _cuboid_facets(expr_ints, surfaces):
    """lat=1 格元表达式 → (facets, err)；facets 保持书写顺序，项 = (num, ux, uy, uz, d)。

    与 `_hex_side_facets` 的区别：三维法向（含 PZ）、不跳过任何面。
    半空间统一写成 ``u·p < d``（u = 外向单位法向；`-s` → u = +n̂，`+s` → u = −n̂）。
    """
    out = []
    for num, sign in expr_ints:
        kw, params = surfaces.get(num, (None, []))
        if kw == "PZ":
            v = _float0(params)
            if v is None:
                return None, f"曲面 {num} 的 PZ 卡参数不足"
            n, D = (0.0, 0.0, 1.0), v
        elif kw == "P":
            n, D = _plane_const(params)
            if n is None:
                return None, f"曲面 {num} 的 P 卡参数不足（需 A B C D 或三点定义）"
        elif kw == "PX":
            v = _float0(params)
            if v is None:
                return None, f"曲面 {num} 的 PX 卡参数不足"
            n, D = (1.0, 0.0, 0.0), v
        elif kw == "PY":
            v = _float0(params)
            if v is None:
                return None, f"曲面 {num} 的 PY 卡参数不足"
            n, D = (0.0, 1.0, 0.0), v
        else:
            return None, f"曲面 {num} 类型 {kw or '未定义'} 不是六面体平面（需 P/PX/PY/PZ）"
        nrm = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
        if nrm <= 1e-12:
            return None, f"曲面 {num} 的平面法向为零向量"
        u = (n[0] / nrm, n[1] / nrm, n[2] / nrm)
        d = D / nrm
        if sign > 0:
            u, d = (-u[0], -u[1], -u[2]), -d
        out.append((num, u[0], u[1], u[2], d))
    return out, ""


def _cuboid_pairs(facets):
    """6（或 4）张面 → 3（或 2）对，每对必须**反向平行**（C810 3-29：第 2 张之外是 (-1,0,0)）。"""
    if len(facets) == 6:
        idxs = [(0, 1), (2, 3), (4, 5)]
    elif len(facets) == 4:
        idxs = [(0, 1), (2, 3)]
    else:
        return None, f"lat=1 六面体需 4 或 6 张面（当前 {len(facets)} 张）"
    pairs = []
    for i, j in idxs:
        a, b = facets[i], facets[j]
        if a[0] == b[0]:
            return None, f"第 {i + 1}/{j + 1} 张面是同一曲面（退化）"
        dot = a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
        if dot > -0.999:
            ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
            return None, (f"第 {i + 1} 与第 {j + 2 - 1} 张面必须是一对反向平行面"
                          f"（C810 3-29：第 2 张之外是 (-1,0,0)）；当前夹角 {ang:.1f}°")
        pairs.append(((a[1], a[2], a[3], a[4]), (b[1], b[2], b[3], b[4])))
    return pairs, ""


def _solve3(rows, rhs):
    """3×3 线性方程组（Cramer）→ (x,y,z) 或 None（奇异）。"""
    (a1, a2, a3), (b1, b2, b3), (c1, c2, c3) = rows
    det = (a1 * (b2 * c3 - b3 * c2) - a2 * (b1 * c3 - b3 * c1) + a3 * (b1 * c2 - b2 * c1))
    if abs(det) < 1e-12:
        return None
    d1, d2, d3 = rhs
    x = (d1 * (b2 * c3 - b3 * c2) - a2 * (d2 * c3 - b3 * d3) + a3 * (d2 * c2 - b2 * d3)) / det
    y = (a1 * (d2 * c3 - b3 * d3) - d1 * (b1 * c3 - b3 * c1) + a3 * (b1 * d3 - d2 * c1)) / det
    z = (a1 * (b2 * d3 - d2 * c2) - a2 * (b1 * d3 - d2 * c1) + d1 * (b1 * c2 - b2 * c1)) / det
    return (x, y, z)


def _box_verts(center, e1, e2, e3):
    """中心 + 三棱向量 → 8 顶点（位标与 `_parallelepiped` 一致：idx=s1·4+s2·2+s3，
    idx=0 取 "+(e1+e2+e3)/2" 角、第 k 位翻转即 ±e_k 反号）。"""
    out = []
    for idx in range(8):
        s = [(idx >> 2) & 1, (idx >> 1) & 1, idx & 1]
        out.append(tuple(center[i] + (e1[i] * (2 * s[0] - 1) + e2[i] * (2 * s[1] - 1)
                                      + e3[i] * (2 * s[2] - 1)) / 2.0 for i in range(3)))
    return out


def _parallelepiped(pairs, zlo=None, zhi=None, tol: float = 1e-6):
    """面组（3 对，或 2 对 + z 界补第 3 对）→ 平行六面体数据；不合法 → (None, msg)。

    返回 ``{"verts": [8 顶点], "corner": V000, "a1","a2","a3", "center","clip_kind"}``：
    8 顶点按位标 idx = s1·4 + s2·2 + s3（s_k = 取该对的第 1 张/第 2 张面）排列；
    a_k = 第 k 对两张面之间的平移（= 距离 × 外向法向）= MCNP 的第 k 个格矢。
    """
    pts = list(pairs)
    if len(pts) == 2:
        if zlo is None or zhi is None or float(zhi) <= float(zlo):
            return None, "2D 六面体（4 张面）需有限 z 界才能合成裁剪实体"
        pts = pts + [((0.0, 0.0, 1.0, float(zhi)), (0.0, 0.0, 1.0, -float(zlo)))]
    # 每对：f0 = u·p < d0；f1 = (-u)·p < d1 ⇔ u·p > -d1 ⇒ 平面取 u·p = d0（s=0）/ u·p = -d1（s=1）
    rows = []
    for f0, f1 in pts:
        rows.append(((f0[0], f0[1], f0[2]), f0[3], -f1[3]))
    verts = []
    for idx in range(8):
        rhs = tuple(rows[k][2] if (idx >> (2 - k)) & 1 else rows[k][1] for k in range(3))
        p = _solve3([r[0] for r in rows], rhs)
        if p is None:
            return None, "三对面方向线性相关（退化六面体）"
        verts.append(p)
    # 可行性：每个顶点必须满足全部 6 个半空间（否则该卡在 MCNP 里是空集/非凸）
    for p in verts:
        for f0, f1 in pts:
            if f0[0] * p[0] + f0[1] * p[1] + f0[2] * p[2] - f0[3] > tol * max(1.0, abs(f0[3])):
                return None, "六张面的半空间交集为空（面卡常数/正负号写反）"
            if f1[0] * p[0] + f1[1] * p[1] + f1[2] * p[2] - f1[3] > tol * max(1.0, abs(f1[3])):
                return None, "六张面的半空间交集为空（面卡常数/正负号写反）"
    corner = verts[0]
    # MCNP 格矢 a_k = 第 k 对两张面之间的平移 = 外向法向 × 对边距（"第 1 张之外是 (1,0,0)"）；
    # 位标 idx 的第 (2-k) 位 = 1 表示取该对的第 2 张面 ⇒ a_k = verts[0] − verts[bit_k 翻转]。
    a1 = tuple(verts[0][i] - verts[4][i] for i in range(3))
    a2 = tuple(verts[0][i] - verts[2][i] for i in range(3))
    a3 = tuple(verts[0][i] - verts[1][i] for i in range(3))
    if min(math.dist(corner, v) for v in verts[1:]) <= 1e-9:
        return None, "六面体退化（顶点重合）"
    center = tuple(sum(v[i] for v in verts) / 8.0 for i in range(3))

    def _dot(p, q):
        return p[0] * q[0] + p[1] * q[1] + p[2] * q[2]

    def _norm(p):
        return math.sqrt(_dot(p, p))

    orth = all(abs(_dot(x, y)) <= 1e-6 * _norm(x) * _norm(y)
               for x, y in ((a1, a2), (a1, a3), (a2, a3)))
    # 盒角点：与 a1/a2/a3 同向的那组基 {op + Σ ε_k·a_k} 必须覆盖 8 个顶点 ⇒ op = verts[0] − a1 − a2 − a3
    op = tuple(verts[0][i] - a1[i] - a2[i] - a3[i] for i in range(3))
    return ({"verts": verts, "corner": op, "a1": a1, "a2": a2, "a3": a3,
             "center": center, "clip_kind": "box" if orth else "arb"}, "")


def _arb_codes():
    """平行六面体 8 顶点（位标 idx=s1·4+s2·2+s3）→ 6 个 ARB 面码（4 位整数，高位在前）。

    面 k/位 s 的 4 个顶点按另两位的 (0,0)→(1,0)→(1,1)→(0,1) 环绕序（平行四边形的合法环绕，
    不交叉）。worker 的 `_convex_from_faces` 按体心定向 ⇒ 无需关心绕向。
    """
    def vidx(s1, s2, s3):
        return s1 * 4 + s2 * 2 + s3

    codes = []
    for k in range(3):                      # 面序：对 1 的 s=0/1 → 对 2 → 对 3
        for s in (0, 1):
            others = [b for b in range(3) if b != k]
            order = []
            for b0, b1 in ((0, 0), (1, 0), (1, 1), (0, 1)):
                bits = [None, None, None]
                bits[k] = s
                bits[others[0]] = b0
                bits[others[1]] = b1
                order.append(vidx(*bits) + 1)          # 1 基角点号
            codes.append(int("".join(str(d) for d in order)))
    return codes


def cuboid_basis(surface_expr: str, lat: str, surfaces_text: str = "",
                 surfaces: dict | None = None, zlo=None, zhi=None) -> dict | None:
    """lat=1 格元 → 格阵基矢 + **格元自身形状**裁剪实体。

    返回 ``{"source", "a1","a2","a3"(=三个格矢), "center",
    "clip": (kind, payload), "ref_num"}``：
      - ``("ref", num)``：单 RPP/BOX 宏体 → 直接引用该曲面号当裁剪实体（形状即格元本身）；
      - ``("box", corner, e1, e2, e3)``：三对面正交（MCNP BOX 的全部要求）；
      - ``("arb", verts8, codes6)``：非直角平行六面体（MCNP BOX 不收，须 ARB）。
    无法解析 → None。
    """
    if str(lat) != "1" or not surface_expr or not str(surface_expr).strip():
        return None
    expr = str(surface_expr).strip()
    if any(ch in expr for ch in "#:()"):
        return None
    expr_ints = []
    for tok in expr.split():
        if not _INT_RE.match(tok):
            return None
        n = int(tok)
        expr_ints.append((abs(n), 1 if n >= 0 else -1))
    if surfaces is None:
        surfaces = _parse_surface_cards(surfaces_text)
    if not surfaces:
        return None
    if len(expr_ints) == 1:
        num = expr_ints[0][0]
        kw, params = surfaces.get(num, (None, []))
        if kw == "RPP":
            e = _rpp_extent(params)
            if not e:
                return None
            a1 = (e["x_max"] - e["x_min"], 0.0, 0.0)
            a2 = (0.0, e["y_max"] - e["y_min"], 0.0)
            a3 = (0.0, 0.0, e["z_max"] - e["z_min"])
            center = tuple((e[k + "_min"] + e[k + "_max"]) / 2.0 for k in "xyz")
            return {"source": "rpp", "a1": a1, "a2": a2, "a3": a3, "center": center,
                    "clip": ("ref", num), "ref_num": num, "axis_aligned": True,
                    "verts": _box_verts(center, a1, a2, a3)}
        if kw == "BOX":
            nums = _nums_of(params)
            if len(nums) < 9:
                return None
            corner = (nums[0], nums[1], nums[2])
            e1 = (nums[3], nums[4], nums[5])
            e2 = (nums[6], nums[7], nums[8])
            if len(nums) >= 12:
                e3 = (nums[9], nums[10], nums[11])
            else:                            # 9 参：v3 = v1×v2（C810 BOX 语义）
                e3 = (e1[1] * e2[2] - e1[2] * e2[1],
                      e1[2] * e2[0] - e1[0] * e2[2],
                      e1[0] * e2[1] - e1[1] * e2[0])
            center = tuple(corner[i] + (e1[i] + e2[i] + e3[i]) / 2.0 for i in range(3))
            # BOX 的面序（C810 3-21 / 仓库《曲面卡格式参考》§5.1）：面 1 = A1 终点、面 2 = A1 起点
            # ⇒ a1 = A1（格矢 = 第一对反向面之间的平移）✓，a2 = A2、a3 = A3。
            ua = []
            for v in (e1, e2, e3):
                n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
                u = tuple(t / n for t in v) if n > 1e-12 else (0.0, 0.0, 0.0)
                comps = [abs(t) for t in u]
                ua.append(comps.index(max(comps)) if max(comps) > 0.999999
                          and sum(1 for c in comps if c > 1e-6) == 1 else -1)
            return {"source": "box", "a1": e1, "a2": e2, "a3": e3, "center": center,
                    "clip": ("ref", num), "ref_num": num,
                    "axis_aligned": len(set(ua)) == 3 and -1 not in ua,
                    "verts": _box_verts(center, e1, e2, e3)}
        return None
    facets, _err = _cuboid_facets(expr_ints, surfaces)
    if facets is None:
        return None
    pairs, _perr = _cuboid_pairs(facets)
    if pairs is None:
        return None
    para, _msg = _parallelepiped(pairs, zlo, zhi)
    if para is None:
        return None
    verts = para["verts"]
    if para["clip_kind"] == "box":
        clip = ("box", para["corner"], para["a1"], para["a2"], para["a3"])
    else:
        clip = ("arb", verts, _arb_codes())
    zs = [v[2] for v in verts]

    def _u(v):
        n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
        return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)

    # 三对面方向是否**轴对齐**（任意正负号）：轴对齐卡保留历史口径（i→+x/j→+y/k→+z + RPP 裁剪），
    # 只有旋转/斜的卡才走 basis（MCNP 顺序 → 格矢方向）+ BOX/ARB 自身形状裁剪。
    axes = []
    for v in (para["a1"], para["a2"], para["a3"]):
        u = _u(v)
        comps = [abs(u[i]) for i in range(3)]
        if max(comps) < 0.999999 or sum(1 for c in comps if c > 1e-6) != 1:
            axes = []
            break
        axes.append(comps.index(max(comps)))
    axis_aligned = len(axes) == 3 and len(set(axes)) == 3
    return {"source": "planes", "a1": para["a1"], "a2": para["a2"], "a3": para["a3"],
            "center": para["center"], "clip": clip, "axis_aligned": axis_aligned,
            "verts": verts, "z": (min(zs), max(zs))}


def cuboid_extent(verts: list) -> dict | None:
    """平行六面体 8 顶点 → AABB（lat=1 斜格元的 extent；正交时与 `_plane_box_extent` 一致）。"""
    if not verts or len(verts) < 8:
        return None
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return {"x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys),
            "z_min": min(zs), "z_max": max(zs)}


def _hex_plane_extent(expr_ints, surfaces):
    """lat=2 6 侧 P/PX/PY（+ 可选 2 PZ）：侧平面两两求交得六边形顶点 → x/y AABB；PZ 给 z 界。

    PX/PY 作为法向 (1,0,0)/(0,1,0) 的特例处理（u233 cell 19 用 2 PX + 4 P 定六棱柱，
    原实现只认 P 导致 x/y extent 解析失败 → 3D 预览 STL 被裁成 1×1 小盒错乱）。
    ⚠ 本函数只求「面所在直线的多边形」⇒ 符号写反（半空间交为空）时 AABB 仍看着正常，
    故合法性判定必须另走 `validate_lattice_surfaces`（其中有空交集检查）。
    """
    facets, _err = _hex_side_facets(expr_ints, surfaces)
    if facets is None or len(facets) < 3:
        return None
    verts, _c, _a = _hex_polygon(facets)
    if verts is None:
        return None
    caps = _hex_cap_bounds(expr_ints, surfaces)
    if caps is None:
        return None
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    return {"x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys),
            "z_min": caps[0], "z_max": caps[1]}


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


def _hex_pitch(px: float, py: float) -> tuple:
    """hex（lat=2）格距**兜底**（仅在拿不到曲面卡/基矢时使用）：返回 (p, p)。

    格距 = 六棱柱中心距 = 2a = AABB 两个跨度中较**小**者（六棱柱 AABB 的最小跨度
    必出现在垂直于某条格矢的方向上，其值即 2a；另一跨度 ≥ 2a）。
    ⚠ 历史坑（TD-28 前身）：旧实现恒取 **x 跨度**，只对「第 1 面法向 = ±x」的卡成立；
    面序 30°/90°/… 的合法卡 x 跨度 = 外接半径·2 = 1.1547p ⇒ 格距被撑大 15.47%、
    格元间出现缝隙。**权威路径是 `hex_lattice_basis()["pitch"]`**，本函数只兜底。
    """
    cands = [s for s in (px, py) if s and s > 0]
    p = min(cands) if cands else 1.0
    return p, p


def _half_span(extent: dict | None, axis: str, fallback: float = 1.0) -> float:
    """extent 该轴的半跨度；无界/缺失 → fallback/2（格元盒半宽语义）。"""
    if extent:
        lo = extent.get(axis + "_min")
        hi = extent.get(axis + "_max")
        if lo is not None and hi is not None:
            try:
                span = float(hi) - float(lo)
                if span > 0:
                    return span / 2.0
            except (TypeError, ValueError):
                pass
    return fallback / 2.0


def _lattice_pitch(extent: dict | None, lat: str, basis: dict | None = None):
    """extent → 每轴 pitch (px, py, pz)。

    rect：x/y/z 跨度（无界默认 1）。
    hex：**权威 = basis["pitch"]（中心距，与朝向无关）**；无 basis 才回落
    `_hex_pitch`（AABB 最小跨度）。pz 恒取 z 跨度。
    """
    px = _extent_span(extent, "x", 1.0)
    py = _extent_span(extent, "y", 1.0)
    pz = _extent_span(extent, "z", 1.0)
    if str(lat) == "2":
        p = float((basis or {}).get("pitch") or 0.0)
        if p > 0:
            a2 = math.hypot(*((basis or {}).get("a2") or (0.0, 0.0)))
            return p, (a2 if a2 > 0 else p), pz
        px, py = _hex_pitch(px, py)
    return px, py, pz


def _cell_pz_bounds(surface_expr: str, surfaces_text: str = "", surfaces=None) -> tuple:
    """扫描栅元曲面表达式中的 PZ 约束 → (z_lower, z_upper)；无 PZ 返回 (None, None)。

    -surf(PZ z0) → z < z0（上界）；+surf(PZ z0) → z > z0（下界）。
    surfaces 预解析曲面卡（dict）可传入避免重复 parse（性能：单卡多次扫描时
    不必每次全量 _parse_surface_cards 整段曲面卡文本）。
    """
    if not surface_expr or not str(surface_expr).strip():
        return None, None
    expr = str(surface_expr).strip()
    if any(ch in expr for ch in "#:()"):
        return None, None
    if surfaces is None:
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


def _build_axial_segments(u, cells, surf_text, surfaces=None):
    """识别 universe u 的轴向 stack：单-fill 子 universe + PZ 界定的 z 段列表。

    轴向 stack（如 BEAVRS 燃料柱 u=116/124/131/…：25 个 cell 各 fill 一个
    径向 pin universe，每 cell 由一对 PZ 平面界定，z 从 0 到 460 分 25 段）。
    每段 = {zmin, zmax, fill_u, cellNum}。非单-fill cell（径向层/格阵 cell）跳过；
    段数 < 2 → 返回 None（普通径向 pin universe 不是轴向 stack）。
    OWEN mcnp.ts buildAxialStack 移植（MIT, BelvoirDynamics 2026）。
    """
    segs = []
    for cell in cells or []:
        fg = cell.get("fill_grid")
        if fg is not None and fg.kind == "lattice":
            continue  # 格阵 cell 不是轴向段
        if fg is not None and fg.kind == "translated":
            fill_u = fg.cells[0].u if fg.cells else ""
        else:
            fill_u = str(cell.get("fill") or "").strip()
        if not fill_u or fill_u == "0":
            continue
        mat_s = str(cell.get("material") or "").strip()
        # 轴向段 cell：material=0（装配容器）+ 单-fill。material≠0 的径向层不是轴向段
        if mat_s not in ("0", ""):
            continue
        lo, hi = _cell_pz_bounds(cell.get("surface_expr", ""), surf_text, surfaces)
        if lo is None or hi is None or not (hi > lo):
            continue
        segs.append({"zmin": lo, "zmax": hi, "fill_u": fill_u, "cellNum": cell.get("cellNum")})
    if len(segs) < 2:
        return None
    segs.sort(key=lambda s: s["zmin"])
    return segs


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


def _range_start(token) -> int:
    """FILL 范围 token ``"a:b"`` → **起始索引 a**（MCNP 索引的绝对值）；非法/缺失 → 0。"""
    s = str(token or "").strip()
    if not _RANGE_RE.match(s):
        return 0
    try:
        return int(s.split(":", 1)[0])
    except (ValueError, IndexError):
        return 0


def expand_positions(fg: "FillGrid | None", extent: dict | None,
                     trcl_rotation_deg: float = 0,
                     max_positions: int = MAX_EXPANDED_ENTRIES,
                     z_origin: float = 0.0,
                     basis: dict | None = None) -> list | None:
    """格阵 → 每格位中心 [{idx,u,x,y,z,dx,dy,dz}, ...]。

    - rect 中心 = ((i-(nx-1)/2)*px, (j-(ny-1)/2)*py, (k-(nz-1)/2)*pz)（pitch 来自 extent）
    - hex 用矩形盒模型 + 格位中心；**给了 basis（`hex_lattice_basis`）→
      中心 = col·a1 + row·a2（MCNP 权威：a1 方位由卡的曲面顺序决定）**；
      无 basis 才回落规范朝向 hex_center（a1∥x，历史行为）
    - TRCL 绕 Z 旋转（trcl_rotation_deg 度）
    - 格位总数超 max_positions → 返回 None（实例上限拒绝）
    与前端 lattice.ts hexGrid/hexCenter 键名/公式逐字一致（规范朝向下）。
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
    if lat == "2" and basis:
        px = float(basis.get("pitch") or 0.0) or _extent_span(extent, "x", 1.0)
        py = px
    else:
        px = _extent_span(extent, "x", 1.0)
        py = _extent_span(extent, "y", 1.0)
    pz = _extent_span(extent, "z", 1.0)
    if lat == "2" and not basis:
        # 无基矢兜底：格距 = AABB 最小跨度（见 _hex_pitch 说明）
        px, py = _hex_pitch(px, py)
    # z 原点（z_origin）只由根格阵传送（容器 z 中点）；嵌套格阵 z_origin=0（相对父格位），
    # 避免在父格位绝对 z 上再叠加自身 z 中点（BEAVRS 组件 pin 被推成 z=460 的 bug）。
    theta = math.radians(float(trcl_rotation_deg or 0))
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    # 索引口径（MCNP 权威）：**格元索引 = 相对 (0,0,0) 格元的位置偏移**（C810 3-30：
    # "The indices of each lattice element are determined by its location with respect to the
    # (0,0,0) element. The range of the indices depends on where in the lattice the (0,0,0)
    # element is located. For example, −5:5, 0:10, and −10:0 all define a range of 11 elements."）
    # ⇒ 元素位置 = (range 起始 + 数组下标) × 格矢，**不做"按数组中心居中"**：
    #   −8:8 与 0:16 都合法，但 0:16 的格阵整体偏在一侧（旧实现把整个数组强行居中 ⇒
    #   非对称 range 相对外壳/其它几何平移半个数组，与 MCNP 不一致）。
    _rng = list(fg.range_ or [])
    st0 = _range_start(_rng[0]) if len(_rng) > 0 else 0
    st1 = _range_start(_rng[1]) if len(_rng) > 1 else 0
    st2 = _range_start(_rng[2]) if len(_rng) > 2 else 0
    out = []
    cells = fg.cells
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                idx = i + nx * (j + ny * k)  # 行主序 i 最快（rectGrid idxOf 一致）
                entry = cells[idx] if idx < len(cells) else FillEntry()
                if lat == "2":
                    # 索引 = range 起始 + 数组下标（MCNP 绝对值；不再按数组中心居中）
                    ci, cj = float(st0 + i), float(st1 + j)
                    if basis:
                        hx, hy = hex_position(basis, ci, cj)
                    else:
                        hx, hy = hex_center(ci, cj, px)
                    cz = z_origin + (st2 + k) * pz
                else:
                    # lat=1：给了 basis（`cuboid_basis`）→ 位置 = col·a1 + row·a2 + layer·a3，
                    # a_k = 第 k 对反向面之间的平移（C810 3-29「第 1 张面之外是 (1,0,0)」）
                    # ⇒ **方向跟曲面顺序与正负号走**，不再恒按 i→+x/j→+y/k→+z。
                    # 例：`20 0 50 -51 52 -53 lat=1`（`50 px -0.63` 在前、取 +50）⇒ a1 = (−1.26,0,0)。
                    ci, cj, ck = float(st0 + i), float(st1 + j), float(st2 + k)
                    if basis:
                        a1, a2, a3 = basis.get("a1"), basis.get("a2"), basis.get("a3")
                        if a1 and a2 and a3:
                            hx = ci * a1[0] + cj * a2[0] + ck * a3[0]
                            hy = ci * a1[1] + cj * a2[1] + ck * a3[1]
                            cz = z_origin + ci * a1[2] + cj * a2[2] + ck * a3[2]
                        else:
                            hx, hy = ci * px, cj * py
                            cz = z_origin + ck * pz
                    else:
                        hx = ci * px
                        hy = cj * py
                        cz = z_origin + ck * pz
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


def _cell_box_outside_container(bx, by, bz, hx, hy, hz, cb) -> bool:
    """格元盒 [bx±hx]×[by±hy]×[bz±hz] 是否**完全在**容器 cell 之外。

    方法级判断（依容器 cell 几何，非超壳结果适配）：格元盒最近点到容器几何中心
    距离 > 容器半径/边界 → 该格元完全在容器 cell 外 → 不产实体（如 BEAVRS 角位
    u=30 无限水格元盒完全在 cz 187.96 圆柱外）。cyl: 格元盒最近点到 (cx,cy) 距离
    ≤ r 才可能有堆芯部分；box: 格元盒与容器盒有重叠。cb 为空 → 不裁剪（兼容）。
    """
    if not cb:
        return False
    if cb.get("shape") == "cylinder":
        dx = max(0.0, abs(bx - cb.get("cx", 0.0)) - hx)
        dy = max(0.0, abs(by - cb.get("cy", 0.0)) - hy)
        if math.hypot(dx, dy) > cb.get("r", 0.0):
            return True
        zmin, zmax = cb.get("zmin"), cb.get("zmax")
        if zmin is not None and bz + hz < zmin:
            return True
        if zmax is not None and bz - hz > zmax:
            return True
        return False
    if cb.get("shape") == "box":
        xr = cb.get("x") or [0, 0]
        yr = cb.get("y") or [0, 0]
        zr = cb.get("z")
        if bx + hx < xr[0] or bx - hx > xr[1]:
            return True
        if by + hy < yr[0] or by - hy > yr[1]:
            return True
        if zr and (bz + hz < zr[0] or bz - hz > zr[1]):
            return True
        return False
    return False


def _lattice_cells_by_num(sub_by_u: dict) -> dict:
    """{cellNum: cell_info}（只收 fill_grid.kind == "lattice" 的格阵 cell）。

    供 `_expand_lattice` 取该格阵的 `basis`（`hex_lattice_basis` 产物，lat=2 时由调用方
    按真实曲面卡算好放入 cell_info）与 extent；无 basis → 回落规范朝向。
    """
    out = {}
    for _u, cells in (sub_by_u or {}).items():
        for c in cells or []:
            fg = c.get("fill_grid")
            if fg is None or getattr(fg, "kind", "") != "lattice":
                continue
            num = c.get("cellNum")
            if num is not None:
                out[num] = c
    return out


def compose_lattice_tree(outer_fg: "FillGrid | None", sub_by_u: dict,
                         extent: dict | None, trcl,
                         max_depth: int = MAX_LATTICE_DEPTH,
                         max_total: int = MAX_TOTAL_INSTANCES,
                         surf_text: str = "",
                         axial: bool = False,
                         detail: str = "layers",
                         container_bound: dict | None = None) -> dict:
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
        "surf_text": surf_text or "",
        "axial": bool(axial),
        "detail": str(detail or "layers"),
        "container_bound": container_bound,
        "surfaces": _parse_surface_cards(surf_text or ""),
        "axial_cache": {},
        "lat_cells": _lattice_cells_by_num(sub_by_u),
    }
    outer_num = _find_lattice_cell_num(outer_fg, sub_by_u)
    # 预计算全部 universe 的轴向 stack（一次性），供 _expand_universe 的 axial_cache 命中
    # TD-25（t8）：删除原此处的裸引用语句 `_parse_surface_cards  # noqa: 保持符号可见（未使用）`
    # —— 模块级表达式语句（无副作用）纯噪声，且该符号在同函数 :1247 已被真正调用。
    for _u, _cells in (sub_by_u or {}).items():
        state["axial_cache"].setdefault(
            str(_u), _build_axial_segments(str(_u), _cells, state["surf_text"], state["surfaces"]))
    root_ctx = {"base": (0.0, 0.0, 0.0), "depth": 1, "path": "",
                "trcl": float(trcl or 0),
                "z_origin": _extent_center(extent)[2]}
    tree = _expand_lattice(outer_fg, extent, outer_num, root_ctx, state)
    return {
        "status": state["status"],
        "tree": tree,
        "leafInstances": state["leaves"],
        "count": state["count"],
        "lattices": state["lattices"],
        "detailViable": state["count"] <= DETAIL_MAX_INSTANCES,
        "detail": str(detail or "layers"),
        "axial": bool(axial),
    }


def _expand_lattice(fg, extent, cell_num, ctx, state) -> list:
    """展开一个格阵：返回该格阵的 NESTED 节点列表；同时填 state.lattices/leaves。"""
    lat = str(fg.lat or "1")
    # basis（lat=2 时由 api_server 按真实曲面卡算好放进 cell_info）：
    # a1 方位由曲面**顺序**决定 → 格位排布与格距都不再写死 +x。
    basis = ((state.get("lat_cells") or {}).get(cell_num) or {}).get("basis") if lat == "2" else None
    positions = expand_positions(fg, extent, trcl_rotation_deg=ctx["trcl"],
                                  z_origin=ctx.get("z_origin", 0.0), basis=basis)
    if positions is None:
        state["status"] = "too_many"
        return []
    px, py, pz = _lattice_pitch(extent, lat, basis)
    # 容器剔除用的格元盒半宽：取 extent 的真实半跨度（hex 的 AABB 半宽 ≠ pitch/2：
    # 垂直格矢方向 = 外接半径 = pitch/√3，旧实现恒用 px/2 会偏小 13.4% 多剔边缘格元）。
    hx_half = _half_span(extent, "x", px)
    hy_half = _half_span(extent, "y", py)
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
        # 前端程序化色块（六棱柱）需按同一 a1 方位旋转，否则与真实格元差 30°
        "basisDeg": float(basis["basis_deg"]) if basis else 0.0,
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
        # 方法级：格元盒完全在容器 cell 外 → 该格元不属于容器 cell（堆芯），不产实体。
        # 依据"格元与容器 cell 几何相交"，非超壳结果适配；换任何外壳皆正确。
        cb = state.get("container_bound")
        if cb is not None and _cell_box_outside_container(
                abs_x, abs_y, abs_z, hx_half, hy_half, pz / 2.0, cb):
            continue
        idx = pos.get("idx", "")
        path = f"{ctx['path']}.{idx}" if ctx["path"] else str(idx)
        node = _expand_universe(u, (abs_x, abs_y, abs_z), depth, path, state)
        if node is not None:
            nodes.append(node)
    return nodes


def _expand_universe(u, base_xyz, depth, path, state) -> dict | None:
    """展开 universe u 的栅元 → 该格位的 NESTED 节点（无可渲染子节点 → None）。

    轴向折叠（state["axial"] is False，默认）：若 universe u 是轴向 stack
    （单-fill + PZ 界定，≥2 段），只展开跨度最大的"代表段"（OWEN placeEntry
    折叠逻辑：active fuel 段作整柱代表），逐段展开则由 axial=True 放开。
    非 stack 的径向 pin universe（material cell、无 PZ）不受影响。
    """
    cells = state["sub_by_u"].get(str(u))
    if not cells:
        return None
    bx, by, bz = base_xyz
    node = {"u": str(u), "x": bx, "y": by, "z": bz,
            "depth": depth, "path": path, "children": []}
    # 轴向折叠：默认只展开"代表段"。axial_cache 在 compose 入口预计算，避免每格位重解析。
    if not state.get("axial"):
        _cache = state.setdefault("axial_cache", {})
        segs = _cache.get(str(u))
        if segs is None:
            segs = _build_axial_segments(u, cells, state.get("surf_text", ""), state.get("surfaces"))
            _cache[str(u)] = segs
        if segs is not None:
            rep = segs[0]
            for sgm in segs:
                if (sgm["zmax"] - sgm["zmin"]) > (rep["zmax"] - rep["zmin"]):
                    rep = sgm
            sub_node = _expand_universe(rep["fill_u"], base_xyz, depth + 1, path, state)
            if sub_node is not None:
                node["children"].append(sub_node)
            return node if node["children"] else None
    # disc 降级（步骤2）：detail=="disc" 且该 universe 是"纯径向 pin"（全部 material
    # cell、无格阵/无单-fill）→ 只产 1 个代表叶（OWEN disc：主材料层单盘），而不是
    # 每径向层一个叶。用户"把每个 U 打包成只有外壳的 STL"的叶数层面实现。
    # 轴向 stack / 格阵 universe 不在此处理（由轴向折叠 + 各自递归负责）。
    if state.get("detail") == "disc":
        material_layers = [
            cell for cell in cells
            if str(cell.get("material") or "").strip() not in ("0", "")
            and cell.get("fill_grid") is None
            and str(cell.get("fill") or "").strip() == ""
        ]
        has_lattice_or_fill = any(
            cell.get("fill_grid") is not None or str(cell.get("fill") or "").strip() not in ("", "0")
            for cell in cells)
        if material_layers and not has_lattice_or_fill:
            # OWEN placePin disc：取"主导实心层"（第一个 material cell；disc 单盘）
            rep = material_layers[0]
            leaf = {
                "path": path,
                "u": str(u),
                "cellNum": rep.get("cellNum"),
                "mat": str(rep.get("material") or "").strip(),
                "x": bx, "y": by, "z": bz,
                "depth": depth,
                "disc": True,
            }
            state["leaves"].append(leaf)
            state["count"] += 1
            node["children"].append({"leaf": True, **leaf})
            return node if node["children"] else None
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
