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
