"""
INP 生成器：使用 pymcnp 库构建 MCNP 数据卡，cells/surfaces 保留原始文本处理
"""

import json
import math
import re
from app.models import BasicSettings, CellData, MaterialData, SourceData, AdvancedSettings, DeckData, TallySettings


# ===== Cells & Surfaces: 保留原始文本 pass-through =====

def _generate_cells(cells: list[CellData]) -> list[str]:
    """生成栅元卡 — 空值不输出"""
    lines = []
    for cell in cells:
        mat = cell.material
        if " " in mat:
            mat = mat.split()[0]
        if mat.startswith("M") and len(mat) > 1 and mat[1:].isdigit():
            mat = mat[1:]

        density = "" if mat == "0" else cell.density

        # 只输出用户明确设置的参数
        params_parts = []
        if cell.imp_n:
            params_parts.append(f"IMP:N={cell.imp_n}")
        if cell.imp_p:
            params_parts.append(f"IMP:P={cell.imp_p}")
        if cell.imp_e:
            params_parts.append(f"IMP:E={cell.imp_e}")
        if cell.vol:
            params_parts.append(f"VOL={cell.vol}")
        if cell.pwt:
            params_parts.append(f"PWT={cell.pwt}")
        if cell.ext:
            params_parts.append(f"EXT={cell.ext}")
        if cell.fcl:
            params_parts.append(f"FCL={cell.fcl}")
        if cell.u:
            params_parts.append(f"U={cell.u}")
        if cell.fill:
            params_parts.append(f"FILL={cell.fill}")
        if cell.lat:
            params_parts.append(f"LAT={cell.lat}")
        if cell.trcl:
            params_parts.append(f"TRCL={cell.trcl}")
        params = "  " + "  ".join(params_parts) if params_parts else ""
        comment = f"  $ {cell.comment}" if cell.comment else ""

        core = f"{cell.number}  {mat}  {density}  {cell.surface_expr}"
        full_line = core + params + comment

        if len(full_line) > 80:
            lines.append(core)
            continuation = "     " + (params + comment).strip()
            lines.append(continuation.rstrip())
        else:
            lines.append(full_line.rstrip())

    return lines


def _generate_surfaces(surfaces_text: str) -> list[str]:
    """曲面卡文本（pass-through）"""
    if not surfaces_text:
        return []
    return [line.rstrip() for line in surfaces_text.split("\n") if line.strip()]


# ===== 数据卡：使用 pymcnp API =====

def _generate_basic(basic: BasicSettings) -> list[str]:
    """基本设置 → pymcnp Mode / Nps / Ctme / Nonu"""
    from pymcnp import inp as pymcnp_inp
    lines = []

    particles = []
    if basic.mode_n: particles.append('n')
    if basic.mode_p: particles.append('p')
    if basic.mode_e: particles.append('e')
    if basic.mode_h: particles.append('H')
    if basic.mode_he: particles.append('HE')
    if particles:
        # pymcnp 不识别 'HE'，手动生成 Mode 卡
        if basic.mode_he:
            lines.append(f'MODE  {" ".join(particles).upper()}')
        else:
            lines.append(str(pymcnp_inp.Mode(particles=particles)).upper())

    if basic.nps and basic.nps.strip():
        try:
            nps_int = int(float(basic.nps))
            lines.append(str(pymcnp_inp.Nps(npp=nps_int)).upper())
        except ValueError:
            lines.append(f"NPS  {basic.nps}")

    if basic.ctme and basic.ctme.strip():
        try:
            lines.append(str(pymcnp_inp.Ctme(tme=float(basic.ctme))).upper())
        except ValueError:
            lines.append(f"CTME  {basic.ctme}")

    if not basic.phys_fis:
        lines.append(str(pymcnp_inp.Nonu()).upper())
        lines.append("C  Fission turned off via NONU card")

    return lines


