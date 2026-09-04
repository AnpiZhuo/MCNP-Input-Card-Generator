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


FORM_SDEF_DECK = {
    "basic": {"title": "form sdef", "mode_n": True, "nps": "1000"},
    "surfaces": "", "cells": [], "materials": [], "sources": [],
    "tally": {},
    "adv": {
        "source_mode": "distribution",
        "sdef_erg": "14",
        "sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0",
    },
}


def test_http_form_sdef_generate(backend_base_url):
    """表单模式 SDEF（sources 空、adv.sdef_* 有值）→ 输出含 SDEF 卡（用户实测漏源卡回归）。"""
    resp = _post(backend_base_url, "/api/generate", FORM_SDEF_DECK)
    assert resp.get("status") == "ok", resp
    assert "SDEF" in resp.get("inp", "")
    assert "ERG=14" in resp["inp"]
    assert "POS=0 0 0" in resp["inp"]


def test_http_sdef_extra_survives_roundtrip(backend_base_url):
    """导入带未知 SDEF 参数（EFF=）→ 再生成仍保留（sdef_extra API 往返不丢）。"""
    inp_text = (
        "form sdef extra\n"
        "1 0 -1\n\n"
        "1 sph 0 0 0 1\n\n"
        "mode n\n"
        "sdef erg=14 eff=1\n"
        "nps 100\n"
    )
    p = _post(backend_base_url, "/api/parse-inp", {"inp": inp_text})
    assert p.get("status") == "ok", p
    g = _post(backend_base_url, "/api/generate", p.get("deck", {}))
    assert g.get("status") == "ok", g
    assert "EFF=1" in g.get("inp", "")


def test_http_parse_outp_compact_mcnp61(backend_base_url):
    """/api/parse-outp：MCNP6.1 紧凑 tally 布局（无 energy 列/total 行）→ 正常解析（用户实测 1.o）。"""
    outp = (PROJECT_DIR / "tests" / "fixtures" / "simple_tally.outp").read_text(encoding="utf-8")
    resp = _post(backend_base_url, "/api/parse-outp", {"outp": outp})
    assert resp.get("status") == "ok", resp
    assert resp.get("nps") == 10000
    assert "4" in resp.get("tallies", {})
    t = resp["tallies"]["4"]
    assert t["type"] == 4
    assert t["rows"] == [{"energy": "", "flux": "3.36115E-03", "error": "0.0071"}]


def test_http_sweep_run_budget_rejected(backend_base_url):
    """sweep-run 组合数×单次超时超总预算（7×300>1800s）→ code=budget_exceeded 拒绝。

    拒绝发生在 MCNP 检测之前，不依赖真实 MCNP 可执行文件。
    """
    params = [{"name": "nps", "pattern": r"NPS\s+(\d+)",
               "values": [1000, 2000, 3000, 4000, 5000, 6000, 7000]}]
    resp = _post(backend_base_url, "/api/sweep-run",
                 {"deck": "t\n", "parameters": params})
    assert resp.get("status") == "error", resp
    assert resp.get("code") == "budget_exceeded", resp
    assert "7" in resp.get("message", "")  # 当前组合数
    assert "预算" in resp.get("message", "")


def test_http_validate_lattice_surfaces(backend_base_url):
    """/api/validate-lattice-surfaces：17×17 4 平面 2D → ok:true；含 # 拒绝；lat=2 8 平面合法。"""
    resp = _post(backend_base_url, "/api/validate-lattice-surfaces", {
        "surface_expr": "50 -51 52 -53",
        "lat": "1",
        "surfaces_text": "50 px -0.63\n51 px 0.63\n52 py -0.63\n53 py 0.63",
    })
    assert resp.get("status") == "ok", resp
    assert resp.get("ok") is True, resp
    assert resp.get("msg") == "", resp
    resp_bad = _post(backend_base_url, "/api/validate-lattice-surfaces", {
        "surface_expr": "-10 #11", "lat": "1",
        "surfaces_text": "10 px 0\n11 py 0",
    })
    assert resp_bad.get("ok") is False, resp_bad
    resp_hex = _post(backend_base_url, "/api/validate-lattice-surfaces", {
        "surface_expr": "-1 -2 -3 -4 -5 -6 -7 8",
        "lat": "2",
        "surfaces_text": (
            "1 p 0.866 0.5 0 -0.866\n2 p 0.866 -0.5 0 -0.866\n"
            "3 p 0 -1.0 0 -0.866\n4 p -0.866 -0.5 0 -0.866\n"
            "5 p -0.866 0.5 0 -0.866\n6 p 0 1.0 0 -0.866\n"
            "7 pz 0.5\n8 pz -0.5"),
    })
    assert resp_hex.get("status") == "ok", resp_hex
    assert resp_hex.get("ok") is True, resp_hex


