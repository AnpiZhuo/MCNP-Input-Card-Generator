# T1 记忆与文档债务审计报告（MCNP 输入卡生成器）

> 任务：tech-debt-audit / t1「记忆与文档债务审计」
> 审计人：researcher（AgentTeams 成员）
> 日期：2026-09-10
> 性质：**只读审计，未修改任何代码**（本文件由项目经理明确授权新增，是本次审计唯一写盘产物）
> 债条总数：**23 条（P0 5 / P1 13 / P2 5）**
> （版本沿革：v4 并入与 `docs/audit/t2-backend-debt.md`、`t3-frontend-debt.md` 交叉核对后的 M-20~M-23（见 §6）；**v5 追加 §7 T4 引用版精简表（M-01…M-17 逐条含 ≤120 字原文引用，§7.1 为 M-18~M-23）、§8 已核实已清偿/勿再报、§9 证据类型标注（静态核实 vs 无 shell 推断）**；**v5.1（冻结令下唯一的更正性编辑，不新增债条）**：§8 第 8 条「`source-demo-visualization.md` 契约与实现一致」被 t4 reviewer 证伪一处（`resolve_ds` 签名，TD-31）→ 已在该行标注更正；**债条总数仍为 23 条不变**）

---

## 1. 方法与工具限制（原话照搬）

本会话**无 shell 工具**（工具集只有 read/glob/grep/write/edit 等文件工具），因此**无法执行** `git status --porcelain` / `git log --oneline -12` / `git diff --stat`。替代静态证据全部取自真实文件内容，未编造：

- `.git/refs/heads/main` = `4f0798fa880eac85dedb7a210e677f32bf3418ad`（工作分支 main，即当前 HEAD）
- `.git/logs/HEAD`（reflog，281 行）= 提交流水的替代证据源；本文所有「reflog:N」均指向该文件行号
- 部署目录 `D:\MCNP\MCNP输入卡生成器` 的文件级 / 内容级只读比对（用于交付链路核对）

**无法取得**：`git status`（未提交文件清单）、`git diff --stat`、文件 mtime、PYZ 内部真实内容。
因此**工作区"未提交/已提交"结论一律标注为推断或不可核实**；凡依赖 PYZ 内部内容的判断一律不下结论（见 §3.3）。
端点一致性用 grep 静态比对（api.yaml ↔ api_server handlers 集合）。
**二进制串探测已试并放弃**：用字符串探测部署版 `python.exe` 判断 PYZ 内容不可靠——对照探针 `preview-3d`（必然存在）也返回 No matches，故该手段全部作废，相关疑点仅以"待 runtime 复核"形式提出（M-19）。

---

## 2. 完整债表（M-01 … M-23）

列：债ID | 类别 | 位置(file:line) | 证据 | 影响 | 建议严重度 | 建议处置 | 建议 Owner

