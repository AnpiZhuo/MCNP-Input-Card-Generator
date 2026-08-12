# P1 技术债重构契约（F#7 → F#3 → F#4 → F#5+F#6 → F#1）

> 契约人：架构师 | 施工方：后端 | 分支：`refactor/generator-tech-debt`（自 `experiment/geouned` 拉出）
> 日期：2026-08-12 | 状态：**契约已锁定（P1 放行条件 245/6 已达成）**
> 依据：`PROJECT_MEMORY.md` P0 修复轮完成态 + `docs/contracts/bugfix-f1-f5.md`（§0.5.5 复合根因清单 + §7 P1 边界 + §8 重锚定）+ `app/generator/review_findings.json`（7 项）
> 目标：**6 红全部转绿，全量终态 251 绿 / 0 红**（245 基线 + F#3×2 + F#7×2 + kitchen-sink R1/R4×2）
> 重构顺序：**F#7 → F#3 → F#4 → F#5+F#6 → F#1**（F#5+F#6 是核心，验收最严）
> 行号说明：本契约行号为**动工前 Grep 重锚定**值（2026-08-12 工作树），施工以每次 Grep 重锚定为准，见 §7。

---

## 0. 纪律（后端施工必读，违反即打回）

1. **每 commit 前 grep 重锚定、commit 后模式归零**。任一 commit 不得打破 P0 全绿基线 245/6（即每一步后全量绿数不得少于上一 commit；F#5+F#6 内部子步除外，见 §6.4）。
2. **每步跑全量 `python -m pytest tests/ -v` + R1 子集**，只允许该步关联断言红→绿；F#5+F#6 子步期间 kitchen-sink R1/R4 允许保持红（结构性拆解先于漂移修复），其余已绿断言一律不得回红。
3. **按序重构，不可跳步**：F#7/F#3/F#4 是低风险热身，F#5+F#6 的"拆 seam 前先有整函数字符化测试 + R1 快照"依赖 P0 测试网已有的 `tests/unit/test_generator_multi_source.py` 整函数字符化用例与 kitchen-sink R1/R4 快照（P0 已提供）。
4. **不引入新依赖**；**不改行为只改结构**（唯一例外 = F#5/F#6 修漂移，属本契约范围）。
5. **禁止反向降级断言**（改断言、删断言、加 skip 骗绿一律打回）。
6. **铁律：raw_overrides 行为一字不动**——前端只写 cells/materials/tally/sdef 4 key + 空串=无覆盖 + 1145 门控（raw_tally 判的是 tally key，非当前 key），禁止凭直觉"修正"。
7. **边界**：P1 只动引擎/解析器/横幅词汇；**不碰** `gui/backend/api_server.py` 的路由表（25 端点）与 `docs/contracts/api.yaml`（无 API 变更，漂移闸门必须保持绿）。api_server.py 仅允许删 F#3 的 `[E0DBG]` print + 函数内 `import sys`。
8. 施工完成后按 §7 重锚定 `UI_ARCHITECTURE.md`、`review_findings.json`、`test_tech_debt.py` 注释行号，并向 PM 汇报 commit 索引。

---

## 1. F#7 —— pymcnp 函数内 import 提到模块顶部

### 1.1 目标
`inp_generator.py:110` `from pymcnp import inp as pymcnp_inp` 在 `_generate_basic`（108）函数内，pymcnp 是硬依赖（requirements.txt）却延迟到调用期 import。提到模块顶部，实现**模块导入期 fail-fast**（pymcnp 缺失 → import 即炸，而非运行到生成 MODE 卡才炸）。

### 1.2 改动范围
- `inp_generator.py`：
  - **删除** 110 行函数内 `from pymcnp import inp as pymcnp_inp`。
  - **新增** 模块顶部（`from .banners import ...` 块之后，约 21 行处）`from pymcnp import inp as pymcnp_inp`。
  - `_generate_basic` 函数体其余逻辑一字不改（123-151 行 `pymcnp_inp.Mode/Nps/Ctme/Nonu` 引用保持不变）。

### 1.3 验收标准
| 测试 | 文件 | 期望 |
| :--- | :--- | :--- |
| `test_f7_pymcnp_imported_at_module_level` | tests/integration/test_tech_debt.py | 红→绿 |
| `test_f7_pymcnp_function_level_import_absent` | tests/integration/test_tech_debt.py | 红→绿 |

回归：`tests/unit/test_generator_basic.py` 全绿（`_generate_basic` 行为不变）；全量绿数 245→247（2 红转绿），余 4 红。

### 1.4 风险
- 模块 import 现在硬依赖 pymcnp：**确认 pymcnp 在测试环境与 PyInstaller sidecar 打包 spec（`gui/mcnp_sidecar.spec`）中均已捆绑**（pymcnp 在 requirements.txt，P0 245 绿已证测试环境可 import，`_generate_basic` 用例全绿即证据）。若打包漏装 pymcnp，sidecar 启动即崩——但这是预期的 fail-fast 行为，且是既有硬依赖，非新增。
- 无 import 环：pymcnp 不反向 import inp_generator。

---

## 2. F#3 —— 函数内 `import json` / `import sys` + `[E0DBG]` 残留清理

### 2.1 目标
消除 4 处函数内 import 遮蔽 + 5 处 `[E0DBG]` stderr 调试 print。grep `import json as` / `E0DBG` / 函数内 `import sys` 归零。

### 2.2 改动范围（全部函数内 import → 用模块级或删除）

**`app/generator/inp_generator.py`（模块级已有 `import json`，见 5 行）**
| 行 | 位置 | 改动 |
| :--- | :--- | :--- |
| 631 | `_generate_kcode` 内 `import json as _json` | 删除；633 行 `_json.loads` → `json.loads`；649 行 `(_json.JSONDecodeError, TypeError)` → `(json.JSONDecodeError, TypeError)` |
| 671 | `_generate_structured_distributions` 内 `import json as _json` | 删除；673 行 `_json.loads` → `json.loads`；674 行 `(_json.JSONDecodeError, TypeError)` → `(json.JSONDecodeError, TypeError)` |

