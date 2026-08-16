"""PTRAC 粒子径迹输出卡结构化导入/生成往返（契约 ptrac-visualization.md v2 §4.5）。

口径（与 D-10 回归 test_regress_lexicon_d10_other_cards_comment.py 并存）：
  - 含结构化关键字（FILE=/WRITE=/MAX=/TYPE=/NPS=/CELL=/SURFACE=/VALUE=/EVENT=）→ tally.ptrac；
  - 裸卡 / 行内 `$ 注释` / 未识别关键字（CONIC=/TALLY=/FILTER=/BUFFER=/MEPH=）→ other_cards 保留原文。

纪律：本文件只 import app 纯模块（不 import gui.backend.api_server / FreeCAD）。
"""
from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.generator.parsers.core import parse_data_cards


# ── 1. 结构化 PTRAC 吸收（不再 other_cards 裸文本）────────────────
def test_ptrac_structured_absorbed_not_other_cards():
    """PTRAC FILE=… 结构化 → tally.ptrac 字段，不再落 other_cards。"""
    result = parse_data_cards([
        "MODE N",
        "PTRAC FILE=ASC WRITE=ALL MAX=-1 TYPE=N P NPS=1 50 CELL=3 4",
        "NPS 1000",
    ])
    assert "ptrac" in result, "入口门未产出 ptrac（PTRAC 仍走 other_cards 兜底）"
    p = result["ptrac"]
    assert p.enabled is True
    assert p.file == "ASC" and p.write == "ALL" and p.max == "-1"
    assert p.types == ["N", "P"]
    assert p.nps == "1 50"
    assert p.cell == "3 4"
    assert not any(str(c).startswith("PTRAC") for c in result["other_cards"]), (
        "结构化 PTRAC 仍残留在 other_cards"
    )


# ── 2. 裸卡 / 行内 $ 注释仍 other_cards（D-10 不弱化）─────────────
def test_ptrac_bare_inline_comment_stays_other_cards():
    """裸 PTRAC 卡 + 行内 $ 注释 → other_cards 保留原文，不结构化。"""
    result = parse_data_cards(["PTRAC $ write particles"])
    joined = "\n".join(result["other_cards"])
    assert "write particles" in joined and "$" in joined, (
        "PTRAC 行内 $ 注释未保留在 other_cards（D-10 回归）"
    )
    assert "ptrac" not in result, "裸 PTRAC 卡不应结构化为 tally.ptrac"


def test_ptrac_unrecognized_keyword_stays_other_cards():
    """含未识别关键字（CONIC=）的 PTRAC → other_cards 原文（round-trip 不丢）。"""
    result = parse_data_cards(["PTRAC FILE=ASC CONIC=1"])
    joined = "\n".join(result["other_cards"])
    assert "CONIC=1" in joined, "未识别关键字 PTRAC 卡未回落 other_cards"
    assert "ptrac" not in result


# ── 3. 结构化 → 生成回放 → 再导入 → 字段保留 + R1 不动点 ──────────
def _shell_wrap_data(text: str) -> str:
    return f"t\n1 0 -1 imp:n=1\n\n1 px 0\n\n{text}\n"


