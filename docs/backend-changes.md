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
cd "PROJECT_ROOT"
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
cd "PROJECT_ROOT"
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
cd "PROJECT_ROOT"
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
cd "PROJECT_ROOT"
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
cd "PROJECT_ROOT"
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
cd "PROJECT_ROOT"
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
cd "PROJECT_ROOT"
python -m pytest tests/ -v          # 期望 343 绿 / 0 红
python -c "from app.generator.parsers.sections import split_sections; print(split_sections(['t','1 0 -1','1 pz -1e9','*F4:N 1 2 3'])[3])"   # ['*F4:N 1 2 3']
python -c "from app.generator.parsers.core import parse_sdef_simple, parse_data_cards; print(parse_sdef_simple('SDEF ERG 14'.split())[0].erg); print(parse_data_cards(['PTRAC \$ write particles'])['other_cards'])"
```

---

# G. 网格计数（FMESH/TMESH）3D 体积可视化 — 后端施工

> 施工方：后端 | 分支：`experiment/geouned` | 日期：2026-08-14
> 契约：`docs/contracts/meshtal-visualization.md`（§4/§5/§6/§8/§12 A1.2/F4）
> 任务：红基线 63 红 → 全绿（62 绿 + 1 待 PM 仲裁）；343 基线不破；api.yaml 25→28。

## G.1 交付概览

| 项 | 内容 |
| :--- | :--- |
| **A. FMESH/TMESH 结构化五步走** | sections.py 补 `^TMESH`/`RMESHn`/`CMESHn`；core.py 入口门加 FMESH/TMESH 分支吸收进 fmesh_defs；新建 `app/meshtal/fmesh_parser.py`；models.py 加 `FmeshDefinition` + `TallySettings.fmesh_defs`；inp_generator `_generate_tallies` 后回放 fmesh；api_server `_tally_from_dict` 读 fmesh_defs（另两处经 asdict 自动带出） |
| **B. app/meshtal/ 模块** | meshtal_parser / volume_builder / colormap / downsample_plan / meshtal_cache / deck_match / _meshtal_worker（8 文件） |
| **C. 3 端点 + api.yaml 25→28 + _err hint** | meshtal-detect / meshtal-parse / meshtal-texture；漂移闸门双向一致；`_err(msg, status=500, hint="")` 加性兼容 |
| **D. 红→绿** | 62/63 红转绿；1 红（colormap midpoints）与 golden 冲突，待 PM 仲裁 |

## G.2 A. FMESH/TMESH 结构化五步走

| 文件 | 改动 |
| :--- | :--- |
| `app/generator/parsers/sections.py` | DATA_PATTERNS 补 `^TMESH` / `^RMESH\d*` / `^CMESH\d*`（节首直出不误分曲面/栅元段，D-03 同类防患） |
| `app/generator/parsers/core.py` | 入口门 if/elif 链加 FMESH/TMESH 分支（`re.match(r'^FMESH\d+', first)` 与 `re.match(r'^TMESH\d*$', first)`，大小写不敏感）→ 收集卡体行（5 空格续行 + RMESH/CMESH 子卡）→ `parse_fmesh_lines` → `result["fmesh_defs"]`；异常 → 保底 other_cards raw_line。新增 `_is_fmesh_body_line` helper。**伴生正确性修复**：`pending_c` C 注释在 EOF 未 flush 被静默丢弃 → 已 flush 进 other_cards（R1 不变量必要修复） |
| `app/meshtal/fmesh_parser.py`（新） | `parse_fmesh_lines(lines) -> list[FmeshDefinition]`（FMESHn 直接定义 / TMESHn 标题 + RMESHn/CMESHn 子卡；GEOM/ORIGIN/IMESH/IINTS/JMESH/JINTS/KMESH/KINTS/EMESH/EINTS/TMESH/TINTS/MAT/OUT 键值吸收，值原文保存）；`fmesh_defs_to_lines(defs)` 结构化回放，structured 空 → raw 回放 |
| `app/models.py` | 新增 `FmeshDefinition`（§5.1 全字段含 raw）；`TallySettings.fmesh_defs: list[FmeshDefinition]` |
| `app/generator/inp_generator.py` | `_generate_tallies` F 卡段后追加 `fmesh_defs_to_lines(...)`；`not tally.tallies and not fmesh_defs` 才提前返回 |
| `app/generator/parsers/__init__.py` | `parse_inp_text` 把 `data.get("fmesh_defs", [])` 传入 `TallySettings` |
| `gui/backend/api_server.py` | `_tally_from_dict` 读 `fmesh_defs` → `_fmesh_from_list`；`_handle_parse_inp`/`_deck_to_frontend_dict` 经 `dataclasses.asdict` 自动带出 `tally.fmesh_defs` |

## G.3 B. app/meshtal/ 模块

| 文件 | 接口 |
| :--- | :--- |
| `app/meshtal/meshtal_parser.py` | `parse_meshtal(text) -> MeshtalFile` / `parse_meshtal_file(path)`；pymcnp 惰性优先校验 + 轻量兜底；MeshTally{number/particle/geom/bins_x/y/z/bins_energy/bins_time/data[(e,t)]/error/scalar_range}；数据行按 `[Energy] [Time] X Y Z Result RelError` 判别（has_energy_col=energyBins>1、has_time_col=timeBins>1），"Total" 汇总行跳过；x/y/z 最近邻中心索引，energy/time bisect 位置-1 |
| `app/meshtal/volume_builder.py` | `build_frame(mf, tally_number, energy_bin, time_bin, resolution, budget_bytes) -> Frame{resolution/world_box/scalar(uint8)/scalar_range/avg_factor/downsampled}`；box-average 均值降采样（保总量）+ 归一化在降采样后 |
| `app/meshtal/colormap.py` | `WEATHER_STOPS` 5 锚点；`weather_lut(n=256)`（t=i/(n-1) 线性插值，round-half-even）；`map_value(v, lo, hi, lut)`（v<lo → alpha 0）；golden sha256 = 36770ae2… |
| `app/meshtal/downsample_plan.py` | `GPU_BUDGET_BYTES=256MiB` / `DEFAULT_RESOLUTION=128` / `MAX_RESOLUTION=256`；`estimate_texture_bytes`（RGBA 4B）；`plan_downsample`；`decide_resolution`（自动 128³ / 256 显式 / 超预算 popup） |
| `app/meshtal/meshtal_cache.py` | `MeshtalParseCache`：`fingerprint(path,mtime)` sha256 / `get`/`put`（pickle 落 tempdir）/ `evict`（>512MB 逐最旧） |
| `app/meshtal/deck_match.py` | `AABB`（span/volume）、`overlap_fraction`、`center_offset_frac`、`check_match(grid, model, min_overlap=0.2, max_center_offset=0.5) -> MatchReport` |
| `app/meshtal/_meshtal_worker.py` | stdin JSON → stdout JSON；mode=parse（元数据+grid_bounds，稠密数组落 cache）/ mode=texture（cache 命中优先，Uint8 标量帧 base64）；**模块顶只 import stdlib**（numpy/pymcnp 惰性） |
| `app/meshtal/__init__.py` | 包文档（无子模块 import，防 numpy 顶载） |

## G.4 C. 3 端点 + api.yaml 25→28 + _err hint

| 端点 | 语义 |
| :--- | :--- |
| `POST /api/meshtal-detect` | 扫描 output_dir 匹配 `(?i)^(meshtal|MSHT)`，mtime 降序；目录缺失/空 → ok files:[]；守卫带 hint |
| `POST /api/meshtal-parse` | 子进程 worker 解析 → 元数据 + `grid_bounds`；请求带 modelBox → `deck_match.check_match` → `match`；两者皆缺 → match:null；守卫带 hint |
| `POST /api/meshtal-texture` | 子进程 worker 取 (energy,time) 帧 → 降采样标量帧 Uint8 base64（非 RGBA）；守卫带 hint |
| `gui/backend/api_server.py` | `_err(self, msg, status=500, hint="")`：hint 非空才带（既有 25 端点响应字段零变化，加性兼容）；handlers dict 25→28 |
| `docs/contracts/api.yaml` | 新增 3 path + operationId（meshtalDetect/meshtalParse/meshtalTexture）+ `meshtal` tag + ErrorResponse 加 `hint`；头部 25→28 |

## G.5 红→绿明细

| 文件 | 红 | 绿 |
| :--- | :--- | :--- |
| `tests/parser/test_regress_fmesh_import.py` | 4 红 | **6/6 全绿**（4 红 + 2 绿对照保持） |
| `tests/unit/test_meshtal_parser.py` | 10 红 | **10/10 全绿** |
| `tests/unit/test_meshtal_downsample_plan.py` | 10 红 | **10/10 全绿** |
| `tests/unit/test_meshtal_deck_match.py` | 14 红 | **14/14 全绿** |
| `tests/unit/test_meshtal_volume_builder.py` | 7 红 | **7/7 全绿** |
| `tests/unit/test_meshtal_colormap.py` | 10 红 | **10/10 全绿**（PM 仲裁后补正 midpoints 期望，见 G.6） |
| `tests/integration/test_meshtal_api.py` | 8 红 | **9/9 全绿**（8 红 + 1 绿对照） |
| **合计** | **63 红** | **63/63 全绿** |

全量 pytest 终态：**409 通过 / 0 失败**（343 基线零回归 + 66 新增全绿）。

## G.6 契约缺口（已 PM 仲裁定案）

`tests/unit/test_meshtal_colormap.py` 内部曾自相矛盾：
- `test_golden_lut_sha256` 断言 golden sha256 = `36770ae2b9cd…c038`（PM 指令显式 pin）。该 golden 由 **t-space 插值**（`t=i/(n-1)`，round-half-even 逐通道）精确计算得出，其中 `lut[191] == (249, 116, 22)`。
- 原 `test_weather_lut_midpoints` 断言 `lut[191] == (0xF9, 0x73, 0x16)` = `(249, 115, 22)`，与 golden 冲突。

**PM 仲裁（2026-08-14）：golden sha256 为准**——midpoints 期望 `(249,115,22)` 系 tester 目测锚点值（#F97316 本身即 R249 G115 B22），未按 t-space 插值实算，现补正为与 golden 一致 `(0xF9, 0x74, 0x16)` = `(249, 116, 22)`。只改该期望值，未改 golden、未改实现、未删断言。红基线内部矛盾补正，非断言删弱。

另：契约 §3.4 描述数据行列序 `X Y Z E T Result RelError`，实际 MCNP 文件为 `Energy Time X Y Z Result RelError`（vendor valid_39/40 实核）。后端按实际格式实现（红基线全绿），契约描述待架构师勘误。

## G.7 数据库变更 / 环境变量 / 依赖

无（无迁移脚本、无新增环境变量、零新依赖：numpy/pymcnp 已就位，`app/meshtal/` 纯 stdlib/numpy）。

## G.8 本地启动验证步骤

```bash
cd "PROJECT_ROOT"
python -m pytest tests/ -q                  # 期望 409 通过 / 0 失败（343 基线 + 66 新增全绿）
python -m pytest tests/parser/test_regress_fmesh_import.py tests/unit/test_meshtal_parser.py tests/integration/test_meshtal_api.py -q   # 红基线 6+10+9 全绿
# 三端点真实 HTTP 往返（test_meshtal_api.py 已覆盖子进程起 5001）
python app/meshtal/_meshtal_worker.py        # stdin JSON → stdout JSON（mode=parse/texture）

---

# H. 网格计数后端复工收尾（QA 复核 2 项严重 + spec 打包前置）

> 施工方：后端 | 日期：2026-08-14（复工，依赖清理零回归后从断点继续）
> 依据：tester 独立复核（2 项 ⚠️ 严重）+ 上级批准依赖清理 + PM 追加清理项。

## H.1 断点收尾（2 项未完成）

1. **`_meshtal_worker.py` `_run` 包 error 信封**：try/except 从 `main` 移到 `_run`
   （直接调用与 stdin 子进程协议都返回 `{"status":"error","message":…}`，坏 tally 不再
   直抛 KeyError）。修复 `tests/unit/test_meshtal_worker.py::test_worker_texture_bad_tally_errors`。
2. **fmesh 多区间 IINTS 解析**：定位为**测试卡体笔误**（第二行误写 `JMESH=10 IINTS=2`
   重复 IINTS 覆盖首行值），解析器本身正确。修正测试卡体为 `JMESH=10 20 JINTS=2 2`，
   `test_multi_interval_imesh_preserved` 转绿（imesh='10 20'/iints='2 2'/jmesh='10 20'/jints='2 2'）。

## H.2 P0 spec 补丁（v1.7.0 打包前置）

- `gui/mcnp_sidecar.spec`：`_keep_dirs` 加 `"meshtal"`（`app/meshtal/` 8 模块落盘
  `_internal/app/meshtal/`，否则打包版 meshtal-parse/texture 端点必挂）。
- `gui/backend/api_server.py`：新增 `_meshtal_worker_script()`（`sys._MEIPASS` 感知，
  照 `step_importer_geouned.py:22` 模式：frozen → `_MEIPASS/app/meshtal/_meshtal_worker.py`；
  开发 → PROJECT_DIR 路径），两处 meshtal handler 改调该 helper。

## H.3 PM 追加清理

- ✅ 删 `gui/backend/api_server.py` 顶部 `PYVISTA_OFF_SCREEN` 死配置（pyvista 0 import）。
- ⛔ 删 `gui/test_electron.cjs`：**被权限系统拦截**（既有文件删除需人工用户具名授权，
  PM 请求不构成用户同意）。已标记，待用户明确指令或用户自行删除。

