"""体素 CSG + 纯 numpy marching cubes 单元测试。

铁律：本文件不 import vtk / FreeCAD / gui.backend.api_server；只 import numpy
与 app.voxel_csg / app.mc。水密断言统一用「每条无向边恰被 2 个三角形使用」
的边计数法（vtkFeatureEdges 对本套网格会误报边界边，勿用）。
"""

import time

import numpy as np
import pytest

from app import voxel_csg
from app.mc import marching_cubes


# ── 工具函数 ─────────────────────────────────────────────────
def _neg(n):
    return ["unary", ["surf", n], "neg"]


def _pos(n):
    return ["unary", ["surf", n], "pos"]


def _signed_volume(vertices, triangles):
    """有向网格体积：Σ dot(v0, cross(v1, v2)) / 6。"""
    v0 = vertices[triangles[:, 0]]
    v1 = vertices[triangles[:, 1]]
    v2 = vertices[triangles[:, 2]]
    return float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0)


def _centroid(vertices, triangles):
    """有向网格体积质心（对封闭外定向网格=真实质心）。"""
    v0 = vertices[triangles[:, 0]]
    v1 = vertices[triangles[:, 1]]
    v2 = vertices[triangles[:, 2]]
    vol = np.einsum("ij,ij->i", v0, np.cross(v1, v2)) / 6.0
    total = vol.sum()
    if abs(total) < 1e-30:
        return np.zeros(3)
    tetra_centroids = (v0 + v1 + v2) / 4.0
    return (tetra_centroids * vol[:, None]).sum(axis=0) / total


def _edge_counts(vertices, triangles):
    """统计无向边出现次数（水密网格应全部为 2）。"""
    e01 = triangles[:, [0, 1]]
    e12 = triangles[:, [1, 2]]
    e20 = triangles[:, [2, 0]]
    edges = np.sort(np.concatenate([e01, e12, e20], axis=0), axis=1)
    _unique, counts = np.unique(edges, axis=0, return_counts=True)
    return counts


def _assert_watertight(vertices, triangles):
    assert len(vertices) > 0 and len(triangles) > 0
    counts = _edge_counts(vertices, triangles)
    bad = counts[counts != 2]
    assert bad.size == 0, f"网格非水密：{bad.size} 条边计数 ≠ 2（max={counts.max() if counts.size else 0}）"


def _sphere_surface(num, radius=2.0):
    return {num: {"type": "GQ", "number": num,
                  "params": [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                             -radius * radius],
                  "transform": None}}


# ── GQ 球：体积 / 水密 / 朝向 ─────────────────────────────────
def test_gq_sphere_volume_watertight_and_orientation():
    """GQ 球 res=64：体积误差 ≤1%，水密，法线朝向一致（有向体积为正）。"""
    radius = 2.0
    surfaces = _sphere_surface(1, radius)
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        _neg(1), surfaces, {}, B=3.0, res=64)
    _assert_watertight(vertices, triangles)

    expected = 4.0 / 3.0 * np.pi * radius ** 3
    volume = _signed_volume(vertices, triangles)
    assert abs(volume - expected) / expected <= 0.01, (
        f"GQ 球体积误差超限：mesh={volume:.6f} analytical={expected:.6f}"
    )
    assert volume > 0, "外定向网格有向体积应为正"


# ── GQ 椭球 + TR 平移（交接文档实测铁证场景）──────────────
def test_gq_ellipsoid_tr_translation_center():
    """椭球 GQ + TR 平移 (5,0,0) → 网格质心必须为 (5,0,0)。"""
    surfaces = {1: {"type": "GQ", "number": 1,
                    "params": [0.25, 1.0, 1.0, 0.0, 0.0, 0.0,
                               0.0, 0.0, 0.0, -1.0],
                    "transform": 1}}
    tr_cards = {1: {"translate": [5.0, 0.0, 0.0],
                    "rotate": [[1.0, 0.0, 0.0],
                               [0.0, 1.0, 0.0],
                               [0.0, 0.0, 1.0]]}}
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        _neg(1), surfaces, tr_cards, B=10.0, res=64)
    _assert_watertight(vertices, triangles)

    center = _centroid(vertices, triangles)
    assert np.allclose(center, [5.0, 0.0, 0.0], atol=0.05), (
        f"TR 平移被忽略：网格质心 {center} 应≈(5,0,0)"
    )
    lo = vertices.min(axis=0)
    hi = vertices.max(axis=0)
    assert np.allclose((lo + hi) / 2.0, [5.0, 0.0, 0.0], atol=0.08)


