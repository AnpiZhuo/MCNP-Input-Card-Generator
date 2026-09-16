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
    from _freecad_csg_worker import make_halfspace as _csg_make_halfspace
except ImportError:  # 测试/直接 import app 包时在 app/ 下
    from app._freecad_csg_worker import make_halfspace as _csg_make_halfspace


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
    """MCNP 曲面 → 正侧半空间实体：**直接复用** :mod:`_freecad_csg_worker` 的实现。

    2026-09-16：本文件原有一份"部分复制"的 make_halfspace（P_0/P_1 自己一套、
    环面/球/椭球/REC/BOX/WED/RHP/ARB/点定义面的 helper **一个都没拷过来**），
    结果是截面窗口对环面、SPH/REC/BOX/WED/RHP/HEX/ARB、X-Y-Z 一律
    `NameError` → 逐面降级成"缺块"，一般平面也被做成 `Part.makePlane` 面片而非半空间。
    现改为单一实现（CSG worker），本文件只保留截面特有的裁切/输出逻辑。
    """
    return _csg_make_halfspace(surf_type, params, B)


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
            elif trn:
                surface_errors.append({"number": num, "type": s.get("type", ""),
                                       "error": f"引用了 TR{trn} 但请求里没有该 TR 卡 → 按未变换处理"})
            if tr_data:
                # 与 3D worker 同一口径：局部系造半空间（局部盒放大 √3·B+|平移| 保证覆盖）
                # → 变换回世界系 → 与世界盒取交。旧行为 `T(盒−实体)` 会把裁剪结果整体平移。
                tt = tr_data.get("translate", [0, 0, 0])
                b_loc = math.sqrt(3.0) * B + max(abs(float(v)) for v in tt)
                shape = make_halfspace(s["type"], s["params"], b_loc)
                apply_trn(shape, tr_data)
                shape = shape.common(bound_box)
            else:
                shape = make_halfspace(s["type"], s["params"], B)
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
