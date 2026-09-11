"""生成器单测：单源 SDEF / 分布源 SDEF / 结构化分布卡。"""
import json

from app.generator.inp_generator import (
    _is_d_ref, _generate_sdef, _generate_single_source,
    _generate_distribution_sdef, _generate_structured_distributions,
    generate_inp_from_deck, _sdef_form_has_values, _source_from_adv,
)
from app.models import SourceData, AdvancedSettings, DeckData


def _src(**kw):
    base = dict(number=1)
    base.update(kw)
    return SourceData(**base)


# ── _is_d_ref ───────────────────────────────────────────
def test_is_d_ref():
    assert _is_d_ref("D1")
    assert _is_d_ref("d2")
    assert _is_d_ref("  D10 ")
    assert not _is_d_ref("")
    assert not _is_d_ref("1.0")
    assert not _is_d_ref("POS=1")


# ── _generate_sdef 分派 ─────────────────────────────────
def test_sdef_empty_sources_no_output():
    assert _generate_sdef([]) == []


def test_sdef_single_source_delegates():
    lines = _generate_sdef([_src(erg="14.0", pos_x="0", pos_y="0", pos_z="0")])
    assert lines == ["SDEF  ERG=14.0  POS=0 0 0"]


# ── 正常分支（283-301）：非 Dn、无扩展字段 ───────────────
def test_single_normal_common_fields():
    src = _src(par="1", erg="14.0", pos_x="0", pos_y="0", pos_z="0",
               dir_="1", wgt="1.0", cel="1", tme="0.0", vec="0 0 1",
               axs="0 0 1", rad="0.5", ext="0.0")
    lines = _generate_single_source(src)
    text = lines[0]
    for tok in ("SDEF", "PAR=1", "ERG=14.0", "POS=0 0 0", "DIR=1", "WGT=1.0",
                "CEL=1", "TME=0.0", "VEC=0 0 1", "AXS=0 0 1", "RAD=0.5", "EXT=0.0"):
        assert tok in text, f"缺少 {tok}: {text}"


def test_single_partial_pos_no_pos_emitted():
    src = _src(erg="14.0", pos_x="1", pos_y="2")  # 只有 2 个分量 → 不输出 POS
    lines = _generate_single_source(src)
    assert "POS=" not in lines[0]
    assert "ERG=14.0" in lines[0]


# ── Dn 分支（247-281）：Dn 引用或扩展字段 ────────────────
def test_single_dn_ref_uses_x_y_z():
    src = _src(erg="D1", pos_x="D1", pos_y="D1", pos_z="D1")
    lines = _generate_single_source(src)
    text = lines[0]
    # 三个分量同 D 引用 → POS=D1（_all_same_d）
    assert "POS=D1" in text


def test_single_pos_dn_ref_three_axes():
    src = _src(erg="14.0", pos_x="D1", pos_y="D2", pos_z="D3")
    lines = _generate_single_source(src)
    text = lines[0]
    assert "X=D1" in text
    assert "Y=D2" in text
    assert "Z=D3" in text


def test_single_extended_fields_only_in_dn_branch():
    # 扩展字段（SUR/NRM/TR/CCC/ARA/RATE/sdef_extra）→ 触发 has_d_or_extra → Dn 分支
    src = _src(erg="14.0", pos_x="0", pos_y="0", pos_z="0",
               sur="1", nrm="1", tr="1", ccc="1", ara="1.0", rate="1e6",
               sdef_extra="TME=0.0")
    text = _generate_single_source(src)[0]
    for tok in ("SUR=1", "NRM=1", "TR=1", "CCC=1", "ARA=1.0", "RATE=1e6", "TME=0.0"):
        assert tok in text, f"缺少扩展字段 {tok}: {text}"


def test_single_no_extended_fields_not_in_output():
    src = _src(erg="14.0", pos_x="0", pos_y="0", pos_z="0")
    text = _generate_single_source(src)[0]
    for tok in ("SUR=", "NRM=", "TR=", "CCC=", "ARA=", "RATE="):
        assert tok not in text


# ── 分布源 SDEF（_generate_distribution_sdef）────────────
def test_distribution_sdef_fields():
    adv = AdvancedSettings(
        sdef_par="1", sdef_erg="D2", sdef_pos_x="0", sdef_pos_y="0", sdef_pos_z="0",
        sdef_wgt="1", sdef_dir="1", sdef_cel="1",
    )
    lines = _generate_distribution_sdef(adv)
    text = lines[0]
    for tok in ("SDEF", "PAR=1", "ERG=D2", "POS=0 0 0", "WGT=1", "DIR=1", "CEL=1"):
        assert tok in text


