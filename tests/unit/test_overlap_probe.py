"""GQ/SQ 解析采样探针测试（纯 numpy，不 import vtk/FreeCAD）。"""

import pytest

import app.overlap_probe as probe_mod
from app.overlap_probe import sample_overlap


def _sphere_ast(num, sense="neg"):
    return ["unary", ["surf", num], sense]


def test_two_overlapping_spheres_detect_hits():
    surfaces = {
        1: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -4.0]},   # r=2 @0
        2: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, -1.0, 0, 0, -2.25]},
        # 球2：x²+y²+z²-2x+1-2.25=0 → 中心 (1,0,0) r=1.5
    }
    bounds = {
        1: ((-2.0, -2.0, -2.0), (2.0, 2.0, 2.0)),
        2: ((-0.5, -1.5, -1.5), (2.5, 1.5, 1.5)),
    }
    r = sample_overlap(_sphere_ast(1), _sphere_ast(2), surfaces, {},
                       bounds[1], bounds[2], res=32)
    assert r is not None
    assert r["method"] == "probe"
    assert r["hits"] > 0
    assert r["volume"] > 0
    assert 0 < r["volumeFraction"] <= 1.0
    assert r["low_confidence"] is False


def test_abab_not_overlapping_geometry_hits_zero():
    # AABB 相交但几何不相交：球 r=1.5 @0 与角落小盒（在球 AABB 内但在球外）
    surfaces = {
        1: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -2.25]},
        2: {"type": "RPP", "params": [1.2, 1.4, 1.2, 1.4, 1.2, 1.4]},
    }
    bounds = {
        1: ((-1.5, -1.5, -1.5), (1.5, 1.5, 1.5)),
        2: ((1.2, 1.2, 1.2), (1.4, 1.4, 1.4)),
    }
    r = sample_overlap(_sphere_ast(1), _sphere_ast(2), surfaces, {},
                       bounds[1], bounds[2], res=32)
    assert r is not None
    assert r["hits"] == 0
    assert r["volume"] == 0.0


def test_disjoint_boxes_returns_none():
    surfaces = {
        1: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.0]},
        2: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, -10.0, 0, 0, 24.0]},
    }
    bounds = {
        1: ((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)),
        2: ((4.0, -1.0, -1.0), (6.0, 1.0, 1.0)),
    }
    r = sample_overlap(_sphere_ast(1), _sphere_ast(2), surfaces, {},
                       bounds[1], bounds[2], res=16)
    assert r is None


def test_probe_respects_tr_transform():
    # 球 r=1 @0 + TR 平移(2,0,0) vs 球 r=1 @(2,0,0) → 完全重合，hits≈全部
    surfaces = {
        1: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.0],
            "transform": 1},
        2: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, -4.0, 0, 0, 3.0]},
        # 球2：中心 (2,0,0) r=1
    }
    tr = {1: {"translate": [2.0, 0.0, 0.0],
              "rotate": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}}
    bounds = {
        1: ((1.0, -1.0, -1.0), (3.0, 1.0, 1.0)),
        2: ((1.0, -1.0, -1.0), (3.0, 1.0, 1.0)),
    }
    r = sample_overlap(_sphere_ast(1), _sphere_ast(2), surfaces, tr,
                       bounds[1], bounds[2], res=24)
    assert r is not None
    assert r["hits"] > 0
    assert r["volumeFraction"] > 0.9  # 近乎完全重合


def test_probe_eval_failure_raises_probe_error(monkeypatch):
    """探针求值失败不再静默返回 None → 抛带 probe_error 前缀的异常。

    调用方（worker）据此把该栅元对记入 overlap_unresolved（reason），
    不再静默遗漏。
    """
    def boom(*args, **kwargs):
        raise ValueError("eval_cell_field boom")
    monkeypatch.setattr(probe_mod, "eval_cell_field", boom)
    surfaces = {
        1: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, 0, 0, 0, -1.0]},
        2: {"type": "GQ", "params": [1, 1, 1, 0, 0, 0, -3.0, 0, 0, 1.25]},
    }
    bounds = {
        1: ((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)),
        2: ((0.5, -1.0, -1.0), (2.5, 1.0, 1.0)),
    }
    with pytest.raises(RuntimeError) as ei:
        sample_overlap(_sphere_ast(1), _sphere_ast(2), surfaces, {},
                       bounds[1], bounds[2], res=8)
    assert "probe_error" in str(ei.value)
