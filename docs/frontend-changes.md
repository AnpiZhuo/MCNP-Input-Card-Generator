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
