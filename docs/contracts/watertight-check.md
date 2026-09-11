# 栅元封闭性 / 几何水密自检 — 设计约定（watertight-check）

> 状态：**已交付（部分）** —— 「单栅元封闭性判定」链路已实现并接入 UI（2026-09-09 批次，commit 见 `.git/logs/HEAD:277-280`）；「外部栅元 ROI 缝隙/水密（gap）检测」**仅有接口骨架、尚未实现**（见 §2.2，待裁定）。
> 权威依据：本文件；实现锚点 `app/_freecad_csg_worker.py:1122-1175`（判定）、`gui/backend/api_server.py:1829-1889`（端点）、`gui/src/utils/cellClosure.ts`（展示语义）、`app/lattice.py` 无关。
> 引用方：`docs/contracts/validator-crosscheck.md:37-41`、`MCNP输入卡生成器_功能待办清单.md:8`（本文件为其落地契约）。
> 补写说明：本文件原被上述两处引用但**不存在**（审计 T1 M-12 / T4 TD-14）；2026-09-10 按代码现状补写，**只描述已实现事实，未实现的明确标注**。
> ⚠️ 维护纪律：本文件描述的是**代码现状**；若实现变更（尤其 §2.2 骨架去留），必须同步本文件。

---

## 1. 目标与非目标

- **目标**：在编辑期拦下「几何没盖严」这类**MCNP 输运不报错但结果错**的缺陷（lost-particle 源头），并把结果以**非阻断诊断**形式呈现给用户。
- **非目标**：
  - 不做输运级 lost-particle 判定（不跑 MCNP）；
  - **不参与 INP 生成**（UI-only 诊断，任何状态都不阻断生成/保存）；
  - 不做 ROI 级「缝隙/重叠」测量（见 §2.2，未实现）。

---

## 2. 两条链路：已实现 / 仅骨架

### 2.1 已实现（唯一生效路径）：单栅元封闭性判定

| 层 | 锚点 | 说明 |
| :--- | :--- | :--- |
| 端点 | `POST /api/check-cell-closure`，`docs/contracts/api.yaml:1448`（operationId `checkCellClosure`） | handler `gui/backend/api_server.py:1829-1889` |
| 入参 | `{surfaces: str, cells: [...], tr_cards: str}` | 单栅元自检只发 1 个 cell 的 payload（`CellEditDialog.tsx:74-87`） |
| 强制包含 | `build_cells_data(cell_list, include_void=True, force_include_numbers=all_nums)`（`:1869-1870`） | **全部栅元参与判定**：graveyard（imp=0）/ fill 容器 / void / `render:false` 都不跳过（`:1861-1863` 注释） |
| 引擎 | `FreeCADEngine.build_geometry(..., check_closure=True)`（`app/freecad_preview.py:383-391`，worker 参数 `:452`） | 必须 FreeCAD；无 FreeCAD 时返回空 `closure_report` + message（`api_server.py:1849-1852`） |
| 判定 | worker Step 3.6（`app/_freecad_csg_worker.py:1122-1175`） | 见 §3 |
| 响应 | `{status:"ok", closure_report:{ "<cellNum>": {status, volume, aabb, infinite_axes} }}` | 降级分支返回 `closure_report: {}` + `message`（无 FreeCAD / 无有效曲面 / 无可检测栅元） |

### 2.2 仅有骨架、尚未实现：外部栅元 ROI 缝隙/水密（gap）检测

下列符号**已声明并有读取点，但没有生产者、也没有调用点**（2026-09-10 静态核对）：

| 符号 | 声明/读取 | 实测状态 |
| :--- | :--- | :--- |
| `FreeCADEngine.gap_volume` / `gap_fraction` / `gap_unresolved_cells` | `app/freecad_preview.py:374-379`（初始化）、`:466-470`（从 worker 结果读回） | worker **无对应计算**（全仓 grep `缝隙`/`ROI`/`gap_` 在 worker 内零命中）→ 恒为 `None`/`[]` |
| `build_geometry(check_watertight=True)` / `outside_cell_num=` | `app/freecad_preview.py:389-390`、`:403-405`、`:450-451`（传入 worker payload） | **全仓无调用点**（无任何 handler/脚本传 `check_watertight=True`）；worker 亦无该字段处理分支 |
| `build_cells_data(force_include_numbers=...)` 的水密用途注释 | `gui/backend/api_server.py:306` | 已被 §2.1 的封闭性检测使用（现存唯一消费者），与 gap 无关 |

