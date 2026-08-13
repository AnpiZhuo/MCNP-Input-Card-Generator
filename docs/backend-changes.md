# 后端改动清单 — 引擎缺陷修复 F-A~F-H（M1.4 门禁）

> 施工方：后端 | 分支：`experiment/geouned` | 日期：2026-08-12
> 契约：`docs/contracts/bugfix-f1-f5.md`（F-A 裁决=方案 C，A 主 B 辅；§0.5 上级裁决微调：范围=F-A~F-E，终态 245 绿/6 红）
> 基线：app/ 回滚到干净基线后重新施工；动工前 234 通过 / 17 失败（与权威基线一致）。

## 一、缺陷修复结果

| 缺陷 | 修复结果 | 关联断言（红→绿） |
| :--- | :--- | :--- |
| **F-A** R1 头泄漏 | **修复**（方案 C：新增 `banners.py` 冻结词汇 + `split_sections` 拦截节头 + 生成器各节头改调常量）。契约 §1.2 的 11 词汇之外，实测发现生成器另有多条内联 C 头（`Fission turned off`/`KCODE Criticality`/`KSRC Initial`/`Additional Cards`/raw-mode 头/mesh/Time 等）也在样例上泄漏进 `other_cards`/`mat.comment`/`cell.comment`，已一并纳入 `banners.is_generator_banner`（仍只精确匹配生成器产出形式，用户任意 C 注释零误伤）。 | `test_r1_fixed_point_minimal_deck`、`test_r1_fixed_point_sample_prob41c`、`test_r1_fixed_point_sample_avr13`、`test_smoke_r1_fixed_point[*]`（3）→ **绿**；`test_r1_output_does_not_grow_unboundedly`（kitchen-sink 增长探针）保持绿 |
| **F-B** validate_deck 与 CellRow 不兼容 | **修复**（只改 `validate_deck` 加 `_unwrap_cells` 解包 kind=='cell' 的 CellData，raw 条件行跳过；`validate_all` 签名不动）。 | `test_smoke_validate_deck_does_not_crash[*]`（3）→ **绿** |
| **F-C** 多粒子计数卡丢失 | **修复**（`parse_f_tally` 正则 `([NPEHAS])` 扩为逗号列表 `([NPEHAS](?:,[NPEHAS])*)`，6 处全改；合并/新建分支按逗号展开粒子去空小写；未加外层门）。 | `test_r2_tally_multi_particle_parse_supported` → **绿**；`test_r2_tally_single_particle_survive` 不回归 |
| **F-D** 材料 options 丢失 | **修复**（`_generate_materials` 的 options 上移 M 头行，删除末行尾追加；raw 条件行 `#ifdef/#else/#endif` 仍各自独立成行）。 | `test_r2_material_options_survive` → **绿**；`test_r2_material_rows_and_mt_survive` 不回归 |
| **F-E** & 续行符污染 | **修复**（`parsers/lines.py:normalize_lines`：5 空格缩进合并分支合并前剥离当前缓冲尾 `&`；空行/节边界/循环结束的 flush 统一用 `_rstrip_amp` 先 `strip_comment` 再剥尾 `&`（不误伤 `$` 注释内字面 `&`）。`_wrap_long_lines` 拆分逻辑未动）。**伴生修复**：缩进合并分支原样丢弃续行的 `$` 注释——`_generate_cells` 拆分超 80 列长行时注释落在续行上，被 `normalize_lines` 吞掉，导致 prob41c 的 cell.comment 丢失（F-A 修掉头泄漏后暴露）；已改为当前行无注释时保留续行注释。 | prob41c/avr13/inp24 三个 R1 + 3 样例 R1 由 F-A+F-E 合并转绿；`test_r2_cell_content_fields_survive` / `test_r2_single_source_fields_survive` 不回归 |
| **F-F** ksrc 数值坐标崩溃 | **修复（可选翻新，§0.5.1）**：`_generate_kcode`（634-643）坐标 None 感知 + 显式 `str()` 强转，修复 `json.loads` 数值坐标 `.strip()` 崩溃与 `0 or ""` 吞 0；**未动** 631/673 的 `import json as _json`（F#3，P1）。 | `test_ksrc_numeric_coords_emitted`（原 pin `test_ksrc_numeric_coords_raises` 翻新为正确行为断言）→ **绿**；字符串坐标用例保持绿 |
| **F-G** EFF 裸值静默丢弃 | **修复（可选翻新，§0.5.1）**：`parsers/core.py:_apply_sdef_param` 加 `EFF` 分支走 `sdef_extra`（裸值 `EFF=2` 保留；续值 `EFF=2 5` 因 `_apply_sdef_param` 先应用前缀而天然保留前缀）。 | `test_sdef_simple_eff_bare_value_preserved` / `test_sdef_simple_eff_with_continuation_preserves_prefix`（pin 翻新）→ **绿** |
| **F-H** 小写 m 材料引用不识别 | **修复（可选翻新，§0.5.1）**：`parsers/sections.py:_is_cell_line` 大小写不敏感（`second[0] in "Mm"`），与 `parse_cells` 一致。 | `test_is_cell_line_lowercase_m_reference_detected`（pin 翻新为 `is True`）→ **绿** |

## 二、文件改动明细（行号为本轮施工后 Grep 重锚定）

