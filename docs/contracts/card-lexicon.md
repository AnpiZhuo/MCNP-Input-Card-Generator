# MCNP 卡类型权威词条目录（Lexicon）

> **MCNP 卡格式唯一权威源 = 官方 `D:\MCNP\MCNP6\C810.pdf`（MCNP5 版：卡格式权威章 = MCNP5 卷 II Ch.3，打印页 3-1~3-166；本 PDF 不含 MCNP6.1 手册卷 II Ch.3）。**
> 本文件与 `app/docs/` 蒸馏 md 均为**派生产物**，可能含盲区，必须随 C810.pdf 更新。
> **MCNP6 专属卡（BFLD/COSY/DAWWG/EMBED/KPERT/KSEN/TROPT/UNC/ACT/BURN/PHYS:H/HE 等）在 C810.pdf 无格式定义**（仅 MCNP6.1 发布说明提及）——此类卡须另以 **MCNP6 手册卷 II Ch.3** 核验；本机当前无该手册，相关词条标注「待 MCNP6 手册核验」。
> 后续任何新增/修改 MCNP 卡类型（解析/生成/前端 UI/分节识别），必须：
> 1. 先回查 C810.pdf（MCNP5 卷 II Ch.3）或 MCNP6 手册对应章节确认格式，再在本文件登记词条 + 更新差异表；
> 2. 蒸馏 md 有缺失 → 同步补录对应 `app/docs/*.md`；
> 3. 修改卡格式 → 先改本文件与 md，再改代码，防止解析器与知识库二次漂移；
> 4. 差异表条目修复后 → 状态标「已修」，不得删除（保留审计痕迹）。
>
> 维护责任人：架构师（登记 + C810.pdf 复核）→ 项目经理（排期）→ 后端（按差异表施工）。

- 权威源：**`D:\MCNP\MCNP6\C810.pdf`（卡格式权威 = MCNP5 卷 II Ch.3，打印页 3-1~3-166；**本 PDF 无 MCNP6.1 卷 II Ch.3**）**；MCNP6 专属卡（BFLD/EMBED/KPERT/KSEN/DAWWG/TROPT/UNC/COSY/ACT/BURN/PHYS:H/HE 等）另需 MCNP6 手册卷 II Ch.3 核验（本机缺，标注待核验）；本文件 + `app/docs/` 蒸馏 md 均为派生
- 来源（蒸馏派生物，各带 C810.pdf 页号引用）：`app/docs/C810_卡片格式详细.md`、`app/docs/MCNP6_FN卡结构参考.md`、`app/docs/MCNP6_曲面卡格式参考.md`、`app/docs/MCNP6_输出卡结构参考.md`、`app/docs/PRINT卡说明.md`、`app/docs/源分布卡说明.md`、`app/docs/sample_format.md`
- 审计范围：解析器 `app/generator/parsers/core.py`（`parse_data_cards`）、`parsers/sections.py`（分节识别）、`app/generator/validator.py`；生成/序列化联动（`inp_generator.py`、`gui/backend/api_server.py`、`parsers/__init__.py`）
- 审计日期：2026-08-13（工作树 `experiment/geouned`，**只读审计，未改任何 app/ 源码**）
- 行号为当前工作树实测，非 commit 版本（FM 修复已在工作树、未提交）

> **核验状态（2026-08-13，上级纠正后重锚定）**：
> - 本版词条基于 `app/docs/` 蒸馏 md（其各章节页号已引用 C810.pdf，如 FN 卡 3-80 起 / 曲面 3-11 起 / 输出卡 3-143 起 / 源分布 3-53 起）+ 解析器源码实测交叉构建。
> - **✅ C810.pdf 页级逐卡核验已完成（2026-08-13，tester，PyMuPDF 1.28 全库页级文本抽取，零安装）**：C810.pdf 实际构成 = **MCNP5 卷 I+II 全文 + MCNP6.1/MCNP5 发布说明 + 附录 + 索引**；卡格式权威章 = **MCNP5 卷 II Ch.3**（PDF 页 526-691，打印页 3-1~3-166）。**权威源声明修正**：本 PDF 是 MCNP5 版卡格式，MCNP6 专属卡（BFLD/EMBED/KPERT/KSEN/DAWWG/TROPT/UNC/COSY/ACT/BURN/PHYS:H/HE 等）无格式定义，须另以 MCNP6 手册卷 II Ch.3 核验。D-09 全部 ~35 族候选已三分定案（确认真卡 27 族 / MCNP6 专属仅提及 8 族 / 本 PDF 无证据 16 族），详见 §1.3.8 核验表 + `docs/card-lexicon-diff.md` D-11。
> - **已核事实（md 内部 + 解析器实测 + PDF 页级）**：FM 卡在蒸馏 md 中**已有**（`C810_卡片格式详细.md` §4b:305-312 + 附录索引:642、`MCNP6_FN卡结构参考.md` §二:29）——原「FM 不识别」根因在**解析器**（入口门正则漏 FM），不在 md；`C810_卡片格式详细.md` 主清单缺计数辅助卡（见 §四，已由 FN 卡 md 合并补录）；Table 3.11（3-161~3-164）为 C810 全卡汇总表，SPDTL/DRXS/AWTAB/XSn/PIKMT/MGOPT/THTME 等均在其中。

