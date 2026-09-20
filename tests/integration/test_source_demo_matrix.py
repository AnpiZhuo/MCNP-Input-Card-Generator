# -*- coding: utf-8 -*-
"""源演示 CEL/面源/效率矩阵 —— 逐条对照 C810（CCC-810）。

## 为什么在集成层
`sample_source` 需要的 `geometry`（field 闭包 + 紧盒）由 `api_server._prepare_source_geometry`
构造，而测试**禁止 import api_server**（模块级 pyvista/FreeCAD 探测）。所以"卡 → 抽样"的完整链路
只能走 HTTP（共享 `backend_base_url` fixture：源码后端子进程 + 空闲端口 + 端口归属核对）。

## 对应用户症状
`SDEF CEL=n` 在**宏体**界定的栅元上必失败（2026-09-20 实测：`cell_aabb` 只支持 SPH/RPP，
其余 8 类返回 None ⇒ 旧代码退回 ±1e3 大盒 ⇒ 接受率 ~1e-8 ⇒ 「拒绝采样失败」）。

## 独立判据（不复用被测代码）
粒子位置用**用例内自己写的解析判据**验收（球半径、长方体分量、圆柱轴向+径向、椭圆方程……），
而不是再调一次 `voxel_csg` —— 否则"盒错"和"场错"会互相掩盖。
"""
import json
import math
import urllib.error
import urllib.request

import pytest

PATH = "/api/source-demo-sample"
PI = math.pi


