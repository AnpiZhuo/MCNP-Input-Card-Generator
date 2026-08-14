"""回归测试：FMESH/TMESH 网格计数卡结构化导入往返（网格计数可视化 v1.7.0，契约 meshtal-visualization.md §6）。

现状（2026-08-14，功能未实现 → 红基线）：
  - core.py parse_data_cards 入口门（:941 if/elif 链）无 FMESH/TMESH 结构化分支 →
    FMESHn/TMESHn 落 other_cards（raw_line 兜底，round-trip 不丢但非结构化）；
  - sections.py DATA_PATTERNS（:180）只认 `^FMESH`，TMESH 未认 → 节首直出（紧凑 INP
    节间无空行）会误分曲面/栅元段（D-03 同类缺陷）；
  - inp_generator.py _generate_tallies 只发 Fn/FMn，无 fmesh_defs 回放；
  - app/models.py 无 FmeshDefinition / TallySettings.fmesh_defs。

红基线 pin（按契约 §9.4 / §6 五步走）：
  1. FMESH4:N 结构化吸收 → fmesh_defs（不再 other_cards 裸文本）——RED
  2. TMESHn + RMESHn 子卡结构化吸收（sections 补 ^TMESH）——RED
  3. 结构化 → 生成回放 → 再导入 → 字段保留（IMESH/IINTS/ORIGIN 全链）——RED
  4. sections.py DATA_PATTERNS 缺 ^TMESH（紧凑 INP 误分曲面段）——RED
  5. R1 不动点（对照：当前经 other_cards 兜底已绿，施工后不得回归）——GREEN 对照
  6. 无 FMESH 卡 deck 生成不回归（对照）——GREEN 对照

纪律：本文件只 import app 纯模块（不 import gui.backend.api_server / FreeCAD）。
"""
from pathlib import Path

from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.generator.parsers.core import parse_data_cards
from app.generator.parsers.sections import split_sections

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

FMESH4_DATA_LINES = [
    "MODE N",
    "FMESH4:N GEOM=XYZ ORIGIN=-100 -100 -150",
    "     IMESH=100 IINTS=10",
    "     JMESH=100 JINTS=10",
    "     KMESH=50 KINTS=100",
    "NPS 100000",
]

TMESH_DATA_LINES = [
    "MODE N",
    "TMESH5",
    "RMESH5:N GEOM=XYZ ORIGIN=-50 -50 -50",
    "     IMESH=50 IINTS=5",
    "     JMESH=50 JINTS=5",
    "     KMESH=50 KINTS=5",
    "NPS 100000",
]


def _load_minimal_fmesh_inp() -> str:
    return (FIXTURES / "minimal_fmesh.inp").read_text(encoding="utf-8")


# ── 1. FMESH 结构化吸收（不再 other_cards 裸文本）────────────────
def test_fmesh4_absorbed_structured_not_other_cards():
    """FMESH4:N → parse_data_cards 产出 fmesh_defs 结构化字段，不再落 other_cards。

    契约 §5.1 FmeshDefinition（kind/number/particle/geom/origin/imesh/iints/...）。
    当前入口门无 FMESH 分支 → 无 fmesh_defs key → RED。
    """
    result = parse_data_cards(FMESH4_DATA_LINES)
    assert "fmesh_defs" in result, "入口门未产出 fmesh_defs（FMESH 仍走 other_cards 兜底）"
    assert len(result["fmesh_defs"]) == 1, "应恰好吸收 1 张 FMESH 卡"
    fd = result["fmesh_defs"][0]
    assert fd.kind == "FMESH" and fd.number == 4
    assert fd.particle.upper() == "N"
    assert fd.geom.lower() == "xyz"
    assert fd.origin == "-100 -100 -150"
    assert fd.imesh == "100" and fd.iints == "10"
    assert fd.jmesh == "100" and fd.jints == "10"
    assert fd.kmesh == "50" and fd.kints == "100"
    # FMESH 不再落 other_cards（裸文本吸收为结构化）
    assert not any(str(c).startswith("FMESH4") for c in result["other_cards"]), (
        "FMESH4 仍残留在 other_cards（未结构化吸收）"
    )


# ── 2. TMESH 结构化吸收（sections 补 ^TMESH）─────────────────────
def test_tmesh_absorbed_structured_not_other_cards():
    """TMESH5 + RMESH5 子卡 → fmesh_defs 结构化。

    TMESH 未在 DATA_PATTERNS/_KNOWN_OTHER_CARDS（core.py:890 表无 TMESH）→ RED。
    """
    result = parse_data_cards(TMESH_DATA_LINES)
    assert "fmesh_defs" in result, "入口门未产出 fmesh_defs（TMESH 仍走 other_cards 兜底）"
    assert len(result["fmesh_defs"]) == 1, "TMESH 应吸收为 1 个结构化定义"
    fd = result["fmesh_defs"][0]
    assert fd.kind == "TMESH" and fd.number == 5
    assert fd.origin == "-50 -50 -50"
    assert fd.imesh == "50" and fd.iints == "5"
    assert fd.jmesh == "50" and fd.jints == "5"
    assert fd.kmesh == "50" and fd.kints == "5"
    assert not any(str(c).startswith("TMESH") or str(c).startswith("RMESH")
                   for c in result["other_cards"]), "TMESH/RMESH 仍残留在 other_cards"


