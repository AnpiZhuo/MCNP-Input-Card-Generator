# 项目记忆文档（AI 速查手册）

> 最后更新时间：2026-09-12（**STEP 导入 500 热修**：`/api/import-step` 手写 `CellRow` 字段映射 ⇒ 每次导入必 HTTP 500；已收敛到单一序列化 seam + 补回归测试 + **仅重打包 sidecar 部署（未升版）**，详见下方 S4）。此前（2026-09-10，**SDEF 源粒子演示可视化（TODO #6）落地**，已实现待提交：后端三深模块（`DistributionSampler` 分布抽样 / `source_sampler` 源编排 / `voxel_csg` 全宏体拆解）+ 端点 `/api/source-demo-sample` + 独立「🎬 演示源」3D 窗口；按 C810.pdf 权威语义**做全不降级**、有错就地报；门禁后端新单测 **49 passed** + tsc EXIT 0）。此前（2026-09-04，**后端拉起提速 + preview_cache 跨进程持久化**，已提交 commit 0a266cd；此前未提交 3D 功能已一并提交 f7fc2ed）。此前（2026-08-28，**v1.7.4**：3D 预览 MCNP 窗口裁剪修复 + U 分组侧边栏，**追加两项 Bug 修复——① disc STL 键错配（d8b6747，BEAVRS 燃料 pin 方块→真实圆柱）；② z 居中（5fafd1d，燃料棒/围板整体上移 230→位置正确，用户已复验确认），均仅重打包 sidecar 部署**；门禁后端 test_lattice(81)+test_api_contract(17) 绿 / 前端 vitest 527/527 / tsc EXIT 0）。此前（2026-08-27）：v1.7.4 上线（MCNP 窗口裁剪 + U 分组侧边栏，已打包部署 `D:\MCNP\MCNP输入卡生成器`；门禁后端 **85/85**（test_lattice+test_api_contract）/ 前端 vitest **527/527** / tsc EXIT 0）。此前（2026-08-24）：Wave 2a 后端 15 项修复**全绿**：pytest **703/0/0**（基线 686 + 新增 17）——项 2/4/5/9/13/15 + 项 14 剩余 + api.yaml cycle 契约 + R1 五夹具/kitchen_sink R4 不回退 + 契约闸门含 cycle HTTP 用例；详见 docs/backend-changes.md §AA。前端 Wave 2b 并行进行中，golden 已写盘全部可断言无 skip）。此前：格阵 fill 三阶段**最终复验全绿**：pytest **674/0** / vitest **466/0 无 skip** / tsc EXIT 0 / 契约闸门 15/15 / 空 STL 修复生效，用户指定 E2E 17/17 PASS，**建议放行统一提交**，详见 docs/qa-report-final.md —— **按人脑模型重组**（原「顶部横幅 + §8 流水混装」整理为「短期记忆 / 长期记忆」两区，完整流水外置 `docs/CHANGELOG.md`）。同日完成 **GQ/SQ 3D 预览修复 + 渲染后续增强 + OWEN 四项 + 参数扫描前端**：全部门禁绿（pytest **573/0** / vitest **358/0** / tsc EXIT 0）+ PyInstaller sidecar 重打包 + 打包版冒烟通过。
>
> **人脑模型组织说明**：
> - **◉ 短期记忆（工作记忆）**：只放"现在正在处理的事"——当前批次 / 工作区 / 待办。**容量小、变化快、随批次刷新**（人脑工作记忆约 7±2 项）。
> - **◉ 长期记忆（稳定存储）**：固化后不随批次变动的知识——**语义记忆**（是什么/为什么：身份/ADR/规则/目录）、**情景记忆**（发生过什么/经验教训：踩坑/里程碑）、**程序性记忆**（怎么操作：打包/测试手册）。
> - **记忆巩固规则**：批次结束 → 短期记忆区刷新；经验教训**固化**进长期记忆（§5 规则 / §6 踩坑 / §4 ADR）；详细流水**归档**进 `docs/CHANGELOG.md`（+ backend/frontend-changes.md + git log）。
> - **维护者**：项目经理（AgentTeams 记忆维护）。

---

# ◉ 短期记忆（工作记忆）—— 当前活跃上下文

> 只保留"正在处理"的信息。**批次完成后，本区随 CHANGELOG 归档一起刷新。**

## S4（当前批次）STEP 导入 500 热修（2026-09-12，**仅重打包 sidecar 部署，未升版**）

> **用户报告**：「我导入 step 功能怎么炸了？」——部署版点「📥 导入 STEP」→ 后端 **HTTP 500**，前端弹出 `'CellRow' object has no attribute 'number'`。

### 根因（一个字段名过期，整条链路 100% 挂）

`gui/backend/api_server.py:_handle_import_step` 里**手写**了 deck 平铺序列化：

```python
[{"number": c.number, "material": str(c.material), ...} for c in (deck.cells or [])]
```

而 `deck.cells` 自 `f8f7fe6` 起已是 **`CellRow` 判别联合**（`kind` + 嵌套 `cell`），**没有** `number/material/density/surface_expr` 字段 ⇒ 每次 STEP 导入必然 `AttributeError`。2026-08 删掉 McCAD 兜底分支后只剩这一条路径，缺陷 100% 暴露；**该端点当时零测试覆盖**，所以静态审计与全量 pytest 都没抓到（pytest 908 passed 全绿也照样漏）。

### 修法（收敛到唯一序列化 seam）

- `app/step_importer.py` 新增 **`flat_cell_json(row)`**：吃 `CellRow` / `CellData` / 平铺 dict，出 `docs/contracts/api.yaml` 契约的平铺 5 字段（`number/material/density/surface_expr/comment`）；`kind=="raw"` 的 `#ifdef` 条件行 `{kind:"raw", text}` 原样透传，不丢行。
- **`geometry_deck_response()`** 内部统一走它；handler 只传 `deck.cells`，**不再手写字段映射**（同类漂移无处可藏）。
- 顺带修 `app/step_importer.py` 的 `from freecad_locator import ...`：补 `except ImportError → app.freecad_locator` 双导入（其余 app 模块都有，唯独它没有 ⇒ `import app.step_importer` 直接炸，测试无法在包路径下导入）。

### 回归测试（先红后绿，已实证）

`tests/unit/test_step_import_deck_response.py`（**8 例**）：CellRow 序列化不再炸 / 契约字段集恰好 5 键 / void 空密度 / raw 行透传保序 / 平铺 CellData+dict 兼容 / 空与 `cell=None` 不炸。
**红能力实证**：把 `geometry_deck_response` 临时回退成 `cells_list or []` → 该文件 **2 failed**（`'CellRow' object is not subscriptable`）；恢复 → **8 passed**。

### 端到端实证（HTTP 500 → 200）

自建反馈回路 `_loop_step_import.py`（仓库根，可复用）：FreeCAD 造 10×10×10 box STEP → 走前端同款 payload（`file.text()` → `data` 字段）POST `/api/import-step`。

| 目标 | 修前 | 修后 |
| :--- | :--- | :--- |
| 源码后端（dev） | HTTP 500 `'CellRow' object has no attribute 'number'` | **200** · cells=4 / surfaces 16 行 |
| **部署版 sidecar**（改前实测） | HTTP 500 同款 traceback（`api_server.py:2640`） | **200** · cells=4（1 实体 + 自动 void + Graveyard_in + Graveyard） |

### 附带修：GEOUNED 定位只在 FreeCAD 解释器里问得到

`app/step_importer_geouned.py` 的 `_resolve_geouned_path()` 原来只在**后端解释器**里 `find_spec("geouned")` —— 但 geouned 是装给 **FreeCAD 的 Python** 的（requirements.txt），开发机因此恒报「缺少 geouned 包: 」（路径还是空的）。现改为候选链：`GEOUNED_PATH` → 冻结 `_MEIPASS/vendor` → 后端解释器 → **FreeCAD 解释器子进程探测**（进程内缓存一次），且每个候选都经 **`_is_geouned_dir()`** 验证（须有 `geouned/__init__.py` + `geouned/GEOUNED/__init__.py`）——本机 FreeCAD site-packages 里那个**只含空 `GEOReverse` 的残缺 namespace 包会被正确拒掉**（旧代码只判 `isdir` 会当可用，worker 起来才炸 ImportError）。失败信息也改成可操作版（含 `GEOUNED_PATH` 用法）。**开发环境跑 STEP 导入需 `GEOUNED_PATH=D:\MCNP\GEOUNED`**。

### S4.1 续：GQ 栅元"奇形怪状/消失"+ 体积误差 4.6% → 0.3%（2026-09-12 同日，用户真实文件驱动）

**用户实测文件** `P:\dekstop\mcnp_export.step`（本程序导出的 STEP 再导入，18 栅元）。现象：**一部分栅元奇形怪状**。

**判据（可复用）**：GEOUNED 在 `csg.mcnp` 里给每个实体栅元写了 **`Vol=`**（从 STEP 算的真实体积）→ 拿它当尺子量我们 3D 预览产出的 STL 体积，误差一眼可见。修复前：7 号 **+22%**、8 号 **完全没有 STL**、9 号 **−24%**；其余栅元吻合（它们走 OCC 精确路径）。

**根因（三层，全在 `app/voxel_csg.py`）**：
1. `cell_aabb` 对**裸平面引用**（MCNP 正侧，如 `112`=PZ400 正侧）返回 None ⇒ 薄片丢下界。
2. `_aabb_intersect` **只比数值不看 `axes` 标志位** ⇒ `CZ` 无界轴占位 `(0,0)` 把 `-PZ405` 的 `z≤405` 压成 `z∈[0,0]` ⇒ 紧盒退化 ⇒ `_clip_aabb_to_bound` 兜底**整个 ±846 盒** ⇒ 体素 13.2 mm，而 8 号只有 **5 mm 厚** ⇒ 网格为空/糊块。
3. 细化盒顺序错（先取交后补 margin）⇒ 命中盒 z 只剩一个粗扫层时，margin 把盒子撑到 120 mm ⇒ 9 号厚度只剩 3.8 mm。

**修法**：① 新增 `_surface_positive_aabb`（轴对齐平面正侧=半空间，球/柱/锥仍 None）；② `_aabb_intersect`/`_aabb_union` 认标志位、无界轴统一 `±1e300` 哨兵；③ 细化盒 =「(命中盒 + 粗扫余量) ∩ 解析紧盒」（两者都是保守超集，取交才安全）。

**体积精修（−4.6% → −0.3%）**：二值 marching cubes 的顶点落在内外采样点**中点** ⇒ 曲面整体内缩半个体素，薄片受害最重且误差随分辨率**振荡**（res64→256：−4.7/+4.0/+0.5/−1.1%）。新增 `eval_cell_scalar`（min/max 组合的 CSG 标量场）+ `project_vertices_to_surface`（1~2 步牛顿沿梯度贴回真实曲面）：**MC 只负责拓扑，位置由标量场修正**。代价 +0.02 s/栅元（1M 三角的 graveyard +0.31 s）。

| 栅元 | GEOUNED Vol | 修前 | 修后（生产 res） |
| :--- | ---: | ---: | ---: |
| 7 | 78087.4 | 95425（+22%） | **77870.9（−0.28%）** |
| 8 | 38704.4 | 无 STL | **38573.0（−0.34%）** |
| 9 | 156514.1 | 119314（−24%） | **156176.9（−0.22%）** |

全模型 18 栅元（体素路径压力测试）全部 **≤0.6%**。视觉对照 `_cmp_cells.png`（前/后）、`_grid_after.png`（1–14 号逐个）：修复前 7 号是锯齿糊块、8 号空白、9 号带洞薄片；修复后均为干净圆盘。

**顺手关掉的坑**：`PreviewCache.GEOMETRY_CACHE_VERSION`（几何算法进指纹）——同一 deck 改算法后会命中**旧 STL**，用户"看不到修复"（本次实测踩到，手动清了 `D:\MCNP\memory\preview_cache`）；bump 到 2 后自动失效。

**未修（记录在案）**：① `classify_gq` 把这两个**抛物线柱面**误判成"半径 3.0 的椭圆柱"（特征值 ~1.7e-21 应视作 0），影响交叉截面路径；② void 15/16 仍不产 STL（改动前后一致，非回归）；③ 二值 MC 的剩余偏差由投影压到 <0.35%。

### 重打包/部署记录（两轮，均未升版）

**第 1 轮（15:30，sidecar-only）** —— 只改了 Python，前端没动：

