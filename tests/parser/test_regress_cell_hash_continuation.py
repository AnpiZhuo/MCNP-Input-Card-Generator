# -*- coding: utf-8 -*-
"""回归：栅元几何的 `#`（补集算子）被误判成"条件行" + 缺空格（2026-09-26 用户实测）。

用户给的三行实卡（几何很长、手工折行，续行行首正好是 `#`）::

    5 5 -1.205e-3 -14#1#2#3#4#6#7#8#10#11#12#13#14#15#16#17#18#19#20#21 #22 #23 #24
    #25#26#27#28#29#30#31#32#33#34#35#36#37#38#39#40#41#42#43#44#45#46#47#48#49 &
    #50#51#52#53#54#55 imp:n=1 imp:p=1 $ region of interest

旧行为（两条缺陷叠加，全程无报错）：
  ① `normalize_lines` 见**行首** `#` 就当 MCNP 预处理器/条件行，当续行断点整行抛出
     ⇒ 栅元卡在第 2 行被切断（`&` 还被 `_rstrip_amp` 吃掉）；
  ② `parse_cells` 把这两行当 `kind="raw"` 行 ⇒ `surface_expr` 只剩 `#1…#24`
     （丢 31 项补集）、`imp:n/imp:p=1` 与 `$ region of interest` 一起丢；
     再生成时几何已经被静默改写。
  ③ 另：`-14#1#2` 这种**用户没打空格**的写法被原样存进 `surface_expr`，而 `#` 是几何里
     唯一"前面必须有空白"的算子 —— pymcnp 直接 `TypesError` ⇒ AST=None ⇒ 该栅元在
     3D 预览 / 源演示 / 重合检测里静默消失（实测见下 `test_glued_hash_...`）。

修法（判据 = `#` 后第一个非空白字符是**数字还是字母**）：
  · `#` + 字母（`#ifdef` / `#else` / `#endif`、THTME 表头 `#    tmp1 …`）⇒ 条件行，断点、单独成行（不变）；
  · `#` + 数字/括号（`#25` / `# 22` / `#(1 2)`）⇒ 几何补集算子 ⇒ 接回上一张几何卡；
  · 补集算子前缺空白时补一个空格（`-14#1` → `-14 #1`），已规范的写法逐字不变（护 R1 不动点）。
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for _p in (ROOT, os.path.join(ROOT, "app"), os.path.join(ROOT, "gui", "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.freecad_preview import parenthesize_unions  # noqa: E402
from app.generator.inp_generator import generate_inp_from_deck  # noqa: E402
from app.generator.parsers import parse_inp_text  # noqa: E402
from app.generator.parsers.core import parse_cells  # noqa: E402
from app.generator.parsers.lines import (  # noqa: E402
    is_preprocessor_line, normalize_geometry_spacing, normalize_lines)

# 用户实卡：第 1 行**不带** `&`（手工折行的真实形态），第 2 行带 `&`
USER_CELL_NO_AMP = (
    "probe\n"
    "5 5 -1.205e-3 -14#1#2#3#4#6#7#8#10#11#12#13#14#15#16#17#18#19#20#21 #22 #23 #24\n"
    "#25#26#27#28#29#30#31#32#33#34#35#36#37#38#39#40#41#42#43#44#45#46#47#48#49 &\n"
    "#50#51#52#53#54#55 imp:n=1 imp:p=1 $ region of interest\n"
    "\n1 pz -1\n\nMODE N\nNPS 1000\n"
)

# 同一张卡，但第 1 行行尾补上标准续行符 `&`
USER_CELL_WITH_AMP = USER_CELL_NO_AMP.replace("#22 #23 #24\n", "#22 #23 #24 &\n")

# 用户实卡里出现的全部补集项：#1…#55，但**不含 #5 与 #9**（实卡从 #4 直跳 #6、从 #8 直跳 #10）
ALL_TERMS = ["#1"] + [f"#{n}" for n in range(2, 56) if n not in (5, 9)]


def _cell_of(text: str):
    deck, _w = parse_inp_text(text)
    cells = [c for c in deck.cells if c.kind == "cell"]
    assert len(cells) == 1, f"应只解析出 1 个栅元，实得 {[(c.kind, getattr(c, 'text', None)) for c in deck.cells]}"
    return deck, cells[0].cell


@pytest.mark.parametrize("text", [USER_CELL_NO_AMP, USER_CELL_WITH_AMP],
                         ids=["第1行无&", "第1行有&"])
def test_hash_continuation_merges_into_cell(text):
    """行首 `#`+数字＝几何续行：三行必须并成一张栅元卡，补集项一项不少。"""
    deck, cell = _cell_of(text)
    expr = cell.surface_expr
    assert expr.startswith("-14 "), f"surface_expr 起始不对: {expr!r}"
    missing = [t for t in ALL_TERMS if t not in expr.split()]
    assert not missing, f"补集项丢失: {missing}"
    # imp 与行内注释也必须落在这张卡上（旧行为里它们跟着续行一起变成 raw 行）
    assert (cell.imp_n, cell.imp_p) == ("1", "1"), f"imp 丢失: {cell.imp_n!r}/{cell.imp_p!r}"
    assert cell.comment == "region of interest", f"行内注释丢失: {cell.comment!r}"
    # 没有任何 raw 行残留（旧行为：两行 raw）
    assert all(c.kind == "cell" for c in deck.cells), \
        f"残留 raw 行: {[(c.kind, getattr(c, 'text', None)) for c in deck.cells]}"


def test_hash_terms_are_space_separated_and_engine_parses():
    """补集算子前必须补空格，且补完的表达式真能被几何引擎解析成 AST。"""
    _deck, cell = _cell_of(USER_CELL_NO_AMP)
    assert "#1 #2" in cell.surface_expr, f"未补空格: {cell.surface_expr[:60]!r}"
    assert "#1#" not in cell.surface_expr and "#2#" not in cell.surface_expr, \
        f"还有粘连的补集算子: {cell.surface_expr[:80]!r}"
    Geometry = pytest.importorskip("pymcnp.types.Geometry").Geometry
    ast = Geometry.from_mcnp(parenthesize_unions(cell.surface_expr))
    assert ast is not None and ast.ast is not None, "补空格后几何引擎仍解析不出 AST"


def test_glued_hash_is_rejected_by_geometry_engine():
    """反向对照：`#` 前缺空白是**引擎硬要求**，不是排版美观问题。

    实测（pymcnp 内置版本）：`-14#1#2#3` → TypesError「MCNP data type not recognized」，
    `-14 #1 #2 #3` → 正常。若将来 pymcnp 接受了粘连写法，可重估补空格是否仍必要
    （但那时仍需重核 R1 字节不动点）。
    """
    Geometry = pytest.importorskip("pymcnp.types.Geometry").Geometry
    try:
        ast = Geometry.from_mcnp("(-14#1#2)")
        accepted = ast is not None and ast.ast is not None
    except Exception:
        accepted = False
    assert not accepted, "当前 pymcnp 已能解析缺空白的 `#`；补空格是否仍必要需重新评估"


def test_roundtrip_keeps_geometry_and_imp():
    """parse → generate 往返：几何、imp、注释都不许被改写或丢失。"""
    deck, _cell = _cell_of(USER_CELL_NO_AMP)
    out = generate_inp_from_deck(deck)
    deck2, _w = parse_inp_text(out)
    cells2 = [c for c in deck2.cells if c.kind == "cell"]
    assert len(cells2) == 1, f"往返后栅元数变了: {[(c.kind, getattr(c, 'text', None)) for c in deck2.cells]}"
    expr2 = cells2[0].cell.surface_expr
    assert [t for t in ALL_TERMS if t not in expr2.split()] == [], f"往返后补集项丢失: {expr2!r}"
    assert (cells2[0].cell.imp_n, cells2[0].cell.imp_p) == ("1", "1")


# ── 反向边界：`#`+字母仍必须是条件行断点（不得被上面的规则吞进上一张卡）──

def test_ifdef_line_is_still_a_breakpoint():
    """`#ifdef` 等宏指令仍是断点、单独成行（否则缩进核素行会被并进宏行）。"""
    text = "M1 1001.06c 1\n#ifdef ENDF7\n   50112. 1\n#endif\n"
    out = normalize_lines(text)
    assert "#ifdef ENDF7" in out and "#endif" in out, out
    assert not any(l.startswith("M1") and "#ifdef" in l for l in out), out
    assert is_preprocessor_line("#ifdef ENDF7") and is_preprocessor_line("#  tmp1  tmp2")
    assert not is_preprocessor_line("#25#26") and not is_preprocessor_line("#(1 2)")


def test_thtme_table_header_not_merged_into_card():
    """THTME 表头（`#` + 空白 + 列名）紧随 `THTME …` 行时不得被并进该卡。"""
    text = "THTME -10 0 .5 1 2\n#    tmp1  tmp2  tmp3\n   1  1e-8  2e-8  3e-8\n"
    out = normalize_lines(text)
    assert out[0].startswith("THTME"), out
    assert out[1].strip().startswith("#") and "tmp1" in out[1], out
    assert len([l for l in out if "tmp1" in l]) == 1


def test_leading_hash_without_prev_cell_is_preserved_as_raw():
    """没有可接的上一张几何卡时（如文件首行就是 `#25`）不得静默丢：原样保留为 raw 行。"""
    cells = parse_cells(["#25#26 imp:n=1"])
    assert len(cells) == 1 and cells[0].kind == "raw", \
        f"应保留为 raw 行，实得 {[(c.kind, getattr(c, 'text', None)) for c in cells]}"
    assert "#25#26" in cells[0].text


def test_preprocessor_line_in_cell_section_stays_raw():
    """栅元段里的 `#ifdef` 仍进 raw 行（不进 surface_expr）。"""
    cells = parse_cells(["1 0 -1 imp:n=1", "#ifdef X", "2 0 -2"])
    assert [c.kind for c in cells] == ["cell", "raw", "cell"], \
        f"{[(c.kind, getattr(c, 'text', None)) for c in cells]}"


# ── 空格规范化助手本身 ──

@pytest.mark.parametrize("raw,expected", [
    ("-14#1#2#3", "-14 #1 #2 #3"),
    ("#1", "#1"),                        # 行首（无前导字符）不动
    ("1 -2 #3", "1 -2 #3"),              # 已规范：逐字不变（R1）
    ("1 -2 # 3", "1 -2 # 3"),            # 已规范
    ("(#1 -2)", "(#1 -2)"),              # `(` 之后已是边界
    ("-14#(1 2)", "-14 #(1 2)"),
    ("", ""),
])
def test_normalize_geometry_spacing(raw, expected):
    assert normalize_geometry_spacing(raw) == expected


def test_spacing_leaves_already_canonical_deck_byte_identical():
    """已带空格的实卡（BEAVRS `#351 #352`）解析后逐字不变 —— 护 R1 字节不动点。"""
    line = "355 5 7.41863e-2  85 -86 700 -730 #351 #352 #353 #354 imp:n=1  $ NS water"
    cells = parse_cells([line])
    assert cells[0].cell.surface_expr == "85 -86 700 -730 #351 #352 #353 #354"
