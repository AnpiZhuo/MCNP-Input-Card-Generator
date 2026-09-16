"""源抽样编排单测：sample_source（契约 source-demo-visualization.md §1 模块 B）。

覆盖位置四路（点源/多点/笛卡尔/球柱）+ SUR/CEL 几何判定 + 方向/能量/权重 +
DS 依赖链 + MCNP 语义错误。全部固定 seed 保证确定性。
"""
import collections
import math
import random

import numpy as np
import pytest

from app.generator.source_sampler import sample_source


def _ok(r):
    assert r["status"] == "ok", r.get("error")
    return r


# ── 点源 ──────────────────────────────────────────────────

def test_point_source():
    r = _ok(sample_source({"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0",
                           "sdef_erg": "14"}, [], n_particles=100, seed=1))
    assert len(r["particles"]) == 100
    p = r["particles"][0]
    assert (p["x"], p["y"], p["z"]) == (0.0, 0.0, 0.0)
    assert p["energy"] == 14.0
    # 方向单位矢量
    n = math.sqrt(p["dx"] ** 2 + p["dy"] ** 2 + p["dz"] ** 2)
    assert abs(n - 1.0) < 1e-9


def test_direction_isotropic():
    r = _ok(sample_source({"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0",
                           "sdef_erg": "14"}, [], n_particles=2000, seed=2))
    # 各向同性：方向均值 ≈ 0
    mx = sum(p["dx"] for p in r["particles"]) / 2000
    my = sum(p["dy"] for p in r["particles"]) / 2000
    mz = sum(p["dz"] for p in r["particles"]) / 2000
    assert abs(mx) < 0.05 and abs(my) < 0.05 and abs(mz) < 0.05


# ── 多点源 ────────────────────────────────────────────────

def test_multi_point_source():
    r = _ok(sample_source(
        {"sdef_pos_x": "D1", "sdef_pos_y": "D1", "sdef_pos_z": "D1", "sdef_erg": "14"},
        [{"id": 1, "si": {"type": "L", "values": ["0", "0", "0", "10", "10", "10"]},
          "sp": {"type": "D", "values": ["0.3", "0.7"]}}],
        n_particles=1000, seed=1))
    cnt = collections.Counter((round(p["x"]), round(p["y"]), round(p["z"])) for p in r["particles"])
    assert abs(cnt[(0, 0, 0)] / 1000 - 0.3) < 0.05
    assert abs(cnt[(10, 10, 10)] / 1000 - 0.7) < 0.05


# ── 笛卡尔盒体 ────────────────────────────────────────────

def test_cartesian_box():
    r = _ok(sample_source(
        {"sdef_pos_x": "D1", "sdef_pos_y": "D2", "sdef_pos_z": "D3", "sdef_erg": "14"},
        [{"id": 1, "si": {"type": "H", "values": ["-2", "2"]}},
         {"id": 2, "si": {"type": "H", "values": ["-2", "2"]}},
         {"id": 3, "si": {"type": "H", "values": ["-2", "2"]}}],
        n_particles=1000, seed=1))
    for ax in ("x", "y", "z"):
        vals = [p[ax] for p in r["particles"]]
        assert min(vals) >= -2 and max(vals) <= 2


# ── 球体 / 圆柱 ───────────────────────────────────────────

def test_sphere_shell():
    # RAD=2 固定 → 球壳（所有点 |r|=2）
    r = _ok(sample_source({"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0",
                           "sdef_rad": "2", "sdef_erg": "14"}, [], n_particles=200, seed=1))
    for p in r["particles"]:
        d = math.sqrt(p["x"] ** 2 + p["y"] ** 2 + p["z"] ** 2)
        assert abs(d - 2.0) < 1e-9


