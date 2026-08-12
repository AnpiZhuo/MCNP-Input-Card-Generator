# 3D 预览卡顿修复契约（复现实测修订版）

> 契约人：架构师 | 施工方：后端 + 前端 | 分支：自 `experiment/geouned` 拉出（命名 `perf/preview3d`）
> 日期：2026-08-12 | 状态：**契约已锁定（复现实测回填，修订原诊断）**
> 依据：`PROJECT_MEMORY.md` 顶部 3D 预览任务节 + repro agent（`repro`）复现实测权威数据 + 7 个已 vendor 大尺寸预览 fixture（`tests/fixtures/preview_*.inp`）
> 目标：打开卡 / 交互卡 / 大坐标深度三真凶 + 三项新发现，按 P0a~P0d 修复；现有 251 用例零回归；新增后端/前端性能测试
> 行号说明：本契约行号为动工前 Grep 重锚定值（2026-08-12 工作树），施工以每次 Grep 重锚定为准（见 §11）。

---

## 0. 纪律（施工方必读，违反即打回）

1. **不改 MCNP 生成/解析语义**：`app/generator/`、`app/generator/parsers/` 一律不碰（本轮不涉及）。
2. **不改 API 契约**：`docs/contracts/api.yaml` 25 端点不变；`/api/preview-3d` 响应结构（`stl_files`/`stl_data`/`freecad`/`count`）不变；缓存与 127.0.0.1 均对契约透明。
3. **测试铁律不变**：纯引擎测试不得 `import gui.backend.api_server`；测试不得 `import FreeCAD`。
4. **每 commit 前 grep 重锚定、每步全量 pytest**：任一 commit 不得打破 P0 全绿 251（新增测试另计，见 §8）；前端 vitest 不并入 pytest 门禁。
5. **禁止反向降级断言**（改断言、删断言、加 skip 骗绿一律打回；FreeCAD 依赖的集成测试仅允许整文件条件 skip，不算绿数）。
6. **边界**：复现脚本在仓库外 `D:\code\preview_measure\`（测试不依赖）；本轮不新增运行时依赖（vitest 仅 `gui/` devDependency，见 §8.3，需 PM 确认）。
7. 施工完成按 §11 重锚定文档并向 PM 汇报 commit 索引。

---

## 1. 背景与诊断修订（复现实测锚定）

### 1.1 管线
```
Preview3D.tsx → POST /api/preview-3d → api_server._handle_preview_3d (:1001)
→ FreeCADEngine.build_geometry (freecad_preview.py:243)
→ 子进程 _freecad_csg_worker.py（逐曲面布尔裁剪 + 逐栅元 AST 布尔级联）
→ tessellate(1.0) → 每栅元 STL → base64 单 JSON
→ 前端 atob + STLLoader.parse（Preview3D.tsx:305-308）
```

### 1.2 被反驳的原诊断（不要按原假设修）
| # | 原诊断 | repro 反驳 |
| :--- | :--- | :--- |
| 1 | 前端同步解析大 STL = 主因 | 16MB 实测 54ms（JSON.parse 11ms），不构成秒级卡顿 |
| 2 | 120s 超时风险 | 官方大文件子进程最大 2.38s |
| 3 | 大坐标 OCC 精度崩溃 | ±2742/±10000 布尔 <0.6s 无崩溃 |
| 4 | 20m bound 放大布尔更贵 | 简单几何布尔 0.1~0.6s 不慢 |

### 1.3 被确认的真凶（优先修）
1. **P0a 打开卡（最可复现）**：每次打开无缓存全量重建（3 连发均 3.30s）+ 无加载态 + handler 1.3~2.7s + HTTP ~0.5s → 1.5~3s 白屏。前端 `Preview3D.tsx:542` `useEffect([], ...)` 每次打开必 POST 全量重建；handler（`api_server.py:1001`）每次跑 FreeCAD 子进程，无任何缓存。
2. **P0b 交互卡（与几何大小无关，最贴用户症状）**：`rebuildTicks`（`Preview3D.tsx:196-243`）相机 change 每帧重建 ~160 对象 / 81 张 CanvasTexture（拖动时），且清空时只 dispose sprite 的 material，Line geometry 与 CanvasTexture 从未 dispose → GPU 泄漏累积；无条件渲染循环（354-383）每 rAF 都 render；全栅元 `transparent+opacity0.6+depthWrite:false`（312）→ 透明通道 overdraw。简单 20m 屏蔽也卡。
3. **P0c 大坐标闪烁**：`near=0.1` 固定（99）、`far=realVD*100`（344）→ far/near 随几何线性放大；±1000 时 ≈7M 临界、±10000 时 ≈17.5M 超 2^24 深度极限；几何不归一化、`target` 恒原点（341）。

### 1.4 新发现（高收益低成本，优先入契约）
1. **IPv6 HTTP 惩罚**：server 只绑 `0.0.0.0:5001`（`api_server.py:1283`，IPv4），前端 ~25 处硬编码 `http://localhost:5001`。Chrome 对 localhost 先试 `::1` → 连接拒绝 → Happy Eyeballs 回退 IPv4，每请求 ~300-500ms，**影响全部 25 端点**。修法：前端收敛为 `127.0.0.1` 单一常量（CORS 已 `*`，api_server.py:541，切换 host 不破坏）。
2. **vtk 惰性化**：worker（`_freecad_csg_worker.py:30-35`）模块顶层 `import vtk`，每次子进程启动白付 ~0.46s（无 GQ/SQ 也加载），占子进程 ~35%。→ 惰性 import。
3. **bound 过撑 bug**：`_compute_bound_from_surfaces`（`freecad_preview.py:206-225`）把宏体方向向量/轴长当坐标取 max。`preview_shield_20m.inp` 的 RCC `h=(0,0,4000)` 是轴长非坐标 → `max_coord=4000` → B=5300，真实外盒 ±2000 → 应为 2700。→ 只对位移类参数取 max。

