"""重合判定纯分类（纯 stdlib，可单测；无 FreeCAD/vtk）。

对齐 2026-08-13 契约 geometry-check.md：
- 重叠判定 volume > max(vol_floor_abs, vol_floor_rel*min(vol_a,vol_b))；
- severity 按 volumeFraction = volume / min(vol_a,vol_b)：
  >=0.10 双方非真空=error、含真空=warning；0.01~0.10 warning/info；
  [min_floor,0.01) info；< min_floor 排除；
- method=="probe"（GQ/SQ 解析采样探针）→ suspected:true 并降级一级
  （error→warning，warning→info，info 保持）。
"""

from __future__ import annotations


DEFAULT_VOL_FLOOR_ABS = 1e-6
DEFAULT_VOL_FLOOR_REL = 1e-4


def _is_void(material) -> bool:
    return str(material or "0").strip().split()[0] == "0"


def _severity(frac: float, any_void: bool, suspected: bool) -> str:
    if frac >= 0.10:
        sev = "warning" if any_void else "error"
    elif frac >= 0.01:
        sev = "info" if any_void else "warning"
    else:
        sev = "info"
    if suspected and sev == "error":
        sev = "warning"
    elif suspected and sev == "warning":
        sev = "info"
    return sev


def classify_overlaps(results, cells_meta, *,
                      vol_floor_abs: float = DEFAULT_VOL_FLOOR_ABS,
                      vol_floor_rel: float = DEFAULT_VOL_FLOOR_REL) -> dict:
    """把布尔/探针结果分类为最终报告。

    results: [{a, b, volume, vol_a, vol_b, method}]，method ∈ boolean|probe。
    cells_meta: {num: {"material": str}}。
    返回 {"overlaps": [...], "excluded": [...]}；overlaps 元素含
    a/b/volume/volumeFraction/severity/method（probe 额外 suspected:true）。
    """
    overlaps = []
    excluded = []
    for r in results:
        a = int(r["a"])
        b = int(r["b"])
        volume = float(r.get("volume", 0.0))
        vol_a = float(r.get("vol_a", 0.0))
        vol_b = float(r.get("vol_b", 0.0))
        method = r.get("method", "boolean")
        min_vol = min(vol_a, vol_b)
        floor = max(vol_floor_abs, vol_floor_rel * max(min_vol, 0.0))
        if volume <= floor or min_vol <= 0:
            excluded.append({"a": a, "b": b, "volume": volume,
                             "volumeFraction": 0.0, "method": method})
            continue
        frac = volume / min_vol
        any_void = _is_void(cells_meta.get(a, {}).get("material")) or \
            _is_void(cells_meta.get(b, {}).get("material"))
        suspected = method == "probe"
        entry = {
            "a": a, "b": b, "volume": volume,
            "vol_a": vol_a, "vol_b": vol_b,
            "volumeFraction": frac,
            "severity": _severity(frac, any_void, suspected),
            "method": method,
        }
        if suspected:
            entry["suspected"] = True
        overlaps.append(entry)
    order = {"error": 0, "warning": 1, "info": 2}
    overlaps.sort(key=lambda e: (order.get(e["severity"], 3),
                                 -e["volumeFraction"], e["a"], e["b"]))
    return {"overlaps": overlaps, "excluded": excluded}


def cap_by_bbox_volume(candidates, max_ops: int = 300):
    """按 AABB 交叠体积降序截断候选对 → (top, truncated)。"""
    if not candidates:
        return [], False
    ordered = sorted(candidates, key=lambda c: -float(c.get("bbox_volume", 0.0)))
    if len(ordered) > max_ops:
        return ordered[:max_ops], True
    return ordered, False


__all__ = ["classify_overlaps", "cap_by_bbox_volume",
           "DEFAULT_VOL_FLOOR_ABS", "DEFAULT_VOL_FLOOR_REL"]