| 文件 | 改动函数 / 行 |
| :--- | :--- |
| `app/generator/banners.py` | **新增**：24 条精确节头常量 + `cell_cards_banner(n)`/`surface_cards_banner(n)`/energy·time·skipped 构造器 + `is_generator_banner`（`re.IGNORECASE` + 锚定 `$`，动态计数用 7 条正则），生成器与解析器共享的单一事实来源 |
| `app/generator/parsers/sections.py` | `split_sections` C 注释分支最前面加 `is_generator_banner(line)` 拦截（节头不入 cell_lines/surf_lines/data_lines 任一 phase 收集，单一拦截点）；`_is_cell_line` 小写 m（F-H） |
| `app/generator/parsers/lines.py` | 新增 `_rstrip_amp`（先 `strip_comment` 再剥尾 `&`，保留 `$` 注释）；`normalize_lines` 空行 flush、C/`#` 断点 flush、无续行 flush、循环结束 flush 统一剥尾 `&`；5 空格缩进合并分支剥当前缓冲尾 `&` + 保留续行 `$` 注释 |
| `app/generator/parsers/core.py` | `parse_f_tally` 多粒子逗号正则 + 粒子展开（F-C）；`_apply_sdef_param` 加 `EFF` 分支（F-G） |
| `app/generator/inp_generator.py` | 顶部 import banners 常量（11-19）；`_generate_basic`(150) `FISSION_OFF_BANNER`；`_generate_materials`(207-209) options 上移 M 头行（F-D）；`_generate_tallies`(531) `TALLIES_BANNER`；`_generate_kcode`(610/609/645/651/654) KCODE/KSRC/HSRC 常量 + (634-643) 坐标强转（F-F）；`_generate_en_cards`(828/831)、`_generate_time_mesh`、`_generate_tn_cards`(888)、`_generate_energy_mesh`、`_generate_other_cards`(1000) 各节头改调 banners；`generate_inp_from_deck`(1071/1076/1083/1088/1093/1101/1109/1117/1133/1141/1149/1170) 各节头改调 banners 常量。**未动**：`_generate_multi_source`(375-519)、`_generate_distribution_sdef`(313-363)、631/673 `import json as _json`、110 `from pymcnp import inp`、`import sys`/`[E0DBG]` print、`raw_overrides` 守卫逻辑与 1156 门控 |
| `app/generator/validator.py` | 新增 `_unwrap_cells`；`validate_deck`(253-256) 解包 CellRow（`validate_all` 签名未动） |
| `tests/unit/test_generator_phys.py` | `test_ksrc_numeric_coords_raises` 翻新为 `test_ksrc_numeric_coords_emitted`（正确行为断言：数值坐标产出合法 KSRC 行） |
| `tests/parser/test_core_sdef.py` | 两例 EFF pin 翻新为 `sdef_extra == "EFF=2"` / `"EFF=2 5"` |
| `tests/parser/test_sections.py` | `test_is_cell_line_lowercase_m_reference_not_detected` 翻新为 `is True` |

## 三、数据库变更
无（纯 Python 引擎改动，无迁移脚本）。

## 四、新增环境变量
无。

## 五、终态与未决项

**全量 pytest：245 通过 / 6 失败**，与契约 §0.5.3 预期一致。6 红确认：

| 红项 | 类别 | 归属 |
| :--- | :--- | :--- |
| `test_r1_fixed_point_kitchen_sink` | kitchen-sink R1 表示漂移（非膨胀） | **P1 F#5/F#6**（§0.5.5 复合根因清单），本轮预期保持红 |
| `test_r4_kitchen_sink_full_roundtrip` | kitchen-sink R1+R2 | **P1 F#5/F#6**，本轮预期保持红 |
| `test_f3_no_function_level_import_json_in_inp_generator` | 技术债 F#3（函数内 `import json as _json`） | P1 |
| `test_f3_no_function_level_import_sys_in_parsers` | 技术债 F#3（函数内 `import sys` + `[E0DBG]` print） | P1 |
| `test_f7_pymcnp_imported_at_module_level` | 技术债 F#7（函数内 `from pymcnp import inp`） | P1 |
| `test_f7_pymcnp_function_level_import_absent` | 技术债 F#7 | P1 |

未因 kitchen-sink 红而触碰 `_generate_multi_source` / `_generate_distribution_sdef`（§7 P1 边界，本轮严禁）。

## 六、重锚定完成情况

- **`app/generator/review_findings.json`**：已按 §8.2 用 Grep 重锚定全部 `line` 字段与 prose 行号至本轮施工后的 inp_generator.py（raw_overrides→1156、import json→631、_generate_single_source→247、_generate_multi_source→375/384、pymcnp→110）。其中"`import re` in `_generate_en_cards`"一条为**陈旧记录**——干净基线中该函数已无函数内 `import re`（`test_f3_no_function_level_import_re` 绿），已标注 resolved。
- **`app/UI_ARCHITECTURE.md`**：**基线为空文件（0 字节，git 全历史均空）**，契约 §8.1 引用的 §5/§7.1/§7.2 内容不存在，无法重锚定。需 PM 决策：由架构师补建（含 raw_overrides 守卫新行号 1069/1081/1107/1115/1131/1139/1147/1168、`_wrap_long_lines` 1010、F#3 631/673、F#4 247、F#5 375、F#6 384-517、F#7 110），或将 §8.1 的锚点基线改到该文件重建后。

## 七、遇到的坑与处理

