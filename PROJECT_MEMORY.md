# 项目记忆文档（AI 速查手册）
> 最后更新时间：2026-08-12

> **当前执行计划：3D 预览卡顿修复（新任务，2026-08-12 上级转来）**：用户报告 ~20m 混凝土屏蔽（MCNP cm 单位 = 2000 坐标单位）3D 预览卡顿。**修复契约已锁定（docs/contracts/preview3d-performance.md，2026-08-12 复现实测修订版）**：repro 实测反驳原诊断 4 项（前端同步解析大 STL 54ms 非主因 / 120s 超时不触发 / OCC 大坐标无崩溃 / 20m bound 布尔不慢），确认真凶 P0a 打开卡（无缓存全量重建 3.30s×3+无加载态）、P0b 交互卡（rebuildTicks 每帧 ~160 对象/81 纹理不 dispose + 无条件渲染 + 全栅元透明 overdraw）、P0c 大坐标深度（far/near 7M~17.5M 超 2^24 + target 恒原点），并新增高收益项 P0d（IPv6 绑定 300-500ms/请求 / vtk 惰性 0.46s/次 / bound 过撑 shield 5300→2700）。**以下旧诊断部分已被 repro 反驳，以契约为准**：
> - **管线**：Preview3D.tsx → POST /api/preview-3d → api_server(_handle_preview_3d, :1001) → FreeCADEngine.build_geometry(freecad_preview.py:243) → 子进程 _freecad_csg_worker.py（逐曲面布尔裁剪 + 逐栅元 AST 布尔级联）→ tessellate(1.0) → 每栅元 STL → base64 进单 JSON → 前端 atob+STLLoader.parse 全量加载
> - **三因**：① 打开卡/黑屏（主因）：无缓存每次全量重建；base64 单 JSON 可达几十 MB（api_server.py:1058）；前端 JSON.parse+atob+STLLoader.parse 主线程同步无 Web Worker（Preview3D.tsx:305-308）；后端 120s 硬超时（freecad_preview.py:339）。② 交互低帧率：相机 change 每帧 rebuildTicks 新建数百 Line/Sprite/CanvasTexture 不 dispose（Preview3D.tsx:196-252）；渲染循环无条件每帧跑（354-383）；全栅元 transparent+depthWrite:false overdraw（312）。③ 闪烁/错乱：near=0.1/far≈35万（99,344）；无几何居中/归一化 target 恒原点（341）；大坐标 OCC 浮点容差。
> - **20m 放大器**：bound 自适应 `_compute_bound_from_surfaces`（freecad_preview.py:206-225）：2000 单位→B≈2700 布尔裁剪更贵；预览无单位缩放/无归一化（仅 STEP 导出有 SCALE=10）；前端深度精度失衡。
> - **执行流程**：复现验证已由 `repro` 完成 → **架构师契约已锁定并经 PM 裁决生效（docs/contracts/preview3d-performance.md）** → **后端/前端施工并行派发中** → 测试复核（补大尺寸预览测试 + 全量 251 绿不破）。**性能任务与 P0/P1/P2 正交，施工不得破坏现有测试（每步全量 pytest）。** 契约要点：P0a 打开卡（后端 preview_cache 深模块 + 前端加载态，缓存命中打开 ≤1s）、P0b 交互卡（TickGrid/renderGate/cellMaterial 拆深模块 + vitest）、P0c 深度（computeCameraParams 几何归一化 + far/near ≤1e4）、P0d 新发现三项（IPv6 前端改 127.0.0.1 / vtk 惰性 / bound 位移参数修正）。
> - **PM 三项裁决（2026-08-12，已闭合生效）**：① 半透明默认 opaque + "半透明查看"开关默认关（附非阻断引导提示可选）；② vitest 批准为 gui/ devDependency（测试目录 gui/test/ 独立，不并入 pytest 门禁）；③ 冷启动 ≤3.0s 批准（核心指标 = 缓存命中 ≤1.0s）。
> - **施工派发（2026-08-12）**：分支 perf/preview3d（基于 refactor/generator-tech-debt，保证 251/0 测试基线）。**后端（backend-perf a2a2f2c4786230bcf）**：步 1 bound 修正 + app/preview_cache.py + 后端单测 → 步 2 vtk 惰性 → 步 3 handler 缓存接线 + _clear_stl_session 联动。**前端（frontend-perf a2b6642aaf0b9b4c2）**：步 3 前端 api.ts（127.0.0.1，grep 归零）+ 步 4 抽 4 深模块（TickGrid/renderGate/cellMaterial/cameraParams + vitest 4 测试文件）+ 步 5 加载态 + 半透明开关。文件零重叠。
> - **前端施工完成（2026-08-12，frontend-perf a2b6642aaf0b9b4c2）**：步 3 `gui/src/utils/api.ts`（127.0.0.1 单一常量）14 文件 ~25 处 localhost:5001 归零；步 4 `gui/src/three/` 4 深模块（TickGrid 台账+完整 dispose+步长表 1e6 / renderGate dirty 按需渲染 / cellMaterial 默认 opaque / cameraParams farNear≤1e4）+ Preview3D.tsx 接线 + 几何归一化（translate 先于 computeBoundingBox）；步 5 加载态遮罩 + 半透明查看开关（默认关，M0 真空 opacity 0 不变）；vitest 4 文件 13 用例全绿（`cd gui && npx vitest run`），tsc/build 通过。改动清单 docs/frontend-changes.md。
> - **复现实测结论（repro，2026-08-12，部分反驳原诊断）**：
>   - **被反驳**：前端同步解析 16MB=54ms（非主因）；子进程最大 2.38s（无 120s 超时风险）；±2742/±10000 布尔 <0.6s（无 OCC 崩溃）；bound 放大布尔不慢。
>   - **真凶**：① 打开卡（每次无缓存全量重建 3.30s + 无加载态 + handler 1.3~2.7s → 1.5~3s 白屏）；② 交互卡（rebuildTicks 每帧 ~160 对象/81 GPU 纹理 + 全栅元透明 overdraw + 无条件渲染循环，与几何大小无关）；③ 大坐标闪烁（far/near 失衡，±10000 时 17.5M 超 2^24 深度极限，target 恒原点）。
  >   - **新发现 3 项**：IPv6 HTTP 惩罚（server 绑 0.0.0.0:5001 + 前端 localhost，Chrome Happy Eyeballs 每请求 300-500ms，影响全部 25 端点，修法绑 [::]:5001 或改 127.0.0.1）；vtk 惰性化（worker 每次 import vtk 白付 0.46s 占子进程 ~35%）；bound 过撑 bug（把宏体方向向量/轴长当坐标，shield_20m 轴长 4000→B=5300 vs 真实 2000，只对位移参数取 max）。
