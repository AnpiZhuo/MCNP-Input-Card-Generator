"""
FreeCAD Cross-Section Worker
"""
import sys, json, math
try:
    import FreeCAD
    import Part
except ImportError as e:
    print(json.dumps({"status":"error","message":f"FreeCAD: {e}"}))
    sys.exit(1)

VTK = None

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
        except:
            pass

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

    print(json.dumps({"status":"ok", "slices":results}))

if __name__ == "__main__":
    main()
