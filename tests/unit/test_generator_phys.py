"""生成器单测：PHYS / other_cards / KCODE / KSRC / HSRC / SSW / SSR。"""
from app.generator.inp_generator import (
    _generate_phys, _generate_other_cards, _generate_kcode,
    _generate_ssw, _generate_ssr,
)
from app.models import AdvancedSettings


def _adv(**kw):
    base = dict()
    base.update(kw)
    return AdvancedSettings(**base)


# ── PHYS 卡 ─────────────────────────────────────────────
def test_phys_n_p_e_h_he_compressed():
    adv = _adv(
        phys_n_emax="100", phys_n_emcnf="0.1", phys_n_iunr="1",
        phys_p_emcpf="50", phys_p_ides="1",
        phys_e_emax="100", phys_e_ides="1", phys_e_iphoto="1",
        phys_h_emax="100", phys_h_ie="1",
        phys_he_emax="100", phys_he_ie="1",
    )
    lines = _generate_phys(adv)
    assert any(l.startswith("PHYS:N  ") for l in lines)
    assert any(l.startswith("PHYS:P  ") for l in lines)
    assert any(l.startswith("PHYS:E  ") for l in lines)
    assert any(l.startswith("PHYS:H  ") for l in lines)
    assert any(l.startswith("PHYS:HE  ") for l in lines)


def test_phys_empty_no_output():
    assert _generate_phys(_adv()) == []


# ── other_cards ─────────────────────────────────────────
def test_other_cards_verbatim():
    adv = _adv(other_cards="MPHYS  1\nDBCN  28j  0  13j  0")
    lines = _generate_other_cards(adv)
    assert any("MPHYS  1" in l for l in lines)
    assert any("DBCN" in l for l in lines)


def test_other_cards_empty():
    assert _generate_other_cards(_adv()) == []


# ── KCODE / KSRC / HSRC ────────────────────────────────
def test_kcode_header_and_8_params():
    adv = _adv(kcode_nsrc="1000", kcode_rkk="1.0", kcode_ikz="30", kcode_kct="100")
    lines = _generate_kcode(adv)
    assert lines[0] == "C  KCODE Criticality Source Parameters"
    assert any("KCODE  1000 1.0 30 100" in l for l in lines)


def test_kcode_skipped_when_no_nsrc():
    lines = _generate_kcode(_adv())
    assert any("skipped" in l for l in lines)


def test_ksrc_points_emitted_with_continuation():
    # 生产数据：ksrc_points JSON 串中坐标是字符串（契约 ksrcPoints: type string）
    adv = _adv(kcode_nsrc="1000",
               ksrc_points='[{"x":"0","y":"0","z":"0"},{"x":"1","y":"1","z":"1"}]')
    lines = _generate_kcode(adv)
    assert any(l.startswith("KSRC") for l in lines)
    assert any(l.strip().startswith("1  1  1") for l in lines)


def test_ksrc_numeric_coords_emitted():
    # 翻新（F-F）：数值坐标（json.loads 保持 int/float）不应崩溃，应产出合法 KSRC 行；
    # 且坐标 0 是合法值，不得被 falsy 吞掉（参照 test_ksrc_points_emitted_with_continuation 的断言形式）。
    adv = _adv(kcode_nsrc="1000",
               ksrc_points='[{"x":0,"y":0,"z":0},{"x":1,"y":1,"z":1}]')
    lines = _generate_kcode(adv)
    assert any(l.startswith("KSRC") for l in lines)
    assert any("0  0  0" in l for l in lines)
    assert any("1  1  1" in l for l in lines)


def test_ksrc_invalid_json_graceful():
    adv = _adv(kcode_nsrc="1000", ksrc_points="not-json")
    lines = _generate_kcode(adv)
    assert any("failed to parse" in l for l in lines)


def test_hsrc_emitted_when_enabled():
    adv = _adv(kcode_nsrc="1000", hsrc_enabled=True, hsrc_text="3 0 1 10 -10 10 10")
    lines = _generate_kcode(adv)
    assert any("HSRC  3 0 1 10 -10 10 10" in l for l in lines)


def test_hsrc_not_emitted_when_disabled():
    adv = _adv(kcode_nsrc="1000", hsrc_enabled=False, hsrc_text="3 0 1 10 -10 10 10")
    lines = _generate_kcode(adv)
    assert not any(l.startswith("HSRC") for l in lines)


# ── SSW / SSR 面源 ──────────────────────────────────────
def test_ssw_full():
    adv = _adv(ssw_surf="1", ssw_sym="1", ssw_pty="N", ssw_cel="1 2")
    lines = _generate_ssw(adv)
    assert lines == ["SSW  1  SYM=1  PTY=N  CEL=1 2"]


def test_ssw_empty_when_no_surf():
    assert _generate_ssw(_adv()) == []


def test_ssr_old_mode():
    adv = _adv(ssr_surf="2", ssr_mode="old", ssr_cel="2", ssr_pty="N",
               ssr_col="3", ssr_wgt="1.0", ssr_tr="1", ssr_psc="1")
    lines = _generate_ssr(adv)
    assert lines == ["SSR  OLD  2  CEL=2  PTY=N  COL=3  WGT=1.0  TR=1  PSC=1"]


def test_ssr_empty_when_no_surf():
    assert _generate_ssr(_adv()) == []
