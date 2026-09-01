"""
INP 生成器：使用 pymcnp 库构建 MCNP 数据卡，cells/surfaces 保留原始文本处理
"""

import json
import math
import re
from pymcnp import inp as pymcnp_inp
from app import lattice
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
    skipped_card_banner, multi_source_comment_banner,
    universe_group_banner,
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


def _generate_cells(cells: list[CellRow], universe_comments: dict = None) -> list[str]:
    """生成栅元卡 — 空值不输出；CellRow 可为 cell 或 raw 条件行。

    universe_comments（项9）：{u_str: text} → 按「当前 cell 顺序中相邻同 U 连续段」
    在该组首个栅元行前插 `C  U-group U=<n>: <user text>`（词汇冻结唯一发射源
    universe_group_banner）。raw 条件行不打断连续段；u 空/不同 → 新段。

    按 U 分组排序生成（用户要求）：无 raw 条件行时先稳定排序——未分组（u=""）在前、
    其余按数值 U 升序——使每个 U 组的 C U-group 注释恰出现一次；有 raw 条件行
    （#ifdef/#else/#endif 等）时保留原序，防止条件编译错位。
    """
    universe_comments = universe_comments or {}
    if not any(getattr(r, "kind", "cell") == "raw" for r in cells):
        def _u_key(r: CellRow):
            u = ((getattr(r, "cell", None) and r.cell.u) or "").strip()
            if not u:
                return (-1, 0)   # 未分组排最前（与 UI 分组视图一致）
            try:
                return (0, int(u))
            except (TypeError, ValueError):
                return (1, 0)    # 非数值 U（罕见）排最后
        cells = sorted(cells, key=_u_key)
    lines = []
    # ── IMP 归一化（MCNP 硬规则：某粒子只要出现 IMP 卡，条目数必须等于栅元数）──
    # 任一结构化栅元显式写了 imp_n/imp_p/imp_e → 所有结构化栅元补齐该粒子条目，
    # 缺省值用 MCNP 默认重要性 1（0/0.5 等显式值保留）；全部没写则不输出（MCNP 默认全 1）。
    # raw 条件行按原文透传，不参与归一化。
    structured_cells = [row.cell for row in cells if getattr(row, 'kind', 'cell') != "raw"]
    imp_kws = (("imp_n", "IMP:N"), ("imp_p", "IMP:P"), ("imp_e", "IMP:E"))
    need_imp = {attr: any(getattr(c, attr, "") for c in structured_cells)
                for attr, _ in imp_kws}
    prev_u = None  # 上一个结构化 cell 的 u（raw 行不打断连续段）
    for row in cells:
        if getattr(row, 'kind', 'cell') == "raw":
            lines.append(row.text)  # 原样条件行（#ifdef/#else/#endif…）
            continue
        cell = row.cell
        if cell.u and cell.u != prev_u:
            # 相邻同 U 连续段起点：每 U 组都插 U-group 头注释（用户要求：未编辑也生成，
            # 至少 `C  U-group U=<n>`；有编辑文本则追加 `<text>`）
            _u_text = universe_comments.get(str(cell.u))
            lines.append(universe_group_banner(cell.u, _u_text or ""))
        prev_u = cell.u
        mat = cell.material
        if " " in mat:
            mat = mat.split()[0]
        if mat.startswith("M") and len(mat) > 1 and mat[1:].isdigit():
            mat = mat[1:]

        density = "" if mat == "0" else cell.density

        # 只输出用户明确设置的参数
        params_parts = []
        for attr, kw in imp_kws:
            if need_imp[attr]:
                params_parts.append(f"{kw}={getattr(cell, attr, '') or '1'}")
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
        # 格阵 fill 分派：fill_grid JSON 有效 → 走格阵/翻译路径（FILL 首行放 params
        # 最后 = MCNP 要求 FILL 是 cell 卡最后参数；续行独立追加，绕开通用续行不加 &）。
        # 脏 JSON → FillGrid.from_json 返回 None → 优雅回退单值路径（R1 字节不变）。
        fg = lattice.FillGrid.from_json(cell.fill_grid or "")
        lattice_lines = lattice.format_fill_cards(fg) if fg is not None else []
        if cell.fill and fg is None:
            params_parts.append(f"FILL={cell.fill}")
        if cell.lat:
            params_parts.append(f"LAT={cell.lat}")
        if cell.trcl:
            params_parts.append(f"TRCL={cell.trcl}")
        if cell.tmp and cell.tmp.strip():
            params_parts.append(f"TMP={cell.tmp}")
        if cell.other_params:
            params_parts.append(cell.other_params)
        if lattice_lines:
            params_parts.append(lattice_lines[0])
        params = "  " + "  ".join(params_parts) if params_parts else ""
        # 格阵 cell：$ 注释不内联（FILL= 后是条目续行，解析 join 后 $ 注释会吞掉条目），
        # 改放所有续行之后的尾行（MCNP $ 只到本行尾，条目前置不受影响；round-trip 稳定）。
        lattice_comment_tail = ""
        if lattice_lines and cell.comment:
            comment = ""
            lattice_comment_tail = f"     $ {cell.comment}"
        else:
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

        # 格阵/翻译续行独立追加（FILL 卡条目行：5 空格续行、≤80 列、不加 &）
        for _extra in lattice_lines[1:]:
            lines.append(_extra)
        if lattice_comment_tail:
            lines.append(lattice_comment_tail)

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

        # 首行: M{n}，材料选项（nlib= 等）与 M 头同行（MCNP 规范）。
        # options 可含换行（前端"其他"框为 textarea）：按 \n 拆分——首段仍内联 M{n} 后
        # （无换行时字节不变，F-D pin 不回归），其余段作为 M 卡续行（行首 5 空格缩进），
        # 否则 MCNP 会把 gas=/plib= 当新卡解析。
        card = f"M{mat.number}"
        _opts = (getattr(mat, 'options', '') or '').replace("\r\n", "\n").replace("\r", "\n").strip()
        if _opts:
            _opt_lines = _opts.split("\n")
            _first_opt = _opt_lines[0].strip()
            if _first_opt:
                card += "  " + _first_opt
            for _extra_opt in _opt_lines[1:]:
                _extra_opt = _extra_opt.strip()
                if _extra_opt:
                    card += f"\n     {_extra_opt}"
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


