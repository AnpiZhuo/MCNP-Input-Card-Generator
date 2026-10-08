"""二进制 STL 变换/包围盒单元测试（纯 numpy，不 import FreeCAD）。

用途（用户 2026-10-08）：STEP 方向预览要"点一下就能看、切换上轴即时重画" ——
镶嵌一次（FreeCAD 子进程），此后每次切换只在主进程做矩阵（本模块）。
矩阵来自 `app/cad_orientation.py` 单一来源；本测试顺带锁住"变换与约定一致"。
"""

import numpy as np
import pytest

from app.cad_orientation import matrix_cad_to_mcnp, translation_for
from app.stl_transform import bbox_of, parse_binary_stl, transform, write_binary_stl


def _box_tris(x0, y0, z0, x1, y1, z1):
    """轴对齐盒子的 12 个三角形（够做包围盒/变换断言即可）。"""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (3, 7, 6), (3, 6, 2), (1, 2, 6), (1, 6, 5), (0, 4, 7), (0, 7, 3)]
    return np.array([[v[i] for i in f] for f in faces], dtype=np.float64)


def test_stl_roundtrip_keeps_bbox():
    tris = _box_tris(10, 20, 30, 11, 21, 31)
    blob = write_binary_stl(tris)
    assert parse_binary_stl(blob).shape == (12, 3, 3)
    lo, hi = bbox_of(parse_binary_stl(blob))
    assert lo == pytest.approx((10, 20, 30))
    assert hi == pytest.approx((11, 21, 31))
    assert bbox_of(np.zeros((0, 3, 3))) is None


def test_identity_transform_is_stable():
    blob = write_binary_stl(_box_tris(0, 0, 0, 2, 3, 4))
    same = transform(blob, ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    assert bbox_of(parse_binary_stl(same))[1] == pytest.approx((2, 3, 4))


def test_y_up_convention_matches_matrix():
    """上轴 Y 约定：预览里的网格必须落在 `matrix_cad_to_mcnp` 算出的位置（与真正导入同一口径）。"""
    blob = write_binary_stl(_box_tris(10, 20, 30, 11, 21, 31))
    moved = transform(blob, matrix_cad_to_mcnp({"up": "Y"}))
    lo, hi = bbox_of(parse_binary_stl(moved))
    # (x, y, z) → (x, −z, y)：x 10-11 / y −31..−30 / z 20-21
    assert lo == pytest.approx((10, -31, 20))
    assert hi == pytest.approx((11, -30, 21))


def test_origin_center_and_bottom_shifts():
    """原点口径：体心归零 / 坐在底面上（预览里就按这个平移，和后端一致）。"""
    blob = write_binary_stl(_box_tris(10, 20, 30, 11, 21, 31))
    bbox = bbox_of(parse_binary_stl(blob))
    centered = transform(blob, ((1, 0, 0), (0, 1, 0), (0, 0, 1)), translation_for(bbox, "center"))
    lo, hi = bbox_of(parse_binary_stl(centered))
    assert lo == pytest.approx((-0.5, -0.5, -0.5)) and hi == pytest.approx((0.5, 0.5, 0.5))
    bottom = transform(blob, ((1, 0, 0), (0, 1, 0), (0, 0, 1)), translation_for(bbox, "bottom", "Z"))
    lo, hi = bbox_of(parse_binary_stl(bottom))
    assert lo == pytest.approx((-0.5, -0.5, 0.0)) and hi == pytest.approx((0.5, 0.5, 1.0))


def test_normals_are_recomputed_not_stale():
    """法向按变换后的绕向重算 —— 旋转后法向必须等于 R·原法向（否则着色全反）。"""
    tris = _box_tris(0, 0, 0, 1, 1, 1)
    m = ((0, -1, 0), (1, 0, 0), (0, 0, 1))     # 绕 Z 转 +90°

    def facet_normal(t):
        n = np.cross(t[1] - t[0], t[2] - t[0])
        return n / max(float(np.linalg.norm(n)), 1e-12)

    before = facet_normal(tris[0])
    out = parse_binary_stl(transform(write_binary_stl(tris), m))
    after = facet_normal(out[0])
    assert float(np.linalg.norm(after)) == pytest.approx(1.0, abs=1e-6)
    assert after == pytest.approx(np.asarray(m, dtype=float) @ before, abs=1e-6)
