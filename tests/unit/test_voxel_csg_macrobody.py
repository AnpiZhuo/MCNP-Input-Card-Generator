"""宏体拆解单测：app/voxel_csg.surface_fn 对全部宏体的内部/外部/边界判定。

契约 source-demo-visualization.md §2 宏体 → facet 拆解表。
约定：f<0 = 宏体内部、f>0 = 外部（MCNP「负号=内部」语义）。
"""
import numpy as np
import pytest

from app.voxel_csg import surface_fn


def _val(f, p):
    return float(np.asarray(f(p[0], p[1], p[2])).ravel()[0])


def assert_inside(t, params, pts):
    f = surface_fn(t, params)
    for p in pts:
        assert _val(f, p) < 0, f"{t} 点 {p} 应在内部"


def assert_outside(t, params, pts):
    f = surface_fn(t, params)
    for p in pts:
        assert _val(f, p) > 0, f"{t} 点 {p} 应在外部"


def test_rcc_cylinder():
    # 底 (0,0,0) 高 10 半径 2（沿 z）
    p = [0, 0, 0, 0, 0, 10, 2]
    assert_inside("RCC", p, [(0, 0, 5), (1.9, 0, 5), (0, 0, 0.01), (0, 0, 9.99)])
    assert_outside("RCC", p, [(0, 0, 11), (2.1, 0, 5), (0, 0, -0.01)])


def test_trc_cone():
    # 底半径 1 顶半径 3
    p = [0, 0, 0, 0, 0, 10, 1, 3]
    assert_inside("TRC", p, [(0, 0, 5)])
    assert_outside("TRC", p, [(4, 0, 5), (0, 0, 11)])


def test_rec_elliptic_cylinder():
    # 半轴 2,1 高 10
    p = [0, 0, 0, 0, 0, 10, 2, 0, 0, 0, 1, 0]
    assert_inside("REC", p, [(0, 0, 5), (1.9, 0, 5), (0, 0.9, 5)])
    assert_outside("REC", p, [(2.1, 0, 5), (0, 1.1, 5)])


def test_ell_ellipsoid():
    # 焦点 (0,0,-1),(0,0,1) 长轴半长 2
    p = [0, 0, -1, 0, 0, 1, 2]
    assert_inside("ELL", p, [(0, 0, 0), (1, 0, 0)])
    assert_outside("ELL", p, [(3, 0, 0)])


def test_box_parallelepiped():
    # 单位盒（正交边向量）
    p = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
    assert_inside("BOX", p, [(0.5, 0.5, 0.5), (0.1, 0.1, 0.1)])
    assert_outside("BOX", p, [(1.1, 0.5, 0.5), (-0.1, 0, 0)])


def test_wed_wedge():
    # 三角底 V=(0,0,0) V1=(2,0,0) V2=(0,2,0) 高 V3=(0,0,3)
    p = [0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 3]
    assert_inside("WED", p, [(0.5, 0.5, 1.5)])
    assert_outside("WED", p, [(3, 0, 1.5), (-0.1, 0, 1.5)])


def test_rhp_hexagonal_prism():
    # 底面中心 (0,0,0) 高 (0,0,10) R1=(2,0,0)（9 参，R2/R3 绕 H 转 60° 推断）
    p = [0, 0, 0, 0, 0, 10, 2, 0, 0]
    assert_inside("RHP", p, [(0, 0, 5), (1, 0, 5), (0, 1.5, 5)])
    assert_outside("RHP", p, [(2.5, 0, 5), (0, 2.5, 5), (0, 0, 11)])


def test_hex_same_as_rhp():
    p = [0, 0, 0, 0, 0, 10, 2, 0, 0]
    assert_inside("HEX", p, [(0, 0, 5)])
    assert_outside("HEX", p, [(3, 0, 5)])


def test_arb_cube():
    # 单位立方体 8 顶点 + 6 面定义（MCNP 编码：4 位数字，顶点 1-based）
    verts = [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1]
    face_defs = [1234, 5678, 1265, 2376, 3487, 4158]
    assert_inside("ARB", verts + face_defs, [(0.5, 0.5, 0.5)])
    assert_outside("ARB", verts + face_defs, [(1.5, 0.5, 0.5)])


def test_existing_surfaces_no_regression():
    """既有曲面类型零回退：RPP/SPH 及平面/球/柱仍正常。"""
    assert_inside("RPP", [-1, 1, -2, 2, -3, 3], [(0, 0, 0)])
    assert_outside("RPP", [-1, 1, -2, 2, -3, 3], [(2, 0, 0)])
    assert_inside("SPH", [0, 0, 0, 2], [(0, 0, 0)])
    assert_outside("SPH", [0, 0, 0, 2], [(3, 0, 0)])
    assert_inside("CZ", [2], [(0, 0, 0)])
    assert_outside("CZ", [2], [(3, 0, 0)])


def test_unsupported_type_raises():
    with pytest.raises(ValueError):
        surface_fn("TX", [0, 0, 0, 5, 2, 2])
