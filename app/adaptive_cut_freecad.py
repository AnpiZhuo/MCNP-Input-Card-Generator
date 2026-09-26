# -*- coding: utf-8 -*-
"""FreeCAD 侧的实体预分解执行体（**子进程**，由 adaptive_decompose.decompose 拉起）。

用法：python.exe adaptive_cut_freecad.py <request.json> <result.json>

为什么是独立文件而不是内嵌字符串
=================================
本脚本要跑在 **FreeCAD 的 python.exe** 里（要 `import FreeCAD/Part/BOPTools`），
而父侧代码跑在后端解释器里。两者解释器不同 ⇒ 必须是**两个文件**，不能是一个模块
里的函数。父侧只管"写请求、拉起、读报告"，本文件只管"切"。

为什么只依赖 FreeCAD、**不 import GEOUNED**
==========================================
早期探针直接复用了 GEOUNED 的 `decom_one.gen_plane`，但那只是 4 行 `Part.makePlane`
包装（见 GEOUNED `decompose/decom_one.py:126`）。多一个 import 就多一个"GEOUNED 路径
没配好 ⇒ 整个分解失败"的失败模式，而它换来的只是 4 行代码。这里内联。

切法（为什么是"最长边中分"而不是"等距网格"）
=============================================
网格切 K 档只能得到 3^K 块数（3/27/81/192…），无法对准"每块 ≤30 面"这个目标：K=3 时
最大块还有 50 面，K=4 就冲到 192 块。最长边二分是**按结果收敛**的：每块自己判断要不要
再切，块数是结果不是输入。实测 274 m³ 厂房模型：目标 30 面 → 18 块（原 3 块），
目标 50 面 → 9 块，目标 20 面 → 41 块。

诚实性约定（**不静默假装达标**）
================================
切不动的块（三轴都切不出两块，或到深度上限）**保留原样并计数**，写进报告的
`over_limit` / `unsplit`。使用者看到的是"41 块里有 2 块仍是 21 面"，而不是一句
"已完成"。体积同理：`eps` 只用来**否决一次退化的切割**，绝不用来偷偷扔掉小块 ——
所以体积比在报告里始终可见（实测 1.0000000）。
"""
import json
import os
import sys
import time

import FreeCAD
import Part
import BOPTools.SplitAPI as SA

# 深度上限：2^8 = 256 片/实体，够 274 m³ 模型从 3 块切到 41 块（目标 20 面）还有余量
DEFAULT_MAX_DEPTH = 8
# 碎屑阈值（cm³）：小于它的碎片视为"这次切分退化"，否决该次切割（不丢体积）
DEFAULT_EPS_CM3 = 1e-6
# 全局块数保险：超过就停止细分并把剩余块计入 over_limit（防止病态输入把内存吃光）
DEFAULT_MAX_PIECES = 4000


def gen_plane(pos, normal, diag):
    """GEOUNED `gen_plane` 的内联版：一块足够大的方形平面，用来当切割面。

    两段式是关键：先 `makePlane` 拿到一个已知顶点，算出"面内偏移向量"，把起点挪到
    对角外侧再建一次，保证 2*diag 的方板**完整覆盖**实体（否则切割面比实体小，
    布尔切出来的是残缺的）。
    """
    plane = Part.makePlane(diag, diag, pos, normal)
    vec_on_plane = plane.Vertexes[3].Point.sub(plane.Vertexes[0].Point)
    new_pos = plane.Vertexes[0].Point.sub(vec_on_plane)
    return Part.makePlane(2.0 * diag, 2.0 * diag, new_pos, normal)


def cut_once(piece, eps_cm3):
    """沿包围盒最长边中分；返回 ≥2 个像样的块则成功，否则 None（换下一根轴）。

    "像样"= 每块体积 ≥ eps_cm3。只用它**否决**，不丢弃 —— 切出来带碎屑说明这次
    切分退化（切到了退化的薄壳上），换轴重试比留一颗碎屑强。
    """
    bb = piece.BoundBox
    dims = [bb.XLength, bb.YLength, bb.ZLength]
    for ax in sorted(range(3), key=lambda a: -dims[a]):
        if dims[ax] <= 0:
            continue
        lo = (bb.XMin, bb.YMin, bb.ZMin)[ax]
        n = [0.0, 0.0, 0.0]
        n[ax] = 1.0
        c = bb.Center
        pos = FreeCAD.Vector(c.x, c.y, c.z)
        pos[ax] = lo + dims[ax] / 2.0
        diag = max(bb.DiagonalLength, 1.0)
        try:
            res = SA.slice(piece, [gen_plane(pos, FreeCAD.Vector(*n), diag)], "Standard")
        except Exception:
            continue
        parts = [s for s in res.Solids if s.Volume / 1000.0 >= eps_cm3]
        if len(parts) >= 2:
            return parts
    return None


