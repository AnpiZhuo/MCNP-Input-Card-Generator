"""AABB 空间索引：候选栅元对生成（纯 stdlib，可单测）。

避免 O(n²) 两两 AABB 检测：均匀网格分桶——把每个栅元的 AABB 覆盖的
网格单元登记进桶，同一桶内的栅元才互为候选对；典型几何候选对
O(n·k)。同时提供「新增栅元 vs 已有栅元」单查询（O(n) 一次扫描）。
"""

from __future__ import annotations


def aabb_overlap_volume(lo_a, hi_a, lo_b, hi_b) -> float:
    """两 AABB 交叠体积；不相交返回 0。"""
    w = min(hi_a[0], hi_b[0]) - max(lo_a[0], lo_b[0])
    h = min(hi_a[1], hi_b[1]) - max(lo_a[1], lo_b[1])
    d = min(hi_a[2], hi_b[2]) - max(lo_a[2], lo_b[2])
    if w <= 0 or h <= 0 or d <= 0:
        return 0.0
    return w * h * d


def _buckets(cells: dict, cell_size: float):
    """cells: {num: (lo3, hi3)} → {gcell: [num]}。"""
    buckets: dict = {}
    for num, (lo, hi) in cells.items():
        x0 = int(lo[0] // cell_size)
        x1 = int(hi[0] // cell_size)
        y0 = int(lo[1] // cell_size)
        y1 = int(hi[1] // cell_size)
        z0 = int(lo[2] // cell_size)
        z1 = int(hi[2] // cell_size)
        for ix in range(x0, x1 + 1):
            for iy in range(y0, y1 + 1):
                for iz in range(z0, z1 + 1):
                    key = (ix, iy, iz)
                    buckets.setdefault(key, []).append(num)
    return buckets


def _cell_size_for(cells: dict, fallback: float = 10.0) -> float:
    """网格单元尺寸：按 AABB 尺寸中位数，防病态（全盒/点盒）。"""
    sizes = []
    for lo, hi in cells.values():
        s = max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
        if 0 < s < 1e12:
            sizes.append(s)
    if not sizes:
        return fallback
    sizes.sort()
    return sizes[len(sizes) // 2]


def grid_candidates(cells: dict, cell_size: float | None = None) -> list:
    """生成 AABB 相交候选对（去重、含 bbox_volume）。

    cells: {num: (lo3, hi3)}；返回 [{a, b, bbox_volume}]。
    """
    if len(cells) < 2:
        return []
    size = cell_size or _cell_size_for(cells)
    if size <= 0:
        return []
    buckets = _buckets(cells, size)
    seen = set()
    pairs = []
    for nums in buckets.values():
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                a, b = nums[i], nums[j]
                key = (a, b) if a < b else (b, a)
                if key in seen:
                    continue
                seen.add(key)
                lo_a, hi_a = cells[key[0]]
                lo_b, hi_b = cells[key[1]]
                v = aabb_overlap_volume(lo_a, hi_a, lo_b, hi_b)
                if v > 0:
                    pairs.append({"a": key[0], "b": key[1], "bbox_volume": v})
    return pairs


def query_new_vs_existing(new_lo, new_hi, cells: dict) -> list:
    """新增栅元 AABB vs 已有栅元：O(n) 单查询 → [{num, bbox_volume}]。"""
    out = []
    for num, (lo, hi) in cells.items():
        v = aabb_overlap_volume(new_lo, new_hi, lo, hi)
        if v > 0:
            out.append({"num": num, "bbox_volume": v})
    out.sort(key=lambda c: -float(c["bbox_volume"]))
    return out


__all__ = ["aabb_overlap_volume", "grid_candidates", "query_new_vs_existing"]
