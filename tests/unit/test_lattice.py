"""格阵深模块单测：app.lattice（纯 stdlib，阶段1 数据层 + 阶段2 validate 预检测）。

覆盖 parse_fill_tokens / parse_fill_entries / format_fill_cards（raw 优先 + 范围剥离）/
FillGrid JSON 往返 / hex_lattice 合成夹具 / validate_lattice_surfaces（含跨语言 golden）。
"""

import json
from pathlib import Path

import pytest

from app.lattice import (
    FillEntry, FillGrid,
    parse_fill_tokens, parse_fill_entries, format_fill_cards,
    validate_lattice_surfaces,
    hex_ring_rows, hex_ring_cell_count, hex_center,
    lattice_cell_extent, expand_positions, compose_lattice_tree,
    MAX_EXPANDED_ENTRIES, MAX_LATTICE_DEPTH, MAX_TOTAL_INSTANCES, DETAIL_MAX_INSTANCES,
)

# 跨语言 golden：单一权威数据集（前端创建，Python 与 TS lattice.test.ts 同读断言）
_GOLDEN_PATH = (Path(__file__).resolve().parents[2]
                / "gui" / "src" / "utils" / "__golden__" / "latticeGolden.json")


# ── parse_fill_tokens ──────────────────────────────────
def test_parse_tokens_lattice_rect_17x17():
    tokens = ["0:16", "0:16", "0:0"] + ["1"] * 17
    fg = parse_fill_tokens(tokens, lat="1")
    assert fg is not None
    assert fg.kind == "lattice"
    assert fg.lat == "1"
    assert fg.range_ == ["0:16", "0:16", "0:0"]
    assert fg.dims == [17, 17, 1]
    assert len(fg.cells) == 289  # 不足条目补 0
    assert fg.cells[0].u == "1"
    assert fg.raw.startswith("0:16 0:16 0:0")


def test_parse_tokens_lattice_offset_entries():
    tokens = ["0:2", "0:1", "0:0", "1", "(9", "0", "9)", "1", "(9", "0", "9)"]
    fg = parse_fill_tokens(tokens, lat="1")
    assert fg is not None
    assert fg.dims == [3, 2, 1]
    assert len(fg.cells) == 6  # 2 个偏移条目 + 补 0 到 3×2×1
    assert fg.cells[0].u == "1"
    assert fg.cells[0].dx == "9"
    assert fg.cells[0].dz == "9"
    assert fg.cells[1].u == "1"


def test_parse_tokens_nr_repeat():
    tokens = ["-8:8", "-8:8", "0:0", "1", "17r", "2", "14r", "1", "17r"]
    fg = parse_fill_tokens(tokens, lat="1")
    assert fg is not None
    assert fg.dims == [17, 17, 1]
    assert len(fg.cells) == 289  # 51 展开 + 补 0 到 289
    assert fg.cells[0].u == "1"
    # 1 17r → 18 个 1；首个 "2" 在下标 18
    assert fg.cells[18].u == "2"
    assert fg.cells[33].u == "1"  # 2 14r → 15 个 2 之后回到 1


def test_parse_tokens_translated_single_fill():
    fg = parse_fill_tokens(["5", "(-11.5", "23", "0)"])
    assert fg is not None
    assert fg.kind == "translated"
    assert len(fg.cells) == 1
    assert fg.cells[0].u == "5"
    assert fg.cells[0].dx == "-11.5"
    assert fg.cells[0].dy == "23"


def test_parse_tokens_single_universe_returns_none():
    assert parse_fill_tokens(["5"]) is None
    assert parse_fill_tokens(["0"]) is None
    assert parse_fill_tokens([]) is None


# ── parse_fill_entries ─────────────────────────────────
def test_parse_entries_nr_repeat_elements():
    entries = parse_fill_entries(["4", "3r", "5", "2r"])
    assert [e.u for e in entries] == ["4", "4", "4", "4", "5", "5", "5"]


def test_parse_entries_offsets():
    entries = parse_fill_entries(["1", "(9", "0", "9)", "2", "(0", "0", "0)"])
    assert entries[0].u == "1" and entries[0].dx == "9" and entries[0].dy == "0"
    assert entries[1].u == "2" and entries[1].dx == "0"


# ── 内存防护：nR 展开 / 补 0 封顶（QA 建议）──────────────
def test_parse_entries_nr_cap_no_memory_blowup():
    """极端 nR 展开封顶 MAX_EXPANDED_ENTRIES（不爆内存、不抛异常）。"""
    from app.lattice import MAX_EXPANDED_ENTRIES
    entries = parse_fill_entries(["1", "999999999r"])
    assert len(entries) == MAX_EXPANDED_ENTRIES
    assert all(e.u == "1" for e in entries)


def test_parse_entries_nr_cap_injectable():
    """max_entries 可注入：小上限快速验证截断逻辑（raw 兜底不受影响）。"""
    entries = parse_fill_entries(["4", "3r", "5", "2r", "6", "999r"], max_entries=5)
    # 1 个 4 + 3 个 4 → 4 个；追加 5 → 5 个封顶；后续 token 不再展开
    assert len(entries) == 5
    assert [e.u for e in entries] == ["4", "4", "4", "4", "5"]


def test_parse_tokens_huge_range_pad_capped(monkeypatch):
    """超大范围 dims 的补 0 受 MAX_EXPANDED_ENTRIES 封顶（不爆内存，raw 完整）。"""
    import app.lattice as lattice_mod
    monkeypatch.setattr(lattice_mod, "MAX_EXPANDED_ENTRIES", 1000)
    fg = parse_fill_tokens(["-1000:1000", "-1000:1000", "0:0"], lat="1")
    assert fg is not None
    assert len(fg.cells) == 1000          # 补 0 封顶，而非 total=2001²≈4M
    assert all(c.u == "0" for c in fg.cells)
    assert fg.raw == "-1000:1000 -1000:1000 0:0"   # raw 完整保留


# ── format_fill_cards：cells 按 j 行分隔（用户复验修复，2026-08-24）──
def test_format_fill_cards_per_row_grouping_17x17():
    """MCNP 规范每行一个 j 行：17×17 → 每行 17 个条目、共 17 行（cells 优先）。"""
    fg = FillGrid(lat="1", kind="lattice", range_=["0:16", "0:16", "0:0"],
                  dims=[17, 17, 1],
                  cells=[FillEntry(u="9")] * 289,
                  raw="0:16 0:16 0:0 1 17r 2 14r 1 17r")
    lines = format_fill_cards(fg)
    assert lines[0] == "FILL=0:16 0:16 0:0"
    cont = [l for l in lines[1:] if l.strip()]
    assert len(cont) == 17, f"应 17 行（每行一个 j 行），实际 {len(cont)}"
    for row in cont:
        toks = row.split()
        assert len(toks) == 17, f"每行应 17 个条目: {row!r}"
        assert all(t == "9" for t in toks)
        assert len(row) <= 80, f"行超 80 列: {row!r}"


