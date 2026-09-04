"""复现：17×17 格阵卡 3D 预览重合检测乱报错。

模拟前端 Preview3D.runOverlapCheck 请求（cells 只带 number/material/density/
surface_expr，**丢掉 u/fill/lat/fill_grid**），走 /api/check-overlap 的完整逻辑：
    cell_list = [c for c in cells if not _cell_u_of(c)]  ← 因无 u，全部保留
    → _lattice_pin_fit_overlaps
    → build_cells_data → FreeCADEngine.build_geometry(check_overlaps=True)
"""
import sys, json, os
sys.path.insert(0, r"D:\MCNP\输入卡生成器源码")
sys.path.insert(0, r"D:\MCNP\输入卡生成器源码\app")
sys.path.insert(0, r"D:\MCNP\输入卡生成器源码\gui\backend")
from pathlib import Path

FIX_PATH = os.environ.get("FIX", r"D:\MCNP\输入卡生成器源码\tests\fixtures\owen\assembly_17x17_mcnp.i")
FIX = Path(FIX_PATH).read_text(encoding="utf-8", errors="replace")
print("=== fixture:", Path(FIX_PATH).name, "===")

# ---- 解析出 surfaces 文本 / tr 文本 / cells ----
from app.generator.parsers import parse_inp_text
deck, warn = parse_inp_text(FIX)
surf_text = deck.surfaces
tr_text = deck.tr_cards if hasattr(deck, "tr_cards") else ""
print("=== surface cards ===")
print(surf_text)
print("=== tr cards ===")
print(tr_text)

# ---- 前端式 cells ----
# PASS_FULL=True 模拟修复后请求（传 u/fill/lat/fill_grid/trcl/render，如同 preview-lattice）。
import os
PASS_FULL = os.environ.get("PASS_FULL", "1") == "1"
fe_cells = []
for c in deck.cells:
    if c.kind == "raw":
        continue
    cell = c.cell
    d = {
        "number": cell.number,
        "material": cell.material,
        "density": cell.density,
        "surface_expr": cell.surface_expr,
    }
    if PASS_FULL:
        d.update({
            "u": cell.u or "",
            "fill": cell.fill or "",
            "lat": cell.lat or "",
            "trcl": cell.trcl or "",
            "render": True,
            "fill_grid": cell.fill_grid or "",
            "imp_n": getattr(cell, "imp_n", "") or "",
            "imp_p": getattr(cell, "imp_p", "") or "",
            "imp_e": getattr(cell, "imp_e", "") or "",
        })
    fe_cells.append({"kind": "cell", "cell": d})
print(f"PASS_FULL={PASS_FULL}")

# ---- check-overlap 逻辑（源码逐行） ----
import importlib
from api_server import _cell_u_of, _lattice_pin_fit_overlaps, build_cells_data, parse_surfaces, parse_tr_cards, _PREVIEW_CACHE

cell_list = [c for c in fe_cells if not _cell_u_of(c)]
print(f"\n=== cell_list 长度（排除 u 后）: {len(cell_list)} / {len(fe_cells)} ===")
for c in cell_list:
    print("  keep:", c["cell"]["number"])

import app.lattice as lattice
fit = _lattice_pin_fit_overlaps(fe_cells, surf_text, lattice)
print(f"\n=== lattice-fit 结果（{len(fit)} 条）===")
for f in fit:
    print(" ", f)

cells_data = build_cells_data(cell_list, include_void=True)
print(f"\n=== build_cells_data 产出 {len(cells_data)} 个栅元 ===")
for cd in cells_data:
    print("  ", cd["number"], "mat=", cd["material"], "ast=", cd["ast"] is not None)

# ---- FreeCAD 布尔 / 探针 ----
from step_importer import StepImporter
from freecad_preview import FreeCADEngine
fc_bin = StepImporter.detect_freecad()
print(f"\nFreeCAD: {fc_bin}")
if not fc_bin:
    print("无 FreeCAD，跳过布尔检测")
    sys.exit(0)
surfs = parse_surfaces(surf_text)
tr_cards = parse_tr_cards(tr_text)
engine = FreeCADEngine(fc_bin)
engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl", check_overlaps=True)
engine.cleanup()
print(f"\n=== FreeCAD overlaps（{len(engine.overlaps)} 条）===")
for o in engine.overlaps:
    print("  ", o)
print(f"\n=== unresolved（{len(engine.overlap_unresolved)} 条）===")
for u in engine.overlap_unresolved:
    print("  ", u)
