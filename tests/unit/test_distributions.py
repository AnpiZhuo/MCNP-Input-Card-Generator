"""深度模块单测：app/generator/distributions.py 双态分布子系统。

涵盖：
  - parse_distribution_lines（原文分组、结构化派生、"" 类型主修复）
  - emit_distribution_entries（raw 直通 / structured 规范发射）
  - sync_entry / merge_distribution_entry
  - has_d1_probability_chain / multi_source_probability_count
  - q1112 真实场景的 round-trip 保真（无字母 SI 不被打回 L）
"""
import json
import re
from app.generator.distributions import (
    parse_distribution_lines,
    emit_distribution_entries,
    sync_entry,
    merge_distribution_entry,
    has_d1_probability_chain,
    multi_source_probability_count,
    _format_entry_cards,
    _family_lines_to_structured,
)


# ────────────────────────────────────────────────────────────────────────────
# parse_distribution_lines
# ────────────────────────────────────────────────────────────────────────────

def test_parse_unlettered_si_type_is_empty():
    """无字母 SI → type=""（MCNP 缺省为 H——L-default 修复核心）。"""
    entries = parse_distribution_lines(["SI1  -5 5", "SP1  0 1"])
    assert len(entries) == 1
    e = entries[0]
    assert e["id"] == 1
    assert e["editMode"] == "raw"
    assert e["si"]["type"] == "", f"无字母 SI 应记 type=''，实际 {e['si']['type']!r}"
    assert e["si"]["values"] == ["-5", "5"]
    assert e["sp"]["values"] == ["0", "1"]
    assert e["rawText"] == "SI1  -5 5\nSP1  0 1"


def test_parse_explicit_letter_preserved():
    """显式 SI 字母 L/H/A/S 保持原样。"""
    entries = parse_distribution_lines(["SI5  L  4 5", "SP5  .4  .6"])
    assert entries[0]["si"]["type"] == "L"
    assert entries[0]["si"]["values"] == ["4", "5"]
    entries2 = parse_distribution_lines(["SI2  A  -5 5"])
    assert entries2[0]["si"]["type"] == "A"


def test_parse_multiple_families_by_id():
    """按 id 分组，保持首次出现顺序。"""
    lines = ["SI1  -5 5", "SP1  0 1", "SC2  comment", "SI2  A -5 5", "SP2  1 1"]
    entries = parse_distribution_lines(lines)
    assert len(entries) == 2
    assert entries[0]["id"] == 1
    assert entries[1]["id"] == 2
    assert entries[1]["sc"] == "comment"


def test_parse_sc_comment_preserved():
    """SCn 源注释卡原文保留在 sc 字段 + rawText。"""
    entries = parse_distribution_lines([
        "SC2  position is biased toward the ring detector.",
    ])
    assert entries[0]["sc"] == "position is biased toward the ring detector."
    assert "SC2" in entries[0]["rawText"]


def test_parse_sb_ds():
    """SB 与 DS 分支。"""
    entries = parse_distribution_lines(["SB2  1 2", "DS2  S  ERG  3  4"])
    assert entries[0]["sb"]["type"] == "D"
    assert entries[0]["sb"]["values"] == ["1", "2"]
    assert entries[0]["ds"]["type"] == "S"
    assert entries[0]["ds"]["param"] == "ERG"
    assert entries[0]["ds"]["distributionIds"] == ["3", "4"]


def test_parse_sb_fn_codes():
    entries = parse_distribution_lines(["SB1  -21  1.5", "SB2  -31  2.0"])
    assert entries[0]["sb"]["type"] == "-21"
    assert entries[1]["sb"]["type"] == "-31"


def test_parse_sp_fn_code():
    entries = parse_distribution_lines(["SP1  -3  0.965  2.29"])
    assert entries[0]["sp"]["fnCode"] == "-3"
    assert entries[0]["sp"]["fnParams"] == ["0.965", "2.29"]


def test_parse_sp_type_v():
    entries = parse_distribution_lines(["SP4  V"])
    assert entries[0]["sp"]["type"] == "V"
    assert entries[0]["sp"]["values"] == []


def test_parse_raw_text_verbatim():
    """rawText 保留原文行（含内部空格、$ 注释）。"""
    entries = parse_distribution_lines(["SI2  -5  5  $ uniform ext"])
    assert "SI2  -5  5  $ uniform ext" in entries[0]["rawText"]
    # 结构化字段剥离 $ 注释
    assert entries[0]["si"]["values"] == ["-5", "5"]
    assert entries[0]["si"]["type"] == ""


# ────────────────────────────────────────────────────────────────────────────
# emit_distribution_entries — raw 直通 vs structured 规范
# ────────────────────────────────────────────────────────────────────────────

def test_emit_raw_verbatim():
    """editMode=raw → rawText 逐字直通。"""
    entries = [
        {"id": 2, "editMode": "raw", "rawText": "SI2  -5.5 5.5\nSP2  0 1",
         "si": None, "sp": None, "sb": None, "ds": None, "sc": None},
    ]
    lines = emit_distribution_entries(entries)
    assert lines == ["SI2  -5.5 5.5", "SP2  0 1"]


