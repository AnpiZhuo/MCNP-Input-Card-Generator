# PTRAC 粒子径迹可视化契约（v2，按用户讨论定稿）

> 依据：用户指令（2026-08-15 深夜，「像 FMESH 一样把 PTRAC 也做适配」，显示方案经用户逐项敲定）+ `PROJECT_MEMORY.md` + meshtal-visualization.md 范式 + PyMCNP `ptrac` 包（Header.py/History.py + `examples/example_02.ptrac` 1.2MB 真实文件，开发调试用）。
> 交付版本：**1.7.1 不变**（用户定，不升 1.8.0）。

## 0. 目标（用户敲定）

在 MCNP 输入卡里开启 PTRAC（计数页表单）→ 跑出 ASCII 粒子径迹文件 → 「输出」页解析 →
独立「3D 径迹」窗口：几何外壳 + 每个源粒子的径迹折线，**按粒子类型三色 + 能量深浅渐变**，
可勾选粒子类型、调透明度、高亮单径迹、按密度抽样。

## 1. PTRAC 文件格式（实核 example_02.ptrac + PyMCNP ptrac 包）

- 头：① `   -1`；② code(8)/version(25)/code_date(9)/run_datetime(18)；③ 标题(80)；
  ④ V 行（问题常数，可能多行）；⑤ N 行（各类事件变量个数）；⑥ L 行（**变量 ID 表**：
  `(粒子类型, 变量ID)` 对，定义事件行每列含义——能量/粒子类型语义以此为准）。
- 历史：`      NPS      1000`（恰 2 个整数字段）→ 事件两行一组：
  字段行（首字段=事件类型 1000/2000族/3000/4000/5000/9000；第二字段=节点粒子类型；
  后续列按 L 表取能量等）+ 位置行 `x y z`。
- **能量提取**：按 L 表定位能量列（不同 WRITE/粒子类型列布局不同）；取不到记 0。

## 2. 后端（app/ptrac/，模块顶仅 stdlib，照 app/meshtal/ 范式）

| 模块 | 职责 |
| :--- | :--- |
| `ptrac_parser.py` | 纯 stdlib：`parse_ptrac(path, max_tracks=500, max_points=200000)` → `{header:{code,title}, tracks:[{nps, particle, points:[[x,y,z,type,energy],…]}], world_box, stats:{nps,events,points,truncated,particles:{n,p,e}}, truncated}`；L 表驱动能量/粒子类型提取（参考 PyMCNP ptrac/header 子包 + History.py 的字段映射）；超上限截断标 truncated；第 1 行非 "-1" 或行数<8 → PTRACFormatError |
| `_ptrac_worker.py` | 子进程入口（stdin JSON → stdout JSON 信封），模块顶只 stdlib，照 `_meshtal_worker` |

## 3. 端点

`POST /api/ptrac-detect`：`{outputDir}` → `{files:[{path,name,size,mtime}], outputDir}`（照 meshtal-detect，
扫描 `^ptrac(\..*)?$` 大小写不敏感、按 mtime 降序；目录缺失/空 → ok files:[]）。

`POST /api/ptrac-parse`：`{path, maxTracks?=500, maxPoints?=200000}` →
`{status, header, tracks, worldBox, stats, truncated}`；坏文件/缺失 → 友好中文 hint（照 F4）。
api.yaml 同步（30 端点）；漂移闸门双向一致；`mcnp_bridge.py` 加 `--ptrac-worker` 分派；
spec `_hidden`/`_keep_dirs` 补 ptrac（照 meshtal）。

## 4. 前端

