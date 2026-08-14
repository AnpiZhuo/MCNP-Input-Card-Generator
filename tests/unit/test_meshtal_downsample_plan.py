"""降采样与自适应决策测试 —— app/meshtal/downsample_plan.py（契约 meshtal-visualization.md §4.4 / §12 A2.3 / F3）。

现状（2026-08-14，功能未实现 → 红基线）：`app/meshtal/downsample_plan.py` 不存在 → ImportError → 全部红。

红基线 pin：
  1. 预算常量：GPU_BUDGET_BYTES=256MiB、DEFAULT_RESOLUTION=128、MAX_RESOLUTION=256 —— RED
  2. estimate_texture_bytes：RGBA 每体素 4B（128³=8MiB、256³=64MiB）≤ 预算 —— RED
  3. plan_downsample：native 更小保 native（avg_factor=1）—— RED
  4. plan_downsample：128³ 默认 avg_factor=ceil(native/out)—— RED
  5. plan_downsample：超预算 → over_budget=True —— RED
  6. decide_resolution：A2.3 无用户选择自动 128³（仅显式才 256³）—— RED
  7. decide_resolution：256³ 显式 / 超预算 popup 素材（F3）—— RED

纪律：纯 stdlib，不 import gui.backend.api_server / FreeCAD / numpy。
"""
import pytest

try:
    from app.meshtal.downsample_plan import (
        DEFAULT_RESOLUTION,
        GPU_BUDGET_BYTES,
        MAX_RESOLUTION,
        decide_resolution,
        estimate_texture_bytes,
        plan_downsample,
    )
    _MISSING = None
except ImportError as _e:  # pragma: no cover - 红基线：功能未实现
    _MISSING = _e


def _require_module():
    """模块缺失守卫：app/meshtal/downsample_plan 不存在 → 本用例红（pin 缺口，非崩溃断言）。"""
    assert _MISSING is None, f"app/meshtal/downsample_plan 模块缺失（红基线，功能未实现）: {_MISSING}"


def _res_per_axis(d) -> int:
    """容忍 resolution 为 int 或 (int,int,int) 两种表示。"""
    r = d.resolution
    if isinstance(r, (tuple, list)):
        assert len(set(int(x) for x in r)) == 1, f"每轴分辨率应一致: {r}"
        return int(r[0])
    return int(r)


# ── 1. 预算常量 ─────────────────────────────────────────────────
def test_budget_constants():
    """GPU 驻留 ≤256MB；128³ 默认、256³ 显式上限。"""
    _require_module()
    assert GPU_BUDGET_BYTES == 256 * 1024 * 1024
    assert DEFAULT_RESOLUTION == 128
    assert MAX_RESOLUTION == 256


# ── 2. estimate_texture_bytes ───────────────────────────────────
def test_estimate_texture_bytes_rgba():
    """每体素 4 字节（RGBA）：128³=8MiB、256³=64MiB，均 ≤ 256MB 预算。"""
    _require_module()
    b128 = estimate_texture_bytes((128, 128, 128))
    b256 = estimate_texture_bytes((256, 256, 256))
    assert b128 == 128 ** 3 * 4 == 8 * 1024 * 1024
    assert b256 == 256 ** 3 * 4 == 64 * 1024 * 1024
    assert b128 <= GPU_BUDGET_BYTES and b256 <= GPU_BUDGET_BYTES


# ── 3. plan_downsample：native 更小保 native ────────────────────
def test_plan_keeps_native_when_smaller():
    """native(10,10,10) + 目标 128 → out=(10,10,10)、avg_factor=(1,1,1)、不超预算。"""
    _require_module()
    p = plan_downsample((10, 10, 10), 128)
    assert tuple(p.out_dims) == (10, 10, 10)
    assert tuple(p.avg_factor) == (1, 1, 1)
    assert p.fits_budget is True
    assert p.over_budget is False


def test_plan_128_avg_factor():
    """native(1000,1000,1000) + 128 → out=(128,128,128)、avg_factor=ceil(1000/128)=8。"""
    _require_module()
    p = plan_downsample((1000, 1000, 1000), 128)
    assert tuple(p.out_dims) == (128, 128, 128)
    assert tuple(p.avg_factor) == (8, 8, 8)
    assert p.over_budget is False


def test_plan_explicit_256():
    """native(256,256,256) + 显式 256 → 保 native，avg_factor=1。"""
    _require_module()
    p = plan_downsample((256, 256, 256), 256)
    assert tuple(p.out_dims) == (256, 256, 256)
    assert tuple(p.avg_factor) == (1, 1, 1)


# ── 4. plan_downsample：超预算 ──────────────────────────────────
def test_plan_over_budget_flag():
    """128³ 输出 8MiB > 注入 4MiB 预算 → over_budget=True。"""
    _require_module()
    p = plan_downsample((1000, 1000, 1000), 128, budget_bytes=4 * 1024 * 1024)
    assert p.over_budget is True
    assert p.fits_budget is False
    assert tuple(p.out_dims) == (128, 128, 128)


# ── 5. decide_resolution：A2.3 自动 128³ ────────────────────────
def test_decide_resolution_automatic_128():
    """无用户选择 → 自动 128³（A2.3）；128³ 预算内 → 不弹窗。"""
    _require_module()
    d = decide_resolution(native=(1000, 1000, 1000), requested=None,
                          budget_bytes=GPU_BUDGET_BYTES)
    assert _res_per_axis(d) == 128
    assert d.popup is False


def test_decide_resolution_native_smaller_no_popup():
    """native 已小于 128 → 保 native，无弹窗。"""
    _require_module()
    d = decide_resolution(native=(32, 32, 32), requested=None,
                          budget_bytes=GPU_BUDGET_BYTES)
    assert _res_per_axis(d) == 32
    assert d.popup is False


def test_decide_resolution_256_only_explicit():
    """256³ 仅显式选择：requested=256 → 256（预算内不弹窗）。"""
    _require_module()
    d = decide_resolution(native=(512, 512, 512), requested=256,
                          budget_bytes=GPU_BUDGET_BYTES)
    assert _res_per_axis(d) == 256
    assert d.popup is False


def test_decide_resolution_over_budget_popup():
    """超预算 → popup=True + recommended 素材（'smooth'/'precise'，F3 弹窗决策）。"""
    _require_module()
    d = decide_resolution(native=(1000, 1000, 1000), requested=256,
                          budget_bytes=4 * 1024 * 1024)
    assert d.popup is True
    assert d.recommended in ("smooth", "precise")
