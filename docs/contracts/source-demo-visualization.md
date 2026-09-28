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
  - **SP/SB `V` 仅对 CEL 源合法**（C810 3-64：for cell distributions only）：非 CEL 场景抛错。**体积加权语义已实现**——`Probability is proportional to cell volume (times Pi if the Pi are present)`：权重 = 逐栅元体积（给了 `Pi` 再乘 `Pi`），体积由 `geometry.cellVolumes` 提供（api_server 用 `voxel_csg.cell_volume()` 分层 MC 估计，同 seed 可复现）；**用到的栅元缺体积 → 抛 `SourceSamplingError`**（对应 MCNP「算不出体积且无 VOL 卡 = FATAL」）。
  - **`SI S` 里分布号为 0**（C810 3-64：该变量用默认值）：优先取 SDEF 卡上的**字面值**（`SDEF ERG=2.5` ⇒ 2.5），读不到才退回 Table 3.3 静态默认；`sample(..., sdef_fields=…)` 传入字段表。
  - **内置函数默认参数**按 C810 3-66：`SP −21` 不给 a ⇒ DIR=1、RAD=2（**定义了 AXS 或 JSU≠0 ⇒ 1**）、EXT=0；`SP −31` 不给 a ⇒ 0。
  - **`SI x` + `SP −21/−31` 的对称默认**（C810 3-66 规则 4/5）：RAD ⇒ 等价 `SI 0 x`；DIR/EXT ⇒ 等价 `SI −x x`（由 `sample(..., var=…)` 传入变量名判定）。
  - 任何分布引用不存在的 id / SP 个数与 SI 不匹配 / SI H 边界非单调 / 概率和为 0 / SI S 分布号非法 → 抛 `SourceSamplingError`（见 §4）。
- **测试面**：`sample()` 是纯函数（seed 由 rng 注入，可固定复现）；数值逆 CDF 的网格按**结构化键**（函数名+参数+区间）缓存，**不得改用 `id(pdf)`**（临时 lambda 回收后 id 复用会串概率网格）。

### 模块 B：`app/generator/source_sampler.py`（新）— 源抽样编排（深模块）

- **接口**：`sample_source(sdef_fields, distributions, geometry=None, *, n_particles=500, seed=None) -> dict`
  - 输入：`sdef_fields`（SDEF 字段 dict）、`distributions`（v2 分布条目）、`geometry`（CEL/SUR 用，其余可 None）。
    `geometry` 由 **api_server 层准备**（复用其 `parse_surfaces` / `Geometry.from_mcnp` / `resolve_cell_complements` / `voxel_csg` 构造 field 函数）：`{cells: {num: {field, aabb}}, surfaces: {num: {type, params, field, rotate, origin}}, trCards, cellVolumes}`——source_sampler 只消费 field/变换/体积、不解析几何（保持纯 stdlib+numpy，不 import pymcnp）。`rotate`/`origin` 是该曲面自身 TR 卡的 3×3 与平移；`trCards` 供 `SDEF TR=n`/`TR=Dn` 使用；`cellVolumes` 是逐栅元体积（`SP V` 用）。
  - 输出（`status=ok`）：`{status, particles:[{id,x,y,z,dx,dy,dz,energy,weight,particle}], energyRange:{min,max}, bounds:{min:[x,y,z],max:[x,y,z]}}`。
  - 输出（`status=error`）：`{status, error, hint?}`（见 §4 错误清单）。
  - 输出（`status=ok` 的**附加告警键**，都非阻断、都**必须**被前端展示）：
    `warnings?: string[]`（引擎侧语义告警，如「`ARA` 已接受但本程序不使用」）、
    `geometryWarnings?: string[]`（几何解析告警，由 api_server 在栅元/曲面/TR 解析失败时附加）。
    前端把两类合成一条警示条（`gui/src/utils/sourceDemoWarnings.ts` ← `SourceTab`）。
    **只展示其中一类等于静默**：实测踩过 —— `ARA` 的"接受但不使用"说明被丢掉，用户以为它生效了。
