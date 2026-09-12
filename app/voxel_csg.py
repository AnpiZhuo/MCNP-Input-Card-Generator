"""体素 CSG：在均匀网格上求值栅元布尔表达式并提取水密网格。

用途：含 GQ/SQ 曲面的栅元。OCC 对「网格化二次曲面半空间」的布尔不可靠
（isInside 不一致、cut/common 结果错），因此这类栅元直接在体素网格上
逐点求值布尔表达式（intersect=AND、union=OR、neg/complement=NOT），
用 marching cubes 提取闭合表面，天然水密、绕开 OCC 布尔。

只支持「隐式可求值」的曲面：平面/球/圆柱/圆锥/GQ/SQ + RPP/SPH 简单宏体；
其余类型抛 ValueError，由调用方回退 OCC 路径。
"""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)

# 紧盒「无界轴」哨兵：``cell_aabb`` 返回的 (lo, hi, axes) 里，axes[i]==False
# 表示该轴无界、lo[i]/hi[i] 只是占位值。生产者历史上混用 0（CZ/CY/CX）与
# ±1e300（平面半空间），故合并/裁剪时必须认标志位、并把结果统一成本哨兵，
# 由 _clip_aabb_to_bound 裁到 ±B。详见 _aabb_intersect 的坑说明。
_AABB_UNBOUNDED = 1e300

try:
    from quadric import sq_to_gq, gq_aabb, classify_gq
except ImportError:  # 测试/直接 import app 包时 quadric 在 app/ 下
    from app.quadric import sq_to_gq, gq_aabb, classify_gq

try:
    from mc import marching_cubes
except ImportError:  # 测试/直接 import app 包时 mc 在 app/ 下
    from app.mc import marching_cubes


def _surface_transform(tr_data):
    """把 TR 数据转换为「世界坐标 → 曲面局部坐标」的向量化函数。

    tr_cards.rotate 的每行 = 局部坐标轴在全局系的方向余弦（MCNP TR 卡
    B 矩阵按列写 9 值后由 parse_tr_cards 组织为 3×3；FreeCAD worker 的
    apply_trn 也以 rotate.T 作为 local→global 矩阵）。因此：
        p_local = rotate^{-T} · (p_global − o)
        （local = q @ inv(rotate)，兼容非严格正交输入）
    """
    if not tr_data:
        return None
    origin = np.asarray(tr_data.get("translate", [0, 0, 0]), dtype=float).ravel()
    if origin.size != 3:
        raise ValueError("TR translate 必须为 3 维向量")
    rotate = np.asarray(
        tr_data.get("rotate", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
        dtype=float,
    )
    if rotate.shape != (3, 3):
        raise ValueError("TR rotate 必须为 3×3 矩阵")
    try:
        rotate_inv = np.linalg.inv(rotate)
    except np.linalg.LinAlgError:
        rotate_inv = rotate.T

    def to_local(x, y, z):
        x = np.asarray(x)
        y = np.asarray(y)
        z = np.asarray(z)
        p = np.stack(np.broadcast_arrays(x, y, z), axis=-1)
        q = p - origin
        local = q @ rotate_inv
        return local[..., 0], local[..., 1], local[..., 2]

    return to_local


def _surface_tr(surface, tr_cards):
    """读取曲面引用的 TR 数据（兼容 int/str key），无引用或缺失返回 None。"""
    if not tr_cards:
        return None
    trn = surface.get("transform")
    if trn is None:
        return None
    for key in (trn, str(trn)):
        if key in tr_cards:
            return tr_cards[key]
    try:
        key = int(trn)
    except (TypeError, ValueError):
        return None
    return tr_cards.get(key)


def _transform_aabb(lo, hi, transform):
    """把局部 AABB 的 8 角点经 TR 变换到全局后取包围盒。

    TR 方向（与 _surface_transform 一致）：p_local = R⁻¹·(p_global − o)，
    逆映射 p_global = o + p_local @ R。仿射变换下局部 AABB 的 8 角点
    变换后的 bbox 是变换后曲面的保守全局盒——带 TR 的有界曲面不再
    回退全盒（全盒会让 32³ 粗扫在 B=500 时漏掉 4cm 级小栅元，实测
    体素网格为空 → 降级包围盒）。
    """
    if transform is None:
        return lo, hi
    origin = np.asarray(transform.get("translate", [0, 0, 0]), dtype=float).ravel()
    rotate = np.asarray(
        transform.get("rotate", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]), dtype=float
    )
    if origin.size != 3 or rotate.shape != (3, 3):
        return lo, hi
    xs = (lo[0], hi[0])
    ys = (lo[1], hi[1])
    zs = (lo[2], hi[2])
    corners = np.array(
        [[x, y, z] for x in xs for y in ys for z in zs], dtype=float
    )
    glob = origin[None, :] + corners @ rotate
    glo = glob.min(axis=0)
    ghi = glob.max(axis=0)
    return tuple(glo.tolist()), tuple(ghi.tolist())


def _polyhedron_field(verts, faces):
    """凸多面体 → 标量场 f(x, y, z)：f<0 内部、f>0 外部（宏体判定复用）。

    每面法向朝外（体心定向：面心 − 体心）；f = max_i dot(n_i, P − p_i)。
    f<0 ⇔ 所有面半空间内侧（凸多面体内部）。BOX/RHP/HEX/WED/ARB 本质是
    多面体，统一经此求值，避免各宏体写特殊坐标判定。
    """
    arr = np.asarray(verts, dtype=float)
    center = arr.mean(axis=0)
    planes = []
    for f in faces:
        pts = arr[f]
        if len(f) < 3:
            continue
        nrm = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        ln = float(np.linalg.norm(nrm))
        if ln < 1e-15:
            continue
        nrm = nrm / ln
        fc = pts.mean(axis=0)
        if float(np.dot(nrm, fc - center)) < 0:
            nrm = -nrm
        planes.append((nrm, fc))

    def field(x, y, z):
        X = np.stack(np.broadcast_arrays(x, y, z), axis=-1)
        out = None
        for n, p0 in planes:
            d = X @ n - float(n @ p0)
            out = d if out is None else np.maximum(out, d)
        return out
    return field


def _rot60(v, axis):
    """向量 v 绕单位轴 axis 转 60°（Rodrigues；RHP/HEX 9 参时推断 R2/R3）。"""
    v = np.asarray(v, dtype=float)
    k = np.asarray(axis, dtype=float)
    c = 0.5
    s = math.sqrt(3.0) / 2.0
    kxv = np.cross(k, v)
    dot = float(k @ v)
    return c * v + s * kxv + k * dot * (1.0 - c)


