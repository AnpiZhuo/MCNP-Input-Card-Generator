# 3D 预览几何检查（重合栅元预警）契约

> 契约人：架构师 | 施工方：后端 + 前端 | **✅ 已交付（2026-08-22 施工，见 `docs/CHANGELOG.md` 该日条目）：原"本轮不施工（仅存档，未排期）"的状态已失效，2026-09-10 更正**
> 日期：2026-08-13 | 状态：**已交付** —— `/api/check-overlap`（`docs/contracts/api.yaml:1379`，operationId `checkOverlap`）与 `/api/quick-add-check`（`:1412`）均已上线；`app/overlap_classify.py` / `app/spatial_index.py` / `app/overlap_probe.py` 均已在册；下方 §9 的"本轮不施工"表述为**历史记录**，勿据此判断未实现。
> 端点数量说明：文中"25→26"等为 2026-08-13 当时值（现 api.yaml 共 49 path）。
> 依据：用户反馈 #7（3D 预览缺几何检查 / 重合栅元无预警，参考 VISED，P2 功能增强）+ `PROJECT_MEMORY.md` + 现有 3D 预览链路
> 目标：方案 A（FreeCAD 精确布尔求交 + AABB 预过滤）落地为可施工契约；preview-3d 性能契约（缓存命中 ≤1s / 冷启动 ≤3s）零回归
> 行号说明：本契约行号为 2026-08-13 工作树 Grep 锚定值，施工以每次 Grep 重锚定为准（见 §10）。

---

## 0. 纪律（施工方必读，违反即打回）

1. **不碰 `app/generator/` 与 `app/generator/parsers/`**（MCNP 生成/解析语义零变化，本轮无关）。
2. **不碰 preview-3d 性能契约**：`/api/preview-3d` 响应结构（`stl_files`/`stl_data`/`freecad`/`count`）不变；preview-3d 冷/热路径零新增延迟；已有 KPI（缓存命中 ≤1s、冷启动 ≤3s）测试不得回归。
3. **契约漂移闸门双向一致**：新增 `/api/check-overlap` 必须同时写入 `gui/backend/api_server.py` handlers dict（:505-524）与 `docs/contracts/api.yaml`，`tests/integration/test_api_contract.py` 7/7 绿。
4. **测试铁律不变**：测试不 `import gui.backend.api_server`（模块级 pyvista/FreeCAD 探测污染）；不 `import FreeCAD`；新增纯逻辑测试走 `app/overlap_classify.py` seam（stdlib，无 FreeCAD）。
5. **worker 协议只增不改**：`_freecad_csg_worker.py` 新增 `check_overlaps` / per-cell `export` 入参键与 `overlaps` / `overlap_truncated` / `overlap_unresolved` 出参键，均为可选；现有行为（无该键时）逐字节不变，全文件无 vtk 依赖断言不回归（2026-08-22 起 worker 已改纯 numpy MC）。
6. **禁止反向降级断言**（改断言/删断言/加 skip 骗绿一律打回；FreeCAD 依赖的集成测试仅允许整文件条件 skip，不算绿数）。
7. 施工完成按 §10 重锚定文档并向 PM 汇报 commit 索引。

---

## 1. 背景与管线

### 1.1 现有 3D 预览管线（检测复用的几何已在此构建）
```
Preview3D.tsx → POST /api/preview-3d → api_server._handle_preview_3d (api_server.py:1391)
→ build_cells_data(cell_list, include_void=False) (api_server.py:1443, 定义 :233)
→ FreeCADEngine.build_geometry (freecad_preview.py:370)
→ 子进程 _freecad_csg_worker.py main() (:_freecad_csg_worker.py:932)
   ├─ Step 2: 每曲面 make_halfspace → surfaces dict（bound box [-B,B]³ 内）
   ├─ Step 3: 逐栅元 eval_ast → results{num: Part.Shape} (:940-946)   ← 检测复用点
   └─ Step 4: 每栅元 tessellate → STL (:977-1002)
→ 每栅元 STL → base64 → 单 JSON → 前端
```
- **关键事实**：worker Step 3 已为每个被传入的栅元构建 FreeCAD 实体（`results` dict）。检测只是在这批实体上追加 AABB 预过滤 + 两两布尔求交，**不需要新建几何管线**。
- 缓存深模块 `app/preview_cache.py`（LRU 3，fingerprint :43 / get :56 / put :70 / evict_dir :124 / evict_lru :133）按 `{surfaces, cells, tr_cards}` 指纹存 STL 拷贝目录。检测结果可同指纹落 `overlaps.json` 进缓存目录，随 `_drop`/`evict_dir` 的 rmtree 自动驱逐。