- **备份**：`D:\MCNP\_backup_1.7.6_20260912_152729`（2304 files）。
- **PyInstaller**：`cd gui && python -m PyInstaller mcnp_sidecar.spec --noconfirm --distpath dist_sidecar --workpath build_sidecar`（**146 s**；产物 `python.exe` 28623682 B + `_internal` 2294 files，含 `vendor\geouned`）。
- **暂存/部署**：`dist_sidecar\python\{python.exe,_internal}` → `gui\src-tauri\binaries\`（exe 名仍带 target triple）→ `D:\MCNP\MCNP输入卡生成器\{python.exe,_internal}`（robocopy `/MIR`；部署目录多出的 6 个 `app\__pycache__\*.cpython-311.pyc` 是 FreeCAD py3.11 旧字节码缓存，被 `/MIR` 清掉，无影响）。
- **冒烟**：`/api/import-step` 200；`/api/xsdir-check`/`mcnp-detect`/`diff-inp` 均 ok。

**第 2 轮（16:32，完整链路：前端 + sidecar + tauri）** —— 本轮改了 TSX（导入即关窗），必须重出 Tauri exe：

1. **前端** `node .\node_modules\vite\bin\vite.js build` → `dist/assets/index-BIZ-a7qZ.js`（旧 `index-D8_xgTqs.js`）；构建后 grep 到新标记「STEP 转换中」确认入包。
2. **sidecar** PyInstaller **92 s**；日志明示 `Building because app\voxel_csg.py changed`；产物 `python.exe` **28631092 B**。
3. **暂存**：`dist_sidecar\python\_internal` → `binaries\_internal`；exe 同时写 `binaries\python-x86_64-pc-windows-msvc.exe` **与** `src-tauri\python-x86_64-pc-windows-msvc.exe`（后者是 `externalBin` 真正读取的位置）。
4. **tauri build**：`$env:RUSTUP_HOME='D:\rust\rustup'; $env:CARGO_HOME='D:\rust\cargo'; node .\node_modules\@tauri-apps\cli\tauri.js build` → `Finished release profile in 30.54s`；`beforeBuildCommand` 里的 `npm run build` 由 tauri 自行拉起，**不受 PowerShell 执行策略影响**。
5. **⚠️ 6.2 坑第 6 次命中**：`target\release\python.exe` 已是新版（28631092），但 `target\release\_internal` **仍是旧的**（逐文件哈希比对差 10 项：`app\voxel_csg.py`/`step_importer*.py`/`preview_cache.py`/`base_library.zip`…）—— Tauri 只拷 `externalBin` 的 exe，不拷 `_internal`。**判据升级：逐文件 MD5 比对 `target\release\_internal` 与 `dist_sidecar\python\_internal`**，比"查有没有本批新增模块"更硬（本批全是改文件、没有新增模块）。按手册强制覆盖后一致。
6. **部署**：`target\release\MCNP 输入卡生成器.exe`（6622208 B）+ `python.exe`（28631092 B）+ `_internal`（2294 files）→ `D:\MCNP\MCNP输入卡生成器`；三处 MD5 逐一比对一致。改前快照 `D:\MCNP\_backup_1.7.6_20260912_162912`（2304 files）。
7. **冒烟（`_smoke_deployed.py`，部署版实机）**：5001 **2 s** 就绪；`/api/import-step` **200**（18 栅元，6.4 s）；**`/api/preview-3d` 16 个 STL（8 号在列）且最大体积误差 0.36%**；`xsdir-check`/`mcnp-detect`/`diff-inp` 全 ok。**故意不清 `preview_cache`** ⇒ 缓存版本号（`GEOMETRY_CACHE_VERSION=2`）生效，旧网格未再被命中。

**教训固化（已入 §6）**：① 只改 Python 可以只重打 sidecar；**改了 TSX 就必须 `vite build` + `tauri build`**（前端 bundle 内嵌在 Tauri exe 里）；② 6.2 校验改用**逐文件哈希比对**；③ 部署前必须停掉 `MCNP 输入卡生成器.exe` 及其 sidecar，否则文件占用且 5001 会与 dev 后端互相劫持。

## S1（上一批次）v1.7.6 发布批次（2026-09-10 ~ 09-11，**全链路闭环，已交付用户**）

> **一句话**：技术债审计（34 条）→ 修复 → 实跑验证（抓出 **5 个静态审计看不见的编译级缺陷**）→ 打包部署；随后按**用户真实卡**（Practice3 热室）逐轮验收，又修出**源演示 4 连 bug** + 方向线/滑杆 + 粒子圆点化 + **一键运行多核 tasks** → **v1.7.6 升版打包部署 + 冒烟通过**。
> **版本**：**1.7.6**（2026-09-11 用户指定）。**完整逐条流水**：`docs/CHANGELOG.md`（「一、批次详情档案」含各子批全文）+ `docs/fix-verification.md` §7/§8 + `docs/backend-changes.md` + `docs/frontend-changes.md`。

### 📊 门禁（2026-09-11 实跑全绿）

| 门禁 | 结果 |
| :--- | :--- |
| `python -m pytest tests -q -rs` | **900 passed / 0 failed / 0 skipped**（875 基线 + 25 例 `test_mcnp_tasks.py`；`skipped=0` ⇒ "隐藏 skip"不存在） |
| `tsc --noEmit` / `tsc -p tsconfig.test.json --noEmit` | 两档 **EXIT 0**（后者首次启用时曾暴露 35 处测试类型错误，已全清 —— TD-17 盲区关闭） |
| `vitest run` | **78 files / 625 tests passed / 0 skip** |
| `vite build` | **EXIT 0** |
| spec 一致性闸门 `test_sidecar_spec_keep.py` | **绿**（`_keep_py` ↔ `_import_app` 双向；该闸门此前**从未执行过**，2026-09-10 首次跑通） |

**先决条件（实测）**：跑 pytest 前**须停 5001**（契约测试要端口空闲，§6 坑 1）；`pytest-timeout` **未装**（勿加 `--timeout` —— 否则 pytest 以 `unknown option` 直接退出，看似"全红"其实根本没跑）；`npm.ps1` 被执行策略拦 ⇒ 用 `npx.cmd` 或 `node .\node_modules\...`。**执行者能力**：**有 shell**（PowerShell + Python 3.13.14 + node v24.18.0 + cargo 1.97.1）。

### 📦 v1.7.6 发布（2026-09-11，8 步手动链路；一键打包已废弃）

- 链路：**升版六处** → vite build → PyInstaller（~160 s）→ 替换 binaries → tauri build（33 s）→ **6.2 时效校验** → 备份旧包 → 部署 → 冒烟。
- **⚠️ 6.2 坑第 5 次命中**：`target\release\python.exe` 仍是 09/10 的 **28561279 B** 旧版且**缺 `mcnp_tasks.py`** ⇒ 强制覆盖为 **28615181 B**。**最优判据（本批固化）：直接查 `target\release\_internal\app\` 有没有本批新增模块** —— 比对比 mtime/字节数更硬。
- **冒烟（部署版 vs 旧包）**：`/api/xsdir-check` 200（loaded）、`/api/diff-inp` **200**（旧包 **500**，`No module named 'diff_inp'`）、`/api/lattice-extent` 200、`/api/source-demo-sample` **200**（旧包 **404**）；5001 **3 s** 就绪 + MCP 8100 LISTENING。
- **升版六处**：`gui/package.json:4` / **`gui/package-lock.json`（顶层 + `packages[""]`；本批发现手册原先漏列）** / `tauri.conf.json:10` / `Cargo.toml:3` / `Cargo.lock`（`mcnp-ui`）/ `README.md:25` 徽章 ⇒ 全 **1.7.6**。⚠️ `Sidebar.tsx:2` 直接 `import pkg from "../../package.json"` ⇒ **版本号构建期进 bundle**，升版后**必须重新 `vite build`**。
- **备份**：`D:\MCNP\_backup_1.7.5_20260912_114743`（223.1 MB / 2303 files）；部署目录 `D:\MCNP\MCNP输入卡生成器`（`_internal` 2294 files）。用户数据在 `D:\MCNP\material`，不受覆盖影响。

### 🔴 本批次抓出的真缺陷（静态审计/单测都看不见，全部已修）

| # | 缺陷 | 症状 |
| :-- | :--- | :--- |
| 1 | `app/meshtal/meshtal_cache.py:136` **`IndentationError`**（TD-26 加锁丢了 `while` 体缩进） | 全量 pytest **收集阶段中断**，一条测试都没跑 ⇒ "全绿"是假象 |
| 2 | `gui/src/components/CellEditDialog.tsx:174` 多余三元 `: null,`（TS1135） | 该文件**无法编译**（启用 `tsconfig.test.json` 才暴露） |
| 3 | `app/generator/source_sampler.py:_summarize` 丢弃单能 δ 分布真实能量 | `[14,14]` 被改成假 `[0,1]` |
| 4 | `tests/unit/test_sidecar_spec_keep.py:_parse_hidden` 正则**静默丢内容** | 闸门自身假绿（已改显式配对扫描） |
| 5 | `gui/mcnp_sidecar.spec` `_keep_py` 误列 `_cross_section_helper.py` | TD-34 闸门报"spec 与源码漂移" |
| 6 | **源演示 4 连 bug**（见下表） | 用户实测"一坨方块、看不到栅元" |

**用户裁决 5 项已全部落实**（水密骨架删除 + 契约改名 `cell-closure-check.md`、hexCenter 旧公式 2 处、`frontend-changes:208` 核实为**审计记录有误**、SI 类型 `V` 改合法 `L`（TD-35 关闭，R1/R4 字节断言未回归）、先提交再验证）—— 详情见 `docs/CHANGELOG.md`。
**新依赖**：`@types/node@^22.20.2`（**devDependency**，已获批，不影响运行时与打包体积）。**类型放宽 3 处**（行为等价）：`CellEditDialog`/`DeckContext` 的 `CellData.fill_grid` 改可选、`CycleCellLike.fill_grid` 加 `| null`。**前端另有** TD-23 死代码修复（`sourceAdv.ts` 旧存档 SI/SP 静默丢失）+ `distDual.parseDistributionLines` 见 `frontend-changes.md`。

### 🔧 源演示修复链（S1.0c → S1.0d-3，**用户真实卡 Practice3 逐轮驱动**，4 轮全部经**浏览器端视觉复验**）

> 本项目**首次具备"看图判读"能力**：headless Edge（CDP）+ node 24 内置 `WebSocket` 自写驱动，**零新依赖**、脚本置于仓库外。方法学与三个坑（`alert` 冻结渲染进程 / 同 hash 导航不重载 / PowerShell 空串参数被丢弃）见 `docs/fix-verification.md` §8.4 与 §6。

| 轮 | commit | 根因（真 bug） | 修法 |
| :-- | :--- | :--- | :--- |
| **c** | `a255a3f` | ① 栅元只传 `{num,mat,comment}` ⇒ **`surface_expr` 丢失**（它是建外壳 STL 与判定 CEL/SUR 几何的**唯一来源**）⇒ 4 张真卡外壳栅元数**全 0**；② `resolve_cell_complements()` 返回 **pymcnp 节点**（`_Paren`/`_Union`）而 `voxel_csg` 只认 list AST ⇒ `TypeError` 被 `except Exception: continue` **静默吞掉** ⇒ 几何全丢；③ 防呆：POS 全空时后端兜底 `(0,0,0)` ⇒ 500 粒子叠原点 | 传扁平 `{number,material,surface_expr,...}`；补 `_geometry_ast_to_json`；`except` 改记录 `geometryErrors`（响应带 `geometryWarnings`，前端黄字）；POS 未配置时前端**红字拦截** |
| **d** | `48c51ed` | ④ 后端补 camelCase 别名时**漏 `mat`** + `SourceTab` 把 **snake_case** `deck.cells` **强断言**成 camelCase `LocalCellRow` ⇒ `c.cell.mat` 恒 `undefined` ⇒ `material=""` ⇒ `getMatColor("")` 返回 `"transparent"` ⇒ `buildCellMaterial` 判**真空 M0**（`opacity:0`，**13 个外壳全隐形**）；⑤ 取景**误用体积窗口**的 `computeFramingBox`（`VOLUME_FRAMING_RATIO=0.25`，源区/热室≈**0.057**）⇒ **只框粒子、外壳被挤出视野** | 补 `mat`；`SourceTab` **直读 snake_case（删类型谎言）** + 过滤 `kind:"raw"`；`getMatColor` 区分「空/非法→中性灰」与「M0→透明」；取景改 `unionBoxes`（**`PtracRenderer` 同类缺陷同批修**；`computeFramingBox` 本身**不动**，以保体积窗口语义与其 3 个测试） |
| **d-2** | `857aed1` | ⑥ 方向线长度是**世界空间固定值**（39.05×0.03=**1.17**）⇒ 被"外壳优先"取景（盒对角线 ≈914）缩成 **~1px**；⑦ **「方向线长度」滑杆完全无效**（`setDirectionLength` 只改变量 + `markDirty`，**从不重建几何**） | 改**屏幕空间恒定**（`2×相机距离×tan(fov/2)×3%×倍率`，随相机实时重算 + 0.5% 去抖）；滑杆改为驱动重建 |
| **d-3** | `b1f0043` | ⑧ 粒子是 `THREE.Points` **轴对齐方块**、永远面向摄像头（用户观感差） | 加 `getDotTexture()`（64² canvas 径向渐变圆 + `alphaTest`）⇒ **圆点**；零新依赖，且**保住屏幕空间可见性**（优于 `InstancedMesh` 小球——后者是真实尺寸，外壳取景下只有几像素） |

**视觉复验（修后）**：热室立方体 + 内部空腔 + 盖板圆盘 + 观察孔圆柱**全部可见、多材料配色正常**；500 粒子 x∈[-7.480,7.413]⊂[-7.5,7.5]、y∈[-9.973,9.930]⊂[-10,10]、z∈[50.031,79.893]⊂[50,80]，`allParticlesInsideSourceBox=true`，跨度 14.89×19.90×29.86 ≈ 源区 15×20×30；PTRAC 窗口外壳亦恢复可见。

**S1.0d-2 方向线 + 滑杆（`857aed1`）**：见上表第 3 行。**测试盲区（教训）**：`gui/test` 下**没有任何 `SourceDemoRenderer` 测试**（grep `SourceDemoRenderer|setDirectionLength|arrowLen` **零命中**）⇒ "滑杆无效"能长期存活；该渲染器目前**只有端到端视觉验证能覆盖**。

**S1.0d-3 粒子圆点化（`b1f0043`）**：见上表第 4 行（用户裁决"换成圆形贴图点"，改动最小）。

**★ 顺带定案：用户报"粒子颜色不对"** —— 其卡 `si1 -2 1` + `sp1 0 1` 按 C810 **H 直方图**语义就是**能量在 [-2, 1] MeV 内均匀抽样**（⚠️ **`sp1` 的 `0` 是强制占位符 —— 定义能量范围的只有 `si1`**）⇒ 约 **2/3 粒子为负能量**；而 `app/generator/source_sampler.py:431` 用 `if p["energy"] and p["energy"] > 0` **只把正值计入 `energyRange`** ⇒ 返回 `[0.0037, 0.9973]`（**失真**）⇒ 前端 `normalizeEnergy01` 把负能量**钳到 0** ⇒ 全落到 `trackShade` 最浅端 ⇒ **颜色层次塌成一片接近白色**。

**A/B 实证**（按用户要求把 `si1 -2 1` 改成 `si1 0 2`，**只改注入副本，用户原卡 `E:\download\Practice3 (3).TXT` 未动**）：

| 指标 | 原卡 `si1 -2 1` | 变体 `si1 0 2` |
| :--- | :--- | :--- |
| 负能量粒子数 | **约 2/3** | **0** |
| `energyRange` | `[0.0037, 0.9973]`（失真） | `[0.0002, 1.9954]`（**与真实一致**） |
| 颜色参数 t 的 10 桶分布 | 2/3 挤在第 0 桶（最浅） | **`[49,48,50,43,55,56,54,45,51,49]` 均匀铺满** |
| 观感 | 一片接近白色 | **完整浅蓝→深蓝层次** |

⇒ **程序抽样符合 C810，无 bug**。真正缺口是**缺少"SDEF 能量分布可能产生非正值"的校验/提示**（"有错就地报"原则），而 `energyRange` 的 `>0` 过滤是**症状补丁**。**待用户裁决**（加校验 / 改卡）。
> **订正一条旧记载**：早前记的"点源场景方向线长度趋近 0（`arrowLen` 依赖粒子跨度）"已随 d-2 的**屏幕空间恒定**改造而不再是问题。
> 粒子类型侧**无问题**：卡里 `sdef … par=1` ⇒ 粒子类型 1，后端实测返回 `particle:"n"`、面板"中子 500 / 光子 0 / 电子 0"，与卡一致。

**★ `C810.pdf` 已可直读（本批打通，能力级收获）**：本机 **PyMuPDF（`fitz`）已安装** ⇒ **零新依赖**即可提取这份 1001 页权威手册文本，卡格式语义不必再靠 `app/docs/` 派生 md 猜。**已提取定案**：SI/SP（页 746-747 —— SI = 自变量值、SP = 对应概率；**H 下 SI 是分箱边界、SP 首项必须为 0（占位）**，抽样 = 选分箱后**箱内均匀**；A/L/S 同页）、`tasks`（页 520/875）。**`DSn` 卡的 `param`/J 起点语义仍待核对**（两份派生文档矛盾，§4 待办 5 残余）。脚本在仓库外：`D:\MCNP\_agent_probe\{pdf_index,pdf_extract,pdf_tasks}.py`。

### ⚙️ 一键运行 MCNP 支持多核 tasks（S1.0e，`21d93d0`）

- **权威依据（C810 页 875）**：`TASKS n` 走 OpenMP 线程（*Invokes OpenMP threading on shared memory systems*）；且 **`DBCN(2,3,4)` / `SSW` / `SSR` / `PTRAC` 与 `tasks > 1` 不兼容（FATAL error）**。
- **实测：`tasks` 取物理核数而非逻辑核**（Ryzen 7 4800H，8 物理核/16 逻辑核，10M 历史）：

  | tasks | 1 | 4 | **8** | 9 | 16 |
  | :-- | :-- | :-- | :-- | :-- | :-- |
  | 墙钟 | 22.35 s | 8.38 s | **8.36 s** | 8.81 s | **15.06 s** |
  | CPU/墙钟 | 0.99 | 3.96 | 7.83 | 8.91 | 13.66 |

  ⇒ **`tasks 8` 最优；`tasks 16` 因超订反慢 80%**（烧 205 s CPU，大半自旋）。Amdahl 反推：串行 ≈6.35 s、可并行 ≈16 s ⇒ 理论上限 ≈3.5×，实测 2.67×。
  > ⚠️ 这是**极简铁球模型**（碰撞少、可并行占比低）；真实屏蔽模型收益更好 —— 建议用**自己的卡**调小 NPS 后比墙钟选优。
  > ⚠️ `tasks` **只在 OpenMP 构建上生效**；判据是输出出现 `comment.  threading will be used …`，非线程版**静默忽略**（不报错也不加速）。

- **两层防线**：**UI 前置提示**（`TasksIncompatibleHint` 挂在 **PTRAC 启用** 与 **SSW/SSR 面源** 两处 ⇒ **选模式即提示**）+ **后端兜底**（`app/mcnp_tasks.py` 扫卡强制降级并把原因回传 `tasksNote`，经「高级→额外卡片」手写进去也拦得住）。
- **复用**：抽 `gui/src/utils/detectedCores.ts`（**消除 `SweepDialog` / `PreviewDialog` 里重复的 `DETECTED_CORES`**；`DEFAULT_WORKERS` 保持既有 `min(8,核)` 行为，新增 `SUGGESTED_WORKERS` = ⌈逻辑/2⌉ 物理核估计、`clampWorkers`）。`PreviewDialog` footer 加核数滑杆并把 `tasks` 传给 `/api/run-mcnp`。
- **新模块必须登记 spec**：`app/mcnp_tasks.py` 已入 `_keep_py`（**不登记即 TD-02 那个"冻结包 import 失败"**），受 `test_sidecar_spec_keep.py` 双向闸门守护；新增 **25 例**单测（跳格展开 / 三种排他卡 / DBCN 第 2·3·4 项 / `28j 0 13j 0` **不误报** / 注释跳过 / 缺省·非法·超限夹取）。
- **为什么单列 `app/` 模块**：项目纪律禁止 pytest import `gui/backend/api_server`（pyvista/FreeCAD 污染），逻辑必须住 `app/` 才能被测 —— 与 `diff_inp`/`lattice` 同构。

**UI 复验（截图三连）**：勾选 PTRAC → 黄框提示现；切「面源 (SSW/SSR)」→ 提示现；生成预览 footer → `CPU [滑杆] 8`（= 实测最优值）。

**发布**：本批是**新功能**，按规则"升版由上级指定"当时未升版；**同日用户指定升版 1.7.6 并打包部署** —— 见上文「📦 v1.7.6 发布」。三态：**已改 ✅ / 已提交 ✅ / 已打包部署 ✅**。



### 🧹 待办（本轮**未做**，明确记录，勿当作已做）

1. **M-10**：`app/UI_ARCHITECTURE.md` 仍陈旧（`25 端点` 实际 **49**、`pytest 251 绿` 实际 **900**，共 3 处）→ 审计处置①要求"整体重锚定或标为历史快照"。
2. **TD-19**（P1）：214 处 `any` 重构 + **单一 `CellData` 定义**（现状实证：`DeckContext.CellData` snake_case `imp_n` vs `CellEditDialog.CellData` camelCase `impN` **两套并存**）。上一轮"无 tsc 可跑"的搁置理由**已消失**，可排期。**⚠️ 2026-09-11 升级为高优先**：S1.0d 的"看不见栅元"根因正是这条缝的产物（`deck.cells` 是 snake_case、`cellBridge.LocalCellRow` 是 camelCase，中间靠后端补 camelCase 别名 + `as` 断言糊住，**别名漏了 `mat` 就整条链路静默失效**）。
3. **TD-35 残项**：`gui/src/utils/distDual.ts:19` 的 `SI_LETTERS` 仍含 `V`/`Q`/`T`/`F`，与后端 `_SI_LETTERS = (L,H,A,S)` 不一致。
4. **C810.pdf 仍未逐字核对**（`DSn` 卡 `param`/J 起点语义；项目内两份派生文档互相矛盾）。

---

## S1.1 历史批次索引（2026-08-22 ~ 09-10，**详情已归档，勿在此重复展开**）

> **维护规则**：批次完成即在此表加一行「索引」；**详情写 `docs/CHANGELOG.md`**（+ `docs/backend-changes.md` / `docs/frontend-changes.md`）。
> 本区只保留**仍影响当下判断**的状态与未闭环项；已验证闭环的历史细节不再重复（正是"记忆量过大"的成因，2026-09-10 压缩）。

| 日期 | 批次 | 关键交付 | commit | 门禁（当时） | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 09-10 | **SDEF 源粒子演示（TODO #6）** | 后端三深模块（`DistributionSampler` 分布抽样 / `source_sampler` 源编排 / `voxel_csg` 全宏体拆解）+ `/api/source-demo-sample` + 独立「🎬 演示源」3D 窗口；按 C810 全不降级、有错就地报 | `4f0798fa` | 新单测 49 / tsc 0 | ✅ **已打包部署**（2026-09-10，见 S1 发布批次；实施时"未打包"状态已闭合） |
| 09-10 | **源分布 v2 双态 + 原文值网格化** | 修"无字母 `SI` 被回填 `L`"根因（`distributions.py` 权威解析/发射，raw 逐字直通）；前端 `distDual.ts` 双态 + 8 列值网格 | 随本批 | 相关 46 / vitest 587+4 | ✅ 已提交 |
| 09-04 | **AI 接入 inputcard-mcp** | `inputcard_mcp/` 6 深工具（按语义段读写）；`--mcp-http` 本机 8100；快捷建栅元 HEX/TET；IMP 数值化；深模块 `useQuickAddOverlap`；**废弃一键打包**；`AI接入.md` | 1.7.5 批次 | vitest 554 / tsc 0 | ✅ 已提交（**stdio `--mcp-server` 已移除，别再教它**） |
| 09-04 | **stderr-hang 修复** | mcp/anyio/httpx 日志降 WARNING（Windows 管道缓冲小 + 无人读 stderr → server 阻塞写 stderr → MCP 卡死）；因果实验证实 | 同上 | pytest 765/0 | ✅ 已修（**作 A 级教训见 §6**） |
| 09-04 | **后端拉起提速 + preview_cache 跨进程持久化** | `import api_server` 2546ms→299ms（惰性 `_surf_classes` + handler 内按需 import + 后台预热线程）；STL 缓存写盘到 `D:\MCNP\memory`，跨重启命中 | `0a266cd` | 654/0、preview_cache 11/0 | ✅ 已提交 |
| 09-04 | **3D 预览重合检测 fill 修复** | 前端补传 `u/fill/lat/fill_grid/trcl/render/imp`（原只传 4 字段 → 后端三道防线全失效）；17×17 假重叠 57→0；BEAVRS 331→10 真实栅元 | 随批 | overlap 15 / vitest 546 | ✅ 已提交 |
| 09-04 | **格阵 universe 覆盖完整性检测（红框预防）** | `coverage_check.py`（16³ 采样 + `EDGE_INSET_REL`）+ `/api/validate-universe-coverage`；涂色时即时提示（不阻断） | `f7fc2ed` | 随批 | ✅ 已提交 |
| 09-04 | ***fmesh 能量沉积 + 3D 可视化** | `fn_prefix` 贯通（`*FMESH14:N`→MeV/g）；`sliceExport.ts` 切面 + PNG/SVG/CSV 导出；零新依赖 | `f7fc2ed` | pytest 741 / vitest 546 | ✅ 已提交 |
| 08-30 | **材料库深化** | `material_library.py` + 5 端点；`D:\MCNP\material\material_library.json`（D 盘不可写回落 `%APPDATA%`）；custom/override；JSON/CSV 导入导出（冲突三选 + 一致自动跳过）；📚 管理面板 | 1.7.4 沿用 | pytest 737 / vitest 534 | ✅ 已打包部署 v1.7.4 |
| 08-28 | **lat=2 六棱柱 3D 预览 bug 三修** | ①容器表达式含 `#n` 补集 → FreeCAD 构建失败（**剥离 `#` token**）；②`_subpitch` 硬编码 1.26 → `None` 初值取实际 min pitch；③hex 未居中 → 统一 `(i-(nx-1)/2, j-(ny-1)/2)` | 见 CHANGELOG | 99/0 / vitest 527 | ✅ 已修（**hexCenter 权威公式未改，只改调用处偏移**） |
| 08-28 | **FILL 涂色 U 配色** | 固定 12 色 → golden-angle 色相散列（`universeColorByRank`，500 U 零撞色） | 见 CHANGELOG | vitest 528 | ✅ 已打包部署 v1.7.4 |
| 08-27 | **3D 预览 MCNP 窗口裁剪 + U 分组侧边栏** | 实体 = `universe ∩ 格元盒 ∩ 容器 cell`（MCNP 窗口机制）；BEAVRS 超壳叶 48→16；侧边栏改 U 分组 | `530ee8a`/`7de14cd`/`39772a0` | 85/85 / vitest 527 | ✅ 已打包部署 **v1.7.4**（版本五处同步） |
| 08-28 | ↳ **disc STL 键错配 + z 居中** | ①disc 按格阵引用建 STL，但叶 universe 是径向 pin → 回退 `BoxGeometry` 方块（5.5 万 pin）；改为补建叶 universe 裁剪 STL。②格元盒底锚 STL + 原点在中心 → 整体上移 height/2；`_stl_recenter_z` 平移居中 | `d8b6747`/`5fafd1d` | test_api_contract 17 | ✅ 已重打包 sidecar 部署，**用户已复验** |
| 08-25 | **用户 3D/格阵编辑器 7 项反馈** | 见 CHANGELOG | 见 CHANGELOG | vitest 516 / 后端 79 | ✅ 已提交 |
| 08-24 | **格阵 fill 15 项用户实测反馈（三阶段）** | 见 CHANGELOG（含 golden 写盘、R1 不动点） | `2e38934` | — | ✅ 已提交 |
| 08-24 | ↳ 阶段3 3D 预览实施 + 阶段2 UI 画布设计契约 | 见 CHANGELOG | 同上 | — | ✅ 已完成（曾因两 agent 被用户停止而重派） |
| 08-23 | **栅元列表批量编辑 + 会话外技术债清偿 14 项 + P0 3D 重合 bug** | 见 CHANGELOG | `c3e5c43`（未 push） | — | ✅ 已提交 |
| 08-23 | **v1.7.3 两批发布**（keff 仪表盘 / 材料搜索 / 示例库 / INP 对比；重合检测超时 + 零体积检测） | 见 CHANGELOG | 见 CHANGELOG | — | ✅ 已提交并部署 |
| 08-22 | **GQ/SQ 3D 预览修复 + 渲染增强 + OWEN 四项 + 参数扫描前端** | 纯 numpy MC 去 vtk、TR、解析切片、切线平面法、mctal 解析、校验规则交叉核对、sweep 模块 + 2 端点 + SweepDialog | 未 commit（文件恒 1.7.2） | pytest 573 / vitest 358 / tsc 0 | ⚠️ **当时未发版**；其成果已并入后续版本（如需追溯见 CHANGELOG） |

