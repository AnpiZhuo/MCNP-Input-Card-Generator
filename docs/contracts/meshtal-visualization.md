# 网格计数（FMESH/TMESH）3D 体积可视化契约

> 契约人：架构师 | 施工方：后端 + 前端（并行）| 分支：自 `experiment/geouned` 拉出（命名 `feat/meshtal-volume`）
> 日期：2026-08-14 | 状态：**契约已锁定（本次为契约产出，不施工）**
> 依据：项目经理直接指令（对标 VISED 网格计数 3D 体积可视化）+ `PROJECT_MEMORY.md` + 现有 3D 预览链路 + PyMCNP `meshtal` 解析器 + 现有 FM 乘子五步走先例
> 目标：FMESH/TMESH 卡结构化 + MESHTAL 文件解析 + 光线追踪体积渲染（Three.js/WebGL2 DataTexture3D）+ 独立「3D 结果」窗口；零新依赖、343 pytest 基线 / 19 vitest 基线不破、api.yaml 漂移闸门 25→28 双向同步
> **交付版本目标：1.7.0**（用户 2026-08-14 指定，非 1.6.5；网格计数可视化是下个大功能按 1.7.0 发布；打包时按 docs/手动打包方法.md 步骤 1 三处+README 同步到 1.7.0，其中 Cargo.toml v1.6.4 曾漏改需特别注意）
> 行号说明：本契约行号为 2026-08-14 工作树 Grep 锚定值，施工以每次 Grep 重锚定为准（见 §16）。
>
> **修订记录（2026-08-14 · QA F1/F2/F6 契约滞后修复，仅文档不改码；详见 docs/qa-report-fmesh-c810.md §3）**
> - **F6 字段名同步**：§5.1 字段名 `eints`/`t_ints` → `emints`/`tmints`（对齐 models.py:225-227、api_server.py:373-375、fmesh_parser.py EMINTS/TMINTS 容错）；§4.7.1 幽灵文字 `EINTS`/`TINTS` → `EMINTS`/`TMINTS`；§5.1 补 `axs`/`vec`/`tr` 字段（对齐 models.py:230-232）。
> - **F2 1INTS 文案**：删除「1INTS n 语法」支持声明（§4.7.1:286、§5.3:335）——v1 结构化解析仅支持多区间 `IMESH= v1 v2 ... IINTS= n1 n2 ...`，`1INTS n` 简写不吸收（`_KEYS`/`KEY_TO_FIELD` 无 `1INTS` 键），用户须改写为多值形式；C810 原文是否收录 1INTS 待人工核验。
> - **F1 OUT 初步对齐**：§4.7.1 OUT 由 `[f|q|n]`（TMESH 输出单位语义）初步对齐实现九选项（COL 默认/CF/COLSC/CFSC/IJ/IK/JK/NONE/XDMF，FMESH 输出格式语义，fmeshState.ts:145-155）；XDMF 是否 MCNP6.2+ 待 C810 3-118 人工核验（qa-report-fmesh-c810 §3 F1）。
> - **窗口 label 建议值同步（2026-08-15，P0 修复单值统一，仅文档不改码）**：§1.2 项 6 / §2.1 数据流 / §4.7 ResultWindow 行 / §10 步 4 / §17 检查清单 中窗口 label 建议值 `volume3d` → `volume`（对齐 App.tsx WindowRouter 路由 `volume` 与调试 hash `#/volume`）；command 名 `open_volume3d_window`、windows.ts 桥 key、窗口标题「3D 结果」、尺寸 1300×820 均不变。

---

## 0. 纪律（施工方必读，违反即打回）

1. **零新运行时依赖**：numpy / pymcnp / three 均已就位（numpy 现用于 `stl_cross_section.py`，pymcnp 在 `inp_generator.py` 模块顶 import，three 在 `gui/`）。**禁止** `pip install` / `npm install`（vitest 仅 `gui/` devDependency，已批准）。
2. **不碰 MCNP 生成/解析既有 pin 行为**：`app/generator/`、`app/generator/parsers/` 只允许 §6 规定的最小增量（sections.py DATA_PATTERNS 补 `^TMESH`、core.py 入口门加 FMESH/TMESH 结构化分支），其余既有解析/生成行为逐字节不变；既有 `tests/parser/*` pin 全部保持。
3. **契约漂移闸门双向一致**：新增 `/api/meshtal-detect`、`/api/meshtal-parse`、`/api/meshtal-texture` 必须同时写入 `gui/backend/api_server.py` handlers dict（:501-527）与 `docs/contracts/api.yaml`，`tests/integration/test_api_contract.py` 双向一致绿（**25 → 28**）。
4. **测试铁律不变**：测试不 `import gui.backend.api_server`（模块级 pyvista/FreeCAD 探测污染）；不 `import FreeCAD`；纯逻辑测试走 `app/meshtal/` 各 seam（stdlib / numpy，无 FreeCAD）。
5. **不污染 preview-3d 性能契约**：`/api/preview-3d` 响应结构（`stl_files`/`stl_data`/`freecad`/`count`）不变、冷/热路径零新增延迟；**不改 Preview3D.tsx 主组件**（体积窗口独立场景，仅复用纯模块 `computeCameraParams`/`renderGate`/`cellMaterial`/`STLLoader`）。
6. **体积窗口关闭不清 preview-3d 的 STL 会话**：`ResultWindow` 关闭只 `close_window`，**不调** `clearStlSession()`（STL 会话由主窗口 3D 预览生命周期管理）。
7. **禁止反向降级断言**（改断言/删断言/加 skip 骗绿一律打回；依赖外部环境/大文件的测试仅允许整文件条件 skip，不算绿数）。
8. **测试先行纪律**：tester 先建红基线（见 §9.4），后端施工转绿，每步全量 pytest 343 不破 + vitest 19 不破。
9. **大文件解析走子进程 worker**（照 `_freecad_csg_worker.py` 模式：stdin JSON → stdout JSON），避免阻塞 5001 线程池。
10. 施工完成按 §16 重锚定文档并向 PM 汇报 commit 索引。

---

## 1. 背景与现状（锚定点）

### 1.1 现状管线
- **FMESH 卡当前落 other_cards 兜底**：`sections.py` DATA_PATTERNS（:180）已认 `^FMESH`（节首直出进 data_lines）；`core.py` parse_data_cards 入口门（:941 起 if/elif 链）无 FMESH 分支 → 走 :1284 `first in _KNOWN_OTHER_CARDS` 分支 append `raw_line` 进 `other_cards`（:1286）。**TMESH 未在 DATA_PATTERNS / `_KNOWN_OTHER_CARDS` 中**（:890 表无 TMESH），节首直出会误分曲面/栅元段 → 需补 `^TMESH`。
- **生成器**：`_generate_tallies`（inp_generator.py:633-674）只输出 Fn / FMn；`_generate_other_cards`（:1111-1120）在数据卡段最末尾回放 `other_cards` → FMESH/TMESH 文本随 other_cards 回放（round-trip 不丢但非结构化）。
- **MESHTAL 解析**：PyMCNP `D:\MCNP\PyMCNP\src\pymcnp\Meshtal.py`（`Meshtal.from_mcnp`，:50）+ `meshtal/Header.py`（bins_x/y/z/energy/time 均为 String 原始边界文本，:147-163）+ `meshtal/Tally.py`（每行 x/y/z/energy/time/result/error 全 String，:23）。**header 正则严格，拒收即抛 `MeshtalError(SYNTAX_FILE)`** → 需自研轻量兜底。
- **MESHTAL 文件格式事实**（vendor `valid_38.meshtal` 已核）：头部 `Mesh Tally Number N` + `粒子 mesh tally.` + `Tally bin boundaries:`（`X/Y/Z direction:` 每轴边界边数组、`Energy bin boundaries:`、可选 `Time bin boundaries:`）+ 表头 `X Y Z Result Rel Error` + 数据行（x/y/z 为**栅元中心**，Result/RelError 为数值）。**数据行列序 = `Energy Time X Y Z Result RelError`（energy/time 在前，可为空=单 bin）**；遍历序 z 最快 → y → x。
- **3D 预览**：`Preview3D.tsx` `initScene`（:95）→ `loadStlMeshes`（:257，几何归一化 translate(-center) 先于 computeBoundingBox，:296-305）→ `computeCameraParams`（`gui/src/three/cameraParams.ts`）→ `renderGate`（按需渲染）+ `cellMaterial`（默认 opaque）+ `TickGrid`。独立窗口经 `windows.ts`（localStorage 桥 KEY_PREVIEW3D + `openPreview3D`/`readPreview3DData`）+ `main.rs` `open_preview3d_window`（:74）→ `Preview3DWindow.tsx`。
- **API 信封**：`api_server.py` `_ok`（:539）/`_err`（:546），handlers dict :501-527（25 端点），`api.yaml` 25 端点（:34-891）。
- **worker 模式**：`freecad_preview.py` `_run_freecad_script`（:390-431）`subprocess.run([python_exe, worker_script], input=json, timeout=120)` → 解析 stdout JSON → `status:"ok"` 检查。`_freecad_csg_worker.py` 模块顶只 import stdlib + FreeCAD（vtk 惰性）。

