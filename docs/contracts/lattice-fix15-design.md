# 格阵 fill 15 项用户实测反馈修复 — 设计增量（Wave 1 架构图纸）

> 状态：Wave 1 设计定稿（2026-08-24）。本批**只出图纸，不改代码/golden/api.yaml**。
> 后端/前端按此图施工（Wave 2），测试按测试清单补；golden 权威值 + api.yaml diff 在 Wave 2 落地时写入
> `gui/src/utils/__golden__/latticeGolden.json` 与 `docs/contracts/api.yaml`（防实现前弄红门禁）。
>
> 权威依据（不可违背）：用户核心原则①MCNP 能输多少参数编辑器就给多少参数；②格阵 cell 几何统一用宏体定义；
> 已确认 3D 预览 STL 生成 cell 分类规则 1-7（见 §3.1）。

---

## 0. 分派总览（谁做什么）

| 项 | 归属 | 涉及侧 | 更新 golden | 更新 api.yaml |
| :-- | :-- | :-- | :-- | :-- |
| 1 延伸并入第一页 | 前端 | LatticeEditDialog | — | — |
| 2 方向块数→-N:M | 双端 | lattice.ts / lattice.py + 两端点 | 双端（positions/range 段） | — |
| 3 宏体自动生成互斥+子预览 | 前端（生成）+ 双端（golden） | lattice.ts autoGenerateSurfaces 宏体版 + LatticeEditDialog + validate 后端 | 双端（validate/宏体样例） | — |
| 4 六棱柱全量参数 | 双端 | LatticeEditDialog + lattice.py validate/_rhp_extent + lattice.ts | 双端（RHP/HEX 卡样例） | — |
| 5 hex 排列修正 | **双端（跨语言锁死）** | lattice.py hex_center/hex_ring_rows + lattice.ts hexCenter/hexGrid/hexRingRows + LatticeCanvas + latticeInstances + golden | 双端（hexCenter/positions hex 段） | — |
| 6 调色板同屏 | 前端 | LatticeEditDialog | — | — |
| 7 调色板来源合并 | 前端（纯函数）+ TS golden | lattice.ts collectFillUniverses + LatticeEditDialog | TS 侧（collectFillUniverses 段） | — |
| 8 分组默认开+保持 | 前端 | GeometryTab（已实现，补验证/测试） | — | — |
| 9 分组头注释→INP C 注释 | 双端 | 存储 deck.universeComments + inp_generator + banners + parser + GeometryTab + universeGroups | 后端（R1 round-trip 用例） | — |
| 10 未分组组 | 前端 | universeGroups（已实现，补测试） | — | — |
| 11 拖拽改 U 弹回 | 前端 | GeometryTab（已实现，补 DOM 测试） | — | — |
| 12 raw=cellsToRaw 全路径+体积 | 双端 | LatticeEditDialog/CellEditDialog/导入路径 + lattice.ts cellsToRaw/compressRaw | TS 侧（compressRaw 段） | — |
| 13 循环嵌套检测 | **双端** | lattice.py detect_fill_cycle + compose_lattice_tree + lattice.ts detectFillCycle + LatticeEditDialog | 双端（cycle 段） | **后端**（preview-lattice 响应） |
| 14 void 参与 STL + skip fill | 后端 | build_cells_data + _build_one_universe | — | — |
| 15 格阵 FILL 装配显示 | **双端** | Preview3D 路由 + Preview3DLattice + _expand_universe 修正 | 双端（单值 fill 装配/嵌套叶样例） | — |

- **谁更新 golden**：每个「双端 golden」项由**前端产出权威 JSON 段 + 后端消费断言**（沿用阶段2/3 模式：
  前端改 `latticeGolden.json`，后端 `test_lattice.py` 读同一文件；本批设计只写期望值，落地由 Wave 2 前端写盘）。
- **谁更新 api.yaml**：仅项 13（preview-lattice 响应加 `cycle`/`chain`）；由**后端**在实现时同步改 api.yaml +
  契约闸门 HTTP 用例。

---

## 1. 逐项设计

### 项 1：延伸方向并入第一页（类型尺寸 + 2D/3D 延伸）

- **涉及**：`gui/src/components/LatticeEditDialog.tsx`。
- **行为变化**：原 6 步状态机删除「延伸方向」独立步骤，并入第 0 步。含项 6（调色板同屏）后，最终为 **4 步**：
  ```
  0 类型与尺寸 + 延伸方向   （lat 选择 + 列/行 或 环数 + 2D/3D toggle + 轴向层数 k）
  1 材料与曲面               （材料锁死 0 + 本格阵 U + 曲面表达式/自动生成互斥 + 校验）
  2 画布涂色 + 调色板（同屏） （LatticeCanvas + 常驻调色板侧栏）
  3 保存摘要
  ```
  （原「延伸方向」页的 `ext3D`/`layers` 状态保留，UI 移到第 0 步；原「宇宙调色板」页的
  `universeList`/`selectedU`/`customU` 状态保留，UI 移到第 2 步画布旁。）
- **风险**：低。仅 UI 重组；状态机 footer 的 step 边界改为 `step<3 下一步 / step===3 保存`。
- **测试**：`gui/test/lattice.test.ts` 不涉及；DOM 测试（如有步骤断言）同步改 4 步；新增一条「第 0 步含轴向层数 k 输入」断言。

---

### 项 2：尺寸改「方向块数」→ 映射 fill 范围 `-N:M`

- **涉及**：`gui/src/utils/lattice.ts`（`rangeFromDims` → 新 `rangeFromDirCounts` / `dirCountsFromRange`）、
  `gui/src/components/LatticeEditDialog.tsx`（尺寸 UI）、`app/lattice.py`（`_range_count` 已具备，补 `_dir_counts_from_range`）。
- **行为变化**：尺寸输入从「列数/行数/层数」改为「每轴 负/正 方向复制块数」：
  - x 轴：向左 L_x、向右 R_x；y 轴：向前 L_y、向后 R_y；z 轴（仅 3D）：向下 L_z、向上 R_z。
  - 映射：`range_token = "-L:R"`（`0:16` = L=0,R=16 角起；`-8:8` = L=8,R=8 居中）；`dims[axis] = L+R+1`。
  - 反派生：`L = -a, R = b`（token `a:b`）；`dims = b - a + 1`（与 `_range_count` 一致）。