def test_sphere_solid_volume():
    # RAD=D1 + SI 0 2（默认幂律 a=2 → 体积均匀）
    r = _ok(sample_source(
        {"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0", "sdef_rad": "D1", "sdef_erg": "14"},
        [{"id": 1, "si": {"type": "", "values": ["0", "2"]}}], n_particles=3000, seed=1))
    dists = [math.sqrt(p["x"] ** 2 + p["y"] ** 2 + p["z"] ** 2) for p in r["particles"]]
    assert max(dists) <= 2.0
    # 体积均匀：r^3 均匀（外层占比大）
    outer = sum(1 for d in dists if d > 1.0) / 3000
    assert 0.82 < outer < 0.92  # 期望 (8-1)/8 = 0.875


def test_cylinder():
    r = _ok(sample_source(
        {"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0",
         "sdef_axs": "0 0 1", "sdef_rad": "2", "sdef_ext": "D2", "sdef_erg": "14"},
        [{"id": 2, "si": {"type": "", "values": ["-5", "5"]}}], n_particles=500, seed=1))
    for p in r["particles"]:
        rad = math.sqrt(p["x"] ** 2 + p["y"] ** 2)
        assert rad <= 2.0
        assert -5 <= p["z"] <= 5


# ── 能量谱 / 依赖链 ────────────────────────────────────────

def test_energy_spectrum():
    r = _ok(sample_source(
        {"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0", "sdef_erg": "D2"},
        [{"id": 2, "si": {"type": "L", "values": ["1", "2", "14"]},
          "sp": {"type": "D", "values": ["1", "1", "1"]}}],
        n_particles=3000, seed=1))
    es = collections.Counter(round(p["energy"]) for p in r["particles"])
    assert all(0.28 < es[v] / 3000 < 0.38 for v in (1, 2, 14))


def test_erg_depends_on_pos():
    # ERG=FPOS D2：位置 0 → 分布 3，位置 1 → 分布 4
    r = _ok(sample_source(
        {"sdef_pos_x": "D1", "sdef_pos_y": "D1", "sdef_pos_z": "D1", "sdef_erg": "FPOS D2"},
        [{"id": 1, "si": {"type": "L", "values": ["0", "0", "0", "10", "10", "10"]},
          "sp": {"type": "D", "values": ["1", "1"]}},
         {"id": 2, "ds": {"type": "S", "distributionIds": ["3", "4"]}},
         {"id": 3, "si": {"type": "L", "values": ["1"]}},
         {"id": 4, "si": {"type": "L", "values": ["14"]}}],
        n_particles=1000, seed=1))
    for p in r["particles"]:
        if p["x"] == 0:
            assert p["energy"] == 1.0
        else:
            assert p["energy"] == 14.0


# ── 固定方向 ──────────────────────────────────────────────

def test_fixed_direction():
    r = _ok(sample_source(
        {"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0",
         "sdef_dir": "1", "sdef_vec": "0 0 1", "sdef_erg": "14"}, [], n_particles=50, seed=1))
    for p in r["particles"]:
        assert abs(p["dx"]) < 1e-9 and abs(p["dy"]) < 1e-9 and abs(p["dz"] - 1) < 1e-9


# ── SUR / CEL 几何判定 ────────────────────────────────────

def _geom():
    def sphere_field(x, y, z):
        return (x ** 2 + y ** 2 + z ** 2) <= 1.0
    return {
        "cells": {1: {"field": sphere_field, "aabb": ((-1, -1, -1), (1, 1, 1))}},
        "surfaces": {5: {"type": "SO", "params": [2.0],
                         "field": lambda x, y, z: x ** 2 + y ** 2 + z ** 2 - 4}},
    }


def _plane_geom():
    """PX 5 平面源几何（C810 3-58 平面源：POS 在面上，位置 = POS + RAD·面内方向）。"""
    return {
        "cells": {},
        "surfaces": {5: {"type": "PX", "params": [5.0], "field": None,
                         "rotate": None, "origin": (0.0, 0.0, 0.0)}},
    }


def _sphere_geom():
    """球面 S 0 0 0 10（法线 = 径向向外）。"""
    return {
        "cells": {},
        "surfaces": {6: {"type": "S", "params": [0.0, 0.0, 0.0, 10.0], "field": None,
                         "rotate": None, "origin": (0.0, 0.0, 0.0)}},
    }