| 债ID | 类别 | 位置(file:line) | 证据 | 影响 | 建议严重度 | 建议处置 | 建议 Owner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **M-01** | 记忆-版本身份漂移 | `PROJECT_MEMORY.md:296`(§1) / `:309`(§2) / `:431`(§5) / `:276`(S2) / `:483-484`(§8 里程碑) | 实际版本 = **1.7.5**，五处一致：`gui/package.json:4`、`gui/src-tauri/tauri.conf.json:10`、`gui/src-tauri/Cargo.toml:3`、`gui/src-tauri/Cargo.lock:1642`、`README.md:25`(徽章 Version-1.7.5)；部署版 `D:\MCNP\MCNP输入卡生成器\README.md:25` 同为 1.7.5；reflog:251 `chore(release): bump version to 1.7.5`。记忆侧：§1=1.7.2、§2=v1.7.2、S2:276="恒 1.7.2"、§8 里程碑表最新两行均为 v1.7.4（**确认无 1.7.5 行**） | AI/新人按记忆取版本、判发布状态全错；版本纪律记录失效 | **P0** | §1/§2/§5/S2/§8 全部改 1.7.5；§8 里程碑补 v1.7.5 行（AI inputcard-mcp + 六棱柱/四面体） | PM（记忆维护者） |
| **M-02** | 记忆-状态快照滞后 | `PROJECT_MEMORY.md:309`(§2 当前状态快照) | 写"已交付 v1.7.2（2026-08-18 打包）+ V1.7.2.2；后续功能（#7 重合检查）待用户排期"；实际 #7 重合检查 2026-08-22 已交付（`docs/CHANGELOG.md:65`；`docs/contracts/api.yaml:1379` checkOverlap），且 v1.7.3/1.7.4/1.7.5 均已发布部署（§8:483、reflog:205/228/251） | 把已上线能力写成"未排期"，能力清单与排期决策被误导（滞后 3 个版本） | **P0** | 重写 §2：版本 + 补格阵 fill 三阶段/重合与覆盖检测/材料库/AI-MCP/源演示/封闭性/参数扫描多核改造 | PM |
| **M-03** | 记忆-数量与基线失真 | `PROJECT_MEMORY.md:389`/`:394`(§3)、`:521-524`(§9 门禁表)、`docs/CHANGELOG.md:9` | 记忆称 api.yaml "30 端点"、pytest "573 绿"、vitest "358 绿"、漂移闸门 "30 端点"；实测 api.yaml **49** path + 49 operationId（`api.yaml:39…:2014`），`gui/backend/api_server.py:1428-1476` handler 49；同文件 S1 自记 pytest **765/0**(`:55`)、vitest **587+4**(`:40`)/**554**(`:52`)；实测 `tests/` 81 个 `.py`、`gui/test/` **75 个 `*.test.ts(x)` + 1 个 `.snap`**（精确分项见 M-20）；CHANGELOG:9 基线沿革停在 pytest 528 / vitest 327 | 门禁基线与接口数误判 → 审计、验收、排期全偏 | **P0** | 按当前仓库重算回填 §3/§9；更新 CHANGELOG:9 基线沿革 | PM + 架构师 |
| **M-04** | 工作区-待提交状态失真 | `PROJECT_MEMORY.md:272-275`(S2)、`:281-284`(S3)、`:41`(S1) | S2 称"工作树未提交改动仅批量编辑 5 文件、版本恒 1.7.2"；S3 称"GQ/SQ 修复待发版、当前全部改动未 commit、已知阻塞无"；S1:41 称分布 v2"改动未 commit"。reflog 显示 2026-08-22~09-10 有约 45 条提交（`:245-281`），HEAD=4f0798fa(09-10)；reflog:275 提交消息明写 `参数扫描改造…+ misc prior uncommitted work`，reflog:276 紧随 `reset: moving to HEAD` | 无法判断哪些改动已入库、哪些真在工作区；批次边界与"一主题一提交"纪律不可审计，存在无关改动被夹带进他主题提交的风险（分布 v2 是否落入 08e5acef——**存疑，无 shell 无法 git show 证实**） | **P0** | S2/S3 按真实 git status/log 重写；新增纪律：批次结束必记 commit 短号或待提交文件清单 | PM |
| **M-05** | 记忆-MCP 接入形态错误 | `PROJECT_MEMORY.md:46`/`:52`(S1)、`:356`(§3 目录表) | 记忆写 stdio `mcnp_bridge --mcp-server` 分派，并自相矛盾地写"6 工具"(:46) 与"10 工具"(:52)；实测 `gui/backend/mcnp_bridge.py:53-57` 仅 `--mcp-http`（8100）唯一入口，`inputcard_mcp/server.py` 实为 6 个 `@mcp.tool`；reflog:267 `移除 stdio 旧接入（注册MCP.bat/--mcp-server），统一 MCP over HTTP`；`AI接入.md:3`/`:14`/`:19`、`README.md:68` 均 HTTP/8100；**部署目录全树 `*.bat` 0 命中**（无 `注册MCP.bat`）反向印证；`mcnp_bridge.py:14-17` docstring 仍留 `--mcp-server` | 按记忆配置 MCP 必然失败；工具数量描述不可信 | **P1** | 改写 S1/§3 为 HTTP/8100 + 6 工具；删除 `mcnp_bridge.py:14-17` 陈旧注释 | PM + 后端 |
| **M-06** | 文档-自相矛盾 | `docs/inputcard-mcp.md:12`、`:45`、`:66`、`:70`、`:76`、`:137`、`:140` | `:12` 仍写"本地 stdio 模式"、`:45` 仍给 `"type": "stdio"`；`:66` 又写"不再用 stdio"、`:70`/`:76` 写 MCP over HTTP（8100）；`:137`/`:140` 仍教 `<部署目录>\python.exe --mcp-server` | 用户照前半部分配置必然失败；同一文档三处状态互相打脸 | **P1** | 删除 stdio 段落与 `--mcp-server` 描述，全文统一 HTTP/8100 | 文档 Owner（PM 指派） |
| **M-07** | 文档-打包手册陈旧 | `docs/手动打包方法.md:7`、`:41`、`:50`、`:149-151` | 称"最新 **v1.7.4**（2026-08-28）"、"当前 **v1.7.2**"、"README.md 版本徽章（第 9 行 `Version-1.7.2`）同步改"、"spec 含 inputcard_mcp（mcnp_bridge `--mcp-server` 分派用）"；实测 `README.md:25` 为 `Version-1.7.5`，唯一入口为 `--mcp-http` | 发布流程按错版本号/错 MCP 入口执行，且会漏改版本 | **P1** | 更新为 v1.7.5 + `--mcp-http`；徽章行号改 25 | 构建 Owner |
| **M-08** | 文档-归档断层 + 格式损坏 | `docs/CHANGELOG.md:9`、`:50-52`、`:132` | "完整变更流水档案"总表最新一行仅到 2026-09（覆盖检测，`:132`）；缺 08-27/28 v1.7.4、08-30 材料库总表行、09-04（后端提速 / preview_cache 跨进程持久化 / 重合 fill 修复 / `*fmesh` 能量沉积）、09-09（分布 v2 双态 / 校验规则补全 + 几何水密自检 / 栅元封闭性 / 参数扫描改造 / AI over HTTP / **1.7.5 升版**）、09-10（SDEF 源演示）；`:9` 基线沿革陈旧；`:50-52` 材料库深化段**缺标题**（孤立段落直接接空行） | 唯一可回溯的流水档案断档 6 批，无法审计"何时改了什么" | **P1** | 依 reflog 补 6 批条目到总表顶部；修材料库段标题；更新 `:9` 基线沿革 | PM |
| **M-09** | 文档-逐批清单断层 | `docs/backend-changes.md:1406`（末节 §AC 材料库深化 2026-08-30）、`docs/frontend-changes.md:1277`（末节 材料库深化） | 两份逐批改动清单在 08-30 后零条目；后端另缺 08-25 GPU 偏好端点（`api.yaml:1822` setGpuPreference）、08-27/28 v1.7.4 后端改动、09-04 后端提速与 preview_cache、09-09 分布 v2 与封闭性 | 后端/前端"改动明细"线索中断，代码溯源只能靠 reflog 猜 | **P1** | 按 §AA/§AB/§AC 体例补 08-25~09-10 六批附录 | 架构师 |
| **M-10** | 文档-架构文档通篇陈旧（自带纪律违约） | `app/UI_ARCHITECTURE.md:5`、`:27-28`、`:47`、`:280`、`:141-154`、`:96-109`、`:259`、`:241`、`:282` | 自述"最后重锚定 2026-08-12"，文末却立"行号漂移必须 Grep 重锚定"的纪律，实际已违约：① "25 端点"（实为 49）；② §5.2 行号表全错（详见 §3.1）；③ §4 deck 契约表 `models.py` 行号漂移（详见 §3.1）；④ §7 技术债地图终态仍写"pytest **251** 绿"(`:259`)；⑤ §6.4/§7.2 引用的 `_generate_structured_distributions` 的 `'  '.join` 回放语义已被 09-09 分布 v2 改写（函数现存 `inp_generator.py:908`，权威实现迁至 `app/generator/distributions.py`） | AI 按此文档定位代码必读错行、误判门禁基线；"文档纪律失效"本身即债 | **P1** | 整体重锚定（行号 + 端点数 + 基线），或在文首显式标注"历史快照（行号按 2026-08-12 版本）"并停止作为权威 | 架构师 |
| **M-11** | 契约-状态位与端点数陈旧 | `docs/contracts/lattice-coverage-check.md:3`；`geometry-check.md:3`/`:221`/`:169`；`meshtal-visualization.md:4`/`:41`/`:452`/`:632`；`preview3d-performance.md:14`/`:48`/`:67`/`:252`/`:394`；`ptrac-visualization.md:36`；`p1-refactor.md:20` | ① lattice-coverage-check 标"状态：**待确认**（确认后实现）"，但功能已实现并入 `api.yaml:1546`（CHANGELOG:132 记 752/0）；② geometry-check 标"本轮不施工（仅存档，未排期）"，但 `/api/check-overlap` 已交付（`api.yaml:1379`）；③ meshtal-visualization 标"本次为契约产出，不施工"，v1.7.0 已交付；④ 多份契约把"25 端点/30 端点"当作当前值 | 把已交付能力读成"未实现"，重复排期或误判缺口 | **P1** | 状态行改为"已交付 + 交付时间/commit"；端点数改 49 或显式标注为历史值 | 架构师 |
| **M-12** | 契约-缺失 + 双处悬空引用 | `MCNP输入卡生成器_功能待办清单.md:8`；`docs/contracts/validator-crosscheck.md:39`；`docs/contracts/`（无 watertight-check.md） | 两处文档均引用 `docs/contracts/watertight-check.md`，全树 glob `*watertight*` **0 命中**；功能确已在：`app/freecad_preview.py:374`/`:389`/`:403`/`:405`（check_watertight 参数）/`:450`（回参）、`gui/src/components/CellEditDialog.tsx:80`（调 `/api/check-cell-closure`）/`:156-163`（「🩺 自检此栅元」）、`api.yaml:1448` checkCellClosure / `:1546` validateUniverseCoverage；PROJECT_MEMORY 全文无"封闭/closure"，§3(`:363-364`) 未登记 `gui/src/utils/cellClosure.ts`、`useCellClosure.ts` | 已交付功能的"设计约定"文件不存在 → 后续维护无权威契约、双处引用悬空 | **P1**（原 P2，依 PM 证据上调） | 补 `docs/contracts/watertight-check.md`（按 `validator-crosscheck.md:37-41` 已写要点扩写）；§2 补功能、§3 补登记两个深模块 | 架构师 + PM |
| **M-13** | 文档-编号与根目录文档未登记 | `MCNP输入卡生成器_功能待办清单.md:2-3`/`:10-12`/`:19-20` vs `PROJECT_MEMORY.md:83`；`PROJECT_MEMORY.md:386-391`(§3 文档表) | 清单编号为 P0#1 / P1#2 / P2#6~#11（#3/#4/#5 缺号），而 `PROJECT_MEMORY.md:83` 引用"待办 P1#5 里的切面 + 导出"（清单无 #5，引用悬空）；§3 文档表未登记根目录 `MCNP输入卡生成器_功能待办清单.md` 与 `AI接入.md` | 引用悬空；新人/新会话找不到当前待办与 AI 接入入口 | **P2** | 统一待办编号并同步记忆引用；§3 补登记两份根目录文档 | PM |
| **M-14** | 测试-资产未登记 + 新端点零测试 | `PROJECT_MEMORY.md:394`(§3 测试行)；`tests/`（grep 无匹配） | §3 只给总数（573/358）不给结构；实测 `tests/` 81 个 `.py`（unit 34 / parser 26 / integration 12 + conftest）、`gui/test/` **75 个 `*.test.ts(x)` + 1 个 `.snap`**（根 47 / volume 23 / ptrac 4 / source 1；精确分项见 M-20）；grep `tests/` 对 `cell-closure`、`checkCellClosure`、`check_cell_closure` **零匹配**（封闭性端点无专门回归测试，仅 `test_build_cells_data.py:130-135`/`:232` 的 `force_include_numbers` 旁证） | 按 §3 找不到测试；新端点缺回归网（严重度请 T2/T4 复核） | **P2**（测试缺口交 T4 定级） | §3 补测试目录结构与文件数；为 `/api/check-cell-closure` 补单测/契约测试 | PM + 测试 |
| **M-15** | 记忆-提交状态与真实 git 相反（并入部署侧证据） | `PROJECT_MEMORY.md:3`（顶部横幅）、`:17`（S1 标题）、`:31` | `:3` 写 SDEF 演示批次"**已实现待提交**"，而 `.git/refs/heads/main`=4f0798fa、reflog:281=`feat(source-demo): SDEF 源粒子演示可视化（TODO #6）—— 后端采样器 + 全宏体拆解 + 独立 3D 演示窗口` → **该批已提交**；同文件 `:17` 却写"已实现，本次提交"（自相矛盾）、`:31` 写"未打包、未升版"。**交付侧证据**：部署版确有 1.7.5 与 AI 接入，但部署 `_internal\app\generator\` 无 `source_sampler.py`、其 `distributions.py` 无 `DistributionSampler`、`voxel_csg.py` 无宏体拆解代码 → **该功能确实未进用户安装包**（"未打包"成立） | 后续会话误判工作区状态；用户以为有该功能实则没有 | **P1** | `:3` 改为"已提交 4f0798fa；未打包（用户安装版 1.7.5 不含）"；`:17`/`:31` 措辞统一 | PM |
| **M-16** | 记忆-记忆外改动零登记 | `PROJECT_MEMORY.md`（关键词全零命中）；证据 = reflog 行号（见 §3.2 完整清单） | grep PROJECT_MEMORY 对 §3.2 所列关键词**全部 0 命中**（仅命中无关的 `mcnp_workspace_v1`:371 与"水密自检":25）。已逐条坐实 **20 条**未登记提交（reflog:251/259-275/277-280，详见 §3.2）。**修正 PM 初判"全部未记录"**：MCP **stdio 时代**批次在 S1:43-55 有记录；零记录的是 HTTP 化之后的全部 AI 改动 + 封闭性/校验规则/参数扫描改造/源项 adv+appScale | **用户担心的"记忆外会话改动"实证**：20 次真实改动（含新功能与升版）无记忆/契约/§3 锚点，下个会话会重复实现或误删 | **P0** | 按 reflog 逐条补记 S1/§2/§3/CHANGELOG；为封闭性与校验规则补契约（见 M-12）；建立"提交即登记"纪律 | PM（+ 架构师补契约） |
| **M-17** | 文档-待办清单状态与实际相反 | `MCNP输入卡生成器_功能待办清单.md:50-53`（第 11 项） | `:50` 标 `### 11. 2D 结果导出增强 ❌（按需）`、`:51` 称"meshtal 体积渲染窗口增加'切面存为 2D 热图 PNG/SVG + 数据 CSV'…目前只有 3D 渲染和 OUTP 表格 CSV"；实际已落地：`gui/src/volume/sliceExport.ts` + `gui/src/volume/SliceExportPanel.tsx`（`sliceFrame`/`frameToCsv`/`sliceToSvg`），`PROJECT_MEMORY.md:83`/`:86` 记 2026-09-04 实现，reflog:246 `feat(3d): universe 覆盖完整性检测 + 格阵切片导出`（f7fc2ed）已提交。另 `:25` 对源演示批"未打包未升版"基本成立，但与前文"未做"口径易与 M-15 混淆 | 待办清单把已完成项标 ❌ → 下个会话可能重复开发（真实浪费） | **P1** | `:50` 改 ✅（2026-09-04 落地，f7fc2ed，sliceExport.ts / SliceExportPanel.tsx）；`:25` 补"已提交 4f0798fa" | PM |
| **M-18** | 交付链路断裂：HEAD 功能未进用户安装包 | 部署 `D:\MCNP\MCNP输入卡生成器\_internal\app\generator\`（无 `source_sampler.py`）；部署 `...\app\generator\distributions.py`（无 `DistributionSampler`）；部署 `...\app\voxel_csg.py`（无宏体）对照 `gui/mcnp_sidecar.spec:31` `_keep_dirs=["generator","docs","meshtal","ptrac"]` + `:45-56` `_walk_add`（把 `app/generator/**.py` 整目录作数据文件打进包） | **证据①（文件级）**：spec 机制决定"构建时该文件存在就必在部署目录"；实测部署 `_internal\app\generator\` 仅 __init__/banners/distributions/inp_generator/inp_parser/parsers/*/validator，**无 source_sampler.py**。**证据②（内容级，独立于文件存在性）**：部署 `distributions.py` 333 行是 v2 双态版但 grep `^class ` **零命中**（无 DistributionSampler/SourceSamplingError；源码 `app/generator/distributions.py:344`/`:368` 有）。**证据③（内容级）**：部署 `voxel_csg.py` grep `_polyhedron_field`、`_rot60`、`RHP`、`ARB` **零命中**（宏体拆解为 SDEF 批新增）。⇒ 部署版后端确为 **4f0798fa 之前**的构建：SDEF 源粒子演示可视化「已实现、已提交、**未打包给用户**」 | **源码功能对用户等于不存在**（前端入口 / 后端端点 / 采样器全缺）；用户与后续会话若按记忆/CHANGELOG 认为"已交付"会误判 | **P1**（若用户已据此对外声称交付则按 P0 处理） | 重打包 sidecar（vite build → PyInstaller → binaries → tauri build → 6.2 时效核对 → 部署 → 冒烟含 `/api/source-demo-sample`）；记忆写明"已提交 commit / 已打包版本 / 部署校验"三态 | 构建 Owner + PM |
| **M-19** | 打包-spec 动态导入缺口（**待 runtime 复核**） | `gui/mcnp_sidecar.spec:17-30`（`_keep_py` 无 `lattice.py`/`diff_inp.py`）、`:31`（`_keep_dirs` 不含顶层 `app/*.py`）；`gui/backend/api_server.py:27-36`（`_import_app` = `__import__(module)`，实参是变量）、`:1793`/`:2965`/`:2984`/`:3013`/`:3217`（`_import_app("lattice")`）、`:1756`（`_import_app("diff_inp")`） | 部署目录全树 glob `*lattice*` **0 命中**（`_internal\app\lattice.py` 不存在）；`lattice`/`diff_inp` 无静态导入者（全仓 grep：仅 `tools/diag_*.py` 与 `app/generator/inp_generator.py:9`、`app/generator/parsers/core.py:18` 的 `from app import lattice`，后者注册的是 **app.lattice** 而非顶层 `lattice`），而 `_import_app()` 走 `__import__("lattice")`（变量实参 → PyInstaller 静态分析不可见） | 若运行时确实 ImportError → 用户安装版**格阵端点**（validate-lattice-surfaces / lattice-extent / preview-lattice）与 **INP 对比**（diff-inp）不可用；与记忆"部署版验证过格阵"（`tools/diag_universe_stl.py` 打 5001 HTTP）存在张力 | **P1**（runtime 证实则 P0） | **T2/PM 用 runtime 复核**：起部署版 5001 → `POST /api/lattice-extent`、`/api/diff-inp`、`/api/validate-lattice-surfaces`；若 500 → spec `_keep_py` 补 `lattice.py`/`diff_inp.py` 并重打包 | 后端/构建（+ T4 定级） |
| **M-20** | 文档-测试文件数与实测不符 | `PROJECT_MEMORY.md:52`（"554/0（69 文件）"）、`:87`（"546/0（69 文件全过）"）、`:40`（"587+4 passed（73+1 文件）"）、`:153`（"522/0（66 文件全过）"）；`docs/CHANGELOG.md:47` | 实测 `gui/test/**` 共 **76 个文件 = 75 个 `*.test.ts(x)` + 1 个 `__snapshots__/volumeShader.snapshot.test.ts.snap`**（根 47 / `volume/` 23 / `ptrac/` 4 / `source/` 1；`.test.ts` 60 + `.test.tsx` 15）。记忆各处的"66/69/73+1 文件"是**各批当时的快照**，与当前实测不符；真正的债是**叙述未标注"当时快照"**，且 §3/§9 门禁基线仍停在旧值（见 M-03）。**附带更正 T3 报告**：`docs/audit/t3-frontend-debt.md:90`/`:119` 的"81 个（根 61 + `volume/` 19 + `ptrac/` 4）"**与实测不符且自身不自洽**（61+19+4=84≠81），应以 75 test + 1 snap 为准 | 后人引用"文件数"必错；错误数字有被写进汇总文档的风险 | **P2** | 记忆各处标注"该批当时文件数"；统一以 75 test + 1 snap 为当前值；更正 T3 文档两处数字 | PM（+ researcher 更正 T3 文档） |
| **M-21** | 文档/注释-hexCenter 旧公式残留（30° 旋转差） | `gui/src/utils/lattice.ts:123-128`(docstring)；`gui/test/lattice.test.ts:131`(describe 名)；`docs/frontend-changes.md:11`/`:208`/`:1234`；`docs/qa-report.md:64`；`docs/qa-report-phase2.md:50`；`docs/qa-report-total.md:24`；`docs/backend-changes.md:1285`；`docs/contracts/lattice-fix15-design.md:171-172`/`:450`(L1 锁死表)；`PROJECT_MEMORY.md:166`/`:172`/`:178`/`:179`/`:208` | **代码两侧一致且正确**：`gui/src/utils/lattice.ts:133-136` → `x = col*pitch + row*(pitch/2)`、`y = row*pitch*(√3/2)`，与 `app/lattice.py:615-616` 逐字一致；`app/lattice.py:604-613` docstring 明写"旧公式 `x=col·p·√3/2, y=row·p+(col%2)·p/2` 与此差 30° 旋转，已按 MCNP 修正（2026-08-25 交叉验证后替换；golden hexCenter/positions.hex 同步更新）"。而**上列 16 处**（含 docstring 与契约 L1 行）仍写旧公式 | 同一函数"注释/文档两套公式"并存：下次改 hex 的人先信注释即引入几何回归（历史上已因此返工）；契约 L1 锁死表写错公式会污染跨语言实现 | **P1** | 16 处一次性替换为新公式（**实现不动**），docstring 补齐自洽核验并交叉引用 `app/lattice.py:604-613`；测试 describe 名同步 | 前端注释 + 架构师改 docs（T2 BE-14 与 T3 FE-07 同根因，请 T4 去重） |
| **M-22** | 文档-死模块被描述成生产消费方 | `docs/contracts/core3d-instancing.md:130`/`:133`/`:188`；`docs/qa-report.md:89`；`docs/frontend-changes.md:17-18`；`docs/contracts/lattice-fix15-design.md:30`/`:405`/`:410`/`:412`/`:456`/`:547`；`PROJECT_MEMORY.md:119`/`:134`/`:136`/`:153`/`:171`/`:178`/`:188`/`:191` | `gui/src/components/Preview3DLattice.tsx`（479 行）**全 `gui/` 树零 import**（grep 仅命中其自身 `:2`/`:48`/`:176`）；`gui/src/components/Preview3D.tsx:15` 直接 `import { buildLatticeInstances }` 并在 `:783` 内联装配（`:721` 调 `/api/preview-lattice`）→ 装配视图的**生产实现是 Preview3D 内联**。**定性证据**：`PROJECT_MEMORY.md:178` 记 2026-08-24 项15 曾接线"fill/fill_grid → Preview3DLattice"，且 `gui/test/preview3dLatticeRouting.dom.test.tsx` 仍在 → 判定为**"落地后被内联取代"的废弃实现**（取代的具体时点需 `git show` 复核，本会话无 shell） | 文档把死模块当生产接线：后续 agent 会照文档去找不存在的调用链；479 行重复装配逻辑持续腐化（T3 已记 FE-03，P1） | **P2**（文档侧；死代码侧交 T3/T4） | docs 三处 + 契约两处标注"已废弃／被 Preview3D 内联取代"；若删除该文件，同步清理 `frontend-changes.md:17-18`、`core3d-instancing.md:130`/`:188`、`qa-report.md:89` 与记忆 8 处描述 | 架构师 + PM（+ engineer-frontend 删码） |
| **M-23** | 文档-建议失效未结案（跨报告） | `docs/qa-report-phase2.md:78`；`gui/src/utils/lattice.ts:447-471`（`estimateLatticeExtent`）；`docs/audit/t3-frontend-debt.md:30`(FE-06) | phase2 报告留"`estimateLatticeExtent` 六棱柱以 pitch=1 估算，阶段3 需以真实格距覆盖"的建议；现状：真实格元盒已由后端 `/api/lattice-extent` 提供（`gui/src/components/MacrobodyPreview.tsx:55`），而 `estimateLatticeExtent` 在 `gui/src` 内**零引用**（仅 `gui/test/lattice.test.ts:19`/`:227-241` 在用） | 建议悬空：读者以为还需"阶段3 衔接"；死导出留在权威模块内易被误用（T3 记 FE-06，P2） | **P2** | 在 phase2 报告该行标"已由 `/api/lattice-extent` 覆盖，结案"；按 FE-06 处置死导出 | 架构师（+ engineer-frontend） |

