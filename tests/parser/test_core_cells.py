"""解析管线单测：栅元解析与 j-skip 展开。"""
import pytest

from app.generator.parsers.core import parse_cells, _expand_j_skip


# ── parse_cells ─────────────────────────────────────────
def test_parse_simple_cell():
    rows = parse_cells(["1 1 -1.0 -1 imp:n=1"])
    assert len(rows) == 1
    c = rows[0].cell
    assert c.number == 1
    assert c.material == "1"
    assert c.density == "-1.0"
    assert c.surface_expr == "-1"
    assert c.imp_n == "1"


def test_parse_void_cell_no_density():
    rows = parse_cells(["2 0 -2 imp:n=0"])
    c = rows[0].cell
    assert c.material == "0"
    assert c.density == ""
    assert c.imp_n == "0"


def test_parse_material_m1_reference():
    rows = parse_cells(["3 m1 -11.34 -3"])
    c = rows[0].cell
    assert c.material == "m1"
    assert c.density == "-11.34"
    assert c.surface_expr == "-3"


def test_parse_imp_multi_particle():
    rows = parse_cells(["1 1 -1.0 -1 imp:n,p=1"])
    c = rows[0].cell
    assert c.imp_n == "1"
    assert c.imp_p == "1"


def test_parse_imp_space_syntax():
    rows = parse_cells(["1 1 -1.0 -1 imp:n 1"])
    c = rows[0].cell
    assert c.imp_n == "1"


def test_parse_vol_pwt_u_fill_lat_trcl_tmp():
    rows = parse_cells(["1 1 -1.0 -1 vol=100 pwt=2 u=1 fill=0 lat=1 trcl=1 tmp=2.53e-8"])
    c = rows[0].cell
    assert c.vol == "100"
    assert c.pwt == "2"
    assert c.u == "1"
    assert c.fill == "0"
    assert c.lat == "1"
    assert c.trcl == "1"
    assert c.tmp == "2.53e-8"


def test_parse_other_params_captured():
    rows = parse_cells(["1 1 -1.0 -1 geo=2 wwg=1"])
    c = rows[0].cell
    assert "geo=2" in c.other_params
    assert "wwg=1" in c.other_params


def test_parse_comment_from_dollar():
    rows = parse_cells(["1 1 -1.0 -1 $ inner cell"])
    assert rows[0].cell.comment == "inner cell"


def test_parse_comment_from_c_comment_line():
    rows = parse_cells(["c fuel region", "1 1 -1.0 -1"])
    assert rows[0].cell.comment == "fuel region"


def test_parse_raw_condition_lines():
    rows = parse_cells(["#ifdef ENDF7", "1 1 -1.0 -1", "#endif"])
    assert rows[0].kind == "raw"
    assert rows[0].text == "#ifdef ENDF7"
    assert rows[-1].kind == "raw"


def test_parse_surface_expr_with_complement():
    rows = parse_cells(["1 1 -1.0 -1 #2"])
    assert rows[0].cell.surface_expr == "-1 #2"


# ── _expand_j_skip ──────────────────────────────────────
def test_expand_j_skip():
    assert _expand_j_skip(["2j", "0", "0"], 6) == ["", "", "0", "0", "", ""]


def test_expand_j_skip_repeat_r():
    assert _expand_j_skip(["1", "3R"], 5) == ["1", "1", "1", "1", ""]


def test_expand_j_skip_multiply_m():
    # str(2.0*3.0) = "6.0"（float 运算结果字符串化，pin 既有行为）
    assert _expand_j_skip(["2", "M", "3"], 4) == ["2", "6.0", "", ""]


def test_expand_j_skip_pads_short():
    assert _expand_j_skip(["0", "0"], 5) == ["0", "0", "", "", ""]