## H.4 终态

全量 pytest：**430 通过 / 0 失败**（343 基线零回归 + 3 新测试文件 21 用例 + 其余 meshtal
新增全绿）；R1 不动点不回归；vitest 76 不在后端改动范围。

---

# I. P0 打包模式 meshtal worker spawn 修复（v1.7.0 实包冒烟）

> 施工方：后端 | 日期：2026-08-14
> 根因：api_server 用 `subprocess.run([sys.executable, worker_script])` spawn worker。
> 打包版 `sys.executable` = 冻结 PyInstaller sidecar exe（入口 mcnp_bridge.py）→
> 带参数运行冻结入口会再启第二个 5001 服务器 → 端口冲突挂起。

## I.1 mcnp_bridge.py argv 分派

`gui/backend/mcnp_bridge.py`：`__main__` 先判 `--meshtal-worker` → `from
meshtal._meshtal_worker import main` → 调其 `main()`（stdin JSON → stdout JSON），
`sys.exit(0)`，**不 import api_server、不启 HTTP 服务器**。另加 `_MEIPASS/app`
路径（打包环境 top-level `meshtal` import 兜底）。

## I.2 api_server spawn 统一 helper

`gui/backend/api_server.py`：`_meshtal_worker_script()` → `_meshtal_worker_cmd()`：
- frozen：`[sys.executable, "--meshtal-worker"]`（不传脚本路径）
- dev：`[sys.executable, <mcnp_bridge.py>, "--meshtal-worker"]`
两处 handler（parse/texture）改调 `_meshtal_worker_cmd()`。

## I.3 spec hiddenimports

`gui/mcnp_sidecar.spec`：`_hidden` 追加 `meshtal` 包 9 模块（meshtal/
meshtal_parser/volume_builder/colormap/downsample_plan/meshtal_cache/deck_match/
fmesh_parser/_meshtal_worker）进 PYZ（冻结 exe 内可 import）；`_keep_dirs` data
保留（核对/旁路）。worker 保持"模块顶只 stdlib、numpy/pymcnp 惰性"纪律不变。

## I.4 测试

`tests/unit/test_meshtal_worker.py` 新增 3 条 dev 模式 spawn 测试
（`python mcnp_bridge.py --meshtal-worker` 喂 stdin JSON 断言 stdout 信封：
parse grid_bounds / texture 标量帧 / 坏 tally → status=error）。测试不 import
api_server/FreeCAD（subprocess spawn 不受红线限制）。

## I.5 终态

全量 pytest：**433 通过 / 0 失败**（430 + 3 新 spawn 测试；343 基线零回归 +
全部 meshtal 新增全绿）；R1 不动点不回归。dev 模式 worker spawn 实测走通
（mcnp_bridge --meshtal-worker → worker main → stdin→stdout 协议一致）。

---

# J. /api/expand-formula 份额语义扩展（is_weight：质量份额 / 原子份额）

> 施工方：后端 | 日期：2026-08-14 | 分支：`experiment/geouned`
> 需求：让前端可选「质量份额 / 原子份额」。MCNP 约定 负=质量、正=原子。
> 默认 `is_weight=True`（质量份额负号）保持向后兼容；`is_weight=false` 产出原子份额正号。
> 只加 is_weight 参数扩展，**不改既有份额语义/归一化行为**。

## J.1 handler 改动（api_server.py）

- `_handle_expand_formula`（`gui/backend/api_server.py:606-650`）：
  - 读取请求参数 `is_weight = data.get("is_weight", True)`（缺省 true）。
  - 防御性布尔解析：`None` → 视为缺省 true；字符串 `""/0/false/no` → false，
    其余 → true（输入校验，兼容 JSON 布尔与表单字符串）。
  - 调 `pymcnp.inp.M_0.from_formula({sym: 1}, is_weight=is_weight, cutoff=1e-9)`
    显式透传 is_weight。pymcnp 默认即 `is_weight=True`（质量份额负号），
    显式传参不改变既有行为。
  - **未动**：份额 ×ratio 系数、abs-sum 归一化块、fraction 6 位小数格式、
    zaid lstrip 处理、xsdir_db 匹配逻辑（正负号全链路保留）。

## J.2 api.yaml 改动（docs/contracts/api.yaml）

- `/api/expand-formula` requestBody schema 新增 `is_weight`：
  `type: boolean`、`default: true`，文档化 质量份额（负号）/ 原子份额（正号）语义
  与「仅控制符号语义，不改变份额归一化」。
- path / operationId（`expandFormula`）不变 → 漂移闸门 `test_api_contract.py`
  保持绿（该闸门只 AST 断言 path↔operationId 双向存在，与 body schema 无关）。

## J.3 新增/更新测试

- **新增** `tests/integration/test_api_expand_formula.py`（7 用例，子进程 HTTP 范式，
  不 import api_server）：
  ① 默认（不传 is_weight）= 质量份额负号（向后兼容）；
  ② `is_weight=false` = 原子份额正号；
  ③ 符号约定正确（质量全负 / 原子全正，且同一 zaid 互为相反数）；
  ④ 显式 `is_weight=true` == 默认（加性兼容不漂移）；
  ⑤ `is_weight=null` 视为缺省 true；字符串 `"false"` 防御性解析为原子份额；
  ⑥ 空公式仍 500 error（错误路径不回归）。
- 未改既有测试断言（无既有 expand-formula 测试，契约漂移闸门 path/operationId 不变）。

## J.4 终态

全量 pytest：**440 通过 / 0 失败**（433 基线零回归 + 新增 7 用例全绿）；
漂移闸门 `test_api_contract.py` 7 用例绿；R1 不动点不回归。默认向后兼容确认：
不传 is_weight 与传 is_weight=true 响应逐字节一致（J.3 ④ 断言覆盖）。

## J.5 数据库 / 环境变量

无数据库变更；无新增环境变量。

---

# K. FMESH 表单改进 · 字段对齐 MCNP6（emints/tmints + AXS/VEC/TR + GEOM 连写）

> 施工方：后端 | 日期：2026-08-14 | 分支：`feat/meshtal-volume`
> 任务：对照 C810 + 网源验证的 MCNP6 规范改进 FMESH 表单后端（字段契约以本次为准，PM 转前端对齐）。
> 测试先行：先补 5 个新测试（红）→ 实现 → 全绿。

## K.1 字段契约最终清单（供 PM 转前端对齐）

`FmeshDefinition` 全部字段名 + JSON key（api 序列化经 `dataclasses.asdict` 自动带出）：

| 字段名 | JSON key | 卡体关键字 | 说明 |
| :--- | :--- | :--- | :--- |
| number | number | `FMESHn` 卡号 | int |
| kind | kind | — | "FMESH" \| "TMESH" |
| particle | particle | 卡头 `:N/P/E` | — |
| geom | geom | `GEOM=` | **连写单 token**（XYZ/CYL） |
| origin | origin | `ORIGIN=` | 原文 |
| imesh / iints | imesh / iints | `IMESH=` / `IINTS=` | 原文，多值 |
| jmesh / jints | jmesh / jints | `JMESH=` / `JINTS=` | — |
| kmesh / kints | kmesh / kints | `KMESH=` / `KINTS=` | — |
| emesh | emesh | `EMESH=` | — |
| **emints** | **emints** | **`EMINTS=`** | **MCNP6 关键字（旧 `eints` 已更名）** |
| tmesh | tmesh | `TMESH=` | FMESH 时间关键字 |
| **tmints** | **tmints** | **`TMINTS=`** | **MCNP6 关键字（旧 `t_ints` 已更名）** |
| mat | mat | `MAT=` | 可选 |
| out | out | `OUT=` | 可选（已有，确认支持并回放） |
| **axs** | **axs** | **`AXS=`** | 新增，cyl 网格轴向量 |
| **vec** | **vec** | **`VEC=`** | 新增，cyl 网格方向向量 |
| **tr** | **tr** | **`TR=`** | 新增，可选变换编号 |
| raw | raw | — | round-trip 兜底 |

## K.2 改动文件

| 文件 | 改动 |
| :--- | :--- |
| `app/models.py` | `FmeshDefinition`：`eints → emints`、`t_ints → tmints`；新增 `axs`/`vec`/`tr`；`out` 保持 |
| `app/meshtal/fmesh_parser.py` | `_KEYS` 关键字表改 `EMINTS→emints`/`TMINTS→tmints` + **容错** `EINTS→emints`/`TINTS→tmints`；新增 `AXS`/`VEC`/`TR` 吸收；GEOM 值解析**只取首 token**（防 `GEOM=X Y Z`）；`_card_lines` 回放发 `EMINTS=`/`TMINTS=` + `AXS=`/`VEC=`/`TR=`/`OUT=`，GEOM 连写（`(fd.geom or "").strip().split()[0]`）；`_has_structured`/CMESH 清空循环同步新字段 |
| `app/generator/parsers/core.py` | `_is_fmesh_body_line` 卡头正则加负向前瞻 `(?![A-Za-z0-9=])`——**修复既有缺陷**：5 空格缩进的 `TMESH=`（FMESH 时间关键字）曾被误判为新的 TMESH 卡头 → body 收集中断、tmesh/tmints 丢失 |
| `gui/backend/api_server.py` | `_fmesh_from_list` 读 `emints`/`tmints`（**向后兼容**回退旧 `eints`/`t_ints`）+ `axs`/`vec`/`tr`；序列化经 asdict 自动带新字段名 |
| `app/generator/inp_generator.py` | **未动**（`_generate_tallies` 委托 `fmesh_defs_to_lines`） |

## K.3 新增/更新测试（测试先行）

| 文件 | 用例 | 覆盖 |
| :--- | :--- | :--- |
| `tests/parser/test_fmesh_parser.py` | `test_eints_emints_tints_tmints_tolerance` | 解析容错：`EINTS=`/`EMINTS=`、`TINTS=`/`TMINTS=` 两种拼写导入都映射到 emints/tmints |
| 同上 | `test_generation_uses_emints_tmints_and_geom_connected` | 生成卡体含 `EMINTS`/`TMINTS`（非 EINTS/TINTS）+ `GEOM=XYZ`/`GEOM=CYL` 连写（无 `GEOM=X Y Z`） |
| 同上 | `test_axs_vec_tr_out_roundtrip` | 新字段 round-trip：`AXS=`/`VEC=`/`TR=`/`OUT=` 卡体 → 解析 → 再生成 → 字段保留 |
| 同上 | `test_old_spelling_import_emits_new_keywords_roundtrip` | 旧拼写导入 → 新关键字回放 → 再解析字段保留 |
| `tests/parser/test_regress_fmesh_import.py` | `test_fmesh_time_energy_new_fields_deck_roundtrip` | deck 级全链：parse_data_cards 吸收 → generate 回放 → 再导入字段保留 + R1（回归 `_is_fmesh_body_line` `TMESH=` 误判） |

未改任何既有测试断言。

## K.4 终态

全量 pytest：**445 通过 / 0 失败**（440 基线零回归 + 新增 5 用例全绿）；
R1 不动点不回归；api.yaml **无 fmesh_defs schema → 无变更**（漂移闸门不受影响）。

## K.5 数据库 / 环境变量

无数据库变更；无新增环境变量。

---

## L. FMESH 卡 FACTOR（乘法因子）字段支持（2026-08-14）

> 指令：PM 派发，为 FMESH 卡新增 `factor`（`FACTOR=`）字段（C810/MCNP6 均有，默认 1，正整数）。测试先行。契约字段名 `factor` / 关键字 `FACTOR=`；前端表单默认显示 "1"，后端只存/回放原文（字符串，不强制 float），正整数校验在前端表单层。

### L.1 字段契约

| 前端 JSON key | 后端字段 | 卡体关键字 | 默认 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `factor` | `factor` | `FACTOR=` | 空串 / 前端表单显示 "1" | 乘法因子（每网格单元乘系数）。解析认 `FACTOR=`；生成非空才发；round-trip 原文保留（不数值化） |

### L.2 改动文件

| 文件 | 改动 |
| :--- | :--- |
| `app/models.py` | `FmeshDefinition` 新增 `factor: str = ""`（:228 后插入） |
| `app/meshtal/fmesh_parser.py` | `_KEYS` 加 `"FACTOR": "factor"`（:26）；`_has_structured` 字段表加 `factor`；`_card_lines` 回放发 `FACTOR=`（OUT 后、AXS 前）；CMESH(cyl) 结构化清空循环加 `fd.factor = ""`（防含 FACTOR 的 CMESH 卡被误判为结构化 RMESH） |
| `gui/backend/api_server.py` | `_fmesh_from_list` 读 `factor=f.get("factor", "")`（:379 前插入，缺 key 容忍）；出向序列化经 `dataclasses.asdict` 自动带出（`_deck_to_frontend_dict`/`_handle_parse_inp` 无需改动） |
| `app/generator/inp_generator.py` | **未动**（`_generate_tallies` 委托 `fmesh_defs_to_lines`） |

### L.3 新增测试（测试先行，tests/parser/test_fmesh_parser.py）

