"""`gui/backend/_cross_section_helper.py` 的 TR 卡解析必须**复用**权威实现。

背景（`docs/audit/t2-backend-debt.md` BE-15）：该文件内联过第二份 `parse_tr_cards`
（复制粘贴自 `api_server` 的旧版），于是同一个 deck 在 **preview-3d** 与 **cross-section**
两条通道下解析出的几何可以不同 —— 而且没有任何报错。修复是让它转发给
`api_server.parse_tr_cards`（唯一实现）；本文件是这条约定的回归闸门。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_DIR / "gui" / "backend"
for p in (str(PROJECT_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

api_server = pytest.importorskip("api_server", reason="需要 gui/backend 可导入（pymcnp）")
helper = pytest.importorskip("_cross_section_helper", reason="需要 helper 可导入")

#: 覆盖两份实现真正分叉过的每一处：`*TRn` 角度、`$` 行内注释、6 值叉积、M=-1、非法条目数。
_TRICKY = "\n".join([
    "TR1 0 0 100",
    "TR2 10 0 0 0 1 0 -1 0 0 0 0 1 -1",
    "*TR3 0 0 0 90 90 0 0 90 90 90 0 90",
    "TR4 0 0 0  1 0 0  0 1 0 $ 六值 + 行内注释",
    "TR5 0 0 0  0 0 1  1 0",
])


def test_helper_tr_parser_is_the_authoritative_one():
    """同一条 deck 文本 → 两条通道必须得到**逐字节相同**的 TR dict。"""
    assert helper.parse_tr_cards(_TRICKY) == api_server.parse_tr_cards(_TRICKY)


def test_helper_tr_parser_inherits_m_and_star_handling():
    """转发后必须连带拿到 `*TRn` 角度与 `M=-1` 的处理（旧副本两样都不认）。"""
    cards = helper.parse_tr_cards(_TRICKY)
    assert cards["2"]["translate"] == pytest.approx([0.0, -10.0, 0.0])
    star = cards["3"]["rotate"]
    assert star[0] == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)
    assert "5" not in cards, "5 值模式应被明确拒绝，不得静默退化"
