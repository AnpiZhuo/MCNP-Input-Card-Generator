"""解析管线单测：行处理（注释剥离 / 续行合并）。"""
from app.generator.parsers.lines import strip_comment, extract_comment, normalize_lines


def test_strip_comment():
    assert strip_comment("1 1 -1 $ inner cell") == "1 1 -1 "
    assert strip_comment("no comment") == "no comment"


def test_extract_comment():
    assert extract_comment("1 1 -1 $ inner cell") == "inner cell"
    assert extract_comment("no comment") == ""


def test_normalize_merges_indented_continuation():
    text = "sdef erg=d1\n     pos=0 0 0\n     axs=1"
    out = normalize_lines(text)
    assert len(out) == 1
    assert "pos=0 0 0" in out[0]
    assert "axs=1" in out[0]


def test_normalize_merges_ampersand_continuation():
    # MCNP & 续行：前一行以 & 结尾，下一行为续行
    text = "sdef erg=d1 &\n     axs=1"
    out = normalize_lines(text)
    assert len(out) == 1
    assert "axs=1" in out[0]


def test_normalize_keeps_c_comments_as_breakpoints():
    text = "1 1 -1\nc cell card\n2 0 -2\n"
    out = normalize_lines(text)
    assert any(l.upper().startswith("C") for l in out)


def test_normalize_preserves_preprocessor_lines():
    text = "#ifdef ENDF7\n    92235 0.05\n#endif\n"
    out = normalize_lines(text)
    assert "#ifdef ENDF7" in out
    assert "#endif" in out


def test_normalize_blank_lines_preserved():
    out = normalize_lines("1 1 -1\n\n1 pz 0\n")
    assert out.count("") >= 1
