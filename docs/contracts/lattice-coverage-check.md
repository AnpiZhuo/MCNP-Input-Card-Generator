# 格阵覆盖完整性检测（universe 未编辑外部 → 红框预防）

> 状态：**✅ 已交付（2026-09-04，commit f7fc2ed）** —— 原标"待确认/落地前契约"，2026-09-10 按实现事实更正：端点 `POST /api/validate-universe-coverage` 已入 `docs/contracts/api.yaml:1546`（operationId `validateUniverseCoverage`），前端 `LatticeEditDialog` 涂色侧栏已接覆盖徽标（绿已覆盖 / 橙未覆盖 / empty 无定义 / lattice 嵌套），门禁 pytest 752/0 + vitest 546/0（见 `docs/CHANGELOG.md` 2026-09 行）。
> 目标：在格阵编辑器（LatticeEditDialog）涂色时，检测当前选中 universe 是否完整覆盖
> 格元盒，提前提示「只定义内部、未定义外部」造成的红色未定义区。

## 1. 背景与动机

MCNP 阵列（lattice）格位被 fill 进 universe `U` 时，`U` 的各栅元必须把整个格元盒（由
格阵 cell 的曲面表达式界定的封闭盒）**填满**。若 `U` 只定义了内部实体（如燃料芯块），
而漏掉了包围它的外部栅元（包壳/冷却剂/真空），则格元盒边缘会出现无任何栅元定义的
区域 —— 也就是填进 lattice 后在预览里看到的「红框」。

由于该未定义区与格元/外层 lattice 的边界重合，输运粒子无法到达这里，**MCNP 输运不报错**，
因此该缺陷藏在卡里不显现。本检测的作用是：在**编辑格阵时**（涂色阶段）就把这种
「没编辑外部」找出来，作为**警告**提示用户，而不是等到跑输运才暴露。

## 2. 已确认的业务方向

| 决策点 | 选择 |
|---|---|
| 检测时机 | **涂色时对当前选中的 U 检测**（`selectedU` 变化或格元盒范围变化时即时提示） |
| 严重程度 | **警告但允许保存**（在涂色面板/调色板区以醒目标识提示，不阻断保存） |
| 覆盖判定 | **U 的任意栅元（含 void/真空）填满格元盒即可**（void 也定义空间，符合 MCNP 语义） |
| 实现范围 | **先出详细设计，确认后再实现**（本文） |

## 3. 覆盖判定规则（核心）

给定 universe `U` 与其格元盒范围 `box = {x_min,x_max,y_min,y_max,z_min,z_max}`：

```
covered(X) = OR over cell∈U  ( X inside cell )
U 填满格元盒  ⇔  box 内任意点 X 都满足 covered(X)
```

- **包含**：material=0 的 void/真空栅元**算作覆盖**（它定义了「该区域是真空」，参与判定）。
- **不含**：fill 装配容器栅元（`fill` 非空或 `fill_grid.kind=="lattice"`）不产实体几何，
  其覆盖由被 fill 的内容决定 —— 这类栅元视作「格阵/装配容器」，不参与叶级覆盖判定。
- **判定输出**：在 `box` 内均匀采样 `N` 个点，统计不满足 `covered` 的点占比
  `uncoveredFraction`；超过阈值 `COVERAGE_TOL`（默认 0.01，即 1%）→ 判定未覆盖。

## 4. 算法与复用

纯 numpy 采样逐点解析判定（复用现有 `voxel_csg` 能力，不走 FreeCAD）。

### 4.1 输入组装（后端接口内做）

```
surfaces_by_num = { num: {type, params, transform} }   // parse_surfaces + _pymcnp_surf_to_dict
tr_cards        = parse_tr_cards(tr_text)
cells_of_U      = deck 中 u==U 的 cell（跳过 graveyard imp=0、跳过 fill 容器）
box             = lattice_cell_extent(surface_expr, lat, surfaces_text)
```

- `surfaces_by_num` 的 `type` 需归一化为 `surface_fn` 认识的类型（P→P_0/P_1 等），这正是
  `_pymcnp_surf_to_dict` 的职责；`transform` 由表面对象带出（*TRn → transform 号）。
- 每个 cell 的 `surface_expr` → AST：`Geometry.from_mcnp(parenthesize_unions(expr)).ast`，
  再 `resolve_cell_complements(ast, cells_by_num)`（处理 `#n` 补集）。AST JSON 化后即可
  交给 `eval_cell_field`。

### 4.2 采样判定

```
lo = (box.x_min, box.y_min, box.z_min);  hi = (box.x_max, box.y_max, box.z_max)
xs,ys,zs = linspace(lo, hi, 16) 每轴（16³≈4096 点）
X,Y,Z = meshgrid
in_cell[i] = eval_cell_field(ast_i, fns, X,Y,Z)      // 每个 cell 一个布尔场
covered    = OR_i in_cell[i]
uncovered  = ~covered
uncoveredFraction = uncovered.mean()
```

- 网格分辨率取 16³（4096 点，毫秒级）。边界点位于曲面附近可能误判，因此阈值用 1% 留裕量。
- 复核：若 `covered` 全部为 True → `covered=true, uncoveredFraction=0`。

### 4.3 输出

```
{
  status: "ok",
  universe: "5",
  kind: "leaf",            // leaf | lattice | empty
  covered: false,
  uncoveredFraction: 0.12,
  sampleCount: 4096,
  detailViable: true,      // 采样是否可信（box 可用时恒 true）
  message: "U=5 未完整覆盖格元盒（约 12% 区域无栅元定义，可能产生红色未定义区）"
}
```