**`app/generator/parsers/core.py`**
| 行 | 位置 | 改动 |
| :--- | :--- | :--- |
| 826-827 | `_parse_card_with_continuation` 内 `import sys` + `[E0DBG] print` | 删除这两行，函数其余逻辑一字不动 |
| 1018-1019 | `parse_data_cards` E0 分支内 `import sys` + `[E0DBG] E0 line print` | 删除 |
| 1021 | `parse_data_cards` E0 分支 `[E0DBG] E0 vals print` | 删除 |

**`app/generator/parsers/__init__.py`**
| 行 | 改动 |
| :--- | :--- |
| 138-140 | 删除 `import sys` + 两行 `[E0DBG] __init__` print |

**`gui/backend/api_server.py`（仅删调试，不动路由）**
| 行 | 改动 |
| :--- | :--- |
| 608-610 | 删除 `import sys as _s` + 两行 `[E0DBG] api tally` print |

可选（不 gated）：`api_server.py:602` 函数内 `import dataclasses` 一并提到模块顶部（一致性，无测试约束）。

### 2.3 验收标准
| 测试 | 文件 | 期望 |
| :--- | :--- | :--- |
| `test_f3_no_function_level_import_json_in_inp_generator` | tests/integration/test_tech_debt.py | 红→绿 |
| `test_f3_no_function_level_import_sys_in_parsers` | tests/integration/test_tech_debt.py | 红→绿 |
| `test_f3_no_function_level_import_re_in_inp_generator` | tests/integration/test_tech_debt.py | 保持绿（不回归） |

grep 归零（commit 前检查）：`grep -n "import json as" app/generator/`、`grep -rn "E0DBG" app/ gui/backend/`、`grep -n "import sys" app/generator/parsers/ gui/backend/api_server.py` 全部无命中。
回归：`tests/unit/test_generator_phys.py`（含 `test_ksrc_points_emitted_with_continuation`，走 `_generate_kcode` 的 json.loads 路径）全绿；`tests/parser/test_core_data_cards.py` 全绿；全量绿数 247→249。

### 2.4 风险
- `[E0DBG]` print 是纯调试，删除前确认不包裹任何逻辑分支（已核：均为 `print(..., file=sys.stderr)` 独立语句）。
- `_generate_kcode` 内 `json.loads` 的异常兜底路径（`except (json.JSONDecodeError, TypeError)` → KSRC_FAILED_BANNER）必须保留，只改符号不改语义。

---

## 3. F#4 —— 单源 SDEF 两分支合并为 `_build_sdef_parts(src, include_special)`

### 3.1 目标
`_generate_single_source`（247-310）Dn 分支（254-290，含 6 扩展字段 + sdef_extra）与普通分支（292-310，不含）是 ~25 行纯复制。合并为单一构造函数，DRY 消除。**输出字节不变**（两分支公共字段逐 token 一致是 F#4 既有断言）。

### 3.2 改动范围
`inp_generator.py:247-310`：

```python
def _build_sdef_parts(src: SourceData, include_special: bool) -> list[str]:
    """单源 SDEF 字段构造（F#4 seam）。include_special=True 时含 6 扩展字段 + sdef_extra。

    字段顺序/条件与合并前完全一致：PAR ERG [POS 三态] DIR WGT CEL TME VEC AXS RAD EXT
    [+ SUR NRM TR CCC ARA RATE sdef_extra]。POS 三态：
      _all_same_d  → POS=Dn（三分量同 D 引用）
      _pos_ref     → X=/Y=/Z=（逐轴 D 引用或 F-续值）
      普通          → POS=x y z（仅三分量齐全时）
    """
    parts = ["SDEF"]
    if src.par:   parts.append(f"PAR={src.par}")
    if src.erg:   parts.append(f"ERG={src.erg}")
    _all_same_d = (src.pos_x and src.pos_y and src.pos_z
                   and src.pos_x == src.pos_y == src.pos_z and _is_d_ref(src.pos_x))
    _pos_ref = any(_is_d_ref(v) for v in (src.pos_x, src.pos_y, src.pos_z) if v)
    if _all_same_d:
        parts.append(f"POS={src.pos_x}")
    elif _pos_ref:
        if src.pos_x: parts.append(f"X={src.pos_x}")
        if src.pos_y: parts.append(f"Y={src.pos_y}")
        if src.pos_z: parts.append(f"Z={src.pos_z}")
    else:
        pos_parts = [v for v in (src.pos_x, src.pos_y, src.pos_z) if v]
        if len(pos_parts) == 3:
            parts.append(f"POS={' '.join(pos_parts)}")
    if src.dir_:  parts.append(f"DIR={src.dir_}")
    if src.wgt:   parts.append(f"WGT={src.wgt}")
    if src.cel:   parts.append(f"CEL={src.cel}")
    if src.tme:   parts.append(f"TME={src.tme}")
    if src.vec:   parts.append(f"VEC={src.vec}")
    if src.axs:   parts.append(f"AXS={src.axs}")
    if src.rad:   parts.append(f"RAD={src.rad}")
    if src.ext:   parts.append(f"EXT={src.ext}")
    if include_special:
        if src.sur:  parts.append(f"SUR={src.sur}")
        if src.nrm:  parts.append(f"NRM={src.nrm}")
        if src.tr:   parts.append(f"TR={src.tr}")
        if src.ccc:  parts.append(f"CCC={src.ccc}")
        if src.ara:  parts.append(f"ARA={src.ara}")
        if src.rate: parts.append(f"RATE={src.rate}")
        if src.sdef_extra: parts.append(src.sdef_extra)
    return parts

def _generate_single_source(src: SourceData) -> list[str]:
    has_d_or_extra = any(_is_d_ref(v) for v in (src.par, src.erg, src.dir_, src.wgt,
                                                src.cel, src.tme, src.rad, src.ext,
                                                src.axs, src.vec, src.pos_x, src.pos_y, src.pos_z)
                         ) or any((src.sur, src.nrm, src.tr, src.ccc, src.ara, src.rate, src.sdef_extra))
    return ["  ".join(_build_sdef_parts(src, include_special=has_d_or_extra))]
```