- **权威公式（-N:M ↔ expand_positions 中心一致性，R1 关键）**：
  `expand_positions` rect 中心 = `(i - (nx-1)/2)·px`，其中 `nx = L+R+1`。代入 `i=0`：
  `x = -(L+R)/2·px`，`i=nx-1` → `x = +(L+R)/2·px` —— **`-N:M` 映射下格阵始终以几何中心居中于原点**，
  与 `0:16`（角起，中心偏移 `+(L-R)/2·px`）是同一套坐标系的两种写法，二者不冲突。
  MCNP `FILL=-8:8 -8:8 0:0` 与 `FILL=0:16 0:16 0:0` 都只改变格位索引起点，不改变格位间距/拓扑。
- **权威公式（raw round-trip 字节稳定）**：`fill` 串、`fill_grid.range`、`cellsToRaw` 全部原样携带 `-N:M` token；
  `format_fill_cards` raw 优先回放 —— **生成/往返字节不回退（R1）**。仅「新建格阵 UI 默认」从 `0:d-1` 改 `-8:8` 类居中写法；
  导入的旧 `0:16` deck 编辑时保持原 range（不做无损重写，防 R1 漂移）。
- **golden 期望值（新增段 `dirCounts`）**：
  ```json
  { "id": "center_-8:8", "neg": 8, "pos": 8, "range": "-8:8", "dims": 17 },
  { "id": "corner_0:16", "neg": 0, "pos": 16, "range": "0:16", "dims": 17 },
  { "id": "asym_-2:5",  "neg": 2, "pos": 5,  "range": "-2:5", "dims": 8 }
  ```
- **风险**：中。UI 改动波及 `initialRectCells/initialHexCells/resizeLatticeCells` 的 dims 来源；`rangeFromDims`
  保留（编辑旧 deck 反派生用），新增函数为超集。R1 不动点闸门（17×17/BEAVRS/hex_lattice/prob41c/inp24）必须保持绿。
- **测试**：Python `test_dir_counts_from_range`（3 例映射 + 反派生一致）；TS `rangeFromDirCounts` 对称；R1 五夹具不动点。

---

### 项 3：自动生成曲面(宏体) vs 手填 = 互斥切换 + 子预览

- **涉及**：`gui/src/utils/lattice.ts`（`autoGenerateSurfaces` 改宏体版，新增 `autoGenMacrobody`）、
  `gui/src/components/LatticeEditDialog.tsx`（互斥 UI + 子预览）、后端 `validate_lattice_surfaces`（已支持单宏体，无需改）。
- **行为变化**：
  1. **互斥切换**：第 1 步加「自动生成宏体 / 手动填写曲面」radio。自动模式：曲面 textarea 只读 + 显示自动宏体卡；
     手动模式：textarea 可编辑 + 失焦调 `validate-lattice-surfaces`（现有）。二选一，不叠加。
  2. **自动生成统一用宏体**（用户原则②）：
     - rect(lat=1) → **单个 RPP**：`RPP xmin xmax ymin ymax zmin zmax`（由 L/W/H/cx/cy/cz 推）；
     - hex(lat=2) → **单个 RHP**（项 4 权威语法）；不再生成 PX/PY/PZ 六面 / 6P+2PZ（旧路径废弃为「手动」）。
  3. **子预览**：自动生成后实时显示宏体几何。方案：新增 `gui/src/components/MacrobodyPreview.tsx`
     （复用 `useThreeCanvas` + `lattice_cell_extent` 端 `/api/lattice-extent` 拿盒，渲染线框 RPP/RHP），
     或复用 `LatticePreview3D`（dims=[1,1,1] + 单格位）。**推荐独立 MacrobodyPreview**（不污染格阵预览语义）。
- **权威公式（RPP 生成）**：`xmin=cx-L/2 … zmax=cz+H/2`；`surface_expr = "-<num>"`；编号 `maxSurfaceNumber+1` 顺延。
- **权威公式（RHP 生成）**：见项 4。
- **golden 期望值（新增段 `macrobody`）**：
  ```json
  {
    "id": "rect_rpp", "lat": "1",
    "params": { "L": 20, "W": 20, "H": 10, "cx": 0, "cy": 0, "cz": 0 },
    "expectedSurface": "rpp -10 10 -10 10 -5 5", "expr": "-6"
  },
  {
    "id": "hex_rhp", "lat": "2",
    "params": { "side": 2, "H": 10, "cx": 0, "cy": 0, "cz": 0 },
    "expectedSurface": "rhp 0 0 -5  0 0 10  0.866 0.5 0", "expr": "-6"
  }
  ```
  （`expr` 编号为既有曲面最大号 5 顺延；`validate` 段补 `lat1_rpp_macro` / `lat2_rhp_macro` expectedOk=true。）
- **风险**：中。旧 autoGenerateSurfaces 六面体/6P 路径被替换，`gui/test/lattice.test.ts` 现有 autoGenerateSurfaces
  3 用例（192-211 行）期望值需改为宏体版；`validate_lattice_surfaces` 对 RHP 参数合法性校验（项 4）先行落地，否则
  生成的 RHP 卡在校验时误报。

---

### 项 4：六棱柱参数 = MCNP 全量（RHP/HEX）

- **涉及**：`gui/src/components/LatticeEditDialog.tsx`（两种输入模式表单）、`app/lattice.py`
  （`_rhp_extent` 支持 9/12/15/18 参数 + `validate_lattice_surfaces` 加 RHP 参数校验）、`gui/src/utils/lattice.ts`。
- **权威 RHP/HEX 卡语法**（源自项目 `app/docs/MCNP6_曲面卡格式参考.md` §5.5 + `C810_卡片格式详细.md`，权威=C810.pdf）：
  ```
  RHP  Vx Vy Vz   Hx Hy Hz   R1x R1y R1z [R2x R2y R2z [R3x R3y R3z]]
  HEX  同上
  ```
  - `V` = 底面中心（3）；`H` = 底面→顶面矢量（3，编码高度+轴向）；`R1` = 轴→第一小面中点矢量（3，编码面位+外接半径方向）。
  - `R2/R3` 可选（缺省 MCNP 绕 `H` 旋转 60°/120° 推断）；`_rhp_extent` 现读 12 参（V+H+R1+R2），**需扩展**：
    9 参（仅 R1）→ R2/R3 用 Rodrigues 绕 H 转 60°/120° 推断（与 MCNP 语义一致）；12/15 参原样读取。