def test_emit_raw_ignores_structured():
    """raw 模式即使 structured 字段存在也以 rawText 为准。"""
    entries = [
        {"id": 1, "editMode": "raw", "rawText": "SI1  -5 5\nSP1  0 1",
         "si": {"type": "L", "values": ["0"]},  # 本应废弃，但 raw 模式忽略
         "sp": {"type": "D", "values": ["1"]}, "sb": None, "ds": None, "sc": None},
    ]
    lines = emit_distribution_entries(entries)
    assert lines == ["SI1  -5 5", "SP1  0 1"]


def test_emit_structured_no_edit_mode():
    """无 editMode 或无 rawText → 结构化规范重建（旧 v1 条目）。"""
    entries = [
        {"id": 1, "si": {"type": "L", "values": ["14.0", "2.0"]},
         "sp": {"type": "D", "values": ["0.5", "0.5"], "fnCode": "", "fnParams": []},
         "sb": None, "ds": None},
    ]
    lines = emit_distribution_entries(entries)
    assert any(l.startswith("SI1  L") for l in lines)
    assert any("SP1  0.5  0.5" in l for l in lines)


def test_emit_structured_type_empty_no_letter():
    """SI type="" → 不发射字母（MCNP 缺省 H）。"""
    entries = [
        {"id": 2, "si": {"type": "", "values": ["-5.5", "5.5"]},
         "sp": {"type": "", "values": ["0", "1"]}, "sb": None, "ds": None},
    ]
    lines = emit_distribution_entries(entries)
    si_line = [l for l in lines if l.startswith("SI2")]
    assert si_line, "SI2 行应存在"
    assert "  L" not in si_line[0], f"无字母 SI 不应含 L: {si_line[0]}"
    assert "-5.5" in si_line[0]
    sp_line = [l for l in lines if l.startswith("SP2")]
    assert sp_line and "0" in sp_line[0]


def test_emit_structured_sc():
    """SC 先于分布卡族回放。"""
    entries = [
        {"id": 2, "si": {"type": "A", "values": ["-5", "5"]},
         "sp": {"type": "", "values": ["1", "1"]},
         "sc": "comment here", "sb": None, "ds": None},
    ]
    lines = emit_distribution_entries(entries)
    assert lines[0].startswith("SC2")
    assert lines[1].startswith("SI2")


def test_emit_fn_code():
    entries = [
        {"id": 1, "si": None, "sp": {"fnCode": "-3", "fnParams": ["0.965", "2.29"]},
         "sb": None, "ds": None},
    ]
    lines = emit_distribution_entries(entries)
    assert any("SP1  -3  0.965  2.29" in l for l in lines)


# ────────────────────────────────────────────────────────────────────────────
# sync_entry
# ────────────────────────────────────────────────────────────────────────────

def test_sync_entry_raw_to_structured():
    """raw 权威 → 重派 structured 字段。"""
    e = {"id": 1, "editMode": "raw", "rawText": "SI1  -5 5\nSP1  0 1",
         "si": None, "sp": None, "sb": None, "ds": None, "sc": None}
    synced = sync_entry(e)
    assert synced["si"]["type"] == ""
    assert synced["si"]["values"] == ["-5", "5"]
    assert synced["sp"]["values"] == ["0", "1"]


def test_sync_entry_structured_to_raw():
    """structured 权威 → 重建 rawText。"""
    e = {"id": 2, "editMode": "structured",
         "si": {"type": "L", "values": ["14", "2"]},
         "sp": {"type": "D", "values": ["0.5", "0.5"], "fnCode": "", "fnParams": []},
         "sb": None, "ds": None, "sc": "note"}
    synced = sync_entry(e)
    assert synced["rawText"]  # 非空
    assert "SI2  L" in synced["rawText"]
    assert "SC2  note" in synced["rawText"]


# ────────────────────────────────────────────────────────────────────────────
# merge_distribution_entry
# ────────────────────────────────────────────────────────────────────────────

def test_merge_new_id():
    """新条目追加。"""
    existing = [{"id": 1, "si": {"type": "", "values": ["0"]}}]
    new_e = {"id": 2, "sp": {"values": ["1"]}}
    merged = merge_distribution_entry(existing, new_e)
    assert len(merged) == 2


def test_merge_existing_id_structured_fields():
    """已有 id 下只覆盖非 None 结构化字段。"""
    existing = [{"id": 1, "si": {"type": "L", "values": ["0"]}, "sp": None}]
    new_e = {"id": 1, "sp": {"values": ["1"]}}
    merged = merge_distribution_entry(existing, new_e)
    assert merged[0]["si"] == {"type": "L", "values": ["0"]}  # 未被覆盖
    assert merged[0]["sp"] == {"values": ["1"]}


def test_merge_raw_text_appended():
    """rawText 追加到既有 rawText 后面。"""
    existing = [{"id": 1, "editMode": "raw", "rawText": "SI1  0 1"}]
    new_e = {"id": 1, "rawText": "SP1  0.5 0.5"}
    merged = merge_distribution_entry(existing, new_e)
    assert merged[0]["rawText"] == "SI1  0 1\nSP1  0.5 0.5"


