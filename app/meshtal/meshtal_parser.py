"""MESHTAL 文件解析（契约 meshtal-visualization.md §2.2 / §3.4）。

策略：pymcnp 优先（惰性 import，作为标准 MCNP 格式校验）→ 成功则用 pymcnp
header 的 code/histories 元数据；抛异常/ImportError → 轻量兜底。两条路径共用
同一个稠密数组构建核心，保证产出同一 MeshtalFile。

数据行列序按 MCNP 实际格式 [Energy] [Time] X Y Z Result RelError 判别：
  has_energy_col = energyBins > 1；has_time_col = timeBins > 1。
"Total" 汇总行跳过（不归属任何单 (e,t) 帧）。
x/y/z 栅元中心 → 最近邻 bin 索引；energy/time 边界标签 → bisect 位置 - 1。
"""
from __future__ import annotations

import bisect
import os
import re
from dataclasses import dataclass, field

import numpy as np

_PARTICLE_MAP = {
    "neutron": "n",
    "photon": "p",
    "electron": "e",
    "proton": "h",
}


@dataclass
class MeshTally:
    """单个 MESH 计数（契约 §2.2）。"""
    number: int
    particle: str
    geom: str
    bins_x: list
    bins_y: list
    bins_z: list
    bins_energy: list
    bins_time: list
    data: dict                      # {(e,t): np.ndarray(float64, (ni,nj,nk))}
    error: dict                     # {(e,t): np.ndarray(float64, (ni,nj,nk))}
    scalar_range: tuple             # (dataMin, dataMax) 全帧


@dataclass
class MeshtalFile:
    """规范化 MESHTAL 文件（契约 §2.2）。"""
    path: str
    mtime: float
    code: str
    histories: float
    tallies: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _parse_global_header(text: str) -> tuple[str, float]:
    """从文件头提取 code + histories。"""
    code = "mcnp"
    m = re.match(r'^\s*(\w+)', text)
    if m:
        code = m.group(1)
    histories = 0.0
    mh = re.search(r'Number of histories used for normalizing tallies\s*=\s*([\d.Ee+\-]+)', text)
    if mh:
        try:
            histories = float(mh.group(1))
        except ValueError:
            histories = 0.0
    return code, histories


def _center_index(edges: list, value: float) -> int:
    """栅元中心值 → bin 索引（最近邻中心，容差由最近邻保证）。"""
    nbins = len(edges) - 1
    best, best_d = 0, float("inf")
    for i in range(nbins):
        center = (edges[i] + edges[i + 1]) / 2.0
        d = abs(value - center)
        if d < best_d:
            best_d, best = d, i
    return best


def _bin_index(edges: list, value: float) -> int:
    """energy/time 边界标签值 → bin 索引（bisect 位置 - 1）。"""
    pos = bisect.bisect_left(edges, value)
    return max(0, min(len(edges) - 2, pos - 1))


