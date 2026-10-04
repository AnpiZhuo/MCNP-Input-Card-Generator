# 内置教程 × C810 页级核对报告

> **状态**：**核对 6/6 完成；§7.3 的 P0→P2 修正已执行并复验**（详见 §8 复核记录、§9 修正执行记录）。
> 教程原文现为"已按 C810 页级证据改正"的版本；镜像 `gui/public/docs`、`gui/dist/docs` 已同步。
> **核对标准（唯一权威源）**：`D:\MCNP\MCNP6\C810.pdf`
> **标准身份依据**：`docs/card-lexicon-diff.md` **D-11**（2026-08-13 页级核验）——C810.pdf = **MCNP5 卷 I+II 全文**（p78-989）＋ MCNP6.1/MCNP5 发布说明（p15-77）＋ 附录 ＋ MCNP MANUAL INDEX（p990-1001），共 **1001 页**；**卡格式权威章 = MCNP5 卷 II Ch.3**（PDF 526-691 = 打印页 3-1~3-166，页眉 `EXPORT CONTROLLED INFORMATION 10/3/05`）；**本 PDF 内无 MCNP6 手册卷 II Ch.3**。
> **判定四态**：✅原文可支持 ｜❌与原文不符 ｜⛔页码引用错 ｜⚠️本 C810 无证据（须另标来源）
> **节奏**（用户决定）：**只出报告，不改文档**；不建锚点回归测试。修正待用户过目后执行。
> **范围**（用户决定）：6 篇有 UI 入口的教程（PRINT卡说明 / MCNP6_FN卡结构参考 / MCNP6_输出卡结构参考 / C810_卡片格式详细 / MCNP6_曲面卡格式参考 / 源分布卡说明）。

---

## 0. 证据链与可复现方法

| 环节 | 做法 | 复核证据 |
|---|---|---|
| 读取 PDF | Store Python 3.13.14 + **PyMuPDF 1.28.0**（包位于 Store 包缓存 `…\LocalCache\local-packages\Python313\site-packages`，用 `PYTHONPATH` 接入，**零安装**） | `fitz.__doc__` = `PyMuPDF 1.28.0: Python bindings for the MuPDF 1.29.0 library` |
| 页数 | `doc.page_count` = **1001** | 与 PROJECT_MEMORY「1001 页权威手册」一致 |
| 页码映射 | **打印页 3-x = PDF 页 − 525**，并用**页面自己印刷的页码**复核 | PDF 674→3-149、675→3-150、676→3-151；页眉 `EXPORT CONTROLLED INFORMATION 10/3/05` 三页一致 |
| 表格三列配对 | **按行坐标 y 复核**（number / type / description 必须同一 y）——防止线性化错位 | `y=541.5 → 60 ｜ basic ｜ Cell importances`；`y=192.5 → 160 ｜ default ｜ TFC bin tally analysis` |
| 独立互证 | 原文**正文**对表号的直接指称 | 「Table 128, the repeated structure universe map」「Table 175 cannot be turned off completely…」「Tables 160, 161, and 162 are different」 |

> **已知限制**：抽取按词的几何位置重建阅读序，表格被线性化（非版式影印）。本报告所有涉及表格的判定，均以**行坐标配对**为据，不以线性文本为据。
> 复现命令（workdir = 仓库根；下列脚本为一次性探针，可随时重建，亦可直接用等价的一行命令）：
> ```powershell
> $sp='C:\Users\13789\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\site-packages'
> $env:PYTHONPATH=$sp
> & 'C:\Users\13789\AppData\Local\Microsoft\WindowsApps\python.exe' -c "import fitz;d=fitz.open(r'D:\MCNP\MCNP6\C810.pdf');print(d.page_count);print(d[642].get_text()[:200])"
> ```
> （`d[i]` 为 0-based，故 PDF 页 n = `d[n-1]`；打印页 3-x 在 Ch.3 区间满足 x = n − 525。全库文本可自建：把 `d[i].get_text()` 逐页拼成一个 UTF-8 文件即可。）

---

## 1. `app/docs/PRINT卡说明.md`（自标来源：C810 第 3-149 ~ 3-151 页）

### 1.1 页码引用 —— ✅ 正确
PRINT 词条起于 **3-149** 末尾（`6. PRINT  Output Print Tables`），**Table 3.7** 横跨 **3-150 ~ 3-151**，两个 Example 与 TALNP/MPLOT 词条在 **3-151**。自标页区间与原文一致；且本文件**未**误称 C810 为「MCNP6 手册」（对比：另外 4 篇待核）。

### 1.2 非表格部分台账

