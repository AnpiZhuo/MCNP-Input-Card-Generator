# 格阵 fill 三阶段（数据层 / UI 画布 / 3D 预览）最终总验收质量报告

> ⚠️ **历史报告更正注记（2026-09-10，文档债 TD-29 修复）**：本报告「代码抽查」行（第 7 项）写的 `hex_center` 老式 `x=col·pitch+(row%2)·pitch/2, y=row·pitch·√3/2` 是**旧式**，**与 2026-08-25 交叉验证后的权威公式相差 30° 旋转**；**权威 = `x=col*pitch+row*pitch/2, y=row*pitch*√3/2`**（`gui/src/utils/lattice.ts:130-137` ↔ `app/lattice.py:604-616`）。当次"逐字一致"的判定在当时成立（双端一致地写着旧式），历史结论不改。

- **审查人**：测试（独立审查方，非开发自报）
- **日期**：2026-08-24
- **审查方式**：只读代码核验 + 实际独立复跑测试 + 后端 API 直验（不依赖开发自报，未启动 Tauri GUI）
- **验收依据**：`C:\Users\13789\.claude\plans\fill-cell-lat-0-u-fill-cell-u-u-u-u-u-3-fluffy-lampson.md`「验证（端到端）」节 + 三阶段「验收」节
- **重点**：阶段3（3D 预览 universe 实例化）+ 全链路总验收；阶段1/2 复核
- **复核既有报告**：`docs/qa-report.md`（阶段1，632/0）、`docs/qa-report-phase2.md`（阶段2，651/0 + 契约闸门 12/12）

---

## 一、三阶段验收项清单（全部独立复跑 / 直验）

### 阶段3（3D 预览 universe 实例化）

| # | 验收项 | 预期 | 独立实测 | 结果 |
| :-- | :--- | :--- | :--- | :--- |
| 1 | **pytest 全绿**（全仓 `python -m pytest tests/ -q`） | 673 passed / 0 failed | **673 passed / 0 failed**（25.17s） | ✅ |
| 2 | **vitest 全绿**（gui/ `npx vitest run`） | 466 passed / 0 failed / **无 skip**（skip 应消除） | **465 passed / 1 skipped** | ❌ skip 未消除（见问题2） |
| 3 | **tsc** `npx tsc --noEmit` | EXIT 0 | **EXIT 0** | ✅ |
| 4 | **契约闸门** `tests/integration/test_api_contract.py`（真实 HTTP） | HTTP 全过（5001 已清占用） | **14 passed**（validate-lattice-surfaces / lattice-extent / preview-lattice shape 全部真实 HTTP 通过） | ✅ |
| 5 | **跨语言 golden** `latticeGolden.json` positions/嵌套段 | Python 与 TS 读同一 JSON 逐位一致 | Python 侧 **3/3 PASSED 未 skip**（positions / nested / validate）；**TS 侧 golden 用例仍 skip**（见问题2） | ❌ TS 侧未消费 |
| 6 | **嵌套 fill 递归** | BEAVRS 2 层嵌套+叶级；NESTED+FLAT 双形态；depth/too_many/detail 降级 | BEAVRS parse=16 个格阵 cell、preview-lattice tree 实测 depth 1→2→叶级；`compose_lattice_tree` 单元测试嵌套 10 叶双形态、depth_limit、too_many、常量（MAX_LATTICE_DEPTH=8 / MAX_TOTAL_INSTANCES=500000 / DETAIL_MAX_INSTANCES=20000）全过 | ✅ |
| 7 | **代码抽查** | hex_center 逐字一致；render:false→skip；fill_grid 非空→skip；cells_by_num 保留；独立缓存键 | 后端 `hex_center`（x=col·pitch+(row%2)·pitch/2，y=row·pitch·√3/2）与前端 `lattice.ts:124-129` **逐字一致**；`build_cells_data` render:false→skip（api_server.py:305-306）、has_fill_grid→skip（:307-308）、cells_by_num 保留（:300）；`_PREVIEW_CACHE_LATTICE = PreviewCache(max_entries=2)` 独立实例（:87），fingerprint extra 含 u/cellNum/pitch/height（:520-523） | ✅ |

### 端到端（plan「验证」节第3项，后端 API 直验，模拟 GUI 无法项）