### 1.2 功能需求（用户已敲定共识，契约全量覆盖）
对标 VISED 网格计数 3D 体积可视化：
1. **数据来源**：外部跑 MCNP 为主 + 内部跑自动探测 MESHTAL 文件，用户点「解析」读取。**FMESH 和 TMESH 都进 v1**（渲染仅支持 GEOM=xyz 矩形网格；cyl 解析但标记不支持降级提示）。
2. **FMESH 表单**：计数标签页新增「网格计数（FMESH/TMESH）」小节，结构化词条（网格类型/ORIGIN/三向 IMESH+INTS + 能量/时间边界 + MAT/OUT），每个输入框幽灵文字注明关键字作用。DeckContext 加字段。
3. **渲染**：光线追踪体积渲染（烟雾云雾质感，Three.js/WebGL2 光线步进 shader，DataTexture3D）。
4. **分辨率**：128³ 流畅默认、256³ 供用户选；超预算**弹窗让用户选**（流畅=自动降采样 / 精细=保原精度）。预算阈值：GPU 驻留 ≤256MB、128³ 默认。
5. **配色**：天气图式蓝→黄→橙→红阶梯渐变；**色阶下限=显示阈值（低于不显示）**；生成时自适应数据范围 + 用户可手改上下限。
6. **窗口**：独立「3D 结果」窗口（label 建议 `volume`），复用当前 deck 几何（半透明模型）+ 彩色体积层。
7. **控制**：透明度、能量区间选择、时间轴动画（播放/暂停/拖动）、几何外壳开关、3D 视角。
8. **几何外壳交互**：像 3D 预览一样可交互——可勾选显示哪些栅元 + 栅元内粒子是否显示（复用 Preview3D 的勾选逻辑）。
9. **降采样算法**：均值（box-average），保总量准确。
10. **模块化**：后端 `app/meshtal/`（meshtal_parser / volume_builder / colormap / downsample_plan + FMESH 结构化生成/解析/序列化链路），前端 `gui/src/volume/`（volumeShader / VolumeRenderer / FMeshForm / VolumeControlPanel / ResultWindow）。

---

## 2. 数据来源与 MESHTAL 规范化结构

### 2.1 数据流
```
外部 MCNP 运行 或 内部 /api/run-mcnp → output_dir 产生 meshtal*
用户点「解析」
  → POST /api/meshtal-detect（扫描 output_dir 找 meshtal* / MSHT*）
  → POST /api/meshtal-parse（子进程 worker 解析 → 网格元数据 + tally 列表 + 数据范围统计）
  → 前端分辨率决策（128³ 默认 / 256³ 可选 / 超预算弹窗）
  → 打开 volume 窗口
  → POST /api/meshtal-texture（子进程 worker 取当前 (energy,time) 帧 → 降采样标量帧 base64）
  → 前端 colorize → RGBA → DataTexture3D 上传（当前帧 texSubImage3D 复用）
```

### 2.2 规范化结构（`app/meshtal/meshtal_parser.py` 产出）
**以 MESHTAL 自带 bin 边界为准，不信表单**。栅格维度/ORIGIN/bin 边界全部来自 meshtal 头部 `X/Y/Z direction` / `Energy/Time bin boundaries`。

```python
@dataclass
class MeshTally:
    number: int              # Mesh Tally Number（与 FMESHn/TMESHn 卡号对应）
    particle: str            # "n" / "p" / "e"（header "neutron/photon/electron mesh tally."）
    geom: str                # "xyz"（v1 仅支持矩形；cyl 解析后标记 unsupported_geom=True）
    bins_x: list[float]      # X 方向边界边数组（长度 ni+1）
    bins_y: list[float]
    bins_z: list[float]
    bins_energy: list[float] # 能量边界（长度 energyBins+1；无能量分箱时 [0.0, 1e36]）
    bins_time: list[float]   # 时间边界（长度 timeBins+1；无时间分箱时 []）
    data: dict               # {(e, t): np.ndarray(dtype=float64, shape=(ni,nj,nk))}
    error: dict              # {(e, t): np.ndarray(dtype=float64, shape=(ni,nj,nk))}（相对误差）
    scalar_range: tuple      # (dataMin, dataMax)（全 tally 全帧）

@dataclass
class MeshtalFile:
    path: str
    mtime: float
    code: str                # header code（"mcnp"）
    histories: float         # 归一化历史数
    tallies: list[MeshTally]
    warnings: list[str]
```

- **索引规则**：数据行 (energy,time,x,y,z,result,error) → 按 header 顺序映射到稠密数组 `data[(e,t)][i][j][k]`。x 索引按 x 中心落入的 bin 确定（中心值 = (edge[k]+edge[k+1])/2，最近邻匹配，容差 `1e-9*span`）。
- **解析策略**：先 `pymcnp.meshtal.Meshtal.from_mcnp`（惰性 import），成功 → 用其 header bins + tally 行构建稠密数组；抛 `MeshtalError`/任何异常 → 轻量兜底解析（§3.4）。**两条路径产出同一 `MeshtalFile`**。

---

## 3. API 端点（新增 3 个，25 → 28）

响应信封一律 `_ok` / `_err`（§0.3）。POST body JSON。大文件解析/纹理提取走子进程 worker（§4.5）。

**错误信封 `hint` 字段（F4）**：`_err(msg, status=500, hint="")` 增可选 `hint`（友好中文提示）；`hint` 非空时响应 `{"status":"error","message":...,"traceback":...,"hint":"..."}`，空则省略。**对既有 25 端点加性兼容**（既有调用不传 hint → 响应字段不变，漂移闸门不感知）。三 meshtal 端点 guard 必须带 hint。

### 3.1 `POST /api/meshtal-detect`（operationId `meshtalDetect`，tags `meshtal`）
- **入参**：`{"outputDir": "D:/..."}`（缺省回退 `D:/MCNP/new/claude`）。
- **出参（ok）**：
```json
{"status":"ok",
 "files":[
   {"path":"D:/.../meshtal","name":"meshtal","size":123456,"mtime":"2026-08-14T10:00:00Z"}
 ],
 "outputDir":"D:/..."}
```
- **扫描规则**：`os.scandir(outputDir)` 匹配文件名 `re.match(r'(?i)^(meshtal|MSHT)')`（含 `meshtal`、`meshtal1`、`MSHTAL` 等）；按 mtime 降序；目录缺失/空 → `{"status":"ok","files":[]}`。
- **守卫**：outputDir 非法 → `_err`。

### 3.2 `POST /api/meshtal-parse`（operationId `meshtalParse`，tags `meshtal`）
- **入参**：
```json
{"path":"D:/.../meshtal",
 "modelBox":{"min":[-B,-B,-B],"max":[B,B,B]}}   // 可选：deck 几何包围盒（A2/A1.2 比对用）。
 // 备选来源：请求也可带 {"surfaces":"...","cells":[...],"tr_cards":"..."}，handler 用 preview-3d
 // bound 同源口径（_compute_bound_from_surfaces）算 [-B,B]³；两者皆缺 → match:null（跳过比对）
```
- **出参（ok）**：
```json
{"status":"ok",
 "file":{"path":"...","size":123456,"mtime":"..."},
 "header":{"code":"mcnp","version":"6","histories":10000000},
 "grid_bounds":{"min":[-100,-100,-150],"max":[100,100,-50]},   // bin 边界算出的网格世界包围盒（A1.2）
 "match":{"matched":true,"overlapFraction":0.98,"centerOffsetFrac":0.01,
          "reason":"ok","message":""},                          // 缺 modelBox → null（A1.2）
 "tallies":[
   {"number":4,"particle":"n","geom":"xyz","unsupportedGeom":false,
    "dims":{"ni":10,"nj":10,"nk":100,"energyBins":1,"timeBins":1,"nVoxels":10000},
    "binEdges":{"x":[-100,...,100],"y":[-100,...,100],"z":[-150,...,-50],
                "energy":[0.0,1e36],"time":[]},
    "range":{"min":0.0,"max":3.5e7,"count":10000}},
   "..."
 ],
 "warnings":[]}
```
- **语义**：供前端「弹窗分辨率决策」（§4.4）与 tally/能量/时间选择器。只返回元数据，**不传输稠密数组**（大文件走 worker，内存/耗时与传输解耦）。`grid_bounds` 由 worker mode=parse 产出；`match` 在 api_server 进程内用纯函数 `deck_match.check_match` 比对（§4.6A / §12 A1.2）。
- **缓存**：命中 `MeshtalParseCache`（path+mtime 指纹）时免重解析（§4.4）。
- **守卫**：路径不存在/非 meshtal → `_err("不是有效的 meshtal 文件", hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")`。

