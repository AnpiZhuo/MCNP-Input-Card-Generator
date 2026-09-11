# 技术债修复 · 验证交接清单

> 背景：2026-09-10 完成技术债审计（34 条，见 `docs/tech-debt-report.md` + `docs/audit/`），随后进入**修复阶段**。
> **本次修复由 AI 完成，但修复期间执行环境没有 shell** —— 所有改动都是**静态编写 + 静态自检**，**未跑过任何测试/构建**。
> 因此这份清单就是"怎么确认修对了"的唯一依据。**请按顺序执行，不要跳步。**

---

## 0. 先决条件（必须先做，否则结果不可信）

### 0.1 释放 5001 端口（本项目历史最大坑，§6）
HTTP 契约测试会连本机 5001。若旧后端仍在跑，新端点会 404/500、老端点会假绿 —— **每次跑测试前都要确认**：

```powershell
Get-NetTCPConnection -LocalPort 5001 -ErrorAction SilentlyContinue | Select-Object OwningProcess
# 或
netstat -ano | findstr :5001
```

- **有输出** → 记下 PID；若是 `D:\MCNP\MCNP输入卡生成器\python.exe`（您正在用的打包版后端），**先关闭 GUI**，否则测试会连到旧代码。
- **无输出** → 可以开始。

### 0.2 确认 `pytest-timeout`（避免误判）
`--timeout=` 参数需要 `pytest-timeout`；**未安装时 pytest 会以 `unknown option` 直接退出**，看起来像"全红"，但其实是没跑。

```powershell
python -c "import pytest_timeout; print('ok')"
```
- 报 `ModuleNotFoundError` → **不要加 `--timeout`**，改用外层超时（下面每条命令都写了 `WaitForExit` 式的说明）。
- 另外：本项目 §9 规定所有测试/构建命令都要有**硬性超时**，别让它无限挂起。

---

## 1. 修复清单（按批次，含"改了什么/为什么"）

> 详细审计依据见 `docs/audit/t4-consolidated.md`（TD 编号）与 `docs/tech-debt-report.md`。

### ✅ 批次 0 · 已实测（2026-09-10，接手方执行）：TD-02 定性完成

**结论：TD-02 确认是「真缺口」，且比原判更精确 —— 坏的只有 `diff_inp`，`lattice` 实际可用。**

部署版（用户手上的 1.7.5）实测（先确认 5001 空闲 → 起 sidecar → 逐个只读请求 → 杀进程 → 确认无残留）：

| 端点 | 实测 | 含义 |
| :--- | :--- | :--- |
| `/api/diff-inp` | **HTTP 500** `{"message":"No module named 'diff_inp'"}`，traceback 指向 `api_server.py:36 _import_app` | **真缺口，已复现** —— 用户当前安装版**这个功能就是坏的** |
| `/api/lattice-extent` | 200（`ok:false`） | **可导入**（未 500）→ 原判"lattice 也缺口"**与实机不符** |
| `/api/preview-lattice` | 200 | 同上 |
| `/api/validate-lattice-surfaces` | 200 | 同上 |
| `/api/check-cell-closure` | 200（降级 message） | 正常（该能力已含在部署版） |
| `/api/source-demo-sample` | **HTTP 404** | 部署版**不含**该端点 ⇒ 坐实"SDEF 演示已提交但**不在用户安装的 1.7.5 里**" |

