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
RAD/EXT/POS/XYZ=0、CEL 由位置定、VEC=面法线（面源）、NRM=+1、EFF=.01、PAR 由 MODE 定、
AXS/CCC/ARA/BEM/BAP/LOC/DAT/TR/RATE=0）。**默认值必须在 VAR_SPEC 表里声明，不允许散落在各分支。**

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