- **接口不变量**：
  - 方向 `(dx,dy,dz)` 是单位矢量；`particle` ∈ {n,p,e,f,h,a,s,other}：PAR 映射 `1/N`→`n`、
    `2/P`→`p`、`3/E`→`e`、**特殊写法 `4/F`→`f`（正电子，C810 3-56 表尾正文，锚点
    `#C810-3-56-PAR`）**、`H/A/S`→`h/a/s`（本程序既有扩展、手册 3-56 未列）、其余→`other`。
  - `particles` 恒 500 条（除非报错）；`id` 1..500。
  - 位置分四路（互斥，按 MCNP 语义）：**① 面源 SUR** / **② 栅元均匀 CEL** / **③ 笛卡尔 X/Y/Z** / **④ 柱坐标 POS+RAD+EXT+AXS**。
  - **面源（①）语义（C810 3-58 ~ 3-59 + Table 3.3）**：只支持**平面**（P/PX/PY/PZ）、**球面**（SO/S/SPH/SX/SY/SZ）、**椭球面**（GQ/SQ 的**轴平行**椭球，位置按**面积均匀** —— 拉伸回单位球后加权拒绝采样，不是旧实现的"体内近似撒点"）；柱面/锥面/环面、以及**斜置 GQ / 非椭球二次曲面**按 MCNP 语义**明确报错**并提示改用退化体源（原文：Cylindrical surface sources must be specified as degenerate volume sources）。
    - 平面：位置 = `POS + RAD·(面内单位矢量)`（RAD 缺省幂律 a=1 ⇒ 面内均匀），位置恒在面上；球面：位置按面积均匀。
      **球面 + AXS（C810 3-58）**：指定 AXS 时，`EXT` 的抽样值 = 「AXS 与球心→位置矢量」夹角的余弦
      （µ），方位角仍 0~360° 均匀；未给 AXS 才按面积均匀。故球面源的 µ 分布由 EXT 的 SI/SP 决定。
    - **方向参考轴**：显式 `VEC` 优先；面源缺 `VEC` ⇒ **面法线**（球面 = 径向、带 `NRM` 符号）；`DIR` 缺省 ⇒ 余弦分布 `p(μ)=2μ`。`NRM` 只影响面法线符号。
    - `SDEF TR=n`（整数编号）或 **`TR=Dn`（变换分布：`SI L` 列 TR 号 + `SP` 给概率，C810 3-64/3-66）**：对抽出的**位置与方向**都作用一次（约定 `p_global = Rᵀ·p + o`，与 `_freecad_csg_worker.apply_trn` 一致）；引用的 TR 卡不存在 ⇒ **明确报错**（不按"未变换"静默放行）。
      - **TR 卡本体**（锚点 `#C810-3-30-TR-CARD` / `#C810-3-31-TR-B-MATRIX`）：`parse_tr_cards` 的输出恒为 `{translate: o, rotate: R}`，其中 R 的**每行 = 一个辅系轴在主系的分量**（手册 3-31 的 `Axes` 轴对表），**`M` 折进 `o`**：`M=1`（默认）⇒ `o = O`；`M=-1`（此时位移矢量是"主系原点在辅系里"的位置）⇒ `o = −Rᵀ·O`。M 只改位移矢量的读法、不改 B 的含义（「The meanings of the Bi do not depend on M」），故下游（`voxel_csg` / `source_sampler` / FreeCAD worker）各自都不必再处理 M。
      - 手册**未给判别规则**的一处：O 之后给 **6 项且末项恰为 ±1** 时，「6 值（叉积补全第三矢量）」与「5 值 + M」两种读法同时合法。本程序按 **6 值**读（M 取默认 1），并把该歧义写进 `geometryErrors` —— 明确说明，不静默选边。
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
11. **CEL 的栅元紧盒算不出来**（栅元含无界曲面或未支持的几何）⇒ 无法做栅元均匀抽样，提示改用面源或退化体源。
    （旧实现退回 ±1e3 大盒硬撞 10 万次，只会给出一句误导性的「包围盒可能退化」。）
12. **CEL 拒绝采样效率过低**（C810 3-59 判据 `MAX(成功数,10) < EFF×尝试数`，EFF 默认 0.01）⇒
    明确报「效率过低」并指路；`sdef_eff` 可覆盖 EFF（C810 Table 3.3）。
13. **面源只允许 平面/球面/椭球面**（C810 3-58）：柱面/锥面/环面、**斜置 GQ（有 xy/yz/zx 交叉项）**、
    双曲面/抛物面一律报错并提示改用退化体源。