- `kind=="empty"`：`U` 在 deck 中无任何栅元定义 → 提示「该 universe 尚无栅元定义」。
- `kind=="lattice"`：`U` 本身是格阵 cell（含 `fill_grid.kind=="lattice"`）→ 属嵌套格阵，
  覆盖性由子层格阵整体保证，本检测不误报，提示「嵌套格阵由子层覆盖」。
- `kind=="leaf"`：普通叶 universe，执行覆盖采样判定。

## 5. 后端接口

新增端点 **`POST /api/validate-universe-coverage`**（operationId `validateUniverseCoverage`，
tag `geometry`），仅服务格阵编辑器涂色提示。

请求：
```json
{
  "surfaces": "<曲面卡文本>",
  "cells": [ {"kind":"cell","cell":{number,material,surface_expr,u,fill,fill_grid,lat,trcl,...}}, ... ],
  "tr_cards": "",
  "lat": "1",
  "surface_expr": "-1 -2 3 -4 5 -6",   // 当前格阵格元盒曲面表达式
  "universe": "5"                       // 待检测的 universe 号
}
```

响应：见 4.3（错误 → `{status:"error", message}`，HTTP 200 信封；调用方降级为不显示）。

### 实现落点
- 纯采样函数放 **`app/coverage_check.py`**（新，纯 stdlib+numpy，复用 `voxel_csg` 的
  `surface_fn`/`eval_cell_field`/`_surface_tr`，`lattice.lattice_cell_extent`）。承担
  `universe_coverage(cell_asts, surfaces_by_num, tr_cards, box) -> coverage dict` 纯逻辑。
- `gui/backend/api_server.py` 新增 `_handle_validate_universe_coverage`：组装输入（复用
  `parse_surfaces`/`parse_tr_cards`/`build_cells_data` 的 AST 构造段，或轻量化重写），
  调 `coverage_check`，回 `_ok(...)`。
- `docs/contracts/api.yaml`：加 path（operationId/schema）。

## 6. 前端接入（LatticeEditDialog）

- 在**步骤 2（画布涂色）**，当 `selectedU` 变化 或 `surfaceExpr`/`lat`/`localSurfaces`
  变化时，调用 `validateUniverseCoverage(...)`（新 API 封装，`gui/src/utils/lattice.ts`
  加 `validateUniverseCoverage`，与既有 `validateLatticeSurfaces` 同风格，后端不可达兜底）。
- 结果展示在**调色板侧栏**当前选中 U 的上方（新增一行徽标）：
  - `covered=true` → 绿色 `✓ U=5 已覆盖格元盒`。
  - `covered=false` → 橙红 `⚠ U=5 未覆盖格元盒（约 12% 区域无定义，会出现红框）`；
    点击可跳/提示「补一个包围格元盒的外部栅元（材料或 void）」。**不阻断保存。**
  - `kind=="empty"` → 灰 `U=5 尚无栅元定义`。
  - `kind=="lattice"` → 灰 `U=5 为嵌套格阵，覆盖由子层保证`。
- 校验请求用 `AbortSignal.timeout`（如 30s）防挂起；结果滞后不阻塞涂色。
- **保存摘要（步骤 3）**不额外强制；用户已选「警告允许保存」，只保留涂色时提示。

## 7. 改动文件清单

| 文件 | 改动 |
|---|---|
| `app/coverage_check.py` | 新：`universe_coverage` 纯采样函数 + 常量 `COVERAGE_TOL=0.01` |
| `gui/backend/api_server.py` | 新 `_handle_validate_universe_coverage` + handlers 注册 |
| `gui/src/utils/lattice.ts` | 新 `validateUniverseCoverage(u, cfg)` 封装 |
| `gui/src/components/LatticeEditDialog.tsx` | 步骤 2 涂色区接入检测 + 徽标展示 |
| `docs/contracts/api.yaml` | 新 path `validateUniverseCoverage` |
| `tests/unit/test_coverage_check.py` | 新：覆盖/未覆盖/空格元盒/无界/void 参与/阈值用例 |
| `tests/integration/test_api_contract.py` | 新：真实 HTTP `validateUniverseCoverage` |

## 8. 测试要点

- 纯函数：给定 box + 两个 cell AST（内部圆柱 + 外围 void 盒）→ covered=true；
  只有内部圆柱、缺外围 → covered=false 且 uncoveredFraction>1%。
- void 参与：`U` 用「内部圆柱 + 外围 void」vs 「只有内部圆柱」对照，前者覆盖成立。
- 空 U（无 cell）→ `kind=="empty"`；嵌套格阵 U → `kind=="lattice"`（不误报）。
- 格元盒无法解析（`box is None`，含 #/:）→ 返回 `detailViable=false` 且不误判。
- 契约闸门：handlers dict ↔ api.yaml 双向一致；HTTP 用例返回 shape 正确。

## 9. 局限与后续

- **坐标基**：假定 universe 栅元与格元盒同坐标系（未平移/旋转的格位）。带 `TRCL` 的
  格阵本检测不还原平移旋转（首版不做，注明局限）。若 `surface_expr` 引用 `*TRn` 曲面，
  `surfaces_by_num` 已带 `transform`，仅对单曲面生效；格阵级 TRCL 留后续。
- **性能**：单个 U 一次 16³ 采样毫秒级；涂色切换时对选中 U 即时检测，无压力。
- **嵌套格阵**：首版仅标注 `kind=="lattice"` 不递归判定覆盖，避免误报；后续可递归。
