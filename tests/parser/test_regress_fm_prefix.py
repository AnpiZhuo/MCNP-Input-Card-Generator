"""回归测试：计数卡前缀修饰符（*F / +F）导入→导出往返保留（用户反馈 #2，P2）。

复核结论（2026-08-13）：
  app/generator/parsers/core.py:715-719 parse_f_tally 对行首 `^([*+])(.+)` 有 fn_prefix 处理——
  *F 表示乘数/倍增修正（如 *F4 按入射粒子数倍增），+F 表示正电流/正通量；
  TallyDefinition.fn_prefix（app/models.py）承载 "" / "*" / "+"；
  生成器 _generate_tallies（inp_generator.py:646 pre = td.fn_prefix）回放时前缀保留。
  本测试确认 *F4 / +F4（及无前缀 F4）在 导入→导出 不丢。

范围说明（非 #2 回归，词条审计 D-03 既有缺陷）：
  紧凑 INP（节间无空行分隔、且无 MODE/NPS/SDEF 等数据关键词先行）下，
  split_sections（sections.py DATA_PATTERNS）不识别 `^[*+]?F\\d+` → 整个 tally 卡
  （含前缀）误分曲面段被 parse_surfaces 丢弃。该缺陷对无前缀 F5Z:P 同样存在，
  #1/#6 修复未引入（sections.py 仅新增 `^FM\\d+$`），与 #2 前缀保留正交。
  本测试覆盖标准结构（生成器产出/空行分隔）下的前缀往返。
"""
import re

from app.generator.inp_generator import _generate_tallies, generate_inp_from_deck
from app.generator.parsers.core import parse_data_cards, parse_f_tally
from app.models import BasicSettings, CellData, CellRow, DeckData, TallyDefinition, TallySettings
from app.generator.parsers import parse_inp_text


def _make_deck(prefix: str) -> DeckData:
    """构造最小 deck：1 个栅元 + 1 张带前缀的 F4 计数卡。"""
    td = TallyDefinition(type="F4", number=4, particles=["n"], params="1 2", fn_prefix=prefix)
    return DeckData(
        basic=BasicSettings(title="t"),
        cells=[CellRow(kind="cell", text="1 0 -1",
                       cell=CellData(number=1, material="0", density="", surface_expr="-1"))],
        tally=TallySettings(tallies=[td]),
    )


def test_parse_data_cards_detects_fn_prefix():
    """导入（parse_data_cards 数据层）：*F4 / +F4 / F4 的 fn_prefix 分别为 "*" / "+" / ""。"""
    for head, expected in (("*F4:N", "*"), ("+F4:N", "+"), ("F4:N", "")):
        result = parse_data_cards([f"{head} 1 2"])
        assert len(result["tally_defs"]) == 1, f"{head} 未识别为计数卡"
        td = result["tally_defs"][0]
        assert td.type == "F4" and td.number == 4
        assert td.particles == ["n"] and td.params == "1 2"
        assert td.fn_prefix == expected, f"{head}: 期望 fn_prefix={expected!r}, 实得 {td.fn_prefix!r}"


def test_parse_f_tally_returns_handled_for_all_prefix_forms():
    """parse_f_tally 对 *F / +F / 无前缀三种形态均返回 True（已被处理，不进 other_cards）。"""
    for head in ("*F4:N", "+F4:N", "F4:N"):
        tally_defs = []
        handled = parse_f_tally([head, "1", "2"], tally_defs)
        assert handled is True, f"{head} 返回 {handled}（应为 True）"
        assert len(tally_defs) == 1 and tally_defs[0].fn_prefix in ("*", "+", "")


def test_generator_replays_prefix():
    """生成器 _generate_tallies 回放：*F4 / +F4 / F4 前缀保留。"""
    for prefix in ("*", "+", ""):
        td = TallyDefinition(type="F4", number=4, particles=["n"], params="1 2", fn_prefix=prefix)
        lines = _generate_tallies(TallySettings(tallies=[td]))
        card = next(l for l in lines if re.search(r'F4:N', l) and "FM4" not in l)
        assert card.strip().startswith(f"{prefix}F4:N"), \
            f"prefix {prefix!r} 丢失: {card.strip()!r}"


def test_full_inp_round_trip_keeps_prefix():
    """完整 INP 往返 parse→generate→parse：*F4 / +F4 / F4 前缀不丢。"""
    for prefix in ("*", "+", ""):
        deck = _make_deck(prefix)
        out = generate_inp_from_deck(deck)
        # 生成器输出含带正确前缀的 F 卡（前缀回放）
        assert f"{prefix}F4:N  1 2" in out, \
            f"prefix {prefix!r}: 生成输出缺 F 卡 {prefix}F4:N 1 2"
        # 重新解析：fn_prefix 仍保留
        deck2, _warnings = parse_inp_text(out)
        assert len(deck2.tally.tallies) == 1
        td = deck2.tally.tallies[0]
        assert (td.type, td.number, td.params, td.fn_prefix) == ("F4", 4, "1 2", prefix), \
            f"prefix {prefix!r}: 往返后 (type,number,params,fn_prefix) 实得 " \
            f"{td.type, td.number, td.params, td.fn_prefix!r}"