---

## 一、权威词条目录

### 1.1 栅元段（CELL CARDS）

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| 栅元卡 | `j m d geom params` | 无 | 无 | 定义几何区域：编号/材料/密度/曲面表达式/栅元参数 |
| 栅元参数 | `IMP:pl=VALUE`、`VOL=`、`PWT=`、`EXT=`、`FCL=`、`U=`、`FILL=`、`LAT=`、`TRCL=`、`TMP=` | IMP 有（:N/:P/:E） | 无 | 栅元级重要性/体积/指数变换/强制碰撞/宇宙/填充/格阵/变换/温度 |
| LIKE m BUT | `j LIKE k BUT kw=val` | 无 | 无 | 继承栅元 k 形状，仅改指定参数 |

> 解析器：`parse_cells`（core.py:158-319）结构化，栅元参数全字段覆盖，`LIKE m BUT` 落在 surface_expr 原样保留（几何表达不丢）。

### 1.2 曲面段（SURFACE CARDS）

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| 方程曲面 | `j n TYPE params`：P/PX/PY/PZ、SO/S/SX/SY/SZ、CX/CY/CZ/C/X/C/Y/C/Z、KX/KY/KZ/K/X/K/Y/K/Z、SQ、GQ、TX/TY/TZ、X/Y/Z 坐标平面 | 无 | 曲面号前缀 `*`=反射、`+`=白边界 | 定义曲面方程（n>0=TRn 变换，n<0=周期性） |
| 轴对称点定义 | `j n X x1 r1 [x2 r2] [x3 r3]`（X/Y/Z） | 无 | 同上 | 由 1-3 个坐标对生成平面/线性/二次曲面 |
| 三点定义平面 | `j n P X1 Y1 Z1 X2 Y2 Z2 X3 Y3 Z3` | 无 | 同上 | 过三点定义平面（>4 输入项时） |
| 宏体 | `j n BOX/RPP/SPH/RCC/RHP/HEX/REC/TRC/ELL/WED/ARB params` | 无 | 同上 | 一类几何体，自动分解为方程曲面（小面编号） |
| TRn 变换卡 | `TRn O1..O3 B1..B9 M` / `*TRn …` | 无 | `*TRn`=B 矩阵为角度 | 曲面坐标变换（位移+旋转），1≤n≤999 |

> 解析器：`parse_surfaces`（core.py:322-324）**按原文整体保留**（不结构化），曲面类型由 validator `_SURFACE_TYPES` 校验；`*TRn` 数据段 → `tr_cards`（core.py:1157-1160）。曲面内容无丢失（往返保真靠原文）。

### 1.3 数据段（DATA CARDS，主清单）

#### 1.3.1 粒子 / 运行控制

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| MODE | `MODE N[/P][/E][/H][/HE][/D][/T][/A]` | 无 | 无 | 粒子输运类型开关 |
| NPS | `NPS N [NPSMG]` | 无 | 无 | 历史数截断 |
| CTME | `CTME minutes` | 无 | 无 | 计算机时间截断 |
| ACT | `ACT ...` | 无 | 无 | 活化分析——**MCNP6/MCNPX 专属（D-13）**：MCNP5 C810 Ch.3 无此卡节，待 MCNP6 手册核验 |
| NONU | `NONU` | 无 | 无 | 关闭裂变中子产生 |
| TOTNU | `TOTNU` | 无 | 无 | 用总 ν（瞬发+缓发）采样裂变中子数 |
| NOTRN | `NOTRN` | 无 | 无 | 禁止散射输运（只算直穿） |
| PRINT | `PRINT tbl1 …` | 无 | 无 | 输出打印表选择 |
| PRDMP | `PRDMP NDP NDM MCT NDMP DMMP` | 无 | 无 | 打印与转存周期控制 |
| RAND | `RAND GEN=… SEED=…` | 无 | 无 | 随机数参数（重现） |
| FILES | `FILES unit filename access form rec_len` | 无 | 无 | 输出文件创建 |
| DBCN | `DBCN X1..X20` | 无 | 无 | 调试输出控制 |
| LOST | `LOST LOST(1) LOST(2)` | 无 | 无 | 粒子丢失控制 |
| PTRAC | `PTRAC keyword=params …` | 无 | 无 | 粒子径迹输出 |
| MPLOT | `MPLOT MCPLOT kw=param …` | 无 | 无 | 运行中记数绘图 |
| TALNP | `TALNP [n1 n2 …]` | 无 | 无 | 记数分箱打印控制 |

