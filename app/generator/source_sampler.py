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
        # 最近一次 _position() 的副产品：面源法线（带 NRM 符号）；非面源为 None
        self._surface_normal = None
        # 本次抽样是否为 CEL 源（SP V 合法性判定用；C810 3-64）
        self.cel_source = False

    # ── 字段读取 ─────────────────────────────────────────────
    def _v(self, key) -> str:
        return str(self.f.get(key) or "").strip()

    def _vec(self, key) -> tuple:
        toks = self._v(key).split()
        return tuple(_num(t, 0.0) for t in toks)

    def _sdef_trn(self):
        """SDEF TR=n（固定整数编号）的变换数据；缺省 / 分布形态 / 未定义 → None。

        C810 Table 3.3：TR = 源变换（可给编号，也可给分布 Dn —— 分布形态需要用户
        自己给一组 TR 卡，本项目按「未实现即明确不静默」处理：仅支持整数编号）。
        """
        v = self._v("sdef_tr")
        if not v or v.upper().startswith("F") or _is_d_ref(v):
            return None
        cards = (self.geometry or {}).get("trCards") or {}
        tr = cards.get(v) or cards.get(str(v))
        if not tr:
            return None
        return {"origin": tuple(tr.get("translate") or (0.0, 0.0, 0.0)),
                "rotate": tr.get("rotate")}

    # ── 单粒子 ───────────────────────────────────────────────
    def sample_one(self, rng, i: int) -> dict:
        par = self._par(rng)
        pos, pos_index = self._position(rng)
        cel = self.cel_source
        erg = self._erg(rng, pos_index, cel=cel)
        # 面源法线：位置抽样的副产品（C810 3-57~3-59：面源的 VEC 默认 = 面法线，
        # 符号由 NRM 定；平面源的 RAD 沿切向量、法线方向不动）
        normal = self._surface_normal
        dirv = self._direction(rng, pos, normal)
        wgt = self._wgt(rng, cel=cel)
        # SDEF TR=n（源坐标变换）：位置与方向都要变换（C810 Table 3.3 TR 行）
        trn = self._sdef_trn()
        if trn is not None:
            # SDEF TR 是**源坐标系**变换：对已抽出的世界系位置/方向再作用一次
            # （与曲面自身 TR 复合；_to_world_dir 内部是 Rᵀ·v，位置再加 origin）
            o = trn["origin"]
            dirv = _GeometryHelper._to_world_dir(dirv, trn["rotate"])
            pos = _GeometryHelper._to_world_dir(pos, trn["rotate"])
            pos = (pos[0] + o[0], pos[1] + o[1], pos[2] + o[2])
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
            val = self.s.sample(int(v[1:]), rng, var="PAR")
            return _PAR_GROUP.get(str(int(val)), "other")
        if v:
            return _PAR_GROUP.get(v.strip().upper(), "other")
        return "n"  # 默认中子

    # ── 能量 ─────────────────────────────────────────────────
    def _erg(self, rng, pos_index, cel=False) -> float:
        v = self._v("sdef_erg")
        if _is_d_ref(v):
            return self.s.sample(int(v[1:]), rng, var="ERG")
        toks = v.split()
        if len(toks) >= 2 and toks[0].upper().startswith("F"):
            # ERG=FPOS Dn：依赖位置索引
            parent = toks[0][1:].upper()
            if parent != "POS":
                raise SourceSamplingError(f"依赖引用 {v} 的父变量 {parent} 仅支持 POS")
            did = int(toks[1][1:])
            r = self.s.resolve_ds(did, float(pos_index) if pos_index is not None else 0.0)
            return self._ds_value(r, rng, cel=cel)
        return _num(v, 14.0)

    def _ds_value(self, r, rng, cel=False) -> float:
        if "value" in r:
            return float(r["value"])
        if "distribution" in r:
            return self.s.sample(r["distribution"], rng, var="ERG", cel=cel)
        return 14.0  # default

    # ── 权重 ─────────────────────────────────────────────────
    def _wgt(self, rng, cel=False) -> float:
        v = self._v("sdef_wgt")
        if _is_d_ref(v):
            return self.s.sample(int(v[1:]), rng, var="WGT", cel=cel)
        return _num(v, 1.0)

    # ── 方向 ─────────────────────────────────────────────────
    def _direction(self, rng, pos, normal=None) -> tuple:
        """方向抽样（C810 3-59 + Table 3.3）。

        - DIR=Dn：μ 从分布抽（μ = VEC 与方向的夹角余弦），方位角 0~360° 均匀；
        - DIR 固定值：多值当方向分量；单值 = 沿参考轴（VEC，面源可退回面法线）；
        - DIR 缺省：面源 = 余弦分布 p(μ)=2μ（相对 VEC；VEC 缺省 = **面法线**，
          符号由 NRM 定）；体源 = 各向同性。
        """
        d = self._v("sdef_dir")
        vec = self._vec("sdef_vec")
        # 参考轴：显式 VEC 优先；面源无 VEC 时 = 面法线（C810：VEC 缺省 = 面法线 with NRM sign）
        axis = vec if (vec and any(vec)) else (normal or ())
        if _is_d_ref(d):
            mu = self.s.sample(int(d[1:]), rng, var="DIR", cel=self.cel_source,
                               axs=bool(self._v("sdef_axs")))
            return self._dir_from_mu(mu, axis, rng)
        if d:
            # 固定 DIR（方向余弦数值，可多值 u v w）
            toks = d.split()
            if len(toks) >= 3:
                return tuple(_num(t, 0.0) for t in toks[:3])
            # DIR=1 单值：沿参考轴（VEC / 面法线）
            if axis and any(axis):
                return self._norm(axis)
            raise SourceSamplingError(
                "SDEF DIR=1（单方向）缺少参考轴：请给 VEC，或把源放在曲面上"
                "（面源的 VEC 默认为面法线）—— C810 Table 3.3 VEC 行")
        # 默认：面源余弦分布 p(DIR)=2·DIR；体源各向同性
        if normal is not None:
            mu = math.sqrt(rng.uniform(0.0, 1.0))
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
        # 非面源路径一律无面法线（方向按体源各向同性语义处理）
        self._surface_normal = None
        self.cel_source = bool(cel and cel not in ("0",))

        # 1. 面源 SUR
        if sur and sur not in ("0",):
            return self._sample_surface(int(sur), rng, px, py, pz, rad), None
        # 2. 栅元均匀 CEL
        if cel and cel not in ("0",):
            return self._sample_cell(int(cel), rng), None
        # 3. POS=Dn 多点源（三分量同 D 引用）
        if px and px == py == pz and _is_d_ref(px):
            return self._sample_pos_dist(int(px[1:]), rng, cel=self.cel_source,
                                         axs=bool(axs))
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

    def _sample_pos_dist(self, did, rng, cel=False, axs=False):
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
        def axis(v, default, name):
            if _is_d_ref(v):
                return self.s.sample(int(v[1:]), rng, var=name, cel=self.cel_source,
                                     axs=bool(self._v("sdef_axs")))
            return _num(v, default)
        return (axis(px, 0.0, "X"), axis(py, 0.0, "Y"), axis(pz, 0.0, "Z"))

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
        """RAD 值（半径）。power = 默认幂律 a（SI 无 SP 时：球 2 / 柱 1）。

        ``axs=True``（定义了 AXS）时，C810 3-66 规定 `SP −21` 的默认 a 从 2 变成 1。
        """
        if _is_d_ref(rad):
            return _default_power_law(self.s, int(rad[1:]), rng, power, "RAD",
                                      cel=self.cel_source, axs=bool(self._v("sdef_axs")))
        return _num(rad, 0.0)

    def _axial_value(self, ext, rng) -> float:
        """EXT 值（沿轴距离）。SI 无 SP → 默认幂律 a=0（均匀）。"""
        if _is_d_ref(ext):
            return _default_power_law(self.s, int(ext[1:]), rng, 0.0, "EXT",
                                      cel=self.cel_source)
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
            self._geom_helper = _GeometryHelper(self.geometry, self.s)
        return self._geom_helper

    def _sample_cell(self, cell_num, rng):
        return self._helper().sample_cell(cell_num, rng)

    def _sample_surface(self, surf_num, rng, px, py, pz, rad):
        """面源位置 + 法线；法线写入 `self._surface_normal` 供方向抽样使用。"""
        pos, normal = self._helper().sample_surface(surf_num, rng, px, py, pz, rad,
                                                    nrm=self._v("sdef_nrm"))
        self._surface_normal = normal
        return pos