def _normalize_zaid(zaid: str) -> str:
    """将 ZAID 规范化为 ZZAAA 格式（不带前导零）。
    001001 → 1001, 008016 → 8016, 092235 → 92235
    """
    if "." in zaid:
        num_part, lib = zaid.split(".", 1)
        lib = "." + lib
    else:
        num_part, lib = zaid, ""
    stripped = num_part.lstrip("0") or "0"
    return stripped + lib


def _generate_materials(materials: list[MaterialData]) -> list[str]:
    """材料卡 → pymcnp M_0，附加 nlib= 等选项"""
    from pymcnp import inp as pymcnp_inp
    from pymcnp.types import Substance
    lines = []
    for mat in materials:
        if not mat.rows:
            continue

        if mat.comment:
            lines.append(f"C  Material {mat.number}: {mat.comment}")

        substances = [
            Substance(zaid=_normalize_zaid(row.zaid), weight_ratio=float(row.fraction))
            for row in mat.rows
        ]
        card = str(pymcnp_inp.M_0(substances=substances, suffix=mat.number)).upper()

        # 追加材料选项（nlib=, gas=, plib= 等）
        opts = getattr(mat, 'options', '') or ''
        if opts.strip():
            card += "  " + opts.strip()

        lines.append(card)

    return lines


def _generate_sdef(sources: list[SourceData]) -> list[str]:
    """源项卡 → pymcnp Sdef（单源）/ 手动 SI/SP（多源）"""
    if not sources:
        return []

    n_sources = len(sources)

    if n_sources == 1:
        return _generate_single_source(sources[0])
    else:
        return _generate_multi_source(sources)


def _is_d_ref(val: str) -> bool:
    """检查值是否为 Dn 分布引用（如 D1、D2）"""
    return bool(re.match(r'^D\d+$', val.strip().upper())) if val else False


def _generate_single_source(src: SourceData) -> list[str]:
    """单源：存在 Dn 引用时手写 SDEF，否则用 pymcnp Sdef"""
    from pymcnp import inp as pymcnp_inp
    has_d_or_extra = any(
        _is_d_ref(v) for v in [src.par, src.erg, src.dir_, src.wgt,
                               src.cel, src.tme, src.rad, src.ext, src.axs, src.vec]
    ) or any([src.sur, src.nrm, src.tr, src.ccc, src.ara, src.rate, src.sdef_extra])
    if has_d_or_extra:
        # ── Dn 引用 → 手写 SDEF 行 ──
        parts = ["SDEF"]
        if src.par: parts.append(f"PAR={src.par}")
        if src.erg: parts.append(f"ERG={src.erg}")
        pos_parts = []
        if src.pos_x: pos_parts.append(src.pos_x)
        if src.pos_y: pos_parts.append(src.pos_y)
        if src.pos_z: pos_parts.append(src.pos_z)
        if pos_parts:
            parts.append(f"POS={' '.join(pos_parts)}")
        if src.dir_: parts.append(f"DIR={src.dir_}")
        if src.wgt: parts.append(f"WGT={src.wgt}")
        if src.cel: parts.append(f"CEL={src.cel}")
        if src.tme: parts.append(f"TME={src.tme}")
        if src.vec: parts.append(f"VEC={src.vec}")
        if src.axs: parts.append(f"AXS={src.axs}")
        if src.rad: parts.append(f"RAD={src.rad}")
        if src.ext: parts.append(f"EXT={src.ext}")
        if src.sur: parts.append(f"SUR={src.sur}")
        if src.nrm: parts.append(f"NRM={src.nrm}")
        if src.tr: parts.append(f"TR={src.tr}")
        if src.ccc: parts.append(f"CCC={src.ccc}")
        if src.ara: parts.append(f"ARA={src.ara}")
        if src.rate: parts.append(f"RATE={src.rate}")
        if src.sdef_extra: parts.append(src.sdef_extra)
        return ["  ".join(parts)]

    # ── 正常数值 → 用 pymcnp ──
    options = []

    # PAR
    if src.par:
        options.append(pymcnp_inp.sdef.Par_0(src.par))

    # ERG
    if src.erg:
        options.append(pymcnp_inp.sdef.Erg_0(float(src.erg)))

    # POS
    pos_values = [src.pos_x, src.pos_y, src.pos_z]
    if any(v for v in pos_values):
        options.append(pymcnp_inp.sdef.Pos_0(
            float(src.pos_x) if src.pos_x else 0.0,
            float(src.pos_y) if src.pos_y else 0.0,
            float(src.pos_z) if src.pos_z else 0.0,
        ))

    # DIR
    if src.dir_:
        options.append(pymcnp_inp.sdef.Dir_0(float(src.dir_)))

    # CEL
    if src.cel:
        options.append(pymcnp_inp.sdef.Cel_0(int(src.cel)))

    # WGT
    if src.wgt:
        options.append(pymcnp_inp.sdef.Wgt_0(float(src.wgt)))

    # TME
    if src.tme:
        options.append(pymcnp_inp.sdef.Tme_0(float(src.tme)))

    # VEC
    if src.vec:
        vparts = src.vec.split()
        if len(vparts) >= 3:
            options.append(pymcnp_inp.sdef.Vec_0(
                float(vparts[0]), float(vparts[1]), float(vparts[2])
            ))

    # AXS
    if src.axs:
        aparts = src.axs.split()
        if len(aparts) >= 3:
            options.append(pymcnp_inp.sdef.Axs_0(
                float(aparts[0]), float(aparts[1]), float(aparts[2])
            ))

    # RAD
    if src.rad:
        options.append(pymcnp_inp.sdef.Rad_0(float(src.rad)))

    # EXT
    if src.ext:
        options.append(pymcnp_inp.sdef.Ext_0(float(src.ext)))

    return [str(pymcnp_inp.Sdef(options=options)).upper()]


