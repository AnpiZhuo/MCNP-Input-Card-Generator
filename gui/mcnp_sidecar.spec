# -*- mode: python ; coding: utf-8 -*-
"""打包 Python 后端为 Tauri sidecar exe（mcnp_bridge → api_server 常驻 5001）

- 只打包后端需要的 app 模块（排除 Qt 死代码）
- GEOUNED 纯 Python 包打包到独立子目录 vendor/（运行时由 FreeCAD python
  加载，避免 worker 用本程序 numpy 顶掉 FreeCAD 的 numpy）
产出: python.exe → 重命名为 python-x86_64-pc-windows-msvc.exe 放入 src-tauri/binaries/
"""
import os
from PyInstaller.utils.hooks import collect_submodules

PROJECT = os.path.abspath(os.path.join(os.getcwd(), ".."))
APP_SRC = os.path.join(PROJECT, "app")
GUI_BACKEND = os.path.join(PROJECT, "gui", "backend")

# ── 只保留后端需要的 app 顶层 .py（排除 Qt 死代码）──
_keep_py = [
    "models.py", "freecad_preview.py", "_freecad_csg_worker.py",
    "freecad_locator.py", "step_importer_geouned.py", "geouned_worker.py",
    "xsdir_db.py", "step_importer.py",
    "_cross_section_helper.py",
    "_freecad_cross_section_worker.py",
    "stl_cross_section.py",
]
_keep_dirs = ["generator", "docs"]  # generator（含 parsers）+ 参考文档

_datas = []
for f in _keep_py:
    sp = os.path.join(APP_SRC, f)
    if os.path.isfile(sp):
        _datas.append((sp, "app"))

# gui/backend 里 api_server 运行时要 import 的辅助模块（通过 app 目录路径找到）
for f in ["_cross_section_helper.py", "generate_step.py"]:
    sp = os.path.join(GUI_BACKEND, f)
    if os.path.isfile(sp):
        _datas.append((sp, "app"))

def _walk_add(base, rel):
    p = os.path.join(base, rel)
    for name in os.listdir(p):
        sp = os.path.join(p, name)
        rp = rel + "/" + name if rel else name
        if os.path.isdir(sp):
            _walk_add(base, rp)
        elif name.endswith(".py") or name.lower().endswith((".md", ".txt")):
            _datas.append((sp, "app/" + os.path.dirname(rp) if os.path.dirname(rp) else "app"))

for d in _keep_dirs:
    _walk_add(APP_SRC, d)

# ── GEOUNED 打包（随程序分发，运行时由 FreeCAD python 加载）──
# 必须落在独立子目录 vendor/，避免 worker 用本程序 numpy 顶掉 FreeCAD 的 numpy。
_binaries = []
GEOUNED_SRC = r"D:\MCNP\GEOUNED"
if os.path.isdir(os.path.join(GEOUNED_SRC, "geouned")):
    _datas.append((GEOUNED_SRC, "vendor"))

# 排除 pymcnp._show*（渲染层，不拉 pyvista/vtk）
_hidden = [m for m in collect_submodules("pymcnp") if not m.startswith("pymcnp._show")]

a = Analysis(
    [os.path.join(GUI_BACKEND, "mcnp_bridge.py")],
    pathex=[APP_SRC, GUI_BACKEND, PROJECT],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pyvista", "pyvistaqt", "vtk", "vtkmodules"],
    noarchive=False,
)
pyz = PYZ(a.pure)
# onedir：python.exe(小) + _internal/（一次展开、启动秒级）
# 不用 onefile：163MB 每次启动自解压 + Defender 扫描 → 后端 60s+ 才起来
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="python",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="python",
)
