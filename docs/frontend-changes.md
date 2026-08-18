# 前端改动清单 — 3D 预览性能修复（perf/preview3d）

> 施工方：前端 | 契约：`docs/contracts/preview3d-performance.md` | 分支：`perf/preview3d`
> 范围：仅 `gui/src/`、`gui/package*.json`、`gui/test/`、`docs/frontend-changes.md`（与后端 `app/`、`gui/backend/api_server.py` 零重叠）

## 步 3 — IPv6 惩罚修复（§6.1，前端部分）

**新增**：
- `gui/src/utils/api.ts`：`API_BASE = "http://127.0.0.1:5001"` + `apiUrl(p)`。单一后端地址常量，前端全部 fetch 直连 IPv4，规避 Chrome `localhost` 的 IPv6 回退惩罚（~300-500ms/请求）。

**修改（14 个文件，`"http://localhost:5001/api/..."` 硬编码 → `apiUrl("/api/...")`）**：
- `gui/src/App.tsx`（6 处：mcnp-detect / xsdir-check / validate-inp / parse-inp / choose-file / choose-dir）
- `gui/src/utils/backend.ts`（2 处：xsdir-check / generate）
- `gui/src/utils/dataCollector.ts`（1 处：generate）
- `gui/src/utils/sectionConvert.ts`（2 处：section-to-text / text-to-section）
- `gui/src/utils/useFreecadStatus.ts`（`const API = apiUrl("/api")`）
- `gui/src/utils/windows.ts`（1 处：clear-stl）
- `gui/src/components/AdvancedTab.tsx`（2 处：xsdir-check）
- `gui/src/components/CrossSectionWindow.tsx`（1 处：cross-section）
- `gui/src/components/GeometryTab.tsx`（3 处：import-step / export-step / serve-file）
- `gui/src/components/MaterialEditDialog.tsx`（4 处：expand-formula / validate-zaid ×3）
- `gui/src/components/OutputTab.tsx`（1 处：parse-outp）
- `gui/src/components/PreviewDialog.tsx`（2 处：save-inp / run-mcnp）
- `gui/src/components/Preview3D.tsx`（2 处：cross-section / preview-3d）

**验收**：`grep gui/src localhost:5001` 归零（已验证）。

## 步 4 — 抽 4 个深模块 + Preview3D.tsx 接线（§4.2 / §5.2）

**新增 `gui/src/three/`**：
- `TickGrid.ts`（§4.2.1）：`planTickStep` 纯函数（STEPS 表扩到 1e6：1000/2000/5000/1e4/2e4/5e4/1e5/2e5/5e5/1e6，`dist/5` 档位 → 每轴 ≤10 刻度）；`createTickGrid(group, createTexture?)` — 台账 createdGeoms/createdTexs/disposedGeoms/disposedTexs，rebuild 先完整 dispose 旧的（line.geometry/material + sprite.material + sprite.material.map）再建；`createTexture` 依赖注入（测试注入假纹理记账 dispose）。
- `renderGate.ts`（§4.2.2）：`createRenderLoop({requestFrame?, cancelFrame?, onRender})` — dirty 按需渲染，idle 0 渲染；`requestFrame/cancelFrame` 注入（测试假 rAF）。
- `cellMaterial.ts`（§4.2.3）：`buildCellMaterial({color, transparentMode?})` — 默认 opaque `{transparent:false, depthWrite:true, opacity:1}`；see-through `{opacity:0.6, depthWrite:false}`；M0 真空色维持 opacity 0。
- `cameraParams.ts`（§5.2.1）：`computeCameraParams(bboxCenter, bboxSize)` 纯函数 — `near=realExt*0.02 / far=realExt*100`（farNear=5000 恒 ≤1e4）、`position=center+viewDist*(0.6,0.6,0.5)`、`target=center`、`min/maxDistance=realExt*0.1/50`。

**修改 `gui/src/components/Preview3D.tsx`**：
- 替换 `rebuildTicks`（:196-243）→ `tickGrid.rebuild({dist, axes})`。
- 替换 `animate` 无条件渲染循环（:354-383）→ `createRenderLoop`；接线 controls change / WASD / loadStlMeshes / setVisible / setColor / selectAll / resizeRenderer 全部 `markDirty()`；按键按住时 onRender 续 dirty 保持连续移动。
- 替换全栅元透明材质（:312）→ `buildCellMaterial`（默认 opaque）。
- 替换手写 reframe（:334-347）→ `computeCameraParams` + **几何归一化**：`loadStlMeshes` 加载后先 `geometry.translate(-center)` 再 `computeBoundingBox()`（顺序关键，renderOrder 排序用平移后 bbox），相机 target=center≈原点，轴线/刻度天然对齐。
- `setColor`/`setTransparentMode` 复用 `applyMeshMaterial` 助手（buildCellMaterial 单点）。
- 保留既有行为：WASD 移动、ResizeObserver、LOD、renderOrder 排序。
- 清理死代码 `makeNumberSprite`、`cellColors`/`cellNums`、`running`。

## 步 5 — 加载态 + 半透明开关（§3.2.3 / §4.2.3）

- `useEffect` fetch `/api/preview-3d` 期间 `loading=true` → 遮罩"正在生成 3D 几何…"；`.then/.catch/.finally` 后 `loading=false`。
- 面板新增"半透明查看"开关（`seeThrough` state，默认关 → opaque）；切换调 `ctrlRef.setTransparentMode("opaque"|"see-through")`，全栅元重应用材质（M0 真空 opacity 0 不变）。
- 开关下附非阻断提示："默认不透明渲染（性能最佳）；开启可看穿外壳"（PM 裁决的可选 UX 引导）。

## vitest 基建（§8.3）

- `gui/package.json`：新增 `"test": "vitest run"` + `vitest@^1.6.0`（devDependency，不并入 pytest 门禁）。
- 新增 `gui/test/`（4 文件，13 用例全绿）：
  - `cameraParams.test.ts`（4）：farNear≤1e4（inp01 z∈[0,10000] bbox / shield ±2000）、bboxSize∈[1e-2,1e5] 单调有界、position=center+偏移。
  - `tickGrid.test.ts`（4）：rebuild_disposes_previous（disposed==created，纹理记账归零）、object budget≤60 / textures≤30（dist=1e5）、planTickStep 不饱和（1e5→2e4）、dispose 清空 group。
  - `renderGate.test.ts`（2）：idle 5 帧 0 渲染、markDirty 后恰 1 次、dispose 停帧。
  - `cellMaterial.test.ts`（3）：默认 opaque、see-through 透明、M0 真空 opacity 0。
- 跑法：`cd gui && npx vitest run`（独立于 pytest 门禁）。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `grep gui/src localhost:5001` | 归零（0 处） |
| `cd gui && npx vitest run` | 4 文件 / 13 用例全绿 |
| `cd gui && npx tsc --noEmit` | 通过（EXIT 0） |
| `cd gui && npm run build` | 通过（vite build） |

## 不做（后端范围）

`app/preview_cache.py`、`freecad_preview.py` bound、`_freecad_csg_worker.py` vtk、`api_server.py` handler 接线、`gui/backend/` 一切文件 —— 由后端并行施工，前端零触碰。
---
# 前端改动清单 — 用户反馈 #3/#4/#5（2026-08-13，实验分支 experiment/geouned）

> 施工方：前端 | 指令：PM 批复排查结论后直接落地 | 范围：仅 `gui/src/components/` 3 个文件

## #3 F 卡输入数字光标消失

**根因**：`TallyTab.tsx` 行 `key={t.id}`（143 行）依赖由 `number` 推导的 id（原 93 行），输入数字改变 number → id 变化 → `<tr>` 重挂载 → 焦点/光标丢失。

**修改 `gui/src/components/TallyTab.tsx`**：
- 新增 `idsRef = useRef<number[]>([])`（按位置缓存上次 id）。
- deck→local pull effect：id 优先复用 `idsRef.current[i]`（number 变化不再改变 key，行不重挂载）；新行回退到 `number*10+typeCode+particleCode` 种子并用 `Set` 去重防冲突。
- 未改 push 的 `parseInt||0` 归一化（清空弹回 0 为既有次要行为，PM 指示本次不动）。

## #4 高级"其他卡"输入空间太窄

**修改 `gui/src/components/AdvancedTab.tsx`**："其他卡片" textarea（约 285 行）`minHeight: 100 → 240`，保留 `resize:"vertical"` 可拖拽。

## #5 材料 options 框改名"其他" + 放大换行

**修改 `gui/src/components/MaterialEditDialog.tsx`**（289-294 行）：
- label `"nlib= / gas= / plib="` → `"其他"`。
- 单行 `<input>` → `<textarea>`（`minHeight:60`、`fontFamily:"Consolas,monospace"`、`fontSize:12`、`resize:"vertical"`），`value`/`onChange` 保持绑定 `options` 字符串。
- `options` 为纯字符串，`\n` 经 JSON 直传后端（`app/models.py:104 options:str`）透传成立。

**后端联动点（不在本次前端范围，需后端配合）**：
- `app/generator/inp_generator.py:205-209`：options 含 `\n` 时需按行拆分，首段内联 `M{n}  ` 后、其余段作 M 卡续行（5 空格缩进），否则第 1 列输出会被 MCNP 当独立新卡。
- `app/generator/parsers/core.py:397`：`" ".join(options_parts)` 会拍平换行，多行 options 导入后换行丢失（语义保留，增强项）。
- `_wrap_long_lines`（inp_generator.py ~1010）与 options 内嵌 `\n` 的交互需验证。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 5 文件 / 19 用例全绿 |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积/动态导入警告） |
---
# 前端改动清单 — 用户反馈 #1 配套：FM 计数乘子编辑 UI（2026-08-13，实验分支 experiment/geouned）

> 施工方：前端 | 指令：PM 派发（D-05 高价值卡结构化配套）| 后端全链已修（pytest 297 绿），前端零后端改动
> 范围：仅 `gui/src/components/TallyTab.tsx`、`gui/src/utils/DeckContext.tsx`

## 改动点

**`gui/src/components/TallyTab.tsx`**：
- 本地 `Tally` 接口新增 `multiplier: string`（第 18 行）。
- local→deck push effect（第 82 行）mapped 对象新增 `multiplier: t.multiplier`。
- deck→local pull effect（第 105 行）回填 `multiplier: t.multiplier || ""`（导入/文本模式解析出的 multiplier 透传回表单）。
- `addTally`（第 122 行）新行初始化 `multiplier: ""`。
- 表格 thead 新增「乘子」列头（参数与 En 之间）。
- tbody 新增乘子输入框（第 180 行）：单行 `<input>`，`value={t.multiplier}`、`onChange=updateTally(id,"multiplier",...)`，width 150，placeholder "如 8.65E10 1 -5 -6"，空值 = 不生成 FM 卡。

**`gui/src/utils/DeckContext.tsx`**：
- `TallyDef` 新增 `multiplier?: string`（第 25 行）——与后端 `TallyDefinition.multiplier`（app/models.py:200）字段名对齐，api_server 358/480/665 读写同一 key，生成器 inp_generator.py:648/671 空值不发 FM 卡。

## 说明（与 PM 指令的一处偏差）
- PM 指令写「contract.ts 加 multiplier 字段」：实际前端 tally 类型定义在 `gui/src/utils/DeckContext.tsx` 的 `TallyDef`（contract.ts 仅含 source/SSW/KCODE 契约，无 tally 类型），已落在 DeckContext.tsx。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 5 文件 / 19 用例全绿 |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |
---
# 前端改动清单 — 网格计数（FMESH/TMESH）3D 体积可视化（2026-08-14，meshtal-volume）

> 施工方：前端 | 契约：`docs/contracts/meshtal-visualization.md` | 后端已完工（3 端点 + _err hint），前端按契约对接
> 范围：`gui/src/volume/`（11 模块）+ `gui/test/volume/`（8 测试文件）+ windows.ts / main.rs / App.tsx / TallyTab.tsx / PreviewDialog.tsx / api.ts
> 纪律：零新依赖（three 0.160 复用 Data3DTexture）；未改 Preview3D.tsx 主组件；体积窗口关闭不清 STL 会话

## A. `gui/src/volume/` 11 模块（新建文件夹）