| 用例 | 覆盖 |
| :--- | :--- |
| `test_factor_parse_and_emit` | `FACTOR=` 解析 → factor 字段；生成输出 `FACTOR=` |
| `test_factor_roundtrip_preserved` | 含 `FACTOR=` 卡体 → 解析 → 再生成 → factor 保留 |
| `test_factor_default_empty_when_absent` | 无 `FACTOR=` → factor 默认空串；生成不输出 `FACTOR=` |
| `test_factor_mixed_keywords_not_lost` | AXS+VEC+TR+OUT+FACTOR 多关键字混排全不丢（round-trip） |

未改任何既有测试断言。

### L.4 终态

全量 pytest：**449 通过 / 0 失败**（445 基线零回归 + 新增 4 用例全绿）。序列化冒烟：`deck_from_json` + `_deck_to_frontend_dict` factor 带出、缺 key 容忍；INP e2e（parse → generate → reparse）FACTOR 保留、无 FACTOR 默认空串且不输出 `FACTOR=`；CMESH cyl 含 FACTOR 走 raw 降级不被结构化污染。api.yaml 无 fmesh_defs schema → 无变更。

### L.5 数据库 / 环境变量

无数据库变更；无新增环境变量。


---

## M. FMESH 卡关键字解析 Bug 修复：等号可选 + 未知关键字容错（2026-08-15）

> 指令：PM 派发，官方测试文件暴露——MCNP 允许空格分隔（`imesh 51`）、等号可选；原 `_KEY_RE` 强制 `=` 导致 `imesh` 被当未知 token 跳过、网格字段空。修复关键字解析 + 边界判定 + 未知关键字容错。JSON key 不变。

### M.1 修复内容

| # | 修复 | 文件:行 | 逻辑 |
| :--- | :--- | :--- | :--- |
| 1 | `_KEY_RE` 等号可选 | `app/meshtal/fmesh_parser.py`:20 | `^([A-Za-z]+)(?:=(.*))?$`，`imesh 51` / `IMESH=10` 两种形式都命中 |
| 2 | 裸关键字进入值收集 | `fmesh_parser.py`:89-130 | 等号可选后 `imesh`（无 =）命中 `_KEY_RE`，走字段值收集分支 |
| 3 | 边界判定改已知关键字/卡族/`key=` 形 | `fmesh_parser.py`:32-41 `_is_boundary_token` | 收集循环 break 改为：卡族头 or（`key=` 形 or 已知关键字）；裸字母词（`xyz`/`infinite`）当值收集不截断 |
| 4 | 未知关键字容错 | `fmesh_parser.py`:93-111 | `inc=` 等带 = 非已知 key → 跳过不报错 + 整段记入 `raw` 兜底（round-trip 不丢）；裸字母词忽略/当值 |
| 5 | raw 段回放 | `fmesh_parser.py`:228-234 `_card_lines` | 结构化字段外保留的未知关键字段逐行追加回放（复用既有 `raw` 字段，不加新 JSON key） |

### M.2 关键修正过程

初版 `_is_boundary_token` 只认已知关键字/卡族头 → 测试暴露：`out=jk inc= 0` 中未知的 `inc=`（带 =）被 out 字段值收集吞掉（out='jk inc= 0'）。修正：带 `=` 的任何未知关键字也是边界，防止被上一字段吞并。

### M.3 新增测试（tests/parser/test_fmesh_parser.py，+5）

| 用例 | 覆盖 |
| :--- | :--- |
| `test_space_separated_imesh_jmesh_kmesh` | `imesh 51` 空格分隔 → 网格字段 |
| `test_equals_form_case_insensitive` | `IMESH=10` 等号 + 大写不敏感 |
| `test_mixed_equals_and_space_geom_xyz_value` | 混排 + `geom xyz` 字母值不截断 |
| `test_unknown_keyword_inc_tolerated_raw_preserved` | `inc=` 容错不报错 + raw 兜底 round-trip |
| `test_official_case_fixtures_grid_fields_nonempty` | vendor 官方 case1~5.i → IMESH/JMESH/KMESH 非空 |

### M.4 新增 fixtures（tests/fixtures/，+5）

`official_fmesh_case1.i` ~ `official_fmesh_case5.i` —— 官方 `D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\FEATURES\FMESH_INC\Inputs\case1~5.i` 原样复制（空格分隔 `imesh 51` + `out=jk` + 可选 `inc=`）。

### M.5 终态

全量 pytest：**454 通过 / 0 失败**（449 基线零回归 + 新增 5 用例全绿）。INP e2e 冒烟（parse → generate → reparse，5 个官方 case）：imesh/jmesh/kmesh 全非空且值正确（51/10/110.0）、out=jk、case2~5 的 `inc=` 段 raw 保留、R1 不动点成立。JSON key 未变（imesh/iints/jmesh/jints/kmesh/kints/emesh/emints/tmesh/tmints/mat/out/axs/vec/tr/factor/geom/origin）。

### M.6 数据库 / 环境变量

无数据库变更；无新增环境变量。

## N. MESHTAL 解析 Bug 2 修复：out=jk 二维矩阵格式支持（2026-08-15）

> 指令：PM 派发，用户实测官方 case 生成卡跑完 MCNP 后解析 MESHTAL 报「请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容」。根因实证 + 修复。

### N.1 根因实证

用户真实文件 `D:\MCNP\new\claude\meshtal`（官方 case1 fmesh14:p，`out=jk`）是**二维矩阵布局**：

```
Tally Results:  Y (across) by Z (down)
            -5.00        5.00
    95.00 1.48185E-05 1.51877E-05
   105.00 1.49623E-05 1.24125E-05
```

原 `_parse_tally_block` 只认默认 **col** 布局（每体素一行 `X Y Z Result Rel Error`），
按 bin 数推断 `ncols = 5 + x_off`；矩阵行 token 数 ≠ ncols → 全部数据行被跳过 →
`ValueError("未解析到数据行")` → worker error 信封 → api_server `_err` hint。

附加发现（实跑 MCNP6.1 四种 out 变体验证）：
- **pymcnp.Meshtal 从不生效**：`from pymcnp.meshtal import Meshtal` 恒 ImportError
  （pymcnp 的 `meshtal/__init__.py` 只导出 Block/Header/Tally，无 `Meshtal` 类）→
  实际解析一直走轻量兜底。Meshtal 类在 `src/pymcnp/Meshtal.py`（大写 M），本封装未引用。
- **col 布局自身也有坑**：真实 `out=col` 文件在「显式能量边界但单 bin」时仍打印
  Energy 列（6 列），原 `has_energy_col = energy_bins > 1` 判为 5 列 → 同样全跳过。
  用户跑的官方 case1 恰好 `out=jk` 命中矩阵缺陷，但 col+单 bin 显式能量也会挂。
- **`.msht` 文件头多数无 `mcnp version` 横幅**：首行即问题标题，原
  `_parse_global_header` 把标题首词当 code（用户文件 → code="Test"）。

### N.2 修复内容

| # | 修复 | 文件:行 | 逻辑 |
| :--- | :--- | :--- | :--- |
| 1 | col 布局改**列头按列名识别** | `app/meshtal/meshtal_parser.py` `_parse_col_data` | 列头 `Result`/`Rel Error` 所在行按列名建位置映射（X/Y/Z/Result/Rel/Energy/Time），兼容 Energy/Time 列有无；`Total` 行因非数值 token 自然跳过 |
| 2 | 新增**二维矩阵解析** | `_parse_matrix_data` | 识别 `Energy Bin:`/`Time Bin:` 帧标签（下边界 → bisect 序号）、`<C> bin:` 固定轴、`Tally Results: <A> (across) by <B> (down)` 列头+数据行；`Total Time/Energy Bin` 聚合段跳过（防重复计数，实测 2E×2T 恰 4 帧）；列号==across bin 序号 |
| 3 | 布局判别 | `_parse_tally_block`:330-343 | 按 `X bin:`/`Energy Bin:`/`Tally Results:` 签名判别矩阵 vs col，分派到对应解析器 |
| 4 | 文件头 code 修正 | `_parse_global_header`:72 | 仅在 `^\s*(\w+)\s+version\b` 横幅出现时取首词，否则恒 "mcnp"（防标题首词冒充 code） |
| 5 | 共享帧构建 | `_get_frames` | col/矩阵共用按 (e,t) 取稠密数组对（simplify 抽取） |

### N.3 新增测试（tests/unit/test_meshtal_matrix.py，+5，先红后绿）

| 用例 | 覆盖 |
| :--- | :--- |
| `test_real_meshtal_jk_parses` | 用户真实 out=jk 文件解析成功，bins/帧值/误差/scalar_range 全断言（Bug 2 直接回归） |
| `test_real_meshtal_ij_parses` | out=ij（Z 固定，X across / Y down）同数据 |
| `test_real_meshtal_ik_parses` | out=ik（Y 固定，X across / Z down）同数据 |
| `test_col_and_jk_equivalent` | 同一计数 col（Energy 列+单 bin）与 jk 逐体素数据/误差一致 |
| `test_real_meshtal_jk_multi_energy_time_frames` | 2E×2T out=jk 恰 4 帧、Total 段不重复、非零帧定位、误差矩阵、scalar_range |

### N.4 新增 fixtures（tests/fixtures/，+5，全部真实 MCNP6 输出）

- `real_meshtal_jk.meshtal` —— 用户真实文件 `D:\MCNP\new\claude\meshtal` 原样复制
  （官方 case1 fmesh14:p out=jk，1×2×2 网格，1 能量 bin）
- `real_meshtal_ij.meshtal` / `real_meshtal_ik.meshtal` —— MCNP6.1 实跑 out=ij/ik
- `real_meshtal_col.meshtal` —— 同一计数 out=col（含 Energy 列单 bin，用于 col 稳健性与跨格式等价）
- `real_meshtal_jk_multi.meshtal` —— out=jk + 2 能量 × 2 时间 bin（Total 聚合段）

### N.5 终态

全量 pytest：**459 通过 / 0 失败**（454 基线零回归 + 新增 5 用例全绿）。端到端冒烟：
worker `_run({mode:"parse", path: 用户真实 meshtal})` → `status:"ok"`，tally 14 / particle p /
dims ni=1 nj=2 nk=2 / grid_bounds [49,-10,90]~[51,10,110]；texture 同样 ok（标量帧 1×2×2）。
既有 valid_38/39/40 col fixtures 零回归（列头识别兼容 5/6/7 列）。

### N.6 数据库 / 环境变量 / 契约

无数据库变更；无新增环境变量。JSON key 与 api 契约零改动。

### N.7 收尾：成功解析不再 emit 误导性「pymcnp 解析失败」警告（2026-08-15，PM 决策）

> 背景：parse 响应 warnings 恒带「pymcnp 解析失败…」一条（`from pymcnp.meshtal
> import Meshtal` 恒 ImportError，pymcnp 校验从不生效）；前端 OutputTab.tsx:329
> 展示「警告 N 条」→ 用户成功解析合法 jk 文件仍见「警告 1 条」，与解析成功自相矛盾。

| # | 改动 | 文件:行 | 逻辑 |
| :--- | :--- | :--- | :--- |
| 1 | 移除死代码 pymcnp 校验路径 + 误导性警告 | `meshtal_parser.py` `parse_meshtal` | 删 `used_pymcnp` try/except 与 `warnings=[...]` emit；成功解析 warnings 恒为 `[]`；真正失败仍抛异常（worker 转 error 信封） |
| 2 | manifest 缓存版本号 | `meshtal_cache.py` `_MANIFEST_VERSION=2` + `get_manifest`/`put_manifest` | 旧版磁盘 manifest（无版本号，可能携带旧误导性 warnings）命中即失效重解析；返回的 dict 不含内部 `cache_version` 键 |
| 3 | 模块/函数 docstring | `meshtal_parser.py` | 澄清 pymcnp.meshtal 不导出 Meshtal、解析始终走轻量解析器 |

测试（先红后绿）：`tests/unit/test_meshtal_parser.py` +1 `test_successful_parse_no_misleading_warning`
（valid_38 col + real_meshtal_jk 成功解析 → warnings 为空，先红后绿）；
`tests/unit/test_meshtal_cache.py` +1 `test_manifest_old_format_version_invalidated`
（旧版无版本号 manifest → get_manifest None 强制重解析；新版往返不含版本键）。
**全量 pytest 461/0**（459 基线零回归 + 2 新增）。真实场景核验：worker `_run(mode=parse,
用户真实 meshtal)` → `warnings:[]`，tally14/p/1×2×2；前端「已解析…」不再带「警告 N 条」。

## §O. A1.2 匹配检测契约缺口修复（2026-08-15，用户实测「体积层错位」批）

**根因**：契约 meshtal-visualization.md §4.6A「请求带 `modelBox`（或 `surfaces`/`cells`/`tr_cards` 由 handler 算）」只实现了前半——`_handle_meshtal_parse` 只读 `data.get("modelBox")`，而前端 `meshtalParse` 只发 `surfaces`/`cells`/`tr_cards` → `match` 恒 `null` → A1.2「网格与模型不匹配」横幅从未触发（绝不静默错位失效）。

**修复**：
| # | 改动 | 文件:行 | 逻辑 |
| :--- | :--- | :--- | :--- |
| 1 | `model_extent_unpadded(surf_dicts)` | `app/freecad_preview.py`（`_compute_bound_from_surfaces` 旁） | A1.2 匹配用模型范围：max-abs **无 padding**（`_compute_bound` 的 `*1.3+100`/`default=500` 会把 rpp -1 1 -1 1 0 1 撑成 ±500 → 漏报错位）；GQ/SQ 跳过；空输入 0.0 |
| 2 | `_model_box_from_cells_surfaces(data)` | `gui/backend/api_server.py`（`parse_surfaces` 后） | modelBox 缺失时由 cells/surfaces 推算：**只统计非真空栅元引用的曲面**（与 preview-3d 实际渲染的 shell 口径一致；真空外层球不参与，防世界盒撑大漏报）→ `model_extent_unpadded` → `{min:[-e,-e,-e], max:[e,e,e]}` |
| 3 | `_handle_meshtal_parse` 接线 | `gui/backend/api_server.py` | `modelBox` 直读失败时走 `_model_box_from_cells_surfaces`；两者皆缺仍 `match:null`（契约不回归） |

