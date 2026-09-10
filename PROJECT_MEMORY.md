# 项目记忆文档（AI 速查手册）

> 最后更新时间：2026-09-10（**SDEF 源粒子演示可视化（TODO #6）落地**，已实现待提交：后端三深模块（`DistributionSampler` 分布抽样 / `source_sampler` 源编排 / `voxel_csg` 全宏体拆解）+ 端点 `/api/source-demo-sample` + 独立「🎬 演示源」3D 窗口；按 C810.pdf 权威语义**做全不降级**、有错就地报；门禁后端新单测 **49 passed** + tsc EXIT 0）。此前（2026-09-04，**后端拉起提速 + preview_cache 跨进程持久化**，已提交 commit 0a266cd；此前未提交 3D 功能已一并提交 f7fc2ed）。此前（2026-08-28，**v1.7.4**：3D 预览 MCNP 窗口裁剪修复 + U 分组侧边栏，**追加两项 Bug 修复——① disc STL 键错配（d8b6747，BEAVRS 燃料 pin 方块→真实圆柱）；② z 居中（5fafd1d，燃料棒/围板整体上移 230→位置正确，用户已复验确认），均仅重打包 sidecar 部署**；门禁后端 test_lattice(81)+test_api_contract(17) 绿 / 前端 vitest 527/527 / tsc EXIT 0）。此前（2026-08-27）：v1.7.4 上线（MCNP 窗口裁剪 + U 分组侧边栏，已打包部署 `D:\MCNP\MCNP输入卡生成器`；门禁后端 **85/85**（test_lattice+test_api_contract）/ 前端 vitest **527/527** / tsc EXIT 0）。此前（2026-08-24）：Wave 2a 后端 15 项修复**全绿**：pytest **703/0/0**（基线 686 + 新增 17）——项 2/4/5/9/13/15 + 项 14 剩余 + api.yaml cycle 契约 + R1 五夹具/kitchen_sink R4 不回退 + 契约闸门含 cycle HTTP 用例；详见 docs/backend-changes.md §AA。前端 Wave 2b 并行进行中，golden 已写盘全部可断言无 skip）。此前：格阵 fill 三阶段**最终复验全绿**：pytest **674/0** / vitest **466/0 无 skip** / tsc EXIT 0 / 契约闸门 15/15 / 空 STL 修复生效，用户指定 E2E 17/17 PASS，**建议放行统一提交**，详见 docs/qa-report-final.md —— **按人脑模型重组**（原「顶部横幅 + §8 流水混装」整理为「短期记忆 / 长期记忆」两区，完整流水外置 `docs/CHANGELOG.md`）。同日完成 **GQ/SQ 3D 预览修复 + 渲染后续增强 + OWEN 四项 + 参数扫描前端**：全部门禁绿（pytest **573/0** / vitest **358/0** / tsc EXIT 0）+ PyInstaller sidecar 重打包 + 打包版冒烟通过。
>
> **人脑模型组织说明**：
> - **◉ 短期记忆（工作记忆）**：只放"现在正在处理的事"——当前批次 / 工作区 / 待办。**容量小、变化快、随批次刷新**（人脑工作记忆约 7±2 项）。
> - **◉ 长期记忆（稳定存储）**：固化后不随批次变动的知识——**语义记忆**（是什么/为什么：身份/ADR/规则/目录）、**情景记忆**（发生过什么/经验教训：踩坑/里程碑）、**程序性记忆**（怎么操作：打包/测试手册）。
> - **记忆巩固规则**：批次结束 → 短期记忆区刷新；经验教训**固化**进长期记忆（§5 规则 / §6 踩坑 / §4 ADR）；详细流水**归档**进 `docs/CHANGELOG.md`（+ backend/frontend-changes.md + git log）。
> - **维护者**：项目经理（AgentTeams 记忆维护）。

---

# ◉ 短期记忆（工作记忆）—— 当前活跃上下文

> 只保留"正在处理"的信息。**批次完成后，本区随 CHANGELOG 归档一起刷新。**

## S1（当前批次）SDEF 源粒子演示可视化（TODO #6，2026-09-10，已实现，本次提交）

- **批次目标**：源（SDEF）界面加「🎬 演示源」→ 按 SDEF + SI/SP/SB/DS 抽样 **500 个粒子** → 独立 3D 窗口显示源的形状与分布（粒子点 + 方向短线 + 粒子类型基色 + 能量深浅），**不做输运**（只表"从哪发出、往哪飞"）。用户逐项拍板：**做全**（按 MCNP 语义，**不降级不近似**）、**有错报错**（MCNP 语义真错误 → 就地提示、不开窗）、**`D:\MCNP\MCNP6\C810.pdf` 为唯一权威**、**复用 voxel_csg 本地几何判定**（含宏体）、**用 codebase-design 深模块化**。
- **✅ 架构契约先行**：新增 `docs/contracts/source-demo-visualization.md`（照 ptrac-visualization.md 范式：目标 / 三个深模块接口 / 宏体 facet 拆解表 / 端点 / 错误清单 / 抽样语义覆盖清单 / 验收 / 非目标）。
- **✅ 模块 A `app/generator/distributions.py`（深模块，接口小）**：新增 `DistributionSampler` + `SourceSamplingError`——`sample(eid, rng)` 抽一个标量值 / `resolve_ds(eid, parent_value, parent_si)` DS 查表 / `weight_factor(...)` SB 偏倚权重补偿 / `resolve_ds_t(...)`。覆盖 SI **H（默认/""）/L/A/S**、SP **D/C**、内置函数 **-2/-3/-4/-5/-6/-21/-31/-41**、SB 偏倚、DS **H/L/S/T/Q**。
- **✅ C810 权威语义（pymupdf 提取 3-57~3-67 逐字核对，纠正三处臆测）**：① **SI 卡只有 H/L/A/S 四种**（`_SI_LETTERS` 里的 Q/T/F/V 是多余的，抽样器对它们报错）；② **SI H 的 SP 首条目必须是 0 占位**（`_pad(allow_leading_zero)`——首版顺序写错把前导 0 当第一个 bin 概率，已修）；③ **DS S/L 按离散索引取 J[idx]**（不是按值匹配 parent_si——POS 多点源传的是位置索引）。内置函数公式：Maxwell=Gamma(3/2,a)、蒸发=Gamma(2,a)、Watt=数值逆 CDF、-41 高斯 σ=a/√(8·ln2)、-4 高斯 σ=a/√2（b=-1→DT 14.08 / b=-2→DD 2.45）。**SI A 段内逆变换三元表达式踩坑**：`t = (...) / s if s > 0 else 0.0` 导致 s<0（递减密度段）样本全堆段起点 → 三角分布均值偏 0.08，改 `t = (...)/s` 修正。
- **✅ 模块 B `app/generator/source_sampler.py`（新，深模块）**：`sample_source(sdef_fields, distributions, geometry=None, *, n_particles=500, seed=None) -> dict`。**位置四路（MCNP 语义互斥）** = SUR 面源 / CEL 栅元均匀 / 笛卡尔 X-Y-Z / 柱坐标 POS+RAD+EXT+AXS；方向（体源各向同性 / 面源**余弦分布 p(DIR)=2·DIR** / 固定 DIR+VEC / DIR=Dn）；能量（固定 / SI 谱 / 内置函数 / **`ERG=FPOS Dn` DS 依赖链**）；权重；粒子类型（PAR→n/p/e/h/a/s/other）。
- **✅ C810 3-57~58 位置语义（纠正首版实现）**：**RAD = 半径**，位置在**半径 RAD 的球面/圆**上（**不是**球内/柱内均匀！首版写错）；实心球靠 **RAD 幂律 a=2**、圆柱靠 **a=1**（SI 无 SP 时按 C810 特殊默认补幂律，`_power_law_range`）；**EXT = 沿 AXS 距 POS 的距离标量**（可正负，`EXT=5` 是 z=5 的圆盘而非 ±5 圆柱）；**面源只支持平面/球面/spheroid**（C810 明示柱面源须用退化体源，遇到报错提示）。
- **✅ 模块 C `app/voxel_csg.py` 宏体拆解（路 A，三处受益）**：`surface_fn` 补 **BOX/RCC/RHP/HEX/TRC/REC/ELL/WED/ARB**——`_polyhedron_field`（凸多面体 f=max 各面朝外有符号距离：f<0 内部）+ `_rot60`（RHP/HEX 9 参绕 H 转 60° 推断 R2/R3）+ RCC/TRC/REC/ELL 解析式。约定 **f<0 = 宏体内部**（MCNP「负号=内部」语义，与既有 RPP/SPH 一致）。消费者三处：coverage_check（水密自检）/ overlap_probe（重合检测）/ source_sampler（CEL/SUR 判定）。
- **✅ 端点 + 契约**：`POST /api/source-demo-sample`（`api_server._handle_source_demo_sample` + `_prepare_source_geometry`）；**关键架构决策——几何解析留在 api_server 层**（复用 `parse_surfaces` / `Geometry.from_mcnp` / `resolve_cell_complements`（`#n` 补集展开）/ `voxel_csg` 构造 field 闭包），source_sampler 只消费 field、**保持纯 stdlib+numpy 不 import pymcnp**（首版 source_sampler 自解析几何写错了 pymcnp 接口 `pymcnp.inp.parse_surfaces`，已重构掉）。`api.yaml` 加 operationId `sourceDemoSample`（漂移闸门绿）。
- **✅ 前端**：`gui/src/source/SourceDemoRenderer.ts`（深模块：外壳 STL + 500 粒子 Points 点云 + 方向**短线** LineSegments，复用 `trackColors` 粒子类型基色×能量深浅 + `alignWorld` 归一化对齐 + `cameraParams` 自动取景 + `renderGate` 按需渲染）；`SourceDemoWindow.tsx`（独立窗口 + 右 300px 面板：统计/粒子类型计数/能量深浅图例/粒子透明度/方向线长度/外壳开关/↻ 重新抽样）；`windows.ts` 桥 `mcnp_win_source_demo`；`main.rs` `open_source_demo_window`（label `"source-demo"`）；`App.tsx` `#/source-demo` 路由；`SourceTab.tsx`「🎬 演示源」按钮（**先 `sourceDemoSample` 校验 → 有 error 就地红字、不开窗；ok 才写桥开窗**）。
- **门禁**：后端新单测 **49 passed**（test_voxel_csg_macrobody 12 / test_distribution_sampler 21 / test_source_sampler 16）；宏体改动回归 **21 passed**（coverage_check+overlap_probe+overlap_classify）+ test_distributions/test_validator_rules **43 passed** 零回退；契约漂移闸门绿（+ 2 HTTP 用例，需后端在跑）；前端 **tsc EXIT 0** + vitest windowRouteConsistency(5)/SourceDemoWindow SSR(1) 绿。
- **改动清单**：新增 `app/generator/source_sampler.py`、`docs/contracts/source-demo-visualization.md`、`gui/src/source/{SourceDemoRenderer.ts,SourceDemoWindow.tsx}`、`tests/unit/{test_source_sampler,test_distribution_sampler,test_voxel_csg_macrobody}.py`、`gui/test/source/SourceDemoWindow.test.tsx`；改 `app/generator/distributions.py`、`app/voxel_csg.py`、`gui/backend/api_server.py`、`docs/contracts/api.yaml`、`gui/src/utils/{api.ts,windows.ts}`、`gui/src/components/SourceTab.tsx`、`gui/src/App.tsx`、`gui/src-tauri/src/main.rs`、`gui/test/volume/windowRouteConsistency.test.ts`、`tests/integration/test_api_contract.py`。
- **⚠️ 待用户复验**：点「演示源」→ 点源/多点源/球壳（`RAD=2`）/实心球（`RAD=D1`+`SI 0 2`）/圆柱（`EXT=D2`）/能量谱/固定方向各形态是否符合预期；故意写错（如 `ERG=D7`）是否**就地红字且不开窗**；3D 窗口粒子分色 + 能量深浅 + 方向线是否与 PTRAC 窗口观感一致。
- **⚠️ 未做（用户确认不需要）**：契约 §7 里 `SourceDemoRenderer` 的 WebGL 单测 + `SourceTab` 按钮重组件测试（需 three.js / DeckContext 重 mock，投入产出比低）。**未打包、未升版**。

## S1（当前批次）源分布 v2 双态 + 原文模式值网格化（本会话/上一会话，已实现，未提交）

- **批次目标**：① 修 q1112 输入卡"程序导入-再生成后 MCNP 结果与原生不一致"根因——无字母 `SI` 行被解析时自动补成 `L`（MCNP 里无字母 SI 默认是 H 直方图，不是 L 离散列表）；② 分布编辑器导入后处于"原文模式(raw)"，行数据一多就整行挤成一个长输入框/一长串，观感差——改为**值拆网格**（每格一个值，MCNP 卡形态）。
- **✅ 根因修复（无字母 SI 不再回填 L）**：后端新增 `app/generator/distributions.py`（权威实现，纯 stdlib）——`parse_distribution_lines` 解析 SI/SP/SB/DS/SC，无字母 SI → type `""`（MCNP 缺省 H 直方图），绝不回填 `L`；`emit_distribution_entries` 发射（`editMode=raw` 时 rawText 逐字直通，round-trip 字节级一致；structured 规范重建）；同步 `inp_generator.py`（删旧 `_generate_structured_distributions` 内联逻辑）、`parsers/core.py`（改调 parse_distribution_lines，sdef_raw_text 停写转 sdef_distributions 权威）、`validator.py`（sdef_distributions 非空判定）、`models.py` AdvancedSettings 注释升级 v2 双态 schema、`api.yaml` DistEntry 补 editMode/rawText/si null。
- **✅ 前端 v2 双态**：新增 `gui/src/utils/distDual.ts`（TS 镜像，structuredToRawLines/rawToStructured/isRawMode/switchToRaw/switchToStructured/withStructuredEdit）；`DistributionEditor.tsx` raw⇄structured 切换、SI/SP 类型选择改为无字母省略项；`DeckContext.tsx` DistEntry/SiEntry/SpEntry 类型升级；`sourceTemplates.ts` SI_TYPES 加空值直方图省略、SP_TYPES 注明 D 裸值语义。
- **✅ 原文模式值网格化（本次 UI 修复）**：`DistributionEditor.tsx` raw 模式把**值部分拆成固定 8 列网格**（`repeat(8, minmax(0,1fr))`、monospace、右对齐，同 MCNP 卡 80 列/8 数据区形态，与导出卡一致），值多了自动换行不再拉长；行尾 `$` 注释从值中剥离、单独在网格下方编辑（清空注释自动去掉 `$`，改值/注释互不丢失）；SC 注释行/含标点行仍走 textarea。
- **✅ 测试**：`tests/unit/test_distributions.py`（25 项：解析/发射/同步/合并/D1 链/raw 直通）；`gui/test/distDual.test.ts`（13 项 TS 镜像）；`gui/test/distributionEditorRaw.dom.test.tsx`（4 项：值拆格、$ 注释分离、改值保留注释、清注释去 $）；相关旧回归 test_regress_sdef_sc_chain / test_core_data_cards 全绿。
- **门禁**：pytest（parser+unit+integration 相关）**46 passed**；vitest **587+4 passed**（73+1 文件）；tsc EXIT 0；vite build EXIT 0。改动未 commit、未打包。
- **⚠️ 待办**：本批含上一会话遗留未提交改动（分布 v2 双态整体），打包/提交前先确认工作区全部意图内改动（见下方 S2 改动清单）。

## S1（当前批次）AI 接入 inputcard-mcp + 快捷建栅元六棱柱/四面体 + 深模块化（本会话，已实现，本次提交）
- **批次目标**：① 让支持 MCP 的 AI 助手能在本地读写/生成 MCNP 输入卡；② 快捷建栅元扩到六棱柱(RHP)/四面体；③ IMP 改数值输入默认 0；④ 把 GeometryTab/Preview3D 重复的重合检测编排抽成深模块；⑤ 废弃一键打包、提示词做成页面。
- **✅ inputcard-mcp（AI 接入，本地 stdio）**：新增 `inputcard_mcp/` 包（`server.py`/`__main__.py`/`__init__.py`/`requirements.txt`，`mcp>=1,<2`），FastMCP v1 @tool。**无状态**：每次工具调用 AI 携带完整文本文档，修改型工具「收当前 INP → 返回新 INP」。**6 工具**：`read_document/generate_document/validate_document/list_section/patch_section/add_shape`（可写=8 语义段 basic/surfaces/tr_cards/cells/materials/sources/tally/advanced；add_shape 支持 rcc/rpp/sph/hex/tet）。**深接口**：read/generate/list/patch 统一按 **sections（asdict）口径**，一个 `patch_section` 全量覆盖一段（复用 api_server `_xxx_from_dict`，与 `deck_from_json` 同口径）；已删 6 个旧浅工具（list_cells/get_cell/update_cell/set_mode/list_materials/set_material）。**边界：不建模 textMode/raw override**（raw_override 是 generate 第二参数非 deck 字段，MCP 结构化路径会重写该段）。复用后端 `parse_inp_text`/`generate_inp_from_deck`/`deck_from_json`；**命名刻意避开 "MCNP" 子串**。
- **✅ 打包（随 sidecar）**：`gui/backend/mcnp_bridge.py` 加 `--mcp-server` 分派（仅此分支 import mcp/FastMCP，主 api_server 5001 路径不触碰 mcp）；`gui/mcnp_sidecar.spec` `_hidden` 加 `inputcard_mcp`/`inputcard_mcp.server`；打包版 `<部署>\python.exe --mcp-server` 可作 stdio MCP server（已用 MCP 客户端端到端验证自动发现全部 10 工具）。`gui/backend/api_server.py` 加公开别名 `deck_to_frontend_dict` 供复用。
- **✅ 快捷建栅元新增**：`gui/src/utils/quickCell.ts` 加 `HexConfig`/`TetConfig`/`hexRadialBasis`（RHP R1 轴向）、`generateHex`（RHP 宏体，结构同 RCC）、`generateTet`（4 顶点→4 平面，法向朝体内）；`quickCellPreview.ts` 加 `buildHex`/`buildTet`；`QuickCellForm.tsx` 加 hex/tet 形状按钮与表单（hex 同圆柱参数 / tet 输入 4 顶点）。
- **✅ IMP 数值化**：`QuickCellForm` N/P/E 由复选框改数值输入（默认 "0"，留空按基础页模式填 1）；`QuickCellContext.impN/impP/impE` 由 boolean→string；`cellBase` 相应改。
- **✅ 深模块 useQuickAddOverlap**：新增 `gui/src/utils/useQuickAddOverlap.ts`（3 getter + 统一写回 + 可选 onCheckFail，把后端请求体/appendCardText/applyQuickAddChoice 藏进实现）；`GeometryTab.tsx`/`Preview3D.tsx` 改用，删各自重复 fetch+决策逻辑。
- **✅ 一键打包废弃**：删除 `release.bat`/`README-release.md`/`scripts\release.ps1`；`README.md`/手动打包方法/PROJECT_MEMORY 改"仅手动打包，一键已废弃"。
- **✅ 提示词页面**：新增项目根 `AI接入.md`（与 README 同级，① 配置 ② 给 AI 的提示，合并原 AI接入提示词/部署配置；简单版 + System Prompt 版）；`docs/inputcard-mcp.md` 方式二指向该页。
- **✅ 门禁**：前端 vitest **554/0**（69 文件）；tsc EXIT 0；`gui/dist/python/python.exe --mcp-server` 端到端 list_tools 10 工具全通。后端零核心改动（api_server 仅加别名）。
- **改动清单**：`inputcard_mcp/`(新)、`gui/src/utils/quickCell.ts`、`gui/src/three/quickCellPreview.ts`、`gui/src/components/QuickCellForm.tsx`、`gui/src/components/GeometryTab.tsx`、`gui/src/components/Preview3D.tsx`、`gui/src/utils/useQuickAddOverlap.ts`(新)、`gui/backend/api_server.py`、`gui/backend/mcnp_bridge.py`、`gui/mcnp_sidecar.spec`、`docs/inputcard-mcp.md`(新)、`AI接入提示词.md`(新)、`README.md`、`docs/手动打包方法.md`、`requirements.txt`、删除 `release.bat`/`README-release.md`/`scripts/release.ps1`、`gui/test/quickCell.test.ts`/`quickCellPreview.test.ts`/`quickAddCheckWarn.test.ts`/`useQuickAddOverlap.test.tsx`(新)。
- **⚠️ 注意**：`inputcard_mcp/server.py` 顶层 import `mcp.server.fastmcp`、`generator.parsers`、`api_server`；源码 dev 用 `python -m inputcard_mcp`（需 PYTHONPATH 含项目根/app/gui-backend，server 已自加路径）。
- **✅ stderr-hang 修复（diagnostics，因果证实）**：mcp/anyio/httpx 等 logger 默认 INFO 会在**每个请求**都往 stderr 打一条；Windows 管道缓冲小（~12KB），`stdio_client` 把 stderr 重定向到 errlog 却无 task 读它 → server 阻塞在**写 stderr** → stdout 停 → MCP 卡死（官方客户端也卡 120s、只见 stderr 刷）。**因果实验**：不读 stderr 时第 26 请求卡死，**中途开始读 stderr 立即恢复**。**修复**：`_configure_logging()` 把 mcp/anyio/httpx/httpcore/starlette/uvicorn/h11 降到 **WARNING**（默认安静；`INPUTCARD_MCP_LOG=DEBUG` 放开排查，非法值回退）。验证：修复后**不读 stderr + 2000 请求 2.1s 全通、stderr=0B**；回归 3 用例；pytest **765/0**。

