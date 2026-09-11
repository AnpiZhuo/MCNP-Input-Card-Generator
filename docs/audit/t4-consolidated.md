# T4 交叉验证 + 去重 + 严重度定级（汇总裁决稿）

> 任务：`tech-debt-audit` / t4 —— 对 t1 / t2 / t3 三份清单做**独立交叉验证、去重合并、统一定级**，并产出待 PM / 用户裁决问题。
> 审计人：**reviewer**（AgentTeams 成员）｜日期：**2026-09-10**
> 输入（**已冻结，以文件为准**）：`docs/audit/t1-memory-debt.md`（**23 条 M-01…M-23**，v5 含 §6 跨报告交叉核对 / §7 引用版 / §8 已清偿 / §9 证据类型）、`docs/audit/t2-backend-debt.md`（**主表 26 行 BE-01…BE-26 + 3 条相邻发现**；⚠️ 其中 **BE-06 已由 t2 于 §5.1 自行撤回** ⇒ **有效 25 条**，t2 §5.3 亦自记 25 条）、`docs/audit/t3-frontend-debt.md`（**24 条** FE-01…FE-22，v2 含第八节跨组回执）、`docs/tech-debt-report.md`（PM 汇总，仅作起点）。
> **v1.1（同日）**：并入 engineer-backend 的 §四 回执 —— 采纳其 2 处自我更正、**驳回其 1 处「新发现」**、并新增 1 条我方发现（`_parse_ds` 的 `param` 偏移）。**v1.2（同日）**：并入 researcher v5 的 M-18…M-23 与 §6.3/§6.4/§9 提示 —— 新增 1 条（M-20）、3 条按同根因并入既有行；**并就 t1 §8 的一处结论提出异议**。**v1.3（同日）**：并入 **PM 提供的 PyInstaller 构建 TOC 证据**（我已独立复核，见 §8.8）+ **用户已裁决的 Q10**（§0.1）；新增 TD-34。**v1.4（同日，PM 冻结收口）**：并入 t2 v8 的 **BE-26**（→ TD-22）与 **BE-06 撤回**（→ TD-15 收窄）、hex pitch 副本计数对齐（→ TD-28）；**本版为定稿**。详见 **§8 修订记录**。
> **冻结口径（PM 下达）**：三份清单不再变更（t1 23 / t2 26 行（撤回 1 条，有效 25）/ t3 24）；**本 t4 总表为 34 行**，是跨三份清单 + PM 证据去重合并后的最终账目。
> 性质：**全程只读**。未运行 pytest / vitest / tsc / vite build / 打包；未装依赖；未起停任何服务；本会话**无 shell 工具**。除本文件外未修改任何文件。

---

## 0. 范围与时间（**用户已定，先读**）

- **今晚只做审计，不做修复**（用户原话："今晚先只做审计，不做修复"）⇒ 本报告**不含任何修复补丁**，也**不建议今晚改代码**；门禁执行、打包部署一并推到明晚/明天再议。
- 因此本报告定位是「**可执行修复工单的前置依据**」：每条 P0/P1 均给出「**最小验证方式 + 建议处置 + 依赖顺序**」，目标 = **明晚可直接照单派单**（见 §7）。

### 0.1 用户已裁决事项（**已定，不再列为待裁决**）

**Q10 栅元「外无限（infinite）」展示语义** —— 用户原话：

> 「外无限是允许存在的，仅提示感叹号即可，唯有曲面不封闭是禁止的」

⇒ **三档语义（已定）**：**① 封闭 = 正常**；**② 外无限 = 允许存在，展示"感叹号"级提示（不是红色错误）**；**③ 曲面不封闭 = 禁止 / 错误级**。

**据此裁决 FE-21b（TD-32）**：**以深模块语义为准** —— `gui/src/utils/cellClosure.ts:41-48` 的 `allowed:true`（允许）是**正确的一方**；`gui/src/components/CellEditDialog.tsx:50-58` 把 `infinite` 渲染成**红色错误态 `#e53935`** 属**待清理的第三份映射**（与用户裁决直接冲突）。处置：三处映射统一为「封闭=正常 / 外无限=允许+**感叹号** / 不封闭=错误」，并让 `CellEditDialog` 改走 `useCellClosure`（收敛第三份实现）。**本项无需再裁决。**

---

## 0.2 独立结论：**本次审计是否发现 P0？**

> 本结论为 reviewer 独立判断，**不跟随任何成员的既有定级**。

**答：未发现「已证实」的 P0（0 条成立）。** 有 **2 条 P0 候选**，均因**证据不足（需 runtime）或影响面不在已交付版本**而不予定级，按 PM 口径标「待验证 / 发布阻断」：

| P0 候选 | 为什么**不判 P0** | 什么条件下会变成 P0 |
| :--- | :--- | :--- |
| **TD-02** 打包版 `lattice.py` / `diff_inp.py` 动态导入缺口（t2 判 P0、t1 判 P1） | 静态证据现有**三条独立链条、方向一致**：① spec `_keep_py` 未列；② 部署全树 2301 条路径 `lattice`/`diff_inp` **零命中**；③ **PM 提供的构建 TOC 经我独立复核**（`PYZ-00.toc:782` 只有**点号名** `app.lattice`、**无顶层** `lattice`，而 `analytic_slice`(:638)/`voxel_csg`(:12682)/`mc`(:3512)/`models`(:3839) 都是顶层名；`COLLECT-00.toc` 无 `app\lattice.py`/`app\diff_inp.py`）⇒ 静态强指向打包版这两个端点必 500。**仍不判 P0**：冻结环境的运行期行为不能静态证成；且记忆 `:138` 记过一次"部署版 sidecar 直跑 `preview-lattice` 通过"的**反证**（我复核后认为其**对应更早的 v1.7.4 构建**、不是当前部署的 1.7.5，故**不直接反驳**本链条 —— 详见 §8.8）。**v1.1 收窄**：`diff_inp.py` 是**纯动态 import、无静态边**，这半条最硬；`lattice.py` 曾是争议项，**TOC 证据支持我方判断**（该边只注册 `app.lattice`）。 | 一条只读 HTTP 调用（见 §5-Q1）证实 500 → **立即升 P0 + 阻塞发布**（用户安装版功能不可用） |
| **TD-03** DS 解析/抽样键错配（t2 判 P0） | 证据**成立且我已逐行复核**，但影响面**限定在尚未打包的 SDEF 演示功能**：对当前用户**零实害** | 该功能一旦打包（下一次发布）→ **即成 P0**。故本次按「**P1 + 发布阻断项**」处理，不预先拔高 |

**同时，我改判了成员原判 10 处**（见 §3「改判清单」）：`M-01/02/03`、`M-04`、`M-16`（P0 → P1）、`BE-01`（P0 → P1）、`BE-02`（P0 → **P1 + 发布阻断**）、`BE-05`（P0，**半条不成立** → P1）、`BE-06`（P1 → P2，**主机制不成立**）、`FE-07`（P1 → P2）、`FE-17` 的 1.26 活路径（P2 → P3，**不可达防御**）、`FE-01`（"名不符实"**部分不成立**，维持 P1）。

**为什么整体没有 P0**：按 PM 批准的口径，P0 需命中「§5 红线违规 / 门禁或构建通过不了 / 用户可见错误结果且无提示无兜底 / 数据丢失 / 发布链路断裂导致发旧代码」。逐类核对：版本五处一致（1.7.5）**无红线违规**；无证据表明门禁/构建当前是红的（未跑，属「待验证」）；已交付版本里**没有一条被我证实**的用户可见静默错；DS 静默退化与封闭性陈旧报告都在**未打包功能/辅助提示**范围内（分别 P1 + 发布阻断、P1）。**不把 P1 拔高**正是本次审计对 5001 劫持、colorize flaky 这类历史「测试假象」的防误伤要求。

---

## 1. 定级口径（PM 已批准 + 一处修订，t4 据此重排全表）

### 1.1 五级判据

| 级别 | 判据（满足任一） |
| :--- | :--- |
| **P0** | ① 违反 §5 硬规则（bug 批乱升版 / 未批准新依赖 / 自动装包）；② 门禁或构建**当前即红**；③ **用户可见的错误结果且无提示无兜底**（静默错，如生成 INP 与原生不一致）；④ **数据丢失**（保存/导入丢内容）；⑤ **发布链路断裂**导致用户拿到旧代码或不可用功能 |
| **P1** | ① 错误结果但**限于边界条件**或**已有告警/兜底**；② 契约漂移（handlers ↔ `api.yaml`，或契约与实现签名不符且闸门校验不到）；③ **关键路径无测试**致回归不可发现（含「测试守卫静默失效」）；④ 环境类（5001 劫持 / 打包时效 / spec 缺项）使**验证结论不可信或发布物残缺**；⑤ **误导后续开发**（记忆/文档/契约把已交付写未交付、把假实现写可用、把红灯写绿灯） |
| **P2** | 可维护性：违反 §4 深模块 ADR 的重复/浅模块/超大文件；死代码；**注释与代码不符**（行为正确）；非关键路径测试缺口；无退场计划的兼容层 |
| **P3** | 命名/注释/风格/措辞/可选优化；不可达的防御代码 |

### 1.2 升降级规则

- **有实测证据**（命令输出/日志/HTTP 响应）相对纯代码阅读 **升一级**；本次**全员无 shell**，故**没有任何条目获得这一升级**。
- **已有兜底 + 回归测试** → **降一级**。
- **证据不足** → 标「**待验证**」，**不参与 P0 定级**（防误伤）。
- **不成立/部分不成立** → 不以原定级参与全表，取复核后结论（见 §2）。

### 1.3 「未提交 / 未打包散落改动」专项（PM 修订）

- 基准 **P1**：理由 ① 用户用的是**打包部署版**（源码里已实现未打包 = 对用户不存在，属交付链路断裂）；② `c3e5c43` 已因「会话外改动未提交」专门清偿过 14 项 → **复发型风险**；③ 单机单分支 `main`、无备份冗余，丢失不可恢复。
- **例外降 P2**：该改动**门禁已绿** **且** 已登记在 `PROJECT_MEMORY` 短期记忆（**有台账**、可知可控）。
- **无台账 / 未登记**的未提交（或未登记）改动 **一律 P1**。
- 总表因此新增 **「台账(有/无)」** 列，并**只对该类条目**生效；非交付状态类条目填「—」。判据链：**无台账 → P1；有台账且门禁绿 → P2；有台账但门禁未绿 → 不降级（P1）**。

### 1.4 去重口径

- **同根因跨 t1/t2/t3 合并为一条，取最高严重度**，来源全部保留在「来源」列。
- 分类固定五类：**记忆·文档债 / 后端代码债 / 前端代码债 / 跨端契约债 / 门禁与流程债**。
- 每条必带：债ID、类别、来源、位置、**证据复核结论**、影响、严重度、**最小验证方式**、建议处置、Owner、台账、**是否阻塞发布**。
- 「是否阻塞发布」与「严重度」**分开写**：严重度=当下危害；阻塞发布=下一次打包前是否必修。

### 1.5 复核结论列取值

`成立` = 我亲自 read/grep 打开 file:line 核实；`部分成立` = 核心机制部分对、部分错（写明哪半错）；`不成立` = 机制错（写明正确机制）；`未复核` = 我未独立打开核对（倚成员 file:line 证据，**不用于 P0 定级**）；`待验证` = 静态无法定论，需运行。

### 1.6 本次复核覆盖面（实测）

我对 4 条必裁决项 + 抽验 P0/P1 共 **20 项**亲自打开核对（t1 抽 4：M-01/M-03/M-18/M-19；t2 抽 10：BE-01/02/04/05/06/09/10/11/12/21；t3 抽 6：FE-01/02/03/04/08/21c），其中 **4 项判不成立或部分不成立**（BE-05、BE-06、FE-01、FE-17 的活路径部分）。其余条目按 §1.5 标「未复核」。

---

## 2. 合并去重后的技术债总表（34 条）

> 来源编号：`M-xx`=t1、`BE-xx`=t2、`FE-xx`=t3（含 t3 §8 的 v2 修正）、`PM`=PM 报告、`RV`=reviewer 本次新发现。

