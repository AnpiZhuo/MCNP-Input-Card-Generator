# FMESHn 卡 · C810.pdf 格式核验报告（只读核验）

> 任务来源：PM 派发（供编写《FMESH卡参数填法参考》文档）
> 核验源：`D:\MCNP\MCNP6\C810.pdf`（唯一权威源 = MCNP5 卷 I+II 全文 + MCNP6.1/MCNP5 发布说明；卡格式权威章 = MCNP5 卷 II Ch.3 = PDF 页 526-691 = 打印页 3-1~3-166）
> 核验人：tester（子代理）　日期：2026-08-14　红线：零安装，只读
>
> **执行结论（摘要）**
> 1. **❌ C810.pdf 原文抽取未执行成功**：本会话沙箱与派生子代理均**无 OS 命令执行工具**（已自查工具集 + 子代理探测确认），无法运行本机已装的 fitz/PyMuPDF（记忆记载 1.28.0）。对 PDF 二进制做 raw grep 亦无 "FMESH" 明文（文本流被压缩），无法绕过 PDF 库直接读文本。
> 2. **✅ 已收集全部本地派生证据**（契约文档、前后端实现、测试 pin、PyMCNP 交叉参考），并发现 **7 处派生文档/实现间的语义冲突**（见 §3，这些是无需 C810 即可成立的 QA 发现）。
> 3. **⚠️ 本报告不提供任何冒充 C810 原文的"引文"**。任务 a~h 逐条结论均为「**待人工核对**（给出 C810 精确位置 + 要核对的原文问题）」+「派生证据现状」。**建议 PM 侧有命令执行能力的环境直接运行 §6 的零安装脚本**（约 1 分钟出全文），或用户手动翻 PDF。

---

## 1. 核验执行情况（诚实声明）

| 尝试 | 结果 |
| :--- | :--- |
| 工具集自查（本代理） | 无 run/command/shell/terminal/execute/bash/cmd/job_start 类工具；`job_list/job_kill/job_output` 仅管理已启动任务，不能启动新任务 |
| 子代理探测（独立子代理完整工具清单） | 与宿主同工具集，同样无命令执行工具；明确回复"无命令执行工具" |
| 对 C810.pdf 二进制 grep "FMESH" | 0 命中 → 文本流全部压缩（FlateDecode 等），raw grep 不可达 |
| 工作区/临时目录查找先前 tester-pdf 全文抽取残留 | 无（仅蒸馏版 `app\docs\C810_卡片格式详细.md` 731 行，无逐字引文/默认值细节） |
| 本机已装 PDF 库（fitz/PyMuPDF 1.28.0） | 记忆记载存在且 2026-08-13 tester-pdf 曾成功抽取 1001 页，但**本沙箱无法调用** |

→ 按任务第 4 条处理：**无法抽取，如实上报**，并列待用户核对清单（§5），附零安装抽取脚本（§6）。

## 2. 逐条核验结果（a~h）

> 状态图例：🔴 C810 原文不可得（待人工核对）｜🟡 派生证据（项目内已核实，非 C810 原文）｜🟢 无需 C810 即可成立的 QA 结论
> C810 定位：FMESHn 主节 = **打印页 3-118 = PDF 页 643**；Table 3.11 汇总 = 打印页 3-161~3-164 = PDF 页 686~689。

### a. FMESHn 完整语法（卡头 / GEOM / ORIGIN / IMESH/IINTS… 必填性）
- 🔴 **C810 原文：待核对**。打印页 3-118（PDF 643）。核对要点：卡头粒子设计符写法（`FMESHn:N`？）、GEOM 取值集合、ORIGIN 是否必填、IMESH/IINTS 等是否必填及其说明文字。
- 🟡 派生证据（均非 C810 引文）：
  - `app\docs\C810_卡片格式详细.md:330`（蒸馏骨架）：`FMESHn:N/P/E  GEOM=xyz  ORIGIN=x0 y0 z0` + `IMESH=val IINTS=val` / `JMESH=val JINTS=val` / `KMESH=val KINTS=val`；:701 记 FMESHn 打印页 3-118。
  - 实际实现（`app\models.py:204-233`、`app\meshtal\fmesh_parser.py`、`gui\src\volume\fmeshState.ts`）：全部关键字可选（空字段 → raw 兜底回放），卡头默认 `FMESHn`（n 空=0）、particle 默认 "N"、geom 默认 "XYZ"。
  - 卡头设计符容错正则 `([NPEHAS]?)`（fmesh_parser.py:14-16 / fmeshState.ts:191）——N/P/E/H/A/S 都吞，但**实现只把 N/P/E 当 FMESH 设计符**；H/A/S 是否为合法设计符（MCNP6 才有的粒子？）待核对。

