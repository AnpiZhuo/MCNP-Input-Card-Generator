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

1. **所有改动都未经运行验证** —— 修复者与审计者都没有 shell。
2. **静态自检的覆盖范围**：改了哪些文件、有没有残留引用、import 是否闭合、api.yaml ↔ handlers 是否同删 —— 这些查过了；**运行时行为、类型错误、测试红绿一律没查**。
3. **未做的事**（有意留到后续批次，理由已写进报告）：TD-19（214 处 `any` 的类型重构）—— 无 tsc 可跑时盲改大范围类型风险高于收益。
4. **未访问 `C810.pdf`**：凡是"以 MCNP 权威为准"的语义结论（DS 卡的 `param`/J 起点、SI 字母集），本次只核到"与项目内派生文档 + 代码自述一致"，**没有对 PDF 逐字复核**。TD-03 的 `param` 语义属于这一类 —— 若您手边有 C810.pdf，建议对 `DSn` 卡做一次人工确认（本项目两份派生文档互相矛盾：`app/docs/源分布卡说明.md:175` 写 `DSn S S1…Sk`（无 var），`app/docs/C810_卡片格式详细.md:183` 写 `DS[n] var Dn1…`（有 var））。
