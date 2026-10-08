"""2D 解析切片：在切割平面上**按栅元定义求交**，marching squares 提取轮廓。

## 这个模块解决什么（2026-10-07 用户实测）
截面原来只有一条路：切 3D 预览那份**三角网格**（`stl_cross_section`）。网格切的是
"实体"，于是**切割平面与栅元边界面重合**时会把那张边界面当成"区域"：
用户卡 `石默/MCNP_Input.i` 在 Z=0（恰是卡里面 112 `PZ 0.000`）上，栅元 3/4 本以该面为界
（`-112` / `112`，严格说 z=0 两边都不含），网格却各切出一块半径 5 的**假盘**。

本模块走的是**定义**：在平面上逐点对栅元的布尔表达式求值（`voxel_csg` 的隐式曲面场，
含 ``*TRn``），再用 marching squares 提取"场内"的轮廓 ⇒ 平面与模型真正的交线。
栅元不在该平面上，结果就是空的 —— 不会再凭空造出几何。

## 精度（实测口径，别再说"与分辨率无关"而其实不是）
轮廓顶点由**二分法**沿栅格边收敛到真实的零水平集（默认 30 次 ⇒ 相对步长 ~1e-9），
所以**位置误差与 `res` 无关**；`res` 只决定两件事：
  1. **拓扑**：薄于一个栅格步长的特征可能整个被漏掉（步长 = 投影跨度 / (res-1)）；
  2. 折线的疏密。
2026-10-07 实测（旧实现在栅格边**中点**取顶点）：球 R=100 的 xy 截面最大半径误差
res=32/64/128/256 → 3.17 / 1.35 / 0.78 / 0.40 cm（随 res 变、且有半格系统偏差）；
改为二分法后同口径误差 ≤ 1e-6 cm。

纯 numpy + stdlib，不依赖 FreeCAD / vtk；``_join_loops`` 复用
``stl_cross_section``（端点吸附 + 走环，开放链丢弃）。
"""

from __future__ import annotations

import math

import numpy as np

try:
    from voxel_csg import (
        surface_fn, eval_cell_field3, _surface_tr,
        _ast_surf_nums, cell_aabb, _clip_aabb_to_bound,
    )
except ImportError:  # 测试/直接 import app 包时在 app/ 下
    from app.voxel_csg import (
        surface_fn, eval_cell_field3, _surface_tr,
        _ast_surf_nums, cell_aabb, _clip_aabb_to_bound,
    )
try:
    from stl_cross_section import _join_loops
except ImportError:
    from app.stl_cross_section import _join_loops

# ── 2D marching squares：16 种 case → 线段表 ─────────────────
# 顶点：0=(0,0) 1=(1,0) 2=(1,1) 3=(0,1)（栅元内 = bit 置位）
# 边：0=下(0-1) 1=右(1-2) 2=上(2-3) 3=左(3-0)
_MS_TABLE = (
    (),                # 0: 无
    ((0, 3),),         # 1: {0}
    ((0, 1),),         # 2: {1}
    ((1, 3),),         # 3: {0,1}
    ((1, 2),),         # 4: {2}
    ((0, 3), (1, 2)),  # 5: {0,2}（对角鞍点，任选配对，拓扑等价）
    ((0, 2),),         # 6: {1,2}
    ((2, 3),),         # 7: {0,1,2}
    ((2, 3),),         # 8: {3}
    ((0, 2),),         # 9: {0,3}
    ((0, 1), (2, 3)),  # 10: {1,3}（对角鞍点）
    ((1, 2),),         # 11: {0,1,3}
    ((1, 3),),         # 12: {2,3}（上边在内 → 跨左右边）
    ((0, 1),),         # 13: {0,2,3}
    ((0, 3),),         # 14: {1,2,3}
    (),                # 15: 全满
)

# 二分法迭代次数：30 ⇒ 把边长缩到 2^-30 ≈ 1e-9（远超网格分辨率所需的精度）
_BISECT_ITERS = 30


