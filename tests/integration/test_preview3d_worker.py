"""§6.2 vtk 依赖移除 —— AST 断言 worker 全文件无 import vtk / from vtk。

不 import worker（其导入 FreeCAD，本机不可用）；读源码 ast.parse，仿 test_tech_debt.py。
验收：模块顶层无 `import vtk`/`from vtk`；`import vtk` 出现在 `_quadric_to_shape`
函数体内且位于 native 回退（marching cubes 分支）之后；`_HAVE_VTK` 顶层初值 False。
"""
import ast
import json
import subprocess
from pathlib import Path

import pytest

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


# ══════════════════════════════════════════════════════════════════════
# 平面半空间必须盖满包围盒（2026-09-24；运行期用例，要 FreeCAD）
# ══════════════════════════════════════════════════════════════════════

_WORKER_APP = PROJECT_DIR / "app"

_HALFSPACE_SNIPPET = '''
import sys, json
sys.path.insert(0, "@APP@")
import FreeCAD, Part          # noqa: F401  FreeCAD 必须早于 Part
import _freecad_csg_worker as W

B = 500.0
bb = W._make_box(-B, B, -B, B, -B, B)
cases = {
    # A 只是个小分量 ⇒ 旧实现取的 (D/A, 0, 0) 严重偏离法向，厚板横向盖不满盒子
    "P0_A_small":  ("P_0", [0.1, 0.9, 0.4, 100.0]),
    "P0_A_tiny":   ("P_0", [0.001, 0.707, 0.707, 300.0]),
    # 平面在原点负侧较远 ⇒ 厚度不够（块 003 残留 +249% → 横向修好后仍 +0.49% 的那一档）
    "P0_neg_far":  ("P_0", [-0.852, -0.523, 0.0, -462.61]),
    "P0_axis":     ("P_0", [1.0, 0.0, 0.0, 400.0]),
    # 三点形式（一直取最近点，作为反向保护）
    "P1":          ("P_1", [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]),
}

# 盒内采样：3x3x3 网格（含 8 角点、12 棱中点、6 面心、原点）
grid = [-B, 0.0, B]
pts = [(x, y, z) for x in grid for y in grid for z in grid]

out = {}
for name, (t, p) in cases.items():
    h = W.make_halfspace(t, p, B)
    if t == "P_0":
        nx, ny, nz, D = (float(v) for v in p)
    else:
        from quadric import plane_from_points
        nx, ny, nz, D = plane_from_points([float(v) for v in p])
    nrm = (nx * nx + ny * ny + nz * nz) ** 0.5
    ux, uy, uz = nx / nrm, ny / nrm, nz / nrm
    dd = D / nrm
    mism = []
    for (x, y, z) in pts:
        f = ux * x + uy * y + uz * z - dd
        if abs(f) < 1e-9:          # 落在平面上，容差内无意义
            continue
        occ = bool(h.isInside(FreeCAD.Vector(x, y, z), 1e-6, True))
        if occ != (f > 0):
            mism.append({"pt": [x, y, z], "f": f, "occ": occ})
    out[name] = {"mismatch": mism, "n": len(pts)}
print(json.dumps(out))
'''


@pytest.fixture(scope="module")
def halfspace_probe():
    """子进程里跑真 worker 的 `make_halfspace`，逐点对比 OCC 判定与解析判定。"""
    from app.freecad_locator import bin_dir
    b = bin_dir()
    if not b:
        pytest.skip("FreeCAD 不可用，跳过半空间覆盖不变量直验")
    exe = Path(b) / "python.exe"
    if not exe.is_file():
        exe = Path(b) / "bin" / "python.exe"
    if not exe.is_file():
        pytest.skip(f"FreeCAD python.exe 未找到：{b}")
    snippet = _HALFSPACE_SNIPPET.replace("@APP@", _WORKER_APP.as_posix())
    proc = subprocess.run([str(exe), "-c", snippet], capture_output=True,
                          text=True, timeout=600, cwd=str(PROJECT_DIR))
    if proc.returncode != 0:
        pytest.fail(f"半空间探针失败：{proc.stderr[-1500:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_plane_halfspace_matches_the_analytic_halfspace(halfspace_probe):
    """半空间的形状必须**逐点等于**解析半空间 `{x ∈ 盒 : n·x > n·p}`。

    为什么必须是这条判据（而不是"正侧+负侧=盒"）：
    `负侧 := bb.cut(正侧)` ⇒ `正侧+负侧 ≡ 盒体积` **恒成立**，那条判据抓不到这里的
    任何缺陷（我先写的就是它，回退修复后照样绿 —— 典型假判据）。
    真正的缺陷是"**正侧少了一块**"：负侧随之多一块 ⇒ 交集漏出包围盒。

    真 bug（2026-09-24 实测，块 003 残留 +249%）：
    `_plane_halfspace` 用「底面过参考点、沿法向伸出、横向 4B」的厚板切包围盒，
    **两个尺寸都要够**，缺一个就会在盒的某个角落留缺口：
      · 横向半宽 2B ≥ 盒角到「过参考点沿法向的直线」的垂直距离（参考点 ∥ 法向时 = √3·B）。
        `P_1` 分支一直取最近点因而安全；`P_0` 分支原先取 `(D/A, 0, 0)`，A 只是小分量时
        该点严重偏离法向 ⇒ 缺口（块 003：+249%）。
      · 沿法向厚度需 ≥ `√3·B − n·p`。只伸出 2B 时要求 `n·p ≥ −0.268B`，
        块 003 的平面 `n·p = −462.8 < −333` ⇒ 仍有缺口（修横向后仍 +0.49%、`semi_infinite`）。
    修法：参考点投影成最近点（横向对齐）+ 厚度取 4B（任意与盒相交的平面都够）。

    实测效果（块 003 实体栅元，真值 8,667,390 cm³）：
    修复前 **30,253,932（+249%）** → 只修横向 8,709,578（+0.49%）→
    横向+厚度都修 **8,666,962（−0.0049%，状态 closed）**。
    """
    bad = []
    assert len(halfspace_probe) == 5, (
        f"探针应回 5 个平面，实得 {sorted(halfspace_probe)} —— "
        f"空/缺结果会让下面的循环空转、测试假绿")
    for name, v in halfspace_probe.items():
        if v["mismatch"]:
            sample = v["mismatch"][:3]
            bad.append(f"{name}: {len(v['mismatch'])}/{v['n']} 个采样点判定不一致，"
                       f"如 {sample}")
    assert not bad, ("半空间形状与解析半空间不符（正侧少一块 ⇒ 栅元漏出包围盒）：\n  "
                     + "\n  ".join(bad))