### 3.3 `POST /api/meshtal-texture`（operationId `meshtalTexture`，tags `meshtal`）
- **入参**：
```json
{"path":"D:/.../meshtal",
 "tallyNumber":4,
 "energyBin":0, "timeBin":0,
 "resolution":128,        // 目标每轴上限：128 默认 / 256 显式
 "normalize":"adaptive"}   // 默认 adaptive；预留 "log"（对数映射，v1 可不做）
```
- **出参（ok）**：
```json
{"status":"ok",
 "frame":{"resolution":[128,128,128],
   "worldBox":{"min":[-100,-100,-150],"max":[100,100,-50]},
   "binIndices":{"energy":0,"time":0},
   "scalarRange":{"min":...,"max":...},
   "dataBase64":"...",        // Uint8 标量帧，长度 = resolution[0]*[1]*[2]，值域 [0,255] 归一化
   "bytes":2097152,"nVoxels":2097152,
   "downsampled":true,"avgFactor":[1,1,1],
   "particle":"n","tallyNumber":4,
   "scalarMin":..., "scalarMax":...}}
```
- **语义**：返回**当前帧标量**（非 RGBA，见 §4.3「前端 CPU 上色」裁决）。`resolution` 为每轴上限；若 native 更小则保 native（`avgFactor`=1）。降采样均值（box-average）保总量（§4.2）。`worldBox` 永远来自 meshtal bin 边界（降采样不改世界坐标）。
- **上传预算**：worker 把解析/降采样/归一化全在子进程完成，只把 ≤ (256³=16MiB) 的标量帧 base64 回传。
- **守卫**：tallyNumber 不存在 / energyBin/timeBin 越界 → `_err(..., hint="请重新选择计数与能量/时间范围")`；native 单轴 > 4096 → `_err("网格过密无法解析", hint="网格过密无法解析，请确认该 meshtal 文件对应的 FMESH/TMESH 网格在合理范围内")`（防御，见 §13）。

### 3.4 轻量兜底解析（`meshtal_parser` 内部）
pymcnp 严格 header 正则（`Meshtal._REGEX`）拒收时，轻量解析：
1. 按 `Mesh Tally Number` 分隔各 tally 段；
2. 行匹配 `^\s*(X|Y|Z) direction:\s*(.+)$` / `Energy bin boundaries:\s*(.+)` / `Time bin boundaries:\s*(.+)` → 按空白 split 转 float 边界；
3. 数据行按列数判别：`X Y Z Result RelError`（3 坐标，无能量/时间列=单 bin）/ `Energy Time X Y Z Result RelError`（5 索引，**energy/time 在前**，可为空=单 bin）；表头行（含 `Rel Error`）跳过；
4. 构建 `MeshTally`。
- 兜底路径必须通过 `tests/fixtures/minimal_meshtal.txt` 手写样例（非 pymcnp 产出格式）验证。

---

## 4. 模块 seam（后端 `app/meshtal/` + 前端 `gui/src/volume/`）

### 4.1 `app/meshtal/meshtal_parser.py`（新，stdlib + 惰性 pymcnp）
| 接口（小） | 实现（深） | 测试面 |
| :--- | :--- | :--- |
| `parse_meshtal(text: str) -> MeshtalFile` | pymcnp 优先 + 轻量兜底；header bins → 边界数组；逐 tally 按 `Energy Time X Y Z Result RelError` 行序解析（**energy/time 在前，可为空=单 bin**）映射稠密数组 (e,t)→(i,j,k)；错误隔离 per-tally | pytest 单测（vendor fixture + 手写最小样例） |
| `parse_meshtal_file(path: str) -> MeshtalFile` | 读文件 + mtime + 转 parse_meshtal | 同上 |

### 4.2 `app/meshtal/volume_builder.py`（新，numpy 已就位）
| 接口 | 实现 | 测试面 |
| :--- | :--- | :--- |
| `build_frame(mf: MeshtalFile, tally_number: int, energy_bin: int, time_bin: int, resolution: int, budget_bytes: int) -> Frame` | 取 (e,t) 稠密 → `downsample_plan` 算 avgFactor → box-average 降采样（均值，保总量）→ 标量 [0,255] 归一化 → Frame | pytest 单测（总量守恒断言 + 切片选择） |
| `Frame`（dataclass） | `{resolution, world_box:{min,max}, scalar: np.ndarray(uint8), scalar_range:(min,max), avg_factor, downsampled}` | — |

- **box-average（保总量）**：每输出体素 = 输入块内原值均值；因输入块体积 == 输出体素体积（几何等比），块和不变 → 全量守恒。归一化在降采样**之后**做（对降采样后数组取 min/max），避免"对归一化值再求均值"失真。
- **切片语义**：`energy_bin`/`time_bin` 为 bin 索引；无能量分箱（bins_energy==[0,1e36] 或空）时 energyBins=1 恒可切片 0。

### 4.3 `app/meshtal/colormap.py`（新，纯 stdlib）
| 接口 | 实现 | 测试面 |
| :--- | :--- | :--- |
| `WEATHER_STOPS: list[tuple[float, tuple[int,int,int,int]]]` | 蓝→黄→橙→红阶梯渐变锚点（见 §4.3.1 定锚） | pytest 单测 |
| `weather_lut(n: int = 256) -> list[tuple[int,int,int,int]]` | 锚点间线性插值 → RGBA LUT | 同上 + 跨语言 golden 对照 |
| `map_value(v: float, lo: float, hi: float, lut) -> tuple[int,int,int,int]` | v≤lo→alpha 0（显示阈值=色阶下限）；线性映射 | 同上 |

**4.3.1 配色锚点（单一事实来源，python 与 TS 必须一致）**
```
0.00  #3B4CC0 (蓝)    0.33  #00E5FF (青)    0.55  #FDE047 (黄)
0.75  #F97316 (橙)    1.00  #DC2626 (红)
alpha：v < displayMin（=色阶下限）→ 0；否则 255
```
- **色阶下限=显示阈值（低于不显示）**：`displayMin` 是用户可改的「下限」；默认 = 自适应 `scalarRange.min`。
- **跨语言防漂移**：python `weather_lut()` 与 TS `colorize.weatherLut()` 各自实现；`tests/unit/test_meshtal_colormap.py::golden_lut` 把 python 256 项 LUT 的 sha256 写成固定 golden，`gui/test/volume/colorize.test.ts::lut_matches_golden` 断言 TS 端 sha256 相等。锚点改动 → 两侧同时改 + golden 重算。

### 4.4 `app/meshtal/downsample_plan.py`（新，纯 stdlib）+ `app/meshtal/meshtal_cache.py`（新，stdlib）
```python
# downsample_plan.py
GPU_BUDGET_BYTES = 256 * 1024 * 1024   # GPU 驻留预算 ≤256MB（当前帧 RGBA + 外壳几何）
DEFAULT_RESOLUTION = 128               # 128³ 默认（流畅）
MAX_RESOLUTION = 256                   # 256³ 供用户显式选
def estimate_texture_bytes(dims) -> int        # nx*ny*nz*4（RGBA）
def plan_downsample(native, target_res, budget_bytes=GPU_BUDGET_BYTES) -> Plan
    # Plan = {out_dims, avg_factor, fits_budget, over_budget: bool}
    # 每轴 factor = max(1, ceil(native/out)); out = 每轴 min(target_res, native)
    # fits_budget = estimate(out) <= budget
def decide_resolution(native, requested, budget_bytes) -> ResolutionDecision
    # requested 128 默认 / 256 显式；fits → no popup；over → popup 素材（§12 F3）
```
```python
# meshtal_cache.py —— worker 侧稠密数组缓存（stdlib pickle，numpy 序列化）
class MeshtalParseCache:
    def fingerprint(self, path, mtime) -> str          # sha256(path + mtime)
    def get(self, fp, tally_number) -> dict | None     # {"data":..., "scalar_range":...}
    def put(self, fp, tally_number, arrays) -> None    # pickle 落 tempdir，LRU 按磁盘量
    def evict(self) -> None                            # 超容量 512MB 逐最旧
```
- **命中语义**：`/api/meshtal-texture` 重复取不同 (energy,time) 帧时复用已解析稠密数组，免整文件重解析（大文件关键）。`meshtal-parse` 元数据也缓存（防弹窗流程重复解析）。

### 4.5 `app/meshtal/_meshtal_worker.py`（新，照 `_freecad_csg_worker.py` 模式）
- **协议**：stdin JSON → stdout JSON（`{"status":"ok", ...}` / `{"status":"error","message":...}`），失败时 stdout 末尾打错误。
- **mode="parse"**：读文件 → `parse_meshtal_file` → 只回传元数据 + range + warnings（稠密数组落 cache）。
- **mode="texture"**：cache 命中取稠密 → `build_frame` → base64 标量帧。
- **模块顶只 import stdlib**（numpy 惰性按需），pymcnp 惰性 import（在 `parse_meshtal` 内 try）。AST 断言防模块顶重 import（照 `test_preview3d_worker.py` 风格）。
- **worker 定位**：`app/meshtal/_meshtal_worker.py`，api_server 用 `sys.executable`（打包 sidecar 即 python.exe）spawn，`timeout=120`。
- **接线**：api_server 新增薄 handler（照 `_handle_preview_3d` 的 worker 调用模式），缓存注入到 `_meshtal_worker` 的 stdout 结果（worker 自身读写 cache，避免跨进程共享内存）。

### 4.6 FMESH 结构化链路（后端 `app/meshtal/fmesh_parser.py` + models + generator + api_server）
照 FM 乘子五步走先例（见 §6）。

### 4.6A deck↔meshtal 匹配检测（`app/meshtal/deck_match.py`，新，纯 stdlib，pytest 可测 seam）
| 接口 | 实现 | 测试面 |
| :--- | :--- | :--- |
| `@dataclass AABB`（`min`/`max`/`span()`/`volume()`） | 轴对齐包围盒 | pytest |
| `overlap_fraction(a: AABB, b: AABB) -> float` | 交集体积 / min(vol_a, vol_b) | pytest |
| `center_offset_frac(a: AABB, b: AABB) -> float` | 中心距 / max(model span) | pytest |
| `check_match(grid_box, model_box, *, min_overlap=0.2, max_center_offset=0.5) -> MatchReport` | `matched` / `reason` | pytest（容差边界） |