#### 1.3.2 截断 / 重要性

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| CUT:n | `CUT:N/P/E/H/HE/D/T/A T E WC1 WC2 SWTM` | 有（:N/:P/:E/:H/:HE/:D/:T/:A） | 无 | 时间/能量/权重截断 |
| ELPT:n | `ELPT:N/P/E E1 E2 …` | 有 | 无 | 逐栅元能量截断 |
| IMP:n | `IMP:N/P/E I1 I2 …`（含 r 重复） | 有（可多粒子逗号） | 无 | 栅元重要性数据卡 |
| VOL | `VOL V1 V2 …` | 无 | 无 | 全局栅元体积数据卡 |
| TMP | `TMP T1 T2 …` | 无 | 无 | 全局温度数据卡 |

#### 1.3.3 源

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| SDEF | `SDEF var=val …`（变量：CEL/SUR/ERG/TME/DIR/VEC/NRM/POS/RAD/EXT/AXS/X/Y/Z/CCC/ARA/WGT/EFF/PAR/TR） | 无 | 无 | 通用源定义（三种赋值：直值/Dn/依赖） |
| SIn | `SI[n] H/L/A/S vals…` | 无 | 无 | 源信息（分布值） |
| SPn | `SP[n] D/C/V vals… 或 f a b`（f=-2/-3/-4/-5/-6/-21/-31/-41） | 无 | 无 | 源概率（含内置函数） |
| SBn | `SB[n] D B1… 或 -21 a / -31 a` | 无 | 无 | 源偏倚 |
| DSn | `DS[n] H/L/S/T/Q …` | 无 | 无 | 依赖分布 |
| SCn | `SCn 注释文字` | 无 | 无 | 源注释 |
| SSW | `SSW S1 S2 … [SYM=] [PTY=] [CEL=]` | 无 | 无 | 写面源文件 |
| SSR | `SSR OLD/NEW S… [CEL=] [PTY=] [COL=] [WGT=] [TR=] [PSC=]` | 无 | 无 | 读面源文件 |
| KCODE | `KCODE NSRC RKK IKZ KCT [MSRK KNRM MRKP KC8]` | 无 | 无 | 临界源参数 |
| KSRC | `KSRC x1 y1 z1 …` | 无 | 无 | 临界初始源点 |
| HSRC | `HSRC nx xmin xmax ny ymin ymax nz zmin zmax` | 无 | 无 | 香农熵收敛网格 |
| IDUM/RDUM | `IDUM …` / `RDUM …` | 无 | 无 | SOURCE 子程序数据数组 |

#### 1.3.4 材料

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| Mn | `Mn ZAID1 f1 … [kw=val]`（kw=GAS/ESTEP/NLIB/PLIB/PNLIB/ELIB/COND） | 无 | 无 | 材料组成（ZAID+份额+选项） |
| MTn | `MTn ZAID1 ZAID2 …` | 无 | 无 | S(α,β) 热散射 |
| MPNn | `MPNn ZA1 ZA2 …` | 无 | 无 | 光核核素选择 |

#### 1.3.5 物理

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| PHYS:N | `PHYS:N EMAX EMCNF IUNR DNB FISNU` | 有 | 无 | 中子物理设置 |
| PHYS:P | `PHYS:P EMCPF IDES NOCOH ISPN NODOP` | 有 | 无 | 光子物理设置 |
| PHYS:E | `PHYS:E EMAX IDES IPHOT IBAD ISTRG BNUM XNUM RNOK ENUM NUMB` | 有 | 无 | 电子物理设置 |
| PHYS:H / PHYS:HE | MCNP6 扩展 | 有 | 无 | 质子/重离子物理设置——**MCNP6 专属（D-13）**：MCNP5 C810 Ch.3 仅 PHYS:N/P/E，本卡待 MCNP6 手册卷 II Ch.3 核验 |
| PHYS（裸） | `PHYS` | 无 | 无 | 裸 PHYS 卡（保原样） |
| MPHYS / LCA | — | 无 | 无 | 多物理/潜在 alpha 计数相关——**存疑（D-13）**：C810 全文 0 出现、PyMCNP 类空 docstring，疑似占位/非真卡，待 MCNP6 手册卷 II Ch.3 复核 |