> - **大尺寸预览 fixture 已 vendor 7 个**（tests/fixtures/）：preview_inp09_m27.inp / preview_inp01_m100.inp / preview_duct_conc.inp / preview_inp96.inp / preview_inp08_m27.inp / preview_shield_20m.inp / preview_stress_bunker.inp。复现脚本在仓库外 D:\code\preview_measure\（不污染生产）。
> - **命名冲突教训（2026-08-12）**：曾以 `backend` 命名派发复现 agent 导致名称解析冲突，`repro` 正确执行后也被停（用户主动）。**后续新增 agent 用唯一名（如 arch-perf/repro）**，避免与在途 agent 重名。
>
> 上一计划（P0 测试防线 + P1 技术债清偿 + P2 文档补齐）**已完成并验收**：全量 251 绿/0 红。

> **当前执行计划**：测试补防 + 技术债清偿 + 文档补齐（P0 测试 → P1 重构依赖 P0 → P2 文档并行）。
> 定稿计划文件：`C:\Users\13789\.claude\plans\tranquil-greeting-biscuit.md`（优先级由上级拍板并授权自动执行）。
> - **P0 测试防线**：派「测试」（**第一轮完成，2026-08-12**）：234 通过 / 17 失败。M1.1/M1.2/M1.3/M1.5 通过，**M1.4 未全绿——门禁拦截**。17 失败全部为"按设计先红"的缺陷/技术债 pin：F-A~F-E 是引擎真实缺陷（测试网捕获），F#3/F#7 是技术债（P1 处理）。
> - **P0 修复轮（当前：后端已完成 F-A~F-E 重新施工，2026-08-12）**：
>   - 契约 **docs/contracts/bugfix-f1-f5.md（已确认有效，2026-08-12 上级裁决微调完成）**：F-A~F-H 均为基线真实缺陷，放行重新施工。F-A 裁决方案 C（解析器拦截节头为主 + banners.py 单点辅助）、F-B 解包 CellRow、F-C 正则扩逗号、F-D options 上移 M 头行、F-E 剥 &、F-F/F-G/F-H 翻新 pin（本轮可选不阻塞）。**微调：多源 SDEF 漂移（F#5/F#6）归 P1 不并入本轮；范围=F-A~F-E；终态 245 绿/6 红；kitchen-sink R1/R4 移入 P1 验收，复合根因清单写入 §0.5.5**。
>   - **施工结果（2026-08-12）**：全量 `python -m pytest tests/ -v` = **245 绿 / 6 红**（与 §0.5.3 预期一致）。F-A~F-E 全部红转绿；F-F/F-G/F-H 已翻新 pin 为正确行为断言（仍绿）；6 红 = 4 技术债（F#3/F#7）+ 2 kitchen-sink（R1/R4）。**banners.py 词汇按"生成器全部节头"扩展**（契约 11 词汇外实测发现 Fission/KCODE/KSRC/Additional 等内联 C 头也泄漏）；**prob41c R1 伴生修复**：normalize_lines 缩进合并保留续行 `$` 注释。**app/UI_ARCHITECTURE.md 基线为空文件（0 字节）**，§8.1 无法重锚定；**已由架构师补建完成（2026-08-12，见 §8 变更日志）**。改动清单见 docs/backend-changes.md。
>   - **基线真相（上级已承认方法论失误）**：基线全量 **234 通过 / 17 失败**，与 QA 报告一致，契约依据成立。上级上一轮"245/6"复核错误源于读了后端施工中途未 commit 的工作树。
>   - **上级最终裁决（2026-08-12）**：
>     1. 契约有效，放行后端按 bugfix-f1-f5.md 重新施工
>     2. **M1.4 门禁（本轮）**：minimal + 3 样例（prob41c/avr13/inp24）R1 全绿 + F-B/F-C/F-D/F-E 红转绿；**kitchen-sink R1/R4 本轮允许保持红，归入 P1 F#5/F#6**（已实测：修完 F-A~F-H 后 kitchen-sink 仍不会绿，SDEF 漂移需 P1 重构）
>     3. 技术债 F#3/F#7 的 4 红保持红（设计内 pin，P1 范围）
>     4. **本轮终态预期 245 绿 / 6 红**（4 技术债 + 2 kitchen-sink）；P1 放行条件 = 本轮达成 245/6；P1 目标 = 6 红全部转绿
>     5. 施工纪律不变：每步全量、禁改断言骗绿、按 §7 不越 P1 边界、完成按 §8 重锚定
>   - **执行链（M1.4 已通过，P1 放行条件达成）**：
>     - 架构师微调契约完成 → **后端重新施工完成**（全量 **245 绿 / 6 红**，与契约 §0.5.3 一致）→ **tester 复核通过（2026-08-12）**：245/6 复跑两次稳定；6 红 = 4 技术债（F#3 x2、F#7 x2）+ 2 kitchen-sink（归 P1）；门禁 §0.5.2 全过（minimal+3 样例 R1 全绿、F-B/C/D 转绿、129+73+7 零回归）；无断言降级（用例总数 251 不变）；P1 范围未触碰（_wrap_long_lines/_generate_multi_source/_generate_distribution_sdef 均未改）；F-F/F-G/F-H pin 翻新写死正确行为断言全绿。
>     - **kitchen-sink 归 P1 实证**：头泄漏已归零（2102→2266 缩至 2102→2110，无 cell 注释污染/曲面膨胀），残留差异纯化为多源 SDEF 字段重组漂移（POS=F D1→X=F Y=D1、TME=D6→TME=0.0、SI1 V→L、分布注释丢失、SI 值空格归一化）= P1 F#5/F#6 验收基准。
>     - **P1 放行条件已达成**（上级裁决：本轮 245/6 即可放行 P1，P1 目标 = 6 红全部转绿）。**待上级确认后启动 P1**：架构师出重构契约 → 后端在 refactor/generator-tech-debt 分支按 F#7→F#3→F#4→F#5+F#6→F#1 顺序重构。
>   - **⚠️ PM 失误记录（2026-08-12，已修复）**：此前为回滚引擎代码执行 `git checkout -- app/` 时，误将架构师 P2 补全但**未 commit** 的 `app/UI_ARCHITECTURE.md` 还原成 git 空版本。docs/ 契约文件（api.yaml、bugfix-f1-f5.md）未受影响。**已由架构师（ae059169a61adc2ad）重建完成（2026-08-12，7 节非空，行号全 Grep 实测）**。关键重锚定行号：raw_overrides 守卫 1069(cells)/1081(surfaces)/1107(materials)/1115(sdef)/1131(phys)/1139(tally)/1147(e0)/1168(cut)、raw_tally 变体 1156、门控 1157/1162、_wrap_long_lines 1010、**F#3 import json 631/671（注意 673 是 `_json.loads` 调用行，非 import；PM 原记录 631/673 有误，已修正）**、F#4 247（Dn 254-290/普通 292-310）、F#5 375、F#6 384-403/434-449/486-489、F#7 110、E0DBG（core.py 826-827/1018-1021、__init__.py 138-140、api_server.py 608-610）。文档已含缺陷修复行为变化（banners.py/normalize_lines 剥 &/多粒子正则/小写 m/解包 CellRow/options 上移）。
> - **P0 复核口径（2026-08-12 上级裁决后，后端施工时须满足）**：终态预期 **245 绿 / 6 红**。本轮 11 例红转绿 = F-A 样例 R1 6（minimal/prob41c/avr13/inp24 R1 归零：prob41c ~1097、avr13 ~644 稳定）+ F-B 3 + F-C 1 + F-D 1；6 红 = 4 技术债（F#3/F#7）+ 2 kitchen-sink（R1/R4，复合根因移入 P1 F#5/F#6 验收，清单见契约 §0.5.5）。误判断言走 tester→PM 仲裁通道，绝不自行改断言。
> - **P1 技术债清偿（已完成并通过复核，2026-08-12）**：上级确认 P1 启动（放行条件 245/6 已达成）。**架构师 P1 重构契约已锁定（docs/contracts/p1-refactor.md）**。**后端施工完成**：全量 pytest = **251 绿 / 0 红**（复跑 ×2 稳定），6 红全部转绿。commit 索引：F#7 bf0a2c7 → F#3 c774e56 → F#4 52ca251 → F#5/F#6 4a e404172 → 4b/4c 018ced5 → F#1 1488aae（详见上文）。重锚定完成（review_findings 7 项 resolved/UI_ARCHITECTURE/test_tech_debt/PROJECT_MEMORY）。**tester 复核通过（2026-08-12）**：251 passed/0 failed 复跑稳定；逐 F# 核对全绿；纪律核对（用例总数 251 不变、无 skip/xfail 骗绿、api_server 路由/api.yaml 漂移闸门 7/7 绿含真实 HTTP、_wrap_long_lines/structured_distributions join 未进 P1 diff、无新依赖）；kitchen-sink 实证 5 项残留差异全消除（POS=F D1 保持/TME=D6 保持/SI1 V 型保持/概率键控注释保留/SI 值字节恒定，g1==g2 精确相等 len 2099==2099）。
> - **✅ 全量计划完成（P0 测试防线 + P1 技术债清偿 + P2 文档补齐，2026-08-12）**：全量 pytest = **251 绿 / 0 红**。最终交付：tests/ 测试网（unit 129 + parser 73 + integration 含契约闸门 7 真实 HTTP）、dev-requirements.txt、3 样例 fixtures、docs/contracts/（api.yaml 25 端点 + bugfix-f1-f5.md + p1-refactor.md）、app/UI_ARCHITECTURE.md（7 节）、review_findings.json 7 项全 resolved、引擎缺陷 F-A~F-H 全修、技术债 F#1~F#7 全清偿。分支 refactor/generator-tech-debt（P0 基线 996d11f 已并入）。**待上级确认可交付状态。**
> - **P2 补文档**：派「架构师」（**已完成，2026-08-12**）：app/UI_ARCHITECTURE.md 7 节齐全 + docs/contracts/api.yaml（OpenAPI 3.0，25/25 端点，每 path 带 operationId，已验收）。
> - **关键红线**：测试不得 import gui.backend.api_server（模块级 pyvista/FreeCAD 探测污染）；raw_overrides 行为兼容前端只写 4 key + 空串=无覆盖 + 1145 门控，禁止凭直觉改；往返断言用 R1 不动点而非文本相等；样例 inp24 已 vendor 进仓库副本（上级提供的官方测试库 D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing）。
> - **契约要点（架构师已核）**：run-mcnp 响应 status 字面量是 "started" 非 "ok"；import-step/export-step/set-freecad-path 守卫分支 HTTP 200 下返回 status:"error"；validate-zaid/xsdir-search/serve-file 从 query 读参（GET），其余 22 端点为 POST body；do_GET/do_POST 同路由。闸门 HTTP 往返断言勿按统一信封假设。


