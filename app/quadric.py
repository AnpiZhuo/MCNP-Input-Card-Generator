"""GQ/SQ 二次曲面纯数学模块（仅依赖 numpy，不依赖 FreeCAD/vtk）。

用途：
- ``sq_to_gq``：MCNP SQ 10 参数（A B C D E F G x y z）→ GQ 10 系数。
- ``classify_gq``：完整二次曲面分类（特征值分解），供测试/前端 AABB 参照。
- ``gq_aabb``：有界二次曲面的轴对齐包围盒；无界/退化返回 None。

约定：GQ 方程
    A x² + B y² + C z² + D xy + E yz + F zx + G x + H y + J z + K = 0
正侧 = F(x,y,z) > 0。
"""

from __future__ import annotations

import math

import numpy as np


def sq_to_gq(params: list[float]) -> list[float]:
    """SQ 10 参数 → GQ 10 系数。

    SQ 方程为
        A(x-x0)² + B(y-y0)² + C(z-z0)²
        + D(x-x0)(y-y0) + E(y-y0)(z-z0) + F(z-z0)(x-x0) + G = 0
    """
    A, B, C, D, E, F, G, x0, y0, z0 = (float(v) for v in params)
    return [
        A, B, C, D, E, F,
        -2 * A * x0 - D * y0 - F * z0,
        -2 * B * y0 - D * x0 - E * z0,
        -2 * C * z0 - E * y0 - F * x0,
        A * x0 * x0 + B * y0 * y0 + C * z0 * z0
        + D * x0 * y0 + E * y0 * z0 + F * z0 * x0 + G,
    ]


def _sym_matrix(coeffs: list[float]) -> np.ndarray:
    """二次型对称矩阵（GQ 前 6 个系数）。"""
    A, B, C, D, E, F = (float(v) for v in coeffs[:6])
    return np.array(
        [[A, D / 2, F / 2],
         [D / 2, B, E / 2],
         [F / 2, E / 2, C]],
        dtype=float,
    )