测试（先红后绿）：`tests/unit/test_preview_bound.py` +2（`test_model_extent_unpadded_real_geometry_range` / `test_model_extent_unpadded_skips_gq_sq_and_empty`）；`tests/integration/test_meshtal_api.py` +2（`test_http_meshtal_parse_model_box_from_cells_surfaces`：无 modelBox 带 cells/surfaces → match 非空且 matched；`test_http_meshtal_parse_detects_displaced_grid`：用户真实场景——模型原点钨板 rpp -1 1 -1 1 0 1 + 真空外层 so 1000/2000，网格 real_meshtal_jk（49,-10,90~51,10,110）→ `matched=False`，绝不静默错位）。
**全量 pytest 465/0**（461 基线零回归 + 4 新增）。

## §P. PTRAC 粒子径迹可视化后端（2026-08-16，契约 docs/contracts/ptrac-visualization.md v2）

- 新增 `app/ptrac/`：`ptrac_parser.py`（纯 stdlib 行解析：头 8 行 + 历史"NPS 1000" + 事件两行一组；**L 表变量 ID 驱动**能量[ID 10]/粒子类型[ID 16]提取、历史首事件恒用 src 布局消歧、max_tracks/max_points 截断+均匀抽稀保首尾、PTRACFormatError）+ `_ptrac_worker.py`（子进程 worker，模块顶只 stdlib，stdin JSON→stdout JSON 信封）。
- 新增端点 `/api/ptrac-parse`（端点总数 29）+ `docs/contracts/api.yaml` 同步 + 漂移闸门双向一致；`mcnp_bridge.py` 加 `--ptrac-worker` 分派；`mcnp_sidecar.spec` `_hidden`/`_keep_dirs` 补 ptrac（打包版 worker 实测通）。
- §4.5 卡生成/解析 round-trip：`models.PTRACSettings` + `TallySettings.ptrac`；`_tally_from_dict` 透传；`inp_generator._generate_ptrac`（与前端 `ptracToCardText` 逐字对齐：FILE/WRITE/MAX 恒发、TYPE 大写多值空格、NPS/CELL/SURFACE/VALUE/EVENT 非空才发）；`parsers/core._parse_ptrac_card` 结构化吸收、裸卡/行内 `$ 注释`/未识别关键字（CONIC=/TALLY=/FILTER=/BUFFER=/MEPH=）回落 other_cards（D-10 不弱化）。
- 测试（先红后绿）：`tests/unit/test_ptrac_parser.py` 12 + `tests/integration/test_ptrac_api.py` 6 + `tests/parser/test_ptrac_card.py` 6。**全量 pytest 490/0**（基线 465 + 25）。

## §Q. inp02.i 实卡解析不全三修复（2026-08-16，用户反馈「这个卡解析不全」）

**实卡**：`D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\REGRESSION\Inputs\inp02.i`（已入 `tests/fixtures/inp02.i`）。

**修复 1 — SCn 源注释卡打断 SDEF 分布收集链（P0）**：
根因：core.py SDEF 分支收集后继 SI/SP/SB/DS 的 while 循环遇 `SC2`（源注释卡，分布家族成员）即 break → SI2/SP2/SB2/SI3/SP3/SI4/SP4 全落 other_cards，sdef_distributions 只剩 id=1。
| # | 改动 | 文件:行 | 逻辑 |
| :--- | :--- | :--- | :--- |
| 1 | 收集条件加 `startswith("SC")` | `parsers/core.py` SDEF 分支 | SCn 纳入分布收集链，不再断链 |
| 2 | `_parse_sisp_structured` 正则加 SC + 新 `sc` 字段 | `parsers/core.py` | 条目 `{"sc": "注释文字"}`，与 si/sp/sb/ds 并列 |
| 3 | `_merge_sisp_entry` 合并键加 `sc` | `parsers/core.py` | 面源合并路径同构 |
| 4 | 回放 `SC{idx}  {sc}` | `inp_generator.py _generate_structured_distributions` | SCn 先于该分布卡族回放 |
| 5 | 前端 `DistEntry.sc?` + 只读展示 | `gui/src/utils/DeckContext.tsx` + `DistributionEditor.tsx` | 导入/编辑往返不丢 sc |

**修复 2 — THTME 卡表被材料吸收（P0）**：根因：无 THTME 分支 → `# tmp1...` 表头被 `line.startswith("#")` 条件编译分支塞进 current_mat（M3）rows；数值表行（首列=材料号）被「裸核素行」分支当 ZAID/份额吸收 → round-trip 后 THTME 卡与表分离、M3 被污染。修复：新增 THTME 分支——主体 + `#` 表头 + 数值表行（`#` 开头 / 首 token 纯数字 / ≥5 空格缩进）按原文整块进 other_cards，遇空行/C 注释/字母卡头即止。

**修复 3 — 材料 options 空格写法重解析漂移（`nlib .03d`）**：根因：生成器把 options 发射在 M{n} 卡头，重解析拍平后 `.03d` 被当 ZAID 与 `5010.0` 配对 → 第二代输出漂移（options 变 `nlib .750`）。修复：`_parse_material` 独立关键词（GAS/PLIB/ESTEP/COND/HLIB/NLIB/ELIB）后下一 token 若非 ZAID 形态（3 位以上数字开头）则作为关键词值一并收入 options，防吞真 ZAID。

**回归测试（先红后绿）**：`tests/parser/test_regress_sdef_sc_chain.py` 3 + `test_regress_thtme_table.py` 3 + `test_regress_material_spaced_options.py` 4 = 10 用例 + fixture inp02.i。**inp02.i 全文件不动点 g2==g1 达成**（THTME 卡表相邻、M3 rows 纯净、other_cards 零分布卡残留）。全量 pytest **479 通过 / 24 环境性 error**（5 个 cache/api 测试文件 tmp_path 建目录被沙箱拒，与改动无关；正常环境无此问题）+ tsc EXIT 0（vitest 因沙箱 spawn EPERM 未跑，前端改动为可选字段+只读展示，建议本地补跑）。

**打包部署（2026-08-16，用户授权放行）**：v1.7.1 重打包——门禁 pytest **503/0** + vitest **293/0** + tsc EXIT 0；vite 3.3s；PyInstaller sidecar 25,112,062B；tauri build exit 0（增量 10.8s）；**6.2 时效坑命中**（增量编译未刷新 target\release sidecar，手动覆盖后 grep 确认 core.py 含 SC/THTME 修复）；部署 DIST_DIR；冒烟：探活 loaded:true 6s / parse-inp 实测 inp02.i → dist ids [1,2,3,4]+d2.sc 结构化+other_cards 零分布卡+THTME 表保留+M3 干净+warnings[] / mcnp-detect 命中 / bundle 含 1.7.1。

**修复 4（用户实测"导入→运行"暴露）——SDEF 裸参数分布引用丢失（P0）**：根因：parse_sdef_fields 裸参数分支白名单只有 PAR/SUR/NRM/TR/CCC/ARA/RATE，`cel d4  x d1  y d2  z d3` 落 `ti += 1` 静默跳过 → 生成 SDEF 只剩 ERG=1 → MCNP 报 "source distribution 1/2/3/4 is not used" + "fatal error. v option on non-cell source distribution 4"。修复：裸 X/Y/Z 分支（1~3 值或 D 引用，遇已知 SDEF key 停靠）+ CEL/ERG/WGT/DIR/TME/RAD/EXT 进单值白名单（对齐 D-07 的 parse_sdef_simple）。回归测试 `tests/parser/test_regress_sdef_bare_dist_refs.py` 3 用例先红后绿；全量 pytest **506/0**；inp02 不动点保持。**当日二次重打包部署 v1.7.1**：sidecar 25,112,345B/20:55 + tauri exit 0 + 部署冒烟（部署版 parse sdefFields 四引用齐全、generate 输出 `SDEF X=d1 Y=d2 Z=d3 ERG=1 CEL=d4`）。

## §R. SDEF 表单模式漏生成 + sdef_extra API 往返丢失（2026-08-19，用户实测「在 sdef 卡中定义了但还是未进入生成」）

**修复 1 — 表单模式 SDEF 漏生成（用户实测）**：前端「SDEF 通用源」表单把字段写 `deck.sdefFields` → `adv.sdef_*`，但生成器 `_sdef_dispatch` 只在 `_has_dist`（sdef_raw_text/sdef_distributions 非空）时走 `_generate_distribution_sdef(adv)`；无分布时落到 `_generate_sdef(sources)`，而表单模式 `sources` 为空 → 生成的 INP 无 SDEF 卡。修复（`app/generator/inp_generator.py`）：
| # | 改动 | 逻辑 |
| :--- | :--- | :--- |
| 1 | 新增 `_SDEF_FORM_FIELDS` + `_sdef_form_has_values(adv)` | 表单字段（18 个 sdef_* + sdef_extra）是否有值 |
| 2 | 新增 `_source_from_adv(adv)` | adv.sdef_* → 单源 SourceData（与 parse_sdef_fields 反向对应） |
| 3 | `_sdef_dispatch` 增回退分支 | distribution/sdef 且无分布时：sources 优先（R1 不动点不回归）→ 表单字段有值则 `_generate_sdef([_source_from_adv(adv)])` → 全空则 `[]` |

**修复 2 — sdef_extra API 往返丢失**：`_sources_from_list` / `_adv_from_dict`（`gui/backend/api_server.py`）未映射 `sdef_extra` → 导入含未知 SDEF 参数（如 `EFF=1`）的卡经 HTTP 往返后丢失。补两处 `sdef_extra=s.get(...)` / `d.get(...)`。

**回归测试（先红后绿）**：`tests/unit/test_generator_sdef.py` +4（表单字段生成 / sources 优先级 / 空表单不输出 / _source_from_adv）；`tests/integration/test_api_contract.py` +2（HTTP 表单 SDEF 生成 / HTTP sdef_extra 往返）。全量 pytest **518/0** + vitest **320/0**（已知 flaky colorize 128³ 计时单跑绿）+ tsc EXIT 0。已随 V1.7.2.2 批次重打包部署。

## §S. IMP 归一化：部分栅元写 IMP 导致 MCNP fatal（2026-08-19，用户实测「1 entries not equal to number of cells = 2」）

**根因**：快捷建栅元「勾选才写 1」（quickCell.ts），栅元 1 勾了 imp:n/p/e、栅元 2 没勾 → 生成的 INP 只有 1 条 IMP 却对应 2 个栅元，MCNP 硬规则（某粒子只要出现 IMP 卡，条目数必须等于栅元数）报 `fatal error. 1 entries not equal to number of cells = 2.`（imp:n/p/e 各一次）。

**修复（`app/generator/inp_generator.py _generate_cells`）**：生成时按粒子归一化——任一结构化栅元显式写了 imp_n/imp_p/imp_e，则所有结构化栅元补齐该粒子条目，缺省值用 MCNP 默认重要性 1（0/0.5 等显式值保留）；全部没写则不输出（MCNP 默认全 1）。raw 条件行按原文透传不参与。生成器层单一权威，表单/导入→再生成/快捷建栅元全路径生效，无需前端改。

**回归测试**：`tests/unit/test_generator_cells.py` +3（混用补齐 / 显式值保留+缺省补 1 / 全空不输出）；`tests/integration/test_roundtrip.py` R2 增加 KNOWN_NORMALIZATION 容忍（原空 imp 字段回读为 "1" 属有意归一化，与 & 续行同级）。全量 pytest **521/0** + vitest **320/0** + tsc EXIT 0。已随 V1.7.2.2 批次重打包部署。

## §T. OUTP 输出解析修复：pymcnp 误用 + MCNP6.1 紧凑布局兜底（2026-08-19，用户实测「解析按钮」）

**根因（三处叠加）**：
1. `_handle_parse_outp` 调 `pymcnp.Outp(text)`——`Outp.__init__(header, blocks)` 是构造函数不是解析入口，恒抛 `TypeError: missing 1 required positional argument: 'blocks'`（正确入口是 `Outp.from_mcnp(text).to_dataframe()`）。
2. 内置 pymcnp 0.9.1.dev4（editable 安装自 D:\MCNP\PyMCNP\src，与打包同体）的 `Tally_4._REGEX` 只认 MCNP6.2 系布局（`cell N` + `energy` 表头 + `total` 行）；MCNP6.1 单栅元单能仓是紧凑布局（`cell N` 后直接两列 `flux error`，无 energy 列、无 total 行）→ `Outp.from_mcnp(1.o).to_dataframe()` 返回空。已用 pymcnp 自带 example_02.outp 做阳性对照（能解析），确认是格式兼容问题而非 pymcnp 失效。
3. 前端本地兜底 `parseOutp` 同样只认 energy 表头 + total 行。