**注意**：普通分支（`include_special=False`）下 `has_d_or_extra` 为 False 保证任何 pos 分量都不是 D 引用，故合并后统一走 `_pos_ref`/`_all_same_d` 分支也不会触发（行为等价）；扩展字段仅在 Dn 分支出现——这是 F#4 pin 的核心。

### 3.3 验收标准
| 测试 | 文件 | 期望 |
| :--- | :--- | :--- |
| `test_f4_extended_fields_only_in_dn_branch` | tests/integration/test_tech_debt.py | 保持绿 |
| `test_f4_common_fields_equivalent_across_branches` | tests/integration/test_tech_debt.py | 保持绿 |
| `test_single_normal_common_fields` / `test_single_partial_pos_no_pos_emitted` / `test_single_dn_ref_uses_x_y_z` / `test_single_pos_dn_ref_three_axes` / `test_single_extended_fields_only_in_dn_branch` / `test_single_no_extended_fields_not_in_output` | tests/unit/test_generator_sdef.py | 全绿（字节不变） |

回归：`test_sdef_single_source_delegates`（pin `SDEF  ERG=14.0  POS=0 0 0` 精确串）保持绿；`test_r2_single_source_fields_survive` 保持绿。全量绿数 249。

### 3.4 风险
- 合并后 POS 处理对两分支共用——已验证普通分支不会带 D 引用，无行为漂移；若将来新增字段，只需加 `include_special` 块一行，这正是 DRY 收益。
- 禁止顺手改 `_generate_single_source` 的字段顺序（PIN 了 `SDEF  ERG=14.0  POS=0 0 0`）。

---

## 4. F#5 + F#6（本轮核心）—— 多源重构 + SDEF 漂移消除

### 4.1 目标
`_generate_multi_source`（375-519，145 行）拆 5 个函数 + 单一 `SDEF_FIELD_SPECS` 表驱动（值收集 / add_dist 标注 / SI-SP 映射三处枚举合一）；`add_dist` 闭包改纯函数；分布回放 `_generate_distribution_sdef`（313-372）一并处理。**验收 = kitchen-sink R1/R4 转绿**，即 §0.5.5 复合根因清单第 2-5 项 + SI 值空格归一化逐项消除，多源表示字节稳定（g1 == g2 恒定，当前实测残留 2102→2110 归零）。

### 4.2 §0.5.5 复合根因 → P1 消除对照表

| # | §0.5.5 因子 | P1 归属 | 消除方案 | 落点（动工前锚点） |
| :--- | :--- | :--- | :--- | :--- |
| 1 | C 注释头泄漏 | F-A（P0 已修） | — | — |
| 2 | `POS=F D1`→`X=F Y=D1` 逐轴重组 | **F#5/F#6** | 分布回放 POS 处理加 F-dist 分支：`_px` 匹配 `^F\d*$`（大小写不敏感）且 `_py` 为 D 引用且 `_pz` 为空 → 原样 `POS={_px} {_py}`（= `POS=F D1`）。**解析侧无需改**（`parse_sdef_fields` 已把 `POS=F D1` 拆为 `sdef_pos_x="F"` / `sdef_pos_y="D1"`，现状即足够） | `_generate_distribution_sdef` POS 段 |
| 3 | `TME=D6`→`TME=0.0` 退标量 | **F#5/F#6** | 多源 `sdef_extra` 去重：`sdef_extra` 中以 `KEY=` 开头的片段，若 `KEY` 已在当前 SDEF 中作为分布关键字（∈ `dist_names`），剥离该片段。kitchen-sink 的 source[0].sdef_extra=`TME=0.0` 与 `TME=D6` 冲突 → 剥离 → g1 只剩 `TME=D6`；parse 得 `sdef_tme="D6"`，回放 `TME=D6`。**仅当 KEY 是分布时才剥离**（标量-标量重复走 sdef_extra 天然 round-trip，不动） | `_generate_multi_source`（F#5 拆出的 SDEF 构造函数） |
| 4 | `SI1 V`→`SI1 L` 变型 | **F#5/F#6** | `_parse_sisp_structured` 的 SI 类型表（core.py:126 `("L","H","A","S","Q","T","F")`）**加 "V"**。否则 `SI1 V ...` 的 `V` 被当数值吞掉且 typ 落回 L | `parsers/core.py:126` |
| 5 | 分布注释 `C  {n} sources, probability keyed to D1` 丢失/移位 | **F#5/F#6** | ① banners.py 加构造器 `multi_source_comment_banner(n)` → `f"C  {n} sources, probability keyed to D1"`，`is_generator_banner` 的 `_DYNAMIC_PATTERNS` 加 `^C\s+\d+ sources, probability keyed to D1$`（parse 在 split_sections 拦截丢弃，不再进 other_cards）；② `_generate_distribution_sdef` 在 D1 键控链存在时重发该注释 | `banners.py` + `_generate_distribution_sdef` + `parsers/sections.py`（零改动，banners 拦截自动生效） |
| 6 | `&` 续行符污染 | F-E（P0 已修） | — | — |
| 7 | 多粒子计数 | F-C（P0 已修） | — | — |
| （附加）| **SI 值空格归一化** | **F#5/F#6** | 多源 SI 卡值全扁平化：每个 value 先 `split()` 拆 token，再 `'  '.join` 全部 token。VEC/AXS/V-向量（`0 0 1` / `5 5 5`）被 parse 扁平化后与回放 `'  '.join` 输出字节一致 | `_generate_multi_source` SI 构建 |
| （附加）| **SDEF 字段序不一致**（多源 POS 首位 vs 分布 PAR 首位 + DIR/WGT 互换） | **F#5/F#6** | 统一为**多源现状序**（POS, PAR, ERG, DIR, WGT, CEL, TME, VEC, AXS, RAD, EXT, SUR, NRM, TR, CCC, ARA, RATE），`_generate_distribution_sdef` 改从该序构建。D-index 与 SI 卡序由 `dist_params` 位置决定（与字段发射序解耦，见 §4.4） | `_generate_distribution_sdef` + `SDEF_FIELD_SPECS` |

