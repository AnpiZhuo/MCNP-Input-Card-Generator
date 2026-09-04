# inputcard-mcp 全量覆盖 — 字段映射缺口与深接口设计

> 用 codebase-design 视角审查现有 `inputcard-mcp` 后得到的结论：**生成器已全量支持所有 INP 数据段**，无需为每段造一个浅工具；正确做法是把"后端语义段"作为 AI 工作单位，用一个深工具 `patch_section` 覆盖全部段。

## 一、前端 deck JSON 与后端 DeckData 不同构（关键）

**前端 `DeckData` 顶层有（含 UI 中间态）**：

`basic / surfaces / tr_cards / cells / materials / sources / tallies / tally / grids / adv / sourceMode / sdefFields / sdefRawText / sourceTemplate / distributions / sswFields / ssrFields / kcodeFields / ksrcPoints / rawOverrides / textMode / universeComments`

**`deck_from_json`（`gui/backend/api_server.py`）只读这些**：

| 后端段 | 读入来源 | 子字段（`_*_from_*` helper） |
| :--- | :--- | :--- |
| `basic` | `data["basic"]` | title / mode_n·p·e·h·he·d·t·a / nps / ctme / act / print_pr / phys_fis |
| `surfaces` | `data["surfaces"]` | 原始文本 |
| `tr_cards` | `data["tr_cards"]` | 原始文本 |
| `cells` | `data["cells"]` | CellRow 判别联合（kind==raw→text / else cell 嵌套） |
| `materials` | `data["materials"]` | number / rows / comment / formula / options / mt_card |
| `sources` | `data["sources"]` | number / par / erg / pos_* / wgt / cel / dir_ / prob / tme / vec / axs / rad / ext / sur / nrm / tr / ccc / ara / rate / sdef_extra |
| `tally` | `data["tally"]` | tallies / fmesh_defs / ptrac / e_min·e_max·e_bins·e_log·e_custom*·e_cards_text / t0_*·t_cards_text / cut_*（n/p/e/h/he/d/t/a）|
| `adv` | `data["adv"]` | other_cards / phys_* / source_mode / sdef_* / kcode_* / ksrc_points / hsrc_* / sdef_distributions / ssw_* / ssr_* |
| `universe_comments` | `data["universeComments"]` | {u_str: text} |

## 二、缺口：前端顶层字段 `deck_from_json` 不读

以下前端顶层字段**不被 `deck_from_json` 读取**（改成 JSON 顶层再 `generate_document` 会被**丢弃**）：

- `tallies`（应改 `tally.tallies`）
- `grids`（前端 UI 网格权威；后端从 `tally` 的 e_/t_ 字段生成）
- `sourceMode`、`sdefFields`、`sdefRawText`、`distributions`（应改 `adv.source_mode / sdef_* / sdef_distributions`）
- `sswFields`、`ssrFields`（应改 `adv.ssw_* / ssr_*`）
- `kcodeFields`、`ksrcPoints`（应改 `adv.kcode_* / ksrc_points`）
- `rawOverrides`、`textMode`、`sourceTemplate`（UI 中间态，不属 INP 内容）

## 三、正确抽象：AI 操作"后端语义段"，而非前端顶层

**后端生成器真正的输入段**（= AI 可写段）：

```
basic / surfaces / tr_cards / cells / materials / sources / tally / advanced(adv)
```

这 8 类正好对应 `deck_from_json` 的 8 个读取入口。

### 深接口：`patch_section`

```
patch_section(inp, section, data) -> inp
  section ∈ { basic, surfaces, tr_cards, cells, materials, sources, tally, advanced }
  data    = 该段的**后端语义**结构化值（snake_case，与 deck_from_json 读取口径一致）
```
内部：`deck_from_json` 读入当前 deck → **替换/合并**该段 → `generate_inp_from_deck`。一个工具覆盖全部段。

### 可写 / 不可写判定
- ✅ 可写（进 INP）：上述 8 个语义段。
- ⛔ 不可写（纯前端 UI 中间态，`patch_section` 应拒绝）：`textMode` / `sourceTemplate` 编号 / `grids` / `rawOverrides` / 标签页开合。

## 四、落地前必做（深模块的测试面）

1. **`deck_from_json` 字段对齐**：核对 8 类对前端顶层 camelCase 中间态的映射（`sourceMode`→`adv.source_mode`、`tallies`→`tally.tallies`、`sswFields`→`adv.ssw_*` 等），保证"前端读回 → AI 改 → generate → parse"不丢语义。
2. **roundtrip 测试（红→绿）**：`后端语义 deck → DeckData → generate → parse → 后端语义 deck`，逐字段断言不丢。这是全量覆盖能否真正可用的唯一可靠判定（"interface 即测试面"）。
3. 再实现 `patch_section` 的 section 归并 + 写接口。

## 五、保留的深工具（全量 = 6 个）
| 工具 | 作用 |
| :--- | :--- |
| `read_document` / `generate_document` / `validate_document` | 文档级读/写/校验 |
| `list_section(inp, section)` | 收敛 list_cells/list_materials/list_sources → 一个按段查 |
| `patch_section(inp, section, data)` | **核心**：全量写一段 |
| `add_shape` | 几何便捷（保留，内部走 cells/surfaces） |