---

## 3. 存疑 / 互相矛盾（与逐条详证）

### 3.1 M-10 行号漂移明细（文档 vs 实测）

| 文档声明 | 实测（当前工作树） |
| :--- | :--- |
| `app/UI_ARCHITECTURE.md:5`/`:27-28`/`:47`/`:280` "25 端点" | `api.yaml` 49 path + `api_server.py:1428-1476` 49 handler |
| §5.2 `_apply_raw_override` 1149-1161、`_has_raw_override` 1145、`_raw_override_text` 1140、`generate_inp_from_deck` 1163 | `inp_generator.py` 实际 **1260 / 1256 / 1251 / 1274** |
| §5.2 调用点 1191 / 1196 / 1215 / 1229 / 1231 / 1234 / 1237 / 1252 | 实际 **1302 / 1308 / 1331 / 1352 / 1354 / 1357 / 1360 / 1375** |
| §4 `models.py` TallySettings 203、AdvancedSettings 297、DeckData 420、CellData 22、CellRow 59 | 实际 **271 / 371 / 497 / 23 / 60** |
| §7 终态"全量 pytest 251 绿"(`:259`) | S1 自记 pytest 765/0（`PROJECT_MEMORY.md:55`） |

### 3.2 M-16 记忆完全未登记的 20 条提交（reflog 行号 → 提交）

