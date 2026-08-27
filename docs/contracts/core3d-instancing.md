# 全堆芯 3D 实例化渲染契约（OWEN 思路移植 + 轴向外壳降级）

> 契约人：架构师 | 施工方：后端 + 前端 | 分支：自当前 HEAD 拉出（命名 `perf/core3d-instancing`）
> 日期：2026-08-25 | 状态：**计划书（待 PM 裁决后动工）**
> 目标：BEAVRS 全堆芯 3D 预览**能渲染、位置正确、不锁死详细、驱动独显 GPU 实例化**。
> 依据：`docs/contracts/preview3d-performance.md` 之外的格阵实例化链路；OWEN（`D:\MCNP\owen-1.4.1`，MIT）`src/preview/budget.ts` 与 `src/preview/codes/mcnp.ts` 移植。
> 强约束：`app/lattice.py`、`gui/src/three/latticeInstances.ts`、`tests/unit/test_lattice.py`、`gui/test/latticeInstances.test.ts` 判定为 binary，只能用 PowerShell `[System.IO.File]::ReadAllText/WriteAllText` 改写，不做 `edit`/`write` 直改。

---

## 0. 一句话结论（先看这个）

**你问"实体超限后把每个 U 打包成只有外壳的 STL"——方向正确，但它只解决"几何重"，不解决"数量爆炸"。**
完整方案 = 三步，缺一不可。**但在此之前必须先修一个更根本的 bug：堆芯格阵 z 位置基准错（色块/详细整体被压在 z=0，而 BEAVRS 堆芯实际在 [0,460]、中心 +230）——见 §0.5。**

1. **轴向折叠（数量杀手）**：把 BEAVRS 554 万叶（每个 pin 的 fuel/plenum/grid/dashpot/end plug 各算一段）折叠成几十万 pin 位置。**这一步才真正把数量降到 GPU 能吃的量级。**
2. **每 universe 外壳 STL / disc（几何降级）**：超限时每个 universe（pin/格阵）用一个"外壳/单盘"低模几何取代内部全部同心层。**这是你说的"打包外壳 STL"。** 它解决"每实例三角形数"，不解决"实例数量"（见契约 §1.2）。
3. **InstancedMesh 实例化（渲染通道）**：前端按 `(u, cellNum)` 分组、组内 `setMatrixAt` 复用一个几何。**这步我们已具备**（`latticeInstances.ts`），缺的是喂进去的"少而精"的数据，不是渲染代码。

> 更正上一轮误解：**fill 位置算法目前还没移植到项目**。此前只做了 outer_bound 解析 + 色块裁剪 + z 高度恢复，与 OWEN `placeUniverse` 无关。

### 0.5 步骤 0——堆芯格阵 z 位置基准（最高优先，位置不对则以上全白搭）

**现象（用户实测）**：全堆卡定义的外壳在 Z 轴 >0 处（BEAVRS `cell 343`：`cz 187.96` + `700 pz 0` + `730 pz 460` → **z ∈ [0,460]，中心 +230**），但色块总览/详细渲染中心在 z=0。

**根因（已钉死，`app/lattice.py`）**：
1. `expand_positions`（:1015/:1019）算格位 z：`cz = (k - (nz-1)/2)*pz`。根格阵 `fill=-8:8 -8:8 0:0` 是单层 `nz=1, k=0` → **`cz = 0`**。
2. `compose_lattice_tree` `root_ctx = {"base": (0,0,0)}` → 根格阵整体 z 基准 = 0。
3. 色块总览用根格阵 `positions` 的 z（=0）；详细叶 `abs_z = bz + pos.z`，`bz` 从 `(0,0,0)` 起 → 也压在 z=0。
4. 之前"z clamp 到 21.5 又撤销"那件事的真根因：**不是 height 该 clamp，而是 z 基准原点错**（该用容器 z 中点 230，我却在 z=0 上改高度，方向完全错了）。

