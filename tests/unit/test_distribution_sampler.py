"""分布抽样单测：DistributionSampler（契约 source-demo-visualization.md §1 模块 A）。

覆盖 SI H（默认）/L/A/S、SP D/C/内置函数（-2~-6/-21/-31/-41）、SB 偏倚、
DS H/L/S/T/Q 查表，及 MCNP 语义错误（引用不存在/概率不匹配/边界非单调/概率和零）。
"""
import math
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


def test_si_s_d_prefix_distribution_numbers():
    """C810 3-64：`Each distribution number on the SI card can be prefixed with a D`。

    旧实现 `int(float("D2"))` → ValueError（被兜底成"源抽样失败: could not convert…"）。
    """
    s = DistributionSampler([
        {"id": 1, "si": {"type": "S", "values": ["D2", "3"]},
         "sp": {"type": "D", "values": ["1", "1"]}},
        {"id": 2, "si": {"type": "L", "values": ["100"]}},
        {"id": 3, "si": {"type": "L", "values": ["200"]}},
    ])
    rng = _rng()
    vals = {s.sample(1, rng) for _ in range(400)}
    assert vals == {100.0, 200.0}


def test_si_s_zero_uses_variable_default():
    """C810 3-64：`If a distribution number is zero, the default value for the variable is used`。"""
    s = DistributionSampler([
        {"id": 1, "si": {"type": "S", "values": ["0"]}, "sp": {"type": "D", "values": ["1"]}},
    ])
    assert s.sample(1, _rng(), var="ERG") == 14.0     # Table 3.3 默认能量
    assert s.sample(1, _rng(), var="RAD") == 0.0


def test_si_s_bad_distribution_number_reports_semantic_error():
    """分布号不是数字/不是 D+数字 → 必须报 SourceSamplingError（可读），不能漏成 ValueError。"""
    s = DistributionSampler([
        {"id": 1, "si": {"type": "S", "values": ["X2"]}, "sp": {"type": "D", "values": ["1"]}},
    ])
    with pytest.raises(SourceSamplingError, match="分布号"):
        s.sample(1, _rng())


# ── SP V 仅 CEL（C810 3-64：V−for cell distributions only）──

def test_sp_v_requires_cel_source():
    entry = {"id": 1, "si": {"type": "L", "values": ["1", "2"]},
             "sp": {"type": "V", "values": ["1", "2"]}}
    with pytest.raises(SourceSamplingError, match="只能用于 CEL"):
        DistributionSampler([entry]).sample(1, _rng(), var="ERG")


def test_sp_v_weights_by_cell_volume():
    """C810 3-64：`V — Probability is proportional to cell volume (times Pi if present)`。

    SI L 列出栅元号，SP V 未给 Pi ⇒ 权重 = 体积；给了 Pi ⇒ 体积 × Pi。
    """
    entry = {"id": 1, "si": {"type": "L", "values": ["1", "2"]},
             "sp": {"type": "V", "values": []}}
    s = DistributionSampler([entry])
    vol = {1: 3.0, 2: 1.0}
    rng = random.Random(1)
    vals = [s.sample(1, rng, var="CEL", cel=True, cell_volumes=vol) for _ in range(4000)]
    assert set(vals) == {1.0, 2.0}
    assert abs(vals.count(1.0) / 4000 - 0.75) < 0.03, "体积 3:1 ⇒ 概率 3:1"

    # 给了 Pi：体积 × Pi（3×1 : 1×3 = 1:1）
    entry2 = {"id": 1, "si": {"type": "L", "values": ["1", "2"]},
              "sp": {"type": "V", "values": ["1", "3"]}}
    s2 = DistributionSampler([entry2])
    rng = random.Random(2)
    vals2 = [s2.sample(1, rng, var="CEL", cel=True, cell_volumes=vol) for _ in range(4000)]
    assert abs(vals2.count(1.0) / 4000 - 0.5) < 0.03, "体积 × Pi ⇒ 1:1"