| # | 验收项 | 预期 | 独立实测 | 结果 |
| :-- | :--- | :--- | :--- | :--- |
| 1 | 17×17 夹具 parse | fill_grid 有值、surface_expr 干净 | `fill_grid` dims=[17,17,1]，surface_expr=`'50 -51 52 -53'`（无范围串污染），warnings=[] | ✅ |
| 2 | `POST /api/preview-lattice`（17×17） | positions=289、leafInstances 合理、detailViable=true、universes 去重 STL | positions **=289**、position 键全、leafInstances=1133、detailViable=**true**、limit=ok、universes u 集合=**3**（去重：u1={1,2,3,4} u2={5,6,7} u3={8..12}）、count==leafInstances len | ✅ 结构正确 |
| 2b | 同上次 `preview-lattice` **universes STL 内容** | 非空 STL（真实 pin 几何） | **❌ 全部为空**：u1/u2/u3 每 cell STL raw 仅 84 字节（STL 头 + **0 三角形**）——详见「问题1（致命）」 | ❌ **致命** |
| 3 | `POST /api/preview-lattice`（BEAVRS 全堆芯） | detailViable=false → 默认总览 | **count=28067 > 20000**、detailViable=**false**、limit=ok、tree depth 1→2→叶级 | ✅ |
| 4 | `POST /api/lattice-extent` | 合法 box/hex → ok+extent；非法 → ok=false+msg | rect 合法（x_min=-1, y_max=1, z null）ok=true；hex 合法（x_max≈1.0, y_max≈0.866, z=-0.5..0.5）ok=true；`-10 #11` 非法 → ok=false + extent null + msg | ✅ |
| 5 | R1 闸门 + kitchen_sink R4 | 不回退 | `test_roundtrip.py -k "r1_lattice or r4 or r1_fixed"` **7 passed** | ✅ |

### 阶段1/2 不回退

| # | 验收项 | 独立实测 | 结果 |
| :-- | :--- | :--- | :--- |
| 1 | pytest 全仓（含阶段1/2） | **673/0**（含 R1 不动点、kitchen_sink R4、validate_lattice_surfaces、单值 fill 回归） | ✅ |
| 2 | 单值 fill 回归 `test_core_cells.py -k "vol_pwt or fill"` | **6 passed**（u=1 fill=0 lat=1 零回归） | ✅ |
| 3 | 画布 U 分组/拖拽（vitest） | lattice 26 + LatticeCanvas 5 + universeGroups 6 = **37 passed** | ✅ |
| 4 | 契约闸门后端字段子集校验 | `test_contract_backend_fields_subset_of_models` 通过（api.yaml 含 fill_grid / lattice-extent / preview-lattice） | ✅ |

---

## 二、问题列表（按严重程度排序）

### ❌ 致命（阻塞上线，1 项）

**1. `_build_one_universe` 产出的 universe STL 全空 —— 阶段3 核心「universe 实例化」对圆柱形格元不产出任何几何**
- **现象**：`POST /api/preview-lattice`（17×17）返回的 `lattices[].universes` 中，u1/u2/u3 每个 cell 的 STL base64 解码后 **raw 仅 84 字节（STL 二进制头 + 0 三角形）**。详细模式下燃料棒/导向管/仪表管均无真实几何。
- **位置**：`gui/backend/api_server.py::_build_one_universe`（487-562 行）。
- **根因（独立复现定位）**：该函数把格元盒裁剪平面追加进 universe cell 的 `surface_expr` 做 **CSG 交集**（如 cell1 → `-1 -61 +62 -63 +64 -65 +66`，61-66 为裁剪盒平面）。FreeCAD/OCC 对「圆柱（C/CZ 半空间）∩ 平行于其轴的平面（PX/PY）」的布尔 common **恒返回空**：
  - 圆柱 `-1` + 2×PZ（垂直轴）→ 正常（4884B, 96 三角形）
  - 圆柱 `-1` + 2×PX（平行轴）→ **空**（84B, 0 三角形）
  - 圆柱 `-1` + 6×盒平面 → **空**；有限圆柱（带 z 界）+ PX/PY → 仍 **空**
  - 纯 box `2 -3 4 -5 6 -7` + 盒平面 → 正常（684B, 12 三角形）
- **对照证明（非环境问题）**：现有 `POST /api/preview-3d` 对同一 17×17 deck 的 12 个 universe cell **全部产出非空 STL**（cell1=4884B/96 三角，cell6=14884B/296 三角）——preview-3d 走 worker 的 **post-hoc 全局 bound 盒裁剪（solid-solid boolean）**，未把裁剪平面塞进 cell 表达式。
- **影响**：阶段3 交付目标「格阵以真实 pin 几何呈现（每 universe 一份 STL，按 fill 位置前端实例化）」在 detailViable=true 的常见场景（17×17 PWR 燃料组件）**完全失效**——详细 3D 预览不渲染任何真实 pin 几何（空 STL 经 STLLoader 解析为空网格/或解码失败回退 1×1×1 占位盒）。BEAVRS 等默认「色块总览」模式（不依赖 STL）不受此影响。
- **修复方向（归属后端）**：不要在 cell 表达式里追加裁剪平面做 CSG 交集；改为复用 preview-3d 的 solid-solid 盒裁剪（把格元盒作为 bound 传 worker / 构建后按格元盒 cut），或对裁剪失败格元降级色块兜底。

### ⚠️ 严重（建议修复后上线，1 项）

