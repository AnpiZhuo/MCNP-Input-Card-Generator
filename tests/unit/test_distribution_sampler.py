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
    # 对照：RAD 同写法是 [0, x]（规则 4），不得出现负值
    rng = _rng(3)
    rad = [s.sample(1, rng, var="RAD") for _ in range(2000)]
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