### 1.2 反馈 #7 语义
重合栅元 = 两个栅元的几何实体存在正体积交集。VISED 同类功能对该情况预警。本契约做**显式「几何检查」动作 + 预警面板**，不改变默认预览行为。

---

## 2. 检测算法（方案 A：AABB 粗筛 + 精确布尔精测）

在 worker 内、复用 Step 3 已建实体，执行：

```
输入：results{num: Part.Shape}, bound, cells_meta{num: {material}}, check_overlaps=true
1. 对每栅元取 shape.BoundBox（OCC 对顶点单遍，廉价）→ bbox[num]
2. 候选对：两两 AABB 重叠（min/max 三轴判交）→ pairs
3. 按 bbox 重叠体积（三轴交集区间体积）降序排序 pairs
4. 截断：只处理前 max_boolean_ops 对（默认 300）→ 若 pairs 超限，置 truncated=true
5. 对每候选对 (a,b)：
     try: inter = results[a].common(results[b]); vol = inter.Volume
     except Exception → unresolved[a,b,reason]（OCC 失败/网格不封闭），跳过
6. raw_pairs += {a, b, volume: vol}
7. 交 app/overlap_classify.classify_overlaps(raw_pairs, cells_meta, ...) → report
8. 输出 overlaps / overlap_truncated / overlap_unresolved
```

要点：
- **粗筛在前、精测在后**：AABB 预过滤把典型几何的候选对从 O(n²) 压到 O(~n·26)（每栅元邻域上限）；布尔 `common()` 只作用于候选对。
- **不引入新几何原语**：全部复用 Step 2 的 surfaces / bound box / Step 3 的 results。
- **错误隔离**：每对 try/except，失败进 `unresolved`，不中断整体。
- **性能预算**：布尔次数上限保护病态同心嵌套（AABB 全重叠）场景；典型卡 ~O(N) 次布尔 ≈ 0.2~5s，作为显式按钮 + 加载态可接受。

### 2.1 方案取舍结论（存档）
| 方案 | 结论 | 理由 |
| :--- | :--- | :--- |
| A：精确布尔（本契约采用） | **采用** | 精度最高、无伪报（共享面零体积被容差排除）；补集天然零体积不误报 |
| B：STL 层近似（体素/三角相交） | 否决为主检测器 | 三角网格离散近似漏微重叠；GQ/SQ marching cubes 网格不封闭不可靠；共享面边界易伪报。仅可作未来 A 的预筛增强，本轮不引入 |
| C：纯 AABB 候选提示 | 否决为独立功能 | 邻接共享面栅元包围盒必然重叠 → 伪报率极高；价值低。AABB 仅作为 A 的粗筛骨架 |

---

## 3. 补集 `#n` 处理（天然零体积不误报的论证）

### 3.1 论证
MCNP `#n`（栅元补集）在 `resolve_cell_complements`（freecad_preview.py:85）展开为 `_Unary("#", 栅元 n 完整几何)`，worker `eval_ast`（_freecad_csg_worker.py:857）对 `complement` 求值 = `bound_box.cut(operand)`（:879）。因此：

- 补集栅元的实体 = `box \ 被补栅元`，与被补栅元（及任何被 `#n` 挖掉的区域）**交集体积恒为 0**。
- 世界栅元 `#1 #2 #3` = `((box\c1) ∩ (box\c2)) ∩ (box\c3)` = `box \ (c1∪c2∪c3)`，与内层栅元交集体积恒为 0。
- **结论：精确布尔 + `volume > 容差` 天然排除全部补集伪预警，无需 AST 层面特判**。这是选方案 A 的核心论据（方案 C 在此必伪报，故被否决）。

