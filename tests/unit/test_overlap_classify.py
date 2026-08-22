"""重合分类纯函数测试（severity 表 / 容差 / 探针降级 / 截断）。"""

from app.overlap_classify import (
    cap_by_bbox_volume, classify_overlaps,
    DEFAULT_VOL_FLOOR_ABS, DEFAULT_VOL_FLOOR_REL,
)


def _meta(empty_mats=True):
    return {1: {"material": "1"}, 2: {"material": "2"}, 3: {"material": "0"},
            4: {"material": "4"}}


def test_material_material_error_and_warning():
    meta = _meta()
    r = classify_overlaps([
        {"a": 1, "b": 2, "volume": 5.0, "vol_a": 10.0, "vol_b": 10.0,
         "method": "boolean"},   # frac 0.5 → error
        {"a": 1, "b": 4, "volume": 0.5, "vol_a": 10.0, "vol_b": 10.0,
         "method": "boolean"},   # frac 0.05 → warning
    ], meta)
    by = {(o["a"], o["b"]): o for o in r["overlaps"]}
    assert by[(1, 2)]["severity"] == "error"
    assert by[(1, 4)]["severity"] == "warning"


def test_void_downgrades_severity():
    meta = _meta()
    r = classify_overlaps([
        {"a": 1, "b": 3, "volume": 5.0, "vol_a": 10.0, "vol_b": 10.0,
         "method": "boolean"},   # 含真空，frac 0.5 → warning（非 error）
    ], meta)
    assert r["overlaps"][0]["severity"] == "warning"


def test_probe_suspected_downgrade():
    meta = _meta()
    r = classify_overlaps([
        {"a": 1, "b": 2, "volume": 5.0, "vol_a": 10.0, "vol_b": 10.0,
         "method": "probe"},    # 0.5 探针 → warning 而非 error
        {"a": 1, "b": 4, "volume": 0.5, "vol_a": 10.0, "vol_b": 10.0,
         "method": "probe"},    # 0.05 探针 → info
    ], meta)
    by = {(o["a"], o["b"]): o for o in r["overlaps"]}
    assert by[(1, 2)]["severity"] == "warning"
    assert by[(1, 2)]["suspected"] is True
    assert by[(1, 4)]["severity"] == "info"


def test_floor_excludes_shared_face():
    meta = _meta()
    r = classify_overlaps([
        {"a": 1, "b": 2, "volume": 1e-8, "vol_a": 10.0, "vol_b": 10.0,
         "method": "boolean"},   # 远低于 abs floor → 排除
    ], meta)
    assert r["overlaps"] == []
    assert len(r["excluded"]) == 1


def test_rel_floor_large_cells():
    # 大栅元 1e5，1e-4 相对下限 = 10 → 0.5 体积排除
    meta = _meta()
    r = classify_overlaps([
        {"a": 1, "b": 2, "volume": 0.5, "vol_a": 1e5, "vol_b": 1e5,
         "method": "boolean"},
    ], meta)
    assert r["overlaps"] == []


def test_cap_by_bbox_volume():
    cands = [
        {"a": 1, "b": 2, "bbox_volume": 1.0},
        {"a": 3, "b": 4, "bbox_volume": 9.0},
        {"a": 5, "b": 6, "bbox_volume": 4.0},
    ]
    top, truncated = cap_by_bbox_volume(cands, max_ops=2)
    assert [t["bbox_volume"] for t in top] == [9.0, 4.0]
    assert truncated is True
    top2, tr2 = cap_by_bbox_volume(cands, max_ops=10)
    assert tr2 is False
    assert len(top2) == 3