| # | 教程断言（行号） | 原文（页 / 行坐标） | 判定 |
|---|---|---|---|
| 1 | 格式三种写法：`PRINT` / `PRINT x1 x2 …` / `PRINT -x1 -x2 …`（:7-11） | 3-149 `Form:` —`no entry gives the full output print` / `x1 x2 … prints basic output plus the tables speciﬁed` / `−x1 −x2 … prints full output except the tables speciﬁed` | ✅ |
| 2 | 无参数＝所有输出表全打（:15） | 3-149 `no entry gives the full output print` | ✅ |
| 3 | 正数表号＝基础表＋指定的表（:16） | 3-149 `prints basic output plus the tables speciﬁed by the table numbers x1, x2, …` | ✅ |
| 4 | 负数表号＝全打 − 排除的表（:17） | 3-149 `prints full output except the tables speciﬁed by x1, x2, …` | ✅ |
| 5 | 无 PRINT 卡 → 缩减输出（:19） | 3-149 `Default: No PRINT card in the INP ﬁle **or no PRINT option on the execution line** will result in a reduced output print.` | ✅（可补全：执行行无 PRINT 亦同；原文并明确此时只出 basic/default/shorten） |
| 6 | 始终会打印：输入列表/问题摘要/KCODE 摘要/记数/TFC（:23-27） | 3-149 `a listing of the input ﬁle` / `the problem summary of particle creation and loss` / `KCODE cycle summaries` / `tallies` / `tally ﬂuctuation charts` | ✅ |
| 7 | 始终会打印：**标记为 basic / default / shorten 的表**（:28） | 3-149 自动打印列表只含 `marked basic and default`；`You will always get … the first ﬁve bullets … and the tables labelled “basic” … They cannot be turned off. Tables marked “default” will be printed automatically but **they can be turned off** with the PRINT card.` | ⚠️ **表述不精确**：只有前 5 项＋`basic` 关不掉；`default` 可关、`shorten`(175) 只能缩短。与本文件 §「表类型」（:35 写 default 可关）**自相矛盾** |
| 8 | basic＝强制打印、关不掉（:34） | 3-150 `Tables that cannot be controlled by the PRINT card are marked as type “basic.”` | ✅ |
| 9 | default＝自动打印、可用 PRINT 关掉（:35） | 3-150 `Tables that are automatically printed but can be turned off are marked as type “default.”` | ✅ |
| 10 | 空白＝可选，正数开启、负数关闭（:36） | 3-150 `Tables with no type (blank) can be turned off and on with the PRINT card or option.` | ✅ |
| 11 | 160/161/162 绑定：关 160 则 161/162 不出；正数下不自动出除非显式写 160（:75） | 3-150 `If you turn off table 160, tables 161 and 162 will not appear either… If a PRINT card has a positive entry, tables 160, 161, and 162 will not appear unless table 160 is explicitly requested.` | ✅ |
| 12 | 175 关不掉，`PRINT -175` 可缩短为（每 100 周期＋最后 5 个）（:76） | 3-150 `Table 175 cannot be turned off completely, but the output can be greatly shortened to every 100 cycles plus the last ﬁve cycles. PRINT −175 and PRINT 110 both will produce the short version` | ✅ |
| 13 | 128（宇宙映射）须在初始运行开启，continue-run 开不了，且占存储（:77） | 3-150 `Table 128, the repeated structure universe map… If table 128 is not turned on in an initial run, it CANNOT be turned on in a subsequent continue-run… Table 128 is the only print table that affects storage.` | ✅（与 §1.3 表号表**自相矛盾**：那里把 126 写成宇宙映射） |
| 14 | 执行行优先：命令行 PRINT 选项优先于 INP 里的 PRINT 卡（:78） | 3-149 `The execute line takes precedence over the input card.` | ✅ |
| 15 | continue-run 可用 PRINT 恢复任何表，128 例外（:79） | 3-150 `The PRINT control can be used in a continue-run to recover all or any applicable print tables… Table 128 can never be printed if it was not requested in the original run.` | ✅ |
| 16 | 示例 `PRINT 110 40 150` → 基础表＋40/110/150，160-162 不出现，175 缩短版（:83-86） | 3-151 `Example 1: PRINT 110 40 150 — The output ﬁle will contain the “basic” tables plus tables 40, 110, and 150, not 160, 161, 162 (the “default” tables), and the shortened version of 175.` | ✅ 逐字对应 |
| 17 | 示例 `PRINT -70 -110` → 全部输出，排除 70 和 110，175 完整版（:88-91） | 3-151 `Example 2: PRINT **170** −70 −110 — … except tables 70, 110, **and 170**.` | ❌ **示例被改坏**：原文示例含 `170`，排除集是 70/110/**170**；教程删掉 170 后结论随之失真 |
| 18 | 示例 `PRINT 110` → 基础表＋表 110，175 缩短版（:93-96） | 3-150 `PRINT 110 … will produce the short version of Table 175` ＋ 3-149 正数规则 | ✅（结论有原文依据；原文未把它列为 Example） |

### 1.3 `常用表号` 表（:40-71）——**31 行中 24 行与原文不符**

原文依据：Table 3.7（3-150 下半页与 3-151 上半页），**按行坐标逐行配对**。

| 教程写（表号 ｜ 类型 ｜ 内容） | 原文同一 y 行（表号 ｜ 类型 ｜ 内容） | 判定 |
|---|---|---|
| 10 ｜ basic ｜ 栅元重要性 | 10 ｜ — ｜ Source coefﬁcients and distribution | ❌ 内容错（栅元重要性=**60**）＋类型错 |
| 20 ｜ basic ｜ 栅元温度 | 20 ｜ — ｜ Weight window information | ❌ 内容错（栅元温度=**72**）＋类型错 |
| 30 ｜ basic ｜ 截面表 | 30 ｜ — ｜ Tally description | ❌ 内容错（截面表=**100**）＋类型错 |
| 40 ｜ default ｜ 记数分析 | 40 ｜ — ｜ Material composition | ❌ 内容错（材料组成=40）＋类型错 |
| 50 ｜ — ｜ 源系数与分布 | 50 ｜ — ｜ Cell volumes and masses, surface areas | ❌ 内容错（源系数与分布=**10**） |
| 60 ｜ — ｜ 曲面系数 | 60 ｜ basic ｜ Cell importances | ❌ 内容错（曲面系数=**70**）＋类型错 |
| 70 ｜ — ｜ 栅元体积/质量、曲面面积 | 70 ｜ — ｜ Surface coefﬁcients | ❌ 内容错（体积/面积=**50**） |
| 80 ｜ — ｜ 材料组成 | 80 ｜ — ｜ ESPLT/TSPLT Importance Ratios | ❌ 内容错（材料组成=**40**；ESPLT/TSPLT=80） |
| 85 ｜ — ｜ 电子射程与 straggling | 85 ｜ — ｜ Electron range and straggling tables | ✅ |
| 86 ｜ — ｜ 重合探测器 | 86 ｜ — ｜ Electron bremsstrahlung and secondary production | ❌ 内容错（重合探测器=**35**） |
| 90 ｜ basic ｜ 物理常数与编译选项 | 90 ｜ — ｜ KCODE source data | ❌ 内容错（物理常数=**98**）＋类型错 |
| 98 ｜ basic ｜ 强迫碰撞与指数变换 | 98 ｜ — ｜ Physical constants and compile options | ❌ 内容错（强迫碰撞=**62**）＋类型错 |
| 100 ｜ default ｜ f(x) 记数密度图 | 100 ｜ basic ｜ Cross-section tables | ❌ 内容错（f(x) 密度图=**161**）＋类型错 |
| 102 ｜ default ｜ 累积 f(x) 与记数密度图 | 102 ｜ — ｜ Assignment of S(α,β) data to nuclides | ❌ 内容错（累积 f(x)=**162**）＋类型错 |
| 110 ｜ — ｜ 曲面积分 | 110 ｜ — ｜ First 50 starting histories | ❌ 内容错（原文 110＝首批 50 个起始历史；正文亦称「Problem Summary (located after table 110)」） |
| 120 ｜ — ｜ 重要性函数质量分析 | 120 ｜ — ｜ Analysis of the quality of your importance function | ✅ |
| 126 ｜ — ｜ 宇宙映射（重复结构） | 126 ｜ **basic** ｜ Particle activity in each cell | ❌ **126/128 对调**＋类型错 |
| 128 ｜ basic ｜ 各栅元粒子活动 | 128 ｜ — ｜ Universe map | ❌ **126/128 对调**（原文正文独立佐证 128＝universe map）＋类型错 |
| 130 ｜ — ｜ 中子/光子/电子权重平衡 | 130 ｜ — ｜ Neutron/photon/electron weight balance | ✅ |
| 140 ｜ — ｜ 核素活动 | 140 ｜ — ｜ Neutron/photon nuclide activity | ✅ |
| 150 ｜ — ｜ DXTRAN 诊断 | 150 ｜ — ｜ DXTRAN diagnostics | ✅ |
| 160 ｜ — ｜ 源分布频率表、面源 | 160 ｜ **default** ｜ TFC bin tally analysis | ❌ 内容错（源分布频率表=**170**）＋类型错（原文 160 是 default 三兄弟之一） |
| 161 ｜ default ｜ 记数分箱分析 | 161 ｜ default ｜ f(x) tally density plot | ❌ 内容错（TFC bin tally analysis=**160**；161＝f(x) 密度图） |
| 162 ｜ default ｜ f(x) 记数密度 | 162 ｜ default ｜ Cumulative f(x) and tally density plot | ❌ 内容错（f(x) 密度图=**161**） |
| 170 ｜ — ｜ 权重窗生成器摘要 | 170 ｜ — ｜ Source distribution frequency tables, surface source | ❌ 内容错（权重窗生成器摘要=**190**） |
| 175 ｜ shorten ｜ keff 按周期估计 | 175 ｜ shorten ｜ Estimated keff results by cycle | ✅ |
| 178 ｜ basic ｜ keff 按批次大小估计 | 178 ｜ — ｜ Estimated keff results by batch size | ❌ **类型错**（原文 178 无类型＝可选） |
| 190 ｜ — ｜ 权重窗生成窗口 | 190 ｜ **basic** ｜ Weight window generator summary | ❌ 内容错（权重窗生成窗口=**200**）＋类型错 |
| 198 ｜ — ｜ ESPLT/TSPLT 重要性比率 | 198 ｜ — ｜ Weight windows from multigroup ﬂuxes | ❌ 内容错（ESPLT/TSPLT=**80**） |
| 200 ｜ — ｜ 电子射程与 straggling 表 | 200 ｜ **basic** ｜ Weight window generated windows | ❌ 内容错（电子射程表=**85**）＋类型错 |

**统计**：31 行 → ✅ 7 行（85 / 120 / 130 / 140 / 150 / 175 / 178 的**内容**）、❌ 24 行；其中**类型列**错误另有 10 处（10/20/30/40/60/90/98/100/102/126/128/160/178/190 等行）。

**原文 Table 3.7 完整正确映射（供修正直接采用）**：
| 表号 | 类型 | 内容 |
|---|---|---|
| 10 | — | Source coefficients and distribution |
| 20 | — | Weight window information |
| 30 | — | Tally description |
| 32 | — | Mesh tally description |
| 35 | — | Coincident detectors |
| 40 | — | Material composition |
| 50 | — | Cell volumes and masses, surface areas |
| 60 | basic | Cell importances |
| 62 | basic | Forced collision and exponential transform |
| 70 | — | Surface coefficients |
| 72 | basic | Cell temperatures |
| 80 | — | ESPLT/TSPLT Importance Ratios |
| 85 | — | Electron range and straggling tables（其下一行 `multigroup: flux values for biasing adjoint calculations` 无编号，属该格续行，版式待复核） |
| 86 | — | Electron bremsstrahlung and secondary production |
| 90 | — | KCODE source data |
| 98 | — | Physical constants and compile options |
| 100 | basic | Cross-section tables |
| 102 | — | Assignment of S(α,β) data to nuclides |
| 110 | — | First 50 starting histories |
| 120 | — | Analysis of the quality of your importance function |
| 126 | basic | Particle activity in each cell |
| 128 | — | Universe map |
| 130 | — | Neutron/photon/electron weight balance |
| 140 | — | Neutron/photon nuclide activity |
| 150 | — | DXTRAN diagnostics |
| 160 | default | TFC bin tally analysis |
| 161 | default | f(x) tally density plot |
| 162 | default | Cumulative f(x) and tally density plot |
| 170 | — | Source distribution frequency tables, surface source |
| 175 | shorten | Estimated keff results by cycle |
| 178 | — | Estimated keff results by batch size |
| 190 | basic | Weight window generator summary |
| 198 | — | Weight windows from multigroup ﬂuxes |
| 200 | basic | Weight window generated windows |

> 教程 `常用表号` 表还**漏收**原文中的 32（Mesh tally description）、62（Forced collision and exponential transform）、72（Cell temperatures）三行——它们是错误映射的"受害者"（被并进了别的表号）。

### 1.4 本篇修正建议（待批准，尚未执行）
1. **整表替换** `常用表号`（:38-71）：按 §1.3 的原文映射重写，含类型列；补回 32/62/72。
2. **修正示例 2**（:88-91）：改回原文 `PRINT 170 -70 -110`，结论补上"排除 170"。
3. **拆开"始终会打印"**（:28）：关不掉的只有前 5 项＋`basic`；`default` 可关，175 只能缩短。
4. 修正 126/128 的**内部矛盾**：正文 :77 与表号表必须一致（128＝宇宙映射）。
5. 明确表号在输出中的形态（原文：`PRINT TABLE n`，n 前有一空格、两或三位数）——属可补充项，非错误。

### 1.5 结论
本篇**结构、格式、默认行为、特殊规则、示例 1/3 均与原文吻合**，唯一的重大缺陷集中在 `常用表号` 表（24/31 行错、类型列另错 10 处、漏 3 行），并造成**教程内部自相矛盾**（126/128）。该表若不修，用户按它去写 `PRINT` 卡会得到与预期相反的输出表。

---

## 2. `app/docs/MCNP6_FN卡结构参考.md`（自标来源：C810 第 3-80 页起）

### 2.1 头尾声明 —— ❌ 手册名误标（3 处）

| 位置 | 教程原文 | C810 事实 | 判定 |
|---|---|---|---|
| :1 标题 | `# MCNP6 记数卡（Tally Card）结构参考` | C810.pdf 是 **MCNP5 卷 I+II**（D-11；页眉 `EXPORT CONTROLLED INFORMATION 10/3/05`），**不含** MCNP6 手册卷 II Ch.3 | ❌ |
| :3 来源行 | `> 来源：MCNP6 手册 C810.pdf，第 3-80 页起` | 同上 | ❌ |
| :213 结语 | `文档覆盖 MCNP6 手册第 3-80 页至第 3-91 页的记数卡（Tally）体系` | 同上；且与自表引用到 3-120 不协调 | ❌ ＋ ⚠️ 范围自述不一致 |

### 2.2 §二 页码总表 —— ✅ **22/22 正确**（与原文官方表逐行一致）

原文 **3-80** 有手册自带的 `Mnemonic ｜ Card Type ｜ Page` 表，教程逐行照录；我另用「卡词条标题落页」独立复核，22 项**双向全部命中**：

Fna 3-81 ｜ FCn 3-95 ｜ En 3-96 ｜ Tn 3-96 ｜ Cn 3-97 ｜ FQn 3-98 ｜ FMn 3-99 ｜ DEn/DFn 3-103 ｜ EMn 3-104 ｜ TMn 3-104 ｜ CMn 3-105 ｜ CFn 3-105 ｜ SFn 3-106 ｜ FSn 3-106 ｜ SDn 3-108 ｜ FUn 3-109 ｜ TFn 3-111 ｜ DDn 3-112 ｜ DXT 3-114 ｜ FTn 3-116 ｜ FMESHn 3-118 ｜ SPDTL 3-120。
（独立落页证据示例：`1. Fna Tally Cards`@3-81、`FCn Tally Comment Card`@3-95、`Tally Energy Card`/`Tally Time Card`@3-96、`Cosine Card`@3-97、`Print Hierarchy Card`@3-98、`Tally Multiplier Card`@3-99、`Dose Energy Card`@3-103、`Energy Multiplier Card`/`Time Multiplier Card`@3-104、`Cosine Multiplier Card`/`Cell Flagging`@3-105、`Surface Flagging`/`Tally Segment Card`@3-106、`Segment Divisor Card`@3-108、`TALLYX Input Card`@3-109、`Tally Fluctuation Card`@3-111、`Detector Diagnostics Card`@3-112、`DXTRAN Card`@3-114、`Special Treatments for Tallies`@3-116、`22. FMESH Superimposed Mesh Tally`@3-118、`23. SPDTL Lattice Speed Tally Enhancement`@3-120）

> 与 §1 的 `PRINT卡说明.md`（表号表 24/31 行错）形成鲜明对比：**本篇页码是可用的**。

### 2.3 断言台账

| # | 教程断言（行号） | 原文（页） | 判定 |
|---|---|---|---|
| 1 | 记数卡用途：电流/点通量/区域加热等（:10） | 3-80 `current across a surface, ﬂux at a point, heating in a region` | ✅ |
| 2 | 只需 `Fn` 卡即可得结果，其余记数卡为可选功能（:12） | 3-80 `To obtain tally results, only the Fn card is required; the other tally cards provide various optional features.` | ✅ 逐字 |
| 3 | `n` 为用户选择的记数编号（< 999），辅助卡（如 `En`）用同一 n（:45） | 3-80 `The n is a user-chosen tally number < 999 … any other input card used with that tally (such as En for energy bins) is given the same value of n` | ✅ 逐字 |
| 4 | 归一化为每个源粒子，除非用户以 TALLYX 或 KCODE 权重修改（:14） | 3-81 `All are normalized to be per source particle unless changed by the user with a TALLYX subroutine or normed by weight in a criticality (KCODE) calculation.` | ✅ |
| 5 | §3.1 类型总表（F1/F2/F4/F5/F6/F7/F8 助记符、描述、无*/有* 单位） | 3-81 官方表：F1 current/particles/MeV；F2、F4 flux particles/cm²/MeV/cm²；F5a point or ring detector；F6 MeV/g→jerks/g；F7 fission energy MeV/g→jerks/g；F8 pulses/MeV（+F8 charge/N/A）；另含 FIP5/FIR5/FIC5 三行 | ✅ 全表一致 |
| 6 | `*F1` = 能量 × 权重（:69） | 3-81 `if the Fn card is ﬂagged with an asterisk (for example, ∗F1:N), energy times weight will be tallied` | ✅ |
| 7 | F1/F2 仅可用于栅元边界曲面且已在栅元卡中列出（:71、:76） | 3-82 `Only surfaces bounding cells and listed in the cell card description can be used on F1 and F2 tallies.` | ✅ 逐字 |
| 8 | F2 需要曲面面积（:74） | 3-82 `Only the F2 surface ﬂux tally requires the surface area.` | ✅ |
| 9 | F4 ＝ 栅元内**径迹长度估计**的通量（:79） | **2-89** `The F6 and F7 heating tallies are special cases of the F4 track length estimate of cell ﬂux`；**2-86** 径迹长度估计通量的推导 | ✅（依据在 **第 2 章**，非自标的 3-80~3-91） |
| 10 | F5 点探测器 `Fn:pl X Y Z ±R0`；X Y Z＝位置（:84-85） | 3-83 `Form for point detectors: Fn:pl X Y Z`；`X Y Z = location of the detector point` | ✅ |
| 11 | `R0 > 0`＝cm；`R0 < 0`＝mfp（:86） | 3-83 `in centimeters, if R0 is entered as positive, in mean free paths, if entered as negative` | ✅ |
| 12 | `R0 < 0` 在真空中非法**（FATAL error）**（:87） | 3-83 `(A negative entry is illegal in a void.)` | ⚠️ **超出原文的解释性补注**（非确定错误）：原文只作 "illegal"，未标 FATAL；鉴于手册在确需标 FATAL 处（如 3-84 FIC 的 `0 is FATAL error`）是会明写的，此处仍建议改用原文口径 |
| 13 | 环探测器 `Fna:pl a0 r ±R0`；`a`＝X/Y/Z（追加到编号后，如 `F5X:N`）；a0＝轴上距离；r＝环半径（:88-90） | 3-83 `Form for ring detectors: Fna:pl ao r`；`a = the letter X, Y, or Z`；`ao = distance along axis "a" where the ring plane intersects the axis`；`r = radius of the ring in centimeters` | ✅ |
| 14 | 通量成像（编号以 5 结尾）：`FIPn` 针孔、`FIRn` 平面矩形 radiograph、`FICn` 圆柱 radiograph（:91-94） | 3-83/3-84 `FIR establishes a ﬂux image on a rectangular radiograph planar grid`；`FIC … on a cylindrical radiograph grid`；3-84 `Form for ﬂux image by pinhole: FIPn:pl …`；`the tally number ending with 5` | ✅ **本 C810 确有**（非 MCNP6 专属） |
| 15 | 探测器总数 ≤ 20；记数总数 ≤ 100（:95、:191） | 3-82 `The detector total is restricted to 20. The tally total is limited to 100.` | ✅ 逐字 |
| 16 | 探测器结果误差 < 5% 通常可靠（:96） | 3-81 `detector results are generally reliable below 5%` | ✅ |
| 17 | R0 经验法则：约 1/8 ~ 1/2 平均自由程，真空中为 0（:97） | 3-86 `Rules of Thumb for R0: R0 should be about 1/8 to 1/2 mean free path for particles of average energy at the sphere and zero in a void.` | ✅ 逐字 |
| 18 | F6 为栅元能量沉积（**不包含裂变能量**）（:100） | 3-81 表：F6＝Energy deposition、F7＝Fission energy deposition；2-87/2-89 `F6 and F7 cell heating and energy deposition tallies are track length ﬂux tallies`；例 5-65 `tally type 6 track length estimate of heating` vs `type 7 … fission heating` | ✅（由 F7 定义与输出标题支持） |
| 19 | `*F6` 单位 MeV/g → jerks/g；`1 jerk = 1 GJ = 10⁹ J`（:101） | 3-82 `jerks/g (1 jerk = 1 GJ = 10⁹ J)` | ✅ 逐字 |
| 20 | F6 不允许电子（`:E`）（:102）；F7 仅中子（:106） | 3-82 `Tally 6 does not allow E. Tally 7 allows N only.` | ✅ 逐字 |
| 21 | F8 输入同 F4（栅元列表）；并集＝求和（非平均）（:166-167） | 3-87 `The F8 card is used to list the cell bins, just like an F4 tally. The union of tallies produces a tally sum, not an average.` | ✅ 逐字 |
| 22 | F8 允许：栅元/能量/用户分箱；不允许：标记、分段、乘子、时间、余弦（:168-169） | 3-87 `Cell, user, and energy bin cards are allowed. Flagging, segment, multiplier, time, and cosine bins are not allowed.` | ✅ 逐字 |
| 23 | 光子和电子同时存在时都会被记入，即使只写 `:P` 或 `:E`（:170） | 3-87 `Both photons and electrons will be tallied if present, even if only E or only P is on the F8 card. … F8:P, F8:E, and F8:P,E are all equivalent tallies.` | ✅ |
| 24 | `*F8` → 能量沉积；`+F8` → 电荷沉积（单位电子电荷）（:110-111、:180-181） | 3-87 `An asterisk on the F8 card converts the tally from a pulse height tally to an energy deposition tally. A plus … to a charge deposition tally in units of electron charge.` | ✅ 逐字 |
| 25 | 能量分箱建议含零箱与 epsilon 箱：`E8 0 1E-5 1E-3 1E-1 ...`（:113） | 3-87 `It is recommended that a zero bin and an epsilon bin be included such as / E8 / 0 1E–5 1E-3 1E-1 ...` | ✅ **逐字（含示例数值）** |
| 26 | F8 与中子兼容性差（中子输运非类比），建议仅用于光子/电子（:112） | 3-87 `CAUTION: The pulse height tally does not work well with neutrons because of the nonanalog nature of neutron transport`；`The F8 tally can be used effectively in photon problems. Electron problems may give correct results as long as the tally cells are thick enough …` | ✅（可补"电子问题需栅元足够厚"） |
| 27 | §4.1 简单格式 `Fn:pl S1 ... Sk`、通用格式 `Fn:pl S1 (S2 ... S3) (S4 ... S5) S6 S7 ...`（:123-128） | 3-82 `Simple Form: Fn:plS1 ... Sk` / `General Form: Fn:plS1 (S2 ... S3) (S4 ... S5) S6 S7 ...` | ✅ 逐字 |
| 28 | `pl` ＝ N / P / N,P / E；`Si` ＝ 曲面或栅元号，或 `T`（:132-133） | 3-82 `pl = N or P or N,P or E`；`Si = problem number of surface or cell for tallying, or T` | ✅ 逐字 |
| 29 | `T` ＝ 本卡其他所有项的并集；并对各项与并集各出一个记数（:134、:139-141） | 3-82 `The symbol T … is shorthand for a region that is the union of all of the other entries on the card. A tally is made for the individual entries on the Fn card plus the union of all the entries.` | ✅ 逐字 |
| 30 | 括号＝并集：F1（未归一）为求和，F2/F4/F6/F7（归一）为平均（:135） | 3-82 `Parentheses indicate … union … For unnormalized tallies (tally type 1), the union of tallies is a sum, but for normalized tallies (types 2, 4, 6, and 7), the union results in an average.` | ✅ 逐字 |
| 31 | 示例 `F2:N 1 3 6 T` → 4 个记数（1、3、6 各自 + 三者平均）（:139-141） | 3-82/3-83 Example 1 `This card speciﬁes four neutron ﬂux tallies, one across each of the surfaces 1, 3, and 6 and one which is the average of the ﬂux across all three` | ✅ 逐字 |
| 32 | 示例 `F1:P (1 2) (3 4 5) 6` → 3 个记数（1+2、3+4+5、6）（:144-146） | 3-83 Example 2 `three photon current tallies, one for the sum over surfaces 1 and 2; one for the sum over surfaces 3, 4, and 5; and one for surface 6 alone` | ✅ 逐字 |
| 33 | §五 `*Fn`（F1/F2/F4/F5）→ MeV；`*Fn`（F6/F7）→ jerks/g（:178-179） | 3-81 `Tally types 1, 2, 4, and 5 are normally weight tallies … if the Fn card is ﬂagged with an asterisk … energy times weight will be tallied. The asterisk ﬂagging can also be used on tally types 6 and 7 to change the units from MeV/g to jerks/g` | ✅ 逐字 |
| 34 | §六 编号＝1,2,4,5,6,7,8 或 +10 增量；不超过 3 位；`:N,P` 仅 F6、`:P,E` 仅 F8；同文件不允许同时有 `F1:N` 与 `F1:P`（:187-190） | 3-81 `Tallies are given the numbers 1, 2, 4, 5, 6, 7, 8, or increments of 10 thereof, and are given the particle designator :N, :P, or :E (or :N,P only in the case of tally type 6 or :P,E only in the case of tally type 8). … Having both an F1:N card and an F1:P card in the same INP ﬁle is not allowed. The tally number may not exceed three digits.` | ✅ 逐字 |
| 35 | 合法示例 `F4:N F14:N F104:N F234:N` / `F5:P F15:P *F305:P`（:195-196） | 3-81 逐字同例 | ✅ 逐字 |
| 36 | §七 误差可靠性：>50% 无用；20–50% 可信到数倍以内；10–20% 可疑；<10% 通常可靠（探测器除外）；探测器 <5% 可靠（:203-209） | 3-80/3-81 交界 `Results with errors greater than 50% are useless, results between 20% and 50% can be believed to within a factor of a few, results between 10% and 20% are questionable, results less than 10% are generally (but not always) reliable except for detectors, and detector results are generally reliable below 5%.` | ✅（⚠️ 漏 `but not always`） |

**统计**：36 条断言 → ✅ 34、⚠️ 2（#12 超出原文的解释性补注；#36 漏 "but not always"）、❌ 0（技术内容）＋ 头尾手册名误标 3 处。

### 2.4 修正建议（待批准，尚未执行）
1. **改手册名**：:1 标题、:3 来源行、:213 结语——C810.pdf 为 **MCNP5 卷 I+II**；如需 MCNP6 专属卡（BFLD/EMBED/KPERT 等）须另找 MCNP6 手册卷 II Ch.3（见 D-11/D-13）。
2. :87 去掉无原文依据的「（FATAL error）」，或改为原文口径「真空中（void）为非法」。
3. :208 补回原文的 `(but not always)`。
4. :213 的覆盖范围自述（3-80~3-91）与自表（到 3-120）对齐。
5. :79 的 F4「径迹长度估计」建议补依据页 **2-89**（原文不在 3-80~3-91）。
6. 可补充项：无分箱卡时得到 **1 个无界箱**且不打印其界限（3-80）；`FIC/FIR` 每卡只允许一个成像探测器、`R0` 须填 0 占位（3-84）；`FIP` 每卡只允许一个（3-85）；F8 上**中子不可记**，只有光子/电子（3-87）。