**文件系统取证**：部署版 `_internal\app\` 下**有** `material_library.py`、`gpu_pref.py`（同类 `_import_app` 动态导入且已登记），**独独没有** `lattice.py` 与 `diff_inp.py`；`base_library.zip` 内亦无 `lattice`/`diff_inp` 字样。
⇒ **`_keep_py` 补 `diff_inp.py` 是必需的**（正对应上面那个 500）；**补 `lattice.py` 属"多补不害"**（实机显示它另有一条可导入路径，但显式登记能让行为不依赖隐式路径）。

⚠️ **仍需重打包后复验**：本批修复**不在部署版里**，故上表数字描述的是**旧包**。要确认修好，须重打包后重跑本节（预期 `/api/diff-inp` 转 200、`/api/source-demo-sample` 出现并 200）。

### 批次 0 · 先验证一条悬而未决的 P0 候选（**只需 1 次请求，2 分钟**）

**TD-02**：打包版可能无法 import `lattice` / `diff_inp`（`_import_app()` 走顶层 `__import__`，而 spec 白名单原先没有这两个文件）。

```powershell
# 1) 起部署版 sidecar（不弹 GUI）
Start-Process -FilePath "D:\MCNP\MCNP输入卡生成器\python.exe" -ArgumentList "-u","backend\mcnp_bridge.py" -WorkingDirectory "D:\MCNP\MCNP输入卡生成器"
Start-Sleep -Seconds 8

# 2) 打四个只读请求，记状态码
foreach ($p in @("lattice-extent","preview-lattice","validate-lattice-surfaces","diff-inp")) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/$p" -Method POST -ContentType "application/json" -Body "{}" -TimeoutSec 10 -UseBasicParsing
    "$p => $($r.StatusCode)"
  } catch { "$p => $($_.Exception.Response.StatusCode.value__)" }
}
```

| 结果 | 含义 | 处置 |
| :--- | :--- | :--- |
| 全部 200/400（非 500） | 打包版能 import | TD-02 结案为"机制债"，本次已顺手把 `lattice.py`/`diff_inp.py` 补进白名单 |
| **任一 500** | **确认是真缺口** | 本次修复已补白名单（`gui/mcnp_sidecar.spec:30`）+ 需在下次打包后的冒烟里复验 |

⚠️ 注意：**这份清单跑的是"当前已部署的 1.7.5"**，它**不含本次修复**。所以它只能证明"旧包有没有这个问题"；要验证"修好了没有"，得等重新打包后（见 §4）。

---

## 2. 后端门禁（Python）

```powershell
# 建议先跑小范围（快，先暴露明显的坏）
python -m pytest tests/unit/test_distribution_sampler.py tests/unit/test_distributions.py tests/unit/test_lattice.py -q
```
**预期**：全绿。重点看三件事：
1. **`test_distribution_sampler.py` 新增 4 个用例**（`test_ds_real_parse_path_q_l_h_t` / `test_ds_s_real_parse_path_index_not_shifted` / `test_ds_var_form_keeps_param_and_data`）—— 它们走**真实解析路径**，是 TD-03 的回归锁。
2. `test_distributions.py::test_parse_sb_ds` 仍应通过（`DS2 S ERG 3 4` → `param="ERG"`、`distributionIds=["3","4"]`）。
3. `test_lattice.py` 的 hex golden 用例**不能 skip** —— 本次把两处静默 `continue` 改成了 `assert`（`:678` 与 `:829`）。若这里红了，说明 golden 的 hex 期望值陈旧，需要重算写盘（不是代码坏了）。

```powershell
# 再跑全量（会慢；务必加超时）
python -m pytest tests -q
```
**预期**：全绿。**特别关注 `skipped` 数** —— 审计里最担心的"隐藏 skip"就在这里。若出现 `skipped > 0`，请把 skip 的用例名贴给我，我判断是否属"静默失效"。

⚠️ 契约闸门 `tests/integration/test_api_contract.py` 走真实 HTTP → **再确认一次 5001 空闲**（§0.1）。

---

## 3. 前端门禁（TypeScript / Vite）

```powershell
cd gui

# 3.1 先跑新增的类型检查（本次修复的核心产物之一）
npm run typecheck
```
**预期**：`tsc --noEmit`（查 `src/`）应 EXIT 0；`tsc -p tsconfig.test.json --noEmit`（查 `src/` + `test/`）**首次运行大概率会报一批测试文件的类型错误** —— 这是**预期内的**，因为审计发现这 75 个测试文件从来没被类型检查覆盖过（TD-17）。
> 处置口径：**把报错清单贴给我**，我按"真错 vs 测试写法宽松"分类；不要因为红就回退 `tsconfig.test.json` —— 那等于放弃这块盲区的治理。

```powershell
# 3.2 单测（关注 skipped 数）
npx vitest run --reporter=basic

