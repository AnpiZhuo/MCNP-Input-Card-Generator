"""
分节解析：栅元/曲面/数据卡识别与分段
Section Splitting: identify and split MCNP input into cell, surface, and data card sections.

MCNP input files follow a strict section ordering: title line, cell cards, blank line,
surface cards, blank line, data cards. This module detects section boundaries by
examining each line's content and classifying it as a cell, surface, or data card.
"""
import re
from ..banners import is_generator_banner
from .lines import _SURFACE_TYPES


def _is_surface_line(line: str) -> bool:
    """判断一行是否为曲面卡（而非栅元卡）
    Check whether a line is a surface card (as opposed to a cell card).

    A surface card starts with a numeric ID, followed by a surface mnemonic
    (e.g., "P", "PX", "S", "RPP") from the _SURFACE_TYPES set.

    Supports optional TRn reference after the surface number:
        j [n] a list   where n > 0 = TRn, n < 0 = periodic with surface |n|
        n can be explicit "TR1" or a bare integer "1".

    Args:
        line: A normalized MCNP input line.

    Returns:
        True if the line matches the surface card pattern, False otherwise.
    """
    parts = line.split()
    if len(parts) < 2:
        return False
    if not parts[0].lstrip('-').isdigit():
        return False

    # Determine where the surface type keyword sits
    surf_type_idx = 1
    second = parts[1].upper()

    # Case A: Explicit TRn prefix (e.g. "TR1", "TR99")
    if re.match(r'^TR\d+$', second) and len(parts) > 2:
        surf_type_idx = 2
    # Case B: Bare integer TRn reference / periodic surface index (e.g. "2", "-3")
    elif len(parts) > 2 and parts[1].lstrip('-').isdigit():
        try:
            n_val = int(parts[1])
            if n_val != 0:  # 0 = no transform, skip
                surf_type_idx = 2
        except ValueError:
            pass

    surf_type = parts[surf_type_idx].upper()
    return surf_type in _SURFACE_TYPES


def _is_cell_line(line: str) -> bool:
    """判断一行是否为栅元卡
    Check whether a line is a cell card.

    A cell card starts with a numeric ID, followed by either a material number
    (0 or a positive/negative integer) or an Mn material reference.

    Args:
        line: A normalized MCNP input line.

    Returns:
        True if the line matches the cell card pattern, False otherwise.
    """
    parts = line.split()
    if len(parts) < 2:
        return False
    if not parts[0].lstrip('-').isdigit():
        return False
    second = parts[1]
    # Cell line second token is a material number (0 or integer) or an Mn reference
    if second == "0" or second.lstrip('-').isdigit():
        return True
    # 大小写不敏感（F-H）：MCNP 材料引用不区分大小写，小写 m1 应与 M1 同样识别
    if second[0] in "Mm" and len(second) > 1 and second[1:].isdigit():
        return True
    return False


