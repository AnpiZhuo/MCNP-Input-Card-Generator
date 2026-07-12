"""
INP 文本预验证：在解析前检查参数/字段的合法性。
所有检查均在 parse_inp_text 之前运行，确保非法参数被提前捕获。
"""
import re
from .lines import normalize_lines, strip_comment
from .sections import split_sections

# SDEF 已知参数列表（核心字段 + 额外字段）
_KNOWN_SDEF_KEYS = {
    "PAR", "ERG", "POS", "DIR", "WGT",
    "CEL", "TME", "VEC", "AXS", "RAD", "EXT",
    "SUR", "NRM", "TR", "CCC", "ARA", "RATE",
}

# MODE 已知粒子
_VALID_MODE_PARTICLES = {"N", "P", "E", "H", "HE"}


def validate_inp_text(text: str) -> list[str]:
    """
    预验证 INP 文本的合法性。

    检查项:
    - SDEF 参数是否在已知列表中（如 SUR 会被捕获）
    - MODE 粒子是否有效
    - 可根据需要扩展其他检查

    返回错误列表（空列表 = 文本合法，可以解析）。
    """
    errors = []

    lines = normalize_lines(text)
    _title, _cell_lines, _surf_lines, data_lines = split_sections(lines)

    for _raw_line in data_lines:
        stripped = _raw_line.strip()
        if not stripped:
            continue

        # 移出行内注释后识别卡片类型
        clean = strip_comment(stripped).strip()
        if not clean:
            continue

        parts = clean.split()
        first = parts[0].upper()

        if first == "SDEF":
            _check_sdef_line(parts, errors)
        elif first == "MODE":
            _check_mode_line(parts, errors)

    return errors


def _check_sdef_line(parts: list[str], errors: list[str]):
    """检查 SDEF 行：每个 KEY=value 的 KEY 是否已知。"""
    tokens = parts[1:]
    for token in tokens:
        if "=" not in token:
            # 裸参数（如 POS 命令）不含 =，不计入参数检查
            continue
        key = token.split("=", 1)[0].upper()
        if key not in _KNOWN_SDEF_KEYS:
            errors.append(
                f"SDEF 不支持的参数：{key}\n"
                f"如需使用该参数，请手动在「高级」标签页的「其他 MCNP 卡片」中添加"
            )


def _check_mode_line(parts: list[str], errors: list[str]):
    """检查 MODE 行：每个粒子类型是否有效。"""
    for p in parts[1:]:
        p_upper = p.upper()
        if p_upper not in _VALID_MODE_PARTICLES:
            errors.append(f"MODE 不支持的粒子类型：{p}")
