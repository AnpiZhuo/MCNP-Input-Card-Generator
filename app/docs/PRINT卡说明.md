# PRINT 卡说明

> 来源：`C810.pdf` —— **MCNP5 手册**（LA-UR-03-1987，Vol. II *MCNP User's Guide* 第 3 章）
> 第 3-149 ~ 3-151 页；常用表号与类型取自 Table 3.7（3-150 ~ 3-151）。

## 格式

```
PRINT
PRINT x1 x2 ...
PRINT -x1 -x2 ...
```

| 用法 | 效果 |
|------|------|
| 无参数 | 所有输出表全打 |
| 正数表号 | 基础表 + 指定的表 |
| 负数表号 | 全打 - 排除的表 |

**无 PRINT 卡** → 缩减输出（short output）。

## 默认自动打印的内容

以下 5 项**始终打印且无法关闭**（原文 3-149 的前五条 bullet）：

- 输入文件列表
- 问题摘要（粒子产生/丢失）
- KCODE 周期摘要
- 记数结果（tallies）
- 记数涨落图（TFC）

除这 5 项外，**只有标为 `basic` 的表关不掉**；标为 `default` 的表会自动打印**但可用 PRINT 卡关掉**；
`shorten` 型只有表 175（关不掉，但可缩短）。
> 原文 3-149：`You will always get the information indicated by the first five bullets listed above and
> the tables labelled “basic” … They cannot be turned off. Tables marked “default” will be printed
> automatically but they can be turned off with the PRINT card.`

## 表类型

| 类型 | 含义 |
|------|------|
| **basic** | 强制打印，关不掉 |
| **default** | 自动打印，可以用 PRINT 关掉 |
| **（空白）** | 可选，用 PRINT 数字开启，负数关闭 |

## 常用表号

| 表号 | 类型 | 内容 |
|------|------|------|
| 10 | | 源系数与分布（Source coefficients and distribution） |
| 20 | | 权重窗信息（Weight window information） |
| 30 | | 记数描述（Tally description） |
| 32 | | 网格记数描述（Mesh tally description） |
| 35 | | 重合探测器（Coincident detectors） |
| 40 | | 材料组成（Material composition） |
| 50 | | 栅元体积与质量、曲面面积（Cell volumes and masses, surface areas） |
| 60 | basic | 栅元重要性（Cell importances） |
| 62 | basic | 强迫碰撞与指数变换（Forced collision and exponential transform） |
| 70 | | 曲面系数（Surface coefficients） |
| 72 | basic | 栅元温度（Cell temperatures） |
| 80 | | ESPLT/TSPLT 重要性比率（ESPLT/TSPLT Importance Ratios） |
| 85 | | 电子射程与 straggling 表（Electron range and straggling tables） |
| 86 | | 电子轫致辐射与次级产生（Electron bremsstrahlung and secondary production） |
| 90 | | KCODE 源数据（KCODE source data） |
| 98 | | 物理常数与编译选项（Physical constants and compile options） |
| 100 | basic | 截面表（Cross-section tables） |
| 102 | | S(α,β) 数据分配（Assignment of S(α,β) data to nuclides） |
| 110 | | 前 50 个起始历史（First 50 starting histories） |
| 120 | | 重要性函数质量分析（Analysis of the quality of your importance function） |
| 126 | basic | 各栅元粒子活动（Particle activity in each cell） |
| 128 | | 宇宙映射（Universe map，重复结构） |
| 130 | | 中子/光子/电子权重平衡（Neutron/photon/electron weight balance） |
| 140 | | 中子/光子核素活动（Neutron/photon nuclide activity） |
| 150 | | DXTRAN 诊断（DXTRAN diagnostics） |
| 160 | default | TFC 分箱记数分析（TFC bin tally analysis） |
| 161 | default | f(x) 记数密度图（f(x) tally density plot） |
| 162 | default | 累积 f(x) 与记数密度图（Cumulative f(x) and tally density plot） |
| 170 | | 源分布频率表、面源（Source distribution frequency tables, surface source） |
| 175 | shorten | keff 按周期估计（Estimated keff results by cycle） |
| 178 | | keff 按批次大小估计（Estimated keff results by batch size） |
| 190 | basic | 权重窗生成器摘要（Weight window generator summary） |
| 198 | | 多群通量权重窗（Weight windows from multigroup fluxes） |
| 200 | basic | 权重窗生成窗口（Weight window generated windows） |

> 上表逐行取自 C810 **Table 3.7**（打印页 3-150 ~ 3-151），类型列与手册一致（空白＝可选表）。
> 交叉验证：手册第 5 章示例输出里每张表都印有自己的表号（如 `source … print table 10`、
> `cell temperatures … print table 72`、`activity in each cell … print table 126`、
> `weight-window lower bounds from the weight-window generator … print table 190`），与本表一致。
> 表号在输出中的形态为 `PRINT TABLE n`（n 前一个空格、两或三位数，3-150）。
> 注：3-150 的 85 号行下另有一行无编号文字 `multigroup: flux values for biasing adjoint
> calculations`，应为该格续行，取值时以手册版式为准。

## 特殊说明

- **表 160/161/162** 绑定：关 160 则 161 和 162 也不出。正数 PRINT 下不会自动出，除非显式写 160
- **表 175** 关不掉，但 `PRINT -175` 可缩短为（每 100 周期 + 最后 5 个）
- **表 128**（宇宙映射）必须在**初始运行**开启，continue-run 开不了，而且会占存储
- **执行行优先**：命令行上的 PRINT 选项优先级高于 INP 文件里的 PRINT 卡
- **continue-run**：可以用 PRINT 恢复任何表，但表 128 例外

## 示例

```
PRINT 110 40 150
```
→ 基础表 + 表 40/110/150。表 160-162（默认）不出现。表 175 缩短版。

```
PRINT 170 -70 -110
```
→ 全部输出，排除表 70、110 和 170。表 175 完整版。
（原文 3-151 的 Example 2 就是这三个参数；本文件旧版漏了 `170`。）

```
PRINT 110
```
→ 基础表 + 表 110。表 175 缩短版。
