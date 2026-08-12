"""
INP 生成器：使用 pymcnp 库构建 MCNP 数据卡，cells/surfaces 保留原始文本处理
"""

import json
import math
import re
from pymcnp import inp as pymcnp_inp
from app.models import (BasicSettings, CellData, CellRow, MaterialData, MaterialRow,
                        SourceData, AdvancedSettings, DeckData, TallySettings)
from .banners import (
    DATA_CARDS_BANNER, TALLIES_BANNER, TR_BANNER, KSRC_BANNER, HSRC_BANNER,
    KCODE_BANNER, KCODE_SKIPPED_BANNER, KSRC_FAILED_BANNER, FISSION_OFF_BANNER,
    RAW_CELL_BANNER, RAW_SURF_BANNER, RAW_MAT_BANNER, RAW_SDEF_BANNER,
    RAW_PHYS_BANNER, RAW_TALLY_BANNER, RAW_E0_BANNER, RAW_CUT_BANNER,
    ADDITIONAL_CARDS_BANNER, PER_TALLY_EN_BANNER, PER_TALLY_TN_BANNER,
    ENERGY_MESH_SKIP_BANNER, ENERGY_MESH_INVALID_BANNER,
    TIME_MESH_SKIP_BANNER, TIME_MESH_INVALID_BANNER,
    cell_cards_banner, surface_cards_banner, energy_mesh_banner,
    energy_mesh_custom_banner, time_mesh_banner, time_mesh_custom_banner,
    skipped_card_banner,
)


# ===== Cells & Surfaces: 保留原始文本 pass-through =====

def _dist_json_nonempty(dist_json: str) -> bool:
    """结构化分布 JSON 是否含有效条目（"[]"/空串 → False）"""
    if not dist_json or not dist_json.strip():
        return False
    try:
        arr = json.loads(dist_json)
        return isinstance(arr, list) and len(arr) > 0
    except (json.JSONDecodeError, TypeError):
        return False


def _generate_cells(cells: list[CellRow]) -> list[str]:
    """生成栅元卡 — 空值不输出；CellRow 可为 cell 或 raw 条件行"""
    lines = []
    for row in cells:
        if getattr(row, 'kind', 'cell') == "raw":
            lines.append(row.text)  # 原样条件行（#ifdef/#else/#endif…）
            continue
        cell = row.cell
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
        if cell.tmp and cell.tmp.strip():
            params_parts.append(f"TMP={cell.tmp}")
        if cell.other_params:
            params_parts.append(cell.other_params)
        params = "  " + "  ".join(params_parts) if params_parts else ""
        comment = f"  $ {cell.comment}" if cell.comment else ""

        core = f"{cell.number}  {mat}  {density}  {cell.surface_expr}"
        full_line = core + params + comment

        if len(full_line) > 80:
            lines.append(core)
            cont_content = (params + comment).strip()
            if cont_content:
                continuation = "     " + cont_content
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
    lines = []

    particles = []
    if basic.mode_n: particles.append('n')
    if basic.mode_p: particles.append('p')
    if basic.mode_e: particles.append('e')
    if basic.mode_h: particles.append('H')
    if basic.mode_he: particles.append('HE')
    if basic.mode_d: particles.append('D')
    if basic.mode_t: particles.append('T')
    if basic.mode_a: particles.append('A')
    if particles:
        # pymcnp 不识别 'HE'/'D'/'T'/'A'，手动生成 Mode 卡
        if basic.mode_he or basic.mode_d or basic.mode_t or basic.mode_a:
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

    if basic.act and basic.act.strip():
        lines.append(f"ACT  {basic.act}")

    if basic.print_pr and basic.print_pr.strip():
        lines.append(f"PRINT  {basic.print_pr}")

    if not basic.phys_fis:
        lines.append(str(pymcnp_inp.Nonu()).upper())
        lines.append(FISSION_OFF_BANNER)

    return lines


