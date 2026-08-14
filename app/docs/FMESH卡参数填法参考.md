# FMESH 卡参数填法参考

> 适用：MCNP 输入卡生成器（v1.7.0）「网格计数（FMESH）」功能——FMESH 卡的结构化填写、校验与卡体生成。
> 文档性质：**已按 C810 原文回填**（2026-08-14）。凡标注【MCNP5·C810 3-118~3-120】的内容，均已对照 `D:\MCNP\MCNP6\C810.pdf`（MCNP5 手册）打印页 3-118~3-120（PDF 页 643~645）页级核验；凡标注【MCNP6】的为 MCNP6 专属行为，C810 未收录。
> 参考依据：
> - `D:\MCNP\MCNP6\C810.pdf`（MCNP5 手册）3-118~3-120（Table 3.6 关键字表）/ Table 3.11（3-161~3-164 卡汇总表）
> - `docs/contracts/meshtal-visualization.md`（§4.7.1 / §5.1 / §5.3）
> - `gui/src/volume/fmeshState.ts`（字段契约、校验规则、两档模板）
> - 注：本机另有网源核验 MCNP6 差异（EMINTS/TMINTS 拼写、OUT 新取值、MAT 语义），已并入下方版本标注

---

## 1. 概述

**FMESHn（Fixed Mesh Tally，固定网格计数）** 是 MCNP 的网格计数卡：在一张固定的三维网格上记录粒子通量/流，结果写入 MESHTAL 文件，可供 3D 体积可视化。

- **卡头**：`FMESHn:pl`，`n` 为计数卡号，`pl` 为粒子设计符。【MCNP5·C810 3-118】粒子设计符为 **N（中子）/ P（光子）/ E（电子）**；另有星号形式 **`*FMESHn`**（能量-时间-粒子权重计数，单位 MeV/cm²）。
- **与 Fn 计数卡的关系**：【MCNP5·C810 3-118】FMESHn 只允许 type 4 通量型计数；卡号 `n` 与普通 Fn 卡号独立编号。【MCNP6】TMESH 卡号另有独立规则，本项目暂不暴露 TMESH（见 §0）。
- **几何**：【MCNP5·C810 3-118】GEOM 可选 **`xyz`/`rec`**（笛卡尔）与 **`rzt`/`cyl`**（圆柱），默认 `xyz`。**无 `sph`**（球系 C810 未收录，项目亦不支持）。项目表单取值：`XYZ`（默认）/`REC`/`CYL`/`RZT`，单 token 连写。
- **卡体格式**（C810 3-118 原文骨架，Table 3.6）：

```
FMESHn:N/P/E  GEOM=xyz  ORIGIN=x0 y0 z0
          IMESH=val  IINTS=val
          JMESH=val  JINTS=val
          KMESH=val  KINTS=val
```

- **续行格式**：生成器按 MCNP 标准续行规则输出——续行以 **5 空格缩进** 开头（第 1~5 列为空白即续行），每行一个 `关键字=值`。等号可选、关键字任意顺序；GEOM/FACTOR/OUT/TR 不可使用特殊输入特性（I/M/R）。

---

## 2. 必填字段速查表

> 说明：`IMESH/IINTS` 等以「边界 + 区间数」成对出现，算作一组。速查共 **7 组 10 个输入项**。