**关键词零命中清单**（在 `PROJECT_MEMORY.md` 全文 grep，结果 0 命中）：

```
8100 | mcp-http | 自配置 | 注册MCP | AI 接入面板 | 多核 | 免安装 | 闪主界面 |
源类型模板 | 等比缩放 | appScale | sourceAdv | useDeckSynced | 彩色行标记 | 封闭 | closur
```

（仅两处无关命中：`mcnp_workspace_v1` localStorage 键 `:371`、"水密自检"一词 `:25`）

- reflog **:251** `chore(release): bump version to 1.7.5 (AI inputcard-mcp + 六棱柱/四面体新功能打包)`
- reflog **:259** `fix(material-library): 迁移旧 localStorage 预设不覆盖已入库同名 key（原 JSON 优先）`
- reflog **:260** `docs(ai): AI接入配置去除硬编码路径，用 <安装目录> 占位符`
- reflog **:261** `feat(ai): 新增 注册MCP.bat 一键自动注册 MCP（零硬编码路径）`
- reflog **:262** `feat(ai): inputcard-mcp 增加「当前工作区」会话 + MCP over HTTP（/workspace + /mcp）`
- reflog **:263** `docs(ai): 合并 AI 接入为单一 AI接入.md 并修引用`
- reflog **:264** `feat(ai): 前端 AI 接入——当前工作区同步/回显 + AI 接入面板；/workspace 前后端 deck 对齐`
- reflog **:265** `feat(ai): 主程序启动时自动拉起 MCP over HTTP（--mcp-http → 8100），关闭时一起关`
- reflog **:266** `fix(ai): /workspace 空工作区 tally=None 崩溃修复 + sidecar 显式打入 uvicorn/starlette`
- reflog **:267** `chore(ai): 移除 stdio 旧接入（注册MCP.bat/--mcp-server），统一 MCP over HTTP（--mcp-http 唯一入口）`
- reflog **:268** `feat(ai): AI 接入面板复制改为给 AI 的自配置提示词`
- reflog **:269** `fix(ai): 回显投影 adv→前端源项中间态（sourceMode/sdefFields/ssw/ssr/分布）`
- reflog **:270** `精简源类型模板为单点源/多点源/高级自由，删除七种冗余模板与自动分布预设`
- reflog **:271** `修复MCP over HTTP：移除/mcp双挂载，改用custom_route；patch_section兼容list段`
- reflog **:272** `refactor(ui): 源项 adv 权威化 + 主窗口等比缩放深模块（sourceAdv/useDeckSynced/appScale）`
- reflog **:273** `fix(3d-preview): 独立窗口闪主界面 + 免安装版 FreeCAD 空预览`
- reflog **:274** `docs(待办清单): 移除已完成功能项…登记 SDEF 源粒子演示可视化（P1#3）并统一编号`
- reflog **:275** `参数扫描改造：免正则选中即参数 + 多核并行 + 彩色行标记 + misc prior uncommitted work`
- reflog **:277** `feat(validate): 语法规则补全（宏体参数/80列/未定义引用）+ 栅元封闭性自检（closed/infinite/empty）`
- reflog **:278 / :279 / :280** 封闭性深化：3D 预览顺带检测 →「封闭」列 → `useCellClosure`/`cellClosure` 深模块 → 真空栅元也参与（`force_include_numbers`）