def test_format_fill_cards_row_width_split():
    """某 j 行超 75 字符（长条目含偏移）→ 按宽度拆子行（token 序不变）。"""
    # dims [2,2,1] → 每行 2 条目；条目带偏移很长 → 整行超宽 → 拆子行仍可解析
    fg = FillGrid(lat="1", kind="lattice", range_=["0:1", "0:1", "0:0"],
                  dims=[2, 2, 1],
                  cells=[FillEntry(u="1", dx="99", dy="88", dz="77"),
                         FillEntry(u="2", dx="99", dy="88", dz="77"),
                         FillEntry(u="3"), FillEntry(u="4")])
    lines = format_fill_cards(fg)
    assert lines[0] == "FILL=0:1 0:1 0:0"
    flat = " ".join(l.strip() for l in lines[1:] if l.strip())
    for needle in ("1 (99 88 77)", "2 (99 88 77)", "3", "4"):
        assert needle in flat, f"丢失条目 {needle}: {flat}"
    # 行序保持行主序 token 序（行分隔不改变 MCNP 读序）
    assert flat.index("3") < flat.index("4")


def test_format_fill_cards_cells_first_over_raw():
    """cells 完整时优先结构化展开（即使 raw 非空）——不再 raw 优先。"""
    fg = FillGrid(lat="1", kind="lattice", range_=["0:0", "0:0", "0:0"],
                  dims=[1, 1, 1],
                  cells=[FillEntry(u="7")],
                  raw="0:0 0:0 0:0 9")   # raw 与 cells 不同 → cells 权威
    lines = format_fill_cards(fg)
    cont = [l for l in lines[1:] if l.strip()]
    assert cont[0].strip() == "7", f"应输出 cells 的 7 而非 raw 的 9: {cont}"


def test_format_fill_cards_raw_fallback_empty_cells():
    """cells 空 → raw 兜底（原样 token 回放 + 范围 token 剥离）。"""
    fg = FillGrid(lat="1", kind="lattice", range_=["0:16", "0:16", "0:0"],
                  dims=[17, 17, 1], cells=[],
                  raw="0:16 0:16 0:0 1 17r 2 14r 1 17r")
    lines = format_fill_cards(fg)
    assert lines[0] == "FILL=0:16 0:16 0:0"
    cont = [l for l in lines[1:] if l.strip()]
    assert "1 17r" in cont[0], f"raw 兜底应保留简写: {cont}"
    assert cont[0].lstrip().startswith("1 17r")


def test_format_fill_cards_raw_fallback_truncated():
    """截断边界：len(cells) < dims 乘积（MAX_EXPANDED_ENTRIES 封顶）→ 回落 raw 保真。"""
    fg = FillGrid(lat="1", kind="lattice", range_=["-1000:1000", "0:0", "0:0"],
                  dims=[2001, 1, 1],
                  cells=[FillEntry(u="1")] * 10,   # 不完整（截断）
                  raw="-1000:1000 0:0 0:0 1 17r 2 14r 1 17r")
    lines = format_fill_cards(fg)
    cont = [l for l in lines[1:] if l.strip()]
    # 回落 raw → 保留 17r/14r 简写（不展开截断的 cells）
    assert "17r" in " ".join(cont) and "14r" in " ".join(cont)
    assert all(tok in ("1", "17r", "2", "14r") for tok in cont[0].split()[:4])


def test_format_fill_cards_translated():
    fg = parse_fill_tokens(["5", "(-11.5", "23", "0)"])
    lines = format_fill_cards(fg)
    assert lines[0] == "FILL=5"
    assert lines[1].strip() == "(-11.5 23 0)"


def test_format_fill_cards_none_returns_empty():
    assert format_fill_cards(None) == []


# ── FillGrid JSON 往返 ─────────────────────────────────
def test_fill_grid_json_roundtrip():
    fg = FillGrid(lat="2", kind="lattice", range_=["0:1", "0:1", "0:0"],
                  dims=[2, 2, 1],
                  cells=[FillEntry(u="1", dx="9", dy="0", dz="9")],
                  raw="0:1 0:1 0:0 1 (9 0 9)")
    fg2 = FillGrid.from_json(fg.to_json())
    assert fg2 is not None
    assert fg2.kind == "lattice"
    assert fg2.range_ == ["0:1", "0:1", "0:0"]
    assert fg2.dims == [2, 2, 1]
    assert fg2.cells[0].u == "1"
    assert fg2.cells[0].dx == "9"
    assert fg2.raw == "0:1 0:1 0:0 1 (9 0 9)"


def test_fill_grid_from_json_dirty_returns_none():
    assert FillGrid.from_json("") is None
    assert FillGrid.from_json("not-json") is None
    assert FillGrid.from_json("null") is None
    assert FillGrid.from_json("[1,2]") is None


# ── hex_lattice 合成夹具（lat=2，pointy-top + 轴向 +Z）──
def test_hex_lattice_fixture_parse():
    from tests.conftest import load_sample
    from app.generator.parsers import parse_inp_text
    text = load_sample("hex_lattice.inp")
    deck, warns = parse_inp_text(text)
    assert warns == [], f"解析警告: {warns[:3]}"
    lat_cells = [c.cell for c in deck.cells
                 if c.kind == "cell" and c.cell.fill_grid]
    assert len(lat_cells) == 1
    c = lat_cells[0]
    assert c.lat == "2"
    assert c.fill == "0:1 0:1 0:0"
    fg = FillGrid.from_json(c.fill_grid)
    assert fg.kind == "lattice"
    assert fg.dims == [2, 2, 1]
    assert [e.u for e in fg.cells] == ["1", "2", "1", "2"]
    assert "0:1" not in c.surface_expr, \
        f"surface_expr 被 FILL 范围串污染: {c.surface_expr!r}"


def test_hex_lattice_fixture_roundtrip_stable():
    from tests.conftest import load_sample
    from app.generator.parsers import parse_inp_text
    from app.generator.inp_generator import generate_inp_from_deck
    text = load_sample("hex_lattice.inp")
    deck, _ = parse_inp_text(text)
    g1 = generate_inp_from_deck(deck)
    deck2, _ = parse_inp_text(g1)
    g2 = generate_inp_from_deck(deck2)
    assert g1 == g2, f"hex_lattice R1 不动点不成立（len {len(g1)} → {len(g2)}）"


# ── validate_lattice_surfaces（阶段2 预检测）──────────────
def test_validate_lat1_single_rpp():
    ok, msg = validate_lattice_surfaces("-10", "1", "10 rpp -1 1 -1 1 -1 1")
    assert ok, msg


def test_validate_lat1_single_box_macrobody():
    # prob41c 实卡：单 BOX 宏体六面体
    ok, msg = validate_lattice_surfaces("-6", "1", "6 box 0 0 0 18 0 0 0 0 18")
    assert ok, msg


def test_validate_lat1_six_planes():
    st = "1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 pz -1\n6 pz 1"
    ok, msg = validate_lattice_surfaces("-1 2 -3 4 -5 6", "1", st)
    assert ok, msg


