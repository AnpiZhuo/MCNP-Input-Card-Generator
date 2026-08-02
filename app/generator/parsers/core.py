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
from app.models import CellData, MaterialData, MaterialRow, SourceData, TallyDefinition
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
    """展开 j-skip / R / M 语法，补齐到 count 个元素。
    Expands MCNP j-skip (placeholder skipping), R (repeat), M (multiply).

    J 语法:
        "J" → 跳过一个字段（填入空串）
        "nJ" → 跳过 n 个字段
    R 语法:
        "R" → 重复前一个值 1 次 (例: 1 R → 1 1)
        "nR" → 重复前一个值 n 次 (例: 1 3R → 1 1 1 1)
    M 语法:
        "M" 后跟一个数字 → 前一个值乘以该数字 (例: 2 M 3 → 2 6)

    Examples:
        ["2j", "0", "0"] with count=6 → ["", "", "0", "0", "", ""]
        ["1", "3R"] with count=5 → ["1", "1", "1", "1", ""]
        ["2", "M", "3"] with count=4 → ["2", "6", "", ""]
    """
    result = []
    i = 0
    while i < len(params):
        p = params[i]
        u = p.upper()
        if u == "J":
            result.append("")
        elif u.endswith("J") and u[:-1].isdigit():
            for _ in range(int(u[:-1])):
                result.append("")
        elif u == "R":
            if result:
                result.append(result[-1])
        elif u.endswith("R") and u[:-1].isdigit():
            n = int(u[:-1])
            if result:
                for _ in range(n):
                    result.append(result[-1])
        elif u == "M" and i + 1 < len(params):
            i += 1
            if result:
                try:
                    prev = float(result[-1])
                    factor = float(params[i])
                    result.append(str(prev * factor))
                except ValueError:
                    result.append(params[i])
            else:
                result.append(params[i])
        else:
            result.append(p)
        i += 1
    return (result[-count:] if len(result) >= count
            else result + [""] * (count - len(result)))


def _is_d_ref(val: str) -> bool:
    """检查值是否为 Dn 分布引用（如 D1、D2）"""
    return bool(re.match(r'^D\d+$', val.strip().upper())) if val else False


def _parse_sisp_structured(sisp_lines: list[str]) -> list[dict]:
    """将 SI/SP/SB/DS 行解析为结构化分布列表（源分布卡说明.md 三/四节）。

    返回 [{"id", "paramRef", "si":{"type","values"}, "sp":{"type","values","fnCode","fnParams"},
           "sb":{"type","values"} | None, "ds":{"type","param","distributionIds"} | None}]
    """
    entries: dict[int, dict] = {}
    order: list[int] = []
    for line in sisp_lines:
        s = line.strip()
        if not s:
            continue
        # 剥 $ 注释（MCNP $ 后为注释，不参与分布值）
        if "$" in s:
            s = s.split("$", 1)[0].strip()
        upper = s.split()[0].upper() if s.split() else ""
        m = re.match(r'^(SI|SP|SB|DS)(\d+)', upper)
        if not m:
            continue
        kind, num = m.group(1), int(m.group(2))
        rest = s[m.end():].strip()
        if num not in entries:
            entries[num] = {"id": num, "paramRef": "", "si": None, "sp": None, "sb": None, "ds": None, "auto": False}
            order.append(num)
        e = entries[num]
        toks = rest.split()
        if kind == "SI":
            typ = "L"
            vals = toks
            if toks and toks[0].upper() in ("L", "H", "A", "S", "Q", "T", "F"):
                typ = toks[0].upper(); vals = toks[1:]
            e["si"] = {"type": typ, "values": vals}
        elif kind == "SP":
            sp = {"type": "", "values": [], "fnCode": "", "fnParams": []}
            if toks and re.match(r'^-\d+$', toks[0]):
                sp["fnCode"] = toks[0]; sp["fnParams"] = toks[1:]
            elif toks and toks[0].upper() in ("D", "C", "V"):
                sp["type"] = toks[0].upper(); sp["values"] = toks[1:]
            else:
                sp["values"] = toks
            e["sp"] = sp
        elif kind == "SB":
            sb = {"type": "D", "values": toks}
            if toks and toks[0] in ("-21", "-31"):
                sb["type"] = toks[0]; sb["values"] = toks[1:]
            elif toks and toks[0].upper() == "D":
                sb["type"] = "D"; sb["values"] = toks[1:]
            e["sb"] = sb
        elif kind == "DS":
            ds = {"type": "S", "param": "", "distributionIds": []}
            if toks and toks[0].upper() in ("H", "L", "S", "T", "Q"):
                ds["type"] = toks[0].upper(); toks = toks[1:]
            if ds["type"] == "T":
                pass
            elif toks:
                ds["param"] = toks[0]
                ds["distributionIds"] = toks[1:]
            e["ds"] = ds
    return [entries[n] for n in order]