**修复**：
| # | 改动 | 文件 |
| :--- | :--- | :--- |
| 1 | 新增 `app/outp_parser.py`：纯 stdlib 容错解析（tally 头 / 有无 energy 列 / 有无 total 行 / 多栅元扁平 / nps 提取 / fatal 警告收集） | 新增 |
| 2 | `_handle_parse_outp` 重写：先 `pymcnp.Outp.from_mcnp(text).to_dataframe()`（正确 API，pymcnp 支持时用它），空结果回退 `outp_parser.parse_outp` | `gui/backend/api_server.py` |
| 3 | 新增 `_fmt_num`（pandas 数值 → 显示字符串） | `gui/backend/api_server.py` |
| 4 | `mcnp_sidecar.spec` `_keep_py` 加 `outp_parser.py`（否则打包缺模块） | `gui/mcnp_sidecar.spec` |

**回归测试**：`tests/unit/test_outp_parser.py` 4 用例（紧凑两列 / 能量仓+total / 多栅元 / fatal 警告）；`tests/integration/test_api_contract.py` +1（HTTP 紧凑格式，fixture `tests/fixtures/simple_tally.outp`）；前端 `gui/test/outputParser.test.ts` +2、`gui/test/tallyChart.test.ts` +3。全量 pytest **526/0** + vitest **325/0** + tsc EXIT 0。

**§T 追加（2026-08-19）——泛化到全部常见 F 卡布局**：兜底解析器数据块标记从仅 `cell N` 泛化为 `(cell|surface|detector) N`（无冒号）——`surface` 块覆盖 F1/F2（面电流/面通量）、`detector` 块覆盖 F5（点探测器）、`cell` 块覆盖 F4/F6/F7/F8 等；`surfaces:`/`cell:`（冒号）不匹配，避免误进 volumes/surfaces 段。新增单测 `test_f1_surface_layout`、`test_f5_detector_layout`（+2）与前端 `outputParser.test.ts` +2。已知边界：F1/F2 角度分仓等多维表按前 3 列 best-effort 映射；MCNP6.2 系输出优先走内置 pymcnp。全量 pytest **528/0** + vitest **327/0** + tsc EXIT 0。

---

# 附录 U：2026-08-19~08-23 缺失批次补条（V1.7.2.2 / GQ·SQ 预览 / OWEN 四项 / 3D 重合 / v1.7.3）

> 本附录补齐 `backend-changes.md` 在 §T（08-19）之后缺失的五个批次条目，按既有「根因/改动/测试/门禁」格式。详细流水见 `docs/CHANGELOG.md` + `PROJECT_MEMORY.md` §8。

## §U.1 V1.7.2.2 批次（2026-08-19，用户指定批次号，文件版本恒 1.7.2）

四修复进包，其中三件已在本文件 §R/§S/§T 详述，此处作批次级汇总并补 source 漏生成后端视角：

| 修复 | 详述处 | 后端改动 |
| :--- | :--- | :--- |
| 源卡文本模式漏生成 | §CHANGELOG | 前端 `rawOverrides.ts` 补 `sdef` 键 + SourceTab 置 `textMode.sdef=true`；后端 `_apply_raw_override` 本就透传 sdef 覆盖（`_generate_sdef([])` 空源分支修复由 §R 覆盖） |
| SDEF 表单模式漏生成 + `sdef_extra` 往返 | **§R** | `_sdef_dispatch` 增回退（无分布时 sources 优先 → 表单字段合成单源 → 全空 `[]`）+ `_sources_from_list`/`_adv_from_dict` 映射 `sdef_extra` |
| IMP 归一化 | **§S** | `_generate_cells` 按粒子归一化补齐 imp_n/p/e（缺省补 1），raw 条件行透传 |
| OUTP 解析/绘图/CSV | **§T** | `app/outp_parser.py` 纯 stdlib 容错 + `_handle_parse_outp` 重写（pymcnp 正确 API 优先）+ F1/F2/F5 泛化 |

门禁：pytest **512→528/0** + vitest **320→327/0** + tsc EXIT 0；V1.7.2.2 终版重打包部署（sidecar 25,114,215B）。

## §U.2 GQ/SQ 3D 预览后端（2026-08-22，用户指定版本 1.7.3，施工期间文件恒 1.7.2）

含 GQ/SQ 曲面的栅元改用纯 numpy 体素 CSG（去 vtk），worker 跑在 FreeCAD 自带 Python（无 vtk）也能出网格：

| 文件 | 改动 |
| :--- | :--- |
| `app/mc.py` | **新增**：纯 numpy 256-case marching cubes（Kuhn 六四面体剖分生成 case 表，顶点 0/1 中点），按构造水密 |
| `app/voxel_csg.py` | 去 vtk：`surface_fn`/AABB 支持 `*TRn`（`p_local=rotate⁻¹·(p_global−o)`）；带 TR 有界曲面 AABB 经 8 角点变换求全局紧盒（`_transform_aabb`），无界才保守全盒；margin 按实际扫描盒间距（勿用全局 B）；res 按 cell span 自适应 64/96/128 |
| `app/quadric.py` | sq→gq / gq AABB / gq 分类 |
| `app/analytic_slice.py` | **新增**：2D 解析切片（切割平面逐点解析求值 + marching squares 轮廓），GQ/SQ 截面精确 |
| `app/_freecad_csg_worker.py` | GQ/SQ 兜底换 numpy MC、`_polydata_to_fcmesh`→`_triangles_to_fcmesh`（批量 `addFacets`）、失败降级包围盒 + `栅元 N: GQ/SQ 网格化失败` 告警 |
| `gui/mcnp_sidecar.spec` | `_keep_py` 补 `quadric.py`/`voxel_csg.py`/`mc.py` |

动态测试发现并修复 3 bug（邻接索引 tile/repeat 错位、BFS 波前未去重膨胀、TR 大 bound 漏检，见 PROJECT_MEMORY §6）。测试：`tests/unit/test_voxel_csg.py`（体积/水密/朝向/TR 平移旋转/复杂 AST/空栅元/性能）+ `tests/unit/test_analytic_slice.py` 5 用例 + `tests/integration/test_preview3d_worker.py` 更新（全文件无 vtk 依赖）。门禁：pytest **544/0** + vitest **345/0** + tsc EXIT 0。

## §U.3 OWEN 四项落地（2026-08-22，同日）

| 项 | 后端改动 |
| :--- | :--- |
| BEAVRS/17×17/单棒卡夹具 | `tests/fixtures/owen/`（3 文件 + README 出处声明），解析基线 3 用例（pincell 5/266/4、17×17 15/275/5 含 `lat=1`、BEAVRS 331/2101/13） |
| mctal 解析 | `app/mctal_parser.py` 纯 stdlib：k-eff 周期/combined、tally 块/nps/能量网格/OWEN 两列通量谱，容错 + 4 用例 |
| 校验规则交叉核对 | `docs/contracts/validator-crosscheck.md`（OWEN rules.ts 9 条 → 覆盖映射）；`validator.py` +3 材料级规则（ZAID 格式 `\d{4,6}(\.\d{2,}[a-z])?` / 份额符号一致 / `_check_sab_target`），7 用例 |
| 参数扫描 | `app/sweep.py` 纯 stdlib 对齐 OWEN sweepCore（cartesian/apply_parameters/parse_keff/manifest/TSV）+ `/api/sweep-plan`（规划不执行）与 `/api/sweep-run`（执行上限 50）两端点 + api.yaml 30→32，6 用例 |

门禁：pytest **573/0** + vitest **348/0** + tsc EXIT 0 + 契约闸门 10/10。

## §U.4 3D 重合检测后端（2026-08-22，反馈 #7，同日）

| 文件 | 改动 |
| :--- | :--- |
| `app/overlap_classify.py` | 容差/volumeFraction/severity 表/探针 suspected 降级/截断 |
| `app/spatial_index.py` | AABB 均匀网格候选对 O(n·k) + 新增单查询 |
| `app/overlap_probe.py` | GQ/SQ 解析采样探针（复用 voxel_csg 求值含 TR，MC 估占比），结果标 suspected |
| `app/_freecad_csg_worker.py` | Step 3.5 检测段：`check_overlaps`/`focus_num`(s) 入参，`overlaps`/`overlap_truncated`/`overlap_unresolved`/`zero_volume` 出参，**只增不改**既有行为 |
| 端点 | `/api/check-overlap`（同指纹缓存 overlaps.json）+ `/api/quick-add-check`（推荐方向 new_hole/existing_hole）+ api.yaml 32→34 |

测试：pytest **+14**（classify 6 / spatial 4 / probe 4）。门禁：pytest **587/0** + vitest **358/0** + tsc EXIT 0 + 契约闸门 10/10（34 端点）。

## §U.5 v1.7.3（2026-08-23，用户指定版本 1.7.3）

| 改动 | 端点 | 说明 |
| :--- | :--- | :--- |
| parse-keff | `/api/parse-keff` | mctal 目录/文件两种方式 → 5 周期收敛 + combined（`sweep.py +parse_keff_history`），api.yaml 36→37 |
| sweep 仪表盘 | `/api/sweep-dashboard` | 历史目录重读 manifest 补全收敛序列；读 manifest 容忍 UTF-8 BOM（utf-8-sig） |
| INP 对比 | `/api/diff-inp` | difflib unified diff + 增删统计，零新依赖 |
| sweep-run 总时长预算 | `/api/sweep-run` | 组合数 × 单次超时 ≤ 预算（默认 30 分钟），超预算/超上限拒绝 `code="budget_exceeded"`（详见 §V.1 T3） |

门禁：pytest **595/0** + vitest **376/0** + tsc EXIT 0 + 契约闸门 37 端点双向绿。

# 附录 V：后端技术债清偿（2026-08-23，PM 派发全修，测试先行 红→绿）

> 契约：api.yaml 端点**数量与签名不变**（37 端点，仅 sweep-run 错误信封加 `code` 字段，加性不改签名）；门禁 pytest 595 基线不破 + 漂移闸门保持绿。

## §V.1 P1

| 项 | 根因 | 修复 | 测试（红→绿） |
| :--- | :--- | :--- | :--- |
| **T3** sweep-run 无总时预算 | `_handle_sweep_run` 顺序跑 ≤50 组合 × 300s = 最长 ~4.2h，违反「命令加硬性超时」纪律 | `app/sweep.py +sweep_budget_status`（`SWEEP_MAX_COMBOS=50`/`SWEEP_PER_RUN_TIMEOUT=300`/`SWEEP_TOTAL_BUDGET=1800`）：组合数×单次超时超预算或超上限 → 拒绝 `{"status":"error","code":"budget_exceeded","message":含组合数与预算说明}`；单组合保持 300s 超时 | `test_sweep_budget_*` +4 + HTTP `test_http_sweep_run_budget_rejected`（7×300>1800 拒绝，不依赖真实 MCNP） |
| **T7** 探针求值静默遗漏 | `overlap_probe.py` 探针求值失败 `except Exception: return None` → worker `continue`，该栅元对既不入报告也不入 unresolved | 改 `raise RuntimeError("probe_error: …")`，worker 既有 `except` 把它记入 `overlap_unresolved`（reason） | `test_probe_eval_failure_raises_probe_error`（monkeypatch `eval_cell_field` 抛异常） |
| **T8** sweep 临时目录从不清理 | `tempfile.mkdtemp(prefix="mcnp_sweep_")` 泄漏 run_XXX 子目录与 MCNP 大文件 | `app/sweep.py +persist_sweep_summary`（manifest+TSV 拷到 `SWEEP_SUMMARY_ROOT/<stamp>/`）`+cleanup_sweep_dir`（rmtree）；`_handle_sweep_run` 成功/失败后 `shutil.rmtree(base_dir, ignore_errors=True)`（try/finally） | `test_persist_summary_then_cleanup_sweep_dir`（摘要保留 + 临时目录删除）+ `test_cleanup_sweep_dir_ignores_missing` |

## §V.2 P2/可选

| 项 | 修复 | 测试（红→绿） |
| :--- | :--- | :--- |
| **T6** `voxel_csg._tangent_plane_mesh` 宽 except 静默回退 MC | `except Exception` 加 `logger.warning` 记录回退原因（保留回退行为） | `test_tangent_plane_fallback_warns_on_failure`（monkeypatch `classify_gq` 抛异常 → 告警 + MC 仍出网格） |
| **T9** `sweep._substitute` 用 `.index()` 找组位置 | 改 `m.start(1)/m.end(1)`（相对 group(0) 偏移 = 绝对偏移 − m.start(0)）精确定位，修掉「匹配上下文更早出现同文本」错位 | `test_substitute_precise_group_position`（`\d(\d+)cm` 匹配 "55cm" → 替换到第二个 5）+ `test_substitute_simple_cm_unchanged` |
| **T10** `mctal_parser` 顶层 `"nps": None` 死字段 | 从 mctal 头部（首个 tally/ktally 块之前）解析 nps；解析不到则移除该键（不再硬编码 None） | `test_top_level_nps_parsed_from_header` + `test_top_level_nps_absent_when_not_in_header` |
| **T11** api_server 7+ 处重复 `sys.path.insert` + 惰性 import | 抽 `_import_app(module, base_dir=APP_DIR)` 助手集中（`__import__` + 目录确保在 sys.path），替换全部 9 处调用点（sweep-plan/run/dashboard、diff-inp、check-overlap、quick-add-check、generate-step、preview-3d、cross-section、parse-keff）；「不模块级 import 后端污染」语义不变 | 零行为变化，靠既有测试守护（漂移闸门 HTTP 往返绿） |
| **T12** quick-add-check `>0.98` 魔法数字 | 提为具名常量 `RECOMMEND_EXISTING_HOLE_FRAC = 0.98` | 既有行为不变 |
| **T13** `mesh_cell_polydata` 旧签名兼容 shim | grep 全仓库确认全部调用方（worker + test_voxel_csg.py）已用新签名 `(ast, surfaces_by_num, tr_cards, B, res)`，移除 shim | 既有测试守护（test_voxel_csg.py 全绿） |
| **T14** `sweep.parse_keff` `except Exception: pass` 静默降级 | 加 `logger.warning` 记录 mctal 解析失败（保留分层兜底：正则继续） | `test_parse_keff_warns_on_mctal_failure`（monkeypatch `parse_mctal` 抛异常 → 告警 + 兜底仍返回） |

