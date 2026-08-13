# 解析器词条清单 × 知识库 差异表（施工契约）

> 审计对象：`app/generator/parsers/core.py`（parse_data_cards）、`parsers/sections.py`、`parsers/__init__.py`、`app/models.py`、`app/generator/inp_generator.py`、`gui/backend/api_server.py`
> **权威基准：官方 `D:\MCNP\MCNP6\C810.pdf`（唯一权威源）**。`docs/contracts/card-lexicon.md` 与 `app/docs/` 蒸馏 md 均为派生产物；本差异表的「知识库格式」列以派生产物为准、**待 C810.pdf 页级核验**。
> 审计日期：2026-08-13，**只读审计未改源码**。行号为审计时工作树实测（FM 修复已在工作树、未提交）；**D-01 修复（backend-fb16）后 core.py 后续分支行号 +~22 位移**，除 D-01 已更新为 1124-1134 外，其余行号按审计时点为准。
> 重锚定说明（2026-08-13）：上级纠正后以 C810.pdf 为唯一权威。**本会话未能做 PDF 页级核验**（Read 缺 poppler-utils、无 shell 抽取文本），差异条目 1-7 为解析器行为事实（源码实测，不受影响）+ 知识库格式基于蒸馏 md（带 C810 页号引用）；**新增条目**：D-08（md 主清单文档缺口，本次已补录）、D-09（PyMCNP ~230 卡类交叉核对——均落 other_cards 保留无丢失，**设计行为非缺陷**，降为兜底可靠性验证）、D-10（other_cards 行内 `$` 注释被剥离 = 兜底会丢，真需修轻量）。**设计意图校准（2026-08-13 上级）**：未设计卡落 other_cards/other_params 是设计好的兜底网，非 bug；专项目标=兜底可靠性+告警机制+高价值卡结构化，重评归三类（见下）。PDF 页级核验待 poppler 就绪后补做，届时本表若有增删会标注「新增/修订」。
>
> **✅ PDF 页级核验已完成（2026-08-13，tester，PyMuPDF 1.28 全库页级文本抽取，零安装）**：C810.pdf 实为 **MCNP5 卷 I+II 全文 + MCNP6.1/MCNP5 发布说明 + 附录 + 索引**，卡格式权威章 = **MCNP5 卷 II Ch.3**（PDF 页 526-691，打印页 3-1~3-166）。已逐页核验 D-09 全部 ~35 族候选（三分定案见 D-11）+ 补录 PDF-only/词典-only 差异（D-12/D-13）。**权威源声明修正**：本 PDF 是 MCNP5 版卡格式，MCNP6 专属卡（BFLD/EMBED/KPERT/KSEN/DAWWG/TROPT/UNC/COSY/ACT/BURN/PHYS:H/HE 等）无格式定义，须另以 MCNP6 手册卷 II Ch.3 核验。
> 本表即系统性修复的施工契约，由 PM 审计通过后派后端执行。每条含建议修法；修复后在本表标记状态+commit。

严重度定义：**P0**=数据丢失；**P1**=结构丢失/误识别；**P2**=仅警告/无 UI 增强。

---

## 设计意图校准与三类重评（2026-08-13）

> **设计意图（上级明确，PM 裁决采纳）**：程序有意不覆盖所有 MCNP 关键词；未设计的"数据卡"关键词落 other_cards 兜底、未设计的"栅元卡"关键词落栅元 other_params 框——均为**设计好的安全网**（非遗漏、非 bug）。词条专项目标重定为：① 兜底网可靠性；② 告警机制；③ 高价值卡结构化（仅用户高频依赖，参照 FM）。**不再以"全结构化"为目标。**

