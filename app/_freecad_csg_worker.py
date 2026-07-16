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
    import numpy as np
except ImportError as e:
    # FreeCAD 不可用时的错误报告
    print(json.dumps({"status": "error", "message": f"FreeCAD 导入失败: {e}"}))
    sys.exit(1)

# VTK 可选导入（用于 GQ/SQ 曲面）
try:
    import vtk
    _HAVE_VTK = True
except ImportError:
    _HAVE_VTK = False


# ============================================================
# 辅助工具
# ============================================================

def _vec(x, y, z):
    return FreeCAD.Vector(x, y, z)


def _make_box(xmin, xmax, ymin, ymax, zmin, zmax):
    """创建轴对齐长方体"""
    return Part.makeBox(xmax - xmin, ymax - ymin, zmax - zmin,
                        _vec(xmin, ymin, zmin))


# ============================================================
# 曲面 → FreeCAD Part.Shape 半空间
# ============================================================

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
        # 用 A,B,C 构建方向，在包围盒内切割
        bb = _make_box(-B, B, -B, B, -B, B)
        normal = FreeCAD.Vector(A, Bc, C)
        if normal.Length < 1e-15:
            return bb
        # 构建通过原点的平面，平移到 D
        plane = Part.makePlane(B * 2, B * 2,
                               _vec(-B, -B, 0),
                               _vec(0, 1, 0))
        plane.translate(normal.normalize() * D / normal.Length)
        # 取法向量指向的一侧
        return bb.common(plane)

    # ── 三点定义平面 P_1 ──
    elif surf_type == "P_1":
        x1, y1, z1, x2, y2, z2, x3, y3, z3 = params
        bb = _make_box(-B, B, -B, B, -B, B)
        # FreeCAD 的 makePlane 通过三点创建
        edge1 = _vec(x2 - x1, y2 - y1, z2 - z1)
        edge2 = _vec(x3 - x1, y3 - y1, z3 - z1)
        normal = edge1.cross(edge2)
        if normal.Length < 1e-15:
            return bb
        # 创建大平面
        plane = Part.makePlane(B * 2, B * 2,
                               _vec(x1 - B, y1 - B, z1),
                               normal)
        return bb.common(plane)

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
# GQ / SQ → VTK Marching Cubes
# ============================================================

def _quadric_to_shape(qtype: str, coeffs: list[float], B: float, grid_res: int = 40):
    """从二次曲面系数生成 Part.Shape (正侧 pos = 外部)"""
    if not _HAVE_VTK:
        raise RuntimeError("VTK 不可用，无法处理 GQ/SQ 曲面")

    # 构建采样网格
    xs = np.linspace(-B, B, grid_res)
    X, Y, Z = np.meshgrid(xs, xs, xs, indexing='ij')

    # 计算隐式函数 F(x,y,z) = 0
    if qtype == "gq":
        a, b, c, d, e, f, g, h, j, k = coeffs
        F = (a * X ** 2 + b * Y ** 2 + c * Z ** 2 +
             d * X * Y + e * Y * Z + f * Z * X +
             g * X + h * Y + j * Z + k)
    elif qtype == "sq":
        a, b, c, d, e, f, g, cx, cy, cz = coeffs
        x_, y_, z_ = X - cx, Y - cy, Z - cz
        F = (a * x_ ** 2 + b * y_ ** 2 + c * z_ ** 2 +
             d * x_ * y_ + e * y_ * z_ + f * z_ * x_ + g)

    # VTK marching cubes
    data = vtk.vtkImageData()
    data.SetDimensions(grid_res, grid_res, grid_res)
    data.SetSpacing(2 * B / (grid_res - 1),
                    2 * B / (grid_res - 1),
                    2 * B / (grid_res - 1))
    data.SetOrigin(-B, -B, -B)

    arr = vtk.vtkDoubleArray()
    arr.SetNumberOfValues(grid_res ** 3)
    flat = F.ravel()
    for i in range(grid_res ** 3):
        arr.SetValue(i, float(flat[i]))
    data.GetPointData().SetScalars(arr)

    contour = vtk.vtkFlyingEdges3D()
    contour.SetInputData(data)
    contour.SetValue(0, 0.0)
    contour.Update()

    polydata = contour.GetOutput()
    n_pts = polydata.GetNumberOfPoints()
    n_tri = polydata.GetNumberOfPolys()

    if n_pts == 0 or n_tri == 0:
        return _make_box(-B, B, -B, B, -B, B)

    # 转换为 FreeCAD Mesh
    verts = [polydata.GetPoint(i) for i in range(n_pts)]
    polys_arr = polydata.GetPolys().GetData()
    face_data = [polys_arr.GetValue(i) for i in range(polys_arr.GetNumberOfTuples())]

    mesh = FcMesh.Mesh()
    for ti in range(n_tri):
        offset = ti * 4  # [3, i1, i2, i3]
        i1, i2, i3 = face_data[offset + 1:offset + 4]
        v1, v2, v3 = verts[i1], verts[i2], verts[i3]
        mesh.addFacet(_vec(*v1), _vec(*v2), _vec(*v3))

    # Mesh → Part.Shape via temporary STL file
    # Note: VTK isosurface may not produce a watertight solid.
    # For preview purposes, use the mesh to carve the box.
    try:
        stl_path = os.path.join(tempfile.gettempdir(), "_fcad_gq_mesh.stl")
        mesh.write(stl_path)
        shape = Part.Shape()
        shape.read(stl_path)
        os.remove(stl_path)
        if shape.isNull():
            return _make_box(-B, B, -B, B, -B, B)
        # Try to make solid from shells
        if not shape.isSolid() and shape.Shells:
            try:
                solid = Part.makeSolid(shape.Shells[0])
                return _make_box(-B, B, -B, B, -B, B).cut(solid)
            except Exception:
                pass
        # Fallback: if no solid, return box (will be skipped)
        return _make_box(-B, B, -B, B, -B, B)
    except Exception:
        return _make_box(-B, B, -B, B, -B, B)


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
    # M = [R^T, t; 0, 1]
    mat = FreeCAD.Matrix(
        r[0][0], r[1][0], r[2][0], t[0],
        r[0][1], r[1][1], r[2][1], t[1],
        r[0][2], r[1][2], r[2][2], t[2],
        0, 0, 0, 1
    )
    shape.Placement = FreeCAD.Placement(mat)


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
            shape = make_halfspace(s["type"], s["params"], B)
            # 应用 TRn 变换
            trn = s.get("transform")
            if trn is not None and str(trn) in data.get("tr_cards", {}):
                apply_trn(shape, data["tr_cards"][str(trn)])
            surfaces[num] = shape
        except Exception as e:
            warnings.append(f"曲面 {num} ({s['type']}): {e}")
            # 跳过该曲面 → 后续用到它的栅元会报错

    # Step 3: 为每个栅元求值布尔表达式
    results = {}
    cell_warnings = []
    for cell in data.get("cells", []):
        num = cell["number"]
        try:
            shape = eval_ast(cell["ast"], surfaces, bound_box)
            results[str(num)] = shape
        except Exception as e:
            cell_warnings.append(f"栅元 {num}: {e}")

    # Step 4: 导出
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for num_str, shape in results.items():
        path = os.path.join(out_dir, f"cell_{num_str}.{fmt}")
        try:
            if fmt == "stl":
                mesh = FcMesh.Mesh(shape.tessellate(1.0))
                mesh.write(path)
            elif fmt == "step":
                Part.export([shape], path)
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

    print(json.dumps(output))


if __name__ == "__main__":
    main()
