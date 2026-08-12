# 引擎缺陷修复契约（F-A ~ F-H）

> 契约人：架构师 | 施工方：后端 | 分支：`experiment/geouned`（**非 P1 重构范围**）
> 日期：2026-08-12 | 状态：**契约已锁定（2026-08-12 上级裁决修订）**
> 依据：`docs/qa-report.md` + 权威基线（干净基线 **234 通过 / 17 失败，0 测试误判，与首轮逐例一致**）；行号以动工前 Grep 重锚定为准，见 §8 漂移警告。
> 目标：本轮 M1.4 门禁达成 **245 绿 / 6 红**（F-A~F-E 修复 + 既有 129+73+7 零回归；6 红 = 4 技术债 F#3/F#7 + 2 kitchen-sink R1/R4），达成即放行 P1。
> 修订要点（2026-08-12 上级裁决）：**多源 SDEF 漂移（F#5/F#6 范围）归入 P1，不并入本轮修复**；kitchen-sink R1/R4 移出本轮验收。详见 §0.5。

---

## 0. 纪律（后端施工必读，违反即打回）

1. **修复 = 让测试断言由红转绿**。禁止反向降级测试断言（改断言、删断言、加 `skip` 来"骗绿"一律打回）。已 pin 的三项低优先缺陷（F-F/F-G/F-H）的 pin 断言属于"标记缺陷存在"，修复后**更新断言为正确行为**（改名/改期望，这是红转绿，不是降级）。**2026-08-12 修订：F-F/F-G/F-H 本轮不阻塞（可选翻新，见 §0.5.1）**，翻新时仍须写死正确行为断言，严禁 pass/skip/弱断言。
2. **每完成一项缺陷**：跑 `python -m pytest tests/ -v`，确认该项关联断言红→绿，且既有 129 生成器单测 + 73 解析器单测 + 7 契约闸门**零回归**。
3. **R1 是字节级不动点**：`g2 == generate(d)` 字节相等（从第二代起稳定），不是文本相等。任何"看起来对但字节不等"都不算通过。
4. **动引擎代码的行号以修复时 Grep 重锚定为准**。本契约的行号是动工前锚点（已在当前分支核验）。
5. 本次只做缺陷修复。P1 重构清单见 §7，**一律不碰**（含 `import json as _json`、`import sys`、`[E0DBG]` print、pymcnp import 提升、raw_overrides 守卫收敛等）。

---

## 0.5 上级裁决修订：本轮范围 / 门禁 / 终态 / P1 放行（2026-08-12）

> 本契约原以"17 红全部转绿 + R1/R4 全绿"为目标，已按上级最终裁决微调。
> 裁决：**多源 SDEF 漂移（F#5/F#6 范围）归入 P1，不并入本轮修复。**

### 0.5.1 本轮施工范围（已锁定，后端只做这些）

- **F-A**（C 注释头泄漏，含 minimal + 3 样例 R1）+ **F-B**（validate_deck CellRow）+ **F-C**（多粒子计数）+ **F-D**（材料 options）+ **F-E**（`&` 续行污染）。
- **F-F / F-G / F-H**：确认**不阻塞**本轮门禁。翻新 pin 属可选——后端顺手做允许（§7 范围内），但不列为本轮验收；不翻新则 pin 断言保持现状（保持绿态标记缺陷存在），不计入终态 6 红。

### 0.5.2 本轮门禁（M1.4 重写）

minimal + 3 样例（prob41c / avr13 / inp24）R1 全绿 + F-B/F-C/F-D 红转绿
+ 既有 129 生成器单测 + 73 解析器单测 + 7 契约闸门**零回归**。
**不含 kitchen-sink R1/R4**（`test_r1_fixed_point_kitchen_sink` / `test_r4_kitchen_sink_full_roundtrip` 本轮允许保持红）。

### 0.5.3 本轮终态预期

**245 绿 / 6 红**。计算：234 基线 + 本轮 11 例红转绿（F-A 样例 R1 6 + F-B 3 + F-C 1 + F-D 1）= 245；
6 红 = 4 技术债（F#3/F#7）+ 2 kitchen-sink（R1/R4）。
原"17 红全部转绿"表述**废止**。

### 0.5.4 P1 放行条件

本轮达成 **245/6** 即放行 P1。P1 目标 = 把 6 红全部转绿（4 技术债 F#3/F#7 + 2 kitchen-sink R1/R4）。
kitchen-sink R1/R4 的复合根因清单见 §0.5.5，供 P1 重构 `_generate_multi_source`（F#5/F#6）时对照。

### 0.5.5 kitchen-sink R1/R4 复合根因清单（P1 验收对照）

