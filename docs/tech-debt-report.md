# 技术债审计报告（PM 汇总）

> 审计发起：项目经理（AgentTeams 团队 `tech-debt-audit`）
> 审计方式：**只读静态审计**（无 shell 工具，未运行 pytest / vitest / tsc / vite build / 打包）
> 审计范围：`app/`、`gui/src/`、`gui/backend/`、`gui/test/`、`tests/`、`inputcard_mcp/`、`docs/`、`PROJECT_MEMORY.md`、`.git`（只读）、部署目录 `D:\MCNP\MCNP输入卡生成器`（只读）
> 状态：**审计阶段已完成并冻结**（t1 记忆债 **23 条**、t2 后端债 **25 条 + 3 相邻**（BE-06 已自行撤回）、t3 前端债 **25 条**；t4 交叉验证定稿 **v1.4**，合并总表 **34 条**）
>
> 🚧 **修复阶段已开始（2026-09-10）**：修复内容与**验证命令清单**见 **`docs/fix-verification.md`**；本批修复台账见 `PROJECT_MEMORY.md` 顶部「S1（当前批次）技术债修复」。
> ⚠️ **§7 的"未验证清单"在修复阶段依然成立**：修复同样是**无 shell** 条件下做的（静态编写 + 静态自检），**未跑过任何测试/构建**。

---

## 0.0 用户已决策事项（2026-09-10）

| 事项 | 用户决策 | 对本次交付的含义 |
| :--- | :--- | :--- |
| **范围与时间** | **今晚只做审计，不做修复**；门禁执行与打包部署"明晚/明天再说" | 本报告定位为**可执行修复工单的前置依据**；本批**未改任何源码**（仅新增 `docs/tech-debt-report.md` 与 `docs/audit/*.md` 审计文档） |
| **Q10 栅元「外无限」语义** | 原话：「外无限是允许存在的，仅提示感叹号即可，唯有曲面不封闭是禁止的」 | 三档语义确定：**封闭=正常** / **外无限=允许 + 感叹号级提示（非红色错误）** / **曲面不封闭=禁止级错误**。据此 `CellEditDialog.tsx:50-58` 的"外无限=红色错误"映射属待清理的第三份实现，应以深模块 `cellClosure.ts` 的 `allowed:true` 为准并统一为"感叹号" |

---

## 0.1 审计方法与口径（PM 设定）

| 项 | 约定 |
| :--- | :--- |
| 证据要求 | 每条债必须能定位到 `file:line` / reflog 行号 / 部署目录实测；禁止编造运行结果 |
| 定级 | P0=红线违规或用户可见静默错/数据丢失/发布链路断裂；P1=边界错误或有兜底、契约漂移、关键路径无测试、环境类致验证不可信；P2=深模块 ADR 违背/死代码/文档滞后/未提交未打包散落改动；P3=风格措辞 |
| 升降级 | 有实测证据升一级；有兜底+回归测试降一级；证据不足标「待验证」，**不参与 P0 定级** |
| 去重 | 同根因跨清单合并为一条，取最高严重度；分类固定五类：记忆·文档债 / 后端代码债 / 前端代码债 / 跨端契约债 / 门禁与流程债 |
| 「未提交/未打包散落改动」专项 | 基准 **P1**（交付链路断裂 + `c3e5c43` 复发先例 + main 单分支无备份）；例外降 P2：门禁已绿**且**已登记在 PROJECT_MEMORY 短期记忆（有台账）。新增「台账：有/无」列作为判据 |
| 边界纪律 | 严守 §5 依赖红线（禁 npm/pip install）、§6 5001 端口劫持（不起/不杀服务）、§9 测试硬性超时；本次全员未跑测试，故凡需运行才能定论者一律标「待验证」 |

**已知方法论局限（必须写进结论）**：本次为纯静态审计。**「测试门禁是否真绿」「是否有隐藏 skip」这类问题无法在本次审计中定论**，只能给出静态推断与验证方式。

---

## 1. PM 侧独立复核证据（不依赖成员结论，可单独引用）

### 1.1 交付链路断裂（最硬的一条）

| 事实 | 证据 |
| :--- | :--- |
| 源码 HEAD = SDEF 源粒子演示批次 | `.git/refs/heads/main` = `4f0798fa880eac85dedb7a210e677f32bf3418ad`；`.git/logs/HEAD:281` = `feat(source-demo): SDEF 源粒子演示可视化（TODO #6）` |
| 用户实际部署版 = 1.7.5 | `D:\MCNP\MCNP输入卡生成器\README.md:25` 徽章 `Version-1.7.5` |
| 部署包里有该批次之前的模块 | `_internal\app\generator\distributions.py` 存在（源分布 v2 批次） |
| 部署包里**没有**该批次新增模块 | `_internal\app\generator\source_sampler.py` **不存在** |
| 排除"打包形态"解释 | `gui/mcnp_sidecar.spec:31` `_keep_dirs = ["generator", ...]` → `app/generator/*.py` 作为源文件整目录打进包，缺文件 = 未进构建 |

**结论**：`4f0798fa` 的 SDEF 演示功能已实现、已提交，但**未打包给用户**；用户装的 1.7.5 里没有这个功能。源码里已实现的功能对用户等于不存在。

### 1.2 记忆与真实 git 历史严重脱节

`PROJECT_MEMORY.md` 完全未登记、但 reflog 实证存在的提交（节选，`.git/logs/HEAD`）：

| reflog 行 | 提交摘要 |
| :--- | :--- |
| `:251` | `chore(release): bump version to 1.7.5` |
| `:262` | MCP 增加「当前工作区」会话 + MCP over HTTP（/workspace + /mcp） |
| `:265` | 主程序启动时自动拉起 MCP over HTTP（--mcp-http → 8100） |
| `:267` | **移除 stdio 旧接入（注册MCP.bat / --mcp-server），统一 MCP over HTTP** |
| `:268`–`:270` | AI 接入面板自配置提示词 / 回显投影 adv / 精简源类型模板 |
| `:272` | 源项 adv 权威化 + 主窗口等比缩放深模块（sourceAdv / useDeckSynced / appScale） |
| `:273` | 独立窗口闪主界面 + 免安装版 FreeCAD 空预览 |
| `:275` | 参数扫描改造（免正则选中即参数 / 多核并行 / 彩色行标记 + misc prior uncommitted work） |
| `:277`–`:280` | 语法规则补全 + 栅元封闭性自检（closed/infinite/empty）+ 深模块 useCellClosure / cellClosure |
| `:281` | SDEF 源粒子演示可视化（TODO #6，HEAD） |

### 1.3 版本号三处不一致

实际 **1.7.5**：`gui/package.json:4`、`gui/src-tauri/tauri.conf.json:10`、`gui/src-tauri/Cargo.toml:3`、`README.md:25`。
记忆侧：`PROJECT_MEMORY.md:296` §1 写 **1.7.2**；短期记忆多处写 **1.7.4**；**全文零处提及 1.7.5**。