### 2.5 结论
本篇是 6 篇里**质量最高的一篇**：页码总表与原文官方表逐行一致，技术断言几乎全部可与原文逐字对上（含 `E8 0 1E-5 1E-3 1E-1` 这类示例数值）。缺陷集中在**手册名误标**（3 处）与两处加料/漏词，没有会造成用户误用卡片的实质性错误。

---

## 3. `app/docs/MCNP6_输出卡结构参考.md`（自标来源：C810 第 3-143 ~ 3-164 页）

### 3.1 概览

| 维度 | 结果 |
|---|---|
| 手册名 | ❌ :1 标题与 :3 来源行称「MCNP6 手册」（同 §2.1；:267 结语同） |
| 页码总表（9 张卡） | ✅ **9/9 正确**（另用卡词条标题落页独立复核：`1. PRDMP`@3-143、`2. LOST`/`3. RAND`@3-145、`4. DBCN`@3-146、`5. FILES`@3-148、`6. PRINT`@3-149、`7. TALNP`/`8. MPLOT`@3-151、`9. PTRAC`@3-152） |
| 各卡参数/默认值 | ✅ 基本全对（含 3-164 官方默认表逐项印证） |
| `常用打印表编号` 表 | ❌ **31 行中 28 行与原文不符** |

### 3.2 各卡台账

| # | 教程断言（行号） | 原文（页） | 判定 |
|---|---|---|---|
| 1 | 格式 `PRDMP NDP NDM MCT NDMP DMMP`（:29） | 3-143 `Form: PRDMP NDP NDM MCT NDMP DMMP`（并逐项给出 4 个释义） | ✅ |
| 2 | NDP：>0 每 NDP 个历史打印；<0 每 \|NDP\| 分钟（:34） | 3-144 `Positive entries mean that after every NDP history the summary and tallies are printed… A negative entry changes the unit from histories to minutes of computer time.` | ✅ |
| 3 | NDP 默认 = end（仅末尾）（:34） | 3-144 `Default: Print only after the calculation has successfully ended.`；3-164 默认表 `PRDMP: end −60 0 all 10 rendezvous points` | ✅ |
| 4 | NDM 默认 −60（每 60 分钟）（:35） | 3-144 `Dump every 60 minutes and at the end of the problem.`；3-164 官方默认表第 2 列 = **−60** | ✅ |
| 5 | MCT ≠ 0 时末尾生成 MCTAL（ASCII 记数文件，可绘图）；默认 0（:36） | 3-144 `If the third entry MCT … is nonzero, a MCTAL ﬁle is written at the problem end. The MCTAL ﬁle is an ASCII ﬁle of tallies that can be subsequently plotted with … MCPLOT`；默认 `Do not write a MCTAL ﬁle` | ✅ |
| 6 | NDMP＝RUNTPE 保留的最大转存数；默认 all（:37） | 3-144 `maximum number of dumps, NDMP… The RUNTPE ﬁle will contain the last NDMPs`；默认 `Write all dumps to the RUNTPE ﬁle` | ✅ |
| 7 | DMMP 三行语义表（<0 / =0 / >0，串行 TFC 与并行 rendezvous）（:42-46） | 3-144 表：`< 0  1000 particles` / `= 0  1000 particles`（串行，后倍增）、`> 0 DMMP particles`；并行列为 `1000 particles` / `10 during the run` / `DMMP particles`；正文 `results in TFC entries every 1000 particles initially. This value doubles to 2000 after 20 TFC entries`、`produces ten TFC entries and task rendezvous, rounded to the nearest 1000 particles` | ✅ 全表一致 |
| 8 | 默认行为：成功结束后才打印、每 60 分钟转存、不写 MCTAL、全部转存写 RUNTPE（:48） | 3-144 `Print only after the calculation has successfully ended. Dump every 60 minutes and at the end of the problem. Do not write a MCTAL ﬁle. Write all dumps to the RUNTPE ﬁle.` | ✅ 逐字 |
| 9 | 临界计算：正数 NDP/NDM 视为**周期数**（:50） | 3-144 `In a criticality calculation, positive entries for NDP and NDM … are interpreted as the number of cycles rather than the number of particles started.` | ✅ 逐字 |
| 10 | `LOST LOST(1) LOST(2)`；LOST(1)＝超限则 BAD TROUBLE 终止；LOST(2)＝debug 打印上限（:179-185） | 3-145 `LOST(1) = number of particles which can be lost before the job terminates with BAD TROUBLE.` / `LOST(2) = maximum number of debug prints that will be made for lost particles.` | ✅ 逐字 |
| 11 | LOST 默认 10 / 10（:184-185） | 3-145 `Defaults: 10 lost particles and 10 debug prints.`；3-164 默认表 `LOST: 10 10` | ✅ |
| 12 | 「不鼓励使用此卡」（:187） | 3-145 `Use: Discouraged.` | ✅ |
| 13 | 「丢失超过 10 个粒子通常是几何错误」（:187） | 3-145 `Losing more than 10 particles is rarely justiﬁable.` ＋ `Even if only one of many particles gets lost, there could be something seriously wrong with the geometry speciﬁcation.` | ⚠️ 加强改写：原文是"鲜有正当理由"＋"几何**可能**有严重问题"，教程说成"通常是几何错误" |
| 14 | `RAND keyword=value …`；GEN 默认 1（1=Lehmer 48-bit，2/3/4=L'Ecuyer 63-bit）（:213-218） | 3-145 `Keywords: GEN{1} SEED{19073486328125} STRIDE{152917} HIST{1}`；`1 MCNP Lehmer 48-bit congruential generator`；`2/3/4 L'Ecuyer 63-bit generator number 1/2/3` | ✅ 逐字 |
| 15 | SEED 默认 19073486328125（末尾须为奇数）；STRIDE 152917；HIST 1（:219-221） | 3-145 同上花括号默认值；`initial random number generator seed (must end with an odd digit)`；3-164 默认表 `RAND 1 19073486328125 152917 1` | ✅ 与官方默认表逐项一致 |
| 16 | 「RAND 参数优先于 DBCN 中的对应位置」（:223） | 3-145 `RAND entries take precedence over DBCN(1), DBCN(8), and DBCN(13).` | ✅（可补全为 DBCN(1)/(8)/(13)） |
| 17 | `DBCN X1 X2 X3 … X20`（:194） | 3-146 `Form: DBCN X1 X2 X 3 ... X20` | ✅ |
| 18 | X2＝调试打印间隔（每 X2 个历史）（:201） | 3-146 `X2 = debug print interval`；3-147 `X2 is used to print out information about every X2nd particle` | ✅ 逐字 |
| 19 | X3 X4＝事件日志的历史号范围（:202） | 3-147 `Event log printing is done for histories X3 through X4, inclusively.` | ✅ 逐字 |
| 20 | X5 默认 600＝每个历史事件日志最多事件数（:203） | 3-146 `Default = 600`；3-147 `X5 is the maximum number of events the event log will print per history. The default is 600.` | ✅ 逐字 |
| 21 | X11＝1 打印丢失粒子事件日志中的碰撞行（:204） | 3-146 `1 causes collision lines to print in lost particle event log`；3-147 `X11 = 1 causes collision lines to print in the lost particle event log.` | ✅ 逐字 |
| 22 | X15：≠0 打印所有记数分箱的偏移置信区间与 VOV（:205） | 3-147 `A nonzero X15th entry causes the shifted conﬁdence interval and the variance of the variance (VOV) to be calculated and printed for all tally bins.` | ✅ 语义逐字 |
| 23 | X15 默认 0；X16 默认 1（:205-206） | 正文未给这两个默认值（3-146 `Default: See below` 之后**未逐条给出**）；3-164 默认表有 DBCN 一长串数值，但线性化后**列与位置无法可靠对应** | ⚠️ **原文未直述**，需按版式复核 3-164 默认表（附录 A 亦有） |
| 24 | X16＝表 161/162 记分网格范围乘子（:206） | 3-146 `scale the score grid for the accumulation of the empirical f(x) in print tables 161 and 162`；3-147 详述 1E−30~1E30 共 60 个数量级 | ✅ |
| 25 | `FILES unit_no filename access form record_length`；unit 1~99；access=sequential/direct；form=formatted/unformatted（:230-235） | 3-148 `unit no. = 1 to 99`；`access = sequential or direct`；`form = formatted or unformatted` | ✅ 逐字 |
| 26 | 最多 6 个文件；continue-run 中非法（:236-237） | 3-148 `The maximum number of ﬁles allowed is six…`；`Not legal in a continue-run.` | ✅ 逐字 |
| 27 | 示例 `FILES 21 ANDY S F 0 22 MIKE D U 512`（:241） | 3-148 `Example 1: FILES 21 ANDY S F 0 22 MIKE D U 512` | ✅ 逐字 |
| 28 | TALNP：无参数关闭所有分箱打印；有参数只关指定编号；continue-run 用负数恢复；`TALNP 0` 恢复全部（:119-127） | 3-151 `The TALNP card with no entries turns off the bin prints for all tallies… If there are entries, it turns off the bin prints for the tally numbers that are listed… restored … with the TALNP card in an INP ﬁle used in a continue-run and the tally numbers entered … as negative numbers. A single entry of zero in a continue run restores the prints of all tally bins.` | ✅ 逐字 |
| 29 | 用途：减小 OUTP，尤其大网格成像（FIR/FIC/FIP）（:129） | 3-84 `Consider … the TALNP card to reduce size of the OUTP ﬁle for large-image grids.` | ✅ |
| 30 | MPLOT 默认间隔 `FREQ 5000`（:140） | 3-152 `If a FREQ n command is not included on the MPLOT card, n will be set to 5000.` | ✅ 逐字 |
| 31 | MPLOT 不可用命令：RMCTAL、RUNTPE、DUMP、END（:141） | 3-152 `The following commands cannot appear on the MPLOT card: RMCTAL, RUNTPE, DUMP, and END.` | ✅ 逐字 |
| 32 | 支持 `<ctrl-c>` 交互式进入 MCPLOT（:142） | 3-152 `Another way … is to use the TTY interrupt <ctrl–c>IMCPLOT or <ctrl–c>IM` | ✅ |
| 33 | PTRAC 默认文件名 PTRAC；无关键字＝记录所有事件（文件可能极大）（:152-153） | 3-152 `default name PTRAC`；`Using this card without any keywords causes all particle events to be written`；`CAUTION: An extremely large ﬁle likely will be created unless NPS is small.` | ✅ |
| 34 | 三类关键字：输出控制／事件过滤／历史过滤（:154） | 3-152 `the keywords are arranged into three categories: output control keywords, event ﬁlter keywords, and history ﬁlter keywords` | ✅ 逐字 |
| 35 | PTRAC 输出控制默认值：BUFFER 100、FILE bin、MAX 10000、WRITE pos（:160-164） | 3-153 `Table 3.8`：BUFFER `Integer > 0` 默认 **100**；FILE `asc, bin` 默认 **bin**；MAX `8 byte integer` 默认 **10000**；WRITE `pos, all` 默认 **pos** | ✅ 逐项一致 |
| 36 | MEPH 默认「—」（:163） | 3-153 `MEPH … Default: write all events.` | ⚠️ 应写明默认＝写出全部事件，而非留空 |
| 37 | 示例 `PTRAC FILTER=8,9 erg EVENT=sur NPS=1,50 TYPE=e CELL=3,4`（:168） | 3-152 同例（原文分 5 行书写：`FILTER=8,9,erg` / `EVENT=sur` / `NPS=1,50` / `TYPE=e` / `CELL=3,4`） | ✅（`8,9 erg` 是原文 `8,9,erg` 的连写） |
| 38 | 例释「…电子**穿出**栅元 3 或 4 的曲面事件」（:170） | 3-152 `will write only surface crossing events for 8–9 MeV electrons generated by histories 1–50 that have **entered** cells 3 or 4` | ❌ **方向译错**：原文是"**进入**（entered）栅元 3 或 4" |
| 39 | PTRAC 卡在 continue-run 中非法（:172） | 3-152 `The PTRAC card is not legal in a continue-run input ﬁle…` | ✅ 逐字 |
| 40 | 三、输出文件类型：OUTP 始终；RUNTPE 始终；MCTAL 由 PRDMP MCT≠0；PTRAC 由 PTRAC 卡（:250-253） | 3-144（MCTAL/RUNTPE 默认）＋ 3-152（PTRAC） | ✅ |
| 41 | 四、注意事项 1-5（PRINT 执行行优先 / 表 128 / 表 175 / PTRAC 大文件 / TALNP 只控打印）（:259-263） | 3-149、3-150、3-152、3-151（§1 已逐条核过） | ✅ |

**统计**：41 条 → ✅ 37、⚠️ 3（#13、#23、#36）、❌ 1（#38）＋ 手册名误标 3 处。

### 3.3 `常用打印表编号` 表（:75-106）——**31 行中 28 行与原文不符**

原文依据：**Table 3.7（3-150 / 3-151）**，行坐标配对证明见 §0、§1.3。

| 教程（表号 ｜ 类型 ｜ 描述） | 原文该表号实际为 | 判定 |
|---|---|---|
| 10 ｜ basic ｜ 栅元重要性 | 10 ｜ — ｜ Source coefﬁcients and distribution | ❌（栅元重要性＝60 basic） |
| 20 ｜ basic ｜ 栅元温度 | 20 ｜ — ｜ Weight window information | ❌（栅元温度＝72 basic） |
| 30 ｜ basic ｜ 截面表 | 30 ｜ — ｜ Tally description | ❌（截面表＝100 basic） |
| 40 ｜ default ｜ TFC 分箱记数分析 | 40 ｜ — ｜ Material composition | ❌（TFC bin tally analysis＝160 default） |
| 50 ｜ — ｜ 源系数与分布 | 50 ｜ — ｜ Cell volumes and masses, surface areas | ❌（源系数与分布＝10） |
| 60 ｜ — ｜ 曲面系数 | 60 ｜ basic ｜ Cell importances | ❌（曲面系数＝70） |
| 70 ｜ — ｜ 栅元体积与质量、曲面面积 | 70 ｜ — ｜ Surface coefﬁcients | ❌（＝50） |
| 80 ｜ — ｜ 记数描述 | 80 ｜ — ｜ ESPLT/TSPLT Importance Ratios | ❌（Tally description＝30） |
| 85 ｜ — ｜ 网格记数描述 | 85 ｜ — ｜ Electron range and straggling tables | ❌（Mesh tally description＝32） |
| 86 ｜ — ｜ 重合探测器 | 86 ｜ — ｜ Electron bremsstrahlung and secondary production | ❌（Coincident detectors＝35） |
| 90 ｜ — ｜ 材料组成 | 90 ｜ — ｜ KCODE source data | ❌（Material composition＝40） |
| 98 ｜ basic ｜ 强迫碰撞与指数变换 | 98 ｜ — ｜ Physical constants and compile options | ❌（＝62 basic） |
| 100 ｜ default ｜ f(x) 记数密度图 | 100 ｜ basic ｜ Cross-section tables | ❌（f(x) 密度图＝161 default） |
| 102 ｜ default ｜ 累积 f(x) 与记数密度图 | 102 ｜ — ｜ Assignment of S(α,β) data to nuclides | ❌（＝162 default） |
| 110 ｜ — ｜ 源系数与分布（可选） | 110 ｜ — ｜ First 50 starting histories | ❌（且与本节 50 号行描述重复） |
| 120 ｜ — ｜ 曲面积分 | 120 ｜ — ｜ Analysis of the quality of your importance function | ❌ |
| 126 ｜ — ｜ 重要性函数质量分析 | 126 ｜ **basic** ｜ Particle activity in each cell | ❌（重要性函数质量分析＝120） |
| **128 ｜ — ｜ 宇宙映射（重复结构，需初始运行开启）** | 128 ｜ — ｜ Universe map | ✅ |
| 130 ｜ basic ｜ 各栅元粒子活动 | 130 ｜ — ｜ Neutron/photon/electron weight balance | ❌（粒子活动＝126 basic） |
| 140 ｜ — ｜ 中子/光子/电子权重平衡 | 140 ｜ — ｜ Neutron/photon nuclide activity | ❌（＝130） |
| 150 ｜ — ｜ 核素活动 | 150 ｜ — ｜ DXTRAN diagnostics | ❌（＝140） |
| 160 ｜ — ｜ DXTRAN 诊断 | 160 ｜ **default** ｜ TFC bin tally analysis | ❌（＝150） |
| 161 ｜ — ｜ 权重窗生成器摘要 | 161 ｜ default ｜ f(x) tally density plot | ❌（WW generator summary＝190 basic） |
| 162 ｜ — ｜ 权重窗生成窗口 | 162 ｜ default ｜ Cumulative f(x) and tally density plot | ❌（WW generated windows＝200 basic） |
| 170 ｜ — ｜ 问题截断总结 | 170 ｜ — ｜ Source distribution frequency tables, surface source | ❌（且"问题截断总结"在本 C810 Table 3.7 中**不存在**） |
| **175 ｜ shorten ｜ keff 按周期估计** | 175 ｜ shorten ｜ Estimated keff results by cycle | ✅ |
| **178 ｜ — ｜ keff 按批次大小估计** | 178 ｜ — ｜ Estimated keff results by batch size | ✅ |
| 190 ｜ — ｜ 物理常数与编译选项 | 190 ｜ **basic** ｜ Weight window generator summary | ❌（物理常数＝98） |
| 198 ｜ — ｜ ESPLT/TSPLT 重要性比率 | 198 ｜ — ｜ Weight windows from multigroup ﬂuxes | ❌（ESPLT/TSPLT＝80） |
| 200 ｜ — ｜ 电子射程与 Straggling 表 | 200 ｜ **basic** ｜ Weight window generated windows | ❌（电子射程＝85） |

**统计**：✅ 3 行（128 / 175 / 178）、❌ 28 行；类型列错 10 处以上；漏收原文的 32、62、72 三行。
> **注意**：本篇与 §1 `PRINT卡说明.md` 的 31 行表**同源同错但错法不同**（例如 80/85/86/90 号的错法在两篇里不一致）——说明不是复制同一份错误，而是两次各自"凭记忆/凭印象"生成。

### 3.4 交叉发现（供两篇共用）
- **表号尺度冲突**：3-82 正文写 `The detector total is restricted to 20. The tally total is limited to 100.`（§2 已核 ✅），而 C810 **3-164 Table 3.12 Storage Limitations** 写 `Total number of tallies: NTALMX = 1000`、`Detectors: MXDT = 100`。两者口径不同（输入卡数量限制 vs 存储维度），教程若要写"上限"应注明依据页，否则读者会困惑。
- **3-164 `Table 3.11: Summary of MCNP Input Cards`** 是官方默认值表，本次用它独立印证了 PRDMP（`end −60 0 all 10 rendezvous points`）、LOST（`10 10`）、FILES（`none none sequential formatted`）、PRINT（`*short output`）、TALNP（`no bin prints for tallies`）、RAND（`1 19073486328125 152917 1`）——建议后续修正时以该表为准绳。

### 3.5 修正建议（待批准，尚未执行）
1. **整表替换** `常用打印表编号`（:75-106）：直接采用 §1.3 的原文映射（含类型列），并补 32/62/72；与 §1 的 PRINT 卡篇使用**同一张**修正表，避免两处再分叉。
2. :170 「穿出」→「**进入**（entered）」。
3. :163 MEPH 默认写为「写出全部事件」（原文 `Default: write all events`）。
4. :187 「丢失超过 10 个粒子通常是几何错误」→ 按原文口径「丢失超过 10 个粒子鲜有正当理由；即使只丢一个，几何也可能存在严重问题」。
5. :205-206 X15/X16 默认值先核实 3-164 默认表版式（或附录 A）再写；未核实前标注"原文未直述"。
6. 改手册名（:1、:3、:267）。

### 3.6 结论
本篇**各卡参数部分质量高**（41 条断言里 37 条 ✅，页码 9/9 对，默认值与官方默认表逐项吻合），缺陷集中在两处：**`常用打印表编号` 表 28/31 行错**（与 PRINT 卡篇同源同错但错法不同）与 1 处方向译错（entered → 穿出）。表号表若不修，用户按它写 `PRINT` 卡会得到与预期相反的输出。

---

## 4. `app/docs/C810_卡片格式详细.md`（自标来源：C810.pdf ｜ MCNP5 Vol.II Ch.3）

### 4.1 概览

| 维度 | 结果 |
|---|---|
| 手册名标注 | ✅ 头部写 `MCNP5 Vol.II Ch.3` —— **6 篇里唯一正确标注 C810 身份的一篇** |
| 附录《卡片速查索引》52 行页码 | **49 ✅ / 1 ❌ / 2 ⚠️** |
| 卡格式与默认值 | ✅ 绝大多数（含与 Table 3.11 官方默认表逐项吻合） |
| 重大内容错误 | ❌ 3 处：`TXY/TXZ/TYZ` 三种曲面在 C810 全文**不存在**；`X/Y/Z` 曲面语义写错；`FTn` 关键字表错；材料卡 `ZAID` 字母表错（详见下） |

> 原文依据（官方结构表）：**Table 3.11 Summary of MCNP Input Cards**（3-161 ~ 3-164）给出各卡官方默认值；**Table 3.1 MCNP Surface Cards**（3-13）给出曲面类型表；**Table 3.3 Source Variables**（3-55 ~ 3-56）给出 SDEF 变量默认值；**Table 3.5**（3-101 附近）给出特殊乘子反应号。

### 4.2 附录《卡片速查索引》页码核对（52 行）

| 判定 | 条目 | 证据 |
|---|---|---|
| ❌ | `PRINT ｜ 3-144` | 原文 PRINT 词条起于 **3-149**（3-144 是 PRDMP 的续页；Table 3.11 亦列 PRINT 于 3-149 段） |
| ⚠️ | `SIn / SPn / SBn ｜ 3-63` | 词条标题（`2. SIn / Source Information Card` 等）在 **3-62**，正文跨到 3-63；引哪一页都可以，但与同表其他行（取词条首页）口径不一致 |
| ⚠️ | `MTn ｜ 3-138` | 页号 ✅，但**助记符应为 `MTm`**（原文 `4. MTm / S(α,β) Material Card`，3-138；索引亦作 “S(α,β) Material (MTm) card, 3-138”） |
| ✅ | 其余 49 行 | 逐条与「卡词条标题落页」及 Table 3.11 一致：栅元 3-9、曲面 3-11、MODE 3-24、VOL 3-24、IMP:n 3-34、SDEF 3-54、DSn 3-66、SSW 3-70、SSR 3-72、KCODE 3-77、KSRC 3-78、Fn 3-81、FCn 3-95、En/Tn 3-96、Cn 3-97、FQn 3-98、FMn 3-99、DEn/DFn 3-103、EMn/TMn 3-104、CMn/CFn 3-105、SFn/FSn 3-106、SDn 3-108、FUn 3-109、TFn 3-111、DDn 3-112、DXT 3-114、FTn 3-116、FMESHn 3-118、SPDTL 3-120、Mn 3-122、MPNn 3-124、TOTNU/NONU 3-126、PHYS:N 3-131、PHYS:P 3-133、PHYS:E 3-134、TMP 3-136、CUT:n 3-139、ELPT:n 3-140、NOTRN/NPS 3-141、CTME 3-142 |

### 4.3 §9 输入文件结构与通用格式规则 —— ✅ 主体正确，4 处不完整/不精确

| 教程写（行号） | 原文（页） | 判定 |
|---|---|---|
| 每行不超过 80 列（:663） | 3-4 `All input lines are limited to 80 columns.` | ✅ 逐字 |
| 卡片名在 1-5 列开始（:664） | 3-4 `Cell, surface, and data cards all must begin within the ﬁrst ﬁve columns.` | ✅ 逐字 |
| 条目空格分隔（:665） | 3-4 `Data entries are separated by one or more blanks.` | ✅ |
| 注释：**第 1 列 'c'** ＝整行注释（:666） | 3-4 `Comment cards … must have a C **anywhere in columns 1−5** followed by at least one blank.` | ⚠️ 应为"1−5 列内任意位置有 C" |
| 续行：行尾 `&`（:668） | 3-4 `Blanks in the first five columns indicate a continuation … **Alternatively, an & (ampersand) preceded by at least one blank ending a line** indicates data will continue` | ✅ `&` 确有（此前怀疑不成立）；⚠️ 但漏了**主规则**（前五列留空） |
| `nJ` / `nR` / `nI`（:669-671） | 3-4/3-5 五个特性：`nR`、`nI`、**`nILOG`**、**`xM`**、`nJ` | ⚠️ 漏 `nILOG`（对数插值）与 `xM`（乘子） |
| 数据卡块"隐式终止（无空行要求）"（:657） | Table 3.11 `Data cards plus blank terminator`（3-161） | ⚠️ 原文列了空行终止符 |

### 4.4 §1 栅元卡 —— ✅ 全部正确

| 教程断言 | 原文 | 判定 |
|---|---|---|
| `j m d geom params`；j ＝ 1 ~ 99999（:8、:12） | 附录卡格式表 `cell number; begins in columns 1-5; J = 1-99999` | ✅ |
| `m = 0` 表示真空（:13） | 3-2 `a single zero to indicate a void cell` | ✅ |
| 密度：+数＝原子密度（10²⁴/cm³），−数＝质量密度（g/cm³）（:14） | 附录表 `0 atom density in units of atoms/barn-cm (10-24 atoms/cm3)` / `0 mass density in units of grams/cm3`；3-9 同义 | ✅ 逐字 |
| geom：`:` 并、`#` 补、`()` 优先级（:15） | 3-2 起（`: `＝union、`#n`＝complement）；附录 `complement operator format: #n` | ✅ |
| `LIKE m BUT` 继承并改参数（:19-23） | 3-9~3-10 `cards with LIKE m BUT`；`The LIKE n BUT feature uses keywords for the cell material number and density. The mnemonics are MAT and RHO` | ✅ |