### b. EMESH 能量边界单位
- 🔴 **C810 原文：待核对**（3-118）。核对要点：EMESH 是否写默认单位（MeV），是否写"与 Fn 卡能量单位一致"之类表述；TMESH 时间单位是否写 shakes。
- 🟡 派生证据：项目实现无单位说明（placeholder 仅"能量边界（多值，单调递增；空=不分箱）"，fmeshState.ts:180）；测试用 `EMESH=1e-6 1 14`（test_fmesh_parser.py:148，能量数量级暗示 MeV，但**未标注来源**）。
- 💡 一般 MCNP 常识（**非 C810 引文，禁止写入《参考》当作 C810 依据**）：MCNP 能量单位 MeV、时间 shakes。此条必须在 C810 原文确认后才可写入参考文档。

### c. 可选参数与默认值（OUT / DOS / UNIT / MAT / AXS / VEC / PDATA / TRACK / COR / DIMS）
- 🟢 **派生三处 OUT 语义互斥**（QA 发现 F1，见 §3）：契约 §4.7.1 写 `OUT [f|q|n]`（输出单位语义）；`fmeshState.ts:145-155` 写九选项 COL/CF/COLSC/CFSC/IJ/IK/JK/NONE/XDMF（输出格式语义）；PyMCNP `Out.py:65` 只收 `col/cf/ij/ik/jk/none`。**C810（MCNP5）3-118 的 OUT 取值集合与默认值（COL？）必须人工核对**；XDMF 几乎可断定是 MCNP6.2+（ParaView 输出），C810 大概率无——核对确认后标注版本。
- 🔴 **DOS / UNIT / PDATA / TRACK / COR / DIMS**：项目实现与 PyMCNP fmesh 选项族（见 §3 F7）**均无这些关键字** → 高度疑似 MCNP6 TMESH（RMESH/CMESH）专属，C810（MCNP5 FMESHn）应标注「未收录/不支持」。**须人工核对 C810 3-118 全文确认无这些词**。
- 🔴 **MAT**：项目 FMESH 表单/模型有 MAT（默认文案"0=粒子所在格材料（默认），非 0=指定材料号"，fmeshState.ts:184）；**PyMCNP fmesh 选项族无 Mat**。MCNP5 FMESHn 是否真有 MAT 关键字及其默认语义 → 人工核对 3-118。
- 🔴 **AXS/VEC**：项目 cyl 系必填（无默认值；AXS∥VEC 报错，fmeshState.ts:581-588）；C810 对圆柱系 AXS/VEC 的默认值/必填性原文 → 人工核对。
- 🟢 TR：项目实现为可选正整数（fmeshState.ts:590-593），PyMCNP 亦有 Tr 选项；C810 是否有 TR → 人工核对。

### d. 多区间语法（IMESH=v1 v2 IINTS=n1 n2 / 1INTS n）
- 🟢 **契约 §5.3 声明原文（可引用，非 C810）**：`meshtal-visualization.md:335` —— "MCNP6.2+ 支持 `IMESH= v1 v2 ... IINTS= n1 n2 ...`（多区间）与 `1INTS n` 语法"。即**项目契约自己声明多区间/1INTS 是 MCNP6.2+ 行为**，不是 C810（MCNP5）行为。
- 🔴 **C810（MCNP5）行为：无法从 C810 确认**，须人工核对 3-118 原文。若 C810 只有"单值 IMESH + IINTS n"，则确认"多区间= MCNP6 专属，C810 未收录"；若 C810 也写了多值，则修正契约 §5.3。
- 🟡 派生现状：实现已按多值支持（`test_fmesh_parser.py:81-94` pin `IMESH=10 20 IINTS=2 2` 往返保留；`fmeshValidation.test.ts:73-95` 条目数一一对应校验）；但 **1INTS n 语法解析器不支持**（`_KEYS`/`KEY_TO_FIELD` 无 `1INTS` 键）——与 §4.7.1:286 幽灵文字"可多值或 1INTS n 语法"不一致（QA 发现 F2）。

### e. 粒子设计符规则（FMESHn 与 Fn 计数卡号、粒子类型对应）
- 🔴 **C810 原文：待核对**（3-118 FMESHn 设计符说明；Fn 卡设计符总则在 3-81 起，PDF 606 起）。核对要点：FMESHn 的设计符是否与 Fn 卡同一套规则（N/P/E 可组合？）、卡号 n 与 Fn 计数卡号是否独立编号。
- 🟡 派生证据：实现将 FMESHn 卡号/粒子独立存储（number + particle），与 F 卡号无关联校验；FAMILY_RE 容错 N/P/E/H/A/S 但默认 N。