def _parse_tally_block(num: int, body: str) -> MeshTally:
    """解析单个 tally 段 → MeshTally（共享稠密数组构建核心）。"""
    lines = body.splitlines()
    bins_x = bins_y = bins_z = energy_edges = time_edges = None
    particle = "n"
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m = re.match(r'^([A-Za-z]+)\s+mesh tally\.$', s)
        if m:
            particle = _PARTICLE_MAP.get(m.group(1).lower(), m.group(1).lower())
            continue
        m = re.match(r'^X direction:\s*(.+)$', s)
        if m:
            bins_x = [float(x) for x in m.group(1).split()]
            continue
        m = re.match(r'^Y direction:\s*(.+)$', s)
        if m:
            bins_y = [float(x) for x in m.group(1).split()]
            continue
        m = re.match(r'^Z direction:\s*(.+)$', s)
        if m:
            bins_z = [float(x) for x in m.group(1).split()]
            continue
        m = re.match(r'^Energy bin boundaries:\s*(.+)$', s)
        if m:
            energy_edges = [float(x) for x in m.group(1).split()]
            continue
        m = re.match(r'^Time bin boundaries:\s*(.+)$', s)
        if m:
            time_edges = [float(x) for x in m.group(1).split()]
            continue
    if not (bins_x and bins_y and bins_z):
        raise ValueError("未找到 X/Y/Z direction bin 边界，无法构建网格")

    energy_edges = energy_edges if energy_edges else [0.0, 1e36]
    time_edges = time_edges if time_edges else []
    energy_bins = max(1, len(energy_edges) - 1)
    time_bins = max(0, len(time_edges) - 1)
    has_energy_col = energy_bins > 1
    has_time_col = time_bins > 1
    x_off = (1 if has_energy_col else 0) + (1 if has_time_col else 0)
    ncols = 5 + x_off

    ni, nj, nk = len(bins_x) - 1, len(bins_y) - 1, len(bins_z) - 1
    data = {}
    error = {}
    total_min = float("inf")
    total_max = float("-inf")

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if "Rel Error" in s or "RelError" in s or "Energy" in s or "Time" in s:
            continue
        toks = s.split()
        if len(toks) != ncols:
            continue
        if "Total" in toks:
            continue
        try:
            nums = [float(t) for t in toks]
        except ValueError:
            continue
        if has_energy_col:
            e_idx = _bin_index(energy_edges, nums[0])
            t_start = 1
        else:
            e_idx = 0
            t_start = 0
        if has_time_col:
            t_idx = _bin_index(time_edges, nums[t_start])
            t_start += 1
        else:
            t_idx = 0
        x, y, z = nums[t_start], nums[t_start + 1], nums[t_start + 2]
        result = nums[t_start + 3]
        rel_err = nums[t_start + 4]
        i_idx = _center_index(bins_x, x)
        j_idx = _center_index(bins_y, y)
        k_idx = _center_index(bins_z, z)
        key = (e_idx, t_idx)
        frame = data.get(key)
        if frame is None:
            frame = np.zeros((ni, nj, nk), dtype=np.float64)
            data[key] = frame
        errframe = error.get(key)
        if errframe is None:
            errframe = np.zeros((ni, nj, nk), dtype=np.float64)
            error[key] = errframe
        frame[i_idx, j_idx, k_idx] = result
        errframe[i_idx, j_idx, k_idx] = rel_err
        if result < total_min:
            total_min = result
        if result > total_max:
            total_max = result

    if not data:
        raise ValueError("未解析到数据行（非有效 meshtal tally）")

    # 无时间分箱时 bins_time 为空（契约 §2.2）
    return MeshTally(
        number=num,
        particle=particle,
        geom="xyz",
        bins_x=[float(e) for e in bins_x],
        bins_y=[float(e) for e in bins_y],
        bins_z=[float(e) for e in bins_z],
        bins_energy=[float(e) for e in energy_edges],
        bins_time=[float(e) for e in time_edges],
        data=data,
        error=error,
        scalar_range=(total_min, total_max),
    )


def parse_meshtal(text: str) -> MeshtalFile:
    """解析 MESHTAL 文本 → MeshtalFile（pymcnp 优先 + 轻量兜底）。"""
    used_pymcnp = False
    try:
        from pymcnp.meshtal import Meshtal  # 惰性 import
        Meshtal.from_mcnp(text)
        used_pymcnp = True
    except Exception:
        used_pymcnp = False

    warnings = [] if used_pymcnp else [
        "pymcnp 解析失败，已使用轻量兜底解析（文件格式非标准 MCNP 或版本不兼容）"
    ]
    code, histories = _parse_global_header(text)

    tallies = []
    blocks = re.split(r'(?m)^\s*Mesh Tally Number\s+(\d+)\s*$', text)
    # blocks = [prefix, num, body, num, body, ...]
    idx = 1
    while idx + 1 < len(blocks):
        num = int(blocks[idx])
        body = blocks[idx + 1]
        tallies.append(_parse_tally_block(num, body))
        idx += 2

    if not tallies:
        raise ValueError(
            "不是有效的 MESHTAL 文件（未找到任何 Mesh Tally 段）"
        )

    return MeshtalFile(path="", mtime=0.0, code=code, histories=histories,
                       tallies=tallies, warnings=warnings)


def parse_meshtal_file(path: str) -> MeshtalFile:
    """读文件 + mtime + 转 parse_meshtal。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    mf = parse_meshtal(text)
    mf.path = path
    try:
        mf.mtime = os.path.getmtime(path)
    except OSError:
        mf.mtime = 0.0
    return mf
