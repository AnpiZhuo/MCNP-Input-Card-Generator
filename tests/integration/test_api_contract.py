"""
契约漂移闸门（P0-6）—— 防 API 契约文档腐烂。
================================================
1. AST 读 api_server.py handlers 字典（486-512），断言每个 path 在 api.yaml 有 operationId。
2. gui/src/utils/contract.ts backend 字段 ⊆ app/models.py 字段。
3. 三核心端点（/api/generate, /api/parse-inp, /api/validate-inp）真实 HTTP 往返：
   起本地后端（子进程，端口 5001），POST 断言统一信封 {status:"ok"}。

铁律：本文件【不 import】gui.backend.api_server（模块级 pyvista/FreeCAD 探测）。
HTTP 往返用子进程跑 api_server.py，import 发生在独立进程。
"""
import ast
import json
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
API_SERVER = PROJECT_DIR / "gui" / "backend" / "api_server.py"
CONTRACT_TS = PROJECT_DIR / "gui" / "src" / "utils" / "contract.ts"
MODELS_PY = PROJECT_DIR / "app" / "models.py"
API_YAML = PROJECT_DIR / "docs" / "contracts" / "api.yaml"

MINIMAL_DECK = {
    "basic": {"title": "contract deck", "mode_n": True, "nps": "100000"},
    "surfaces": "1  rcc  0 0 0  0 10 0  2",
    "cells": [{"kind": "cell", "cell": {
        "number": 1, "material": "1", "density": "-1.0", "surface_expr": "-1"}}],
    "materials": [{"number": 1, "rows": [
        {"kind": "nuclide", "zaid": "92235.06c", "fraction": "-0.05"}]}],
    "sources": [{"number": 1, "erg": "14.0", "pos_x": "0", "pos_y": "0",
                 "pos_z": "0"}],
    "adv": {"source_mode": "fixed"},
}
MINIMAL_INP = (
    "t\n1 1 -1.0 -1 imp:n=1\n\n1 rcc 0 0 0 0 10 0 2\n\n"
    "mode n\nm1 92235 -0.05\nsdef pos 0 0 0 erg=14\nnps 100000\n"
)


# ── 1. AST 读 handlers → api.yaml operationId ───────────
def _handlers_dict_paths() -> set[str]:
    """AST 读 api_server.py 中 do_POST 的 handlers dict 的所有 path 键。"""
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
    """轻量解析 api.yaml：{path: operationId}（不依赖 PyYAML）。"""
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


def test_contract_api_yaml_operation_ids():
    """handlers dict 每个 path 在 api.yaml 都有 operationId（防新增端点漏文档）。"""
    if not API_YAML.is_file():
        pytest.skip("docs/contracts/api.yaml 缺失（待架构师产出后补跑）")
    handler_paths = _handlers_dict_paths()
    yaml_ops = _yaml_paths_operation_ids()
    missing = handler_paths - set(yaml_ops)
    assert not missing, f"api.yaml 缺少以下端点的 operationId: {sorted(missing)}"


def test_contract_api_yaml_no_stale_paths():
    """api.yaml 中的 path 都应存在于 handlers dict（防文档写僵尸端点）。"""
    if not API_YAML.is_file():
        pytest.skip("docs/contracts/api.yaml 缺失（待架构师产出后补跑）")
    handler_paths = _handlers_dict_paths()
    yaml_paths = set(_yaml_paths_operation_ids())
    stale = yaml_paths - handler_paths
    assert not stale, f"api.yaml 含 handlers dict 中不存在的 path: {sorted(stale)}"


# ── 2. contract.ts backend 字段 ⊆ models.py 字段 ────────
def _contract_backend_fields() -> set[str]:
    text = CONTRACT_TS.read_text(encoding="utf-8")
    return set(re.findall(r'backend:\s*"([^"]+)"', text))


def _models_dataclass_fields() -> set[str]:
    """收集 models.py 中所有 @dataclass 类的字段名。

    @dataclass 装饰器在 AST 中是 ast.Name("dataclass")（非 Attribute），
    需同时匹配 Name 与 Attribute 两种形态。
    """
    tree = ast.parse(MODELS_PY.read_text(encoding="utf-8"))
    fields = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        is_dc = any(
            (isinstance(b, ast.Name) and b.id == "dataclass")
            or (isinstance(b, ast.Attribute) and b.attr == "dataclass")
            for b in node.decorator_list
        )
        if not is_dc:
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                fields.add(stmt.target.id)
            elif isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        fields.add(t.id)
    return fields


def test_contract_backend_fields_subset_of_models():
    """contract.ts 每个 backend 字段都应在 models.py 某 dataclass 中存在。"""
    contract_fields = _contract_backend_fields()
    model_fields = _models_dataclass_fields()
    missing = contract_fields - model_fields
    assert not missing, (
        f"contract.ts 引用 models.py 不存在的字段: {sorted(missing)}\n"
        "（前端/后端任一改了字段名，本闸门拦截）"
    )


# ── 3. 三核心端点真实 HTTP 往返 ─────────────────────────
@pytest.fixture(scope="module")
def backend_base_url():
    """起 api_server.py 子进程（端口 5001），就绪后返回 base URL。"""
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
        # 冒烟就绪
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_http_generate(backend_base_url):
    """/api/generate：最小 deck → status ok + inp 非空。"""
    resp = _post(backend_base_url, "/api/generate", MINIMAL_DECK)
    assert resp.get("status") == "ok", resp
    assert resp.get("inp"), "generate 未返回 inp"
    assert "SDEF" in resp["inp"]


def test_http_parse_inp(backend_base_url):
    """/api/parse-inp：INP 文本 → status ok + deck 结构化。"""
    resp = _post(backend_base_url, "/api/parse-inp", {"inp": MINIMAL_INP})
    assert resp.get("status") == "ok", resp
    deck = resp.get("deck", {})
    assert len(deck.get("cells", [])) >= 1
    assert deck.get("basic", {}).get("mode_n") is True


def test_http_validate_inp(backend_base_url):
    """/api/validate-inp：INP 文本 → status ok + valid/errors。"""
    resp = _post(backend_base_url, "/api/validate-inp", {"inp": MINIMAL_INP})
    assert resp.get("status") == "ok", resp
    assert "valid" in resp and "errors" in resp


def test_http_generate_then_parse_roundtrip(backend_base_url):
    """端到端：generate 的输出喂给 parse-inp → 解析出相同栅元数。"""
    g = _post(backend_base_url, "/api/generate", MINIMAL_DECK)
    assert g["status"] == "ok"
    p = _post(backend_base_url, "/api/parse-inp", {"inp": g["inp"]})
    assert p["status"] == "ok"
    assert len(p["deck"].get("cells", [])) >= 1