### 3.2 排除伪预警逻辑（显式化，供测试断言）
```
overlap iff  vol > max(vol_floor_abs, vol_floor_rel * min(vol_a, vol_b))
```
- 共享面邻接栅元：`common()` 体积 ≈ 0（浮点细条），被 floor 排除。
- 补集/世界栅元 vs 内层栅元：`common()` 体积 = 0，被 floor 排除。
- 真实重叠（内缩/嵌套/部分重叠）：`common()` 体积 > floor，被检出。

### 3.3 void 栅元参与
- 检测需包含 void（材料 0）栅元：void 区域与材料区域重叠同样是未定义区域错误。
- 施工点：检测路径调 `build_cells_data(cell_list, include_void=True)`（api_server.py:168），并为每个传入栅元携带 `export: bool`（void → `false`），使 worker **求交参与、不出 STL**（否则世界栅元巨型 STL 会把相机拉飞，这正是 include_void=False 的成因，见 api_server.py:1063-1066 注释）。
- 性能注记：世界补集栅元自身的 AST 求值（若干次 cut）是必要开销；两两求交受 §4 布尔上限保护。

---

## 4. 容差 / 上限 / severity 分级定义

### 4.1 容差（Tolerance）
```
vol_floor_abs = 1e-6          # 绝对下限（deck 长度单位³，MCNP 为 cm³），滤数值尘埃
vol_floor_rel = 1e-4          # 相对下限系数
重叠判定：volume > max(vol_floor_abs, vol_floor_rel * min(vol_a, vol_b))
volumeFraction = volume / min(vol_a, vol_b)
```
- `vol_floor_rel` 保证大栅元的小数值缝隙（浮点）不计为重叠；`vol_floor_abs` 防超大连锁 box 上的数值噪声。
- 两者均可在 `classify_overlaps` 参数注入，测试可覆盖边界。

### 4.2 上限（Cap）
```
max_boolean_ops = 300         # 布尔求交次数上限（防病态 O(n²) 击穿子进程 120s 超时）
truncated = candidate_pairs 数 > max_boolean_ops
```
- 超限时按 §2 第 3 步的 bbox 重叠体积降序处理前 300 对，置 `truncated:true`，UI 提示「已达上限，部分重合可能未检出」。

### 4.3 severity 分级（info / warning / error）
| volumeFraction | 双方均非 void（材料重叠） | 含 void（未定义区域） |
| :--- | :--- | :--- |
| ≥ 0.10 | **error** | **warning** |
| 0.01 ≤ f < 0.10 | **warning** | **info** |
| min_floor ≤ f < 0.01 | **info** | **info** |
| < min_floor（min_floor = max(1e-4, vol_floor_abs/min_vol)） | 排除（非重合） | 排除（非重合） |

- 分级纯函数进 `app/overlap_classify.py`，pytest 可单测（无 FreeCAD）。

---

## 5. 模块 seam（检测放哪、与现有模块的关系）

