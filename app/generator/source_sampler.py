"""source_sampler — SDEF 源粒子抽样编排（source-demo-visualization 契约 §1 模块 B：深模块）。

接口（小接口 + 深实现）：:

    sample_source(sdef_fields, distributions, geometry=None, *, n_particles=500, seed=None) -> dict

输入 SDEF 字段 + v2 分布列表 + 几何原文（CEL/SUR 用），按 MCNP 语义抽样
``n_particles`` 个粒子：位置 / 方向 / 能量 / 权重 / 粒子类型。只表「从哪发出、
往哪飞」，不做输运。

位置分四路（互斥，按 MCNP 语义）：面源 SUR / 栅元均匀 CEL / 笛卡尔 X-Y-Z /
柱坐标 POS+RAD+EXT+AXS；方向（各向同性 / 固定 VEC / DIR 分布 / 面源余弦）；
能量（固定 / SI 谱 / 内置函数 / 依赖 POS 的 DS 链）。

错误：MCNP 语义错误（引用不存在 / 概率不匹配 / 边界非单调 / 几何无法判定）→
抛 ``SourceSamplingError``，由 ``sample_source`` 转 ``{"status":"error"}``，
不静默降级。
"""

from __future__ import annotations

import math
import random
import re

from .distributions import DistributionSampler, SourceSamplingError, _pick

# PAR → 渲染分组（与前端 trackColors.ts 的 particleGroup 对齐）
_PAR_GROUP = {
    "1": "n", "n": "n", "2": "p", "p": "p", "3": "e", "e": "e",
    "h": "h", "a": "a", "s": "s",
}

# F 依赖引用的父变量名 → SDEF 字段键（FPOS→pos, FERG→erg, FDIR→dir, FTME→tme）
_F_PARENT = {"POS": "pos", "ERG": "erg", "DIR": "dir", "TME": "tme", "WGT": "wgt"}


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _is_d_ref(v: str) -> bool:
    return bool(re.match(r"^D\d+$", (v or "").strip(), re.IGNORECASE))