def _generate_distribution_sdef(adv: AdvancedSettings) -> list[str]:
    """分布源模式：从结构化字段生成 SDEF + 反序列化 SI/SP 文本"""
    parts = ["SDEF"]
    if adv.sdef_par: parts.append(f"PAR={adv.sdef_par}")
    if adv.sdef_erg: parts.append(f"ERG={adv.sdef_erg}")
    pos_parts = []
    if adv.sdef_pos_x: pos_parts.append(adv.sdef_pos_x)
    if adv.sdef_pos_y: pos_parts.append(adv.sdef_pos_y)
    if adv.sdef_pos_z: pos_parts.append(adv.sdef_pos_z)
    if pos_parts:
        parts.append(f"POS={' '.join(pos_parts)}")
    if adv.sdef_wgt: parts.append(f"WGT={adv.sdef_wgt}")
    if adv.sdef_dir: parts.append(f"DIR={adv.sdef_dir}")
    if adv.sdef_cel: parts.append(f"CEL={adv.sdef_cel}")
    if adv.sdef_tme: parts.append(f"TME={adv.sdef_tme}")
    if adv.sdef_vec: parts.append(f"VEC={adv.sdef_vec}")
    if adv.sdef_axs: parts.append(f"AXS={adv.sdef_axs}")
    if adv.sdef_rad: parts.append(f"RAD={adv.sdef_rad}")
    if adv.sdef_ext: parts.append(f"EXT={adv.sdef_ext}")
    if adv.sdef_sur: parts.append(f"SUR={adv.sdef_sur}")
    if adv.sdef_nrm: parts.append(f"NRM={adv.sdef_nrm}")
    if adv.sdef_tr: parts.append(f"TR={adv.sdef_tr}")
    if adv.sdef_ccc: parts.append(f"CCC={adv.sdef_ccc}")
    if adv.sdef_ara: parts.append(f"ARA={adv.sdef_ara}")
    if adv.sdef_rate: parts.append(f"RATE={adv.sdef_rate}")
    if adv.sdef_extra: parts.append(adv.sdef_extra)

    lines = ["  ".join(parts)]

    # 反序列化 SI/SP 对，自动加回 SI{n}/SP{n} 前缀
    if adv.sdef_raw_text:
        try:
            pairs = json.loads(adv.sdef_raw_text)
            for idx, pair in enumerate(pairs, 1):
                si = pair.get("si", "").strip()
                sp = pair.get("sp", "").strip()
                if si:
                    # 内容可能已不含 SI{n} 前缀（UI 标签已显示索引），自动补全
                    if not re.match(r'^SI\d+', si, re.IGNORECASE):
                        si = f"SI{idx}  {si}"
                    lines.append(si)
                if sp:
                    if not re.match(r'^SP\d+', sp, re.IGNORECASE):
                        sp = f"SP{idx}  {sp}"
                    lines.append(sp)
        except (json.JSONDecodeError, TypeError):
            pass

    return lines