- **两种输入模式（各映射哪些参数）**：
  | 模式 | 输入字段 | 派生 → RHP 参数 |
  | :-- | :-- | :-- |
  | **模式 A：三点 + 高度** | 底面中心 V、顶面中心 T、第一小面中点 M、高度 h（只读校验 |T−V|） | `H = T − V`；`R1 = M − V`（校验 ⊥H 且 |R1|=apothem=外接半径·√3/2）；发出 `RHP V H R1` |
  | **模式 B：中心 + 外接半径 + 高** | 中心 C、外接半径 R（顶点半径）、高 h、轴向（默认 +Z）、第一面方向角（默认顶点+X→面心 30°） | `V = C − H/2`（H 沿轴向）；`R1 = (R·cos30°, R·sin30°, 0)`（顶点+X 时）；发出 `RHP V H R1` |
  - 环数 R、轴向层数 k = **格阵维度**（编辑器第 0 步已含），不属于 RHP 卡参数——设计澄清，避免混入宏体卡。
  - **6+2 平面写法备选**：保留「手动填写曲面」下 `6 个竖直 P + 2 PZ`（现有 `autoGenerateSurfaces` hex 路径迁为手动可选），
    与单 RHP/HEX 宏体互为合法写法（`validate_lattice_surfaces` 已认两种）。
- **validate_lattice_surfaces 对 RHP/HEX 参数校验（新增）**：`_validate_lat2` 在 `len(expr_ints)==1` 且 kw∈{RHP,HEX} 时，
  解析 `_parse_surface_cards` 参数：合法参数数 ∈ {9,12,15,18}；`|H|>0`；`|R1|>0`；H·R1≈0（⊥）；若给 R2/R3 各 ⊥H 且 R1/R2/R3 两两夹角 60°。
- **`_rhp_extent` 换算（两输入模式一致性）**：模式 A/B 生成的 RHP 在 `lattice_cell_extent` 下须得到相同物理盒
  （V+H+R1 决定六棱柱 AABB）。9 参推断逻辑补齐后，`expand_positions` hex pitch = y 跨度 = 外接半径·√3（顶点+X 蜂窝，见项 5）。
- **golden 期望值（新增段 `rhpMacro`）**：
  ```json
  { "id": "rhp_modeB_vertexX", "input": { "mode": "center+radius+height", "C": [0,0,0], "R": 2, "H": 10 },
    "expectedCard": "rhp 0 0 -5  0 0 10  1.732 1 0",
    "expectedExtent": { "x_min": -2, "x_max": 2, "y_min": -1.732, "y_max": 1.732, "z_min": -5, "z_max": 5 } }
  ```
- **风险**：中高。RHP 9 参推断是 `_rhp_extent` 行为变化（现 12 参），需保证 12 参既有路径零回归；validate 新增参数校验
  是**破坏性**（此前 `validate_lat2_single_rhp` 用例 `"10 rhp 0 0 0 0 0 2 0.5 0 0"` 12 参合法仍需过）。golden `validate` 段不动。

---

### 项 5：六棱柱蜂窝排列修正（跨语言最大风险）

> ⚠️ 这是后端+前端按同一份公式实现的锁。**权威公式以下为准**，golden `hexCenter`/`positions` hex 段全量重算。

- **涉及**：`app/lattice.py`（`hex_center`、`hex_ring_rows` 语义、`expand_positions` hex 分支）、
  `gui/src/utils/lattice.ts`（`hexCenter`/`hexGrid`/`hexRingRows`/`initialHexCells`/`estimateLatticeExtent`）、
  `gui/src/components/LatticeCanvas.tsx`（格元盒尺寸/交错方向）、`gui/src/three/latticeInstances.ts`（`defaultOrigin`/`gridCenter`）、
  `gui/src/components/LatticePreview3D.tsx`。
- **根因**：现 `hexCenter` 按「奇数**行**横向错半格」（pointy-top 取向），但格元几何是**顶点+X（flat-top）**——
  画布 CSS 六边形与 3D `buildHexPrismGeometry` 顶点都在 ±X。平顶六边形蜂窝必须按「奇数**列**纵向错半格」排布，
  否则格位间距与格元朝向不匹配 → 用户实测的排布错误（格位错位/视觉破洞）。
- **权威公式（双端逐位锁死）**：
  ```
  hexCenter(i, j, pitch):
      # i = 列（快序，MCNP fill 第一轴）；j = 行；pitch = 中心距（edge-to-edge = 外接半径·√3）
      # 顶点+X（flat-top）蜂窝：列水平步距 = pitch·√3/2，行垂直步距 = pitch，
      # 奇数列整体下移 pitch/2（= 与 MCNP LAT=2 基向量 v1=(p·√3/2, p/2), v2=(0,p) 等价的交替形）
      x = i * (pitch * √3 / 2)
      y = j * pitch + (i % 2) * (pitch / 2)
  ```
  - **自洽性核验**：相邻列 `(0,0)→(1,0)` 距离 = √((p·√3/2)² + (p/2)²) = p ✓；相邻行 `(0,0)→(0,1)` 距离 = p ✓；
    `(0,0)→(1,-1)` 距离 = p ✓ —— 全部格位边缘共享（真实蜂窝），与顶点+X 格元朝向一致。
  - `hex_ring_rows` **保持** `[r+1+min(j,2r-j)]`（总格数 1+3r(r+1)），但语义定义为「沿 +30° 共线方向的环行长」
    （顶点+X 蜂窝中 `i+j=const` 方向格位共线）；`initialHexCells` 的角位 void 标记改用新 `inHexRing` 函数
    （见下 golden），不再按 `i<rowLens[j]` 横向行画布。
- **golden 期望值（hexCenter 段全量重算，pitch=2 权威样例）**：
  ```json
  { "col": 0, "row": 0, "pitch": 2, "x": 0,    "y": 0 },
  { "col": 1, "row": 0, "pitch": 2, "x": 1.7320508075688772, "y": 1 },
  { "col": 0, "row": 1, "pitch": 2, "x": 0,    "y": 2 },
  { "col": 1, "row": 1, "pitch": 2, "x": 1.7320508075688772, "y": 3 }
  ```
- **golden 期望值（positions hex 段，fixtures/hex_lattice.inp pitch=√3）**：`hex_2x2_pitch_sqrt3` expected 改为：
  ```
  idx0 (0, 0)          idx1 (1.5, 0.8660254)
  idx2 (0, 1.7320508)  idx3 (1.5, 2.5980762)
  ```
- **画布格元盒**：顶点+X 格元：顶点-顶点宽 = 2R = 2pitch/√3，flat-flat 高 = pitch。`LatticeCanvas` hex 格元
  `width = 2pitch/√3`、`height = pitch`、`clipPath` 顶点在左/右中点（保持 ±X 顶点）；绝对定位 `left = h.x - width/2`、`top = h.y - height/2`。
