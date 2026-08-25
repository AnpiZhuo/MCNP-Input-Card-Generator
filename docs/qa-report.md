# QA 报告 — 格阵 fill 15 项用户实测反馈修复（Wave 3 全量门禁复跑 + 15 项核验）

> 审查人：测试（独立复跑，不轻信实现 agent 汇报）
> 日期：2026-08-25
> 图纸依据：`docs/contracts/lattice-fix15-design.md`（§1 逐项 / §2 L1-L9 跨语言锁死 / §6 测试清单）
> 基准 commit：2e38934（三阶段），本批为工作树修复（未 commit）
> 结论：**全部门禁绿，15 项全部落地，无致命/严重问题，可交用户浏览器复验。**
>
> **✅ Wave 3b 修复已重验并定稿（2026-08-25）**：用户浏览器复验发现的 `format_fill_cards` 格式缺陷
> （FILL 续行按字符宽度打包、未按 MCNP 规范每行一个 j 行）已由 backend 修复（`app/lattice.py`
> format_fill_cards 改 **cells 结构化展开优先、按 dims[0] 每 j 行分组**，raw 仅 cells 空/截断兜底）。
> 测试已独立重验：全量 pytest **706/0/0**（基线 703 + 新增 3 个 format_fill_cards 用例，不回退反增）、
> R1 五夹具 parse→gen→parse 字节全等、kitchen_sink R4 不回退、17×17 FILL 每行恰 17 条目（dims[0]）
> 独立核验通过。详见 §8。

---

## 1. 审查范围概述

对「MCNP 输入卡生成器」格阵 fill 三阶段（commit 2e38934）基础上的 15 项用户实测反馈修复做全量门禁独立复跑与逐项核验。

- 后端改动面：`app/lattice.py`（+225）、`gui/backend/api_server.py`（+126）、`app/generator/{banners,inp_generator}.py`、`app/generator/parsers/core.py`、`app/models.py`、`docs/contracts/api.yaml`（+11）。
- 前端改动面：`gui/src/utils/lattice.ts`（+281）、`gui/src/components/{LatticeEditDialog,LatticeCanvas,LatticePreview3D,Preview3D,Preview3DLattice,GeometryTab}.tsx`、`gui/src/utils/{universeGroups,DeckContext}.tsx`、`gui/src/three/latticeInstances.ts`、新增 `MacrobodyPreview.tsx`、`disposeObject.ts`。
- golden：`gui/src/utils/__golden__/latticeGolden.json`（+113，新增 dirCounts/macrobody/rhpMacro/collectFillUniverses/compressRaw/cycle/assembly 段 + 重算 hexCenter/positions.hex）。
- 测试新增：`tests/unit/test_build_cells_data.py`、`tests/parser/test_universe_group_comment.py`、`gui/test/{latticeEditDialog,geometryGroupDrag,groupHeaderEdit,preview3dLatticeRouting}.dom.test.tsx` 等。

关键风险点防护：运行前检测 5001 端口（`netstat -ano`）——**全程空闲**，无残留旧 server 劫持；独立 HTTP 验证走**备用端口 5099**（包装脚本起独立测试实例，不碰 5001，用毕已清理），规避踩坑指南 §6 的 5001 劫持坑。所有测试/构建命令均硬性超时（Start-Process 式后台 + 轮询 + Kill）。

---

## 2. 全量门禁独立复跑结果（真实计数）

