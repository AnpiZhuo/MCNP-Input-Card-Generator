"""回归测试：other_cards 行内 $ 注释被剥离（词条审计 D-10，P2，影响全部未设计卡）。

缺陷（当前工作树，2026-08-13）：
  app/generator/parsers/core.py parse_data_cards 顶部（:941）
  `line = strip_comment(raw_line.strip())` 剥离行内 `$ 注释`；
  other_cards 各 append 点（:1018/:1059/:1064/:1128/:1260/:1291）均存剥离后的 `line`
  → 未设计卡上的 `$ 注释` 在解析时被剥离，round-trip 后不保真（卡功能数据不丢，
    但卡行文本非逐字保真）。影响所有走 other_cards 的未设计卡（含 D-02/D-09 全部）。

触发场景（**2026-09-10 更正：已清偿 → 本文件为验收基准，应全绿**；"当前红"为初版遗留）：
  ① PTRAC $ write particles（_KNOWN_OTHER_CARDS 命中，core.py:1258-1260）；
  ② FILES 22 DUM1 8 $ output files（else 兜底命中，core.py:1282-1291）；
  ③ RAND GEN=2 SEED=12345 $ reproducible（else 兜底命中）。

期望修复后行为（验收基准）：
  other_cards append 改存 raw_line（保留 `$ 注释`），与结构化卡 comment 字段语义区分
  → 未设计卡 `$ 注释` 在 parse 与 round-trip（parse→generate→parse）均不丢。
"""
from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.generator.parsers.core import parse_data_cards


# ---- parse_data_cards 层：other_cards 原样保留 $ 注释 -------------------------

def test_known_other_card_inline_comment_preserved():
    """PTRAC（_KNOWN_OTHER_CARDS 命中）行内 $ 注释在 other_cards 中保留。"""
    result = parse_data_cards(["PTRAC $ write particles"])
    joined = "\n".join(result["other_cards"])
    assert "write particles" in joined, (
        f"PTRAC 行内 $ 注释被 strip_comment 剥离。other_cards={result['other_cards']!r}"
    )
    assert "$" in joined, f"PTRAC 行内 $ 注释被剥离。other_cards={result['other_cards']!r}"


def test_else_other_card_inline_comment_preserved():
    """FILES（else 兜底命中）行内 $ 注释在 other_cards 中保留。"""
    result = parse_data_cards(["FILES 22 DUM1 8 $ output files"])
    joined = "\n".join(result["other_cards"])
    assert "output files" in joined, (
        f"FILES 行内 $ 注释被 strip_comment 剥离。other_cards={result['other_cards']!r}"
    )


def test_rand_other_card_inline_comment_preserved():
    """RAND（else 兜底命中）行内 $ 注释在 other_cards 中保留。"""
    result = parse_data_cards(["RAND GEN=2 SEED=12345 $ reproducible"])
    joined = "\n".join(result["other_cards"])
    assert "reproducible" in joined, (
        f"RAND 行内 $ 注释被 strip_comment 剥离。other_cards={result['other_cards']!r}"
    )


# ---- round-trip：parse→generate→parse 后 $ 注释仍保留 --------------------------

def _shell_wrap_data(text: str) -> str:
    """数据卡文本放入数据段（cells/surfaces 之后），供 parse_inp_text 全链路 round-trip。"""
    return f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"


def test_other_card_inline_comment_round_trip_preserved():
    """PTRAC $ 注释经 parse→generate→parse 后仍保留（round-trip 不丢）。"""
    src_card = "PTRAC $ write particles"
    deck, _warnings = parse_inp_text(_shell_wrap_data(src_card))
    out = generate_inp_from_deck(deck)
    assert "write particles" in out, (
        f"round-trip 输出丢失 PTRAC 行内 $ 注释。输出:\n{out}"
    )
    deck2, _w2 = parse_inp_text(out)
    assert "write particles" in deck2.adv.other_cards, (
        f"round-trip 重解析丢失 PTRAC 行内 $ 注释。other_cards={deck2.adv.other_cards!r}"
    )


def test_files_inline_comment_round_trip_preserved():
    """FILES $ 注释经 parse→generate→parse 后仍保留（round-trip 不丢）。"""
    src_card = "FILES 22 DUM1 8 $ output files"
    deck, _warnings = parse_inp_text(_shell_wrap_data(src_card))
    out = generate_inp_from_deck(deck)
    assert "output files" in out, (
        f"round-trip 输出丢失 FILES 行内 $ 注释。输出:\n{out}"
    )
    deck2, _w2 = parse_inp_text(out)
    assert "output files" in deck2.adv.other_cards, (
        f"round-trip 重解析丢失 FILES 行内 $ 注释。other_cards={deck2.adv.other_cards!r}"
    )