def _generate_multi_source(sources: list[SourceData]) -> list[str]:
    """
    多源：手动生成 SDEF + SI/SP 分布卡。
    保留此逻辑是因为 pymcnp 的 SI/SP 机制需要逐卡构造，
    且多源之间的 Dn 键控关联由我们精确控制更可靠。
    """
    lines = []
    n_sources = len(sources)

    par_list = [src.par for src in sources]
    erg_list = [src.erg for src in sources]
    pos_x_list = [src.pos_x for src in sources]
    pos_y_list = [src.pos_y for src in sources]
    pos_z_list = [src.pos_z for src in sources]
    dir_list = [src.dir_ for src in sources]
    wgt_list = [src.wgt for src in sources]
    cel_list = [src.cel for src in sources]
    tme_list = [src.tme for src in sources]
    vec_list = [src.vec for src in sources]
    axs_list = [src.axs for src in sources]
    rad_list = [src.rad for src in sources]
    ext_list = [src.ext for src in sources]
    sur_list = [src.sur for src in sources]
    nrm_list = [src.nrm for src in sources]
    tr_list = [src.tr for src in sources]
    ccc_list = [src.ccc for src in sources]
    ara_list = [src.ara for src in sources]
    rate_list = [src.rate for src in sources]
    prob_list = [src.probability if src.probability else '1' for src in sources]

    # 归一化概率
    try:
        prob_floats = [float(p) for p in prob_list]
    except ValueError as e:
        raise ValueError(f"多源概率格式错误：{e}") from e
    total_prob = sum(prob_floats)
    if total_prob <= 0:
        prob_norm = [f"{1.0 / n_sources:.6f}" for _ in sources]
    else:
        prob_norm = [f"{p / total_prob:.6f}" for p in prob_floats]

    # POS 跨源是否不同
    pos_differ = any(
        (pos_x_list[i] != pos_x_list[0] or
         pos_y_list[i] != pos_y_list[0] or
         pos_z_list[i] != pos_z_list[0])
        for i in range(1, n_sources)
    )

    # 收集需要分布的参数
    dist_params = []

    def add_dist(param_name, values):
        if len(set(values)) > 1:
            dist_params.append((param_name, values))

    add_dist("PAR", par_list)
    add_dist("ERG", erg_list)
    add_dist("DIR", dir_list)
    add_dist("WGT", wgt_list)
    add_dist("CEL", cel_list)
    add_dist("TME", tme_list)
    add_dist("VEC", vec_list)
    add_dist("AXS", axs_list)
    add_dist("RAD", rad_list)
    add_dist("EXT", ext_list)
    add_dist("SUR", sur_list)
    add_dist("NRM", nrm_list)
    add_dist("TR", tr_list)
    add_dist("CCC", ccc_list)
    add_dist("ARA", ara_list)
    add_dist("RATE", rate_list)

    # SDEF 行
    sdef_parts = []
    di = 1
    dist_names = {d[0] for d in dist_params}

    if pos_differ:
        vec_entries = [
            f"{pos_x_list[i]} {pos_y_list[i]} {pos_z_list[i]}"
            for i in range(n_sources)
        ]
        sdef_parts.append(f"POS=F D{di}")
        dist_params.insert(0, ("POS_VEC", vec_entries))
        di += 1
    elif any([pos_x_list[0], pos_y_list[0], pos_z_list[0]]):
        sdef_parts.append(f"POS={pos_x_list[0]} {pos_y_list[0]} {pos_z_list[0]}")

    for pn, default, vals in [
        ("PAR", par_list[0], par_list),
        ("ERG", erg_list[0], erg_list),
        ("DIR", dir_list[0], dir_list),
        ("WGT", wgt_list[0], wgt_list),
    ]:
        if pn in dist_names:
            sdef_parts.append(f"{pn}=D{di}"); di += 1
        elif pn == "ERG" and default:
            sdef_parts.append(f"ERG={default}")
        elif pn == "DIR" and default:
            sdef_parts.append(f"DIR={default}")
        elif pn == "WGT":
            sdef_parts.append(f"WGT={default}")
        elif pn == "PAR":
            sdef_parts.append(f"PAR={default}")

    for pn in ("CEL", "TME", "VEC", "AXS", "RAD", "EXT",
               "SUR", "NRM", "TR", "CCC", "ARA", "RATE"):
        vals = {"CEL": cel_list, "TME": tme_list, "VEC": vec_list,
                "AXS": axs_list, "RAD": rad_list, "EXT": ext_list,
                "SUR": sur_list, "NRM": nrm_list, "TR": tr_list,
                "CCC": ccc_list, "ARA": ara_list, "RATE": rate_list}[pn]
        if pn in dist_names:
            sdef_parts.append(f"{pn}=D{di}"); di += 1
        elif vals[0]:
            sdef_parts.append(f"{pn}={vals[0]}")

    # 多源共用同一份 sdef_extra（取第一个源）
    if sources and sources[0].sdef_extra:
        sdef_parts.append(sources[0].sdef_extra)

    lines.append("SDEF  " + "  ".join(sdef_parts))

    # SI/SP 卡
    si_di = 1
    first_dist = True
    for param_name, values in dist_params:
        if param_name == "POS_VEC":
            lines.append(f"SI{si_di}  V  {'  '.join(values)}")
        else:
            lines.append(f"SI{si_di}  L  {'  '.join(values)}")
        if first_dist:
            lines.append(f"SP{si_di}  {'  '.join(prob_norm)}")
            first_dist = False
        else:
            lines.append(f"SP{si_di}  D1")
        si_di += 1

    if dist_params:
        lines.append(f"C  {n_sources} sources, probability keyed to D1")

    return lines