### 4.5 §2 曲面卡 —— ✅ 多数正确，**2 处内容错误**

| 教程段落 | 原文（页） | 判定 |
|---|---|---|
| 平面 `P Ax+By+Cz=D` / `PX D` …（:43-46） | Table 3.1（3-13）`Ax + By + Cz – D = 0`、`x – D = 0` … | ✅ |
| 球面 `SO R` / `SX Xc R` / `S Xc Yc Zc R`（:51-55） | Table 3.1 球面组 | ✅ |
| 柱面 `CX R` / `C/X Xc Yc Zc R`（:60-65） | Table 3.1 柱面组（`C/X` 平行 X 轴、`CX` 在 X 轴上） | ✅ |
| 锥面 `KX x0 t2 (±1)` 等（:70-75） | Table 3.1 锥面组（`K/X` 平行轴、`KX` 在轴上"used only for 1 sheet cone"） | ✅ 形式与条目数一致（⏳ ±1 分支的"哪一叶/正侧"措辞与 §5 曲面卡专篇同名断言，将在 §5 一并逐字核） |
| `SQ A B C D E F G x0 y0 z0`；`GQ A B C D E F G H J K`（:80-82） | Table 3.1：SQ `A B C D E F G`＋中心、GQ `A B C D E F G H J K` | ✅ |
| 环面 `TZ/TX/TY x0 y0 z0 A B C`（:87-89） | Table 3.1 环面组 `A B C`；3-19 `The TX, TY, and TZ input cards represent elliptical tori` | ✅ 形式一致（⏳ 方程写法待核） |
| **椭圆柱面 `TXY Yc Zc A B` / `TXZ` / `TYZ`（:92-97）** | **全库 0 命中**：Table 3.1（3-13）无此三类；2.58 M 字符全文检索 `TXY`/`TXZ`/`TYZ` 均无 | ❌ **C810 不存在这三种曲面**——椭圆柱应走 `GQ`/`SQ`（轴平行坐标轴）或宏体 `REC` |
| **坐标平面 `X x0` / `Y y0` / `Z z0`（:99-104）** | 3-15~3-16 `Surface cards of type X, Y, and Z can be used to describe surfaces by **coordinate points** rather than by equation coefﬁcients`；`If one coordinate pair is used, a plane (PX, PY, or PZ) is defined. If two … a linear surface … If three … a quadratic surface`；例 `j X 7 5 3 2 4 3` → 被转成 `SQ` | ❌ **语义写错**：X/Y/Z 不是"单值坐标平面"，而是"用 1~3 个 (坐标, 半径) 点对定义曲面"的卡片 |
| 宏体参数顺序：`BOX/RPP/SPH/RCC/REC/TRC/ELL/WED/ARB/RHP`（:107-119） | 3-18~3-21：`BOX Vx Vy Vz A1… A3`、`RPP`、`SPH`、`RCC`、`REC`（12 项，10 项缩略＝次半径）、`TRC R1 R2`、`ELL V1 V2 Rm`、`WED`（顶点＋三个向量）、`ARB`（8 个三重坐标＋6 个四位面号，共 30 项）、`RHP/HEX`（v/h/r/s/t 五组共 15 项） | ✅ 条目数与语义一致（`WED`/`ELL` 教程用 A1A2A3 记法，位置等同原文 V1x V1y V1z 向量） |

### 4.6 §3 源卡 —— SDEF 变量表与原文 Table 3.3 逐项比对（20 项）

| 变量 | 教程写（:133-152） | 原文默认（3-55/3-56 Table 3.3） | 判定 |
|---|---|---|---|
| CEL | 由 XYZ 确定 | Determined from XXX, YYY, ZZZ and possibly UUU, VVV, WWW | ✅ |
| SUR | 0＝体源 | Zero (means cell source) | ✅ |
| ERG | 14 | 14 MeV | ✅ |
| TME | 0 | 0 | ✅ |
| DIR | 体源各向同性、面源 p(µ)=2µ | Volume: isotropic；Surface: p(µ)=2µ | ✅ |
| VEC | 面源：法向 | Surface: vector normal to the surface with sign determined by NRM | ✅ |
| NRM | +1 | + 1 | ✅ |
| POS | 0 0 0 | 0,0,0 | ✅ |
| RAD | 0 | 0 | ✅ |
| **EXT** | **"无"** | **0**（cell 情形：沿 AXS 距 POS 的距离；surface 情形：与 AXS 夹角的余弦） | ❌ **默认值写错**（原文为 0） |
| AXS | 无 | No direction | ✅ |
| X / Y / Z | 无 | No X / No Y / No Z | ✅ |
| CCC | 无 | No cookie-cutter cell | ✅（**C810 确有 CCC**，3-55/3-56） |
| ARA | 无 | None | ✅ |
| WGT | 1 | 1 | ✅ |
| EFF | 0.01 | .01 | ✅ |
| PAR | 1=N, 2=P, 3=E, **4=F(正电子)** | 3-56：`1 or N`、`2 or P`、`3 or E`；`A special syntax allows PAR to be specified as **4 or F** to make the source type a positron` | ✅ **逐字** |
| TR | 无 | None | ✅ |

其他源卡断言：

| 教程写 | 原文 | 判定 |
|---|---|---|
| `SI[n] [type]`，类型 `L/A/H/S`（:167-168） | 3-62/3-63：option `omitted or H`（默认直方图边界）、`L`、`A`、`S` | ✅（可注 H 为默认） |
| `SP[n] [type]`，类型 `D` 或无（:173-174） | 3-63：option 允许 `omitted`、`D`（默认）、**`C`（累积概率）**、**`V`（按栅元体积）**，另有 `SPn f a b` 内置函数形式 | ⚠️ **漏 C / V 两个选项与内置函数形式** |
| `DS[n] var Dn1 Dn2 …`（:184） | 3-66 `5. DSn / Dependent Source Distribution Card` | ⏳ 形式未逐字核（该词条在 3-66，本轮未展开） |
| `KCODE NSRC RKK IKZ KCT [KNRM]`；NSRC ~10000、RKK ~1.0、IKZ ~50、KCT ~1000（:205-210） | Table 3.11（3-162）官方默认行：`KCODE 1000 1 30 130 MAX(4500,2∗NSRCK) 0` | ⚠️ 教程的 10000/50/1000 **不是 C810 默认值**（默认 1000/1/30/130/0）；作为"典型值"可以，但未与默认值区分 |
| `KSRC 0 0 0 2 0 0 -2 0 0`（:216） | 3-78 KSRC 三元组坐标；索引 `KSRC, 3-78` | ✅ |

### 4.7 §4 计数卡

