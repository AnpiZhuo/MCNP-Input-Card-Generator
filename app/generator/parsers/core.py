"""
数据卡解析：栅元/材料/SDEF/计数/CUT
Core Parsers: parse cell cards, material definitions, SDEF source, tallies, CUT, and PHYS cards.

This module contains the main parsing logic for MCNP input card types:
- Cell cards: geometry cells with material, density, surface expressions, and parameters
- Surface cards: returned as raw text (no structured parsing needed)
- Material cards (Mn): ZAID/fraction pairs with options
- SDEF source card: source definition with POS/VEC/AXS and distribution support
- Tally cards (Fn): F1-F8 with particle designators
- CUT cards: time/energy cutoffs for each particle type
- PHYS cards: physics settings per particle type
- E0 energy grid: support for explicit values and parametric (nlog/nlin/nI) syntax
"""
import json
import math
import re
from app.models import CellData, MaterialData, MaterialRow, SourceData
from .lines import _SURFACE_TYPES, extract_comment, strip_comment


def _is_float(s: str) -> bool:
    """Check if a string can be interpreted as a float.

    Args:
        s: The string to test.

    Returns:
        True if float(s) succeeds, False otherwise.
    """
    try:
        float(s)
        return True
    except ValueError:
        return False


def _expand_j_skip(params: list[str], count: int) -> list[str]:
    """展开 j-skip 语法，补齐到 count 个元素。
    Expand MCNP j-skip syntax (placeholder skipping) to a fixed count of elements.

    MCNP uses "j" to skip a field and "nj" to skip n fields. This function
    expands those placeholders into empty strings, padding or truncating
    to the requested count. If the expansion exceeds count, trailing non-empty
    values are preserved and intermediate values are truncated.

    Examples:
        ["2j", "0", "0"] with count=6 -> ["", "", "0", "0", "", ""]
        ["4j", "1"] with count=3 -> ["", "", "1"]

    Args:
        params: List of parameter tokens, possibly containing "j" / "nj" skips.
        count: The target number of elements.

    Returns:
        A list of length count, with empty strings for skipped positions.
    """
    result = []
    for p in params:
        u = p.upper()
        if u == "J":
            result.append("")
        elif u.endswith("J") and u[:-1].isdigit():
            for _ in range(int(u[:-1])):
                result.append("")
        else:
            result.append(p)
    return (result[-count:] if len(result) >= count
            else result + [""] * (count - len(result)))