- **风险**：**极高**（跨语言 + 3D + golden 三方一致性）。改动波及面大，必须：
  - 后端 `hex_center` + `test_hex_center_formula` + `test_expand_positions_hex_ring_order` 期望值同步改；
  - TS `hexCenter`/`hexGrid` + `gui/test/lattice.test.ts` hexCenter/hexGrid 用例 + `latticeInstances.ts` `defaultOrigin`(hex 保持 [0,0,0])/`gridCenter`(hex 走新 hexCenter) + `estimateLatticeExtent`；
  - golden `hexCenter`/`positions.hex_2x2` 两段重算；`composeCases` 无 hex 用例不受影响。
  - **待 PM/用户确认的显示歧义**：用户列的「行长交替 [2,3,2]」是**点朝上取向**的行模式；顶点+X 取向下
    对称环的水平行长为 `[1,2,1,2,1]`。设计以 **MCNP 顶点+X 蜂窝为权威**（格元几何/3D/expand_positions 三方自洽），
    画布环按顶点+X 蜂窝绘制；若用户坚持视觉 `[2,3,2]`，需整体 90° 旋转显示（另开确认，本批不做）。

---

### 项 6：调色板与画布同屏

- **涉及**：`gui/src/components/LatticeEditDialog.tsx`。
- **行为变化**：删除独立「宇宙调色板」步骤，调色板（`universeList` 色块 + `selectedU` 高亮 + 自定义宇宙号输入）
  常驻「画布涂色」步骤画布左侧/右侧，点选即当前涂色笔。状态 `selectedU` 提升为弹窗级 state（画布 `onCellChange` 直用）。
- **风险**：低。纯 UI 重组；`LatticeCanvas` props 不变。
- **测试**：DOM 用例「调色板点选 → 画布涂色用新笔」1 条。

---

### 项 7：调色板 = void ∪ fill 表去重 ∪ deck 现有宇宙

- **涉及**：`gui/src/utils/lattice.ts`（新纯函数 `collectFillUniverses`）、`gui/src/components/LatticeEditDialog.tsx`
  （`universeList` 构造改为调用纯函数）。
- **行为变化**：调色板宇宙来源合并三路：
  1. `void 0` 常驻（可涂 void，画布特判透明）；
  2. deck cells 的 `u=` 去重（现有逻辑）；
  3. 各格阵 cell 的 `fill_grid` JSON `cells[].u` 去重（导入 17×17 → 选 0/1/2/3，含格位里出现的 universe）。
- **权威契约（纯函数签名）**：
  ```ts
  collectFillUniverses(cells: LatticeCellLike[]): string[]
  // 返回：void "0" 恒在首位，随后 deck u= 去重 ∪ 各 fill_grid.cells[].u 去重，数值升序
  ```
- **golden 期望值（新增段 `collectFillUniverses`）**：17×17 样例输入（deck u=10 + fill_grid cells 含 1/2/3/0）
  → `["0","1","2","3","10"]`。
- **风险**：低。纯前端；不触后端/契约。
- **测试**：TS 3 例（17×17 合并、空 deck、fill_grid 脏 JSON 容错）。

---

### 项 8：分组默认开启 + 状态保持

- **涉及**：`gui/src/components/GeometryTab.tsx`（**当前工作树已实现**：`mcnp_groupbyu_v1` localStorage，初始 `true`，
  `useEffect` 回写）。
- **行为变化/设计确认**：默认 ON；状态存 `localStorage["mcnp_groupbyu_v1"]`（与工作区 `mcnp_workspace_v1` 解耦 →
  **不随导入/清空工作区重置**）。不做 deck 字段持久化（分组是显示偏好，非文档数据）。
- **风险**：低。已实现，仅补验证。
- **测试**：DOM 1 条（toggle → 断言 localStorage 写回；重挂载读回默认 true）。

---

### 项 9：分组头文字可编辑 → 输出 INP 时每 U 组前生成 C 注释

- **涉及（双端）**：
  - 存储：`gui/src/utils/DeckContext.tsx`（deck 加 `universeComments: Record<string,string>`）+ 类型三处同步（CellEditDialog/DeckContext/cellBridge 不涉）；
  - 生成：`app/generator/inp_generator.py`（`_generate_cells` 插 C 注释）+ `app/generator/banners.py`（冻结词汇 `universe_group_banner`）；
  - 解析：`app/generator/parsers/`（core.py/sections.py 识别该 C 注释 → `deck.universeComments`）；
  - UI：`gui/src/components/GeometryTab.tsx`（组头双击内联编辑）+ `gui/src/utils/universeGroups.ts`（组头文案并入自定义文本）。
- **权威契约（C 注释格式，词汇冻结防 R1 漂移）**：
  ```
  C  U-group U=<n>: <user text>
  ```
  放于该 U 组**首个栅元行之前**。生成器按「当前 cell 顺序中相邻同 U 连续段」插入（非全 deck 重排——MCNP 不要求同 U 连续，
  设计不做重排，只按连续段插注释）。`banners.universe_group_banner(u, text)` 为唯一发射源（对齐 F-A 方案 C 词汇冻结）。
- **存储决策**：放 **deck 字段**（非 localStorage）——随工作区保存/导入导出，是文档附属数据；`universeComments` 键名
  snake_case 风格与 deck 其他字段一致。
- **解析/往返（R1）**：`parse-inp` 把匹配 `C  U-group U=` 前缀的 C 行吸收进 `deck.universeComments`（**从 cell 注释/other_cards 路径排除**，
  防被吞）；生成器按 `universeComments` 逐连续段重放 —— `parse→gen→parse` 字节稳定。既有夹具无 `universeComments` → 零影响。
- **golden/round-trip 影响评估**：新增一个带 U 注释的合成夹具 R1 测试（gen→parse→gen 字节不动点）；既有 5 夹具不受影响。
- **GeometryTab 编辑 UI**：组头行双击 → 内联 `<input>`，失焦 `patch({universeComments: {...}})`；
  `groupHeaderLabel(u, count)` 追加可选参数 `comment`（有则显示 `U=n · N 栅元 · 「text」`）。
- **风险**：中。解析器对 `C  U-group U=` 的识别必须在「吸收 cell 注释」之前（行级归一顺序见 `lines.py` C 行保留逻辑）；
  冻结词汇与 banners 同机制，防解析器/生成器两侧词汇漂移。