### 1.4 幽灵 CLI 参数（按官方文档操作会起错进程）

- `gui/backend/mcnp_bridge.py:14-17` docstring 仍宣传 `--mcp-server`（stdio MCP）
- 实际分派只有 `--meshtal-worker`(:41) / `--ptrac-worker`(:47) / `--mcp-http`(:53)，**无 `--mcp-server` 分支**
- 后果：`python.exe --mcp-server` 会**落到 `api_server.main()`(:60-61)** → 起第二个 5001 后端，撞 §6 端口劫持老坑
- 同类过期文档：`docs/手动打包方法.md:149-151` 仍在教 stdio 用法；`docs/inputcard-mcp.md:68` 写 HTTP、`:137,140` 又写 stdio（同文件自相矛盾）；`PROJECT_MEMORY.md:46,52,356` 同样过期

### 1.5 契约文档悬空引用

`MCNP输入卡生成器_功能待办清单.md:8` 与 `docs/contracts/validator-crosscheck.md:39` 都引用 `docs/contracts/watertight-check.md`，**该文件不存在**（功能本身在：`app/freecad_preview.py:374` 起 `check_watertight`、`gui/src/components/CellEditDialog.tsx:156` 几何自检）。

### 1.6 待办清单状态与事实相反

`MCNP输入卡生成器_功能待办清单.md:50-53` 第 11 项「2D 结果导出增强（切面 PNG/SVG + CSV）」标 ❌未做；实际 `gui/src/volume/sliceExport.ts` + `gui/src/volume/SliceExportPanel.tsx` 已落地（2026-09-04 批次）。

### 1.7 PM 抽验成员 P1 指控（验收前置）

| 指控 | PM 复核结论 | 复核证据 |
| :--- | :--- | :--- |
| FE-03 `Preview3DLattice.tsx` 为死模块 | **成立** | 全 `gui/` 树 grep `Preview3DLattice` 仅 3 处命中，全部在该文件自身（:2,:48,:176），**零 import** |
| FE-08 测试文件不在 tsc 覆盖内 | **成立** | `gui/tsconfig.json:21-23` `include: ["src"]`；测试目录 `gui/test/` 未纳入 |

### 1.8 待补 P0 候选（来自成员，PM 待验收）

- **M-01 版本身份漂移**（t1，P0）：记忆 1.7.2~1.7.4 vs 实际 1.7.5；AI/新人按记忆判断发布状态必然出错。
- **FE-01 / FE-02 跨语言 golden「双端锁死」名不符实**（t3，P1→**是否升 P0 待 reviewer 裁决**）：`gui/test/latticeInstances.test.ts:370-414` 的 `expandPositionsRef()` 是同文件手写的 Python `expand_positions` TS 重抄，断言只比对「TS 重抄 ↔ golden」，golden 内无后端原始产出字段；`:421-428` 的 `hasGolden` 守卫读的又是被测对象自己 → 两侧同时漂移可静默通过，键名变更可静默 skip 而门禁仍显示 0 failed。
  - 附带风险（t1 独立发现）：`/api/check-cell-closure` 在 `tests/` **零匹配** → 封闭性功能无测试、无契约。

### 1.9 记忆·文档债（t1 交付摘要 v2，明细见 `docs/audit/t1-memory-debt.md`）

共 **17 条（P0 5 / P1 10 / P2 2）**——v2 为并入 PM 注入证据后的交叉核实版（v1 为 14 条）。

**P0 五条**

| ID | 债项 | 证据 |
| :--- | :--- | :--- |
| M-01 | 版本身份漂移：记忆写 1.7.2~1.7.4，实际 **1.7.5**；记忆全文零处提 1.7.5（§8 里程碑表停在 v1.7.4，无 1.7.5 行） | `PROJECT_MEMORY.md:296,:309,:431,:276,:483-484` vs `gui/package.json:4`、`tauri.conf.json:10`、`Cargo.toml:3`、`Cargo.lock:1642`、`README.md:25`；reflog:251 `bump version to 1.7.5`。**注**：§9「版本发布纪律」(:528-532) 本身不含版本号，不能算"停在 1.7.4"；真正陈旧的是 §9 门禁表 :521-524 与 §5:431 例句 |
| M-02 | §2 状态快照滞后 3 个版本：称"已交付 v1.7.2；#7 重合检查待排期"，实际 #7 于 2026-08-22 交付、v1.7.3/1.7.4/1.7.5 均已发布部署 | `PROJECT_MEMORY.md:309` vs `docs/CHANGELOG.md:65`、`docs/contracts/api.yaml:1379` |
| M-03 | 数量与门禁基线失真：写 api.yaml 30 端点 / pytest 573 / vitest 358，实测 **49 端点**、同文件自记 pytest **765**、vitest 587~554 | `PROJECT_MEMORY.md:389,:394,:521-524` + 自相矛盾处 `:55,:40,:52` |
| M-04 | 工作区记录失真：S2 称"未提交仅批量编辑 5 文件"、S3 称"全部改动未 commit"，实际 08-22~09-10 约 100 条提交、HEAD 已到 09-10 | `PROJECT_MEMORY.md:272-275,:281-284` vs `.git/logs/HEAD`（09-09 有 `…+ misc prior uncommitted work` 后紧跟 reset → 分布 v2 是否被夹带提交**待 git show 复核**） |
| **M-16** | **记忆外的会话改动（本次最严重）**：HTTP 化之后的 AI 改动 + 封闭性/校验规则/参数扫描改造/源项 adv+appScale **约 20 条提交零记忆、零契约、零 §3 锚点** | grep `PROJECT_MEMORY.md` 对 `8100\|mcp-http\|自配置\|注册MCP\|AI 接入面板\|多核\|免安装\|闪主界面\|源类型模板\|等比缩放\|appScale\|sourceAdv\|useDeckSynced\|彩色行标记\|封闭\|closur` **全部零命中**（仅命中无关的 `mcnp_workspace_v1`:371 与"水密自检":25）；对应 reflog `:251,:259-:275,:277-:280` |

