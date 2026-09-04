# -*- coding: utf-8 -*-
"""inputcard-mcp 全量覆盖：list_section / patch_section 往返不丢语义（深模块测试面）。

这些工具以「后端语义段」为单位（复用 api_server 的 _xxx_from_dict 映射，与 deck_from_json 同口径），
所以「list_section 读回 → 改 → patch_section 写回」应当自洽：写入的语义能被重新生成并读回。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for _p in (ROOT, os.path.join(ROOT, "app"), os.path.join(ROOT, "gui", "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from inputcard_mcp.server import list_section, patch_section, read_document  # noqa: E402


INP = """my title
1 1 -1.0 -1

1 pz 0
2 pz 1
"""


def test_patch_sources_generates_sdef_and_reads_back():
    out = patch_section(INP, "sources",
                        [{"number": 1, "par": "n", "erg": "14.0", "pos_x": "0", "pos_y": "0", "pos_z": "0"}])
    assert "sdef" in out.lower()
    got = list_section(out, "sources")
    assert got and got[0]["erg"] == "14.0"
    assert got[0]["par"] == "n"


def test_patch_tally_generates_fcard_and_reads_back():
    out = patch_section(INP, "tally",
                        {"tallies": [{"type": "F4", "number": 4, "particles": ["n"], "params": "1"}]})
    assert "f4:n" in out.lower()
    got = list_section(out, "tally")
    assert got["tallies"][0]["params"] == "1"


def test_patch_advanced_kcode_and_reads_back():
    out = patch_section(INP, "advanced",
                        {"source_mode": "kcode", "kcode_nsrc": "1000", "kcode_rkk": "1.0", "ksrc_points": "0 0 0"})
    assert "kcode" in out.lower()
    got = list_section(out, "advanced")
    assert got["source_mode"] == "kcode"
    assert got["kcode_nsrc"] == "1000"


def test_read_modify_write_roundtrip():
    # 读→改→写→读，语义应保留
    out1 = patch_section(INP, "sources", [{"number": 1, "par": "n", "erg": "14.0"}])
    got = list_section(out1, "sources")
    assert got and got[0]["erg"] == "14.0"
    got[0]["erg"] = "13.0"
    out2 = patch_section(out1, "sources", got)
    again = list_section(out2, "sources")
    assert again[0]["erg"] == "13.0"


def test_list_section_bad_section_rejected():
    try:
        list_section(INP, "not_a_section")
        assert False, "should raise"
    except ValueError:
        pass