| 模块 | 职责 |
| :--- | :--- |
| `gui/src/ptrac/trackColors.ts` | 纯函数：粒子类型基色 **n=蓝(#3b82f6)/p=红(#ef4444)/e=黄(#eab308)**、其余灰；`trackShade(color, energy01)` 能量归一→亮度深浅（低能浅、高能深，HSL lightness 插值）；legend 常量 |
| `gui/src/ptrac/decimateTracks.ts` | 纯函数：均匀抽稀保持首尾 + **密度抽样**（sampleTracks(tracks, step)：每 step 条取 1，固定按 nps 序号稳定抽样） |
| `gui/src/ptrac/PtracWindow.tsx` | 独立窗宿主（照 ResultWindow）：外壳 STL（fetchPreview3dStl，无模型则无）+ 每条径迹 LineSegments（**顶点色=类型色×能量深浅**）+ 归一化 offset（alignWorld 复用）+ OrbitControls；右 300px 面板：标题「🧭 3D 径迹 — PTRAC」、关闭、统计行（**径迹(粒子)条数/事件/点数/截断提示**，事件数≫径迹数时提示「事件≠粒子」并建议 WRITE=SOURCE）、**粒子类型三勾选（中子/光子/电子）**、**能量深浅图例**、**径迹透明度滑杆**、**密度抽样滑杆（1/1、1/10、1/100、1/1000、1/10000）**、**单径迹高亮（NPS 数字输入，空=全部）**、外壳开关、关闭按钮 |
| `gui/src/utils/api.ts` | `ptracParse(path, maxTracks?, maxPoints?)` + 类型 |
| `gui/src/utils/windows.ts` | 桥 key `mcnp_win_ptrac`（openPtracWindow/readPtracData） |
| `gui/src/ptrac/openPtracWindow.ts` | 组装桥（stlData/cells/ptracPath/maxTracks/maxPoints）→ openPtracWindow；非 Tauri fallback 提示 #/ptrac；**默认 maxTracks=100000 / maxPoints=200000**（WRITE=SOURCE 每粒子 1 点、10 万粒子可全量显示——单点径迹合并为一个 Points 云一次 draw call；多事件径迹由 maxPoints 抽稀兜底） |
| `main.rs` | `create_or_focus(&app, "ptrac", "3D 径迹", 1300.0, 820.0)` + `open_ptrac_window` |
| `App.tsx` | `#/ptrac` 路由 |
| `OutputTab.tsx` | 「粒子径迹（PTRAC）」小节：**「解析 PTRAC」自动探测**（照「解析 MESHTAL」：ptrac-detect 扫输出目录 → 解析 → 开窗）+「选择 ptrac 文件」手动 +「解析并查看 3D 径迹」；错误 hint；浏览器 fallback |

## 4.5 计数标签页 PTRAC 表单（用户敲定口径）

- TallyTab 加「粒子径迹（PTRAC）」小节：**勾选启用** → 生成 `PTRAC ...` 卡。
- **常用 7 项（平铺不折叠）**：FILE（ASC/BIN，默认 ASC）、WRITE（ALL/SOURCE/EVENT，默认 ALL）、
  MAX（数字，**留空=不输出**，MCNP 默认 100——MAX=-1 会使本机 MCNP 写完 1 个事件即终止，实测踩坑）、
  TYPE（N/P/E 多选，可空）、NPS（数字，可空）、**CELL（数字，可空）**、
  **SURFACE（数字，可空）**。
- **高级折叠**：VALUE、EVENT。
- 不做表单：CONIC/TALLY/FILTER/BUFFER/MEPH（用户手写「其他卡」，解析器 round-trip 保留）。
- 状态：`deck.tally.ptrac?: {enabled, file, write, max, types, nps, cell, surface, value, event}`（加性字段，JSON key 与后端生成/解析同步）；fmeshState.ts 同款 state 模块或并入 TallySettings——实现者取最少改动路径并测 round-trip。

## 5. 验收（测试先行，先红后绿）

- pytest：`tests/unit/test_ptrac_parser.py`（fixture tests/fixtures/ptrac_sample.txt：
  2 历史/7 点/类型/位置/world_box/max 截断/坏文件/缺文件；L 表能量提取：用 example_02 子集断言
  能量列提取与粒子类型）+ `tests/integration/test_ptrac_api.py`（HTTP 信封 + 坏路径 hint）。
- vitest：`gui/test/ptrac/` trackColors（三色映射/深浅渐变区间）+ decimateTracks（抽稀/抽样步长/保持首尾）+
  PtracWindow SSR 兜底 + windowRouteConsistency 含 "ptrac"。
- 全量门禁：pytest + vitest + tsc/build EXIT 0（colorize 128³ 计时已知 flaky）。

## 6. 非目标

- 二进制 PTRAC（FILE=BIN）不解析（提示用 FILE=ASC）；能量谱/统计图；时间轴动画；
  起终点小球标记（用户未选）。