### 4.3 拆函数设计（`_generate_multi_source` → 5 个纯/半纯函数）

当前 145 行的 5 个子关注点（review_findings F#5）：(a) 值收集 384-403、(b) 概率归一 405-417、(c) 方差检测 419-425、(d) SDEF 构造 451-499、(e) SI/SP 构造 501-517。拆为：

```python
# (a) 值收集：SDEF_FIELD_SPECS 驱动，返回 {keyword: [values...]} + prob + sdef_extra
def _collect_source_values(sources: list[SourceData]) -> tuple[dict[str, list[str]], list[str], str]:
    """返回 (field_values, prob_list, first_sdef_extra)。field_values 键 = 各 spec.keyword
    （POS 特殊拆三键：POS_X/POS_Y/POS_Z 三个 list）；prob_list = [src.probability or '1' ...]。"""

# (b) 概率归一（含 NaN/inf 校验，可独立单测——F#5 的核心收益）
def _normalize_probabilities(prob_list: list[str], n_sources: int) -> list[str]:
    """float 化 → NaN/inf 抛 ValueError → 求和；total<=0（含 NaN）回退等概率 1/n；
    否则 p/total 格式化为 f"{:.6f}"。等价于现状 405-417。"""

# (c) 方差检测 + add_dist 纯函数化（等价于现状 419-449）
def _varying_dist_params(field_values: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    """按 SDEF_FIELD_SPECS 序收集 len(set(values))>1 的 (keyword, values)；
    POS_X/POS_Y/POS_Z 三键跨源任一分量不同 → 首插 ("POS_VEC", ["x y z", ...])。
    原 add_dist 闭包 = 本函数内部的一行判断，不再捕获外部状态。"""

# (d) SDEF 行构造（等价于现状 451-499，含 sdef_extra 去重）
def _build_multi_sdef_parts(sources, field_values, dist_params, n_sources) -> list[str]:
    """按 SDEF_FIELD_SPECS 序发射字段；D-index = dist_params.index(keyword) + 1
    （POS_VEC 恒占 D1）。发射规则与现状逐条一致：
      - POS：pos_differ → `POS=F D{1}`；else 三分量齐全 → `POS=x y z`
      - 首组（PAR/ERG/DIR/WGT）：在 dist_names → `{kw}=D{di}`；
        else PAR→`PAR={default}`（无条件）、WGT→`WGT={default}`（无条件）、
        ERG/DIR→`{kw}={default}`（default 非空才发）
      - 次组（CEL..RATE）：在 dist_names → `{kw}=D{di}`；else vals[0] 非空 → `{kw}={vals[0]}`
      - sdef_extra：取 sources[0].sdef_extra，剥离已在 dist_names 的 `KEY=` 片段（根因#3）"""

# (e) SI/SP 构造（等价于现状 501-517 + 值扁平化）
def _build_multi_sisp_cards(dist_params, prob_norm, n_sources) -> list[str]:
    """SI 卡序 = dist_params 序；POS_VEC → `SI{di}  V  平坦值`，其余 → `SI{di}  L  平坦值`；
    首张 SI 的 SP 带 prob_norm（`SP{di}  {prob}`），其余 `SP{di}  D1`；
    dist_params 非空 → 末尾 `multi_source_comment_banner(n_sources)`。"""

def _generate_multi_source(sources):
    field_values, prob_list, sdef_extra = _collect_source_values(sources)
    prob_norm = _normalize_probabilities(prob_list, len(sources))
    dist_params = _varying_dist_params(field_values)
    sdef_parts = _build_multi_sdef_parts(sources, field_values, dist_params, sdef_extra)
    lines = ["SDEF  " + "  ".join(sdef_parts)]
    lines += _build_multi_sisp_cards(dist_params, prob_norm, len(sources))
    return lines
```

### 4.4 `SDEF_FIELD_SPECS` 表结构建议

```python
# 单一事实来源：字段序 = 多源现状发射序（POS 首位）。三处枚举（值收集/方差标注/SI-SP）
# 全部改读本表。source_attr/adv_attr 分别供多源与分布回放取字段。
SDEF_FIELD_SPECS = (
    # (keyword, source_attr, adv_attr, si_type, special)
    ("POS",  None,   None,      "V", "pos"),    # 特殊：三分量 + F-分布（见 4.5）
    ("PAR",  "par",  "sdef_par",  "L", None),
    ("ERG",  "erg",  "sdef_erg",  "L", None),
    ("DIR",  "dir_", "sdef_dir",  "L", None),
    ("WGT",  "wgt",  "sdef_wgt",  "L", None),
    ("CEL",  "cel",  "sdef_cel",  "L", None),
    ("TME",  "tme",  "sdef_tme",  "L", None),
    ("VEC",  "vec",  "sdef_vec",  "L", None),
    ("AXS",  "axs",  "sdef_axs",  "L", None),
    ("RAD",  "rad",  "sdef_rad",  "L", None),
    ("EXT",  "ext",  "sdef_ext",  "L", None),
    ("SUR",  "sur",  "sdef_sur",  "L", None),
    ("NRM",  "nrm",  "sdef_nrm",  "L", None),
    ("TR",   "tr",   "sdef_tr",   "L", None),
    ("CCC",  "ccc",  "sdef_ccc",  "L", None),
    ("ARA",  "ara",  "sdef_ara",  "L", None),
    ("RATE", "rate", "sdef_rate", "L", None),
)

def _src_field(src, spec):      # spec.special=="pos" → (pos_x,pos_y,pos_z)；else getattr(src, attr)
def _adv_field(adv, spec):      # spec.special=="pos" → (sdef_pos_x,sdef_pos_y,sdef_pos_z)；else getattr(adv, adv_attr)
```