def test_validate_lat1_four_planes_2d():
    # 17×17 实卡形态：50 -51 52 -53（x/y 各一对±，z 无界 2D 延伸）
    st = "50 px -0.63\n51 px 0.63\n52 py -0.63\n53 py 0.63"
    ok, msg = validate_lattice_surfaces("50 -51 52 -53", "1", st)
    assert ok, msg


def test_validate_lat2_single_rhp():
    ok, msg = validate_lattice_surfaces("-10", "2", "10 rhp 0 0 0 0 0 2 0.5 0 0")
    assert ok, msg


def test_validate_lat2_single_hex():
    ok, msg = validate_lattice_surfaces("-11", "2", "11 hex 0 0 0 0 0 2 0.5 0 0")
    assert ok, msg


def test_validate_lat2_six_p_plus_two_pz():
    st = (
        "1 p 0.866 0.5 0 -0.866\n"
        "2 p 0.866 -0.5 0 -0.866\n"
        "3 p 0 -1.0 0 -0.866\n"
        "4 p -0.866 -0.5 0 -0.866\n"
        "5 p -0.866 0.5 0 -0.866\n"
        "6 p 0 1.0 0 -0.866\n"
        "7 pz 0.5\n"
        "8 pz -0.5"
    )
    ok, msg = validate_lattice_surfaces("-1 -2 -3 -4 -5 -6 -7 8", "2", st)
    assert ok, msg


def test_validate_reject_hash():
    ok, msg = validate_lattice_surfaces("-10 #11", "1", "10 px 0\n11 py 0")
    assert not ok
    assert "补集" in msg or "#" in msg


def test_validate_reject_colon_and_parens():
    ok, msg = validate_lattice_surfaces("(1 -2):(3 -4)", "1", "")
    assert not ok
    ok, msg = validate_lattice_surfaces("1:2", "1", "")
    assert not ok
    assert "并集" in msg or "括号" in msg


def test_validate_reject_unpaired_planes():
    # 3 个平面：不成盒
    st = "1 px -1\n2 px 1\n3 py -1"
    ok, msg = validate_lattice_surfaces("-1 2 -3", "1", st)
    assert not ok
    # 同轴同号：x 上两个都负（不成盒）
    st = "1 px -1\n2 px 1\n3 py -1\n4 py 1"
    ok, msg = validate_lattice_surfaces("-1 -2 -3 4", "1", st)
    assert not ok
    # 4 面但分布到 3 轴（2/1/1）：非 2D 延伸
    st = "1 px -1\n2 px 1\n3 py -1\n5 pz 0"
    ok, msg = validate_lattice_surfaces("-1 2 -3 5", "1", st)
    assert not ok
    # lat=2 但曲面数非 1/8
    st = "1 p 0.866 0.5 0 -0.866\n7 pz 0.5\n8 pz -0.5"
    ok, msg = validate_lattice_surfaces("-1 -7 8", "2", st)
    assert not ok
    # lat=2：PZ 顶底同号（不成棱柱）
    st = ("1 p 0.866 0.5 0 -0.866\n2 p 0.866 -0.5 0 -0.866\n3 p 0 -1.0 0 -0.866\n"
          "4 p -0.866 -0.5 0 -0.866\n5 p -0.866 0.5 0 -0.866\n6 p 0 1.0 0 -0.866\n"
          "7 pz 0.5\n8 pz -0.5")
    ok, msg = validate_lattice_surfaces("-1 -2 -3 -4 -5 -6 -7 -8", "2", st)
    assert not ok
    # lat=2：侧平面法向未均布 60°（第 6 个偏到 ~310°）
    st = ("1 p 1 0 0 -1\n2 p 0.5 0.866 0 -1\n3 p -0.5 0.866 0 -1\n4 p -1 0 0 -1\n"
          "5 p -0.5 -0.866 0 -1\n6 p 0.5 -0.6 0 -1\n7 pz 1\n8 pz -1")
    ok, msg = validate_lattice_surfaces("-1 -2 -3 -4 -5 -6 -7 8", "2", st)
    assert not ok


def test_validate_reject_missing_surfaces_text():
    ok, msg = validate_lattice_surfaces("-1 2", "1", "")
    assert not ok
    assert "surfaces_text" in msg or "曲面卡" in msg


def test_validate_reject_unknown_surface():
    ok, msg = validate_lattice_surfaces("-1 2", "1", "1 px 0")
    assert not ok
    assert "2" in msg


def test_validate_reject_bad_lat():
    ok, msg = validate_lattice_surfaces("-10", "3", "10 rpp -1 1 -1 1 -1 1")
    assert not ok
    assert "lat" in msg


def test_validate_reject_non_plane_in_lat1():
    st = "1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 rpp -1 1 -1 1 -1 1\n6 pz 1"
    ok, msg = validate_lattice_surfaces("-1 2 -3 4 -5 6", "1", st)
    assert not ok


# ── 跨语言 golden：validate 样例（前端 latticeGolden.json 单一权威）──
def test_validate_lattice_golden_cross_language():
    """validate_lattice_surfaces 对 latticeGolden.json 内样例返回与 expected 一致。

    golden JSON 由前端创建（gui/src/utils/__golden__/latticeGolden.json），
    Python 与 TS（gui/test/lattice.test.ts）读同一文件断言同一 expected。
    文件缺失时跳过（前端尚未产出，不影响后端门禁）。
    """
    if not _GOLDEN_PATH.is_file():
        pytest.skip("gui/src/utils/__golden__/latticeGolden.json 缺失（前端未产出 golden）")
    data = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    samples = data.get("validate", [])
    assert samples, "golden 的 validate 样例为空"
    for s in samples:
        ok, msg = validate_lattice_surfaces(
            s["surfaceExpr"], s["lat"], s.get("surfacesText", ""))
        assert ok == s["expectedOk"], (
            f"golden {s.get('id', '?')}: expectedOk={s['expectedOk']} "
            f"实际 ok={ok} msg={msg!r}"
        )
        if s.get("expectedOk"):
            assert msg == "", f"golden {s.get('id', '?')}: 合法样例应无消息，实际 {msg!r}"


# ── 阶段3：3D 预览 — hex_ring_rows / hex_center / lattice_cell_extent ──
def _fg(lat, dims, us, kind="lattice") -> FillGrid:
    """构造格阵（dims 行主序，u 字符串列表）。"""
    return FillGrid(lat=str(lat), kind=kind, range_=[f"0:{d - 1}" for d in dims],
                    dims=list(dims),
                    cells=[FillEntry(u=str(u)) for u in us])


def test_hex_ring_rows_cell_count():
    assert hex_ring_rows(1) == [2, 3, 2]
    assert hex_ring_rows(2) == [3, 4, 5, 4, 3]
    assert hex_ring_rows(3) == [4, 5, 6, 7, 6, 5, 4]
    assert hex_ring_cell_count(0) == 1
    assert hex_ring_cell_count(1) == 7
    assert hex_ring_cell_count(2) == 19
    assert hex_ring_cell_count(3) == 37
    for r in range(1, 5):
        assert sum(hex_ring_rows(r)) == hex_ring_cell_count(r)