def surface_fn(surf_type: str, params: list, transform=None):
    """返回向量化函数 f(x, y, z)，f > 0 为正侧（与 make_halfspace 一致）。

    宏体（RPP/SPH/RCC/TRC/REC/ELL/WED/BOX/RHP/HEX/ARB）的约定：f<0 = 宏体
    内部、f>0 = 外部（MCNP 宏体「负号=内部」语义），使 cell 表达式 `-n`
    经 eval_cell_field 的 neg 得到「内部」。

    ``transform`` 为 parse_tr_cards 产出的 TR dict 时，世界坐标先变换到
    曲面局部系再求值，修正此前 *TRn 被忽略的问题。
    """
    t = (surf_type or "").upper()
    p = [float(v) for v in params]
    to_local = _surface_transform(transform)

    def wrap(fn):
        if to_local is None:
            return fn

        def transformed(x, y, z):
            lx, ly, lz = to_local(x, y, z)
            return fn(lx, ly, lz)

        return transformed

    if t == "PX":
        return wrap(lambda x, y, z: x - p[0])
    if t == "PY":
        return wrap(lambda x, y, z: y - p[0])
    if t == "PZ":
        return wrap(lambda x, y, z: z - p[0])
    if t == "P_0":
        a, b, c, dd = p[0], p[1], p[2], p[3]
        return wrap(lambda x, y, z: a * x + b * y + c * z - dd)
    if t == "P_1":
        x1, y1, z1, x2, y2, z2, x3, y3, z3 = p
        ax, ay, az = x2 - x1, y2 - y1, z2 - z1
        bx, by, bz = x3 - x1, y3 - y1, z3 - z1
        nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
        return wrap(lambda x, y, z: nx * (x - x1) + ny * (y - y1) + nz * (z - z1))

    if t == "SO":
        r = p[0]
        return wrap(lambda x, y, z: x * x + y * y + z * z - r * r)
    if t == "SX":
        cx, r = p[0], p[1]
        return wrap(lambda x, y, z: (x - cx) ** 2 + y * y + z * z - r * r)
    if t == "SY":
        cy, r = p[0], p[1]
        return wrap(lambda x, y, z: x * x + (y - cy) ** 2 + z * z - r * r)
    if t == "SZ":
        cz, r = p[0], p[1]
        return wrap(lambda x, y, z: x * x + y * y + (z - cz) ** 2 - r * r)
    if t == "S":
        cx, cy, cz, r = p[0], p[1], p[2], p[3]
        return wrap(lambda x, y, z: (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 - r * r)

    if t == "CX":
        r = p[0]
        return wrap(lambda x, y, z: y * y + z * z - r * r)
    if t == "CY":
        r = p[0]
        return wrap(lambda x, y, z: x * x + z * z - r * r)
    if t == "CZ":
        r = p[0]
        return wrap(lambda x, y, z: x * x + y * y - r * r)
    if t == "C/X":
        y0, z0, r = p[0], p[1], p[2]
        return wrap(lambda x, y, z: (y - y0) ** 2 + (z - z0) ** 2 - r * r)
    if t == "C/Y":
        x0, z0, r = p[0], p[1], p[2]
        return wrap(lambda x, y, z: (x - x0) ** 2 + (z - z0) ** 2 - r * r)
    if t == "C/Z":
        x0, y0, r = p[0], p[1], p[2]
        return wrap(lambda x, y, z: (x - x0) ** 2 + (y - y0) ** 2 - r * r)

    if t in ("KX", "KY", "KZ"):
        v0, t2, sgn = p[0], p[1], p[2]
        s = 1.0 if sgn >= 0 else -1.0
        if t == "KX":
            return wrap(lambda x, y, z: (t2 * (x - v0) ** 2 - (y * y + z * z)) * s)
        if t == "KY":
            return wrap(lambda x, y, z: (t2 * (y - v0) ** 2 - (x * x + z * z)) * s)
        return wrap(lambda x, y, z: (t2 * (z - v0) ** 2 - (x * x + y * y)) * s)
    if t in ("K/X", "K/Y", "K/Z"):
        x0, y0, z0, t2, sgn = p[0], p[1], p[2], p[3], p[4]
        s = 1.0 if sgn >= 0 else -1.0
        if t == "K/X":
            return wrap(lambda x, y, z: (t2 * (x - x0) ** 2 - ((y - y0) ** 2 + (z - z0) ** 2)) * s)
        if t == "K/Y":
            return wrap(lambda x, y, z: (t2 * (y - y0) ** 2 - ((x - x0) ** 2 + (z - z0) ** 2)) * s)
        return wrap(lambda x, y, z: (t2 * (z - z0) ** 2 - ((x - x0) ** 2 + (y - y0) ** 2)) * s)

    if t == "GQ":
        a, b, c, d, e, f, g, h, j, k = p
        return wrap(lambda x, y, z: (a * x * x + b * y * y + c * z * z
                                     + d * x * y + e * y * z + f * z * x
                                     + g * x + h * y + j * z + k))
    if t == "SQ":
        return surface_fn("GQ", sq_to_gq(p), transform)

    if t == "RPP":
        xmin, xmax, ymin, ymax, zmin, zmax = p
        def _rpp(x, y, z):
            inside = ((x > xmin) & (x < xmax) & (y > ymin) & (y < ymax)
                      & (z > zmin) & (z < zmax))
            return np.where(inside, -1.0, 1.0)
        return wrap(_rpp)
    if t == "SPH":
        vx, vy, vz, r = p[0], p[1], p[2], p[3]
        return wrap(lambda x, y, z: (x - vx) ** 2 + (y - vy) ** 2 + (z - vz) ** 2 - r * r)

    # ── 其余宏体（MCNP 语义：f<0 内部）──
    if t == "RCC":
        vx, vy, vz, hx, hy, hz, r = p
        h2 = hx * hx + hy * hy + hz * hz
        if h2 <= 1e-30:
            raise ValueError("RCC 高度向量退化")

        def _rcc(x, y, z):
            dx, dy, dz = x - vx, y - vy, z - vz
            axial = (dx * hx + dy * hy + dz * hz) / h2
            rx = dx - axial * hx
            ry = dy - axial * hy
            rz = dz - axial * hz
            rad2 = rx * rx + ry * ry + rz * rz
            inside = (axial >= 0) & (axial <= 1) & (rad2 <= r * r)
            return np.where(inside, -1.0, 1.0)
        return wrap(_rcc)

    if t == "TRC":
        vx, vy, vz, hx, hy, hz, r1, r2 = p
        h2 = hx * hx + hy * hy + hz * hz
        if h2 <= 1e-30:
            raise ValueError("TRC 高度向量退化")

        def _trc(x, y, z):
            dx, dy, dz = x - vx, y - vy, z - vz
            axial = (dx * hx + dy * hy + dz * hz) / h2
            rx = dx - axial * hx
            ry = dy - axial * hy
            rz = dz - axial * hz
            rad2 = rx * rx + ry * ry + rz * rz
            r_at = r1 + (r2 - r1) * axial
            inside = (axial >= 0) & (axial <= 1) & (rad2 <= r_at * r_at)
            return np.where(inside, -1.0, 1.0)
        return wrap(_trc)

    if t == "REC":
        vx, vy, vz, hx, hy, hz, v1x, v1y, v1z, v2x, v2y, v2z = p
        h2 = hx * hx + hy * hy + hz * hz
        v1l2 = v1x * v1x + v1y * v1y + v1z * v1z
        v2l2 = v2x * v2x + v2y * v2y + v2z * v2z
        if h2 <= 1e-30 or v1l2 <= 1e-30 or v2l2 <= 1e-30:
            raise ValueError("REC 高度/半轴向量退化")

        def _rec(x, y, z):
            dx, dy, dz = x - vx, y - vy, z - vz
            axial = (dx * hx + dy * hy + dz * hz) / h2
            u = dx * v1x + dy * v1y + dz * v1z
            w = dx * v2x + dy * v2y + dz * v2z
            # 椭圆方程 (dot(P,V1)/|V1|²)² + (dot(P,V2)/|V2|²)² <= 1（|V1|=半轴长）
            inside = (axial >= 0) & (axial <= 1) & (
                (u * u) / (v1l2 * v1l2) + (w * w) / (v2l2 * v2l2) <= 1.0)
            return np.where(inside, -1.0, 1.0)
        return wrap(_rec)

    if t == "ELL":
        v1x, v1y, v1z, v2x, v2y, v2z, rm = p

        def _ell(x, y, z):
            d1 = np.sqrt((x - v1x) ** 2 + (y - v1y) ** 2 + (z - v1z) ** 2)
            d2 = np.sqrt((x - v2x) ** 2 + (y - v2y) ** 2 + (z - v2z) ** 2)
            inside = (d1 + d2) <= 2.0 * rm
            return np.where(inside, -1.0, 1.0)
        return wrap(_ell)

    if t == "BOX":
        v = np.asarray(p[0:3], dtype=float)
        a1 = np.asarray(p[3:6], dtype=float)
        a2 = np.asarray(p[6:9], dtype=float)
        a3 = np.asarray(p[9:12], dtype=float)
        pts = [v, v + a1, v + a1 + a2, v + a2,
               v + a3, v + a1 + a3, v + a1 + a2 + a3, v + a2 + a3]
        faces = [[0, 1, 2, 3], [4, 7, 6, 5],
                 [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]
        return wrap(_polyhedron_field(pts, faces))

    if t == "WED":
        v = np.asarray(p[0:3], dtype=float)
        v1 = np.asarray(p[3:6], dtype=float)
        v2 = np.asarray(p[6:9], dtype=float)
        v3 = np.asarray(p[9:12], dtype=float)
        bot = [v, v + v1, v + v2]
        top = [q + v3 for q in bot]
        pts = bot + top
        faces = [[0, 1, 2], [3, 5, 4],
                 [0, 3, 4, 1], [1, 4, 5, 2], [2, 5, 3, 0]]
        return wrap(_polyhedron_field(pts, faces))

    if t in ("RHP", "HEX"):
        v = np.asarray(p[0:3], dtype=float)
        h = np.asarray(p[3:6], dtype=float)
        r1 = np.asarray(p[6:9], dtype=float)
        hn = float(np.linalg.norm(h))
        if hn < 1e-15:
            raise ValueError("RHP/HEX 高度向量退化")
        k = h / hn
        r2 = np.asarray(p[9:12], dtype=float) if len(p) >= 12 else _rot60(r1, k)
        r3 = np.asarray(p[12:15], dtype=float) if len(p) >= 15 else _rot60(r2, k)
        base = [v + r1, v + r2, v + r3, v - r1, v - r2, v - r3]
        top = [q + h for q in base]
        pts = base + top
        faces = [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9, 10, 11]]
        for i in range(6):
            j = (i + 1) % 6
            faces.append([i, j, j + 6, i + 6])
        return wrap(_polyhedron_field(pts, faces))

    if t == "ARB":
        coords = p[:24]
        face_defs = p[24:30]
        pts = [np.asarray(coords[i * 3:i * 3 + 3], dtype=float) for i in range(8)]
        faces = []
        for fd in face_defs:
            fd_int = int(abs(fd))
            vi = []
            for _ in range(4):
                if fd_int == 0:
                    break
                vi.append((fd_int % 10) - 1)
                fd_int //= 10
            vi.reverse()  # MCNP 编码 MSD 在前，取出的 LSD 在后，需反转
            if len(vi) >= 3:
                faces.append(vi)
        return wrap(_polyhedron_field(pts, faces))

    raise ValueError(f"体素 CSG 暂不支持曲面类型: {t}")


def _ast_surf_nums(ast):
    """递归收集 AST 中引用的曲面号。"""
    if ast[0] == "surf":
        return {ast[1]}
    nums = set()
    for child in ast[1:]:
        if isinstance(child, list):
            nums |= _ast_surf_nums(child)
    return nums


def surface_aabb(surf_type: str, params: list, transform=None):
    """单曲面有界范围。返回 (lo3, hi3, (bx,by,bz)) 或 None（无界/不支持）。

    带 TR 变换的曲面：先求局部 AABB，若三轴均有界则经
    ``_transform_aabb`` 得全局紧盒；无界/退化才回退全盒（保守）。
    """
    if transform is not None:
        local = surface_aabb(surf_type, params, None)
        if local is not None and all(local[2]):
            lo, hi = _transform_aabb(local[0], local[1], transform)
            return lo, hi, (True, True, True)
        return (-1e300, -1e300, -1e300), (1e300, 1e300, 1e300), (True, True, True)
    t = (surf_type or "").upper()
    p = [float(v) for v in params]
    if t == "PX":
        return (p[0], -1e300, -1e300), (p[0], 1e300, 1e300), (True, False, False)
    if t == "PY":
        return (-1e300, p[0], -1e300), (1e300, p[0], 1e300), (False, True, False)
    if t == "PZ":
        return (-1e300, -1e300, p[0]), (1e300, 1e300, p[0]), (False, False, True)
    if t == "SO":
        r = p[0]
        return (-r, -r, -r), (r, r, r), (True, True, True)
    if t == "SX":
        cx, r = p[0], p[1]
        return (cx - r, -r, -r), (cx + r, r, r), (True, True, True)
    if t == "SY":
        cy, r = p[0], p[1]
        return (-r, cy - r, -r), (r, cy + r, r), (True, True, True)
    if t == "SZ":
        cz, r = p[0], p[1]
        return (-r, -r, cz - r), (r, r, cz + r), (True, True, True)
    if t == "S":
        cx, cy, cz, r = p[0], p[1], p[2], p[3]
        return (cx - r, cy - r, cz - r), (cx + r, cy + r, cz + r), (True, True, True)
    if t == "CX":
        r = p[0]
        return (0, -r, -r), (0, r, r), (False, True, True)
    if t == "CY":
        r = p[0]
        return (-r, 0, -r), (r, 0, r), (True, False, True)
    if t == "CZ":
        r = p[0]
        return (-r, -r, 0), (r, r, 0), (True, True, False)
    if t == "C/X":
        y0, z0, r = p[0], p[1], p[2]
        return (0, y0 - r, z0 - r), (0, y0 + r, z0 + r), (False, True, True)
    if t == "C/Y":
        x0, z0, r = p[0], p[1], p[2]
        return (x0 - r, 0, z0 - r), (x0 + r, 0, z0 + r), (True, False, True)
    if t == "C/Z":
        x0, y0, r = p[0], p[1], p[2]
        return (x0 - r, y0 - r, 0), (x0 + r, y0 + r, 0), (True, True, False)
    if t == "RPP":
        xmin, xmax, ymin, ymax, zmin, zmax = p
        return (xmin, ymin, zmin), (xmax, ymax, zmax), (True, True, True)
    if t == "SPH":
        vx, vy, vz, r = p[0], p[1], p[2], p[3]
        return (vx - r, vy - r, vz - r), (vx + r, vy + r, vz + r), (True, True, True)
    if t in ("GQ", "SQ"):
        if t == "SQ":
            p = sq_to_gq(p)
        aabb = gq_aabb(p)
        if aabb:
            lo, hi, axes = aabb
            return lo, hi, axes
        return None
    return None  # 平面 P/P_1、锥 K*、其余宏体 → 无界/不支持


def _surface_negative_aabb(surf_type: str, params: list, transform=None):
    """曲面的负侧（-n）有界范围；无法保守确定 → None。

    封闭曲面（球/椭球/圆柱内/宏体内）的负侧就是曲面内部，沿用 surface_aabb；
    轴对齐平面的负侧取互补半空间；一般平面/锥/无界二次曲面 → None（全盒兜底）。
    """
    if transform is not None:
        local = _surface_negative_aabb(surf_type, params, None)
        if local is not None and all(local[2]):
            lo, hi = _transform_aabb(local[0], local[1], transform)
            return lo, hi, (True, True, True)
        return (-1e300, -1e300, -1e300), (1e300, 1e300, 1e300), (True, True, True)
    t = (surf_type or "").upper()
    p = [float(v) for v in params]
    if t in ("PX", "PY", "PZ"):
        if t == "PX":
            return (-1e300, -1e300, -1e300), (p[0], 1e300, 1e300), (True, False, False)
        if t == "PY":
            return (-1e300, -1e300, -1e300), (1e300, p[0], 1e300), (False, True, False)
        return (-1e300, -1e300, -1e300), (1e300, 1e300, p[0]), (False, False, True)
    if t in ("SO", "SX", "SY", "SZ", "S", "CX", "CY", "CZ",
             "C/X", "C/Y", "C/Z", "RPP", "SPH"):
        return surface_aabb(t, p, None)
    if t in ("GQ", "SQ"):
        if t == "SQ":
            p = sq_to_gq(p)
        return surface_aabb("GQ", p, None)
    return None


def _surface_positive_aabb(surf_type: str, params: list, transform=None):
    """裸曲面引用（MCNP 正侧）的**有界**范围；只有轴对齐平面是单侧半空间。

    球/柱/锥/一般二次曲面/宏体的正侧是"外面"→ 无界，返回 None。这条不能松：
    裸球引用若返回球自身 AABB，壳/外部栅元会被裁到球内（实测 288k 三角形，
    见 test_bare_positive_surface_aabb_is_unbounded）。

    但轴对齐平面的正侧是「x ≥ a」这样的半空间——**一侧有界**，必须给出，
    否则「GQ 无界面 + 两张 PZ 夹住」的薄栅元拿不到 z 紧盒（2026-09-12 实证：
    cell 8 紧盒退化成整个 ±B 盒 → 13mm 体素 → 5mm 薄片直接消失）。
    """
    if transform is not None:
        return None
    t = (surf_type or "").upper()
    p = [float(v) for v in params]
    unb = _AABB_UNBOUNDED
    if t == "PX":
        return (p[0], -unb, -unb), (unb, unb, unb), (True, False, False)
    if t == "PY":
        return (-unb, p[0], -unb), (unb, unb, unb), (False, True, False)
    if t == "PZ":
        return (-unb, -unb, p[0]), (unb, unb, unb), (False, False, True)
    return None


def cell_aabb(ast, surfaces_by_num, B, tr_cards=None):
    """递归计算栅元紧盒。返回 (lo3, hi3, axes3) 或 None（无法确定 → 全盒）。

    带 TR 的曲面由 surface_aabb 保守回退全盒；调用方负责把 ±1e300
    裁剪到实际 bound 盒。

    ``axes[i] == False`` 表示该轴**无界**，此时 lo[i]/hi[i] 只是占位值
    （历史上混用 0 与 ±1e300），不得参与数值 max/min —— 见 _aabb_intersect。
    """
    tag = ast[0]
    if tag == "surf":
        # MCNP 中裸曲面引用 = 曲面的正侧。球/柱/锥/二次曲面的正侧无界 → None
        # （不能返回曲面自身 AABB——否则会把「球外/壳」这类无界栅元裁到曲面
        # 范围内，导致网格只覆盖角部、三角形数量爆炸（实测 288k 三角））。
        # 轴对齐平面的正侧是半空间，一侧有界 → 给出（薄片栅元靠它拿紧盒）。
        s = surfaces_by_num.get(ast[1])
        if s is None:
            return None
        return _surface_positive_aabb(
            s["type"], s["params"], _surface_tr(s, tr_cards))
    if tag == "unary":
        if ast[2] in ("neg", "complement"):
            child = ast[1]
            # 单曲面的负侧：封闭曲面内部有界；复杂表达式保守回退全盒。
            if isinstance(child, list) and child and child[0] == "surf":
                s = surfaces_by_num[child[1]]
                return _surface_negative_aabb(
                    s["type"], s["params"], _surface_tr(s, tr_cards))
            return None  # 补集无界（裁到盒）
        # 正侧：任何曲面的正侧在 R^3 中均无界（曲面本身是零测度集），
        # 不能返回曲面自身 AABB——否则会把「球外/壳」这类无界栅元裁到
        # 曲面范围内，导致网格只覆盖角部、三角形数量爆炸（实测 288k 三角）。
        # 返回 None 后由 _aabb_intersect 取有界伙伴的紧盒，或全盒兜底。
        return None
    if tag == "intersect":
        a = cell_aabb(ast[1], surfaces_by_num, B, tr_cards)
        b = cell_aabb(ast[2], surfaces_by_num, B, tr_cards)
        return _aabb_intersect(a, b)
    if tag == "union":
        a = cell_aabb(ast[1], surfaces_by_num, B, tr_cards)
        b = cell_aabb(ast[2], surfaces_by_num, B, tr_cards)
        return _aabb_union(a, b)
    return None


def _aabb_intersect(a, b):
    """两个紧盒求交；**按 axes 标志位**取边界，占位值不参与比较。

    历史坑（2026-09-12 实证，STEP 导入 GQ 栅元"奇形怪状"/消失的根因）：
    无界轴上的占位值生产者之间不一致 —— ``surface_aabb("CZ")`` 给 z=(0,0)
    而 ``_surface_negative_aabb("PZ")`` 给 x/y=(±1e300)。旧实现直接
    ``max(alo, blo)``/``min(ahi, bhi)``，于是 CZ 的占位 0 把
    「-PZ405」的 z≤405 压成 z∈[0,0] → ``_clip_aabb_to_bound`` 见 hi<=lo
    直接兜底整个 ±B 盒 → 体素边长 13mm（B=846 时）→ 5mm 薄栅元网格为空
    （预览无 STL）、13mm 结构被混叠成胖块。
    """
    if a is None:
        return b
    if b is None:
        return a
    alo, ahi, ax = a
    blo, bhi, bx = b
    lo, hi, bounded = [], [], []
    for i in range(3):
        if ax[i] and bx[i]:
            lo.append(max(alo[i], blo[i]))
            hi.append(min(ahi[i], bhi[i]))
            bounded.append(True)
        elif ax[i]:                      # 只有 a 有界 → 用 a 的边界
            lo.append(alo[i])
            hi.append(ahi[i])
            bounded.append(True)
        elif bx[i]:                      # 只有 b 有界 → 用 b 的边界
            lo.append(blo[i])
            hi.append(bhi[i])
            bounded.append(True)
        else:                            # 两侧都无界 → 该轴无界（哨兵 ±1e300）
            lo.append(-_AABB_UNBOUNDED)
            hi.append(_AABB_UNBOUNDED)
            bounded.append(False)
    return tuple(lo), tuple(hi), tuple(bounded)


def _aabb_union(a, b):
    if a is None or b is None:
        return None
    alo, ahi, ax = a
    blo, bhi, bx = b
    lo, hi, bounded = [], [], []
    for i in range(3):
        if ax[i] and bx[i]:
            lo.append(min(alo[i], blo[i]))
            hi.append(max(ahi[i], bhi[i]))
            bounded.append(True)
        else:                            # 任一侧无界 → 并集该轴无界
            lo.append(-_AABB_UNBOUNDED)
            hi.append(_AABB_UNBOUNDED)
            bounded.append(False)
    return tuple(lo), tuple(hi), tuple(bounded)


def eval_cell_scalar(ast, fns, X, Y, Z):
    """递归求值栅元 **标量** 场（>=0 = 栅元内），供顶点投影用。

    与 ``eval_cell_field`` 的布尔语义逐点一致（intersect=AND / union=OR /
    neg=NOT），只是用 min/max 组合代替按位运算，从而拿到"离边界多远"的标量，
    零等值面即栅元边界 —— 标准 CSG 标量表示。
    """
    tag = ast[0]
    if tag == "intersect":
        return np.minimum(eval_cell_scalar(ast[1], fns, X, Y, Z),
                          eval_cell_scalar(ast[2], fns, X, Y, Z))
    if tag == "union":
        return np.maximum(eval_cell_scalar(ast[1], fns, X, Y, Z),
                          eval_cell_scalar(ast[2], fns, X, Y, Z))
    if tag == "unary":
        s = eval_cell_scalar(ast[1], fns, X, Y, Z)
        return -s if ast[2] in ("neg", "complement") else s
    if tag == "surf":
        return fns[ast[1]](X, Y, Z)
    raise ValueError(f"未知 AST 节点: {tag}")


def project_vertices_to_surface(vertices, ast, fns, spacing, iters: int = 2):
    """把 marching cubes 顶点牛顿投影到真实 CSG 零等值面。

    二值 marching cubes 只保证拓扑正确：顶点落在"最后一个内部采样点与第一个
    外部采样点"的中点 ⇒ 曲面整体内缩最多半个体素。薄栅元受害最重 —— 5mm 厚、
    z 向体素 0.23mm 时体积偏小 ~4.6%（2026-09-12 实测 cell 7/8/9）。
    这里用标量场做 1~2 步牛顿（沿梯度走 s/|∇s|），把顶点贴回真实曲面：
    平面误差直接归零，二次曲面误差降到曲率量级。

    顶点是焊接后的唯一集合，逐点确定性函数 ⇒ 共享顶点仍共享，拓扑/水密性不变。
    """
    v = np.array(vertices, dtype=float)
    if v.size == 0:
        return v
    h = max(float(spacing) * 1e-3, 1e-9)
    lim = 0.5 * float(spacing)          # 限步：防 min/max 折角处跳面
    for _ in range(max(0, int(iters))):
        s = eval_cell_scalar(ast, fns, v[:, 0], v[:, 1], v[:, 2])
        g = np.empty_like(v)
        for k in range(3):
            d = np.zeros(3)
            d[k] = h
            gp = eval_cell_scalar(ast, fns, v[:, 0] + d[0], v[:, 1] + d[1],
                                  v[:, 2] + d[2])
            gm = eval_cell_scalar(ast, fns, v[:, 0] - d[0], v[:, 1] - d[1],
                                  v[:, 2] - d[2])
            g[:, k] = (gp - gm) / (2.0 * h)
        gn = np.einsum("ij,ij->i", g, g)
        good = gn > 1e-300
        if not good.any():
            break
        step = np.zeros_like(v)
        step[good] = (s[good] / gn[good])[:, None] * g[good]
        n = np.linalg.norm(step, axis=1)
        big = n > lim
        if big.any():
            step[big] *= (lim / n[big])[:, None]
        v = v - step
    return v


def eval_cell_field(ast, fns, X, Y, Z):
    """递归求值栅元布尔表达式 → 布尔数组（True = 栅元内）。"""
    tag = ast[0]
    if tag == "intersect":
        return eval_cell_field(ast[1], fns, X, Y, Z) & eval_cell_field(ast[2], fns, X, Y, Z)
    if tag == "union":
        return eval_cell_field(ast[1], fns, X, Y, Z) | eval_cell_field(ast[2], fns, X, Y, Z)
    if tag == "unary":
        field = eval_cell_field(ast[1], fns, X, Y, Z)
        return ~field if ast[2] in ("neg", "complement") else field
    if tag == "surf":
        return fns[ast[1]](X, Y, Z) >= 0.0
    raise ValueError(f"未知 AST 节点: {tag}")


def _clip_aabb_to_bound(aabb, B):
    """把 cell_aabb 结果裁剪到 [-B, B]³，返回 (lo3, hi3)。"""
    if aabb is None:
        return np.array([-B, -B, -B], dtype=float), np.array([B, B, B], dtype=float)
    lo = np.array(aabb[0], dtype=float)
    hi = np.array(aabb[1], dtype=float)
    lo = np.where(np.isfinite(lo), lo, -B)
    hi = np.where(np.isfinite(hi), hi, B)
    lo = np.clip(lo, -B, B)
    hi = np.clip(hi, -B, B)
    if np.any(hi <= lo):
        return np.array([-B, -B, -B], dtype=float), np.array([B, B, B], dtype=float)
    return lo, hi


def _adaptive_res(lo, hi, B):
    """按粗盒 span 选 64/96/128：大 cell 加密，小 cell 保持 64（26ms 实测）。"""
    span = float((hi - lo).max())
    rel = span / (2.0 * B) if B > 0 else 1.0
    if rel < 0.5:
        return 64
    if rel < 0.8:
        return 96
    return 128


# ============================================================
# 切线平面法：可分类凸二次曲面（椭球/球/圆柱，内侧）+ 平面封口
# → 切线半空间 + 凸多面体裁剪，水密 by construction（借鉴 OWEN
#   src/preview/csgScene.ts 的 cylinderTangentPlanes/sphereTangentPlanes/
#   clipBoxByPlanes）。带 union/补集/多个二次曲面/正侧二次曲面 → None，
#   调用方回退 marching cubes。
# ============================================================

def _collect_intersect_halves(ast):
    """收集纯 intersect 树的半空间叶子 → [(曲面号, sense)]（sense: -1=neg 内侧）。

    含 union/complement/嵌套 unary/非 surf 叶子 → 返回 None。
    """
    tag = ast[0]
    if tag == "intersect":
        a = _collect_intersect_halves(ast[1])
        b = _collect_intersect_halves(ast[2])
        if a is None or b is None:
            return None
        return a + b
    if tag == "surf":
        return [(ast[1], +1)]
    if tag == "unary":
        op = ast[2]
        if op not in ("neg", "pos") or ast[1][0] != "surf":
            return None
        return [(ast[1][1], -1 if op == "neg" else +1)]
    return None


def _dedupe_face(face):
    out = []
    for v in face:
        if out and out[-1] == v:
            continue
        if len(out) > 1 and out[0] == v:
            continue
        out.append(v)
    return out


def _clip_box_by_planes(bounds, planes):
    """从 box 开始按半空间 n·p ≤ d 逐次凸裁剪（移植 OWEN clipBoxByPlanes）。

    bounds: (lo3, hi3)；planes: [(n3, d)]。
    返回 {"verts": [[x,y,z]...], "faces": [[idx...]...]} 或 None（区域被裁空）。

    实现：Sutherland–Hodgman——每平面保留内侧顶点 + 边交点，逐面裁剪；
    裁剪面（cap）由交点绕其质心在平面内极角排序得到（凸多边形极角序
    必为正确环序，替代 OWEN 的边链法——边链在细密切线平面下会退化丢面，
    实测 162 面球只收敛出 35 面）。
    """
    (x0, y0, z0), (x1, y1, z1) = bounds
    verts = [
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ]
    faces = [
        [0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
        [2, 3, 7, 6], [1, 2, 6, 5], [0, 4, 7, 3],
    ]
    eps = 1e-9
    for n, d in planes:
        n_arr = np.asarray(n, dtype=float)
        n_len = float(np.linalg.norm(n_arr))
        if n_len < 1e-15:
            continue
        n_arr = n_arr / n_len
        dist = [float(n_arr[0] * v[0] + n_arr[1] * v[1] + n_arr[2] * v[2] - d)
                for v in verts]
        if all(di <= eps for di in dist):
            continue  # 平面不裁任何顶点
        if all(di >= -eps for di in dist):
            return None  # 全部裁掉

        keep_idx = {}
        new_verts = []

        def keep(i):
            if i not in keep_idx:
                keep_idx[i] = len(new_verts)
                new_verts.append(verts[i])
            return keep_idx[i]

        edge_cut = {}

        def cut(i, j):
            # 端点恰在裁剪面上（浮点）：交点就是该顶点本身，用规范索引，
            # 否则盖面用重复顶点、侧面用原顶点 → 拓扑破洞
            if abs(dist[i]) <= eps:
                return keep(i)
            if abs(dist[j]) <= eps:
                return keep(j)
            key = (i, j) if i < j else (j, i)
            if key not in edge_cut:
                t = dist[i] / (dist[i] - dist[j])
                new_verts.append([
                    verts[i][k] + (verts[j][k] - verts[i][k]) * t
                    for k in range(3)
                ])
                edge_cut[key] = len(new_verts) - 1
            return edge_cut[key]

        new_faces = []
        cap_pts = set()
        for face in faces:
            out = []
            for m in range(len(face)):
                cur = face[m]
                nxt = face[(m + 1) % len(face)]
                dc = dist[cur]
                dn = dist[nxt]
                if dc <= eps:
                    out.append(keep(cur))
                if (dc < -eps and dn > eps) or (dc > eps and dn < -eps):
                    ni = cut(cur, nxt)
                    out.append(ni)
                    cap_pts.add(ni)
                elif (abs(dc) <= eps and dn > eps) or (abs(dn) <= eps and dc > eps):
                    # 交点恰为平面上顶点（另一端点严格在外）：该顶点进盖面，
                    # 否则盖面缺交点被丢弃 → 三角形破洞
                    on = cur if abs(dc) <= eps else nxt
                    ni = keep(on)
                    if ni not in out:
                        out.append(ni)
                    cap_pts.add(ni)
            if len(out) >= 3:
                new_faces.append(_dedupe_face(out))

        # 裁剪面（cap）：交点绕其质心在平面内极角排序（凸多边形 → 正确环序）
        if len(cap_pts) >= 3:
            ref = np.array([1.0, 0.0, 0.0]) if abs(n_arr[0]) < 0.9 \
                else np.array([0.0, 1.0, 0.0])
            u_vec = np.cross(n_arr, ref)
            u_vec = u_vec / np.linalg.norm(u_vec)
            v_vec = np.cross(n_arr, u_vec)
            pts = [new_verts[i] for i in cap_pts]
            cen = np.mean(pts, axis=0)
            cap_list = sorted(
                cap_pts,
                key=lambda i: math.atan2(
                    (new_verts[i][0] - cen[0]) * v_vec[0]
                    + (new_verts[i][1] - cen[1]) * v_vec[1]
                    + (new_verts[i][2] - cen[2]) * v_vec[2],
                    (new_verts[i][0] - cen[0]) * u_vec[0]
                    + (new_verts[i][1] - cen[1]) * u_vec[1]
                    + (new_verts[i][2] - cen[2]) * u_vec[2],
                ),
            )
            new_faces.append(cap_list)

        verts = new_verts
        faces = new_faces
        if not verts or not faces:
            return None
    return {"verts": verts, "faces": faces}


def _poly_to_triangles(verts, faces):
    """面列表（多边形）→ 扇形三角化。"""
    tris = []
    for f in faces:
        for k in range(1, len(f) - 1):
            tris.append((f[0], f[k], f[k + 1]))
    return tris


def _orient_polyhedron_faces(verts, faces):
    """凸多面体逐面定向：面法向朝外（面心 − 体心 方向）。

    `_clip_box_by_planes` 的面绕序是裁剪簿记的产物，可能混合 CW/CCW；
    凸多面体下体心在内部，面心在边界，法向·(面心−体心)>0 即朝外。
    """
    arr = np.asarray(verts, dtype=float)
    center = arr.mean(axis=0)
    out = []
    for f in faces:
        pts = arr[f]
        if len(f) < 3:
            continue
        nrm = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        if np.dot(nrm, pts.mean(axis=0) - center) < 0:
            out.append(list(reversed(f)))
        else:
            out.append(list(f))
    return out


def _plane_halfspace(surface, sense):
    """平面曲面 → (n, d) 半空间（n·p ≤ d 为内侧）。sense: -1=neg（f<0）。

    与 surface_fn 的 PX/PY/PZ/P_0/P_1 正侧约定一致。
    """
    t = (surface.get("type") or "").upper()
    p = [float(v) for v in surface.get("params", [])]
    # sense -1 = neg（f<0 内侧）→ 半空间 n·p ≤ d 取 n=+法向、d=+常量；
    # sense +1 = pos（f>0 内侧）→ 取 n=−法向、d=−常量。
    sgn = 1.0 if sense == -1 else -1.0
    if t == "PX":
        n = [sgn, 0.0, 0.0]
        d = sgn * p[0]
    elif t == "PY":
        n = [0.0, sgn, 0.0]
        d = sgn * p[0]
    elif t == "PZ":
        n = [0.0, 0.0, sgn]
        d = sgn * p[0]
    elif t == "P_0":
        n = [sgn * p[0], sgn * p[1], sgn * p[2]]
        d = sgn * p[3]
    elif t == "P_1":
        x1, y1, z1, x2, y2, z2, x3, y3, z3 = p
        ax = x2 - x1
        ay = y2 - y1
        az = z2 - z1
        bx = x3 - x1
        by = y3 - y1
        bz = z3 - z1
        nx = ay * bz - az * by
        ny = az * bx - ax * bz
        nz = ax * by - ay * bx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz)
        if ln < 1e-15:
            return None
        nx /= ln
        ny /= ln
        nz /= ln
        n = [sgn * nx, sgn * ny, sgn * nz]
        d = sgn * (nx * x1 + ny * y1 + nz * z1)
    else:
        return None
    return (n, d)


def _transform_halfspace(hp, transform):
    """局部半空间 n·p ≤ d → 全局（TR：p_local=(p_global−o)·R⁻¹）。

    推导：n·((p−o)·R⁻¹) ≤ d ⇔ (R⁻¹n)·p ≤ d + (R⁻¹n)·o。
    """
    n, d = hp
    origin = np.asarray(transform.get("translate", [0, 0, 0]), dtype=float).ravel()
    rotate = np.asarray(
        transform.get("rotate", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]), dtype=float
    )
    try:
        r_inv = np.linalg.inv(rotate)
    except np.linalg.LinAlgError:
        r_inv = rotate.T
    n_g = r_inv @ np.asarray(n, dtype=float)
    d_g = float(d + float(n_g @ origin))
    return (n_g.tolist(), d_g)