## §V.3 全量门禁

**pytest 609/0**（基线 595 + 14 新增；复跑稳定）——含契约漂移闸门 `tests/integration/test_api_contract.py`（37 端点双向绿：handlers dict ↔ api.yaml operationId + contract.ts 字段 ⊆ models.py + 三核心端点 HTTP 往返 + 本批新增 sweep-run 预算 HTTP 拒绝）。**未 commit**（等 PM 统一提交）。

# 附录 W：格阵 fill 阶段1 数据层（2026-08-24，PM 派发，架构师定稿，未 commit）

> 设计权威：`C:\Users\13789\.claude\plans\fill-cell-lat-0-u-fill-cell-u-u-u-u-u-3-fluffy-lampson.md` 阶段1。深模块契约/跨阶段决策见 plan 第 1-6 条。依赖红线：零新增 Python 依赖（lattice.py 只 stdlib）。

## §W.1 新增/修改接口

无新 HTTP 端点。`fill_grid` 字段全链路透传（parse→deck→asdict 桥接→前端→`_cells_from_list`→generate），asdict 自动透传无需改桥接代码。

## §W.2 文件改动明细

| 文件 | 改动 |
| :--- | :--- |
| `app/lattice.py` | **保留精化（架构师裁决，248 行草稿）**：`format_fill_cards` 2 处必须修——① **raw 优先回放**（非 cells，保 `17r` 简写 / 字节贴近源 / R1 稳定）；② 回放 raw 时**剥离前导 `len(fg.range_)` 个范围 token**（首行已含范围串，续行不重复）。raw 空（手工构造/画布覆盖）才回落 `fg.cells` 展开 |
| `app/models.py` | `CellData` 加 `fill_grid: str = ""`（render 之后、comment 之前；全仓关键字构造，安全） |
| `app/generator/parsers/core.py` | 模块顶 `from app import lattice`；新增 `_consume_fill_tokens` helper（FILL= / FILL 两分支共用）；`FILL=`（原 273）与 `FILL`（原 313）两分支改调它：收集 FILL 之后全部剩余 token → `parse_fill_tokens`。格阵→`fill=范围串`+`fill_grid=JSON`+`idx=len(parts); break`；翻译→fill 保留单值；返回 None（单值填充）→ 走原循环零回归。`CellData` 构造加 `fill_grid=fill_grid`。**伴生修复**：`parse_data_cards` 连续 C 注释行先回落 other_cards 再覆盖 pending_c（防覆盖丢失，17×17/BEAVRS 数据段连续 C 行 R1 逐代保持） |
| `app/generator/inp_generator.py` | 模块顶 `from app import lattice`；`_generate_cells` FILL 发射前分派 `lattice.FillGrid.from_json(cell.fill_grid or "")`（脏 JSON→None 优雅回退单值路径）；格阵/翻译路径（fg 非 None）：跳过通用 FILL、常规参数照旧、`lattice_lines[0]`（FILL= 首行）放 params_parts 最后（MCNP 要求 FILL 是 cell 卡最后参数）、`lattice_lines[1:]` 独立 append 续行（绕开通用续行不加 `&`）；格阵 cell 的 `$` 注释移到所有续行之后的尾行（不吞条目）。**伴生修复**：`_wrap_long_lines` 注释保护——行内 `$` 位于第 80 列内 → 卡体已合法、注释超长不拆（MCNP 忽略 80 列后；防 `&` 注入污染注释逐代漂移，BEAVRS 长注释实卡触发） |
| `gui/backend/api_server.py` | `_cells_from_list`（407-428）CellData 构造加 `fill_grid=cell_dict.get("fill_grid","")`；其余 asdict 桥接自动透传无需改；`build_cells_data`（阶段3）**未动** |

## §W.3 数据库变更 / 环境变量

无（纯 Python 引擎 + 字段透传，无迁移脚本、无新增环境变量）。

## §W.4 新增/修改测试

- `tests/unit/test_lattice.py`（新，13 用例）：parse_fill_tokens（17×17 矩形 / 3D 偏移 `(9 0 9)` / `17r` 重复 / 翻译单填充 / 单宇宙 None）/ parse_fill_entries（Nr 重复 / 偏移）/ format_fill_cards（**raw 优先** + **范围剥离** / cells 回落 / 翻译 / None）/ FillGrid JSON 往返 + 脏 JSON / hex_lattice 夹具解析 + R1。
- `tests/parser/test_core_cells.py`：单值回归（48-57）补 `assert c.fill_grid == ""`；新增 6 用例（17×17 范围 / `1 (9 0 9)` 偏移 / `17r` 重复 / 翻译单填充 / 条目同行 / 空格 `FILL` 语法）。
- `tests/integration/test_roundtrip.py`：`_cell_fields` 加 `fill_grid`；新增 `test_r1_lattice_17x17_fixed_point`、`test_r1_lattice_prob41c_fixed_point`（R1 字节不动点闸门）。
- `tests/conftest.py`：kitchen_sink cell1 加 `fill_grid=""`。
- `tests/parser/test_owen_deck_fixtures.py`：17×17 基线加强断言——`fill_grid` 非空、`fill=="0:16 0:16 0:0"`、`dims==[17,17,1]`、`surface_expr=="50 -51 52 -53"`（无范围串污染）。
- `tests/fixtures/hex_lattice.inp`（新）：合成 lat=2 六棱柱（pointy-top 默认 + 轴向 +Z，2×2 阵列）。

## §W.5 本地启动验证

```
python -m pytest tests/ -q                          # 632 passed（基线 609 + 新增 23）
# R1 字节不动点（prob41c / inp24 / hex_lattice / 17×17 / BEAVRS 五夹具全 True）：
python - <<'PY'
from app.generator.parsers import parse_inp_text
from app.generator.inp_generator import generate_inp_from_deck
from tests.conftest import load_sample
from pathlib import Path
for name, text in {
    'prob41c': load_sample('prob41c.inp'),
    'inp24': load_sample('inp24.inp'),
    'hex_lattice': load_sample('hex_lattice.inp'),
    '17x17': (Path('tests/fixtures/owen')/'assembly_17x17_mcnp.i').read_text(encoding='utf-8', errors='replace'),
    'BEAVRS': (Path('tests/fixtures/owen')/'beavrs_fullcore_mcnp.i').read_text(encoding='utf-8', errors='replace'),
}.items():
    deck, _ = parse_inp_text(text)
    g1 = generate_inp_from_deck(deck)
    deck2, _ = parse_inp_text(g1)
    g2 = generate_inp_from_deck(deck2)
    print(name, g1 == g2)
PY
```

## §W.6 终态

**pytest 632/0**（609 基线 + 23 新增）——含 R1 不动点 2 条新闸门 + kitchen_sink R4 不回退 + 契约漂移闸门全绿。wire 链路实测：asdict 桥接 + `_cells_from_list` 反向构造 `fill_grid` 不丢。**未 commit**（等 PM 统一提交）。

# 附录 X：格阵 fill 阶段2 后端（validate 预检测 + API + golden 配套，2026-08-24，PM 派发，架构师定稿，未 commit）

> 设计权威：`C:\Users\13789\.claude\plans\fill-cell-lat-0-u-fill-cell-u-u-u-u-u-3-fluffy-lampson.md` 阶段2 + `PROJECT_MEMORY.md` §S1b-1（架构师阶段2设计契约）。QA 建议（parse_fill_entries nR 上限）一并落地。依赖红线：零新增 Python 依赖（lattice.py 只 stdlib）。改动纪律：只动 5 个文件，未动阶段1已验收的解析/生成逻辑与 `_expand_repeat`。

## §X.1 新增接口

- `app/lattice.py::validate_lattice_surfaces(surface_expr, lat, surfaces_text="") -> (ok, msg)`：
  - 只认带符号整数曲面号交集（如 `-10 20 -30 40`）；拒绝 `#`（补集）/ `:` / 括号。
  - `lat="1"` 六面体合法：单 RPP/BOX 宏体；或 6 个 PX/PY/PZ 平面（每轴一对±）；或 4 个平面（2D 延伸，两轴各一对±）。
  - `lat="2"` 六棱柱合法：单 RHP/HEX 宏体；或 6 个竖直 P 平面（法向在水平面均布 6 向）+ 2 个 PZ 顶底（一正一负）。
  - 自带曲面卡正则解析（`_parse_surface_cards` 读 `surfaces_text` 定位曲面号定义），不依赖 freecad/parsers 模块。
  - 返回 `(True, "")` 或 `(False, 中文错误消息)`。
- HTTP 端点 `POST /api/validate-lattice-surfaces`（operationId `validateLatticeSurfaces`）：
  - 入参 `{surface_expr, lat, surfaces_text}`，出参 `{"status":"ok","ok":bool,"msg":string}`（对齐 validate-inp 扁平信封风格；ok=false 为正常校验结果，非 HTTP 错误）。

## §X.2 文件改动明细

| 文件 | 改动 |
| :--- | :--- |
| `app/lattice.py` | 追加 validate 段：`validate_lattice_surfaces` + `_parse_surface_cards`（曲面卡文本→{号:(关键字,参数)}，跳过注释行/内联 `$`/支持 `j*i` 前缀与 `*TRn` 后缀）+ `_plane_normal`（P 卡系数形 A B C D 或三点形取法向）+ `_check_axis_pairs`（按轴成对±、号互异、2D 恰好两轴）+ `_validate_lat1`/`_validate_lat2` + `_resolve_surfaces`（共享查号）。**QA 建议**：新增模块常量 `MAX_EXPANDED_ENTRIES = 1_000_000`；`parse_fill_entries` 加 `max_entries` 参数（默认常量）封顶 nR 展开（超限截断不抛异常，raw 兜底保留原始 `17r` 简写，R1 不受影响）；`parse_fill_tokens` 补 0 逻辑同样封顶（极端超大范围 dims 不爆内存） |
| `gui/backend/api_server.py` | `handlers` dict 注册 `/api/validate-lattice-surfaces`；新增 `_handle_validate_lattice_surfaces`（`_import_app("lattice")` 惰性导入 → 调 validate → `_ok({"ok":…,"msg":…})`） |
| `docs/contracts/api.yaml` | 加 `/api/validate-lattice-surfaces` path（operationId `validateLatticeSurfaces`，tag geometry，含入参/出参 schema） |
| `tests/unit/test_lattice.py` | 新增 validate 用例 15 条（lat=1 单RPP/单BOX/6平面/4平面2D 合法；lat=2 单RHP/单HEX/6P+2PZ 合法；`#`/`:`/括号/非配对/缺 surfaces_text/未知曲面/非法 lat/非平面混入 拒绝）+ 跨语言 golden 断言 `test_validate_lattice_golden_cross_language`（读 `gui/src/utils/__golden__/latticeGolden.json`，文件缺失跳过）+ nR 上限 3 条（超大 nR 封顶 1M / max_entries 可注入 / 超大范围补 0 封顶 monkeypatch） |
| `tests/integration/test_api_contract.py` | 新增 `test_http_validate_lattice_surfaces`（真实 HTTP：17×17 4 平面 2D → ok:true；含 `#` → ok:false；lat=2 8 平面 → ok:true） |

## §X.3 数据库变更 / 环境变量

无（纯 Python 逻辑 + 端点，无迁移脚本、无新增环境变量）。

## §X.4 测试

- 全量 pytest：**650 passed, 1 skipped**（基线 632 + 新增 18；1 skip = golden JSON 前端未产出，缺失跳过）。
- 阶段1 门禁不回退：prob41c / inp24 / hex_lattice / 17×17 / BEAVRS R1 字节不动点 + kitchen_sink R4 全绿。
- 契约漂移闸门：handlers dict ↔ api.yaml 双向一致（新端点两方向均覆盖）。

## §X.5 本地启动验证

```
python -m pytest tests/ -q     # 650 passed, 1 skipped
# 端点冒烟（真实 HTTP，集成测试已覆盖）：
curl -s -X POST http://127.0.0.1:5001/api/validate-lattice-surfaces \
  -H 'Content-Type: application/json' \
  -d '{"surface_expr":"50 -51 52 -53","lat":"1","surfaces_text":"50 px -0.63\n51 px 0.63\n52 py -0.63\n53 py 0.63"}'
# → {"status":"ok","ok":true,"msg":""}
```

## §X.6 终态

**pytest 650/0（1 skip）**。未 commit（等 PM 统一提交）。**nR 上限已加：MAX_EXPANDED_ENTRIES=1_000_000**（QA 建议）。跨语言 golden 断言已就位（前端产出 `gui/src/utils/__golden__/latticeGolden.json` 后即自动生效）。

