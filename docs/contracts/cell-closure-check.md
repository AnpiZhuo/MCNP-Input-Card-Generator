# 栅元封闭性自检 — 设计约定（cell-closure-check）

> 状态：**已完整交付** —— 「单栅元封闭性判定」链路已实现并接入 UI（2026-09-09 批次，commit 见 `.git/logs/HEAD:277-280`）。
> ~~「外部栅元 ROI 缝隙/水密（gap）检测」仅有接口骨架~~ → **2026-09-10 用户裁决：删除骨架**（见 §2.2）。
> 权威依据：本文件；实现锚点 `app/_freecad_csg_worker.py:1122-1175`（判定）、`gui/backend/api_server.py:1829-1889`（端点）、`gui/src/utils/cellClosure.ts`（展示语义）、`app/lattice.py` 无关。
> 引用方：`docs/contracts/validator-crosscheck.md`、`MCNP输入卡生成器_功能待办清单.md:8`（本文件为其落地契约）。
> ⚠️ 维护纪律：本文件描述的是**代码现状**；若实现变更，必须同步本文件。
> 命名说明：本文件原名 `watertight-check.md`（沿用审计期引用）；因未实现的 ROI 水密链路已裁决删除，2026-09-10 改名为 `cell-closure-check.md` 以对齐实际内容。

---

## 1. 目标与非目标

- **目标**：在编辑期拦下「几何没盖严」这类**MCNP 输运不报错但结果错**的缺陷（lost-particle 源头），并把结果以**非阻断诊断**形式呈现给用户。
- **非目标**：
  - 不做输运级 lost-particle 判定（不跑 MCNP）；
  - **不参与 INP 生成**（UI-only 诊断，任何状态都不阻断生成/保存）；
  - **不做 ROI 级「缝隙/重叠」量测**（2026-09-10 裁决：该能力不实现，其接口骨架已删除，见 §2.2）。

---

## 2. 唯一链路：已实现的单栅元封闭性判定

### 2.1 已实现（唯一生效路径）

| 层 | 锚点 | 说明 |
| :--- | :--- | :--- |
| 端点 | `POST /api/check-cell-closure`，`docs/contracts/api.yaml:1448`（operationId `checkCellClosure`） | handler `gui/backend/api_server.py:1829-1889` |
| 入参 | `{surfaces: str, cells: [...], tr_cards: str}` | 单栅元自检只发 1 个 cell 的 payload（`CellEditDialog.tsx:74-87`） |
| 强制包含 | `build_cells_data(cell_list, include_void=True, force_include_numbers=all_nums)`（`:1869-1870`） | **全部栅元参与判定**：graveyard（imp=0）/ fill 容器 / void / `render:false` 都不跳过（`:1861-1863` 注释） |
| 引擎 | `FreeCADEngine.build_geometry(..., check_closure=True)`（`app/freecad_preview.py`） | 必须 FreeCAD；无 FreeCAD 时返回空 `closure_report` + message（`api_server.py:1849-1852`） |
| 判定 | worker Step 3.6（`app/_freecad_csg_worker.py:1122-1175`） | 见 §3 |
| 响应 | `{status:"ok", closure_report:{ "<cellNum>": {status, volume, aabb, infinite_axes} }}` | 降级分支返回 `closure_report: {}` + `message`（无 FreeCAD / 无有效曲面 / 无可检测栅元） |

### 2.2 已删除：外部栅元 ROI 缝隙/水密（gap）检测骨架

**裁决（用户，2026-09-10）**：该能力**不实现**，删除其在 `FreeCADEngine` 里的全部痕迹。

删除前的事实（2026-09-10 静态核对）：下列符号**已声明并有读取点，但没有生产者、也没有调用点** ——

| 符号 | 删除前声明/读取 | 实测状态 |
| :--- | :--- | :--- |
| `FreeCADEngine.gap_volume` / `gap_fraction` / `roi_volume` / `fused_volume` / `gap_unresolved_cells` | `app/freecad_preview.py`（初始化 + 从 worker 结果读回） | worker **无对应计算** → 恒为 `None`/`[]` |
| `build_geometry(check_watertight=True)` / `outside_cell_num=` | `app/freecad_preview.py`（签名 + 传入 worker payload） | **全仓无调用点**；worker 亦无该字段处理分支 |

**处置**：以上两组参数/字段已从 `app/freecad_preview.py` **整体删除**（含 docstring 与 payload 键），全仓 grep `check_watertight` / `gap_volume` / `outside_cell_num` 在 **代码侧零残留**（仅审计冻结件 `docs/audit/**` 与 `docs/tech-debt-report.md` 作为历史证据保留）。同时 §5 的两处文档引用已修正。

> **据此**：`MCNP输入卡生成器_功能待办清单.md` 与 `docs/contracts/validator-crosscheck.md` 此前描述的「FreeCAD BRep ROI **缝隙 + 重叠**检测」「外部栅元**「外」列**标记」**与实现不符，已删除该表述** —— `GeometryTab.tsx` 中只有「**封闭**」列，不存在「外」列。

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

## 7. 测试面（2026-09-10 更新）

- **后端**：`tests/unit/test_build_cells_data.py:130-135`、`:232`（`force_include_numbers` 强制包含外部/graveyard 栅元）。
- **前端（2026-09-10 技术债批次新增）**：
  - `gui/test/cellClosure.test.ts`（8 例）：`closureMeta(status)` 六状态 + 未知状态 fallback 的展示元数据；
  - `gui/test/useCellClosure.test.tsx`（8 例）：惰性不自动请求 + 同 deck 指纹缓存 + **「同长度编辑必须重发」回归锁**（防 TD 里"指纹只比长度"的旧缺陷复发）。
- **仍缺（已登记为审计债）**：`POST /api/check-cell-closure` 端点**无契约测试**（全仓 grep `check-cell-closure` / `checkCellClosure` 在 `tests/` 零命中）；worker Step 3.6 的六态判定与 `tol = B*0.005` 边界无后端单测。
- **建议补齐**（交测试 Owner）：六态判定（`closed`/`infinite`/`semi_infinite`/`empty`/`voxel`/`unresolvable`）、`tol = B*0.005` 边界（恰好触界/恰好不触界）、**bound 依赖**（同几何在不同 B 下状态变化）、三个降级分支。

---

## 8. 变更记录

| 日期 | 变更 |
| :--- | :--- |
| 2026-09-09 | 功能落地：单栅元封闭性判定（端点 + worker Step 3.6 + 前端「封闭」列/自检按钮/`useCellClosure`）；见 `.git/logs/HEAD:277-280` |
| 2026-09-10 | **本文件补写**（原被两处引用但缺失）：按代码现状描述；当时标注 §2.2 的 gap/ROI 链路**尚未实现**并列出待裁定项 |
| 2026-09-10 | **用户裁决执行**：① 删除 `FreeCADEngine` 的 gap/ROI 骨架（`check_watertight` / `outside_cell_num` / `gap_*` / `roi_volume` / `fused_volume` 全部移除，代码侧零残留）；② 修正 `MCNP输入卡生成器_功能待办清单.md` 与 `docs/contracts/validator-crosscheck.md` 两处不符表述；③ 本文件改名 `watertight-check.md` → `cell-closure-check.md` 以对齐实际内容；④ §7 补记前端两套新测试 |