## 1. 项目身份
- **名称**：MCNP 输入卡生成器（MCNP Input Card Generator）
- **版本**：1.6.3
- **技术栈**：
  - 前端 UI：React 18 + TypeScript + Vite（端口 1420，表单化标签页界面）
  - 3D 渲染：Three.js（3D 预览）/ SVG（平面截面）
  - 窗口外壳：Tauri 1.x（Rust，无边框自定义窗口），另有 Electron 备用壳
  - 后端：Python 标准库 `http.server`（端口 5001，**不用 Flask**），PyInstaller 打包 sidecar
  - 核心引擎：pymcnp（BSD-3-Clause）+ 自研 generator/parsers
  - CSG 几何：FreeCAD（LGPL）；STEP→MCNP：GEOUNED（EUPL-1.2，随程序 vendor 打包）
- **核心业务**：用可视化表单 GUI 替代手工编辑 MCNP `.INP` 输入文件；覆盖生成/导入/校验/3D 预览/截面/材料库/源/计数/输出分析全流程
- **许可**：All Rights Reserved（自有代码禁止盈利/未经许可发布）；开源组件各按自身许可


## 2. 当前状态快照
- **开发阶段**：开发中（实验分支 experiment/geouned，v1.6.3 已具备完整可交付功能）
- **当前分支**：`experiment/geouned`（主分支 `main`）
- **工作区**：干净（无未提交改动）
- **已完成功能**：
  - 8 标签页表单编辑（基本/材料/几何/源/计数/高级/输出）
  - INP 生成/导入（含拖拽）、工作区自动保存/恢复、4 套主题
  - 材料库（50+ 预设 + xsdir 校验）、材料下拉自动填充密度
  - 3D 预览（FreeCAD CSG，`#n` 栅元补集支持）+ 平面截面（STL numpy 切）+ STEP/GEOUNED 导入
  - 条件编译行（#ifdef/#else/#endif）、全行拖拽排序
  - E0/En/T0/Tn 网格（线性/对数/自定义）、三种源模式（固定/SDEF/KCODE）、SSW/SSR 面源
  - **文本↔表单双向互转**：材料/几何/计数三标签页（深模块 `useSectionTextMode` + `/api/section-to-text` + `/api/text-to-section`）
  - MCNP 检测与一键运行、输出文件解析绘图、内联参考文档
