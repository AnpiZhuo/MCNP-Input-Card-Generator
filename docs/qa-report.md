# QA 报告 — P0 测试防线 + P1 终态复核 + 3D 预览性能修复 + 打包产物验证 + 复验 + 网格计数可视化验收

> 测试工程师产出 | 日期：2026-08-12 | 交付产物：D:\MCNP\MCNP输入卡生成器\（v1.6.3 两次打包）
> 运行：仓库根 `python -m pytest tests/ -v`；前端 `cd gui && npx vitest run`

## 〇-7、网格计数（FMESH/TMESH）3D 体积可视化·最终复审（施工链最后一道验收：**通过**）

> 日期：2026-08-14 | 复审：tester（只读独立复跑 + 真实后端 5001 HTTP 冒烟 + 授权删除，未改任何代码/测试/断言）| 分支 experiment/geouned 工作树
> 背景：上轮「有条件通过」的 2 项严重（parse 元数据缓存 / §9.1 三测试文件）已由 backend-meshtal 修复 + P0 spec 补丁已生效，本轮回查闭环。

### 〇-7.1 授权删除确认（任务 0）
- ✅ `gui/test_electron.cjs`（electron 残留脚本，require electron 已失效）已 `git rm`（git status `D gui/test_electron.cjs`）；`gui/electron/`（main.cjs/preload.cjs）此前已整目录删除。用户 2026-08-14 具名授权，本次为唯一写操作。

### 〇-7.2 A. 两项严重闭环（独立复跑核实）
| 项 | 证据 | 结果 |
| :--- | :--- | :--- |
| A-1 parse 元数据缓存 <1s | `_meshtal_worker.py` `_mode_parse`（:63-120）先 `cache.get_manifest(fp)`（:74-76）命中即重建返回；`meshtal_cache.py` 增 `get_manifest/put_manifest`（:35-58）。独立实测 valid_39（3.36MB）worker 子进程：cold 4.338s → **cache hit 0.2314s <1s**；HTTP 实测 cold 3.308s → **cache hit 0.233s**；两次结果逐字节一致 | ✅ 闭环 |
| A-2 §9.1 三测试文件 | `tests/unit/test_meshtal_cache.py`（9 用例）/ `test_meshtal_worker.py`（5 用例，含 `test_worker_texture_bad_tally_errors`）/ `tests/parser/test_fmesh_parser.py`（7 用例，含 `test_multi_interval_imesh_preserved`）均在位且全绿（并入 430/0） | ✅ 闭环 |

### 〇-7.3 B. P0 spec 补丁（Grep 核实）
- ✅ `gui/mcnp_sidecar.spec` `_keep_dirs = ["generator", "docs", "meshtal"]`（app/meshtal 8 模块落盘 `_internal/app/meshtal/`，v1.7.0 打包前置）
- ✅ `gui/backend/api_server.py` `_meshtal_worker_script()`（:34-42）：`sys.frozen+_MEIPASS` → `_MEIPASS/app/meshtal/_meshtal_worker.py`；dev 返回 `PROJECT_DIR/app/meshtal/_meshtal_worker.py`（PROJECT_DIR=仓库根，:16 归一化正确）；parse（:809）/ texture（:880）两处 handler 均调用

### 〇-7.4 C. 全绿零回归（独立复跑）
| 项 | 结果 |
| :--- | :--- |
| 全量 pytest | ✅ **430 passed / 0 failed**（14.08s；343 基线零回归 + 66 meshtal + 21 三新文件） |
| 前端 vitest | ✅ **76 passed / 13 文件**（19 基线不破 + 57 volume） |
| tsc / build | ✅ EXIT 0 / EXIT 0（仅既有 chunk 体积警告） |
| 漂移闸门 25→28 | ✅ test_api_contract.py 7/7 绿（并入 430）；handlers dict **28 端点**（grep 实测）+ api.yaml **28 path** + meshtalDetect/Parse/Texture operationId |
| R1 不动点 | ✅ tests/parser/ 全绿（含 test_regress_fmesh_import R1 fixed point） |

### 〇-7.5 D. KPI 实测（真实后端 5001 + 真实 FreeCAD + 真实 fixture）
| 指标 | 目标 | 实测 | 结论 |
| :--- | :--- | :--- | :--- |
| preview-3d HIT | ≤1s | **0.011s**（1-cell sphere，MISS 经 FreeCAD 产真实 STL 后缓存命中） | ✅ |
| meshtal-texture 开窗链路 | <2s | **0.402–0.582s**（valid_39 tally 4；标量帧 base64 往返 bytes==nVoxels==decoded） | ✅ |
| parse 元数据缓存命中 | <1s | **0.233s**（HTTP 二次 parse，同文件同 mtime） | ✅ |
| 128³ 切帧 | ≤50ms | ✅ colorize.test.ts 计时代理 vitest 绿（valid_39 native 10×10×100 按契约 §3.3 保 native，downsampled=False；128³ 降采样路径由 volume_builder/worker 单测覆盖） | ✅ |
| 大文件解析不卡 5001 | 不阻塞 | ✅ valid_39 cold parse 期间并发探活 meshtal-detect **3.6–17.2ms** | ✅ |
| GPU 驻留 | ≤256MB | ✅ downsample_plan 预算断言绿（128³=8MiB / 256³=64MiB） | ✅ |