def parse_cells(cell_lines: list[str]) -> list[CellData]:
    """解析栅元卡行 → CellData 列表（C 注释行关联到下一个栅元，$ 注释优先）"""
    cells = []
    pending_c = ""  # 最近的 C 注释行
    for line in cell_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.upper().startswith("C ") or stripped.upper().startswith("C\t"):
            pending_c = stripped
            continue
        comment = extract_comment(line)
        if not comment and pending_c:
            comment = pending_c[1:].strip()  # 去掉 C 前缀
        pending_c = ""
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
        pwt = ext = fcl = u_ = fill = lat = trcl = tmp = other_params = ""

        idx = surf_start
        while idx < len(parts):
            token = parts[idx]
            upper = token.upper()
            if upper.startswith("IMP:"):
                # 处理 imp:n,p=1 这种多粒子合并语法（逗号分隔粒子列表）
                imp_body = token.split("=", 1)
                if len(imp_body) == 2:
                    value = imp_body[1]
                    particles = imp_body[0][4:]  # 去掉 "IMP:" 前缀
                    for p in particles.split(","):
                        p = p.strip().lower()
                        if p == "n":
                            imp_n = value
                        elif p == "p":
                            imp_p = value
                        elif p == "e":
                            imp_e = value
                    idx += 1
                    continue
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
            elif upper.startswith("TMP="):
                tmp = token.split("=", 1)[1]
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
                # 带 = 的未知关键词 → other_params
                if "=" in token and not token[0].isdigit():
                    if other_params:
                        other_params += " " + token
                    else:
                        other_params = token
                else:
                    surf_parts.append(token)
            idx += 1

        cells.append(CellData(
            number=number, material=material, density=density,
            surface_expr=" ".join(surf_parts),
            imp_n=imp_n, imp_p=imp_p, imp_e=imp_e,
            vol=vol, pwt=pwt, ext=ext, fcl=fcl,
            u=u_, fill=fill, lat=lat, trcl=trcl,
            tmp=tmp, other_params=other_params,
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
    elif key == "X":      src.pos_x = val
    elif key == "Y":      src.pos_y = val
    elif key == "Z":      src.pos_z = val
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
                   "SUR", "NRM", "TR", "CCC", "ARA", "RATE",
                   "X", "Y", "Z", "EFF"}
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
                # 收集后续续值（支持 DIR=FERG D2、POS=x y z 等模式）
                cont = _collect_multi_val(tokens, ti)
                # POS/VEC/AXS 有特殊拆分逻辑
                if key in ("POS", "VEC", "AXS"):
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
                # 所有已知参数都可能带 F-keyword 续值（如 DIR=FERG D2、X=FERG D2、CEL=FERG D5）
                if key in _KNOWN_KEYS and cont:
                    # 遇到已知 SDEF key 则停止消耗（防止 erg = d1 x = d2 吃 x）
                    real_cont = []
                    for c in cont:
                        if c.upper() in _KNOWN_KEYS:
                            break
                        real_cont.append(c)
                    if real_cont:
                        cont_str = " ".join(real_cont)
                        ti += len(real_cont)
                        if key == "X":
                            src.pos_x = (src.pos_x + " " + cont_str).strip()
                        elif key == "Y":
                            src.pos_y = (src.pos_y + " " + cont_str).strip()
                        elif key == "Z":
                            src.pos_z = (src.pos_z + " " + cont_str).strip()
                        elif key == "EFF":
                            src.sdef_extra = (src.sdef_extra + " " + cont_str).strip()
                        else:
                            # 通用：key 小写即为 SourceData 属性名（DIR→dir_ 特殊处理）
                            attr = "dir_" if key == "DIR" else key.lower()
                            cur = getattr(src, attr, "")
                            setattr(src, attr, (cur + " " + cont_str).strip())
                    continue
                # 其他已知单值参数（X/Y/Z/EFF/CEL/TME 等）：续值留回流重新处理
                # 未知参数 → 累加到 sdef_extra 避免静默丢失
                if key not in _KNOWN_KEYS:
                    extra = f"{key}={val}"
                    if cont:
                        extra += " " + " ".join(cont)
                        ti += len(cont)
                    src.sdef_extra = (src.sdef_extra + " " + extra).strip()
            else:
                ti += 1
                if ti < len(tokens):
                    _apply_sdef_param(src, key, tokens[ti])
                    ti += 1
                    # key= 后跟续值（如 pos= -5 0 0 或 par= D1 或 X= FERG D2）
                    if key in ("POS", "VEC", "AXS"):
                        cont = _collect_multi_val(tokens, ti)
                        if cont:
                            if key == "POS":
                                all_vals = [tokens[ti - 1]] + cont
                                if len(all_vals) >= 1: src.pos_x = all_vals[0]
                                if len(all_vals) >= 2: src.pos_y = all_vals[1]
                                if len(all_vals) >= 3: src.pos_z = all_vals[2]
                            elif key == "VEC":
                                src.vec = " ".join([tokens[ti - 1]] + cont)
                            elif key == "AXS":
                                src.axs = " ".join([tokens[ti - 1]] + cont)
                            ti += len(cont)
                    elif key in _KNOWN_KEYS:
                        cont = _collect_multi_val(tokens, ti)
                        real_cont = []
                        for c in cont:
                            if c.upper() in _KNOWN_KEYS:
                                break
                            real_cont.append(c)
                        if real_cont:
                            cont_str = " ".join(real_cont)
                            ti += len(real_cont)
                            if key == "X":
                                src.pos_x = (src.pos_x + " " + cont_str).strip()
                            elif key == "Y":
                                src.pos_y = (src.pos_y + " " + cont_str).strip()
                            elif key == "Z":
                                src.pos_z = (src.pos_z + " " + cont_str).strip()
                            elif key == "EFF":
                                src.sdef_extra = (src.sdef_extra + " " + cont_str).strip()
                            else:
                                attr = "dir_" if key == "DIR" else key.lower()
                                cur = getattr(src, attr, "")
                                setattr(src, attr, (cur + " " + cont_str).strip())
                    continue
        else:
            # 裸参数（无 = 号）
            # 通用：如果下一个 token 是 =，则必然是 key = value 带空格语法
            if ti + 2 < len(tokens) and tokens[ti + 1] == "=":
                tokens[ti] = f"{token}={tokens[ti + 2]}"
                del tokens[ti + 1:ti + 3]
                continue
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
        "X": "sdef_pos_x", "Y": "sdef_pos_y", "Z": "sdef_pos_z",
    }
    multi_val_params = {"VEC", "AXS"}  # 多值参数（key=val 后跟空格续值）
    _FKEY_PARAMS = {"DIR", "ERG", "WGT", "PAR", "X", "Y", "Z", "TME"}  # F-关键字续值（DIR=FERG D2、X=FERG D2 等）
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
                    # 续值收集（VEC=1 -1 0, DIR=FERG D2 等）
                    cont = _collect_multi_val(tokens, ti)
                    if cont:
                        # 遇到已知 SDEF key 则停止消耗（防止 erg = d1 x = d2 吃 x）
                        real_cont = []
                        for c in cont:
                            if c.upper() in field_map or c.upper() in ("EFF", "POS"):
                                break
                            real_cont.append(c)
                        if real_cont:
                            cont_str = " ".join(real_cont)
                            ti += len(real_cont)
                            result[field_map[key]] = " ".join([val] + real_cont)
                    continue
                # 未知参数 → 累加到 sdef_extra
                extra = f"{key}={val}"
                ti += 1
                cont = _collect_multi_val(tokens, ti)
                if cont:
                    extra += " " + " ".join(cont)
                    ti += len(cont)
                result["sdef_extra"] = (result.get("sdef_extra", "") + " " + extra).strip()
                continue
            # key= 无值（如 pos= -5 0 0）→ 下一个 token 是值
            ti += 1
            if ti < len(tokens):
                next_val = tokens[ti]
                if key == "POS":
                    pos_parts = [next_val]
                    ti += 1
                    cont = _collect_multi_val(tokens, ti)
                    pos_parts.extend(cont)
                    ti += len(cont)
                    if len(pos_parts) >= 1: result["sdef_pos_x"] = pos_parts[0]
                    if len(pos_parts) >= 2: result["sdef_pos_y"] = pos_parts[1]
                    if len(pos_parts) >= 3: result["sdef_pos_z"] = pos_parts[2]
                elif key in field_map:
                    result[field_map[key]] = next_val
                    ti += 1
                    # VEC/AXS 多值
                    if key in ("VEC", "AXS"):
                        cont = _collect_multi_val(tokens, ti)
                        if cont:
                            result[field_map[key]] = " ".join([next_val] + cont)
                            ti += len(cont)
                    # F-keyword 续值
                    elif key in _FKEY_PARAMS:
                        cont = _collect_multi_val(tokens, ti)
                        real_cont = []
                        for c in cont:
                            if c.upper() in field_map or c.upper() in ("EFF", "POS"):
                                break
                            real_cont.append(c)
                        if real_cont:
                            result[field_map[key]] = " ".join([next_val] + real_cont)
                            ti += len(real_cont)
                else:
                    # 未知参数
                    result["sdef_extra"] = (result.get("sdef_extra", "") + f" {key}={next_val}").strip()
                    ti += 1
            continue
        else:
            # 裸参数（无 = 号）
            # 通用：如果下一个 token 是 =，则必然是 key = value 带空格语法
            if ti + 2 < len(tokens) and tokens[ti + 1] == "=":
                tokens[ti] = f"{token}={tokens[ti + 2]}"
                del tokens[ti + 1:ti + 3]
                continue
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
    # POS=Dn（矢量分布）→ 三个分量同引用（否则再生成会退化成 X=D1 丢失三元组语义）
    _px = result.get("sdef_pos_x", "")
    if _is_d_ref(_px) and not result.get("sdef_pos_y") and not result.get("sdef_pos_z"):
        result["sdef_pos_y"] = _px
        result["sdef_pos_z"] = _px
    return result