def parse_cells(cell_lines: list[str]) -> list[CellData]:
    """解析栅元卡行 → CellData 列表"""
    cells = []
    content = [l for l in cell_lines if l.strip()
               and not l.strip().upper().startswith("C ")
               and not l.strip().upper().startswith("C\t")]

    for line in content:
        comment = extract_comment(line)
        line_clean = strip_comment(line)
        parts = line_clean.split()
        if not parts:
            continue

        cell_num = parts[0]
        if not cell_num.lstrip('-').isdigit():
            continue
        number = int(cell_num)

        material = parts[1] if len(parts) > 1 else "0"

        density = ""
        surf_start = 2
        if material != "0" and len(parts) > 2:
            if parts[2].startswith("-") and _is_float(parts[2]):
                density = parts[2]
                surf_start = 3
            elif _is_float(parts[2]):
                if (len(parts) <= 3 or
                    parts[3].upper() in _SURFACE_TYPES or
                    parts[3].lstrip('#(+-').isdigit()):
                    density = parts[2]
                    surf_start = 3

        surf_parts = []
        imp_n = "1"
        imp_p = ""
        imp_e = ""
        vol = ""
        pwt = ext = fcl = u_ = fill = lat = trcl = ""

        idx = surf_start
        while idx < len(parts):
            token = parts[idx]
            upper = token.upper()
            if upper.startswith("IMP:N="):
                imp_n = token.split("=", 1)[1]
            elif upper.startswith("IMP:P="):
                imp_p = token.split("=", 1)[1]
            elif upper.startswith("IMP:E="):
                imp_e = token.split("=", 1)[1]
            elif upper.startswith("VOL="):
                vol = token.split("=", 1)[1]
            elif upper.startswith("PWT="):
                pwt = token.split("=", 1)[1]
            elif upper.startswith("EXT="):
                ext = token.split("=", 1)[1]
            elif upper.startswith("FCL="):
                fcl = token.split("=", 1)[1]
            elif upper.startswith("U="):
                u_ = token.split("=", 1)[1]
            elif upper.startswith("FILL="):
                fill = token.split("=", 1)[1]
            elif upper.startswith("LAT="):
                lat = token.split("=", 1)[1]
            elif upper.startswith("TRCL="):
                trcl = token.split("=", 1)[1]
            elif upper.startswith("IMP:N"):
                idx += 1
                if idx < len(parts):
                    imp_n = parts[idx]
            elif upper.startswith("IMP:P"):
                idx += 1
                if idx < len(parts):
                    imp_p = parts[idx]
            elif upper.startswith("IMP:E"):
                idx += 1
                if idx < len(parts):
                    imp_e = parts[idx]
            elif upper.startswith("VOL"):
                idx += 1
                if idx < len(parts):
                    vol = parts[idx]
            elif upper == "PWT":
                idx += 1
                if idx < len(parts):
                    pwt = parts[idx]
            elif upper == "EXT":
                idx += 1
                if idx < len(parts):
                    ext = parts[idx]
            elif upper == "FCL":
                idx += 1
                if idx < len(parts):
                    fcl = parts[idx]
            elif upper == "U":
                idx += 1
                if idx < len(parts):
                    u_ = parts[idx]
            elif upper == "FILL":
                idx += 1
                if idx < len(parts):
                    fill = parts[idx]
            elif upper == "LAT":
                idx += 1
                if idx < len(parts):
                    lat = parts[idx]
            elif upper == "TRCL":
                idx += 1
                if idx < len(parts):
                    trcl = parts[idx]
            else:
                surf_parts.append(token)
            idx += 1

        cells.append(CellData(
            number=number, material=material, density=density,
            surface_expr=" ".join(surf_parts),
            imp_n=imp_n, imp_p=imp_p, imp_e=imp_e,
            vol=vol, pwt=pwt, ext=ext, fcl=fcl,
            u=u_, fill=fill, lat=lat, trcl=trcl,
            comment=comment,
        ))

    return cells


def parse_surfaces(surf_lines: list[str]) -> str:
    """曲面卡直接返回原始文本"""
    return "\n".join(surf_lines).strip()


def _parse_material(parts: list[str], m_str: str) -> MaterialData:
    """解析材料卡：Mn zaid1 frac1 zaid2 frac2 ... [options]"""
    num_str = m_str[1:]
    try:
        number = int(num_str)
    except ValueError:
        number = 0

    rows = []
    options_parts = []
    i = 1
    while i < len(parts):
        token = parts[i]
        upper = token.upper()

        # keyword=value 选项（nlib=, gas=, plib=, estep=, cond=, hlib=, elib=）
        if "=" in token:
            options_parts.append(token)
            i += 1
            continue

        # 单独的关键词（无 =）
        if upper in ("GAS", "PLIB", "ESTEP", "COND", "HLIB", "NLIB", "ELIB"):
            options_parts.append(token)
            i += 1
            continue

        # 下一个 token 若是关键词则跳过本次 zaid（单关键词后面可能跟值）
        if i + 1 < len(parts):
            next_upper = parts[i + 1].upper()
            if next_upper in ("GAS", "PLIB", "ESTEP", "COND", "HLIB", "NLIB", "ELIB"):
                options_parts.append(token)
                i += 1
                continue

        # ZAID + fraction pair
        if i + 1 < len(parts):
            zaid = token
            frac = parts[i + 1]
            rows.append(MaterialRow(zaid=zaid, fraction=frac))
            i += 2
        else:
            # trailing option
            options_parts.append(token)
            i += 1

    return MaterialData(
        number=number, rows=rows, comment="",
        options=" ".join(options_parts) if options_parts else "",
    )


def _apply_sdef_param(src: SourceData, key: str, val: str):
    """将 SDEF 参数值应用到 SourceData"""
    key = key.upper()
    if key == "PAR":      src.par = val
    elif key == "ERG":    src.erg = val
    elif key == "POS":    src.pos_x = val
    elif key == "DIR":    src.dir_ = val
    elif key == "WGT":    src.wgt = val
    elif key == "CEL":    src.cel = val
    elif key == "TME":    src.tme = val
    elif key == "VEC":    src.vec = val
    elif key == "AXS":    src.axs = val
    elif key == "RAD":    src.rad = val
    elif key == "EXT":    src.ext = val
    elif key == "SUR":    src.sur = val
    elif key == "NRM":    src.nrm = val
    elif key == "TR":     src.tr = val
    elif key == "CCC":    src.ccc = val
    elif key == "ARA":    src.ara = val
    elif key == "RATE":   src.rate = val