| 模块 | 实现 | 契约锚点 |
| :--- | :--- | :--- |
| `volumeShader.ts` | WebGL2 光线步进 GLSL（vertex+fragment 字符串导出 + `isWebGL2` 降级提示 + `MAX_RAY_STEPS`）；`buildRayMarchMaterial` 用 **RawShaderMaterial**（shader 自带 `#version 300 es`，避免 three 自动前缀造成双 `#version` 编译错）；CPU 已上色 → GPU 只采样 + alpha 合成 | §4.7 |
| `VolumeRenderer.ts` | `createVolumeRenderer`（外壳 STL 复用 STLLoader/cellMaterial/renderGate/computeCameraParams + Data3DTexture 一次创建 texSubImage3D 复用 + OrbitControls + §7.2 统一归一化对齐）；`computeVolumeCamera`（A2.1 开窗自动取景=几何+体积联合包围盒）；时间轴 play/pause/seek | §4.7/§7/§12 A2.1 |
| `colorize.ts` | TS 镜像后端 colormap：`weatherLut()` sha256 **= golden `36770ae2…`**（round-half-even，t=i/(n-1)）；`colorizeScalar` 色阶下限=阈值 alpha 0、默认 range=scalarRange（A2.2）；128³ 热路径预计算系数 <50ms | §4.3/§12 A2.2 |
| `alignWorld.ts` | `worldBoxFromEdges`/`unionBoxes`/`translateToCenter`/`applyOffset`（§7.3 四断言：共享 offset 不变量/尺寸保持/相对位移保持/体积盒⊆外壳） | §7 |
| `downsampleRequest.ts` | `decideResolution`（128 默认/256 显式/native 更小保 native）+ F3 弹窗文案「要更流畅，还是要更精细？」 | §4.4/§12 A2.3/F3 |
| `fmeshState.ts` | `FmeshRow` ↔ 卡体文本（镜像 fmesh_parser.py，raw 兜底）+ `buildFmeshPayload`（→ tally.fmesh_defs 后端 key 对齐）+ 幽灵文字映射 | §4.7.1/§5.3 |
| `workflow.ts` | F1 空态三步引导 + 没找到文件可操作提示（纯逻辑） | §12 F1 |
| `ColorLegend.tsx` | 色条图例 + `legendTicks` 刻度纯函数（单位+上下限数值） | §12 F5.2 |
| `FMeshForm.tsx` | FMESH/TMESH 受控表单（幽灵文字 F5.1）+ 3D 可视化启动器（解析→分辨率决策→开窗；A1.2 不匹配横幅；F4 hint 优先；F3 弹窗） | §4.7.1/§12 |
| `VolumeControlPanel.tsx` | 透明度/能量/时间轴/外壳/色阶；**高级控件默认折叠**（F2） | §4.7/§12 F2 |
| `ResultWindow.tsx` | volume3d 窗口宿主：读桥→取帧→渲染；**关闭只 close_window 不清 STL 会话**（§14）；外壳勾选复用 CellList | §4.7/§14 |

## B. 接线

- `gui/src/utils/windows.ts`：`KEY_VOLUME3D` + `openVolume3D`/`readVolumeData`（照 openPreview3D 桥）。
- `gui/src-tauri/src/main.rs`：`open_volume3d_window` command（label `volume3d`，复用 create_or_focus）+ invoke_handler 注册。
- `gui/src/App.tsx`：`#/volume` 哈希路由 → ResultWindow；generate 载荷 `tally.fmesh_defs = buildFmeshPayload(deck.tally.fmesh)`；importInpText `tally.fmesh = fmeshDefsToRows(d.tally.fmesh_defs)`。
- `gui/src/components/TallyTab.tsx`：嵌入 FMeshForm 小节（值=deck.tally.fmesh，回填 fmesh_defs → fmesh）；文本模式 onBackToForm 同步 fmesh。
- `gui/src/utils/api.ts`：meshtalDetect/meshtalParse/meshtalTexture/fetchPreview3dStl 封装 + `errorHint`（F4 hint 优先）。
- `gui/src/components/PreviewDialog.tsx`：**A1.1** run-mcnp 完成后自动 meshtal-detect（发现文件弹提示）。

## C. 产品方向 F1-F5 落实

- **F1**：workflow.ts 三步引导 + noFileMessage「请点这里选择 meshtal 文件」→ choose-file。
- **F2**：128³ 默认、自适应色阶、自动取景、外壳开 = 开箱即用；256³/透明度/色阶/外壳开关在「高级设置」折叠内。
- **F3**：超预算弹窗「要更流畅，还是要更精细？」（流畅=128 自动降采样 / 精细=256 保原精度）。
- **F4**：`errorHint(j)` 优先显示后端 `_err` 的 hint 字段，其次 message。
- **F5**：FMESH 每输入框幽灵文字注明关键字作用；ColorLegend 色条两端显示 displayMin/displayMax + 单位标签。

## D. vitest（`gui/test/volume/` 8 文件 57 用例 + 基线 19 不破 = 76 全绿）

- `colorize.test.ts`（10）：**golden sha256 命中**、阈值 alpha0、默认 range=scalarRange、range 重映射、128³ 计时 <50ms。
- `workflow.test.ts`（5）、`ColorLegend.test.ts`（8）、`downsampleRequest.test.ts`（7，F3 文案）、`VolumeRenderer.test.ts`（5，A2.1 自动取景）、`fmeshState.test.ts`（9）、`alignWorld.test.ts`（5，§7.3 四断言）、`volumeShader.snapshot.test.ts`（8，GLSL 快照 + isWebGL2）。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 13 文件 / 76 用例全绿（基线 19 不破 + 新增 57） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积/动态导入警告） |
| golden sha256 | `36770ae2b9cd2a2ac3b6e6a08de45d522261dfced960c0c1db49bc515358c038` 命中 |

## 偏差说明（PM 指令 vs 实际）

1. **GridEditor 复用**：PM 指令写「能量/时间边界复用 GridEditor/gridState」；契约 §4.7.1 明确「卡语义不同（边界 vs 参数化网格）→ **不复用 GridEditor**，自管结构化输入，照 gridState setFromBody/getBody 范式」。已按契约执行（fmeshState 提供 cardTextToFmesh/fmeshToCardText 对，同范式）。
2. **DataTexture3D 命名**：PM 指令写「three 0.160.0 已含 DataTexture3D」；实测 three 0.160 类名为 **Data3DTexture**（DataTexture3D 为旧名，@types/runtime 均无）。已用 `THREE.Data3DTexture`。
3. **DeckContext fmesh 字段**：契约 §4.7.1「tally 对象加 fmesh」；落位 `deck.tally.fmesh`（deck.tally 为 Record，D-05 先例：tally 字段在 DeckContext 而非 contract.ts，contract.ts 仅 source/SSW/KCODE 映射）。generate 载荷映射后端 key `fmesh_defs`。
4. **ResultWindow 首帧**：桥不携带纹理，ResultWindow 挂载后调 meshtal-texture 取首帧再 createVolumeRenderer（渲染器需真实 frame.resolution 建 Data3DTexture dims）。
---
# 前端改动清单 — UI 调整两处（2026-08-14，experiment/geouned）

> 施工方：前端 | 指令：PM 直接派发（两处 UI 调整）| 范围：仅 `gui/src/` 4 个文件
> 纪律：不碰后端/测试基线；vitest 76 / tsc / build 全绿

## 任务 1 — 删除 F1-F8 可展开提示

- **`gui/src/components/TallyTab.tsx`**：删除 `:222-230` 的 `<details>` 折叠"FN 计数卡结构参考"表格（F1 曲面电流 / F2 曲面通量 … F8 脉冲高度）。该块为纯内联内容，无外部常量引用，整块移除无残留。

## 任务 2 — 3D 结果入口移到「输出」标签页

### 新增共享模块 `gui/src/volume/openVolume3DWindow.ts`

- 导出 `openVolume3DWindow(params)`（签名 `{ path, tally, resolution, model?, parseResult? }` → `OpenVolume3DWindowOutcome`），封装原 `FMeshForm.openWindow` 开窗逻辑（openVolume3D 数据桥 + 非 Tauri fallback），**行为逐字节一致**：
  - 成功 → `{ ok: true }`；非 Tauri → `{ ok: false, kind: "fallback", message: "已写入 3D 结果数据（浏览器模式无法自动开窗，可访问 #/volume 查看）" }`；异常 → `{ ok: false, kind: "error", message: errorHint(e, "打开 3D 结果窗口失败") }`。
  - 原 `buildBinOptions`/`fmtBound` 迁入本模块；`readOutputDir` 一并迁入（读 `mcnp_workspace_v1` 的 `outputPath`）。

### FMeshForm 退化为纯表单（`gui/src/volume/FMeshForm.tsx`）

- **移除**：3D 可视化启动器整段（`runParse`/`chooseMeshtalFile`/`openWindow`/F3 预算弹窗/工作流提示横幅）+ 启动按钮（原 `:189` runParse 自动开窗、`:309`「打开 3D 结果」、`:376/:390` F3「流畅/精细」）。`FMeshFormProps` 去掉 `cells/surfaces/trCards`。
- **保留**：网格定义编辑（幽灵文字 F5.1）、`cardText` 卡体预览、空态提示。
- 死代码清理：`parseResult`/`parseError`/`workflowState`/`pendingBudget`/`busy`/`outputDir`/`files` 等启动器状态全删；`buildBinOptions`/`fmtBound`/`readOutputDir` 迁出。

### OutputTab 新增「网格计数 3D 结果」小节（`gui/src/components/OutputTab.tsx`）

- 布局参考原 FMeshForm 启动器：`解析 MESHTAL`（`meshtal-detect` 自动探测，outputDir 读工作区落盘目录）+ `选择 meshtal 文件`（Tauri `POST /api/choose-file`）+ 主按钮 `3D 体积可视化`（调共享 `openVolume3DWindow`）。
- `meshtal-parse` 取 tally 列表 → `<select>` 选择 xyz 矩形网格 tally；`decideResolution` 超预算 → F3「流畅/精细」弹窗；保留 F1 空态三步引导 / F1.2 无文件提示 / A1.2 不匹配横幅 / F4 错误 hint 优先。
- 几何外壳模型来自 `useDeck()`（`deck.cells/surfaces/tr_cards`，cells 映射照 TallyTab → FMeshForm 原实现）。

### TallyTab FMeshForm 调用点（`gui/src/components/TallyTab.tsx`）

- FMeshForm 调用移除 `cells/surfaces/trCards` 三个 props（不再需要 3D 启动器素材），仅传 `value`/`onChange`。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 13 文件 / 76 用例全绿 |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积/动态导入警告） |

## 测试同步说明

- 无既有测试断言 FMeshForm/OutputTab 启动按钮行为（grep `gui/test` 无命中）。`fmeshState`/`workflow`/`downsampleRequest` 纯模块测试不受影响，无需改动。
---
# 前端改动清单 — 材料编辑对话框两 Bug 修复（2026-08-14，experiment/geouned）

> 施工方：前端 | 指令：PM 派发（用户报 Bug 1 导入 INP 不自动查截面库 / Bug 2 Fe57 编辑异常）
> 范围：仅 `gui/src/components/MaterialEditDialog.tsx` + 新增 `gui/test/zaidSplit.test.ts` + 本文档。不碰后端/其它前端文件/既有测试。

## Bug 1 — 导入 INP 后材料编辑不自动查截面库（实证与用户描述有出入）

**真实根因**：手动核素行的 `onChange`（原 :264/:274）**确实接了** `/api/validate-zaid`——用户描述"没接校验"不准确。缺的是**载入时的自动校验**：`nucs` 由 `initial`（含导入 INP 的核素）在 :69 初始化，`zaidValid` 初始为空（:77），**没有挂载 effect** → 打开对话框时核素行圆点恒为灰（#555），只有用户手动改元素/质量数才触发校验。公式路径（:96-107）解析后逐核素校验，手动路径无对应。

**修法**（MaterialEditDialog.tsx）：
- 新增共用 `validateZaid(i, zaid)`（:123-130）：统一 strip 库后缀/前导 0 → GET `/api/validate-zaid` → 回写 `zaidValid[i]`。
- 新增挂载 effect（:132-137）：对 `initial` 里每个非空核素自动调 `validateZaid`（deps `[initial]`），行内立即显示 ✓/✗；外部喂入新核素时顺带重新校验。
- 公式路径校验循环改用 `validateZaid`（:193-195），行为不变。

## Bug 2 — 核素输入（Fe57）编辑异常（代码走查实证）

**真实根因**：导入 INP 的核素是**数值 ZAID**（如 `26057`，api_server:639 `lstrip("0")`）。原元素/质量数两个受控输入框的 `value`（:258/:268）都从 `nu.zaid` 派生（数值→`zaidToEl`→`split("-")`），每个 `onChange` 又用 `nu.zaid.split("-")` 重建 `nu.zaid` 回写（:260/:270）——**数值串 `split("-")` 得到 `["26057"]`，`old[1]`/`el` 取成整个 `"26057"`**：
- 删元素（Fe→F）→ 回写 `"F-"`，mass 段丢空 → **删 Fe 删掉 7**；
- 改质量数（57→56）→ 回写 `"26057-56"`，再 `zaidToEl("26057-56")` → 元素变 `"2605"` → **改 57 改不动**。

即"value 派生 + onChange 回写"闭环打在同一个 `nu.zaid` 上，且数值/带横线两种表示互相错位。

