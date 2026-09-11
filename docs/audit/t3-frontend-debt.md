# T3 前端代码债务扫描清单（前端权威落盘版）

> 本文件是团队 `tech-debt-audit` 任务 **t3「前端代码债务扫描」** 的完整交付物。
> 落盘原因：任务 output 在平台侧被截断（`team.json` 只存 2000 字符），PM 仅收到 FE-01~FE-04 与摘要。
> **追加交付，非重做审计**；内容与 t3 output 一致，并补全被截断的 FE-05…FE-20。

---

## 一、方法（静态核对 + 无 shell 声明）

**范围**：`gui/src/`（119 个源文件，components / utils / three / volume / ptrac / source / hooks / data）、`gui/test/`（**75 个 `*.test.ts(x)` + 1 个 `__snapshots__/*.snap`**，数字采用 researcher 实测；见 §8.7 关于我 v1 误报 81 的更正）、`gui/package.json`、`gui/tsconfig.json`、`gui/vite.config.ts`；`gui/src-tauri/src/main.rs` **只读引用**。

**手段**：本会话**无 shell 工具**（仅 read / glob / grep / write / edit）。全部结论来自**静态读取源码 + 只读 grep 计数 + 与 docs/test 文本互证**。代表性计数：`as any|: any|any[]|as unknown as` 在 `gui/src` **214 处**、`gui/test` **57 处**；`gui/src` 导出符号 468 处；`console.log` 在 `gui/src` **6 处**。

**未做的事（红线遵守）**：**未运行** `vitest` / `tsc` / `vite build` / `npm install` / `npm ci`，**未启动** dev server 或后端，**未修改任何代码**（本次仅新增本审计文档）。凡「跑起来才能定论」的项一律列入第五节「存疑」，**未实机验证**，不编造运行结果。

**行号**均取自实际读到的文件内容（非估算）。

---

## 二、完整债务清单（FE-01 … FE-20，20 条）

