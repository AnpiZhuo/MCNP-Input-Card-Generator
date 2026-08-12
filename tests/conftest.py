"""
P0 测试基建 — sys.path 引导 + deck 工厂 + 样例装载 fixture
=========================================================
运行方式：仓库根 `python -m pytest tests/ -v`
（python -m pytest 会把 cwd 加入 sys.path；此处再显式注入 PROJECT_DIR 兜底）

铁律：本文件（及全部纯引擎测试）【不得】import gui.backend.api_server
（其模块级 pyvista/FreeCAD 探测会污染纯引擎测试）。
"""
import os
import sys
from pathlib import Path

# PROJECT_DIR = tests/ 的上一级 = 仓库根
PROJECT_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import pytest


# ── 样例装载 ──────────────────────────────────────────────
def load_sample(name: str) -> str:
    """读取 tests/fixtures/<name> 的原始文本（vendor 样例，来自 MCNPX_EXTENDED 测试套件）。"""
    path = FIXTURES_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"fixture 缺失: {path}")
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return path.read_text(encoding="latin-1")


@pytest.fixture(scope="session")
def sample_prob41c() -> str:
    """vendor 样例 prob41c（macrobody lattice 栅元，验证复杂几何解析）。"""
    return load_sample("prob41c.inp")


@pytest.fixture(scope="session")
def sample_avr13() -> str:
    """vendor 样例 avr13（WWG 生成器、si1/sp1 分布、f1:n 计数）。"""
    return load_sample("avr13.inp")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


# ── deck 工厂 ─────────────────────────────────────────────
def _cell(**kw) -> "CellData":
    from app.models import CellData
    base = dict(number=1, material="1", density="-1.0", surface_expr="-1")
    base.update(kw)
    return CellData(**base)


def make_deck(**kw) -> "DeckData":
    """构造最小合法 DeckData，可覆盖任意 section。"""
    from app.models import (BasicSettings, DeckData, TallySettings,
                            AdvancedSettings)
    base = dict(
        basic=BasicSettings(title="test deck", mode_n=True, nps="100000"),
        surfaces="1  rcc  0 0 0  0 10 0  2",
        cells=[],
        materials=[],
        sources=[],
        tally=TallySettings(),
        adv=AdvancedSettings(),
    )
    base.update(kw)
    return DeckData(**base)


def single_cell_deck(**cell_kw) -> "DeckData":
    """单栅元 + 单曲面 + 单材料 + 单源的典型 deck。"""
    from app.models import (BasicSettings, DeckData, TallySettings,
                            AdvancedSettings, SourceData, MaterialData,
                            MaterialRow, CellRow)
    deck = make_deck()
    deck.cells = [CellRow(kind="cell", cell=_cell(**cell_kw))]
    deck.materials = [MaterialData(number=1, rows=[MaterialRow(zaid="92235.06c", fraction="-0.05")])]
    deck.sources = [SourceData(number=1, erg="14.0", pos_x="0", pos_y="0", pos_z="0")]
    return deck