- **待开发功能**：[无明确 backlog，见"工作计划"待用户定夺]
- **已知阻塞**：无（测试缺口见第 6 节"踩坑"）


## 3. 项目目录结构速查（AI 定位代码用）

> **用途**：当需要修改某个功能时，先查此表定位文件位置，避免全盘扫描。

| 目录路径 | 功能说明 | 涉及 Agent |
| :--- | :--- | :--- |
| **Python 核心引擎（app/）** | | |
| `app/models.py` | 数据模型：DeckData/CellData/MaterialData/SourceData/BasicSettings/TallySettings/AdvancedSettings 等 dataclass | 后端 |
| `app/generator/inp_generator.py` | INP 生成主引擎（**已知技术债集中地，见第 6 节**） | 后端 |
| `app/generator/inp_parser.py` | INP 解析入口 | 后端 |
| `app/generator/parsers/{core,lines,sections,validator}.py` | 解析管线（行/分段/校验） | 后端 |
| `app/generator/validator.py` | 校验逻辑 | 后端 |
| `app/freecad_preview.py` / `_freecad_csg_worker.py` | FreeCAD 3D CSG 求值（子进程） | 后端 |
| `app/stl_cross_section.py` / `_freecad_cross_section_worker.py` | 截面（numpy 切 STL，不依赖 FreeCAD） | 后端 |
| `app/step_importer_geouned.py` / `geouned_worker.py` | GEOUNED STEP→MCNP 转换封装 | 后端 |
| `app/step_importer.py` / `freecad_locator.py` | STEP 导入 / FreeCAD 定位唯一入口 | 后端 |
| `app/xsdir_db.py` / `material_presets.py` | xsdir 截面数据库 / 预设材料库 | 后端 |
| | | |
| **前端（gui/src/）** | | |
| `gui/src/App.tsx` | 主界面（顶栏/导入/生成/保存恢复/主题） | 前端 |
| `gui/src/components/` | 标签页组件：BasicSettings/MaterialTab/GeometryTab/SourceTab/TallyTab/AdvancedTab/OutputTab | 前端 |
| `gui/src/components/Preview3D.tsx` / `Preview3DWindow.tsx` | Three.js 3D 预览（独立窗口） | 前端 |
| `gui/src/components/CrossSectionView.tsx` / `CrossSectionWindow.tsx` | 平面截面（独立窗口） | 前端 |
| `gui/src/utils/DeckContext.tsx` | **单一权威表单状态**（localStorage 键 `mcnp_workspace_v1`） | 前端 |
| `gui/src/utils/useSectionTextMode.ts` | **文本↔表单互转深模块**（材料/几何/计数共用） | 前端 |
| `gui/src/utils/sectionConvert.ts` | section-to-text / text-to-section API 封装（前端契约层） | 前端 |
| `gui/src/utils/gridState.ts` | E0/En/T0/Tn 网格解析/序列化深模块 | 前端 |
| `gui/src/utils/backend.ts` | 后端生命周期（sidecar 拉起/关闭） | 前端 |
| `gui/src/utils/dataCollector.ts` | 表单→DeckData 收集 | 前端 |
| `gui/src/utils/contract.ts` | 前端数据类型定义 | 前端 |
| | | |
| **后端（gui/backend/）** | | |
| `gui/backend/api_server.py` | **HTTP 后端总入口**（路由表见第 4 节，端口 5001） | 后端 |
| `gui/backend/mcnp_bridge.py` | 打包后 sidecar 启动器 | 后端 |
| `gui/backend/generate_step.py` | STEP 生成（备用） | 后端 |
| | | |
| **窗口外壳（gui/src-tauri/）** | | |
| `gui/src-tauri/tauri.conf.json` | 无边框窗口、sidecar 配置（externalBin: python） | 后端 |
| `gui/src-tauri/src/main.rs` | Tauri Rust 入口（close_window 命令等） | 后端 |
| | | |
| **文档** | | |
| `README.md` | 项目总览（技术栈/功能/打包说明/项目结构） | — |
| `app/docs/` | MCNP 参考文档（曲面卡/FN 卡/输出卡/PRINT/C810/源分布/sample_format） | — |
| `app/UI_ARCHITECTURE.md` | UI 架构说明：三层边界/启动链路/import-root/deck JSON 契约/raw_overrides/往返保真/技术债地图 | 架构师 |
| `docs/contracts/api.yaml` | **OpenAPI 3.0 契约**（25 端点，每 path 带 operationId，防漂移闸门验证） | 架构师 |
| | | |
| **测试** | | |
| 无 test/ 目录 | **测试缺口**（见第 6 节） | 测试 |


