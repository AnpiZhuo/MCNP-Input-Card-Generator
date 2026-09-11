r"""回归测试：sections.py 分节识别缺口（词条审计 D-03，P1 边界误分 → 兜底网失效）。

缺陷（当前工作树，2026-08-13）：
  app/generator/parsers/sections.py DATA_KEYWORDS（:131-138）+ DATA_PATTERNS（:140-153）
  未收录 Cn/DE/DF/FS/SD/CF/SF/EM/TM/CM/TF/DD/DXT/SBn/DSn/SCn/ELPT/NOTRN/TALNP/MPLOT/
  RAND/FILES/IDUM/RDUM/FMESHn（带编号）等词条，也未收 `^[*+]?F\d+` / `^[*+]?F\d+[XYZ]:?`
  前缀正则（*F4/+F4/F5Z:P 环探测器）。
  → 未设计卡在「节首」出现（phase 仍为 cell/surface，作为首个数据卡）被误分到栅元/曲面段，
     不落 data_lines → 不达 parse_data_cards → other_cards 兜底网失效。

触发场景（**2026-09-10 更正：已清偿 → 本文件为验收基准，应全绿**；"当前红"为初版遗留）：
  ① 标题行+空行后直接是未设计数据卡（前面没有任何已识别数据卡）；
  ② 紧凑 INP：cells/surfaces 后无空行分隔、且无 MODE/NPS 等数据关键词先行，首数据卡即
     *F4 / +F4 / F5Z:P（pm 补充：与 D-03 同根因，误分曲面段后被 parse_surfaces 丢弃）。

期望修复后行为（验收基准）：
  sections.py DATA_PATTERNS 补词条与 `^[*+]?F\d+`/`^[*+]?F\d+[XYZ]:?` 前缀正则
  → 未设计卡在节首进 data_lines → 数据卡进 other_cards 兜底 / F 卡进 tally_defs。
"""
import pytest

from app.generator.parsers import parse_inp_text
from app.generator.parsers.sections import split_sections


# ---- 场景①：标题行+空行后直接是未设计数据卡（无 cells/surfaces 先行） -------------

def _title_blank_then(card: str) -> list[str]:
    """构造「标题行 + 空行 + 数据卡」的最小 INP 行序列（无任何已识别数据卡先行）。"""
    return ["test title", "", card]


def _assert_led_to_data(lines: list[str], card: str):
    title, cells, surfs, data = split_sections(lines)
    assert card in data, (
        f"数据卡 {card.split()[0]!r} 在节首被误分："
        f"栅元段={cells!r}，曲面段={surfs!r}，data_lines={data!r}。"
        f"未进 data_lines → 兜底网失效。"
    )
    assert card not in cells, f"{card.split()[0]!r} 不应进栅元段（现被误分到 {cells!r}）"
    assert card not in surfs, f"{card.split()[0]!r} 不应进曲面段（现被误分到 {surfs!r}）"


def test_sections_route_elpt_at_leading_to_data_lines():
    """ELPT:N 在节首 → data_lines（现被误分栅元段）。"""
    _assert_led_to_data(_title_blank_then("ELPT:N 100 14"), "ELPT:N 100 14")


def test_sections_route_fmesh4_at_leading_to_data_lines():
    """FMESH4（带编号）在节首 → data_lines（DATA_KEYWORDS 只有裸 FMESH，FMESH4 漏）。"""
    _assert_led_to_data(
        _title_blank_then("FMESH4:N GEOM=XYZ ORIGIN=0 0 0 IMESH=10 10 10"),
        "FMESH4:N GEOM=XYZ ORIGIN=0 0 0 IMESH=10 10 10",
    )


def test_sections_route_cn_cosine_bins_at_leading_to_data_lines():
    """Cn（余弦分箱）在节首 → data_lines（现被误分栅元段）。"""
    _assert_led_to_data(_title_blank_then("C1 0.5 0.25 0.25"), "C1 0.5 0.25 0.25")


def test_sections_route_dxt_at_leading_to_data_lines():
    """DXT 在节首 → data_lines（现被误分栅元段）。"""
    _assert_led_to_data(_title_blank_then("DXT 2 2 2 2 2"), "DXT 2 2 2 2 2")