class _Context:
    def __init__(self, fields: dict, sampler: DistributionSampler, geometry):
        self.f = fields or {}
        self.s = sampler
        self.geometry = geometry
        self._geom_helper = None

    # ── 字段读取 ─────────────────────────────────────────────
    def _v(self, key) -> str:
        return str(self.f.get(key) or "").strip()

    def _vec(self, key) -> tuple:
        toks = self._v(key).split()
        return tuple(_num(t, 0.0) for t in toks)

    # ── 单粒子 ───────────────────────────────────────────────
    def sample_one(self, rng, i: int) -> dict:
        par = self._par(rng)
        pos, pos_index = self._position(rng)
        erg = self._erg(rng, pos_index)
        sur = self._v("sdef_sur")
        is_surface = bool(sur and sur not in ("0",))
        dirv = self._direction(rng, pos, is_surface)
        wgt = self._wgt(rng)
        # 方向归一化（各向同性/固定 DIR 已单位化；VEC 参考系已折算）
        n = math.sqrt(sum(d * d for d in dirv))
        if n < 1e-15:
            dirv = (0.0, 0.0, 1.0)
            n = 1.0
        return {
            "id": i + 1,
            "x": pos[0], "y": pos[1], "z": pos[2],
            "dx": dirv[0] / n, "dy": dirv[1] / n, "dz": dirv[2] / n,
            "energy": erg, "weight": wgt, "particle": par,
        }

    # ── 粒子类型 ─────────────────────────────────────────────
    def _par(self, rng) -> str:
        v = self._v("sdef_par")
        if _is_d_ref(v):
            val = self.s.sample(int(v[1:]), rng)
            return _PAR_GROUP.get(str(int(val)), "other")
        if v:
            return _PAR_GROUP.get(v.strip().upper(), "other")
        return "n"  # 默认中子

    # ── 能量 ─────────────────────────────────────────────────
    def _erg(self, rng, pos_index) -> float:
        v = self._v("sdef_erg")
        if _is_d_ref(v):
            return self.s.sample(int(v[1:]), rng)
        toks = v.split()
        if len(toks) >= 2 and toks[0].upper().startswith("F"):
            # ERG=FPOS Dn：依赖位置索引
            parent = toks[0][1:].upper()
            if parent != "POS":
                raise SourceSamplingError(f"依赖引用 {v} 的父变量 {parent} 仅支持 POS")
            did = int(toks[1][1:])
            r = self.s.resolve_ds(did, float(pos_index) if pos_index is not None else 0.0)
            return self._ds_value(r, rng)
        return _num(v, 14.0)

    def _ds_value(self, r, rng) -> float:
        if "value" in r:
            return float(r["value"])
        if "distribution" in r:
            return self.s.sample(r["distribution"], rng)
        return 14.0  # default

    # ── 权重 ─────────────────────────────────────────────────
    def _wgt(self, rng) -> float:
        v = self._v("sdef_wgt")
        if _is_d_ref(v):
            return self.s.sample(int(v[1:]), rng)
        return _num(v, 1.0)

    # ── 方向 ─────────────────────────────────────────────────
    def _direction(self, rng, pos, is_surface=False) -> tuple:
        d = self._v("sdef_dir")
        vec = self._vec("sdef_vec")
        # 固定 DIR 标量 + VEC 参考矢量 → 沿 VEC（或 DIR 分布）
        if _is_d_ref(d):
            # DIR=Dn 分布：分布给方向余弦（相对 VEC 的 μ 或直接分量）
            mu = self.s.sample(int(d[1:]), rng)
            return self._dir_from_mu(mu, vec, rng)
        if d:
            # 固定 DIR（方向余弦数值，可多值 u v w）
            toks = d.split()
            if len(toks) >= 3:
                return tuple(_num(t, 0.0) for t in toks[:3])
            # DIR=1 单值：沿 VEC（若有）或各向同性退化
            if vec and any(vec):
                return self._norm(vec)
            return self._isotropic(rng)
        # 默认：面源余弦分布 p(DIR)=2·DIR（相对 VEC/面法线）；体源各向同性
        if is_surface:
            mu = math.sqrt(rng.uniform(0.0, 1.0))
            axis = vec if (vec and any(vec)) else (0.0, 0.0, 1.0)
            return self._dir_from_mu(mu, axis, rng)
        return self._isotropic(rng)

    def _dir_from_mu(self, mu, vec, rng) -> tuple:
        """方向余弦 μ（相对 VEC 轴）→ 方向矢量（绕 VEC 均匀方位角）。"""
        if vec and any(vec):
            ax = self._norm(vec)
            # 绕 ax 的方位角 φ 均匀
            phi = rng.uniform(0.0, 2.0 * math.pi)
            mu = max(-1.0, min(1.0, mu))
            perp = math.sqrt(max(0.0, 1.0 - mu * mu))
            # 正交基 (u, v, ax)
            ref = (1.0, 0.0, 0.0) if abs(ax[0]) < 0.9 else (0.0, 1.0, 0.0)
            u = self._norm(self._cross(ax, ref))
            v = self._cross(ax, u)
            return (mu * ax[0] + perp * (math.cos(phi) * u[0] + math.sin(phi) * v[0]),
                    mu * ax[1] + perp * (math.cos(phi) * u[1] + math.sin(phi) * v[1]),
                    mu * ax[2] + perp * (math.cos(phi) * u[2] + math.sin(phi) * v[2]))
        return self._isotropic(rng)

    @staticmethod
    def _isotropic(rng) -> tuple:
        z = rng.uniform(-1.0, 1.0)
        phi = rng.uniform(0.0, 2.0 * math.pi)
        r = math.sqrt(max(0.0, 1.0 - z * z))
        return (r * math.cos(phi), r * math.sin(phi), z)

    @staticmethod
    def _norm(v) -> tuple:
        n = math.sqrt(sum(x * x for x in v))
        if n < 1e-15:
            return (0.0, 0.0, 1.0)
        return tuple(x / n for x in v)

    @staticmethod
    def _cross(a, b) -> tuple:
        return (a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])

    # ── 位置（四路分叉）──────────────────────────────────────
    def _position(self, rng):
        px, py, pz = self._v("sdef_pos_x"), self._v("sdef_pos_y"), self._v("sdef_pos_z")
        sur = self._v("sdef_sur")
        cel = self._v("sdef_cel")
        rad = self._v("sdef_rad")
        ext = self._v("sdef_ext")
        axs = self._v("sdef_axs")

        # 1. 面源 SUR
        if sur and sur not in ("0",):
            return self._sample_surface(int(sur), rng), None
        # 2. 栅元均匀 CEL
        if cel and cel not in ("0",):
            return self._sample_cell(int(cel), rng), None
        # 3. POS=Dn 多点源（三分量同 D 引用）
        if px and px == py == pz and _is_d_ref(px):
            return self._sample_pos_dist(int(px[1:]), rng)
        # 4. 笛卡尔 X/Y/Z（任一轴 D 引用）
        if any(_is_d_ref(v) for v in (px, py, pz) if v):
            return self._sample_cartesian(px, py, pz, rng), None
        # 5. 柱坐标 POS+RAD/EXT/AXS
        if rad or ext:
            return self._sample_cylindrical(px, py, pz, rad, ext, axs, rng), None
        # 6. 点源 / 默认原点
        if px and py and pz:
            return (float(px), float(py), float(pz)), None
        return (0.0, 0.0, 0.0), None

    def _sample_pos_dist(self, did, rng):
        """POS=Dn 多点源：SI 值每 3 个一组 = 一个位置，SP 概率选位置组。"""
        e = self.s._entry(did)
        si = e.get("si") or {}
        si_vals = self.s._floats(si.get("values"))
        if len(si_vals) % 3 != 0 or len(si_vals) < 3:
            raise SourceSamplingError(f"POS=D{did} 的位置值个数（{len(si_vals)}）不是 3 的倍数")
        n_pos = len(si_vals) // 3
        sp = e.get("sp") or {}
        sp_type = (sp.get("type") or "D").strip().upper() or "D"
        probs = self.s._probs(sp_type, self.s._floats(sp.get("values")), n_pos)
        idx = _pick(probs, rng)
        return tuple(si_vals[idx * 3:idx * 3 + 3]), idx

    def _sample_cartesian(self, px, py, pz, rng):
        def axis(v, default):
            if _is_d_ref(v):
                return self.s.sample(int(v[1:]), rng)
            return _num(v, default)
        return (axis(px, 0.0), axis(py, 0.0), axis(pz, 0.0))

    def _sample_cylindrical(self, px, py, pz, rad, ext, axs, rng):
        """球体（POS+RAD 无 AXS）/ 圆柱（POS+AXS+RAD+EXT）——C810 3-57~58 语义。

        RAD = 半径（距 POS/AXS 距离）；EXT = 沿 AXS 距 POS 的距离（标量，可正负）。
        位置在「半径 RAD 的球面/圆」上；均匀体积靠 RAD/EXT 的幂律分布（默认 a=2 球 /
        a=1 柱 / a=0 轴）。
        """
        cx, cy, cz = (_num(px, 0.0), _num(py, 0.0), _num(pz, 0.0))
        axs_vec = self._vec("sdef_axs") if axs else ()
        if not axs or not axs_vec or not any(axs_vec):
            # 球体：位置在半径 RAD 的球面上均匀
            R = self._radial_value(rad, rng, power=2.0)
            dx, dy, dz = self._isotropic(rng)
            return (cx + R * dx, cy + R * dy, cz + R * dz)
        # 圆柱：位置在半径 RAD 的圆上（圆心在轴，距 POS = EXT）
        k = self._norm(axs_vec)
        ref = (1.0, 0.0, 0.0) if abs(k[0]) < 0.9 else (0.0, 1.0, 0.0)
        u = self._norm(self._cross(k, ref))
        v = self._cross(k, u)
        R = self._radial_value(rad, rng, power=1.0)
        Z = self._axial_value(ext, rng)
        phi = rng.uniform(0.0, 2.0 * math.pi)
        return (cx + Z * k[0] + R * (math.cos(phi) * u[0] + math.sin(phi) * v[0]),
                cy + Z * k[1] + R * (math.cos(phi) * u[1] + math.sin(phi) * v[1]),
                cz + Z * k[2] + R * (math.cos(phi) * u[2] + math.sin(phi) * v[2]))

    def _radial_value(self, rad, rng, power) -> float:
        """RAD 值（半径）。power = 默认幂律 a（SI 无 SP 时：球 2 / 柱 1）。"""
        if _is_d_ref(rad):
            did = int(rad[1:])
            entry = self.s._entry(did)
            sp = entry.get("sp") or {}
            si = entry.get("si") or {}
            si_vals = self.s._floats(si.get("values"))
            if not (sp.get("fnCode") or "").strip() and not sp.get("values") and len(si_vals) >= 1:
                # SI 无 SP → 默认幂律（C810 特殊默认 2/4：RAD 单值 x → [0,x]）
                lo = 0.0
                hi = si_vals[-1] if si_vals else 0.0
                return self._power_law_range(power, lo, hi, rng)
            return self.s.sample(did, rng)
        return _num(rad, 0.0)

    def _axial_value(self, ext, rng) -> float:
        """EXT 值（沿轴距离）。SI 无 SP → 默认幂律 a=0（均匀）。"""
        if _is_d_ref(ext):
            did = int(ext[1:])
            entry = self.s._entry(did)
            sp = entry.get("sp") or {}
            si = entry.get("si") or {}
            si_vals = self.s._floats(si.get("values"))
            if not (sp.get("fnCode") or "").strip() and not sp.get("values") and len(si_vals) >= 1:
                # SI 单值 x → [-x, x]（C810 特殊默认 5）；双值 → [lo, hi]
                if len(si_vals) == 1:
                    x = abs(si_vals[0])
                    return rng.uniform(-x, x)
                lo, hi = si_vals[0], si_vals[-1]
                return lo + rng.uniform(0.0, 1.0) * (hi - lo)
            return self.s.sample(did, rng)
        return _num(ext, 0.0)

    @staticmethod
    def _power_law_range(a, lo, hi, rng) -> float:
        """[lo,hi] 内按 |x|^a 抽样（= x^(a+1) 均匀；RAD 非负）。"""
        if hi <= 0:
            return 0.0
        lo = max(0.0, lo)
        u = rng.uniform(0.0, 1.0)
        if abs(a + 1.0) < 1e-12:
            return lo * (hi / lo) ** u if lo > 0 else hi * u
        return (lo ** (a + 1) + u * (hi ** (a + 1) - lo ** (a + 1))) ** (1.0 / (a + 1))

    # ── 几何判定（CEL/SUR，惰性 import pymcnp/voxel_csg）────
    def _helper(self):
        if self._geom_helper is None:
            self._geom_helper = _GeometryHelper(self.geometry)
        return self._geom_helper

    def _sample_cell(self, cell_num, rng):
        return self._helper().sample_cell(cell_num, rng)

    def _sample_surface(self, surf_num, rng):
        return self._helper().sample_surface(surf_num, rng)