## 4. 关键架构决策（ADR）

| 决策 | 理由 | 日期 |
| :--- | :--- | :--- |
| 后端用 Python 标准库 http.server，不用 Flask | 减少依赖，PyInstaller 打包 sidecar 更简单 | — |
| 前端单一权威状态在 DeckContext（localStorage 工作区） | 8 个标签页共享一份数据，避免多源状态冲突 | — |
| 文本↔表单互转按 section 维度做深模块（useSectionTextMode） | 材料/几何/计数三处共用一套进出文本模式逻辑，接口只暴露"进/出 + 回填回调" | 近期 |
| 3D 预览用 FreeCAD 子进程 CSG 求值输出 STL | FreeCAD 精确几何；STL 保留在会话中供截面复用（numpy 切），不重复调 FreeCAD | — |
| 截面不依赖 FreeCAD，直接 numpy 切 STL | 独立窗口即时响应，无需 CAD 内核 | — |
| GEOUNED 随程序 vendor 打包，用户只装 FreeCAD | STEP 导入开箱即用；FreeCAD 经 locator 检测/手动指定 | — |
| 全部代码遵循**深模块原则**（用户全局记忆 codebase-design-always） | 小接口覆盖复杂行为，AI 友好、可测试 | — |
| **P1 多源/分布 SDEF 表示统一**（`SDEF_FIELD_SPECS` 表驱动 + 字段序统一为 POS 首位 + D-index 由 `dist_params` 位置决定、与发射序解耦） | kitchen-sink R1/R4 字节不动点要求多源生成与分布回放产出逐字节一致；消除 §0.5.5 复合根因 #2-#5 + SI 值空格归一化 | 2026-08-12 |
| **P1 分布注释作为生成器横幅词汇**（`multi_source_comment_banner(n)` 进 `is_generator_banner`，parse 拦截丢弃、回放重发） | 复用 F-A 方案 C 的词汇冻结机制，注释不漂移不重复 | 2026-08-12 |
| **P1 raw_overrides 收敛为 `_apply_raw_override` 助手**（1145 raw_tally 门控保留"判 tally key"语义） | 消除 8 处复制粘贴；门控判 tally key 是既有行为，非 bug | 2026-08-12 |
| **3D 预览 deck 指纹缓存**（`app/preview_cache.py`，LRU 上限 3，命中跳过 FreeCAD 子进程） | 打开卡真凶=每次全量重建 3.30s；同 deck 二次打开缓存命中 ≤1s，对 API 契约透明 | 2026-08-12 |
| **前端 3D 拆深模块**：`TickGrid`（刻度生命周期+dispose 台账）/`renderGate`（dirty 按需渲染）/`cellMaterial`（默认 opaque）/`computeCameraParams`（几何归一化 + far/near ≤1e4） | 交互卡真凶=每帧 160 对象/81 纹理泄漏+无条件渲染+透明 overdraw；大坐标深度 17.5M 超 2^24；深模块接口小实现深，vitest 可测 | 2026-08-12 |
| **前端后端地址收敛 `127.0.0.1:5001`**（`gui/src/utils/api.ts` 单一常量），后端绑定 `0.0.0.0` 不动 | server 只绑 IPv4 + 前端 localhost → Chrome Happy Eyeballs 每请求 300-500ms，影响全部 25 端点；127.0.0.1 直连命中 IPv4，CORS `*` 已覆盖 | 2026-08-12 |


## 5. 核心业务规则（必读）

- **DeckData 是聚合根**：前端 DeckContext ↔ 后端 generate/parse 全走 DeckData 单对象，避免参数膨胀。
- **密度写在栅元卡（CELL）上**，材料卡（Mm）只含 ZAID+份额，不含密度。
- **栅元/材料/计数行支持判别联合**：`kind=="cell"|"raw"`（栅元）、`kind=="nuclide"|"raw"`（材料）——`raw` 行承载 `#ifdef/#else/#endif` 原样条件行。
- **文本模式状态存在 deck.textMode[section] + deck.rawOverrides[section]**；进文本模式前必须由后端先生成当前表单的文本（section-to-text），防数据丢失。
- **STL 会话**：3D 预览生成的 STL 保留在 `_STL_SESSION`，供截面复用；只在关预览窗口/清空时 `/api/clear-stl` 删除。
- **曲面文本解析**：GEOUNED 常见 `*TRn` 后缀或 `100*` 前缀的 TR 引用，均需提取 transform；P 卡 `A B C D` 系数形式需转三点定义（注意法向同向性）。
- **SDEF 三种模式**：`fixed`（固定点源）/ `distribution`（SDEF 分布源，SI/SP/DS 结构化 JSON 优先于 sdef_raw_text）/ `kcode`（KCODE/KSRC/HSRC）。
- **前端契约层**：`sectionConvert.ts` 只认 `{status:"ok"}` 成功响应，`/api/text-to-section` 返回 `{data}`，`/api/section-to-text` 返回 `{text}`。


