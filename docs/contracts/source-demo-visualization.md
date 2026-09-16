# SDEF 源粒子演示可视化契约（v1）

> 依据：TODO #6（`MCNP输入卡生成器_功能待办清单.md` P2）+ 用户 2026-09-09 会话逐项敲定（做全、按 MCNP 语义、有错报错、每次 500 粒子只表"从哪发出/往哪飞"）。
> 参照：`ptrac-visualization.md`（粒子可视化范式）、`lattice-coverage-check.md`（几何判定范式）、`codebase-design`（深模块）。

## 0. 目标（用户敲定）

源（SDEF）定义界面加「🎬 演示源」入口：后端按 SDEF + SI/SP/SB/DS 分布做**随机抽样**（位置/方向/能量/权重/粒子类型），
前端在独立 3D 窗口（几何外壳内）用**粒子点 + 方向短线 + 粒子类型基色 + 能量深浅**展示源的形状与分布。
**只表"从哪发出、往哪飞"，不做输运模拟。** 每次固定抽 **500 个粒子**。

**做全**：所有曲面、所有宏体、所有分布卡特性、DS 依赖链、多源概率链，全部按 MCNP 语义本地计算，**不降级、不近似**。
报错只留给"引用不存在 / 参数非法 / 概率不匹配"这类 MCNP 语义真错误。

## 1. 深模块划分（三个后端模块，各一个小接口 + 深实现）

### 模块 A：`app/generator/distributions.py` 扩展 — 分布抽样（深模块）

现状：已是 SI/SP/SB/DS/SC 的**唯一语法知识源**（解析 parse + 发射 emit）。本次新增**抽样**，使"分布"的
解析/发射/抽样三件事共享同一 v2 schema，locality 收敛一处。

- **接口**：`DistributionSampler`（新类）——
  - `DistributionSampler(entries: list[dict])`：编译 v2 分布列表（解析 SI/SP/SB 类型、预计算累积概率、缓存内置函数参数）。
  - `sample(eid: int, rng) -> float`：从分布 `eid` 抽一个标量值。
  - `resolve_ds(eid: int, parent_value: float, parent_si: list | None = None) -> dict`：DS 卡按父变量值查表。**返回判别式 dict**（不是子分布号列表）：`{"distribution": n}`（用子分布 n）/ `{"value": v}`（直接用值 v）/ `{"default": True}`（该分支无匹配，退回默认）。
    - `parent_si` 可选：H 型需要父变量 SI 的 bin 边界才能插值（不传则 H 退回 default）。
    - 数据字段统一为 `distributionIds`（见 `_parse_ds` 文档串）：S 型是分布编号列表；H/L/Q/T 型是数据 token（J 列表 / V-S 对 / I-J 对）；`param` 仅在首 token 非数值（`DSn S ERG 3 4` 这类变量名写法）时保留。
- **接口不变量**：
  - 抽样覆盖 SI `L/H/A/S`（无字母 `""` = H）+ SP `D/C/V`（无字母 `""` = D）+ 内置函数 `-2/-3/-4/-5/-6/-21/-31/-41` + SB 偏倚。
  - SI `S` 递归选子分布（**分布号可带 `D` 前缀**，C810 3-64；**分布号 0 = 该变量用 Table 3.3 默认值**）；SI `A` 概率密度定义点线性插值；SP `C` 累积概率二分。
  - **SP/SB `V` 仅对 CEL 源合法**（C810 3-64：for cell distributions only）：非 CEL 场景抛错。⚠ **未实现体积加权语义**——采样侧仍按 `D` 表处理（概率值原样使用），只有发射侧保留 `V` 字母；实现需要逐栅元体积，登记为已知缺口。
  - **内置函数默认参数**按 C810 3-66：`SP −21` 不给 a ⇒ DIR=1、RAD=2（**定义了 AXS 或 JSU≠0 ⇒ 1**）、EXT=0；`SP −31` 不给 a ⇒ 0。
  - **`SI x` + `SP −21/−31` 的对称默认**（C810 3-66 规则 4/5）：RAD ⇒ 等价 `SI 0 x`；DIR/EXT ⇒ 等价 `SI −x x`（由 `sample(..., var=…)` 传入变量名判定）。
  - 任何分布引用不存在的 id / SP 个数与 SI 不匹配 / SI H 边界非单调 / 概率和为 0 / SI S 分布号非法 → 抛 `SourceSamplingError`（见 §4）。
