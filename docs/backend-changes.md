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