def test_distribution_sdef_si_sp_prefix_from_distributions():
    """TD-23（t5）：原用例名为 `..._raw_text_si_sp_prefix`，用已退役的 adv.sdef_raw_text
    走生成器旧兜底分支（假活）。现改走唯一权威入口 sdef_distributions（v2 结构化 JSON），
    断言 SI1/SP1 前缀生成。"""
    adv = AdvancedSettings(
        sdef_distributions=json.dumps([{
            "id": 1, "editMode": "structured",
            "si": {"type": "", "values": ["0", "1"]},
            "sp": {"type": "D", "values": ["0.5", "0.5"], "fnCode": "", "fnParams": []},
            "sb": None, "ds": None, "sc": None,
        }]),
    )
    lines = _generate_distribution_sdef(adv)
    assert any(l.startswith("SI1") for l in lines)
    assert any(l.startswith("SP1") for l in lines)


# ── 结构化分布（_generate_structured_distributions）──────
def test_structured_distributions_full():
    dist_json = json.dumps([
        {
            "id": 1, "paramRef": "ERG",
            "si": {"type": "L", "values": ["14.0", "2.0"]},
            "sp": {"type": "D", "values": ["0.5", "0.5"], "fnCode": "", "fnParams": []},
            "sb": None, "ds": None,
        },
        {
            "id": 2, "paramRef": "POS",
            "si": {"type": "L", "values": ["0 0 0", "1 1 1"]},
            "sp": {"type": "D", "values": ["0.3", "0.7"], "fnCode": "", "fnParams": []},
            "sb": None, "ds": None,
        },
    ])
    lines = _generate_structured_distributions(dist_json)
    assert any(l.startswith("SI1  L") for l in lines)
    assert any(l.startswith("SP1  0.5  0.5") for l in lines)
    assert any(l.startswith("SI2  L") for l in lines)


def test_structured_distributions_fn_code():
    dist_json = json.dumps([
        {"id": 1, "si": {"type": "L", "values": ["1", "2"]},
         "sp": {"fnCode": "-3", "fnParams": ["0.965", "2.29"]}, "sb": None, "ds": None},
    ])
    lines = _generate_structured_distributions(dist_json)
    assert any("SP1  -3  0.965  2.29" in l for l in lines)


def test_structured_distributions_empty_json():
    assert _generate_structured_distributions("") == []
    assert _generate_structured_distributions("not-json") == []


# ── 表单模式（前端 sdefFields → adv.sdef_*，无分布/无多点源）──
def test_form_mode_sdef_fields_generate():
    """用户填 SDEF 源参数字段（表单模式）→ 生成单源 SDEF 卡（回归：漏源卡）。"""
    deck = DeckData(adv=AdvancedSettings(
        source_mode="distribution",
        sdef_erg="14", sdef_pos_x="0", sdef_pos_y="0", sdef_pos_z="0",
    ))
    out = generate_inp_from_deck(deck, {})
    assert "SDEF  ERG=14  POS=0 0 0" in out


def test_form_mode_sources_take_precedence():
    """sources 非空时优先走多点源路径，adv.sdef_* 不叠加（R1 不动点守卫）。"""
    deck = DeckData(
        adv=AdvancedSettings(source_mode="distribution", sdef_par="1", sdef_erg="99"),
        sources=[_src(erg="14.0", pos_x="0", pos_y="0", pos_z="0")],
    )
    out = generate_inp_from_deck(deck, {})
    assert "SDEF  ERG=14.0  POS=0 0 0" in out
    assert "PAR=1" not in out
    assert "ERG=99" not in out


def test_form_mode_empty_no_sdef():
    """表单全空（无字段/无分布/无源）→ 不输出 SDEF（原有空源行为不回归）。"""
    deck = DeckData(adv=AdvancedSettings(source_mode="distribution"))
    out = generate_inp_from_deck(deck, {})
    assert "SDEF" not in out


def test_sdef_form_has_values_and_source_from_adv():
    assert not _sdef_form_has_values(AdvancedSettings())
    assert _sdef_form_has_values(AdvancedSettings(sdef_erg="14"))
    src = _source_from_adv(AdvancedSettings(
        sdef_erg="14", sdef_pos_x="0", sdef_pos_y="0", sdef_pos_z="0",
        sdef_dir="1", sdef_wgt="1.0", sdef_extra="EFF=1",
    ))
    assert src.erg == "14" and src.pos_z == "0"
    assert src.dir_ == "1" and src.wgt == "1.0" and src.sdef_extra == "EFF=1"