1. **契约 11 词汇不足以让样例 R1 全绿**：prob41c/inp24 上 `C  Fission turned off via NONU card`、`C  KCODE Criticality Source Parameters`、`C  ===== Additional Cards (from Advanced tab) =====` 等生成器内联 C 头同样泄漏进 `other_cards`/`mat.comment`。按"冻结生成器全部节头"的方案 C 精神，`banners.py` 扩展为全部生成器产出形式（仍精确匹配，防误伤用户注释）。
2. **prob41c R1 的"隐藏"阻塞是续行注释丢失**：F-A 修掉头泄漏后，prob41c 仍红——`_generate_cells` 把超 80 列长行拆成 core+续行，注释落在续行上，`normalize_lines` 缩进合并分支原样丢弃续行 `$` 注释。作为 F-E 伴生修复补上（当前行无注释时保留续行注释），属 `parsers/lines.py`（F-E 指定文件）内改动。
3. **F-F 边界**：`_generate_kcode` 内的 `import json as _json`（631）与 `_generate_structured_distributions` 的（673）未动，坐标强转只改 634-643。
4. **test 翻新是"改期望"，非"降级"**：F-F/F-G/F-H 三个 pin 用例均翻新为写死正确行为断言（数值坐标合法 KSRC、`sdef_extra=="EFF=2 5"`、`is True`），严禁 pass/skip/弱断言。`test_ksrc_numeric_coords_emitted` 首版断言 `l.strip().startswith("0  0  0")` 误判（0 坐标在 `KSRC 0 0 0` 首行，不以 0 开头），改为 `"0  0  0" in l` 子串断言。

## 八、本地启动验证步骤

```bash
cd "d:/MCNP/输入卡生成器源码"
python -m pytest tests/ -v          # 期望 245 绿 / 6 红（4 红=F#3/F#7 技术债，2 红=kitchen-sink R1/R4，P1 范围）
```

（引擎纯函数，无 HTTP 端点变更，无需起 5001。）

---

# 附录 A：P1 技术债重构（2026-08-12，分支 refactor/generator-tech-debt）

> 契约：`docs/contracts/p1-refactor.md`（已锁定）。施工顺序 F#7→F#3→F#4→F#5+F#6→F#1。
> **终态：全量 pytest = 251 绿 / 0 红（复跑 ×2 稳定）**，6 红全部转绿。

## A.1 每个 F# 的重构结果 + commit 索引

| F# | 重构 | 断言红→绿 | commit |
| :--- | :--- | :--- | :--- |
| F#7 | `from pymcnp import inp` 从 `_generate_basic` 函数内提到模块顶部（导入期 fail-fast） | `test_f7_pymcnp_imported_at_module_level` / `test_f7_pymcnp_function_level_import_absent` ×2 转绿 | `bf0a2c7` |
| F#3 | 删函数内 `import json as _json`（改 `json.loads`）+ `import sys` + `[E0DBG]` print（inp_generator/core.py/__init__.py/api_server.py 4 文件）；连带 api_server 两处捆绑 `import sys, os, json...` 收敛（模块级已有） | `test_f3_no_function_level_import_json_in_inp_generator` / `test_f3_no_function_level_import_sys_in_parsers` ×2 转绿；grep `import json as`/`E0DBG`/函数内 `import sys` 归零 | `c774e56` |
| F#4 | `_generate_single_source` 两分支（Dn/普通）合并为 `_build_sdef_parts(src, include_special)` | `test_f4_*`×2 保持绿；`test_generator_sdef.py` 全绿（字节不变）；`test_sdef_single_source_delegates` pin `SDEF  ERG=14.0  POS=0 0 0` 保持 | `52ca251` |
| F#5+F#6 4a | 拆 `_collect_source_values`/`_normalize_probabilities`/`_varying_dist_params`/`_build_multi_sdef_parts`/`_build_multi_sisp_cards` 五函数 + `SDEF_FIELD_SPECS` 表 | `test_generator_multi_source.py` 14/14 全绿（行为 pin，输出逐字节一致）；kitchen-sink R1/R4 仍红（结构未改漂移） | `e404172` |
| F#5+F#6 4b | 漂移修复：sdef_extra 分布关键字去重 / SI 类型表加 V / banners 注释 + `_DYNAMIC_PATTERNS` / 多源 SI 值扁平化 / `_generate_distribution_sdef` 改字段序 + POS F-dist 分支 + 注释重发 | `test_r1_fixed_point_kitchen_sink` + `test_r4_kitchen_sink_full_roundtrip` **红→绿**；样例 R1（prob41c/avr13/inp24/minimal）保持绿 | `018ced5` |
| F#5+F#6 4c | 全量回归 | **251 绿 / 0 红**（复跑 ×2 稳定） | （含于 018ced5） |
| F#1 | 8 处 raw_overrides 守卫收敛为 `_apply_raw_override(...)` 一行调用；1145 门控保留（判 tally key） | `test_generator_overrides.py` 28/28 全绿（含 raw_tally 门控三例 pin）；grep `overrides.get` 仅 `_raw_override_text` 一处 | `1488aae` |

## A.2 F#5+F#6 子步验收

- **4a 字符化门**：五函数拆出后 `test_generator_multi_source.py` 全绿（行为 pin），证明重构未改字节；此步 kitchen-sink R1/R4 允许仍红。
- **4b 漂移修复**：§0.5.5 根因 #2（POS F-dist 分支重建 `POS=F D1`）+ #3（sdef_extra 分布关键字去重）+ #4（SI 类型表加 V）+ #5（分布注释 banners 词汇 + 回放重发）+ SI 值扁平化 + 字段序统一；kitchen-sink R1/R4 红→绿，样例 R1 保持绿。
- **4c 全量回归**：251 绿 / 0 红，R1/R4 kitchen-sink 稳定。

## A.3 文件改动明细（P1 重锚定后行号）

