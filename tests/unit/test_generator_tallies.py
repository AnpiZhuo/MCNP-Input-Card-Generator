"""生成器单测：计数卡 / En/T0/Tn / CUT / j-skip 压缩 / E0 网格。"""
import pytest

from app.generator.inp_generator import (
    _compress_j_skip, _parse_numeric_cards, _emit_numeric_card,
    _generate_tallies, _generate_en_cards, _generate_time_mesh,
    _generate_tn_cards, _generate_energy_mesh, _generate_cut,
)
from app.models import TallySettings, TallyDefinition


# ── _compress_j_skip ────────────────────────────────────
def test_compress_j_skip():
    assert _compress_j_skip(["", "", "0", "0"]) == "2J 0 0"
    assert _compress_j_skip(["", "1", "", "0"]) == "J 1 J 0"
    assert _compress_j_skip(["0", "0", "", ""]) == "0 0"
    assert _compress_j_skip([""] * 5) == ""
    assert _compress_j_skip(["1"]) == "1"


# ── _parse_numeric_cards ────────────────────────────────
def test_parse_numeric_cards_simple():
    text = "E4  1\n     2\nE1  0.1 1\n"
    out = _parse_numeric_cards(text, "E")
    assert out == [(4, ["1", "2"]), (1, ["0.1 1"])]


def test_parse_numeric_cards_unrecognized_line_merged_into_current_card():
    # 非空且无法识别为 E{n} 开头的行，会并入上一张卡的参数（续行语义）
    out = _parse_numeric_cards("E1  1\njunk line\n", "E")
    assert out == [(1, ["1", "junk line"])]


# ── _generate_tallies ───────────────────────────────────
def test_tally_cards_per_particle_merged():
    # 同一计数多粒子 → 逗号合并到一张卡（F4:N,P）
    tally = TallySettings(tallies=[
        TallyDefinition(type="F4", number=4, particles=["n", "p"], params="1 2"),
    ])
    lines = _generate_tallies(tally)
    assert any("F4:N,P" in l for l in lines)


def test_tally_fip_prefix():
    tally = TallySettings(tallies=[
        TallyDefinition(type="F4", number=4, particles=["n"], params="1",
                        fn_prefix="FIP"),
    ])
    lines = _generate_tallies(tally)
    assert any(l.strip().startswith("FIP4:N") for l in lines)


def test_tally_no_particles_defaults_to_n():
    tally = TallySettings(tallies=[
        TallyDefinition(type="F4", number=4, particles=[], params="1"),
    ])
    lines = _generate_tallies(tally)
    assert any("F4:N" in l for l in lines)


def test_tally_f5_multipoint_params_preserved():
    tally = TallySettings(tallies=[
        TallyDefinition(type="F5", number=5, particles=["n"],
                        params="1 2 3 1 2 4"),
    ])
    lines = _generate_tallies(tally)
    assert any("1 2 3 1 2 4" in l for l in lines)


# ── En 卡（_generate_en_cards）──────────────────────────
def test_en_cards_only_for_enabled_tallies():
    tally = TallySettings(
        tallies=[TallyDefinition(type="F4", number=4, particles=["n"], params="1",
                                 generate_en=True)],
        e_cards_text="E4  1 2 3 4\nE1  0.1 1 10",
    )
    lines = _generate_en_cards(tally)
    assert any(l.strip() == "E4" for l in lines)
    assert not any(l.strip().startswith("E1") for l in lines)


def test_en_cards_empty_text():
    assert _generate_en_cards(TallySettings()) == []


# ── Tn 卡（_generate_tn_cards）──────────────────────────
def test_tn_cards_for_enabled_tallies():
    tally = TallySettings(
        tallies=[TallyDefinition(type="F4", number=4, particles=["n"], params="1",
                                 generate_tn=True)],
        t_cards_text="T4  0 5 10\nT1  0 1 2",
    )
    lines = _generate_tn_cards(tally)
    assert any(l.strip() == "T4" for l in lines)
    assert not any(l.strip().startswith("T1") for l in lines)


# ── E0 网格（_generate_energy_mesh）─────────────────────
def test_energy_mesh_parametric_log():
    tally = TallySettings(e_min="0.001", e_max="14", e_bins=100, e_log=True)
    lines = _generate_energy_mesh(tally)
    text = "\n".join(lines)
    assert text.startswith("E0\n")
    assert "100log" in text
    assert "0.001" in text and "14" in text


def test_energy_mesh_linear():
    tally = TallySettings(e_min="0.0", e_max="10", e_bins=10, e_log=False)
    lines = _generate_energy_mesh(tally)
    text = "\n".join(lines)
    assert "10i" in text


def test_energy_mesh_empty():
    assert _generate_energy_mesh(TallySettings()) == []


# ── T0 网格（_generate_time_mesh）───────────────────────
def test_time_mesh_parametric():
    tally = TallySettings(t0_min="0", t0_max="100", t0_bins=50, t0_log=True)
    lines = _generate_time_mesh(tally)
    text = "\n".join(lines)
    assert text.startswith("T0\n")
    assert "50log" in text


def test_time_mesh_custom_text():
    tally = TallySettings(t0_custom_enabled=True, t0_custom_text="0\n5\n10")
    lines = _generate_time_mesh(tally)
    text = "\n".join(lines)
    assert text.startswith("T0\n")
    assert "5" in text


# ── CUT 卡（_generate_cut）──────────────────────────────
def test_cut_n_compressed():
    tally = TallySettings(cut_n_t="100", cut_n_e="1e-4", cut_n_wc1="0.5")
    lines = _generate_cut(tally)
    assert any("CUT:N  100 1e-4 0.5" in l for l in lines)


def test_cut_only_emits_nonempty():
    tally = TallySettings(cut_n_t="", cut_n_e="", cut_n_wc1="", cut_n_wc2="", cut_n_swtm="")
    lines = _generate_cut(tally)
    assert not any(l.startswith("CUT:N") for l in lines)


def test_cut_all_particle_types():
    tally = TallySettings(
        cut_n_t="1", cut_p_t="2", cut_e_t="3", cut_h_t="4",
        cut_he_t="5", cut_d_t="6", cut_t_t="7", cut_a_t="8",
    )
    lines = _generate_cut(tally)
    designators = [l.split(":")[1].split()[0] for l in lines if l.startswith("CUT:")]
    assert set(designators) == {"N", "P", "E", "H", "HE", "D", "T", "A"}


# ── _emit_numeric_card ──────────────────────────────────
def test_emit_numeric_card_values_split():
    out = []
    _emit_numeric_card(out, "E", 4, ["1", "2", "3"])
    assert out == ["E4", "     1", "     2", "     3"]


def test_emit_numeric_card_mixed_keeps_raw():
    out = []
    _emit_numeric_card(out, "E", 4, ["1 2i 3"])
    assert out == ["E4  1 2i 3"]