# ── 格阵阶段3端点：lattice-extent / preview-lattice ──────
LATTICE_FILL_GRID = {
    "lat": "1", "kind": "lattice", "range": ["0:1", "0:1", "0:0"], "dims": [2, 2, 1],
    "cells": [
        {"u": "1", "dx": "", "dy": "", "dz": ""},
        {"u": "2", "dx": "", "dy": "", "dz": ""},
        {"u": "1", "dx": "", "dy": "", "dz": ""},
        {"u": "2", "dx": "", "dy": "", "dz": ""},
    ],
    "raw": "0:1 0:1 0:0 1 2 1 2",
}
LATTICE_DECK = {
    "surfaces": "1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 cz 0.3\n6 cz 0.5",
    "tr_cards": "",
    "cells": [
        {"kind": "cell", "cell": {"number": 20, "material": "0", "density": "",
                                  "surface_expr": "1 -2 3 -4", "u": "10", "fill": "0:1 0:1 0:0",
                                  "lat": "1", "trcl": "", "render": True,
                                  "fill_grid": json.dumps(LATTICE_FILL_GRID)}},
        {"kind": "cell", "cell": {"number": 1, "material": "1", "density": "-1.0",
                                  "surface_expr": "-5", "u": "1", "render": True,
                                  "fill_grid": ""}},
        {"kind": "cell", "cell": {"number": 2, "material": "2", "density": "-1.0",
                                  "surface_expr": "5 -6", "u": "2", "render": True,
                                  "fill_grid": ""}},
    ],
}


# 嵌套格阵：堆芯 u=100 → 组件 u=201 → 针 u=1/2。cells 顺序组件(600)在前 → 复现 lattice_infos[0] 误选组件
_ASSEMBLY_FG = {
    "lat": "1", "kind": "lattice", "range": ["0:1", "0:1", "0:0"], "dims": [2, 2, 1],
    "cells": [{"u": "1", "dx": "", "dy": "", "dz": ""}, {"u": "2", "dx": "", "dy": "", "dz": ""},
              {"u": "1", "dx": "", "dy": "", "dz": ""}, {"u": "2", "dx": "", "dy": "", "dz": ""}],
    "raw": "0:1 0:1 0:0 1 2 1 2",
}
_CORE_FG = {
    "lat": "1", "kind": "lattice", "range": ["0:1", "0:1", "0:0"], "dims": [2, 2, 1],
    "cells": [{"u": "201", "dx": "", "dy": "", "dz": ""}, {"u": "5", "dx": "", "dy": "", "dz": ""},
              {"u": "5", "dx": "", "dy": "", "dz": ""}, {"u": "201", "dx": "", "dy": "", "dz": ""}],
    "raw": "0:1 0:1 0:0 201 5 5 201",
}
NESTED_DECK = {
    "surfaces": "1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 pz -1\n6 pz 1\n7 cz 0.3\n8 cz 0.5",
    "tr_cards": "",
    "cells": [
        {"kind": "cell", "cell": {"number": 600, "material": "0", "density": "", "surface_expr": "1 -2 3 -4 5 -6",
                                  "u": "201", "fill": "0:1 0:1 0:0", "lat": "1", "trcl": "", "render": True,
                                  "fill_grid": json.dumps(_ASSEMBLY_FG)}},
        {"kind": "cell", "cell": {"number": 410, "material": "0", "density": "", "surface_expr": "1 -2 3 -4 5 -6",
                                  "u": "100", "fill": "0:1 0:1 0:0", "lat": "1", "trcl": "", "render": True,
                                  "fill_grid": json.dumps(_CORE_FG)}},
        {"kind": "cell", "cell": {"number": 1, "material": "1", "density": "-1.0", "surface_expr": "-7", "u": "1", "render": True, "fill_grid": ""}},
        {"kind": "cell", "cell": {"number": 2, "material": "2", "density": "-1.0", "surface_expr": "7 -8", "u": "2", "render": True, "fill_grid": ""}},
        {"kind": "cell", "cell": {"number": 5, "material": "5", "density": "-1.0", "surface_expr": "1 -2 3 -4 5 -6", "u": "5", "render": True, "fill_grid": ""}},
    ],
}