- **测试**：后端 pytest（生成插注释 / 解析吸收 / R1 新夹具 / 无注释零影响）；前端 vitest（`universe_group_banner` 镜像、组头编辑 DOM 1 条）。

---

### 项 10：无 U 的 cell 进「未分组」组

- **涉及**：`gui/src/utils/universeGroups.ts`（**当前工作树已实现**：哨兵 `UNGROUPED_U=-1`，`groupByUniverse` 兜底 + `groupHeaderLabel`）。
- **行为变化/设计确认**：u 空/空白/非有限 → `UNGROUPED_U` 组，组头「未分组 · N 栅元」；raw 行永不进组；
  拖栅元到未分组组头 = 清空该栅元 u（`resolveDrop` regroup u=-1 → 置空）。未被任何组吞并。
- **风险**：低。已实现，补测试。
- **测试**：`gui/test/universeGroups.test.ts` 补「空 u / 空白 u / NaN u 进未分组」「未分组组头拖入清空 u」2 例。

---

### 项 11：拖拽改 U 失效（弹回）修复

- **根因（已确认）**：`GeometryTab.onDropOnGroup` 原先只 `setCells`（本地视图），未同步 `patch` deck →
  `local→deck` 同步 effect 用旧 deck.cells 覆盖回来 → 拖拽后回弹。
- **修复路径（当前工作树已实现）**：`onDropOnGroup` 内 `setCells` 同时 `patch({ cells: localToDeckCells(nextCells) })`，
  单一权威（deck）即时同步（参照其他 cell 编辑：`applyMatFromPicker` 等同样走 setCells+patch 管线）。
- **涉及**：`gui/src/components/GeometryTab.tsx` + `gui/test/geometryGroupDrag.dom.test.tsx`（新文件）。
- **风险**：低。注意 `nextCells` 从**当前 `cells` state** 计算（勿用闭包旧值——用 `setCells(prev => …)` 内构造再 patch）。
- **测试**：DOM 用例「拖栅元到组头 → deck.cells 对应行的 u 已改（读 context/mock fetch）」1 条；「拖到未分组组头 → u 清空」1 条。

---

### 项 12：保存时 fill_grid.raw = cellsToRaw(cells) 全路径核验 + 体积决策

- **全路径核验**：
  1. `LatticeEditDialog.handleSave`：`fg.raw = cellsToRaw(fg)` ✓（已实现）；
  2. `CellEditDialog`「打开栅格编辑器」→ 同对话框保存 ✓（同路径）；
  3. 导入路径：`parse-inp` → `parse_fill_tokens` 产出 `fg.raw` = 原始 token 流 ✓（导入保留源简写）。
  缺口：**大格阵体积**——`cells` 全展开 JSON。
- **体积评估**：17×17（289 格位）`serializeFillGrid` ≈ 289 × ~40B ≈ **~11.6KB**（可接受）；
  BEAVRS 全堆芯 ~2.8 万格位 ≈ **~1.1MB**（不可接受，localStorage/网络均超）。
- **设计决策（推荐：两者都要）**：
  1. **nR 压缩（`compressRaw`）**：`cellsToRaw` 后对条目 token 流做「连续重复 run → `u nR`」回缩
     （语义与 `parse_fill_entries` 的 `nR=前一条目再重复 n 次` 一致）。**R1 不动点证明**：压缩流 → parse 展开 →
     cells 相等 → 再压缩 = 同串（压缩是幂等不动点）；`format_fill_cards` raw 优先回放。**仅编辑器保存路径启用**
     （`LatticeEditDialog.handleSave` 设 `fg.raw = compressRaw(cellsToRaw(fg))`）；导入路径保持源 raw 原样
     （不重写，防 `parse→gen→parse` 字节漂移）。
  2. **体积告警（前端 threshold）**：`serializeFillGrid` 序列化长度 > 64KB 或 `cells.length > 8000` →
     LatticeEditDialog 保存前非阻塞提示「格阵体积过大（约 N KB），保存后工作区可能变慢」。
- **涉及**：`gui/src/utils/lattice.ts`（新 `compressRaw`）、`LatticeEditDialog`（保存用压缩 + 告警）。
- **golden 期望值（新增段 `compressRaw`）**：`["1","1","1","2","2"]` → `"1 2r 2 1r"`（nR = 再重复 n 次语义）；
  `parse_fill_entries(["1","2r","2","1r"])` 展开回 `[1,1,1,2,2]`。
- **风险**：中。压缩仅编辑器保存路径，导入/往返不改 → R1 安全；但**既有 17×17 UI 编辑保存会改写 raw**（源 `17r` 简写
  保留——`compressRaw` 对 17 个连续 1 输出 `1 16r`，与源 `1 17r` 字面不同但 parse 等价）。golden 补该等价断言。
- **测试**：TS `compressRaw` 幂等 + parse 往返等价；前端体积告警 DOM 1 条。

---

### 项 13：循环嵌套检测（后端 status="cycle" + 链；前端保存前阻止）

- **涉及（双端）**：
  - 后端：`app/lattice.py` 新增 `detect_fill_cycle(sub_by_u)`；`compose_lattice_tree` 递归前拦截；`api_server._handle_preview_lattice` 透传 cycle/chain。
  - 前端：`gui/src/utils/lattice.ts` 新增 `detectFillCycle`（纯函数镜像）；`LatticeEditDialog.handleSave` 判环阻止 + 提示。
- **权威算法（DFS 判环，基于 sub_by_u fill 图）**：
  ```
  nodes = 所有 universe 号（sub_by_u 键）
  edge U→V：universe U 中任一 cell，其 fill_grid(kind=lattice/translated).cells[].u == V
             或 fill 单值 == V（V≠"0"/""）
  DFS(U, path, state):  # path = 当前递归栈（栈内成员表 visited_in_stack）
      U ∈ path → 找到环：chain = path[path.index(U):] + [U]，status="cycle"
      递归深度 > MAX_LATTICE_DEPTH → 仍按 depth_limit（不再加深）
  ```
- **权威契约（返回结构，双端镜像）**：
  ```
  detect_fill_cycle(sub_by_u) -> { "cycle": bool, "chain": list[str] }
  # chain 形如 ["1","2","1"]（U=1 → U=2 → U=1）；无环 → {"cycle":false, "chain":[]}
  ```
- **`compose_lattice_tree` 行为变化**：入口（`_expand_lattice` 前）对可达子图先 `detect_fill_cycle`；
  命中 → `return {status:"cycle", cycle:chain, tree:[], leafInstances:[], count:0, lattices:[], detailViable:True}`（**不递归**，防无限/超时）。
  `MAX_LATTICE_DEPTH`/`MAX_TOTAL_INSTANCES` 仍为深度/规模守卫（cycle 优先判定）。
