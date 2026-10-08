"""API 份额语义测试 —— /api/expand-formula 的 is_weight 参数（质量份额 / 原子份额）。

背景（2026-08-14 引入 is_weight；2026-09 修正口径）：
  - handler 自行按定义展开化学式（`_expand_formula_member`，见 gui/backend/api_server.py），
    **不再**复用 `pymcnp.inp.M_0.from_formula` 的 is_weight 分支——该函数两个分支取的是
    同一个量（molmass `Composition.fraction` == `mass/formula.mass`，均为质量分数），
    is_weight=False 只是把质量份额翻成正号，并非原子份额；
  - 默认 is_weight=True → 质量份额（MCNP 约定 负=质量），元素内同位素按质量加权；
  - is_weight=False → 原子份额（MCNP 约定 正=原子），元素内同位素按原子丰度。

覆盖：
  ① 默认（不传 is_weight）= 质量份额负号（向后兼容）；
  ② is_weight=false = 原子份额正号；
  ③ 物理正确性（本次修正的核心，旧断言「原子 == 负质量」是错的）：
     H2O 原子模式 H:O = 2:1、质量模式 H 0.111898 / O 0.888102；
     元素内同位素质量加权：天然硼 B-10 质量份额 0.184309（原子模式 0.199）；
     D2O 只出 H-2（0.201133），不出 H-1；
  ④ 两种模式份额绝对值之和均为 1（归一化不回归）；
  ⑤ 显式 is_weight=true == 默认（加性兼容）；
  ⑥ null / 字符串 "false" 防御性布尔解析（输入校验）；
  ⑦ 空公式仍走既有错误路径（is_weight 扩展不破坏错误响应）。

铁律：本文件【不 import】gui.backend.api_server（模块级 pyvista/FreeCAD 探测）。
HTTP 往返用子进程跑 api_server.py，fixture `backend_base_url` 在
`tests/integration/conftest.py`（**挑空闲端口 + 核对端口归属**：原先各文件写死 5001，
会跟常驻的打包版抢端口，"连上别人的后端"照样报绿 —— 见 PROJECT_MEMORY §6 / S9.6）。
"""
import json
import urllib.error
import urllib.request

import pytest


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


def _by_zaid(nuclides: list[dict]) -> dict[str, float]:
    return {n["zaid"]: float(n["fraction"]) for n in nuclides}


def _by_element(nuclides: list[dict]) -> dict[int, float]:
    """按元素 Z 汇总份额绝对值（ZAID 去掉末 3 位质量数）。"""
    out: dict[int, float] = {}
    for n in nuclides:
        z = int(n["zaid"][:-3]) if len(n["zaid"]) > 3 else int(n["zaid"])
        out[z] = out.get(z, 0.0) + abs(float(n["fraction"]))
    return out


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


# ── ③ 物理正确性（核心：原子份额不是质量份额取反）────────────
def test_expand_formula_mass_mode_water_matches_mass_fractions(backend_base_url):
    """质量模式 H2O：H 总量 0.111898、O 总量 0.888102（质量分数，非原子比）。"""
    el = _by_element(_expand(backend_base_url, {"formula": "H2O"}))
    assert el[1] == pytest.approx(0.111898, abs=2e-5), f"H 质量份额 {el[1]}"
    assert el[8] == pytest.approx(0.888102, abs=2e-5), f"O 质量份额 {el[8]}"


def test_expand_formula_atomic_mode_water_is_atom_ratio_2_to_1(backend_base_url):
    """原子模式 H2O：H 0.666667 / O 0.333333（原子比 2:1）。

    回归防线：修正前该模式返回的是质量份额数值（H 0.1119 / O 0.8859，
    H:O = 0.126），MCNP 按原子份额读入会得到严重错误的材料组成。
    """
    el = _by_element(_expand(backend_base_url, {"formula": "H2O", "is_weight": False}))
    assert el[1] == pytest.approx(2.0 / 3.0, abs=2e-5), f"H 原子份额 {el[1]}"
    assert el[8] == pytest.approx(1.0 / 3.0, abs=2e-5), f"O 原子份额 {el[8]}"
    assert el[1] / el[8] == pytest.approx(2.0, rel=1e-3), "H:O 原子比应为 2:1"


def test_expand_formula_isotopes_are_mass_weighted_in_mass_mode(backend_base_url):
    """质量模式下元素内同位素按质量加权：天然硼 B-10 = 0.184309（非原子丰度 0.199）。

    回归防线：修正前把 NIST 原子丰度直接当质量份额用（B-10 +8.0%、Li-6 +15.4%、
    H-2 −50%），对含硼/含锂热中子吸收材料是非保守偏差。
    """
    mass = _by_zaid(_expand(backend_base_url, {"formula": "B: 1"}))
    assert mass["5010"] == pytest.approx(-0.184309, abs=1e-5), f"B-10 质量份额 {mass['5010']}"
    assert mass["5011"] == pytest.approx(-0.815691, abs=1e-5), f"B-11 质量份额 {mass['5011']}"

    atomic = _by_zaid(_expand(backend_base_url, {"formula": "B: 1", "is_weight": False}))
    assert atomic["5010"] == pytest.approx(0.199, abs=1e-5), f"B-10 原子份额 {atomic['5010']}"


def test_expand_formula_deuterium_species_keeps_h2_only(backend_base_url):
    """D2O：只出 H-2（质量份额 0.201133），不出 H-1（molmass 把 D 记作元素 '2H'）。"""
    nuclides = _expand(backend_base_url, {"formula": "D2O"})
    d = _by_zaid(nuclides)
    assert "1002" in d, f"D2O 应含 H-2: {nuclides}"
    assert "1001" not in d, f"D2O 不应含 H-1: {nuclides}"
    assert d["1002"] == pytest.approx(-0.201133, abs=1e-5), f"D 质量份额 {d['1002']}"


# ── ④ 份额绝对值之和 = 1（归一化不回归）─────────────────────
@pytest.mark.parametrize("is_weight", [True, False])
def test_expand_formula_fractions_sum_to_one(backend_base_url, is_weight):
    """两种模式下 |Σ fraction| = 1（abs-sum 归一行为与现状一致）。"""
    nuclides = _expand(backend_base_url, {"formula": "N2: 0.755, O2: 0.232, Ar: 0.013",
                                          "is_weight": is_weight})
    assert sum(abs(float(n["fraction"])) for n in nuclides) == pytest.approx(1.0, abs=1e-5)


# ── ⑤ 显式 is_weight=true == 默认（加性兼容）────────────────
def test_expand_formula_explicit_true_equals_default(backend_base_url):
    """显式传 is_weight=true 应与不传完全一致（向后兼容不漂移）。"""
    default = _expand(backend_base_url, {"formula": "H2O"})
    explicit = _expand(backend_base_url, {"formula": "H2O", "is_weight": True})
    assert default == explicit


# ── ⑥ 防御性布尔解析（null / 字符串 "false"）────────────────
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


# ── ⑦ 空公式错误路径不回归 ────────────────────────────────
def test_expand_formula_empty_formula_still_errors(backend_base_url):
    """空化学式仍返回 500 error（is_weight 扩展不破坏既有错误路径）。"""
    status, body = _post(backend_base_url, "/api/expand-formula", {"formula": ""})
    assert status == 500
    assert body.get("status") == "error"