**P1 十条**：M-05 记忆把 MCP 写成 stdio `--mcp-server` 且"6 工具/10 工具"自相矛盾（实际 `mcnp_bridge.py:53-57` 仅 `--mcp-http`）｜M-06 `docs/inputcard-mcp.md` 同文档内 stdio 与 HTTP 两套说法并存｜M-07 `docs/手动打包方法.md` 仍称"当前 v1.7.2/最新 v1.7.4"并教 stdio｜M-08 `docs/CHANGELOG.md` 归档断层（缺 v1.7.4 / 材料库 / 09-04 三批 / 09-09 六批 / 09-10 源演示，基线沿革停在 528/327）｜M-09 `backend-changes.md`/`frontend-changes.md` 均止于 08-30，其后 6 批无条目｜M-10 `app/UI_ARCHITECTURE.md` 通篇陈旧（"25 端点"、§5.2 行号表全错、§7 终态仍写 pytest 251 绿）｜M-11 契约状态位陈旧（`lattice-coverage-check.md:3` 标"待确认"但已实现；`geometry-check.md:3,:221` 标"本轮不施工"但已交付；`meshtal-visualization.md:4` 标"不施工"但 v1.7.0 已交付）｜**M-12（v2 由 P2 上调 P1）** 待办清单与 `validator-crosscheck.md:37-41` **两处**引用不存在的 `docs/contracts/watertight-check.md`（功能确在：`app/freecad_preview.py:374/:389/:403/:405`、`:450` 回参；`CellEditDialog.tsx:80` 调 `/api/check-cell-closure`、`:156-163`「🩺 自检此栅元」）｜**M-15（新增）** 交付状态记载自相矛盾：`PROJECT_MEMORY.md:3` 写"已实现待提交"、`:17` 却写"本次提交"（PM 已实证该批**已提交** `4f0798fa`）｜**M-17（新增）** 待办清单第 11 项标 ❌未做，实际 `sliceExport.ts`/`SliceExportPanel.tsx` 已落地（reflog:246 `f7fc2ed` 已提交）。

**P2 二条**：M-13 待办清单编号与记忆 `:83` 引用的"P1#5"悬空，根目录 `功能待办清单.md`/`AI接入.md` 未登记进 §3｜M-14 §3 只给测试总数不给结构；`grep tests/` 对 `cell-closure` **零匹配** → 新端点无回归测试（转 t4 定级）。

**t1 负面结论（勿再排期）**：`api.yaml` ↔ `api_server.py` 静态集合一致（49/49，**无漂移**）；`release.bat`/`scripts/release.ps1` 已彻底删除，与记忆一致；`AI接入.md` 与 source-demo 契约口径与实现一致。

### 1.10 前端代码债（t3 交付摘要 v2，明细见 `docs/audit/t3-frontend-debt.md`）

共 **25 条（P0 0 / P1 11 / P2 9 / P3 5）**——v2 为并入 PM 注入证据后的复核版（v1 为 20 条）。
> **口径钉子（两处已知不一致，以本行/本表为准）**：① t3 冻结文件 `:53/:144/:154` 的计数行仍写 `P1 12`，与其总数 25 不自洽（12+9+5=26）——PM 按其 20 条主表 + 5 条衍生逐项重算，**权威分解 = P1 11**（主表 8 + FE-21/21b/21c 三条），t3 的最终对齐编辑未改该行，故不以其计数行为准；② t3 文件 §8.6 的「hex pitch **8 处**」含 2 处误报（`api_server.py:554-564` 实为 `_clip_suffix_and_lines` 拼 rpp 文本、`:884-895` 实为 `_lattice_container_bound` 曲面号扫描），**权威口径 = t2 的 BE-21 附表（7 处）**，t3 已在 §8.6 加注"计数与定级以 BE-21 附表为准"。

**v2 新增 4 条（打开被点名文件后发现，比"无测试"更重）**

| ID | 债项 | 关键证据 | PM 复核 |
| :--- | :--- | :--- | :--- |
| **FE-21c** | **封闭性自检指纹只比长度 → 同长度编辑静默判为"未变化"**：指纹 = `surfaces.length : JSON.stringify(cells).length : tr_cards.length`，命中即早退；`useCallback` deps 为 `[report]` 却读 `fpRef.current` | `gui/src/utils/useCellClosure.ts:37-43`（指纹）、`:56`（早退）、`:76`（deps） | **PM 已独立复核成立**（实读源码逐行确认）。例：材料号 `1`→`2` 长度不变 → 永不重发，永远显示旧报告 |
| FE-21b | 第三份状态→展示映射已与深模块分歧：同一 `infinite` 状态一处红 `#e53935`、一处琥珀 `#f9a825`；语义相反（模块 `allowed:true`＝外无限合法，旧对话框渲染成红色错误）；且旧对话框仍自建 `/api/check-cell-closure` 请求，**深模块抽取没收敛旧实现** | `CellEditDialog.tsx:50-58`（映射）、`:80-94`（自建请求） vs `cellClosure.ts:41-48` | 待 Q10 产品裁决 |
| FE-21a | 死导出：`cellClosure.ts:56-62` `getClosureStatus` 全仓只命中定义处，同函数体被 `useCellClosure.ts:79` 内联重写 | `cellClosure.ts:56-62`、`useCellClosure.ts:79` | — |
| 无测试补强 | 4 个模块无测试**成立且已定位间接覆盖边界**：`useDeckSynced`/`useAppScale` 有"不抛错"级间接覆盖；`useCellClosure` 的 refresh/缓存路径**完全没执行**（`geometryBatchEditReorder.dom.test.tsx:48-52` 的 fetch mock 让 `/api/check-cell-closure` 走 error 分支 → `report` 恒 null → `GeometryTab.tsx:302` 提前 return）；`cellClosure.closureMeta` **零覆盖** | 见左列 file:line | 已给 18 个应补用例名（分 4 个测试文件） |

> **注意**：FE-21c 按 reviewer 定级口径属「用户可见错误结果 + 无告警无兜底」＝**P0 候选**（t3 自评 P1）。PM 已把它挂入 t4 仲裁，**不预先拔高**。

**v1 已交付的 P1 八条**

| ID | 债项 | 关键证据 |
| :--- | :--- | :--- |
| FE-01 | 跨语言 golden「双端锁死」名不符实：断言实为「同文件手写 Python 重抄 ↔ golden」，golden 无后端原始产出字段 | `gui/test/latticeInstances.test.ts:370-414`（`expandPositionsRef`）、断言在 `:429` |
| FE-02 | 自指 skip 守卫：`hasGolden` 读被测对象自己，条件不满足即静默 skip 而门禁仍 0 failed | `gui/test/latticeInstances.test.ts:421-428` |
| FE-03 | 479 行死模块：全仓零 import（Preview3D 已内联装配） | `gui/src/components/Preview3DLattice.tsx:1-479`（**PM 已独立复核成立**） |
| FE-04 | 同名重复实现（运行期隐患）：`backend.ts` 的 `generateInp` 无人用，失败时返回 `"// Python backend not connected"` 注释串而非报错，并读陈旧 `output.inp`；在用的是 `dataCollector.generateInp` | `gui/src/utils/backend.ts:74-95`（**PM 已独立复核成立**：`:83` 静默 catch、`:92` 读陈旧文件、`:94` 返回注释串） |
| FE-07 | 代码与注释矛盾：`hexCenter` 代码是新权威公式，docstring 仍写旧公式（差 30° 旋转） | `gui/src/utils/lattice.ts:123-137`、`docs/frontend-changes.md:11,208`、`lattice.test.ts:131` |
| FE-08 | 门禁盲区：**82 个测试文件不在 tsc 内**，且无 typecheck 脚本 → 记忆多轮"tsc EXIT 0"覆盖不到测试 | `gui/tsconfig.json:21-23`（**PM 已独立复核成立**） |
| FE-09 | flaky 计时断言反模式（单采样/无 warmup/无分位数，前置 O(n) 填 16.7M 字节） | `gui/test/volume/colorize.test.ts:145`（`dt<50`，t0 在 `:141`） |
| FE-13 | 双 `CellData` 类型债：`DeckContext`(snake_case) vs `CellEditDialog`(camelCase) 两套同名接口，桥接靠注释纪律；已现 `impN \|\| imp_n` 防御性双读 | `gui/src/utils/DeckContext.tsx:12`、`CellEditDialog.tsx:6-27`、`GeometryTab.tsx:48`、`Preview3D.tsx:600-602,894-896` |