def test_gq_ellipsoid_tr_rotation_bounds():
    """TR 旋转 90°（绕 Z）：局部 x 半轴 2 → 全局 y 方向拉长。

    rotate 采用 api_server.parse_tr_cards 的存储约定：行=局部轴在全局的
    方向余弦。Rz(90°) 的 B 矩阵为 [[0,1,0],[-1,0,0],[0,0,1]]。
    """
    surfaces = {1: {"type": "GQ", "number": 1,
                    "params": [0.25, 1.0, 1.0, 0.0, 0.0, 0.0,
                               0.0, 0.0, 0.0, -1.0],
                    "transform": 1}}
    tr_cards = {1: {"translate": [0.0, 0.0, 0.0],
                    "rotate": [[0.0, 1.0, 0.0],
                               [-1.0, 0.0, 0.0],
                               [0.0, 0.0, 1.0]]}}
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        _neg(1), surfaces, tr_cards, B=6.0, res=64)
    _assert_watertight(vertices, triangles)

    lo = vertices.min(axis=0)
    hi = vertices.max(axis=0)
    assert np.allclose(lo, [-1.0, -2.0, -1.0], atol=0.08), f"bounds lo={lo}"
    assert np.allclose(hi, [1.0, 2.0, 1.0], atol=0.08), f"bounds hi={hi}"


def test_surface_aabb_with_tr_returns_tight_global_box():
    """带 TR 的局部有界曲面 → 全局紧盒（TR 平移 (5,0,0) 的单位球 →
    x∈[4,6]，y/z∈[-1,1]）；无界曲面仍保守回退全盒。"""
    tr = {"translate": [5, 0, 0], "rotate": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    aabb = voxel_csg.surface_aabb(
        "GQ", [1, 1, 1, 0, 0, 0, 0, 0, 0, -1], tr)
    assert aabb is not None
    lo, hi, axes = aabb
    assert axes == (True, True, True)
    assert np.allclose(lo, [4.0, -1.0, -1.0], atol=1e-9), f"lo={lo}"
    assert np.allclose(hi, [6.0, 1.0, 1.0], atol=1e-9), f"hi={hi}"

    # 旋转 90°（绕 Z）：局部 x 半轴 1 → 全局 y，局部 y 半轴 1 → 全局 -x
    tr_r = {"translate": [0, 0, 0], "rotate": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]]}
    aabb_r = voxel_csg.surface_aabb(
        "GQ", [1, 1, 1, 0, 0, 0, 0, 0, 0, -1], tr_r)
    lo_r, hi_r, _ = aabb_r
    assert np.allclose(lo_r, [-1, -1, -1], atol=1e-9), f"lo={lo_r}"
    assert np.allclose(hi_r, [1, 1, 1], atol=1e-9), f"hi={hi_r}"

    # 无界曲面（PZ 半空间）带 TR：仍保守回退全盒
    aabb_pz = voxel_csg.surface_aabb(
        "PZ", [0.0], tr)
    lo_pz, hi_pz, axes_pz = aabb_pz
    assert axes_pz == (True, True, True)
    assert np.all(np.asarray(lo_pz) <= -1e200)
    assert np.all(np.asarray(hi_pz) >= 1e200)


# ── 复杂 AST：intersect / union / neg / complement ─────────────
def test_union_of_two_gq_spheres_watertight():
    """两个 GQ 球的 union：非空且水密。"""
    surfaces = {
        1: {"type": "GQ", "number": 1,
            "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.44], "transform": None},
        2: {"type": "GQ", "number": 2,
            "params": [1, 1, 1, 0, 0, 0, -3, 0, 0, 0.81], "transform": None},
    }
    # 球 2：中心 (1.5,0,0)，r=1.2 → x²+y²+z²-3x+2.25-1.44=0
    ast = ["union", _neg(1), _neg(2)]
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        ast, surfaces, {}, B=5.0, res=64)
    _assert_watertight(vertices, triangles)