`@dataclass MatchReport`：`{matched: bool, overlap_fraction: float, center_offset_frac: float, reason: str, message: str}`；`reason ∈ {"ok","overlap_too_small","offset_too_large"}`。
- **口径**：`grid_box` = meshtal bin 边界算出（ORIGIN..上限，worker mode=parse 产出 `grid_bounds`）；`model_box` = preview-3d bound 同源口径（`_compute_bound_from_surfaces` 的 `[-B,B]³`）。
- **比对机制（后端做，可测，不增加端点）**：`_handle_meshtal_parse` 请求带 `modelBox`（或 `surfaces`/`cells`/`tr_cards` 由 handler 算）→ `check_match` → 响应 `match`；两者皆缺 → `match:null`。worker 只回 `grid_bounds`，比对在 api_server 进程内（纯函数）。
- **不静默错位**：`match.matched==false` → 前端友好横幅「网格数据与当前模型几何可能不匹配（网格范围 X vs 模型范围 Y），可能显示错位」。
- **边界**：`deck_match.py` 不 import freecad_preview（model_box 由调用方算好传入），保持最纯可测。

### 4.7 前端 `gui/src/volume/`（新文件夹）
| 模块 | 接口（小） | 实现（深） | 测试面 |
| :--- | :--- | :--- | :--- |
| `volumeShader.ts` | `RAY_MARCH_VERTEX`/`RAY_MARCH_FRAGMENT`（const 字符串）；`buildRayMarchMaterial(opts:{texture:THREE.DataTexture3D, opacity:number}): THREE.ShaderMaterial`；`isWebGL2(): boolean` | GLSL 前向光线步进（front-to-back 累积，采样 sampler3D RGBA，线性过滤）；ray 由相机逆投影/Box3 求交计算 | vitest 快照 + `isWebGL2` 判定 |
| `VolumeRenderer.ts` | `createVolumeRenderer(canvas, opts:{stlData, cellViews, frame, worldBox, energyOptions, timeOptions, onError})` 返回 `{setOpacity, setShellVisible, setFrame(frame), setColorizeRange, play, pause, seek(timeIdx), dispose, markDirty}` | 场景组装：外壳 STL 网格（复用 STLLoader + cellMaterial + renderGate + computeCameraParams）+ 体积盒（ShaderMaterial + DataTexture3D）+ OrbitControls + 归一化对齐（§7）；DataTexture3D 一次创建，`texSubImage3D` 复用上传当前帧 | vitest（纯状态/类型）+ `#/volume` e2e 冒烟 |
| `colorize.ts` | `weatherLut(): Uint8Array`；`colorizeScalar(scalar:Uint8Array, lut:Uint8Array, range:{min,max}, displayMin:number): Uint8Array`（RGBA） | 天气图 LUT（与 python colormap golden 一致）；v < displayMin → alpha 0；线性映射 | vitest |
| `alignWorld.ts` | `worldBoxFromEdges(edges:{x:number[],y:number[],z:number[]}) -> {min:[n,n,n],max:[n,n,n]}`；`unionBoxes(boxes) -> Box3`；`translateToCenter(geometries, box) -> offset:[n,n,n]`；`applyOffset(vec, offset)` | 单一归一化偏移（§7 对齐机制核心） | vitest（对齐不变量） |
| `downsampleRequest.ts` | `decideResolution(nativeDims, requested, budgetBytes) -> {resolution, popup:boolean, recommended:'smooth'\|'precise', popupCopy}` | 镜像 `downsample_plan.py`（预算/弹窗决策纯逻辑）；popupCopy =「要更流畅，还是要更精细？」（F3） | vitest |
| `fmeshState.ts` | `FmeshRow` 类型 + `fmeshToCardText(row) -> string` + `cardTextToFmesh(text) -> FmeshRow \| null` + `buildFmeshPayload(rows) -> tally.fmesh` | FMESH/TMESH 卡体 ↔ 结构化（镜像 fmesh_parser.py） | vitest |
| `workflow.ts` | `workflowStep(state) -> {title, steps[]}`；`noFileMessage(hasFiles) -> {text, action}` | 空态三步引导（F1.1）+ 没找到文件可操作提示（F1.2）纯逻辑 | vitest |
| `ColorLegend.tsx` | 色条图例（单位标签 + 上下限数值）；导出 `legendTicks(min,max,n)` 纯函数 | F5.2 图例；刻度纯函数 | vitest |
| `FMeshForm.tsx` | 受控表单（§4.7.1） | 计数标签页「网格计数」小节 | tsc + vitest（状态） |
| `VolumeControlPanel.tsx` | 面板（透明度/能量/时间轴/外壳/视角） | 纯展示 + 回调 | tsc |
| `ResultWindow.tsx` | Tauri `volume` 窗口宿主（读桥 + 挂 VolumeRenderer + 关闭只 close_window） | 独立场景 | `#/volume` e2e 冒烟 |

**4.7.1 `FMeshForm` 词条与幽灵文字（placeholder 注明关键字作用）**
```
网格类型      GEOM   [xyz]                     $ 网格几何：xyz 矩形（v1 仅此渲染）
原点          ORIGIN [x y z]                   $ 网格原点坐标（MCNP 全局坐标）
X 方向       IMESH [边界]  IINTS [区间数]      $ X 向网格边界（可多值，与 IINTS 条目一一对应；1INTS n 简写 v1 不支持）
Y 方向       JMESH [边界]  JINTS [区间数]
Z 方向       KMESH [边界]  KINTS [区间数]
能量边界     EMESH [边界]  EMINTS [区间数]      $ 可选能量分箱（多值；空=不分箱；生成发 EMINTS，导入容错 EINTS/EMINTS）
时间边界     TMESH [边界]  TMINTS [区间数]      $ 可选时间分箱（生成发 TMINTS，导入容错 TINTS/TMINTS）
材料过滤     MAT   [材料号]                     $ 可选：只统计该材料栅元
输出单位     OUT   [COL]  $ 可选：COL（默认）/CF/COLSC/CFSC/IJ/IK/JK/NONE/XDMF（FMESH 输出格式；XDMF=MCNP6.2+ ParaView，C810 待核验）
粒子设计符   FMESHn:N/P/E（卡头）                $ 粒子类型
```
- 每行输入框 `title`/`placeholder` 展示上述关键字作用（照 TallyTab FM 乘子框 `placeholder="如 8.65E10 1 -5 -6" title="FM 响应乘子…"` 先例，:180）。
- **网格编辑器复用**：IMESH/IINTS 对结构类似 E0/T0 网格（`gridState.ts` 深模块范式），但卡语义不同（边界 vs 参数化网格）→ **不复用 GridEditor**，FMeshForm 自管结构化输入，进出转换走 `fmeshState.ts`（照 gridState setFromBody/getBody 模式）。
- **DeckContext 字段**：tally 对象加 `fmesh: FmeshRow[]`（默认 `[]`）；`push/pull/addRow/updateRow` 全链路透传（照 D-05 multiplier 透传先例）。`contract.ts`/`dataCollector.ts` 同步加字段。

---

## 5. 数据结构（模型 + JSON 契约）

### 5.1 `app/models.py` 新增
```python
@dataclass
class FmeshDefinition:
    number: int = 0          # FMESHn/TMESHn 卡号
    kind: str = "FMESH"      # "FMESH" | "TMESH"
    particle: str = ""       # "N"/"P"/"E"（FMESH 卡头设计符）
    geom: str = "xyz"        # GEOM=xyz（v1）
    origin: str = ""         # "x0 y0 z0"
    imesh: str = ""          # IMESH 边界（原文，多值/续行）
    iints: str = ""          # IINTS 区间数
    jmesh: str = ""          # JMESH
    jints: str = ""
    kmesh: str = ""          # KMESH
    kints: str = ""
    emesh: str = ""          # EMESH（可选）
    emints: str = ""         # EMINTS 区间数（MCNP6 关键字；导入容错 EINTS/EMINTS）
    tmesh: str = ""          # TMESH 时间（可选；注意与 TMESH 卡种类别区分字段名）
    tmints: str = ""         # TMINTS 区间数（MCNP6 关键字；导入容错 TINTS/TMINTS）
    mat: str = ""            # MAT（可选）
    out: str = ""            # OUT（可选；FMESH 输出格式九选项 COL/CF/COLSC/CFSC/IJ/IK/JK/NONE/XDMF，见 §4.7.1）
    axs: str = ""            # AXS（可选，cyl 网格轴向量）
    vec: str = ""            # VEC（可选，cyl 网格方向向量）
    tr: str = ""             # TR（可选，网格变换编号）
    raw: str = ""            # 原文卡体（round-trip 保真兜底；结构化字段为空时回放 raw）
```
- 挂载：`TallySettings.fmesh_defs: list[FmeshDefinition] = field(default_factory=list)`。

### 5.2 序列化带出（api_server 三处，照 FM multiplier 先例 :358/:480/:665）
- `_tally_from_dict`：读 `fmesh_defs` 列表 → `FmeshDefinition`（缺 key 容忍）。
- `_deck_to_frontend_dict`：tally 项带 `fmesh_defs`（含 `raw`）。
- `_handle_parse_inp`：parse 结果携带 `fmesh_defs`。
- 前端 `contract.ts` `backend: "fmesh_defs"` 字段 ⊆ models.py（漂移闸门 §2 自动覆盖）。