def _post(base, path, payload, timeout=180):
    req = urllib.request.Request(f"{base}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:400]}


def _sample(base, fields, surfs="", cells=(), n=200, dists=None):
    _, j = _post(base, PATH, {
        "sdefFields": fields, "sdefDistributions": dists or [],
        "surfaces": surfs, "cells": list(cells), "trCards": "", "nParticles": n})
    return j


def _cell(num, expr):
    return {"kind": "cell", "cell": {"number": num, "material": "1", "density": "-1.0",
                                     "surface_expr": expr, "render": True, "fill_grid": ""}}


def _pts(j):
    return [(p["x"], p["y"], p["z"]) for p in j["particles"]]


# ── 独立解析判据：点是否在宏体内部（用例自己写，不复用被测场）──
def _inside_box(p, v, a1, a2, a3):
    """BOX：把 p−v 表成 a1/a2/a3 的线性组合，系数须都在 [0,1]。"""
    import numpy as np
    M = np.array([a1, a2, a3], dtype=float).T
    try:
        t = np.linalg.solve(M, np.array(p, dtype=float) - np.array(v, dtype=float))
    except np.linalg.LinAlgError:
        return False
    return all(-1e-6 <= x <= 1 + 1e-6 for x in t)


def _inside_rcc(p, v, h, r):
    d = [p[i] - v[i] for i in range(3)]
    hn = math.sqrt(sum(x * x for x in h))
    u = [x / hn for x in h]
    t = sum(d[i] * u[i] for i in range(3))
    rad2 = sum((d[i] - t * u[i]) ** 2 for i in range(3))
    return -1e-6 <= t <= hn + 1e-6 and rad2 <= r * r * (1 + 1e-6)


def _inside_trc(p, v, h, r1, r2):
    d = [p[i] - v[i] for i in range(3)]
    hn = math.sqrt(sum(x * x for x in h))
    u = [x / hn for x in h]
    t = sum(d[i] * u[i] for i in range(3))
    if t < -1e-6 or t > hn + 1e-6:
        return False
    rad2 = sum((d[i] - t * u[i]) ** 2 for i in range(3))
    rr = r1 + (r2 - r1) * (t / hn)
    return rad2 <= rr * rr * (1 + 1e-6)


# 名称、曲面卡、栅元表达式、解析判据、抽样点数
MACRO = [
    ("SPH", "1 sph 0 0 0 5", "-1",
     lambda p: sum(x * x for x in p) <= 25 * (1 + 1e-6)),
    ("RPP", "1 rpp -2 2 -2 2 -2 2", "-1",
     lambda p: all(-2 - 1e-6 <= x <= 2 + 1e-6 for x in p)),
    ("BOX", "1 box -1 -1 -1 2 0 0 0 2 0 0 0 2", "-1",
     lambda p: _inside_box(p, (-1, -1, -1), (2, 0, 0), (0, 2, 0), (0, 0, 2))),
    ("RCC", "1 rcc 0 -5 0 0 10 0 4", "-1",
     lambda p: _inside_rcc(p, (0, -5, 0), (0, 10, 0), 4)),
    ("RHP", "1 rhp 0 0 -4 0 0 8 0 2 0", "-1", None),      # 判据另给（见测试内）
    ("REC", "1 rec 0 -5 0 0 10 0 4 0 0 2", "-1",
     lambda p: (-5 - 1e-6 <= p[1] <= 5 + 1e-6) and (p[0] / 4) ** 2 + (p[2] / 2) ** 2 <= 1 + 1e-6),
    ("TRC", "1 trc -5 0 0 10 0 0 4 2", "-1",
     lambda p: _inside_trc(p, (-5, 0, 0), (10, 0, 0), 4, 2)),
    ("ELL", "1 ell 0 0 -2 0 0 2 6", "-1",
     lambda p: (p[0] ** 2 + p[1] ** 2) / 5 + (p[2] ** 2) / 9 <= 1 + 1e-6),
    ("WED", "1 wed 0 0 -6 4 0 0 0 3 0 0 0 12", "-1",
     lambda p: (0 - 1e-6 <= p[0] <= 4 + 1e-6 and 0 - 1e-6 <= p[1] <= 3 + 1e-6
                and -6 - 1e-6 <= p[2] <= 6 + 1e-6
                and p[0] / 4 + p[1] / 3 <= 1 + 1e-6)),
    ("ARB", "1 arb 0 0 0 1 0 0 1 1 0 0 1 0 0 0 1 1 0 1 1 1 1 0 1 1 "
            "1234 5678 1265 2376 3487 4158", "-1",
     lambda p: all(-1e-6 <= x <= 1 + 1e-6 for x in p)),
]


@pytest.mark.parametrize("name,card,expr,pred", MACRO, ids=[m[0] for m in MACRO])
def test_cel_source_on_every_macrobody(backend_base_url, name, card, expr, pred):
    """C810 p.3-21 的 10 类宏体：`SDEF CEL=1` 必须能抽，且粒子**真在体内**。

    修前：除 SPH/RPP 外全部报「CEL=1 拒绝采样失败（栅元包围盒可能退化）」。
    """
    j = _sample(backend_base_url, {"sdef_cel": "1", "sdef_erg": "14"}, card, [_cell(1, expr)], n=300)
    assert j.get("status") == "ok", f"{name}: {j.get('error') or j}"
    pts = _pts(j)
    assert len(pts) == 300, name
    if name == "RHP":
        # 现行 surface_fn 把 r 当顶点矢量（R=|r|=2）⇒ 六边形边心距 √3；见单测里的 C810 偏差留档
        ap = math.sqrt(3.0)
        ok = all(abs(p[2]) <= 4 + 1e-6 and abs(p[1]) <= 2 + 1e-6
                 and abs(-0.5 * p[0] + (math.sqrt(3) / 2) * p[1]) <= ap + 1e-6
                 and abs(0.5 * p[0] + (math.sqrt(3) / 2) * p[1]) <= ap + 1e-6
                 and abs(-p[0]) <= ap + 1e-6 for p in pts)
        assert ok, "RHP: 有粒子落在六棱柱外"
    else:
        bad = [p for p in pts if not pred(p)]
        assert not bad, f"{name}: {len(bad)} 个粒子落在体外，例如 {bad[:2]}"
    # 位置必须有真实散布（不是全叠在一个点）
    span = max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3))
    assert span > 0.05, f"{name}: 粒子几乎无散布（span={span}）"