**2. vitest 仍有 1 skip（PM 期望「466/0 无 skip」未达成）；TS 侧未消费阶段3 positions/nested golden**
- **现象**：`npx vitest run` = **465 passed / 1 skipped**。`latticeInstances.test.ts` 的「跨语言 golden positions/nested」用例（`composeNestedPositions 对 golden compose 输入产出一致 FLAT 叶`）**仍被 skip**，即使后端已产出 golden。
- **位置**：`gui/test/latticeInstances.test.ts:278-298`。
- **根因**：测试读取 `(golden as any).positions` 上的 `compose/input/node` 与 `leafInstances` 键，但 golden JSON（`gui/src/utils/__golden__/latticeGolden.json`）的 `positions` 是**数组**（id/lat/dims/extent/trclDeg/expected），`nested` 段键名为 `outerLat/innerLat/universeCells/leafCount/leaves` → `hasGolden=false` **恒成立** → 用例恒 skip。
- **影响**：PM 验收项「TS latticeInstances.test.ts 读同一 JSON 断言逐位一致」的 **TS 侧未生效**（dead test）；阶段3 跨语言「逐位一致」只靠 Python 单侧（3/3 PASSED）锁定。16 个 inline 用例已独立覆盖 rect/hex 位置、TRCL90、总览、嵌套 10 叶绝对坐标，但未与权威 golden JSON 交叉断言。
- **修复方向（归属前端）**：把 golden 的 `positions`/`nested` 段转成 TS `LatticeComposeNode` 可消费的 `compose` 输入（或直接断言 `nested.leaves` 绝对坐标），使 `hasGolden` 为真并真正跑起来，消除 skip。

### 💡 建议（2 项，不阻塞）

1. **`build_cells_data` 的 render:false→skip / fill_grid→skip 无直接测试覆盖**：代码抽查正确（api_server.py:305-308），但因「测试不得 import gui.backend.api_server」的既有约束，无单测锁定。建议提取纯函数或经契约闸门加覆盖。
2. **（跟随致命问题）** `_build_one_universe` 裁剪失败时应显式降级（返回可渲染占位或走总览），而非静默产出 0 三角形 STL——当前前端拿到 84 字节空 STL 无法自愈。

---

## 三、测试执行结果汇总（全部独立复跑）

| 门禁 | 命令 | 结果 |
| :--- | :--- | :--- |
| pytest 全仓 | `python -m pytest tests/ -q`（300s 超时） | **673 passed / 0 failed**（25.17s） |
| vitest 全仓 | `cd gui && npx vitest run`（300s 超时） | **465 passed / 1 skipped**（61 文件，5.87s） |
| tsc | `cd gui && npx tsc --noEmit`（240s 超时） | **EXIT 0** |
| 契约闸门 | `python -m pytest tests/integration/test_api_contract.py -v` | **14 passed**（含真实 HTTP：validate-lattice-surfaces / lattice-extent / preview-lattice） |
| Python golden 跨语言 | `test_lattice.py::{positions,nested,validate}_golden_cross_language` | **3 passed（未 skip）** |
| R1/R4 闸门 | `test_roundtrip.py -k "r1_lattice or r4 or r1_fixed"` | **7 passed** |
| 阶段1 回归 | `test_core_cells.py -k "vol_pwt or fill"` | **6 passed** |
| 阶段2 画布回归 | vitest lattice 26 + LatticeCanvas 5 + universeGroups 6 | **37 passed** |
| 端到端 API 直验 | 独立脚本（起 api_server 子进程，真实 HTTP） | **20/20 PASS**（17×17 / BEAVRS / lattice-extent 结构全部正确） |
| universe STL 内容直验 | 独立解码 | **❌ 全部空**（84B / 0 三角形）——致命问题 |
| FreeCAD 对照直验 | preview-3d vs preview-lattice | preview-3d **非空**（4884B+），preview-lattice **空** —— 证实为 lattice clip 实现缺陷 |

**「未验证」项**：无（FreeCAD 在本机可用，STL 内容已实际解码核验）。未启动 Tauri GUI（按指令用后端 API 直验）。

---

## 四、整体评估结论

**三阶段总验收：未通过（存在 1 项致命问题，阻塞上线）。**

- **门禁**：pytest 673/0 ✅、tsc EXIT 0 ✅、契约闸门 14/14 ✅、端到端结构 20/20 ✅、阶段1/2 全不回退 ✅、Python 侧 golden 3/3 ✅。
- **致命（1 项，后端）**：`_build_one_universe` 的「格元盒裁剪构建 universe STL」对圆柱形格元（最常见燃料棒/导向管/仪表管）产空 STL —— 阶段3 核心交付「真实 pin 几何呈现」失效。BEAVRS 默认总览模式不受影响，但 17×17 这类 detailViable=true 的详细模式渲染不出任何真实几何。
- **严重（1 项，前端测试代码）**：vitest 仍有 1 skip，TS 侧跨语言 golden（positions/nested）用例 dead，PM 期望的「466/0 无 skip」未达成。
- **建议打回后端修复致命问题**（`gui/backend/api_server.py::_build_one_universe` 裁剪方式改 solid-solid 盒裁剪或降级兜底）；前端严重问题（`gui/test/latticeInstances.test.ts` golden 用例结构）建议同批修复。修复后重新审查。

**归属**：致命问题归后端（阶段3 `_build_one_universe`）；严重问题归前端（`latticeInstances.test.ts`）。