| 条目 | 新归类 | 结论 | 严重度 |
| :-- | :-- | :-- | :-- |
| D-01 | 已修（backend-fb16） | 不受影响 | P0 |
| D-02 | ① 兜底可靠可保持（仅登记） | **确认兜底即可** | P2 |
| D-03 | ② 兜底会丢/误吸收 | **真需修** | P1 |
| D-04 | 告警机制（第二支柱） | 确认兜底即可；告警可选优化 | P2 |
| D-05 | ③ 高价值卡结构化（前端） | 补前端闭环（后端已修） | P2 |
| D-06 | ① 兜底可靠可保持 | 确认兜底即可（可选增强） | P2 |
| D-07 | ② 兜底会丢 | **真需修** | P2 |
| D-08 | ① 文档登记（已修） | 已修 | P2 |
| D-09 | ① 兜底可靠（设计行为，非缺陷） | 确认兜底即可；**C810 页级核验已完成（D-11）** | P2/P3 |
| D-10 | ② 兜底会丢（行内 `$` 注释被剥离） | **真需修**（轻量） | P2 |
| D-11 | ① 文档核验（PDF 页级三分定案） | 确认真卡 27 族 / MCNP6 专属 8 族 / 无证据 16 族；供告警/文档/登记 | P2 |
| D-12 | ① 文档登记（PDF-only 词条缺失） | **已登记**（arch，lexicon §1.3.8 D-12 表，20+1 族带 C810 页号；数据流不动） | P2 |
| D-13 | ① 文档复核（词条有但 C810 无） | ACT/BURN/PHYS:H/HE 标 MCNP6 专属；MPHYS/LCA 存疑待复核 | P2 |

**结论（按新标准）**：**真需修 = D-03 / D-07 / D-10（3 条）**；**确认兜底即可 = D-02 / D-04 / D-06 / D-08 / D-09 / D-11 / D-12 / D-13（8 条）**；**高价值卡结构化 = D-05（1 条，前端）**。

---

## 差异条目

