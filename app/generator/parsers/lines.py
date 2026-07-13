"""
行处理工具：注释剥离 + 续行合并 + 曲面类型常量
Line Processing Utilities: comment stripping, continuation line merging, and surface type constants.

This module provides low-level line normalization for MCNP input files:
- Removing inline comments (text after $)
- Extracting comment text for preservation
- Merging continuation lines (& suffix or 5+ space indentation)
- Defining the set of known MCNP surface mnemonics.
"""
import re

_SURFACE_TYPES = {
    "P", "PX", "PY", "PZ", "SO", "S", "SX", "SY", "SZ",
    "CX", "CY", "CZ", "C/X", "C/Y", "C/Z",
    "KX", "KY", "KZ", "K/X", "K/Y", "K/Z",
    "SQ", "GQ", "TX", "TY", "TZ", "TXY", "TXZ", "TYZ",
    "RPP", "SPH", "RCC", "TRC", "REC", "ELL", "WED", "BOX", "ARB", "RHP", "HEX",
    "X", "Y", "Z",
}


def strip_comment(line: str) -> str:
    """移除 $ 后面的注释
    Strip the inline comment (everything after $) from a line.

    Args:
        line: A raw line of MCNP input text potentially containing $.

    Returns:
        The line with the $ comment suffix removed (including the $ itself).
        If no $ is present, returns the line unchanged.
    """
    idx = line.find("$")
    if idx >= 0:
        return line[:idx]
    return line


def extract_comment(line: str) -> str:
    """提取 $ 后面的注释文本（不含 $ 符号本身），无则返回空字符串
    Extract the comment text after $ (without the $ symbol itself).

    Args:
        line: A raw line of MCNP input text.

    Returns:
        The trimmed comment text after $, or an empty string if no $ is present.
    """
    idx = line.find("$")
    if idx >= 0:
        return line[idx + 1:].strip()
    return ""


def normalize_lines(raw_text: str) -> list[str]:
    """
    将原始 INP 文本标准化为独立行列表：
    Normalize raw INP text into a list of independent, ready-to-parse lines.

    Processing steps:
    1. 保留 $ 行内注释（供后续解析器提取，如栅元注释）
       Preserve inline $ comments for later extraction (e.g., cell comments).
    2. 合并续行（以 & 结尾，或下一行以 5+ 空格开头）
       Merge continuation lines (lines ending with &, or next line indented by 5+ spaces).
    3. C 注释行保留，并作为续行断点
       Preserve C comment lines; they act as continuation breakpoints.
    4. 保留空行用于分节
       Keep empty lines for downstream section splitting.

    Args:
        raw_text: The raw MCNP input file content as a single string.

    Returns:
        A list of normalized lines. Continuation lines are merged into their
        parent lines. Empty lines and C comment lines are preserved as-is.
    """
    # Split raw text into individual lines and strip trailing whitespace
    raw_lines = raw_text.split("\n")

    # C 注释行保留（不再过滤），作为续行断点
    # Keep C comment lines as-is — they serve as continuation breakpoints
    clean_lines = [line.rstrip() for line in raw_lines]

    merged = []
    current = ""
    for line in clean_lines:
        stripped = line.lstrip()
        is_c_comment = bool(stripped.upper().startswith("C"))

        # Empty line: flush current buffer and preserve the blank line
        if not line.strip():
            if current.strip():
                merged.append(current.strip())
                current = ""
            merged.append("")
            continue

        # C comment line: flush current buffer, then keep the comment as a standalone entry
        if is_c_comment:
            if current.strip():
                merged.append(current.strip())
                current = ""
            merged.append(line)
            continue

        # If we are already building a merged continuation line
        if current:
            cur_no_dollar = strip_comment(current)
            line_no_dollar = strip_comment(line)

            # Continuation by indentation: next line starts with 5+ spaces
            if len(line) - len(line.lstrip()) >= 5:
                cur_comment = extract_comment(current)
                if cur_comment:
                    current = (cur_no_dollar.strip() + " "
                               + line_no_dollar.strip() + " $ " + cur_comment)
                else:
                    current += " " + line_no_dollar.strip()
                continue
            # Continuation by ampersand: current line ends with &
            if cur_no_dollar.rstrip().endswith("&"):
                merged_no_dollar = cur_no_dollar.rstrip()[:-1].rstrip() + " " + line_no_dollar.strip()
                current_dollar = extract_comment(current)
                line_dollar = extract_comment(line)
                current = merged_no_dollar
                if current_dollar:
                    current += " $ " + current_dollar
                if line_dollar:
                    current += " $ " + line_dollar
                continue
            # No continuation: flush current and start a new one
            merged.append(current.strip())
            current = line
        else:
            # Start a new line buffer
            current = line

    # Flush any remaining buffered line
    if current.strip():
        merged.append(current.strip())

    return merged