**修法**（MaterialEditDialog.tsx，本地编辑草稿方案）：
- 抽 3 个可测纯函数并导出（:38-71）：`splitZaid(zaid)→{el,mass}`（兼容数值 `26057`/`26057.50c`、自然元素 `6000`、手写 `Fe-57`）、`buildZaid(el,mass)`（对齐旧 elToZaid 语义）、`resolveZaid(ed)`（元素为空→null 不提交）。
- 新增每行本地编辑草稿 `rowEdits`（:104-110，载入时由 `zaid` 初始化一次）；sync effect（:140-151）为新增/结构变更后的核素行补初始化，不覆盖正在编辑的行。
- 元素/质量数输入框 `value` 改读 `rowEdits[i]`（:347/:354），onChange 只写草稿（:349/:356，函数式更新防交叉丢失），**不再逐键回写 nu.zaid**。
- `onBlur → commitRow(i)`（:154-166）：`resolveZaid` → `buildZaid` 写回 `nu.zaid` + `validateZaid`（失焦时校验，对齐公式路径做法）。
- 保存按钮改 `mergePendingEdits()`（:169-182，:227）：未失焦草稿兜底并入 nucs。
- `delRow`/`moveRow`/`parseFormula` 清空草稿（:201/:217/:191），防按位置缓存的行号错位。

**新增可测纯函数 vitest**：`gui/test/zaidSplit.test.ts`（22 用例）：拆组/组装/往返稳定（splitZaid∘buildZaid 恒等）+ Bug 2 回归（改质量数不动元素、改元素不动质量数、删元素不清质量数）+ resolveZaid 空元素不提交。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 14 文件 / 98 用例全绿（76 基线不破 + 新增 22） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

## 回归风险（需 PM 留意）

1. **校验时机从"逐键"变为"失焦/提交"**：手动编辑元素/质量数时不再每键打 validate-zaid（请求更少、避免中间态），✓/✗ 在失焦/保存时刷新。行为对齐公式路径。若 PM 希望"输入过程中实时变灰"的视觉反馈，可后续再加。
2. **自然元素显示变化**：`6000`（自然 C）质量数框从显示 `0` 变为空串（质量位 000 语义更贴合 MCNP），失焦提交仍回写 `6000`，往返稳定（有测试 pin）。
3. **结构操作（删除/拖动排序/公式重解析）会丢弃未失焦的行内草稿**（清空 rowEdits 后按已提交值重新初始化）——预测性行为，窗口极小。
---
# 前端改动清单 — 化学式份额语义 UI（2026-08-14，experiment/geouned）

> 施工方：前端 | 指令：PM 直接派发（份额语义标注 + 可选原子份额切换）| 后端已加 `is_weight`（`/api/expand-formula`，body JSON 布尔，缺省 true）
> 范围：仅 `gui/src/components/MaterialEditDialog.tsx` + 新增 `gui/test/shareMode.test.ts` + 本文档。不碰后端/其它前端文件/既有测试。
> 纪律：fraction 仍为不透明字符串直通（未改直通语义）；未动 zaidValid/rowEdits/commitRow/mergePendingEdits（两 Bug 修复链路零触碰）。

## 背景（已实证）

正负号全链路保留、无数据丢失。用户困惑源于 UI 未说明 MCNP 约定：**负号=质量份额、正号=原子份额**，而 expand-formula 默认输出质量份额（负）。本次让 UI 说清楚 + 可选原子份额。

## 改动点（MaterialEditDialog.tsx）

### ① UI 标注（份额语义）
- **化学式区**：解析结果处新增标注行（:333-335）「`份额 = {质量份额|原子份额} · MCNP 负号=质量份额，正号=原子份额 · 质量份额按各核素质量占比；原子份额按原子数占比`」。
- **文本区幽灵文字**（:315）：注明「份额符号由右侧模式决定：负号=质量份额，正号=原子份额」。
- **解析表**：份额表头与每个 fraction 单元格加 `title` tooltip（SIGN_CONVENTION_NOTE，:344/:352）；手动行份额输入框 placeholder `"份额"`→`"份额(负=质量)"` + tooltip（:400）。
- 密度栏原已注明「负号=质量密度，正号=原子密度」（:277），语义一致。

### ② 份额模式切换（质量/原子）
- 新增 `shareMode` state（:119，默认 `"weight"`）+ 切换按钮组（:317-331，在「解析化学式」旁两个小按钮 `质量份额 / 原子份额`）。
- 对接后端 `is_weight`：`expandFormula(formula, isWeight)` 请求体加 `is_weight` 布尔（:97-100）；`parseFormula` 按当前模式取值 `shareModeToIsWeight(mode ?? shareMode)`（:206）；切换时若已填公式立即按新模式重解析（`toggleShareMode` :207-213）→ 各核素份额显示更新（负号=质量 / 正号=原子）。
- 新增 6 个导出纯函数/常量（:74-90）：`ShareMode` / `SIGN_CONVENTION_NOTE` / `SHARE_CONVERSION_NOTE` / `shareModeToIsWeight` / `shareModeLabel` —— 可测、防正负号约定与参数名漂移。

### ③ 导入 INP 的份额保留原样 + 正负含义提示
- 手动模式核素列表标题下新增小字（:367-370）：「份额保留原样：负号=质量份额、正号=原子份额（导入 INP 不自动转换）」——不擅自转换，仅提示含义。

## is_weight 对接方式

- `POST /api/expand-formula` body：`{ "formula": string, "is_weight": boolean }`。
- `is_weight: true`（质量份额，默认）→ 输出负号；`false`（原子份额）→ 输出正号。
- 前端始终显式传 `is_weight`（weight 模式传 `true`）；后端 `data.get("is_weight", True)` + `None`→`True` + 字符串 truthy 解析，向后兼容（未传/传 null 行为与现状一致）。fraction 仍直通展示、不改符号。

## 新增测试

`gui/test/shareMode.test.ts`（6 用例）：shareModeToIsWeight（weight→true / atomic→false）、shareModeLabel（两种显示名 + 穷举）、SIGN_CONVENTION_NOTE（含负号=质量份额 与 正号=原子份额）、SHARE_CONVERSION_NOTE（含质量占比 与 原子数占比）。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 15 文件 / 104 用例全绿（98 基线不破 + 新增 6） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积/动态导入警告） |

## 未破坏项确认

- `splitZaid/buildZaid/resolveZaid` + `zaidValid/validateZaid` + `rowEdits/commitRow/mergePendingEdits`（载入自动校验 + 元素/质量数稳定编辑）全部原样保留，`zaidSplit.test.ts` 22 用例仍全绿。
- fraction 直通语义未改（手动行 :400 / 公式解析 :352 均原样展示后端返回的字符串）。
---
# 前端改动清单 — 份额归一化提示 + 计数类型自动变修复（2026-08-14，experiment/geouned）

> 施工方：前端 | 指令：PM 转派两项新任务（在份额标注/切换工作之后接续）| 范围：仅 MaterialEditDialog.tsx + TallyTab.tsx + 新增 2 测试文件 + 本文档
> 纪律：vitest 104 全绿不破（+10=114）；tsc/build EXIT 0；零新依赖；不改后端/测试基线。未 commit（任务 3 统一提交由 PM 安排）。

## 任务 1 — 份额归一化提示（MaterialEditDialog）

- 归一化保留现状（后端 api_server.py:636-638 不动）。化学式解析结果处新增提示（MaterialEditDialog.tsx :340-343，`parsed` 时显示，样式与份额标注一致：小字/tertiary 色）：
  「份额已归一化（总和=1）；化学式:比例 只影响各成分的相对比例，结果仍会归一化」
- 让用户明白为什么 `H2O:2` 和 `H2O` 份额一样。

## 任务 2 — 计数类型自动变修复（TallyTab）

**bug 定位**：`handleNumberChange` 只对纯数字走 `numberToType`；`parseF5Variant` 对 `F25`/`F25X` 的 num 段是 `"F25"`（`parseInt`→NaN，`pn>0` 分支跳过）→ 输入带 F 前缀时类型字段不自动跳 F5；且 `F25` 存入 number 后 `parseInt`→0 会污染 deck 编号。

**修法**：
- 新增导出纯函数 `parseTallyTypeNumber(raw)`（TallyTab.tsx :45-57）：剥前导 `F` + 剥 `X`/`Y`/`Z` 后缀 → 按个位数经 `numberToType` 映射类型；无效输入（""/abc/F/0/成像前缀）→ `{ type:null, number:原样 }`。编号字段回填剥净后的数字（`F25X`→"25"，顺带修掉 parseInt→0 的 latent bug）。
- `handleNumberChange`（TallyTab.tsx :150-159）改接 `parseTallyTypeNumber`：命中类型即 `{ number, type }`；未命中再走 `parseF5Variant`（F5 成像 IC/IR/IP 既有语义保留）。
- `parseF5Variant`（TallyTab.tsx :62-70）导出，普通编号分支改委托 `parseTallyTypeNumber`；删死常量 `F5_RING_SUFFIXES`（环形后缀判定并入通用解析）。

## 新增测试（gui/test/tallyTypeNumber.test.ts，10 用例）

- `parseTallyTypeNumber`：25/F25/25X/F25X/5/F5 → F5（含编号回填 25/5）；1/12/24/6/17/8/F4 → 各类型；无效兜底 ""/abc/F/0/F5IC123 → type null、编号原样。
- `parseF5Variant`：成像前缀 IC123；普通 5/25X/F25 → F5（保留既有语义）。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 16 文件 / 114 用例全绿（104 基线不破 + 新增 10） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积/动态导入警告） |

## 行为细节说明（PM 留意）

- 环形后缀输入 `25X` 现在编号框回填 "25"（旧行为保留 "25X"）：下游 deck push 本就 `parseInt(t.number)` 剥掉 X（deck 恒存整数），生成端只发 `F{number}`，行为等价；且 `F25X` 此前存成 "F25X"→parseInt→0（deck 编号丢失 bug）本次一并修复。
- `parseTallyTypeNumber`/`parseF5Variant` 已导出（测试可 pin），不改变组件对外行为。
---
# 前端改动清单 — UI 隐藏 TMESH 计数卡入口（2026-08-14，feat/meshtal-volume）

> 施工方：前端 | 指令：PM 直接派发（用户决定：TMESH 以后再更新加入）| 范围：仅 `gui/src/volume/fmeshState.ts` + `gui/src/volume/FMeshForm.tsx` + 2 个测试文件 + 本文档
> 纪律：只隐藏"创建/选择 TMESH"入口，不删 TMESH 代码路径；不碰后端/解析核心；零新依赖；未 commit。

## 任务 — UI 层隐藏 TMESH 计数卡，代码路径保留

### ① UI 点（FMeshForm.tsx）

| UI 点 | 位置 | 改动 |
| :--- | :--- | :--- |
| 表单标题 | :131 | `网格计数（FMESH/TMESH）` → `网格计数（FMESH）` |
| 文件头注释 | :2-5 | 同步改为「网格计数（FMESH）」，注明 TMESH 入口 UI 隐藏、代码路径保留待后续启用 |
| 空态文案 | :138 | 「创建 FMESH/TMESH 卡」 → 「创建 FMESH 卡」 |
| kind 下拉 | :154-161 | **移除 `<option value="TMESH">`**，只留 FMESH（用户不能选/建 TMESH 卡） |
| tmesh 字段标注 | :31 | label `"TMESH"` → `"时间分箱（TMESH 关键字）"` + 新增 hint 小字「这是 FMESH 卡的时间边界分箱关键字，不是 TMESH 计数卡」；字段/placeholder/值不变，时间轴动画依赖不变 |
| t_ints 字段标注 | :32 | label `"TINTS"` → `"TINTS（时间区间数）"`（与 tmesh 呼应）；字段/placeholder/值不变 |

### ② 导入 TMESH 行处理（选方案 a：只读徽标）

- 新增导出纯函数 `fmeshKindControl(kind, geom)`（:44-57）：kind=FMESH → `select`；kind=TMESH → `badge`（只读徽标 + note）。
- 表单行 :148-162：`kind === "TMESH"` 时**渲染只读徽标"TMESH"**（不可编辑/不可切，title 带说明），不再渲染下拉 → 无空白 option 问题；:186-190 在行头下渲染说明小字。
- 说明文案按 geom 区分：`cyl` → 「…cyl 网格不进入体积可视化」；`xyz`（RMESH 子卡）→ 「…数据原样保留」。
- **为什么选 a 不选 b（raw 兜底到其他卡）**：方案 a 保持行仍在 `deck.tally.fmesh` 受控列表内，`fmeshToCardText` 的 TMESH 序列化分支原样回放，round-trip 保真、零数据丢失；方案 b 需把行搬出 fmesh 列表，会破坏受控表单契约、引入跨区搬移的丢数据/报错面，且与"保留 TMESH 代码路径"目标冲突。TMESH 行其余字段（编号/粒子/网格边界等）保持可编辑，仅 kind 锁只读。