**正确做法（对齐 OWEN）**：
- OWEN `findZPlaneBounds` 读全局 pz 上/下界 → `zmid=(zmax+zmin)/2=230`，`placePin(..., zCenter: zmid, height)`——**每个格位放在容器 z 中点**。
- 移植：根格阵/各格阵的 z 基准（`base.z` / `expand_positions` 的 z 偏移）改为**容器 cell 的 z 范围中点**（`_scan_embedding_z`/`_scan_lattice_z` 已能扫出 `z_min/z_max`；比 OWEN 更准——我们的 extent 直接解出 `[0,460]`）。单层格阵（nz=1）不要让 `cz` 恒为 0，而是把格位 z 叠加到容器 z 中点。
- `_resolved_extent` z 覆盖（:661-677）：`req_height` 覆盖只是"改高度 span"，**不应把 center 拉到 0**——需保留容器扫描到的 z 中点（`300 pz 0 / 730 pz 460` → center +230）。

**验收**：BEAVRS 色块总览中心 z = +230（跨 [0,460]）；`inOuter` 裁剪、`cz 187.96` 不超壳不因此被误剔除；`z` 高度=460。

**测试**：`tests/unit/test_lattice.py` 增 `expand_positions` 单层格阵 z 基准用例（容器 z 中点而非 0）；`gui/test/latticeInstances.test.ts` 对应。

---

## 1. 背景与问题根因（实测锚定）

### 1.1 两条独立链路（别混淆）
- **FreeCAD-CSG 链路**：`/api/preview-3d` → 逐栅元布尔 → STL（`freecad_preview.py`）。契约见 `preview3d-performance.md`。**本轮不碰。**
- **格阵实例化链路**：`/api/preview-lattice` → `compose_lattice_tree`（`app/lattice.py`）→ `leafInstances` JSON → 前端 `buildLatticeInstances`（`latticeInstances.ts`）InstancedMesh。**本轮主体。**
  - BEAVRS 全堆芯嵌套 3 层：容器 cell343（`cz 187.96` 外壳）→ 堆芯格阵 u=100 `60 -61 62 -63`（pitch 21.50364、17×17）→ 组件格阵 u=201/…（17×17、pitch 1.26）→ pin universe u=1/2/…。

### 1.2 根因（为什么 554 万把内存拉满、GPU 没被喂到）
| # | 现象 | 根因 |
| :--- | :--- | :--- |
| 1 | count 每轮贴阈值（50万→100万→200万→10亿，实测 5549815） | BEAVRS 真实叶数 554 万：**每个 pin 的每个轴向段（fuel/间隙/包壳/plenum/grid/dashpot/端塞）都算一个叶实例**，不折叠 |
| 2 | GPU1 几乎不动、内存拉满 | 我们后端把 554 万 `leafInstances` **传 JSON 到前端**（几百 MB）+ JS `JSON.parse`/堆分配 → 内存爆；**InstancedMesh 实例化渲染根本没被喂到** |
| 3 | 调大阈值追不上 | 阈值只放行"更多实例"，**不减少实例数**——调 10 亿照样 554 万，只是不再截断，JSON 照样几百 MB |

对比 OWEN：**本地解析 + 轴向折叠 + disc 单盘 + InstancedMesh**，靠 GPU 实例化（`budget.ts` 默认 `DEFAULT_MAX_INSTANCES = 1_500_000`，BEAVRS ~56k pin 位置，展开轴向后 ≈0.8M，径向完整 ≈170k，都能吃下）。关键差异是**OWEN 在源头就折叠 + 降级，不把数百万条实例塞给 JSON**。

---

## 2. 方案：OWEN 三件套移植到本项目

### 2.1 移植 OWEN 的轴向 stack 折叠（数量必杀——本契约核心）
`codes/mcnp.ts` 的做法（我已读透）：
- `buildAxialStack(group, surfaces)`：universe 里单-fill 子 universe + PZ 平面界定 → 排序成 `AxialSegment[{zmin,zmax,universe}]`。**≥2 段才算 stack**（否则普通径向 pin 不动）。
- `placeEntry(uid, cx, cy)`：
  - `axialOn`（用户开轴向分层时）：**逐段展开** `placePin(seg.universe, …, (zmin+zmax)/2, h)`——真实 z 结构。
  - 否则（**默认，折叠**）：取最高段（active fuel）当"代表"`placePin(rep.universe, cx, cy, zmid, height)`——**一个 pin 一段，就这一个！**