def test_intersection_sphere_and_plane_watertight():
    """GQ 球 ∩ +PZ（z≥0 半空间）→ 半球网格，水密。"""
    surfaces = {
        1: {"type": "GQ", "number": 1,
            "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -2.25], "transform": None},
        2: {"type": "PZ", "number": 2, "params": [0.0], "transform": None},
    }
    ast = ["intersect", _neg(1), ["surf", 2]]
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        ast, surfaces, {}, B=3.0, res=64)
    _assert_watertight(vertices, triangles)

    expected = 0.5 * 4.0 / 3.0 * np.pi * 1.5 ** 3
    volume = _signed_volume(vertices, triangles)
    assert abs(volume - expected) / expected <= 0.02, (
        f"半球体积误差超限：mesh={volume:.6f} analytical={expected:.6f}"
    )


def test_complement_expression_watertight():
    """neg/complement 补集组合：`-1 : -2` 的并集，水密。"""
    surfaces = {
        1: {"type": "GQ", "number": 1,
            "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.0], "transform": None},
        2: {"type": "SQ", "number": 2,
            "params": [1, 1, 1, 0, 0, 0, -1.0, 3.0, 0.0, 0.0], "transform": None},
    }
    ast = ["union", ["unary", ["surf", 1], "complement"], _neg(2)]
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        ast, surfaces, {}, B=5.0, res=64)
    _assert_watertight(vertices, triangles)


# ── 空栅元 / 退化输入 ──────────────────────────────────────────
def test_empty_cell_returns_empty_mesh():
    """矛盾表达式（球内 ∩ 球外）→ 空网格。"""
    surfaces = _sphere_surface(1, 1.5)
    ast = ["intersect", _neg(1), _pos(1)]
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        ast, surfaces, {}, B=3.0, res=32)
    assert vertices.shape == (0, 3)
    assert triangles.shape == (0, 3)


def test_unsupported_surface_type_raises():
    """不支持的曲面类型 → 明确 ValueError（调用方回退/告警）。"""
    surfaces = {1: {"type": "TZ", "number": 1,
                    "params": [0, 0, 0, 1, 2, 3], "transform": None}}
    with pytest.raises(ValueError):
        voxel_csg.mesh_cell_polydata(_neg(1), surfaces, {}, B=3.0, res=16)


# ── mc.py 基础契约 ────────────────────────────────────────────
def test_marching_cubes_small_sphere_watertight():
    """直接测 mc.marching_cubes：小网格球，边计数法水密。"""
    n = 24
    x = np.linspace(-2.0, 2.0, n)
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")
    field = (X ** 2 + Y ** 2 + Z ** 2) <= 1.0
    vertices, triangles = marching_cubes(
        field, x, x, x,
        inside_fn=lambda a, b, c: (a ** 2 + b ** 2 + c ** 2) <= 1.0)
    _assert_watertight(vertices, triangles)


# ── 性能 ──────────────────────────────────────────────────────
def test_gq_sphere_res64_performance():
    """单栅元 res=64 预算 ≤100ms；CI 留 5 倍余量防环境抖动。"""
    surfaces = _sphere_surface(1, 2.0)
    t0 = time.perf_counter()
    voxel_csg.mesh_cell_polydata(_neg(1), surfaces, {}, B=3.0, res=64)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"res=64 单栅元耗时 {elapsed*1000:.0f}ms（预算 100ms）"


# ── 切线平面法快路径（借鉴 OWEN csgScene：凸二次曲面 + 平面封口 → 凸裁剪）──
def test_tangent_plane_sphere_fast_path():
    """球 GQ 走切线平面快路径：三角形数远小于 MC（~600 vs ~10 万），体积精确。"""
    surfaces = _sphere_surface(1, 2.0)
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        _neg(1), surfaces, {}, B=3.0, res=64)
    assert len(triangles) < 5000, (
        f"切线路径未生效：triangles={len(triangles)}（MC 级 ~10 万）"
    )
    _assert_watertight(vertices, triangles)
    expected = 4.0 / 3.0 * np.pi * 2.0 ** 3
    volume = _signed_volume(vertices, triangles)
    assert abs(volume - expected) / expected <= 0.005, (
        f"体积误差超限：{volume:.4f} vs {expected:.4f}"
    )