其余：FE-05 `UNIVERSE_PALETTE_12` 仅测试引用、FE-06 `estimateLatticeExtent` 仅测试引用且 hex 分支写死 `pitch=1`、FE-10 `SourceDemoRenderer`/`SourceTab` 零测试、FE-11/FE-12 窗口路由闸门可能"空对空假绿"且无"新增窗口必须登记"的断言、FE-14 src 214 处 `any` / test 57 处、FE-15 日志守卫仅覆盖单文件、FE-17 `subPitch` 兜底 `1.26` 三处硬编码、FE-18 兼容层退场版本未记录、FE-20 11 处 `golden.xxx as any[]` 关掉 golden 段名编译期校验。

另新增跨端项：**封闭性状态词表双实现无锁**（TS `cellClosure.ts:15` 的 6 个状态值逐字复刻 Python `_freecad_csg_worker.py:1137/1140/1148/1157/1169/1171`，今天一致但无任何机制锁住；`gui/test/**` 对 `closureMeta|check-cell-closure|closure_report` 零命中）→ 建议照 `latticeGolden` 先例增 `closureGolden.json` 并把枚举写进 api.yaml。

> **口径精确化（t3 v2 复核后更正，明晚派单照此写）**：`api.yaml:1452` 的 **summary 散文里已列举** 6 状态，但响应 schema `:1484` 只有 `status: {type: string}` → **枚举只在散文里、不在 schema 里**；且漂移闸门做的是 handlers↔api.yaml 的 **AST 存在性**双向校验，**结构上校验不到 enum**。故**只补 `enum` 是"文档装饰"**，必须**同时**给闸门加一条"响应 `status` 必须落在 enum 内"的 HTTP 用例。另：封闭性判定**依赖 bound**（`_freecad_csg_worker.py:1122-1175` 的 tol = B×0.005，按 AABB 触及包围盒轴数定性：3 轴=`infinite`、1~2 轴=`semi_infinite`、0 轴=`closed`）→ 同一 cell 在不同 bound 下可能从 `closed` 变 `semi_infinite`，**测试断言必须按"给定 bound 下的期望"写**。

**t3 负面结论（勿再报）**：模块级缓存 + `useMemo` 冻结**已清偿**（`useMaterialLibrary.ts:60-61` 有防回归注释，全仓无第二处）；`dbgLog` 已删、`TODO/FIXME/XXX/HACK` **零命中**；`windowRouteConsistency` 的 5 个窗口 label 逐一核对同值，**覆盖完整**；`console.log` 仅 6 处且全在 `backend.ts`；`mcpProcess`（`backend.ts:6,14`）经 PM 复核**不是** stdio 遗留（它启动的是 `--mcp-http`），勿误报。

### 1.14 PM 新增决定性证据：PyInstaller 构建 TOC（成员均未使用，可静态判定"打包版哪些模块能 import"）

**证据源**：本机最后一次构建产物 `gui/build/mcnp_sidecar/{PYZ-00.toc, COLLECT-00.toc}`（纯文本，可 grep）。

| 事实 | 证据 |
| :--- | :--- |
| PYZ 内**只有 dotted 名** `app.lattice`，**无顶层 `lattice`** | `PYZ-00.toc:782` `('app.lattice', 'D:\\…\\app\\lattice.py', 'PYMODULE')` |
| 对照：能被子进程/动态 import 命中的是**顶层名** | `analytic_slice`（`PYZ-00.toc:638`）、`voxel_csg`（`:12682`）均为顶层条目 |
| 打进包的 app 源文件只有 3 个（`_keep_py` 成员） | `COLLECT-00.toc:3960` `coverage_check.py`、`:4034` `gpu_pref.py`、`:4035` `material_library.py`；**无 `lattice.py`、无 `diff_inp.py`** |
| 加载机制取顶层名 | `api_server._import_app()`（`:27-36`）用 `__import__(module)`；`_keep_py` 文件靠 `mcnp_bridge.py:27` 把 `_internal/app` 加入 `sys.path` 后以**顶层名**导入 |
| 静态边只产生 dotted 名 | `app/generator/inp_generator.py:9`、`app/generator/parsers/core.py:18` 均为 `from app import lattice` → 注册的是 `app.lattice`，**不等于**顶层 `lattice` |

**PM 静态推论**：打包版 `/api/lattice-extent`、`/api/preview-lattice`、`/api/validate-lattice-surfaces`、`/api/validate-universe-coverage`（lattice 部分）与 `/api/diff-inp` 会 ImportError → 500。

⚠️ **必须标注的矛盾（不得据此定 P0）**：`PROJECT_MEMORY.md:122` 记载部署版冒烟时 `preview-lattice` 返回过 `universes STL keys=['1','2','3']`、`subPitch=1.45034`，与上述推论**冲突**。可能原因：① 那次冒烟实际走的是源码后端；② 当时的构建与本次 TOC 快照不同；③ 静态推论有漏洞（frozen importer 对 dotted 名可能另有回退）。
→ **归入"待实机验证"，不参与 P0 定级**。最小验证方式：起部署版 sidecar，对 `/api/lattice-extent`、`/api/diff-inp` 各发一次请求看是否 500（**先确认 5001 未被旧进程占用**，见 §6 端口劫持坑）。
→ 无论谁对，**廉价且安全的处置一致**：把 `_import_app()` 的全部目标模块补进 `spec._keep_py`，并加一条 `test_sidecar_spec_keep.py` 做 handler↔spec 双向集合断言（消除"人工核对 spec"这唯一防线）。

### 1.15 需实机验证才能定论的项（本次静态审计无法闭环）

- vitest 实际 skipped 计数（FE-01/FE-02 是否已造成静默 skip）
- `colorize.test.ts:145` 真实失败率与阈值是否合理（FE-09）
- 真实 deck 下 `subPitch` 兜底命中率（FE-17）
- 工作区是否有未提交改动（无 shell，仅能由 reflog 推断，M-04 的"分布 v2 是否被夹带进无关主题提交"**需 `git show` 复核**）

### 1.12 后端代码债（t2 交付摘要，明细见 `docs/audit/t2-backend-debt.md`）