| 教程写 | 原文 | 判定 |
|---|---|---|
| `En E1 … Ek [NT/C]`（:289） | 3-96 `Tally Energy Card`；3-96/3-97 `by putting the symbol NT at the end of the En card`、`The symbol C …` | ✅ |
| `Tn T1 … Tk`（:296） | 3-96 `Tally Time Card`（NT / C 同 En） | ✅ |
| `Cn mu1 … munk`（:302） | 3-97 `Cn / Cosine Card (tally type 1 only)` | ✅（原文 "munk" 系笔误，非技术错） |
| `FMn C m r1 r2 …`；`ri` 负数＝特殊处理，`-6`＝裂变（:308-312） | 3-99 `Tally Multiplier Card`；Table 3.5（3-101 附近）：`−4 average heating number`、`−5 gamma-ray production`、**`−6 total fission cross section`**、`−7 fission ν`（光子列另有 −6 photon heating number） | ✅ `-6`＝总裂变截面（中子）正确；⚠️ 可补充"`C` 为负时乘原子密度"这一规则 |
| **`FTn` 关键字：`TAL, PHL, CAP, FFT, INC, GEO, …`（:326）** | 3-116/3-117 FTn 的 ID 全集＝**`FRV`、`GEB`、`TMC`、`INC`、`ICD`、`SCX`、`SCD`、`PTT`、`ELC`**（共 9 个） | ❌ **表错（相对所标出处 3-116）**：教程列的 6 个里只有 `INC` 在该词条内。**复核细化**：`PHL`/`CAP`/`FFT` 是本 PDF 内 **MCNP6.1 发布说明**（p29~p37 段）里真实存在的 FT 选项（另有 `PDS`、`ROC`），故性质是"混入 MCNP6 时期选项却挂在 MCNP5 词条名下"；而 **`TAL`、`GEO` 在 2.58 M 字符全库中找不到任何作为 FT 选项的依据**（`TAL` 仅出现为 Fortran 数组名） |
| `FMESHn:N/P/E GEOM=… ORIGIN=… IMESH/IINTS/JMESH/JINTS/KMESH/KINTS`（:331-334） | 3-118 `22. FMESH Superimposed Mesh Tally`；`n = tally number (only type 4 tallies are permitted)`；Table 3.6 关键字表 | ✅（与 §1/§2 已核内容一致） |
| `:337` 自注「2026-08-13 审计补录 … **格式细节待 C810.pdf 页级核验**」的 11 张辅助卡（FCn/FQn/EMn/TMn/CMn/CFn/SFn/FSn/SDn/FUn/TFn/DDn/DXT/SPDTL） | 页号与助记符见 §2 已验证（22/22 ✅） | ✅ 页码/助记符已核；**这些条目本身只写了意义、没写格式**，属"占位"——本次核验可为其补格式 |

### 4.8 §5 材料卡 —— **ZAID 字母表错误**

| 教程写（:406-407） | 原文 | 判定 |
|---|---|---|
| `c=中子连续` | Ch.2 `ZZZAAA.nnC`＝连续能量中子表 | ✅ |
| **`g=中子多群`** | `ZZZAAA.nnM`＝多群中子；`ZZZAAA.nnG`＝多群光子 | ❌ |
| **`y=光原子`** | `ZZZ000.nnP`＝光原子表；`ZZZAAA.nnY`＝**剂量（dosimetry）** | ❌ |
| `e=电子` | `ZZZ000.nnE`＝电子表 | ✅ |
| `u=光核` | `ZZZAAA.nnU`＝光核表 | ✅ |
| **`r=剂量`** | 剂量＝`nnY`；`D`＝离散反应表（教程漏） | ❌ |

其余材料卡断言：

| 教程写 | 原文（3-122/3-123） | 判定 |
|---|---|---|
| `Mn ZAID f …`；正数＝原子分数、负数＝质量分数（:399-408） | 3-122/3-124：`atomic fraction (or weight fraction if entered as a negative number)`；`Atom and mass fractions cannot be mixed on the same material card` | ✅（可补"不可混用"与"会自动归一"） |
| `GAS=n`：0＝固/液、1＝气态（:413） | 3-122 `GAS = m flag … m = 0 … condensed (solid or liquid) … m = 1 … gaseous` | ✅ |
| `ESTEP`（:414） | 3-122 `causes the number of electron substeps per energy step to be increased to n … If n is smaller than the built-in default … the entry is ignored` | ✅（可补"小于内建默认则忽略"） |
| `NLIB/PLIB/PNLIB/ELIB`（:415-418） | 3-122 四条 xLIB 关键字齐全 | ✅ |
| `COND=n`：<0 非导、0 默认、>0 导（:419） | 3-122 **COND 确在 C810**：`sets conduction state of a material only for el03 evaluation. < 0 nonconductor; = 0 (default) …; > 0 conductor …` | ✅（原文是"仅对 el03 评价生效"＋默认值语义更细） |
| `MPNn`、`TOTNU`、`NONU`（:434-450） | 3-124 `MPNn Photonuclear Nuclide Selector`；3-126 `TOTNU`/`NONU`；Table 3.11 `TOTNU *prompt（非 KCODE）/ total（KCODE）`、`NONU *ﬁssion treated as real ﬁssion` | ✅ |

### 4.9 §6/§7/§8 物理卡、截断卡、其他卡 —— ✅ 与 Table 3.11 官方默认行逐项一致

| 教程写 | Table 3.11 官方默认（3-163） | 判定 |
|---|---|---|
| PHYS:N `EMAX EMCNF IUNR DNB FISNU`；EMAX 默认极大、EMCNF 0.0、IUNR 0、DNB −1、FISNU 0 | `PHYS:N *very large 0 0 –1 0` | ✅ **逐项一致** |
| PHYS:P `EMCPF IDES NOCOH ISPN NODOP`；EMCPF 默认 100、IDES 0、NOCOH 0、ISPN 0、NODOP 0 | `PHYS:P *100 0 0 0 0` | ✅ **逐项一致** |
| PHYS:E 十个参数 `EMAX IDES IPHOT IBAD ISTRG BNUM XNUM RNOK ENUM NUMB`；默认 EMAX=100、IDES/IPHOT/IBAD/ISTRG=0、BNUM/XNUM/RNOK/ENUM=1 | 3-134 原文 Form 正是这 **10 个**；`Defaults: EMAX = 100 MeV; IDES, IPHOT, IBAD, ISTRG = 0; BNUM, XNUM, RNOK, ENUM = 1., NUMB = 0` | ✅（原文示例行只写 9 值＝NUMB 取默认 0） |
| TMP 默认 `2.53e-8` MeV（≈293.6 K） | `TMP 2.53 x 10−8` | ✅ **逐字** |
| CUT:N `T=极大 E=0.0 WC1=−0.50 WC2=−0.25 SWTM=自动`；CUT:P `E=0.001 WC1=−0.50 WC2=−0.25`；CUT:E `E=0.001 WC1=0 WC2=0` | `CUT:N very large 0 −0.5 −0.25 SWTM`；`CUT:P very large .001 −0.5 −0.25 SWTM`；`CUT:E very large .001 0 0 SWTM` | ✅ **逐项一致** |
| `ELPT:n … 实际使用 max(ELPT_i, CUT:n E)` | Table 3.11 `ELPT cut card energy cutoff`（3-163） | ✅（"取较大者"语意见 3-140，本轮未逐字摘） |
| `NPS N [NPSMG]`；`CTME minutes`；`NOTRN`（:570-584） | Table 3.11 `NPS none`、`CTME none`、`NOTRN direct-only neutral particle detector contributions` | ✅ |
| `MODE N P E`（示例）、`IMP:n I1 I2 …`、`VOL`、`MTn` | Table 3.11 `MODE N`、`IMP required unless weight windows used`、`VOL 0`、`MTm none` | ⚠️ 教程把 S(α,β) 卡写作 **`MTn`**，原文为 **`MTm`**（3-138）；其余 ✅ |

### 4.10 修正建议（待批准，尚未执行）
1. **删掉虚构的曲面类型**：`TXY/TXZ/TYZ`（:92-97）三种"椭圆柱面"曲解为 C810 不存在的助记符 → 删或改为 `GQ`/`SQ`/宏体 `REC`。
2. **改正 X/Y/Z 曲面语义**（:99-104）：改为"用 1~3 个 (坐标, 半径) 点对定义曲面"，并给原文例 `j X 7 5 3 2 4 3`。
3. **重写材料卡 ZAID 字母表**（:406-407）：`C`＝连续中子、`D`＝离散反应、`M`＝多群中子、`G`＝多群光子、`P`＝光原子、`E`＝电子、`U`＝光核、`Y`＝剂量（`t` 后缀用于 MT 热散射表）。
4. **重写 FTn 关键字表**（:326）：改为 `FRV / GEB / TMC / INC / ICD / SCX / SCD / PTT / ELC`。
5. 修 `PRINT` 页码 3-144 → **3-149**；`MTn` → **`MTm`**；`SIn/SPn/SBn` 页码与同表口径统一（3-62 词条首页）。
6. SDEF 的 `EXT` 默认值由"无"改为 **0**；`SPn` 补 `C` / `V` 选项与 `SPn f a b` 形式。
7. 格式规则补：注释卡是"1−5 列内任意位置有 C"；续行主规则是"前五列留空"（`&` 为替代）；补 `nILOG` 与 `xM`；数据卡块亦有空行终止符。
8. KCODE 处把"官方默认 1000/1/30/130/0"与"常用取值"分开写。
9. 对 `:337` 那批"待核"补录条目，用 §2 已核实的页号/助记符补齐格式（FCn/FQn/EMn/TMn/CMn/CFn/SFn/FSn/SDn/FUn/TFn/DDn/DXT/SPDTL）。

### 4.11 结论
本篇是**信息量最大、也是最需要修的一篇**：页码索引（52 行）只有 1 处真错，物理/截断/材料关键字与官方默认表几乎逐项吻合；但**曲面、材料 ZAID、FT 三处是"凭印象生成"的实质性错误**——其中 `TXY/TXZ/TYZ` 在权威手册中根本不存在、`X/Y/Z` 语义相反、ZAID 字母 `g/y/r` 对应关系错误，用户照抄会直接得到错误输入卡。文件自身对补录段已诚实标注"待 C810 页级核验"，本次核验正好把这段清单变成可执行结论。

---

## 5. `app/docs/MCNP6_曲面卡格式参考.md`（自标来源：C810 第 3-11 至 3-24 页）

### 5.1 概览

| 维度 | 结果 |
|---|---|
| 手册名 | ❌ 标题 `MCNP6 曲面卡…`、:3 来源行、:567 结语均称「MCNP6 手册」（同 §2/§3 病灶） |
| 技术断言 | **✅ 绝大多数逐字可对，是全 6 篇里核验质量最高的一篇**；❌ 1 处（§七示例 3）、⚠️ 1 处（ε/∞） |
| 页码引用 | ✅ 3-11 ~ 3-24 覆盖正确；正文内引用（3-12、3-13、3-14、3-15、3-16、3-17、3-18、3-22、3-30、3-31、4-16、2.C.1）**逐条命中** |
| 自记历史修正 | ✅ `:116-117` 自述"早期把环面 A/C 抄反、2026-09-16 已修正并加回归测试"——本轮独立复核确认**现版本正确**（见 §5.4） |

### 5.2 §一 通用格式（3-11）—— ✅ 全部正确

| 教程断言（行号） | 原文 | 判定 |
|---|---|---|
| 格式 `j n a list`（:11） | 3-15 `Form: j n a list`（轴的 X/Y/Z 卡）；3-17 三点平面同构 | ✅ |
| `1 ≤ j ≤ 99999`（:16） | 3-15 / 3-17 `1 ≤ j ≤ 99999` | ✅ 逐字 |
| 前加 `*`＝反射面（镜面反射）（:16、:21） | 3-12 `If the surface number is preceded by an asterisk, a reﬂecting surface is deﬁned. A particle track that hits a reﬂecting surface is reﬂected specularly.` | ✅ 逐字 |
| 前加 `+`＝白边界（:16、:22） | 3-12 `If the surface number is preceded by a plus, a white boundary is deﬁned.` | ✅ 逐字 |
| `n`：空＝无变换；>0＝TRn（1≤n≤999）；<0＝与曲面 \|n\| 周期（:17） | 3-17 `absent for no coordinate transformation`／`> 0, speciﬁes number of TRn card`／`< 0, speciﬁes surface j is periodic with surface n`；3-30 `1 ≤ n ≤ 999` | ✅ 逐字 |
| 周期面 7 条限制（:24-30） | 3-12 逐条：j/k 必须为平面、不允许变换、顶底面可为反射/白但不可周期、只能与周期面或顶底面相邻、每面一侧须有单一零重要性栅元、共同旋转矢量垂直于顶底面、不应使用探测器/DXTRAN | ✅ **7/7 逐字** |
| 感度：球/柱/锥/环面正侧＝外部；PX/PY/PZ 超截距为正；P/SQ/GQ 由系数决定（:32-33） | 3-12 `For the P, SQ and GQ surfaces, the user supplies all of the coefficients … can determine the sense of the surface at will. This is different from the other cases where the sense … is uniquely determined by the form`；3-14 例 1 `positive sense for all points with y > 3`；例 2 `Points outside the cone have a positive sense`；例 3 `The sense is positive for points outside the cylinder` | ✅ |

### 5.3 §二 方程定义曲面（Table 3.1，3-13）—— ✅ 正确；锥面/环面两段尤其准确

| 教程段落 | 原文 | 判定 |
|---|---|---|
| 平面 P/PX/PY/PZ 方程与输入项（:43-46） | Table 3.1 `Ax + By + Cz – D = 0`、`x – D = 0`…`A B C D`、`D` | ✅ |
| 球面 SO/S/SX/SY/SZ（:52-56） | Table 3.1 球面组 | ✅ |
| 柱面 C/X、C/Y、C/Z、CX、CY、CZ（:62-67） | Table 3.1 柱面组 | ✅ |
| SQ `A B C D E F G x̄ ȳ z̄`、GQ `A B C D E F G H J K`（:90-91） | Table 3.1 SQ/GQ 行 | ✅ |
| 锥面 `K/X … KZ`：`t²` + 可选 `±1`；**t＝半开角正切，卡上输入 t²**（:73-78、:80） | 3-14 例 2 `The tangent t of the opening angle of the cone is 0.5 (note that t2 is entered)` | ✅ 逐字 |
| **省略 `±1`＝双叶锥**；**给出 `+1`＝朝 +轴延伸到无穷的那一片，`−1` 反之**；所选叶片内部为负侧、锥外为正侧（:80-84） | **2.C.1 `Explanation of Cone and Torus`**（2-9/2-10）：`The quadratic equation for a cone describes a cone of two sheets … The +1 or the −1 entry on the cone surface card causes the one sheet cone treatment to be used. If the sign of the entry is positive, the specified sheet is the one that extends to infinity in the positive direction of the coordinate axis to which the cone axis is parallel.`；3-14 例 2 `only the positive (right hand) sheet … Points outside the cone have a positive sense.` | ✅ **逐字**；且教程标注的出处 `§2.C.1` **精确命中** |
| 环面 `TX/TY/TZ x̄ ȳ z̄ A B C`（:97-99） | 3-14 `The TX, TY, and TZ input cards represent elliptical tori (fourth degree surfaces)` | ✅ |
| 方程 `s²/B² + ((r−A)²/C²) = 1`；TY 时 `s=(y−ȳ)`、`r=√[(x−x̄)²+(z−z̄)²]`（:104-109） | 3-14 图 3-1b 方程 `s²/b² + (r−a)²/c² = 1`；`In the case of a TY torus, s = (y−ȳ) and r = √[(x−x̄)²+(z−z̄)²]` | ✅ **逐字（教程 A/B/C ↔ 原文 a/b/c 一一对应）** |
| A＝主半径、B＝轴向次半径、C＝径向次半径，三者不可互换（:111-114） | 3-14 `the input parameters a b c specify the ellipse rotated about the s-axis in the (r,s) cylindrical coordinate system`；`|a| < c` 退化判定 | ✅（角色与原文一致；这正是该文件自记修正的那一处，现已正确） |
| 退化：`0<A<C` 外表面、`−C<A<0` 内表面（:119-121） | 3-14 `A torus is degenerate if |a| < c where 0 < a < c produces the outer surface (Figure 3-1c), and −c < a < 0 produces the inner surface (Figure 3-1d).` | ✅ 逐字 |
| 环面坐标变换限于辅助系各轴与主系对应轴平行（:123） | 3-15 `Coordinate transformations for tori are limited to those in which each axis of the auxiliary coordinate system is parallel to an axis of the main system.` | ✅ 逐字 |

### 5.4 §三 轴对称曲面（由点定义，3-15 / 3-16）—— ✅ 全部正确

| 教程断言 | 原文 | 判定 |
|---|---|---|
| 格式 `j n X x1 r1 [x2 r2] [x3 r3]`；`r = √(x²+z²)`（Y 卡）（:132-137） | 3-15 `a = the letter X, Y, or Z`／`list = one to three coordinate pairs`；3-16 `ri = √(xi² + zi²)` | ✅ |
| 1 点→平面（PX/PY/PZ）；2 点→线性曲面；3 点→二次曲面（含 SQ）（:143-145） | 3-16 逐字三行规则 | ✅ 逐字 |
| 两点指定锥面→仅单叶片（:147） | 3-16 `When a cone is specified by two points, a cone of only one sheet is generated.` | ✅ 逐字 |
| SQ 感度＝离对称轴足够远为正侧，与方程定义 SQ 不同（:148） | 3-16 `For SQ, the sense is defined so that points sufﬁciently far from the axis of symmetry have positive sense. Note that this is different from the equation-deﬁned SQ` | ✅ 逐字 |
| 示例 `j X 7 5 3 2 4 3` → 双叶双曲面（:150-151） | 3-16 例 1 逐字（并给出等价 SQ 系数） | ✅ 逐字 |
| 错误示例 `j Y 1 2 1 3 3 4` → 两平行平面、FATAL（:153-154） | 3-16 例 2 `This describes two parallel planes at Y = 1 and Y = 3 and is a FATAL error because the requirement that all points be on the same sheet is not met.` | ✅ **逐字（连示例数值都一样）** |

