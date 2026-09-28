# 契约 · 源抽样模型（仿 MCNP 的重构）

> 2026-09-20 立。起因：官方 `VALIDATION_SHIELDING` 三算例（`photon_kerma` /
> `fns_config1_neutron_onaxis` / `lps_water`）在"官方 mcnp6.exe 输出当裁判"的对照下暴露 6 项不符，
> 根因不是某个补丁没打，而是**我们没照 MCNP 的源描述模型做**：同一语义散在
> `_erg` / `_direction` / `_radial_value`+`_axial_value`+`_default_power_law` 四处，
> 解析层又有三套独立 tokenizer，任何新写法都只在其中一路被支持（`fdir=d2` 只在 ERG、
> `sp3 d -21 1` 只在 SP），且认不出时**静默兜底**（`_num(v, 14.0)`）⇒ 缺陷长得像"跑得对"。
> 本契约定义重构后的唯一模型，实现必须严格按此走。

## 0. 对外不变量（不得改变）

- 公开入口仍是 `app/generator/source_sampler.py::sample_source(
  sdef_fields, distributions, geometry=None, *, n_particles=500, seed=None) -> dict`，
  返回 `{"status","particles","energyRange","bounds"}`；粒子字段
  `id, x, y, z, dx, dy, dz, energy, weight, particle`（前端/`api_server` 零改动）。
- 本引擎**只算起始状态**：位置、方向、能量、权重、粒子类型。不做运输、不做 tally、不做时间轴。
- 权重必须正确（界面显示 WGT）：它是 `SDEF WGT` 基值 × 各变量的补偿之积。

## 1. MCNP 的模型（唯一依据，C810 页码为证）

> **锚点索引**（原文逐字 + 关键短语见 `docs/authority/c810-sdef.md`，由 `tools/c810_extract.py`
> 从 `C810.pdf` 脚本生成、`--check` 可复核；`tests/unit/test_c810_anchors.py` 断言本文引用的每个 id
> 都在锚点表里且原文含关键短语）：
> §1.1 `#C810-3-55-VAR-FORMS` `#C810-3-55-SAMPLING-ORDER` `#C810-3-55-ONE-LEVEL`；
> §1.2 `#C810-3-63-SI-OPTIONS` `#C810-3-63-SP-OPTIONS` `#C810-3-63-H-FIRST-ZERO`
> `#C810-3-64-BUILTIN-FORM` `#C810-3-64-SB-RULES` `#C810-3-64-SI-S` `#C810-3-64-SP-V`
> `#C810-3-66-DS-CARD`；§1.3 `#C810-3-65-TABLE-3-4` `#C810-3-66-BUILTIN-VARS`
> `#C810-3-66-TRUNC-WEIGHT` `#C810-3-66-SPECIAL-DEFAULTS`；§1.4 `#C810-3-56-TABLE-3-3`；
> §1.5 卡格式 `#C810-3-4-COMMENTS` `#C810-3-4-CONTINUATION`。
> **纪律：本文任何一句语义若找不到锚点，就不许留在文中**（宁可标"未决"）。

### 1.1 三种变量形态（p.3-55）

```
变量 = 显式值 | Dn | Fvar' Dn
```
- `Dn`：值取自分布 n（SI/SP/SB/DS 描述）；
- `Fvar' Dn`：值取自分布 n，而**选哪个分布/取什么值取决于父变量 var' 的抽样值**；
- 「Only one level of dependence is allowed」；「Each distribution may be used for only
  one source variable」；「**Each dependent variable must be sampled after the variable it
  depends on has been sampled**」。
- 官方写法既有空格分隔 `ERG FDIR D2`，也有等号连写 `erg=fdir=d2`（官方两算例实测）；
  解析层统一归一成 `FDIR D2`。

### 1.2 分布家族（p.3-63~3-66）

| 卡 | 语义 |
|---|---|
| `SIn option I1..Ik` | option：空/H 分箱边界、L 离散值、A 概率密度定义点、S 分布号 |
| `SPn option P1..Pk` / `SPn f a b` | 第一形态：D 箱概率（默认）/C 累积/V 按栅元体积（仅 CEL）；**A 型 SI 时 SP 给的是概率密度**；第二形态：内置函数 `f`（**允许前面带一个选项字母**，官方实测） |
| `SBn` | 偏倚：同 SP 第一形态规则；**权重 = 真/偏**（表：箱概率比；A 型：概率密度比） |
| `DSn` | 依赖映射 H/L/S/T/Q（父值 → 子分布号/值/默认） |
| `SCn` | 分布注释（只影响输出标题） |

