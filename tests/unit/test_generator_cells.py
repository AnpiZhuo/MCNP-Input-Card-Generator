"""生成器单测：栅元卡 / 曲面卡 pass-through。"""
from app.models import CellRow
from app.generator.inp_generator import _generate_cells, _generate_surfaces
from tests.conftest import _cell


def test_empty_cells_no_output():
    assert _generate_cells([]) == []


def test_void_cell_no_density():
    row = CellRow(kind="cell", cell=_cell(number=1, material="0", density="",
                                          surface_expr="-1"))
    lines = _generate_cells([row])
    assert lines == ["1  0    -1"]


def test_material_m1_prefix_stripped():
    row = CellRow(kind="cell", cell=_cell(number=2, material="M1", density="-11.34",
                                          surface_expr="-2 3"))
    lines = _generate_cells([row])
    assert lines[0].startswith("2  1  -11.34  -2 3")


def test_imp_vol_pwt_emitted():
    row = CellRow(kind="cell", cell=_cell(
        number=1, material="1", density="-1.0", surface_expr="-1",
        imp_n="1", imp_p="0", imp_e="0.5", vol="100", pwt="2.0",
    ))
    lines = _generate_cells([row])
    text = " ".join(lines)
    assert "IMP:N=1" in text
    assert "IMP:P=0" in text
    assert "IMP:E=0.5" in text
    assert "VOL=100" in text
    assert "PWT=2.0" in text


def test_u_fill_lat_trcl_tmp_ext_fcl_emitted():
    row = CellRow(kind="cell", cell=_cell(
        number=1, material="1", density="-1.0", surface_expr="-1",
        u="2", fill="0", lat="1", trcl="1", tmp="2.53e-8", ext="1.5", fcl="0.25",
    ))
    lines = _generate_cells([row])
    text = " ".join(lines)
    for tok in ("U=2", "FILL=0", "LAT=1", "TRCL=1", "TMP=2.53e-8", "EXT=1.5", "FCL=0.25"):
        assert tok in text, f"缺少 {tok}: {text}"


def test_comment_emitted():
    row = CellRow(kind="cell", cell=_cell(number=1, material="0", density="",
                                          surface_expr="-1", comment="inner cell"))
    lines = _generate_cells([row])
    assert any("$ inner cell" in l for l in lines)


def test_long_line_wrapped_to_continuation():
    # 多参数导致超 80 列 → 核心行 + 5 空格续行
    # 注：_generate_cells 只在"核心行超 80"时拆一次续行；续行内容自身可能仍超 80 列，
    #     最终 80 列收紧由 generate_inp_from_deck 末端的 _wrap_long_lines 负责。
    row = CellRow(kind="cell", cell=_cell(
        number=1, material="1", density="-1.0",
        surface_expr="-1 2 -3 4 -5 6 -7 8 -9 10",
        imp_n="1", imp_p="1", imp_e="1", vol="100", pwt="2",
        u="1", fill="0", lat="1", trcl="1", tmp="2.53e-8",
        other_params="GEO=2  WWG=1  PD=1",
    ))
    lines = _generate_cells([row])
    assert len(lines) >= 2, f"应产生续行: {lines}"
    # 续行必须 5 空格开头
    assert lines[1].startswith("     "), lines[1]


def test_raw_condition_line_passthrough():
    row = CellRow(kind="raw", text="#ifdef ENDF7")
    lines = _generate_cells([row])
    assert lines == ["#ifdef ENDF7"]


def test_imp_normalized_to_all_cells():
    """任一栅元显式写 IMP → 全部结构化栅元补齐该粒子条目（缺省补 1）。"""
    rows = [
        CellRow(kind="cell", cell=_cell(number=1, material="1", density="-1.0",
                                        surface_expr="-1", imp_n="1", imp_p="1", imp_e="1")),
        CellRow(kind="cell", cell=_cell(number=2, material="0", density="",
                                        surface_expr="-2")),
    ]
    lines = _generate_cells(rows)
    assert "IMP:N=1  IMP:P=1  IMP:E=1" in lines[0]
    assert "IMP:N=1  IMP:P=1  IMP:E=1" in lines[1]


def test_imp_explicit_values_preserved_missing_filled_with_one():
    """显式 0/0.5 保留；同粒子缺省栅元补 1；没人写的粒子不输出。"""
    rows = [
        CellRow(kind="cell", cell=_cell(number=1, material="1", density="-1.0",
                                        surface_expr="-1", imp_p="0")),
        CellRow(kind="cell", cell=_cell(number=2, material="0", density="",
                                        surface_expr="-2", imp_p="0.5")),
    ]
    lines = _generate_cells(rows)
    assert "IMP:P=0" in lines[0]
    assert "IMP:P=0.5" in lines[1]
    assert "IMP:N" not in " ".join(lines)  # 没人写 N → 不输出


def test_imp_absent_everywhere_no_output():
    """全部栅元都没写 IMP → 不输出任何 IMP（MCNP 默认全 1）。"""
    rows = [
        CellRow(kind="cell", cell=_cell(number=1, material="0", density="",
                                        surface_expr="-1")),
        CellRow(kind="cell", cell=_cell(number=2, material="0", density="",
                                        surface_expr="-2")),
    ]
    lines = _generate_cells(rows)
    assert all("IMP" not in line for line in lines)


def test_surfaces_passthrough_strips_blank_lines():
    out = _generate_surfaces("1  rcc  0 0 0  0 10 0  2\n\n\n2  pz  10\n")
    assert out == ["1  rcc  0 0 0  0 10 0  2", "2  pz  10"]


def test_surfaces_empty():
    assert _generate_surfaces("") == []
    assert _generate_surfaces("\n  \n") == []