| 模块 | 改动 | 接口（小） | 实现（深） | 测试面 |
| :--- | :--- | :--- | :--- | :--- |
| **`app/overlap_classify.py`（新，纯 stdlib）** | 新增文件 | `classify_overlaps(raw_pairs, cells_meta, *, vol_floor_abs, vol_floor_rel, max_boolean_ops) -> {overlaps, truncated, unresolved}`；`raw_pairs=[{a,b,volume}]` | 容差过滤 / volumeFraction / severity 分级 / 去重 / 排序 / 截断 | **pytest 单测（主测试 seam，无 FreeCAD）** |
| **`app/_freecad_csg_worker.py`** | 入参加 `check_overlaps:bool` + per-cell `export:bool`；Step 3 后追加检测段；出参加 `overlaps`/`overlap_truncated`/`overlap_unresolved` | 输入/输出 JSON 各加可选键（只增不改） | AABB 预过滤 + `common()` 求交 + 容差 → 喂 `overlap_classify` | 真实 FreeCAD e2e fixture + AST 断言（复用 test_preview3d_worker.py 风格） |
| **`app/freecad_preview.py`** | `FreeCADEngine.build_geometry(..., check_overlaps: bool = False)`；请求时把 `engine.overlaps` / `engine.overlap_truncated` / `engine.overlap_unresolved` 存为实例属性 | 新增一个可选关键字参数 + 3 个只读属性（默认 False 时行为逐字节不变） | 透传 worker；解析出参 | 既有 build_geometry 调用点零改动（export_step :380 / api_server :1074） |
| **`app/preview_cache.py`** | 新增 `put_overlaps(fp, report)` / `get_overlaps(fp) -> dict \| None` | 2 个小方法 | `overlaps.json` 落缓存目录；`_drop`/`evict_dir` 已 rmtree 目录 → 自动随驱逐清理 | 现有 cache 单测扩展 |
| **`gui/backend/api_server.py`** | handlers dict 加 `/api/check-overlap`（:519 附近）；新增 `_handle_check_overlap` | 薄封装：指纹→缓存命中→未命中跑 worker 检测→写缓存→返回；守卫镜像 preview-3d | 复用 `parse_surfaces`/`parse_tr_cards`/`build_cells_data(include_void=True)`/`FreeCADEngine` | 契约闸门 + HTTP 往返 |
| **前端 `Preview3D.tsx` + `cellMaterial`** | 「几何检查」按钮 + 预警面板 + `setHighlightCells([a,b])` | 3 个 UI 状态（loading / panel / highlight） | 面板渲染 + 点击对高亮（cellMaterial 红 tint / emissive） | vitest（纯状态/类型）+ tsc |

**关系说明**：
- 检测与 `preview_cache` 的关系：检测结果以 `overlaps.json` 存入**同指纹**缓存目录，二次检查命中免 FreeCAD；`clear-stl`/覆盖预览驱逐缓存目录时 `overlaps.json` 一并消失，无悬挂。
- 检测与 `freecad_preview.py` 的关系：`FreeCADEngine` 是 worker 的适配器（把 pymcnp 对象序列化、spawn 子进程、解析出参），检测的几何侧实现在 worker 内（实体已在此），纯分类逻辑下沉到 `overlap_classify.py`（可测 seam）。

---

## 6. 接口建议（契约影响 + 漂移闸门）

### 6.1 推荐：新增端点 `/api/check-overlap`（POST）
- **入参**：与 preview-3d 同（`surfaces` 文本 / `cells` 列表 / `tr_cards` 文本）。
- **出参**：
```
{"status":"ok","overlaps":[{"a":3,"b":7,"volume":4188.8,"volumeFraction":0.42,"severity":"error"}],
 "truncated":false,"unresolved":[{"a":3,"b":9,"reason":"common 失败"}],"message":""}
```
- **守卫分支**（镜像 preview-3d，api_server.py:1049-1068）：无 FreeCAD / 无曲面 / 无栅元 → HTTP 200 + `{status:"ok","overlaps":[],"message":…}`。
- **选择理由**：
  1. 检测是独立「QA 分析」动作，与 preview-3d 渲染热路径**零耦合**；性能契约（缓存命中 ≤1s / 冷启动 ≤3s）零风险。
  2. preview-3d 响应 schema 不动，前端既有解析零回归。
  3. 检测需要 `include_void=True` + per-cell `export` 开关，塞进 preview-3d 会改变其入参语义与 worker 行为，风险外溢。

### 6.2 备选（不推荐）：复用 preview-3d 加字段
- preview-3d 请求加 `checkOverlaps?:bool`、响应加 `overlaps?:OverlapPair[]`。契约影响：`api.yaml` preview-3d schema（:718-764）追加字段（加性、非破坏）；漂移闸门不受 path 增删影响。
- 否决理由：把检测代价引入 preview 冷路径，有回退性能契约的风险；且必须处理「缓存命中但无 overlaps.json」的二次回算，复杂度上移。