# 3.3 构建
npx vite build
```

**重点看**：
- `gui/test/latticeInstances.test.ts` 的跨语言 golden 用例**必须真跑**（本次已把 `it.skipIf` 换成硬断言 `expect(hasGolden).toBe(true)`）→ 若出现 skip 或红，说明 golden 段名/结构漂移了（TD-06）。
- `gui/test/volume/colorize.test.ts` 的计时断言已改（TD-18）→ 不应再出现"偶发红、隔离单跑绿"。
- 新增的 `cellClosure.test.ts` / `useCellClosure` 测试（TD-30）应存在且绿。

---

## 4. 修复是否"生效到用户手上"（发布链路）

⚠️ **本次修复只改了源码，没有打包**。用户当前安装的 1.7.5 **不含**任何本次修复，也**不含** SDEF 源粒子演示（该功能已提交未打包）。

要真正交付，必须走 `docs/手动打包方法.md` 的手动链路：
```
vite build → PyInstaller sidecar → 复制 dist/python → src-tauri/binaries → tauri build
→ ⚠️ 6.2 时效校验（必做，每次命中）→ 杀进程 → 部署 D:\MCNP\MCNP输入卡生成器 → 冒烟
```

**打包前必须过的新增冒烟项**（审计 TD-02/TD-03 的产物）：
1. `/api/diff-inp` 200（白名单已补 `diff_inp.py`）
2. `/api/lattice-extent` 200（白名单已补 `lattice.py`）
3. `/api/source-demo-sample` 200（SDEF 演示，本次修了 DS 键错配）
4. `_internal\app\diff_inp.py` 与 `_internal\app\lattice.py` **都在**（白名单生效的直接证据）

---

## 5. 如果测试红了怎么办

**先分类，再改**（审计里反复踩过的坑，别重复）：

| 症状 | 大概率原因 | 处置 |
| :--- | :--- | :--- |
| 新端点 404/500，且 traceback 行号与当前文件**对不上** | **5001 被旧进程劫持** | 回 §0.1 杀进程重跑，**不要改代码** |
| `unknown option: --timeout` | 没装 pytest-timeout | 去掉该参数 |
| `test_lattice.py` hex 断言红 | golden hex 期望值陈旧 | 重算 golden（唯一写盘人是前端生成器），不是代码 bug |
| `tsc -p tsconfig.test.json` 大量红 | 测试文件从未被类型检查过（TD-17） | 把清单给我分类，逐个处理 |
| vitest 出现 skipped | 静默失效（TD-06 主题） | 把用例名给我 |

---

## 6. 本次修复的"诚实边界"（请勿高估）

1. ~~**所有改动都未经运行验证** —— 修复者与审计者都没有 shell。~~ → **2026-09-10 已解除**：接手方**有 shell**，本清单**已全部执行**，见 §7。
2. **静态自检的覆盖范围**：改了哪些文件、有没有残留引用、import 是否闭合、api.yaml ↔ handlers 是否同删 —— 这些查过了；**运行时行为、类型错误、测试红绿一律没查**。→ **已由 §7 补齐。**
3. **未做的事**（有意留到后续批次，理由已写进报告）：TD-19（214 处 `any` 的类型重构）—— 无 tsc 可跑时盲改大范围类型风险高于收益。→ **条件已变（tsc 可跑），可列入下一批。**
4. **未访问 `C810.pdf`**：凡是"以 MCNP 权威为准"的语义结论（DS 卡的 `param`/J 起点、SI 字母集），本次只核到"与项目内派生文档 + 代码自述一致"，**没有对 PDF 逐字复核**。TD-03 的 `param` 语义属于这一类 —— 若您手边有 C810.pdf，建议对 `DSn` 卡做一次人工确认（本项目两份派生文档互相矛盾：`app/docs/源分布卡说明.md:175` 写 `DSn S S1…Sk`（无 var），`app/docs/C810_卡片格式详细.md:183` 写 `DS[n] var Dn1…`（有 var））。→ **仍未访问 C810.pdf，此条继续有效。**

---

## 7. 验证执行记录（2026-09-10，接手方**有 shell**）

### 7.1 先决条件（实测）

| 项 | 结果 |
| :--- | :--- |
| 5001 端口 | **空闲**（`Get-NetTCPConnection -LocalPort 5001` 无输出）→ 契约测试结果可信 |
| `pytest-timeout` | **未安装** → 按 §0.2 全程**不加 `--timeout`**，改用外层超时 |
| `npm.ps1` | **被执行策略拦截**（`UnauthorizedAccess`）→ 改用 `npm.cmd` / `npx.cmd` |
| 环境 | Python 3.13.14 / pytest 9.1.1 / node v24.18.0 |

### 7.2 门禁结果（全绿）

| 命令 | 结果 |
| :--- | :--- |
| `python -m pytest tests -q -rs` | **875 passed / 0 failed / 0 skipped**，EXIT 0 |
| `npx tsc --noEmit` | **EXIT 0** |
| `npx tsc -p tsconfig.test.json --noEmit` | **EXIT 0**（首次执行暴露 **35 处**测试类型错误，已全部清偿） |
| `npx vitest run` | **78 files / 625 tests passed / 0 skip**，EXIT 0 |
| `npx vite build` | **EXIT 0**（742 modules；仅 chunk>500kB 提示，非错误） |

**关键核对项**：
- §2 关注的 **`skipped = 0`** —— 审计最担心的"隐藏 skip"**不存在**。
- §3 关注的 `latticeInstances.test.ts` 跨语言 golden **真跑且绿**（`it.skipIf` 已改硬断言）。
- §2/§3 关注的 TD-03 **3 条真实解析路径回归全绿**；`test_distributions.py::test_parse_sb_ds` 绿。
- 上轮"预判会红"的 3 点**全部按期出现且已处置**（`tsconfig.test.json` 类型错误 / `test_sidecar_spec_keep.py` 新建未跑 / `preview3dDeadLog.test.ts` 全树扫描），另**额外抓出 2 个编译级真缺陷**（见 §7.3）。

### 7.3 🔴 跑门禁抓出的 5 个真缺陷（静态审计看不见，全部已修）

| # | 缺陷 | 症状 | 处置 |
| :--- | :--- | :--- | :--- |
| 1 | `app/meshtal/meshtal_cache.py:136` **`IndentationError`**（TD-26 加锁时丢了 `while` 体缩进） | **全量 pytest 在收集阶段中断**（`1 error during collection`）⇒ 一条测试都没跑，"全绿"是假象 | 补回缩进；`compileall app gui tests inputcard_mcp` EXIT 0 确认孤例 |
| 2 | `gui/src/components/CellEditDialog.tsx:174` **多余三元分支 `: null,`**（TS1135） | 该文件**无法编译** | 删多余分支；`tsc --noEmit` EXIT 0 |
| 3 | `app/generator/source_sampler.py:_summarize` **丢弃真实能量** | 单能 δ 分布（`SDEF ERG=14`，粒子恒 14.0）被 `if e_max <= e_min: = 0.0, 1.0` 改成假 `[0,1]` | 改为有有效能量即 `min/max`、无则 `[0,0]`（前端以 `min===max` 判「无能量」） |
| 4 | `tests/unit/test_sidecar_spec_keep.py:_parse_hidden` **正则静默丢内容** | 同一 spec 上 `re.findall(r'"([^"]+)"', text)` 返回 74 项且丢 `models.py`/`meshtal`/`generator`/`docs`；逐引号配对扫描返回 76 对且四者俱全 | 改用显式配对扫描（ASCII 双引号位置逐对切片） |
| 5 | `gui/mcnp_sidecar.spec` `_keep_py` **误列 `_cross_section_helper.py`** | 该文件在 `gui/backend/` 不在 `app/`（spec 另有一段从 GUI_BACKEND 取它）⇒ TD-34 闸门报"spec 与源码漂移" | 删除该条 + 加注释指路 |

> **教训（建议固化进 §6 踩坑）**：**编译级缺陷只有"真的跑一次"才能发现** —— 上述 #1/#2 都是"文件根本跑不起来/编不过"，任何静态审计（哪怕再仔细）都会漏。**"没有 shell 的修复批次"其交付状态必须标注为"未验证"，不能计入完成。**

### 7.4 本轮新增/变更的测试与依赖

- **新增测试**：`sourceAdv.test.ts` 新增 **3 例 TD-23 迁移回归**（旧 `sdefRawText` → `adv.sdef_distributions`）。
- **新依赖（已获用户批准）**：`@types/node@^22.20.2`（devDependency，不影响运行时/打包体积）—— 供 4 个测试文件的 `node:fs/url/path/crypto` 类型（TD-17 盲区的 10 处错误）。
- **类型定义放宽 3 处**（行为等价）：`CellEditDialog.CellData.fill_grid` / `DeckContext.CellData.fill_grid` 改可选、`CycleCellLike.fill_grid` 加 `| null`。

### 7.5 仍未验证 / 待办

1. **TD-02 / TD-03 是否真修好 → 必须重打包后冒烟**（§1 的只读请求验证的是**当前已部署的 1.7.5，不含本批修复**）。按 §4 走：`/api/diff-inp`、`/api/lattice-extent`、`/api/source-demo-sample` 均 200，且 `_internal\app\diff_inp.py`、`lattice.py` 都在。
2. **`C810.pdf` 仍未人工核对**（§6.4 继续有效）—— 尤其 `DSn` 卡的 `param`/J 起点语义。
3. ~~**TD-35（P2）**：`app/generator/inp_generator.py:664` 对 POS_VEC 仍发 C810 非法的 `SI{di} V`~~ → **已修（2026-09-10，用户裁决"本批修"）**：改为一律发合法 `L`；解析侧保留 `V` 容忍以兼容**旧输入卡**。全量 pytest **875 passed**（R1 不动点 / R4 kitchen-sink 字节断言**未回归**），仅 `test_generator_multi_source.py:75` 一处旧断言随修。
4. **TD-19**（214 处 `any`）条件已具备（tsc 可跑），可列入下一批。

---

## 8. 源演示「看不见栅元」根因二批（2026-09-11，用户实测 Practice3 热室卡）

> **背景**：`a255a3f`（S1.0c）修完"cells 未传几何 + CEL AST 未转换"后，交接文档判定为"待用户终验"。
> **2026-09-11 用用户提供的真实卡 `Practice3 (3).TXT`（热室屏蔽模型：14 栅元 / 6 材料 / SDEF 位置用 D2·D3·D4 分布给出）实跑浏览器端，现象依旧**：
> 演示源窗口只有一坨蓝色方块点精灵，「显示几何外壳」已勾选也**完全看不到栅元轮廓** ⇒ **存在第三个真 bug**（上一轮未发现）。

### 8.1 根因链（5 步；前 4 步实测确证，第 5 步为代码推断）

| # | 位置 | 问题 |
| :-- | :--- | :--- |
| 1 | `gui/backend/api_server.py:1439-1443` | 给 cell 补 camelCase 前端别名时补了 `num`/`surfaces`/`impN`/`impP`/`impE`，**唯独漏 `mat`** |
| 2 | `gui/src/components/SourceTab.tsx:126-138` | `demoCellsForBackend()` 把 `deck.cells`（DeckContext 的 **snake_case** `CellData`）**强断言**成 cellBridge 的 `LocalCellRow`（camelCase）⇒ `localToDeckCells` 读 `c.cell.mat` 得 `undefined` ⇒ `material=""`。`num`/`surfaces` 因后端恰好补了同名别名而侥幸可用，**掩盖了这个类型谎言** |
| 3 | `gui/src/utils/materialColors.ts:11-14` | `getMatColor("")`：`parseInt("")` 为 NaN，而 `!NaN` 为真 ⇒ 返回 **`"transparent"`** |
| 4 | `gui/src/three/cellMaterial.ts:35-39` | `buildCellMaterial` 以 `color === "transparent"` 判定**真空 M0** ⇒ `{opacity: 0}` ⇒ **13 个外壳全部全透明** |
| 5 | `gui/src/source/SourceDemoRenderer.ts:243` + `gui/src/volume/alignWorld.ts:104-115` | 取景复用了 `computeFramingBox` 的 `VOLUME_FRAMING_RATIO = 0.25` 规则：粒子盒最大边 30 ÷ 并集最大边 528 ≈ **0.057 < 0.25** ⇒ **只按粒子盒取景**。该规则是为**体积窗口**设计的（网格层 ≪ 模型时聚焦网格层），而"**源在屏蔽体内部**"恰是演示源的常态 ⇒ 即便外壳不透明也会落在视野外 |

### 8.2 处置（5 文件）

| 文件 | 改动 |
| :--- | :--- |
| `gui/backend/api_server.py` | 补 `cell["mat"] = cell.get("material", "")` |
| `gui/src/components/SourceTab.tsx` | `demoCellsForBackend()` 改为直接读 deck 的 snake_case 字段（**删掉 `as LocalCellRow[]` 类型谎言**）；顺带过滤 `kind:"raw"` 条件行（旧实现会造出 `number=0` 的幽灵栅元） |
| `gui/src/utils/materialColors.ts` | `getMatColor` 区分「材料号缺失/非法 → 中性灰 `#888888`」与「M0 真空 → `transparent`」 |
| `gui/src/source/SourceDemoRenderer.ts` | ① 外壳颜色按**栅元号**匹配（原实现恒用 `cellViews[0]` ⇒ 多材料全同色）；② 取景改 `unionBoxes`（外壳优先），不再复用 `computeFramingBox` |
| `gui/src/ptrac/PtracRenderer.ts` | **同类缺陷同批修**：`PtracRenderer.ts:253` 同样误用 `computeFramingBox` ⇒ 径迹落在屏蔽体内时外壳被挤出视野；改为一律用 `union`（径迹为空时 `boxes` 只含外壳，天然退化为"只框外壳"） |

