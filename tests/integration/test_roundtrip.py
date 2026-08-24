"""
往返不变量测试（P0-3，M1.4 门禁核心）
====================================
- R1 不动点（正确性红线）：g2 = generate(parse(generate(d)))，断言 g2 == generate(d) 字节相等。
  （从第二代起稳定；不要求 parse(手写 INP) 原样 == INP）
- R2 语义：parse(generate(d)) 后逐字段对比（容忍已知头泄漏字段，精确定位污染）。
- R3 分段：surfaces / other_cards / TR 卡无内容丢失（允许顺序后移）。
- R4 kitchen-sink deck：每个 dataclass 字段填非平凡值跑 R1+R2。

【当前状态】R1 在现有代码上为 RED —— 根因是生成器 C 注释头泄漏（见本文件底部
KNOWN_LEAK_FIELDS）。这是 M1.4 全绿前必须由引擎侧修复的阻塞项。
"""
from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.models import DeckData

from tests.conftest import load_sample


# ── 已知头泄漏字段（生成器 C 注释头 → 解析器误吸收）────────
# 修复 R1 时应重点核对这些字段；当前 R2 对它们做显式容忍并打印差异。
KNOWN_LEAK_FIELDS = {
    "cell.comment",      # "C  Cell Cards: N cells defined" → 关联到下一个栅元的 $ 注释
    "surfaces",          # "C  Surface Cards: N surfaces defined" → 被计入曲面原始文本
    "other_cards",       # "C  ===== Data Cards =====" → 被捕获进 other_cards 并重放
    "tally.comment",     # 同理，计数段头泄漏
}


def roundtrip_generations(deck: DeckData) -> tuple[str, DeckData, str]:
    """generate(d) → parse → generate，返回 (g1, deck2, g2)。"""
    g1 = generate_inp_from_deck(deck)
    deck2, _warns = parse_inp_text(g1)
    g2 = generate_inp_from_deck(deck2)
    return g1, deck2, g2


# ── R1 不动点 ───────────────────────────────────────────
def test_r1_fixed_point_minimal_deck():
    """R1：最小 deck 第二代起字节稳定。当前应为 RED（头泄漏）。"""
    from tests.conftest import single_cell_deck
    g1, _d2, g2 = roundtrip_generations(single_cell_deck())
    assert g1 == g2, (
        "R1 不动点不成立：generate(parse(generate(d))) != generate(d)。\n"
        "根因：生成器 C 注释头（'C  Cell Cards: N cells defined' 等）被解析器"
        "吸收进结构化字段，导致输出逐代膨胀。这是 M1.4 门禁阻塞项。"
    )


def test_r1_fixed_point_kitchen_sink():
    """R1：kitchen-sink（R4）第二代起字节稳定。当前应为 RED。"""
    from tests.conftest import kitchen_sink_deck
    g1, _d2, g2 = roundtrip_generations(kitchen_sink_deck.__wrapped__())
    assert g1 == g2, "R1 在 kitchen-sink deck 上不成立（头泄漏导致输出增长）。"


def test_r1_fixed_point_sample_prob41c():
    """R1：vendor 样例 prob41c 第二代起字节稳定。当前应为 RED。"""
    text = load_sample("prob41c.inp")
    deck, _w = parse_inp_text(text)
    g1, _d2, g2 = roundtrip_generations(deck)
    assert g1 == g2, f"R1 在 prob41c 上不成立（len {len(g1)} → {len(g2)}）。"


def test_r1_fixed_point_sample_avr13():
    """R1：vendor 样例 avr13 第二代起字节稳定。当前应为 RED。"""
    text = load_sample("avr13.inp")
    deck, _w = parse_inp_text(text)
    g1, _d2, g2 = roundtrip_generations(deck)
    assert g1 == g2, f"R1 在 avr13 上不成立（len {len(g1)} → {len(g2)}）。"


