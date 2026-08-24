"""OWEN 预置 MCNP 卡（BEAVRS/17×17/单棒）解析基线测试。

夹具来自 OWEN 仓库（MIT），文件头声明「community example，未做基准验证」，
仅用于解析器/生成器回归。断言：解析成功、零警告、栅元/曲面/材料数与
2026-08-22 实测基线一致（解析器升级后若计数变化须人工确认而非改断言）。
"""

import json
from pathlib import Path

from app.generator.parsers import parse_inp_text


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "owen"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


def test_pincell_mcnp_parse_baseline():
    deck, warnings = parse_inp_text(_load("pincell_mcnp.i"))
    assert warnings == [], f"解析警告: {warnings[:3]}"
    assert len(deck.cells) == 5
    assert len(deck.surfaces) == 266
    assert len(deck.materials) == 4


def test_assembly_17x17_mcnp_parse_baseline():
    deck, warnings = parse_inp_text(_load("assembly_17x17_mcnp.i"))
    assert warnings == [], f"解析警告: {warnings[:3]}"
    assert len(deck.cells) == 15  # 12 针/导向管栅元 + lat 格阵 + 外围
    assert len(deck.surfaces) == 275
    assert len(deck.materials) == 5
    # 格阵（lat=1）栅元应保留 lat/u/fill 结构化字段，未被丢弃
    lat_cells = [c for c in deck.cells
                 if c.kind == "cell" and getattr(c.cell, "lat", None) in (1, "1")]
    assert len(lat_cells) >= 1, "17×17 应含 lat= 格阵栅元"
    # 阶段1 增强：fill_grid 非空且 dims==[17,17,1]，surface_expr 干净（无范围串污染）
    lat_cell = lat_cells[0].cell
    assert lat_cell.fill_grid, "格阵栅元应带 fill_grid JSON"
    assert lat_cell.fill == "0:16 0:16 0:0", f"fill 应为范围串，实际 {lat_cell.fill!r}"
    fg = json.loads(lat_cell.fill_grid)
    assert fg["dims"] == [17, 17, 1], f"dims 应为 [17,17,1]，实际 {fg['dims']}"
    assert lat_cell.surface_expr == "50 -51 52 -53", \
        f"surface_expr 被 FILL 范围串污染: {lat_cell.surface_expr!r}"


def test_beavrs_fullcore_mcnp_parse_baseline():
    deck, warnings = parse_inp_text(_load("beavrs_fullcore_mcnp.i"))
    assert warnings == [], f"解析警告: {warnings[:3]}"
    assert len(deck.cells) == 331
    assert len(deck.surfaces) == 2101
    assert len(deck.materials) == 13