@pytest.fixture
def kitchen_sink_deck() -> "DeckData":
    """R4 kitchen-sink deck：每个 dataclass 字段填非平凡值。"""
    from app.models import (BasicSettings, DeckData, TallySettings,
                            AdvancedSettings, SourceData, MaterialData,
                            MaterialRow, CellRow, TallyDefinition)
    deck = DeckData(
        basic=BasicSettings(
            title="Kitchen Sink R4", mode_n=True, mode_p=True, mode_e=True,
            mode_h=True, mode_he=True, mode_d=True, mode_t=True, mode_a=True,
            nps="500000", ctme="10.5", act="2j 1", print_pr="128", phys_fis=False,
        ),
        surfaces=(
            "1  rcc  0 0 0  0 10 0  2\n"
            "2  pz  10\n"
            "3  box  0 0 0  20 0 0  0 20 0  0 0 20\n"
            "4  s  0 0 5  1"
        ),
        tr_cards="TR1  1 0 0 0 1 0 0 0 1  5 0 0\nTR2  0 0 1 1 0 0 0 1 0  0 0 5",
        cells=[
            CellRow(kind="cell", cell=_cell(
                number=1, material="1", density="-1.0", surface_expr="-1 2",
                imp_n="1", imp_p="0.5", imp_e="1", vol="3.14", pwt="1.0",
                ext="2.0", fcl="0.5", u="1", fill="0", lat="1", trcl="1",
                tmp="2.53e-8", other_params="GEO=2", comment="core",
            )),
            CellRow(kind="cell", cell=_cell(
                number=2, material="0", density="", surface_expr="3 #1",
                imp_n="0", comment="outer void",
            )),
            CellRow(kind="raw", text="#ifdef ENDF7"),
            CellRow(kind="cell", cell=_cell(
                number=3, material="2", density="-2.7", surface_expr="-4 3",
                imp_n="1",
            )),
            CellRow(kind="raw", text="#endif"),
        ],
        materials=[
            MaterialData(
                number=1, comment="fuel",
                rows=[
                    MaterialRow(zaid="92235.06c", fraction="-0.05"),
                    MaterialRow(zaid="1001.06c", fraction="0.10"),
                    MaterialRow(kind="raw", text="#ifdef MOD1"),
                    MaterialRow(kind="raw", text="#endif"),
                ],
                formula="UO2", options="nlib=.66c", mt_card="lwtr.10t",
            ),
            MaterialData(
                number=2, comment="clad",
                rows=[MaterialRow(zaid="13027", fraction="1.0")],
                options="",
            ),
        ],
        sources=[
            SourceData(
                number=1, par="n", erg="14.0", pos_x="0", pos_y="0", pos_z="0",
                dir_="1", wgt="1.0", probability="0.6",
                cel="1", tme="0.0", vec="0 0 1", axs="0 0 1",
                rad="0.5", ext="0.0", sur="1", nrm="1", tr="1",
                ccc="1", ara="1.0", rate="1e6", sdef_extra="TME=0.0",
            ),
            SourceData(
                number=2, par="n", erg="2.0", pos_x="5", pos_y="5", pos_z="5",
                dir_="-1", wgt="0.5", probability="0.4",
                cel="2", tme="1.0", vec="1 0 0", axs="1 0 0",
                rad="1.0", ext="1.0", sur="2", nrm="-1", tr="2",
                ccc="2", ara="2.0", rate="2e6",
            ),
        ],
        tally=TallySettings(
            tallies=[
                TallyDefinition(type="F4", number=4, particles=["n", "p"],
                                params="1 2", generate_en=True, generate_tn=True,
                                fn_prefix="*", number_suffix=""),
                TallyDefinition(type="F1", number=1, particles=["n"],
                                params="1"),
            ],
            e_min="0.001", e_max="14", e_bins=100, e_log=True,
            e_cards_text="E4  1 2 3 4 5\nE1  0.1 1 10",
            t0_min="0.0", t0_max="100.0", t0_bins=50, t0_log=False,
            t_cards_text="T4  0 5 10\nT1  0 1 2",
            cut_n_t="100", cut_n_e="1e-4", cut_n_wc1="0.5", cut_n_wc2="0.25",
            cut_n_swtm="", cut_p_t="100", cut_p_e="0.01",
            cut_e_t="100", cut_e_e="0.01",
            cut_h_t="100", cut_h_e="0.01",
            cut_he_t="100", cut_he_e="0.01",
            cut_d_t="100", cut_d_e="0.01",
            cut_t_t="100", cut_t_e="0.01",
            cut_a_t="100", cut_a_e="0.01",
        ),
        adv=AdvancedSettings(
            other_cards="MPHYS  1\nDBCN  28j  0  13j  0",
            phys_n_emax="100", phys_n_emcnf="0.1", phys_n_iunr="1",
            phys_n_dnb="-1", phys_n_fisnu="1",
            phys_p_emcpf="50", phys_p_ides="1", phys_p_nocoh="1",
            phys_p_ispn="-1", phys_p_nodop="1",
            phys_e_emax="100", phys_e_ides="1", phys_e_iphoto="1",
            phys_e_ibad="1", phys_e_istrg="1", phys_e_bnum="0.5",
            phys_e_xnum="1.5", phys_e_rnok="1", phys_e_enum="32",
            phys_e_numb="1",
            phys_h_emax="100", phys_h_ie="1", phys_h_ipr="1",
            phys_h_rgas="1", phys_h_emin="0.01", phys_h_ecut="0.1",
            phys_he_emax="100", phys_he_ie="1", phys_he_ipr="1",
            phys_he_rgas="1", phys_he_emin="0.01", phys_he_ecut="0.1",
            source_mode="fixed",
            sdef_par="", sdef_erg="", sdef_pos_x="", sdef_pos_y="", sdef_pos_z="",
            sdef_wgt="", sdef_dir="", sdef_cel="", sdef_tme="", sdef_vec="",
            sdef_axs="", sdef_rad="", sdef_ext="", sdef_sur="", sdef_nrm="",
            sdef_tr="", sdef_ccc="", sdef_ara="", sdef_rate="", sdef_extra="",
            kcode_nsrc="1000", kcode_rkk="1.0", kcode_ikz="30", kcode_kct="100",
            kcode_knrm="1", kcode_msrk="", kcode_mrkp="", kcode_kc8="",
            ksrc_points='[{"x": 0, "y": 0, "z": 0}, {"x": 1, "y": 1, "z": 1}]',
            ssw_surf="1", ssw_sym="1", ssw_pty="N", ssw_cel="1 2",
            ssr_surf="2", ssr_mode="old", ssr_cel="2", ssr_pty="N",
            ssr_col="3", ssr_wgt="1.0", ssr_tr="1", ssr_psc="1",
            hsrc_enabled=True, hsrc_text="3 0 1 10 -10 10 10",
        ),
    )
    return deck