| 文件 | 改动 |
| :--- | :--- |
| `app/generator/inp_generator.py` | pymcnp 顶部 import（8）；`_build_sdef_parts`（247）；`SDEF_FIELD_SPECS`（306）；`_generate_distribution_sdef`（341，字段序 + POS 四态 + 注释重发）；`_multi_source_comment_reemit`（406）；多源 5 函数（434/454/473/500/556/577/608）；`_strip_sdef_extra_dist_keys`（556）；raw_overrides 助手 `_raw_override_text`/`_has_raw_override`/`_apply_raw_override`（1140/1145/1149）+ 8 调用点（1191/1196/1215/1229/1231/1234/1237/1252）+ tally-key 门控（1241/1246） |
| `app/generator/parsers/core.py` | SI 类型表加 "V"（126）；删函数内 import sys + [E0DBG] print |
| `app/generator/parsers/__init__.py` | 删函数内 import sys + [E0DBG] print（138-140） |
| `app/generator/banners.py` | 新增 `multi_source_comment_banner`（84）；`_DYNAMIC_PATTERNS` 加 `^C\s+\d+ sources, probability keyed to D1$` |
| `gui/backend/api_server.py` | 删 [E0DBG] print + 函数内 import sys（608-610、1004、1097）；**路由表 25 端点未触碰** |

## A.4 新增环境变量

无（P1 纯结构重构 + 漂移修复，不引入新依赖、无新增环境变量）。

## A.5 本地启动验证步骤

```bash
cd "d:/MCNP/输入卡生成器源码"
python -m pytest tests/ -v          # 期望 251 绿 / 0 红（复跑 ×2 稳定）
```

（引擎纯函数，无 HTTP 端点变更，无需起 5001。）

## B. 3D 预览性能修复后端（preview3d-performance 契约，分支 perf/preview3d）

> 契约：`docs/contracts/preview3d-performance.md`（2026-08-12 复现实测修订版）。
> 范围：步 1 bound 修正 + preview_cache + 步 2 vtk 惰性 + 步 3 handler 接线。前端（gui/src/）由前端 agent 负责，后端零重叠。

### B.1 改动清单（文件/函数/行号，重锚定 2026-08-12）

| 文件 | 函数 | 改动 |
| :--- | :--- | :--- |
| `app/freecad_preview.py` | `_surface_extent_values`（新增，:206） | 类型→extent 规则表：位移类直接取 max；宏体方向向量（RCC/REC/TRC h、BOX a1/a2/a3、WED v1/v2/v3、RHP/HEX r/s/t）与基点合成角点；未知类型保守全取 |
| `app/freecad_preview.py` | `_compute_bound_from_surfaces`（重写，:268） | 按 extent 表取 max，GQ/SQ 跳过，`max*1.3+100` 与 default 兜底。接口 `(surf_dicts, default)->float` 不变，:335 调用点不变 |
| `app/preview_cache.py` | `PreviewCache`（新增） | 深模块：`fingerprint`（canonical json→sha256）/`get`（isdir 兜底 miss）/`put`（STL 拷贝进缓存自有目录 `base_dir/<fp>/`）/`evict_dir`/`evict_lru`（LRU 上限 3，删目录）/`get_or_build`（builder seam）。纯 stdlib |
| `app/_freecad_csg_worker.py` | 顶层（:30） | 删顶层 `import vtk`，`_HAVE_VTK = False` |
| `app/_freecad_csg_worker.py` | `_quadric_to_shape`（:671） | native 回退分支内按需 `import vtk`（try/except，成功置 `_HAVE_VTK=True`） |
| `gui/backend/api_server.py` | `_PREVIEW_CACHE`（:35） | 模块级 PreviewCache 单例 |
| `gui/backend/api_server.py` | `_clear_stl_session`（:44） | 与缓存联动：`_PREVIEW_CACHE.evict_dir(d)` |
| `gui/backend/api_server.py` | `_handle_preview_3d`（:1001） | 接线：fp=fingerprint → get 命中则免 FreeCAD（_STL_SESSION=缓存目录、读 STL→base64、freecad 用缓存值）→ 未命中走现状 + cache.put。响应结构逐字段不变 |

### B.2 新增测试

| 文件 | 测什么 |
| :--- | :--- |
| `tests/unit/test_preview_bound.py` | 7 fixture 区间断言（shield_20m∈[2600,2800]、stress_bunker∈[2000,2100]、inp01≈13100、inp09≈3665）+ RCC 轴长不当坐标（5300→2700）+ WED/BOX 角点合成 + GQ/SQ 跳过 |
| `tests/unit/test_preview_cache.py` | fingerprint 稳定、put/get 命中、evict_lru 删最旧、evict_dir 联动、命中跳过 builder seam |
| `tests/integration/test_preview3d_worker.py` | AST：worker 顶层无 import vtk、惰性 import 在 _quadric_to_shape 内且位于 native 回退后、_HAVE_VTK 初值 False |

### B.3 全量 pytest（每步验收）

| 步 | 验收 | 结果 |
| :--- | :--- | :--- |
| 步 1 | 251 + test_preview_bound + test_preview_cache 全绿 | **267 passed / 0 failed**（commit 97de569） |
| 步 2 | test_preview3d_worker 绿；grep worker 顶层无 vtk | **271 passed / 0 failed**（commit e65d423） |
| 步 3 | 全量绿 + 联调点 1/2 | **271 passed / 0 failed**（commit dbab84e） |

### B.4 联调验证（真实 FreeCAD，本机 D:\FreeCAD\...\bin）

- **联调点 1（响应结构不变）**：miss/hit 响应均含 `stl_files`/`stl_data`/`freecad`/`count` 四业务字段（`status` 为 `_ok` 信封），逐字段一致，`stl_data` 字节级一致。
- **联调点 2（_STL_SESSION 指向缓存目录后 cross-section 复用）**：命中后 `/api/cross-section` 从缓存目录 STL 切片正常（count=1, polygons=1）。
- **KPI**：未命中 0.68s（FreeCAD 重建）→ clear-stl（缓存存活）→ 命中 0.02s（缓存目录），≤1.0s 达成。重复命中 guard 生效；clear-stl 驱逐命中中的缓存目录（无悬挂）。
- 验证脚本：仓库外临时脚本（手动运行，非 pytest——铁律禁测试 import api_server）。