### 5.3 FMESH/TMESH 卡体 → FmeshDefinition（`fmesh_parser.py`）
- **FMESH 语法**：`FMESHn:N/P/E  GEOM=xyz  ORIGIN=x0 y0 z0`（续行 `IMESH=... IINTS=...` / `JMESH` / `KMESH` / `EMESH` / `TMESH` / `MAT` / `OUT`）。**v1 结构化支持多区间** `IMESH= v1 v2 ... IINTS= n1 n2 ...`（条目一一对应，MCNP6.2+ 行为，QA d 节已 pin）；**`1INTS n` 简写语法 v1 不吸收**（`_KEYS`/`KEY_TO_FIELD` 无 `1INTS` 键，QA F2）——用户须改写为多值形式；C810 原文是否收录 `1INTS` 待人工核验。
- **TMESH 语法**：`TMESHn`（标题行）+ 子卡 `RMESHn:...`（rect）/ `CMESHn:...`（cyl）各带 GEOM/ORIGIN/IMESH/.../EMESH/TMESH/MAT/OUT。v1 结构化吸收 `RMESHn`（rect，GEOM=xyz）；`CMESHn`（cyl）解析但 `unsupported_geom=True`（渲染降级提示，round-trip 保留 raw）。
- `parse_fmesh_lines(lines) -> list[FmeshDefinition]`：按 kind 吸收；`fmesh_defs_to_lines(defs) -> list[str]`：回放（结构化字段齐全走结构化，否则回放 raw——round-trip 兜底，照 D-10 raw_line 先例）。
- **只吸收 GEOM=xyz / 参数化边界原文保留**：边界值以原文字符串存（不数值化），生成回放逐字（保 R1 不动点）。

---

## 6. FMESH 结构化链路（五步走，照 FM 乘子先例）

| 步 | seam | 改动 | 验收 |
| :--- | :--- | :--- | :--- |
| 1 入口门识别 | `core.py` parse_data_cards if/elif 链 | 加分支 `re.match(r'^FMESH\d+', first)` 与 `re.match(r'^TMESH', first)`（大小写不敏感）→ 收集连续卡体行（含 5 空格续行）→ `parse_fmesh_lines` → `result["fmesh_defs"]`；未知/异常 → 保底 other_cards（raw_line，round-trip 不丢） | 红基线绿：FMESH/TMESH 导入识别 |
| 2 结构化吸收 | `app/meshtal/fmesh_parser.py` | `parse_fmesh_lines`（§5.3） | `test_fmesh_parser` 单测绿 |
| 3 models 字段 | `models.py` | `FmeshDefinition` + `TallySettings.fmesh_defs`（§5.1） | 漂移闸门 §2 字段子集绿 |
| 4 生成器回放 | `inp_generator.py` `_generate_tallies` | F 卡段后追加 `fmesh_defs_to_lines(...)`（structured 或 raw）；`_wrap_long_lines` 照常 ≤80 列 | R1 不动点不回归（§9.4） |
| 5 序列化带出 | `api_server.py` 三处（§5.2）+ `sections.py` | DATA_PATTERNS 补 `re.compile(r'^TMESH', re.IGNORECASE)`（:180 旁）；三处序列化 | 契约闸门绿 + HTTP 往返 fmesh_defs 保留 |

- **sections.py 边界**：`^FMESH` 已有（:180）；**必须补 `^TMESH`**，否则 TMESH 卡节首直出误分曲面/栅元段（D-03 同类缺陷，防患）。
- **R1 不动点**：`generate(parse(generate(d))) == generate(d)` 对含 FMESH/TMESH 卡 deck 成立（结构化字段原文保留 + other_cards 兜底 raw 双保险）。

---

## 7. 几何外壳与体积盒世界坐标对齐（关键，契约 pin 死）

### 7.1 坐标事实
- 外壳 STL：preview-3d 产自 deck 曲面/栅元的**全局坐标**（后端 `parse_surfaces` + FreeCAD CSG）。
- 体积盒：由 meshtal `X/Y/Z direction` bin 边界边数组构建的**全局坐标**轴对齐盒（ORIGIN + IMESH 定义，MCNP 结果即全局坐标）。
- **两者天然同坐标系** → 只需「统一归一化」即可保证重合。

### 7.2 对齐机制（`alignWorld.ts` + `VolumeRenderer.ts`）
```
1. worldBox = worldBoxFromEdges(binEdges)             # 体积盒全局包围盒
2. shellBox  = union(stl mesh boundingBox)             # 外壳全局包围盒（体积盒 ⊆ 外壳）
3. unionBox  = unionBoxes([shellBox, worldBoxBox])     # 体积盒在内 → union = shellBox
4. offset    = -unionBox.getCenter()                   # 单一归一化偏移
5. 对每个外壳 mesh：geometry.translate(offset)         # 照 Preview3D 平移顺序（先平移后 computeBoundingBox）
6. 体积盒 mesh.position.set(offset)                    # 同一 offset
7. camera    = computeCameraParams(unionBox.center+offset≈0, unionBox.size)
   # 照 Preview3D 归一化：translate 先于 computeBoundingBox，target=center
```
- **关键不变量**：外壳与体积盒**共用同一 offset** → 世界坐标相对几何逐点保留 → 外壳 STL 与体积盒在场景坐标中与在世界坐标中重合关系一致。
- **勾选显示逻辑复用**：外壳栅元勾选/显隐走 Preview3D 相同的 `cellViews` 状态 + `setVisible` 控制接口（§8 独立场景内实现，不 import Preview3D 组件）。

### 7.3 验收断言（可量化）
| 断言 | 期望 |
| :--- | :--- |
| `alignWorld.test.ts::shared_offset_invariant` | 喂入 shell bbox S 与体积 worldBox V（V⊆S），`translateToCenter` 返回 offset；断言 `SminScene == Smin + offset`、`VminScene == Vmin + offset`、`VsizeScene == Vmax - Vmin`（尺寸保持）、`(VminScene - SminScene) == (Vmin - Smin)`（相对位移保持） |
| `alignWorld.test.ts::world_box_from_edges` | `worldBoxFromEdges` 每轴 min=edge[0]、max=edge[-1] |
| `alignWorld.test.ts::volume_inside_shell` | 归一化后体积盒场景包围盒 ⊆ 外壳场景包围盒（容差 1e-6） |
| `#/volume` e2e 冒烟 | 加载 fixture（valid_38 派生小样例）STL 外壳 + meshtal 帧 → 体积盒完全落在半透明外壳内、中心重合；开启「半透明查看」可见重合边 |
| 视觉 KPI（人工） | 体积彩色层无错位、无悬浮；外壳关/开切换不改变体积层位置 |

---

## 8. 性能目标（KPI 可测代理）

| 指标 | 目标 | 验收方式 |
| :--- | :--- | :--- |
| 128³ 交互流畅 | 拖动/旋转无掉帧感知（OrbitControls + renderGate 按需渲染） | e2e 冒烟人工 + renderGate 复用 |
| 打开「3D 结果」窗口 | **≤2s**（复用 preview-3d 指纹缓存命中：STL ~0.02s + meshtal-parse 缓存 + meshtal-texture worker + 首帧渲染） | e2e 计时 + §9.3 代理 |
| 时间轴切换单帧上传 | **≤50ms**（colorize + texSubImage3D） | `colorize.test.ts` 计时代理（128³ <50ms）+ e2e |
| GPU 驻留 | **≤256MB**（当前帧 RGBA 8MiB@128³ / 64MiB@256³ + 外壳 STL） | `downsample_plan` 预算断言 |
| 256³ | 显式用户选择（非默认） | `decideResolution` 单测 |
| meshtal-parse / texture 响应 | 元数据 <1s（缓存命中）；纹理 <2s（worker，缓存命中近实时） | e2e 计时 |
| 降采样 | 均值保总量（块和守恒） | `volume_builder` 单测断言 |

---

## 9. 测试映射