| # | 字段 | 填什么 | 默认/约束 | 版本来源 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `number`（卡号 n） | 计数卡号，如 `4` | 未填时默认 `4`（模板行为）。C810：FMESHn 只允许 type 4，卡号与 Fn 独立编号 | 项目实现；【MCNP5·C810 3-118】 |
| 2 | `particle`（粒子） | `N` / `P` / `E` | 未填默认 `N`。C810：设计符 N/P/E（无 H/A/S） | 项目实现；【MCNP5·C810 3-118】 |
| 3 | `geom`（几何） | `XYZ` / `REC` / `CYL` / `RZT` | 未填默认 `XYZ`；CYL/RZT 为圆柱系（需 AXS/VEC）。C810：xyz/rec/rzt/cyl，默认 xyz，**无 sph** | 项目实现；【MCNP5·C810 3-118】 |
| 4 | `origin`（原点） | 三个坐标值，如 `-100 -100 -150` | 可选，默认 `0 0 0`。直角系=最负角；圆柱系=底面中心。网格值须从 ORIGIN 起单调递增 | 【MCNP5·C810 3-118】 |
| 5 | `imesh` + `iints`（I 向） | 边界值 + 区间数（正整数） | **必须，至少 1 值**；多值=多区间，条目一一对应；边界单调递增；IINTS 必须 > 0 | 【MCNP5·C810 3-119】 |
| 6 | `jmesh` + `jints`（J 向） | 同 I 向 | **必须，至少 1 值**；同 I 向 | 同上 |
| 7 | `kmesh` + `kints`（K 向） | 同 I 向；圆柱系 θ 向末值须为 1 | **必须，至少 1 值**；圆柱系末值=1（θ 转数，1=整圈 360°） | 同上 |

**卡文本示例**（number=4、particle=N、geom=XYZ、ORIGIN=-100 -100 -150、单区间）：

```
FMESH4:N GEOM=XYZ ORIGIN=-100 -100 -150
     IMESH=100
     IINTS=1
     JMESH=100
     JINTS=1
     KMESH=50
     KINTS=1
```

---

## 3. 可选字段「留空即默认」表

| 字段 | 作用 | 留空即默认 / 备注 | 版本来源 |
| :--- | :--- | :--- | :--- |
| `emesh` + `emints` | 能量分箱：边界 + 区间数（MeV） | 空 = 不分箱，默认 0~该粒子能量上限。**单位 MeV**【MCNP5·C810 3-119】。拼写：C810(MCNP5)=`EINTS`，MCNP6=`EMINTS`——本项目生成发 `EMINTS`（MCNP6），导入容错 `EINTS`/`EMINTS` | 拼写【MCNP6】；语义【MCNP5·C810 3-119】 |
| `tmesh` + `tmints` | 时间分箱：边界 + 区间数 | 空 = 不分箱。【MCNP5·C810】**MCNP5 无时间网格**（C810 全文无 TMESH/TMINTS）；`TMESH/TMINTS` 是 MCNP6 命名。本项目生成发 `TMINTS`，导入容错 `TINTS`/`TMINTS` | 关键字【MCNP6】 |
| `mat` | 材料过滤：只统计指定材料号的栅元 | 默认语义「0 = 粒子所在格材料（默认），非 0 = 指定材料号」。**C810(MCNP5) 无 MAT 关键字**——MAT 是 MCNP6 后期功能 | 【MCNP6】；C810 未收录 |
| `factor` | 乘法因子（每网格单元乘一个系数） | 默认 1。C810 有关键字 FACTOR | 【MCNP5·C810 3-119】（项目表单暂未暴露，见 §0 待办） |
| `out` | 输出格式 | 默认 `COL`。【MCNP5·C810 3-119】取值 `col`（默认）/`cf`/`ij`/`ik`/`jk`；`cf` 额外输出体积+结果×体积。【MCNP6】另有 `COLSC`/`CFSC`/`NONE`/`XDMF`（XDMF 供 ParaView，MCNP6.3+）。项目表单九选项 | MCNP5 取值【C810 3-119】；扩展项【MCNP6】 |
| `axs` + `vec` | 圆柱系轴向量 / θ=0 参考向量（各 3 分量） | 圆柱系（CYL/RZT）使用。C810 默认：AXS=`0 0 1`，VEC=`1 0 0`；两向量不必正交但**不得平行**、长度不得为 0 | 【MCNP5·C810 3-119】 |
| `tr` | 变换编号（正整数） | 可选；对网格整体做坐标变换。C810 有关键字 TR | 【MCNP5·C810 3-119】（项目表单已暴露） |
| `raw` | 原文卡体兜底 | 结构化字段为空时原样回放 raw（round-trip 保真），不由用户直接填写 | 项目实现（契约 §5.3） |

