"""MESHTAL 子进程 worker 测试 —— app/meshtal/_meshtal_worker.py（契约 meshtal-visualization.md §4.5）。

- AST 断言 worker 模块顶只 import stdlib（无 numpy/pymcnp 顶层 import，惰性按需）。
- parse / texture 往返（stdin JSON → stdout JSON 协议，直接调用 _run）。

不 import gui.backend.api_server / FreeCAD。
"""
import ast
import tempfile
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parent.parent.parent / "app" / "meshtal" / "_meshtal_worker.py"
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _worker_top_imports() -> list[str]:
    """AST 读 worker 模块顶 Import/ImportFrom 的模块名。"""
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_worker_top_level_stdlib_only():
    """契约 §4.5：模块顶只 import stdlib（numpy/pymcnp 惰性按需）。"""
    tops = _worker_top_imports()
    roots = {t.split(".")[0] for t in tops}
    forbidden = {"numpy", "pymcnp"}
    assert not (forbidden & roots), f"worker 模块顶不应 import: {sorted(tops)}"
    # 顶层确有几处 stdlib import（base64/json/os/sys/traceback）
    assert {"base64", "json", "os", "sys", "traceback"} <= set(roots)


@pytest.fixture
def isolated_cache(monkeypatch, tmp_path):
    """把 meshtal_cache 默认目录指到临时目录，隔离真实缓存。"""
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    yield tmp_path


# ── mode=parse 往返 ────────────────────────────────────────────
def test_worker_parse_roundtrip(isolated_cache):
    """mode=parse：minimal_meshtal → ok + grid_bounds + tally 元数据。"""
    from app.meshtal._meshtal_worker import _run
    res = _run({"mode": "parse", "path": str(FIXTURES / "minimal_meshtal.txt")})
    assert res["status"] == "ok"
    assert res["grid_bounds"] == {"min": [0.0, 0.0, 0.0], "max": [2.0, 2.0, 1.0]}
    assert len(res["tallies"]) == 1
    t = res["tallies"][0]
    assert t["number"] == 1 and t["particle"] == "n"
    assert t["dims"]["nVoxels"] == 8
    assert t["range"]["min"] == 1.0 and t["range"]["max"] == 8.0


def test_worker_parse_cache_hit_returns_metadata(isolated_cache):
    """契约 §4.4：二次 parse 命中 manifest 缓存，metadata 一致。"""
    from app.meshtal._meshtal_worker import _run
    path = str(FIXTURES / "minimal_meshtal.txt")
    r1 = _run({"mode": "parse", "path": path})
    r2 = _run({"mode": "parse", "path": path})
    assert r1 == r2
    assert r2["status"] == "ok"


# ── mode=texture 往返 ──────────────────────────────────────────
def test_worker_texture_roundtrip(isolated_cache):
    """mode=texture：标量帧字段（resolution/worldBox/scalarRange/dataBase64/bytes）。"""
    from app.meshtal._meshtal_worker import _run
    res = _run({"mode": "texture", "path": str(FIXTURES / "minimal_meshtal.txt"),
                "tallyNumber": 1, "energyBin": 0, "timeBin": 0, "resolution": 128})
    assert res["status"] == "ok"
    frame = res["frame"]
    assert frame["resolution"] == [2, 2, 2]
    assert frame["worldBox"]["min"] == [0.0, 0.0, 0.0]
    assert frame["worldBox"]["max"] == [2.0, 2.0, 1.0]
    assert frame["bytes"] == 8 and frame["nVoxels"] == 8
    assert frame["downsampled"] is False
    assert "dataBase64" in frame


def test_worker_texture_bad_tally_errors(isolated_cache):
    """mode=texture：tallyNumber 不存在 → status=error（不裸崩溃）。"""
    from app.meshtal._meshtal_worker import _run
    res = _run({"mode": "texture", "path": str(FIXTURES / "minimal_meshtal.txt"),
                "tallyNumber": 99, "energyBin": 0, "timeBin": 0})
    assert res["status"] == "error"
    assert res.get("message")
