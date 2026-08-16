"""PTRAC API 契约测试 —— /api/ptrac-parse（契约 ptrac-visualization.md v2 §3/§5）。

- 漂移闸门：handlers dict 与 api.yaml 双向一致（端点 29）。
- HTTP 子进程后端：parse 信封字段（header/tracks/worldBox/stats/truncated）。
- 坏/不存在路径 → 错误响应带友好中文 hint（F4）。

铁律：本文件【不 import】gui.backend.api_server（模块级 pyvista/FreeCAD 探测）。
HTTP 往返用子进程跑 api_server.py（照 test_api_contract.py 范式）。
"""
import ast
import json
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
API_SERVER = PROJECT_DIR / "gui" / "backend" / "api_server.py"
API_YAML = PROJECT_DIR / "docs" / "contracts" / "api.yaml"
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

PTRAC_PATH = "/api/ptrac-parse"
PTRAC_OPERATION_ID = "ptracParse"


# ── 1. 漂移闸门（端点 29）───────────────────────────────────────
def _handlers_dict_paths() -> set[str]:
    tree = ast.parse(API_SERVER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "handlers":
                    if isinstance(node.value, ast.Dict):
                        return {
                            ast.literal_eval(k)
                            for k in node.value.keys
                            if isinstance(k, ast.Constant)
                        }
    raise AssertionError("未在 api_server.py 找到 handlers dict")


def _yaml_paths_operation_ids() -> dict[str, str]:
    text = API_YAML.read_text(encoding="utf-8")
    result = {}
    current_path = None
    for line in text.splitlines():
        m = re.match(r'^\s{2}(/api/[^:]+):\s*$', line)
        if m:
            current_path = m.group(1)
            continue
        op = re.search(r'operationId:\s*(\w+)', line)
        if op and current_path:
            result[current_path] = op.group(1)
    return result


def test_handlers_dict_has_ptrac_parse():
    """漂移闸门：handlers dict 必须含 /api/ptrac-parse（端点 29）。"""
    handler_paths = _handlers_dict_paths()
    assert PTRAC_PATH in handler_paths, f"handlers dict 缺少 {PTRAC_PATH}"


def test_api_yaml_has_ptrac_parse():
    """漂移闸门：api.yaml 必须含 /api/ptrac-parse 且 operationId=ptracParse。"""
    yaml_ops = _yaml_paths_operation_ids()
    assert PTRAC_PATH in yaml_ops, f"api.yaml 缺少 path {PTRAC_PATH}"
    assert yaml_ops[PTRAC_PATH] == PTRAC_OPERATION_ID, (
        f"api.yaml {PTRAC_PATH} operationId 应为 {PTRAC_OPERATION_ID}"
    )


# ── HTTP 子进程后端 fixture（照 test_meshtal_api.py）────────────
@pytest.fixture(scope="module")
def backend_base_url():
    proc = subprocess.Popen(
        [sys.executable, str(API_SERVER)],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = "http://127.0.0.1:5001"
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                if proc.poll() is not None:
                    break
                s = socket.create_connection(("127.0.0.1", 5001), timeout=1)
                s.close()
                break
            except OSError:
                time.sleep(0.3)
        if proc.poll() is not None:
            pytest.skip(f"后端子进程提前退出 (code={proc.returncode})，跳过 HTTP 往返")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _post(base: str, path: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body


# ── 2. parse 信封（契约 §3）─────────────────────────────────────
def test_http_ptrac_parse_envelope(backend_base_url):
    """ptrac-parse：ok 信封 + header/tracks/worldBox/stats/truncated（fixture 2 历史 7 点）。"""
    status, body = _post(backend_base_url, PTRAC_PATH, {"path": str(FIXTURES / "ptrac_sample.txt")})
    assert status == 200, f"ptrac-parse 端点未实现（HTTP {status}）—— 契约 §3"
    assert body.get("status") == "ok", body
    assert body.get("header", {}).get("code") == "mcnp"
    assert "tracks" in body and len(body["tracks"]) == 2
    assert "worldBox" in body
    assert "stats" in body and body["stats"]["points"] == 7
    assert "truncated" in body and body["truncated"] is False
    # 能量提取（L 表 ID 10）：历史 2 的碰撞事件能量 112.6
    t2 = body["tracks"][1]
    col = next(p for p in t2["points"] if p[3] == 4000)
    assert col[4] == pytest.approx(112.6)
    assert t2["particle"] == "n"


def test_http_ptrac_parse_max_tracks_truncation(backend_base_url):
    """maxTracks=1 → 1 历史 + truncated=True。"""
    status, body = _post(backend_base_url, PTRAC_PATH, {
        "path": str(FIXTURES / "ptrac_sample.txt"), "maxTracks": 1,
    })
    assert status == 200 and body.get("status") == "ok", body
    assert len(body["tracks"]) == 1
    assert body["truncated"] is True
    assert body["stats"]["truncated"] is True


# ── 3. 坏路径 → 友好 hint（F4）──────────────────────────────────
def test_http_ptrac_parse_missing_file_hint(backend_base_url):
    """不存在路径 → 错误响应带 hint（友好中文提示，F4）。"""
    status, body = _post(backend_base_url, PTRAC_PATH, {
        "path": str(FIXTURES / "not_a_ptrac.txt"),
    })
    assert status != 200, "坏路径应返回错误"
    assert body.get("status") == "error"
    assert "hint" in body, "错误响应缺 hint 字段（F4 端点 guard 必须带 hint）"
    assert body["hint"].strip(), "hint 不能为空"


def test_http_ptrac_parse_bad_file_hint(backend_base_url, tmp_path):
    """非 PTRAC 文件（首行非 -1）→ 错误响应带 hint。"""
    bad = tmp_path / "bad.ptrac"
    bad.write_text("this is not ptrac\n" + "x" * 80 + "\n", encoding="utf-8")
    status, body = _post(backend_base_url, PTRAC_PATH, {"path": str(bad)})
    assert status != 200, "非 PTRAC 文件应返回错误"
    assert body.get("status") == "error"
    assert "hint" in body and body["hint"].strip()