def _default_power_law(sampler, did, rng, power, var, cel=False, axs=False) -> float:
    """「只有 SI、没有 SP」时 MCNP 自动补的默认幂律（C810 3-66 特殊默认 2/3/4/5）。

    - RAD 的 ``SIn`` 给半径范围（``SI 0 5`` 或单值 x ⇒ ``SI 0 x``，a 默认 2；有 AXS 时 1）；
    - EXT 的 ``SIn`` 给轴向范围（单值 x ⇒ ``SI −x x``，a 默认 0）；
    - 只要 SP 存在（哪怕只是 `SP −21`），就交给通用内置函数路径，本函数不介入。
    """
    entry = sampler._entry(did)
    sp = entry.get("sp") or {}
    if (sp.get("fnCode") or "").strip() or sp.get("values"):
        return sampler.sample(did, rng, var=var, cel=cel, axs=axs)
    si_vals = sampler._floats((entry.get("si") or {}).get("values"))
    if not si_vals:
        return 0.0
    lo, hi = DistributionSampler._range(si_vals, (0.0, 0.0), var)
    return _Context._power_law_range(power, lo, hi, rng)


class _GeometryHelper:
    """CEL/SUR 几何判定（深模块内部 seam，惰性 import pymcnp + voxel_csg）。

    CEL：cell 包围盒内拒绝采样（点在 cell 内 → 接受）。
    SUR：面源位置 + 面法线（C810 3-58：面源只支持 平面/球/椭球 三类；
    「圆柱面源必须写成退化体源」是 MCNP 自身限制，本项目按语义明确报错）。
    """

    def __init__(self, geometry, sampler=None):
        g = geometry or {}
        # geometry 由 api_server 层准备（复用其 parse_surfaces/Geometry.from_mcnp/
        # resolve_cell_complements/voxel_csg 构造 field 函数）：
        #   {"cells": {num: {"field": fn, "aabb": (lo3, hi3)}},
        #    "surfaces": {num: {"type": str, "params": list, "field": fn,
        #                       "rotate": 3×3 | None, "origin": (3,)}}}
        self.cells = g.get("cells", {}) or {}
        self.surfs = g.get("surfaces", {}) or {}
        self.sampler = sampler

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

    def sample_surface(self, surf_num, rng, px="", py="", pz="", rad="", nrm=""):
        """面源位置 + 面法线（C810 3-58 / Table 3.3）。

        - **平面**：位置 = POS + RAD·(面内单位矢量)；RAD 的默认分布是 a=1 的幂律
          （面内均匀）；POS 必须在面上（MCNP 不检查，本项目也不检查，但 RAD 的
          切向偏移保证位置确实在面上）。
        - **球**：位置按面积均匀；法线 = (p − center)/|…|。
        - **椭球（GQ/SQ）**：按面积近似采样（保守盒内拒绝，**位置不在面上**，
          见 `_quadric_pt` 说明），法线 = ∇f 归一化。
        - 其余类型：按 C810「面源只能是平面/球/椭球」的语义**明确报错**，并给出
          「改用退化体源」的可操作提示（旧实现曾在 ±1000 的面上乱撒且不报错）。
        """
        s = self.surfs.get(surf_num)
        if s is None:
            raise SourceSamplingError(f"SUR={surf_num} 引用的曲面未定义")
        typ = s["type"]
        params = [float(v) for v in (s.get("params") or [])]
        rotate = s.get("rotate")
        origin = s.get("origin") or (0.0, 0.0, 0.0)
        nrm_sign = -1.0 if str(nrm).strip() in ("-1", "-1.0") else 1.0
        pos = (_num(px, 0.0), _num(py, 0.0), _num(pz, 0.0))

        if typ in ("PX", "PY", "PZ", "P_0", "P_1"):
            e = {"PX": (1.0, 0.0, 0.0), "PY": (0.0, 1.0, 0.0), "PZ": (0.0, 0.0, 1.0)}.get(typ)
            if e is None:
                e = self._plane_normal(typ, params)
            e = tuple(e)
            t1, t2 = self._tangents(e)
            r = self._radial_at(rad, rng, power=1.0)
            phi = rng.uniform(0.0, 2.0 * math.pi)
            p_local = (pos[0] + r * (math.cos(phi) * t1[0] + math.sin(phi) * t2[0]),
                       pos[1] + r * (math.cos(phi) * t1[1] + math.sin(phi) * t2[1]),
                       pos[2] + r * (math.cos(phi) * t1[2] + math.sin(phi) * t2[2]))
            # 平面源：位置在面上，法线方向不随位置变
            return self._to_world(p_local, origin, rotate), \
                self._nrm_sign_vec(self._to_world_dir(e, rotate), nrm_sign)

        if typ in ("SO", "SPH", "S", "SX", "SY", "SZ"):
            if typ == "SO":
                c, rr = (0.0, 0.0, 0.0), params[0]
            elif typ in ("SPH", "S"):
                c, rr = tuple(params[0:3]), params[3]
            else:
                c = {"SX": (params[0], 0.0, 0.0), "SY": (0.0, params[0], 0.0),
                     "SZ": (0.0, 0.0, params[0])}[typ]
                rr = params[1]
            d = _Context._isotropic(rng)
            p_local = (c[0] + rr * d[0], c[1] + rr * d[1], c[2] + rr * d[2])
            n_local = self._norm3((p_local[0] - c[0], p_local[1] - c[1], p_local[2] - c[2]))
            return (self._to_world(p_local, origin, rotate),
                    self._nrm_sign_vec(self._to_world_dir(n_local, rotate), nrm_sign))

        if typ in ("GQ", "SQ"):
            p_local, n_local = self._quadric_pt(s, rng)
            return (self._to_world(p_local, origin, rotate),
                    self._nrm_sign_vec(self._to_world_dir(n_local, rotate), nrm_sign))

        raise SourceSamplingError(
            f"SUR={surf_num}：曲面类型 {typ} 不能作面源。C810 3-58 原文规定面源只能是"
            "平面（P/PX/PY/PZ）、球面（SO/S/SX/SY/SZ）或椭球面（GQ/SQ）——"
            "「Cylindrical surface sources must be specified as degenerate volume sources」。"
            "柱面/锥面/环面源请改用退化体源：POS + AXS + RAD + EXT（RAD 固定为该半径、"
            "EXT 给轴向范围）")

    # ── 面源辅助：TR / 切向量 / 法线 ──────────────────────────
    def _radial_at(self, rad, rng, power) -> float:
        """平面源 RAD（面内半径）：走变量名感知的通用路径
        （`SI x` + `SP −21` ⇒ C810 规则 4 的 `SI 0 x`；无 SP ⇒ 默认幂律 a=power）。"""
        if _is_d_ref(rad):
            return _default_power_law(self.sampler, int(rad[1:]), rng, power, "RAD")
        return _num(rad, 0.0)

    @staticmethod
    def _norm3(v) -> tuple:
        n = math.sqrt(sum(x * x for x in v))
        if n < 1e-15:
            return (0.0, 0.0, 1.0)
        return tuple(x / n for x in v)

    @staticmethod
    def _nrm_sign_vec(v, sign) -> tuple:
        """按 NRM 符号翻转面法线（C810 Table 3.3：NRM = 面法线符号，默认 +1）。"""
        return tuple(sign * x for x in v)

    @staticmethod
    def _plane_normal(typ, params) -> tuple:
        """平面法线（局部）：P_0 = A B C；P_1 = 三点 (P2−P1)×(P3−P1)（C810 3-17 正侧）。"""
        if typ == "P_0":
            if len(params) < 3:
                raise SourceSamplingError("P 卡参数不足（需 A B C D）")
            a, b, c = params[0], params[1], params[2]
            n = math.sqrt(a * a + b * b + c * c)
            if n < 1e-15:
                raise SourceSamplingError("P 卡法向量为零")
            return (a / n, b / n, c / n)
        if typ == "P_1":
            if len(params) < 9:
                raise SourceSamplingError("P 卡参数不足（需 9 个点坐标）")
            p1, p2, p3 = params[0:3], params[3:6], params[6:9]
            u = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
            v = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            m = math.sqrt(sum(x * x for x in n))
            if m < 1e-15:
                raise SourceSamplingError("P 卡三点共线，无法定法线")
            return (n[0] / m, n[1] / m, n[2] / m)
        raise SourceSamplingError(f"未知平面类型 {typ}")

    @staticmethod
    def _tangents(e) -> tuple:
        """平面内正交单位向量组（与 e 正交）。"""
        ref = (1.0, 0.0, 0.0) if abs(e[0]) < 0.9 else (0.0, 1.0, 0.0)
        t1 = (e[1] * ref[2] - e[2] * ref[1],
              e[2] * ref[0] - e[0] * ref[2],
              e[0] * ref[1] - e[1] * ref[0])
        t1 = _GeometryHelper._norm3(t1)
        t2 = (e[1] * t1[2] - e[2] * t1[1],
              e[2] * t1[0] - e[0] * t1[2],
              e[0] * t1[1] - e[1] * t1[0])
        return t1, _GeometryHelper._norm3(t2)

    @staticmethod
    def _to_world(p, origin, rotate):
        """局部点 → 世界点：``p_global = Rᵀ · p_local + o``。

        约定与 FreeCAD 侧 ``apply_trn`` 一致（`_freecad_csg_worker.py:1070-1078`：
        MCNP TR 卡的 9 个方向余弦按**行**存进 `rotate`，FreeCAD 矩阵按**列**组装 ⇒
        实际是转置作用），也与 `voxel_csg._surface_transform`（world→local 用 ``R⁻¹``）互逆。
        """
        if rotate is None:
            return (p[0] + origin[0], p[1] + origin[1], p[2] + origin[2])
        return (rotate[0][0] * p[0] + rotate[1][0] * p[1] + rotate[2][0] * p[2] + origin[0],
                rotate[0][1] * p[0] + rotate[1][1] * p[1] + rotate[2][1] * p[2] + origin[1],
                rotate[0][2] * p[0] + rotate[1][2] * p[1] + rotate[2][2] * p[2] + origin[2])

    @staticmethod
    def _to_world_dir(v, rotate):
        """局部方向 → 世界方向：``Rᵀ · d``（只转不平移，与 `_to_world` 同约定）。"""
        if rotate is None:
            return (v[0], v[1], v[2])
        return (rotate[0][0] * v[0] + rotate[1][0] * v[1] + rotate[2][0] * v[2],
                rotate[0][1] * v[0] + rotate[1][1] * v[1] + rotate[2][1] * v[2],
                rotate[0][2] * v[0] + rotate[1][2] * v[1] + rotate[2][2] * v[2])

    @staticmethod
    def _sphere_pt(c, r, rng):
        dx, dy, dz = _Context._isotropic(rng)
        return (c[0] + r * dx, c[1] + r * dy, c[2] + r * dz)

    def _quadric_pt(self, s, rng):
        """GQ/SQ 面源采样：保守盒内**在内侧**拒绝采样（f≥0，与曲面正侧一致）。

        返回 (局部点, 局部法线 ∇f)。⚠️ 抽样在**体内均匀**而非面上均匀（旧实现 |f|<tol
        命中率极低且会静默失败）；对 C810 允许的椭球面源，法线方向与「向外」语义
        一致，位置分布是面积均匀的近似（已在 errors/文档中标注为近似，不静默）。
        """
        import numpy as np
        from app.quadric import gq_aabb, gq_gradient_fn, sq_to_gq
        coeffs = s["params"]
        if s["type"] == "SQ":
            coeffs = sq_to_gq(coeffs)
        aabb = gq_aabb(coeffs)
        if not aabb:
            raise SourceSamplingError(f"SUR 面采样：{s['type']} 包围盒无法确定（无界曲面）")
        lo, hi = aabb
        try:
            grad = gq_gradient_fn(coeffs)
        except Exception:  # noqa: BLE001
            grad = None
        for _ in range(20000):
            p = (rng.uniform(lo[0], hi[0]), rng.uniform(lo[1], hi[1]), rng.uniform(lo[2], hi[2]))
            f = float(s["field"](np.asarray([p[0]]), np.asarray([p[1]]), np.asarray([p[2]]))[0])
            if f >= 0.0:
                if grad is None:
                    raise SourceSamplingError(f"SUR 面采样：{s['type']} 缺少梯度实现")
                g = grad(p[0], p[1], p[2])
                return p, self._norm3(tuple(float(x) for x in g))
        raise SourceSamplingError(f"SUR 面采样：{s['type']} 内点拒绝采样失败（包围盒可能退化）")


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