### 1.3 内置函数（Table 3.4，p.3-65~3-66）

`-2` Maxwell(ERG) / `-3` Watt(ERG) / `-4` 聚变高斯(ERG) / `-5` 蒸发(ERG) /
`-6` Muir(ERG) / `-7` spare（**显式不支持**）/ `-21` 幂律(DIR,RAD,EXT) /
`-31` 指数(DIR,EXT) / `-41` 高斯(TME,X,Y,Z)。
- 被 SI **截断**时要乘 `P(I1≤x≤I2)`，**−21/−31 豁免**（p.3-66）。
- 特殊默认（p.3-66 规则 2/3/4/5）：只有 SI 的 RAD/EXT ⇒ 等价 `SP −21` 默认参数；
  只有 `SP −21/−31` 的 DIR/EXT ⇒ 等价 `SI 0 1` / `SI −1 1`；`SI x`+`SP −21` 的 RAD ⇒ `SI 0 x`；
  `SI x`+`SP −21/−31` 的 EXT ⇒ `SI −x x`。

### 1.4 变量默认值（Table 3.3，p.3-55~3-57）

每个变量的默认值/默认分布由表 3.3 给定（ERG=14、TME=0、WGT=1、DIR=体源各向同性/面源余弦、
RAD/EXT/POS/XYZ=0、CEL 由位置定、VEC=面法线（面源）、NRM=+1、EFF=.01、PAR 由 MODE 定）。
**默认值必须在 `VAR_SPEC` 表里声明并挂 C810 锚点，不允许散落在各分支。**

> ⚠ **本契约 v1 曾在此处凭印象写出 `RATE=0 / JSU=0 / BEM/BAP/LOC/DAT=0`——已删除**：这些值没有
> 逐条对过 Table 3.3 原文，正是本契约要防的"AI 转述"。实现侧（`source_spec.py`）对两者一律
> `default=None, anchor=None`，但**定案状态不同**：
> - `JSU`：手册正文有（p.3-55 变量清单、p.3-66 的 SP −21 条件），Table 3.3 无 ⇒ 记**未决**；
> - `RATE`：**C810 没有这个源变量**（2026-09-28 定案）—— Table 3.3 变量列无此行，且说明书
>   **全文检索** `\bRATE\b` 的 57 处命中全是普通英文（convergence / sampling / dose / energy
>   loss rate…），无一处属源变量语义 ⇒ 不写数值、**不实现**，给出值即明确报错；
>   `sdef_rate` 字段仅为兼容旧数据保留（前端模板已标注「非标准」）。
> **未决不等于可以猜**：未决变量在抽样路径上出现时按 C810 语义报错，而不是取一个数。

## 2. 目标结构

```
app/generator/source_spec.py     ← 模型层（新）
    VAR_SPEC: dict[变量名, VarSpec]        每变量声明 {默认值, 允许内置函数, 依赖父, 依赖采样序}
    VarSpec = (name, default, builtins, parents, position_role)
    parse_var_ref(token) -> {"kind": "const"|"dist"|"dep", "value"|"did"|("parent","did")}
    normalize_sdef_fields(fields) -> fields   # Fvar=Dn → Fvar Dn 等归一化（解析侧共用）

app/generator/source_sampler.py  ← 引擎层（重写）
    sample_source(...)                      对外入口（签名不变）
    _Engine:
        __init__(fields, sampler, geometry)
        _order()                            按 VAR_SPEC 的依赖关系给出抽样顺序（拓扑）
        _resolve(var) -> value              显式值 | Dn | Dn@DS(parent)；**认不出即报错**
        _position() / _direction() / ...    位置=组合语义（见 §3），其余变量走通用路径
        _weight_corr                         每个变量的补偿累乘（复用 sampler.sample_with_corrections）

app/generator/distributions.py   ← 分布抽样器（保留，仅补差异）
    DistributionSampler.sample_with_corrections(eid, rng, ...) -> (值, 补偿因子)
    （S6：A 型 + SB 的偏倚密度与权重比；TME 相关处补抽样）
```

**删除**（收敛后）：`_Context._erg` / `_direction` 里的形态分支、`_default_power_law` 之外的
变量专用解析、`_radial_value` / `_axial_value` 的重复逻辑、以及所有 `_num(v, 默认)` 式静默兜底。