### ③ fmeshState.ts（仅注释/标注，未动逻辑）

- 文件头注释 :2-6：追加「UI 现状」说明——TMESH 入口 UI 隐藏，但 `FmeshKind` 联合类型、`FAMILY_RE`、TMESH/RMESH/CMESH 解析吸收、emit、序列化路径**全部保留**，未来启用直接放开 UI 即可。
- `tmesh` 字段注释 :28：`TMESH 时间（与 TMESH 卡种类别区分）` → `FMESH 卡时间分箱关键字（TMESH=时间边界；与 TMESH 计数卡种类别区分）`。
- **解析逻辑零改动**（cardTextToFmesh / fmeshToCardText / buildFmeshPayload / fmeshDefsToRows / FAMILY_RE 全部原样）。

## 测试

- 无既有测试断言 kind 下拉含 TMESH option（grep `gui/test` 仅 fmeshState.test.ts 命中 kind，均为纯模块解析/序列化断言，不受 UI 改动影响）。
- **新增** `gui/test/volume/fmeshKind.test.ts`（3 用例）：pin `fmeshKindControl`——FMESH→select / TMESH→badge+数据保留 / TMESH+cyl→badge+cyl 不进入体积可视化。
- **新增** `fmeshState.test.ts` +1 用例：后端 parse 返回 kind=TMESH 行 → `fmeshDefsToRows` 保留 kind/geom/number/origin，`fmeshToCardText` 仍走 TMESH 结构化分支（TMESH3 + RMESH3…）round-trip 不丢。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 17 文件 / **118 用例全绿**（114 基线不破 + 新增 4） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

## 回归风险

1. **导入含 TMESH 行的 INP**：行显示只读徽标 + 说明，数据原样保留，round-trip 保真；kind 不可切为 FMESH（预期行为，方案 a 语义）。
2. **`tmesh`/`t_ints` 字段**：仅改 UI label/hint，字段名、placeholder、值、`buildFmeshPayload`/`fmeshDefsToRows` key（`tmesh`/`t_ints`）零变动，时间轴动画与后端载荷不受影响。
3. **TallyTab / OutputTab / openVolume3DWindow**：未触碰；FMeshForm props（value/onChange）未变，调用点无需改动。

---
# 前端改动清单 — FMESH 表单改进 · 字段对齐 MCNP6（2026-08-14，feat/meshtal-volume）

> 施工方：前端 | 指令：PM 直接派发（对照 C810 + 网源验证的 MCNP6 规范；字段契约以指令为准，后端已先落地 pytest 445/0）
> 范围：仅 `gui/src/volume/fmeshState.ts` + `gui/src/volume/FMeshForm.tsx` + `gui/test/volume/fmeshState.test.ts` + 新增 `gui/test/volume/fmeshValidation.test.ts` + 本文档
> 纪律：零新依赖；不改后端/其它无关文件；测试先行（先红后绿）。

## 任务 — FMESH 表单字段对齐 + 校验（7 项 + 校验规则）

### ① 字段改名对齐（eints→emints / t_ints→tmints）

| 位置 | 改动 |
| :--- | :--- |
| `fmeshState.ts` FmeshRow/emptyFmeshRow | `eints`→`emints`、`t_ints`→`tmints`（:25/:47-49） |
| `KEY_TO_FIELD`（:91-98） | `EMINTS→emints`、`EINTS→emints`、`TMINTS→tmints`、`TINTS→tmints`（导入容错两种拼写，镜像后端 `_KEYS`） |
| `fmeshToCardText` cardLines（:196-205） | 生成发 `EMINTS=`/`TMINTS=`（非 EINTS/TINTS），顺序 IMESH/IINTS/JMESH/JINTS/KMESH/KINTS/EMESH/EMINTS/TMESH/TMINTS/MAT/OUT/AXS/VEC/TR |
| `buildFmeshPayload`（:228-250） | JSON key 用 `emints`/`tmints`（对齐后端 `_fmesh_from_list`） |
| `fmeshDefsToRows`（:253-276） | 读 `emints`/`tmints`（向后兼容旧 `eints`/`t_ints`） |

### ② 新增字段 axs / vec / tr

- FmeshRow + emptyFmeshRow 加 `axs`/`vec`/`tr`（空串）；KEY_TO_FIELD 加 `AXS→axs`/`VEC→vec`/`TR→tr`；cardLines 回放 `AXS=`/`VEC=`/`TR=`；buildFmeshPayload / fmeshDefsToRows 透传。

### ③ GEOM 下拉（四选，value 存单 token 连写）

- 新增导出 `FMESH_GEOM_OPTIONS`（XYZ 默认 / REC 直角、CYL / RZT 圆柱）+ `normalizeGeom`（大写单 token，空值默认 XYZ）+ `isCylGeom`。
- `cardTextToFmesh` 对 GEOM 只取首 token 归一化（防 `GEOM=X Y Z`）；`fmeshToCardText` 头行 `GEOM=XYZ` 连写（镜像后端 `_card_lines`）。

### ④ AXS/VEC 条件显示 + 平行校验

- FMeshForm：`isCylGeom(r.geom)` 时才渲染 AXS/VEC 两输入。
- 校验：`vectorsParallel`（归一化叉积 |sinθ| < 1e-6；零向量/非法输入不误判），cyl 系两向量平行 → error「AXS 与 VEC 不能平行」。

### ⑤ TR 字段

- 可选变换编号输入；校验非空时须正整数。

### ⑥ OUT 改下拉（九选 + 说明）

- 新增导出 `FMESH_OUT_OPTIONS`：COL（默认）/ CF / COLSC / CFSC / IJ / IK / JK / NONE / XDMF，各带 hint（CF 额外输出体积 + 结果×体积；NONE 不打印 meshtal；XDMF 供 ParaView）。

### ⑦ MAT 帮助文案

- placeholder/hint：「0=粒子所在格材料（默认）；非 0=指定材料号」。

### ⑧ 校验规则（抽为纯函数，表单行内友好提示）

- 新增 `validateFmeshRow(r)` / `vectorsParallel` / `parseNumberList` / `parseVector` / `gridCellCount` / `normalizeGeom` / `isCylGeom`（fmeshState.ts 导出，可测）。
- 规则：① `iints/jints/kints/emints/tmints` 每 token 须正整数；② 各 `*ints` 条目数与对应 `*mesh` 条目数匹配（缺一侧报错，数量不等报「不匹配」）；③ mesh 列表值单调递增（含科学计数法能量）；直角系另校验 mesh 首值 > ORIGIN 对应轴坐标；④ 圆柱系（CYL/RZT）kmesh 末值须 = 1（θ 转数）；⑤ cyl 系 AXS∥VEC 报错；⑥ TR 正整数；⑦ 三方向区间总数乘积 > 128³（2,097,152，即 `FMESH_MEMORY_WARNING_THRESHOLD`，对标契约 128³ 默认渲染预算）→ warning 内存/性能提示。
- 表单：每行渲染校验横幅（红=error / 黄=warning，标字段名）；TMESH 只读导入行跳过校验（数据原样保留）。
- 另修：`fmeshKindControl` 判 cyl 从 `geom==="cyl"` 改为 `isCylGeom(geom)`（geom 现为大写单 token，避免 TMESH cyl 行提示失效）。

## 测试（测试先行：先写红，后实现转绿）

| 文件 | 用例 | 覆盖 |
| :--- | :--- | :--- |
| `gui/test/volume/fmeshValidation.test.ts`（新增 24） | normalizeGeom/isCylGeom / 正整数 / 条目数匹配 / 单调递增+ORIGIN / cyl kmesh 末值=1 / vectorsParallel+AXS 平行 / TR / gridCellCount+内存警告 / parseNumberList | 校验纯函数全套 |
| `gui/test/volume/fmeshState.test.ts`（迁移 +3） | 字段改名引用迁移；新增：EMINTS/TMINTS 新拼写导入、新字段 AXS/VEC/TR/OUT round-trip、旧拼写导入→新关键字回放、fmeshDefsToRows 向后兼容旧 eints/t_ints、GEOM=XYZ 连写 | 卡体生成关键字 + round-trip |

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 18 文件 / **145 用例全绿**（118 基线不破 + 新增 27） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

## 与后端契约一致性

- 生成关键字：前端 `EMINTS=`/`TMINTS=`/`AXS=`/`VEC=`/`TR=`/`OUT=`、GEOM 连写 = 后端 `fmesh_parser._card_lines`（逐字一致）。
- 解析容错：`EINTS/EMINTS`→emints、`TINTS/TMINTS`→tmints = 后端 `_KEYS`（一致）。
- 载荷 JSON key：`emints`/`tmints`/`axs`/`vec`/`tr` = 后端 `api_server._fmesh_from_list`（一致；后端另有旧 key 回退，前端 fmeshDefsToRows 亦兼容旧 key）。
- **无与后端不一致项，无需 PM 仲裁。**

## 回归风险

1. **导入含 GEOM=xyz（小写）的 INP**：前端解析归一化为 `XYZ`，生成 `GEOM=XYZ`（大小写变化，MCNP 大小写不敏感，语义等价；进入前端后 round-trip 稳定）。
2. **OUT 旧值（如 `f`）**：下拉显示空白并回退说明文案，值仍原样保留回放，不丢数据。
3. **TMESH 导入行**：仍只读徽标 + 数据原样保留；校验跳过；`fmeshKindControl` 改用 `isCylGeom` 后 cyl 行提示保持正确。

---

## FMESH 傻瓜友好改造 + factor 字段（2026-08-14，PM 指令）

> 范围：仅 `gui/src/volume/`、`gui/test/volume/`、`docs/frontend-changes.md`。零新依赖；**未改后端**（`app/`、`gui/backend/` 零触碰；后端 factor 已由 backend-fmesh-factor 同步）。

### ① 简单/高级模式（默认简单，傻瓜友好）

- 新增纯函数 `simpleModeVisibleFields(mode)` + 常量 `FMESH_SIMPLE_FIELDS` / `FMESH_ADVANCED_FIELDS`（fmeshState.ts:606-626）：
  - 简单模式只露核心 4 项：`particle` + `imesh/jmesh/kmesh`；
  - 高级模式追加：`geom/origin/iints/jints/kints/emesh/emints/tmesh/tmints/mat/out/axs/vec/tr/factor`。
- FMeshForm 组件本地 `mode` state（默认 `"simple"`，不落 deck）；卡头「高级模式 ▾ / 收起高级 ▲」切换（FMeshForm.tsx:246-256）；字段区按 `visible.map` 渲染（:301-315），AXS/VEC 仍仅圆柱系显示。

### ② 按几何自动填充

- 新增深模块 `gui/src/volume/surfacesAABB.ts`：`computeSurfacesAABB(surfaces[, trCards]) → {min,max} | null`（纯函数）：
  - 解析曲面卡（平面 PX/PY/PZ、球 SO/S/SX/SY/SZ/SPH、圆柱 CX/CY/CZ/C/X/C/Y/C/Z、宏体 RPP/RCC/TRC/REC/WED/BOX/RHP/HEX/ELL/ARB、环面保守球包）合并取 x/y/z 并集；
  - 无限/不可解类型（一般平面 P、二次曲面 GQ/SQ、锥面 K*）跳过；任一轴无有界 → 返回 null；
  - TR 变换：有 trCards 且可解析（含 `*TRn` 角度）→ 平移/旋转后取有界盒；否则跳过该曲面（容错）。
  - `aabbToFmeshValues(aabb)` → `{origin, imesh, jmesh, kmesh}` 填表值 + `formatCoord` 坐标格式化。
- FMeshForm 用 `useDeck()` 接回 `deck.surfaces` + `deck.tr_cards`（TallyTab 未改，表单直连 deck）；「⚡ 按几何自动填充」按钮（FMeshForm.tsx:123-131, :322-328）：解析 AABB 一键填 ORIGIN + IMESH/JMESH/KMESH（网格覆盖模型）；解不出 alert 提示。

### ③ 粒子说明 + 三步上手引导

- 粒子说明：「每个网格计数一个粒子（N/P/E）；要多种粒子就加多行」（FMeshForm.tsx，简单模式粒子旁）。
- 三步引导：「① 选粒子 ② 点自动填充 ③ 解析看 3D 结果」（FMeshForm.tsx，简单模式 FMESH 行顶部）。

### ④ factor 字段（放高级模式）

- `FmeshRow.factor` 默认 `"1"`（fmeshState.ts:45, :64）；`KEY_TO_FIELD` 加 `FACTOR→factor`（:202）；`cardLines` 回放 `FACTOR=`（非空才发，:320）；`buildFmeshPayload` 带 `factor` key（:385）；`fmeshDefsToRows` 读 `factor`（缺省默认 `"1"`，:413）。
- `validateFmeshRow` 加规则 ⑧：FACTOR 正整数（≥1），非法友好提示「FACTOR 须为正整数（乘法因子 ≥ 1）」（fmeshState.ts:598-601）。
- FMeshForm 高级模式 FACTOR 输入框 + 幽灵文字/提示（FMESH_FIELD_LABELS + FMESH_PLACEHOLDERS.factor）。

