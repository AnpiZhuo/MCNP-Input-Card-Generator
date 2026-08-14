"""MESHTAL 解析/纹理提取子进程 worker（契约 meshtal-visualization.md §4.5）。

协议：stdin JSON → stdout JSON（{"status":"ok", …} / {"status":"error","message":…}）。

- mode="parse"：读文件 → parse_meshtal_file → 只回传元数据 + grid_bounds +
  range + warnings（稠密数组落 cache）。
- mode="texture"：cache 命中取稠密数组 → build_frame → base64 标量帧；
  cache 未命中则整文件解析后取帧（并落 cache）。

模块顶**只 import stdlib**（numpy/pymcnp 惰性按需），AST 断言防模块顶重 import。
"""
import base64
import json
import os
import sys
import traceback

# 将 app/ 与项目根加入 sys.path（子进程独立，需自带路径引导）
_HERE = os.path.dirname(os.path.abspath(__file__))      # app/meshtal
_APP = os.path.dirname(_HERE)                            # app
_ROOT = os.path.dirname(_APP)                            # 项目根
for _p in (_APP, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _cache_entry_from_tally(t) -> dict:
    """MeshTally → 可 pickle 缓存条目（含 bins，供 cache 命中重建 Frame）。"""
    return {
        "number": t.number,
        "particle": t.particle,
        "geom": t.geom,
        "bins_x": t.bins_x,
        "bins_y": t.bins_y,
        "bins_z": t.bins_z,
        "bins_energy": t.bins_energy,
        "bins_time": t.bins_time,
        "data": t.data,
        "error": t.error,
        "scalar_range": t.scalar_range,
    }


def _tally_from_cache(entry: dict):
    """缓存条目 → MeshTally（供 build_frame）。"""
    from meshtal.meshtal_parser import MeshTally  # noqa: F401  （app 在 sys.path）
    t = MeshTally(
        number=entry["number"],
        particle=entry["particle"],
        geom=entry["geom"],
        bins_x=entry["bins_x"],
        bins_y=entry["bins_y"],
        bins_z=entry["bins_z"],
        bins_energy=entry["bins_energy"],
        bins_time=entry["bins_time"],
        data=entry["data"],
        error=entry["error"],
        scalar_range=tuple(entry["scalar_range"]),
    )
    return t


def _mode_parse(path: str) -> dict:
    """解析 meshtal → 元数据。契约 §4.4「parse 元数据也缓存」：
    先查 manifest 缓存命中即重建返回（免整文件重解析，缓存命中 <1s）；
    未命中才解析 + 逐 tally 落稠密数组 cache + 落 manifest。"""
    from meshtal.meshtal_parser import parse_meshtal_file
    from meshtal.meshtal_cache import MeshtalParseCache

    cache = MeshtalParseCache()
    mtime = os.path.getmtime(path)
    fp = cache.fingerprint(path, mtime)

    cached = cache.get_manifest(fp)
    if cached is not None:
        return cached

    mf = parse_meshtal_file(path)
    grid_bounds = None
    tallies = []
    for t in mf.tallies:
        grid_bounds = {
            "min": [float(t.bins_x[0]), float(t.bins_y[0]), float(t.bins_z[0])],
            "max": [float(t.bins_x[-1]), float(t.bins_y[-1]), float(t.bins_z[-1])],
        }
        ni, nj, nk = len(t.bins_x) - 1, len(t.bins_y) - 1, len(t.bins_z) - 1
        n_voxels = ni * nj * nk
        cache.put(fp, t.number, _cache_entry_from_tally(t))
        tallies.append({
            "number": t.number,
            "particle": t.particle,
            "geom": t.geom,
            "unsupportedGeom": t.geom != "xyz",
            "dims": {
                "ni": ni, "nj": nj, "nk": nk,
                "energyBins": max(1, len(t.bins_energy) - 1),
                "timeBins": max(0, len(t.bins_time) - 1),
                "nVoxels": n_voxels,
            },
            "binEdges": {
                "x": t.bins_x, "y": t.bins_y, "z": t.bins_z,
                "energy": t.bins_energy, "time": t.bins_time,
            },
            "range": {
                "min": float(t.scalar_range[0]),
                "max": float(t.scalar_range[1]),
                "count": n_voxels,
            },
        })
    result = {
        "status": "ok",
        "code": mf.code,
        "version": "6",
        "histories": float(mf.histories),
        "grid_bounds": grid_bounds,
        "tallies": tallies,
        "warnings": mf.warnings,
    }
    cache.put_manifest(fp, result)
    return result


def _mode_texture(payload: dict) -> dict:
    from meshtal.meshtal_parser import MeshtalFile, parse_meshtal_file
    from meshtal.meshtal_cache import MeshtalParseCache
    from meshtal.volume_builder import build_frame
    import numpy as np  # 惰性

    path = payload["path"]
    tally_number = int(payload.get("tallyNumber", 0))
    energy_bin = int(payload.get("energyBin", 0))
    time_bin = int(payload.get("timeBin", 0))
    resolution = int(payload.get("resolution", 128))
    budget_bytes = int(payload.get("budgetBytes", 256 * 1024 * 1024))

    cache = MeshtalParseCache()
    mtime = os.path.getmtime(path)
    fp = cache.fingerprint(path, mtime)

    entry = cache.get(fp, tally_number)
    if entry is not None:
        tally = _tally_from_cache(entry)
        mf = MeshtalFile(path="", mtime=0.0, code="mcnp", histories=0.0,
                         tallies=[tally])
    else:
        mf = parse_meshtal_file(path)
        for t in mf.tallies:
            cache.put(fp, t.number, _cache_entry_from_tally(t))
        tally = next((t for t in mf.tallies if t.number == tally_number), None)
        if tally is None:
            raise KeyError(f"tally number {tally_number} 不存在")

    frame = build_frame(mf, tally_number, energy_bin, time_bin,
                        resolution, budget_bytes=budget_bytes)
    scalar_bytes = frame.scalar.tobytes()
    n_voxels = int(np.prod(frame.resolution))
    return {
        "status": "ok",
        "frame": {
            "resolution": [int(x) for x in frame.resolution],
            "worldBox": frame.world_box,
            "binIndices": {"energy": energy_bin, "time": time_bin},
            "scalarRange": {"min": float(frame.scalar_range[0]),
                            "max": float(frame.scalar_range[1])},
            "dataBase64": base64.b64encode(scalar_bytes).decode("ascii"),
            "bytes": len(scalar_bytes),
            "nVoxels": n_voxels,
            "downsampled": frame.downsampled,
            "avgFactor": [int(x) for x in frame.avg_factor],
            "particle": tally.particle,
            "tallyNumber": tally_number,
            "scalarMin": float(frame.scalar_range[0]),
            "scalarMax": float(frame.scalar_range[1]),
        },
    }


def _run(payload: dict) -> dict:
    """分派 parse/texture；任何异常 → {"status":"error","message":…}（不裸抛）。

    try/except 在 _run 层（不在 main），保证直接调用与 stdin 子进程协议都拿到
    error 信封（照 _freecad_csg_worker 模式）。"""
    try:
        mode = payload.get("mode")
        path = payload.get("path", "")
        if mode == "parse":
            return _mode_parse(path)
        if mode == "texture":
            return _mode_texture(payload)
        return {"status": "error", "message": f"未知 mode: {mode}"}
    except Exception:
        return {"status": "error", "message": traceback.format_exc()}


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stdout.write(json.dumps({"status": "error", "message": f"stdin JSON 解析失败: {e}"}))
        sys.stdout.flush()
        return
    result = _run(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
