"""§3.3 preview_cache 深模块测试 —— 纯 stdlib，不 import gui.backend/FreeCAD。

覆盖：fingerprint 稳定、put/get 命中、LRU 驱逐、evict_dir 联动、命中跳过 builder seam。
缓存采用"缓存自有拷贝"设计：put 把会话 STL 拷进缓存目录，源会话目录被 clear 后
缓存拷贝仍存活（同一 deck 第二次打开命中，KPI ≤1.0s）。
"""
import os
import shutil
from pathlib import Path

from app.preview_cache import PreviewCache


def _src_dir(tmp_path, cells=1, prefix="src") -> Path:
    """建一个含 cell_1.stl..cell_N.stl 的源会话目录。"""
    d = tmp_path / prefix
    d.mkdir(exist_ok=True)
    for n in range(1, cells + 1):
        (d / f"cell_{n}.stl").write_text(f"stl-{n}")
    return d


def _session(d: Path, cells=None) -> dict:
    if cells is None:
        cells = {n: {"material": "1", "path": str(d / f"cell_{n}.stl")}
                 for n in range(1, len(list(d.glob("cell_*.stl"))) + 1)}
    return {"dir": str(d), "cells": cells, "freecad": "/opt/freecad"}


# ── fingerprint ─────────────────────────────────────────────
def test_fingerprint_stable():
    """同输入同指纹；改一曲面/一栅元/一 TR 指纹不同；dict 键序无关。"""
    cache = PreviewCache()
    s = "px 0\npy 0"
    cells = [{"number": 1, "material": "1", "surface_expr": "-1 2"}]
    tr = "TR1 1 0 0 0 1 0 0 0 1"
    a = cache.fingerprint(s, cells, tr)
    b = cache.fingerprint(s, cells, tr)
    assert a == b

    c = cache.fingerprint("px 1\npy 0", cells, tr)                      # 改一曲面
    d = cache.fingerprint(s, [{"number": 2, "material": "1", "surface_expr": "-1 2"}], tr)  # 改一栅元
    e = cache.fingerprint(s, cells, "TR1 0 0 0 0 1 0 0 0 1")            # 改一 TR
    assert len({a, c, d, e}) == 4, "任一输入字段变化 → 指纹必须不同"

    # canonical sort_keys：dict 键序无关
    f = cache.fingerprint(s, [{"b": 1, "a": 2}], tr)
    g = cache.fingerprint(s, [{"a": 2, "b": 1}], tr)
    assert f == g


# ── put/get 命中 ────────────────────────────────────────────
def test_put_get_hit(tmp_path):
    """put 后 get 命中同 dir/cells/freecad；命中目录是缓存自有拷贝。"""
    cache = PreviewCache()
    src = _src_dir(tmp_path, cells=2)
    cells = {
        1: {"material": "1", "path": str(src / "cell_1.stl")},
        2: {"material": "0", "path": str(src / "cell_2.stl")},
    }
    cache.put("fp", {"dir": str(src), "cells": cells, "freecad": "/opt/freecad"})
    hit = cache.get("fp")
    assert hit is not None
    assert hit["dir"] == os.path.join(cache._base_dir, "fp")
    assert hit["cells"][1]["path"].endswith("cell_1.stl")
    assert hit["cells"][2]["path"].endswith("cell_2.stl")
    assert hit["freecad"] == "/opt/freecad"
    assert (Path(hit["dir"]) / "cell_1.stl").is_file()

    # 源会话目录被删（clear-stl）不影响缓存命中 —— 拷贝设计
    shutil.rmtree(src)
    assert cache.get("fp") is not None


def test_get_unknown_fp_returns_none(tmp_path):
    cache = PreviewCache()
    assert cache.get("missing") is None


# ── LRU 驱逐 ────────────────────────────────────────────────
def test_evict_lru(tmp_path):
    """超 3 指纹删最旧（LRU）；删除的缓存目录一并回收。"""
    cache = PreviewCache(max_entries=3)
    for i in range(4):
        src = _src_dir(tmp_path, cells=1, prefix=f"src{i}")
        cache.put(f"fp{i}", _session(src))
    assert cache.get("fp0") is None, "超上限后最旧 fp0 应被驱逐"
    for i in (1, 2, 3):
        assert cache.get(f"fp{i}") is not None, f"fp{i} 应在缓存内"


def test_lru_touch_on_hit(tmp_path):
    """命中的指纹移到最近使用：被驱逐的是最旧的 fp0 而非命中过的 fp1。"""
    cache = PreviewCache(max_entries=2)
    for i in range(3):
        src = _src_dir(tmp_path, cells=1, prefix=f"src{i}")
        cache.put(f"fp{i}", _session(src))
    cache.get("fp1")  # fp1 移到最近使用
    cache.put("fp3", _session(_src_dir(tmp_path, prefix="src3")))  # 触发驱逐
    assert cache.get("fp1") is not None, "命中过的 fp1 不应被驱逐"
    assert cache.get("fp0") is None, "最旧 fp0 应被驱逐"


