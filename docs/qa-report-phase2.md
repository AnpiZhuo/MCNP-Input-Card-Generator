# 格阵 fill 阶段2（UI 画布）独立验收质量报告

> ⚠️ **历史报告更正注记（2026-09-10，文档债 TD-29 修复）**：本报告验收项 5 引用的 `hexCenter` 公式为**旧式** `x=col·pitch+(row%2)·pitch/2, y=row·pitch·√3/2`，**与 2026-08-25 交叉验证后的权威公式相差 30° 旋转**；**权威 = `x=col*pitch+row*pitch/2, y=row*pitch*√3/2`**（`gui/src/utils/lattice.ts:130-137` ↔ `app/lattice.py:604-616`）。历史验收结论（vitest 449/0、契约闸门 12/12 等）**不改**。

- **审查人**：测试（独立审查方，非开发自报）
- **日期**：2026-08-24
- **审查方式**：只读代码核验 + 实际独立复跑测试（不依赖开发自报）+ 备用端口独立 HTTP 验证
- **验收依据**：`C:\Users\13789\.claude\plans\fill-cell-lat-0-u-fill-cell-u-u-u-u-u-3-fluffy-lampson.md` 阶段2「目标与可验收完成标准」节
- **审查范围**（阶段2）：`gui/src/utils/lattice.ts`（新）、`gui/src/components/LatticeEditDialog.tsx`（新）、`LatticeCanvas.tsx`（新）、`LatticePreview3D.tsx`（新）、`gui/src/three/useThreeCanvas.ts`（新）、`gui/src/three/hexPrism.ts`（新）、`gui/src/utils/universeGroups.ts`（新）、`gui/src/utils/useDragToGroup.ts`（新）、`GeometryTab.tsx`（格阵徽标列/栅格编辑入口/按 U 分组 toggle）、`CellEditDialog.tsx`（格阵字段分组入口）、`app/lattice.py`（validate_lattice_surfaces + MAX_EXPANDED_ENTRIES）、`gui/backend/api_server.py`（新端点）、`docs/contracts/api.yaml`（新端点契约）、跨语言 golden `gui/src/utils/__golden__/latticeGolden.json`（新）
- **阶段1回归核验**：R1 闸门 / kitchen_sink R4 / pytest / vitest / tsc（本报告一并覆盖，见验收项 8）

---

## 一、阶段2「目标与可验收完成标准」对照核验

| # | 阶段2 目标（对照计划节） | 结果 | 独立证据 |
| :-- | :--- | :--- | :--- |
| 1 | 主页面区分「含 fill 的 cell」（格阵徽标列） | ✅ 通过 | `GeometryTab.tsx:655`（普通视图）与 `:455`（U 分组视图）均按 `r.fill_grid` 渲染「格阵」徽标；`fill_grid` 为空不显示 |
| 2 | 「插入栅格编辑」完整流程（LatticeEditDialog 状态机） | ✅ 通过 | 见下「二、状态机核验」 |
| 3 | 矩形 + 六棱柱涂色画布（LatticeCanvas） | ✅ 通过 | 矩形=CSS grid（`LatticeCanvas.tsx:49-76`）；六棱柱=hexGrid 蜂窝环交错（`:78-119`，hexCenter 绝对定位） |
| 4 | 按 U 分组显示 + 拖拽快捷分 U | ✅ 通过 | `universeGroups.ts`（groupByUniverse 数值升序 / raw 不进组）+ `useDragToGroup.ts`（落组头改 u / 落普通行重排）+ GeometryTab「按 U 分组」toggle（`:588`）+ 组头拖拽落点（`:435`） |
| 5 | 子预览窗口（useThreeCanvas + hexPrism + computeCameraParams 线框） | ✅ 通过 | `LatticePreview3D.tsx` 复用 `useThreeCanvas`（WebGL 挂载）+ `buildHexPrism`（pointy-top 六棱柱，外接半径 R=pitch/√3）+ `computeCameraParams`（取景）；跟手重建（dispose 旧 group） |

### 二、LatticeEditDialog 状态机核验（对照计划 6 步）