## S1（当前批次）后端拉起提速 + preview_cache 跨进程持久化（2026-09-04，已提交 commit 0a266cd；此前未提交 3D 功能已一并提交 f7fc2ed）
- **批次目标**：修"后端拉起等待时间过长"。根因=`gui/backend/api_server.py` 模块级 `import pymcnp.inp`（及 `inp_generator` 模块顶层 `from pymcnp import inp`）触发 `pymcnp/__init__` 急切导入 `Plot`/`Visualize`/`outp`，连带 `matplotlib`+`pandas`+`pyvista` → 后端启动 ~2.5s。
- **✅ 启动提速（commit 0a266cd，仅 `gui/backend/api_server.py`）**：① `_SURF_CLASSES` 改**线程安全惰性** `_surf_classes()`（首次 `parse_surfaces` 才 import pymcnp.inp）；② `generate_inp_from_deck` 从模块顶层改为 `_handle_generate` 内**按需导入**（符合本文件"重量依赖延迟到 handler"既有约定）；③ `main()` 加**后台预热线程**——启动即返回不阻塞，后台把 pymcnp 拉起来。效果：`import api_server` **2546ms→299ms**，真实拉起（端口就绪）~0.5s；`pymcnp` 不再随导入进入 `sys.modules`；预热后首个 `generate_inp_from_deck` **0.002s**。
- **✅ 缓存跨进程持久化（commit 0a266cd）**：`app/preview_cache.py` 的 STL 缓存原本 `tempfile.mkdtemp()` + 纯内存 `_index` → **跨进程重启命中不了**，每次重启首开同一 deck 仍重跑 FreeCAD。改为 `put` 写盘 `meta.json`（cells/freecad）+ `get` 内存 miss 时**磁盘恢复**；`__init__` 自动 `makedirs(base_dir)`。api_server 把两个缓存实例 `base_dir` 固定到 **`D:\MCNP\memory`**（用户约定，不存在则创建）：同一 deck 的 STL 结果**跨后端重启命中**，真正"只算一次、往后复用"。
- **✅ 提交拆分**：`api_server.py` 同时含本批 hunk 与先前未提交 hunk，用脚本按 hunk 特征切分成两个 patch，`git apply --cached` 分两次提交（先前功能 f7fc2ed / 本批 0a266cd），避免混入一主题。
- **⚠️ 关键约束（未改）**：`app/generator/inp_generator.py` 仍**模块顶层** `from pymcnp import inp`——这是 `tests/test_tech_debt.py` F#7 的 fail-fast 约定（pymcnp 缺失须导入期报错），**未违背**；`app/generator/inp_generator.py` 在 git 中无改动。故 pymcnp 的 import 是"**进程内一次**"、无法跨进程跳过（`.pyc` 只省编译省不了 import 执行），唯一彻底解是**后端进程常驻不重启**。
- **门禁**：单测+parser **654/0**；单测+关键集成（api_contract/tech_debt/roundtrip）**508/0**；`test_preview_cache` **11/0**（含 3 个新增跨进程恢复用例，含损坏 meta.json 兜底）；`test_tech_debt` F#7 绿；`D:\MCNP\memory\preview_cache`、`preview_cache_lattice` 已自动创建。
- **改动清单**：`gui/backend/api_server.py`、`app/preview_cache.py`、`tests/unit/test_preview_cache.py`（+ 提交的先前 3D 功能：`app/coverage_check.py`、`gui/src/volume/sliceExport.ts/SliceExportPanel.tsx`、`api.yaml`、`docs/contracts/lattice-coverage-check.md`、`tests/unit/test_coverage_check.py`、`tests/integration/test_api_contract.py` 等）。
- **⚠️ 待用户知**：`D:\MCNP\memory` 是本机新约定的后端可复用内容持久目录（不在仓库，不入 git）。若打包/换机需保证该目录可写。

## S1（当前批次）3D 预览重合检测 fill 修复（2026-09-04，已实现，未提交/未打包）
- **批次目标**：修 3D 预览重合检测在含 fill 卡、尤其 fill 套 fill（BEAVRS 全堆芯）时"几乎失效/乱报错"。根因=`Preview3D.runOverlapCheck` 请求只传 number/material/density/surface_expr，丢掉 `u/fill/lat/fill_grid/trcl/render/imp`，使后端三道防线全失效：①`_cell_u_of` universe 排除失效（pin 在本地原点互相比较→跨 universe 假重叠）；②`build_cells_data` 的 fill/graveyard 排除失效（格阵 cell/fill 容器/graveyard/无界 void 被当实体→无界 void 铺满 bound 盒全重叠）；③`_lattice_pin_fit_overlaps` 找不到 fill_grid→装配检测恒 0。
- **✅ 修复**：前端 `runOverlapCheck`+快捷建 `existingCells` 补传全部语义字段（Preview3D.tsx props 加 impN/impP/impE；GeometryTab.tsx 两处调用点转发 impN/impP/impE）；后端 `_handle_quick_add_check` 与 check-overlap 同口径用 `_cell_u_of` 过滤 universe 栅元。
- **✅ 验证**：17×17 卡 修复前 57 条假重叠→修复后 0 重叠/0 unresolved（universe/fill/graveyard 全排除）；BEAVRS 全堆芯 331 栅元→仅 10 个真实结构栅元（barrel/水/RPV）参与布尔，0 重叠。门禁：overlap 单测 15 / lattice+parser 92 / 集成 roundtrip+api_contract 42 / vitest **546/0** / tsc EXIT 0 / vite build EXIT 0。诊断脚本 `tools/diag_overlap_17x17.py`（可切 17×17/BEAVRS）。
- **改动清单**：`gui/src/components/Preview3D.tsx`、`gui/src/components/GeometryTab.tsx`、`gui/backend/api_server.py`（仅 `_handle_quick_add_check` 一处 hunk）、`tools/diag_overlap_17x17.py`(新)。
- **⚠️ 待复验**：17×17 / BEAVRS 全堆芯在 3D 预览重合面板应为 0 重叠；非格阵 deck（graveyard imp=0）重合检测不再被 graveyard 全盒假重叠污染。

## S1（当前批次）格阵 universe 覆盖完整性检测（红框预防）（2026-09-04，已实现，已提交 commit f7fc2ed）
- **批次目标**：修"格阵涂色只定义内部、漏定义外部 → 格元盒边缘红框"未能在编辑期暴露。根因=universe `U` 若只填内部实体（燃料芯块）、漏掉包围外部栅元（包壳/冷却剂/真空），格元盒边缘出现无定义区；该区与格元/外层 lattice 边界重合 → **MCNP 输运不报错、缺陷藏卡不显现**。本检测在**涂色时对当前选中 U 即时提示**（警告但允许保存）。
- **✅ 判定规则**：`U` 填满格元盒 ⇔ box 内任意点被 `U` 任一栅元覆盖（`covered(X)=OR(cell∈U, X∈cell)`）；**material=0 void 算覆盖**（定义了真空，符合 MCNP 语义）；**不含** fill/fill_grid 装配容器（其覆盖由被 fill 内容决定，不产实体几何）；box 内均匀采样（默认 **16³=4096 点**，毫秒级）统计 `uncoveredFraction`，超 `COVERAGE_TOL=0.01`→ 判未覆盖。
- **✅ 后端（无 FreeCAD）**：`app/coverage_check.py`（纯 stdlib+numpy，复用 `voxel_csg.surface_fn/eval_cell_field/_surface_tr`；采样点按 `EDGE_INSET_REL=0.005` 相对内缩**避开盒面共面**的 `>=0` 正侧误判）；`/api/validate-universe-coverage`（api_server）：入参 `surfaces/cells/tr_cards/lat/surface_expr/universe`，用 pymcnp 构造栅元 AST JSON（含 `#n` 补集展开，`Geometry.from_mcnp` + `resolve_cell_complements`）+ `surfaces_by_num`（携带 `*TRn` transform）+ `tr_cards`；格元盒范围用 `lattice.lattice_cell_extent`；响应 `kind/covered/uncoveredFraction/sampleCount/detailViable/unsupportedCells/message`（kind=empty/leaf/lattice，嵌套格阵不误报）。
- **✅ 前端**：`gui/src/components/LatticeEditDialog.tsx` 涂色时对 selectedU 即时检测提示（醒目标识、不阻断保存）；`gui/src/utils/lattice.ts` 相关。
- **契约 + 测试**：`docs/contracts/lattice-coverage-check.md`（待确认→落地契约）；`tests/unit/test_coverage_check.py`（覆盖/未覆盖/void/嵌套格阵/边界内缩等）；`tests/integration/test_api_contract.py` 增 API 契约用例。
- **改动清单**（随 f7fc2ed 提交）：`app/coverage_check.py`(新)、`gui/backend/api_server.py`(`_handle_validate_universe_coverage` + route)、`gui/src/components/LatticeEditDialog.tsx`、`gui/src/utils/lattice.ts`、`docs/contracts/lattice-coverage-check.md`(新)、`tests/unit/test_coverage_check.py`(新)、`tests/integration/test_api_contract.py`。

## S1（当前批次）*fmesh 能量沉积 + 3D 可视化（2026-09-04，已实现，已提交 commit f7fc2ed）
- **批次目标**：在现有 meshtal 体积可视化链路上支持 `*fmesh`（MCNP 能量沉积网格，结果 **MeV/g**）的解析与 3D 可视化，并落地待办 P1#5 里的「切面 + 导出（PNG/SVG + CSV）」。用户拍板：① 能量沉积开关放 **FMeshForm「类型」下拉**；②「有更好的就用更好的依赖」——本次判断复用现有链路+浏览器原生能力可达标，**未引入新依赖**。
- **✅ `*fmesh` 卡体（前端+后端）**：`app/models.py` `FmeshDefinition` 加 `fn_prefix: str`（""=通量 / "*"=能量沉积，照 `TallyDefinition.fn_prefix` 先例）；`app/meshtal/fmesh_parser.py` `_FAMILY_RE` 加 `^(\*?)` 前缀组（parse 设 fn_prefix / `_card_lines` 回放 `*FMESH14:N` / `_has_structured` 加 fn_prefix / CMESH 降级清 fn_prefix）；`gui/backend/api_server.py` `_fmesh_from_list` 传 fn_prefix；前端 `gui/src/volume/fmeshState.ts` `FmeshRow.fn_prefix` + `cardTextToFmesh`（前缀解析）/`cardLines`（发射）/`buildFmeshPayload`/`fmeshDefsToRows`；`FMeshForm.tsx` 类型下拉改「FMESH（通量）/ *FMESH（能量沉积 MeV/g）」→ 写 fn_prefix。
- **✅ 单位标签（MeV/g）**：`gui/src/volume/openVolume3DWindow.ts` 新增纯函数 `isDepositionTally(fmesh, tallyNumber)`（卡号匹配 + fn_prefix="*"）判定能量沉积 → 开窗桥带 `unit`（"MeV/g（能量沉积）" / "归一化计数"）；`ResultWindow.tsx` 读 unit 传 `VolumeControlPanel` → `ColorLegend` 单位标签（图例原有 unit prop）。检测**靠前端卡体匹配**（用户自建 `*fmesh` 卡主场景）；外部无卡体的 meshtal 默认「归一化计数」（不做 meshtal 头识别——MCNP 是否印标志未确认，避免依赖不确定格式）。
- **✅ 切面 + 导出（PNG/SVG + CSV）**：新增 `gui/src/volume/sliceExport.ts` 纯函数（`sliceFrame` 单轴切面 2D 热图 / `frameToCsv` 整帧体素 / `sliceToSvg` 矢量 SVG）+ `gui/src/volume/SliceExportPanel.tsx`（轴+切片滑块+canvas 预览+导出按钮）；`ResultWindow.tsx` 跟踪当前帧 `currentFrame` 供切面。全部浏览器原生（canvas.toDataURL/Blob），零新依赖。
- **门禁全绿**：后端 pytest **741/0/0**（基线 737 + 新增；`test_fmesh_parser` +2 个 `*fmesh` 用例 22 过；无回退）；前端 vitest **546/0**（69 文件全过，新增 fmeshState +2 / sliceExport +6 / openVolume3DWindow +3 = 11；**⚠️ 已知 flaky**：colorize 128³<50ms 偶发负载失败，隔离单跑绿，非回归）；tsc EXIT 0；vite build EXIT 0（产物 `dist/` 生成，此前 exit 1 是 PowerShell 把 chunk 大小警告当 stderr 假象）。
- **⚠️ 5001 端口**：pytest 前 terminate 打包部署版 sidecar（`D:\MCNP\MCNP输入卡生成器\python.exe -u backend/mcnp_bridge.py`，PID 10700 占 5001）释放端口。**若用户在跑打包版 GUI，需重启 `MCNP输入卡生成器.exe` 恢复后端**。
- **改动清单**（源码）：`app/models.py`、`app/meshtal/fmesh_parser.py`、`gui/backend/api_server.py`、`gui/src/volume/fmeshState.ts`、`gui/src/volume/FMeshForm.tsx`、`gui/src/volume/openVolume3DWindow.ts`、`gui/src/volume/ResultWindow.tsx`、`gui/src/volume/sliceExport.ts`(新)、`gui/src/volume/SliceExportPanel.tsx`(新)、`gui/src/components/OutputTab.tsx`、`tests/parser/test_fmesh_parser.py`、`gui/test/volume/fmeshState.test.ts`、`gui/test/volume/sliceExport.test.ts`(新)、`gui/test/volume/openVolume3DWindow.test.ts`(新)。
- **⚠️ 待用户复验**：类型下拉选「*FMESH（能量沉积）」→ 生成卡为 `*FMESH14:N`？导入 `*fmesh` INP → 类型下拉显示「*FMESH（能量沉积）」？开 3D 结果窗口图例显示「MeV/g（能量沉积）」？切面/导出 PNG/SVG/CSV 可用？F6/F7（cell 能量沉积）未做（非网格、本批范围外）。

## S1（当前批次）材料库深化（2026-08-30，已实现 + 已打包部署 v1.7.4）
- **批次目标**：把材料库从 97 种静态预设升级为用户可编辑、可迁移、可自检的材料资产。
- **后端**：`app/material_library.py` + `/api/material-library`(GET/save/delete/import/export)；持久化 `D:\MCNP\material\material_library.json`（D 盘不可写回落 `%APPDATA%\MCNP\material\`，原子写/防半写/损坏备份）；**custom + override** 模型；导入 JSON（无损）+ CSV（长格式带全 options/mtCard，按 key 分组/行交错正确/标量取首个非空），`dry_run` 预览 + 冲突三选（跳过/覆盖/改名）+ **内容完全一致自动跳过**（`apply_import` + `existing_entries` 比对）；xsdir 反向索引（缺库/后缀不匹配）+ 组成自洽校验（份额归一/正负号一致/密度/S(α,β)需含氢）。
- **前端**：`data/materialLibrary.ts`（LibraryEntry builtin/custom/override + `mergeLibrary` 保序合并 + API 封装 + 旧 localStorage 一次性迁移）+ `useMaterialLibrary` hook + MaterialEditDialog 贯通（handlePreset 查合并库 / 选中自动带出 MT卡与其他 / 修"用户预设选中无反应"bug / 「保存至材料库」/ `hidePreset`）+ MaterialLibraryPanel 管理面板（内置/我的材料/已修改三区、搜索/编辑/删除/恢复原始/导入导出/ZAID 明细标 ✓/✗）+ MaterialTab「📚 材料库」入口。
- **✅ 修复（复验反馈）**：① 编辑弹窗被父浮窗 `backdrop-filter` 裁剪 → `MaterialEditDialog` 用 `createPortal` 到 `document.body`；② 编辑保存后列表不刷新（`useMaterialLibrary` 用 `useMemo` 缓存模块级 `_cache`）→ 去 `useMemo` 每次读最新 `_cache`；③ 材料库内编辑隐藏预设区（`hidePreset` + `initialFormulaText`），footer「保存」直接写库；④ 生成 INP 时 **MODE（粒子类型）+ NPS（数量）卡移到数据卡段最末尾**（`inp_generator` 拆 `basic_tail`），其余 CTME/ACT/PRINT/NONU 留开头；⑤ 导入"内容一致 → 默认跳过"。
- **打包**：README 与 exe 同级放入（`release.ps1` 部署步骤加复制 + 自检）＋ `mcnp_sidecar.spec` `_keep_py` 加 `material_library.py`；**⚠️ 踩坑**：edit 改写 `release.ps1` 丢 UTF-8 BOM → Windows PowerShell 5.1 中文乱码解析崩溃，补 BOM 修复。
- **门禁**：后端 pytest **737/0**（含材料库 23 单测 先红后绿）+ 契约闸门含 5 新端点；前端 vitest 534/535（唯一失败 colorize 128³<50ms 已知 flaky，隔离单跑 18/18 绿）+ tsc EXIT 0 + vite build 成功；打包版 sidecar 材料库端点冒烟（list/save/export）过。
- **版本**：沿用 **1.7.4**（材料库为新功能，按 §5 应升版待上级指定；已按用户确认沿用）。
- **⚠️ 待用户复验**：编辑弹窗完整不被裁剪、保存后即时刷新、材料库内编辑无预设区、生成 INP 的 MODE/NPS 在末尾、导入相同自动跳过。

## S1（上一批次）lat=2 六棱柱 3D 预览 bug 修复（2026-08-28，源 `P:\dekstop\u233-comp-therm-001-case-6.i`，核心已修复，未提交）
- **批次目标**：修 U233-COMP-THERM-001 case 6 的 lat=2 六棱柱格阵（43×43 hex）3D 预览 bug —— handoff 第2项。**三个已知问题：① hex pin universe STL 空→前端回退 BoxGeometry 方块；② subPitch 误用硬编码 1.26；③ hex 格位全在正象限未居中。**
- **✅ 根因1（核心，已修复）**：`_build_one_universe(u=1/2/3)` 返回空。根因=容器 cell20 `surface_expr="10 -16 18 -23 -36 -37 38 39 #15 #16 #17 #18"` 含 **MCNP cell 补集运算符 `#n`**（挖控制叶片）。`_lattice_container_expr` 原样返回该表达式 → `_build_one_universe` 把它当作布尔裁剪表达式追加进 universe pin cell（`expr + 格元盒后缀 + 容器cell`），**FreeCAD 解析不了指向未定义 cell 的 `#` → 整次 build 失败 → 所有 universe STL 变空**。BEAVRS 容器 cell343 `-80 700 -730` 无 `#` 所以没踩此坑。
  - **修复**：`_lattice_container_expr` 返回前剥离 `#` 补集 token（`expr.split()` 过滤 `tok.startswith("#")`），容器裁剪只保留外边界曲面（`10 -16 18 -23 -36 -37 38 39`）。
  - **A/B 证实**：含容器裁剪 u=1/2/3 全空；去掉容器或剥离 `#` 后全部正常。**最小触发条件** = 补集引用**未定义** cell（`#99`）→ 构建失败；引用已定义 cell（`#9`）不触发（FreeCAD 能解析 `#9`）。
  - **验证**：`diag_hex.py` 源码/修复后端 → `universes STL keys=['1','2','3']`；STL 包围盒 z∈[-19.05,19.05]（z 居中，关于 origin 对称）；u=1 cell1 半径 ~0.267cm 圆柱 / u=2 cell8 ~0.621 圆柱 / u=3 cell14 填格元盒。
- **✅ 根因2（已修复）**：subPitch=`min(所有格阵pitch)`，但 `_subpitch` 硬编码初值 1.26（BEAVRS pin 间距）→ 单格阵（U233 只有 1 个 lat=2）时 `min(1.26,1.45034)=1.26` 错误。**修复**：`_subpitch=None` 初值，仅对实际格阵取 min pitch（单格阵=1.45034）；无格阵兜底 1.26。验证 fidelity.subPitch=1.45034。
- **✅ 根因3 hex 居中（已修复，2026-08-28）**：`expand_positions` 的 hex 分支 `hex_center(i,j,px)`（i/j 从 0..nx-1）未做 rect 那样的 `(i-(nx-1)/2)` 居中 → 格位全在正象限（x∈0..91.37、y∈0..52.75）。**修复**：所有 hex 消费点统一改 `hex_center(i-(nx-1)/2, j-(ny-1)/2, px)` 使格阵几何中心落原点（与 rect 一致）——① 后端 `expand_positions`；② 前端 `lattice.ts hexGrid`；③ 前端 `latticeInstances.ts gridCenter`（hex 分支）；④ 前端 `LatticePreview3D.tsx` hex 分支。配套：`estimateLatticeExtent` 的 hex 分支 maxX/maxY 改为**跨度 max-min**（不依赖绝对位置，居中前后 span 相同）；golden `positions.hex_2x2` 期望值重算为居中值；`_golden_positions_hex_fresh` 判断条件更新；`test_expand_positions_hex_ring_order` / `lattice.test.ts hexGrid` / `latticeInstances.test.ts expandPositionsRef` 断言更新。**验证**：diag_hex `x -45.69..45.69、y -26.38..26.38`（关于原点对称，此前 0..91.37 / 0..52.75）。**注意**：`hex_center`/`hexCenter` 权威公式（L1 golden 锁死）未改，只改调用处偏移。
- **回归测试（TDD 已验证红绿）**：`tests/integration/test_api_contract.py::test_http_preview_lattice_universe_stl_nonempty_container_hash`（LATTICE_CONTAINER_HASH_DECK，容器边界含 `#99` 补集，断言 universe STL 非空）。**红**：stash 修复后 `assert {}`（universes 空）；**绿**：修复版 18 passed。依赖 FreeCAD（skip if 无）。
- **门禁**：后端 pytest **99/0**（test_lattice 81 + test_build_cells_data + test_api_contract 18，含 hex 居中回归）；前端 vitest **527/527**；tsc EXIT 0。**⚠️ 5001 坑复现**：跑 test_api_contract 前须清 5001——本轮发现 5001 被**打包部署版 sidecar**（`D:\MCNP\MCNP输入卡生成器\python.exe -u backend/mcnp_bridge.py`，旧代码）占用，导致 pytest HTTP 连到旧后端、universes 空、subPitch=1.26（假象）。已终止该进程释放端口。
- **改动清单**：`gui/backend/api_server.py`（`_lattice_container_expr` 剥离 `#` + `_subpitch` None-init）、`tests/integration/test_api_contract.py`（新增 LATTICE_CONTAINER_HASH_DECK + STL 非空回归）、未提交的 `tools/diag_hex.py`。
- **⚠️ 用户注意事项**：本轮为释放 5001 端口已终止打包部署版后端（`...python.exe -u backend/mcnp_bridge.py`）。若用户在用打包版 GUI，需重启 `MCNP输入卡生成器.exe` 恢复后端。

