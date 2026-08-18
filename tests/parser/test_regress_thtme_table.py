"""回归测试：THTME 卡 `#` 表头 + 数值表行被材料吸收（inp02.i 实卡，解析不全/往返损坏）。

根因：
  core.py parse_data_cards 无 THTME 分支 →
  ① `# tmp1 ...` 表头行被 `line.startswith("#")` 分支塞进 current_mat（末个材料）rows；
  ② 数值表行（首列=材料号，如 `1 1e-8 2e-8 ...`）被"裸核素行"分支当 ZAID/份额
     吸收进 current_mat rows；
  ③ 结果：round-trip 后 THTME 卡与表分离（表错挂进 M3 材料块），MCNP 再读语义损坏。

期望修复后行为：
  THTME 卡 + 其 `#` 表头 + 数值表行按原文整体保留进 other_cards（无 UI，原样保真）；
  材料 rows 不吸收任何 THTME 表内容。
"""
import re

from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from tests.conftest import load_sample


THTME_BLOCK = (
    "M1  1001.06c 1\n"
    "THTME -10 0 .5 1 2\n"
    "#    tmp1  tmp2  tmp3  tmp4  tmp5\n"
    "   1  1e-8  2e-8  3e-8  4e-8  5e-8\n"
    "   2  2e-8  3e-8  5e-8  4e-8  3e-8\n"
    "IMP:N 1 1\n"
)


def _shell_wrap(text: str) -> str:
    return f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"


def test_thtme_table_not_absorbed_into_material():
    deck, _w = parse_inp_text(_shell_wrap(THTME_BLOCK))
    m1 = next(m for m in deck.materials if m.number == 1)
    assert all(r.kind == "nuclide" for r in m1.rows), \
        f"M1 rows 混入非核素行: {[(r.kind, getattr(r, 'text', None)) for r in m1.rows]}"
    oc = deck.adv.other_cards
    assert "thtme -10 0 .5 1 2" in oc.lower()
    assert "tmp1" in oc and "tmp5" in oc, "THTME # 表头行丢失"
    assert "1e-8" in oc and "3e-8" in oc, "THTME 数值表行丢失"
    # 表行与 THTME 卡保持相邻（同块连续保留）
    lines = [l for l in oc.splitlines() if l.strip()]
    ti = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("thtme"))
    after = "\n".join(lines[ti:ti + 4])
    assert "tmp1" in after and "1e-8" in after, f"THTME 块被拆散: {after!r}"


def test_thtme_round_trip_keeps_table():
    deck, _w = parse_inp_text(_shell_wrap(THTME_BLOCK))
    out = generate_inp_from_deck(deck).lower()
    for token in ("thtme -10 0 .5 1 2", "#    tmp1  tmp2  tmp3  tmp4  tmp5",
                  "1  1e-8  2e-8  3e-8  4e-8  5e-8", "2  2e-8  3e-8  5e-8  4e-8  3e-8"):
        assert token in out, f"round-trip 输出缺 {token!r}:\n{out}"
    # 二次解析不变量：表内容不得回到材料 rows（误挂材料即损坏）
    deck2, _w2 = parse_inp_text(out)
    m1 = next(m for m in deck2.materials if m.number == 1)
    assert all(r.kind == "nuclide" for r in m1.rows), \
        f"round-trip 后 M1 rows 被污染: {[(r.kind, getattr(r, 'text', None)) for r in m1.rows]}"
    assert "thtme -10 0 .5 1 2" in deck2.adv.other_cards.lower(), "round-trip 后 THTME 卡丢失"


def test_inp02_thtme_table_stays_with_card():
    text = load_sample("inp02.i")
    deck, _w = parse_inp_text(text)
    # M3 只应有两条核素行
    m3 = next(m for m in deck.materials if m.number == 3)
    assert [(r.kind, r.zaid) for r in m3.rows] == \
        [("nuclide", "5010.0"), ("nuclide", "5011.40c")], \
        f"M3 rows 被 THTME 表污染: {[(r.kind, r.zaid) for r in m3.rows]}"
    oc = deck.adv.other_cards
    assert "tmp1" in oc and "1e-8" in oc, "inp02.i THTME 表丢失"
    out = generate_inp_from_deck(deck)
    # THTME 卡与 # 表头在输出中相邻
    assert re.search(r"thtme -10 0 \.5 1 2\n#\s+tmp1", out, re.I), \
        "inp02.i round-trip THTME 卡与表分离"