14. **内置函数与源变量配对错误**（C810 Table 3.4：−21→DIR/RAD/EXT、−31→DIR/EXT、−41→TME/X/Y/Z、
    能量谱→ERG）；`−7`（spare）显式不支持。

**不报错**（正常做）：含 `#` 补集的 cell、GQ/SQ 曲面、全部宏体、带 TR 变换、DS 依赖链、多源概率链。

## 4.1 CEL 的采样区域来源（相对 C810 的**有意扩展**）

C810 p.3-57 原文：CEL 拒绝采样要由**用户**给一个"完全包含该栅元"的区域（笛卡尔 X/Y/Z、
球 POS+RAD、柱 POS+AXS+RAD+EXT），并原话提醒「you must make sure that the sampling region
really does contain every part of the cell because **MCNP has no way of checking this**」。

本程序：**只给 `CEL=n` 时代码自己用栅元紧盒（`voxel_csg.cell_aabb`）当区域** —— SDEF 表单里
"只给 CEL"是最常见用法，让用户自己算盒不现实。代价是盒必须正确，故 2026-09-20 补齐了
**全部 10 类宏体**的紧盒（`voxel_csg._macrobody_aabb`，依据 C810 p.3-21/3-22），并删掉
"盒算不出来就退回 ±1e3 大盒"的旧兜底（那是接受率 ~1e-8 的硬撞）。

**已对齐 L1**：用户显式给出 X/Y/Z 或 POS+RAD/EXT 时，程序将其作为候选采样区域，
再按 C810 的拒绝采样规则限制在 `CEL` 内；只有未给采样区域时才使用栅元紧包围盒。
因此 `CEL=n + RAD=0.5` 不再被错误地解释成整个栅元均匀源。

## 4.2 已知差异（C810 有明文、本程序暂未对齐）

| # | 项 | C810 依据 | 现状 |
|---|---|---|---|
| **O7** | `−7`（Spare energy spectrum） | p.3-65 Table 3.4 | **显式不支持**（报错说明它是"留给你自己加谱的框架"） |
| **O8** | `SB` 用**内置函数**时对函数的偏倚 | p.3-66：「only −21 and −31 can be used on SB cards… If it is biased, the function is approximated within each bin by n equally probable groups such that the product of n and the number of bins is as large as possible but not over 300」 | **未实现**（`SP f` + `SB f` 的卡本程序按**未偏倚**抽样、权重 1 ⇒ 自洽但不是 MCNP 的行为）。表格式 SB 已实现（见下） |
| **O9** | `CEL` 的**栅元层级路径**（重复结构 / 格阵） | p.3-60~3-61（锚点 `#C810-3-60-CEL-PATH`）：「CEL must have a value that is a path, enclosed in parentheses, from level n to level 0」`( cn < cn-1 < …. < c0 )`；`ci` 可为 0 / `Dm` / 带负号，格元可写成 `ci[j1 j2 j3]`；采样坐标系由「第一个负/零 ci」定（pds level） | **显式不支持**：源演示的几何层只建**平铺**栅元（`{cells: {num: {field, aabb}}}`，没有 universe/FILL/LAT 层级，也没有 pds level 与格元抽样），无法定位路径里的源栅元。抽样前即**报错说明真因**并给两条替代写法（单栅元号 / `SUR=` / `POS+RAD/EXT`）——**不静默当单栅元用**（旧行为是把它当"非法源变量值"，把一个合法写法说成写错了） |

**已对齐（2026-09-20 修复，原列本表）**：

- **O6 · 内置函数被 SI 截断 + 权重补偿** —— C810 p.3-66 原文：「A built-in function on an SP card
  can be biased or **truncated** or both by a table on SI and SB cards. … **Unless the function is
  −21 or −31**, the weight of the source particle is adjusted to compensate for truncation of the
  function by the entries on the SI card.」
  修前：`-2/-3/-4/-5/-6/-41` **完全不读 SI**（照完整谱抽，能量可越出用户给的窗口），WGT 恒 1。
  现在：① 按 SI 给的 `[I1,I2]` 抽**条件分布**（`-2/-5/-3` 走数值逆 CDF；`-4/-41` 走精确截断正态；
  `-6` 走折叠正态 `E=v²`），② 权重乘 `P(I1≤x≤I2)`（对**未截断**密度算，网格与抽样共用 ⇒ 严格自洽），
  ③ `-21/-31` 按原文豁免。区间口径与 `_range` 同源（SI 单值：DIR/EXT ⇒ `[−x,x]`、其余 ⇒ `[0,x]`），
  并夹进函数自然支撑（`SI1 0 1e6` 不会拉出 1e6 宽的数值网格）；窗口与支撑无交集 ⇒ **明确报错**。