def test_sp_v_missing_volume_reports_fatal():
    """拿不到栅元体积 ⇒ 明确报错（C810 3-64：MCNP 算不出体积且无 VOL 卡是 FATAL），不静默按 D 抽。"""
    entry = {"id": 1, "si": {"type": "L", "values": ["1", "2"]},
             "sp": {"type": "V", "values": []}}
    with pytest.raises(SourceSamplingError, match="体积"):
        DistributionSampler([entry]).sample(1, _rng(), var="CEL", cel=True,
                                            cell_volumes={1: 3.0})


# ── 内置函数在「SI 单值」下的对称默认（C810 3-66 特殊默认 3/4/5）──

def test_builtin_single_si_ext_is_symmetric():
    """C810 3-66 规则 5：`If SI x and SP −21 or SP −31 are present for EXT, the SI is
    treated as if it were SI −x x` —— 必须保留负半轴。"""
    entry = {"id": 1, "si": {"type": "", "values": ["5"]},
             "sp": {"type": "", "values": [], "fnCode": "-31", "fnParams": ["1.5"]}}
    s = DistributionSampler([entry])
    rng = _rng(3)
    vals = [s.sample(1, rng, var="EXT") for _ in range(4000)]
    assert min(vals) < 0.0, "EXT 的 SI 单值必须按对称区间 [−5,5] 抽样"
    assert max(vals) <= 5.0
    # 对照：RAD 同写法是 [0, x]（规则 4），不得出现负值。
    # ⚠ 规则 4 针对的是 **SP −21**（Table 3.4：−31 只允许 DIR/EXT，配 RAD 属非法配对，
    # 2026-09-20 起会被 `_BUILTIN_VARS` 拒绝）—— 故这里另建一张 −21 的卡来对照。
    s21 = DistributionSampler([{"id": 1, "si": {"type": "", "values": ["5"]},
                                "sp": {"type": "", "values": [], "fnCode": "-21",
                                       "fnParams": ["1"]}}])
    rng = _rng(3)
    rad = [s21.sample(1, rng, var="RAD") for _ in range(2000)]
    assert min(rad) >= 0.0 and max(rad) <= 5.0


def test_builtin_single_si_dir_is_symmetric_for_31():
    """C810 3-66 规则 3/5：DIR 上 `SI x` + SP −31 ⇒ [−x, x]（±cos）。"""
    entry = {"id": 1, "si": {"type": "", "values": ["1"]},
             "sp": {"type": "", "values": [], "fnCode": "-31", "fnParams": ["1.5"]}}
    s = DistributionSampler([entry])
    rng = _rng(5)
    vals = [s.sample(1, rng, var="DIR") for _ in range(2000)]
    assert min(vals) < 0.0 and max(vals) <= 1.0


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


def test_builtin_21_default_a_depends_on_variable():
    """C810 3-66：`SP −21` 不给 a 时按变量取默认值 —— DIR=1；RAD=2（有 AXS 或 JSU≠0 → 1）；EXT=0。

    旧实现 `_need(params, 1, 1)` 把「不给 a」当错误 ⇒ `SP1 −21` 直接报错，
    而 C810 明确说这种写法有默认值（特殊默认 2/3 还依赖它）。
    """
    entry = {"id": 1, "si": {"type": "", "values": ["0", "1"]},
             "sp": {"type": "", "values": [], "fnCode": "-21", "fnParams": []}}
    s = DistributionSampler([entry])
    # DIR a=1 ⇒ p(μ)=c·μ（均值 2/3）；取 6000 样本比对解析均值
    rng = random.Random(11)
    vals = [s.sample(1, rng, var="DIR") for _ in range(6000)]
    assert all(0.0 <= v <= 1.0 for v in vals)
    assert abs(sum(vals) / len(vals) - 2.0 / 3.0) < 0.02
    # EXT a=0 ⇒ 区间内均匀（均值 1/2）
    rng = random.Random(12)
    vals = [s.sample(1, rng, var="EXT") for _ in range(4000)]
    assert abs(sum(vals) / len(vals) - 0.5) < 0.03
    # RAD a=2 ⇒ p∝r²（区间 [0,1] 上均值 3/4）；axs=True ⇒ a=1 ⇒ 均值 2/3
    # （区间仍由 SI 的两项 [0,1] 决定，a 只改密度形状）
    rng = random.Random(13)
    vals = [s.sample(1, rng, var="RAD", axs=False) for _ in range(6000)]
    assert abs(sum(vals) / len(vals) - 0.75) < 0.02
    rng = random.Random(14)
    vals = [s.sample(1, rng, var="RAD", axs=True) for _ in range(6000)]
    assert abs(sum(vals) / len(vals) - 2.0 / 3.0) < 0.02


