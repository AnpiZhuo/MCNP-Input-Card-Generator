"""deck↔meshtal 匹配检测测试 —— app/meshtal/deck_match.py（契约 meshtal-visualization.md §4.6A / §12 A1.2）。

现状（2026-08-14，功能未实现 → 红基线）：`app/meshtal/deck_match.py` 不存在 → ImportError → 全部红。

红基线 pin（按契约 §4.6A / §12 A1.2）：
  1. AABB min/max/span/volume —— RED
  2. overlap_fraction（交集体积 / min(vol_a,vol_b)：完全包含=1.0、不相交=0）—— RED
  3. center_offset_frac（中心距 / max(model span)：重合=0）—— RED
  4. check_match 完全包含 → matched=True reason='ok' —— RED
  5. check_match 交集过小 → reason='overlap_too_small' matched=False —— RED
  6. check_match 中心偏移过大 → reason='offset_too_large' matched=False —— RED
  7. check_match 完全不相交 → matched=False（绝不静默错位）—— RED
  8. 容差可注入：min_overlap=0.2 / max_center_offset=0.5 边界（注入 0.3 收紧 → 边界翻转）—— RED

纪律：纯 stdlib，不 import gui.backend.api_server / freecad_preview / FreeCAD。
"""
import math

import pytest

try:
    from app.meshtal.deck_match import (
        AABB,
        MatchReport,
        center_offset_frac,
        check_match,
        overlap_fraction,
    )
    _MISSING = None
except ImportError as _e:  # pragma: no cover - 红基线：功能未实现
    _MISSING = _e


def _require_module():
    """模块缺失守卫：app/meshtal/deck_match 不存在 → 本用例红（pin 缺口，非崩溃断言）。"""
    assert _MISSING is None, f"app/meshtal/deck_match 模块缺失（红基线，功能未实现）: {_MISSING}"

# 契约 §12 A1.2：grid_box = meshtal bin 边界世界包围盒；model_box = preview-3d 同源口径 [-B,B]³
# 参考：valid_38 grid_bounds min=[-100,-100,-150] max=[100,100,-50]
# 模块缺失时不得在模块顶层求值 AABB（红基线守卫先行），故经 helper 惰性构造。
def _ref_boxes() -> tuple:
    return (
        AABB(min=(-100, -100, -150), max=(100, 100, -50)),
        AABB(min=(-200, -200, -200), max=(200, 200, 200)),
    )


# ── 1. AABB ─────────────────────────────────────────────────────
def test_aabb_span_and_volume():
    """AABB.span()（max 轴向边长）/ volume()（三向乘积）。"""
    _require_module()
    b = AABB(min=(0, 0, 0), max=(100, 100, 100))
    assert b.volume() == pytest.approx(1_000_000.0)
    assert b.span() == pytest.approx(100.0)
    b2 = AABB(min=(-100, -100, -150), max=(100, 100, -50))
    assert b2.volume() == pytest.approx(200 * 200 * 100)
    assert b2.span() == pytest.approx(200.0)


# ── 2. overlap_fraction ─────────────────────────────────────────
def test_overlap_identical_boxes():
    """重合盒 → overlap_fraction 1.0。"""
    _require_module()
    a = AABB(min=(0, 0, 0), max=(100, 100, 100))
    assert overlap_fraction(a, a) == pytest.approx(1.0)


def test_overlap_fully_contained_is_one():
    """grid 完全包含于 model → 交集体积/min(vol)=1.0（契约口径，非交集体积/model 体积）。"""
    _require_module()
    grid = AABB(min=(0, 0, 0), max=(50, 50, 50))
    model = AABB(min=(0, 0, 0), max=(100, 100, 100))
    assert overlap_fraction(grid, model) == pytest.approx(1.0)


def test_overlap_partial():
    """部分重叠：交集体积 / min(vol)。"""
    _require_module()
    a = AABB(min=(0, 0, 0), max=(100, 100, 100))          # vol 1e6
    b = AABB(min=(50, 50, 50), max=(150, 150, 150))        # vol 1e6，交叠 [50,100]³=125000
    assert overlap_fraction(a, b) == pytest.approx(0.125)


def test_overlap_disjoint_zero():
    """完全不相交 → 0.0。"""
    _require_module()
    a = AABB(min=(0, 0, 0), max=(100, 100, 100))
    b = AABB(min=(200, 200, 200), max=(300, 300, 300))
    assert overlap_fraction(a, b) == pytest.approx(0.0)


# ── 3. center_offset_frac ───────────────────────────────────────
def test_center_offset_identical_zero():
    """中心重合 → 0.0。"""
    _require_module()
    a = AABB(min=(0, 0, 0), max=(100, 100, 100))
    assert center_offset_frac(a, a) == pytest.approx(0.0)