- **api.yaml diff（preview-lattice 响应）**：
  ```diff
  - limit: { type: string, enum: [ok, depth_limit, too_many] }
  + limit: { type: string, enum: [ok, depth_limit, too_many, cycle] }
  + cycle: { type: boolean, description: "嵌套 fill 存在循环引用" }
  + chain: { type: array, items: { type: string }, description: "循环链 universe 号序列，如 [1,2,1]" }
  ```
  契约闸门 HTTP 用例补 1 条（cycle deck → status 200 + limit=cycle + chain 断言）。
- **前端本地判环（免端点）**：`LatticeEditDialog.handleSave` 调 `detectFillCycle`（基于当前 deck cells 构造 sub_by_u 等价物）；
  命中 → 阻止保存 + 提示：
  「U=1 的格元填了 U=2，而 U=2 的格元又引用 U=1，存在循环嵌套」。
- **golden 期望值（新增段 `cycle`）**：
  ```json
  { "id": "cycle_a_b_a",
    "sub_by_u": { "1": [{ "cellNum": 11, "material": "0", "fill": "2", "fill_grid": null }],
                  "2": [{ "cellNum": 21, "material": "0", "fill": "1", "fill_grid": null }] },
    "expected": { "cycle": true, "chain": ["1", "2", "1"] } },
  { "id": "no_cycle_tree",
    "sub_by_u": { "1": [{ "cellNum": 11, "material": "0", "fill": "2", "fill_grid": null }],
                  "2": [{ "cellNum": 22, "material": "1", "fill": "", "fill_grid": null }] },
    "expected": { "cycle": false, "chain": [] } }
  ```
- **风险**：中。cycle 检测必须在 compose 递归入口做（子格阵引用父格阵也可能成环，DFS 需覆盖全部可达子图）；
  api.yaml limit enum 加值对既有闸门是增量（向后兼容）。
- **测试**：Python `test_detect_fill_cycle`（A→B→A / A→B→C→A / 自环 A→A / 无环）/ `test_compose_lattice_tree_cycle`；
  TS `detectFillCycle` 镜像 3 例 + 保存阻止 DOM 1 例。

---

### 项 14：删除「真空栅元不参与 STL」约束 + 补 skip 单值 fill cell

- **权威分类规则（已确认，不可违背）**：见 §3.1。
- **涉及（后端）**：`gui/backend/api_server.py`：
  1. `build_cells_data`（254-320 行）：跳过规则从 `if has_fill_grid: continue` 扩为——
     ```
     if str(cell.get("fill") or "").strip(): continue      # 单值 fill=U（含 fill="0"）
     if cell.get("fill_grid"): continue                    # 格阵 fill（现有）
     if str(cell.get("imp_n") or cell.get("impN") or "").strip() == "0": continue  # graveyard（规则5）
     ```
     `include_void=True`（preview-3d 主路径）时**真空（material=0、无 fill 无 u）保留并产 STL**（规则4）——
     现有 `if not include_void and mat=="0": continue` 已正确，`include_void=True` 分支不动。
  2. **调用点 flip 清单**：
     - `_handle_preview_3d`（2049-2051 注释 + 2062 行）：已传 `include_void=True` ✓（void STL 出得来）；
       **新增**：进 `build_cells_data` 前 cell_list 已在 build 内按 fill/imp 过滤（不额外处理）。
     - `_build_one_universe`（572 行）：`include_void=False` → **改 True**（universe 叶 void 格元也产透明占位 STL，规则4）；
       **新增 skip**：`_build_one_universe` 收集 uni_cells 时 `if _cell_fill(c): continue`（单值 fill cell 不产自身 STL，规则1/7）；
       `_cell_u` 判断加 `fill` 读取。
     - STEP 导出 / 截面：**保持 `include_void=False`**（“不做”边界，见 §5）。
  3. **graveyard 口径**：`imp:n==0`（含 `impN` camelCase）的 cell 在 `build_cells_data` 一律跳过（规则5）；
     preview-3d 前端 `Preview3D` 若仍按材料过滤，无需改（void 透明显示由 `include_void=True` + 前端透明材质承担）。
- **与 preview-lattice 装配的边界**：preview-3d 路径（`/api/preview-3d`）只渲染**非装配实体**（fill 空 + 非 imp0），
  格阵/单值 fill 的装配内容由 `/api/preview-lattice`（项 15）负责，两路径互不产出重复 STL。
- **风险**：中高。skip 单值 fill 是**行为变化**（此前 fill cell 会产实体 STL = 用户看到的「大紫方块」）；void 参与 STL
  会使巨型边界 void（如 `so 1000`）撑大包围盒拉远相机——相机适配属项 15 前端（`frameCamera` 用 leafInstances bbox，
  void 叶参与 bbox 计算需确认，设计建议 **void 叶占位不计入取景 bbox**，防「针尖」）。`preview-3d` 既有 STL 非空回归
  （cell1=96 三角）不受影响（fill 空 + 非 void 实体仍产）。
- **测试**：pytest `build_cells_data` skip fill/imp0/保留 void 3 例 + `_build_one_universe` void 叶非空 1 例 + STEP include_void=False 1 例。

---

### 项 15：格阵按 FILL 装配显示（真实 GUI 3D 主路径接通 preview-lattice）

- **涉及（双端）**：`gui/src/components/Preview3D.tsx`（默认路由 + 边界/切换时机）、
  `gui/src/components/Preview3DLattice.tsx`（消费装配数据，现有）+ `gui/backend/api_server.py` + `app/lattice.py`（`_expand_universe` 修正）。
- **用户可见问题**：主预览把装配容器（fill=10 窗口 cell / fill_grid 格阵 cell）渲染成实体块（紫方块），
  universe pin 单独摆出 → 应改为 **FILL 装配**：容器不渲染自身，格位按 fill 装配 universe 内容。
- **主路径接通**：
  - `Preview3D`（主 GUI）判定：`rawCells` 中任一 `fill_grid` 非空 **或任一 `fill` 非空且 fill≠"0"** →
    **默认进入格阵装配视图**（渲染 `Preview3DLattice`），不再停在 preview-3d 单 cell 路径；
    `latticeView` toggle 保留（单 cell 视图 / 装配视图切换）。
  - `Preview3DLattice`：消费 `/api/preview-lattice`（现有：`leafInstances` FLAT 绝对坐标 + `lattices[].universes` STL，
    InstancedMesh 装配）；`detailViable=false` / 叶数超 `DETAIL_MAX_INSTANCES=20000` → 色块总览（现有）；
    相机 `frameCamera` 用 leafInstances bbox（现有）——**void 叶不计入取景 bbox**（与项 14 相互作用）。
  - **preview-3d 单 cell 路径的边界**：无任何 fill/fill_grid 的 deck 仍走 `Preview3D` 单 cell（preview-3d 端点）；
    有装配的 deck 装配视图内不重复请求 preview-3d。
