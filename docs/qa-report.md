# 格阵 fill 阶段1（数据层）独立验收质量报告

- **审查人**：测试（独立审查方，非开发自报）
- **日期**：2026-08-24
- **审查方式**：只读代码核验 + 实际跑测试（独立复跑，不依赖开发自报）
- **验收依据**：`C:\Users\13789\.claude\plans\fill-cell-lat-0-u-fill-cell-u-u-u-u-u-3-fluffy-lampson.md` 阶段1「验收」节
- **审查范围**：`app/lattice.py`（新）、`app/models.py`、`app/generator/parsers/core.py`、`app/generator/inp_generator.py`、`gui/backend/api_server.py`、`gui/src/utils/cellBridge.ts`（新）、前端四处桥接（GeometryTab/CellEditDialog/DeckContext/quickCell）、相关测试文件

---

## 一、验收项清单（对照计划阶段1「验收」节）

| # | 验收项 | 结果 | 独立证据 |
| :-- | :--- | :--- | :--- |
| 1 | pytest（`tests/parser tests/integration tests/unit`）全绿，开发自报 632/0 | ✅ 通过 | 独立复跑：**632 passed / 0 failed**（22.72s），与开发自报一致。`tests/` 仅含这三个子目录（无根级测试文件），即全量 |
| 2 | R1 字节不动点：prob41c / 17×17 / BEAVRS / inp24 / hex_lattice `parse→gen→parse→gen` | ✅ 通过 | 闸门 `test_r1_lattice_17x17_fixed_point`、`test_r1_lattice_prob41c_fixed_point` 通过；独立脚本复跑 5 夹具全部字节稳定（逐代 len 不变） |
| 3 | kitchen_sink R4 不回退 | ✅ 通过 | `test_r4_kitchen_sink_full_roundtrip` 通过；独立复跑 `g1 == g2`（len 2135 → 2135），cell1「待建格」fill_grid 空值往返不丢 |
| 4 | 单值 fill 回归（`u=1 fill=0 lat=1`）不破坏 | ✅ 通过 | `test_parse_vol_pwt_u_fill_lat_trcl_tmp` 通过；独立核验 `fill='0'`、`fill_grid=''`，走原循环零回归 |
| 5 | 代码抽查（详见下节） | ✅ 通过 | 逐行核对 + `git diff` 比对 |
| 6 | 前端 wire：`cellBridge.ts` 存在 + `fill_grid` 透传不丢 | ✅ 通过 | `gui/test/cellBridge.test.ts` 5/5；全量 vitest **412 passed / 0 failed**（57 文件）；`tsc --noEmit` EXIT 0；localStorage 整表序列化（`JSON.stringify({version, deck, ...})`）无白名单，`fill_grid` 随 cell 原样落盘/恢复 |

### 代码抽查细节（验收项 5）

| 检查点 | 结果 | 证据 |
| :--- | :--- | :--- |
| `format_fill_cards` ① raw 优先回放（非 cells） | ✅ | `app/lattice.py:234` `if fg.raw:` 分支优先于 cells 分支；独立验证 inp24 生成输出保留 `17r` 简写 |
| `format_fill_cards` ② 回放 raw 时剥离前导 `len(fg.range_)` 个范围 token | ✅ | `app/lattice.py:238-240` `tokens = tokens[len(fg.range_):]`，防范围续行重复 |
| `CellData` 加 `fill_grid: str = ""` | ✅ | `app/models.py:56` |
| `core.py` 未动 `_expand_repeat` | ✅ | `git diff` 显示 `_expand_repeat` 原样，仅在其后新增 `_consume_fill_tokens`（core.py:385-397） |
| `core.py` FILL= / FILL 两分支收束 | ✅ | core.py:275-280、319-325 均调 `_consume_fill_tokens` → `parse_fill_tokens` 收 FILL 后全部 token + `idx=len(parts); break` |
| `inp_generator.py` FILL 置末 | ✅ | `_generate_cells`：格阵分支 `lattice_lines[0]` 追加在 `other_params` 之后（inp_generator.py:91-94）；目检 17×17 生成输出 `... LAT=1 FILL=0:16 0:16 0:0` FILL 居末 |
| `inp_generator.py` 续行独立追加不加 `&` | ✅ | inp_generator.py:117-119 `for _extra in lattice_lines[1:]: lines.append(_extra)`，独立条目行、5 空格缩进、≤80 列（目检 0 行超 80） |
| 脏 JSON 优雅回退 | ✅ | `FillGrid.from_json` 对非 JSON/非对象返回 None → 单值路径输出 `FILL={fill}`（test_lattice.py:133-137 + 生成器 83-84） |
| 格阵 cell 注释移尾（不吞条目） | ✅ | inp_generator.py:96-121：格阵 cell 注释放 `     $ comment` 尾行，`strip_comment` 先切 `$` 不污染条目 |