---

## 2. 性能目标（实测锚定 + 可测代理）

| 指标 | 基线（repro 实测） | 目标 | 验收方式 | 依赖实测？ |
| :--- | :--- | :--- | :--- | :--- |
| 打开延迟·缓存命中 | 3.30s 全量重建 ×3 | **≤ 1.0s**（同一 deck 第二次打开，POST 发起到 `stl_data` 收到） | repro 实测 + §4.3 代理 | 是（实测）+ 代理 |
| 打开延迟·冷启动 | 1.5~3s 白屏 | **≤ 3.0s**（缓存未命中） | repro 实测 | 是 |
| 拖动每帧新建对象 | ~160 | **≤ 60**（lines+sprites） | `TickGrid.rebuild().created` 断言 | 否（CI） |
| 拖动每帧新建纹理 | 81 | **≤ 30** | `TickGrid` texture 计数断言 | 否（CI） |
| 拖动泄漏 | 每帧泄漏不释放 | **disposed == created**（重建后归零） | `TickGrid` 断言 | 否（CI） |
| idle 渲染 | 每 rAF 渲染 | **0 渲染**（无输入不渲染） | `renderGate` 断言 | 否（CI） |
| far/near | 7M~17.5M | **≤ 1e4**（远离 2^24 极限，安全区 <1e5） | `computeCameraParams` 断言 | 否（CI） |
| bound | shield_20m = 5300 | **≈ 2700**（1.3×2000+100，±5%） | `_compute_bound_from_surfaces` 单测 | 否（CI） |
| vtk 启动成本 | 0.46s/次（~35%） | 无 GQ/SQ 不 import | worker AST 断言 | 否（CI） |
| IPv6 惩罚 | 300-500ms/请求 ×25 端点 | **0** | grep 归零 + repro 实测 | 混合 |

> 标注"是"的目标（打开延迟/冷启动、拖动帧率、无闪烁、vtk 时间、IPv6 时间）依赖 repro 在 `D:\code\preview_measure\` 的实测，无法在 CI 断言 → 用右侧可测代理指标替代。

---

## 3. P0a 打开卡

### 3.1 根因
- 前端每次打开 `Preview3D.tsx:542` `useEffect([], ...)` 无条件 POST `/api/preview-3d`，无任何会话/缓存复用。
- handler（`api_server.py:1001`）每次跑 `build_geometry` → FreeCAD 子进程（占 handler 1.3~2.7s 的主体；`freecad_locator.bin_dir()` 已有进程内缓存，故不是 detect 扫描问题）。HTTP 序列化 base64 单 JSON 另加 ~0.5s（其中含 §6.1 IPv6 惩罚）。
- 前端无加载态：fetch 期间界面只显示空轴/刻度 → 白屏。

### 3.2 改法

**3.2.1 后端新建深模块 `app/preview_cache.py`**（纯 stdlib，接口即测试面）
```python
class PreviewCache:
    """deck 指纹缓存：同输入跳过 FreeCAD 子进程。隐藏规范化/哈希/目录生命周期/驱逐。"""
    def fingerprint(self, surfaces: str, cells: list, tr_cards: str) -> str:
        """canonical json (sort_keys) → sha256 hex。同一 deck 文本/结构 → 同指纹。"""
    def get(self, fp: str) -> dict | None:
        """命中且目录仍存在 → {"dir": ..., "cells": {...}, "freecad": ...}；否则 None。"""
    def put(self, fp: str, session: dict) -> None: ...
    def evict_dir(self, d: str) -> None:
        """会话目录被清（clear-stl/覆盖）时同步驱逐对应缓存项，防悬挂。"""
    def evict_lru(self, max_entries: int = 3) -> None: ...
```
实现要点：
- 缓存存 STL 文件目录（磁盘），LRU 上限 3 指纹（常量可配，§7 S3）；`fingerprint` 输入与 handler 收到的 `data` 一致（`surfaces` 文本、`cells` JSON 列表、`tr_cards` 文本），canonical 序列化用 `json.dumps(..., sort_keys=True)`。
- 命中时**不调用 FreeCAD**；把 `freecad` 检测路径存入缓存项，命中直接复用。

**3.2.2 `api_server.py:_handle_preview_3d`（:1001）接线**
```
fp = cache.fingerprint(surfaces, cells_list, tr_cards)
if cached := cache.get(fp):
    # 免 FreeCAD：把缓存目录作为本会话 STL 源
    _STL_SESSION = {"dir": cached["dir"], "cells": cached["cells"]}
    for num in cached["cells"]: 读 STL 文件 → base64 进 stl_data
    返回 {stl_files, stl_data, freecad: cached["freecad"], count}