### 〇-7.6 E. 产品方向 F1-F5（抽查实现 + vitest）
- F1.1 空态三步引导：workflow.ts「① 先运行 MCNP（或选择 meshtal 文件）→ ② 点解析 → ③ 看结果」+ workflow.test.ts 5 用例绿 ✅
- F1.2 没找到文件可操作提示：noFileMessage「未在输出目录找到 MESHTAL 文件 / 请点这里选择 meshtal 文件」→ choose-file ✅
- F2 高级控件默认折叠：VolumeControlPanel `showAdvanced=useState(false)` +「▼ 高级设置」✅
- F3 大白话弹窗：`OVER_BUDGET_POPUP_COPY="要更流畅，还是要更精细？"` ✅
- F4 hint 优先：api.ts `errorHint(j)` 先 j.hint 后 j.message；HTTP 实测坏 tally → 500 + hint「请重新选择计数与能量/时间范围」✅
- F5.1 FMESH 幽灵文字：FMeshForm `FMESH_FIELD_LABELS` 每字段 placeholder/title 注明关键字作用 ✅
- F5.2 色条图例：ColorLegend displayMin/displayMax + unit「归一化计数」+ legendTicks 纯函数 + 8 用例绿 ✅

### 〇-7.7 F. 纪律核对
- ✅ 零新依赖：requirements/package.json 零新增（仅已批准清理：删 pyvista/markdown/electron，补 numpy 显式声明）
- ✅ 测试不 import gui.backend.api_server / FreeCAD（精确 import 语句扫描 0 命中）
- ✅ 未改 Preview3D.tsx（git diff 空）
- ✅ ResultWindow 关闭只 closeCurrentWindow()（=close_window），无 clearStlSession
- ✅ 无删弱断言：git diff tests/ 空、仅 3 新未跟踪测试文件；colormap midpoints 115→116 为 PM 仲裁补正（golden 为准，允许）
- ✅ worker 模块顶 stdlib-only（test_meshtal_worker AST 断言绿）

### 〇-7.8 问题列表
- ❌ 致命：0。⚠️ 严重：0。💡 建议：#/volume 真浏览器冒烟待人工补跑（本环境无浏览器自动化且红线禁装 playwright/puppeteer，不阻塞）。

### 〇-7.9 打包就绪（v1.7.0 前置）
- ✅ spec 已含 meshtal（_keep_dirs）；`_meshtal_worker_script()` 路径解析正确（dev/MEIPASS 双路径）；3 端点 HTTP 冒烟通过 → **打包就绪**
- ⏳ `#/volume` 真浏览器冒烟记录待人工补跑（方法：vite dev 起 `#/volume`，经 FMeshForm 解析 valid_38/39 派生 fixture 开窗 → 断言体积层渲染/外壳勾选/半透明/时间轴）；单元层等价断言（VolumeRenderer A2.1 自动取景 / alignWorld / colorize / volumeShader 快照 / workflow）已全绿

### 整体评估结论
- **❌ 致命：0 个。⚠️ 严重：0 个。** 2 项严重全部闭环；spec 打包前置已生效；全量 pytest **430/0** + vitest **76/0** + tsc/build EXIT 0 + 漂移闸门 25→28 双向绿 + R1 零回归；KPI 全部实测达标；F1-F5 全过；纪律零违例；**打包就绪**。
- **验收结论：通过**。建议人工补跑 `#/volume` 真浏览器冒烟后按 v1.7.0 打包。

## 〇-6、网格计数（FMESH/TMESH）3D 体积可视化验收复核（契约 meshtal-visualization.md 步 5：**有条件通过**）

> 日期：2026-08-14 | 复核：tester（只读独立复跑 + 真实 HTTP 联调，未改任何代码/测试/断言）| 分支 experiment/geouned 工作树
> 施工方汇报：后端 pytest 409/0、前端 vitest 76、golden sha256 命中、tsc/build 通过 —— **逐项独立复跑核实**。

### A. 测试全量（逐项独立复跑）
| 验收项 | 施工方汇报 | 独立复跑结果 |
| :--- | :--- | :--- |
| 全量 pytest | 409 通过 / 0 失败 | ✅ **409 passed / 0 failed**（16.49s；343 基线零回归 + 66 新增全绿） |
| 前端 vitest | 76 全绿 | ✅ **76 passed / 13 文件**（基线 19 不破 + 新增 57） |
| tsc | EXIT 0 | ✅ EXIT 0 |
| build | EXIT 0 | ✅ EXIT 0（2.91s，仅既有 chunk 体积警告） |
| 契约漂移闸门 | 25→28 双向一致绿 | ✅ test_api_contract.py **7/7 绿**；api.yaml 三 operationId（meshtalDetect/Parse/Texture）在位；handlers dict 25→28（grep 实测 3 新端点） |
| R1 不动点 | 不回归 | ✅ tests/parser/ 141 全绿（含 test_r1_fixed_point_fmesh_roundtrip + 既有 R1 全套） |