| 债ID | 类别 | 位置(file:line) | 证据 | 影响 | 建议严重度 | 建议处置 | 建议 Owner |
|---|---|---|---|---|---|---|---|
| FE-01 | 测试可信度／跨语言双实现 | `gui/test/latticeInstances.test.ts:370-414`（断言在 `:429-454`） | 用例注释（`:416-420`）自称「positions 格位中心 + composeNestedPositions 输出 === nested.leaves（双端逐位锁死）」，但参考实现 `expandPositionsRef()`(`:370-414`) 是**同文件内手写的 Python `expand_positions` TS 重抄**；断言只比「TS 重抄 ↔ golden」，**golden JSON 内没有后端原始产出字段**。 | 「双端锁死」名不符实：两侧同时漂移即静默通过；若公式在 TS 重抄里也写错，本用例不会红。这是全仓唯一的跨语言几何闸门。 | P1 | 由后端产出并写盘 golden 的 python 侧 `expand_positions` 原始输出，TS 侧只 import golden 断言；或将该用例降级为「TS 自洽」并另建真跨语言闸门。 | engineer-frontend + engineer-backend |
| FE-02 | 测试可信度（自指 skip 守卫） | `gui/test/latticeInstances.test.ts:421-429` | `hasGolden` 守卫读的是**被测对象自己**（`golden.positions` / `golden.nested` / `golden.composeCases`），条件不满足即 `it.skipIf` 静默跳过。已核实 golden 14 段全部实存（含 `positions` / `nested`(`leafCount:10`) / `composeCases`），故**当前 skipIf 不生效**；但一旦改键名或删段即静默变 skip，而门禁仍显示「0 failed」。 | 唯一跨语言用例可在「全绿」状态下失效；门禁数字覆盖不到它。 | P1 | 加 `expect(hasGolden).toBe(true)` 变硬断言；并让 skip 状态进入门禁输出解析（避免「0 failed」掩盖 skip）。 | engineer-frontend |
| FE-03 | 死代码（活模块） | `gui/src/components/Preview3DLattice.tsx:1-479` | 全仓 grep `Preview3DLattice` **仅命中该文件自身**（`:2` 注释、`:176` 定义）；`gui/src` 内**零 import**；`Preview3D.tsx:15` 已直接 import `buildLatticeInstances` 并内联装配（`Preview3D.tsx:721` 走 `/api/preview-lattice`）。 | 479 行重复装配逻辑（与 `Preview3D.tsx` 装配段重复）无编译/测试触达，持续腐化，并误导读者以为存在两条装配路径。 | P1 | 删除该文件；若有参考价值的内容移入 docs。 | engineer-frontend |
| FE-04 | 死代码（同名重复实现，最危险） | `gui/src/utils/backend.ts:74-95` | 该 `generateInp` **无人使用**——全仓只用 `dataCollector.generateInp`（`App.tsx:10`、`DiffDialog.tsx:8`、`SweepDialog.tsx:15`）。二者同名同端点 `/api/generate` 但行为不同：`backend.ts:83` 失败时 `console.log("Bridge not available, using mock")` 并**返回 `"// Python backend not connected"` 字符串**，`:85-92` 还会读磁盘陈旧 `output.inp`；`dataCollector.ts:27` 则正确抛错。 | IDE 自动补全极易误选：生成失败会**静默返回注释串**而非报错，且夹杂 mock/陈旧文件回退——属运行期隐患。 | P1 | 删 `backend.ts:74-95` 及其 `DeckData` import；保留 `startPythonBackend`/`stopPythonBackend`（`App.tsx:100-101` 在用）。 | engineer-frontend |
| FE-05 | 「保留兼容」死导出 | `gui/src/utils/lattice.ts:171-184` | `UNIVERSE_PALETTE_12` 的功能已被 golden-angle 哈希替代（`universeColorByRank` `:192-203`、`buildUniversePalette` `:209-220`）；全仓消费点只有 `gui/test/lattice.test.ts:44` 的 import，**src 内零引用**。 | 死常量会被误当权威色板；测试引用它只制造「有人在用」的假象。 | P2 | 删除常量 + 清 `lattice.test.ts:44` import；同步回收 PROJECT_MEMORY 中「保留导出兼容」的措辞（该项目记忆条目位于 `PROJECT_MEMORY.md:119`）。 | engineer-frontend |
| FE-06 | 死导出 | `gui/src/utils/lattice.ts:447-471` | `estimateLatticeExtent` 全仓消费点只有 `lattice.test.ts:19,227-241`；**src 内零引用**——真实格元盒已由后端 `/api/lattice-extent` 提供（`MacrobodyPreview.tsx:55`、`Preview3DLattice.tsx:223`）；本函数 hex 分支仍写死 `pitch = 1`（`:453`）。 | 用单位 pitch 估算的旧函数留在权威模块里，与真实格距路径并存，后续读者易误用。 | P2 | 删除函数 + 其 hex 分支测试（`lattice.test.ts:227-241`）；`docs/qa-report-phase2.md:78` 的「阶段3 衔接」建议就此结案。 | engineer-frontend |
| FE-07 | 跨语言双实现／文档代码漂移 | `gui/src/utils/lattice.ts:123-128`；`gui/test/lattice.test.ts:131`；`docs/frontend-changes.md:11,208,1234`；`docs/qa-report.md:64`；`docs/qa-report-phase2.md:50`；`docs/qa-report-total.md:24`；`docs/backend-changes.md:1285`；`docs/contracts/lattice-fix15-design.md:171-172,450`；`PROJECT_MEMORY.md:166,172,178,179,208` | `hexCenter` **代码**是权威新公式 `x = col*pitch + row*(pitch/2)`、`y = row*pitch*(√3/2)`（`:134-136`，与 `app/lattice.py:615-616` 逐字一致）；但**旧公式 `x=i·p·√3/2, y=j·p+(i%2)·p/2`（差 30° 旋转）仍存在于 16 处**（我 v1 只列 4 处，**v3 经 researcher 独立复核采信其 16 处清点、并自行 grep 复核一致**）：`lattice.ts:123-128` docstring、`lattice.test.ts:131` describe 名、`frontend-changes.md:11/208/1234`、`qa-report.md:64`、`qa-report-phase2.md:50`、`qa-report-total.md:24`、`backend-changes.md:1285`、**`contracts/lattice-fix15-design.md:171-172` 与 L1 锁死表 `:450`**、`PROJECT_MEMORY.md:166/172/178/179/208`。 | 注释/文档与实际代码差 **30° 旋转**，且**契约 L1 锁死表写的也是错公式**（会污染跨语言实现）。这是被反复「根因修复」过的高危公式，下次有人按注释或 L1 表改动即引入几何回归。 | P1 | 16 处一次性替换为新公式（**实现不动**），docstring 补齐自洽核验并交叉引用 `app/lattice.py:604-613`；测试 describe 名同步。**同根因去重**：researcher 已登记 M-21、T2 侧为 BE-14 —— 三者同根因，请 T4 合并为一条、勿重复计。 | engineer-frontend + researcher（+ 架构师改契约 L1 表） |
| FE-08 | 类型债（门禁盲区） | `gui/tsconfig.json:21-23`；`gui/package.json:6-12` | `include: ["src"]` —— test 目录**不在 tsc 项目内**；`package.json` 无 `typecheck` 脚本、无 `tsc` 步骤，只有 `test: vitest run`、`build: vite build`（后者不做类型检查）。PROJECT_MEMORY 多轮记载的门禁「tsc EXIT 0」实际覆盖不到全部测试文件（**75 个 `*.test.ts(x)`**，其中 57 处 `any`）。 | 测试代码与契约镜像可长期类型错误而门禁全绿；FE-01 那类「TS 重抄」漂移没有任何编译期拦截。 | P1 | 加 `tsconfig.test.json`（include `test`，继承主配置）+ `"typecheck": "tsc -p tsconfig.json && tsc -p tsconfig.test.json"`，接入门禁描述。零新依赖。 | engineer-frontend |
| FE-09 | 测试反模式（时间断言） | `gui/test/volume/colorize.test.ts:137-146`（断言在 **`:145`**，`t0` 在 `:141`） | 单次采样、无 warmup、无重试、无分位数：`performance.now()`(`:141`) → `colorizeScalar(128³)`(`:142`) → `expect(dt).toBeLessThan(50)`(`:145`)；且 `:140` 先花 O(n) 时间填充 16.7M 字节数组（本身可能触发 GC）。PROJECT_MEMORY **至少 5-6 处**记载同一 flaky（`:87`、`:98`、`:137`、`:222`、`:235`、`:526`）。 | 典型「单样本墙钟阈值断言」反模式：CI/并发负载下随机红，逼出「隔离单跑绿、非回归」这类人情判断，削弱门禁可信度。 | P1 | 正确性断言保留、性能断言移出默认门禁：① 采样 N≥5 取中位数 + 宽松上限（如 `<150ms`）；或 ② 改相对断言（如 CPU 上色 vs 朴素实现的加速比）；或 ③ `it.skipIf(!process.env.PERF)` + 另设 perf 脚本。并删除「已知 flaky」这条长期豁免。 | engineer-frontend |
| FE-10 | 测试缺口（记忆自认） | `gui/src/source/SourceDemoRenderer.ts:56-121`；`gui/src/components/SourceTab.tsx:69-205`；`gui/test/source/SourceDemoWindow.test.tsx:11-17` | `SourceDemoRenderer` 无任何单测（`createSourceDemoRenderer` 仅由 `SourceDemoWindow.tsx:51,65` 调用）；`SourceTab` 无组件测试（全仓 `SourceTab` 仅 `TabPanels.tsx:3,20` 消费）；唯一 source 测试只做 SSR 兜底（`renderToString` + 断言「没有演示源数据」）。PROJECT_MEMORY 自认未做（`PROJECT_MEMORY.md:31`）。 | 「🎬 演示源」按钮的前置校验 → 红字 → 开窗链路，以及粒子抽样 → 点云/方向线映射均无回归网；任何重构只能靠人工冒烟。 | P2 | 折中方案降低投入：把 `setParticles` / 能量归一化 / 方向线长度等**纯函数或可注入 seam** 抽出（不需 WebGL）加纯单测；`SourceTab` 用 jsdom + mock `sourceDemoSample`/`windows` 覆盖「error → 红字不开窗 / ok → 写桥开窗」两条分支（照 `sweepDialog.dom.test.tsx` 现成模式）。 | engineer-frontend |
| FE-11 | 测试覆盖缺口（反向） | `gui/test/volume/windowRouteConsistency.test.ts:42-51`（数组在 `:45`） | 已逐条核实 **5 个 label 全覆盖**：`preview3d` / `cross_section` / `volume` / `ptrac` / `source-demo` 在 `main.rs:74-98` 与 `App.tsx:477-481` 均存在且同值，`volume3d` 已消失（`:50` 的 `not.toContain` 成立）。**缺口在反面**：没有任何断言保证「未来新增第 6 个窗口」也必须进 `:45` 的数组。 | 新窗口若只在 `main.rs` + `App.tsx` 加而忘了加进该数组，本测试仍绿（因 `:38` 的集合相等分支已覆盖），守卫失去「逐个同值」的独立校验。 | P3 | 期望 label 列表改为从 `main.rs` 提取结果派生，或加一条「路由分支数 == 5 且无未经断言的 label」的断言。 | engineer-frontend |
| FE-12 | 测试脆弱性（正则守卫） | `gui/test/volume/windowRouteConsistency.test.ts:26`、`:33`、`:38-40` | `mainRsWindowLabels` 正则 `create_or_focus\(&app, "([^"]+)"` 与 `appRouteLabels` 正则 `if \(label === "([^"]+)"\) return` 都对**字面格式**敏感（双引号、单行、无换行）。两侧同时抽取为空数组时 `expect([]).toEqual([])` **通过**——空对空即假绿。当前格式恰好匹配（`main.rs:74` 等为单行双引号），故**现在真跑真过**，无 skip。 | 一次 Prettier/重构（改单引号、拆多行）就可能让守卫在「全绿」状态下失效而不报警。 | P2 | 加持 `expect(m.length).toBeGreaterThan(0)` / `expect(a.length).toBe(5)` 护栏；或改用 label 常量（如 src 内 `WINDOW_LABELS`）单一来源，测试比对常量而非正则。 | engineer-frontend |
| FE-13 | 类型债（双 `CellData` + `any` 抹平） | `gui/src/utils/DeckContext.tsx:12` vs `gui/src/components/CellEditDialog.tsx:6-27`；`gui/src/utils/cellBridge.ts:10,19,47`；`gui/src/components/GeometryTab.tsx:48` | 同名同语义**两套接口、不同命名**：`DeckContext.CellData` 用 snake_case（`number/material/surface_expr/imp_n/imp_p/imp_e/other_params`），`CellEditDialog.CellData` 用 camelCase（`num/mat/surfaces/impN/impP/impE/otherParams`）；桥接靠手写映射，且 `cellBridge.ts:10` 自认「新增/修改字段必须 local↔deck 两处同步 + **类型三处同步**」——纪律全靠注释。更糟：`GeometryTab.tsx:48` 用 `useDeckSynced<LocalCellRow[], any[]>` 把 deck 侧声明成 `any[]`，编译期校验被关掉（`TallyTab.tsx:93` 同）。 | 字段漂移无法被类型系统发现：`Preview3D.tsx:600-602` 与 `:894-896` 已出现 `impN \|\| imp_n` 式**防御性双读**（同一字段两套命名并存的实证），`cellBridge.ts:57-59` 亦然。 | P1 | ① 单一 `CellData` 定义（建议 camelCase 本地 + 明确的 `DeckCellPayload` snake_case 契约类型）；② `useDeckSynced<LocalCellRow[], CellRow[]>` 去掉 `any[]`；③ 加「cellBridge 字段覆盖」单测（对 `keyof` 两向穷举断言），把注释纪律变成测试。 | engineer-frontend |
| FE-14 | 类型债（any 泛滥） | 全 `gui/src/`，热点 `gui/src/components/Preview3D.tsx`（约 70 处）、`gui/src/utils/windows.ts:54,74,92,176,220,229`、`gui/src/utils/api.ts:101,120,121,155,157`、`gui/src/utils/dataCollector.ts:10-12` | grep `as any\|: any\|any[]\|as unknown as` = **src 214 处 / test 57 处**（`tsconfig.json:18` 已 `strict: true`，但被 `any` 逐个短路）。热点集中在三处真 seam：Preview3D 的 cells/deck 载荷、`windows.ts` 的桥载荷、`api.ts` 的响应。 | strict 配置形同虚设；FE-07 那种「注释与代码差 30°」正是无类型约束下的产物；Preview3D（1400+ 行）的深层重构无类型护栏。 | P2 | 分两步收敛，不追求清零：① 先给 `windows.ts` / `api.ts` 的桥与响应建类型（对外契约，收益最高）；② `Preview3D.tsx:56` 已有内联 cells 结构类型，把它提为共享 `CellViewPayload` 并扩用。 | engineer-frontend |
| FE-15 | 日志回潮（定向证据） | `gui/src/utils/backend.ts:15,18,33,40,46,83`（全仓 `gui/src` 仅此 6 处 `console.log`） | `gui/test/preview3dDeadLog.test.ts:13` 的守卫**只读 `Preview3D.tsx` 单文件**（`SRC = readFileSync(join(HERE, "../src/components/Preview3D.tsx"))`）；全仓 grep `dbgLog` 只命中该测试文件自身的字符串 → 守卫范围内未回潮。其中 `:15/:18/:33/:40/:46` 是 sidecar 生命周期日志（可接受），**`:83` 的 `console.log("Bridge not available, using mock")` 是把失败降级成正常路径的日志**，与 FE-04 同源。 | 「清理已完成」的结论仅对单文件成立；守卫范围 = 单文件，回潮窗口仍然敞开。 | P2 | 守卫扩为扫描 `gui/src/**`（白名单 `backend.ts` 的 sidecar 日志）；随 FE-04 一并删 `:83`。 | engineer-frontend |
| FE-16 | 文档/脚本缺口 | `gui/package.json:6-12`、`gui/vite.config.ts:1-9`、`gui/README.md:7-19` | `vite.config.ts` **无 `test` 配置块**（vitest 走默认），无 `setupFiles` / `globals` / `coverage`；测试环境靠 13 个文件顶部的 `// @vitest-environment jsdom` 逐文件 pragma（如 `batchCellEditDialog.dom.test.tsx:1`）；README 只有 `npm install` / `npm run dev` / `npm run tauri dev` / `npm run tauri build`，**没有 `npm test`**。 | 环境与全局配置无单一来源：新增 DOM 测试漏 pragma 时会拿到 Node 环境（`document` 未定义），报错点与真因无关；新人按 README 找不到测试入口。 | P3 | ① README 补 `npm test`（vitest）一行；② 可选在 `vite.config.ts` 加 `test: {}` 块并显式写明「DOM 用例需 pragma」的约定注释。 | engineer-frontend |
| FE-17 | 魔法常量重复 | `gui/src/components/Preview3D.tsx:745`、`gui/src/components/Preview3DLattice.tsx:277`、`gui/backend/api_server.py:3425` | BEAVRS 专属 `1.26` 作为 `subPitch` 兜底**三处硬编码**（前端两处 + 后端一处）；后端 `:3412-3417` 注释已自认「应取该格阵自己的 pitch，而不是硬编码 BEAVRS 专属的 1.26」；`gui/src/three/latticeInstances.ts:312-315` 又依赖它决定 disc 半径。 | disc 半径语义在不同 deck 下静默取错值（BEAVRS 之外的模型没有理由拿 1.26）；三处漂移后行为不一致，且无测试锁。 | P2 | 前端两处合并为单一导出常量（或直接从后端 fidelity 取；缺失即显式报错而非静默兜底）；后端 `_subpitch` 按 `:3416-3417` 注释改为「取该格阵自身 pitch」。 | engineer-frontend + engineer-backend |
| FE-18 | 旧数据兼容无清理计划 | `gui/src/utils/sourceAdv.ts:147-169`、`gui/src/utils/cellBridge.ts:50-51`、`gui/src/utils/DeckContext.tsx:70`、`gui/src/App.tsx:45`、`gui/src/volume/fmeshState.ts:435` | 五处「兼容旧数据」并存且**均无退场条件/版本号**：`migrateLegacySourceKeys`（旧顶层源中间态）、`deckToLocalCells` 的「CellRow 或旧平铺 STEP 格式」双分支、`universeComments` 可选、主题「曾存工作区 JSON，首次读一次后迁移」、`fmesh_defs` 的 `eints/t_ints` 旧键容忍。 | 兼容层无到期机制会永久滞留：每个都要写双分支测试、每次改字段都要考虑两种形态；`cellBridge` 的旧平铺分支（`:50-51`）是 FE-13 类新错误的温床。 | P3 | 逐条标注引入版本 + 计划退场版本（写入代码注释即可，不需文档）；`migrateLegacySourceKeys` 与 `deckToLocalCells` 旧格式分支建议定「下个大版本删」。 | engineer-frontend（+ researcher 记录） |
| FE-19 | 命名/常量重复 | `gui/src/utils/alignWorld.ts:16` vs `gui/src/volume/surfacesAABB.ts:20` | `Vec3` 在 volume 域内两处独立定义（另 `alignWorld.ts:18` 与 `surfacesAABB.ts:26` 各定义 `AABB`）；`Vec3` 语义完全一致。 | 低危但会随重构扩散。 | P3 | 收敛到 `alignWorld.ts` 的 `Vec3` 并 export，`surfacesAABB.ts` 改 import。 | engineer-frontend |
| FE-20 | 测试债 | `gui/test/lattice.test.ts:275,295,326,372,384,398,437,448,455-456`；`gui/test/latticeInstances.test.ts:421-423` | 共 **11 处** `golden.xxx as any[]`；`gui/tsconfig.json:14` 已开 `resolveJsonModule`，golden JSON 本可生成/手写类型。段名拼错或结构改动都不会被编译期发现，只能等运行时遍历 `undefined`（空数组）→ 又一条「静默通过」路径。 | 跨语言唯一权威数据集的消费侧无类型护栏；与 FE-08 叠加后完全裸奔。 | P2 | 为 golden 写 `interface LatticeGolden {...}`（或从后端 schema 生成），把 11 处 `as any` 换成具名类型；**需配合 FE-08 的 `tsconfig.test.json` 才有效**。 | engineer-frontend |