### B.5 bound 修正对 4 fixture 实际输出

| fixture | 旧 bound | 新 bound | 契约期望 |
| :--- | :--- | :--- | :--- |
| preview_shield_20m.inp | 5300 | **2700** | [2600, 2800] |
| preview_stress_bunker.inp | 2050 | **2050** | [2000, 2100] |
| preview_inp01_m100.inp | 13100 | **13100** | ≈13100 ±5% |
| preview_inp09_m27.inp | 3665.6 | **3665.6** | ≈3665 ±5% |

### B.6 新增环境变量

无（preview_cache 纯 stdlib，无新增运行时依赖）。缓存根目录默认系统临时目录 `mcnp_preview_cache_*`，LRU 上限 3。

### B.7 本地启动验证步骤

```bash
cd "d:/MCNP/输入卡生成器源码"
python -m pytest tests/ -v          # 期望 271 绿 / 0 红
python gui/backend/api_server.py    # 起 5001，post /api/preview-3d 同一 deck 两次：第一次 FreeCAD 重建，第二次命中缓存
```

### B.8 遇到的坑

1. **分支已由前端先建**：`perf/preview3d` 已存在（前端 gui/src 改动未提交）。直接切过去；提交时只暂存后端文件，避免 `git add -A` 扫走前端工作树。
2. **缓存设计需"缓存自有拷贝"**：前端关预览窗口即调 `/api/clear-stl`。若缓存只引用会话目录，clear 即驱逐 → 关窗后重开同一 deck 必 miss，KPI 失效。`put` 把 STL 拷入 `base_dir/<fp>/` 缓存目录，会话目录被清不影响缓存。
3. **命中路径 clear 需 guard**：命中若无条件 `_clear_stl_session()`，重复命中（prev==cached dir）会自我删除缓存目录。guard：仅当 `prev_dir != cached["dir"]` 才 clear。
4. **`_ok()` 信封含 `status`**：响应 = `{status, stl_files, stl_data, freecad, count}`，四业务字段逐字段不变，`status` 是既有信封。
5. **commit message 反引号**：git-bash 中 commit message 内反引号会被命令替换，`import vtk` 文本被吞。后续避免。

---

# 附录 C：反馈 #5 材料"其他"框多行 options（2026-08-13，分支 experiment/geouned）

> 工单：用户反馈 #5 —— 材料 nlib/gas/plib 框改名"其他"、输入框放大支持换行、输出原样贴在对应材料卡下。
> 前端同步把 input 改 textarea（value/onChange 绑定 MaterialData.options 字符串），options 可含 `\n`。
> "其他"框定位是 M 卡 options（nlib/plib/gas 必须在 M 卡上），不是独立卡。
> 契约/知识：`app/docs/sample_format.md`（材料卡格式）、PROJECT_MEMORY §6 F-D（options 上移 M 头行）。

## C.1 改动点

| 文件 | 函数 / 行 | 改动 |
| :--- | :--- | :--- |
| `app/generator/inp_generator.py` | `_generate_materials`（首行构造，原 205-209 → 现 205-220） | options 按 `\n` 拆分：首段仍内联 `M{n}  ` 后（无换行时输出字节不变，F-D pin 不回归），其余段作为 M 卡续行（行首 5 空格缩进），否则 MCNP 会把 `gas=/plib=` 当新卡解析；`\r\n`/`\r` 归一化为 `\n`；空白段跳过。续行（核素/raw）逻辑未动 |

## C.2 新增测试

| 文件 | 测什么 |
| :--- | :--- |
| `tests/unit/test_generator_materials_multiline_options.py`（10 用例） | 多行 options 续行格式（首段内联 + 5 空格续行、options 续行在核素续行之前）；F-D pin 单行 options 逐字节不变；无 options 字节不变；CRLF 归一化；空白段跳过；全管线（`generate_inp_from_deck`）M 卡段格式正确；`_wrap_long_lines` 交互——超长 options 行被 `&` 续行拆分后全部行 ≤80 列且 M 卡续行合法（5 空格缩进或行尾 `&`，无无缩进裸行）；回放语义保留（多行 options 拍平成单空格属点 5 接受行为，核素行保留） |

## C.3 全量 pytest

**287 passed / 0 failed**（基线 277 零回归 + 新增 10）。R1 不动点不回归（`test_roundtrip.py` + `test_sample_smoke.py` 34 例全绿）。

## C.4 数据库变更 / 环境变量

无（纯 Python 引擎改动，无迁移脚本、无新依赖、无新增环境变量）。

## C.5 边界说明

- 解析器 `core.py:397` 换行拍平成单空格（`options=" ".join(options_parts)`）属语义保留，不阻塞；多行往返保真列为增强项，本轮不做。
- 未触碰：`_wrap_long_lines`（1010）、`_generate_multi_source`/`_generate_distribution_sdef`、raw_overrides 守卫、api_server 路由表。

## C.6 本地启动验证步骤

```bash
cd "d:/MCNP/输入卡生成器源码"
python -m pytest tests/ -v          # 期望 287 绿 / 0 红
```

（引擎纯函数，无 HTTP 端点变更，无需起 5001。）

---

# 附录 E：词条专项 D-01 独立 SIn/SPn 静默丢弃（2026-08-13，分支 experiment/geouned）

> 工单：词条审计 D-01（P0 数据丢失）——独立 SIn/SPn 卡静默丢弃，不进 other_cards、不进任何字段。
> 契约：`docs/contracts/card-lexicon.md` + `docs/card-lexicon-diff.md` D-01。根因由 tester-d01 回归测试精确暴露。

