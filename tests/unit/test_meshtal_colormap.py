"""色阶映射测试 —— app/meshtal/colormap.py（契约 meshtal-visualization.md §4.3 / §4.3.1 / §12 A2.2）。

现状（2026-08-14，功能未实现 → 红基线）：`app/meshtal/colormap.py` 不存在 → ImportError → 全部红。

红基线 pin（按契约 §4.3 / §9.1）：
  1. WEATHER_STOPS 天气图锚点（§4.3.1 单一事实来源：蓝→青→黄→橙→红）—— RED
  2. weather_lut 长度/端点/插值（lut[0]=蓝、lut[-1]=红、中间=青/橙）—— RED
  3. map_value 色阶下限=显示阈值（v<lo → alpha 0；≥lo → alpha 255）—— RED
  4. map_value 线性映射端点/中点 —— RED
  5. golden_lut sha256 固定（§4.3.1 锚点线性 RGB 插值计算，python 与 TS 双端 golden）—— RED

纪律：纯 stdlib，不 import gui.backend.api_server / FreeCAD。golden 为契约锚点计算值，
后端 weather_lut 必须逐字节匹配（锚点改动 → 双端 + golden 一起重算）。
"""
import hashlib

import pytest

try:
    from app.meshtal.colormap import WEATHER_STOPS, map_value, weather_lut
    _MISSING = None
except ImportError as _e:  # pragma: no cover - 红基线：功能未实现
    _MISSING = _e


def _require_module():
    """模块缺失守卫：app/meshtal/colormap 不存在 → 本用例红（pin 缺口，非崩溃断言）。"""
    assert _MISSING is None, f"app/meshtal/colormap 模块缺失（红基线，功能未实现）: {_MISSING}"

# ── 1. 锚点（§4.3.1 单一事实来源）───────────────────────────────
def test_weather_stops_anchor_positions():
    """锚点位置 0.00/0.33/0.55/0.75/1.00，alpha 全 255。"""
    _require_module()
    positions = [p for p, _ in WEATHER_STOPS]
    assert positions == pytest.approx([0.00, 0.33, 0.55, 0.75, 1.00])
    for p, rgba in WEATHER_STOPS:
        assert rgba[3] == 255
        assert all(0 <= c <= 255 for c in rgba[:3])


def test_weather_stops_anchor_colors():
    """锚点颜色（#3B4CC0 蓝 / #00E5FF 青 / #FDE047 黄 / #F97316 橙 / #DC2626 红）。"""
    _require_module()
    by_pos = {round(p, 2): rgba for p, rgba in WEATHER_STOPS}
    assert by_pos[0.00][:3] == (0x3B, 0x4C, 0xC0)   # 蓝
    assert by_pos[0.33][:3] == (0x00, 0xE5, 0xFF)   # 青
    assert by_pos[0.55][:3] == (0xFD, 0xE0, 0x47)   # 黄
    assert by_pos[0.75][:3] == (0xF9, 0x73, 0x16)   # 橙
    assert by_pos[1.00][:3] == (0xDC, 0x26, 0x26)   # 红


# ── 2. weather_lut ──────────────────────────────────────────────
def test_weather_lut_length_and_shape():
    """weather_lut() 256 项、每项 RGBA 四元组。"""
    _require_module()
    lut = weather_lut()
    assert len(lut) == 256
    assert all(len(px) == 4 for px in lut)
    assert weather_lut(512) and len(weather_lut(512)) == 512


def test_weather_lut_endpoints():
    """LUT 端点：lut[0]=蓝 #3B4CC0、lut[-1]=红 #DC2626。"""
    _require_module()
    lut = weather_lut()
    assert lut[0][:3] == (0x3B, 0x4C, 0xC0)
    assert lut[-1][:3] == (0xDC, 0x26, 0x26)


def test_weather_lut_midpoints():
    """LUT 中间值：t≈0.33 → 青、t≈0.75 → 橙（锚点区间内线性插值）。"""
    _require_module()
    lut = weather_lut(256)
    assert lut[84][:3] == (0x00, 0xE5, 0xFF)        # i=84, t≈0.33 青
    assert lut[191][:3] == (0xF9, 0x74, 0x16)        # i=191, t≈0.75 橙（PM 仲裁：与 golden t-space 插值一致）


# ── 3. map_value 色阶下限 = 显示阈值 ────────────────────────────
def test_map_value_below_min_alpha_zero():
    """v < displayMin（=色阶下限 lo）→ alpha 0（低于不显示，A2.2/F5）。"""
    _require_module()
    lut = weather_lut()
    rgba = map_value(0.5, lo=10.0, hi=100.0, lut=lut)
    assert rgba[3] == 0, "v<lo 应 alpha 0（低于显示阈值不显示）"


def test_map_value_at_min_alpha_255_first_color():
    """v == lo（显示阈值）→ alpha 255 + 色阶下限颜色（LUT 首项）。"""
    _require_module()
    lut = weather_lut()
    rgba = map_value(10.0, lo=10.0, hi=100.0, lut=lut)
    assert rgba[3] == 255
    assert rgba[:3] == lut[0][:3]


def test_map_value_at_max_alpha_255_last_color():
    """v == hi → alpha 255 + LUT 末项。"""
    _require_module()
    lut = weather_lut()
    rgba = map_value(100.0, lo=10.0, hi=100.0, lut=lut)
    assert rgba[3] == 255
    assert rgba[:3] == lut[-1][:3]


# ── 4. map_value 线性映射 ───────────────────────────────────────
def test_map_value_linear_midpoint():
    """中点 v=(lo+hi)/2 → 映射到 LUT 中部（≈第 127/128 项）。"""
    _require_module()
    lut = weather_lut()
    mid = (10.0 + 100.0) / 2.0
    rgba = map_value(mid, lo=10.0, hi=100.0, lut=lut)
    assert rgba[3] == 255
    idx = 127  # round((0.5)*(256-1))
    assert rgba[:3] == lut[idx][:3]


# ── 5. golden_lut sha256（跨语言防漂移）─────────────────────────
def test_golden_lut_sha256():
    """weather_lut(256) 的 sha256 == 固定 golden。

    值由契约 §4.3.1 锚点线性 RGB 插值计算（round-half-even）；python colormap 与
    TS colorize.weatherLut() 双端必须产生相同 golden（§4.3.1 防漂移）。
    锚点改动 → 两侧 + 本 golden 一起重算。
    """
    _require_module()
    lut = weather_lut(256)
    flat = bytes(v for px in lut for v in px)
    digest = hashlib.sha256(flat).hexdigest()
    assert digest == "36770ae2b9cd2a2ac3b6e6a08de45d522261dfced960c0c1db49bc515358c038"