- **测试面**：`sample()` 是纯函数（seed 由 rng 注入，可固定复现）；数值逆 CDF 的网格按**结构化键**（函数名+参数+区间）缓存，**不得改用 `id(pdf)`**（临时 lambda 回收后 id 复用会串概率网格）。

### 模块 B：`app/generator/source_sampler.py`（新）— 源抽样编排（深模块）

- **接口**：`sample_source(sdef_fields, distributions, geometry=None, *, n_particles=500, seed=None) -> dict`
  - 输入：`sdef_fields`（SDEF 字段 dict）、`distributions`（v2 分布条目）、`geometry`（CEL/SUR 用，其余可 None）。
    `geometry` 由 **api_server 层准备**（复用其 `parse_surfaces` / `Geometry.from_mcnp` / `resolve_cell_complements` / `voxel_csg` 构造 field 函数）：`{cells: {num: {field, aabb}}, surfaces: {num: {type, params, field, rotate, origin}}, trCards}`——source_sampler 只消费 field/变换、不解析几何（保持纯 stdlib+numpy，不 import pymcnp）。`rotate`/`origin` 是该曲面自身 TR 卡的 3×3 与平移；`trCards` 供 `SDEF TR=n` 使用（未实现 `TR=Dn`）。
  - 输出（`status=ok`）：`{status, particles:[{id,x,y,z,dx,dy,dz,energy,weight,particle}], energyRange:{min,max}, bounds:{min:[x,y,z],max:[x,y,z]}}`。
  - 输出（`status=error`）：`{status, error, hint?}`（见 §4 错误清单）。
- **接口不变量**：
  - 方向 `(dx,dy,dz)` 是单位矢量；`particle` ∈ {n,p,e,h,a,s,other}（PAR 1/2/3/H/A/S 映射）。
  - `particles` 恒 500 条（除非报错）；`id` 1..500。
  - 位置分四路（互斥，按 MCNP 语义）：**① 面源 SUR** / **② 栅元均匀 CEL** / **③ 笛卡尔 X/Y/Z** / **④ 柱坐标 POS+RAD+EXT+AXS**。
  - **面源（①）语义（C810 3-58 ~ 3-59 + Table 3.3）**：只支持**平面**（P/PX/PY/PZ）、**球面**（SO/S/SPH/SX/SY/SZ）、**椭球面**（GQ/SQ，近似）；柱面/锥面/环面按 MCNP 语义**明确报错**并提示改用退化体源（原文：Cylindrical surface sources must be specified as degenerate volume sources）。
    - 平面：位置 = `POS + RAD·(面内单位矢量)`（RAD 缺省幂律 a=1 ⇒ 面内均匀），位置恒在面上；球面：位置按面积均匀。
    - **方向参考轴**：显式 `VEC` 优先；面源缺 `VEC` ⇒ **面法线**（球面 = 径向、带 `NRM` 符号）；`DIR` 缺省 ⇒ 余弦分布 `p(μ)=2μ`。`NRM` 只影响面法线符号。
    - `SDEF TR=n`（整数编号）：对抽出的**位置与方向**都作用一次（约定 `p_global = Rᵀ·p + o`，与 `_freecad_csg_worker.apply_trn` 一致）；`TR=Dn`（变换分布）**未实现**。
  - 纯 stdlib + numpy + `random.Random(seed)`；无 FreeCAD（几何判定走 voxel_csg，见模块 C）。
- **内部 seam**（实现私有，供其单测）：`_sample_variable(field_name)`、`_compose_position()`、`_sample_direction()`——不构成对外接口。

### 模块 C：`app/voxel_csg.py` 扩展 — 宏体拆解（路 A，三处受益）

现状 `surface_fn` 只支持 平面/球/柱/锥/GQ/SQ + RPP/SPH，**BOX/RCC/RHP/HEX/TRC/REC/ELL/WED/ARB 抛 ValueError**。

