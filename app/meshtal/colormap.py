"""天气图式色阶 LUT（契约 meshtal-visualization.md §4.3 / §4.3.1）。

单一事实来源 = WEATHER_STOPS（蓝→青→黄→橙→红）。python `weather_lut()` 与
TS `colorize.weatherLut()` 各自实现，`tests/unit/test_meshtal_colormap.py::golden_lut`
把 python 256 项 LUT 的 sha256 写成固定 golden，TS 端断言相等（跨语言防漂移）。

- `map_value(v, lo, hi, lut)`：v < lo（色阶下限 = 显示阈值）→ alpha 0（不显示）；
  否则线性映射到 LUT 索引（int 截断，中点 v=(lo+hi)/2 → 索引 127）。
"""
from __future__ import annotations

# §4.3.1 配色锚点（单一事实来源，python 与 TS 必须一致）
WEATHER_STOPS = [
    (0.00, (0x3B, 0x4C, 0xC0, 255)),   # 蓝
    (0.33, (0x00, 0xE5, 0xFF, 255)),   # 青
    (0.55, (0xFD, 0xE0, 0x47, 255)),   # 黄
    (0.75, (0xF9, 0x73, 0x16, 255)),   # 橙
    (1.00, (0xDC, 0x26, 0x26, 255)),   # 红
]

# LUT 由 t = i/(n-1) 线性映射到锚点区间（round-half-even 逐通道）。
# golden sha256 36770ae2…（tests/unit/test_meshtal_colormap.py::golden_lut）即由
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