### 严重度汇总
- **债条数：20**（FE-01 … FE-20）
- **建议 P0：0 条** —— 未发现当前必然致故障的项。最接近 P0 的是 **FE-01 / FE-02**（跨语言测试可信度），其定级取决于第五节 **Q3**（门禁是否含未察觉的 skip），故本次给 P1 并标注升级条件。
- **建议 P1：8 条** —— FE-01、FE-02、FE-03、FE-04、FE-07、FE-08、FE-09、FE-13
- **建议 P2：8 条** —— FE-05、FE-06、FE-10、FE-12、FE-14、FE-15、FE-17、FE-20
- **建议 P3：4 条** —— FE-11、FE-16、FE-18、FE-19

> **附注（PM 后续注入证据 + 跨组回执衍生）**：PM 注入「外部会话新增 4 个前端模块但无测试」的证据经复核**成立**，扩出 FE-21 / FE-21a / FE-21b / FE-21c（3 条 P1、1 条 P2）；另有跨组回执衍生 **FE-22（P3，TRCL/pitch 跨语言口径漂移）**。⇒ **总债数 25 条（P1 12 / P2 9 / P3 5，P0 0）**。本文件按 PM 指令**以 FE-01…FE-20 为主表**保留 §2 不动，追加条目承载于 §6 与 §8.6。

---

## 三、已核实已清偿（勿再报，10 项）

| 项 | 位置 | 核实结论 |
|---|---|---|
| ① 模块级可变缓存 + React 缓存冻结（曾发生在 `useMaterialLibrary`） | `gui/src/hooks/useMaterialLibrary.ts:18,23,27,30,33,50,60-63` | **已修复且有防回归注释**。`_cache` 仍在，但 `entries` 已刻意**不**用 `useMemo`，`:60-61` 写明原因（依赖不在 React deps 里的模块级缓存会读到旧值）。全仓再无非 `useMaterialLibrary` 的 `let _xxx` 模块级缓存（`^let ` 仅命中 `backend.ts:5-7` 的进程句柄与本文件 `:18`）。 |
| ② 跨语言 golden 文件真实存在（非空跑） | `gui/src/utils/__golden__/latticeGolden.json:3,77,107,198,376,531,596,779,802,831,855,893,916,938,967` | **14 个段全部实存**：`rectGrid` / `hexCenter` / `validate` / `positions` / `nested`（含 `leafCount: 10`）/ `composeCases` / `dirCounts` / `macrobody` / `rhpMacro` / `collectFillUniverses` / `compressRaw` / `cycle`。故 `latticeInstances.test.ts:424-429` 的 `hasGolden`（依赖 `positions.length>0` + `nested.leaves.length>0` + `composeCases[0].node`）**条件成立、skipIf 不生效**。⚠️ 但「不 skip」≠「断言有效」，见 FE-01 / FE-02。 |
| ③ windowRouter 是否覆盖全部窗口（含 source-demo / volume / ptrac） | `gui/test/volume/windowRouteConsistency.test.ts:42-51`；`gui/src/App.tsx:477-481`；`gui/src-tauri/src/main.rs:74-98` | **覆盖完整**。5 个 label 逐一核对：`preview3d` / `cross_section` / `volume` / `ptrac` / `source-demo` 在 `main.rs` 的 `create_or_focus` 与 `App.tsx` 的路由分支**均存在且同值**；`volume3d` 确认已消失（`:50` 的 `not.toContain` 成立）；`source-demo` 已在测试数组内（`:45`）。 |
| ④ `colorize.ts` 跨语言实现 | `gui/src/volume/colorize.ts:17-32,56-73`；`app/meshtal/colormap.py:26-44`；`gui/test/volume/colorize.test.ts:16-20` | **无漂移**。TS `roundHalfEven`(`:26-32`) 忠实镜像 Python `round()` 的 half-even 语义；`weatherLut` 的逐字节 sha256 断言 `36770ae2…` **实测存在于测试**（`:20`），非注释吹牛。 |
| ⑤ 死代码 TODO/FIXME 回潮 | 全 `gui/src/` | **零回潮**：grep `TODO\|FIXME\|XXX\|HACK\|@deprecated` 在 src 内 **0 命中**（3 处「临时/旧」类命中均为无关业务文案，如 `gpuInfo.ts:63`「创建临时 context」）。 |
| ⑥ `console.log` / `dbgLog` 回潮 | 见 FE-15 | `gui/src` 内 `console.log` **仅 6 处且全在 `backend.ts`**（sidecar 生命周期 + 一处 mock 降级日志）；`dbgLog` 死代码确认已删（`preview3dDeadLog.test.ts:16-20` 断言通过）。**结论：主体已清偿，残余见 FE-15 与 FE-04。** |
| ⑦ `UNIVERSE_PALETTE_12` 是否还在生产用 | 见 FE-05 | 确认为**死导出**（非「在用」）：`gui/src` 零引用。记忆里「保留导出兼容」的措辞需回收。 |
| ⑧ `gui/dist/` 是否被误提交 | `gui/.gitignore:1-4`、`.gitignore:1-51` | **无问题**：`gui/.gitignore:2` 已忽略 `dist/`，根 `.gitignore:8` 亦忽略 `dist/`。（`gui/dist/` 目录本体存在，属本地构建产物，未纳入版本控制。） |
| ⑨ jsdom pragma 遗漏 | `gui/test/` | **无遗漏**：11 个使用 `@testing-library/react` 的文件**全部首行**带 `// @vitest-environment jsdom`（逐文件核对）；4 个使用 `renderToString` 的（`sidebarVersion.test.tsx` / `source/SourceDemoWindow.test.tsx` / `ptrac/PtracWindow.test.ts` / `sweepDialog.test.tsx` / `volume/ColorLegend.test.ts` 等，Server 端渲染）刻意不带，符合各自需求。 |
| ⑩ 版本号单一来源 | `gui/package.json:4`（`1.7.5`）；`gui/src/components/Sidebar.tsx:45`；`gui/test/sidebarVersion.test.tsx:5,12,21-22` | **一致**：`Sidebar` 读 `pkg.version`，测试直接 import `../package.json` 断言，无硬编码漂移。 |