# 元素符号 → 原子序数（手动 ZAID 模式存的是 "U-235" 元素格式，生成时转 ZZZAA）
_ELEMENT_Z = {
    "H":1,"He":2,"Li":3,"Be":4,"B":5,"C":6,"N":7,"O":8,"F":9,"Ne":10,
    "Na":11,"Mg":12,"Al":13,"Si":14,"P":15,"S":16,"Cl":17,"Ar":18,
    "K":19,"Ca":20,"Sc":21,"Ti":22,"V":23,"Cr":24,"Mn":25,"Fe":26,
    "Co":27,"Ni":28,"Cu":29,"Zn":30,"Ga":31,"Ge":32,"As":33,"Se":34,
    "Br":35,"Kr":36,"Rb":37,"Sr":38,"Y":39,"Zr":40,"Nb":41,"Mo":42,
    "Tc":43,"Ru":44,"Rh":45,"Pd":46,"Ag":47,"Cd":48,"In":49,"Sn":50,
    "Sb":51,"Te":52,"I":53,"Xe":54,"Cs":55,"Ba":56,"La":57,"Ce":58,
    "Pr":59,"Nd":60,"Pm":61,"Sm":62,"Eu":63,"Gd":64,"Tb":65,"Dy":66,
    "Ho":67,"Er":68,"Tm":69,"Yb":70,"Lu":71,"Hf":72,"Ta":73,"W":74,
    "Re":75,"Os":76,"Ir":77,"Pt":78,"Au":79,"Hg":80,"Tl":81,"Pb":82,
    "Bi":83,"Po":84,"At":85,"Rn":86,"Fr":87,"Ra":88,"Ac":89,"Th":90,
    "Pa":91,"U":92,"Np":93,"Pu":94,"Am":95,"Cm":96,"Bk":97,"Cf":98,
    "Es":99,"Fm":100,
}

def _normalize_zaid(zaid: str) -> str:
    """将 ZAID 规范化为 ZZAAA 格式（不带前导零）。支持：
    - 001001 → 1001, 008016 → 8016, 092235 → 92235
    - 92235.06c → 92235.06c（带库后缀）
    - U-235 / U235 / Fe-56 → 92235 / 26056（元素-质量数格式，手动 ZAID 模式）
    """
    lib = ""
    if "." in zaid:
        num_part, lib = zaid.split(".", 1)
        lib = "." + lib
    else:
        num_part = zaid
    num_part = num_part.strip()
    m = re.match(r"^([A-Za-z]+)-?(\d+)$", num_part)
    if m:
        el = m.group(1)[0].upper() + m.group(1)[1:].lower()
        z = _ELEMENT_Z.get(el)
        if z is not None:
            return f"{z}{int(m.group(2)):03d}{lib}"
    stripped = num_part.lstrip("0") or "0"
    return stripped + lib


def _generate_materials(materials: list[MaterialData]) -> list[str]:
    """材料卡 — 每个核素一行续行格式（5 空格空白续行）"""
    lines = []
    for mat in materials:
        if not mat.rows:
            continue

        if mat.comment:
            lines.append(f"C  {mat.comment}")

        # 首行: M{n}，材料选项（nlib= 等）与 M 头同行（MCNP 规范）
        card = f"M{mat.number}"
        _opts = (getattr(mat, 'options', '') or '').strip()
        if _opts:
            card += "  " + _opts
        # 续行: 每个 ZAID/fraction 一行；raw 条件行原样独立成行（#ifdef/#else/#endif…）
        for row in mat.rows:
            if getattr(row, 'kind', 'nuclide') == "raw":
                card += f"\n{row.text}"
                continue
            zaid = _normalize_zaid(row.zaid)
            frac = row.fraction
            card += f"\n     {zaid}  {frac}"

        lines.append(card)

        # MT 热中子 S(a,b) 卡
        mt_card = getattr(mat, 'mt_card', '') or ''
        if mt_card.strip():
            lines.append(f"MT{mat.number}  {mt_card.strip()}")

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
    """单源：存在 Dn 引用或特殊字段时手写 SDEF，否则也用等号格式"""
    has_d_or_extra = any(
        _is_d_ref(v) for v in [src.par, src.erg, src.dir_, src.wgt,
                               src.cel, src.tme, src.rad, src.ext, src.axs, src.vec,
                               src.pos_x, src.pos_y, src.pos_z]
    ) or any([src.sur, src.nrm, src.tr, src.ccc, src.ara, src.rate, src.sdef_extra])
    if has_d_or_extra:
        # ── Dn 引用 → 手写 SDEF 行 ──
        parts = ["SDEF"]
        if src.par: parts.append(f"PAR={src.par}")
        if src.erg: parts.append(f"ERG={src.erg}")
        # 分布引用用 x=/y=/z=，普通数值用 POS=
        _all_same_d = src.pos_x and src.pos_y and src.pos_z and src.pos_x == src.pos_y == src.pos_z and _is_d_ref(src.pos_x)
        _pos_ref = any(_is_d_ref(v) for v in [src.pos_x, src.pos_y, src.pos_z] if v)
        if _all_same_d:
            parts.append(f"POS={src.pos_x}")
        elif _pos_ref:
            if src.pos_x: parts.append(f"X={src.pos_x}")
            if src.pos_y: parts.append(f"Y={src.pos_y}")
            if src.pos_z: parts.append(f"Z={src.pos_z}")
        else:
            pos_parts = []
            if src.pos_x: pos_parts.append(src.pos_x)
            if src.pos_y: pos_parts.append(src.pos_y)
            if src.pos_z: pos_parts.append(src.pos_z)
            if len(pos_parts) == 3:
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

    # ── 正常数值 → 手写 SDEF（统一使用 var=val 格式，对齐 C810）──
    parts = ["SDEF"]
    if src.par: parts.append(f"PAR={src.par}")
    if src.erg: parts.append(f"ERG={src.erg}")
    pos_parts = []
    if src.pos_x: pos_parts.append(src.pos_x)
    if src.pos_y: pos_parts.append(src.pos_y)
    if src.pos_z: pos_parts.append(src.pos_z)
    if len(pos_parts) == 3:
        parts.append(f"POS={' '.join(pos_parts)}")
    if src.dir_: parts.append(f"DIR={src.dir_}")
    if src.wgt: parts.append(f"WGT={src.wgt}")
    if src.cel: parts.append(f"CEL={src.cel}")
    if src.tme: parts.append(f"TME={src.tme}")
    if src.vec: parts.append(f"VEC={src.vec}")
    if src.axs: parts.append(f"AXS={src.axs}")
    if src.rad: parts.append(f"RAD={src.rad}")
    if src.ext: parts.append(f"EXT={src.ext}")
    return ["  ".join(parts)]