#### 1.3.6 计数（Tally，本审计核心）

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| **Fna** | `Fn:pl S1…Sk`（n=1/2/4/5/6/7/8 或 +10 增量，如 11/21/101） | **有**（:N/:P/:E/:N,P/:P,E） | **有**（`*Fn` 能量×权重/jerks/g/能量沉积；`+F8` 电荷沉积） | 7 种基本计数：F1 面电流/F2 面通量/F4 栅元通量/F5 探测器/F6 能沉/F7 裂变能沉/F8 脉冲高度 |
| **F5 变体** | `F5a:pl a0 r ±R0`（a=X/Y/Z 环探测器）；`FIPn/FIRn/FICn` 成像 | 有 | 有 | 环探测器/针孔成像/平面放射成像/柱面成像 |
| FCn | `FCn 注释` | 无 | 无 | 记数注释 |
| En | `En E1…Ek [NT/C]`；`E0` 全局 | 无 | 无 | 能量分箱（含 `nlog/nlin/nI` 参数化） |
| Tn | `Tn T1…Tk`；`T0` 全局 | 无 | 无 | 时间分箱 |
| Cn | `Cn mu1…muk` | 无 | 无 | 余弦分箱 |
| FQn | `FQn …` | 无 | 无 | 打印层次 |
| **FMn** | `FMn C m r1 r2…` | 无 | 有（`*FM` 罕见） | **记数乘子**（常数×材料×MT 反应，如 `FM4 3.7e10 1 -6` 裂变功率） |
| DEn / DFn | `DEn E1…Ek` / `DFn F1…Fk` | 无 | 无 | 剂量能量/剂量函数转换 |
| EMn / TMn / CMn | `EMn …` / `TMn …` / `CMn …` | 无 | 无 | 能量/时间/余弦乘子 |
| CFn / SFn | `CFn …` / `SFn …` | 无 | 无 | 栅元标记/曲面标记 |
| FSn / SDn | `FSn …` / `SDn …` | 无 | 无 | 记数分段/分段除数 |
| FUn | `FU n …` | 无 | 无 | TALLYX 用户输入 |
| TFn | `TFn …` | 无 | 无 | 记数涨落 |
| DDn | `DDn …` | 无 | 无 | 探测器诊断 |
| DXT | `DXT …` | 无 | 无 | DXTRAN |
| FTn | `FTn keyword vals…`（TAL/PHL/CAP/FFT/INC/GEO…） | 无 | 无 | 记数特殊处理 |
| FMESHn | `FMESHn:N/P GEOM=… ORIGIN=… IMESH=…` | 有 | 无 | 叠加网格记数 |
| SPDTL | `SPDTL …` | 无 | 无 | 晶格速度记数增强 |

#### 1.3.7 其他

| 词条 | 格式 | 粒子后缀 | */+ 前缀 | 作用 |
| :-- | :-- | :-- | :-- | :-- |
| PERT / BURN | `PERTn …` / `BURN …` | 无 | 无 | 摄动分析 / 燃耗——**BURN 为 MCNP6 专属（D-13）**：MCNP5 C810 Ch.3 无，待 MCNP6 手册核验 |
| VOID | `VOID` | 无 | 无 | 全空几何 |
| ESPLT / WWE / WWN | `ESPLT …` / `WWE …` / `WWN …` | 无 | 无 | 分裂增强/权重窗 |

#### 1.3.8 其他（PyMCNP 交叉候选，**✅ 已 C810.pdf 页级核验**）