表驱动的三处落点：`_collect_source_values` 遍历表取 source_attr；`_varying_dist_params` 按表序判变差；`_build_multi_sdef_parts` 按表序发射。新增字段 = 表加一行，三处自动生效（F#6 消除三处枚举）。

### 4.5 分布回放 `_generate_distribution_sdef`（一并处理，字节对齐）

`_generate_distribution_sdef`（313-372）改为**与多源一致的字段序 + POS F-dist 分支 + 注释重发**：

1. **字段序**：按 `SDEF_FIELD_SPECS` 序（POS, PAR, ERG, DIR, WGT, CEL, TME, VEC, AXS, RAD, EXT, SUR, NRM, TR, CCC, ARA, RATE），值从 `_adv_field(adv, spec)` 取；非空才发（PAR/WGT 空值条件发射保持现状——kitchen-sink 全字段非空，不影响字节对齐）。
2. **POS 四态**（替换现 319-331 三态）：
   - `_px` 匹配 `^F\d*$`（大小写不敏感）且 `_py` 是 D 引用且 `_pz` 空 → `POS={_px} {_py}`（根因 #2：`POS=F D1`）；
   - 否则 `_all_same_d` → `POS={_px}`；
   - 否则 `_pos_ref` → `X=/Y=/Z=`；
   - 否则三分量齐全 → `POS=x y z`。
3. **SI/SP 段**（350-370 现逻辑不动）：结构化分布优先（`_generate_structured_distributions`），`sdef_raw_text` 兜底——两者都已与多源字节对齐（见 4.2 SI 值归一化，g1 多源侧已扁平化以匹配回放）。
4. **注释重发**：结构化分布 ≥2 条且存在 SP 卡为 D 引用（`sp.values == ["D1"]` 这类键控链）时，在 SI/SP 段末尾发 `multi_source_comment_banner(n)`，`n = 首张含数值 SP 卡的 values 长度`（kitchen-sink：SP1 `0.600000 0.400000` → n=2）。**保守触发**：单分布无 D1 键控链（如 avr13/prob41c/inp24）不发，样例输出不变。
5. `_generate_distribution_sdef` 同时服务 `test_distribution_sdef_fields`（sdef_pos_x/y/z="0" → POS=0 0 0 路径）与 `test_distribution_sdef_raw_text_si_sp_prefix`——两用例不受影响。

### 4.6 解析器/横幅最小改动（P1 附带，修漂移所必需）

| 文件 | 行 | 改动 | 根因 |
| :--- | :--- | :--- | :--- |
| `app/generator/parsers/core.py` | 126 | SI 类型元组加 `"V"` | #4 |
| `app/generator/banners.py` | 构造器区 + `_DYNAMIC_PATTERNS` | 加 `multi_source_comment_banner(n)` + `^C\s+\d+ sources, probability keyed to D1$` | #5 |

`sections.py` 零改动：`is_generator_banner` 命中即被既有拦截逻辑丢弃。

### 4.7 验收标准

| 测试 | 文件 | 期望 |
| :--- | :--- | :--- |
| `test_r1_fixed_point_kitchen_sink` | tests/integration/test_roundtrip.py | **红→绿** |
| `test_r4_kitchen_sink_full_roundtrip` | tests/integration/test_roundtrip.py | **红→绿** |
| `test_probability_normalization_table` / `test_all_zero_probability_falls_back_to_equal` / `test_nan_probability_raises` / `test_inf_probability_raises` | tests/unit/test_generator_multi_source.py | 全绿（概率归一是 F#5 拆出的纯函数，可独立测） |
| `test_multi_source_*`（结构/分布/注释 8 例） | tests/unit/test_generator_multi_source.py | 全绿（字节与现状一致，除 SI 值空格归一化——无测试 pin 旧分组空格） |
| `test_distribution_sdef_fields` / `test_distribution_sdef_raw_text_si_sp_prefix` | tests/unit/test_generator_sdef.py | 全绿（分布回放改序后仍逐 token 命中） |
| `test_structured_distributions_full` / `test_structured_distributions_fn_code` | tests/unit/test_generator_sdef.py | 全绿 |
| `test_r2_single_source_fields_survive` / `test_r2_multi_source_roundtrips_to_distribution_mode` | tests/integration/test_roundtrip.py | 保持绿（多源 round-trip 转 distribution 语义不变） |
| `test_f6_kitchen_sink_multi_source_all_fields_present` | tests/integration/test_tech_debt.py | 保持绿（17 字段各出现一次） |
| 样例 R1 | `test_r1_fixed_point_sample_*` + `test_smoke_r1_fixed_point[*]` | 保持绿（分布回放改序后 g1==g2 自洽；**必须复跑确认无字节级意外**） |

全量绿数 249→**251**（kitchen-sink R1/R4 转绿），**0 红**。