def _generate_distribution_sdef(adv: AdvancedSettings) -> list[str]:
    """分布源模式：从结构化字段生成 SDEF + 反序列化 SI/SP 文本"""
    parts = ["SDEF"]
    if adv.sdef_par: parts.append(f"PAR={adv.sdef_par}")
    if adv.sdef_erg: parts.append(f"ERG={adv.sdef_erg}")
    # 分布引用用 x=/y=/z=，普通数值用 POS=
    _px, _py, _pz = adv.sdef_pos_x, adv.sdef_pos_y, adv.sdef_pos_z
    _all_same_d = _px and _py and _pz and _px == _py == _pz and _is_d_ref(_px)
    _pos_ref = any(_is_d_ref(v) for v in [_px, _py, _pz] if v)
    if _all_same_d:
        parts.append(f"POS={_px}")
    elif _pos_ref:
        if _px: parts.append(f"X={_px}")
        if _py: parts.append(f"Y={_py}")
        if _pz: parts.append(f"Z={_pz}")
    else:
        pos_parts = [p for p in [_px, _py, _pz] if p]
        if len(pos_parts) == 3:
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

    # 结构化分布优先（新），旧 sdef_raw_text 兜底（兼容旧数据）
    if (adv.sdef_distributions or "").strip():
        lines.extend(_generate_structured_distributions(adv.sdef_distributions))
    elif adv.sdef_raw_text:
        # 反序列化 SI/SP 对，自动加回 SI{n}/SP{n} 前缀
        try:
            pairs = json.loads(adv.sdef_raw_text)
            for pair in pairs:
                idx = pair.get("id") or pairs.index(pair) + 1
                si = (pair.get("si") or "").strip()
                sp = (pair.get("sp") or "").strip()
                if si:
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
        for p in prob_floats:
            if math.isnan(p) or math.isinf(p):
                raise ValueError(f"无效概率值：{p}")
    except ValueError as e:
        raise ValueError(f"多源概率格式错误：{e}") from e
    total_prob = sum(prob_floats)
    if not (total_prob > 0):  # handles NaN correctly: NaN > 0 is False, so not False → fallback
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


def _generate_tallies(tally: TallySettings) -> list[str]:
    """计数卡 — 遍历 tally.tallies 列表生成 Fn 卡

    每张 TallyDefinition 遍历其 particles 列表，为每个粒子输出一行 Fn 卡。
    不再依赖 MODE 卡决定粒子——每行计数自带粒子选择。
    """
    if not tally.tallies:
        return []

    lines = [TALLIES_BANNER]

    for td in tally.tallies:
        params = td.params if td.params else ""
        pre = td.fn_prefix if td.fn_prefix and td.fn_prefix.strip() else ""
        suffix = getattr(td, 'number_suffix', '') or ''
        particles_str = ",".join(p.strip().upper() for p in td.particles if p.strip()) or "N"
        if pre in ("FIP", "FIR", "FIC"):
            card = f"{pre}{td.number}{suffix}:{particles_str}  {params}"
        else:
            card = f"{pre}F{td.number}{suffix}:{particles_str}  {params}"
        # 简要描述
        desc = {
            "F1": "Surface current",
            "F2": "Surface flux",
            "F4": "Cell flux",
            "F5": "Point detector",
            "F6": "Energy deposition",
            "F7": "Fission energy deposition",
            "F8": "Pulse height",
        }.get(td.type, "")
        if desc:
            card += f"   $ {desc} (particles/cm2)"
        lines.append(card)

    # E0 和 En 由 generate_inp_from_deck 中单独的 e0/cut 处理调用，不在此处重复生成
    return lines


