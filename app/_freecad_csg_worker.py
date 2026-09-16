"""
FreeCAD CSG Worker — 在 FreeCAD Python 环境中运行的几何构建脚本。

由 freecad_preview.py 通过子进程调用 (freecad_bin/python.exe)。
协议: stdin JSON → 几何构建 → 输出文件 (.stl/.step) → stdout JSON 结果

与主进程隔离: 不导入 app 的任何模块。
"""

import sys
import json
import os
import math
import tempfile

# ============================================================
# FreeCAD 环境初始化
# ============================================================
try:
    import FreeCAD
    import Part
    import Mesh as FcMesh
    import Import
    import numpy as np
except ImportError as e:
    # FreeCAD 不可用时的错误报告
    print(json.dumps({"status": "error", "message": f"FreeCAD 导入失败: {e}"}))
    sys.exit(1)

try:
    from quadric import (sq_to_gq, cone_frame, plane_from_points, torus_params,
                         ellipsoid_field_fn, point_surface_field_fn,
                         arb_face_indices, rec_params, rhp_params, box_params,
                         rot60)
except ImportError:  # 测试/直接 import app 包时 quadric 在 app/ 下
    from app.quadric import (sq_to_gq, cone_frame, plane_from_points, torus_params,
                             ellipsoid_field_fn, point_surface_field_fn,
                             arb_face_indices, rec_params, rhp_params, box_params,
                             rot60)

try:
    import voxel_csg
except ImportError:  # 测试/直接 import app 包时 voxel_csg 在 app/ 下
    from app import voxel_csg

try:
    import mc as _mc
except ImportError:  # 测试/直接 import app 包时 mc 在 app/ 下
    from app import mc as _mc

try:
    from spatial_index import grid_candidates
    from overlap_classify import cap_by_bbox_volume, classify_overlaps
    from overlap_probe import sample_overlap
except ImportError:  # 测试/直接 import app 包时在 app/ 下
    from app.spatial_index import grid_candidates
    from app.overlap_classify import cap_by_bbox_volume, classify_overlaps
    from app.overlap_probe import sample_overlap

# GQ/SQ 曲面不再依赖 vtk：体素 marching cubes 由 app/mc.py 纯 numpy 实现。



# ============================================================
# 辅助工具
# ============================================================

def _vec(x, y, z):
    return FreeCAD.Vector(x, y, z)


def _make_box(xmin, xmax, ymin, ymax, zmin, zmax):
    """创建轴对齐长方体"""
    return Part.makeBox(xmax - xmin, ymax - ymin, zmax - zmin,
                        _vec(xmin, ymin, zmin))


def _triangles_to_fcmesh(vertices, triangles):
    """numpy 三角形数组 → FreeCAD Mesh（顶点/三角面直接写入）。"""
    mesh = FcMesh.Mesh()
    # bulk addFacets: 120k triangles 0.33s vs per-facet addFacet 45s (140x)
    facets = []
    for tri in triangles:
        i1, i2, i3 = (int(tri[0]), int(tri[1]), int(tri[2]))
        facets.append((
            _vec(float(vertices[i1][0]), float(vertices[i1][1]), float(vertices[i1][2])),
            _vec(float(vertices[i2][0]), float(vertices[i2][1]), float(vertices[i2][2])),
            _vec(float(vertices[i3][0]), float(vertices[i3][1]), float(vertices[i3][2])),
        ))
    if facets:
        mesh.addFacets(facets)
    return mesh


# ============================================================
# 曲面 → FreeCAD Part.Shape 半空间
# ============================================================

def _plane_halfspace(normal, point, B: float):
    """一般平面 n·x = n·point 的正侧半空间实体（n·x > n·point，限制在 [-B,B]³）。"""
    bb = _make_box(-B, B, -B, B, -B, B)
    n = normal.normalize()
    if n.Length < 1e-15:
        return bb
    p = FreeCAD.Vector(point[0], point[1], point[2])
    # 厚板：4B×4B×2B 盒（角在原点，几何中心 (2B,2B,B)），旋转 z→n，底面(z=0)落在平面 p 上
    z = FreeCAD.Vector(0, 0, 1)
    axis = z.cross(n)
    if axis.Length < 1e-15:
        rot = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 180) if n.z < 0 else FreeCAD.Rotation()
    else:
        angle = math.degrees(math.acos(max(-1.0, min(1.0, n.z))))
        rot = FreeCAD.Rotation(axis, angle)
    slab = Part.makeBox(4 * B, 4 * B, 2 * B)
    c0 = FreeCAD.Vector(2 * B, 2 * B, B)  # 几何中心（局部）
    target = p + n * B                      # 盒子中心目标（底面 z=0 → p，顶面 → p+2B·n）
    base = target - rot.multVec(c0)         # Placement 的 Base
    slab.Placement = FreeCAD.Placement(base, rot)
    return bb.common(slab)


def _make_cone_halfspace(surf_type: str, params: list[float], B: float):
    """圆锥「正侧」半空间（= 所选叶片之外）。

    几何骨架（顶点/轴/半开角/叶片）取自 ``quadric.cone_frame`` —— 与体素求值
    ``voxel_csg.surface_fn`` 同一真源，避免两处各写一套而漂移：
      * KX/KY/KZ：顶点在该轴坐标上、另两轴为 0；K/X K/Y K/Z：顶点为卡片前三项；
      * 半径 r(u) = t·|u| = √(t²)·|u|（**不是** 1/√(t²)·|u|）；
      * ±1 单叶：只挖所选那一叶；省略 ±1（0）：挖双叶。

    正侧 = 盒 − 所选叶片实体：叶片内部为负侧，另一叶与顶点平面外侧都落在正侧。
    """
    fr = cone_frame(surf_type, params)
    box = _make_box(-B, B, -B, B, -B, B)
    t2 = float(fr.t_squared)
    if t2 <= 0:
        return box  # 退化（t² ≤ 0 → 只剩轴线）：正侧近似全空间（与旧行为一致）
    axis_dir = _vec(1.0 if fr.axis == 0 else 0.0,
                    1.0 if fr.axis == 1 else 0.0,
                    1.0 if fr.axis == 2 else 0.0)
    apex = _vec(*fr.apex)
    tan_half = math.sqrt(t2)
    # 高度取 3B + 顶点偏移量：无论顶点落在盒内还是盒外，锥体都足以穿透整个 [-B,B]³
    length = 3.0 * B + sum(abs(float(v)) for v in fr.apex)
    sheets = ((1.0,) if fr.sheet > 0
              else (-1.0,) if fr.sheet < 0
              else (1.0, -1.0))
    shape = box
    for s in sheets:
        cone = Part.makeCone(0.0, tan_half * length, length, apex, axis_dir * s)
        shape = shape.cut(cone)
    return shape


