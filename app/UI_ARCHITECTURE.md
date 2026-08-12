# UI 架构说明（MCNP 输入卡生成器）

> 最后重锚定：2026-08-12（后端 F-A~F-E 缺陷修复重新施工后，全部行号已对当前工作树 Grep 重锚定）
> 适用范围：三层边界 / 启动链路 / import-root / deck JSON 契约 / raw_overrides / 往返保真 / 技术债地图
> 相关契约：`docs/contracts/api.yaml`（OpenAPI 3.0，25 端点）、`docs/contracts/bugfix-f1-f5.md`（F-A~F-H 修复契约）

---

## §1 三层边界图

```
┌─────────────────────────────────────────────────────────────────┐
│ 前端  gui/src/ (React 18 + TypeScript + Vite, dev 端口 1420)     │
│                                                                  │
│   DeckContext.tsx  ←─ 单一权威表单状态（localStorage mcnp_workspace_v1）│
│   dataCollector.ts  表单 → DeckData 收集                          │
│   contract.ts       前端数据类型定义（与 models.py 一一对应）        │
│   useSectionTextMode.ts + sectionConvert.ts   文本↔表单互转深模块    │
│   backend.ts        sidecar 生命周期 + fetch 封装                  │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTP  fetch http://localhost:5001/api/*
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 后端  gui/backend/api_server.py (Python 标准库 http.server)       │
│  端口 5001（api_server.py:33 PORT）                              │
│  _ok/_err 统一信封（524-538）：{"status":"ok|error", ...}         │
│  25 个端点 handler（do_GET/do_POST 同路由）                        │
│  契约：docs/contracts/api.yaml（每 path 带 operationId，漂移闸门）  │
└──────────────┬───────────────────────────────────────────────────┘
               │ 调用
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 引擎  app/ (Python)                                              │
│  models.py            DeckData 聚合根 + 各 section dataclass       │
│  generator/inp_generator.py   INP 生成主引擎                       │
│  generator/banners.py        生成器节头词汇单一事实来源（F-A 新增）   │
│  generator/parsers/          lines→sections→core→validator 解析管线 │
│  generator/validator.py      校验逻辑（validate_all + validate_deck）│
│  旁路：freecad_preview / stl_cross_section / step_importer_geouned │
└─────────────────────────────────────────────────────────────────┘
```

数据流：8 个标签页表单 → `dataCollector.ts` 收成单一 DeckData → 任一生成/解析/校验请求经
HTTP 5001 打给 `api_server.py` → `deck_from_json()` 反序列化成 `models.DeckData` → 引擎
`generate_inp_from_deck()` / `parse_inp_text()` → 响应回前端。

**深模块要点**：前端只与 `api_server.py` 的 25 个端点打交道，从不直接 import 引擎代码；
引擎的模块边界（generator / parsers）内部如何拆分对前端不可见。

---

## §2 启动链路

### 2.1 Tauri sidecar 拉起（生产 / 桌面开发）

1. 前端 `gui/src/utils/backend.ts:8-46 startPythonBackend()` 启动后端。
2. 先探测 `http://localhost:5001/api/xsdir-check`（2s 超时）——若 5001 已有后端在跑则跳过拉起，避免双实例/重复绑定（backend.ts:11-15）。
3. 无响应则经 Tauri shell `Command.sidecar("python", ["-u", "backend/mcnp_bridge.py"])` 拉起 sidecar（backend.ts:16-19）。sidecar 产物名 "python"（`gui/mcnp_sidecar.spec`，PyInstaller），`tauri.conf.json:42` `externalBin: ["python"]`，allowlist shell.scope 声明 sidecar 可执行（tauri.conf.json:17-25）。
4. `mcnp_bridge.py` 负责 sys.path 装配后 `import api_server`（mcnp_bridge.py:21）并 `api_server.main()`，后端常驻监听 5001。
5. 窗口关闭联动：`backend.ts:30-41` 在 `onCloseRequested` 拦截一次关闭 → `stopPythonBackend()` 杀掉后端进程 → Rust `close_window` 命令关窗（走自定义命令而非 `appWindow.close()`，避免缺 window-close feature 时窗口卡住）。

### 2.2 浏览器模式回退（开发调试 / 无 Tauri）