**本区仍需记住的几个「活」约束**：

1. `app/generator/inp_generator.py` 仍**模块顶层** `from pymcnp import inp` —— 这是 `tests/test_tech_debt.py` F#7 的 fail-fast 约定（pymcnp 缺失须导入期报错），**不要"顺手优化掉"**。
2. `D:\MCNP\memory` 是后端可复用内容的持久目录（STL 缓存），**不在仓库、不入 git**；打包/换机须保证可写。
3. **一键打包已废弃**（`release.bat`/`scripts\release.ps1`/`README-release.md` 已删）—— 只走 `docs/手动打包方法.md` 手动链路。
4. **AI 接入统一走 `--mcp-http`（本机 8100 `/mcp`）**；`--mcp-server`（stdio）已移除并显式 `sys.exit(2)`。
5. **5001 端口**：跑 HTTP 契约测试或起 sidecar 前先确认无人占用（`Get-NetTCPConnection -LocalPort 5001`）。历史上**多次**因打包版 sidecar 残留劫持而出现"假红/假绿"（§6）。


## S2 工作区与分支

- **分支**：`main`。**工作树**：干净（2026-09-10 三次提交后 `git status --porcelain` 无输出）。
- **当前 HEAD**：见 `.git/refs/heads/main` + `.git/logs/HEAD`（reflog 是纯文本，比 `git log` 更适合 AI 只读）。
- **2026-09-10 本批提交（三个，按主题拆分）**：
  | commit | 主题 |
  | :--- | :--- |
  | `049885b` | 技术债审计 34 条修复落盘（TD-02/03 阻塞发布项 + 门禁可信度 + 代码债），70 文件 |
  | `024278c` | 验证批次 —— 跑通全部门禁并修复 5 个真缺陷（pytest 875 / vitest 625 / tsc 0 / build 0） |
  | `198fe37` | TD-35 —— 多源 POS_VEC 改发合法 `SI L`（原发 C810 非法的 `SI V`） |
  > ⚠️ **纪律：提交即登记**（S3.1）。此后每批必须记 commit 短号或待提交清单，精确清单实跑 `git status --porcelain`。
- **版本六处**：`tauri.conf.json` / `package.json` / **`package-lock.json`** / `Cargo.toml` / `Cargo.lock` / README 徽章 恒 **1.7.6** 一致（**唯一权威 = `gui/package.json:4`；侧边栏经 `import pkg from "../../package.json"` 读它 ⇒ 升版后必须重新 `vite build`**，否则界面仍显示旧版本）。
- **部署产物**：`D:\MCNP\MCNP输入卡生成器`（**2026-09-11 重打包 v1.7.6**，含 S1 全量）。旧包备份 `D:\MCNP\_backup_1.7.5_20260912_114743`（223.1 MB / 2303 files）。
  - **2026-09-12 两轮热修覆盖**：15:30 sidecar-only（STEP 导入 500）→ **16:32 完整链路**（前端「导入即关窗」+ GQ 薄栅元修复，`vite build` + PyInstaller + `tauri build`）。部署版现为 `MCNP 输入卡生成器.exe` 6622208 B / `python.exe` 28631092 B / `_internal` 2294 files，**版本号仍 1.7.6**；改前快照 `D:\MCNP\_backup_1.7.6_20260912_162912`（2304 files）。冒烟最大体积误差 **0.36%**。
- **2026-09-11 本批提交**（按主题拆分）：`48c51ed` 源演示修复二批（material + 取景）／`857aed1` 方向线不可见 + 长度滑杆失效／`b1f0043` 粒子圆点化 + SI/SP 权威语义定案／`21d93d0` 一键运行多核 tasks + 排他卡提示／`d20726c` 升版 1.7.6 + 打包部署。