# ── 3. 结构化 → 生成回放 → 再导入 → 字段保留 ─────────────────────
def test_fmesh_generate_replay_reimport_fields_preserved():
    """完整 INP：FMESH 结构化 → 生成回放含 FMESH 卡 → 再导入 fmesh_defs 字段保留。

    契约 §6 步 4（inp_generator._generate_tallies 追加 fmesh 回放）+ §9.4
    「导入→表单→回放→再导入字段保留」。当前 fmesh_defs 不存在 → RED。
    """
    deck1, _w = parse_inp_text(_load_minimal_fmesh_inp())
    fmesh_defs = getattr(deck1.tally, "fmesh_defs", None)
    assert fmesh_defs, "parse 未在 tally 上带出 fmesh_defs（结构化未实现）"

    g1 = generate_inp_from_deck(deck1)
    assert "FMESH4" in g1, "生成器回放未包含 FMESH 卡"
    assert "TMESH5" in g1, "生成器回放未包含 TMESH 卡"

    deck2, _w2 = parse_inp_text(g1)
    fmesh_defs2 = getattr(deck2.tally, "fmesh_defs", None)
    assert fmesh_defs2, "再导入未带出 fmesh_defs"
    by_number = {fd.number: fd for fd in fmesh_defs2}
    assert 4 in by_number, "再导入丢失 FMESH4"
    fd4 = by_number[4]
    assert fd4.kind == "FMESH" and fd4.origin == "-100 -100 -150"
    assert fd4.imesh == "100" and fd4.iints == "10"
    assert fd4.jmesh == "100" and fd4.jints == "10"
    assert fd4.kmesh == "50" and fd4.kints == "100"
    assert 5 in by_number, "再导入丢失 TMESH5"


# ── 4. sections.py DATA_PATTERNS 缺 ^TMESH（紧凑 INP 误分曲面段）──
def test_tmesh_section_boundary_not_misrouted():
    """紧凑 INP（节间无空行）下 TMESH 卡不得误分曲面/栅元段。

    契约 §1.1：sections.py DATA_PATTERNS（:180）须补 `^TMESH`，否则 TMESH 节首
    直出误分曲面段 → parse_surfaces 丢弃（D-03 同类缺陷）。当前缺 → RED。
    """
    compact = [
        "test deck",
        "1 0 -1 imp:n=1",
        "1 px 0",
        "TMESH5",
        "RMESH5:N GEOM=XYZ ORIGIN=0 0 0",
        "MODE N",
        "NPS 1000",
    ]
    _title, cells, surfs, data = split_sections(compact)
    assert any(l.strip().startswith("TMESH") or l.strip().startswith("RMESH")
               for l in data), "TMESH 卡未进 data_lines（DATA_PATTERNS 缺 ^TMESH）"
    assert not any(l.strip().startswith("TMESH") or l.strip().startswith("RMESH")
                   for l in surfs), "TMESH 卡被误分曲面段（数据丢失）"
    assert not any(l.strip().startswith("TMESH") or l.strip().startswith("RMESH")
                   for l in cells), "TMESH 卡被误分栅元段"


# ── 5. R1 不动点（对照）──────────────────────────────────────────
def test_r1_fixed_point_fmesh_roundtrip():
    """R1 不动点：含 FMESH/TMESH 卡 deck，generate(parse(generate(d)))==generate(d)。

    当前经 other_cards raw 兜底已成立（对照 GREEN）；施工后结构化回放必须保持不回归。
    """
    deck, _w = parse_inp_text(_load_minimal_fmesh_inp())
    g1 = generate_inp_from_deck(deck)
    deck2, _w2 = parse_inp_text(g1)
    g2 = generate_inp_from_deck(deck2)
    assert g1 == g2, (
        "R1 不动点不成立：含 FMESH/TMESH 卡的 deck 第二代输出漂移。\n"
        "（FMESH 结构化回放施工不得破坏 other_cards raw 兜底的字节稳定）"
    )


# ── 6. 无 FMESH 卡 deck 不回归（对照）────────────────────────────
def test_no_fmesh_deck_not_regressed():
    """对照：无 FMESH/TMESH 卡 deck 生成不回归（fmesh 链路不得影响普通 deck）。"""
    deck, _w = parse_inp_text("t\n1 0 -1 imp:n=1\n\n1 px 0\n\nmode n\nnps 1000\n")
    assert getattr(deck.tally, "fmesh_defs", None) in (None, [])
    g1 = generate_inp_from_deck(deck)
    assert "FMESH" not in g1 and "TMESH" not in g1