### 5.5 §四 三点定义一般平面（3-17 / 3-18）—— ✅ 正确（1 处措辞）

| 教程断言 | 原文 | 判定 |
|---|---|---|
| 格式 `j n P X1 Y1 Z1 X2 Y2 Z2 X3 Y3 Z3`（:163） | 3-17 `Form: j n P X1 Y1 Z1 / X2 Y2 Z2 / X3 Y3 Z3` | ✅ |
| 4 项＝方程系数；>4 项＝三点坐标（:172-173） | 3-17 `If there are four entries on a P card, they are assumed to be the general plane equation coefﬁcients … If there are more than four entries, they give the coordinates of three points` | ✅ 逐字 |
| 感度 5 条：原点负侧；D=0→点 (0,0,**ε**)；D=C=0→(0,**ε**,0)；D=C=B=0→(**ε**,0,0)；三点共线→FATAL（:176-180） | 3-17/3-18 `requiring the origin to have negative sense. If the plane passes through the origin (D = 0), the point (0, 0, ∞) has positive sense. If this fails (D = C = 0), the point (0, ∞, 0) … If this fails (D = C = B = 0), the point (∞, 0, 0) … If this fails, the three points lie in a line and a FATAL error is issued.` | ⚠️ 原文作 **∞**，教程作 ε（语义同"沿该轴正向"，但非原文措辞）；顺序与分支条件 ✅ |

### 5.6 §五 宏体曲面（3-18 ~ 3-22）—— ✅ 结构规则与 10 种宏体小面编号**逐项一致**

| 教程断言 | 原文 | 判定 |
|---|---|---|
| 宏体内部对小面取负侧、外部正侧（:188） | 3-18 `The space inside a body has a negative sense … The space outside a body has a positive sense.` | ✅ 逐字 |
| 自动分解为方程曲面、小面编号＝用户号 + 小数点 + 1,2,…（:189） | 3-18 `decomposed internally into surface equations and the facets are assigned individual numbers according to a predetermined sequence. The assigned numbers are the number selected by the user followed by a decimal point and 1, 2, …` | ✅ 逐字 |
| 小面可用于记数/分段/其他栅元定义/SDEF 源；**不能**用于 SSR/SSW、曲面标记卡、PTRAC、MCTAL（:190-191） | 3-18 `The facets can be used for tallying, tally segmentation, other cell deﬁnitions, SDEF sources, etc. They cannot be used on the SSR/SSW cards, the surface ﬂagging card, PTRAC, or MCTAL ﬁles.` | ✅ 逐字 |
| BOX/RPP/SPH/RCC/RHP/REC/TRC/ELL/WED/ARB 的**参数顺序**（:196-395） | 3-18~3-21 逐条（含 `REC` 10 项缩略＝次半径、`ARB` 8 组坐标＋6 个四位面号共 30 项、`ELL` Rm 正负两种语义、`WED` 顶点＋三向量） | ✅ |
| **小面编号表**（:206-411 与附录 :554-563） | 3-21/3-22 逐条：BOX `1 末端A1 / 2 起点A1 / 3 末端A2 / 4 起点A2 / 5 末端A3 / 6 起点A3`；RPP `Xmax,Xmin,Ymax,Ymin,Zmax,Zmin`；SPH `Treated as a regular surface so no facet`；RCC `柱面 / 末端H / 起点H`；RHP `r面, r对面, s面, s对面, t面, t对面, 顶面, 底面`；REC `椭圆柱面 / 末端H / 起点H`；TRC `锥面 / 末端H / 起点H`；ELL `Treated as regular surface`；WED `斜面 / V2&V3面 / V1&V3面 / 顶三角 / 底三角（含顶点）`；ARB `N1…N6` | ✅ **逐项逐字一致（含 SPH/ELL 无小面、WED 的"含顶点"括注）** |
| RHP 轴向无限时 facet 7/8 不存在（:281） | 3-21 `RHP can be inﬁnite in the axial dimension in which case facets 7 and 8 do not exist.` | ✅ 逐字 |
| BOX/RPP 可在某维无限（:222） | 3-21 `BOX and RPP can be inﬁnite in a dimension, in which case those two facets are skipped and the numbers of the remaining facets are decreased by two.` | ✅ |

### 5.7 §六 TRn 坐标变换卡（3-30 ~ 3-32）—— ✅ 全部正确