`startPythonBackend()` 全程 try/catch——任何一步失败（非 Tauri 环境、无 sidecar、无 python）只打印
`console.warn("Python backend not available (running in browser mode)")`（backend.ts:43-45），
不抛错。`generateInp` 里 HTTP 桥不可用时回退 mock 输出（backend.ts:65/77），
浏览器模式（`#/preview3d` 等哈希路由）专用于前端 3D 预览调试，不依赖后端能力。

### 2.3 启动顺序纪律

`mcnp_bridge.py:12-19` 在 `import api_server` **之前**完成 sys.path 装配（否则 `from models import ...` 失败）；
`api_server.py:11` 模块级先设 `PYVISTA_OFF_SCREEN=true` 再 import，供 handler 里懒加载的 pyvista 使用——测试与打包都不得 import 顺序错乱。

---

## §3 import-root 约定

`app/` 不是标准包根（无 `__init__.py` 于 `app/` 顶层，`app/models.py`、`app/generator/` 平级），
所有代码通过 **sys.path 注入 `app/` 与项目根**来 import：

| 位置 | 注入逻辑 | 用途 |
| :--- | :--- | :--- |
| `api_server.py:17-23` | `APP_DIR = PROJECT_DIR/app`、`PROJECT_DIR = ../..` 双入 sys.path | 源码开发：`from models import ...`、`from generator.inp_generator import ...`、`from xsdir_db import ...` |
| `mcnp_bridge.py:12-19` | 候选路径：`_here`（backend/）、`_here/../../app`（源码）、`_here/app`（PyInstaller `_internal` 布局） | 打包后 backend 与 app 平级，保证 `import api_server` 与后端内部 `from models` 都能解析 |
| `tests/` 各文件 | `PROJECT_DIR` 由 `Path(__file__).resolve().parent.parent.parent` 推导并加入 sys.path（test_tech_debt.py:17） | 测试直接 `from app.models`、`from app.generator...` 导入 |

**约定**：引擎代码一律 `from app.models import ...` / `from .banners import ...`（相对导入，inp_generator.py:8-10）；
测试代码 `from app.generator.inp_generator import ...`（以项目根为锚，绝对导入）。
`docs/contracts/api.yaml` 的漂移闸门（tests/integration/test_api_contract.py）用 AST 读 `api_server.py`
handlers 字典，与 import-root 无关但同受 sys.path 影响。

---

## §4 deck JSON 契约总表

前端 `DeckContext`（DeckData）↔ 后端 `models.DeckData`（models.py:420）双向映射。
契约细节见 `docs/contracts/api.yaml` 的 `/api/generate` requestBody 与 `/api/parse-inp` 响应。

| deck 键 | 后端类型 | 说明 / 字段映射 |
| :--- | :--- | :--- |
| `basic` | `BasicSettings`（models.py:147） | title / mode_n/p/e/h/he/d/t/a / nps / ctme / act / print_pr / phys_fis |
| `surfaces` | `str` | 曲面卡**原始文本**（pass-through，生成/解析都走文本） |
| `tr_cards` | `str` | TR 变换卡**原始文本**（数据卡段，TR_BANNER 之后原样重放） |
| `cells` | `list[CellRow]`（models.py:59） | 判别联合：`kind=="cell"` 嵌 CellData（models.py:22）；`kind=="raw"` 用 text（#ifdef/#else/#endif 原样行） |
| `materials` | `list[MaterialData]`（models.py:88） | **前端字段名 `nuclides` ↔ 后端 `rows`**（api_server 双向映射）；材料卡只含 ZAID+份额，**不含密度**（密度在栅元卡）；判别联合 `kind=="nuclide"|"raw"`；options 在 M 头行（F-D 修复后）；mt_card 热中子卡 |
| `sources` | `list[SourceData]`（models.py:108） | **前端 `prob` ↔ 后端 `probability`**；par/erg/pos_xyz/wgt/dir_/cel/tme/vec/axs/rad/ext/sur/nrm/tr/ccc/ara/rate |
| `tallies` | `list[TallyDef]` | **前端 `particle` 空格串 ↔ 后端 `particles` list**；`enableEn ↔ generate_en`、`enableTn ↔ generate_tn`；type(F1-F8)/number/params/fn_prefix/number_suffix |
| `tally` | `TallySettings`（models.py:203） | En/T0/Tn/CUT 网格：e_min/e_max/e_bins/e_log/e_custom_text/e_cards_text；t0_*；cut_*_t/e/raw/wc1/wc2/swtm |
| `adv` | `AdvancedSettings`（models.py:297） | other_cards（原样）；phys_n/p/e/h/he_*；sdef_* 字段；**sdef_raw_text（SI/SP 序列化回退）**；**sdef_distributions（结构化 JSON，非空时优先于 sdef_raw_text）**；kcode_*（8 参 + ksrc_points JSON 串）；ssw_*/ssr_*；hsrc_* |
| `grids` | `Record<string, GridValue>` | E0/En/T0/Tn 网格**单一权威**（前端 gridState.ts，prefix "e"\|"t"\|"e25"\|"t85"...） |
| `raw_overrides` | `dict[str, str]` | **独立参数，非 DeckData 字段**——api_server 必须单独传给生成器（api_server.py:550-551 `data.get("raw_overrides") or {}`），见 §5 |
| `sourceMode` | `str` | parse 产物：`fixed`/`sdef`/`kcode`/`surface` |
| `textMode` | `dict[section, bool]` | 前端内存态：该 section 是否处于文本模式（不进后端 deck） |
| `_warnings` | `list[str]` | parse 产物的警告收集（api_server 透传） |