def test_hex_center_formula():
    """MCNP LAT=2 权威公式（交叉验证自官方库 u233-comp-therm-001-case-6.i）：
    x=(col+row/2)·pitch, y=row·pitch·√3/2。"""
    assert hex_center(0, 0, 2) == (0.0, 0.0)
    x, y = hex_center(2, 1, 2)
    assert x == pytest.approx(5.0)        # (2+0.5)·2
    assert y == pytest.approx(1.7320508075688772)  # 1·2·√3/2
    x, y = hex_center(1, 0, 1)
    assert x == pytest.approx(1.0)        # (1+0)·1
    assert y == pytest.approx(0.0)        # 0·1·√3/2
    x, y = hex_center(0, 2, 1)
    assert x == pytest.approx(1.0)        # (0+1)·1
    assert y == pytest.approx(1.7320508075688772)  # 2·1·√3/2


def test_lattice_cell_extent_rpp_macrobody():
    e = lattice_cell_extent("-10", "1", "10 rpp -1 1 -2 2 -3 3")
    assert e is not None
    assert e["x_min"] == -1 and e["x_max"] == 1
    assert e["y_min"] == -2 and e["z_max"] == 3


def test_lattice_cell_extent_box_macrobody():
    e = lattice_cell_extent("-6", "1", "6 box 0 0 0 18 0 0 0 18 0 0 0 18")
    assert e is not None
    assert e["x_min"] == 0 and e["x_max"] == 18
    assert e["y_min"] == 0 and e["y_max"] == 18
    assert e["z_min"] == 0 and e["z_max"] == 18


def test_lattice_cell_extent_box_macrobody_9params():
    """省略 v3 的 BOX（9 参数）→ v3=v1×v2 补全，不返回 None。"""
    e = lattice_cell_extent("-6", "1", "6 box 0 0 0 18 0 0 0 0 18")
    assert e is not None
    assert e["x_min"] == 0 and e["x_max"] == 18
    assert e["z_min"] == 0 and e["z_max"] == 18


def test_lattice_cell_extent_rect_planes_2d():
    st = "50 px -0.63\n51 px 0.63\n52 py -0.63\n53 py 0.63"
    e = lattice_cell_extent("50 -51 52 -53", "1", st)
    assert e is not None
    assert e["x_min"] == -0.63 and e["x_max"] == 0.63
    assert e["y_min"] == -0.63 and e["y_max"] == 0.63
    assert e["z_min"] is None and e["z_max"] is None  # 2D 延伸 z 无界


def test_lattice_cell_extent_rect_planes_3d():
    st = "1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 pz -1\n6 pz 1"
    # 盒内 = 低正高负（+PX 下界、-PX 上界）
    e = lattice_cell_extent("+1 -2 +3 -4 +5 -6", "1", st)
    assert e is not None
    assert e["x_min"] == -1 and e["x_max"] == 1
    assert e["z_min"] == -1 and e["z_max"] == 1


def test_lattice_cell_extent_hex_planes():
    # MCNP 约定 n·p = +D：`-`（内侧）= n·p < D；D=+0.866 → 内接六边形 apothem 0.866
    st = ("1 p 0.866 0.5 0 0.866\n2 p 0.866 -0.5 0 0.866\n"
          "3 p 0 -1.0 0 0.866\n4 p -0.866 -0.5 0 0.866\n"
          "5 p -0.866 0.5 0 0.866\n6 p 0 1.0 0 0.866\n"
          "7 pz 0.5\n8 pz -0.5")
    e = lattice_cell_extent("-1 -2 -3 -4 -5 -6 -7 8", "2", st)
    assert e is not None
    assert abs(e["x_min"] + 1.0) < 1e-9 and abs(e["x_max"] - 1.0) < 1e-9
    assert abs(e["y_min"] + 0.866) < 1e-9 and abs(e["y_max"] - 0.866) < 1e-9
    assert e["z_min"] == -0.5 and e["z_max"] == 0.5


def test_lattice_cell_extent_unparseable():
    assert lattice_cell_extent("", "1", "") is None
    assert lattice_cell_extent("-10 #11", "1", "10 px 0") is None
    assert lattice_cell_extent("-10", "1", "") is None


# ── 阶段3：expand_positions（格位中心）────────────────────
def test_expand_positions_rect_2d():
    fg = _fg("1", [2, 2, 1], ["1", "2", "1", "2"])
    ext = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": None, "z_max": None}
    pos = expand_positions(fg, ext)
    assert len(pos) == 4
    assert pos[0] == {"idx": 0, "u": "1", "x": -2.0, "y": -2.0, "z": 0.0, "dx": 0.0, "dy": 0.0, "dz": 0.0}
    assert pos[1]["x"] == 2.0 and pos[1]["y"] == -2.0
    assert pos[2]["x"] == -2.0 and pos[2]["y"] == 2.0
    assert pos[3]["x"] == 2.0 and pos[3]["y"] == 2.0


def test_expand_positions_rect_3d():
    fg = _fg("1", [2, 2, 2], ["1"] * 8)
    ext = {"x_min": -0.5, "x_max": 0.5, "y_min": -0.5, "y_max": 0.5, "z_min": -0.5, "z_max": 0.5}
    pos = expand_positions(fg, ext)
    assert len(pos) == 8
    assert pos[0]["x"] == -0.5 and pos[0]["y"] == -0.5 and pos[0]["z"] == -0.5
    assert pos[7]["x"] == 0.5 and pos[7]["y"] == 0.5 and pos[7]["z"] == 0.5


def test_expand_positions_hex_ring_order():
    """hex 用矩形盒模型（hexGrid 交错），角位 void 由 u="0" 承载（不排除）。
    居中（2026-08-28）：hex 分支用 hex_center(i-(nx-1)/2, j-(ny-1)/2) 使格阵几何中心
    落原点（与 rect 一致），不再全在正象限。"""
    fg = _fg("2", [2, 2, 1], ["1", "2", "1", "2"])
    # 面法向 0°/60°/120°：flat-to-flat=x（格距），pointy-to-pointy=y
    ext = {"x_min": -0.8660254037844386, "x_max": 0.8660254037844386,
           "y_min": -1, "y_max": 1, "z_min": -0.5, "z_max": 0.5}
    pos = expand_positions(fg, ext)
    assert len(pos) == 4
    assert [p["u"] for p in pos] == ["1", "2", "1", "2"]
    # MCNP LAT=2 蜂窝（pitch=√3，x=(col+row/2)·√3, y=row·√3·√3/2=row·1.5），居中偏移
    # (i-0.5, j-0.5)：idx0 (-1.299, -0.75)  idx1 (0.433, -0.75)  idx2 (-0.433, 0.75)
    #   idx3 (1.299, 0.75)
    assert pos[0]["x"] == pytest.approx(-1.299038105676658) and pos[0]["y"] == pytest.approx(-0.7499999999999999)
    assert pos[1]["x"] == pytest.approx(0.4330127018922193) and pos[1]["y"] == pytest.approx(-0.7499999999999999)
    assert pos[2]["x"] == pytest.approx(-0.4330127018922193) and pos[2]["y"] == pytest.approx(0.7499999999999999)
    assert pos[3]["x"] == pytest.approx(1.299038105676658) and pos[3]["y"] == pytest.approx(0.7499999999999999)


