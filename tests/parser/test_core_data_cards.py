"""解析管线单测：parse_data_cards 数据卡段主解析。"""
from app.generator.parsers.core import parse_data_cards


def test_parse_basic_cards():
    r = parse_data_cards(["mode n p", "nps 100000", "ctme 10", "nonu", "act 2j 1",
                          "print 128"])
    assert r["mode_n"] is True
    assert r["mode_p"] is True
    assert r["nps"] == "100000"
    assert r["ctme"] == "10"
    assert r["nonu"] is True
    assert r["act"] == "2j 1"
    assert r["print_pr"] == "128"


def test_parse_material():
    r = parse_data_cards(["m1 92235 -0.05 8016 0.10"])
    assert len(r["materials"]) == 1
    mat = r["materials"][0]
    assert mat.number == 1
    assert len(mat.rows) == 2


def test_parse_sdef_with_si_sp():
    r = parse_data_cards(["sdef erg=d1 pos=0 0 0", "si1 0 14", "sp1 0.5 0.5"])
    assert r["source_mode"] == "distribution"
    assert r["sdef_erg"] == "d1"
    # SI/SP 行原样小写保留在 sdef_raw_text（序列化 JSON 串）
    assert "si1 0 14" in r["sdef_raw_text"].lower()
    assert "sp1 0.5 0.5" in r["sdef_raw_text"].lower()


def test_parse_tally():
    r = parse_data_cards(["f4:n 1 2", "f1:n 1"])
    assert len(r["tally_defs"]) == 2
    assert r["tally_defs"][0].type == "F4"
    assert r["tally_defs"][0].params == "1 2"


def test_parse_e0_parametric():
    r = parse_data_cards(["e0 0.001 100log 14"])
    assert r["e0_parametric"] is True
    assert r["e0_bins"] == 100
    assert r["e0_log"] is True


def test_parse_en_cards():
    r = parse_data_cards(["e4 1 2 3 4", "e1 0.1 1"])
    assert len(r["e_cards_lines"]) == 2
    assert r["e_cards_lines"][0].startswith("e4")  # 原文大小写保留


def test_parse_t0_and_tn():
    # 参数化语法：t0 t1 nI tend（10 个线性间隔从 0 到 100）
    r = parse_data_cards(["t0 0 10i 100", "t4 0 5 10"])
    assert r["t0_parametric"] is True
    assert r["t0_bins"] == 10
    assert len(r["t_cards_lines"]) == 1


def test_parse_cut():
    r = parse_data_cards(["cut:n 100 1e-4 0.5"])
    assert r["tallies"]["cut_n_t"] == "100"


def test_parse_phys_n():
    r = parse_data_cards(["phys:n 100 0.1 1"])
    assert r["phys_n_emax"] == "100"
    assert r["phys_n_emcnf"] == "0.1"
    assert r["phys_n_iunr"] == "1"


def test_parse_kcode_and_ksrc():
    # KSRC 多点在单行（真实 MCNP 用 5 空格续行，normalize 已合并）
    r = parse_data_cards(["kcode 1000 1.0 30 100", "ksrc 0 0 0 1 1 1"])
    assert r["source_mode"] == "kcode"
    assert r["kcode_nsrc"] == "1000"
    assert len(r["ksrc_points"]) == 2
    assert r["ksrc_points"][1] == {"x": "1", "y": "1", "z": "1"}


def test_parse_hsrc():
    r = parse_data_cards(["hsrc 3 0 1 10 -10 10 10"])
    assert r["hsrc_enabled"] is True
    assert r["hsrc_text"] == "3 0 1 10 -10 10 10"


def test_parse_ssw_ssr():
    r = parse_data_cards(["ssw 1 2 sym=1 pty=N", "ssr 2 old cel=2"])
    assert r["source_mode"] == "surface"
    assert r["ssw_surf"] == "1 2"
    assert r["ssw_sym"] == "1"
    assert r["ssr_surf"] == "2"
    assert r["ssr_mode"] == "OLD"


def test_parse_tr_cards():
    r = parse_data_cards(["tr1 1 0 0 0 1 0 0 0 1 5 0 0"])
    assert len(r["tr_cards"]) == 1


def test_parse_imp_n_data_card():
    r = parse_data_cards(["imp:n 1 0 1"])
    assert r["imp_n_values"] == ["1", "0", "1"]


def test_parse_preprocessor_lines_attach_to_material():
    r = parse_data_cards(["#ifdef MOD1", "m1 92235 0.05", "#endif"])
    assert len(r["materials"]) == 1
    texts = [row.text for row in r["materials"][0].rows if row.kind == "raw"]
    assert "#ifdef MOD1" in texts


def test_parse_ifdef_block_within_material_splits_macro_and_nuclides():
    """条件核素块归属当前材料：#ifdef 块（宏+核素可能被续行合并成一行）拆回 raw 宏 + 核素对，
    #endif 也归属当前材料而非误挂到后续 M（u233 官方样例 Zircaloy 条件 Sn 块回归）。"""
    r = parse_data_cards([
        "m1 40090 2.1885e-2",
        "#ifdef ENDF7 50112. 4.8420e-6 50114. 3.2447e-6 50115. 1.6972e-6",
        "#endif",
        "m2 1001 7.8854e-2 6000 3.9427e-2",
    ])
    assert len(r["materials"]) == 2
    m1, m2 = r["materials"]
    # M1：40090 + raw #ifdef ENDF7 + 50112/50114/50115 核素对 + raw #endif（#endif 不跳 M2）
    rows1 = [(x.kind, x.zaid or x.text, x.fraction) for x in m1.rows]
    assert rows1[0] == ("nuclide", "40090", "2.1885e-2")
    assert rows1[1] == ("raw", "#ifdef ENDF7", "")
    assert rows1[2] == ("nuclide", "50112.", "4.8420e-6")
    assert rows1[3] == ("nuclide", "50114.", "3.2447e-6")
    assert rows1[4] == ("nuclide", "50115.", "1.6972e-6")
    assert rows1[-1] == ("raw", "#endif", "")
    # M2 干净，不带 #endif
    rows2 = [(x.kind, x.zaid or x.text) for x in m2.rows]
    assert rows2 == [("nuclide", "1001"), ("nuclide", "6000")]
    assert not any(x.kind == "raw" for x in m2.rows)


def test_parse_unknown_cards_to_other_cards():
    r = parse_data_cards(["dbcn 28j 0 13j 0", "prdmp 2j -1 j -1"])
    assert any("dbcn" in c.lower() for c in r["other_cards"])
    assert any("prdmp" in c.lower() for c in r["other_cards"])


def test_parse_imp_n_r_repeat():
    r = parse_data_cards(["imp:n 1 42r 0"])
    assert len(r["imp_n_values"]) == 44