### 6.3 漂移闸门影响
- `tests/integration/test_api_contract.py:80-97` 是**双向一致性断言**（handlers dict ↔ api.yaml 互含），不锁端点数。新增 1 端点 → **25 → 26**，`api_server.py` handlers dict 与 `api.yaml` 同时增补即绿。
- 需改契约面：`api.yaml` 加 `/api/check-overlap`（operationId `checkOverlap`，tags `geometry`）；`api_server.py` handlers dict 加路由 + handler。

---

## 7. 验收标准

### 7.1 后端（pytest，新增 ≥6）
| 测试 | 期望 |
| :--- | :--- |
| `test_overlap_classify.py::concentric_spheres` | 两同心材料球 → 检出对 (a,b)，volume ≈ 内球体积，severity error |
| `test_overlap_classify.py::adjacent_share_face` | 共享平面临接栅元 → 无重叠（容差排除） |
| `test_overlap_classify.py::world_complement` | 世界栅元 `#1 #2` 与栅元 1/2 → 不产生伪报；真实 void 区与材料区重叠 → 检出 |
| `test_overlap_classify.py::severity_table` | 材料-材料 vs 含 void 的 severity 分级逐格断言（info/warning/error） |
| `test_overlap_classify.py::cap_truncated` | 候选对 > max_boolean_ops → `truncated:true`，且按 bbox 重叠体积降序保留前 N |
| 契约闸门 | 端点数 26 双向一致，7/7 绿（含 `checkOverlap` operationId） |
| worker e2e（FreeCAD 可选，整文件 skip 不算绿） | 真实 fixture 检出已知重叠对；`common()` 异常进 `unresolved` 不中断 |

### 7.2 前端（vitest + tsc）
| 测试 | 期望 |
| :--- | :--- |
| `checkOverlap` 按钮 → 预警面板列出 `{a,b,volumeFraction,severity}` | 面板渲染；点击对在 3D 高亮（cellMaterial 红 tint） |
| 无重合 / `truncated` / `unresolved` 状态 | 分别显示「未发现重合」/「已达上限，部分可能未检出」/「部分栅元检测不可靠」非阻断提示 |
| 类型 | `OverlapPair` 进 contract.ts（或 Preview3D 局部类型），tsc/build 通过 |

### 7.3 性能与回归
- `/api/preview-3d` 冷/热 KPI 零回归（既有测试复跑绿）；preview-3d 响应逐字段不变。
- 检测请求自身：典型卡（N≤50）≤ 10s（显式按钮 + 加载态，无 KPI 约束）；二次检查缓存命中 near-instant。
- 既有 251+ pytest、19+ vitest 零回归；无断言降级；无新增运行时依赖。

---

## 8. 施工顺序（**未排期，P0/P1 完成后再执行**）

| 步 | 改动 | 施工方 | 该步验收 |
| :--- | :--- | :--- | :--- |
| 1 | `app/overlap_classify.py`（纯 stdlib）+ 单测 | 后端 | `test_overlap_classify` 全绿（无 FreeCAD） |
| 2 | worker 检测段（§2/§3/§5）+ e2e fixture + AST 断言 | 后端 | worker 只增不改；既有 preview3d 测试绿 |
| 3 | `freecad_preview.py` build_geometry 加 `check_overlaps` 透传 + `preview_cache.py` put/get_overlaps | 后端 | 既有 build_geometry 调用点零改动；cache 单测扩展绿 |
| 4 | `api_server.py` `/api/check-overlap` handler + 路由 + `api.yaml` 加端点 | 后端 | 契约闸门 26 双向一致绿 |
| 5 | 前端按钮 + 预警面板 + 高亮接入 + vitest | 前端 | vitest 全绿；tsc/build 过 |
| 6 | 收尾：tester 复核 + 性能回归（preview-3d KPI 零回归）+ 重锚定 | 测试 | 全验收表达成；向 PM 汇报 commit 索引 |

---

## 9. 边界与风险