else:
    # 走现状：detect_freecad → parse → build_geometry → base64（1001-1067）
    # 结束后 cache.put(fp, {"dir": session_dir, "cells": _STL_SESSION["cells"], "freecad": freecad_bin})
```
注意点：
- **`_clear_stl_session`（api_server.py:41）与缓存联动**：`clear-stl` 和每次预览覆盖时清掉的 session 目录若在缓存中，须 `evict_dir`（否则缓存指向已删目录，`get` 校验 `os.path.isdir` 兜底为 miss）。
- **响应结构逐字段不变**：`stl_files` 指向缓存目录内 `cell_N.stl`（供 `serve-file`/截面复用）；`freecad` 用缓存值。
- `_STL_SESSION` 必须指向缓存目录，否则跨请求截面 miss。

**3.2.3 前端加载态（`Preview3D.tsx`）**
- 新增 `const [loading, setLoading] = useState(true)`；`useEffect`（:519）fetch 前置 true，`.then/.catch` 后置 false。
- 渲染加载遮罩（复用 initErr 的绝对定位遮罩样式，`:675-678`），文案"正在生成 3D 几何…"。
- `useEffect([], ...)` 保持每次打开都请求（缓存让重复打开快）。

### 3.3 验收标准
| 测试 | 期望 |
| :--- | :--- |
| `tests/unit/test_preview_cache.py::test_fingerprint_stable` | 同输入同指纹；不同输入（改一曲面/一栅元/一 TR）指纹不同 |
| `test_preview_cache::test_put_get_hit` | put 后 get 命中同 dir/cells |
| `test_preview_cache::test_evict_lru` | 超 3 指纹删最旧 |
| `test_preview_cache::test_evict_dir` | evict_dir 后 get 返回 None |
| `test_preview_cache::test_hit_skips_builder` | **命中不调用注入的 builder 依赖**（PreviewCache 构造函数接受可选 `builder` seam，测试注入计数函数断言 0 次调用） |
| handler 结构不变量 | 缓存命中/未命中响应均含 `stl_files`/`stl_data`/`freecad`/`count`（漂移闸门复跑） |
| repro 实测 | 同一 deck 第二次打开端到端 ≤ 1.0s；冷启动 ≤ 3.0s；fetch 期间有加载指示（人工） |

### 3.4 风险
- 缓存目录磁盘占用：上限 3 指纹 × 每指纹数十 MB，可控；LUR 驱逐按需。
- 缓存悬挂：`get` 内 `os.path.isdir` 校验 + `evict_dir` 双保险。
- 覆盖预览时旧 session 目录被 `_clear_stl_session` 删除 → 必须同步 `evict_dir`，否则旧指纹命中已删目录（isdir 兜底 miss，安全但漏缓存）。
- **不可复用前端既有 `_STL_SESSION` 代替缓存**：会话是单槽覆盖式，缓存是 deck 指纹多槽式，两者都要。

---

## 4. P0b 交互卡

### 4.1 根因
- `rebuildTicks`（`Preview3D.tsx:196-243`）：清空时只 `material.dispose()`（:201），Line 的 `BufferGeometry` 与 sprite 的 `CanvasTexture` 均未 dispose → GPU 泄漏；每次相机 change 重建 ~160 对象/81 纹理。
- 无条件渲染循环（:354-383）：每 rAF `renderer.render`，即使场景零变化。
- 全栅元透明（:312）`transparent:true, opacity:0.6, depthWrite:false` → 透明通道 overdraw（MCNP 栅元互斥，opaque 渲染几何本就正确）。

### 4.2 改法（前端拆 4 个深模块 + 接线）

**4.2.1 `gui/src/three/TickGrid.ts`（纯 TS，替换 196-243 实现）**
```ts
export interface TextureFactory { (label: string, color: number): { dispose(): void } }
export interface TickGrid {
  rebuild(opts: { dist: number; axes: { dir: [number,number,number]; color: number }[] }): { created: number; disposed: number; textures: number };
  dispose(): void;
}
export function planTickStep(dist: number): number; // 步长查表，扩展到 1e6，目标每轴 ≤ 10 刻度
export function createTickGrid(group: THREE.Group, createTexture?: TextureFactory): TickGrid;
```
- 实现：内部台账 `createdGeoms/createdTexs/disposedGeoms/disposedTexs`；rebuild 先完整 dispose 旧的（**line.geometry.dispose + line.material.dispose + sprite.material.dispose + sprite.material.map.dispose**）再建新的；`planTickStep` 纯函数把 STEPS 表从 `[...500]` 扩展到含 `1000/2000/5000/1e4/2e4/5e4/1e5/2e5/5e5/1e6`，避免大 dist 下 step 饱和 500 导致刻度爆炸（这是当前 160 对象的主因）。
- `createTexture` 依赖注入（默认 `THREE.CanvasTexture`），测试注入假纹理记账 dispose → 满足"接受依赖不创建依赖"。
- 接口小、实现深：隐藏 canvas 尺寸/步长/格式化/定位/生命周期。

**4.2.2 `gui/src/three/renderGate.ts`（按需渲染，替换 354-383 循环结构）**
```ts
export interface RenderLoop { markDirty(): void; dispose(): void }
export function createRenderLoop(opts: { requestFrame?: (cb: () => void) => number; cancelFrame?: (id: number) => void; onRender: () => void }): RenderLoop;
```
- 循环：每帧 `if (dirty) { onRender(); dirty = false; }`；`markDirty()` 置位。
- 接线：controls `change`（:262）、WASD 按键移动、`loadStlMeshes`、`setVisible`/`setColor`/`selectAll`、`resizeRenderer` 全部调 `markDirty()`。
- OrbitControls `enableDamping` 在衰减期持续触发 `change` → dirty 保持 true 直到停稳，**视觉无损**。
- `requestFrame` 注入（测试假 rAF），生产用 `requestAnimationFrame`。

**4.2.3 `gui/src/three/cellMaterial.ts`（透明 overdraw，替换 312 行）**
```ts
export type TransparentMode = "opaque" | "see-through";
export function buildCellMaterial(opts: { color: string; transparentMode?: TransparentMode }): { transparent: boolean; depthWrite: boolean; opacity: number };
```
- 默认 `opaque` → `{transparent:false, depthWrite:true, opacity:1}`（正确、无 overdraw）。
- `see-through` → 现状透明配置（`opacity:0.6, depthWrite:false`）。
- 面板加"半透明查看"开关（默认关）：开启时全栅元 `see-through`，关闭时 `opaque`。M0 真空色维持 opacity 0。
- **UX 变化需 PM 裁决**（见 §10.3）：默认半透明关闭。MCNP 栅元互斥（#n 已挖空），opaque 显示真实几何；半透明只是"看穿外壳"辅助视图。

**4.2.4 `Preview3D.tsx` 接线**：`tickGroup` 生命周期移交 TickGrid；`rebuildTicks/scheduleRebuild`（196-252）调用 `tickGrid.rebuild({dist, axes})`；`animate` 换 renderGate；材料走 `buildCellMaterial`。

### 4.3 验收标准
| 测试（vitest，§8.3） | 期望 |
| :--- | :--- |
| `tickGrid.test.ts::rebuild_disposes_previous` | 连续 rebuild ×2，`disposed == created` 且重建后台账归零 |
| `tickGrid.test.ts::rebuild_object_budget` | `dist=1e5`（100m deck）时 `created ≤ 60`、`textures ≤ 30` |
| `tickGrid.test.ts::plan_step_no_saturation` | `planTickStep(1e5)` 返回 ≥ 500（STEPS 表不饱和） |
| `renderGate.test.ts::idle_no_render` | 不 `markDirty` 跑 5 帧，`onRender` 调用 0 次；`markDirty` 后恰 1 次 |
| `cellMaterial.test.ts::default_opaque` | 默认 `transparent:false, depthWrite:true`；`see-through` 模式透明 |
| repro 实测 | 拖动每帧对象 ≤ 60/纹理 ≤ 30；GPU 纹理数不随拖动累积；idle 帧率工具 0 渲染 |

### 4.4 风险
- **dirty flag 漏置** → 画面不刷新：必须在所有状态变更点置 dirty（§4.2.2 清单逐项覆盖）。
- **damping 结束前必须继续渲染**：`change` 事件天然覆盖；若未来改 `enableDamping=false`，需在 rotate/zoom 结束补 dirty。
- **TickGrid 清空必须比建多**：漏 dispose 任一类对象，泄漏即回退；台账断言兜底。
- 半透明默认关闭是行为变化（用户可能期望开箱看穿外壳）——需 PM 确认默认值（可改为"首次进入提示用户点开开关"）。

---

## 5. P0c 大坐标深度

### 5.1 根因
- `near=0.1` 固定（`Preview3D.tsx:99`）；STL 加载后 `far=realVD*100`（:344）且 `realVD=realExt*3.5` → far/near = 350，但 far 数值随几何放大：±1000 → 7M、±10000 → 17.5M，超 2^24 深度极限 → 闪烁。
- 几何不归一化，`controls.target` 恒 `(0,0,0)`（:341）：大偏移几何（如 inp01 z∈[0,10000]）远离原点，深度精度进一步恶化。

### 5.2 改法（几何归一化 + near/far 动态收紧）

**5.2.1 `gui/src/three/cameraParams.ts`（纯函数，替换 334-347 reframe）**
```ts
export interface CameraParams {
  near: number; far: number; farNear: number;
  position: [number, number, number]; target: [number, number, number];
  minDistance: number; maxDistance: number;
}
export function computeCameraParams(
  bboxCenter: [number, number, number],
  bboxSize: [number, number, number],
): CameraParams;
```
- 公式：`realExt = max(size)/2`；`near = realExt*0.02`；`far = realExt*100`；`farNear = far/near = 5000`（恒 ≤ 1e4）；`position = center + (0.6,0.6,0.5)*realExt*3.5`；`target = center`；`minDistance = realExt*0.1`；`maxDistance = realExt*50`。
- 常量集中，纯数学，无 THREE 依赖 → 直接单测。

**5.2.2 `Preview3D.tsx` 接线**
- **几何归一化**：`loadStlMeshes`（:285）加载完成后，先计算 `totalBox.center`，对每个 mesh `geometry.translate(-cx,-cy,-cz)`（或 `mesh.position -= center`），**然后** `computeBoundingBox()`（:319 的顺序依赖：必须先平移后重算 bbox，否则 renderOrder 排序用旧 bbox）。
- 归一化后 `target` 保持原点 → 轴线/刻度（以原点为中心）天然对齐，无需改 `updateAxes`/`rebuildTicks` 的坐标基准。
- 相机参数用 `computeCameraParams(totalBox.center, totalBox.getSize())` 替换 :337-345 手写 reframe；near/far 收紧。
- **截面不受影响**：`/api/cross-section` 用后端全局坐标 STL 会话（服务端切），前端场景几何平移纯属视图层，不影响切片对齐。

### 5.3 验收标准
| 测试 | 期望 |
| :--- | :--- |
| `cameraParams.test.ts::far_near_bounded` | inp01 bbox（center≈[0,0,5000], size≈[4000,4000,10000]）→ `farNear ≤ 1e4` |
| `cameraParams.test.ts::far_near_small_deck` | shield bbox（±2000）→ `farNear ≤ 1e4` |
| `cameraParams.test.ts::monotonic_bounded` | `bboxSize` ∈ [1e-2, 1e5] 全范围 `farNear ≤ 1e4` |
| repro 实测 | ±10000 deck 无闪烁；far/near 从 17.5M → ≤ 1e4 |
| 回归 | 小 deck（minimal）相机不因 near/far 收紧被裁剪（near < minDistance，公式保证） |

### 5.4 风险
- **平移顺序**：`geometry.translate` 必须在 `computeBoundingBox` 之前，否则 sort/renderOrder 错乱。
- `near=realExt*0.02` 对极小 deck（realExt≈1e-2 → near≈2e-4）仍合法（PerspectiveCamera 支持），但需回归确认。
- 若未来截面要在前端 3D 场景叠加对齐（当前非此设计），归一化会破坏——记录为边界，不在本轮扩展。

---

## 6. P0d 新发现三项（高收益低成本）

### 6.1 IPv6 绑定/前端直连

**根因**：server 只绑 IPv4 `0.0.0.0`（`api_server.py:1283`）；前端 ~25 处硬编码 `http://localhost:5001`（`gui/src`：App.tsx、Preview3D.tsx、PreviewDialog.tsx、Preview3DWindow.tsx、CrossSectionWindow.tsx、AdvancedTab.tsx、GeometryTab.tsx、MaterialEditDialog.tsx、OutputTab.tsx、backend.ts、dataCollector.ts、sectionConvert.ts、useFreecadStatus.ts、windows.ts 等）。Chrome localhost 先试 `::1` → 拒绝 → Happy Eyeballs 回退 IPv4，每请求 ~300-500ms ×25 端点。