`test_r1_fixed_point_kitchen_sink` / `test_r4_kitchen_sink_full_roundtrip`（R1 字节不动点在
kitchen-sink deck 上不成立）是**复合根因**，非单一缺陷。权威基线确认（2026-08-12）：

| # | 根因因子 | 归属 | 本轮状态 |
| :--- | :--- | :--- | :--- |
| 1 | C 注释头泄漏（Cell/Surface/Data/Tallies 四头） | F-A | **本轮修复** |
| 2 | 多源 SDEF 字段重组漂移：`POS=F D1` → `X=F Y=D1`（位置向量 F 型 D 引用被重组为逐轴引用） | F#5/F#6（P1） | **本轮保持红** |
| 3 | 多源 SDEF 字段重组漂移：`TME=D6` → `TME=0.0`（TME 跨源不同生成 D 引用，round-trip 后退化为标量首值） | F#5/F#6（P1） | **本轮保持红** |
| 4 | 多源 SDEF 字段重组漂移：`SI1 V` → `SI1 L`（分布类型标记 V/L 丢失，回放变型） | F#5/F#6（P1） | **本轮保持红** |
| 5 | 分布注释丢失/移位：`C  {n} sources, probability keyed to D1`（不在 banner 词汇表，回 distribution 模式后不再原样锚定在 SI/SP 卡后） | F#5/F#6（P1） | **本轮保持红** |
| 6 | `&` 续行符污染字段 | F-E | **本轮修复** |
| 7 | 多粒子计数卡 `F4:N,P` parse 后丢失 | F-C | **本轮修复** |

代码位置（**P1 范围，本轮不碰**）：`app/generator/inp_generator.py:_generate_multi_source`（366-510 行，
含 452 行 `POS=F D1`、430/482 行 `TME=D`、497 行 `SI… V`、508 行分布注释）；
分布回放 `_generate_distribution_sdef`（304-363 行）。
本轮 F-A/F-E/F-C 修复后，第 2-5 项（多源漂移 + 分布注释）是 kitchen-sink R1/R4 保持红的唯一剩余阻塞。
**P1 F#5/F#6 重构时必须逐项对照消除，使表示字节稳定。**（漂移示例为权威基线确认的代表性观测，
P1 重构以实测为准逐项核对。）

---

## 1. F-A（致命，最高优先）—— R1 不动点不成立：生成器 C 注释头泄漏

### 1.1 根因

生成器在每节前输出 C 注释头（用户可见的 INP 输出风格），解析器把三种头分别吸收进结构化字段，造成逐代膨胀：

| 生成器头 | 生成位置（动工前） | 解析器吸收路径 | 膨胀机制 |
| :--- | :--- | :--- | :--- |
| `C  Cell Cards: N cells defined` | `inp_generator.py:1065` | `parsers/sections.py` 分节 → `parsers/core.py:parse_cells` 的 `pending_c`（161-177 行）关联到下一个栅元 `$` 注释 | 污染 `cell.comment`（spurious 注释） |
| `C  Surface Cards: N surfaces defined` | `inp_generator.py:1077` | `sections.py` 把 C 行计入 `surf_lines` → `core.py:parse_surfaces`（322-324）整段 verbatim 返回 → `deck.surfaces` 包含该头 | **每次生成 `len(surf_lines)` +1 → deck.surfaces 逐代累积头行 → 线性膨胀** |
| `C  ===== Data Cards =====` | `inp_generator.py:1082` | `parse_data_cards` 的 `pending_c`（882-904）在遇到非 M 卡时回落 `other_cards` 并重放 | **other_cards 逐代 +1 份头 → 线性累积** |
| `C  Tallies` | `inp_generator.py:522` | 同上（`pending_c` → `other_cards`） | 同上 |

已实测膨胀：kitchen-sink 2102→2266、prob41c 1097→1247（qa-report §2 F-A）。

**关键论证：此缺陷无法在生成器单侧根治。** 因为 `parse_surfaces` 对曲面段整段 verbatim 保留（含 C 行），生成器 `_generate_surfaces`（inp_generator.py:87-91）会把 deck.surfaces 里的头再次原样重发，且生成器还要再补一个新头 → 无论生成器头写成什么（除非法解析器不存），都会在 deck.surfaces 里累积。同理 other_cards 重放。**必须解析器侧拦截。**

### 1.2 修复方案 —— **F-A 裁决：方案 C（两者配合），以方案 A（解析器吸收防护）为主、方案 B（生成器头规范化）为辅**

#### 裁决理由