def test_r1_lattice_17x17_fixed_point():
    """R1：OWEN 17×17 格阵夹具第二代起字节稳定（阶段1 格阵不动点闸门）。

    格阵 cell 经 format_fill_cards 回放 raw（范围串 + 条目续行），parse→gen→parse→gen
    字节必须稳定；格阵 cell 的 $ 注释移到条目续行之后（不吞条目）。
    """
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "fixtures" / "owen"
            / "assembly_17x17_mcnp.i").read_text(encoding="utf-8", errors="replace")
    deck, _w = parse_inp_text(text)
    g1, _d2, g2 = roundtrip_generations(deck)
    assert g1 == g2, f"17×17 格阵 R1 不动点不成立（len {len(g1)} → {len(g2)}）。"


def test_r1_lattice_prob41c_fixed_point():
    """R1：vendor 样例 prob41c（含格阵 fill + (9 0 9) 偏移条目）第二代起字节稳定。"""
    text = load_sample("prob41c.inp")
    deck, _w = parse_inp_text(text)
    g1, _d2, g2 = roundtrip_generations(deck)
    assert g1 == g2, f"prob41c 格阵 R1 不动点不成立（len {len(g1)} → {len(g2)}）。"


def test_r1_output_does_not_grow_unboundedly():
    """R1 退化检查：输出长度第二代不应继续增长（近似不动点的必要不充分条件）。"""
    from tests.conftest import kitchen_sink_deck
    g1, _d2, g2 = roundtrip_generations(kitchen_sink_deck.__wrapped__())
    assert len(g2) <= len(g1) * 1.10, f"输出膨胀超阈值: {len(g1)} → {len(g2)}"


# ── R2 语义逐字段对比 ───────────────────────────────────
def _cell_fields(c):
    return {
        "number": c.number, "material": c.material, "density": c.density,
        "surface_expr": c.surface_expr, "imp_n": c.imp_n, "imp_p": c.imp_p,
        "imp_e": c.imp_e, "vol": c.vol, "pwt": c.pwt, "ext": c.ext, "fcl": c.fcl,
        "u": c.u, "fill": c.fill, "lat": c.lat, "trcl": c.trcl, "tmp": c.tmp,
        "fill_grid": c.fill_grid,
    }


def _strip_wrap_artifact(expr: str) -> str:
    """去掉行尾续行符 &（_wrap_long_lines 拆分超长行时附加，污染 surface_expr）。"""
    s = expr.strip()
    while s.endswith("&"):
        s = s[:-1].strip()
    return s


def test_r2_basic_fields_survive():
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    b1, b2 = deck.basic, deck2.basic
    for f in ("title", "mode_n", "mode_p", "mode_e", "mode_h", "mode_he",
              "mode_d", "mode_t", "mode_a", "nps", "ctme", "act", "print_pr",
              "phys_fis"):
        assert getattr(b1, f) == getattr(b2, f), f"basic.{f} 丢失: {getattr(b1, f)!r} → {getattr(b2, f)!r}"


def test_r2_cell_content_fields_survive():
    """除已知泄漏/已知归一化外，栅元内容字段应逐字段保留。"""
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    c1 = {c.cell.number: c.cell for c in deck.cells if c.kind == "cell"}
    c2 = {c.cell.number: c.cell for c in deck2.cells if c.kind == "cell"}
    assert c1.keys() == c2.keys(), f"栅元号集合不一致: {c1.keys()} vs {c2.keys()}"
    for num, cell in c1.items():
        f1, f2 = _cell_fields(cell), _cell_fields(c2[num])
        # 容忍 _wrap_long_lines 附加的尾 &（KNOWN_LEAK）
        f2["surface_expr"] = _strip_wrap_artifact(f2["surface_expr"])
        # 容忍 IMP 归一化（KNOWN_NORMALIZATION）：任一栅元显式写了某粒子 IMP，
        # 生成器会给其余结构化栅元补齐该粒子默认重要性 1 → 回读后原空字段变 "1"。
        for imp_f in ("imp_n", "imp_p", "imp_e"):
            if f1[imp_f] == "" and f2[imp_f] == "1":
                f2[imp_f] = ""
        assert f1 == f2, f"栅元 {num} 内容字段不一致: {f1} vs {f2}"