## S1（当前批次）FILL 涂色编辑 U 分布颜色太少（2026-08-28，handoff 第3项，已修复已提交）
- **用户反馈**：涂色编辑 FILL 按 U 分组/分布只排 **12 种颜色**，太多 U 同色。希望改为函数随机生成（按 universe 稳定 hash 成色）。
- **方案**：`buildUniversePalette` 从固定 `UNIVERSE_PALETTE_12`（12 色轮换）改为 **golden-angle 色相散列**——按 universe 号数值升序去重排序，第 rank 个 U 色相 = `(rank*137.508)%360`，HSL(0.62/0.5) 转 hex。新增 `universeColorByRank(rank)` 纯函数（同 U 恒同色、前 N 个 U 色相最大程度分隔、任意多 U 不撞色）。`getUniverseColor` 签名不变（palette 缺失回退灰）。
- **验证**：500 个 U 全唯一色（0 撞色）；前 12 U 色相邻间隔 ≥20.1°（黄金角特性）；同 U 重复输入恒同色。
- **改动清单**：`gui/src/utils/lattice.ts`（`universeColorByRank` + `buildUniversePalette` 改用哈希；`UNIVERSE_PALETTE_12` 保留导出兼容）、`gui/test/lattice.test.ts`（调色板测试改 golden-angle 断言 + 新增"多 U 不撞色"用例 + import `universeColorByRank`）。生产消费点（LatticeEditDialog/Preview3D/Preview3DLattice/LatticeCanvas/LatticePreview3D）全部经 `buildUniversePalette` 自动受益，无需改。
- **门禁**：前端 vitest **528/528**（新增 1）；tsc EXIT 0；后端 pytest **81/0**（无回归，纯前端改动）。golden 无颜色断言未动。
- **⚠️ 说明**：golang golden 无颜色段，跨语言不受影响；材料色模式（getMatColor/materialMode）未动。
- **✅ 打包部署 v1.7.4（2026-08-28，含 lat=2 hex STL 空修复 + subPitch + hex 居中 + FILL 配色，仅这两批 bug 修复 + 配色，未升版恒 1.7.4）**：完整链路 vite build（8.3s）→ PyInstaller sidecar（python.exe 25,289,687B）→ 复制 binaries → **tauri build（34.5s，main exe 6,578,176B @ 7:44）** → **6.2 时效坑命中**（target/release python.exe 仍是旧 25,287,226B，手动覆盖为新 25,289,687B + _internal 2223 文件）→ 部署 `D:\MCNP\MCNP输入卡生成器`（main 6,578,176 + python 25,289,687 + _internal 2223）→ 冒烟通过：`python.exe` 直跑后端 5001 就绪 + `preview-lattice` U233 **universes STL keys=['1','2','3']**（非空）/ **subPitch=1.45034** / **x -45.69..45.69、y -26.38..26.38**（hex 居中，关于原点对称）。冒烟后已杀手动起的 sidecar（5001 释放）。⚠️ 部署版 GUI 未启动（侧边冒烟用 sidecar 直跑）；用户打开 GUI 时应用会自行拉起 sidecar。

（下一段 S1 记录 disc STL 键错配 + z 居中，见下方 `## S1（当前批次）disc 模式 STL 键错配 + z 居中`。）

## S1（当前批次）3D 预览 MCNP 窗口裁剪修复 + U 分组侧边栏（2026-08-27，v1.7.4，已提交 + 已打包部署）
- **批次目标**：① 修 BEAVRS 全堆芯 3D 预览"圆柱超出/重叠外壳"（用户反复反馈，最终定为"方法级 MCNP 窗口裁剪"而非"针对超壳打补丁"）；② 3D 预览侧边栏改为 U 分组（不显示组成 U 的栅元行，改为显示 U=n 组 + 保留 u 为空的未分组栅元）。**bug 修复批 + 新功能上线 → 版本升 1.7.4**（用户指定）。
- **✅ 方法级 MCNP「窗口」裁剪（commit 530ee8a）**：核心=实体 = `universe ∩ 格元盒 ∩ 容器 cell 几何`（MCNP 窗口机制：被填充 cell 是窗口，填充 universe 再大也被窗口几何裁剪）。此前用 OWEN disc 程序化圆柱（画格位圆心、忽略容器裁剪）→ 超壳/重叠外壳；且 STL 只按格元盒裁无限水 cell（u=30 `-3:3`=全空间）→ 格元盒在圆柱外时生成"圆柱外虚假水块"。
  - `app/lattice.py`：`_cell_box_outside_container`（格元盒与容器 cell 相交才保留）+ `compose_lattice_tree` 加 `container_bound` 参数；`_expand_lattice` 跳过格元盒完全在容器 cell 外的格位。
  - `gui/backend/api_server.py`：`_build_one_universe` 加 `container_expr`（`-80 700 -730`）裁剪 → STL 被容器 cell 切割；新增 `_lattice_container_expr` / `_lattice_container_bound`。
  - 前端 `latticeInstances.ts`：disc 丢弃程序化圆柱（buildDiscGeometry），改用后端容器裁剪 STL。
  - 撤销前端 `inOuter` 圆心裁剪（会误删格元部分在内的角 baffle）。overview 色块仍保留 inOuter。
  - **实测**：BEAVRS 超壳叶 **48 → 16**（仅 u=708-711 角 baffle，格元部分在内 → 显示成"格元∩圆柱"弧板，不超壳）；32 个 u=30 无限水（格元盒完全在圆柱外）被正确剔除。同批加了 subPitch（disc 半径用 min 格距 1.26，不再用根格阵 21.5 → 圆柱不再巨大重叠）。
- **✅ U 分组侧边栏（commit 7de14cd）**：`MaterialPanel.tsx` 新增 `UniverseCellList`（U 组条目 + 未分组栅元行 sub-CellList，`UniverseGroupRow` 接口）；`Preview3D.tsx` hasLattice 时组装 universeGroups（按 u 分组 count/代表色/allVisible）+ 未分组栅元（displayOrigIdx=u 空行），传 UniverseCellList；`toggleUniverseGroup(u)` 切换该 universe 全部栅元可见性。分 u 非空栅元不再作为独立行平铺。二维截面继续用原 CellList 不受影响。独立格阵窗口（Preview3DLattice）无侧边栏无需改。
- **版本号 1.7.3→1.7.4**：五处同步（tauri.conf.json / package.json / Cargo.toml / Cargo.lock / README 徽章，commit 39772a0）。
- **改动清单**：`app/lattice.py`、`gui/backend/api_server.py`、`gui/src/three/latticeInstances.ts`、`gui/src/components/Preview3D.tsx`、`gui/src/components/Preview3DLattice.tsx`、`gui/src/components/MaterialPanel.tsx`、`gui/test/latticeInstances.test.ts`（8 文件）+ 诊断脚本 `tools/diag_*.py`（diag_beavrs_z/diag_compose_time/diag_http_leaf/diag_leaf_dist/diag_pitch/diag_over/diag_boxout）。
- **门禁**：后端 `test_lattice`+`test_api_contract` **85/85**；前端 vitest **527/527**（无回归）；tsc EXIT 0。**⚠️ 已知 flaky**：colorize 128³ 计时 >50ms（负载偶发，隔离单跑绿，非回归）。
- **✅ 已打包部署 v1.7.4（2026-08-27）**：vite build → PyInstaller sidecar → 替换 binaries → tauri build（v1.7.4）→ **6.2 时效坑命中并手动覆盖**（tauri 增量编译未刷新 target/release sidecar，manual overwrite to new sidecar，python.exe mtime 23:03:13）→ 部署 `D:\MCNP\MCNP输入卡生成器` → 冒烟通过（5001 就绪 + BEAVRS `diag_over` 超壳叶 48→16 + `diag_pitch` subPitch=1.26）。⚠️ 待用户浏览器复验 3D 预览（超壳柱消失、U 分组侧边栏）。
- **✅ disc 模式 STL 键错配修复（2026-08-28，用户实测「显示与理论出入很大」；commit d8b6747；仅重打包 sidecar 部署，前端未改）**：BEAVRS 全堆芯 disc/轴向折叠预览**燃料 pin 全显示成 1×1×1 占位方块**而非圆柱燃料棒。根因=`_handle_preview_lattice` 按「每格阵 fill_grid 引用的 universe」建 STL，而 pin 格阵（600-614）引用的是**轴向列 universe**（u=116/124/131/140/150/160，cell 全带 `fill=`，被 `_build_one_universe` 的 `if _cell_fill: continue` 跳过 → 返回空）；但轴向折叠后**叶 universe 是径向 pin universe**（u=1/2/3/12/5/6，真实燃料棒/导向管/仪表管几何），从未被建 STL → 前端 disc 分支 `universeStl[u][cellNum]` 查不到 → 回退 `BoxGeometry(1,1,1)`（约 5.5 万 pin 全成方块）。**修复**：`_handle_preview_lattice` 在 `detail=='disc'` 时，收集未建 STL 的叶 universe（径向 pin），用 pin 格元盒（首个非根格阵 extent 盒）补建「universe ∩ 格元盒 ∩ 容器」裁剪 STL 放进对应格阵 `universes` → `universeStl[leaf.u][leaf.cellNum]` 命中真实几何。**验证**：源码/部署版各跑 `diag_universe_stl.py` —— 燃料芯块 u=1 cell=1 STL 包围盒 (0.78,0.78,460)→半径~0.39cm 圆柱；导向管 u=12 半径~0.50；冷却水 cell=4 填满格元盒 1.26（透明）。门禁 test_lattice(81)+test_api_contract(17) 绿。诊断脚本 `tools/diag_universe_stl.py`。
- **✅ z 居中修复（2026-08-28，用户实测燃料棒/围板「位置不对」；commit 5fafd1d；仅重打包 sidecar 部署，前端未改；用户已复验确认修复）**：`_build_one_universe` 的格元盒/容器裁剪产生 z∈[0,460]**底锚** STL，但前端把几何原点放在叶位置 z=230（格阵中心）→ 底锚 STL 放上去整体上移 height/2（燃料棒与围板浮空/位置不对）。修复：建好每个栅元 STL 后调 `_stl_recenter_z` 平移 z 使包围盒中心=0（几何关于 universe 原点对称，与 buildDiscGeometry 程序化柱/色块总览居中 box 约定一致）；仅平移 z 不动 x/y（围板格位几何按设计在格元盒内偏移）；空/ASCII/解析失败原样降级。**验证**：源码/部署版 STL 包围盒 z 由 [0,460]→[-230,230]；**围板未缺失**（u=700-711 共 64 块：4 直边 BAF_L/R/T/B×9 + 4 斜角 BAF_TL/TR/BL/BR×3 + 4 方角 SQ×4，成圈），与燃料棒同在正确高度。门禁 test_api_contract(17) 绿。诊断 `tools/diag_leaf_z.py`+`diag_baffle.py`。

## S1（当前批次）用户 3D 预览/格阵编辑器 7 项反馈修复（2026-08-25，源：`P:\dekstop\新建 文本文档 (2).txt`；门禁 vitest 516/0 + tsc EXIT 0 + 后端 test_lattice/test_build_cells_data 79/0）
- **批次目标**：用户对 3D 预览 + 格阵编辑器提 7 项反馈（0 分类逻辑确认 / 1-2 色块总览按钮位移+功能 / 3 色块坐标 / 4 独显 / 5 画布 XY 数学平面 / 6 子预览几何随定义+XYZ 轴）。**未 commit**（按惯例用户浏览器复验通过后统一提交）。
- **✅ 项0 分类逻辑确认（后端已符合）**：`app/lattice.py` `_expand_universe` 已按用户四点模型——① U 空/0 的栅元直接显示（实体叶 material≠0 / 纯 void 叶）；② 用 fill（含 fill="0"）的 U=0/空=装配容器不产 STL；③ 无 fill 的 U≠0=可复用 universe 装配组件（每 universe 一份 STL 复用）；④ 用 fill 的 U≠0=位置函数可嵌套递归（sub_by_u fill 图 DFS）。后端点 preview-lattice compose_lattice_tree 已有嵌套。**无代码改动**（仅确认 + 门禁验 79/0）。
- **✅ 项1/项2 色块总览**：`Preview3D.tsx` 标题栏的「色块总览」checkbox 移到右侧控制面板**「半透明查看」下方**（`lattice-overview-toggle`），仅 hasLattice 显示；文案随开关切换「按宇宙色块显示装配格位 / 显示真实几何」。原切换机制（latticeOverview → 重建 effect）保留且功能完好。
- **✅ 项3 色块坐标**：`Preview3D.tsx` + `Preview3DLattice.tsx` 的 overviewPositions 从「根格阵 positions（默认几何中心）」改为**详细可折叠时直接用叶实例绝对坐标**（与详细模式逐位对齐），自动总览（超限/嵌套 BEAVRS）才回落根格阵完整 positions。
- **✅ 项4 独显**：确认全部 5 处 WebGL 渲染器（Preview3D initScene / useThreeCanvas / QuickCellDialog / PtracRenderer / VolumeRenderer）均已 `powerPreference: "high-performance"`。**强制指定物理独显无法从 WebGL/WebView2 JS 侧实现**（渲染跑在共享的 `msedgewebview2.exe` 而非应用主 exe，Windows 按进程分配 GPU）。
  - **✅ 落地工具**：新增 `tools/set-discrete-gpu.ps1` + `tools/set-discrete-gpu.bat`（双击即用，UTF-8 BOM）；原理=把 WebView2 `msedgewebview2.exe` 与应用主 exe 写入 `HKCU\Software\Microsoft\DirectX\UserGpuPreferences\<exe>` = `GpuPreference=2;`（per-user 无需管理员）。本机实测写入→读回 `GpuPreference=2;` 成功（已验证后还原）。脚本自动识别应用 exe（排除 python/msedgewebview/unins 等）+ 搜索共享/固定版本 WebView2；NVIDIA 检测到则提示可在 NVIDIA 控制面板程序设置里再给 `msedgewebview2.exe` 强制选「高性能 NVIDIA 处理器」（驱动层更彻底）。参数：`-AppExeOnly`（只设应用 exe，避免影响其它 WebView2 程序）/ `-AppExe "..."` / `-PrinterOnly`（预览不写）。**注意**：Evergreen 共享 WebView2 设高性能会影响所有 WebView2 程序；改后需重启应用/电脑生效。**前提**：真正渲染仍由 WebView2 决定，注册表/驱动对 WebView2 无 100% 保证（微软 #5072 同结论），最彻底仍需 NVIDIA 控制面板程序级设置。
  - **✅ GPU 信息读出（几何标签页，FreeCAD 状态旁）**：新增 `gui/src/utils/gpuInfo.ts`（深模块：`detectWebGLGpu` 读 `WEBGL_debug_renderer_info`→UNMASKED_*, `classifyGpu` 判 nvidia/amd/intel/apple+核显/独显, `gpuStatusText` 文案）+ `gui/test/gpuInfo.test.ts`(5)。`GeometryTab.tsx` 顶部 useEffect 检测一次，在「曲面卡 & TR 变换」卡片底部操作行 **FreeCAD 状态旁** 显示 🎮 GPU: 名称·独显/核显（核显黄 + tooltip 提示跑 set-discrete-gpu.bat）。主界面与 3D 预览共享 WebView2 进程，可反映 3D 用卡。门禁 vitest 66 文件/522 全过 + tsc 0 + vite build 0。
  - **✅ 方向1 GPU 偏好设置（commit d4c8c18，已重打包部署 v1.7.3）**：GPU 芯片**精简为只显示「独显/核显」**（`gpuShortText`，用户要求不多信息）+ 旁置下拉「GPU 偏好▾」（高性能独显/省电核显/系统默认），调后端 `POST /api/set-gpu-preference` 写 `HKCU\UserGpuPreferences`（对 `msedgewebview2.exe` + 应用主 exe），alert「重启后生效」。后端 `app/gpu_pref.py`（`_PREF_MAP` / `find_msedgewebview2_exe` / `find_app_exe`（sidecar 同目录主 exe）/ `set_gpu_preference`(winreg) / `apply_gpu_preference`）+ api_server handler + api.yaml operationId `setGpuPreference`(tag system) + **spec `_keep_py` 加 `gpu_pref.py`**（`_import_app("gpu_pref")` 动态导入，PyInstaller 不会静态发现，漏则端点 500）。测试 `tests/unit/test_gpu_pref.py`(5, monkeypatch 不真写注册表) + `gpuInfo.test.ts` 补 `gpuShortText`。**门禁 vitest 66/523 + tsc 0 + pytest 713/0（含契约 22）+ 冒烟**：5001 就绪 + `set-gpu-preference` status ok targets=[msedgewebview2, 应用主 exe]（gpu_pref.py 已打进 sidecar）。**⚠️ 注意**：写注册表需重启应用/WebView2 生效；Evergreen 共享 msedgewebview2 设高性能会影响所有 WebView2 程序。
- **✅ 项5 画布 XY 数学平面**：`LatticeCanvas.tsx` 矩形 CSS grid 改**行 j 从下往上排**（首 DOM 行=最大 j 行），六棱柱 hex 改 `top: maxY - h.y`（Y 越大越靠上）→ X 右 / Y 上（数学平面），原来 Y 是屏幕向下。
- **✅ 项6 子预览几何随定义 + XYZ 轴**：`LatticePreview3D.tsx` 增 `buildAxes()`（AXIS_CONFIG：X 红/Y 绿/Z 蓝，数学/物理三维表达系，含正端字母 sprite）+ `pitchY` 参数；`LatticeEditDialog.tsx` 新增 `previewGeom` useMemo（rect 用宏体 L/W/H；hex mode B 用 hexPitch+genHexB.H、mode A 用 apothem×2+ |T−V|），由 `pitch:1` 固定改为真实几何尺寸，图形随定义变化。
- **改动清单**：`gui/src/components/Preview3D.tsx`、`Preview3DLattice.tsx`、`LatticeCanvas.tsx`、`LatticePreview3D.tsx`、`LatticeEditDialog.tsx`（全部前端，无后端新端点）。**门禁：vitest 522/0（66 文件全过，含 gpuInfo 5）+ tsc EXIT 0 + vite build 0 + 后端 test_lattice/test_build_cells_data 79/0**。
- **✅ 已提交 + 已打包部署 v1.7.3（2026-08-25，commit a13fde5）**：bug 修复批不升版（文件恒 1.7.3，五处一致）；打包链路 vite build → PyInstaller sidecar(25,279,636B) → 复制 binaries → tauri build（主 exe 6,577,664B）→ **6.2 时效坑命中并手动覆盖**（tauri 增量编译未刷新 target/release sidecar，手动覆盖为新版）→ 部署 `D:\MCNP\MCNP输入卡生成器` → 冒烟通过（5001 就绪 + `/api/xsdir-check` loaded:true count:7621，与基线一致）。产物三件套在位（preview_cache.py + vendor\geouned）。⚠️ 待用户实测 3D 预览（几何标签页看 GPU 信息读到独显/核显；3D 预览按前文项 1-3/5/6 复验）。

## S1（上一批次）格阵 fill 15 项用户实测反馈修复（2026-08-24，PM 全新接手；三阶段已提交 commit 2e38934）
- **批次目标**：用户浏览器实测格阵 fill 三阶段后提 15 项反馈（A 栅格编辑器 1-7 / B U 分组 8-11 / C 数据校验 12-13 / D 3D 预览 14-15）。修复后**用户在浏览器复验**（后端 5001、前端 1420 已运行），通过后**统一提交**（新 commit，不混入 2e38934）。
- **用户核心原则（不可违背）**：① MCNP 能输入多少参数，编辑器就该提供多少参数输入；② 格阵 cell 几何统一用宏体定义（LAT=1→RPP/BOX，LAT=2→RHP/HEX）。
- **⚠️ 3D 预览 STL 生成 cell 分类规则（用户已确认，2026-08-24，项 14/15 权威依据）**：① 被 fill 的 cell（fill 非空 **或** fill_grid 非空，含 fill="0"）=装配容器，自身不产 STL（无论有无 u、material 是否 0）；② 递归装配 universe 直到叶级实体 cell（material≠0 且无 fill）才产 STL；③ 普通实体 cell（material≠0 无 fill 无 u）→直接产 STL；④ 纯 void（material=0 无 fill 无 u）→参与 STL（项 14 删 void 约束唯一适用范围）；⑤ graveyard（imp=0）→不渲染；⑥ universe U 几何=所有 u=U 的 cell 的 STL 集合。**关键缺口：build_cells_data 当前只 skip fill_grid 非空格阵 cell，没 skip `fill=U` 单值 cell——删 void 后这类 cell 变实体块（"大紫方块"根因），必须补 skip 任何带 fill 的 cell。**
- **🔄 Wave 1 首轮三 agent 被用户停止（2026-08-24）**：因项 14 方向需按上述确认规则纠正，已**重新派发全部 Wave 1**：后端→**项 14 纠正版**（build_cells_data 补 skip 任何带 fill 的 cell + void 只对真·空 void 生效 + graveyard imp=0 不渲染 + STEP 导出保持 include_void=False + 补单值 fill/纯 void/graveyard 回归测试）；架构师→设计增量（项 14/15 按确认规则）；前端→**项 8/10/11**（U 分组默认 ON+localStorage 持久化键 `mcnp_groupbyu_v1` / 无 U cell 进「未分组」组不被吞 / 拖拽改 U 弹回根因=onDropOnGroup 只 setCells 未 patch deck→deck 同步覆盖回弹，修复=改 u 同时 patch deck + DOM 测试）。
- **架构师交付物**：`docs/contracts/lattice-fix15-design.md`（跨语言锁死：hex 排列权威公式 / -N:M 范围映射 / 宏体自动生成卡 / cycle 响应契约 / 项 12 raw 压缩决策 / 项 15 3D 装配路径 / 3D 分类规则；golden 权威值 + api.yaml diff **只写入设计文档，不落盘 golden/api.yaml/代码**防实现前弄红门禁）。
- **✅ 后端项 14 完成（Wave 1，2026-08-24）**：build_cells_data 补成 **skip 任何带 fill（含 fill="0"）或 fill_grid 的 cell**（装配容器不产自身 STL，修"大紫方块"）+ **graveyard（imp 任一首 token 0）skip**；void 参与 STL 仅限真·空 void（material=0 无 fill 无 u）。include_void 边界：preview-3d / 截面 / check-overlap / quick-add-check=True；STEP 导出与格阵 universe 裁剪保持 False。新增 `tests/unit/test_build_cells_data.py`（12 用例，子进程不 import api_server）；**pytest 686/0（基线 674+12）零回退**，HTTP 契约闸门 + FreeCAD 测试未 skip。单值 fill skip 已落实；递归展开由 /api/preview-lattice compose_lattice_tree 处理，本批未改该路径。api.yaml/golden 未动（留给 Wave 2）。
- **✅ 前端项 8/10/11 完成（Wave 1，2026-08-24，未 commit）**：项 8 分组默认开+localStorage 持久化（键 `mcnp_groupbyu_v1` 初始 true，读 useState+写 useEffect，不跨标签页同步）；项 10 无 U cell 进「未分组」兜底组（哨兵 `UNGROUPED_U=-1` 数值升序排最前，组头「未分组 · N 栅元」，新增 `isUngroupedU`/`applyRegroupToRows` 纯函数收敛组件重复映射；拖到未分组组头=清空 u）；项 11 弹回修复（**根因确认**=onDropOnGroup 只 setCells 未提交 deck → deck 同步 useEffect 覆盖回弹；修复=改 u 同时 `patch({cells: localToDeckCells(...)})` 提交单一权威，渲染不回弹）。测试 universeGroups 6→12 + 新 `gui/test/geometryGroupDrag.dom.test.tsx`（4，jsdom：默认分组视图/localStorage 保持/拖 cell→组头 u 更新+不回弹+deck patch/拖未分组清空 u）；既有 T1 `geometryBatchEditReorder.dom.test.tsx` 因默认开显式关分组（localStorage false）保持扁平行语义。门禁 vitest **476/0 无 skip**（基线 466+10）/ tsc EXIT 0 / vite build EXIT 0。改动清单 docs/frontend-changes.md。
- **⚠️ 前端待办（并入项 15）**：void 相机风险——preview-3d include_void=True 后巨型边界 void（如 so 1000）撑大包围盒拉远相机。归前端，相机取景时排除巨型 void 或限制 void STL 范围。Wave 2 前端项 15 必做。
- **✅ 前端项 8/10/11 完成（Wave 1，2026-08-24）**：项 8=groupByU 默认开 + localStorage `mcnp_groupbyu_v1` 持久化；项 10=`UNGROUPED_U=-1` 哨兵未分组兜底组（升序排最前，文案「未分组 · N 栅元」「拖拽栅元到此行清空 U」，raw 行不进组）；项 11=根因 onDropOnGroup 旧实现只 setCells 本地改 u 未提交 deck→被 deck→local 同步覆盖回弹，修复=改 u 同时 `patch({cells: localToDeckCells(...)})` 单一权威，groupHandlers.onMouseUp 接线确认正确。新增 `universeGroups.applyRegroupToRows` 纯函数深模块；测试：universeGroups 6→12、新增 `geometryGroupDrag.dom.test.tsx`(4)、geometryBatchEditReorder 显式关分组保扁平行语义。**vitest 476/0 无 skip（基线 466+10）/ tsc 0 / vite build 0**。api.yaml/golden 未动。
- **✅ 架构师设计增量完成（Wave 1，2026-08-24）**：`docs/contracts/lattice-fix15-design.md`——15 项齐备 + §2 跨语言锁死 L1-L9 + §4 api.yaml 唯一契约变化（项 13：preview-lattice 响应 limit enum 增 "cycle" + cycle boolean + chain array）+ §6 测试清单 + §7 分派。**关键发现（项 5）**：当前 hexCenter 按奇数行横向错半格（pointy-top）但格元几何是顶点+X（flat-top）→ 排布错误根因；权威公式 `x=i·p·√3/2, y=j·p+(i%2)·p/2`（奇数列纵向错半格）。**显示歧义**：用户期望 [2,3,2] 是点朝上取向；权威顶点+X 下水平行长为 [1,2,1,2,1]——本批按权威实现（设计默认），90° 旋转显示待用户确认另排期（已抛给用户）。
- **Wave 2 已并行派发（2026-08-24）**：
  - **后端 Wave 2a**（项 2/4/5/9/13/14 剩余/15 后端 + api.yaml + pytest）：lattice.py（_dir_counts / _rhp_extent 9 参 Rodrigues 推断 / hex_center 权威公式 / detect_fill_cycle / _expand_universe void leaf+fill0 skip）、api_server（_build_one_universe include_void=True+_cell_fill skip、preview-lattice cycle 透传、sub_by_u graveyard 过滤）、inp_generator+banners+parsers（C  U-group U= 注释，deck.universeComments）、**api.yaml 落地**；golden 只读断言（未产出段 skip，不改 golden）。
  - **前端 Wave 2b**（项 1/2/3/4/5/6/7/9 UI/12/13/15 + golden 写盘 + vitest）：LatticeEditDialog 4 步状态机（延伸并入第 0 步 + 调色板同屏第 2 步）、方向块数 -N:M、autoGenMacrobody 互斥 + MacrobodyPreview、RHP 双模式表单、hex 权威公式 + LatticeCanvas/LatticePreview3D/latticeInstances 同步、collectFillUniverses、组头双击编辑 + universeComments、compressRaw + 体积告警、detectFillCycle 保存阻止、Preview3D 默认装配视图路由 + void 叶透明 + 取景排除；**golden 唯一写盘人**（dirCounts/macrobody/rhpMacro/collectFillUniverses/compressRaw/cycle/assembly + hexCenter/positions.hex 重算）。
  - 分工防冲突：frontend 写 golden 后端读（未产出 skip）；api.yaml 后端落地前端不碰；前后端按图纸权威值逐字实现（L1-L9 锁死）。