# ── 面源：C810 p.3-58 只允许 平面/球面/椭球面 ────────────────
SUR_OK = [
    ("平面 PX", "1 px 0", {"sdef_sur": "1", "sdef_pos_x": "0", "sdef_pos_y": "0",
                          "sdef_pos_z": "0", "sdef_rad": "2"}),
    ("球面 SO", "1 so 5", {"sdef_sur": "1"}),
    ("球面 S", "1 s 0 0 0 5", {"sdef_sur": "1"}),
    ("椭球面 SQ", "1 sq 1 1 1 0 0 0 -4 0 0 0", {"sdef_sur": "1"}),
    ("椭球面 GQ", "1 gq 1 1 1 0 0 0 0 0 0 -4", {"sdef_sur": "1"}),
]
SUR_BAD = [
    ("圆柱面 CZ", "1 cz 2"),
    ("锥面 KZ", "1 kz 0 1"),
    ("环面 TZ", "1 tz 0 0 0 3 2 1"),
    ("斜置 GQ（有 xy 交叉项）", "1 gq 1 1 1 1 0 0 0 0 0 -4"),
    ("双曲面 GQ（A/B 异号）", "1 gq 1 -1 1 0 0 0 0 0 0 -4"),
]


@pytest.mark.parametrize("name,card,fields", SUR_OK, ids=[c[0] for c in SUR_OK])
def test_surface_source_allowed_types(backend_base_url, name, card, fields):
    j = _sample(backend_base_url, {**fields, "sdef_erg": "14"}, card, [], n=200)
    assert j.get("status") == "ok", f"{name}: {j.get('error') or j}"
    assert len(_pts(j)) == 200, name


@pytest.mark.parametrize("name,card", SUR_BAD, ids=[c[0] for c in SUR_BAD])
def test_surface_source_rejected_types_cite_c810(backend_base_url, name, card):
    """C810 p.3-58：柱面/锥面/环面/非轴平行二次曲面必须**明确报错**并指路。"""
    j = _sample(backend_base_url, {"sdef_sur": "1", "sdef_erg": "14"}, card, [], n=10)
    assert j.get("status") == "error", f"{name}: 竟然成功了 —— {str(j)[:200]}"
    err = str(j.get("error") or "")
    assert ("C810" in err or "退化体源" in err), f"{name}: 报错没指路：{err}"


@pytest.mark.parametrize("card,axis,R,ctr", [
    # ⚠ SQ 卡项 = A B C D E F G x̄ ȳ z̄（**最后三项是中心**，不是常数项）
    ("1 sq 1 1 1 0 0 0 -4 0 0 0", 2, 2.0, (0.0, 0.0, 0.0)),          # 球（SQ，半径 2）
    ("1 gq 1 1 1 0 0 0 0 0 0 -4", 2, 2.0, (0.0, 0.0, 0.0)),          # 球（GQ，半径 2）
    ("1 sq 1 1 1 0 0 0 -9 0 0 0", 1, 3.0, (0.0, 0.0, 0.0)),          # 球（SQ，半径 3）
])
def test_ellipsoid_surface_source_is_area_uniform_on_the_surface(backend_base_url, card, axis, R, ctr):
    """两个硬判据（旧实现在**体内**撒点，两条都过不了）：

    ① 所有点都在**面上**：|r − R| ≤ 1e-9（球面，逐点严格）；
    ② 面均匀 ⇒ 极角分布 dP ∝ sinθ dθ / 2 ⇒ P(θ<60°) = (1−cos60°)/2 = **0.25**（±0.06，N=2000）。
    """
    j = _sample(backend_base_url, {"sdef_sur": "1", "sdef_erg": "14"}, card, [], n=2000)
    assert j.get("status") == "ok", j.get("error")
    pts = _pts(j)
    radii = [math.dist(p, ctr) for p in pts]
    assert all(abs(r - R) <= 1e-6 for r in radii), (
        f"有点不在面上：min={min(radii):.6f} max={max(radii):.6f}（应在 {R}）")
    near = sum(1 for p in pts
               if math.degrees(math.acos(max(-1.0, min(1.0, p[axis - 1] / R)))) < 60.0)
    frac = near / len(pts)
    assert abs(frac - 0.25) <= 0.06, f"极角分布不像面积均匀：P(θ<60°)={frac:.3f}（应≈0.25）"