> **未收录关键字提醒（C810 已核验）**：`DOS`/`UNIT`/`PDATA`/`TRACK`/`COR`/`DIMS` 在 C810 FMESH 关键字表中**不存在**（高度疑似 MCNP6 TMESH 专属），【MCNP5·C810 3-118 Table 3.6 无】。**注意**：`FACTOR` 与 `MAT` 有区别——FACTOR 在 C810 存在，MAT 不在（MCNP6）。

---

## 4. 通用模板两档（与前端「一键填充」一致）

前端表单提供两档通用模板，一键填入网格字段（只覆盖 `origin/imesh/iints/jmesh/jints/kmesh/kints`；`geom/particle/number` 仅在未填时给默认 `XYZ / N / 4`；其余字段保持用户已填值不变）。模板数值为**项目内置示例网格**，非 C810 原文建议。

### 4.1 minimal —— 最小可用（1×1×1）

> 单网格快速验证卡能否跑通。卡文本（number=4、particle=N）：

```
FMESH4:N GEOM=XYZ ORIGIN=-100 -100 -150
     IMESH=100
     IINTS=1
     JMESH=100
     JINTS=1
     KMESH=50
     KINTS=1
```

网格规模 1×1×1 = 1 单元。

### 4.2 starter —— 通用起步（20×20×10）

> 推荐：先粗网格看分布，再按需加密。卡文本：

```
FMESH4:N GEOM=XYZ ORIGIN=-100 -100 -150
     IMESH=100
     IINTS=20
     JMESH=100
     JINTS=20
     KMESH=50
     KINTS=10
```

网格规模 20×20×10 = **4000 单元**，3D 渲染开销小。

| 模板 | 网格规模 | ORIGIN | IMESH/IINTS | JMESH/JINTS | KMESH/KINTS |
| :--- | :--- | :--- | :--- | :--- | :--- |
| minimal | 1×1×1 = 1 | -100 -100 -150 | 100 / 1 | 100 / 1 | 50 / 1 |
| starter | 20×20×10 = 4000 | -100 -100 -150 | 100 / 20 | 100 / 20 | 50 / 10 |

> 两档模板应用后均通过全部校验（§5），且网格规模 ≤ 128³（2,097,152）不触发内存警告。

---

## 5. 五条必守规则（校验规则 + 错误示例）

> 来源：`gui/src/volume/fmeshState.ts` `validateFmeshRow`。规则 3/4/5 已按 C810 原文确认。

**规则 1：区间数（`*ints`）必须为正整数（每个 ≥ 1）。**
- 覆盖：`iints / jints / kints / emints / tmints`。
- 【MCNP5·C810 3-119】「Entries on the IINTS, JINTS, and KINTS keywords **must be greater than zero**」。
- 错误示例：`IINTS=0`、`IINTS=-1`、`IINTS=1.5` → 报错「IINTS 须为正整数（每个区间数 ≥ 1）」。

**规则 2：网格边界与区间数条目一一对应（多区间时）。**
- 【MCNP5·C810 3-119】「IINTS/JINTS/KINTS 存在时，条目数必须与对应 IMESH/JMESH/KMESH 条目数相等」——**支持多值**。
- `IMESH=10 20 30` 必须配 `IINTS=n1 n2 n3`（3 条目）；条目数不等 → 报错「IINTS 条目数（n）与 IMESH（m）不匹配」。
- 一侧有值一侧空 → 报错「缺少对应的 X 网格边界/区间数」。
- 注：`1INTS n` 简写语法 v1 不支持（解析器无 `1INTS` 键）；C810 Table 3.11 简写列待人工补核（见 §7）。

**规则 3：网格/能量边界值须单调递增；直角系（XYZ/REC）下各向首值须大于 ORIGIN 对应坐标。**
- 【MCNP5·C810 3-119】「粗网格位置与能量值必须单调递增（从 ORIGIN 点开始）」。
- 单调递增：`IMESH=10 10 20`（相等）或 `IMESH=20 10`（递减）→ 报错「IMESH 值须单调递增」。
- 直角系从原点起：ORIGIN x=-100 时 `IMESH=0` 或 `IMESH=-50` → 报错「IMESH 首值 -50 须大于 ORIGIN X 坐标 -100（网格从原点起递增）」。