- **✅ 前端 Wave 2b 完成（2026-08-24）**：LatticeEditDialog 6→4 步（0 类型尺寸+延伸/1 材料曲面/2 画布+调色板同屏/3 保存）+ 新增 `MacrobodyPreview`（lattice-extent 拿盒 + buildHexPrism/RPP 线框）；项 5 hex 权威公式落地（顶点+X flat-top，L1 锁死；LatticeCanvas 格元盒 width=2pitch/√3 height=pitch；latticeInstances 同步；**90° 旋转未做待用户确认已记录**）；项 15 Preview3D 默认装配路由（fill/fill_grid→Preview3DLattice）+ void 叶透明+不取景+装配视图内不请求 preview-3d；项 9 GeometryTab 组头双击内联编辑→patch universeComments + DeckContext 加 universeComments 可选字段 + inp_generator 已按 U 连续段插 `C U-group U=<n>: <text>` + core.py `extract_universe_comments`；项 2 `rangeFromDirCounts/dirCountsFromRange`；项 3/4 `autoGenMacrobody`（rect→RPP/hex→RHP）+ `rhpFromCenterRadiusHeight/rhpFromThreePoints/rhpCard`；项 7 `collectFillUniverses`；项 12 `compressRaw`（nR 回缩）+ `latticeVolumeWarning`（>64KB/8000 格位告警）；项 13 `detectFillCycle`（前端判环保存阻止）。**golden 写盘**：新增 dirCounts/macrobody/rhpMacro/collectFillUniverses/compressRaw/cycle/assembly 段 + 重算 hexCenter/positions.hex + validate 追加 macro 样例；后端只读断言可消费不再 skip。**门禁 vitest 512/0 无 skip / tsc 0 / vite build 0**。与后端 lock 确认：assembly golden 样例已修正（window_cell.fill=1 与 expected_leaves 吻合）；compressRaw nR 语义与 parse_fill_entries 一致；hexCenter/positions.hex 双端逐位一致。
- **✅ 后端 Wave 2a 完成（2026-08-24）**：项 2 `_dir_counts_from_range`；项 4 `_rhp_extent` 9 参推断（Rodrigues 绕 H 转 60°）+ `_validate_rhp_params`（参数数 9/12/15/18、|H|>0、R1⊥H、R2·R3 60° 旋转语义）；项 5 `hex_center` 权威公式（顶点+X flat-top，既有用例期望已同步）；项 9 universe_comments 全链路（models/banners/inp_generator U 连续段插 C 注释/parsers extract/serialization）；项 13 `detect_fill_cycle`（DFS）+ compose 入口判环 status=cycle + **api.yaml limit enum 增 cycle + cycle/chain 字段 + 契约闸门 HTTP cycle 用例**；项 15 `_expand_universe` fill="0" 装配容器 + void 叶；项 14 `_build_one_universe` include_void=True + skip 单值 fill cell。**pytest 703 passed/0 failed/0 skipped（基线 686+17）**；R1/R4 五夹具保持绿；契约闸门含 cycle 用例全绿；golden 后端消费全部可断言无 skip，未改 latticeGolden.json。
- **⚠️ 5001 端口残留坑（Wave 2a 实测，已记 §6）**：pytest 曾遇 5001 被残留旧 server（PID 4776，跑旧代码无 cycle 判环）劫持 → cycle 端点 500 递归错误；杀 PID 复绿。**被杀的是浏览器测试起的 5001 后端——用户浏览器复验前需重新起新代码后端（Wave 3 测试自行起测试实例；复验前 PM 起新 5001 或提示用户重启）**。
- **Wave 3 测试已派发（2026-08-25）**：独立复跑全量门禁（pytest 703 基线 / vitest 512 / tsc / vite build / 契约闸门含 cycle HTTP / 跨语言 golden L1-L9 无 skip / R1 五夹具 / R4）+ 15 项核验 + 风险点独立验证（5001 劫持、void STL、cycle 端点、U 注释 R1）→ 产出 `docs/qa-report.md`。致命清零后交用户浏览器复验（含确认六棱柱取向 [1,2,1,2,1] vs [2,3,2]）。
- **⚠️ 用户复验缺陷（2026-08-25，已派后端修复）**：格阵 FILL 输出未按行分隔——format_fill_cards 用 _pack_entries 按字符宽度贪心打包（17×17 约 37 格/行），MCNP 规范应**每行一个 j 行**（矩形格阵每行 nx 个条目，17×17 → 每行 17 个、17 行）。修复方向：format_fill_cards 改 **cells 结构化展开优先，按 dims[0]（nx）分组每行输出**（行主序 i 最快；某行超 75 字符再拆子行）；**raw 仅 cells 空时兜底（不再 raw 优先）**；lat=2 六棱柱保留宽度打包或另处理；MAX_EXPANDED_ENTRIES 截断场景（cells 不完整）建议回落 raw。更新 test_lattice.py format_fill_cards 用例（raw 优先/范围剥离断言改新语义）；pytest 确认 R1 五夹具固定点 + kitchen_sink R4 不回退（基线 703/0）。
- **✅ QA 报告草稿已产出（测试，2026-08-25）**：`docs/qa-report.md` 标注 ⚠️ 待重验 + 新增 §8 待重验清单（format_fill_cards 新语义用例 / R1 五夹具 parse→gen→parse 字节全等 / kitchen_sink R4 / 全量 pytest ≥703/0）；vitest/tsc/build/契约闸门/golden 不受影响。**协调流程已定：后端修复完成 → PM 通知测试重验 → QA 定稿 → 用户浏览器复验（起新 5001 后端 + 确认六棱柱取向）**。
- **🔴 优先级最高：拖拽改 U 仍未实现（用户复验两次确认，2026-08-25，已派前端）**：拖 cell 到 U 组头 → CellEditDialog 高级参数「U 宇宙」u 字段未变。前端 agent 排查修复：① onDropOnGroup 是否真触发（groupHandlers 落点命中/mouseup 分派/事件冒泡抢占）；② 改 u 后写 deck + 回填 local cells + CellEditDialog 读新 u 链路；③ 可能原因=浏览器缓存旧 bundle（用户硬刷新 Ctrl+Shift+R 重测，但不只归因缓存）/ 拖拽落点/渲染回弹残留；④ 补 vitest 全链路（拖组头→cell.u 变→deck.cells 更新→CellEditDialog 显示新 u，扩 geometryGroupDrag.dom.test.tsx）。门禁 vitest 512/0 不许回退 + tsc + build。**此项优先于其他收尾，前端完成后 PM 安排用户浏览器复验**。
- **✅ 前端 Wave 2b 完成（2026-08-24，未 commit）**：按图纸施工前端全部项 + golden 写盘 + vitest。项 1/6 4 步状态机（0 类型尺寸+延伸 → 1 材料曲面 → 2 画布涂色+调色板同屏 → 3 保存）；项 2 方向块数 -N:M（`rangeFromDirCounts`/`dirCountsFromRange`）；项 3/4 宏体自动互斥 + RHP 双模式 + `MacrobodyPreview`；项 5 hexCenter 权威公式（顶点+X flat-top，`x=i·p·√3/2, y=j·p+(i%2)·p/2`）+ `inHexRing` 角位 + LatticeCanvas 格元盒 + estimate 同步；项 7 `collectFillUniverses`；项 9 组头双击内联编辑 patch `universeComments`；项 12 `compressRaw` 压缩 + 体积告警；项 13 `detectFillCycle` 保存前判环阻止；项 15 Preview3D 默认装配路由（fill/fill_grid → Preview3DLattice）+ void 叶不取景（`nonVoidFrameLeaves`）。**golden 写盘**：新增 dirCounts/macrobody/rhpMacro/collectFillUniverses/compressRaw/cycle/assembly 段 + 重算 hexCenter/positions.hex + validate 补宏体样例；**assembly 段按后端推荐修正**（window_cell.fill "10"→"1"——设计样例 sub_by_u["10"].fill="" 无指向叶 101 的边，原样例内部不一致）。**⚠️ 项 5 显示歧义待确认**（用户期望 [2,3,2] 点朝上；本批按权威顶点+X 蜂窝实现，未做 90° 旋转，另排期——已记录 docs/frontend-changes.md）。门禁 vitest **512/0 无 skip**（基线 476+36）/ tsc EXIT 0 / vite build EXIT 0。改动清单 docs/frontend-changes.md。
- **✅ 后端 Wave 2a 完成（2026-08-24，未 commit）**：按图纸施工后端全部项。项 2 `_dir_counts_from_range`（-N:M 映射，L=-a/R=b，dims=L+R+1 自洽）；项 4 `_rhp_extent` 9 参推断（Rodrigues 绕 H 转 60°）+ `_validate_rhp_params`（参数数∈{9,12,15,18}、|H|>0、R1⊥H、R2/R3 连续 60° 旋转语义；`"10 rhp ... 2 0.5 0 0"` 9 参合法仍过）；项 5 `hex_center` 权威公式（顶点+X flat-top，x=col·p·√3/2, y=row·p+(col%2)·p/2）+ 既有测试期望同步 + golden stale-skip；项 9 `universe_comments` 全链（models DeckData + deck_from_json/序列化 + banners 冻结词汇 `universe_group_banner` + `_generate_cells` 按 U 连续段插 `C  U-group U=<n>: <text>` + core.py parse_cells skip + extract + parse_data_cards 排除 + parse_inp_text 吸收，R1 新夹具字节不动点）；项 13 `detect_fill_cycle` DFS 判环 + `compose_lattice_tree` 入口判环（status="cycle" 不递归）+ handler 透传 cycle/chain（compose `cycle`=链 → 响应 `cycle`=bool + `chain`=数组）+ graveyard 过滤 sub_by_u + **api.yaml limit enum 增 cycle + cycle/chain 字段** + 契约闸门 HTTP cycle 用例；项 15 `_expand_universe` fill="0" 装配容器 + void 叶（计入 count）+ 单值 fill 装配链。项 14 剩余：`_build_one_universe` include_void=True + skip 单值 fill cell。**门禁 pytest 703/0/0**（基线 686 + 新增 17，R1 五夹具/kitchen_sink R4/契约闸门含 cycle 用例全绿；golden 已写盘全部可断言无 skip）。⚠️ 5001 曾被残留旧 server 劫持（跑老代码致 cycle 递归 500）——已杀 PID 4776 后复绿（端口劫持老坑复现，见 §6）。改动清单 docs/backend-changes.md §AA。
- **✅ 用户复验缺陷修复（格式分隔，2026-08-25，未 commit）**：格阵 FILL 输出未按行分隔 → `format_fill_cards` 重写：cells 优先结构化展开按 dims[0]=nx 每行分组（每行一个 j 行，17×17 → 每行 17 条目/17 行）；行超 75 字符按宽度拆子行（token 序不变）；raw 仅 cells 空或截断（len<dims 乘积）时兜底；lat=2 同按 nx 分组（MCNP 合法）；translated 不变。**pytest 706/0/0**（基线 703 + 3），R1 五夹具固定点 + kitchen_sink R4 不回退（行分组不改变 token 序，生成确定性）。改动清单 docs/backend-changes.md §AB。
- **Wave 2（等架构师设计落地后派发，并行）**：后端=项 2/4(validate)/5/9(生成 C 注释)/12(体积评估+压缩决策)/13(cycle)/15(装配数据) + golden/pytest/api.yaml 落地；前端=项 1/2/3/4/5/6/7/9 UI/12(保存 raw 全路径)/13(保存前判环+提示)/15(主 Preview3D 接通 preview-lattice 装配) + golden/vitest 落地。
- **Wave 3**：测试全量门禁（pytest 674 基线 / vitest 466 基线无 skip / tsc EXIT 0 / vite build / 契约闸门 15/15 / 跨语言 golden）+ 产出 qa-report，致命清零后交用户浏览器复验。
- **15 项速览**：1 延伸方向并第一页；2 方向块数→-N:M；3 自动生成(宏体)vs手填互斥+子预览；4 六棱柱全量参数(RHP/HEX 三点+高/中心+外接半径+高、环R、轴向k、6+2平面备选)；5 hex 排列修正(pointy-top +X/交错半格/行长交替)；6 调色板同屏；7 调色板=void∪fill表∪deck 宇宙；8 分组默认开+保持；9 分组头可编辑→INP 前 C 注释；10 无 U cell 进未分组；11 拖拽改 U 弹回修复；12 raw=cellsToRaw 全路径+大格阵体积告警/压缩；13 循环嵌套检测 status="cycle"+链+前端阻止；14 void 参与 STL；15 格阵按 FILL 装配显示（主 GUI 3D 接通 preview-lattice）。