---

## 四、存疑（未实机验证；原 8 项，Q5/Q6 已闭环 + 新增 Q6b 后 9 项）

> **状态更新（两轮后端回执后）**：**Q5 已闭环 → 结论「不排除」**（两侧 TRCL 机制确实不同，已升级为 FE-22）；**Q6 已闭环**（`fidelity.subPitch` 永远在场，前端两处兜底是防御代码）；**新增 Q6b**（封闭性断言的 bound 依赖约束）。

| # | 存疑项 | 未验证的部分 | 建议验证方式 |
|---|---|---|---|
| Q1 | 跨语言 golden 是否真跑无 skip | 本会话**无 shell**，未执行 vitest。静态推断「`hasGolden` 为真 → skipIf 不生效」，但无法确认 vitest 报告中的 skipped 计数为 0。 | 允许 shell 后跑 `npx vitest run gui/test/latticeInstances.test.ts` 看 `skipped` 列；或直接加 `expect(hasGolden).toBe(true)` 把它变成硬断言（FE-02 的建议）。 |
| Q2 | `colorize 128³ < 50ms` 的失败率 | 未跑。PROJECT_MEMORY 有 5-6 处记载 flaky，但无失败次数/运行次数统计。 | 连跑 20 次记录 `dt` 分布（p50/p95/max），再决定阈值与是否移出门禁（FE-09）。 |
| Q3 | 「546/0 全绿」是否含 skip | 未跑全量。记忆里的数字无法区分 pass 与 skip。 | 跑一次并留全量日志，grep `skipped`。**这直接决定 FE-01 / FE-02 的严重度是否升级为 P0。** |
| Q4 | FE-09 的 `dt` 与机器负载的相关性 | 未实测。该断言在开发机「隔离单跑绿」，CI/并发负载下是否必红未知。 | 在有并发负载的机器上跑该单文件 5 次。 |
| Q5（**已由 engineer-backend 回执闭环：不排除**） | `parseTrclDeg` 与后端 TRCL 口径是否一致 | **前端**（`gui/src/three/latticeInstances.ts:248-259`）：把 TRCL 串当「三个角 token」，`const z = toks.length >= 3 ? toks[2] : 末位`（`:256`），再 `((z % step) + step) % step`，`step` = lat"2"→60 / lat"1"→90 / 无 lat→360（`:257-258`）。**后端**：其值来源 = **`gui/backend/api_server.py:622-644` 的 `_cell_trcl_deg`**（**`atan2@:642`**，调用点 **`:3280`**；由 TR 卡旋转矩阵首行反解、**无 mod**）；`api_server.py` 构造 compose 上下文时传 `"trcl": float(trcl or 0)`（`app/lattice.py:1249`）——**该几行只是消费 `_cell_trcl_deg` 已算好的 `trcl_deg`**——一路透传到 `expand_positions(..., trcl_rotation_deg=ctx["trcl"])`（`:1266`）、`math.radians(float(trcl_rotation_deg or 0))`（`:1044`），并**原样回发** `"trclRotationDeg": ctx["trcl"]`（`:1282`）——**后端不做 `% 60/% 90/% 360` 归一化**（全仓 `app/lattice.py` 的 `% 360.0` 只在 `:527`/`:836`，用于**曲面法向角**，与旋转无关）。⇒ **两侧机制不同**：后端吃的是「已归一化的度数」（其归一化由前端 `parseTrclDeg` 依契约负责），前端 fallback 却吃「原始 token 串」。**两条真实分歧**：① TRCL 若写成 MCNP 的「3 角 + 3 平移」形式（如 4 个 token），前端取 `toks[2]` 可能不是 Z 角；② 后端可为负角、前端恒非负。**门槛高**：`api_server.py` **总会**下发 `trclRotationDeg`，故 `Preview3DLattice.tsx:272` 的 `primary ? (primary.trclRotationDeg ?? 0) : parseTrclDeg(...)` fallback 只在 `primary` 为空时才走。 | 属**潜在债而非现行 bug**（fallback 当前不可达）。已发后端回执确认；**处置建议**：统一口径——要么 fallback 改为同语义，要么删 fallback 改 `?? 0` 并在契约里钉「`trclRotationDeg` 必下发」。已记入新增的 FE-22。 |
| Q6 | `subPitch` 兜底 `1.26` 的实际影响面（**已闭环**） | FE-17 的「1.26 兜底」问题**已闭合，且我原先的定级需再次修正**：`api_server.py:3418` `_subpitch = None` → `:3419-3423` 遍历 `composed["lattices"]` 取各格阵 pitch 的 min → **`:3424-3425` `if _subpitch is None: _subpitch = 1.26`** → **`:3426-3431` `_fid = {... "subPitch": _subpitch}` 无条件写入**。⇒ **`fidelity.subPitch` 永远在场**（deck 无任何格阵时就是 `1.26`），故**前端 `Preview3D.tsx:745` 与 `Preview3DLattice.tsx:277` 的两处 `1.26` 兜底取不到，是纯防御代码而非活路径**。 | 已闭环，无需再验。断言可直接写「`fidelity.subPitch` == 该格阵自身 pitch」（单格阵 U233 hex = 1.45034 已修好）。 |
| Q6b | 封闭性断言的可写性约束（**后端已给出精确语义，新补**） | 后端回执明确指出：`semi_infinite` / `infinite` / `closed` 的判定**依赖包围盒 `bound`**（容差 `tol = B * 0.005`，`app/_freecad_csg_worker.py:1160`）→ 同一 cell 在不同 `bound` 下可能从 `closed` 变 `semi_infinite`。故前端补断言时**不能写「固定期望 semi_infinite」**，必须按「给定 bound 下的期望」写；且 `infinite_axes` 恒定性为：`infinite`→`["x","y","z"]`、`semi_infinite`→长度 1 或 2、`closed`→`[]`、`aabb is None` 的三种（`empty`/`voxel`/`unresolvable`）→缺失。 | 写 FE-21 的 `cellClosure.test.ts` 时按此语义逐条构造 fixture（见第六节建议清单第 1-3 项）。 |
| Q7 | `Preview3DLattice.tsx` 是否属「计划中的未来入口」 | 全仓确认当前零 import（FE-03）。但 `docs/contracts/core3d-instancing.md:130,188`、`docs/qa-report.md:89` 仍把它当作装配视图的**生产**消费方描述，可能与真实代码状态脱节。 | 请 **researcher** 核对 docs 与代码状态；若确为废弃实现则连 docs 一起清。已直发。 |
| Q8 | Preview3D 的约 70 处 `any` 是否掩盖了运行期真 bug | 未跑；仅确认数量与热点。 | 单独派「Preview3D 拆分」类任务时逐段收类型，顺手暴露。 |

> **数字更正（v4，researcher 独立复核后）**：① **v1 我写的「`gui/test/**` 81 个 `*.test.*`」撤回** —— 我的分项「61+19+4」自身就不等于 81，**内部不自洽，属我的计数错误**；**权威数字采用 researcher 实测：76 个文件 = 75 个 `*.test.ts(x)` + 1 个 `__snapshots__/*.snap`**（分项：根 47 / `volume/` 23 / `ptrac/` 4 / `source/` 1；我本轮新跑的 glob 只给出「≥60 个 `.test.ts` + 15 个 `.test.tsx`」的量级，**无法在无 shell 条件下给出逐目录权威分项，故一律引用 researcher 的数字，不再自报**）。② PROJECT_MEMORY 的「546/0（69 文件）」等数字是**各批当时快照**（researcher 登记为 M-20，P2）。③ **FE-21 的「4 模块零测试」结论不受影响** —— 判定用的是**内容 grep**（对 `cellClosure` / `useCellClosure` / `computeAppScale` / `useDeckSynced` 等标识符搜 `gui/test/**`，零命中），**不依赖文件计数**（researcher 亦认同此独立性声明）。

---

## 五、跨组交办项（已直发，抄送 PM）

以下请求均由 engineer-frontend **直接发消息**给对应成员（团队规则允许成员间直连，不经 PM 中转）。此处仅登记交办内容与期望回执，**不代表已完成**。

### 5.1 → engineer-backend（4 项）