def parse_f_tally(parts: list[str], tally_defs: list) -> bool | None:
    """解析 Fn:X 计数卡 → 追加 TallyDefinition 到 tally_defs 列表。

    F5 处理所有后续 token 为参数串（支持多点: x y z R0 x y z R0 …）。
    其余类型用空格拼接后续 token。

    返回 True  = 已处理
         False = 识别为计数卡但编号不支持 → 调用方应放入 other_cards
         None  = 不是计数卡
    """
    first = parts[0].upper()
    fn_prefix = ""
    # 检测 *F 或 +F 前缀
    pre_m = re.match(r'^([*+])(.+)', first)
    if pre_m:
        fn_prefix = pre_m.group(1)
        first = pre_m.group(2)  # "F4:N" 去掉前缀后重新匹配
    # 通量成像 FIPn / FIRn / FICn
    img_m = re.match(r'^(FIP|FIR|FIC)(\d+):([NPEHAS])$', first)
    if not img_m:
        img_m = re.match(r'^(FIP|FIR|FIC)(\d+)([NPEHAS])$', first)
    if img_m:
        fn_prefix = img_m.group(1)          # "FIP", "FIR", "FIC"
        suffix = int(img_m.group(2))
        designator = img_m.group(3).upper()
        number_suffix = ""
    else:
        m = re.match(r'^F(\d+):([NPEHAS])$', first)
        if not m:
            m = re.match(r'^F(\d+)([NPEHAS])$', first)
        if not m:
            m = re.match(r'^F(\d+)([XYZ]):([NPEHAS])$', first)   # F5X:N 环探测器
        if not m:
            m = re.match(r'^F(\d+)([XYZ])([NPEHAS])$', first)    # F5XN（无冒号）
        if not m:
            return None

        suffix_str, designator = m.group(1), m.group(2).upper()
        number_suffix = ""
        if m.lastindex == 3:
            # F5X:N → m=(5, X, N)  环探测器轴字母在 group(2)
            number_suffix = m.group(2).upper()
            designator = m.group(3).upper()
        suffix = int(suffix_str)

    # Tally type is determined by the last digit of suffix:
    # F1/F11/F21… → F1 (surface current), F5/F15/F25… → F5 (point detector), etc.
    type_map = {1: "F1", 2: "F2", 4: "F4", 5: "F5",
                6: "F6", 7: "F7", 8: "F8"}
    base = suffix % 10
    if base not in type_map:
        return False

    tally_type = type_map[base]
    params = " ".join(parts[1:]) if len(parts) > 1 else ""

    # 查找同 type+number 的已有定义，合并粒子
    existing = None
    for td in tally_defs:
        if td.type == tally_type and td.number == suffix:
            existing = td
            break

    if existing:
        p_lower = designator.lower()
        if p_lower not in [p.lower() for p in existing.particles]:
            existing.particles.append(p_lower)
        if fn_prefix and not existing.fn_prefix:
            existing.fn_prefix = fn_prefix
    else:
        tally_defs.append(TallyDefinition(
            type=tally_type, number=suffix,
            particles=[designator.lower()],
            params=params,
            fn_prefix=fn_prefix,
            number_suffix=number_suffix,
        ))

    return True


