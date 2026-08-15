"""MESHTAL 解析缓存（契约 meshtal-visualization.md §4.4）。

worker 侧稠密数组磁盘 pickle 缓存（path+mtime 指纹）。重复取不同 (energy,time)
帧时复用已解析稠密数组，免整文件重解析（大文件关键）。容量超 512MB 逐最旧。
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import tempfile

_MAX_BYTES = 512 * 1024 * 1024

# 解析元数据 manifest 格式版本：解析行为/响应字段变化时 +1，使旧版磁盘 manifest
# 失效重解析（防旧警告/旧元数据被缓存继续投放）。v1 = 无版本号字段的旧格式。
_MANIFEST_VERSION = 2


class MeshtalParseCache:
    """path+mtime 指纹 pickle 缓存（LRU 按磁盘量驱逐）。"""

    def __init__(self, directory: str | None = None, max_bytes: int = _MAX_BYTES):
        self._dir = directory or os.path.join(tempfile.gettempdir(), "mcnp_meshtal_cache")
        self._max_bytes = max_bytes
        os.makedirs(self._dir, exist_ok=True)

    def fingerprint(self, path: str, mtime: float) -> str:
        """sha256(path + mtime)，文件被覆盖/重跑自动失效。"""
        return hashlib.sha256(f"{path}|{mtime}".encode("utf-8")).hexdigest()

    def _entry_path(self, fp: str, tally_number: int) -> str:
        return os.path.join(self._dir, f"{fp}_{tally_number}.pkl")

    def _manifest_path(self, fp: str) -> str:
        return os.path.join(self._dir, f"{fp}.manifest.json")

    def get_manifest(self, fp: str) -> dict | None:
        """parse 元数据 manifest（JSON）——命中即免整文件重解析（契约 §4.4/§8）。

        版本不匹配（旧版 manifest）→ None（视为未命中，强制重解析）。
        返回的 dict 不含内部 `cache_version` 键。
        """
        p = self._manifest_path(fp)
        if not os.path.isfile(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None
        if data.pop("cache_version", None) != _MANIFEST_VERSION:
            return None
        return data

    def put_manifest(self, fp: str, data: dict) -> None:
        """parse 元数据 manifest 落盘（含全部 tally 元数据 + grid_bounds）。"""
        payload = dict(data)
        payload["cache_version"] = _MANIFEST_VERSION
        p = self._manifest_path(fp)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        try:
            os.replace(tmp, p)
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def get(self, fp: str, tally_number: int) -> dict | None:
        """返回 {"data":…, "error":…, "scalar_range":…, bins…} 或 None。"""
        p = self._entry_path(fp, tally_number)
        if not os.path.isfile(p):
            return None
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def put(self, fp: str, tally_number: int, entry: dict) -> None:
        """pickle 落盘，随后按容量驱逐最旧。"""
        p = self._entry_path(fp, tally_number)
        tmp = p + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(entry, f)
        try:
            os.replace(tmp, p)
        except OSError:
            os.remove(tmp)
        self.evict()

    def evict(self) -> None:
        """超容量逐最旧（按 mtime 升序）。"""
        entries = []
        total = 0
        try:
            names = os.listdir(self._dir)
        except OSError:
            return
        for name in names:
            p = os.path.join(self._dir, name)
            try:
                sz = os.path.getsize(p)
                entries.append((os.path.getmtime(p), p, sz))
                total += sz
            except OSError:
                continue
        entries.sort(key=lambda x: x[0])
        while total > self._max_bytes and entries:
            _mt, p, sz = entries.pop(0)
            try:
                os.remove(p)
                total -= sz
            except OSError:
                pass

    def _clear(self) -> None:
        """测试辅助：清空缓存目录。"""
        try:
            for name in os.listdir(self._dir):
                os.remove(os.path.join(self._dir, name))
        except OSError:
            pass