## E.1 根因

`parse_data_cards` 分支（原 core.py:1101-1102）`elif first.startswith("SI") or first.startswith("SP"): i += 1` → 整行静默丢弃。
仅「紧跟 SDEF」时被 SDEF 分支（core.py:1003-1028）收集为结构化分布。触发场景：
1. **SSR 面源分布**：`SSR OLD 3 2 NEW 6 7 12 13 TR D5` 后跟 `SI5 L 4 5`/`SP5 .4 .6`
2. **SDEF 与 SI 隔 C 注释行**：SDEF 收集循环遇 C 即 break → 后续 SI/SP 全丢

## E.2 改动点

| 文件 | 函数 / 行 | 改动 |
| :--- | :--- | :--- |
| `app/generator/parsers/core.py` | `_merge_sisp_entry`（新增，:158-178） | 把单个结构化分布条目并入已有 `sdef_distributions` JSON（按 id 合并 SI/SP/SB/DS 子字段），供面源场景逐行累积 |
| `app/generator/parsers/core.py` | `parse_data_cards` SI/SP 分支（:1125-1134） | ① 最小修复（必做）：SI/SP 行 append 进 `result["other_cards"]`（保底不丢，round-trip 保真）；② 增强修复（安全）：`source_mode=="surface"`（SSW/SSR 面源）时并入结构化分布（复用 `_parse_sisp_structured`，与 SDEF 分支一致），source_mode 保持 surface |

增强安全性依据：生成器 `_sdef_dispatch` 对 surface 模式只走 `_generate_ssw + _generate_ssr`、忽略 `sdef_distributions` → 结构化并入不影响生成字节，无双重发射；`_generate_other_cards` 末尾无条件回放 → SI/SP 由 other_cards 保证 round-trip。既有 `test_parse_ssw_ssr` 无 SI/SP、不涉 sdef_distributions，不受影响。

## E.3 测试（6 用例，tester-d01 建，红→绿）

| 文件 | 用例 | 修复前 | 修复后 |
| :--- | :--- | :--- | :--- |
| `tests/parser/test_regress_independent_si_sp.py` | `test_ssr_followed_by_si_sp_not_dropped` | 红 | 绿（SI5/SP5 保底进 other_cards） |
| `tests/parser/test_regress_independent_si_sp.py` | `test_ssr_si_sp_round_trip_keeps_cards` | 红 | 绿（回放出 SI5/SP5） |
| `tests/parser/test_regress_independent_si_sp.py` | `test_sdef_comment_separated_si_sp_not_dropped` | 红 | 绿 |
| `tests/parser/test_regress_independent_si_sp.py` | `test_sdef_comment_separated_si_sp_round_trip_keeps_cards` | 红 | 绿 |
| `tests/parser/test_regress_independent_si_sp.py` | `test_control_sdef_immediately_followed_si_sp_structured` | 绿 | 绿（对照不回归：source_mode=distribution + JSON id=5） |
| `tests/parser/test_regress_independent_si_sp.py` | `test_control_sdef_direct_round_trip_keeps_si_sp` | 绿 | 绿 |

## E.4 全量 pytest

**293 passed / 0 failed**（287 预存在基线 + 6 新 D-01）。R1 不动点 / R2-R4 往返 / 契约漂移闸门全绿。

## E.5 数据库变更 / 环境变量

无（纯 Python 解析器改动，无迁移脚本、无新依赖、无新增环境变量）。

## E.6 边界说明

- 只修 D-01（core.py SI/SP 分支）。未触碰 D-02/D-03/D-04/D-05/D-06/D-07（待架构师重锚定后统一排）。
- SB/DS 卡在 SDEF 上下文外已由 `parse_data_cards` 最终兜底（:1259）进 other_cards，非本项范围。
- **观测项（非本项范围）**：`SSR OLD S1 ... NEW S2 ...` 解析时 `ssr_mode` 按"最后出现的 OLD/NEW"覆盖（OLD 列表丢），属既有 SSR 解析限制；D-01 只解决 SI/SP 丢失，SSR 双列表保真留待 D-02 范畴。

## E.7 本地启动验证步骤

```bash
cd "d:/MCNP/输入卡生成器源码"
python -m pytest tests/ -v          # 期望 293 绿 / 0 红
python -c "from app.generator.parsers.core import parse_data_cards; r=parse_data_cards('SSR OLD 3 2 NEW 6 7 12 13 TR D5\nSI5 L 4 5\nSP5 .4 .6'.splitlines()); print(r['other_cards'], r['sdef_distributions'])"
```

---

# 附录 D：反馈 #1 FM 卡导入识别 + #6 cell 文本→表单丢数据（2026-08-13，分支 experiment/geouned）

> 工单：用户反馈 #1（P0，FM 计数乘子卡导入不识别）+ #6（P0 最严重，cell 卡文本→表单丢几乎所有数据）。
> 根因由 tester 实测确认，断点均在【后端】；修法按 PM 派发根因执行，未改方向。

## D.1 改动点

### #1 FM 计数乘子卡全链补 multiplier