- **方案 B（仅改生成器头为不可吸收形式）单独不可行**：MCNP 注释只有 `C` 一种形式，而现有解析器对任意 `C` 行都会在三种吸收路径里吞掉（栅元注释 / 曲面 verbatim / other_cards）。不存在一种"合法 MCNP 注释且三阶段都天然惰性"的形式（用 `#` 头在语义上是错的，且会被解析为 raw 条件行）。方案 B 单独无法让 R1 成立。
- **方案 A（仅解析器防护）技术上可单独达成 R1**，但把生成器头字符串散落在解析器与生成器两处，属脆弱耦合——生成器文案一改，解析器漏认，R1 静默回红。
- **方案 C** 让"生成器 C 头"成为**冻结的、文档化的输出契约词汇**（`banners.py` 单点定义，生成器与解析器共享），R1 测试套件是漂移的兜底网（词汇漂移 → R1 立刻 RED，不会静默）。
- **保留用户可见风格**：C 头在生成输出里原样保留（用户仍能看到 `C  Cell Cards: N cells defined`），只是解析器不存储、每次生成在规范位置重放，因此**不改变用户可见输出风格**。
- **解析器通用性**：解析器"认识本生成器的节头"不是硬编码实现细节，而是与 `#ifdef` 预处理器行、`CUT:` 与 `C` 的消歧同类——解析器本就在编码输出契约知识。且识别只针对精确规范的节头词汇，不碰用户任意 C 注释。

#### 方案 A（主）：解析器拦截节头

**新增 `app/generator/banners.py`**（纯函数、零重依赖、不 import pymcnp/FreeCAD），作为节的单一事实来源：

```python
# 建议接口（实现由后端定，词汇表必须与下表一致）
def cell_cards_banner(n: int) -> str: ...      # "C  Cell Cards: {n} cells defined"
def surface_cards_banner(n: int) -> str: ...   # "C  Surface Cards: {n} surfaces defined"
DATA_CARDS_BANNER   = "C  ===== Data Cards ====="
TALLIES_BANNER      = "C  Tallies"
TR_BANNER           = "C  TR Transformations"
KSRC_BANNER         = "C  KSRC Initial Fission Points"
HSRC_BANNER         = "C  HSRC Shannon Entropy Mesh"
RAW_CELL_BANNER     = "C  Cell Cards (raw text mode)"
RAW_SURF_BANNER     = "C  Surface Cards (raw text mode)"
RAW_MAT_BANNER      = "C  Materials (raw text mode)"
RAW_SDEF_BANNER     = "C  Source Definition (raw text mode)"

def is_generator_banner(line: str) -> bool: ...
```

`is_generator_banner` 必须精确匹配以下 11 个词汇（`re.IGNORECASE` + 锚定 `$`，防误伤用户注释如 `C  Cell Cards are useful`）：

```
C  Cell Cards: <N> cells defined
C  Surface Cards: <N> surfaces defined
C  Cell Cards (raw text mode)
C  Surface Cards (raw text mode)
C  Materials (raw text mode)
C  Source Definition (raw text mode)
C  ===== Data Cards =====
C  TR Transformations
C  Tallies
C  KSRC Initial Fission Points
C  HSRC Shannon Entropy Mesh
```

**拦截点：`parsers/sections.py:split_sections` 的 C 注释分支（动工前 207-216 行）**，在分支最前面加：

```python
if re.match(r'^C\s', line, re.IGNORECASE):
    if is_generator_banner(line):
        i += 1
        continue   # 节头不入任何 phase 的原始收集
    # ……原有 C 行吸收逻辑保持不变……
```

这是**单一拦截点**：节头既不进 `cell_lines`（→ 不污染 cell.comment）、也不进 `surf_lines`（→ 不进 deck.surfaces）、也不进 `data_lines`（→ 不进 other_cards）。

**注意**：不得改为"所有 C 行都丢弃"——用户手写文件的 C 注释（vendor 样例 prob41c/avr13 的栅元块注释、材料 C 注释 `C  fuel`）必须继续按原语义吸收（栅元 pending_c / 材料 comment）。

#### 方案 B（辅）：生成器头规范化（防御 + 单点）

- `inp_generator.py` 的 1060/1065/1072/1077/1082/1090/1098/1106、522、634、643 各节头改为调用 `banners.py` 的常量/构造器，**禁止内联字符串**。
- 语义零变化：节头文本、动态计数（`{len(cells)}`、`{len(surf_lines)}`）原样保留。
- 若解析器将来漏认某头，R1 立刻 RED → 这是词汇冻结的兜底网。

### 1.3 对 R1 全局的修复效果预期

- kitchen-sink 2102→2266、prob41c 1097→1247 的逐代膨胀**完全停止**：deck.surfaces 不再含曲面头（计数无法复利）、other_cards 不再含 Data/Tallies 头（无重放累积）、cell.comment 不再被栅元头污染。
- 与 F-E（§5）合并后，长行 `&` 续行污染也消除 → R1 在 **minimal / 3 样例**上字节稳定。
- **2026-08-12 修订**：kitchen-sink 的 R1 字节稳定**不等价于仅修 F-A**——它还依赖多源 SDEF 字段重组漂移与分布注释丢失的消除（F#5/F#6，P1 范围）。本轮 F-A 修复后 kitchen-sink **膨胀停止**（`test_r1_output_does_not_grow_unboundedly` 保持绿），但 `test_r1_fixed_point_kitchen_sink` 仍保持红（表示漂移非膨胀），移入 P1 验收（§0.5.5）。