| 债ID | 类别 | 来源 | 位置（file:line） | 证据复核结论 | 影响 | 严重度 | 最小验证方式 | 建议处置 | Owner | 台账 | 阻塞发布 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TD-01** | 门禁与流程债 | M-18 + M-15 + PM§1.1 | 源码 `app/generator/source_sampler.py`（存在）vs 部署 `_internal\app\generator\`（**无此文件**）；`PROJECT_MEMORY.md:3` vs `:17`/`:31` | **成立**（我复核：源码 `app/generator/` 7 文件含 `source_sampler.py`；部署同目录 6 文件无它；部署全树 2301 条路径中 `source_sampler` **零命中**；部署 `README.md` 徽章 1.7.5） | 用户安装版 1.7.5 **没有** TODO #6 演示源功能（前端入口/后端端点/采样器全缺）；记忆「已实现待提交」与「本次提交」同文件自相矛盾 | **P2**（按 §1.3：**有台账**（S1 明写"未打包、未升版"+门禁绿 49 passed）→ 降 P2；**若用户已对外声称该功能可用 → 按 P0 处理**） | 对比 `glob D:/MCNP/MCNP输入卡生成器/**/source_sampler.py`（现为零命中） | 记三态：「已提交 4f0798fa / 已打包 1.7.5（不含）/ 部署校验」；下次发布连带 TD-02 + TD-03 | 构建 Owner + PM | **有** | 否（下次发布必然连带） |
| **TD-02** | 门禁与流程债 | BE-05 + M-19（**合并**；**v1.1 按 t2 §4.4 回执修正**） | `gui/mcnp_sidecar.spec:17-31`（`_keep_py` 25 项，含 **`analytic_slice.py`:19** 与 **`stl_cross_section.py`:28**；`_keep_dirs`:31 = generator/docs/meshtal/ptrac）；`gui/backend/api_server.py:27-36`（`_import_app` = `__import__(module)`）、`:1756`（`diff_inp`，**纯动态、无静态边**）、`:1793/:2965/:2984/:3013/:3217`（`lattice`） | **部分成立（v1.1 收窄）**：**不成立半条**——`analytic_slice.py`（`:19`）**与 `stl_cross_section.py`（`:28`）都在 `_keep_py` 内**，且我已在部署目录见到 `analytic_slice.py`；"不在 `_keep_py` ≠ 打包版用不到"（覆盖来源有三：`_keep_py` / `_keep_dirs` / **PyInstaller 静态 import 图**）。**成立半条**：`app/diff_inp.py` 是**纯动态 import、无任何静态 import 边** ⇒ 打包版 `/api/diff-inp` 必 `ImportError` 500 的**静态链条最硬**。**争议项（唯一不确定处）**：`lattice.py` 也不在 `_keep_py`，t2 §4.4 主张它靠 `inp_generator.py:9`/`parsers/core.py:18` 的 `from app import lattice` 静态边进了图因而可用；**我持保留**——该边注册的模块名是 **`app.lattice`**，而 `_import_app("lattice")` 取的是**顶层名 `lattice`**，两者在 PYZ 里不是同一个 toc 条目；且部署全树 2301 条路径 `lattice` **零命中** ⇒ **只能 runtime 定论**。**v1.3 追加（PM 提供的构建产物证据，我已独立复核，见 §8.8）**：本机最后一次构建的 TOC 显示 `PYZ-00.toc:782` 只有 `app.lattice`（**点号名**）而无顶层 `lattice`，`COLLECT-00.toc` 的 app 源文件里**没有** `lattice.py`/`diff_inp.py`（有的是 `analytic_slice.py:3957`、`coverage_check.py:3960`、`gpu_pref.py:4034`、`material_library.py:4035`、`mc.py:4038`、`sweep.py:4100`、`voxel_csg.py:4101`）⇒ **t2 §4.4「静态边使它可用」的主张被 TOC 证伪**（该边只产生 dotted 名，而 `__import__("lattice")` 取顶层名） | 若成立：打包版 `/api/diff-inp`（及可能的 `/api/lattice-*`、`/api/preview-lattice`、`/api/check-overlap` 的 pin-fit 分支）**必 500**（dev 模式因 `PROJECT_DIR`/`APP_DIR` 进 `sys.path` 永不复现）。**张力**：与用户已复验格阵 3D 预览存在矛盾 → 需 runtime 定论 | **P1**（**证实即 P0**；v1.1 采纳 t2 的定级**依据**修正：本债的根本不是"当前漏了 3 个"，而是「**白名单手写 + 零自动闸门 + 历史上已复发两次**」（`PROJECT_MEMORY.md:97` 记 `material_library` / `gpu_pref` 曾漏）——`diff_inp.py` 只是当前那一例） | **明晚第一件事（PM 指定）**：① 先 `netstat -ano \| findstr :5001` / `Get-NetTCPConnection -LocalPort 5001` 确认 5001 **未被旧进程占用**（§6 劫持坑：旧 sidecar 会让"新端点 500"混入假象）；② 直跑**部署版 sidecar** 起后端（`D:\MCNP\MCNP输入卡生成器\python.exe`，或按现状复用已在跑的后端）；③ 对 `/api/lattice-extent`、`/api/preview-lattice`、`/api/diff-inp`（外加 `/api/validate-lattice-surfaces`）**各发一次只读请求**，记录 **HTTP 状态码 + 响应体**（预期：若为 `500`/`status:error` 且 message 含 `No module named 'lattice'` → **升 P0**）；④ 对照 `_internal\app\` 文件清单 | **先修 spec 再打包**（补 `diff_inp.py`；`lattice.py` 视 runtime 结果一并补），并加 `test_sidecar_spec_keep.py` 做 handlers↔spec↔静态 import 图**三向**集合断言——几十行闸门一劳永逸堵该类 500 | engineer-backend + tester | — | **是** |
| **TD-03** | 后端代码债 | BE-02（PM 复核成立） | `app/generator/distributions.py:97,104-105`（产 `distributionIds`）vs `:675,676-683,684-691,692-707,710-718`（读 `values`）；`gui/src/utils/DeckContext.tsx:33`；`tests/unit/test_distribution_sampler.py:120-146` | **成立**（我逐行复核 5 个分支：**T** `:673-674` 立即 default；**Q** `:676-683` 读 `values`；**S** `:684-691` 读 `distributionIds`；**L** `:692-696` 与 **H/""** `:697-707` 读 `values`；`vals = ds.get("values") or []` 在 `:675`。生产者 `_parse_ds:97/104-105` **从不写 `values`** ⇒ **Q/L/H/T 恒 default**（S 可用）。4 个单测（`:126/132/138/144`）**手写**代码库无任何生产者会产出的形状 → "绿"是假的。**v1.1 追加我方发现的更深一层**：`_parse_ds:104-105` 把 `toks[0]` 塞进 `param`、`toks[1:]` 塞进 `distributionIds`；而按 `app/docs/源分布卡说明.md:175`「`DSn S S1 … Sk`」**S 卡没有独立 param 字段** ⇒ **连"可用"的 S 分支也把 J 列表整体右移一位**（`DS1 S 2 3` → `param="2"`、`ids=["3"]` → 索引 0 取到 3 而非 2），且这与它**自己的单测契约**（`test_ds_s_by_index`：`ids[0]` 即索引 0）**内部矛盾** ⇒ **S 分支同样待修**。注：两份派生文档自相矛盾（`C810_卡片格式详细.md:183` 写 `DS[n] var Dn1 Dn2 …` 有 var 字段），权威只有 C810.pdf 且本次未访问 ⇒ J 列表起点**待 C810 裁定**，但"与自身单测契约不一致"**无需 PDF 即成立**） | 分布源 **DS 依赖链**（`ERG=FPOS D1`/`POS=Dn`/依赖查表）在真实导入 INP 与 UI 两条路径上**静默退化为默认值**，`/api/source-demo-sample` 给出语义错误的抽样且不报错——直接违背 S1「按 C810 做全不降级、有错就地报」决议 | **P1**（t2 判 P0 → **改判 P1**：功能**尚未打包**、对当前用户零实害。**但列为发布阻断：打包即 P0**） | 跑走**真实解析路径**的新用例：`parse_distribution_lines(["DS1 Q 2 5 3 10 4"])` → `DistributionSampler(...).resolve_ds(...)`（预期现在恒 default）；**追加 S 用例**：`["DS1 S 2 3"]` → `resolve_ds(idx=0)` 预期 `{"distribution": 2}`（**现为 3**，off-by-one） | **三步**（**不可只改读键**）：① 对齐 `_parse_ds` 与 `_resolve_ds` 的键口径（`values` vs `distributionIds`）；② **同时裁定 `param` 语义**——按 C810 定下 J 列表起点（这决定 S/L/H 是否 off-by-one）；③ 补**走真实解析路径**的回归各一条（`["DS1 Q 2 5 3 10 4"]` 与 `["DS1 S 2 3"]`）。**禁止**只留手写 dict 测试 | engineer-backend + tester | — | **是** |
| **TD-04** | 后端代码债 | BE-01（PM 复核成立） | `gui/backend/generate_step.py:5-17`（忽略入参、写死 `#1=MANIFOLD_SOLID_BREP("MCNP Geometry")`）；`gui/backend/api_server.py:2597-2617`（回 `ok` + "STEP 文件已生成"，ImportError 兜底同样造假）、`:1446`（活跃注册）；`docs/contracts/api.yaml:657-687` | **成立**（我实读三处）。**但影响面需下调**：全仓 grep `generate-step|generateStep` 仅命中 api.yaml / api_server / spec / docs / 该文件自身 → **gui/src、inputcard_mcp、tests/ 全部零调用方、零测试**；`:2607` 还把 `"\\n"` 当换行切（无害，因入参被丢弃） | 「看起来能用」的**假功能**被登记为公开契约端点：任何外部/AI/未来调用方拿到「成功」+ 非法 STEP 文件（无几何）；契约谎报 | **P1**（t2 判 P0 → **改判 P1**：无仓内调用方 → 当前无用户可见错误，属"误导后续开发"档） | `grep -rn "generate-step" gui/src inputcard_mcp tests/`（零命中即可定论"无调用方"）；调用一次端点看返回的 STEP 是否有几何 | 三选一：① 真实现（复用 `/api/export-step` 的 FreeCAD 通道）；② 删端点 + api.yaml + `mcnp_sidecar.spec:40`；③ 保留则改回 `{"status":"error","message":"未实现"}` | engineer-backend（+ docs） | — | 否 |
| **TD-05** | 跨端契约债 | BE-04 + M-05 + M-06 + M-07（MCP 部分）+ PM§1.4（**合并**） | `gui/backend/mcnp_bridge.py:14-17`（宣传 `--mcp-server`）vs `:41/:47/:53`（只有 3 个分支）与 `:60-61`（**fallthrough 到 `api_server.main()`**）；`docs/手动打包方法.md:149-151`；`docs/inputcard-mcp.md:12,45,66,137,140`；`PROJECT_MEMORY.md:46,52,356` | **成立**（我实读 `mcnp_bridge.py` 全文：三个 `if` 均不命中时**确实** `import api_server; api_server.main()`） | `python.exe --mcp-server` 实际**起第二个绑 0.0.0.0:5001 的后端进程**（不是 MCP）——正是 §6「5001 端口劫持」的入口；且发布手册**教用户这么用**，还教 `pip install -r inputcard_mcp/requirements.txt`（与 §5 依赖红线相悖） | **P1** | `grep -n "mcp-server" gui/backend/mcnp_bridge.py docs/手动打包方法.md docs/inputcard-mcp.md PROJECT_MEMORY.md`；起 `python.exe --mcp-server` 看是否出现第二个 5001 监听（**须在受控环境、先记录原占用者**） | ① `mcnp_bridge.py` 加显式 `--mcp-server` 分支：打印"已废弃，请用 `--mcp-http`"后 `sys.exit(2)`，**绝不 fallthrough**；② 清 5 处文档/注释 → `--mcp-http`(8100)，删 pip 安装指示；③ 清 `inputcard_mcp/{__init__.py,requirements.txt,server.py:2}` 的 stdio 字样 | engineer-backend + docs | — | 否 |
| **TD-06** | 门禁与流程债 | FE-01 + FE-02 + t3§8.2（**合并**） | `gui/test/latticeInstances.test.ts:367-455`（`expandPositionsRef()` 为同文件手写 Python 重抄；`hasGolden` 守卫 `:424-427`；断言 `:429-454`）；`tests/unit/test_lattice.py:650-689`（`_golden_positions_hex_fresh` `:651-665`、`continue` `:679`、`pytest.skip` `:670-675`）；`gui/src/utils/__golden__/latticeGolden.json:198-375`(positions/expected)、`:376-530`(nested/leaves)、`:596+`(composeCases/node) | **部分成立**。**不成立半条**：t3「golden 内无后端原始产出字段 → 双端锁死名不符实」——`golden.positions[].expected` **正是真实 `expand_positions` 的断言对象**（`tests/unit/test_lattice.py:668-689` 用真函数逐位断言），故「TS 重抄 ↔ golden ↔ 真实 Python」构成**真实跨语言锁**（我实读确认）。**成立半条**：① `hasGolden` 守卫**读被测对象自身** → 改键名/删段即静默 skip 而门禁仍「0 failed」，且**历史上已真实发生过一次**（`docs/qa-report-total.md:69` 记录该用例曾因键名不匹配**恒 skip**）；② Python 侧 `_golden_positions_hex_fresh` 不满足即 `continue` → hex 样本**静默不校验**；③ `:670-675` 文件/段缺失即 `pytest.skip` | 「**唯一**跨语言几何闸门」可在全绿状态下**整条消失**；两侧同时漂移亦静默通过（TS 侧）；golden 由前端写盘、Python 侧只读断言 → 无"freshness"证明 | **P1**（**不升 P0**） | 允许跑测试后：`npx vitest run gui/test/latticeInstances.test.ts --reporter=verbose` 看 `skipped` 列；`pytest tests/unit/test_lattice.py -q -rs` 看 skip 数与 `-k golden` | ① **立即**加硬断言 `expect(hasGolden).toBe(true)`；② gate 输出解析把 **skipped>0 视为失败**；③ 排期：positions 每条加兄弟字段 `expected_python`（Python 侧自断言原始输出，抓 BE-21/FE-22 那类 pitch 公式被改），与 TD-28 同批 | engineer-frontend + engineer-backend | — | 否 |
| **TD-07** | 前端代码债 | FE-21c（PM 与本人均复核成立） | `gui/src/utils/useCellClosure.ts:37-43`（指纹 = 三个 **length**）、`:56`（命中即早退）、`:76`（`useCallback` deps 为 `[report]` 却读 `fpRef.current`）；消费 `gui/src/components/GeometryTab.tsx:227,302-303` | **成立**（我实读整文件：指纹只含 `surfaces.length : JSON.stringify(cells).length : tr_cards.length`，**内容变而长度不变**（如材料号 `1`→`2`）→ 永不重发请求；`report` 非空即一直返回旧结果） | 用户改几何后点「3D 预览」，「封闭」列**持续显示同长度编辑前的旧结论**，无任何告警 → 误导"已自检通过" | **P1**（PM 提 P0 候选 → **不升 P0**；判据见 §4.2） | 允许跑测试后写一条 DOM 用例：render GeometryTab → 点预览（mock fetch 返回 report）→ 改材料号 1→2（长度不变）→ 断言 fetch **被再次调用** | 指纹改**内容哈希**（`JSON.stringify` 全文 + 长度，或稳定 hash）；`useCallback` deps 去掉 `report`、改从 ref 读；补 `useCellClosure` 直接单测（见 TD-08） | engineer-frontend | — | 否 |
| **TD-08** | 门禁与流程债 | FE-21 + FE-21a + M-14 + t3§6/§8.1（**合并**） | `gui/src/utils/{cellClosure.ts,useCellClosure.ts,appScale.tsx,useDeckSynced.ts}`（`gui/test/**` 对 `cellClosure|useCellClosure|computeAppScale|useDeckSynced` **零命中**）；`tests/` 对 `cell-closure` **零命中**；`gui/src/utils/cellClosure.ts:15`（6 状态）vs `app/_freecad_csg_worker.py:1137/1140/1148/1157/1169/1171`；`docs/contracts/api.yaml:1452`（枚举只在**散文**）`:1484`（schema 仅 `type: string`）；`cellClosure.ts:56-62` 死导出 | **成立**（t3 内容 grep 零命中 + t3§8.1 与后端回执一致） | ① 已交付功能（封闭性自检）**无测试、无契约枚举**；② 6 状态词表**双实现零锁**；③ 漂移闸门做的是 **AST 存在性**校验，**结构上校验不到 enum** → enum 写错也不会红；④ `getClosureStatus` 死导出（P2 子项） | **P1**（死导出子项 P2） | `grep -rn "check-cell-closure\|closureMeta" gui/test tests/`（零命中）；`pytest tests/ -q -k closure` | ① `api.yaml:1484` 加 `enum:[closed,infinite,semi_infinite,empty,voxel,unresolvable]` **并在闸门补一条 HTTP 用例断言响应 status ∈ enum**；② 补 `cellClosure.test.ts`（最便宜）+ `useCellClosure` 直接单测；③ 删死导出 | engineer-backend + engineer-frontend + tester | — | 否 |
| **TD-09** | 门禁与流程债 | BE-11（PM 注入并扩大） | `tests/integration/test_tech_debt.py:2,9`（"当前应为 RED"，同文件 `:62-104` 又写 GREEN）；`tests/integration/test_roundtrip.py:40,51,58,66,168,253`；`tests/integration/test_sample_smoke.py:87,100`；`docs/backend-changes.md:44-52`（共 14 处） | **部分成立**（引文我可见且同文件自相矛盾；"对应能力均已清偿"由 t2 逐条代码侧坐实：`validator.py:447-457`、`core.py:825-826` 等） | 新人/AI 读到「预期红 = 正确」会把**真实红灯当绿灯容忍**（**反向门禁**），或在已绿用例上继续排查不存在的债 | **P1** | `pytest tests/integration/test_tech_debt.py tests/integration/test_roundtrip.py tests/integration/test_sample_smoke.py -q`（**跑前先清 5001**） | 14 处 docstring + `docs/backend-changes.md:44-52` 一次性改写为「F-X 已清偿（commit xxx）/ 现状 GREEN」；**禁用**「当前应为 RED」表述 | tester + docs | — | 否 |
| **TD-10** | 记忆·文档债 | M-01 + M-02 + M-03（**合并**；PM/研究员均判 P0） | `PROJECT_MEMORY.md:296`(§1=**1.7.2**)、`:309`(§2=**v1.7.2**，#7「待排期」)、`:389/:394/:521-524`(§3/§9 门禁表=**30 端点 / pytest 573 / vitest 358**)、`:276`(S2="恒 1.7.2")、`:483-484`(§8 里程碑表**止于 v1.7.4**) | **成立**（我复核：`gui/package.json:4`、`gui/src-tauri/tauri.conf.json:10`、`gui/src-tauri/Cargo.toml:3` **均为 1.7.5**；`docs/contracts/api.yaml` grep `^  /api/` **恰 49 条**；记忆 §1/§2 原文即 1.7.2 / v1.7.2）。**采纳 t1 的 M-01 修正**：**§9「版本发布纪律」段（`:528-532`）不含任何版本号，故不算"版本号写错"**；真正陈旧的是 **§8 里程碑表停在 v1.7.4** 与 §5 例句、§9 门禁基线 | AI/新人按记忆取版本、判发布状态、判接口数与门禁基线**全错**；把已上线能力（重合检测等 3 个版本的功能）读成「未排期」 | **P1**（t1 判 P0 → **改判 P1**：无用户可见错误、无数据丢失、不阻塞构建，属"误导后续开发"档；同族 M-16 见 TD-12） | 对比 `gui/package.json:4` / `tauri.conf.json:10` / `Cargo.toml:3` / `Cargo.lock` / `README.md:25` 五处；`grep -c "^  /api/" docs/contracts/api.yaml` | §1/§2/§5/S2/§8 全改 1.7.5 并补 §8 的 v1.7.5 行；§3/§9 按实测重算（49 端点 / 真实 pytest·vitest 数） | PM | — | 否 |
| **TD-11** | 记忆·文档债 | M-04（t1 判 P0） | `PROJECT_MEMORY.md:272-275`(S2="未提交仅批量编辑 5 文件")、`:281-284`(S3="全部改动未 commit")、`:41` | **部分成立**（reflog 侧成立：`.git/logs/HEAD` 08-22~09-10 有 45+ 条提交、`HEAD=4f0798fa`；**当前工作区真实未提交状态我无法核实**——无 shell） | 无法判断哪些改动已入库/真在工作区；批次边界与「一主题一提交」纪律不可审计；`:275` 提交消息 `+ misc prior uncommitted work` 后紧跟 `reset` → **存在无关改动被夹带进他主题提交的疑点** | **P1**（无台账） | `git status --porcelain`、`git show --stat <09-09 提交>`（授权后执行；**不属本次只读范围**） | S2/S3 按真实 `git status/log` 重写；**新增纪律：批次结束必记 commit 短号或「待提交文件清单」** | PM | **无** | 否 |
| **TD-12** | 记忆·文档债 | M-16（t1 判 P0，本次最严重之一） | `PROJECT_MEMORY.md`（关键词 `8100\|mcp-http\|appScale\|sourceAdv\|useDeckSynced\|封闭\|closur\|多核\|免安装\|闪主界面` 等**全部零命中**）；证据 = `.git/logs/HEAD:251,259-275,277-280`（**20 条**提交） | **成立**（关键词零命中 + 20 条 reflog 逐条；t1 修正了 PM「全部未记录」的初判：stdio 时代批次有记录） | **20 次真实改动（含新功能与 1.7.5 升版）零记忆 / 零契约 / 零 §3 锚点** → 下个会话会重复实现或误删；是本次所有记忆债的**根因放大器** | **P1**（t1 判 P0 → **改判 P1**：属"误导后续开发 + 无台账"档，非用户可见错误/数据丢失。按 §1.3 **无台账一律 P1**） | `grep -c "8100\|appScale\|closur" PROJECT_MEMORY.md`（0）；对照 `git log --oneline -30` | 按 reflog 逐条补记 S1/§2/§3/CHANGELOG；为封闭性与校验规则补契约；建立「**提交即登记**」纪律 | PM（+ 架构师补契约） | **无** | 否 |
| **TD-13** | 记忆·文档债 | M-08 + M-09（**合并**） | `docs/CHANGELOG.md:9`（基线沿革停在 pytest 528/vitest 327）、`:50-52`（材料库段缺标题）、`:132`（总表最新仅到 09 月）；`docs/backend-changes.md:1406`、`docs/frontend-changes.md:1277`（均止于 08-30） | **未复核**（t1 给出精确行号与缺批清单；结构与"止于 08-30"与我读到的文件末尾一致） | 唯一可回溯流水**断档 6 批**（08-27/28、08-30、09-04、09-09、09-10），无法审计「何时改了什么」 | **P1** | `tail -30 docs/backend-changes.md`、`head -20 docs/CHANGELOG.md` | 依 reflog 补 6 批条目（CHANGELOG 总表顶部；两份 changes 按 §AA/§AB 体例） | PM + 架构师 | — | 否 |
| **TD-14** | 记忆·文档债 | M-10 + M-11 + M-12 + M-13 + M-17 + M-07（版本部分）（**合并**） | `app/UI_ARCHITECTURE.md:5,27-28,47,280`（"25 端点"）、`:259`（"pytest 251 绿"）、§5.2/§4 行号表（实测 `inp_generator.py` 应为 1251/1256/1260/1274，调用点 1302…1375；`models.py` 应为 271/371/497/23/60）、`:66`（把**已死**的 `backend.ts` mock 回退写成现行为）；`docs/contracts/{lattice-coverage-check.md:3, geometry-check.md:3,221, meshtal-visualization.md:4}`（"待确认/不施工"但均已交付）；`docs/contracts/watertight-check.md`（**全树不存在**，双处引用：`MCNP输入卡生成器_功能待办清单.md:8`、`docs/contracts/validator-crosscheck.md:39`）；`MCNP输入卡生成器_功能待办清单.md:50-53`（第 11 项标 ❌，实际 `sliceExport.ts`/`SliceExportPanel.tsx` 已落地）；`docs/手动打包方法.md:7,41,50`（写"最新 v1.7.4 / 当前 v1.7.2 / 徽章第 9 行"） | **部分成立**：M-12（`watertight-check.md` 不存在）我以 grep 复核**成立**；M-17（sliceExport 已落地）我以文件存在 + 记忆 `:83/:86` 复核**成立**；M-10 的"25 端点"与实测 49 一致（我复核过端点数）；UI_ARCHITECTURE 行号未逐条复核 | 把**已交付**读成"未实现/待确认"、把**已死实现**读成现行为、按错行号定位代码 → 重复排期、误判缺口；已交付功能的"设计约定"文件缺失（双处悬空引用） | **P1**（M-12 原 P2 → 依 PM 上调 P1，我认同：已交付功能无权威契约 + 双处悬空） | `ls docs/contracts/watertight-check.md`；`grep -rn "watertight-check" .`；`grep -c "^  /api/" docs/contracts/api.yaml` | ① 补 `docs/contracts/watertight-check.md`（按 `validator-crosscheck.md:37-41` 扩写）；② 契约状态位改"已交付 + 时间/commit"；③ UI_ARCHITECTURE 整体重锚定或文首标"历史快照（行号按 2026-08-12）"并停止当权威；④ 待办清单 #11 改 ✅；⑤ 打包手册版本与徽章行号改 1.7.5/25 | 架构师 + PM | — | 否 |
| **TD-15** | 后端代码债 | BE-06（**t2 已于 v7 §5.1 自行撤回**；与我的"主机制不成立"结论**独立一致**） | `inputcard_mcp/server.py:87-101`（`_sections_to_deck`）、`:71-84`（`_deck_to_sections`）、`:204-222`（`patch_section`）、`:151-154`（`_ws_state`）；`gui/backend/api_server.py:1337-1349`（`deck_from_json` 读 `universe_comments`） | **不成立（主机制）**：我逐行复核——`_sections_to_deck` 把**整个 dict**（仍含 `universe_comments`）交给 `deck_from_json`，后者 `:1347-1348` **显式读取该键**；`_deck_to_sections:83` 也显式保留 → **U 分组注释不会丢**。t3 §8.4 从**前端侧**独立得出同一结论（`App.tsx:92` 浅展开保留本地 `universeComments`）。**成立残余**：① `patch_section` 用 `_deck_to_sections` **整份重写**工作区 sections，而该函数只产 8 段 + `universe_comments` → 工作区里任何**非 deck 键**（如 `rawOverrides`/`raw_overrides`——注意 `server.py:175` 的 `generate_document` 会读它）会被**静默抹掉**；② `_ws_state()` **全仓零调用者**（我 grep 确认唯一命中定义处）且 docstring（"生成的 INP 文本"）与实现（`revision+sections`）不符 | ① 未映射键蒸发（触发条件：前端 PUT 的 deck 含此类键——**待确认**）；② 死函数 + 误导 docstring | **P2**（t2 判 P1 → **改判 P2**，且 t2 已在 v7 §5.1 **撤回该条**：主机制不成立。**本行保留的只是"残余"**：未映射键蒸发风险 + 死函数/误导 docstring） | 允许跑测试后：`pytest tests/unit/test_inputcard_mcp_workspace.py -q`；新增用例「patch_section 后 `universe_comments` 与 `rawOverrides` 仍在」；`grep -rn "_ws_state" .` | `patch_section` 改"**只改目标段**"而非整份重写（或 `_deck_to_sections` 补回全部前端键）；删 `_ws_state()`；补回归 | engineer-backend | — | 否 |
| **TD-16** | 前端代码债 | FE-03 + FE-04 + FE-05 + FE-06 + **M-22 + M-23** + t3-Q7/D3（**合并**：代码侧死实现 + **文档侧把它当生产**，同一现象的两半） | `gui/src/components/Preview3DLattice.tsx:1-479`（零 import）；`gui/src/utils/backend.ts:74-95`（同名 `generateInp` 无人使用，失败返回 `"// Python backend not connected"` 注释串、读陈旧 `output.inp`）；`gui/src/utils/lattice.ts:171-184`(`UNIVERSE_PALETTE_12`)、`:447-471`(`estimateLatticeExtent`，hex 分支写死 `pitch=1`；`docs/qa-report-phase2.md:78` 的"阶段3 衔接"建议悬空 = **M-23**）；**文档侧 16 处**（M-22）：`docs/contracts/core3d-instancing.md:130,133,188`、`docs/qa-report.md:89`、`docs/frontend-changes.md:17-18`、`docs/contracts/lattice-fix15-design.md:30,405,410,412,456,547`、`PROJECT_MEMORY.md:119,134,136,153,171,178,188,191`；`app/UI_ARCHITECTURE.md:66` | **成立**（我 grep 复核：`Preview3DLattice` 仅命中其自身与文档，**零 import**；`generateInp` 的全仓消费点全部来自 `./utils/dataCollector`（`App.tsx:10`、`DiffDialog.tsx:8`、`SweepDialog.tsx:15`）→ `backend.ts` 那份确为死代码）。**M-22 定性采纳**：属"**落地后被内联取代**"（`PROJECT_MEMORY.md:178` 记 08-24 曾接线，`Preview3D.tsx:15` 已改内联；取代**时点**需 `git show`，见 §6-未验证） | ① 479 行重复装配逻辑无编译/测试触达，且 docs 把它当**生产**消费方 → 后续 agent 会照文档去找不存在的调用链；② `backend.ts` 那份**同名同端点却行为不同**（静默返回注释串 + mock/陈旧文件回退），IDE 自动补全极易误选 → **运行期隐患**；③ `UI_ARCHITECTURE.md:66` 把这条已死路径写成现行为 | **P1**（文档侧 M-22/M-23 为 P2，取最高） | `grep -rn "Preview3DLattice" gui/ src 2>/dev/null`；`grep -rn "from \"./utils/backend\"\|from \"../utils/backend\"" gui/src` | **一码一文同批**：删 `Preview3DLattice.tsx` + 同步 16 处文档描述（标"已废弃/被内联取代"）；删 `backend.ts:74-95` + 其 `DeckData` import（保留 `startPythonBackend`/`stopPythonBackend`）；删两个死导出并清 `lattice.test.ts` 引用；phase2 报告该行标"已由 `/api/lattice-extent` 覆盖，结案" | engineer-frontend + 架构师 + PM | — | 否 |
| **TD-17** | 门禁与流程债 | FE-08 | `gui/tsconfig.json:21-23`（`include: ["src"]`）；`gui/package.json:6-12`（无 `typecheck` 脚本；`build` 走 vite 不做类型检查） | **成立**（我实读 tsconfig：`include` 仅 `src`，`gui/test/` 不在 tsc 项目内）。**计数待核对**：t3 报 81 个测试文件、t1 §6.1 实测 **75 test + 1 snap**（且指出 t3 的 61+19+4=84≠81 自身不自洽）→ 本条只需"**整个 `gui/test/**` 不在 tsc 内**"这一事实，**不引用具体文件数** | 记忆多轮记载的「tsc EXIT 0」**覆盖不到整个测试目录**；FE-01 那类"TS 重抄"漂移没有任何编译期拦截 | **P1** | `npx tsc -p gui/tsconfig.json --noEmit` 与加 `tsconfig.test.json` 后的差异；`ls gui/test/**/*.test.*` 计数核对 | 加 `tsconfig.test.json`（include `test`，继承主配置）+ `"typecheck": "tsc -p tsconfig.json && tsc -p tsconfig.test.json"`（**零新依赖**），接入门禁描述 | engineer-frontend | — | 否 |
| **TD-18** | 门禁与流程债 | FE-09 | `gui/test/volume/colorize.test.ts:137-146`（`:141` 起 `t0`、`:142` 跑 128³、`:145` `expect(dt).toBeLessThan(50)`；`:140` 先 O(n) 填 16.7M 字节） | **成立**（写法我实读：单次采样、无 warmup、无重试、无分位数；`PROJECT_MEMORY` 至少 6 处记载同一 flaky） | 典型"单样本墙钟阈值断言"反模式 → CI/负载下随机红，逼出"隔离单跑绿、非回归"这类**人情判断**，削弱门禁可信度（本项目历史误判来源之一） | **P1**（失败率待验证） | 连跑 `npx vitest run gui/test/volume/colorize.test.ts` ×20 记录 `dt` 分布（p50/p95/max） | 正确性断言保留、性能断言移出默认门禁（N≥5 中位数 + 宽松上限，或相对断言，或 `PERF` 环境变量另跑）；**删除"已知 flaky"长期豁免** | engineer-frontend | — | 否 |
| **TD-19** | 前端代码债 | FE-13 + FE-14（**合并**） | `gui/src/utils/DeckContext.tsx:12`（snake_case `CellData`）vs `gui/src/components/CellEditDialog.tsx:6-27`（camelCase 同名接口）；`gui/src/utils/cellBridge.ts:10,19,47`（自认"类型三处同步"）；`gui/src/components/GeometryTab.tsx:48`（`useDeckSynced<LocalCellRow[], any[]>`）；`Preview3D.tsx:600-602,894-896`（`impN \|\| imp_n` 防御性双读） | **未复核**（t3 给出精确行号与计数：`as any\|: any\|any[]\|as unknown as` src **214** 处 / test **57** 处） | strict 形同虚设；字段漂移无法被类型系统发现（已现"同一字段两套命名并存"的实证）→ FE-07 那类漂移正是无类型约束的产物；Preview3D（1400+ 行）重构无护栏 | **P1**（FE-14 部分为 P2） | `grep -rn "as any\|: any\|any\[\]" gui/src \| wc -l` | ① 单一 `CellData` 定义 + 显式 `DeckCellPayload` 契约类型；② `useDeckSynced<LocalCellRow[], CellRow[]>` 去掉 `any[]`；③ 桥梁字段覆盖单测（`keyof` 两向穷举）；④ 先给 `windows.ts`/`api.ts` 建类型（对外契约收益最高） | engineer-frontend | — | 否 |
| **TD-20** | 后端代码债 | BE-07 | `gui/backend/api_server.py:15`（`ThreadingHTTPServer`）、`:110`（`_STL_SESSION`）、`:2693`（缓存命中整体重绑）、`:2751-2753`（**先删上一会话目录再建新会话**）；`app/preview_cache.py:40-41,184-188,240-246`（`_index/_order` 无锁） | **未复核**（结构与"唯一锁是 `_SURF_CLASSES_LOCK`"由 t2 给出；t2 §二-5 明确此锁不覆盖该窗口） | 两个并发 preview-3d 会**互删对方刚生成的 STL 会话目录** → "STL 偶发空/截面缺栅元"这类**难复现随机故障** | **P1** | 并发压测（两个 preview-3d 同时请求）；或加日志后观察 `_clear_stl_session` 竞态 | 加请求级 `_PREVIEW_LOCK`（preview-3d/preview-lattice/cross-section/clear-stl 共享），或把会话改成按请求持有 + 显式生命周期；`PreviewCache` 内部加锁（`_drop` 的删目录移出锁） | engineer-backend | — | 否 |
| **TD-21** | 后端代码债 | BE-03 | `app/generator/inp_generator.py:479-496`（`except (json.JSONDecodeError, TypeError): pass`）、`:919-927`（`except: return []`） | **部分成立**（我见到 `:479-496` 的 `elif adv.sdef_raw_text:` + `json.loads` 兜底结构；触发条件依赖旧存档/坏 JSON——而 TD-23 显示该字段**对新导入恒空**，故触发面仅限旧 localStorage 工作区） | 数据坏/旧格式时生成的 INP **丢失全部 SI/SP 卡仍报"生成成功"**；错误推迟到 MCNP 运行期 | **P1**（影响面=边界条件） | 构造 `adv.sdef_raw_text` 为损坏 JSON 的 deck 调 `generate_inp_from_deck`，看是否静默丢卡 | 失败即 `raise` 或经 handler `_err` 回传；与 TD-23 的退役一并处理 | engineer-backend | — | 否 |
| **TD-22** | 跨端契约债 | BE-12 + **BE-26** + t3§8.4（**合并**） | `gui/backend/api_server.py:2039-2092`（内联序列化，独有 11 行前端中间态字段 `:2061-2091`）vs `:1352-1391`（`_deck_to_frontend_dict`）+ `:1395`（公开别名，供 `/api/text-to-section:2147`）；消费 `inputcard_mcp/server.py:478` | **部分成立**：**分叉成立**（两段同源实现已分叉，窄的那份被 MCP `/workspace` 与 `/api/text-to-section` 使用）；**前端可见影响不成立**（t3 §8.4 独立复核：前端已删顶层中间态副本、权威是 `deck.adv`，`migrateLegacySourceKeys` 兜住 → 不产生用户可见 bug）；**新成立点**：`_deck_to_frontend_dict:1353` docstring 自称"与 `/api/parse-inp` 的序列化一致"——**该声明已不成立**（t2 **BE-26** 同样成立并**更正了方向**：**宽的是 `/api/parse-inp`** —— 它从 `asdict(deck)` 起手、**不删任何键**（`:2044`），故**含** 9 个前端中间态键 **+ `_warnings`**（`:2061-2078`/`:2091`）；**窄的是 `_deck_to_frontend_dict`** —— 既不注入中间态键、**也不带 `_warnings`**，正是 MCP `/workspace` 与 `/api/text-to-section` 走的那份） | 两处消费者契约不一致且**声明错误**；**真正受影响的是应用外消费者**：`deck_to_frontend_dict`（公开别名，MCP `/workspace`）**缺 `_warnings`**（`/api/parse-inp` 反而带它）；任一边改字段另一边静默落后 | **P1** | diff 两段序列化的键集合；`curl /api/text-to-section` 与 `/api/parse-inp` 对比键集 | 合并为一个序列化函数（`include_frontend_aliases` 显式参数）；或至少修正 docstring 去掉错误声明 + 对齐 `_warnings` 语义 | engineer-backend | — | 否 |
| **TD-23** | 后端代码债 | BE-10（PM 注入，t2 判 P1） | 定义 `app/models.py:463-465`；wire `gui/backend/api_server.py:1320`、`:2067`；读 `app/generator/inp_generator.py:479-496,1336`、`app/generator/validator.py:351,361`、`app/generator/parsers/__init__.py:269`；写 `parsers/core.py:1154-1155`（**只写 `sdef_distributions`**）、`parsers/__init__.py:79`（默认 `""`）、前端旧存档迁移 `gui/src/utils/sourceAdv.ts:192`；测试 `tests/unit/test_generator_sdef.py:104-106` | **成立**（我复核关键两端：读侧 `:1320`、`parsers/__init__.py:269` 均读该键；写侧只剩 `:79` 默认值与 `sourceAdv.ts:192` 旧存档迁移；`api.yaml:2244` 自述"新解析已停写，仅读兼容"） | **僵尸字段**：新导入的 INP 恒 `""`，4 处读兼容分支**永不被真实数据命中**（零覆盖活代码）；1 条测试手写它维持假活；**无退役计划** → 永久技术债 | **P1**（字段本身 P2，叠加"多处读 + 测试锁死 + 无计划"升 P1） | 导入任一含 SI/SP 的 INP，断言 `deck.adv.sdef_raw_text == ""` 且 `sdef_distributions` 非空 | 三步：① 前端把旧 `old.sdefRawText` 一次性迁移成 `sdef_distributions`；② 随后一次性删 model 字段 / generator 兜底 / validator 左项 / api_server 两处 / `contract.ts:44` / `api.yaml:2207,2244,2289` / 那条测试；③ **不采**"仅保留 + 加注释"（注释已存在 = 等于无计划） | engineer-backend + engineer-frontend | — | 否 |
| **TD-24** | 后端代码债 | BE-09 | `app/generator/distributions.py:43`（`_SI_LETTERS = ("L","H","A","S","Q","T","F","V")`）、`:61-68`（`_parse_si`）、`:451-472`（抽样只认 H/""/L/A 否则 raise） | **成立**（我实读 `:43` 与 `:61-68`；与 `PROJECT_MEMORY:22` 的 C810 权威结论"SI 只有 H/L/A/S"一致） | ① `SI1 Q …` 被判为**合法类型**：生成/往返看不出（rawText 原样回放），**只有走到抽样才炸** → 错误被推迟到最不方便发现处；② 未知字母（`SI1 B 1 2`）被当数值 token → 后续抛"分布值无法解析为数值"，**归因错误** | **P1** | `grep -n "_SI_LETTERS" app/generator/distributions.py`；用 `SI1 Q 1 2` 走一遍 parse→sampler | `_SI_LETTERS` 收紧为 `("L","H","A","S")`；未知首 token 明确报"非法 SI 类型"，**不要静默当值**；顺带核对 `_SP_LETTERS`/`_DS_LETTERS` 与 `_resolve_ds` 判断集是否同源 | engineer-backend | — | 否 |
| **TD-25** | 后端代码债 | BE-13 + BE-18 + BE-19 + BE-21 + BE-24（**合并**：死代码/未接线/重复实现/性能） | `inp_generator.py:422-426`（`_src_field` 零调用者）、`:908-927`；`app/meshtal/downsample_plan.py:54-67`（唯一消费者是测试）；`app/lattice.py:1244`（裸引用噪声）、`:915-929` vs `:1037-1041`（同一 hex 规则两处）、`:591-601`/`:108-119`（仅测试引用）；`api_server.py:675`（`_cell_pz_bounds` **未传** `surfaces` 预解析参数 → 每 cell 全量正则）、`lattice.py:1239-1247`（入口全量预计算 vs `:1336-1341` 惰性回填） | **未复核**（t2 逐条给 file:line 与"全仓库搜索唯一命中在 tests/"的结论） | 迁移走了实现、没删旧壳 → 读者以为还有第二条路径；`_is_d_ref` 三份 = "改一处漏两处"；**优化做完没接线**（BEAVRS 量级下确定性叠加延迟）；死符号让读者高估成熟度 | **P2** | `grep -rn "_src_field\|decide_resolution\|hex_ring_rows\|query_new_vs_existing" app tests \| grep -v test_`；BEAVRS 输入计时对比 | 删 `_src_field`/`lattice.py:1244`；`decide_resolution` 接线或标"未接线"；`_cell_pz_bounds` 沿递归透传预解析 surfaces；hex 规则抽单一实现；死符号加"golden-only/未接线"标注 | engineer-backend | — | 否 |
| **TD-26** | 后端代码债 | BE-16 + BE-17 + BE-20 + BE-25 + **3 条相邻发现**（**合并**：静默失败/归因缺失） | `app/_freecad_cross_section_worker.py:656-657`（**裸 `except: pass`**）等；`app/meshtal/meshtal_cache.py:96-119`（`evict` 无锁、不过滤 `*.tmp`）、`:84-94`（`put` 固定 tmp 名 → 并发互相覆盖、`os.replace` 失败分支未捕获）；`api_server.py:1668-1676`（`TimeoutExpired: pass`，不置标记）；`app/meshtal/fmesh_parser.py:142-147,160-168,241-245`（整段 raw 赋给每卡 → 可能重复回放；死分支 `group(2)` 取错组）；`app/overlap_probe.py:20-27`（缺曲面静默 `continue`，绕过 `probe_error` 上抛） | **未复核** | 曲面构造失败**完全无痕迹**（截屏缺块却拿不到"哪个曲面"）；多 worker 并发下**偶发解析失败/静默全量重解析**；参数扫描**超时与崩溃不可区分**；fmesh 回放"重复卡行"与死分支真 bug 需构造输入才能定性 | **P2**（fmesh 死分支/相邻项 P3） | 各一条最小复现：① 造不支持曲面 → 看是否只缺件无日志；② 并发两 worker 取同 meshtal 不同帧；③ 造 300s+ 超时组合；④ 造"同卡体含 2 个仅未知 key 的 FMESH 卡" | 裸 except 改收集 `errors` 并经响应透传（至少 stderr）；`evict` 排除 `*.tmp` + tmp 名加 pid；超时置 `rec["exitCode"]="timeout"` + 告警；fmesh 按卡号切分 raw、删或修死分支；五处同构 field builder 抽 `voxel_csg.build_field_fns` | engineer-backend + tester | — | 否 |
| **TD-27** | 前端代码债 | FE-11 + FE-12 + FE-15 + FE-16 + FE-18 + FE-19 + FE-20（**合并**：测试守卫脆弱 + 前端杂项） | `gui/test/volume/windowRouteConsistency.test.ts:26,33,38-51`（正则敏感 → 两侧抽空时 `expect([]).toEqual([])` **空对空假绿**；且无"新增窗口必须登记"断言）；`gui/test/preview3dDeadLog.test.ts:13`（守卫只读单文件）；`gui/test/lattice.test.ts:275…455`（11 处 `golden.xxx as any[]`）；`gui/package.json:6-12`/`vite.config.ts`（无 `test` 块、无 `typecheck`）；`gui/README.md:7-19`（无 `npm test`）；`sourceAdv.ts:147-169`、`cellBridge.ts:50-51` 等 5 处兼容层无退场版本；`alignWorld.ts:16` vs `surfacesAABB.ts:20` 双 `Vec3` | **未复核**（t3 §三给出"覆盖完整/无遗漏 pragma/无 TODO 回潮"等**负面结论**，我未逐条复核） | 一次 Prettier/重构就让守卫在**全绿**状态下失效；golden 段名拼错只等运行期 `undefined`；守卫范围=单文件；兼容层永久滞留 | **P2**（FE-11/FE-16/FE-18/FE-19 为 P3） | 各一条最小断言/重构演练（把 `main.rs` 正则改单引号看是否仍绿） | 守卫加 `expect(len).toBeGreaterThan(0)` 或改用 label 单一来源常量；golden 具名类型（配合 TD-17）；守卫扩到 `gui/src/**`（白名单 sidecar 日志）；README 补 `npm test`；兼容层标注引入/退场版本 | engineer-frontend | — | 否 |
| **TD-28** | 前端代码债 | FE-17 + FE-22 + t2-BE-21 + t3§8.3（**合并**：hex pitch / subPitch 多副本） | `api_server.py:3418-3431`（`_subpitch` 取各格阵 min，`:3424-3425` 无格阵兜底 `1.26`，`:3430` **无条件写入** `fidelity.subPitch`）；`Preview3D.tsx:745`、`Preview3DLattice.tsx:277`（前端两处 `1.26` 兜底）；hex 格距↔跨度换算**副本**：**t2 v8 复核为 7 处 / 2 个方向**（BE-21 附表逐处行号），**t3 v2 计 8 处 / ≥3 种口径** → 两数并存，**取「≥7 处」即可**（`app/lattice.py:915-929` vs `:1037-1041`；`api_server.py:734-740` 反向；`lattice.ts:453` 写死 `pitch=1`；`latticeInstances.ts:384-389`；测试消费点） | **部分成立**：**1.26 活路径不成立**——我实读 `:3418-3431` 确认 `subPitch` **恒下发**（无格阵时才取 1.26），故前端两处 `?? 1.26` 与后端那处均为**不可达防御**（t3 §8.3 已自我修正）；**hex pitch 副本成立**（**≥7 处**：t2 v8 计 7 处/2 方向并附逐处行号表、t3 v2 计 8 处/≥3 口径 —— 两数并存，未独立逐处复核）；单格阵已改取自身 pitch（`min` 分支） | 公式**多副本多口径**：改一处漏七处，即使 TD-06 加了 `expected_python` 也会被 pitch 副本坑；防御代码与活路径混淆 → 后续读者误判影响面 | **P2**（1.26 部分 P3） | `grep -rn "1\.26\|_subpitch\|subPitch" gui app \| grep -v test`；对单格阵 deck 断言 `fidelity.subPitch == 该格阵 pitch` | ① 后端无格阵时下发 `null`，前端**集中一处**兜底（语义正确且兜底变可测）；② 抽 `_hex_pitch(extent)` 单一实现，8 处收敛；③ 与 TD-06 的 `expected_python` **同批**做 | engineer-backend + engineer-frontend | — | 否 |
| **TD-29** | 前端代码债 | FE-07 + BE-14 + **M-21**（**同源三处合并**） | `gui/src/utils/lattice.ts:123-128`（docstring 旧公式）vs `:130-137`（实现=新公式，与 `app/lattice.py:604-616` 一致）；**M-21 清点到 16 处**：`gui/test/lattice.test.ts:131`(describe 名)、`docs/frontend-changes.md:11,208,1234`、`docs/qa-report.md:64`、`docs/qa-report-phase2.md:50`、`docs/qa-report-total.md:24`、`docs/backend-changes.md:1285`、`docs/contracts/lattice-fix15-design.md:171-172`(**L1 锁死表**:450)、`PROJECT_MEMORY.md:166,172,178,179,208` | **成立**（t2 与 t3 从两端独立核对同一处：**实现正确、注释与文档是旧公式**，差 30° 旋转；M-21 把残留处数从 4 扩到 16，含**契约 L1 锁死表**——后者会污染跨语言实现） | 被反复"根因修复"过的高危公式，注释与文档并存两套 → **下次有人照注释改即引入几何回归**；测试 describe 名与文档同错；契约 L1 表写错公式尤其危险 | **P2**（t3 判 P1、t1 判 P1 → **改判 P2**：纯注释/文档漂移，**行为正确**，t2 对同一处亦判 P2；按口径"注释与代码不符"归 P2。**若 PM 认为 L1 锁死表算契约债可回 P1**） | 对同一输入跑 `hexCenter` 与 `app.lattice.hex_center` 逐位比对（应一致）；`grep -rn "pitch\*0.866\|p\*√3/2" docs PROJECT_MEMORY.md` | 16 处一次性改为新公式（**实现不动**），docstring 补自洽核验并交叉引用 `app/lattice.py:604-613` | engineer-frontend + 架构师(researcher 已认领 docs) | — | 否 |
| **TD-30** | 前端代码债 | FE-10 | `gui/src/source/SourceDemoRenderer.ts:56-121`（无单测）；`gui/src/components/SourceTab.tsx:69-205`（无组件测试）；`gui/test/source/SourceDemoWindow.test.tsx:11-17`（仅 SSR 兜底） | **未复核**（与 `PROJECT_MEMORY.md:31` 自认"未做"一致） | 演示源的"按钮校验 → 红字 → 开窗"链路与粒子/方向线映射**无回归网**，重构只能靠人工冒烟 | **P2** | `grep -rn "SourceDemoRenderer\|SourceTab" gui/test` | 抽纯函数 seam（能量归一化/方向线长度）加纯单测；`SourceTab` 用 jsdom + mock 覆盖"error 不开窗 / ok 写桥"两分支（照 `sweepDialog.dom.test.tsx`） | engineer-frontend | — | 否 |
| **TD-31** | 跨端契约债 | **RV（reviewer 本次新发现）** | `docs/contracts/source-demo-visualization.md:25`（"`resolve_ds(eid, parent_value) -> list[int]`：…返回子分布号列表"）vs `app/generator/distributions.py:401-405`（实际签名 `resolve_ds(self, eid, parent_value, parent_si=None) -> dict`，返回 `{"distribution": n}` / `{"value": v}` / `{"default": True}`） | **成立**（我实读两侧） | 已交付功能的契约**签名与语义都与实现不符**（返回类型从 `list[int]` 变成判别 dict，且多了 `parent_si` 参数）→ 契约不能作为"实现该功能"的依据；漂移闸门（AST 存在性）**校验不到**函数签名 | **P2** | 读 `docs/contracts/source-demo-visualization.md` §1 与 `distributions.py:401` 并排比对 | 契约按实现改写（含 `parent_si` 与三种返回形态）；把"契约里出现的函数签名"也纳入人工评审清单 | 架构师 + engineer-backend | — | 否 |
| **TD-32** | 跨端契约债 | FE-21b（**用户已裁决，转待施工**：见 §0.1） | `gui/src/utils/cellClosure.ts:41-48`（`infinite` → `allowed:true`、琥珀 `#f9a825`）vs `gui/src/components/CellEditDialog.tsx:50-58`（同状态 → **红色错误态** `#e53935`） | **成立**（t3 与 PM 均实读；我复核 `CellEditDialog.tsx` 有**第三份**状态→展示映射，且仍自建 `/api/check-cell-closure` 请求，未收敛到深模块） | 同一 `infinite`（外无限，深模块视为**合法**）在两处**语义相反**：一处"正常"、一处"红色错误"。用户在旧对话框看到红色错误、在几何页看到琥珀提示 → 认知矛盾；且"抽取深模块"没收敛旧实现 | **P1**（**用户已裁决语义，转为待施工**：三档 = 封闭正常 / 外无限"允许+感叹号" / 不封闭错误 —— 见 §0.1） | 打开旧对话框与几何页，对同一外无限栅元比对颜色/图标/文案 | **按 §0.1 裁决落地**：以 `cellClosure.ts:41-48`（`allowed:true`）为准，**红色错误态是待清理的第三份映射**；三处映射统一为三档语义（含 `STATUS_META`/`_META` 合并），并让 `CellEditDialog` 改走 `useCellClosure`（收敛旧实现） | engineer-frontend | — | 否 |
| **TD-33** | 记忆·文档债 | **M-20（t1 v5 新增）** | `PROJECT_MEMORY.md:52`("554/0（69 文件）")、`:87`("546/0（69 文件全过）")、`:40`("587+4 passed（73+1 文件）")、`:153`("522/0（66 文件全过）")；`docs/CHANGELOG.md:47`；**被更正方**：`docs/audit/t3-frontend-debt.md:90,119`（报 81 个：根 61 + volume 19 + ptrac 4） | **成立（以 t1 v5 实测为准）**：`gui/test/**` = **76 个文件 = 75 个 `*.test.ts(x)`（根 47 / volume 23 / ptrac 4 / source 1）+ 1 个 `.snap`**；记忆里的"66/69/73+1"是**各批当时快照却未标注**；t3 的 81 **自身不自洽**（61+19+4=84≠81） | 后人引用"文件数"必错，且有被写进汇总文档的风险；门禁基线的可信度被连带削弱（与 TD-10 同族） | **P2** | `glob gui/test/**/*.test.ts(x)` 与 `glob **/*.snap` 计数（可 10 秒核对） | 记忆各处标注"该批当时文件数"；统一以 **75 test + 1 snap** 为当前值；更正 t3 文档两处数字 | PM（+ researcher 更正 t3 文档） | — | 否 |
| **TD-34** | 门禁与流程债 | **PM 提供证据 / reviewer 复核成条（v1.3 新增）** | `gui/build/mcnp_sidecar/{Analysis-00,PYZ-00,COLLECT-00,EXE-00,PKG-00}.toc`（**构建产物，仓库内已有、未被任何测试消费**）；`gui/mcnp_sidecar.spec:17-31` | **成立**（我逐条复核：`PYZ-00.toc:782` = `('app.lattice', ...)`，**无** `('lattice', ...)`；顶层名只有 `analytic_slice:638`/`mc:3512`/`models:3839`/`voxel_csg:12682`；`COLLECT-00.toc` 的 app 源文件 = `analytic_slice.py:3957`、`coverage_check.py:3960`、`gpu_pref.py:4034`、`material_library.py:4035`、`mc.py:4038`、`sweep.py:4100`、`voxel_csg.py:4101`，**无** `lattice.py`/`diff_inp.py`；且该 TOC **含 `inputcard_mcp` 但不含 `source_sampler`** → 与"当前部署的 1.7.5（AI-MCP 批已进、SDEF 批未进）"**吻合**） | ① `_keep_py` 白名单**没有自动闸门**（TD-02 的机制根因）——而**现成的判据其实就在构建产物里**：TOC 直接给出"最终包里有哪些模块名"；② 无闸门 ⇒ 同类缺口**已复发两次**（`material_library`/`gpu_pref`）且第三次（`diff_inp`）无人发现；③ 该 TOC 目前只能靠人肉读 | **P2** | `grep -n "'lattice'\|'app.lattice'\|app\\\\lattice.py" gui/build/mcnp_sidecar/{PYZ,COLLECT}-00.toc`（10 秒可复现本人结论） | 明晚随 TD-02 一起做：新增 `tests/integration/test_sidecar_spec_keep.py`，**三向集合断言** = `_keep_py ∪ _keep_dirs` × `MCNPHandler.handlers` 覆盖到的 `_import_app("x")` × **PYZ/COLLECT TOC 的模块名集合**；缺一即红 | tester + engineer-backend | — | 否（但**是 TD-02 的根治手段**） |

**覆盖核对**：t1 的 **M-01…M-23**、t2 的 BE-01…BE-25 + 3 相邻发现、t3 的 FE-01…FE-22 **全部落入上表**（34 行）。合并关系：TD-01(M-18,M-15)｜TD-02(BE-05,M-19)｜TD-05(BE-04,M-05,M-06,M-07-MCP半)｜TD-06(FE-01,FE-02)｜TD-08(FE-21,FE-21a,M-14)｜TD-10(M-01,M-02,M-03)｜TD-13(M-08,M-09)｜TD-14(M-10,M-11,M-12,M-13,M-17,M-07-版本半)｜TD-15(BE-06)｜TD-16(FE-03,FE-04,FE-05,FE-06,**M-22,M-23**,Q7/D3)｜TD-19(FE-13,FE-14)｜TD-22(BE-12)｜TD-23(BE-10)｜TD-25(BE-13,BE-18,BE-19,BE-21,BE-24)｜TD-26(BE-16,BE-17,BE-20,BE-25,+3相邻)｜TD-27(FE-11,FE-12,FE-15,FE-16,FE-18,FE-19,FE-20)｜TD-28(FE-17,FE-22,BE-21)｜TD-29(FE-07,BE-14,**M-21**)｜**TD-33(M-20)**｜**TD-34（PM 提供的构建 TOC 证据成条）**。

---

## 3. 严重度分布与改判清单

| 严重度 | 条数 | 债ID |
| :--- | ---: | :--- |
| **P0（已证实）** | **0** | — |
| **P0 候选（待验证/打包即触发）** | 2 | TD-02（待 runtime）、TD-03（打包即 P0） |
| **P1** | **23** | TD-02/03/04/05/06/07/08/09/10/11/12/13/14/16/17/18/19/20/21/22/23/24/32（其中 TD-02/03 同时计入 P0 候选） |
| **P2** | **11** | TD-01/15/25/26/27/28/29/30/31/33/**34**（另含 P2 级**子项**：TD-08 的 `getClosureStatus` 死导出、TD-16 的 ②③、TD-28 的 1.26 三处） |
| **P3** | 子项级 | TD-25 死符号、TD-26 fmesh 死分支、TD-27 的 FE-11/FE-16/FE-18/FE-19、TD-28 的 1.26 活路径部分 |
| **合计** | **34** | 34 行主表条目（由 72 条成员原始条目 + PM 提供的新证据成条 1 条合并而来） |

**改判清单（原判 → 改判 + 理由）**

| 条目 | 原判 | 改判 | 理由 |
| :--- | :--- | :--- | :--- |
| M-01/M-02/M-03 | P0 | **P1** | 记忆滞后不产生用户可见错误/数据丢失/门禁红；属"误导后续开发" |
| M-04 | P0 | **P1** | 同上，且"当前工作区真实状态"无法核实（待验证）；按 §1.3 无台账底为 P1 |
| M-16 | P0 | **P1** | 20 条零登记提交 → 误导后续开发 + 无台账；非用户可见错误；但它使其余记忆债持续复发，处置优先级仍列**最高之一** |
| BE-01 | P0 | **P1** | 全仓**零调用方/零测试** → 当前无用户可见错误；属"活跃注册的假功能 + 契约谎报" |
| BE-02 | P0 | **P1 + 发布阻断** | 功能未打包 → 当前零实害；打包即 P0。严重度与"是否阻塞发布"分开写正是为此 |
| BE-05 | P0 | **部分不成立 → P1** | `analytic_slice.py` **在** `_keep_py:19` 且已在部署目录（指控半条错）；`lattice.py`/`diff_inp.py` 成立但 runtime 未能证实 → 不参与 P0 定级 |
| BE-06 | P1 | **P2（主机制不成立）** | 我逐行复核 `_sections_to_deck`→`deck_from_json:1347-1348` 链路，`universe_comments` **不会丢**；残余为未映射键 + 死函数 |
| FE-07 | P1 | **P2** | 纯注释漂移、实现正确，且 t2 对同一处判 P2 |
| FE-17（1.26 活路径部分） | P2（t3 判"可能静默取错值"） | **P3** | 我实读 `api_server.py:3418-3431`：`subPitch` **恒下发**，三处 1.26 全为不可达防御；真债是 8 处 pitch 副本（TD-28，P2） |
| FE-01 | P1（"名不符实"） | **部分不成立 → 维持 P1** | `golden.expected` 被**真实 Python 函数**断言（`test_lattice.py:668-689`）→ 跨语言锁真实存在；成立的是"守卫可静默失效"（FE-02），且**历史上已发生过一次** |

---

## 4. PM 指定的四条必裁决项 —— 结论

### 4.1 D-BE-02（→ **TD-03**）：P0 是否成立？

- **证据成立**：我在 `app/generator/distributions.py` 逐行确认——生产者 `_parse_ds:97,104-105` 只产 `{type,param,distributionIds}`；消费者 `_resolve_ds` 的 **Q `:676-683` / L `:692-696` / H `:697-707`** 与 `resolve_ds_t:710-718` **全读 `values`**（恒空），只有 **S `:684-691`** 读 `distributionIds`（可用）；`DeckContext.tsx:33` 与 `DistributionEditor.tsx:287-292` 同样只有 `distributionIds`；4 个单测（`:126/132/138/144`）手写解析器**永不产出**的形状。
- **裁决：P0 不成立（当前形态），改判 P1 + 发布阻断项。** 依据：P0 要求"用户可见的错误结果"——而该功能（SDEF 演示）**未进用户安装包**（TD-01 已实证），故对当前用户**零实害**。同时**不降为 P2**：它不是可维护性问题，而是"真实数据路径会静默给出语义错误结果"的缺陷，且违背 S1 明确决议（"做全不降级、有错就地报"）。
- **严重度与"是否阻塞发布"分开写**：**严重度 = P1；阻塞发布 = 是**。含义：下一次打包（含该功能）**必须在打包前修**，否则该功能上线当天即为 P0。
- **附加要求**：修复必须补一条**走真实解析路径**的回归（`parse_distribution_lines(["DS1 Q 2 5 3 10 4"])` → sampler），否则等于继续用假绿测试锁住 bug。

### 4.2 FE-21c（→ **TD-07**）：该不该升 P0？

- **证据成立**（我实读整文件）：指纹 = 三个**长度**（`:39`），内容变而长度不变即早退（`:56`），`report` 非空就一直返回旧结果；`useCallback` deps `[report]` 却读 `fpRef.current`（`:76`）。
- **裁决：不升 P0，维持 P1（强 P1）。** 判据（可复用）：
  1. **输出危害等级**：它只影响「封闭性自检列的显示结论」，**不参与 INP 生成/输运**，不产生错误产物、不丢数据 → 未达 P0 的"用户可见错误结果"中最重的一类（错误产物）。
  2. **触发条件**：需"同长度编辑"（如材料号 1→2）**且**用户之后不再做长度会变的编辑。
  3. **兜底/告警**：无告警（这点对定级不利），但**有 loading 态与既有的"点 3D 预览才刷新"交互契约**，用户可主动重开预览；**降级为 P1 靠的是"影响面是辅助提示"，不是"有 loading 态"**（loading 只在刷新期间出现，不构成兜底）。
  4. **已发货性未证实**：该模块属 09-09 批次，是否进用户 1.7.5 包**未验证**（构建时点无法静态确定）。
- **升 P0 的触发条件**：① 若产品把该列当作"可提交/可运行"的**门禁式**提示（用户据此判断能否导出）→ 升 P0；② 若证实该结论会**随生成的 INP 一起被信任**（例如用户据此省略自检）→ 升 P0；③ 若把"无告警"视为不可接受 → 至少补一句显式"报告可能过期"提示后再谈定级。

### 4.3 FE-01 / FE-02（→ **TD-06**）：静态证据能支持到哪一步 + 升 P0 的前置条件

- **静态能支持的三步**：
  1. **t3 的核心指控部分不成立**：`golden.positions[].expected` **不是**"无后端产出"——`tests/unit/test_lattice.py:668-689` 用**真实 `expand_positions`** 逐位断言同一 golden；`test_nested_golden_cross_language:692+` 同构（用真实 `compose_lattice_tree`）。⇒「TS 重抄 ↔ golden ↔ 真实 Python」三步构成**真实跨语言锁**，而非"TS 自说自话"。
  2. **成立的部分（两类静默失效）**：① TS 侧 `hasGolden`（`:424-427`）读**被测对象自身** → 键名变更即静默 skip 而门禁仍「0 failed」，**且该失效历史上已真实发生**（`docs/qa-report-total.md:69`：该用例曾因键名错**恒 skip**）；② Python 侧 `_golden_positions_hex_fresh`（`:651-665`）不满足即 `continue`（`:679`）→ hex 样本**静默不校验**；文件/段缺失即 `pytest.skip`（`:670-675`）。
  3. **静态无法定论的**：当前 vitest/pytest 的 **skipped 计数**（本会话无 shell，且本次审计禁跑），也就是"锁现在到底有没有生效"。**不得因无法验证而拔高。**
- **裁决：维持 P1，不升 P0。** 因为"跨语言闸门是否存在"目前**静态成立**（两侧断言都在、golden 段齐备：我核对 `leafCount:10`、`leaves[]`、`composeCases[0].node` 均实存）。
- **升 P0 的前置条件（三个，满足任一即可升）**：① 实机跑出该用例 **skipped**（`vitest --reporter=verbose` 的 skipped 列 > 0，或 `pytest -k golden -rs` 出现 skip）；② 出现"两侧同时漂移且门禁全绿"的**实测案例**（例如按 TD-28 改 pitch 后只剩 TS 侧红）；③ 证据显示 `latticeGolden.json` 曾被**手改而非由实现产出**（但注意：手改会被 Python 侧断言抓住 → 只有"连同 Python 实现一起漂移"才成立）。
- **处置**：立即加硬断言 `expect(hasGolden).toBe(true)` + **把 skipped>0 视为门禁失败**；排期补 `expected_python` 兄弟字段（与 TD-28 同批）。

### 4.4 D-BE-01（→ **TD-04**）：严重度与是否阻塞发布

- **证据成立**（我实读 `generate_step.py:5-17`、`api_server.py:2597-2617`、`:1446`、`api.yaml:657-687`）。
- **裁决：P1，不阻塞发布**（t2 判 P0 → 改判）。理由：
  1. **无调用方**：全仓 grep 只有 api.yaml / api_server / spec / docs / 该文件自身命中 → GUI、MCP、测试**都不调用**它，故"看起来能用"目前**只对未来的外部调用方成立**，不是正在发生的用户可见错误。
  2. **它是"假功能"，但不是"已交付的假功能"**：没有任何入口把用户引到它（区别于 TD-05 的手册路径——那里有明确的用户动作路径，故 TD-05 保持 P1 且处置更急）。
  3. **PM 提示"可能已存在多个版本未被发现"**：确实——`docs/backend-changes.md:1026`（T11）在批量重构时已把 `generate-step` 当"正常惰性 import 点"处理，说明该 stub **在此之前就已被当作正式实现对待**，这正是"假功能长期潜伏"的证据；但"潜伏"本身不改定级，改的是**处置优先级**：建议**优先删端点**（三选一里的方案②），因为它同时清掉 api.yaml 契约谎报、`mcnp_sidecar.spec:40` 的打包项与 `--open` 的坏路径（`gui/backend` 三级 `..` → `D:\MCNP`，永不命中）。
  4. **升 P0 的条件**：一旦确认存在**应用外消费者**（例如某 AI 客户端按 api.yaml 调它并据此认为 STEP 已生成）→ 升 P0。

---

## 5. 待 PM 裁决问题（4 条）+ 已裁决事项（原 Q10，见 §0.1）

### Q1（对应 TD-02，**最高优先**）：要不要现在实测安装版 sidecar 的 `lattice` / `diff-inp` 端点？

- **A. 实测**（起/复用 5001 打只读请求）：能**一次定论**是否真 500；代价是必须处理 5001 占用（§6 坑：SO_REUSEADDR 允许多进程同绑），可能要**结束用户正在用的打包版后端**，属"起停服务"动作 —— 与本次 t4 的只读纪律冲突，需要你授权**另派一个任务**在可控窗口做。
- **B. 不实测，直接补 spec 并把验证并入发布前冒烟**：`_keep_py` 补 `lattice.py`/`diff_inp.py` **本身无风险**（多打两个数据文件即消除风险），再在下次打包后用 `/api/lattice-extent`、`/api/diff-inp` 做冒烟。
- **reviewer 推荐 B**：用"补 spec + 冒烟"消除风险，避免在审计期间动用户运行环境；但**必须在发布检查单里固化这两个端点的冒烟**（否则同类缺口会第三次复发——`material_library`/`gpu_pref` 已复发过两次）。

### Q2（对应 TD-03）：DS 键错配的修法 + 与发布的关系

- **A. 修正解析侧（`_parse_ds` 另填 `values`）+ 补真实解析路径回归**，与 SDEF 演示功能**同批打包**；优点：一次到位、语义与 C810 一致；代价：要定 `param` 与数值的关系（Q 卡无 param 的设计缺陷需一并处理）。
- **B. 只收敛读侧（Q/L/H/T 改读 `distributionIds`）+ 遇到不支持的形态就地报错**（符合"有错就地报"）；优点：改动最小、最快解除发布阻断；代价：`Q` 的"V1 S1 V2 S2"语义仍需专门映射，报错分支会比 A 更容易触发（用户可见报错变多）。
- **⚠️ v1.1 更新：B 已不足以覆盖本债**。我新增发现 `_parse_ds:104-105` 会把 `toks[0]` 挪进 `param`，使得 **S 分支的 J 列表右移一位**（`DS1 S 2 3` 索引 0 取到 3）——**只改读键修不好 S**。故 A/B 都必须叠加"**裁定 `param` 语义 / J 列表起点**"这一步（按 C810），并以 `["DS1 S 2 3"]` 走真实解析路径的用例作为验收。
- **reviewer 推荐 A（主）+ B（兜底）**：先按 A 修正解析，再把无法归一的形态**显式报错**而不是 continue 到 default；无论选哪个，**必须补走真实解析路径的用例**，否则假绿测试会继续把 bug 锁死。

### Q3（对应 TD-06/TD-28）：跨语言锁的加固范围与批次

- **A. 只加硬断言（`expect(hasGolden).toBe(true)`）＋ skipped>0 即失败**：半天工作量，立刻消除"整条闸门静默消失"。
- **B. 同时补 `expected_python` 兄弟字段 + 收敛 8 处 hex pitch 副本**：根治"两侧同时漂移"，但要动 `tests/unit/test_lattice.py`、golden 写盘方式与 `app/lattice.py`（**属测试/生成器行为，须明派**）。
- **reviewer 推荐：A 立即做 + B 单独派工（Owner: engineer-backend，与 TD-28 同批）**；B 不做的话，TD-06 的锁在下次改 pitch 时仍会被绕过。

### Q4（对应全表定级）：是否采纳我的 10 条改判？

- **A. 采纳**（M-01/02/03/04/16 由 P0→P1；BE-01 P0→P1；BE-02 P0→P1+发布阻断；BE-05 部分不成立→P1；BE-06 P1→P2；FE-07 P1→P2；FE-17 活路径 P2→P3）：口径一致、不误伤、与 PM「不为凑数拔高」的要求一致；代价是 P0 计数从 6（t1 5 + t2 3 − 重叠）降为 0。
- **B. 保留成员原判**：可保住"P0 数量"的表观紧张度；代价是两份口径并存（同一债两个级别），且与本次批准的定级口径冲突。
- **reviewer 推荐 A**，并在处置顺序里用**「阻塞发布」列**保住急迫性（TD-02/TD-03 都在"是"）。

### Q5（对应 TD-01/TD-11/TD-12）：处置批次与"提交即登记"纪律

- **A. 先止血三件套**（① TD-02 补 spec + 加 `test_sidecar_spec_keep.py`；② TD-05 清幽灵参数与 5 处文档；③ TD-17 加 `typecheck` 脚本）→ 再补记忆/文档（TD-10/12/13/14）→ 最后清代码债（TD-16/25/26/27）。止血三件套都**不依赖 runtime、不触碰业务逻辑**，可并行、当天可完成。
- **B. 先重打包发布**（把 TD-03 修完随 SDEF 演示一起发）：用户最快拿到 TODO #6，但会把 TD-02 的未知风险带进发布。
- **reviewer 推荐 A → 再评估 B**；并建议**固化两条纪律**：① 批次结束必记 commit 短号或待提交文件清单（治 M-04/M-16）；② 记忆写明"**已提交 commit / 已打包版本 / 部署校验**"三态（治 M-15/M-18）。

### ~~Q10~~ → **✅ 已由用户裁决（2026-09-10），不再是待裁决项**

用户原话：「**外无限是允许存在的，仅提示感叹号即可，唯有曲面不封闭是禁止的**」。

- **裁决结果**：采纳**方案 B 的精神 + 深模块判据** —— ① 封闭 = 正常；② **外无限 = 允许存在，展示"感叹号"级提示**（**不是**红色错误）；③ **曲面不封闭 = 禁止 / 错误级**。
- **落地口径（明晚可直接照此派单）**：以 `gui/src/utils/cellClosure.ts:41-48` 的 `allowed:true` 为准；`gui/src/components/CellEditDialog.tsx:50-58` 的红色错误态是**待清理的第三份映射**；三处映射统一为三档语义，并让 `CellEditDialog` 改走 `useCellClosure` 收敛（TD-32）。
- 原三方案（A 纯正常 / B 注意 / C 红色错误，见本报告历史版本）**作废**：用户的裁决落在"允许 + 感叹号提示但非错误"，且**额外钉死了第三档**（不封闭 = 禁止），这正是防止三处映射再次分叉的关键。

---

## 6. 我未能验证的部分（**必读：以下均为"未验证"，不得当作结论引用**）

1. **所有需要运行的东西**：本会话**无 shell 工具**，因此**没有**跑 pytest / vitest / tsc / vite build / PyInstaller / tauri build；也没有跑任何 HTTP 请求。
   ⇒ 以下问题**本次审计无法定论**：门禁是否真绿、是否含未察觉的 skip（FE-01/02 的升级前提）、`colorize` 实际失败率（TD-18）、`test_tech_debt.py` 等 14 处 docstring 对应用例的真实红绿（TD-09）、并发竞态是否可复现（TD-20）、fmesh 重复回放是否真触发（TD-26）、plan perf 占比（TD-25）。
2. **打包版运行时表现**：`python.exe` 内的 **PYZ 无法静态读取**，故 `_import_app("lattice")` / `_import_app("diff_inp")` 在冻结环境**是否真的 ImportError** 未定论（TD-02 因此保留"部分成立"）。**v1.3 补充**：PM 提供的**构建 TOC**（我已独立复核，见 §8.8）把静态链条从"2 条"加到"3 条"且方向一致，但 **TOC ≠ 运行期证明**（它证明"包里没有顶层 `lattice` 名"，不证明"运行时一定 import 失败"，例如冻结导入器是否有未被我掌握的兜底）；且 `gui/build/` 的 TOC 是否**就是当前部署那次**构建仍需旁证（我看到的旁证是"含 `inputcard_mcp`、不含 `source_sampler`"＝与 1.7.5 吻合）。⇒ **仍以实机一条请求定案**。（t1 曾试二进制串探测并因对照探针失败而放弃，我认同该手段不可靠，未重试。）
3. **当前工作区真实未提交状态**：无 `git status` / `git diff`；M-04 的"分布 v2 是否被夹带进无关主题提交"需 `git show`（`.git/logs/HEAD:275-276` 显示 `+ misc prior uncommitted work` 后紧跟 `reset`，**疑点保留**）。
4. **部署版构建时点**：只能证明"早于 4f0798fa（SDEF 批次）"（部署缺 `source_sampler.py`），**无法证明**是否含 09-09 的封闭性/参数扫描/源项 adv 批次 → TD-07 的"已发货性"因此未定。
5. **未独立复核的条目**：TD-13、TD-19、TD-20、TD-25、TD-26、TD-27、TD-30 及 TD-08 的部分子项，我**未逐条打开 file:line**，仅确认成员证据格式完整（含 file:line 与代码引文）；按 §1.5 **不用于 P0 定级**。
6. **外部权威**：未访问 `D:\MCNP\MCNP6\C810.pdf`，凡以该 PDF 为据的语义结论（如 SI 只有 H/L/A/S、DS 卡形态）本次**未复核**，仅引用记忆与代码自述的一致性（TD-24 因此只是"与记忆一致"，不是"与 PDF 一致"）。
7. **PM 报告的"待实机验证"项**：`D-BE-05`（打包版必 500）我做了文件级复核但**未做 runtime 复核**（见第 2 点）；PM §1.11 的四项实机验证清单本次**全部仍未验证**。
8. **未做的**：未修改任何代码/记忆/既有文档；未装依赖；未起停任何服务；未杀任何进程。

---

## 7. 建议的处置顺序（**明晚照单派单用**；今晚不执行任何一条）

> **前置声明**：用户已定「今晚只做审计，不做修复」⇒ 本节是**给明晚的工单依据**，不是本次交付的施工。每条都标了「前置条件 / 最小验证 / 可否并行」，便于直接派单。

- **第 0 步（明晚第一件事，必须先做）**：**TD-02 实机定案** —— 先 `Get-NetTCPConnection -LocalPort 5001` 确认无旧进程劫持；再直跑部署版 sidecar 起后端，对 `/api/lattice-extent`、`/api/preview-lattice`、`/api/validate-lattice-surfaces`、`/api/diff-inp` **各发一次只读请求**并记录状态码。
  - **若 500 / `No module named 'lattice'`（或 `diff_inp`）⇒ TD-02 立即升 P0**，第 1 步的 spec 补齐变成**发布阻断项**；
  - **若全部 200 ⇒ TD-02 降为"机制债（TD-34）"**：spec 白名单仍要补闸门（防第四次复发），但不再阻塞发布，且 `lattice.py`/`diff_inp.py` 的"漏项"结论结案为"无实害"。
  - 依赖：**无**（可与其他步骤并行，但结论会影响第 1 步的优先级）。
- **第 1 步 · 止血（不依赖 runtime 结论即可做，建议并行）**：
  - TD-02/34：`diff_inp.py` 进 `_keep_py`（`lattice.py` 视第 0 步结论）+ 新增 `test_sidecar_spec_keep.py`（**三向集合断言**：`_keep_py ∪ _keep_dirs` × `_import_app(...)` 实际用到的模块 × **TOC 模块名集合**）。
  - TD-05：`mcnp_bridge.py` 加显式 `--mcp-server` 分支（`sys.exit(2)`，**绝不 fallthrough**）+ 清 5 处文档/注释（含"教用户 pip install"那条）。
  - TD-17：加 `tsconfig.test.json` + `typecheck` 脚本（零新依赖）。
  - **前置条件**：无；**可否并行**：三条互不冲突，可 3 人同时做。
- **第 2 步 · 发布阻断（随下次打包，且必须先修完再打包）**：TD-03（DS 键错配 + **`param`/J 起点裁定** + 真实解析路径回归）；TD-31（同功能的契约签名修正，建议同批）。**发布前冒烟必须含** `/api/source-demo-sample`、`/api/lattice-extent`、`/api/diff-inp`。
- **第 3 步 · 闸门可信度（可与第 2 步并行，因为都改测试面）**：TD-06（硬断言 + skipped>0 即失败）、TD-09（清 14 处反向 docstring）、TD-18（flaky 移出货门禁）、TD-08（`api.yaml` 加 enum + HTTP 用例）。
- **第 4 步 · 记忆与文档**：TD-12（补 20 条登记）→ TD-10（口径）→ TD-14（契约/架构/待办）→ TD-13（逐批档案）→ TD-11（工作区状态 + 两条纪律）。
- **第 5 步 · 代码债清偿**：TD-16（删死代码 + 同步 16 处文档，**一码一文同批**）→ TD-23（僵尸字段退役三步）→ TD-24/TD-22/TD-21 → TD-15/TD-19/TD-20 → TD-25/TD-26/TD-27/TD-28/TD-29/TD-30/TD-31/TD-33。
- **第 6 步 · 已裁决项落地**：TD-32（用户已裁决：封闭=正常 / 外无限=允许+感叹号 / 不封闭=错误；统一三处映射并让 `CellEditDialog` 走 `useCellClosure`）。

---

## 8. 修订记录（v1.1 → v1.4）—— 并入成员回执、t1 v5、PM 的构建产物证据与 t2 v8 冻结账目

> engineer-backend 已按 t4 的请求把 3 项补足写入 `docs/audit/t2-backend-debt.md` §四，并在其中**自我更正**、**提出 1 条新发现**。以下为我对该回执的逐项处置（**只采纳经我打开 file:line 核实过的部分**）。

### 8.1 采纳的两处更正（t2 自认，我复核确认）

| 项 | t2 原述 | 更正后 | 我的复核 |
| :--- | :--- | :--- | :--- |
| BE-05 的"漏项"清单 | 声称 `analytic_slice.py`、`diff_inp.py`（摘要版还有 `stl_cross_section.py`）"均未列入 `_keep_py`" | ✅ **只有 `diff_inp.py` 是实存漏项**；`analytic_slice.py`（`spec:19`）与 `stl_cross_section.py`（`spec:28`）**都在 `_keep_py` 内** | **确认**（我实读 `gui/mcnp_sidecar.spec:17-31`；部署目录亦存在 `analytic_slice.py`）。已在 TD-02 行改写 |
| 覆盖来源 | 隐含"进 `_keep_py` 是唯一防线" | ✅ 覆盖来源有**三条**：`_keep_py` / `_keep_dirs` / **PyInstaller 静态 import 图**；"不在 `_keep_py`"≠"打包版用不到" | **确认**（这正是 `lattice.py` 能否用的争点，见 8.2） |

**由此 TD-02 的定级依据一并调整**（我采纳 t2 的改法）：本债的根不是"当前漏了 N 个"，而是「**白名单靠手写 + 零自动闸门 + 历史上已复发两次**」（`PROJECT_MEMORY.md:97` 记 `material_library` / `gpu_pref` 曾漏 → 端点 500）。`diff_inp.py` 只是当前那一例。严重度仍 **P1（证实即 P0）**。

### 8.2 保留的争议：`lattice.py` 到底能不能在冻结环境 import（**唯一未共识项**）

- **t2 主张**：`lattice.py` 虽不在 `_keep_py`，但靠 `inp_generator.py:9` / `parsers/core.py:18` 的 `from app import lattice` **静态边**进了 PyInstaller 模块图 → 打包版可用；因此 `_keep_py` 不是唯一防线。
- **我持保留（未推翻、也未采信）**：该静态边注册的模块名是 **`app.lattice`**（包内子模块），而 `api_server._import_app("lattice")` 执行的是 **`__import__("lattice")`**，取的是**顶层名 `lattice`** —— 二者在 PYZ 的 toc 里不是同一个条目；且部署全树 2301 条路径中 `lattice` **零命中**。
- **结论**：**只能 runtime 定论**（一条 `POST /api/lattice-extent`）。这也正是 TD-02 仍标"部分成立/待验证"、不升 P0 的原因。**注意：无论哪种结论，`diff_inp.py` 的漏项都成立**（它是**纯动态** import，没有任何静态边可救）。

### 8.3 驳回 1 条"新发现"：t2 §4.2 的「`pos_index` 参数不可达」**不成立**

t2 §4.2 称：`source_sampler.py:96-116` 的 `_erg(self, rng, pos_index)` 依赖 `pos_index` 走 `ERG=FPOS Dn`，但"全仓库 grep `_cell_refs_pos` 零命中、`sample_source` 内无传该实参的调用点"⇒ 即便修好键错配 FPOS 链仍不可达，需第 3 步接线。

**我实读后判定不成立**：
- `app/generator/source_sampler.py:67-68` 明确写着 `pos, pos_index = self._position(rng)` → `erg = self._erg(rng, pos_index)` —— **实参已接**；
- `_position()`（`:188-214`）在 **POS=Dn 多点源**分支 `:203-204` → `_sample_pos_dist()`（`:216-228`）末尾 `return tuple(...), idx` —— **返回的就是真实位置索引**（其余模式返回 `None`，此时 `_erg:107` 取 `0.0`，与"只有单一位置、索引 0"的语义一致）；
- `_cell_refs_pos` 零命中**与本题无关**（该符号不是这条链路的机制）。

⇒ **不必新增"接 `pos_index` 实参"这一步**；TD-03 的三步处置改为「键口径 + `param`/J 起点裁定 + 真实解析路径回归」（见 TD-03 行与 §5-Q2）。**若不驳回，会把一条不存在的返工项写进发布阻断清单。**

### 8.4 我新增的发现：`_parse_ds` 的 `param` 偏移 → **S 分支也错**（TD-03 加深）

- `_parse_ds:104-105`：`ds["param"] = toks[0]`、`ds["distributionIds"] = toks[1:]`。
- 而 `app/docs/源分布卡说明.md:175` 写 `DSn S S1 … Sk`（**S 无独立 param 字段**）⇒ 解析后 J 列表整体右移：`DS1 S 2 3` → `param="2"`、`ids=["3"]` → **索引 0 取到分布 3（应为 2）**。
- **这与该分支自己的单测契约直接矛盾**：`tests/unit/test_distribution_sampler.py:119-122` 的 `test_ds_s_by_index` 认定 `ids[0]` 即索引 0。⇒ **"只有 S 分支可用"这一（t2、PM 与我 v1.0 共同的）前提不成立**；S 同样是待修分支。
- 两份派生文档亦自相矛盾（`app/docs/C810_卡片格式详细.md:183` 写 `DS[n] var Dn1 Dn2 …`，含 var 字段）→ **J 列表起点须以 C810.pdf 裁定**（本次未访问，标「待 C810」）；但"与自身单测契约不一致"这一点**无需 PDF 即成立**。
- 影响：TD-03 的修复**不能只改读键**，"只收敛读侧（原 Q2-B 方案）"已被证不足；已同步改写 TD-03 行与 §5-Q2。

### 8.5 其余口径对齐（无实质分歧）

- **条数**：采用落盘文件口径 **25 条（BE-01…BE-25）+ 3 条相邻发现 + 10 条存疑**（任务 output 摘要被 2000 字符截断，`D-BE-13…D-BE-18` 中段"不在摘要里 ≠ 不存在"）。我 v1.0 全部主表条目已按 `BE-NN` 编号引用，**无需重编号**；已把"2 条相邻发现"改为 3 条（新增 TRCL 绕 Z 两端口径不一致，并入 TD-26 相邻族）。
- **BE-01 的判准**（t2 请我明确）：我采「**用户是否被误导 / 是否存在用户可见错误**」为判准 → 因**全仓零调用方**，判 **P1**；若改采"契约承诺了不存在的能力 + 假功能"为判准，则维持 P0。**我在 TD-04 行明示了所采判准**，PM 若要换判准，TD-04 随之升级，不需要重排其余条目。
- **性质标注**（t2 §4.1 的 A/B 分类）与我的 §1.5「复核结论」列**互为补充**：我额外区分了"我亲自打开核实"与"未复核"，两者都标"无 shell 推断"的条目本次**一律不参与 P0 定级**。

### 8.6 v1.1 未改变的结论

§0 的独立结论不变（**未发现已证实的 P0**；2 条候选均按 P1 + 阻塞发布）；32 条总表结构不变；10 处改判不变；Q1/Q3/Q4/Q5/Q10 不变。**唯一变化**：TD-02 的成立范围收窄（只剩 `diff_inp.py` 硬 + `lattice.py` 争）、TD-03 的修复范围**扩大**（S 分支 + `param` 裁定）、并**驳回** t2 §4.2 的第 3 步接线项。

---

### 8.7 v1.2 追加 —— 并入 t1 v5 的 M-18…M-23 与 §6/§9 提示

researcher 已落盘 t1 v5（**23 条 M-01…M-23**；我此前引用的是更早的 output 快照 17/19 条）。处置如下：

| t1 v5 项 | 我的处置 | 说明 |
| :--- | :--- | :--- |
| **M-18**（HEAD 功能未进安装包） | **已并入 TD-01**（我 v1.0 即已引用，并自行复核了文件级 + 目录级证据） | 我额外确认了部署全树 `source_sampler` 零命中 |
| **M-19**（spec 动态导入缺口） | **已并入 TD-02**（v1.1 已按 t2 §4.4 收窄到 `diff_inp.py` 硬 + `lattice.py` 争） | t1 与我同判"`from app import lattice` 注册的是 **app.lattice** 而非顶层名"，与 t2 §4.4 主张相反 → 争议保留至 runtime |
| **M-20（新）** | **新增 TD-33**（P2）——测试文件数与实测不符 + **更正 t3 的 81 个（61+19+4=84≠81 自身不自洽）** | 我据此把 TD-17 里"82 个测试文件"的表述改为**不引用具体数字**（只保留"整个 `gui/test/**` 不在 tsc 内"这一事实），避免把未定论的计数写进结论 |
| **M-21（新）** | **并入 TD-29**（与 T2 BE-14 / T3 FE-07 同根因，**不重复计条** ✅ 与 t1 §6.4 提示一致）；并把残留处数由 4 扩到 **16 处**（含**契约 L1 锁死表** `lattice-fix15-design.md:450`） | 我在 TD-29 加了一句：**若 PM 认为"L1 锁死表写错公式"属契约债，可回 P1**（当前仍判 P2：实现正确、纯漂移） |
| **M-22（新）** | **并入 TD-16**（与 FE-03 是"同一现象的两半"：代码侧删文件 + **16 处文档**把它当生产消费方） | 采纳 t1 定性"**落地后被内联取代**"（取代**时点**需 `git show` → 列入未验证） |
| **M-23（新）** | **并入 TD-16**（与 FE-06 一码一文） | 采纳 t1 的 FE-06 结案建议，写进 TD-16 处置 |
| **§6.3 TRCL 提示** | **采纳，作为降级依据**：T2 的"TRCL 归一化两端口径不一致"**唯一触发点**在 `Preview3DLattice.tsx:272`，该文件已确认零 import → **当前生产不可达**，随 TD-16 同批关闭 | **但**t1 与我一致：其**另一半**（后端 `app/lattice.py` 对 TRCL **无** `%60/%90/%360` 归一化、前端 `parseTrclDeg` 有）是**独立代码异味**，删文件后仍存在 → 保留在 TD-26 相邻族内、标 P3，**不因删码而注销** |
| **§9 证据类型** | 与我的 §1.5 对齐：**无 shell 推断类**（`git show` / 部署版 5001 实测 / `git log -p` 时点 / 工作区清单与 mtime / PYZ 内部）**一律标「待验证」、不参与 P0 定级** —— 已在 §6「我未能验证的部分」逐条对应 | 我与 t1 的方法学一致（t1 亦试过 PYZ 二进制串探测并放弃，我未重试） |
| **§8「已核实已清偿」** | **原样采纳 8 条中 7 条**（api.yaml 49/49 无漂移、`release.bat`/`scripts/release.ps1` 已删且部署全树 `*.bat` 零命中、AI 接入正口径、`mcp_bridge.py:53-57` 实现正确、ADR 未改名、F#1~F#7 已清偿、格阵空 STL 闭环） | ⚠️ **第 8 条我提出异议，见下** |

**⚠️ 我对 t1 §8 第 8 条的异议（本条为 v1.2 的新分歧）**：t1 §8 写「**`source-demo-visualization.md` 契约与实现一致**」。**我判该结论不成立**（至少一处）：契约 `docs/contracts/source-demo-visualization.md:25` 声明 `resolve_ds(eid: int, parent_value: float) -> list[int]`（"返回子分布号列表"），而实现 `app/generator/distributions.py:401-405` 是 `resolve_ds(self, eid, parent_value, parent_si=None) -> dict`，返回 `{"distribution": n}` / `{"value": v}` / `{"default": True}` 三种判别形态 —— **返回类型与参数个数都不同**。我已实读两侧原文（见 **TD-31**，P2）。**建议 PM 派单时把 TD-31 与 TD-03 同一批处理**（同一功能的契约与实现同时要改），并在 t1 §8 该行加"**除 TD-31 所指签名一处外**"的限定。

**v1.2 未改变的结论**：§0 独立结论（**未发现已证实的 P0**）、10 处改判、Q1–Q5/Q10 均不变。**变化**：总表 32 → **33 条**（P2 9 → 10）；TD-16/TD-29 的合并来源与处置面扩大；TD-17 的计数表述去数字；TD-10 采纳 M-01 的 §9 修正。

### 8.8 v1.3 追加 —— PM 提供的构建 TOC 证据（我已独立复核）+ 用户裁决 + 一处再次驳回

**（1）TOC 证据：我逐条复核，结论"成立且方向与静态链条一致"**（已写进 TD-02 与新增 **TD-34**）

| PM 主张 | 我的复核方法 | 结果 |
| :--- | :--- | :--- |
| `PYZ-00.toc` 只有 `app.lattice`、无顶层 `lattice` | `grep "'lattice'\|'app\.lattice'" gui/build/mcnp_sidecar/PYZ-00.toc` | **成立**：仅 2 处命中 = `:638 ('analytic_slice', …)`、`:782 ('app.lattice', …)` ⇒ **无** `('lattice', …)` |
| 对照：`analytic_slice`/`voxel_csg` 等是**顶层**名 | 同上 + `grep "'(voxel_csg\|mc\|models\|diff_inp\|sweep)'"` | **成立**：顶层名 `mc:3512`、`models:3839`、`voxel_csg:12682`；**`diff_inp` 零命中** |
| `COLLECT-00.toc` 没有 `lattice.py`/`diff_inp.py` | `grep "app\\\\(lattice\|diff_inp\|analytic_slice\|coverage_check\|gpu_pref\|material_library\|mc\|sweep\|voxel_csg)\.py"` | **成立**：`:3957 analytic_slice.py`、`:3960 coverage_check.py`、`:4034 gpu_pref.py`、`:4035 material_library.py`、`:4038 mc.py`、`:4100 sweep.py`、`:4101 voxel_csg.py` ⇒ **无 `lattice.py`、无 `diff_inp.py`** |
| 该 TOC 是否就是**当前部署那次**构建？ | 旁证：查 TOC 是否含 1.7.5 批次的 `inputcard_mcp`、是否含 SDEF 批次的 `source_sampler` | **吻合**：含 `inputcard_mcp`（`PYZ:2848`、`COLLECT` 亦在）且**全无** `source_sampler` ⇒ 与"1.7.5（AI-MCP 批已进、SDEF 批未进）"一致。**但这是旁证、不是同一性证明**（无 mtime/manifest），故我仍未据此升 P0 |

**⇒ 裁决**：`t2 §4.4「靠静态边 `from app import lattice` 使 `lattice.py` 可用」的主张，被构建产物证伪**（该边只产生 **dotted** 名 `app.lattice`，而 `_import_app` 取**顶层名**）。**M-19 + BE-05 合并为 TD-02 一条**，其静态链条由 2 条增至 3 条，方向一致。

**⚠️ 但"不判 P0"的理由仍然成立，且我特意查明 PM 指出的那处矛盾的性质**：PM 记忆 `:138`（v1.7.4 打包批）记载"**`python.exe` 直跑后端 5001** + `preview-lattice` U233 `universes STL keys=['1','2','3']` / `subPitch=1.45034`"，`:155` 甚至写"**源码/部署版各跑** `diag_universe_stl.py`"。我与 `:123`/`:127` 对照后认为：该记录属于 **2026-08-28 的 v1.7.4 构建**（且同批 `:127` 还记了 5001 被旧 sidecar 劫持产生**假象**的先例），而**当前部署的是 1.7.5**（含 `inputcard_mcp`、不含 `source_sampler`）——即 **反证与静态链条指向的不是同一次构建** ⇒ 反证**不直接反驳**本链条，但也**不能排除**"冻结环境另有解析路径"（我无 08-28 那次的 spec 快照）。**结论不变：一条只读请求定案**（§7 第 0 步）。

**（2）用户裁决已并入 §0.1**：Q10（`infinite` 语义）→ 三档语义已定（封闭=正常 / **外无限=允许+感叹号** / 不封闭=禁止），**TD-32 从"待用户裁决"改为"待施工"**；理由与落地口径见 §0.1。

**（3）再次驳回 t2 的 `pos_index`「新发现」**：PM 通知里转述了 t2 的"`sample_source` 未传该实参 ⇒ 即便修好键错配 FPOS 链仍不可达（需第 3 步接线）"。**我维持 §8.3 的驳回**，并把证据再钉一次：
- `app/generator/source_sampler.py:67-68`：`pos, pos_index = self._position(rng)` → `erg = self._erg(rng, pos_index)` —— **实参已传**；
- `_position()` 的 POS=Dn 分支（`:203-204`）→ `_sample_pos_dist()`（`:216-228`）末尾 `return tuple(si_vals[idx*3:idx*3+3]), idx` —— **返回真实位置索引**；其余模式返回 `None` → `_erg:107` 取 `0.0`（等价"唯一位置索引 0"），语义一致；
- `grep _cell_refs_pos` 零命中**与该链路无关**（该符号不是它的机制）。
⇒ **TD-03 的处置不含"接 `pos_index` 实参"这一步**；若按未驳回的版本派单，会多出一条**不存在的返工项**。

**（4）其余口径按 PM 通知对齐**：测试文件数 **75 test + 1 snap**（TD-33 已用，t3 的 81 不成立）；`analytic_slice.py`/`stl_cross_section.py` **本来就在 `_keep_py`**（TD-02 已改）；BE-14 ≡ FE-07 ≡ M-21 **同根因只计一条**（TD-29）。

**（5）BE-01 的判准（PM 要求明确）**：**我采「用户是否被误导 / 是否存在用户可见错误」为判准** ⇒ 因全仓**零调用方**，判 **P1**（TD-04）。若 PM 改采「契约承诺了不存在的能力 + 假功能」为判准，则 TD-04 应升 P0 ——**换判准只需改这一条**，不影响其余 33 条。**我的建议**：鉴于该端点**没有任何入口把用户引到它**（区别于 TD-05——那条有"手册教用户敲参数"的明确路径，故保持 P1 且处置更急），维持 P1 + **优先删端点**（顺带清 api.yaml 契约谎报、`mcnp_sidecar.spec:40` 打包项与 `--open` 的坏路径）。

---

### 8.9 v1.4 定稿 —— 并入 t2 v8（BE-26 新增 / BE-06 撤回 / hex pitch 计数）

**（1）BE-26（新增）→ 并入 TD-22，不新增行**：t2 由 T3 的 cross-check 提出并**自行更正了方向**——**宽的是 `/api/parse-inp`**（`asdict(deck)` 起手、不删键，`:2044`；含 9 个前端中间态键 + `_warnings` `:2091`），**窄的是 `_deck_to_frontend_dict`**（MCP `/workspace` 与 `/api/text-to-section` 走的那份，**缺 `_warnings`**）。**我采纳其方向更正**，并修正了我 v1.0 在 TD-22 影响列里写反的一句（原写"`/api/parse-inp` 拿不到 `_warnings`"→ 已改为"`deck_to_frontend_dict` 缺 `_warnings`"）。**暴露面维持 t2/t3 的一致结论**：应用内影响≈0（`/api/text-to-section` 只用 `materials`/`cells`/`tallies` 三子集）；真正受影响的是**应用外消费者**。

**（2）BE-06 撤回 → TD-15 收窄（我与之独立同判）**：t2 §5.1 已撤回该条，**撤回理由与我 §8 前的判断逐条一致**（`_sections_to_deck:92-101` 把整个 dict 交给 `deck_from_json:1347-1348`；`_deck_to_sections:83` 显式回写 ⇒ `universe_comments` **不丢**）。⇒ **TD-15 保留的只是"残余"**（`patch_section` 整份重写会抹掉**非 deck 键** + `_ws_state()` 死函数与 docstring 不符），**P2 不变**；我把行内来源标注为"t2 已撤回"以免后人误当活条。

**（3）hex pitch 副本计数对齐**：t2 v8 复核为 **7 处 / 2 方向**（附逐处行号表），t3 v2 计 **8 处 / ≥3 口径** ⇒ **两数并存，TD-28 取「≥7 处」**（我未独立逐处复核，按 §1.5 不用于 P0 定级）。同时采纳 t2 新增的第③点：**这批副本必须与 TD-06 的 `expected_python` 同批改**，否则加完 golden 仍被副本坑。

**（4）冻结后的最终账目（本版为定稿，不再追加输入）**

| 项 | 值 |
| :--- | :--- |
| 输入清单 | t1 **23**（M-01…M-23）｜t2 **主表 26 行，其中 BE-06 已撤回 ⇒ 有效 25**（BE-01…BE-26；P0 2 / P1 8 / P2 12 / P3 3，存疑 10，相邻 3＝其中 TRCL 已裁决）｜t3 **24**（FE-01…FE-22）｜PM 证据 1 条 |
| **t4 合并总表** | **34 行（TD-01…TD-34）**：**P0 已证实 0 / P0 候选 2（TD-02、TD-03）/ P1 23 / P2 11（含 P3 级子项）** |
| **阻塞发布** | **是：TD-02、TD-03**（其余 32 行为否） |
| 改判 | 10 处（§3 清单） |
| 我独立新增 | 2 条（TD-31 契约签名；TD-03 的 `param` 偏移致 S 分支亦错） |
| 我驳回成员结论 | 2 条（BE-06 主机制——**t2 随后自行撤回**；t2 §4.2 `pos_index`——**t2 随后自行撤回**） |
| 我提出异议 | 1 条（t1 §8 第 8 条"source-demo 契约一致"→ TD-31） |
| 待 PM 裁决 | **4 条**（Q1–Q5 中的 Q1/Q2/Q3/Q4/Q5 → 去掉已裁决的 Q10；详见 §5） |
| 我未能验证 | 8 类（§6） |

**（5）本节新增的未验证项**：无（BE-26 为纯文档/docstring 判断，BE-06 撤回为纯静态核实，hex pitch 计数为成员自核 —— 三者均**不引入新的待验证项**）。

---

> 审计人：**reviewer**（AgentTeams `tech-debt-audit`，任务 t4）｜**v1.4 定稿（并入 PM 的构建 TOC 证据 + 用户已裁决 Q10 + t2 v8 冻结账目）**
> 结论：**未发现已证实的 P0；2 条 P0 候选（TD-02 待 runtime、TD-03 打包即触发）均按"P1 + 阻塞发布"处理**；共合并出 **34 条债**（P1 23 / P2 11 / P3 若干子项），来源覆盖 **t1 23 条 + t2 26 行（撤回 1，有效 25；+3 相邻）+ t3 24 条（+FE-22）+ PM 提供的 TOC 证据 1 条**；**推翻成员原判 10 处**；reviewer 独立新增 2 条发现（TD-31 契约签名与实现不符；TD-03 的 `param` 偏移致 S 分支亦错），另**驳回成员 2 条结论**（`pos_index` 不可达 §8.3/§8.8-3；BE-06 主机制 §8.9-2 —— 两条均已由原提出者自行撤回）、**对 1 条"已清偿"结论提出异议**（t1 §8 的 source-demo 契约一致性，§8.7）。
> **定位**：按用户"今晚只做审计，不做修复" ⇒ 本文件是**明晚可执行工单的前置依据**（§7 已给"第 0 步→第 6 步"的派单顺序与前置条件），**不含任何修复补丁**。
> **本文件为 t4 唯一写盘产物；全程只读：未跑测试/构建/打包，未装依赖，未起停任何服务，未改任何代码与既有文档。**