# 附录 Y：格阵 fill 阶段3 后端（3D 预览 universe 实例化 + 嵌套 fill 递归，2026-08-24，PM 派发，架构师定稿，未 commit）

## §Y.1 新增/修改接口

- **POST /api/lattice-extent**（operationId `latticeExtent`，tag geometry）：入参 `{surface_expr, lat, surfaces_text}`，响应 `{ok, extent|null, msg}`。`lattice_cell_extent` 解析格元物理范围（lat=1 单 RPP/BOX 宏体 / 6 或 4 平面；lat=2 单 RHP/HEX / 6 竖直 P 两两求交 + 2 PZ），z 无界字段为 null。
- **POST /api/preview-lattice**（operationId `previewLattice`，tag geometry）：入参 `{surfaces, cells, tr_cards, latticeNum?, pitch?, height?}`，响应 `{lattices:[{num,lat,kind,dims,range,center,pitch,height,trclRotationDeg,positions,universes}], leafInstances, tree, count, detailViable, limit}`。嵌套 fill 递归在后端 `compose_lattice_tree` 完成（双形态：NESTED tree + FLAT leafInstances），每格阵一条 lattices（含嵌套、按 cellNum 去重），universes = 该格阵直接引用叶 universe 的裁剪 STL（合成 6 个格元盒平面 max_surf+1..+6，universe 栅元 surface_expr=原式+盒内半空间）。
- **改 `build_cells_data`**：第一遍捕获 u/fill/lat/trcl/render/fill_grid；第二遍 `render:false`→skip（修死代码：前端传 render 但此前被忽略）+ `fill_grid` 非空→skip（格阵栅元不产实体 STL）；`cells_by_num` 保留（#n 补集引用不受影响）。

## §Y.2 文件改动明细

| 文件 | 改动 |
| :--- | :--- |
| `app/lattice.py` | 阶段3深模块：`hex_ring_rows`/`hex_ring_cell_count`/`hex_center`（与前端逐字一致 golden 锁死）、`lattice_cell_extent`（复用 `_parse_surface_cards`）、`expand_positions`（rect 中心公式 / hex 矩形盒+hexCenter / TRCL 绕 Z / 超限返回 None）、`compose_lattice_tree`（嵌套 fill 递归，三参数 MAX_LATTICE_DEPTH=8 / MAX_TOTAL_INSTANCES=500000 / DETAIL_MAX_INSTANCES=20000）、`_cell_pz_bounds` 助手。纯 stdlib。 |
| `gui/backend/api_server.py` | `build_cells_data` render/fill_grid skip；`_PREVIEW_CACHE_LATTICE=PreviewCache(max_entries=2)`；两端点 handler + 助手（`_resolved_extent` pitch/height 覆盖次序、`_cell_trcl_deg` TRCL 绕 Z、`_build_one_universe` 裁剪 STL + 指纹缓存）；handlers dict 注册。 |
| `app/preview_cache.py` | `fingerprint` 加可选 `extra` 参（并入 canonical json；None 时与旧版指纹一致，向后兼容）。 |
| `docs/contracts/api.yaml` | 两 path（operationId previewLattice / latticeExtent，tag geometry）。 |
| `tests/unit/test_lattice.py` | 阶段3用例：hex_ring_rows/hex_center golden、lattice_cell_extent（rpp/box/9参数box/6/4平面/hex平面/不可解析）、expand_positions（rect 2D/3D、hex 环序、TRCL 90°、上限拒绝）、compose_lattice_tree（嵌套 10 叶绝对坐标、depth_limit、too_many、常量）、跨语言 golden positions/nested 断言。 |
| `tests/integration/test_api_contract.py` | lattice-extent / preview-lattice 真实 HTTP shape。 |
| `gui/src/utils/__golden__/latticeGolden.json` | 扩展 positions（rect 2D/3D、hex、TRCL90）+ nested（嵌套样例 10 叶坐标）。 |

## §Y.3 数据库变更 / 环境变量

无（纯 Python 逻辑 + 端点，无迁移脚本、无新增环境变量）。

## §Y.4 测试

- 全量 pytest：**673 passed, 0 failed**（基线 651 + 新增 22；阶段2 的 1 skip 已消除——golden 已产出）。
- 契约漂移闸门：handlers dict ↔ api.yaml 双向一致（新端点两方向均覆盖），HTTP 用例 15/15。
- 端到端冒烟：hex_lattice 夹具 parse-inp → preview-lattice（hex 格位 0/1.732/0.866/2.598 正确，u=1 燃料 pin 裁剪 STL，void u=2 不产叶）→ preview-3d（格阵 cell 20 不再产实体 STL，仅燃料 pin cell 10）。

## §Y.5 本地启动验证

```
python -m pytest tests/ -q     # 673 passed
# 端点冒烟（真实 HTTP，集成测试已覆盖；契约闸门 fixture 起子进程）：
curl -s -X POST http://127.0.0.1:5001/api/lattice-extent \
  -H 'Content-Type: application/json' \
  -d '{"surface_expr":"50 -51 52 -53","lat":"1","surfaces_text":"50 px -0.63\n51 px 0.63\n52 py -0.63\n53 py 0.63"}'
# → {"status":"ok","ok":true,"extent":{"x_min":-0.63,"x_max":0.63,"y_min":-0.63,"y_max":0.63,"z_min":null,"z_max":null},"msg":""}
```

## §Y.6 终态

**pytest 673/0**。未 commit（等 PM 统一提交）。与前端已对齐响应 shape（前端提案的 compose 递归树被否决——嵌套递归在后端 compose_lattice_tree 完成，前端消费 flat leafInstances + 每格阵 positions/universes）。契约闸门 5001 端口本次空闲无劫持，全程真实端口验证通过。

# 附录 Z：项14 3D 预览 STL 生成 cell 分类规则（2026-08-24，PM 派发，用户已确认权威规则，未 commit）

> 本批只做 15 项反馈中的项14。分类规则为用户已确认，不可违背。契约 api.yaml / golden 不动（后续批次统一处理）。

## Z.1 分类规则（用户已确认）

| 类别 | 判定 | 行为 |
| :--- | :--- | :--- |
| fill 装配容器 | `fill` 非空 **或** `fill_grid` 非空（**含 `fill="0"` 的 void-fill**） | 跳过自身 STL。无论有没有 u、material 是否 0。内容由 FILL 装配：单值 fill=U → 装配一份 universe U；格阵 fill=range+表 → 切格位装配（preview-lattice 路径） |
| graveyard | impN/impP/impE（或 imp_n/imp_p/imp_e）任一非空且**首个 token 为 "0"** | 不渲染（跳过自身 STL） |
| render:false | 前端 render 显式 false | 跳过自身 STL（既有规则，保持） |
| 实体 cell | material≠0、无 fill 无 u | 直接产 STL |
| 纯 void cell | material=0、无 fill 无 u | 参与 STL（透明占位）——项14「删 void 约束」唯一适用范围 |
| universe 定义 cell | u≠0、material≠0、无 fill | 仍产 STL（universe U 几何 = 所有 u=U 的 cell 的 STL 集合） |

## Z.2 build_cells_data 改动（gui/backend/api_server.py）

- 第一遍新增捕获：`has_fill = bool(str(cell.get("fill","") or "").strip())`、`is_graveyard = _imp_is_zero(cell)`。
- `_imp_is_zero` 助手：遍历 `imp_n/impN/imp_p/impP/imp_e/impE`，任一非空且首个 token 为 `"0"` → graveyard。MCNP imp 单值语义，取首个 token 兼容 `"0 0"` 续值。
- 第二遍 skip 合并：`has_fill or has_fill_grid → continue`（**此前只 skip fill_grid、漏掉单值 fill=U → 删 void 约束后 fill cell 自身几何被当实体块渲染，即用户看到的「大紫方块」——本批核心修复**）；`is_graveyard → continue`。
- `cells_by_num` 映射保留（#n 补集引用不受影响）；entries 元组扩为 8 元（number, mat_val, density, ast_node, render, has_fill, has_fill_grid, is_graveyard）。
- 递归语义：被 fill 的 cell 是装配容器自身不产 STL；装配 universe 时其 cell 内套 fill → 递归展开，直到叶级实体 cell（material≠0 且无 fill）才产 STL（由 /api/preview-lattice 的 compose_lattice_tree 处理，本批不改该路径）。

## Z.3 include_void 调用点清单

| 调用点 | 路径 | include_void | 是否本批改动 |
| :--- | :--- | :--- | :--- |
| `_handle_preview_3d`（主路径 ~L2086） | preview-3d | **True** | 已改（原 False） |
| `_handle_preview_3d` 缓存命中分支截面 deck 快照（~L2046） | preview-3d 缓存命中 | **True** | 已改（原 False，防缓存命中/未命中截面行为不一致） |
| `_handle_check_overlap`（~L1202） | check-overlap | True | 已是 True |
| `_handle_quick_add_check`（~L1251） | quick-add-check | True | 已是 True |
| `_build_one_universe`（~L597，/api/preview-lattice 内部裁剪） | 格阵 universe 裁剪 STL | **False** | 保持不动（void 无实体可裁剪，语义正确） |
| `_handle_export_step`（~L1993） | STEP 导出 | **False** | 保持不动（void 无实体可导出，语义正确） |

**边界**：项14「删 void 约束」只对 3D 预览主路径（+ 截面 deck 快照）生效；STEP 导出与格阵 universe 裁剪保持 include_void=False，void 不产实体，语义正确不回退。

## Z.4 graveyard 口径

- 判定：impN/impP/impE 任一粒子重要性为 0（首个 token == "0"）即视为 graveyard，整 cell 不渲染。
- 理由：MCNP 中 imp=0 的 cell 杀对应粒子（外围边界典型为 imp:n=0 真空）；用户规则明确「graveyard（imp=0 外围）→ 不渲染」。
- 口径选择：任一粒子的 imp 为 0 即 skip，而非只认 impN=0——imp 未写（空）不判 graveyard；imp="1"/非 0 不误判（测试覆盖）。
- 前端过滤备选方案未采纳：STL 会话跨功能复用（preview-3d 产 STL 供截面复用），若前端过滤则截面仍会用到 graveyard STL；后端 skip 使 graveyard 全局不产 STL，语义一致。
- 副作用：含材料但某粒子 imp=0 的 cell（如 imp:p=0 光子杀）也会被跳过——属用户规则「imp=0 不渲染」的预期。

## Z.5 void STL 相机风险（只记录，不改前端）

preview-3d 主路径改 include_void=True 后，巨型边界 void（如 so 1000）的 STL 会撑大包围盒，可能把前端相机拉远导致模型缩成针尖。**相机适配属前端项（本批另一 agent），后端只保证 void STL 出得来**，不在本批超前改前端。

## Z.6 文件改动明细

| 文件 | 改动 |
| :--- | :--- |
| `gui/backend/api_server.py` | `build_cells_data` 加 has_fill / graveyard skip + 项14 分类规则 docstring；3D 预览主路径 + 截面 deck 快照 include_void 改 True；STEP 导出 / _build_one_universe 保持 False（注释标注边界）；`_handle_export_step` 错误消息微调（「没有可预览的栅元」）。 |
| `tests/unit/test_build_cells_data.py` | **新增**，12 用例（子进程驱动 build_cells_data，不 import api_server、不依赖 FreeCAD）：单值 fill=U skip / fill_grid skip / 纯 void 产 STL / 实体 cell 产 STL / render:false skip / graveyard imp=0 不渲染 / fill="0" 也是 fill cell / imp_p=0 也算 graveyard / imp="1" 不误判 / include_void=False 纯 void 仍 skip（STEP 边界）/ CellRow 判别联合格式 / u≠0 无 fill 实体 cell 产 STL。 |

## Z.7 测试

- 全量 pytest：**686 passed, 0 failed**（基线 674 + 新增 12，零回退；硬超时保护下 32.6s 跑通）。
- 环境完整：HTTP 契约闸门 + FreeCAD 依赖测试全部 PASSED 未 skip，本机环境可完整跑通。
- 契约 api.yaml / golden 未动（后续批次统一处理）。

## Z.8 本地启动验证

```
python -m pytest tests/unit/test_build_cells_data.py -q   # 12 passed
python -m pytest tests/ -q                                 # 686 passed
```

---

# AA. Wave 2a：格阵 fill 15 项修复——后端全部项（2/4/5/9/13/15 + 项14 剩余 + api.yaml + pytest）

> 图纸：`docs/contracts/lattice-fix15-design.md`（架构师 Wave 1，跨语言锁死 L1-L9）。
> 门禁：pytest **703 passed / 0 failed / 0 skipped**（基线 686 + 新增 17；R1 五夹具 + kitchen_sink R4 不回退；契约闸门含新 cycle HTTP 用例）。

## AA.1 项 14 剩余（_build_one_universe）

- `gui/backend/api_server.py _build_one_universe`：uni_cells 收集时新增 `if _cell_fill(c): continue`（单值 fill cell 含 fill="0" 不产自身 STL，规则 1/7）；`build_cells_data(mod_cells, include_void=True)`（原 False）——universe 叶 void 格元产透明占位 STL（规则 4）；注释同步更新。
- 新增 `_cell_fill` 助手（判别联合取 cell.fill）。`_imp_any_zero` 提升为模块级（build_cells_data 口径复用）。
- 边界保持：STEP 导出仍 include_void=False（void 无实体可导出）。

## AA.2 项 2（方向块数 -N:M）

