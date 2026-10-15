"""
build_cells_data cell 分类规则测试（项14，2026-08-24 用户反馈修复）。

纪律：本文件【不 import】gui.backend.api_server（模块级 pyvista/FreeCAD 探测污染，
见 conftest.py 铁律）。build_cells_data 在**子进程**内 import 并执行（照
test_api_contract.py 范式），测试只收 JSON 结果，不依赖 FreeCAD。

验证项（2026-08-24 用户确认；2026-10-11 按用户指示收敛 graveyard 口径）：
  1. 单值 fill=U 的 cell 不产自身 STL（preview-3d 核心回归，修复「大紫方块」）
  2. fill_grid 格阵 cell 不产自身 STL
  3. 纯 void（material=0、无 fill 无 u）产 STL（项14「删 void 约束」）
  4. 普通实体 cell（material≠0、无 fill 无 u）产 STL（不回退）
  5. render:false 仍 skip
  6. **imp（含 imp:n=0 / imp:p=0）不再决定渲染**（2026-10-11 删旧 graveyard 判据）
  7. 边界：fill="0" 的 void-fill 也是 fill cell → skip
  8. **注释含 graveyard 不再决定渲染**（导入边界已无 GEOUNED 墓区）
  9. mode n 卡（全员 imp:p=0）不得被判墓地 → 全栅元参与 STL（用户 s.i 的回归）
  10. include_void=False（STEP 导出路径）纯 void 仍 skip，不回退
  11. CellRow 判别联合格式（kind=cell 嵌套 camelCase）同样生效
  12. 有 u 无 fill 的实体 cell（universe 定义）仍产 STL
  13. force_include_numbers 仍能放行 include_void=False 会跳过的真空栅元
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

# 13. imp / comment **不得**决定渲染与否（2026-10-11，用户指出 graveyard 判据越权）。
#     mode n 的卡习惯给每个栅元写 imp:p=0 ⇒ 旧口径「任一为 0 ⇒ 墓地」整张卡全灭
#     （用户卡 s.i 实测 35/35，后端回「没有可预览的栅元」、预览全空）。
out["imp_p_zero_all_cells"] = nums([
    cell(number=1, surface_expr="-1", material="1", impN="1", impP="0"),
    cell(number=2, surface_expr="-2", material="1", impN="1", impP="0"),
    cell(number=3, surface_expr="-3", material="0", impN="0", impP="0"),
])

# 14. force_include_numbers：强制包含外部栅元（水密检测，include_void=False 也不跳过）
#     对照组不加 force：真空栅元被 include_void=False 跳过 ⇒ 只 [2]。
out["force_include"] = [
    c["number"] for c in build_cells_data(
        [cell(number=1, surface_expr="-1", material="0"),
         cell(number=2, surface_expr="-2")],
        include_void=False, force_include_numbers={1})
]
out["force_include_control"] = [
    c["number"] for c in build_cells_data(
        [cell(number=1, surface_expr="-1", material="0"),
         cell(number=2, surface_expr="-2")],
        include_void=False)
]

# 15. GEOUNED 的墓区栅元必须不渲染（2026-09-24 用户："3D 预览还是一坨"）
#     GEOUNED 生成的 deck **带 imp**，但 `flat_cell_json` 原先不输出 `imp_*`
#     ⇒ 只认 imp=0 的判据在 STEP 路径上取不到值 ⇒ 恒不成立，
#     ⇒ 半径 1049 的球外（体积 = 模型 7372%、bbox 2927³）被渲染进预览、把模型整个包住。
#     GEOUNED 的官方标记是注释：void.py:201/208 写死 "Graveyard_in"/"Graveyard"。
out["graveyard_comment"] = nums([
    cell(number=1, surface_expr="-1",
         comment="/Open CASCADE STEP translator 7.8 11"),
    cell(number=46, surface_expr="-277 (-262:270:-263:268:-265:266)",
         material="0", comment="Graveyard_in"),
    cell(number=47, surface_expr="277", material="0", comment="Graveyard"),
    cell(number=48, surface_expr="-3", material="0", comment="graveyard"),   # 大小写
    cell(number=49, surface_expr="-4", material="0", comment="graveyard outer sphere"),
])
# imp=0 那条原有规则不许被改坏（即使注释是普通文本）
out["graveyard_imp"] = nums([
    cell(number=1, surface_expr="-1", impN="0", comment="normal cell"),
    cell(number=2, surface_expr="-2", comment="normal cell"),
])

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


def test_imp_zero_no_longer_gates_rendering(classify_results):
    """imp:n=0 不再决定渲染（材料非真空就渲染 —— 2026-10-11 用户指示）。

    imp 是**输运**语义（MCNP 在该栅元杀粒子），不是**可视**语义；旧的 graveyard 判据
    把两者混用，已删。
    """
    assert classify_results["graveyard"] == [1, 2]


def test_fill_zero_is_fill_cell(classify_results):
    """fill="0" 的 void-fill 也是 fill cell → skip（用户规则：与 material 无关）。"""
    assert classify_results["fill_zero"] == [2]


def test_any_particle_imp_zero_no_longer_gates_rendering(classify_results):
    """`imp_p=0` 同样不再算墓地。

    mode n 的卡习惯给**每个**栅元写 `imp:p=0`（该粒子本就不输运）—— 旧的「任一粒子
    重要性 0 ⇒ 墓地」会让整张卡一个栅元都不渲染（用户 s.i 实测：预览全空）。
    """
    assert classify_results["graveyard_impP"] == [1, 2]


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


def test_imp_does_not_gate_rendering(classify_results):
    """imp 是**输运**语义（杀粒子），不得当**可视**语义用。

    mode n 的卡习惯给每个栅元写 `imp:p=0`（该粒子本就不输运）—— 旧的「任一为 0 ⇒ 墓地」
    会让整张卡一个栅元都不渲染（用户 s.i 实测：35/35 全灭、预览全空）。
    """
    assert classify_results["imp_p_zero_all_cells"] == [1, 2, 3]


def test_force_include_still_honored(classify_results):
    """force_include_numbers 仍能放行 include_void=False 会跳过的真空栅元（水密检测用）。"""
    assert sorted(classify_results["force_include"]) == [1, 2]
    assert classify_results["force_include_control"] == [2], "对照组：不加 force 时真空被跳过"


# ══════════════════════════════════════════════════════════════════════
# imp / 注释 **都不再**决定渲染（2026-10-11，用户：「geouned 导出的墓地怎么能和实际
# 定义的墓地混为一谈？……程序端的栅元，只要材料不是真空都应该渲染」）
#
# GEOUNED 墓区已在导入边界消失（voidGen=False：同一份 STEP 9→6 栅元），所以注释判据
# 只剩误伤；当年加判据的真实动因（巨型外壳撑开取景）已在取景侧修（src/three/frameBox.ts）。
# ══════════════════════════════════════════════════════════════════════

def test_geouned_graveyard_comment_cells_are_rendered(classify_results):
    """注释含 graveyard 不再影响渲染：GEOUNED 墓区已在导入边界消失，注释判据只会误伤。"""
    kept = classify_results["graveyard_comment"]
    assert kept == [1, 46, 47, 48, 49], (
        "注释不得决定渲染；普通注释与 GEOUNED 标记一视同仁")


def test_imp_zero_with_normal_comment_still_rendered(classify_results):
    """imp=0 + 普通注释：仍渲染（防"判据以注释为名复活"）。"""
    assert classify_results["graveyard_imp"] == [1, 2]
