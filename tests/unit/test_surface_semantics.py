"""全曲面语义回归（真值全部取自 C810.pdf，逐条标注页码）。

覆盖 2026-09-16 全类型审计查出的每一类问题，一条一个用例：
  1. 圆锥单叶/双叶（已修）+ 半径 = √(t²)·u
  2. 三点平面 P_1 感度规则（C810 §3-17）
  3. SQ 的 D/E/F 是带系数 2 的线性项（C810 Table 3.1）
  4. ELL 两形（C810 §3-20）
  5. ARB 面码第 4 位 0 = 忽略该点（C810 §3-21）
  6. 环面 A 主半径 / B 轴向 / C 径向（C810 §3-14）
  7. X/Y/Z 点定义（C810 §3-15）
  8. 宏体可选尾项：REC 10 项、RHP 9/12 项、BOX 9 项（C810 §3-19）
  9. AABB：负号二次型的负侧无界、斜置柱不声称有界、环面有界盒
"""
import math

import numpy as np
import pytest

from app.quadric import (arb_face_indices, box_params, ellipsoid_field_fn,
                         plane_from_points, point_surface_field_fn,
                         rec_params, rhp_params, sq_to_gq, torus_field_fn)
from app.voxel_csg import _surface_negative_aabb, surface_aabb, surface_fn


def vals(t, p, pts):
    f = surface_fn(t, p)
    return [float(np.asarray(f(*q)).ravel()[0]) for q in pts]


def signs(t, p, pts):
    return ["+" if v > 0 else "-" for v in vals(t, p, pts)]


# ── 1. 圆锥（C810 3-14 例2；§2-C.1 单叶规则）────────────────
def test_cone_two_sided_default_when_sheet_omitted():
    """省略 ±1 = 双叶锥：上下两叶内部都是负侧。"""
    assert signs("KZ", [0, 0.25], [(0, 0, 5), (0, 0, -5), (5, 0, 5)]) == ["-", "-", "+"]


def test_cone_plus_one_is_upper_nappe_only():
    """+1 = 朝 +轴 那一片；另一叶内部与顶点平面外侧都算正侧（"锥外为正"）。"""
    assert signs("KZ", [0, 0.25, 1], [(0, 0, 5), (5, 0, 5), (0, 0, -5)]) == ["-", "+", "+"]
    assert signs("KZ", [0, 0.25, -1], [(0, 0, -5), (0, 0, 5)]) == ["-", "+"]


def test_cone_radius_is_sqrt_t_squared_times_distance():
    """t²=4 → r = 2u（不是 1/√t²·u）。"""
    assert vals("KZ", [0, 4.0, 1], [(1, 0, 5)])[0] == pytest.approx(1 - 10)
    assert signs("KZ", [0, 4.0, 1], [(1, 0, 5), (11, 0, 5)]) == ["-", "+"]


def test_cone_parallel_axis_uses_own_axis():
    """K/X 轴是 x、K/Y 轴是 y（旧实现互换）。"""
    assert signs("K/X", [0, 0, 0, 0.25, 1], [(5, 0, 0), (0, 5, 0)]) == ["-", "+"]
    assert signs("K/Y", [0, 0, 0, 0.25, 1], [(0, 5, 0), (5, 0, 0)]) == ["-", "+"]


# ── 2. 三点平面感度（C810 §3-17）───────────────────────────
@pytest.mark.parametrize("pts", [
    [0, 0, 0, 0, 1, 0, 1, 0, 0],          # 序 A
    [0, 0, 0, 1, 0, 0, 0, 1, 0],          # 序 B（反向）
])
def test_plane_from_three_points_sense_rule_origin_negative(pts):
    """原点必须具负感度；过原点时 (0,0,∞) 取正 → 两种点序结论一致。"""
    A, B, C, D = plane_from_points(pts)
    assert A * 0 + B * 0 + C * 0 - D <= 0
    assert C > 0
    assert signs("P_1", pts, [(0, 0, 1), (0, 0, -1)]) == ["+", "-"]


@pytest.mark.parametrize("pts", [
    [0, 0, 5, 1, 0, 5, 0, 1, 5],
    [0, 0, 5, 0, 1, 5, 1, 0, 5],          # 反向点序
])
def test_plane_from_three_points_sense_rule_offset_plane(pts):
    """D≠0 时原点负 → 平面 z=5：z>5 为正侧，与点序无关。"""
    assert signs("P_1", pts, [(0, 0, 6), (0, 0, 4)]) == ["+", "-"]


