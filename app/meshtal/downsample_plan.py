"""降采样与分辨率自适应决策（契约 meshtal-visualization.md §4.4 / §8 / §12 A2.3 / F3）。

- GPU 驻留预算 ≤256MB（当前帧 RGBA + 外壳几何）。
- 128³ 默认（流畅）/ 256³ 仅显式选择。
- native 更小保 native（avg_factor=1）。
- 超预算 → over_budget=True / popup 素材（recommended ∈ {"smooth","precise"}）。

纯 stdlib，不依赖 numpy。
"""
from __future__ import annotations

from dataclasses import dataclass

GPU_BUDGET_BYTES = 256 * 1024 * 1024   # GPU 驻留预算 ≤256MB
DEFAULT_RESOLUTION = 128               # 128³ 默认（流畅）
MAX_RESOLUTION = 256                   # 256³ 供用户显式选


def estimate_texture_bytes(dims) -> int:
    """RGBA 每体素 4B：128³=8MiB、256³=64MiB。"""
    n = 1
    for d in dims:
        n *= int(d)
    return n * 4


@dataclass
class Plan:
    """降采样方案。"""
    out_dims: tuple
    avg_factor: tuple
    fits_budget: bool
    over_budget: bool


@dataclass
class ResolutionDecision:
    """分辨率决策（A2.3 自动 128³ / 256³ 显式 / 超预算弹窗素材 F3）。"""
    resolution: tuple
    popup: bool
    recommended: str
    avg_factor: tuple
    out_dims: tuple


def plan_downsample(native, target_res, budget_bytes: int = GPU_BUDGET_BYTES) -> Plan:
    """每轴 out = min(target_res, native)；每轴 factor = max(1, ceil(native/out))。"""
    out_dims = tuple(min(int(target_res), int(n)) for n in native)
    avg_factor = tuple(max(1, -(-int(n) // int(o))) for n, o in zip(native, out_dims))
    fits = estimate_texture_bytes(out_dims) <= budget_bytes
    return Plan(out_dims, avg_factor, fits, not fits)


def decide_resolution(native, requested, budget_bytes: int = GPU_BUDGET_BYTES) -> ResolutionDecision:
    """requested=128 默认 / 256 显式；native 更小保 native；超预算 → popup 素材。"""
    if requested in (None, 0):
        target = DEFAULT_RESOLUTION
    else:
        target = int(requested)
    plan = plan_downsample(native, target, budget_bytes=budget_bytes)
    return ResolutionDecision(
        resolution=plan.out_dims,
        popup=plan.over_budget,
        recommended="smooth" if plan.over_budget else "",
        avg_factor=plan.avg_factor,
        out_dims=plan.out_dims,
    )
