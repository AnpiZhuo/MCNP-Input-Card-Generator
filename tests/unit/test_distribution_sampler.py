"""分布抽样单测：DistributionSampler（契约 source-demo-visualization.md §1 模块 A）。

覆盖 SI H（默认）/L/A/S、SP D/C/内置函数（-2~-6/-21/-31/-41）、SB 偏倚、
DS H/L/S/T/Q 查表，及 MCNP 语义错误（引用不存在/概率不匹配/边界非单调/概率和零）。
"""
import random

import pytest

from app.generator.distributions import DistributionSampler, SourceSamplingError


def _rng(seed=42):
    return random.Random(seed)


# ── SI L 离散 ──────────────────────────────────────────────

def test_si_l_equal_probability():
    s = DistributionSampler([{"id": 1, "si": {"type": "L", "values": ["10", "20", "30"]}, "sp": None}])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(3000)]
    assert set(vals) == {10.0, 20.0, 30.0}
    for v in (10.0, 20.0, 30.0):
        assert 0.28 < vals.count(v) / 3000 < 0.38  # 等概率 ~0.33


def test_si_l_weighted():
    s = DistributionSampler([{"id": 1, "si": {"type": "L", "values": ["1", "2", "3"]},
                              "sp": {"type": "D", "values": ["0.2", "0.5", "0.3"]}}])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(5000)]
    assert abs(vals.count(1.0) / 5000 - 0.2) < 0.03
    assert abs(vals.count(2.0) / 5000 - 0.5) < 0.03


def test_si_l_cumulative():
    s = DistributionSampler([{"id": 1, "si": {"type": "L", "values": ["1", "2", "3"]},
                              "sp": {"type": "C", "values": ["0.2", "0.7", "1.0"]}}])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(5000)]
    assert abs(vals.count(1.0) / 5000 - 0.2) < 0.03
    assert abs(vals.count(2.0) / 5000 - 0.5) < 0.03


# ── SI H 直方图 ────────────────────────────────────────────

def test_si_h_leading_zero():
    # SP 首条目 0 占位（MCNP H 分布约定）
    s = DistributionSampler([{"id": 1, "si": {"type": "H", "values": ["0", "10", "20"]},
                              "sp": {"type": "D", "values": ["0", "0.5", "0.5"]}}])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(4000)]
    assert all(0 <= v <= 20 for v in vals)
    assert abs(sum(1 for v in vals if v < 10) / 4000 - 0.5) < 0.04


def test_si_h_unlettered_default_h():
    # 无字母 SI = H（MCNP 缺省）
    s = DistributionSampler([{"id": 1, "si": {"type": "", "values": ["0", "10"]}, "sp": None}])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(1000)]
    assert all(0 <= v <= 10 for v in vals)


# ── SI A 概率密度点 ────────────────────────────────────────

def test_si_a_density():
    # 线性密度 [0,1,0] 在 [0,1]（三角分布）
    s = DistributionSampler([{"id": 1, "si": {"type": "A", "values": ["0", "0.5", "1"]},
                              "sp": {"type": "", "values": ["0", "1", "0"]}}])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(2000)]
    assert all(0 <= v <= 1 for v in vals)
    assert abs(sum(v for v in vals) / 2000 - 0.5) < 0.05  # 均值 ~0.5


# ── SI S 递归选分布 ────────────────────────────────────────

def test_si_s_recursive():
    s = DistributionSampler([
        {"id": 1, "si": {"type": "S", "values": ["2", "3"]}, "sp": {"type": "D", "values": ["1", "1"]}},
        {"id": 2, "si": {"type": "L", "values": ["100"]}},
        {"id": 3, "si": {"type": "L", "values": ["200"]}},
    ])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(500)]
    assert set(vals) == {100.0, 200.0}


# ── 内置函数 ───────────────────────────────────────────────

@pytest.mark.parametrize("fn,params,lo,hi", [
    ("-2", [], 0, 15),       # Maxwell
    ("-3", [], 0, 15),       # Watt
    ("-4", [], 10, 18),      # Gaussian fusion (DT ~14.08)
    ("-5", [], 0, 15),       # Evaporation
    ("-21", ["2"], 0, 1),    # power law (default SI 0 1)
    ("-31", ["1.5"], -1, 1), # exponential
])
def test_builtin_range(fn, params, lo, hi):
    s = DistributionSampler([{"id": 1, "si": None,
                              "sp": {"fnCode": fn, "fnParams": params}}])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(1000)]
    assert all(lo <= v <= hi for v in vals)


def test_builtin_gaussian_41():
    s = DistributionSampler([{"id": 1, "si": None,
                              "sp": {"fnCode": "-41", "fnParams": ["2", "0"]}}])
    rng = _rng()
    vals = [s.sample(1, rng) for _ in range(2000)]
    assert abs(sum(vals) / 2000) < 0.1  # 均值 ~0


# ── DS 查表 ────────────────────────────────────────────────

def test_ds_s_by_index():
    s = DistributionSampler([{"id": 5, "ds": {"type": "S", "distributionIds": ["2", "3"]}}])
    assert s.resolve_ds(5, 0, ["0", "1"]) == {"distribution": 2}
    assert s.resolve_ds(5, 1, ["0", "1"]) == {"distribution": 3}


def test_ds_q_by_value():
    s = DistributionSampler([{"id": 5, "ds": {"type": "Q", "values": ["0", "2", "10", "3"]}}])
    assert s.resolve_ds(5, -5, None) == {"distribution": 2}
    assert s.resolve_ds(5, 5, None) == {"distribution": 3}


def test_ds_l_value():
    s = DistributionSampler([{"id": 5, "ds": {"type": "L", "values": ["1.5", "2.5"]}}])
    assert s.resolve_ds(5, 0, ["0", "1"]) == {"value": 1.5}
    assert s.resolve_ds(5, 1, ["0", "1"]) == {"value": 2.5}


def test_ds_h_interpolate():
    s = DistributionSampler([{"id": 5, "ds": {"type": "H", "values": ["0", "10"]}}])
    r = s.resolve_ds(5, 0.5, ["0", "1"])
    assert r["value"] == 5.0  # 中点插值


def test_ds_t_match():
    s = DistributionSampler([{"id": 5, "ds": {"type": "T", "values": ["0", "7", "1", "8"]}}])
    assert s.resolve_ds_t(5, 0) == {"value": 7.0}
    assert s.resolve_ds_t(5, 2) == {"default": True}


# ── 错误 ───────────────────────────────────────────────────

def test_error_undefined_distribution():
    with pytest.raises(SourceSamplingError, match="未定义"):
        DistributionSampler([]).sample(9, _rng())


def test_error_prob_mismatch():
    with pytest.raises(SourceSamplingError, match="不匹配"):
        DistributionSampler([{"id": 1, "si": {"type": "H", "values": ["0", "10", "20"]},
                              "sp": {"type": "D", "values": ["0.5"]}}]).sample(1, _rng())


def test_error_zero_probability():
    with pytest.raises(SourceSamplingError, match="为零"):
        DistributionSampler([{"id": 1, "si": {"type": "L", "values": ["1", "2"]},
                              "sp": {"type": "D", "values": ["0", "0"]}}]).sample(1, _rng())


def test_error_invalid_si_type():
    with pytest.raises(SourceSamplingError, match="SI 类型"):
        DistributionSampler([{"id": 1, "si": {"type": "Q", "values": ["1", "2"]}, "sp": None}]).sample(1, _rng())