### 3.3 存疑项（明确标注，不作结论）

1. **分布 v2 是否已被夹带提交**：S1:41 称"未 commit"，但 reflog:275 的提交消息含 `misc prior uncommitted work`、reflog:276 紧随 `reset: moving to HEAD`。无 shell 无法 `git show` 核对，**存疑**。
2. **M-19 的运行时表现**：`lattice`/`diff_inp` 是否真的在打包版 ImportError，取决于 PYZ 内部是否含顶层 `lattice` 名。**我尝试用二进制串探测部署版 `python.exe`，但对照探针 `preview-3d` 也返回 No matches → 探针不可靠，已放弃**，故仅作为"待 runtime 复核"提出，不作结论。
3. **源演示批次"未打包"**：已用文件级 + 内容级证据坐实（M-18）；但**"未升版"的判断仅相对该批次成立**——1.7.5 的升版发生在 09-04（reflog:251，AI + 六棱柱/四面体批次），早于该批次。
4. **"官方 C810.pdf 权威源"等外部资料**：本次审计未访问 `D:\MCNP\MCNP6\C810.pdf`，凡记忆中以该 PDF 为依据的结论未复核。

### 3.4 文档间互相矛盾清单（同文件或跨文件）

| 矛盾点 | A 说法 | B 说法 |
| :--- | :--- | :--- |
| SDEF 演示批提交状态 | `PROJECT_MEMORY.md:3` "已实现待提交" | 同文件 `:17` "已实现，本次提交"；`.git/refs/heads/main`+reflog:281 证明确已提交 |
| MCP 接入形态 | `PROJECT_MEMORY.md:46`/`:356`、`docs/inputcard-mcp.md:12`/`:45`/`:137`/`:140`、`docs/手动打包方法.md:149-151` 均为 stdio `--mcp-server` | `AI接入.md:3`/`:14`/`:19`、`README.md:68`、`mcnp_bridge.py:53-57` 均为 HTTP/8100；`docs/inputcard-mcp.md:66` 亦自述"不再用 stdio" |
| 测试基线 | `PROJECT_MEMORY.md:394`/`:521-524` pytest 573 / vitest 358 | 同文件 S1 `:40`/`:55` pytest 765 / vitest 587+4；实测 `tests/` 81 文件、`gui/test/` 70 文件 |
| 端点数量 | `PROJECT_MEMORY.md:389`/`:524` "30 端点" | 实测 49（api.yaml ↔ api_server 一致）；CHANGELOG:66 曾记 34，`backend-changes.md:1005` 曾记 37 |
| 2D 结果导出（切面 PNG/SVG + CSV） | `MCNP输入卡生成器_功能待办清单.md:50` ❌ 未做 | `PROJECT_MEMORY.md:83`/`:86` 已实现；`gui/src/volume/sliceExport.ts`/`SliceExportPanel.tsx` 在；reflog:246 已提交 |
| 格阵覆盖检测契约状态 | `docs/contracts/lattice-coverage-check.md:3` "待确认" | 已实现并提交（`api.yaml:1546`；CHANGELOG:132 记 752/0） |

---

## 4. 负面结论（勿再排期）

1. **契约漂移无债**：`docs/contracts/api.yaml` 49 个 path / 49 个 operationId ↔ `gui/backend/api_server.py:1428-1476` 49 项 handler，端点名一一对应、集合一致 → 静态比对**未见漂移**。
2. **一键打包废弃一致**：记忆 §9"release.bat / scripts/release.ps1 已废弃删除"与仓库一致（源码根无 `release.bat`、无 `scripts/release.ps1`；部署目录全树 `*.bat` 0 命中）。
3. **AI 接入正口径文档已存在**：`AI接入.md:3`/`:14`/`:19`/`:25`、`README.md:34`/`:68` 与实现一致（HTTP/8100、6 工具）；`docs/contracts/source-demo-visualization.md` 与实现一致（勿把"全部 AI 文档都过期"当结论——过期的具体是 M-05/M-06/M-07 三处）。
4. **ADR 编号未被改名**：`PROJECT_MEMORY.md` §4 编号与 `docs/contracts/*` 引用面未见冲突。
5. **`gui/backend/mcnp_bridge.py:53-57` 的实现本身正确**（`--mcp-http` 唯一入口 + 延迟 import mcp，符合"主 api_server 路径不触碰 mcp"约定）；债只在 `:14-17` 的**注释**（M-05）。

---

## 5. 汇总与建议顺序

| 严重度 | 条数 | 债ID |
| :--- | :--- | :--- |
| P0 | 5 | M-01、M-02、M-03、M-04、M-16 |
| P1 | 13 | M-05、M-06、M-07、M-08、M-09、M-10、M-11、M-12、M-15、M-17、M-18、M-19、M-21 |
| P2 | 5 | M-13、M-14、M-20、M-22、M-23 |
| **合计** | **23** | — |

**建议处置顺序**：M-18 重打包（用户侧功能缺失最急）→ M-16 补记（记忆外改动）→ M-19 runtime 复核 → M-01/M-02/M-03 改口径 → M-12 补契约 → 其余文档同步。

**跨界交办**：M-19 → engineer-backend / 构建；M-12、M-14 → reviewer（T4 定级）；M-05 → engineer-backend（清 `mcnp_bridge.py:14-17` 陈旧注释）。

---

## 6. 跨报告交叉核对（T2 / T3 → T1，2026-09-10 追加）

### 6.1 T3 请求核对的三项（结论）