| # | 卡名 | 知识库格式 | 当前行为 | 影响 | 建议修法 | 严重度 | 状态 |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| D-01 | **SIn / SPn（独立出现）** | `SI[n] H/L/A/S vals`、`SP[n] D/C/V vals 或 f a b`（源分布卡说明 §三；C810 §3b） | **原缺陷（已修复）**：core.py:1101-1102（旧行号）`elif first.startswith("SI") or first.startswith("SP"): i += 1` → 整行静默丢弃，不进 other_cards、不进任何字段。仅在「紧跟 SDEF」时被 SDEF 分支收集为结构化分布。**修复后（core.py:1124-1134，backend-fb16）**：保底 `result["other_cards"].append(line)`（round-trip 不丢）+ `source_mode=="surface"` 时经 `_merge_sisp_entry` 并入 sdef_distributions 结构化（与 SDEF 分支一致） | 原影响：静默数据丢失。触发：① SSR 面源分布（`SSR … TR D5` 后跟 `SI5 L 4 5`/`SP5 .4 .6`）；② SDEF 与 SI 之间隔 C 注释行 → 后续 SI/SP 全丢。**已修复，无当前影响** | **已实施（backend-fb16，2026-08-13）**：最小修复（append other_cards）+ 增强修复（surface 场景并入 sdef_distributions）均已落地。回归：pytest 293 绿（6 回归用例转绿） | **P0** | **已修**（backend-fb16） |
| D-02 | **计数辅助卡体系无结构化关联**：Cn、DEn/DFn、EMn/TMn/CMn、CFn/SFn、FSn/SDn、FUn、TFn、DDn、DXT、SPDTL（FTn/FQn/FCn 走 `_TALLY_MODIFIER_RE`） | `MCNP6_FN卡结构参考.md` §二 记数卡体系总表；C810 §4b | 全部落入 else 兜底（core.py:1250-1260）或 `_TALLY_MODIFIER_RE`（core.py:845-847, 1226-1229）→ **other_cards 原样保留**。无数据丢失，但与所属 Fn 无结构关联：改 F4 粒子/参数后 FS4/DE4/DF4 仍独立悬挂在 other_cards 文本中 | **结构丢失（P1 定义）**，内容不丢。这些卡**无前端 UI** → 按 PM 分级「可保 other_cards 原样，只要不丢即可」 | ① **登记进 lexicon**（已做，§一 1.3.6）；② 在 `_KNOWN_OTHER_CARDS`/新增 `_TALLY_AUX_RE` 显式登记这批词条，使「已知」语义成立（不警告、防未来误判），但**数据流保持 other_cards 不动**（当前已不丢，勿为结构而改）；③ 未来若某卡需 UI（参照 FMn 先例），再单独加结构化分支 + models 字段。**本轮不施工也成立，仅登记** | P1（结构）/ P2（实务：无 UI 仅保原样） | 待修（登记型） |
| D-03 | **sections.py 分节识别清单缺口**：Cn、DEn/DFn、FSn/SDn、CFn/SFn、EMn/TMn/CMn、TFn/DDn/DXT、SBn/DSn/SCn、ELPT:n、NOTRN、TALNP/MPLOT/RAND/FILES、IDUM/RDUM、FMESHn（带编号） | C810 + FN + 输出卡 + 源分布卡各词条 | `DATA_KEYWORDS`（sections.py:131-138）+ `DATA_PATTERNS`（140-153）未收录上述词条。若这些卡在**节首**出现（phase 仍为 cell/surface，作为首个数据卡触发切换），会被误分到曲面/栅元段（如 `Cn` → surface 文本；`ELPT:N` → 曲面/栅元）。**正常布局无影响**：一旦任意已识别数据卡出现，phase 切 data，后续全部入 data_lines | **边界结构错位（P1 定义）**。官方测试库（1769 样例）中节首直接是辅助卡的文件存在该风险 | 扩展 `DATA_PATTERNS` 补 `(^C\d+$|^DE\d+$|^DF\d+$|^FS\d+$|^SD\d+$|^CF\d+$|^SF\d+$|^EM\d+$|^TM\d+$|^CM\d+$|^TF\d+$|^DD\d+$|^DXT$|^SB\d+$|^DS\d+$|^SC\d+$|^ELPT|^NOTRN$|^TALNP$|^MPLOT$|^RAND$|^FILES$|^IDUM$|^RDUM$|^FMESH)` 等；或把分节识别下沉为 lexicon 单一事实来源的「词条表驱动」（长期机制） | P1（边界）/ P2（常规布局无影响） | 待修 |
| D-04 | **`_KNOWN_OTHER_CARDS` 精确匹配失效**：FMESHn（真卡带编号）、PERTn、PHYS:N/P/E/H/HE（已被前序专门分支拦截） | — | `first in _KNOWN_OTHER_CARDS`（core.py:836-842, 1226）是**精确字符串匹配**：`FMESH4:N`≠`FMESH`、`PERT5`≠`PERT` → 落 else 兜底；`PHYS:N/P/E/H/HE` 被 1060-1100 专门分支先拦截，_KNOWN_OTHER_CARDS 中 PHYS 条目为死代码。**数据均经 else→other_cards 保留，无丢失** | 无数据影响，仅「known」标注失效（这些卡仍会进 other_cards，与未知卡无差别） | 改为前缀/正则匹配（`first.startswith("FMESH")`/`first.startswith("PERT")`）或删死条目；使"已知但无 UI"语义成立（区分于真未知卡，可警示）。**P2 可选** | P2 | 待修（可选） |
| D-05 | **FMn 前端无乘子编辑 UI** | `FMn C m r1 r2…`（C810 §4b） | **后端已全链修（工作树未提交）**：入口门 `^[*+]?FM\d+$`（core.py:1030）+ parse_f_tally FM 分支（723-739，Fn 未先行建占位）+ models.py:200 `TallyDefinition.multiplier` + 生成器回放（inp_generator.py:648-671）+ api 透传（api_server.py:358/480/665）+ 回归测试（test_regress_fm5_import.py 3 用例）。**但 `gui/src/components/TallyTab.tsx` 无 multiplier 输入框**（grep 零命中） | 导入保真已通（FM5 不丢）；用户无法在表单**新增/编辑**计数乘子（只能靠导入+手工其他卡） | api 已带 multiplier 字段 → PM 可派前端在 TallyTab 增「乘子」输入框（每行 TallyDefinition.multiplier），写入 backend 现有 `multiplier` key。**后端零改动** | P1（功能缺口）/ P2（仅保真已达标） | 前端待派 |
| D-06 | **En（n≥1）参数化不解析** | `En … nlog/nlin/nI …`（C810 §9；sample_format.md `E15 0.001 200log 14`） | E0 分支（core.py:1044-1056）解析 parametric → e0_min/max/bins/log；En（n≥1）分支（1171-1185）只收原文进 `e_cards_lines` → parsers/__init__:94-109 关联 tally.generate_en 后原文进 `TallySettings.e_cards_text`。**round-trip 不丢** | 一致性差异（P2）：E15 参数化在 UI 只能按文本展示/编辑（E0 有 min/max/bins/log 结构化） | 可选：En/Tn 复用 `_parse_card_with_continuation` 的 parametric 标记（同 E0/T0），把 nlog/nlin/nI 拆成结构化字段。**P2 增强，不阻塞** | P2 | 待修（可选） |
| D-07 | **SDEF 裸参数（无 = 号）白名单不全** | `SDEF POS 0 0 0`（裸 POS 合法）；标准为 `var=val` | `parse_sdef_simple` 裸分支（core.py:548-569）只处理 `POS`/`PAR`/`SUR`/`NRM`/`TR`/`CCC`/`ARA`/`RATE`；裸 `ERG 14`/`WGT 1`/`CEL 2`/`TME 0`/`EFF 0.5`/`X 5`/`AXS 0 0 1`/`DIR 1` 等 → `ti+=1` 跳过（静默丢值）。`EFF=val` 形式已 → sdef_extra（core.py:424）不丢 | 仅影响非标准裸参数写法；标准 `key=val` 全保留。低风险 P2 | 裸分支白名单补 `ERG/WGT/CEL/TME/EFF/X/Y/Z/RAD/EXT/AXS/VEC/DIR`（复用 `_apply_sdef_param`）。**P2 可选** | P2 | 待修（可选） |
| D-08 | **md 主清单文档缺口**：`C810_卡片格式详细.md` 未收录计数辅助卡 EMn/TMn/CMn/CFn/SFn/FSn/SDn/FUn/TFn/DDn/DXT/SPDTL | `MCNP6_FN卡结构参考.md` §二 已收录（带 PDF 页号 3-104~3-120）；`C810_卡片格式详细.md` 为「卡索引主清单」却缺这批词条 | 主清单不完全 → 未来按主清单开发易漏卡（本轮解析器实测已证明：这批卡落 other_cards 保留，未构成解析差异，仅文档盲区） | 文档缺口（P2，不产生数据丢失） | **本次已补录**：合并 FN 卡 md 词条进 `C810_卡片格式详细.md` §4b + 附录索引（来源标注 FN md，**待 C810.pdf 页级核验**）。复核：FM 卡 md 中已有（§4b:305-312），原失识别在解析器不在 md | P2 | 已修（本次补录，待 PDF 核验） |
| D-09 | **PyMCNP 交叉核对：解析器结构化 + 蒸馏 md 均未收录的 MCNP6 卡**：AWTAB/BBREM/BFLD/BFLCL/COSY/COSYP/DAWWG/DMn/DRXS/DXCn/EMBED 族/FMULT/HISTP/KOPTS/KPERT/KSEN/LCB/LCC/LEA/LEB/MESH/MGOPT/OTFDB/PDn/PIKMT/STOP/THTME/TROPT/TSPLT/URAN/UNC/VAR/WWG/WWGE/WWGT/WWP/WWT/XS/ZA/ZB/ZC/ZD/MXn/AREA（~35 族，详见 lexicon §1.3.8） | PyMCNP `D:\MCNP\PyMCNP\src\pymcnp\inp\`（每卡一类，~230 顶层卡类，`_KEYWORD` 即 mnemonic） | 解析器：全部落 else 兜底（core.py:~1282 起）→ other_cards 原样保留，**无数据丢失**（源码路径验证 DXCn/DMn/EMBED/STOP 等 `_is_zaid_line` 不匹配、续行已 merge，不会误吸收/误分节）；**md 盲区**：app 蒸馏 md 未收录这批词条 | **设计行为（非缺陷）**：未设计卡落其他框=设计好的兜底。残余影响仅① 词条目录不全（文档盲区，开发易漏）；② known/unknown 告警语义（用户不知"原样保留在高级-其他"） | ① 降为**兜底可靠性验证**：抽测代表卡（EMBED 多行 / DXCn 带粒子 / STOP 选项）round-trip 不丢不坏；② **C810 页级核验已完成（tester，见 D-11）**：~35 族三分定案（27 族确认真卡 / 8 族 MCNP6 专属仅提及 / 16 族本 PDF 无证据）；③ 可选：unknown 卡告警提示"未结构化支持、原样保留在高级-其他" | P2/P3 | 兜底可靠；**词条已 PDF 页级核验（D-11）** |
| D-10 | **other_cards 兜底丢行内 `$` 注释**（影响全部未设计卡） | — | `parse_data_cards` 顶部 `line = strip_comment(raw_line.strip())`（core.py:918），other_cards 各 append 点均存 `line`（core.py:1260/1282 等）→ 未设计卡上的行内 `$ 注释` 在解析时被剥离，round-trip 后丢失 | **兜底"不坏但不完整"**：卡的功能数据不丢，但 `$ 注释` 丢（卡行文本非逐字保真）。影响所有走 other_cards 的未设计卡（含 D-02/D-09 全部） | other_cards append 改存 `raw_line`（保留 `$ 注释`）或对已剥离 `$` 作还原；注意与结构化卡（`$` 有 comment 字段）语义区分 | P2 | 待修（轻量） |
| D-11 | **PDF 页级核验新增：C810 结构鉴定 + D-09 候选三分定案** | C810.pdf 实际构成：**MCNP5 卷 I+II 全文**（p78-989）+ MCNP6.1/MCNP5 发布说明（p15-77）+ 附录 + MCNP MANUAL INDEX（p990-1001）。**卡格式权威章 = MCNP5 卷 II Ch.3**（PDF 页 526-691、打印页 3-1~3-166，页眉 "EXPORT CONTROLLED INFORMATION 10/3/05"）；**本 PDF 无 MCNP6.1 手册卷 II Ch.3**（MCNP6 新卡仅发布说明提及，无格式定义）。D-09 ~35 族 PyMCNP 候选三分（全库页级文本检索）：**① 确认真卡（Ch.3 有卡节 / Table 3.11 收录，27 族）**：AREA(3-25)/ESPLT(3-36)/TSPLT(3-38)/PWT(3-40)/EXT(3-41)/VECT(3-42)/FCL(3-43)/WWE(3-45)/WWN(3-45)/WWP(3-46)/WWG(3-48)/WWGE(3-48)/MESH(3-49)/PDn(3-52)/DXCn(3-52)/BBREM(3-53)/VAR(3-35)/URAN(3-32)/SPDTL(3-120)/DRXS(3-125)/TOTNU(3-126)/NONU(3-126)/AWTAB(3-127)/**XSn**(3-127，非 XS)/PIKMT(3-128)/MGOPT(3-129)/THTME(3-137)，另 ZA/ZB/ZC 在 Appendix A/F 承认为"separate cards for inputting user data"（无 Ch3 卡节）、ZD 无；**② MCNP6 专属（发布说明提及、本 PDF 无格式，8 族）**：BFLD(p30)/COSY(p30)/DAWWG(p29)/EMBED 族 8 子卡(p29)/KPERT(p37)/KSEN(p28)/TROPT(p32)/UNC(p31)；**③ 本 PDF 无证据（16 族，不可确认）**：BFLCL/COSYP/DMn/FMULT/HISTP/KOPTS/LCB/LCC/LEA/LEB/OTFDB/STOP/WWGT/WWT/ZD/MXn（PyMCNP 对应类多空 docstring=占位） | 解析器均落 other_cards 兜底无丢失（与 D-09 原判一致，页级核验强化）；文档盲区：① 27 族确认真卡多数未正式登记（→ D-12）；② MCNP6 专属卡无格式源（→ D-13） | ① 确认真卡按 C810 页号登记进 lexicon 正式词条 + 补录 `app/docs/*.md`；② MCNP6 专属卡标注"MCNP6 专属、本 C810 无格式"，格式核验另需 MCNP6 手册卷 II Ch.3；③ 无证据 16 族标注"本 C810 无证据，不可确认"，PyMCNP 占位类不作为权威依据 | P2（文档） | 已核验（2026-08-13 tester） |
| D-12 | **PDF 页级核验新增：C810 Ch.3 真卡但词条目录/解析器结构化均未收录** | AREA/EXT/VECT/PWT(数据卡)/VAR/TSPLT/BBREM/FCL(数据卡)/PDn/DXCn/DRXS/AWTAB/XSn/PIKMT/MGOPT/THTME/URAN/WWG/WWGE/MESH（20 族，C810 打印页号见 D-11 ①） | 解析器：全落 else→other_cards（core.py:~1282 起）无丢失；词条目录正文（§1.1-§1.3.7）未登记这批（部分在 §1.3.8 候选），AREA/EXT/VECT/PWT(数据卡)/VAR/TSPLT/BBREM/FCL(数据卡)/URAN/THTME/PDn/DXCn/DRXS/AWTAB/XSn/PIKMT/MGOPT/WWG/WWGE/MESH 20 族均属"known 失效"（与未知卡无差别） | 文档盲区（P2）+ known/unknown 告警语义失效（用户不知"原样保留在高级-其他"） | ① lexicon 补录为正式词条（来源=C810 页号，本表 D-11 ①）；② 可选：解析器 `_KNOWN_OTHER_CARDS`/DATA_PATTERNS 登记这批（扩 D-03 修法防节首误分）；**数据流保持 other_cards 不动**（当前不丢） | P2 | **已登记**（arch 2026-08-13，lexicon §1.3.8 D-12 表） |
| D-13 | **PDF 页级核验新增：词条目录有但 C810 Ch.3 无（MCNP6 专属或存疑）** | ACT/BURN = MCNP6/MCNPX 专属（发布说明 p35/p33 提及，MCNP5 Ch.3 无）；PHYS:H/PHYS:HE = MCNP6 专属（MCNP5 Ch.3 仅 PHYS:N/P/E）；**MPHYS/LCA = C810 全文 0 出现，PyMCNP 类空 docstring（Lca.py/Mphys.py），疑似占位/非真卡** | 词条仅登记无数据流影响 | MCNP6 专属卡标注来源；MPHYS/LCA 若无法在 MCNP6 手册卷 II Ch.3 找到 → 建议降级移出词条或标"存疑" | ACT/BURN/PHYS:H/HE 标"MCNP6 专属（待 MCNP6 手册核验）"；MPHYS/LCA 标"存疑（C810 无证据）" | P2 | 待复核 |

---

## 已知线索核查结论（PM 指定核对）

| 已知线索 | 核查结论 | 严重度 |
| :-- | :-- | :-- |
| **FM 卡漏识别**（反馈 #1） | **已修（工作树未提交，backend-fb16 在途）**：入口门+parse+model+generator+api+测试全链通；仅前端乘子 UI 缺失（D-05） | 已修（后端） |
| FS/FT/FQ/SD/CF/TF/DE/DF 计数辅助卡 | **均保留不丢**（other_cards verbatim 回放）；仅无结构化关联（D-02） | P2 |
| E4/T4 | **已识别**：e_cards_lines/t_cards_lines 原文保留 + 关联 tally.generate_en/generate_tn | 无差异 |
| 其他潜在漏识别卡 | 独立 SI/SP（D-01，P0）；sections.py 分节边界缺口（D-03，P1） | P0/P1 |

---

## 施工契约（PM 通过后派后端；按设计意图校准后优先级）

| 优先级 | 条目 | 归类 | 动作 | 验收 |
| :-- | :-- | :-- | :-- | :-- |
| **P1** | D-03 | ② 真需修 | sections.py DATA_PATTERNS 补词条（对齐 lexicon 词条表）；保证未设计卡在节首也进 data_lines → other_cards 兜底 | 节首辅助卡 INP 分节正确、round-trip 不丢 |
| P2 | D-07 | ② 真需修 | parse_sdef_simple 裸分支白名单补 `ERG/WGT/CEL/TME/EFF/X/Y/Z/RAD/EXT/AXS/VEC/DIR`，或非白名单裸 token 并入 sdef_extra 保底 | `SDEF ERG 14` 不丢值；全量 pytest 零回归 |
| P2 | D-10 | ② 真需修（轻量） | other_cards append 改存 `raw_line` 保留行内 `$` 注释（与结构化卡 comment 字段语义区分） | 未设计卡 `$ 注释` round-trip 不丢 |
| P2 | D-05 | ③ 高价值卡结构化（前端） | TallyTab 增乘子输入框（后端已全链支持，零后端改动） | vitest 绿 |
| P2 | D-04 | 告警机制（可选） | _KNOWN_OTHER_CARDS 改前缀匹配/删死条目；unknown 卡告警提示"未结构化支持、原样保留在高级-其他" | 无回归 |
| — | D-02 / D-06 / D-08 / D-09 | ① 兜底可靠可保持 | **不改代码**；仅登记（已做）+ 兜底可靠性抽测（D-09 代表卡 EMBED/DXCn/STOP round-trip） | 抽测通过 |
| — | D-11 | ① 文档核验（已完成） | 27 族确认真卡 + 8 族 MCNP6 专属 + 16 族无证据的三分清单落 lexicon §1.3.8（已由 tester 核验，待架构师转登记） | 词条目录标注三分状态 |
| — | D-12 | ① 文档登记 | **已完成（arch 2026-08-13）**：lexicon §1.3.8 D-12 表 20 族 + WWP 按 C810 页号补录为正式词条（数据流保持 other_cards 不动）；`app/docs/*.md` 补录留待后续可选 | 词条目录含 C810 页号；无回归 |
| — | D-13 | ① 文档复核 | ACT/BURN/PHYS:H/HE 标"MCNP6 专属"；MPHYS/LCA 对照 MCNP6 手册卷 II Ch.3 复核（找不到则标存疑/移除） | 词条标注准确 |
| 已修 | D-01 | — | backend-fb16（core.py:1124-1134，pytest 293 绿） | 已达标 |

> 纪律：施工前全量 pytest 基线 **293 绿/0 红** 须保持；禁改断言骗绿；每步全量回归。
