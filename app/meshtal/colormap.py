"""天气图式色阶 LUT（契约 meshtal-visualization.md §4.3 / §4.3.1）。

单一事实来源 = WEATHER_STOPS（**viridis 8 锚点**：深紫→蓝→青绿→黄绿→亮黄）。python `weather_lut()` 与
TS `colorize.weatherLut()` 各自实现，`tests/unit/test_meshtal_colormap.py::golden_lut`
把 python 256 项 LUT 的 sha256 写成固定 golden，TS 端断言相等（跨语言防漂移）。

⚠️ **2026-09-19 换表**：原表是"蓝→青→黄→橙→红"的天气图配色，**在黑白打印下会塌**
（蓝与红亮度接近、中段黄过亮，读者分不出高低）。改用 **viridis**（感知均匀、色盲友好，
业界为灰度/打印可辨设计的标准色表）：亮度沿 t **单调递增**（相对亮度 0.019→0.782，
换算灰阶 42→228），打印/复印后仍能读高低。换表连带改了 TS 端 + 两个 golden sha256。

- `map_value(v, lo, hi, lut)`：v < lo（色阶下限 = 显示阈值）→ alpha 0（不显示）；
  否则线性映射到 LUT 索引（int 截断，中点 v=(lo+hi)/2 → 索引 127）。
"""
from __future__ import annotations

# §4.3.1 配色锚点（单一事实来源，python 与 TS 必须一致）
# viridis 官方锚点（取 8 个）：亮度单调递增，色盲与灰度打印可辨
WEATHER_STOPS = [
    (0.00, (0x44, 0x01, 0x54, 255)),   # 深紫（最低值，最暗）
    (0.14, (0x41, 0x44, 0x87, 255)),
    (0.29, (0x2A, 0x78, 0x8E, 255)),
    (0.43, (0x22, 0xA8, 0x84, 255)),
    (0.57, (0x55, 0xC6, 0x67, 255)),
    (0.71, (0xA5, 0xDB, 0x37, 255)),
    (0.86, (0xDF, 0xE3, 0x18, 255)),
    (1.00, (0xFD, 0xE7, 0x25, 255)),   # 亮黄（最高值，最亮）
]

# LUT 由 t = i/(n-1) 线性映射到锚点区间（round-half-even 逐通道）。
# golden sha256 44694904…（tests/unit/test_meshtal_colormap.py::golden_lut）即由
# 本插值公式计算 —— 与 TS `colorize.weatherLut()` 双端一致，防跨语言漂移。


def _interp_t(t: float) -> tuple[int, int, int, int]:
    """t ∈ [0,1] → RGBA（锚点区间内线性插值，round-half-even）。"""
    for k in range(len(WEATHER_STOPS) - 1):
        p0, c0 = WEATHER_STOPS[k]
        p1, c1 = WEATHER_STOPS[k + 1]
        if t <= p1:
            if p1 == p0:
                frac = 0.0
            else:
                frac = (t - p0) / (p1 - p0)
            return tuple(round(c0[c] + (c1[c] - c0[c]) * frac) for c in range(4))
    return WEATHER_STOPS[-1][1]


def weather_lut(n: int = 256) -> list[tuple[int, int, int, int]]:
    """256（默认）或自定义长度 LUT，每项 RGBA（t=i/(n-1) 线性插值）。"""
    if n <= 1:
        return [WEATHER_STOPS[0][1]] if n == 1 else []
    return [_interp_t(i / (n - 1)) for i in range(n)]


def map_value(v: float, lo: float, hi: float, lut: list) -> tuple[int, int, int, int]:
    """v 线性映射到 LUT；v < lo（显示阈值）→ alpha 0（低于不显示）。"""
    if v < lo:
        return (0, 0, 0, 0)
    if hi <= lo:
        idx = 0
    else:
        t = (v - lo) / (hi - lo)
        idx = int(t * (len(lut) - 1))
        idx = max(0, min(len(lut) - 1, idx))
    r, g, b, _a = lut[idx]
    return (r, g, b, 255)