# ────────────────────────────────────────────────────────────────────────────
# D1 键控链检测
# ────────────────────────────────────────────────────────────────────────────

def test_d1_chain_detection():
    entries = [{"id": 1, "sp": {"values": ["D1"]}},
               {"id": 2, "sp": {"values": ["0.3", "0.7"]}}]
    assert has_d1_probability_chain(entries)
    assert multi_source_probability_count(entries) == 2


def test_d1_chain_no_chain():
    assert not has_d1_probability_chain([])
    assert not has_d1_probability_chain([{"id": 1}])
    assert not has_d1_probability_chain([{"id": 1, "sp": {"values": ["0.5"]}}])


# ────────────────────────────────────────────────────────────────────────────
# q1112 实景 round-trip（无字母 SI 原文保真）
# ────────────────────────────────────────────────────────────────────────────

def test_q1112_style_round_trip():
    """模拟 q1112 的 SI/SP 块：无字母 SI2 → 原文直通，不藏 L。"""
    lines = [
        "SI1  0.0  1.335",
        "SP1  -21  1",
        "SI2  -5.5  5.5",
        "SP2  0  1",
        "SI3  H  0.001  0.003  0.005  0.007  0.009  0.011  0.013  0.015  0.017  0.019  0.021  "
        "0.025  0.03  0.035  0.04  0.045  0.05  0.055  0.06  0.065  0.07  0.075  0.08  0.085  "
        "0.09  0.095  0.1  0.11  0.12  0.13  0.14  0.15  0.16  0.17  0.18  0.19  0.2  0.22  0.24  "
        "0.26  0.28  0.3  0.33  0.36  0.4  0.44  0.48  0.5  0.52  0.56  0.6  0.65  0.7  0.75  0.8  "
        "0.85  0.9  0.95  1.0  1.5  2.0  2.5  3.0  3.5  4.0  5.0  6.0  7.0  8.0  9.0  10.0  12.0  "
        "14.0  16.0  18.0  20.0",
        "SP3  D  0.001  0.005  0.01  0.015  0.02  0.025  0.03  0.035  0.04  0.045  0.05  0.055  "
        "0.06  0.065  0.07  0.075  0.08  0.085  0.09  0.095  0.1  0.11  0.12  0.13  0.14  0.15  "
        "0.16  0.17  0.18  0.19  0.2  0.22  0.24  0.26  0.28  0.3  0.33  0.36  0.4  0.44  0.48  "
        "0.5  0.52  0.56  0.6  0.65  0.7  0.75  0.8  0.85  0.9  0.95  1.0  1.5  2.0  2.5  3.0  3.5  "
        "4.0  5.0  6.0  7.0  8.0  9.0  10.0  12.0  14.0  16.0  18.0  20.0",
    ]
    # 解析 → v2 条目
    entries = parse_distribution_lines(lines)
    # 验证 SI2 type=""（无字母）
    si2 = [e for e in entries if e["id"] == 2][0]
    assert si2["si"]["type"] == "", f"SI2 无字母应记 type=''，实际 {si2['si']['type']!r}"
    # 发射 → raw 直通原文
    out = emit_distribution_entries(entries)
    out_text = "\n".join(out)
    # SI2 行不含 L
    for line in out:
        if line.startswith("SI2"):
            assert "  L" not in line, f"SI2 不应含 L: {line}"
            assert "-5.5" in line
    # 原文逐字保留（内部空格可能略有差异，但内容完整）
    assert "SI2  -5.5  5.5" in out_text.replace("\n", " ")
    # SI3 显式 H 保留
    si3 = [e for e in entries if e["id"] == 3][0]
    assert si3["si"]["type"] == "H"
    # SI1 内置函数
    si1 = [e for e in entries if e["id"] == 1][0]
    assert si1["sp"]["fnCode"] == "-21"


# ────────────────────────────────────────────────────────────────────────────
# AI / MCP schema 不变性（adv.sdef_distributions 字符串不透明通过）
# ────────────────────────────────────────────────────────────────────────────

def test_ai_schema_passthrough():
    """sdef_distributions 字符串经 _adv_from_dict / asdict 不受损（AI 读写路径）。"""
    from app.models import AdvancedSettings
    import dataclasses
    v2_json = json.dumps([
        {"id": 1, "editMode": "raw", "rawText": "SI1  0 1\nSP1  0.5 0.5",
         "si": {"type": "", "values": ["0", "1"]},
         "sp": {"type": "", "values": ["0.5", "0.5"], "fnCode": "", "fnParams": []},
         "sb": None, "ds": None, "sc": None, "paramRef": "", "auto": False},
    ])
    adv = AdvancedSettings(sdef_distributions=v2_json)
    d = dataclasses.asdict(adv)
    assert d["sdef_distributions"] == v2_json
    # 模拟 _adv_from_dict 重建
    adv2 = AdvancedSettings(**{k: v for k, v in d.items() if k in AdvancedSettings.__dataclass_fields__})
    assert adv2.sdef_distributions == v2_json