"""
build_cells_data cell 分类规则测试（项14，2026-08-24 用户反馈修复）。

纪律：本文件【不 import】gui.backend.api_server（模块级 pyvista/FreeCAD 探测污染，
见 conftest.py 铁律）。build_cells_data 在**子进程**内 import 并执行（照
test_api_contract.py 范式），测试只收 JSON 结果，不依赖 FreeCAD。

验证项（用户已确认权威规则）：
  1. 单值 fill=U 的 cell 不产自身 STL（preview-3d 核心回归，修复「大紫方块」）
  2. fill_grid 格阵 cell 不产自身 STL
  3. 纯 void（material=0、无 fill 无 u）产 STL（项14「删 void 约束」）
  4. 普通实体 cell（material≠0、无 fill 无 u）产 STL（不回退）
  5. render:false 仍 skip
  6. graveyard（imp=0）不渲染
  7. 边界：fill="0" 的 void-fill 也是 fill cell → skip
  8. 边界：imp_p=0（光子重要性 0）同样算 graveyard
  9. 边界：imp="1"（非 0）不误判 graveyard
  10. include_void=False（STEP 导出路径）纯 void 仍 skip，不回退
  11. CellRow 判别联合格式（kind=cell 嵌套 camelCase）同样生效
  12. 有 u 无 fill 的实体 cell（universe 定义）仍产 STL
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
API_DIR = PROJECT_DIR / "gui" / "backend"
APP_DIR = PROJECT_DIR / "app"

_SNIPPET = '''
import sys, json
sys.path.insert(0, "@API_DIR@")
sys.path.insert(0, "@APP_DIR@")
from api_server import build_cells_data

def cell(**kw):
    base = dict(number=1, material="1", density="", surface_expr="-1",
                render=True, fill="", fill_grid="", u="", impN="", impP="", impE="")
    base.update(kw)
    return base

def nums(cells, include_void=True):
    return [c["number"] for c in build_cells_data(cells, include_void=include_void)]

out = {}

# 1. 单值 fill=U 的 cell 不产自身 STL（preview-3d）
out["fill_single"] = nums([
    cell(number=1, surface_expr="-1", material="1", fill="10"),
    cell(number=2, surface_expr="-2", material="1"),
])

# 2. fill_grid 格阵 cell 不产自身 STL
out["fill_grid"] = nums([
    cell(number=1, surface_expr="-1", fill_grid='{"dims":[2,2,1],"cells":[1,1,1,1]}'),
    cell(number=2, surface_expr="-2"),
])

# 3. 纯 void（material=0、无 fill 无 u）产 STL（项14 核心回归）
out["void_pure"] = nums([
    cell(number=1, surface_expr="-1", material="0"),
])

# 4. 普通实体 cell（material≠0、无 fill 无 u）产 STL
out["entity_normal"] = nums([
    cell(number=1, surface_expr="-1", material="1"),
])

# 5. render:false 仍 skip
out["render_false"] = nums([
    cell(number=1, surface_expr="-1", render=False),
    cell(number=2, surface_expr="-2"),
])

# 6. graveyard imp=0 不渲染
out["graveyard"] = nums([
    cell(number=1, surface_expr="-1", impN="0"),
    cell(number=2, surface_expr="-2"),
])

# 7. fill="0" 的 void-fill 也是 fill cell → skip
out["fill_zero"] = nums([
    cell(number=1, surface_expr="-1", material="0", fill="0"),
    cell(number=2, surface_expr="-2"),
])

# 8. imp_p=0（光子重要性 0）同样算 graveyard
out["graveyard_impP"] = nums([
    cell(number=1, surface_expr="-1", impN="1", impP="0"),
    cell(number=2, surface_expr="-2"),
])

# 9. imp="1"（非 0）不误判 graveyard
out["imp_nonzero"] = nums([
    cell(number=1, surface_expr="-1", impN="1"),
    cell(number=2, surface_expr="-2"),
])

# 10. include_void=False（STEP 导出路径）纯 void 仍 skip
out["void_step"] = nums([
    cell(number=1, surface_expr="-1", material="0"),
], include_void=False)

# 11. CellRow 判别联合格式（kind=cell 嵌套 camelCase）
out["cellrow_format"] = nums([
    {"kind": "cell", "cell": dict(num="1", mat="1", surfaces="-1", render=True,
                                  fill="3", fill_grid="", u="", impN="")},
    {"kind": "cell", "cell": dict(num="2", mat="1", surfaces="-2", render=True,
                                  fill="", fill_grid="", u="", impN="")},
])

# 12. 有 u 无 fill 的实体 cell（universe 定义）仍产 STL
out["universe_entity"] = nums([
    cell(number=1, surface_expr="-1", u="10"),
])

# 13. 项15：handler 构造 sub_by_u 时过滤 graveyard（_imp_any_zero 口径与 build 一致）
from api_server import _imp_any_zero
out["imp_any_zero"] = [
    _imp_any_zero({"imp_n": "0"}),                 # imp_n=0 → True
    _imp_any_zero({"impN": "0"}),                  # camelCase impN=0 → True
    _imp_any_zero({"imp_p": "0", "imp_n": "1"}),   # 任一粒子 0 → True
    _imp_any_zero({"imp_n": "1"}),                 # 非 0 → False
    _imp_any_zero({}),                             # 无 imp → False
]

# 14. force_include_numbers：强制包含外部栅元（水密检测，imp=0 也不跳过）
out["force_include"] = [
    c["number"] for c in build_cells_data(
        [cell(number=1, surface_expr="-1", material="0", impN="0"),
         cell(number=2, surface_expr="-2")],
        include_void=True, force_include_numbers={1})
]

print("RESULT=" + json.dumps(out, ensure_ascii=False))
'''


@pytest.fixture(scope="module")
def classify_results() -> dict:
    """子进程跑 build_cells_data 全场景 → {scenario: cell_numbers}。"""
    # as_posix() 正斜杠，避免 Windows 绝对路径反斜杠被 -c 源码转义破坏（\M/\输）
    snippet = (_SNIPPET.replace("@API_DIR@", API_DIR.as_posix())
                      .replace("@APP_DIR@", APP_DIR.as_posix()))
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"build_cells_data 子进程失败 rc={proc.returncode}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )
    marker = "RESULT="
    line = next((l for l in proc.stdout.splitlines() if l.startswith(marker)), None)
    assert line is not None, f"子进程未输出 RESULT 行\nstdout={proc.stdout}\nstderr={proc.stderr}"
    return json.loads(line[len(marker):])


def test_fill_single_skips_own_stl(classify_results):
    """单值 fill=U 的 cell 不产自身 STL（项14 核心修复：删 void 约束后 fill cell
    不再当实体块渲染）。"""
    assert classify_results["fill_single"] == [2]


def test_fill_grid_skips_own_stl(classify_results):
    """fill_grid 格阵 cell 不产自身 STL（既有规则，保持）。"""
    assert classify_results["fill_grid"] == [2]


def test_pure_void_produces_stl(classify_results):
    """纯 void（material=0、无 fill 无 u）产 STL（项14「删 void 约束」核心回归）。"""
    assert classify_results["void_pure"] == [1]


def test_entity_cell_produces_stl(classify_results):
    """普通实体 cell（material≠0、无 fill 无 u）产 STL（不回退）。"""
    assert classify_results["entity_normal"] == [1]


def test_render_false_still_skipped(classify_results):
    """render:false → 仍 skip（既有规则，保持）。"""
    assert classify_results["render_false"] == [2]


def test_graveyard_imp_zero_not_rendered(classify_results):
    """graveyard（imp=0）→ 不渲染。"""
    assert classify_results["graveyard"] == [2]


def test_fill_zero_is_fill_cell(classify_results):
    """fill="0" 的 void-fill 也是 fill cell → skip（用户规则：与 material 无关）。"""
    assert classify_results["fill_zero"] == [2]


def test_graveyard_any_particle_imp_zero(classify_results):
    """imp_p=0（任一粒子重要性 0）同样算 graveyard。"""
    assert classify_results["graveyard_impP"] == [2]


def test_imp_nonzero_not_graveyard(classify_results):
    """imp="1"（非 0）不误判 graveyard。"""
    assert classify_results["imp_nonzero"] == [1, 2]


def test_step_export_void_still_skipped(classify_results):
    """include_void=False（STEP 导出路径）纯 void 仍 skip，项14 边界保持。"""
    assert classify_results["void_step"] == []


def test_cellrow_discriminated_union_format(classify_results):
    """CellRow 判别联合格式（kind=cell 嵌套 camelCase）分类同样生效。"""
    assert classify_results["cellrow_format"] == [2]


def test_universe_entity_still_produces_stl(classify_results):
    """有 u 无 fill 的实体 cell（universe 定义 cell）仍产 STL。"""
    assert classify_results["universe_entity"] == [1]


def test_imp_any_zero_graveyard_filter(classify_results):
    """项15：handler 构造 sub_by_u 的 graveyard 过滤（_imp_any_zero）与 build_cells_data 口径一致。"""
    assert classify_results["imp_any_zero"] == [True, True, True, False, False]


def test_force_include_graveyard_retained(classify_results):
    """水密检测 force_include_numbers：graveyard（imp=0）在内的第一栅元被强制包含。"""
    assert sorted(classify_results["force_include"]) == [1, 2]