### 9.1 后端 pytest 新增文件（基线 343 → +N 全绿，不破 343 中既有用例）
| 文件 | 测什么 | 依赖 |
| :--- | :--- | :--- |
| `tests/fixtures/`（新增） | vendor `valid_38.meshtal` / `valid_39.meshtal` / `valid_40.meshtal`（自 `D:\MCNP\PyMCNP\files\meshtal\` 拷贝）+ 手写 `minimal_meshtal.txt`（兜底解析样例）+ `minimal_fmesh.inp` | 无 |
| `tests/unit/test_meshtal_parser.py` | vendor 3 fixture 解析：dims/binEdges/**grid_bounds**/range 断言；pymcnp 路径与兜底路径产出一致；`minimal_meshtal.txt` 走兜底 | 无（惰性 import pymcnp） |
| `tests/unit/test_meshtal_deck_match.py` | §4.6A：`overlap_fraction` / `center_offset_frac`；`check_match` 完全包含=matched / 交集过小=overlap_too_small / 中心偏移过大=offset_too_large / 不相交=matched:false；容差可注入（min_overlap=0.2、max_center_offset=0.5 边界） | 无 |
| `tests/unit/test_meshtal_volume_builder.py` | 切片 (e,t) 稠密构建；box-average 降采样**总量守恒**（输入块和==输出块和）；标量归一化 [0,255] | numpy（已就位） |
| `tests/unit/test_meshtal_downsample_plan.py` | 128 默认/256 显式；native 更小保 native；**自动决策（A2.3）**：无用户选择时自动 128³、仅显式才 256³；超预算 → over_budget=true + avgFactor 计算；`estimate_texture_bytes` 预算断言 | 无 |
| `tests/unit/test_meshtal_colormap.py` | weather LUT 锚点/插值；`map_value` v<lo → alpha 0；**golden_lut sha256 固定** | 无 |
| `tests/unit/test_meshtal_cache.py` | fingerprint(path,mtime) 稳定/变化；get/put 命中；evict 按磁盘量 | 无 |
| `tests/unit/test_fmesh_parser.py` | FMESH/TMESH 卡体 ↔ FmeshDefinition 往返；多区间 `IMESH=a b IINTS=2 2`；TMESH RMESHn 吸收 / CMESHn 降级；structured 空 → raw 回放 | 无 |
| `tests/parser/test_regress_fmesh_import.py` | **红基线**：FMESH/TMESH 导入 → fmesh_defs 结构化 → 生成回放 → 再导入字段保留；R1 不动点不回归；对照：无 FMESH 卡不回归 | 无 |
| `tests/unit/test_meshtal_worker.py` | AST 断言 worker 模块顶无 numpy/pymcnp 顶层 import；stdin/stdout JSON 协议 parse/texture round-trip（小样例） | 无 |
| `tests/integration/test_meshtal_api.py` | 子进程起 api_server（照 test_api_contract HTTP fixture）：meshtal-detect（临时 output_dir 放 fixture）/ meshtal-parse / meshtal-texture 三端点往返 + 信封；**`grid_bounds`+`match` 字段断言（A1.2）**；**坏文件/不存在路径 → 错误响应带 `hint`（F4）**；`_err` hint 对既有端点加性兼容（缺省无 hint 字段） | 无（不 import api_server） |
| `tests/integration/test_api_contract.py`（既有） | 漂移闸门 25→28 双向一致（§2 自动） | 无 |

### 9.2 前端 vitest 新增文件（基线 19 → +N 全绿，不破既有 19）
| 文件 | 测什么 |
| :--- | :--- |
| `gui/test/volume/alignWorld.test.ts` | §7.3 断言 |
| `gui/test/volume/colorize.test.ts` | weatherLut 锚点/插值、**sha256 golden 与 python 一致**、threshold→alpha0、range 重映射、**默认 range=scalarRange（A2.2）**、128³ 计时 <50ms |
| `gui/test/volume/downsampleRequest.test.ts` | 预算/弹窗决策纯逻辑；**popup 文案「要更流畅，还是要更精细？」（F3）**；自动 128³ / 256³ 显式 |
| `gui/test/volume/fmeshState.test.ts` | FmeshRow ↔ 卡体文本 ↔ deck payload |
| `gui/test/volume/workflow.test.ts` | 空态三步引导「① 运行/选择 meshtal → ② 解析 → ③ 看结果」（F1.1）+ 没找到文件可操作提示文案/动作（F1.2） |
| `gui/test/volume/ColorLegend.test.ts` | `legendTicks` 上下限/单位；色条两端显示 displayMin/displayMax 数值（F5.2） |
| `gui/test/volume/volumeShader.snapshot.test.ts` | RAY_MARCH_FRAGMENT 字符串快照（防无意识改动）；`isWebGL2` 判定 |
| `gui/test/volume/VolumeRenderer.test.ts`（可选 DOM-lite） | 类型/状态；DataTexture3D dims 匹配 frame.resolution；**开窗自动取景相机按「几何+体积联合包围盒」摆位（A2.1）** |

### 9.3 KPI 代理（e2e/人工）
- `#/volume` 浏览器模式冒烟：设 fixture → 开窗 → 体积层渲染 + 外壳勾选交互 + 半透明查看 + 时间轴拖动（若 timeBins>1）。
- 计时：开窗 ≤2s、切帧 ≤50ms（浏览器 Performance API 埋点或人工秒表）。

### 9.4 测试先行纪律（红基线 → 转绿顺序）
1. **tester 先建红基线**：
   - `tests/parser/test_regress_fmesh_import.py`（FMESH/TMESH 导入→表单→回放→再导入字段保留 + R1 不动点不回归；当前 0 结构化 → 红）。
   - `tests/unit/test_meshtal_parser.py`（vendor fixture 解析；当前无模块 → 红）。
   - `tests/unit/test_meshtal_deck_match.py`（§4.6A 匹配检测；当前无模块 → 红）。
   - api.yaml 漂移闸门预置 3 端点 operationId → 因 handlers 未加 → 双向一致红。
2. **后端施工转绿**：入口门→absorb→models→generate→serialize + `app/meshtal/` 模块 + 3 端点 + api.yaml 25→28 → 红基线全绿。
3. **验收时机**：红基线全绿后跑全量 pytest **343 基线不破** + 契约漂移闸门 **25→28 双向一致绿** + vitest **19 不破**。

---

## 10. 施工顺序（分工 + 每步验收）

> 分支：`git checkout -b feat/meshtal-volume`（自 `experiment/geouned`）。

| 步 | 改动 | 施工方 | 该步验收 |
| :--- | :--- | :--- | :--- |
| 0 | 红基线（§9.4）：test_regress_fmesh_import + test_meshtal_parser + test_meshtal_deck_match + api.yaml 预置 3 operationId | 测试 | 红基线红；全量 pytest 343 既有全绿 |
| 1 | FMESH 结构化五步（§6）：sections.py 补 `^TMESH` + core.py 入口门 + fmesh_parser.py + models.py + inp_generator.py 回放 + api_server 三处序列化 | 后端 | test_regress_fmesh_import 绿；R1 不动点不回归；343 不破 |
| 2 | `app/meshtal/`：meshtal_parser / volume_builder / colormap / downsample_plan / meshtal_cache / _meshtal_worker + **deck_match.py（§4.6A）** | 后端 | test_meshtal_* 单测绿（含 deck_match 容差边界）；vendor fixture 解析绿 |
| 3 | 3 端点 handler + worker 接线 + **`_err` hint（F4）+ meshtal-parse `grid_bounds`/`match`（A1.2）** + api.yaml 25→28（schema 补 grid_bounds/match/hint） | 后端 | 漂移闸门 25→28 双向一致绿；test_meshtal_api HTTP 往返绿（含 hint/匹配断言） |
| 4 | 前端 `gui/src/volume/`（volumeShader/VolumeRenderer/colorize/alignWorld/downsampleRequest/fmeshState/**workflow/ColorLegend**/FMeshForm/VolumeControlPanel/ResultWindow + 高级控件折叠 F2）+ windows.ts（KEY_VOLUME3D/openVolume3D/readVolume3DData）+ main.rs（open_volume3d_window/label `volume`）+ App.tsx `#/volume` 路由 + **run-mcnp 后自动 meshtal-detect 联动（A1.1）** | 前端 | vitest 全绿（19 不破 + 新增）；tsc/build 过 |
| 5 | 收尾：tester 复核（全量 pytest 343 不破 + 漂移闸门绿 + vitest 不破 + 对齐断言 + KPI 实测 + `#/volume` e2e 冒烟 + **§12 上级产品方向验收项全过**）+ 重锚定 | 测试 | 全验收表达成；向 PM 汇报 commit 索引 |

**联调点**：
1. `meshtal-parse`（子进程 worker）→ 弹窗分辨率决策 → `meshtal-texture`（缓存命中）→ 前端 colorize → texSubImage3D 首帧 <2s。
2. 体积窗口外壳 = preview-3d STL（缓存命中复用）；关体积窗口不调 clear-stl；开体积窗口不清 STL 会话。
3. FMESH 卡：表单生成 → `/api/generate` 回放 → `/api/parse-inp` 再导入字段保留（HTTP 联调）。

---

## 11. 验收标准（量化汇总）

1. **后端**：全量 pytest **343 基线不破** + 新增 `test_meshtal_*`/`test_fmesh_parser`/`test_regress_fmesh_import`/`test_meshtal_api` 全绿；`tests/unit/test_meshtal_colormap.py::golden_lut` sha256 固定。
2. **契约漂移闸门**：`/api/meshtal-detect`、`/api/meshtal-parse`、`/api/meshtal-texture` 在 handlers dict 与 api.yaml 双向一致，operationId 齐（`meshtalDetect`/`meshtalParse`/`meshtalTexture`），**25→28**。
3. **前端**：vitest **19 不破** + 新增 volume 测试全绿；tsc EXIT 0；build EXIT 0。
4. **对齐断言**：§7.3 全过（共享 offset 不变量 + 体积盒 ⊆ 外壳 + 中心重合）。
5. **性能 KPI**：打开结果窗口 ≤2s、时间轴切帧 ≤50ms、GPU 驻留 ≤256MB（128³ 默认 / 256³ 显式）、128³ 交互流畅。
6. **几何重合**：体积盒与外壳 STL 重合（世界坐标同源 + 统一归一化），半透明外壳下可见重合边。
7. **降采样**：box-average 总量守恒断言绿。
8. **e2e 冒烟**：`#/volume` 路由跑通（外壳勾选 + 半透明 + 时间轴 + 体积层渲染）。
9. **纪律**：零新依赖；未改 Preview3D.tsx 主组件；未污染 preview-3d 性能契约；体积窗口关闭不清 STL 会话；无断言降级。

