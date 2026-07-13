"""
INP 解析器包 — 将 MCNP 输入卡解析为 DeckData
INP Parser Package — Parse MCNP input cards into DeckData data model.

This package provides the public API (parse_inp_text) for parsing raw MCNP input
text into structured DeckData, BasicSettings, TallySettings, and AdvancedSettings objects.
It coordinates sub-modules for line normalization, section splitting, and core parsing.
"""
import json

from app.models import BasicSettings, TallySettings, AdvancedSettings, DeckData

from .lines import normalize_lines
from .sections import split_sections
from .core import parse_cells, parse_surfaces, parse_data_cards


def parse_inp_text(text: str) -> tuple[DeckData, list[str]]:
    """
    解析 MCNP 输入卡文本 → (DeckData, warnings)
    Parse raw MCNP input card text and return structured data plus any warnings.

    This is the main entry point for parsing. It normalizes lines, splits them
    into sections (title, cells, surfaces, data), then delegates to sub-parsers.

    Args:
        text: Raw MCNP input file content as a string.

    Returns:
        A tuple of (DeckData, warnings_list). DeckData holds the fully structured
        model data; warnings_list contains non-fatal error messages encountered
        during parsing (e.g., malformed cards that were skipped).
    """
    warnings = []

    # Step 1: Normalize lines — strip comments, merge continuations, etc.
    lines = normalize_lines(text)
    # Step 2: Split into title, cell lines, surface lines, and data card lines.
    title, cell_lines, surf_lines, data_lines = split_sections(lines)

    try:
        # Parse cell cards (e.g., "1 1 -1.0 -1 imp:n=1")
        cells = parse_cells(cell_lines)
    except Exception as e:
        warnings.append(f"栅元卡解析异常: {e}，已跳过")
        # If cells fail, return empty list so the caller still gets a usable result
        cells = []

    try:
        # Parse surface cards (e.g., "1 PZ 10")
        surfaces = parse_surfaces(surf_lines)
    except Exception as e:
        warnings.append(f"曲面卡解析异常: {e}")
        surfaces = ""

    try:
        # Parse data cards (MODE, NPS, SDEF, materials, tallies, PHYS cards, etc.)
        data = parse_data_cards(data_lines)
        if data.get("warnings"):
            warnings.extend(data["warnings"])
    except Exception as e:
        warnings.append(f"数据卡解析异常: {e}")
        # Provide safe defaults so the UI can still function
        data = {"mode_n": False, "mode_p": False, "mode_e": False,
                "mode_h": False, "mode_he": False,
                "mode_d": False, "mode_t": False, "mode_a": False,
                "nps": "", "ctme": "", "nonu": False,
                "materials": [], "sources": [], "tallies": {},
                "other_cards": [], "e0_values": [], "warnings": [],
                "source_mode": "fixed", "sdef_raw_text": ""}

    # Build BasicSettings: title, particle modes, NPS/CTME, and NONU (inverted as phys_fis)
    basic = BasicSettings(
        title=title, mode_n=data["mode_n"], mode_p=data["mode_p"],
        mode_e=data["mode_e"], mode_h=data["mode_h"],
        mode_he=data["mode_he"], nps=data["nps"], ctme=data["ctme"],
        mode_d=data.get("mode_d", False),
        mode_t=data.get("mode_t", False),
        mode_a=data.get("mode_a", False),
        phys_fis=not data["nonu"],
    )

    # Process tally data (TallyDefinition list) and E0 energy grid
    tally_defs = data.get("tally_defs", [])
    e_cards_text = "\n".join(data.get("e_cards_lines", []))
    e0_vals = data["e0_values"]
    e0_data = {}
    if data.get("e0_parametric"):
        # MCNP parametric syntax (nlog/nlin/nI) — use standard E0 fields, not custom grid
        e0_data = {
            "e_min": str(data["e0_min"]),
            "e_max": str(data["e0_max"]),
            "e_bins": int(data["e0_bins"]),
            "e_log": bool(data["e0_log"]),
            "e_custom_enabled": False,
            "e_custom_text": "",
        }
    elif e0_vals and len(e0_vals) >= 2:
        # Explicit E0 values (custom energy grid) — populate custom text field
        e0_data = {
            "e_custom_enabled": True,
            "e_custom_text": "\n".join(str(v) for v in e0_vals),
            "e_min": str(e0_vals[0]) if e0_vals else "0.001",
            "e_max": str(e0_vals[-1]) if e0_vals else "14",
            "e_bins": len(e0_vals) - 1,
        }

    # CUT fields still come from data["tallies"] dict
    tally_raw = data["tallies"]

    # Build TallySettings: TallyDefinition list + CUT parameters
    tally = TallySettings(
        tallies=tally_defs,
        e_cards_text=e_cards_text,
        cut_n_t=tally_raw.get("cut_n_t", ""), cut_n_e=tally_raw.get("cut_n_e", ""),
        cut_n_raw=tally_raw.get("cut_n_raw", ""),
        cut_n_wc1=tally_raw.get("cut_n_wc1", ""),
        cut_n_wc2=tally_raw.get("cut_n_wc2", ""),
        cut_n_swtm=tally_raw.get("cut_n_swtm", ""),
        cut_p_t=tally_raw.get("cut_p_t", ""), cut_p_e=tally_raw.get("cut_p_e", ""),
        cut_p_raw=tally_raw.get("cut_p_raw", ""),
        cut_p_wc1=tally_raw.get("cut_p_wc1", ""),
        cut_p_wc2=tally_raw.get("cut_p_wc2", ""),
        cut_p_swtm=tally_raw.get("cut_p_swtm", ""),
        cut_e_t=tally_raw.get("cut_e_t", ""), cut_e_e=tally_raw.get("cut_e_e", ""),
        cut_e_raw=tally_raw.get("cut_e_raw", ""),
        cut_e_wc1=tally_raw.get("cut_e_wc1", ""),
        cut_e_wc2=tally_raw.get("cut_e_wc2", ""),
        cut_e_swtm=tally_raw.get("cut_e_swtm", ""),
        cut_h_t=tally_raw.get("cut_h_t", ""),
        cut_h_e=tally_raw.get("cut_h_e", ""),
        cut_h_raw=tally_raw.get("cut_h_raw", ""),
        cut_h_wc1=tally_raw.get("cut_h_wc1", ""),
        cut_h_wc2=tally_raw.get("cut_h_wc2", ""),
        cut_h_swtm=tally_raw.get("cut_h_swtm", ""),
        cut_he_t=tally_raw.get("cut_he_t", ""),
        cut_he_e=tally_raw.get("cut_he_e", ""),
        cut_he_raw=tally_raw.get("cut_he_raw", ""),
        cut_he_wc1=tally_raw.get("cut_he_wc1", ""),
        cut_he_wc2=tally_raw.get("cut_he_wc2", ""),
        cut_he_swtm=tally_raw.get("cut_he_swtm", ""),
        cut_d_t=tally_raw.get("cut_d_t", ""),
        cut_d_e=tally_raw.get("cut_d_e", ""),
        cut_d_raw=tally_raw.get("cut_d_raw", ""),
        cut_d_wc1=tally_raw.get("cut_d_wc1", ""),
        cut_d_wc2=tally_raw.get("cut_d_wc2", ""),
        cut_d_swtm=tally_raw.get("cut_d_swtm", ""),
        cut_t_t=tally_raw.get("cut_t_t", ""),
        cut_t_e=tally_raw.get("cut_t_e", ""),
        cut_t_raw=tally_raw.get("cut_t_raw", ""),
        cut_t_wc1=tally_raw.get("cut_t_wc1", ""),
        cut_t_wc2=tally_raw.get("cut_t_wc2", ""),
        cut_t_swtm=tally_raw.get("cut_t_swtm", ""),
        cut_a_t=tally_raw.get("cut_a_t", ""),
        cut_a_e=tally_raw.get("cut_a_e", ""),
        cut_a_raw=tally_raw.get("cut_a_raw", ""),
        cut_a_wc1=tally_raw.get("cut_a_wc1", ""),
        cut_a_wc2=tally_raw.get("cut_a_wc2", ""),
        cut_a_swtm=tally_raw.get("cut_a_swtm", ""),
        **e0_data,
    )

    # Build AdvancedSettings: PHYS cards, SDEF source distribution, and other uncategorized cards
    adv = AdvancedSettings(
        other_cards="\n".join(data["other_cards"]),
        phys_n_emax=data.get("phys_n_emax", ""),
        phys_n_emcnf=data.get("phys_n_emcnf", ""),
        phys_n_iunr=data.get("phys_n_iunr", ""),
        phys_n_dnb=data.get("phys_n_dnb", ""),
        phys_n_fisnu=data.get("phys_n_fisnu", ""),
        phys_p_emcpf=data.get("phys_p_emcpf", ""),
        phys_p_ides=data.get("phys_p_ides", ""),
        phys_p_nocoh=data.get("phys_p_nocoh", ""),
        phys_p_ispn=data.get("phys_p_ispn", ""),
        phys_p_nodop=data.get("phys_p_nodop", ""),
        phys_e_emax=data.get("phys_e_emax", ""),
        phys_e_ides=data.get("phys_e_ides", ""),
        phys_e_iphoto=data.get("phys_e_iphoto", ""),
        phys_e_ibad=data.get("phys_e_ibad", ""),
        phys_e_istrg=data.get("phys_e_istrg", ""),
        phys_e_bnum=data.get("phys_e_bnum", ""),
        phys_e_xnum=data.get("phys_e_xnum", ""),
        phys_e_rnok=data.get("phys_e_rnok", ""),
        phys_e_enum=data.get("phys_e_enum", ""),
        phys_e_numb=data.get("phys_e_numb", ""),
        phys_h_emax=data.get("phys_h_emax", ""),
        phys_h_ie=data.get("phys_h_ie", ""),
        phys_h_ipr=data.get("phys_h_ipr", ""),
        phys_h_rgas=data.get("phys_h_rgas", ""),
        phys_h_emin=data.get("phys_h_emin", ""),
        phys_h_ecut=data.get("phys_h_ecut", ""),
        phys_he_emax=data.get("phys_he_emax", ""),
        phys_he_ie=data.get("phys_he_ie", ""),
        phys_he_ipr=data.get("phys_he_ipr", ""),
        phys_he_rgas=data.get("phys_he_rgas", ""),
        phys_he_emin=data.get("phys_he_emin", ""),
        phys_he_ecut=data.get("phys_he_ecut", ""),
        # KCODE/KSRC 临界源
        kcode_nsrc=data.get("kcode_nsrc", ""),
        kcode_rkk=data.get("kcode_rkk", ""),
        kcode_ikz=data.get("kcode_ikz", ""),
        kcode_kct=data.get("kcode_kct", ""),
        kcode_knrm=data.get("kcode_knrm", ""),
        ksrc_points=json.dumps(data.get("ksrc_points", [])),
        # SDEF 分布源模式
        source_mode=data.get("source_mode", "fixed"),
        sdef_par=data.get("sdef_par", ""),
        sdef_erg=data.get("sdef_erg", ""),
        sdef_pos_x=data.get("sdef_pos_x", ""),
        sdef_pos_y=data.get("sdef_pos_y", ""),
        sdef_pos_z=data.get("sdef_pos_z", ""),
        sdef_wgt=data.get("sdef_wgt", ""),
        sdef_dir=data.get("sdef_dir", ""),
        sdef_cel=data.get("sdef_cel", ""),
        sdef_tme=data.get("sdef_tme", ""),
        sdef_vec=data.get("sdef_vec", ""),
        sdef_axs=data.get("sdef_axs", ""),
        sdef_rad=data.get("sdef_rad", ""),
        sdef_ext=data.get("sdef_ext", ""),
        sdef_sur=data.get("sdef_sur", ""),
        sdef_nrm=data.get("sdef_nrm", ""),
        sdef_tr=data.get("sdef_tr", ""),
        sdef_ccc=data.get("sdef_ccc", ""),
        sdef_ara=data.get("sdef_ara", ""),
        sdef_rate=data.get("sdef_rate", ""),
        sdef_extra=data.get("sdef_extra", ""),
        sdef_raw_text=data.get("sdef_raw_text", ""),
    )

    # Assemble the final DeckData object combining all parsed sections
    deck = DeckData(basic=basic, surfaces=surfaces, cells=cells,
                    materials=data["materials"], sources=data["sources"],
                    tally=tally, adv=adv)

    return deck, warnings