- **接口**：扩展 `surface_fn(surf_type, params, transform)` 覆盖全部宏体——宏体按 MCNP 语义**拆成 facet 曲面交集**（见 §2），
  每个 facet 复用现有 `surface_fn`（平面 P/P_1、柱 C/Z、球 S、锥 K、二次 GQ/SQ）。
- **深度/leverage**：一处实现，三处消费者受益——`coverage_check`（水密自检）、`overlap_probe`（重合检测）、`source_sampler`（本功能 CEL/SUR 判定）。
- **locality**：宏体几何知识（facet 组成、顶点→面法向）只在此一处。

## 2. 宏体 → facet 拆解表（MCNP 语义）

| 宏体 | 参数 | facet（半空间交集） |
|------|------|-------------------|
| RPP | 6 | 6 个轴对齐平面 PX/PY/PZ（内部） |
| SPH | 4 | 1 个球面 S（内部） |
| RCC | 7 | 1 个柱面 C/Z + 2 个端面平面（底/顶，法向 H） |
| TRC | 8 | 1 个锥面 K/Z + 2 个端面平面 |
| REC | 12 | 1 个椭圆柱面（GQ）+ 2 个端面平面 |
| ELL | 6 | 1 个椭球面（GQ） |
| WED | 12 | 5 个平面（三角底 + 3 侧面 + 斜顶） |
| BOX | 12 | 6 个平面（8 顶点 → 6 面，任意朝向） |
| RHP / HEX | 9/12/15/18 | 6 个侧面平面（V+R/S/T 基）+ 2 个端面平面（法向 H） |
| ARB | 30 | 6 个平面（8 顶点 + 6 面定义） |

每个 facet 求值 `f>=0`（正侧在内）后 `AND`；宏体在 cell 表达式里带 `-` 号（如 `-BOX`）= facet 交集的补。
`#n` 补集复用现有 `freecad_preview.resolve_cell_complements`（api_server 已用）。

## 3. 端点

`POST /api/source-demo-sample`（operationId `sourceDemoSample`，tag `source`）：
- 入参 `{sdefFields, sdefDistributions, surfaces, cells, trCards, nParticles?=500}`。
- 出参：§1 模块 B 的 `sample_source` 返回（`status/particles/energyRange/bounds` 或 `status/error/hint`）。
- api.yaml 同步（新增 path + schema + 漂移闸门断言）；`api_server.py` handlers 字典注册 `"/api/source-demo-sample"`。

## 4. 错误清单（MCNP 语义真错误，就地报、不开窗）

校验在点「演示源」时执行（后端 `sample_source` 内抛 `SourceSamplingError`，前端在 SourceTab 捕获并就地红字展示，不写窗口桥）：

1. 分布引用不存在的 id（`D7` 但无 id=7）。
2. SP 值个数与 SI 值个数不匹配。
3. SI H / "" 边界非单调递增；SI A 密度点非单调递增。
4. SP D 概率存在负数 / 全为 0。
5. DS 引用不存在的分布；DS 与 `Fxxx` 依赖变量不一致。
6. SI S 选子分布但子分布不存在。
7. `SUR=n` 引用的曲面未定义；`CEL=n` 引用的栅元不存在。
8. 概率和为零（多源）。
9. 内置函数参数个数错误（如 Watt 需 2 参）。
10. `SP V`（体积加权）出现在非 CEL 场景。

**不报错**（正常做）：含 `#` 补集的 cell、GQ/SQ 曲面、全部宏体、带 TR 变换、DS 依赖链、多源概率链。

## 5. 前端