def classify_gq(coeffs: list[float], rtol: float = 1e-6):
    """特征值分类 GQ 系数 → 信息 dict。

    返回字段：
      kind        椭球/双曲面/锥面/柱面/抛物面/退化等
      bounded     是否有界（椭球 = True）
      axes_bounded 每根全局轴是否被该曲面约束（[x,y,z]）
      center      有界曲面的全局中心（椭球/圆柱）
      semiaxes    椭球三半轴（全局坐标，椭球时有效）
      axis        柱面轴线方向（单位向量，圆柱时有效）
      radii       柱面两径向半轴（圆柱时有效）
      radial_indices  柱面径向特征方向索引（圆柱时有效）
      free_axis   柱面自由轴索引（轴对齐圆柱时 0/1/2，否则 None）
      eigenvalues / eigenvectors  升序特征值与特征向量（V 列为特征向量）
    """
    c = [float(v) for v in coeffs]
    # 系数归一化：方程整体缩放不改变曲面，但能让"零特征值"判断与
    # 系数量级无关（如 1e-6·(x²+y²+z²)-1 的半径 1000 椭球不会被误判为退化）
    norm = max(1e-300, max(abs(v) for v in c))
    c = [v / norm for v in c]
    A, B, C, D, E, F, G, H, J, K = c
    M = _sym_matrix(c)
    w, V = np.linalg.eigh(M)  # w 升序；V 列为特征向量
    # 相对容差：按二次型特征值本身定标（不取 1 兜底），
    # 否则 1e-6·(x²+y²+z²)-1 这类"小系数大几何"椭球会被误判为退化
    scale = max(1e-300, float(np.max(np.abs(w))))
    tol = rtol * scale
    L = np.array([G, H, J], dtype=float)
    Lp = V.T @ L
    nz = np.abs(w) > tol
    n_nz = int(nz.sum())
    zeros = [i for i in range(3) if not nz[i]]

    info = {
        "kind": "degenerate",
        "bounded": False,
        "axes_bounded": [False, False, False],
        "center": None,
        "semiaxes": None,
        "axis": None,
        "radii": None,
        "radial_indices": None,
        "free_axis": None,
        "eigenvalues": w.tolist(),
        "eigenvectors": V.tolist(),
    }

    if n_nz == 3:
        # 中心：λ_i (x_i - c_i)² 配平方 → c_local = -Lp/(2λ)
        c_local = np.zeros(3)
        for i in range(3):
            c_local[i] = -Lp[i] / (2 * w[i])
        Cc = float(sum(Lp[i] ** 2 / (4 * w[i]) for i in range(3)) - K)
        # 统一符号：令 w' = s·w, C' = s·C，要求 w' 全正且 C'>0 才是椭球
        s = 1.0 if w[0] > 0 else -1.0
        ww = s * w
        CC = s * Cc
        if all(x > tol for x in ww) and CC > tol:
            center_g = V @ c_local
            semi = [math.sqrt(CC / ww[i]) for i in range(3)]
            info.update(
                kind="ellipsoid", bounded=True,
                axes_bounded=[True, True, True],
                center=[float(x) for x in center_g],
                semiaxes=semi,
            )
        elif abs(Cc) <= tol:
            info["kind"] = "cone"
        elif Cc > 0:
            info["kind"] = "hyperboloid_one"
        else:
            info["kind"] = "hyperboloid_two"
        return info

    if n_nz == 2:
        zi = zeros[0]
        radial = [i for i in range(3) if i != zi]
        lam = w[radial]
        if abs(Lp[zi]) > tol:
            # 沿零特征方向有线性项 → 抛物面（无界）
            info["kind"] = ("paraboloid_elliptic" if lam[0] * lam[1] > 0
                            else "paraboloid_hyperbolic")
            return info
        # 圆柱：径向配平方，轴线方向 = 零特征向量
        c_local = np.zeros(3)
        for i in radial:
            c_local[i] = -Lp[i] / (2 * w[i])
        Cr = float(K - sum(Lp[i] ** 2 / (4 * w[i]) for i in radial))
        if lam[0] * lam[1] > 0:
            # 径向同号：要求 -Cr/λ > 0 才是实椭圆截面
            if (Cr / lam[0] < 0) and (Cr / lam[1] < 0):
                radii = [math.sqrt(-Cr / lam[0]), math.sqrt(-Cr / lam[1])]
                axis_v = V[:, zi]
                center_g = V @ c_local
                # 全局轴向上径向半轴投影（旋转椭圆柱的 AABB 半宽）
                half = [0.0, 0.0, 0.0]
                for g in range(3):
                    s = 0.0
                    for k, i in enumerate(radial):
                        s += (V[g, i] * radii[k]) ** 2
                    half[g] = math.sqrt(s)
                # 轴对齐圆柱 → free_axis；斜置圆柱对全局轴均无界约束
                free = None
                if abs(axis_v[0]) > 1 - 1e-6:
                    free = 0
                elif abs(axis_v[1]) > 1 - 1e-6:
                    free = 1
                elif abs(axis_v[2]) > 1 - 1e-6:
                    free = 2
                bounded_axes = [free != g for g in range(3)]
                info.update(
                    kind="cylinder_elliptic",
                    bounded=free is not None,
                    axes_bounded=bounded_axes,
                    center=[float(x) for x in center_g],
                    axis=[float(x) for x in axis_v],
                    radii=radii,
                    radial_indices=radial,
                    free_axis=free,
                )
            else:
                info["kind"] = "degenerate"  # 虚圆柱 → 无实曲面
        else:
            info["kind"] = "cylinder_hyperbolic"
        return info

    # n_nz <= 1：退化（平面/平面对/点/空/全空间）
    if n_nz == 1:
        info["kind"] = "plane"
    else:
        info["kind"] = "plane_pair_or_empty"
    return info


def gq_aabb(coeffs: list[float], rtol: float = 1e-6):
    """有界 GQ 曲面的轴对齐包围盒。

    返回 ``((lo_x, lo_y, lo_z), (hi_x, hi_y, hi_z), (bx, by, bz))``，
    其中 b* 表示该轴是否被曲面约束（椭球三轴均 True；
    轴对齐椭圆/圆柱两径向轴 True、自由轴 False）。
    无界 / 退化 / 斜置柱面 → None。
    """
    info = classify_gq(coeffs, rtol=rtol)
    if info["kind"] == "ellipsoid":
        c = info["center"]
        h = [0.0, 0.0, 0.0]
        V = np.array(info["eigenvectors"])
        semi = info["semiaxes"]
        for g in range(3):
            s = sum((V[g, i] * semi[i]) ** 2 for i in range(3))
            h[g] = math.sqrt(s)
        lo = tuple(c[g] - h[g] for g in range(3))
        hi = tuple(c[g] + h[g] for g in range(3))
        return lo, hi, (True, True, True)
    if info["kind"] == "cylinder_elliptic" and info["free_axis"] is not None:
        c = info["center"]
        free = info["free_axis"]
        h = [0.0, 0.0, 0.0]
        V = np.array(info["eigenvectors"])
        radii = info["radii"]
        radial = info["radial_indices"]
        for g in range(3):
            s = sum((V[g, i] * radii[k]) ** 2 for k, i in enumerate(radial))
            h[g] = math.sqrt(s)
        lo = tuple(c[g] - h[g] for g in range(3))
        hi = tuple(c[g] + h[g] for g in range(3))
        axes = tuple(g != free for g in range(3))
        return lo, hi, axes
    return None