### 4.8 风险（本轮最易踩）
- **拆 seam 前必须先过字符化门**：`_build_multi_*` 四个函数拆出后、未加漂移修复前，`test_generator_multi_source.py` 必须全绿（证明重构未改字节）；此步 kitchen-sink R1/R4 允许仍红（结构性拆解）。
- **D-index 与 SI 卡序解耦**：D 引用号由 `dist_params` 位置决定，与 SDEF 字段发射位置无关。误按发射序编号 → 分布错位，R1 静默红。
- **sdef_extra 去重只针对分布关键字**：标量-标量重复不得去（走 sdef_extra 天然 round-trip）。去重过度会把用户合法 sdef_extra 字段吞掉。
- **SI 值扁平化只改多源侧**：`_generate_structured_distributions` 的 `'  '.join` 不动（`test_structured_distributions_full` pin `SP1  0.5  0.5` 双空格）。多源侧扁平化使其与回放一致。
- **样例 R1 必须复跑**：分布回放改字段序会改 avr13/prob41c/inp24 的生成字节（g1/g2 都改，理论上自洽）；若意外红，回到 §4.5 查 POS/注释触发是否误伤单分布样例。
- **注释触发保守**：只在 D1 键控链存在时发；多源单分布（仅一个字段变差）边角有 g1 发注释/g2 不发的非对称（无测试覆盖，记录为已知边角，勿擅自扩大注释触发面）。

---

## 5. F#1 —— raw_overrides 守卫收敛 + 1145 门控保留

### 5.1 目标
8 处 `raw = (overrides.get(key) or "").strip(); if raw: banner+split else: _generate_*` 复制粘贴（1069/1081/1107/1115/1131/1139/1147/1168）收敛为 `_apply_raw_override(...)` 一行调用；1145 变体（raw_tally 门控 En/T0/Tn）走同一判空助手并**保留门控语义**（判的是 tally key，非当前 key）。可选 `_validate_raw_section` 只告警不改输出。**铁律：raw_overrides 行为一字不动。**

### 5.2 助手签名

```python
def _raw_override_text(overrides: dict, key: str) -> str:
    """空串/缺省/纯空白 = 无覆盖（现状语义）。"""
    return (overrides.get(key) or "").strip()

def _has_raw_override(overrides: dict, key: str) -> bool:
    return bool(_raw_override_text(overrides, key))

def _apply_raw_override(lines: list[str], overrides: dict, key: str,
                        banner: str, generator) -> None:
    """raw_overrides 守卫（收敛 8 处复制粘贴）。
    key 有非空覆盖 → 打 RAW_*_BANNER + 追加覆盖文本（split("\\n")）；
    否则走 generator()（返回待追加行列表），与现状语义逐字一致。
    banner 是 RAW_*_BANNER 常量；generator 闭包内可含自身节头（如 cells 的 cell_cards_banner）。"""
    if _has_raw_override(overrides, key):
        lines.append(banner)
        lines.extend(_raw_override_text(overrides, key).split("\n"))
    else:
        lines.extend(generator())
```

调用例（8 处逐一收敛）：
```python
_apply_raw_override(lines, overrides, "cells", RAW_CELL_BANNER, lambda: (
    (lambda cl: ([cell_cards_banner(len(cl))] + cl) if cl else [])(_generate_cells(cells))))
_apply_raw_override(lines, overrides, "materials", RAW_MAT_BANNER, lambda: _generate_materials(materials))
_apply_raw_override(lines, overrides, "sdef", RAW_SDEF_BANNER, lambda: _sdef_dispatch(deck, adv, sources))  # 现 1115-1129 的分派逻辑封进闭包/小函数
_apply_raw_override(lines, overrides, "cut", RAW_CUT_BANNER, lambda: _generate_cut(tally))
```

### 5.3 1145 门控保留（raw_tally 语义）

现状 1156-1166：`raw_tally = (overrides.get("tally") or "").strip()`，`if not raw_tally:` 才生成 En / T0 / Tn。收敛后**必须**保持"判 tally key、抑制 En+T0+Tn"：

```python
# En 分计数能量箱（仅当 tally 无有效原始文本覆盖时自动生成）—— 门控看 tally key，非 e0/cut
if not _has_raw_override(overrides, "tally"):
    en_lines = _generate_en_cards(tally)
    if en_lines: lines.extend(en_lines)

# T0 全局时间网格 + Tn 分计数时间箱
if not _has_raw_override(overrides, "tally"):
    t0_lines = _generate_time_mesh(tally)
    if t0_lines: lines.extend(t0_lines)
    tn_lines = _generate_tn_cards(tally)
    if tn_lines: lines.extend(tn_lines)
```

门控语义 pin（`test_e0_override_does_NOT_suppress_en_t0_tn` / `test_cut_override_does_not_affect_en_t0_tn`）**禁止"顺手修正"为判当前 key**。

### 5.4 可选 `_validate_raw_section`

```python
def _validate_raw_section(key: str, raw_text: str) -> list[str]:
    """校验 raw 覆盖段的基本 MCNP 语法（行尾缺 & / 空卡等），只收集告警，不改输出。
    默认不阻断生成；告警经 api_server 透传（可选，不 gated by 测试）。"""
    return []
```
调用：`_apply_raw_override` 的 raw 分支内 `warnings += _validate_raw_section(key, raw_text)`（`warnings` 列表在 `generate_inp_from_deck` 收集；**不得改变 lines 内容**）。

### 5.5 验收标准
| 测试 | 文件 | 期望 |
| :--- | :--- | :--- |
| `test_raw_override_replaces_generated_section[*]`（8 参） | tests/unit/test_generator_overrides.py | 保持绿 |
| `test_raw_override_empty_string_means_no_override[*]` / `test_raw_override_whitespace_means_no_override[*]` | tests/unit/test_generator_overrides.py | 保持绿 |
| `test_raw_override_all_keys_simultaneously` | tests/unit/test_generator_overrides.py | 保持绿 |
| `test_raw_tally_override_suppresses_en_t0_tn` | tests/unit/test_generator_overrides.py | 保持绿（1145 门控） |
| `test_e0_override_does_NOT_suppress_en_t0_tn` / `test_cut_override_does_not_affect_en_t0_tn` | tests/unit/test_generator_overrides.py | 保持绿（门控只认 tally key） |

