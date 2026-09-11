# T2 后端代码债务审计清单（app/ + gui/backend/ + inputcard_mcp/）

> 审计人：**engineer-backend**（AgentTeams `tech-debt-audit` 团队成员）
> 日期：**2026-09-10**
> 范围：`app/**`（models.py、generator/*、lattice.py、coverage_check.py、voxel_csg.py、mc.py、quadric.py、preview_cache.py、meshtal/*、ptrac/*、material_library.py、sweep.py、spatial_index.py、overlap_*.py…）、`gui/backend/api_server.py`、`gui/backend/mcnp_bridge.py`、`gui/backend/_cross_section_helper.py`、`gui/backend/generate_step.py`、`inputcard_mcp/`、`gui/mcnp_sidecar.spec`
> **只读审计，未修改任何代码。** 本文件是本次审计的唯一产物（经 PM 明确授权写盘），除此之外未创建/修改/删除任何文件，未安装依赖，未启动或停止任何服务。

## 〇 方法与工具限制（如实声明）

1. **本会话无 shell 工具**（工具集只有 read / glob / grep / write / edit / subagent）。因此**未运行** pytest、`python -c`、任何构建或打包命令；**未实机验证**任何运行时行为。
2. 全部结论来自：**静态读取源码** + **只读 grep 全仓库计数**（判断"是否有调用者/是否唯一实现"）+ **与 docs/契约/测试文本互证**。每条都给 `file:line`，行号取自实际读到的内容。
3. 凡"必须跑起来才能定论"的项，一律进 **§三 存疑**，不写成结论。
4. 本仓库 §5 红线：严禁自动 npm install / pip install；测试须带硬性超时；5001 端口旧进程会劫持测试产生假象——本次审计**完全没有触发**这些操作。
5. 与前端相关但落在后端文件里的发现（如 `_cross_section_helper`、`generate_step`）计入本表；纯 `gui/src/**` 的发现归 T3。

### 计数总览

| 级别 | 条数 | 债 ID |
| :--- | ---: | :--- |
| **P0** | 2 | **BE-02、BE-05**（BE-01 于 v8 经 t4 判准降 P1） |
| **P1** | 8 | **BE-01**（v8 由 P0 降级）、BE-03、BE-04、BE-07、BE-09、BE-10、BE-11、BE-12（~~BE-06~~ 已于 v7 撤回，见 §五）
| **P2** | 12 | BE-08、BE-13、BE-14、BE-15、BE-16、BE-17、BE-18、BE-19、BE-20、BE-21、BE-22、BE-26 |
| **P3** | 3 | BE-23、BE-24、BE-25 |
| **合计** | **25** | 另含 §二「已核实已清偿」**12** 项（v7 +BE-06 撤回理由）、§三「存疑」10 项、相邻发现 3 项、§五 撤回与自查记录（**含 v7 BE-06 撤回 / v8 §4.2 撤回 / BE-02 口径订正**） |

---

## 一 完整债表

| 债ID | 类别 | 位置(file:line) | 证据 | 影响 | 建议严重度 | 建议处置 | 建议 Owner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BE-01** | 死代码 / 静默失败 / 契约漂移 **[静态核实 ＋ 无 shell 推断：见 §四]** | `gui/backend/generate_step.py:5-17`；`gui/backend/api_server.py:2597-2617`；`docs/contracts/api.yaml:657-687` | `generate_step(surfaces_data)` **完全忽略入参**，只写死一行 `#1=MANIFOLD_SOLID_BREP("MCNP Geometry");`（:15）就 `return step_path`；handler 却 `self._ok({"step_file":..., "message":"STEP 文件已生成"})`（:2617）。api.yaml 仍登记该端点 `operationId: generateStep`，summary 写"由曲面文本生成 STEP（3D 预览用，generate_step 备用通道）" | `/api/generate-step` 是**活跃注册端点**（handlers 表 `api_server.py:1446`）。任何调用方拿到 `ok` + 一个**非法 STEP 文件**（无几何，`ISO-10303-21` 头后只有一条占位实体）→ "看起来能用"的假功能，比缺端点更有害。另：`--open` 分支的 `os.path.join(dirname(__file__),"..","..","..", "FreeCAD_1.1.1-Windows-x86_64-py311")`（:30）三级 `..` 从 `gui/backend` 只能到 `D:\MCNP`（`启动FreeCAD预览.bat:6` 依赖该行为）→ 实际永不命中 | **P1**（**v8 经 t4 判定降级**：t4 采「用户是否被误导／是否存在用户可见错误」为判准 → 全仓零调用方，故 P1；若改采「契约承诺不存在的能力 + 假功能」判准则回 P0。**判准已在 t4 `TD-04` 行明示**，PM 换判准只需改该条） | 三选一并写进契约：① 真实现（复用 `/api/export-step` 的 FreeCAD CSG 通道，删掉这个 stub）；② 删端点 + api.yaml 条目 + `mcnp_sidecar.spec:40` 的 `generate_step.py`；③ 保留则响应改 `{"status":"error","message":"未实现"}`，不再回 `ok` | backend（+ docs 同步 api.yaml） |
| **BE-02** | bug（真实数据路径坏了）**[静态核实 ＋ 无 shell 推断：见 §四]** | `app/generator/distributions.py:671-708`（vs `:96-106`、`:26`、`:1-31`）；`app/generator/source_sampler.py:96-116`；**UI 真实路径**：`gui/src/components/SourceTab.tsx:119` → `gui/src/utils/api.ts:153-161` → `gui/backend/api_server.py:1469/:3118` → `:3141-3155` → `source_sampler`；**导入 INP 路径**：`app/generator/parsers/core.py:1154-1155`（写 `sdef_distributions`）；**测试**：`tests/unit/test_distribution_sampler.py:120-146`、`tests/integration/test_api_contract.py:634,650` | **分支口径【v8 已订正，原表述有误】**：`_DS_LETTERS`（`distributions.py:45`）= `("H","L","S","T","Q")` 是**解析白名单**；`_resolve_ds`（:671-708）**只读 2 个键** —— **`S`（:684-691）读 `distributionIds`**；**`Q`（:676-683）、`L`（:692-696）、`H`/`""`（:697-707）读 `ds.get("values")`**（`vals = ds.get("values") or []`，:675）；**`T`（:673-674）立即 `return {"default":True}`**（交 `resolve_ds_t`，而它 :712-714 **也读 `values`**）→ 而 `_parse_ds`（:96-106）**只写 `type`/`param`/`distributionIds`、从不写 `values`** ⇒ **Q/L/H/T 恒走默认；S 是唯一读对了键的分支**。（我 v5–v7 曾把 S 与 Q/T 并列写成"恒空列表"，**属错误**，经 t4 实读驳回后订正，留 §五 5.4。）**但 S 分支另有更深的错位（t4 补充，我复核确认）**：`_parse_ds:104-105` 把 `toks[0]` 塞进 `param`、`toks[1:]` 塞进 `distributionIds`，而 `app/docs/源分布卡说明.md:175` 写 `DSn S S1 … Sk`（**S 无独立 param**）⇒ **J 列表整体右移一位**：解析 `DS1 S 2 3` 得 `param="2"`、`distributionIds=["3"]` ⇒ 索引 0 取到分布 **3**（应为 2）；而 `app/docs/C810_卡片格式详细.md:183` 又写 `DS[n] var Dn1 …`（**含 var**）⇒ **两份派生文档自相矛盾，权威只有 C810.pdf**（本次未访问）。**"只有 S 分支可用"这一前提因此也不完全成立——S 同样待修，且只改读键修不好它。** **另：`_generate_structured_distributions`/`emit` 对 DS 只回放 `rawText` 或重建 `head = f"DS{idx}  {ds_type}" + param + refs`（:222-235），从未读 `values`** → `values` 键在产消两端**从来不存在**（唯一出现处是测试里手写的 dict） | 分布源的 **DS 依赖链**（`ERG=FPOS D1` / `POS=Dn` / 依赖变量查表）在**真实导入的 INP 上全部静默失效**：`DistributionSampler`/`source_sampler` 恒走 `_ds_value` 的 default 分支（=14.0 MeV / 默认），`/api/source-demo-sample` 给出**语义错误的抽样结果且不报错**，违背 PROJECT_MEMORY S1「按 C810 做全不降级、有错就地报」的明确决议。属"测试 pin 了不存在的数据形状"——把 bug 锁死（`tests/unit/test_distribution_sampler.py:119-122` 就是按 `_parse_ds` 当前写法构造的，因此**该单测无法发现 J 起点错位**） | **P0** | ① **统一读键口径**（勿再只用一种改法）：`_parse_ds` 与 `_resolve_ds` 必须协商成同一套键（要么 `_parse_ds` 补写 `values`，要么四个分支全改读 `distributionIds`）；② 但**先裁 `param` 语义 + S 的 J 列表起点**（权威 C810.pdf，`app/docs/` 两份派生文档互相矛盾，见证据列），否则"只改读键"修不好 S 分支，还会把索引整体错位固化；③ 补**走真实解析路径**的回归（`parse_distribution_lines(["DS1 S 2 3"])` → `resolve_ds` → 期望 `{"distribution": <J1>}`，而不是手写 dict）；④ **不要**改动 `source_sampler` 的 `pos_index` 接线（该项经 t4 实读驳回，见 §五 5.4） | backend（+ tester 补回归；S 分支的 `param` 语义裁定需 docs/C810 权威） |
| **BE-03** | silent failure（生成错误产物） | `app/generator/inp_generator.py:479-496`；同类 `:919-927` | 旧兜底分支 `json.loads(adv.sdef_raw_text)` 的 `except (json.JSONDecodeError, TypeError): pass`（:495-496）——解析失败**什么都不输出、不报错、不告警**，`_generate_distribution_sdef` 只返回 SDEF 行；`:921-926` 的 `except: return []` 同型（分布 JSON 坏 → 静默零卡） | 数据坏/旧格式时生成的 INP **丢失全部 SI/SP 卡**仍报"生成成功"，用户拿去跑 MCNP 才炸；错误被推到最不方便发现的地方。与 BE-10（该分支本就该退役）同源 | P1 | 失败时 `raise` 或把原因经 handler 的 `_err` 通道回传前端；与 BE-10 的迁移一并处理 | backend |
| **BE-04** | 契约漂移（**已坐实会起错进程**） | `gui/backend/mcnp_bridge.py:14-17` vs `:41/:47/:53/:60-61`；`docs/手动打包方法.md:149-151`；`docs/inputcard-mcp.md:137,140`；`PROJECT_MEMORY.md:46,52,356`；`inputcard_mcp/__init__.py:1-8`；`inputcard_mcp/requirements.txt:1`；`inputcard_mcp/server.py:2` vs `:506` | **PM 注入证据已核实并补足机制**：docstring(:14-17) 宣传 `--mcp-server 以 inputcard_mcp 的 MCP server 模式运行（本地 stdio…）`；实际分派只有 `--meshtal-worker`(:41) / `--ptrac-worker`(:47) / `--mcp-http`(:53)，**无 `--mcp-server` 分支**。**比 PM 初判更硬的一点**：三个 `if` 全不命中时会 **fallthrough 到 `import api_server; api_server.main()`（:60-61）**，即 `python.exe --mcp-server` 的实际结果是**起第二个绑 `0.0.0.0:5001` 的 `ThreadingHTTPServer`**（api_server.py:15、:3602）——"说要起 MCP、实际起了第二个后端"，正是 §6「5001 端口劫持」坑的入口。且 `docs/手动打包方法.md:150-151` **正在教用户这么用**（`gui\dist\python\python.exe --mcp-server` 作本地 stdio MCP server，还教 `pip install -r inputcard_mcp/requirements.txt`）；`docs/inputcard-mcp.md:137,140`、`PROJECT_MEMORY.md:46/52/356` 同；而 `inputcard_mcp/server.py:506` 自己写"stdio 已移除"、`__main__.py:1` 直接 call main（= 仅 HTTP 8100）、`AI接入.md:3` 说 8100 是唯一入口 → **五处自相矛盾** | **P1**（**不降级为 P2**）：① `手动打包方法.md` 是发布手册，`AI接入.md:25` 又要求用户"若 8100 未就绪，请重启程序或看顶栏"——排障时照手册敲 `--mcp-server` 是**自然动作**，不是"没人会照做"；② 后果不是"功能没起来"而是**起错进程**并叠加端口劫持老坑（该坑在 memory 里已三次复现、`只有新增端点才暴露`）；③ 打包版还教了用户装依赖（违反 §5 红线） | ① `mcnp_bridge.py` 加显式 `--mcp-server` 分支：打印"已废弃，请用 `--mcp-http`"后 `sys.exit(2)`（**绝不 fallthrough 到 api_server**）；② `手动打包方法.md:149-151`、`inputcard-mcp.md:137,140`、`PROJECT_MEMORY.md:46,52,356` 全部改 `--mcp-http` + 8100，并删掉那条 `pip install` 指示；③ 清 `inputcard_mcp/__init__.py`、`requirements.txt:1`、`server.py:2` 的 "stdio" 字样 | backend（+ docs） |
| **BE-05** | 回归守卫缺失（**历史已复发**）**[静态核实 ＋ 无 shell 推断：见 §四]** | `gui/mcnp_sidecar.spec:17-31,45-56`；`gui/backend/api_server.py:1756`（`_import_app("diff_inp")`）；`docs/手动打包方法.md:506`；`PROJECT_MEMORY.md:97,465` | `_keep_py` 白名单逐个手写，且**全仓库零测试**校验它 vs 端点实际 import 集合（grep `_keep_py`：命中仅 spec 自身 + 文档）。**实存漏项（v7 逐项复核后收敛为 1 个）：`app/diff_inp.py`** —— `api_server.py:1756` 以 `_import_app("diff_inp")` **动态** import，且它**既不在 `_keep_py`、也无任何静态 import 边** → 打包版 `/api/diff-inp` 必 `ImportError`。**【已更正】`analytic_slice.py`（spec:19）与 `stl_cross_section.py`（spec:28）都在 `_keep_py` 内，不是漏项（我在 v1 行内曾误列，已于 v5 更正，t4 复核确认并同步改其 TD-02 行）。** 另 `lattice.py` 不在 `_keep_py`，**是否可用仍属 t4 与我的未决分歧**：我主张可由 `inp_generator.py:9`/`parsers/core.py:18` 的 `from app import lattice` 静态边进包，t4 指出 `__import__("lattice")` 取**顶层名**、与 `app.lattice` 在 PYZ toc 中非同一条目，且部署全树 2301 条路径内 `lattice` 零命中 ⇒ **只能 runtime 定论（一条 `POST /api/lattice-extent`）**；**无论结论如何，`diff_inp.py` 的漏项都成立**（见 §五 5.4） | 打包版（sidecar）调 `/api/diff-inp`、`/api/cross-section` 的解析切片分支必 `ImportError` → 端点 500；**dev 模式因 `APP_DIR` 直接进 `sys.path` 而永不复现**，所以开发/测试全绿而发布版坏。同类 bug 已复发至少两次（`material_library.py`/`gpu_pref.py` 曾漏 → 端点 500，PROJECT_MEMORY:97），现在只剩"每次打包人工核对 spec"（手动打包方法.md:506）这条**人因防线** | **P0** | 新增 `tests/integration/test_sidecar_spec_keep.py`：解析 `mcnp_sidecar.spec` 的 `_keep_py/_keep_dirs/_hidden`，与 `MCNPHandler.handlers` 覆盖到的 `_import_app(...)` / 顶层 import 模块名做**双向集合断言**（缺一即红）。几十行闸门可一劳永逸堵住该类 500 | tester（+ backend 提供 import 清单 seam） |
| ~~**BE-06**~~ | ~~数据丢失（AI 工作区往返）~~ **已撤回（v7）** | — | **🔴 本条为假阳性，撤回。** 我原判「`_sections_to_deck` 不读 `universe_comments`」**错误**：复核确认 `inputcard_mcp/server.py:101` 的 `return deck_from_json(d)` 传入的是**整个 sections dict**（`d = dict(sections)`，:92 只做 `advanced→adv` 改名与 None 归一，**不删任何键**），而 `deck_from_json`（`gui/backend/api_server.py:1347-1348`）**恰好读** `universe_comments` / `universeComments`；`_deck_to_sections`（`server.py:83`）亦显式回写该键。故 `generate_document` / `patch_section`（不带 inp）/ `add_shape` 三条 MCP 路径下 `universe_comments` **均不丢失**；前端 `App.tsx:92` 的浅合并只是**第二道**保险，不是唯一防线。反证由 T3 提供、我逐行复核确认 | — | **撤回条目，不计入总数**（26 → **25**）；证据链与我的自查过程见文件末 **§五 撤回与自查记录** | — |
| **BE-07** | 并发 / 全局可变状态 | `gui/backend/api_server.py:110`（`_STL_SESSION`）、`:127`、`:2677`、`:2693`、`:2751-2753`、`:2839`；`app/preview_cache.py:40-41,184-188,240-246`；对比 `:15`（`ThreadingHTTPServer`）、`:136`（全文件唯一一把锁） | 服务端是 `from http.server import ThreadingHTTPServer as HTTPServer`（:15，**每请求一线程**），但：① `_STL_SESSION` 是模块级 dict 且**逐请求整体重绑定**（`global _STL_SESSION` + `_STL_SESSION = {...}`），preview 路径是"先 `_clear_stl_session()` 删上一会话目录、再建新会话"（:2751-2752），缓存命中分支同样整体重绑（:2693）；② `PreviewCache._index/_order` 无锁，`get/put/evict_lru/_drop` 均可重入，`_drop` 内 `shutil.rmtree` 直接删目录；③ 除 `_SURF_CLASSES_LOCK`（:136，只护 `_surf_classes`）外无任何锁 | 两个并发 preview-3d（前端确实有多个入口）会**互删对方刚生成的 STL 会话目录**；表现为"STL 偶发空 / 截面缺栅元 / 缓存目录被删"这类**难以复现**的随机故障。且 `preview_cache` docstring 宣称"纯 stdlib、无运行时依赖"会让人误判它无状态 | P1 | 加一把请求级 `_PREVIEW_LOCK`（preview-3d / preview-lattice / cross-section / clear-stl 共享），或把 `_STL_SESSION` 改成"按 request 持有会话对象 + 显式生命周期"；`PreviewCache` 内部加 `threading.Lock` 保护 `_index/_order`（`_drop` 的删目录移出锁） | backend |
| **BE-08** | 打包环境鲁棒性 | `gui/backend/api_server.py:94-105` | `MEMORY_DIR = r"D:\MCNP\memory"`，`_cache_base()` 在**模块导入期**执行 `os.makedirs(d, exist_ok=True)` 两次（`preview_cache` / `preview_cache_lattice`），**无 try/except、无回落**。对比 `preview_cache.PreviewCache.__init__` 本身有 `base_dir=None → tempfile.mkdtemp()` 的良性默认；`app/material_library.py:40-62` 已有"env > D 盘 > %APPDATA% > temp"三段落链 | 导入 `api_server` 即依赖 `D:\MCNP` 可写：换机 / 无 D 盘 / 权限受限 → `OSError` 直接冒泡 → **sidecar 后端起不来（整个 GUI 无后端）** | P2 | `_cache_base` 包 try/except 并回落 `%LOCALAPPDATA%` / `tempfile`（照 `material_library.material_dir()` 既有落链） | backend |
| **BE-09** | 死代码 / 白名单过宽（**记忆点名的 `_SI_LETTERS`**） | `app/generator/distributions.py:43`（`_SI_LETTERS = ("L","H","A","S","Q","T","F","V")`）、`:61-68`（`_parse_si`）、`:472`（sampling 报错）；对照 `:44` `_SP_LETTERS`、`:45` `_DS_LETTERS` | `_SI_LETTERS` 含 **Q/T/F/V**，而抽样侧只认 `H`/`""`/`L`/`A`（`_sample_entry:451-472`），其余一律 `raise SourceSamplingError(f"SI 类型 {si_type} 无效（MCNP 仅支持 H/L/A/S）")`。PROJECT_MEMORY:22 已记载 C810 权威结论：「**SI 卡只有 H/L/A/S 四种**（`_SI_LETTERS` 里的 Q/T/F/V 是多余的，抽样器对它们报错）」。**已核实：该记忆结论与代码现状一致，确认多余** | ① `_parse_si` 把 `SI1 Q ...` 判成**合法类型 `"Q"`**：生成/往返**看不出来**（`emit` 照 rawText 原样回放），只有走到抽样才炸 → **错误被推迟到最不方便发现的地方**；② 未知字母（如 `SI1 B 1 2`）会**被当成数值 token** 塞进 `values`，后续 `_floats` 抛"分布值无法解析为数值"——**归因错误**（真正的问题是非法 SI 类型） | P1 | `_SI_LETTERS` 收紧为 `("L","H","A","S")`；未知首 token 记 warning 或按 C810 明确报"非法 SI 类型"，**不要静默当值**；顺带核对 `_SP_LETTERS` 的 V、`_DS_LETTERS` 与 `_resolve_ds` 判断集是否同源 | backend |
| **BE-10** | 僵尸字段（**PM 注入证据 · 已核实**） | 定义：`app/models.py:463-465`；wire：`gui/backend/api_server.py:1320`（`_adv_from_dict`）、`:2067`（`deck_dict["sdefRawText"]`）、`docs/contracts/api.yaml:2289`（schema）、`:2244`（描述）、`:2207`（优先级说明）；读：`app/generator/inp_generator.py:1336`、`:479-496`、`app/generator/validator.py:351`、`:361`、`inputcard_mcp/server.py`（随 adv 透传）；写：`app/generator/parsers/__init__.py:79`（仅默认值）、`:269`（读）、`app/generator/parsers/core.py:1154-1155`（**只写 `sdef_distributions`**）；前端：`gui/src/utils/sourceAdv.ts:159,192`、`gui/src/utils/contract.ts:44`；测试：`tests/unit/test_generator_sdef.py:104-106` | 结论 = **僵尸字段（停写，但 6 处仍读）**：① `parsers/core.py:1154-1155` 把 SI/SP 只写进 `sdef_distributions`，`parse_inp_text` 走 `data.get("sdef_raw_text","")`（`__init__.py:269`）→ **对任何新导入的 INP 恒为 `""`**；② 唯一"写入"来源是前端旧存档迁移 `sourceAdv.ts:192`（`if (!adv.sdef_raw_text && old.sdefRawText)`），而顶层 `old.sdefRawText` 同文件 `:200` 刚被删、**已无人写**；③ 它现在**唯一还"活"的原因是** `tests/unit/test_generator_sdef.py:104-106` 手写它去覆盖 `inp_generator.py:479-496` 的兜底分支；④ 自述已承认：`models.py:463-464`「新解析已停写，仅作旧存档回退读取」、`api.yaml:2244`「新解析已停写，仅读兼容」 | ① 后端 4 处读兼容分支（generator 兜底 / validator 空判定 / api_server 序列化 / model 字段）**永远不会被真实数据命中** = 零覆盖的活代码；② `inp_generator.py:1336` 的 `_has_dist = bool(adv.sdef_raw_text) or bool(_dist_json_nonempty(...))` 真数据下左项恒假，逻辑正确但**读起来像存在第二条路径**；③ **无清理计划** = 永久技术债（这正是不该只写"兼容保留"注释的原因） | P1（字段本身 P2；叠加"6 处读 + 1 条测试锁死 + 无退役计划"升 P1） | 采纳"**保留 + 一次性迁移 + 设退役条件**"三步：① 前端迁移里把 `old.sdefRawText` **转成 `sdef_distributions` 条目**（按 `parse_distribution_lines` 语义），迁完即无真数据来源；② 随后一次性删除：model 字段 / generator 兜底分支 / validator 左项 / api_server 两处 / `contract.ts:44` 行 / `api.yaml:2207,2244,2289` / 那条测试，并把 `api.yaml:2244` 改为"v1 存档迁移后删除"；③ 不采"仅保留 + 加注释"（注释已存在，等于无计划） | backend + engineer-frontend（迁移在前端）+ docs（api.yaml） |
| **BE-11** | 测试文档误导（**系统性，PM 注入 · 已扩大到 14 处**） | `tests/integration/test_tech_debt.py:2`（"测试先行，当前代码故意先红"）、`:9`（"当前应为 RED"）；同文件**自相矛盾** `:62-64`、`:72-74`、`:92-94`、`:102`（写"已清偿…当前应为 GREEN"）；`tests/integration/test_roundtrip.py:40,51,58,66`（"当前应为 RED（头泄漏）"）、`:168`（"当前 RED：options 丢失"）、`:253`（"当前 RED：多粒子被丢"）；`tests/integration/test_sample_smoke.py:87`（"当前 RED（C 注释头泄漏）"）、`:100`（"当前 RED：validate_deck…AttributeError"）；`docs/backend-changes.md:44-52`（仍把这些用例列为"本轮预期保持红 / P1"） | **PM 注入的 `test_tech_debt.py:1-10` 已核实，并扩大到全仓库 14 处**"当前应为 RED / 当前 RED / 预期保持红 / 故意先红"。逐条对照代码，对应能力**均已清偿**：`:59-104` 断言的是 F#3/F#7 的**达成态**（函数内零 `import json/re/sys/pymcnp`、模块顶层有 pymcnp）且 docstring 自己写了 GREEN（**同一文件内互相矛盾**）；`test_roundtrip.py:40/51/58/66` 断言 `g1 == g2`（R1 不动点 = F-A 方案 C 达成态）；`:168` 断言 `mat.options == m2[num].options`（F-D 达成态）；`:253` 断言多粒子计数（F-C 达成态，代码 `parsers/core.py:825-826` 已按逗号展开）；`test_sample_smoke.py:100` 声称 `validate_deck` 会 AttributeError，而 `validator.py:447-457` 已 `_unwrap_cells(deck.cells)`（F-B 达成态）。`docs/backend-changes.md:87-92` 的 A.1 表列明这些 commit（`c774e56`/`bf0a2c7`/`52ca251`/`1488aae`） | 新人/AI 读到"预期红 = 正确"会**把真实红灯当绿灯容忍**（反向门禁），或在已绿用例上继续排查"不存在的技术债"——本轮审计（含 T1）自身的可信度风险；也直接解释了为什么"技术债集中地"这类记忆会长期不退役 | **P1**（建议 PM **直接按文件批量派单**，成本低、收益高） | 把这 14 处 docstring + `docs/backend-changes.md:44-52` 一次性改写为"F-X 已清偿（commit xxx）／现状 GREEN"；并把「当前应为 RED」这种表述**从测试文档中禁用**（未清偿项改在 issue/契约里标注） | tester + docs（可并入 T1） |
| **BE-12** | 重复实现（**已行为分叉**） | `gui/backend/api_server.py:2039-2092`（`_handle_parse_inp` 内联序列化）vs `:1352-1391`（`_deck_to_frontend_dict`）+ `:1395`（别名导出）；MCP 消费方 `inputcard_mcp/server.py:478` | 两段**几乎逐行相同**的 dataclass→前端 camelCase 序列化（`to_dict` 闭包 + `universe_comments→universeComments` + materials `rows→nuclides` + cells `num/surfaces/impN/P/E` + tallies 映射），但**内联版多 11 行前端中间态字段**：`sourceMode`/`sdefFields`/`kcodeFields`/`ksrcPoints`/`sdefRawText`/`distributions`/`sswFields`/`ssrFields`/`_warnings`（:2061-2091）。而 MCP `/workspace` GET 走的是**少字段那一份**（`deck_to_frontend_dict(_ws_deck())`） | 同一个"后端 deck → 前端 deck"契约有两份实现且**已分叉**：前端从 MCP 拿到的 deck 缺全部顶层源/计数中间态字段（靠 `App.tsx:92` 的 `{...deck, ...aiDeck}` 合并 + `sourceAdv.ts:147` 迁移兜底才没崩）。任一边改字段另一边静默落后 → 这是 BE-06 之外的**第二条 AI 工作区字段漂移通道** | P1 | `/api/parse-inp` 改调 `_deck_to_frontend_dict`，把"是否含前端中间态字段"做成该函数的显式参数（如 `include_frontend_aliases=True`）；一份实现两个消费者，MCP 侧按需开启 | backend |
| **BE-13** | 死代码 / 表层化（"技术债集中地"残留） | `app/generator/inp_generator.py:422-426`（`_src_field`）、`:908-927`（`_generate_structured_distributions`）；重复定义：`app/generator/inp_generator.py:337` / `app/generator/source_sampler.py:45` / `app/generator/parsers/core.py:96`（三份 `_is_d_ref`） | grep 全仓库：`_src_field` 仅 `:422` **定义**，**零调用者（含测试）**；`_generate_structured_distributions`（:908-927）实现体只剩"`json.loads` + 空值守卫 + 调 `distributions.emit_distribution_entries`"，且 `not dist_json` 守卫与 `:1336` 的 `_dist_json_nonempty` 重复；`_is_d_ref` 三处定义（`inp_generator:337` 与 `core.py:96` 为同语义函数，`source_sampler:45` 另一份） | PROJECT_MEMORY:459「`inp_generator.py` 仍为技术债集中地」——**在当前代码里的具体形态**：迁移走了实现、没删旧壳，读代码的人会以为还有第二条路径；`_is_d_ref` 三份是"改一处漏两处"的经典面（SDEF D-ref 判定散落） | P2 | 删 `_src_field`；`_generate_structured_distributions` 内联进 `:473-478`（或改为直接调 distributions 模块函数，消除重复守卫）；`_is_d_ref` 收敛到单一实现（建议 `distributions.py`）后三处 import | backend |
| **BE-14** | 文档漂移（跨语言镜像） | `gui/src/utils/lattice.ts:123-128`（docstring）vs `:130-137`（实现）vs `app/lattice.py:604-616`（权威） | `hexCenter` **实现**与 Python `hex_center` **逐字一致**（`x = col·pitch + row·(pitch/2)`、`y = row·pitch·√3/2`，已逐字核对），但该函数**上方 docstring 仍写旧公式** `x = i·(pitch·√3/2)`、`y = j·pitch + (i%2)·(pitch/2)` 并断言"相邻 (0,0)→(1,0) 距=p"。`app/lattice.py:610-612` 记的正是"旧公式与此差 30° 旋转，已按 MCNP 修正（2026-08-25 交叉验证后替换；golden hexCenter/positions.hex 同步更新）" | 注释与实现两套公式并存：读者按注释推导 col/row 语义会得到与实现**差 30° 旋转**的格位——这正是历史上导致 `hex_center` 返工的同款歧义（memory 上一批次"根因3 hex 未居中"）。属**注释漂移**而非行为漂移，但"下一次改 hex 的人会先信注释" | P2 | 用 `app/lattice.py:604-614` 的权威描述替换 `lattice.ts:123-128` 的旧公式段（**实现不动**）；golden `latticeGolden.json` 已是双端锚点，无需改 | frontend（注释）+ backend 复核 |
| **BE-15** | 重复实现（打包通道共用代码） | `gui/backend/_cross_section_helper.py:20-26`（导入期自建类表）、`:47-69`（曲面行解析）；对照 `gui/backend/api_server.py:139-157`（`_surf_classes()` 惰性双检锁）、`:179-223`（`parse_surfaces`）、`:263-291`（`parse_tr_cards`）；`:80-100`（AST 序列化） | helper 在**模块导入期**执行 `for _name in dir(_pi): …` 自建 `_SURF_CLASSES`（:20-26），与 api_server `_surf_classes()` 的惰性双检锁版是**同一逻辑两份实现**；helper 另内联一份曲面行解析（含 `len(_parts) > 2 and _SURF_CLASSES.get(_parts[2].upper())` 的关键字启发式定位，与 api_server `_kw_idx` 同思路）与一份 TR 卡解析（`:106-130`） | 该文件被 `mcnp_sidecar.spec:40-43` **打进 sidecar**，是冻结版 `/api/cross-section` 的真实通道。两份解析器各自演进 → "同一 deck 在 preview 与 cross-section 下解析结果不同"的隐蔽不一致；且导入期构建类表与 sidecar"启动即快"的目标相悖（PROJECT_MEMORY:59 的提速成果会被这条抵消一部分） | P2 | helper 改为复用 `api_server` 的 `parse_surfaces` / `parse_tr_cards` / `_surf_classes`（同目录、冻结包内同层，路径已具备），或把三者上提为小深模块；至少把导入期类表改惰性 | backend |
| **BE-16** | 静默失败（worker 内裸 except） | `app/_freecad_cross_section_worker.py:656-657`（**裸 `except: pass`**，即 `except:` 无异常类型）；同文件同类 `:394`、`:440`、`:710`、`:714`（`except Exception:` 系） | `try: surfaces[num] = <构造 FreeCAD 半空间/宏体> except: pass`——**裸 `except:` 全吞**（连 KeyboardInterrupt/SystemExit 都吞）。失败后 `surfaces` 缺该号，随后 `eval_ast(cell["ast"], surfaces, …)` 取不到键 → 该栅元 eval 失败（外层 try 转 error 或静默少切片） | 曲面构造失败**完全无痕迹**：用户看到"截面缺了几块 / 截面失败"却拿不到"哪个曲面、哪类曲面不支持"。`docs/backend-changes.md:1023` 已确立项目级标准（T6：宽 except 必须 `logger.warning` 记录回退原因），此处是**未执行同一标准的裸 except**，且发生在 FreeCAD 子进程里（日志更难取） | P2 | 改 `except Exception as e: errors.append((num, repr(e)))`，把 `errors` 并入 worker 响应（`status:"ok"` + `surfaceErrors`）由 handler 透传；至少 `traceback.print_exc()` 到 stderr | backend |
| **BE-17** | 跨进程缓存竞态 + 静默损坏 | `app/meshtal/meshtal_cache.py:96-119`（`evict`）、`:48-52`/`:78-82`（损坏静默 miss）、`:84-94`（`put` 的固定 tmp 名）；`app/meshtal/_meshtal_worker.py:70,136`；`:25`（目录默认 `tempfile.gettempdir()`） | `evict()` 无锁：`listdir` + `getsize/getmtime` 后按 mtime 升序 `os.remove`（:101-119），**不过滤 `*.tmp` 与 manifest**，`except OSError: pass`。缓存目录是进程间共享的 `%TEMP%/mcnp_meshtal_cache`，而**每个 meshtal worker 子进程各 new 一个 `MeshtalParseCache()`**；`put` 用**固定** `tmp = p + ".tmp"`（:87-88）→ 两进程写同一 `(path,mtime,tally)` 互相覆盖；`os.replace` 失败分支 `os.remove(tmp)`（:93）在 tmp 已被并发驱逐时抛 `FileNotFoundError`（**未捕获**） | 多 worker 并发取同一 meshtal 的不同 (energy,time) 帧时：可能删掉对方刚写的 tmp/manifest、或 `put` 抛 `FileNotFoundError` → worker 转 error 信封（表现为"偶发解析失败"）；`get/get_manifest` 遇损坏**静默全量重解析**（大文件秒级→分钟级）且无日志 | P2 | `evict` 排除 `*.tmp`；tmp 名加 `pid`/随机后缀；两处 `except` 加 `logger.warning`（区分"版本不匹配的正常 miss"与"真损坏"）；或改为每进程独立缓存子目录 | backend |
| **BE-18** | 死代码 + 契约缺口 | `app/meshtal/downsample_plan.py:36-43`（`ResolutionDecision`）、`:54-67`（`decide_resolution`）、`:16`（`MAX_RESOLUTION`）；生产侧 `app/meshtal/volume_builder.py:63`（`plan_downsample`）、`app/meshtal/_meshtal_worker.py:133`（裸 `int(payload.get("resolution",128))`）；契约 `docs/contracts/meshtal-visualization.md:235` | `decide_resolution` 的**唯一消费者是测试**（`tests/unit/test_meshtal_downsample_plan.py:105-136`）；`MAX_RESOLUTION` 在 `app/` 内**零消费者**。契约声明的"A2.3 自动 128³ / 256³ 显式 / 超预算弹窗"决策函数**没有接线**，实际分辨率由请求方直接透传 | 契约与实现存在未闭合缺口：契约说系统会做分辨率裁决，实际是"调用方说什么就是什么"（超预算无保护）；也属"契约先行的产物没落地"，会让人高估成熟度 | P2 | 二选一：`_meshtal_worker` 用 `decide_resolution` 替换裸取值（让契约成立）；或修订契约删去该 seam 并把函数标注为"未接线（备用）" | backend（+ docs） |
| **BE-19** | perf hazard（优化做了没接线） | `gui/backend/api_server.py:675`（`_scan_lattice_z` 内 `lattice._cell_pz_bounds(cell.get("surface_expr",""), surf_text)`）；被调方 `app/lattice.py:932-961`（`:944-945` `if surfaces is None: surfaces = _parse_surface_cards(surfaces_text)`） | `_cell_pz_bounds` 的 `surfaces` 预解析参数 docstring 自述"性能：单卡多次扫描时不必每次全量 `_parse_surface_cards` 整段曲面卡文本"（:936-937），而 `_scan_lattice_z` 是**逐 cell 循环**且**未传** `surfaces` → 每个 cell 触发一次全量正则解析。全仓库另一调用点 `lattice.py:988` **已正确传参**（有对照片） | BEAVRS 量级（数百 universe × 数十 cell）下是预览请求的**确定性叠加延迟**，与 §6 记录过的"compose_lattice_tree 97s"类性能坑同族；属"优化做完没接线" | P2 | `_scan_lattice_z` 入口解析一次 `lattice._parse_surface_cards(surf_text)` 后沿递归透传（函数已是递归，加一参即可）；顺带给 `_cell_pz_bounds` 加"未传 surfaces 时按 `id(surfaces_text)` 内部缓存"兜底 | backend |
| **BE-20** | 静默失败（超时不可归因） | `gui/backend/api_server.py:1668-1676`（`except subprocess.TimeoutExpired: pass`）；落盘侧 `app/sweep.py:265` | `proc = subprocess.run([...], timeout=300)`（:1668-1671）超时后 `except subprocess.TimeoutExpired: pass`——**不写 `rec["exitCode"]`（保持 None）、不记日志、不置超时标记**，后续 `parse_keff` 也不跑。落盘 manifest 里该 run 与"MCNP 未产生任何输出"**不可区分**（`build_summary_tsv` 两者都输出 `n/a`） | 参数扫描（最长 30 分钟总预算）出问题时，用户/PM **无法判断某组合是"超时"还是"崩溃"还是"无 keff 输出"**。`sweep.py` 一侧（T3 预算 / T8 清理）已硬化，**恰恰这里漏了归因**，而"命令加硬性超时"正是本仓库纪律（§5） | P2 | 置 `rec["exitCode"] = "timeout"`（或 `rec["timedOut"] = True`）+ `logger.warning`；summary TSV 区分 `n/a` 与 `timeout` | backend |
| **BE-21** | 重复实现（性能冗余 + **跨端 7 处 pitch 换算副本**） | ① 轴向预计算：`app/lattice.py:1239-1247`（`compose_lattice_tree` 入口全量 `axial_cache`）vs `:1336-1341`（`_expand_universe` 惰性回填）；② **hex pitch 换算副本（v5 经 T3 复核后放大、我侧已逐处核实）：7 处 / 2 个方向** | **① 轴向预计算**：入口对**全部** `sub_by_u` 预计算（每 cell 走 `_cell_pz_bounds`），而 `_expand_universe` 自身已有惰性回填（入口注释 :1243 声称预计算"供命中"，两套叠加）。**② hex pitch 换算（见下表）**：同一条"MCNP LAT=2 六棱柱格距"规则在**正向（格距→间距）2 处**与**反向（pitch→跨度）3 处**各写一遍，判据还不完全同源（`str(lat)=="2"` 参数 vs 局部 `fg.lat`），加上 2 处 TS 镜像/消费点 | ① "只渲染一个格阵"的请求也付出全 `sub_by_u` 成本（BEAVRS 量级可观）；② **7 处副本是"改一处漏六处"的结构**，而 hex pitch 历史上**已经因此出过事故**（`:925-926`/`:1038` 的注释即"先前用 py 撑大间距/pitch 错用"的历史伤痕，与本项目上一批次"根因2 subPitch 硬编码 1.26"同族）；③ 与 **FE-01 的 `expected_python` 方案直接耦合**——公式副本不同批改，golden 也拦不住 | P2 | ① 去掉入口全量预计算（保留惰性回填，结果等价）；② **hex pitch 收敛为单一权威 seam**（建议落在 `app/lattice.py`：正向 `_hex_pitch(extent) -> (px, py)` + 反向 `hex_half_extent(pitch) -> (hx, hy)` 一对纯函数），`_lattice_pitch` / `expand_positions` / `api_server._resolved_extent` / `frontend estimateLatticeExtent` / `expandPositionsRef` 全部改调；③ **7 处必须与 FE-01 golden 同批改**（否则 `expected_python` 加完照样被副本坑）。**跨端合并后再评估"重复实现"本身是否降级为 P3** | backend + frontend（跨端，建议同批） |
| **BE-22** | 文档漂移（模块清单 / 契约） | `app/coverage_check.py:77-78`（"BOX/RHP/HEX 等宏体暂不支持"）、`:122-125`（`kind` 可取 `"lattice"`）；`app/meshtal/__init__.py:4`；`app/sweep.py:225-226`；`app/voxel_csg.py:8` | ① `coverage_check._resolve_cell_ast` docstring 写"BOX/RHP/HEX 等宏体**暂不支持**"，而 `voxel_csg.surface_fn` **已实现** RCC/TRC/REC/ELL/BOX/WED/RHP/HEX/ARB（`voxel_csg.py:163` 自述约定、`:272-394` 实现）——即 memory S1「模块 C」那批；② 同文件 `universe_coverage` docstring 说 `kind` 可取 `"lattice"`，但函数体 `kind = "leaf"`（:129）硬编码且四个 return 全透传，`"lattice"` 只由 handler（`api_server.py:3059`）构造；③ `meshtal/__init__.py:4` 写"pymcnp 优先 + 轻量兜底"，而 `meshtal_parser.py:3-5,364-367` 明确"pymcnp 校验路径实际从不生效"；④ `sweep.persist_sweep_summary` docstring 说"调用方随后 `cleanup_sweep_dir(base_dir)`"，实际 handler 内联 `shutil.rmtree`（`api_server.py:1711-1712`），该函数**零生产调用者**（仅测试）；⑤ `voxel_csg.py:8` 模块 docstring 仍写"只支持平面/球/柱/锥/GQ/SQ + RPP/SPH 简单宏体" | ①②**直接误导判据**：据①会以为宏体栅元"无法解析"（实际能，且 `detailViable`/`unsupportedCells` 语义会随之被误读）；据②会以为本模块会返回 `kind="lattice"` → 诱发重复实现。③④⑤是陈旧的"能力描述"，在 AI 深度参与维护的仓库里会被当成事实引用 | P2 | 逐条按实测改注释：① 改为已支持宏体清单（最好由 `surface_fn` 支持集生成）；② 删 `"lattice"` 条目并注明"kind 由 handler 判定，本模块恒 leaf"；③ 改为"轻量解析器（pymcnp 路径已废弃）"；④ 让 handler 改调 `cleanup_sweep_dir`（单一实现）或改 docstring；⑤ 更新宏体清单 | backend（③⑤可归 docs） |
| **BE-23** | 静默失败（降级已可观测，但异常不可分辨） | `app/coverage_check.py:74-106`（三处 `except Exception: return None`：`:81-83`、`:91-96`、`:100-104`）；可观测性对照 `:154-168`、`:179-180`；前端消费 `gui/src/components/LatticeEditDialog.tsx:123` | 三处 `except Exception: return None` 分别吞"`_ast_surf_nums` 失败"、"`surface_fn` 不支持该曲面类型"、"内层 `field()` 运行时失败"。**降级本身已可观测**（计入 `unsupportedCells`、写进 message、`evaluated==0` 时置 `detailViable=False`，前端已按 `detailViable/unsupportedCells` 短路 → **已核实不会误报红框**） | 残留问题：① 三类异常（类型不支持 / AST 畸形 / numpy 广播或维度 bug）被压成同一个 `unsupported`，**把实现 bug 伪装成"宏体不支持"**；② `covered=False` 在 API 层与"确实未覆盖"不可区分，任何只看 `covered` 的新消费者会误报 | P3 | 保留降级，但按异常类型分档（`unsupportedReasons`）或至少带上异常文本；响应加三态 `reason: "unresolvable"｜"uncovered"｜"covered"`，或在契约里钉死"`detailViable=false` 时不得消费 `covered`" | backend |
| **BE-24** | 死代码 / 只在测试中的能力 | `app/lattice.py:591-601`（`hex_ring_rows`/`hex_ring_cell_count`）、`:108-119`（`_dir_counts_from_range`）、`:1244`（`_parse_surface_cards  # noqa: 保持符号可见（未使用）`）；`app/spatial_index.py:81-92`（`query_new_vs_existing`）；`app/meshtal/colormap.py:40-58`（`weather_lut`/`map_value`） | 逐一全仓库搜索：这些符号的**唯一外部命中都在 tests/**（`tests/unit/test_lattice.py:409-417` 与 `:728-733`、`tests/unit/test_spatial_index.py:52`、`tests/unit/test_meshtal_colormap.py` 多处），`app/` 内无生产消费者。其中 `lattice.py:1244` 是**模块级裸属性引用语句**，真调用在 `:1239`，该行纯噪声（其 `# noqa` 自己写了"未使用"）；`colormap` 的 Python LUT 有 docstring 自述"TS 端断言相等（跨语言防漂移）"= **有意的 golden 锚点**，非垃圾 | 三类性质混在一起，需要分开处理：① 可立即删的噪声；② 跨语言 golden seam（保留但必须标注，否则后人以为能删）；③ "能力已建、没接线"（会让读者高估系统成熟度，也是 AI 误判"这功能已存在"的来源） | P3 | ① 删 `lattice.py:1244`；② 在 `meshtal/__init__.py:6` 与相关 docstring 标注"golden-only，不参与运行时"；③ 给 `_dir_counts_from_range`/`query_new_vs_existing`（以及 BE-18 的 `decide_resolution`）在 docstring 首行加"未接线（备用，无生产调用者）"，或按裁决接线／删除 | backend（+ docs） |
| **BE-25** | silent failure（fmesh 回放前提被破坏即静默重复卡行） **[行号已复核，与初版一致]** | `app/meshtal/fmesh_parser.py:143-147`、`:241-245`、`:186-195`、`:181-188`、`:160-167` | ① `joined_raw = "\n".join(cleaned)`（:144）后 `for fd in defs: if not _has_structured(fd) and not fd.raw: fd.raw = joined_raw`（:145-147）——把**整段卡体行**赋给每个缺 raw 的定义；若同一卡体含 ≥2 个"仅未知 key"的 FMESH 卡，`fmesh_defs_to_lines` 的非结构化分支（:194-197）会**逐条回放同一批行 N 次**；② 兜底分支 `:160-168` 里 `number = int(first.group(2)) if first.group(2) else 0`，而 `_FAMILY_RE`（:14-16）的 `group(2)` 是卡族名（`FMESH\|TMESH\|RMESH\|CMESH`）、数字是 `group(3)` → **若该分支可达必抛 `ValueError`** | ①重复输出卡行会让 MCNP 报错或后者覆盖前者（静默的语义损坏）；②死分支里的真 bug 一旦主循环入 `defs` 的路径被改动，会以"解析器崩溃"而非"raw 兜底"暴露。**两条均需构造输入跑一次才能定性**（见 §三 存疑） | P3 | ① 按卡号边界切分 raw（复用 `_extract_subcard_raw` 思路）而非整段赋值，并补"两卡均含未知 key"的回放用例；② 改 `first.group(3)` 并补一条直测该兜底分支的用例，或直接删除死分支 | backend（+ tester 各补一条用例） |
| **BE-26** | 文档漂移（**已失效的等价性声明**；由 T3 cross-check 提出，我侧核实并**更正其方向**） | `gui/backend/api_server.py:1352-1353`（docstring）、`:1395`（公开别名）、`:2147`（`/api/text-to-section` 复用点）vs `:1352-1391`（实现）与 `:2039-2092`（`/api/parse-inp` 内联实现） | `_deck_to_frontend_dict` 的 docstring `:1353` 自称「**与 `/api/parse-inp` 的序列化一致**」，**该声明已不成立**（两实现已在 9 个前端顶层键上分叉，见 BE-12）。**方向更正（T3 原表述为"`/api/parse-inp` 返回较窄那份"，实际相反）**：`/api/parse-inp` 的 `deck_dict` 从 `asdict(deck)` 起手、**不做任何键删除**（:2044），因此**同样包含** `sourceMode`/`sdefFields`/`kcodeFields`/`ksrcPoints`/`sdefRawText`/`distributions`/`sswFields`/`ssrFields`（:2061-2078）**外加 `_warnings`（:2091）**；而 `_deck_to_frontend_dict` 既**不注入**任何前端中间态键、**也不带 `_warnings`**。⇒ **宽的是 `/api/parse-inp`，窄的是 `_deck_to_frontend_dict`（MCP `/workspace` 走的那份）**。暴露面（与 T3 结论一致，勿夸大）：① `/api/text-to-section` 只用其中 `materials`/`cells`/`tallies` 三个子集（:2148-2153）→ **应用内影响≈0**；② 真正受影响的是**应用外消费者**（公开别名供 MCP 复用）——`deck_to_frontend_dict` **缺 `_warnings`**，而 `_warnings` 是前端解析提示的展示源 | ① docstring 自称一致 → 后续维护者会把两份实现当**同一契约**改，BE-12 的分叉会继续扩大；② `_warnings` 在两条 deck 出口上语义不一致（parse-inp 有、MCP 无）；③ 公开别名 + 内联实现并存 = 把"契约"暴露给外部却无单一实现 | P2 | ① **修正 docstring** `:1353`：删去"与 `/api/parse-inp` 一致"，改为"**返回较窄口径**（不含前端中间态键与 `_warnings`）；宽口径见 `/api/parse-inp`"；② 与 BE-12 一并做**单一实现 + 显式参数**（如 `_deck_to_frontend_dict(deck, include_frontend_aliases=False, include_warnings=False)`），三处消费者各自开关；③ 若暂不合并，至少在契约里写明两条出口的字段差集 | backend（+ docs 若走契约） |

> 表内 26 条中，**BE-09（`_SI_LETTERS`）、BE-04（幽灵 `--mcp-server`）、BE-10（`sdef_raw_text` 死字段）、BE-11（过期 docstring）** 是 PM 点名要求独立成行的四条，均已独立给证据。**BE-26 为 v5 新增**（由 T3 前端扫描 cross-check 提出、我侧核实并更正方向）。个别条目合并了同源证据（如 BE-01 含 `.bat` 路径、BE-22 含 5 处文档漂移），以保持"一条债 = 一个可派单处置"。

### 表 BE-21 附表：hex pitch 换算的 7 处副本（逐处行号 + 方向 + 判据；均为静态核实读到的代码）

| # | 位置 | 方向 | 判据 / 公式 | 备注 |
| --- | --- | --- | --- | --- |
| 1 | `app/lattice.py:915-929`（`_lattice_pitch`） | 格距 → 间距 | `str(lat)=="2"` 时 `p = px if px>0 else (py if py>0 else 1.0); px = py = p` | 用传入 `lat` 参数判定 |
| 2 | `app/lattice.py:1037-1041`（`expand_positions`） | 格距 → 间距 | `hp = px if px>0 else (py if py>0 else 1.0); px = hp; py = hp` | **判据不同源**（局部 `lat = str(fg.lat or "1")`） |
| 3 | `gui/backend/api_server.py:734-743`（`_resolved_extent`） | pitch → 跨度（**反向**） | `lat=="2"`：`hx = p*2/√3/2`、`y = ±p/2`；else `±p/2`（注释自述「hex：pitch=中心距；x 跨度=2R=2p/√3，y 跨度=p」） | **T3 补报，我此前漏计**；本轮已核实为真实换算（`:736-740` 字面可读） |
| 4 | `gui/src/utils/lattice.ts:452-468`（`estimateLatticeExtent`） | **单位 pitch 正向估算**（**v8 按 T3 更正**：既非反向、也不消费外部 pitch） | `const pitch = 1`（:453）→ `hexGrid(dims, 1)`，再按半宽/半高取外沿（`x: span + pitch/√3`、`y: span + pitch/2`）；docstring `lattice.ts:440` 自述「阶段2 用单位 pitch≈1；阶段3 由 surface_expr 提供真实格距」 | **有意为之、不是缺陷**；仍列出是因为"半宽 = pitch/√3 / 半高 = pitch/2"这条**几何常数**与第 3 处同源（改常数须两处同批）。T3 的 FE-06 处置是**删该函数**（已被 `/api/lattice-extent` 取代、src 零引用） |
| 5 | `gui/src/three/latticeInstances.ts:384-389`（`expandPositionsRef`） | 格距 → 间距 | `const hp = px>0 ? px : py>0 ? py : 1; px = hp; py = hp`（注释自述「镜像 Python `_lattice_pitch` 修复」） | 第 2 处的 TS 镜像 |
| 6 | `gui/test/latticeInstances.test.ts:416-453` | — | 消费上述 `expandPositionsRef` 与 golden | 测试消费点（改公式须同批） |
| 7 | `app/lattice.py:1249 → :1266 → :1044` | 旋转/定位链路 | `"trcl": float(trcl or 0)` → `expand_positions(..., trcl_rotation_deg=...)` → `math.radians(...)` | **非 pitch 换算**，但属同一 `expand_positions` 契约链，改签名时需一并核对（列出以免误计为第 8 份） |
| — | `gui/backend/api_server.py:554-564` / `:884-895` | — | —— | **T3 原列为"lat 分派"的两处，双方复核后一致确认不成立**：`:559-563` 是 `_clip_suffix_and_lines` 里拼 `{num} rpp …` **文本行**；`:890-894` 是 `_lattice_container_bound` 的**曲面号扫描循环**（`lattice._INT_RE.match(tok)` / `surfaces.get(abs(n))`）。**既非 lat 分派、更非换算**，不计入（T3 已认误报，并**更正了其误报描述**） |

> **方向口径小结（v8，按 T3 更正）**：**正向（格距 → 间距）3 处** = 序号 1、2、5；**反向（pitch → 跨度）1 处** = 序号 3；**单位 pitch 正向估算 1 处** = 序号 4（**有意为之、非缺陷**，T3 的 FE-06 将删该函数）；**测试消费 1 处** = 序号 6；**同链非换算 1 处** = 序号 7。**⇒ 换算实现共 5 处。**

> **计数口径说明（避免与 T3 的 FE-21 对不上）**：含 hex pitch 换算的**代码实现 5 处**（序号 1–5），另加**测试消费点 1 处**（序号 6）与**同一 `expand_positions` 契约链的 TRCL/定位入口 1 处**（序号 7）⇒ 合计**7 处**。T3 原点名的 `api_server.py:563-566`/`:891-894` 经双方逐处复核**不成立**，故**不写成"8 处换算"**。t4 如需统一表述，建议用「**hex pitch 换算 5 处实现 + 1 处 TS 测试消费点 + 1 处同链 TRCL 入口；另有 2 处被误报**」。

---

## 二 已核实已清偿（勿再报）

1. **`spec._keep_py` 的 `material_library.py` / `gpu_pref.py` 漏项** —— 已补（`gui/mcnp_sidecar.spec:28-29`）；`/api/material-library*`（`api_server.py:1506-1583`）与 `/api/set-gpu-preference`（`:1492`）在冻结包内可解析。**这两条历史债已清**（但机制问题转 **BE-05**）。
2. **`inp_generator.py` 模块顶层 `from pymcnp import inp`（fail-fast 约定）** —— 确认在模块顶层（`inp_generator.py:8`），`tests/integration/test_tech_debt.py:89-104` 的 F#7 断言成立，`docs/backend-changes.md:87`（commit `bf0a2c7`）一致；`api_server.py:43-46` 的注释与之一致。**这是刻意约定、不是债**；请勿再把它当作"后端启动慢的根因"（启动优化已由 `_surf_classes()` 惰性 + handler 内按需 import 解决，见 `PROJECT_MEMORY.md:59`）。
3. **`raw_overrides` 8 处守卫复制粘贴** —— 已收敛为单一实现 `_apply_raw_override`（`inp_generator.py:1260-1271`），8 个调用点（`:1302/1308/1331/1352/1354/1357/1360/1375`）与 `tests/unit/test_generator_overrides.py`（`RAW_KEYS` 8 项 × 4 组 + 1145 门控 3 例）一致。前端**有意只发 4 key**（`gui/src/utils/rawOverrides.ts:8`），后端另 4 个（surfaces/phys/e0/cut）是**有意的类型遗留**（测试文件 `:4-5` 已注明），不建议按"死代码"清理，除非 PM 要收窄契约。
4. **`preview_cache` 的 LRU / `evict_dir` / `meta.json` 跨进程恢复** —— 实现与 `docs/contracts/preview3d-performance.md`、`PROJECT_MEMORY.md:60` 一致；`evict_dir` 与 `_clear_stl_session` 的联动（`api_server.py:113-127`）已在 docstring 说明清楚。
5. **`api_server.main()` 的后台 pymcnp 预热线程 + `_SURF_CLASSES_LOCK` 双检锁** —— `:139-157` + `:3607-3615` 实现正确（"并发首拉只构建一次"语义成立）。**不要把它误报成 BE-07 的并发债**（BE-07 的窗口在 `_STL_SESSION` / `PreviewCache`，与此锁无关）。
6. **`sweep.py` 的预算 / 清理硬化** —— `SWEEP_MAX_COMBOS=50` / `SWEEP_PER_RUN_TIMEOUT=300` / `SWEEP_TOTAL_BUDGET=1800`（`:33-35`）+ `persist_sweep_summary`（`:222-238`）+ `cleanup_sweep_dir`（`:241-244`，handler 在 `try/finally` 内调用）：`docs/backend-changes.md:1015-1017` 的 T3/T8 已闭合，临时目录不再泄漏。`run_mcnp` 调用是 list 形式、**无 `shell=True`**、用户输入只落 `sweep.i` 文件 → **无命令注入面（已查）**。
7. **`overlap_probe.sample_overlap` 的 `probe_error` 上抛** —— `:73-79` 注释与 `raise RuntimeError(f"probe_error: {e}")` 一致，`docs/backend-changes.md:1016` 的 T7 已闭合 = **显式设计，非静默**。
8. **`meshtal` / `ptrac` worker 的"模块顶层只 stdlib"约定** —— `_meshtal_worker.py:12-16`（base64/json/os/sys/traceback）、`_ptrac_worker.py:10-13`、`ptrac_parser.py:21` 全部达标（numpy 在 `_meshtal_worker.py:127` 惰性 import），且有 AST 断言守卫（`tests/unit/test_meshtal_worker.py:31-38`、`tests/unit/test_ptrac_parser.py:36-47`）。**约定有自动防线，勿再报**。
9. **`voxel_csg._tangent_plane_mesh` 的降级** —— `except Exception as e: logger.warning("切线平面法快路径失败，回退 marching cubes: %s", e)` + `return None` = 显式记录 + 显式降级（`docs/backend-changes.md:1023` 的 T6 标准已达成）。
10. **跨语言 golden 一致性（抽查 3 处，均一致）** —— `hex_center`↔`hexCenter` 公式逐字一致（唯一差异是 TS 的 docstring，见 BE-14）；`expand_positions` 的 rect/hex 居中偏移与行主序 `idx = i + nx*(j + ny*k)` 与 `gui/src/utils/lattice.ts:90-105 / 151-166` 一致；`detect_fill_cycle`↔`detectFillCycle`（`lattice.ts:395-438`）的边集构造 / `chain` 形态 / `fill="0"` 语义全部一致。golden 单一权威 = `gui/src/utils/__golden__/latticeGolden.json`，双端断言。
11. **app/ 业务模块内基本不存在"逐请求被 mutate 的模块级全局"** —— `lattice.compose_lattice_tree` 的 `state`（`:1227-1241`）每次调用新建；`mc._CASE_TABLE` 等（`mc.py:134`）导入期一次构建后只读；`voxel_csg` 的 `mid_cache` / `keep|cut` 均为闭包局部。**唯一真正的跨请求可变全局在 `api_server`（见 BE-07）**。

### 附：3 条相邻发现（供 reviewer 去重时判断归属）

- **五处同构的"曲面号集合 → {num: surface_fn(...)}"**：`app/overlap_probe.py:20-27` / `app/coverage_check.py:86-96` / `app/voxel_csg.py:1091-1094` / `app/analytic_slice.py:137` / `gui/backend/api_server.py:3159`。差异只在"缺失曲面"处理：`overlap_probe` **静默 `continue`**（丢失半空间 → 交集判定错误且难发现），`coverage_check:88-90` 直接 `return None`（放弃整栅元）。后者使 `overlap_probe.py:62-63` 在"`nums` 非空但全部缺失"时返回 None，**绕过** `:76-79` 刻意设计的 `probe_error` 上抛路径。建议在 `voxel_csg` 加 `build_field_fns(nums, surfaces_by_num, tr_cards) -> (fns, missing)` 统一五处。**P2 / Owner: backend**（可并入 BE-15 的"解析器重复"主题）。
- **BE-25 的 ②（fmesh 死分支 `group(2)`）已并入 BE-25 行**；此外 `app/meshtal/fmesh_parser.py:241-245` 的 emit 恒追加 `fd.raw`，与 parse 侧"结构化齐全则不清 raw"的前提互相依赖——当前前提成立（`:240` 注释已说明），一旦前提被破坏即静默重复输出卡行。**P3 / Owner: backend**。
- **TRCL 绕 Z 归一化口径两端不一致（后端无 mod、前端有 mod）** —— 待 t4 定级归属。后端唯一入口 `gui/backend/api_server.py:622-644`（`_cell_trcl_deg`）由 **TR 卡旋转矩阵首行** `(rot[0][0], rot[0][1])` 反解 `degrees(atan2(b, a))`（**:642**），**不做任何 mod 归一化**（返回值域 (−180°, 180°]）；全仓库 grep 确认 Python 侧**不存在** `% 60 / % 90 / % 360` 的旋转归一化。前端 `gui/src/three/latticeInstances.ts:248-259`（`parseTrclDeg`）走**完全不同的口径**：把 TRCL 串当"三个角 token"取 `toks.length >= 3 ? toks[2] : 末位`，再 `((z % step) + step) % step`（`step` = lat"2"→60 / lat"1"→90 / 无 lat→360）。后果：① **"TRCL 三数=三个欧拉角"这个参数化后端并不存在**（`core.py` 把它当 raw 串透传、`inp_generator.py:116-117` 也原样回发），前端 fallback 一旦被启用就可能取错 token（如 `TRCL=0 0 0 5` 会取到 `0` 而非 `5`）；② 归一化结果不同（后端负角、前端恒非负）。触发条件仅一条：`gui/src/components/Preview3DLattice.tsx:272` 的 `primary ? (primary.trclRotationDeg ?? 0) : parseTrclDeg(...)`——而后端**总会**下发 `trclRotationDeg`（`app/lattice.py:1282` 无条件写入、`api_server.py:3322-3339` 返回），故 `primary` 为空时才走 fallback。**P3（潜在，两侧当前输出一致性未实机验证）**

---

## 三 存疑（未实机验证，需后续确认）

1. **本会话无 shell** → BE-01~25 中所有"某测试现在是绿/RED"的判断均来自**代码 + docstring 静态互证**，未执行 pytest。建议由能跑 pytest 的成员执行：`pytest tests/integration/test_tech_debt.py tests/integration/test_roundtrip.py tests/integration/test_sample_smoke.py -q`（**跑前先确认 5001 未被旧 sidecar 占用**，见 `PROJECT_MEMORY.md:447`），一次性坐实 BE-11。
2. **BE-05 "打包版必 500"** —— 由 `sys.path` 结构 + spec 清单推导（dev 模式 `APP_DIR` 直入 `sys.path`，故永不复现），**未实机跑一次 PyInstaller 打包版**验证 `/api/diff-inp` 与 `/api/cross-section` 的解析切片分支。
3. **BE-02 的真实影响面** —— `_parse_ds` 只写 `distributionIds` 是**确定的**（`:104-105`），四个 `_resolve_ds` 分支的读键也确定；但"用户实际有多少 INP 用 DS Q/S/T/L/H"未统计，故影响面按"抽样语义错误"定 P0，而非"必崩"。
4. **BE-06 的端到端链路** —— `patch_section` 丢 `universe_comments` 的机制已逐行核实；但"前端轮询是否真会把清空后的 deck 应用回界面"依赖 `gui/src/App.tsx:92` 的 `{...deck, ...aiDeck}` 合并策略，**未跑端到端**。
5. **BE-07 的竞态** —— 需并发压测（两个 preview-3d 同时请求）才能确证现象；从代码判断窗口客观存在（`global` 整体重绑定 + 先删后建），但未实测复现。
6. **BE-15 的打包路径** —— `mcnp_sidecar.spec:40-43` 把 `_cross_section_helper.py` 塞进 `_internal/app/`，helper 自身按 `os.path.dirname(__file__)` 找 worker（`:10-11`）；冻结下该路径是否与 worker 落点一致**未验证**。
7. **BE-22① 的 `detailViable` 语义** —— 宏体已支持后 `unsupportedCells` 是否真会归零，取决于 `surface_fn` 的宏体分支是否覆盖测试卡里的全部宏体类型；未跑 `coverage_check` 实际用例。
8. **BE-25 的两条** —— ①"整段 raw 赋值 + 多卡回放"需构造"同一卡体含 ≥2 个仅带未知 key 的 FMESH 卡"的输入并跑 `parse_fmesh_lines → fmesh_defs_to_lines`；②死分支 `group(2)` 的可达性基于正则分组与控制流推断，未做运行时证明。**建议 tester 各补一条用例**。
9. **BE-19 / BE-21 的耗时占比** —— 需 BEAVRS 量级输入计时，未测（判定依据是 `_cell_pz_bounds` docstring 自述该参数即为消除此成本而加、以及 `_expand_universe` 已存在等价惰性回填）。
10. **TRCL 绕 Z 口径两端一致性（T3 的 Q5）** —— 后端口径（`api_server.py:622-644`，由旋转矩阵 `atan2` 反解、**不 mod**）与前端 fallback 口径（`latticeInstances.ts:248-259`，token 三数取 `toks[2]`、**mod 60/90/360**）**机制不同**（已逐字核实）；但"在 `primary.trclRotationDeg` 缺失的真实输入下两侧结果是否恰好一致、以及 fallback 在实测中是否真被走到"**未跑未验证**。已记入「相邻发现」（P3，归属待 t4 定级）。

---

<!-- 审计结论（§〇 方法 / §一 债表 / §二 已清偿 / §三 存疑）到此结束；§四 为 t4 复审增补附录，落款见文件末。 -->

---

## 四 t4 复审增补：三条 P0 的定级依据 + 结论性质标注

> 本节针对 t4「交叉验证 + 去重 + 定级」的复审请求补足证据。**t2 定稿条数为 25 条（BE-01…BE-25），非任务 output 摘要里的 22 条**（output 被平台截断到 2000 字符，中段 D-BE-13…D-BE-18 丢失；本文件是权威来源）。

### 4.1 结论性质标注（静态核实 vs 无 shell 推断）

本会话**无 shell 工具**，故所有条目分两类：

**A. 静态核实（仅凭读码/全仓库 grep 即可定论，可靠性高）**
- **BE-01**：`generate_step.py` 函数体只写死一行占位实体（读到的字面量）；handler 回 `ok`（读到的字面量）；**端点在 handlers 表注册**（`api_server.py:1446`）；**调用方侧**：全仓库 grep `generate-step|generateStep` 命中仅 4 处——`docs/contracts/api.yaml:657`、`docs/backend-changes.md:1026`（历史记录）、`api_server.py:1446`（注册）、本审计文件；**`gui/src/**` 与 `gui/test/**` 零命中** → **确认无前端调用方**。
- **BE-02**：`_parse_ds` 写入键集合（字面 dict 构造，:97）、`_resolve_ds`/`resolve_ds_t` 读取键（字面 `ds.get(...)`）、`_DS_LETTERS`（字面 tuple）三者**均为逐字读到的常量**；两条真实数据路径**逐跳可读**（见 4.3）。
- **BE-04**：docstring 字面量与分派结构、fallthrough 目标 `api_server.main()`、五处文档冲突文本——全部读到的字面量。
- **BE-09 / BE-10 / BE-11 / BE-13**：白名单字面量、写入点 grep 唯一性、docstring 字面量、调用点 grep 零命中——均为静态可定论。
- **BE-05**：`_keep_py` 字面清单 + `handlers` 表内容 + `_import_app(...)` 调用点——三份**全部逐字可读**，差集可机械算出（见 4.4）。

**B. 无 shell 推断（结论方向确定，但量级/可达性未实机验证）**
- **BE-05 的"打包版必 500"**：由 `sys.path` 结构 + spec 差集**推断**（未实跑 PyInstaller 打包版）。
- **BE-07（并发竞态）**：窗口由"`ThreadingHTTPServer` + 无锁模块级 dict 整体重绑定 + 先删后建"**推断**存在；**未压测复现**（无法断言"必然出故障"，只能断言"窗口客观存在"）。
- **BE-02 的影响面**：机制确定，但"用户 INP 中 DS Q/S/T/L/H 的实际使用频次"**未统计**（故定 P0 依据是"语义错误 + 违背不降级决议"，而非"必崩"）。
- **BE-16 / BE-17 / BE-20 / BE-25 / 相邻发现 TRCL**：机制与行号确定，行为/量级未跑。
- **BE-19 / BE-21 的耗时占比**：需 BEAVRS 量级计时，**未测**。

### 4.2 【🔴 v8 已撤回】原称"`pos_index` 参数不可达"—— 经 t4 实读**驳回**，本条不成立

~~`source_sampler.py:96-116` 的 `_erg(..., pos_index)` 无调用方传入实参 ⇒ FPOS 链不可达。~~ **错误结论，勿据以派单**：
- `app/generator/source_sampler.py:67-68` 逐字为 `pos, pos_index = self._position(rng)` → `erg = self._erg(rng, pos_index)` ⇒ **实参已接**；
- `_position()` 的 **POS=Dn 多点源**分支 `:202-204` → `_sample_pos_dist()`（`:216-228`）末尾 `return tuple(si_vals[idx*3:idx*3+3]), idx` ⇒ **返回的就是真实位置索引**，正是 `ERG=FPOS Dn` 所需；其余模式返回 `None` → `_erg:107` 取 `0.0`（与"仅一个位置、索引 0"语义一致）；
- 我当初的 grep 依据 `_cell_refs_pos` **与该链路毫无关系**（不是它的机制）。

⇒ **BE-02 的处置里不应包含"接 `pos_index` 实参"这一步**（否则给发布阻断清单加了一条不存在的返工项）。详见 §五 5.4。

### 4.3 BE-02 的两条真实数据路径（t4 问项②）

**路径 A｜导入 INP（生产主路径）**
`app/generator/parsers/__init__.py:parse_inp_text` → `core.py:parse_data_cards` → SI/SP/SB/DS/SC 行收集 → **`core.py:1154-1155`：`result["sdef_distributions"] = json.dumps(parse_distribution_lines(sisp_lines))`** → `__init__.py:270` 写入 `adv.sdef_distributions` → （前端/接口）→ `inp_generator.py:473-474` 或 `api_server._handle_source_demo_sample:3118` → `DistributionSampler(entries)` → `_resolve_ds` 读 `values` → **恒 `{"default":True}`**。
（面源另有 `core.py:1231-1237` 的 `surface` 分支，同样走 `parse_distribution_lines`，**同一 bug**。）

**路径 B｜UI 演示源（`/api/source-demo-sample`）**
`gui/src/components/SourceTab.tsx:119`（点「🎬 演示源」）→ `gui/src/utils/api.ts:152-161`（`sourceDemoSample`）→ `POST /api/source-demo-sample`（注册 `api_server.py:1469`）→ `_handle_source_demo_sample`（`:3118`）→ `_prepare_source_geometry`（`:3141-3155`，构造 `voxel_csg` field 闭包）→ `source_sampler.sample_source` → 上述 `_erg`/`_resolve_ds`。
（`SourceDemoWindow.tsx:90` 亦调用同一 `sourceDemoSample`；契约闸门 `tests/integration/test_api_contract.py:634,650` 有两个 HTTP 用例，但它们**只断言响应形状，不断言 DS 语义**——故现有测试全绿而 bug 存活。）

### 4.4 BE-05 的 `_keep_py` 全量清单与差集 + 打包历史（t4 问项③）

**`gui/mcnp_sidecar.spec:17-31` 现有 `_keep_py`（24 项，逐字）**：
`models.py`、`preview_cache.py`、`freecad_preview.py`、`_freecad_csg_worker.py`、`quadric.py`、`voxel_csg.py`、`mc.py`、`analytic_slice.py`、`mctal_parser.py`、`sweep.py`、`overlap_classify.py`、`spatial_index.py`、`overlap_probe.py`、`freecad_locator.py`、`step_importer_geouned.py`、`geouned_worker.py`、`xsdir_db.py`、`step_importer.py`、`outp_parser.py`、`coverage_check.py`、`_cross_section_helper.py`、`_freecad_cross_section_worker.py`、`stl_cross_section.py`、`gpu_pref.py`、`material_library.py`
**`_keep_dirs`（:31）**：`["generator", "docs", "meshtal", "ptrac"]`

**差集判定（正确算口径）**：`app/` 下模块的**覆盖来源有三条**——① `_keep_py`（spec:17-30，25 个顶层 .py 显式列出）、② `_keep_dirs`（spec:31，`generator`/`docs`/`meshtal`/`ptrac` 整目录 `_walk_add`）、③ **PyInstaller 静态 import 图**（从入口 `mcnp_bridge.py → api_server.py` 走得到的模块会被自动收进 PYZ）。所以"`_keep_py` 里没有"**不等于**"打包版用不到"——必须叠加第 ③ 条才能定论。据此，全仓库逐项核实 `api_server.py` 里 **28 处** `_import_app("名字")` 动态 import（行号：:597/:1002/:1492/:1506/:1517/:1530/:1548/:1583/:1605/:1635/:1728/:1756/:1793/:1797/:1798/:1847/:1848/:1911/:1912/:2605/:2719/:2808/:2965/:2984/:3013/:3014/:3217/:3493），结果如下：

| 动态 import 的模块名 | `_keep_py` 是否已列 | 是否另有静态 import 边兜住 | 打包版可用性 |
| :--- | :--- | :--- | :--- |
| `stl_cross_section`（:597,:2808） | ✅ 已列（:28） | — | 可用 |
| `step_importer`（:1002,:1797,:1847,:1911,:2719） | ✅ 已列（:23） | — | 可用 |
| `gpu_pref`（:1492） | ✅ 已列（:28） | — | 可用 |
| `material_library`（:1506…:1583） | ✅ 已列（:29） | — | 可用 |
| `sweep`（:1605,:1635,:1728） | ✅ 已列（:20） | — | 可用 |
| `lattice`（:1793,:2965,:2984,:3013,:3217） | ❌ 未列 | **有**：`app/generator/inp_generator.py:9 \|from app import lattice\|`、`parsers/core.py:18` 同 | 可用（靠静态边进图） |
| `freecad_preview`（:1798,:1848,:1912） | ✅ 已列（:18） | 另有 `api_server.py:237/:319/:1017/…` 静态 import | 可用 |
| **`diff_inp`（:1756）** | **❌ 未列** | **无**（全仓库仅 `_import_app("diff_inp")` 一处、无静态 import 边） | **必 `ImportError` → `/api/diff-inp` 500** |
| `coverage_check`（:3014） | ✅ 已列（:25） | — | 可用 |
| `mctal_parser`（:3493） | ✅ 已列（:20） | — | 可用 |
| `generate_step`（:2605，`base_dir=os.path.dirname(__file__)`＝**gui/backend**，由 spec:40-43 单独 `_datas`） | n/a（不在 app/） | — | 可用（spec:40-43 单独登记） |

**⇒ BE-05 的实存漏项只有 `diff_inp.py` 一个**。**修正说明**：我在 BE-05 行内还列了 `analytic_slice.py` 与 `stl_cross_section.py` —— 经本轮逐字复核，**二者均已在 `_keep_py` 内**（`analytic_slice.py` 为第 8 项、`stl_cross_section.py` 为第 23 项），**该两处属我的行内误述，请 t4 以本节为准**（本表已把"未列"集合从 18 个机械收敛到 1 个）。但 **BE-05 的根因与定级不变**：白名单**手写** + **零自动闸门** + **历史上已复发两次**（`PROJECT_MEMORY.md:97` 记「spec `_keep_py` 加 `material_library.py`」）——`diff_inp.py` 只是**当前**那一例，下一个动态 import 的模块照样会漏；且 `lattice.py` 能进包**完全靠** `from app import lattice` 这条静态边，一旦有人把它改成纯动态名立刻复发。**仍建议 P0**（判准：这是一类会反复发生的、只在发布版暴露的 500 缺陷，且已有零成本的自动闸门解法）。

**是否已进过任何一次打包（t4 问项③后半）**：`_keep_py` 的 `_datas` 会把清单内文件拷进 `_internal/app/`；`diff_inp.py` 不在清单 → **从未进过任何一次打包**（推断，依据是 spec 逻辑 + `docs/手动打包方法.md:499-515` 的手动打包流程；**未实机核验 `_internal/app/` 目录内容**）。对照：`material_library.py`/`gpu_pref.py` 是**后来补进**清单的（`PROJECT_MEMORY.md:97` 记「spec `_keep_py` 加 `material_library.py`」），说明该清单历史上确实漏过 → 但**它们被补上后是否已随某次打包发布过，本项目无记录，无法从代码侧判定**。

### 4.5 对 t4 定级的建议（供去重/定级参考）

- **BE-01 建议维持 P0 但可作 P1**：机制是"假功能"，但**已核实无任何前端调用方**（`gui/src/**`、`gui/test/**` 零命中），用户**触达率≈0**；危害在"契约承诺了不存在的能力"（api.yaml 有 operationId + 响应 schema），以及未来调用方会拿到非法文件。**若 t4 以"用户是否被误导"为 P0 判准 → 宜降 P1；若以"契约与实际不符 + 假功能"为判准 → 维持 P0。请 t4 裁决并说明所采判准。**
- **BE-02 建议维持 P0**：两条真实数据路径都活（UI 按钮 + 导入 INP），且违背项目已明文决议的"不降级"，属**静默错误结果**。唯一削弱项是"DS Q/S/T/L/H 的实际使用频次未统计"。
- **BE-05 建议维持 P0，但把"实存漏项"收窄为 `diff_inp.py` 一条**（见 4.4 修正），定级依据改为「**白名单手写 + 零自动闸门 + 历史上已复发**」，而非"当前漏了 3 个"。

### 4.6 本轮相对任务 output 摘要的变更（供 t4 建总表时对齐）

| 项 | 任务 output 摘要里的说法 | 本文件（权威） |
| :--- | :--- | :--- |
| 条数 | 22 条（`D-BE-01…D-BE-24` 被截断成 22） | **26 条 BE-01…BE-26**（v5 新增 BE-26） |
| 编号 | `D-BE-NN` | **`BE-NN`**（PM 要求统一） |
| 分级 | P0=3 / P1=8 / P2=11 / P3=3 混在截断文本里 | **P0=3（BE-01/02/05）/ P1=8 / P2=12 / P3=3** |
| 存疑 | 9 条 | **10 条**（新增 TRCL 口径一致性） |
| 相邻发现 | 2 条 | **3 条**（新增 TRCL 绕 Z 两端口径不一致） |
| BE-01 | 未提"有无调用方" | **已补：无任何前端调用方**（全仓库 grep 仅 4 处，`gui/src/**`、`gui/test/**` 零命中） |
| BE-02 | 未分路径 | **已补两条真实路径 + 5 分支逐条行号 + `pos_index` 不可达** |
| BE-05 | 列了 3 个漏项（analytic_slice / diff_inp / stl_cross_section） | **实存漏项收窄为 1 个（`diff_inp.py`）**；analytic_slice 与 stl_cross_section **实际都在 `_keep_py` 内**（行内误述已更正） |
| BE-06 | 未区分前端/后端暴露面 | **🔴 已撤回（v7）**：T3 反证 + 我复核确认 → 该条的**前置事实不成立**（见 §五），不计入总数 |
| BE-12 | 未提 docstring 声明失效 | **已拆出 BE-26**（`_deck_to_frontend_dict` docstring 自称与 parse-inp 一致 → 已不成立；方向已更正） |

### 4.7 BE-06 / BE-12 的暴露面切分（应 T3 复核对齐，避免重复定级）

> **v7 更新**：本节的 **BE-06 部分已被 §五 推翻并撤回**（前置事实不成立），仅保留作过程留档；**BE-12 部分仍然有效**。

- **BE-06（`universe_comments` 丢失）**：~~前端侧经 `App.tsx:92` 浅合并被吸收、后端 MCP 侧仍实存~~ → **🔴 已撤回**：`_sections_to_deck:101` → `deck_from_json` 实际**会**读 `universe_comments`（`api_server.py:1347-1348`），故 MCP 侧**不丢**。详见 §五。
- **BE-12（两份分叉序列化）**：T3 核实前端**已删除**这些顶层中间态副本（`gui/src/utils/sourceAdv.ts:8-9`），权威是 `deck.adv`；且 `migrateLegacySourceKeys`（`sourceAdv.ts:147-174`）**只在 `adv` 缺值时取中间态**，不会覆盖 AI 写入的 `adv`。⇒ **前端侧不成立**。**后端侧仍成立**（两份实现 + 公开别名 + `_warnings` 语义不一致），其**契约层后果已单列为 BE-26**；BE-12 自身仍保留（P1）作为"应合并为单一实现"的**重构项**。

---

## 五 撤回与自查记录（v7，2026-09-10）

> **PM 已下达 t2 冻结令**：本清单不再新增债条、不再扩条数、不再开新核对轮次。**本节不是新增条目，而是对一条假阳性的撤回与留档**（账目只减不增：26 → 25），以 t4 合并总表时不被误导为准。

### 5.1 撤回 BE-06（P1 → 撤回）

- **原断言**：「`inputcard_mcp/server.py:87-101` 的 `_sections_to_deck` 只送 8 段进 `deck_from_json`，**不读** `universe_comments` ⇒ AI 不经前端自行 `generate` 时丢 U 分组头注释」。
- **反证（T3 engineer-frontend 提出，我逐行复核确认成立）**：
  1. `server.py:101` 的 `return deck_from_json(d)` 传入的是 **`d = dict(sections)` 整个 dict**（`:92`），后面的 `:93-100` 只做两件事——`advanced → adv` 改名、None 段归一化（`basic/surfaces/tr_cards/tally/adv` + `cells/materials/sources`），**不删任何键**；因此 `universe_comments` 仍在 `d` 里；
  2. `gui/backend/api_server.py:1347-1348` 的 `deck_from_json` **末位参数就是** `universe_comments=(data.get("universe_comments") or data.get("universeComments") or {})` ⇒ **它读**（且两个键名都兼容）；
  3. `server.py:83` 的 `_deck_to_sections` 亦**显式回写** `sec["universe_comments"] = d.get("universe_comments", {})`；
  4. `patch_section`（不带 inp）链路 `:219-222` 走 `_ws_deck()`（`:141-142` = `_sections_to_deck(_ws_sections())`）→ `_apply_section_patch` → `_set_ws_sections(_deck_to_sections(deck))`，**全程经 `deck_from_json`** ⇒ 注释在改写后仍被回写。
- **⇒ 结论**：`generate_document` / `patch_section`（不带 inp）/ `add_shape` 三条 MCP 路径下 `universe_comments` **均不丢失**；前端 `App.tsx:92` 的浅合并只是**第二道保险**，不是唯一防线。**条目不成立，撤回。**
- **我的错误成因（自查）**：我读 `_sections_to_deck` 时**只逐行了 `:92-100` 的键归一化列表，没跟进 `:101` 的 `return` 落到 `deck_from_json` 的哪个参数**，就直接断言"不读"。**教训**：涉及"是否透传某字段"的判断，必须跟到函数的**返回值/参数绑定**处，不能止于中间的键白名单。

### 5.2 顺带更正 T3 提到的另两处（均已被其采纳）

- `_cell_trcl_deg` 归属：正确位置是 **`gui/backend/api_server.py:622-644`**（`atan2` 在 `:642`、调用点 `:3280`），**不在** `app/lattice.py`（那里只消费已算好的 `trcl_deg` 并原样回发）。T3 已在 FE-22/§8.6 更正。
- **FE-22（TRCL）裁决已落定（T3 于 v5 通知）**：**选"删 fallback"路线** —— `parseTrclDeg` 在全 `gui/` 内**唯一生产调用点是 `Preview3DLattice.tsx:272`**，而该文件是 T3 判定的**死模块（FE-03）** ⇒ **TRCL 部分随 FE-03 删除即自然消除，零额外成本**。
  ⇒ **t2 相邻发现第 3 条（TRCL 口径不一致）状态更新为「已裁决」**：**前端侧随 FE-03 关闭**（**需 PM 派单执行 FE-03，本会话只读、未执行**）；**后端侧保留**（`_cell_trcl_deg` 作为唯一口径，且"`trclRotationDeg` 必下发"应写进契约）。该相邻发现**仍不计入 25 条总数**。

### 5.3 冻结后的最终账目

| 项 | 值 |
| :--- | :--- |
| 债条总数 | **25**（BE-01…BE-26，其中 **BE-06 已撤回**） |
| 分级 | **P0 = 2（BE-02 / BE-05）｜P1 = 8（含 v8 降级的 BE-01）｜P2 = 12｜P3 = 3** |
| §二 已核实已清偿 | 11 项 + **BE-06 撤回理由（第 12 项）** |
| §三 存疑 | 10 项 |
| 相邻发现 | 3 项（其中 **TRCL 那条状态：已裁决，前端随 FE-03 关闭**） |
| 本文件之外 | **未修改任何文件、未执行任何代码改动、未跑测试/构建/打包** |

### 5.4 v8 增补：t4 复审带来的两处撤回/订正（2026-09-10）

**（a）§4.2「`pos_index` 不可达」—— 撤回（错报，已驳回）**
t4 实读指出并逐行给出：`source_sampler.py:67-68` 已有 `pos, pos_index = self._position(rng)` → `_erg(rng, pos_index)`（**实参已接**）；`_position():202-204` 的 POS=Dn 分支 → `_sample_pos_dist():216-228` 末尾 `return tuple(...), idx`（**返回真实位置索引**）；其余模式 `None` → `_erg:107` 取 `0.0`。我原依据 `_cell_refs_pos` grep 零命中**与该机制无关**。⇒ 本条撤回，BE-02 的处置**删除"接 pos_index"这一步**。我已在 §4.2 用删除线留档。

**（b）BE-02 分支口径 —— 订正（我 v5–v7 写错）**
我原写"Q/S/T 恒得空列表"，**错**：`S`（`:684-691`）读的是 `distributionIds`，而 `_parse_ds` **恰好写这个键** ⇒ **S 是唯一读对的**；恒走默认的是 **Q（读 `values`）/ L（读 `values`）/ H（读 `values`）/ T（直接 return default，`resolve_ds_t` 亦读 `values`）**。已在 BE-02 证据列订正并标注原表述有误。**影响**：若按我原口径派单，修法会漏掉"L/H 也坏"这一面。

**（c）t4 追加的更深发现（已并入 BE-02）：S 分支 J 列表起点错位**
`_parse_ds:104-105` 把 `toks[0]` 当 `param`、`toks[1:]` 当 `distributionIds`；而 `app/docs/源分布卡说明.md:175` 写 `DSn S S1 … Sk`（**S 无独立 param**）⇒ 解析 `DS1 S 2 3` 得 `param="2"`、`distributionIds=["3"]` ⇒ **索引 0 取到分布 3（应为 2）**，J 列表整体右移一位。`app/docs/C810_卡片格式详细.md:183` 又写 `DS[n] var Dn1 …`（含 var）⇒ **两份派生文档自相矛盾，权威只有 C810.pdf**（本次未访问）。**"只有 S 可用"的前提因此也不成立**；且**只改读键修不好 S**，必须先裁 `param` 语义与 J 列表起点。已写进 BE-02 证据列与处置。

**（d）t4 的两项判准/未决项（我不改其结论，仅登记）**
- **BE-01 降 P1**：t4 采「用户是否被误导／是否存在用户可见错误」为判准（零调用方 ⇒ P1），判准已在其 `TD-04` 行明示；**我按其判准同步本表为 P1**，并注明若换判准只需改该条。
- **`lattice.py` 是否随包可用**：**t4 与我仍未决**。我主张有静态边（`from app import lattice`）；t4 指出 `__import__("lattice")` 取**顶层名**、与 `app.lattice` 在 PYZ toc 中非同一条目，且部署全树 2301 条路径内 `lattice` 零命中 ⇒ **只能 runtime 定论**（一条 `POST /api/lattice-extent`）。**我接受"runtime 定论"这一结论**，并同意 t4 的建议：**先补 `diff_inp.py`**（纯动态、无静态边可救，结论不受该争议影响），`lattice.py` 待 runtime 结果。BE-05 行内已同步此分歧表述。

---

**审计人：engineer-backend ｜ 日期：2026-09-10 ｜ 只读审计，未修改任何代码**（本文件为唯一产物，写盘经 PM 明确授权；§四 为应 t4 复审与 T3 交叉复核追加的增补附录；**§五 为 v7 撤回与自查记录（含 PM 冻结令后的账目终态）**）

