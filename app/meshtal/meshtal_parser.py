"""MESHTAL 文件解析（契约 meshtal-visualization.md §2.2 / §3.4）。

策略：pymcnp.meshtal 包并不导出 `Meshtal` 类（`from pymcnp.meshtal import
Meshtal` 恒 ImportError），pymcnp 校验路径实际从不生效，解析始终走本轻量
解析器；成功解析 warnings 恒为空，真正失败抛异常（worker 转 error 信封）。

支持两种 MCNP 数据布局（同一稠密数组产出）：
  1. **col**（out=col/colsc/cf，默认）：每体素一行 `[Energy] [Time] X Y Z Result RelError`。
     列布局由数据段列头按列名识别，兼容 Energy/Time 列的有无（含单能量 bin 但
     MCNP 仍打印 Energy 列的真实输出）。
  2. **二维矩阵**（out=ij/ik/jk）：`Energy Bin:`/`Time Bin:` 帧标签 + `<C> bin:`
     固定轴 + `Tally Results: <A> (across) by <B> (down)` + 列头 + 数据行。
     "Total Time/Energy Bin" 聚合段跳过（防重复计数）。

x/y/z 栅元中心 → 最近邻 bin 索引；col 的 energy/time 列值（bin 上边界）→
bisect 位置 - 1；矩阵的 bin 标签（bin 下边界）→ bisect 位置。
文件头 code 仅在出现 `mcnp version ...` 横幅时取横幅首词，否则恒为 "mcnp"
（多数 `.msht` 文件无横幅、首行即问题标题）。
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
    """从文件头提取 code + histories。

    真实 MCNP 输出两种文件头：① 带 `mcnp version 6 ld=...` 横幅（`.m`/部分
    `.msht`）；② 无横幅、首行即问题标题（多数 `.msht`）。code 仅在横幅明确给
    出时才取首词，否则默认 "mcnp"（防把标题首词当模拟代码）。
    """
    code = "mcnp"
    m = re.match(r'^\s*(\w+)\s+version\b', text)
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
    """energy/time 边界标签值 → bin 索引（bisect 位置 - 1）。

    col 布局打印的是 bin 的**上边界**（如能量 1.000E+36 对应 bin [1e-3, 1e36]），
    以"边界点"落入前一个 bin。
    """
    pos = bisect.bisect_left(edges, value)
    return max(0, min(len(edges) - 2, pos - 1))


def _matrix_axis_index(edges: list, lo_value: float) -> int:
    """矩阵布局 bin 标签（**下边界**）→ bin 索引。

    矩阵布局的 `Energy Bin: <lo> - <hi>` / `X bin: <lo> - <hi>` 打印的是 bin
    的**下边界**，直接 bisect_left 即得 bin 序号（不做 -1）。
    """
    if not edges:
        return 0
    pos = bisect.bisect_left(edges, lo_value)
    return max(0, min(len(edges) - 2, pos))


def _get_frames(data, error, key, ni, nj, nk):
    """按 (e,t) 键取稠密数组对，缺则新建全零帧（col/矩阵两布局共用）。"""
    frame = data.get(key)
    if frame is None:
        frame = np.zeros((ni, nj, nk), dtype=np.float64)
        data[key] = frame
    errframe = error.get(key)
    if errframe is None:
        errframe = np.zeros((ni, nj, nk), dtype=np.float64)
        error[key] = errframe
    return frame, errframe


def _parse_col_data(lines, bins_x, bins_y, bins_z,
                    energy_edges, time_edges, ni, nj, nk):
    """col 布局数据段（out=col/colsc/cf，每体素一行）→ (data, error, scalar_range)。

    列布局由数据段列头（含 `Result` / `Rel Error` 的行）按列名识别，兼容
    Energy/Time 列的有无——含单能量 bin 但 MCNP 仍打印 Energy 列的真实输出
    （valid_38 无 Energy 列、valid_39 只有 Time 列、valid_40 双列均可）。
    `Total` 汇总行因含非数值 token 被 float 转换自然跳过。
    """
    data = {}
    error = {}
    total_min = float("inf")
    total_max = float("-inf")

    cols = None
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        toks = s.split()
        if cols is None:
            if "Result" in toks and "Rel" in toks and "Error" in toks:
                cols = {t: i for i, t in enumerate(toks)}
                continue
            continue
        if len(toks) < 5:
            continue
        try:
            nums = [float(t) for t in toks]
        except ValueError:
            continue
        x, y, z = nums[cols["X"]], nums[cols["Y"]], nums[cols["Z"]]
        result = nums[cols["Result"]]
        rel_err = nums[cols["Rel"]]
        e_idx = _bin_index(energy_edges, nums[cols["Energy"]]) if "Energy" in cols else 0
        t_idx = _bin_index(time_edges, nums[cols["Time"]]) if "Time" in cols else 0
        i_idx = _center_index(bins_x, x)
        j_idx = _center_index(bins_y, y)
        k_idx = _center_index(bins_z, z)
        key = (e_idx, t_idx)
        frame, errframe = _get_frames(data, error, key, ni, nj, nk)
        frame[i_idx, j_idx, k_idx] = result
        errframe[i_idx, j_idx, k_idx] = rel_err
        if result < total_min:
            total_min = result
        if result > total_max:
            total_max = result
    return data, error, (total_min, total_max)


def _parse_matrix_data(lines, bins_x, bins_y, bins_z,
                       energy_edges, time_edges, ni, nj, nk):
    """二维矩阵布局数据段（out=ij/ik/jk）→ (data, error, scalar_range)。

    MCNP 矩阵打印结构（MCNP6.1 实跑实测）：
      Energy Bin: <lo> - <hi> MeV          # 能量帧标签（单能量也可能有）
      Time Bin:  <lo> - <hi> shakes        # 时间帧标签（可选）
      X/Y/Z bin: <lo> - <hi>               # 固定轴 bin（across/down 之外的轴）
      Tally Results:  <A> (across) by <B> (down)
         <A中心1> <A中心2> ...             # 列头（恰 n_A 个 token，跳过）
         <B中心> <值1> <值2> ...           # 数据行（n_A+1 个 token）
      Relative Errors                      # 相对误差矩阵（同布局）
    "Total Time Bin" / "Total Energy Bin" 聚合段整体跳过（防重复计数）。
    列位置 == across bin 序号（MCNP 按 across 轴升序打印列）。
    """
    axes = {"X": (bins_x, ni), "Y": (bins_y, nj), "Z": (bins_z, nk)}
    data = {}
    error = {}
    total_min = float("inf")
    total_max = float("-inf")

    energy_idx = 0
    time_idx = 0
    c_idx = 0
    across = down = None
    mode = None          # "result" | "error"
    n_across = 0
    skip_energy = False  # 处于 Total Energy Bin 聚合段
    skip_time = False    # 处于 Total Time Bin 聚合段

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m = re.match(r'^Energy Bin:\s*([\d.Ee+\-]+)\s*-\s*([\d.Ee+\-]+)', s)
        if m:
            energy_idx = _matrix_axis_index(energy_edges, float(m.group(1)))
            skip_energy = skip_time = False
            mode = None
            continue
        m = re.match(r'^Time Bin:\s*([\d.Ee+\-]+)\s*-\s*([\d.Ee+\-]+)', s)
        if m:
            time_idx = _matrix_axis_index(time_edges, float(m.group(1)))
            skip_time = False
            mode = None
            continue
        if s.startswith("Total Energy Bin"):
            # Total Energy Bin 段内仍打印 Time Bin 子块（跨能量聚合），须整体跳过
            skip_energy = skip_time = True
            mode = None
            continue
        if s.startswith("Total Time Bin"):
            skip_time = True
            mode = None
            continue
        m = re.match(r'^([XYZ])\s+bin:\s*([\d.Ee+\-]+)\s*-\s*([\d.Ee+\-]+)', s)
        if m:
            bins_c, _n = axes[m.group(1)]
            c_idx = _matrix_axis_index(bins_c, float(m.group(2)))
            continue
        m = re.match(r'^Tally Results:\s*([XYZ])\s+\(across\) by\s*([XYZ])\s+\(down\)', s)
        if m:
            across, down = m.group(1), m.group(2)
            bins_a, _n = axes[across]
            n_across = len(bins_a) - 1
            mode = "result"
            continue
        if s.startswith("Relative Errors"):
            mode = "error"
            continue
        if skip_energy or skip_time:
            continue
        if across is None or down is None or mode is None:
            continue
        toks = s.split()
        if len(toks) == n_across:
            continue          # 列头（across 中心行）
        if len(toks) != n_across + 1:
            continue
        try:
            nums = [float(t) for t in toks]
        except ValueError:
            continue
        bins_down, _n = axes[down]
        d_idx = _center_index(bins_down, nums[0])
        key = (energy_idx, time_idx)
        frame, errframe = _get_frames(data, error, key, ni, nj, nk)
        for col_i in range(n_across):
            val = nums[1 + col_i]
            # across 列号 == across bin 序号；down 用其中心映射；第三轴保持固定轴 c_idx
            idx = {"X": c_idx, "Y": c_idx, "Z": c_idx}
            idx[across] = col_i
            idx[down] = d_idx
            i_idx, j_idx, k_idx = idx["X"], idx["Y"], idx["Z"]
            if mode == "result":
                frame[i_idx, j_idx, k_idx] = val
                if val < total_min:
                    total_min = val
                if val > total_max:
                    total_max = val
            else:
                errframe[i_idx, j_idx, k_idx] = val
    return data, error, (total_min, total_max)


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
    ni, nj, nk = len(bins_x) - 1, len(bins_y) - 1, len(bins_z) - 1

    # 判别数据布局：col（每体素一行） vs 二维矩阵（out=ij/ik/jk）。
    # 矩阵签名：`X bin:` / `Energy Bin:` / `Tally Results:`（col 只有 `X direction:` 与列头）。
    is_matrix = any(
        re.match(r'^\s*(?:[XYZ]\s+bin:|Energy Bin:|Time Bin:|Tally Results:)', ln)
        for ln in lines
    )
    if is_matrix:
        data, error, (total_min, total_max) = _parse_matrix_data(
            lines, bins_x, bins_y, bins_z, energy_edges, time_edges, ni, nj, nk
        )
    else:
        data, error, (total_min, total_max) = _parse_col_data(
            lines, bins_x, bins_y, bins_z, energy_edges, time_edges, ni, nj, nk
        )

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
    """解析 MESHTAL 文本 → MeshtalFile（轻量解析器）。

    注：pymcnp.meshtal 包不导出 `Meshtal` 类（`from pymcnp.meshtal import
    Meshtal` 恒 ImportError），pymcnp 校验路径实际从不生效，解析始终走本
    轻量解析器。成功解析不 emit 误导性警告（warnings 为空）；真正失败抛
    异常，由调用方/worker 转 error 信封。
    """
    warnings: list = []
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