def test_ptrac_generate_replay_reimport_roundtrip():
    """含结构化 PTRAC 卡 deck：生成回放含 PTRAC → 再导入字段保留 → R1 不动点。"""
    src = "PTRAC FILE=ASC WRITE=ALL MAX=-1 TYPE=N P NPS=1 50 CELL=3 4 SURFACE=7 VALUE=1.0 EVENT=col"
    deck1, _w = parse_inp_text(_shell_wrap_data(src))
    p1 = deck1.tally.ptrac
    assert p1 is not None, "parse 未在 tally 上带出 ptrac"
    assert p1.enabled and p1.file == "ASC" and p1.write == "ALL"
    assert p1.types == ["N", "P"] and p1.nps == "1 50" and p1.cell == "3 4"
    assert p1.surface == "7" and p1.value == "1.0" and p1.event == "col"

    g1 = generate_inp_from_deck(deck1)
    # 生成回放含 PTRAC 卡（超 80 列会被 _wrap_long_lines 折行，故按关键字断言）
    assert "PTRAC" in g1 and "FILE=ASC" in g1 and "WRITE=ALL" in g1 and "MAX=-1" in g1
    assert "TYPE=N P" in g1 and "NPS=1 50" in g1 and "CELL=3 4" in g1
    assert "SURFACE=7" in g1 and "VALUE=1.0" in g1 and "EVENT=col" in g1, (
        f"生成器回放未含完整 PTRAC 卡。输出:\n{g1}"
    )

    deck2, _w2 = parse_inp_text(g1)
    p2 = deck2.tally.ptrac
    assert p2 is not None, "再导入未带出 ptrac"
    for attr in ("enabled", "file", "write", "max", "types", "nps", "cell",
                 "surface", "value", "event"):
        assert getattr(p1, attr) == getattr(p2, attr), f"字段 {attr} 再导入丢失"

    g2 = generate_inp_from_deck(deck2)
    assert g1 == g2, "R1 不动点不成立（PTRAC 结构化回放漂移）"


# ── 4. 无 PTRAC deck 不回归（对照）────────────────────────────────
def test_no_ptrac_deck_not_regressed():
    """对照：无 PTRAC 卡 deck 生成不回归（ptrac 链路不得影响普通 deck）。"""
    deck, _w = parse_inp_text("t\n1 0 -1 imp:n=1\n\n1 px 0\n\nmode n\nnps 1000\n")
    assert deck.tally.ptrac is None
    g1 = generate_inp_from_deck(deck)
    assert "PTRAC" not in g1


# ── 5. asdict 序列化形状（前端 deck.tally.ptrac JSON key 对齐）────
def test_ptrac_asdict_frontend_shape():
    """TallySettings.ptrac → dataclasses.asdict 产出前端 {enabled,file,write,max,types[],…} 形状。"""
    import dataclasses
    from app.models import PTRACSettings, TallySettings
    tally = TallySettings(ptrac=PTRACSettings(
        enabled=True, file="ASC", write="ALL", max="-1",
        types=["N", "P"], nps="1 50", cell="3 4",
    ))
    d = dataclasses.asdict(tally)
    assert d["ptrac"] == {
        "enabled": True, "file": "ASC", "write": "ALL", "max": "-1",
        "types": ["N", "P"], "nps": "1 50", "cell": "3 4",
        "surface": "", "value": "", "event": "",
    }


# ── 6. emit 格式与前端 ptracToCardText 逐字对齐 ──────────────────
def test_ptrac_generate_matches_frontend_card_format():
    """_generate_ptrac 与 gui/src/ptrac/ptracState.ts `ptracToCardText` 格式对齐：
    FILE/WRITE/MAX 恒发（默认 ASC/ALL/-1，FILE/WRITE 大写）；TYPE 大写多值空格；
    其余只发非空项；enabled=false → 无卡。"""
    from app.generator.inp_generator import _generate_ptrac
    from app.models import PTRACSettings, TallySettings

    # 默认：只发 FILE/WRITE/MAX（无空项）
    assert _generate_ptrac(TallySettings(ptrac=PTRACSettings(enabled=True))) == \
        ["PTRAC FILE=ASC WRITE=ALL MAX=-1"]
    # 小写归一化 + 多值 TYPE + 非空项
    assert _generate_ptrac(TallySettings(ptrac=PTRACSettings(
        enabled=True, file="asc", write="source", max="-1",
        types=["n", "p"], nps="1 50", cell="3", surface="7", value="1.0", event="col",
    ))) == ["PTRAC FILE=ASC WRITE=SOURCE MAX=-1 TYPE=N P NPS=1 50 CELL=3 SURFACE=7 VALUE=1.0 EVENT=col"]
    # 未启用 → 无卡
    assert _generate_ptrac(TallySettings(ptrac=PTRACSettings(enabled=False))) == []
    assert _generate_ptrac(TallySettings(ptrac=None)) == []
