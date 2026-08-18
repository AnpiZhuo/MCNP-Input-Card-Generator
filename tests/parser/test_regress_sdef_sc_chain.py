"""回归测试：SDEF 分布收集链被 SCn 源注释卡打断（inp02.i 实卡，P0 解析不全）。

根因：
  core.py parse_data_cards SDEF 分支收集后继 SI/SP/SB/DS 的 while 循环，
  遇 SCn（源注释卡，源分布卡说明.md §三 已收录为分布家族成员）即 break →
  后续 SI2/SP2/SB2/SI3/SP3/SI4/SP4 全部落入 other_cards，sdef_distributions 只剩 id=1。

触发场景（inp02.i，MCNP6 Testing/REGRESSION/Inputs）：
  SDEF  CEL D4 X D1 Y D2 Z D3 ERG=1
  SI1 -5 5 / SP1 0 1
  SC2 注释行 ← 断链点
  SI2 A -5 5 / SP2 1 1 / SB2 1 2
  SI3 -5 5 / SP3 0 1
  SI4 L 1 / SP4 V

期望修复后行为：
  SCn 并入分布收集链并结构化进条目 "sc" 字段；
  SI/SP/SB/DS/SC 全部结构化，不再出现在 other_cards；
  生成器回放 SC{idx} 注释（round-trip 内容保真）。
"""
import json
import re

from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from tests.conftest import load_sample


SRC_BLOCK = (
    "SDEF  CEL D4  X D1  Y D2  Z D3  ERG=1\n"
    "SI1  -5 5\n"
    "SP1  0 1\n"
    "SC2  position is biased toward the dxtran and the ring detector.\n"
    "SI2  A -5 5\n"
    "SP2  1 1\n"
    "SB2  1 2\n"
    "SI3  -5 5\n"
    "SP3  0 1\n"
    "SI4  L 1\n"
    "SP4  V\n"
)


def _shell_wrap(text: str) -> str:
    return f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"


def _dist_heads_not_in_other(deck) -> list[str]:
    """other_cards 里残留的分布卡行首（SI/SP/SB/DS/SC 家族），应为空。"""
    bad = []
    for line in deck.adv.other_cards.splitlines():
        head = line.strip().split()[0].upper() if line.strip().split() else ""
        if re.match(r'^(SI|SP|SB|DS|SC)\d+$', head):
            bad.append(line)
    return bad


# ── 最小复现（SRC_BLOCK）──────────────────────────────────

def test_scn_does_not_break_sdef_distribution_chain():
    deck, _w = parse_inp_text(_shell_wrap(SRC_BLOCK))
    dist = json.loads(deck.adv.sdef_distributions)
    ids = [e["id"] for e in dist]
    assert ids == [1, 2, 3, 4], f"分布条目不完整: {ids}"
    d2 = next(e for e in dist if e["id"] == 2)
    assert d2["si"] == {"type": "A", "values": ["-5", "5"]}
    assert d2["sb"] == {"type": "D", "values": ["1", "2"]}
    assert d2["sc"] == "position is biased toward the dxtran and the ring detector."
    d4 = next(e for e in dist if e["id"] == 4)
    assert d4["sp"] == {"type": "V", "values": [], "fnCode": "", "fnParams": []}
    assert not _dist_heads_not_in_other(deck), f"分布卡仍落 other_cards: {_dist_heads_not_in_other(deck)}"


def test_scn_chain_round_trip_keeps_distribution_cards():
    deck, _w = parse_inp_text(_shell_wrap(SRC_BLOCK))
    out = generate_inp_from_deck(deck)
    for token in ("SI2  A  -5  5", "SB2  D  1  2", "SP4  V",
                  "SI4  L  1", "SC2  position is biased"):
        assert token in out, f"round-trip 输出缺 {token!r}:\n{out}"


# ── 全文件实卡回归（inp02.i fixture）───────────────────────

def test_inp02_full_roundtrip_distributions_structured():
    text = load_sample("inp02.i")
    deck, _w = parse_inp_text(text)
    dist = json.loads(deck.adv.sdef_distributions)
    ids = [e["id"] for e in dist]
    assert ids == [1, 2, 3, 4], f"inp02.i 分布条目: {ids}"
    assert not _dist_heads_not_in_other(deck), \
        f"inp02.i 分布卡仍落 other_cards: {_dist_heads_not_in_other(deck)}"
    out = generate_inp_from_deck(deck)
    for token in ("SI2  A  -5  5", "SB2  D  1  2", "SC2  position is biased",
                  "SI4  L  1", "SP4  V"):
        assert token in out, f"inp02.i round-trip 缺 {token!r}"