def test_tangent_plane_cylinder_fast_path():
    """圆柱 GQ（沿 z，r=1）走切线路径：三角形数少且水密。"""
    surfaces = {1: {"type": "GQ", "number": 1,
                    "params": [1.0, 1.0, 0.0, 0.0, 0.0, 0.0,
                               0.0, 0.0, 0.0, -1.0],
                    "transform": None}}
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        _neg(1), surfaces, {}, B=3.0, res=64)
    assert len(triangles) < 5000, (
        f"圆柱切线路径未生效：triangles={len(triangles)}"
    )
    _assert_watertight(vertices, triangles)


def test_tangent_plane_hemisphere_with_cap():
    """球 ∩ 平面封口：仍走切线路径（642 方向，无体积校正），水密且体积误差 ≤2%。"""
    surfaces = {
        1: {"type": "GQ", "number": 1,
            "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -2.25], "transform": None},
        2: {"type": "PZ", "number": 2, "params": [0.0], "transform": None},
    }
    ast = ["intersect", _neg(1), ["surf", 2]]
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        ast, surfaces, {}, B=3.0, res=64)
    assert len(triangles) < 10000, f"半球切线路径未生效：{len(triangles)}"
    _assert_watertight(vertices, triangles)
    expected = 0.5 * 4.0 / 3.0 * np.pi * 1.5 ** 3
    volume = _signed_volume(vertices, triangles)
    assert abs(volume - expected) / expected <= 0.02, (
        f"半球体积误差超限：{volume:.4f} vs {expected:.4f}"
    )


def test_union_falls_back_to_marching_cubes():
    """union 不满足切线路径模式 → 回退 MC（三角形数 ~10 万级）。"""
    surfaces = {
        1: {"type": "GQ", "number": 1,
            "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.44], "transform": None},
        2: {"type": "GQ", "number": 2,
            "params": [1, 1, 1, 0, 0, 0, -3, 0, 0, 0.81], "transform": None},
    }
    ast = ["union", _neg(1), _neg(2)]
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        ast, surfaces, {}, B=5.0, res=64)
    assert len(triangles) > 50000, (
        f"union 应回退 MC：triangles={len(triangles)}"
    )
    _assert_watertight(vertices, triangles)


# ---- regression: bare positive surface unbounded (2026-08-23 shell blowup) ----
def test_bare_positive_surface_aabb_is_unbounded():
    """MCNP bare surface ref = positive side (unbounded); cell_aabb must not return
    the surface's own AABB, otherwise shell/outside cells get clipped (288k tris)."""
    surfaces = _sphere_surface(1, 1.0)
    assert voxel_csg.cell_aabb(["surf", 1], surfaces, 10.0) is None
    assert voxel_csg.cell_aabb(_pos(1), surfaces, 10.0) is None


def test_cell_aabb_shell_takes_outer_partner():
    """shell '1 -3' (outside sphere1 & inside sphere3) tight box = outer [-2,2]."""
    surfaces = {
        1: {"type": "GQ", "number": 1,
            "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.0], "transform": None},
        3: {"type": "SQ", "number": 3,
            "params": [1, 1, 1, 0, 0, 0, -4.0, 0.0, 0.0, 0.0], "transform": None},
    }
    ast = ["intersect", ["surf", 1], _neg(3)]
    aabb = voxel_csg.cell_aabb(ast, surfaces, 10.0)
    assert aabb is not None
    lo, hi, axes = aabb
    assert axes == (True, True, True)
    assert np.allclose(lo, [-2.0, -2.0, -2.0], atol=1e-9), f"lo={lo}"
    assert np.allclose(hi, [2.0, 2.0, 2.0], atol=1e-9), f"hi={hi}"


def test_shell_mesh_covers_outer_extent():
    """shell '1 -3' mesh must span [-2,2] and stay triangle-bounded."""
    surfaces = {
        1: {"type": "GQ", "number": 1,
            "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.0], "transform": None},
        3: {"type": "SQ", "number": 3,
            "params": [1, 1, 1, 0, 0, 0, -4.0, 0.0, 0.0, 0.0], "transform": None},
    }
    ast = ["intersect", ["surf", 1], _neg(3)]
    vertices, triangles = voxel_csg.mesh_cell_polydata(ast, surfaces, {}, B=500.0)
    assert len(vertices) > 0 and len(triangles) > 0
    hi = vertices.max(axis=0)
    assert hi.min() > 1.8, f"outer shell clipped hi={hi}"
    assert hi.max() < 2.5, f"outer shell out of bounds hi={hi}"
    assert len(triangles) < 200000, f"triangle blowup {len(triangles)}"