### ⑤ 未改既有行为

- 既有字段/校验/geom 下拉/AXS/VEC/TR/OUT/MAT 零改动；`hasStructured` 未含 factor（raw 兜底 round-trip 保真不变）。

## 测试（测试先行：先红后绿）

| 文件 | 用例 | 覆盖 |
| :--- | :--- | :--- |
| `gui/test/volume/fmeshFactor.test.ts`（新增 9） | 默认 "1" / 卡体含 FACTOR=（非空才发）/ 解析 FACTOR=→factor（round-trip）/ 载荷+解析透传 / 校验正整数（合法/非法/空） | factor 全链路 |
| `gui/test/volume/simpleMode.test.ts`（新增 4） | 简单只露核心 4 项 / 高级含 factor 等全部 / 无重复 / ADVANCED_FIELDS 齐备 | 简单/高级可见性纯函数 |
| `gui/test/volume/surfacesAABB.test.ts`（新增 22） | 平面/球/圆柱/宏体/混合 AABB / */+ 前缀 / TR 平移与角度旋转 / 解不出→null（空/无限/二次曲面/单轴无界/TR 未提供/非法数值） / formatCoord+aabbToFmeshValues | AABB 纯函数全套 |

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 22 文件 / **190 用例全绿**（155 基线不破 + 新增 35） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

## 与后端契约一致性（factor）

- 字段名 `factor` / 关键字 `FACTOR=` / 默认 `1` / 序列化 JSON key `factor` —— 与 backend-fmesh-factor 同步一致（后端 `fmesh_parser.py` / `_fmesh_from_list`）。
- 卡体生成发 `FACTOR=`（前端默认 "1"，后端默认 1，语义一致）；解析 `FACTOR=` → factor。
- **无与后端不一致项。**

## 回归风险

1. **生成卡体新增 `FACTOR=1`**：前端 `emptyFmeshRow.factor="1"` → 结构化 FMESH 卡体回放/载荷现含 `FACTOR=1`（MCNP factor 默认 1，语义等价；后端已支持）。旧 localStorage 工作区行无 factor 字段 → `fmeshToCardText` 按空串不发，round-trip 文本稳定。
2. **简单模式隐藏字段**：默认简单只露粒子+三向范围；ORIGIN/INTS/能量/时间/GEOM 等在高级模式。老用户需点「高级模式」查看全部（GEOM 默认 XYZ，行为不变）。
3. **AABB 容错**：TR 变换未提供 TR 卡 / 仅无限曲面的模型 → 自动填充提示解不出，回退「通用模板一键填充」；宏体方向矢量类按保守合成角点，网格只可能偏大（覆盖模型，安全）。

---

## FMESH 关键字等号可选解析修复（2026-08-15，PM 指令，镜像后端 fmesh_parser）

> 范围：仅 `gui/src/volume/fmeshState.ts` + `gui/test/volume/fmeshState.test.ts` + 本文档。零新依赖；**未改后端**（后端同步在修 `app/meshtal/fmesh_parser.py`）。

### Bug

MCNP 允许空格分隔关键字（`imesh 51`）、等号可选；原 `KEY_RE = /^([A-Za-z]+)=(.*)$/` 强制 `=` → 裸 `imesh` 不匹配，落到 `i += 1` 被当未知 token 跳过，网格字段全空。

### 改动（fmeshState.ts）

1. **`KEY_RE` 等号可选**（:199）：`/^([A-Za-z]+)(?:=(.*))?$/` —— 裸 `imesh` 与 `imesh=51` 均匹配，`km[2]` 为 `undefined` 时走收集分支（`vals = km[2] ? [km[2]] : []`，:285）。
2. **新增 `KEY_EQ_RE`**（:201）：`/^([A-Za-z]+)=/` —— 带显式等号必是关键字起点（无论已知未知），作收集循环边界。
3. **新增 `isKnownKeyToken`**（:220-223）：`KEY_TO_FIELD` 内、大小写不敏感（裸或带 `=` 均算），作收集循环已知关键字边界判定。
4. **收集循环 break 条件**（:288-296）：由「任意字母词（`FAMILY_RE || KEY_RE`）」改为「卡族头 / 已知关键字 / 未知关键字带 `=`」三判——防 `geom xyz` 的字母值 `xyz` 被误判截断，同时 `inc=1` 之类在收集中途出现时不污染字段值。
5. **未知关键字容错**：`inc=` 等非已知 key（带 `=`）在主循环经 `!field` 分支跳过不报错（既有 :281-284 已覆盖，未改）；裸字母词在收集循环当值收集。

### 测试（fmeshState.test.ts 13 → 20，+7）

| 用例 | 覆盖 |
| :--- | :--- |
| 空格分隔：裸关键字进入值收集，字段不丢 | `IMESH 51 IINTS 10` 等 + `GEOM xyz` + `ORIGIN -100 -100 -150` |
| 等号形式不受影响 | 回归：`IMESH=100 IINTS=10` |
| 混排：等号与空格分隔混合，值不串位 | GEOM=CYL / ORIGIN 0 0 0 / AXS=0 0 1 / VEC 1 0 0 等 |
| 未知关键字 `inc=` 跳过不报错，不污染相邻字段 | `IINTS=2 INC=1 JMESH=10` → jmesh 正确 |
| 关键字大小写不敏感 | `fmesh4:n geom=xyz` / `imesh=10` / `jmesh 20 jINTS=2` |
| `geom xyz` 的字母值 xyz 不被误判截断 | GEOM 裸关键字 + 字母值 + 后续 EMESH 多值 |
| round-trip：空格分隔卡体 → 结构化 → 生成（= 形式）字段保留 | 二次解析字段不丢 |

### 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 22 文件 / **197 用例全绿**（190 基线不破 + 新增 7） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

### 与后端契约一致性

- JSON key 不变：`imesh/iints/jmesh/jints/kmesh/kints/emesh/emints/tmesh/tmints/mat/out/axs/vec/tr/factor` —— 与后端 `fmesh_parser.py` 同步（后端等号可选修复同语义）。
- 生成仍发 `=` 形式（`IMESH=…`），MCNP 双形式兼容；round-trip 保真。

---

## FMeshForm 去简单/高级模式 + 字段控件 9 行布局分组（2026-08-15，PM 指令，纯布局）

> 范围：仅 `gui/src/volume/fmeshState.ts` + `gui/src/volume/FMeshForm.tsx` + `gui/test/volume/simpleMode.test.ts`→`fmeshLayout.test.ts` + 本文档。
> **零数据模型 / 卡体生成格式 / 解析逻辑改动**：`cardTextToFmesh`/`fmeshToCardText` 生成与解析逻辑完全未动（关键字等号可选修复保留，属合法）。

### 改动 1：去掉简单/高级模式切换（始终显示完整表单）

- `fmeshState.ts`：删除 `FmeshFormMode` 类型、`FMESH_SIMPLE_FIELDS`、`FMESH_ADVANCED_FIELDS`、`simpleModeVisibleFields(mode)`（原 :637-655）。
- `FMeshForm.tsx`：删除 `mode` state、card-header「高级模式 ▾ / 收起高级 ▲」折叠按钮（原 :247-254）、渲染 IIFE `(() => { const visible = simpleModeVisibleFields(mode); return … })()`（原 :264-265/:362-363）；三步引导/粒子说明由 `mode === "simple" && isSelectRow` 改为 `isSelectRow`（原 :299/:317），去掉模式条件。

### 改动 2：字段控件按 MCNP 卡结构 9 行分组（纯布局）

新增可测纯数据常量 `FMESH_ROW_LAYOUT`（`fmeshState.ts` 末尾），FMeshForm 逐行渲染：

| 行 | 字段（值/placeholder/校验/round-trip 不变） | 对应卡体行 |
| :--- | :--- | :--- |
| 1 | 粒子 \| GEOM \| OUT | 卡头 |
| 2 | ORIGIN | ORIGIN 行 |
| 3 | IMESH \| IINTS | 轴行 |
| 4 | JMESH \| JINTS | 轴行 |
| 5 | KMESH \| KINTS | 轴行 |
| 6 | EMESH \| EMINTS | 能量行 |
| 7 | TMESH \| TMINTS | 时间行 |
| 8 | MAT \| FACTOR \| TR | 材料/因子/变换行 |
| 9 | AXS \| VEC | 圆柱系才显示（`isCylGeom` 过滤） |

- 每组（边界+区间数）拆单独一行，视觉与 FMESH 卡续行逐行对应；多行 FMESH 卡（每行一个卡）保持。
- 每行分组 `display:flex; flexWrap:wrap; marginBottom:6`；AXS/VEC 行在直角系整行隐藏（`shown.length===0` → 不渲染）。
- 控件 value/placeholder/title/hint/校验、GMESH/OUT 下拉、kind 徽标（TMESH 只读导入行）全部不变。

### 改动 3：simpleMode 测试迁移（等量，197 不破）

- 删除 `gui/test/volume/simpleMode.test.ts`（4 用例，测已删除的模式可见性函数）。
- 新增 `gui/test/volume/fmeshLayout.test.ts`（4 用例，按布局方向迁移）：①9 行分组结构逐字节断言；②全部 19 字段恰好出现一次（无遗漏无重复 = 始终完整显示）；③每对 边界+区间数 在同一行；④MAT/FACTOR/TR 一行 + AXS/VEC 一行。

### 保留项确认

⚡ 按几何自动填充按钮（`autoFillByGeometry`）、通用模板一键填充、粒子说明「每个网格计数一个粒子（N/P/E）」、三步引导「① 选粒子 ② 点自动填充 ③ 解析看 3D 结果」、factor 字段（默认 1/正整数校验/FACTOR= 关键字）全部在位。

### 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 22 文件 / **197 用例全绿**（197 基线不破：-4 simpleMode + 4 fmeshLayout） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

### 零格式/解析改动确认

- `git diff gui/src/volume/fmeshState.ts`：仅「删模式块 + 加 FMESH_ROW_LAYOUT」+ 既有关键字等号可选修复（KEY_RE/KEY_EQ_RE/isKnownKeyToken/cardTextToFmesh 边界判定，上个会话合法改动，未动）。
- `fmeshToCardText`/`cardLines` 生成逻辑 grep 零改动；卡体预览即生成格式不变。
- 未改后端（app/、gui/backend 零触碰）。

---

## Bug 1 修复：FMESH 导入时粒子/GEOM/OUT 下拉不更新（2026-08-15，PM 指令）

> 用户实测官方测试文件（`tests/fixtures/official_fmesh_case1~5.i`，卡体 `fmesh14:p geom=xyz out=jk`）导入后，粒子设计符 / GEOM / OUT 三个下拉未正确变化；手动生成正常。
> 范围：仅 `gui/src/volume/fmeshState.ts` + 新增 `gui/test/volume/fmeshNormalize.test.ts` + 本文档。未碰后端/契约，JSON key 零改动。

### 根因确认

导入值小写、下拉选项大写 → React 受控 `<select>` 的 `value` 不匹配任何 `<option>` → 下拉空白不更新：

| 字段 | 导入值 | 下拉 option 值 | 归一化函数 |
| :--- | :--- | :--- | :--- |
| 粒子 | `fmesh14:p` → `particle="p"` | `P`（N/P/E） | 无（缺）→ Bug |
| GEOM | `geom=xyz` → `"xyz"` | `XYZ` | `normalizeGeom` 已有 → 正常 |
| OUT | `out=jk` → `"jk"` | `JK` | 无（缺）→ Bug |

- 导入链路两条：INP 导入走后端 parse → `fmeshDefsToRows`（`App.tsx:170` / `TallyTab.tsx:83`）；文本模式走 `cardTextToFmesh`。两条路径 `geom` 均经 `normalizeGeom` 归一化，`particle`/`out` 均未归一化。

### 改动 1：新增归一化纯函数（`fmeshState.ts`，`normalizeGeom` 之后）

- `normalizeParticle(p)`：统一大写单字母（N/P/E…，MCNP 大小写不敏感）；未知值/空值保留原文。
- `normalizeOut(o)`：大小写不敏感匹配 `FMESH_OUT_OPTIONS`（COL/CF/COLSC/CFSC/IJ/IK/JK/NONE/XDMF），命中转大写下拉值（`jk`→`JK`）；**未知值保留原文**（round-trip 保真，如既有测试 `OUT=f` 不破坏）。

### 改动 2：导入/解析路径统一应用归一化（`fmeshState.ts`）