- **后端 `_expand_universe` 与确认规则一致性核对（含修正点）**：
  | 确认规则 | `_expand_universe` 现状 | 修正点 |
  | :-- | :-- | :-- |
  | 规则1 带 fill 的 cell=装配容器不自产 STL | fill_grid lattice → 递归 ✓；fill=X 单值 → `if fv and fv!="0": recurse` ✓（但 `fill="0"` 落空） | **`fill="0"` 的 cell 也跳过 leaf 分支**（`if fv != ""` 即算装配容器） |
  | 规则2 叶级 = material≠0 且无 fill | `mat not in ("0","")` 且无 fill 才 leaf ✓ | — |
  | 规则4 纯 void 参与 STL | 当前 **跳过**（void 不产 leaf） | **补 void leaf**：material="0" 且无 fill → 产 `{leaf, void:true}`，前端透明渲染 |
  | 规则5 graveyard 排除 | 无 imp 信息 | handler 在构造 sub_by_u 时**过滤 imp_n=="0" 的 cell**（与项 14 graveyard 口径一致） |
  | 规则7 任何带 fill 的 cell skip | fill="0" 会落 leaf 分支 | 同上修正（统一 `fill` 非空即容器） |
- **golden 期望值（新增段 `assembly`，单值 fill 装配 + 嵌套递归叶级）**：
  ```json
  { "id": "single_fill_assembly",
    "outer_fg": null,
    "sub_by_u": {
      "10": [{ "cellNum": 10, "material": "0", "fill": "",   "fill_grid": null, "surface_expr": "1 2 3 4", "u": "10" }],
      "1":  [{ "cellNum": 101, "material": "1", "fill": "",  "fill_grid": null, "surface_expr": "-1" }]
    },
    "window_cell": { "cellNum": 30, "material": "0", "fill": "10", "fill_grid": null },
    "expected_leaves": [ { "cellNum": 101, "u": "1", "x": 0, "y": 0, "z": 0, "depth": 1 } ],
    "expected_lattices": [] }
  ```
  （窗口 cell `fill=10` 不自产 STL；universe 10 的叶 cell 101 作为装配叶。）
- **风险**：高。主预览默认路由变化是 UI 行为大改；`_expand_universe` 补 void leaf 会改变 `count`（BEAVRS 若 void 叶多可能
  顶到 DETAIL 上限——`DETAIL_MAX_INSTANCES` 判定在 void 叶计入前，设计确认 void 叶**计入 count** 但可被 `detailViable` 总览兜底）；
  前端透明材质 + void 叶不取景防「针尖」。
- **测试**：pytest `_expand_universe` void leaf / fill="0" skip / imp0 过滤 3 例 + compose 单值 fill 装配 golden 消费；
  vitest `Preview3D` 路由判定（有 fill → 默认装配视图）1 例 + void 叶透明 + 取景排除 2 例。

---

## 2. 跨语言锁死清单（后端/前端逐位一致，缺一不可）

| # | 锁点 | 权威值/公式 | Python 文件 | TS 文件 |
| :-- | :-- | :-- | :-- | :-- |
| L1 | hexCenter 顶点+X 蜂窝 | `x=i·p·√3/2, y=j·p+(i%2)·p/2` | `lattice.py hex_center` | `lattice.ts hexCenter/hexGrid` |
| L2 | hexRingRows 环行长（语义=+30° 共线方向） | `[r+1+min(j,2r-j)]`，总和 `1+3r(r+1)` | `lattice.py hex_ring_rows` | `lattice.ts hexRingRows` |
| L3 | -N:M 范围映射 | `token="-L:R"`，`dims=L+R+1`，`expand_positions` 中心 `((i-(nx-1)/2)·px)` | `lattice.py _range_count`+新 `_dir_counts` | `lattice.ts rangeFromDirCounts/dirCountsFromRange` |
| L4 | RPP/BOX/RHP/HEX 宏体自动生成卡 | rect→`rpp …`；hex→`rhp V H R1`（项 4 语法） | `validate_lattice_surfaces` 接受 | `lattice.ts autoGenerateSurfaces` 宏体版 |
| L5 | RHP/HEX 参数合法性 | 参数数∈{9,12,15,18}；\|H\|>0；R1⊥H；两两 60° | `lattice.py _validate_lat2` 扩展 | 镜像 `validateLatticeSurfaces` 本地判定（可选） |
| L6 | cycle 响应 | `detect_fill_cycle` → `{cycle,chain}`；`compose_lattice_tree` status="cycle" | `lattice.py detect_fill_cycle` | `lattice.ts detectFillCycle` |
| L7 | 3D 分类规则 1-7 | 带 fill（含 fill="0"）跳过自身；叶=material≠0 无 fill；void 参与；graveyard 排除 | `build_cells_data`/`_build_one_universe`/`_expand_universe` | `Preview3DLattice` 透明 void / 不取景 |
| L8 | compressRaw nR 压缩 | `[1,1,1,2,2]`→`1 2r 2 1r`（nR=再重复 n 次） | `parse_fill_entries`（消费侧） | `lattice.ts compressRaw`（生产侧） |
| L9 | 宏体 auto-gen 互斥 + 子预览 | 自动/手填互斥；自动仅单宏体 | `validate_lattice_surfaces` 单宏体接受 | `LatticeEditDialog` + `MacrobodyPreview` |

> 每个锁点都必须有 golden 期望值（§1 各 golden 段）；Python `test_lattice.py` 与 TS `lattice.test.ts` 读同一
> `latticeGolden.json` 断言（沿用阶段2/3 模式，未产出段 skip）。

---

## 3. 附：权威约束快查

