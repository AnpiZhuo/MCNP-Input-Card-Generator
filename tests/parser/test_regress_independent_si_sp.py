"""回归测试：独立 SIn/SPn 卡静默丢弃（词条审计 D-01，P0 数据丢失）。

根因（当前工作树未修，2026-08-13）：
  app/generator/parsers/core.py:1101-1102 parse_data_cards 分支
  `elif first.startswith("SI") or first.startswith("SP"): i += 1`
  → 整行静默丢弃，不进 other_cards、不进任何字段。
  仅在「紧跟 SDEF」时被 SDEF 分支（core.py:1003-1028）收集为结构化分布。

触发场景（**2026-09-10 更正：已清偿 → 本文件为验收基准，应全绿**；"当前红"为初版遗留）：
  ① SSR 面源分布：`SSR OLD 3 2 NEW 6 7 12 13 TR D5` 后跟 `SI5 L 4 5`/`SP5 .4 .6`
    （参考 app/docs/源分布卡说明.md 示例 1）；
  ② SDEF 与 SI 之间隔 C 注释行：SDEF 收集循环遇 `C` 即 break → 后续 SI/SP 全丢。

期望修复后行为（验收基准）：
  独立 SI/SP 至少保底进 other_cards 不丢（round-trip 保真）；
  增强场景（SSR 后跟 SI/SP）应并入结构化分布。

对照（不回归）：
  SDEF 紧跟 SI/SP（结构化收集场景）仍按既有行为工作。
"""
import json

from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.generator.parsers.core import parse_data_cards


# ---- 测试输入 -------------------------------------------------------------

SSR_SI_SP = (
    "SSR OLD 3 2 NEW 6 7 12 13 TR D5\n"
    "SI5 L 4 5\n"
    "SP5 .4 .6"
)

SDEF_COMMENT_SI_SP = (
    "SDEF POS=0 0 0\n"
    "C 源分布注释行\n"
    "SI5 L 4 5\n"
    "SP5 .4 .6"
)

SDEF_DIRECT_SI_SP = (
    "SDEF POS=0 0 0\n"
    "SI5 L 4 5\n"
    "SP5 .4 .6"
)


# ---- 辅助 -----------------------------------------------------------------

def _shell_wrap_data(text: str) -> str:
    """数据卡文本放入数据段（cells/surfaces 之后），供 parse_inp_text 全链路 round-trip。"""
    return f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"


def _sisp_cards_text(result: dict) -> str:
    """拼出解析结果中所有承载 SI/SP 的位置（other_cards 原样 + 结构化分布 JSON），
    用于断言独立 SI/SP 是否保底保留。"""
    parts = list(result.get("other_cards", []))
    # TD-23（t5）：旧 sdef_raw_text 已退役（解析侧只写 sdef_distributions），不再参与拼装
    for key in ("sdef_distributions",):
        raw = result.get(key) or ""
        if raw:
            parts.append(raw)
    return "\n".join(parts)


# ---- D-01 场景①：SSR 面源分布后跟 SI5/SP5 ----------------------------------

def test_ssr_followed_by_si_sp_not_dropped():
    """D-01 场景①：SSR 后跟 SI5/SP5，解析后 SI5/SP5 不得丢失
    （other_cards 保底 或 并入结构化分布，二者任一即可）。"""
    result = parse_data_cards(SSR_SI_SP.splitlines())
    # SSR 仍被识别为面源（源本身解析不受影响）
    assert result["source_mode"] == "surface"
    preserved = _sisp_cards_text(result)
    assert "SI5" in preserved, f"SI5 被静默丢弃。解析结果承载文本: {preserved!r}"
    assert "SP5" in preserved, f"SP5 被静默丢弃。解析结果承载文本: {preserved!r}"


def test_ssr_si_sp_round_trip_keeps_cards():
    """D-01 场景① round-trip：SSR + SI5/SP5 经 解析→生成 回放后，输出仍含 SI5/SP5。"""
    deck, _warnings = parse_inp_text(_shell_wrap_data(SSR_SI_SP))
    out = generate_inp_from_deck(deck)
    assert "SI5" in out, "round-trip 输出丢失 SI5（独立 SI 卡被静默丢弃）"
    assert "SP5" in out, "round-trip 输出丢失 SP5（独立 SP 卡被静默丢弃）"


# ---- D-01 场景②：SDEF 与 SI 之间隔 C 注释行 ---------------------------------

def test_sdef_comment_separated_si_sp_not_dropped():
    """D-01 场景②：SDEF 收集循环遇 C 即 break，后续独立 SI5/SP5 不得丢失。"""
    result = parse_data_cards(SDEF_COMMENT_SI_SP.splitlines())
    preserved = _sisp_cards_text(result)
    assert "SI5" in preserved, f"SI5 被静默丢弃。解析结果承载文本: {preserved!r}"
    assert "SP5" in preserved, f"SP5 被静默丢弃。解析结果承载文本: {preserved!r}"


def test_sdef_comment_separated_si_sp_round_trip_keeps_cards():
    """D-01 场景② round-trip：SDEF 与 SI 隔 C 注释，回放后输出仍含 SI5/SP5。"""
    deck, _warnings = parse_inp_text(_shell_wrap_data(SDEF_COMMENT_SI_SP))
    out = generate_inp_from_deck(deck)
    assert "SI5" in out, "round-trip 输出丢失 SI5（独立 SI 卡被静默丢弃）"
    assert "SP5" in out, "round-trip 输出丢失 SP5（独立 SP 卡被静默丢弃）"


# ---- 对照：SDEF 紧跟 SI/SP（结构化收集场景）不回归 ---------------------------

def test_control_sdef_immediately_followed_si_sp_structured():
    """对照：SDEF 紧跟 SI5/SP5 → 结构化分布收集仍工作（source_mode=distribution，不进 other_cards）。"""
    result = parse_data_cards(SDEF_DIRECT_SI_SP.splitlines())
    assert result["source_mode"] == "distribution"
    # 结构化 JSON 仍精确收集 id=5 的 SI/SP 条目
    dist = json.loads(result["sdef_distributions"])
    assert len(dist) == 1 and dist[0]["id"] == 5
    assert dist[0]["si"] == {"type": "L", "values": ["4", "5"]}
    assert dist[0]["sp"]["values"] == [".4", ".6"]


def test_control_sdef_direct_round_trip_keeps_si_sp():
    """对照 round-trip：SDEF 紧跟 SI5/SP5，回放后输出仍含 SI5/SP5（不回归）。"""
    deck, _warnings = parse_inp_text(_shell_wrap_data(SDEF_DIRECT_SI_SP))
    out = generate_inp_from_deck(deck)
    assert "SI5" in out
    assert "SP5" in out