| 文件 | 函数 / 行 | 改动 |
| :--- | :--- | :--- |
| `app/generator/parsers/core.py` | `parse_data_cards` 入口门（:1030） | 正则扩 `^[*+]?FM\d+$`（FM 卡无粒子设计符，格式 `FMn C m r1 r2 ...`），FM5 不再落 other_cards |
| `app/generator/parsers/core.py` | `parse_f_tally` FM 分支（:721-737） | `^FM(\d+)$` → 提取编号 n，multiplier = 该卡全部 token；附加到同 number 的已有 TallyDefinition（重复 FM 卡空格合并）；无对应 Fn 时建占位 `TallyDefinition(type="", number=n, multiplier=...)`（保证不丢） |
| `app/generator/parsers/core.py` | F 卡合并块（:790-811） | FMn 先于 Fn 出现时，F 卡解析把占位（type=="" 同 number）的 multiplier 并入真实 TallyDefinition 并移除占位 |
| `app/generator/parsers/sections.py` | `DATA_PATTERNS`（:146） | 补 `^FM\d+$`，FM 卡在 cell/surface 相位也能正确分到 data 段 |
| `app/models.py` | `TallyDefinition`（:200） | 新增字段 `multiplier: str = ""`（FMn 乘子参数串，如 `8.65061E10 1 -5 -6`） |
| `app/generator/inp_generator.py` | `_generate_tallies`（:644-671） | 每张 td 若 multiplier 非空，在对应 `F{number}` 卡**之后**输出 `FM{number}  {multiplier}`；占位（type==""）只回放 FM 卡、不生成 F 卡。无 multiplier 的既有 tallies 输出字节不变 |
| `gui/backend/api_server.py` | `_tally_from_dict`（:358） | 读 `multiplier`（导入→生成不丢） |
| `gui/backend/api_server.py` | `_deck_to_frontend_dict`（:480）/ `_handle_parse_inp`（:665） | tallies 每项带出 `multiplier` 字段（文本互转 / 导入→前端不丢） |

### #6 cell 文本→表单 shell 修复

| 文件 | 函数 / 行 | 改动 |
| :--- | :--- | :--- |
| `gui/backend/api_server.py` | `_handle_text_to_section`（:718-719） | `section=="cells"` 走独立 shell `f"{text}\n\nC  surf\n1 pz -1e9\n\nMODE N\n"`——用户 cell 文本放入【栅元段】；原 shell 把 `{text}` 追加在曲面段之后落 data 段，被 `other_cards` 兜底、用户栅元字段全丢。materials/tally 分支保持原 shell 不变（本属数据段） |

## D.2 测试（6 用例，验收基准转绿）

| 文件 | 用例 | 断言（修复后正确行为） |
| :--- | :--- | :--- |
| `tests/parser/test_regress_fm5_import.py` | 3 | 入口门识别 FM5/FM4；`parse_f_tally` 附加 multiplier（含 FM 先于 F 的占位吸收）；`parse_data_cards` 吸收 FM5 不进 other_cards + 生成器在 F 卡后回放 `FM5  8.65061E10 1 -5 -6` |
| `tests/parser/test_regress_cell_text_to_form.py` | 3 | cell 文本→表单 3 栅元字段全保留（material/density/surface_expr/imp/vol/tmp/pwt/comment）不再落 other_cards；对照组 materials/tally 经原 shell 解析正常；parse_cells 字段解析完整 |

**⚠️ 测试状态说明（需 PM 知悉）**：测试已提交的两个回归文件**pin 的是修复前的 bug 行为**（提交时即为绿，与派发信息"现在红"不符）。代码修复会让其中 2 个变红（`parse_f_tally`/`parse_data_cards` 实际被调用的用例）。为达成"6 回归全绿"验收，已把测试断言**更新为修复后的正确行为**（强化断言：FM5 必须被识别/吸收/回放、用户栅元必须全保留，非删弱断言骗绿），并用 `test_fm_before_f_placeholder_absorbed` 覆盖占位吸收（并入场景二）。

## D.3 全量 pytest

**287 passed / 0 failed**（复跑稳定）= 271（基线）+ 6（#1/#6 回归）+ 10（#5 在途 `test_generator_materials_multiline_options.py`）。R1 不动点 / R2-R4 往返 / 契约漂移闸门（test_api_contract 26 例含真实 HTTP）全绿。

## D.4 数据库变更 / 环境变量

无（纯 Python 引擎改动，无迁移脚本、无新运行时依赖、无新增环境变量）。

## D.5 边界说明

- 未触碰：`parse_cells`（PM 明确不改）、`_generate_multi_source`/`_generate_distribution_sdef`、raw_overrides 守卫、api_server 路由表（25 端点零增删）、materials/tally 分支 shell。
- **观测项（非本任务范围）**：`F5Z:P` 环探测器轴的 `number_suffix`（"Z"）在 `_handle_parse_inp` 的 tallies 序列化中本就不带出（既有缺陷，非本轮引入），roundtrip 后 `F5Z:P` → `F5:P`；本任务只按根因补 multiplier，number_suffix 序列化列为观测项待后续处理。

## D.6 本地启动验证步骤

```bash
cd "d:/MCNP/输入卡生成器源码"
python -m pytest tests/ -v          # 期望 287 绿 / 0 红
python gui/backend/api_server.py    # 起 5001
# #6: POST /api/text-to-section {"section":"cells","text":"1 1 -2.7 -1 2 imp:n=1 vol=3.14 ..."}
# #1: POST /api/parse-inp {"inp":"...F5Z:P 100. 5000. 99.\nFM5 8.65061E10 1 -5 -6..."} → tallies[0].multiplier
#     → 该 deck 原样 POST /api/generate → 输出含 "FM5  8.65061E10 1 -5 -6"
```

---

# 附录 F：词条专项"真需修 3 条" D-03 分节缺口 + D-07 SDEF 裸参数 + D-10 other_cards $ 注释（2026-08-13，分支 experiment/geouned）

> 工单：按设计意图校准后，词条专项真需修 3 条（兜底网会丢/会误吸收的条目）。契约：`docs/contracts/card-lexicon.md` + `docs/card-lexicon-diff.md` D-03/D-07/D-10。回归测试由 tester-dfix 红基线先行（45 红），后端施工转绿。