> `computeFramingBox` / `VOLUME_FRAMING_RATIO` **本身未改动** ⇒ 体积窗口语义与其 3 个测试文件（`framingBox` / `cameraSceneAlign` / `volumeLayer`）原样保留、全绿。

### 8.3 门禁（改后实跑，全绿）

| 命令 | 结果 |
| :--- | :--- |
| `python -m pytest tests -q -rs` | **875 passed / 0 failed / 0 skipped**，EXIT 0 |
| `tsc --noEmit` / `tsc -p tsconfig.test.json --noEmit` | 两档 **EXIT 0** |
| `vitest run` | **78 files / 625 tests passed / 0 skip**，EXIT 0 |
| `vite build` | **EXIT 0** |
| `compileall app gui tests` | **EXIT 0** |

**先决条件**：跑 pytest 前先停掉占用 5001 的源码版后端（契约测试需端口空闲，§0.1 / `PROJECT_MEMORY` §6 坑 1），跑完重启为**新代码**。

### 8.4 浏览器端视觉复验（2026-09-11，本项目首次具备"看图判读"能力）

| 项 | 修前 | 修后 |
| :--- | :--- | :--- |
| 演示源窗口几何外壳 | **完全不可见**（一坨蓝色方块） | **完整可见**：热室立方体 + 内部空腔 + 盖板圆盘 + 观察孔圆柱，多材料配色正常 |
| SourceTab 请求体 `material` | 14/14 全为 `""` | `"1"/"2"/"2"/"3"/"4"`（且 14/14 带非空 `surface_expr`） |
| 500 粒子空间分布 | — | x∈[-7.480, 7.413]⊂[-7.5, 7.5]、y∈[-9.973, 9.930]⊂[-10, 10]、z∈[50.031, 79.893]⊂[50, 80]；`allParticlesInsideSourceBox = true`；跨度 14.89×19.90×29.86 ≈ 源区 15×20×30 |
| PTRAC 3D 径迹窗口 | （同源缺陷） | **外壳可见**（样本径迹 (101.7, 94.66, 143.87) 落在热室内，正是旧规则失效的场景） |