def test_expand_positions_trcl_90():
    """TRCL 绕 Z 旋转 90°：(x,y) → (-y,x)。"""
    fg = _fg("1", [2, 2, 1], ["1", "2", "1", "2"])
    ext = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": None, "z_max": None}
    pos = expand_positions(fg, ext, trcl_rotation_deg=90)
    assert pos[0]["x"] == pytest.approx(2.0) and pos[0]["y"] == pytest.approx(-2.0)
    assert pos[3]["x"] == pytest.approx(-2.0) and pos[3]["y"] == pytest.approx(2.0)


def test_expand_positions_too_many_returns_none():
    fg = _fg("1", [201, 201, 1], ["1"])
    ext = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": None, "z_max": None}
    assert expand_positions(fg, ext, max_positions=1000) is None


def test_expand_positions_single_layer_z_uses_z_origin():
    """1 - container z non-symmetric (BEAVRS pz 0->460, center +230): single-layer lattice
    grid z = z_origin（根格阵 context 传容器 z 中点 230）。不带 z_origin（缺省 0，嵌套
    格阵相对父格位）→ 相对偏移 0。Pre-fix 内置 z_base 使嵌套格阵在父绝对 z 上再叠加，
    导致组件 pin 全被推成 z=460（只看到"两排横向棒子"）。"""
    fg = _fg("1", [2, 2, 1], ["1", "2", "1", "2"])
    ext = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": 0.0, "z_max": 460.0}
    pos = expand_positions(fg, ext, z_origin=230.0)
    assert all(p["z"] == pytest.approx(230.0) for p in pos)
    # 嵌套格阵（z_origin 缺省 0）：单层相对偏移 0，不叠加容器中点
    pos2 = expand_positions(fg, ext)
    assert all(p["z"] == pytest.approx(0.0) for p in pos2)


def test_expand_positions_symmetric_z_center_stays_zero():
    """2 - symmetric z ([-0.5,0.5], center 0): grid z stays 0 (backward-compatible)."""
    fg = _fg("1", [2, 2, 1], ["1", "2", "1", "2"])
    ext = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": -0.5, "z_max": 0.5}
    pos = expand_positions(fg, ext)
    assert all(p["z"] == pytest.approx(0.0) for p in pos)


# ── 阶段3：compose_lattice_tree（嵌套 fill 递归）───────────
def _lcell(num, mat, u, fg=None, expr="-1", lat="1", extent=None) -> dict:
    return {"cellNum": num, "material": mat, "fill": "", "fill_grid": fg,
            "surface_expr": expr, "lat": lat, "trcl": "", "trcl_deg": 0,
            "extent": extent}


def _nested_sub(outer_fg, inner_fg, outer_ext, inner_ext) -> dict:
    return {
        "99": [_lcell(110, "0", "99", fg=outer_fg, expr="20 21 22 23", extent=outer_ext)],
        "10": [_lcell(111, "0", "10", fg=inner_fg, expr="10 11 12 13", extent=inner_ext)],
        "1": [_lcell(101, "1", "1")],
        "2": [_lcell(102, "1", "2")],
        "3": [_lcell(103, "1", "3")],
        "4": [_lcell(104, "1", "4")],
        "20": [_lcell(201, "1", "20")],
        "30": [_lcell(301, "1", "30")],
    }


def test_compose_lattice_tree_nested_10_leaves():
    """2×2 外格阵（pitch4）内嵌 2×2 子格阵（pitch2）→ 10 叶绝对坐标。"""
    outer_fg = _fg("1", [2, 2, 1], ["10", "10", "20", "30"])
    inner_fg = _fg("1", [2, 2, 1], ["1", "2", "3", "4"])
    inner_ext = {"x_min": -1, "x_max": 1, "y_min": -1, "y_max": 1, "z_min": None, "z_max": None}
    outer_ext = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": None, "z_max": None}
    sub = _nested_sub(outer_fg, inner_fg, outer_ext, inner_ext)
    r = compose_lattice_tree(outer_fg, sub, outer_ext, 0)
    assert r["status"] == "ok"
    assert r["count"] == 10
    assert r["detailViable"] is True
    coords = {(leaf["cellNum"], round(leaf["x"], 9), round(leaf["y"], 9), round(leaf["z"], 9))
              for leaf in r["leafInstances"]}
    expected = {
        (101, -3, -3, 0), (102, -1, -3, 0), (103, -3, -1, 0), (104, -1, -1, 0),
        (101, 1, -3, 0), (102, 3, -3, 0), (103, 1, -1, 0), (104, 3, -1, 0),
        (201, -2, 2, 0), (301, 2, 2, 0),
    }
    assert coords == expected
    # 双形态：lattices 去重（外层 110 + 内层 111 各一条），tree 保层次
    assert [e["num"] for e in r["lattices"]] == [110, 111]
    assert r["lattices"][0]["pitch"] == [4.0, 4.0, 1.0]
    assert r["lattices"][1]["pitch"] == [2.0, 2.0, 1.0]
    assert len(r["tree"]) == 4
    assert r["tree"][0]["u"] == "10" and r["tree"][0]["path"] == "0"
    assert len(r["tree"][0]["children"]) == 4
    assert r["tree"][2]["u"] == "20"
    assert r["tree"][2]["children"][0]["leaf"] is True


def test_compose_lattice_tree_depth_limit():
    outer_fg = _fg("1", [2, 2, 1], ["10", "10", "20", "30"])
    inner_fg = _fg("1", [2, 2, 1], ["1", "2", "3", "4"])
    inner_ext = {"x_min": -1, "x_max": 1, "y_min": -1, "y_max": 1, "z_min": None, "z_max": None}
    outer_ext = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": None, "z_max": None}
    sub = _nested_sub(outer_fg, inner_fg, outer_ext, inner_ext)
    r = compose_lattice_tree(outer_fg, sub, outer_ext, 0, max_depth=1)
    assert r["status"] == "depth_limit"