### 1.4 验收标准（红→绿，2026-08-12 修订：分本轮 / P1 两栏）

#### 本轮验收（范围 = minimal + 3 样例）

| 测试 | 文件 |
| :--- | :--- |
| `test_r1_fixed_point_minimal_deck` | tests/integration/test_roundtrip.py |
| `test_r1_fixed_point_sample_prob41c` | tests/integration/test_roundtrip.py |
| `test_r1_fixed_point_sample_avr13` | tests/integration/test_roundtrip.py |
| `test_smoke_r1_fixed_point[*]`（3 参：prob41c/avr13/inp24） | tests/integration/test_sample_smoke.py |

回归：`test_r1_output_does_not_grow_unboundedly`（kitchen-sink 增长探针，基线已绿）**保持绿**，不得回归。

#### P1 F#5/F#6 验收（2026-08-12 移出本轮；重构 `_generate_multi_source` 后转绿）

| 测试 | 文件 |
| :--- | :--- |
| `test_r1_fixed_point_kitchen_sink` | tests/integration/test_roundtrip.py |
| `test_r4_kitchen_sink_full_roundtrip` | tests/integration/test_roundtrip.py |

本轮允许保持红（复合根因清单见 §0.5.5）。

---

## 2. F-B（致命）—— validate_deck 与 CellRow 判别联合不兼容

### 2.1 根因

`app/generator/validator.py:validate_all`（91-99 签名 `cells: list[CellData]`）直接访问 `cell.surface_expr` / `cell.material` / `cell.density` / `cell.number`；而 `deck.cells` 是 `list[CellRow]`（`kind`/`cell`/`text` 嵌套，models.py:59）。`validate_deck`（249-259）把 `deck.cells` 原样传给 `validate_all` → 对含栅元 deck 抛 `AttributeError: 'CellRow' object has no attribute 'surface_expr'`。

生产 `/api/validate-inp` 走文本层 `parsers/validator.validate_inp_text`（对 3 样例全过），**不受影响**；`validate_deck` 是 DeckData 层辅助路径，是 CellRow 模型演进后遗留未同步。

### 2.2 修复方案

**只改 `validate_deck`（DeckData 层入口），不改 `validate_all` 签名**（`validate_all` 仍被表单层以 `list[CellData]` 调用）：

```python
def _unwrap_cells(cells):
    """CellRow 判别联合 → 仅保留 kind=='cell' 的 CellData；raw 条件行不参与校验。"""
    return [row.cell for row in cells if getattr(row, "kind", "cell") == "cell"]

def validate_deck(deck: DeckData) -> list[str]:
    return validate_all(
        ...,
        cells=_unwrap_cells(deck.cells),
        ...,
    )
```

注意 `validate_all` 后续 `numbers = [c.number for c in cells]` 与交叉引用循环都基于 CellData 字段，解包后天然可用。`kind=="raw"` 行（`#ifdef/#else/#endif`）跳过，符合"raw 行不参与校验"语义。

### 2.3 验收标准（红→绿）

`test_smoke_validate_deck_does_not_crash[*]`（SAMPLES 参数化；inp24 磁盘缺失 skipif 不算失败）。

---

## 3. F-C（严重）—— 多粒子计数卡 F4:N,P 解析后丢失

### 3.1 根因

生成器 `inp_generator.py:528` 输出 `particles_str = ",".join(...)` → `*F4:N,P`；解析器 `parsers/core.py:730-738` 的 `parse_f_tally` 正则 `^F(\d+):([NPEHAS])$` 只认**单粒子**设计符，`F4:N,P` 四个模式全不匹配 → 返回 None → `parse_data_cards:1007-1009` 把裸 F 卡丢进 `other_cards` → 多粒子计数在 round-trip 后消失。

`parse_data_cards:998` 的入口门 `^[*+]?F\d+:` 已能放行 `F4:N,P`（`F4:` 命中），所以问题**只在 parse_f_tally 内部正则**，无需新增外层门。

### 3.2 修复方案（解析器侧）

`parsers/core.py:parse_f_tally`：