def _collect_multi_val(tokens: list[str], start: int) -> list[str]:
    """从 start 开始收集后续连续 token，直到遇到 key=value 结尾"""
    vals = []
    while start < len(tokens) and "=" not in tokens[start]:
        vals.append(tokens[start])
        start += 1
    return vals


def parse_sdef_simple(parts: list[str]) -> list[SourceData]:
    """解析单行 SDEF 卡 → 单个 SourceData。
    支持 POS x y z（无=）、POS=x y z、VEC=1 -1 0 续值等格式。
    未知关键字静默跳过（预验证已检查）。
    """
    _KNOWN_KEYS = {"PAR", "ERG", "POS", "DIR", "WGT",
                   "CEL", "TME", "VEC", "AXS", "RAD", "EXT",
                   "SUR", "NRM", "TR", "CCC", "ARA", "RATE"}
    src = SourceData(number=1)
    tokens = parts[1:]
    ti = 0
    while ti < len(tokens):
        token = tokens[ti]
        upper = token.upper()
        if "=" in token:
            key, _, val = token.partition("=")
            key = key.upper()
            if val:
                _apply_sdef_param(src, key, val)
                ti += 1
                # 多值参数：POS=x y z, VEC=x y z, AXS=x y z
                if key in ("POS", "VEC", "AXS"):
                    cont = _collect_multi_val(tokens, ti)
                    if cont:
                        if key == "POS":
                            all_vals = [val] + cont
                            if len(all_vals) >= 1: src.pos_x = all_vals[0]
                            if len(all_vals) >= 2: src.pos_y = all_vals[1]
                            if len(all_vals) >= 3: src.pos_z = all_vals[2]
                        elif key == "VEC":
                            src.vec = " ".join([val] + cont)
                        elif key == "AXS":
                            src.axs = " ".join([val] + cont)
                        ti += len(cont)
                    continue
                # 未知关键字 → 跳过（预验证已检查，不会到达此处）
                if key not in _KNOWN_KEYS:
                    continue
            else:
                ti += 1
                if ti < len(tokens):
                    _apply_sdef_param(src, key, tokens[ti])
                    ti += 1
                    continue
        else:
            # 裸参数（无=）：POS x y z, PAR val, SUR val, …
            if upper == "POS":
                ti += 1
                vals = _collect_multi_val(tokens, ti)
                if len(vals) >= 1: src.pos_x = vals[0]
                if len(vals) >= 2: src.pos_y = vals[1]
                if len(vals) >= 3: src.pos_z = vals[2]
                ti += len(vals)
                continue
            elif upper in ("PAR", "SUR", "NRM", "TR", "CCC", "ARA", "RATE"):
                ti += 1
                if ti < len(tokens):
                    _apply_sdef_param(src, upper, tokens[ti])
                    ti += 1
                    continue
            ti += 1
    return [src]