> **按本契约（含 §12 上级产品方向验收标准）逐条验收**——§12 全部验收项并入本清单，作为强制门禁。

---

## 12. 上级产品方向验收标准（Advanced + Fool-proof UX，2026-08-14 追加）

> PM 已批准施工（测试先行纪律不变），追加两条产品方向为本契约的**强制验收标准**。方向一（更先进）+ 方向二（更傻瓜友好）逐条 pin 成可执行验收项。**验收口径改为「按本契约（含本节）逐条验收」**。

### 12.1 方向一 · 更先进（Advanced）

**A1 智能探测（MESHTAL 自动发现 + deck↔meshtal 匹配检测）**
- A1.1 **自动发现**：内部跑完 = `/api/run-mcnp` 完成后前端自动调 `meshtal-detect(outputDir)` 扫描 `meshtal*`/`MSHT*`（联动点=前端，**不新增端点**）；外部 = 复用 `choose-file` 直接选 meshtal 文件。两种来源都进同一解析流程。
- A1.2 **deck↔meshtal 匹配检测**（新纯函数模块 `app/meshtal/deck_match.py`，pytest 可测 seam）：
  - `AABB`（min/max/span/volume）、`overlap_fraction(a,b)`（交集体积 / min(vol_a,vol_b)）、`center_offset_frac(a,b)`（中心距 / max(model span)）、`check_match(grid_box, model_box, *, min_overlap=0.2, max_center_offset=0.5) -> MatchReport{matched, overlap_fraction, center_offset_frac, reason, message}`。
  - **口径**：`grid_box` = meshtal bin 边界算出的世界包围盒（ORIGIN..上限，worker mode=parse 产出 `grid_bounds`）；`model_box` = 与 preview-3d bound 同源口径（`_compute_bound_from_surfaces` 的 `[-B,B]³`）。
  - **比对机制（后端做，不增加端点，必须可测）**：`_handle_meshtal_parse` 请求可选携带 `{surfaces, cells, tr_cards}`（当前 deck），handler 算 `model_box` → `check_match` → 响应加 `match`；请求无模型数据 → `match:null`。worker 只回 `grid_bounds`，比对在 api_server 进程内做（纯函数，不阻塞）。
  - **绝不静默错位显示**：`match.matched==false` 时前端显示友好横幅 **「网格数据与当前模型几何可能不匹配（网格范围 X vs 模型范围 Y），可能显示错位」**（X/Y 填入实际数值），不阻止渲染但显式告知。
  - **容差**：`min_overlap=0.2`、`max_center_offset=0.5`，均可注入，测试覆盖边界（完全包含=匹配 / 交集过小=overlap_too_small / 中心偏移过大=offset_too_large / 完全不相交=matched:false）。

**A2 一切自适应（用户零操作看到正确结果）**
- A2.1 **开窗自动取景**：相机按「几何 + 体积联合包围盒」（unionBox = 外壳 ∪ 体积盒）自动摆好（`computeCameraParams`，§7.2 第 7 步）——开窗即见全貌，无需用户调整。
- A2.2 **色阶自动范围**：`colorize` 默认 `range = {min: scalarRange.min, max: scalarRange.max}`（自适应数据范围）；用户手改上下限前即显示正确渐变。
- A2.3 **分辨率自动决策**：`downsample_plan` 默认 128³ 自动定（native 更小保 native）；256³ 仅显式选择（§4.4）。

**A3 性能 KPI 强制（契约 §8 保持）**
- 切帧 ≤50ms、开窗 ≤2s（preview 缓存命中）、大文件子进程解析不卡后端（worker + pickle 缓存）。验收按 §8 表执行。

### 12.2 方向二 · 更傻瓜友好（Fool-proof UX）

**F1 引导式工作流**
- F1.1 **空态清晰指引**：无 meshtal 数据时显示三步引导「① 先运行 MCNP（或选择 meshtal 文件）→ ② 点解析 → ③ 看结果」。
- F1.2 **没找到文件给可操作提示**：`meshtal-detect` 返回空列表 → 显示「未在输出目录找到 MESHTAL 文件，请点这里选择 meshtal 文件」，「点这里」触发 `choose-file`（可操作，非报错）。
- 纯逻辑（状态→文案/动作）进 `gui/src/volume/workflow.ts`（vitest 可测）。

**F2 默认值即好用**
- 高级控件默认**折叠/隐藏**（256³ 选择、手改色阶上下限、透明度、几何外壳开关），展开才见；基础默认值（128³、自适应色阶、自动取景、外壳开）开箱即用。

**F3 大白话弹窗/提示**
- 超预算弹窗文案（非技术术语）：**「要更流畅，还是要更精细？」**（流畅=自动降采样 / 精细=保原精度）。
- 解析失败提示：**「文件格式不对或版本不兼容，请确认是 MCNP 生成的 meshtal 文件」** + 建议（选文件/重跑 MCNP）。
- 兜底解析成功但有警告时给出可读说明。

**F4 错误信封带 `hint` 字段**
- `_err(msg, status=500, hint="")` 增可选 `hint`（友好中文提示）；`hint` 非空时响应带 `"hint":"..."`，空则省略（对既有 25 端点加性兼容，不改任何既有响应字段）。
- 前端错误处理**优先显示 `j.hint`**，其次 `j.message`（原始异常）。
- 三 meshtal 端点 guard 必须带 hint（如 `_err("不是有效的 meshtal 文件", hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")`）。

**F5 FMESH 表单幽灵文字 + 色条图例**
- F5.1 FMESH 表单幽灵文字（§4.7.1）落实（placeholder/title 注明关键字作用）。
- F5.2 **色条图例清晰标注单位与上下限数值**：色条两端显示当前 displayMin/displayMax 数值 + 单位标签（如「归一化计数」）。图例刻度纯函数 `legendTicks(min,max,n)` 进 `gui/src/volume/ColorLegend.tsx`（vitest 可测）。

### 12.3 验收项汇总（可执行）
| 项 | 验收 |
| :--- | :--- |
| A1.1 | run-mcnp 完成后自动调 meshtal-detect；外部 choose-file 可选文件 |
| A1.2 | `test_meshtal_deck_match.py` 全绿（含容差边界）；meshtal-parse 响应带 `grid_bounds`+`match`；不匹配→前端友好横幅，不静默 |
| A2.1 | 开窗自动取景（联合包围盒）；`alignWorld/VolumeRenderer` 断言 |
| A2.2 | 默认 range=scalarRange（colorize 单测） |
| A2.3 | `downsample_plan` 128³ 自动 / 256³ 显式（单测） |
| A3 | §8 KPI 全达成 |
| F1.1/F1.2 | `workflow.test.ts` 绿；空态三步引导 + 可操作提示 |
| F2 | 高级控件折叠/隐藏（vitest 状态断言） |
| F3 | 弹窗文案「要更流畅，还是要更精细？」+ 解析失败提示（快照/文案断言） |
| F4 | `_err` hint 字段 + 前端优先显示 hint（HTTP 断言 + 前端单测） |
| F5.1/F5.2 | 幽灵文字落实 + 色条图例单位/上下限（`ColorLegend` 单测） |

---

## 13. 风险与对策

| 风险 | 对策 |
| :--- | :--- |
| **体积渲染性能** | 复用 renderGate（dirty 按需渲染）；交互期保持当前帧（不重建纹理）；128³ 默认；timeBins 拖动只 texSubImage3D 更新当前帧 |
| **3D 纹理内存** | 前端 CPU 上色 RGBA Uint8（128³≈8MiB/张）；**不预上传全部能量×时间帧，只上传当前帧 texSubImage3D 复用**；选 Uint8+CPU 上色避开 float 纹理扩展坑（R32F/HALF_FLOAT 扩展不可靠）；预算 ≤256MB（downsample_plan 断言） |
| **MESHTAL 数据规模** | 子进程 worker（照 `_freecad_csg_worker.py` 模式，不阻塞 5001）；`meshtal_cache` 磁盘 pickle 缓存稠密数组（path+mtime 指纹）；`meshtal-parse` 只回元数据不传稠密数组；单轴 >4096 防御 `_err` |
| **pymcnp 严格拒收** | `parse_meshtal` 先 pymcnp、异常即轻量兜底；两条路径产出同一 `MeshtalFile`；`minimal_meshtal.txt` 手写样例测兜底；真实运行产 fixture 验证 |
| **shader 可测性** | 数值逻辑镜像纯 TS 模块（colorize/alignWorld/downsampleRequest）vitest；shader 字符串快照；`#/volume` e2e 冒烟 |
| **WebGL2 不可用** | `isWebGL2()` feature-detect → 降级提示「当前环境不支持 WebGL2 体积渲染」（DataTexture3D 需 WebGL2） |
| **FMESH 链路回归** | R1 不动点（generate(parse(generate(d)))==generate(d)）测试 + other_cards raw 兜底 + 红基线（导入→表单→回放→再导入字段保留） |
| **多区间/续行边界卡体** | 边界值原文保存（不数值化）+ structured 空回放 raw（round-trip 保真双保险） |
| **TMESH cyl（CMESH）** | 解析标记 `unsupported_geom`，渲染降级提示，round-trip 保留 raw 不丢 |
| **跨语言配色漂移** | 锚点单一事实来源（§4.3.1）+ python/TS 双端 golden sha256 对照 |
| **deck↔meshtal 静默错位显示** | `deck_match.check_match`（§4.6A）+ 前端友好横幅（A1.2），绝不静默 |
| **错误信息晦涩（用户看不懂原始异常）** | `_err` 带 `hint` 友好中文提示（F4），前端优先显示 hint |
| **缓存一致性** | `meshtal_cache` 指纹含 path+mtime（文件被覆盖/重跑自动失效）；容量 LRU 驱逐 |

