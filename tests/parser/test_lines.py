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


# ── 续行拼接：断点在 token 中间时不能补空格（2026-09-23 实测根因） ──

def test_continuation_inside_token_is_glued_not_spaced():
    """GEOUNED 按 80 列硬折行会把一个 token 截成两半。

    实测原始文件（`厂房建模.step` 的真空栅元 24）：
        第 408 行 '... (160:-122:140:'
        第 409 行 '           -220:-190) ...'
    旧实现无条件补空格 ⇒ `140: -220` ⇒ pymcnp `_Digit.from_mcnp` 断言失败
    ⇒ AST=None ⇒ 3D 预览 HTTP 500。
    """
    text = "24 0 254 -263 (-160:190:-139:-209:140) (160:-122:140:\n           -220:-190)"
    out = normalize_lines(text)
    assert len(out) == 1
    assert "(160:-122:140:-220:-190)" in out[0], out[0]


def test_continuation_between_two_numbers_keeps_separator():
    """反向边界：断点两侧都是词字符时必须补空格，否则 `-1` 与 `2` 会粘成 `-12`。"""
    text = "1 1 -1 -101\n           2 -102"
    out = normalize_lines(text)
    assert len(out) == 1
    assert " -101 2 " in out[0] + " ", out[0]


def test_continuation_after_operator_is_glued():
    """运算符/指数被截断时同样直接接上（`e-` + `8` → `e-8`）。"""
    text = "tmp=2.53e-\n     8"
    out = normalize_lines(text)
    assert "2.53e-8" in out[0], out[0]


def test_continuation_at_real_token_boundary_keeps_space():
    """反向边界（护 R1 字节不动点）：断点**可能是合法 token 边界**时必须补空格。

    prob41c 实测：`(9 0 9)` 后接 `1)` —— 这类折行是**在 token 边界**折的，原逻辑行里
    本来就有空格。若在这里也"直接相接"会得到 `(9 0 9)1)`，parse→generate 不再字节相同
    （实测：4 failed + 21 errors，R1 不动点全红）。
    """
    text = "1 (9 0 9)\n     1 (9 0 9) 0 0"
    out = normalize_lines(text)
    assert "(9 0 9) 1 (9 0 9)" in out[0], out[0]


def test_continuation_leading_colon_is_glued():
    """行首是 `:`（并集链被截断）→ 直接相接。"""
    text = "24 0 -190\n           :240"
    out = normalize_lines(text)
    assert "-190:240" in out[0], out[0]
