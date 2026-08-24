# 格阵 fill 三阶段 —— 修复后最终复验质量报告（放行评审）

- **审查人**：测试（独立审查方，不依赖开发自报）
- **日期**：2026-08-24
- **审查方式**：只读代码核验 + 全部门禁独立复跑 + 用户指定路径后端 API 直验（未启动 Tauri GUI，GUI 交互项已注明以 API 直验替代）
- **背景**：前次验收（docs/qa-report-total.md）打回 2 项——**致命·后端** `_build_one_universe` 空 STL、**严重·前端** golden 死 skip。本次复验两处修复 + 全量门禁 + 用户指定 E2E。
- **复验 E2E 脚本**：`C:\Users\13789\AppData\Local\Temp\qa_e2e_final.py`（独立起 api_server 子进程，真实 HTTP）

---

## 一、必核复验项清单（全部独立复跑，非开发自报）

| # | 复验项 | 预期 | 独立实测 | 结果 |
| :-- | :--- | :--- | :--- | :--- |
| 1 | **pytest 全仓** `python -m pytest tests/ -q` | 674 passed / 0 failed | **674 passed / 0 failed**（25.00s） | ✅ |
| 2 | **vitest 全仓** `cd gui && npx vitest run` | 466 passed / 0 failed / 无 skip | **61 files / 466 passed / 0 failed / 无 skip**（6.02s） | ✅ |
| 3 | **tsc** `cd gui && npx tsc --noEmit` | EXIT 0 | **EXIT 0** | ✅ |
| 4 | **契约闸门** `tests/integration/test_api_contract.py`（真实 HTTP） | 15/15 含新回归 | **15 passed**（含 `test_http_preview_lattice_universe_stl_nonempty` **PASSED 未 skip**，真实 HTTP，FreeCAD 可用） | ✅ |
| 5 | **嵌套 golden 双端逐位一致** | TS `composeNestedPositions` 真跑断言 FLAT 叶===golden nested.leaves；Python golden/compose 7/7 | TS 侧「跨语言 golden positions/nested/composeCases」用例**真正运行且 PASSED**（latticeInstances.test.ts 17 passed，无 skip）；Python 侧 `test_positions_golden_cross_language` / `test_nested_golden_cross_language` **PASSED 未 skip**（test_lattice.py 53 passed，含 compose 3 用例） | ✅ |
| 6 | **空 STL 修复生效（核心）** `POST /api/preview-lattice`（17×17 示例） | 每 universe cell STL 非空且三角数>0（含圆柱格元）；cell1≈96 三角 | **12 个 universe cell STL 全部非空**，三角形数范围 **[96, 296]**；cell1=**96 三角**（真实 pin 几何，与 preview-3d 基线一致）；empty=NONE | ✅ |
| 6b | beavrs 仍默认总览 | detailViable=false | count=28067 > 20000、**detailViable=false** | ✅ |
| 7 | R1/R4 不回退 | `test_roundtrip.py -k "r1_lattice or r4 or r1_fixed"` | **7 passed** | ✅ |

### 空 STL 修复细节（核心项 6 展开）
`POST /api/preview-lattice`（17×17 PWR 组件示例，含圆柱燃料棒/导向管/仪表管格元）解码 `lattices[].universes` 逐 cell STL：

- u1（燃料棒）：c1=96、c2=204、c3=220、c4=132 三角
- u2（导向管）：c5=140、c6=296、c7=168 三角
- u3（仪表管）：c8=108、c9=236、c10=268、c11=296、c12=168 三角
- **全部 > 0，无 84B/0 三角**（修复前全空）。cell1=96 三角与 preview-3d 基线逐位一致。

修复实现核验（`gui/backend/api_server.py`）：
- `_clip_suffix_and_lines`（349-374）：格元盒合成**单个 RPP 宏体**（`-<num>` 盒内半空间），明确注释「禁止再合成 6 个 PX/PY/PZ 平面」（圆柱∩平行轴平面恒空根因）。
- `_build_one_universe`（516-599）：universe cell `surface_expr` 追加 `-<num>`，worker 内做 **cell solid ∩ RPP 盒实体 solid-solid common**（与 preview-3d bound 同机制）。
- 显式降级：`_stl_triangle_count`（377-390）+ `_build_one_universe` 内 `if _stl_triangle_count(raw)==0: continue`（不产出空 STL，前端对缺失 (u,cellNum) 回退 1×1×1 占位盒）。

前端 golden skip 修复核验（`gui/test/latticeInstances.test.ts`）：
- `hasGolden`（331-337）消费**正确键名**：`positions` 是数组、`nested` 是对象（leafCount/leaves）、`composeCases` 是数组且 `[0].node` 存在 → 恒真。
- golden 用例（339-364）**真跑** `composeNestedPositions(cc.node)`，断言 FLAT 叶===`nested.leaves`（10 叶，集合双向相等，消除死 skip）。
- golden JSON（`gui/src/utils/__golden__/latticeGolden.json`）已含 `composeCases` 段（1 例，node 含 lat/dims/cellSize/cells），与 nested 段同源。

---

## 二、用户指定最终验收手工 E2E 路径