**判别联合贯穿三层**：CellRow（cell/raw）与 MaterialRow（nuclide/raw）在 models.py 定义，
api_server.py 序列化为 `{kind, ...}` JSON，DeckContext.tsx 用可辨识联合类型消费——三层语义一致。

---

## §5 raw_overrides 机制

### 5.1 契约（前端只写 4 key）

`/api/generate` 的 `raw_overrides` 入参（`docs/contracts/api.yaml`）：

| key | 含义 | 覆盖对象 |
| :--- | :--- | :--- |
| `cells` | 栅元卡原始文本 | `_generate_cells` 的产出 |
| `materials` | 材料卡原始文本 | `_generate_materials` 的产出 |
| `tally` | 计数卡原始文本 | `_generate_tallies` 的产出 |
| `sdef` | 源定义原始文本 | `_generate_sdef`/`_generate_distribution_sdef`/`_generate_kcode` 的产出 |

后端另支持 `surfaces` / `phys` / `e0` / `cut`（UI 类型遗留，前端不写）；`DeckData` 无 raw_overrides 字段，
api_server 生成路径单独传参（api_server.py:550-551）。

**空串 = 无覆盖**：守卫用 `(overrides.get(key) or "").strip()`，空/缺省 key 走正常 `_generate_*` 分支。

### 5.2 守卫行号表（P1 F#1 收敛后）

P1 F#1（commit 1488aae）将 8 处复制粘贴守卫收敛为 `_apply_raw_override` 一行调用（inp_generator.py:1149-1161），
判空统一走 `_has_raw_override`（1145）→ `_raw_override_text`（1140，`(overrides.get(key) or "").strip()`，空串=无覆盖语义保留）。
调用点全部在 `generate_inp_from_deck`（inp_generator.py:1163）：

| 调用点行号 | key | banner 常量 | generator 闭包 |
| :--- | :--- | :--- | :--- |
| 1191 | `cells` | RAW_CELL_BANNER | `_generate_cells` + `cell_cards_banner` 节头 |
| 1196 | `surfaces` | RAW_SURF_BANNER | `_generate_surfaces` + `surface_cards_banner` 节头 |
| 1215 | `materials` | RAW_MAT_BANNER | `_generate_materials` |
| 1229 | `sdef` | RAW_SDEF_BANNER | `_sdef_dispatch`（distribution/kcode/surface/fixed 四分支闭包） |
| 1231 | `phys` | RAW_PHYS_BANNER | `_generate_phys` |
| 1234 | `tally` | RAW_TALLY_BANNER | `_generate_tallies` |
| 1237 | `e0` | RAW_E0_BANNER | `_generate_energy_mesh` |
| 1252 | `cut` | RAW_CUT_BANNER | `_generate_cut` |

grep 归零检查：`grep -n "overrides.get" inp_generator.py` 仅命中 `_raw_override_text`（1142 行）。

### 5.3 raw_tally 门控语义（不一致变体，P1 保留为特性）

P1 F#1 收敛后，En/T0/Tn 门控不再有第 9 处守卫的"判 raw_tally 而非当前 key"形态，统一为
`_has_raw_override(overrides, "tally")`（inp_generator.py:1145）——**判的仍是 tally key，非当前 override key**：