1. 设计符单字符类 `([NPEHAS])` 扩为逗号列表 `([NPEHAS](?:,[NPEHAS])*)`，作用于全部 6 处：FIP/FIR/FIC 两处（721-723）、`F(n):p`（730）、`F(n)p`（732）、`F(n)[XYZ]:p`（734）、`F(n)[XYZ]p`（736）。
2. 匹配后按逗号展开粒子，在 `existing` 合并分支（766-771）与新建分支（772-779）**两处**都改为：
   ```python
   particles_to_add = [p.strip().lower() for p in designator.split(",") if p.strip()]
   ```
   - 合并分支：对列表逐个去重 append（保持现有"逐粒子去重"语义）。
   - 新建分支：`particles=particles_to_add`。
3. FIP/FIR/FIC 分支的 `designator = img_m.group(3).upper()` 同样做逗号展开。

生成器侧（528）**不改**——逗号形式是既有的输出契约，也是 R2 测试的意图（`test_r2_tally_multi_particle_parse_supported` 断言 round-trip 后 tally 集合相等）。

### 3.3 验收标准（红→绿）

- `test_r2_tally_multi_particle_parse_supported` → 绿。
- 回归：`test_r2_tally_single_particle_survive` 保持绿（单粒子不受影响）。

---

## 4. F-D（严重）—— 材料 options 丢失

### 4.1 根因

生成器 `inp_generator.py:204-208` 把 `MaterialData.options`（如 `nlib=.66c`）追加到**材料卡末行尾部**。当末行是 raw 条件行（kitchen-sink M1 的 rows 末尾是 `#endif`）时，产出 `#endif  nlib=.66c`。解析器 `parse_data_cards:1201-1220` 把 `#endif...` 整行作为 raw 行归入材料 → `_parse_material`（349-398）只在 **M 头行**解析 options → options 文本被锁死在 raw 行里，`mat.options` 为空。

### 4.2 修复方案（生成器侧，主）

**options 移到 M 头行**（符合 MCNP 规范：材料选项与 `M{n}` 同行），并删除末行尾追加：

`inp_generator.py:_generate_materials`（194-208）：

```python
# 首行: M{n}，options 与 M 头同行（MCNP 规范）
card = f"M{mat.number}"
_opts = (getattr(mat, 'options', '') or '').strip()
if _opts:
    card += "  " + _opts
# 续行不变：raw 条件行原样独立成行；核素行 "\n     {zaid}  {frac}"
for row in mat.rows: ...
# 删除原 204-208 的末行尾追加
```

解析器**无需改动**：`_parse_material` 已能从 M 头行识别 `nlib=.66c`（364-368 的 `=` 分支）。`parse_data_cards:933` 的 `^M\d+$` 门按 `parts[0]`（`M1`）匹配，`M1  nlib=.66c` 照常命中；`C  {mat.comment}` 前置行照常作为 M 卡 comment 吸收。

### 4.3 验收标准（红→绿）

- `test_r2_material_options_survive` → 绿。
- 回归：`test_r2_material_rows_and_mt_survive` 保持绿（raw 条件行仍逐行保留）。

---

## 5. F-E（严重）—— `_wrap_long_lines` 的 `&` 续行符污染字段

### 5.1 根因

`inp_generator.py:_wrap_long_lines`（999-1025）对超 80 列行在列 30-78 的最后空格处拆分，第一段末尾加 `&`，续行以 **5 空格缩进**。回解析时 `parsers/lines.py:normalize_lines` 的续行合并有两条路径：

- **5 空格缩进合并**（122-129）：**不剥离**当前行的尾 `&`，且 `continue` 短路 → 后面的 `&` 续行分支（131-140，会剥 `&`）永远轮不到 → `&` 残留在字段中段（如 `-1 2 & 3 -4`）；
- 段末无续行的尾 `&`（行尾落在空行/节边界前）在 flush 时也原样保留（148-151）→ 字段尾 `&`（如 `0 0 1 &`）。

污染 `surface_expr` / `vec` 等字段。R2 已在测试层用 `_strip_wrap_artifact`（test_roundtrip.py:90-95）对**尾 `&`**做容差，但**中段 `&` 容差不掉**，且 R1 字节不动点要求字段干净。

### 5.2 修复方案（解析器侧，主）

`parsers/lines.py:normalize_lines`：

1. **5 空格缩进合并分支（122-129）**：合并前剥离当前行的尾 `&` 续行符——`cur_no_dollar` 若以 `&` 结尾，先 `rstrip('&')` 再合并（保留 `$` 注释提取逻辑不变）。
2. **flush 收尾**（空行分支 92-96、循环结束 149-151）：flush 当前行时同样剥离尾 `&`（`&` 在 MCNP 里语义就是续行符，行尾 `&` 剥掉安全；注意先 `strip_comment` 再剥，避免误伤 `$` 注释内的字面 `&`）。

生成器 `_wrap_long_lines` 不动（拆分逻辑是确定性纯函数，同一输入同一拆分点）；修复后 `parse(generate(d))` 得到无 `&` 的干净字段，二次生成重拆位置与一次完全一致 → 字节稳定。

