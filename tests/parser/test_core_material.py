"""解析管线单测：材料解析与 r 重复展开。"""
from app.generator.parsers.core import _parse_material, _expand_repeat, _is_zaid_line


def test_parse_material_basic():
    mat = _parse_material(["m1", "92235", "-0.05", "8016", "0.10"], "m1")
    assert mat.number == 1
    assert len(mat.rows) == 2
    assert mat.rows[0].zaid == "92235" and mat.rows[0].fraction == "-0.05"
    assert mat.rows[1].zaid == "8016" and mat.rows[1].fraction == "0.10"


def test_parse_material_options():
    mat = _parse_material(["m1", "92235", "-0.05", "nlib=.66c", "gas=1"], "m1")
    assert "nlib=.66c" in mat.options
    assert "gas=1" in mat.options


def test_parse_material_single_keyword_option():
    mat = _parse_material(["m1", "92235", "-0.05", "plib"], "m1")
    assert "plib" in mat.options


def test_is_zaid_line():
    assert _is_zaid_line("92235")
    assert _is_zaid_line("92235.06c")
    assert _is_zaid_line("13027")
    assert _is_zaid_line("U-235")
    assert not _is_zaid_line("nlib=.66c")
    assert not _is_zaid_line("#endif")


def test_expand_repeat():
    assert _expand_repeat(["1.0", "42r", "0.0", "5r"]) == ["1.0"] * 43 + ["0.0"] * 6
