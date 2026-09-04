"""app.coverage_check 单测：格阵 universe 覆盖完整性检测（红框预防）。

核心：给定格元盒 box + universe 栅元 AST JSON，判定 universe 是否填满格元盒。
用例覆盖：只定义内部（应未覆盖）/ 内部+外围 void（应覆盖）/ 纯 void 盒（应覆盖）/
空 U（empty）/ 格元盒不可解析 / 无界轴 / 引用未定义曲面降级。
"""

import numpy as np
import pytest

from app.coverage_check import (
    universe_coverage, COVERAGE_TOL, DEFAULT_RES,
)

# 曲面卡：1=CZ r=1 圆柱（正侧=柱外），2..7=格元盒 ±2 边界平面（PX/PY/PZ）
_SURF = {
    1: {"type": "CZ", "params": [1.0], "transform": None},
    2: {"type": "PX", "params": [-2.0], "transform": None},
    3: {"type": "PX", "params": [2.0], "transform": None},
    4: {"type": "PY", "params": [-2.0], "transform": None},
    5: {"type": "PY", "params": [2.0], "transform": None},
    6: {"type": "PZ", "params": [-2.0], "transform": None},
    7: {"type": "PZ", "params": [2.0], "transform": None},
}
_BOX = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": -2, "z_max": 2}
_TR = {}


def _box_ast(signs):
    """按 (曲面号, 正负感) 构造 intersect 盒 AST（+sense 正侧 / -sense 负侧）。"""
    cur = None
    for num, sense in signs:
        node = ["surf", num]
        if sense < 0:
            node = ["unary", node, "neg"]
        cur = node if cur is None else ["intersect", cur, node]
    return cur


# 内部圆柱：盒 ∩ 柱内（CZ(1) 负侧 = 柱内）
def _inner_cyl():
    box = _box_ast([(2, 1), (3, -1), (4, 1), (5, -1), (6, 1), (7, -1)])
    cyl = ["unary", ["surf", 1], "neg"]
    return ["intersect", box, cyl]


# 外围 void：盒 ∩ 柱外（CZ(1) 正侧 = 柱外，complement 同正侧）
def _outer_void():
    box = _box_ast([(2, 1), (3, -1), (4, 1), (5, -1), (6, 1), (7, -1)])
    cyl = ["unary", ["surf", 1], "neg"]
    return ["intersect", box, ["unary", cyl, "complement"]]


def _full_box():
    return _box_ast([(2, 1), (3, -1), (4, 1), (5, -1), (6, 1), (7, -1)])


def test_inner_only_not_covered():
    """只定义内部圆柱、没定义外部 → 未覆盖（即「没编辑外部」）。"""
    r = universe_coverage(_BOX, [_inner_cyl()], _SURF, _TR)
    assert r["kind"] == "leaf"
    assert r["covered"] is False
    assert r["uncoveredFraction"] > COVERAGE_TOL
    assert r["detailViable"] is True


def test_inner_plus_outer_covered():
    """内部圆柱 + 外围 void 填满格元盒 → 覆盖。"""
    r = universe_coverage(_BOX, [_inner_cyl(), _outer_void()], _SURF, _TR)
    assert r["kind"] == "leaf"
    assert r["covered"] is True
    assert r["uncoveredFraction"] <= COVERAGE_TOL


def test_full_void_box_covered():
    """只一个填满格元盒的 void 盒（无内部）→ 覆盖。以盒面内缩避免共面误判。"""
    r = universe_coverage(_BOX, [_full_box()], _SURF, _TR)
    assert r["kind"] == "leaf"
    assert r["covered"] is True
    assert r["uncoveredFraction"] < 1e-6


def test_empty_u():
    """U 无栅元定义 → kind=empty、不判定覆盖。"""
    r = universe_coverage(_BOX, [], _SURF, _TR)
    assert r["kind"] == "empty"
    assert r["covered"] is False
    assert r["detailViable"] is False


def test_no_box_detail_not_viable():
    """格元盒无法解析（box=None）→ detailViable=False、不误判。"""
    r = universe_coverage(None, [_inner_cyl()], _SURF, _TR)
    assert r["kind"] == "leaf"
    assert r["covered"] is False
    assert r["detailViable"] is False


def test_unbounded_axis_uses_default_span():
    """某轴无界（z=None）→ 用默认厚度采样，不抛异常、detailViable 取决于采样。"""
    box = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": None, "z_max": None}
    r = universe_coverage(box, [_inner_cyl()], _SURF, _TR)
    assert r["uncoveredFraction"] > COVERAGE_TOL  # 内部圆柱仍未满，反例可判


def test_undefined_surface_degrades():
    """引用未定义曲面（曲面号不在 surfaces_by_num）→ 该栅元不可求值 → 降级。"""
    bad_ast = ["unary", ["surf", 999], "neg"]  # 曲面 999 未定义
    r = universe_coverage(_BOX, [bad_ast], _SURF, _TR)
    assert r["kind"] == "leaf"
    assert r["detailViable"] is False
    assert r["unsupportedCells"] >= 1
    # 无法可靠判定 → 不标 covered
    assert r["covered"] is False


def test_sample_count_matches_res_cube():
    """sampleCount = res³（16³=4096）。"""
    r = universe_coverage(_BOX, [_full_box()], _SURF, _TR, res=DEFAULT_RES)
    assert r["sampleCount"] == DEFAULT_RES ** 3