def _particle_for_mode(basic: BasicSettings) -> str:
    """由 MODE 决定计数卡粒子标识符"""
    if basic.mode_n:
        return "n"
    elif basic.mode_p:
        return "p"
    elif basic.mode_e:
        return "e"
    elif basic.mode_h:
        return "h"
    elif basic.mode_he:
        return "he"
    return "n"


def _generate_tallies(tally: TallySettings, particle: str) -> list[str]:
    """计数卡 → pymcnp F_0 / E"""
    from pymcnp import inp as pymcnp_inp
    any_enabled = any([
        tally.f1_enabled, tally.f2_enabled, tally.f4_enabled,
        tally.f5_enabled, tally.f6_enabled, tally.f7_enabled,
        tally.f8_enabled,
    ])
    if not any_enabled:
        return []

    lines = ["C  Tallies"]

    # --- F1-F7 (pymcnp F_0 支持) ---
    for enabled, suffix, value, desc in [
        (tally.f1_enabled, 1, tally.f1_surface, "Surface current (particles)"),
        (tally.f2_enabled, 2, tally.f2_surface, "Surface flux (particles/cm2)"),
        (tally.f4_enabled, 4, tally.f4_cell,   "Cell flux (particles/cm2)"),
        (tally.f6_enabled, 6, tally.f6_cell,   "Energy deposition (MeV/g)"),
        (tally.f7_enabled, 7, tally.f7_cell,   "Fission energy deposition (MeV/g)"),
    ]:
        if enabled and value.strip():
            clean = value.strip().strip("()")
            problems = [int(v) for v in clean.replace(",", " ").split() if v.lstrip('-').isdigit()]
            if problems:
                card = str(pymcnp_inp.F_0(
                    suffix=suffix, designator=particle, problems=problems
                )).upper()
                lines.append(f"{card}   $ {desc}")

    # F5 点探测器（坐标）— 手写（pymcnp F_0 不支持）
    if tally.f5_enabled:
        lines.append(
            f"F5:{particle.upper()}  {tally.f5_x}  {tally.f5_y}  {tally.f5_z}"
            f"   $ Point detector (particles/cm2)"
        )

    # F8 脉冲高度 — 手写（pymcnp F_0 不支持 suffix=8）
    if tally.f8_enabled and tally.f8_cell.strip():
        clean = tally.f8_cell.strip().strip("()")
        problems = [int(v) for v in clean.replace(",", " ").split() if v.lstrip('-').isdigit()]
        if problems:
            cell_str = " ".join(str(p) for p in problems)
            lines.append(f"F8:{particle.upper()}  {cell_str}   $ Pulse height distribution")

    # E0 能谱网格（仅在有 F 计数时生成）
    e0_lines = _generate_energy_mesh(tally)
    lines.extend(e0_lines)

    return lines


