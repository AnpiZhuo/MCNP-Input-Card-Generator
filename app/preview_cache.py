"""
preview-3d deck 指纹缓存 —— 同一 deck 跳过 FreeCAD 子进程重建。

深模块：对外只暴露 fingerprint/get/put/evict_dir/evict_lru 小接口，隐藏
规范化/哈希/目录拷贝生命周期/磁盘驱逐/构造 seam。纯 stdlib，无运行时依赖。

设计要点：
- 缓存存 STL 文件目录（磁盘）：`put` 把会话目录里的 STL **拷贝**进缓存自有目录
  （base_dir/<fp>/），因此关预览窗口（clear-stl）删除的是会话目录，缓存拷贝
  存活 → 同一 deck 第二次打开命中，KPI ≤1.0s 达成。
- 命中时不调用 FreeCAD：`get` 返回 {dir, cells, freecad}，`freecad` 检测路径
  一并复用；handler 命中路径只读 STL → base64。
- 悬挂防护双保险：`get` 内 `os.path.isdir` 校验（目录被删 → 视为 miss 并清理）
  + `evict_dir`（会话目录被 clear/覆盖时同步驱逐对应缓存项）。
- LRU 上限 3（构造参数可配）：`evict_lru` 驱逐最旧指纹并删除其缓存目录，控制磁盘。
"""

import hashlib
import json
import os
import shutil
import tempfile


