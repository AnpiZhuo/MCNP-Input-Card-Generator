"""§6.2 vtk 惰性化 —— AST 断言 worker 顶层无 import vtk，惰性 import 在 _quadric_to_shape 内。

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
    assert hits, "vtk 惰性 import 未出现在 _quadric_to_shape 函数体内"


def test_worker_vtk_import_after_native_fallback():
    """惰性 import 行必须位于 native 回退之后（marching cubes 分支执行前）。"""
    lines = WORKER.read_text(encoding="utf-8").splitlines()
    import_lines = [ln for ln, _ in _function_vtk_imports(WORKER, "_quadric_to_shape")]
    assert import_lines
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
    assert found, "模块顶层应初始化 _HAVE_VTK = False"
