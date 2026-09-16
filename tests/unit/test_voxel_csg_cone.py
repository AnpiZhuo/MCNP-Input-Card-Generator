"""圆锥（KX/KY/KZ、K/X K/Y K/Z）语义测试 —— 体素隐式场 + 卡片解析。

MCNP 语义（C810 Table 3.1；ANL openmc_mcnp_adapter 与 MontePy 一致）：
  * 双叶锥（省略最后一项 ±1）：负侧 = 双叶锥内部，正侧 = 双叶之外；
  * 单叶锥（±1）：+1 = 朝 +轴 张开的叶、−1 = 朝 −轴 的叶，
    **所选叶片内部是负侧**，另一叶与顶点平面外侧都算正侧；
  * 半径 r = √(t²)·|轴向距离|（不是 1/√(t²)·|u|）；
  * KX/KY/KZ 的顶点落在该轴坐标上（另两轴为 0），K/X K/Y K/Z 的轴分别是 x/y/z。

历史 bug（本次修复，无回归测试 → 内外颠倒 + 轴错位 + 半径取倒数）：
  `voxel_csg` 旧实现 `(t2·u² − r²)·s` 把 +1 当成"整体反号"，
  FreeCAD worker 旧实现 K/X 用 Y 轴、K/Y 用 X 轴，半径取 1/√t²、顶点放轴端。
"""
import numpy as np
import pytest

from app.quadric import cone_field_fn, cone_frame
from app.voxel_csg import surface_fn


def field(t, params):
    f = surface_fn(t, params)
    return lambda p: float(np.asarray(f(*p)).ravel()[0])


def sign(t, params, p):
    return "+" if field(t, params)(p) > 0 else "-"


# ── 双叶锥（省略 ±1）──────────────────────────────────────────
@pytest.mark.parametrize("params", [[0.0, 0.25, 0.0], [0.0, 0.25]])
def test_kz_two_sided_negative_inside_both_nappes(params):
    """双叶锥：上下两叶内部都是负侧，锥外为正侧；t=0.5 → r=0.5|z|。"""
    assert sign("KZ", params, (0, 0, 5)) == "-"
    assert sign("KZ", params, (0, 0, -5)) == "-"
    assert sign("KZ", params, (5, 0, 5)) == "+"
    assert sign("KZ", params, (5, 0, -5)) == "+"


def test_two_sided_cone_missing_sheet_defaults_to_zero():
    """省略最后一项 ±1 = 双叶锥（sheet=0），不是单叶。"""
    assert cone_frame("KZ", [0.0, 0.25]).sheet == 0.0
    assert cone_frame("K/X", [1.0, 2.0, 3.0, 0.25]).sheet == 0.0
    assert cone_frame("KZ", [0.0, 0.25, 0.0]).sheet == 0.0


# ── 单叶锥：±1 选叶片且定感度 ─────────────────────────────────
def test_kz_plus_one_upper_nappe_inside_negative():
    """KZ +1：上叶内部负；下叶内部与顶点平面另一侧都是正侧。"""
    p = [0.0, 0.25, 1.0]
    assert sign("KZ", p, (0, 0, 5)) == "-"
    assert sign("KZ", p, (2, 0, 5)) == "-"
    assert sign("KZ", p, (5, 0, 5)) == "+"
    assert sign("KZ", p, (0, 0, -5)) == "+"   # 另一叶内部 → 正侧（旧实现 -）
    assert sign("KZ", p, (5, 0, -5)) == "+"


def test_kz_minus_one_lower_nappe_mirror():
    p = [0.0, 0.25, -1.0]
    assert sign("KZ", p, (0, 0, -5)) == "-"
    assert sign("KZ", p, (0, 0, 5)) == "+"
    assert sign("KZ", p, (5, 0, -5)) == "+"
    assert sign("KZ", p, (5, 0, 5)) == "+"


def test_one_sided_cone_follows_apex_offset():
    """顶点不在原点：负侧区域随顶点平移（旧实现把顶点放在 x0−B 等轴端）。"""
    p = [3.0, 0.25, 1.0]
    assert sign("KZ", p, (0, 0, 8)) == "-"    # u=5, r=0 < t·u=2.5
    assert sign("KZ", p, (0, 0, -8)) == "+"   # 顶点平面另一侧
    assert sign("KZ", p, (9, 0, 3)) == "+"    # 顶点所在平面、径向 9 → 正侧


def test_one_sided_upper_nappe_unbounded_inside_axis_side():
    """上叶负侧只存在于 +轴 一侧（顶点平面另一侧必为正）。"""
    p = [3.0, 0.25, 1.0]
    assert sign("KZ", p, (0, 0, 13)) == "-"   # r=0 < t·10
    assert sign("KZ", p, (0, 0, 2.999)) == "+"  # 顶点平面下方紧邻点
    assert sign("KZ", p, (6, 0, 2.999)) == "+"