**改法（裁决：前端改 127.0.0.1，后端绑定不动）**：
- 新建 `gui/src/utils/api.ts`：`export const API_BASE = "http://127.0.0.1:5001";` 及 `export const apiUrl = (p: string) => API_BASE + p;`
- 25 处 `"http://localhost:5001/api"` 替换为 `${API_BASE}/api`（或 `apiUrl("/api/...")`）。
- 后端 `0.0.0.0` 绑定保留（127.0.0.1 直连命中 IPv4；保留局域网可访问性）。CORS 已 `*`（:541），host 切换不破坏跨源。
- 备选（弃用）：后端绑 `::`（AF_INET6 双栈）——Windows Python 双栈行为不可靠，改动面反而集中在前端单一常量，故选前端。

**验收**：grep `gui/src` 对 `localhost:5001` 归零；`api.ts` 导出 `API_BASE`；repro 实测单请求下降 ~300-500ms。

**风险**：Tauri 窗口 fetch `127.0.0.1` 跨源 → CORS `*` 已覆盖；无 CSP 限制（现状 localhost 同为跨源）。

### 6.2 vtk 惰性化

**根因**：`_freecad_csg_worker.py:30-35` 模块顶层 `import vtk`，每次子进程启动（无论有无 GQ/SQ）白付 ~0.46s（~35% 子进程时长）。