def parse_cut(parts: list[str], tally_dict: dict):
    """解析 CUT:N/P/E 卡 — 展开 j-skip 到 5 个独立字段 (C810: T E WC1 WC2 SWTM)"""
    first = parts[0].upper()
    m = re.match(r'^CUT:(N|P|E|H|HE|D|T|A)$', first)
    if not m:
        return
    d = m.group(1).lower()
    params = parts[1:]
    raw_params = " ".join(params)
    tally_dict[f"cut_{d}_raw"] = raw_params

    expanded = _expand_j_skip(params, 5)
    field_names = ["cut_{}_t", "cut_{}_e", "cut_{}_wc1",
                   "cut_{}_wc2", "cut_{}_swtm"]
    for i, name in enumerate(field_names):
        tally_dict[name.format(d)] = expanded[i]


# ── 已知但无对应 UI 的 MCNP 卡片（保留在 other_cards 中，但不警告） ──
_KNOWN_OTHER_CARDS = {
    "PHYS:N", "PHYS:P", "PHYS:E", "PHYS",
    "MPHYS", "LCA", "PRDMP", "DBCN",
    "KCODE", "KSRC", "TOTNU", "PTRAC", "VOID", "LOST",
    "SSW", "SSR", "ESPLT", "WWE", "WWN",
    "BURN", "FMESH", "PERT",
}