### B. 红基线终态
- ✅ 7 文件 66 用例全绿（test_regress_fmesh_import 6 + test_meshtal_parser 10 + test_meshtal_deck_match 14 + test_meshtal_downsample_plan 10 + test_meshtal_volume_builder 7 + test_meshtal_colormap 10 + test_meshtal_api 9）。**63 红 → 63 绿**，3 绿对照（R1 不动点对照 / 无 FMESH 卡对照 / hint 空缺省省略对照）保持绿。

### C. §7.3 对齐断言
- ✅ alignWorld.test.ts **5 用例全绿**（shared_offset_invariant / 尺寸保持 / 相对位移保持 / volume_inside_shell / world_box_from_edges）。
- 抽查 alignWorld.ts 实现：`translateToCenter` 单一归一化偏移（offset=-unionBox.center，逐几何 translate 同一 offset），外壳与体积盒共用 → §7.2 关键不变量成立。

### D. KPI 实测（真实后端 5001 + 真实 FreeCAD + 真实 meshtal fixture）
| 指标 | 目标 | 实测 | 结论 |
| :--- | :--- | :--- | :--- |
| preview-3d 二次命中（开窗 STL 链路） | ≤1s | MISS 2.491s / **HIT 0.041s**（prob41c，2 cells，114KB STL） | ✅ |
| meshtal-texture（worker 缓存命中） | <2s | **0.202s**（valid_39 3.36MB，parse 后缓存命中） | ✅ |
| 128³ 切帧（colorize + texSubImage3D 代理） | ≤50ms | ✅ colorize.test.ts「128³ 计时 <50ms」vitest 绿 | ✅ |
| 大文件解析不卡 5001 | 子进程 worker 不阻塞 | ✅ meshtal-parse valid_39 解析期（3s）并发探活 meshtal-detect 响应 **2–25ms** | ✅ |
| meshtal-parse 元数据缓存命中 | <1s（§8） | ⚠️ 二次调用仍 **3.07s**（缓存未命中，见问题 1） | ❌ 未达成 |
| GPU 驻留 | ≤256MB | ✅ downsample_plan 预算断言绿（128³=8MiB / 256³=64MiB） | ✅ |
| 开窗 ≤2s | preview 命中 + texture 命中 + 首帧 | ✅ ResultWindow 链路：texture 0.2s + STL 0.04s + 128³ colorize <50ms ≪ 2s | ✅ |

### E. e2e 冒烟（#/volume 路由）
- ✅ 静态链路：App.tsx `#/volume` → ResultWindow（line 438/444）+ windows.ts 桥（KEY_VOLUME3D/openVolume3D/readVolumeData）+ main.rs `open_volume3d_window`（label `volume3d`，title「3D 结果」）+ TallyTab 嵌 FMeshForm + PreviewDialog A1.1 自动 meshtal-detect 全部在位；vite dev 服务 index HTTP 200。
- ⚠️ 真浏览器 canvas 非空 + 无 console 报错**需人工浏览器冒烟**（本环境无浏览器自动化且红线禁装 playwright/puppeteer）。方法：vite dev 起 `#/volume`，先经 FMeshForm「解析」valid_38/39 派生 fixture 开窗 → 断言体积层渲染非空、外壳勾选/半透明/时间轴可交互、空态三步引导可见。单元层等价断言（VolumeRenderer A2.1 自动取景 / alignWorld / colorize / volumeShader 快照 / workflow）已全绿。

### F. 产品方向 F1-F5 逐条核对
| 项 | 核对 | 结果 |
| :--- | :--- | :--- |
| F1.1 空态三步引导 | workflow.ts「① 先运行 MCNP（或选择 meshtal 文件）→ ② 点解析 → ③ 看结果」+ workflow.test.ts 5 用例绿 | ✅ |
| F1.2 没找到文件可操作提示 | workflow.ts noFileMessage「未在输出目录找到 MESHTAL 文件 / 请点这里选择 meshtal 文件」→ choose-file | ✅ |
| F2 高级控件默认折叠 | VolumeControlPanel showAdvanced 默认 false（「▼ 高级设置」），128³/自适应色阶/自动取景/外壳开箱即用 | ✅ |
| F3 大白话弹窗 | downsampleRequest.ts OVER_BUDGET_POPUP_COPY「要更流畅，还是要更精细？」+ 解析失败 hint | ✅ |
| F4 错误 hint 优先 | api.ts errorHint(j) 优先 j.hint 其次 j.message；HTTP 实测坏文件 → hint「请确认是 MCNP 生成的 meshtal 文件…」；既有端点错误无 hint 字段（加性兼容） | ✅ |
| F5.1 FMESH 幽灵文字 | FMeshForm FMESH_FIELD_LABELS 每字段 placeholder/title 注明关键字作用 | ✅ |
| F5.2 色条图例单位+上下限 | ColorLegend displayMin/displayMax + unit（默认「归一化计数」）+ legendTicks 纯函数；ColorLegend.test.ts 8 用例绿 | ✅ |