# ── SDEF 表单字段（前端 sdefFields → adv.sdef_*）────────────────
# 表单模式（SDEF 通用源）填的字段只落在 adv.sdef_*；无分布/无多点源时，
# 需要合成单源走 _generate_sdef（与导入 round-trip 同路径，字节一致）。
_SDEF_FORM_FIELDS = (
    "sdef_par", "sdef_erg", "sdef_pos_x", "sdef_pos_y", "sdef_pos_z",
    "sdef_wgt", "sdef_dir", "sdef_cel", "sdef_tme", "sdef_vec", "sdef_axs",
    "sdef_rad", "sdef_ext", "sdef_sur", "sdef_nrm", "sdef_tr",
    "sdef_ccc", "sdef_ara", "sdef_rate", "sdef_extra",
)


def _sdef_form_has_values(adv: AdvancedSettings) -> bool:
    """SDEF 表单是否填了任何字段。"""
    return any(getattr(adv, f, "") for f in _SDEF_FORM_FIELDS)


def _source_from_adv(adv: AdvancedSettings) -> SourceData:
    """表单模式回退：adv.sdef_* → 单源 SourceData（与 parse_sdef_fields 反向对应）。"""
    return SourceData(
        number=1,
        par=adv.sdef_par, erg=adv.sdef_erg,
        pos_x=adv.sdef_pos_x, pos_y=adv.sdef_pos_y, pos_z=adv.sdef_pos_z,
        wgt=adv.sdef_wgt, dir_=adv.sdef_dir, cel=adv.sdef_cel, tme=adv.sdef_tme,
        vec=adv.sdef_vec, axs=adv.sdef_axs, rad=adv.sdef_rad, ext=adv.sdef_ext,
        sur=adv.sdef_sur, nrm=adv.sdef_nrm, tr=adv.sdef_tr,
        ccc=adv.sdef_ccc, ara=adv.sdef_ara, rate=adv.sdef_rate,
        sdef_extra=adv.sdef_extra,
    )


def _is_d_ref(val: str) -> bool:
    """检查值是否为 Dn 分布引用（如 D1、D2）"""
    return bool(re.match(r'^D\d+$', val.strip().upper())) if val else False