def test_cel_uniform():
    r = _ok(sample_source({"sdef_cel": "1", "sdef_erg": "14"}, [], geometry=_geom(),
                          n_particles=300, seed=1))
    for p in r["particles"]:
        assert p["x"] ** 2 + p["y"] ** 2 + p["z"] ** 2 <= 1.0


def test_surface_sphere():
    r = _ok(sample_source({"sdef_sur": "5", "sdef_erg": "14"}, [], geometry=_geom(),
                          n_particles=200, seed=1))
    for p in r["particles"]:
        d = math.sqrt(p["x"] ** 2 + p["y"] ** 2 + p["z"] ** 2)
        assert abs(d - 2.0) < 1e-6


# ── 面源语义（C810 3-58 / Table 3.3）──────────────────────

def test_plane_source_position_on_pos_rad_circle():
    """平面源：位置必须**在 POS 所在的面上**、且落在 POS+RAD 的圆内（面内均匀 a=1）。

    旧实现：PX 直接 `y,z ~ U(-1000,1000)` —— RAD/POS 全被忽略（实测 y≈-680）。
    """
    r = _ok(sample_source(
        {"sdef_sur": "5", "sdef_pos_x": "5", "sdef_pos_y": "0", "sdef_pos_z": "0",
         "sdef_rad": "D1", "sdef_erg": "14"},
        [{"id": 1, "si": {"type": "", "values": ["0", "3"]},
          "sp": {"type": "", "values": [], "fnCode": "-21", "fnParams": ["1"]}}],
        geometry=_plane_geom(), n_particles=800, seed=11))
    rs = []
    for p in r["particles"]:
        assert abs(p["x"] - 5.0) < 1e-9, "平面源位置必须落在 x=5 面上"
        rs.append(math.hypot(p["y"], p["z"]))
    assert max(rs) <= 3.0 + 1e-9, "面内半径不得超过 RAD"
    # 面内均匀（a=1）：P(r>1.5) = (9-2.25)/9 = 0.75
    frac = sum(1 for v in rs if v > 1.5) / len(rs)
    assert 0.68 < frac < 0.82


def test_plane_source_direction_around_surface_normal():
    """面源方向：VEC 缺省 = 面法线（PX → ±X），且 DIR 缺省 = 余弦分布 p(μ)=2μ（全朝外）。

    旧实现：轴回落 `(0,0,1)` 且忽略 NRM ⇒ 方向在 ±X 上双向、且与 NRM 无关（实测逐位相同）。
    """
    for nrm, sign in (("", 1.0), ("-1", -1.0)):
        r = _ok(sample_source(
            {"sdef_sur": "5", "sdef_pos_x": "5", "sdef_pos_y": "0", "sdef_pos_z": "0",
             "sdef_rad": "1", "sdef_nrm": nrm, "sdef_erg": "14"},
            [], geometry=_plane_geom(), n_particles=400, seed=3))
        dx = [p["dx"] for p in r["particles"]]
        assert all(sign * v > 0 for v in dx), "余弦分布必须全在半空间（NRM 定符号）"
        # 余弦分布 p(μ)=2μ ⇒ <μ>=2/3
        assert abs(sum(dx) / len(dx) - sign * 2.0 / 3.0) < 0.06


def test_sphere_source_direction_outward_by_default():
    """球面源 DIR 缺省 = 余弦分布绕**外法线**（C810 3-58）⇒ 方向·径向 ≥ 0。"""
    r = _ok(sample_source(
        {"sdef_sur": "6", "sdef_pos_x": "10", "sdef_pos_y": "0", "sdef_pos_z": "0",
         "sdef_erg": "14"}, [], geometry=_sphere_geom(), n_particles=400, seed=5))
    for p in r["particles"]:
        m = math.sqrt(p["x"] ** 2 + p["y"] ** 2 + p["z"] ** 2)
        cos = (p["x"] * p["dx"] + p["y"] * p["dy"] + p["z"] * p["dz"]) / m
        assert cos >= 0.0, "默认余弦分布不得朝球心飞"


