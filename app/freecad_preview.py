"""
FreeCAD CSG 引擎 — 主进程侧封装。

在 app 主进程中运行。通过子进程调用 FreeCAD Python 执行 _freecad_csg_worker.py，
处理 pymcnp 对象的序列化和 JSON 协议。
"""

import json
import os
import subprocess
import tempfile
import shutil
import threading

# pymcnp Geometry AST 节点类型，在 freecad_preview 中延迟导入
_Intersection = None
_Union = None
_Unary = None
_Paren = None
_Digit = None


def _lazy_import_geometry():
    """延迟导入 pymcnp Geometry AST 类型"""
    global _Intersection, _Union, _Unary, _Paren, _Digit
    if _Intersection is None:
        from pymcnp.types.Geometry import (
            _Intersection, _Union, _Unary, _Paren, _Digit
        )


def parenthesize_unions(expr: str) -> str:
    """把 MCNP 顶层 ':' 并集的每段包上括号，让 pymcnp 正确解析为顶层 union。

    MCNP 语义 'a b c:d e f' = (a∩b∩c) ∪ (d∩e∩f)；pymcnp 会把 ':' 解析成
    链中普通并集导致几何错误。包上括号后 pymcnp 识别为顶层 union。
    已带括号的段保持原样；括号内的 ':' 不切分。
    """
    expr = (expr or "").strip()
    if not expr:
        return expr
    parts = []
    depth = 0
    start = 0
    for i, ch in enumerate(expr):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            parts.append(expr[start:i].strip())
            start = i + 1
    parts.append(expr[start:].strip())
    wrapped = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        wrapped.append(p if (p.startswith("(") and p.endswith(")")) else "(" + p + ")")
    return ":".join(wrapped)


def _geometry_ast_to_json(node):
    """递归遍历 pymcnp Geometry AST → JSON 列表"""
    _lazy_import_geometry()

    if isinstance(node, _Intersection):
        return ["intersect", _geometry_ast_to_json(node.left),
                _geometry_ast_to_json(node.right)]
    if isinstance(node, _Union):
        return ["union", _geometry_ast_to_json(node.left),
                _geometry_ast_to_json(node.right)]
    if isinstance(node, _Unary):
        signs = {"+": "pos", "-": "neg", "#": "complement"}
        return ["unary", _geometry_ast_to_json(node.operand),
                signs[node.operator]]
    if isinstance(node, _Paren):
        return _geometry_ast_to_json(node.ast)  # 括号不额外编码
    if isinstance(node, _Digit):
        val = str(node.value)
        if "." in val:
            # 宏体 facet 引用（如 -1.1 = 宏体 1 的第 1 个小面）：几何引擎尚未支持，
            # 编码成显式节点让调用方**跳过该栅元并归因**，而不是 int('1.1') 崩掉整次预览。
            num, _, facet = val.partition(".")
            return ["facet", int(num), int(facet)]
        return ["surf", int(val)]

    raise ValueError(f"未知 AST 节点: {type(node).__name__}")


def ast_has_facet(node) -> bool:
    """JSON AST 中是否含宏体 facet 引用（``["facet", n, f]``）。"""
    if isinstance(node, list):
        if node and node[0] == "facet":
            return True
        return any(ast_has_facet(x) for x in node)
    return False


