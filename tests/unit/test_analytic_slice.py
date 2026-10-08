"""2D 解析切片单元测试（纯 numpy，不 import vtk / FreeCAD）。

铁律：本文件只 import numpy 与 app.analytic_slice / app.voxel_csg。

**精度口径（2026-10-07 改写）**：轮廓顶点由二分法落在真实零水平集上，位置误差
**与 res 无关**（实测 ≤1e-6）；res 只决定拓扑（薄特征是否被采到）与折线密度。
旧实现的顶点取**栅格边中点**，误差是"半格"量级且随 res 变（实测球 R=100：
res=32/64/128/256 → 3.17/1.35/0.78/0.40 cm），故本文件用 1e-6 级容差锁住新口径。

**语义口径**：切割平面恰是栅元边界面（或与栅元内部无交）时返回**空集**，且这是
**权威结论** —— 调用方不得据此回落网格切（网格会把那张边界面当成区域，造出假几何）。
"""

import numpy as np

from app.analytic_slice import analytic_cross_section, model_bound


def _neg(n):
    return ["unary", ["surf", n], "neg"]


def _ellipsoid_surface(num, transform=None):
    """局部 x 半轴 2、y/z 半轴 1 的椭球 GQ（可选 transform）。"""
    return {num: {"type": "GQ", "number": num,
                  "params": [0.25, 1.0, 1.0, 0.0, 0.0, 0.0,
                             0.0, 0.0, 0.0, -1.0],
                  "transform": transform}}


def _sphere_surface(num, radius=2.0):
    return {num: {"type": "GQ", "number": num,
                  "params": [1.0, 1.0, 1.0, 0.0, 0.0, 0.0,
                             0.0, 0.0, 0.0, -radius * radius],
                  "transform": None}}


def _s_surface(num, cx, cy, cz, r):
    """球 S：正侧 = 球外（体素场约定 x²+y²+z²−r² ≥ 0）。"""
    return {num: {"type": "S", "number": num, "params": [cx, cy, cz, r],
                  "transform": None}}


def _cz_surface(num, radius):
    return {num: {"type": "CZ", "number": num, "params": [radius], "transform": None}}


def _pz_surface(num, z):
    return {num: {"type": "PZ", "number": num, "params": [z], "transform": None}}


def _radii_in_plane(poly, ax=0, ay=1):
    pts = np.array([[p["x"], p["y"], p["z"]] for p in poly])
    return np.hypot(pts[:, ax], pts[:, ay]), pts


def test_gq_sphere_z0_circle_radius():
    """GQ 球 r=2 ∩ 平面 z=0 → 圆半径 ≈ 2（xy 平面）。"""
    ast = _neg(1)
    polys = analytic_cross_section(
        ast, _sphere_surface(1), {}, {"A": 0, "B": 0, "C": 1, "D": 0},
        bound=5.0, res=128)
    assert len(polys) == 1, f"期望 1 个轮廓，实际 {len(polys)}"
    assert len(polys[0]) >= 8, "轮廓点数过少"
    r, _ = _radii_in_plane(polys[0])
    assert np.allclose(r, 2.0, atol=0.08), f"半径 {r.min():.4f}~{r.max():.4f}"
    # 轮廓应在 z=0 平面上
    assert np.allclose([p["z"] for p in polys[0]], 0.0, atol=1e-9)


def test_gq_ellipsoid_tr_translation_plane_x5():
    """椭球(2,1,1) + TR 平移(5,0,0) ∩ 平面 x=5 → 圆 r=1（yz 平面）。"""
    surfaces = _ellipsoid_surface(1, transform=1)
    tr_cards = {1: {"translate": [5.0, 0.0, 0.0],
                    "rotate": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}}
    polys = analytic_cross_section(
        _neg(1), surfaces, tr_cards, {"A": 1, "B": 0, "C": 0, "D": 5},
        bound=10.0, res=128)
    assert len(polys) == 1, f"期望 1 个轮廓，实际 {len(polys)}"
    r, _ = _radii_in_plane(polys[0], ax=1, ay=2)
    assert np.allclose(r, 1.0, atol=0.08), f"半径 {r.min():.4f}~{r.max():.4f}"
    assert np.allclose([p["x"] for p in polys[0]], 5.0, atol=1e-9)