def test_builtin_31_default_a_is_zero():
    """C810 3-66：`f = −31` 默认 a = 0 ⇒ 退化为区间内均匀（而不是报错缺参数）。"""
    entry = {"id": 1, "si": {"type": "", "values": ["-1", "1"]},
             "sp": {"type": "", "values": [], "fnCode": "-31", "fnParams": []}}
    s = DistributionSampler([entry])
    rng = _rng(15)
    vals = [s.sample(1, rng, var="DIR") for _ in range(4000)]
    assert all(-1.0 <= v <= 1.0 for v in vals)
    assert abs(sum(vals) / len(vals)) < 0.03


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
    # 数据统一落 distributionIds（_parse_ds 产出的形状）——勿再手写 values（该键无人产出）
    s = DistributionSampler([{"id": 5, "ds": {"type": "Q", "distributionIds": ["0", "2", "10", "3"]}}])
    assert s.resolve_ds(5, -5, None) == {"distribution": 2}
    assert s.resolve_ds(5, 5, None) == {"distribution": 3}


def test_ds_l_value():
    s = DistributionSampler([{"id": 5, "ds": {"type": "L", "distributionIds": ["1.5", "2.5"]}}])
    assert s.resolve_ds(5, 0, ["0", "1"]) == {"value": 1.5}
    assert s.resolve_ds(5, 1, ["0", "1"]) == {"value": 2.5}


def test_ds_h_interpolate():
    s = DistributionSampler([{"id": 5, "ds": {"type": "H", "distributionIds": ["0", "10"]}}])
    r = s.resolve_ds(5, 0.5, ["0", "1"])
    assert r["value"] == 5.0  # 中点插值


def test_ds_t_match():
    s = DistributionSampler([{"id": 5, "ds": {"type": "T", "distributionIds": ["0", "7", "1", "8"]}}])
    assert s.resolve_ds_t(5, 0) == {"value": 7.0}
    assert s.resolve_ds_t(5, 2) == {"default": True}


# ── 真实解析路径回归（TD-03 发布阻断项：走 parse_distribution_lines 而非手写 dict）──

def test_ds_real_parse_path_q_l_h_t():
    """解析 → 抽样的真实链路：`DSn Q/L/H` 的 J 列表不得被 param 吃掉首项。"""
    from app.generator.distributions import parse_distribution_lines

    def _ds_of(line: str) -> dict:
        return parse_distribution_lines([line])[0]["ds"]

    # Q：V1 S1 V2 S2（首 token 是数值 → 不得当 param）
    ds_q = _ds_of("DS5  Q  0  2  10  3")
    assert ds_q["param"] == "", "数值首 token 不得被当作 param"
    assert ds_q["distributionIds"] == ["0", "2", "10", "3"]
    s_q = DistributionSampler([{"id": 5, "ds": ds_q}])
    assert s_q.resolve_ds(5, -5, None) == {"distribution": 2}
    assert s_q.resolve_ds(5, 5, None) == {"distribution": 3}

    # L：J 列表按离散索引取（索引 0 必须取到第一个 J，而非第二个）
    ds_l = _ds_of("DS5  L  1.5  2.5")
    assert ds_l["distributionIds"] == ["1.5", "2.5"]
    s_l = DistributionSampler([{"id": 5, "ds": ds_l}])
    assert s_l.resolve_ds(5, 0, ["0", "1"]) == {"value": 1.5}
    assert s_l.resolve_ds(5, 1, ["0", "1"]) == {"value": 2.5}

    # H：连续插值
    ds_h = _ds_of("DS5  H  0  10")
    s_h = DistributionSampler([{"id": 5, "ds": ds_h}])
    assert s_h.resolve_ds(5, 0.5, ["0", "1"])["value"] == 5.0

    # T：I1 J1 … 成对匹配
    ds_t = _ds_of("DS5  T  0  7  1  8")
    s_t = DistributionSampler([{"id": 5, "ds": ds_t}])
    assert s_t.resolve_ds_t(5, 0) == {"value": 7.0}
    assert s_t.resolve_ds_t(5, 1) == {"value": 8.0}