class _GeometryHelper:
    """CEL/SUR 几何判定（深模块内部 seam，惰性 import pymcnp + voxel_csg）。

    CEL：cell 包围盒内拒绝采样（点在 cell 内 → 接受）。
    SUR：面上采样（平面/球/柱参数化；GQ/SQ 拒绝采样）。
    """

    def __init__(self, geometry):
        g = geometry or {}
        # geometry 由 api_server 层准备（复用其 parse_surfaces/Geometry.from_mcnp/
        # resolve_cell_complements/voxel_csg 构造 field 函数）：
        #   {"cells": {num: {"field": fn, "aabb": (lo3, hi3)}},
        #    "surfaces": {num: {"type": str, "params": list, "field": fn}}}
        self.cells = g.get("cells", {}) or {}
        self.surfs = g.get("surfaces", {}) or {}

    def sample_cell(self, cell_num, rng):
        info = self.cells.get(cell_num)
        if info is None:
            raise SourceSamplingError(f"CEL={cell_num} 引用的栅元不存在或无法判定")
        field = info.get("field")
        aabb = info.get("aabb")
        lo = list(aabb[0]) if aabb else [-1e3, -1e3, -1e3]
        hi = list(aabb[1]) if aabb else [1e3, 1e3, 1e3]
        lo = [max(-1e6, x) for x in lo]
        hi = [min(1e6, x) for x in hi]
        import numpy as np
        for _ in range(100000):
            p = [rng.uniform(lo[i], hi[i]) for i in range(3)]
            try:
                inside = field(np.asarray([p[0]]), np.asarray([p[1]]), np.asarray([p[2]]))
            except Exception:
                continue
            if inside is not None and bool(np.asarray(inside).ravel()[0]):
                return (p[0], p[1], p[2])
        raise SourceSamplingError(f"CEL={cell_num} 拒绝采样失败（栅元包围盒可能退化）")

    def sample_surface(self, surf_num, rng):
        s = self.surfs.get(surf_num)
        if s is None:
            raise SourceSamplingError(f"SUR={surf_num} 引用的曲面未定义")
        typ = s["type"]
        params = s["params"]
        if typ in ("PX",):
            y = rng.uniform(-1e3, 1e3)
            z = rng.uniform(-1e3, 1e3)
            return (params[0], y, z)
        if typ in ("PY",):
            x = rng.uniform(-1e3, 1e3)
            z = rng.uniform(-1e3, 1e3)
            return (x, params[0], z)
        if typ in ("PZ",):
            x = rng.uniform(-1e3, 1e3)
            y = rng.uniform(-1e3, 1e3)
            return (x, y, params[0])
        if typ == "SO":
            return self._sphere_pt((0.0, 0.0, 0.0), params[0], rng)
        if typ in ("S",):
            return self._sphere_pt(tuple(params[0:3]), params[3], rng)
        if typ in ("GQ", "SQ"):
            return self._quadric_pt(s, rng)
        raise SourceSamplingError(
            f"SUR={surf_num} 曲面类型 {typ} 的面采样不支持（MCNP 面源仅平面/球面/spheroid；"
            "柱面源请用退化体源 RAD 固定 + EXT 指定）")

    @staticmethod
    def _sphere_pt(c, r, rng):
        dx, dy, dz = _Context._isotropic(rng)
        return (c[0] + r * dx, c[1] + r * dy, c[2] + r * dz)

    def _quadric_pt(self, s, rng):
        """GQ/SQ 面采样：在保守包围盒内拒绝采样（|f|<tol）。"""
        import numpy as np
        try:
            from app.quadric import gq_aabb
            coeffs = s["params"]
            if s["type"] == "SQ":
                from app.quadric import sq_to_gq
                coeffs = sq_to_gq(coeffs)
            aabb = gq_aabb(coeffs)
            lo = list(aabb[0]) if aabb else (-1e2, -1e2, -1e2)
            hi = list(aabb[1]) if aabb else (1e2, 1e2, 1e2)
            for _ in range(200000):
                p = [rng.uniform(lo[i], hi[i]) for i in range(3)]
                f = s["field"](np.asarray([p[0]]), np.asarray([p[1]]), np.asarray([p[2]]))
                if abs(float(f[0])) < 1e-6:
                    return (p[0], p[1], p[2])
        except Exception:
            pass
        raise SourceSamplingError(f"SUR 面采样：曲面类型 {s['type']} 无法判定")