| 门禁 | 命令 | 基线 | 独立复跑实测 | 结果 |
| :-- | :-- | :-- | :-- | :-- |
| pytest | `python -m pytest tests/ -q` | **703/0/0** | **修复前 703/0/0（27.43s）；修复后 706/0/0（18.09s，+3 format_fill_cards 用例）** | ✅ |
| vitest | `cd gui && npx vitest run` | **512/0 无 skip** | **512 passed / 0 failed / 0 skipped**（65 文件） | ✅ |
| tsc | `cd gui && npx tsc --noEmit` | EXIT 0 | **EXIT 0**（零输出） | ✅ |
| vite build | `cd gui && npx vite build` | EXIT 0 | **EXIT 0**（5.79s，dist 产物齐全；仅既有 chunk>500kB 提示，非阻塞） | ✅ |
| 契约闸门 | `tests/integration/test_api_contract.py` | 双向一致 + 真实 HTTP 含 cycle 用例 | 118 passed/0 failed（含契约闸门 + lattice + build_cells_data + U 注释 + roundtrip 定向复跑） | ✅ |
| 跨语言 golden | Python `test_lattice.py` + TS `lattice.test.ts` 读同一 `latticeGolden.json` | L1-L9 双端逐位一致、无 skip | Python 侧 `test_{validate,positions,nested,single_fill_assembly}_golden_cross_language` 全过；TS 侧 golden 循环全过（hexCenter/dirCounts/macrobody/rhpMacro/collectFillUniverses/compressRaw/cycle）；pytest 0 skip / vitest 0 skip | ✅ |
| R1 不动点 | 五夹具 17×17/BEAVRS/hex_lattice/prob41c/inp24 parse→gen→parse | 字节稳定 | 独立脚本复跑（修复前）：五夹具 `gen2==gen1` 字节全等；**修复后复跑：仍全等**（17×17=2753B、beavrs=46364B、hex_lattice=1048B、prob41c=1103B、inp24=2962B；FILL 输出改为 cells 展开按 j 行分组，长度变化属预期）；pytest `test_r1_*_fixed_point` + `test_hex_lattice_fixture_roundtrip_stable` 全过 | ✅ |
| R4 不回退 | kitchen_sink | 不回退 | `test_r4_kitchen_sink_full_roundtrip` PASSED；修复后独立复跑 15 passed（R4 + build_cells_data） | ✅ |

**契约闸门 detail**：AST 双向断言两个用例全绿——
- `test_contract_api_yaml_operation_ids`（handlers dict 每个 path 在 api.yaml 有 operationId）
- `test_contract_api_yaml_no_stale_paths`（api.yaml path 都在 handlers dict）
- 真实 HTTP：`test_http_preview_lattice_shape` / `test_http_preview_lattice_cycle` / `test_http_preview_lattice_universe_stl_nonempty` / `test_http_generate_then_parse_roundtrip` 全 PASSED。
- api.yaml `/api/preview-lattice` 响应已含：`limit: enum [ok, depth_limit, too_many, cycle]` + `cycle: boolean` + `chain: array<string>`（api.yaml:1637-1642，已逐字核对）。

**跨语言 golden L1-L9 落位核验**：golden JSON 顶层段齐全——`hexCenter`(4)/`positions`(4，hex_2x2 已重算为项5 新值)/`dirCounts`(3)/`macrobody`(2)/`rhpMacro`(1)/`collectFillUniverses`(3)/`compressRaw`(2)/`cycle`(2)/`assembly`(1)。Python `_golden_positions_hex_fresh` / `_assembly_golden_consistent` 判 fresh 均命中（用例未 skip，证明 golden 已由前端写盘为最终值）。

---

## 3. 15 项核验结论（逐项 过/不过 + 证据）

### A 栅格编辑器（项 1-7）

