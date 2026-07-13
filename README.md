# MCNP 输入卡生成器 — MCNP Input Card Generator

一款基于 **PyQt5** 的桌面应用程序，用于可视化地创建、编辑和校验 **MCNP**（Monte Carlo N-Particle）输入文件（`.INP`）。用结构化、表单化的 GUI 替代手工文本编辑。

A **PyQt5** desktop application for visually creating, editing, and validating **MCNP** input files (`.INP`). Replaces manual text editing with a structured, form-based GUI.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)

---

## 功能特性 Features

| 功能 Feature | 说明 Description |
|-------------|-----------------|
| **表单化编辑 Form-based editing** | 8 个标签页覆盖所有 MCNP 输入段 / 8 organized tabs covering all MCNP input sections |
| **INP 生成 INP generation** | 自动生成标准 MCNP 输入文件，80 列格式排版 / Auto-generates standard MCNP input decks with 80-column formatting |
| **INP 导入 INP import** | 解析现有 `.INP` 文件，回填所有标签页字段 / Parse existing `.INP` files and backfill all tab fields |
| **项目保存/加载 Project save/load** | 以 JSON 格式保存和恢复完整工作区 / Save/restore complete workspace as JSON |
| **材料库 Material library** | 50+ 预设材料（化合物、元素、合金、屏蔽材料、组织、吸收体） / 50+ preset materials |
| **双模式源 Dual source mode** | 固定多源（概率权重）或分布源（SDEF + SI/SP） / Fixed multi-source or distribution source |
| **双模式材料输入 Dual material input** | 手动 ZAID 表格或化学式输入（通过 `pymcnp M_0.from_formula()`） / Manual ZAID table or chemical formula |
| **3D 预览 3D preview** | 基于 PyVista 的几何可视化 / PyVista-based geometry visualization |
| **输出分析 Output analysis** | 解析 MCNP 输出文件，绘制计数结果（matplotlib），导出 CSV/Parquet / Parse output files, plot tallies, export |
| **xsdir 集成 xsdir integration** | 截面库 ZAID 校验与查找 / Cross-section library ZAID validation and lookup |
| **深色/浅色主题 Dark/Light theme** | 内置 QSS 主题切换 / Built-in QSS theme toggle |
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
| 几何 Geometry | 曲面与栅元 Surfaces & Cells | 曲面定义、栅元表格、3D 预览 / Surface definitions, cell table with 3D preview |
| 源 Source | SDEF | 固定点源或分布源模式 / Fixed point sources or distribution source mode |
| 计数 Tallies | F1–F8 | 启用/禁用计数及参数 / Enable/disable tallies with parameters |
| 能量 Energy | E0, CUT 卡 | 能量网格与时间/能量截断 / Energy mesh and time/energy cutoffs |
| 高级 Advanced | PHYS, 其他 | 物理卡、辅助卡、xsdir 路径 / Physics cards, auxiliary cards, xsdir path |
| 输出 Output | 结果 Results | MCNP 输出解析、绘图、导出 / Output parsing, plotting, export |

---

## 项目结构 Project Structure

```
├── main.py                    # 入口文件 Application entry point
├── requirements.txt           # 依赖 Dependencies
├── build.bat                  # PyInstaller 打包脚本 Build script
├── app/
│   ├── main_window.py         # 主窗口协调器 Main window orchestrator
│   ├── models.py              # 数据模型 Data models (DeckData, CellData, etc.)
│   ├── style.py               # QSS 样式表 QSS stylesheets
│   ├── project_io.py          # JSON 项目保存/加载 JSON project save/load
│   ├── inp_importer.py        # INP 文件导入器 INP file importer
│   ├── material_presets.py    # 预设材料库 Preset material library
│   ├── mcnp_detector.py       # MCNP 可执行文件自动检测 MCNP auto-detection
│   ├── xsdir_db.py            # xsdir 截面数据库 xsdir cross-section database
│   ├── xsdir_manager.py       # xsdir 路径管理 xsdir path management
│   ├── tabs/                  # 8 个 UI 标签页 8 UI tab pages
│   ├── dialogs/               # 模态编辑对话框 Modal edit dialogs
│   ├── widgets/               # 可复用组件 Reusable widgets (text mode toggle)
│   └── generator/             # INP 生成与解析引擎 INP generation & parsing engine
│       ├── inp_generator.py   # 主生成器 Main generator (~800 lines)
│       ├── validator.py       # 文件校验 Deck validation
│       └── parsers/           # INP 解析子包 INP file parser subpackage
```

---

## 许可协议 License

All Rights Reserved. 本软件仅供**查阅参考**。未经明确许可，不得修改、分发或商业使用。
This software is provided for **viewing purposes only**. No modification, distribution, or commercial use is permitted without explicit permission.

---

Built with [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) and [pymcnp](https://pypi.org/project/pymcnp/).

> 本项目代码由 AI 辅助生成 / This project was generated with AI assistance.
