# MCNP 输入卡生成器 — MCNP Input Card Generator

一款基于 **PyQt5** 的桌面应用程序，用于可视化地创建、编辑和校验 **MCNP**（Monte Carlo N-Particle）输入文件（`.INP`）。用结构化、表单化的 GUI 替代手工文本编辑。

A **PyQt5** desktop application for visually creating, editing, and validating **MCNP** input files (`.INP`). Replaces manual text editing with a structured, form-based GUI.

![应用截图](images/screenshot.png)

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey)
![MCNP](https://img.shields.io/badge/MCNP-6.x%20Compatible-orange)

---

## 解决痛点 Why This Tool Exists

MCNP 是核工程领域最权威的蒙卡程序之一，但它的输入卡编写方式停留在上世纪 80 年代——纯文本、固定格式、零容错。本项目专门针对以下痛点：

| 痛点 | 传统方式 | 本项目的方案 |
|------|---------|-------------|
| **格式敏感** | 每行严格 80 列，一个空格错位就 fatal error，调试全靠肉眼 | 表单化 GUI，自动格式化排版，不可能出现列对齐错误 |
| **CAD 几何转换门槛高** | 从 STEP 文件手动提取曲面方程再写成 MCNP 曲面卡，动辄几百行 | 集成 McCAD 转换引擎，一键导入 STEP 文件，自动生成曲面和栅元，含完整对话框配置 |
| **材料定义繁琐** | 翻手册查 ZAID 号、算原子分数、手动拼写 Mm 卡，容易写错截面库 ID | 50+ 种预设材料库 + 化学式自动换算 → ZAID 表格，支持 xsdir 校验 |
| **缺乏可视反馈** | 写完后跑 MCNP plotter 才能看到几何，错了回头改，循环极慢 | 双引擎 3D 预览：PyVista 快速预览 + FreeCAD CSG 精确渲染（支持 TR 变换/斜向圆柱） |
| **输出分析需额外工作** | 跑完 MCNP 后自己写脚本解析输出文件、提取计数、画图 | 内置输出解析器，自动提取 F1–F8 计数结果并绘图，支持 CSV/Parquet 导出 |
| **学习曲线陡峭** | MCNP 手册上千页，卡类型上百种，记不住参数顺序和默认值 | 每个字段都有 Tooltip 提示和格式化输入，参考文档（C810）一键查看 |
| **项目管理混乱** | 多个 INP 文件散落在文件夹里，改了什么版本完全靠文件名 | JSON 项目保存/加载，完整工作区随时恢复 |

---

## 功能特性 Features

| 功能 Feature | 说明 Description |
|-------------|-----------------|
| **表单化编辑 Form-based editing** | 8 个标签页覆盖所有 MCNP 输入段 / 8 organized tabs covering all MCNP input sections |
| **INP 生成 INP generation** | 自动生成标准 MCNP 输入文件，80 列格式排版 / Auto-generates standard MCNP input decks with 80-column formatting |
| **INP 导入 INP import** | 解析现有 `.INP` 文件，回填所有标签页字段 / Parse existing `.INP` files and backfill all tab fields |
| **STEP 导入 STEP import (McCAD)** | 集成 McCAD 引擎，含完整导入设置对话框（分解/转换/void参数） / Full McCAD integration with settings dialog |
| **项目保存/加载 Project save/load** | 以 JSON 格式保存和恢复完整工作区 / Save/restore complete workspace as JSON |
| **材料库 Material library** | 50+ 预设材料（化合物、元素、合金、屏蔽材料、组织、吸收体） / 50+ preset materials |
| **双模式源 Dual source mode** | 固定多源（概率权重）或分布源（SDEF + SI/SP） / Fixed multi-source or distribution source |
| **双模式材料输入 Dual material input** | 手动 ZAID 表格或化学式输入（通过 `pymcnp M_0.from_formula()`） / Manual ZAID table or chemical formula |
| **3D 预览 (PyVista + FreeCAD CSG)** | 双引擎渲染：PyVista 实时预览 + FreeCAD 精确 CSG（支持 TR 坐标变换、C/Y 等斜向圆柱） / Dual-engine 3D preview with full TR transform support |
| **栅元渲染控制 Cell render control** | 浮动控制窗口，逐栅元显隐切换、材料号编辑、悬停查看曲面信息 / Per-cell toggle, material editing, hover surface tooltip |
| **输出分析 Output analysis** | 解析 MCNP 输出文件，绘制计数结果（matplotlib），导出 CSV/Parquet / Parse output files, plot tallies, export |
| **xsdir 集成 xsdir integration** | 截面库 ZAID 校验与查找 / Cross-section library ZAID validation and lookup |
| **深色/浅色/粉色/传统主题 Themes** | 内置 4 套 QSS 主题切换 / 4 built-in QSS themes (Light/Dark/Pink/Traditional) |
| **MCNP 自动检测 MCNP auto-detect** | 自动查找已安装的 MCNP 可执行文件 / Automatically finds installed MCNP executable |

---

## 快速开始 Quick Start

### 环境要求 Prerequisites

- Python 3.10+
- MCNP（可选，用于运行生成的输入文件 / optional, for running generated input decks）

### 安装 Installation

```bash
# 克隆或下载 Clone or download
cd MCNP-Input-Card-Generator

# 安装依赖 Install dependencies
pip install -r requirements.txt

# 运行 Run
python main.py
```

### 3D 预览（FreeCAD CSG 引擎）

需要安装 FreeCAD（≥ 0.20），启动后在「几何」标签页点击 **"3D 预览"** 选择 FreeCAD 可执行文件路径。CSG 引擎支持：

- **TRn 坐标变换**：C/X, C/Y, C/Z, CX, CY, CZ 曲面带 TR 变换时精确渲染
- **布尔运算**：交/并/补操作正确求值
- **同色合并**：同材料相邻栅元自动合并为一个实体
- **逐栅元显隐控制**：支持透明度调节

### 打包为独立 EXE Build Standalone EXE

```bash
build.bat
```

打包后的可执行文件输出到 `dist/MCNP输入卡生成器/`。
The packaged executable will be output to `dist/MCNP输入卡生成器/`.

---

## 用户界面 User Interface

| 标签页 Tab | 章节 Section | 说明 Description |
|-----------|-------------|-----------------|
| 基础 Basic | Title, MODE, NPS, CTME | 文件标识与粒子输运参数 / Deck identification and transport parameters |
| 材料 Materials | 材料卡 Material cards | ZAID/份额输入，含预设材料库 / ZAID/fraction entries with preset library |
| 几何 Geometry | 曲面与栅元 Surfaces & Cells | 曲面定义、栅元表格、3D 预览、STEP 导入 / Surface definitions, cell table, 3D preview, STEP import |
| 源 Source | SDEF | 固定点源或分布源模式 / Fixed point sources or distribution source mode |
| 计数 Tallies | F1–F8 | 启用/禁用计数及参数 / Enable/disable tallies with parameters |
| 能量 Energy | E0, CUT 卡 | 能量网格与时间/能量截断 / Energy mesh and time/energy cutoffs |
| 高级 Advanced | PHYS, 其他 | 物理卡、辅助卡、xsdir 路径 / Physics cards, auxiliary cards, xsdir path |
| 输出 Output | 结果 Results | MCNP 输出解析、绘图、导出 / Output parsing, plotting, export |

---

## 项目结构 Project Structure

```
├── main.py                          # 入口文件 Application entry point
├── requirements.txt                 # 依赖 Dependencies
├── build.bat                        # PyInstaller 打包脚本 Build script
├── images/
│   └── screenshot.png               # 应用截图
├── app/
│   ├── __init__.py
│   ├── main_window.py               # 主窗口协调器 Main window orchestrator
│   ├── models.py                    # 数据模型 Data models (DeckData, CellData, etc.)
│   ├── style.py                     # QSS 样式表（4 套主题）QSS stylesheets (4 themes)
│   ├── project_io.py                # JSON 项目保存/加载 JSON project save/load
│   ├── inp_importer.py              # INP 文件导入器 INP file importer
│   ├── material_presets.py          # 预设材料库 Preset material library
│   ├── mcnp_detector.py             # MCNP 可执行文件自动检测 MCNP auto-detection
│   ├── xsdir_db.py                  # xsdir 截面数据库 xsdir cross-section database
│   ├── xsdir_manager.py             # xsdir 路径管理 xsdir path management
│   ├── freecad_preview.py           # FreeCAD 3D 预览主进程侧封装 FreeCAD preview orchestrator
│   ├── _freecad_csg_worker.py       # FreeCAD CSG 几何求值子进程（创建/变换/布尔运算）CSG worker subprocess
│   ├── step_importer.py             # STEP → MCNP (McCAD) 导入器，含完整设置对话框 McCAD STEP importer
│   ├── step_to_standard.py          # STEP 标准化转换 STEP standardization
│   ├── analyze_step.py              # STEP 结构分析 STEP structural analysis
│   ├── docs/
│   │   ├── MCNP6_曲面卡格式参考.md   # MCNP 曲面卡中文参考文档
│   │   └── C810_卡片格式详细.txt      # C810 手册摘录
│   ├── generator/                    # INP 生成与解析引擎
│   │   ├── __init__.py
│   │   ├── inp_generator.py          # 主生成器 Main generator (~800 lines)
│   │   ├── validator.py              # 文件校验 Deck validation
│   │   ├── inp_parser.py             # INP 语法解析 INP syntax parser
│   │   └── parsers/                  # INP 解析子包
│   │       ├── __init__.py
│   │       ├── core.py
│   │       ├── lines.py
│   │       ├── sections.py
│   │       └── validator.py
│   ├── tabs/                         # 8 个 UI 标签页
│   │   ├── __init__.py
│   │   ├── basic_settings_tab.py
│   │   ├── geometry_tab.py
│   │   ├── material_tab.py
│   │   ├── sdef_tab.py
│   │   ├── tally_tab.py
│   │   ├── energy_tab.py
│   │   ├── advanced_tab.py
│   │   └── output_tab.py
│   ├── dialogs/                      # 模态编辑对话框
│   │   ├── __init__.py
│   │   ├── cell_edit_dialog.py
│   │   ├── source_edit_dialog.py
│   │   ├── material_edit_dialog.py
│   │   └── preview_dialog.py
│   └── widgets/                      # 可复用组件
│           ├── __init__.py
│           ├── render_ctrl.py        # 栅元渲染控制浮动窗口（含悬停曲面信息） Floating render control
│           ├── opacity_ctrl.py       # 透明度滑块控制 Opacity slider control
│           ├── coord_aids.py         # 坐标辅助工具 Coordinate aids
│           ├── stat_card.py          # 统计卡片 Stat card widget
│           └── text_mode_section.py  # 文本模式切换 Text mode toggle section
```

---

## 引擎说明 Engine Notes

### STEP 导入（McCAD）

McCAD 是韩国首尔大学（SNU）开发的 STEP→MCNP 转换器（开源，使用 OpenCascade 内核）。

使用方式：
1. 「几何」标签页 → 「导入 STEP」按钮
2. 在弹出的 McCAD 设置对话框中配置分解/转换/void 参数
3. McCAD 自动运行并解析生成的 MCFile.i，回填曲面卡和栅元卡

McCAD 二进制默认路径：`D:\McCAD_build\src\McCAD\Release\McCAD.exe`

### 3D 预览（FreeCAD CSG）

从 PyVista 快速预览升级为 FreeCAD 精确 CSG 求值引擎，处理方式：

- 以 JSON AST 序列化 pymcnp 几何树，发送给 FreeCAD 子进程
- 子进程用 `Part.Shape` 布尔运算（cut, common, fuse）逐个求值
- 输出 STL 三角网格返主进程渲染

支持的 MCNP 曲面类型：P, PX/PY/PZ, S/SO/SX/SY/SZ, C/X/C/Y/C/Z, CX/CY/CZ, K/X/K/Y/K/Z, KX/KY/KZ, SQ, GQ, RPP, RCC, SPH, BOX, TRC, REC, WED, ARB 等

坐标变换（TRn）：正确支持任意角度旋转/平移的圆柱、圆锥、平面等曲面。

---

## 引用与致谢 Acknowledgements

本项目引用了以下开源软件，谨此致谢：

| 项目 | 用途 | 许可证 |
|------|------|--------|
| [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) | 图形界面框架 | GPL v3 |
| [PyMCNP](https://github.com/FSIBT/PyMCNP) | MCNP 核心库（几何、生成、解析） | BSD-3-Clause |
| [PyVista](https://github.com/pyvista/pyvista) | 3D 可视化 | MIT |
| [matplotlib](https://matplotlib.org/) | 数据绘图 | PSF 风格 |
| [McCAD](https://github.com/snukc1325/McCAD) | STEP → MCNP 几何转换引擎 | AGPL-3.0 |
| [FreeCAD](https://www.freecad.org/) | 3D CAD 几何处理（CSG 求值引擎） | LGPL v2+ |
| [OpenCascade](https://dev.opencascade.org/) | CAD 内核（McCAD + FreeCAD 共用） | LGPL v2.1 |
| [VTK](https://vtk.org/) | 3D 渲染与可视化管线 | BSD-3-Clause |
| [NumPy](https://numpy.org/) | 科学计算 | BSD-3-Clause |
| [SciPy](https://scipy.org/) | 科学计算 | BSD-3-Clause |

McCAD 由 Seoul National University（韩国首尔大学）Nuclear Engineering 团队开发，许可证为 AGPL-3.0。
FreeCAD 基于 OpenCascade 内核，本项目通过子进程调用其 Python API 进行 CSG 几何求值。

---

## 许可协议 License

**All Rights Reserved.** 版权所有 © 2026 魏祎卓

- ✅ 允许个人及机构内部**免费使用**
- ✅ 允许为自用或内部使用**修改代码**
- ❌ **严禁任何形式的盈利活动**（销售、付费服务、商业嵌入等）
- ❌ 修改后公开发布须**经作者书面许可**

如需授权请联系：1378963177@qq.com

---

> 本项目由 AI 辅助编程完成 / Built with AI assistance (Claude).

Built with [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) and [pymcnp](https://pypi.org/project/pymcnp/).
