"""API 份额语义测试 —— /api/expand-formula 的 is_weight 参数（质量份额 / 原子份额）。

背景（2026-08-14，PM 派发）：
  - handler 用 pymcnp.inp.M_0.from_formula 展开化学式；
  - 默认 is_weight=True → 质量份额（MCNP 约定 负=质量），fraction 带负号；
  - is_weight=False → 原子份额（MCNP 约定 正=原子），fraction 带正号；
  - 正负号全链路保留（负=质量 / 正=原子 语义不变），只让前端可选原子份额。

覆盖：
  ① 默认（不传 is_weight）= 质量份额负号（向后兼容，与现状一致）；
  ② is_weight=false = 原子份额正号；
  ③ 符号约定正确（质量全负 / 原子全正，且二者互为相反数）；
  ④ 显式 is_weight=true == 默认（加性兼容）；
  ⑤ null / 字符串 "false" 防御性布尔解析（输入校验）；
  ⑥ 空公式仍走既有错误路径（is_weight 扩展不破坏错误响应）。

铁律：本文件【不 import】gui.backend.api_server（模块级 pyvista/FreeCAD 探测）。
HTTP 往返用子进程跑 api_server.py（照 test_api_contract.py / test_meshtal_api.py 范式）。
"""
import json
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


def _expand(base: str, payload: dict) -> list[dict]:
    status, body = _post(base, "/api/expand-formula", payload)
    assert status == 200, body
    assert body.get("status") == "ok", body
    nuclides = body.get("nuclides")
    assert nuclides, "expand-formula 未返回 nuclides"
    return nuclides


# ── ① 默认（不传 is_weight）= 质量份额负号（向后兼容）────────
def test_expand_formula_default_is_mass_negative(backend_base_url):
    """默认不传 is_weight → 质量份额，所有 fraction 为负（MCNP 负=质量约定）。"""
    nuclides = _expand(backend_base_url, {"formula": "H2O"})
    assert len(nuclides) >= 2
    for n in nuclides:
        assert float(n["fraction"]) < 0, f"质量份额应为负号: {n}"


# ── ② is_weight=false = 原子份额正号 ────────────────────────
def test_expand_formula_is_weight_false_is_atomic_positive(backend_base_url):
    """is_weight=false → 原子份额，所有 fraction 为正（MCNP 正=原子约定）。"""
    nuclides = _expand(backend_base_url, {"formula": "H2O", "is_weight": False})
    assert len(nuclides) >= 2
    for n in nuclides:
        assert float(n["fraction"]) > 0, f"原子份额应为正号: {n}"


# ── ③ 符号约定正确（质量全负 / 原子全正，互为相反数）────────
def test_expand_formula_sign_convention_mass_vs_atomic(backend_base_url):
    """同一化学式下，原子份额 == 负的质量份额（同一 zaid 一一对应）。"""
    mass = _expand(backend_base_url, {"formula": "H2O"})
    atomic = _expand(backend_base_url, {"formula": "H2O", "is_weight": False})
    assert [n["zaid"] for n in mass] == [n["zaid"] for n in atomic], (
        "质量/原子模式应展开出相同核素集合"
    )
    for m, a in zip(mass, atomic):
        assert float(a["fraction"]) == pytest.approx(-float(m["fraction"])), (
            f"{m['zaid']}: 原子份额 {a['fraction']} 应等于 质量份额相反数 "
            f"{m['fraction']}"
        )


# ── ④ 显式 is_weight=true == 默认（加性兼容）────────────────
def test_expand_formula_explicit_true_equals_default(backend_base_url):
    """显式传 is_weight=true 应与不传完全一致（向后兼容不漂移）。"""
    default = _expand(backend_base_url, {"formula": "H2O"})
    explicit = _expand(backend_base_url, {"formula": "H2O", "is_weight": True})
    assert default == explicit


# ── ⑤ 防御性布尔解析（null / 字符串 "false"）────────────────
def test_expand_formula_is_weight_null_defaults_mass(backend_base_url):
    """is_weight 传 null → 视为缺省 true（质量份额负号）。"""
    nuclides = _expand(backend_base_url, {"formula": "H2O", "is_weight": None})
    for n in nuclides:
        assert float(n["fraction"]) < 0


def test_expand_formula_is_weight_string_false_parses_atomic(backend_base_url):
    """is_weight 传字符串 "false" → 防御性解析为原子份额正号。"""
    nuclides = _expand(backend_base_url, {"formula": "H2O", "is_weight": "false"})
    for n in nuclides:
        assert float(n["fraction"]) > 0


# ── ⑥ 空公式错误路径不回归 ────────────────────────────────
def test_expand_formula_empty_formula_still_errors(backend_base_url):
    """空化学式仍返回 500 error（is_weight 扩展不破坏既有错误路径）。"""
    status, body = _post(backend_base_url, "/api/expand-formula", {"formula": ""})
    assert status == 500
    assert body.get("status") == "error"