| # | 事项 | 关联债 | 请求内容 | 期望回执 |
|---|---|---|---|---|
| B1 | 由后端产出并写盘 golden 的 python 侧 `expand_positions` 原始输出 | FE-01 | `gui/test/latticeInstances.test.ts:370-414` 的 `expandPositionsRef()` 是同文件手写的 Python TS 重抄，断言只比「重抄 ↔ golden」，golden 内无后端原始产出 → 「双端锁死」名不符实。请评估能否让 `_golden_positions_*` 生成器统一写盘 python 原始输出（或加 `expected_python` 字段）。 | 可行/不可行 + 工作量；若不可行，前端将把该用例降级为「TS 自洽」并另立闸门。 |
| B2 | `_subpitch` 兜底改为「取该格阵自身 pitch」 | FE-17 | `gui/backend/api_server.py:3425` 仍是 `_subpitch = 1.26`（BEAVRS 专属硬编码），而其 `:3412-3417` 注释已自认应改为取格阵自身 pitch；前端另有 `Preview3D.tsx:745`、`Preview3DLattice.tsx:277` 两处同值硬编码。另请确认「deck 无任何格阵」时 `fidelity.subPitch` 是否确实缺席（决定前端兜底是否真会被取到，见 Q6）。 | 确认或缺席结论 + 是否改 `_subpitch`。 |
| B3 | `checkCellClosure` 响应 schema 补 6 状态枚举 + 产出 `closureGolden.json` | FE-21（跨端状态词表无锁） | 封闭性判定在 `app/_freecad_csg_worker.py:1122-1175`（`closed`@`:1157`、`infinite`@`:1168-1169`、`semi_infinite`@`:1170-1171`、`empty`@`:1148`、`voxel`@`:1140`、`unresolvable`@`:1137`），前端 `gui/src/utils/cellClosure.ts:15` 逐字复刻。端点**注册**在 `api_server.py:1464`、**handler 定义**在 `:1830`（※ v1 曾误引 `:1450`，那是 `/api/cross-section`；已修正）。`docs/contracts/api.yaml:1452` 的 **summary 散文里已列举**该 6 状态，但 **`:1484` 的 schema 只写 `status: { type: string }`** → 漂移闸门（handlers↔api.yaml AST 双向存在性）**结构上校验不到 enum**；`:1496` 的 `infinite_axes` 也未钉住「非空 ⟺ semi_infinite/infinite」语义。`latticeGolden.json` 无 closure 段 → 后端改名/新增状态时前端静默掉进 `cellClosure.ts:53` 的 fallback（`icon:"?"`、英文状态串）且无测试会红。 | ① `:1484` 改 `enum: [closed, infinite, semi_infinite, empty, voxel, unresolvable]`（加性收紧，不动 handlers 签名）**并必须在闸门补一条 HTTP 用例断言「响应中的 status ∈ enum」**，否则 enum 只是文档装饰；② 顺手钉住 `infinite_axes` 语义；③ 照 `latticeGolden` 增 `closureGolden.json` 时**由 Python 写盘、TS 只读断言**（避免 FE-01 那种「既写又断言」的坑）。 |
| B4 | 核对 `app/lattice.py` 的 TRCL 归一化口径 | Q5 | 前端 `gui/src/three/latticeInstances.ts:248-259` 实测：取第 3 个 token（不足取末位），mod 基数 lat2→60 / lat1→90 / 无 lat→360。请核对后端是否同口径。 | 一致 → 回「Q5 排除」；不一致 → 给出后端实际口径（这会是新债）。 |

### 5.2 → reviewer（2 项裁决）

| # | 事项 | 关联债 | 请求内容 |
|---|---|---|---|
| R1 | 是否因 skip 盲区把 FE-01 / FE-02 升为 **P0** | FE-01、FE-02（依赖 Q3） | 若「546/0 全绿」中混有未察觉的 skip，则「唯一跨语言几何闸门实际未生效」属 P0；请依 Q3 的验证结果裁决定级。 |
| R2 | FE-09 计时断言阈值裁决 | FE-09 | 在「保留性能回归价值」与「门禁稳定性」之间取舍：建议方案（N≥5 中位数 + 宽松上限 / 相对断言 / `PERF` 环境变量另跑）请择一或另定。 |

### 5.3 → researcher（3 项文档核对）

| # | 事项 | 关联债 | 请求内容 |
|---|---|---|---|
| D1 | `hexCenter` 权威公式在各文档中的旧式残留 | FE-07 | 代码（`gui/src/utils/lattice.ts:134-136`）与 `app/lattice.py:615-616` 是新公式；但前端 docstring（`lattice.ts:124-128`）、`docs/frontend-changes.md:11,208`、测试 describe 名（`lattice.test.ts:131`）仍是旧式（差 30° 旋转）。请核对 docs 与 PROJECT_MEMORY 中还有多少处残留并登记为文档债。 |
| D2 | 测试文件数与记忆记载不符 | FE-08 / FE-20 相关，独立项 | **已由 researcher 实测闭环（并纠正了我 v1 的误报）**：`gui/test/**` = **75 个 `*.test.ts(x)` + 1 个 `.snap` = 76 文件**（根 47 / `volume/` 23 / `ptrac/` 4 / `source/` 1）；PROJECT_MEMORY 的「546/0（69 文件）」等是各批当时快照（登记为 M-20）。**此项已结案，无需再核。** |
| D3 | docs 把已死模块描述为「生产消费方」 | FE-03、Q7 | `gui/src/components/Preview3DLattice.tsx` 在 `gui/src` 内零 import（`Preview3D.tsx:15` 已内联装配），但 `docs/contracts/core3d-instancing.md:130,188`、`docs/qa-report.md:89`、`docs/frontend-changes.md:18` 仍按生产接线描述。请判定是「计划未落地」还是「落地后被内联取代」，并据此标注/清理，否则后续 agent 会照文档去找不存在的调用链。 |

### 5.4 → PM / 用户（1 项产品裁决）

| # | 事项 | 关联债 | 请求内容 |
|---|---|---|---|
| P1 | `infinite`（外无限 / graveyard 类栅元）的展示语义 | FE-21b | 两处代码语义**相反**：深模块 `gui/src/utils/cellClosure.ts:43` 为 `allowed: true`（视为正常，琥珀色 `#f9a825`），而旧对话框 `gui/src/components/CellEditDialog.tsx:53` 渲染为**红色错误态** `#e53935`。我无法从代码判定产品意图。请裁决「外无限应显示为正常还是需注意」，裁决后统一三处映射（含 `STATUS_META` 与 `_META` 的合并）。 |

---

## 六、附：FE-21 系列 + FE-22（PM 注入证据复核 + 跨组回执衍生）

PM 注入「外部会话新增 4 个前端模块但无测试」的证据，经**内容 grep 复核成立**，并由此扩出 4 条债（完整证据与 18 个建议用例名见 t3 output）：

- **FE-21（P1）测试缺口**：`gui/src/utils/cellClosure.ts`（62 行）、`gui/src/utils/useCellClosure.ts`（83 行）、`gui/src/utils/appScale.tsx`（79 行）、`gui/src/utils/useDeckSynced.ts`（70 行）在 `gui/test/**` **零命中**。四者均为纯函数/深模块，**应当且容易测**（`renderHook` + mock fetch / jsdom 即可，项目已有 `useQuickAddOverlap.test.tsx` 先例）。同批 `sourceAdv.ts` 有 `gui/test/sourceAdv.test.ts` 作对照。
- **FE-21a（P2）死导出**：`gui/src/utils/cellClosure.ts:57-62` 的 `getClosureStatus`（定义在 `:57`，函数体 `:61`）全仓仅命中定义处（1 处），同一函数体被 `useCellClosure.ts:79` 内联重写。
- **FE-21b（P1）双实现已分歧**：`CellEditDialog.tsx:50-58` 存在**第三份**状态→展示映射，与 `cellClosure.ts:41-48` 实测矛盾（颜色 + `allowed` 语义），且 `CellEditDialog.tsx:80-94` 仍自建 `/api/check-cell-closure` 请求、未走新 hook → 「抽取深模块」未收敛旧实现。产品裁决见 5.4 P1。
- **FE-21c（P1）逻辑缺陷（被无测试掩盖）**：`useCellClosure.ts:39` 的指纹 = `${surfaces.length}:${JSON.stringify(cells).length}:${tr_cards.length}`，**内容改变但长度不变**（如材料号 `1`→`2`）即指纹相同 → `:56` 早退**不重发请求**、`report` 非空即一直返回旧结果；另 `:76` 的 `useCallback` deps 为 `[report]` 却读 `fpRef.current`，配合 `GeometryTab.tsx:227` 的 `setTimeout(refreshClosure, 100)` 构成陈旧闭包。→ 封闭性自检可能静默展示陈旧结论。
- **FE-22（P3，v3 新增）跨语言口径漂移（TRCL + hex pitch）**：A) **TRCL**：前端 `latticeInstances.ts:248-259` 按「token 取角 + mod 60/90/360」解析原始串；后端**权威入口是 `gui/backend/api_server.py:622-644` 的 `_cell_trcl_deg`**（由 TR 卡旋转矩阵首行反解 `math.degrees(math.atan2(b, a))`，**`atan2@:642`**，调用点 **`:3280`**），**不做任何 mod**；`app/lattice.py:1249/1266/1044/1282` 只是**消费**已算好的 `trcl_deg`（`"trcl": float(trcl or 0)` → `expand_positions(..., trcl_rotation_deg=...)` → `math.radians(...)` → 原样回发 `trclRotationDeg`）→ 两侧机制不同（两条分歧：4-token 时取错角；符号域不同）；**fallback 当前不可达**（后端总会下发 `trclRotationDeg`，`Preview3DLattice.tsx:272`），故为**潜在债非现行 bug**。★**v3 关键收敛（researcher 反哺＋我 grep 复核确认）**：全仓 `parseTrclDeg` 的**唯一生产调用点就是 `Preview3DLattice.tsx:272`**（其余命中全在 `latticeInstances.test.ts` 的测试内）→ 而该文件正是 **FE-03 的待删死模块**，**故删除 FE-03 即同时消除本债的 TRCL 部分（隐患不可达）**；仅「`parseTrclDeg` 的『三数 = 绕 X/Y/Z 三欧拉角』参数化在后端并不存在」这半结论独立成立。B) **hex pitch↔跨度**换算**8 处 / 至少 3 种口径**（Python 5 + 前端 3，明细见 §8.6）。**处置**：TRCL 部分建议**随 FE-03 一并删除**（比二选一更省）；pitch 副本与 FE-01 的 `expected_python`、BE-21 同批收敛。Owner：engineer-frontend（FE-03 连带）+ engineer-backend（与后端 t2 的「相邻发现（P3）」同一条，两端同号）。