共 **25 条 + 3 条相邻发现（P0 3 / P1 7 / P2 12 / P3 3）**，另 10 条存疑待实机验证。三条 P0 全部经 PM 抽验；**BE-06 已由 t2 自行撤回（v7，只减不增）**：

| ID | 债项 | 关键证据 | PM 复核 |
| :--- | :--- | :--- | :--- |
| **D-BE-01** | **假 STEP 端点**：`generate_step(surfaces_data)` 完全忽略入参，只写死 `#1=MANIFOLD_SOLID_BREP("MCNP Geometry")` 就返回；handler 却回 `ok + "STEP 文件已生成"`，且该端点仍活跃注册在 `api.yaml:657-687` | `gui/backend/generate_step.py:5-17`（`:26` 甚至传空列表）、`:27` | **PM 已复核成立**（实读源码：函数体与入参零关联，输出为常量占位符） |
| **D-BE-02** | **DS 解析/抽样键错配 → 真实数据上 DS 依赖链静默退化**：`_parse_ds` 只产 `distributionIds`（无 `values`），而 `_resolve_ds` 的 **Q/L/H/T 分支全读 `values`** → 恒空 → 一律 return `{"default": True}`；前端 `DsEntry` 同样只有 `{type,param,distributionIds}`。单测之所以绿，是因为它**手写**了代码库里**没有任何生产者会产出**的 `ds:{"type":"L","values":[...]}` 形状 | `app/generator/distributions.py:97,105`（生产者）vs `:675,713`（消费者）；`gui/src/utils/DeckContext.tsx:33`、`DistributionEditor.tsx:287-292`；假绿测试 `tests/unit/test_distribution_sampler.py:126,132,138,144` | **PM 已复核成立并加重**：仅 DS **S** 分支可用（走 `distributionIds`）；Q/L/H/T 在真实导入 INP 与 UI 两条路径上均静默退化。**直接违背 PROJECT_MEMORY S1「有错就地报、不降级不近似」决议**。⚠️ 影响面限定：该功能（SDEF 演示）**尚未打包**，故当前对用户无实害，属"打包前必须修"的发布阻断项 |
| **D-BE-05** | **spec `_keep_py` 无自动闸门**：`analytic_slice.py`、`diff_inp.py` 未进 `_keep_py`/`_keep_dirs` → 打包版 `/api/cross-section` 解析切片分支与 `/api/diff-inp` **必 import 失败**（dev 模式因 `APP_DIR` 直入 `sys.path` 永不复现）。同类 bug 已复发两次（`material_library` / `gpu_pref`），如今只剩"人工核对 spec"这道防线 | `gui/mcnp_sidecar.spec:17-31,55-56`；先例见 `PROJECT_MEMORY.md:150` | **待实机验证**（打包版必 500 属静态推断）；处置建议：加 `test_sidecar_spec_keep.py` 做 handler↔spec 双向集合断言 |

**其他值得注意的 P1**

| ID | 债项 | 证据 |
| :--- | :--- | :--- |
| D-BE-03（幽灵参数，PM 已复核） | 三个 `if` 均不命中时 fallthrough 到 `import api_server; api_server.main()` → `python.exe --mcp-server` 实际**起第二个绑 0.0.0.0:5001 的后端进程**（不是 MCP），正好踩 §6 端口劫持入口；而 `docs/手动打包方法.md:149-151` 正在教用户这么用 | `gui/backend/mcnp_bridge.py:14-17,41,47,53,60-61` |
| D-BE-04（僵尸字段） | `sdef_raw_text` 对新导入 INP **恒 `""`**（`parsers/core.py:1154-1155` 只写 `sdef_distributions`），唯一"活"的原因是 `tests/unit/test_generator_sdef.py:104-106` 手写它覆盖生成器兜底分支；全链路仍有 4 处读点 + `api.yaml:2244/2289` + `contract.ts:44` | 同上；处置需决策：保留+一次性迁移，或设退役条件后删 7 处读点 |
| ~~D-BE-06（数据丢失）~~ **已撤回** | ~~MCP `patch_section` 丢 U 分组头注释~~ → **主机制不成立**：t3 给逐行反证、t2 复核后**自行撤回整条**（`inputcard_mcp/server.py:101` 的 `return deck_from_json(d)` 传整个 sections dict，`api_server.py:1347-1348` **恰好读** `universe_comments`，`server.py:83` 亦回写） | 残余（reviewer 保留为 **TD-15 / P2**）：`patch_section` 整份重写抹掉**非 deck 键**（如 `rawOverrides`）+ `_ws_state()` 死函数且 docstring 不符 |
| D-BE-07（并发竞态） | `api_server` 是 `ThreadingHTTPServer`（`:15`），但 `_STL_SESSION` 模块级 dict 逐请求重绑定 + 预览路径"先删上一会话目录再建新会话"（`:2751-2752`），`PreviewCache._index/_order` 无锁 → 并发预览/截面会互删目录 | 同上 |
| D-BE-09 | `_SI_LETTERS` 的 Q/T/F/V 确认为多余（与 PM 记忆 C810 结论一致）→ 这些 SI 类型只在**抽样时**才炸，生成/往返看不出来（错误被推迟到运行期） | `app/generator/distributions.py` `_SI_LETTERS` |
| D-BE-12 | `_handle_parse_inp`（`:2039-2092`）与 `_deck_to_frontend_dict`（`:1352-1391`）是两份**已分叉**的序列化实现——MCP `/workspace` 用的那份少 11 行前端中间态字段 | 同上 |
| 测试文档债扩大 | "当前应为 RED"的过期 docstring 不止 `test_tech_debt.py`，另有 **14 处**：`test_roundtrip.py:40/51/58/66/168/253`、`test_sample_smoke.py:87/100`、`docs/backend-changes.md:44-52`，而对应 F-A~F-D / F#3 / F#7 均已清偿 | 同上 |

**t2 负面结论（勿再报）**：`_keep_py` 的 `material_library`/`gpu_pref` 已补；`inp_generator.py` 顶层 `pymcnp` import 是**刻意的 fail-fast 约定**（F#7 已绿，**勿再当启动慢根因**）；`raw_overrides` 8 处守卫已收敛；`preview_cache` 的 LRU/`evict_dir`/`meta.json` 恢复完好；`_SURF_CLASSES_LOCK` 双检锁正确；sweep 预算/清理/无命令注入面；meshtal/ptrac worker 顶层只 stdlib（有 AST 断言守卫）；跨语言 golden 抽查 3 处一致。

### 1.13 t2 建议的一条实机验证命令（给有 shell 的执行者）

```
pytest tests/integration/test_tech_debt.py tests/integration/test_roundtrip.py tests/integration/test_sample_smoke.py -q
```

⚠️ **跑前先确认 5001 未被旧 sidecar 占用**（§6 端口劫持坑：旧进程会让新端点静默 404/500 且 traceback 行号对不上）。

---