def _compress_j_skip(fields: list[str]) -> str:
    """将字段列表压缩为 j-skip 语法。
    尾部连续空→截断，前导连续空→nJ，中间空→J。
    例: ["","","0","0"] → "2J 0 0"
    """
    while fields and not fields[-1]:
        fields.pop()
    if not fields:
        return ""
    lead = 0
    while lead < len(fields) and not fields[lead]:
        lead += 1
    parts = []
    if lead == 1:
        parts.append("J")
    elif lead > 1:
        parts.append(f"{lead}J")
    for f in fields[lead:]:
        parts.append("J" if not f else f)
    return " ".join(parts)


def _generate_cut(tally: TallySettings) -> list[str]:
    """CUT:N/P/E 截断 — 从 6 个字段压缩 j-skip 后输出"""
    lines = []
    for designator, field_names in [
        ('n', ['cut_n_t', 'cut_n_e', 'cut_n_wgt', 'cut_n_tmc', 'cut_n_wc1', 'cut_n_wc2']),
        ('p', ['cut_p_t', 'cut_p_e', 'cut_p_wgt', 'cut_p_tmc', 'cut_p_wc1', 'cut_p_wc2']),
        ('e', ['cut_e_t', 'cut_e_e', 'cut_e_wgt', 'cut_e_tmc', 'cut_e_wc1', 'cut_e_wc2']),
        ('h', ['cut_h_t', 'cut_h_e', 'cut_h_wgt', 'cut_h_tmc', 'cut_h_wc1', 'cut_h_wc2']),
        ('he', ['cut_he_t', 'cut_he_e', 'cut_he_wgt', 'cut_he_tmc', 'cut_he_wc1', 'cut_he_wc2']),
    ]:
        values = [getattr(tally, f, '') or '' for f in field_names]
        compact = _compress_j_skip(values)
        if compact:
            lines.append(f"CUT:{designator.upper()}  {compact}")
    return lines