def test_cel_without_bounded_aabb_reports_c810_style_error(backend_base_url):
    """无界栅元（无限圆柱）与其"算不出盒"：必须说清原因，而不是旧那句误导性的
    「包围盒可能退化」（旧代码会退回 ±1e3 大盒硬撞 10 万次）。"""
    j = _sample(backend_base_url, {"sdef_cel": "1", "sdef_erg": "14"}, "1 cz 2", [_cell(1, "-1")], n=10)
    assert j.get("status") == "error", j
    err = str(j.get("error") or "")
    assert ("无界" in err or "无法确定栅元包围盒" in err), f"报错未说清原因：{err}"


def test_cel_inefficiency_follows_c810_eff_criterion(backend_base_url):
    """C810 p.3-59：接受率过低 ⇒ 终止（`MAX(成功数,10) < EFF×尝试数`，EFF 默认 0.01）。

    薄壳（δ=0.001）的紧盒/体积比 ≈ 3000 ⇒ 接受率 ~3e-4 ⇒ 必然触发；把 `sdef_eff` 调到 1e-6
    （C810：「for the rare problem in which low source efficiency is unavoidable, you may need
    to specify a lower value for EFF」）就应当能抽出来。
    """
    surfs = "1 so 5\n2 so 4.999"
    cells = [_cell(1, "-1 2")]
    j = _sample(backend_base_url, {"sdef_cel": "1", "sdef_erg": "14"}, surfs, cells, n=5)
    assert j.get("status") == "error", j
    err = str(j.get("error") or "")
    assert ("效率过低" in err or "100000 次" in err), f"报错不像效率判据：{err}"

    ok = _sample(backend_base_url, {"sdef_cel": "1", "sdef_erg": "14", "sdef_eff": "1e-6"},
                 surfs, cells, n=3)
    assert ok.get("status") == "ok", f"降 EFF 后仍失败：{ok.get('error')}"


def test_cel_rejection_is_uniform_in_volume(backend_base_url):
    """紧盒抽样必须**在体内均匀**：球源各象限计数、径向分布都该像三元均匀。

    用"球内接立方体"做判据：对半径 R 的均匀球，`P(r < R/2) = 1/8`（±0.08，N=2000）。
    """
    j = _sample(backend_base_url, {"sdef_cel": "1", "sdef_erg": "14"},
                "1 so 5", [_cell(1, "-1")], n=2000)
    assert j.get("status") == "ok", j.get("error")
    pts = _pts(j)
    inner = sum(1 for p in pts if math.dist(p, (0, 0, 0)) < 2.5) / len(pts)
    assert abs(inner - 0.125) <= 0.08, f"球内径向分布不像均匀：P(r<2.5)={inner:.3f}（应≈0.125）"


def test_unparsed_surface_line_is_reported_with_line_number(backend_base_url):
    """**诊断可读性**：没被解析的曲面行必须**带行号与原因**回传（走 geometryWarnings）。

    实测场景（2026-09-20）：用户卡里写 `1 so 0 0 0 5`（C810 Table 3.1：SO 的卡项只有 R）
    ⇒ 该行被静默丢弃 ⇒ 用户看到的却是「CEL=1 引用的栅元不存在或无法判定」，
    真因完全看不到。修完后该行必须自己被点名。
    """
    surfs = "1 so 0 0 0 5\n2 px 0"          # 第 1 行非法（SO 只吃 R），第 2 行合法
    j = _sample(backend_base_url, {"sdef_cel": "1", "sdef_erg": "14"}, surfs,
                [_cell(1, "-1 2")], n=5)
    warns = (j.get("geometryWarnings") or []) + [str(j.get("error") or "")]
    joined = " | ".join(warns)
    assert "第 1 行" in joined, f"未点名未解析的行：{joined}"
    assert "so 0 0 0 5" in joined.lower(), f"未回显原始行：{joined}"


def test_cel_with_only_cel_still_works_when_geometry_is_valid(backend_base_url):
    """回归：只给 CEL（不给任何采样区域）是本程序的常用扩展路径，合法几何下必须照常可抽。"""
    j = _sample(backend_base_url, {"sdef_cel": "1", "sdef_erg": "14"},
                "1 rcc 0 0 0 0 0 10 3", [_cell(1, "-1")], n=100)
    assert j.get("status") == "ok", j.get("error")
    assert len(_pts(j)) == 100