def parse_sdef_fields(parts: list[str]) -> dict:
    """解析 SDEF 行中的 key=value 对 → 分布源模式字段字典。
    支持 POS x y z（无=）、POS=x y z、VEC=1 -1 0 续值等格式。
    未知关键字静默跳过（预验证已检查）。
    返回 {"sdef_par": "1", "sdef_erg": "D2", ...}
    """
    result = {}
    field_map = {
        "PAR": "sdef_par", "ERG": "sdef_erg", "WGT": "sdef_wgt",
        "DIR": "sdef_dir", "CEL": "sdef_cel", "TME": "sdef_tme",
        "VEC": "sdef_vec", "AXS": "sdef_axs", "RAD": "sdef_rad",
        "EXT": "sdef_ext",
        "SUR": "sdef_sur", "NRM": "sdef_nrm", "TR": "sdef_tr",
        "CCC": "sdef_ccc", "ARA": "sdef_ara", "RATE": "sdef_rate",
    }
    multi_val_params = {"VEC", "AXS"}  # 多值参数（key=val 后跟空格续值）
    tokens = parts[1:]
    ti = 0
    while ti < len(tokens):
        token = tokens[ti]
        upper = token.upper()
        if "=" in token:
            key, _, val = token.partition("=")
            key = key.upper()
            if val:
                if key == "POS":
                    pos_parts = [val]
                    ti += 1
                    cont = _collect_multi_val(tokens, ti)
                    pos_parts.extend(cont)
                    ti += len(cont)
                    if len(pos_parts) >= 1: result["sdef_pos_x"] = pos_parts[0]
                    if len(pos_parts) >= 2: result["sdef_pos_y"] = pos_parts[1]
                    if len(pos_parts) >= 3: result["sdef_pos_z"] = pos_parts[2]
                    continue
                elif key in field_map:
                    result[field_map[key]] = val
                    ti += 1
                    # 多值参数续值：VEC=1 -1 0
                    if key in multi_val_params:
                        cont = _collect_multi_val(tokens, ti)
                        if cont:
                            result[field_map[key]] = " ".join([val] + cont)
                            ti += len(cont)
                    continue
                # 未知关键字（如 SUR）→ 跳过（预验证已检查）
                ti += 1
                continue
            ti += 1
            continue
        else:
            # 裸参数（无=）：POS x y z, PAR val, SUR val, …
            if upper == "POS":
                ti += 1
                vals = _collect_multi_val(tokens, ti)
                if len(vals) >= 1: result["sdef_pos_x"] = vals[0]
                if len(vals) >= 2: result["sdef_pos_y"] = vals[1]
                if len(vals) >= 3: result["sdef_pos_z"] = vals[2]
                ti += len(vals)
                continue
            elif upper in ("PAR", "SUR", "NRM", "TR", "CCC", "ARA", "RATE"):
                ti += 1
                if ti < len(tokens) and upper in field_map:
                    result[field_map[upper]] = tokens[ti]
                    ti += 1
                    continue
            ti += 1
    return result


def parse_f_tally(parts: list[str], tally_dict: dict) -> bool | None:
    """解析 Fn:X 计数卡。
    返回 True  = 已处理（支持 F1-F8）
         False = 识别为计数卡但编号不支持 → 调用方应放入 other_cards
         None  = 不是计数卡
    """
    first = parts[0].upper()
    m = re.match(r'^F(\d+):([NPEHAS])$', first)
    if not m:
        m = re.match(r'^F(\d+)([NPEHAS])$', first)
    if not m:
        return None

    suffix = int(m.group(1))
    designator = m.group(2).upper()
    attach = " ".join(parts[1:]) if len(parts) > 1 else ""

    keys = {
        1: ("f1_enabled", "f1_surface"),
        2: ("f2_enabled", "f2_surface"),
        4: ("f4_enabled", "f4_cell"),
        5: ("f5_enabled", "f5_x"),
        6: ("f6_enabled", "f6_cell"),
        7: ("f7_enabled", "f7_cell"),
        8: ("f8_enabled", "f8_cell"),
    }

    if suffix not in keys:
        return False  # 不支持的计数卡编号

    warning = None
    en_key, val_key = keys[suffix]
    if tally_dict.get(en_key) and tally_dict.get(f"_f{suffix}_par", designator) != designator:
        prev_par = tally_dict.get(f"_f{suffix}_par", "?")
        warning = (f"F{suffix}:{prev_par} tally 被 F{suffix}:{designator} 覆盖"
                   f"（当前版本每个计数卡只支持一种粒子类型，生成时视 MODE 而定）")
    tally_dict[en_key] = True
    tally_dict[f"_f{suffix}_par"] = designator
    if suffix == 5:
        if len(parts) >= 2: tally_dict["f5_x"] = parts[1]
        if len(parts) >= 3: tally_dict["f5_y"] = parts[2]
        if len(parts) >= 4: tally_dict["f5_z"] = parts[3]
    else:
        tally_dict[val_key] = attach

    return True


def parse_cut(parts: list[str], tally_dict: dict):
    """解析 CUT:N/P/E 卡 — 展开 j-skip 到 6 个独立字段"""
    first = parts[0].upper()
    m = re.match(r'^CUT:(N|P|E|H|HE)$', first)
    if not m:
        return
    d = m.group(1).lower()
    params = parts[1:]
    raw_params = " ".join(params)
    tally_dict[f"cut_{d}_raw"] = raw_params

    expanded = _expand_j_skip(params, 6)
    field_names = ["cut_{}_t", "cut_{}_e", "cut_{}_wgt",
                   "cut_{}_tmc", "cut_{}_wc1", "cut_{}_wc2"]
    for i, name in enumerate(field_names):
        tally_dict[name.format(d)] = expanded[i]