| T3 项 | 我的核实结论 | 落点 |
| :--- | :--- | :--- |
| 测试文件数（T3 报 81 个：根 61 + volume 19 + ptrac 4） | **T3 的数字不成立**：实测 `gui/test/**` = 76 个文件 = **75 个 `*.test.ts(x)`**（根 47 / volume 23 / ptrac 4 / source 1；`.ts` 60 + `.tsx` 15）+ 1 个 `.snap`。T3 自身也不自洽（61+19+4=84≠81）。记忆侧"69 文件"是各批当时快照，与当前实测差 6。 | **M-20**（并请 T3 更正其文档 `:90`/`:119`） |
| FE-07 `hexCenter` 文档/docstring 写旧公式 | **成立，且比 T3 报的更多**：T3 报 4 处，我实测清点到 **16 处**（含 `docs/qa-report*.md` 三份、`docs/backend-changes.md:1285`、契约 `lattice-fix15-design.md:171-172` 与 **L1 锁死表 `:450`**、记忆 5 处）。**代码两侧一致且正确**（`lattice.ts:133-136` ↔ `app/lattice.py:615-616`），纯属注释/文档漂移。 | **M-21**（P1；与 T2 BE-14 同根因 → 请 T4 去重，勿重复计条） |
| Q7 `Preview3DLattice.tsx` 是"计划未落地"还是"落地后被取代" | **判定：落地后被内联取代的废弃实现**。证据：该文件在 `gui/` 树零 import（仅自引用 `:2`/`:48`/`:176`）；`Preview3D.tsx:15` 直接 import `buildLatticeInstances` 并在 `:783` 内联装配（`:721` 调 `/api/preview-lattice`）；`PROJECT_MEMORY.md:178` 明确记 08-24 项15 曾接线"fill/fill_grid → Preview3DLattice"且 `gui/test/preview3dLatticeRouting.dom.test.tsx` 至今存在（该测试测的是 Preview3D 的路由，不 import 该组件）。**取代时点无法确定**（需 `git show`，本会话无 shell），故只判定性质、不判时点。 | **M-22**（docs 3 处 + 契约 2 处 + 记忆 8 处需标注/清理；死代码本身归 T3 FE-03） |

### 6.2 FE-06 结案建议

**采纳**。`estimateLatticeExtent` 在 `gui/src` 内零引用（仅测试用），真实格元盒已由后端 `/api/lattice-extent` 提供（`MacrobodyPreview.tsx:55`）→ `docs/qa-report-phase2.md:78` 的"阶段3 衔接"建议应结案。登记为 **M-23**（文档侧结案 + 死导出处置归 T3）。

### 6.3 对 T2 的一条反馈（供 T4 定级参考）

T2 记的"TRCL 归一化两端口径不一致（P3 潜在）"，其**唯一触发点**是 `gui/src/components/Preview3DLattice.tsx:272`；而该文件已确认 **`gui/` 树零 import**（M-22）→ 该潜在不一致在当前生产路径中**不可达**。证据：`gui/src/components/Preview3D.tsx:15` 只 import `buildLatticeInstances`（未 import `parseTrclDeg`）。
**建议**：请 T4 将其标注为"随 FE-03/M-22 清理同批关闭"，或在确认无其它消费点后降级；**但**注意 T2 的另一半结论（`parseTrclDeg` 的"TRCL 三数=三个欧拉角"参数化在后端并不存在）仍是**独立的代码异味**，不因该文件删除而消失——若将来有人复用该 fallback 仍会踩。

### 6.4 去重提示（给 T4）

1. **T2 BE-14 ≡ T3 FE-07**（`lattice.ts:123-128` 注释漂移）→ 已合并为 **M-21** 一条。
2. **T3 FE-03（死代码）与 M-22（文档把它当生产接线）是同一现象的两半**：代码侧删文件 + 文档侧清理描述，建议同一批处理，避免"删了码但文档还指路"。
3. **T3 FE-06 与 M-23** 同上（一码一文）。
4. 各报告数字口径请以本文件实测值为准（`gui/test/**` = 75 test + 1 snap；`tests/` = 81 个 `.py` 含 conftest；api.yaml = 49 端点）。

---

## 7. T4 引用版精简表（M-01 … M-17，逐条含 ≤120 字原文引用）

> 用途：供 t4 交叉验证 / 去重 / 定级时**直接引用**（每格证据为文件原文摘句，长度 ≤120 字；完整证据见 §2）。
> **证据类型**列：`静态核实` = 文件内容 / 文件存在性 / glob / grep 可直接复核；`无 shell 推断` = 依赖 git 历史或运行时而本会话无 shell，**请 T4 标为"待验证"，且不参与 P0 定级**（见 §9）。