# 词条审计 D-03 缺口全清单（对齐 docs/card-lexicon-diff.md 建议修法正则族）
_AUX_CARDS_AT_LEADING = [
    "DE4 0.1 0.5 1.0",       # ^DE\d+$
    "DF4 1.0 2.0 3.0",       # ^DF\d+$
    "FS4 1 2 3",             # ^FS\d+$
    "SD4 1 2 3",             # ^SD\d+$
    "CF4 1 2",               # ^CF\d+$
    "SF4 1 2",               # ^SF\d+$
    "EM4 1 2",               # ^EM\d+$
    "TM4 1 2",               # ^TM\d+$
    "CM4 1 2",               # ^CM\d+$
    "TF4 1 2",               # ^TF\d+$
    "DD4 1 2",               # ^DD\d+$
    "SB1 1 2 3",             # ^SB\d+$
    "DS1 S 1",               # ^DS\d+$
    "SC1 source comment",    # ^SC\d+$
    "NOTRN",                 # ^NOTRN$
    "TALNP",                 # ^TALNP$
    "MPLOT",                 # ^MPLOT$
    "RAND GEN=2 SEED=12345", # ^RAND$
    "FILES 22 DUM1 8",       # ^FILES$
    "IDUM 5 10",             # ^IDUM$
    "RDUM 1.0 2.0",          # ^RDUM$
]


@pytest.mark.parametrize(
    "card",
    _AUX_CARDS_AT_LEADING,
    ids=[c.split()[0].split(":")[0] for c in _AUX_CARDS_AT_LEADING],
)
def test_sections_aux_card_at_leading_to_data_lines(card: str):
    """D-03 缺口清单各词条在节首 → data_lines（现被误分栅元段）。"""
    _assert_led_to_data(_title_blank_then(card), card)


# ---- 场景②（pm 补充）：紧凑 INP，首数据卡即 *F4/+F4/F5Z:P -----------------------

def _compact_inp_with(card: str) -> list[str]:
    """紧凑 INP：无空行分隔节、无 MODE/NPS 等数据关键词先行，cells→surface→首数据卡。"""
    return ["test title", "1 0 -1", "1 pz -1e9", card]


def _assert_led_to_data_compact(card: str):
    _assert_led_to_data(_compact_inp_with(card), card)


def test_sections_route_prefix_f4_compact_inp_to_data_lines():
    """紧凑 INP 首数据卡 *F4:N → data_lines（现被误分曲面段）。"""
    _assert_led_to_data_compact("*F4:N 1 2 3")


def test_sections_route_plus_f4_compact_inp_to_data_lines():
    """紧凑 INP 首数据卡 +F4:N → data_lines（现被误分曲面段）。"""
    _assert_led_to_data_compact("+F4:N 1 2 3")


def test_sections_route_f5z_ring_compact_inp_to_data_lines():
    """紧凑 INP 首数据卡 F5Z:P（环探测器）→ data_lines（现被误分曲面段）。"""
    _assert_led_to_data_compact("F5Z:P 0 0 0 10")


# ---- 场景② 解析链路：*F4 紧凑 INP 应进 tally_defs（而非被 parse_surfaces 丢弃） ----

def test_prefix_f4_compact_inp_parsed_into_tally_defs():
    """紧凑 INP 下 *F4:N 若进 data_lines → 解析后 tally_defs 含 number=4；
    当前被误分曲面段（parse_surfaces verbatim 保留、非 tally）→ tally_defs 为空。

    注意：不做 round-trip 文本断言——*F4 误分曲面段后虽以曲面原文幸存，
    但已非 tally 结构（伪绿），正确验收口径是 tally_defs 结构化归属。
    """
    deck, _warnings = parse_inp_text("test title\n1 0 -1\n1 pz -1e9\n*F4:N 1 2 3\n")
    assert deck.tally is not None, "tally 设置为空，*F4 未解析"
    numbers = [t.number for t in deck.tally.tallies]
    assert 4 in numbers, f"*F4:N 未进 tally_defs（当前 numbers={numbers!r}，被误分曲面段丢失）"