## 2. 成员清单（口径已冻结，以 `docs/audit/*.md` 文件为唯一权威）

> ⚠️ 上文字段中的 t1/t2/t3 摘要对应各成员的早期快照（t1 v2 / t3 v1 / t2 v3）。**冻结口径如下，若数字冲突以本表与 `docs/audit/*.md` 为准**（任务 output 因平台 2000 字符截断已过期，勿引用）。

| 来源 | 冻结条数 | 分级 | 落盘位置 | 状态 |
| :--- | :--- | :--- | :--- | :--- |
| t1（researcher） | **23 条** | P0 5 / P1 13 / P2 5 | `docs/audit/t1-memory-debt.md` | ✅ 已落盘 v5 |
| t2（engineer-backend） | **25 条 + 3 相邻** | **P0 2 / P1 8** / P2 12 / P3 3 | `docs/audit/t2-backend-debt.md` | ✅ 已落盘 v8（BE-06 撤回；**BE-01 由 P0 降 P1**——按 t4 判准"零调用方 ⇒ 用户无可见错误"） |
| t3（engineer-frontend） | **25 条** | P0 0 / P1 11 / P2 9 / P3 5 | `docs/audit/t3-frontend-debt.md` | ✅ 已落盘 v5（含 FE-22） |
| t4（reviewer） | 合并去重后总表 | 待定 | `docs/audit/t4-consolidated.md` | 🔄 进行中（口径冻结后收口） |
| **合计（去重前）** | **73 条** | P0 8 / P1 31 / P2 26 / P3 8 | — | （+ t2 的 3 条相邻发现；BE-06 撤回后 26→25） |

**已知同根因（t4 合并，勿重复计条）**：t2 的 BE-14 ≡ t3 的 FE-07 ≡ t1 的 M-21（hexCenter 旧公式残留，researcher 清点到 **16 处**含 `lattice-fix15-design.md:450` 的 L1 锁死表）；t2 的 TRCL 归一化项与死模块 `Preview3DLattice.tsx` 同批可关。
> ⚠️ **派单提醒（t3 复核后最有价值的一条）**：这 16 处里 **`docs/contracts/lattice-fix15-design.md:450` 的 L1 锁死表写的也是错公式** —— 注释漂移只误导人，**契约锁死表漂移会污染跨语言实现**。故该条修复 **Owner 必须含架构师**（改 L1 锁死表），不能只派前端改注释。
> **三端去重表（t3 产出，已对齐）**：hexCenter 旧公式 = FE-07 + M-21 + BE-14 → 合并 1 条、三端 Owner（含架构师改 L1 表）｜`Preview3DLattice` 死码 = FE-03 + M-22 → 合并 1 条、双 Owner（删文件 + 清文档）｜`estimateLatticeExtent` 死导出 = FE-06 + M-23 → 合并 1 条｜TRCL 口径 = FE-22(A) + t2 相邻发现(P3) → 合并 1 条（**前端侧随 FE-03 删除即消除**）｜测试文件数/门禁数字 = 纯记忆侧 M-20。

**成员已自我更正（勿沿用旧数字）**：
- 测试文件数 = **75 个 `*.test.ts(x)` + 1 个 `.snap`**（t3 报的"81"不成立且自身不自洽）
- t2 撤回"`analytic_slice.py`/`stl_cross_section.py` 漏 spec"的误报（二者本就在 `_keep_py`）→ **真实动态 import 漏项只剩 `app/diff_inp.py`**（`api_server.py:1756`）
- t1 修正 PM 的两处初判：① 记忆外零记录的是"HTTP 化之后的 AI 改动 + 封闭性/校验规则/参数扫描改造/源项 adv+appScale"（stdio 时代在 S1 有记录）；② §9 版本发布纪律段本身不含版本号，陈旧的是 §8 里程碑表与 §9 门禁表

---

## 3. PM 验收结论（对 t4 定稿的独立验收）

**验收动作**：PM 独立抽验了 t4 最关键的一条反证——**TD-06「跨语言锁是否真实存在」**（reviewer 据此推翻 t3 的 FE-01 主要指控）。
**抽验结果：反证成立。** `tests/unit/test_lattice.py:668-689` 确实用**真实 Python `expand_positions`**（`:683`）逐位断言 `latticeGolden.json` 的 `expected`（`:685-689`），故「TS 重抄 ↔ golden ↔ 真实 Python」三步锁**真实存在**；同时 reviewer 保留的两类静默失效也成立（`:679` 的 `continue` 静默跳过 hex 样本、`:670-675` 段缺失即 `pytest.skip`）。

**验收结论：通过。** 理由：
1. 定级口径与 PM 批准版一致，且**拒绝为凑数拔高**（P0 计数从成员合计 8 降到 0 条已证实，另列 2 条 P0 候选并写明升级条件）。
2. **推翻成员原判 10 处**，每处都给了理由与复核范围（`analytic_slice` 半条不成立、BE-06 主机制不成立、FE-01 部分不成立、FE-17 活路径不成立等）——这正是要 reviewer 做的事，**没有做背书式复述**。
3. 严重度与「是否阻塞发布」**分开写**，使 P0=0 不导致急迫性丢失（TD-02/TD-03 仍标"阻塞发布=是"）。
4. 独立新发现 1 条（**TD-31**：`docs/contracts/source-demo-visualization.md:25` 的 `resolve_ds(eid, parent_value) -> list[int]` 与实际签名 `resolve_ds(self, eid, parent_value, parent_si=None) -> dict` **不符**）。
5. 「我未能验证的部分」8 条写实，明确标注不可引用——符合本次"静态审计"的性质。

**PM 补充确认的一条口径**：reviewer 对 **TD-02** 的保留是对的。PM 另提供了成员均未使用的决定性证据（§1.14 的 PyInstaller TOC：`PYZ-00.toc:782` 只有 `app.lattice` 无顶层 `lattice`；`COLLECT-00.toc` 无 `lattice.py`/`diff_inp.py`），静态链条**强指向**打包版 500，但与记忆 `:122` 的"部署版冒烟 preview-lattice 通过"矛盾 → **维持"待 runtime 定论"**，不升 P0。

**PM 复核更正的一处数字（不影响任何定级）**：测试文件数曾出现 74/75/81/82 四个版本。PM 用确定性 glob 定案：`gui/test/**` = **60 个 `*.test.ts` + 15 个 `*.test.tsx` = 75 个测试文件**（另 1 个 `.snap`）→ **researcher 的"75 + 1"正确，t3 报的"81"偏高**，本报告与 t4 的 TD-17 里出现的"82"同源应读作 **75**。**TD-17 的实质结论不变**（`gui/tsconfig.json:21-23` 只 include `src`，这 75 个测试文件均不在 tsc 覆盖内）。

---

## 4. 最终技术债口径（冻结）