def _compress_j_skip(fields: list[str]) -> str:
    """将字段列表压缩为 j-skip 语法。
    尾部连续空→截断，前导连续空→nJ，中间空→J。
    例: ["","","0","0"] → "2J 0 0"
    """
    fields = list(fields)  # 复制避免副作用
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
        ('n', ['cut_n_t', 'cut_n_e', 'cut_n_wc1', 'cut_n_wc2', 'cut_n_swtm']),
        ('p', ['cut_p_t', 'cut_p_e', 'cut_p_wc1', 'cut_p_wc2', 'cut_p_swtm']),
        ('e', ['cut_e_t', 'cut_e_e', 'cut_e_wc1', 'cut_e_wc2', 'cut_e_swtm']),
        ('h', ['cut_h_t', 'cut_h_e', 'cut_h_wc1', 'cut_h_wc2', 'cut_h_swtm']),
        ('he', ['cut_he_t', 'cut_he_e', 'cut_he_wc1', 'cut_he_wc2', 'cut_he_swtm']),
        ('d', ['cut_d_t', 'cut_d_e', 'cut_d_wc1', 'cut_d_wc2', 'cut_d_swtm']),
        ('t', ['cut_t_t', 'cut_t_e', 'cut_t_wc1', 'cut_t_wc2', 'cut_t_swtm']),
        ('a', ['cut_a_t', 'cut_a_e', 'cut_a_wc1', 'cut_a_wc2', 'cut_a_swtm']),
    ]:
        values = [getattr(tally, f, '') or '' for f in field_names]
        compact = _compress_j_skip(values)
        if compact:
            lines.append(f"CUT:{designator.upper()}  {compact}")
    return lines


def _generate_kcode(adv: AdvancedSettings) -> list[str]:
    """生成 KCODE + KSRC + HSRC 临界源卡。

    KCODE  NSRC RKK IKZ KCT [MSRK KNRM MRKP KC8]
    KSRC   x1 y1 z1 [x2 y2 z2 ...]
    HSRC   nx xmin xmax ny ymin ymax nz zmin zmax
    """
    lines = [KCODE_BANNER]
    if not adv.kcode_nsrc:
        return lines + [KCODE_SKIPPED_BANNER]

    # 8 参数：NSRC RKK IKZ KCT MSRK KNRM MRKP KC8（空值用 j-skip 压缩省略）
    kcode_parts = [
        adv.kcode_nsrc,
        adv.kcode_rkk or "1.0",
        adv.kcode_ikz or "30",
        adv.kcode_kct or "100",
        (adv.kcode_msrk or "").strip(),
        (adv.kcode_knrm or "").strip(),
        (adv.kcode_mrkp or "").strip(),
        (adv.kcode_kc8 or "").strip(),
    ]
    compact = _compress_j_skip(kcode_parts)
    lines.append(f"KCODE  {compact}")

    # KSRC coordinate points — 合并成单张 KSRC 卡（MCNP 只允许一张 KSRC 卡，
    # 多张卡会报错；多个点用 5 空格续行）
    if adv.ksrc_points:
        import json as _json
        try:
            points = _json.loads(adv.ksrc_points)
            if points:
                coords = []
                for pt in points:
                    # F-F：坐标可能是数值类型（json.loads 保持 int/float）→ 显式 str 强转；
                    # 0 是 falsy，`0 or ""` 会吞掉合法坐标 0 → None 感知 + 显式强转
                    _v = pt.get("x"); x = "" if _v is None else str(_v).strip()
                    _v = pt.get("y"); y = "" if _v is None else str(_v).strip()
                    _v = pt.get("z"); z = "" if _v is None else str(_v).strip()
                    if x and y and z:
                        coords.append(f"{x}  {y}  {z}")
                if coords:
                    lines.append(KSRC_BANNER)
                    lines.append("KSRC  " + coords[0])   # 首行 1 点
                    for c in coords[1:]:                 # 续行每行 1 点，方便阅读
                        lines.append("     " + c)
        except (_json.JSONDecodeError, TypeError):
            lines.append(KSRC_FAILED_BANNER)

    # HSRC 香农熵网格（评估裂变源收敛）
    if getattr(adv, "hsrc_enabled", False) and (adv.hsrc_text or "").strip():
        lines.append(HSRC_BANNER)
        lines.append(f"HSRC  {adv.hsrc_text.strip()}")
    return lines


