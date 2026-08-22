"""2D 解析切片单元测试（纯 numpy，不 import vtk / FreeCAD）。

铁律：本文件只 import numpy 与 app.analytic_slice / app.voxel_csg。
轮廓位置精度只取决于解析求值，测试用「所有轮廓点到解析曲线距离 ≤ 分辨率
量级容差」断言（res=128 时网格步长 ~0.03，容差取 0.08）。
"""

import numpy as np

from app.analytic_slice import analytic_cross_section


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


def test_gq_sphere_z0_circle_radius():
    """GQ 球 r=2 ∩ 平面 z=0 → 圆半径 ≈ 2（xy 平面）。"""
    ast = _neg(1)
    polys = analytic_cross_section(
        ast, _sphere_surface(1), {}, {"A": 0, "B": 0, "C": 1, "D": 0},
        bound=5.0, res=128)
    assert len(polys) == 1, f"期望 1 个轮廓，实际 {len(polys)}"
    pts = polys[0]
    assert len(pts) >= 8, "轮廓点数过少"
    r = np.sqrt(np.array([p["x"] ** 2 + p["y"] ** 2 for p in pts]))
    assert np.allclose(r, 2.0, atol=0.08), f"半径 {r.min():.4f}~{r.max():.4f}"
    # 轮廓应在 z=0 平面上
    assert np.allclose([p["z"] for p in pts], 0.0, atol=1e-9)


def test_gq_ellipsoid_tr_translation_plane_x5():
    """椭球(2,1,1) + TR 平移(5,0,0) ∩ 平面 x=5 → 圆 r=1（yz 平面）。"""
    surfaces = _ellipsoid_surface(1, transform=1)
    tr_cards = {1: {"translate": [5.0, 0.0, 0.0],
                    "rotate": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}}
    polys = analytic_cross_section(
        _neg(1), surfaces, tr_cards, {"A": 1, "B": 0, "C": 0, "D": 5},
        bound=10.0, res=128)
    assert len(polys) == 1, f"期望 1 个轮廓，实际 {len(polys)}"
    pts = polys[0]
    r = np.sqrt(np.array([p["y"] ** 2 + p["z"] ** 2 for p in pts]))
    assert np.allclose(r, 1.0, atol=0.08), f"半径 {r.min():.4f}~{r.max():.4f}"
    assert np.allclose([p["x"] for p in pts], 5.0, atol=1e-9)


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
    pts = np.array([[p["x"], p["y"], p["z"]] for p in polys[0]])
    assert np.allclose(pts[:, 0], 0.0, atol=1e-9)
    r = np.sqrt(pts[:, 1] ** 2 + pts[:, 2] ** 2)
    assert np.allclose(r, 1.0, atol=0.08), f"半径 {r.min():.4f}~{r.max():.4f}"