grep 归零：`grep -n "overrides.get" app/generator/inp_generator.py` 只应命中 `_raw_override_text`（+ 已删的 8 处不在）；全量绿数保持 **251**。

### 5.6 风险
- **铁律最大坑**：收敛时把门控从"判 tally key"改成"判当前 key" → `test_e0_override_does_NOT_suppress_en_t0_tn` 立刻红。禁止动语义。
- 空串/空白语义（`or ""` + `.strip()`）必须保留在 `_raw_override_text`，误改成 `if key in overrides` 会让"空串=无覆盖"失效。
- `sdef` 分派（现 1120-1128：distribution/kcode/surface/fixed 四分支）封进闭包时不得改分派顺序。

---

## 6. 施工顺序与每步验收（参照 P0 契约 §0.5 风格）

分支：`git checkout -b refactor/generator-tech-debt`（自 `experiment/geouned`）。

| 步 | 改动 | 该步验收（全量绿数） | 备注 |
| :--- | :--- | :--- | :--- |
| 1. F#7 | pymcnp 提到模块顶部（§1） | **247 绿 / 4 红**；`test_f7_*`×2 转绿；`test_generator_basic.py` 零回归 | 最简热身 |
| 2. F#3 | 4 文件函数内 import + E0DBG 清理（§2） | **249 绿 / 2 红**；`test_f3_*`×2 转绿；grep `import json as`/`E0DBG`/函数内 `import sys` 归零 | 每删一处跑一次 `test_generator_phys.py` + `test_core_data_cards.py` 防误删逻辑 |
| 3. F#4 | `_build_sdef_parts` 合并两分支（§3） | **249 绿 / 2 红**；`test_f4_*` 保持绿；`test_generator_sdef.py` 全绿（字节不变） | 纯 DRY，无行为变化 |
| 4. F#5+F#6 | §4 全部 | 见 §6.4 子步 | 核心，拆 3 子步 |
| 5. F#1 | raw_overrides 收敛（§5） | **251 绿 / 0 红**；`test_generator_overrides.py` 全绿 | 最后做，最低风险面 |
| 6. 收尾 | 全量复跑 ×2、review_findings 标 resolved、UI_ARCHITECTURE 重锚定（§7） | **251 绿 / 0 红** ×2 稳定 | 向 PM 汇报 commit 索引 |

### 6.4 F#5+F#6 内部子步（拆分三子步，每子步独立 commit）

| 子步 | 改动 | 验收 |
| :--- | :--- | :--- |
| 4a. **字符化门（拆 seam 前置）** | 先把 `_collect_source_values`/`_normalize_probabilities`/`_varying_dist_params`/`_build_multi_sdef_parts`/`_build_multi_sisp_cards` 五个函数拆出，**输出与现状逐字节一致** | `test_generator_multi_source.py` 全绿（行为 pin）；kitchen-sink R1/R4 仍红（结构未改漂移）；其余全量不回归。**此子步不绿不得进 4b** |
| 4b. **漂移修复（生成/横幅/解析）** | §4.2 根因 #3 去重 + #4 SI V 型 + #5 banners 注释 + SI 值扁平化；`_generate_distribution_sdef` 改字段序 + POS F-dist 分支 + 注释重发（§4.5） | `test_r1_fixed_point_kitchen_sink` 红→**绿**；`test_r4_kitchen_sink_full_roundtrip` 红→**绿**；`test_generator_multi_source.py`/`test_generator_sdef.py` 全绿；样例 R1（prob41c/avr13/inp24 + minimal）**保持绿（必须复跑）** |
| 4c. **全量回归** | 全量 `python -m pytest tests/ -v` | **251 绿 / 0 红**（4a+4b 累计），R1/R4 kitchen-sink 稳定绿 |

---

## 7. 重锚定清单（重构大幅移动行号，所有受影响锚点）

动工前基线行号（2026-08-12 已 Grep 核验）：

| 符号 | 动工前行号 |
| :--- | :--- |
| `from pymcnp import inp`（F#7） | inp_generator.py:110 |
| `import json as _json`（F#3） | inp_generator.py:631 / 671 |
| `import sys` + `[E0DBG]`（F#3） | core.py:826-827 / 1018-1021；`__init__.py`:138-140；api_server.py:608-610 |
| `def _generate_single_source`（F#4） | inp_generator.py:247（Dn 分支 254-290 / 普通分支 292-310） |
| `def _generate_distribution_sdef`（F#5/F#6） | inp_generator.py:313-372 |
| `def _generate_multi_source`（F#5/F#6） | inp_generator.py:375-519（值收集 384-403 / 概率归一 405-417 / 方差 419-425 / SDEF 451-499 / SI-SP 501-517；add_dist 430-449） |
| `def _generate_kcode` | inp_generator.py:603 |
| `def _wrap_long_lines` | inp_generator.py:1010 |
| raw_overrides 守卫 | inp_generator.py:1069/1081/1107/1115/1131/1139/1147/1168；raw_tally 门控 1156-1166 |
| `_parse_sisp_structured` SI 类型表 | parsers/core.py:126 |
| `_DYNAMIC_PATTERNS` | banners.py:115-123 |

