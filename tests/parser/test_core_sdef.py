"""解析管线单测：SDEF 解析（parse_sdef_simple / parse_sdef_fields）。"""
from app.generator.parsers.core import parse_sdef_simple, parse_sdef_fields


# ── parse_sdef_simple（固定源模式）──────────────────────
def test_sdef_simple_pos():
    srcs = parse_sdef_simple(["sdef", "pos", "9", "6", "9"])
    assert len(srcs) == 1
    s = srcs[0]
    assert s.pos_x == "9" and s.pos_y == "6" and s.pos_z == "9"


def test_sdef_simple_pos_equals():
    srcs = parse_sdef_simple(["sdef", "POS=0", "0", "0", "ERG=14.0"])
    s = srcs[0]
    assert s.pos_x == "0" and s.pos_y == "0" and s.pos_z == "0"
    assert s.erg == "14.0"


def test_sdef_simple_known_fields():
    srcs = parse_sdef_simple(["sdef", "PAR=1", "ERG=D1", "DIR=1", "WGT=1.0",
                              "CEL=1", "TME=0.0"])
    s = srcs[0]
    assert s.par == "1"
    assert s.erg == "D1"
    assert s.dir_ == "1"
    assert s.wgt == "1.0"
    assert s.cel == "1"
    assert s.tme == "0.0"


def test_sdef_simple_eff_bare_value_preserved():
    # 翻新（F-G）：EFF 裸值应保留进 sdef_extra（不再静默丢弃）
    srcs = parse_sdef_simple(["sdef", "POS=0", "0", "0", "EFF=2"])
    s = srcs[0]
    assert s.sdef_extra == "EFF=2"


def test_sdef_simple_eff_with_continuation_preserves_prefix():
    # 翻新（F-G）：EFF 带续值 → 前缀 EFF=2 与续值 5 都应保留（sdef_extra == "EFF=2 5"）
    srcs = parse_sdef_simple(["sdef", "POS=0", "0", "0", "EFF=2", "5"])
    assert srcs[0].sdef_extra == "EFF=2 5"


# ── parse_sdef_fields（分布源模式）───────────────────────
def test_sdef_fields_pos_vector():
    r = parse_sdef_fields(["sdef", "POS=0", "0", "0"])
    assert r["sdef_pos_x"] == "0"
    assert r["sdef_pos_y"] == "0"
    assert r["sdef_pos_z"] == "0"


def test_sdef_fields_pos_d_ref_triple_same():
    # POS=D1 单引用 → 三元组同引用（再生成保三元组语义）
    r = parse_sdef_fields(["sdef", "POS=D1"])
    assert r["sdef_pos_x"] == "D1"
    assert r["sdef_pos_y"] == "D1"
    assert r["sdef_pos_z"] == "D1"


def test_sdef_fields_erg_vec():
    r = parse_sdef_fields(["sdef", "ERG=D2", "VEC=1", "-1", "0"])
    assert r["sdef_erg"] == "D2"
    assert r["sdef_vec"] == "1 -1 0"


def test_sdef_fields_x_y_z():
    r = parse_sdef_fields(["sdef", "X=D1", "Y=D2", "Z=D3"])
    assert r["sdef_pos_x"] == "D1"
    assert r["sdef_pos_y"] == "D2"
    assert r["sdef_pos_z"] == "D3"