**改法**：
- 顶层 `_HAVE_VTK` 保留为模块标记但初值 `False`，**删除顶层 `import vtk`**。
- `_quadric_to_shape`（:671）的 native 回退分支（`_quadric_to_native` 返回 None）内按需 `import vtk`（try/except，成功置 `_HAVE_VTK=True`），再走 marching cubes。
- `_quadric_to_native` 优先路径不变（多数 GQ/SQ 原生分类不需 vtk）。

**验收**：
- `tests/integration/test_preview3d_worker.py`（AST，仿 `test_tech_debt`）：解析 `_freecad_csg_worker.py` 源码，断言模块顶层无 `import vtk`/`from vtk`；`import vtk` 出现在 `_quadric_to_shape` 函数体内。
- repro 实测：无 GQ/SQ deck 子进程启动下降 ~0.46s。

**风险**：惰性 import 必须在 marching cubes 分支执行前完成（本设计在分支内，天然满足）；import 失败仍抛 `RuntimeError("VTK 不可用...")`（:677）。

### 6.3 bound 位移参数修正

**根因**：`_compute_bound_from_surfaces`（`freecad_preview.py:206-225`）对全部数值参数取 `max abs`，把宏体方向向量/轴长当坐标。`preview_shield_20m.inp` 的 `1009 rcc 0 0 -2000 0 0 4000 180`：`h=(0,0,4000)` 是轴长 → `max_coord=4000` → B=5300；真实外盒 ±2000 → 应为 2700。