def _build_sdef_parts(src: SourceData, include_special: bool) -> list[str]:
    """单源 SDEF 字段构造（F#4 seam）。include_special=True 时含 6 扩展字段 + sdef_extra。

    字段顺序/条件与合并前完全一致：PAR ERG [POS 三态] DIR WGT CEL TME VEC AXS RAD EXT
    [+ SUR NRM TR CCC ARA RATE sdef_extra]。POS 三态：
      _all_same_d  → POS=Dn（三分量同 D 引用）
      _pos_ref     → X=/Y=/Z=（逐轴 D 引用或 F-续值）
      普通          → POS=x y z（仅三分量齐全时）
    """
    parts = ["SDEF"]
    if src.par:   parts.append(f"PAR={src.par}")
    if src.erg:   parts.append(f"ERG={src.erg}")
    _all_same_d = (src.pos_x and src.pos_y and src.pos_z
                   and src.pos_x == src.pos_y == src.pos_z and _is_d_ref(src.pos_x))
    _pos_ref = any(_is_d_ref(v) for v in (src.pos_x, src.pos_y, src.pos_z) if v)
    if _all_same_d:
        parts.append(f"POS={src.pos_x}")
    elif _pos_ref:
        if src.pos_x: parts.append(f"X={src.pos_x}")
        if src.pos_y: parts.append(f"Y={src.pos_y}")
        if src.pos_z: parts.append(f"Z={src.pos_z}")
    else:
        pos_parts = [v for v in (src.pos_x, src.pos_y, src.pos_z) if v]
        if len(pos_parts) == 3:
            parts.append(f"POS={' '.join(pos_parts)}")
    if src.dir_:  parts.append(f"DIR={src.dir_}")
    if src.wgt:   parts.append(f"WGT={src.wgt}")
    if src.cel:   parts.append(f"CEL={src.cel}")
    if src.tme:   parts.append(f"TME={src.tme}")
    if src.vec:   parts.append(f"VEC={src.vec}")
    if src.axs:   parts.append(f"AXS={src.axs}")
    if src.rad:   parts.append(f"RAD={src.rad}")
    if src.ext:   parts.append(f"EXT={src.ext}")
    if include_special:
        if src.sur:  parts.append(f"SUR={src.sur}")
        if src.nrm:  parts.append(f"NRM={src.nrm}")
        if src.tr:   parts.append(f"TR={src.tr}")
        if src.ccc:  parts.append(f"CCC={src.ccc}")
        if src.ara:  parts.append(f"ARA={src.ara}")
        if src.rate: parts.append(f"RATE={src.rate}")
        if src.sdef_extra: parts.append(src.sdef_extra)
    return parts


def _generate_single_source(src: SourceData) -> list[str]:
    """单源：存在 Dn 引用或特殊字段时手写 SDEF，否则也用等号格式"""
    has_d_or_extra = any(
        _is_d_ref(v) for v in [src.par, src.erg, src.dir_, src.wgt,
                               src.cel, src.tme, src.rad, src.ext, src.axs, src.vec,
                               src.pos_x, src.pos_y, src.pos_z]
    ) or any([src.sur, src.nrm, src.tr, src.ccc, src.ara, src.rate, src.sdef_extra])
    return ["  ".join(_build_sdef_parts(src, include_special=has_d_or_extra))]


# ── SDEF 字段表（F#5/F#6 单一事实来源）──
# 字段序 = 多源现状发射序（POS 首位）。值收集/方差标注/SI-SP 三处枚举全部改读本表。
# source_attr/adv_attr 分别供多源与分布回放取字段；special=="pos" 走三分量/F-分布特判。
_FieldSpec = tuple  # (keyword, source_attr, adv_attr, si_type, special)

SDEF_FIELD_SPECS = (
    ("POS",  None,   None,       "V", "pos"),    # 特殊：三分量 + F-分布
    ("PAR",  "par",  "sdef_par",  "L", None),
    ("ERG",  "erg",  "sdef_erg",  "L", None),
    ("DIR",  "dir_", "sdef_dir",  "L", None),
    ("WGT",  "wgt",  "sdef_wgt",  "L", None),
    ("CEL",  "cel",  "sdef_cel",  "L", None),
    ("TME",  "tme",  "sdef_tme",  "L", None),
    ("VEC",  "vec",  "sdef_vec",  "L", None),
    ("AXS",  "axs",  "sdef_axs",  "L", None),
    ("RAD",  "rad",  "sdef_rad",  "L", None),
    ("EXT",  "ext",  "sdef_ext",  "L", None),
    ("SUR",  "sur",  "sdef_sur",  "L", None),
    ("NRM",  "nrm",  "sdef_nrm",  "L", None),
    ("TR",   "tr",   "sdef_tr",   "L", None),
    ("CCC",  "ccc",  "sdef_ccc",  "L", None),
    ("ARA",  "ara",  "sdef_ara",  "L", None),
    ("RATE", "rate", "sdef_rate", "L", None),
)


def _src_field(src: SourceData, spec) -> tuple:
    """spec.special=="pos" → (pos_x,pos_y,pos_z)；else getattr(src, source_attr)"""
    if spec[4] == "pos":
        return (src.pos_x, src.pos_y, src.pos_z)
    return getattr(src, spec[1])


def _adv_field(adv: AdvancedSettings, spec) -> tuple:
    """spec.special=="pos" → (sdef_pos_x,sdef_pos_y,sdef_pos_z)；else getattr(adv, adv_attr)"""
    if spec[4] == "pos":
        return (adv.sdef_pos_x, adv.sdef_pos_y, adv.sdef_pos_z)
    return getattr(adv, spec[2])