# ── t² 是半开角正切平方：r = √(t²)·u ───────────────────────────
def test_radius_uses_sqrt_of_t_squared_not_reciprocal():
    """t²=4 → t=2 → r(5)=10：r=1 在叶内（负）、r=11 在叶外（正）。

    旧实现用 1/√t²（=0.5）算半径 → 半开角被取倒数，锥面形状全错。
    """
    p = [0.0, 4.0, 1.0]
    assert sign("KZ", p, (1, 0, 5)) == "-"
    assert sign("KZ", p, (11, 0, 5)) == "+"
    f = field("KZ", p)
    assert f((1, 0, 5)) == pytest.approx(1 - 2 * 5, abs=1e-12)   # f = r − t·u
    # 双叶锥同款半径：r² − t²u²
    f2 = field("KZ", [0.0, 4.0, 0.0])
    assert f2((1, 0, 5)) == pytest.approx(1 - 4 * 25, abs=1e-12)


# ── KX/KY/KZ：顶点落在各自轴上，轴心在原点 ─────────────────────
@pytest.mark.parametrize("t,inside,outside", [
    ("KX", (5, 0, 0), (0, 5, 0)),
    ("KY", (0, 5, 0), (5, 0, 0)),
    ("KZ", (0, 0, 5), (5, 0, 0)),
])
def test_on_axis_cones_use_their_own_axis(t, inside, outside):
    p = [0.0, 0.25, 1.0]
    assert sign(t, p, inside) == "-"
    assert sign(t, p, outside) == "+"


def test_kx_ky_axes_not_swapped():
    """K/X 的轴是 x、K/Y 的轴是 y（旧实现两者互换）。"""
    assert cone_frame("K/X", [0, 0, 0, 0.25, 1]).axis == 0
    assert cone_frame("K/Y", [0, 0, 0, 0.25, 1]).axis == 1
    assert cone_frame("K/Z", [0, 0, 0, 0.25, 1]).axis == 2
    p = [0.0, 0.0, 0.0, 0.25, 1.0]
    assert sign("K/X", p, (5, 0, 0)) == "-"
    assert sign("K/X", p, (0, 5, 0)) == "+"
    assert sign("K/Y", p, (0, 5, 0)) == "-"
    assert sign("K/Y", p, (5, 0, 0)) == "+"


# ── 平行轴锥：顶点 = 卡片前三项 ────────────────────────────────
def test_parallel_axis_cones_apex_is_first_three_params():
    p = [1.0, 2.0, 3.0, 0.25, 1.0]
    assert cone_frame("K/X", p).apex == (1.0, 2.0, 3.0)
    # K/X：径向 = (y,z)，轴向 = x；顶点在曲面上 → f≈0
    assert field("K/X", p)((1, 2, 3)) == pytest.approx(0.0)
    assert sign("K/X", p, (5, 2, 3)) == "-"      # u=4, r=0 < 2
    assert sign("K/X", p, (5, 2, 5.1)) == "+"    # r=2.1 > 2
    assert sign("K/X", p, (0, 2, 3)) == "+"      # 顶点平面另一侧
    # K/Y：径向 = (x,z)、轴向 = y
    assert sign("K/Y", p, (1, 5, 3)) == "-"
    assert sign("K/Y", p, (1, 5, 5.1)) == "+"
    assert sign("K/Y", p, (1, 0, 3)) == "+"


# ── 退化与参数不足 ───────────────────────────────────────────
def test_cone_frame_rejects_non_cone_and_short_params():
    with pytest.raises(ValueError):
        cone_frame("CZ", [1.0])
    with pytest.raises(ValueError):
        cone_frame("KZ", [0.0])
    with pytest.raises(ValueError):
        cone_frame("K/X", [0.0, 0.0, 0.0])


def test_cone_t_squared_zero_degenerates_to_axis():
    """t²≤0（非法/退化）：正侧近似全空间（只在轴线上取零）。"""
    f = field("KZ", [0.0, 0.0, 1.0])
    assert f((0, 5, 3)) > 0
    assert f((5, 0, 3)) > 0
    assert f((0, 0, 3)) == pytest.approx(0.0)


# ── 变换（*TRn）下仍在局部系求值 ───────────────────────────────
def test_cone_field_with_transform_stays_local():
    """带 TR 的锥面在局部系求值：世界点先减平移再判正负。"""
    tr = {"translate": [0.0, 0.0, 10.0], "rotate": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
          "inverse": True}
    f = surface_fn("KZ", [0.0, 0.25, 1.0], tr)
    v = lambda p: float(np.asarray(f(*p)).ravel()[0])
    assert v((0, 0, 15)) < 0    # 世界 (0,0,15) → 局部 (0,0,5)
    assert v((0, 0, 5)) > 0     # 局部 (0,0,-5)：另一叶 → 正侧