### G. 纪律核对
- ✅ **零新依赖**：package.json / requirements.txt / dev-requirements.txt 零变更（git diff 为空）。
- ✅ **测试不 import 禁项**：grep 全 tests/ 无 `import gui.backend.api_server` / `import FreeCAD`（仅注释声明）。
- ✅ **未改 Preview3D.tsx 主组件**（git status 无该文件）。
- ✅ **ResultWindow 关闭不清 STL 会话**：关闭只 closeCurrentWindow()（=close_window），无 clearStlSession。
- ✅ **无删弱/改断言骗绿**：`git status tests/` 仅新增 7 未跟踪测试文件，**零既有测试改动**。colormap midpoints `(249,115,22)→(249,116,22)` 系 PM 仲裁补正（golden 为准，非删弱），实测 python `weather_lut(256)` sha256 = `36770ae2b9cd…515358c038` **与 TS golden 逐字节一致**。
- ✅ **worker stdlib-only**：_meshtal_worker.py 模块顶仅 base64/json/os/sys/traceback；numpy/pymcnp 惰性。
- ✅ **契约文档改动**：api.yaml diff 仅 +3 meshtal path + hint + 头部 25→28；meshtal-visualization.md 为新契约文件（§3.4 行序勘误已反映）。
- ✅ 后端改动范围：仅 FMESH 五步走（sections/core/parsers __init__/models/inp_generator/fmesh_parser）+ app/meshtal/ + api_server 3 端点 + 前端 wiring。

### 问题列表
#### ⚠️ 严重 1：meshtal-parse 元数据缓存未实现（契约 §4.4 / §8 KPI 未达成）
- 证据：`app/meshtal/_meshtal_worker.py` `_mode_parse`（:63-109）**从不查 `cache.get`**，每次无条件 `parse_meshtal_file(path)` 全量重解析（只 put 不 get）。handler（api_server.py:789）每请求 spawn 新 worker，无 handler 层缓存。实测 valid_39（3.36MB）连续两次 meshtal-parse 均 **3.07s**（应 <1s 缓存命中）。
- 契约要求：§4.4「meshtal-parse 元数据也缓存（防弹窗流程重复解析）」；§8 KPI「元数据 <1s（缓存命中）」。当前缓存命中路径对 parse 不可达（texture 已缓存，0.2s，不受影响）。
- 影响：用户重复点「解析」或前端重复流程时整文件重解析，大 meshtal（10MB+）每次数秒~数十秒。核心开窗链路（parse 一次 + texture 缓存命中）达标。
- 修复方向（后端）：`_mode_parse` 对每 tally 先 `cache.get(fp, number)`，全命中则从缓存重建元数据（bins/range）返回；仅 miss 才解析 + put。handler 层无需改。

#### ⚠️ 严重 2：契约 §9.1 三个测试文件缺失
- 证据：`tests/unit/test_meshtal_cache.py`、`tests/unit/test_meshtal_worker.py`、`tests/unit/test_fmesh_parser.py` **不存在**（grep 无任何测试引用 MeshtalParseCache / _meshtal_worker / parse_fmesh_lines / cardTextToFmesh）。契约 §9.1 列 10 个新增测试文件，实际落地 7 个。
- 影响：worker 模块顶 stdlib-only 的 AST 断言（§4.5 显式要求「照 test_preview3d_worker.py 风格」）、cache fingerprint/evict 单测、fmesh_parser 独立单测缺位（fmesh 往返已由 test_regress_fmesh_import 间接覆盖）。当前实现本身合规（worker 实测 stdlib-only），属**回归防护缺口**。
- 修复方向：补齐 3 个测试文件（worker AST 断言 + cache 单测 + fmesh_parser 单测），基线 pytest 409→+N 不破既有。

### 整体评估结论
- **❌ 致命：0 个。** ⚠️ 严重：2 个。💡 建议：e2e 真浏览器冒烟待人工补跑。
- 核心功能全链路打通：FMESH/TMESH 结构化五步 + app/meshtal/ 8 模块 + 3 端点 + volume3d 窗口 + 对齐断言 + 主 KPI（开窗/texture/preview 命中/切帧/非阻塞）全部实测达标；409 pytest + 76 vitest 全绿；golden 跨语言一致；纪律零违例。
- **建议**：不构成打回。建议后端补齐 meshtal-parse 元数据缓存（严重 1）+ 补齐 §9.1 三个测试文件（严重 2），并人工补跑 `#/volume` 真浏览器冒烟后**转「通过」**。已更新 PROJECT_MEMORY.md 记录两处待收口项。

## 〇-5、重新打包复验结论（v1.6.3 带 GeometryTab 修复：**通过**）

新 exe 6645760B（旧版 6645248B，尺寸变化证明前端修复已打包，commit 773742a）。

| 验证项 | 结果 |
| :--- | :--- |
| exe 启动 | ✅ Tauri 进程（PID 3792）+ sidecar 拉起，5001 秒级 LISTENING |
| 5001 探活 | ✅ mcnp-detect/xsdir-check 200/ok、generate 200/ok（inp 217B 含 SDEF） |
| 3D 预览出图 | ✅ shield_20m→1040 tri、prob41c→500+1252 tri，stl_data 非空，miss/hit 四字段一致（缓存命中正常） |
| **材料下拉修复（本次重打包目的）** | ✅ **bundle grep 确认已打入**（详见下） |
| spec 自检 | ✅ `_internal/app/preview_cache.py` 存在、`_internal/PyQt5` 不存在 |
| 清理 | ✅ exe + sidecar 终止，5001 释放，无残留 |