def test_gq_ellipsoid_tr_plane_z0_ellipse_bounds():
    """椭球(2,1,1) + TR ∩ 平面 z=0 → 椭圆 x∈[3,7]、y∈[±1]。"""
    surfaces = _ellipsoid_surface(1, transform=1)
    tr_cards = {1: {"translate": [5.0, 0.0, 0.0],
                    "rotate": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}}
    polys = analytic_cross_section(
        _neg(1), surfaces, tr_cards, {"A": 0, "B": 0, "C": 1, "D": 0},
        bound=10.0, res=128)
    assert len(polys) == 1
    pts = np.array([[p["x"], p["y"], p["z"]] for p in polys[0]])
    lo = pts.min(axis=0)
    hi = pts.max(axis=0)
    assert np.allclose(lo, [3.0, -1.0, 0.0], atol=0.1), f"lo={lo}"
    assert np.allclose(hi, [7.0, 1.0, 0.0], atol=0.1), f"hi={hi}"
    # 椭圆方程：((x-5)/2)² + y² = 1
    f = ((pts[:, 0] - 5.0) / 2.0) ** 2 + pts[:, 1] ** 2
    assert np.allclose(f, 1.0, atol=0.08), f"椭圆残差 {np.abs(f - 1).max():.4f}"


def test_plane_misses_cell_returns_empty():
    """平面 z=10 与 [-5,5]³ 内球不相交 → 空轮廓。"""
    polys = analytic_cross_section(
        _neg(1), _sphere_surface(1), {}, {"A": 0, "B": 0, "C": 1, "D": 10},
        bound=5.0, res=64)
    assert polys == []


def test_tilted_plane_ellipsoid_circle():
    """椭球(2,1,1)（无 TR）∩ 平面 x=0 → yz 截面圆 r=1。"""
    polys = analytic_cross_section(
        _neg(1), _ellipsoid_surface(1), {},
        {"A": 1, "B": 0, "C": 0, "D": 0},
        bound=5.0, res=128)
    assert len(polys) == 1
    r, pts = _radii_in_plane(polys[0], ax=1, ay=2)
    assert np.allclose(pts[:, 0], 0.0, atol=1e-9)
    assert np.allclose(r, 1.0, atol=0.08), f"半径 {r.min():.4f}~{r.max():.4f}"


# ─────────────── 2026-10-07 新增：位置精度 / 孔洞 / 边界面语义 / 求值盒 ───────────────

def test_contour_position_is_res_independent():
    """球 r=2 ∩ z=0：轮廓点必须落在真实圆上，**与 res 无关**。

    旧实现顶点取栅格边中点 ⇒ 半径误差 ≈ 半个步长（res=32 时约 6e-2，且随 res 变），
    本条会红；改成二分法后误差 ≤1e-6。
    """
    for res in (32, 64, 128, 256):
        polys = analytic_cross_section(
            _neg(1), _sphere_surface(1), {}, {"A": 0, "B": 0, "C": 1, "D": 0},
            bound=5.0, res=res)
        assert len(polys) == 1, f"res={res} 轮廓数 {len(polys)}"
        r, _ = _radii_in_plane(polys[0])
        err = float(np.abs(r - 2.0).max())
        assert err < 1e-6, f"res={res} 最大半径误差 {err:.3e}（旧实现在此量级为 ~6e-2）"


def test_annulus_cell_two_loops():
    """环带栅元（球 r=5 内、球 r=4.5 外）∩ z=0 → 两个环：外 ≈5、内 ≈4.5。

    用户卡上栅元 2（石墨）在 Z=0 就是这个形状；前端靠"奇偶"把内环认成孔。
    """
    surfaces = {**_s_surface(1, 0, 0, 0, 5.0), **_s_surface(2, 0, 0, 0, 4.5)}
    ast = ["intersect", _neg(1), ["surf", 2]]
    polys = analytic_cross_section(
        ast, surfaces, {}, {"A": 0, "B": 0, "C": 1, "D": 0}, bound=8.0, res=160)
    assert len(polys) == 2, f"期望外环+内孔两个环，实际 {len(polys)}"
    means = sorted(float(_radii_in_plane(p)[0].mean()) for p in polys)
    assert abs(means[0] - 4.5) < 1e-3, f"内环半径 {means[0]:.6f}"
    assert abs(means[1] - 5.0) < 1e-3, f"外环半径 {means[1]:.6f}"


def test_two_disjoint_disks_two_loops():
    """同一栅元的两块不连通实体（并集）∩ z=0 → 两个独立环，各自是半径 2 的圆。"""
    surfaces = {**_s_surface(1, -10, 0, 0, 2.0), **_s_surface(2, 10, 0, 0, 2.0)}
    ast = ["union", _neg(1), _neg(2)]
    polys = analytic_cross_section(
        ast, surfaces, {}, {"A": 0, "B": 0, "C": 1, "D": 0}, bound=14.0, res=200)
    assert len(polys) == 2, f"期望两个环，实际 {len(polys)}"
    # 每个环是半径 2 的圆：中心取自身包围盒中点（顶点均值会被离散采样偏掉），
    # 半径按该中心算（不是按原点 —— 圆心在 ±10）。
    centers = []
    for poly in polys:
        _, pts = _radii_in_plane(poly)
        cx = float((pts[:, 0].min() + pts[:, 0].max()) / 2)
        cy = float((pts[:, 1].min() + pts[:, 1].max()) / 2)
        r = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
        assert abs(float(r.mean()) - 2.0) < 0.02, f"环半径 {r.mean():.6f}"
        centers.append(cx)
    centers.sort()
    assert abs(centers[0] + 10.0) < 0.05 and abs(centers[1] - 10.0) < 0.05, centers