## S1（上一批次）格阵 fill 阶段3：3D 预览实施中（2026-08-24，阶段1/2 已验收；阶段3 曾因两 agent 被用户停止中断，已按用户指示重新派发）
- **⚠️ 中断与重派记录**：阶段3首轮两实施 agent 被用户停止（后端 lattice.py/api_server.py 未落盘阶段3代码；前端 latticeInstances.ts 已落盘但可能不完整）。用户明确指示**重新派发** → 已重派后端（全新 agent）+ 前端（全新 agent，先核验 latticeInstances.ts 完整性，不完整补全/重写）。架构师阶段3契约定稿作唯一图纸（含嵌套 fill 递归：MAX_LATTICE_DEPTH=8 / MAX_TOTAL_INSTANCES=500k / DETAIL_MAX_INSTANCES=20k 降级总览；BEAVRS 实测 2 层嵌套+叶级，全堆芯默认总览）。
- **5001 端口占用已由用户手动清除**（旧打包版 sidecar 已关）→ 契约闸门应复绿；测试已接续复跑确认。
- **✅ 前端阶段3完成**（2026-08-24，重派后，未 commit）：新建 `gui/src/three/latticeInstances.ts`（双模式 `buildLatticeInstances` / `parseTrclDeg` rect mod90/hex mod60 / `instanceIndexAt` / `composeNestedPositions` NESTED+FLAT 双形态，测试锁定「child origin=父格位中心」）、`gui/src/components/Preview3DLattice.tsx`（useThreeCanvas+computeCameraParams+STLLoader+色块总览 toggle+DETAIL 20k 超限自动切总览+提示+点击查格位，消费 lattice-extent + preview-lattice）、`gui/test/latticeInstances.test.ts`（16 用例 + 1 skip golden）。改 `gui/src/components/Preview3D.tsx`（fill_grid 非空→「格阵 3D」toggle）、`gui/src/components/GeometryTab.tsx`（两处 cells 投影透传 u/fill/lat/trcl/fill_grid）。门禁 vitest **466/0 无 skip**（golden skip 已修 + TS composeNestedPositions 已按 PM 裁决对齐 Python：golden JSON 加 `composeCases` 段（TS LatticeComposeNode 输入样例）、`latticeInstances.ts` 子格阵递归 origin=父格位中心+条目偏移+子默认居中偏移（子格阵整体居中于父格位中心，与 Python compose_lattice_tree 逐位一致）、golden 用例真断言 `composeNestedPositions` 输出===`nested.leaves` 10 叶双向集合相等（双端逐位锁死，不再只读 golden 值）、嵌套用例期望值同步更新；既有键不动、Python golden 3/3 不受影响）+ tsc EXIT 0 + vite build EXIT 0。备注：parseTrclDeg/instanceIndexAt 落盘签名是契约超集（加 lat? 与 instancedMeshes 参，因 rect/hex mod 需 lat 区分、拾取需网格列表）——最小必要扩展。
- **✅ 后端阶段3完成**（2026-08-24，重派后，未 commit）：lattice.py 新增 `hex_ring_rows`/`hex_ring_cell_count`/`hex_center`（与前端公式逐字一致，golden 锁死）、`lattice_cell_extent`（RPP/BOX 含9参数补全/RHP/HEX + 6/4平面 + 6P+2PZ，z 无界 None）、`expand_positions`（rect/hex 矩形盒模型、TRCL 绕 Z、超限 None）、`compose_lattice_tree`（嵌套递归双形态 NESTED tree + FLAT leafInstances，fill=X 单值列也递归，MAX_LATTICE_DEPTH=8/MAX_TOTAL_INSTANCES=500k/DETAIL 20k→detailViable=false）。`build_cells_data`：render:false→skip（修死代码）+ fill_grid 非空→skip + cells_by_num 保留；`_PREVIEW_CACHE_LATTICE` 独立缓存 + `_build_one_universe` 合成格元盒平面；preview_cache.fingerprint 加可选 extra（向后兼容）。两端点 `/api/lattice-extent` + `/api/preview-lattice`（api.yaml operationId latticeExtent/previewLattice + tag geometry；响应含 lattices[].positions/universes + leafInstances + tree + count + detailViable + limit）。门禁 pytest **673 passed/0 failed**（基线651+新增22）；契约闸门 HTTP **15/15**；golden positions/nested 已扩展（前端 1 skip 应消掉）；5001 端口空闲真实端口验证通过。改动清单 docs/backend-changes.md 附录Y。
- **⚠️ 三阶段总验收未通过，已打回修复（docs/qa-report-total.md）**：pytest 673/0 ✅、tsc 0 ✅、契约闸门 14/14 ✅、端到端结构 20/20 ✅、Python golden 3/3 ✅、R1/R4 不回退 ✅。**致命·后端**：`_build_one_universe`（api_server.py:487-562）格元盒裁剪把 6 平面追加进 cell 表达式做 CSG 交集 → 圆柱∩平行轴平面布尔恒空 → 17×17 详细模式 universe STL 全空（84B/0 三角），阶段3 核心「真实 pin 几何呈现」失效。修复方向=改 solid-solid 盒裁剪（复用 preview-3d 的 bound 机制）或降级兜底 + 补圆柱非空回归测试。**严重·前端测试**：latticeInstances.test.ts:278-298 golden 用例读错键名（positions 是数组、nested 段键名 outerLat/innerLat/…）→ hasGolden 恒 false → 恒 skip，TS 侧未消费阶段3 golden（仅 Python 单侧 3/3）。修复方向=正确消费 golden 键名，vitest 应 466/0 无 skip。
- **✅ 前端两处修复全部完成**（2026-08-24）：① golden skip 修复（latticeInstances.test.ts 消费正确键名）→ vitest **466/0 无 skip** + tsc 0 + Python golden 3/3；② TS `composeNestedPositions` 语义对齐 Python（嵌套 origin = 父格位中心 + 条目偏移 + 子格阵居中偏移；golden JSON 新增 **composeCases 段**；golden 用例真跑 composeNestedPositions 断言 FLAT 叶===nested.leaves 10 叶集合相等；既有嵌套用例期望值同步为 Python 对齐坐标）→ vitest 466/0 + tsc 0 + Python golden/compose 7/7（Python 未改）。无渲染回归风险（生产 Preview3DLattice 直食后端 leafInstances，改动只影响 TS 镜像测试）。
- **✅ 最终复验全绿（QA 独立复跑，docs/qa-report-final.md）**：pytest **674/0** / vitest **466/0 无 skip** / tsc EXIT 0 / 契约闸门 **15/15**（含新回归 `test_http_preview_lattice_universe_stl_nonempty` PASSED 未 skip）/ 嵌套 golden 双端逐位锁死（TS composeNestedPositions 真跑===golden nested.leaves 10 叶 + Python golden/compose 53 passed）/ R1/R4 7 passed。**空 STL 致命修复生效**：17×17 详细模式 12 个 universe cell STL 全非空（96~296 三角，cell1=96 与 preview-3d 基线一致），beavrs 仍 detailViable=false 总览。用户指定路径 E2E 直验 **17/17 PASS**（API 直验替代 GUI：导入 fill_grid 有值/surface_expr 干净、详细模式真实 pin、总览切换信号、generate round-trip 字节稳定且含 LAT=1+U=10+FILL=0:16 0:16 0:0）。**无致命/严重问题，建议放行统一提交。**
- **🔄 已打回修复全部闭环**：后端 `_build_one_universe` 空 STL（solid-solid 盒裁剪 + 显式降级）+ 前端 golden 死 skip（消费正确键名 + composeCases 段）均修复并复验通过。待统一提交。
- **⚖️ 争议仲裁（2026-08-24）**：TS `composeNestedPositions` 与 Python `compose_lattice_tree` 嵌套子格阵放置语义分歧——TS=child cell(0,0,0)=父格位中心；Python=child 格阵整体居中（child cell(0,0,0)=父中心−子 pitch/2，内层首叶 Python/golden (−3,−3) vs TS (−2,−2)）。**裁决=改 TS 对齐 Python**（运行时消费后端 leafInstances 为权威；plan 把跨语言格位双端逐位一致列为阶段3 最大风险，golden 应真正双端锁死，防未来前端消费 TS compose 引入偏差）。已派前端执行：改 `composeNestedPositions` 语义 + 嵌套用例真断言 TS 输出===golden leaves（不再只读 golden 值）。
- **📋 用户指定最终验收手工 E2E 用例（2026-08-24）**：用标签页示例库**第二个示例「17×17 PWR 组件」（/examples/assembly_17x17_mcnp.i）**。路径：应用内「示例文件」弹窗 → 选中第二个「17×17 PWR 组件」导入 → 验证：①导入后 fill_grid 有值、surface_expr 干净；②格阵 3D 预览「详细」模式渲染出**真实 pin 几何**（复验空 STL 修复是否生效）；③「色块总览」切换；④生成 INP 与示例等价。beavrs 全堆芯仍走总览。两路修复完成后按此复验。
- **✅ 阶段1数据层验收通过（QA 独立验收，docs/qa-report.md）**：六项全过——pytest **632/0**（独立复跑一致）/ vitest **412/0** / tsc 0 / 五夹具（prob41c/inp24/hex_lattice/17×17/BEAVRS）R1 字节全稳 / kitchen_sink R4 不回退 / 单值 fill 回归零破坏 / 前端 wire 透传不丢。**无致命/严重问题**。3 条建议已转：①nR 展开无上限 → 已追加给后端（lattice.py 加 MAX_EXPANDED_ENTRIES 上限 + 超限用例）；②CellData 字段顺序纯装饰忽略；③条目流≠dims 静默补 0 → 已追加给前端（画布不匹配提示）。未 commit（等三阶段完成统一提交）。
- **✅ 后端阶段2完成**（2026-08-24，未 commit）：`app/lattice.py` 增 `validate_lattice_surfaces(surface_expr,lat,surfaces_text="")->(ok,msg)`（只认带符号整数曲面号交集，拒绝 #/:/括号；lat=1 合法=单RPP/BOX、6个PX/PY/PZ每轴一对±、4平面2D；lat=2 合法=单RHP/HEX、6竖直P法向均布60°+2个PZ；自带曲面卡正则解析，纯 stdlib）。新端点 `POST /api/validate-lattice-surfaces`：入参 `{surface_expr,lat,surfaces_text}`，出参 `{status:"ok",ok,msg}`；api.yaml 补 operationId=validateLatticeSurfaces + tag geometry。**QA建议#1 已落地**：`MAX_EXPANDED_ENTRIES=1_000_000` 封顶 nR 展开与补 0（截断不抛异常，raw 保留 17r 简写，R1 不回退）。**golden 跨语言**：test_lattice.py 读 `gui/src/utils/__golden__/latticeGolden.json` 的 validate 数组断言（前端未产出时 pytest skip，产出后自动生效）。门禁 pytest **650 passed/1 skipped**（1 skip=golden JSON 前端未产出）；五夹具 R1 + kitchen_sink R4 全绿；契约闸门 12/12。改动清单 docs/backend-changes.md 附录X。
- **✅ 前端阶段2完成**（2026-08-24，未 commit）：新建 9 文件——`gui/src/utils/lattice.ts`（TS 镜像深模块 8 接口 + 派生/校验辅助：rangeFromDims/initialRectCells/initialHexCells/resizeLatticeCells/cellsToRaw/autoGenerateSurfaces/latticeMismatchMessage/validateLatticeSurfaces）、`universeGroups.ts`、`useDragToGroup.ts`、`three/useThreeCanvas.ts`（提取自 QuickCellDialog）、`three/hexPrism.ts`、`components/LatticeCanvas.tsx`、`components/LatticePreview3D.tsx`、`components/LatticeEditDialog.tsx`（6 步状态机：0 类型尺寸→1 材料锁死0+曲面校验+自动生成平面→2 延伸方向→3 调色板→4 涂色+子预览→5 保存，cells 反算覆盖 raw）、`utils/__golden__/latticeGolden.json`（rectGrid/hexRingRows/hexCenter/validate 9 样例，实测 9/9 全过含 lat2 PZ 一正一负修正）；改 `GeometryTab.tsx`（格阵徽标列+「⬚ 栅格编辑」按钮+「按 U 分组显示」toggle+拖组头改 u）、`CellEditDialog.tsx`（格阵字段分组+打开编辑器入口）。**QA建议#3 已落地**：`latticeMismatchMessage` 纯函数 + LatticeCanvas 非阻塞横幅。测试 3 文件 37 用例（lattice.test.ts 26 / LatticeCanvas.test.tsx 5 / universeGroups.test.ts 6）。门禁 vitest **449/0** + tsc 0 + vite build 0；跨语言 golden validate 9/9 PASS。
- **✅ 阶段2验收完成（QA 独立验收，docs/qa-report-phase2.md）**：必核 8 项全核——vitest **449/0**（独立复跑）/ tsc EXIT 0 / golden 跨语言**未 skip** 且 Python+TS 双端一致 / 新端点契约（api.yaml + AST 闸门 + **契约闸门 12/12 全绿** + 备用端口 5999 独立 HTTP 5/5 全 PASS）/ QA 建议① MAX_EXPANDED_ENTRIES 封顶、② 画布不匹配提示均已落地 / hexCenter 公式·材料锁死 0·LatticeCanvas props 与契约一致 / 阶段1 R1 闸门 + kitchen_sink R4 不回退。**全部门禁复绿：pytest 651/0/0（无 skip）、契约闸门 12/12、vitest 449/0、tsc EXIT 0。无致命问题，不放行打回，阶段2 通过可进阶段3**。曾 1 项严重（环境）已解决：5001 被旧打包版 sidecar（`D:\MCNP\MCNP输入卡生成器\python.exe -u backend/mcnp_bridge.py`，无新端点）劫持 → 契约闸门 HTTP 用例 404；用户手动关闭旧 sidecar 后复绿（端口占用检测加固按 PM 决策本次不做）。3 条建议已记录（pitch 超契约 / 「5步」措辞→6步 / estimateLatticeExtent 六棱柱单位格距待阶段3衔接）。
- **✅ 后端阶段2完成**（2026-08-24，未 commit）：见上「validate_lattice_surfaces + 端点 + MAX_EXPANDED_ENTRIES + golden 配套」，pytest 650 passed/1 skipped（skip=golden JSON 待前端产出，已产出→应消掉）。
- **前端 wire 透传完成**：阶段1纯字段透传，无可见 UI/无画布。新增 `gui/src/utils/cellBridge.ts` 深模块（`localToDeckCells`/`deckToLocalCells` 双向桥接 + `LocalCellRow` 类型），GeometryTab 四处重复映射收敛复用；三处类型桥接加 `fill_grid`（DeckContext / CellEditDialog / GeometryTab）+ quickCell.ts（tsc 必带）。localStorage 核实：`mcnp_workspace_v1` 整体存取无白名单，`fill_grid` 随 cell 原样不丢。测试 `gui/test/cellBridge.test.ts`（5）；门禁 vitest **412/0** + tsc EXIT 0。
- **架构师审阅裁决（保留精化 + 2处必须修）**：lattice.py 草稿（248行）接口齐备保留（FillEntry/FillGrid + to_json/from_json + parse_fill_tokens + parse_fill_entries + format_fill_cards，JSON 键名 / Nr 语义 nR=前一条目再重复n次 / 三形态判定 lattice/translated/单宇宙 均与 plan 一致）。**必须修**=①`format_fill_cards` 改 raw 优先回放（非 cells，保 17r 简写 / R1 稳定，raw 空才回落 cells）；②回放 raw 时剥离前导 `len(fg.range_)` 个范围 token（避免范围续行重复）。四文件改造点已定稿：models.py 加 `fill_grid: str=""`；core.py 两分支（FILL=273 / FILL 313）收 FILL 后全部 token 调 parse_fill_tokens + `idx=len(parts); break`；inp_generator.py 77-78 分派 from_json（脏JSON 优雅回退）+ 格阵/翻译路径 FILL 摘出放最后 + 续行独立追加；api_server.py `_cells_from_list` 加 `fill_grid=cell_dict.get("fill_grid","")`。
- **✅ 后端阶段1数据层完成**（2026-08-24，未 commit）：四文件改造完成（models.py 加 `fill_grid: str=""` / core.py FILL=273+FILL 313 两分支收束 `_consume_fill_tokens`：parse_fill_tokens 收 FILL 后全部 token，格阵→fill=范围串+fill_grid=JSON+`idx=len(parts); break`，单值路径 `_fg is None` 走原循环零回归 / inp_generator.py `_generate_cells` 分派 from_json（脏 JSON 优雅回退）+ FILL 摘出放 params 最后 + `lattice_lines[1:]` 独立追加续行不加 `&` + 格阵 cell 注释移尾（不吞条目）/ api_server.py `_cells_from_list` 加 `fill_grid=cell_dict.get("fill_grid","")`）。**format_fill_cards 2 处必须修已落地**：raw 优先回放（非 cells）+ 续行剥离前导 `len(fg.range_)` 范围 token。**伴生修复 2 处既有 R1 阻塞**：`_wrap_long_lines` 注释保护（`$` 在第 80 列内不拆，防 `&` 污染注释逐代漂移——BEAVRS 长注释实卡触发）+ `parse_data_cards` 连续 C 行回落 other_cards（防覆盖丢失——17×17/BEAVRS 数据段触发）。门禁 pytest **632/0**（基线 609 + 新增 23）；prob41c/inp24/17×17/BEAVRS/hex_lattice 五夹具 R1 字节稳定；kitchen_sink R4 不回退；wire 链路 asdict 桥接 + `_cells_from_list` 反向构造 fill_grid 不丢。新增 `tests/unit/test_lattice.py`（13）+ `tests/fixtures/hex_lattice.inp`（合成 lat=2 pointy-top 轴向 +Z）。测试清单全落地：test_core_cells 单值回归补 `fill_grid==""` + 新增 17×17/3D偏移 `1 (9 0 9)`/`17r` 重复/翻译单填充/条目同行/空格 FILL 用例 / roundtrip `_cell_fields` 加 fill_grid + R1 不动点闸门 2 条（17×17 + prob41c）/ conftest kitchen_sink cell1 加 fill_grid="" / owen 断言 fill_grid 非空+dims=[17,17,1]+surface_expr 干净。
- **已定约定**：`Nr` 展开复制进 lattice.py（**不动 core._expand_repeat**，防材料卡测试破坏）；六棱柱默认 pointy-top 轴向 +Z；kitchen_sink 既有 `fill="0" lat="1"` 按「待建格」（fill_grid 空）；阶段2 材料锁死 0；阶段3 用 universe 实例化方案。
- **阶段1验收标准**：pytest（parser/integration/unit）**632/0 全绿** + prob41c/17×17/BEAVRS（+inp24/hex_lattice）`parse→gen→parse→gen` 字节稳定（R1 不动点）+ kitchen_sink R4 不回退 + 前端 wire 透传不丢（均已达成）。

## S1b-1 阶段2（UI画布）设计契约（架构师已交付，2026-08-24，待阶段1验收后派活）
- **gui/src/utils/lattice.ts（TS 镜像深模块）**：FillGridJson 接口（键名与 Python FillGrid 逐字一致）+ `parseFillGrid`/`serializeFillGrid`/`rectGrid`（idx=i+dims[0]*(j+dims[1]*k) 行主序）/`hexRingRows`（rings=1→[2,3,2]，总和 1+3r(r+1)）/`hexGrid`/`hexCenter`（pointy-top 顶点+X：x=col*pitch+(row%2)*pitch/2，y=row*pitch*√3/2——画布与阶段3共用，golden 测试锁死）/`buildUniversePalette`（u 数值升序取 12 色板）/`getUniverseColor`（未命中回退灰）/`estimateLatticeExtent`。
- **LatticeEditDialog.tsx 5 步状态机**：0 选 lat 矩形/六棱柱 → 1 材料锁死0 + 曲面 textarea（失焦调后端 validate_lattice_surfaces）+「自动生成平面」（矩形长宽高+中心→PX/PY/PZ；六棱柱边长+高+中心→RHP/HEX）→ 2 延伸方向 2D/3D → 3 宇宙调色板 → 4 LatticeCanvas 涂色 → 5 保存（fill=range.join，lat，fill_grid=serializeFillGrid，surface_expr，mat=0，density=""；保存时 cells 反算覆盖 raw）。
- **LatticeCanvas.tsx props**：`{lat,dims,cells,palette,selectedU,onCellChange(idx,u),disabled?}`；矩形=CSS grid，六棱柱=hexGrid 蜂窝环交错排布。
- **app/lattice.py 增 validate_lattice_surfaces(surface_expr,lat,surfaces_text="")->(ok,msg)**：只认带符号整数交集，拒绝 #/:/括号；lat=1 单 RPP 或 6 平面 PX/PY/PZ 每轴一对± 或 4 平面 2D；lat=2 单 RHP/HEX 或 6 个 P+0/2 个 PZ；自带曲面卡正则解析，不依赖 freecad/parsers。
- **universeGroups.ts + useDragToGroup.ts**：`groupByUniverse`（u 数值升序，raw 不进组）+ `groupHeaderLabel`（`U=${u} · ${count} 栅元`）；useDragToGroup 复用 useRowDrag 指针骨架，落组头改 u、落普通行保持行重排。
- **子预览复用**：新 `gui/src/three/useThreeCanvas.ts`（把 QuickCellDialog.tsx:48-100 提取为共享 hook）+ `gui/src/three/hexPrism.ts`（buildHexPrism pointy-top 六棱柱线框，外接半径 R=pitch/√3）+ 复用 computeCameraParams。
- **跨语言 golden**：`gui/src/utils/__golden__/latticeGolden.json` 单一权威数据集，Python test_lattice.py 与 TS lattice.test.ts 读同一 JSON 断言相同 expected。
- **GeometryTab 集成**：格阵徽标列 +「插入栅格编辑」按钮 +「按 U 分组显示」toggle。
- **✅ 前端阶段2 UI 画布完成**（2026-08-24，未 commit）：`gui/src/utils/lattice.ts`（TS 镜像 8 接口：FillGridJson/parseFillGrid/serializeFillGrid/rectGrid/hexRingRows+hexGrid+hexCenter/buildUniversePalette+getUniverseColor/estimateLatticeExtent，键名与 Python 逐字一致）+ `LatticeEditDialog.tsx`（6 步状态机：0 类型尺寸→1 材料锁死0+曲面失焦校验 validate-lattice-surfaces+自动生成平面→2 延伸方向 2D/3D→3 调色板→4 画布涂色+3D 子预览→5 保存，保存 cells 反算覆盖 raw）+ `LatticeCanvas.tsx`（矩形 CSS grid / 六棱柱 hexGrid 蜂窝）+ `LatticePreview3D.tsx`（复用 useThreeCanvas+hexPrism+computeCameraParams 跟手重建）+ `three/useThreeCanvas.ts`+`three/hexPrism.ts`（共享 WebGL 挂载 + pointy-top 六棱柱线框）+ `universeGroups.ts`+`useDragToGroup.ts`（拖组头改 u / 落普通行重排）+ GeometryTab（格阵徽标列/⬚ 栅格编辑按钮/按 U 分组 toggle）+ CellEditDialog（格阵字段分组+打开栅格编辑器入口）+ 跨语言 golden `__golden__/latticeGolden.json`（backend schema 产出）。门禁 vitest **449/0**（基线 412 + 新增 37：lattice 26 / LatticeCanvas 5 / universeGroups 6）+ tsc EXIT 0 + vite build EXIT 0。**画布不匹配提示已加**（QA 建议3：条目流≠dims 乘积 → 非阻塞横幅）。
- **✅ 后端阶段2完成**（2026-08-24，未 commit）：`app/lattice.py` 增 `validate_lattice_surfaces(surface_expr,lat,surfaces_text="")->(ok,msg)`——只认带符号整数曲面号交集，拒绝 #/:/括号；lat=1 合法=单 RPP/BOX 宏体、6 个 PX/PY/PZ（每轴一对±）、4 个平面（2D 延伸）；lat=2 合法=单 RHP/HEX、6 个竖直 P（法向水平面均布 60°）+2 个 PZ（一正一负）；自带曲面卡正则解析（`_parse_surface_cards`，纯 stdlib 不依赖 freecad/parsers）。新端点 `POST /api/validate-lattice-surfaces`（operationId `validateLatticeSurfaces`，响应 `{status:"ok",ok,msg}` 扁平风格对齐 validate-inp；api.yaml 已补 + 契约闸门 HTTP 用例已加）。跨语言 golden 断言已就位（`tests/unit/test_lattice.py` 读 `gui/src/utils/__golden__/latticeGolden.json`，前端未产出时 skip）。**QA 建议落地**：`MAX_EXPANDED_ENTRIES=1_000_000` 封顶 `parse_fill_entries` nR 展开与 `parse_fill_tokens` 补 0（截断不抛异常、raw 兜底 R1 不受影响）。门禁 pytest **650/0（1 skip golden）**，阶段1 五夹具 R1 不动点不回退。

## S1（上一批次）当前批次：栅元列表批量编辑 + 会话外技术债清偿（14 项）+ P0 3D 预览重合 bug 修复（2026-08-23 已统一提交 commit c3e5c43，未 push）
- **✅ v1.7.3 重打包部署完成（backend，2026-08-23，c3e5c43 无新 commit）**：技术债 14 项 + 3D 预览重合修复进包。版本四处+锁 1.7.3 一致（零改动）；门禁 pytest 609/0 + vitest 407/0 + tsc/build；冒烟 6 项全过（探活 loaded:true 7621 / parse real_meshtal_jk grid_bounds 49,-10,90~51,10,110 tally14/p/1×2×2 warnings[] / texture bytes 4 / 版本双信号 1.7.3 / _internal 完整含本批新模块 / 6.2 时效校验手动覆盖）；产物 D:\MCNP\MCNP输入卡生成器（exe 6,563,328B + python.exe 25,222,687B + _internal，mtime 23:50）；环境已清理。遗留人工冒烟：3D 预览重合修复 + 参数扫描取消/预算拒绝 待用户实测。
- **✅ 统一提交完成（backend，2026-08-23）**：commit `c3e5c43`（29 files +1604/-112，message `chore(tech-debt): 清偿会话外改动技术债 14 项 + 修 3D 预览重合检测陈旧数据 bug`，main 分支，未 push）。工作树仅剩 `.snap` 行尾环境产物（勿提交）。门禁 pytest **609/0** + vitest **407/0**。**技术债 14 项全清**（会话外改动审计）：后端 T3 sweep 预算 / T7 探针失败进 unresolved / T8 临时目录清理 / T6/T9/T10/T11/T12/T13/T14 + 前端 T1 批量编辑勾选下标 bug / T2 重合检测静默 / T3 扫描可取消 / T4 死代码 / 文档 T5 双端补批。**P0 bug**（用户实测"添加新栅元后预览仍显示重合，重开才正常"）根因=Preview3DWindow 一次性快照 + 丢 existingExprPatch → 修复 `applyExistingExprPatch`（通病，真空最常见受害者）；增强"主窗口 deck 同步预览"评估为中高风险，本批不做待排期。
- 一句话状态：**栅元列表批量编辑功能落地**——勾选若干栅元 → 「⚡ 批量编辑」按钮由灰变亮 → 弹窗批量改材料号/密度/IMP/高级参数；曲面表达式**只能追加**（锁死提示「无法批量更改曲面表达式，只可添加」+ 后缀输入，确认后追加到勾选栅元曲面表达式末尾）。门禁 vitest **387/0**（含 colorize 性能 flaky 复跑通过）/ tsc EXIT 0 / vite build 成功；纯前端改动，无新增后端端点。
- **同日技术债清理批（PM 派发，未 commit，测试先行红→绿）**：T1 批量编辑勾选状态「数组下标 → 栅元 num」（`batchCellEdit.ts` 新增 `toggleCellNum/selectedCellsFromNums/applyBatchEditToRows/pruneSelectedNums`，重排/删除后仍改对原勾选栅元；DOM 集成测试 勾选→拖拽重排→批量编辑）；T2 快捷建栅元重合检测 catch 不再静默（`quickAddCheckFailedMessage` + 非阻塞警告弹窗 + console.warn）；T3 SweepDialog doRun 加 `AbortController` + 120s 超时 + 「取消」按钮；T4 Preview3D 删 `dbgLog`/`log()` 死代码与 initScene 生产 console.log。
- **同日 P0 修复（用户实测「添加新栅元后真空栅元仍显示重合，关闭重开预览才正常」）**：根因=Preview3DWindow 打开时一次性取 deck 快照，预览窗口内快捷建栅元 + 补集决策只 append 新栅元、丢 `existingExprPatch`（被侵占栅元表达式没改 `...#新`）→ 预览侧旧快照 POST check-overlap 报陈旧重合（真空只是最常见受害者）。修复：`quickCell.ts` 新增 `applyExistingExprPatch` 纯函数，`Preview3DWindow.handleQuickCellGenerate` 追加前先应用补丁（照 GeometryTab:211-216）；`existingExprPatch.test.ts`(4) + `preview3dWindowPatch.dom.test.tsx`(1) 红→绿。**增强「主窗口 deck 同步到预览窗口」未做，方案+风险已报 PM 定夺**。
- **门禁 vitest 407/0（基线 388 + 新增 19）/ tsc EXIT 0 / vite build EXIT 0**。改动清单 docs/frontend-changes.md 已补 08-18/08-22/08-23 五批缺失条目 + 本批 T1-T4 + P0。
- **批量编辑**：`gui/src/utils/batchCellEdit.ts`（纯函数：`applyBatchCellEdit` 空字段=不改、曲面永不覆盖只追加；`batchEditEmpty` 判空控确认钮）+ `gui/src/components/BatchCellEditDialog.tsx`（材料下拉自动带出密度 / IMP:N·P·E / 高级参数折叠区 / 锁死的曲面提示 + 追加输入）。
- **接入** `gui/src/components/GeometryTab.tsx`：栅元列表新增勾选列 + 表头全选/取消全选 + 「⚡ 批量编辑」按钮（无勾选时灰色禁用，勾选后可点）；删除/同步行变化自动清理失效勾选；local→deck 走现有 patch 管线。
- **约定（用户已确认）**：弹窗留空字段 = 不修改；曲面表达式只做「追加」（空格分隔）。
- **测试**：`gui/test/batchCellEdit.test.ts`（9 用例）+ `gui/test/batchCellEditDialog.dom.test.tsx`（3 用例）。