## 6. 踩坑与排雷指南

- **已知技术债（来自 `app/generator/review_findings.json`，7 项，全部在 inp_generator.py）——P1 已全部清偿（2026-08-12）**：
  1. ✅ `raw_overrides` 覆盖守卫 8 处复制粘贴 → 收敛为 `_apply_raw_override`（commit 1488aae），raw_tally 门控判 tally key 语义保留
  2. ✅ `_generate_en_cards` 函数内重复 `import re`（P0 期间已 Resolved）
  3. ✅ 函数内 `import json as _json` + `import sys` + `[E0DBG]` 调试 print → 清理（commit c774e56），grep 归零
  4. ✅ `_generate_single_source` 两段相同 SDEF 构造 → 合并 `_build_sdef_parts`（commit 52ca251），字节不变
  5. ✅ `_generate_multi_source` 145 行 5 子关注点 → 拆 5 函数（commit e404172），概率归一可单测
  6. ✅ 多源源字段名 3 处枚举 → `SDEF_FIELD_SPECS` 表驱动（commit e404172 + 018ced5）
  7. ✅ 函数内 `from pymcnp import inp` → 提到模块顶部（commit bf0a2c7），导入期 fail-fast
- **测试缺口**：全仓库无 test/ 目录、无 pytest/unittest 用例。对生成器/解析器这种核心引擎是高风险。
- **P0 测试防线（2026-08-12 建立）**：`tests/` 目录，`python -m pytest tests/ -v`。总体 234 通过 / 17 失败（17 个全为技术债/往返缺陷的"按设计先红" pin，红=标记缺陷存在，见 `docs/qa-report.md`）。
- **R1 不动点（正确性红线）不成立 — 阻塞 M1.4**：`generate(parse(generate(d))) != generate(d)`。根因是生成器 C 注释头泄漏（`C  Cell Cards: N cells defined` → 变成栅元 `$` 注释；`C  Surface Cards: N surfaces defined` → 计入曲面文本；`C  ===== Data Cards ====="` → 捕获进 other_cards），输出逐代膨胀。P1 动引擎代码前必须先修。
- **validate_deck 与 CellRow 不兼容**：`app/generator/validator.py:validate_all` 直接访问 `cell.surface_expr`，而 `deck.cells` 是 `CellRow`（kind/cell/text 嵌套）→ 对含栅元 deck 抛 AttributeError。生产 `/api/validate-inp` 走文本层 `parsers/validator.validate_inp_text`，不受影响。
- **多粒子计数卡 round-trip 丢失**：生成输出 `F4:N,P`（逗号合并），`parse_f_tally` 只认单粒子设计符 → 多粒子计数 parse 后消失（进 other_cards）。
- **材料 options 丢失**：MaterialData.options（nlib= 等）生成时追加到材料末行尾，被解析器并入 raw 行 → round-trip 后 options 为空。
- **`_wrap_long_lines` 的 & 续行符污染字段**：超 80 列行拆分附加 `&`，解析后污染 surface_expr/vec 等字段（R2 已对尾 & 容差）。
- **ksrc_points 数值坐标崩溃**：`_generate_kcode` 对数值坐标（int）`.strip()` 崩溃；契约要求字符串坐标（前端发字符串，属潜在缺陷）。
- **parse_sdef_simple 的 EFF 裸值静默丢弃**：EFF 在 _KNOWN_KEYS 但 _apply_sdef_param 无 EFF 分支 → 数据丢失点。
- **UI_ARCHITECTURE.md 已重建**（2026-08-12）：后端 F-A~F-E 重新施工后原 P2 文档因未 commit 被回滚误清空，架构师已补建 7 节文档并用 Grep 全量重锚定行号（见 §8 变更日志）。
- **契约文档已补**（2026-08-12）：`docs/contracts/api.yaml` 覆盖 api_server.py 全部 25 端点（每 path 有 operationId）；漂移闸门 `tests/integration/test_api_contract.py` 会 AST 断言 handlers 字典每 path 在 api.yaml 有 operationId。
- **打包注意**：Tauri build 需要 `RUSTUP_HOME/CARGO_HOME` 指向 D:\rust；sidecar 用 PyInstaller（spec：`gui/mcnp_sidecar.spec`，产物名 "python"）；后端窗口关闭时经 Rust `close_window` 命令一起退出。


## 7. 技术争议与决议

| 争议点 | 方案 A | 方案 B | 最终裁决 | 裁决理由 |
| :--- | :--- | :--- | :--- | :--- |
| F-A R1 不动点：生成器 C 注释头泄漏，解析器吸收 vs 生成器改头 | 解析器吸收防护（仅节头词汇精确剥离） | 生成器改头为不可吸收形式 | **方案 C，以 A 为主、B 为辅**（2026-08-12） | 方案 B 单独不可行：MCNP 注释只有 C 一种形式，现有解析器对任意 C 行都会在栅元注释/曲面 verbatim/other_cards 三路吞掉，不存在合法且三阶段天然惰性的注释形式；曲面段 verbatim 回放使生成器单侧无法根治。方案 C 把节头冻结为 banners.py 单一事实来源，生成器与解析器共享，R1 测试为漂移兜底；用户可见 INP 输出风格保留 |


## 8. 最近变更日志