# ── 计数修饰卡 / 时间卡 / 能量卡（带数字后缀）
_TALLY_MODIFIER_RE = re.compile(
    r'^(FU|FT|FQ|FC|T|E)\d+$', re.IGNORECASE
)


def _parse_card_with_continuation(data: list[str], i: int, first: str, parts: list[str]) -> tuple[list[float], int]:
    """通用续行卡片解析：解析 E0/En/Tn 的 nlog/nlin 语法 + 续行值收集
    返回 (values, new_i)，new_i 指向最后一个续行
    """
    import sys
    print(f"[E0DBG] _parse_card_with_continuation: first={first}, parts={parts}", file=sys.stderr)
    vals: list[float] = []
    ti = 1
    while ti < len(parts):
        token = parts[ti]
        nl_m = re.match(r'^(\d+)(LOG|LIN|I)$', token.upper())
        if nl_m and vals:
            count = int(nl_m.group(1))
            curve = nl_m.group(2)
            ti += 1
            if ti < len(parts):
                try:
                    end_val = float(parts[ti]); ti += 1
                    start_val = vals[-1]
                except ValueError: break
            elif curve == "I" and len(vals) >= 2:
                end_val = vals.pop(); start_val = vals[-1]
            else: break
            is_log = (curve == "LOG")
            for j in range(1, count + 1):
                vals.append(10.0 ** (math.log10(max(start_val, 1e-99)) + j * (math.log10(end_val) - math.log10(max(start_val, 1e-99))) / count) if is_log else start_val + j * (end_val - start_val) / count)
            continue
        try:
            vals.append(float(token))
            ti += 1
        except ValueError: break
    # 收集续行值
    while i + 1 < len(data):
        nr = data[i + 1].strip()
        if not nr: i += 1; continue
        nf = nr.split()[0].upper()
        if re.match(r'^[A-Z][A-Z0-9]*$', nf) or nf.startswith("C"): break
        for tok in nr.split():
            try: vals.append(float(tok))
            except: break
        i += 1
    return vals, i