# ── 结构化分布生成（SI/SP/SB/DS，源分布卡说明.md 第三/四节）──
def _generate_structured_distributions(dist_json: str) -> list[str]:
    """从 sdef_distributions JSON 生成 SI/SP/SB/DS 卡。

    格式: [{"id":1,"paramRef":"ERG",
            "si":{"type":"L","values":[...]},
            "sp":{"type":"D","values":[...],"fnCode":"-3","fnParams":["0.965","2.29"]},
            "sb":{"type":"-31","values":["1.5"]} | null,
            "ds":{"type":"S","param":"ERG","distributionIds":["3","4"]} | null}]
    """
    if not dist_json:
        return []
    import json as _json
    try:
        entries = _json.loads(dist_json)
    except (_json.JSONDecodeError, TypeError):
        return []
    lines = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("id", 1)
        si = entry.get("si") or {}
        sp = entry.get("sp") or {}
        sb = entry.get("sb")
        ds = entry.get("ds")
        # SI: SIn type values (L/H/A/S)
        si_type = (si.get("type") or "L").upper()
        si_vals = [str(v) for v in (si.get("values") or []) if str(v).strip()]
        if si_vals:
            lines.append(f"SI{idx}  {si_type}  {'  '.join(si_vals)}")
        # SP: SPn [type] values 或内置函数
        if sp:
            sp_type = (sp.get("type") or "").upper()
            fn = (sp.get("fnCode") or "").strip()
            fn_params = [str(v) for v in (sp.get("fnParams") or []) if str(v).strip()]
            vals = [str(v) for v in (sp.get("values") or []) if str(v).strip()]
            if fn:
                params_str = "  ".join(fn_params)
                lines.append(f"SP{idx}  {fn}" + (f"  {params_str}" if params_str else ""))
            elif sp_type in ("C", "V"):
                lines.append(f"SP{idx}  {sp_type}  {'  '.join(vals)}")
            elif vals:
                lines.append(f"SP{idx}  {'  '.join(vals)}")
        # SB: SBn [D] values 或 SBn -21/-31 a
        if sb:
            sb_type = (sb.get("type") or "D")
            sb_vals = [str(v) for v in (sb.get("values") or []) if str(v).strip()]
            if str(sb_type) in ("-21", "-31"):
                lines.append(f"SB{idx}  {sb_type}  {'  '.join(sb_vals)}")
            elif sb_vals:
                lines.append(f"SB{idx}  D  {'  '.join(sb_vals)}")
        # DS: DSn [type] [param] distIds（依赖分布）
        if ds:
            ds_type = (ds.get("type") or "S").upper()
            param = (ds.get("param") or "").strip()
            refs = [str(r) for r in (ds.get("distributionIds") or []) if str(r).strip()]
            if ds_type == "T":
                lines.append(f"DS{idx}  T")
            else:
                head = f"DS{idx}  {ds_type}"
                if param:
                    head += f"  {param}"
                if refs:
                    head += "  " + "  ".join(refs)
                lines.append(head)
    return lines


def _generate_ssw(adv: AdvancedSettings) -> list[str]:
    """SSW 写面源卡。SSW S1 S2 ... [SYM=] [PTY=] [CEL=]（源分布卡说明.md 四）"""
    if not (adv.ssw_surf or "").strip():
        return []
    parts = ["SSW  " + adv.ssw_surf.strip()]
    if (adv.ssw_sym or "").strip():
        parts.append(f"SYM={adv.ssw_sym.strip()}")
    if (adv.ssw_pty or "").strip():
        parts.append(f"PTY={adv.ssw_pty.strip()}")
    if (adv.ssw_cel or "").strip():
        parts.append(f"CEL={adv.ssw_cel.strip()}")
    return ["  ".join(parts)]