def test_ds_s_real_parse_path_index_not_shifted():
    """S 卡：`DS1 S 2 3` 索引 0 必须取到分布 2（历史 bug：被 param 吃掉 → 取到 3）。"""
    from app.generator.distributions import parse_distribution_lines

    ds = parse_distribution_lines(["DS1  S  2  3"])[0]["ds"]
    assert ds["distributionIds"] == ["2", "3"]
    s = DistributionSampler([{"id": 1, "ds": ds}])
    assert s.resolve_ds(1, 0, ["0", "1"]) == {"distribution": 2}
    assert s.resolve_ds(1, 1, ["0", "1"]) == {"distribution": 3}


def test_ds_var_form_keeps_param_and_data():
    """带变量名的写法（C810_卡片格式详细.md:183 `DS[n] var Dn1…`）：首 token 非数值 → 保留为 param。"""
    from app.generator.distributions import parse_distribution_lines

    ds = parse_distribution_lines(["DS2  S  ERG  3  4"])[0]["ds"]
    assert ds["param"] == "ERG"
    assert ds["distributionIds"] == ["3", "4"]


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


# ── 内置函数 ↔ 源变量配对（C810 p.3-66 Table 3.4）────────────

def test_builtin_is_restricted_to_its_variables():
    """C810 Table 3.4 的配对表：−41 只能用于 TME/X/Y/Z。

    用在 RAD 上必须**抽样前**报错 —— 旧实现只校验参数个数，配错就静默产出一个
    无意义的"高斯径向分布"，比报错难查得多。
    """
    s = DistributionSampler([{"id": 1, "si": None,
                              "sp": {"fnCode": "-41", "fnParams": ["0.1", "0.0"]}}])
    with pytest.raises(SourceSamplingError, match="Table 3.4"):
        s.sample(1, _rng(), var="RAD")
    assert isinstance(s.sample(1, _rng(), var="TME"), float)      # 用在该用的变量上正常
    assert isinstance(s.sample(1, _rng(), var="Z"), float)


def test_energy_spectrum_builtin_is_rejected_for_direction():
    """能量谱（−2…−6）只能给 ERG；给 DIR 必须报错。"""
    s = DistributionSampler([{"id": 1, "si": None,
                              "sp": {"fnCode": "-2", "fnParams": []}}])
    with pytest.raises(SourceSamplingError, match="Table 3.4"):
        s.sample(1, _rng(), var="DIR")
    assert s.sample(1, _rng(), var="ERG") >= 0.0


def test_builtin_minus7_spare_is_explicitly_unsupported():
    """C810 Table 3.4 的 −7 是「framework … to add a spectrum of his own」⇒ 显式不支持。"""
    s = DistributionSampler([{"id": 1, "si": None,
                              "sp": {"fnCode": "-7", "fnParams": ["1", "1"]}}])
    with pytest.raises(SourceSamplingError, match="spare"):
        s.sample(1, _rng(), var="ERG")