### f. 网格边界与 ORIGIN 的关系
- 🟡 派生证据（项目已 pin 的规则）：`fmeshValidation.test.ts:110-117` —— 直角系 IMESH 首值**必须大于** ORIGIN x 坐标（JMESH>y、KMESH>z），"网格从原点起递增"；fmeshState.ts:557-571 同规则。`minimal_fmesh.inp` 用 ORIGIN=-100 -100 -150 + KMESH=50（50>-150 合法）。
- 🔴 **C810 原文：待核对**（3-118）。核对要点：原文是否有"边界值须大于对应 ORIGIN 坐标"的明确要求；多值边界时是否只约束首值、还是所有边界值都须大于 ORIGIN；圆柱系（径向 r 与 ORIGIN 径向坐标）是否同样约束。

### g. 圆柱/球坐标（GEOM=CYL/SPH）i/j/k 方向语义、角度单位、kmesh 末值=1
- 🟡 派生证据（项目实现语义）：cyl 系 i=径向(r)、j=轴向、k=θ（placeholder fmeshState.ts:174-179 "X/径向""Y/轴向""Z/θ"）；**kmesh 末值须为 1**（"θ 是转数，末值 1 = 整圈 360°"，fmeshState.ts:573-579 + fmeshValidation.test.ts:120-136）；角度单位=**转数**（revolutions，非度/弧度）。
- 🔴 **C810 原文：待核对**。① MCNP5 FMESHn 是否支持 GEOM=cyl（项目另有 REC/RZT 两值，PyMCNP Geom.py:65 收 `xyz|rec|rzt|cyl`）；② 若 C810 无 cyl/sph，则整个圆柱语义（含 kmesh 末值=1）属 MCNP6 行为，须在《参考》标注版本；③ **GEOM=sph（球系）项目与 PyMCNP 均不支持**，C810 有无 sph 待核对；④ 圆柱系 i/j/k 与角度单位若 C810 有原文，须逐字摘录。

### h. 网格单元数 / 内存注意事项
- 🟢 **项目 128³ 警告是"渲染预算"而非 C810 建议**：`fmeshState.ts:493-494` `FMESH_MEMORY_WARNING_THRESHOLD = 2_097_152`（128³），来源是契约 meshtal-visualization.md §2/§12（3D 体积渲染预算），**与 C810 无关**。
- 🔴 **C810 原文：待核对**（3-118 及邻近）。核对要点：MCNP5 手册 FMESHn 节有无网格单元数上限/内存限制/建议（MCNP 手册对网格规模限制一般在别处，3-118 未必有）；无则《参考》注明"C810 未给出该建议"。
- 🟡 派生：契约 §13 另有 meshtal 解析防御"单轴 >4096 报错"（meshtal-visualization.md:173），同为派生设计。

## 3. QA 发现：派生文档/实现间的不一致（无需 C810 即可成立，建议先行裁决）

| # | 冲突内容 | 涉及位置 | 影响 |
| :--- | :--- | :--- | :--- |
| F1 | OUT 语义三处互斥：`[f\|q\|n]`（输出单位，TMESH 风格）vs `COL/CF/COLSC/CFSC/IJ/IK/JK/NONE/XDMF`（输出格式，FMESH 风格）vs PyMCNP `col/cf/ij/ik/jk/none` | meshtal-visualization.md:292 / fmeshState.ts:145-155 / PyMCNP fmesh/Out.py:65 | 《参考》文档 OUT 取值必须以 C810 3-118 原文为准；XDMF 必须核对是否 MCNP6.2+ |
| F2 | §4.7.1 幽灵文字写"可多值或 1INTS n 语法"，实现无 `1INTS` 解析 | meshtal-visualization.md:286 / fmesh_parser.py:19-26 / fmeshState.ts:197-204 | 1INTS 要么实现要么删文案 |
| F3 | FMESH 表单/模型含 MAT，PyMCNP fmesh 选项族无 Mat | models.py:228 / fmeshState.ts:184 / PyMCNP fmesh/ | MAT 是否 FMESH 合法关键字待 C810 核对 |
| F4 | GEOM 取值：项目 XYZ/REC/CYL/RZT 四值 vs 任务问 sph；PyMCNP 同为四值无 sph | fmeshState.ts:132-137 / PyMCNP Geom.py:65 | sph 是否 MCNP6 专属待核对 |
| F5 | DOS/UNIT/PDATA/TRACK/COR/DIMS 在项目与 PyMCNP 均不存在 | — | 判定为 MCNP6 TMESH 专属，C810 标"未收录"，待人工确认 |
| F6 | 契约 §5.1 模型字段名 `eints/t_ints` 已被实现改 `emints/tmints`（记忆记载已改，models.py:225-227 实为 emints/tmints） | meshtal-visualization.md:319-321 vs models.py | 契约文档 §5.1 需同步更新（文档滞后） |
| F7 | 卡头设计符容错 N/P/E/H/A/S，但只有 N/P/E 被当作 FMESH 设计符 | fmesh_parser.py:14-16 / fmeshState.ts:191 | H/A/S 合法性与 C810 设计符集合待核对 |

