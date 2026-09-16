"""§6.2 vtk 依赖移除 —— AST 断言 worker 全文件无 import vtk / from vtk。

不 import worker（其导入 FreeCAD，本机不可用）；读源码 ast.parse，仿 test_tech_debt.py。
验收：模块顶层无 `import vtk`/`from vtk`；`import vtk` 出现在 `_quadric_to_shape`
函数体内且位于 native 回退（marching cubes 分支）之后；`_HAVE_VTK` 顶层初值 False。
"""
import ast
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
WORKER = PROJECT_DIR / "app" / "_freecad_csg_worker.py"


def _module_top_vtk_imports(file_path: Path) -> list[int]:
    """返回模块顶层（非函数内）的 vtk import 行号。"""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    lines = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "vtk" or a.name.startswith("vtk."):
                    lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "vtk" or node.module.startswith("vtk.")):
                lines.append(node.lineno)
    return lines


def _function_vtk_imports(file_path: Path, func_name: str) -> list[tuple[int, str]]:
    """返回 (行号, import 语句)：在 FunctionDef 内部的 vtk 导入。"""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for a in child.names:
                    if a.name == "vtk" or a.name.startswith("vtk."):
                        hits.append((child.lineno, f"import {a.name}"))
            elif isinstance(child, ast.ImportFrom):
                if child.module and (child.module == "vtk" or
                                     child.module.startswith("vtk.")):
                    hits.append((child.lineno, f"from {child.module} import ..."))
    return hits


def test_worker_module_top_has_no_vtk_import():
    """模块顶层不得 import vtk（每次子进程启动免白付 ~0.46s）。"""
    top = _module_top_vtk_imports(WORKER)
    assert top == [], f"_freecad_csg_worker.py 模块顶层仍有 vtk import: {top}"


def test_worker_vtk_lazily_imported_in_quadric_to_shape():
    """vtk 惰性 import 必须出现在 _quadric_to_shape 函数体内。"""
    hits = _function_vtk_imports(WORKER, "_quadric_to_shape")
    assert hits == [], "worker 全文件不得有 vtk 导入"


def test_worker_vtk_import_after_native_fallback():
    """惰性 import 行必须位于 native 回退之后（marching cubes 分支执行前）。"""
    lines = WORKER.read_text(encoding="utf-8").splitlines()
    import_lines = [ln for ln, _ in _function_vtk_imports(WORKER, "_quadric_to_shape")]
    assert import_lines == [], "worker 全文件不得有 vtk 导入"
    # native 调用行（排除函数定义行）
    native_call = [i + 1 for i, l in enumerate(lines)
                   if "_quadric_to_native(qtype" in l and "def " not in l]
    assert native_call, "未找到 _quadric_to_native 调用行"
    for il in import_lines:
        assert il > native_call[0], (
            f"vtk import 行 {il} 应位于 native 回退 (行 {native_call[0]}) 之后"
        )


def test_worker_have_vtk_flag_initially_false():
    """模块顶层 _HAVE_VTK 初值必须为 False（默认不加载 vtk）。"""
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    found = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "_HAVE_VTK":
                    assert isinstance(node.value, ast.Constant), "_HAVE_VTK 顶层须字面量赋值"
                    assert node.value.value is False, "_HAVE_VTK 顶层初值须为 False"
                    found = True
    assert not found, "worker 不应再保留 _HAVE_VTK 惰性开关"



def test_worker_imports_pure_numpy_marching_cubes():
    """worker 必须接入 app/mc.py（FreeCAD 自带 Python 无 vtk）。"""
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    imported_mc = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "mc":
                    imported_mc = True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "app" and any(a.name == "mc" for a in node.names):
                imported_mc = True
    assert imported_mc, "worker 未导入 app/mc.py"


def test_worker_has_no_vtk_import_anywhere():
    """全文件（含函数体）不得出现 vtk import——已改为纯 numpy marching cubes。"""
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "vtk" or a.name.startswith("vtk."):
                    hits.append((node.lineno, f"import {a.name}"))
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "vtk" or node.module.startswith("vtk.")):
                hits.append((node.lineno, f"from {node.module} import ..."))
    assert hits == [], f"_freecad_csg_worker.py 仍含 vtk import: {hits}"


def test_worker_tr_surface_builds_in_local_box_then_transforms():
    """TRn 曲面：必须在**局部放大盒**里造半空间 → 变换 → 再与世界盒取交。

    2026-09-16 修：旧行为 `T(盒 − 实体)` 把"已裁剪"结果整体平移/旋转，既不是原曲面也不是原盒
    —— 实测 `K/Z` 带 `TR2 5 0 0` 的 STL 包围盒 x[-500,10]（正确应为 x[0,10]），
    而圆柱当年靠 `_make_primitive` 特例绕开了，锥/球/宏体全中。
    修法统一为 `B_loc = √3·B + |平移|` 的局部盒 + 变换 + `common(世界盒)`，
    因此 `_make_primitive` 特例已删除。

    Worker 需要 FreeCAD，无法在 pytest 里跑运行期；此用例做源码级锁（同文件既有范式）。
    """
    src = WORKER.read_text(encoding="utf-8")
    assert "B_loc = math.sqrt(3.0) * B" in src, "TR 局部盒放大公式缺失（TR 曲面会裁剪错）"
    assert "shape = shape.common(bound_box)" in src, "TR 曲面变换后必须与世界盒取交"
    assert "def _make_primitive" not in src, "旧的原语特例实现应已删除（统一走局部盒方案）"
    assert "prim = _make_primitive" not in src, "旧的原语特例调用点应已删除"
    assert "引用了 TR" in src, "引用缺失 TR 卡时必须留告警（不能静默按未变换处理）"