def _leaf(stats, piece, *, more=False):
    """记一个叶子（保留的块）。`more=True` 表示它是"没切动"留下的。"""
    stats["leaves"] += 1
    if more:
        stats["unsplit"] += 1
        stats["over_limit"] += 1
    return piece


def refine(piece, limit, eps_cm3, max_depth, stats, depth=0):
    """递归：够简单就留，否则切一刀再来。返回该块贡献的叶子列表。"""
    if len(piece.Faces) <= limit:
        return [_leaf(stats, piece)]
    if depth >= max_depth or stats["leaves"] >= stats["max_pieces"]:
        return [_leaf(stats, piece, more=True)]
    parts = cut_once(piece, eps_cm3)
    if parts is None:
        return [_leaf(stats, piece, more=True)]
    stats["cuts"] += 1
    out = []
    for q in parts:
        out.extend(refine(q, limit, eps_cm3, max_depth, stats, depth + 1))
    return out


def run(req):
    src = req["src"]
    dst = req["dst"]
    limit = int(req.get("face_limit") or 30)
    max_depth = int(req.get("max_depth") or DEFAULT_MAX_DEPTH)
    eps_cm3 = float(req.get("eps_cm3") or DEFAULT_EPS_CM3)

    t0 = time.time()
    shape = Part.Shape()
    shape.read(src)
    solids = list(shape.Solids)
    if not solids:
        raise RuntimeError("STEP 里没有实体（Solids=0）")
    in_vol_mm3 = sum(s.Volume for s in solids)

    stats = {"cuts": 0, "unsplit": 0, "over_limit": 0, "leaves": 0,
             "max_pieces": int(req.get("max_pieces") or DEFAULT_MAX_PIECES)}
    pieces = []
    for s in solids:
        if stats["leaves"] >= stats["max_pieces"]:
            break
        pieces.extend(refine(s, limit, eps_cm3, max_depth, stats))

    if not pieces:
        raise RuntimeError("分解后没有剩下任何实体")
    fs = sorted(len(p.Faces) for p in pieces)
    out_vol_mm3 = sum(p.Volume for p in pieces)
    ratio = (out_vol_mm3 / in_vol_mm3) if in_vol_mm3 > 0 else 0.0

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    Part.makeCompound(pieces).exportStep(dst)

    return {
        "src": src,
        "dst": os.path.abspath(dst),
        "face_limit": limit,
        "input_solids": len(solids),
        "input_faces": sorted(len(s.Faces) for s in solids),
        "blocks": len(pieces),
        "faces": {"min": fs[0], "median": fs[len(fs) // 2], "max": fs[-1]},
        "over_limit": sum(1 for f in fs if f > limit),
        "unsplit": stats["unsplit"],
        "cuts": stats["cuts"],
        "slivers": sum(1 for p in pieces if p.Volume / 1000.0 < eps_cm3),
        "volume_ratio": ratio,
        "bytes": os.path.getsize(dst),
        "seconds": time.time() - t0,
    }


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: adaptive_cut_freecad.py <request.json> <result.json>\n")
        return 2
    req_path, res_path = sys.argv[1], sys.argv[2]
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            req = json.load(f)
        rep = run(req)
        payload = {"ok": True, "report": rep}
    except Exception as exc:  # noqa: BLE001 —— 子进程边界：任何异常都要变成可读报告
        import traceback
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                   "traceback": traceback.format_exc()[-2000:]}
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if payload["ok"]:
        r = payload["report"]
        print("adaptive cut: {} solids -> {} blocks, faces {}-{} (limit {}), "
              "over_limit={}, volume_ratio={:.7f}, {:.1f}s".format(
                  r["input_solids"], r["blocks"], r["faces"]["min"], r["faces"]["max"],
                  r["face_limit"], r["over_limit"], r["volume_ratio"], r["seconds"]),
              flush=True)
        return 0
    sys.stderr.write(payload["error"] + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