## S1b（上一批次）当前批次：v1.7.3 第二批发版（keff 仪表盘 / 材料搜索 / 示例库 / INP 对比，2026-08-23 已提交并部署）
- 一句话状态：**v1.7.3 第二次打包部署完成**（主 exe 含全部新前端，sidecar 25,235,799B @ 13:21）；门禁 pytest **595/0** / vitest **376/0** / tsc 0；api.yaml **36** 端点。
- **ef9499f / 76b0c76（第六轮，用户定稿 3D 预览深色方案，已打包部署）**：3D 预览固定黑色背景不受亮色主题影响——Preview3DWindow 根容器硬编码 #000/#fff + preview3d-root 作用域类；global.css 作用域内覆盖 --bg-*/--text-* 为黑底白字系、.form-select/option 黑底白字、强调色 --accent 固定红色系 #FF4D6D（用户：文字不强制全白，红色/强调保留）；场景画布背景 0x000000。门禁 vitest 376 / tsc 0；已部署（主 exe 6,561,792B @ 14:07:32）。
- **b1e6ebe（第五轮主题修复，已打包部署）**：3D 预览亮色主题全面可读——Preview3DWindow 根容器硬编码 #0a0a1e 蓝黑底+白字 → var(--bg-deepest)/var(--text-primary)；Preview3D 侧栏/面板/输入框/边框/标题硬编码 rgba(10,10,30,…)/rgba(0,0,0,0.3)/rgba(255,255,255,0.04~0.1)/rgba(241,241,249,0.8) → 主题变量；QuickCellForm 材料下拉 select 加 form-select（option 下拉列表走 var(--bg-surface)/var(--text-primary)，不再黑底深字）；3D 场景画布背景与模态遮罩保留深色。门禁 vitest 376 / tsc 0；已部署（主 exe 6,561,280B @ 13:53:45，sidecar 未变）。
- **e2225e7（第四轮 UI 修复，已打包部署）**：① Preview3D 快捷建栅元覆盖层硬编码深底 rgba(10,10,30,0.98)/白字 → 改主题变量（--bg-surface/--text-primary/--border-glass），亮色主题不再灰底白字；② OutputTab keff 按钮被嵌套进参数扫描按钮内（点击冒泡连带触发）→ 平级闭合；③ ExamplesDialog 查看卡文本 DocViewer 用 createPortal 挂 document.body，脱离父弹窗 overflow:hidden 裁剪。门禁 vitest 376（colorize 性能 flaky 复跑通过）/ tsc 0；已部署（主 exe 6,561,280B）。
- **9ccee02（第三轮，已打包部署）**：输出页新增「🔬 解析 keff」按钮（KeffDialog：mctal 路径/目录 → /api/parse-keff → 最终 k-eff + 收敛图）；对比按钮从输出页移到基础页工具栏（用户指定）；api.yaml 36→37；部署冒烟 parse-keff 目录/文件两种方式均返回 5 周期收敛 + combined。
- 构建顺序纪律（再修正）：**vite → PyInstaller → 复制 dist/python → src-tauri/binaries → tauri build → 部署**；tauri build 的 beforeBuildCommand 会重跑 vite 清空 dist/python，故 PyInstaller 产物必须先复制进 binaries 再跑 tauri，或 PyInstaller 放 tauri 之后。
- **1e86299（keff 仪表盘）**：用户批准引入 **recharts@3.10.1**（npm 常规位置，prod audit 0 漏洞）；后端 `sweep.py +parse_keff_history`（逐周期 cycles/mean/std）+ sweep-run 读 mctal 补 convergence/keffStd + manifest 写盘 + 新端点 `/api/sweep-dashboard`（历史目录重读并补全收敛）；前端 `utils/sweepDashboard.ts` 聚合纯函数（对齐 OWEN sweepDashboardCore）+ `components/SweepDashboard.tsx`（Recharts：k-eff vs 参数误差棒 + y=1 临界线 + 逐 run 收敛小多图）+ SweepDialog 结果区默认仪表盘视图（表格/仪表盘切换）。
- **d7aad5d（材料搜索 + 示例库）**：MaterialEditDialog 预设下拉加搜索过滤（名称/化学式/描述，抽纯函数 `filterPresets` + 4 用例）；BasicSettings「示例」按钮（原格式文档）→ ExamplesDialog 内置 pincell/17×17/BEAVRS 三张真实卡（`gui/public/examples/`），一键导入 = fetch → `mcnp:import-inp` 自定义事件 → App 监听复用 `importInpText` 管线（validate-inp + parse-inp + loadDeck），查看卡文本 = DocViewer。
- **fa2bee6（INP 对比 diff）**：输出页「⇄ 对比」入口（参数扫描旁）；A=当前工作区生成 INP（可编辑），B=从文件加载/粘贴；后端 `/api/diff-inp`（Python difflib，零新依赖，unified diff + 增删统计）；前端 `DiffDialog` 行着色渲染（新增绿/删除红/头蓝）+ `diffRender` 纯函数 + 2 用例。
- **e70f309**：sweep-dashboard 读 manifest 容忍 UTF-8 BOM（utf-8-sig）。
- 发布纪律再记一条：**构建顺序必须 vite build → PyInstaller → tauri build**（vite 会清空 dist，先跑 PyInstaller 会被删掉 dist/python）；本次踩坑后已纠正。
## S1b（上一批次）当前批次：v1.7.3 发布 + 重合检测超时修复 + 零体积检测（2026-08-23，已提交并部署）
- 一句话状态：**v1.7.3 已发版并部署至 `D:\MCNP\MCNP输入卡生成器`**（版本四处+lock 均 1.7.3）；重合检测门禁 pytest **590/0** / vitest **363/0** / tsc EXIT 0；交接文档已更新。
- **e5e09af（快捷添加补集决策完善）**：决策抽纯函数 `applyQuickAddChoice`（A=新#已有 / B=被侵占栅元（含真空）#新 / D=只占真空（真空让位#新，新#非真空） / C=不改）；支持一次性多栅元；后端 quick-add-check 接收 `new_cells` 数组 + worker `focus_nums` 多栅元过滤 + 零体积检测；48 个 PNNL 预设改中文名。
- **698e7e2（重合检测超时根治，本批关键）**：
  1. **cell_aabb 裸曲面正侧无界修复**：MCNP 裸 `["surf",n]` = 正侧（R³ 无界），不得返回曲面自身 AABB。旧 bug 将球壳栅元 '1 -3' 裁到内球 [-1,1]，网格只覆盖 8 角碎块、288k 三角形 → worker 120s 超时（check-overlap/quick-add-check 实测均报 error）。修复后紧盒取有界伙伴 [-2,2]，球壳网格 132k、4.0s 完成。
  2. **_triangles_to_fcmesh 批量化**：逐面 `addFacet`（120k 三角 45s）→ 批量 `addFacets`（0.33s），140 倍提速。
  3. **空栅元零体积检测**：体素网格为空的真实空几何不再 fallback 包围盒（否则伪造非零体积），改记 `empty_nums` → `zero_volume` 输出；零体积栅元不生成 STL。
  - 测试：+3（裸正侧无界 / 球壳 AABB / 球壳网格外延）；部署版冒烟：check-overlap 检出 (1,6)+(3,7)、zero_volume [5]；quick-add-check 多栅元 8 对、zero_volume [5,12]、recommended existing_hole；preview-3d GQ+SQ+*TR1 出 1/6/7 号 STL。
- 自动测试规则：所有测试/构建均加硬性超时（Start-Process + WaitForExit + Kill）；打包纪律：PyInstaller sidecar → 替换 src-tauri/binaries → 手动复制到 target/release（增量 tauri build 不刷新 sidecar）→ 杀进程部署。
## S1b（上一批次）当前批次：GQ/SQ 3D 预览修复（2026-08-22，施工完成，未发版/未 commit）

- **一句话状态**：GQ/SQ 曲面 3D 预览修复**施工完成**——纯 numpy marching cubes 去 vtk + TR 变换修复 + 动态测试发现的 3 个 bug 修复；全部门禁绿（pytest **544/0**、vitest **345/0**、tsc EXIT 0）；PyInstaller sidecar 重打包成功，**打包版 GQ/SQ preview-3d 冒烟通过**（GQ 椭球 + `*TR1` 平移 (5,0,0)：94272 三角形、bounds [2.97,7.03]×[±1]×[±1]、mid (5,0,0)、水密 0 异常边）。文件版本恒 **1.7.2**。
- **动态测试发现的 3 个 bug**（细节见交接文档 `P:\dekstop\GQ-SQ_3D预览修复_交接文档.md`）：
  1. `app/mc.py` 邻接索引 `t_ids`/`slots` 的 repeat/tile 与「块状拼接的边数组」错位 → 朝向传播全乱（signed volume≈0、假碎片/假冲突）；
  2. BFS 波前未去重指数膨胀（4 千万+）+ 性能（焊接/z 循环优化，单栅元 res=64 从 477ms → **172ms**）；
  3. TR 小栅元在大 bound（B=500）下：TR 曲面 AABB 保守全盒 + margin 用全局 B（35cm）→ 32³ 粗扫漏检 → 空网格降级包围盒；修复=TR AABB 8 角点变换求全局紧盒（`_transform_aabb`）+ margin 按实际扫描盒间距。
- **第 4 项（GQ/SQ 渲染后续增强）也已完工（同日）**：
  - **2D 解析切片**（`app/analytic_slice.py` + `tests/unit/test_analytic_slice.py` 5 用例）：切割平面上逐点解析求值栅元布尔表达式（含 TR）+ 2D marching squares 提取轮廓，GQ/SQ 截面**精确**（不依赖 STL 网格分辨率）；preview-3d 在会话里存 deck 快照，cross-section 对 GQ/SQ 栅元自动走解析切片、失败回退 STL 切。打包版冒烟：480 点椭圆轮廓 x∈[3.002,6.998]、y∈[±1.003]。
  - **切线平面法快路径**（`voxel_csg._tangent_plane_mesh`，借鉴 OWEN csgScene）：单个内侧椭球/球/圆柱 + 平面封口 → 切线半空间 + 凸多面体裁剪（Sutherland–Hodgman + 盖面极角排序），水密 by construction；椭球 162 方向 + 绕中心体积校正（无封口时）或 642 方向（有封口时），圆柱 48 段；union/补集/多二次曲面/锥 → 回退 MC。三角形数从 MC 的 ~10 万降到 ~600。
- **同日小改动（前端）**：材料编辑对话框选「预设材料」后直接填充到**手动 ZAID 模式**（`MaterialEditDialog.handlePreset` 的 `setMode("formula")→"manual"`；`parseFormula` 本就填充核素行，formulaText 保留供切回化学式查看）。vitest 345/0 + tsc EXIT 0。
- **同日（材料库扩充）**：从 OWEN 的 `data/pnnl-materials.json`（PNNL-15870 Rev.2）**精选 48 种**材料（核燃料 6 / 探测器 11 / 屏蔽与慢化 9 / 结构与合金 5 / 气体与冷却剂 3 / 组织与剂量 6 / 通用 8），生成 `gui/src/data/pnnlPresets.ts`（同位素级 ZAID + 负质量份额 rows，一次性脚本生成勿手改）；`PresetItem` 加 `rows` 字段，选 PNNL 预设**直接填手动 ZAID 模式**（不走化学式展开）。**总预设 49 内置 + 48 PNNL = 97 种 ≤100**（用户要求）。vitest 348/0（+3 数据契约用例）+ tsc EXIT 0。
- **同日（OWEN 四项落地）**：① **BEAVRS/17×17/单棒 MCNP 卡进测试夹具**（`tests/fixtures/owen/`，3 文件 + README 出处声明，解析基线 3 用例：pincell 5 栅元/266 曲面/4 材料，17×17 15/275/5 含 `lat=1` 结构化字段，BEAVRS 全堆芯 331/2101/13）；② **mctal 解析**（`app/mctal_parser.py` 纯 stdlib：k-eff 周期/combined、tally 块/nps/能量网格/OWEN 两列通量谱，容错 + 4 用例；夹具 `sample.mctal`（OWEN 原样）+ `kcode_realistic.mctal` 合成）；③ **校验规则交叉核对**（`docs/contracts/validator-crosscheck.md`：OWEN rules.ts 9 条 → 覆盖映射，新增 3 条材料级规则进 validator.py——ZAID 格式 `\d{4,6}(\.\d{2,}[a-z])?`、份额符号一致、S(α,β) 目标核素 `_check_sab_target`，7 用例）；④ **参数扫描**（`app/sweep.py` 纯 stdlib 对齐 OWEN sweepCore：cartesian/apply_parameters/parse_keff/manifest/summary TSV + `/api/sweep-plan`（规划不执行）与 `/api/sweep-run`（逐组合跑 MCNP 上限 50，无 MCNP 返回错误）两端点 + api.yaml 30→32 端点，6 用例）。pytest **573/0** / vitest 348/0 / tsc 0 / 契约闸门 10/10。
- **同日（3D 重合检测，反馈 #7 施工）**：空间索引版全 deck 检测 + 快捷添加补集决策——`app/overlap_classify.py`（容差/volumeFraction/severity 表/探针 suspected 降级/截断）、`app/spatial_index.py`（AABB 均匀网格候选对 O(n·k) + 新增单查询）、`app/overlap_probe.py`（GQ/SQ 解析采样探针，复用 voxel_csg 求值含 TR，蒙特卡洛估占比）；worker Step 3.5 检测段（`check_overlaps`/`focus_num` 入参，`overlaps`/`overlap_truncated`/`overlap_unresolved` 出参，只增不改）；端点 `/api/check-overlap`（同指纹缓存 overlaps.json）+ `/api/quick-add-check`（含推荐方向 new_hole/existing_hole）+ api.yaml 32→34；前端 Preview3D 异步自动检测 + 预警面板 + 点击对红色高亮（controller.setHighlight），GeometryTab 快捷添加后 A/B/C 补集决策（A=新#已有 / B=已有#新 / C=保留，自动改写表达式）。真空参与检测。pytest **587/0**（+14：classify 6 / spatial 4 / probe 4）/ vitest 358/0 / tsc 0 / 契约闸门 10/10。
- **同日（参数扫描前端 + 组件测试）**：`gui/src/components/SweepDialog.tsx`（主窗口弹窗：基准 INP 自动生成、参数编辑、组合数、规划预览、执行结果表、TSV 下载；OutputTab「⚙ 参数扫描」入口）；**DOM 交互测试** `gui/test/sweepDialog.dom.test.tsx`（6 用例，`@vitest-environment jsdom`，mock fetch 覆盖生成→改参→规划→执行→错误→关闭）——为此**用户批准新增开发依赖**：jsdom 30 / @testing-library/react 14.3.1 / @testing-library/dom 9.3.4（§5 依赖红线例外，仅 devDeps）；同时修了 `FloatingDialog` 的 SSR 不兼容（`useState` 初始化访问 `window` → 加 `typeof window` 防护，浏览器行为不变）。vitest **358/0** / tsc EXIT 0。
- **上一批次 V1.7.2.2**（2026-08-19 已部署，4 修复）详情见 §8 / docs/CHANGELOG.md。

## S2 工作区与分支

- **分支**：`main`。
- **工作树未提交改动**（git status 快照，批量编辑栅元批次）：
  - 修改：`gui/src/components/GeometryTab.tsx`（栅元列表批量编辑接入）
  - 新增：`gui/src/components/BatchCellEditDialog.tsx`、`gui/src/utils/batchCellEdit.ts`、`gui/test/batchCellEdit.test.ts`、`gui/test/batchCellEditDialog.dom.test.tsx`
  - 说明：`gui/test/volume/__snapshots__/volumeShader.snapshot.test.ts.snap` 仅行尾 LF/CRLF 差异（非内容改动，环境产物，勿提交）；此前 `app/*.py` 等相关改动已提交，故不再列出。
- **版本四处+锁文件**：tauri.conf.json / package.json / Cargo.toml / README 徽章 / Cargo.lock 恒 **1.7.2** 一致。

## S3 进行中任务 / 待办

- **已完成（2026-08-22）**：GQ/SQ 曲面 3D 预览修复——施工 + 3 bug 修复 + 全量门禁（pytest 544 / vitest 345 / tsc）+ PyInstaller sidecar 重打包 + 打包版 GQ/SQ preview-3d 冒烟全过；交接文档已更新为收尾版 `P:\dekstop\GQ-SQ_3D预览修复_交接文档.md`。
- **待发版**：tauri build + 部署（§9 链路，含 6.2 时效坑）；版本号由上级另行指定（施工期间文件恒 1.7.2）；当前全部改动未 commit。
- **已完成**：3D 重合检测（空间索引 + 精确布尔 + GQ/SQ 探针 + 快捷添加补集决策），契约 geometry-check.md 落地。
- **讨论过未做（可排期）**：无（OWEN 借鉴项已全部落地：PNNL 精选材料库 / BEAVRS·17×17 夹具 / mctal 解析 / 校验规则交叉核对 / 参数扫描后端+端点+**前端弹窗** `gui/src/components/SweepDialog.tsx`，OutputTab「⚙ 参数扫描」入口）。
- **已知阻塞**：无。
- **其余**：按用户新反馈排队。

---

# ◉ 长期记忆（稳定存储）—— 固化知识

> 固化后不随批次变动；更新只在"经验固化"时进行。

## §1 项目身份（语义记忆）

- **名称**：MCNP 输入卡生成器（MCNP Input Card Generator）
- **版本**：1.7.2（快捷建栅元新功能，用户 2026-08-18 指定；**bug 修复批严禁升版**，V1.7.2.2 批次文件版本恒 1.7.2；升版由上级另行指定）
- **技术栈**：
  - 前端 UI：React 18 + TypeScript + Vite（端口 1420，表单化标签页界面）
  - 3D 渲染：Three.js（3D 预览 + 体积可视化）/ SVG（平面截面 / OUTP 折线图）
  - 窗口外壳：Tauri 1.x（Rust，无边框自定义窗口；Electron 备用壳已于依赖清理中删除）
  - 后端：Python 标准库 `http.server`（端口 5001，**不用 Flask**），PyInstaller 打包 sidecar
  - 核心引擎：pymcnp（BSD-3-Clause）+ 自研 generator/parsers
  - CSG 几何：FreeCAD（LGPL）；STEP→MCNP：GEOUNED（EUPL-1.2，随程序 vendor 打包）
- **核心业务**：用可视化表单 GUI 替代手工编辑 MCNP `.INP` 输入文件；覆盖生成/导入/校验/3D 预览/截面/材料库/源/计数/输出分析全流程
- **许可**：本项目自有代码 MIT License（2026-08-28 由自定义限制许可改为 MIT，放弃商用/再分发限制）；开源组件各按自身许可

## §2 当前状态快照（语义记忆）