> **因此**：`MCNP输入卡生成器_功能待办清单.md:8` 与 `docs/contracts/validator-crosscheck.md:37-41` 描述的「FreeCAD BRep ROI **缝隙 + 重叠**检测」「外部栅元**「外」列**标记」**与当前实现不符**——`GeometryTab.tsx` 中只有「**封闭**」列（`:665`），不存在「外」列；ROI 缝隙量测无实现。
> **待裁定（PM）**：① 实现该能力（补 worker 计算 + 调用点 + UI 列），或 ② 删除骨架并修正上列两处引用。**在裁定前不得据待办清单/交叉核对文档认为该能力可用。**

---

## 3. 判定规则（worker Step 3.6，权威实现 `app/_freecad_csg_worker.py:1122-1175`）

对每个栅元的 BRep 实体依次判定（**顺序敏感，先命中先返回**）：

| # | 条件 | status | 附加字段 |
| :--- | :--- | :--- | :--- |
| 1 | 该栅元无 BRep 结果（`results[num] is None`） | `unresolvable` | `volume=None, aabb=None` |
| 2 | 是体素网格（GQ/SQ 走 marching cubes，`FcMesh.Mesh`） | `voxel` | `volume=None, aabb=None` |
| 3 | 体积取不到 / 取体积抛异常 | `unresolvable` | — |
| 4 | `vol <= 1e-6` | `empty` | `volume=vol, aabb=None` |
| 5 | AABB 取不到（异常） | `closed`（保守降级） | `aabb=None` |
| 6 | AABB 触界判定（见下） | `infinite`（触 3 轴）/ `semi_infinite`（触 1–2 轴）/ `closed`（不触界） | `volume, aabb, infinite_axes=[...]` |

**触界判定与容差（依赖 bound —— 关键语义）**：

```
tol = B * 0.005                       # B = 本次构建的包围盒半边长（_freecad_csg_worker.py:1160）
touch = 轴 ∈ {x,y,z}，满足 |cb.min − bb.lo| < tol 或 |cb.max − bb.hi| < tol     # :1162-1167
```

- `B` 由 `app/freecad_preview.py:_compute_bound_from_surfaces(surf_dicts, default=500)`（`:268`）**按曲面自适应**（`max*1.3+100`），并经 payload `:445` 传给 worker（worker 侧默认 500：`_freecad_csg_worker.py:962`）。
- **推论（必须在读报告时知道）**：`infinite` / `semi_infinite` 的语义是「**实体触及本次包围盒边界**」，**不是**数学上的无限大。同一栅元在大 bound 的 deck 下更易被判 `infinite`；**改变 deck 的曲面集合可能改变该状态**。故该状态是**诊断信号**，不可当作绝对几何性质引用。

---

## 4. 用户已裁决的展示语义（唯一权威：`gui/src/utils/cellClosure.ts:41-48`）

| status | 图标 / 颜色 | 标签 | `allowed` | 语义（用户裁决） |
| :--- | :--- | :--- | :--- | :--- |
| `closed` | ✓ 绿 `#2e7d32` | 封闭 | `true` | 封闭有界，正常 |
| `infinite` | **!** 黄 `#f9a825` | 外无限 | **`true`（允许）** | 曲面外空间（如 graveyard）——**正常情况，不报错** |
| `semi_infinite` | **!** 黄 `#f9a825` | 部分无限 | **`true`（允许）** | 在某轴延伸到包围盒边界（非全包围的外无限） |
| `empty` | ❌ 红 `#e53935` | 空/退化 | **`false`（禁止）** | 体积 ≈0 → **曲面未围出封闭实体（=「曲面不封闭」）**，需修 |
| `voxel` | ❌ 红 | 体素网格 | `false` | GQ/SQ 体素网格，**无法判定**（诊断降级，非几何错误） |
| `unresolvable` | ❌ 红 | 未解析 | `false` | 几何解析失败，**无法判定** |