- `app/lattice.py` 新增 `_dir_counts_from_range(token)->(L,R)`：`a:b` → `(-a, b)`；与 `_range_count` dims=b-a+1 自洽（dims=L+R+1）。`expand_positions` rect 中心 `((i-(nx-1)/2)·px)` 在 -N:M 下格阵以几何中心居中于原点（权威公式，R1 稳定）。
- pytest `test_dir_counts_from_range`（3 例映射 + 反派生一致）。

## AA.3 项 4（六棱柱全量参数 RHP/HEX）

- `app/lattice.py _rhp_extent`：扩展支持 **9 参**（V+H+R1）→ R2 用 Rodrigues 绕 H 转 60° 推断（`_rotate_about`），AABB 与 12 参显式一致；12/15/18 参原样读取。12 参既有路径零回归。
- `validate_lattice_surfaces._validate_lat2`：单 RHP/HEX 宏体新增 `_validate_rhp_params` 校验——参数数∈{9,12,15,18}；|H|>0；|R1|>0；H·R1≈0；R2/R3 各 ⊥H 且连续夹角 60°（R1→R2→R3 = 0°/60°/120° 旋转语义，与 `_rhp_extent` 推断一致；`*TRn` 非数值 token 跳过）。
- **破坏性变更**：既有 `"10 rhp 0 0 0 0 0 2 0.5 0 0"`（9 参合法）仍过。
- pytest `test_validate_rhp_params`（9/12/15/18 合法；|H|=0、R1 非 ⊥H、R2 不 ⊥H、夹角错、参数数非法 → 拒）+ `test_rhp_extent_9params_infer`（9 参推断 AABB 与 12 参一致）。

## AA.4 项 5（hex 排列修正，跨语言 L1/L2 锁死）

- `app/lattice.py hex_center` 改权威公式：`x = col·pitch·√3/2, y = row·pitch + (col%2)·pitch/2`（顶点+X flat-top 蜂窝，奇数列纵向错半格）。`hex_ring_rows` 保持 `[r+1+min(j,2r-j)]`。`expand_positions` hex 分支走新 hex_center。
- golden 消费：`hexCenter`/`positions.hex` 段由前端 Wave 2b 写盘（已写盘）。`test_positions_golden_cross_language` 加 stale-hex skip（前端未重算时跳过，写盘后自动生效）。
- pytest `test_hex_center_flat_top`（pitch=2/√3 权威样例）+ `test_expand_positions_hex_flat_top`（golden positions.hex 新值）+ 既有 `test_hex_center_formula`/`test_expand_positions_hex_ring_order` 期望值同步新公式。

## AA.5 项 9（分组头注释 → INP C 注释）

- 存储：`app/models.py DeckData` 加 `universe_comments: dict`（键 snake_case u_str）。`deck_from_json` 读 `universe_comments`/`universeComments`；parse-inp / `_deck_to_frontend_dict` 序列化 `universeComments`。
- 生成：`app/generator/banners.py` 冻结词汇 `universe_group_banner(u, text)` + `is_universe_group_comment`/`parse_universe_group_comment`（词汇冻结唯一发射源）。`inp_generator._generate_cells` 按「相邻同 U 连续段」在该组首个栅元行前插 `C  U-group U=<n>: <user text>`（raw 条件行不打断连续段）。
- 解析：`parsers/core.py parse_cells` 跳过 U-group 行（防被吸收为 cell 注释）+ 新增 `extract_universe_comments`；`parse_data_cards` U-group 行进 `universe_comments`（从 other_cards 路径排除）。`parsers/__init__.py parse_inp_text` 合并 cell/data 段注释 → DeckData。
- R1：既有 5 夹具无 universe_comments → 零影响；新夹具 gen→parse→gen 字节不动点。
- pytest `tests/parser/test_universe_group_comment.py`（5 用例：生成插注释 / 解析吸收 / R1 字节稳定 / 无注释零影响 / raw 行不打断连续段）。

## AA.6 项 13（循环嵌套检测，跨语言 L6 + api.yaml 唯一契约变化）

- `app/lattice.py` 新增 `detect_fill_cycle(sub_by_u)->{cycle, chain}`：DFS 判环（fill_grid lattice/translated cells[].u 或 fill 单值非 "0"/"" 构成边 U→V；递归栈成员表判环，chain=path[idx:]+[U]）。
- `compose_lattice_tree` 入口（`_expand_lattice` 前）detect_fill_cycle → 命中返回 `{status:"cycle", cycle:chain, tree:[], leafInstances:[], count:0, lattices:[], detailViable:True}`（不递归）。MAX_LATTICE_DEPTH/MAX_TOTAL_INSTANCES 仍为守卫。
- `api_server._handle_preview_lattice`：透传 cycle/chain（compose `cycle`=链 转换 → 响应 `cycle:boolean`+`chain:array`）；graveyard（imp=0）cell 从 sub_by_u 排除（规则 5，`_imp_any_zero`）。
- **api.yaml**：preview-lattice 响应 `limit` enum 增 `"cycle"` + 新增 `cycle: boolean` + `chain: array<string>`（§4 diff 落地）。契约闸门 HTTP 用例 `test_http_preview_lattice_cycle`（cycle deck → 200 + limit=cycle + cycle=true + chain 闭合链）。
- pytest `test_detect_fill_cycle`（自环/两元/三元/无环/fill0 非边/fill_grid 边）+ `test_compose_lattice_tree_cycle`（A→B→A → status="cycle"+chain）。

## AA.7 项 15（格阵按 FILL 装配显示，后端部分）

- `app/lattice.py _expand_universe`：fill 非空（含 `fill="0"`）统一为装配容器不自产 STL（规则 1/7）；补 void 叶（material="0" 无 fill）→ 产 `{leaf, void:true}` 计入 count（规则 4，detailViable 总览兜底）。
- `api_server._handle_preview_lattice` 构造 sub_by_u 时过滤 imp=0 cell（规则 5）。
- golden 消费：`assembly` 段（前端 Wave 2b 写盘，已写盘）——`test_single_fill_assembly_golden` 按「结构完整才断言否则 skip」消费。
- pytest `test_expand_universe_void_leaf_and_fill0`（void 叶 / fill0 skip / 混合）+ `test_expand_universe_single_fill_assembly`（单值 fill 装配链）+ `test_single_fill_assembly_golden` + `test_imp_any_zero_graveyard_filter`。

## AA.8 api.yaml diff 摘要（本批唯一契约变化 = 项 13）

```
/api/preview-lattice 响应：
  limit: enum [ok, depth_limit, too_many] → [ok, depth_limit, too_many, cycle]
  + cycle: boolean（嵌套 fill 存在循环引用）
  + chain: array<string>（循环链 universe 号序列，如 [1,2,1]）
```

## AA.9 测试计数

| 门禁 | 结果 |
| :--- | :--- |
| pytest 全量 | **703 passed / 0 failed / 0 skipped**（基线 686 + 新增 17） |
| R1 五夹具（17×17/BEAVRS/hex_lattice/prob41c/inp24） | 保持绿（零影响） |
| kitchen_sink R4 | 保持绿（不回退） |
| 契约闸门（含新 cycle HTTP 用例） | 保持绿 |
| golden 跨语言（hexCenter/positions.hex/cycle/assembly/dirCounts 已写盘） | 全部断言通过，无 skip |

## AA.10 文件改动明细

| 文件 | 改动 |
| :--- | :--- |
| `app/lattice.py` | `_dir_counts_from_range`；`_rotate_about`/`_rhp_extent` 9 参推断；`_validate_rhp_params`；`hex_center` 新公式；`detect_fill_cycle` + `compose_lattice_tree` 判环；`_expand_universe` void 叶 + fill0 装配容器 |
| `gui/backend/api_server.py` | `_cell_fill`/`_imp_any_zero`；`_build_one_universe` include_void=True + skip fill；`_handle_preview_lattice` graveyard 过滤 + cycle/chain 透传；`deck_from_json` + parse-inp/`_deck_to_frontend_dict` universeComments |
| `app/models.py` | DeckData 加 `universe_comments` |
| `app/generator/banners.py` | `universe_group_banner`/`is_universe_group_comment`/`parse_universe_group_comment` |
| `app/generator/inp_generator.py` | `_generate_cells` U-group 注释 + `generate_inp_from_deck` 透传 |
| `app/generator/parsers/core.py` | parse_cells skip + `extract_universe_comments` + parse_data_cards U-group |
| `app/generator/parsers/__init__.py` | parse_inp_text 吸收 universe_comments |
| `docs/contracts/api.yaml` | preview-lattice limit enum + cycle/chain |
| `tests/` | test_lattice.py（+9）/ test_universe_group_comment.py（新 5）/ test_build_cells_data.py（+1）/ test_api_contract.py（+1 HTTP cycle） |

## AA.11 本地启动验证

```
python -m pytest tests/ -q          # 703 passed
python -m pytest tests/unit/test_lattice.py -q          # 63 passed
python -m pytest tests/parser/test_universe_group_comment.py -q   # 5 passed
python -m pytest tests/unit/test_build_cells_data.py -q  # 13 passed
python -m pytest tests/integration/test_api_contract.py::test_http_preview_lattice_cycle -q  # 1 passed
```

---

# AB. 用户复验缺陷修复：格阵 FILL 输出按行分隔（2026-08-25）

> 用户浏览器复验发现生成缺陷：格阵 FILL 输出未按行分隔（`_pack_entries` 按字符宽度贪心打包，17×17 约 37 格/行）。MCNP 规范每行一个 j 行（矩形每行 nx 个条目，17×17 → 每行 17 个、17 行）。

## AB.1 改动（app/lattice.py format_fill_cards）

- **cells 优先结构化展开**：按 `dims[0]`（nx）每行分组（行主序 i 最快 → 每行 = 一个 j 行）；某行超 75 字符（含 5 空格缩进 ≤80 列）再按宽度拆子行（token 序不变，MCNP 续行合法）。
- **raw 仅 cells 空或截断时兜底**（不再 raw 优先——否则无法行分隔）。raw 回放仍剥离前导 len(range_) 个范围 token（防续行重复）。
- **截断边界决策**：`MAX_EXPANDED_ENTRIES` 截断（len(cells) < dims 乘积）→ 回落 raw。理由：截断 cells 展开会输出不完整数据丢源 token，回落 raw 保 R1/保真。注：此处略超用户「raw 仅 cells 空兜底」字面，但 PM 授权权衡，截断场景 raw 更安全。
- **lat=2 六棱柱**：同样按 nx 行分组（token 序不变即 MCNP 合法；hex_lattice fixture dims=[2,2,1] → 每行 2 条目、2 行）。未按 hexRingRows 视觉对齐（仅可读性差异，非合法性）。
- **translated 单填充路径不变**。

## AB.2 测试

- `tests/unit/test_lattice.py` format_fill_cards 用例重写/新增（2 → 5）：
  - `test_format_fill_cards_per_row_grouping_17x17`（17 行 × 17 条目）
  - `test_format_fill_cards_row_width_split`（长条目行超宽拆子行，token 序不变）
  - `test_format_fill_cards_cells_first_over_raw`（cells 完整时 cells 权威）
  - `test_format_fill_cards_raw_fallback_empty_cells`（cells 空 → raw 兜底 + 范围剥离）
  - `test_format_fill_cards_raw_fallback_truncated`（截断 → raw 兜底保简写）
- 门禁：pytest **706 passed / 0 failed / 0 skipped**（基线 703 + 新增 3）。R1 五夹具（17×17/BEAVRS/hex_lattice/prob41c/inp24）parse→gen→parse→gen 固定点保持绿（生成确定性 gen1==gen2 成立，行分组不改变 token 序）；kitchen_sink R4 不回退；契约闸门全绿。

## AB.3 本地启动验证

```
python -m pytest tests/ -q      # 706 passed
python -m pytest tests/integration/test_roundtrip.py -q   # R1 五夹具 + R4 全绿
python -m pytest tests/unit/test_lattice.py -q            # 66 passed
```

## Wave 3c 补充：材料 #ifdef 块 R1 修复

> 日期：2026-08-25 | 触发：官方验收样例 `u233-comp-therm-001-case-6.i`（含 R 的 lat=2 + 材料 `#ifdef ENDF7`）整文件 R1 失败。

**根因**：`#ifdef ENDF7` + 条件核素（如 Zircaloy 的 Sn 50112-50124）被续行合并成单条逻辑行，
`parse_data_cards` 把整块作为一条 raw 行挂到当前材料；`#endif` 又被 lookahead（下一非 C 行为
新 `M{n}`）误挂到**下一**材料。一进一出材料卡变形（`#ifdef` 与核素同列、`&` 续行、`#endif` 错位）。

**修复**（`app/generator/parsers/core.py` parse_data_cards `#`-分支）：
- `#ifdef/#ifndef/#if` 块归属两路：紧跟未出现 `M{n}` → pending（包裹 M 头，原逻辑保留）；
  否则归属**当前材料**，且合并行拆回 `raw 宏 + 核素对`（按首个数字 token 切分，兼容 `50112.70c`）。
- 新增 `ifdef_routes` 栈：块起压栈（True=当前材料 / False=pending），匹配 `#endif` 弹栈；
  `#else/#endif` 按栈顶归属，避免 lookahead 误挂下一材料。

**验证**：u233 官方样例整文件 `parse→gen→parse→gen` **字节全等**（R1）；lat=2 cell 19 仍
1849 格完整。全量 pytest **707/0**（新增 `test_parse_ifdef_block_within_material_splits_macro_and_nuclides`）。