| 模块 | 职责 |
| :--- | :--- |
| `gui/src/source/SourceDemoRenderer.ts` | 纯渲染器（照 `PtracRenderer` 范式）：几何外壳 STL（复用 `buildCellMaterial` semi）+ 500 粒子 `Points`（`vertexColors`，粒子类型基色 × 能量深浅 `trackColors.ts`）+ 方向短线 `LineSegments`（出生点 → 沿方向一小段，长度取场景尺寸 ~2~5%，复用 `alignWorld` 归一化 offset + `computeFramingBox` 取景）；接口 `createSourceDemoRenderer(canvas, {stlData, cellViews})` → handle `{setParticles, setShellVisible, setShellOpacity, setDirectionLength, dispose}` |
| `gui/src/source/SourceDemoWindow.tsx` | 独立窗宿主（照 `PtracWindow`）：读桥 → `fetchPreview3dStl` 外壳 + `sourceDemoSample` 抽样 → 渲染；右 300px 面板：标题「🎬 演示源」、统计（粒子数/能量范围/各类型计数）、能量深浅图例、粒子透明度、方向线长度、外壳开关、**重新抽样**按钮、关闭 |
| `gui/src/utils/api.ts` | `sourceDemoSample(payload)` + 类型 |
| `gui/src/utils/windows.ts` | 桥 key `mcnp_win_source_demo`（`openSourceDemo`/`readSourceDemoData`） |
| `gui/src/components/SourceTab.tsx` | SDEF 模式顶部「🎬 演示源」按钮：收集 `sdefFields`（par/erg/pos_x/y/z/dir/vec/axs/rad/ext/cel/sur/nrm/tr/wgt/tme/ccc/ara）+ `sdefDistributions` + `surfaces/cells/trCards` → 先 `sourceDemoSample` 校验 → 有 `error` 就地红字、不开窗；`status=ok` 才写桥开窗 |
| `main.rs` | `create_or_focus(&app, "source_demo", "演示源", 1300.0, 820.0)` + `open_source_demo_window` |
| `App.tsx` | `#/source-demo` 路由 |

## 6. 抽样语义覆盖清单（做全，逐项测）

| 维度 | 覆盖 |
|------|------|
| 位置 | 点源、多点离散（POS=Dn + SI L）、直线（单轴）、盒体（X/Y/Z）、球体/球壳（POS+RAD）、圆柱/圆盘/锥（POS+AXS+RAD+EXT，RAD 依赖 EXT 的 DS 链）、面源（SUR 平面/球面/柱面）、栅元均匀（CEL 拒绝采样） |
| 能量 | 固定值、SI L 离散谱、SI H/"" 直方图、SI A 密度点、内置 -2/-3/-4/-5/-6 |
| 方向 | 各向同性、固定 DIR+VEC、锥形/指数偏倚（-21/-31）、方向 DS 依赖链、面源余弦分布 |
| 权重 | 固定值、SI/SP 分布、SB 偏倚（权重补偿） |
| 粒子类型 | PAR 固定、PAR=Dn 分布、默认（由 MODE 或 n） |
| 依赖 | DS 链（Fxxx）、SI S 选分布、多源概率链（SP D1 / POS=F D1） |
| 变换 | TR 变换（位置采样后变换） |

## 7. 验收（测试先行，先红后绿）

- **pytest**：
  - `tests/unit/test_source_sampler.py`：固定 seed 下——点源 500 粒子同坐标；SI L 等概率（统计分箱）；SI H 边界内均匀；球体源点在球内（`r<=R`）；圆柱源；盒体源；DS 依赖链（父值→子分布）；多源概率链（各源占比≈概率）；方向各向同性（方向矢量均匀分布于单位球）；内置函数（Watt/Maxwell 参数校验 + 抽样范围）；每个 §4 错误清单项各一条报错用例。
  - `tests/unit/test_distribution_sampler.py`：DistributionSampler 各分布类型 + SI S 递归 + DS 查表。
  - `tests/unit/test_voxel_csg_macrobody.py`：宏体拆解后 `surface_fn` 对各宏体内部/外部/边界点判定正确（RPP/BOX/RCC/RHP/HEX/TRC/ELL/WED）；现有 `surface_fn` 单测零回退。
  - `tests/integration/test_api_contract.py`：`sourceDemoSample` HTTP 信封 + 坏分布 hint + 漂移闸门。
- **vitest**：`gui/test/source/` —— SourceDemoRenderer 创建/销毁/setParticles、windowRouteConsistency 含 `source-demo`、SourceTab 按钮 error 就地展示（不写桥）。
- **门禁**：pytest + vitest + tsc EXIT 0 + vite build EXIT 0（colorize 128³ 计时已知 flaky）。

## 8. 非目标

- 不做输运模拟、不做时间轴动画、不做粒子径迹（那是 PTRAC 窗口的职责）。
- 不做 TS 端抽样镜像（抽样全在后端，前端只渲染；无跨语言 golden）。
- 不引入新依赖（纯 stdlib + numpy + 现有 three.js）。