def parse_data_cards(data_lines: list[str]) -> dict:
    """解析数据卡段，返回 dict"""
    result = {
        "mode_n": False, "mode_p": False, "mode_e": False,
        "mode_h": False, "mode_he": False,
        "mode_d": False, "mode_t": False, "mode_a": False,
        "nps": "", "ctme": "", "nonu": False,
        "materials": [], "sources": [], "tallies": {},
        "tally_defs": [], "e_cards_lines": [],
        "kcode_nsrc": "", "kcode_rkk": "", "kcode_ikz": "",
        "kcode_kct": "", "kcode_knrm": "",
        "ksrc_points": [],  # list of {"x":..., "y":..., "z":...}
        "source_mode": "fixed",
        "other_cards": [], "e0_values": [], "warnings": [],
        "tr_cards": [], "t_cards_lines": [],
    }

    data = [l for l in data_lines
            if l.strip()]  # 保留 C 注释行，后续手动放入 other_cards

    i = 0
    pending_c = ""  # 最近的 C 注释行（关联到下一个 M 卡）
    while i < len(data):
        raw_line = data[i]
        line = strip_comment(raw_line.strip())
        if not line:
            i += 1
            continue

        # C 注释行缓冲（C 后跟至少一个空格，CUT 不是注释）；若后续非 M 卡则回落到 other_cards
        if re.match(r'^C\s', line, re.IGNORECASE):
            pending_c = raw_line
            i += 1
            continue

        parts = line.split()
        first = parts[0].upper()

        # 非 M 卡 → 未消费的 C 注释回落 other_cards（M 卡分支自行消费）
        if not re.match(r'^M\d+$', first, re.IGNORECASE) and pending_c:
            result["other_cards"].append(pending_c)
            pending_c = ""

        if first == "MODE":
            for p in parts[1:]:
                p_upper = p.upper()
                if p_upper == "N": result["mode_n"] = True
                elif p_upper == "P": result["mode_p"] = True
                elif p_upper == "E": result["mode_e"] = True
                elif p_upper == "H": result["mode_h"] = True
                elif p_upper == "HE": result["mode_he"] = True
                elif p_upper == "D": result["mode_d"] = True
                elif p_upper == "T": result["mode_t"] = True
                elif p_upper == "A": result["mode_a"] = True
            i += 1
        elif first == "NPS":
            result["nps"] = parts[1] if len(parts) > 1 else ""
            i += 1
        elif first == "CTME":
            result["ctme"] = parts[1] if len(parts) > 1 else ""
            i += 1
        elif first == "ACT":
            result["act"] = " ".join(parts[1:]) if len(parts) > 1 else ""
            i += 1
        elif first == "PRINT":
            result["print_pr"] = " ".join(parts[1:]) if len(parts) > 1 else ""
            i += 1
        elif first == "NONU":
            result["nonu"] = True
            i += 1
        elif re.match(r'^M\d+$', first, re.IGNORECASE):
            mat = _parse_material(parts, first)
            mat_comment = extract_comment(raw_line)
            if mat_comment:
                mat.comment = mat_comment
            elif pending_c:
                mat.comment = pending_c[1:].strip()  # 去掉 C 前缀
            pending_c = ""
            result["materials"].append(mat)
            i += 1
        elif re.match(r'^MT\d+$', first, re.IGNORECASE):
            # MT 热中子卡 — 附加到对应材料
            mt_num_str = first[2:]
            mt_text = " ".join(parts[1:]) if len(parts) > 1 else ""
            found = False
            for mat in result["materials"]:
                if str(mat.number) == mt_num_str:
                    mat.mt_card = mt_text
                    found = True
                    break
            if not found:
                result["other_cards"].append(line)
            i += 1
        elif first == "SDEF":
            result["sources"] = parse_sdef_simple(parts)
            # 解析分布源字段
            sdef_dict = parse_sdef_fields(parts)
            result.update(sdef_dict)
            # 收集后续 SI/SP/SB/DS 行
            i += 1
            sisp_lines = []
            while i < len(data):
                next_first = data[i].strip().split()[0].upper() if data[i].strip().split() else ""
                if (next_first.startswith("SI") or next_first.startswith("SP")
                        or next_first.startswith("SB") or next_first.startswith("DS")):
                    sisp_lines.append(data[i].strip())
                    i += 1
                else:
                    break
            if sisp_lines:
                result["source_mode"] = "distribution"
                # 结构化分布（新）+ 旧格式 sdef_raw_text（兼容）并存
                result["sdef_distributions"] = json.dumps(_parse_sisp_structured(sisp_lines), ensure_ascii=False)
                # 旧格式：SI/SP 配对 [{si, sp}, ...]
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
        elif (re.match(r'^[*+]?F\d+:', first) or re.match(r'^[*+]?F\d+$', first)
              or re.match(r'^[*+]?F(?:IP|IR|IC)\d+:', first) or re.match(r'^[*+]?F(?:IP|IR|IC)\d+$', first)
              or re.match(r'^[*+]?F\d+[XYZ]:', first) or re.match(r'^[*+]?F\d+[XYZ][NPEHAS]$', first)):
            handled = parse_f_tally(parts, result["tally_defs"])
            if handled is False:
                # 计数卡编号超出 F1-F8 支持范围 → 保留原样
                result["other_cards"].append(line)
            elif handled is True:
                pass  # 已处理
            elif handled is None:
                # 裸 Fn 无粒子标识符（如 F1）→ 保留原样
                result["other_cards"].append(line)
            i += 1

        elif re.match(r'^E0?$', first, re.IGNORECASE):
            import sys
            print(f"[E0DBG] E0 line: {line[:80]}", file=sys.stderr)
            vals, i = _parse_card_with_continuation(data, i, first, parts)
            print(f"[E0DBG] E0 vals: {len(vals)} -> {vals[:5]}", file=sys.stderr)
            if len(vals) >= 2:
                raw = " ".join(parts[1:])
                pm = re.search(r'(\d+)(LOG|LIN|I)\s+([\d.eE+\-]+)$', raw.upper())
                if pm:
                    result["e0_parametric"] = True
                    result["e0_min"] = str(vals[0])
                    result["e0_max"] = str(vals[-1])
                    result["e0_bins"] = int(pm.group(1))
                    result["e0_log"] = pm.group(2) == "LOG"
                result["e0_values"] = vals
            i += 1
        elif first.startswith("CUT:"):
            parse_cut(parts, result["tallies"])
            i += 1
        elif first == "PHYS:N":
            expanded = _expand_j_skip(parts[1:], 5)
            for key in ["phys_n_emax", "phys_n_emcnf", "phys_n_iunr",
                         "phys_n_dnb", "phys_n_fisnu"]:
                result[key] = expanded[0]
                expanded = expanded[1:]
            i += 1
        elif first == "PHYS:P":
            expanded = _expand_j_skip(parts[1:], 5)
            for key in ["phys_p_emcpf", "phys_p_ides", "phys_p_nocoh",
                         "phys_p_ispn", "phys_p_nodop"]:
                result[key] = expanded[0]
                expanded = expanded[1:]
            i += 1
        elif first == "PHYS:E":
            expanded = _expand_j_skip(parts[1:], 10)
            for key in ["phys_e_emax", "phys_e_ides", "phys_e_iphoto",
                         "phys_e_ibad", "phys_e_istrg", "phys_e_bnum",
                         "phys_e_xnum", "phys_e_rnok", "phys_e_enum",
                         "phys_e_numb"]:
                result[key] = expanded[0]
                expanded = expanded[1:]
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
        elif first.startswith("KCODE"):
            # KCODE  NSRC RKK IKZ KCT [MSRK KNRM MRKP KC8]
            result["source_mode"] = "kcode"
            expanded = _expand_j_skip(parts[1:], 8)
            result["kcode_nsrc"] = expanded[0]
            result["kcode_rkk"] = expanded[1]
            result["kcode_ikz"] = expanded[2]
            result["kcode_kct"] = expanded[3]
            result["kcode_msrk"] = expanded[4]
            result["kcode_knrm"] = expanded[5]
            result["kcode_mrkp"] = expanded[6]
            result["kcode_kc8"] = expanded[7]
            i += 1
        elif first.startswith("HSRC"):
            # HSRC  nx xmin xmax ny ymin ymax nz zmin zmax（香农熵网格）
            result["hsrc_enabled"] = True
            result["hsrc_text"] = " ".join(parts[1:])
            i += 1
        elif first.startswith("SSW"):
            # SSW  S1 S2 ... [SYM=] [PTY=] [CEL=]（写面源）
            result["source_mode"] = "surface"
            result["ssw_surf"] = ""
            extra = []
            for tok in parts[1:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    if k.upper() == "SYM": result["ssw_sym"] = v
                    elif k.upper() == "PTY": result["ssw_pty"] = v
                    elif k.upper() == "CEL": result["ssw_cel"] = v
                    else: extra.append(tok)
                else:
                    if result["ssw_surf"]: result["ssw_surf"] += " " + tok
                    else: result["ssw_surf"] = tok
            i += 1
        elif first.startswith("SSR"):
            # SSR  [OLD|NEW] S ... [CEL=] [PTY=] [COL=] [WGT=] [TR=] [PSC=]（读面源）
            result["source_mode"] = "surface"
            result["ssr_surf"] = ""
            for tok in parts[1:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    ku = k.upper()
                    if ku == "CEL": result["ssr_cel"] = v
                    elif ku == "PTY": result["ssr_pty"] = v
                    elif ku == "COL": result["ssr_col"] = v
                    elif ku == "WGT": result["ssr_wgt"] = v
                    elif ku == "TR": result["ssr_tr"] = v
                    elif ku == "PSC": result["ssr_psc"] = v
                elif tok.upper() in ("OLD", "NEW"):
                    result["ssr_mode"] = tok.upper()
                else:
                    if result["ssr_surf"]: result["ssr_surf"] += " " + tok
                    else: result["ssr_surf"] = tok
            i += 1
        elif re.match(r'^\*?TR\d+$', first, re.IGNORECASE):
            # TRn / *TRn 变换卡 — 存入 tr_cards
            result["tr_cards"].append(raw_line)
            i += 1
        elif first.startswith("KSRC"):
            # KSRC  x y z [x y z ...] — 每三个数一组
            coords = parts[1:]
            triples = [coords[j:j+3] for j in range(0, len(coords), 3)]
            for triple in triples:
                if len(triple) == 3:
                    result["ksrc_points"].append({
                        "x": triple[0], "y": triple[1], "z": triple[2],
                    })
            i += 1
        elif re.match(r'^E\d+$', first, re.IGNORECASE):
            # En (n≥1) 能量卡: 先收续行原文再解析值
            raw_lines = [line]
            while i + 1 < len(data):
                nr = data[i + 1].strip()
                if not nr: i += 1; continue
                nf = nr.split()[0].upper()
                if re.match(r'^[A-Z][A-Z0-9]*$', nf) or nf.startswith("C"): break
                raw_lines.append(data[i + 1]); i += 1
            vals, _ = _parse_card_with_continuation(data, i, first, parts)
            result["e_cards_lines"].append("\n".join(raw_lines))
            i += 1
        elif re.match(r'^T0$', first, re.IGNORECASE):
            # T0 时间网格（同 E0 逻辑）
            vals, i = _parse_card_with_continuation(data, i, first, parts)
            if len(vals) >= 2:
                raw = " ".join(parts[1:])
                pm = re.search(r'(\d+)(LOG|LIN|I)\s+([\d.eE+\-]+)$', raw.upper())
                if pm:
                    result["t0_parametric"] = True
                    result["t0_min"] = str(vals[0])
                    result["t0_max"] = str(vals[-1])
                    result["t0_bins"] = int(pm.group(1))
                    result["t0_log"] = pm.group(2) == "LOG"
                else:
                    # 显式值列表 → 自定义文本
                    result["t0_custom_enabled"] = True
                    result["t0_custom_text"] = " ".join(str(v) for v in vals)
                result["t0_values"] = vals
            i += 1
        elif re.match(r'^T\d+$', first, re.IGNORECASE):
            # Tn (n≥1) 时间卡: 先收续行原文再解析值
            raw_lines = [line]
            while i + 1 < len(data):
                nr = data[i + 1].strip()
                if not nr: i += 1; continue
                nf = nr.split()[0].upper()
                if re.match(r'^[A-Z][A-Z0-9]*$', nf) or nf.startswith("C"): break
                raw_lines.append(data[i + 1]); i += 1
            vals, _ = _parse_card_with_continuation(data, i, first, parts)
            result["t_cards_lines"].append("\n".join(raw_lines))
            i += 1
        elif first in _KNOWN_OTHER_CARDS or _TALLY_MODIFIER_RE.match(first):
            # 标准 MCNP 卡片但无对应 UI，保留原样到 other_cards
            result["other_cards"].append(line)
            i += 1
        else:
            result["other_cards"].append(line)
            i += 1

    return result