# ── O6：内置函数被 SI **截断** + 权重补偿（C810 p.3-66）────────
#
# 「A built-in function on an SP card can be biased or truncated or both by a table on SI and
#   SB cards. … Unless the function is −21 or −31, the weight of the source particle is
#   adjusted to compensate for truncation of the function by the entries on the SI card.」
# 修前：−2…−6/−41 **完全不看 SI**（照完整谱抽），WGT 也恒为 1 ⇒ 能量越界 + 权重错。

def _builtin(fn, params, si=None, var_entry_si_type=""):
    return DistributionSampler([{
        "id": 1,
        "si": ({"type": var_entry_si_type, "values": [str(v) for v in si]} if si else None),
        "sp": {"type": "", "values": [], "fnCode": fn, "fnParams": params},
        "sb": None,
    }])


def test_builtin_truncated_by_si_stays_inside_window():
    """−2…−6/−41 被 `SI I1 I2` 截断后，抽样必须**全部落在区间内**。"""
    cases = [
        ("-2", [], [1.0, 4.0], "ERG", 1.0, 4.0),
        ("-3", ["0.965", "2.29"], [2.0, 6.0], "ERG", 2.0, 6.0),
        ("-4", ["0.5", "14.1"], [13.0, 15.0], "ERG", 13.0, 15.0),
        ("-5", ["1.0"], [0.5, 3.0], "ERG", 0.5, 3.0),
        ("-6", ["0.5", "14.1"], [13.0, 15.0], "ERG", 13.0, 15.0),
        ("-41", ["2", "0"], [-1.0, 1.0], "TME", -1.0, 1.0),
    ]
    for fn, params, si, var, lo, hi in cases:
        s = _builtin(fn, params, si=si)
        rng = _rng(7)
        vals = [s.sample_with_corrections(1, rng, var=var)[0] for _ in range(300)]
        assert all(lo - 1e-9 <= v <= hi + 1e-9 for v in vals), (
            f"{fn}: SI 截断失效，越界样本 {[v for v in vals if not lo <= v <= hi][:3]}")


def test_truncation_weight_matches_analytic_probability():
    """权重补偿 = P(I1 ≤ x ≤ I2)：用**有解析式的**两个函数对账。"""
    from statistics import NormalDist

    # ① −5 蒸发谱 p(E) ∝ E·e^{−E/a}：P(0≤E≤x) = 1 − e^{−x/a}(1 + x/a)
    a, hi = 1.0, 5.0
    s = _builtin("-5", [str(a)], si=[0.0, hi])
    _v, w = s.sample_with_corrections(1, _rng(1), var="ERG")
    analytic = 1.0 - math.exp(-hi / a) * (1.0 + hi / a)
    assert w == pytest.approx(analytic, rel=1e-5)

    # ② −41 高斯 p(t) ∝ exp[−(1.6651092(t−b)/a)²]，a=FWHM ⇒ σ = a/√(8 ln 2)
    a41, b41 = 2.0, 0.0
    nd = NormalDist(b41, a41 / math.sqrt(8.0 * math.log(2.0)))
    s = _builtin("-41", [str(a41), str(b41)], si=[-1.0, 1.0])
    _v, w = s.sample_with_corrections(1, _rng(2), var="TME")
    assert w == pytest.approx(2.0 * nd.cdf(1.0) - 1.0, rel=1e-12)

    # ③ −4 聚变高斯：SI 窗口远宽于 FWHM ⇒ P ≈ 1（不是随手写 1，而是条件概率就是 1）
    s = _builtin("-4", [], si=[10.0, 18.0])
    _v, w = s.sample_with_corrections(1, _rng(3), var="ERG")
    assert w == pytest.approx(1.0, abs=1e-6)


def test_minus21_and_minus31_are_exempt_from_truncation_weight():
    """C810 p.3-66 明文豁免 −21/−31（它们的定义就在 SI 区间上归一化）⇒ 补偿因子恒 1。"""
    for fn, params, var in (("-21", ["2"], "RAD"), ("-31", ["1.5"], "DIR")):
        s = _builtin(fn, params, si=[0.0, 1.0])
        rng = _rng(4)
        vals = [s.sample_with_corrections(1, rng, var=var) for _ in range(50)]
        assert all(w == 1.0 for _v, w in vals), fn
        assert all(0.0 <= v <= 1.0 for v, _w in vals), fn