| 项 | 核验结论 | 证据 |
| :-- | :-- | :-- |
| **1 延伸并入第一页** | ✅ 过 | `LatticeEditDialog.tsx:44` `STEPS = ["类型与尺寸","材料与曲面","画布涂色","保存"]` 4 步；步骤 0 含 lat 选择 + 方向块数 + 2D/3D toggle + 轴向层数 k（`:347-365`）；footer 边界 `step<3 下一步 / step===3 保存`（`:302-313`）。 |
| **2 方向块数 -N:M** | ✅ 过 | TS `rangeFromDirCounts/dirCountsFromRange`（lattice.ts:248-261）+ Python `_dir_counts_from_range`（test_dir_counts_from_range PASSED：-8:8→(8,8)、0:16→(0,16)、-2:5→(2,5)，dims=L+R+1 与 `_range_count` 自洽）；新格阵默认 {neg:8,pos:8}→`-8:8` 居中（LatticeEditDialog.tsx:87-91）；golden dirCounts 3 样例全过。 |
| **3 自动生成宏体 vs 手填互斥 + 子预览** | ✅ 过 | `autoMode` radio 互斥（LatticeEditDialog.tsx:389-394）；自动模式 textarea 只读 + `autoGenMacrobody`（rect→`rpp …`/hex→`rhp V H R1`，lattice.ts:609-626）；`MacrobodyPreview` 子预览组件存在（`:448-451` 挂载，新建 `gui/src/components/MacrobodyPreview.tsx`）；golden macrobody 2 样例（rect_rpp=`rpp -10 10 -10 10 -5 5`、hex_rhp=`rhp 0 0 -5  0 0 10  0.866 0.5 0`）双端过。 |
| **4 六棱柱全量参数** | ✅ 过 | RHP 双模式：模式 B 中心+外接半径+高 `rhpFromCenterRadiusHeight`（lattice.ts:548）、模式 A 三点+高 `rhpFromThreePoints`+`rhpModeAError`（`:563-590`）；后端 `_validate_rhp_params`（9/12/15/18 参合法、\|H\|>0、R1⊥H、R2/R3 两两 60° 旋转；test_validate_rhp_params PASSED）+ `_rhp_extent` 9 参 Rodrigues 推断（test_rhp_extent_9params_infer PASSED：9 参 AABB == 12 参显式）；golden rhpMacro `rhp 0 0 -5  0 0 10  1.732 1 0` + extent 过。 |
| **5 hex 权威公式（L1）** | ✅ 过（90° 旋转未做，待用户确认，非缺陷） | Python `hex_center` + TS `hexCenter` 双端同一权威公式 `x=i·p·√3/2, y=j·p+(i%2)·p/2`（lattice.py / lattice.ts:130-135；test_hex_center_formula / test_hex_center_flat_top PASSED）；golden hexCenter 4 样例（pitch=2：(1,0)→(1.7320508075688772,1)、(0,1)→(0,2)）双端逐位一致；positions.hex_2x2 已重算（idx1=(1.5,0.866…)、idx3=(1.5,2.598…)）；LatticeCanvas 格元盒 `width=2pitch/√3, height=pitch` + clipPath 顶点在 ±X 中点（LatticeCanvas.tsx:24,85-86,104-109）；LatticePreview3D/buildHexPrism 顶点 0° 在 +X（hexPrism.ts:23）。**无 90° 旋转实现**（设计 §5.5 明确本批不做，待用户拍板——见复验要点 6）。 |
| **6 调色板同屏** | ✅ 过 | 步骤 2 画布 + 调色板侧栏同屏（LatticeEditDialog.tsx:494-541：LatticeCanvas + 常驻 `universeList` 色块按钮 + 自定义宇宙号 + 当前涂色笔），点选即用。 |
| **7 调色板来源合并** | ✅ 过 | `collectFillUniverses`（lattice.ts:221-235）：void "0" 恒首 ∪ deck u= 去重 ∪ 各 fill_grid.cells[].u 去重，数值升序；golden merge_17x17 → `["0","1","2","3","10"]`、empty_deck → `["0"]`、dirty_fill_grid 容错 → `["0","5"]` 全过。 |

### B U 分组（项 8-11）