**改法（替换 206-225 实现，接口 `(surf_dicts, default) -> float` 不变，:271 调用点不变）**：
- 按曲面类型定义"extent 相关参数"规则：位移类参数（空间坐标/偏移/半径）直接取 max；方向向量类（RCC/REC/TRC 的 h、BOX 的 a1/a2/a3、WED 的 v1/v2/v3、RHP 的 r/s/t）**不单独取模**，而与基点合成角点（顶点 = base + Σ向量）后参与。
- 类型→规则映射表（键 = `_pymcnp_surf_to_dict` 的 `type` 串）：

| type | extent 相关 | 说明 |
| :--- | :--- | :--- |
| PX/PY/PZ | `[d]` | 平面位置 |
| SO | `[r]` | 半径 |
| SX/SY/SZ | `[c, r]` | 中心+半径 |
| S | `[x,y,z,r]` | |
| CX/CY/CZ | `[r]` | |
| C/X C/Y C/Z | 全参 | 偏移+半径 |
| KX/KY/KZ | `[顶点]` | 跳过 `t²`/`sgn` |
| K/X K/Y K/Z | `[x0,y0,z0]` | 跳过 `t²`/`sgn` |
| TX/TY/TZ | `[x0,y0,z0,A,Bc]` | 跳过第三半径占位 |
| P_0 | `[D]` | 跳过法向 A/B/C |
| P_1 | 全 9 坐标 | |
| RPP | 全 6 | |
| SPH | `[vx,vy,vz,r]` | |
| RCC/TRC | 基 `[vx,vy,vz]` + `[r...]` + 端点 `v+h` | h 是轴长，端点=基点+轴 |
| REC | 基 + `v1`、`v2`、端点 `v+h`、`v+v1+v2` | |
| ELL | `[v1, v2, Rm]` | 焦点+主半径 |
| WED | 基 + `v+v1+v2`、`v+v3`、`v+v1+v2+v3` | |
| BOX | 基 + `v+a1+a2+a3` | 正交，对角最远 |
| RHP/HEX | 基 + `v+h` + `v±r±s±t` | 六棱柱顶点 |
| ARB | 前 24（8 顶点） | |
| GQ/SQ | 跳过（现逻辑保留） | 二次型系数非坐标 |
| X/Y/Z | 全参 | 点定义旋转体（a,r 对） |

- 保持 `max(max_coord*1.3 + 100, default)` 与 default 兜底。

**验收**：
| 测试（`tests/unit/test_preview_bound.py`，无需 FreeCAD——`freecad_preview.py` 顶层仅 stdlib） | 期望 |
| :--- | :--- |
| `shield_20m` 曲面 dict | `bound ∈ [2600, 2800]`（≈2700，非 5300） |
| `stress_bunker`（外盒 ±1500） | `bound ∈ [2000, 2100]`（≈2050） |
| `inp01`（pz 0..10000） | `bound ≈ 13100`（±5%） |
| `inp09`（±2742） | `bound ≈ 3665`（±5%） |
| 含 GQ/SQ 曲面 | 跳过，不撑 bound |
| repro 实测 | bound 输出与真实几何一致 |

**风险**：映射表漏类型 → 落入保守 default；ARB/WED/RHP 角点合成需正确（顶点=基点+向量组合）。

---

## 7. 次级项（可选，不阻塞门禁）
- **S1**：STEPS 表扩展并入 §4.2.1 `planTickStep`（随 P0b 一起交付）。
- **S2**：`_handle_preview_3d` 内函数级 `import`（tempfile/re/base64/shutil，:1004/:1040）上提模块顶部（一致性，无测试约束，仿 P1 F#3）。
- **S3**：缓存 LRU 上限抽为 `preview_cache` 构造参数（默认 3）。

---

## 8. 测试要求

### 8.1 新增大尺寸预览测试（后端）
| 文件 | 测什么 | 依赖 |
| :--- | :--- | :--- |
| `tests/unit/test_preview_bound.py` | §6.3 bound 修正：7 fixture 曲面 dict → 期望区间 | 无（freecad_preview 顶层 stdlib） |
| `tests/unit/test_preview_cache.py` | §3.3：fingerprint/put/get/evict_lru/evict_dir/命中跳过 builder | 无（preview_cache 纯 stdlib） |
| `tests/integration/test_preview3d_worker.py` | §6.2 vtk 惰性 AST 断言 | 无（读源码 ast.parse，仿 test_tech_debt） |
| `tests/integration/test_preview3d_freecad.py`（可选） | `build_geometry` 对 7 fixture 全曲面不抛、cell STL 数、base64 大小上限、缓存命中路径；**FreeCAD 不可用整文件 skip**（不算绿数） | FreeCAD 环境 |