- 结果：554 万段 → **~8.4 万 pin 位置**（289 组件 × 289 pin × 每 pin 1 段；去掉 void/控制棒 = 真实 ~56k）。这是数量量级跃迁，也是"挑战独显"的前提。

**移植到本项目（后端 `app/lattice.py`）**：
- 新增 `_build_axial_stack(cells, surf_text)`：对某 universe 的 cells 识别"单-fill 子 universe + PZ 包围"的段，排序。仿 OWEN `buildAxialStack`。
- `compose_lattice_tree` / `_expand_universe` 增加轴向折叠开关：默认 `axial=false`（折叠，取最高段为代表）；`axial=true`（展开分段）。折叠时把 `_expand_universe` 对"同一宇宙内多段"的重复叶合并为一段代表叶。
- `leafInstances` 数量从 554 万 → 几十万，JSON 从几百 MB → 几 MB。

### 2.2 移植 OWEN 的 LOD 预算降级（决定"折叠到什么程度"）
`budget.ts` `planRender`（我已读透）：给定 `totalPins`/`avgLayers`/`axialSegments`/`detail`/`axial`/`maxInstances`，选最富保真度，**降级顺序：**
1. 请求级（layers 径向 + axial）最贵；
2. **先 `layers → disc`**（径向同心层折叠成单盘，保留轴向）——最省的大动作；
3. **再折叠轴向**（保留每个 pin）。
关键不变量：**永远不丢 pin**（所有位置仍画），只降几何细节。超上限才 `capped` 截断。

**移植到项目**：后端 `compose_lattice_tree` 前用等价预算函数决定 `detail=layers|disc` + `axial`，把选择写进 `fidelity`（比对现有 `detailViable`/`limit`）。前端据 `fidelity` 渲染：
- `layers`：每 universe 用内部 STL（现状详细模式）；
- `disc`：每 universe 用**外壳/单盘**几何（见 §2.3）。

### 2.3 每 universe 外壳 STL（你的"打包外壳"方案——几何降级）
OWEN disc 模式：`placePin` 用 `radius = min(subPitch*0.47, max(layer radii))` 一个圆柱代表整 pin，颜色取主导实心层、组件取 pin 类别（fuel/guide/instrument）。**不是全部实体。**

**移植到项目**：超限/选 disc 时，后端给每个 universe（pin 格阵）**生成一个"外壳/盘 STL"**（低模：一个圆柱/盒包络该 universe 全部实体，或用 `radius=min(subPitch*0.47, max cell radius)` 单盘），而不是展开全部内部同心层。前端 `buildLatticeInstances` 该 universe 只用这一个外壳几何实例化。

> 注意：这解决"每实例三角形太多"，**不解决"实例数量多"**。数量靠 §2.1 轴向折叠。两者必须同时上，缺一 BEAVRS 仍旧爆（要么几何重、要么数量多）。

### 2.4 InstancedMesh（渲染通道——已具备，未缺）
`latticeInstances.ts` `buildLatticeInstances` 已按 `(u, cellNum)` 分组、组内 `setMatrixAt` 复用几何。**不用重写**，只需：
- 数据源换#2.1折叠后的几十万 `leafInstances`（而不是 554 万）；
- `universeStl` 换#2.3外壳 STL（disc 模式下）；
- 现存 `DETAIL_MAX_INSTANCES`（2万）改为按 `fidelity`/`planRender` 结果决定，不再一刀切 auto-overview。

---

## 3. 实施分解（每步含门禁）

> 施工顺序：步骤 0（z 基准）→ 后端折叠 → 外壳 STL → 前端接线 → 打包部署验证。每步 pytest/vitest/tsc 全绿才进下一步。

### 步骤 0：堆芯格阵 z 位置基准修正（`app/lattice.py` + `api_server.py`）
- `expand_positions`：单层格阵格位 z 不再恒为 0；把 z 偏移叠加到容器 cell 的 z 中点（`_scan_embedding_z`/`_scan_lattice_z` 已能解出 `[0,460]` → center +230）。
- `compose_lattice_tree` `root_ctx["base"]`：z 取容器 z 中点（而非 0）。
- `_resolved_extent` z 覆盖（:661）：`req_height` 只改 span，保留容器 z 中点（不把 center 拉到 0）。