def test_http_preview_lattice_outermost_root(backend_base_url):
    """/api/preview-lattice 嵌套：外层格阵=未被任何格阵 fill 引用的堆芯 u=100（cells 顺序组件在前也不误选）。"""
    resp = _post(backend_base_url, "/api/preview-lattice", NESTED_DECK)
    assert resp.get("status") == "ok", resp
    lattices = resp.get("lattices", [])
    assert lattices, resp
    # 根格阵应为堆芯 cell 410（u=100），而非列表中第一个格阵 cell 600（组件）
    assert lattices[0]["num"] == 410, lattices
    assert len(lattices[0]["positions"]) == 4, lattices[0]
    assert all(p["u"] in ("201", "5") for p in lattices[0]["positions"]), lattices[0]


def test_http_lattice_extent(backend_base_url):
    """/api/lattice-extent：rect 2D → ok + extent（z 无界）；含 # → ok:false + extent:null。"""
    resp = _post(backend_base_url, "/api/lattice-extent", {
        "surface_expr": "1 -2 3 -4", "lat": "1",
        "surfaces_text": "1 px -1\n2 px 1\n3 py -1\n4 py 1",
    })
    assert resp.get("status") == "ok", resp
    assert resp.get("ok") is True, resp
    ext = resp.get("extent")
    assert ext is not None, resp
    assert ext["x_min"] == -1 and ext["x_max"] == 1
    assert ext["y_min"] == -1 and ext["y_max"] == 1
    assert ext["z_min"] is None and ext["z_max"] is None
    bad = _post(backend_base_url, "/api/lattice-extent", {
        "surface_expr": "-10 #11", "lat": "1", "surfaces_text": "10 px 0",
    })
    assert bad.get("status") == "ok", bad
    assert bad.get("ok") is False, bad
    assert bad.get("extent") is None, bad
    assert bad.get("msg"), bad


def test_http_preview_lattice_shape(backend_base_url):
    """/api/preview-lattice：2×2 格阵 → lattices/positions/leafInstances/count shape。"""
    resp = _post(backend_base_url, "/api/preview-lattice", LATTICE_DECK)
    assert resp.get("status") == "ok", resp
    assert resp.get("limit") in ("ok", "depth_limit", "too_many"), resp
    lattices = resp.get("lattices", [])
    assert len(lattices) == 1, resp
    lat = lattices[0]
    assert lat["num"] == 20, lat
    assert lat["lat"] == "1"
    assert lat["dims"] == [2, 2, 1], lat
    positions = lat.get("positions", [])
    assert len(positions) == 4, lat
    assert positions[0]["u"] == "1" and positions[0]["idx"] == 0
    assert positions[1]["u"] == "2"
    assert set(positions[0].keys()) == {"idx", "u", "x", "y", "z", "dx", "dy", "dz"}
    assert isinstance(lat.get("universes"), dict), lat
    leaves = resp.get("leafInstances", [])
    assert len(leaves) == 4, resp
    for leaf in leaves:
        assert set(leaf.keys()) == {"path", "u", "cellNum", "mat", "x", "y", "z", "depth"}
    assert resp.get("count") == 4, resp
    assert isinstance(resp.get("tree"), list), resp
    assert isinstance(resp.get("detailViable"), bool), resp


# 项13 cycle：外层格阵 → universe 1 → fill=2 → fill=1（U=1→U=2→U=1 循环）。
CYCLE_FILL_GRID = {
    "lat": "1", "kind": "lattice", "range": ["0:0", "0:0", "0:0"], "dims": [1, 1, 1],
    "cells": [{"u": "1", "dx": "", "dy": "", "dz": ""}],
    "raw": "0:0 0:0 0:0 1",
}
CYCLE_DECK = {
    "surfaces": "1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 cz 0.3",
    "tr_cards": "",
    "cells": [
        {"kind": "cell", "cell": {"number": 20, "material": "0", "density": "",
                                  "surface_expr": "1 -2 3 -4", "u": "10", "fill": "0:0 0:0 0:0",
                                  "lat": "1", "trcl": "", "render": True,
                                  "fill_grid": json.dumps(CYCLE_FILL_GRID)}},
        {"kind": "cell", "cell": {"number": 1, "material": "0", "density": "",
                                  "surface_expr": "-5", "u": "1", "fill": "2",
                                  "lat": "", "trcl": "", "render": True, "fill_grid": ""}},
        {"kind": "cell", "cell": {"number": 2, "material": "0", "density": "",
                                  "surface_expr": "-5", "u": "2", "fill": "1",
                                  "lat": "", "trcl": "", "render": True, "fill_grid": ""}},
    ],
}