### 9.1 边界（铁律）
1. 不碰 `app/generator/`、`app/generator/parsers/`。
2. 不碰 `/api/preview-3d` 响应结构与冷/热路径（性能契约零回归）。
3. 测试不 import `gui.backend.api_server`、不 import FreeCAD（纯逻辑走 `overlap_classify` seam）。
4. 不新增运行时依赖。
5. ~~本轮不施工：契约存档待排期。~~ → **2026-09-10 更正：本项已失效 —— 功能已于 2026-08-22 交付，见文件头状态行（`/api/check-overlap` 在 `api.yaml:1379`）。**

### 9.2 风险
| 风险 | 缓解 |
| :--- | :--- |
| 病态嵌套几何 O(n²) 布尔 | AABB 预过滤 + `max_boolean_ops`=300 + `truncated` 提示 |
| 复杂 BRep `common()` 偶发失败/崩溃 | 每对 try/except → `unresolved`，不中断整体 |
| GQ/SQ marching cubes 网格不封闭 → 体积失真 | 相关对进 `unresolved`，UI 提示不可靠 |
| void/世界栅元参与拉长子进程 | void 只求交不出 STL（`export:false`）；布尔上限兜底 |
| 共享面邻接伪报 | 容差（§4.1）排除零体积求交 |
| 缓存一致性 | `overlaps.json` 是 deck 指纹纯函数；随缓存目录 `_drop` 自动驱逐 |
| 子进程 120s 超时 | 布尔上限 + 独立请求加载态 + 既有 RuntimeError 通道 |

---

## 10. 施工完成后重锚定清单

动工前基线行号（2026-08-22 GQ/SQ 3D 预览修复后重锚定）：

| 符号 | 行号 |
| :--- | :--- |
| `build_cells_data`（include_void 参数） | api_server.py:233 |
| `_STL_SESSION` / `_clear_stl_session` | api_server.py:71 / :74 |
| handlers dict | api_server.py:626-657（preview-3d :646 / cross-section :648 / clear-stl :649） |
| `_handle_preview_3d` | api_server.py:1391 |
| `_handle_cross_section` | api_server.py:1502 |
| `_handle_clear_stl` | api_server.py:1542 |
| `resolve_cell_complements` | freecad_preview.py:85 |
| `_compute_bound_from_surfaces` | freecad_preview.py:268 |
| `build_geometry` | freecad_preview.py:370 |
| worker `eval_ast`（complement :914） | _freecad_csg_worker.py:892 |
| worker `main`（Step 3 results :972-1005 / Step 4 导出 :1007-1065 / 输出 :1067-1074） | _freecad_csg_worker.py:932 |
| `PreviewCache.fingerprint/get/put/evict_dir/evict_lru` | preview_cache.py:43 / :56 / :70 / :124 / :133 |
| api.yaml `/api/preview-3d` | api.yaml:733 |
| 契约漂移闸门（双向一致） | test_api_contract.py:80-97 |

施工完成后更新：`PROJECT_MEMORY.md`（§4 ADR + §8 变更日志）、`app/UI_ARCHITECTURE.md`（若涉及 preview 链路描述）。

---

## 11. 交付检查清单
- [ ] `app/overlap_classify.py` 纯 stdlib + 单测（容差/分级/截断）绿
- [ ] worker 检测段只增不改；真实 FreeCAD e2e 检出已知重叠、补集零伪报
- [ ] `freecad_preview.py` build_geometry 加 `check_overlaps` 透传；既有调用点零改动
- [ ] `preview_cache.py` put/get_overlaps；随 `_drop` 自动驱逐
- [ ] `/api/check-overlap` handler + 路由 + api.yaml 加端点；闸门 26 双向一致绿
- [ ] 前端按钮/预警面板/高亮 + vitest 绿；tsc/build 过
- [ ] preview-3d KPI 零回归；既有 251+ pytest、19+ vitest 零回归
- [ ] 无断言降级、无新增运行时依赖
- [ ] PROJECT_MEMORY.md 更新 + 向 PM 汇报 commit 索引