| 步骤 | 计划要求 | 实现 | 结果 |
| :-- | :--- | :--- | :--- |
| 0 | 选 lat 矩形(lat=1)/六棱柱(lat=2) + 尺寸 | `step===0` 类型与尺寸按钮 + 列/行/环数 | ✅ |
| 1 | 材料锁死 0 + 曲面 textarea（失焦调后端）+ 自动生成平面 | 材料号 readOnly `value="0"`（`:257`）/ 密度 readOnly 空（`:261`）/ 曲面 onBlur→`handleSurfaceBlur`→`validateLatticeSurfaces`（`:120-123`）/「生成平面卡并填表达式」（`:126-138`） | ✅ |
| 2 | 延伸方向 2D（第三轴 0:0）/ 3D（第三轴 0:k） | `step===2` 2D/3D 切换 + 层数 k | ✅ |
| 3 | 宇宙调色板（deck.cells 去重收集 u= → 每宇宙一色） | `step===3` 从 `deckCells` 去重收集（`:85-92`）+ buildUniversePalette + 自定义宇宙号 | ✅ |
| 4 | LatticeCanvas 涂色 + 3D 子预览 | `step===4` LatticeCanvas + LatticePreview3D 并排 | ✅ |
| 5 | 保存：写 fill/lat/fill_grid/surface_expr/mat=0/density=""，cells 反算覆盖 raw | `handleSave`（`:165-186`）：`fill:r.join(" ")`、`lat`、`fill_grid:serializeFillGrid(fg)`、`surfaces:surfaceExpr`、`mat:"0"`、`density:""`、`fg.raw=cellsToRaw(fg)`（cells 反算覆盖 raw） | ✅ |

### 三、必核验收项

| # | 验收项 | 结果 | 独立证据 |
| :-- | :--- | :--- | :--- |
| 1 | **vitest 全绿**（独立复跑） | ✅ 通过 | `npx vitest run` → **449 passed / 0 failed**（60 文件，7.32s）。新增：`lattice.test.ts` 26 / `LatticeCanvas.test.tsx` 5 / `universeGroups.test.ts` 6（=412 基线 + 37）。`LatticeCanvas.test.tsx` 单独复跑 5/5；`lattice.test.ts` 单独复跑 26/26 |
| 2 | **tsc** `npx tsc --noEmit` EXIT 0 | ✅ 通过 | EXIT 0 |
| 3 | **pytest 不回退 + golden 生效** | ✅ 通过 | `python -m pytest tests/parser tests/integration tests/unit -q` → **651 passed / 0 failed / 0 skipped**（23.58s，复跑确认；端口清理后全绿）。golden 断言 `test_validate_lattice_golden_cross_language` **PASSED 未 skip**；validate_lattice_surfaces 用例全过；`MAX_EXPANDED_ENTRIES` 封顶 3 用例全过 |
| 4 | **后端新端点契约**（api.yaml + 契约闸门） | ✅ 通过 | api.yaml `POST /api/validate-lattice-surfaces`（operationId=validateLatticeSurfaces，tag geometry，lat enum ['1','2']，响应 `{status:"ok",ok,msg}`）；AST 契约闸门 `test_contract_api_yaml_operation_ids` / `test_contract_api_yaml_no_stale_paths` 通过。HTTP 行为在备用端口独立验证（见验收项 3 备注）：5 场景全 PASS |
| 5 | **跨语言 golden**（Python 与 TS 同读 latticeGolden.json 断言一致） | ✅ 通过 | Python `tests/unit/test_lattice.py::test_validate_lattice_golden_cross_language` 读 `gui/src/utils/__golden__/latticeGolden.json` 的 `validate` 数组，逐例断言 `ok==expectedOk` 且合法例 `msg==""`；TS `gui/test/lattice.test.ts` 同读 golden（rectGrid/hexRingRows/hexCenter/validate），结构 + 非法字符（#/:/(/) → expectedOk 必 false）断言。键名 `surfaceExpr/lat/surfacesText/expectedOk/expectedMsg` 双端逐字一致 |
| 6 | **QA 建议落地** ① MAX_EXPANDED_ENTRIES 上限 ② 画布不匹配提示 | ✅ 通过 | ① `app/lattice.py:35` `MAX_EXPANDED_ENTRIES=1_000_000`；`parse_fill_entries`/`parse_fill_tokens` 补 0 均封顶、截断不抛异常、`raw` 保留简写（用例 `test_parse_entries_nr_cap_*` / `test_parse_tokens_huge_range_pad_capped` 全过）。② `lattice.ts::latticeMismatchMessage` + `LatticeCanvas.tsx:123-127` 渲染非阻塞警告横幅；`LatticeCanvas.test.tsx` 不匹配/匹配两用例覆盖 |
| 7 | **代码抽查**（hexCenter 公式 / 材料锁死 / LatticeCanvas props） | ✅ 通过 | 见「四、代码抽查细节」 |
| 8 | **阶段1 不回退**（R1 闸门 + kitchen_sink R4） | ✅ 通过 | `test_r1_lattice_17x17_fixed_point` / `test_r1_lattice_prob41c_fixed_point` / `test_r1_fixed_point_kitchen_sink` / `test_r4_kitchen_sink_full_roundtrip` 定向复跑 4/4 PASSED；全量 pytest 650 passed 含全部 roundtrip |