def sample_source(sdef_fields, distributions, geometry=None, *, n_particles=500, seed=None) -> dict:
    """SDEF 抽样编排入口（契约 §1 模块 B 接口）。

    返回 {"status":"ok", particles, energyRange, bounds} 或 {"status":"error", error}。
    """
    try:
        sampler = DistributionSampler(distributions)
        ctx = _Context(sdef_fields or {}, sampler, geometry)
        rng = random.Random(seed)
        particles = [ctx.sample_one(rng, i) for i in range(int(n_particles))]
        return _summarize(particles)
    except SourceSamplingError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"源抽样失败: {e}"}


def _summarize(particles: list) -> dict:
    energies = [p["energy"] for p in particles if p["energy"] and p["energy"] > 0]
    xs = [p["x"] for p in particles]
    ys = [p["y"] for p in particles]
    zs = [p["z"] for p in particles]
    if energies:
        e_min, e_max = min(energies), max(energies)
    else:
        # 无有效能量（全部 ≤0 或缺字段）→ 中性零区间。
        # 注意：不能用 (0.0, 1.0) —— 前端以 min==max 判定「无能量」
        # （SourceDemoWindow.tsx:166），且单能 δ 分布（如 SDEF ERG=14）本就该
        # 返回 [14,14]，旧实现把 e_max<=e_min 一律改成 [0,1]，等于**丢弃真实能量**。
        e_min = e_max = 0.0
    return {
        "status": "ok",
        "particles": particles,
        "energyRange": {"min": e_min, "max": e_max},
        "bounds": {
            "min": [min(xs), min(ys), min(zs)],
            "max": [max(xs), max(ys), max(zs)],
        },
    }