## S3 进行中任务 / 待办

- **⭐ 当前（2026-09-11）**：**v1.7.6 已升版并打包部署**（用户指定）。三态 = **已改 / 已提交 / 已打包部署 + 冒烟通过**。本批次覆盖：**源演示修复链（4 轮）**、方向线不可见 + 长度滑杆失效、粒子圆点化（附 `si1 -2 1` 诊断）、一键运行 MCNP 多核 tasks + PTRAC/SSW/SSR 排他卡提示。
- **本轮明确未做（按优先级，详见 S1「🧹 待办」）**：
  1. **M-10**：`app/UI_ARCHITECTURE.md` 重锚（3 处陈旧计数）。**成本最低，建议先做**。
  2. **TD-19**（P1）：214 处 `any` 重构 + 统一 `CellData`（现 snake_case/camelCase 两套并存）。搁置理由已消失（tsc 现 EXIT 0）。
  3. **TD-35 残项**：`distDual.ts` 的 `SI_LETTERS` 仍含 `V`/`Q`/`T`/`F`，与后端 `(L,H,A,S)` 不一致。
  4. **C810.pdf 人工核对**：`DSn` 卡 `param`/J 起点语义（项目内两份派生文档互相矛盾）。
- **已交付（近期，全部已打包部署）**：SDEF 源粒子演示（**2026-09-10 首次真正交付**）／AI 接入 MCP over HTTP（1.7.5）／格阵 fill 三阶段 + 覆盖完整性检测／`*fmesh` 能量沉积可视化／材料库深化／栅元封闭性自检／校验规则补全／参数扫描改造／源项 adv 权威化。
- **讨论过未做（可排期）**：`MCNP输入卡生成器_功能待办清单.md` P1#2「3D 预览悬停读数 + 栅元编号标签」（点选高亮已做）；审计遗留 P2/P3 子项（见 `docs/audit/t4-consolidated.md`）。
- **已知阻塞**：无（**唯一环境类风险**：5001 端口劫持——跑 HTTP 契约测试/起 sidecar 前必须确认无人占用；见 §6）。
- **其余**：按用户新反馈排队。

### S3.1 两条新增纪律（2026-09-10 技术债审计输出，**必须遵守**）

1. **提交即登记**：每批改动结束**必须**记「commit 短号 **或** 待提交文件清单」。**依据**：审计发现 08-22~09-10 有约 20 条真实提交（含 1.7.5 升版、封闭性自检、参数扫描改造、源项 adv+appScale）在记忆里**零记录**（`M-16`，记忆外改动），是本次所有记忆债的根因放大器。
2. **三态表述**：凡记录已完成的功能，**必须写清「已提交 commit / 已打包版本 / 部署校验」三态**，不得只写"已完成"。**依据**：SDEF 演示批次的"已实现/已提交/未打包"三态在记忆里曾自相矛盾（`M-15`），并导致"用户安装版有没有该功能"无法回答（实测：**没有**）。

---

# ◉ 长期记忆（稳定存储）—— 固化知识

> 固化后不随批次变动；更新只在"经验固化"时进行。

## §1 项目身份（语义记忆）

- **名称**：MCNP 输入卡生成器（MCNP Input Card Generator）
- **版本**：**1.7.6**（**六处**一致：`gui/package.json:4` / `gui/package-lock.json`（顶层 `version` + `packages[""]` 两处，**本批新纳入清单**）/ `gui/src-tauri/tauri.conf.json:10` / `gui/src-tauri/Cargo.toml:3` / `gui/src-tauri/Cargo.lock`（`name="mcnp-ui"`）/ `README.md:25` 徽章；2026-09-11 **用户指定升版**，因源演示修复二批 + 粒子圆点化 + 一键运行 MCNP 多核 tasks 等新功能上线）。**历史演进**：1.7.2（2026-08-18 快捷建栅元）→ V1.7.2.2 批次（文件恒 1.7.2）→ 1.7.3（2026-08-22 GQ/SQ+重合检测）→ 1.7.4（2026-08-27 MCNP 窗口裁剪+U 分组）→ 1.7.5（2026-09-04 AI inputcard-mcp + 六棱柱/四面体）→ **1.7.6（2026-09-11）**。**规则不变：bug 修复批严禁升版；升版由上级另行指定**。⚠️ 打包手册原先只列"五处（四处+锁文件）"，**`gui/package-lock.json` 也带项目版本号**，本批已补进手册。
- **技术栈**：
  - 前端 UI：React 18 + TypeScript + Vite（端口 1420，表单化标签页界面）
  - 3D 渲染：Three.js（3D 预览 + 体积可视化）/ SVG（平面截面 / OUTP 折线图）
  - 窗口外壳：Tauri 1.x（Rust，无边框自定义窗口；Electron 备用壳已于依赖清理中删除）
  - 后端：Python 标准库 `http.server`（端口 5001，**不用 Flask**），PyInstaller 打包 sidecar
  - 核心引擎：pymcnp（BSD-3-Clause）+ 自研 generator/parsers
  - CSG 几何：FreeCAD（LGPL）；STEP→MCNP：GEOUNED（EUPL-1.2，随程序 vendor 打包）
- **核心业务**：用可视化表单 GUI 替代手工编辑 MCNP `.INP` 输入文件；覆盖生成/导入/校验/3D 预览/截面/材料库/源/计数/输出分析全流程
- **许可**：本项目自有代码 MIT License（2026-08-28 由自定义限制许可改为 MIT，放弃商用/再分发限制）；开源组件各按自身许可

## §2 当前状态快照（语义记忆）

- **开发阶段**：**v1.7.6 已打包部署**（2026-09-11，`D:\MCNP\MCNP输入卡生成器`）——含 **S1 全量**（源演示修复链 4 轮 + 粒子圆点化 + 方向线/长度滑杆 + 一键运行多核 tasks）。**部署版冒烟实测**：`/api/xsdir-check` **200**（`loaded=true`）、`/api/diff-inp` **200**（旧包 500）、`/api/lattice-extent` **200**、`/api/source-demo-sample` **200**（旧包 404）；5001 与 MCP 8100 均 LISTENING；`_internal\app\{mcnp_tasks,preview_cache,lattice,diff_inp}.py` 与 `_internal\vendor\geouned` 全部在位。旧包已备份 `D:\MCNP\_backup_1.7.5_20260912_114743`（223.1 MB / 2303 files）。
  > 旧状态（已作废）：v1.7.5（2026-09-10 部署）只含技术债修复全量 + SDEF 源粒子演示，**不含** 09-11 的源演示二批 / 圆点化 / 多核 tasks。
- **技术债状态**：2026-09-10 完成全量审计（**34 条**，详见 `docs/tech-debt-report.md` + `docs/audit/`，后者被 `.gitignore` 忽略）→ **已完成修复 + 实跑验证 + 打包部署**（见 S1）。审计结论"已证实 P0 = 0"经实机**修正为：至少 1 条实际已坏**（部署版 `/api/diff-inp` 500）。剩余待办见 S1「🧹 待办」（M-10 / TD-19 / TD-35 残项 / C810 核对）。
- **待排期**：无（#7 重合检查已于 2026-08-22 交付；`MCNP输入卡生成器_功能待办清单.md` 的 P1#2「3D 预览悬停/编号标签」仍未做）
- **已完成功能**：
  - 8 标签页表单编辑（基本/材料/几何/源/计数/高级/输出）
  - INP 生成/导入（含拖拽）、工作区自动保存/恢复、4 套主题
  - 材料库（**97 种预设**：49 内置 + 48 PNNL-15870 精选同位素级；xsdir 校验 + 下拉自动填充密度）+ **用户可编辑持久材料库**（材料库深化，2026-08-30：custom/override、导入导出 JSON·CSV、xsdir 反向索引 + 组成自洽校验、「📚材料库」管理面板、MT卡/其他随预设贯通，存 `D:\MCNP\material\material_library.json`）
  - 3D 预览（FreeCAD CSG，`#n` 栅元补集支持）+ 平面截面（STL numpy 切）+ STEP/GEOUNED 导入
  - **GQ/SQ 曲面 3D 预览**（2026-08-22）：含任意 GQ/SQ 的栅元走纯 numpy 体素 CSG（`app/mc.py`/`voxel_csg.py`/`quadric.py`），TR 变换正确、水密、无 vtk 依赖、打包可用
  - **GQ/SQ 精确截面（2D 解析切片）**（2026-08-22）：`app/analytic_slice.py` 在切割平面上解析求值 + marching squares 提取轮廓；**切线平面法快路径**（椭球/圆柱平滑水密网格，~600 三角形）
  - **mctal 解析 + 参数扫描**（2026-08-22）：`app/mctal_parser.py`（k-eff/收敛/tally，纯 stdlib）+ `app/sweep.py` + `/api/sweep-plan`（规划）/`/api/sweep-run`（执行，上限 50 组合）+ 前端 `SweepDialog.tsx`（参数编辑/组合预览/结果表/TSV 下载，OutputTab 入口）
  - **校验规则交叉核对**（2026-08-22）：`docs/contracts/validator-crosscheck.md`（OWEN rules.ts 映射）+ validator 新增 ZAID 格式/份额符号/S(α,β) 目标 3 条材料级规则
  - **BEAVRS/17×17/单棒卡进测试夹具**（2026-08-22）：`tests/fixtures/owen/` 解析基线回归
  - **快捷建栅元**（几何标签页「曲面卡 & TR 变换」⚡）：RCC/RPP/SPH 一键生成曲面+TR+栅元（编号顺延/材料密度带出/imp 勾选/实时线框预览，轴固定世界原点 Z 朝上）
  - **栅元列表批量编辑**（几何标签页栅元列表 ⚡，2026-08-23）：勾选多栅元 → 批量改材料号/密度/IMP/高级参数；曲面表达式**只能追加**（锁死提示 + 后缀输入，确认后回填到栅元表达式末尾；留空字段=不改）
  - **格阵 fill 阶段1：数据层（解析+生成+模型+wire）**（2026-08-24）：`app/lattice.py` 深模块（纯 stdlib）结构化解析 prob41c/inp24/17×17/BEAVRS 格阵（FillGrid JSON：range/dims/cells/raw，`17r` 简写 + `(x y z)` 偏移 + 翻译单填充）+ `format_fill_cards` raw 优先回放（R1 字节稳定）；`CellData.fill_grid` + FILL=/FILL 解析收束 + `_generate_cells` 格阵分派 + `_cells_from_list` wire 透传；伴生修复 `_wrap_long_lines` 注释保护与 `parse_data_cards` 连续 C 行丢失；**前端 wire 透传**：`cellBridge.ts` 深模块统一 local↔deck 双向桥接 + 三处类型桥接 + quickCell 透传；parse→deck→localStorage→generate 全链路 `fill_grid` 不丢（含旧数据兜底 `""`）
  - **格阵 fill 阶段2 后端：validate 预检测 + 端点 + golden 配套**（2026-08-24）：`app/lattice.py` 增 `validate_lattice_surfaces(surface_expr,lat,surfaces_text="")->(ok,msg)`（只认带符号整数交集，拒绝 #/:/括号；lat=1 单 RPP/BOX 或 6 PX/PY/PZ 每轴一对± 或 4 平面 2D；lat=2 单 RHP/HEX 或 6 竖直 P 均布 60°+2 PZ 一正一负；自带曲面卡正则解析，纯 stdlib 不依赖 freecad/parsers）+ 新端点 `/api/validate-lattice-surfaces`（api.yaml operationId=validateLatticeSurfaces + 契约闸门 HTTP 用例）+ 跨语言 golden 断言（读 `gui/src/utils/__golden__/latticeGolden.json`，前端未产出 skip）+ **QA 建议落地** `MAX_EXPANDED_ENTRIES=1_000_000` 封顶 nR 展开/补 0（raw 兜底 R1 不回退）；门禁 pytest **650/0（1 skip golden）**
  - **格阵 fill 阶段2 前端：UI 画布**（2026-08-24）：`gui/src/utils/lattice.ts`（TS 镜像 app/lattice.py 深模块，键名逐字一致）+ `LatticeEditDialog.tsx`（6 步状态机：0 类型尺寸→1 材料锁死0+曲面失焦校验 validate-lattice-surfaces+自动生成平面→2 延伸方向 2D/3D→3 宇宙调色板→4 画布涂色+3D 子预览→5 保存，保存 cells 反算覆盖 raw）+ `LatticeCanvas.tsx`（矩形 CSS grid / 六棱柱 hexGrid 蜂窝涂色）+ `LatticePreview3D.tsx`（useThreeCanvas+hexPrism+computeCameraParams 跟手重建）+ `three/useThreeCanvas.ts`+`three/hexPrism.ts` + `universeGroups.ts`+`useDragToGroup.ts`（按 U 分组显示 + 拖组头改 u）+ GeometryTab（格阵徽标列/⬚ 栅格编辑按钮/按 U 分组 toggle）+ CellEditDialog（格阵字段分组入口）+ 跨语言 golden `__golden__/latticeGolden.json`（backend schema 产出，Python/TS 同断言）；门禁 vitest **449/0**（基线 412 + 新增 37）+ tsc EXIT 0 + vite build EXIT 0；**画布不匹配提示已加**（QA 建议3：条目流≠dims 乘积 → 非阻塞横幅）
  - **网格计数（FMESH/TMESH）3D 体积可视化**（独立「3D 结果」窗口）：体积渲染（`glslVersion:GLSL3`）+ 相机 offset 居中 + 图层级半透明 + 自适应色阶下限 + 不相交并集取景 + A1.2 不匹配警告横幅
  - **PTRAC 粒子径迹可视化**（独立「3D 径迹」窗口）：类型三色 × 能量渐变 + 密度抽样 + NPS 高亮 + 自动探测
  - **OUTP 输出解析/绘图/导出 CSV**（`app/outp_parser.py` 纯 stdlib 容错 + `tallyChart.ts` SVG 折线图 + BOM CSV；MCNP6.1 紧凑布局 + F1/F2/F5 泛化）
  - 条件编译行（#ifdef/#else/#endif）、全行拖拽排序
  - E0/En/T0/Tn 网格（线性/对数/自定义）、三种源模式（固定/SDEF/KCODE）、SSW/SSR 面源
  - **文本↔表单双向互转**：材料/几何/计数三标签页（深模块 `useSectionTextMode`）
  - MCNP 检测与一键运行、内联参考文档
  - **AI 接入（MCP over HTTP）**（2026-09-04，1.7.5）：主程序启动时自动拉起 `--mcp-http`（本机环回 **8100** `/mcp` + `/workspace`），外部 AI agent 可直读直改程序当前工作区；前端「🤖 AI」面板给"给 AI 的自配置提示词"。**stdio 接入（`--mcp-server` / 注册MCP.bat）已于 09-04 移除**（reflog `:267`）——`mcnp_bridge.py` 对 `--mcp-server` 现为显式 `sys.exit(2)`（防止 fallthrough 起第二个 5001）。契约见 `inputcard_mcp/`、`AI接入.md`、`docs/inputcard-mcp.md`。
  - **栅元封闭性自检**（2026-09-09）：`/api/check-cell-closure` 判定 6 状态（closed / infinite / semi_infinite / empty / voxel / unresolvable），结果标在栅元列表「封闭」列；3D 预览顺带检测；深模块 `gui/src/utils/{cellClosure.ts,useCellClosure.ts}`。**展示语义（用户 2026-09-10 裁决）**：外无限 = 允许存在、仅提示**感叹号**；**唯有曲面不封闭 = 禁止**。⚠️ 触界判定依赖 bound（`app/_freecad_csg_worker.py:1122-1175`，tol = B×0.005）。
  - **校验规则补全 + 几何水密自检**（2026-09-09）：validator 6 条语法规则（ZAID 格式 / 份额正负号 / S(α,β) 目标核素 / 宏体参数个数 / 80-128 列 / 未定义引用）；几何页「🩺 几何自检」+ 栅元保存/生成 INP 自动触发（FreeCAD BRep 缝隙 + 重叠）。
  - **参数扫描改造**（2026-09-09）：免正则选中即参数 + 多核并行 + 彩色行标记。
  - **源项编辑器权威化 + 主窗口等比缩放**（2026-09-09）：深模块 `sourceAdv.ts`（adv 权威）/ `useDeckSynced.ts` / `appScale.tsx`；源类型模板精简为单点源 / 多点源 / 高级自由（删除七种冗余模板与自动分布预设）。
  - **格阵 fill 三阶段 + 覆盖完整性检测**（2026-08-24~09-04）：`app/lattice.py` 深模块 + 编辑器 UI 画布 + 3D universe 实例化 + `/api/validate-universe-coverage`（红框预防）+ 切面导出（PNG/SVG + CSV，`gui/src/volume/sliceExport.ts`）。
  - ***fmesh 能量沉积可视化**（2026-09-04）：`*FMESH` 卡（MeV/g）解析 + 3D 可视化 + 单位标签。
  - **SDEF 源粒子演示可视化**（2026-09-10，TODO #6，**已提交未打包**）：`DistributionSampler` + `source_sampler.py` + 全宏体拆解 + `/api/source-demo-sample` + 独立「🎬 演示源」3D 窗口。
  - **部署提速 + preview_cache 跨进程持久化**（2026-09-04）：`_surf_classes()` 惰性导入 + 后台预热（`import api_server` 2546ms→299ms）；STL 缓存落盘 `D:\MCNP\memory`（跨后端重启命中）。