- `cardTextToFmesh` 卡头 FAMILY_RE 分支：`particle: normalizeParticle(particle)`。
- `cardTextToFmesh` 通用 KEY 分支：`field === "out"` 时 `normalizeOut(vals.join(" "))`。
- `fmeshDefsToRows`：`particle` / `out` 两字段归一化（geom 原本已有 `normalizeGeom`）。
- 生成路径 `fmeshToCardText` / `cardLines` / `buildFmeshPayload` 零改动 —— 行值解析时已归一化，生成自然输出大写 MCNP 写法（`FMESH14:P GEOM=XYZ … OUT=JK`），round-trip 稳定。

### 新增测试（红→绿，测试先行）

`gui/test/volume/fmeshNormalize.test.ts`（6 用例）：
1. `normalizeParticle` 纯函数（p→P / n→N / E 不变 / 空→空）。
2. `normalizeOut` 纯函数（jk→JK / col→COL / xdmf→XDMF / 未知 f 保留 / 空→空）。
3. `cardTextToFmesh` 官方 case1 卡体 → particle=P / geom=XYZ / out=JK（回归样本=官方 case 原样复制）。
4. `fmeshDefsToRows` 后端 parse 载荷（小写值）→ 同样归一化。
5. round-trip：解析→生成→再解析，粒子/GEOM/OUT 保持大写下拉值，网格字段保留。
6. 官方 case2~5 变体（含未知关键字 `inc=`）不污染字段，`out=jk` 仍归一化。

### 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 23 文件 / **203 用例全绿**（197 基线不破 + 6 新增） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

- 说明：全量首跑曾见 `colorize.test.ts` 128³ 计时用例 1 次失败（50.9ms>50ms），为 PROJECT_MEMORY 已记录的 **flaky 计时用例**（负载偶发），隔离重跑通过（49ms），非本次改动回归。
- 未改后端（app/、gui/backend 零触碰）；未装任何依赖。

---

## P0 修复：3D 结果窗口渲染整棵主应用树（2026-08-15，PM 指令，测试先行）

> 用户反馈「网格计数 3D 结果会弹出一个客户端」。只读排查定位：`main.rs` 建窗 label `volume3d` 与 `App.tsx` WindowRouter 路由分支 `volume` 不匹配 → volume3d 窗口落空到 `<AppInner/>`，子窗口渲染整个主应用。
> 范围：`gui/src-tauri/src/main.rs`（label 单值统一 + 死代码清理）+ 新增 `gui/test/volume/windowRouteConsistency.test.ts` + 本文档。未碰后端/契约，未 commit。

### 根因

- `main.rs:85` `create_or_focus(&app, "volume3d", "3D 结果", 1300.0, 820.0)` —— 建窗 label = `volume3d`。
- `App.tsx:444` WindowRouter `if (label === "volume") return <ResultWindow />` —— 路由只认 `volume`（对应浏览器调试 hash `#/volume`）。
- `"volume3d"` 不匹配任何路由分支 → `App.tsx:445` 落到 `<DeckProvider><AppInner /></DeckProvider>` → 子窗口渲染整个主应用 UI（视觉 = 第二个完整客户端）。
- 对照 preview3d / cross_section 两窗 label 与路由一致，唯独 volume3d 例外；git 历史确认自 `ea20ad7` 首次引入、从未修复。

### 改动 1：窗口 label 单值统一（`main.rs`）

- `open_volume3d_window` 的 `create_or_focus` label `"volume3d"` → `"volume"`（title「3D 结果」、尺寸 1300×820、command 名 `open_volume3d_window` 均不变）。App.tsx:444 已路由 `volume`→ResultWindow，无需改 App.tsx；调试 hash `#/volume` 与真实窗口 label 从此统一为 `volume`（对齐 preview3d/cross_section 惯例）。
- 完整性核验：全仓 grep `volume3d`，唯一作为**窗口 label** 的是 main.rs:85；`windows.ts` 的 `KEY_VOLUME3D = "mcnp_win_volume3d"`（桥 key）与 `invoke("open_volume3d_window")`（command 名）**保持不动**。docs（contracts/qa-report/frontend-changes 历史条目）为文档层，由 PM 决定是否通知架构师更新契约建议 label。

### 改动 2：死代码清理（`main.rs`，PM 批准，低风险）

- `create_or_focus` 内重复的 `if let Some(win)` 块两段逐字节相同，删一段（原 :51-60 → 单段）。

### 新增测试（红→绿，测试先行）

`gui/test/volume/windowRouteConsistency.test.ts`（3 用例，源码级守卫，读 `main.rs`+`App.tsx`+`windows.ts` 文本断言）：
1. main.rs `create_or_focus` 建窗 label 集合 == App.tsx WindowRouter 路由分支 label 集合（三者一致）。
2. 三弹出窗 label 各自与路由同值（preview3d/cross_section/volume），断言**绝无 volume3d**。
3. localStorage 桥 key `mcnp_win_volume3d`（KEY_VOLUME3D）保持不动，不随窗口 label 更名。
先红（2 失败：set 不等 + main.rs 缺 volume）后绿。

### 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 24 文件 / **206 用例全绿**（203 基线不破 + 3 新增；全量首跑 colorize 128³ 计时 1 次 flaky 红，隔离重跑 206/0） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |
| `cd gui/src-tauri && cargo check` | EXIT 0（mcnp-ui v1.7.0 Finished dev，29.73s） |

- 未改后端（app/、gui/backend 零触碰）；未装任何依赖；未 commit（等 PM 统一提交，P0 落库后派 packager 重打包）。

---

# 前端改动清单 — 3D 结果窗口体积可视化用户实测 4 症状修复（2026-08-15，PM 指令，测试先行）

> 施工方：前端 | 指令：PM 直接派发（用户实测反馈 4 症状：改透明度没用 / 单滑杆语义不清 / 栅元默认应半透明 / 默认视距过大栅元极小 / 只见栅元不见体积层）+ PM 补充指令（用真实文件确认真实体积层渲染链路完整）
> 范围：仅 `gui/src/volume/`、`gui/src/three/`、`gui/test/volume/` 新测试 + 本文档。零新依赖；未改后端/契约（§7 共享 offset、renderGate 复用、WebGL2 降级、cameraParams farNear≤1e4 铁律全部保持）。

## 症状与根因（PM 已定位，本批照修）

| 症状（用户原话） | 根因 |
| :--- | :--- |
| 1「改透明度没有用」+ 5「只看见栅元」 | 栅元外壳默认 opaque（VolumeRenderer `transparentMode="opaque"`，cellMaterial 默认 `{transparent:false, depthWrite:true}`）→ 不透明外壳 depthWrite 挡住体积层 → 体积层永远被遮住 |
| 2「栅元透明度还是粒子透明度？」 | 只有一个「透明度」滑杆且只控体积层 uOpacity（VolumeControlPanel opacity → setOpacity → volumeMat.uniforms.uOpacity）；外壳只有二元「半透明」checkbox（see-through→opacity 0.6 硬编码），无连续控制 |
| 4「默认视距特别大、把栅元弄的特别小」 | 默认取景按并集包围盒（VolumeRenderer alignAndFrame → unionBoxes([shellBox, volumeWorldBox]) → computeVolumeCamera → viewDist=realExt*3.5）；外壳远大于体积盒时（真实几何模型包 1×2×2 微网格）视距过大、体积层小到看不见 |

## 修复 1 — 栅元外壳默认半透明（`gui/src/three/cellMaterial.ts` + `gui/src/volume/VolumeRenderer.ts`）

- `TransparentMode` 扩为 `"opaque" | "semi" | "see-through"`；新增 `DEFAULT_SHELL_OPACITY = 0.4`。
- `buildCellMaterial` 新增 **semi 档位**：`{transparent:true, depthWrite:false, opacity:0.4}`——**depthWrite:false 是体积层透出的关键**（外壳不再写深度）；新增可选 `opacity` 参数作半透明档位连续透明度覆盖（栅元滑杆 0~1）；真空栅元（M0）opacity 0 语义全档位保持；**模块无 mode 调用默认仍 opaque**（Preview3D 主组件默认契约不变，不回归）。
- `VolumeRenderer` 默认 `let shellOpacity = DEFAULT_SHELL_OPACITY`（原 `transparentMode="opaque"`）；`shellSpecFor(color)`/`applyShellMaterial(mesh,color)` 单点应用（透明度滑杆 0~1 → semi；1 → opaque 恢复 depthWrite 无 overdraw）。

## 修复 2 — 双透明度滑杆、语义明确（`VolumeControlPanel.tsx` + `ResultWindow.tsx` + `VolumeRenderer.ts`）

- `VolumeControlPanel` 拆两个独立滑杆，标签/tooltip 写清"哪个管哪个"：
  - **栅元透明度**（控几何外壳；默认 0.4=半透明；拉满=不透明；title「越低越能看穿外壳看到体积层」）
  - **体积透明度**（控体积计数数据层；默认 1 最实；title「100% 最实，越低越淡」）
- 删除原二元「半透明」checkbox（seeThrough/onSeeThroughChange）——语义并入「栅元透明度」滑杆（连续 0~1 含默认半透明）。
- `ResultWindow` 状态改为 `shellOpacity`（`DEFAULT_SHELL_OPACITY`）/ `volumeOpacity`（`DEFAULT_VOLUME_OPACITY`）→ `renderer.setShellOpacity` / `renderer.setOpacity`。
- `VolumeRendererHandle` 新增 `setShellOpacity(v)`；`setTransparentMode` 保留（向后兼容，档位→透明度映射）。
- 新增可测纯函数 `deriveOpacity(shellOpacity, volumeOpacity)`：两滑杆**独立、可叠加**，越界钳制 [0,1]；1 → 外壳 opaque（无 overdraw）、(0,1) → semi、0 → 全透明。

## 修复 3 — 默认取景以外壳≫体积时以体积盒为主（`alignWorld.ts` + `VolumeRenderer.ts`）

- 新增纯函数 `computeFramingBox(shellBox, volumeBox)`（alignWorld.ts）：无外壳 / 外壳⊆体积 / 外壳与体积可比（体积盒最大边 ≥ 25% 并集最大边）→ 返回**并集**（既有行为，中心重合不回归）；外壳≫体积盒（< `VOLUME_FRAMING_RATIO=0.25`）→ 返回**体积盒**（体积层清晰可辨，避免视距过大）。
- `VolumeRenderer.alignAndFrame` 相机改接 `computeVolumeCamera(computeFramingBox(shellBox, volumeWorldBox))`；**共享归一化 offset 仍按并集**（§7.2 对齐不变量逐字节不变，cameraParams near/far≤1e4 铁律未破坏）。

## 修复 4 — 真实文件体积层渲染链路纯 seam 验证（PM 补充指令）

用户真实文件 `tests/fixtures/real_meshtal_jk.meshtal`（tally14/p/1×2×2 四体素，grid_bounds 49,-10,90~51,10,110）是受支持文件；把渲染链路中可测的纯几何/数据派生全部 pin 住（GPU 实渲染为 `#/volume` e2e/人工冒烟，契约 §9.3）：

- 新增 `textureDimsFromResolution([ni,nj,nk])` → `[nk,nj,ni]`（Data3DTexture 维度，后端 numpy z 最快扁平布局）。
- 新增 `volumeBoxSceneTransform(volumeWorldBox, offset)` → Mesh position/scale + shader uBoxMin/uBoxMax（复用 alignWorld.applyOffset）。
- 验证：标量帧长度 = 4 体素 → colorize 输出 RGBA 16 字节；dims=(2,2,1)；box scale=(2,20,20)；外壳≫体积时取景 target=体积盒中心。

## 测试（测试先行：先写红 → 实现转绿）

新增 `gui/test/volume/` 4 文件 27 用例，首跑 **22 失败 / 5 通过（红）** → 实现后全绿：

| 文件 | 用例 | 覆盖 |
| :--- | :--- | :--- |
| `shellSemiTransparent.test.ts`（6） | DEFAULT_SHELL_OPACITY=0.4 / semi 档位 transparent+depthWrite:false / 连续 opacity 覆盖 / 真空 opacity 0 / 拉满 opaque / 无 mode 默认 opaque | 修复 1 外壳默认半透明 spec |
| `dualOpacity.test.ts`（7） | 默认双滑杆值 / 两滑杆独立（改壳不动体积、改体积不动壳）/ 可叠加 / 拉满 opaque / 拉 0 全透明 / 越界钳制 | 修复 2 双滑杆状态派生 |
| `framingBox.test.ts`（8） | 阈值常量 0.25 / 外壳≫体积→体积为主 / 无外壳→体积 / 外壳⊆体积→并集 / 可比→并集 / 阈值边界 24% vs 25% / 中心重合不回归 / 真实文件场景 | 修复 3 取景纯函数 |
| `volumeLayer.test.ts`（6） | worldBoxFromEdges=真实 grid_bounds / dims=(nk,nj,ni) / 4 体素→RGBA 16 / 盒场景变换 / 外壳≫体积取景 target=体积中心 / §7.3 共享 offset 不变量 | 修复 4 真实文件体积层链路 |

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 28 文件 / **233 用例全绿**（206 基线零回归 + 新增 27） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