def split_sections(lines: list[str]) -> tuple[str, list[str], list[str], list[str]]:
    """
    按栅元→曲面→数据 分节。
    Split normalized lines into MCNP sections: title, cells, surfaces, data cards.

    MCNP input structure: title line, blank line, cell cards, blank line,
    surface cards, blank line, data cards. This function detects boundaries
    by classifying each line's content after the title.

    Args:
        lines: A list of normalized lines (output of normalize_lines).

    Returns:
        A tuple of (title, cell_lines, surface_lines, data_lines).
        - title: The title line string.
        - cell_lines: List of cell card lines.
        - surface_lines: List of surface card lines.
        - data_lines: List of data card lines (MODE, NPS, SDEF, materials, etc.).
    """
    title = ""
    cell_lines = []
    surf_lines = []
    data_lines = []

    if not lines:
        return title, cell_lines, surf_lines, data_lines

    # Skip leading blank lines to find the title
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1

    if start >= len(lines):
        return title, cell_lines, surf_lines, data_lines

    # Determine title: first non-empty line, unless it looks like a cell/comment card
    first_line = lines[start].strip()
    first_part = first_line.split()[0].upper() if first_line.split() else ""
    # Cell cards start with a digit; comments start with C (exact "C", not "Co"/"Cu"/"Ca")
    if first_part.isdigit() or first_part == 'C':
        title = "inp_CARD"
    else:
        title = first_line
    remaining = lines[start + 1:] if first_line == title else lines[start:]

    # Keywords that unambiguously indicate a data card (used for section boundary detection)
    DATA_KEYWORDS = {
        "MODE", "NPS", "CTME", "NONU", "SDEF", "PRDMP",
        "KCODE", "KSRC", "TOTNU", "PTRAC", "VOID", "LOST",
        "DBCN", "PERT", "SSW", "SSR", "ESPLT", "WWE", "WWN",
        "PHYS:N", "PHYS:P", "PHYS:E", "PHYS:H", "PHYS:HE", "PHYS",
        "BURN", "FMESH", "FC", "F", "F0",
        "PRINT", "ACT", "MPHYS", "LCA",
    }
    # Regex patterns for data card line starts
    DATA_PATTERNS = [
        re.compile(r'^M\d+$', re.IGNORECASE),
        re.compile(r'^SI\d*$', re.IGNORECASE),
        re.compile(r'^SP\d*$', re.IGNORECASE),
        re.compile(r'^E\d*$', re.IGNORECASE),
        re.compile(r'^CUT:', re.IGNORECASE),
        re.compile(r'^MT\d+$', re.IGNORECASE),
        re.compile(r'^\*?TR\d+$', re.IGNORECASE),
        # D-03：F 家族计数卡（含 */+ 前缀与 F5X 环探测器形态，对齐 parse_data_cards 入口门）
        re.compile(r'^[*+]?F\d+:', re.IGNORECASE),
        re.compile(r'^[*+]?F\d+$', re.IGNORECASE),
        re.compile(r'^[*+]?F\d+[XYZ]:?', re.IGNORECASE),
        re.compile(r'^[*+]?F(?:IP|IR|IC)\d+', re.IGNORECASE),
        re.compile(r'^[*+]?FM\d+', re.IGNORECASE),
        re.compile(r'^[*+]?FC\d+', re.IGNORECASE),
        # D-03：计数/源分布辅助卡缺口词条（节首直出时也必须识别为数据卡 → data_lines → other_cards 兜底）
        re.compile(r'^C\d+$', re.IGNORECASE),      # Cn 余弦分箱
        re.compile(r'^DE\d+$', re.IGNORECASE),     # DEn 剂量能量
        re.compile(r'^DF\d+$', re.IGNORECASE),     # DFn 剂量函数
        re.compile(r'^FS\d+$', re.IGNORECASE),     # FSn 面源
        re.compile(r'^SD\d+$', re.IGNORECASE),     # SDn 源分布
        re.compile(r'^CF\d+$', re.IGNORECASE),     # CFn
        re.compile(r'^SF\d+$', re.IGNORECASE),     # SFn
        re.compile(r'^EM\d+$', re.IGNORECASE),     # EMn
        re.compile(r'^TM\d+$', re.IGNORECASE),     # TMn
        re.compile(r'^CM\d+$', re.IGNORECASE),     # CMn
        re.compile(r'^TF\d+$', re.IGNORECASE),     # TFn
        re.compile(r'^DD\d+$', re.IGNORECASE),     # DDn
        re.compile(r'^DXT$', re.IGNORECASE),       # DXT
        re.compile(r'^SB\d+$', re.IGNORECASE),     # SBn
        re.compile(r'^DS\d+$', re.IGNORECASE),     # DSn
        re.compile(r'^SC\d+$', re.IGNORECASE),     # SCn
        re.compile(r'^ELPT', re.IGNORECASE),       # ELPT:n
        re.compile(r'^NOTRN$', re.IGNORECASE),     # NOTRN
        re.compile(r'^TALNP$', re.IGNORECASE),     # TALNP
        re.compile(r'^MPLOT$', re.IGNORECASE),     # MPLOT
        re.compile(r'^RAND$', re.IGNORECASE),      # RAND
        re.compile(r'^FILES$', re.IGNORECASE),     # FILES
        re.compile(r'^IDUM$', re.IGNORECASE),      # IDUM
        re.compile(r'^RDUM$', re.IGNORECASE),      # RDUM
        re.compile(r'^FMESH', re.IGNORECASE),      # FMESHn（带编号）
        # 网格计数（契约 meshtal-visualization.md §6）：TMESHn 标题 + RMESHn/CMESHn 子卡
        re.compile(r'^TMESH', re.IGNORECASE),      # TMESHn（节首直出不误分曲面/栅元段）
        re.compile(r'^RMESH\d*', re.IGNORECASE),   # RMESHn（TMESH rect 子卡）
        re.compile(r'^CMESH\d*', re.IGNORECASE),   # CMESHn（TMESH cyl 子卡）
    ]

    # Phase-based section classification: start in "cell", transition on blank line or data patterns
    phase = "cell"
    i = 0
    while i < len(remaining):
        line = remaining[i].strip()

        # Blank line: transition to the next section (cell -> surface -> data)
        # Only non-C-comment lines count as real content for the transition,
        # so C-comment headers like "c cell card" before actual cells don't
        # trigger premature section change.
        if not line:
            if phase == "cell":
                has_real_cells = any(
                    not l.strip().upper().startswith("C")
                    for l in cell_lines
                )
                if has_real_cells:
                    phase = "surface"
            elif phase == "surface":
                phase = "data"
            i += 1
            continue

        # Continuation line (indented by 5+ spaces): append to the last line of the current phase
        if len(remaining[i]) - len(remaining[i].lstrip()) >= 5:
            if phase == "cell" and cell_lines:
                cell_lines[-1] = cell_lines[-1] + " " + line
            elif phase == "surface" and surf_lines:
                surf_lines[-1] = surf_lines[-1] + " " + line
            elif phase == "data" and data_lines:
                data_lines[-1] = data_lines[-1] + " " + line
            i += 1
            continue

        parts = line.split()
        first = parts[0].upper() if parts else ""

        # In cell or surface phase, check if the line is actually a data card
        if phase == "cell" or phase == "surface":
            is_data = False
            if first in DATA_KEYWORDS:
                is_data = True
            else:
                for pat in DATA_PATTERNS:
                    if pat.match(first):
                        is_data = True
                        break

            if is_data:
                # Data card found — switch to data phase immediately
                phase = "data"
                data_lines.append(line)
                i += 1
                continue

        # C-comment cards go to the current section (cell/surface/data) without changing phase
        if re.match(r'^C\s', line, re.IGNORECASE):
            # 生成器节头（F-A）：不吸收进任何 phase 的原始收集，防止逐代膨胀。
            # 单一拦截点 —— 节头不进 cell_lines（→ 不污染 cell.comment）、
            # 不进 surf_lines（→ 不进 deck.surfaces）、不进 data_lines（→ 不进 other_cards）。
            if is_generator_banner(line):
                i += 1
                continue
            if phase == "cell":
                cell_lines.append(line)
            elif phase == "surface":
                surf_lines.append(line)
            else:
                data_lines.append(line)
            i += 1
            continue

        # Classify the line based on the current phase
        if phase == "cell":
            if _is_surface_line(line):
                # Surface card detected — transition to surface phase
                phase = "surface"
                surf_lines.append(line)
            else:
                cell_lines.append(line)
        elif phase == "surface":
            if _is_cell_line(line) and not _is_surface_line(line):
                cell_lines.append(line)
            else:
                surf_lines.append(line)
        elif phase == "data":
            data_lines.append(line)

        i += 1

    return title, cell_lines, surf_lines, data_lines