- **开发阶段**：已交付 v1.7.2（2026-08-18 打包）+ V1.7.2.2 批次（2026-08-19 终版重打包，4 修复进包）；后续功能（#7 重合检查）待用户排期
- **已完成功能**：
  - 8 标签页表单编辑（基本/材料/几何/源/计数/高级/输出）
  - INP 生成/导入（含拖拽）、工作区自动保存/恢复、4 套主题
  - 材料库（**97 种预设**：49 内置 + 48 PNNL-15870 精选同位素级；xsdir 校验 + 下拉自动填充密度）+ **用户可编辑持久材料库**（材料库深化，2026-08-30：custom/override、导入导出 JSON·CSV、xsdir 反向索引 + 组成自洽校验、「📚材料库」管理面板、MT卡/其他随预设贯通，存 `D:\MCNP\material\material_library.json`）
  - 3D 预览（FreeCAD CSG，`#n` 栅元补集支持）+ 平面截面（STL numpy 切）+ STEP/GEOUNED 导入
  - **GQ/SQ 曲面 3D 预览**（2026-08-22）：含任意 GQ/SQ 的栅元走纯 numpy 体素 CSG（`app/mc.py`/`voxel_csg.py`/`quadric.py`），TR 变换正确、水密、无 vtk 依赖、打包可用
  - **GQ/SQ 精确截面（2D 解析切片）**（2026-08-22）：`app/analytic_slice.py` 在切割平面上解析求值 + marching squares 提取轮廓；**切线平面法快路径**（椭球/圆柱平滑水密网格，~600 三角形）
  - **mctal 解析 + 参数扫描**（2026-08-22）：`app/mctal_parser.py`（k-eff/收敛/tally，纯 stdlib）+ `app/sweep.py` + `/api/sweep-plan`（规划）/`/api/sweep-run`（执行，上限 50 组合）+ 前端 `SweepDialog.tsx`（参数编辑/组合预览/结果表/TSV 下载，OutputTab 入口）
  - **校验规则交叉核对**（2026-08-22）：`docs/contracts/validator-crosscheck.md`（OWEN rules.ts 映射）+ validator 新增 ZAID 格式/份额符号/S(α,β) 目标 3 条材料级规则
  - **BEAVRS/17×17/单棒卡进测试夹具**（2026-08-22）：`tests/fixtures/owen/` 解析基线回归
  - **快捷建栅元**（几何标签页「曲面卡 & TR 变换」⚡）：RCC/RPP/SPH 一键生成曲面+TR+栅元（编号顺延/材料密度带出/imp 勾选/实时线框预览，轴固定世界原点 Z 朝上）
  - **栅元列表批量编辑**（几何标签页栅元列表 ⚡，2026-08-23）：勾选多栅元 → 批量改材料号/密度/IMP/高级参数；曲面表达式**只能追加**（锁死提示 + 后缀输入，确认后回填到栅元表达式末尾；留空字段=不改）
  - **格阵 fill 阶段1：数据层（解析+生成+模型+wire）**（2026-08-24）：`app/lattice.py` 深模块（纯 stdlib）结构化解析 prob41c/inp24/17×17/BEAVRS 格阵（FillGrid JSON：range/dims/cells/raw，`17r` 简写 + `(x y z)` 偏移 + 翻译单填充）+ `format_fill_cards` raw 优先回放（R1 字节稳定）；`CellData.fill_grid` + FILL=/FILL 解析收束 + `_generate_cells` 格阵分派 + `_cells_from_list` wire 透传；伴生修复 `_wrap_long_lines` 注释保护与 `parse_data_cards` 连续 C 行丢失；**前端 wire 透传**：`cellBridge.ts` 深模块统一 local↔deck 双向桥接 + 三处类型桥接 + quickCell 透传；parse→deck→localStorage→generate 全链路 `fill_grid` 不丢（含旧数据兜底 `""`）
  - **格阵 fill 阶段2 后端：validate 预检测 + 端点 + golden 配套**（2026-08-24）：`app/lattice.py` 增 `validate_lattice_surfaces(surface_expr,lat,surfaces_text="")->(ok,msg)`（只认带符号整数交集，拒绝 #/:/括号；lat=1 单 RPP/BOX 或 6 PX/PY/PZ 每轴一对± 或 4 平面 2D；lat=2 单 RHP/HEX 或 6 竖直 P 均布 60°+2 PZ 一正一负；自带曲面卡正则解析，纯 stdlib 不依赖 freecad/parsers）+ 新端点 `/api/validate-lattice-surfaces`（api.yaml operationId=validateLatticeSurfaces + 契约闸门 HTTP 用例）+ 跨语言 golden 断言（读 `gui/src/utils/__golden__/latticeGolden.json`，前端未产出 skip）+ **QA 建议落地** `MAX_EXPANDED_ENTRIES=1_000_000` 封顶 nR 展开/补 0（raw 兜底 R1 不回退）；门禁 pytest **650/0（1 skip golden）**
  - **格阵 fill 阶段2 前端：UI 画布**（2026-08-24）：`gui/src/utils/lattice.ts`（TS 镜像 app/lattice.py 深模块，键名逐字一致）+ `LatticeEditDialog.tsx`（6 步状态机：0 类型尺寸→1 材料锁死0+曲面失焦校验 validate-lattice-surfaces+自动生成平面→2 延伸方向 2D/3D→3 宇宙调色板→4 画布涂色+3D 子预览→5 保存，保存 cells 反算覆盖 raw）+ `LatticeCanvas.tsx`（矩形 CSS grid / 六棱柱 hexGrid 蜂窝涂色）+ `LatticePreview3D.tsx`（useThreeCanvas+hexPrism+computeCameraParams 跟手重建）+ `three/useThreeCanvas.ts`+`three/hexPrism.ts` + `universeGroups.ts`+`useDragToGroup.ts`（按 U 分组显示 + 拖组头改 u）+ GeometryTab（格阵徽标列/⬚ 栅格编辑按钮/按 U 分组 toggle）+ CellEditDialog（格阵字段分组入口）+ 跨语言 golden `__golden__/latticeGolden.json`（backend schema 产出，Python/TS 同断言）；门禁 vitest **449/0**（基线 412 + 新增 37）+ tsc EXIT 0 + vite build EXIT 0；**画布不匹配提示已加**（QA 建议3：条目流≠dims 乘积 → 非阻塞横幅）
  - **网格计数（FMESH/TMESH）3D 体积可视化**（独立「3D 结果」窗口）：体积渲染（`glslVersion:GLSL3`）+ 相机 offset 居中 + 图层级半透明 + 自适应色阶下限 + 不相交并集取景 + A1.2 不匹配警告横幅
  - **PTRAC 粒子径迹可视化**（独立「3D 径迹」窗口）：类型三色 × 能量渐变 + 密度抽样 + NPS 高亮 + 自动探测
  - **OUTP 输出解析/绘图/导出 CSV**（`app/outp_parser.py` 纯 stdlib 容错 + `tallyChart.ts` SVG 折线图 + BOM CSV；MCNP6.1 紧凑布局 + F1/F2/F5 泛化）
  - 条件编译行（#ifdef/#else/#endif）、全行拖拽排序
  - E0/En/T0/Tn 网格（线性/对数/自定义）、三种源模式（固定/SDEF/KCODE）、SSW/SSR 面源
  - **文本↔表单双向互转**：材料/几何/计数三标签页（深模块 `useSectionTextMode`）
  - MCNP 检测与一键运行、内联参考文档
- **用户真实数据档案**：`D:\MCNP\new\claude\meshtal`（tally14/p；旧卡=点探测器周围 1×2×2 网格，新卡=±2000 全域 20×20×10）；模型=原点钨板（rpp -1 1 -1 1 0 1）+ 真空 so 1000/2000；输出样本 `tests/fixtures/simple_tally.outp`、`tests/fixtures/real_meshtal_jk.meshtal`
- **已知阻塞**：无

## §3 项目目录结构速查（语义记忆 · AI 定位代码用）

> 修改功能时先查此表定位文件，避免全盘扫描。