def test_http_preview_lattice_cycle(backend_base_url):
    """项13：循环嵌套 → status 200 + limit=cycle + cycle=true + chain 闭合链断言。"""
    resp = _post(backend_base_url, "/api/preview-lattice", CYCLE_DECK)
    assert resp.get("status") == "ok", resp
    assert resp.get("limit") == "cycle", resp
    assert resp.get("cycle") is True, resp
    chain = resp.get("chain", [])
    assert len(chain) >= 3, f"cycle 链应至少 3 个节点（首尾闭合）: {chain}"
    assert chain[0] == chain[-1], f"cycle 链应首尾闭合: {chain}"
    assert {"1", "2"} <= set(chain), f"cycle 链应含 1/2: {chain}"


# ── universe 覆盖完整性检测（validate-universe-coverage）──
# 格元盒 = 六平面 ±1（曲面 1..6），内部圆柱 CZ=0.3（曲面 7），外围 void = 盒补柱。
COV_SURF = "1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 pz -1\n6 pz 1\n7 cz 0.3"
COV_SURFACE_EXPR = "1 -2 3 -4 5 -6"
COV_DECK = {
    "surfaces": COV_SURF,
    "tr_cards": "",
    "lat": "1",
    "surface_expr": COV_SURFACE_EXPR,
    "cells": [
        # universe 5：内部圆柱（-7 = 柱内）
        {"kind": "cell", "cell": {"number": 11, "material": "1", "density": "-1.0",
                                  "u": "5", "surface_expr": "-7", "render": True,
                                  "fill_grid": ""}},
        # 外围 void：盒 ∩ 柱外（7 正侧=柱外）→ 与内部一起填满格元盒
        {"kind": "cell", "cell": {"number": 12, "material": "0", "density": "",
                                  "u": "5", "surface_expr": "1 -2 3 -4 5 -6 7", "render": True,
                                  "fill_grid": ""}},
    ],
}


def test_http_validate_universe_coverage_leaf_uncovered(backend_base_url):
    """universe 只定义内部（-7）没定义外部 → kind=leaf + covered=false（红框预防）。"""
    deck = dict(COV_DECK)
    # 移除外围 void，只留内部圆柱
    deck["cells"] = [deck["cells"][0]]
    resp = _post(backend_base_url, "/api/validate-universe-coverage",
                 {**deck, "universe": "5"})
    assert resp.get("status") == "ok", resp
    assert resp.get("kind") == "leaf", resp
    assert resp.get("covered") is False, resp
    assert resp.get("uncoveredFraction", 0) > 0, resp
    assert "未" in resp.get("message", "") or "红框" in resp.get("message", "")


def test_http_validate_universe_coverage_leaf_covered(backend_base_url):
    """universe 内部圆柱 + 外围 void 填满格元盒 → covered=true + detailViable=true。"""
    resp = _post(backend_base_url, "/api/validate-universe-coverage",
                 {**COV_DECK, "universe": "5"})
    assert resp.get("status") == "ok", resp
    assert resp.get("kind") == "leaf", resp
    assert resp.get("covered") is True, resp
    assert resp.get("detailViable") is True, resp
    assert resp.get("uncoveredFraction", 1) < 0.01, resp


def test_http_validate_universe_coverage_empty(backend_base_url):
    """universe 无栅元定义 → kind=empty + covered=false + 不判定。"""
    resp = _post(backend_base_url, "/api/validate-universe-coverage",
                 {**COV_DECK, "universe": "99"})
    assert resp.get("status") == "ok", resp
    assert resp.get("kind") == "empty", resp
    assert resp.get("covered") is False, resp
    assert resp.get("detailViable") is False, resp


def _stl_triangle_count(raw: bytes) -> int:
    """STL 字节 → 三角形数（ASCII 'facet' 计数 / 二进制头 offset80 uint32）。"""
    if not raw:
        return 0
    if b"facet" in raw:
        return raw.count(b"facet")
    if len(raw) >= 84:
        import struct
        return struct.unpack("<I", raw[80:84])[0]
    return 0