- **用户真实数据档案**：`D:\MCNP\new\claude\meshtal`（tally14/p；旧卡=点探测器周围 1×2×2 网格，新卡=±2000 全域 20×20×10）；模型=原点钨板（rpp -1 1 -1 1 0 1）+ 真空 so 1000/2000；输出样本 `tests/fixtures/simple_tally.outp`、`tests/fixtures/real_meshtal_jk.meshtal`
- **已知阻塞**：无

## §3 项目目录结构速查（语义记忆 · AI 定位代码用）

> 修改功能时先查此表定位文件，避免全盘扫描。

| 目录路径 | 功能说明 | 涉及 Agent |
| :--- | :--- | :--- |
| **Python 核心引擎（app/）** | | |
| `app/models.py` | 数据模型：DeckData/CellData/MaterialData/SourceData/BasicSettings/TallySettings/AdvancedSettings 等 dataclass | 后端 |
| `app/generator/inp_generator.py` | INP 生成主引擎（**已知技术债集中地，见 §4 末尾**） | 后端 |
| `app/generator/inp_parser.py` | INP 解析入口 | 后端 |
| `app/generator/parsers/{core,lines,sections,validator}.py` | 解析管线（行/分段/校验） | 后端 |
| `app/generator/validator.py` | 校验逻辑 | 后端 |
| `app/freecad_preview.py` / `_freecad_csg_worker.py` | FreeCAD 3D CSG 求值（子进程） | 后端 |
| `app/stl_cross_section.py` / `_freecad_cross_section_worker.py` | 截面（numpy 切 STL，不依赖 FreeCAD） | 后端 |
| `app/step_importer_geouned.py` / `geouned_worker.py` | GEOUNED STEP→MCNP 转换封装 | 后端 |
| `app/step_importer.py` / `freecad_locator.py` | STEP 导入 / FreeCAD 定位唯一入口 | 后端 |
| `app/xsdir_db.py` / `material_presets.py` / `material_library.py` | xsdir 截面数据库 / 预设材料库 / **用户材料库持久化（深化，custom/override、导入导出、xsdir 反向索引、组成自洽）** | 后端 |
| `app/outp_parser.py` | **OUTP 输出解析（纯 stdlib 容错，V1.7.2.2 新增）** | 后端 |
| `app/mctal_parser.py` / `app/sweep.py` | **mctal 输出解析（k-eff/收敛/tally）** / **参数扫描纯函数（对齐 OWEN sweepCore）** | 后端 |
| `app/meshtal/` | 网格计数解析/体积构建/配色/cache/deck_match/worker（8 模块） | 后端 |
| `app/ptrac/` | PTRAC 粒子径迹解析 + worker | 后端 |
| `inputcard_mcp/` | **AI 接入 MCP server（本地 stdio，6 工具：read/generate/validate/list_section/patch_section/add_shape，按语义段全量读写；打包用 `mcnp_bridge --mcp-server` 分派）** | 后端 |
| | | |
| **前端（gui/src/）** | | |
| `gui/src/App.tsx` | 主界面（顶栏/导入/生成/保存恢复/主题） | 前端 |
| `gui/src/components/` | 标签页组件：BasicSettings/MaterialTab/GeometryTab/SourceTab/TallyTab/AdvancedTab/OutputTab | 前端 |
| `gui/src/components/Preview3D.tsx` / `Preview3DWindow.tsx` | Three.js 3D 预览（独立窗口） | 前端 |
| `gui/src/components/CrossSectionView.tsx` / `CrossSectionWindow.tsx` | 平面截面（独立窗口） | 前端 |
| `gui/src/three/` | 3D 深模块：cameraParams/renderGate/cellMaterial/TickGrid/axisConfig（轴单一事实来源）/planeOffset（截面平面坐标换算）/quickCellPreview（快捷建栅元线框） | 前端 |
| `gui/src/volume/` | 体积可视化 11 模块（volumeShader/VolumeRenderer/colorize/alignWorld/downsampleRequest/fmeshState/ColorLegend/FMeshForm/VolumeControlPanel/ResultWindow/surfacesAABB） | 前端 |
| `gui/src/ptrac/` | PTRAC 径迹 3D 窗口模块（trackColors/PtracRenderer/PtracWindow 等） | 前端 |
| `gui/src/utils/quickCell.ts` / `gui/src/components/QuickCellDialog.tsx` | 快捷建栅元：纯函数生成（编号/校验/RCC/RPP/SPH/**HEX/TET**）+ 弹窗 | 前端 |
| `gui/src/utils/useQuickAddOverlap.ts` | **快捷建栅元重合检测+补集决策深模块（GeometryTab/Preview3D 共用）** | 前端 |
| `gui/src/utils/batchCellEdit.ts` / `gui/src/components/BatchCellEditDialog.tsx` | 栅元列表批量编辑：纯函数应用（空字段=不改、曲面只追加）+ 弹窗 | 前端 |
| `gui/src/utils/rawOverrides.ts` | **raw_overrides 纯函数构造（V1.7.2.2 新增，含 sdef）** | 前端 |
| `gui/src/utils/tallyChart.ts` | **OUTP 结果 SVG 折线图纯函数（V1.7.2.2 新增）** | 前端 |
| `gui/src/utils/DeckContext.tsx` | **单一权威表单状态**（localStorage 键 `mcnp_workspace_v1`） | 前端 |
| `gui/src/utils/useSectionTextMode.ts` / `sectionConvert.ts` | 文本↔表单互转深模块 + API 封装 | 前端 |
| `gui/src/utils/gridState.ts` | E0/En/T0/Tn 网格解析/序列化深模块 | 前端 |
| `gui/src/utils/backend.ts` / `dataCollector.ts` / `contract.ts` | 后端生命周期 / 表单收集 / 数据类型 | 前端 |
| | | |
| **后端（gui/backend/）** | | |
| `gui/backend/api_server.py` | **HTTP 后端总入口**（路由表见 api.yaml，端口 5001） | 后端 |
| `gui/backend/mcnp_bridge.py` | 打包后 sidecar 启动器（含 `--meshtal-worker` 分派） | 后端 |
| `gui/backend/generate_step.py` | STEP 生成（备用） | 后端 |
| | | |
| **窗口外壳（gui/src-tauri/）** | | |
| `gui/src-tauri/tauri.conf.json` | 无边框窗口、sidecar 配置（externalBin: python） | 后端 |
| `gui/src-tauri/src/main.rs` | Tauri Rust 入口（close_window / open_volume3d_window 等） | 后端 |
| | | |
| **文档** | | |
| `README.md` | 项目总览（技术栈/功能/打包说明/项目结构） | — |
| `app/docs/` | MCNP 参考文档（曲面卡/FN 卡/输出卡/PRINT/C810/源分布/sample_format） | — |
| `app/UI_ARCHITECTURE.md` | UI 架构说明：三层边界/启动链路/deck JSON 契约/raw_overrides/往返保真/技术债地图 | 架构师 |
| `docs/contracts/api.yaml` | **OpenAPI 3.0 契约**（**49 path / 49 operationId**，每 path 带 operationId，防漂移闸门验证） | 架构师 |
| `docs/CHANGELOG.md` | **完整变更流水档案（2026-08-22 起，历史 §8 外置于此）** | 项目经理 |
| `docs/backend-changes.md` / `frontend-changes.md` | 后端/前端逐批改动清单 | 架构师 |
| | | |
| **测试** | | |
| `tests/` | **测试网**：unit + parser + integration（含契约闸门/真实 HTTP）；`gui/test/` vitest（含 jsdom DOM 交互测试）。**计数基线见 §9——历史数字多为各批当时快照，勿直接引用** | 测试 |

## §4 关键架构决策 ADR（语义记忆）

> ⚠️ 本 § 编号被 docs/contracts/* 引用，**不得改名**。

| 决策 | 理由 | 日期 |
| :--- | :--- | :--- |
| 后端用 Python 标准库 http.server，不用 Flask | 减少依赖，PyInstaller 打包 sidecar 更简单 | — |
| 前端单一权威状态在 DeckContext（localStorage 工作区） | 8 个标签页共享一份数据，避免多源状态冲突 | — |
| 文本↔表单互转按 section 维度做深模块（useSectionTextMode） | 材料/几何/计数三处共用一套进出文本模式逻辑 | 近期 |
| 3D 预览用 FreeCAD 子进程 CSG 求值输出 STL | FreeCAD 精确几何；STL 保留供截面复用（numpy 切），不重复调 FreeCAD | — |
| 截面不依赖 FreeCAD，直接 numpy 切 STL | 独立窗口即时响应，无需 CAD 内核 | — |
| GEOUNED 随程序 vendor 打包，用户只装 FreeCAD | STEP 导入开箱即用；FreeCAD 经 locator 检测/手动指定 | — |
| 全部代码遵循**深模块原则**（用户全局记忆 codebase-design-always） | 小接口覆盖复杂行为，AI 友好、可测试 | — |
| **P1 多源/分布 SDEF 表示统一**（`SDEF_FIELD_SPECS` 表驱动 + 字段序 POS 首位 + D-index 由 `dist_params` 位置决定） | kitchen-sink R1/R4 字节不动点要求多源生成与分布回放逐字节一致 | 2026-08-12 |
| **P1 分布注释作为生成器横幅词汇**（`multi_source_comment_banner` 进 `is_generator_banner`） | 复用 F-A 方案 C 的词汇冻结机制，注释不漂移不重复 | 2026-08-12 |
| **P1 raw_overrides 收敛为 `_apply_raw_override` 助手**（1145 raw_tally 门控保留） | 消除 8 处复制粘贴 | 2026-08-12 |
| **3D 预览 deck 指纹缓存**（`app/preview_cache.py`，LRU 上限 3） | 打开卡真凶=全量重建 3.30s；缓存命中 ≤1s | 2026-08-12 |
| **前端 3D 拆深模块**：TickGrid/renderGate/cellMaterial/computeCameraParams | 交互卡真凶=纹理泄漏+无条件渲染+透明 overdraw；大坐标深度超 2^24 | 2026-08-12 |
| **前端后端地址收敛 `127.0.0.1:5001`** | 规避 Chrome Happy Eyeballs 每请求 300-500ms 延迟 | 2026-08-12 |
| **重合栅元几何检查走方案 A（FreeCAD 精确布尔 + AABB 预过滤）**，独立 `/api/check-overlap`；纯分类下沉 `app/overlap_classify.py`；结果同指纹落 preview_cache | 反馈 #7（参考 VISED，P2）；弃 B（STL 不封闭）/C（AABB 伪报率高）；独立端点不污染 preview-3d 契约；**本轮不施工仅存档** | 2026-08-13 |
| **MCNP 卡类型唯一权威源=官方 C810.pdf**；`docs/contracts/card-lexicon.md`（词条目录+解析器清单+差异表）与 `app/docs/` 蒸馏 md 均为**派生**，须随 PDF 更新 | 反馈 #1 FM 漏识别暴露系统性缺陷=解析器卡类型清单未与知识库对齐 | 2026-08-13 |
| **网格计数（FMESH/TMESH）3D 体积可视化契约**（`docs/contracts/meshtal-visualization.md`，16 节） | 对标 VISED；用户拷问敲定全部澄清项；测试先行 + 零新依赖红线 | 2026-08-14 |
| **meshtal-texture 返回标量帧 Uint8，前端 colorize CPU 上色**（python/TS 双端 golden sha256 对照） | 改色阶只重跑本地 colorize；Uint8+CPU 上色避开 float 纹理坑；双端 golden 防漂移 | 2026-08-14 |
| **体积窗口独立场景，不改 Preview3D.tsx 主组件**（复用纯模块）；几何外壳与体积盒共享 offset 对齐；关闭不清 preview-3d STL 会话 | 复用会污染 preview3d-performance 契约 | 2026-08-14 |
| **meshtal 后端落地细节**：数据行列序按实际 MCNP `[Energy] [Time] X Y Z Result RelError`；colormap golden = t-space 插值 round-half-even；worker 模块顶只 stdlib；大文件走子进程 + cache 不阻塞 5001 | golden 是 §4.3.1 跨语言防漂移强契约；"Total" 汇总行跳过 | 2026-08-14 |
| **3D 预览截面坐标双修**：后端 on-plane 顶点作交点 + 共面三角面贡献外轮廓边 + `_join_loops` 容差走环；前端 `planeOffset.ts` 换算 D_raw=D_disp+n·center | 面重合切割旧实现返回 0 环/错环 + 多环被贪心串接；预览归一化平移与后端原始坐标不一致 | 2026-08-18 |
| **快捷建栅元模块化**：纯函数 `quickCell.ts` 集中编号/校验/生成；斜向用 6 局部平面 + TRn（行=局部轴方向余弦）而非 RPP+TR | 规避 worker 对带 Placement 宏体半空间补集布尔缺陷；编号/密度带出/文本模式禁用集中，vitest 可测 | 2026-08-18 |
| **OUTP 解析：pymcnp 正确 API（`Outp.from_mcnp(text).to_dataframe()`）优先 + `app/outp_parser.py` 纯 stdlib 容错兜底**；前端 `tallyChart.ts` 纯函数 SVG 绘图 + CSV 加 BOM | pymcnp 0.9.1 只认 MCNP6.2 布局、MCNP6.1 紧凑布局解析为空；兜底支持 energy 列/total 行可有可无、F1/F2/F5 泛化 | 2026-08-19 |
| **IMP 归一化在生成器层（`_generate_cells`）单一权威**：任一结构化栅元写 imp_n/p/e → 全部补齐，缺省补默认重要性 1 | 部分栅元有 IMP、部分没有 → MCNP 硬规则 fatal；表单/导入/快捷建栅元全路径生效 | 2026-08-19 |
| **SDEF 表单模式回退分支**（`_sdef_dispatch`）：distribution/sdef 无分布时 sources 优先（保 R1 不动点）→ 表单字段有值合成单源 → 全空 `[]` | 表单字段写 `adv.sdef_*` 但无分布时旧逻辑返回空 → INP 无 SDEF | 2026-08-19 |
| **含 GQ/SQ 栅元走纯 numpy 体素 CSG（`app/mc.py` + `app/voxel_csg.py`），去掉 vtk 依赖**；`mesh_cell_polydata(ast, surfaces_by_num, tr_cards, B, res)` 返回 (vertices, triangles)；TR 求值前 `p_local=rotate⁻¹·(p_global−o)`；**带 TR 的有界曲面 AABB 经 8 角点变换求全局紧盒（`_transform_aabb`），无界才保守全盒**；**margin 按实际扫描盒间距（勿用全局 B）**；失败降级包围盒 + `栅元 N: GQ/SQ 网格化失败` 告警 | worker 跑在 FreeCAD 自带 Python（无 vtk）→ GQ/SQ 兜底必失败；OCC 对网格化二次曲面半空间布尔不可靠；实测 TR 被完全忽略 + B=500 下全盒/margin 坑致小栅元空网格 | 2026-08-22 |
| **GQ/SQ 渲染后续增强（同日）**：① **2D 解析切片**（`app/analytic_slice.py`）——切割平面逐点解析求值 + 2D marching squares 轮廓，preview-3d 会话存 deck 快照、cross-section 对 GQ/SQ 栅元自动走解析切片；② **切线平面法快路径**（`voxel_csg._tangent_plane_mesh`）——单个内侧椭球/球/圆柱 + 平面封口 → 切线半空间 + 凸裁剪（Sutherland–Hodgman + 盖面极角排序），水密；椭球 162 方向 + 绕中心体积校正（无封口）/642 方向（有封口），圆柱 48 段；union/补集/多二次曲面/锥回退 MC | 截面轮廓位置精度只取决于解析求值（STL 受网格分辨率限制）；切线路径三角形数 ~600 vs MC ~10 万；OWEN csgScene 的做法（金螺旋方向分布不均 + 边链盖面在贴面顶点退化）不能直接照搬 | 2026-08-22 |

## §5 核心业务规则（语义记忆 · 必读）

- **⭐ hexCenter 权威公式（单一事实，2026-09-10 立此条目以防误用）**：
  ```
  x = col * pitch + row * pitch / 2
  y = row * pitch * √3 / 2
  ```
  代码权威在**两处且必须逐位一致**：`gui/src/utils/lattice.ts:130-137` ↔ `app/lattice.py:604-616`。
  **⛔ 历史记录里的旧公式不要照抄**：本项目 2026-08-25 之前用的是"pointy-top 顶点+X"式
  `x = i·p·√3/2, y = j·p + (i%2)·p/2`（差 30° 旋转），已全部替换。**本记忆文件 §1~§3 与 S1/S2 历史条目里、
  以及 `docs/frontend-changes.md` / `docs/qa-report*.md` / `docs/backend-changes.md` / **`docs/contracts/lattice-fix15-design.md`（含 L1 锁死表）**
  中出现的旧式写法均为历史残留**。⚠️ **L1 锁死表曾写错公式 —— 它是跨语言实现依据，写错会污染实现**（审计 TD-29）。
  被反复"根因修复"过的高危公式，改前先查本节。

- **版本号规则（上级硬规则）**：**任何 bug 修复批次严禁提升版本号**（改多少轮 bug，文件版本号恒为当前版本）。仅**实际新功能**上线才由上级重新指定版本号——快捷建栅元用户指定 **1.7.2**（2026-08-18）；AI inputcard-mcp + 六棱柱/四面体 **1.7.5**（2026-09-04）；**当前版本为 1.7.6**（2026-09-11 用户指定：源演示修复二批 + 粒子圆点化 + 一键运行 MCNP 多核 tasks）。打包时版本**六处**（`tauri.conf.json` / `package.json` / **`package-lock.json`** / `Cargo.toml` / `Cargo.lock` / README 徽章）必须一致；**Cargo/tauri 只接受 `主.次.修订`**，四段号（如 1.7.2.2）会构建失败，仅可作批次号。
- **依赖红线（上级 2026-08-14 更新）**：**新依赖一律须用户批准，且由用户指定安装位置**（2026-08-23 更新：不再默认零新依赖；评估时列出依赖名/用途/体积/许可/替代方案，批准后按用户指定位置安装，如 node_modules 常规位置或 vendored 目录）；**严禁自动运行 npm install / npm ci / pip install**（用户高度敏感，违反即打回）；测试不得 import gui.backend.api_server（模块级 pyvista/FreeCAD 探测污染）。**2026-08-22 用户批准的唯一例外**：`jsdom` / `@testing-library/react` / `@testing-library/dom`（devDeps，用于 SweepDialog DOM 组件测试，已写入 package.json）。
- **权威源**：MCNP 卡类型唯一权威 = `D:\MCNP\MCNP6\C810.pdf`（实际 = MCNP5 卷 I+II 全文 + 发布说明；卡格式权威章 = MCNP5 卷 II Ch.3，PDF 页 526-691）；`app/docs/` 蒸馏 md 与 `docs/contracts/card-lexicon.md` 均为**派生**，须随 PDF 更新。
- **DeckData 是聚合根**：前端 DeckContext ↔ 后端 generate/parse 全走 DeckData 单对象，避免参数膨胀。
- **密度写在栅元卡（CELL）上**，材料卡（Mm）只含 ZAID+份额，不含密度。
- **栅元/材料/计数行支持判别联合**：`kind=="cell"|"raw"`（栅元）、`kind=="nuclide"|"raw"`（材料）——`raw` 行承载 `#ifdef/#else/#endif` 原样条件行。
- **文本模式状态存在 deck.textMode[section] + deck.rawOverrides[section]**；进文本模式前必须由后端先生成当前表单的文本（section-to-text），防数据丢失。
- **STL 会话**：3D 预览生成的 STL 保留在 `_STL_SESSION`，供截面复用；只在关预览窗口/清空时 `/api/clear-stl` 删除。
- **曲面文本解析**：GEOUNED 常见 `*TRn` 后缀或 `100*` 前缀的 TR 引用，均需提取 transform；P 卡 `A B C D` 系数形式需转三点定义（注意法向同向性）。
- **SDEF 三种模式**：`fixed`（固定点源）/ `distribution`（SDEF 分布源，SI/SP/DS 结构化 JSON 优先于 sdef_raw_text）/ `kcode`（KCODE/KSRC/HSRC）。
- **前端契约层**：`sectionConvert.ts` 只认 `{status:"ok"}` 成功响应，`/api/text-to-section` 返回 `{data}`，`/api/section-to-text` 返回 `{text}`。
- **测试时间限制（上级 2026-08-22）**：所有测试/构建命令必须加**硬性时间限制**——探活/HTTP 请求/PyInstaller 等长命令用 `Start-Process` + `WaitForExit(超时)` + `Kill`，超时即杀并明确报错，严禁无限挂起。

## §6 踩坑与排雷指南（情景记忆 · 经验教训）

- **vite dev 在本机挂死（2026-08-15 实测）**：node 24.18 + vite 5.4.21 + @vitejs/plugin-react 4.7.0 组合下 vite dev 接收请求后零响应（最小空项目正常，加载项目配置即挂）→ 浏览器白屏/转圈。**启动 bat 已改为 vite build + python http.server 静态服务 dist**，不再依赖 vite dev。
- **5001 端口劫持（2026-08-15 实测；2026-08-24 阶段2 验收复现；2026-08-24 Wave 2a 再复现）**：Windows SO_REUSEADDR 允许多进程同绑 5001——打包版 sidecar 与 bat 起的 api_server 可同时"监听"，请求被劫持分流。bat 已加 netstat 占用检测（有后端就复用）；诊断用 `Get-NetTCPConnection -LocalPort 5001` 查 OwningProcess。**阶段2 复现实证（QA 独立验收）**：运行中的旧打包版 `D:\MCNP\MCNP输入卡生成器\python.exe -u backend/mcnp_bridge.py`（无新端点）劫持契约闸门 HTTP 用例 → 新端点 `test_http_validate_lattice_surfaces` 404；其余旧端点用例由劫持端也能通过，**只有新增端点才暴露劫持**。**Wave 2a 再复现**：残留旧 server（PID 4776，跑旧代码无 cycle 判环）劫持 5001 → cycle 端点 500 递归错误（新端点/新逻辑才暴露）；杀 PID 复绿。教训：验收新端点/新逻辑前先清 5001（杀旧 sidecar/旧 server/关主程序），或契约闸门 fixture 起子进程前检测端口占用并明确报错；**浏览器复验前必须确认 5001 跑的是新代码**。**Wave 2a 复发（2026-08-24）**：pytest 残留的旧 api_server 子进程（PID 4776，跑**旧代码**）劫持 5001 → 新 cycle 端点 500（maximum recursion depth exceeded，traceback 行号与当前文件不符=老代码跑 cycle 无判环）。杀 PID 后复绿。诊断要点：HTTP 500 且 traceback 行号对不上当前文件 → 先查 `netstat -ano | grep 5001` 占位进程，别先改代码。
- **P0 体积层渲染两弹（2026-08-15 实测，真实渲染复现）**：① three r160 WebGLProgram 对 RawShaderMaterial **前置 `#define SHADER_TYPE` 块** → shader 首行 `#version 300 es` 不再首位 → GLSL 编译失败 → **体积层自引入从未渲染**（静默，快照测试只锁字符串不编译一路绿灯）。修复：shader 去首行 `#version` + `glslVersion: THREE.GLSL3`。② 相机未 offset：物体按 offset 平移到原点但相机用未 offset 世界盒 → target 对空、画面错位。修复：`applyOffsetToBox` 纯函数。**教训：WebGL 类问题必须 headless 真渲染验证，不能只靠快照测试**。
- **3D 预览截面"部分实体切错"（2026-08-18 实测）**：① 切割平面恰与实体面重合（模型底面 z=0、相邻栅元共享面）时旧 `slice_stl_segments` 对 on-plane 顶点 continue → 0 环/错环；共面三角面须贡献出现 1 次的外轮廓边。② 预览归一化平移与后端原始 STL 系不一致 → 切位偏移；2026-08-18 起主预览**已去归一化**（显示系=原始系，modelCenter 恒 0，`planeOffset` 换算恒等但保留防回归）。③ 坐标轴单一事实来源 `axisConfig.ts`（X 红/Y 绿/Z 蓝），不要再内联写 dirs。
- **FreeCAD 对「旋转宏体半空间」补集布尔失效（2026-08-18 实测）**：`RPP ... *TRn` 正侧 = bound.cut(内盒) 再 apply_trn（带 Placement 复合体），对 `-曲面` 求补集返回垃圾体积（1.7e8 > 整盒 1.25e8）。斜向六面体一律改用 6 个局部 PX/PY/PZ + `*TRn`（普通平面布尔可靠）；轴对齐 RPP 宏体无 TR 正常。quickCell.ts 已按此实现。
- **大网格零通量背景涂蓝（2026-08-15 用户实测）**：色阶下限=0 时精确 0 值也被涂蓝遮模型。已修：色阶下限**自适应** = `minPositive×0.5`（曾用 sqrt 规则切太狠致"只显示一个面"，已按用户反馈改）；注意纹理是线性归一化 u8，微小值会被量化成 0（minPositive 从 u8 字节重建，勿用原始文件最小值）。
- **GQ/SQ 3D 预览 3 连坑（2026-08-22 实测，静态审查发现不了）**：① `app/mc.py` 邻接索引 `t_ids`/`slots` 的 repeat/tile 与「先全部 (0,1)、再 (1,2)、再 (2,0) 的块状边数组」错位 → 朝向传播全乱（signed volume≈0、假碎片/假冲突）；必须 `t_ids=tile`、`slots=repeat`。② BFS 波前同波重复三角形未去重 → 指数膨胀到 4 千万+（内存炸）；用一次性 bool 数组去重。③ 带 TR 小栅元在大 bound（B=500）下：TR 曲面 AABB 必须经 8 角点变换（`p_global=o+p_local@R`）求全局紧盒，保守全盒会让 32³ 粗扫漏检 → 空网格降级包围盒；margin 必须按**实际扫描盒**间距 `(scan_hi−scan_lo).max()/(coarse−1)×1.1`，用全局 `2B/(coarse-1)` 在 B=500 时达 35cm 把细化盒撑爆。水密断言必须用「每条无向边恰被 2 个三角形使用」的边计数法（**vtkFeatureEdges 对 marching cubes 网格误报边界边**）；`*TRn` 求值前必须 `p_local = rotate⁻¹·(p_global − o)`。
- **GQ/SQ 后续增强 3 连坑（2026-08-22 实测）**：① **凸裁剪盖面**：顶点恰落在裁剪面上（dist≈0）时跨边条件会漏掉该交点 → 盖面缺顶点被丢弃 → 三角形破洞（228 条开放边）；`cut()` 端点贴面返回 `keep()`、盖面收集贴面顶点本身。OWEN 的边链盖面法在细密切线平面下会退化丢面（162 面球只出 35 面），改用 Sutherland–Hodgman + 盖面绕质心极角排序。② **金螺旋方向分布不均**：外接多面体顶点半径到 1.08r+、体积误差 8%+，改二十面体细分（162/642 方向）；162 方向外接误差仍 ~2.1% → 无封口时绕中心体积校正 λ=(V_true/V_mesh)^(1/3)（体积精确）、有封口时用 642 方向（区域体积无法解析）。③ **解析切片 marching squares 16 格表 case 12（{2,3} 上边在内）应为 (1,3) 而非 (0,1)**；`_plane_halfspace` 的 pos/neg sgn 与 surface_fn 正侧约定相反（pos 侧要取 −法向）。
- **材料库深化 3 坑（2026-08-30 实测）**：① **嵌套浮窗被 `backdrop-filter` 裁剪**——`FloatingDialog` 用 `backdrop-filter: blur(16px)` 会创建 containing block，使嵌套其中 `position:fixed` 的子弹窗相对父定位、被父 `overflow:hidden` 裁剪。修法=子弹窗用 `createPortal` 渲染到 `document.body`（ExamplesDialog/GeometryTab 同法）。② **模块级缓存被 `useMemo` 冻结不刷新**——`useMaterialLibrary` 用 `useMemo(()=>entries,_cache…,[loaded])`，但 `entries` 依赖模块级 `_cache`（不在 deps），save/remove 后 `_cache` 更新 + notify 触发重渲染，`useMemo` 仍返回旧缓存 → 面板不刷新。修法=去掉 `useMemo` 每次读最新 `_cache`。③ **edit 改写 `.ps1` 丢 UTF-8 BOM**——Windows PowerShell 5.1 按 GBK 读无 BOM 的 UTF-8 中文就乱码解析崩溃；修法=用 `[System.Text.UTF8Encoding]::new($true)` 重存为带 BOM。

- **OUTP 解析误用 pymcnp 构造函数（2026-08-19 实测）**：`pymcnp.Outp(text)` 是构造函数非解析入口，恒报 TypeError；正确入口 `Outp.from_mcnp(text).to_dataframe()`。且内置 pymcnp 0.9.1 Tally_4 只认 MCNP6.2 布局，MCNP6.1 紧凑两列解析为空 → 需 `app/outp_parser.py` 兜底。
- **测试笔误陷阱（fixtures 实测）**：① valid_39.meshtal 的 tally number 是 **4 不是 1**（须取自 parse 响应 `tallies[].number`）；② preview-3d 单栅元 material="0" 是 void → `include_void=False` 跳过 → 空 stl_files（冒烟 deck 须用非 0 material）。
- **❗❗ 编译级缺陷只有"真的跑一次"才能发现（2026-09-10 实证，本项为最高优先级教训）**：一个"97% 修复完成、静态自检全过"的批次里，实测藏着 2 个**编译级**缺陷 ——
  - `app/meshtal/meshtal_cache.py` 的 `IndentationError`（加锁改动丢了 `while` 循环体缩进）⇒ **全量 pytest 在收集阶段就中断，一条测试都没跑**（`1 error during collection`）。若不真跑，会以为"门禁全绿"。
  - `gui/src/components/CellEditDialog.tsx` 多余的三元分支 `: null,`（TS1135）⇒ **该文件根本无法编译**，只有启用 `tsc -p tsconfig.test.json` 才暴露。
  **推论（本项目纪律）**：① **"没有 shell 的修复批次"其交付状态必须标注为「未验证」，不得计入完成**；② 任何"改了很多文件"的批次，第一件事是**全量跑一次**（含 `python -m compileall -q app gui tests` 扫语法 + `tsc` 两档），再谈别的；③ 静态审计（哪怕再仔细）**发现不了"文件根本跑不起来/编不过"**。
- **`/api/diff-inp` 在部署版 1.7.5 是坏的（2026-09-10 实机实证）**：`_import_app("diff_inp")` 走**顶层名** `__import__("diff_inp")`，而 spec `_keep_py` 没登记该文件 ⇒ 冻结包 `ModuleNotFoundError` ⇒ 端点 **HTTP 500**（traceback 落到 `api_server.py` 的 `_import_app`）。**同类模块（`material_library.py`/`gpu_pref.py`）都在 `_keep_py` 里，唯独漏了 `diff_inp.py`**。修法：加进 `_keep_py` 并重打包。**注意**：`lattice` 也走 `_import_app`，但实测**可导入**（未 500）—— 故"有动态导入就必须登记"是**保守且正确**的经验，但"它一定 500"要实机验证；`gui/mcnp_sidecar.spec` 的 `_keep_py` 与 `api_server._import_app` 的**双向一致性**已由 `tests/unit/test_sidecar_spec_keep.py` 自动闸门守住（该闸门此前**从未执行过**，2026-09-10 首次跑通）。
- **"无 shell"会连带污染测试本身的可靠性（2026-09-10 实证）**：`tests/unit/test_sidecar_spec_keep.py` 的 `_parse_hidden` 用 `re.findall(r'"([^"]+)"', spec_text)` 取"全 spec 字符串字面量"，实测**静默丢内容**（同一份文本上返回 74 项且**丢** `models.py`/`meshtal`/`generator`/`docs`；改用**逐引号配对扫描**返回 76 对且四者俱全；`[^"]+` 与 `\x22([^\x22]+)\x22` 两种写法**均复现**）。⇒ 教训：**闸门自身的解析逻辑也要有"内容非空/数量合理"的自检**，否则闸门会假红或假绿。该函数已改为显式配对扫描。
- **打包链路「6.2 时效坑」每次必中（2026-09-10 再次命中，第 4 次以上）**：`tauri build` 是增量编译，**不会刷新** `target\release\` 里的 sidecar（`python.exe` + `_internal\`）——本次实测 `target\release\python.exe` 仍是**上一次**的（mtime 10/9、28561279 B），而新 sidecar 是 11/9、28614639 B，且 `target\release\_internal\app\` **没有**本次新增的 `lattice.py`/`diff_inp.py`。**不校验就会"版本号新、后端旧"**（用户装了新版但仍缺修复）。→ 部署前**必须**按 `docs/手动打包方法.md` §6.2 比对 mtime/大小，不匹配就手动覆盖 `python.exe` + `_internal`。
- **本机命令环境三坑（2026-09-10 实测）**：① **PowerShell 下 `npm`/`npx` 被执行策略拦截**（`npm.ps1 cannot be loaded because running scripts is disabled`）→ 改用 **`npm.cmd` / `npx.cmd`**，或直接 `node .\node_modules\vite\bin\vite.js build`（手册正文即用后者，天然规避）；② **`pytest --timeout` 需要 `pytest-timeout`**，未安装时 pytest 会以 `unknown option` **直接退出**——看起来像"全红"，其实是**没跑**（先 `python -c "import pytest_timeout"` 确认）；③ **Windows 终端默认 GBK**，直接 `print()` 中文可能 `UnicodeEncodeError` 或乱码（PowerShell `Get-Content` 读含 CJK 的 UTF-8 也会乱码）→ 让脚本 `PYTHONIOENCODING=utf-8`，或**把结果写文件再用读文件工具看**（比在终端里读可靠）。
- **meshtal-parse 元数据缓存**：已闭环（`_mode_parse` 先 `get_manifest` 命中即返回，实测二次 0.23s）；`meshtal_cache._MANIFEST_VERSION=2` 使旧磁盘缓存失效。
- **P0/P1 技术债全清偿（2026-08-12）**：引擎缺陷 F-A~F-H + F#1~F#7 全修，R1-R4 不动点成立；`inp_generator.py` 仍为**技术债集中地**（见 docs/backend-changes.md + UI_ARCHITECTURE.md 技术债地图）。
- **FreeCAD 对「圆柱 ∩ 平行于轴平面」布尔恒空（2026-08-24 三阶段验收实测，QA 独立复现）**：`_build_one_universe` 把格元盒裁剪平面追加进 universe cell 表达式做 CSG 交集（`-1 -61 +62 ...`），圆柱（C/CZ 半空间）∩ 任一 PX/PY（平行轴平面）→ **空 STL（84B/0 三角形）**；圆柱 ∩ PZ（垂直轴）正常（4884B/96 三角）、纯 box ∩ 盒正常。现有 preview-3d 走 worker post-hoc bound 盒裁剪（solid-solid boolean）对同 deck 全部非空——**裁剪必须走 solid-solid，不得把平面塞进 cell 表达式**。影响：格阵 universe 实例化详细模式对燃料棒等圆柱格元不渲染。
- **QA API 直验两个易错点（2026-08-24 最终复验实测）**：① `/api/generate` 期望 **deck 字段在 body 顶层**（`deck_from_json(data)` 直接吃 body），不是 `{"deck": deck}` 包裹——包错层会静默生成空 INP（实测 67B）；`/api/section-to-text` 才是 `data.get("deck")`。② 生成器把关键字**大写**输出（`LAT=1`/`U=10`/`FILL=`/`IMP:N`），断言匹配须大小写不敏感（`inp.upper().replace(" ","")`）。
- **FreeCAD 圆柱∩盒平面恒空已闭环修复**：`_build_one_universe` 不再把 6 平面塞进 cell 表达式，改合成单 RPP 宏体 `-<num>` 做 cell solid ∩ RPP 盒实体 solid-solid common（与 preview-3d bound 同机制）；0 三角 STL 显式丢弃（前端回退占位盒）。复验 17×17 全部 12 个 universe cell STL 非空、cell1=96 三角与 preview-3d 基线一致。
- **契约文档**：docs/contracts/api.yaml 覆盖全部端点；漂移闸门 `tests/integration/test_api_contract.py` AST 断言 handlers ↔ api.yaml 双向一致（含真实 HTTP）。
- **Cargo.toml 版本隐患**：v1.6.4 曾漏改（停在 1.6.3）；Tauri 以 tauri.conf.json 为权威不影响出包，但**版本四处+锁文件**必须一致。
- **打包注意（详见 §9）**：Tauri build 需要 `RUSTUP_HOME/CARGO_HOME` 指向 D:\rust；sidecar 用 PyInstaller（spec：`gui/mcnp_sidecar.spec`，产物名 "python"）；**6.2 时效校验**（tauri 增量编译不刷新 target/release 的 sidecar，必须手动核对 mtime/覆盖）；后端窗口关闭时经 Rust `close_window` 命令一起退出。
- **❗「后端返回对」≠「前端拿到对」——跨层缝上的字段丢失（2026-09-11 实证，源演示"看不见栅元"根因）**：后端 `parse-inp` 的 `material` 完全正确（`"1"/"2"/"3"`），但前端经 `SourceTab.demoCellsForBackend()` → `localToDeckCells` 后 `material` 恒为 `""`。**两个成因叠加**：① `api_server.py:1439-1443` 给 cell 补 camelCase 前端别名（`num`/`surfaces`/`impN`/`impP`/`impE`）时**漏了 `mat`**；② `SourceTab` 把 **snake_case** 的 `deck.cells` **强断言**成 camelCase 的 `LocalCellRow`（`as` 类型谎言）—— 而它"看起来能用"恰恰是因为后端补了 `num`/`surfaces` 同名别名，**别名补得越全，类型谎言藏得越深**。⇒ **纪律：跨 snake_case/camelCase 边界禁止 `as` 断言**，要么显式走 `deckToLocalCells`、要么直读本侧字段名。**pytest（后端对）+ vitest（渲染器对）都覆盖不到这条缝**，只有端到端实跑能暴露。
- **❗`!n` 这类"值域重载"会把「缺失」与「特定值」混为一谈（2026-09-11 实证）**：`getMatColor` 原实现 `const n = parseInt(mat); if (!n) return "transparent";` 本意是"M0 = 真空"，但 `parseInt("")` 是 NaN、`!NaN` 为真 ⇒ **空材料号也被当成真空**，下游 `buildCellMaterial` 直接给 `opacity: 0` ⇒ 整个几何不可见。⇒ **纪律：判"特定值"用 `n === 0`，"缺失/非法"单独一条分支**（本次改为返回中性灰 `#888888`）。凡"0 是合法值"的场合，`!x` / `x || 默认` 都要警惕。
- **❗跨模块复用"为别的场景调过的取景/布局启发式"会静默失效（2026-09-11 实证）**：`computeFramingBox` 的 `VOLUME_FRAMING_RATIO=0.25` 是**为体积窗口**设计的（网格层 ≪ 模型时聚焦网格层），被 `SourceDemoRenderer`/`PtracRenderer` 复用后，遇到"源/径迹在屏蔽体内部"（**演示源与径迹窗口的常态**，实测 ratio≈0.057）就把几何外壳挤出视野，且**不报任何错**。⇒ **纪律：复用带阈值/启发式的几何工具前，先问"这条启发式对**本**场景语义是否成立"**；本次两处调用点改为 `unionBoxes`（外壳优先），**共用函数本身与其 3 个测试文件保持不动**。
- **headless Edge + CDP 端到端取证三坑（2026-09-11 实测，本项目首次具备"看图判读"能力）**：① **`alert()` 在 headless 里永久冻结渲染进程**（本程序"导入成功"必弹 `alert`）⇒ CDP `Runtime.evaluate` 永不返回、看起来像"页面卡死"；必须在**同一 CDP 会话内**监听 `Page.javascriptDialogOpening` 并 `Page.handleJavaScriptDialog({accept:true})`。② **导航到"含相同 hash 的同一 URL"不会重新加载文档** ⇒ 是假"重载"（两次截图 sha256 完全相同，一度被误判为"渲染确定性"）⇒ 真重载须用 `Page.reload`；要在加载**前**注入钩子须用 `Page.addScriptToEvaluateOnNewDocument`。③ **PowerShell 调原生程序时空字符串参数会被丢弃** ⇒ 位置参数错位（`run ... "" 8000` 把等待时长当成输出文件名，**在仓库根生成了垃圾截图 `3000`/`8000`**，已删）⇒ 占位参数用 `-` 而非 `""`。**另**：headless SwiftShader 下主界面 `Page.captureScreenshot` 会超时、子窗口正常 ⇒ 只在子窗口截图。
- **MCNP 多核（`tasks N`）知识（2026-09-11 实测 + C810 页 875 定案）**：① 语法 = 命令行**末尾** `tasks N`（**无等号**）；② **只在 OpenMP 构建上生效**（判据：输出出现 `comment.  threading will be used …`；非线程版**静默忽略** —— 不报错、也不加速）；③ **`tasks` 取物理核数**，不是逻辑核数 —— 本机 8 物理核/16 逻辑核：`tasks 8` 8.36s 最优，`tasks 16` 反而 **15.06s**（烧 205s CPU，大半自旋）；④ **`DBCN(2,3,4)` / `SSW` / `SSR` / `PTRAC` 与 `tasks > 1` 不兼容（FATAL error）** ⇒ 程序必须扫卡拦截（见 S1.0e，`app/mcnp_tasks.py`）；⑤ 判据：**`CPU时间 / 墙钟 ≈ N`** 即 N 个核在跑。**本机 MCNP 路径 = `D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe`**（下划线、少一层），与用户 bat 里写的 `D:\MCNP6\MCNP6\MCNP CODE\…`（带空格）**不是同一路径**。
- **❗deck.cells 是「改过型的判别联合」，任何手写字段映射都会静默过期（2026-09-12 实证，用户报"导入 STEP 炸了"）**：`/api/import-step` 里手写 `c.number/c.material/c.surface_expr`，而 `deck.cells` 自 `f8f7fe6` 起是 `CellRow`（`kind` + 嵌套 `cell`）⇒ 每次导入必 `AttributeError` → HTTP 500。**该端点当时零测试覆盖**，且 2026-08 删掉 McCAD 兜底分支后 100% 暴露却一直没人踩到（全量 pytest 908 passed 也照样漏）。修法＝把序列化收敛到 `app/step_importer.flat_cell_json` 一处（handler 只传 `deck.cells`）+ `tests/unit/test_step_import_deck_response.py`（先证红后转绿）。⇒ **纪律：类型改造（dataclass → 判别联合 / 改名）后必须 grep 该字段的全部字面读取点**，跨模块手写映射一律改走单一序列化函数。
- **geouned 的安装位置只能在 FreeCAD 的 Python 里问（2026-09-12 实证）**：`_resolve_geouned_path()` 原来在**后端解释器**里 `find_spec("geouned")` ⇒ 开发机恒报「缺少 geouned 包: 」（路径为空，用户看不出该做什么）。现为候选链（`GEOUNED_PATH` → 冻结 `_MEIPASS/vendor` → 后端解释器 → **FreeCAD 解释器子进程探测**）+ **`_is_geouned_dir()` 验证**（须有 `geouned/__init__.py` + `geouned/GEOUNED/__init__.py`）。**本机 FreeCAD site-packages 里那个只含空 `GEOReverse`、没有 `__init__.py` 的残缺 namespace 包证明：光判 `isdir` 会把残缺安装当可用**，worker 起来才炸 `ImportError: cannot import name 'CadToCsg'`。开发环境跑 STEP 导入须 `set GEOUNED_PATH=D:\MCNP\GEOUNED`。
- **❗发布链路的三个"必中坑"（2026-09-12 两轮热修实证）**：① **改了 TSX 就必须重出 Tauri exe** —— 前端 bundle 内嵌在 `MCNP 输入卡生成器.exe` 里，只重打 sidecar 用户**看不到前端修复**（本轮「导入即关窗」只有重跑 `vite build` + `tauri build` 才生效）；只改 Python 才可以 sidecar-only。② **6.2 时效校验升级为逐文件哈希比对**：`target\release\python.exe` 可能已是新版而 `_internal` 仍是旧的（Tauri 只拷 `externalBin` 的 exe，**不拷 `_internal`**）—— 本批用 `Get-FileHash` + `Compare-Object` 比出 **10 项差异**（`app\voxel_csg.py`/`step_importer*.py`/`preview_cache.py`/`base_library.zip`…）；"查有没有本批新增模块"的旧判据在**全是改文件**时查不出来。③ **部署前必须停掉 `MCNP 输入卡生成器.exe` 与其 sidecar**：否则文件被占用，且残留旧 sidecar 会与新起的 dev 后端**互相劫持 5001**（本轮实测：预览请求落到旧代码，数字看起来像"没修好"，白排查一轮）。
- **`C810.pdf` 已可直读（2026-09-11 打通，重要能力）**：本机 **PyMuPDF（`fitz`）已安装** ⇒ **零新依赖**即可提取这份 1001 页权威手册的文本，卡格式语义不必再靠 `app/docs/` 派生 md 猜（§4 待办 5 的 `DSn` 语义亦可照此核对）。范例脚本在仓库外：`D:\MCNP\_agent_probe\{pdf_index.py,pdf_extract.py,pdf_tasks.py}`。**已提取定案**：SI/SP（页 746-747）、tasks（页 520/875）。

## §7 技术争议与决议（语义记忆）

| 争议点 | 方案 A | 方案 B | 最终裁决 | 裁决理由 |
| :--- | :--- | :--- | :--- | :--- |
| F-A R1 不动点：生成器 C 注释头泄漏，解析器吸收 vs 生成器改头 | 解析器吸收防护（仅节头词汇精确剥离） | 生成器改头为不可吸收形式 | **方案 C，以 A 为主、B 为辅**（2026-08-12） | MCNP 注释只有 C 一种形式，现有解析器对任意 C 行都会在栅元注释/曲面 verbatim/other_cards 三路吞掉，不存在合法且三阶段天然惰性的注释形式。方案 C 把节头冻结为 banners.py 单一事实来源，生成器与解析器共享，R1 测试为漂移兜底；用户可见 INP 输出风格保留 |

## §8 变更日志（情景记忆 · 里程碑纲要，完整流水已外置）

> ⚠️ 本 § 编号被 docs/contracts/* 引用，**不得改名**。完整逐条流水（2026-08-11 起）见 **`docs/CHANGELOG.md`** + `docs/backend-changes.md` + `docs/frontend-changes.md` + git log。
>
> **维护规则**：每次批次完成后，在 `docs/CHANGELOG.md` 追加新条目；本 § 只在里程碑定型时更新一行。

### 版本里程碑

| 版本 | 时间 | 内容 |
| :--- | :--- | :--- |
| **v1.7.6** | 2026-09-11 | **源演示修复二批 + 粒子圆点化 + 一键运行 MCNP 多核 tasks**（**用户指定升版**）：① 源演示"看不见栅元"根因二批 —— 后端补 camelCase 别名时**漏 `mat`** + `SourceTab` 把 **snake_case** `deck.cells` 强断言成 camelCase `LocalCellRow` ⇒ `material=""` ⇒ `getMatColor("")` 返回 `transparent` ⇒ `buildCellMaterial` 判为**真空 M0**（`opacity:0`，13 个外壳全不可见）；且取景误用体积窗口的 `computeFramingBox`（`VOLUME_FRAMING_RATIO=0.25`，源区/热室≈0.057）把外壳挤出视野。② 方向线不可见（世界空间固定长度 1.17 被取景缩成 ~1px）+「方向线长度」滑杆失效（`setDirectionLength` 从不重建几何）⇒ 改**屏幕空间恒定**。③ 粒子圆点化（`Points` 贴图 + `alphaTest`）。④ **一键运行 MCNP 支持多核 `tasks N`**：UI（`PreviewDialog` footer 核数滑杆 + PTRAC/SSW/SSR **选模式即提示**）+ 后端 `app/mcnp_tasks.py` 扫卡强制降级（C810 页 875 排他卡）。**实测 `tasks` 取物理核数而非逻辑核**（8 物理核机上 tasks 8 = 8.36s vs tasks 16 = 15.06s）。门禁 pytest **900** / vitest **625** / tsc 两档 0 / build 0。**已打包部署 + 冒烟通过**（部署版 `diff-inp` 200、`source-demo-sample` 200、5001 + MCP 8100 LISTENING）。commits `48c51ed` / `857aed1` / `b1f0043` / `21d93d0` |
| **v1.7.5** | 2026-09-04 | **AI 接入 inputcard-mcp（MCP over HTTP）+ 快捷建栅元六棱柱(RHP)/四面体 + 深模块化 + 废弃一键打包**（新功能上线，用户指定/确认升版）：`inputcard_mcp/` 包（6 深工具，统一按语义段读写）；主程序启动自动拉起 `--mcp-http`（本机 8100 `/mcp` + `/workspace`，含「当前工作区」会话 + 前端 AI 面板）；**移除 stdio 旧接入**（`--mcp-server`/注册MCP.bat 删除）；快捷建栅元扩到 HEX/TET + IMP 改数值默认 0；抽出深模块 `useQuickAddOverlap`；删除 `release.bat`/`release.ps1`（一键打包废弃，仅手动）；新增 `AI接入.md`。门禁 vitest 554/0 + tsc EXIT 0。reflog: `.git/logs/HEAD:250-251` |
| **v1.7.4** | 2026-08-27 | **3D 预览 MCNP 窗口裁剪修复 + U 分组侧边栏**（用户指定新功能上线升版）：① 实体=universe∩格元盒∩容器cell，修超壳/重叠外壳 + 无限水虚假水块（BEAVRS 超壳叶 48→16）；② 3D 预览侧边栏改 U 分组 + 保留未分组栅元；disc 改用容器裁剪 STL、subPitch 半径；版本五处同步。**18-28 追加**：disc STL 键错配修复（燃料 pin 方块→真实圆柱）+ z 居中（燃料棒/围板位置）|
| **v1.7.4（材料库深化，沿用版本待上级指定）** | 2026-08-30 | **材料库深化**（新功能）：用户可编辑持久材料库（custom/override、`D:\MCNP\material\material_library.json`、D盘回落 `%APPDATA%`）、导入导出 JSON·CSV（冲突三选 + 内容一致自动跳过）、xsdir 反向索引 + 组成自洽校验、📚 材料库管理面板、MT卡/其他随预设贯通；修复：编辑弹窗 `backdrop-filter` 裁剪（`createPortal`）、编辑保存后列表不刷新（去 useMemo）、材料库内编辑隐藏预设区、生成 INP 的 MODE+NPS 卡移数据卡段末尾；README 与 exe 同级放入；spec `_keep_py` 加 `material_library.py`。门禁 pytest **737/0** + vitest 534/535（flaky 隔离绿）+ tsc/build 过 |
| **GQ/SQ 预览修复 + 渲染增强 + OWEN 四项 + 参数扫描前端**（未 commit/发版，文件恒 1.7.2） | 2026-08-22 | 纯 numpy MC 去 vtk + TR + 解析切片 + 切线平面法 + BEAVRS/17×17 夹具 + mctal 解析 + 校验规则交叉核对（validator +3 规则）+ 参数扫描（sweep 模块 + 2 端点 + SweepDialog 前端 + DOM 交互测试）；门禁 pytest **573/0** / vitest **358/0** / tsc EXIT 0；打包冒烟通过；待 tauri build/部署 |
| **V1.7.2.2 批次**（文件恒 1.7.2） | 2026-08-19 | 4 修复进包：源卡文本模式漏生成 / SDEF 表单模式漏生成 + sdef_extra 往返 / IMP 归一化 / OUTP 解析+绘图+CSV（含 F1/F2/F5 泛化）；终版重打包部署，冒烟全过 |
| **v1.7.2** | 2026-08-18 | 新功能**快捷建栅元**（RCC/RPP/SPH 一键生成曲面+TR+栅元，8 次迭代打包）；3D 预览坐标轴/截面/取景修复批 |
| **v1.7.1** | 2026-08-15~16 | **PTRAC 粒子径迹可视化**交付 + 网格计数 3D 结果批（图层级透明/自适应色阶/并集取景）+ P0 体积层渲染两弹 + inp02 解析修复批 |
| **v1.7.0** | 2026-08-14 | 网格计数（FMESH/TMESH）3D 体积可视化大功能（meshtal/ 8 模块 + volume/ 11 模块 + 3 端点 25→28） |
| **v1.6.x** | 2026-08-11~12 | 文本↔表单双向互转 + P0/P1/P2 技术债清偿（F-A~F-H + F#1~F#7）+ 3D 预览性能（preview_cache/TickGrid 深模块）+ 词条专项 D-01~D-13 + 反馈 #1~#7 |

### 关键历史结论（压缩自 08-11~08-15 流水，细节见 CHANGELOG）

- 发布：**手动打包**（docs/手动打包方法.md）；release.bat 已停用（Git Bash MSYS 坑 + 自检失败）。
- 网格计数可视化 v1.7.0（FMESH/TMESH 体积渲染）；P0/P1 技术债清偿（251 绿）；3D 预览性能（preview3d-performance）；文本↔表单互转；用户 7 条反馈 + 词条专项 D-01~D-13（08-13）。

## §9 程序性记忆（操作手册 · 怎么做事）

### 打包链路（每次发布走此流程，详见 `docs/手动打包方法.md`）

> **打包唯一流程为手动**（`docs/手动打包方法.md`）。曾有一键脚本 `release.bat` / `scripts\release.ps1` 均已**废弃删除**（一键脚本曾解决第 ② 项 npm/npx 被 ExecutionPolicy 禁与 6.2 sidecar 时效坑，但整套一键能力已弃用）。当前**每次发布**按下面分步手动执行，**尤其 6.2 时效校验不可跳过**。

```
1. vite build                       （前端产物，~3-4s；node .\node_modules\vite\bin\vite.js build）
2. PyInstaller sidecar              （在 gui\ 下跑 gui/mcnp_sidecar.spec，产物名 "python"；
                                    核对 _keep_py / _keep_dirs 清单，如 outp_parser.py/meshtal/ 等新增模块）
3. 替换 binaries                    （把新 sidecar 的 python.exe + _internal 换进 target\release\）
4. tauri build                      （需 RUSTUP_HOME/CARGO_HOME=D:\rust；node .\node_modules\@tauri-apps\cli\tauri.js build）
5. ⚠️ 6.2 时效校验（必做）           （tauri 增量编译不刷新 target\release 的 sidecar！
                                    ★ 最快判据：查 target\release\_internal\app\ 里**有没有本批新增模块**
                                      —— 2026-09-11 实测缺 mcnp_tasks.py，一眼看穿"版本号新、后端旧"；
                                      亦可对比 python.exe 的 mtime/体积，不一致就按手册强制覆盖）
6. 备份 + 部署 D:\MCNP\MCNP输入卡生成器（⚠️ 先杀运行中的旧主程序 + 占 5001 的 sidecar，否则文件锁目录致
                                      _internal 残缺；部署前把旧包备份到 D:\MCNP\_backup_<版本>_<时间戳>）
7. 冒烟                             （起部署版 → 5001 探活 → 打端点；⚠️ 先确认 5001 空闲，被占则请求被劫持
                                      产生假象；收尾杀掉主 exe + 其 sidecar **按路径精确匹配**，勿误杀他处 python）
```

**关键坑提醒**：① 6.2 时效坑**每次都命中**，不可跳过；② 部署前杀进程（锁目录）；③ 冒烟前先清 5001（否则劫持出假象）；④ 版本**六处**必须一致（`tauri.conf.json` / `package.json` / **`package-lock.json`** / `Cargo.toml` / `Cargo.lock` / README 徽章；Cargo 不接受四段号）；⑤ **升版后必须重新 `vite build`** —— 侧边栏版本号由 `Sidebar.tsx` 直接 `import package.json`，**构建期打进 bundle**（不从磁盘读）。

### 测试门禁（发布前必须全绿）

| 门禁 | 命令/位置 | 基线 |
| :--- | :--- | :--- |
| pytest | `tests/`（unit + parser + integration，含契约漂移闸门 test_api_contract.py 与真实 HTTP） | **最新实跑（2026-09-11）：900 passed / 0 failed / 0 skipped**。沿革：573(08-22) → … → 765(09-09) → 875(09-10) → **900(09-11，含 +25 例 `test_mcnp_tasks.py`)**。**重跑后请覆盖本行** |
| vitest | `gui/test/`（**78 个测试文件**；含 jsdom DOM 交互） | **最新实跑（2026-09-10）：78 files / 625 tests passed / 0 skip**。沿革：358(08-22) → … → 587+4(09-09) → **625(09-10)**。**重跑后请覆盖本行** |
| tsc | `gui/` 下 `npm run typecheck`（= `tsc --noEmit && tsc -p tsconfig.test.json --noEmit`） | 两档 **EXIT 0**。**2026-09-10 扩容**：此前只查 `src/`，测试文件不在类型检查内（审计 TD-17） |
| 漂移闸门 | handlers dict ↔ `docs/contracts/api.yaml` 双向一致；spec `_keep_py` ↔ `_import_app` 双向一致 | **49 端点**；spec 闸门（`test_sidecar_spec_keep.py`）**绿** |

**已知 flaky（2026-09-10 已修）**：colorize 128³ 计时用例负载偶发 >50ms —— 该断言属"单样本墙钟阈值"反模式，已改为多次取中位数 + 宽松上限（或移出默认门禁）。**不再以"隔离单跑即绿"作为放行理由**（审计 TD-18）。

### 版本发布纪律

- bug 修复批**严禁升版**；升版仅限新功能且由上级指定。
- 版本**六处**同步：`tauri.conf.json` / `package.json` / **`package-lock.json`（顶层 `version` + `packages[""].version`）** / `Cargo.toml` / `Cargo.lock`（`name="mcnp-ui"`）/ README 徽章。
- 侧边栏版本号来自 `Sidebar.tsx` 直接 `import pkg from "../../package.json"`（单一来源，升版不再破）—— ⚠️ **构建期打进 bundle**，故**升版后必须重新 `vite build`**，否则界面仍显示旧版本。