- tally 有覆盖时（`_has_raw_override(overrides, "tally")` 为真），**抑制 En 分计数能量箱（1241 `if not _has_raw_override(overrides, "tally"):`）与 T0/Tn 时间网格（1246）的自动生成**——
  即"手写 tally 文本时，不要自动补 En/T0/Tn 卡，让用户文本说了算"。
- e0 / cut / 其它 override 不触发该门控（test_e0_override_does_NOT_suppress_en_t0_tn / test_cut_override_does_not_affect_en_t0_tn pin）。

该门控是 `review_findings.json` F#1 记载的历史"不一致变体"，P1 收敛时**语义一字未动**（判 tally key 是特性不是 bug，
契约 bugfix-f1-f5.md §7 / p1-refactor.md §5 明确禁止凭直觉"修正"为判当前 key）。

### 5.4 覆盖行为的注意点

- raw 文本绕过所有格式/校验（80 列换行 `_wrap_long_lines` 除外——整段拼回后统一走 1010 行）与 MCNP 语法校验，
  坏串静默失败（F#1 leaky bypass，P1 收敛时补契约校验）。
- override 段各自打 `RAW_*_BANNER` 节头；banners.py 的 `is_generator_banner` 能识别这些头，
  解析器在 split_sections 拦截（sections.py:214），覆盖文本 round-trip 回读时不会污染结构化字段。

---

## §6 往返保真边界

### 6.1 R1 不动点（正确性红线）

**定义**（tests/integration/test_roundtrip.py:30-35）：`g2 = generate(parse(generate(d)))`，
断言 `g2 == generate(d)` **字节相等**（从第二代起稳定；不要求 parse(手写 INP) 原样 == INP）。

| 测试 | 状态（P1 F#5/F#6 后） | 说明 |
| :--- | :--- | :--- |
| `test_r1_fixed_point_minimal_deck` | 绿 | 最小 deck 第二代起稳定 |
| `test_r1_fixed_point_sample_prob41c` / `avr13` | 绿 | vendor 样例第二代起稳定 |
| `test_smoke_r1_fixed_point[*]`（3 参） | 绿 | 冒烟 |
| `test_r1_output_does_not_grow_unboundedly` | 绿 | kitchen-sink 增长探针（不膨胀） |
| `test_r1_fixed_point_kitchen_sink` | **绿（P1 已修）** | 多源 SDEF 漂移已消除（F#5/F#6），见 §6.4 |
| `test_r4_kitchen_sink_full_roundtrip` | **绿（P1 已修）** | 同根因已消除 |

R1 成立的机制（F-A 方案 C 修复，2026-08-12；P1 F#5/F#6 补多源漂移）：
- 生成器节头词汇冻结在 `banners.py`（单一事实来源），生成器禁止内联节头字符串；
- 解析器 `split_sections` 的 C 注释分支（sections.py:210-216）用 `is_generator_banner` **精确拦截**生成器节头，
  节头不进 cell_lines/surf_lines/data_lines——不污染 cell.comment、不进 deck.surfaces、不进 other_cards，逐代膨胀停止；
- F-E 剥 `&` 续行符（lines.py:142-150/153-161 + `_rstrip_amp` flush）保证字段干净，二次生成拆分点与一次一致。
- **R1 测试套件是词汇漂移的兜底网**：banner 文案一改 → R1 立刻 RED，不会静默。

### 6.2 原始文本兜底字段（不走结构化 round-trip）

以下字段以"原始文本"形态承载，parse/generate 全程逐字节保留，是保真的主要机制：

| 字段 | 承载位置 | 保真机制 |
| :--- | :--- | :--- |
| `deck.surfaces` | 曲面段 verbatim | `_generate_surfaces`（inp_generator.py:100-103）pass-through，`parse_surfaces` 整段 verbatim 回放 |
| `deck.tr_cards` | 数据卡 TR 段 | TR_BANNER 后原样重放（1101-1105） |
| `adv.other_cards` | 数据卡最末尾 | `_generate_other_cards` 原样输出（1176-1178） |
| `adv.sdef_raw_text` | SI/SP 序列化文本 | 结构化 sdef_distributions 为空时的回退路径，原样重发 |
| `cell`/`material` 的 `raw` 行 | 判别联合 text | #ifdef/#else/#endif 条件行独立成行，不参与校验/格式化 |
| `adv.ksrc_points` | KSRC JSON 串 | F-F 修复后数值坐标显式 str 强转（inp_generator.py:639-641） |

### 6.3 缺陷修复带来的保真行为变化（相对旧版）