# ── 3. SQ 的 D/E/F（C810 Table 3.1）───────────────────────
def test_sq_linear_terms_are_doubled_linear_not_cross():
    """SQ 线性项：A(x-x̄)²+…+2D(x-x̄)+…+G，无交叉项。"""
    gq = sq_to_gq([1, 1, 1, 2, 0, 0, -10, 0, 0, 0])
    assert gq == pytest.approx([1, 1, 1, 0, 0, 0, 4, 0, 0, -10])   # f = x²+y²+z²+4x-10
    # 球心 x=-2、R²=14：内部负、外部正
    assert signs("SQ", [1, 1, 1, 2, 0, 0, -10, 0, 0, 0],
                 [(0, 0, 0), (2, 0, 0), (-6, 0, 0)]) == ["-", "+", "+"]


def test_sq_manual_printed_coefficients_roundtrip():
    """C810 3-17 页 MCNP 自打印的 SQ（1 -1.5 1 0 0 0 -.625 0 2.5 0）代回三点须为 0。"""
    gq = sq_to_gq([1, -1.5, 1, 0, 0, 0, -0.625, 0, 2.5, 0])
    f = surface_fn("SQ", [1, -1.5, 1, 0, 0, 0, -0.625, 0, 2.5, 0])
    for y, r in ((2, 1), (3, 1), (4, 2)):
        assert float(np.asarray(f(0, y, r)).ravel()[0]) == pytest.approx(0.0, abs=1e-9)
    assert gq[0:3] == [1.0, -1.5, 1.0]


# ── 4. ELL 两形（C810 §3-20）──────────────────────────────
def test_ell_focus_form_semi_major_is_half_of_rm():
    """Rm>0：Rm = 长轴**长度** → 半长轴 = Rm/2（旧实现当 Rm → 大 2 倍）。"""
    ell = ellipsoid_field_fn([0, 0, -2, 0, 0, 2, 6])
    assert float(ell(0, 0, 0)) < 0        # 中心在内部
    assert float(ell(0, 0, 3.5)) > 0      # 超出半长轴 3
    assert float(ell(0, 0, 2.9)) < 0
    assert signs("ELL", [0, 0, -2, 0, 0, 2, 6], [(0, 0, 0), (0, 0, 3.5)]) == ["-", "+"]


def test_ell_center_vector_form():
    """Rm<0：V1 = 中心、V2 = 长轴矢量（模 = 长半径）、|Rm| = 短半径。"""
    p = [0, 0, 0, 0, 0, 3, -2]
    assert signs("ELL", p, [(0, 0, 2.5), (0, 0, 4), (1, 0, 0), (2.5, 0, 0)]) == ["-", "+", "-", "+"]


# ── 5. ARB 面码（C810 §3-21）─────────────────────────────
def test_arb_face_code_fourth_digit_zero_ignored():
    assert arb_face_indices([1234, 1250, 1350, 2450, 3450, 0]) == [
        [0, 1, 2, 3], [0, 1, 4], [0, 2, 4], [1, 3, 4], [2, 3, 4]]