def _generate_ssr(adv: AdvancedSettings) -> list[str]:
    """SSR 读面源卡。SSR [OLD|NEW] S ... [CEL=] [PTY=] [COL=] [WGT=] [TR=] [PSC=]"""
    if not (adv.ssr_surf or "").strip():
        return []
    mode = (adv.ssr_mode or "").strip().upper()
    parts = ["SSR"]
    if mode == "OLD":
        parts.append("OLD")
    elif mode == "NEW":
        parts.append("NEW")
    parts.append(adv.ssr_surf.strip())
    for k, f in [("CEL", adv.ssr_cel), ("PTY", adv.ssr_pty), ("COL", adv.ssr_col),
                 ("WGT", adv.ssr_wgt), ("TR", adv.ssr_tr), ("PSC", adv.ssr_psc)]:
        if (f or "").strip():
            parts.append(f"{k}={f.strip()}")
    return ["  ".join(parts)]


def _parse_numeric_cards(text: str, letter: str) -> list[tuple[int | None, list[str]]]:
    """
    解析 En/Tn 多行卡文本 → [(number, [param_lines...]), ...]
    以 E{n}/T{n} 开新卡；缩进行或裸值行并入上一张卡的参数（保持多行原样）。
    无法识别的孤立行返回 (None, [原文])。
    """
    out: list[tuple[int | None, list[str]]] = []
    cur_num: int | None = None
    cur_lines: list[str] = []

    def flush():
        nonlocal cur_num, cur_lines
        if cur_num is not None:
            out.append((cur_num, cur_lines))
            cur_num, cur_lines = None, []

    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(rf'^{letter}(\d+)(?:\s+(.*))?$', stripped, re.IGNORECASE)
        if m:
            flush()
            cur_num = int(m.group(1))
            first = (m.group(2) or "").strip()
            cur_lines = [first] if first else []
        elif cur_num is not None:
            # 续行（缩进或裸值）→ 并入上一张卡参数，保持原样
            cur_lines.append(stripped)
        else:
            out.append((None, [stripped]))
    flush()
    return out


_NUM_RE = re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$')


def _emit_numeric_card(lines: list[str], letter: str, num: int, plines: list[str]) -> None:
    """
    输出 En/Tn 卡：
    - 纯数值列表 → 每值一个续行（E4 / 1 / 2 / 3）
    - 含参数化(i/log/lin)或混合 → 保持原样多行
    """
    body = " ".join(plines)
    tokens = body.split()
    if tokens and all(_NUM_RE.match(t) for t in tokens):
        lines.append(f"{letter}{num}")
        for t in tokens:
            lines.append(f"     {t}")
    else:
        if plines:
            lines.append(f"{letter}{num}  {plines[0]}")
            for extra in plines[1:]:
                lines.append(f"     {extra}")
        else:
            lines.append(f"{letter}{num}")


def _generate_en_cards(tally: TallySettings) -> list[str]:
    """生成 En 分计数能量箱卡 — 从 e_cards_text 解析，每计数可不同参数"""
    if not tally.e_cards_text or not tally.e_cards_text.strip():
        return []

    enabled = {td.number for td in tally.tallies
               if getattr(td, 'generate_en', False)}

    lines = [PER_TALLY_EN_BANNER]
    for num, plines in _parse_numeric_cards(tally.e_cards_text, "E"):
        if num is None:
            lines.append(skipped_card_banner("En", plines[0] if plines else ""))
        elif num in enabled:
            _emit_numeric_card(lines, "E", num, plines)
    return lines


def _generate_time_mesh(tally: TallySettings) -> list[str]:
    """生成 T0 时间网格 — 续行格式，空值跳过（对应 E0 的 _generate_energy_mesh）"""
    lines = []

    # 数值格式化：去掉多余的尾随零
    def _fmt(v: float) -> str:
        s = f"{v:.7g}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s

    if getattr(tally, 't0_custom_enabled', False) and getattr(tally, 't0_custom_text', '').strip():
        custom_values = []
        for raw_line in tally.t0_custom_text.strip().split("\n"):
            val = raw_line.strip()
            if val:
                try:
                    custom_values.append(float(val))
                except ValueError:
                    pass
        if len(custom_values) >= 2:
            parts = "\n".join(f"     {_fmt(v)}" for v in custom_values)
            lines.append(f"T0\n{parts}")
            lines.append(time_mesh_custom_banner(len(custom_values)))
        else:
            lines.append(TIME_MESH_SKIP_BANNER)
    else:
        if not tally.t0_min or not tally.t0_max or not tally.t0_bins:
            return lines  # 空值 → 不生成 T0
        try:
            tmin = float(tally.t0_min)
            tmax = float(tally.t0_max)
            n_bins = tally.t0_bins
            if n_bins > 0 and tmax > tmin:
                grid_syntax = "log" if tally.t0_log else "i"
                type_label = "LOG" if tally.t0_log else "LINEAR"
                lines.append(f"T0\n     {_fmt(tmin)} {n_bins}{grid_syntax} {_fmt(tmax)}")
                lines.append(time_mesh_banner(n_bins, type_label, _fmt(tmin), _fmt(tmax)))
        except (ValueError, ZeroDivisionError):
            lines.append(TIME_MESH_INVALID_BANNER)
    return lines


