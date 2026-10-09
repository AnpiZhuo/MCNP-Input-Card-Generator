# -*- coding: utf-8 -*-
"""重合检测缓存指纹的规范化口径（2026-10-10 修：该缓存原本**永不命中**）。

背景（实测）：`/api/preview-3d` 收到的 cell 是**扁平** dict（前端只发 4~14 个键），
`/api/check-overlap` 收到的是 `{kind,cell}` **信封** ⇒ 两端 `PreviewCache.fingerprint`
算出的指纹永远不同（同一 deck：`6663f94f…` vs `998d9a0c…`）⇒ `put_overlaps` 静默空操作、
`overlaps.json` 永不读（每次「重新检测」都重跑 FreeCAD 布尔）。

本测试把"同口径"钉死，并守住反向风险：**几何/取舍相关的任一字段变了，指纹必须变** ——
少一个都可能让缓存给出陈旧的重叠报告。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "gui", "backend"))

import api_server as A  # noqa: E402

FLAT = {
    "number": 9, "material": "0", "density": "", "surface_expr": "124",
    "u": "", "fill": "", "lat": "", "trcl": "", "render": True, "fill_grid": "",
    "imp_n": "0", "imp_p": "0", "imp_e": "", "comment": "Graveyard",
}
ENVELOPE = {"kind": "cell", "cell": dict(FLAT)}
# 前端历史版本只发 4 个字段（修复前的真实形状）——不能被当成"同一个 deck"而命中缓存
LEGACY4 = {k: FLAT[k] for k in ("number", "material", "density", "surface_expr")}


def fp(cells):
    return A._PREVIEW_CACHE.fingerprint("1 so 5", A._cell_geometry_payload(cells), "")


def test_flat_and_envelope_normalize_identically():
    """两种载荷形状（扁平 / 信封）→ 同一份规范化列表 ⇒ **同一指纹**（这正是修复点）。"""
    assert A._cell_geometry_payload([FLAT]) == A._cell_geometry_payload([ENVELOPE])
    assert fp([FLAT]) == fp([ENVELOPE])
    # 修复前这两句必然不等（一个吃扁平、一个吃信封）
    assert A._PREVIEW_CACHE.fingerprint("1 so 5", [FLAT], "") != \
           A._PREVIEW_CACHE.fingerprint("1 so 5", [ENVELOPE], "")


def test_geometry_or_filter_fields_all_change_fingerprint():
    """几何与 item-14 取舍相关的字段，**改一个就必须换指纹**（否则缓存会给出陈旧报告）。"""
    base = fp([FLAT])
    for field, value in [("surface_expr", "125"), ("imp_n", "1"), ("render", False),
                         ("fill", "7"), ("fill_grid", '{"a":1}'), ("comment", "别的"),
                         ("u", "3"), ("material", "1"), ("density", "-1.0"),
                         ("lat", "1"), ("trcl", "5"), ("number", 10)]:
        changed = dict(FLAT, **{field: value})
        assert fp([changed]) != base, f"{field} 改了但指纹没变"


def test_missing_semantic_fields_are_not_equal_to_present_ones():
    """⚠️ 反向风险：只发 4 字段的旧载荷**不能**与带语义字段的载荷同指纹 ——
    它们会被 `build_cells_data` 区别对待（前者跳过规则全失效），重叠报告因此不同。"""
    assert fp([LEGACY4]) != fp([FLAT])


def test_u_cells_are_dropped_by_caller_the_same_way():
    """调用方（两个 handler）都用 `_cell_u_of` 排除 universe 栅元 ⇒ 规范化前先滤，两端同解。"""
    u_cell = dict(FLAT, number=3, u="1")
    filtered = A._cell_geometry_payload([c for c in [FLAT, u_cell] if not A._cell_u_of(c)])
    assert [c["number"] for c in filtered] == [9]


def test_raw_rows_are_skipped():
    """raw 条件行（#ifdef 之类）不参与几何 ⇒ 不进指纹。"""
    assert A._cell_geometry_payload([{"kind": "raw", "text": "#ifdef A"}]) == []
