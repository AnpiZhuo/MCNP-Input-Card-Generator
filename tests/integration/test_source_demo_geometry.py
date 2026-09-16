"""源演示几何准备（`api_server.MCNPHandler._prepare_source_geometry`）的回归。

本文件覆盖两个**只在真实后端路径上才暴露**的缺陷（单测里用手写 geometry dict 全绿，
所以长期没被发现）：

1. `vc._surface_transform(tr_data)` 被误传两个参数 → `TypeError` → 被 except 吞掉
   → `surfaces` 恒为空 → **任何 `SDEF SUR=` 面源都报「曲面未定义」**。
2. MCNP 的**轴对齐圆柱缩写** `CX/CY/CZ`（≡ `C/X` 等）pymcnp 解析不了 → 被静默丢弃
   → 同样表现为「曲面未定义」，且 3D 预览/截面/STEP 导出同时受影响。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_DIR / "gui" / "backend"
for p in (str(PROJECT_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

api_server = pytest.importorskip("api_server", reason="需要 gui/backend 可导入（pymcnp）")


def _prep(surfaces_text: str, tr_text: str = "", cells: list | None = None):
    return api_server.MCNPHandler._prepare_source_geometry(None, surfaces_text,
                                                           cells or [], tr_text)


def test_plane_surface_ready_for_source_sampling():
    """`5 PX 5` 必须出现在 surfaces 里（旧实现 surface_fn 调用即抛错 → 面源全废）。"""
    g = _prep("5 PX 5")
    assert g["geometryErrors"] == [], g["geometryErrors"]
    s = g["surfaces"].get(5)
    assert s is not None, "PX 曲面未进入 surfaces（SDEF SUR=5 必然报'曲面未定义'）"
    assert s["type"] == "PX" and s["params"] == [5.0]
    assert callable(s["field"])


def test_sphere_surface_ready_and_normal_available():
    g = _prep("6 S 0 0 0 10")
    assert g["geometryErrors"] == []
    s = g["surfaces"].get(6)
    assert s is not None and s["type"] == "S"
    # api_server 侧补了 TR 的 rotate/origin（面源位置/法线要在世界系里）
    assert tuple(s["origin"]) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("text,expect_type", [
    ("7 CX 0 0 3", "C/X"),
    ("8 CY 1 2 3", "C/Y"),
    ("9 CZ 0 0 5", "C/Z"),
])
def test_axis_aligned_cylinder_abbrev_not_dropped(text, expect_type):
    """`CX/CY/CZ` 三项式缩写必须被改写成 `C/X` 等（pymcnp 对 CX/CY 什么都不认）。"""
    g = _prep(text)
    num = int(text.split()[0])
    s = g["surfaces"].get(num)
    assert s is not None, f"{text} 被丢弃"
    assert s["type"] == expect_type


def test_cz_two_item_short_form_is_kept_verbatim():
    """`CZ R`（两项式，MCNP 允许且 pymcnp 认）**不得**被改写成 `C/Z R`。

    2026-09-17 回归：把 `CZ` 无条件改写成 `C/Z` 后 `7 cz 0.3` 少两个参数 →
    pymcnp 抛 InpError → 被静默丢弃 → `test_api_contract.py` 的格元覆盖
    （其 COV_SURF 用的就是 `7 cz 0.3`）两例转红。
    """
    g = _prep("7 cz 0.3")
    assert g["geometryErrors"] == []
    s = g["surfaces"].get(7)
    assert s is not None, "CZ R 两项式被丢弃"
    assert s["type"] == "CZ" and s["params"] == [0.3]


def test_tr_cards_passed_through_for_sdef_tr():
    """SDEF TR=n 需要在 geometry 里拿到 TR 卡数据。"""
    g = _prep("5 PX 5", "TR2 0 0 100")
    assert "trCards" in g and "2" in g["trCards"]
    assert g["trCards"]["2"]["translate"] == [0.0, 0.0, 100.0]


def test_cell_volumes_available_for_sp_v():
    """`SP V`（C810 3-64 概率 ∝ 栅元体积）需要 geometry 给出逐栅元体积。

    立方体 −1..1 ⇒ 8；球 SO 2 ⇒ 33.51。旧实现根本没算体积 ⇒ SP V 无从实现。
    """
    cube = _prep("1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 pz -1\n6 pz 1",
                 cells=[{"number": 1, "material": "1", "density": "-1",
                         "surface_expr": "1 -2 3 -4 5 -6", "imp_n": "1", "render": True}])
    assert cube["geometryErrors"] == [], cube["geometryErrors"]
    assert abs(cube["cellVolumes"][1] - 8.0) < 0.1, cube["cellVolumes"]

    sphere = _prep("1 so 2", cells=[{"number": 1, "material": "1", "density": "-1",
                                     "surface_expr": "-1", "imp_n": "1", "render": True}])
    v = sphere["cellVolumes"][1]
    assert abs(v - 4.0 / 3.0 * 3.141592653589793 * 8.0) / v < 0.03, v