def _generate_energy_mesh(tally: TallySettings) -> list[str]:
    """生成 E0 能谱网格 — 空值跳过"""
    from pymcnp import inp as pymcnp_inp
    lines = []

    # 数值格式化：去掉多余的尾随零
    def _fmt(v: float) -> str:
        s = f"{v:.7g}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s

    if tally.e_custom_enabled and tally.e_custom_text.strip():
        custom_values = []
        for raw_line in tally.e_custom_text.strip().split("\n"):
            val = raw_line.strip()
            if val:
                try:
                    custom_values.append(float(val))
                except ValueError:
                    pass
        if len(custom_values) >= 2:
            lines.append(str(pymcnp_inp.E(suffix=0, bounds=custom_values)).upper())
            lines.append(f"C  Energy mesh: {len(custom_values)} user-defined points")
        else:
            lines.append("C  Energy mesh: custom grid skipped — need at least 2 energy values")
    else:
        if not tally.e_min or not tally.e_max or not tally.e_bins:
            return lines  # 空值 → 不生成 E0
        try:
            e_min = float(tally.e_min)
            e_max = float(tally.e_max)
            n_bins = tally.e_bins

            if n_bins > 0 and e_max > e_min:
                if tally.e_log:
                    # E0  e_min n_binslog e_max  (MCNP 对数间隔语法)
                    lines.append(
                        f"E0    {_fmt(e_min)} {n_bins}log {_fmt(e_max)}"
                    )
                else:
                    # E0  e_min n_binsi e_max  (MCNP 线性间隔语法)
                    lines.append(
                        f"E0    {_fmt(e_min)} {n_bins}i {_fmt(e_max)}"
                    )
                grid_type = "LOG" if tally.e_log else "LINEAR"
                lines.append(f"C  Energy mesh: {n_bins} {grid_type} intervals, {_fmt(e_min)} to {_fmt(e_max)} MeV")

        except (ValueError, ZeroDivisionError):
            lines.append("C  Energy mesh: invalid parameters, skipped")

    return lines


def _generate_advanced(adv: AdvancedSettings) -> list[str]:
    """高级设置：PHYS 卡 + 用户手动输入的额外 MCNP 卡片"""
    lines = []

    # PHYS:N — 从结构化字段生成
    phys_n = [adv.phys_n_emax, adv.phys_n_ie, adv.phys_n_nubar,
              adv.phys_n_rgas, adv.phys_n_idm]
    compact = _compress_j_skip(list(phys_n))
    if compact:
        lines.append(f"PHYS:N  {compact}")

    # PHYS:P
    phys_p = [adv.phys_p_emin, adv.phys_p_isnp, adv.phys_p_ff]
    compact = _compress_j_skip(list(phys_p))
    if compact:
        lines.append(f"PHYS:P  {compact}")

    # PHYS:E
    phys_e = [adv.phys_e_emin, adv.phys_e_isne]
    compact = _compress_j_skip(list(phys_e))
    if compact:
        lines.append(f"PHYS:E  {compact}")

    # PHYS:H
    phys_h = [adv.phys_h_emax, adv.phys_h_ie, adv.phys_h_ipr,
              adv.phys_h_rgas, adv.phys_h_emin, adv.phys_h_ecut]
    compact = _compress_j_skip(list(phys_h))
    if compact:
        lines.append(f"PHYS:H  {compact}")

    # PHYS:HE
    phys_he = [adv.phys_he_emax, adv.phys_he_ie, adv.phys_he_ipr,
               adv.phys_he_rgas, adv.phys_he_emin, adv.phys_he_ecut]
    compact = _compress_j_skip(list(phys_he))
    if compact:
        lines.append(f"PHYS:HE  {compact}")

    # 其他手动卡片
    if adv.other_cards:
        lines.append("C  ===== Additional Cards (from Advanced tab) =====")
        for card in adv.other_cards.split("\n"):
            stripped = card.rstrip()
            if stripped:
                lines.append(stripped)
    return lines


# ===== 80 列换行修正 =====

def _wrap_long_lines(text: str) -> str:
    """
    后处理：确保所有行不超过 80 列（MCNP 严格要求）。
    对已含 & 续行符但超长的行做二次拆分。
    """
    result = []
    for line in text.split("\n"):
        line = line.rstrip()
        while len(line) > 80:
            # 暂时去掉末尾 &，找合适的空格拆分点，再加回 &
            has_cont = line.endswith("&")
            if has_cont:
                line = line[:-1].rstrip()

            # 在列 30-79 范围内找最后一个空格（优先在值之间拆分）
            split_at = line.rfind(" ", 30, 80)
            if split_at < 6:
                split_at = 78

            first = line[:split_at].rstrip() + " &"
            line = "     " + line[split_at:].strip()
            if has_cont:
                line = line + " &"

            result.append(first)
        result.append(line)
    return "\n".join(result)