@pytest.mark.parametrize("base", [(0, 0), (100, 100)])
def test_arb_pyramid_near_and_far_from_origin(base):
    """未用角点是零三元组：体心不能把 (0,0,0) 平均进来（远离原点时法向会翻）。"""
    x, y = base
    corners = [x, y, 0, x + 4, y, 0, x + 4, y + 4, 0, x, y + 4, 0,
               x + 2, y + 2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    p = corners + [1234, 1250, 2350, 3450, 4150, 0]
    pts = [(x + 2, y + 2, 1), (x + 2, y + 2, -1), (x + 5, y + 2, 1)]
    assert signs("ARB", p, pts) == ["-", "+", "+"]


# ── 6. 环面（C810 §3-14）─────────────────────────────────
def test_torus_roles_of_a_b_c():
    """A 主半径、B 轴向次半径、C 径向次半径（旧实现丢 C、把管心放轴上）。"""
    p = [0, 0, 0, 3, 2, 1]
    # 管心在 (A,0,0)：轴向 ±B 内为负，径向 ±C 内为负
    assert signs("TZ", p, [(3, 0, 1.5), (3, 0, 2.5), (3.5, 0, 0), (4.5, 0, 0)]) == ["-", "+", "-", "+"]
    # 孔中心 (0,0,0) 在环面外
    assert signs("TZ", p, [(0, 0, 0)]) == ["+"]


def test_torus_axes_all_three():
    # 管心在 A 距离的**径向**上（不是沿轴）：TX→(0,A,0)、TY→(A,0,0)、TZ→(A,0,0)
    for t, inside, outside in (("TX", (0, 3, 0), (0, 0, 0)),
                               ("TY", (3, 0, 0), (0, 0, 0)),
                               ("TZ", (3, 0, 0), (0, 0, 0))):
        assert signs(t, [0, 0, 0, 3, 1, 1], [inside, outside]) == ["-", "+"]


def test_torus_aabb_uses_radial_plus_tube():
    lo, hi, axes = surface_aabb("TZ", [0, 0, 0, 3, 2, 1])
    assert axes == (True, True, True)
    assert lo[0] == pytest.approx(-4) and hi[0] == pytest.approx(4)   # A + C
    assert lo[2] == pytest.approx(-2) and hi[2] == pytest.approx(2)   # B
    # 负侧（管内）也在该盒内 → 可复用
    assert _surface_negative_aabb("TZ", [0, 0, 0, 3, 2, 1]) is not None


# ── 7. X/Y/Z 点定义（C810 §3-15）──────────────────────────
def test_point_surface_one_pair_is_plane():
    assert signs("X", [5, 0], [(6, 0, 0), (4, 0, 0)]) == ["+", "-"]


def test_point_surface_two_pairs_equal_radius_is_cylinder():
    assert signs("X", [-3, 2, 3, 2], [(0, 1, 0), (0, 3, 0)]) == ["-", "+"]


def test_point_surface_two_pairs_is_one_sheet_cone():
    """两点的锥只生成单叶；轴外为正。"""
    assert signs("X", [-3, 2, 2, 1], [(2, 1, 0), (2, 3, 0)]) == ["-", "+"]


def test_point_surface_three_pairs_quadric_matches_manual_example():
    """C810 3-20 页例 2-10：X 7 5 3 2 4 3 的三个点必须落在曲面上。"""
    f = point_surface_field_fn("X", [7, 5, 3, 2, 4, 3])
    for a, r in ((7, 5), (3, 2), (4, 3)):
        assert float(f(a, r, 0)) == pytest.approx(0.0, abs=1e-9)
    assert signs("X", [7, 5, 3, 2, 4, 3], [(7, 6, 0), (7, 4, 0)]) == ["+", "-"]


# ── 8. 宏体可选尾项（C810 §3-19）──────────────────────────
def test_rec_ten_entries_minor_radius_from_cross_product():
    p = rec_params([0, 0, 0, 0, 0, 10, 2, 0, 0, 1])     # V=(0,0,0) H=+z V1=+x(2) r2=1
    assert p[9:12] == pytest.approx([0, 1, 0])          # H×V1 方向、模长 1
    assert signs("REC", [0, 0, 0, 0, 0, 10, 2, 0, 0, 1], [(1.9, 0, 5), (2.1, 0, 5),
                                                           (0, 0.9, 5), (0, 1.1, 5)]) \
        == ["-", "+", "-", "+"]


def test_rhp_nine_and_twelve_entries_derive_s_t_by_60deg():
    p9 = rhp_params([0, 0, -4, 0, 0, 8, 0, 2, 0])
    assert len(p9) == 15
    assert p9[9:12] == pytest.approx([-math.sqrt(3), 1.0, 0.0], abs=1e-6)
    p12 = rhp_params([0, 0, -4, 0, 0, 8, 0, 2, 0, 0, -2, 0])
    assert p12[12:15] == pytest.approx([math.sqrt(3), -1.0, 0.0], abs=1e-6)
    assert signs("RHP", p9, [(0, 0, 0), (0, 3, 0), (0, 0, 9)]) == ["-", "+", "+"]


def test_box_nine_entries_is_infinite_prism():
    p, infinite = box_params([0, 0, 0, 1, 0, 0, 0, 1, 0])
    assert infinite and len(p) == 12
    # 沿 A1×A2 = +z 无限：z 方向永远算内部，只有 x/y 才判内外
    assert signs("BOX", p, [(0.5, 0.5, 50), (1.5, 0.5, 0), (0.5, 0.5, -50)]) == ["-", "+", "-"]


# ── 9. AABB 语义 ─────────────────────────────────────────
def test_negative_aabb_none_when_negative_side_is_unbounded():
    """二次型整体取负 → f<0 是**外侧**（无界）→ 不能拿曲面盒当负侧盒。"""
    assert _surface_negative_aabb("GQ", [-1, -1, -1, 0, 0, 0, 0, 0, 0, 4]) is None
    assert _surface_negative_aabb("GQ", [1, 1, 1, 0, 0, 0, 0, 0, 0, -4]) is not None


def test_negative_aabb_none_for_oblique_cylinder():
    """手册 3-13 例3 的斜置 GQ 圆柱沿三轴都无界 → 不得声称有界（旧实现给 ±257 假盒）。"""
    p = [1, .25, .75, 0, -.866, 0, -12, -2, 3.464, 39]
    assert surface_aabb("GQ", p) is None
    assert _surface_negative_aabb("GQ", p) is None