| 项 | 核验结论 | 证据 |
| :-- | :-- | :-- |
| **8 分组默认开 + localStorage 持久化** | ✅ 过 | GeometryTab.tsx:70-80：`useState` 读 `localStorage["mcnp_groupbyu_v1"]`（`stored===null ? true : stored==="true"` 默认 true）+ `useEffect` 写回；键与工作区 `mcnp_workspace_v1` 解耦。 |
| **9 组头可编辑 → INP C 注释** | ✅ 过 | 组头双击内联 input → `patch({universeComments})`（GeometryTab.tsx:82-93）；DeckContext.tsx:74/86 加 `universeComments?: Record<string,string>` 字段；生成器 `universe_group_banner(u,text)` 冻结词汇（banners.py:93-95，`C  U-group U=<n>: <text>`）在相邻同 U 连续段首行前插入（inp_generator.py:64-67）；解析器 `_UNIVERSE_GROUP_RE` 吸收进 `deck.universe_comments`（parsers/core.py:188,1118）。**独立 HTTP 验证 6/6**：generate INP 含两条 `C  U-group` 注释、parse 吸收 `universeComments`、gen2==gen1 字节等长（213B）。pytest test_universe_group_comment 5 用例全过（含 round-trip + 无注释零影响 + raw 行不打断连续段）。 |
| **10 未分组组兜底** | ✅ 过 | universeGroups.ts:13 `UNGROUPED_U=-1` 哨兵；`groupByUniverse` 对 u 空/空白/非有限进未分组组（`:35-37`），数值升序排最前；组头「未分组 · N 栅元」；拖入未分组组头 = 清空 u（resolveDrop / applyRegroupToRows，`:75-88`）；universeGroups.test.ts 12 用例全过。 |
| **11 拖拽改 U 弹回修复** | ✅ 过 | 根因确认（onDropOnGroup 只 setCells 未 patch deck → deck 同步 effect 覆盖回弹）；修复=GeometryTab.tsx:96-101 `nextCells=applyRegroupToRows(...)` → `setCells(nextCells)` **同时** `patch({cells: localToDeckCells(nextCells)})` 单一权威即时同步；`geometryGroupDrag.dom.test.tsx` 4 用例全过（默认分组视图/localStorage 保持/拖 cell→组头 u 更新+不回弹+deck patch/拖未分组清空 u）；既有 `geometryBatchEditReorder.dom.test.tsx` 显式关分组保扁平行语义。 |

### C 数据校验（项 12-13）

| 项 | 核验结论 | 证据 |
| :-- | :-- | :-- |
| **12 保存 raw 全路径 + 体积告警** | ✅ 过 | 保存路径 `fg.raw = compressRaw(cellsToRaw(fg))`（LatticeEditDialog.tsx:277）；`compressRaw` nR 回缩 `["1","1","1","2","2"]`→`"1 2r 2 1r"` + 幂等（golden compressRaw 2 样例 + lattice.test.ts:341-348）；`latticeVolumeWarning` >64KB 或 cells>8000 非阻塞告警（lattice.ts:346-352，LatticeEditDialog.tsx:297-300,562-564）；导入路径保持源 raw 原样（防 parse→gen→parse 漂移）。 |
| **13 循环嵌套检测** | ✅ 过 | 后端 `detect_fill_cycle` DFS（test_detect_fill_cycle PASSED：自环/两元环/三元环/无环/fill="0" 不构成边/fill_grid+translated 引用构成边）+ `compose_lattice_tree` 入口判环 status="cycle"（test_compose_lattice_tree_cycle PASSED：`{status:"cycle",cycle:["1","2","1"],tree:[],leafInstances:[],count:0}`）+ handler 透传 cycle/chain（api_server.py:2475-2480）+ api.yaml limit enum 增 cycle + cycle/chain 字段 + 契约闸门 HTTP cycle 用例（test_http_preview_lattice_cycle PASSED）；前端 `detectFillCycle` 镜像（lattice.ts:375-418）+ 保存前阻止 alert（LatticeEditDialog.tsx:261-273）。**独立 HTTP 验证**：A→B→A deck → `{limit:"cycle", cycle:true, chain:["1","2","1"]}`。 |

### D 3D 预览（项 14-15）