def _ellipsoid_tangent_planes(info, subdiv: int = 3):
    """椭球（含球）切线半空间：二十面体细分方向 + 支撑函数 h(n)=√(Σ(s_i·n_i)²)。

    subdiv=3 → 642 方向，外接多面体体积误差 ~0.5%（162 方向时 ~2.1%，
    超 1% 门禁；金螺旋分布不均弃用）。
    """
    c = np.asarray(info["center"], dtype=float)
    s = np.asarray(info["semiaxes"], dtype=float)
    planes = []
    for n in _icosphere_dirs(subdiv):
        h = float(np.sqrt(max(1e-300, float(np.sum((s * n) ** 2)))))
        d = float(n @ c) + h
        planes.append((n.tolist(), d))
    return planes


def _icosphere_dirs(subdiv: int = 2):
    """正二十面体细分 → 单位方向（均匀分布，供切线平面法用）。

    subdiv=0 → 12 方向；每级 4 倍。subdiv=2 → 162 方向，外接多面体体积
    误差 <0.3%（金螺旋在本场景分布不均，顶点半径会到 1.08r+，弃用）。
    """
    t = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
    ]
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]
    varr = [np.array(v, dtype=float) for v in verts]
    for _ in range(max(0, int(subdiv))):
        mid_cache = {}

        def midpoint(i, j):
            key = (i, j) if i < j else (j, i)
            if key not in mid_cache:
                mid_cache[key] = len(varr)
                m = (varr[i] + varr[j]) / 2.0
                m = m / np.linalg.norm(m)
                varr.append(m)
            return mid_cache[key]

        new_faces = []
        for a, b, c in faces:
            ab = midpoint(a, b)
            bc = midpoint(b, c)
            ca = midpoint(c, a)
            new_faces.extend([(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)])
        faces = new_faces
    out = []
    seen = set()
    for v in varr:
        k = (round(v[0], 12), round(v[1], 12), round(v[2], 12))
        if k not in seen:
            seen.add(k)
            out.append(v / np.linalg.norm(v))
    return out


