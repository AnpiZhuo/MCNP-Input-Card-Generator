"""
FreeCAD STEP 方向预览 worker —— 读 STEP、镶嵌成 STL，**不做任何转换**。

用途（用户 2026-10-08：「给个按钮，点一下先用 STEP 生成预览，方便选择 Y/Z 朝上」）：
本 worker 只负责"把 STEP 变成能看的网格"，朝向/原点的**变换在主进程里做**
（`app/stl_transform.py`，毫秒级）⇒ 切换上轴不必重跑 FreeCAD。

协议（与其它 worker 一致）:
    stdin : {"step_path", "output_dir", "deflection"?: float}
    stdout: {"status":"ok","files":["step_preview.stl"],"bbox":[[..],[..]],"solids":N,"triangles":M,
             "warnings":[...]} 或 {"status":"error","message":...}
"""
import json
import os
import sys

try:
    import FreeCAD
    import Part
    import Mesh as FcMesh
except ImportError as e:
    print(json.dumps({"status": "error", "message": f"FreeCAD 导入失败: {e}"}))
    sys.exit(1)


def main():
    data = json.load(sys.stdin)
    step_path = data["step_path"]
    out_dir = data["output_dir"]
    # 预览用：容差可以粗一点（1.0 mm 级），换来"点一下就能看"
    deflection = float(data.get("deflection") or 1.0)
    os.makedirs(out_dir, exist_ok=True)

    shape = Part.Shape()
    shape.read(step_path)
    solids = list(getattr(shape, "Solids", []) or [])
    src = solids if solids else ([shape] if not shape.isNull() else [])
    if not src:
        print(json.dumps({"status": "error", "message": "STEP 里没有可显示的实体"}))
        return

    warnings = []
    meshes = []
    for i, sol in enumerate(src):
        try:
            meshes.append(FcMesh.Mesh(sol.tessellate(deflection)))
        except Exception as e:  # noqa: BLE001 —— 单个实体失败不该让整次预览失败
            warnings.append(f"实体 {i + 1} 镶嵌失败：{type(e).__name__}: {e}")

    if not meshes:
        print(json.dumps({"status": "error", "message": "所有实体镶嵌都失败了", "warnings": warnings}))
        return

    merged = FcMesh.Mesh()
    for m in meshes:
        merged.addMesh(m)
    path = os.path.join(out_dir, "step_preview.stl")
    merged.write(path)

    # 包围盒直接用 FreeCAD 的 BoundBox（MeshPoint 不可下标，别去遍历顶点）
    bb = merged.BoundBox
    lo = [bb.XMin, bb.YMin, bb.ZMin]
    hi = [bb.XMax, bb.YMax, bb.ZMax]
    print(json.dumps({
        "status": "ok",
        "files": [os.path.basename(path)],
        "bbox": [[float(v) for v in lo], [float(v) for v in hi]],
        "solids": len(src),
        "triangles": int(len(merged.Facets)),
        "warnings": warnings,
    }))


if __name__ == "__main__":
    main()