## 3. 位置是组合语义（不是"一变量一值"）

`SUR` / `POS`+`RAD`+`EXT`+`AXS` / `CEL` 决定位置，是**变量组合**，单独一层实现（沿用现有几何代码：
`voxel_csg.cell_aabb`、`surface_fn`、CEL 拒绝采样 + EFF 判据、面源平面/球面/椭球面 + NRM），
但其中 `RAD`/`EXT` 的**取值**必须走通用引擎（`Dn` / 内置函数 / 无 SP 时的默认幂律）。
方向层同理：`DIR`（Dn/固定值/默认）+ `VEC`/`AXS`/`NRM` 语义集中在 `source_spec` 声明。

## 4. 错误语义（取消静默兜底）

认不出的变量值、非法的 SI/SP/SB/DS 组合、依赖父变量非法、依赖值缺失 ⇒ 抛
`SourceSamplingError`（`sample_source` 转 `{"status":"error","error":...}`）。
**不允许**"取默认值"式的静默降级；默认值只允许来自 VAR_SPEC 表（即 MCNP 的 Table 3.3）。

## 5. 门禁（这次教训固化成闸门）

1. **官方算例闸门**（新，`tests/integration/test_sdef_official_gate.py`）：
   三个官方算例的 SDEF 卡片块（逐字取自 `MCNP6\Testing\VALIDATION_SHIELDING\Inputs`）做夹具，
   断言：分布号**齐全**；`DIR` A 型样本均值 ≈ 官方打印均值；`ERG` 走 DS 依赖后落在各子分布
   SI 区间内且均值 ≈ 官方；`RAD` 幂律/密度抽样均值 ≈ 官方；离散谱频率 ≈ 官方 expected 列。
   期望值来源 = **官方 mcnp6.exe 输出**（print table 170 与 "the mean of source distribution N is …"）。
2. 既有 `pytest`（1133）全绿；抽样语义变更处允许重定标，但必须在提交信息里给出"官方数字"依据。
3. `vitest`（830）/`tsc` 两档 /`vite build` 全绿（前端零改动也应保持）。
4. 外部裁判脚本（仓库外，`D:\AItool\.tmp\_sdef_audit2.py`）：改抽样就必须重跑三算例对照。

## 6. 非目标

- 不实现 −7 spare；不做内置函数在 SB 上的"分箱近似"（p.3-66），该组合显式报错；
- 不做时间轴/运输；`TME` 只作为变量参与抽样与权重，不进粒子记录（前端不显示）。

## 7. 实现约定（2026-09-20 与引擎层实现者对账后冻结）

1. **`VarSpec.parents` 的语义** = 「该变量**允许**出现在 `Fvar' Dn` 的父位置上」；
   它**不是**抽样依赖图。真正的硬依赖边只有手册明写的那三条：
   `POS→RAD/EXT`、`VEC/AXS→DIR`、`DIR→ERG`（p.3-55/3-56 的默认值与依赖描述）。
   抽样序 = 分层（位置层 POS/X/Y/Z/CEL/SUR/RAD/EXT/AXS → 方向层 DIR/VEC →
   能量层 ERG → 独立层 TME/WGT/NRM/EFF/PAR）+ 层内稳定序 + 上列硬边 + 环检测（成环即报错）。
2. **`VAR_SPEC` 是变量登记表，不等于依赖图**：`JSU`（Table 3.3 无此变量，仅 p.3-55 变量清单与
   p.3-66 条件里出现）在表里以 `default=None, anchor=None, field_keys=()` 登记为**未决**，
   但**不进**依赖表、不要求 SDEF 字段。`RATE` 则在 2026-09-28 **定案为"C810 没有这个源变量"**
   （依据见 §1.4 的 ⚠）：同样 `anchor=None`、不进依赖表，但状态是"不实现 + 给了值就报错"，
   不再挂"未决"。
3. **`PAR` 缺省**：Table 3.3 说"由 MODE 卡最低的那一种"定。**2026-09-28 已接 MODE**：
   `sample_source(..., mode=[...])`（`gui/backend/api_server.py` 从 `deck.basic.mode_n/p/e`
   取）⇒ 引擎按 `n → p → e` 选**最低的适用粒子**；调用方不传 `mode` 时退回既有口径（中子 `n`）。