---

## 14. 边界与禁区（铁律）

1. **零新依赖**：不装任何东西（pip/npm 一律不碰；numpy/pymcnp/three 已就位）。
2. **不碰 preview-3d 性能契约**：`/api/preview-3d` 响应结构不变、冷/热路径零新增延迟；**不改 Preview3D.tsx 主组件**（体积窗口独立场景，仅复用纯模块 computeCameraParams/renderGate/cellMaterial/STLLoader）。
3. **体积窗口关闭不清 preview-3d 的 STL 会话**：`ResultWindow` 关闭只 `close_window`，不调 `clearStlSession()`。
4. **不改 generator/parsers 既有测试 pin 行为**：只允许 §6 最小增量（sections.py 补 `^TMESH`、core.py 入口门、inp_generator `_generate_tallies` 追加 fmesh 回放）；既有 `tests/parser/*` 全部保持绿。
5. **测试不 import `gui.backend.api_server`**（模块级 pyvista/FreeCAD 探测污染）；不 import FreeCAD。
6. **API 信封统一**：三端点响应 `{"status":"ok", ...}` / `_err`（照 :539/:546）。
7. **不预上传全部能量×时间帧**：只当前帧；时间轴动画逐帧 texSubImage3D。
8. **能量区间选择 v1 范围**：单能量 bin 选择；多 bin「区间合并求和为一帧」列为增强项（不在 v1 契约内）。
9. **v1 不覆盖**：TMESH cyl 渲染、对数归一化、多时间帧预计算、TR 变换后的 ORIGIN 重映射（meshtal 已给全局坐标，天然对齐）。
10. **智能探测不新增端点**：run-mcnp 后自动扫描 = 前端在 run 完成后调 `meshtal-detect`（A1.1 联动点）；deck↔meshtal 比对在 `meshtal-parse` handler 内（A1.2）。漂移闸门保持 **25→28**（不扩到 29+）。

---

## 15. ADR 建议（施工完成后由架构师补录 PROJECT_MEMORY §4）

| 决策 | 理由 |
| :--- | :--- |
| meshtal-texture 返回**标量帧**（非 RGBA），前端 colorize CPU 上色 | 用户手改上下限/阈值只重跑本地 colorize（小开销），不重取纹理；Uint8+CPU 上色避开 float 纹理扩展坑；只上传当前帧 |
| 大文件解析走**子进程 worker** + `meshtal_cache`（path+mtime 指纹 pickle） | 照 `_freecad_csg_worker.py` 模式防阻塞 5001；重复取帧免整文件重解析 |
| FMESH/TMESH 卡**结构化字段原文保留** + raw 兜底 | 照 D-10 raw_line 先例：结构化可编辑、raw 保证 R1 不动点与 round-trip 保真 |
| 体积窗口**复用 Preview3D 纯模块 + 独立场景**，不改 Preview3D 主组件 | 不污染 preview-3d 性能契约；外壳与体积盒统一归一化（共享 offset）保证重合 |
| 配色锚点**跨语言 golden sha256 对照** | 防 python colormap 与 TS colorize 漂移 |
| deck↔meshtal 匹配检测下沉 `app/meshtal/deck_match.py`（纯函数），**比对在后端 handler 做**（meshtal-parse 响应带 `grid_bounds`+`match`），不新增端点 | A1.2 要求可测、绝不静默错位；worker 保持哑（只回 grid_bounds）；前端只渲染 match 结果 |
| `_err` 增**可选 `hint` 字段**（加性兼容，空则省略） | F4 傻瓜友好；对既有 25 端点零破坏（漂移闸门不感知） |
| **自适应默认**（开窗自动取景 / 色阶自动范围 / 128³ 自动决策）+ **高级控件默认折叠** | A2/F2「默认值即好用」，用户零操作看到正确结果 |
| 入口门/API 契约 **25→28 双向同步** | 照 preview-3d/geometry-check 契约先例，防文档腐烂 |

---

## 16. 施工完成后重锚定清单

动工前基线行号（2026-08-14 已核验）：
| 符号 | 行号 |
| :--- | :--- |
| handlers dict | api_server.py:501-527 |
| `_ok` / `_err` | api_server.py:539 / :546 |
| `_handle_preview_3d` | api_server.py:1021 |
| `_handle_run_mcnp`（output_dir 语义 :809） | api_server.py:803 |
| `_PREVIEW_CACHE` 接线（preview_cache import :38） | api_server.py:35-39 |
| `_STL_SESSION` / `_clear_stl_session` | api_server.py:44 / :51 |
| `_tally_from_dict` / `_deck_to_frontend_dict` / `_handle_parse_inp`（FM multiplier 带出） | api_server.py:358 / :480 / :665 |
| `parse_data_cards` 入口门（FMESH 落 other_cards :1284-1287） | core.py:941 / :1284 |
| `parse_f_tally` FM 分支（先例） | core.py:772-788 |
| `DATA_PATTERNS`（`^FMESH` :180） | sections.py:140-181 |
| `_generate_tallies`（FM 回放 :670-671） | inp_generator.py:633-674 |
| `_generate_other_cards`（末尾回放 :1111-1120） | inp_generator.py:1111 |
| `TallyDefinition.multiplier`（先例） | models.py:200 |
| `PreviewCache`（深模块先例） | preview_cache.py:25-153 |
| worker spawn（`_run_freecad_script`） | freecad_preview.py:390-431 |
| 前端 windows.ts（KEY_PREVIEW3D :12 / openPreview3D :49） | windows.ts:12 / :49 |
| main.rs `open_preview3d_window`（:74）/ `open_cross_section_window`（:79） | main.rs:73-81 |
| Preview3D.tsx `initScene`（:95）/ `loadStlMeshes` 归一化（:296-305）/ 勾选显隐（:401-418） | Preview3D.tsx:95 / :296 / :401 |
| `computeCameraParams` / `renderGate` / `cellMaterial`（纯模块） | cameraParams.ts / renderGate.ts / cellMaterial.ts |
| api.yaml（25 端点，:34-891） | api.yaml:34 |
| `_compute_bound_from_surfaces`（model_box 同源口径，供 deck_match 调用方） | freecad_preview.py:268 |
| 契约漂移闸门（双向一致） | test_api_contract.py:80-97 |
| vendor meshtal fixture | D:\MCNP\PyMCNP\files\meshtal\valid_38/39/40.meshtal |

施工完成后更新：`PROJECT_MEMORY.md`（§4 ADR + §8 变更日志）、`app/UI_ARCHITECTURE.md`（若涉及 preview 链路描述）。

---

## 17. 交付检查清单

- [ ] `app/meshtal/`：meshtal_parser / volume_builder / colormap / downsample_plan / meshtal_cache / _meshtal_worker + **deck_match.py（§4.6A）** 全部落地
- [ ] vendor fixture（valid_38/39/40.meshtal + minimal_meshtal.txt + minimal_fmesh.inp）拷贝进 `tests/fixtures/`
- [ ] FMESH 结构化五步全链（core.py 入口门 + fmesh_parser.py + models.py + inp_generator.py 回放 + api_server 三处序列化 + sections.py 补 `^TMESH`）
- [ ] 3 端点 handler + worker 接线 + **`_err` hint（F4）+ meshtal-parse `grid_bounds`/`match`（A1.2）** + api.yaml 25→28 双向一致；漂移闸门绿
- [ ] 前端 `gui/src/volume/` 11 模块（含 **workflow/ColorLegend**）+ 高级控件折叠（F2）+ windows.ts 桥 + main.rs `open_volume3d_window`（label `volume`）+ `#/volume` 路由
- [ ] **A1.1**：run-mcnp 后自动 meshtal-detect；外部 choose-file 可选文件
- [ ] **A1.2**：test_meshtal_deck_match 全绿（容差边界）；不匹配 → 前端友好横幅，不静默
- [ ] **A2/F2**：开窗自动取景 + 色阶自动范围 + 128³ 自动决策；高级控件默认折叠
- [ ] **F1**：空态三步引导 + 没找到文件可操作提示；**F3**：弹窗「要更流畅，还是要更精细？」+ 解析失败提示；**F5.2**：色条图例单位/上下限
- [ ] 对齐断言（§7.3）全过；体积盒 ⊆ 外壳、中心重合
- [ ] KPI 实测：开窗 ≤2s、切帧 ≤50ms、GPU 驻留 ≤256MB、128³ 流畅、256³ 显式
- [ ] `#/volume` e2e 冒烟：外壳勾选 + 半透明 + 时间轴 + 体积层渲染
- [ ] 全量 pytest **343 基线不破** + 新增全绿（复跑 ×2）；vitest **19 不破** + 新增全绿；tsc/build 过
- [ ] 红基线 → 转绿顺序达成；无断言降级；零新依赖；未改 Preview3D.tsx 主组件；体积窗口关闭不清 STL 会话
- [ ] PROJECT_MEMORY.md 更新 + 向 PM 汇报 commit 索引
