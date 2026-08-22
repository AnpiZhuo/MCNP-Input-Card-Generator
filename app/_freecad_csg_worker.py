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
    from quadric import sq_to_gq
except ImportError:  # 测试/直接 import app 包时 quadric 在 app/ 下
    from app.quadric import sq_to_gq

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
        x1, y1, z1, x2, y2, z2, x3, y3, z3 = params
        edge1 = _vec(x2 - x1, y2 - y1, z2 - z1)
        edge2 = _vec(x3 - x1, y3 - y1, z3 - z1)
        normal = edge1.cross(edge2)
        return _plane_halfspace(normal, (x1, y1, z1), B)

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


    # ── 圆锥 (KX/KY/KZ) ──
    elif surf_type == "KX":
        x0, t2, sgn = params
        sgn = 1 if sgn >= 0 else -1
        # 圆锥半角 = atan(1/t) if t>0
        if t2 <= 0:
            return _make_box(-B, B, -B, B, -B, B)
        # 有限锥近似: 从 x=x0-B 到 x=x0+B 的截断锥
        R_top = abs(1.0 / math.sqrt(t2)) * B * sgn
        cone = Part.makeCone(0, R_top, B * 2, _vec(x0 - B, 0, 0), _vec(1, 0, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(cone)

    elif surf_type == "KY":
        y0, t2, sgn = params
        sgn = 1 if sgn >= 0 else -1
        if t2 <= 0:
            return _make_box(-B, B, -B, B, -B, B)
        R_top = abs(1.0 / math.sqrt(t2)) * B * sgn
        cone = Part.makeCone(0, R_top, B * 2, _vec(0, y0 - B, 0), _vec(0, 1, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(cone)

    elif surf_type == "KZ":
        z0, t2, sgn = params
        sgn = 1 if sgn >= 0 else -1
        if t2 <= 0:
            return _make_box(-B, B, -B, B, -B, B)
        R_top = abs(1.0 / math.sqrt(t2)) * B * sgn
        cone = Part.makeCone(0, R_top, B * 2, _vec(0, 0, z0 - B), _vec(0, 0, 1))
        return _make_box(-B, B, -B, B, -B, B).cut(cone)

    # ── 平行轴圆锥 (K/X K/Y K/Z) ──
    elif surf_type == "K/X":
        x0, y0, z0, t2, sgn = params
        sgn = 1 if sgn >= 0 else -1
        if t2 <= 0:
            return _make_box(-B, B, -B, B, -B, B)
        R_top = abs(1.0 / math.sqrt(t2)) * B * sgn
        cone = Part.makeCone(0, R_top, B * 2,
                             _vec(x0, y0 - B, z0), _vec(0, 1, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(cone)

    elif surf_type == "K/Y":
        x0, y0, z0, t2, sgn = params
        sgn = 1 if sgn >= 0 else -1
        if t2 <= 0:
            return _make_box(-B, B, -B, B, -B, B)
        R_top = abs(1.0 / math.sqrt(t2)) * B * sgn
        cone = Part.makeCone(0, R_top, B * 2,
                             _vec(x0 - B, y0, z0), _vec(1, 0, 0))
        return _make_box(-B, B, -B, B, -B, B).cut(cone)

    elif surf_type == "K/Z":
        x0, y0, z0, t2, sgn = params
        sgn = 1 if sgn >= 0 else -1
        if t2 <= 0:
            return _make_box(-B, B, -B, B, -B, B)
        R_top = abs(1.0 / math.sqrt(t2)) * B * sgn
        cone = Part.makeCone(0, R_top, B * 2,
                             _vec(x0, y0, z0 - B), _vec(0, 0, 1))
        return _make_box(-B, B, -B, B, -B, B).cut(cone)

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
    """BOX: 从基底 V 和三边向量 A1/A2/A3 创建正交长方体"""
    vx, vy, vz, a1x, a1y, a1z, a2x, a2y, a2z, a3x, a3y, a3z = params
    a1 = _vec(a1x, a1y, a1z)
    a2 = _vec(a2x, a2y, a2z)
    a3 = _vec(a3x, a3y, a3z)
    v = _vec(vx, vy, vz)
    pts = [v, v + a1, v + a1 + a2, v + a2,
           v + a3, v + a1 + a3, v + a1 + a2 + a3, v + a2 + a3]
    faces = [[0, 1, 2, 3], [4, 7, 6, 5],
             [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]
    return _build_polyhedron(pts, faces)


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
    """ARB: 8 顶点 + 6 面定义 → 任意多面体"""
    coords = params[:24]
    face_defs = params[24:30]
    pts = [_vec(coords[i*3], coords[i*3+1], coords[i*3+2]) for i in range(8)]
    faces = []
    for fd in face_defs:
        fd_int = int(abs(fd))
        vi = []
        for _ in range(4):
            if fd_int == 0:
                break
            vi.append((fd_int % 10) - 1)  # digit → 0-based vertex
            fd_int //= 10
        vi.reverse()  # MCNP encodes MSD first; we extracted LSD first
        if len(vi) >= 3:
            faces.append(vi)
    return _build_polyhedron(pts, faces)


def _make_hex_from_params(params):
    """RHP/HEX: 六棱柱 — polygon + extrude"""
    vx, vy, vz, hx, hy, hz, r1, r2, r3, s1, s2, s3, t1, t2, t3 = params
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
    """环面半空间 — 用圆截面 revolve 创建实体环"""
    x0, y0, z0, A, Bc, _ = params
    c = _vec(x0, y0, z0)
    # 圆截面的法向量 = 垂直于 revolve 轴的向量
    if surf_type == "TX":
        axis = _vec(1, 0, 0)
        circle_normal = _vec(0, 1, 0)  # circle in YZ plane at x=A
        circle_center = c + _vec(A, 0, 0)
    elif surf_type == "TY":
        axis = _vec(0, 1, 0)
        circle_normal = _vec(1, 0, 0)  # circle in XZ plane at y=A
        circle_center = c + _vec(0, A, 0)
    else:  # TZ
        axis = _vec(0, 0, 1)
        circle_normal = _vec(0, 1, 0)  # circle in XZ plane at z? Actually circle in XY plane placed at (A,0,0) normal Y -> XZ plane
        circle_center = c + _vec(A, 0, 0)
    circle = Part.makeCircle(abs(Bc), circle_center, circle_normal)
    face = Part.Face(Part.Wire(circle))
    torus = face.revolve(c, axis, 360)
    return _make_box(-B, B, -B, B, -B, B).cut(torus)


def _make_ellipsoid(params: list[float], B: float):
    """ELL: 椭球 — 椭圆弧 revolve"""
    v1x, v1y, v1z, v2x, v2y, v2z, Rm = params
    f1 = _vec(v1x, v1y, v1z)
    f2 = _vec(v2x, v2y, v2z)
    center = (f1 + f2) / 2
    focal_dist = f1.distanceToPoint(f2) / 2
    a = Rm / 2
    if a <= focal_dist:
        return _make_box(-B, B, -B, B, -B, B)
    b = math.sqrt(a ** 2 - focal_dist ** 2)
    axis_dir = (f2 - f1).normalize()
    # 在局部 ZX 平面创建椭圆弧: x=b*cos(t), z=a*sin(t)
    # 用三点: 南极 (0,0,-a), 赤道 (b,0,0), 北极 (0,0,a)
    arc = Part.Arc(_vec(0, 0, -a), _vec(b, 0, 0), _vec(0, 0, a)).toShape()
    line = Part.LineSegment(_vec(0, 0, -a), _vec(0, 0, a)).toShape()
    wire = Part.Wire([arc, line])
    face = Part.Face(wire)
    body = face.revolve(_vec(0, 0, 0), _vec(0, 0, 1), 360)
    # 旋转到 axis_dir, 平移到 center
    _orient_shape(body, _vec(0, 0, 1), axis_dir)
    body.translate(center)
    return _make_box(-B, B, -B, B, -B, B).cut(body)


def _make_rec(params: list[float], B: float):
    """REC: 椭圆柱 — 椭圆 + 拉伸"""
    vx, vy, vz = params[0], params[1], params[2]
    hx, hy, hz = params[3], params[4], params[5]
    v1x, v1y, v1z = params[6], params[7], params[8]
    H = math.sqrt(hx**2 + hy**2 + hz**2)
    if H < 1e-15:
        return _make_box(-B, B, -B, B, -B, B)
    major = math.sqrt(v1x**2 + v1y**2 + v1z**2)
    minor = major
    if len(params) >= 12:
        minor = math.sqrt(params[9]**2 + params[10]**2 + params[11]**2)
    el = Part.Ellipse()
    el.Center = _vec(0, 0, 0)
    el.MajorRadius = major
    el.MinorRadius = minor
    el_shape = el.toShape()
    wire = Part.Wire([el_shape])
    face = Part.Face(wire)
    prism = face.extrude(_vec(0, 0, H))
    _orient_shape(prism, _vec(0, 0, 1), _vec(hx, hy, hz))
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
        # SQ → GQ 展开，共用同一套特征值分类（否则会忽略 D/E/F 交叉项导致旋转 SQ 出错）
        A, Bb, C, D, E, F, G, x0, y0, z0 = coeffs
        coeffs = [A, Bb, C, D, E, F,
                  -2 * A * x0 - D * y0 - F * z0,
                  -2 * Bb * y0 - D * x0 - E * z0,
                  -2 * C * z0 - E * y0 - F * x0,
                  A * x0 * x0 + Bb * y0 * y0 + C * z0 * z0
                  + D * x0 * y0 + E * y0 * z0 + F * z0 * x0 + G]

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
        return _make_box(-B, B, -B, B, -B, B).cut(cyl)  # 正侧 = 柱外

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
    """点定义旋转体：profile 绕轴 revolve"""
    points = [(params[i], params[i+1]) for i in range(0, len(params), 2) if i+1 < len(params)]
    if not points:
        return _make_box(-B, B, -B, B, -B, B)

    revolve_axis = _vec(axis == "X", axis == "Y", axis == "Z")
    # 构建 profile (在轴对称平面内)
    if axis.upper() == "Z":
        prof = [_vec(r, 0, a) for a, r in points]
        prof += [_vec(0, 0, points[-1][0]), _vec(0, 0, points[0][0]), prof[0]]
    elif axis.upper() == "X":
        prof = [_vec(a, r, 0) for a, r in points]
        prof += [_vec(points[-1][0], 0, 0), _vec(points[0][0], 0, 0), prof[0]]
    else:  # Y
        prof = [_vec(r, a, 0) for a, r in points]
        prof += [_vec(0, points[-1][0], 0), _vec(0, points[0][0], 0), prof[0]]

    try:
        wire = Part.makePolygon(prof)
        face = Part.Face(wire)
        shape = face.revolve(_vec(0, 0, 0), revolve_axis, 360)
        return _make_box(-B, B, -B, B, -B, B).cut(shape)
    except Exception:
        return _make_box(-B, B, -B, B, -B, B)


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
# 无界曲面原语 (用于 TR 变换)
# ============================================================

def _make_primitive(surf_type: str, params: list[float], B: float):
    """
    创建无界的曲面原语（不包围盒裁剪），供 TR 变换后使用。

    对于 `B - primitive` 类型的曲面（圆柱/球/锥），
    TR 应先作用于原语再包围盒裁剪，而非作用于已裁剪结果。
    """
    if surf_type == "C/X":
        y0, z0, R = params
        return Part.makeCylinder(R, B * 2, _vec(-B, y0, z0), _vec(1, 0, 0))
    elif surf_type == "C/Y":
        x0, z0, R = params
        return Part.makeCylinder(R, B * 2, _vec(x0, -B, z0), _vec(0, 1, 0))
    elif surf_type == "C/Z":
        x0, y0, R = params
        return Part.makeCylinder(R, B * 2, _vec(x0, y0, -B), _vec(0, 0, 1))
    elif surf_type == "CX":
        R = params[0]
        return Part.makeCylinder(R, B * 2, _vec(-B, 0, 0), _vec(1, 0, 0))
    elif surf_type == "CY":
        R = params[0]
        return Part.makeCylinder(R, B * 2, _vec(0, -B, 0), _vec(0, 1, 0))
    elif surf_type == "CZ":
        R = params[0]
        return Part.makeCylinder(R, B * 2, _vec(0, 0, -B), _vec(0, 0, 1))
    else:
        raise ValueError(f"不支持的 TR 曲面: {surf_type}")


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

            if tr_data is not None and s["type"] in ("C/X", "C/Y", "C/Z", "CX", "CY", "CZ"):
                # ── TR 圆柱修复 ──
                # 旧行为: T(B - C) = T(B) - T(C), 导致负侧求值错误:
                #   B - T(B-C) = (B \ T(B)) ∪ (B ∩ T(C)) — 多了 B \ T(B) 的垃圾区域
                # 正确做法: 先变换圆柱本体, 再从 B 挖掉:
                #   正侧 = B - T(C), 负侧 = B - (B - T(C)) = B ∩ T(C)
                prim = _make_primitive(s["type"], s["params"], B)
                apply_trn(prim, tr_data)
                shape = bound_box.cut(prim)  # B - T(primitive) = 正侧
            else:
                shape = make_halfspace(s["type"], s["params"], B)
                if tr_data:
                    apply_trn(shape, tr_data)

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

    print(json.dumps(output))


if __name__ == "__main__":
    main()