### 5.3 验收标准

- **本轮（2026-08-12 修订）**：3 样例（prob41c/avr13/inp24）R1 稳定依赖 F-A + F-E 合并修复（超 80 列长行拆分不再携带 `&` 污染 surface_expr/vec）；`test_r1_output_does_not_grow_unboundedly` 保持绿。
- `test_r2_cell_content_fields_survive` / `test_r2_single_source_fields_survive` 保持绿（测试内 `_strip_wrap_artifact` 成为无害空操作，**不删该容差**）。
- **P1 F#5/F#6（移出本轮）**：`test_r1_fixed_point_kitchen_sink` / `test_r4_kitchen_sink_full_roundtrip` 的转绿依赖 F-A+F-E+F-C 全套（本轮修）**+ 多源 SDEF 字段重组漂移与分布注释丢失**（P1 修，见 §0.5.5），本轮保持红。

---

## 6. 已 pin 潜在缺陷（不阻塞 M1.4，P1 顺手处理——仍属缺陷修复，非重构）

> 这三项在契约里给处理方向。pin 断言是"标记缺陷存在"；修复后**更新断言为正确行为**（红转绿，非降级）。
> **2026-08-12 修订：三项已确认不阻塞本轮门禁。** 翻新 pin 属可选（后端顺手做允许，§7 范围内）；不翻新则 pin 断言保持现状，不计入终态 6 红。若翻新，必须写死正确行为断言（严禁 pass/skip/弱断言）。

### 6.1 F-F —— ksrc_points 数值坐标崩溃（inp_generator.py:628-632）

- 根因：`(pt.get("x") or "").strip()` 对 `json.loads` 保持的数值（int/float）调用 `.strip()` 崩溃；且 `0` 是 falsy，`0 or ""` 会把合法坐标 0 吞成空串。
- 方向：None 感知 + 显式 str 强转：
  ```python
  val = pt.get("x"); x = "" if val is None else str(val).strip()
  ```
  三坐标同改；保留 `if x and y and z` 过滤。**不碰**同函数内 622 行的 `import json as _json`（F#3，P1 范围）。
- 验收：`tests/unit/test_generator_phys.py::test_ksrc_numeric_coords_raises` 由 `pytest.raises((AttributeError, TypeError))` **翻转为"数值坐标产出合法 KSRC 行"**（参照同文件 `test_ksrc_points_emitted_with_continuation` 的断言形式，字符串坐标用例保持绿）。

### 6.2 F-G —— parse_sdef_simple 的 EFF 裸值静默丢弃（parsers/core.py:440-443 / 401-423）

- 根因：`EFF` 在 `_KNOWN_KEYS` 但 `_apply_sdef_param` 无 EFF 分支 → 裸值 `EFF=2` 静默丢弃；带续值只保留续值（`EFF=2 5` → `sdef_extra="5"`，前缀丢）。
- 方向：`_apply_sdef_param` 加 `elif key == "EFF": src.sdef_extra = (src.sdef_extra + " EFF=" + val).strip()`；续值分支（489-490）改为保留前缀 `EFF=2 5` → `sdef_extra="EFF=2 5"`。EFF 走 `sdef_extra` 保存即可在生成端原样重发。
- 验收：`tests/parser/test_core_sdef.py` 两例 pin 翻转为 `sdef_extra == "EFF=2"` 与 `sdef_extra == "EFF=2 5"`。

### 6.3 F-H —— `_is_cell_line` 小写 m 材料引用不识别（parsers/sections.py:78）

- 根因：`second.startswith("M")` 大小写敏感；`parse_cells` 能识别小写 `m1`，`_is_cell_line` 不能 → 分节把 `3 m1 -1.0 -3` 误判为曲面行。
- 方向：改大小写不敏感（如 `second[0] in "Mm" and second[1:].isdigit()`）。顺带检查 `inp_generator.py:36` `mat.startswith("M")` 与 generator 端同类判断，保持一致（此属缺陷邻接，勿扩面）。
- 验收：`tests/parser/test_sections.py::test_is_cell_line_lowercase_m_reference_not_detected` 翻转为 `is True`。

---

## 7. 缺陷修复 vs P1 重构边界（防止后端越界）

**本次契约范围内（可以动）**：

| 文件 | 改动 |
| :--- | :--- |
| `app/generator/banners.py` | **新增**（节头词汇单点） |
| `app/generator/parsers/sections.py` | split_sections 拦截节头（F-A）；`_is_cell_line` 大小写（F-H） |
| `app/generator/parsers/core.py` | parse_f_tally 多粒子正则（F-C）；`_apply_sdef_param` EFF（F-G） |
| `app/generator/parsers/lines.py` | normalize_lines 剥 `&`（F-E） |
| `app/generator/inp_generator.py` | 节头改调 banners（F-A/B）；options 上移 M 头行（F-D）；ksrc 坐标强转（F-F） |
| `app/generator/validator.py` | validate_deck 解包 CellRow（F-B） |