4. **返回字典允许的附加键**：`particles` / `energyRange` / `bounds` / `status` / `error` 之外的
   `warnings` 是**允许的加法**（只放"降级/近似"类提示，例如"`DIR=Dn` 但没有 VEC/面法线可作参考轴
   ⇒ 按体源各向同性处理"）。**粒子字段与主键不得增删改名**。
5. **未实现变量一律显式报错**（契约 §4）。**当前清单只剩 `RATE`**（C810 里没有这个源变量，
   见 §1.4 的 ⚠ ⇒ 报错文案说明"手册无此变量"，不猜语义）。历史两项已各自落地：
   `CCC`（cookie-cutter cell）2026-09-28 实现（位置层拒绝采样，EFF 判据同 CEL）；
   `ARA` 改为**接受并记 `warnings`**（它只用于点探测器直接贡献的归一化，不改变粒子起始状态，
   官方 VALIDATION_SHIELDING 的 6 个 duct 算例全带 `ara=` ——按"未实现即报错"会让它们一个都开不出来）。
   报错文案必须说明原因并指路（用 `SUR`/`CEL` 表达或到 MCNP 里加），不得静默忽略。
   前端若允许填这些字段，用户会看到该报错——这是有意的代价，直到实现为止。
6. **确定性**：`sample_source(..., seed=<int>)` 可复现；HTTP 端点不透传 seed（前端固定不传），
   故闸门只能做**统计级**对账（官方夹具用 20000 粒子 + 容差），不做逐粒子比对。
7. **`DS … Q` 的查表语义 = C810 原文（唯一权威，p.3-67）**：
   > "When the Q option is used on a DS card, the Vi define a set of bins for the independent
   > variable. The sampled value of the independent variable is compared with the Vi, **starting
   > with V1, and if the sampled value is less than or equal to Vi, the distribution Si is
   > sampled** for the value of the dependent variable. The value of Vk must be greater than or
   > equal to any possible value of the independent variable. If a distribution number Si is zero,
   > the default value for the variable is used."
   ⇒ 实现必须是「**按书写顺序找第一个满足 `父值 ≤ Vi` 的项，取与之配对的 Si**」（升/降序都只是书写
   顺序，不得重排）。`Q` 也是唯一可用于"父变量是内置函数"的 DS 形态。
   ⚠ **明确否决**一种在实测中被误记为"官方约定"的偏移写法：「第 i 段阈值区间对应第 **i+1** 项子
   分布号」。三条独立依据都指向它是错的：① 上引原文；② `fns_config1` 的 DS2 里 `(-0.99619,180)`
   与子分布 SI 区间配对后能量随 μ 单调（μ→−1 最低能 13.200、μ→+1 最高能 15.110），与 D-T 反应
   运动学一致；③ 该表若按"i→i+1"读，μ≈−0.95（近后向）会给出 14.97~15.02 MeV（近最高能），物理上
   不可能。**凡夹具/代码里出现这种偏移，按原文改，不要反过来改引擎。**
8. **官方数字的"类型"决定它能当什么判据**（2026-09-20 S6 实测踩出来的分层，写死在这里免得下次又拿错）：
   - **理论硬界**：由公式逐点算出的值，任何样本量都必须满足。例：`weight multiplier` 列
     `(d_true/Z_true)/(d_bias/Z_bias)` ⇒ 可当权重的硬上下界。
   - **观测范围**：`range of sampled source weights` 是**某次 nps 运行的样本极值**，**不是硬界**。
     实测 photon_kerma：权重 > 945 的占比 1.5e-4，官方 nps=3000 时期望颗数仅 **0.45**，而 20000 颗
     出现 3 颗（max≈2058）是统计必然 ⇒ 拿它当上界会随我方抽样数增大而**假红**。只可当量级参考。
   - **打印精度**：官方表只印 5–6 位有效数字（`1.2527E-04` vs 精确 `1.252690e-4`，差 7.6e-6）
     ⇒ 以打印值为判据时容差**不得小于**打印精度（现值 **1e-5**，并在 docstring 写明理由）。
   - **"expected_*" 列必须逐列核语义再当锚点**：实测 `expected_weight` 与 `weight multiplier`
     **不同源**（17 行里只 5 行接近）；`expected_prob` 的箱是 **`[x_{i-1}, x_i]`**（与
     `cumulative probability` 同右移口径），不是 `[x_i, x_{i+1}]`。选错列/错箱会得到
     "怎么改判据都对不上"的假象——此时应先怀疑**引擎**（S6 期间正是这样挖出
     `_sample_A` 段内逆 CDF 误用真密度表的真 bug）。