**规则 4：圆柱系（CYL/RZT）下 `kmesh` 末值须为 1（θ 为转数，末值 1 = 整圈 360°）。**
- 【MCNP5·C810 3-119】圆柱系：I→径向 r，J→轴向（沿 AXS），K→周向 θ（单位转数，**最后一个值必须 = 1**）。
- 错误示例：圆柱系 `KMESH=2 4` → 报错「圆柱系（CYL/RZT）下 KMESH 末值须为 1」。

**规则 5：圆柱系 `axs` 与 `vec` 不可平行；`tr` 须为正整数。**
- 【MCNP5·C810 3-119】AXS/VEC 不必正交但不得平行，长度不得为 0。
- `AXS=0 0 1` 配 `VEC=0 0 2`（同向/反向）→ 报错「AXS 与 VEC 不能平行（圆柱轴与网格方向需不同）」。
- `TR=-3`、`TR=1.5` → 报错「TR 须为变换编号（正整数）」。

**附加提示（警告，非错误）：网格规模上限提醒。**
- 三方向区间总数乘积 > **128³ = 2,097,152** 时给出警告「网格规模 i×j×k = N 单元，超出 128³ 渲染预算，3D 体积渲染内存/性能开销大」。
- 注：128³ 是**本项目 3D 渲染预算**（fmeshState.ts，契约 §2/§12），**与 C810 无关**；C810 未给出网格单元数/内存建议（Table 3.6 无此类内容）。

---

## 6. 版本来源标注约定（阅读本文前必读）

| 标注 | 含义 |
| :--- | :--- |
| 【MCNP5·C810 3-118~3-120】 | MCNP5 官方手册 C810.pdf 打印页 3-118~3-120（PDF 页 643~645）已页级核验的原文内容 |
| 【MCNP6】 | MCNP6 专属行为（项目契约/实现/网源核验依据，非 MCNP5 原文） |
| 项目实现 | 本生成器实现行为（fmeshState.ts / fmesh_parser.py / 契约），可作为开发依据，不得冒充 MCNP 官方原文 |

**已确认项（C810 页级核验完成，2026-08-14）**：
- 粒子设计符 N/P/E；`*FMESHn` 星号形式（MeV/cm²）【3-118】
- GEOM 取值 xyz/rec/rzt/cyl，默认 xyz，无 sph【3-118】
- ORIGIN 默认 0 0 0（可选）【3-118】
- IMESH/JMESH/KMESH 必须至少各 1 值；IINTS 等必须 > 0 且条目数与粗网格匹配【3-119】
- FACTOR 存在；MAT 不在 C810【3-119】
- OUT：col（默认）/cf/ij/ik/jk；cf 额外体积+结果×体积【3-119】
- AXS 默认 0 0 1、VEC 默认 1 0 0；不平行【3-119】
- 圆柱系 I→r / J→轴 / K→θ（末值=1）【3-119】
- MCNP5 无时间网格（TMESH/TMINTS 零命中）【全文检索】

**仍待人工补核（少量）**：Table 3.11（3-161~3-164）的 FMESHn 简写语法列；`1INTS n` 区间简写是否收录（见 §7）。

---

## 7. 待 C810 原文回填清单（已基本回填，仅剩 2 项）

> 原十项清单已按 C810 页级核验逐条回填（见 §6 已确认项）。剩余 2 项需补查 C810 打印页 3-161~3-164（Table 3.11 卡汇总表）：

