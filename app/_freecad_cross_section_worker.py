"""
FreeCAD Cross-Section Worker
"""
import sys, json, math, traceback
try:
    import FreeCAD
    import Part
    import Mesh as FcMesh
    import numpy as np
except ImportError as e:
    print(json.dumps({"status":"error","message":f"FreeCAD: {e}"}))
    sys.exit(1)

try:
    from quadric import sq_to_gq
except ImportError:  # 测试/直接 import app 包时 quadric 在 app/ 下
    from app.quadric import sq_to_gq

# VTK 可选（用于 GQ/SQ 曲面）：惰性导入，见 _quadric_to_shape 的 native 回退分支。
_HAVE_VTK = False

def _vec(x, y, z):
    return FreeCAD.Vector(x, y, z)



def _make_box(xmin, xmax, ymin, ymax, zmin, zmax):
    """创建轴对齐长方体"""
    return Part.makeBox(xmax - xmin, ymax - ymin, zmax - zmin,
                        _vec(xmin, ymin, zmin))



def _orient_shape(shape, from_dir, to_dir):
    """将 shape 从 Z 轴 (from_dir) 旋转到 to_dir 方向"""
    f = from_dir.normalize()
    t = to_dir.normalize()
    cross = f.cross(t)
    if cross.Length < 1e-15:
        return  # 同向，无需旋转
    angle = math.degrees(math.acos(max(-1, min(1, f.dot(t)))))
    shape.rotate(_vec(0, 0, 0), cross, angle)



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
# GQ / SQ → FreeCAD 原生曲面（精确，优先）或二值体素区域网格化（兜底）
# ============================================================