| 修复 | 位置 | 行为变化 |
| :--- | :--- | :--- |
| F-A 节头拦截 | 新增 `banners.py`；sections.py:210-216 | 生成器节头不再被解析器吸收；用户手写 C 注释仍按原语义吸收（不误伤） |
| F-B CellRow 解包 | validator.py:249-259 `_unwrap_cells` | `validate_deck` 对含栅元 deck 不再抛 AttributeError；raw 条件行跳过校验 |
| F-C 多粒子计数 | core.py:704-786 `parse_f_tally` | `F4:N,P` 逗号设计符可解析，多粒子计数不再进 other_cards（722 `_PARTICLE_RE`、762 逗号展开） |
| F-D options 上移 | inp_generator.py `_generate_materials` | `MaterialData.options`（nlib= 等）在 M 头行输出，不再追加到末行尾（raw 条件行不被污染） |
| F-E 剥 `&` | lines.py `normalize_lines` | 续行合并/flush 前剥离尾 `&`，surface_expr/vec 等字段不再带续行符污染（先 strip_comment 再剥，不误伤 `$` 注释内字面 `&`） |
| F-H 小写 m | sections.py:79-81 `_is_cell_line` | `3 m1 -1.0 -3` 大小写不敏感识别为栅元行 |

### 6.4 多源 ↔ 分布表示字节稳定（P1 F#5/F#6 新增）

P1 F#5/F#6（commits e404172 + 018ced5）使多源生成与分布回放两种表示**逐字节一致**（g1 == g2 恒定），
消除 bugfix-f1-f5.md §0.5.5 复合根因 #2-#5 + SI 值空格归一化：

| 根因 | 消除方案 | 落点（重锚定后） |
| :--- | :--- | :--- |
| #2 `POS=F D1`→`X=F Y=D1` 逐轴重组 | 分布回放 POS 四态加 F-dist 分支：`_px` 匹配 `^F\d*$` 且 `_py` 为 D 引用且 `_pz` 空 → 原样 `POS={_px} {_py}` | `_generate_distribution_sdef`（inp_generator.py:341-363） |
| #3 `TME=D6`→`TME=0.0` 退标量 | 多源 sdef_extra 去重：`_strip_sdef_extra_dist_keys` 剥离 sdef_extra 中 KEY 属于 dist_names 的 `KEY=` 片段（标量-标量重复不去） | `_build_multi_sdef_parts` + `_strip_sdef_extra_dist_keys`（556） |
| #4 `SI1 V`→`SI1 L` 变型 | `_parse_sisp_structured` SI 类型表加 `"V"` | parsers/core.py:126 |
| #5 分布注释丢失/移位 | `multi_source_comment_banner(n)` 进 banners.py（84）+ `_DYNAMIC_PATTERNS` 加 `^C\s+\d+ sources, probability keyed to D1$`；分布回放 `_multi_source_comment_reemit` 在 D1 键控链存在时重发（保守触发） | banners.py + `_generate_distribution_sdef` |
| SI 值空格归一化 | 多源 SI 卡值全扁平化：每个 value `split()` 拆 token 再 `'  '.join` 全部 token（VEC/AXS/V-向量 `0 0 1` 等与回放字节一致） | `_build_multi_sisp_cards`（577） |
| 字段序不一致 | 统一为 `SDEF_FIELD_SPECS` 序（POS, PAR, ERG, DIR, WGT, CEL, TME, VEC, AXS, RAD, EXT, SUR, NRM, TR, CCC, ARA, RATE），分布回放与多源共用 | `SDEF_FIELD_SPECS`（306）+ `_generate_distribution_sdef` |

关键不变式：**多源 D-index 由 `dist_params` 位置决定**（POS_VEC 恒占 D1），与 SDEF 字段发射序解耦；
`_generate_structured_distributions` 的 `'  '.join`（SI/SP 值双空格）作为回放基准**一字未动**（test_structured_distributions_full pin）。

---

## §7 技术债地图

数据源：`app/generator/review_findings.json`（7 项，全部在 `inp_generator.py`）。**P1 已全部清偿（2026-08-12）**。