def _generate_tn_cards(tally: TallySettings) -> list[str]:
    """生成 Tn 分计数时间箱卡 — 从 t_cards_text 解析，每计数可不同参数"""
    if not getattr(tally, 't_cards_text', '') or not tally.t_cards_text.strip():
        return []

    enabled = {td.number for td in tally.tallies
               if getattr(td, 'generate_tn', False)}

    lines = [PER_TALLY_TN_BANNER]
    for num, plines in _parse_numeric_cards(tally.t_cards_text, "T"):
        if num is None:
            lines.append(skipped_card_banner("Tn", plines[0] if plines else ""))
        elif num in enabled:
            _emit_numeric_card(lines, "T", num, plines)
    return lines


# 公用：收集 enabled 计数编号
def _enabled_tally_nums(tally, attr: str) -> set:
    return {td.number for td in tally.tallies if getattr(td, attr, False)}


def _generate_energy_mesh(tally: TallySettings) -> list[str]:
    """生成 E0 能谱网格 — 续行格式，空值跳过"""
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
            # 手写 E0 + 每值一行续行
            parts = "\n".join(f"     {_fmt(v)}" for v in custom_values)
            lines.append(f"E0\n{parts}")
            lines.append(energy_mesh_custom_banner(len(custom_values)))
        else:
            lines.append(ENERGY_MESH_SKIP_BANNER)
    else:
        if not tally.e_min or not tally.e_max or not tally.e_bins:
            return lines  # 空值 → 不生成 E0
        try:
            e_min = float(tally.e_min)
            e_max = float(tally.e_max)
            n_bins = tally.e_bins

            if n_bins > 0 and e_max > e_min:
                grid_syntax = "log" if tally.e_log else "i"
                type_label = "LOG" if tally.e_log else "LINEAR"
                # 首行 E0，续行参数
                lines.append(
                    f"E0\n     {_fmt(e_min)} {n_bins}{grid_syntax} {_fmt(e_max)}"
                )
                lines.append(energy_mesh_banner(n_bins, type_label, _fmt(e_min), _fmt(e_max)))

        except (ValueError, ZeroDivisionError):
            lines.append(ENERGY_MESH_INVALID_BANNER)

    return lines


def _generate_phys(adv: AdvancedSettings) -> list[str]:
    """高级设置：PHYS 卡（不包含 other_cards，后者在数据卡段末尾生成）"""
    lines = []

    # PHYS:N — C810: EMAX EMCNF IUNR DNB FISNU
    phys_n = [adv.phys_n_emax, adv.phys_n_emcnf, adv.phys_n_iunr,
              adv.phys_n_dnb, adv.phys_n_fisnu]
    compact = _compress_j_skip(list(phys_n))
    if compact:
        lines.append(f"PHYS:N  {compact}")

    # PHYS:P — C810: EMCPF IDES NOCOH ISPN NODOP
    phys_p = [adv.phys_p_emcpf, adv.phys_p_ides, adv.phys_p_nocoh,
              adv.phys_p_ispn, adv.phys_p_nodop]
    compact = _compress_j_skip(list(phys_p))
    if compact:
        lines.append(f"PHYS:P  {compact}")

    # PHYS:E — C810: EMAX IDES IPHOT IBAD ISTRG BNUM XNUM RNOK ENUM NUMB
    phys_e = [adv.phys_e_emax, adv.phys_e_ides, adv.phys_e_iphoto,
              adv.phys_e_ibad, adv.phys_e_istrg, adv.phys_e_bnum,
              adv.phys_e_xnum, adv.phys_e_rnok, adv.phys_e_enum,
              adv.phys_e_numb]
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

    return lines