# ── evict_dir 联动 ──────────────────────────────────────────
def test_evict_dir(tmp_path):
    """clear-stl 清掉缓存目录（命中路径 _STL_SESSION 指向缓存目录）→ 驱逐对应项。"""
    cache = PreviewCache()
    src = _src_dir(tmp_path)
    cache.put("fp1", _session(src))
    hit = cache.get("fp1")
    assert hit is not None
    cache.evict_dir(hit["dir"])
    assert cache.get("fp1") is None, "evict_dir 后 get 应返回 None"
    assert not Path(hit["dir"]).exists(), "缓存目录应被删除"


def test_evict_dir_other_entries_untouched(tmp_path):
    """evict_dir 只驱逐指向给定目录的项，其它指纹不受影响。"""
    cache = PreviewCache()
    src_a = _src_dir(tmp_path, prefix="srca")
    src_b = _src_dir(tmp_path, prefix="srcb")
    cache.put("fp_a", _session(src_a))
    cache.put("fp_b", _session(src_b))
    cache.evict_dir(str(src_a))  # 源会话目录（未命中路径）不匹配缓存拷贝目录
    assert cache.get("fp_a") is not None, "evict_dir(源目录) 不应误伤缓存拷贝"
    assert cache.get("fp_b") is not None


# ── builder seam（命中跳过构建）──────────────────────────────
def test_hit_skips_builder(tmp_path):
    """命中不调用注入的 builder 依赖；未命中才调用一次。"""
    calls = []

    def builder(data):
        calls.append(data)
        d = _src_dir(tmp_path, prefix="built")
        return _session(d)

    cache = PreviewCache(builder=builder)
    src = _src_dir(tmp_path, prefix="pre")
    cache.put("fp", _session(src))

    hit = cache.get_or_build("fp", {"surfaces": "px 0"})
    assert calls == [], f"命中不应当调用 builder，实际调用 {len(calls)} 次"
    assert hit["freecad"] == "/opt/freecad"

    miss = cache.get_or_build("fp2", {"surfaces": "px 1"})
    assert len(calls) == 1, "未命中应恰好调用 builder 一次"
    assert miss["dir"] == os.path.join(cache._base_dir, "fp2")


# ── 跨进程磁盘恢复（用户约定：可复用内容存持久目录，重启后命中）──
def test_cross_process_disk_recovery(tmp_path):
    """模拟进程重启：全新实例（内存 _index 为空、相同 base_dir）仍能从磁盘恢复命中。

    preview_cache 把 cells/freecad 写到 meta.json；新实例 get 内存 miss 时读盘恢复，
    同一 deck 无需再调 FreeCAD/builder ——「只算一次、往后复用」。
    """
    base = tmp_path / "mem_cache"
    src = _src_dir(tmp_path, cells=2)
    cells = {
        1: {"material": "1", "path": str(src / "cell_1.stl")},
        2: {"material": "0", "path": str(src / "cell_2.stl")},
    }
    cache_a = PreviewCache(base_dir=str(base))
    cache_a.put("fp", {"dir": str(src), "cells": cells, "freecad": "/opt/freecad"})
    # 源会话目录被清（clear-stl）不影响缓存拷贝
    shutil.rmtree(src)
    assert cache_a.get("fp") is not None
    assert (Path(base) / "fp" / "meta.json").is_file()

    # 模拟进程重启：全新实例、空 _index、相同 base_dir → 应从磁盘恢复命中
    cache_b = PreviewCache(base_dir=str(base))
    hit = cache_b.get("fp")
    assert hit is not None, "跨进程后应从磁盘 meta.json 恢复命中"
    assert hit["dir"] == str(base / "fp")
    assert hit["cells"][1]["material"] == "1"
    assert hit["cells"][1]["path"].endswith("cell_1.stl")
    assert hit["freecad"] == "/opt/freecad"
    assert (Path(hit["dir"]) / "cell_1.stl").is_file()
    assert (Path(hit["dir"]) / "cell_2.stl").is_file()


def test_cross_process_get_missing_fp_returns_none(tmp_path):
    """跨进程 & 磁盘没有该指纹 → 返回 None（不误命中）。"""
    cache = PreviewCache(base_dir=str(tmp_path / "mem_cache"))
    assert cache.get("missing") is None


def test_cross_process_corrupt_meta_returns_none(tmp_path):
    """meta.json 损坏/无内容 → 视为 miss，不返回脏数据。"""
    base = tmp_path / "mem_cache"
    cache = PreviewCache(base_dir=str(base))
    fp_dir = base / "fp"
    fp_dir.mkdir(parents=True)
    (fp_dir / "meta.json").write_text("{not json", encoding="utf-8")
    assert cache.get("fp") is None