**间接覆盖核证**（宁标「有间接覆盖」不夸大缺口）：`useDeckSynced` 与 `useAppScale` **有间接覆盖**（`geometryBatchEditReorder.dom.test.tsx:38,77`、`geometryGroupDrag.dom.test.tsx:46`、`groupHeaderEdit.dom.test.tsx:44` 均 `render(GeometryTab)`，而 `GeometryTab.tsx:45,48,70,73` 调用二者）；`useCellClosure` **仅「不抛错」级**（上述测试的 fetch mock 对 `/api/check-cell-closure` 走 `{status:"error"}` 分支 → `report` 恒 `null` → `GeometryTab.tsx:302` 提前 return「—」，故 refresh 请求/缓存路径与 `closureMeta()` 全未执行）；`getAppPortalRoot` 可能未覆盖（未证实有用例打开相关弹窗，保守不减债）。

**总债数由此达 24 条（P1 12 条 / P2 9 条 / P3 4 条，P0 0 条）。**

**v2/v3 追加（两轮后端回执核实后）**：新增 **FE-22（P3）TRCL/pitch 跨语言口径漂移**（见 §8.6）→ **总债数 25 条（P1 12 / P2 9 / P3 5，P0 0）**。§2 主表按 PM 指令保持 FE-01…FE-20 不动，FE-22 以本节 + §8.6 承载。

---

## 七、审计元信息

- **审计人**：`engineer-frontend`（团队 `tech-debt-audit`，任务 t3）
- **日期**：2026-09-10（**v2 修订同日**：并入 engineer-backend 回执与交叉核实，见第八节）
- **审计性质**：**只读审计（未跑 vitest / tsc / vite build），未修改任何代码**。本文件为审计期间唯一的写盘产物（位于 `docs/audit/`）。
- **配套交付**：t3 任务 output（含 FE-21 系列完整证据与建议测试清单）；本文件为其不受平台 2000 字符限制影响的完整落盘版。
- **修订记录**：**v1** 初版（FE-01…FE-20 主表 + 清偿/存疑/交办）；**v2** 追加第八节（B1–B4 回执核实、FE-17 影响面收窄、B3 措辞精确化、BE-06/BE-12 前端侧「已被吸收」判定、新增 Q6b）；**v3** 并入第二轮回执：**Q5 闭环为「不排除」并升级为 FE-22**、**FE-17 二次下调**（前端两处 `1.26` 兜底经核实为不可达防御代码）、B3 行号勘误（`api_server.py` 端点注册 `:1464` / handler `:1830`，v1 误引 `:1450`）、hex pitch 副本数经我复核由「5 处」修正为「**8 处 / 至少 3 种口径**」；**v4** 并入 researcher（t1）回执：**撤回 v1 的测试文件数自报并采用 researcher 权威数字 76**（我原报 81 且分项自相矛盾）、**FE-07 旧公式残留由 4 处更正为 16 处**（采信并复核一致）、**FE-22 的 TRCL 部分收敛为「随 FE-03 删除即消除」**、FE-06 与 researcher 的 M-23 结案对齐、FE-07 与 M-21/BE-14 同根因去重提示；**v5**（本版）并入第三轮后端回执：**Q5 结案级措辞定稿（不排除）并更正 `_cell_trcl_deg` 归属**（`api_server.py:622-644`，v3 误写 `app/lattice.py`）、**FE-17 措辞按「后端无条件下发 `subPitch`（无格阵=1.26）；前端两处兜底不可达」订正**（删除我「后端不产出」的误述）、**BE-12 宽/窄方向更正**（宽的是 `/api/parse-inp`，窄的是 `_deck_to_frontend_dict`）、**BE-05 收窄为仅 `diff_inp.py`**（我复核 `mcnp_sidecar.spec:17-31` 确认）、**BE-06 我进一步核 MCP 侧并给出反证**（`_sections_to_deck`→`deck_from_json:1347` 实读 `universe_comments`）。**债条总数仍为 25（P1 12 / P2 9 / P3 5 / P0 0）**，无新增条目。

---

## 八、跨组回执与交叉核实（engineer-backend → engineer-frontend）

engineer-backend 已就第五节的 B1–B4 全部回执（其完整清单落盘于 `docs/audit/t2-backend-debt.md`）。以下为**我独立复核后的结论**，含两处**对我原判断的修正**。

### 8.1 B3（封闭性 6 状态）：证据被加强，并修正我的措辞

- **后端回执 + 我独立复核一致**：`docs/contracts/api.yaml:1452` 的 **summary 散文里已列举** 6 个状态（`（closed/infinite/semi_infinite/empty/voxel/unresolvable）`），但**响应 schema 没有枚举** —— 我读 `api.yaml:1484` 确认是 `status: { type: string }`。
- ⇒ **我原措辞「未把 6 状态枚举进契约」应更精确为「枚举只存在于散文里、不在 schema 里」**。后果一致但更严重：漂移闸门 `tests/integration/test_api_contract.py` 做的是 handlers ↔ api.yaml 的 **AST 双向存在性**校验，**结构上校验不到 enum**，故 enum 加不加、对不对，闸门都不会红。
- **后端建议（我认同，方案 1 优先）**：把 `api.yaml:1484` 改为 `status: { type: string, enum: [closed, infinite, semi_infinite, empty, voxel, unresolvable] }`（加性收紧、不动 handlers 签名），**并必须在闸门里补一条 HTTP 用例断言「响应中出现的 status ∈ enum」**，否则 enum 只是文档装饰。
- **golden 方案（方案 2）我认同后端意见**：先做方案 1；若做 golden 则**由 Python 侧写盘、TS 只读断言**（正是 FE-01 的同一个坑，不能既写又断言）。

### 8.2 B1（FE-01）：后端确认我的判断成立，且揭示前端**未知**的第三处弱点

后端逐行核实：`latticeGolden.json` 的 positions 段确实是**前端单向产出**——
- `tests/unit/test_lattice.py:380-385` docstring 自述「golden JSON 由前端创建」，缺失即 `pytest.skip`；
- `tests/unit/test_lattice.py:668-689` 是**单侧断言**（Python 产出 vs golden 的 `expected`），**Python 侧从不写盘、也不自断言**；
- **新弱点（我原先未发现，记录备查）**：`tests/unit/test_lattice.py:651-665` 的 `_golden_positions_hex_fresh()` 在 hex 条目「未重算」时直接 `continue` **skip 绕开断言** → hex 段最坏情况是**静默不校验**。
- ⇒ FE-01 从 P1 的「名不符实」升级为**双侧确认的结构性缺陷**：Python 侧是**被测方**而非**锚定方**，两侧同时漂移即静默通过。
- **修法（后端提议，我认同）**：在 `positions[]` 每条里给 `expected` 加**兄弟字段** `expected_python`（不覆盖 `expected`）；Python 侧自断言 `expand_positions(...) == expected_python`（这才是后端自己的不动点锁，可抓 BE-21 那类 pitch 公式被改）；TS 侧同时断言两个字段（跨语言锁仍在）；写盘仍由现有前端 golden 生成器做，或由 `test_lattice.py` 的 `--update-golden` 式辅助从 Python 原始输出生成。
- **后端可行性**：`expand_positions` 是纯函数（`app/lattice.py:1012`，纯 stdlib + `FillGrid.from_json`），可零额外依赖输出原始 positions → **工作量可接受**；按纪律应是**测试/生成器**行为，不是运行时写盘。**待 PM 派工**（Owner: backend，建议与 BE-21 的 hex pitch 收敛同批做）。

### 8.3 B2（FE-17）：**我的定级需要下调两次** —— 1.26 是「不可达的防御代码」

- 后端**先**给出一版判断（「1.26 只在取不到 pitch 时生效，属不可达防御分支」），**随后自己修正**：该判断取决于「无格阵时 `fidelity.subPitch` 是否缺席」，需分情况。终版结论（我**逐行复核确认**，`api_server.py:3418-3431`）：
  - `:3418` `_subpitch = None` → `:3419-3423` 遍历 `composed["lattices"]` 取各格阵 pitch 的 **min** → `:3424-3425` `if _subpitch is None: _subpitch = 1.26` → **`:3426-3431` `_fid = {... "subPitch": _subpitch}` 无条件写入**。
  - ⇒ **`fidelity.subPitch` 永远在场**（deck 无任何格阵时就是 `1.26`）。