def _generate_other_cards(adv: AdvancedSettings) -> list[str]:
    """生成其他卡片（来自高级选项卡的手动输入），在数据卡段最末尾生成"""
    lines = []
    if adv.other_cards:
        lines.append(ADDITIONAL_CARDS_BANNER)
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

            # 在列 30-78 范围内找最后一个空格，留位置给续行符 &（2 列）
            split_at = line.rfind(" ", 30, 78)
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

    lines = []

    # 1. 标题卡
    title = basic.title.strip() if basic.title else "MCNP Input Generated by MCNP Generator"
    lines.append(title)

    # 2. 栅元卡
    raw = (overrides.get("cells") or "").strip()
    if raw:
        lines.append(RAW_CELL_BANNER)
        lines.extend(raw.split("\n"))
    else:
        cell_lines = _generate_cells(cells)
        if cell_lines:
            lines.append(cell_cards_banner(len(cells)))
            lines.extend(cell_lines)
    lines.append("")

    # 3. 曲面卡
    raw = (overrides.get("surfaces") or "").strip()
    if raw:
        lines.append(RAW_SURF_BANNER)
        lines.extend(raw.split("\n"))
    else:
        surf_lines = _generate_surfaces(surfaces_text)
        if surf_lines:
            lines.append(surface_cards_banner(len(surf_lines)))
            lines.extend(surf_lines)
    lines.append("")

    # 4. 数据卡
    lines.append(DATA_CARDS_BANNER)

    basic_lines = _generate_basic(basic)
    if basic_lines: lines.extend(basic_lines)

    # TRn 变换卡（来自右侧 TR 文本框，放入数据卡段）
    tr_text = deck.tr_cards.strip()
    if tr_text:
        lines.append(TR_BANNER)
        for tr_line in tr_text.split("\n"):
            tr_line = tr_line.strip()
            if tr_line:
                lines.append(tr_line)

    raw = (overrides.get("materials") or "").strip()
    if raw:
        lines.append(RAW_MAT_BANNER)
        lines.extend(raw.split("\n"))
    else:
        mat_lines = _generate_materials(materials)
        if mat_lines: lines.extend(mat_lines)

    raw = (overrides.get("sdef") or "").strip()
    if raw:
        lines.append(RAW_SDEF_BANNER)
        lines.extend(raw.split("\n"))
    else:
        _has_dist = bool(adv.sdef_raw_text) or bool(_dist_json_nonempty(adv.sdef_distributions))
        if adv.source_mode in ("distribution", "sdef") and _has_dist:
            sdef_lines = _generate_distribution_sdef(adv)
        elif adv.source_mode == "kcode" and adv.kcode_nsrc:
            sdef_lines = _generate_kcode(adv)
        elif adv.source_mode == "surface":
            sdef_lines = _generate_ssw(adv) + _generate_ssr(adv)
        else:
            sdef_lines = _generate_sdef(sources)
        if sdef_lines: lines.extend(sdef_lines)

    raw = (overrides.get("phys") or "").strip()
    if raw:
        lines.append(RAW_PHYS_BANNER)
        lines.extend(raw.split("\n"))
    else:
        phys_lines = _generate_phys(adv)
        if phys_lines: lines.extend(phys_lines)

    raw = (overrides.get("tally") or "").strip()
    if raw:
        lines.append(RAW_TALLY_BANNER)
        lines.extend(raw.split("\n"))
    else:
        tally_lines = _generate_tallies(tally)
        if tally_lines: lines.extend(tally_lines)

    raw = (overrides.get("e0") or "").strip()
    if raw:
        lines.append(RAW_E0_BANNER)
        lines.extend(raw.split("\n"))
    else:
        e0_lines = _generate_energy_mesh(tally)
        if e0_lines: lines.extend(e0_lines)

    # En 分计数能量箱（仅当 tally 无有效原始文本覆盖时自动生成）
    raw_tally = (overrides.get("tally") or "").strip()
    if not raw_tally:
        en_lines = _generate_en_cards(tally)
        if en_lines: lines.extend(en_lines)

    # T0 全局时间网格 + Tn 分计数时间箱
    if not raw_tally:
        t0_lines = _generate_time_mesh(tally)
        if t0_lines: lines.extend(t0_lines)
        tn_lines = _generate_tn_cards(tally)
        if tn_lines: lines.extend(tn_lines)

    raw = (overrides.get("cut") or "").strip()
    if raw:
        lines.append(RAW_CUT_BANNER)
        lines.extend(raw.split("\n"))
    else:
        cut_lines = _generate_cut(tally)
        if cut_lines: lines.extend(cut_lines)

    # 其他卡片排在数据卡段最末尾（来自高级选项卡的手动输入）
    other_lines = _generate_other_cards(adv)
    if other_lines: lines.extend(other_lines)

    lines.append("")
    raw = "\n".join(lines)
    return _wrap_long_lines(raw)
