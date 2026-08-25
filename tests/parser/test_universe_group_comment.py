"""项9：U 分组头注释 → INP C 注释 round-trip（生成插注释 / 解析吸收 / 字节不动点）。

设计契约（lattice-fix15-design.md §1 项9）：
  - 存储：deck.universeComments（backend DeckData.universe_comments，键 snake_case u_str）
  - 生成：_generate_cells 按「当前 cell 顺序中相邻同 U 连续段」在该组首个栅元行前插
    `C  U-group U=<n>: <user text>`（唯一发射源 banners.universe_group_banner）
  - 解析：parse-inp 识别 `C  U-group U=` 前缀 C 行 → deck.universe_comments
    （从 cell 注释 / other_cards 路径排除，防被吞）
  - R1：parse→gen→parse 字节稳定；既有夹具无 universeComments → 零影响。
"""
import pytest

from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.models import (BasicSettings, DeckData, CellRow, CellData,
                        TallySettings, AdvancedSettings)


def _ug_deck() -> DeckData:
    """含 universe_comments 的多 U 连续段 deck（U=10 两段、U=1 一段）。"""
    return DeckData(
        basic=BasicSettings(title="ug roundtrip", mode_n=True, nps="100"),
        surfaces="1  pz  0\n2  pz  -1\n3  so  10",
        cells=[
            CellRow(kind="cell", cell=CellData(
                number=1, material="0", density="", surface_expr="-3",
                u="10", comment="c10")),
            CellRow(kind="cell", cell=CellData(
                number=2, material="0", density="", surface_expr="-1 2",
                u="10", comment="c10b")),
            CellRow(kind="cell", cell=CellData(
                number=3, material="1", density="-1.0", surface_expr="1 -2",
                u="1", comment="leaf")),
            CellRow(kind="cell", cell=CellData(
                number=4, material="0", density="", surface_expr="-3",
                u="10", comment="c10c")),
        ],
        materials=[], sources=[], tally=TallySettings(),
        adv=AdvancedSettings(),
        universe_comments={"10": "核心燃料组件", "1": "围板"},
    )


def test_generate_inserts_universe_group_comments():
    """生成：按 U 分组稳定排序（未分组在前、数值 U 升序）后，每 U 组恰插一条
    `C  U-group U=<n>: <text>`（用户要求：分组排序生成，使注释每 U 组一条）。"""
    g = generate_inp_from_deck(_ug_deck())
    lines = [l.rstrip() for l in g.split("\n")]
    # 排序后 u="1"（cell 3）在前、u="10"（cell 1/2/4 连续）在后 → 恰 2 条注释
    ug = [i for i, l in enumerate(lines) if l.startswith("C  U-group")]
    assert len(ug) == 2, lines
    assert "U=1: 围板" in lines[ug[0]]
    assert "U=10: 核心燃料组件" in lines[ug[1]]
    # 注释不污染 cell 行内 $ 注释（cell 1 的 $ c10 保留原样）
    cell1 = next(l for l in lines if l.startswith("1  "))
    assert "$ c10" in cell1


def test_parse_absorbs_universe_group_comments():
    """解析：`C  U-group U=` 前缀 C 行 → deck.universe_comments（不进 cell 注释/other_cards）。"""
    g = generate_inp_from_deck(_ug_deck())
    deck, warns = parse_inp_text(g)
    assert warns == [], warns
    assert deck.universe_comments == {"10": "核心燃料组件", "1": "围板"}
    # 不被吸收为 cell 注释（cell 1 的 comment 应保持 $ c10，而非 U-group 文本）
    c1 = next(c.cell for c in deck.cells
              if c.kind == "cell" and c.cell.number == 1)
    assert c1.comment == "c10", f"cell1 comment 被 U-group 注释污染: {c1.comment!r}"
    # 不进 other_cards
    assert "U-group" not in deck.adv.other_cards


def test_universe_group_comment_roundtrip():
    """R1 不动点：gen→parse→gen 字节稳定（新夹具）。"""
    g1 = generate_inp_from_deck(_ug_deck())
    deck2, _ = parse_inp_text(g1)
    g2 = generate_inp_from_deck(deck2)
    assert g1 == g2, f"U-group 注释 R1 不动点不成立（len {len(g1)} → {len(g2)}）"
    # 二次解析 universe_comments 仍保持
    deck3, _ = parse_inp_text(g2)
    assert deck3.universe_comments == {"10": "核心燃料组件", "1": "围板"}


def test_no_universe_comments_still_generates_group_header():
    """无 universeComments 也生成 U-group 头注释（用户要求：未编辑也生成）——每 U 组一条。"""
    deck = _ug_deck()
    deck.universe_comments = {}
    g = generate_inp_from_deck(deck)
    ug = [l for l in g.split("\n") if l.startswith("C  U-group")]
    assert len(ug) == 2, g  # 排序后 U=1、U=10 各一条（无文本）
    assert all("U=" in l for l in ug)
    # 无注释 deck parse→gen→parse 仍字节稳定
    g1 = generate_inp_from_deck(deck)
    deck2, _ = parse_inp_text(g1)
    g2 = generate_inp_from_deck(deck2)
    assert g1 == g2


def test_raw_rows_do_not_break_contiguous_run():
    """raw 条件行不打断相邻同 U 连续段（U=10 的 cell 1、raw 行、cell 2 仍同一段）。"""
    deck = _ug_deck()
    deck.cells.insert(2, CellRow(kind="raw", text="#ifdef EXTRA"))
    g = generate_inp_from_deck(deck)
    lines = [l.rstrip() for l in g.split("\n")]
    ug = [i for i, l in enumerate(lines) if l.startswith("C  U-group")]
    # raw 行不打断 → cell1/raw/cell2 仍同一 U=10 段（仅段首一条注释）
    assert len(ug) == 3, f"raw 行错误打断连续段: {ug}"