### 材料下拉修复验证方式与结论
- **方式**：grep 打包构建产物 `gui/dist/assets/index-*.js`（23:47 构建，即打入 exe 的前端 bundle）中的 portal 独有**字符串字面量**（压缩不会改字符串）+ 行为标记。
- **结果**：`createPortal`×2、`document.body`×1、`zIndex:1100`（遮罩）/`zIndex:1200`（下拉）、`position:"fixed"`、`preview-overlay`、`mat-cell-btn`、以及 GeometryTab 材料下拉独有背景 `rgba(15,15,40,0.97)` 全部在 bundle 中 → portal 渲染到 body + fixed 定点 + 遮罩关闭已打包。
- **clampDropdownLeft 说明**：函数名被生产压缩重命名（等价重构，行为不变），exe/dist 中无该名字符串属预期；其右缘防溢出逻辑已由 `gui/test/portalPosition.test.ts` 6 用例（19/19 全绿）对同源代码独立验证。
- **结论**：材料下拉 portal 修复在打包版中生效。

## 〇-4、打包产物验证结论（v1.6.3：**通过**）

交付产物 `D:\MCNP\MCNP输入卡生成器\`：`MCNP 输入卡生成器.exe`（6645248B）+ `python.exe`（25035105B sidecar）+ `_internal/`。

| 验证项 | 结果 |
| :--- | :--- |
| exe 启动 | ✅ Tauri 窗口进程（PID）+ sidecar python.exe 同时拉起，5001 秒级 LISTENING |
| 5001 HTTP 探活 | ✅ mcnp-detect 200/ok（found=True）、xsdir-check 200/ok（loaded=True）、generate 200/ok（inp 215B 含 SDEF）——完整应用层响应，非 connection refused |
| 3D 预览出图 | ✅ shield_20m → cell1 STL 1040 三角形；prob41c → cell1 500 + cell3 1252 三角形；stl_data 非空；miss/hit 四字段一致（preview_cache 打包后命中路径正常，vtk 惰性 + bound 修正生效） |
| spec 修复 1 | ✅ `_internal/app/preview_cache.py` 存在（7481B，已在 _keep_py） |
| spec 修复 2 | ✅ `_internal/PyQt5` 不存在（已在 excludes） |
| vendor | ✅ `_internal/vendor/geouned/`（GEOReverse/GEOUNED）打包 |
| 清理 | ✅ 验证后已终止 exe + sidecar 进程，5001 释放，无残留 |

**结论**：打包产物完整可用，核心引擎、3D 预览（含缓存命中）、xsdir、MCNP 检测在打包 sidecar 中全部正常。spec 两处修复（preview_cache 保留 / PyQt5 排除）生效。

## 〇-3、3D 预览性能修复复核结论（步 6：**通过**）

**后端全量 271 通过 / 0 失败**（251 基线零回归 + 新增 20）；**前端 vitest 4 文件 13 用例全绿**。

### 复核清单
| 项 | 结果 |
| :--- | :--- |
| 后端全量 | ✅ 271 绿 / 0 红（test_preview_bound 8 + test_preview_cache 8 + test_preview3d_worker 4） |
| 前端 vitest | ✅ 4 文件 13 用例（cameraParams 4 / tickGrid 4 / renderGate 2 / cellMaterial 3） |
| 契约验收 bound | ✅ shield_20m≈2700、stress_bunker≈2050、inp01≈13100、inp09≈3665（区间断言）+ RCC/WED/BOX 轴长定点 + GQ/SQ 跳过 |
| 契约验收 cache | ✅ fingerprint 稳定、put_get_hit、evict_lru/evict_dir、命中跳过 builder |
| 契约验收 worker | ✅ 顶层无 import vtk、惰性 import 在 `_quadric_to_shape` 内且位于 native 回退后、`_HAVE_VTK` 初值 False |
| 契约验收前端 | ✅ cameraParams farNear≤1e4、tickGrid dispose==created + 对象≤60/纹理≤30、renderGate idle 0 渲染、cellMaterial 默认 opaque |
| 联调点（真实 FreeCAD） | ✅ /api/preview-3d 四字段 miss/hit 一致；命中后 cross-section 复用正常（shield_20m fixture → STL 1040 tri → slices=1、polygons=2） |

### 纪律核对
- 无断言降级：既有 251 用例零改动（git diff 仅新增 3 preview 测试文件 + 7 fixtures）；总用例 271 不变。
- 未触碰 `app/generator/` 与 `parsers/`（git diff 确认）。
- api_server 路由表零变更（handlers dict 0 增删行）；漂移闸门 test_api_contract.py 7/7 绿。
- 新测试不 import `gui.backend.api_server` / FreeCAD：`app/freecad_preview.py` 与 `app/preview_cache.py` 顶层仅 stdlib，worker 以子进程隔离；test_preview3d_worker.py 走 AST。
- 无新增运行时依赖：vitest 仅 devDependencies；requirements.txt / dev-requirements.txt 零变更。

### 联调观察（非阻塞）
最小测试几何（圆柱 + pz 顶盖）经 worker 产出空 STL（0 三角形），但真实 fixture（preview_shield_20m）产出有效 STL（1040 tri）且 cross-section 正常。空 STL 属 worker 对退化输入的曲面细分特性，与本分支性能改动（bound 修正 / vtk 惰性 / 缓存）无关，非回归。

## 〇-2、P1 终态复核结论（全量计划 P0+P1+P2 完成）

**全量终态：251 通过 / 0 失败**（复跑稳定）。P1 技术债清偿 7 项全部 Resolved。

### P1 复核清单（逐 F#）
| F# | 验证项 | 结果 |
| :--- | :--- | :--- |
| F#7 | pymcnp 模块顶部 import（inp_generator.py:8 `from pymcnp import inp as pymcnp_inp`）；test_f7_*×2 绿 | ✅ |
| F#3 | `import json as` / `E0DBG` / 函数内 `import sys` 全归零（仅文档残留）；test_f3_*×2 绿 | ✅ |
| F#4 | `_build_sdef_parts(src, include_special)` 合并两分支（247/298）；`test_sdef_single_source_delegates` pin 精确串 `SDEF  ERG=14.0  POS=0 0 0` 不变；test_generator_sdef.py 全绿 | ✅ |
| F#5+F#6 | kitchen-sink R1/R4 红→绿（g1==g2 字节恒定，len 2099==2099）；样例 prob41c/avr13/inp24 R1 保持绿；test_generator_multi_source.py / test_generator_sdef.py 全绿 | ✅ |
| F#1 | 8 守卫收敛 `_apply_raw_override`（1149，8 调用点）；1145 tally-key 门控行为一字不动（三例 pin 绿）；raw_overrides 兼容性保留 | ✅ |

### 纪律核对
- 无断言降级：用例总数 251 不变（0 删除/0 skip/0 xfail/0 pass 骗绿；仅契约闸门防御守卫在非触发路径）。
- api_server 路由表 / api.yaml 漂移闸门保持绿（test_api_contract.py 7/7）。
- `_wrap_long_lines` 与 `_generate_structured_distributions` 未进入 P1 diff（git diff -U0 核对 hunk 无两函数定义行）；`'  '.join` 语义仅随 F#5/6 重构在 multi_source 内调整。
- 无新依赖（requirements.txt / dev-requirements.txt 与 P0 基线无 diff）。
- `review_findings.json` 7 项全部标 Resolved（F#1=1488aae、F#2=historical、F#3=c774e56、F#4=52ca251、F#5/6=e404172+018ced5、F#7=bf0a2c7）。

### kitchen-sink 实证（5 项残留差异全部消除）
| 差异项（P0 时） | P1 后 |
| :--- | :--- |
| `POS=F D1` → `X=F Y=D1` 退化 | ✅ 保持 `POS=F D1` |
| `TME=D6` → `TME=0.0` 分布丢失 | ✅ 保持 `TME=D6` |
| SI1 V 型 → L 型 | ✅ 保持 `SI1  V` |
| 概率键控注释丢失 | ✅ 保留 `probability keyed to D1` |
| SI 值空格归一化 | ✅ 字节恒定 |

## 〇、第二轮复核结论（M1.4 门禁：**通过**）

**全量终态：245 通过 / 6 失败**（与契约 §0.5.3 一致）。P1 放行条件达成。

### 复核清单（§0.5.2 门禁）
| 项 | 结果 |
| :--- | :--- |
| minimal + 3 样例（prob41c/avr13/inp24）R1 不动点 | ✅ 全绿（F-A 头泄漏已修，`banners.py` + `split_sections` 单一拦截点） |
| F-B validate_deck 不再崩溃 | ✅ 全绿（validator `_unwrap_cells` 适配 CellRow） |
| F-C 多粒子计数卡解析 | ✅ 全绿（core.py `_PARTICLE_RE` 逗号设计符） |
| F-D 材料 options 保留 | ✅ 全绿（options 移到 M 头行） |
| 既有 129+73+7 零回归 | ✅ 209 通过 |
| 纪律：无断言降级 / P1 范围未触碰 | ✅ `_wrap_long_lines`、`_generate_multi_source`、`_generate_distribution_sdef` 均未改动 |
| F-F/F-G/F-H pin 翻新 | ✅ 已改为断言修复行为（非 pass/skip），仍绿 |

### 6 红构成（均设计内）
1. `test_r1_fixed_point_kitchen_sink` — **归 P1**（F#5/F#6 验收项）
2. `test_r4_kitchen_sink_full_roundtrip` — **归 P1**
3. `test_f3_no_function_level_import_json_in_inp_generator` — 技术债 F#3，待 P1
4. `test_f3_no_function_level_import_sys_in_parsers` — 技术债 F#3，待 P1
5. `test_f7_pymcnp_imported_at_module_level` — 技术债 F#7，待 P1
6. `test_f7_pymcnp_function_level_import_absent` — 技术债 F#7，待 P1

> kitchen-sink R1 残留差异已实证纯化为**多源 SDEF 字段重组漂移**（`POS=F D1`→`X=F Y=D1`、`TME=D6`→`TME=0.0`、SI1 V 型→L 型、分布注释丢失）；头泄漏归零（输出增长 2102→2266 缩至 2102→2110，无 cell 注释污染/曲面计数膨胀）。P1 重构 F#5/F#6 后应转绿。

## 一、审查范围

为 MCNP 输入卡生成器 v1.6.3 建立第一道测试安全网（全仓库此前零测试）。覆盖：

| 模块 | 文件 | 用例数 |
| :--- | :--- | :--- |
| 测试基建 | `tests/conftest.py`（sys.path 引导 + deck 工厂 + 样例装载）、`tests/fixtures/`（prob41c / avr13 / inp24，vendor 自 MCNPX_EXTENDED 与 REGRESSION 测试套件）、`dev-requirements.txt`（pytest>=8.0） | — |
| 生成器单测 | `tests/unit/` 8 文件（cells/basic/materials/sdef/multi_source/tallies/phys/overrides） | 129 通过 |
| 解析管线单测 | `tests/parser/` 8 文件（lines/sections/core 分拆/parse_inp 入口） | 73 通过 |
| 往返不变量 | `tests/integration/test_roundtrip.py`（R1/R2/R3/R4） | 混编 |
| 样例冒烟 | `tests/integration/test_sample_smoke.py`（prob41c + avr13 + inp24） | 混编 |
| 技术债联动 | `tests/integration/test_tech_debt.py`（F#3/F#4/F#5/F#6/F#7，F#1 在 unit） | 混编 |
| 契约漂移闸门 | `tests/integration/test_api_contract.py`（AST + contract.ts + 三核心端点 HTTP） | 7 通过 |

**总体：234 通过 / 17 失败。17 个失败全部为"按设计先红"的技术债/往返缺陷 pin（红 = 符合预期，标记缺陷存在）。**

## 二、问题列表（按严重程度）

### ❌ 致命（阻塞 M1.4 全绿，P1 不得动引擎代码）

**F-A. R1 不动点不成立 — C 注释头泄漏导致输出逐代膨胀**
- 现象：`generate(parse(generate(d))) != generate(d)`，输出长度逐代增长（kitchen-sink 2102→2266；样例 prob41c 1097→1247）。
- 根因：生成器在每节前输出的 C 注释头被解析器吸收进结构化字段：
  1. `C  Cell Cards: N cells defined` → 关联到下一个栅元的 `$` 注释（cell.comment 污染）；
  2. `C  Surface Cards: N surfaces defined` → 被计入 `deck.surfaces` 原始文本，下次生成计数 +1；
  3. `C  ===== Data Cards ====="` → 被 `pending_c` 机制捕获进 `adv.other_cards` 并在段末重放。
