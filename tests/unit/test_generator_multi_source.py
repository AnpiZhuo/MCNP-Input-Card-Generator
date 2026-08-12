"""生成器单测：多源 SDEF + SI/SP 概率归一化（F#5/F#6 的整函数字符化测试）。"""
import math
import re

import pytest

from app.generator.inp_generator import _generate_multi_source
from app.models import SourceData


def _src(**kw):
    base = dict(number=1, erg="14.0", pos_x="0", pos_y="0", pos_z="0")
    base.update(kw)
    return SourceData(**base)


# ── 概率归一化（表驱动）──────────────────────────────────
@pytest.mark.parametrize("probs,expected", [
    (["1", "1"], ["0.500000", "0.500000"]),
    (["1", "2", "1"], ["0.250000", "0.500000", "0.250000"]),
    (["3", "1"], ["0.750000", "0.250000"]),
    (["", ""], ["0.500000", "0.500000"]),   # 空串 → 默认 '1' → [1,1] → 各 0.5
    (["1", ""], ["0.500000", "0.500000"]),  # "1" 与 ""(→'1') → [1,1] → 各 0.5
])
def test_probability_normalization_table(probs, expected):
    # 各源 ERG 不同 → 产生分布参数 → SI/SP 卡出现，SP1 携带归一化概率
    srcs = [_src(number=i + 1, probability=p, erg=f"{10.0 - i:.1f}")
            for i, p in enumerate(probs)]
    lines = _generate_multi_source(srcs)
    text = "\n".join(lines)
    # 首张 SI 卡后的 SP 卡带归一化概率
    m = re.search(r'SP1\s+([\d.\s]+)', text)
    assert m, f"未找到 SP1: {text}"
    got = m.group(1).split()
    assert got == expected, f"{probs} → {got}, 期望 {expected}"


def test_all_zero_probability_falls_back_to_equal():
    # 全 0 → total_prob==0 → 回退等概率 1/n
    srcs = [_src(number=i + 1, probability="0", erg=f"{10.0 - i:.1f}") for i in range(3)]
    lines = _generate_multi_source(srcs)
    text = "\n".join(lines)
    m = re.search(r'SP1\s+([\d.\s]+)', text)
    got = m.group(1).split()
    assert got == ["0.333333"] * 3


def test_nan_probability_raises():
    srcs = [_src(number=1, probability="nan"), _src(number=2, probability="1")]
    with pytest.raises(ValueError):
        _generate_multi_source(srcs)


def test_inf_probability_raises():
    srcs = [_src(number=1, probability="inf"), _src(number=2, probability="1")]
    with pytest.raises(ValueError):
        _generate_multi_source(srcs)


# ── 基本多源结构 ─────────────────────────────────────────
def test_multi_source_same_pos_single_sdef_pos():
    srcs = [_src(number=1), _src(number=2)]
    lines = _generate_multi_source(srcs)
    sdef = next(l for l in lines if l.startswith("SDEF"))
    assert "POS=0 0 0" in sdef
    assert "POS=F" not in sdef


def test_multi_source_different_pos_uses_pos_vector_dist():
    srcs = [_src(number=1, pos_x="0", pos_y="0", pos_z="0"),
            _src(number=2, pos_x="1", pos_y="1", pos_z="1")]
    lines = _generate_multi_source(srcs)
    sdef = next(l for l in lines if l.startswith("SDEF"))
    assert "POS=F D1" in sdef
    assert any(l.startswith("SI1  V") for l in lines)


def test_multi_source_varying_erg_produces_si_sp_pair():
    srcs = [_src(number=1, erg="14.0"), _src(number=2, erg="2.0")]
    lines = _generate_multi_source(srcs)
    sdef = next(l for l in lines if l.startswith("SDEF"))
    assert "ERG=D1" in sdef
    assert any(l.startswith("SI1  L") for l in lines)
    assert any(l.startswith("SP1") for l in lines)


def test_multi_source_probability_keyed_to_first_dist():
    srcs = [_src(number=1, erg="14.0"), _src(number=2, erg="2.0"),
            _src(number=3, dir_="-1")]
    lines = _generate_multi_source(srcs)
    text = "\n".join(lines)
    # 第二个分布引用 D1（概率键控到第一张分布）
    assert re.search(r'SP\d+\s+D1', text)


def test_multi_source_sdef_extra_from_first_source():
    srcs = [_src(number=1, sdef_extra="TME=0.0"), _src(number=2)]
    lines = _generate_multi_source(srcs)
    sdef = next(l for l in lines if l.startswith("SDEF"))
    assert "TME=0.0" in sdef


def test_multi_source_comment():
    # 需要至少一个分布参数（ERG 不同）才会输出概率键控注释
    srcs = [_src(number=1, erg="14.0"), _src(number=2, erg="2.0")]
    lines = _generate_multi_source(srcs)
    assert any("sources, probability keyed to D1" in l for l in lines)