| 日期 | 变更类型 | 改动描述 | 涉及 Agent |
| :--- | :--- | :--- | :--- |
| 2026-08-12 | 修复/重构 | **3D 预览性能修复·前端施工完成**（perf/preview3d）：步 3 IPv6 修复（`gui/src/utils/api.ts` 127.0.0.1 单一常量，14 文件 ~25 处 `localhost:5001` → `apiUrl`，grep 归零）；步 4 抽 4 深模块 `gui/src/three/`（TickGrid 台账+完整 dispose+步长表扩 1e6 / renderGate dirty 按需渲染 / cellMaterial 默认 opaque / cameraParams farNear≤1e4）+ Preview3D.tsx 接线 + 几何归一化（translate 先于 computeBoundingBox，相机 reframe）；步 5 加载态遮罩"正在生成 3D 几何…" + 半透明查看开关（默认关，M0 真空 opacity 0 不变）；vitest 基建（`gui/test/` 4 文件 13 用例全绿，devDependency，独立于 pytest 门禁）。tsc/build 通过。改动清单 docs/frontend-changes.md | 前端 |
| 2026-08-12 | 文档 | **3D 预览卡顿修复契约已锁定**：`docs/contracts/preview3d-performance.md`（复现实测修订版，repro 数据回填）。反驳原诊断 4 项（前端 STL 解析 54ms 非主因 / 120s 超时不触发 / OCC 无崩溃 / bound 布尔不慢）；确认真凶 P0a 打开卡（preview_cache 缓存 + 加载态，命中 ≤1s）、P0b 交互卡（TickGrid/renderGate/cellMaterial 深模块 + 默认 opaque + dirty 渲染）、P0c 深度（computeCameraParams 归一化 + far/near ≤1e4）；P0d 新发现（IPv6 前端 127.0.0.1 / vtk 惰性 / bound 位移参数 shield 5300→2700）。含 7 fixture 测试映射 + 后端 pytest 新增 3 文件 + 前端 vitest 4 文件 + 施工 6 步分工 + 3 项 PM 开放决策（半透明默认/vitest devDep/冷启动目标）。ADR 已补 3 条 | 架构师 |
| 2026-08-12 | 测试 | P1 终态复核（refactor/generator-tech-debt，基 996d11f）：全量 **251 绿 / 0 红** 确认（复跑稳定）。逐 F# 通过（F#7 模块顶 import / F#3 grep 归零 / F#4 `_build_sdef_parts` 合并且 pin 精确串不变 / F#5+F#6 kitchen-sink R1/R4 红→绿 g1==g2 字节恒定 len 2099==2099，5 项残留差异全消除 / F#1 `_apply_raw_override` 收敛 + 1145 门控 pin 绿）；纪律无降级（251 用例不变）、无新依赖、漂移闸门绿、`_wrap_long_lines`/`_generate_structured_distributions` 未入 diff、review_findings 7 项全 Resolved。`docs/qa-report.md` 标注 P1 终态。**全量计划（P0+P1+P2）完成** | 测试 |
| 2026-08-12 | 修复/重构 | **P1 技术债重构完成**（refactor/generator-tech-debt 分支，自 experiment/geouned 建）：全量 pytest **251 绿 / 0 红**（复跑 ×2 稳定），6 红全部转绿。F#7 bf0a2c7（pymcnp 提到模块顶部，test_f7_*×2 转绿）→ F#3 c774e56（函数内 import json/sys + E0DBG 清理，grep 归零，test_f3_*×2 转绿）→ F#4 52ca251（`_build_sdef_parts` 合并两分支，字节不变）→ F#5/F#6 4a e404172（`_generate_multi_source` 拆 5 函数 + SDEF_FIELD_SPECS 表驱动，字符化门 test_generator_multi_source.py 全绿）→ 4b/4c 018ced5（kitchen-sink R1/R4 红→绿：POS F-dist 重建 / sdef_extra 分布关键字去重 / SI V 型 / banners 注释 + 回放重发 / SI 值扁平化 / 字段序统一）→ F#1 1488aae（raw_overrides 收敛 `_apply_raw_override`，tally-key 门控保留，test_generator_overrides.py 28/28 绿）。重锚定：review_findings.json 7 项全 resolved + commit 索引；UI_ARCHITECTURE.md §5.2/§5.3/§6.4/§7/§7.1 更新；test_tech_debt.py 注释行号更新；PROJECT_MEMORY.md 本行 + §6。边界遵守：未碰 api.yaml / api_server 路由 / _wrap_long_lines / `_generate_structured_distributions` join。待 tester 复核 | 后端 |
| 2026-08-12 | 文档 | **P1 重构契约已锁定**：`docs/contracts/p1-refactor.md`（目标 251 绿/0 红，顺序 F#7→F#3→F#4→F#5+F#6→F#1）。F#5+F#6 拆 5 函数 + `SDEF_FIELD_SPECS` 表驱动，按 §0.5.5 复合根因清单逐项消除漂移（POS F-dist 分支重建 `POS=F D1` / sdef_extra 分布关键字去重 / `_parse_sisp_structured` SI 类型表加 V / 分布注释进 banners 词汇 + 回放重发 / SI 值扁平化 / 字段序统一）；`_generate_distribution_sdef` 一并改序。F#1 收敛为 `_apply_raw_override`（保留 1145 raw_tally 门控）。含施工顺序/每步验收/重锚定清单/风险预警。记忆文档 ADR 已补 3 条 | 架构师 |
| 2026-08-12 | 测试 | P0 第二轮复核（M1.4 门禁）：全量 **245 绿 / 6 红** 复核确认通过，放行 P1。minimal+3 样例 R1 全绿、F-B/C/D 转绿、129+73+7 零回归、无断言降级、P1 范围未触碰；6 红 = 4 技术债 F#3/F#7 + 2 kitchen-sink R1/R4（归 P1，残留差异纯化为多源 SDEF 漂移）。`docs/qa-report.md` 已更新 | 测试 |
| 2026-08-12 | 文档 | 重建 `app/UI_ARCHITECTURE.md`（7 节：边界图/启动链路/import-root/deck JSON 契约/raw_overrides/往返保真/技术债地图）。原 P2 产出因未 commit 被 `git checkout -- app/` 误清空（PM 回滚失误，非内容问题）；本次按 7 节结构复原，**全部行号已 Grep 重锚定到 F-A~F-E 修复后工作树**：raw_overrides 守卫 1069/1081/1107/1115/1131/1139/1147/1168 + 不一致变体 1156；`_wrap_long_lines` 1010；F#3 import json 631/671（原 622/660）；F#4 `_generate_single_source` 247；F#5 `_generate_multi_source` 375；F#6 源字段枚举 384-403/434-449/486-489；F#7 pymcnp import 110；E0DBG core.py 826-827/1018-1021、__init__.py 138-140、api_server.py 608-610。如实反映缺陷修复后行为（banners.py 新增、normalize_lines 剥 &、parse_f_tally 多粒子、_is_cell_line 大小写、validate_deck 解包、options 上移 M 头行）。 | 架构师 |
| 2026-08-12 | 修复 | 引擎缺陷修复 F-A~F-E 重新施工（app/ 回滚后）：F-A 方案 C（新增 `app/generator/banners.py` 冻结全部生成器节头词汇 + `split_sections` 拦截 + 生成器改调常量，R1 minimal+3 样例全绿）；F-B `validate_deck` 解包 CellRow；F-C `parse_f_tally` 多粒子逗号正则；F-D materials options 上移 M 头行；F-E `normalize_lines` 剥尾 & + 保留续行 $ 注释（prob41c 伴生修复）。可选翻新 F-F/F-G/F-H 已做（pin 翻新为正确行为断言）。全量 pytest **245 绿 / 6 红**（4 技术债 F#3/F#7 + 2 kitchen-sink R1/R4，P1 范围）。`docs/backend-changes.md`；`review_findings.json` 已重锚定；`app/UI_ARCHITECTURE.md` 基线为空文件需 PM 决策 | 后端 |
| 2026-08-12 | 测试 | P0 测试防线：`tests/`（unit 129 + parser 73 + integration 49，共 234 通过 / 17 失败——17 个全为技术债/往返缺陷的按设计先红 pin）；R1-R4 往返不变量；3 份 vendor 样例冒烟（prob41c/avr13/inp24）；F#1-F#7 联动测试；契约漂移闸门 7/7 通过；`docs/qa-report.md`；`dev-requirements.txt`。M1.4 未全绿（R1 头泄漏 + validate_deck CellRow 崩溃阻塞 P1） | 测试 |
| 2026-08-12 | 文档 | 补 `app/UI_ARCHITECTURE.md`（7 节：边界图/启动链路/import-root/deck JSON 契约/raw_overrides/往返保真/技术债地图）；新建 `docs/contracts/api.yaml`（OpenAPI 3.0，25 端点，每 path 带 operationId） | 架构师 |
| 2026-08-12 | 测试 | P0 测试防线第一轮：tests/ 全目录 + dev-requirements.txt（pytest>=8.0）+ 3 样例 vendor（prob41c/avr13/inp24，inp24 来自官方 REGRESSION 库）；234 通过/17 失败；M1.4 未全绿（F-A 头泄漏/F-B validate_deck 崩溃/F-C 多粒子计数丢失/F-D options 丢失/F-E & 续行污染） | 测试 |
| 2026-08-12 | 管理 | P0 首轮验收：M1.4 打回修复，派架构师出 F-A~F-E 修复契约（docs/contracts/bugfix-f1-f5.md） | 项目经理 |
| 2026-08-12 | 管理 | 上级复核引发分歧（245/6 与 234/17）：经权威基线测量定论 234/17（0 误判），分歧源于复核时机落在施工后未 commit 工作树；PM 裁决回滚 + 权威测量，上级最终裁决：契约有效、kitchen-sink SDEF 漂移归 P1 | 项目经理 |
| 2026-08-12 | 修复 | 引擎缺陷修复重新施工（按契约 §0.5）：F-A banners.py 方案 C（节头拦截 24 词汇+7 动态）、F-B _unwrap_cells、F-C 多粒子正则、F-D options 上移 M 头行、F-E 剥 & + 伴生续行 $ 注释修复、F-F/F-G/F-H pin 翻新；全量 245 绿/6 红 | 后端 |
| 2026-08-12 | 测试 | M1.4 复核通过：245/6 复跑稳定，门禁 §0.5.2 全过（minimal+3 样例 R1 全绿、F-B/C/D 转绿、129+73+7 零回归），无断言降级，P1 范围未触碰；kitchen-sink 残留差异纯化为多源 SDEF 漂移 = P1 F#5/F#6 验收基准 | 测试 |
| 2026-08-12 | 管理 | P0 验收通过（245/6 达成，P1 放行条件满足）；UI_ARCHITECTURE.md 因回滚误伤被清空，派架构师重建中 | 项目经理 |
| 2026-08-11 | 新增/重构 | 材料/栅元/计数双向文本↔表单互转（深模块 useSectionTextMode）；3D 预览优先解析文本栅元；删除基础/高级标签页冗余文本模式按钮；侧栏头像=应用图标；修复 E 卡续行吞 F 卡 | 前端/后端 |
| 2026-08-11 | 修复 | 截面拖拽平移 1:1 跟随鼠标（按 SVG 渲染尺寸而非 zoom 缩放）；打包文档内附带 README | 前端/后端 |
| 2026-08-11 | 修复 | C810 卡速查索引渲染为 markdown 表格（原为折叠纯文本） | 前端 |
| 2026-08-11 | 文档 | README 更新至 1.6.3（独立窗口、条件行、#n 补集、材料选择器、STL 截面） | — |
| 2026-08-11 | 构建 | 新增 `#/preview3d` 哈希路由（浏览器模式测试 3D 用） | 前端 |
| 2026-08-12 | 管理 | 启动"测试补防+技术债清偿+文档补齐"计划（P0 测试 tester 已派发 / P2 文档 architect 已派发 / P1 重构等 M1.4 全绿） | 项目经理 |