**说明**：本机未启动 Tauri GUI。仓库无自动化 GUI 冒烟手段（既有冒烟均为 sidecar python 直跑 + API），故按指令**用后端 API 直验模拟**该路径，GUI 交互项已明确标注「API 直验替代」。

示例库第二个示例 **「17×17 PWR 组件」**（`gui/public/examples/assembly_17x17_mcnp.i`）：

| # | 验收项 | 验证方式 | 独立实测 | 结果 |
| :-- | :--- | :--- | :--- | :--- |
| ① | 导入后 fill_grid 有值、surface_expr 干净 | API `parse-inp`（GUI「示例文件→导入」走同一 parse-inp 管线） | cell20 `fill_grid` len=12837（含 dims=[17,17,1]）；`surface_expr='50 -51 52 -53'`（无范围串污染）；lat=1 / fill='0:16 0:16 0:0' / u=10 | ✅ |
| ② | 格阵 3D 预览「详细」模式渲染真实 pin 几何 | API `preview-lattice`（GUI 详细模式消费同一响应：detailViable + universes base64 → STLLoader 解码 → InstancedMesh） | detailViable=true、positions=289、universes u={1,2,3}，**12 个 STL 全非空（96~296 三角）** —— 空 STL 致命修复生效 | ✅ |
| ③ | 「色块总览」切换正常 | API 信号 + 前端 `isOverview` 单测（`isOverview = overviewUser || detailViable===false || count>20000`） | 17×17：count=1133≤20000 且 detailViable=true → 详细模式渲染真实 pin，用户可勾选总览切换；beavrs：detailViable=false → 自动切总览 | ✅ |
| ④ | 生成 INP 与示例等价 | API `generate` round-trip（parse→gen→parse→gen 字节稳定） | gen len=2708B；**gen1==gen2 字节稳定**；含 `20 0 50 -51 52 -53 IMP:N=1 U=10 LAT=1 FILL=0:16 0:16 0:0` + fill 17 行条目 + cz 0.39218 燃料棒曲面 + kcode/ksrc，与示例结构语义等价 | ✅ |

- beavrs 全堆芯仍走总览：count=28067、detailViable=false（③已覆盖）。
- **E2E 直验合计：17/17 PASS。**

---

## 三、问题列表

**❌ 致命：0 项**
**⚠️ 严重：0 项**
**💡 建议（不阻塞）：0 项**

前次打回 2 项均已修复且被独立复验闭环：
1. ❌致命·后端 `_build_one_universe` 空 STL → 已修复（solid-solid 盒裁剪 + 显式降级），12/12 STL 非空、cell1=96 三角与 preview-3d 基线一致。
2. ⚠️严重·前端 golden 死 skip → 已修复（消费正确键名 + composeCases 段），vitest 466/0 无 skip，TS/Python 双端 golden 逐位锁死。

---

## 四、测试执行结果汇总（全部独立复跑，含硬超时）

| 门禁 | 命令 | 结果 |
| :--- | :--- | :--- |
| pytest 全仓 | `python -m pytest tests/ -q`（420s 超时） | **674 passed / 0 failed**（25.00s） |
| vitest 全仓 | `cd gui && npx vitest run`（420s 超时） | **466 passed / 0 failed / 无 skip**（61 files，6.02s） |
| tsc | `cd gui && npx tsc --noEmit`（240s 超时） | **EXIT 0** |
| 契约闸门 | `python -m pytest tests/integration/test_api_contract.py -v` | **15 passed**（含新回归 universe STL 非空，真实 HTTP，未 skip） |
| Python golden/compose | `tests/unit/test_lattice.py` | **53 passed**（positions/nested golden 未 skip，compose 3 用例全过） |
| TS 跨语言 golden | `cd gui && npx vitest run test/latticeInstances.test.ts`（verbose） | **17 passed**（golden 用例真跑未 skip） |
| R1/R4 闸门 | `test_roundtrip.py -k "r1_lattice or r4 or r1_fixed"` | **7 passed** |
| 端到端 API 直验 | `qa_e2e_final.py`（17×17 + beavrs） | **17/17 PASS** |

**「未验证」项**：Tauri GUI 交互（示例弹窗导入点击、「详细/总览」checkbox 切换、3D 画布交互）——未启动 GUI，按指令以 API 直验替代（同一后端管线 + 前端逻辑已有单测覆盖）。

---

## 五、整体评估结论

**最终复验：全绿，无致命/严重问题，放行统一提交。**

- 两处打回修复均被独立复验闭环：**空 STL 致命修复生效**（17×17 详细模式 12 个 universe cell STL 全部非空，cell1=96 三角与 preview-3d 基线一致）；**golden 双端真正锁死**（vitest 466/0 无 skip，TS/Python 对同一 golden 逐位一致）。
- 全部六项必核复验通过：pytest 674/0、vitest 466/0 无 skip、tsc EXIT 0、契约闸门 15/15、嵌套 golden 双端一致、空 STL 修复生效。
- 用户指定最终验收 E2E 路径 17/17 PASS（API 直验替代 GUI 交互项，已标注）。
- **建议放行统一提交**（工作树当前未 commit，三阶段改动齐备，无阻塞）。