def _generate_distribution_sdef(adv: AdvancedSettings) -> list[str]:
    """分布源模式：从结构化字段生成 SDEF + 反序列化 SI/SP 文本。

    字段序 = SDEF_FIELD_SPECS 序（POS 首位，与多源一致）；POS 四态含 F-dist 分支
    （根因 #2：`POS=F D1` → `_px="F" _py="D1"` 原样重建）；D1 键控链存在时重发
    multi_source_comment_banner（根因 #5）。
    """
    parts = ["SDEF"]
    # POS 特殊（先于表驱动，占 SDEF_FIELD_SPECS 首位）
    _px, _py, _pz = adv.sdef_pos_x, adv.sdef_pos_y, adv.sdef_pos_z
    _all_same_d = _px and _py and _pz and _px == _py == _pz and _is_d_ref(_px)
    _pos_ref = any(_is_d_ref(v) for v in [_px, _py, _pz] if v)
    if _px and _py and not _pz and re.match(r'^F\d*$', _px, re.IGNORECASE) and _is_d_ref(_py):
        # F-dist：POS=F D1（多源 `POS=F D1` 原样回放，逐轴重组漂移消除）
        parts.append(f"POS={_px} {_py}")
    elif _all_same_d:
        parts.append(f"POS={_px}")
    elif _pos_ref:
        if _px: parts.append(f"X={_px}")
        if _py: parts.append(f"Y={_py}")
        if _pz: parts.append(f"Z={_pz}")
    else:
        pos_parts = [p for p in [_px, _py, _pz] if p]
        if len(pos_parts) == 3:
            parts.append(f"POS={' '.join(pos_parts)}")
    # 其余字段按 SDEF_FIELD_SPECS 序发射（值非空才发）
    for spec in SDEF_FIELD_SPECS:
        keyword = spec[0]
        if keyword == "POS":
            continue
        value = _adv_field(adv, spec)
        if value:
            parts.append(f"{keyword}={value}")

    lines = ["  ".join(parts)]

    # 结构化分布优先（新），旧 sdef_raw_text 兜底（兼容旧数据）
    if (adv.sdef_distributions or "").strip():
        dist_lines = _generate_structured_distributions(adv.sdef_distributions)
        lines.extend(dist_lines)
        # 注释重发（根因 #5）：D1 键控链存在（SP 卡为 D1 引用）时发 multi_source_comment_banner。
        # 保守触发：≥2 条结构化分布且存在 D1 引用 SP 卡才发，单分布/无键控链不发（样例输出不变）。
        lines.extend(_multi_source_comment_reemit(adv.sdef_distributions))
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