# ── 已知但无对应 UI 的 MCNP 卡片（保留在 other_cards 中，但不警告） ──
_KNOWN_OTHER_CARDS = {
    "PHYS:N", "PHYS:P", "PHYS:E", "PHYS",
    "ACT", "MPHYS", "LCA", "PRDMP", "DBCN",
    "KCODE", "KSRC", "TOTNU", "PTRAC", "VOID", "LOST",
    "SSW", "SSR", "ESPLT", "WWE", "WWN",
    "BURN", "FMESH", "PERT", "PRINT",
}

# ── 计数修饰卡 / 时间卡 / 能量卡（带数字后缀） ──
_TALLY_MODIFIER_RE = re.compile(
    r'^(FU|FT|FQ|FC|T|E)\d+$', re.IGNORECASE
)


def parse_data_cards(data_lines: list[str]) -> dict:
    """解析数据卡段，返回 dict"""
    result = {
        "mode_n": False, "mode_p": False, "mode_e": False,
        "mode_h": False, "mode_he": False,
        "nps": "", "ctme": "", "nonu": False,
        "materials": [], "sources": [], "tallies": {},
        "other_cards": [], "e0_values": [], "warnings": [],
    }

    data = [l for l in data_lines
            if l.strip()]  # 保留 C 注释行，后续手动放入 other_cards

    i = 0
    while i < len(data):
        raw_line = data[i]
        line = strip_comment(raw_line.strip())
        if not line:
            i += 1
            continue

        # C 注释行保留到 other_cards（C 后跟至少一个空格，CUT 不是注释）
        if re.match(r'^C\s', line, re.IGNORECASE):
            result["other_cards"].append(raw_line)
            i += 1
            continue

        parts = line.split()
        first = parts[0].upper()

        if first == "MODE":
            for p in parts[1:]:
                p_upper = p.upper()
                if p_upper == "N": result["mode_n"] = True
                elif p_upper == "P": result["mode_p"] = True
                elif p_upper == "E": result["mode_e"] = True
                elif p_upper == "H": result["mode_h"] = True
                elif p_upper == "HE": result["mode_he"] = True
            i += 1
        elif first == "NPS":
            result["nps"] = parts[1] if len(parts) > 1 else ""
            i += 1
        elif first == "CTME":
            result["ctme"] = parts[1] if len(parts) > 1 else ""
            i += 1
        elif first == "NONU":
            result["nonu"] = True
            i += 1
        elif re.match(r'^M\d+$', first, re.IGNORECASE):
            mat = _parse_material(parts, first)
            mat_comment = extract_comment(raw_line)
            if mat_comment:
                mat.comment = mat_comment
            result["materials"].append(mat)
            i += 1
        elif first == "SDEF":
            result["sources"] = parse_sdef_simple(parts)
            # 解析分布源字段
            sdef_dict = parse_sdef_fields(parts)
            result.update(sdef_dict)
            # 收集后续 SI/SP 行
            i += 1
            sisp_lines = []
            while i < len(data):
                next_first = data[i].strip().split()[0].upper() if data[i].strip().split() else ""
                if next_first.startswith("SI") or next_first.startswith("SP"):
                    sisp_lines.append(data[i].strip())
                    i += 1
                else:
                    break
            if sisp_lines:
                result["source_mode"] = "distribution"
                # 转为 JSON 对 [{si, sp}, ...]
                pairs = []
                for line in sisp_lines:
                    upper = line.strip().split()[0].upper() if line.strip().split() else ""
                    if upper.startswith("SI"):
                        pairs.append({"si": line.strip(), "sp": ""})
                    elif upper.startswith("SP"):
                        if pairs and not pairs[-1]["sp"]:
                            pairs[-1]["sp"] = line.strip()
                        else:
                            pairs.append({"si": "", "sp": line.strip()})
                result["sdef_raw_text"] = json.dumps(pairs, ensure_ascii=False)
        elif re.match(r'^F\d+:', first) or re.match(r'^F\d+$', first):
            handled = parse_f_tally(parts, result["tallies"])
            if handled is False:
                # 计数卡编号超出 F1-F8 支持范围 → 保留原样
                result["other_cards"].append(line)
            elif handled is True:
                pass  # 已处理
            elif handled is None:
                # 裸 Fn 无粒子标识符（如 F1）→ 保留原样
                result["other_cards"].append(line)
            i += 1
        elif re.match(r'^E0?$', first):
            # 仅 E / E0 是全局能谱网格；En (n≥1) 是计数专用能谱，归入 other_cards
            # 支持 MCNP nlog/nlin 语法（如 1 200log 200）
            vals = []
            ti = 1
            while ti < len(parts):
                token = parts[ti]
                # 识别 nlog / nlin / nI（MCNP E0 插值语法）
                nl_m = re.match(r'^(\d+)(LOG|LIN|I)$', token.upper())
                if nl_m and vals:
                    count = int(nl_m.group(1))
                    curve = nl_m.group(2)
                    ti += 1
                    if ti < len(parts):
                        # nLOG/nLIN:  <start> <nLOG> <end>
                        try:
                            end_val = float(parts[ti])
                            ti += 1
                            start_val = vals[-1]
                        except ValueError:
                            break
                    elif curve == "I" and len(vals) >= 2:
                        # nI:  <start> <end> <nI>（末尾无后续值）
                        end_val = vals.pop()
                        start_val = vals[-1]
                    else:
                        break
                    is_log = (curve == "LOG")
                    # 记录原始参数，让 UI 填入正常 E0 字段而非自定义网格
                    result["e0_parametric"] = True
                    result["e0_min"] = str(start_val)
                    result["e0_max"] = str(end_val)
                    result["e0_bins"] = count
                    result["e0_log"] = is_log
                    if is_log:
                        log_min = math.log10(max(start_val, 1e-99))
                        log_max = math.log10(end_val)
                        for j in range(1, count + 1):
                            vals.append(10.0 ** (log_min + j * (log_max - log_min) / count))
                    else:
                        for j in range(1, count + 1):
                            vals.append(start_val + j * (end_val - start_val) / count)
                    continue
                try:
                    vals.append(float(token))
                    ti += 1
                except ValueError:
                    break
            if vals:
                result["e0_values"] = vals
            i += 1
        elif first.startswith("CUT:"):
            parse_cut(parts, result["tallies"])
            i += 1
        elif first == "PHYS:N":
            expanded = _expand_j_skip(parts[1:], 5)
            for key in ["phys_n_emax", "phys_n_ie", "phys_n_nubar",
                         "phys_n_rgas", "phys_n_idm"]:
                result[key] = expanded[0]
                expanded = expanded[1:]
            i += 1
        elif first == "PHYS:P":
            expanded = _expand_j_skip(parts[1:], 3)
            result["phys_p_emin"] = expanded[0]
            result["phys_p_isnp"] = expanded[1]
            result["phys_p_ff"] = expanded[2]
            i += 1
        elif first == "PHYS:E":
            expanded = _expand_j_skip(parts[1:], 2)
            result["phys_e_emin"] = expanded[0]
            result["phys_e_isne"] = expanded[1]
            i += 1
        elif first == "PHYS:H":
            expanded = _expand_j_skip(parts[1:], 6)
            result["phys_h_emax"] = expanded[0]
            result["phys_h_ie"] = expanded[1]
            result["phys_h_ipr"] = expanded[2]
            result["phys_h_rgas"] = expanded[3]
            result["phys_h_emin"] = expanded[4]
            result["phys_h_ecut"] = expanded[5]
            i += 1
        elif first == "PHYS:HE":
            expanded = _expand_j_skip(parts[1:], 6)
            result["phys_he_emax"] = expanded[0]
            result["phys_he_ie"] = expanded[1]
            result["phys_he_ipr"] = expanded[2]
            result["phys_he_rgas"] = expanded[3]
            result["phys_he_emin"] = expanded[4]
            result["phys_he_ecut"] = expanded[5]
            i += 1
        elif first.startswith("SI") or first.startswith("SP"):
            i += 1
        elif first in _KNOWN_OTHER_CARDS or _TALLY_MODIFIER_RE.match(first):
            # 标准 MCNP 卡片但无对应 UI，保留原样到 other_cards
            result["other_cards"].append(line)
            i += 1
        else:
            result["other_cards"].append(line)
            i += 1

    return result