### 四、代码抽查细节（验收项 7）

| 检查点 | 结果 | 证据 |
| :--- | :--- | :--- |
| `hexCenter` 公式与架构师契约一致（x=col·pitch+(row%2)·pitch/2，y=row·pitch·√3/2） | ✅ | `lattice.ts:124-129` 逐字一致；golden `hexCenter` 4 例验算通过（如 {col:2,row:1,pitch:2} → x=2·2+1·1=5, y=√3≈1.732）；TS `hexCenter.test` 与 Python 读同 golden |
| LatticeEditDialog 材料锁死 0 | ✅ | 输入框 `value="0" readOnly`（`:257`）；`handleSave` 写 `mat:"0"`、`density:""`（`:173-174`） |
| LatticeCanvas props 与契约一致 | ✅ | `{lat, dims, cells, palette, selectedU, onCellChange(idx,u), disabled?, pitch?}`；契约要求 `{lat,dims,cells,palette,selectedU,onCellChange(idx,u),disabled?}`，仅多一个可选 `pitch`（默认 18，无副作用） |
| `universeGroups.groupHeaderLabel` 文案 `U=n · N 栅元` | ✅ | `universeGroups.ts:45-47`；universeGroups.test.ts:6/6 |
| `useDragToGroup` 落组头改 u / 落普通行重排 | ✅ | `useDragToGroup.ts` + `resolveDrop` 纯函数判定；`universeGroups.test.ts` resolveDrop 两例 |
| `hexPrism` pointy-top 顶点朝 +X、外接半径 R=pitch/√3 | ✅ | `hexPrism.ts:15-48`：0/60/120/180/240/300° 顶点，radius 参数=R；与 hexCenter 蜂窝排布对齐 |
| `LatticePreview3D` 复用 useThreeCanvas + computeCameraParams，跟手重建 | ✅ | `LatticePreview3D.tsx:66-131`：useEffect 依赖 dims/cells/palette 变化 → dispose 旧 group → Box3 求盒 → computeCameraParams 取景 → markDirty |
| golden 键名与 Python 读取逐字一致 | ✅ | golden JSON `validate[].surfaceExpr/lat/surfacesText/expectedOk/expectedMsg`；Python `test_lattice.py:343-348` 读取同键 |

---

## 五、问题列表（按严重程度）

### ❌ 致命（阻塞上线）
**无。**

### ⚠️ 严重（已解决，非代码缺陷）

1. **端口 5001 被旧打包版后端劫持，契约闸门 HTTP 用例曾失败（环境/部署问题，非前后端代码）——已解决**
   - 现象（初跑）：`pytest tests/integration/test_api_contract.py::test_http_validate_lattice_surfaces` FAILED（404 Not Found）。
   - 根因：Windows SO_REUSEADDR 允许多进程同绑 5001。检测到 **PID 15008 = `D:\MCNP\MCNP输入卡生成器\python.exe -u backend/mcnp_bridge.py`**（已部署的旧打包版 sidecar，无阶段2 新端点）正在监听 0.0.0.0:5001；测试起的新 api_server 与旧端并存，请求被劫持到旧端 → 旧端无 `/api/validate-lattice-surfaces` → 404。记忆库 §6「5001 端口劫持」为已知坑。
   - 独立佐证代码正确：在备用端口 5999 启动仓库 `api_server.py` 直测新端点 5 场景（矩形 2D / 六棱柱 8 平面 / 单 RPP 宏体 → ok:true；# 补集 / : 范围 → ok:false）**全部 PASS**，且统一信封 `{status:"ok"}` 正确。
   - **解决**：用户手动关闭旧 sidecar（PID 15008）后端口释放，复跑契约闸门 **12/12 全绿**（EXIT 0），全量 pytest **651 passed / 0 failed / 0 skipped**。端口占用检测加固按 PM 决策本次不做（作为可选防御，不阻塞）。

### 💡 建议（3 项，均不阻塞阶段2）

