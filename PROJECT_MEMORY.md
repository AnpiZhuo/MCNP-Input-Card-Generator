# 项目记忆文档（AI 速查手册）

> 最后更新时间：2026-08-22 —— **按人脑模型重组**（原「顶部横幅 + §8 流水混装」整理为「短期记忆 / 长期记忆」两区，完整流水外置 `docs/CHANGELOG.md`）。同日完成 **GQ/SQ 3D 预览修复 + 渲染后续增强 + OWEN 四项 + 参数扫描前端**：全部门禁绿（pytest **573/0** / vitest **358/0** / tsc EXIT 0）+ PyInstaller sidecar 重打包 + 打包版冒烟通过。
>
> **人脑模型组织说明**：
> - **◉ 短期记忆（工作记忆）**：只放"现在正在处理的事"——当前批次 / 工作区 / 待办。**容量小、变化快、随批次刷新**（人脑工作记忆约 7±2 项）。
> - **◉ 长期记忆（稳定存储）**：固化后不随批次变动的知识——**语义记忆**（是什么/为什么：身份/ADR/规则/目录）、**情景记忆**（发生过什么/经验教训：踩坑/里程碑）、**程序性记忆**（怎么操作：打包/测试手册）。
> - **记忆巩固规则**：批次结束 → 短期记忆区刷新；经验教训**固化**进长期记忆（§5 规则 / §6 踩坑 / §4 ADR）；详细流水**归档**进 `docs/CHANGELOG.md`（+ backend/frontend-changes.md + git log）。
> - **维护者**：项目经理（AgentTeams 记忆维护）。

---

# ◉ 短期记忆（工作记忆）—— 当前活跃上下文

> 只保留"正在处理"的信息。**批次完成后，本区随 CHANGELOG 归档一起刷新。**

## S1 当前批次：GQ/SQ 3D 预览修复（2026-08-22，施工完成，未发版/未 commit）

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

- **分支**：`feat/meshtal-volume`（主分支 `main`）。
- **工作树未提交改动**（git status 快照）：
  - 修改：`PROJECT_MEMORY.md`、`docs/CHANGELOG.md`、`docs/contracts/geometry-check.md`、`app/_freecad_cross_section_worker.py`、`app/_freecad_csg_worker.py`、`app/freecad_preview.py`、`tests/unit/test_preview_bound.py`、`tests/integration/test_preview3d_worker.py`、`gui/mcnp_sidecar.spec`
  - 新增：`app/quadric.py`、`app/voxel_csg.py`、`app/mc.py`、`tests/unit/test_voxel_csg.py` —— GQ/SQ 3D 预览修复施工（去 vtk + TR 变换），归属已确认。
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
- **许可**：All Rights Reserved（自有代码禁止盈利/未经许可发布）；开源组件各按自身许可

## §2 当前状态快照（语义记忆）