| # | 技术债 | 锚点（P1 重锚定后） | pin 状态 | 清偿 commit / 说明 |
| :--- | :--- | :--- | :--- | :--- |
| F#1 | raw_overrides 守卫复制粘贴 8 次 + 不一致变体 | `_apply_raw_override` 调用点 1191/1196/1215/1229/1231/1234/1237/1252；门控 `_has_raw_override(overrides, "tally")` 1241/1246 | **已清偿** | commit 1488aae；收敛为 `_apply_raw_override` 一行调用，tally-key 门控语义保留（test_generator_overrides.py 28/28 绿） |
| F#2 | `_generate_en_cards` 函数内重复 `import re` | — | **已清偿**（P0 期间 Resolved） | 原 567 行局部 import 已移除，仅历史记录 |
| F#3 | 函数内 `import json as _json` + `import sys` + `[E0DBG]` | `_generate_kcode`/`_generate_structured_distributions` 现用模块级 `json` | **已清偿** | commit c774e56；grep `import json as`/`E0DBG`/函数内 `import sys` 全归零；test_f3_* ×2 转绿 |
| F#4 | `_generate_single_source` 两段几乎相同 SDEF 构造 | `_build_sdef_parts(src, include_special)`（247） | **已清偿** | commit 52ca251；输出字节不变（test_generator_sdef.py 全绿 + `test_sdef_single_source_delegates` pin） |
| F#5 | `_generate_multi_source` 145 行混杂 5 个子关注点 | `_collect_source_values`(434) / `_normalize_probabilities`(454) / `_varying_dist_params`(473) / `_build_multi_sdef_parts`(500) / `_build_multi_sisp_cards`(577) | **已清偿** | commits e404172（4a 拆函数）+ 018ced5（4b 漂移）；概率归一早成独立纯函数，kitchen-sink R1/R4 转绿 |
| F#6 | 多源源字段名 3 处枚举 | `SDEF_FIELD_SPECS` 表（306）单源驱动值收集/方差/SI-SP 三处 | **已清偿** | commits e404172 + 018ced5；新增字段 = 表加一行三处自动生效 |
| F#7 | `_generate_basic` 函数内 `from pymcnp import inp` | 模块顶部 8 行 `from pymcnp import inp as pymcnp_inp` | **已清偿** | commit bf0a2c7；导入期 fail-fast，test_f7_* ×2 转绿 |

**终态口径（P1 完成后 2026-08-12）**：全量 pytest = **251 绿 / 0 红**（复跑 ×2 稳定）。
6 红全部转绿 = F#3×2 + F#7×2（技术债）+ kitchen-sink R1/R4×2（漂移）。无断言降级（用例总数 251 不变），无 skip/pass 骗绿。

### 7.1 E0DBG 调试残留（P1 F#3 已清除）

`[E0DBG]` stderr 调试 print（`file=sys.stderr`）与函数内 `import sys` 已在 F#3（commit c774e56）全部删除，
grep `E0DBG` 归零。历史位置（已清除）：

| 文件 | 旧行号 | 内容 |
| :--- | :--- | :--- |
| `parsers/core.py` | 826-827 | `_parse_card_with_continuation` 残留 |
| `parsers/core.py` | 1018-1021 | `parse_data_cards` 的 E0 行调试 |
| `parsers/__init__.py` | 138-140 | `parse_inp_text` 的 e0/t0 调试 |
| `api_server.py` | 608-610 | `_handle_parse_inp` 的 tally e_custom 调试 |

### 7.2 相关辅助注意点

- **AST pin 测试行号不敏感**：tests/integration/test_tech_debt.py 的 F#3/F#7 用 `ast` 扫描"函数内 import"，
  逻辑与行号无关；文件内注释行号已更新为 P1 后现状（见 test_tech_debt.py 文件头）。
- **kitchen-sink R1/R4 已转绿**：复合根因清单（bugfix-f1-f5.md §0.5.5）第 2-5 项 + SI 值空格归一化已在 P1 F#5/F#6 逐项消除，
  多源生成与分布回放表示字节稳定（见 §6.4）。
- **P1 边界红线遵守情况**：`api.yaml` 漂移闸门保持绿；`gui/backend/api_server.py` 路由表（25 端点）未触碰
  （仅删 F#3 的 `[E0DBG]` print + 函数内 `import sys`）；`_wrap_long_lines` 未动；
  `_generate_structured_distributions` 的 `'  '.join` 未动（test_structured_distributions_full pin 保持）。

---

*维护纪律：任何改动移动本文件引用的行号后，必须 Grep 重锚定再提交；R1 测试套件是 banner 词汇漂移与
保真回归的兜底网（词汇漂移 → R1 RED）。*