| 教程断言 | 原文 | 判定 |
|---|---|---|
| 格式 `TRn O1 O2 O3 B1…B9 M`（:422-423） | 3-30 Form 逐字 | ✅ |
| `n`：1 ≤ n ≤ 999（:428） | 3-30 `number of the transformation: 1 ≤ n ≤ 999` | ✅ 逐字 |
| `*TRn`＝Bi 为角度（度，0~180）（:435） | 3-30 `∗TRn means that the Bi are angles in degrees`；3-31 `the angle itself, in degrees in the range from 0 to 180` | ✅ 逐字 |
| `M=1`（默认）位移矢量＝辅助系原点在主系中的位置；`M=−1`＝主系原点在辅助系中的位置（:431-432） | 3-30 逐字 | ✅ 逐字 |
| 默认 `TRn 0 0 0 1 0 0 0 1 0 0 0 1 1`（:437） | 3-30 `Default: TRn 0 0 0 1 0 0 0 1 0 0 0 1 1` | ✅ 逐字 |
| 单问题最多 999 个变换（:439） | 3-30 `The maximum number of transformations in a single problem is 999.` | ✅ 逐字 |
| **B 矩阵轴对应表**（B1↔x,x'、B2↔y,x'、B3↔z,x'、B4↔x,y'… B9↔z,z'）（:445-457） | 3-31 `Element B1 B2 B3 B4 B5 B6 B7 B8 B9 / Axes x,x' y,x' z,x' x,y' y,y' z,y' x,z' y,z' z,z'` | ✅ **逐项一致** |
| "B 的含义不随 M 改变"（隐含）／教程未写 | 3-31 `The meanings of the Bi do not depend on M.` | ✅（可补充项） |
| B 矩阵 5 种输入模式：9 / 6 / 5（公共分量 <1，按欧拉角补全）/ 3 / 0（单位矩阵）（:465-469） | 3-31 五条逐字 | ✅ **逐字** |
| 清洗微小非正交并归一化；非正交超过约 0.001 rad 警告（:472） | 3-31 `MCNP cleans up any small nonorthogonality and normalizes the matrix … A warning message is issued if the nonorthogonality is more than about 0.001 radian.` | ✅ 逐字 |
| 示例 2：`17 4 PX 5` + `TR4 7 .9 1.3 0 −1 0 0 0 1 −1 0 0` → 等效 `17 P 0 −1 0 4.1`，不会得到 `PY 4.1`（感度反） | 3-31/3-32 逐字（`MCNP will produce coefﬁcients … as if surface 17 had been entered as 17 P 0 −1 0 4.1. It will not produce 17 PY 4.1. The surface represented by PY … has the wrong sense.`） | ✅ 逐字 |
| 锥面变换限制：单叶锥只能从一个坐标轴转到另一个（90° 倍数）、位移任意；双叶锥可任意变换；双叶锥配模糊面可模拟单叶，模糊面须用同一变换号（:504-506） | 3-30/3-31 逐字（含 `multiples of 90°`、`The ambiguity surface must have the same transformation number as the cone of two sheets.`） | ✅ **逐字** |
| 周期边界曲面不能使用坐标变换（:510） | 3-31 `Periodic boundary surfaces cannot have surface transformations.` | ✅ 逐字 |
| 更多示例见第 4 章 4-16（:511） | 3-31 `See Chapter 4 page 4–16` | ✅ |

### 5.8 §七 示例汇总 —— ❌ 1 处

| 教程示例 | 原文 | 判定 |
|---|---|---|
| 例 1 `j PY 3` → y=3，y>3 为正侧（:519-521） | 3-14 例 1 逐字 | ✅ |
| 例 2 `j K/Y 0 0 2 .25 1` → 顶点 (0,0,2)、轴平行 Y、t=0.5、正叶片（:525-527） | 3-14 例 2 逐字 | ✅（连中文解释都与原文 `only the positive (right hand) sheet` 对应） |
| 例 3 `j GQ 1 .25 .75 0 -.866 0 -12 -2 3.464 39` → 半径 1 的柱面，轴在 x=6 平面内、偏离 X 轴 2 cm、绕 X 轴从 Y 向 Z 转 30°（:531-533） | 3-14 例 3 逐字（系数与描述均一致） | ✅ 逐字 |
| **例 3 的"更简单方式"**：`1 7 CX 1` + `*TR7 10 0 0  90 90 90  0 0 0  0 0 0`（:537-540） | 3-14 原文给的是 `j 7 CX 1` + **`*TR7 6 1 –1.732 0 30 60`**（6 值＝模式 #2） | ❌ **改写错误**：教程自造的 9 个角度值使第一向量 (cos90°,cos90°,cos90°)=(0,0,0)，**必然退化**，既不等于原文示例也不是合法旋转矩阵。**复核补充**：原文该示例本身也不干净（`*TRn` 下这 6 个角度值组合非正交，要靠 MCNP 清洗），基线不可作范例——但教程版本仍是确定的错 |
| 例 4 `j P 0 0 0 1 0 0 0 1 0` → 过原点、(1,0,0)、(0,1,0) 的平面（:544-546） | 原文 §III.C 无此示例（教程自建）；按 3-17 规则，三点定面且原点为负侧 ⇒ 描述自洽 | ✅（自建示例，语义正确） |

### 5.9 修正建议（待批准，尚未执行）
1. 改手册名：:1 标题、:3 来源行、:567 结语（C810.pdf ＝ **MCNP5 卷 I+II**）。
2. **修 §七例 3 的替代写法**（:537-540）：改为原文 `j 7 CX 1` + `*TR7 6 1 -1.732 0 30 60`（6 值模式），或删掉该"更简单方式"。
3. §四感度第 2~4 条把 `ε` 改回原文的 **∞**（`(0,0,∞)`、`(0,∞,0)`、`(∞,0,0)`），避免读者以为是"很小的数"。
4. 可选补充：`The meanings of the Bi do not depend on M.`（3-31）；宏体小面的"master 栅元"感度继承规则（3-18）。

### 5.10 结论
本篇是 6 篇里**核验质量最高的一篇**：Table 3.1 方程、锥面双叶/单叶语义（并**精确**标注了出处 §2.C.1）、环面方程与退化条件、点定义曲面的 1/2/3 点规则与原文示例（含"错误示例"数值）、宏体 10 种小面编号、TRn 的 B 矩阵轴对应表与 5 种输入模式、锥面变换限制——**全部可与原文逐字对上**；文件自记的"环面 A/C 抄反"历史修正经本轮独立复核确认已正确。缺陷只有 3 处：手册名误标（3 处）、§七例 3 自造的退化 TR7、以及 ε/∞ 措辞。

---

## 6. `app/docs/源分布卡说明.md`（自标来源：C810 第 3-53 ~ 3-79 页）

### 6.1 概览

| 维度 | 结果 |
|---|---|
| 手册名 | ⚠️ 头部 `:3` 未误标（写 "C810.pdf"），但 `:128` 段前说明与 `:557` 结语写「MCNP6 手册」（2 处） |
| 技术断言 | **✅ 几乎全部逐字可对**（质量与 §5 同级）；⚠️ 2 处措辞/精度；❌ 0 处技术错 |
| 第二证据源交叉验证 | ✅ 与项目自有锚点产物 `docs/authority/c810-sdef.md`（22 锚点、机检）指向同一批原文，本次页级抽取与之**无冲突** |
| 页码引用 | ✅ 3-53 ~ 3-79 覆盖正确；正文内逐条引用（3-54、3-55、3-56、3-63、3-64、3-65、3-66、3-67、3-70、3-74、3-77、3-78、3-79）**逐条命中** |

### 6.2 §一 四种源模式与源变量清单 —— ✅

| 教程断言 | 原文 | 判定 |
|---|---|---|
| 四种源模式：SDEF／SSW+SSR／KCODE+KSRC/HSRC／SOURCE 子程序（:10-15） | 3-53 起 `Source Specification`；3-79 `If SDEF, SSR, or KCODE cards are not present in the INP ﬁle, a user supplied source is assumed and is implemented by calling subroutine SOURCE` | ✅ |
| 源须定义的变量：ERG、TME、UUU/VVV/WWW、XXX/YYY/ZZZ、IPT、WGT、ICL、JSU（:17） | 3-54 逐条：`ERG the energy of the particle (MeV)`、`TME the time…`、`UUU, VVV, WWW the direction…`、`XXX, YYY, ZZZ the position…`、`IPT the type of the particle`、`WGT the statistical weight`、`ICL the cell where the particle started`、`JSU the surface where the particle started, or zero if…` | ✅ **逐字对应** |

### 6.3 §二 通用源 SDEF —— ✅

| 教程断言 | 原文 | 判定 |
|---|---|---|
| 空卡默认：14 MeV 各向同性点源、(0,0,0)、时间 0、权重 1（:29） | 3-55 `The default is a 14-MeV isotropic point source at position 0,0,0 at time 0 with weight 1 (all defaults).` | ✅ 逐字 |
| 三种赋值方式：直接给值／`D` 前缀分布号／`F`＋变量名＋分布号（:31-36） | 3-55 `1. explicit value, 2. a distribution number prefixed by a D, or 3. the name of another variable prefixed by an F, followed by a distribution number` | ✅ 逐字 |
| Table 3.3 变量表 19 行（含 **EXT 默认 0**、PAR「由 MODE 卡」、ARA「平面源面积」）（:40-59） | 3-55/3-56 Table 3.3（§4.6 已逐项核过） | ✅ **本篇 EXT 默认值写对（＝0）**，与 §4 那篇写"无"形成对照 |
| 曲面源 `AXS+EXT` 组合暗示球面（:106） | 3-68 `The presence of AXS and EXT implies that surface m is a sphere because AXS and EXT are not otherwise used together for sources on a surface` | ✅ 逐字 |
| 球/柱体源的 RAD 幂律默认：球 a=2、柱（定义了 AXS）a=1（:79、:86） | 3-66 `For DIR, a = 1. For RAD, a = 2, unless AXS is deﬁned or JSU ≠ 0, in which case a = 1. For EXT, a = 0.` | ✅ |
| `SP1 -3`＝Watt、`-2`＝Maxwell、`-4`＝高斯聚变谱（:112-114） | Table 3.4（3-65）函数号定义 | ✅ |

### 6.4 §三 SIn / SPn / SBn / DSn / SCn 与 Table 3.4 —— ✅ 逐条逐字

| 教程断言 | 原文 | 判定 |
|---|---|---|
| SIn option：省略/`H`＝直方图分箱边界（仅标量、默认）、`L`＝离散值、`A`＝概率密度定义点、`S`＝分布号（:135-145） | 3-62/3-63 逐字（`omitted or H—bin boundaries for a histogram distribution, for scalar variables only. This is the default.` …） | ✅ 逐字 |
| SPn option：省略（H/L 时同 `D`；A 时为概率密度值）、`D`、`C`、`V`（仅 CEL，概率∝栅元体积，给了 Pi 则再乘 Pi）（:158-166） | 3-63 逐字（含 `V−for cell distributions only. Probability is proportional to cell volume (times Pi if the Pi are present).`） | ✅ 逐字 |
| SP 判定规则：首项为正/非数值＝常规表；首项为负＝内置函数（:174-175） | 3-63 `The ﬁrst form of the SP card, where the ﬁrst entry is positive or nonnumeric, indicates that it and its SI card deﬁne a probability distribution function.` | ✅ 逐字 |
| H 语义：SI 单调递增、**SP 首项必须为 0**、先选箱再箱内均匀（:180-182） | 3-63 `must be monotonically increasing. The ﬁrst numerical entry on the SP card must be zero … sampling uniformly within the chosen bin.` | ✅ 逐字 |
| L：不需要单调递增（:195） | 3-64（离散值、无需单调） | ✅ |
| S：可嵌套、约 20 层、分布号可带/省略 `D`、**分布号 0＝用默认值**、一个分布不能用于一个以上源变量（:199-203） | 3-64 逐字 | ✅ |
| V：仅 CEL；若算不出体积且未给 `VOL` → **FATAL**（:207-208） | 3-64 逐字 | ✅ |
| SBn：`f` 只允许 −21/−31；自动调整权重补偿偏倚；SP 第一种形态的规则同样适用（:219-222） | 3-63/3-64 逐字 | ✅ |
| 内置函数：only for Table 3.3 variables（ERG/DIR/RAD/EXT/TME/X/Y/Z）；SP 任意、SB 仅 −21/−31；SB 用了某函数则 SP 只能同函数；SI/SP 常规表＋SB 函数不允许；偏倚只改分箱概率、每箱近似 n 个等概率组且 n×箱数 ≤ 300；除 −21/−31 外截断会调权重（:227-235） | 3-66 逐字（含 `the product of n and the number of bins is as large as possible but not over 300`、`Unless the function is −21 or −31, the weight of the source particle is adjusted`） | ✅ 逐字 |
| 特殊默认 5 条（SB f 无 SP f／RAD·EXT 只有 SI／DIR·EXT 只有 SP −21/−31／RAD 的 SI x 按 SI 0 x／EXT 的 SI x 按 SI −x x）（:238-243） | 3-66 五条逐字 | ✅ **5/5 逐字** |
| Table 3.4 九个函数：−2 Maxwell（默认 a=1.2895）、−3 Watt（0.965/2.29）、−4 高斯聚变（a=−0.01、b=−1；a<0 按温度、b=−1 D–T、b=−2 D–D；**a 不是 FWHM，FWHM = a(ln2)^(1/2)**）、−5 蒸发（1.2895）、−6 Muir（含 a=(b+a₄)^(1/2)−b^(1/2)）、−7 Spare（SPROB/SPEC/SMPSRC/CALCPS）、−21 幂律（默认随变量：DIR=1、RAD=2 除非 AXS 或 JSU≠0 则 1、EXT=0）、−31 指数（a=0）、−41 高斯（1.6651092、a 为 FWHM、a=(8ln2)^(1/2)σ）（:249-257） | 3-65/3-66 Table 3.4 逐字 | ✅ **逐字**。⚠️ 附注：`FWHM = a(ln2)^(1/2)` 是**手册原话**（3-65），与同表 −41 的 `1.6651092` 关系式**自相矛盾**——教程忠实照抄，不算教程的错，建议加一句"手册此处表述与 −41 不一致" |
| DSn option：空白或 `H`（仅标量）、`L`、`S`、`T`（自变量须离散标量）、`Q`（自变量须标量）；H 时 n+1 项、首项不必为 0；插值因子 f 恒存在；T 未命中取默认；Q 从 V1 比较、Vk ≥ 任何可能值、Si=0 取默认、**Q 是自变量分布为内置函数时唯一可用形态**（:263-300） | 3-66/3-67 逐字 | ✅ **逐字** |
| SCn：注释作为分布 n 表头打印在源分布表与源分布频率表；**`&` 续行符算注释的一部分而非续行命令**（:310-311） | 3-67/3-68 `The comment is printed as part of the header of distribution n in the source distribution table and in the source distribution frequency table. The & continuation symbol is considered as part of the comment, not as a continuation command.` | ✅ 逐字 |

### 6.5 §四 面源 SSW / SSR —— ✅

| 教程断言 | 原文 | 判定 |
|---|---|---|
| SSW 形态 `SSW S1 S2 (C1…Ck) S3 keyword=values`；`=` 可省（:325） | 3-70 `Form: SSW S1 S2 (C1 … Ck) S3 Sn keyword=values / The = signs are optional.` | ✅ 逐字 |
| Si＝记录的曲面号，**宏体曲面不允许**（:330） | 3-70 `… for which particle-crossing information is to be written to the surface source ﬁle WSSA. Macrobody surfaces are not allowed.` | ✅ 逐字 |
| Ci：正＝进入该栅元、负＝离开该栅元（:331） | 3-70 `A positive entry denotes an other-side cell. A negative entry speciﬁes a just-left cell.` | ✅ |
| SYM：0＝无对称（默认）、1＝球对称（只能一个球面）、2＝双向记录；否则只记录"出正侧/入负侧"（:332） | 3-70 逐字 | ✅ 逐字 |
| PTY：N/P/E；缺省＝记录全部（:333） | 3-70/3-71 逐字 | ✅ |
| 示例 `SSW 4 -7 19 (45 -46) 16 -83 (49)` 及其中文解释（:338-340） | 3-71 Example 1 逐字（含"entering cell 45 or leaving cell 46"…） | ✅ **逐字** |
| 面源文件默认名 WSSA；异常终止为 WXXA、须与 RUNTPE 一起保存（:391） | 3-72 `During execution, surface source information is written to the scratch ﬁle WXXA. Upon normal completion, WXXA becomes WSSA. If the run terminates abnormally, the WXXA ﬁle will appear instead of WSSA and must be saved along with the RUNTPE ﬁle.` | ✅ 逐字 |
| SSR 关键字 OLD/CEL/NEW/PTY/COL/WGT/TR n/TR Dn/PSC 的语义（:350-357） | 3-72/3-73/3-74 逐字；`COL：m=−1 仅无碰撞直接粒子、m=1 仅碰撞过、m=0 不论碰撞` 与原文一字不差 | ✅ 逐字 |
| 球对称专用四关键字 AXS / EXT / POA / BCW（:359） | 3-73 `The following four keywords are used only with spherically symmetric surface sources, that is, sources generated with SYM=1 on the SSW card.` | ✅ 逐字 |
| NPS 改变会重新分配权重：变小→按比例拒绝轨迹；变大→复制轨迹、各带不同随机数种子、权重减半（例 100→200）（:389） | 3-74/3-75 逐字（`if the SSW calculation used an NPS of 100 and the SSR calculation uses an NPS of 200, then every track is duplicated, each with a different random number seed and each with half the original weight.`） | ✅ **逐字** |
| 记录方向只有单向（除 SYM=2）（:388） | 3-71 `Otherwise, only particles going out of a positive surface and into a negative surface are recorded.` | ✅ |
| 探测器/DXTRAN 需 PSC 近似；靠近源可能 WRONG（:390） | 3-75 `Warning: … If the point detector or DXTRAN sphere is close to the source sphere and the approximation is poor, the answers will be WRONG.`；`A PSC entry of zero specifies an isotropic angular distribution` | ✅ 逐字 |

### 6.6 §五 临界源 KCODE / KSRC / HSRC —— ✅（1 处措辞）

| 教程断言 | 原文 | 判定 |
|---|---|---|
| `KCODE NSRCK RKK IKZ KCT MSRK KNRM MRKP KC8`（8 项）（:400） | 3-77 `NSRCK RKK IKZ KCT MSRK KNRM MRKP KC8` | ✅ 逐字 |
| 默认值：NSRCK=1000、RKK=1.0、IKZ=30、KCT=IKZ+100、MSRK=4500 或 2×NSRCK、KNRM=0、MRKP=6500、KC8=1（:405-412） | 3-77 `Defaults: NSRCK=1000; RKK=1.0; IKZ=30; KCT=IKZ+100; MSRK=4500 or 2*NSRCK; KNRM=0; MRKP=6500; KC8=1` | ✅ **8/8 逐字**（对照 §3 那篇的 "~10000/50/1000" 可见本篇才是对的） |
| KC8：0＝全部周期／1＝仅活跃周期（:412） | 3-77 `KC8=0 causes tallies and summary table information to be for both active and inactive cycles and should not be used.` | ✅ |
| KSRC：点须远离栅元边界；至少一个点在含裂变材料栅元；初始能量从硬编码 Watt 谱取样（a=0.965, b=2.29）；缺省用 SRCTP 或 SDEF 提供初始源（:419-423） | 3-78 逐字（`At least one point must be in a cell containing ﬁssile material and points must be away from cell boundaries.`；`sampled from a Watt ﬁssion spectrum hardwired into MCNP, with a = 0.965 MeV and b = 2.29 MeV−1`） | ⚠️ 一处加强：教程"**每个可裂变区域至少一个点**"→原文是 `Usually one point in each ﬁssile region is **adequate**`（"至少一个"是**全局**要求，非每个区域）；其余 ✅ |
| HSRC 形态与用法：3D 网格评估裂变源收敛；每方向 5~10 格为宜；缺省自动确定且**最少 4×4×4**（:428-432） | 3-79 `users should use a small number of grid boxes (e.g., 5-10 in each of the XYZ directions)`；`The minimum number of mesh cells for the automatic mesh is 4x4x4.` | ✅ 逐字 |

### 6.7 §六 SOURCE / SRCDX 子程序 —— ✅

| 教程断言 | 原文 | 判定 |
|---|---|---|
| SDEF/SSR/KCODE 均缺省时调用用户 `SOURCE`（:445） | 3-79 逐字 | ✅ |
| UUU/VVV/WWW 默认已设为各向同性，各向同性无需指定（:461） | 3-79 `Prior to calling subroutine SOURCE, isotropic direction cosines u,v,w (UUU, VVV, WWW) are calculated and need not be speciﬁed if you want an isotropic distribution.` | ✅ 逐字 |
| 随机数用 `RANG()` 生成 0~1（:462） | 3-79 `A random number generator RANG( ) is available … for generating random numbers between 0 and 1.` | ✅ 逐字 |
| 数据可用 IDUM/RDUM 传入，各最多 50 项（:463） | 3-79 `Up to 50 numerical entries can be entered on each of the IDUM and RDUM cards` | ✅ 逐字 |
| 探测器/DXTRAN＋各向异性源需额外写 `SRCDX`（:464） | 3-79 逐字 | ✅ |
| 备用数组 `SPARE(M)`（M=1~3），MCNP 不重置（:465） | 3-79 `SPARE(M), M=1,MSPARE, where MSPARE=3 … MCNP does not reset them.` | ✅ 逐字 |

### 6.8 §七 示例汇总 —— ✅（1 处精度，1 处手册自身笔误）

| 教程示例 | 原文 | 判定 |
|---|---|---|
| 示例1（`SDEF ERG=D1 POS=x y z WGT=w` + `SI1 H …` + `SP1 D 0 …` + `SB1 D 0 …`，并注"H 分布时 SP/SB 首项须为 0 占位"）（:473-478） | 3-68 Example 1 逐字；3-63 `The ﬁrst numerical entry on the SP card must be zero` | ✅ **逐字**（占位项说法有原文依据） |
| 示例2（`SDEF SUR=m AXS=i j k EXT=D6` + `SB6 -31 1.5`）（:482-484） | 3-68 Example 2 逐字 | ✅ 逐字 |
| 示例3（`SDEF SUR=m NRM=-1 DIR=D1 WGT=w` + `SB1 -21 2`）（:488-490） | 3-68 Example 3 逐字 | ✅ 逐字 |
| 示例6（`SDEF POS=D1 ERG=FPOS D2` + `SI1 L 5 3.3 6 75 3.3 6` + `SP1 .3 .7` + `DS2 S 3 4`）（:507-511） | 3-69 Example 6（两位置、概率 .3/.7、DS2 指向不同能谱） | ✅ |
| 示例7（`SDEF DIR=1 VEC=0 0 1 X=D1 Y=0 Z=-2 TR=1` + `SI1 0.0 0.5` + `SP1 0.0 1.0` + **`TR77`**）（:515-518） | 3-69 Example 7 逐字——**原文自身就是 `TR = 1` 配 `TR77` 卡**（手册笔误） | ✅ 教程忠实照录；建议加注"原文此处卡号不一致" |
| 示例8（高斯束＋CCC＋三束变换，SP1 −41 .470964 0、SP2 −41 .235482 0、SI3 L 11 22 33、SP3/SB3、TR11/TR22/TR33）（:523-531） | 3-70 Example 8 逐字（含 `SP1 −41 .470964 0`、`SP2 −41 .235482 0`、`TR33 0 -2 0 .707107 0 .707107 .707107 0 −.707107 0 1 0`） | ⚠️ 教程把 `.707107` 截成 `.707`（精度）；其余逐字 |
| 示例9（面源两步法 MODE/SSW/NPS → MODE/SSR/NPS）（:536-545） | 3-74 的 Run 1/Run 2 示例结构一致 | ✅ |
| 示例10（`KCODE 10000 1.0 50 150` + KSRC + HSRC）（:549-552） | 与 3-77/3-78/3-79 语法一致 | ✅ |

### 6.9 修正建议（待批准，尚未执行）
1. `:128`、`:557` 的「MCNP6 手册」→ MCNP5（同 §2/§3/§5）。
2. KSRC 处改为原文口径："须至少有一个点位于含裂变材料的栅元中；通常每个裂变区给一个点就够"。
3. 示例8 的 `.707` → `.707107`；示例7、示例1 各加一句原文备注（`TR=1` 与 `TR77` 不一致；`SP/SB` 首项 0 是 H 分布的占位要求）。
4. Table 3.4 的 −4 高斯谱加注："手册此处给出 `FWHM = a(ln2)^{1/2}`，与同表 −41 的 `a=(8ln2)^{1/2}σ` 表述不一致，属手册自身问题"。

### 6.10 结论
本篇与 §5 并列为**质量最高的两篇**：Table 3.3/3.4、SIn/SPn/SBn/DSn/SCn 的全部 option 语义、内置函数 9 条、5 条特殊默认、SSW/SSR 全部关键字与默认值、KCODE 8 个默认值、HSRC 的 4×4×4、SOURCE/SRCDX 的 SPARE/RANG/IDUM/RDUM——**均与原文逐字对应**；项目自有的锚点产物 `docs/authority/c810-sdef.md` 与本轮页级抽取**无冲突**。缺陷仅 2 处措辞/精度（KSRC"每个区域至少一个点"、`.707` 截断）＋2 处手册名。

---

## 7. 汇总裁决（6/6 篇）

### 7.1 逐篇结论

| # | 教程 | 页码类断言 | 技术断言 | 会致用户写错卡的硬错误 |
|---|---|---|---|---|
| 1 | `PRINT卡说明.md` | 页码引用 ✅ | 18 条：✅ 15 / ⚠️ 1 / ❌ 1（示例2 丢参数 `170`） | **`常用表号` 31 行错 24 行**（类型列另错 10 处、漏 32/62/72 三行）；与正文自相矛盾（126/128） |
| 2 | `MCNP6_FN卡结构参考.md` | **22/22 ✅** | 36 条：✅ 34 / ⚠️ 2 / ❌ 0 | 无；仅手册名误标 3 处 |
| 3 | `MCNP6_输出卡结构参考.md` | **9/9 ✅** | 41 条：✅ 37 / ⚠️ 3 / ❌ 1（`entered`→"穿出"） | **`常用打印表编号` 31 行错 28 行** |
| 4 | `C810_卡片格式详细.md` | 附录 52 行：**49 ✅ / 1 ❌（PRINT 3-144）/ 2 ⚠️** | 约 40 条：❌ 4 类 | **`TXY/TXZ/TYZ` 虚构（C810 全文 0 命中）**、**`X/Y/Z` 曲面语义写反**、**材料卡 ZAID 字母表错**、**`FTn` 关键字表错**（另：SDEF `EXT` 默认值、`MTn`→`MTm`、KCODE 默认值混淆） |
| 5 | `MCNP6_曲面卡格式参考.md` | 全部引用 ✅（含 §2.C.1） | 约 35 条：✅ 33 / ⚠️ 1 / ❌ 1（自造退化 `*TR7`） | 无（仅该 1 处示例） |
| 6 | `源分布卡说明.md` | 全部引用 ✅ | 约 45 条：✅ 43 / ⚠️ 2 / ❌ 0 | 无 |

### 7.2 跨篇共性（4 条）

1. **手册名误标 11 处 / 4 篇**：`MCNP6_FN`(3)、`MCNP6_输出卡`(3)、`MCNP6_曲面卡`(3)、`源分布卡`(2) 把 C810.pdf 称作「MCNP6 手册」。**事实**：C810.pdf = MCNP5 卷 I+II（页眉 `EXPORT CONTROLLED INFORMATION 10/3/05`，卡格式权威章＝卷 II Ch.3）——这 11 处是**唯一 100% 确定的系统性错误**。仅 `C810_卡片格式详细.md`（"MCNP5 Vol.II Ch.3"）与 `PRINT卡说明.md` 未误标。
2. **两张"PRINT 表号表"同源同错、错法不同**：§1 错 24/31、§3 错 28/31，且 80/85/86/90 等行的错法两篇互不一致 ⇒ 不是复制同一份错误，而是**两次各自凭印象生成**——正是 `tools/c810_extract.py` 文件头记录的"凭记忆转述手册"事故同款。
3. **页码表整体可信，内容表不可信**：页码类断言（FN 22/22、输出 9/9、曲面全对、C810 49/52）几乎全对；而"编号→内容"映射类表格（两张表号表）错得最多。**可复用规律：教程的页码可信，映射表必须逐格复核。**
4. **"加料/加强"是另一类高发缺陷**：`R0 在真空中非法（FATAL error）`（§2，原文无 FATAL）、`丢失超 10 个通常是几何错误`（§3，原文"鲜有正当理由"）、`每个可裂变区域至少一个点`（§6，原文"通常一个就够"）、`漏 (but not always)`（§2）。**方向一致但强度被放大**，属"读起来更确定"的隐形失真。

### 7.3 修正优先级（待你批准后执行；本轮未改任何教程原文）

| 级别 | 内容 | 涉及文件 |
|---|---|---|
| **P0** | 统一替换两张 PRINT 表号表为 §1.3 的原文映射（含类型列、补 32/62/72），两处用**同一张**表 | `PRINT卡说明.md`、`MCNP6_输出卡结构参考.md` |
| **P0** | 删 `TXY/TXZ/TYZ`；改正 `X/Y/Z` 语义；重写 ZAID 字母表；重写 `FTn` 关键字表 | `C810_卡片格式详细.md` |
| **P0** | 修正 PTRAC 示例译法（entered＝进入） | `MCNP6_输出卡结构参考.md` |
| **P1** | 11 处「MCNP6 手册」→ MCNP5 | 4 篇 |
| **P1** | SDEF `EXT` 默认 0；`SPn` 补 `C`/`V`/`f a b`；`MTn`→`MTm`；KCODE 默认值与常用值分开写；附录 `PRINT` 页码 3-144→3-149 | `C810_卡片格式详细.md` |
| **P1** | 示例2 补回 `170`；拆开"始终会打印"；删无依据的 `FATAL error`；补 `(but not always)`；`MEPH` 默认写"写出全部事件" | `PRINT卡说明.md`、`MCNP6_FN卡结构参考.md`、`MCNP6_输出卡结构参考.md` |
| **P1** | §七例 3 的 `*TR7` 改回原文 6 值模式；`ε` → `∞` | `MCNP6_曲面卡格式参考.md` |
| **P2** | 格式规则 4 处（注释卡"1−5 列"、续行主规则、`nILOG`/`xM`、数据卡终止符）；`:337` 那批"待核"补录条目升级为已核；KSRC 措辞；示例8 数值精度 | `C810_卡片格式详细.md`、`源分布卡说明.md` |
| **P2（结构）** | `app/docs` ↔ `gui/public/docs` 双份（FMESH 内容已漂移、源分布卡仅 CRLF 差异）：定单一真源＋同步校验 | 目录级 |

### 7.4 完成度声明（对照本轮完成定义）

| 检查项 | 结果 |
|---|---|
| 6 篇每条断言都有页级证据（页号＋原文摘录） | ✅ 本报告 §1~§6 逐条列出 |
| 页码引用抽检命中 | ✅ 6 篇自标页区间全部命中；单点误差仅 C810 篇附录 `PRINT 3-144` |
| C810 未收录项显式标注 | ✅ 例：`TXY/TXZ/TYZ`（全文 0 命中）、`FTn` 的 `TAL/PHL/CAP/FFT/GEO`（不在 C810 的 9 个 ID 内） |
| 读取方式可复现 | ✅ §0 给出 PYTHONPATH＋PyMuPDF 调用；全库文本 `__c810_full.txt`（2.58 M 字符）可复查 |
| 不改教程原文、不建锚点回归测试 | ✅ 全程只读；报告为本轮唯一新增产物 |
| 修正 | ⏸ **待你过目后执行**（本轮按约定未动） |

### 7.5 一句话总结
6 篇里**两篇（曲面卡、源分布卡）质量很高、几乎逐字可靠**，两篇（FN、输出卡）"页码全对、正文扎实、附表烂掉"，一篇（PRINT）"正文对、表号表错 24/31"，一篇（C810 卡片格式详细）虽信息量最大却含 **4 类虚构/错配内容**；最确定的系统性错误是 **11 处"C810＝MCNP6 手册"**，最危险的是**两张 PRINT 表号表**与 **`TXY/TXZ/TYZ`、`X/Y/Z`、ZAID、`FTn`** 这四处——它们会让用户写出与手册相悖的输入卡。

---

## 8. 复核记录（对抗性自检）

> 用户质询"复核一下是否是真错误"后，对**最要害的判定**用**新方法＋新证据源**重核一遍。结论：**P0 级判定全部成立**，另有 1 条细化、1 条软化、1 条补充注记。

### 8.1 新增的决定性证据

| # | 新证据 | 直接支持/推翻什么 |
|---|---|---|
| E1 | **手册扉页（PDF 78）**：`MCNP — A General Monte Carlo N-Particle Transport Code, **Version 5** / Volume I: Overview and Theory / **LA-UR-03-1987**`；PDF 80 FOREWORD：本手册对应 **MCNP Version 5**，分三卷，Vol II = *MCNP User's Guide*（Ch.1/3/4/5） | **坐实**"11 处『MCNP6 手册』是真错"——此前只有 D-11 与页眉佐证，现有手册自身扉页 |
| E2 | **Table 3.1（3-13）按坐标重抽 mnemonics 列**（x≈116-131）：P, PX, PY, PZ, SO, S, SX, SY, SZ, C/X, C/Y, C/Z, CX, CY, CZ, K/X, K/Y, K/Z, KX, KY, KZ, SQ, GQ, TX, TY, TZ, **XYZP**；末行 `XYZP：Surfaces defined by points，See pages 3–15 and 3–17` | **坐实** ① `TXY/TXZ/TYZ` 不存在；② `X/Y/Z` 是"点定义曲面"而非"坐标平面" |
| E3 | **Table 3.7（3-150/3-151）按坐标重抽**：每行 number/type/description **同 y**（例 `y=541.5 → 60｜basic｜Cell importances`），配对零歧义 | 再次排除"线性化错位"这一唯一能翻案的可能 |
| E4 | **手册第 5 章示例输出自带表号标签**（本 PDF 内约 25 处）：`source…print table 10`、`tally…30`、`material composition…40`、`cell volumes…50`、`cells…60`、`surfaces…70`、`cell temperatures…72`、`cross-section tables…100`、`range table…85`、`electron secondary production…86`、`physical constants…98`、`starting mcrun…110`、`activity in each cell…126`、`weight balance…130`、`activity of each nuclide…140`、`tfc analysis…160`、`unnormed tally density…161`、`cumulative…162`、`keff by cycle…175`、`keff by batch…178`、`ww lower bounds from generator…190`、`ww cards from generator…200`、`initial source from ksrc card…90`、`Look at print tables 10, 110, and 170 to check the source`、`Universe Map/Lattice Activity Arrays for Table 128`、`cell particle activity in Print Table 126`、`tally fluctuation chart bin … Print Table 161` | **坐实**两张"表号表"的**每一处**错判：手册用自己的输出给自己做了对照答案，与 §1.3 的映射**逐条一致** |
| E5 | **FT 关键字全库检索**：`PHL`/`CAP`/`FFT` 仅出现在 **MCNP6.1 发布说明**段（"FT card, PHL option"、"FT CAP keyword"、"FT FFT keyword"，另有 `PDS`、`ROC`）；MCNP5 的 FTn 词条（3-116/3-117）只有 9 个 ID；`TAL` 仅作 Fortran 数组名、`GEO` 零命中 | **细化** FT 判定（见 8.2） |

### 8.2 复核后的调整（3 条）

| 调整 | 原判定 | 复核后判定 |
|---|---|---|
| FT 关键字表 | ❌「表错…疑为 MCNP6 之后的选项」 | ❌ 维持"表错"，但**性质更准确**：`PHL/CAP/FFT` 是**本 PDF 内 MCNP6.1 发布说明里真实存在的 FT 选项**（不是编造），错在"挂在 MCNP5 词条 3-116 名下且未标出处"；**`TAL`、`GEO` 全库无 FT 依据 → 仍属无来源**。修正建议相应改为："按 MCNP5 的 9 个 ID 重写；若确要收录 MCNP6 选项，须另注出处（发布说明段）" |
| FN 篇 `(FATAL error)` | ⚠️「无依据添加」 | ⚠️ 维持 ⚠️ 但**下调措辞**为"超出原文的解释性补注"（原文 "illegal" 在 MCNP 语境下确实通常即输入被拒；手册在确需标 FATAL 处会明写，故仍建议改回原文口径）——**不算确定错误** |
| 曲面卡篇 `*TR7` | ❌「改写错误」 | ❌ 维持。**补充注记**：原文该示例本身也不干净（`*TRn` 下 6 个角度值组合非正交，依赖 MCNP 清洗），但教程版本第一向量 (0,0,0) 属**必然退化**，仍是确定的错 |

### 8.3 复核未推翻的判定（清单）

`TXY/TXZ/TYZ` 虚构 ✅仍成立｜`X/Y/Z` 语义写反 ✅｜ZAID 字母表错（C/D/M/G/P/E/U/Y 逐字核实）✅｜两张 PRINT 表号表 24/31、28/31 错 ✅（E3+E4 双重坐实）｜PRINT 附录页码 3-144→3-149 ✅｜PTRAC `entered`→"穿出" ✅｜SDEF `EXT` 默认 0 ✅｜`MTn`→`MTm` ✅（手册与索引均作 MTm）｜KCODE 默认值 1000/1/30/130/0 ✅｜`SPn` 漏 `C`/`V` ✅｜11 处手册名误标 ✅（E1 坐实）｜`TMP 2.53×10⁻⁸`、`PHYS:N/P/E`、`CUT:N/P/E` 默认值逐项一致 ✅（无需改）。

### 8.4 复核方法的自评

- 本次刻意**不依赖第一轮的任何中间文件**（重抽坐标、另取证据源），并**优先寻找能"翻案"的反例**（例如：会不会是抽取错位？→ 用坐标与手册自带表号标签双重排除）。
- 唯一仍带主观性的是"⚠️ 类"判定（措辞超出原文的程度），已在 8.2 逐条下调到与其证据强度相称；**P0 级（会让用户写出错卡）的判定全部经得起复核**。
- 尚未做、也不宜在本轮做的一件事：把教程改正后**重新生成/运行**以验证修正效果——按你的节奏，那属于"过目后修正"阶段的工作。

---

## 9. 修正执行记录（P0 → P2，已执行）

> 依据 §7.3 清单执行。**每处改动只用 §1~§6 已核实的页级原文证据**，未引入任何未核实的新说法；
> 原文件中"照录手册自身笔误/自身不一致"的地方保留但加了知情注（示例 7 卡号、−4 的 FWHM 关系）。

### 9.1 逐文件改动

| 文件（行末风格） | 增/删 | 主要改动 | 级别 |
|---|---|---|---|
| `PRINT卡说明.md`（LF） | +56 / −35 | ① `常用表号` 整表替换为 Table 3.7 的 34 行正确映射（含类型列与 32/62/72）② 示例 2 改回 `PRINT 170 -70 -110` ③「始终会打印」拆为"前 5 项 + `basic` 关不掉 / `default` 可关 / `shorten` 只缩短"④ 来源行补手册身份与 Table 3.7 出处 ⑤ 补 `PRINT TABLE n` 形态说明 | P0/P1 |
| `MCNP6_输出卡结构参考.md`（LF） | +51 / −35 | ① `常用打印表编号` 换成与 PRINT 篇**同一张**正确表 ② PTRAC 例释"穿出"→"**进入**（entered）" ③ LOST 措辞改回原文 `rarely justifiable` 口径 ④ MEPH 默认改"写出全部事件" ⑤ DBCN 的 X15/X16 默认值改为"正文未直述"并补两条原文规则（continue-run 限制、负值语义）⑥ 标题/来源/结语手册名 | P0/P1 |
| `MCNP6_FN卡结构参考.md`（LF） | +8 / −6 | ① 标题/来源/结语手册名（3 处）② 删 `（FATAL error）`，改原文 `A negative entry is illegal in a void.` ③ `<10%` 补 `（但不总是）` | P1 |
| `C810_卡片格式详细.md`（CRLF） | +86 / −49 | ① 删 `TXY/TXZ/TYZ` 虚构曲面并指向 `GQ`/`SQ`/`REC` ② `X/Y/Z` 重写为"点定义轴对称曲面"（1/2/3 点对规则、单叶锥、SQ 感度、正反例）③ ZAID 字母表重写（`c/d/m/g/p/e/u/y`）④ `FTn` 关键字表重写为 9 个 ID，并注明 `PHL/CAP/FFT` 属 MCNP6 发布说明段 ⑤ SDEF 变量表按 Table 3.3 校订（`EXT` 默认 0、`VEC`/`ARA`/`PAR` 措辞）⑥ `SPn` 补 `C`/`V`/`f a b` ⑦ `MTn`→`MTm`（正文 §8e + 附录）⑧ KCODE 补全 8 参数与官方默认 ⑨ 格式规则 14 条（注释 1-5 列、续行主规则、`nILOG`/`xM`、空行终止符）⑩ 附录 `PRINT` 3-144→**3-149**、`SIn/SPn/SBn` 3-63→**3-62** ⑪ 补录段由"待核"升级为"已核 + 官方默认值 + 未核项声明" | P0/P1/P2 |
| `MCNP6_曲面卡格式参考.md`（LF） | +21 / −12 | ① 标题/来源/结语手册名 ② §七例 3 的 `*TR7` 改回原文 6 值示例，并加"原文角度组合非正交、实际请给正交余弦"提示 ③ 感度 5 条 `ε`→**`∞`** | P1 |
| `源分布卡说明.md`（CRLF） | +14 / −5 | ① 两处手册名 ② KSRC 改为原文口径（全局至少一点 + "通常每区一点就够"）③ 示例 8 的 `.707`→`.707107` ④ 示例 7 加"原文 `TR=1` 与 `TR77` 不一致"注 ⑤ Table 3.4 的 −4 FWHM 加"手册自身表述不一致"注 | P1/P2 |

规模：`git diff --stat` = **12 files changed, 472 insertions(+), 284 deletions(-)**（6 篇 × `app/docs` 与 `gui/public/docs` 两处）。

### 9.2 改完之后的实测复验

| 检查项 | 方法 | 结果 |
|---|---|---|
| **表号表 ↔ 手册** | 脚本按**行坐标**从 PDF 675/676 页抽取 Table 3.7 的 (表号, 类型, 描述) 34 行，与改正后的表逐行比对（连字/全半角先归一化） | ✅ **PASS 34/34** |
| 手册名残留 | 6 篇 grep `MCNP6 手册` | ✅ **0**（修正前 11 处） |
| PDF 连字残留 | 6 篇 grep `[\uFB00-\uFB04]` | ✅ **0**（修掉 `justiﬁable`、`ﬁssile` 两处） |
| 关键修正点抽查 | 25 个特征串逐条 grep | ✅ 25/25 |
| 换行风格 | 逐文件统计 CRLF/bare-LF | ✅ 6/6 内部一致（4 篇全 LF；C810、源分布卡两篇全 CRLF），无混合 |
| 镜像同步 | `app/docs` ↔ `gui/public/docs` 逐文件 SHA256 | ✅ **6/6 一致**；`gui/dist/docs` 同步同 6 篇 |
| 改动面 | `git status --porcelain` | 6 篇 ×2 目录 = 12 文件 modified；`docs/qa-report-tutorial-c810.md` 新增 |

> 复验过程中机检抓出并已修掉 3 个**我自己引入的**问题：表 130/140 的括注英文被我缩写成 `weight balance`/`nuclide activity`（改为原文全称后通过）、输出卡篇英文引文混入连字 `ﬁ`、FN 篇结语那处手册名首轮漏改。这正是"改完必须实测"的价值。

### 9.3 明确未做（范围外或待你定）

1. `FMESH卡参数填法参考.md` 的**既有内容漂移**（`app/docs` 已回填版 230 行 vs `gui/public/docs` 草稿版 209 行）——该文件无 UI 入口，按你定的"6 篇有 UI 入口"范围未处理。
2. **文件名仍含 `MCNP6_`**（`MCNP6_FN卡结构参考.md`、`MCNP6_输出卡结构参考.md`、`MCNP6_曲面卡格式参考.md`）——改名会牵动 `DocViewer` 调用路径、`gui/dist` 与 `docs/contracts/card-lexicon.md` 等引用，建议单独一次做。
3. 那 11 张补录辅助卡的 **Form 段细节**仍未逐字核（文档内已显式声明未核范围）。
4. 未新建锚点/回归测试（按你此前决定）；本次机检脚本属一次性探针。
5. `docs/CHANGELOG.md`、`docs/手动打包方法.md` 的未提交改动**不是本次产生的**（改动前即存在）。

### 9.4 复现方式（探针被清理后仍可重做）

- **表号表机检**：PyMuPDF 打开 `C810.pdf` → 取第 675/676 页（打印 3-150/3-151）的 `get_text("dict")` → 按 y 聚类，表号列 x≈85-110（3-150）/118-148（3-151）、类型列 x≈165-200/196-240、描述列 x≥220/258 → 得到 34 组 (表号, 类型, 描述) → 与 `app/docs/PRINT卡说明.md` 表格逐行比对（描述需归一化后作子串匹配，类型列须相等）。
- **渲染检查**（建议你做一次）：在程序里点开「📖 C810 / 曲面参考 / 源参考 / FN参考 / 输出卡参考 / PRINT」，扫一眼新表与新注是否正常显示（我未启动 GUI 验证渲染）。