def test_untouched_builtins_keep_full_range_without_si():
    """没有 SI ⇒ 不截断、不补偿（旧行为逐字保留：完整谱 + 权重 1）。"""
    s = _builtin("-2", [], si=None)
    rng = _rng(5)
    vals = [s.sample_with_corrections(1, rng, var="ERG") for _ in range(200)]
    assert all(w == 1.0 for _v, w in vals)
    assert max(v for v, _w in vals) > 5.0      # 完整 Maxwell 能抽到远高于 5 MeV
    assert all(v >= 0.0 for v, _w in vals)


def test_builtin_truncation_window_invalid_reports_error():
    """SI 窗口与函数支撑**无交集**（DT 聚变谱 14 MeV 却写 SI 0 5）⇒ 明确报错，不静默给空分布。"""
    s = _builtin("-4", [], si=[0.0, 5.0])
    with pytest.raises(SourceSamplingError, match="截断区间无效"):
        s.sample(1, _rng(6), var="ERG")


# ── SB 偏倚的权重补偿（C810 p.3-64）────────────────────────

def test_sb_bias_weight_compensation():
    """C810 p.3-64：「The weight of each source particle is adjusted to compensate for the bias.」

    SI L[A B] / SP 真概率 0.5/0.5 / SB 偏倚概率 0.9/0.1 ⇒ 权重 0.5/0.9 与 0.5/0.1。
    修前：`weight_factor` 写了却**没有任何调用者**，WGT 恒 1 ⇒ 偏倚白做。
    """
    s = DistributionSampler([{
        "id": 1,
        "si": {"type": "L", "values": ["1", "2"]},
        "sp": {"type": "", "values": ["0.5", "0.5"], "fnCode": "", "fnParams": []},
        "sb": {"type": "D", "values": ["0.9", "0.1"]},
    }])
    rng = _rng(9)
    pairs = [s.sample_with_corrections(1, rng, var="ERG") for _ in range(4000)]
    w1 = {round(w, 9) for v, w in pairs if v == 1.0}
    w2 = {round(w, 9) for v, w in pairs if v == 2.0}
    assert w1 == {round(0.5 / 0.9, 9)}, w1
    assert w2 == {round(0.5 / 0.1, 9)}, w2
    # 抽样本身按 SB 偏倚（1 出现得远多于 2），否则"补偿"没有意义
    n1 = sum(1 for v, _w in pairs if v == 1.0)
    assert n1 / len(pairs) == pytest.approx(0.9, abs=0.03)


def test_no_sb_means_no_weight_change():
    """无 SB ⇒ 补偿因子 1（抽样按 SP 概率）。"""
    s = DistributionSampler([{
        "id": 1,
        "si": {"type": "L", "values": ["1", "2"]},
        "sp": {"type": "", "values": ["0.5", "0.5"], "fnCode": "", "fnParams": []},
        "sb": None,
    }])
    assert all(w == 1.0 for _v, w in
               (s.sample_with_corrections(1, _rng(10), var="ERG") for _ in range(50)))


def test_sb_bias_zero_true_probability_gives_zero_weight():
    """真概率为 0 的档被偏倚抽中 ⇒ 权重 0（该粒子代表零概率事件，MCNP 同样算 0）。"""
    s = DistributionSampler([{
        "id": 1,
        "si": {"type": "L", "values": ["1", "2"]},
        "sp": {"type": "", "values": ["0", "1"], "fnCode": "", "fnParams": []},
        "sb": {"type": "D", "values": ["0.5", "0.5"]},
    }])
    rng = _rng(11)
    pairs = [s.sample_with_corrections(1, rng, var="ERG") for _ in range(400)]
    assert {w for v, w in pairs if v == 1.0} == {0.0}
    assert {w for v, w in pairs if v == 2.0} == {2.0}
