"""生成器单测：基本设置卡（MODE/NPS/CTME/NONU）与 ZAID 归一化。"""
import pytest

from app.generator.inp_generator import _generate_basic, _normalize_zaid, _dist_json_nonempty
from app.models import BasicSettings


def _basic(**kw):
    base = dict(title="t", mode_n=True, nps="100000")
    base.update(kw)
    return BasicSettings(**base)


def test_mode_n_only():
    lines = _generate_basic(_basic())
    assert lines[0] == "MODE N"


def test_mode_npe():
    lines = _generate_basic(_basic(mode_n=True, mode_p=True, mode_e=True))
    assert "MODE" in lines[0]
    for p in ("N", "P", "E"):
        assert p in lines[0]


def test_mode_he_d_t_a_manual_card():
    # pymcnp 不识别 HE/D/T/A → 手动 MODE 卡（全大写）
    lines = _generate_basic(_basic(mode_n=False, mode_d=True, mode_t=True,
                                   mode_a=True, mode_he=True))
    assert lines[0] == "MODE  HE D T A"


def test_nps_emitted():
    lines = _generate_basic(_basic(nps="500000"))
    assert any("NPS" in l for l in lines)


def test_ctme_emitted():
    lines = _generate_basic(_basic(ctme="10.5"))
    assert any("CTME" in l for l in lines)


def test_phys_fis_false_emits_nonu():
    lines = _generate_basic(_basic(phys_fis=False))
    assert any("NONU" in l for l in lines)


def test_phys_fis_true_no_nonu():
    lines = _generate_basic(_basic(phys_fis=True))
    assert not any("NONU" in l for l in lines)


def test_act_and_print_emitted():
    lines = _generate_basic(_basic(act="2j 1", print_pr="128"))
    assert any("ACT" in l for l in lines)
    assert any("PRINT" in l for l in lines)


def test_empty_mode_no_particles_no_mode_card():
    lines = _generate_basic(_basic(mode_n=False, mode_p=False, mode_e=False))
    assert not any("MODE" in l for l in lines)


# ── _normalize_zaid ─────────────────────────────────────
@pytest.mark.parametrize("zaid,expected", [
    ("001001", "1001"),
    ("008016", "8016"),
    ("092235", "92235"),
    ("92235", "92235"),
    ("92235.06c", "92235.06c"),
    ("8016.03c", "8016.03c"),
])
def test_normalize_zaid_numeric(zaid, expected):
    assert _normalize_zaid(zaid) == expected


@pytest.mark.parametrize("zaid,expected", [
    ("U-235", "92235"),
    ("U235", "92235"),
    ("Fe-56", "26056"),
    ("H-1", "1001"),
])
def test_normalize_zaid_element(zaid, expected):
    assert _normalize_zaid(zaid) == expected


def test_normalize_zaid_keeps_library():
    assert _normalize_zaid("U-235.06c") == "92235.06c"


# ── _dist_json_nonempty ─────────────────────────────────
def test_dist_json_nonempty():
    assert not _dist_json_nonempty("")
    assert not _dist_json_nonempty("[]")
    assert _dist_json_nonempty('[{"id":1}]')
    assert not _dist_json_nonempty("not-json")