def test_face_coincident_cell_is_empty_and_present_below():
    """切割平面恰是栅元的边界面 ⇒ **空集**；同栅元下移 2 cm 就有轮廓。

    复刻用户卡 Z=0（正是面 112 `PZ 0.000`）上的栅元 3/4：`ρ<5 ∧ z<0 ∧ 球(5)外`。
    网格切会把这张**边界面**当成区域，切出一块半径 5 的整盘（实测面积 π·5² = 78.5 的假几何）；
    按定义求值，z=0 处该栅元是空的（`z<0` 与"球外且在球内"两处都不成立）。
    """
    surfaces = {**_cz_surface(1, 5.0), **_pz_surface(2, 0.0), **_s_surface(3, 0, 0, 0, 5.0)}
    ast = ["intersect", ["intersect", _neg(1), _neg(2)], ["surf", 3]]

    at_face = analytic_cross_section(
        ast, surfaces, {}, {"A": 0, "B": 0, "C": 1, "D": 0}, bound=8.0, res=128)
    assert at_face == [], f"切在边界面上应为空集，实际 {len(at_face)} 个环"

    below = analytic_cross_section(
        ast, surfaces, {}, {"A": 0, "B": 0, "C": 1, "D": -2.0}, bound=8.0, res=160)
    # z=-2 处区域 = {ρ<5 ∧ ρ²+4>25} = 环带 4.583<ρ<5 ⇒ 边界是**两个**环
    assert len(below) == 2, f"z=-2 处环带应有 2 个环，实际 {len(below)}"
    for poly in below:
        _, pts = _radii_in_plane(poly)
        assert abs(float(pts[:, 2].mean()) + 2.0) < 1e-9, "轮廓应落在 z=-2 平面上"
    means = sorted(float(_radii_in_plane(p)[0].mean()) for p in below)
    assert abs(means[0] - np.sqrt(21.0)) < 1e-3, f"内边界 {means[0]:.6f}（应 √21=4.5826）"
    assert abs(means[1] - 5.0) < 1e-3, f"外边界 {means[1]:.6f}"


def test_boundary_only_contact_is_not_interior():
    """切割平面恰是栅元边界面 ⇒ 空集；同栅元上移 1 cm ⇒ 半径 0.5 的圆。

    复刻用户卡栅元 5（`112 -109 -115` = `z>0 ∧ ρ<0.5 ∧ z<50`，z=0 是它的下界）。
    MCNP 的曲面感度是**严格**的：面上的点不属于任何一侧 ⇒ 该栅元在 z=0 上不存在。
    布尔版求值（`f >= 0` 配 `~field`）会把 `z=0` 算成"在 z>0 里"，凭空给出一块盘。
    """
    surfaces = {**_pz_surface(2, 0.0), **_cz_surface(4, 0.5), **_pz_surface(5, 50.0)}
    ast = ["intersect", ["intersect", ["surf", 2], _neg(4)], _neg(5)]

    at_face = analytic_cross_section(
        ast, surfaces, {}, {"A": 0, "B": 0, "C": 1, "D": 0}, bound=10.0, res=64)
    assert at_face == [], f"平面恰是边界面时应为空集，实际 {len(at_face)} 个环"

    above = analytic_cross_section(
        ast, surfaces, {}, {"A": 0, "B": 0, "C": 1, "D": 1.0}, bound=10.0, res=64)
    assert len(above) == 1, f"z=1 处应有 1 个圆环，实际 {len(above)}"
    r, pts = _radii_in_plane(above[0])
    assert abs(float(pts[:, 2].mean()) - 1.0) < 1e-9
    assert abs(float(r.mean()) - 0.5) < 1e-6, f"半径 {r.mean():.9f}"


def test_model_bound_unclips_big_cell():
    """求值盒半边长随模型量级走 —— 写死 500 会让 R=600 的球整个落在盒外（返回空）。"""
    surfaces = _s_surface(1, 0, 0, 0, 600.0)
    b = model_bound(surfaces)
    assert b >= 600.0, f"model_bound={b}"

    polys = analytic_cross_section(
        _neg(1), surfaces, {}, {"A": 0, "B": 0, "C": 1, "D": 0}, bound=None, res=96)
    assert len(polys) == 1, f"R=600 应出 1 个环，实际 {len(polys)}（bound 写死 500 时为空）"
    r, _ = _radii_in_plane(polys[0])
    assert abs(float(r.mean()) - 600.0) < 0.05, f"平均半径 {r.mean():.6f}"