- **开发阶段**：已交付 v1.7.2（2026-08-18 打包）+ V1.7.2.2 批次（2026-08-19 终版重打包，4 修复进包）；后续功能（#7 重合检查）待用户排期
- **已完成功能**：
  - 8 标签页表单编辑（基本/材料/几何/源/计数/高级/输出）
  - INP 生成/导入（含拖拽）、工作区自动保存/恢复、4 套主题
  - 材料库（**97 种预设**：49 内置 + 48 PNNL-15870 精选同位素级；xsdir 校验 + 下拉自动填充密度）
  - 3D 预览（FreeCAD CSG，`#n` 栅元补集支持）+ 平面截面（STL numpy 切）+ STEP/GEOUNED 导入
  - **GQ/SQ 曲面 3D 预览**（2026-08-22）：含任意 GQ/SQ 的栅元走纯 numpy 体素 CSG（`app/mc.py`/`voxel_csg.py`/`quadric.py`），TR 变换正确、水密、无 vtk 依赖、打包可用
  - **GQ/SQ 精确截面（2D 解析切片）**（2026-08-22）：`app/analytic_slice.py` 在切割平面上解析求值 + marching squares 提取轮廓；**切线平面法快路径**（椭球/圆柱平滑水密网格，~600 三角形）
  - **mctal 解析 + 参数扫描**（2026-08-22）：`app/mctal_parser.py`（k-eff/收敛/tally，纯 stdlib）+ `app/sweep.py` + `/api/sweep-plan`（规划）/`/api/sweep-run`（执行，上限 50 组合）+ 前端 `SweepDialog.tsx`（参数编辑/组合预览/结果表/TSV 下载，OutputTab 入口）
  - **校验规则交叉核对**（2026-08-22）：`docs/contracts/validator-crosscheck.md`（OWEN rules.ts 映射）+ validator 新增 ZAID 格式/份额符号/S(α,β) 目标 3 条材料级规则
  - **BEAVRS/17×17/单棒卡进测试夹具**（2026-08-22）：`tests/fixtures/owen/` 解析基线回归
  - **快捷建栅元**（几何标签页「曲面卡 & TR 变换」⚡）：RCC/RPP/SPH 一键生成曲面+TR+栅元（编号顺延/材料密度带出/imp 勾选/实时线框预览，轴固定世界原点 Z 朝上）
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
| `app/xsdir_db.py` / `material_presets.py` | xsdir 截面数据库 / 预设材料库 | 后端 |
| `app/outp_parser.py` | **OUTP 输出解析（纯 stdlib 容错，V1.7.2.2 新增）** | 后端 |
| `app/mctal_parser.py` / `app/sweep.py` | **mctal 输出解析（k-eff/收敛/tally）** / **参数扫描纯函数（对齐 OWEN sweepCore）** | 后端 |
| `app/meshtal/` | 网格计数解析/体积构建/配色/cache/deck_match/worker（8 模块） | 后端 |
| `app/ptrac/` | PTRAC 粒子径迹解析 + worker | 后端 |
| | | |
| **前端（gui/src/）** | | |
| `gui/src/App.tsx` | 主界面（顶栏/导入/生成/保存恢复/主题） | 前端 |
| `gui/src/components/` | 标签页组件：BasicSettings/MaterialTab/GeometryTab/SourceTab/TallyTab/AdvancedTab/OutputTab | 前端 |
| `gui/src/components/Preview3D.tsx` / `Preview3DWindow.tsx` | Three.js 3D 预览（独立窗口） | 前端 |
| `gui/src/components/CrossSectionView.tsx` / `CrossSectionWindow.tsx` | 平面截面（独立窗口） | 前端 |
| `gui/src/three/` | 3D 深模块：cameraParams/renderGate/cellMaterial/TickGrid/axisConfig（轴单一事实来源）/planeOffset（截面平面坐标换算）/quickCellPreview（快捷建栅元线框） | 前端 |
| `gui/src/volume/` | 体积可视化 11 模块（volumeShader/VolumeRenderer/colorize/alignWorld/downsampleRequest/fmeshState/ColorLegend/FMeshForm/VolumeControlPanel/ResultWindow/surfacesAABB） | 前端 |
| `gui/src/ptrac/` | PTRAC 径迹 3D 窗口模块（trackColors/PtracRenderer/PtracWindow 等） | 前端 |
| `gui/src/utils/quickCell.ts` / `gui/src/components/QuickCellDialog.tsx` | 快捷建栅元：纯函数生成（编号/校验/RCC/RPP/SPH）+ 弹窗 | 前端 |
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
- **依赖红线（上级 2026-08-14 更新）**：默认零新依赖，但使用新依赖更好时就使用，需要用户批准；有更好的库须**先提出、批准后安装**；**严禁自动运行 npm install / npm ci / pip install**（用户高度敏感，违反即打回）；测试不得 import gui.backend.api_server（模块级 pyvista/FreeCAD 探测污染）。**2026-08-22 用户批准的唯一例外**：`jsdom` / `@testing-library/react` / `@testing-library/dom`（devDeps，用于 SweepDialog DOM 组件测试，已写入 package.json）。
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
- **5001 端口劫持（2026-08-15 实测）**：Windows SO_REUSEADDR 允许多进程同绑 5001——打包版 sidecar 与 bat 起的 api_server 可同时"监听"，请求被劫持分流。bat 已加 netstat 占用检测（有后端就复用）；诊断用 `Get-NetTCPConnection -LocalPort 5001` 查 OwningProcess。
- **P0 体积层渲染两弹（2026-08-15 实测，真实渲染复现）**：① three r160 WebGLProgram 对 RawShaderMaterial **前置 `#define SHADER_TYPE` 块** → shader 首行 `#version 300 es` 不再首位 → GLSL 编译失败 → **体积层自引入从未渲染**（静默，快照测试只锁字符串不编译一路绿灯）。修复：shader 去首行 `#version` + `glslVersion: THREE.GLSL3`。② 相机未 offset：物体按 offset 平移到原点但相机用未 offset 世界盒 → target 对空、画面错位。修复：`applyOffsetToBox` 纯函数。**教训：WebGL 类问题必须 headless 真渲染验证，不能只靠快照测试**。
- **3D 预览截面"部分实体切错"（2026-08-18 实测）**：① 切割平面恰与实体面重合（模型底面 z=0、相邻栅元共享面）时旧 `slice_stl_segments` 对 on-plane 顶点 continue → 0 环/错环；共面三角面须贡献出现 1 次的外轮廓边。② 预览归一化平移与后端原始 STL 系不一致 → 切位偏移；2026-08-18 起主预览**已去归一化**（显示系=原始系，modelCenter 恒 0，`planeOffset` 换算恒等但保留防回归）。③ 坐标轴单一事实来源 `axisConfig.ts`（X 红/Y 绿/Z 蓝），不要再内联写 dirs。
- **FreeCAD 对「旋转宏体半空间」补集布尔失效（2026-08-18 实测）**：`RPP ... *TRn` 正侧 = bound.cut(内盒) 再 apply_trn（带 Placement 复合体），对 `-曲面` 求补集返回垃圾体积（1.7e8 > 整盒 1.25e8）。斜向六面体一律改用 6 个局部 PX/PY/PZ + `*TRn`（普通平面布尔可靠）；轴对齐 RPP 宏体无 TR 正常。quickCell.ts 已按此实现。
- **大网格零通量背景涂蓝（2026-08-15 用户实测）**：色阶下限=0 时精确 0 值也被涂蓝遮模型。已修：色阶下限**自适应** = `minPositive×0.5`（曾用 sqrt 规则切太狠致"只显示一个面"，已按用户反馈改）；注意纹理是线性归一化 u8，微小值会被量化成 0（minPositive 从 u8 字节重建，勿用原始文件最小值）。
- **GQ/SQ 3D 预览 3 连坑（2026-08-22 实测，静态审查发现不了）**：① `app/mc.py` 邻接索引 `t_ids`/`slots` 的 repeat/tile 与「先全部 (0,1)、再 (1,2)、再 (2,0) 的块状边数组」错位 → 朝向传播全乱（signed volume≈0、假碎片/假冲突）；必须 `t_ids=tile`、`slots=repeat`。② BFS 波前同波重复三角形未去重 → 指数膨胀到 4 千万+（内存炸）；用一次性 bool 数组去重。③ 带 TR 小栅元在大 bound（B=500）下：TR 曲面 AABB 必须经 8 角点变换（`p_global=o+p_local@R`）求全局紧盒，保守全盒会让 32³ 粗扫漏检 → 空网格降级包围盒；margin 必须按**实际扫描盒**间距 `(scan_hi−scan_lo).max()/(coarse−1)×1.1`，用全局 `2B/(coarse-1)` 在 B=500 时达 35cm 把细化盒撑爆。水密断言必须用「每条无向边恰被 2 个三角形使用」的边计数法（**vtkFeatureEdges 对 marching cubes 网格误报边界边**）；`*TRn` 求值前必须 `p_local = rotate⁻¹·(p_global − o)`。
- **GQ/SQ 后续增强 3 连坑（2026-08-22 实测）**：① **凸裁剪盖面**：顶点恰落在裁剪面上（dist≈0）时跨边条件会漏掉该交点 → 盖面缺顶点被丢弃 → 三角形破洞（228 条开放边）；`cut()` 端点贴面返回 `keep()`、盖面收集贴面顶点本身。OWEN 的边链盖面法在细密切线平面下会退化丢面（162 面球只出 35 面），改用 Sutherland–Hodgman + 盖面绕质心极角排序。② **金螺旋方向分布不均**：外接多面体顶点半径到 1.08r+、体积误差 8%+，改二十面体细分（162/642 方向）；162 方向外接误差仍 ~2.1% → 无封口时绕中心体积校正 λ=(V_true/V_mesh)^(1/3)（体积精确）、有封口时用 642 方向（区域体积无法解析）。③ **解析切片 marching squares 16 格表 case 12（{2,3} 上边在内）应为 (1,3) 而非 (0,1)**；`_plane_halfspace` 的 pos/neg sgn 与 surface_fn 正侧约定相反（pos 侧要取 −法向）。

