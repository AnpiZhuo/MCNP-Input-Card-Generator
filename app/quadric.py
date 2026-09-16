"""GQ/SQ 二次曲面纯数学模块（仅依赖 numpy，不依赖 FreeCAD/vtk）。

用途：
- ``sq_to_gq``：MCNP SQ 10 参数（A B C D E F G x y z）→ GQ 10 系数。
- ``classify_gq``：完整二次曲面分类（特征值分解），供测试/前端 AABB 参照。
- ``gq_aabb``：有界二次曲面的轴对齐包围盒；无界/退化返回 None。
- ``cone_frame`` / ``cone_field_fn``：MCNP 圆锥（KX/KY/KZ、K/X K/Y K/Z）的
  顶点/轴/半开角/叶片**语义单一真源**，供体素求值与 FreeCAD 两个 worker 共用。

约定：GQ 方程
    A x² + B y² + C z² + D xy + E yz + F zx + G x + H y + J z + K = 0
正侧 = F(x,y,z) > 0。
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np


def sq_to_gq(params: list[float]) -> list[float]:
    """SQ 10 参数 → GQ 10 系数。

    C810 Table 3.1（3-13 页）的 SQ 是**轴平行二次曲面**，D/E/F 是**带系数 2 的线性项**
    （没有 xy/yz/zx 交叉项）：

        A(x-x0)² + B(y-y0)² + C(z-z0)²
        + 2D(x-x0) + 2E(y-y0) + 2F(z-z0) + G = 0

    展开到 GQ 形式（Ax²+By²+Cz²+Dxy+Eyz+Fzx+Gx+Hy+Jz+K）：
        x 系数 = -2A·x0 + 2D，y 系数 = -2B·y0 + 2E，z 系数 = -2C·z0 + 2F
        常数项 = A·x0² + B·y0² + C·z0² - 2D·x0 - 2E·y0 - 2F·z0 + G

    ⚠ 2026-09-16 修正：旧实现把 D/E/F 当成交叉项系数（Dxy+Eyz+Fzx，且线性项不带 2），
    D=E=F=0 时两式等价（所以球/椭球一直没暴露），一旦线性项非零（如 `SQ 1 1 1 2 0 0 -10`）
    形状与位置全错（实测体积差 28%）。真值锚点：C810 3-17 页 MCNP 自己打印的
    `SQ 1 -1.5 1 0 0 0 -.625 0 2.5 0`（D=E=F=0）与 3-20 页例 2-10 的
    `SQ -.083333 1 1 0 0 0 68.52083 -26.5 0 0`。
    """
    A, B, C, D, E, F, G, x0, y0, z0 = (float(v) for v in params)
    return [
        A, B, C, 0.0, 0.0, 0.0,
        -2 * A * x0 + 2 * D,
        -2 * B * y0 + 2 * E,
        -2 * C * z0 + 2 * F,
        A * x0 * x0 + B * y0 * y0 + C * z0 * z0
        - 2 * D * x0 - 2 * E * y0 - 2 * F * z0 + G,
    ]


def gq_field_fn(coeffs: list[float]):
    """GQ 10 系数 → 标量场 f(x,y,z)（与 ``voxel_csg.surface_fn("GQ", …)`` 逐项一致）。

    ``f ≥ 0`` = MCNP 的**正侧**（``eval_cell_field`` 用 ``fns[n](X,Y,Z) >= 0``）。
    抽出一个函数是为了让「梯度/法线」与「场」共用同一套系数语义，避免两处漂移。
    """
    a, b, c, d, e, f, g, h, j, k = (float(v) for v in coeffs)
    return lambda x, y, z: (a * x * x + b * y * y + c * z * z
                            + d * x * y + e * y * z + f * z * x
                            + g * x + h * y + j * z + k)


def gq_gradient_fn(coeffs: list[float]):
    """GQ → 解析梯度 ∇f(x,y,z) = 2M·p + (g,h,j)（``f ≥ 0`` 侧的外法线方向）。

    M = ``_sym_matrix``（含 ½ 交叉项），所以 ∇f 与 ``gq_field_fn`` 严格自洽：
    ∂f/∂x = 2A x + D y + F z + g （由 M 的 (0,0)/(0,1)/(0,2) 项给出 ×2）。
    """
    a, b, c, d, e, f, g, h, j, _k = (float(v) for v in coeffs)
    return lambda x, y, z: (
        2.0 * a * x + d * y + f * z + g,
        d * x + 2.0 * b * y + e * z + h,
        f * x + e * y + 2.0 * c * z + j,
    )


def _sym_matrix(coeffs: list[float]) -> np.ndarray:
    """二次型对称矩阵（GQ 前 6 个系数）。"""
    A, B, C, D, E, F = (float(v) for v in coeffs[:6])
    return np.array(
        [[A, D / 2, F / 2],
         [D / 2, B, E / 2],
         [F / 2, E / 2, C]],
        dtype=float,
    )


def classify_gq(coeffs: list[float], rtol: float = 1e-3):
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
    # 否则 1e-6·(x²+y²+z²)-1 这类"小系数大几何"椭球会被误判为退化。
    # ⚠ 取 1e-3 而非 1e-6：MCNP 输出/手写系数常只保留 3~4 位小数（手册 3-12 页例3 的
    # GQ 圆柱就是 -.866），"零特征值"会带 ~1e-5 的舍入噪声；容差太紧会把斜置圆柱
    # 误判成椭球 → 给出 y=±257 的假有界盒（实测放大 2086 倍）。
    # 与 _freecad_csg_worker._quadric_to_native 的 tol 口径一致（同一坑的既有注释）。
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
                # 轴对齐圆柱 → free_axis；斜置圆柱沿三根全局轴都无界（轴方向三个分量都非零），
                # 此时 axes_bounded 必须全 False，否则调用方按"有界盒"裁剪会切掉几何。
                free = None
                if abs(axis_v[0]) > 1 - 1e-6:
                    free = 0
                elif abs(axis_v[1]) > 1 - 1e-6:
                    free = 1
                elif abs(axis_v[2]) > 1 - 1e-6:
                    free = 2
                bounded_axes = ([free != g for g in range(3)] if free is not None
                                else [False, False, False])
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


def gq_aabb(coeffs: list[float], rtol: float = 1e-3):
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


# ── MCNP 圆锥（KX/KY/KZ、K/X K/Y K/Z）─────────────────────────
# 方程（C810 Table 3.1）：
#   KZ   x² + y² − t²(z − z̄)² = 0            卡片 `z̄ t² (±1)`
#   K/X  (y − ȳ)² + (z − z̄)² − t²(x − x̄)² = 0  卡片 `x̄ ȳ z̄ t² (±1)`
#   （KY/KX 与 K/Y K/Z 同理，轴分别为 y / x 与 y / z）
#
# 最后一项 ±1 **只用于单叶锥**，且同时决定两件事：
#   ① 选叶片：+1 = 朝 +轴 张开的那一叶，−1 = 朝 −轴 张开的那一叶；
#   ② 定感度：所选叶片的**内部是负侧**；另一叶内部的点、以及顶点平面另一侧的
#      点，全都算**正侧**（该单叶面是"以顶点收口的开口面"）。
# 省略 ±1（卡片只给 t²）= **双叶锥**：负侧 = 双叶锥内部（沿轴两侧都算），
# 正侧 = 双叶之外。
#
# 权威依据：MCNP6 手册 Table 3.1 锥面注；ANL openmc_mcnp_adapter
# （`up = coeffs[2] > 0` → ConeOneSided，"negative side = inside of the cone"）
# 与 MontePy ZCone（"+1 upper, -1 lower；省略 = both nappes"）一致。
#
# t = √(t²) 是半开角正切，半径 r(轴向距离 u) = t·|u|；**不是** 1/√(t²)·|u|。

#: mnemonic → (轴索引, 顶点前参数个数, 径向轴索引)
_CONE_AXES = {
    "KX": (0, 1, (1, 2)),
    "KY": (1, 1, (0, 2)),
    "KZ": (2, 1, (0, 1)),
    "K/X": (0, 3, (1, 2)),
    "K/Y": (1, 3, (0, 2)),
    "K/Z": (2, 3, (0, 1)),
}


class ConeFrame(NamedTuple):
    """圆锥几何骨架（MCNP 语义，见模块内锥面注）。"""

    apex: tuple[float, float, float]   # 顶点（主坐标系）
    axis: int                          # 轴索引 0/1/2
    radial: tuple[int, int]            # 两个径向轴索引
    t_squared: float                   # 半开角正切平方（卡片原值）
    sheet: float                       # +1 朝 +轴 / −1 朝 −轴 / 0 双叶锥


def cone_frame(surf_type: str, params: list) -> ConeFrame:
    """MCNP 圆锥卡 → :class:`ConeFrame`（轴/顶点/半开角/叶片）。

    支持 2 项形（双叶，省略 ±1）与 3 项形（单叶）的 KX/KY/KZ，
    以及 4 项形与 5 项形的 K/X K/Y K/Z。参数不足或非锥面 → ValueError。
    """
    t = (surf_type or "").upper()
    spec = _CONE_AXES.get(t)
    if spec is None:
        raise ValueError(f"非圆锥曲面类型: {surf_type}")
    axis, n_apex, radial = spec
    p = [float(v) for v in params]
    if len(p) < n_apex + 1:
        raise ValueError(f"{t} 参数不足（需要顶点 + t²）: {params}")
    if n_apex == 1:
        apex = [0.0, 0.0, 0.0]
        apex[axis] = p[0]
    else:
        apex = p[:3]
    t2 = p[n_apex]
    sheet = 0.0
    if len(p) > n_apex + 1:
        v = float(p[n_apex + 1])
        sheet = 1.0 if v > 0 else (-1.0 if v < 0 else 0.0)
    return ConeFrame(tuple(apex), axis, radial, t2, sheet)


def cone_field_fn(surf_type: str, params: list):
    """圆锥隐式场 ``f(x, y, z)``（numpy 可广播；f > 0 = 正侧）。

    双叶锥（sheet == 0）：``f = r² − t²u²``（锥外为正）。
    单叶锥（sheet == ±1）：``f = r − t·sheet·u``，其中 ``u`` 为带符号轴向距离、
    ``r`` 为径向距离。该式在所选叶片内部为负、在另一叶与顶点平面外侧为正，
    且零集恰为该叶锥面（无多余封口）。
    """
    fr = cone_frame(surf_type, params)
    apex = fr.apex
    axis = fr.axis
    radial = fr.radial
    t2 = float(fr.t_squared)
    sheet = float(fr.sheet)
    tan_half = math.sqrt(t2) if t2 > 0 else 0.0

    def field(x, y, z):
        coords = (np.asarray(x, dtype=float),
                  np.asarray(y, dtype=float),
                  np.asarray(z, dtype=float))
        u = coords[axis] - apex[axis]
        r2 = (coords[radial[0]] - apex[radial[0]]) ** 2 \
            + (coords[radial[1]] - apex[radial[1]]) ** 2
        if sheet == 0.0:
            return r2 - t2 * u * u
        return np.sqrt(r2) - tan_half * sheet * u

    return field


# ── 三点定义平面（C810 §3-17）─────────────────────────────────
def plane_from_points(params: list[float]) -> tuple[float, float, float, float]:
    """三点定义平面 → (A, B, C, D)，f = Ax+By+Cz-D，感度按 C810 §3-17 规则。

    C810 3-17 页原文：**感度由"原点具负感度"确定**；若平面过原点（D=0），
    则 (0,0,∞) 取正；若 D=C=0 则 (0,∞,0) 取正；若 D=C=B=0 则 (∞,0,0) 取正；
    全失败（三点共线）FATAL。

    ⚠ 2026-09-16 修正：旧实现直接用 edge1×edge2 的原始叉积定号，等于把感度交给
    用户点序 —— 一半点序整体翻面（实测 4000/4000 点判反、体积 40000 vs 24000）。
    """
    x1, y1, z1, x2, y2, z2, x3, y3, z3 = (float(v) for v in params)
    u = np.array([x2 - x1, y2 - y1, z2 - z1], dtype=float)
    v = np.array([x3 - x1, y3 - y1, z3 - z1], dtype=float)
    n = np.cross(u, v)
    if float(np.linalg.norm(n)) < 1e-300:
        raise ValueError("三点共线，无法定义平面")
    d = float(n @ np.array([x1, y1, z1], dtype=float))
    s = 1.0
    if d < 0:
        s = -1.0
    elif d == 0:
        if n[2] != 0:
            s = 1.0 if n[2] > 0 else -1.0
        elif n[1] != 0:
            s = 1.0 if n[1] > 0 else -1.0
        elif n[0] != 0:
            s = 1.0 if n[0] > 0 else -1.0
        else:  # 三点重合于原点 → 退化
            raise ValueError("三点定义平面退化")
    return float(s * n[0]), float(s * n[1]), float(s * n[2]), float(s * d)


def plane_field_fn(params: list[float]):
    """三点定义平面的隐式场（f > 0 = 正侧，见 :func:`plane_from_points`）。"""
    A, B, C, D = plane_from_points(params)

    def field(x, y, z):
        return (A * np.asarray(x, float) + B * np.asarray(y, float)
                + C * np.asarray(z, float) - D)
    return field


# ── 环面（C810 §3-14 / Table 3.1）───────────────────────────
#   TX/TY/TZ： s²/B² + (r − A)²/C² − 1 = 0
#   s = 沿轴坐标偏移（TY 时 s = y−ȳ），r = 到轴的径向距离
#   A = 主半径（中心到管心距离）、B = 管的**轴向**次半径、C = 管的**径向**次半径
#   正侧 = 外部（与球/柱/锥同）。
_TORUS_AXIS = {"TX": (0, (1, 2)), "TY": (1, (0, 2)), "TZ": (2, (0, 1))}


def torus_params(surf_type: str, params: list) -> tuple:
    """环面卡 → (中心3, 轴索引, 径向轴索引, A 主半径, B 轴向次半径, C 径向次半径)。"""
    t = (surf_type or "").upper()
    spec = _TORUS_AXIS.get(t)
    if spec is None:
        raise ValueError(f"非环面曲面类型: {surf_type}")
    p = [float(v) for v in params]
    if len(p) < 6:
        raise ValueError(f"{t} 参数不足（需要 x̄ ȳ z̄ A B C）: {params}")
    axis, radial = spec
    return tuple(p[0:3]), axis, radial, p[3], p[4], p[5]


def torus_field_fn(surf_type: str, params: list):
    """环面隐式场（f > 0 = 外侧）。⚠ A/B/C 三个半径角色不可混（旧实现丢 C、管心放轴上）。"""
    center, axis, radial, A, B, C = torus_params(surf_type, params)
    B = B if B != 0 else 1e-30
    C = C if C != 0 else 1e-30

    def field(x, y, z):
        co = (np.asarray(x, dtype=float), np.asarray(y, dtype=float),
              np.asarray(z, dtype=float))
        d = co[axis] - center[axis]
        r = np.sqrt((co[radial[0]] - center[radial[0]]) ** 2
                    + (co[radial[1]] - center[radial[1]]) ** 2)
        return d * d / (B * B) + (r - A) ** 2 / (C * C) - 1.0

    return field


def torus_aabb(surf_type: str, params: list):
    """环面有界盒 ((lo3, hi3))：径向 A±C、轴向 ±B。环面恒有界。"""
    center, axis, radial, A, B, C = torus_params(surf_type, params)
    lo = list(center)
    hi = list(center)
    for i in radial:
        lo[i] = center[i] - (abs(A) + abs(C))
        hi[i] = center[i] + (abs(A) + abs(C))
    lo[axis] = center[axis] - abs(B)
    hi[axis] = center[axis] + abs(B)
    return tuple(lo), tuple(hi)


# ── 直椭圆柱 REC / 六棱柱 RHP·HEX / BOX 的可选输入项（C810 §3-18~3-19）──
def rot60(vec, axis) -> np.ndarray:
    """向量绕单位轴 axis 转 +60°（Rodrigues）。RHP 省略 s/t 时用。"""
    v = np.asarray(vec, dtype=float)
    k = np.asarray(axis, dtype=float)
    c, s = 0.5, math.sqrt(3.0) / 2.0
    return c * v + s * np.cross(k, v) + k * float(k @ v) * (1.0 - c)


def rec_params(params: list) -> list[float]:
    """REC → 统一 12 参数（V H V1 V2）。

    C810 3-19 页：**10 项时第 10 项是短轴半径**，方向由 H×V1 叉积确定。
    旧实现不认 10 项：pymcnp 字段为 None → 序列化 TypeError → 整个预览失败。
    """
    p = [float(v) for v in params]
    if len(p) >= 12:
        return p[:12]
    if len(p) == 10:  # V H V1 r2
        v1 = np.array(p[6:9], dtype=float)
        h = np.array(p[3:6], dtype=float)
        e2 = np.cross(h, v1)
        n = float(np.linalg.norm(e2))
        if n < 1e-300:
            raise ValueError("REC 的 H×V1 退化，无法确定短轴方向")
        v2 = e2 / n * abs(p[9])
        return p[:9] + [float(v2[0]), float(v2[1]), float(v2[2])]
    raise ValueError(f"REC 参数个数不支持: {len(p)}（应为 10 或 12）")


def rhp_params(params: list) -> list[float]:
    """RHP/HEX → 统一 15 参数（v h r s t）。

    C810 3-19 页：只给 v h r（9 项，手册例题就是这个写法）时 s/t 由 r 绕轴依次转 60°
    推出；给到 v h r s（12 项）时 t 同理推出；轴向无限（facet 7/8 不存在）是省略
    **高度矢量**的另一种写法（本函数不涉及，见 §3-19 注）。
    旧实现不认 9/12 项：pymcnp 字段为 None → 序列化 TypeError → 整个预览失败。
    """
    p = [float(v) for v in params]
    if len(p) >= 15:
        return p[:15]
    if len(p) in (9, 12):
        h = np.array(p[3:6], dtype=float)
        r1 = np.array(p[6:9], dtype=float)
        hn = float(np.linalg.norm(h))
        if hn < 1e-300:
            raise ValueError("RHP/HEX 高度矢量退化")
        k = h / hn
        r2 = (np.array(p[9:12], dtype=float) if len(p) >= 12
              else rot60(r1, k))
        r3 = rot60(r2, k)
        return (p[:9] + [float(x) for x in r2] + [float(x) for x in r3])
    raise ValueError(f"RHP/HEX 参数个数不支持: {len(p)}（应为 9、12 或 15）")


def box_params(params: list) -> tuple[list[float], bool]:
    """BOX → (12 参数, 是否轴向无限)。

    C810 3-19 页：**BOX/RPP 可在某一维无限**（该维两个 facet 不存在）。BOX 少给第三个
    边向量（9 项）即沿 A1×A2 方向无限。旧实现不认 9 项：pymcnp 直接拒卡 →
    parse_surfaces 静默跳过 → 引用它的栅元整块丢失。
    """
    p = [float(v) for v in params]
    if len(p) >= 12:
        # 12 项但 A3 为零向量 → 与 9 项等价（parse_surfaces 补零后的统一形态）
        a3 = np.array(p[9:12], dtype=float)
        return p[:12], float(np.linalg.norm(a3)) < 1e-12
    if len(p) == 9:
        return p[:9] + [0.0, 0.0, 0.0], True
    raise ValueError(f"BOX 参数个数不支持: {len(p)}（应为 9 或 12）")


# ── 椭球 ELL（C810 §3-20）───────────────────────────────────
def ellipsoid_field_fn(params: list):
    """ELL 隐式场（f > 0 = 外侧）。

    C810 3-20 页：Rm>0 → V1/V2 为两焦点、Rm = 长轴**长度**；Rm<0 → V1 为球心、
    V2 为长轴**矢量**（长度 = 长半径）、|Rm| = 短半径。
    焦点形式：f = d1 + d2 − Rm（椭圆定义，正侧在内侧）。
    中心矢量形式：f = (轴向/a)² + (径向/b)² − 1。
    """
    p = [float(v) for v in params]
    if len(p) < 7:
        raise ValueError(f"ELL 参数不足: {params}")
    v1 = np.array(p[0:3], dtype=float)
    v2 = np.array(p[3:6], dtype=float)
    rm = p[6]
    if rm > 0:
        def field(x, y, z):
            d1 = np.sqrt((np.asarray(x, float) - v1[0]) ** 2
                         + (np.asarray(y, float) - v1[1]) ** 2
                         + (np.asarray(z, float) - v1[2]) ** 2)
            d2 = np.sqrt((np.asarray(x, float) - v2[0]) ** 2
                         + (np.asarray(y, float) - v2[1]) ** 2
                         + (np.asarray(z, float) - v2[2]) ** 2)
            return d1 + d2 - rm
        return field
    a = float(np.linalg.norm(v2))
    b = abs(rm)
    if a < 1e-300 or b < 1e-300:
        raise ValueError("ELL 长/短半径退化")
    e = v2 / a

    def field2(x, y, z):
        d = np.stack([np.asarray(x, float) - v1[0], np.asarray(y, float) - v1[1],
                      np.asarray(z, float) - v1[2]], axis=-1)
        axial = d @ e
        perp2 = np.sum(d * d, axis=-1) - axial ** 2
        return axial ** 2 / (a * a) + perp2 / (b * b) - 1.0
    return field2


# ── 任意多面体 ARB 面码（C810 §3-21）─────────────────────────
def arb_face_indices(codes: list) -> list[list[int]]:
    """ARB 6 个面码 → 0 基角点索引表。

    C810 3-21 页：面码是 4 位整数（高位在前 = 该面的角点号）；**第 4 位为 0 则忽略该点**
    （四点共面校验用）。旧实现 `(digit)-1` 把 0 变成索引 −1 → 取到第 8 角点
    （Python/JS 负索引），面片被污染：手册五面体例 20/4000 点判错，
    远离原点时体心/面心一起被 (0,0,0) 带偏 → 3738/4000 点判错、体积 4372 vs 64000。
    """
    faces = []
    for code in codes:
        try:
            code = int(abs(float(code)))
        except (TypeError, ValueError):
            continue
        if code == 0:
            continue
        digits = []
        c = code
        while c:
            digits.append(c % 10)
            c //= 10
        digits.reverse()                      # 高位在前
        idx = [d - 1 for d in digits if d != 0]
        if len(idx) >= 3:
            faces.append(idx)
    return faces


# ── 点定义回转面 X/Y/Z（C810 §3-15）──────────────────────────
def point_surface_field_fn(surf_type: str, params: list):
    """X/Y/Z 点定义回转面隐式场（f > 0 = 外侧）。

    C810 3-15 页：给 1 对 (a,r) → 平面；2 对 → 线性曲面（柱面/单叶锥）；
    3 对 → 二次曲面（r² = 二次式 a）。除 SQ 外感度与方程定义曲面一致
    （球/柱/锥 = 外侧为正）。
    """
    t = (surf_type or "").upper()
    if t not in ("X", "Y", "Z"):
        raise ValueError(f"非点定义回转面: {surf_type}")
    axis = {"X": 0, "Y": 1, "Z": 2}[t]
    radial = tuple(i for i in range(3) if i != axis)
    p = [float(v) for v in params]
    pts = [(p[i], p[i + 1]) for i in range(0, len(p) - 1, 2)]
    if not pts:
        raise ValueError(f"{t} 卡缺少坐标对: {params}")

    def _axis_coord(x, y, z):
        return (np.asarray(x, float), np.asarray(y, float), np.asarray(z, float))[axis]

    def _radial2(x, y, z):
        co = (np.asarray(x, float), np.asarray(y, float), np.asarray(z, float))
        return co[radial[0]] ** 2 + co[radial[1]] ** 2

    if len(pts) == 1:
        a1 = pts[0][0]
        return lambda x, y, z: _axis_coord(x, y, z) - a1

    if len(pts) == 2:
        (a1, r1), (a2, r2) = pts
        if abs(a2 - a1) < 1e-300:
            raise ValueError(f"{t} 卡两点轴向坐标相同（退化为平面，MCNP 判致命错误）")
        if r1 == r2:                      # 柱面 r = r1
            return lambda x, y, z: _radial2(x, y, z) - r1 * r1
        tan = (r2 - r1) / (a2 - a1)       # 单叶锥（MCNP 由两点只生成单叶）
        a0 = a1 - r1 / tan
        # 半径 r(a) = tan·(a−a0) 必须用**带符号** tan：该式在所给两点之间为正（正是那一叶），
        # 越过顶点变负（另一叶 → 正侧）。旧实现取 abs(tan) → tan<0 时整叶判反。
        def cone_field(x, y, z):
            rr = np.sqrt(_radial2(x, y, z))
            return rr - tan * (_axis_coord(x, y, z) - a0)
        return cone_field

    if len(pts) == 3:
        A = np.array([[a * a, a, 1.0] for a, _ in pts], dtype=float)
        rhs = np.array([r * r for _, r in pts], dtype=float)
        ca, cb, cc = np.linalg.solve(A, rhs)

        def quad_field(x, y, z):
            a = _axis_coord(x, y, z)
            return _radial2(x, y, z) - (ca * a * a + cb * a + cc)
        return quad_field

    raise ValueError(f"{t} 卡坐标对过多（最多 3 对）: {params}")