def _quadric_to_native(qtype: str, coeffs: list[float], B: float):
    """GQ/SQ 系数 → FreeCAD 原生曲面（精确），返回正侧半空间；无法分类返回 None。

    通过二次型矩阵特征值分解分类：
      (0, λ, λ)          → 圆柱  Part.makeCylinder
      (λ, λ, λ) / (λ1λ2λ3 同号) → 球 / 椭球  Part.makeSphere / makeEllipsoid
    其余（平面/锥/椭圆柱/双曲面）→ None → 回退区域网格化。
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


def _quadric_to_shape(qtype: str, coeffs: list[float], B: float, grid_res: int = 40):
    """从二次曲面系数生成 Part.Shape（正侧 pos = F(x,y,z) > 0 的半空间）。

    先试原生（球/椭球、正圆柱、正圆锥 —— 特征值分类精确原语），其余类型
    回退到「二值体素区域 marching cubes」：对 {F>0} ∩ [-B,B]³ 加一层 0 padding
    提取区域边界，天然水密、法线一致，覆盖全部二次曲面（含无界/退化）。

    vtk 惰性导入：仅在 native 回退分支内按需 `import vtk`，成功置 _HAVE_VTK=True；
    无 GQ/SQ 的 deck 子进程启动不加载 vtk。import 失败仍抛 RuntimeError("VTK 不可用...")。
    """
    global _HAVE_VTK
    native = _quadric_to_native(qtype, coeffs, B)
    if native is not None:
        return native
    if not _HAVE_VTK:
        try:
            import vtk
            _HAVE_VTK = True
        except ImportError:
            _HAVE_VTK = False
    if not _HAVE_VTK:
        raise RuntimeError("VTK 不可用，无法处理 GQ/SQ 曲面")

    # SQ → GQ 统一系数后走通用区域网格化
    if qtype == "sq":
        coeffs = sq_to_gq(coeffs)
    return _quadric_region_solid(coeffs, B, grid_res)


def _quadric_region_solid(coeffs: list[float], B: float, res: int = 40):
    """{F(x,y,z) >= 0} ∩ [-B,B]³ 的半空间实体（水密）。

    实现：在 [-B-δ, B+δ]³ 上构造二值体素（盒内 F>=0 记 1，padding 一层记 0），
    vtkDiscreteMarchingCubes 提取区域边界 → FreeCAD Mesh → Part.Solid。
    区域为空（正侧在盒内无点）→ RuntimeError，让该曲面在调用侧被跳过并告警。
    """
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk

    pad = 1
    n = res + 2 * pad
    xs = np.linspace(-B, B, res)
    d = xs[1] - xs[0]
    xp = np.concatenate([[xs[0] - d], xs, [xs[-1] + d]])
    X, Y, Z = np.meshgrid(xp, xp, xp, indexing="ij")
    F = (coeffs[0] * X ** 2 + coeffs[1] * Y ** 2 + coeffs[2] * Z ** 2
         + coeffs[3] * X * Y + coeffs[4] * Y * Z + coeffs[5] * Z * X
         + coeffs[6] * X + coeffs[7] * Y + coeffs[8] * Z + coeffs[9])
    in_box = (np.abs(X) <= B) & (np.abs(Y) <= B) & (np.abs(Z) <= B)
    region = np.where(in_box & (F >= 0.0), 1, 0).astype(np.uint8)

    img = vtk.vtkImageData()
    img.SetDimensions(n, n, n)
    img.SetSpacing(d, d, d)
    img.SetOrigin(-B - d, -B - d, -B - d)
    arr = numpy_to_vtk(region.ravel(order="F"), deep=True)  # vtk 布局 = x 最快
    arr.SetName("region")
    img.GetPointData().SetScalars(arr)

    mc = vtk.vtkDiscreteMarchingCubes()
    mc.SetInputData(img)
    mc.SetValue(0, 1)
    mc.Update()
    polydata = mc.GetOutput()
    if polydata.GetNumberOfPolys() == 0:
        raise RuntimeError("GQ/SQ 曲面正侧在包围盒内为空")

    mesh = FcMesh.Mesh()
    polys = polydata.GetPolys().GetData()
    for ti in range(polydata.GetNumberOfPolys()):
        off = ti * 4
        i1, i2, i3 = (polys.GetValue(off + 1), polys.GetValue(off + 2),
                      polys.GetValue(off + 3))
        p1, p2, p3 = (polydata.GetPoint(i1), polydata.GetPoint(i2),
                      polydata.GetPoint(i3))
        mesh.addFacet(_vec(*p1), _vec(*p2), _vec(*p3))

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




def main():
    data = json.load(sys.stdin)
    B = float(data.get("bound", 500))
    plane = data.get("plane", {"A":0,"B":0,"C":1,"D":0})
    A, Bp, C, D = plane["A"], plane["B"], plane["C"], plane["D"]

    bound_box = _make_box(-B, B, -B, B, -B, B)
    surfaces = {}
    # TD-26（t5）：原为裸 `except: pass`（连 KeyboardInterrupt/SystemExit 都吞，且无任何痕迹）。
    # 改为 `except Exception` + 收集，随响应透传 surfaceErrors，让"截面缺块"可归因到具体曲面。
    surface_errors = []
    for s in data.get("surfaces", []):
        num = s["number"]
        try:
            trn = s.get("transform")
            tr_data = None
            if trn and str(trn) in data.get("tr_cards", {}):
                tr_data = data["tr_cards"][str(trn)]
            if tr_data and s["type"] in ("C/X","C/Y","C/Z","CX","CY","CZ"):
                prim = _make_primitive(s["type"], s["params"], B)
                apply_trn(prim, tr_data)
                shape = bound_box.cut(prim)
            else:
                shape = make_halfspace(s["type"], s["params"], B)
                if tr_data: apply_trn(shape, tr_data)
            surfaces[num] = shape
        except Exception as e:  # noqa: BLE001 —— 逐曲面降级，但要留下归因
            surface_errors.append({"number": num, "type": s.get("type", ""),
                                   "error": f"{type(e).__name__}: {e}"})
            traceback.print_exc()

    results = []
    for cell in data.get("cells", []):
        num = cell["number"]
        mat = cell.get("material", "0")
        try:
            shape = eval_ast(cell["ast"], surfaces, bound_box)
            n2 = A*A + Bp*Bp + C*C
            if n2 < 1e-15:
                n_vec = FreeCAD.Vector(0, 0, 1)
                origin = FreeCAD.Vector(0, 0, D)
            else:
                n_vec = FreeCAD.Vector(A, Bp, C)
                origin = n_vec * (D / n2)
            # 截面：用 shape.slice() 取平面上的 Wire
            # slice(direction, distance) 中 distance 是沿法向从世界原点算
            dist = D / math.sqrt(n2) if n2 > 1e-15 else D
            wires = shape.slice(n_vec, dist)
            polygons = []
            for w in wires:
                try:
                    es = w.Edges
                    if len(es) < 3: continue
                    # 按边邻接步行：从 edge 0 开始，每次找下一条连接边
                    used = [False] * len(es)
                    chain = []
                    # 取 edge 0 的两个端点
                    v0 = es[0].Vertexes[0]; chain.append((v0.X, v0.Y, v0.Z))
                    v1 = es[0].Vertexes[1]; chain.append((v1.X, v1.Y, v1.Z))
                    used[0] = True
                    last_x, last_y, last_z = v1.X, v1.Y, v1.Z
                    while True:
                        found = False
                        for ei, e in enumerate(es):
                            if used[ei]: continue
                            a, b = e.Vertexes
                            for vv in (a, b):
                                if abs(vv.X-last_x)<1e-6 and abs(vv.Y-last_y)<1e-6 and abs(vv.Z-last_z)<1e-6:
                                    other = b if vv is a else a
                                    chain.append((other.X, other.Y, other.Z))
                                    last_x, last_y, last_z = other.X, other.Y, other.Z
                                    used[ei] = True
                                    found = True
                                    break
                            if found: break
                        if not found: break
                    # 去重首尾
                    while len(chain) >= 3 and chain[0] == chain[-1]:
                        chain.pop()
                    if len(chain) >= 3:
                        verts = [{"x": p[0], "y": p[1], "z": p[2]} for p in chain]
                        polygons.append(verts)
                except Exception:
                    pass

            results.append({"number": num, "material": mat, "polygons": polygons})
        except Exception:
            results.append({"number": num, "material": mat, "polygons": []})

    # TD-26（t5）：把逐曲面构造失败随响应透传（原裸 except 完全无痕，用户只看到"截面缺块"）
    print(json.dumps({"status":"ok", "slices":results, "surfaceErrors": surface_errors}))

if __name__ == "__main__":
    main()