- 未改后端（app/、gui/backend 零触碰）；未改契约 / JSON key / meshtal 数据；未装任何依赖；未 commit（等 PM 统一提交）。
- simplify 单趟已跑（boxMin/boxMax 复用 applyOffset；`clamp01` 全库无既有工具，保留新建）。

---

# P0 根因修复：体积层真实渲染从未生效（2026-08-15，PM 实测未闭环后真实复现）

> 用户实测：4 症状修复后**外壳半透明已生效，但体积层（云雾/着色体素）完全没显示**，画面几乎全透明只剩一个小栅元。此前的 seam 测试只验证纯函数/数据维度，未验证 WebGL2 真实渲染。

## 真实复现（零新依赖，本机 Edge headless + SwiftShader）

临时自包含复现页 `gui/repro_volume.html`（已删除）：从 `gui/node_modules/three/build/three.min.js` 加载，复刻 VolumeRenderer 体积盒路径（相同 RAY_MARCH_VERTEX/FRAGMENT + RawShaderMaterial + Data3DTexture(2,2,1) + 四体素 RGBA + BoxGeometry(1,1,1)×scale(2,20,20) + uBoxMin/uBoxMax + computeCameraParams 相机 Z-up）。

Edge headless 截图 + stderr 日志铁证：
```
WebGL: INVALID_OPERATION: useProgram: program not valid
=== VOLUME SHADER PROGRAM INFO === Vertex shader is not compiled.
=== VOLUME SHADER VS INFO === ERROR: 0:3: 'version' : #version directive must occur before anything else
=== VOLUME SHADER FS INFO === ERROR: 0:3: 'version' : #version directive must occur before anything else
```
**shader 程序从未编译成功 → 体积层从未渲染**（外壳 MeshStandardMaterial 正常编译，所以只有外壳可见）。

## 根因（一句话）

three r160 的 WebGLProgram 对 **RawShaderMaterial 会前置 `#define SHADER_TYPE RawShaderMaterial`… 块**再拼用户源码；旧 shader 字符串以 `#version 300 es` 开头 → `#version` 不再处于首位 → GLSL 编译失败 → 程序无效 → 体积层从没画出来。此 bug 自 ea20ad7 引入后从未在真浏览器跑过（契约 §9.3 `#/volume` e2e 一直标注"待人工补跑"），shader 快照测试只锁字符串、不编译，故一路绿灯放行。

## 修复（`gui/src/volume/volumeShader.ts`）

1. `RAY_MARCH_VERTEX` / `RAY_MARCH_FRAGMENT` 去掉首行 `#version 300 es`（shader 字符串内不再含 `#version`）。
2. `buildRayMarchMaterial` 增 `glslVersion: THREE.GLSL3`（= "300 es"）——由 three 在最顶端生成 `#version 300 es`（版本指令必须为首行，随后 three 的 `#define` 块 + 用户 shader 顺序合法）。

## 真实渲染验证（前后截图对比，保存在 D:/code/vol_repro.png / vol_repro_fixed.png）

| 项 | 修复前 `vol_repro.png` | 修复后 `vol_repro_fixed.png` |
| :--- | :--- | :--- |
| stderr shader 日志 | `program not valid` + `#version directive` 报错 | 无（编译通过） |
| 中心 120×120 非背景像素 | **0 / 14400**（纯背景，体积层零渲染） | **14400 / 14400** |
| 画面内容（ASCII 采样） | 全 `.` 背景 | 4 体素色块 **G 绿 / Y 黄 / R 红 / B 蓝** 按 y/z 布局清晰渲染 |

## 回归测试（volumeShader.snapshot.test.ts，+3 用例，防再回归）

- shader 字符串不得含 `#version`（three 前置 #define 块，用户源码首行 #version 必编译失败）——**此守卫能直接抓住本 bug**。
- shader 首行为 `precision` 声明（#version 由 three 经 glslVersion 生成在最顶端）。
- `buildRayMarchMaterial(...).glslVersion === "300 es"`。
- 快照更新 2（fragment/vertex 字符串去掉首行 `#version 300 es`）。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 28 文件 / **236 用例全绿**（233 基线 + 3 新增回归守卫） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

- 临时复现页 `gui/repro_volume.html` 已删除（不留垃圾）；截图证据保留 `D:/code/vol_repro.png`（前）/ `vol_repro_fixed.png`（后）。
- **需要重新打包**：已部署版（HEAD 301d325）仍带本 bug（体积层全程未渲染），修复后需重打包才能让用户看到体积层。
- 未改后端/契约；零新依赖；未 commit。

---

# P0 第二弹：相机未 offset 导致体积层画面错位（2026-08-15，用户实测 v1.7.2）

> 用户实测：`#version` 修复生效，体积层终于能渲染了；但新反馈「摄像机位置不对，渲染出来的位置也不对」——相机视角错位、物体出现在画面错误位置。

## 根因（PM 代码级分析经验证成立）

`VolumeRenderer.alignAndFrame` 用 `translateToCenter` 把外壳/体积盒按 `offset = -unionBox.center` 平移到场景中心（原点），体积盒 position/scale、uBoxMin/uBoxMax 都已适配 offset；**但相机参数仍用未 offset 的 world 坐标**：`computeVolumeCamera(computeFramingBox(shellBox, volumeWorldBox))` 传的是原始 world 盒（用户文件 center=(50,0,100)）→ `camera.target=(50,0,100)`、`position=(71,21,117.5)`。物体已被平移到原点 → **相机对空、物体偏出视锥/极小** = 用户看到的现象。此 bug 同样自 ea20ad7 引入（#version 修复让体积层首次可见才暴露）。

## 修复（`gui/src/volume/VolumeRenderer.ts` + `alignWorld.ts`）

- `alignWorld.ts` 新增纯函数 `applyOffsetToBox(box, offset)`：AABB min/max 同步平移（尺寸不变）。
- `VolumeRenderer.alignAndFrame`：`computeVolumeCamera(computeFramingBox(shellBox, volumeWorldBox))` → `computeVolumeCamera(applyOffsetToBox(framingWorld, offset))`——相机 target/position 用 offset 后场景坐标（联合盒居中时 target≈原点）。near/far 尺寸平移不变，farNear≤1e4 铁律保持。
- 全链路核对（§7）：外壳几何 translate（offset）、体积盒 position/scale（offset）、uBoxMin/uBoxMax（offset）、相机（offset）四者现共享同一 offset。Preview3D 用 `computeCameraParams` + 自身归一化，不受影响（未触碰）。

## 真实渲染验证（headless Edge + SwiftShader，临时 repro_camera.html / repro_camera_noshell.html，已删）

完整场景复刻（外壳 300×200×300 半透明 + 体积盒 2×20×20 四体素 ray-march，用户数据 center(50,0,100)），左右分屏 BEFORE（未 offset 相机）/ AFTER（offset 相机），两种场景（有外壳 / 无外壳）：

| 场景 | BEFORE 体积色块占比 | AFTER 体积色块占比 |
| :--- | :--- | :--- |
| 有外壳 | **0.3%**（相机在 shell 内看向空 world 中心，体积层偏出视锥不可见） | **32.7%**（G/Y/R/B 四色块清晰居中） |
| 无外壳（纯体积盒） | **0.1%**（背景 95.8%） | **32.7%** |

截图证据保留 `D:/code/vol_camera_compare.png`（有外壳 前后对比）/ `vol_camera_noshell.png`（无外壳 前后对比）；数值经 PIL 像素统计 + ASCII 图双确认。

## 回归测试（`gui/test/volume/cameraSceneAlign.test.ts`，+6 用例，先红后绿）

- `applyOffsetToBox` 纯函数（min/max 平移、尺寸不变）。
- 相机 target = 场景盒中心（世界中心 + offset）；联合盒居中时 target ≈ 原点（用户场景 (50,0,100) → 0）。
- position 相对场景中心偏移（viewDist*(0.6,0.6,0.5)）。
- farNear ≤ 1e4 铁律保持。
- 全链路：world framing → applyOffsetToBox → computeVolumeCamera（外壳≫体积时以体积为主）。
- 无外壳场景（shellBox=null）同样对原点。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `cd gui && npx vitest run` | 29 文件 / **242 用例全绿**（236 基线 + 6 新增；colorize 128³ 计时既有 flaky 负载偶发，隔离跑 10/10 通过，非回归） |
| `cd gui && npx tsc --noEmit` | EXIT 0 |
| `cd gui && npm run build` | EXIT 0（仅既有 chunk 体积警告） |

- 临时复现页已删（不留垃圾）；截图证据保留 `D:/code/vol_camera_compare.png` / `vol_camera_noshell.png`。
- **需要重新打包**：v1.7.2（HEAD 135b1a1）仍带此相机错位 bug。
- 未改后端/契约；零新依赖；未 commit。

## 取景盒不相交修复（2026-08-15，用户实测「体积彩色数据层位置偏/错位」批）

**根因**：`computeFramingBox` 只看体积/并集尺寸比。用户真实场景——meshtal 网格在
(50,0,100)（围 F5 点探测器）而模型钨板在原点，两盒**空间不相交**；比例 20/112=0.18<0.25
→ 以体积盒取景 → 模型被整个挤出屏幕，用户只看到一个"浮在一边"的彩色块，观感=体积层错位。

**修复**（`gui/src/volume/alignWorld.ts`）：
- 新增纯函数 `boxesOverlap(a, b)`（任一轴 min≥max 或 max≤min 即分离）。
- `computeFramingBox` 前置分支：外壳与体积盒不相交 → 返回并集（两者都可见，
  由 A1.2 不匹配横幅同步解释"网格与模型不在一起"）；其余行为逐字节不变。
- 共享归一化 offset 仍按并集（§7.2 对齐不变量不变），仅取景受影响。

测试（先红后绿）：`gui/test/volume/framingBox.test.ts` +1
（真实场景数值：shell rpp [-1,1]×[-1,1]×[0,1] + volume [49,51]×[-10,10]×[90,110]
不相交 → 并集 [-1,-10,0..51,10,110]），先红后绿；既有 8 用例零回归。

## 验证结果

| 项 | 结果 |
| :--- | :--- |
| `vitest run` | 31 文件 / **248 用例全绿**（242 基线 + framing 不相交 1 + 诊断期探针已删） |
| `npx tsc --noEmit` | EXIT 0 |
| `vite build` | EXIT 0（仅既有 chunk 体积警告） |

- 配套后端修复见 docs/backend-changes.md §O（A1.2 match 恒 null 契约缺口）。
- 版本号不提升（bug 修复批恒 1.7.1）；零新依赖；未 commit。

## 体积透明度图层级语义修复（2026-08-15，用户实测「大网格调低透明度没用」）

**根因**：shader 把 `uOpacity` 乘在**每采样步** alpha 上（`a = col.a * uOpacity`）。±2000 全域
大网格光线路程 256 步、每步都有非零通量 → 累积 alpha = 1-(1-a)^256 必然饱和，
滑杆再低也近乎不透明 →「看不到体积内部/模型」。

**修复**（`gui/src/volume/volumeShader.ts` RAY_MARCH_FRAGMENT）：
- `uOpacity` 改为**图层级**：只乘最终 alpha（`fragColor = vec4(acc.rgb, acc.a * uOpacity)`），
  每采样步用原 alpha（`a = col.a`）。uOpacity=1 行为逐字节不变；拉到 30% 即可看穿体积见外壳。
- 测试（先红后绿）：volumeShader.snapshot.test.ts +1
  `体积透明度为图层级：uOpacity 只乘最终 alpha，不乘每采样步`（断言含新合成式、且不含 `col.a * uOpacity`）
  + 快照更新 1。**vitest 244/0** + tsc/build EXIT 0。
- 配套使用提示：0 通量体素被涂蓝（整块蓝）属色阶下限=0 的默认行为；在高级设置把
  「色阶下限」调到 ~1e-7 即让零通量体素全透明，只剩光束区域与外壳。
- 仅前端改动；已重打包部署（exe 22:45:54，bundle index-CTAsPTG-.js 嵌入确认）。

## 自适应色阶下限（数量级自适应，2026-08-15，用户反馈）

**背景**：±2000 全域网格（20×20×10，4000 体素中 3576 个精确 0）默认把零通量背景
涂成蓝色挡住模型。第一版规则 `max*1e-6` 是固定 6 个数量级偏移，用户要求"数量级自适应"。

**修复**（`gui/src/volume/colorize.ts` + `VolumeRenderer.ts` + `ResultWindow.tsx`）：
- 新增纯函数 `defaultDisplayMin(sr, minPositive?)`：数据最小值恰为 0 时，
  阈值 = `sqrt(minPositive * max)`（**log10 空间几何中点**，数量级自适应，
  把接近 0 的噪声尾与真实信号分开）；无 minPositive 时保守兜底 `max*1e-6`；
  最小值 >0 保持数据最小值（既有自适应行为）。