**要点**：
1. 「外无限」与「部分无限」是**允许**的（黄色感叹号 `!`、`allowed=true`），**不阻断**；
2. `allowed=false` 的三态中，**只有 `empty` 属"曲面不封闭"的实质禁止**；`voxel` / `unresolvable` 是**"无法判定"**（渲染同为 ❌，但语义不同——勿把"无法判定"读成"几何错误"）；
3. 渲染：`GeometryTab.tsx:299-307` 用 `closureMeta(status)` 取图标/颜色/标题，`allowed=false` 时以**粗体**强调（`:307`）；**任何状态都不阻断保存/生成**。

---

## 5. 前端入口（三处，均已接线）

| 入口 | 锚点 | 行为 |
| :--- | :--- | :--- |
| 栅元列表「**封闭**」列 | `GeometryTab.tsx:665`（列头）+ `:299-307`（渲染） | 3D 预览后自动取得报告并逐行标注；无面板 |
| 单栅元「🩺 **自检此栅元**」按钮 | `CellEditDialog.tsx:80`（POST）+ `:156-163`（按钮与结果） | 只发当前栅元；结果文本 = `标签 + (体积 mm³) + [延伸至 x/y 轴]`（`:170`） |
| 深模块 hook（惰性） | `gui/src/utils/useCellClosure.ts:1-16` / `:60-84`；接线 `GeometryTab.tsx:226` | **不自动请求**（避免 FreeCAD 子进程开销）；`refresh()` 在点「3D 预览」后触发；**同 deck 指纹缓存**（`:37-47`、`:64`）；请求失败**静默保留上次结果**（`:79-82`） |

（另：`gui/test/**` 目前**无**该链路的专门测试——见 §7。）

---

## 6. 降级与容错

| 场景 | 行为 | 锚点 |
| :--- | :--- | :--- |
| 未检测到 FreeCAD | `closure_report: {}` + `message:"未检测到 FreeCAD，封闭性检测需要 FreeCAD"` | `api_server.py:1849-1852` |
| 未解析到有效曲面 | `closure_report: {}` + message | `:1854-1858` |
| 无可检测栅元 | `closure_report: {}` + message | `:1871-1878` |
| 单个栅元解析失败 | 该栅元记 `unresolvable`（不中断整批） | worker `:1137`/`:1145` |
| GQ/SQ 栅元 | 记 `voxel`（体素网格，无法判定） | worker `:1139-1141` |
| 前端请求失败 | 静默（保留上次结果），不弹错 | `useCellClosure.ts:79-82` |

---

## 7. 测试面（现状 = 缺口）

- **现有旁证**（非该端点专项）：`tests/unit/test_build_cells_data.py:130-135`、`:232`（`force_include_numbers` 强制包含外部/graveyard 栅元）。
- **缺口（已登记为审计债）**：全仓 grep `check-cell-closure` / `checkCellClosure` / `check_cell_closure` **零命中** → 该端点**无专门单测/契约测试**（T1 M-14 / T3 相关条目）。
- **建议补齐**（交测试 Owner）：六态判定（`closed`/`infinite`/`semi_infinite`/`empty`/`voxel`/`unresolvable`）、`tol = B*0.005` 边界（恰好触界/恰好不触界）、**bound 依赖**（同几何在不同 B 下状态变化）、三个降级分支；前端 `closureMeta` 纯函数单测（`cellClosure.ts` 目前仅有类型+常量，无测试文件）。

---

## 8. 变更记录

| 日期 | 变更 |
| :--- | :--- |
| 2026-09-09 | 功能落地：单栅元封闭性判定（端点 + worker Step 3.6 + 前端「封闭」列/自检按钮/`useCellClosure`）；见 `.git/logs/HEAD:277-280` |
| 2026-09-10 | **本文件补写**（原被两处引用但缺失）：按代码现状描述；明确标注 §2.2 的 gap/ROI 链路**尚未实现**并列出待裁定项 |