def test_http_preview_lattice_universe_stl_nonempty(backend_base_url):
    """回归：圆柱格元（燃料棒/导向管/仪表管）裁剪后 STL 非空。

    致命缺陷根因：_build_one_universe 曾把 6 个盒平面塞进 cell 表达式做 CSG 交集，
    FreeCAD/OCC 对「圆柱（C/CZ）∩ 平行轴平面（PX/PY）」的布尔 common 恒空 →
    84B/0 三角形 STL。修复=格元盒改用单个 RPP 宏体（-num 盒内半空间）做
    solid-solid 盒裁剪。本用例用含实心圆柱（u1 `-5`）与环形（u2 `5 -6`）的
    LATTICE_DECK 直验：每个 universe cell 的 STL 三角形数必须 > 0。
    FreeCAD 不可用时 skip（universe STL 依赖 FreeCAD 子进程）。
    """
    try:
        from app.freecad_locator import bin_dir
    except ImportError:
        bin_dir = None
    if not bin_dir:
        pytest.skip("FreeCAD 不可用，跳过 universe STL 非空直验")
    import base64
    resp = _post(backend_base_url, "/api/preview-lattice", LATTICE_DECK)
    assert resp.get("status") == "ok", resp
    lattices = resp.get("lattices", [])
    assert len(lattices) == 1, resp
    universes = lattices[0].get("universes", {})
    assert universes, f"universes 为空（FreeCAD 可用但未产出任何 STL）: {resp}"
    for u in sorted(universes):
        cells = universes[u]
        assert cells, f"universe u{u} 无 STL"
        for cell_num in sorted(cells):
            raw = base64.b64decode(cells[cell_num])
            tri = _stl_triangle_count(raw)
            assert tri > 0, (
                f"universe u{u} cell {cell_num} STL 空（{len(raw)}B/0 三角形）——"
                "格元盒裁剪仍产出空几何")


# 容器 cell 带 MCNP cell 补集 `#n`（如核心挖控制叶片 `#15 #16 #17 #18`）时，
# _build_one_universe 把 container_expr 当作布尔裁剪表达式追加进 universe pin cell，
# FreeCAD 解析不了 `#` → 整次 build 失败、所有 universe STL 变空（前端回退方块占位）。
# 回归：_lattice_container_expr 必须剥离 `#` 补集 token，容器只保留曲面边界。
# `#99` 引用未定义 cell = 最简触发：补集 cell 不在 universe 构建集合时构建失败。
LATTICE_CONTAINER_HASH_DECK = {
    "surfaces": "1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 pz -1\n6 pz 1\n7 cz 0.3\n9 px 0",
    "tr_cards": "",
    "cells": [
        {"kind": "cell", "cell": {"number": 20, "material": "0", "density": "",
                                  "surface_expr": "1 -2 3 -4 5 -6 #99", "u": "",
                                  "fill": "4", "lat": "", "trcl": "", "render": True,
                                  "fill_grid": ""}},
        {"kind": "cell", "cell": {"number": 19, "material": "0", "density": "",
                                  "surface_expr": "1 -2 3 -4 5 -6", "u": "4",
                                  "fill": "0:1 0:1 0:0", "lat": "1", "trcl": "", "render": True,
                                  "fill_grid": json.dumps(LATTICE_FILL_GRID)}},
        {"kind": "cell", "cell": {"number": 1, "material": "1", "density": "-1.0",
                                  "surface_expr": "-7", "u": "1", "render": True,
                                  "fill_grid": ""}},
    ],
}


def test_http_preview_lattice_universe_stl_nonempty_container_hash(backend_base_url):
    """回归：容器 cell 含 `#` 补集（如核心挖叶片）时 universe STL 仍非空。

    致命缺陷根因：_lattice_container_expr 返回的容器 cell surface_expr 若含 MCNP cell
    补集运算符 `#n`（如 `... #15 #16 #17 #18`），_build_one_universe 把它拼进 pin cell
    表达式做布尔裁剪，FreeCAD 解析不了指向未定义 cell 的 `#` → 整次 build 失败 → 所有
    universe STL 变空（前端回退 BoxGeometry 方块）。修复=_lattice_container_expr 剥离
    `#` 补集 token。本用例构造容器边界含 `#99`（补集引用未定义 cell）直验 universe STL 非空。
    FreeCAD 不可用时 skip。
    """
    try:
        from app.freecad_locator import bin_dir
    except ImportError:
        bin_dir = None
    if not bin_dir:
        pytest.skip("FreeCAD 不可用，跳过 universe STL 非空直验")
    import base64
    resp = _post(backend_base_url, "/api/preview-lattice", LATTICE_CONTAINER_HASH_DECK)
    assert resp.get("status") == "ok", resp
    lattices = resp.get("lattices", [])
    assert len(lattices) == 1, resp
    universes = lattices[0].get("universes", {})
    assert universes, f"universes 为空（#补集容器导致 STL 全空）: {resp}"
    for u in sorted(universes):
        cells = universes[u]
        assert cells, f"universe u{u} 无 STL"
        for cell_num in sorted(cells):
            raw = base64.b64decode(cells[cell_num])
            tri = _stl_triangle_count(raw)
            assert tri > 0, (
                f"universe u{u} cell {cell_num} STL 空（{len(raw)}B/0 三角形）——"
                "容器 # 补集仍被塞进裁剪表达式")
