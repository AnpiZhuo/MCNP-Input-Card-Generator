"""stl_cross_section 回归测试 —— 纯 numpy/stdlib 合成二进制 STL，不依赖 FreeCAD。

覆盖两个用户实测 bug：
1. 切割平面与实体面重合（face-coincident）时旧实现返回空环/错环
   （slice_stl_segments 对 on-plane 顶点直接 continue，共面三角面不贡献轮廓边）。
2. 多环截面（带孔/多连通）不得被最近点贪心连接串成一条错误折线。

与生产同管线：cross_section_from_stl(path, A, B, C, D)。
"""
import struct
from pathlib import Path

import numpy as np

from app.stl_cross_section import cross_section_from_stl


def _write_binary_stl(path: Path, tris) -> None:
    """写二进制 STL（80B 头 + uint32 三角形数 + 每三角 50B）。"""
    with open(path, "wb") as f:
        f.write(b"\0" * 80)
        f.write(struct.pack("<I", len(tris)))
        for tri in tris:
            f.write(b"\0" * 12)  # 法向（切片不用）
            for v in tri:
                f.write(struct.pack("<3f", *(float(x) for x in v)))
            f.write(b"\0\0")


def _box(x0, x1, y0, y1, z0, z1):
    """坐标轴对齐盒子的 12 个三角形（两两成面）。"""
    v = [
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],  # z0 面
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],  # z1 面
    ]
    faces = [
        [0, 2, 1], [0, 3, 2],  # bottom
        [4, 5, 6], [4, 6, 7],  # top
        [0, 1, 5], [0, 5, 4],  # y0
        [3, 7, 6], [3, 6, 2],  # y1
        [1, 2, 6], [1, 6, 5],  # x1
        [0, 4, 7], [0, 7, 3],  # x0
    ]
    return [[v[i] for i in f] for f in faces]


def _quad(tris, p0, p1, p2, p3):
    tris.append([p0, p1, p2])
    tris.append([p0, p2, p3])


def _frame(x0, x1, y0, y1, z0, z1, ix0, ix1, iy0, iy1):
    """外盒 − 内盒（Z 向通孔）的 32 三角形。"""
    tris = []
    # 外盒四个侧面
    _quad(tris, [x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1])  # x0
    _quad(tris, [x1, y0, z0], [x1, y0, z1], [x1, y1, z1], [x1, y1, z0])  # x1
    _quad(tris, [x0, y0, z0], [x0, y0, z1], [x1, y0, z1], [x1, y0, z0])  # y0
    _quad(tris, [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1])  # y1
    # 顶/底面环（外方 − 内方）
    for z in (z0, z1):
        _quad(tris, [x0, y0, z], [x1, y0, z], [x1, iy0, z], [x0, iy0, z])
        _quad(tris, [x0, iy1, z], [x1, iy1, z], [x1, y1, z], [x0, y1, z])
        _quad(tris, [x0, iy0, z], [ix0, iy0, z], [ix0, iy1, z], [x0, iy1, z])
        _quad(tris, [ix1, iy0, z], [x1, iy0, z], [x1, iy1, z], [ix1, iy1, z])
    # 内孔四个侧面
    _quad(tris, [ix0, iy0, z0], [ix0, iy1, z0], [ix0, iy1, z1], [ix0, iy0, z1])
    _quad(tris, [ix1, iy0, z0], [ix1, iy0, z1], [ix1, iy1, z1], [ix1, iy1, z0])
    _quad(tris, [ix0, iy0, z0], [ix0, iy0, z1], [ix1, iy0, z1], [ix1, iy0, z0])
    _quad(tris, [ix0, iy1, z0], [ix1, iy1, z0], [ix1, iy1, z1], [ix0, iy1, z1])
    return tris


def _corners(loop, use_xy=True):
    """取环点集的 (x,y) 或 (y,z) 坐标（按切割平面法向选投影面）。"""
    out = set()
    for p in loop:
        out.add((round(p["x"], 4), round(p["y"], 4)) if use_xy
                else (round(p["y"], 4), round(p["z"], 4)))
    return out