def make_halfspace(surf_type: str, params: list[float], B: float = 500):
    """
    为 MCNP 曲面类型创建"正侧 (pos)"半空间形状。

    正侧含义:
      平面 PX/PY/PZ: 法向量指向的半空间 (x>D / y>D / z>D)
      球/圆柱/一般封闭曲面: 外侧 (球外/柱外)
      封闭体 (RPP/SPH/RCC): 外侧壳体

    Args:
        surf_type: MCNP 曲面助记符 (如 "PZ", "CZ", "RCC")
        params: 曲面的几何参数列表
        B: 包围盒半边长 (BOUND)

    Returns:
        Part.Shape — 正侧半空间的形状
    """
    # ── 轴对齐平面 ──
    if surf_type == "PX":
        return _make_box(params[0], B, -B, B, -B, B)
    elif surf_type == "PY":
        return _make_box(-B, B, params[0], B, -B, B)
    elif surf_type == "PZ":
        return _make_box(-B, B, -B, B, params[0], B)

    # ── 一般平面 P (4参数: A B C D) ──
    elif surf_type == "P_0":
        A, Bc, C, D = params
        normal = FreeCAD.Vector(A, Bc, C)
        if abs(A) > 1e-15:
            pt = (D / A, 0, 0)
        elif abs(Bc) > 1e-15:
            pt = (0, D / Bc, 0)
        else:
            pt = (0, 0, D / C)
        return _plane_halfspace(normal, pt, B)

    # ── 三点定义平面 P_1 ──
    elif surf_type == "P_1":
        # C810 §3-17 感度规则统一由 quadric.plane_from_points 决定
        # （旧实现 edge1×edge2 原始叉积 → 感度随点序翻转）
        A, Bc, C, D = plane_from_points(params)
        nrm = FreeCAD.Vector(A, Bc, C)
        nn = nrm.Length
        if nn < 1e-15:
            return _make_box(-B, B, -B, B, -B, B)
        pt = nrm * (D / (nn * nn))   # 平面上离原点最近的点
        return _plane_halfspace(nrm, (pt.x, pt.y, pt.z), B)

    # ── 球 ──
    elif surf_type == "SO":
        R = params[0]
        sphere = Part.makeSphere(R)
        return _make_box(-B, B, -B, B, -B, B).cut(sphere)

    elif surf_type == "S":
        cx, cy, cz, R = params
        sphere = Part.makeSphere(R)
        sphere.translate(_vec(cx, cy, cz))
        return _make_box(-B, B, -B, B, -B, B).cut(sphere)

    elif surf_type in ("SX",):
        cx, R = params[0], params[1]
        sphere = Part.makeSphere(R)
        sphere.translate(_vec(cx, 0, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(sphere)

    elif surf_type in ("SY",):
        cy, R = params[0], params[1]
        sphere = Part.makeSphere(R)
        sphere.translate(_vec(0, cy, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(sphere)

    elif surf_type in ("SZ",):
        cz, R = params[0], params[1]
        sphere = Part.makeSphere(R)
        sphere.translate(_vec(0, 0, cz))
        return _make_box(-B, B, -B, B, -B, B).cut(sphere)

    # ── 轴对齐圆柱 (CX/CY/CZ) ──
    elif surf_type == "CX":
        R = params[0]
        cyl = Part.makeCylinder(R, B * 2, _vec(-B, 0, 0), _vec(1, 0, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(cyl)

    elif surf_type == "CY":
        R = params[0]
        cyl = Part.makeCylinder(R, B * 2, _vec(0, -B, 0), _vec(0, 1, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(cyl)

    elif surf_type == "CZ":
        R = params[0]
        cyl = Part.makeCylinder(R, B * 2, _vec(0, 0, -B), _vec(0, 0, 1))
        return _make_box(-B, B, -B, B, -B, B).cut(cyl)

    # ── 平行轴圆柱 (C/X C/Y C/Z) ──
    elif surf_type == "C/X":
        y0, z0, R = params  # 轴通过 (0, y0, z0) 平行于 X
        cyl = Part.makeCylinder(R, B * 2, _vec(-B, y0, z0), _vec(1, 0, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(cyl)

    elif surf_type == "C/Y":
        x0, z0, R = params
        cyl = Part.makeCylinder(R, B * 2, _vec(x0, -B, z0), _vec(0, 1, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(cyl)

    elif surf_type == "C/Z":
        x0, y0, R = params
        cyl = Part.makeCylinder(R, B * 2, _vec(x0, y0, -B), _vec(0, 0, 1))
        return _make_box(-B, B, -B, B, -B, B).cut(cyl)


    # ── 圆锥 (KX/KY/KZ 与 K/X K/Y K/Z) ──
    elif surf_type in ("KX", "KY", "KZ", "K/X", "K/Y", "K/Z"):
        return _make_cone_halfspace(surf_type, params, B)

    # ── 环面 ──
    elif surf_type in ("TX", "TY", "TZ"):
        return _make_torus_halfspace(surf_type, params, B)

    # ── Macrobody ──
    elif surf_type == "RPP":
        xmin, xmax, ymin, ymax, zmin, zmax = params
        inner = _make_box(xmin, xmax, ymin, ymax, zmin, zmax)
        return _make_box(-B, B, -B, B, -B, B).cut(inner)

    elif surf_type == "SPH":
        vx, vy, vz, R = params
        sphere = _make_solid_sphere(R, _vec(vx, vy, vz))
        return _make_box(-B, B, -B, B, -B, B).cut(sphere)

    elif surf_type == "RCC":
        vx, vy, vz, hx, hy, hz, R = params
        H = math.sqrt(hx ** 2 + hy ** 2 + hz ** 2)
        if H < 1e-15:
            return _make_box(-B, B, -B, B, -B, B)
        cyl = Part.makeCylinder(R, H, _vec(0, 0, 0), _vec(0, 0, 1))
        _orient_shape(cyl, _vec(0, 0, 1), _vec(hx, hy, hz))
        cyl.translate(_vec(vx, vy, vz))  # base at V, top at V+H
        return _make_box(-B, B, -B, B, -B, B).cut(cyl)

    elif surf_type == "TRC":
        vx, vy, vz, hx, hy, hz, r1, r2 = params
        H = math.sqrt(hx ** 2 + hy ** 2 + hz ** 2)
        if H < 1e-15:
            return _make_box(-B, B, -B, B, -B, B)
        cone = Part.makeCone(r1, r2, H, _vec(0, 0, 0), _vec(0, 0, 1))
        _orient_shape(cone, _vec(0, 0, 1), _vec(hx, hy, hz))
        cone.translate(_vec(vx, vy, vz))  # base at V, top at V+H
        return _make_box(-B, B, -B, B, -B, B).cut(cone)

    elif surf_type == "REC":
        return _make_rec(params, B)

    elif surf_type == "ELL":
        return _make_ellipsoid(params, B)

    elif surf_type == "WED":
        wedge = _make_wedge_from_vectors(params)
        if wedge:
            return _make_box(-B, B, -B, B, -B, B).cut(wedge)
        return _make_box(-B, B, -B, B, -B, B)

    elif surf_type == "BOX":
        box = _make_box_from_vectors(params)
        if box:
            return _make_box(-B, B, -B, B, -B, B).cut(box)
        return _make_box(-B, B, -B, B, -B, B)

    elif surf_type == "ARB":
        arb = _make_arb_from_vertices(params)
        if arb:
            return _make_box(-B, B, -B, B, -B, B).cut(arb)
        return _make_box(-B, B, -B, B, -B, B)

    elif surf_type in ("RHP", "HEX"):
        prism = _make_hex_from_params(params)
        if prism:
            return _make_box(-B, B, -B, B, -B, B).cut(prism)
        return _make_box(-B, B, -B, B, -B, B)

    # ── GQ / SQ (VTK marching cubes) ──
    elif surf_type == "GQ":
        return _quadric_to_shape("gq", params, B)

    elif surf_type == "SQ":
        return _quadric_to_shape("sq", params, B)

    # ── 点定义旋转体: X / Y / Z ──
    elif surf_type in ("X", "Y", "Z"):
        return _point_surf_to_shape(surf_type, params, B)

    else:
        raise ValueError(f"不支持的曲面类型: {surf_type}")


# ============================================================
# 辅助几何工具
# ============================================================

def _orient_shape(shape, from_dir, to_dir):
    """将 shape 从 Z 轴 (from_dir) 旋转到 to_dir 方向"""
    f = from_dir.normalize()
    t = to_dir.normalize()
    cross = f.cross(t)
    if cross.Length < 1e-15:
        return  # 同向，无需旋转
    angle = math.degrees(math.acos(max(-1, min(1, f.dot(t)))))
    shape.rotate(_vec(0, 0, 0), cross, angle)


def _make_wedge(vx, vy, vz, v1x, v1y, v1z, v2x, v2y, v2z, v3x, v3y, v3z):
    """创建楔形体 Wedge"""
    # WED = 底面三角形 V - V1 - V2, 高度沿 V3
    base_pts = [
        FreeCAD.Vector(0, 0, 0),
        FreeCAD.Vector(v1x, v1y, v1z),
        FreeCAD.Vector(v2x, v2y, v2z),
    ]
    # 计算高度
    h_vec = FreeCAD.Vector(v3x, v3y, v3z)
    h = h_vec.Length
    if h < 1e-15:
        return None

    # 创建在 XY 平面上的三角形底面
    tri = Part.makePolygon([
        _vec(0, 0, 0),
        _vec(base_pts[1].Length, 0, 0),
        base_pts[2],  # 在 XY 平面
        _vec(0, 0, 0)
    ])
    face = Part.makeFace(tri, "Part::Face")
    # 沿 Z 拉伸
    prism = face.extrude(_vec(0, 0, h))

    # 旋转到正确方向并平移
    z_axis = _vec(0, 0, 1)
    h_dir = h_vec.normalize()
    _orient_shape(prism, z_axis, h_dir)
    prism.translate(_vec(vx, vy, vz))
    return prism


def _make_box_from_vectors(params):
    """BOX: 从基底 V 和三边向量 A1/A2/A3 创建正交长方体。

    9 项写法（省略 A3）= 沿 A1×A2 方向**无限**（C810 3-19：BOX 可在某一维无限）：
    此时用一个把盒沿该方向"撑满"的大棱柱代替（正侧仍是挖掉该棱柱）。
    """
    p, infinite = box_params(params)
    a1 = _vec(p[3], p[4], p[5])
    a2 = _vec(p[6], p[7], p[8])
    a3 = _vec(p[9], p[10], p[11])
    v = _vec(p[0], p[1], p[2])
    if infinite:
        # 沿 A1×A2 无限：四边形底面沿该方向双向拉伸成"无限"棱柱
        n1 = a1.Length
        n2 = a2.Length
        if n1 < 1e-15 or n2 < 1e-15:
            return None
        n = (a1 / n1).cross(a2 / n2)
        if n.Length < 1e-15:
            return None
        quad = [v, v + a1, v + a1 + a2, v + a2]
        return _extrude_face(quad, n.normalize())
    pts = [v, v + a1, v + a1 + a2, v + a2,
           v + a3, v + a1 + a3, v + a1 + a2 + a3, v + a2 + a3]
    faces = [[0, 1, 2, 3], [4, 7, 6, 5],
             [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]
    return _build_polyhedron(pts, faces)


def _revolve_profile(profile_pts, axis_dir, origin=None):
    """把平面闭合 profile 绕轴整圈旋转成实体（自动修绕向）。

    ⚠ 坑：`Part.makePolygon` 不闭合线框，`Part.Face(开线框)` 会给出**负面积非法面**，
    revolve 得到**负体积实体**，随后 `box.cut(该实体)` 结果荒谬（实测 X 3 点回转体
    正侧体积 2877 vs 真值 61146）。故显式闭合 + 面积/有效性检查 + 必要时反向重试。
    """
    o = origin if origin is not None else _vec(0, 0, 0)
    for seq in (list(profile_pts), list(reversed(profile_pts))):
        try:
            wire = Part.makePolygon(seq + [seq[0]])
            face = Part.Face(wire)
            if face.Area <= 0 or not face.isValid():
                continue
            body = face.revolve(o, axis_dir, 360)
            if float(body.Volume) < 0:
                body.reverse()
            return body
        except Exception:
            continue
    return None


def _convex_from_faces(pts, faces, B):
    """凸多面体 → 实体：面半空间逐次求交。

    比 `makeShell + makeSolid` 稳：后者对绕向不一致的面会给出**负体积实体**
    （手册五面体例 ARB 实测 Volume=-275），随后 `box.cut` 静默失效 → 整个面变成整盒。
    ARB 的体心只取**面表引用到**的角点（未用角点是零三元组，不能参与平均）。
    """
    used = sorted({i for f in faces for i in f})
    if len(used) < 4:
        return None
    body = pts[used[0]]
    for i in used[1:]:
        body = body + pts[i]
    body = body * (1.0 / len(used))
    shape = _make_box(-B, B, -B, B, -B, B)
    for idx in faces:
        q = [pts[i] for i in idx]
        nrm = (q[1] - q[0]).cross(q[2] - q[0])
        if nrm.Length < 1e-15:
            return None
        nrm.normalize()
        fc = q[0]
        for v in q[1:]:
            fc = fc + v
        fc = fc * (1.0 / len(q))
        # 要的是**内侧**半空间（多面体本身）：法向指向体内
        if nrm.dot(fc - body) > 0:
            nrm = nrm * (-1.0)
        shape = shape.common(_plane_halfspace(nrm, (q[0].x, q[0].y, q[0].z), B))
        if shape.Volume <= 0:
            return None
    return shape


def _extrude_face(quad_pts, direction, length=1e4):
    """四边形沿 direction 双向拉伸 2×length → 无限棱柱近似实体（BOX 9 项用）。"""
    try:
        pts = list(quad_pts)
        face = Part.Face(Part.makePolygon(pts + [pts[0]]))
        if face.Area <= 0 or not face.isValid():
            face = Part.Face(Part.makePolygon(list(reversed(pts)) + [pts[-1]]))
        return face.extrude(direction * length).fuse(face.extrude(direction * (-length)))
    except Exception:
        return None


def _make_wedge_from_vectors(params):
    """WED: 创建楔形体 (不一定 axis-aligned)"""
    vx, vy, vz, v1x, v1y, v1z, v2x, v2y, v2z, v3x, v3y, v3z = params
    v = _vec(vx, vy, vz)
    v1 = _vec(v1x, v1y, v1z)
    v2 = _vec(v2x, v2y, v2z)
    v3 = _vec(v3x, v3y, v3z)
    # WED 的 6 个顶点: 底面三角形 V-V1-V2 沿 V3 拉伸
    bot = [v, v + v1, v + v2]
    top = [p + v3 for p in bot]
    pts = bot + top
    faces = [[0, 1, 2], [3, 5, 4],  # 底面、顶面 (注意绕向)
             [0, 3, 4, 1], [1, 4, 5, 2], [2, 5, 3, 0]]
    return _build_polyhedron(pts, faces)


def _make_arb_from_vertices(params):
    """ARB: 8 顶点 + 6 面定义 → 任意多面体。

    面码解码走 ``quadric.arb_face_indices``（C810 3-21：第 4 位为 0 则**忽略**该点）。
    旧实现 `(digit)-1` 把 0 变成 −1 → `pts[-1]` 取到第 8 角点，面线框被污染成
    非平面四边形（手册五面体例 4/8 决定性点判错、体积 64000 vs 63278）。
    """
    coords = params[:24]
    pts = [_vec(coords[i*3], coords[i*3+1], coords[i*3+2]) for i in range(8)]
    faces = arb_face_indices(params[24:30])
    if not faces:
        return None
    # 面半空间求交（凸多面体）——比 makeShell/makeSolid 稳：后者绕向不一致时给出
    # 负体积实体，随后 box.cut 静默失效（手册五面体例 Volume=-275 → 正侧变整盒）
    solid = _convex_from_faces(pts, faces, 500)
    if solid is not None:
        return solid
    return _build_polyhedron(pts, faces)


def _make_hex_from_params(params):
    """RHP/HEX: 六棱柱 — polygon + extrude。

    9/12 项写法（s/t 省略 → 由 60° 旋转推出，C810 3-19）先经 ``quadric.rhp_params``
    补齐为 15 项；旧实现直接解包 15 项 → 少项即 ValueError → 曲面被丢弃。
    """
    p = rhp_params(params)
    vx, vy, vz, hx, hy, hz, r1, r2, r3, s1, s2, s3, t1, t2, t3 = p
    v = _vec(vx, vy, vz)
    h = _vec(hx, hy, hz)
    if h.Length < 1e-15:
        return None
    r, s, t = _vec(r1, r2, r3), _vec(s1, s2, s3), _vec(t1, t2, t3)
    base = [v + r, v + s, v + t, v - r, v - s, v - t]
    pts = base + [base[0]]  # 闭合
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)
    prism = face.extrude(h)
    return prism


def _build_polyhedron(pts, faces):
    """从顶点列表和面索引表创建实体"""
    try:
        shell_faces = []
        for fi in faces:
            wire_pts = [pts[i] for i in fi]
            wire_pts.append(wire_pts[0])
            wire = Part.makePolygon(wire_pts)
            shell_faces.append(Part.Face(wire))
        shell = Part.makeShell(shell_faces)
        return Part.makeSolid(shell)
    except Exception:
        return None


def _make_solid_sphere(R, center):
    """创建实体球"""
    s = Part.makeSphere(R)
    s.translate(center)
    return s


def _make_torus_halfspace(surf_type: str, params: list[float], B: float):
    """环面半空间（正侧 = 环面外侧）。C810 §3-14 / Table 3.1：

        s²/B² + (r − A)²/C² = 1
        A = 主半径（轴心到管心）；B = 管的**轴向**次半径；C = 管的**径向**次半径。

    旧实现：管心沿**轴**偏移 A（TX/TY 直接退化成球 → OCC 报错丢弃），管半径只取 |B|、
    把 C 整个丢掉（椭圆管退化成圆管，实测 [4.5,0,0] 判反）。现按椭球管截面 revolve：
    截面椭圆放在"含轴平面"内，长半轴沿轴向 = B、短半轴沿径向 = C，管心离轴 A。
    """
    center, axis_idx, radial, A, Bb, C = torus_params(surf_type, params)
    if abs(Bb) < 1e-15 or abs(C) < 1e-15:
        return _make_box(-B, B, -B, B, -B, B)   # 退化：正侧近似全空间
    c = _vec(*center)
    ax = _vec(1.0 if axis_idx == 0 else 0.0,
              1.0 if axis_idx == 1 else 0.0,
              1.0 if axis_idx == 2 else 0.0)
    # 径向基向量（与轴垂直）：取余下两轴的第一根
    e_rad = _vec(1.0 if radial[0] == 0 else 0.0,
                 1.0 if radial[0] == 1 else 0.0,
                 1.0 if radial[0] == 2 else 0.0)
    # 截面椭圆：局部 x 沿**长**半轴、y 沿短半轴（OCC 要求 major ≥ minor，否则
    # 抛 "Axis value is invalid" → 旧写法 B≠C 时直接退化成整盒）
    if abs(C) >= abs(Bb):
        major, minor, ex, ey = abs(C), abs(Bb), e_rad, ax
    else:
        major, minor, ex, ey = abs(Bb), abs(C), ax, e_rad
    try:
        ell = Part.Ellipse(_vec(0, 0, 0), major, minor)
        face = Part.Face(Part.Wire([ell.toShape()]))
        e3 = ex.cross(ey)
        mat = FreeCAD.Matrix(ex.x, ey.x, e3.x, 0,
                             ex.y, ey.y, e3.y, 0,
                             ex.z, ey.z, e3.z, 0,
                             0, 0, 0, 1)
        face.transformShape(mat)
        face.translate(c + e_rad * A)   # 管心离轴 A（**径向**偏移，不是沿轴）
        torus = face.revolve(c, ax, 360)
    except Exception:
        return _make_box(-B, B, -B, B, -B, B)
    return _make_box(-B, B, -B, B, -B, B).cut(torus)


def _make_ellipsoid(params: list[float], B: float):
    """ELL: 椭球 — 椭圆弧 revolve（C810 §3-20 两形）。

    Rm>0：V1/V2 为两焦点、Rm = 长轴**长度**（半长轴 = Rm/2）。
    Rm<0：V1 = 球心、V2 = 长轴**矢量**（长度 = 长半径）、|Rm| = 短半径。
    旧实现只认焦点形，Rm<0 时 a = Rm/2 < 0 → 直接返回整盒（正侧=全空间）。
    """
    v1x, v1y, v1z, v2x, v2y, v2z, Rm = (float(v) for v in params[:7])
    f1 = _vec(v1x, v1y, v1z)
    f2 = _vec(v2x, v2y, v2z)
    if Rm > 0:
        center = (f1 + f2) / 2
        focal_dist = f1.distanceToPoint(f2) / 2
        a = Rm / 2
        if a <= focal_dist:
            return _make_box(-B, B, -B, B, -B, B)
        b = math.sqrt(a ** 2 - focal_dist ** 2)
        axis_dir = (f2 - f1).normalize()
    else:
        # Rm<0：V1 = 球心，V2 = 长轴**矢量**（模长 = 长半径），|Rm| = 短半径
        center = f1
        a = f2.Length
        b = abs(Rm)
        if a <= 1e-15 or b <= 1e-15:
            return _make_box(-B, B, -B, B, -B, B)
        axis_dir = f2.normalize()
    # 精确椭球：**真椭圆弧**绕轴回转（不是"三点圆弧"——那是圆不是椭圆）。
    # 不走"单位球 + 非均匀缩放"：transformShape 出来的是 B 样条近似面，
    # OCC 的点分类/BoundBox 都会失真（实测 body.isInside((2.2,0,0))=True，
    # 而椭球半轴只有 2；bbox ±2.29 而真实 ±3）。
    try:
        ell = Part.Ellipse(_vec(0, 0, 0), a, b)          # 长半轴 a 沿局部 x、短半轴 b 沿局部 y
        arc = Part.ArcOfEllipse(ell, 0.0, math.pi)       # 局部 y ≥ 0 的半椭圆
        chord = Part.LineSegment(_vec(-a, 0, 0), _vec(a, 0, 0)).toShape()
        face = Part.Face(Part.Wire([arc.toShape(), chord]))
        # 局部 x → 轴向 z、局部 y → 径向（绕 y 轴 −90°），于是剖面落在 YZ 平面
        face.transformShape(FreeCAD.Matrix(0, 0, -1, 0,
                                           0, 1, 0, 0,
                                           1, 0, 0, 0,
                                           0, 0, 0, 1))
        body = face.revolve(_vec(0, 0, 0), _vec(0, 0, 1), 360)
        _orient_shape(body, _vec(0, 0, 1), axis_dir)
        body.translate(center)
    except Exception:
        return _make_box(-B, B, -B, B, -B, B)
    return _make_box(-B, B, -B, B, -B, B).cut(body)


def _make_rec(params: list[float], B: float):
    """REC: 椭圆柱（C810 §3-19）。

    椭圆**方向**由 V1（长轴矢量）/V2（短轴矢量，10 项写法时 = H×V1 方向 × 短轴半径）给定：
    旧实现把椭圆长轴永远摆在全局 x（只旋转 z→H），V1 的方向被丢弃 ——
    V1 沿 +y 时 4 个决定性点错 2 个。现按 (ê1, ê2, ê3=H) 正交基放置椭圆。
    """
    p = rec_params(params)   # 10 项 → 12 项（短轴半径 → 矢量）
    vx, vy, vz = p[0], p[1], p[2]
    hx, hy, hz = p[3], p[4], p[5]
    v1 = _vec(p[6], p[7], p[8])
    v2 = _vec(p[9], p[10], p[11])
    h = _vec(hx, hy, hz)
    H = h.Length
    if H < 1e-15 or v1.Length < 1e-15 or v2.Length < 1e-15:
        return _make_box(-B, B, -B, B, -B, B)
    e3 = h / H
    e1 = v1 / v1.Length
    e2 = e3.cross(e1)
    if e2.Length < 1e-15:
        e2 = e3.cross(_vec(0, 0, 1)) if abs(e3.z) < 0.9 else e3.cross(_vec(1, 0, 0))
        if e2.Length < 1e-15:
            return _make_box(-B, B, -B, B, -B, B)
    e2 = e2 / e2.Length
    # 椭圆：局部 x → ê1（长半轴 |V1|）、局部 y → ê2（短半轴 |V2|）
    try:
        ell = Part.Ellipse(_vec(0, 0, 0), v1.Length, v2.Length)
        face = Part.Face(Part.Wire([ell.toShape()]))
        e3b = e1.cross(e2)
        mat = FreeCAD.Matrix(e1.x, e2.x, e3b.x, 0,
                             e1.y, e2.y, e3b.y, 0,
                             e1.z, e2.z, e3b.z, 0,
                             0, 0, 0, 1)
        face.transformShape(mat)
        prism = face.extrude(h)
    except Exception:
        return _make_box(-B, B, -B, B, -B, B)
    prism.translate(_vec(vx, vy, vz))  # base at V, top at V+H
    return _make_box(-B, B, -B, B, -B, B).cut(prism)


# ============================================================
# GQ / SQ → FreeCAD 原生曲面（精确，优先）或 VTK Marching Cubes（兜底）
# ============================================================

def _quadric_to_native(qtype: str, coeffs: list[float], B: float):
    """GQ/SQ 系数 → FreeCAD 原生曲面（精确），返回正侧半空间；无法分类返回 None。

    通过二次型矩阵特征值分解分类：
      (0, λ, λ)          → 圆柱  Part.makeCylinder
      (λ, λ, λ) / (λ1λ2λ3 同号) → 球 / 椭球  Part.makeSphere / makeEllipsoid
    其余（平面/锥/椭圆柱/双曲面）→ None → 回退 marching cubes。
    """
    if qtype == "sq":
        # SQ → GQ 展开走 quadric.sq_to_gq（单一实现）：C810 Table 3.1 的 D/E/F 是
        # **带系数 2 的线性项**，不是交叉项（旧内联副本与旧 sq_to_gq 都写成交叉项）
        coeffs = sq_to_gq(coeffs)

    a, b, c, d, e, f, g, h, j, k = coeffs
    M = np.array([[a, d / 2, f / 2], [d / 2, b, e / 2], [f / 2, e / 2, c]], dtype=float)
    w, V = np.linalg.eigh(M)  # w 升序，V 列 = 特征向量
    L = np.array([g, h, j], dtype=float)
    Lp = V.T @ L
    scale = max(1.0, max(abs(x) for x in w))
    # 系数可能被格式化成 3 位小数，圆柱的"零特征值"会有 ~1e-3 的舍入噪声，
    # 用相对容差，否则圆柱会被误判成椭球
    tol = 1e-3 * scale
    nz = [i for i, x in enumerate(w) if abs(x) > tol]

    if len(nz) == 2:
        # ── 圆柱（两非零特征值相等）──
        zi = [i for i in range(3) if i not in nz][0]
        lam = w[nz]
        if abs(Lp[zi]) > tol:
            return None  # 轴方向有线性项 → 不是正圆柱
        if abs(lam[0] - lam[1]) > 1e-3 * max(1.0, abs(lam[0])):
            return None  # 椭圆圆柱暂不支持
        lam0 = lam[0]
        cp = np.zeros(3)
        for idx in nz:
            cp[idx] = -Lp[idx] / (2 * lam0)
        r2 = (Lp[nz[0]] ** 2 + Lp[nz[1]] ** 2) / (4 * lam0 ** 2) - k / lam0
        if r2 <= 0:
            return None
        r = math.sqrt(r2)
        center_g = V @ cp
        axis_g = V[:, zi]
        # Part.makeCylinder 的 center 是底面端点，不是中心 → 用 center-2B*axis 作底面、4B 高，确保覆盖整个盒子
        base = center_g - 2 * B * axis_g
        cyl = Part.makeCylinder(r, 4 * B, _vec(*base), _vec(*axis_g))
        # 感度看二次型符号：f = λ·(径向² − R²) + O(轴向)。λ>0 → 正侧=柱外；
        # λ<0（系数整体乘 −1，如 GQ -1 -1 0 … 4）→ 正侧=**柱内**。
        # 旧实现无条件返回"柱外" → 该写法整块几何翻面（实测 8/8 点判反、体积 63497 vs 444）。
        if lam0 > 0:
            return _make_box(-B, B, -B, B, -B, B).cut(cyl)   # 正侧 = 柱外
        return cyl.common(_make_box(-B, B, -B, B, -B, B))     # 正侧 = 柱内

    if len(nz) == 3 and all(x > 0 for x in w):
        # ── 球 / 椭球 ──
        return _quadric_ellipsoid(w.tolist(), None, (V, Lp, k), B)

    if len(nz) == 3:
        # ── 圆锥：两个正特征值相等 + 一个负（直圆锥）──
        pos = [i for i in range(3) if w[i] > tol]
        neg = [i for i in range(3) if w[i] < -tol]
        if (len(pos) == 2 and len(neg) == 1
                and abs(w[pos[0]] - w[pos[1]]) < 1e-3 * scale):
            lam = w[pos[0]]
            mu = -w[neg[0]]
            axis = V[:, neg[0]]
            cp = np.zeros(3)
            for i in range(3):
                cp[i] = -Lp[i] / (2 * w[i])
            # 残差 K = k - Σwᵢcᵢ² ≈ 0 才是锥（否则是双曲面）
            K = k - sum(w[i] * cp[i] ** 2 for i in range(3))
            if abs(K) > 1e-2 * max(1.0, abs(k)):
                return None
            tan2 = mu / lam
            if tan2 <= 0:
                return None
            L = 2 * B
            r = math.sqrt(tan2) * L
            apex = V @ cp
            try:
                c1 = Part.makeCone(0, r, L, _vec(*apex), _vec(*axis))
                c2 = Part.makeCone(0, r, L, _vec(*apex), _vec(*(-axis)))
                dc = c1.fuse(c2)
            except Exception:
                return None
            return _make_box(-B, B, -B, B, -B, B).cut(dc)  # 正侧 = 锥外

    return None


def _quadric_ellipsoid(w, center, extra, B):
    """由主轴特征值/中心生成椭球或球半空间（正侧 = 外部）。"""
    if isinstance(extra, tuple):
        V, Lp, k = extra
        # 主轴系配方：Σ w_i (x_i-c_i)² = C，c_i=-Lp_i/(2w_i)
        cp = np.zeros(3)
        for i in range(3):
            cp[i] = -Lp[i] / (2 * w[i])
        C = sum(Lp[i] ** 2 / (4 * w[i]) for i in range(3)) - k
        semi = [math.sqrt(C / w[i]) for i in range(3)]
        cg = V @ cp
    else:
        # SQ 轴对齐形式
        a, b, c = w
        cx, cy, cz = center
        C = -extra
        semi = [math.sqrt(C / a), math.sqrt(C / b), math.sqrt(C / c)]
        cg = np.array([cx, cy, cz])
        V = None
    if any(x <= 0 for x in semi):
        return None
    # 三半轴近似相等 → 球
    if max(semi) - min(semi) < 1e-4 * max(1.0, max(semi)):
        sph = Part.makeSphere(semi[0], _vec(*cg))
        return _make_box(-B, B, -B, B, -B, B).cut(sph)
    # 一般椭球：建球→非均匀缩放（transformShape 缩放矩阵）→旋转
    try:
        ell = Part.makeSphere(1.0)
        scale_mat = FreeCAD.Matrix()
        scale_mat.scale(*semi)
        ell.transformShape(scale_mat)
        if V is not None:
            rot = FreeCAD.Matrix(V[0, 0], V[0, 1], V[0, 2], 0,
                                 V[1, 0], V[1, 1], V[1, 2], 0,
                                 V[2, 0], V[2, 1], V[2, 2], 0,
                                 0, 0, 0, 1)
            ell.Placement = FreeCAD.Placement(rot)
        ell.translate(FreeCAD.Vector(*cg))
        return _make_box(-B, B, -B, B, -B, B).cut(ell)
    except Exception:
        return None  # 非球椭球无法原生创建 → 回退区域网格化


def _legacy_quadric_to_shape(qtype: str, coeffs: list[float], B: float, grid_res: int = 40):
    """旧实现（保留对照，勿调用）。"""
    # 旧实现：native 优先，失败走 _quadric_region_solid（保留对照，勿调用）
    native = _quadric_to_native(qtype, coeffs, B)
    if native is not None:
        return native
    # vtk 旧分支已删除
    # （旧 vtk 惰性导入分支已整体删除）
    # （旧占位）
    # 占位（旧分支已删除）

    pass  # （旧分支占位）
    pass  # （旧分支占位）
    # （旧占位）
    pass  # （旧分支占位）
    # 旧 vtk 守卫已移除（不再需要）

    # SQ → GQ 统一系数后走通用区域网格化
    if qtype == "sq":
        coeffs = sq_to_gq(coeffs)
    return _quadric_region_solid(coeffs, B, grid_res)


def _quadric_to_shape(qtype: str, coeffs: list[float], B: float, grid_res: int = 40):
    """从二次曲面系数生成 Part.Shape（正侧 pos = F(x,y,z) > 0 的半空间）。

    先试原生（球/椭球、正圆柱、正圆锥 —— 特征值分类精确原语），其余类型
    回退到「二值体素区域 marching cubes」：对 {F>0} ∩ [-B,B]³ 加一层 0 padding
    提取区域边界，天然水密、法线一致，覆盖全部二次曲面（含无界/退化）。
    纯 numpy（app/mc.py），不再依赖 vtk。
    """
    native = _quadric_to_native(qtype, coeffs, B)
    if native is not None:
        return native
    if qtype == "sq":
        coeffs = sq_to_gq(coeffs)
    return _quadric_region_solid(coeffs, B, grid_res)



def _quadric_region_solid(coeffs: list[float], B: float, res: int = 40):
    """{F(x,y,z) >= 0} ∩ [-B,B]³ 的半空间实体（水密）。

    实现：在 [-B-δ, B+δ]³ 上构造二值体素（盒内 F>=0 记 1，padding 一层记 0），
    纯 numpy marching cubes（app/mc.py）提取区域边界 → FreeCAD Mesh → Part.Solid。
    区域为空（正侧在盒内无点）→ RuntimeError，让该曲面在调用侧被跳过并告警。
    """

    pad = 1
    res = max(8, int(res))
    xs = np.linspace(-B, B, res)
    d = xs[1] - xs[0]
    xp = np.concatenate([[xs[0] - d], xs, [xs[-1] + d]])
    X, Y, Z = np.meshgrid(xp, xp, xp, indexing="ij")

    def quadric_f(x, y, z):
        return (coeffs[0] * x ** 2 + coeffs[1] * y ** 2 + coeffs[2] * z ** 2
                + coeffs[3] * x * y + coeffs[4] * y * z + coeffs[5] * z * x
                + coeffs[6] * x + coeffs[7] * y + coeffs[8] * z + coeffs[9])

    F = quadric_f(X, Y, Z)
    in_box = (np.abs(X) <= B) & (np.abs(Y) <= B) & (np.abs(Z) <= B)
    region = np.where(in_box & (F >= 0.0), 1, 0).astype(np.uint8)

    def inside_clipped(x, y, z):
        return (np.abs(x) <= B) & (np.abs(y) <= B) & (np.abs(z) <= B) & (quadric_f(x, y, z) >= 0.0)

    vertices, triangles = _mc.marching_cubes(region, xp, xp, xp, inside_fn=inside_clipped)
    if len(triangles) == 0:
        raise RuntimeError("GQ/SQ 曲面正侧在包围盒内为空")

    mesh = _triangles_to_fcmesh(vertices, triangles)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, 0.05)
    if shape.isNull() or not shape.Shells:
        raise RuntimeError("GQ/SQ 曲面区域网格无法转换为实体")
    # 多连通分量（外盒 + 浮空孔）→ Compound 保留全部 shell，makeSolid 支持带空腔实体
    solid = Part.makeSolid(Part.Compound(shape.Shells))
    if not solid.isValid():
        raise RuntimeError("GQ/SQ 曲面区域网格生成的实体无效")
    # 方向校正：makeShapeFromMesh 对非凸壳的自动定向可能选反，采样区域点验证。
    # 采样点须严格在盒内（离壁一个体素以上）且 F 尽量大（远离曲面），避免落在边界上歧义。
    interior = ((np.abs(X) < B - d) & (np.abs(Y) < B - d)
                & (np.abs(Z) < B - d) & (region == 1))
    idx = np.argwhere(interior)
    if idx.size == 0:
        idx = np.argwhere(region == 1)
    if idx.size == 0:
        raise RuntimeError("GQ/SQ 曲面正侧在包围盒内为空")
    flat_f = F[idx[:, 0], idx[:, 1], idx[:, 2]]
    i, j, k = idx[int(np.argmax(flat_f))]
    sample = _vec(float(xp[i]), float(xp[j]), float(xp[k]))
    if not solid.isInside(sample, 1e-6, True):
        solid.reverse()
    return solid


# ============================================================
# 点定义旋转体 X/Y/Z
# ============================================================

def _point_surf_to_shape(axis: str, params: list[float], B: float):
    """点定义旋转体 X/Y/Z（C810 §3-15）。

    1 对坐标 → 平面；2 对 → 柱面（等半径）或**单叶锥**（手册：两点只生成单叶）；
    3 对 → 回转二次曲面 r² = A·a² + B·a + C。
    正侧 = 外侧（与方程定义曲面同口径），故最终都是 `盒 − 实体`。

    旧实现把 3 点当**折线**绕轴旋转（且 1 点/2 点也走折线 → 平面退化成空、柱/锥轴向被截断）：
    实测 1 点平面体积 64000 vs 24000（全错）、2 点柱 4/8 决定性点错。
    """
    t = (axis or "").upper()
    ax_i = {"X": 0, "Y": 1, "Z": 2}[t]
    rad = [i for i in range(3) if i != ax_i]
    p = [float(v) for v in params]
    pts = [(p[i], p[i + 1]) for i in range(0, len(p) - 1, 2)]
    box = _make_box(-B, B, -B, B, -B, B)

    def mk(a, r, w=0.0):
        """把 (轴向, 径向) 平面点映射到 3D（径向落在 rad[0] 轴上）。"""
        v = [0.0, 0.0, 0.0]
        v[ax_i] = a
        v[rad[0]] = r
        return _vec(*v)

    if not pts:
        return box

    if len(pts) == 1:                       # 平面
        a1 = pts[0][0]
        lo = [-B, -B, -B]
        hi = [B, B, B]
        lo[ax_i] = a1
        shape = _make_box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
        return shape

    axis_dir = _vec(1.0 if ax_i == 0 else 0.0,
                    1.0 if ax_i == 1 else 0.0,
                    1.0 if ax_i == 2 else 0.0)

    if len(pts) == 2:
        (a1, r1), (a2, r2) = pts
        if abs(a2 - a1) < 1e-15:
            return box
        if abs(r1 - r2) < 1e-15:            # 柱面
            try:
                cyl = Part.makeCylinder(abs(r1), 4 * B, axis_dir * (-2 * B), axis_dir)
                return box.cut(cyl)
            except Exception:
                return box
        tan = (r2 - r1) / (a2 - a1)         # 单叶锥
        a0 = a1 - r1 / tan
        length = 3.0 * B + abs(a0)
        direction = axis_dir if tan > 0 else axis_dir * (-1.0)
        try:
            cone = Part.makeCone(0.0, abs(tan) * length, length,
                                 axis_dir * a0, direction)
            return box.cut(cone)
        except Exception:
            return box

    if len(pts) == 3:
        A = np.array([[a * a, a, 1.0] for a, _ in pts], dtype=float)
        rhs = np.array([r * r for _, r in pts], dtype=float)
        try:
            ca, cb, cc = np.linalg.solve(A, rhs)
        except np.linalg.LinAlgError:
            return box

        def q(a):
            return ca * a * a + cb * a + cc

        # q(a) > 0 的区间：每段单独做成一个回转体再逐段从盒里挖掉。
        # ⚠ 不能把整段 [−3B, 3B] 一次采样：q<0 的地方 r=0，轮廓会有一大段**贴着轴**
        # 的重复顶点 → Part.Face 判 invalid → 整个回转体作废（实测正侧退回整盒）。
        bounds = [-3.0 * B, 3.0 * B]
        aa, bb2 = bounds
        intervals = []
        if abs(ca) < 1e-300:                       # 线性 q = cb·a + cc
            if abs(cb) < 1e-300:
                intervals = [(aa, bb2)] if cc > 0 else []
            else:
                root = -cc / cb
                intervals = [(root, bb2)] if cb > 0 else [(aa, root)]
        else:
            disc = cb * cb - 4 * ca * cc
            if disc <= 0:
                intervals = [(aa, bb2)] if ca > 0 else []      # 无实根：q 恒号
            else:
                s = math.sqrt(disc)
                r1_, r2_ = sorted(((-cb - s) / (2 * ca), (-cb + s) / (2 * ca)))
                if ca > 0:            # 开口向上：q>0 在两根之外
                    intervals = [(aa, max(aa, r1_)), (min(bb2, r2_), bb2)]
                else:                 # 开口向下：q>0 在两根之间
                    intervals = [(max(aa, r1_), min(bb2, r2_))]
        shape = box
        any_body = False
        for alo, ahi in intervals:
            if ahi - alo < 1e-9:
                continue
            prof = []
            n = 96
            for i in range(n + 1):
                a = alo + (ahi - alo) * i / n
                prof.append(mk(a, math.sqrt(max(q(a), 0.0))))
            # 绕向：沿轴走底边再沿曲线回来（开口线框会让 Face 出现负面积）
            body = _revolve_profile([mk(alo, 0.0), mk(ahi, 0.0)] + list(reversed(prof)),
                                    axis_dir)
            if body is None:
                continue
            any_body = True
            shape = shape.cut(body)
        return shape if any_body else box

    return box


# ============================================================
# TRn 变换 → FreeCAD Placement
# ============================================================

def apply_trn(shape, tr_data):
    """将 TRn 变换施加到 Part.Shape"""
    t = tr_data["translate"]
    r = tr_data["rotate"]

    # 构建 4x4 矩阵 (MCNP TRn 格式: 列向量 = 局部轴在全局的方向)
    # FreeCAD: M * P (column vector), 矩阵列 = 局部轴在全局的方向
    # 列0=V, 列1=W, 列2=U
    mat = FreeCAD.Matrix(
        r[0][0], r[1][0], r[2][0], t[0],
        r[0][1], r[1][1], r[2][1], t[1],
        r[0][2], r[1][2], r[2][2], t[2],
        0, 0, 0, 1
    )
    shape.Placement = FreeCAD.Placement(mat)
    shape.Placement = FreeCAD.Placement(mat)


def _fallback_box_mesh(ast, surfaces_by_num, tr_cards, B):
    """GQ/SQ 体素网格化失败时的诚实降级：返回栅元 AABB 包围盒网格。

    优先用 voxel_csg.cell_aabb（带 TR 曲面会保守全盒）；解析失败或退化
    时退回整个 bound 盒。warnings 由调用方写入 `栅元 N: GQ/SQ 网格化失败`。
    """
    try:
        aabb = voxel_csg.cell_aabb(ast, surfaces_by_num, B, tr_cards)
        if aabb is not None:
            lo = [float(x) for x in aabb[0]]
            hi = [float(x) for x in aabb[1]]
            lo = [max(min(v, B), -B) for v in lo]
            hi = [max(min(v, B), -B) for v in hi]
            if all(hi[i] > lo[i] for i in range(3)):
                box = _make_box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
                return FcMesh.Mesh(box.tessellate(1.0))
    except Exception:
        pass
    box = _make_box(-B, B, -B, B, -B, B)
    return FcMesh.Mesh(box.tessellate(1.0))



# ============================================================
# AST 求值
# ============================================================

def eval_ast(node, surfaces, bound_box):
    """递归求值 JSON AST → Part.Shape"""
    tag = node[0]

    if tag == "intersect":
        left = eval_ast(node[1], surfaces, bound_box)
        right = eval_ast(node[2], surfaces, bound_box)
        return left.common(right)

    elif tag == "union":
        left = eval_ast(node[1], surfaces, bound_box)
        right = eval_ast(node[2], surfaces, bound_box)
        return left.fuse(right)

    elif tag == "unary":
        operand = eval_ast(node[1], surfaces, bound_box)
        sign = node[2]
        if sign == "neg":
            return bound_box.cut(operand)
        elif sign == "pos":
            return operand
        elif sign == "complement":
            return bound_box.cut(operand)
        else:
            raise ValueError(f"未知的一元运算符: {sign}")

    elif tag == "surf":
        surf_num = node[1]
        if surf_num not in surfaces:
            raise KeyError(f"曲面 {surf_num} 未定义")
        return surfaces[surf_num]

    else:
        raise ValueError(f"未知的 AST 节点: {tag}")


# ============================================================
# 入口
# ============================================================

def main():
    data = json.load(sys.stdin)
    bound = float(data.get("bound", 500))
    out_dir = data["output_dir"]
    fmt = data.get("format", "stl")
    B = bound

    # Step 1: 构建包围盒
    bound_box = _make_box(-B, B, -B, B, -B, B)

    # Step 2: 为每个曲面创建半空间 (正侧)
    surfaces = {}
    warnings = []
    for s in data.get("surfaces", []):
        num = s["number"]
        try:
            trn = s.get("transform")
            tr_data = None
            if trn is not None and str(trn) in data.get("tr_cards", {}):
                tr_data = data["tr_cards"][str(trn)]
            elif trn is not None:
                # 引用了 TRn 但没有该变换卡：**不能静默按未变换处理**（几何会悄悄错位）
                warnings.append(f"曲面 {num} ({s['type']}) 引用了 TR{trn}，但请求里没有该 TR 卡 → 按未变换处理")

            if tr_data is not None:
                # ── TRn 曲面：必须在**局部系**里先把半空间造好，再变换回世界系 ──
                # 旧行为（锥/球/宏体等）：`T(盒 − 实体)` —— 把"已裁剪"的结果整体平移/旋转，
                # 结果既不是原曲面也不是原盒（实测 K/Z + TR2 平移 5x 的 STL 包围盒
                # x[-500,10] y[-500,500]，而正确应是 x[0,10] y[-5,5]）。
                # 正确 = `T(局部正侧) ∩ 世界盒`；局部盒取 √3·B + |平移| 保证旋转后仍覆盖世界盒，
                # 变换后再与世界盒取交裁掉多出来的部分。等价于"先变换无界曲面、再裁剪"，
                # 且每种曲面类型内部实现都不用动（圆柱也不再需要 _make_primitive 特例）。
                t = tr_data.get("translate", [0, 0, 0])
                B_loc = math.sqrt(3.0) * B + max(abs(float(v)) for v in t)
                shape = make_halfspace(s["type"], s["params"], B_loc)
                apply_trn(shape, tr_data)
                shape = shape.common(bound_box)
            else:
                shape = make_halfspace(s["type"], s["params"], B)

            surfaces[num] = shape
        except Exception as e:
            warnings.append(f"曲面 {num} ({s['type']}): {e}")
            # 跳过该曲面 → 后续用到它的栅元会报错

    # Step 3: 为每个栅元求值布尔表达式（所有栅元都求值，含真空/空气）
    results = {}
    cell_warnings = []
    voxel_nums = set()
    empty_nums = set()
    quadric_nums = {s["number"] for s in data.get("surfaces", [])
                    if s.get("type") in ("GQ", "SQ")}
    surfaces_by_num = {s["number"]: s for s in data.get("surfaces", [])}
    tr_cards = data.get("tr_cards", {})
    for cell in data.get("cells", []):
        num = cell["number"]
        ast = cell.get("ast")
        use_voxel = (ast is not None and bool(quadric_nums)
                     and bool(voxel_csg._ast_surf_nums(ast) & quadric_nums))
        try:
            # 含 GQ/SQ 的栅元：OCC 对网格化二次曲面半空间的布尔不可靠，
            # 走体素 CSG 直接出网格，绕开 OCC 布尔。
            if use_voxel:
                vertices, triangles = voxel_csg.mesh_cell_polydata(
                    ast, surfaces_by_num, tr_cards, B)
                if len(triangles) == 0:
                    raise ValueError("体素网格为空（栅元在包围盒内无实体）")
                results[str(num)] = _triangles_to_fcmesh(vertices, triangles)
                voxel_nums.add(num)
            else:
                if ast is None:
                    raise ValueError("几何 AST 不可解析")
                shape = eval_ast(ast, surfaces, bound_box)
                results[str(num)] = shape
        except Exception as e:
            if use_voxel:
                if "体素网格为空" in str(e):
                    cell_warnings.append(f"栅元 {num}: 空几何（零体积）")
                    empty_nums.add(num)
                else:
                    # 诚实降级：不静默、不拖垮整卡；该栅元回退为包围盒网格。
                    cell_warnings.append(f"栅元 {num}: GQ/SQ 网格化失败（{e}）")
                    results[str(num)] = _fallback_box_mesh(
                        ast, surfaces_by_num, tr_cards, B)
                    voxel_nums.add(num)
            else:
                cell_warnings.append(f"栅元 {num}: {e}")

    # Step 3.5: 重合检测（check_overlaps 时；只增不改现有行为）
    overlaps = []
    overlap_truncated = False
    overlap_unresolved = []
    zero_volume = []
    if data.get("check_overlaps"):
        focus_num = data.get("focus_num")
        focus_nums_raw = data.get("focus_nums") or (
            [focus_num] if focus_num is not None else [])
        focus_nums = {int(n) for n in focus_nums_raw if n is not None}
        cells_by_num = {c["number"]: c for c in data.get("cells", [])}
        aabbs = {}
        for num_str, shape in results.items():
            try:
                bb = shape.BoundBox
                aabbs[int(num_str)] = (
                    (bb.XMin, bb.YMin, bb.ZMin), (bb.XMax, bb.YMax, bb.ZMax))
            except Exception:
                pass
        candidates = grid_candidates(aabbs) if len(aabbs) >= 2 else []
        if focus_nums:
            candidates = [c for c in candidates
                          if c["a"] in focus_nums or c["b"] in focus_nums]
        top, overlap_truncated = cap_by_bbox_volume(candidates, max_ops=300)
        # 零体积栅元检测：空/退化栅元（体积 ≤ 绝对下限）
        for num_str, shape in results.items():
            try:
                vol = shape.Volume
            except Exception:
                try:
                    vol = shape.Mass  # FcMesh 兼容
                except Exception:
                    vol = None
            if vol is not None and float(vol) <= 1e-6:
                zero_volume.append(int(num_str))
        zero_volume = sorted(set(zero_volume) | empty_nums)
        results_raw = []
        for cand in top:
            a, b = cand["a"], cand["b"]
            sa = results.get(str(a))
            sb = results.get(str(b))
            if sa is None or sb is None:
                continue
            if a in voxel_nums or b in voxel_nums:
                # 含 GQ/SQ 或体素栅元 → 解析采样探针（采样证据，疑似）
                ca = cells_by_num.get(a)
                cb = cells_by_num.get(b)
                if (ca is None or cb is None
                        or ca.get("ast") is None or cb.get("ast") is None):
                    overlap_unresolved.append({"a": a, "b": b,
                                               "reason": "AST 缺失"})
                    continue
                try:
                    r = sample_overlap(ca["ast"], cb["ast"], surfaces_by_num,
                                       tr_cards, aabbs[a], aabbs[b])
                    if r is None:
                        continue
                    r["a"], r["b"] = a, b
                    results_raw.append(r)
                except Exception as e:
                    overlap_unresolved.append({"a": a, "b": b,
                                               "reason": str(e)})
            else:
                # 普通 BRep 栅元对：精确布尔
                try:
                    common = sa.common(sb)
                    results_raw.append({
                        "a": a, "b": b, "volume": common.Volume,
                        "vol_a": sa.Volume, "vol_b": sb.Volume,
                        "method": "boolean",
                    })
                except Exception as e:
                    overlap_unresolved.append({"a": a, "b": b,
                                               "reason": str(e)})
        cells_meta = {n: {"material": c.get("material", "0")}
                      for n, c in cells_by_num.items()}
        report = classify_overlaps(results_raw, cells_meta)
        overlaps = report["overlaps"]

    # Step 3.6: 栅元封闭性判定 (check_closure 时)
    # 对每个成功构建 BRep 的栅元判定三种状态：
    #   closed  — BRep 实体有界（AABB 不触及包围盒边界），体积>0
    #   infinite — 实体延伸到包围盒边界（曲面外无限大空间）
    #   empty    — 空/退化几何（体积≈0）
    # 体素网格（GQ/SQ）标记为 unresolvable（跳过判定）。
    closure_report = {}
    if data.get("check_closure"):
        bb = bound_box.BoundBox
        bb_lo = (bb.XMin, bb.YMin, bb.ZMin)
        bb_hi = (bb.XMax, bb.YMax, bb.ZMax)
        for cell in data.get("cells", []):
            num = cell["number"]
            shape = results.get(str(num))
            if shape is None:
                closure_report[num] = {"status": "unresolvable", "volume": None, "aabb": None}
                continue
            if isinstance(shape, FcMesh.Mesh):
                closure_report[num] = {"status": "voxel", "volume": None, "aabb": None}
                continue
            try:
                vol = float(shape.Volume)
            except Exception:
                closure_report[num] = {"status": "unresolvable", "volume": None, "aabb": None}
                continue
            if vol <= 1e-6:
                closure_report[num] = {"status": "empty", "volume": vol, "aabb": None}
                continue
            # AABB 检查：cell 是否在某个轴上到达包围盒边界
            try:
                cb = shape.BoundBox
                aabb = {"xmin": cb.XMin, "xmax": cb.XMax,
                        "ymin": cb.YMin, "ymax": cb.YMax,
                        "zmin": cb.ZMin, "zmax": cb.ZMax}
            except Exception:
                closure_report[num] = {"status": "closed", "volume": vol, "aabb": None}
                continue
            # 容差：与包围盒边界距离 < 包围盒 0.5% 长度 → 视为触及边界
            tol = B * 0.005
            touch = []
            if abs(cb.XMin - bb_lo[0]) < tol or abs(cb.XMax - bb_hi[0]) < tol:
                touch.append("x")
            if abs(cb.YMin - bb_lo[1]) < tol or abs(cb.YMax - bb_hi[1]) < tol:
                touch.append("y")
            if abs(cb.ZMin - bb_lo[2]) < tol or abs(cb.ZMax - bb_hi[2]) < tol:
                touch.append("z")
            if len(touch) >= 3:
                status = "infinite"
            elif len(touch) > 0:
                status = "semi_infinite"
            else:
                status = "closed"
            closure_report[num] = {"status": status, "volume": vol, "aabb": aabb,
                                   "infinite_axes": touch}

    # Step 4: 导出
    os.makedirs(out_dir, exist_ok=True)
    single_file = data.get("single_file", False)
    files = {}
    if single_file:
        # 合并模式: 所有栅元导出一个文件（用户导出，跳过真空/空气栅元）
        export_data = []
        for cell in data.get("cells", []):
            num = cell["number"]
            mat = str(cell.get("material", "0")).strip()
            if mat == "0" or mat == "":
                continue
            shape = results.get(str(num))
            if shape is not None:
                export_data.append((num, mat, shape))
        if not export_data:
            warnings.append("没有非真空栅元可导出")
        elif fmt == "step":
            single_path = os.path.join(out_dir, "geometry.step")
            try:
                SCALE = 10.0  # MCNP cm → FreeCAD mm
                scaled = [shape.copy() for _, _, shape in export_data]
                for s in scaled:
                    s.scale(SCALE)
                Part.makeCompound(scaled).exportStep(single_path)
                files["0"] = "geometry.step"
            except Exception as e:
                warnings.append(f"导出 STEP 失败: {e}")

    else:
        # 独立模式: 每个栅元单独文件（3D 预览使用）
        for num_str, shape in results.items():
            path = os.path.join(out_dir, f"cell_{num_str}.{fmt}")
            try:
                if fmt == "stl":
                    mesh = (shape if isinstance(shape, FcMesh.Mesh)
                            else FcMesh.Mesh(shape.tessellate(1.0)))
                    mesh.write(path)
                elif fmt == "step":
                    if isinstance(shape, FcMesh.Mesh):
                        raise ValueError("体素栅元不支持 STEP 导出")
                    shape.exportStep(path)
                elif fmt == "mesh":
                    # 返回网格数据（顶点+三角面），不写文件
                    mesh = (shape if isinstance(shape, FcMesh.Mesh)
                            else FcMesh.Mesh(shape.tessellate(1.0)))
                    verts = []
                    faces = []
                    for v in mesh.Points:
                        verts.append([v.x, v.y, v.z])
                    for facet in mesh.Facets:
                        faces.append([facet.PointIndices[0], facet.PointIndices[1], facet.PointIndices[2]])
                    files[num_str] = {"vertices": verts, "faces": faces}
                    continue
                else:
                    raise ValueError(f"不支持的导出格式: {fmt}")
                files[num_str] = f"cell_{num_str}.{fmt}"
            except Exception as e:
                warnings.append(f"导出栅元 {num_str}: {e}")

    # Step 5: 输出结果
    output = {"status": "ok", "files": files}
    if warnings:
        output["warnings"] = warnings
    if cell_warnings:
        output["cell_warnings"] = cell_warnings
    if data.get("check_overlaps"):
        output["overlaps"] = overlaps
        output["overlap_truncated"] = overlap_truncated
        output["overlap_unresolved"] = overlap_unresolved
        output["zero_volume"] = zero_volume
    if data.get("check_closure"):
        output["closure_report"] = closure_report

    print(json.dumps(output))


if __name__ == "__main__":
    main()
