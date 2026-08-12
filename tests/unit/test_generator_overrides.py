"""
raw_overrides 机制测试（F#1）—— 只 pin 既有行为，不改变行为。

前端实际只写 4 key（cells/materials/tally/sdef），后端另支持
surfaces/phys/e0/cut（类型遗留）。空串 = 无覆盖。
"""
import pytest

from app.generator.inp_generator import generate_inp_from_deck
from app.models import (DeckData, BasicSettings, TallySettings, AdvancedSettings,
                        SourceData, MaterialData, MaterialRow, CellRow,
                        TallyDefinition)

RAW_KEYS = ["cells", "surfaces", "materials", "sdef", "phys", "tally", "e0", "cut"]


def _full_deck() -> DeckData:
    """8 个 section 全部有可生成内容的 deck。"""
    from tests.conftest import _cell
    return DeckData(
        basic=BasicSettings(title="override deck", mode_n=True, mode_p=True,
                            nps="100000", act="2j 1", print_pr="128",
                            phys_fis=False),
        surfaces="1  rcc  0 0 0  0 10 0  2\n2  pz  10",
        cells=[
            CellRow(kind="cell", cell=_cell(number=1, material="1", density="-1.0",
                                            surface_expr="-1 2", imp_n="1",
                                            comment="core")),
            CellRow(kind="cell", cell=_cell(number=2, material="0", density="",
                                            surface_expr="-2", imp_n="0")),
        ],
        materials=[
            MaterialData(number=1, comment="fuel",
                         rows=[MaterialRow(zaid="92235.06c", fraction="-0.05")],
                         options="nlib=.66c"),
        ],
        sources=[SourceData(number=1, par="n", erg="14.0", pos_x="0", pos_y="0",
                            pos_z="0", wgt="1.0")],
        tally=TallySettings(
            tallies=[
                TallyDefinition(type="F4", number=4, particles=["n"], params="1 2",
                                generate_en=True, generate_tn=True),
            ],
            e_min="0.001", e_max="14", e_bins=100, e_log=True,
            e_cards_text="E4  1 2 3 4 5",
            t0_min="0", t0_max="100", t0_bins=50, t0_log=False,
            t_cards_text="T4  0 5 10",
            cut_n_t="100", cut_n_e="1e-4", cut_n_wc1="0.5",
        ),
        adv=AdvancedSettings(
            phys_n_emax="100", phys_n_emcnf="0.1", phys_n_iunr="1",
            other_cards="MPHYS  1",
        ),
    )


# 每个 key 的"生成内容特征串"（出现即代表该 section 走了生成路径，而非 raw）
GENERATED_MARKERS = {
    "cells": "C  Cell Cards:",
    "surfaces": "C  Surface Cards:",
    "materials": "M1",
    "sdef": "SDEF",
    "phys": "PHYS:N",
    "tally": "F4:N",
    "e0": "E0",
    "cut": "CUT:N",
}


@pytest.mark.parametrize("key", RAW_KEYS)
def test_raw_override_replaces_generated_section(key):
    # 注意：marker 用小写 key，避免与 GENERATED_MARKERS 的大写子串（SDEF/E0/M1…）冲突
    deck = _full_deck()
    raw = f"@RAW_{key}_OVERRIDE_MARKER_ZZ\ncontinuation line"
    out = generate_inp_from_deck(deck, {key: raw})
    assert f"@RAW_{key}_OVERRIDE_MARKER_ZZ" in out, f"{key} 覆盖未生效"
    assert GENERATED_MARKERS[key] not in out, f"{key} 覆盖后仍生成原内容"


@pytest.mark.parametrize("key", RAW_KEYS)
def test_raw_override_empty_string_means_no_override(key):
    deck = _full_deck()
    out = generate_inp_from_deck(deck, {key: ""})
    assert GENERATED_MARKERS[key] in out, f"{key} 空串应等于无覆盖（保留生成内容）"


@pytest.mark.parametrize("key", RAW_KEYS)
def test_raw_override_whitespace_means_no_override(key):
    deck = _full_deck()
    out = generate_inp_from_deck(deck, {key: "   \n  "})
    assert GENERATED_MARKERS[key] in out, f"{key} 纯空白应等于无覆盖"


def test_raw_override_all_keys_simultaneously():
    deck = _full_deck()
    overrides = {k: f"RAW_{k}_MARKER" for k in RAW_KEYS}
    out = generate_inp_from_deck(deck, overrides)
    for k in RAW_KEYS:
        assert f"RAW_{k}_MARKER" in out
    for marker in GENERATED_MARKERS.values():
        assert marker not in out


# ── 1145 行门控 pin（raw_tally 门控 En/T0/Tn，不一致变体）────────
def test_raw_tally_override_suppresses_en_t0_tn():
    """tally 覆盖 → En/T0/Tn 全部不生成（1145 行 raw_tally 门控既有行为）。"""
    deck = _full_deck()
    out = generate_inp_from_deck(deck, {"tally": "RAW_TALLY_MARKER"})
    assert "RAW_TALLY_MARKER" in out
    assert "E4" not in out, "tally 覆盖后 En 卡不应生成"
    assert "T0" not in out, "tally 覆盖后 T0 不应生成"
    assert "T4" not in out, "tally 覆盖后 Tn 不应生成"


def test_e0_override_does_NOT_suppress_en_t0_tn():
    """e0 覆盖 → e0 section 被替换，但 En/T0/Tn 仍生成（门控只看 raw_tally）。

    这是 F#1 的不一致变体：1145 行 `raw_tally = overrides.get("tally")`
    判的是 tally key，而非当前 e0 override key。pin 既有行为。
    """
    deck = _full_deck()
    out = generate_inp_from_deck(deck, {"e0": "@RAW_e0_OVERRIDE_MARKER_ZZ"})
    assert "@RAW_e0_OVERRIDE_MARKER_ZZ" in out
    assert "E0" not in out, "e0 覆盖后 parametric E0 不应生成"
    assert "E4" in out, "En 卡仍应生成（门控看 raw_tally 而非 e0）"
    assert "T0" in out, "T0 仍应生成"
    assert "T4" in out, "Tn 仍应生成"


def test_cut_override_does_not_affect_en_t0_tn():
    deck = _full_deck()
    out = generate_inp_from_deck(deck, {"cut": "RAW_CUT_MARKER"})
    assert "RAW_CUT_MARKER" in out
    assert "E4" in out
    assert "T0" in out
    assert "T4" in out