| 项 | 核验结论 | 证据 |
| :-- | :-- | :-- |
| **14 void 参与 STL + skip fill** | ✅ 过 | `build_cells_data`（api_server.py:254-351）三连 skip：`if has_fill or has_fill_grid: continue`（含 fill="0"，`:334-339`）+ `if is_graveyard: continue`（imp_n/impP/impE 任一首 token "0"）+ `if not render: continue`；void（mat=0 无 fill 无 u）在 `include_void=True` 下保留产 STL；`_build_one_universe` include_void=True（`:632`）。`tests/unit/test_build_cells_data.py` **13 用例全过**（fill 单值/格阵/fill="0" 跳过自身、纯 void 产 STL、实体产 STL、render:false 跳过、graveyard imp0/任意粒子 imp0/imp 非 0 非 graveyard、STEP include_void=False 边界、判别联合格式）。**独立 HTTP 验证**：纯 void 球 preview-3d → **8000 三角** STL 非空；fill cell（material=1+fill="5"）preview-3d **stl_data 不含该 cell**（只有实体 cell "2"）。 |
| **15 格阵按 FILL 装配显示** | ✅ 过 | Preview3D 默认装配路由：`hasLattice = rawCells.some(c => fill_grid非空 ∥ fill非空且≠"0")` → `latticeView` 默认 true（Preview3D.tsx:491-497）；装配视图内不请求 preview-3d（`:626-627`）；Preview3DLattice `nonVoidFrameLeaves` 取景排除 void 叶（latticeInstances.ts，`leaves.filter(p => p.mat!=="0")`）+ void 叶透明（`transparent: isVoid, opacity: isVoid ? 0 : 1`）；后端 `_expand_universe` 修正（test_expand_universe_void_leaf_and_fill0 PASSED：void 叶产 `{leaf,void:true}`、fill="0" 装配容器 skip、同 U 实体 cell 正常叶）+ 单值 fill 装配链（test_expand_universe_single_fill_assembly PASSED）+ golden assembly 消费（test_single_fill_assembly_golden PASSED，window fill=1 → leaf 101 u=1 depth=1）+ sub_by_u 过滤 graveyard（api_server.py:2413）。`preview3dLatticeRouting.dom.test.tsx` 全过。 |

### ⏸ 项 5 显示歧义（90° 旋转）

按图纸 §5.5，本批**未做** 90° 旋转显示，前端按权威顶点+X 蜂窝实现（画布 clipPath ±X 顶点、3D buildHexPrism 顶点 0° 在 +X、hexCenter 权威公式）。**这不是缺陷**，设计已确认待用户拍板是否追加（见复验要点 6）。

---

## 4. 关键风险点独立验证（非实现 agent 自报，测试自建实例验证）

在**备用端口 5099** 起独立 api_server 测试实例（`python test_api_launcher.py`，包装脚本设 PORT=5099），真实 HTTP 请求核验，**6/6 PASS**：

| 风险点 | 独立验证结果 |
| :-- | :-- |
| 5001 端口劫持 | 运行前 `netstat -ano` 确认 **5001 全程无监听**（无残留旧 server）；独立实例用 5099 不碰 5001，用毕 `taskkill` 已清理（PID 20508）。 |
| void 参与 STL 后 preview-3d 对 void 出 STL 非空 | void 球（`-1`/`1 so 5`）→ `stl_files={"1":...cell_1.stl}`，**8000 三角形**。 |
| 单值 fill cell 不产自身 STL（装配容器） | 实体 cell（mat=1 + fill="5"）+ 实体 cell（mat=1）→ `stl_data` 键仅 `["2"]`，fill cell 被跳过。 |
| cycle 端点 | A→B→A deck → `/api/preview-lattice` 返回 `{"limit":"cycle","cycle":true,"chain":["1","2","1"]}`。 |
| U 注释 round-trip | `C  U-group U=1: 燃料区` 生成进 INP → parse 吸收 `universeComments:{"1":"燃料区","2":"反射层"}` → gen2==gen1 字节等长（213B）。 |
| 五夹具 R1 不动点 | 独立脚本 parse→gen→parse→gen：17×17/BEAVRS/hex_lattice/prob41c/inp24 `gen1==gen2` 字节全等。 |
| R4 kitchen_sink 不回退 | `test_r4_kitchen_sink_full_roundtrip` PASSED。 |

---

## 5. 问题列表（按严重程度排序）

### ❌ 致命（阻塞上线）：**0 个**