def test_surface_source_cylinder_reports_semantics():
    """柱面源：C810 3-58「Cylindrical surface sources must be specified as degenerate
    volume sources」⇒ 明确报错并给出可操作提示（不得静默乱撒）。"""
    geo = {"cells": {}, "surfaces": {7: {"type": "CX", "params": [0.0, 0.0, 3.0],
                                         "field": None, "rotate": None,
                                         "origin": (0.0, 0.0, 0.0)}}}
    r = sample_source({"sdef_sur": "7", "sdef_erg": "14"}, [], geometry=geo,
                      n_particles=10, seed=1)
    assert r["status"] == "error"
    assert "退化体源" in r["error"]


def test_sdef_tr_transforms_position_and_direction():
    """SDEF TR=n（C810 Table 3.3：源变换）：抽出的位置与方向都要按 TR 卡变换。

    旧实现完全不读 `sdef_tr` ⇒ 源位置/方向留在未变换的坐标系里。
    """
    geom = _plane_geom()
    geom["trCards"] = {"2": {"translate": [0.0, 0.0, 100.0],
                             "rotate": [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]}}
    r = _ok(sample_source(
        {"sdef_sur": "5", "sdef_pos_x": "5", "sdef_pos_y": "0", "sdef_pos_z": "0",
         "sdef_rad": "1", "sdef_tr": "2", "sdef_erg": "14"},
        [], geometry=geom, n_particles=50, seed=1))
    for p in r["particles"]:
        # Rᵀ·(5,y,z) + (0,0,100) = (y, 5, z) + (0,0,100)（R = [[0,1,0],[-1,0,0],[0,0,1]]）
        assert abs(p["x"]) <= 1.0 + 1e-9 and abs(p["y"] - 5.0) < 1e-9, "位置必须经 TR 旋转+平移"
        assert p["z"] > 99.0
        # 方向也要转（PX 面法线 +X → 世界 +Y）
        assert p["dy"] > 0.0, "方向必须经 TR 旋转（旧实现完全忽略 TR）"


# ── SP V / SI S 分布号 0 / SDEF TR=Dn ─────────────────────

def test_sp_v_samples_cells_by_volume():
    """C810 3-64 `SP V`：`Probability is proportional to cell volume`（CEL 源）。

    两个栅元体积比 1:7 ⇒ 抽到栅元 1 的概率应≈1/8。
    """
    def shell_field(lo2, hi2):
        def f(x, y, z):
            r2 = x ** 2 + y ** 2 + z ** 2
            return (r2 >= lo2) & (r2 <= hi2)
        return f
    geo = {
        "cells": {1: {"field": shell_field(0.0, 1.0), "aabb": ((-1, -1, -1), (1, 1, 1))},
                  2: {"field": shell_field(1.0, 4.0), "aabb": ((-2, -2, -2), (2, 2, 2))}},
        "cellVolumes": {1: 4.0 / 3.0 * math.pi, 2: 28.0 / 3.0 * math.pi},
    }
    r = _ok(sample_source(
        {"sdef_cel": "1", "sdef_erg": "D1"},
        [{"id": 1, "si": {"type": "L", "values": ["1", "2"]},
          "sp": {"type": "V", "values": []}}],
        geometry=geo, n_particles=4000, seed=4))
    # V 的权重体现在**抽到哪个栅元号**上（体积 1:7 ⇒ 抽到 1 的概率≈1/8）
    small = sum(1 for p in r["particles"] if p["energy"] == 1.0)
    assert abs(small / 4000 - 0.125) < 0.03, f"体积比 1:7 ⇒ 栅元1占比应≈0.125，实得 {small/4000:.3f}"