- **O6b（同源发现）· 表格式 `SB` 偏倚的权重补偿** —— C810 p.3-64：「The weight of each source
  particle is adjusted to compensate for the bias.」修前 `weight_factor()` 写了却**零调用者**
  ⇒ H/L/S 三个分支按 SB 偏倚抽样、权重却不补（偏倚白做，WGT 恒 1）。现在统一在
  `DistributionSampler.sample_with_corrections()` 返回路径上的补偿之积（真概率/偏倚概率，按
  **抽中的档位**算），`_Context` 把它并进每粒子的 WGT；`_sample_pos_dist`（POS=Dn 多点源）
  原本连 SB 都没读，一并接上。
- **R1 · `RHP/HEX` 的 `r` 语义** —— C810 p.3-21 明写 r/s/t 是「vector from the axis to the **middle of
  the first/second/third facet**」= **面心矢量（边心距）**，六个侧顶点须由相邻两面求交得到。
  本仓库原本并存三种解释（前端生成侧按面心 ✓；`voxel_csg.surface_fn`、`_freecad_csg_worker`、
  `surfacesAABB.rhpCorners` 把 r 当顶点 ✗；`lattice._rhp_extent` 把面心当极值点 ✗）⇒
  同一张卡在生成侧与解释侧差 **30° 朝向 + 13.4% 尺寸**（实测卡 `rhp 0 0 -4 0 0 8 0 2 0`：
  后端旧给 x∈[±1.732]，C810 为 x∈[±2.3094]、y∈[±2]、该面 ⊥ y 于 y=2）。
  收敛为**唯一实现** `app/quadric.py::rhp_hex_vertices`（数值上与手册例题逐位吻合），
  全部消费者改为调用它：`voxel_csg.surface_fn`、`voxel_csg._macrobody_aabb`、
  `_freecad_csg_worker._make_hex_from_params`、`lattice._rhp_extent`、
  `gui/src/volume/surfacesAABB.ts::rhpCorners`（TS 侧同名规则 + 9/12 项 60° 推断）、
  以及 `freecad_preview._surface_extent_values`（bound 由撑大 1.7× 收紧为真值）。
  回归锁：`tests/unit/test_voxel_csg_macrobody_aabb.py`（正例，xfail 留档已转绿）、
  `tests/integration/test_source_demo_matrix.py`（RHP 判据=30°/90°/150° 三面法向，边心距 2）、
  `gui/test/volume/surfacesAABB.test.ts`、`tests/unit/test_lattice.py`（hex 紧盒 y=0.5774）。

> **权威出处**（本次用作依据的是 CCC-810 原文，不是二手摘要）：
> Table 3.1 曲面卡（p.3-13）、宏体清单与卡项（p.3-20~3-22）、SDEF/Table 3.3（p.3-55~3-57）、
> 源分布与面源（p.3-57~3-59）、EFF 判据（p.3-59）、SI/SP/SB 卡与 SB 权重补偿（p.3-63~3-64）、
> Table 3.4 内置函数与特殊默认、截断权重补偿（p.3-65~3-66）。

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
| 能量 | 固定值、SI L 离散谱、SI H/"" 直方图、SI A 密度点、内置 -2/-3/-4/-5/-6/-41（含 **SI 截断区间 + 截断权重补偿**，C810 p.3-66） |
| 方向 | 各向同性、固定 DIR+VEC、锥形/指数偏倚（-21/-31）、方向 DS 依赖链、面源余弦分布 |
| 权重 | 固定值、SI/SP 分布、**SB 偏倚（表格式：抽样按偏倚概率、权重按真/偏补偿，C810 p.3-64）**、**内置函数被 SI 截断的权重补偿（C810 p.3-66）** |
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