| # | 待核对项 | 状态 |
| :--- | :--- | :--- |
| 1 | 卡头设计符 / 粒子 / 星号 | ✅ 已回填（N/P/E；`*FMESHn` MeV/cm²）【3-118】 |
| 2 | GEOM 取值集合 / 缺省 / 有无 sph | ✅ 已回填（xyz/rec/rzt/cyl，默认 xyz，无 sph）【3-118】 |
| 3 | ORIGIN 必填 / 与网格边界大小关系 | ✅ 已回填（默认 0 0 0；单调递增从 ORIGIN 起）【3-118~119】 |
| 4 | IMESH/IINTS 单值 vs 多值 / `1INTS` 简写 | ⏳ 多值已确认【3-119】；`1INTS` 简写待 Table 3.11 补核 |
| 5 | EMESH 单位 / 时间单位 | ✅ 已回填（能量 MeV；MCNP5 无时间）【3-119】 |
| 6 | OUT 取值 / 默认 | ✅ 已回填（col 默认/cf/ij/ik/jk；扩展项 MCNP6）【3-119】 |
| 7 | DOS/UNIT/MAT/PDATA/TRACK/COR/DIMS/FACTOR | ✅ 已回填（FACTOR 在；MAT/DOS/UNIT/PDATA/TRACK/COR/DIMS 不在）【Table 3.6】 |
| 8 | 圆柱系 i/j/k 语义 / kmesh 末值=1 | ✅ 已回填（I→r/J→轴/K→θ，末值=1）【3-119】 |
| 9 | 网格单元数/内存建议 | ✅ 已回填（C810 无；128³ 为项目预算） |
| 10 | Table 3.11 FMESHn 行简写语法 | ⏳ 待 Table 3.11 补核 |

---

## 8. 术语对照（供开发者参考）

| 文档用词 | 实现字段（FmeshRow / FmeshDefinition） | 备注 |
| :--- | :--- | :--- |
| 卡号 | `number` | 模板默认 `4` |
| 粒子 | `particle` | 默认 `N`；导入容错 N/P/E/H/A/S（仅 N/P/E 视为设计符） |
| 几何 | `geom` | 单 token 连写 `XYZ`/`REC`/`CYL`/`RZT`；空值默认 `XYZ` |
| 原点 | `origin` | 3 分量空格分隔 |
| I/J/K 向边界+区间数 | `imesh`/`iints`、`jmesh`/`jints`、`kmesh`/`kints` | 多值空格分隔 |
| 能量边界+区间数 | `emesh`/`emints` | 关键字 `EMINTS`（MCNP6）；导入容错 `EINTS` |
| 时间边界+区间数 | `tmesh`/`tmints` | 关键字 `TMINTS`（MCNP6）；导入容错 `TINTS` |
| 乘法因子 | `factor` | 【C810 有】项目表单暂未暴露（待办） |
| 材料过滤 | `mat` | 默认语义 0=粒子所在格材料；【MCNP6】C810 无 |
| 输出格式 | `out` | 九选项，默认 `COL` |
| 圆柱轴/方向向量 | `axs`/`vec` | 圆柱系 |
| 变换编号 | `tr` | 正整数 |
| 原文兜底 | `raw` | 结构化为空时回放 |

---

## 0. 附：与前端「简单模式 + 自动填充」规划（2026-08-14）

为降低新手填写门槛，前端规划：
1. **简单模式**：默认只露核心 4 项——粒子（N/P/E）+ 三向网格范围（IMESH/JMESH/KMESH）；其余字段（ORIGIN/INTS/能量/时间/MAT/OUT/AXS/VEC/TR）折叠进「高级模式」
2. **按几何自动填充**：从曲面卡解析几何包围盒，一键把 x/y/z 最大范围填入 IMESH/JMESH/KMESH（网格自动覆盖模型）
3. **粒子说明**：每个网格计数一个粒子（N/P/E），要多种粒子就加多行
4. **三步上手**：① 选粒子 ② 点自动填充 ③ 解析看 3D 结果

> 待办：① 简单/高级模式 ② 几何自动填充（需把 surfaces 数据接回 FMeshForm 或上层算好边界传入）③ `factor` 字段是否暴露（C810 有，MCNP6 也有）④ Table 3.11 简写补核。

*本文档 2026-08-14 由 C810 页级核验回填并整理；待办项见 §0/§7。*