---

## 二、问题列表

### ❌ 致命（阻塞上线）
**无。**

### ⚠️ 严重（建议修复后上线）
**无。**

### 💡 建议（3 项，均不阻塞阶段1，仅供参考/阶段2交接）

1. **`parse_fill_entries` nR 重复展开无上限（`app/lattice.py:125-152`）**：`nR` 先全量展开、再在 `parse_fill_tokens` 按 dims 截断（179-182 行）。恶意/畸形 INP 如 `fill=0:0 0:0 0:0 1 999999999r` 会先分配约 10 亿个 `FillEntry` 再截断，造成内存膨胀。桌面本地应用（用户自提交文件）风险低，不构成远程攻击面。建议在 `parse_fill_entries` 内传 `limit`（= dims 乘积）并在达到后停止扩展。

2. **`CellData` 字段顺序与计划描述不一致（`app/models.py:54-56`）**：实际为 `comment → render → fill_grid`，计划写「render 之后、comment 之前」（即 `render → fill_grid → comment`）。全库 CellData 均关键字构造（core.py:345 / api_server.py:420），无功能影响，纯文档级偏差。

3. **条目流总长 ≠ 范围乘积时静默补 0/截断，无警告信号（`app/lattice.py:179-182`）**：`raw` 保留原始 token 流，R1 不受影响；但计划提及「补 0 + 警告」，当前解析器不暴露不匹配信号。阶段2 画布需自行检测（比对 raw 条目 token 数与 `product(dims)`），否则画布展示的补 0 格位可能与源卡语义不一致且无提示。

---

## 三、测试执行结果汇总

| 门禁 | 命令 | 结果 |
| :--- | :--- | :--- |
| pytest（parser/integration/unit） | `python -m pytest tests/parser tests/integration tests/unit -q` | **632 passed / 0 failed**（22.72s） |
| 格阵 R1 闸门 | `pytest tests/integration/test_roundtrip.py -k "r1_lattice or r4 or r1_fixed"` | 7 passed（含 2 条 `test_r1_lattice_*`） |
| 全量 vitest | `npx vitest run` | **412 passed / 0 failed**（57 文件，5.58s） |
| cellBridge 单测 | `npx vitest run test/cellBridge.test.ts` | 5 passed |
| tsc | `npx tsc --noEmit` | EXIT 0 |
| 独立 R1 五夹具复跑 | 内联脚本 | prob41c / 17×17 / BEAVRS / inp24 / hex_lattice 全字节稳定 |
| 独立语义核验 | 内联脚本 | surface_expr 干净（5 夹具 0 污染）/ 17r 简写保留 / 单值 fill fill_grid 空 / 翻译单填充 kind=translated / kitchen_sink R4 g1==g2 |

---

## 四、整体评估结论

**阶段1（数据层）验收通过。**

- 全部 6 项验收标准达成，独立复跑与开发自报一致（pytest 632/0、vitest 412/0、tsc EXIT 0）。
- R1 字节不动点五夹具全稳、kitchen_sink R4 不回退、单值 fill 回归无破坏、前端 wire 全链路透传不丢。
- 无致命、无严重问题；3 项建议（nR 展开上限 / 字段顺序文档 / 画布不匹配信号）不阻塞上线，其中第 1 项建议在阶段2 派活时一并处理。
- 建议放行，可进入阶段2（UI 画布）派活。

**归属说明**：如后续有致命问题需打回，本报告问题清单（建议项）1 归后端（`app/lattice.py`）、2 归后端（`app/models.py`）、3 归阶段2 前端（画布提示）——阶段1 无致命问题，无需打回。
