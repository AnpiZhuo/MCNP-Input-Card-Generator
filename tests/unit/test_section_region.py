"""栅元区域判定单元测试（纯 numpy，不 import vtk / FreeCAD / pymcnp）。

锁的是 2026-10-07 用户实测的那类假几何：**切割平面与栅元边界面重合时，网格切会把那张
边界面当成"区域"**（用户卡 Z=0 上栅元 3/4 各切出一块半径 5 的盘、栅元 5 一块半径 0.5 的盘，
按定义这三个栅元在该平面上都不存在）。这里用合成几何复刻同三种形态。
"""

import numpy as np

from app.section_region import build_inside_fn, region_present


def _neg(n):
    return ["unary", ["surf", n], "neg"]


def _poly_loop(cx, cy, r, n=64):
    """z=0 平面上的正 n 边形环（{x,y,z} 字典，与后端响应同格式）。"""
    out = []
    for i in range(n):
        t = 2 * np.pi * i / n
        out.append({"x": cx + r * np.cos(t), "y": cy + r * np.sin(t), "z": 0.0})
    return out


def _surf(num, typ, params):
    return {num: {"number": num, "type": typ, "params": params, "transform": None}}


def _inter(*nodes):
    r = nodes[0]
    for nd in nodes[1:]:
        r = ["intersect", r, nd]
    return r


PLANE_Z0 = {"A": 0.0, "B": 0.0, "C": 1.0, "D": 0.0}

# 用户卡三个相关栅元的合成复刻（杆/球都在 (0,50)，与卡一致）
_CYL5 = _surf(104, "C/Z", [0.0, 50.0, 5.0])
_CYL05 = _surf(109, "C/Z", [0.0, 50.0, 0.5])
_PZ0 = _surf(112, "PZ", [0.0])
_SPH5 = _surf(110, "S", [0.0, 50.0, 0.0, 5.0])
_SPH45 = _surf(111, "S", [0.0, 50.0, 0.0, 4.5])


def test_boundary_artifact_is_dropped():
    """栅元 3 形态（`-104 113 110 -112`，z=0 是它的上界）⇒ 网格那块盘必须被剔除。"""
    surfaces = {**_CYL5, **_PZ0, **_SPH5}
    ast = _inter(_neg(104), _neg(112), ["surf", 110])      # ρ<5 ∧ z<0 ∧ 球(5)外
    disk = [_poly_loop(0.0, 50.0, 5.0)]                     # 网格在那个平面上切出的整盘
    assert region_present(ast, surfaces, {}, PLANE_Z0, hint_loops=disk) is False


def test_boundary_artifact_at_lower_face_is_dropped():
    """栅元 5 形态（`112 -109 -115`，z=0 是它的下界）⇒ 半径 0.5 的盘必须被剔除。"""
    surfaces = {**_PZ0, **_CYL05}
    ast = _inter(["surf", 112], _neg(109))                  # z>0 ∧ ρ<0.5
    disk = [_poly_loop(0.0, 50.0, 0.5)]
    assert region_present(ast, surfaces, {}, PLANE_Z0, hint_loops=disk) is False


def test_genuine_region_kept_even_with_hole_loop():
    """栅元 6 形态（`-102 100 106 -105`）：外环 + 内孔环 ⇒ **在**（孔环不影响判定）。"""
    surfaces = {**_surf(106, "C/Z", [0.0, 50.0, 6.0]),
                **_surf(105, "CZ", [49.0]),
                **_surf(100, "PY", [1.0]),
                **_surf(102, "PY", [100.0])}
    ast = _inter(_neg(102), ["surf", 100], ["surf", 106], _neg(105))
    outer = [_poly_loop(0.0, 25.0, 24.0)]                   # 大致覆盖水体那块
    hole = [_poly_loop(0.0, 50.0, 6.0)]                     # ρ<6 是它的**孔**（不在栅元内）
    assert region_present(ast, surfaces, {}, PLANE_Z0, hint_loops=outer) is True
    # 孔环也在候选里时不得把整个栅元判掉（孔环的"内部"不是该栅元的内部）
    assert region_present(ast, surfaces, {}, PLANE_Z0, hint_loops=outer + hole) is True


def test_annulus_region_kept():
    """栅元 2 形态（环带 4.5<ρ<5）⇒ 在（薄环带必须留着）。"""
    surfaces = {**_SPH5, **_SPH45, **_surf(107, "PZ", [4.472])}
    ast = _inter(_neg(110), _neg(107), ["surf", 111])
    ring = [_poly_loop(0.0, 50.0, 5.0)]
    assert region_present(ast, surfaces, {}, PLANE_Z0, hint_loops=ring) is True


def test_missing_surface_does_not_drop():
    """曲面缺失（无法判定）⇒ 返回 True（宁可保留，也不静默删几何）。"""
    assert build_inside_fn(_neg(999), {}, {}) is None
    assert region_present(_neg(999), {}, {}, PLANE_Z0, hint_loops=[_poly_loop(0, 0, 1)]) is True


def test_without_hint_loops_uses_cell_aabb():
    """不给候选环时用栅元 AABB 采样：球壳在 z=0 上有内部点 ⇒ 在；纯半空间 z>0 ⇒ 不在。"""
    surfaces = {**_SPH5}
    assert region_present(_neg(110), surfaces, {}, PLANE_Z0) is True
    assert region_present(["surf", 112], {**_PZ0}, {}, PLANE_Z0) is False


def test_plane_below_face_keeps_the_region():
    """同栅元下移 2 cm ⇒ 那块环带是真的（4.583<ρ<5）⇒ 保留。"""
    surfaces = {**_CYL5, **_PZ0, **_SPH5}
    ast = _inter(_neg(104), _neg(112), ["surf", 110])
    ring = [_poly_loop(0.0, 50.0, 5.0)]
    plane = {"A": 0.0, "B": 0.0, "C": 1.0, "D": -2.0}
    assert region_present(ast, surfaces, {}, plane, hint_loops=ring) is True