- ⇒ **FE-17 的影响判断再次收窄（比我上版更彻底）**：「非 BEAVRS deck 下 disc 半径静默取错值」**不成立**；且**前端 `Preview3D.tsx:745` 与 `Preview3DLattice.tsx:277` 的两处 `1.26` 兜底「取不到」，是纯防御代码而非活路径**。**v5 措辞更正（后端指出我 v2/v3 表述不准）**：正确说法是「**后端 `_fid` 无条件下发 `subPitch`（`api_server.py:3426-3431`），无格阵时下发的是 `1.26` 而非缺席；前端两处兜底因此不可达**」——**不是**「后端不产出」。我 v2 写的「`lattices` 为空时也不会进 disc 详细模式」属**超出代码的推断，已删除**（该推断原为后端上轮所给、其亦已自我修正）。
- **已修好的部分（后端确认 + 我复核）**：单格阵（U233 hex，pitch=1.45034）走 min 分支取**自身** pitch → 不再被 1.26 拖累；可**直接断言**「`fidelity.subPitch` == 该格阵自身 pitch」。
- **处置建议（后端提出，需 PM/契约决策；我认同其 ① 并补充前端视角）**：
  - **① 推荐**：后端在无格阵时改下发 **`null`**，前端集中做**一处**兜底 → 语义正确，且**前端兜底变成活路径、可测**（可被 FE-21 的测试清单覆盖）。
  - ② 三者全保留但把前端两处显式标注「防御，不可达」。
  - **前端视角补充**：无论选哪个，`Preview3DLattice.tsx:277` 那处都会随 **FE-03 删除死模块**自动消失；剩余 `Preview3D.tsx:745` 一处应与后端契约对齐（`?? 0` 或显式报错），不要再保留默默兜 `1.26`。
- **同一处的真债（后端发现，归 BE-21）**：`app/lattice.py:915-929`（`_lattice_pitch`，用 `str(lat)=="2"`）与 `:1037-1041`（局部 `fg.lat`）把「lat=2 格距取 x 跨度」**各写一遍且判定不同源**——与 FE-22（见 §8.6）合起来构成同一族「hex pitch 多副本」债。

### 8.4 BE-06 / BE-12 对前端的实际影响：**我独立复核后判定「已被前端吸收」**

后端提示两条后端债可能表现为前端 bug。我在**前端侧**逐条核实，结论如下（避免误报）：

| 后端债 | 后端描述 | 我的前端侧核实结论 |
|---|---|---|
| **BE-06**（MCP `patch_section` 不带 inp 时整份重写工作区，`_sections_to_deck` 不读 `universe_comments` → 丢 `deck.universeComments`） | 预期表现为「AI 改任意一段 → U 分组头注释消失 → generate 产出丢注释的 INP」 | **主应用不成立（已被前端 merge 吸收）**。证据链：① AI 回显走 `useAiWorkspace.ts:44` → `applyRef.current(ws.deck)`；② `App.tsx:92` 是 **`loadDeck({ ...deck, ...aiDeck })`** —— 浅展开中 **`aiDeck` 缺 `universeComments` 键时，本地的 `deck.universeComments` 被保留**；③ `App.tsx:325` 生成时送的是 `deck.universeComments`，故 INP 不丢注释。**v5 追加（我进一步核了 MCP 一侧，后端原表述的前提也不成立）**：`inputcard_mcp/server.py` 的这条链**本身保住了 `universe_comments`** —— `_deck_to_sections`（`:71-84`）显式 `sec["universe_comments"] = d.get("universe_comments", {})`（并注明「generate 时不会被丢」），`deck_from_json`（`api_server.py:1337-1349`）按其**末位参数** `universe_comments=(data.get("universe_comments") or data.get("universeComments") or {})` 读回；`patch_section`（`:219-222`）的 `_ws_deck() → _apply_section_patch → _set_ws_sections(_deck_to_sections(deck)) → _generate(deck)` 全程经该函数。**故「AI 不经前端自行 generate 也丢注释」这一残留我看不到代码支撑**；后端已在 t2 §4.7 把 BE-06 的定级依据收窄为「后端侧、AI 拿到的文档是错的」，**该定级依据请以后端复核为准**（我已把我的反证直发后端）。 |
| **BE-12**（两份已分叉的 deck→前端序列化：`api_server.py:2033-2094` 与 `:1352-1391`） | 预期表现为「AI 改完后某个源/计数面板显示不对」 | **后端「少 11 行字段」的差异我逐行复核确认属实**（`:2061-2078` 独有 `sourceMode`/`sdefFields`/`kcodeFields`/`ksrcPoints`/`sdefRawText`/`distributions`/`sswFields`/`ssrFields`；`:2091` 独有 `_warnings`）。但**主应用不成立**，原因是互补的两点：① 前端**已删除**这些顶层中间态副本（`sourceAdv.ts:8-9` 明写「不再存在」），权威是 `deck.adv`，故顶层缺这些键无影响；② 它们**被注入时**更危险——`App.tsx:92` 让它们进入 deck，但 `loadDeck` → `migrateLegacySourceKeys`（`sourceAdv.ts:147-174`，仅在 `adv` 缺值时取中间态并**随后删除顶层键**）会兜住，不会反向覆盖 AI 写入的 `adv`。 |
| **BE-12 的真实残留（我新发现，后端已核实并采纳）** | —— | `_deck_to_frontend_dict` 是**公开别名**（`api_server.py:1395`）且被 `/api/text-to-section` 复用（`:2147`），而其 docstring `:1353` 自称「与 `/api/parse-inp` 的序列化一致」——**该声明已不成立**。**v5 方向更正（我 v2/v3 写反了，后端勘误 + 我逐行复核确认）**：**宽的是 `/api/parse-inp`，窄的是 `_deck_to_frontend_dict`** —— `_handle_parse_inp`（`:2033-2094`）在 `:2061-2078` **注入**前端中间态键、`:2091` **带** `_warnings`；而 `_deck_to_frontend_dict`（`:1352-1391`）**两者都没有**（故 MCP `/workspace` 走的那份是窄的）。暴露面（此半段后端采信我的切分）：`/api/text-to-section` 只返回 `materials`/`cells`/`tallies` 三个子集（`:2148-2153`）→ **应用内影响≈0**；危害集中在 **① docstring 自称一致会让后人把两份实现当同一契约改（BE-12 分叉继续扩大）② `_warnings` 两条出口语义不一致**。后端已单列 **BE-26（P2）** 承载，处置 = 修 docstring + 与 BE-12 合并为单一实现（带 `include_frontend_aliases`/`include_warnings` 参数）。 |

**结论**：BE-06 / BE-12 均**不构成前端用户可见 bug**，故**不新增前端债条目**；两者仍应按后端债（BE-06/BE-12）处置，只是不要把它们归因到前端。**BE-12 的「docstring 声明与实现不符 + 双序列化共存」我建议单列一条跨端契约债**（Owner 建议 backend，证据已在此表给出）。

### 8.5 BE-05（P0，打包版端点 500）对前端联调的提示

后端原提示：`app/analytic_slice.py`、`app/diff_inp.py` 未进 `mcnp_sidecar.spec` 的 `_keep_py/_keep_dirs` → **打包版** `/api/cross-section`（解析切片分支）与 `/api/diff-inp` 必 500，dev 模式永不复现。**前端侧对应消费点**：`CrossSectionView.tsx` / `CrossSectionWindow.tsx`（截面）与 `DiffDialog.tsx`（差异）——若在**打包版**联调遇到这两个功能 500，**先查 sidecar spec，不要查前端**。此项属后端 P0，我不重复登记，仅登记前端消费点以便定位。

**v5 更正（后端自我更正 + 我复核确认）**：**后端的 BE-05 已收紧为「实存漏项只有 `app/diff_inp.py` 一个」** —— 我读 `gui/mcnp_sidecar.spec:17-31` 确认：`:19` 的 `_keep_py` 列表**已含** `analytic_slice.py`、`:28` **已含** `stl_cross_section.py`，而 **`diff_inp.py` 确实不在其中**。⇒ 前端联调提示相应收窄：**只有 `/api/diff-inp`（`DiffDialog.tsx`）是打包版必 500 的确认项**；`/api/cross-section` 属**已排除**（其动态 import 逐项对照表见后端 t2 §4.4）。**若他处引用过我上文旧版说法，一律以 t2 §4.4 为准。**

### 8.6 Q5 闭环：**不排除（我的推测方向错了，后端结论相反）** → 新增 FE-22

我在 Q5 里怀疑的是「Python 侧 TRCL 归一化写法与前端不同」，并**推测方向是「同类不 bug」**。后端逐字核对两侧后给出的结论**与我预期相反，且我复核确认**：

