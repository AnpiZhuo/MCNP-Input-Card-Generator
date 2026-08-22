"""GQ/SQ 栅元对解析采样探针（纯 numpy，复用 voxel_csg 求值，含 TR）。

精确布尔对体素/二次曲面不可靠，改为在两栅元 AABB 交叠盒内均匀采样，
逐点解析判定「是否同时在两栅元内」；用蒙特卡洛估计体积占比：
    V_A≈nA/N·V_box，V_B≈nB/N·V_box，V_AB≈nAB/N·V_box
    volumeFraction = V_AB / min(V_A, V_B) ≈ nAB / min(nA, nB)
逐点判定是解析精确的，只有采样密度是近似——结果标 suspected（疑似）。
"""

from __future__ import annotations

import numpy as np

try:
    from voxel_csg import surface_fn, eval_cell_field, _surface_tr
except ImportError:  # 测试/直接 import app 包时在 app/ 下
    from app.voxel_csg import surface_fn, eval_cell_field, _surface_tr


def _fns_for(nums, surfaces_by_num, tr_cards) -> dict:
    fns = {}
    for num in nums:
        s = surfaces_by_num.get(num)
        if s is None:
            continue
        fns[num] = surface_fn(s["type"], s["params"], _surface_tr(s, tr_cards))
    return fns


def _intersection_box(lo_a, hi_a, lo_b, hi_b):
    lo = [max(lo_a[i], lo_b[i]) for i in range(3)]
    hi = [min(hi_a[i], hi_b[i]) for i in range(3)]
    if any(hi[i] <= lo[i] for i in range(3)):
        return None
    return lo, hi


def sample_overlap(ast_a, ast_b, surfaces_by_num, tr_cards,
                   bounds_a, bounds_b, res: int = 32) -> dict:
    """对 (A,B) 做解析采样探针 → 结果 dict（method="probe"）。

    返回 {a, b, volume, vol_a, vol_b, volumeFraction, method, samples,
    hits, low_confidence}；box 无交叠返回 None。
    """
    box = _intersection_box(bounds_a[0], bounds_a[1], bounds_b[0], bounds_b[1])
    if box is None:
        return None
    lo, hi = box
    nums = set()

    def collect(node):
        if node[0] == "surf":
            nums.add(node[1])
        else:
            for child in node[1:]:
                if isinstance(child, list):
                    collect(child)

    collect(ast_a)
    collect(ast_b)
    fns = _fns_for(nums, surfaces_by_num, tr_cards)
    if not fns:
        return None

    xs = np.linspace(lo[0], hi[0], res)
    ys = np.linspace(lo[1], hi[1], res)
    zs = np.linspace(lo[2], hi[2], res)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    box_vol = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])
    if box_vol <= 0:
        return None
    n_total = X.size
    try:
        in_a = eval_cell_field(ast_a, fns, X, Y, Z)
        in_b = eval_cell_field(ast_b, fns, X, Y, Z)
    except Exception:
        return None
    n_a = int(in_a.sum())
    n_b = int(in_b.sum())
    n_ab = int((in_a & in_b).sum())
    vol_a = n_a / n_total * box_vol
    vol_b = n_b / n_total * box_vol
    vol_ab = n_ab / n_total * box_vol
    min_n = min(n_a, n_b)
    low_conf = min_n < 8
    frac = (n_ab / min_n) if min_n > 0 else 0.0
    return {
        "a": 0, "b": 0,  # 由调用方回填
        "volume": vol_ab,
        "vol_a": vol_a,
        "vol_b": vol_b,
        "volumeFraction": frac,
        "method": "probe",
        "samples": n_total,
        "hits": n_ab,
        "low_confidence": low_conf,
    }


__all__ = ["sample_overlap"]