1. **`LatticeCanvas` 可选 `pitch` prop 超出契约**（`LatticeCanvas.tsx:19`）：契约 props 未列 `pitch`，实现增加默认 18 的可选 prop。无功能影响（阶段3 由 surface_expr 提供真实格距），纯文档/契约对齐项。
2. **LatticeEditDialog 为 6 步状态机（0-5，含保存摘要步骤），计划文案写「5 步状态机」**：计划自身枚举为「选 lat→材料→延伸→调色板→画布→保存」6 项，与实现一致，仅文档措辞（5 步 vs 6 步）偏差，建议计划文档将「5 步」改「6 步」消除歧义。
3. **`estimateLatticeExtent` 六棱柱分支以 pitch=1 估算**（`lattice.ts:271-284`）：阶段2 子预览/范围展示用单位格距可接受；阶段3 需以真实格距覆盖（计划已注明阶段3 由 `lattice_cell_extent` 提供真实格距），此处仅提示后续衔接。

---

## 六、测试执行结果汇总（全部独立复跑）

| 门禁 | 命令 | 结果 |
| :--- | :--- | :--- |
| vitest 全量 | `cd gui && npx vitest run` | **449 passed / 0 failed**（60 文件，7.32s） |
| lattice.test.ts（TS golden 单测） | `npx vitest run test/lattice.test.ts` | 26 passed |
| LatticeCanvas.test.tsx（DOM 画布） | 含于全量 | 5 passed |
| universeGroups.test.ts | 含于全量 | 6 passed |
| tsc | `cd gui && npx tsc --noEmit` | **EXIT 0** |
| pytest（parser/integration/unit） | `python -m pytest tests/parser tests/integration tests/unit -q` | **651 passed / 0 failed / 0 skipped**（23.58s；初跑曾 650/0/1，端口清理后复绿） |
| 契约闸门 test_api_contract.py | `python -m pytest tests/integration/test_api_contract.py -q` | **12/12 passed**（含 `test_http_validate_lattice_surfaces`，端口清理后复绿，EXIT 0） |
| golden 跨语言（Python 侧） | `pytest tests/unit/test_lattice.py::test_validate_lattice_golden_cross_language` | PASSED（**未 skip**，读 golden 生效） |
| 阶段1 R1 闸门 + R4 | `pytest .../test_r1_lattice_17x17_fixed_point .../test_r1_lattice_prob41c_fixed_point .../test_r1_fixed_point_kitchen_sink .../test_r4_kitchen_sink_full_roundtrip` | 4/4 PASSED |
| 新端点独立 HTTP 验证 | 备用端口 5999 起仓库 api_server，urllib POST 5 场景 | 5/5 PASS（信封 status:ok + 合法/非法判定全部正确） |

**关于「未验证」项**：唯一无法在当前环境全绿的门禁是契约闸门 HTTP 用例（端口劫持所致）；已用备用端口独立 HTTP 验证补足对仓库代码正确性的确认。其余各项均已实测，无伪造通过。

---

## 七、整体评估结论

**阶段2（UI 画布）验收通过，无致命问题，全部门禁复绿。**

- 阶段2 五项目标全部达成：格阵徽标列区分 / LatticeEditDialog 6 步流程（材料锁死 0 + 曲面失焦校验 + 自动生成平面 + 延伸方向 + 调色板 + 画布涂色 + 保存写 fill/lat/fill_grid/surface_expr/mat=0/density="" + cells 反算覆盖 raw）/ 矩形+六棱柱涂色画布 / 按 U 分组 + 拖拽分 U / 3D 子预览（useThreeCanvas+hexPrism+computeCameraParams）。
- 必核 8 项独立复跑全部核实：vitest **449/0**、tsc EXIT 0、golden 跨语言**未 skip 且双端一致**、后端新端点契约（api.yaml + AST 闸门 + 契约闸门 **12/12**）、QA 建议两项落地（MAX_EXPANDED_ENTRIES 封顶 + 画布不匹配提示）、hexCenter 公式/材料锁死 0/LatticeCanvas props 与契约一致、阶段1 R1 闸门 + kitchen_sink R4 不回退。
- **1 项严重（环境/部署）已解决**：5001 端口曾遭旧打包版 sidecar 劫持致契约闸门 HTTP 用例 404；用户手动关闭旧 sidecar 后复跑，契约闸门 **12/12 全绿**、全量 pytest **651/0/0**，无残留失败。此问题不归前端/后端业务代码，无需打回。
- 无致命问题，**不放行打回**；阶段2 验收通过，可进入阶段3（3D 预览 universe 实例化）。

**归属说明**：端口占用检测加固按 PM 决策本次不做（可选防御，不阻塞）；建议项 1/2/3 分别归前端（契约对齐/文档措辞）与阶段3 衔接，均不阻塞。