**门禁**：`tests/unit/test_lattice.py` 单层格阵 z 基准用例；BEAVRS 色块中心 +230、跨 [0,460]、不误剔。

### 步骤 1：后端轴向识别与折叠（`app/lattice.py`）
- 新增 `_build_axial_stack` / `_axial_segments_for_universe`（PZ 包围 + 单-fill 识别 + 排序）。
- `compose_lattice_tree` / `_expand_universe` 加 `axial: bool` + `axial_fold` 参数；折叠时每 pin 取最高段为一个代表叶（`mat`/`u`/`cellNum` 用该段）。
- `MAX_TOTAL_INSTANCES` 语义确认：折叠后应显著低于阈值（几十万 < 50万）。

**门禁**：
- `tests/unit/test_lattice.py`：新增轴向折叠用例（构造含 PZ 段 stack 的 universe，断言折叠后 `leafInstances` 数 = pin 位置数、无重复段；`axial=true` 时展开段数）。
- 已知 BEAVRS 折叠后 count（后端冒烟）≈ 8 万级（不再贴 50 万阈值）。**取消"调阈值追数量"的旧思路**。

### 步骤 2：disc/外壳 STL 生成（`app/lattice.py` + `api_server.py`）
- `_expand_universe` 产 leaf 时若 `fidelity.detail == "disc"`，该 universe 的 STL key 指向一个**外壳/单盘几何**（`radius=min(subPitch*0.47, max radius)`、`height=格元盒 z`），由后端生成（复用现有 STL 结构，只是几何简化为单盘/圆柱包络）。
- `api_server.py:_handle_preview_lattice`（:2735 组装 `entry["universes"]`）：disc 模式下为每 universe 供外壳 STL；`fidelity` 字段写进响应（`{detail, axial, estimate, requestedEstimate, simplified}`）。

**门禁**：
- `tests/unit/test_lattice.py`：disc 模式每 universe 只有一个外壳几何 key；外壳半径/高度断言。
- `api_server` 响应含 `fidelity`；`count` 折叠后为几十万。

### 步骤 3：前端接线（`gui/src/three/latticeInstances.ts` + `gui/src/components/Preview3D.tsx` + `Preview3DLattice.tsx`）
- `buildLatticeInstances`：`detail`/`axial` 来自响应 `fidelity`；`disc` 模式用外壳 STL（`universeStl[u][shellKey]`），`layers` 模式用内部 STL（现状）。
- `DETAIL_MAX_INSTANCES` 语义化：不再 2 万一刀切成 auto-overview；改为 `fidelity.detail==="disc"` 时允许几十万实例（`InstancedMesh` + GPU 实例化），`detailViable`/`limit` 联动（`too_many` 时仍兜底色块总览）。
- `Preview3D.tsx`(`:710-765`)/`Preview3DLattice.tsx`：解码 `r.universeStl` 时按 fidelity 选外壳/内部几何；读取 `r.fidelity`。

**门禁**：
- `gui/test/latticeInstances.test.ts`：disc 模式每 `(u, shellKey)` 一个 InstancedMesh、实例数 = 折叠后 positions 数、几何为外壳/单盘；layers 模式不回归。
- `node .\node_modules\typescript\bin\tsc --noEmit`（前端）0 错误。
- `node .\node_modules\vitest\vitest.mjs run`（gui/test）全绿。

### 步骤 4：打包部署 + BEAVRS 实测
- 构建顺序：vite → PyInstaller（`python -m PyInstaller --noconfirm mcnp_sidecar.spec`，在 gui/ 下）→ binaries → tauri build（`node .\node_modules\@tauri-apps\cli\tauri.js build`）→ 6.2 sidecar 覆盖。
- 部署 `D:\MCNP\MCNP输入卡生成器`，版本恒 1.7.3。
- **BEAVRS 实测**：全堆芯渲染，position 正确、不超 `cz 187.96` 壳（`inOuter` 保留）、z=460（高度正确，不再 clamp）、**不卡、GPU 实例化被喂到（独显工作）**；文件加载 < 几秒。