### ⚠️ 严重（建议修复后上线）：**0 个**

### 💡 建议（仅供参考）：3 个

1. **项 5 显示歧义待用户拍板**：用户期望 `[2,3,2]` 行长（点朝上取向），权威顶点+X 蜂窝下水平行长为 `[1,2,1,2,1]`。本批按权威实现，未做 90° 旋转显示。若用户坚持视觉 `[2,3,2]`，需追加整体 90° 旋转显示（另排期）。**涉及项 5，图纸 §1 项 5 / §5.5**。
2. **项 12 已知等价改写**：17×17 等大格阵经编辑器保存后 raw 会被 `compressRaw` 改写（如源 `1 17r` → `1 16r`），字面不同但 `parse_fill_entries` 展开等价（golden 已补等价断言）。这是设计决策（编辑器路径启用压缩，导入路径保持源 raw），非缺陷，复验时可留意 INP 输出与此差异。
3. **vite build chunk>500kB 提示**：主 bundle 1,454kB（gzip 423kB），既有提示非本批引入，非阻塞；如需可后续动态 import 分包（不属于本批）。

---

## 6. 整体评估结论

**全部门禁独立复跑绿**：pytest **703/0/0**、vitest **512/0 无 skip**、tsc EXIT 0、vite build EXIT 0、契约闸门含 cycle HTTP 用例全绿、跨语言 golden L1-L9 双端逐位一致无 skip、R1 五夹具不动点全稳、R4 kitchen_sink 不回退。

**15 项全部落地（15/15 过）**，关键风险点（5001 劫持 / void STL / fill cell skip / cycle 端点 / U 注释 round-trip / R1 五夹具）独立 HTTP 验证 6/6 PASS。

**无 ❌ 致命、无 ⚠️ 严重**。**结论：可交用户浏览器复验**（复验要点见下）。无需打回，不阻塞上线。

---

## 7. 复验准备建议 + 用户浏览器复验要点清单

### 复验准备（交付前环境）
1. **后端 5001**：需用**新代码**起后端（本批测试用 5099 独立实例，未占用 5001）。浏览器复验前，PM 需在 5001 起新 api_server（或提示用户重启主程序 sidecar），**务必确认 5001 跑的是新代码**（旧 server 无 cycle 判环，会 500；诊断：cycle 端点 500 且 traceback 行号对不上当前文件 → 先 `netstat -ano | grep 5001` 杀残留）。
2. **前端 dist**：`gui/dist` 已由本批 vite build 产出（dist 就绪），1420 静态服务 `python -m http.server 1420` 指向 `gui/dist` 即可复验。
3. 测试实例（5099）已清理；5001 全程未被测试占用。

### 用户浏览器复验要点（按用户实测反馈逐项确认）
1. 栅格编辑器为 **4 步**：类型尺寸+延伸（第 0 步）/ 材料曲面 / 画布涂色+调色板同屏 / 保存。
2. 矩形格阵尺寸改为**方向块数**（负/正复制块数，如 `-8:8` 居中）；六棱柱仍用环数。
3. 自动生成宏体（rect→RPP / hex→RHP）与手动填曲面**互斥**，自动模式下有宏体子预览；六棱柱 RHP 双模式（中心+外接半径+高 / 三点+高）参数全量。
4. 画布六棱柱蜂窝：格位间距与格元顶点朝向一致（顶点+X flat-top），无破洞错位。
5. U 分组**默认开启**且重启保持；无 U 栅元进「未分组」组；拖拽栅元到组头改 U **不再弹回**。
6. **六棱柱取向确认**：用户请拍板 —— 权威顶点+X 下水平行长为 `[1,2,1,2,1]`（用户原先期望点朝上 `[2,3,2]`）；若需点朝上显示，**是否追加 90° 旋转显示**（另排期）。
7. 分组头**双击可编辑**，生成 INP 时每 U 组首行前有 `C  U-group U=<n>: <text>` 注释；重新导入后注释保留。
8. 保存大格阵（如 BEAVRS 全堆芯）有**体积过大**非阻塞提示；保存后 raw 用 nR 压缩（如 `1 16r`），INP 等价。
9. 构造 A→B→A 循环嵌套格阵：保存被**阻止**并提示循环；预览端点返回 limit=cycle。
10. 3D 预览：**纯 void 格元出透明 STL**；带 fill 的格元（含 fill="0"）**不再出「大紫方块」**（装配容器不渲染自身）；graveyard（imp=0）不渲染；**有 FILL/格阵的 deck 默认进格阵装配视图**，void 叶透明且不撑大取景（无「针尖」拉远相机）。
11. 17×17 PWR 组件（`/examples/assembly_17x17_mcnp.i`）导入 → fill_grid 有值、详细模式真实 pin 几何（非空 STL）、色块总览切换、generate 字节稳定。

