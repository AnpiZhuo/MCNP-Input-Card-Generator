"""解析管线单测：计数卡（F 卡）与 CUT 卡解析。"""
from app.generator.parsers.core import parse_f_tally, parse_cut


def test_parse_f_tally_basic():
    tally_defs = []
    handled = parse_f_tally(["F4:N", "1", "2"], tally_defs)
    assert handled is True
    assert len(tally_defs) == 1
    td = tally_defs[0]
    assert td.type == "F4" and td.number == 4
    assert td.particles == ["n"]
    assert td.params == "1 2"


def test_parse_f_tally_merges_particles():
    tally_defs = []
    parse_f_tally(["F4:N", "1"], tally_defs)
    parse_f_tally(["F4:P", "1"], tally_defs)
    assert len(tally_defs) == 1
    assert tally_defs[0].particles == ["n", "p"]


def test_parse_f_tally_multipoint_f5():
    tally_defs = []
    parse_f_tally(["F5:N", "1", "2", "3", "1", "2", "4"], tally_defs)
    assert tally_defs[0].type == "F5"
    assert tally_defs[0].params == "1 2 3 1 2 4"


def test_parse_f_tally_ring_detector():
    tally_defs = []
    parse_f_tally(["F5X:N", "1", "2", "3"], tally_defs)
    td = tally_defs[0]
    assert td.type == "F5"
    assert td.number_suffix == "X"


def test_parse_f_tally_imaging():
    tally_defs = []
    parse_f_tally(["FIP4:N", "1"], tally_defs)
    assert tally_defs[0].fn_prefix == "FIP"
    assert tally_defs[0].number == 4


def test_parse_f_tally_unsupported_number_returns_false():
    tally_defs = []
    handled = parse_f_tally(["F9:N", "1"], tally_defs)
    assert handled is False
    assert tally_defs == []


def test_parse_f_tally_non_tally_returns_none():
    handled = parse_f_tally(["SDEF", "POS=0"], [])
    assert handled is None


def test_parse_cut_n():
    d = {}
    parse_cut(["CUT:N", "100", "1e-4", "0.5"], d)
    assert d["cut_n_t"] == "100"
    assert d["cut_n_e"] == "1e-4"
    assert d["cut_n_wc1"] == "0.5"
    assert d["cut_n_raw"] == "100 1e-4 0.5"


def test_parse_cut_j_skip_expanded():
    d = {}
    parse_cut(["CUT:N", "100", "j", "j", "0.5"], d)
    assert d["cut_n_t"] == "100"
    assert d["cut_n_e"] == ""
    assert d["cut_n_wc1"] == ""
    assert d["cut_n_wc2"] == "0.5"