def test_sp_v_without_volume_reports_error():
    """缺栅元体积 ⇒ 报错（不是静默等概率）。"""
    geo = {"cells": {1: {"field": lambda x, y, z: x * 0 <= 1e9,
                         "aabb": ((-1, -1, -1), (1, 1, 1))}},
           "cellVolumes": {}}
    r = sample_source({"sdef_cel": "1", "sdef_erg": "D1"},
                      [{"id": 1, "si": {"type": "L", "values": ["1"]},
                        "sp": {"type": "V", "values": []}}],
                      geometry=geo, n_particles=10, seed=1)
    assert r["status"] == "error" and "体积" in r["error"]


def test_si_s_zero_uses_sdef_field_value():
    """C810 3-64：分布号 0 ⇒ **该变量默认值**；能读到 SDEF 字面值就用它（不是硬编码 14）。"""
    from app.generator.distributions import DistributionSampler
    entry = {"id": 1, "si": {"type": "S", "values": ["0"]},
             "sp": {"type": "D", "values": ["1"]}}
    s = DistributionSampler([entry])
    assert s.sample(1, random.Random(1), var="ERG", sdef_fields={"sdef_erg": "2.5"}) == 2.5
    assert s.sample(1, random.Random(1), var="WGT", sdef_fields={"sdef_wgt": "7"}) == 7.0
    # 读不到 → 退回 Table 3.3 静态默认
    assert s.sample(1, random.Random(1), var="ERG", sdef_fields={}) == 14.0


def test_sdef_tr_distribution_applies_sampled_transform():
    """C810 3-64/3-66：`TR=Dn` 走**变换分布**（SI L 列 TR 号，SP 选概率）——旧实现忽略。"""
    geo = _plane_geom()
    geo["trCards"] = {
        "2": {"translate": [0.0, 0.0, 100.0],
              "rotate": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
        "3": {"translate": [0.0, 0.0, 200.0],
              "rotate": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
    }
    r = _ok(sample_source(
        {"sdef_sur": "5", "sdef_pos_x": "5", "sdef_pos_y": "0", "sdef_pos_z": "0",
         "sdef_rad": "1", "sdef_tr": "D9", "sdef_erg": "14"},
        [{"id": 9, "si": {"type": "L", "values": ["2", "3"]},
          "sp": {"type": "D", "values": ["1", "1"]}}],
        geometry=geo, n_particles=200, seed=6))
    zs = [p["z"] for p in r["particles"]]
    assert all(z > 99.0 for z in zs), "TR=Dn 必须真的生效（旧实现忽略 sdef_tr）"
    assert any(z > 199.0 for z in zs) and any(z < 199.0 for z in zs), "两个 TR 号都要被抽到"


def test_surface_source_ext_single_si_symmetric():
    """C810 3-66 规则 5：EXT 的 `SI x` + `SP −31` ⇒ 等价 `SI −x x`（负半轴必须保留）。"""
    r = _ok(sample_source(
        {"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0", "sdef_axs": "0 0 1",
         "sdef_rad": "3", "sdef_ext": "D2", "sdef_erg": "14"},
        [{"id": 2, "si": {"type": "", "values": ["5"]},
          "sp": {"type": "", "values": [], "fnCode": "-31", "fnParams": ["0"]}}],
        n_particles=1500, seed=9))
    zs = [p["z"] for p in r["particles"]]
    assert max(zs) <= 5.0 and min(zs) < 0.0, "对称区间才会有负 z（旧实现恒 0≤z≤5）"


# ── 错误 ───────────────────────────────────────────────────

def test_error_undefined_cell():
    r = sample_source({"sdef_cel": "99", "sdef_erg": "14"}, [], geometry=_geom(),
                      n_particles=10, seed=1)
    assert r["status"] == "error"
    assert "CEL=99" in r["error"]


def test_error_undefined_surface():
    r = sample_source({"sdef_sur": "99", "sdef_erg": "14"}, [], geometry=_geom(),
                      n_particles=10, seed=1)
    assert r["status"] == "error"


def test_error_undefined_distribution():
    r = sample_source({"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0",
                       "sdef_erg": "D7"}, [], n_particles=10, seed=1)
    assert r["status"] == "error"
    assert "D7" in r["error"]