---

## 8. backend format_fill_cards 修复（Wave 3b）— 已重验定稿

### 8.1 缺陷定位（测试独立复核）

**用户浏览器复验发现的格式缺陷**：`format_fill_cards`（`app/lattice.py:247-308`）lattice 分支对 FILL 条目续行原用 `_pack_entries` **按字符宽度 max_chars=75 贪心打包**，而非 MCNP 规范要求的**每个 j 行一条续行（按 dims[0] 分组，行内按 i 从左到右）**。后果：宽格阵（如 17×17 每行 17 条目）的一条 j 行可能被拆到多条续行，或相邻 j 行被合并——输出格式不符合 MCNP FILL 卡语义（用户浏览器实测，2026-08-25）。

### 8.2 修复方案（backend 已落地，2026-08-25 00:26）

`format_fill_cards` 改 **cells 结构化展开优先**：按 `dims[0]=nx` 每行分组（行主序 i 最快 → 每行一个 j 行，行首 5 空格缩进）；某 j 行超 75 字符（含缩进 ≤80 列）再按宽度拆子行（token 序不变）。**raw 仅 cells 空或截断**（`len(cells) < dims 乘积`，MAX_EXPANDED_ENTRIES 封顶致 cells 不完整）时兜底——截断数据展开会丢源 token，回落 raw 保 R1/保真。lat=2 六棱柱同样按 nx 行分组（token 序不变即合法）。translated 单填充路径不变。

### 8.3 独立重验结果（backend 落地后，测试独立复跑）

| # | 重验项 | 独立实测 | 结论 |
| :-- | :-- | :-- | :-- |
| 1 | format_fill_cards 新语义 | `tests/unit/test_lattice.py` **66 passed/0 failed**（新增 `test_format_fill_cards_{per_row_grouping_17x17,row_width_split,cells_first_over_raw,raw_fallback_empty_cells,raw_fallback_truncated}` 全过） | ✅ |
| 2 | R1 五夹具不动点 | 独立脚本：五夹具 `gen2==gen1` 字节全等（17×17=2753B / beavrs=46364B / hex_lattice=1048B / prob41c=1103B / inp24=2962B；FILL 输出改 cells 展开按 j 行分组，长度变化属预期）；**独立核验 17×17 FILL 块 = 17 行 × 每行 17 条目（==dims[0]）** | ✅ |
| 3 | R4 kitchen_sink | `test_r4_kitchen_sink_full_roundtrip` + build_cells_data 独立复跑 **15 passed** | ✅ |
| 4 | 全量 pytest 基线 | `python -m pytest tests/ -q` **706 passed / 0 failed / 0 skipped**（18.09s；基线 703 + 新增 3 用例，不回退反增） | ✅ |

**不受影响（按 Wave 3 原结果）**：vitest **512/0**、tsc EXIT 0、vite build EXIT 0、契约闸门（含 cycle HTTP）、跨语言 golden L1-L9（format_fill_cards 属后端单侧，不涉 golden 断言段）。

### 8.4 结论

format_fill_cards 缺陷修复**已重验通过**：每 j 行 = dims[0] 条目符合 MCNP 规范，R1 五夹具 / R4 / 全量 pytest 基线不回退。QA 报告定稿，可交用户浏览器复验。
