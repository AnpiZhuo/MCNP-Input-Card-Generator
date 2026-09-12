"""
STEP 导入 deck 序列化回归测试 —— flat_cell_json / geometry_deck_response。

背景（2026-12 用户反馈「导入 STEP 炸了」）：
    deck.cells 改造成 CellRow 判别联合（f8f7fe6）后，api_server 的
    /api/import-step 仍在手写 ``c.number / c.material / c.surface_expr``，
    CellRow 上没有这些字段 → 每次 STEP 导入都 500：
        AttributeError: 'CellRow' object has no attribute 'number'

    该映射现在收敛到 app/step_importer.flat_cell_json 一处，本文件锁死
    它接受的入参形态（CellRow / CellData / 平铺 dict）与出参契约
    （docs/contracts/api.yaml 的 deck.cells 平铺 5 字段）。

纪律：本文件【不 import】gui.backend.api_server（conftest.py 铁律）。
"""
import pytest

from app.models import CellData, CellRow
from app.step_importer import flat_cell_json, geometry_deck_response


def _cell(**kw) -> CellData:
    base = dict(number=1, material="1", density="-1.0",
                surface_expr="-1 2", comment="")
    base.update(kw)
    return CellData(**base)


# ── 1. 回归本体：CellRow 必须能序列化（修复前 AttributeError）──
def test_cellrow_serializes_without_number_attribute_error():
    row = CellRow(kind="cell", cell=_cell(number=7, material="2",
                                         density="-2.7",
                                         surface_expr="-3 4",
                                         comment="clad"))
    out = flat_cell_json(row)
    assert out == {"number": 7, "material": "2", "density": "-2.7",
                   "surface_expr": "-3 4", "comment": "clad"}


# ── 2. 契约字段集：恰好 api.yaml 的 5 个平铺键 ──
def test_flat_cell_contract_fields():
    assert set(flat_cell_json(CellRow(kind="cell", cell=_cell()))) == {
        "number", "material", "density", "surface_expr", "comment"}


# ── 3. 真空栅元：density 空串（不是 "None"/"0"）──
def test_void_cell_density_is_empty_string():
    out = flat_cell_json(CellRow(kind="cell", cell=_cell(
        number=2, material="0", density="", surface_expr="3 #1")))
    assert out["density"] == ""
    assert out["material"] == "0"


# ── 4. 原样条件行（#ifdef/#endif）不丢行、顺序不变 ──
def test_raw_rows_pass_through_in_order():
    cells = [
        CellRow(kind="raw", text="#ifdef ENDF7"),
        CellRow(kind="cell", cell=_cell(number=1)),
        CellRow(kind="raw", text="#endif"),
    ]
    out = geometry_deck_response("1 pz 1", "", cells)
    assert out["cells"] == [
        {"kind": "raw", "text": "#ifdef ENDF7"},
        {"number": 1, "material": "1", "density": "-1.0",
         "surface_expr": "-1 2", "comment": ""},
        {"kind": "raw", "text": "#endif"},
    ]


# ── 5. 兼容历史平铺 CellData / 平铺 dict（旧调用方与前端旧格式）──
def test_flat_cell_data_and_dict_still_accepted():
    assert flat_cell_json(_cell(number=3)) ["number"] == 3
    flat_dict = {"number": 4, "material": "1", "density": "-1.0",
                 "surface_expr": "-9", "comment": "x"}
    assert flat_cell_json(flat_dict) == flat_dict
    assert flat_cell_json({"kind": "raw", "text": "#else"}) == {
        "kind": "raw", "text": "#else"}


# ── 6. 空/缺字段不炸 ──
@pytest.mark.parametrize("cells", [[], None, [CellRow(kind="cell", cell=None)]])
def test_empty_and_none_cells_do_not_raise(cells):
    out = geometry_deck_response(None, None, cells)
    assert out["surfaces"] == "" and out["tr_cards"] == ""
    if cells == [] or cells is None:
        assert out["cells"] == []
    else:  # cell=None 的行退化为平铺空栅元，不抛异常
        assert out["cells"][0]["number"] == ""