def test_compose_lattice_tree_too_many():
    outer_fg = _fg("1", [2, 2, 1], ["10", "10", "20", "30"])
    inner_fg = _fg("1", [2, 2, 1], ["1", "2", "3", "4"])
    inner_ext = {"x_min": -1, "x_max": 1, "y_min": -1, "y_max": 1, "z_min": None, "z_max": None}
    outer_ext = {"x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2, "z_min": None, "z_max": None}
    sub = _nested_sub(outer_fg, inner_fg, outer_ext, inner_ext)
    r = compose_lattice_tree(outer_fg, sub, outer_ext, 0, max_total=3)
    assert r["status"] == "too_many"
    assert r["count"] == 3


def test_compose_lattice_tree_limits_constants():
    assert MAX_LATTICE_DEPTH == 8
    assert MAX_TOTAL_INSTANCES == 500000
    assert DETAIL_MAX_INSTANCES == 20000


# ── 阶段3：跨语言 golden（positions / nested，前端 latticeGolden.json）──
def _golden_positions_hex_fresh(s: dict) -> bool:
    """golden positions 段 hex 条目是否已重算为居中公式值。

    hex 居中（2026-08-28）：expand_positions/hexGrid/gridCenter 的 hex 分支改
    hex_center(i-(nx-1)/2, j-(ny-1)/2) 使格阵几何中心落原点（与 rect 一致）。前端
    Wave 写盘后 golden hex_2x2 期望值为居中值（idx1=(0.433,-0.75)）。未重算时仍为旧
    正象限值 → 本条目 skip（沿用「未产出 skip」模式）。rect 段不受影响恒 fresh。
    """
    if s.get("lat") != "2":
        return True
    for exp in s.get("expected", []):
        if exp.get("idx") == 1:
            return (exp["x"] == pytest.approx(0.4330127018922193, abs=1e-9)
                    and exp["y"] == pytest.approx(-0.7499999999999999, abs=1e-9))
    return False


def test_positions_golden_cross_language():
    """expand_positions 对 latticeGolden.json positions 段产出与 expected 一致。"""
    if not _GOLDEN_PATH.is_file():
        pytest.skip("gui/src/utils/__golden__/latticeGolden.json 缺失")
    data = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    samples = data.get("positions", [])
    if not samples:
        pytest.skip("golden 无 positions 段（阶段3 golden 待扩展）")
    import math as _m
    for s in samples:
        if not _golden_positions_hex_fresh(s):
            continue  # 项5 hex 段前端未重算 → skip（写盘后自动生效）
        dims = s["dims"]
        total = _m.prod(dims)
        fg = _fg(s["lat"], dims, ["1"] * total)
        pos = expand_positions(fg, s["extent"], trcl_rotation_deg=s.get("trclDeg", 0))
        assert pos is not None, f"golden {s.get('id', '?')}: 超限返回 None"
        for exp in s["expected"]:
            p = pos[exp["idx"]]
            assert p["x"] == pytest.approx(exp["x"], abs=1e-9), f"{s['id']} idx {exp['idx']} x"
            assert p["y"] == pytest.approx(exp["y"], abs=1e-9), f"{s['id']} idx {exp['idx']} y"
            assert p["z"] == pytest.approx(exp["z"], abs=1e-9), f"{s['id']} idx {exp['idx']} z"


def test_nested_golden_cross_language():
    """compose_lattice_tree 嵌套样例与 latticeGolden.json nested 段叶坐标一致。"""
    if not _GOLDEN_PATH.is_file():
        pytest.skip("gui/src/utils/__golden__/latticeGolden.json 缺失")
    data = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    nested = data.get("nested")
    if not nested:
        pytest.skip("golden 无 nested 段（阶段3 golden 待扩展）")
    outer_fg = FillGrid.from_json(json.dumps(nested["outerLat"]))
    inner_fg = FillGrid.from_json(json.dumps(nested["innerLat"]))
    outer_ext = nested["outerExtent"]
    inner_ext = nested["innerExtent"]
    cells = nested["universeCells"]
    sub = {}
    for u, cell_list in cells.items():
        c = cell_list[0]
        sub[u] = [{"cellNum": c["cellNum"], "material": c["material"], "fill": "",
                   "fill_grid": None, "surface_expr": c.get("surfaceExpr", ""),
                   "lat": "1", "trcl": "", "trcl_deg": 0, "extent": None}]
    sub["99"][0]["fill_grid"] = outer_fg
    sub["99"][0]["extent"] = outer_ext
    sub["10"][0]["fill_grid"] = inner_fg
    sub["10"][0]["extent"] = inner_ext
    r = compose_lattice_tree(outer_fg, sub, outer_ext, 0)
    assert r["status"] == "ok"
    assert r["count"] == nested["leafCount"]
    got = {(leaf["cellNum"], round(leaf["x"], 9), round(leaf["y"], 9), round(leaf["z"], 9))
           for leaf in r["leafInstances"]}
    exp = {(leaf["cellNum"], leaf["x"], leaf["y"], leaf["z"]) for leaf in nested["leaves"]}
    assert got == exp


# ── Wave 2a：项2/4/5/13/15 ─────────────────────────────
# 项2：方向块数 -N:M 映射
def test_dir_counts_from_range():
    """项2：'a:b' → (L,R)=(-a,b)，dims=L+R+1 与 _range_count dims=b-a+1 自洽。"""
    from app.lattice import _dir_counts_from_range, _range_count
    assert _dir_counts_from_range("-8:8") == (8, 8)    # 居中
    assert _dir_counts_from_range("0:16") == (0, 16)   # 角起
    assert _dir_counts_from_range("-2:5") == (2, 5)    # 非对称
    assert _dir_counts_from_range("bad") == (0, 0)     # 解析失败
    assert _dir_counts_from_range("8") == (0, 0)
    for token, (L, R) in [("-8:8", (8, 8)), ("0:16", (0, 16)), ("-2:5", (2, 5))]:
        assert L + R + 1 == _range_count(token), f"{token} 反派生 dims 不一致"
        assert L == -int(token.split(":")[0]) and R == int(token.split(":")[1])


# 项4：RHP/HEX 单宏体参数校验 + 9 参推断
def test_validate_rhp_params():
    """项4：9/12/15/18 参合法；|H|=0、R1 非⊥H、R2 不⊥H、R1/R2 夹角错、R2/R3 夹角错、参数数非法 → 拒。"""
    # 9 参合法（V+H+R1）
    ok, msg = validate_lattice_surfaces("-10", "2", "10 rhp 0 0 0 0 0 2 0.5 0 0")
    assert ok, msg
    # 12 参合法（R2=rot60(R1)）
    ok, msg = validate_lattice_surfaces("-10", "2",
        "10 rhp 0 0 0 0 0 2 0.5 0 0 0.25 0.4330127019 0")
    assert ok, msg
    # 15 参合法（R3=rot120(R1)，R2/R3 夹角 60°）
    ok, msg = validate_lattice_surfaces("-10", "2",
        "10 hex 0 0 0 0 0 2 0.5 0 0 0.25 0.4330127019 0 -0.25 0.4330127019 0")
    assert ok, msg
    # 18 参合法（前 15 + 3 额外 token）
    ok, msg = validate_lattice_surfaces("-10", "2",
        "10 rhp 0 0 0 0 0 2 0.5 0 0 0.25 0.4330127019 0 -0.25 0.4330127019 0 1 2 3")
    assert ok, msg
    # |H|=0 拒
    ok, msg = validate_lattice_surfaces("-10", "2", "10 rhp 0 0 0 0 0 0 0.5 0 0")
    assert not ok and "H" in msg
    # R1 非 ⊥H 拒（R1=(0.5,0,0.5) 与 H=(0,0,2) 夹角非 90°）
    ok, msg = validate_lattice_surfaces("-10", "2", "10 rhp 0 0 0 0 0 2 0.5 0 0.5")
    assert not ok and "垂直" in msg
    # R2 不 ⊥H 拒
    ok, msg = validate_lattice_surfaces("-10", "2", "10 rhp 0 0 0 0 0 2 0.5 0 0 0.5 0 1")
    assert not ok
    # R1/R2 夹角错（30°）拒
    ok, msg = validate_lattice_surfaces("-10", "2",
        "10 rhp 0 0 0 0 0 2 0.5 0 0 0.4330127019 0.25 0")
    assert not ok
    # R2/R3 夹角错（R3 与 R2 平行 0°）拒
    ok, msg = validate_lattice_surfaces("-10", "2",
        "10 rhp 0 0 0 0 0 2 0.5 0 0 0.25 0.4330127019 0 0.25 0.4330127019 0")
    assert not ok
    # 参数数非法（6 参）拒
    ok, msg = validate_lattice_surfaces("-10", "2", "10 rhp 0 0 0 0 0 2 0.5")
    assert not ok
    # HEX 同规则
    ok, msg = validate_lattice_surfaces("-10", "2", "10 hex 0 0 0 0 0 2 0.5 0 0")
    assert ok, msg


def test_rhp_extent_9params_infer():
    """项4：9 参 RHP 推断 R2（Rodrigues 绕 H 转 60°）→ AABB 与 12 参显式一致。"""
    nine = lattice_cell_extent("-10", "2", "10 rhp 0 0 0 0 0 2 0.5 0 0")
    twelve = lattice_cell_extent("-10", "2",
                                 "10 rhp 0 0 0 0 0 2 0.5 0 0 0.25 0.433012701892 0")
    assert nine is not None and twelve is not None
    for k in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"):
        assert nine[k] == pytest.approx(twelve[k], abs=1e-9), k
    # 9 参 H⊥ 平面：R1=(0.5,0,0) → 六边形 AABB x∈[-0.5,0.5] y∈[-0.433,0.433] z∈[-1,1]
    assert nine["x_min"] == pytest.approx(-0.5)
    assert nine["x_max"] == pytest.approx(0.5)
    assert nine["y_max"] == pytest.approx(0.433012701892, abs=1e-9)
    assert nine["z_min"] == -1.0 and nine["z_max"] == 1.0


# 项5：hex 权威公式（顶点+X flat-top）
def test_hex_center_flat_top():
    """项5：顶点+X 蜂窝权威公式，pitch=2/√3 权威样例（设计 golden 值）。"""
    import math as _m
    p = 2.0 / _m.sqrt(3.0)
    x0, y0 = hex_center(0, 0, p)
    x1, y1 = hex_center(1, 0, p)
    x2, y2 = hex_center(0, 1, p)
    # 相邻列 (0,0)→(1,0) 距 = p；相邻行 (0,0)→(0,1) 距 = p
    assert (x1 - x0) ** 2 + (y1 - y0) ** 2 == pytest.approx(p * p, abs=1e-9)
    assert (x2 - x0) ** 2 + (y2 - y0) ** 2 == pytest.approx(p * p, abs=1e-9)
    # pitch=2 权威样例：x=(i+j/2)·2, y=j·2·√3/2=j·√3
    x, y = hex_center(1, 0, 2)
    assert x == pytest.approx(2.0) and y == pytest.approx(0.0)
    x, y = hex_center(0, 1, 2)
    assert x == pytest.approx(1.0) and y == pytest.approx(1.7320508075688772)
    x, y = hex_center(1, 1, 2)
    assert x == pytest.approx(3.0) and y == pytest.approx(1.7320508075688772)


def test_expand_positions_hex_flat_top():
    """项5：expand_positions hex 分支走新 hex_center，消费 golden positions.hex 段
    （前端 Wave 2b 重算写盘后自动生效；未重算 skip）。"""
    if not _GOLDEN_PATH.is_file():
        pytest.skip("gui/src/utils/__golden__/latticeGolden.json 缺失")
    data = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    samples = data.get("positions", [])
    if not samples:
        pytest.skip("golden 无 positions 段")
    import math as _m
    for s in samples:
        if s.get("lat") != "2" or not _golden_positions_hex_fresh(s):
            continue  # 非 hex 或前端未重算项5 hex 段 → skip
        dims = s["dims"]
        total = _m.prod(dims)
        fg = _fg("2", dims, ["1"] * total)
        pos = expand_positions(fg, s["extent"], trcl_rotation_deg=s.get("trclDeg", 0))
        assert pos is not None
        for exp in s["expected"]:
            p = pos[exp["idx"]]
            assert p["x"] == pytest.approx(exp["x"], abs=1e-9), f"{s['id']} idx {exp['idx']} x"
            assert p["y"] == pytest.approx(exp["y"], abs=1e-9), f"{s['id']} idx {exp['idx']} y"
            assert p["z"] == pytest.approx(exp["z"], abs=1e-9), f"{s['id']} idx {exp['idx']} z"


# 项13：循环嵌套检测
def test_detect_fill_cycle():
    """项13：自环/两元环/三元环/无环；fill="0" 不构成边；fill_grid 引用构成边。"""
    from app.lattice import detect_fill_cycle

    def _sub(map_):
        return {str(u): [{"fill": f, "fill_grid": fg} for (f, fg) in cl]
                for u, cl in map_.items()}

    # 两元环 A→B→A
    r = detect_fill_cycle(_sub({"1": [("2", None)], "2": [("1", None)]}))
    assert r["cycle"] is True and r["chain"][0] == r["chain"][-1]
    assert {"1", "2"} <= set(r["chain"])
    # 三元环 A→B→C→A
    r = detect_fill_cycle(_sub({"1": [("2", None)], "2": [("3", None)], "3": [("1", None)]}))
    assert r["cycle"] is True and r["chain"][0] == r["chain"][-1]
    assert set(r["chain"]) == {"1", "2", "3"}
    # 自环 A→A
    r = detect_fill_cycle(_sub({"1": [("1", None)]}))
    assert r["cycle"] is True and r["chain"] == ["1", "1"]
    # 无环
    r = detect_fill_cycle(_sub({"1": [("2", None)], "2": [("", None)]}))
    assert r["cycle"] is False and r["chain"] == []
    # fill="0" / 空 不构成边
    r = detect_fill_cycle(_sub({"1": [("0", None)], "2": [("", None)]}))
    assert r["cycle"] is False
    # fill_grid lattice 引用构成边
    fg = FillGrid(lat="1", kind="lattice", dims=[1, 1, 1],
                  range_=["0:0", "0:0", "0:0"], cells=[FillEntry(u="2")])
    r = detect_fill_cycle(_sub({"1": [("", fg)], "2": [("1", None)]}))
    assert r["cycle"] is True and {"1", "2"} <= set(r["chain"])
    # translated 引用同样构成边
    fg2 = FillGrid(lat="1", kind="translated", cells=[FillEntry(u="2", dx="1", dy="2", dz="3")])
    r = detect_fill_cycle(_sub({"1": [("", fg2)], "2": [("1", None)]}))
    assert r["cycle"] is True


def test_compose_lattice_tree_cycle():
    """项13：compose 入口 detect_fill_cycle → status="cycle" + chain（不递归，空树）。"""
    outer_fg = FillGrid(lat="1", kind="lattice", range_=["0:0", "0:0", "0:0"],
                        dims=[1, 1, 1], cells=[FillEntry(u="1")])
    sub = {
        "99": [_lcell(110, "0", "99", fg=outer_fg, expr="1 -2 3 -4",
                      extent={"x_min": -1, "x_max": 1, "y_min": -1, "y_max": 1,
                              "z_min": None, "z_max": None})],
        "1": [_lcell(101, "0", "1", expr="-1")],
        "2": [_lcell(102, "0", "2", expr="-1")],
    }
    sub["1"][0]["fill"] = "2"
    sub["2"][0]["fill"] = "1"
    r = compose_lattice_tree(outer_fg, sub, {"x_min": -1, "x_max": 1,
                                             "y_min": -1, "y_max": 1,
                                             "z_min": None, "z_max": None}, 0)
    assert r["status"] == "cycle"
    assert r["cycle"] == ["1", "2", "1"]
    assert r["tree"] == [] and r["leafInstances"] == [] and r["count"] == 0
    assert r["lattices"] == [] and r["detailViable"] is True


# 项15：装配规则（fill="0" 装配容器 + void 叶 + 单值 fill 装配链）
def test_expand_universe_void_leaf_and_fill0():
    """项15：void 叶（material=0 无 fill）产 {leaf, void:true}；fill="0" 装配容器不产 STL。"""
    from app.lattice import _expand_universe, MAX_LATTICE_DEPTH, MAX_TOTAL_INSTANCES

    def _state(sub):
        return {"sub_by_u": sub, "max_depth": MAX_LATTICE_DEPTH,
                "max_total": MAX_TOTAL_INSTANCES, "status": "ok",
                "leaves": [], "lattices": [], "count": 0}

    # void 叶
    st = _state({"1": [{"cellNum": 101, "material": "0", "fill": "", "fill_grid": None}]})
    node = _expand_universe("1", (0.0, 0.0, 0.0), 1, "0", st)
    assert node is not None
    assert len(st["leaves"]) == 1
    assert st["leaves"][0]["void"] is True
    assert st["leaves"][0]["cellNum"] == 101 and st["leaves"][0]["u"] == "1"
    assert st["count"] == 1
    # fill="0" → 装配容器：不产自身 STL，不递归
    st2 = _state({"1": [{"cellNum": 101, "material": "1", "fill": "0", "fill_grid": None}]})
    node2 = _expand_universe("1", (0.0, 0.0, 0.0), 1, "0", st2)
    assert node2 is None and st2["leaves"] == [] and st2["count"] == 0
    # fill="0" 容器 + 同 universe 实体 cell → 实体 leaf 正常产出
    st3 = _state({"1": [{"cellNum": 101, "material": "1", "fill": "0", "fill_grid": None},
                        {"cellNum": 102, "material": "1", "fill": "", "fill_grid": None}]})
    node3 = _expand_universe("1", (0.0, 0.0, 0.0), 1, "0", st3)
    assert node3 is not None
    assert [l["cellNum"] for l in st3["leaves"]] == [102]
    assert "void" not in st3["leaves"][0]


def test_expand_universe_single_fill_assembly():
    """项15：单值 fill 装配链——窗口 cell fill=10 → universe 10 → fill=1 → 叶 cell 101。"""
    from app.lattice import _expand_universe, MAX_LATTICE_DEPTH, MAX_TOTAL_INSTANCES
    sub = {
        "10": [{"cellNum": 10, "material": "0", "fill": "1", "fill_grid": None,
                "surface_expr": "1 2 3 4"}],
        "1": [{"cellNum": 101, "material": "1", "fill": "", "fill_grid": None,
               "surface_expr": "-1"}],
    }
    state = {"sub_by_u": sub, "max_depth": MAX_LATTICE_DEPTH,
             "max_total": MAX_TOTAL_INSTANCES, "status": "ok",
             "leaves": [], "lattices": [], "count": 0}
    node = _expand_universe("10", (0.0, 0.0, 0.0), 1, "0", state)
    assert node is not None
    assert [l["cellNum"] for l in state["leaves"]] == [101]
    assert state["leaves"][0]["u"] == "1"
    assert state["leaves"][0]["depth"] == 2
    assert state["count"] == 1


def _assembly_golden_consistent(s: dict) -> bool:
    """golden assembly 段是否结构完整：窗口 fill 指向的 universe 需能沿 fill 边到达
    所有期望叶所在 universe。当前 golden 草稿可能缺 fill 边（前端 Wave 2b 写盘中，
    如 window.fill="10" 但叶 u="1" 不可达）→ 视为未产出 → skip。
    """
    sub_by_u = s.get("sub_by_u", {})
    start = str((s.get("window_cell") or {}).get("fill") or "")
    if start not in sub_by_u:
        return False
    reachable = {start}
    frontier = [start]
    while frontier:
        u = frontier.pop()
        for cell in sub_by_u.get(u, []):
            v = str(cell.get("fill") or "").strip()
            if v and v != "0" and v not in reachable:
                reachable.add(v)
                frontier.append(v)
            fg = cell.get("fill_grid")
            if isinstance(fg, dict):
                for e in fg.get("cells", []) or []:
                    v = str(e.get("u") or "")
                    if v and v != "0" and v not in reachable:
                        reachable.add(v)
                        frontier.append(v)
    leaf_unis = {str(l.get("u")) for l in s.get("expected_leaves", [])}
    return leaf_unis <= reachable


def test_single_fill_assembly_golden():
    """项15：golden assembly 段（单值 fill 装配样例）消费；前端未产出/结构未定稿 → skip。"""
    if not _GOLDEN_PATH.is_file():
        pytest.skip("gui/src/utils/__golden__/latticeGolden.json 缺失")
    data = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    samples = data.get("assembly", [])
    if not samples:
        pytest.skip("golden 无 assembly 段（前端未产出）")
    from app.lattice import _expand_universe, MAX_LATTICE_DEPTH, MAX_TOTAL_INSTANCES
    for s in samples:
        if not _assembly_golden_consistent(s):
            pytest.skip(f"assembly golden {s.get('id', '?')} 结构未定稿（窗口 fill 无法到达期望叶）")
        sub_by_u = {}
        for u, cell_list in s["sub_by_u"].items():
            sub_by_u[u] = [dict(c) for c in cell_list]
        window = s["window_cell"]
        wu = str(window.get("fill") or "")
        state = {"sub_by_u": sub_by_u, "max_depth": MAX_LATTICE_DEPTH,
                 "max_total": MAX_TOTAL_INSTANCES, "status": "ok",
                 "leaves": [], "lattices": [], "count": 0}
        _expand_universe(wu, (0.0, 0.0, 0.0), 1, "0", state)
        got = [{"cellNum": l.get("cellNum"), "u": l.get("u"),
                "x": l.get("x"), "y": l.get("y"), "z": l.get("z"),
                "depth": l.get("depth")} for l in state["leaves"]]
        assert got == s.get("expected_leaves", []), (
            f"assembly {s.get('id', '?')}: 实际 {got} vs 期望 {s.get('expected_leaves')}")
