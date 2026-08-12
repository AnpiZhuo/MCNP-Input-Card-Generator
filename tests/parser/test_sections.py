"""解析管线单测：分节（栅元/曲面/数据卡识别）。"""
import pytest

from app.generator.parsers.sections import split_sections, _is_surface_line, _is_cell_line
from app.generator.parsers.lines import normalize_lines


def test_is_surface_line():
    assert _is_surface_line("1 rcc 0 0 0 0 10 0 2")
    assert _is_surface_line("2 pz 10")
    assert _is_surface_line("3 TR1 s 0 0 5 1")  # TRn 前缀
    assert _is_surface_line("4 2 rpp -1 1 -1 1 -1 1")  # bare 整数 TR 引用
    assert not _is_surface_line("1 1 -1")  # 栅元行


def test_is_cell_line():
    assert _is_cell_line("1 1 -1")
    assert _is_cell_line("2 0 -2 imp:n=1")
    assert _is_cell_line("3 M1 -1.0 -3")
    assert not _is_cell_line("1 rcc 0 0 0 0 10 0 2")


def test_is_cell_line_lowercase_m_reference_detected():
    # 翻新（F-H）：_is_cell_line 对小写 m1 材料引用应识别为栅元行
    # （与 parse_cells 的 MCNP 大小写不敏感语义保持一致）
    assert _is_cell_line("3 m1 -1.0 -3") is True
    assert _is_cell_line("3 M1 -1.0 -3") is True


def test_split_sections_basic():
    text = (
        "my title\n"
        "1 1 -1 imp:n=1\n"
        "2 0 -2\n"
        "\n"
        "1 rcc 0 0 0 0 10 0 2\n"
        "2 pz 10\n"
        "\n"
        "mode n\n"
        "nps 100000\n"
        "sdef pos 0 0 0\n"
    )
    lines = normalize_lines(text)
    title, cells, surfs, data = split_sections(lines)
    assert title == "my title"
    assert len(cells) == 2
    assert len(surfs) == 2
    assert any(l.upper().startswith("MODE") for l in data)
    assert any(l.upper().startswith("NPS") for l in data)
    assert any(l.upper().startswith("SDEF") for l in data)


def test_split_sections_numeric_start_title():
    lines = normalize_lines("1 1 -1\n1 rcc 0 0 0 0 10 0 2\nmode n\n")
    title, cells, surfs, data = split_sections(lines)
    assert title == "inp_CARD"  # 数字开头 → 无标题回退


def test_split_sections_material_in_data():
    text = "t\n1 1 -1\n\n1 pz 0\n\nm1 92235 0.05\nsdef pos 0 0 0\n"
    lines = normalize_lines(text)
    title, cells, surfs, data = split_sections(lines)
    assert any(l.upper().startswith("M1") for l in data)
