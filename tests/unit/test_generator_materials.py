"""生成器单测：材料卡（Mm 卡：核素行 + raw 条件行 + 选项 + MT 卡）。"""
from app.generator.inp_generator import _generate_materials
from app.models import MaterialData, MaterialRow


def _mat(**kw):
    base = dict(number=1, rows=[MaterialRow(zaid="92235.06c", fraction="-0.05")])
    base.update(kw)
    return MaterialData(**base)


def test_empty_rows_skipped():
    assert _generate_materials([_mat(rows=[])]) == []


def test_single_nuclide_continuation_format():
    lines = _generate_materials([_mat()])
    assert lines == ["M1\n     92235.06c  -0.05"]


def test_multiple_rows_each_continuation():
    mat = _mat(rows=[
        MaterialRow(zaid="92235.06c", fraction="-0.05"),
        MaterialRow(zaid="8016", fraction="0.10"),
    ])
    lines = _generate_materials([mat])
    text = "\n".join(lines)
    assert "    92235.06c  -0.05" in text
    assert "    8016  0.10" in text


def test_raw_condition_lines_preserved():
    mat = _mat(rows=[
        MaterialRow(zaid="92235.06c", fraction="-0.05"),
        MaterialRow(kind="raw", text="#ifdef MOD1"),
        MaterialRow(kind="raw", text="#endif"),
    ])
    lines = _generate_materials([mat])
    text = "\n".join(lines)
    assert "#ifdef MOD1" in text
    assert "#endif" in text


def test_comment_and_options_and_mt_card():
    mat = _mat(comment="fuel", options="nlib=.66c", mt_card="lwtr.10t")
    lines = _generate_materials([mat])
    assert lines[0] == "C  fuel"
    assert "nlib=.66c" in "\n".join(lines)
    assert "MT1  lwtr.10t" in lines


def test_zaid_normalization_applied():
    mat = _mat(rows=[MaterialRow(zaid="U-235", fraction="-0.05")])
    lines = _generate_materials([mat])
    assert "92235  -0.05" in lines[0]


def test_multiple_materials_each_cap():
    lines = _generate_materials([_mat(number=1), _mat(number=2)])
    assert any(l.startswith("M1") for l in lines)
    assert any(l.startswith("M2") for l in lines)