**门禁**：后端 `test_lattice`+`test_api_contract` 83/0；前端 latticeInstances 19/19；tsc 0；BEAVRS 人工（见 §6）。

---

## 4. 测试要求（全量门禁，勿降级）

| 层 | 命令 | 预期 |
| :--- | :--- | :--- |
| 后端 | `python -m pytest tests/` | 全部绿（含新增轴向折叠 / disc 用例），既有 251 用例零回归 |
| 前端 | `node .\node_modules\vitest\vitest.mjs run` | `gui/test` 全绿（含 latticeInstances disc/折叠用例） |
| 类型 | `node .\node_modules\typescript\bin\tsc --noEmit` | 0 错误 |
| 契约 | `test_api_contract.py` | 路由/结构不变（`preview-lattice` 响应新增 `fidelity` 字段向后兼容） |

---

## 5. 边界与铁律

1. 不碰 `app/generator/` 与 `app/generator/parsers/`（MCNP 生成/解析语义零变化）。
2. 不碰 FreeCAD-CSG 链路（`preview3d-performance.md` 那套不动）。
3. 不碰 `docs/contracts/api.yaml` 路由表；`preview-lattice` 响应**只增 `fidelity` 字段**（向后兼容），其余键不变。
4. `app/lattice.py`/`latticeInstances.ts`/两份测试**必须走 PowerShell `[System.IO.File]` 改写**（harness 判 binary），不用 `edit`/`write`。
5. 保留 OWEN 版权声明（MIT，BelvoirDynamics 2026）于移植注释中。
6. 不新增运行时依赖。

---

## 6. 需 PM 裁决 / 实测的开放项

| # | 决策 | 说明 |
| :--- | :--- | :--- |
| 1 | **默认 `axial=true` 还是折叠？** | 折叠（默认 `axial=false`）是本契约"数量必杀"。若 PM 要求默认展开轴向（用户要看 pin 内部 z 结构），需把`detailViable` 上限调高 + 折叠/展开切换默认值裁决。建议：默认折叠（能渲染、挑战独显），UI 提供"轴向分层"开关（默认关）。 |
| 2 | **disc 外壳 vs 完整层**：用户超限后默认看到"外壳/单盘"（几何简化）是否可接受？ | OWEN 亦如此（disc 模式是降级，UI 可切回 layers 看单组件）。建议：核心视 disc，单组件打开时允许 layers。 |
| 3 | `DETAIL_MAX_INSTANCES` 语义 | 建议按 `fidelity` 决定，disc 模式允许几十万实例，不再 2 万一刀切。需确认前端 InstancedMesh + 独显能扛（实测）。 |
| 4 | `MAX_TOTAL_INSTANCES` | 折叠后几十万 < 50万。若轴向展开（axial=true）到 ~0.8M，建议上调到 ~100万 并确认 GPU 能吃下（预算 `planRender` 兜底降级）。 |

---

## 7. 交付检查清单

- [ ] **步骤 0**：堆芯 z 位置基准修正（单层格阵 z=容器中点 +230，非 0）；BEAVRS 色块中心 +230、不误剔
- [ ] `app/lattice.py`：轴向识别折叠（`_build_axial_stack`）+ `axial` 开关；折叠后 BEAVRS count ~8万级（不再贴阈值）
- [ ] `app/lattice.py`/`api_server.py`：disc/外壳 STL 生成；响应 `fidelity` 字段
- [ ] `latticeInstances.ts`：按 `fidelity` 选外壳/内部几何；`DETAIL_MAX_INSTANCES` 语义化
- [ ] `Preview3D.tsx`/`Preview3DLattice.tsx`：读 `fidelity`/外壳 STL；`inOuter`、z=460 保留
- [ ] 后端 `test_lattice`+`test_api_contract` 83/0；前端 latticeInstances 19/19；tsc 0（全量无降级）
- [ ] 打包部署 `D:\MCNP\MCNP输入卡生成器`（v1.7.3），程序启动、5001 ready
- [ ] BEAVRS 全堆芯实测：位置正确、不超壳、z 对、**不卡 + 独显 GPU 实例化工作**
- [ ] `PROJECT_MEMORY.md` 更新 + 向 PM 汇报 commit 索引
