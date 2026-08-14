"""体积数据构建（契约 meshtal-visualization.md §4.2 / §8 KPI）。

- 取 (e,t) 稠密数组 → `downsample_plan` 算 avgFactor → box-average 均值降采样
  （保总量：输入块体积 == 输出体素体积，块和不变）。
- 归一化在降采样**之后**做（scalar_range 反映降采样后数组范围）。
- 标量帧 dtype=uint8、值域 [0,255]。
- world_box 永远来自 meshtal bin 边界（降采样不改世界坐标）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .downsample_plan import GPU_BUDGET_BYTES, plan_downsample
from .meshtal_parser import MeshtalFile


@dataclass
class Frame:
    """单帧标量体积。"""
    resolution: tuple
    world_box: dict            # {"min":[x,y,z],"max":[x,y,z]} 来自 bin 边界
    scalar: np.ndarray         # uint8，shape = resolution
    scalar_range: tuple        # 降采样后 (min,max)
    avg_factor: tuple
    downsampled: bool


def _box_average(arr: np.ndarray, avg_factor: tuple) -> np.ndarray:
    """box-average 均值降采样（保总量）。

    每输出体素 = 输入块内原值均值。不足整块的部分以 0 填充（边界块仍求均值，
    保总量近似；MCNP 网格维度通常可被 factor 整除）。
    """
    fi, fj, fk = (int(f) for f in avg_factor)
    if fi == 1 and fj == 1 and fk == 1:
        return arr
    ni, nj, nk = arr.shape
    pi = -(-ni // fi) * fi
    pj = -(-nj // fj) * fj
    pk = -(-nk // fk) * fk
    padded = np.zeros((pi, pj, pk), dtype=np.float64)
    padded[:ni, :nj, :nk] = arr
    reshaped = padded.reshape(pi // fi, fi, pj // fj, fj, pk // fk, fk)
    return reshaped.mean(axis=(1, 3, 5))


def build_frame(mf: MeshtalFile, tally_number: int, energy_bin: int, time_bin: int,
                resolution: int, budget_bytes: int = GPU_BUDGET_BYTES) -> Frame:
    """构建 (energy,time) 帧的标量体积（Uint8，归一化在降采样后）。

    契约 §3.3 guard 语义：tallyNumber 不存在 → KeyError；energyBin/timeBin 越界
    → IndexError。
    """
    tally = next((t for t in mf.tallies if t.number == tally_number), None)
    if tally is None:
        raise KeyError(f"tally number {tally_number} 不存在")
    if (energy_bin, time_bin) not in tally.data:
        raise IndexError(f"帧 (energy={energy_bin}, time={time_bin}) 不存在")

    data = tally.data[(energy_bin, time_bin)]
    plan = plan_downsample(data.shape, resolution, budget_bytes=budget_bytes)
    downsampled = _box_average(data, plan.avg_factor)
    lo = float(downsampled.min())
    hi = float(downsampled.max())

    if hi > lo:
        scaled = (downsampled - lo) / (hi - lo) * 255.0
        u8 = np.clip(scaled, 0, 255).astype(np.uint8)
    else:
        u8 = np.zeros(downsampled.shape, dtype=np.uint8)

    world_box = {
        "min": [float(tally.bins_x[0]), float(tally.bins_y[0]), float(tally.bins_z[0])],
        "max": [float(tally.bins_x[-1]), float(tally.bins_y[-1]), float(tally.bins_z[-1])],
    }
    downsampled_flag = any(int(f) > 1 for f in plan.avg_factor)
    return Frame(
        resolution=plan.out_dims,
        world_box=world_box,
        scalar=u8,
        scalar_range=(lo, hi),
        avg_factor=plan.avg_factor,
        downsampled=downsampled_flag,
    )
