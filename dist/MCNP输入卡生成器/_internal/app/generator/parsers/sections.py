"""
分节解析：栅元/曲面/数据卡识别与分段
Section Splitting: identify and split MCNP input into cell, surface, and data card sections.

MCNP input files follow a strict section ordering: title line, cell cards, blank line,
surface cards, blank line, data cards. This module detects section boundaries by
examining each line's content and classifying it as a cell, surface, or data card.
"""
import re
from .lines import _SURFACE_TYPES


def _is_surface_line(line: str) -> bool:
    """判断一行是否为曲面卡（而非栅元卡）
    Check whether a line is a surface card (as opposed to a cell card).

    A surface card starts with a numeric ID, followed by a surface mnemonic
    (e.g., "P", "PX", "S", "RPP") from the _SURFACE_TYPES set.

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
    surf_type = parts[1].upper()
    # Handle TRn transformation cards where the actual surface type is the 3rd token
    if re.match(r'^TR\d+$', surf_type) and len(parts) > 2:
        surf_type = parts[2].upper()
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
    if second.startswith("M") and len(second) > 1 and second[1:].isdigit():
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
    # Cell cards start with a digit; comments start with C
    if first_part.isdigit() or (first_part.startswith('C') and len(first_part) <= 2):
        title = "inp_CARD"
    else:
        title = first_line
    remaining = lines[start + 1:] if first_line == title else lines[start:]

    # Keywords that unambiguously indicate a data card (used for section boundary detection)
    DATA_KEYWORDS = {
        "MODE", "NPS", "CTME", "NONU", "SDEF", "PRDMP",
        "KCODE", "KSRC", "TOTNU", "PTRAC", "VOID", "LOST",
        "DBCN", "PERT", "SSW", "SSR", "ESPLT", "WWE", "WWN",
        "PHYS:N", "PHYS:P", "PHYS:E", "PHYS",
        "BURN", "FMESH", "FC", "F", "F0",
    }
    # Regex patterns for data card line starts (Mnn, SIn, SPn, Fn:, Fn, FCn, En, CUT:)
    DATA_PATTERNS = [
        re.compile(r'^M\d+$', re.IGNORECASE),
        re.compile(r'^SI\d*$', re.IGNORECASE),
        re.compile(r'^SP\d*$', re.IGNORECASE),
        re.compile(r'^F\d+:', re.IGNORECASE),
        re.compile(r'^F\d+$', re.IGNORECASE),
        re.compile(r'^FC\d+$', re.IGNORECASE),
        re.compile(r'^E\d*$', re.IGNORECASE),
        re.compile(r'^CUT:', re.IGNORECASE),
    ]

    # Phase-based section classification: start in "cell", transition on blank line or data patterns
    phase = "cell"
    i = 0
    while i < len(remaining):
        line = remaining[i].strip()

        # Blank line: transition to the next section (cell -> surface -> data)
        if not line:
            if phase == "cell":
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
                # Ambiguous line: looks like a cell card — verify it's not actually a surface
                surf_type = parts[1].upper() if len(parts) > 1 else ""
                if re.match(r'^TR\d+$', surf_type) and len(parts) > 2:
                    surf_type = parts[2].upper()
                if surf_type in _SURFACE_TYPES:
                    surf_lines.append(line)
                else:
                    cell_lines.append(line)
            else:
                surf_lines.append(line)
        elif phase == "data":
            data_lines.append(line)

        i += 1

    return title, cell_lines, surf_lines, data_lines