# ===== 主入口 =====

def generate_inp_from_deck(deck: DeckData, raw_overrides: dict = None) -> str:
    """
    从 DeckData 聚合对象生成完整的 INP 文件内容。

    raw_overrides 可覆盖各模块的生成：
      {"cells": str, "surfaces": str, "materials": str,
       "sdef": str, "e0": str, "cut": str, "phys": str}
    有 override 时直接用文本行替代 _generate_* 的产出。

    MCNP 文件结构（严格顺序）：
        标题卡 → 栅元卡 → [空行] → 曲面卡 → [空行] → 数据卡
    """
    overrides = raw_overrides or {}
    basic = deck.basic
    cells = deck.cells
    surfaces_text = deck.surfaces
    materials = deck.materials
    sources = deck.sources
    tally = deck.tally or TallySettings()
    adv = deck.adv
    particle = _particle_for_mode(basic)

    lines = []

    # 1. 标题卡
    title = basic.title.strip() if basic.title else "MCNP Input Generated by MCNP Generator"
    lines.append(title)

    # 2. 栅元卡
    if "cells" in overrides:
        raw = overrides["cells"].strip()
        if raw:
            lines.append("C  Cell Cards (raw text mode)")
            lines.extend(raw.split("\n"))
    else:
        cell_lines = _generate_cells(cells)
        if cell_lines:
            lines.append(f"C  Cell Cards: {len(cells)} cells defined")
            lines.extend(cell_lines)
    lines.append("")

    # 3. 曲面卡
    if "surfaces" in overrides:
        raw = overrides["surfaces"].strip()
        if raw:
            lines.append("C  Surface Cards (raw text mode)")
            lines.extend(raw.split("\n"))
    else:
        surf_lines = _generate_surfaces(surfaces_text)
        if surf_lines:
            lines.append(f"C  Surface Cards: {len(surf_lines)} surfaces defined")
            lines.extend(surf_lines)
    lines.append("")

    # 4. 数据卡
    lines.append("C  ===== Data Cards =====")

    basic_lines = _generate_basic(basic)
    if basic_lines: lines.extend(basic_lines)

    if "materials" in overrides:
        raw = overrides["materials"].strip()
        if raw:
            lines.append("C  Materials (raw text mode)")
            lines.extend(raw.split("\n"))
    else:
        mat_lines = _generate_materials(materials)
        if mat_lines: lines.extend(mat_lines)

    if "sdef" in overrides:
        raw = overrides["sdef"].strip()
        if raw:
            lines.append("C  Source Definition (raw text mode)")
            lines.extend(raw.split("\n"))
    else:
        if adv.source_mode == "distribution" and adv.sdef_raw_text:
            sdef_lines = _generate_distribution_sdef(adv)
        else:
            sdef_lines = _generate_sdef(sources)
        if sdef_lines: lines.extend(sdef_lines)

    if "phys" in overrides:
        raw = overrides["phys"].strip()
        if raw:
            lines.append("C  PHYS Cards (raw text mode)")
            lines.extend(raw.split("\n"))
    else:
        adv_lines = _generate_advanced(adv)
        if adv_lines: lines.extend(adv_lines)

    tally_lines = _generate_tallies(tally, particle)
    if tally_lines: lines.extend(tally_lines)

    if "e0" in overrides:
        raw = overrides["e0"].strip()
        if raw:
            lines.append("C  Energy mesh (raw text mode)")
            lines.extend(raw.split("\n"))
    else:
        e0_lines = _generate_energy_mesh(tally)
        if e0_lines: lines.extend(e0_lines)

    if "cut" in overrides:
        raw = overrides["cut"].strip()
        if raw:
            lines.append("C  Particle Cutoffs (raw text mode)")
            lines.extend(raw.split("\n"))
    else:
        cut_lines = _generate_cut(tally)
        if cut_lines: lines.extend(cut_lines)

    lines.append("")
    raw = "\n".join(lines)
    return _wrap_long_lines(raw)
