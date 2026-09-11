"""
样例冒烟（P0-4）：vendor 样例 parse → validate → generate。
覆盖 prob41c / avr13 / inp24 三份（已 vendor 进 tests/fixtures/，不依赖外部路径）。

管道：parse_inp_text → validate → generate_inp_from_deck
断言：关键卡出现、R1 成立、结果可二次解析。

【当前状态（2026-09-10 更正）】**全部应为 GREEN**。初版写"R1 不动点 RED / validate_deck RED"——
该表述**已作废**（C 注释头泄漏与 CellRow 判别联合不兼容均已修复）。**红灯就是真红灯**（审计 TD-09）。
- validate_inp_text（生产文本层校验）在 3 份样例上全过。
- generate 关键卡出现、可二次解析：GREEN。
- R1 不动点：GREEN。
- validate_deck（DeckData 层）：GREEN。
"""
import pytest

from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.generator.parsers.validator import validate_inp_text
from app.generator.validator import validate_deck

from tests.conftest import load_sample

SAMPLES = ["prob41c.inp", "avr13.inp", "inp24.inp"]

# 每份样例生成结果应出现的关键卡特征
# 注：inp24 无 MODE/NPS（kcode 临界 deck）；avr13 无材料卡（void 栅元）。
KEY_CARDS = {
    "prob41c.inp": ["MODE", "NPS", "SDEF", "F4"],
    "avr13.inp": ["MODE", "NPS", "SDEF", "SI1", "SP1", "F1"],
    "inp24.inp": ["KCODE", "KSRC", "F6", "M1"],
}

# 每份样例应存在的 section（inp24 无 NPS/MODE，avr13 无材料）
REQUIRED_SECTIONS = {
    "prob41c.inp": ["cells", "surfaces", "materials", "sources"],
    "avr13.inp": ["cells", "surfaces", "sources"],
    "inp24.inp": ["cells", "surfaces", "materials"],
}


def _parse_sample(name):
    deck, warns = parse_inp_text(load_sample(name))
    return deck, warns


# ── 生产文本层校验（validate_inp_text）────────────────────
@pytest.mark.parametrize("name", SAMPLES)
def test_smoke_validate_inp_text(name):
    """validate_inp_text 在 vendor 样例上应返回空错误列表（生产 /api/validate-inp 路径）。"""
    errors = validate_inp_text(load_sample(name))
    assert errors == [], f"{name} validate_inp_text 报错: {errors[:5]}"


# ── 解析 → 生成 → 二次解析 ──────────────────────────────
@pytest.mark.parametrize("name", SAMPLES)
def test_smoke_generate_key_cards_and_reparse(name):
    """parse → generate：关键卡出现，且结果可二次解析（不抛异常）。"""
    deck, _warns = _parse_sample(name)
    assert len(deck.cells) > 0, f"{name} 未解析出栅元"
    out = generate_inp_from_deck(deck)
    for card in KEY_CARDS[name]:
        assert card in out.upper(), f"{name} 生成结果缺少关键卡 {card}"
    # 二次解析不抛异常
    deck2, _warns2 = parse_inp_text(out)
    assert len(deck2.cells) > 0, f"{name} 二次解析失败（无栅元）"


@pytest.mark.parametrize("name", SAMPLES)
def test_smoke_parse_populates_sections(name):
    deck, _warns = _parse_sample(name)
    sections = []
    if len(deck.cells) > 0:
        sections.append("cells")
    if deck.surfaces.strip():
        sections.append("surfaces")
    if len(deck.materials) > 0:
        sections.append("materials")
    if len(deck.sources) > 0 or deck.adv.source_mode in ("kcode", "surface"):
        sections.append("sources")
    for req in REQUIRED_SECTIONS[name]:
        assert req in sections, f"{name} 缺少 {req} section（实际: {sections}）"


# ── R1 不动点（已清偿 → 应 GREEN）──────────────────────────
@pytest.mark.parametrize("name", SAMPLES)
def test_smoke_r1_fixed_point(name):
    """R1：样例第二代起字节稳定。**已清偿 → 应 GREEN**（初版："当前 RED（C 注释头泄漏）"）。"""
    deck, _w = _parse_sample(name)
    g1 = generate_inp_from_deck(deck)
    deck2, _w2 = parse_inp_text(g1)
    g2 = generate_inp_from_deck(deck2)
    assert g1 == g2, f"{name} R1 不成立（len {len(g1)} → {len(g2)}，头泄漏）"


# ── validate_deck（DeckData 层）已清偿 → 应 GREEN（初版标"RED：CellRow 不兼容"）───────
@pytest.mark.parametrize("name", SAMPLES)
def test_smoke_validate_deck_does_not_crash(name):
    """计划流程 parse → validate_deck → generate。

    **已清偿 → 应 GREEN**（初版写"当前 RED：validate_deck 直接访问 cell.surface_expr，
    与 CellRow 判别联合不兼容，抛 AttributeError"，已作废）。
    """
    deck, _w = _parse_sample(name)
    try:
        errors = validate_deck(deck)
    except AttributeError as e:
        pytest.fail(
            f"{name} validate_deck 崩溃（CellRow 与 validate_all 不兼容）: {e}"
        )
    assert isinstance(errors, list)
