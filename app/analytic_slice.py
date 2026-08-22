"""2D 解析切片：在切割平面上解析求值栅元布尔表达式，marching squares 提取轮廓。

用于含 GQ/SQ 曲面的栅元——预览 STL 是体素网格近似，切片轮廓带阶梯且旧实现
依赖预览 STL 会话；本模块直接复用 :mod:`voxel_csg` 的隐式曲面求值（含
``*TRn`` 变换），在切割平面上逐点判定栅元内外，再用 2D marching squares
提取轮廓多边形。**轮廓的位置精度只取决于解析求值本身，分辨率仅影响折线
平滑度**。

纯 numpy + stdlib，不依赖 FreeCAD / vtk；``_join_loops`` 复用
``stl_cross_section``（端点吸附 + 走环，开放链丢弃）。
"""

from __future__ import annotations

import numpy as np

try:
    from voxel_csg import (
        surface_fn, eval_cell_field, _surface_tr,
        _ast_surf_nums, cell_aabb, _clip_aabb_to_bound,
    )
except ImportError:  # 测试/直接 import app 包时在 app/ 下
    from app.voxel_csg import (
        surface_fn, eval_cell_field, _surface_tr,
        _ast_surf_nums, cell_aabb, _clip_aabb_to_bound,
    )
try:
    from stl_cross_section import _join_loops
except ImportError:
    from app.stl_cross_section import _join_loops

# ── 2D marching squares：16 种 case → 线段表 ─────────────────
# 顶点：0=(0,0) 1=(1,0) 2=(1,1) 3=(0,1)（栅元内 = bit 置位）
# 边：0=下(0-1) 1=右(1-2) 2=上(2-3) 3=左(3-0)
# 线段两端为边编号，取该边中点作为轮廓顶点。
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
_EDGE_MID = {
    0: (0.5, 0.0),
    1: (1.0, 0.5),
    2: (0.5, 1.0),
    3: (0.0, 0.5),
}


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


def _ms_segments(field, us, vs, p0, u_vec, v_vec):
    """二值场 → 轮廓线段列表（每段为两个 (x,y,z) 3 元组，供 _join_loops）。"""
    f = field.astype(np.int8)
    case = (
        f[:-1, :-1]
        | (f[1:, :-1] << 1)
        | (f[1:, 1:] << 2)
        | (f[:-1, 1:] << 3)
    )
    segs = []
    for i, j in np.argwhere(case != 0):
        c = int(case[i, j])
        du = us[i + 1] - us[i]
        dv = vs[j + 1] - vs[j]
        for e1, e2 in _MS_TABLE[c]:
            m1 = _EDGE_MID[e1]
            m2 = _EDGE_MID[e2]
            u1 = us[i] + m1[0] * du
            v1 = vs[j] + m1[1] * dv
            u2 = us[i] + m2[0] * du
            v2 = vs[j] + m2[1] * dv
            p1 = p0 + u1 * u_vec + v1 * v_vec
            p2 = p0 + u2 * u_vec + v2 * v_vec
            segs.append(((float(p1[0]), float(p1[1]), float(p1[2])),
                         (float(p2[0]), float(p2[1]), float(p2[2]))))
    return segs


def analytic_cross_section(ast, surfaces_by_num, tr_cards, plane,
                           bound: float = 500.0, res: int = 128) -> list:
    """切割平面解析切片 → 轮廓多边形列表（``[{x,y,z}...]``，兼容截面响应）。

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
        cell_aabb 无界/退化时的裁剪半边长（默认与预览一致 500）。
    res:
        平面网格分辨率（每轴点数；轮廓位置精度与 res 无关）。
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
        return eval_cell_field(ast, fns, x, y, z)

    # 求值盒：cell_aabb（带 TR 紧盒）裁剪到 bound；无界退化 → 全 bound 盒
    aabb = cell_aabb(ast, surfaces_by_num, bound, tr_cards)
    lo, hi = _clip_aabb_to_bound(aabb, bound)
    corners = np.array(
        [[x, y, z]
         for x in (lo[0], hi[0])
         for y in (lo[1], hi[1])
         for z in (lo[2], hi[2])],
        dtype=float,
    )
    uv = (corners - p0) @ np.stack([u_vec, v_vec], axis=1)
    umin, umax = float(uv[:, 0].min()), float(uv[:, 0].max())
    vmin, vmax = float(uv[:, 1].min()), float(uv[:, 1].max())
    span = max(umax - umin, vmax - vmin, 1e-9)
    margin = max(span * 0.02, span / max(res - 1, 1) * 0.5 + 1e-9)
    us = np.linspace(umin - margin, umax + margin, res)
    vs = np.linspace(vmin - margin, vmax + margin, res)
    U, V = np.meshgrid(us, vs, indexing="ij")
    X = p0[0] + U * u_vec[0] + V * v_vec[0]
    Y = p0[1] + U * u_vec[1] + V * v_vec[1]
    Z = p0[2] + U * u_vec[2] + V * v_vec[2]
    field = inside(X, Y, Z)
    if not field.any():
        return []

    segments = _ms_segments(field, us, vs, p0, u_vec, v_vec)
    loops = _join_loops(segments)
    out = []
    for loop in loops:
        pts = [{"x": p[0], "y": p[1], "z": p[2]} for p in loop]
        if len(pts) >= 3:
            out.append(pts)
    return out


__all__ = ["analytic_cross_section"]
