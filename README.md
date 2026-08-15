# MCNP 输入卡生成器 — MCNP Input Card Generator

一款用于可视化创建、编辑、校验 **MCNP**（Monte Carlo N-Particle）输入文件（`.INP`）的桌面应用。用结构化、表单化的 GUI 替代手工文本编辑，内置 3D 几何预览、平面截面、材料库、能量/时间网格等工具。

A desktop application for visually creating, editing, and validating **MCNP** input files (`.INP`). Replaces manual text editing with a structured, form-based GUI, with built-in 3D preview, cross-section view, material library, and energy/time grids.

![应用截图](![alt text](<屏幕截图 2026-08-01 015145.png>))

![Version](https://img.shields.io/badge/Version-1.7.3-blue)
![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-teal)
![Shell](https://img.shields.io/badge/Shell-Tauri-green)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey)
![MCNP](https://img.shields.io/badge/MCNP-6.x%20Compatible-orange)

---

## 技术栈 Tech Stack

| 层 | 技术 |
|----|------|
| **前端 UI** | React + TypeScript + Vite（表单化标签页界面） |
| **3D 渲染** | Three.js（3D 预览）/ SVG（平面截面） |
| **窗口外壳** | Tauri（无边框自定义窗口：拖拽、缩放、最小化/最大化/关闭、圆角） |
| **后端** | Python（api_server：INP 解析/生成/校验/3D/截面），FreeCAD 做 CSG 几何 |
| **构建** | Vite（前端）→ Tauri（exe）+ PyInstaller（Python 后端 sidecar） |

---

## 功能特性 Features

| 功能 Feature | 说明 Description |
|-------------|-----------------|
| **表单化编辑 Form-based editing** | 8 个标签页覆盖所有 MCNP 输入段 |
| **INP 生成 INP generation** | 自动生成标准 MCNP 输入卡，含 C/`$` 注释、En/Tn/E0/T0 网格 |
| **INP 导入 INP import** | Windows 原生文件对话框选择 `.INP/.I/.TXT`，或直接拖入窗口；解析后一次性回填所有字段 |
| **文本↔表单双向互转** | 材料/几何/计数支持一键在"表单"与"原始文本"间切换，互转不丢数据 |
| **计数乘子 FMn** | 计数卡支持 FMn 乘子（导入自动识别 + 表单直接编辑，自动生成/回放） |
| **STEP 导入（GEOUNED）** | 几何标签页导入 `.STEP/.STP`，经 FreeCAD + GEOUNED 自动转换为 MCNP 曲面/栅元 |
| **工作区保存/恢复 Save/Restore** | 关闭自动保存、手动保存按钮、一键清空；刷新/重开自动恢复全部输入 |
| **3D 预览 / 截面** | FreeCAD 精确几何渲染，独立窗口可边编辑边看；截面由 STL 直接切出，支持 `#n` 栅元补集 |
| **条件编译行** | 材料/栅元支持 `#ifdef/#else/#endif`，所有行可拖拽排序 |
| **材料下拉选择** | 栅元表格与 3D 预览中点击材料号下拉选择，**自动填充材料密度** |
| **自定义窗口 Custom window** | 无系统边框 + 自绘标题栏（拖拽、最小化/最大化/关闭），类似 VSCode |
| **材料库 Material library** | 50+ 预设材料 + 化学式换算，xsdir 校验 |
| **E0/En/T0/Tn 网格** | 全局能谱/时间网格 + 每计数独立 En/Tn，线性/对数/自定义三模式 |
| **源模式 Source modes** | 固定多源 / SDEF 分布源（SI/SP）/ KCODE 临界源 |
| **主题 Themes** | 4 套 CSS 主题：夜之城（霓虹）/ 青空 / 护眼 / 多巴胺 |
| **MCNP 检测与运行** | 自动检测 mcnp6.exe，一键运行、跑完清理临时文件；默认走独显 GPU |
| **内联参考文档 Inline references** | 曲面卡、计数卡等结构参考一键查看 |
| **输出分析 Output analysis** | 解析 MCNP 输出文件并绘图 |

---

## 快速开始 Quick Start

### 环境要求 Prerequisites

- **Node.js 18+**（前端构建）
- **Python 3.10+**（后端，含 pymcnp、numpy 等）
- **Rust / Cargo**（仅打包 Tauri exe 时需要）
- **FreeCAD ≥ 0.20**（3D 预览/截面/STEP 导入用，检测到才启用）

### 开发运行 Run in Dev

```bash
# 前端（Vite，端口 1420）
cd gui
npm install
npm run dev

# 后端（api_server，端口 5001）
cd gui/backend
python api_server.py
```

浏览器打开 `http://localhost:1420`。

### 打包为 EXE Build Standalone EXE

> 出包请按 **`docs/手动打包方法.md`** 分步操作（v1.6.4 起已停用 build.bat / release.bat 自动化脚本）。
> 流程：vite 构建 → PyInstaller 打包后端 sidecar → 替换 `src-tauri/binaries/` → Tauri 构建 → 复制产物到交付目录 → 冒烟验证。

打包产物在 `gui/src-tauri/target/release/`（`bundle.active=false`，`bundle/` 目录为空属正常）。运行 exe 时前端自动拉起后端、关闭时一起退出。

---

## 用户界面 User Interface

| 标签页 Tab | 章节 Section | 说明 Description |
|-----------|-------------|-----------------|
| 基础 Basic | Title, MODE, NPS, CTME | 文件标识与粒子输运参数 |
| 材料 Materials | 材料卡 Material cards | ZAID/份额输入，含预设材料库 |
| 几何 Geometry | 曲面与栅元 Surfaces & Cells | 曲面定义、栅元表格、3D 预览、截面、STEP 导入 |
| 源 Source | SDEF / 固定源 / KCODE | 三种源模式 |
| 计数 Tallies | F1–F8 | 计数及 En/Tn 网格 |
| 高级 Advanced | PHYS, CUT, 其他 | 物理卡、粒子截断、辅助卡、xsdir 路径 |
| 输出 Output | 结果 Results | MCNP 输出解析、绘图、导出 |

---

## 项目结构 Project Structure

```
├── app/                            # Python 核心（生成/解析/校验引擎）
│   ├── generator/                  # inp_generator、parsers、validator
│   ├── models.py                   # 数据模型 (DeckData, CellData, ...)
│   ├── freecad_preview.py          # FreeCAD 3D 预览封装
│   ├── _freecad_csg_worker.py      # FreeCAD CSG 几何求值子进程
│   ├── geouned_worker.py           # GEOUNED 转换 worker（FreeCAD python 子进程）
│   ├── step_importer_geouned.py    # GEOUNED 转换器封装
│   ├── freecad_locator.py          # FreeCAD 定位（检测/手动指定路径唯一入口）
│   ├── stl_cross_section.py        # 从 STL 切平面（numpy，截面用，不依赖 FreeCAD）
│   ├── xsdir_db.py                 # xsdir 截面数据库
│   └── material_presets.py         # 预设材料库
└── gui/
    ├── src/                        # React 前端
    │   ├── App.tsx                 # 主界面（顶栏/导入/生成/保存恢复）
    │   ├── components/             # 标签页与对话框
    │   │   ├── BasicSettings / GeometryTab / MaterialTab / SourceTab / TallyTab / AdvancedTab / OutputTab
    │   │   ├── Preview3D.tsx       # 3D 预览（Three.js + 材料着色）
    │   │   ├── CrossSectionView.tsx# 平面截面
    │   │   ├── MaterialPanel.tsx   # 材料图例 + 栅元列表（共享组件）
    │   │   └── GridEditor.tsx      # E0/En/T0/Tn 网格编辑器
    │   ├── utils/
    │   │   ├── DeckContext.tsx     # 单一权威表单状态
    │   │   ├── gridState.ts        # 网格解析/序列化深模块
    │   │   ├── backend.ts          # 后端生命周期（启动/关闭 sidecar）
    │   │   └── materialColors.ts   # 材料颜色单一来源
    │   └── styles/global.css       # CSS 变量（4 主题）
    ├── backend/
    │   ├── api_server.py           # HTTP 后端（生成/解析/3D/截面/运行）
    │   ├── mcnp_bridge.py          # 打包后 sidecar 启动器（拉起 api_server）
    │   └── xsdir_db.py
    ├── src-tauri/                  # Tauri 窗口外壳
    │   ├── tauri.conf.json         # 无边框窗口、sidecar 配置
    │   └── icons/
    └── electron/                   # （备用）Electron 外壳
```

---

## 引擎说明 Engine Notes

### 3D 预览（FreeCAD CSG）

- 以 JSON AST 序列化 pymcnp 几何树，FreeCAD 子进程用 `Part.Shape` 布尔运算求值
- 支持 `#n` 栅元补集算子（如空心反射体），输出 STL 网格按材料着色
- 3D 预览与截面均为独立窗口；截面直接从保留的 STL 切（numpy），不重新调 FreeCAD

支持的曲面：P, PX/PY/PZ, S/SO/SX/SY/SZ, C/X/C/Y/C/Z, CX/CY/CZ, K/X/K/Y/K/Z, KX/KY/KZ, SQ, GQ, RPP, RCC, SPH, BOX, TRC, REC, WED, ARB 等，支持 TRn 坐标变换。

### STEP 导入（GEOUNED）

「几何」标签页 → 「导入 STEP」，经 **GEOUNED**（西班牙 CIEMAT 开发，EUPL-1.2）转换：
- 随程序打包、无需单独安装；运行时经 FreeCAD Python 调用，**用户仅需另装 FreeCAD**
- 自动转换并回填曲面/栅元卡，科学计数法自动整理为 3 位小数（GQ/SQ 保留精度）

---

## 引用与致谢 Acknowledgements

| 项目 | 用途 | 许可证 |
|------|------|--------|
| [React](https://react.dev/) | 前端 UI 框架 | MIT |
| [Vite](https://vitejs.dev/) | 前端构建工具 | MIT |
| [Tauri](https://tauri.app/) | 桌面窗口外壳 | MIT/Apache-2.0 |
| [Three.js](https://threejs.org/) | 3D 渲染 | MIT |
| [PyMCNP](https://github.com/FSIBT/PyMCNP) | MCNP 核心库（几何、生成、解析） | BSD-3-Clause |
| [FreeCAD](https://www.freecad.org/) | 3D CAD 几何处理（CSG 求值引擎） | LGPL v2+ |
| [GEOUNED](https://geouned-org.github.io/GEOUNED/) | STEP → MCNP 几何转换引擎（随程序打包） | EUPL-1.2 |
| [OpenCascade](https://dev.opencascade.org/) | CAD 内核（FreeCAD 依赖） | LGPL v2.1 |
| [NumPy](https://numpy.org/) | 科学计算 | BSD-3-Clause |

---

## 许可协议 License

**All Rights Reserved.** 版权所有 © 2026 魏祎卓

> **本许可仅适用于本项目自有代码。** 所捆绑/调用的开源组件保留其各自许可证：GEOUNED（EUPL-1.2）、OpenCascade（LGPL v2.1）、FreeCAD（LGPL v2+）、pymcnp（BSD-3-Clause）、React（MIT）、Vite（MIT）、Tauri（MIT/Apache-2.0）、Three.js（MIT）、NumPy（BSD）等，详见上方"引用与致谢"。

- ✅ 允许个人及机构内部**免费使用**
- ✅ 允许为自用或内部使用**修改代码**
- ❌ **严禁任何形式的盈利活动**（销售、付费服务、商业嵌入等）
- ❌ 修改后公开发布须**经作者书面许可**

如需授权请联系：1378963177@qq.com

---

> 本项目由 AI 辅助编程完成 / Built with AI assistance (Claude).
>
> Built with [React](https://react.dev/), [Vite](https://vitejs.dev/), [Tauri](https://tauri.app/), and [pymcnp](https://pypi.org/project/pymcnp/).