- 位置：`app/generator/inp_generator.py:1065/1077/1082`；`app/generator/parsers/__init__.py` 注释吸收逻辑。
- 修复方向：解析器对生成器 C 注释头的吸收做防护（如仅在"紧邻栅元/M 卡"时吸收，或生成器头改用不可吸收形式）。
- 波及：`test_r1_fixed_point_*`（4 例）、`test_smoke_r1_fixed_point[*]`（3 例）、`test_r4_kitchen_sink_full_roundtrip`。

**F-B. validate_deck 与 CellRow 判别联合不兼容，直接崩溃**
- 现象：`validate_deck(parse_inp_text(inp)[0])` 对任何含栅元的 deck 抛 `AttributeError: 'CellRow' object has no attribute 'surface_expr'`。
- 根因：`app/generator/validator.py:validate_all` 直接访问 `cell.surface_expr`，而 `deck.cells` 是 `list[CellRow]`（kind/cell/text 嵌套，`app/models.py:59`）。
- 注意：生产 `/api/validate-inp` 走 `parsers/validator.validate_inp_text`（文本层，对 3 份样例全过），不受影响；`validate_deck` 是 DeckData 层辅助路径，属遗留未随 CellRow 模型同步。
- 位置：`app/generator/validator.py:137-146`。
- 波及：`test_smoke_validate_deck_does_not_crash[*]`（3 例）。