def test_r2_material_rows_and_mt_survive():
    """材料行（zaid/fraction/raw）与 MT 卡应逐条保留。"""
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    m1 = {m.number: m for m in deck.materials}
    m2 = {m.number: m for m in deck2.materials}
    assert m1.keys() == m2.keys(), f"材料号集合不一致: {m1.keys()} vs {m2.keys()}"
    for num, mat in m1.items():
        rows1 = [(r.kind, r.zaid, r.fraction) for r in mat.rows]
        rows2 = [(r.kind, r.zaid, r.fraction) for r in m2[num].rows]
        assert rows1 == rows2, f"M{num} 行不一致: {rows1} vs {rows2}"
        assert mat.mt_card == m2[num].mt_card


def test_r2_material_options_survive():
    """材料 options（nlib= 等）应逐字段保留。当前 RED：options 被并入 raw 行丢失。"""
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    m1 = {m.number: m for m in deck.materials}
    m2 = {m.number: m for m in deck2.materials}
    for num, mat in m1.items():
        assert mat.options == m2[num].options, (
            f"M{num} options 丢失: {mat.options!r} → {m2[num].options!r}\n"
            "(生成时 options 追加到末行尾部，被解析器并入 raw 行文本)"
        )


def _single_source_deck():
    """单源 fixed 模式 deck：SourceData 各字段填非平凡值。"""
    from app.models import (DeckData, BasicSettings, TallySettings,
                            AdvancedSettings, SourceData, MaterialData,
                            MaterialRow, CellRow)
    from tests.conftest import _cell
    return DeckData(
        basic=BasicSettings(title="single src r2", mode_n=True, nps="100000"),
        surfaces="1  rcc  0 0 0  0 10 0  2",
        cells=[CellRow(kind="cell", cell=_cell(number=1, material="1",
                                               density="-1.0", surface_expr="-1"))],
        materials=[MaterialData(number=1, rows=[MaterialRow(zaid="92235.06c", fraction="-0.05")])],
        sources=[SourceData(number=1, par="1", erg="14.0", pos_x="0", pos_y="0",
                            pos_z="0", dir_="1", wgt="1.0", cel="1", tme="0.0",
                            vec="0 0 1", axs="0 0 1", rad="0.5", ext="0.0",
                            sur="1", nrm="1", tr="1", ccc="1", ara="1.0",
                            rate="1e6")],
        tally=TallySettings(), adv=AdvancedSettings(source_mode="fixed"),
    )


def test_r2_single_source_fields_survive():
    """单源 fixed 模式：SourceData 各字段应逐字段保留（表示不变，可语义对比）。"""
    deck = _single_source_deck()
    g1, deck2, _g2 = roundtrip_generations(deck)
    s1, s2 = deck.sources[0], deck2.sources[0]
    for f in ("par", "erg", "pos_x", "pos_y", "pos_z", "dir_", "wgt",
              "cel", "tme", "vec", "axs", "rad", "ext", "sur", "nrm",
              "tr", "ccc", "ara", "rate"):
        # 容忍 _wrap_long_lines 拆超长 SDEF 行时附加的尾 &（KNOWN_LEAK）
        expect = _strip_wrap_artifact(getattr(s1, f))
        got = _strip_wrap_artifact(getattr(s2, f))
        assert expect == got, \
            f"source.{f} 丢失: {getattr(s1, f)!r} → {getattr(s2, f)!r}"


def test_r2_multi_source_roundtrips_to_distribution_mode():
    """多源 kitchen-sink 经 round-trip 合法转为 distribution 模式（SDEF D 引用 + SI/SP）。

    这不是数据丢失，而是表示变换：多源在生成时合并为一张带 Dn 引用的 SDEF +
    SI/SP 分布卡，解析回 distribution 模式。R1 字节稳定是此场景的正确性红线。
    """
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    assert deck2.adv.source_mode == "distribution", \
        f"多源 round-trip 后应为 distribution 模式，实际 {deck2.adv.source_mode!r}"
    assert deck2.adv.sdef_distributions, "distribution 模式应带结构化分布 JSON"