| 债ID | 类别 | 位置(file:line) | 证据（原文引用 ≤120 字） | 影响 | 建议严重度 | 建议处置 | Owner | 证据类型 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| M-01 | 记忆-版本身份漂移 | `PROJECT_MEMORY.md:296`；`gui/package.json:4` | 记忆：「版本：1.7.2（快捷建栅元新功能，用户 2026-08-18 指定；bug 修复批严禁升版）」；实测：`"version": "1.7.5"`（package.json/tauri.conf.json/Cargo.toml/Cargo.lock/README 徽章五处一致）。**修正**：§9 版本发布纪律段(:528-532) 无版本号，不算写错；陈旧的是 §8 里程碑表(:483-484 止于 v1.7.4) | 按记忆取版本、判发布状态全错 | P0 | 五处记忆全改 1.7.5 + §8 补 v1.7.5 行 | PM | 静态核实 |
| M-02 | 记忆-状态快照滞后 | `PROJECT_MEMORY.md:309` | 记忆：「已交付 v1.7.2（2026-08-18 打包）+ V1.7.2.2 批次…；后续功能（#7 重合检查）待用户排期」；实际 `/api/check-overlap` 已在 `api.yaml:1379`（checkOverlap），CHANGELOG:65 记 08-22 交付，v1.7.3/1.7.4/1.7.5 均已发布 | 把已上线写成"未排期"，滞后 3 版 | P0 | 重写 §2 | PM | 静态核实 |
| M-03 | 记忆-数量与基线失真 | `PROJECT_MEMORY.md:389`/`:521`；`docs/CHANGELOG.md:9` | 记忆：「docs/contracts/api.yaml … 30 端点」；`pytest … 573/0`；CHANGELOG：「门禁基线沿革：pytest 343 → 465 → 512 → 528（最新）」；实测 api.yaml 49 path+49 operationId ↔ handlers 49；S1 自记 pytest 765/0(:55)、vitest 587+4(:40) | 门禁与接口数误判 | P0 | 重算回填 §3/§9 + CHANGELOG:9 | PM+架构师 | 静态核实 |
| M-04 | 工作区-待提交状态失真 | `PROJECT_MEMORY.md:272-275`(S2)/`:281-284`(S3) | 记忆：「工作树未提交改动（git status 快照，批量编辑栅元批次）」仅列 5 文件、「当前全部改动未 commit」；reflog:245-281 显示 08-22~09-10 约 45 条提交，reflog:275 消息含「misc prior uncommitted work」，reflog:276 为「reset: moving to HEAD」 | 无法判"已入库/在工作区"；批次边界不可审计 | P0 | S2/S3 按真实 git 重写 + "提交即登记"纪律 | PM | 静态核实（reflog）+ 结尾结论**无 shell 推断** |
| M-05 | 记忆-MCP 接入形态错误 | `PROJECT_MEMORY.md:356`/`:46`/`:52` | 记忆：「inputcard_mcp/ … 打包用 `mcnp_bridge --mcp-server` 分派」；实测 `gui/backend/mcnp_bridge.py:53` 仅 `if "--mcp-http" in sys.argv:`（8100 唯一入口），server.py 6 个 `@mcp.tool`；记忆 :46「6 工具」与 :52「10 工具」自相矛盾 | 按记忆配置必然失败 | P1 | 改写 S1/§3；删 mcnp_bridge.py:14-17 陈旧注释 | PM+后端 | 静态核实 |
| M-06 | 文档-自相矛盾 | `docs/inputcard-mcp.md:12`/`:45`/`:66` | `:12`「它采用的是本地 stdio 模式」、`:45` `"type": "stdio"`；同文 `:66`「通过 MCP over HTTP（本机环回 8100）供外部 agent 连接，不再用 stdio」；`:140` 仍教 `<部署目录>\python.exe --mcp-server` | 照前半配置必失败 | P1 | 删 stdio 段，统一 HTTP/8100 | 文档 Owner | 静态核实 |
| M-07 | 文档-打包手册陈旧 | `docs/手动打包方法.md:41`/`:50`/`:149-151` | `:41`「仅实际新功能上线由上级指定新版本（当前 **v1.7.2**…）」；`:50`「README.md 版本徽章（第 9 行 `Version-1.7.2` 同步改）」；实测 `README.md:25` = `Version-1.7.5`，唯一入口 `--mcp-http` | 发布按错版本/错入口执行 | P1 | 更新 v1.7.5 + HTTP + 行号 25 | 构建 Owner | 静态核实 |
| M-08 | 文档-归档断层 + 格式损坏 | `docs/CHANGELOG.md:9`/`:50-52`/`:132` | `:9` 基线沿革止于 528/327；总表最新行仅 `2026-09` 覆盖检测(:132)；缺 08-27/28 v1.7.4、08-30 材料库、09-04、09-09（含 1.7.5 升版）、09-10；`:50-52` 材料库段**缺标题**（孤立段落） | 唯一流水档案断档 6 批 | P1 | 依 reflog 补 6 批 + 修标题 | PM | 静态核实 |
| M-09 | 文档-逐批清单断层 | `docs/backend-changes.md:1406`；`docs/frontend-changes.md:1277` | 两份清单末节均为「§AC 材料库深化（2026-08-30）」/「材料库深化（2026-08-30）」，其后零条目；后端另缺 08-25 GPU 偏好端点（`api.yaml:1822`）、v1.7.4、09-04、09-09 | 改动明细线索中断 | P1 | 补 08-25~09-10 六批附录 | 架构师 | 静态核实 |
| M-10 | 文档-架构文档通篇陈旧（自带纪律违约） | `app/UI_ARCHITECTURE.md:5`/`:141-154`/`:96-109`/`:259` | 自述「最后重锚定：2026-08-12」并立"行号漂移必须 Grep 重锚定"；实际 "25 端点"（真 49）、`_apply_raw_override` 文档 1149-1161（真 1260）、`generate_inp_from_deck` 1163（真 1274）、`DeckData` models.py:420（真 497）、§7 仍"pytest 251 绿" | 按它定位必读错行 | P1 | 重锚定或标"历史快照" | 架构师 | 静态核实 |
| M-11 | 契约-状态位与端点数陈旧 | `docs/contracts/lattice-coverage-check.md:3`；`geometry-check.md:3`/`:221` | 「状态：**待确认**（用户已选定方向，本文为落地前契约，确认后实现）」但功能已实现（`api.yaml:1546`）；「本轮不施工（P0/P1 在修，仅存档，未排期）」但 `/api/check-overlap` 已交付（`api.yaml:1379`）；多份契约以 25/30 端点为当前值 | 把已交付当未实现 | P1 | 状态行 + 端点数（49）更新 | 架构师 | 静态核实 |
| M-12 | 契约-缺失 + 双处悬空引用 | `MCNP输入卡生成器_功能待办清单.md:8`；`docs/contracts/validator-crosscheck.md:39` | 两处均写「见 `docs/contracts/watertight-check.md` 设计约定」，全树 glob `*watertight*` **0 命中**；功能在：`app/freecad_preview.py:374`（`# 水密/缝隙检测结果`）、`CellEditDialog.tsx:80`（`/api/check-cell-closure`） | 已交付功能无权威契约、引用悬空 | P1 | 补 watertight-check.md + §2/§3 登记 | 架构师+PM | 静态核实 |
| M-13 | 文档-编号与根目录文档未登记 | `MCNP输入卡生成器_功能待办清单.md:2-3`/`:10-12`/`:19-20`；`PROJECT_MEMORY.md:83` | 清单编号 P0#1 / P1#2 / P2#6~#11（#3/#4/#5 缺号）；记忆 :83 引「落地待办 **P1#5** 里的「切面 + 导出」」而清单无 #5；§3 未登记根目录 待办清单.md 与 AI接入.md | 引用悬空、找不到入口 | P2 | 统一编号 + §3 补登记 | PM | 静态核实 |
| M-14 | 测试-资产未登记 + 新端点零测试 | `PROJECT_MEMORY.md:394`；`tests/` | 记忆：「tests/ … pytest **573** 绿；`gui/test/` vitest **358** 绿」；实测 `tests/` 81 个 `.py`、`gui/test/` 75 个 `*.test.ts(x)`+1 `.snap`；grep `tests/` 对 `cell-closure`/`checkCellClosure`/`check_cell_closure` 零匹配 | 按 §3 找不到测试；新端点无回归网 | P2 | §3 补结构 + 补封闭性测试 | PM+测试 | 静态核实 |
| M-15 | 记忆-提交状态与真实 git 相反 | `PROJECT_MEMORY.md:3`/`:17`/`:31` | `:3`「SDEF 源粒子演示可视化（TODO #6）落地，**已实现待提交**」；`.git/refs/heads/main`=`4f0798fa…`、reflog:281=「feat(source-demo): SDEF 源粒子演示可视化（TODO #6）—— 后端采样器 + 全宏体拆解 + 独立 3D 演示窗口」→ 已提交；`:17` 另写"本次提交" | 后续会话误判工作区状态 | P1 | :3 改"已提交 4f0798fa；未打包" | PM | 静态核实（reflog） |
| M-16 | 记忆-记忆外改动零登记 | `PROJECT_MEMORY.md`（关键词零命中）；证据 = reflog 行号（§3.2） | grep `8100`/`mcp-http`/`自配置`/`注册MCP`/`AI 接入面板`/`多核`/`免安装`/`闪主界面`/`源类型模板`/`等比缩放`/`appScale`/`sourceAdv`/`useDeckSynced`/`彩色行标记`/`封闭`/`closur` **全部 0 命中**；20 条未登记提交 reflog:251/259-275/277-280（如 :267「移除 stdio 旧接入…统一 MCP over HTTP」、:277「语法规则补全…+ 栅元封闭性自检」） | 记忆外会话改动实证（含新功能与升版） | P0 | 按 reflog 逐条补记 + 补契约 + 提交即登记 | PM（+架构师） | 静态核实 |
| M-17 | 文档-待办清单状态与实际相反 | `MCNP输入卡生成器_功能待办清单.md:50-53` | `:50`「### 11. 2D 结果导出增强 ❌（按需）」、`:51`「meshtal 体积渲染窗口增加'切面存为 2D 热图 PNG/SVG + 数据 CSV'…目前只有 3D 渲染和 OUTP 表格 CSV」；实际 `gui/src/volume/sliceExport.ts` + `SliceExportPanel.tsx` 已在，记忆 :83/:86 记 09-04 落地（reflog:246 f7fc2ed） | 已完成标 ❌ → 重复开发 | P1 | :50 改 ✅ | PM | 静态核实 |

### 7.1 追加 6 条（M-18 … M-23，T4 也应纳入去重/定级）

