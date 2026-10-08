"""按栅元**定义**判定"切割平面上这个栅元到底在不在"。

## 为什么需要它（2026-10-07 用户实测的"假几何"）
截面原来的几何来源是"切 3D 预览那份三角网格"。网格切的是**实体**，所以当切割平面
恰好与栅元的边界面重合时，它会把那张**边界面**当成"区域"返回：

    user deck `石墨/MCNP_Input.i`，Z=0（正是卡里面 112 `PZ 0.000`）
      栅元 3 `-104 113 110 -112`：网格切出一块半径 5 的盘（面积 π·5² = 78.507）
      栅元 4 `(112 …):(…)`     ：同上，另一块半径 5 的盘
      栅元 5 `112 -109 -115`   ：半径 0.5 的盘
    而按定义：z=0 处 `-112`（z<0）不成立、`112`（z>0）也不成立 ⇒ **三个栅元在该平面上都不存在**。

## 为什么不是"全部改走解析采样"
解析采样（`analytic_slice`）能给精确轮廓，但它的**拓扑**受采样步长限制：薄于步长的特征
会整个被漏掉（用户卡栅元 1 里有 1 cm 宽的长条、0.5 cm 宽的环带）。用采样替换网格，
等于用一个"静默丢几何"的风险换掉另一个 —— 不可接受。

## 采用的口径
* **几何仍取网格**（`stl_cross_section`）：薄特征由网格精确表达，不依赖采样步长；
* **"在不在"由定义判定**：用严格内部（三值场 `== 1`）判断该平面上是否存在**真内部**点；
* 判定为"不在" ⇒ 整块剔除（那是边界伪影）；判定为"在" ⇒ 保留网格给的全部环（含内孔环）。
* 采样盒优先取**网格环的投影范围**（网格给出的正是"东西在哪"），比栅元整盒紧得多；
  粗查（128）为"无"时再细查（320），防薄特征被粗网格漏掉 —— 这一步只在"网格有环但
  粗查说没内部点"时才有意义，代价可接受。
"""

from __future__ import annotations

import numpy as np

try:
    from voxel_csg import (
        surface_fn, eval_cell_field3, _surface_tr, _ast_surf_nums,
        cell_aabb, _clip_aabb_to_bound,
    )
except ImportError:  # 测试/直接 import app 包时在 app/ 下
    from app.voxel_csg import (
        surface_fn, eval_cell_field3, _surface_tr, _ast_surf_nums,
        cell_aabb, _clip_aabb_to_bound,
    )
try:
    from analytic_slice import _plane_basis, model_bound
except ImportError:
    from app.analytic_slice import _plane_basis, model_bound


def build_inside_fn(ast, surfaces_by_num, tr_cards=None):
    """栅元的**严格内部**判定函数 ``f(x, y, z) -> 布尔数组``（恰在曲面上 ⇒ 不在内部）。

    返回 None 表示该栅元引用的曲面缺失、无法判定（调用方应保持原行为）。
    """
    fns = {}
    for num in _ast_surf_nums(ast):
        s = surfaces_by_num.get(num)
        if s is None:
            continue
        fns[num] = surface_fn(s["type"], s["params"], _surface_tr(s, tr_cards or {}))
    if not fns:
        return None

    def inside(x, y, z):
        return eval_cell_field3(ast, fns, x, y, z) == 1

    return inside


def _uv_range(p0, u_vec, v_vec, loops):
    """候选环的投影范围 → (umin, umax, vmin, vmax)。环点兼容 {x,y,z} 与 (x,y,z) 两种写法。"""
    pts = []
    for lp in loops:
        for p in lp:
            if isinstance(p, dict):
                pts.append((p.get("x", 0.0), p.get("y", 0.0), p.get("z", 0.0)))
            else:
                pts.append((p[0], p[1], p[2]))
    arr = np.asarray(pts, dtype=float)
    uv = (arr - p0) @ np.stack([u_vec, v_vec], axis=1)
    return (float(uv[:, 0].min()), float(uv[:, 0].max()),
            float(uv[:, 1].min()), float(uv[:, 1].max()))


def region_present(ast, surfaces_by_num, tr_cards, plane, hint_loops=None,
                   levels=(128, 320), margin_frac: float = 0.05) -> bool:
    """该栅元在切割平面上是否存在**严格内部**（= 网格切出的那块是真区域还是边界伪影）。

    hint_loops：网格切出来的候选环（3D 平面内点列，``[[(x,y,z), ...], ...]``）。
    给了就用它们的投影范围当采样盒（紧）；没给就用栅元 AABB 投影（松，但可用）。
    """
    inside = build_inside_fn(ast, surfaces_by_num, tr_cards)
    if inside is None:
        return True   # 无法判定 → 不剔除（宁可保留，也不静默删几何）

    A = float(plane.get("A", 0.0)); B = float(plane.get("B", 0.0))
    C = float(plane.get("C", 0.0)); D = float(plane.get("D", 0.0))
    _nhat, p0, u_vec, v_vec = _plane_basis(A, B, C, D)

    if hint_loops:
        umin, umax, vmin, vmax = _uv_range(p0, u_vec, v_vec, hint_loops)
    else:
        bound = model_bound(surfaces_by_num)
        lo, hi = _clip_aabb_to_bound(cell_aabb(ast, surfaces_by_num, bound, tr_cards), bound)
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], dtype=float)
        uv = (corners - p0) @ np.stack([u_vec, v_vec], axis=1)
        umin, umax = float(uv[:, 0].min()), float(uv[:, 0].max())
        vmin, vmax = float(uv[:, 1].min()), float(uv[:, 1].max())

    span_u = max(umax - umin, 1e-9)
    span_v = max(vmax - vmin, 1e-9)
    mu = span_u * margin_frac
    mv = span_v * margin_frac
    umin, umax = umin - mu, umax + mu
    vmin, vmax = vmin - mv, vmax + mv

    for res in levels:
        us = np.linspace(umin, umax, int(res))
        vs = np.linspace(vmin, vmax, int(res))
        U, V = np.meshgrid(us, vs, indexing="ij")
        X = p0[0] + U * u_vec[0] + V * v_vec[0]
        Y = p0[1] + U * u_vec[1] + V * v_vec[1]
        Z = p0[2] + U * u_vec[2] + V * v_vec[2]
        try:
            if bool(np.any(inside(X, Y, Z))):
                return True
        except Exception:  # noqa: BLE001 —— 求值异常时按"无法判定"处理，不剔除几何
            return True
    return False