> **冻结后成员回执的数字/方向更正（仅影响数字与描述，不影响任何定级；明晚派单请以此为准）**
>
> | 项 | 更正后 | 说明 |
> | :--- | :--- | :--- |
> | 测试文件数 | **75 个**（60 `.test.ts` + 15 `.test.tsx`）+ 1 `.snap` | 原文出现的 81/82 读作 75 |
> | hex pitch 副本数 | **7 处**（非 8 处）：换算实现 5（`lattice.py:915-929`、`lattice.py:1037-1041`、`api_server.py:734-743`、`lattice.ts:452-468`、`latticeInstances.ts:384-389`）+ TS 测试消费点 1 + TRCL 定位入口 1 | t2 复核：t3 另点的 `api_server.py:563-566`/`:891-894` **无** hex pitch 换算，勿写 8 处去找不存在的第 8 个实现 |
> | `estimateLatticeExtent` 的 `pitch = 1` | **有意为之**（`lattice.ts:440` docstring 自述"阶段2 用单位 pitch≈1"），**不算缺陷** | 仍在表内但降级为说明项 |
> | `subPitch` 1.26 三处 | 正确理由＝**后端无条件下发**（`api_server.py:3426-3431`）故前端两处 `?? 1.26` 永不执行；**不是**"lattices 为空时不进 disc"（那是消费侧判断） | TD-28 处置不变：后端无格阵时下发 `null` + 前端集中一处兜底，让兜底变活路径 |
> | TRCL 归一化 | **后端不存在"归一化 bug"，只是"不归一化"**（`_cell_trcl_deg` 由旋转矩阵 `atan2` 反解、无 mod）；归一化逻辑只在前端 fallback | 处置是"统一到哪一侧"的产品决策，**不是"给后端加 mod"**；若删前端 fallback，**必须把"`trclRotationDeg` 必下发"写进契约**，否则将来漏发会静默变 0 |
> | BE-26 方向 | **宽的是 `/api/parse-inp`**（从 `asdict(deck)` 起手不删键 + `_warnings:2091`），**窄的是 `_deck_to_frontend_dict`**（MCP `/workspace` 那份） | 与 t3 原表述相反，修哪一侧以此为准 |
> | **TD-02 收窄**（t4 v1.1） | **确认漏项只有 `diff_inp.py`**；`analytic_slice.py`/`stl_cross_section.py` 本就在 `_keep_py:19/:28`（**勿派单去改**）；`lattice.py` 是唯一争议项，**待 runtime** | 止血项只补 `diff_inp.py` + **三向**断言闸门（handlers ↔ spec ↔ 静态 import 图）；定级依据改为「白名单手写 + 零自动闸门 + 历史已复发两次」，而非"当前漏了 N 个" |
> | **TD-03 扩大**（t4 v1.1，**影响最大**） | `_parse_ds:104-105` 把 `toks[0]` 塞进 `param`，而 `app/docs/源分布卡说明.md:175` 的 `DSn S S1…Sk` **无独立 param 字段** ⇒ J 列表**整体右移**（`DS1 S 2 3` 的索引 0 取到分布 **3**，应为 2），且与该分支**自身单测契约**（`test_distribution_sampler.py:119-122`）矛盾 ⇒ **"只有 S 分支可用"的三方共同假设不成立，S 同样待修** | TD-03 处置定为三步：**键口径 + `param`/J 起点按 C810 裁定 + 真实解析路径回归**；**只改读键修不好 S**，Q2 派单必须写明 |
> | **`pos_index` 一条被驳回**（t4 v1.1） | t2 称 `source_sampler` 的 `pos_index` 不可达、需补接线 → **不成立**：`source_sampler.py:67-68` 已 `pos, pos_index = self._position(rng)` → `self._erg(rng, pos_index)`，`_sample_pos_dist:216-228` 返回真实索引 | **明晚不派"接 pos_index"**（避免往发布阻断清单加无效返工） |
> | **BE-01 判准**（PM 裁定） | 采纳 reviewer 判准「用户是否被误导 / 是否有用户可见错误」⇒ 零调用方 ⇒ **P1，不阻塞发布** | TD-04 按**方案②删端点**（含 api.yaml + `spec:40`）派单——假功能靠"删"而不是靠"提级"解决 |
> | **BE-06 撤回**（t2 v7，只减不增） | t2 自行撤回整条：`inputcard_mcp/server.py:101` 的 `return deck_from_json(d)` 传整个 sections dict（`:92-100` 只做 `advanced→adv` 改名与 None 归一，不删键），`api_server.py:1347-1348` 恰好读 `universe_comments` ⇒ **U 分组注释不丢** | 残余保留为 **TD-15（P2）**：`patch_section` 整份重写抹掉非 deck 键 + `_ws_state()` 死函数。**t2 的条数 26→25，P1 8→7**；t2 另附「错误成因自查」（判字段是否透传必须跟到返回值/参数绑定处） |

| 项 | 值 |
| :--- | :--- |
| 合并后债条 | **32 条**（由成员原始 68 条去重合并而来） |
| **P0（已证实）** | **0 条** |
| **P0 候选** | **2 条**：TD-02（打包版 `lattice`/`diff_inp` 动态导入缺口，待 runtime，**阻塞发布=是**）、TD-03（DS 键错配，**打包即 P0**，**阻塞发布=是**） |
| P1 | **23 条** |
| P2 | **9 条**（另含若干 P2 级子项） |
| P3 | 子项级（死符号、fmesh 死分支、1.26 不可达防御等） |
| 分类 | 记忆·文档债 / 后端代码债 / 前端代码债 / 跨端契约债 / 门禁与流程债（五类固定） |

**明细权威文件**：`docs/audit/t4-consolidated.md`（定稿总表 + 10 条改判理由 + 4 条必裁决结论 + 未验证清单）。

---

## 5. 处置批次建议（明晚可直接照单派单）

> 原则：**先止血（不依赖 runtime、不碰业务逻辑）→ 再解发布阻断 → 再修闸门可信度 → 再补记忆文档 → 最后清代码债**。

**批次 0 · 第一件事（实测，1 条命令）**：起/复用 5001 对安装版 sidecar 打只读请求验证 TD-02——
`POST /api/lattice-extent`、`POST /api/diff-inp`（**先 `netstat -ano | findstr :5001` 确认占用者**，见 §6 端口劫持坑）。**500 即升 P0 + 阻塞发布**。

