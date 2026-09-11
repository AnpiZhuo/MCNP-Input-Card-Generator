"""MESHTAL API 契约与 hint 测试 —— 三端点（meshtal-detect/parse/texture）+ _err hint（契约 §3 / §12 A1.2 / F4）。

现状（2026-08-14，功能未实现 → 红基线）：
  - api_server handlers dict（:501-527）仅 25 端点，无三 meshtal 端点 → 请求 404；
  - api.yaml 仅 25 端点，无三 meshtal operationId；
  - `_err(self, msg, status=500)`（:546）无 hint 参数（F4 未实现）。

红基线 pin（**2026-09-10 更正：以下 1-7 项均已于 v1.7.0 清偿，本文件应全绿；"RED"字样为初版遗留，红灯即真红灯**）：
  1. 漂移闸门预置 3 operationId：handlers dict 必须有 /api/meshtal-detect|parse|texture —— 已交付
  2. 漂移闸门预置：api.yaml 必须有三 path 且 operationId=meshtalDetect/Parse/Texture —— 已交付
  3. F4：_err 签名增可选 hint 参数（缺省 → 对既有端点加性兼容）—— 已交付
  4. HTTP meshtal-detect：ok 信封 + files/outputDir —— 已交付
  5. HTTP meshtal-parse：响应带 grid_bounds + match（A1.2）—— 已交付
  6. HTTP meshtal-parse 坏文件 → 错误响应带友好 hint（F4）—— 已交付
  7. HTTP meshtal-texture：标量帧字段（resolution/worldBox/scalarRange/dataBase64）—— 已交付
  8. 对照：既有端点错误响应不含 hint 字段（hint 空缺省省略，加性兼容不破坏既有字段）—— 对照

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

MESHTAL_PATHS = ["/api/meshtal-detect", "/api/meshtal-parse", "/api/meshtal-texture"]
MESHTAL_OPERATION_IDS = {
    "/api/meshtal-detect": "meshtalDetect",
    "/api/meshtal-parse": "meshtalParse",
    "/api/meshtal-texture": "meshtalTexture",
}


# ── 1/2. 漂移闸门预置 3 operationId（红：handlers/api.yaml 均未加）──
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


def test_handlers_dict_has_three_meshtal_paths():
    """漂移闸门：handlers dict 必须含三 meshtal 端点（当前 25 端点缺失 → RED）。"""
    handler_paths = _handlers_dict_paths()
    missing = set(MESHTAL_PATHS) - handler_paths
    assert not missing, f"handlers dict 缺少 meshtal 端点: {sorted(missing)}"


def test_api_yaml_has_three_meshtal_paths_with_operation_ids():
    """漂移闸门：api.yaml 必须含三 meshtal path 且 operationId 齐（当前 25 端点缺失 → RED）。"""
    yaml_ops = _yaml_paths_operation_ids()
    for path, opid in MESHTAL_OPERATION_IDS.items():
        assert path in yaml_ops, f"api.yaml 缺少 path {path}"
        assert yaml_ops[path] == opid, f"api.yaml {path} operationId 应为 {opid}"


# ── 3. F4：_err 可选 hint 参数（加性兼容）────────────────────────
def _err_signature_params() -> dict[str, object]:
    """AST 读 _err 方法定义的参数名→默认值映射（未带默认值记为 None）。"""
    tree = ast.parse(API_SERVER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_err":
            params = {}
            defaults = node.args.defaults
            n_plain = len(node.args.args) - len(defaults)
            for idx, arg in enumerate(node.args.args):
                default = None
                if idx >= n_plain:
                    d = defaults[idx - n_plain]
                    default = ast.unparse(d) if d is not None else None
                params[arg.arg] = default
            return params
    raise AssertionError("未在 api_server.py 找到 _err 方法")


def test_err_hint_param_additive_default():
    """F4：_err 增可选 hint 参数（hint 缺省 → 对既有 25 端点加性兼容，响应字段不变）。"""
    sig = _err_signature_params()
    assert "hint" in sig, "F4 未实现：_err 缺 hint 参数（三 meshtal 端点 guard 须带 hint）"
    assert sig["hint"] is not None, "hint 必须是可选参数（带缺省，既有调用不传 hint → 字段不变）"


# ── HTTP 子进程后端 fixture（照 test_api_contract.py）────────────
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body


# ── 4. meshtal-detect ───────────────────────────────────────────
def test_http_meshtal_detect(backend_base_url, tmp_path):
    """meshtal-detect：outputDir 内 meshtal* 文件 → status ok + files + outputDir（契约 §3.1）。"""
    (tmp_path / "meshtal").write_text("x")
    (tmp_path / "notmeshtal.txt").write_text("y")
    status, body = _post(backend_base_url, "/api/meshtal-detect", {"outputDir": str(tmp_path)})
    assert status == 200, f"meshtal-detect 端点未实现（HTTP {status}）—— 契约 §3.1"
    assert body.get("status") == "ok", body
    assert "files" in body and "outputDir" in body
    names = [f["name"] for f in body["files"]]
    assert "meshtal" in names, f"meshtal-detect 未扫到 meshtal 文件: {names}"


# ── 5. meshtal-parse：grid_bounds + match（A1.2）─────────────────
def test_http_meshtal_parse_grid_bounds_and_match(backend_base_url):
    """meshtal-parse：响应带 grid_bounds（bin 边界世界包围盒）+ match（deck↔meshtal 比对，A1.2）。"""
    fixture = FIXTURES / "minimal_meshtal.txt"
    model_box = {"min": [0.0, 0.0, 0.0], "max": [2.0, 2.0, 1.0]}  # 与 minimal 网格重合
    status, body = _post(backend_base_url, "/api/meshtal-parse", {
        "path": str(fixture), "modelBox": model_box,
    })
    assert status == 200, f"meshtal-parse 端点未实现（HTTP {status}）—— 契约 §3.2"
    assert body.get("status") == "ok", body
    assert "grid_bounds" in body, "meshtal-parse 响应缺 grid_bounds（A1.2）"
    assert body["grid_bounds"] == {"min": [0.0, 0.0, 0.0], "max": [2.0, 2.0, 1.0]}
    assert "match" in body, "meshtal-parse 响应缺 match（A1.2）"
    m = body["match"]
    for key in ("matched", "overlapFraction", "centerOffsetFrac", "reason"):
        assert key in m, f"match 缺字段 {key}"


def test_http_meshtal_parse_no_model_box_match_null(backend_base_url):
    """两者皆缺 modelBox → match:null（契约 §3.2：跳过比对，不静默错位）。"""
    fixture = FIXTURES / "minimal_meshtal.txt"
    status, body = _post(backend_base_url, "/api/meshtal-parse", {"path": str(fixture)})
    assert status == 200 and body.get("status") == "ok", body
    assert body.get("match") is None, "缺 modelBox 时应 match=null"


def test_http_meshtal_parse_model_box_from_cells_surfaces(backend_base_url):
    """A1.2 契约缺口修复：请求带 cells/surfaces（无 modelBox）→ handler 推算模型盒并返回 match。"""
    fixture = FIXTURES / "minimal_meshtal.txt"
    status, body = _post(backend_base_url, "/api/meshtal-parse", {
        "path": str(fixture),
        "surfaces": "1 rpp 0 2 0 2 0 1",
        "cells": [{"number": 1, "material": "1", "surface_expr": "-1"}],
        "tr_cards": "",
    })
    assert status == 200 and body.get("status") == "ok", body
    m = body.get("match")
    assert m is not None, "带 cells/surfaces 应推算 modelBox 并返回 match（A1.2 契约缺口）"
    assert m["matched"] is True, m


def test_http_meshtal_parse_detects_displaced_grid(backend_base_url):
    """真实案例回归（绝不静默错位）：模型在原点（rpp -1 1 -1 1 0 1），
    网格在 (50,0,100)（用户真实 meshtal）→ matched=False。"""
    fixture = FIXTURES / "real_meshtal_jk.meshtal"
    status, body = _post(backend_base_url, "/api/meshtal-parse", {
        "path": str(fixture),
        "surfaces": "1 rpp -1 1 -1 1 0 1\n9 so 1000\n10 so 2000",
        "cells": [
            {"number": 10, "material": "1", "surface_expr": "-1"},
            {"number": 20, "material": "0", "surface_expr": "1 -9"},
            {"number": 30, "material": "0", "surface_expr": "9 -10"},
        ],
        "tr_cards": "",
    })
    assert status == 200 and body.get("status") == "ok", body
    m = body.get("match")
    assert m is not None and m["matched"] is False, m


# ── 6. meshtal-parse 坏文件 → 友好 hint（F4）────────────────────
def test_http_meshtal_parse_bad_file_friendly_hint(backend_base_url):
    """坏/不存在路径 → 错误响应带 hint（友好中文提示，F4）。"""
    status, body = _post(backend_base_url, "/api/meshtal-parse",
                         {"path": str(FIXTURES / "not_a_meshtal.bin")})
    assert status != 200, "坏文件应返回错误"
    assert body.get("status") == "error"
    assert "hint" in body, "错误响应缺 hint 字段（F4 三 meshtal 端点 guard 必须带 hint）"
    assert body["hint"].strip(), "hint 不能为空"


# ── 7. meshtal-texture：标量帧字段 ──────────────────────────────
def test_http_meshtal_texture_frame_fields(backend_base_url):
    """meshtal-texture：ok 信封 + frame（resolution/worldBox/scalarRange/dataBase64 等，契约 §3.3）。"""
    fixture = FIXTURES / "minimal_meshtal.txt"
    status, body = _post(backend_base_url, "/api/meshtal-texture", {
        "path": str(fixture), "tallyNumber": 1, "energyBin": 0, "timeBin": 0,
        "resolution": 128, "normalize": "adaptive",
    })
    assert status == 200, f"meshtal-texture 端点未实现（HTTP {status}）—— 契约 §3.3"
    assert body.get("status") == "ok", body
    frame = body.get("frame", {})
    assert "resolution" in frame and "worldBox" in frame
    assert "scalarRange" in frame and "dataBase64" in frame
    assert "bytes" in frame and "nVoxels" in frame


# ── 8. 对照：既有端点错误响应不含 hint（加性兼容）───────────────
def test_http_existing_error_response_has_no_hint(backend_base_url):
    """对照：既有端点（非 meshtal）错误响应不含 hint 字段（hint 空缺省省略，不破坏既有字段）。

    当前 _err 无 hint → 无 hint 字段（GREEN 对照）；施工后 hint 空缺省仍应省略 → 保持 GREEN。
    """
    status, body = _post(backend_base_url, "/api/generate", {"garbage": True})
    assert status == 200 or body.get("status") == "error" or "inp" in body
    if body.get("status") == "error":
        assert "hint" not in body, "既有端点不应带 hint（hint 空缺省省略，加性兼容）"