def resolve_cell_complements(ast_node, cells_by_num: dict, stack=None):
    """把 AST 中的 #n（栅元补集算子）展开为对应栅元的完整几何。

    MCNP 语义：#n = 除栅元 n 外的所有空间 = bound_box 中不属于栅元 n 的区域。
    展开方法：把 `#n` 的 operand 从『曲面 n』替换成『栅元 n 的完整几何』，
    序列化后 worker 对 ["unary", X, "complement"] 执行 bound_box.cut(X)，
    即挖掉栅元 n 的实体。这样 `#43` 会挖掉栅元 43（空心反射体）而不是曲面 43。

    注意 #n 的操作数永远是栅元号（MCNP 语法无歧义，`#` 即判别器），
    与曲面号重合时查的是栅元表。preview-3d / export-step / cross-section 共用。
    """
    _lazy_import_geometry()
    if stack is None:
        stack = set()
    if isinstance(ast_node, _Unary) and ast_node.operator == "#":
        operand = ast_node.operand
        if isinstance(operand, _Digit):
            n = int(operand.value)
            if n in stack or n not in cells_by_num:
                return ast_node  # 循环引用或未知栅元，保持原样
            ref = cells_by_num[n]
            if ref is None:
                return ast_node
            inner = resolve_cell_complements(ref, cells_by_num, stack | {n})
            return _Unary("#", inner)
        return ast_node
    if isinstance(ast_node, _Intersection):
        return _Intersection(
            resolve_cell_complements(ast_node.left, cells_by_num, stack),
            resolve_cell_complements(ast_node.right, cells_by_num, stack))
    if isinstance(ast_node, _Union):
        return _Union(
            resolve_cell_complements(ast_node.left, cells_by_num, stack),
            resolve_cell_complements(ast_node.right, cells_by_num, stack))
    if isinstance(ast_node, _Paren):
        return _Paren(resolve_cell_complements(ast_node.ast, cells_by_num, stack))
    return ast_node