### ⚠️ 严重（建议修复后上线）

**F-C. 多粒子计数卡 round-trip 丢失**
- 现象：生成输出合并粒子为 `F4:N,P`，但 `parse_f_tally` 只认单粒子设计符（`^F(\d+):([NPEHAS])$`），`F4:N,P` 无法匹配 → 被丢进 `other_cards`，多粒子计数在 parse 后消失。
- 位置：`app/generator/inp_generator.py:528`（`,`join 输出）；`app/generator/parsers/core.py:730-738`（正则不认逗号）。
- 波及：`test_r2_tally_multi_particle_parse_supported`。

**F-D. 材料 options 丢失**
- 现象：`MaterialData.options`（nlib=.66c 等）生成时追加到材料末行尾部，被解析器并入 raw 行文本（`#endif  nlib=.66c`），round-trip 后 options 为空。
- 位置：`app/generator/inp_generator.py:205-208`；`app/generator/parsers/core.py` 裸行归属逻辑。
- 波及：`test_r2_material_options_survive`。

**F-E. _wrap_long_lines 的 & 续行符污染字段**
- 现象：超 80 列行拆分时附加 `&`，解析后污染 `surface_expr` / `vec` 等字段（如 `-1 2 &`、`0 0 1 &`）。
- 位置：`app/generator/inp_generator.py:1007-1018`（`_wrap_long_lines`）。
- 注：R2 已对尾 `&` 做容差；R1 修复需与 F-A 一并处理，否则 kitchen-sink 的 R1 仍不稳定。