### 7.1 施工完成后必须重锚定的文档
1. **`app/generator/review_findings.json`**：逐项更新为 resolved，附 commit 索引（F#3/F#7/F#4/F#5/F#6/F#1；F#2 已 Resolved 保持）。行号字段改为重锚定后值或标注"已重构，行号作废"。
2. **`app/UI_ARCHITECTURE.md`**：
   - §5.2 守卫行号表（1069/1081/1107/1115/1131/1139/1147/1168 + 1156）→ 收敛后 `_apply_raw_override` 调用点行号。
   - §5.3 raw_tally 门控说明 → 更新为 `_has_raw_override(overrides, "tally")` 形式（语义不变）。
   - §7 技术债地图 F#1-F#7 锚点行号 → 全部重锚定；F#3/F#7 pin 状态列改"已清偿"。
   - §7.1 E0DBG 位置表 → 标记已清除。
   - §6 往返保真边界 → 补"多源↔分布表示字节稳定"说明。
3. **`tests/integration/test_tech_debt.py`**：文件注释中的旧行号（622/660/821/1013/138/98）更新为现状（AST 断言本身行号不敏感，仅注释维护）。
4. **`PROJECT_MEMORY.md`**：§6 技术债清单 7 项全标已清偿；§8 变更日志补 P1 完成记录。
5. **`docs/contracts/bugfix-f1-f5.md`**：§7/§8 的 P1 锚点为历史记录，不更新（P1 契约独立成文，交叉引用本文件）。

**不影响**：`docs/contracts/api.yaml`（无 API 变更）、`tests/integration/test_api_contract.py`（读 api_server 路由，不读 inp_generator）、`gui/` 前端（无契约层变更）。

### 7.2 重锚定方法
`grep -n` 定位符号名（不靠记忆行号）：`from pymcnp import inp`、`import json as`、`E0DBG`、`def _generate_single_source`、`def _build_sdef_parts`、`def _generate_multi_source`、`def _collect_source_values`、`def _build_multi_sisp_cards`、`SDEF_FIELD_SPECS`、`def _generate_distribution_sdef`、`def _apply_raw_override`、`def _has_raw_override`、`multi_source_comment_banner`。commit 后模式归零：`grep -n "overrides.get" inp_generator.py` 仅 `_raw_override_text` 一处。

---

## 8. 风险预警（重构最易踩的坑）

1. **F#7 模块级 import 的打包连锁**：pymcnp 移到模块顶部后，任何 `import app.generator.inp_generator`（含 api_server、所有测试）都在导入期依赖 pymcnp。确认 PyInstaller spec 与测试环境均已装 pymcnp（P0 已证），否则 sidecar 启动即崩。
2. **F#3 误删逻辑**：`[E0DBG]` print 是纯 stderr 调试，但删除前逐行确认不是 `if ...: print(...)` 的条件块一部分；`json.loads` 异常兜底（KSRC_FAILED_BANNER）只换符号不改语义。
3. **F#4 字段序 PIN**：`test_sdef_single_source_delegates` 钉死 `SDEF  ERG=14.0  POS=0 0 0`（PAR 之后 ERG 再 POS）。合并 `_build_sdef_parts` 时禁止"顺手统一"到多源序。
4. **F#5/F#6（最高危）**：
   - 4a 字符化门不绿就进 4b → 漂移修复和结构重构混在一起，无法定位回归。
   - **D-index 与 SI 卡序由 `dist_params` 位置决定**，与 SDEF 字段发射序解耦；按发射序编号会静默错位。
   - **sdef_extra 去重仅限分布关键字**，标量-标量重复（如 `PAR=n` + sdef_extra `PAR=n`）不去；去重过度吞合法字段。
   - **SI 值扁平化只在多源侧**；`_generate_structured_distributions` 的 `'  '.join` 与 `test_structured_distributions_full`（pin `SP1  0.5  0.5`）不动。
   - 分布回放改字段序会改样例生成字节——**样例 R1 必须复跑**，这是最容易"看起来绿实则依赖顺序不变"的隐蔽回退点。
   - 注释触发必须保守（仅 D1 键控链），防止 avr13 这类单分布样例输出被污染。
5. **F#1 门控语义**：收敛 8 守卫时把 1145 门控"顺手修正"为判当前 key → `test_e0_override_does_NOT_suppress_en_t0_tn` 红。**门控判 `tally` key 是特性不是 bug。**
6. **每步全量**：一次改多项后一起跑难以定位回归；按 §6 每步跑全量 + 该步关联测试。
7. **边界不越 P0**：`api.yaml`/api_server 路由/前端契约层一律不碰；`_wrap_long_lines` 不动（F-E 已修 `&`，且是确定性纯函数）。

---

## 9. 交付检查清单

- [ ] F#7：`test_f7_*`×2 绿；pymcnp 在模块顶部
- [ ] F#3：`test_f3_no_function_level_import_json_in_inp_generator` + `test_f3_no_function_level_import_sys_in_parsers` 绿；grep `import json as` / `E0DBG` / 函数内 `import sys` 归零
- [ ] F#4：`test_f4_*`×2 保持绿；`_generate_single_source` 输出字节不变
- [ ] F#5/F#6：`test_r1_fixed_point_kitchen_sink` + `test_r4_kitchen_sink_full_roundtrip` **红→绿**；`test_generator_multi_source.py` / `test_generator_sdef.py` 全绿；样例 R1（prob41c/avr13/inp24/minimal）保持绿；§0.5.5 因子 #2-#5 + SI 值空格归一化逐项对照表核销
- [ ] F#1：`test_generator_overrides.py` 全绿（含 1145 门控三例）；8 守卫收敛为 `_apply_raw_override` 一行
- [ ] 全量 `python -m pytest tests/ -v` = **251 绿 / 0 红**（复跑 ×2 稳定）
- [ ] 无断言降级（用例总数 251 不变）、无 skip/pass 骗绿
- [ ] review_findings.json 7 项标 resolved + commit 索引；UI_ARCHITECTURE.md §5/§7 重锚定；test_tech_debt.py 注释行号更新；PROJECT_MEMORY.md 更新
- [ ] 未触碰 api.yaml / api_server 路由 / 前端契约层
