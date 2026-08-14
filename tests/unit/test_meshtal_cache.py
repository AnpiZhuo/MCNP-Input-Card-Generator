"""MESHTAL 解析缓存测试 —— app/meshtal/meshtal_cache.py（契约 meshtal-visualization.md §4.4）。

测 fingerprint(path,mtime) 稳定/变化、get/put 命中、evict 按磁盘量、manifest get/put。
纯 stdlib，不 import gui.backend.api_server / FreeCAD。
"""
import pytest

from app.meshtal.meshtal_cache import MeshtalParseCache


def _cache(tmp_path, max_bytes=1 << 20) -> MeshtalParseCache:
    return MeshtalParseCache(directory=str(tmp_path), max_bytes=max_bytes)


# ── 1. fingerprint ─────────────────────────────────────────────
def test_fingerprint_stable_for_same_path_mtime(tmp_path):
    """同 path+mtime → 同指纹（sha256 hex）。"""
    c = _cache(tmp_path)
    fp1 = c.fingerprint("D:/x/meshtal", 1234.5)
    fp2 = c.fingerprint("D:/x/meshtal", 1234.5)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_changes_with_mtime(tmp_path):
    """mtime 变化 → 指纹变化（文件被覆盖/重跑自动失效）。"""
    c = _cache(tmp_path)
    assert c.fingerprint("D:/x/meshtal", 1.0) != c.fingerprint("D:/x/meshtal", 2.0)


def test_fingerprint_changes_with_path(tmp_path):
    """path 变化 → 指纹变化。"""
    c = _cache(tmp_path)
    assert c.fingerprint("D:/a/meshtal", 1.0) != c.fingerprint("D:/b/meshtal", 1.0)


# ── 2. get / put ───────────────────────────────────────────────
def test_get_missing_returns_none(tmp_path):
    """未缓存 → get 返回 None（非抛错）。"""
    c = _cache(tmp_path)
    assert c.get("abc", 4) is None


def test_put_get_roundtrip(tmp_path):
    """put 后 get 命中，内容一致（pickle 往返）。"""
    c = _cache(tmp_path)
    entry = {"data": [1.0, 2.0, 3.0], "scalar_range": (0.0, 3.0)}
    c.put("abc", 4, entry)
    assert c.get("abc", 4) == entry


def test_get_absent_tally_returns_none(tmp_path):
    """同 fp 但 tally_number 不同 → None。"""
    c = _cache(tmp_path)
    c.put("abc", 4, {"data": 1})
    assert c.get("abc", 5) is None


# ── 3. evict 按磁盘量（LRU 最旧）───────────────────────────────
def test_evict_removes_oldest_over_budget(tmp_path):
    """容量超限 → 逐最旧（fp0 被驱逐，近期至少一个存活）。"""
    c = _cache(tmp_path, max_bytes=1000)
    entry = {"data": [0] * 100, "i": 0}   # pickle ~450B/条
    for i in range(5):
        c.put(f"fp{i}", 4, dict(entry, i=i))
    assert c.get("fp0", 4) is None, "最旧条目未被驱逐"
    assert any(c.get(f"fp{i}", 4) is not None for i in (3, 4)), "近期条目不应被驱逐"


# ── 4. manifest（parse 元数据缓存，契约 §4.4）─────────────────
def test_manifest_put_get(tmp_path):
    """parse 元数据 manifest：put 后 get 命中（免整文件重解析）。"""
    c = _cache(tmp_path)
    assert c.get_manifest("fp9") is None
    data = {"grid_bounds": {"min": [0.0, 0.0, 0.0], "max": [2.0, 2.0, 1.0]},
            "tallies": [{"number": 1}]}
    c.put_manifest("fp9", data)
    assert c.get_manifest("fp9") == data


def test_manifest_changes_fingerprint_isolation(tmp_path):
    """不同 fp 的 manifest 互不串扰。"""
    c = _cache(tmp_path)
    c.put_manifest("fp1", {"tallies": [1]})
    assert c.get_manifest("fp2") is None