**P1 重构范围（本次一律不碰，禁止顺手做）**：

- `inp_generator.py:98` 函数内 `from pymcnp import inp`（F#7，P1 提到模块顶部）
- `inp_generator.py:622/660` 函数内 `import json as _json`（F#3）——**F-F 修复只改 628-632，不得动 622**
- `parsers/core.py:821-822/1014-1016`、`parsers/__init__.py:138-140` 函数内 `import sys` + `[E0DBG]` print（F#3）
- `inp_generator.py:247-281 vs 283-301` 单源 SDEF 两分支合并（F#4）
- `inp_generator.py:366-510` 多源重构拆 5 函数 + `SDEF_FIELD_SPECS` 表（F#5/F#6）
- raw_overrides 守卫收敛为 `_apply_raw_override(...)`（F#1；含 1145 `raw_tally` 门控语义，P1 必须保留）
- **任何对 `deck.rawOverrides` 行为的修改**（前端只写 4 key + 空串=无覆盖 + 1145 门控，禁止凭直觉改）

判定规则：**本次改动若触及 §7 P1 清单里的函数体结构（不是行号），即越界。**

**2026-08-12 修订（边界不变）**：`_generate_multi_source`（366-510 行）本轮**不碰**——多源 SDEF 漂移（`POS=F D1`→`X=F Y=D1`、`TME=D6`→`TME=0.0`、`SI1 V`→`SI1 L`、分布注释丢失）属 **P1 F#5/F#6 范围**，不并入本轮修复。**后端不得因 kitchen-sink R1/R4 保持红而越界改动多源逻辑**；本轮只允许 F-A~F-E 按 §1-5 落点施工。

---

## 8. 行号漂移重锚定清单（修复完成后必须执行）

**2026-08-12 修订**：后端施工后 `app/` 已回滚到干净基线，重新施工会再次移动行号，本清单仍适用（先修缺陷、跑绿、再重锚定；顺序不可颠倒）。kitchen-sink 相关测试（`test_r1_fixed_point_kitchen_sink` / `test_r4_kitchen_sink_full_roundtrip`）保留在 **P1 验收**（§0.5.5）；§8.3 的 `def _generate_multi_source` 锚点供 P1 重锚定，本轮不因 kitchen-sink 红而动多源逻辑。

F-A~F-H 会移动 `inp_generator.py` 与 `parsers/` 的行号。以下文档/锚点在修复完成后**必须用 Grep 重锚定**：

### 8.1 `app/UI_ARCHITECTURE.md`

| 章节 | 需重锚定锚点 | 受影响原因 |
| :--- | :--- | :--- |
| §5（213-237 行） | raw_overrides 守卫 1058/1070/1096/1104/1120/1128/1136/1157；不一致变体 1145；`_wrap_long_lines（行 999）` | F-A 改 1058-1082、F-E 改 999-1025 |
| §7.1（278-292 行） | F#1 守卫 1058/1070/1096/1104/1120/1128/1136/1157 + 1145；F#3 622+660；F#4 247-281/283-301；F#5 366-510；F#6 375-394/425-440/447-453/477-480；F#7 98 | 98 之前无改动不漂移；其余全部漂移 |
| §7.2（294-305 行） | core.py 822/1014/1016；`parsers/__init__.py` 139/140；api_server.py 609/610 | F-C 改 core.py 721-746 → 822/1014/1016 后移；`__init__.py`/api_server 本次不漂移 |

### 8.2 `app/generator/review_findings.json`

| 锚点行 | 受影响原因 |
| :--- | :--- |
| 78（`_generate_basic` pymcnp import） | 不漂移（78 < 194） |
| 182（`_generate_single_source` DRY） | 不漂移 |
| 535/567（`_generate_kcode`/`_generate_en_cards` 函数内 import） | F-D 改 194-208 → 后移 |
| 622/660（函数内 `import json as _json`） | F-D + F-F（628-640）双重后移 |
| 837（raw override key 判错处） | F-D/F-C/F-F 累积后移 |

### 8.3 重锚定方法

`grep -n` 定位以下符号名（不靠记忆行号）：`Cell Cards: `、`Surface Cards: `、`Data Cards =====`、`def _wrap_long_lines`、`def _generate_kcode`、`import json as _json`、`def _generate_multi_source`、`def _generate_single_source`、`from pymcnp import inp`、`raw_tally`、`def parse_f_tally`、`E0DBG`。P1 开工前先跑 `tests/integration/test_tech_debt.py` 与 `tests/integration/test_api_contract.py` 确认 F#* pin 基线未因本次修复被误触发（F#3/F#7 仍应红，F#1/F#5/F#6 仍应绿）。

