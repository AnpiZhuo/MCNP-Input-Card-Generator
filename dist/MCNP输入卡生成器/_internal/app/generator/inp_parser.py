"""
INP 导入解析器：将现有 MCNP 输入卡解析为 DeckData
(向后兼容 — 实际逻辑已拆分到 app.generator.parsers 包)
"""

from app.generator.parsers import parse_inp_text

# 保留旧模块级函数引用（向后兼容）
from app.generator.parsers.lines import strip_comment, extract_comment, normalize_lines
from app.generator.parsers.sections import split_sections
from app.generator.parsers.core import parse_cells, parse_surfaces, parse_data_cards
