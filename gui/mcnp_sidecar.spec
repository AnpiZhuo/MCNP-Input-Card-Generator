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
    "models.py", "preview_cache.py", "freecad_preview.py", "_freecad_csg_worker.py",
    "quadric.py", "voxel_csg.py", "mc.py", "analytic_slice.py",
    "mctal_parser.py", "sweep.py",
    "overlap_classify.py", "spatial_index.py", "overlap_probe.py",
    "freecad_locator.py", "step_importer_geouned.py", "geouned_worker.py",
    "xsdir_db.py", "step_importer.py",
    "outp_parser.py",
    "coverage_check.py",
    # 注意：_cross_section_helper.py 在 gui/backend/（不在 app/），见下方 GUI_BACKEND 段
    "_freecad_cross_section_worker.py",
    "stl_cross_section.py", "gpu_pref.py",
    "material_library.py",
    "lattice.py", "diff_inp.py",  # _import_app() 动态导入 → 需显式保留
    "mcnp_tasks.py",              # tasks N 解析（纯 stdlib；_import_app 动态导入 → 必须登记，勿重蹈 TD-02）
    "mcnp_locator.py",            # MCNP 版本检测/选择（_import_app 动态导入 → 必须登记）
    "user_config.py",             # config.json 唯一读写口（被 mcnp_locator 顶层 import；它同时是
                                  # _keep_py 的**数据**文件而非 PYZ 模块 ⇒ PyInstaller 静态分析
                                  # 看不到这条边，漏登记则冻结版 mcnp_locator 必 ImportError）
    "file_dialog.py",             # 原生文件选择窗口规格（kind → 标题/类型；keff 解析卡用）
    "adaptive_decompose.py",      # 实体预分解（父侧）
    "adaptive_cut_freecad.py",    # 实体预分解（**子进程**执行体，由 FreeCAD python 跑）
                                  # 两者都是 geouned_worker 在 FreeCAD python 里的
                                  # `import` / 子进程目标 —— 松散数据文件之间的引用，
                                  # PyInstaller 静态分析看不到 ⇒ 漏登记则冻结版必失败，勿重蹈 TD-02
]
_keep_dirs = ["generator", "docs", "meshtal", "ptrac"]  # generator（含 parsers）+ 参考文档 + meshtal 网格计数 + ptrac 粒子径迹模块

_datas = []
for f in _keep_py:
    sp = os.path.join(APP_SRC, f)
    if os.path.isfile(sp):
        _datas.append((sp, "app"))

# gui/backend 里 api_server 运行时要 import 的辅助模块（通过 app 目录路径找到）
for f in ["_cross_section_helper.py"]:
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

# ── 外部可执行文件：**目前一个都没有** ──
# 实体预分解改由 FreeCAD 自带的 python.exe 直接做（`adaptive_cut_freecad.py`），
# 所以不再随包分发任何 exe。下面这条历史教训留在这里，别让后人再踩：
#
# 若将来又要随包带一个 exe：**不要放进 `Analysis(datas=...)`**。PyInstaller 会对它做
# "binary vs. data reclassification"，顺着导入表把 FreeCAD 的 49 个 OCC/MSVC DLL
# （TKernel.dll / FreeCAD.dll 系 + MSVCP140 …，约 46 MB）也收进包，落在 `_internal\`
# 根目录 —— 而那个 exe 在子目录里，**DLL 搜索顺序不含上级目录，它照样找不到**。
# 正确做法是在 Analysis 之后 `a.datas += [(目标名, 源路径, "DATA")]` 晚注入（3 元组、
# 顺序与 `Analysis(datas=)` 的 2 元组相反；直接 += 2 元组会 ValueError:
# not enough values to unpack (expected 3, got 2)）。

# 排除 pymcnp._show*（渲染层，不拉 pyvista/vtk）
_hidden = [m for m in collect_submodules("pymcnp") if not m.startswith("pymcnp._show")]

# meshtal 网格计数模块（app/meshtal 8 模块 + __init__）进 PYZ：冻结 exe 内
# mcnp_bridge --meshtal-worker 分派与 worker 内部 `from meshtal.xxx import` 都从
# PYZ 可 import（_keep_dirs data 保留供核对/旁路）。worker 保持模块顶只 stdlib。
_meshtal_mods = [
    "meshtal", "meshtal.meshtal_parser", "meshtal.volume_builder",
    "meshtal.colormap", "meshtal.downsample_plan", "meshtal.meshtal_cache",
    "meshtal.deck_match", "meshtal.fmesh_parser", "meshtal._meshtal_worker",
]
_hidden += _meshtal_mods

# ptrac 粒子径迹模块（app/ptrac 2 模块 + __init__）进 PYZ：照 meshtal，
# mcnp_bridge --ptrac-worker 分派与 worker 内部 `from ptrac.xxx import` 都从
# PYZ 可 import。parser/worker 模块顶只 stdlib。
_ptrac_mods = [
    "ptrac", "ptrac.ptrac_parser", "ptrac._ptrac_worker",
]
_hidden += _ptrac_mods

# inputcard-mcp（AI 接入）：mcnp_bridge --mcp-server / --mcp-http 分派时 import inputcard_mcp.server
# （顶层 import mcp.server.fastmcp）。其 __mcp_http_main 还需 uvicorn/starlette（FastMCP stdio 路径
# 不 import 它们，故须显式打进 PYZ；主程序 api_server 路径不触碰，不影响 5001 后端启动）。
_hidden += ["inputcard_mcp", "inputcard_mcp.server", "uvicorn", "starlette"]

# ── 关于随包 exe 的教训见上方注释（当前没有随包 exe，故无晚注入步骤）──

a = Analysis(
    [os.path.join(GUI_BACKEND, "mcnp_bridge.py")],
    pathex=[APP_SRC, GUI_BACKEND, PROJECT],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pyvista", "pyvistaqt", "vtk", "vtkmodules", "PyQt5"],
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

# ── 产物落点：**必须用命令行 `--distpath dist_sidecar` 指定为独立目录** ──
# 为什么不用默认的 `dist/python`：`vite build` 会**清空 `gui/dist/`**，
# 于是"先 PyInstaller → 再 npm run build:app"会把刚打好的 sidecar 删掉，
# 同步脚本随后把 binaries/ 里**上一次的旧 python.exe** 铺进 target/release，
# 还报"✅ 已是最新" ⇒ 打出"版本号新、后端旧"的包（冒烟才发现修复不生效，坑 6.7）。
# 两者物理分开后互不干扰，构建顺序不再有隐藏依赖。
#
# ⚠️ 为什么不在这里写 `coll.distpath = ...`：COLLECT 对象没有这个属性，
# 赋值会被**静默忽略**（实测：照样写进 dist/）。落点只能用命令行参数，
# 因此统一走 `npm run build:sidecar`（脚本里带 --distpath），不要手敲裸 PyInstaller。