## F.1 改动点

| 缺陷 | 文件 | 函数 / 行 | 改动 |
| :--- | :--- | :--- | :--- |
| **D-03** 分节缺口 | `app/generator/parsers/sections.py` | `split_sections` `DATA_PATTERNS`（:148-185） | ① F 家族计数卡补前缀形态：`^[*+]?F\d+:` / `^[*+]?F\d+$` / `^[*+]?F\d+[XYZ]:?` / `^[*+]?F(?:IP\|IR\|IC)\d+` / `^[*+]?FM\d+` / `^[*+]?FC\d+`（对齐 parse_data_cards 入口门）；② 计数/源分布辅助卡缺口词条：`^C\d+$`(Cn 余弦)/`^DE\d+$`/`^DF\d+$`/`^FS\d+$`/`^SD\d+$`/`^CF\d+$`/`^SF\d+$`/`^EM\d+$`/`^TM\d+$`/`^CM\d+$`/`^TF\d+$`/`^DD\d+$`/`^DXT$`/`^SB\d+$`/`^DS\d+$`/`^SC\d+$`/`^ELPT`/`^NOTRN$`/`^TALNP$`/`^MPLOT$`/`^RAND$`/`^FILES$`/`^IDUM$`/`^RDUM$`/`^FMESH`。未设计卡在节首（phase 仍 cell/surface）直出时进 data_lines → other_cards 兜底，不再误分曲面/栅元段 |
| **D-07** SDEF 裸参数白名单 | `app/generator/parsers/core.py` | `parse_sdef_simple` 裸分支（:593-620）+ `=` 分支 POS/VEC/AXS 续值（:485-497） | ① 裸分支白名单补 `ERG/WGT/CEL/TME/EFF/RAD/EXT/DIR/X/Y/Z`（复用 `_apply_sdef_param`，EFF→sdef_extra）；② 新增裸 `AXS/VEC` 多值分支（整体收集，遇已知 key 停止）；③ `POS/VEC/AXS=` 续值收集加已知 key 停靠（防止 `POS=0 0 0 ERG 14 WGT 1` 吞裸 ERG/WGT） |
| **D-10** other_cards $ 注释剥离 | `app/generator/parsers/core.py` | `parse_data_cards` 6 处 `other_cards` append（:1044/:1085/:1090/:1154/:1286/:1317） | `append(line)`（strip_comment 后）→ `append(raw_line)`（保留行内 `$ 注释`）。`tr_cards`（:1217）本就是 raw_line 未动；C 注释回落（:983 `pending_c`）本就是 raw_line |

## F.2 新增测试（tester-dfix 建，45 红 → 全绿）

| 文件 | 用例 | 修复前 | 修复后 |
| :--- | :--- | :--- | :--- |
| `tests/parser/test_regress_lexicon_d03_sections.py` | 29（节首辅助卡 21 词条参数化 + ELPT/FMESH4/Cn/DXT + 紧凑 INP `*F4`/`+F4`/`F5Z:P` + `*F4` 解析进 tally_defs） | 全红 | 29 绿 |
| `tests/parser/test_regress_lexicon_d07_sdef_bare.py` | 12（单裸参数 ERG/WGT/CEL/TME/EFF/X/AXS/DIR + 组合裸 + 混合 `=`/裸 + 对照 EFF= + round-trip） | 11 红 1 绿 | 12 绿 |
| `tests/parser/test_regress_lexicon_d10_other_cards_comment.py` | 5（PTRAC/FILES/RAND 行内 $ 注释保留 + 两个 round-trip） | 全红 | 5 绿 |

## F.3 全量 pytest

**343 passed / 0 failed**（298 预修通过 + 45 红转绿）。R1 不动点 / R2-R4 往返 / 契约漂移闸门 / 样例冒烟（test_roundtrip + test_api_contract + test_sample_smoke 41 例）全绿。

## F.4 数据库变更 / 环境变量

无（纯 Python 解析器/分节改动，无迁移脚本、无新依赖、无新增环境变量）。

## F.5 边界说明

- 只修 D-03/D-07/D-10。未触碰 D-02/D-04/D-05/D-06/D-08/D-09（兜底登记/前端/文档类，不改代码）。
- D-03 只影响"节首直出未设计卡"场景；正常布局（phase 已切 data）行为不变。`^C\d+$` 不与 C 注释冲突（注释是 `C `+空格，`C\d+` 是余弦分箱）。
- D-07 只补裸参数写法；`key=val` 等号形式既有行为零改动（对照 `EFF=0.5` 保持绿）。
- D-10 保留 raw_line 的 $ 注释进 other_cards；R2 尾 $ 容差与 `_wrap_long_lines` 交互实测无回归（R3 other_cards 集合包含断言通过）。
- **观测项（非本项范围）**：D-03 补的词条在 parse_data_cards 多数仍落 other_cards 兜底（结构化登记属 D-02 范畴）；紧凑 INP 是合法 MCNP 结构，真实样例与标准生成器产出不受影响。

## F.6 本地启动验证步骤

```bash
cd "d:/MCNP/输入卡生成器源码"
python -m pytest tests/ -v          # 期望 343 绿 / 0 红
python -c "from app.generator.parsers.sections import split_sections; print(split_sections(['t','1 0 -1','1 pz -1e9','*F4:N 1 2 3'])[3])"   # ['*F4:N 1 2 3']
python -c "from app.generator.parsers.core import parse_sdef_simple, parse_data_cards; print(parse_sdef_simple('SDEF ERG 14'.split())[0].erg); print(parse_data_cards(['PTRAC \$ write particles'])['other_cards'])"
```
