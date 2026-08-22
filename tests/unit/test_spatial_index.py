"""AABB 空间索引测试：候选对生成与新增单查询。"""

from app.spatial_index import (
    aabb_overlap_volume, grid_candidates, query_new_vs_existing,
)


def test_aabb_overlap_volume():
    lo = (-1, -1, -1)
    hi = (1, 1, 1)
    assert aabb_overlap_volume(lo, hi, (0, 0, 0), (2, 2, 2)) == 1.0
    assert aabb_overlap_volume(lo, hi, (2, 0, 0), (3, 1, 1)) == 0.0
    # 共享面（只碰边）→ 0
    assert aabb_overlap_volume(lo, hi, (1, 0, 0), (2, 1, 1)) == 0.0


def test_grid_candidates_only_adjacent():
    # 三个并排盒：0-1 相邻（共享面→0 体积不计），0-2 相隔
    cells = {
        0: ((-1, -1, -1), (0, 1, 1)),
        1: ((0, -1, -1), (1, 1, 1)),
        2: ((5, -1, -1), (6, 1, 1)),
    }
    pairs = grid_candidates(cells)
    assert pairs == []  # 共享面体积 0、相隔盒不相交 → 无候选

    # 让 1 与 0 真正交叠
    cells2 = {
        0: ((-1, -1, -1), (1, 1, 1)),
        1: ((0, 0, 0), (2, 2, 2)),
        2: ((10, 10, 10), (11, 11, 11)),
    }
    pairs2 = grid_candidates(cells2)
    assert len(pairs2) == 1
    assert (pairs2[0]["a"], pairs2[0]["b"]) in ((0, 1), (1, 0))
    assert pairs2[0]["bbox_volume"] > 0


def test_grid_candidates_no_duplicates():
    cells = {i: ((i, 0, 0), (i + 1.5, 1, 1)) for i in range(4)}  # 链式相邻
    pairs = grid_candidates(cells)
    keys = {tuple(sorted((p["a"], p["b"]))) for p in pairs}
    assert len(keys) == len(pairs)  # 无重复


def test_query_new_vs_existing():
    existing = {
        1: ((0, 0, 0), (1, 1, 1)),
        2: ((2, 2, 2), (3, 3, 3)),
        3: ((0.5, 0.5, 0.5), (1.5, 1.5, 1.5)),
    }
    hits = query_new_vs_existing((0.8, 0.8, 0.8), (1.2, 1.2, 1.2), existing)
    nums = {h["num"] for h in hits}
    assert nums == {1, 3}
    assert 2 not in nums
    # 按 bbox 交叠体积降序
    vols = [h["bbox_volume"] for h in hits]
    assert vols == sorted(vols, reverse=True)