def _cylinder_tangent_planes(info, segments):
    """圆柱（圆/椭圆截面）切线半空间：绕轴线 N 个方向 + 支撑/中点半径。"""
    c = np.asarray(info["center"], dtype=float)
    axis = np.asarray(info["axis"], dtype=float)
    axis = axis / np.linalg.norm(axis)
    r1, r2 = info["radii"]
    # 正交基 (u, v, axis)
    ref = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, ref)
    u = u / np.linalg.norm(u)
    v = np.cross(axis, u)
    planes = []
    for s in range(segments):
        ang = ((s + 0.5) / segments) * 2 * math.pi
        cu = math.cos(ang)
        cv = math.sin(ang)
        n = cu * u + cv * v
        # 圆截面用中点半径；椭圆截面用支撑函数
        if abs(r1 - r2) < 1e-9:
            r = float(r1)
            r_eff = r * (1 + 1 / math.cos(math.pi / segments)) / 2
            d = float(n @ c) + r_eff
        else:
            h = float(np.sqrt(max(1e-300, (r1 * cu) ** 2 + (r2 * cv) ** 2)))
            d = float(n @ c) + h
        planes.append((n.tolist(), d))
    return planes


def _tangent_plane_mesh(ast, surfaces_by_num, tr_cards, B, segments: int = 48):
    """切线平面法快路径：单个内侧椭球/圆柱 + 平面封口 → (vertices, triangles)。

    不满足模式（union/补集/多二次曲面/正侧二次曲面/锥/退化）→ None，
    调用方回退 marching cubes。
    """
    try:
        halves = _collect_intersect_halves(ast)
        if halves is None:
            return None
        quadric_h = []
        plane_h = []
        for num, sense in halves:
            s = surfaces_by_num.get(num)
            if s is None:
                return None
            t = (s.get("type") or "").upper()
            if t in ("GQ", "SQ"):
                quadric_h.append((num, sense))
            elif t in ("PX", "PY", "PZ", "P_0", "P_1"):
                plane_h.append((num, sense))
            else:
                return None
        if len(quadric_h) != 1 or len(plane_h) + 1 != len(halves):
            return None
        qnum, qsense = quadric_h[0]
        if qsense != -1:
            return None  # 正侧无界，不适用
        qsurf = surfaces_by_num[qnum]
        coeffs = [float(v) for v in qsurf["params"]]
        if (qsurf.get("type") or "").upper() == "SQ":
            coeffs = sq_to_gq(coeffs)
        info = classify_gq(coeffs)
        kind = info.get("kind")
        if kind == "ellipsoid":
            if plane_h:
                # 有平面封口：区域体积≠整椭球，无法用体积校正 →
                # 642 方向外接误差 ~0.5%（可直接过 1%/2% 门禁）
                planes = _ellipsoid_tangent_planes(info, 3)
            else:
                planes = _ellipsoid_tangent_planes(info, 2)  # 162 方向（~0.1s）
        elif kind == "cylinder_elliptic":
            planes = _cylinder_tangent_planes(info, 48)
        else:
            return None  # 锥/双曲面/抛物面等 → MC
        # 二次曲面切线半空间按二次曲面自身 TR 变换
        qtr = _surface_tr(qsurf, tr_cards)
        if qtr is not None:
            planes = [_transform_halfspace(p, qtr) for p in planes]
        # 平面封口按各自 TR 变换（无 TR 的平面保持局部系）
        for num, sense in plane_h:
            hp = _plane_halfspace(surfaces_by_num[num], sense)
            if hp is None:
                return None
            ptr = _surface_tr(surfaces_by_num[num], tr_cards)
            if ptr is not None:
                hp = _transform_halfspace(hp, ptr)
            planes.append(hp)

        aabb = cell_aabb(ast, surfaces_by_num, B, tr_cards)
        lo, hi = _clip_aabb_to_bound(aabb, B)
        span = float((hi - lo).max())
        margin = max(span * 0.02, 1e-6)
        poly = _clip_box_by_planes(
            ((lo[0] - margin, lo[1] - margin, lo[2] - margin),
             (hi[0] + margin, hi[1] + margin, hi[2] + margin)),
            planes,
        )
        if poly is None or len(poly["verts"]) < 4:
            return None
        faces = _orient_polyhedron_faces(poly["verts"], poly["faces"])
        if not faces:
            return None
        tris = _poly_to_triangles(poly["verts"], faces)
        if not tris:
            return None
        verts_arr = np.array(poly["verts"], dtype=float)
        tri_arr = np.array(tris, dtype=np.int64)
        if kind == "ellipsoid" and not plane_h:
            # 体积校正：162 方向外接多面体体积偏高 ~2.1%（超 1% 门禁），
            # 绕椭球全局中心径向缩放 λ=(V_true/V_mesh)^(1/3) 使体积精确
            # （缩放绕中心 → 体积 λ³ 倍；穿过中心的封口平面保持原位）。
            a0 = verts_arr[tri_arr[:, 0]]
            a1 = verts_arr[tri_arr[:, 1]]
            a2 = verts_arr[tri_arr[:, 2]]
            v_mesh = float(np.einsum("ij,ij->i", a0, np.cross(a1, a2)).sum() / 6.0)
            if abs(v_mesh) > 1e-12:
                sa = info["semiaxes"]
                v_true = 4.0 / 3.0 * math.pi * sa[0] * sa[1] * sa[2]
                lam = (abs(v_true / v_mesh)) ** (1.0 / 3.0)
                center_g = np.asarray(info["center"], dtype=float)
                if qtr is not None:
                    origin = np.asarray(
                        qtr.get("translate", [0, 0, 0]), dtype=float
                    ).ravel()
                    rotate = np.asarray(
                        qtr.get("rotate", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
                        dtype=float,
                    )
                    center_g = origin + center_g @ rotate
                verts_arr = center_g + lam * (verts_arr - center_g)
        return verts_arr, tri_arr
    except Exception as e:
        # 切线平面法快路径异常 → 记录原因后回退 marching cubes（保留回退行为）。
        logger.warning("切线平面法快路径失败，回退 marching cubes: %s", e)
        return None


def mesh_cell_polydata(ast, surfaces_by_num, tr_cards, B, res: int = None):
    """体素求值栅元并提取水密三角形网格（纯 numpy，无 vtk）。

    surfaces_by_num: {num: {"type":..., "params":[...], "transform": trn?}}
    tr_cards: {trn: {"translate": [...], "rotate": [[...],...]}}
    返回 ``(vertices, triangles)``：
      vertices  (N,3) float64
      triangles (M,3) int64（空栅元时两个数组均为 shape (0,3)）

    两遍：先在包围盒上粗扫定位栅元 AABB（带 TR 曲面保守全盒），再在
    紧盒子内按 cell span 自适应 64/96/128 细化；32³ 粗扫找不到时用
    cell_aabb 紧盒兜底再扫一遍。
    """
    # 新签名 mesh_cell_polydata(ast, surfaces_by_num, tr_cards, B, res)：全部调用方
    # 已迁移（grep 全仓库确认无旧签名「第三参=bound 数值」调用方），旧 shim 已移除。
    tr_cards = tr_cards or {}

    # 切线平面法快路径：单个内侧椭球/球/圆柱 + 平面封口 → 水密光滑多面体
    # （免 marching cubes，三角形数少一个数量级）；不匹配 → None → 走 MC。
    tp = _tangent_plane_mesh(ast, surfaces_by_num, tr_cards, B)
    if tp is not None:
        return tp

    nums = _ast_surf_nums(ast)
    fns = {}
    for n in nums:
        s = surfaces_by_num[n]
        fns[n] = surface_fn(s["type"], s["params"], _surface_tr(s, tr_cards))

    def inside_world(x, y, z):
        return eval_cell_field(ast, fns, x, y, z)

    # 第一遍：全 bound 盒粗扫定位栅元范围（不用 cell_aabb 当粗扫盒：
    # 对「正侧无界曲面」cell_aabb 可能只给出曲面范围，会把无界栅元裁小）。
    coarse = 32
    scan_lo = np.array([-B, -B, -B], dtype=float)
    scan_hi = np.array([B, B, B], dtype=float)
    lo = scan_lo.copy()
    hi = scan_hi.copy()
    xs0 = np.linspace(scan_lo[0], scan_hi[0], coarse)
    ys0 = np.linspace(scan_lo[1], scan_hi[1], coarse)
    zs0 = np.linspace(scan_lo[2], scan_hi[2], coarse)
    X0, Y0, Z0 = np.meshgrid(xs0, ys0, zs0, indexing="ij")
    field0 = inside_world(X0, Y0, Z0)
    idx = np.argwhere(field0)

    if idx.size == 0:
        # 粗网格漏检（薄壳/细小栅元）：用 cell_aabb 紧盒再扫；仍找不到则
        # 直接把该紧盒作为细化盒兜底（marching cubes 空场会自然返回空网格）。
        aabb = cell_aabb(ast, surfaces_by_num, B, tr_cards)
        scan_lo, scan_hi = _clip_aabb_to_bound(aabb, B)
        lo = scan_lo.copy()
        hi = scan_hi.copy()
        xs0 = np.linspace(scan_lo[0], scan_hi[0], coarse)
        ys0 = np.linspace(scan_lo[1], scan_hi[1], coarse)
        zs0 = np.linspace(scan_lo[2], scan_hi[2], coarse)
        X0, Y0, Z0 = np.meshgrid(xs0, ys0, zs0, indexing="ij")
        field0 = inside_world(X0, Y0, Z0)
        idx = np.argwhere(field0)
        if idx.size == 0:
            if aabb is None:
                return np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=np.int64)
            # 紧盒兜底：不再依赖粗扫命中
            idx = None
            lo = scan_lo.copy()
            hi = scan_hi.copy()

    if idx is None:
        # 紧盒兜底路径：lo/hi 已来自 cell_aabb（保守含栅元）
        pass
    else:
        lo = np.array([xs0[idx[:, 0].min()], ys0[idx[:, 1].min()], zs0[idx[:, 2].min()]])
        hi = np.array([xs0[idx[:, 0].max()], ys0[idx[:, 1].max()], zs0[idx[:, 2].max()]])

    # ── 细化盒 = (命中盒 + 粗扫余量) ∩ 解析紧盒 ──
    # 顺序很重要：命中盒只保证「不漏」，粗扫间距那一格必须补上（真曲面可能
    # 距最近内部粗点整整一格）；补完之后盒子仍是保守超集，此时再与解析紧盒
    # （cell_aabb，同为保守超集）取交才是安全的收紧。
    # 反例（2026-09-12 实测 cell 9）：先取交再补 margin 时，命中盒 z 退化成
    # 一个粗扫层(409.2) → 取交看不出变化 → margin 又把 z 撑成 ±60mm →
    # 分辨率全花在空处 → 5mm 薄片厚度只剩 3.8mm、体积 −24%。
    coarse_step = (scan_hi - scan_lo).max() / (coarse - 1)
    span_hit = (hi - lo).max()
    if span_hit < 1e-12:
        span_hit = max(hi.max() - lo.min(), coarse_step, 1e-9)
    margin_hit = max(span_hit * 0.05, coarse_step * 1.1) + 1e-9
    lo = lo - margin_hit
    hi = hi + margin_hit

    tightened = False
    a_lo, a_hi = _clip_aabb_to_bound(
        cell_aabb(ast, surfaces_by_num, B, tr_cards), B)
    cand_lo = np.maximum(lo, a_lo)
    cand_hi = np.minimum(hi, a_hi)
    if np.all(cand_hi > cand_lo):
        tightened = bool(np.any(cand_lo > lo) or np.any(cand_hi < hi))
        lo, hi = cand_lo, cand_hi

    if tightened:
        # 解析盒已收紧：只需 5% 余量，防解析边界与真实曲面恰好重合被裁掉。
        span = (hi - lo).max()
        extra = span * 0.05 + 1e-9
        lo = lo - extra
        hi = hi + extra
    lo = np.clip(lo, -B, B)
    hi = np.clip(hi, -B, B)

    # 第二遍：紧盒子内细化（无 TR 时 cell span 小用 64，大 cell 自动加密）
    if res is None:
        res = _adaptive_res(lo, hi, B)
    res = max(8, int(res))
    pad = 1
    xs = np.linspace(lo[0], hi[0], res)
    dx = xs[1] - xs[0]
    ys = np.linspace(lo[1], hi[1], res)
    dy = ys[1] - ys[0]
    zs = np.linspace(lo[2], hi[2], res)
    dz = zs[1] - zs[0]
    xp = np.concatenate([[xs[0] - dx], xs, [xs[-1] + dx]])
    yp = np.concatenate([[ys[0] - dy], ys, [ys[-1] + dy]])
    zp = np.concatenate([[zs[0] - dz], zs, [zs[-1] + dz]])
    X, Y, Z = np.meshgrid(xp, yp, zp, indexing="ij")
    # 裁剪到紧盒 [lo, hi]：无界/补集栅元在 padding 层强制为外，保证提取
    # 的是 cell ∩ tight-box 的闭合边界（外盒面水密）。
    in_tight = ((X >= xs[0]) & (X <= xs[-1])
                & (Y >= ys[0]) & (Y <= ys[-1])
                & (Z >= zs[0]) & (Z <= zs[-1]))
    field = inside_world(X, Y, Z) & in_tight
    region = np.where(field, 1, 0).astype(np.uint8)

    def inside_clipped(x, y, z):
        return (inside_world(x, y, z)
                & (x >= xs[0]) & (x <= xs[-1])
                & (y >= ys[0]) & (y <= ys[-1])
                & (z >= zs[0]) & (z <= zs[-1]))

    vertices, triangles = marching_cubes(region, xp, yp, zp,
                                         inside_fn=inside_clipped)
    # 顶点贴回真实曲面（修二值 MC 的半体素内缩；拓扑/焊接在 MC 内已完成，
    # 这里只挪位置）。被紧盒裁剪的栅元例外：贴面会让裁剪面顶点乱跑 ——
    # 只贴"没有落在紧盒边界上"的顶点。
    if len(vertices):
        move = ~(
            np.isclose(vertices[:, 0], xs[0]) | np.isclose(vertices[:, 0], xs[-1])
            | np.isclose(vertices[:, 1], ys[0]) | np.isclose(vertices[:, 1], ys[-1])
            | np.isclose(vertices[:, 2], zs[0]) | np.isclose(vertices[:, 2], zs[-1])
        )
        if move.any():
            spacing = min(abs(dx), abs(dy), abs(dz))
            vertices[move] = project_vertices_to_surface(
                vertices[move], ast, fns, spacing)
    return vertices, triangles
