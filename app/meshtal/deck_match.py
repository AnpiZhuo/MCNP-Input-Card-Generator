"""deck↔meshtal 匹配检测（契约 meshtal-visualization.md §4.6A / §12 A1.2）。

纯 stdlib、纯函数、pytest 可测 seam。`grid_box` = meshtal bin 边界世界包围盒；
`model_box` = preview-3d 同源口径（`_compute_bound_from_surfaces` 的 [-B,B]³）。

比对机制（A1.2）：`/api/meshtal-parse` handler 请求带 modelBox 时调用
`check_match` → 响应 `match`；两者皆缺 → match:null。绝不静默错位。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AABB:
    """轴对齐包围盒（min/max 各为 3 元组）。"""
    min: tuple
    max: tuple

    def span(self) -> float:
        """max 轴向边长。"""
        return max(self.max[i] - self.min[i] for i in range(3))

    def volume(self) -> float:
        """三向乘积。"""
        v = 1.0
        for i in range(3):
            v *= (self.max[i] - self.min[i])
        return v


@dataclass
class MatchReport:
    """匹配检测报告。reason ∈ {"ok","overlap_too_small","offset_too_large"}。"""
    matched: bool
    overlap_fraction: float
    center_offset_frac: float
    reason: str
    message: str = ""


def overlap_fraction(a: AABB, b: AABB) -> float:
    """交集体积 / min(vol_a, vol_b)。完全包含 → 1.0；不相交 → 0.0。"""
    vol = 1.0
    for i in range(3):
        lo = max(a.min[i], b.min[i])
        hi = min(a.max[i], b.max[i])
        if hi <= lo:
            return 0.0
        vol *= (hi - lo)
    denom = min(a.volume(), b.volume())
    return vol / denom if denom > 0 else 0.0


def center_offset_frac(a: AABB, b: AABB) -> float:
    """中心距（max 轴向）/ max(model span)。重合 → 0.0。"""
    dist = 0.0
    for i in range(3):
        ca = (a.min[i] + a.max[i]) / 2.0
        cb = (b.min[i] + b.max[i]) / 2.0
        dist = max(dist, abs(ca - cb))
    denom = max(b.span(), 1e-12)
    return dist / denom


def check_match(grid_box: AABB, model_box: AABB, *,
                min_overlap: float = 0.2,
                max_center_offset: float = 0.5) -> MatchReport:
    """deck↔meshtal 匹配检测（容差可注入，覆盖契约边界）。

    - overlap < min_overlap              → matched=False, reason='overlap_too_small'
    - center_offset > max_center_offset  → matched=False, reason='offset_too_large'
    - 否则                                → matched=True,  reason='ok'
    """
    ov = overlap_fraction(grid_box, model_box)
    off = center_offset_frac(grid_box, model_box)
    if ov < min_overlap:
        return MatchReport(False, ov, off, "overlap_too_small")
    if off > max_center_offset:
        return MatchReport(False, ov, off, "offset_too_large")
    return MatchReport(True, ov, off, "ok")