- **OUTP 解析误用 pymcnp 构造函数（2026-08-19 实测）**：`pymcnp.Outp(text)` 是构造函数非解析入口，恒报 TypeError；正确入口 `Outp.from_mcnp(text).to_dataframe()`。且内置 pymcnp 0.9.1 Tally_4 只认 MCNP6.2 布局，MCNP6.1 紧凑两列解析为空 → 需 `app/outp_parser.py` 兜底。
- **测试笔误陷阱（fixtures 实测）**：① valid_39.meshtal 的 tally number 是 **4 不是 1**（须取自 parse 响应 `tallies[].number`）；② preview-3d 单栅元 material="0" 是 void → `include_void=False` 跳过 → 空 stl_files（冒烟 deck 须用非 0 material）。
- **meshtal-parse 元数据缓存**：已闭环（`_mode_parse` 先 `get_manifest` 命中即返回，实测二次 0.23s）；`meshtal_cache._MANIFEST_VERSION=2` 使旧磁盘缓存失效。
- **P0/P1 技术债全清偿（2026-08-12）**：引擎缺陷 F-A~F-H + F#1~F#7 全修，R1-R4 不动点成立；`inp_generator.py` 仍为**技术债集中地**（见 docs/backend-changes.md + UI_ARCHITECTURE.md 技术债地图）。
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

```
1. vite build                       （前端产物，~3-4s）
2. PyInstaller sidecar              （在 gui\ 下跑 gui/mcnp_sidecar.spec，产物名 "python"；
                                    核对 _keep_py / _keep_dirs 清单，如 outp_parser.py/meshtal/ 等新增模块）
3. 替换 binaries                    （把新 sidecar 的 python.exe + _internal 换进 target\release\）
4. tauri build                      （需 RUSTUP_HOME/CARGO_HOME=D:\rust）
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