### 3.1 已确认 3D 预览 STL 生成 cell 分类规则（项 14/15 设计依据，不可违背）
1. 带 fill（`fill` 非空 **或** `fill_grid` 非空，含 `fill="0"`）= 装配容器，自身不产 STL。
2. 递归展开 fill → 叶级实体 cell（material≠0 且无 fill）才产 STL。
3. 普通实体 cell（mat≠0、无 fill 无 u）→ 直接产 STL。
4. 纯 void cell（mat=0、无 fill 无 u）→ 参与 STL（透明占位）——项 14「删 void 约束」唯一适用范围。
5. graveyard（imp=0 外围）→ 不渲染。
6. universe U 几何 = 所有 u=U 的 cell 的 STL 集合。
7. **项 14 关键缺口**：build_cells_data 当前只 skip `fill_grid` 非空，**没 skip `fill=U` 单值 cell** → 补成「任何带 fill 的 cell 都跳过自身 STL」。

---

## 4. api.yaml diff 摘要（本批唯一契约变化 = 项 13）

```
/api/preview-lattice 响应：
  limit: enum 增 "cycle"
  + cycle: boolean（循环引用存在）
  + chain: array<string>（循环链 universe 号序列）
```
项 15 复用 preview-lattice（无新端点）；项 13 前端本地判环（免端点）；项 14/15 无契约变化（preview-3d 响应结构不变）。
**Wave 2 由后端在实现时同步落盘 api.yaml + 契约闸门 HTTP 用例。**

---

## 5. 「不做」边界（明确排除）

1. **STEP 导出**：保持 `include_void=False`（void 无实体可导出；`/api/export-step` 语义不变）。
2. **render:false**：保持 skip（`build_cells_data` 的 `if not render: continue` 不动）。
3. **`/api/preview-3d` 响应结构**：不改（void STL 通过 include_void=True 天然产出，字段不变）。
4. **本批不改** `docs/contracts/api.yaml` / `gui/src/utils/__golden__/latticeGolden.json` / 任何实现代码（Wave 2 落地）。
5. **画布/3D 整体 90° 旋转显示**：项 5 显示歧义待 PM/用户确认后另排期，本批按顶点+X 蜂窝权威公式。
6. **preview-3d 主窗口 deck 同步到预览窗口**（阶段遗留中高风险项）：不属本批。
7. **不新增端点**：cycle（前端本地判环）、装配显示（复用 preview-lattice）、体积（前端本地）。

---

## 6. 测试清单（pytest / vitest 各补什么）

### 后端 pytest（tests/unit/test_lattice.py + tests/parser/integration）
| 用例 | 归属项 |
| :-- | :-- |
| `test_dir_counts_from_range`（-N:M 映射 + 反派生一致，3 例） | 2 |
| `test_validate_rhp_params`（9/12/15/18 参合法；\|H\|=0、R1 非 ⊥H、R2/R3 夹角错 → 拒） | 4 |
| `test_rhp_extent_9params_infer`（9 参 RHP 推断 R2/R3 → AABB 与 12 参一致） | 4 |
| `test_hex_center_flat_top`（新公式权威值，pitch=2/√3） | 5 |
| `test_expand_positions_hex_flat_top`（golden `positions.hex_2x2` 新值） | 5 |
| `test_compose_lattice_tree_cycle`（A→B→A → status="cycle"+chain） | 13 |
| `test_detect_fill_cycle`（自环/两元环/三元环/无环） | 13 |
| `test_build_cells_data_skip_fill_single`（fill="10" / fill="0" 跳过；imp_n=0 跳过；void 保留产 STL） | 14 |
| `test_build_one_universe_void_leaf`（void 叶产透明 STL；fill cell 跳过） | 14/15 |
| `test_expand_universe_void_leaf_and_fill0`（规则4/7 修正） | 15 |
| `test_single_fill_assembly_golden`（golden `assembly` 段消费） | 15 |
| `test_universe_group_comment_roundtrip`（新夹具：`C  U-group U=` 插注释 → parse 吸收 → gen 字节稳定 R1） | 9 |
| 既有五夹具 R1 不动点（17×17/BEAVRS/hex_lattice/prob41c/inp24）+ kitchen_sink R4 不回退（**保持绿**） | 全部 |

### 前端 vitest（gui/test/）
| 用例 | 归属项 |
| :-- | :-- |
| `rangeFromDirCounts/dirCountsFromRange` 对称（3 例） | 2 |
| `autoGenerateSurfaces` 宏体版（rect→RPP / hex→RHP，编号顺延） | 3 |
| `hexCenter/hexGrid` 新公式权威值（golden hexCenter 段） | 5 |
| `collectFillUniverses`（17×17 合并 / 空 deck / 脏 JSON） | 7 |
| `groupByUniverse` 未分组兜底（空 u/空白/NaN）+ 拖入未分组清空 u | 10 |
| `compressRaw` 幂等 + parse 等价 | 12 |
| `detectFillCycle` 镜像（3 例） | 13 |
| `universe_group_banner` 镜像 | 9 |
| DOM：LatticeEditDialog 4 步状态机 + 第 0 步含 k；调色板同屏点选涂色；体积告警；保存前 cycle 阻止提示 | 1/6/12/13 |
| DOM：geometryGroupDrag（拖组头改 u → deck patch；拖未分组清空 u） | 11 |
| DOM：groupByU toggle → localStorage 持久化 | 8 |
| DOM：Preview3D 有 fill → 默认装配视图；void 叶透明；取景排除 void | 15 |

---

## 7. 分派建议（Wave 2 拆活）

- **后端 Wave 2a**（项 2/4/5/9/13/14/15 后端 + golden 消费 + api.yaml + pytest）：lattice.py（`_dir_counts`、`_rhp_extent` 9 参、hex 公式、
  `detect_fill_cycle`、`_expand_universe` 修正）、api_server.py（`build_cells_data`/`_build_one_universe`/`_handle_preview_lattice` cycle）、
  inp_generator+banners+parsers（U 注释）、**api.yaml diff（项 13）+ 契约闸门**。
- **前端 Wave 2b**（项 1/2/3/4/5/6/7/9 UI/12/13/15 前端 + golden 写盘 + vitest）：lattice.ts（hex/range/compressRaw/detectFillCycle/
  collectFillUniverses/autoGenMacrobody）、LatticeEditDialog（4 步 + 互斥 + 调色板同屏 + 方向块数 + RHP 双模式 + 判环阻止）、
  LatticeCanvas/Preview3DLattice/Preview3D（装配路由 + void 透明）、GeometryTab（组头编辑）、MacrobodyPreview、**latticeGolden.json 全量更新**。
- **golden 写盘人**：前端（新增段 dirCounts/macrobody/rhpMacro/collectFillUniverses/compressRaw/cycle/assembly + 重算 hexCenter/positions.hex）；
  后端只读断言，未产出段 skip。
- **api.yaml 落地人**：后端（项 13）。