- 后端测试统一 `python -m pytest tests/ -v`。**新增用例不改变既有 251 用例**（251 零回归为硬门禁）。

### 8.2 7 个 fixture 测试映射
| fixture | 场景 | 契约测什么 |
| :--- | :--- | :--- |
| `preview_shield_20m.inp` | 合成 ~20m（用户症状复现） | **bound 修正 5300→≈2700**；20m deck `build_geometry` 冒烟（FreeCAD 可选）；缓存命中第二次打开（repro 实测）；前端 `computeCameraParams` farNear |
| `preview_inp09_m27.inp` | 40 曲面 ±2742 ≈27m | 后端 CSG 全曲面 parse/`_pymcnp_surf_to_dict` 序列化不抛/STL 数；**bound≈3665**；base64 大小 |
| `preview_inp01_m100.inp` | ±10000 ≈100m | **前端深度精度** `computeCameraParams`（z∈[0,10000] bbox）farNear≤1e4；后端 **bound≈13100** |
| `preview_duct_conc.inp` | 真实混凝土屏蔽 | 真实 deck parse 冒烟全绿，中小尺度回归锚；bound 上界 |
| `preview_inp96.inp` | quad GQ 测试 | **vtk 惰性**（AST）+ GQ 曲面 marching cubes 路径（FreeCAD 可选集成） |
| `preview_inp08_m27.inp` | quad DBCN=29 GQ 测试 | vtk 惰性 + GQ 回归（与 inp96 互为对照） |
| `preview_stress_bunker.inp` | 30m bunker 29 个 #n 级联 | 最坏 AST 布尔级联 `build_geometry` 时长上界（repro 实测）；`resolve_cell_complements` 展开不崩；**bound≈2050**；缓存收益（实测） |

### 8.3 前端测试（vitest，需 PM 确认新 devDependency）
- **决策**：引入 `vitest` 为 `gui/` devDependency（Vite 5 原生支持，标准方案）。这与 P1"不引入新依赖"正交（本轮为性能任务，vitest 仅开发/测试，不进入 sidecar 产物）。
- **备选（PM 不批时）**：Node 内置 `node:test` + esbuild 预编译（零新依赖），但可读性/断言能力弱，不推荐。
- 测试目录 `gui/test/`：
  - `cameraParams.test.ts`（§5.3）：farNear 有界、单调有界。
  - `tickGrid.test.ts`（§4.3）：dispose==created、对象/纹理预算、`planTickStep` 不饱和。
  - `renderGate.test.ts`（§4.3）：idle 不渲染。
  - `cellMaterial.test.ts`（§4.3）：默认 opaque。
- 跑法：`cd gui && npx vitest run`（独立于 pytest 门禁，但作为施工完成复核项）。

---

## 9. 施工顺序与每步验收（分工 + 联调点）

> 分支：`git checkout -b perf/preview3d`（自 `experiment/geouned`）。

| 步 | 改动 | 施工方 | 该步验收 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | bound 修正（§6.3）+ `app/preview_cache.py`（§3.2.1）+ 后端单测（§8.1 前 3 文件） | 后端 | pytest 全绿（251 + 新增全绿）；`test_preview_bound`/`test_preview_cache`/`test_preview3d_worker` 绿 | bound 是最纯、零风险；缓存模块是 P0a 地基 |
| 2 | vtk 惰性（§6.2） | 后端 | `test_preview3d_worker.py` 绿；grep worker 顶层无 vtk | 若 worker 源码被 ast 断言抓住未改 → 打回 |
| 3 | handler 接线缓存（§3.2.2）+ `_clear_stl_session` 联动（§3.2.2）+ IPv6 前端 `api.ts`（§6.1） | 后端+前端 | pytest 全绿；grep `gui/src` localhost:5001 归零；**联调：同一 deck 第二次打开 < 1s** | 联调点 1 |
| 4 | 前端抽 4 模块（§4.2/§5.2）TickGrid/renderGate/cellMaterial/cameraParams + vitest 基建 | 前端 | `npx vitest run` 全绿；替换 Preview3D.tsx 对应段 | 纯前端，与后端无耦合 |
| 5 | 加载态（§3.2.3）+ 面板"半透明查看"开关（§4.2.3） | 前端 | 人工：fetch 有加载指示；开关切换透明/不透明 | 半透明默认值需 PM 先裁决（§10.3） |
| 6 | 收尾：repro 实测全目标 + tester 复核（pytest 全绿 + vitest 全绿 + 251 零回归 + 联调） | repro/测试 | 全目标表（§2）达成；无断言降级 | 向 PM 汇报 commit 索引 |