- 新增纯函数 `minPositiveOfBytes(bytes, sr)`：从纹理 u8（后端线性归一化）重建最小非零正值。
- `ResultWindow` 首帧取到纹理后：`dm = defaultDisplayMin(sr, minPositiveOfBytes(...))` →
  `setColorRange({min: dm})`（色阶输入框显示与实际阈值一致）→ `createVolumeRenderer({initialDisplayMin: dm})`；
  `VolumeRenderer` 用 `opts.initialDisplayMin ?? defaultDisplayMin(sr)`（缺省兜底）。
- 用户数据实测：u8 最小非零≈7.38e-8 → 阈值 sqrt(7.38e-8×1.88e-5)≈1.18e-6 →
  只显示 u8≥16 的光束核心，零背景全透明；仍可手动覆盖。
- 测试（先红后绿）：colorize.test.ts +7（sqrt 规则 / 兜底 / min>0 / 退化 / 负 min /
  minPositiveOfBytes 线性+偏移 / 全零 undefined），**vitest 252 用例**（唯一偶发红=
  colorize 128³ 计时既有 flaky 负载 65ms，隔离 18/18 全绿）+ tsc/build EXIT 0。
- 已重打包部署（exe 23:00:22，bundle index-DbM58sDm.js 嵌入确认）。

## 体积透明度深度剥除（2026-08-15，用户需求「拉低时外层先透明、内层慢慢跟」）

**设计**（`gui/src/volume/volumeShader.ts` RAY_MARCH_FRAGMENT）：
- `peel = (1 - uOpacity) * 0.5`：滑杆越低，每条光线靠近视线外侧的 peel 段越大（最大剥到一半深）。
- peel 段内每采样系数 `m = k²`（k = df/peel 二次曲线）→ **外层先平滑淡出**；
  内层（df ≥ peel）完整采样 → **内层保持**；整体再乘图层级透明度 `uOpacity` → **内层慢慢跟着变淡**。
- `uOpacity=1` → peel=0、m=1，与全不透明行为逐字节一致（零回归）。
- 配合自适应色阶下限：零通量背景透明后，"剥壳"作用在光束核心的外侧面上，
  中等滑杆值即可看穿外壳看内部结构 + 背后的模型外壳。
- 测试：volumeShader.snapshot.test.ts +1（深度剥除守卫：peel 公式 / m=k² / col.a*m）
  + 快照更新 1；**vitest 253/253** + tsc/build EXIT 0。
- 已重打包部署（exe 23:11:24，bundle index-ZwgTVVaq.js 嵌入确认）。

## 色条图例双柄滑杆（2026-08-15，用户需求「色阶上加两个拉动按钮调控显示/不显示」）

**改动**（`gui/src/volume/ColorLegend.tsx` + `VolumeControlPanel.tsx`）：
- ColorLegend 新增可选 props：`scalarMin`/`scalarMax`（数据范围，把手定位基准）+
  `onRangeChange(min,max)`；提供后色条变成**双柄滑杆**：
  - **左柄 = 色阶下限（显示阈值）**：拖低/拖高决定"低于该值的颜色不显示"；
  - **右柄 = 色阶上限**：决定色带映射上限；
  - 点击色条任意处自动吸附最近的柄开始拖动；把手位置按数据范围**线性映射**
    （与 colorizeScalar 线性映射一致）；两端数值标签随拖动实时更新。
- VolumeControlPanel 把 scalarMin/scalarMax/onColorRangeChange 透传给 ColorLegend
  （与「高级设置」里的色阶上下限数字输入共享同一状态，拖滑杆=改数字输入，双向同步）。
- 纯函数 `rangeThumbPercent`（数值→百分比，钳 [0,1]，span≤0 兜底）+
  `rangeValueFromPercent`（百分比→数值）导出，可测。
- 测试：ColorLegend.test.ts +5（双柄渲染守卫 / 线性映射 / 钳位 / 零范围 / 往返一致）；
  **vitest 258/258** + tsc/build EXIT 0。
- 已重打包部署（bundle index-D27x-vPy.js 嵌入确认）。

## 色阶调节交互改版（2026-08-15 深夜，用户反馈修正）

**① 双柄叠层滑杆移除**（用户实测：手动改数字上下限后拖动吸附逻辑诡异）：
- ColorLegend 恢复为**纯展示**组件（删除 rangeThumbPercent/rangeValueFromPercent/双柄交互），
  上下限改由 VolumeControlPanel 中图例下方的**两条独立 range 滑杆**控制——
  「下限」滑杆=显示阈值（低于不显示），「上限」滑杆=色阶上限，各管一个、互不吸附，
  右侧实时显示数值（formatLegendValue）；与「高级设置」数字输入共享同一状态双向同步。
- 测试：ColorLegend.test.ts 恢复展示守卫（legendTicks/formatLegendValue/SSR 渲染）。

**② 自适应色阶下限规则修正**（用户实测「体素只显示一个面」）：
- 根因 = 网格体素 200×200×400cm、光束约 200cm 粗 → 光束只占 1 体素宽；叠加
  sqrt(minPositive×max) 阈值把低值光晕也切掉 → 只剩细蓝柱。
- 规则改为 **minPositive × 0.5**（只隐精确 0 背景，正结构全保留；纹理是线性 u8，
  比噪声小的值本就量化为 0，无需阈值切噪声）；兜底 max*1e-6、min>0 保持 min 不变。
- 测试：colorize.test.ts 更新（minPositive*0.5 断言），**vitest 253/253** + tsc/build EXIT 0。
- 已重打包部署（bundle index-DzFV9Bgk.js 嵌入确认）。

## PTRAC 粒子径迹可视化前端（2026-08-16，契约 ptrac-visualization.md v2）

- 新建 `gui/src/ptrac/`：`trackColors.ts`（三色 n=#3b82f6/p=#ef4444/e=#eab308、其余灰，能量 HSL lightness 深浅插值）、`decimateTracks.ts`（均匀抽稀保首尾 + `sampleTracks` 密度抽样 1/1…1/10000）、`ptracState.ts`（表单状态 + 卡体 round-trip）、`PtracRenderer.ts`（外壳 STL + LineSegments 顶点色=类型×能量 + alignWorld 归一化 offset + OrbitControls）、`PtracWindow.tsx`（独立窗：统计/粒子三勾选/能量图例/透明度滑杆/密度抽样滑杆/NPS 单径迹高亮/外壳开关）、`PtracForm.tsx`（计数页表单：FILE/WRITE/MAX/TYPE/NPS/CELL/SURFACE 平铺 + VALUE/EVENT 高级折叠）、`openPtracWindow.ts`（桥 + 非 Tauri fallback #/ptrac）。
- 接线：`utils/api.ts`（ptracParse + 类型）、`utils/windows.ts`（KEY_PTRAC 桥）、`main.rs`（open_ptrac_window，label ptrac「3D 径迹」1300×820）、`App.tsx`（#/ptrac 路由 + generate 载荷 tally.ptrac）、`OutputTab.tsx`（粒子径迹 PTRAC 小节）、`TallyTab.tsx`（挂 PtracForm）。
- 测试：`gui/test/ptrac/` 4 文件（trackColors 9 + decimateTracks 11 + ptracState 14 + PtracWindow 1）+ windowRouteConsistency 扩展；**vitest 290 绿**（唯一 flaky=colorize 128³ 计时，隔离绿）+ tsc/build EXIT 0。

## 侧边栏版本号显示（2026-08-16，用户需求）

- `Sidebar.tsx` 悬停展开时应用图标右侧显示 `v{package.json 版本}`（单一来源，与打包四处版本同步）；`gui/test/sidebarVersion.test.tsx` +2。

## 材料导入所见即所得：数据层剥 ZAID 库后缀（2026-08-16，用户规则"丢后缀是对的，除非手填"）
- 问题：导入后材料表单显示 元素+质量数（无后缀），但 deck 数据里 MaterialRow.zaid 仍带 .50d/.40c → 生成输出带后缀 → 所见非所得。
- 修法（MaterialEditDialog.tsx）：新增纯函数 stripZaidSuffix（截到第一个 "." 前）+ 
ormalizeImportedMaterials（核素行 zaid 剥后缀，raw 行原样，rows/nuclides 双键同步）；App.tsx importInpText 导入映射处套用（文件对话框/拖放/粘贴三条路径同一点收敛）。
- 规则固化：表单只表示 元素+质量数；手填截面库走材料卡「其他」框 nlib=（现状即正确，不新增后缀输入框）。后端解析器不动（引擎保真不变）。
- 测试：gui/test/zaidSplit.test.ts +5（stripZaidSuffix 2 + normalizeImportedMaterials 3），先红后绿；vitest **298/0** + tsc EXIT 0；当日重打包部署 v1.7.1（仅前端，sidecar 未重打），部署冒烟探活 loaded:true。

## PTRAC 视图退化取景修复（2026-08-16，用户实测 Practice3「一个蓝点 + 拖动围点转」）
- 根因：点源 + PTRAC EVENT=src → 全部事件重合于出生点（数据层，非 bug）；但 computeFramingBox 对零尺寸体积盒比例恒 0<0.25 → 以单点盒取景 → 相机怼点、外壳被剔除、OrbitControls 围点转（渲染层真 bug）。
- 修复：alignWorld.computeFramingBox 退化盒守卫（volMaxDim<=0 → 并集取景）；trackColors 新增 allPointsCoincident 纯函数；PtracWindow 统计区新增重合点橙色提示（建议 EVENT=sur,col 或体源）。
- 测试：framingBox.test.ts +2（单点/单线段退化盒不劫持取景）、trackColors.test.ts +3（allPointsCoincident）；vitest 303/0 + tsc EXIT 0；当日重打包部署 v1.7.1。

## 源卡文本模式生成漏源卡修复（2026-08-19，用户实测「在源卡中键入后，生成时漏掉源卡」）

- 根因（两处叠加）：① App.tsx handleGenerate 构造 `raw_overrides` 载荷的循环只遍历 `["materials","cells","tally"]`，漏掉 `sdef`；② SourceTab 的「文本模式」从未置 `deck.textMode.sdef`——即使把 sdef 加进循环，也会被 `tm[sec] && raw[sec]` 门控挡掉。后端 `generate_inp_from_deck(deck, raw_overrides)` 收到空 overrides 后走结构化源分支（空 sources）→ `_generate_sdef([])` 返回空 → 生成的 INP 没有源卡。
- 修复：
  - 新增 `gui/src/utils/rawOverrides.ts`：`buildRawOverrides` 纯函数 + `RAW_OVERRIDE_SECTIONS`（含 sdef），App.tsx 改调（单一事实来源，不再内联）。
  - `SourceTab.tsx`：进入源卡文本模式置 `textMode.sdef=true`（工作区恢复后据此回显文本模式）；切回表单（含「← 返回表单」）清 `rawOverrides.sdef` + `textMode.sdef=false`。
  - `DeckContext.tsx`：textMode key 注释补 sdef。
- 回归测试：`gui/test/rawOverrides.test.ts` 3 用例先红后绿（textMode.sdef + rawOverrides.sdef → 载荷带 sdef 原文；非文本模式不带 sdef；materials/cells/tally 原有行为不回归）。
- 验收：全量 pytest **512/0**；vitest **337/0**（已知 flaky colorize 128³ 计时单跑 18/18 绿）；tsc EXIT 0。未 commit。

## 输出页解析/绘图/导出 CSV 修复（2026-08-19，用户实测「输出里解析按钮、绘图/导出CSV按钮」）

- **解析按钮**：原实现「点解析 → 重新打开文件选择器」，不解析已显示的文件；改为保存所选 File，解析按钮直接对当前文件重新解析（未选文件才弹选择器），选择文件后立即解析。
- **绘图按钮**：原为 alert 占位（"建议使用 Excel/Matplotlib"）；新增真实 SVG 折线图弹窗——`gui/src/utils/tallyChart.ts` 纯函数 `buildFluxChartSvg`（无图表依赖，折线+数据点+1σ 误差棒+网格，通量跨 >100 倍自动对数 y 轴），OutputTab 弹窗渲染。
- **导出 CSV**：加 UTF-8 BOM（Excel 直接打开不乱码）。
- **本地兜底解析器**：`utils/outputParser.ts` 重构——tally 头正则容错、支持 MCNP6.1 紧凑布局（cell 行后两列 flux/error）、energy 表头+total 行布局、tally type 提取。
- 测试：`gui/test/outputParser.test.ts` +2、`gui/test/tallyChart.test.ts` +3；vitest **325/0** + tsc EXIT 0。

> 追加：本地兜底解析器数据块标记泛化为 `(cell|surface|detector) N`（F1/F2/F4/F5/F7/F8 等），`outputParser.test.ts` +2（F1 surface / F5 detector），vitest **327/0**。