| 目录路径 | 功能说明 | 涉及 Agent |
| :--- | :--- | :--- |
| **Python 核心引擎（app/）** | | |
| `app/models.py` | 数据模型：DeckData/CellData/MaterialData/SourceData/BasicSettings/TallySettings/AdvancedSettings 等 dataclass | 后端 |
| `app/generator/inp_generator.py` | INP 生成主引擎（**已知技术债集中地，见 §4 末尾**） | 后端 |
| `app/generator/inp_parser.py` | INP 解析入口 | 后端 |
| `app/generator/parsers/{core,lines,sections,validator}.py` | 解析管线（行/分段/校验） | 后端 |
| `app/generator/validator.py` | 校验逻辑 | 后端 |
| `app/freecad_preview.py` / `_freecad_csg_worker.py` | FreeCAD 3D CSG 求值（子进程） | 后端 |
| `app/stl_cross_section.py` / `_freecad_cross_section_worker.py` | 截面（numpy 切 STL，不依赖 FreeCAD） | 后端 |
| `app/step_importer_geouned.py` / `geouned_worker.py` | GEOUNED STEP→MCNP 转换封装 | 后端 |
| `app/step_importer.py` / `freecad_locator.py` | STEP 导入 / FreeCAD 定位唯一入口 | 后端 |
| `app/xsdir_db.py` / `material_presets.py` / `material_library.py` | xsdir 截面数据库 / 预设材料库 / **用户材料库持久化（深化，custom/override、导入导出、xsdir 反向索引、组成自洽）** | 后端 |
| `app/outp_parser.py` | **OUTP 输出解析（纯 stdlib 容错，V1.7.2.2 新增）** | 后端 |
| `app/mctal_parser.py` / `app/sweep.py` | **mctal 输出解析（k-eff/收敛/tally）** / **参数扫描纯函数（对齐 OWEN sweepCore）** | 后端 |
| `app/meshtal/` | 网格计数解析/体积构建/配色/cache/deck_match/worker（8 模块） | 后端 |
| `app/ptrac/` | PTRAC 粒子径迹解析 + worker | 后端 |
| `inputcard_mcp/` | **AI 接入 MCP server（本地 stdio，6 工具：read/generate/validate/list_section/patch_section/add_shape，按语义段全量读写；打包用 `mcnp_bridge --mcp-server` 分派）** | 后端 |
| | | |
| **前端（gui/src/）** | | |
| `gui/src/App.tsx` | 主界面（顶栏/导入/生成/保存恢复/主题） | 前端 |
| `gui/src/components/` | 标签页组件：BasicSettings/MaterialTab/GeometryTab/SourceTab/TallyTab/AdvancedTab/OutputTab | 前端 |
| `gui/src/components/Preview3D.tsx` / `Preview3DWindow.tsx` | Three.js 3D 预览（独立窗口） | 前端 |
| `gui/src/components/CrossSectionView.tsx` / `CrossSectionWindow.tsx` | 平面截面（独立窗口） | 前端 |
| `gui/src/three/` | 3D 深模块：cameraParams/renderGate/cellMaterial/TickGrid/axisConfig（轴单一事实来源）/planeOffset（截面平面坐标换算）/quickCellPreview（快捷建栅元线框） | 前端 |
| `gui/src/volume/` | 体积可视化 11 模块（volumeShader/VolumeRenderer/colorize/alignWorld/downsampleRequest/fmeshState/ColorLegend/FMeshForm/VolumeControlPanel/ResultWindow/surfacesAABB） | 前端 |
| `gui/src/ptrac/` | PTRAC 径迹 3D 窗口模块（trackColors/PtracRenderer/PtracWindow 等） | 前端 |
| `gui/src/utils/quickCell.ts` / `gui/src/components/QuickCellDialog.tsx` | 快捷建栅元：纯函数生成（编号/校验/RCC/RPP/SPH/**HEX/TET**）+ 弹窗 | 前端 |
| `gui/src/utils/useQuickAddOverlap.ts` | **快捷建栅元重合检测+补集决策深模块（GeometryTab/Preview3D 共用）** | 前端 |
| `gui/src/utils/batchCellEdit.ts` / `gui/src/components/BatchCellEditDialog.tsx` | 栅元列表批量编辑：纯函数应用（空字段=不改、曲面只追加）+ 弹窗 | 前端 |
| `gui/src/utils/rawOverrides.ts` | **raw_overrides 纯函数构造（V1.7.2.2 新增，含 sdef）** | 前端 |
| `gui/src/utils/tallyChart.ts` | **OUTP 结果 SVG 折线图纯函数（V1.7.2.2 新增）** | 前端 |
| `gui/src/utils/DeckContext.tsx` | **单一权威表单状态**（localStorage 键 `mcnp_workspace_v1`） | 前端 |
| `gui/src/utils/useSectionTextMode.ts` / `sectionConvert.ts` | 文本↔表单互转深模块 + API 封装 | 前端 |
| `gui/src/utils/gridState.ts` | E0/En/T0/Tn 网格解析/序列化深模块 | 前端 |
| `gui/src/utils/backend.ts` / `dataCollector.ts` / `contract.ts` | 后端生命周期 / 表单收集 / 数据类型 | 前端 |
| | | |
| **后端（gui/backend/）** | | |
| `gui/backend/api_server.py` | **HTTP 后端总入口**（路由表见 api.yaml，端口 5001） | 后端 |
| `gui/backend/mcnp_bridge.py` | 打包后 sidecar 启动器（含 `--meshtal-worker` 分派） | 后端 |
| `gui/backend/generate_step.py` | STEP 生成（备用） | 后端 |
| | | |
| **窗口外壳（gui/src-tauri/）** | | |
| `gui/src-tauri/tauri.conf.json` | 无边框窗口、sidecar 配置（externalBin: python） | 后端 |
| `gui/src-tauri/src/main.rs` | Tauri Rust 入口（close_window / open_volume3d_window 等） | 后端 |
| | | |
| **文档** | | |
| `README.md` | 项目总览（技术栈/功能/打包说明/项目结构） | — |
| `app/docs/` | MCNP 参考文档（曲面卡/FN 卡/输出卡/PRINT/C810/源分布/sample_format） | — |
| `app/UI_ARCHITECTURE.md` | UI 架构说明：三层边界/启动链路/deck JSON 契约/raw_overrides/往返保真/技术债地图 | 架构师 |
| `docs/contracts/api.yaml` | **OpenAPI 3.0 契约**（30 端点，每 path 带 operationId，防漂移闸门验证） | 架构师 |
| `docs/CHANGELOG.md` | **完整变更流水档案（2026-08-22 起，历史 §8 外置于此）** | 项目经理 |
| `docs/backend-changes.md` / `frontend-changes.md` | 后端/前端逐批改动清单 | 架构师 |
| | | |
| **测试** | | |
| `tests/` | **测试网**：unit + parser + integration（含契约闸门/真实 HTTP），pytest **573** 绿；`gui/test/` vitest **358** 绿（含 jsdom DOM 交互测试） | 测试 |

## §4 关键架构决策 ADR（语义记忆）

> ⚠️ 本 § 编号被 docs/contracts/* 引用，**不得改名**。

| 决策 | 理由 | 日期 |
| :--- | :--- | :--- |
| 后端用 Python 标准库 http.server，不用 Flask | 减少依赖，PyInstaller 打包 sidecar 更简单 | — |
| 前端单一权威状态在 DeckContext（localStorage 工作区） | 8 个标签页共享一份数据，避免多源状态冲突 | — |
| 文本↔表单互转按 section 维度做深模块（useSectionTextMode） | 材料/几何/计数三处共用一套进出文本模式逻辑 | 近期 |
| 3D 预览用 FreeCAD 子进程 CSG 求值输出 STL | FreeCAD 精确几何；STL 保留供截面复用（numpy 切），不重复调 FreeCAD | — |
| 截面不依赖 FreeCAD，直接 numpy 切 STL | 独立窗口即时响应，无需 CAD 内核 | — |
| GEOUNED 随程序 vendor 打包，用户只装 FreeCAD | STEP 导入开箱即用；FreeCAD 经 locator 检测/手动指定 | — |
| 全部代码遵循**深模块原则**（用户全局记忆 codebase-design-always） | 小接口覆盖复杂行为，AI 友好、可测试 | — |
| **P1 多源/分布 SDEF 表示统一**（`SDEF_FIELD_SPECS` 表驱动 + 字段序 POS 首位 + D-index 由 `dist_params` 位置决定） | kitchen-sink R1/R4 字节不动点要求多源生成与分布回放逐字节一致 | 2026-08-12 |
| **P1 分布注释作为生成器横幅词汇**（`multi_source_comment_banner` 进 `is_generator_banner`） | 复用 F-A 方案 C 的词汇冻结机制，注释不漂移不重复 | 2026-08-12 |
| **P1 raw_overrides 收敛为 `_apply_raw_override` 助手**（1145 raw_tally 门控保留） | 消除 8 处复制粘贴 | 2026-08-12 |
| **3D 预览 deck 指纹缓存**（`app/preview_cache.py`，LRU 上限 3） | 打开卡真凶=全量重建 3.30s；缓存命中 ≤1s | 2026-08-12 |
| **前端 3D 拆深模块**：TickGrid/renderGate/cellMaterial/computeCameraParams | 交互卡真凶=纹理泄漏+无条件渲染+透明 overdraw；大坐标深度超 2^24 | 2026-08-12 |
| **前端后端地址收敛 `127.0.0.1:5001`** | 规避 Chrome Happy Eyeballs 每请求 300-500ms 延迟 | 2026-08-12 |
| **重合栅元几何检查走方案 A（FreeCAD 精确布尔 + AABB 预过滤）**，独立 `/api/check-overlap`；纯分类下沉 `app/overlap_classify.py`；结果同指纹落 preview_cache | 反馈 #7（参考 VISED，P2）；弃 B（STL 不封闭）/C（AABB 伪报率高）；独立端点不污染 preview-3d 契约；**本轮不施工仅存档** | 2026-08-13 |
| **MCNP 卡类型唯一权威源=官方 C810.pdf**；`docs/contracts/card-lexicon.md`（词条目录+解析器清单+差异表）与 `app/docs/` 蒸馏 md 均为**派生**，须随 PDF 更新 | 反馈 #1 FM 漏识别暴露系统性缺陷=解析器卡类型清单未与知识库对齐 | 2026-08-13 |
| **网格计数（FMESH/TMESH）3D 体积可视化契约**（`docs/contracts/meshtal-visualization.md`，16 节） | 对标 VISED；用户拷问敲定全部澄清项；测试先行 + 零新依赖红线 | 2026-08-14 |
| **meshtal-texture 返回标量帧 Uint8，前端 colorize CPU 上色**（python/TS 双端 golden sha256 对照） | 改色阶只重跑本地 colorize；Uint8+CPU 上色避开 float 纹理坑；双端 golden 防漂移 | 2026-08-14 |
| **体积窗口独立场景，不改 Preview3D.tsx 主组件**（复用纯模块）；几何外壳与体积盒共享 offset 对齐；关闭不清 preview-3d STL 会话 | 复用会污染 preview3d-performance 契约 | 2026-08-14 |
| **meshtal 后端落地细节**：数据行列序按实际 MCNP `[Energy] [Time] X Y Z Result RelError`；colormap golden = t-space 插值 round-half-even；worker 模块顶只 stdlib；大文件走子进程 + cache 不阻塞 5001 | golden 是 §4.3.1 跨语言防漂移强契约；"Total" 汇总行跳过 | 2026-08-14 |
| **3D 预览截面坐标双修**：后端 on-plane 顶点作交点 + 共面三角面贡献外轮廓边 + `_join_loops` 容差走环；前端 `planeOffset.ts` 换算 D_raw=D_disp+n·center | 面重合切割旧实现返回 0 环/错环 + 多环被贪心串接；预览归一化平移与后端原始坐标不一致 | 2026-08-18 |
| **快捷建栅元模块化**：纯函数 `quickCell.ts` 集中编号/校验/生成；斜向用 6 局部平面 + TRn（行=局部轴方向余弦）而非 RPP+TR | 规避 worker 对带 Placement 宏体半空间补集布尔缺陷；编号/密度带出/文本模式禁用集中，vitest 可测 | 2026-08-18 |
| **OUTP 解析：pymcnp 正确 API（`Outp.from_mcnp(text).to_dataframe()`）优先 + `app/outp_parser.py` 纯 stdlib 容错兜底**；前端 `tallyChart.ts` 纯函数 SVG 绘图 + CSV 加 BOM | pymcnp 0.9.1 只认 MCNP6.2 布局、MCNP6.1 紧凑布局解析为空；兜底支持 energy 列/total 行可有可无、F1/F2/F5 泛化 | 2026-08-19 |
| **IMP 归一化在生成器层（`_generate_cells`）单一权威**：任一结构化栅元写 imp_n/p/e → 全部补齐，缺省补默认重要性 1 | 部分栅元有 IMP、部分没有 → MCNP 硬规则 fatal；表单/导入/快捷建栅元全路径生效 | 2026-08-19 |
| **SDEF 表单模式回退分支**（`_sdef_dispatch`）：distribution/sdef 无分布时 sources 优先（保 R1 不动点）→ 表单字段有值合成单源 → 全空 `[]` | 表单字段写 `adv.sdef_*` 但无分布时旧逻辑返回空 → INP 无 SDEF | 2026-08-19 |
| **含 GQ/SQ 栅元走纯 numpy 体素 CSG（`app/mc.py` + `app/voxel_csg.py`），去掉 vtk 依赖**；`mesh_cell_polydata(ast, surfaces_by_num, tr_cards, B, res)` 返回 (vertices, triangles)；TR 求值前 `p_local=rotate⁻¹·(p_global−o)`；**带 TR 的有界曲面 AABB 经 8 角点变换求全局紧盒（`_transform_aabb`），无界才保守全盒**；**margin 按实际扫描盒间距（勿用全局 B）**；失败降级包围盒 + `栅元 N: GQ/SQ 网格化失败` 告警 | worker 跑在 FreeCAD 自带 Python（无 vtk）→ GQ/SQ 兜底必失败；OCC 对网格化二次曲面半空间布尔不可靠；实测 TR 被完全忽略 + B=500 下全盒/margin 坑致小栅元空网格 | 2026-08-22 |
| **GQ/SQ 渲染后续增强（同日）**：① **2D 解析切片**（`app/analytic_slice.py`）——切割平面逐点解析求值 + 2D marching squares 轮廓，preview-3d 会话存 deck 快照、cross-section 对 GQ/SQ 栅元自动走解析切片；② **切线平面法快路径**（`voxel_csg._tangent_plane_mesh`）——单个内侧椭球/球/圆柱 + 平面封口 → 切线半空间 + 凸裁剪（Sutherland–Hodgman + 盖面极角排序），水密；椭球 162 方向 + 绕中心体积校正（无封口）/642 方向（有封口），圆柱 48 段；union/补集/多二次曲面/锥回退 MC | 截面轮廓位置精度只取决于解析求值（STL 受网格分辨率限制）；切线路径三角形数 ~600 vs MC ~10 万；OWEN csgScene 的做法（金螺旋方向分布不均 + 边链盖面在贴面顶点退化）不能直接照搬 | 2026-08-22 |

## §5 核心业务规则（语义记忆 · 必读）

- **版本号规则（上级硬规则）**：**任何 bug 修复批次严禁提升版本号**（改多少轮 bug，文件版本号恒为当前版本；PM 曾擅自升到 1.7.2/1.7.3 属违规，已回退并记此规则）。仅**实际新功能**上线才由上级重新指定版本号——快捷建栅元新功能用户指定 **1.7.2**（2026-08-18）。打包时版本四处+锁文件（tauri.conf.json / package.json / Cargo.toml / README 徽章 / Cargo.lock）必须一致；**Cargo/tauri 只接受 `主.次.修订`**，四段号（如 1.7.2.2）会构建失败，仅可作批次号。
- **依赖红线（上级 2026-08-14 更新）**：**新依赖一律须用户批准，且由用户指定安装位置**（2026-08-23 更新：不再默认零新依赖；评估时列出依赖名/用途/体积/许可/替代方案，批准后按用户指定位置安装，如 node_modules 常规位置或 vendored 目录）；**严禁自动运行 npm install / npm ci / pip install**（用户高度敏感，违反即打回）；测试不得 import gui.backend.api_server（模块级 pyvista/FreeCAD 探测污染）。**2026-08-22 用户批准的唯一例外**：`jsdom` / `@testing-library/react` / `@testing-library/dom`（devDeps，用于 SweepDialog DOM 组件测试，已写入 package.json）。
- **权威源**：MCNP 卡类型唯一权威 = `D:\MCNP\MCNP6\C810.pdf`（实际 = MCNP5 卷 I+II 全文 + 发布说明；卡格式权威章 = MCNP5 卷 II Ch.3，PDF 页 526-691）；`app/docs/` 蒸馏 md 与 `docs/contracts/card-lexicon.md` 均为**派生**，须随 PDF 更新。
- **DeckData 是聚合根**：前端 DeckContext ↔ 后端 generate/parse 全走 DeckData 单对象，避免参数膨胀。
- **密度写在栅元卡（CELL）上**，材料卡（Mm）只含 ZAID+份额，不含密度。
- **栅元/材料/计数行支持判别联合**：`kind=="cell"|"raw"`（栅元）、`kind=="nuclide"|"raw"`（材料）——`raw` 行承载 `#ifdef/#else/#endif` 原样条件行。
- **文本模式状态存在 deck.textMode[section] + deck.rawOverrides[section]**；进文本模式前必须由后端先生成当前表单的文本（section-to-text），防数据丢失。
- **STL 会话**：3D 预览生成的 STL 保留在 `_STL_SESSION`，供截面复用；只在关预览窗口/清空时 `/api/clear-stl` 删除。
- **曲面文本解析**：GEOUNED 常见 `*TRn` 后缀或 `100*` 前缀的 TR 引用，均需提取 transform；P 卡 `A B C D` 系数形式需转三点定义（注意法向同向性）。
- **SDEF 三种模式**：`fixed`（固定点源）/ `distribution`（SDEF 分布源，SI/SP/DS 结构化 JSON 优先于 sdef_raw_text）/ `kcode`（KCODE/KSRC/HSRC）。
- **前端契约层**：`sectionConvert.ts` 只认 `{status:"ok"}` 成功响应，`/api/text-to-section` 返回 `{data}`，`/api/section-to-text` 返回 `{text}`。
- **测试时间限制（上级 2026-08-22）**：所有测试/构建命令必须加**硬性时间限制**——探活/HTTP 请求/PyInstaller 等长命令用 `Start-Process` + `WaitForExit(超时)` + `Kill`，超时即杀并明确报错，严禁无限挂起。

## §6 踩坑与排雷指南（情景记忆 · 经验教训）

- **vite dev 在本机挂死（2026-08-15 实测）**：node 24.18 + vite 5.4.21 + @vitejs/plugin-react 4.7.0 组合下 vite dev 接收请求后零响应（最小空项目正常，加载项目配置即挂）→ 浏览器白屏/转圈。**启动 bat 已改为 vite build + python http.server 静态服务 dist**，不再依赖 vite dev。
- **5001 端口劫持（2026-08-15 实测；2026-08-24 阶段2 验收复现；2026-08-24 Wave 2a 再复现）**：Windows SO_REUSEADDR 允许多进程同绑 5001——打包版 sidecar 与 bat 起的 api_server 可同时"监听"，请求被劫持分流。bat 已加 netstat 占用检测（有后端就复用）；诊断用 `Get-NetTCPConnection -LocalPort 5001` 查 OwningProcess。**阶段2 复现实证（QA 独立验收）**：运行中的旧打包版 `D:\MCNP\MCNP输入卡生成器\python.exe -u backend/mcnp_bridge.py`（无新端点）劫持契约闸门 HTTP 用例 → 新端点 `test_http_validate_lattice_surfaces` 404；其余旧端点用例由劫持端也能通过，**只有新增端点才暴露劫持**。**Wave 2a 再复现**：残留旧 server（PID 4776，跑旧代码无 cycle 判环）劫持 5001 → cycle 端点 500 递归错误（新端点/新逻辑才暴露）；杀 PID 复绿。教训：验收新端点/新逻辑前先清 5001（杀旧 sidecar/旧 server/关主程序），或契约闸门 fixture 起子进程前检测端口占用并明确报错；**浏览器复验前必须确认 5001 跑的是新代码**。**Wave 2a 复发（2026-08-24）**：pytest 残留的旧 api_server 子进程（PID 4776，跑**旧代码**）劫持 5001 → 新 cycle 端点 500（maximum recursion depth exceeded，traceback 行号与当前文件不符=老代码跑 cycle 无判环）。杀 PID 后复绿。诊断要点：HTTP 500 且 traceback 行号对不上当前文件 → 先查 `netstat -ano | grep 5001` 占位进程，别先改代码。
- **P0 体积层渲染两弹（2026-08-15 实测，真实渲染复现）**：① three r160 WebGLProgram 对 RawShaderMaterial **前置 `#define SHADER_TYPE` 块** → shader 首行 `#version 300 es` 不再首位 → GLSL 编译失败 → **体积层自引入从未渲染**（静默，快照测试只锁字符串不编译一路绿灯）。修复：shader 去首行 `#version` + `glslVersion: THREE.GLSL3`。② 相机未 offset：物体按 offset 平移到原点但相机用未 offset 世界盒 → target 对空、画面错位。修复：`applyOffsetToBox` 纯函数。**教训：WebGL 类问题必须 headless 真渲染验证，不能只靠快照测试**。
- **3D 预览截面"部分实体切错"（2026-08-18 实测）**：① 切割平面恰与实体面重合（模型底面 z=0、相邻栅元共享面）时旧 `slice_stl_segments` 对 on-plane 顶点 continue → 0 环/错环；共面三角面须贡献出现 1 次的外轮廓边。② 预览归一化平移与后端原始 STL 系不一致 → 切位偏移；2026-08-18 起主预览**已去归一化**（显示系=原始系，modelCenter 恒 0，`planeOffset` 换算恒等但保留防回归）。③ 坐标轴单一事实来源 `axisConfig.ts`（X 红/Y 绿/Z 蓝），不要再内联写 dirs。
- **FreeCAD 对「旋转宏体半空间」补集布尔失效（2026-08-18 实测）**：`RPP ... *TRn` 正侧 = bound.cut(内盒) 再 apply_trn（带 Placement 复合体），对 `-曲面` 求补集返回垃圾体积（1.7e8 > 整盒 1.25e8）。斜向六面体一律改用 6 个局部 PX/PY/PZ + `*TRn`（普通平面布尔可靠）；轴对齐 RPP 宏体无 TR 正常。quickCell.ts 已按此实现。
- **大网格零通量背景涂蓝（2026-08-15 用户实测）**：色阶下限=0 时精确 0 值也被涂蓝遮模型。已修：色阶下限**自适应** = `minPositive×0.5`（曾用 sqrt 规则切太狠致"只显示一个面"，已按用户反馈改）；注意纹理是线性归一化 u8，微小值会被量化成 0（minPositive 从 u8 字节重建，勿用原始文件最小值）。
- **GQ/SQ 3D 预览 3 连坑（2026-08-22 实测，静态审查发现不了）**：① `app/mc.py` 邻接索引 `t_ids`/`slots` 的 repeat/tile 与「先全部 (0,1)、再 (1,2)、再 (2,0) 的块状边数组」错位 → 朝向传播全乱（signed volume≈0、假碎片/假冲突）；必须 `t_ids=tile`、`slots=repeat`。② BFS 波前同波重复三角形未去重 → 指数膨胀到 4 千万+（内存炸）；用一次性 bool 数组去重。③ 带 TR 小栅元在大 bound（B=500）下：TR 曲面 AABB 必须经 8 角点变换（`p_global=o+p_local@R`）求全局紧盒，保守全盒会让 32³ 粗扫漏检 → 空网格降级包围盒；margin 必须按**实际扫描盒**间距 `(scan_hi−scan_lo).max()/(coarse−1)×1.1`，用全局 `2B/(coarse-1)` 在 B=500 时达 35cm 把细化盒撑爆。水密断言必须用「每条无向边恰被 2 个三角形使用」的边计数法（**vtkFeatureEdges 对 marching cubes 网格误报边界边**）；`*TRn` 求值前必须 `p_local = rotate⁻¹·(p_global − o)`。
- **GQ/SQ 后续增强 3 连坑（2026-08-22 实测）**：① **凸裁剪盖面**：顶点恰落在裁剪面上（dist≈0）时跨边条件会漏掉该交点 → 盖面缺顶点被丢弃 → 三角形破洞（228 条开放边）；`cut()` 端点贴面返回 `keep()`、盖面收集贴面顶点本身。OWEN 的边链盖面法在细密切线平面下会退化丢面（162 面球只出 35 面），改用 Sutherland–Hodgman + 盖面绕质心极角排序。② **金螺旋方向分布不均**：外接多面体顶点半径到 1.08r+、体积误差 8%+，改二十面体细分（162/642 方向）；162 方向外接误差仍 ~2.1% → 无封口时绕中心体积校正 λ=(V_true/V_mesh)^(1/3)（体积精确）、有封口时用 642 方向（区域体积无法解析）。③ **解析切片 marching squares 16 格表 case 12（{2,3} 上边在内）应为 (1,3) 而非 (0,1)**；`_plane_halfspace` 的 pos/neg sgn 与 surface_fn 正侧约定相反（pos 侧要取 −法向）。
- **材料库深化 3 坑（2026-08-30 实测）**：① **嵌套浮窗被 `backdrop-filter` 裁剪**——`FloatingDialog` 用 `backdrop-filter: blur(16px)` 会创建 containing block，使嵌套其中 `position:fixed` 的子弹窗相对父定位、被父 `overflow:hidden` 裁剪。修法=子弹窗用 `createPortal` 渲染到 `document.body`（ExamplesDialog/GeometryTab 同法）。② **模块级缓存被 `useMemo` 冻结不刷新**——`useMaterialLibrary` 用 `useMemo(()=>entries,_cache…,[loaded])`，但 `entries` 依赖模块级 `_cache`（不在 deps），save/remove 后 `_cache` 更新 + notify 触发重渲染，`useMemo` 仍返回旧缓存 → 面板不刷新。修法=去掉 `useMemo` 每次读最新 `_cache`。③ **edit 改写 `.ps1` 丢 UTF-8 BOM**——Windows PowerShell 5.1 按 GBK 读无 BOM 的 UTF-8 中文就乱码解析崩溃；修法=用 `[System.Text.UTF8Encoding]::new($true)` 重存为带 BOM。

- **OUTP 解析误用 pymcnp 构造函数（2026-08-19 实测）**：`pymcnp.Outp(text)` 是构造函数非解析入口，恒报 TypeError；正确入口 `Outp.from_mcnp(text).to_dataframe()`。且内置 pymcnp 0.9.1 Tally_4 只认 MCNP6.2 布局，MCNP6.1 紧凑两列解析为空 → 需 `app/outp_parser.py` 兜底。
- **测试笔误陷阱（fixtures 实测）**：① valid_39.meshtal 的 tally number 是 **4 不是 1**（须取自 parse 响应 `tallies[].number`）；② preview-3d 单栅元 material="0" 是 void → `include_void=False` 跳过 → 空 stl_files（冒烟 deck 须用非 0 material）。
- **meshtal-parse 元数据缓存**：已闭环（`_mode_parse` 先 `get_manifest` 命中即返回，实测二次 0.23s）；`meshtal_cache._MANIFEST_VERSION=2` 使旧磁盘缓存失效。
- **P0/P1 技术债全清偿（2026-08-12）**：引擎缺陷 F-A~F-H + F#1~F#7 全修，R1-R4 不动点成立；`inp_generator.py` 仍为**技术债集中地**（见 docs/backend-changes.md + UI_ARCHITECTURE.md 技术债地图）。
- **FreeCAD 对「圆柱 ∩ 平行于轴平面」布尔恒空（2026-08-24 三阶段验收实测，QA 独立复现）**：`_build_one_universe` 把格元盒裁剪平面追加进 universe cell 表达式做 CSG 交集（`-1 -61 +62 ...`），圆柱（C/CZ 半空间）∩ 任一 PX/PY（平行轴平面）→ **空 STL（84B/0 三角形）**；圆柱 ∩ PZ（垂直轴）正常（4884B/96 三角）、纯 box ∩ 盒正常。现有 preview-3d 走 worker post-hoc bound 盒裁剪（solid-solid boolean）对同 deck 全部非空——**裁剪必须走 solid-solid，不得把平面塞进 cell 表达式**。影响：格阵 universe 实例化详细模式对燃料棒等圆柱格元不渲染。
- **QA API 直验两个易错点（2026-08-24 最终复验实测）**：① `/api/generate` 期望 **deck 字段在 body 顶层**（`deck_from_json(data)` 直接吃 body），不是 `{"deck": deck}` 包裹——包错层会静默生成空 INP（实测 67B）；`/api/section-to-text` 才是 `data.get("deck")`。② 生成器把关键字**大写**输出（`LAT=1`/`U=10`/`FILL=`/`IMP:N`），断言匹配须大小写不敏感（`inp.upper().replace(" ","")`）。
- **FreeCAD 圆柱∩盒平面恒空已闭环修复**：`_build_one_universe` 不再把 6 平面塞进 cell 表达式，改合成单 RPP 宏体 `-<num>` 做 cell solid ∩ RPP 盒实体 solid-solid common（与 preview-3d bound 同机制）；0 三角 STL 显式丢弃（前端回退占位盒）。复验 17×17 全部 12 个 universe cell STL 非空、cell1=96 三角与 preview-3d 基线一致。
- **契约文档**：docs/contracts/api.yaml 覆盖全部端点；漂移闸门 `tests/integration/test_api_contract.py` AST 断言 handlers ↔ api.yaml 双向一致（含真实 HTTP）。
- **Cargo.toml 版本隐患**：v1.6.4 曾漏改（停在 1.6.3）；Tauri 以 tauri.conf.json 为权威不影响出包，但**版本四处+锁文件**必须一致。
- **打包注意（详见 §9）**：Tauri build 需要 `RUSTUP_HOME/CARGO_HOME` 指向 D:\rust；sidecar 用 PyInstaller（spec：`gui/mcnp_sidecar.spec`，产物名 "python"）；**6.2 时效校验**（tauri 增量编译不刷新 target/release 的 sidecar，必须手动核对 mtime/覆盖）；后端窗口关闭时经 Rust `close_window` 命令一起退出。

## §7 技术争议与决议（语义记忆）

| 争议点 | 方案 A | 方案 B | 最终裁决 | 裁决理由 |
| :--- | :--- | :--- | :--- | :--- |
| F-A R1 不动点：生成器 C 注释头泄漏，解析器吸收 vs 生成器改头 | 解析器吸收防护（仅节头词汇精确剥离） | 生成器改头为不可吸收形式 | **方案 C，以 A 为主、B 为辅**（2026-08-12） | MCNP 注释只有 C 一种形式，现有解析器对任意 C 行都会在栅元注释/曲面 verbatim/other_cards 三路吞掉，不存在合法且三阶段天然惰性的注释形式。方案 C 把节头冻结为 banners.py 单一事实来源，生成器与解析器共享，R1 测试为漂移兜底；用户可见 INP 输出风格保留 |

## §8 变更日志（情景记忆 · 里程碑纲要，完整流水已外置）

> ⚠️ 本 § 编号被 docs/contracts/* 引用，**不得改名**。完整逐条流水（2026-08-11 起）见 **`docs/CHANGELOG.md`** + `docs/backend-changes.md` + `docs/frontend-changes.md` + git log。
>
> **维护规则**：每次批次完成后，在 `docs/CHANGELOG.md` 追加新条目；本 § 只在里程碑定型时更新一行。

### 版本里程碑

| 版本 | 时间 | 内容 |
| :--- | :--- | :--- |
| **v1.7.4** | 2026-08-27 | **3D 预览 MCNP 窗口裁剪修复 + U 分组侧边栏**（用户指定新功能上线升版）：① 实体=universe∩格元盒∩容器cell，修超壳/重叠外壳 + 无限水虚假水块（BEAVRS 超壳叶 48→16）；② 3D 预览侧边栏改 U 分组 + 保留未分组栅元；disc 改用容器裁剪 STL、subPitch 半径；版本五处同步 |
| **v1.7.4（材料库深化，沿用版本待上级指定）** | 2026-08-30 | **材料库深化**（新功能）：用户可编辑持久材料库（custom/override、`D:\MCNP\material\material_library.json`、D盘回落 `%APPDATA%`）、导入导出 JSON·CSV（冲突三选 + 内容一致自动跳过）、xsdir 反向索引 + 组成自洽校验、📚 材料库管理面板、MT卡/其他随预设贯通；修复：编辑弹窗 `backdrop-filter` 裁剪（`createPortal`）、编辑保存后列表不刷新（去 useMemo）、材料库内编辑隐藏预设区、生成 INP 的 MODE+NPS 卡移数据卡段末尾；README 与 exe 同级放入；spec `_keep_py` 加 `material_library.py`。门禁 pytest **737/0** + vitest 534/535（flaky 隔离绿）+ tsc/build 过 |
| **GQ/SQ 预览修复 + 渲染增强 + OWEN 四项 + 参数扫描前端**（未 commit/发版，文件恒 1.7.2） | 2026-08-22 | 纯 numpy MC 去 vtk + TR + 解析切片 + 切线平面法 + BEAVRS/17×17 夹具 + mctal 解析 + 校验规则交叉核对（validator +3 规则）+ 参数扫描（sweep 模块 + 2 端点 + SweepDialog 前端 + DOM 交互测试）；门禁 pytest **573/0** / vitest **358/0** / tsc EXIT 0；打包冒烟通过；待 tauri build/部署 |
| **V1.7.2.2 批次**（文件恒 1.7.2） | 2026-08-19 | 4 修复进包：源卡文本模式漏生成 / SDEF 表单模式漏生成 + sdef_extra 往返 / IMP 归一化 / OUTP 解析+绘图+CSV（含 F1/F2/F5 泛化）；终版重打包部署，冒烟全过 |
| **v1.7.2** | 2026-08-18 | 新功能**快捷建栅元**（RCC/RPP/SPH 一键生成曲面+TR+栅元，8 次迭代打包）；3D 预览坐标轴/截面/取景修复批 |
| **v1.7.1** | 2026-08-15~16 | **PTRAC 粒子径迹可视化**交付 + 网格计数 3D 结果批（图层级透明/自适应色阶/并集取景）+ P0 体积层渲染两弹 + inp02 解析修复批 |
| **v1.7.0** | 2026-08-14 | 网格计数（FMESH/TMESH）3D 体积可视化大功能（meshtal/ 8 模块 + volume/ 11 模块 + 3 端点 25→28） |
| **v1.6.x** | 2026-08-11~12 | 文本↔表单双向互转 + P0/P1/P2 技术债清偿（F-A~F-H + F#1~F#7）+ 3D 预览性能（preview_cache/TickGrid 深模块）+ 词条专项 D-01~D-13 + 反馈 #1~#7 |

### 关键历史结论（压缩自 08-11~08-15 流水，细节见 CHANGELOG）

- 发布：**手动打包**（docs/手动打包方法.md）；release.bat 已停用（Git Bash MSYS 坑 + 自检失败）。
- 网格计数可视化 v1.7.0（FMESH/TMESH 体积渲染）；P0/P1 技术债清偿（251 绿）；3D 预览性能（preview3d-performance）；文本↔表单互转；用户 7 条反馈 + 词条专项 D-01~D-13（08-13）。

## §9 程序性记忆（操作手册 · 怎么做事）

### 打包链路（每次发布走此流程，详见 `docs/手动打包方法.md`）

> **打包唯一流程为手动**（`docs/手动打包方法.md`）。曾有一键脚本 `release.bat` / `scripts\release.ps1` 均已**废弃删除**（一键脚本曾解决第 ② 项 npm/npx 被 ExecutionPolicy 禁与 6.2 sidecar 时效坑，但整套一键能力已弃用）。当前**每次发布**按下面分步手动执行，**尤其 6.2 时效校验不可跳过**。

```
1. vite build                       （前端产物，~3-4s；node .\node_modules\vite\bin\vite.js build）
2. PyInstaller sidecar              （在 gui\ 下跑 gui/mcnp_sidecar.spec，产物名 "python"；
                                    核对 _keep_py / _keep_dirs 清单，如 outp_parser.py/meshtal/ 等新增模块）
3. 替换 binaries                    （把新 sidecar 的 python.exe + _internal 换进 target\release\）
4. tauri build                      （需 RUSTUP_HOME/CARGO_HOME=D:\rust；node .\node_modules\@tauri-apps\cli\tauri.js build）
5. ⚠️ 6.2 时效校验（必做）           （tauri 增量编译不刷新 target\release 的 sidecar！
                                    手动核对 python.exe mtime/体积，覆盖为新 sidecar）
6. 部署 D:\MCNP\MCNP输入卡生成器     （⚠️ 先杀运行中的旧主程序+sidecar，否则文件锁目录致 _internal 残缺）
7. 冒烟                             （用 sidecar python.exe 直跑不弹 GUI：xsdir-check / generate 定向卡 / preview-3d 出 STL）
```

**关键坑提醒**：① 6.2 时效坑**每次都命中**，不可跳过；② 部署前杀进程（锁目录）；③ 冒烟改 sidecar 直跑（GUI 窗口被关闭=后端退出，中断请求属正常）；④ 版本四处+锁文件必须一致（Cargo 不接受四段号）。

### 测试门禁（发布前必须全绿）

| 门禁 | 命令/位置 | 基线 |
| :--- | :--- | :--- |
| pytest | `tests/`（unit + parser + integration，含契约漂移闸门 test_api_contract.py 与真实 HTTP） | **573/0**（2026-08-22 起累计：voxel_csg / analytic_slice / owen 夹具 / mctal / validator 规则 / sweep） |
| vitest | `gui/test/`（含 quickCell 20 / volume 57 / volumeShader snapshot / sweepDialog DOM 6 等） | **358/0** |
| tsc | `gui/` 下 tsc 类型检查 | EXIT 0 |
| 漂移闸门 | handlers dict ↔ docs/contracts/api.yaml 双向一致 | 30 端点 |

**已知 flaky**：colorize 128³ 计时用例负载偶发 >50ms，隔离单跑即绿（非回归）。

### 版本发布纪律

- bug 修复批**严禁升版**；升版仅限新功能且由上级指定。
- 版本四处+锁文件同步：tauri.conf.json / package.json / Cargo.toml / README 徽章 / Cargo.lock。
- 侧边栏版本号读 package.json（单一来源，升版不再破）。


