"""STEP 导入 GQ 薄栅元紧盒回归（2026-09-12 用户实测"有些栅元奇形怪状"）。

真实案例：用户导出再导入的 STEP（`mcnp_export.step`）里，GEOUNED 把模型拆成
18 个栅元，其中 7/8/9 号含 GQ 曲面（抛物线柱面）+ 两张平行 PZ 夹出的薄片：

    8    1 -1.000     128 -125 -113 112 127        Vol=38704.42   （5mm 薄片）
    9    1 -1.000     129 130 -124 -120 126         Vol=156514.10  （5mm 薄片）

两条独立缺陷叠加把它们变成"奇形怪状/直接消失"：

1. ``cell_aabb`` 对**裸平面引用**（MCNP 正侧，如 `112` = PZ400 正侧）返回 None
   —— 半边半空间信息丢失，薄片拿不到下界。
2. ``_aabb_intersect`` 按数值 max/min 合并，把「无界轴占位值」当真边界：
   `CZ` 的 z 占位 (0,0) 与 `-PZ405` 的 z≤405 相交 → z∈[0,0] → 紧盒退化 →
   `_clip_aabb_to_bound` 兜底整个 ±B 盒 → 体素边长 13mm → 5mm 薄片网格为空
   （3D 预览里该栅元没有 STL）。

本文件用真实 GQ 系数锁死这两点（纯 numpy，不需要 FreeCAD）。
"""
import numpy as np
import pytest

from app import voxel_csg

# 用户文件里的真实曲面（STEP 导入产物，系数原样）
GQ128 = [1.0, 0.25, 0.75, 0.0, -0.866025405677074, 0.0,
         0.0, 336.410162205612551, -582.679490575801651, 113162.796493220565026]
SURFACES = {
    112: {"number": 112, "type": "PZ", "params": [400.0], "transform": None},
    113: {"number": 113, "type": "CZ", "params": [50.0], "transform": None},
    125: {"number": 125, "type": "PZ", "params": [405.0], "transform": None},
    128: {"number": 128, "type": "GQ", "params": GQ128, "transform": None},
    127: {"number": 127, "type": "GQ", "params": GQ128, "transform": None},
}
B = 846.14  # 该模型 _compute_bound_from_surfaces 的实际值（粗扫间距 54mm）


def _cell8_ast():
    """8 号栅元：128 -125 -113 112 127（GQ 正侧 ∩ z<405 ∩ r<50 ∩ z>400 ∩ GQ 正侧）"""
    return ["intersect",
            ["intersect",
             ["intersect",
              ["intersect", ["surf", 128], ["unary", ["surf", 125], "neg"]],
              ["unary", ["surf", 113], "neg"]],
             ["surf", 112]],
            ["surf", 127]]


def _mesh_volume(vertices, triangles) -> float:
    if len(triangles) == 0:
        return 0.0
    a, b, c = vertices[triangles[:, 0]], vertices[triangles[:, 1]], vertices[triangles[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


# ── 1. 裸平面引用给半空间盒（缺陷 1）──
def test_bare_positive_plane_is_one_sided_halfspace():
    lo, hi, axes = voxel_csg.cell_aabb(["surf", 112], SURFACES, B)
    assert axes == (False, False, True), f"axes={axes}"
    assert lo[2] == 400.0 and hi[2] > B, f"lo={lo} hi={hi}"


def test_bare_positive_sphere_still_unbounded():
    """既有契约不回退：裸球引用仍须无界（壳栅元裁到球内会三角形爆炸）。"""
    sph = {1: {"number": 1, "type": "GQ",
               "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.0], "transform": None}}
    assert voxel_csg.cell_aabb(["surf", 1], sph, 10.0) is None


# ── 2. 紧盒不再被无界轴占位值污染（缺陷 2）──
def test_thin_slab_tight_box_is_not_degenerate():
    aabb = voxel_csg.cell_aabb(_cell8_ast(), SURFACES, B)
    assert aabb is not None
    lo, hi, axes = aabb
    assert axes == (True, True, True), f"axes={axes}"
    assert np.allclose(lo, [-50.0, -50.0, 400.0]), f"lo={lo}"
    assert np.allclose(hi, [50.0, 50.0, 405.0]), f"hi={hi}"


def test_intersect_ignores_unbounded_axis_placeholder():
    """直接锁合并语义：有界轴必须取自唯一有界的那侧。"""
    a = ((-1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (True, True, False))     # 类 CZ
    b = ((-1e300, -1e300, -1e300), (1e300, 1e300, 405.0),
         (False, False, True))                                        # 类 -PZ405
    lo, hi, axes = voxel_csg._aabb_intersect(a, b)
    assert axes == (True, True, True)
    assert (lo[0], hi[0]) == (-1.0, 1.0)
    assert (lo[1], hi[1]) == (-1.0, 1.0)
    assert hi[2] == 405.0 and lo[2] < -B, f"z 占位值污染: lo={lo} hi={hi}"


# ── 3. 端到端：5mm 薄片必须出网格，且体积对得上 GEOUNED（38704.42）──
def test_thin_gq_slab_meshes_with_right_volume():
    vertices, triangles = voxel_csg.mesh_cell_polydata(
        _cell8_ast(), SURFACES, {}, B)
    assert len(triangles) > 0, "5mm 薄片又变空网格（预览无 STL）"
    z = vertices[:, 2]
    assert z.max() - z.min() == pytest.approx(5.0, abs=0.3), \
        f"薄片厚度不对: {z.max() - z.min():.3f}"
    vol = _mesh_volume(vertices, triangles)
    assert vol == pytest.approx(38704.42, rel=0.05), f"体积 {vol:.1f}"


def test_tight_box_keeps_union_pieces_apart_from_bound():
    """union 里任一侧无界 → 该轴仍无界（不能凭空收紧）。"""
    a = ((-1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (True, True, False))
    b = ((-2.0, -2.0, 0.0), (2.0, 2.0, 0.0), (True, True, False))
    lo, hi, axes = voxel_csg._aabb_union(a, b)
    assert axes == (True, True, False)
    assert (lo[0], hi[0]) == (-2.0, 2.0)
    assert hi[2] >= B, "无界轴应给哨兵（由 _clip_aabb_to_bound 裁到 ±B）"