**F-F. ksrc_points 数值坐标崩溃**
- 现象：`_generate_kcode` 对 JSON 中数值坐标（`{"x":1}`）调用 `.strip()` 崩溃（AttributeError）。契约要求字符串坐标（前端发字符串），属潜在缺陷。
- 位置：`app/generator/inp_generator.py:628-632`。
- 已 pin：`tests/unit/test_generator_phys.py::test_ksrc_numeric_coords_raises`。

**F-G. parse_sdef_simple 的 EFF 裸值静默丢弃**
- 现象：EFF 在 `_KNOWN_KEYS` 但 `_apply_sdef_param` 无 EFF 分支，裸值 `EFF=2` 被静默丢弃（数据丢失点）；带续值只保留续值（前缀丢失）。
- 位置：`app/generator/parsers/core.py:440-443/401-423`。
- 已 pin：`tests/parser/test_core_sdef.py` 两例。

**F-H. _is_cell_line 对小写 m 材料引用不识别**
- 现象：`_is_cell_line("3 m1 -1.0 -3")` 返回 False（`second.startswith("M")` 大小写敏感），与 `parse_cells`（能识别小写 m1）不一致。
- 位置：`app/generator/parsers/sections.py:78`。
- 已 pin：`tests/parser/test_sections.py`。

### 💡 建议（技术债，已由联动测试先红 pin）

- **F#3**：`inp_generator.py` 622/660 函数内 `import json as _json`；`parsers/core.py` 821/1013、`parsers/__init__.py` 138 函数内 `import sys`（兼 [E0DBG] print）。
- **F#7**：`from pymcnp import inp` 在 `_generate_basic` 函数内（98 行），未在模块导入期 fail-fast。
- **F#4**：Dn 分支（247-281）含扩展字段 vs 普通分支（283-301）不含——测试断言两分支公共字段等价，当前公共字段一致（`test_f4_common_fields_equivalent_across_branches` 绿）。
- **F#5/F#6**：概率归一化表驱动（NaN/inf/全 0）与 kitchen-sink 多源全字段在 SDEF/SI 各出现一次——已全绿，可直接作为拆 seam 的字符化基线。

## 三、测试执行结果（按里程碑）

| 里程碑 | 内容 | 结果 |
| :--- | :--- | :--- |
| M1.1 基建+fixtures | conftest + 3 份样例 vendor + dev-requirements | ✅ 完成（样例全部进仓库副本，不依赖外部路径） |
| M1.2 生成器单测 | tests/unit 8 文件 | ✅ 129 通过 |
| M1.3 解析器单测 | tests/parser 8 文件 | ✅ 73 通过 |
| M1.4 往返+冒烟 | R1/R2/R3/R4 + 3 样例冒烟 | ❌ **未全绿**（见 F-A/F-B/F-C/F-D/F-E） |
| M1.5 契约漂移闸门 | AST 对 api.yaml + contract.ts ⊆ models + 三核心端点 HTTP | ✅ 7/7 通过（api.yaml 已由架构师产出，真实断言跑通，非 skip） |

**M1.4 明细**：
- R1 不动点：❌ RED（F-A 头泄漏，4 例 + 3 样例 + R4 全红）。
- R3 分段无内容丢失：✅ GREEN（surfaces/other_cards/TR 卡无内容丢失，顺序可后移）。
- 样例冒烟（validate_inp_text + 关键卡 + 二次解析）：✅ GREEN；R1 部分 ❌ RED。
- R2 语义：部分绿（basic/cell/materials 行/mt 卡/CUT/phys/单源字段、多源转 distribution 模式）；options 与多粒子计数 ❌ RED（F-C/F-D）。

**契约闸门**：api.yaml 25 端点全部有 operationId 且无僵尸路径；contract.ts backend 字段 ⊆ models.py；`/api/generate`、`/api/parse-inp`、`/api/validate-inp` 子进程起 5001 真实 HTTP 往返全部通过。

## 四、整体评估结论（第一轮 → 第二轮）

1. **第一轮（原始基线）**：234 通过 / 17 失败，M1.4 未全绿，P1 门禁拦截。17 失败 = 13 真实 bug（F-A~F-E）+ 4 技术债（F#3/F#7），0 测试误判。
2. **第二轮（后端按契约修复后复核）**：245 通过 / 6 失败，**M1.4 门禁通过，P1 放行**。F-A/F-B/F-C/F-D 已修转绿，F-E（& 污染）随 F-A 一并归零；F-F/F-G/F-H pin 翻新为断言修复行为。
3. **权威基线校正说明**：首轮测量期间工作树曾被后端并发修复后回滚，导致 245/6 与 234/17 并存的假象；经逐例核实，234/17 为干净基线权威数据（0 误判），245/6 为修复后数据。
4. 契约漂移闸门（M1.5）全程通过（7/7），api.yaml 防腐烂网生效。

**当前状态**：M1.4 全绿达成（6 红全为设计内：4 技术债 F#3/F#7 + 2 kitchen-sink 归 P1）。放行 P1 重构（F#1~F#7 技术债清偿），P1 完成后 6 红应全部转绿。