def _plane_basis(A: float, B: float, C: float, D: float):
    """平面 Ax+By+Cz=D → (nhat, p0, u_vec, v_vec)。"""
    n = np.array([A, B, C], dtype=float)
    nlen = float(np.linalg.norm(n))
    if nlen < 1e-15:
        n = np.array([0.0, 0.0, 1.0])
        nlen = 1.0
    nhat = n / nlen
    p0 = nhat * (D / nlen)
    ref = np.array([1.0, 0.0, 0.0]) if abs(nhat[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u_vec = np.cross(nhat, ref)
    u_vec = u_vec / np.linalg.norm(u_vec)
    v_vec = np.cross(nhat, u_vec)
    return nhat, p0, u_vec, v_vec


def model_bound(surfaces_by_num: dict, floor: float = 500.0) -> float:
    """从曲面参数推一个**够用**的求值盒半边长（替代写死的 500）。

    为什么不能写死：实测 GQ 球 R=600 时，旧实现把求值盒裁到 ±500 ⇒ 轮廓整个落在盒外
    ⇒ 解析分支返回空、静默回落网格切（解析精度白丢）。半边长必须随模型量级走。

    取「曲面参数绝对值最大值 × 1.3 + 100」，下限 floor；非有限参数（无界占位）忽略。
    """
    maxc = 0.0
    for s in (surfaces_by_num or {}).values():
        for v in (s.get("params") or []):
            try:
                f = abs(float(v))
            except (TypeError, ValueError):
                continue
            if math.isfinite(f) and f > maxc:
                maxc = f
    return max(floor, maxc * 1.3 + 100.0)


def _grid_axes(corners: np.ndarray, p0, u_vec, v_vec, res: int):
    """把求值盒的 8 个角投影到 (u,v)，返回**近似正方**栅格的 us / vs。

    旧实现两轴各取 res 个点 ⇒ 跨度不等时栅格被拉长（细特征更容易漏）。
    这里按"较长轴的步长"定步长，短轴点数随之减少，栅格近似正方。
    """
    uv = (corners - p0) @ np.stack([u_vec, v_vec], axis=1)
    umin, umax = float(uv[:, 0].min()), float(uv[:, 0].max())
    vmin, vmax = float(uv[:, 1].min()), float(uv[:, 1].max())
    span = max(umax - umin, vmax - vmin, 1e-9)
    h = span / max(int(res) - 1, 1)
    margin = max(span * 0.02, h)
    uspan = (umax - umin) + 2 * margin
    vspan = (vmax - vmin) + 2 * margin
    nu = int(min(max(round(uspan / h) + 1, 3), 4000))
    nv = int(min(max(round(vspan / h) + 1, 3), 4000))
    # 总点数上限：解析求值本身很快，但二分法要逐轮重算 → 给个天花板防病态输入
    if nu * nv > 400_000:
        k = math.sqrt(400_000.0 / (nu * nv))
        nu = max(3, int(nu * k))
        nv = max(3, int(nv * k))
    return (np.linspace(umin - margin, umax + margin, nu),
            np.linspace(vmin - margin, vmax + margin, nv))


def _edge_key(i: int, j: int, e: int):
    """网格单元 (i,j) 的第 e 条边 → 全局边标识（相邻单元共享同一条边/key）。"""
    if e == 0:
        return ("h", i, j)
    if e == 1:
        return ("v", i + 1, j)
    if e == 2:
        return ("h", i, j + 1)
    return ("v", i, j)


def _edge_endpoints(key, us, vs):
    """全局边 → 两端 (u,v) 与两端的内外标志。"""
    kind, a, b = key
    if kind == "h":          # 水平边：沿 u 方向，v 固定
        return (us[a], vs[b]), (us[a + 1], vs[b])
    return (us[a], vs[b]), (us[a], vs[b + 1])


def _crossings(keys, field, us, vs, p0, u_vec, v_vec, inside):
    """对所有"一内一外"的网格边求交点 —— 二分法收敛到真实零水平集。

    只用**布尔**内外判定（不需要标量场），所以对任意布尔表达式都成立。
    返回 {key: (u, v)}。
    """
    if not keys:
        return {}
    u0 = np.empty(len(keys)); v0 = np.empty(len(keys))
    u1 = np.empty(len(keys)); v1 = np.empty(len(keys))
    f0 = np.empty(len(keys), dtype=bool)
    for n, key in enumerate(keys):
        kind, a, b = key
        if kind == "h":
            (au, av), (bu, bv) = (us[a], vs[b]), (us[a + 1], vs[b])
            f0[n] = field[a, b]
        else:
            (au, av), (bu, bv) = (us[a], vs[b]), (us[a], vs[b + 1])
            f0[n] = field[a, b]
        u0[n], v0[n], u1[n], v1[n] = au, av, bu, bv

    def _pts(u, v):
        X = p0[0] + u * u_vec[0] + v * v_vec[0]
        Y = p0[1] + u * u_vec[1] + v * v_vec[1]
        Z = p0[2] + u * u_vec[2] + v * v_vec[2]
        return X, Y, Z

    for _ in range(_BISECT_ITERS):
        um = 0.5 * (u0 + u1)
        vm = 0.5 * (v0 + v1)
        fm = inside(*_pts(um, vm))
        same = (fm == f0)
        u0 = np.where(same, um, u0)
        v0 = np.where(same, vm, v0)
        u1 = np.where(same, u1, um)
        v1 = np.where(same, v1, vm)
    uc = 0.5 * (u0 + u1)
    vc = 0.5 * (v0 + v1)
    return {key: (float(uc[n]), float(vc[n])) for n, key in enumerate(keys)}


def _ms_segments(field, us, vs, p0, u_vec, v_vec, inside):
    """二值场 → 轮廓线段列表（顶点落在真实边界上，每段两个 (x,y,z) 3 元组）。"""
    f = field.astype(np.int8)
    case = (
        f[:-1, :-1]
        | (f[1:, :-1] << 1)
        | (f[1:, 1:] << 2)
        | (f[:-1, 1:] << 3)
    )
    mixed = np.argwhere(case != 0)
    if mixed.size == 0:
        return []

    # 1) 收集本帧用到的全部网格边（相邻单元共享 ⇒ 去重后只算一次）
    need: dict = {}
    for i, j in mixed:
        for e1, e2 in _MS_TABLE[int(case[i, j])]:
            for e in (e1, e2):
                need.setdefault(_edge_key(int(i), int(j), e), None)
    crossings = _crossings(list(need.keys()), field, us, vs, p0, u_vec, v_vec, inside)

    # 2) 逐单元出线段
    segs = []
    for i, j in mixed:
        i = int(i); j = int(j)
        for e1, e2 in _MS_TABLE[int(case[i, j])]:
            u1, v1 = crossings[_edge_key(i, j, e1)]
            u2, v2 = crossings[_edge_key(i, j, e2)]
            p1 = p0 + u1 * u_vec + v1 * v_vec
            p2 = p0 + u2 * u_vec + v2 * v_vec
            segs.append(((float(p1[0]), float(p1[1]), float(p1[2])),
                         (float(p2[0]), float(p2[1]), float(p2[2]))))
    return segs


def analytic_cross_section(ast, surfaces_by_num, tr_cards, plane,
                           bound: float | None = None, res: int = 128) -> list:
    """切割平面 ∩ 栅元定义 → 轮廓多边形列表（``[{x,y,z}...]``，兼容截面响应）。

    参数
    ----
    ast:
        ``_geometry_ast_to_json`` 产出的 JSON 列表（与体素求值同格式）。
    surfaces_by_num:
        ``{num: {"type","params","transform"}}``。
    tr_cards:
        ``parse_tr_cards`` 产出 dict（``*TRn`` 支持）。
    plane:
        ``{"A","B","C","D"}``。
    bound:
        求值盒半边长；``None`` ⇒ 由 ``model_bound(surfaces_by_num)`` 推（不写死）。
    res:
        较长轴的栅格点数（仅影响拓扑与折线密度；轮廓位置由二分法决定，与 res 无关）。

    返回空列表的含义是**权威的**："该平面与这个栅元没有内部交集"
    （例如切割平面恰好是该栅元的边界面）—— 调用方不得据此回落网格切，
    否则"切在边界面上的栅元"又会凭网格造出假几何。
    """
    A = float(plane.get("A", 0.0))
    B = float(plane.get("B", 0.0))
    C = float(plane.get("C", 0.0))
    D = float(plane.get("D", 0.0))
    nhat, p0, u_vec, v_vec = _plane_basis(A, B, C, D)

    nums = _ast_surf_nums(ast)
    fns = {}
    for num in nums:
        s = surfaces_by_num.get(num)
        if s is None:
            continue
        fns[num] = surface_fn(s["type"], s["params"], _surface_tr(s, tr_cards))
    if not fns:
        return []

    def inside(x, y, z):
        """严格内部判定（1 = 内部）：恰在曲面上的点不算在栅元内。

        为什么不用布尔版 `eval_cell_field`：它表达不了"点在曲面上"这一态，
        `unary neg` 会把 `f == 0` 归到负侧 ⇒ 切割平面恰是栅元边界面时（用户卡 Z=0
        正是面 112 `PZ 0.000`）会把该栅元整个算进来。见 `voxel_csg.eval_cell_field3`。
        """
        return eval_cell_field3(ast, fns, x, y, z) == 1

    # 求值盒：cell_aabb（带 TR 紧盒）裁剪到 bound；无界退化 → 全 bound 盒
    B_ = float(bound) if bound is not None else model_bound(surfaces_by_num)
    aabb = cell_aabb(ast, surfaces_by_num, B_, tr_cards)
    lo, hi = _clip_aabb_to_bound(aabb, B_)
    corners = np.array(
        [[x, y, z]
         for x in (lo[0], hi[0])
         for y in (lo[1], hi[1])
         for z in (lo[2], hi[2])],
        dtype=float,
    )
    us, vs = _grid_axes(corners, p0, u_vec, v_vec, res)
    U, V = np.meshgrid(us, vs, indexing="ij")
    X = p0[0] + U * u_vec[0] + V * v_vec[0]
    Y = p0[1] + U * u_vec[1] + V * v_vec[1]
    Z = p0[2] + U * u_vec[2] + V * v_vec[2]
    field = inside(X, Y, Z)
    if not field.any():
        return []

    segments = _ms_segments(field, us, vs, p0, u_vec, v_vec, inside)
    loops = _join_loops(segments)
    out = []
    for loop in loops:
        pts = [{"x": p[0], "y": p[1], "z": p[2]} for p in loop]
        if len(pts) >= 3:
            out.append(pts)
    return out


__all__ = ["analytic_cross_section", "model_bound"]