def test_center_offset_normalized_by_model_span():
    """中心距 / max(model span)：偏移 45 单位、model span 100 → 0.45。"""
    _require_module()
    grid = AABB(min=(0, 0, 0), max=(100, 100, 10))
    model = AABB(min=(0, 0, 0), max=(100, 100, 100))
    # 中心 (50,50,5) vs (50,50,50)：dist=45
    assert center_offset_frac(grid, model) == pytest.approx(45.0 / 100.0)


# ── 4. check_match：完全包含 → ok ───────────────────────────────
def test_match_fully_contained_ok():
    """grid 完全包含于 model（含 valid_38 参考包围盒）→ matched=True, reason='ok'。"""
    _require_module()
    grid38, model38 = _ref_boxes()
    for grid, model in [
        (grid38, model38),                    # valid_38 网格 ⊂ [-200,200]³ 模型
        (AABB(min=(0, 0, 0), max=(50, 50, 50)), AABB(min=(0, 0, 0), max=(100, 100, 100))),
    ]:
        report = check_match(grid, model)
        assert isinstance(report, MatchReport)
        assert report.matched is True, f"{report.reason}: {report.message}"
        assert report.reason == "ok"
        assert report.overlap_fraction == pytest.approx(1.0)
        assert report.message == ""


def test_match_report_has_all_fields():
    """MatchReport 字段齐全：matched/overlap_fraction/center_offset_frac/reason/message。"""
    _require_module()
    grid38, model38 = _ref_boxes()
    report = check_match(grid38, model38)
    assert isinstance(report.matched, bool)
    assert isinstance(report.overlap_fraction, float)
    assert isinstance(report.center_offset_frac, float)
    assert report.reason in {"ok", "overlap_too_small", "offset_too_large"}


# ── 5. check_match：交集过小 → overlap_too_small ────────────────
def test_match_overlap_too_small():
    """overlap<min_overlap → matched=False, reason='overlap_too_small'。

    用 max_center_offset=1.0 注入抑制中心偏移判据，隔离 overlap 判据。
    """
    _require_module()
    grid = AABB(min=(50, 50, 50), max=(150, 150, 150))    # 交叠 0.125
    model = AABB(min=(0, 0, 0), max=(100, 100, 100))
    report = check_match(grid, model, max_center_offset=1.0)
    assert report.matched is False
    assert report.reason == "overlap_too_small"
    assert report.overlap_fraction == pytest.approx(0.125)


# ── 6. check_match：中心偏移过大 → offset_too_large ─────────────
def test_match_offset_too_large():
    """center_offset_frac>max_center_offset → matched=False, reason='offset_too_large'。

    完全包含（overlap=1.0 通过）但中心偏移 0.45 > 注入 0.3 → 隔离 offset 判据。
    """
    _require_module()
    grid = AABB(min=(0, 0, 0), max=(100, 100, 10))
    model = AABB(min=(0, 0, 0), max=(100, 100, 100))
    report = check_match(grid, model, max_center_offset=0.3)
    assert report.matched is False
    assert report.reason == "offset_too_large"
    assert report.center_offset_frac == pytest.approx(0.45)


# ── 7. check_match：完全不相交 → matched False ──────────────────
def test_match_disjoint_never_silent():
    """完全不相交 → matched=False（绝不静默错位，reason 为 overlap_too_small 或 offset_too_large）。"""
    _require_module()
    grid = AABB(min=(200, 200, 200), max=(300, 300, 300))
    model = AABB(min=(0, 0, 0), max=(100, 100, 100))
    report = check_match(grid, model)
    assert report.matched is False
    assert report.reason in {"overlap_too_small", "offset_too_large"}


# ── 8. 容差边界（min_overlap=0.2 / max_center_offset=0.5）────────
def test_tolerance_default_contract_values():
    """契约默认容差：min_overlap=0.2、max_center_offset=0.5。"""
    _require_module()
    grid = AABB(min=(0, 0, 0), max=(100, 100, 10))   # overlap=1.0, offset_frac=0.45
    model = AABB(min=(0, 0, 0), max=(100, 100, 100))
    # 默认 0.5：0.45 < 0.5 → matched
    assert check_match(grid, model).matched is True
    assert check_match(grid, model).center_offset_frac == pytest.approx(0.45)


def test_tolerance_boundary_flips_with_injection():
    """收紧 max_center_offset=0.3 → 同输入从 matched 翻转为 offset_too_large。"""
    _require_module()
    grid = AABB(min=(0, 0, 0), max=(100, 100, 10))
    model = AABB(min=(0, 0, 0), max=(100, 100, 100))
    assert check_match(grid, model, max_center_offset=0.5).matched is True
    assert check_match(grid, model, max_center_offset=0.3).matched is False
    assert check_match(grid, model, max_center_offset=0.3).reason == "offset_too_large"