**联调点**：
1. `/api/preview-3d` 响应结构不变（`stl_files`/`stl_data`/`freecad`/`count`），前端只依赖既有字段，缓存透明。
2. `_STL_SESSION` 指向缓存目录后，`/api/cross-section` 复用正常（截面联调：打开 20m deck → 做截面 → 切片正常）。
3. 前端 127.0.0.1 改动只动 URL 常量，不动物理结构；Tauri 与浏览器双模式回归。

---

## 10. 边界与风险

### 10.1 边界（铁律）
1. 不碰 `app/generator/` 与 `app/generator/parsers/`（MCNP 生成/解析语义零变化）。
2. 不碰 `docs/contracts/api.yaml` 与 api_server 路由表（25 端点零变化）；preview-3d 响应逐字段不变。
3. 测试不 import `gui.backend.api_server`（铁律）；不 import FreeCAD。
4. 复现脚本在仓库外 `D:\code\preview_measure\`，测试不依赖。
5. 不新增运行时依赖；vitest 仅 `gui/` devDependency（需 PM 确认）。

### 10.2 风险
| 风险 | 缓解 |
| :--- | :--- |
| 缓存悬挂（目录被清） | `get` 内 `isdir` 校验 + `evict_dir` 联动 |
| dirty flag 漏置 → 画面不刷新 | §4.2.2 清单逐项覆盖 + renderGate 测试 |
| 半透明默认关闭 = UX 变化 | PM 裁决默认值（§10.3） |
| 几何归一化破坏排序 | 平移先于 `computeBoundingBox`（§5.2.2 顺序） |
| bound 映射表漏类型 | 落入保守 default + fixture 区间断言 |
| vitest 引入前端构建/测试复杂度 | 独立 `gui/test/`，不并入 pytest 门禁 |

### 10.3 需 PM 裁决的开放决策
1. **半透明默认值**：P0b 建议默认 opaque（消除 overdraw）、面板提供"半透明查看"开关（默认关）。若 PM 要求默认保半透明 UX，则 overdraw 目标降级为"透明 pass 仅渲染需看穿的栅元"（实现复杂度上升），需另行评估。
2. **vitest devDependency**：建议批准；不批则降级 node:test + esbuild。
3. **冷启动目标**：≤3.0s（≥ 现状），缓存命中 ≤1.0s 为本轮核心指标；若 PM 要求冷启动 <2.0s，需增补 handler 侧增量优化（超本轮范围，另立契约）。

---

## 11. 施工完成后重锚定清单

动工前基线行号（2026-08-12 已核验）：

| 符号 | 动工前行号 |
| :--- | :--- |
| `Preview3D.tsx` 相机 near/far | :99（near=0.1 / far=viewDist*100） |
| `rebuildTicks` | :196-243 |
| `scheduleRebuild` / controls change | :249-252 / :262 |
| `loadStlMeshes`（含 material :312、reframe :334-347） | :285-349 |
| `animate` 渲染循环 | :354-383 |
| `dispose` | :426-447 |
| 前端 preview-3d fetch | :519-542（useEffect `[]`） |
| `api_server._handle_preview_3d` | :1001-1070 |
| `_STL_SESSION` / `_clear_stl_session` | :38 / :41-48 |
| server 绑定 | :1283（`0.0.0.0`） |
| CORS 头 | :541 |
| `_compute_bound_from_surfaces` | freecad_preview.py:206-225（:271 调用） |
| `build_geometry` | freecad_preview.py:243 |
| worker vtk import | _freecad_csg_worker.py:30-35（`_quadric_to_shape` :671） |
| `bin_dir` 缓存（已存在，勿改） | freecad_locator.py:164-189 |

施工完成后更新：`PROJECT_MEMORY.md`（§4 ADR + §8 变更日志）、`app/UI_ARCHITECTURE.md`（若涉及 preview-3d 链路描述）。**不影响**：`api.yaml`、`test_api_contract.py`（读路由，不读本契约改动的内部实现）。

---

## 12. 交付检查清单
- [ ] `_compute_bound_from_surfaces` 按类型表修正；`test_preview_bound` 对 4+ fixture 区间断言绿
- [ ] `app/preview_cache.py` 深模块 + handler 接线 + `evict_dir` 联动；`test_preview_cache` 全绿；命中跳过 builder
- [ ] worker vtk 惰性；AST 断言绿
- [ ] 前端 `api.ts`（127.0.0.1）；grep localhost:5001 归零
- [ ] TickGrid/renderGate/cellMaterial/cameraParams 抽模块；vitest 全绿；替换 Preview3D.tsx 对应段
- [ ] 加载态 + 半透明开关（PM 裁决默认值）
- [ ] 全量 pytest = 既有 **251 绿零回归** + 新增预览测试全绿（复跑 ×2）
- [ ] vitest 全绿（`cd gui && npx vitest run`）
- [ ] repro 实测：缓存命中打开 ≤1.0s、拖动对象 ≤60/纹理 ≤30、±10000 无闪烁、IPv6 惩罚归零
- [ ] 无断言降级、无新增运行时依赖、api.yaml 零变更
- [ ] PROJECT_MEMORY.md 更新 + 向 PM 汇报 commit 索引