## 4. C810 页面定位速查（供人工核对/脚本抽取）

| 内容 | 打印页 | PDF 页（=打印页+525） |
| :--- | :--- | :--- |
| 卷 II Ch.3 卡格式章 | 3-1 ~ 3-166 | 526 ~ 691 |
| **FMESHn 主节** | **3-118** | **643** |
| Table 3.11 完整卡汇总表 | 3-161 ~ 3-164 | 686 ~ 689 |
| Fn 计数卡（设计符总则） | 3-81 起 | 606 起 |

## 5. 待用户手动核对关键条目清单（照做即可，逐条回填到《参考》文档）

打开 `D:\MCNP\MCNP6\C810.pdf` → 打印页 **3-118**（PDF 第 643 页），逐条核对：

1. 卡头设计符原文写法与可选粒子（`FMESHn:N`？支持 P/E？有无 H/A/S？卡号 n 与 Fn 是否独立编号？）。
2. GEOM 取值集合原文（只有 xyz？还是含 rec/cyl/rzt？**有无 sph？**）；GEOM= 缺省值。
3. ORIGIN 是否必填；与 IMESH/JMESH/KMESH 的先后、大小关系原文（"首值必须大于 ORIGIN 对应坐标"？所有边界值？）。
4. IMESH/IINTS 等是否只支持**单值**（MCNP5 行为）还是多值；原文有无 `1INTS n` 写法（预计无——契约称 MCNP6.2+）。
5. EMESH 单位原文（MeV？与 Fn 卡单位一致？）；TMESH 时间单位（shakes？）。
6. OUT 取值集合与默认值原文（默认 COL？有无 XDMF？有无 f/q/n 单位语义？）。
7. 有无 DOS / UNIT / MAT / PDATA / TRACK / COR / DIMS / FACTOR 等关键字（预计无= MCNP6 TMESH 专属，须在《参考》标注"未收录/不支持"）。
8. 圆柱系（若 C810 有 GEOM=cyl）i/j/k 方向语义与角度单位；kmesh 末值=1 规则是否在原文。
9. 有无网格单元数/内存限制建议。
10. 顺带核对 Table 3.11（打印页 3-161~3-164）中 FMESHn 行的简写语法。

## 6. 零安装抽取脚本（供有命令执行能力的环境代跑，1 分钟出全文）

脚本：`docs/extract_c810_fmesh.py`（fitz/PyMuPDF，本机已装 1.28.0，**不 pip install**，只读打开）。
运行：`python docs/extract_c810_fmesh.py`；输出：页数自检 + 526-691 页所有含 "FMESH" 的页号 + 打印页 3-118（PDF 643）全文 + Table 3.11 区域（686-689）文本。

## 7. 总体结论

- **C810 原文核验：未完成（沙箱无命令执行能力），不阻塞《参考》文档编写的前提是**：① PM 侧代跑 §6 脚本或用户手动翻 3-118 回填 §5 清单；② 在《参考》中把所有默认值/取值集合标注「版本来源」（MCNP5=C810 3-118 / MCNP6 专属=另注）。
- **已确认的 QA 硬结论（无需 C810）**：派生文档 F1-F7 七处不一致，建议 PM 先行裁决，其中 **F1（OUT 语义）、F2（1INTS）、F6（契约 §5.1 字段名滞后）** 建议在写《参考》前修复文档。
- **红线遵守**：零安装（未执行任何 pip/npm 安装）、只读（未改动 C810.pdf 及任何业务代码）；本报告与脚本为新增文档/工具文件。

---

*本报告由 tester 子代理产出；C810 原文引文一律以人工核对/脚本抽取结果为准，本报告未包含任何冒充 C810 原文的内容。*