def _assert_corners(loop, expected, use_xy=True):
    """环点集须包含全部期望角点（允许含三角形边中点等冗余点）。"""
    corners = _corners(loop, use_xy=use_xy)
    assert expected.issubset(corners), (expected, corners)


def test_mid_cut_box_returns_square(tmp_path):
    stl = tmp_path / "box.stl"
    _write_binary_stl(stl, _box(-1, 1, -1, 1, -1, 1))
    loops = cross_section_from_stl(str(stl), 1, 0, 0, 0)
    assert len(loops) == 1
    _assert_corners(loops[0], {
        (-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0),
    }, use_xy=False)


def test_face_coincident_cut_box_returns_face(tmp_path):
    """切割平面恰与盒子 +x 面重合：应返回该面轮廓（此前返回 0 环）。"""
    stl = tmp_path / "box.stl"
    _write_binary_stl(stl, _box(-1, 1, -1, 1, -1, 1))
    loops = cross_section_from_stl(str(stl), 1, 0, 0, 1)
    assert len(loops) == 1
    _assert_corners(loops[0], {
        (-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0),
    }, use_xy=False)


def test_cut_outside_box_empty(tmp_path):
    stl = tmp_path / "box.stl"
    _write_binary_stl(stl, _box(-1, 1, -1, 1, -1, 1))
    assert cross_section_from_stl(str(stl), 1, 0, 0, 1.5) == []


def test_disjoint_boxes_stay_two_loops(tmp_path):
    """同一 STL 内两个沿 Y 并排的盒子：同一平面切出两个独立环，不得串接。"""
    tris = _box(-1, 1, -2, -1, -1, 1) + _box(-1, 1, 1, 2, -1, 1)
    stl = tmp_path / "two.stl"
    _write_binary_stl(stl, tris)
    loops = cross_section_from_stl(str(stl), 1, 0, 0, 0)
    assert len(loops) == 2
    corner_sets = {frozenset(_corners(loop, use_xy=False)) for loop in loops}
    left = {(-2.0, -1.0), (-2.0, 1.0), (-1.0, -1.0), (-1.0, 1.0)}
    right = {(1.0, -1.0), (1.0, 1.0), (2.0, -1.0), (2.0, 1.0)}
    assert any(left.issubset(s) for s in corner_sets)
    assert any(right.issubset(s) for s in corner_sets)


def test_frame_mid_cut_two_loops(tmp_path):
    """带孔实体正中切割：外方框 + 内方孔两个独立环。"""
    stl = tmp_path / "frame.stl"
    _write_binary_stl(stl, _frame(-1, 1, -1, 1, -1, 1, -0.5, 0.5, -0.5, 0.5))
    loops = cross_section_from_stl(str(stl), 0, 0, 1, 0)
    assert len(loops) == 2
    corner_sets = {frozenset(_corners(loop)) for loop in loops}
    outer = {(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)}
    inner = {(-0.5, -0.5), (-0.5, 0.5), (0.5, -0.5), (0.5, 0.5)}
    assert any(outer.issubset(s) for s in corner_sets)
    assert any(inner.issubset(s) for s in corner_sets)


def test_frame_face_coincident_cut_two_loops(tmp_path):
    """带孔实体顶面切割（平面与顶面重合）：外方框 + 内方孔两环（此前返回 0 环/串环）。"""
    stl = tmp_path / "frame.stl"
    _write_binary_stl(stl, _frame(-1, 1, -1, 1, -1, 1, -0.5, 0.5, -0.5, 0.5))
    loops = cross_section_from_stl(str(stl), 0, 0, 1, 1)
    assert len(loops) == 2
    corner_sets = {frozenset(_corners(loop)) for loop in loops}
    outer = {(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)}
    inner = {(-0.5, -0.5), (-0.5, 0.5), (0.5, -0.5), (0.5, 0.5)}
    assert any(outer.issubset(s) for s in corner_sets)
    assert any(inner.issubset(s) for s in corner_sets)