- **机制根本不同（不是同一实现的两种写法）**：前端 `latticeInstances.ts:248-259` 把 TRCL 串当「三个角 token」，`toks.length >= 3 ? toks[2] : 末位`（`:256`）+ `((z % step) + step) % step`，`step` = lat2→60 / lat1→90 / 无 lat→360（`:257-258`）。**后端唯一入口是 `gui/backend/api_server.py:622-644` 的 `_cell_trcl_deg`**（调用点 `:3280`）：由 **TR 卡旋转矩阵首行** `(rot[0][0], rot[0][1])` 反解 `math.degrees(math.atan2(b, a))`（**`:642`**），**无任何 mod**（值域 (−180°, 180°]，可为负）。（※ v3 我误把它写在 `app/lattice.py`，v5 按后端勘误更正为 `api_server.py`；`app/lattice.py:1249/1266/1044/1282` 只是**消费**已算好的 `trcl_deg` 并原样回发。）
- **两条真实分歧**：① TRCL 若写成 MCNP「3 角 + 3 平移」形式（4 个 token），前端取 `toks[2]` **可能不是 Z 角**；② 后端角可为负、前端恒非负。
- **门槛高（故非现行 bug）**：`api_server.py` **总会**下发 `trclRotationDeg`，故 `Preview3DLattice.tsx:272` 的 `primary ? (primary.trclRotationDeg ?? 0) : parseTrclDeg(latCell.trcl, latCell.lat)` **fallback 此刻不可达**。
- ⇒ **定级：潜在债（P3）**（与后端 t2 的「相邻发现 P3」同一条，两端同号）。**处置二选一**：① 让前端 fallback 与后端口径统一（更稳，但需先钉契约）；② 删 fallback 改 `?? 0`，并在契约里钉死「`trclRotationDeg` 必下发」。

**追加发现（我就后端线索独立复核并**扩大了计数**，构成独立前端债 FE-22）**：「lat=2 格距 ↔ 跨度」的换算在仓库里**共 8 处、至少 3 种口径**（后端原话说「五份」，我复核为 8 处且口径不止一种，此处以我的实测为准）——
- **Python 5 处**：① `app/lattice.py:915-929` `_lattice_pitch`（判据 `str(lat)=="2"`，规则「格距 = x 跨度」）；② `app/lattice.py:1037-1041`（判据局部 `fg.lat`，规则同上，**与 ① 判定来源不同源**）；③ `gui/backend/api_server.py:734-740`（**反向**：给定 `pitch` 求跨度 → `x 跨度 = 2p/√3`、`y 跨度 = p`）；④/⑤ 仅作 lat 分派、不含换算（`app/lattice.py:563-566` 的 `_validate_lat1/lat2`、`:891-894` 的 `_plane_box_extent/_hex_plane_extent`）——列出以免误计为同族。
- **前端 3 处**：⑥ `gui/src/utils/lattice.ts:453`（`estimateLatticeExtent` hex 分支，**写死 `pitch = 1`**）；⑦ `gui/src/three/latticeInstances.ts:384-389`（`expandPositionsRef` 内的 Python 镜像，规则「hex 用 x 跨度」）；⑧ `gui/test/latticeInstances.test.ts:416-453` 所在跨语言用例（消费 ⑦ 的产出）。
- **风险（后端原话，我认同）**：改公式时各处必须同批更新，否则**即使 FE-01 加了 `expected_python` 也会被 pitch 副本坑**。
- **口径归属（工程）**：本节「8 处」这个**处数**在工程上宜按 engineer-backend 的 BE-21 附表口径理解 —— 其中真正**实现换算**的为 5 处（`app/lattice.py:915-929`、`app/lattice.py:1037-1041`、`gui/backend/api_server.py:734-743`、`gui/src/utils/lattice.ts:452-468`、`gui/src/three/latticeInstances.ts:384-389`），另加 1 处 TS 测试消费点（`gui/test/latticeInstances.test.ts:416-453`）与 1 处同 `expand_positions` 契约链入口（`app/lattice.py:1249→1266→1044`，非换算）；**§8.6 上列 ④/⑤ 两处经逐行复核为误报**（`api_server.py:554-564` 实为 `_clip_suffix_and_lines` 拼接 `rpp` 文本行、`:884-895` 实为 `_lattice_container_bound` 曲面号扫描循环，**均非 lat 分派、更非换算**）。**计数与定级以 BE-21 附表为准**，本节不再维护该数字（本条本次仅作口径归属说明，不改任何债条内容与定级）。
- **处置**：FE-01 的 `expected_python` 与 BE-21 的 Python ①② 收敛**同批做**；前端侧 FE-06 删掉 `estimateLatticeExtent` 后自动减一处（⑥）。

### 8.7 researcher（t1）回执核实：**我撤回一处自报数字、采信两处扩大**

| 事项 | researcher 主张 | 我的独立复核结论 |
|---|---|---|
| **测试文件数** | 76 个 = 75 `*.test.ts(x)` + 1 `.snap`（根 47 / `volume/` 23 / `ptrac/` 4 / `source/` 1） | **我 v1 的「81 个」撤回**：我的分项「根 61 + `volume/` 19 + `ptrac/` 4」= 84，**与自称的 81 自相矛盾，属我的计数错误**（无误报他人，但确实误导了 PM）。我本轮新跑 glob 只能给出**量级**「≥60 个 `.test.ts` + 15 个 `.test.tsx` + 1 `.snap`」，**无 shell 无法给出逐目录权威分项**，故**一律引用 researcher 的数字**。→ §4 括注已改。 |
| **FE-07 旧公式残留处数** | **16 处**（我 v1 只列 4 处） | **采信**。我用 `i·p·√3|p·√3/2|列水平步距` 等 5 个模式全仓 grep，**独立得到 16 处与其完全一致**（含 `contracts/lattice-fix15-design.md:171-172` 与 **L1 锁死表 `:450`**、`PROJECT_MEMORY.md:166/172/178/179/208`）。其点名「L1 锁死表写的也是错公式」是最有价值的一条——**契约表会污染跨语言实现**，我已写进 FE-07 影响栏。→ §2 的 FE-07 行已扩充为全 16 处。 |
| **Q7 判定** | 属「**曾接线、后被内联取代**」而非「从未落地」 | **采信**。证据链与我一致（`gui/` 零 import + `Preview3D.tsx:15/721/783` 内联 + `PROJECT_MEMORY.md:178` 记 08-24 项15 曾接线）。其补充的待清理文档清单（`lattice-fix15-design.md:30/405/410/412/456/547`、`PROJECT_MEMORY.md` 8 处）我未逐行验证，**按文档债移交其 M-22 处理**，与我的 FE-03（死码侧）互补不重复。 |
| **FE-06 结案** | 采纳（真实格元盒已由 `/api/lattice-extent` 提供） | **一致**，与 M-23 对齐，无异议。 |
| **★ 反哺：FE-22 的 TRCL 唯一触发点** | `Preview3DLattice.tsx:272` 是唯一调用点 → FE-03 删掉即隐患消失 | **复核确认，且比其说的更确定**：我 grep `parseTrclDeg` 全 `gui/` 得 **21 处命中，其中 20 处在该函数的测试文件 `latticeInstances.test.ts`，生产调用点只有 `Preview3DLattice.tsx:272`**。⇒ FE-22 的 TRCL 部分**随 FE-03 删除即消除**（比「二选一处置」更省），已写进 FE-22。 |
| **同根因去重提示** | FE-07 / M-21 / BE-14 同根因 | **接受**，已在 FE-07 处置栏写明「三者同根因，请 T4 合并为一条、勿重复计」。 |

**结论**：researcher 的复核**纠正我一处（文件数）、放大我一处（16 处）、反哺我一处（FE-22 可达性）**；我侧无与其冲突的反证。债条数不变（25）。

---

## 九、方法学附注与文档结构说明
> 本文件按 PM 指令于 2026-09-10 创建，并**同日追加第八/九节**（跨组回执核实；现为 v5）。为免误读，明确各节定位：
>
> | 节 | 内容 | 是否受「追加交付」影响 |
> |---|---|---|
> | 一 | 方法（静态核对 + 无 shell 声明） | 否 |
> | **二** | **完整债表 FE-01…FE-20（PM 指定格式，8 列）** | **否（主表条目未增删；FE-07 的证据在 v4 扩充为 16 处，见 §8.7）** |
> | 三 | 已核实已清偿 10 项（勿再报） | 否 |
> | 四 | 存疑 9 项（原 8；Q5 与 Q6 均已闭环，新增 Q6b） | 是（v2–v5） |
> | 五 | 跨组交办项（已直发，抄送 PM） | 否 |
> | 六 | FE-21 系列 + **FE-22**（跨端口径漂移） | 是（v3–v5） |
> | 七 | 审计元信息 | 是（v2–v5 加修订记录） |
> | 八 | 跨组回执与交叉核实（§8.1–§8.6 后端三轮；**§8.7 researcher**） | **是** |
> | 九 | 本说明 | **是** |
>
> **§2 主表刻意保持 v1 原样**，以保证 PM 5 秒内可读且与团队 output 一一对应；v2–v5 的**定级与证据修正**统一收敛在 §8 正文（§8.1 B3、§8.3 FE-17、§8.4 BE-06/BE-12、§8.5 BE-05、§8.6 Q5→FE-22、§8.7 FE-07 与文件数），并在 §4 与相关行括注里指明，**不回改主表结构**（避免两份口径并存）。PM 如需 v6 合并版主表，请明示。