| 批次 | 内容 | 债ID | 是否依赖 runtime | 建议 Owner |
| :--- | :--- | :--- | :--- | :--- |
| **止损三件套**（当天可完） | ① `spec._keep_py` 补 `lattice.py`/`diff_inp.py` + 新增 `test_sidecar_spec_keep.py` 双向集合断言；② `mcnp_bridge.py` 显式 `--mcp-server` 分支 `sys.exit(2)`（**绝不 fallthrough**）+ 清 5 处过期文档；③ `tsconfig.test.json` + `typecheck` 脚本（零新依赖） | TD-02 / TD-05 / TD-17 | 否 | engineer-backend + engineer-frontend |
| **发布阻断**（随下次打包） | DS 键错配（**必须补走真实解析路径的回归**：`parse_distribution_lines(["DS1 Q 2 5 3 10 4"])` → sampler）+ `pos_index` 接线 | TD-03 | 否 | engineer-backend + tester |
| **闸门可信度** | 硬断言 `expect(hasGolden).toBe(true)` + skipped>0 视为失败；清 14 处"当前应为 RED"反向 docstring；`colorize` 时间断言移出货门禁（删"已知 flaky"豁免）；封闭性 enum 进 `api.yaml` 并加 HTTP 用例 | TD-06 / TD-09 / TD-18 / TD-08 | 部分 | tester + engineer-frontend + engineer-backend |
| **记忆与文档** | 补 20 条零登记提交 → 版本/基线口径改 1.7.5 → 契约状态位与 `watertight-check.md` → CHANGELOG 断档 6 批 → 工作区状态重写 + 两条纪律 | TD-12 / TD-10 / TD-14 / TD-13 / TD-11 | 否 | PM + 架构师 |
| **代码债清偿** | 删死代码（`Preview3DLattice.tsx` 479 行、`backend.ts` 同名 `generateInp`、两个死导出）→ 僵尸字段退役三段式 → `_SI_LETTERS` 收紧 → 序列化合并 → 孤立并发竞态 → 死符号/静默失败/pitch 8 副本/注释漂移/测试缺口/契约签名 | TD-16 / TD-23 / TD-24 / TD-22 / TD-20 / TD-15 / TD-19 / TD-25~TD-31 | 部分 | 前后端 + tester |
| **随 Q10 落地** | 统一三处 `infinite` 映射（含让 `CellEditDialog` 改走 `useCellClosure`，收敛第三份实现与自建请求） | TD-32 | 否 | engineer-frontend |

**建议同时固化的两条纪律**（治本）：① 批次结束必记 **commit 短号 / 待提交文件清单**（治 TD-11/TD-12）；② 记忆必须写明 **「已提交 commit / 已打包版本 / 部署校验」三态**（治 TD-01/TD-15）。

---

## 6. 待您裁决（t4 提出 5 项，PM 给出推荐）

| # | 问题 | 方案 | PM 推荐 |
| :--- | :--- | :--- | :--- |
| Q1 | 是否现在实测安装版 sidecar 的 `lattice`/`diff-inp` | A 实测（能一次定论，但需处理 5001 占用、可能结束您正在用的后端）；B 不实测，直接补 spec + 把两端点冒烟写进发布检查单 | **B**（补 spec 本身零风险），但**发布检查单必须固化这两个端点冒烟**——同类缺口已复发两次（`material_library`/`gpu_pref`） |
| Q2 | DS 键错配修法 | A 修解析侧 `_parse_ds` 另填 `values` + 真路径回归；B 只收敛读侧改读 `distributionIds` + 不支持形态就地报错 | **A 为主 + B 兜底**（A 与 C810 语义一致；无论选哪个**必须补真路径回归**，否则假绿测试继续锁 bug） |
| Q3 | 跨语言锁加固范围 | A 只加硬断言 + skipped 入闸门（半天）；B 另补 `expected_python` + 收敛 8 处 hex pitch 副本 | **A 立即 + B 单独派工**（B 不做，下次改 pitch 仍能绕过锁） |
| Q4 | 是否采纳 reviewer 的 10 条改判 | A 采纳（P0 由 6→0，急迫性由"阻塞发布"列保住）；B 保留成员原判（同一债两个级别并存） | **A**（与"不拔高"口径一致；成员原判会制造两套口径） |
| Q5 | 处置批次 | A 先止血三件套 → 记忆文档 → 代码债；B 先重打包发布（用户最快拿到 TODO #6，但把 TD-02 未知风险带进发布） | **A，再评估 B** |
| ~~Q10~~ | `infinite` 展示语义 | — | **已由您裁决**：「外无限允许存在，仅提示感叹号；唯有曲面不封闭是禁止」→ 落地方案为"允许 + 感叹号级提示（非红色）"，并统一三处映射 |

---

## 7. 未验证清单（**必读：不得当作结论引用**）

本次审计**全程静态、零实机执行**（PM 与 4 名成员**均无 shell 工具**），以下问题**无法定论**：

1. **门禁是否真绿、是否含未察觉 skip**（TD-06 升级为 P0 的前提）、`colorize` 真实失败率（TD-18）、14 处 docstring 对应用例真实红绿（TD-09）。
2. **打包版运行时表现**：`python.exe` 内 PYZ 无法静态读取 → TD-02 的 ImportError 未定论（§1.14 只给静态链条）。
3. **当前工作区真实未提交状态**（无 `git status`/`diff`）；`+ misc prior uncommitted work` 后紧跟 `reset` 的"改动被夹带"疑点保留。
4. **部署版构建时点**：只能证明早于 `4f0798fa`，无法证明是否含 09-09 批次 → TD-07 的"已发货性"未定。
5. **未逐条打开 file:line 的条目**：TD-13、TD-19、TD-20、TD-25、TD-26、TD-27、TD-30 及 TD-08 部分子项（不用于 P0 定级）。
6. **未访问 `D:\MCNP\MCNP6\C810.pdf`**：凡以该 PDF 为据的语义结论（SI 只有 H/L/A/S、DS 卡形态）本次只核到"与记忆/代码自述一致"，**不是"与 PDF 一致"**。

---

## 8. 交付物清单

| 文件 | 内容 | 作者 |
| :--- | :--- | :--- |
| `docs/tech-debt-report.md` | 本报告：方法口径 + PM 独立复核证据 + 成员摘要 + 验收结论 + 口径冻结 + 处置批次 + 待裁决 + 未验证清单 | PM |
| `docs/audit/t1-memory-debt.md` | 记忆·文档债 23 条（P0 5 / P1 13 / P2 5）+ 已清偿 8 条 + 存疑 + 证据类型标注 | researcher |
| `docs/audit/t2-backend-debt.md` | 后端代码债 26 条 + 3 相邻发现（P0 3 / P1 8 / P2 12 / P3 3）+ 已清偿 11 条 + 存疑 10 条 | engineer-backend |
| `docs/audit/t3-frontend-debt.md` | 前端代码债 25 条（P0 0 / P1 11 / P2 9 / P3 5）+ 已清偿 10 条 + 存疑 9 项 | engineer-frontend |
| `docs/audit/t4-consolidated.md` | **定稿总表 32 条** + 10 条改判（含理由）+ 4 条必裁决结论 + Q1~Q10 + 未验证 8 条 + 处置顺序 | reviewer |

> **本次审计未修改任何代码、未运行任何测试/构建/打包、未安装任何依赖、未起停任何服务**。
> 新增文件仅：本报告 + `docs/audit/` 下 4 份成员审计文档。
> 最后更新：2026-09-10（审计阶段完成）