def _multi_source_comment_reemit(dist_json: str) -> list[str]:
    """分布回放后重发多源概率键控注释（根因 #5）。

    结构化分布 ≥2 条且存在 SP 卡为 D1 引用（`sp.values == ["D1"]` 键控链）时，
    发 multi_source_comment_banner(n)，n = 首张含数值 SP 卡的 values 长度。
    保守触发：单分布无 D1 键控链（avr13/prob41c/inp24）不发。
    """
    try:
        entries = json.loads(dist_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(entries, list) or len(entries) < 2:
        return []
    has_d1_chain = any(
        (e.get("sp") or {}).get("values") == ["D1"]
        for e in entries
    )
    if not has_d1_chain:
        return []
    n = 0
    for e in entries:
        sp_vals = (e.get("sp") or {}).get("values") or []
        if sp_vals and sp_vals != ["D1"]:
            n = len(sp_vals)
            break
    return [multi_source_comment_banner(n)] if n else []


def _collect_source_values(sources: list[SourceData]) -> tuple[dict[str, list[str]], list[str], str]:
    """(a) 值收集：SDEF_FIELD_SPECS 驱动，返回 (field_values, prob_list, first_sdef_extra)。

    field_values 键 = 各 spec.keyword（POS 特殊拆三键：POS_X/POS_Y/POS_Z 三个 list）；
    prob_list = [src.probability or '1' ...]；first_sdef_extra = sources[0].sdef_extra。
    """
    field_values = {}
    for spec in SDEF_FIELD_SPECS:
        keyword = spec[0]
        if keyword == "POS":
            field_values["POS_X"] = [src.pos_x for src in sources]
            field_values["POS_Y"] = [src.pos_y for src in sources]
            field_values["POS_Z"] = [src.pos_z for src in sources]
        else:
            field_values[keyword] = [getattr(src, spec[1]) for src in sources]
    prob_list = [src.probability if src.probability else '1' for src in sources]
    first_sdef_extra = sources[0].sdef_extra if sources else ""
    return field_values, prob_list, first_sdef_extra


def _normalize_probabilities(prob_list: list[str], n_sources: int) -> list[str]:
    """(b) 概率归一（含 NaN/inf 校验，可独立单测——F#5 的核心收益）。

    float 化 → NaN/inf 抛 ValueError → 求和；total<=0（含 NaN）回退等概率 1/n；
    否则 p/total 格式化为 f"{:.6f}"。等价于现状（结构拆解前）405-417 行。
    """
    try:
        prob_floats = [float(p) for p in prob_list]
        for p in prob_floats:
            if math.isnan(p) or math.isinf(p):
                raise ValueError(f"无效概率值：{p}")
    except ValueError as e:
        raise ValueError(f"多源概率格式错误：{e}") from e
    total_prob = sum(prob_floats)
    if not (total_prob > 0):  # handles NaN correctly: NaN > 0 is False, so not False → fallback
        return [f"{1.0 / n_sources:.6f}" for _ in range(n_sources)]
    return [f"{p / total_prob:.6f}" for p in prob_floats]


def _varying_dist_params(field_values: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    """(c) 方差检测 + add_dist 纯函数化（等价于结构拆解前 419-449 行）。

    按 SDEF_FIELD_SPECS 序收集 len(set(values))>1 的 (keyword, values)；
    POS_X/POS_Y/POS_Z 三键跨源任一分量不同 → 首插 ("POS_VEC", ["x y z", ...])。
    """
    dist_params = []
    for spec in SDEF_FIELD_SPECS:
        keyword = spec[0]
        if keyword == "POS":
            continue
        values = field_values[keyword]
        if len(set(values)) > 1:
            dist_params.append((keyword, values))
    # POS 跨源是否不同（POS_VEC 恒占 D1）
    px, py, pz = field_values["POS_X"], field_values["POS_Y"], field_values["POS_Z"]
    n_sources = len(px)
    pos_differ = any(
        (px[i] != px[0] or py[i] != py[0] or pz[i] != pz[0])
        for i in range(1, n_sources)
    )
    if pos_differ:
        vec_entries = [f"{px[i]} {py[i]} {pz[i]}" for i in range(n_sources)]
        dist_params.insert(0, ("POS_VEC", vec_entries))
    return dist_params


def _build_multi_sdef_parts(sources: list[SourceData], field_values: dict[str, list[str]],
                            dist_params: list[tuple[str, list[str]]],
                            sdef_extra: str) -> list[str]:
    """(d) SDEF 行构造（等价于结构拆解前 451-499 行，含 sdef_extra 去重）。

    按 SDEF_FIELD_SPECS 序发射字段；D-index = dist_params.index(keyword) + 1
    （POS_VEC 恒占 D1）。发射规则：
      - POS：pos_differ → `POS=F D{1}`；else 三分量齐全 → `POS=x y z`
      - 首组（PAR/ERG/DIR/WGT）：在 dist_names → `{kw}=D{di}`；
        else PAR→`PAR={default}`（无条件）、WGT→`WGT={default}`（无条件）、
        ERG/DIR→`{kw}={default}`（default 非空才发）
      - 次组（CEL..RATE）：在 dist_names → `{kw}=D{di}`；else vals[0] 非空 → `{kw}={vals[0]}`
      - sdef_extra：取 sources[0].sdef_extra，剥离已在 dist_names 的 `KEY=` 片段（根因 #3）
    """
    sdef_parts = []
    di = 1
    dist_names = {d[0] for d in dist_params}
    px, py, pz = field_values["POS_X"], field_values["POS_Y"], field_values["POS_Z"]
    pos_differ = bool(dist_params) and dist_params[0][0] == "POS_VEC"
    if pos_differ:
        sdef_parts.append(f"POS=F D{di}"); di += 1
    elif any([px[0], py[0], pz[0]]):
        sdef_parts.append(f"POS={px[0]} {py[0]} {pz[0]}")

    for pn, default in [
        ("PAR", field_values["PAR"][0]),
        ("ERG", field_values["ERG"][0]),
        ("DIR", field_values["DIR"][0]),
        ("WGT", field_values["WGT"][0]),
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
        vals = field_values[pn]
        if pn in dist_names:
            sdef_parts.append(f"{pn}=D{di}"); di += 1
        elif vals[0]:
            sdef_parts.append(f"{pn}={vals[0]}")

    # 多源共用同一份 sdef_extra（取第一个源）；剥离已在 dist_names 的 `KEY=` 片段
    stripped = _strip_sdef_extra_dist_keys(sdef_extra, dist_names)
    if stripped:
        sdef_parts.append(stripped)
    return sdef_parts


def _strip_sdef_extra_dist_keys(sdef_extra: str, dist_names: set[str]) -> str:
    """剥离 sdef_extra 中 KEY 属于 dist_names（分布关键字）的 `KEY=` 片段（根因 #3）。

    片段边界 = `KEY=` 起始位置（`\b[A-Za-z]+=`），KEY= 到下一个 KEY= 前为一个片段。
    标量-标量重复（KEY 非分布）不去——走 sdef_extra 天然 round-trip。
    """
    if not sdef_extra:
        return ""
    matches = list(re.finditer(r'\b([A-Za-z]+)=', sdef_extra))
    if not matches:
        return sdef_extra.strip()
    segments = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(sdef_extra)
        segments.append(sdef_extra[start:end].strip())
    kept = [seg for seg in segments
            if seg.partition("=")[0].strip().upper() not in dist_names]
    return " ".join(kept)


def _build_multi_sisp_cards(dist_params: list[tuple[str, list[str]]],
                            prob_norm: list[str], n_sources: int) -> list[str]:
    """(e) SI/SP 构造（等价于结构拆解前 501-517 行 + SI 值扁平化）。

    SI 卡序 = dist_params 序；POS_VEC → `SI{di}  V  平坦值`，其余 → `SI{di}  L  平坦值`；
    每个 value 先 split() 拆 token 再 '  '.join 全部 token（与回放字节一致）；
    首张 SI 的 SP 带 prob_norm（`SP{di}  {prob}`），其余 `SP{di}  D1`；
    dist_params 非空 → 末尾 multi_source_comment_banner(n_sources)。
    """
    lines = []
    si_di = 1
    first_dist = True
    for param_name, values in dist_params:
        flat = "  ".join(tok for v in values for tok in v.split())
        if param_name == "POS_VEC":
            lines.append(f"SI{si_di}  V  {flat}")
        else:
            lines.append(f"SI{si_di}  L  {flat}")
        if first_dist:
            lines.append(f"SP{si_di}  {'  '.join(prob_norm)}")
            first_dist = False
        else:
            lines.append(f"SP{si_di}  D1")
        si_di += 1

    if dist_params:
        lines.append(multi_source_comment_banner(n_sources))

    return lines


def _generate_multi_source(sources: list[SourceData]) -> list[str]:
    """
    多源：手动生成 SDEF + SI/SP 分布卡。
    保留此逻辑是因为 pymcnp 的 SI/SP 机制需要逐卡构造，
    且多源之间的 Dn 键控关联由我们精确控制更可靠。
    """
    field_values, prob_list, sdef_extra = _collect_source_values(sources)
    prob_norm = _normalize_probabilities(prob_list, len(sources))
    dist_params = _varying_dist_params(field_values)
    sdef_parts = _build_multi_sdef_parts(sources, field_values, dist_params, sdef_extra)
    lines = ["SDEF  " + "  ".join(sdef_parts)]
    lines += _build_multi_sisp_cards(dist_params, prob_norm, len(sources))
    return lines


def _generate_tallies(tally: TallySettings) -> list[str]:
    """计数卡 — 遍历 tally.tallies 列表生成 Fn 卡 + FMESH/TMESH 网格计数回放 + PTRAC 径迹输出

    每张 TallyDefinition 遍历其 particles 列表，为每个粒子输出一行 Fn 卡。
    不再依赖 MODE 卡决定粒子——每行计数自带粒子选择。
    FMESH/TMESH（fmesh_defs）紧随 F 卡段后回放（契约 §6 步 4，照 FM 回放模式）。
    PTRAC（tally.ptrac.enabled）在计数段末尾 emit（契约 ptrac-visualization.md v2 §4.5）。
    """
    fmesh_defs = getattr(tally, "fmesh_defs", None) or []
    ptrac = getattr(tally, "ptrac", None)
    ptrac_enabled = bool(ptrac and getattr(ptrac, "enabled", False))
    if not tally.tallies and not fmesh_defs and not ptrac_enabled:
        return []

    lines = [TALLIES_BANNER]

    for td in tally.tallies:
        params = td.params if td.params else ""
        pre = td.fn_prefix if td.fn_prefix and td.fn_prefix.strip() else ""
        suffix = getattr(td, 'number_suffix', '') or ''
        multiplier = getattr(td, 'multiplier', '') or ''
        # 仅 FM 乘子占位（type==""，无对应 Fn 卡）→ 不生成 F 卡，只回放 FM 乘子
        if td.type:
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
        # FM 计数乘子卡：紧跟在对应 F 卡之后（FMn 乘在 Fn 计数上）
        if multiplier:
            lines.append(f"FM{td.number}  {multiplier}")

    # FMESH/TMESH 网格计数回放（结构化字段齐全走结构化，否则回放 raw——round-trip 兜底）
    if fmesh_defs:
        from app.meshtal.fmesh_parser import fmesh_defs_to_lines
        lines.extend(fmesh_defs_to_lines(fmesh_defs))

    # PTRAC 粒子径迹输出（契约 v2 §4.5）
    if ptrac_enabled:
        lines.extend(_generate_ptrac(tally))

    # E0 和 En 由 generate_inp_from_deck 中单独的 e0/cut 处理调用，不在此处重复生成
    return lines


def _generate_ptrac(tally: TallySettings) -> list[str]:
    """PTRAC 卡（契约 ptrac-visualization.md v2 §4.5）：`PTRAC FILE=… WRITE=… …`。

    卡体格式与前端 gui/src/ptrac/ptracState.ts `ptracToCardText` 逐字对齐：
    FILE/WRITE 恒发（默认 ASC/ALL，FILE/WRITE 大写）；MAX 只发非空项（留空=不输出，
    用 MCNP 默认 10000 事件——此前 MAX=-1 使本机 MCNP 写完 1 个事件就终止运行，用户实测踩坑）；
    TYPE 多值空格分隔且大写；NPS/CELL/SURFACE/VALUE/EVENT/BUFFER/FILTER/TALLY/MEPH 只发非空项
    （C810 Table I.2 全 13 关键字）。
    """
    ptrac = getattr(tally, "ptrac", None)
    if not ptrac or not getattr(ptrac, "enabled", False):
        return []
    parts = ["PTRAC"]
    parts.append(f"FILE={(getattr(ptrac, 'file', '') or 'ASC').upper()}")
    parts.append(f"WRITE={(getattr(ptrac, 'write', '') or 'ALL').upper()}")
    _max = (getattr(ptrac, "max", "") or "").strip()
    if _max:
        parts.append(f"MAX={_max}")
    types = [str(t).strip().upper() for t in (getattr(ptrac, "types", None) or []) if str(t).strip()]
    if types:
        parts.append("TYPE=" + " ".join(types))
    if (getattr(ptrac, "nps", "") or "").strip():
        parts.append(f"NPS={ptrac.nps.strip()}")
    if (getattr(ptrac, "cell", "") or "").strip():
        parts.append(f"CELL={ptrac.cell.strip()}")
    if (getattr(ptrac, "surface", "") or "").strip():
        parts.append(f"SURFACE={ptrac.surface.strip()}")
    if (getattr(ptrac, "value", "") or "").strip():
        parts.append(f"VALUE={ptrac.value.strip()}")
    if (getattr(ptrac, "event", "") or "").strip():
        parts.append(f"EVENT={ptrac.event.strip()}")
    if (getattr(ptrac, "buffer", "") or "").strip():
        parts.append(f"BUFFER={ptrac.buffer.strip()}")
    if (getattr(ptrac, "filter", "") or "").strip():
        parts.append(f"FILTER={ptrac.filter.strip()}")
    if (getattr(ptrac, "tally", "") or "").strip():
        parts.append(f"TALLY={ptrac.tally.strip()}")
    if (getattr(ptrac, "meph", "") or "").strip():
        parts.append(f"MEPH={ptrac.meph.strip()}")
    return [" ".join(parts)]


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
        try:
            points = json.loads(adv.ksrc_points)
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
        except (json.JSONDecodeError, TypeError):
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
    try:
        entries = json.loads(dist_json)
    except (json.JSONDecodeError, TypeError):
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
        # SC: SCn 源注释卡（源分布卡说明.md §三）——先于该分布卡族回放
        sc = (entry.get("sc") or "").strip()
        if sc:
            lines.append(f"SC{idx}  {sc}")
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
    注释保护：行内 `$` 位于第 80 列内 → 卡体已合法，注释超长不拆
    （MCNP 忽略 80 列后的注释；拆注释会注入 `&` 污染注释文本，
    重解析后注释逐代漂移，破坏 R1 不动点——BEAVRS 长注释实卡触发）。
    """
    result = []
    for line in text.split("\n"):
        line = line.rstrip()
        if len(line) > 80:
            _dollar = line.find("$")
            if 0 <= _dollar < 80:
                result.append(line)
                continue
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

def _raw_override_text(overrides: dict, key: str) -> str:
    """空串/缺省/纯空白 = 无覆盖（现状语义）。"""
    return (overrides.get(key) or "").strip()


def _has_raw_override(overrides: dict, key: str) -> bool:
    return bool(_raw_override_text(overrides, key))


def _apply_raw_override(lines: list[str], overrides: dict, key: str,
                        banner: str, generator) -> None:
    """raw_overrides 守卫（收敛 8 处复制粘贴）。
    key 有非空覆盖 → 打 RAW_*_BANNER + 追加覆盖文本（split("\\n")）；
    否则走 generator()（返回待追加行列表），与现状语义逐字一致。
    banner 是 RAW_*_BANNER 常量；generator 闭包内可含自身节头（如 cells 的 cell_cards_banner）。
    """
    if _has_raw_override(overrides, key):
        lines.append(banner)
        lines.extend(_raw_override_text(overrides, key).split("\n"))
    else:
        lines.extend(generator())


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

    # 2. 栅元卡（项9：deck.universe_comments → U 分组头 C 注释）
    _apply_raw_override(lines, overrides, "cells", RAW_CELL_BANNER, lambda: (
        (lambda cl: ([cell_cards_banner(len(cells))] + cl) if cl else [])(
            _generate_cells(cells, universe_comments=deck.universe_comments))))
    lines.append("")

    # 3. 曲面卡
    _apply_raw_override(lines, overrides, "surfaces", RAW_SURF_BANNER, lambda: (
        (lambda sl: ([surface_cards_banner(len(sl))] + sl) if sl else [])(_generate_surfaces(surfaces_text))))
    lines.append("")

    # 4. 数据卡
    lines.append(DATA_CARDS_BANNER)

    basic_lines = _generate_basic(basic)
    # 用户要求：MODE（粒子类型）+ NPS（数量）卡放到数据卡段最末尾，
    # 其余基本卡（CTME/ACT/PRINT/NONU）留在数据卡开头。
    basic_tail = [l for l in basic_lines if l.startswith("MODE") or l.startswith("NPS")]
    basic_head = [l for l in basic_lines if not (l.startswith("MODE") or l.startswith("NPS"))]
    if basic_head: lines.extend(basic_head)

    # TRn 变换卡（来自右侧 TR 文本框，放入数据卡段）
    tr_text = deck.tr_cards.strip()
    if tr_text:
        lines.append(TR_BANNER)
        for tr_line in tr_text.split("\n"):
            tr_line = tr_line.strip()
            if tr_line:
                lines.append(tr_line)

    _apply_raw_override(lines, overrides, "materials", RAW_MAT_BANNER,
                        lambda: _generate_materials(materials))

    # sdef 分派（distribution/kcode/surface/fixed 四分支，封进闭包）
    def _sdef_dispatch():
        _has_dist = bool(adv.sdef_raw_text) or bool(_dist_json_nonempty(adv.sdef_distributions))
        if adv.source_mode in ("distribution", "sdef"):
            if _has_dist:
                return _generate_distribution_sdef(adv)
            if sources:
                return _generate_sdef(sources)
            # 表单模式（无分布、无多点源）：SDEF 源参数字段有值 → 合成单源生成
            if _sdef_form_has_values(adv):
                return _generate_sdef([_source_from_adv(adv)])
            return []
        elif adv.source_mode == "kcode" and adv.kcode_nsrc:
            return _generate_kcode(adv)
        elif adv.source_mode == "surface":
            return _generate_ssw(adv) + _generate_ssr(adv)
        else:
            return _generate_sdef(sources)
    _apply_raw_override(lines, overrides, "sdef", RAW_SDEF_BANNER, _sdef_dispatch)

    _apply_raw_override(lines, overrides, "phys", RAW_PHYS_BANNER,
                        lambda: _generate_phys(adv))

    _apply_raw_override(lines, overrides, "tally", RAW_TALLY_BANNER,
                        lambda: _generate_tallies(tally))

    _apply_raw_override(lines, overrides, "e0", RAW_E0_BANNER,
                        lambda: _generate_energy_mesh(tally))

    # En 分计数能量箱（仅当 tally 无有效原始文本覆盖时自动生成）—— 门控看 tally key，非 e0/cut
    if not _has_raw_override(overrides, "tally"):
        en_lines = _generate_en_cards(tally)
        if en_lines: lines.extend(en_lines)

    # T0 全局时间网格 + Tn 分计数时间箱
    if not _has_raw_override(overrides, "tally"):
        t0_lines = _generate_time_mesh(tally)
        if t0_lines: lines.extend(t0_lines)
        tn_lines = _generate_tn_cards(tally)
        if tn_lines: lines.extend(tn_lines)

    _apply_raw_override(lines, overrides, "cut", RAW_CUT_BANNER,
                        lambda: _generate_cut(tally))

    # 其他卡片排在数据卡段最末尾（来自高级选项卡的手动输入）
    other_lines = _generate_other_cards(adv)
    if other_lines: lines.extend(other_lines)

    # MODE + NPS 卡放在数据卡段的最末尾（用户指定布局）
    if basic_tail: lines.extend(basic_tail)

    lines.append("")
    raw = "\n".join(lines)
    return _wrap_long_lines(raw)