> **来源：PyMCNP `D:\MCNP\PyMCNP\src\pymcnp\inp\`（每卡一类，~230 顶层卡类；交叉参考，非权威）**。
> 下表为 PyMCNP 有、但 app 蒸馏 md 与解析器结构化识别**均未收录**的 MCNP6 卡类。
> **✅ 2026-08-13 已完成 C810.pdf 页级核验（tester）**，三分定案见下表「核验结论」列（① 确认真卡 / ② MCNP6 专属仅提及 / ③ 本 PDF 无证据）。确认真卡按 C810 页号登记正式词条；MCNP6 专属卡格式须另以 MCNP6 手册卷 II Ch.3 核验；无证据卡不可确认。
> 解析器现状：全部落 else→other_cards 原样保留（无数据丢失）。

| 词条（候选） | 格式 | 粒子后缀 | 作用（PyMCNP 注释推断） |
| :-- | :-- | :-- | :-- |
| AWTAB | `awtab …` | 无 | 原子重量比 |
| BBREM | `bbrem …` | 无 | 轫致辐射（光致核）偏倚 |
| BFLD / BFLCL | `bfld …` / `bflcl …` | 无 | 磁场 / 磁场线圈 |
| COSY / COSYP | `cosy …` / `cosyp …` | 无 | 磁聚焦坐标系变换 |
| DAWWG | `dawwg …` | 无 | 权重窗相关 |
| DMn | `dm{n} zaids…` | 无 | ZAID 别名列表 |
| DRXS | `drxs …` | 无 | 反应截面相关 |
| DXCn | `dxc{n}:pl probs…` | 有 | DXTRAN 贡献概率 |
| EMBED 族 | `embed/embdb/embdf/embeb/embee/embem/embtb/embtm …` | 无 | 嵌入式网格/计数（MCNP6） |
| FMULT | `fmult …` | 无 | 多群上散射 |
| HISTP | `histp …` | 无 | 逐计数直方图 |
| KOPTS / KPERT / KSEN | `kopts/kpert/ksen …` | 无 | KCODE 选项/摄动/源熵 |
| LCB / LCC / LEA / LEB | `lcb/lcc/lea/leb …` | 无 | 层级相关（待核） |
| MESH | `mesh …` | 无 | 网格（待核） |
| MGOPT | `mgopt …` | 无 | 多群选项（MCNP6） |
| OTFDB | `otfdb …` | 无 | 在线多普勒展宽（MCNP6） |
| PDn | `pd …` | 无 | 点探测器（待核） |
| PIKMT | `pikmt …` | 无 | 概率表（待核） |
| STOP | `stop …` | 无 | STOP 卡（DATE/TIME/NPS 等选项） |
| THTME | `thtme …` | 无 | 时间相关（待核） |
| TROPT | `tropt …` | 无 | TR 选项（待核） |
| TSPLT | `tsplt …` | 无 | 时间分裂（MCNP6） |
| URAN | `uran …` | 无 | 光核相关（待核） |
| UNC | `unc …` | 无 | 不确定度（待核） |
| VAR | `var …` | 无 | 变量（待核） |
| WWG / WWGE / WWGT / WWP / WWT | `wwg/wwge/wwgt/wwp/wwt …` | 无 | 权重窗生成器（WWE/WWN 已在 §1.3.7，但 md 未收录） |
| XS | `xs …` | 无 | 截面（待核） |
| ZA / ZB / ZC / ZD | `za/zb/zc/zd …` | 无 | 光核库选择（待核） |
| MXn | `mx …` | 无 | 最大能量/其他（待核） |
| AREA | `area …` | 无 | 面积（待核） |

##### §1.3.8 核验结果（C810 页级，2026-08-13 tester）

> C810.pdf 卡格式权威章 = **MCNP5 卷 II Ch.3**（PDF 页 526-691，打印页 3-1~3-166）；Table 3.11（3-161~3-164）为全卡汇总表。以下结论基于全库页级文本检索 + Ch.3 卡节标题定位。

| 核验结论 | 卡族（C810 打印页号） | 说明 |
| :-- | :-- | :-- |
| **① 确认真卡（Ch.3 有卡节/Table 3.11 收录，27 族）** | AREA(3-25)/ESPLT(3-36)/TSPLT(3-38)/PWT(3-40)/EXT(3-41)/VECT(3-42)/FCL(3-43)/WWE(3-45)/WWN(3-45)/WWP(3-46)/WWG(3-48)/WWGE(3-48)/MESH(3-49)/PDn(3-52)/DXCn(3-52)/BBREM(3-53)/VAR(3-35)/URAN(3-32)/SPDTL(3-120)/DRXS(3-125)/TOTNU(3-126)/NONU(3-126)/AWTAB(3-127)/**XSn**(3-127，助记符带 n)/PIKMT(3-128)/MGOPT(3-129)/THTME(3-137) | 均为 MCNP5 真卡，MCNP6 向后兼容保留。其中 AREA/EXT/VECT/PWT(数据卡)/VAR/TSPLT/BBREM/FCL(数据卡)/URAN/THTME/PDn/DXCn/DRXS/AWTAB/XSn/PIKMT/MGOPT/WWG/WWGE/MESH 词条正文未登记（→ D-12） |
| **② MCNP6 专属（发布说明提及、本 PDF 无格式定义，8 族）** | BFLD(p30)/COSY(p30)/DAWWG(p29)/EMBED 族 8 子卡(p29)/KPERT(p37)/KSEN(p28)/TROPT(p32)/UNC(p31) | C810 仅 MCNP6.1 发布说明（PDF 页 15-77）提及为新增卡，Ch.3 无格式章节；格式须另以 MCNP6 手册卷 II Ch.3 核验 |
| **③ 本 PDF 无证据（16 族，不可确认）** | BFLCL/COSYP/DMn/FMULT/HISTP/KOPTS/LCB/LCC/LEA/LEB/OTFDB/STOP/WWGT/WWT/ZD/MXn | 全库页级检索 0 命中；PyMCNP 对应类多空 docstring（占位类，如 Lca.py/Mphys.py/Lcb.py 等）。HISTP 在 C810 仅作 MCNPX 输出历史文件出现，非卡 |
| ZA/ZB/ZC（附注） | Appendix A/F（PDF 页 875/884/917 等）承认为"separate cards for inputting user data"（无 Ch.3 卡节）；**ZD 全库无** | 待与 MCNP6 手册确认 ZA/ZB/ZC/ZD 完整格式 |

##### D-12 正式词条补录（C810 确认真卡 20 族 + WWP，2026-08-13）

> 下列为 C810（MCNP5 卷 II Ch.3）确认真卡、此前仅列于候选表未登记正式词条；现按 C810 打印页号补录（D-12）。解析器现状：全部落 other_cards 兜底保留（无数据丢失，数据流不动）。格式栏为 PyMCNP 类推断，**格式细节待 C810 页核验**。已登记他处的 ① 确认真卡不重复：ESPLT(3-36)/WWE(3-45)/WWN(3-45)（§1.3.7）、TOTNU(3-126)/NONU(3-126)（§1.3.1）、SPDTL(3-120)（§1.3.6）。

| 词条 | C810 页号 | 格式（PyMCNP 推断） | 作用 |
| :-- | :-- | :-- | :-- |
| AREA | 3-25 | `AREA …` | 面积 |
| EXT（数据卡） | 3-41 | `EXT …` | 指数变换数据卡（栅元 `EXT=` 另见 §1.1） |
| VECT | 3-42 | `VECT …` | 矢量 |
| PWT（数据卡） | 3-40 | `PWT …` | 光子产生权重数据卡（栅元 `PWT=` 另见 §1.1） |
| VAR | 3-35 | `VAR …` | 变量 |
| TSPLT | 3-38 | `TSPLT …` | 时间分裂 |
| BBREM | 3-53 | `BBREM …` | 轫致辐射（光致核）偏倚 |
| FCL（数据卡） | 3-43 | `FCL …` | 强制碰撞数据卡（栅元 `FCL=` 另见 §1.1） |
| PDn | 3-52 | `PD{n} …` | 点探测器 |
| DXCn | 3-52 | `DXC{n}:pl …` | DXTRAN 贡献概率（带粒子后缀） |
| DRXS | 3-125 | `DRXS …` | 反应截面相关 |
| AWTAB | 3-127 | `AWTAB …` | 原子重量比 |
| XSn | 3-127 | `XS{n} …` | 截面（助记符带 n，**非 XS**） |
| PIKMT | 3-128 | `PIKMT …` | 概率表 |
| MGOPT | 3-129 | `MGOPT …` | 多群选项 |
| THTME | 3-137 | `THTME …` | 时间相关 |
| URAN | 3-32 | `URAN …` | 光核相关 |
| WWG | 3-48 | `WWG …` | 权重窗生成器 |
| WWGE | 3-48 | `WWGE …` | 权重窗生成器（增强） |
| MESH | 3-49 | `MESH …` | 网格 |
| （附）WWP | 3-46 | `WWP …` | 权重窗（① 确认真卡，D-12 未列此处补全；WWGT/WWT 属 ③ 无证据） |

> 另有 md 缺失但解析器 `_KNOWN_OTHER_CARDS` 已"known"的：ESPLT / WWE / WWN / VOID / LCA / MPHYS / PERT（C810_卡片格式详细.md §1.3.7 仅列部分；解析器均保 other_cards）。**注：LCA / MPHYS 在 C810 全文 0 出现、PyMCNP 类空 docstring，疑似占位/非真卡，建议复核（见 diff 表 D-13）**。

---

## 二、解析器实际认识清单（工作树现状）

> 入口：`parse_data_cards`（core.py:892-1262）；分节：`split_sections`（sections.py:85-245）。

### 2.1 结构化识别（有专门分支，进结构化字段）

| 词条 | 解析分支（行号 = 当前工作树） | 去向 |
| :-- | :-- | :-- |
| MODE | core.py:937-948 | mode_n/p/e/h/he/d/t/a |
| NPS / CTME / ACT / PRINT / NONU | core.py:949-963 | nps / ctme / act / print_pr / nonu |
| Mn | core.py:964-983 | materials[].rows |
| MTn | core.py:984-996 | materials[].mt_card |
| SDEF | core.py:997-1028 | sources[] + sdef_* 字段 + SI/SP/SB/DS 收集 |
| SIn/SPn/SBn/DSn（紧跟 SDEF） | core.py:1003-1028 | sdef_distributions + sdef_raw_text |
| **Fna / F5 变体 / 成像 / *F/+F** | 入口门 core.py:1029-1042 → parse_f_tally:704-814 | tally_defs[]（type/number/particles/params/fn_prefix/number_suffix） |
| **FMn** | 入口门 core.py:1030 → parse_f_tally FM 分支:723-739 | tally_defs[].multiplier（无 Fn 时建占位 type=""） |
| E0 / En | core.py:1044-1056 / 1171-1185 | e0_* / e_cards_lines（En 经 parsers/__init__:94-109 关联 tally.generate_en） |
| CUT:n | core.py:1057-1059 → parse_cut:817-833（支持 N/P/E/H/HE/D/T/A） | tally.cut_*_raw + cut_*_t/e/wc1/wc2/swtm |
| PHYS:N/P/E/H/HE | core.py:1060-1100 | phys_* 字段 |
| KCODE / HSRC | core.py:1103-1120 | kcode_* / hsrc_* |
| SSW / SSR | core.py:1121-1156 | ssw_* / ssr_*（source_mode=surface） |
| TRn / *TRn | core.py:1157-1160 | tr_cards |
| KSRC | core.py:1161-1170 | ksrc_points[] |
| T0 / Tn | core.py:1186-1215 | t0_* / t_cards_lines（Tn 关联 tally.generate_tn） |
| IMP:n | core.py:1216-1225 | imp_n/p/e_values → 应用至栅元 |
| 裸核素行（数字开头） | core.py:1250-1260 | 归属 current_mat（材料续行，设计内） |
| #ifdef/#else/#endif | core.py:1230-1249 | 材料 raw 行 / pending_raw |

### 2.2 保 other_cards 原样（不丢、无结构）

| 词条 | 命中路径 | 去向 |
| :-- | :-- | :-- |
| FTn / FQn / FCn / FUn | `_TALLY_MODIFIER_RE`（core.py:845-847，`^(FU|FT|FQ|FC|T|E)\d+$`）→ core.py:1226-1229 | other_cards（生成器 verbatim 回放，inp_generator:1111-1120） |
| PHYS（裸）/ MPHYS / LCA / PRDMP / DBCN / TOTNU / PTRAC / VOID / LOST / ESPLT / WWE / WWN / BURN / FMESH / PERT | `_KNOWN_OTHER_CARDS`（core.py:836-842）→ core.py:1226-1229 | other_cards |
| Cn / DEn / DFn / EMn / TMn / CMn / CFn / SFn / FSn / SDn / TFn / DDn / DXT / SPDTL / ELPT:n / NOTRN / VOL / TMP / TALNP / MPLOT / RAND / FILES / IDUM / RDUM / MPNn / SCn / SBn / DSn（独立）/ FMESHn / PERTn | else 兜底（core.py:1250-1260，非 zaid 行） | other_cards |

### 2.3 静默丢弃（缺陷，见差异表 D-01）

| 词条 | 命中路径 | 去向 |
| :-- | :-- | :-- |
| **SIn / SPn（未紧跟 SDEF）** | core.py:1101-1102 `first.startswith("SI") or first.startswith("SP") → i+=1` | **直接丢弃，不进任何字段** |

### 2.4 分节识别（sections.py）

- `DATA_KEYWORDS`（sections.py:131-138）：MODE/NPS/CTME/NONU/SDEF/PRDMP/KCODE/KSRC/TOTNU/PTRAC/VOID/LOST/DBCN/PERT/SSW/SSR/ESPLT/WWE/WWN/PHYS:*/BURN/FMESH/FC/F/F0/PRINT/ACT/MPHYS/LCA
- `DATA_PATTERNS`（sections.py:140-153）：M\d+ / SI\d* / SP\d* / F\d+: / F\d+$ / FM\d+$ / FC\d+$ / E\d*$ / CUT: / MT\d+ / \*?TR\d+ / (FU|FT|FQ|T)\d+
- **缺口**：Cn / DEn / DFn / FSn / SDn / CFn / SFn / EMn / TMn / CMn / TFn / DDn / DXT / SBn / DSn / SCn / ELPT / NOTRN / TALNP / MPLOT / RAND / FILES / IDUM / RDUM / FMESHn（带编号）未入清单（差异表 D-03）

### 2.5 其他解析文件

- `validator.py`：`_SURFACE_TYPES`（曲面类型校验）+ `validate_all/validate_deck`（结构校验，不识别新卡类型）。曲面类型表缺 `TXY/TXZ/TYZ`（椭圆柱，C810 §2 有列但为 C810 附录的补充形式），已在 `lines.py` 之外单独存在——本审计不视为差异（曲面按原文保留，无丢失）。
- `parsers/lines.py`：`_SURFACE_TYPES` 与 validator 同源（P/PX/…/RHP/HEX/X/Y/Z），`normalize_lines` 负责续行/注释归一。

---

## 三、差异总览（设计意图校准后，2026-08-13）

**设计意图（上级明确，PM 裁决采纳）**：程序**有意**不覆盖所有 MCNP 关键词——未设计的"数据卡"关键词落 **other_cards** 兜底、未设计的"栅元卡"关键词落栅元 **other_params** 框。**这是设计好的安全网，非遗漏、非 bug。**

**词条专项三目标**（不再以"全结构化"为目标）：
1. **兜底网可靠性**：任何未设计卡完整落入其他框，round-trip 不丢不坏（重点测几条）。
2. **告警机制**：known/unknown 提示合理，用户知道"这张卡未结构化支持、原样保留在高级-其他"。
3. **高价值卡结构化**：仅对用户高频依赖的卡加结构化（参照 FM——导入识别 + 可编辑），**不是所有卡都结构化**。

**差异按三类重评**（完整差异表 + 施工契约见 `docs/card-lexicon-diff.md`）：

| 归类 | 条数 | 条目 | 说明 |
| :-- | :-- | :-- | :-- |
| ① 兜底可靠可保持（仅登记/核验） | 8 | D-02 计数辅助卡（登记）、D-04 告警语义（第二支柱）、D-06 En 参数化、D-08 md 主清单缺口（已修）、D-09 PyMCNP ~35 族（设计行为）、**D-11（PDF 页级核验三分定案，已核验）**、**D-12（PDF-only 20 族待登记）**、**D-13（词条有但 C810 无，待复核）** | 均落 other_cards verbatim，round-trip 不丢；**无需为"对齐"给每张卡加解析** |
| ② 兜底会丢/误吸收 = **真需修** | 3 | **D-03** sections.py 分节缺口（P1）；**D-07** SDEF 裸参数静默丢（P2）；**D-10（新增）** other_cards 行内 `$` 注释被剥离（P2） | 真兜底失效：卡被误分节 / 值静默丢 / 注释 round-trip 丢 |
| ③ 高价值卡结构化（仅高频） | 1 | D-05 FMn 前端乘子 UI（后端已修，补前端闭环） | FM 典型：导入识别 + 可编辑 |
| 已修 | 1 | D-01 独立 SIn/SPn（backend-fb16，pytest 293 绿） | — |

**现存差异 13 条 = P0×1（已修）+ P1×1（D-03 真需修）+ P2×11**（其中真需修 D-07/D-10；其余登记/核验/增强）。
**结论**：真需修 = D-03 / D-07 / D-10（3 条）；确认兜底即可 = D-02 / D-04 / D-06 / D-08 / D-09 / D-11 / D-12 / D-13（8 条）；高价值结构化 = D-05（1 条，前端）。

> **对已知线索的澄清**（PM 指示核对 FS/FT/FQ/SD/CF/TF/DE/DF/E4/T4）：
> - **E4/T4 已识别**：入 `e_cards_lines`/`t_cards_lines` 原文保留并关联 tally.generate_en/generate_tn（parsers/__init__:94-109），round-trip 不丢；
> - **FS/FT/FQ/SD/CF/TF/DE/DF/Cn/FU/EM/TM/CM/DD/DXT/SPDTL 均保留**：入 other_cards verbatim 回放，无数据丢失，仅无结构化（P2，见 D-02）；
> - **FM 已修（工作树未提交）**：入口门 + parse_f_tally FM 分支 + models.multiplier + 生成器回放 + api 透传 + 回归测试 test_regress_fm5_import.py（3 用例）全链已通，剩余仅前端乘子编辑 UI（D-05）。

---

## 四、防漂移维护机制

1. **权威核对第一序位**：任何卡类型的增改，先回查 `C810.pdf` 对应章节（**卡格式权威 = MCNP5 卷 II Ch.3**：数据卡约 3-24 起、计数卡约 3-80 起、曲面卡 3-11 起、源分布 3-53 起、输出卡 3-143 起）；**MCNP6 专属卡另以 MCNP6 手册卷 II Ch.3 核验**。再登记本文件、再改代码。**蒸馏 md 不得作为唯一依据**（可能漏卡，见下）。
2. **登记即契约**：新卡落地前，架构师在本文件 §一 登记词条（来源标注 C810.pdf 页号），再排期施工；卡格式变更先改本文件 + 对应 `app/docs/*.md` 再改代码。
3. **差异表状态机**：`docs/card-lexicon-diff.md` 每条目维护「待修 → 施工中 → 已修」状态；已修条目保留在表内（标注修复 commit），不删除，供回溯。
4. **闸门建议**（后端施工时可选落地）：新增 `tests/parser/test_card_lexicon.py`，断言解析器入口门/`_KNOWN_OTHER_CARDS`/`_TALLY_MODIFIER_RE` 与本节 §二 清单一致，防词汇漂移（参照 api.yaml 漂移闸门模式）。
5. **归口**：本文件由架构师维护；后端/前端施工涉及新卡时，先经项目经理向架构师提出登记，再施工。

> **已识别的 md 盲区（2026-08-13）**：`C810_卡片格式详细.md`（主清单）未收录计数辅助卡 EMn/TMn/CMn/CFn/SFn/FSn/SDn/FUn/TFn/DDn/DXT/SPDTL（`MCNP6_FN卡结构参考.md` §二 已收录并带 PDF 页号 3-104~3-120）。**已由本次审计将这批词条合并补录进 `C810_卡片格式详细.md` §4b + 附录索引**（来源标注 FN 卡 md，待 C810.pdf 页级核验）。
