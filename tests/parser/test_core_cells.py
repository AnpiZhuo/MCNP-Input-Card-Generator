"""解析管线单测：栅元解析与 j-skip 展开。"""
import json

import pytest

from app.generator.parsers.core import parse_cells, _expand_j_skip


# ── parse_cells ─────────────────────────────────────────
def test_parse_simple_cell():
    rows = parse_cells(["1 1 -1.0 -1 imp:n=1"])
    assert len(rows) == 1
    c = rows[0].cell
    assert c.number == 1
    assert c.material == "1"
    assert c.density == "-1.0"
    assert c.surface_expr == "-1"
    assert c.imp_n == "1"


def test_parse_void_cell_no_density():
    rows = parse_cells(["2 0 -2 imp:n=0"])
    c = rows[0].cell
    assert c.material == "0"
    assert c.density == ""
    assert c.imp_n == "0"


def test_parse_material_m1_reference():
    rows = parse_cells(["3 m1 -11.34 -3"])
    c = rows[0].cell
    assert c.material == "m1"
    assert c.density == "-11.34"
    assert c.surface_expr == "-3"


def test_parse_imp_multi_particle():
    rows = parse_cells(["1 1 -1.0 -1 imp:n,p=1"])
    c = rows[0].cell
    assert c.imp_n == "1"
    assert c.imp_p == "1"


def test_parse_imp_space_syntax():
    rows = parse_cells(["1 1 -1.0 -1 imp:n 1"])
    c = rows[0].cell
    assert c.imp_n == "1"


def test_parse_vol_pwt_u_fill_lat_trcl_tmp():
    rows = parse_cells(["1 1 -1.0 -1 vol=100 pwt=2 u=1 fill=0 lat=1 trcl=1 tmp=2.53e-8"])
    c = rows[0].cell
    assert c.vol == "100"
    assert c.pwt == "2"
    assert c.u == "1"
    assert c.fill == "0"
    assert c.lat == "1"
    assert c.trcl == "1"
    assert c.tmp == "2.53e-8"
    # 单值 fill（u=1 fill=0 lat=1）回归保护：走原循环，fill_grid 必须为空
    assert c.fill_grid == ""


# ── 格阵 fill（阶段1：fill_grid 结构化）────────────────────
def test_parse_lattice_fill_rect_17x17():
    """矩形 17×17 范围（仿 owen/assembly_17x17_mcnp.i）→ fill=范围串 + fill_grid JSON。"""
    line = ("20 0 50 -51 52 -53 lat=1 u=10 imp:n=1 fill=0:16 0:16 0:0 "
            + " ".join(["1"] * 17))
    rows = parse_cells([line])
    c = rows[0].cell
    assert c.surface_expr == "50 -51 52 -53"
    assert c.fill == "0:16 0:16 0:0"
    assert c.lat == "1"
    fg = json.loads(c.fill_grid)
    assert fg["kind"] == "lattice"
    assert fg["range"] == ["0:16", "0:16", "0:0"]
    assert fg["dims"] == [17, 17, 1]


def test_parse_lattice_fill_offset_entries():
    """3D 偏移条目 `1 (9 0 9)`（仿 prob41c）→ cells 带 dx/dy/dz。"""
    line = "10 0 -6 lat=1 u=2 imp:n=1 fill=0:2 0:1 0:0 " + "1 (9 0 9) " * 6
    rows = parse_cells([line])
    c = rows[0].cell
    assert c.fill == "0:2 0:1 0:0"
    fg = json.loads(c.fill_grid)
    assert fg["dims"] == [3, 2, 1]
    assert len(fg["cells"]) == 6
    assert fg["cells"][0] == {"u": "1", "dx": "9", "dy": "0", "dz": "9"}