| 债ID | 类别 | 位置(file:line) | 证据（原文引用 / 实测） | 影响 | 建议严重度 | 建议处置 | Owner | 证据类型 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| M-18 | 交付链路断裂：HEAD 功能未进用户安装包 | 部署 `_internal\app\generator\`；`gui/mcnp_sidecar.spec:31`/`:45-56` | spec `_keep_dirs=["generator","docs","meshtal","ptrac"]` 整目录复制 `app/generator/**.py`，但部署目录**无 `source_sampler.py`**；且部署 `distributions.py` grep `^class ` **0 命中**（无 `DistributionSampler`）、部署 `voxel_csg.py` grep `_polyhedron_field`/`_rot60`/`RHP`/`ARB` **0 命中** | 源码功能对用户等于不存在 | P1（对外声称交付则 P0） | 重打包 + 冒烟 `/api/source-demo-sample` | 构建 Owner+PM | 静态核实 |
| M-19 | 打包-spec 动态导入缺口 | `gui/mcnp_sidecar.spec:17-30`；`gui/backend/api_server.py:27-36`/`:1756`/`:1793` 等 | `_import_app` 实现 `return __import__(module)`（实参变量 → PyInstaller 静态分析不可见），调用点含 `_import_app("lattice")` ×5、`_import_app("diff_inp")`；`_keep_py` 无 `lattice.py`/`diff_inp.py`，部署全树 glob `*lattice*` 0 命中 | 可能：安装版格阵/INP 对比端点不可用 | P1（证实则 P0） | runtime 复核（起部署版 5001 POST 三端点） | 后端/构建+T4 | 静态核实（文件/调用点）+ **运行时结论无 shell 推断** |
| M-20 | 文档-测试文件数与实测不符 | `PROJECT_MEMORY.md:52`/`:87`/`:40`/`:153`；`docs/CHANGELOG.md:47` | 记忆：「vitest **546/0**（**69 文件**全过）」等；实测 `gui/test/**` = 76 文件 = **75 个 `*.test.ts(x)` + 1 `.snap`**（根 47 / volume 23 / ptrac 4 / source 1）。**并更正 T3 报的"81 个"**（61+19+4=84≠81） | 引用文件数必错 | P2 | 标注"当时快照" + 统一 75+1 + 更正 T3 | PM（+researcher 更正 T3） | 静态核实 |
| M-21 | 文档/注释-hexCenter 旧公式残留（30° 旋转） | `gui/src/utils/lattice.ts:123-128`；`docs/contracts/lattice-fix15-design.md:450`(L1) 等 16 处 | 旧公式引用原文：`x = i·(pitch·√3/2)`、`y = j·pitch + (i%2)·(pitch/2)`（docstring/契约/qa 报告/记忆共 16 处）；实测代码 `lattice.ts:133-136` = `x = col*pitch + row*(pitch/2)`、`y = row*pitch*(√3/2)`，与 `app/lattice.py:615-616` 逐字一致，且 Python docstring :611-612 记「旧公式…与此差 30° 旋转，已按 MCNP 修正」 | 注释与实现两套公式，下次改动易回归 | P1 | 16 处替换（实现不动） | 前端注释+架构师（T2 BE-14 ≡ T3 FE-07 请去重） | 静态核实 |
| M-22 | 文档-死模块被描述成生产消费方 | `docs/contracts/core3d-instancing.md:130`/`:188`；`docs/qa-report.md:89`；`docs/frontend-changes.md:17-18`；`docs/contracts/lattice-fix15-design.md:30` 等 | 上述文档把 `Preview3DLattice.tsx` 当装配视图生产接线；实测该文件全 `gui/` 树**零 import**（仅自引用 :2/:48/:176），`Preview3D.tsx:15` 直接 `import { buildLatticeInstances }` 并 `:783` 内联装配；记忆 :178 记 08-24 曾接线 → 判定"曾接线后被内联取代" | 照文档找不存在的调用链 | P2 | docs 标注废弃/清理 | 架构师+PM（+T3 删码） | 静态核实（取代时点为**无 shell 推断**） |
| M-23 | 文档-建议失效未结案 | `docs/qa-report-phase2.md:78`；`gui/src/utils/lattice.ts:447-471` | phase2 建议「`estimateLatticeExtent` 六棱柱以 pitch=1 估算，阶段3 需以真实格距覆盖」；实测真实格元盒已由 `/api/lattice-extent` 提供（`MacrobodyPreview.tsx:55`），该函数 `gui/src` 内零引用（仅测试用） | 建议悬空 + 死导出 | P2 | 标"已结案" + 按 FE-06 处置 | 架构师（+T3） | 静态核实 |

---

## 8. 已核实已清偿 / 勿再报（T4 原样引用，避免重复排期）

| 结论 | 证据 | 证据类型 |
| :--- | :--- | :--- |
| **api.yaml ↔ handlers 无漂移**：49 path / 49 operationId ↔ `api_server.py:1428-1476` 49 handler，集合一一对应 | 双向 grep 静态比对 | 静态核实 |
| **一键打包脚本确已删除**：源码根无 `release.bat`、无 `scripts/release.ps1`；部署目录全树 `*.bat` 0 命中 | glob | 静态核实 |
| **AI 接入正口径文档已存在**（过期的只是 M-05/M-06/M-07 三处，勿扩大为"全部 AI 文档过期"）：`AI接入.md:3`「启动程序会自动拉起 `--mcp-http`（本机环回 **8100**）」、`README.md:68` 同口径 | 文件原文 | 静态核实 |
| **`mcnp_bridge.py:53-57` 实现正确**（`--mcp-http` 唯一入口 + 延迟 import mcp，主 api_server 路径不触碰 mcp）；债只在 `:14-17` 注释 | 文件原文 | 静态核实 |
| **ADR 编号未被改名**（§4 编号与 `docs/contracts/*` 引用面未见冲突） | grep | 静态核实 |
| **`inp_generator.py` 的 F#1~F#7 技术债已清偿**（`review_findings.json` 记 Resolved，commit 1488aae 等；§7 技术债地图表全"已清偿"） | `app/generator/review_findings.json:5` + `UI_ARCHITECTURE.md:249-257` | 静态核实（行号为 2026-08-12 版，见 M-10） |
| **格阵 universe 空 STL 致命修复已闭环**（记忆 §6 明记"`_build_one_universe` 不再把 6 平面塞进 cell 表达式，改合成单 RPP 宏体…复验 17×17 全部 12 个 universe cell STL 非空"） | `PROJECT_MEMORY.md:462` | 静态核实（复审结论为历史记录） |
| **~~`source-demo-visualization.md` 契约与实现一致~~** —— **v5.1 自我更正**：该结论被 t4 reviewer 证伪一处，更正后限定为「该契约**除 `resolve_ds` 函数签名一处外**与实现一致」：契约 `docs/contracts/source-demo-visualization.md:25` 声明 `resolve_ds(eid: int, parent_value: float) -> list[int]`（"返回子分布号列表"），实现 `app/generator/distributions.py:401` 为 `resolve_ds(self, eid, parent_value, parent_si=None) -> dict`（返回 `{"distribution": n}` / `{"value": v}` / `{"default": True}`）——**参数个数与返回类型均不一致**；契约全文 grep 无第二处 `resolve_ds`/`parent_si` 补充说明（仅 `:25` 与无关的 `:34`），故原结论不成立。该项已由 reviewer 登记为 **TD-31（P2）**，本文件**不另计债条**（遵守冻结令）。<br>§8 其余表述仍成立：`docs/contracts/` 下 13 份契约中**仅** M-11 列的 3 份状态位陈旧（其余为历史批次存档，非债） | 文件原文比对（双方独立复核一致） | 静态核实（原结论已更正） |

---

## 9. 证据类型标注说明（供 T4 定级用）

- **静态核实**（可直接复核，参与定级）：文件存在性 / glob / grep 命中与零命中 / 文件原文摘句 / reflog 纯文本行（`.git/logs/HEAD` 是可读文件）/ `.git/refs/heads/main` 内容。
- **无 shell 推断**（**请 T4 标"待验证"，不参与 P0 定级**）：
  1. M-04 的"分布 v2 是否被夹带进 `08e5acef`" —— 需 `git show`；
  2. M-19 的"打包版是否真的 ImportError" —— 需起部署版 5001 实测三端点；
  3. M-22 的"取代发生的具体时点（哪个 commit 把装配改内联）" —— 需 `git log -p`；
  4. 一切**未提交文件清单 / `git diff --stat` / 文件 mtime** —— 本会话无 `git status`、无 mtime 能力；
  5. **PYZ 内部内容** —— 二进制串探测已试并**放弃**（对照探针 `preview-3d` 也返回 No matches → 探针不可靠），故凡涉及 PYZ 的判断均不下结论。


> 审计人：**researcher**（AgentTeams「tech-debt-audit」成员）
> 日期：**2026-09-10**（v5：追加 §7 T4 引用版精简表、§8 已清偿勿再报、§9 证据类型标注；v4 曾并入与 T2/T3 交叉核对后的 M-20 ~ M-23，见 §6）
> **只读审计，未修改任何代码。** 本文件为本次审计唯一的写盘产物（由项目经理明确授权新增；v4 / v5 追加内容同样只写本文件）；审计过程未改动 `PROJECT_MEMORY.md`、`docs/**` 既有文件、`app/**`、`gui/**` 或任何测试。