**取证方法**（可复用，全程**零新依赖**）：headless Edge（`--headless=new --remote-debugging-port=9222` + SwiftShader 软件渲染）+ node 24 **内置 `WebSocket`** 直连 CDP 自写驱动（置于仓库外 `D:\MCNP\_agent_probe\`，不污染仓库）；页面加载**前**用 `Page.addScriptToEvaluateOnNewDocument` 注入 fetch 钩子，抓真实请求体与响应。
> **三个坑（本次实测踩到，已固化进 `PROJECT_MEMORY` §6）**：① `alert()` 在 headless 里**永久冻结渲染进程**（导入成功必弹）⇒ 必须在**同一 CDP 会话内**自动接受；② 导航到**含相同 hash 的同一 URL 不会重新加载文档** ⇒ 假"重载"，须用 `Page.reload`；③ PowerShell 调原生程序时**空字符串参数被丢弃** ⇒ 位置参数错位（曾误在仓库根生成垃圾截图文件，已删）。

### 8.5 用户人工验收反馈修复（S1.0d-2，同日）

**用户人工验收原话**："我能看到你把粒子的源头做出来了，但粒子源头还是一张张蓝色方块，**无法看到粒子的方向的线条**"。

**查出两个新 bug（均由 §8.2 的取景改动牵出）**：

| # | 问题 | 量化 |
| :-- | :--- | :--- |
| 1 | 方向线长度是**世界空间固定值** ⇒ 被"外壳优先"取景缩没 | `arrowLen = 粒子跨度对角线 × 0.03` = 39.05 × 0.03 = **1.17**；取景盒（热室）对角线 ≈ **914** ⇒ 在 ~700px 画面上仅 **约 1px**（修前取景只框粒子盒，1.17 ≈ 27px，故那时可见 —— **取景修复牵出的回归**） |
| 2 | **「方向线长度」滑杆完全无效** | `setDirectionLength(scale)` 只做 `directionScale = scale; markDirty();`，而 `arrowLen` **仅在 `setParticles` 里用过一次** ⇒ 拖动不产生任何变化（滑杆范围 0.2~5） |

**修法**（`gui/src/source/SourceDemoRenderer.ts`，+86/−11）：方向线长度改为**屏幕空间恒定** ——
`len = 2 × 相机到 target 距离 × tan(fov/2) × 0.03 × 滑杆倍率`，由 `controls` 的 change 事件驱动实时重算（长度变化 <0.5% 去抖，避免拖动时频繁重建几何）；`setDirectionLength` 改为调用重建函数 ⇒ **滑杆真正生效**。新增 `captureDirectionAnchors()` 缓存"出生点 + 单位方向"，缩放时只重算终点。

**复验（截图三连，同一窗口）**：

| 场景 | 结果 |
| :--- | :--- |
| 全局视图（滑杆 100%） | **方向线清晰可见**（放射状星芒，约 25px），不再被取景缩没 |
| 放大 20 档 | 线长约 40–50px，**未爆炸**（若仍是世界空间固定长度，此处应约 470px）⇒ 屏幕空间恒定成立 |
| 滑杆 100% → 500% | 线长肉眼明显拉长（约 40px → 约 200px）⇒ **滑杆确认生效** |

**门禁**：tsc 两档 **EXIT 0**、vitest **78 files / 625/0**、vite build **EXIT 0**、compileall **EXIT 0**。本批**纯前端**（仅 `SourceDemoRenderer.ts`）⇒ 上节 pytest 875/0/0 不受影响，未重跑。

**测试盲区（教训）**：`gui/test` 下**没有任何 `SourceDemoRenderer` 的测试**（grep `SourceDemoRenderer|setDirectionLength|arrowLen` **零命中**）⇒ "滑杆无效"能长期存活。该渲染器目前**只有端到端视觉验证能覆盖**。

**仍未处理（待用户裁决）**：粒子仍是 `THREE.Points` **点精灵（方块）**、永远面向摄像头。交接文档 §2.4#1 判定"改小球属**视觉设计变更**，动手前先问用户"——本次已问，等裁决。

> **取证操作再踩一坑**（补进 `PROJECT_MEMORY` §6 第 ③ 条）：除"空字符串参数被丢弃"外，**用 `-` 当占位符也会生成名为 `-` 的文件**（本次在仓库根误生成 86KB 截图，已删）。驱动已改为 `outPng !== '-'` 才截图。

### 8.6 粒子圆点化 + SDEF 能量非正值诊断（S1.0d-3，同日）

**用户裁决**："换成圆形贴图点（改动最小）"。

**改动**（`gui/src/source/SourceDemoRenderer.ts`）：新增模块级单例 `getDotTexture()`（64² canvas 径向渐变圆 + `PointsMaterial.alphaTest = 0.5`），把 `THREE.Points` 默认的**轴对齐方块**渲成**圆点**。**零新依赖、零性能代价，且保住屏幕空间可见性**（区别于 `InstancedMesh` 小球：后者是真实世界尺寸，在"外壳优先"取景下只有几像素，反而更难看见）。jsdom 无 canvas 时返回 null ⇒ 静默降级为方块。

**★ 顺带查清两件事**（详见 `PROJECT_MEMORY` S1.0d-3 与 `docs/CHANGELOG.md`）：

1. **`C810.pdf` 首次访问成功**（推进 §4 待办 5）：本机 **PyMuPDF（`fitz`）已安装**，**零新依赖**即可读这份 1001 页权威手册。SI/SP 权威定义（**PDF 页 746-747 / 印刷页 3-63**）：SI = 自变量值、SP = 对应概率；**H（默认）下 SI 是分箱边界、SP 首个数值项必须为 0（占位符）**；抽样 = 选分箱后**箱内均匀**。

2. **用户报"粒子颜色不对"的根因定案**：卡里 `si1 -2 1` + `sp1 0 1` 按 C810 即**能量在 [-2, 1] MeV 均匀**（**定义范围的是 `si1`；`sp1` 的 `0` 是占位符**）⇒ 约 2/3 粒子负能量 → `app/generator/source_sampler.py:431` 的 `p["energy"] > 0` 过滤使 `energyRange` 失真为 `[0.0037, 0.9973]` → 前端 `normalizeEnergy01` 钳到最浅色 ⇒ **颜色层次塌成一片近白**。

**A/B 实证**（按用户要求把 `si1 -2 1` 改为 `si1 0 2`，**只改注入副本，用户原卡 `E:\download\Practice3 (3).TXT` 未动**）：

| 指标 | 原卡 `si1 -2 1` | 变体 `si1 0 2` |
| :--- | :--- | :--- |
| 负能量粒子数 | **约 2/3** | **0** |
| `energyRange` | `[0.0037, 0.9973]`（失真） | `[0.0002, 1.9954]`（与真实一致） |
| 颜色参数 t 的 10 桶分布 | 2/3 挤在第 0 桶 | **`[49,48,50,43,55,56,54,45,51,49]` 均匀铺满** |
| 观感 | 一片接近白色 | **完整浅蓝→深蓝层次** |

⇒ **程序抽样符合 C810，无 bug**；缺口是**缺"SDEF 能量分布可能产生非正值"的校验/提示**，`energyRange` 的 `>0` 过滤是症状补丁。**待用户裁决**（加校验 / 改卡）。

**粒子类型无问题**：卡里 `sdef … par=1` 即粒子类型 = 1；后端实测返回 `particle:"n"`、面板"中子 500 / 光子 0 / 电子 0"。

**门禁**：tsc 两档 **EXIT 0**、vitest **78 files / 625/0**、vite build **EXIT 0**（纯前端）。

### 8.7 三态表述

**已改源码 ✅ / 未提交 ❌ / 未打包 ❌** —— 部署版仍不含 `a255a3f` 与本批修复。
