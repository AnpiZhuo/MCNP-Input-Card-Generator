"""源抽样编排单测：sample_source（契约 source-demo-visualization.md §1 模块 B）。

覆盖位置四路（点源/多点/笛卡尔/球柱）+ SUR/CEL 几何判定 + 方向/能量/权重 +
DS 依赖链 + MCNP 语义错误。全部固定 seed 保证确定性。
"""
import collections
import math

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