def test_r2_tally_single_particle_survive():
    """单粒子计数卡应逐条保留。"""
    from app.models import DeckData, BasicSettings, TallySettings, TallyDefinition
    from app.models import AdvancedSettings
    from tests.conftest import single_cell_deck
    deck = single_cell_deck()
    deck.tally = TallySettings(tallies=[
        TallyDefinition(type="F1", number=1, particles=["n"], params="1"),
    ])
    deck.adv = AdvancedSettings()
    g1, deck2, _g2 = roundtrip_generations(deck)
    td1 = {(t.type, t.number): t for t in deck.tally.tallies}
    td2 = {(t.type, t.number): t for t in deck2.tally.tallies}
    for key, td in td1.items():
        assert key in td2, f"tally {key} 丢失"
        assert td.particles == td2[key].particles
        assert td.params == td2[key].params


def test_r2_tally_multi_particle_parse_supported():
    """多粒子计数卡（生成输出 F4:N,P）应可解析回 TallyDefinition。

    当前 RED：parse_f_tally 只认单粒子设计符（F4:N），"F4:N,P" 被丢进 other_cards，
    多粒子计数在 round-trip 后消失。
    """
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    t1 = {(t.type, t.number) for t in deck.tally.tallies}
    t2 = {(t.type, t.number) for t in deck2.tally.tallies}
    assert t1 == t2, f"计数卡 round-trip 丢失: {t1 - t2}"


def test_r2_cut_fields_survive():
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    t1, t2 = deck.tally, deck2.tally
    for p in ("n", "p", "e"):
        assert getattr(t1, f"cut_{p}_t") == getattr(t2, f"cut_{p}_t"), f"cut_{p}_t 不一致"
        assert getattr(t1, f"cut_{p}_e") == getattr(t2, f"cut_{p}_e"), f"cut_{p}_e 不一致"


def test_r2_phys_fields_survive():
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    a1, a2 = deck.adv, deck2.adv
    phys_fields = ("phys_n_emax", "phys_n_emcnf", "phys_n_iunr", "phys_n_dnb",
                   "phys_n_fisnu", "phys_p_emcpf", "phys_p_ides",
                   "phys_e_emax", "phys_e_ides")
    for f in phys_fields:
        if getattr(a1, f):
            assert getattr(a1, f) == getattr(a2, f), f"adv.{f} 不一致"


# ── R3 分段无内容丢失（允许顺序后移）────────────────────
def test_r3_surfaces_no_content_loss():
    """surfaces 卡全部行应在 round-trip 后保留（含顺序后移的容忍）。"""
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    orig_lines = {l.strip() for l in deck.surfaces.split("\n") if l.strip()}
    new_lines = {l.strip() for l in deck2.surfaces.split("\n") if l.strip()}
    missing = orig_lines - new_lines
    assert not missing, f"surfaces 内容丢失: {missing}"


def test_r3_other_cards_no_content_loss():
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    orig = {l.strip().lower() for l in deck.adv.other_cards.split("\n") if l.strip()}
    new = {l.strip().lower() for l in deck2.adv.other_cards.split("\n") if l.strip()}
    missing = orig - new
    assert not missing, f"other_cards 内容丢失: {missing}"


def test_r3_tr_cards_no_content_loss():
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    g1, deck2, _g2 = roundtrip_generations(deck)
    assert deck.tr_cards.strip(), "测试前置：tr_cards 应为非空"
    orig = {l.strip().lower() for l in deck.tr_cards.split("\n") if l.strip()}
    new = {l.strip().lower() for l in deck2.tr_cards.split("\n") if l.strip()}
    missing = orig - new
    assert not missing, f"TR 卡内容丢失: {missing}"


# ── R4 kitchen-sink R1+R2 ───────────────────────────────
def test_r4_kitchen_sink_full_roundtrip():
    """R4：kitchen-sink deck 每个 dataclass 字段填非平凡值，跑 R1+R2。"""
    from tests.conftest import kitchen_sink_deck
    deck = kitchen_sink_deck.__wrapped__()
    # 校验前置：deck 各 section 非空（防"空 deck 假绿"）
    assert deck.basic.title and deck.basic.nps
    assert len(deck.cells) >= 3
    assert len(deck.materials) >= 2
    assert len(deck.sources) >= 2
    assert deck.tally.tallies
    # R1
    g1, deck2, g2 = roundtrip_generations(deck)
    assert g1 == g2, "R4 的 R1 不成立（头泄漏导致输出增长）"