def _opt_float(value, default: float = 0.0) -> float:
    """pymcnp 可选字段（如锥面最后一项 ±1）缺失/None → 默认值。

    注意：真·双叶锥卡（``1 KZ 0 0.25``）pymcnp 直接拒绝解析，见
    :func:`cone_card_missing_sheet`；本函数兜的是"字段存在但为空"的情形。
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


#: 锥面助记符 → 省略最后一项 ±1 时的参数个数（KX/KY/KZ 顶点 + t²；K/X 等顶点 3 项 + t²）
_CONE_CARD_ARITY = {"KX": 2, "KY": 2, "KZ": 2, "K/X": 4, "K/Y": 4, "K/Z": 4}


def cone_card_missing_sheet(tokens: list, kw_idx: int) -> bool:
    """锥面卡是否省略了最后一项 ±1（MCNP：省略 = 双叶锥）。

    判定：助记符后面的**数值** token 个数恰好等于「顶点 + t²」参数个数。
    pymcnp 只认带第三/第五项（±1）的写法 → 双叶锥卡会被 ``from_mcnp`` 抛错，
    而 ``parse_surfaces`` 对抛错行是静默跳过（曲面缺失 → 引用它的栅元全丢）。
    故生产解析前补一个 ``0`` 表示双叶（见 ``quadric.cone_frame``：0 → sheet=0）。
    """
    try:
        kw = str(tokens[kw_idx]).upper()
    except (IndexError, TypeError):
        return False
    arity = _CONE_CARD_ARITY.get(kw)
    if arity is None:
        return False
    nums = 0
    for tok in tokens[kw_idx + 1:]:
        try:
            float(tok)
        except (TypeError, ValueError):
            continue  # *TRn 之类的非数值 token 不计
        nums += 1
    return nums == arity


def box_card_missing_vector(tokens: list, kw_idx: int) -> bool:
    """BOX 卡是否省略了第三个边向量（9 项 = 沿 A1×A2 方向无限，C810 §3-19）。

    pymcnp 直接拒收 9 项 BOX（InpError）→ ``parse_surfaces`` 静默跳过该曲面 →
    引用它的栅元在预览里整块消失。生产解析前补 ``0 0 0`` 当第三向量，
    由 ``quadric.box_params`` 识别为"无限棱柱"（两条路径都按无限处理）。
    """
    try:
        kw = str(tokens[kw_idx]).upper()
    except (IndexError, TypeError):
        return False
    if kw != "BOX":
        return False
    nums = 0
    for tok in tokens[kw_idx + 1:]:
        try:
            float(tok)
        except (TypeError, ValueError):
            continue
        nums += 1
    return nums == 9


def _pymcnp_surf_to_dict(surf):
    """从 pymcnp 表面对象提取 type/params/transform"""
    info = {"number": int(surf.number)}
    tr = getattr(surf, 'transform', None)
    info["transform"] = int(tr) if tr is not None else None
    kw = surf._KEYWORD.upper()

    # ── 单参数 ──
    if kw in ("PX", "PY", "PZ"):           p = [float(surf.d)]
    elif kw in ("SO", "CX", "CY", "CZ"):   p = [float(surf.r)]

    # ── 双参数 ──
    elif kw == "SX":   p = [float(surf.x), float(surf.r)]
    elif kw == "SY":   p = [float(surf.y), float(surf.r)]
    elif kw == "SZ":   p = [float(surf.z), float(surf.r)]

    # ── 球 ──
    elif kw == "S":    p = [float(surf.x), float(surf.y), float(surf.z), float(surf.r)]

    # ── 平行轴圆柱 ──
    elif kw == "C/X":  p = [float(surf.y), float(surf.z), float(surf.r)]
    elif kw == "C/Y":  p = [float(surf.x), float(surf.z), float(surf.r)]
    elif kw == "C/Z":  p = [float(surf.x), float(surf.y), float(surf.r)]

    # ── 圆锥 ──
    # 最后一项 ±1 可选（省略 = 双叶锥）→ 缺失时补 0，由 quadric.cone_frame 认双叶
    elif kw == "KX":   p = [float(surf.x), float(surf.t_squared), _opt_float(surf.plusminus_1)]
    elif kw == "KY":   p = [float(surf.y), float(surf.t_squared), _opt_float(surf.plusminus_1)]
    elif kw == "KZ":   p = [float(surf.z), float(surf.t_squared), _opt_float(surf.plusminus_1)]
    elif kw == "K/X":  p = [float(surf.x), float(surf.y), float(surf.z), float(surf.t_squared), _opt_float(surf.plusminus_1)]
    elif kw == "K/Y":  p = [float(surf.x), float(surf.y), float(surf.z), float(surf.t_squared), _opt_float(surf.plusminus_1)]
    elif kw == "K/Z":  p = [float(surf.x), float(surf.y), float(surf.z), float(surf.t_squared), _opt_float(surf.plusminus_1)]

    # ── 环面 ──
    elif kw in ("TX", "TY", "TZ"):  p = [float(surf.x), float(surf.y), float(surf.z), float(surf.a), float(surf.b), float(surf.c)]

    # ── 平面 ──
    elif kw == "P":
        if hasattr(surf, 'd'):
            p = [float(surf.a), float(surf.b), float(surf.c), float(surf.d)]
            kw = "P_0"
        else:
            p = [float(surf.x1), float(surf.y1), float(surf.z1),
                 float(surf.x2), float(surf.y2), float(surf.z2),
                 float(surf.x3), float(surf.y3), float(surf.z3)]
            kw = "P_1"

    # ── RPP ──
    elif kw == "RPP":  p = [float(surf.xmin), float(surf.xmax), float(surf.ymin), float(surf.ymax), float(surf.zmin), float(surf.zmax)]

    # ── Macrobody ──
    # 可选尾项统一在这里补齐（C810 §3-19），下游体素/FreeCAD 两条路径都吃满参形式：
    #   REC 10 项（第 10 项 = 短轴半径，方向 H×V1）→ 12 项
    #   RHP/HEX 9/12 项（s/t 省略，由 60° 旋转推出）→ 15 项
    # 旧行为：pymcnp 少项字段为 None → float(None) TypeError → build_geometry 直接
    # 「曲面序列化失败」→ 整个预览/导出失败。
    elif kw == "SPH":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.r)]
    elif kw == "RCC":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.hx), float(surf.hy), float(surf.hz), float(surf.r)]
    elif kw == "TRC":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.hx), float(surf.hy), float(surf.hz), float(surf.r1), float(surf.r2)]
    elif kw == "REC":
        from quadric import rec_params          # 延迟导入：本模块顶层保持 stdlib
        base = [float(surf.vx), float(surf.vy), float(surf.vz),
                float(surf.hx), float(surf.hy), float(surf.hz),
                float(surf.v1x), float(surf.v1y), float(surf.v1z)]
        if getattr(surf, "v2y", None) is None or getattr(surf, "v2z", None) is None:
            p = rec_params(base + [_opt_float(surf.v2x)])   # 10 项：第 10 项落在 v2x
        else:
            p = base + [float(surf.v2x), float(surf.v2y), float(surf.v2z)]
    elif kw == "ELL":  p = [float(surf.v1x), float(surf.v1y), float(surf.v1z), float(surf.v2x), float(surf.v2y), float(surf.v2z), float(surf.rm)]
    elif kw == "WED":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.v1x), float(surf.v1y), float(surf.v1z), float(surf.v2x), float(surf.v2y), float(surf.v2z), float(surf.v3x), float(surf.v3y), float(surf.v3z)]
    elif kw == "BOX":
        # 9 项（省略 A3）= 沿 A1×A2 无限（C810 3-19）；pymcnp 拒收这种卡，
        # 由 parse_surfaces 在文本层补 "0 0 0" 后再进来，这里只兜字段缺失
        p = [float(surf.vx), float(surf.vy), float(surf.vz),
             float(surf.a1x), float(surf.a1y), float(surf.a1z),
             float(surf.a2x), float(surf.a2y), float(surf.a2z),
             _opt_float(getattr(surf, "a3x", None)),
             _opt_float(getattr(surf, "a3y", None)),
             _opt_float(getattr(surf, "a3z", None))]
    elif kw in ("RHP", "HEX"):
        from quadric import rhp_params         # 延迟导入：本模块顶层保持 stdlib
        base = [float(surf.vx), float(surf.vy), float(surf.vz),
                float(surf.hx), float(surf.hy), float(surf.hz),
                float(surf.r1), float(surf.r2), float(surf.r3)]
        extra = []
        for f in ("s1", "s2", "s3", "t1", "t2", "t3"):
            v = getattr(surf, f, None)
            if v is None:      # 尾项是"连续省略"：到 None 就停，不能补零（补零会当成已给 s/t）
                break
            extra.append(float(v))
        p = rhp_params(base + extra)
    elif kw == "ARB":  p = [float(surf.ax), float(surf.ay), float(surf.az), float(surf.bx), float(surf.by), float(surf.bz), float(surf.cx), float(surf.cy), float(surf.cz), float(surf.dx), float(surf.dy), float(surf.dz), float(surf.ex), float(surf.ey), float(surf.ez), float(surf.fx), float(surf.fy), float(surf.fz), float(surf.gx), float(surf.gy), float(surf.gz), float(surf.hx), float(surf.hy), float(surf.hz), float(surf.n1), float(surf.n2), float(surf.n3), float(surf.n4), float(surf.n5), float(surf.n6)]

    # ── GQ / SQ ──
    elif kw == "GQ":  p = [float(surf.a), float(surf.b), float(surf.c), float(surf.d), float(surf.e), float(surf.f), float(surf.g), float(surf.h), float(surf.j), float(surf.k)]
    elif kw == "SQ":  p = [float(surf.a), float(surf.b), float(surf.c), float(surf.d), float(surf.e), float(surf.f), float(surf.g), float(surf.x), float(surf.y), float(surf.z)]

    # ── 点定义旋转体 ──
    elif kw in ("X", "Y", "Z"):
        pm = {"X": "x", "Y": "y", "Z": "z"}
        pf = pm[kw]
        p = []
        for i in range(1, 4):
            ai = getattr(surf, f"{pf}{i}", None)
            ri = getattr(surf, f"r{i}", None)
            if ai is not None and ri is not None:
                p += [float(ai), float(ri)]

    else:
        raise ValueError(f"未知曲面类型: {kw} (曲面 {info['number']})")

    info.update({"type": kw, "params": p})
    return info


def _surface_extent_values(surf_type: str, params: list) -> list:
    """按曲面类型返回 extent 相关数值（位移类：坐标/偏移/半径）。

    方向向量类（RCC/REC/TRC 的 h、BOX 的 a1/a2/a3、WED 的 v1/v2/v3、
    RHP/HEX 的 r/s/t）**不单独取模**，而与基点合成角点（顶点 = base + Σ向量）
    后参与 max-abs——否则宏体轴长/方向会被当坐标撑大 bound。
    GQ/SQ 二次型系数非坐标，由调用方跳过。未知类型保守取全部参数。
    """
    try:
        p = [float(v) for v in params]
    except (TypeError, ValueError):
        return []
    if not p:
        return []
    # 位移类：全部参数直接参与
    if surf_type in ("PX", "PY", "PZ", "SO", "CX", "CY", "CZ",
                     "SX", "SY", "SZ", "S", "C/X", "C/Y", "C/Z",
                     "P_1", "RPP", "SPH", "ELL", "X", "Y", "Z"):
        return p
    if surf_type in ("KX", "KY", "KZ"):
        return p[:1]          # 顶点坐标，跳过 t²/sgn
    if surf_type in ("K/X", "K/Y", "K/Z"):
        return p[:3]          # 顶点，跳过 t²/sgn
    if surf_type in ("TX", "TY", "TZ"):
        # C810 §3-14：径向范围 = |A| + |C|（A 主半径、C **径向**次半径）、轴向 = |B|。
        # 旧实现 p[:5] 只取 A/B 并把 C 当"占位"跳过 → 大 C 环面 bound 少算 → 被裁。
        x0, y0, z0, A, Bb, C = (float(v) for v in p[:6])
        return [x0, y0, z0, abs(A) + abs(C), abs(Bb)]
    if surf_type == "P_0":
        return [p[3]] if len(p) >= 4 else p   # 跳过法向 A/B/C
    if surf_type == "ARB":
        return p[:24]         # 8 顶点坐标，跳过面定义
    # ── Macrobody：方向向量与基点合成角点 ──
    if surf_type in ("RCC", "TRC"):
        v, h = p[:3], p[3:6]
        radii = p[6:]
        return list(v) + [v[i] + h[i] for i in range(3)] + list(radii)
    if surf_type == "REC":
        v, h = p[:3], p[3:6]
        v1, v2 = p[6:9], p[9:12]
        return (list(v) + [v[i] + h[i] for i in range(3)]
                + [v[i] + v1[i] + v2[i] for i in range(3)]
                + list(v1) + list(v2))
    if surf_type == "WED":
        v = p[:3]
        v1, v2, v3 = p[3:6], p[6:9], p[9:12]
        return (list(v) + [v[i] + v1[i] + v2[i] for i in range(3)]
                + [v[i] + v3[i] for i in range(3)]
                + [v[i] + v1[i] + v2[i] + v3[i] for i in range(3)])
    if surf_type == "BOX":
        v = p[:3]
        a1, a2, a3 = p[3:6], p[6:9], p[9:12]
        return list(v) + [v[i] + a1[i] + a2[i] + a3[i] for i in range(3)]
    if surf_type in ("RHP", "HEX"):
        v, h = p[:3], p[3:6]
        r, s, t = p[6:9], p[9:12], p[12:15]
        vals = list(v) + [v[i] + h[i] for i in range(3)]
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    vals += [v[i] + sx * r[i] + sy * s[i] + sz * t[i] for i in range(3)]
        return vals
    return p  # 未知类型保守取全部


def _compute_bound_from_surfaces(surf_dicts: list, default: float = 500) -> float:
    """根据曲面参数的最大坐标估算 FreeCAD 包围盒半边长。

    只对位移类参数（空间坐标/偏移/半径）取 max-abs；宏体方向向量与基点合成
    角点后参与，避免把轴长/方向当坐标撑大 bound（shield_20m RCC h=(0,0,4000)
    是轴长非坐标 → B 从 5300 修正为 2700）。GQ/SQ 参数是二次型系数非坐标，
    经二次曲面分类换算成真实空间范围后参与；无界/退化仍跳过。
    最终 max*1.3+100 与 default 取大，保证大几何不被 FreeCAD 的 [-B,B]³ 盒子裁剪。
    """
    max_coord = 0.0
    for s in surf_dicts:
        # GQ/SQ：先经分类换算空间范围；系数本身（含大常数项）不是坐标，
        # 直接取 max-abs 会把 bound 撑到上万，导致所有几何用巨大盒子渲染而失真
        gq_vals = _gq_extent_values(s.get("type", ""), s.get("params", []) or [])
        if gq_vals:
            max_coord = max(max_coord, *(abs(float(v)) for v in gq_vals))
            continue
        if s.get("type") in ("GQ", "SQ"):
            continue  # 无界/退化 → 系数不是坐标，不参与 extent
        for v in _surface_extent_values(s.get("type", ""), s.get("params", []) or []):
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if abs(f) > max_coord:
                max_coord = abs(f)
    return max(max_coord * 1.3 + 100, default)


def _gq_extent_values(surf_type: str, params: list) -> list:
    """GQ/SQ 有界曲面贡献的真实空间范围（AABB 有界轴的 lo/hi）。

    系数不是坐标，须经二次曲面分类（quadric.gq_aabb）换算成空间范围；
    无界/退化（如参数被误填成 1e6 的常数）→ []，不撑大 bound。
    """
    if surf_type not in ("GQ", "SQ"):
        return []
    try:
        p = [float(v) for v in params]
    except (TypeError, ValueError):
        return []
    if not p:
        return []
    try:
        from quadric import gq_aabb, sq_to_gq
    except ImportError:  # 测试/直接 import app 包时 quadric 在 app/ 下
        from app.quadric import gq_aabb, sq_to_gq
    if surf_type == "SQ":
        p = sq_to_gq(p)
    aabb = gq_aabb(p)
    if not aabb:
        return []
    (lox, loy, loz), (hix, hiy, hiz), axes = aabb
    vals = []
    for lo, hi, b in ((lox, hix, axes[0]), (loy, hiy, axes[1]),
                      (loz, hiz, axes[2])):
        if b:
            vals += [lo, hi]
    return vals


def model_extent_unpadded(surf_dicts: list) -> float:
    """A1.2 匹配检测用模型范围（无 padding、无 500 兜底）。

    与 _compute_bound_from_surfaces 的差异：匹配检测需要**真实**范围——
    _compute_bound 的 max*1.3+100 与 default=500 会把小模型（如 rpp -1 1 -1 1 0 1）
    撑成 ±500 盒子，导致「网格离模型上百厘米却判匹配」漏报错位（绝不静默错位）。
    此处 max-abs 后原样返回；GQ/SQ 经分类取真实范围；空输入返回 0.0。
    """
    max_coord = 0.0
    for s in surf_dicts:
        gq_vals = _gq_extent_values(s.get("type", ""), s.get("params", []) or [])
        if gq_vals:
            max_coord = max(max_coord, *(abs(float(v)) for v in gq_vals))
            continue
        if s.get("type") in ("GQ", "SQ"):
            continue  # 无界/退化 → 系数不是坐标，不参与 extent
        for v in _surface_extent_values(s.get("type", ""), s.get("params", []) or []):
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if abs(f) > max_coord:
                max_coord = abs(f)
    return max_coord


class FreeCADEngine:
    """FreeCAD CSG 几何引擎封装。

    通过子进程调用 FreeCAD Python 执行布尔几何运算。
    主进程负责 pymcnp 对象的序列化和结果收集。
    """

    def __init__(self, freecad_bin: str):
        """
        Args:
            freecad_bin: FreeCAD 的 bin 目录路径 (StepImporter.detect_freecad() 返回值)
        """
        self._freecad_bin = freecad_bin
        self._tmpdir_obj = None
        # 重合检测结果（build_geometry(check_overlaps=True) 时填充）
        self.overlaps = []
        self.overlap_truncated = False
        self.overlap_unresolved = []
        self.zero_volume = []
        # 栅元封闭性检测结果（build_geometry(check_closure=True) 时填充）
        self.closure_report = {}
        # 因能力限制被跳过的栅元（如宏体 facet 引用）：[{number, reason}]
        self.skipped_cells = []

    def build_geometry(self, pymcnp_surfaces: list, cells_data: list,
                       tr_cards: dict, bound: float = 500,
                       fmt: str = "stl", single_file: bool = False,
                       check_overlaps: bool = False,
                       focus_num: int | None = None,
                       focus_nums: list[int] | None = None,
                       check_closure: bool = False) -> dict[int, str]:
        """从 pymcnp 对象和栅元数据构建各栅元的 CSG 几何。

        Args:
            pymcnp_surfaces: _parse_surface_line() 返回的 pymcnp 表面对象列表
            cells_data: [{number, ast (Geometry 节点), material, density}]
            tr_cards: {"1": {"translate": [...], "rotate": [[...],...]}}
            bound: 半空间包围盒半边长 (BOUND)
            fmt: 输出格式 ("stl" | "step")
            single_file: True=所有栅元合并为单个文件, False=每个栅元单独文件
            check_overlaps: True=同时做栅元重合检测，结果存 self.overlaps 等
            focus_num / focus_nums: 重合检测聚焦栅元（可选）
            check_closure: True=同时做每个栅元的封闭性判定（closed/infinite/
                empty/voxel/unresolvable），结果存 self.closure_report

        Returns:
            {cell_number: 输出文件路径}

        Raises:
            RuntimeError: FreeCAD 进程失败或输出解析失败
        """
        # 1. 序列化 pymcnp 对象
        surf_dicts = []
        for s in pymcnp_surfaces:
            try:
                surf_dicts.append(_pymcnp_surf_to_dict(s))
            except (ValueError, AttributeError) as e:
                raise RuntimeError(f"曲面 {getattr(s, 'number', '?')} 序列化失败: {e}")

        # 根据曲面参数自适应 bound（大几何不被裁剪）
        bound = _compute_bound_from_surfaces(surf_dicts, default=bound)

        # 2. 序列化 Geometry AST
        cell_dicts = []
        self.skipped_cells = []
        for c in cells_data:
            try:
                ast_json = _geometry_ast_to_json(c["ast"].ast)
            except (ValueError, AttributeError) as e:
                raise RuntimeError(f"栅元 {c['number']} AST 序列化失败: {e}")
            if ast_has_facet(ast_json):
                # 宏体 facet 引用（1.1 之类）几何引擎未支持：跳过该栅元并归因，
                # 不让一个栅元拖垮整次预览（旧行为：int('1.1') ValueError → 整次 500）
                self.skipped_cells.append({
                    "number": c["number"],
                    "reason": "宏体 facet 引用（如 1.1）暂不支持预览",
                })
                continue
            cell_dicts.append({
                "number": c["number"],
                "material": str(c.get("material", "0")),
                "ast": ast_json,
            })

        # 3. 准备临时目录
        tmp_dir = self._tmpdir()
        input_json = {
            "surfaces": surf_dicts,
            "tr_cards": tr_cards,
            "cells": cell_dicts,
            "bound": bound,
            "output_dir": tmp_dir,
            "format": fmt,
            "single_file": single_file,
            "check_overlaps": check_overlaps,
            "check_closure": check_closure,
            "focus_nums": focus_nums if focus_nums is not None
            else ([focus_num] if focus_num is not None else None),
        }

        # 4. 子进程调用 FreeCAD
        result_data = self._run_freecad_script(input_json)

        # 5. 收集输出
        result = {}
        self.overlaps = result_data.get("overlaps", []) or []
        self.overlap_truncated = bool(result_data.get("overlap_truncated", False))
        self.overlap_unresolved = result_data.get("overlap_unresolved", []) or []
        self.zero_volume = result_data.get("zero_volume", []) or []
        self.closure_report = result_data.get("closure_report", {}) or {}
        for cell_num_str, entry in result_data.get("files", {}).items():
            if isinstance(entry, dict) and "vertices" in entry:
                # fmt="mesh": 直接返回顶点/三角面数据
                result[int(cell_num_str)] = entry
            elif isinstance(entry, str):
                # fmt="stl"|"step": 文件路径
                result[int(cell_num_str)] = os.path.join(tmp_dir, entry)

        return result

    def export_step(self, pymcnp_surfaces: list, cells_data: list,
                    tr_cards: dict, out_dir: str, bound: float = 500) -> list[str]:
        """将所有栅元导出为一个 STEP 文件（跳过真空/空气栅元）"""
        result = self.build_geometry(pymcnp_surfaces, cells_data,
                                     tr_cards, bound=bound, fmt="step", single_file=True)
        files = []
        for src_path in result.values():
            dst = os.path.join(out_dir, "geometry.step")
            if os.path.abspath(src_path) != os.path.abspath(dst):
                shutil.copy2(src_path, dst)
            files.append(dst)
        return files

    def _run_freecad_script(self, input_data: dict) -> dict:
        """写入临时 JSON → spawn FreeCAD Python → 收集输出"""
        python_exe = os.path.join(self._freecad_bin, "python.exe")
        if not os.path.isfile(python_exe):
            # 便携版（免安装）FreeCAD：bin 目录可能不含 python.exe，
            # 尝试 bin/ 子目录（freecad_locator.bin_dir() 已处理此情况，
            # 但若调用方绕过 bin_dir() 直接传路径，此处兜底）
            alt = os.path.join(self._freecad_bin, "bin", "python.exe")
            if os.path.isfile(alt):
                python_exe = alt
            else:
                raise RuntimeError(f"FreeCAD Python 未找到: {python_exe}")

        script_path = self._worker_script_path()

        proc = subprocess.run(
            [python_exe, script_path],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if proc.returncode != 0:
            stderr_tail = proc.stderr[-500:] if proc.stderr else "无错误输出"
            stdout_tail = proc.stdout[-300:] if proc.stdout else ""
            raise RuntimeError(
                f"FreeCAD 进程退出码 {proc.returncode}\n"
                f"stderr: {stderr_tail}\n"
                f"stdout: {stdout_tail}"
            )

        # 解析 stdout JSON
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"FreeCAD 输出解析失败: {e}\n"
                f"stdout: {proc.stdout[:500]}"
            )

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "FreeCAD 返回未知错误"))

        # 如果有警告，这里可以处理
        # for w in result.get("warnings", []):
        #     logger.warning(w)

        return result

    def _worker_script_path(self) -> str:
        """定位 _freecad_csg_worker.py"""
        return os.path.join(os.path.dirname(__file__), "_freecad_csg_worker.py")

    def _tmpdir(self) -> str:
        """创建并返回临时目录。每个引擎实例一个临时目录。"""
        if self._tmpdir_obj is None:
            self._tmpdir_obj = tempfile.mkdtemp(prefix="freecad_csg_")
        return self._tmpdir_obj

    def cleanup(self):
        """删除临时文件"""
        if self._tmpdir_obj is not None and os.path.isdir(self._tmpdir_obj):
            shutil.rmtree(self._tmpdir_obj, ignore_errors=True)
            self._tmpdir_obj = None

    def __del__(self):
        self.cleanup()