def test_parse_lattice_fill_nr_repeat():
    """`17r` 元素级重复（仿 inp24）→ 展开后条目数 = 范围乘积（截断/补 0）。"""
    line = "7 4 -1.0 -4 +5 -6 +7 u=1 lat=1 fill=-8:8 -8:8 0:0 1 17r 2 14r 1 17r"
    rows = parse_cells([line])
    c = rows[0].cell
    assert c.fill == "-8:8 -8:8 0:0"
    fg = json.loads(c.fill_grid)
    assert fg["dims"] == [17, 17, 1]
    assert len(fg["cells"]) == 289
    # 1 17r → 18 个 1；首个 "2" 在下标 18
    assert fg["cells"][0]["u"] == "1"
    assert fg["cells"][18]["u"] == "2"


def test_parse_lattice_translated_fill():
    """翻译单填充 `fill=5 (-11.5 23 0)`（仿 inp24）→ kind="translated"，fill 保留单值。"""
    line = "13 0 +28 -19 +17 -31 +13 -18 fill=5 (-11.5 23 0)"
    rows = parse_cells([line])
    c = rows[0].cell
    assert c.fill == "5"
    fg = json.loads(c.fill_grid)
    assert fg["kind"] == "translated"
    assert fg["cells"][0]["u"] == "5"
    assert fg["cells"][0]["dx"] == "-11.5"
    assert fg["cells"][0]["dy"] == "23"


def test_parse_lattice_entries_inline():
    """条目与 FILL= 同行（非续行）→ surface_expr 不被条目污染。"""
    line = "20 0 1 2 3 4 lat=1 u=10 fill=0:1 0:1 0:0 1 2 3 4"
    rows = parse_cells([line])
    c = rows[0].cell
    assert c.surface_expr == "1 2 3 4"
    assert c.fill == "0:1 0:1 0:0"
    fg = json.loads(c.fill_grid)
    assert [e["u"] for e in fg["cells"]] == ["1", "2", "3", "4"]


def test_parse_lattice_space_syntax_fill():
    """空格写法 `FILL 0:1 0:1 0:0`（无 =）→ 同样结构化。"""
    line = "20 0 1 2 3 4 lat=1 u=10 fill 0:1 0:1 0:0 1 2 3 4"
    rows = parse_cells([line])
    c = rows[0].cell
    assert c.fill == "0:1 0:1 0:0"
    fg = json.loads(c.fill_grid)
    assert fg["dims"] == [2, 2, 1]


def test_parse_other_params_captured():
    rows = parse_cells(["1 1 -1.0 -1 geo=2 wwg=1"])
    c = rows[0].cell
    assert "geo=2" in c.other_params
    assert "wwg=1" in c.other_params


def test_parse_comment_from_dollar():
    rows = parse_cells(["1 1 -1.0 -1 $ inner cell"])
    assert rows[0].cell.comment == "inner cell"


def test_parse_comment_from_c_comment_line():
    rows = parse_cells(["c fuel region", "1 1 -1.0 -1"])
    assert rows[0].cell.comment == "fuel region"


def test_parse_raw_condition_lines():
    rows = parse_cells(["#ifdef ENDF7", "1 1 -1.0 -1", "#endif"])
    assert rows[0].kind == "raw"
    assert rows[0].text == "#ifdef ENDF7"
    assert rows[-1].kind == "raw"


def test_parse_surface_expr_with_complement():
    rows = parse_cells(["1 1 -1.0 -1 #2"])
    assert rows[0].cell.surface_expr == "-1 #2"


# ── _expand_j_skip ──────────────────────────────────────
def test_expand_j_skip():
    assert _expand_j_skip(["2j", "0", "0"], 6) == ["", "", "0", "0", "", ""]


def test_expand_j_skip_repeat_r():
    assert _expand_j_skip(["1", "3R"], 5) == ["1", "1", "1", "1", ""]


def test_expand_j_skip_multiply_m():
    # str(2.0*3.0) = "6.0"（float 运算结果字符串化，pin 既有行为）
    assert _expand_j_skip(["2", "M", "3"], 4) == ["2", "6.0", "", ""]


def test_expand_j_skip_pads_short():
    assert _expand_j_skip(["0", "0"], 5) == ["0", "0", "", "", ""]