---

## 9. 后端施工最易踩的坑（预警）

1. **F-A 别过度收口**：把 `split_sections` 的 C 分支改成"所有 C 行都丢"会毁掉用户/样例的 C 注释保留（prob41c/avr13 的栅元块注释、材料 `C  fuel` 注释），导致 `test_r2_material_rows_and_mt_survive` 等已绿用例回归。只精确匹配 §1.2 的 11 个节头词汇。
2. **F-A 别漏 `C  Tallies` 和 raw-mode 头**：只修三个主头（Cell/Surface/Data）而漏 `C  Tallies`，kitchen-sink 的 other_cards 仍逐代 +1，R1 依旧红。
3. **F-B 别改 `validate_all` 签名**：表单层（api_server 走 DeckData 收集后调 validate_all）传 `list[CellData]`，签名改动会破坏生产路径；只在 `validate_deck` 解包。
4. **F-C 别加外层门**：`parse_data_cards:998` 已放行 `F4:N,P`；在 `parse_f_tally` 内改正则即可。若另加门易造成 F 卡双重处理（既进 tally_defs 又进 other_cards）。
5. **F-D 注意 raw 条件行**：options 上移 M 头行后，`#ifdef/#else/#endif` 仍必须各自独立成行（normalize_lines 对 `#` 行断点保留），不得并入 M 头行，否则条件行语义破坏。
6. **F-E 只剥续行位置的 `&`**：先 `strip_comment` 再剥尾 `&`，避免误伤 `$` 注释里的字面 `&`；不要动 `_wrap_long_lines` 的拆分逻辑（确定性纯函数，改了反而破坏二次生成同拆分点）。
7. **已 pin 断言的处理是"翻新"不是"降级"**：F-F/F-G/F-H 的 pin 用例改断言后必须写死**正确行为**断言（如数值坐标产出合法 KSRC、`sdef_extra == "EFF=2 5"`、`_is_cell_line("3 m1 -1.0 -3") is True`），严禁改成 `pass`/`skip`/弱断言。
8. **每步跑全量**：一次改多项后一起跑全量会难以定位回归；按 F-A→F-B→F-C→F-D→F-E 顺序，每步 `python -m pytest tests/ -v` 且只允许该步关联断言由红转绿。
9. **kitchen-sink R1/R4 红是预期的（2026-08-12 裁决）**：本轮终态允许 6 红（4 技术债 + 2 kitchen-sink）。看到 `test_r1_fixed_point_kitchen_sink` / `test_r4_kitchen_sink_full_roundtrip` 红**不要**去动 `_generate_multi_source`（P1 F#5/F#6 范围，§7 越界判定）。以 §0.5.3 的 245/6 为准，不以"全绿"为准。

---

## 10. 交付检查清单（2026-08-12 修订：终态 245 绿 / 6 红）

- [ ] F-A：`test_r1_fixed_point_minimal_deck` + `test_r1_fixed_point_sample_{prob41c,avr13}` + `test_smoke_r1_fixed_point[*]`（3 参）全绿；`test_r1_output_does_not_grow_unboundedly` 不回归
- [ ] F-A（P1，本轮允许红）：`test_r1_fixed_point_kitchen_sink`、`test_r4_kitchen_sink_full_roundtrip` —— **不属于本轮验收**（§0.5.5）
- [ ] F-B：`test_smoke_validate_deck_does_not_crash[*]` 绿
- [ ] F-C：`test_r2_tally_multi_particle_parse_supported` 绿，`test_r2_tally_single_particle_survive` 不回归
- [ ] F-D：`test_r2_material_options_survive` 绿，`test_r2_material_rows_and_mt_survive` 不回归
- [ ] F-E：3 样例 R1 稳定依赖 F-A+F-E；`test_r2_cell_content_fields_survive` / `test_r2_single_source_fields_survive` 不回归
- [ ] F-F/F-G/F-H：**可选翻新**（非本轮门禁）；若翻新，断言写死正确行为，严禁 pass/skip/弱断言
- [ ] 全量 `python -m pytest tests/ -v`：既有 129 生成器单测 + 73 解析器单测 + 7 契约闸门零回归；终态 **245 绿 / 6 红**（6 红 = 4 技术债 F#3/F#7 + 2 kitchen-sink R1/R4）
- [ ] 按 §8 重锚定 UI_ARCHITECTURE.md 与 review_findings.json 的行号
- [ ] 未触碰 §7 P1 重构范围任何一项（含 `_generate_multi_source` 366-510，本轮不碰）
