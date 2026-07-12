"""
INP 解析器包 — 将 MCNP 输入卡解析为 DeckData
INP Parser Package — Parse MCNP input cards into DeckData data model.

This package provides the public API (parse_inp_text) for parsing raw MCNP input
text into structured DeckData, BasicSettings, TallySettings, and AdvancedSettings objects.
It coordinates sub-modules for line normalization, section splitting, and core parsing.
"""
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
                "nps": "", "ctme": "", "nonu": False,
                "materials": [], "sources": [], "tallies": {},
                "other_cards": [], "e0_values": [], "warnings": [],
                "source_mode": "fixed", "sdef_raw_text": ""}

    # Build BasicSettings: title, particle modes, NPS/CTME, and NONU (inverted as phys_fis)
    basic = BasicSettings(
        title=title, mode_n=data["mode_n"], mode_p=data["mode_p"],
        mode_e=data["mode_e"], mode_h=data["mode_h"],
        mode_he=data["mode_he"], nps=data["nps"], ctme=data["ctme"],
        phys_fis=not data["nonu"],
    )

    # Process tally data and E0 energy grid
    tally_raw = data["tallies"]
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
    # Build TallySettings: tally enable flags, surface/cell attachments, CUT parameters
    tally = TallySettings(
        f1_enabled=tally_raw.get("f1_enabled", False),
        f1_surface=tally_raw.get("f1_surface", ""),
        f2_enabled=tally_raw.get("f2_enabled", False),
        f2_surface=tally_raw.get("f2_surface", ""),
        f4_enabled=tally_raw.get("f4_enabled", False),
        f4_cell=tally_raw.get("f4_cell", ""),
        f5_enabled=tally_raw.get("f5_enabled", False),
        f5_x=tally_raw.get("f5_x", ""),
        f5_y=tally_raw.get("f5_y", ""),
        f5_z=tally_raw.get("f5_z", ""),
        f6_enabled=tally_raw.get("f6_enabled", False),
        f6_cell=tally_raw.get("f6_cell", ""),
        f7_enabled=tally_raw.get("f7_enabled", False),
        f7_cell=tally_raw.get("f7_cell", ""),
        f8_enabled=tally_raw.get("f8_enabled", False),
        f8_cell=tally_raw.get("f8_cell", ""),
        cut_n_t=tally_raw.get("cut_n_t", ""), cut_n_e=tally_raw.get("cut_n_e", ""),
        cut_n_raw=tally_raw.get("cut_n_raw", ""),
        cut_n_wgt=tally_raw.get("cut_n_wgt", ""),
        cut_n_tmc=tally_raw.get("cut_n_tmc", ""),
        cut_n_wc1=tally_raw.get("cut_n_wc1", ""),
        cut_n_wc2=tally_raw.get("cut_n_wc2", ""),
        cut_p_t=tally_raw.get("cut_p_t", ""), cut_p_e=tally_raw.get("cut_p_e", ""),
        cut_p_raw=tally_raw.get("cut_p_raw", ""),
        cut_p_wgt=tally_raw.get("cut_p_wgt", ""),
        cut_p_tmc=tally_raw.get("cut_p_tmc", ""),
        cut_p_wc1=tally_raw.get("cut_p_wc1", ""),
        cut_p_wc2=tally_raw.get("cut_p_wc2", ""),
        cut_e_t=tally_raw.get("cut_e_t", ""), cut_e_e=tally_raw.get("cut_e_e", ""),
        cut_e_raw=tally_raw.get("cut_e_raw", ""),
        cut_e_wgt=tally_raw.get("cut_e_wgt", ""),
        cut_e_tmc=tally_raw.get("cut_e_tmc", ""),
        cut_e_wc1=tally_raw.get("cut_e_wc1", ""),
        cut_e_wc2=tally_raw.get("cut_e_wc2", ""),
        cut_h_t=tally_raw.get("cut_h_t", ""),
        cut_h_e=tally_raw.get("cut_h_e", ""),
        cut_h_raw=tally_raw.get("cut_h_raw", ""),
        cut_h_wgt=tally_raw.get("cut_h_wgt", ""),
        cut_h_tmc=tally_raw.get("cut_h_tmc", ""),
        cut_h_wc1=tally_raw.get("cut_h_wc1", ""),
        cut_h_wc2=tally_raw.get("cut_h_wc2", ""),
        cut_he_t=tally_raw.get("cut_he_t", ""),
        cut_he_e=tally_raw.get("cut_he_e", ""),
        cut_he_raw=tally_raw.get("cut_he_raw", ""),
        cut_he_wgt=tally_raw.get("cut_he_wgt", ""),
        cut_he_tmc=tally_raw.get("cut_he_tmc", ""),
        cut_he_wc1=tally_raw.get("cut_he_wc1", ""),
        cut_he_wc2=tally_raw.get("cut_he_wc2", ""),
        **e0_data,
    )

    # Build AdvancedSettings: PHYS cards, SDEF source distribution, and other uncategorized cards
    adv = AdvancedSettings(
        other_cards="\n".join(data["other_cards"]),
        phys_n_emax=data.get("phys_n_emax", ""),
        phys_n_ie=data.get("phys_n_ie", ""),
        phys_n_nubar=data.get("phys_n_nubar", ""),
        phys_n_rgas=data.get("phys_n_rgas", ""),
        phys_n_idm=data.get("phys_n_idm", ""),
        phys_p_emin=data.get("phys_p_emin", ""),
        phys_p_isnp=data.get("phys_p_isnp", ""),
        phys_p_ff=data.get("phys_p_ff", ""),
        phys_e_emin=data.get("phys_e_emin", ""),
        phys_e_isne=data.get("phys_e_isne", ""),
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