class PreviewCache:
    """deck 指纹缓存：同输入跳过 FreeCAD 子进程。"""

    def __init__(self, base_dir=None, max_entries: int = 3, builder=None):
        """
        Args:
            base_dir: 缓存根目录（缓存自有 STL 拷贝存于此）。默认系统临时目录。
            max_entries: LRU 上限（指纹数）。默认 3。
            builder: 可选构建 seam，`get_or_build` 未命中时调用 builder(data)
                产出会话 dict 并 put。命中不调用（测试注入计数函数断言 0 次）。
        """
        self._base_dir = base_dir or tempfile.mkdtemp(prefix="mcnp_preview_cache_")
        self._max_entries = max_entries
        self._builder = builder
        self._index = {}   # fp -> {"dir", "cells", "freecad"}
        self._order = []   # fp 最近使用序，index 0 = 最旧

    # ── 指纹 ───────────────────────────────────────────────
    def fingerprint(self, surfaces: str, cells: list, tr_cards: str,
                    extra: dict | None = None) -> str:
        """canonical json (sort_keys) → sha256 hex。

        输入与 handler 收到的 preview-3d 请求一致（surfaces 文本、cells JSON
        列表、tr_cards 文本）。同一 deck 文本/结构 → 同指纹；任一字段变化 → 不同。
        extra（可选 dict）并入 canonical json —— 格阵 universe STL 缓存用它携带
        u/cellNum/pitch/height，防不同裁剪参数脏命中。extra 为 None 时行为与旧版
        完全一致（既有 preview-3d 指纹不变）。
        """
        payload = {"surfaces": surfaces, "cells": cells, "tr_cards": tr_cards}
        if extra is not None:
            payload["extra"] = extra
        canonical = json.dumps(
            payload, sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ── 缓存读写 ───────────────────────────────────────────
    def get(self, fp: str) -> dict | None:
        """命中且目录仍存在 → {"dir", "cells", "freecad"}；否则 None。

        目录已删（悬挂）→ 清理索引并返回 None（isdir 兜底 miss）。
        """
        entry = self._index.get(fp)
        if entry is None:
            return None
        if not os.path.isdir(entry.get("dir", "")):
            self._drop(fp)
            return None
        self._touch(fp)
        return entry

    def put(self, fp: str, session: dict) -> None:
        """把会话目录的 STL 拷贝进缓存自有目录后登记。

        session: {"dir": 会话目录, "cells": {num: {"material", "path"}},
                  "freecad": freecad_bin}。会话目录可能随后被 clear-stl 删除，
        缓存持有自己的拷贝，不受影响。
        """
        src_dir = session.get("dir")
        cells = session.get("cells") or {}
        if not src_dir or not os.path.isdir(src_dir):
            return  # 源目录无效，不缓存
        cache_dir = os.path.join(self._base_dir, fp)
        shutil.rmtree(cache_dir, ignore_errors=True)  # 同指纹重入 → 精确重建
        os.makedirs(cache_dir, exist_ok=True)
        cached_cells = {}
        for num, info in cells.items():
            src_path = info.get("path")
            if src_path and os.path.isfile(src_path):
                dst = os.path.join(cache_dir, f"cell_{num}.stl")
                try:
                    shutil.copy2(src_path, dst)
                except OSError:
                    continue
                cached_cells[num] = {
                    "material": info.get("material", "0"),
                    "path": dst,
                }
        if not cached_cells:
            shutil.rmtree(cache_dir, ignore_errors=True)
            return  # 无 STL 可缓存
        self._index[fp] = {
            "dir": cache_dir,
            "cells": cached_cells,
            "freecad": session.get("freecad"),
        }
        self._touch(fp)
        self.evict_lru(self._max_entries)

    def put_overlaps(self, fp: str, report: dict) -> None:
        """把重合检测报告写入缓存目录（同指纹，随目录驱逐自动清理）。"""
        entry = self._index.get(fp)
        if entry is None:
            return
        cache_dir = entry.get("dir", "")
        if not cache_dir or not os.path.isdir(cache_dir):
            return
        try:
            with open(os.path.join(cache_dir, "overlaps.json"),
                      "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False)
        except OSError:
            pass

    def get_overlaps(self, fp: str) -> dict | None:
        """读取同指纹缓存目录里的 overlaps.json；无则 None。"""
        entry = self._index.get(fp)
        if entry is None:
            return None
        path = os.path.join(entry.get("dir", ""), "overlaps.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def get_or_build(self, fp: str, data=None) -> dict:
        """命中返回缓存；未命中用构造 seam builder(data) 构建并缓存。

        命中不调用 builder（测试断言 0 次调用）。命中/未命中都返回缓存规范化形式
        （cells path 指向缓存自有拷贝），保证两路径返回结构一致。handler 走显式
        fingerprint/get/现状 else/put 流程，本方法供 builder seam 测试与可选惰性构建。
        """
        hit = self.get(fp)
        if hit is not None:
            return hit
        if self._builder is None:
            raise RuntimeError("PreviewCache: 未提供 builder 且缓存未命中")
        self.put(fp, self._builder(data))
        return self.get(fp)

    # ── 驱逐 ───────────────────────────────────────────────
    def evict_dir(self, d: str) -> None:
        """会话目录被清（clear-stl/覆盖预览）时同步驱逐指向它的缓存项，防悬挂。

        命中路径 _STL_SESSION 指向缓存目录时，clear-stl 会 rmtree 该目录——此处
        移除索引并删除缓存目录（_drop），调用方对已删目录的 rmtree 是无害空操作。
        """
        for fp in [fp for fp, e in self._index.items() if e.get("dir") == d]:
            self._drop(fp)

    def evict_lru(self, max_entries: int | None = None) -> None:
        """驱逐最旧指纹直到 ≤ max_entries（默认构造上限），并删除其缓存目录。"""
        cap = self._max_entries if max_entries is None else max_entries
        while len(self._order) > cap:
            self._drop(self._order[0])

    # ── 内部 ───────────────────────────────────────────────
    def _touch(self, fp: str) -> None:
        """把 fp 标记为最近使用（排到 LRU 序末尾）。"""
        if fp in self._order:
            self._order.remove(fp)
        self._order.append(fp)

    def _drop(self, fp: str) -> None:
        """移除 fp 的索引项并删除其缓存目录（若存在）。"""
        entry = self._index.pop(fp, None)
        if fp in self._order:
            self._order.remove(fp)
        if entry and os.path.isdir(entry.get("dir", "")):
            shutil.rmtree(entry["dir"], ignore_errors=True)
