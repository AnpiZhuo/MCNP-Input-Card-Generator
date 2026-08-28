/**
 * lattice — 格阵 FILL 前端深模块（TS 镜像 app/lattice.py）。
 *
 * 只含纯函数与类型（无 React 依赖），键名与 Python FillGrid.to_json 逐字一致：
 *   { lat, kind, range, dims, cells:[{u,dx,dy,dz}], raw }
 *
 * 供 LatticeEditDialog / LatticeCanvas / LatticePreview3D / GeometryTab 消费；
 * rectGrid/hexRingRows/hexCenter 与后端 golden 测试共用同一权威数据集
 * （gui/src/utils/__golden__/latticeGolden.json）。
 */
import { apiUrl } from "./api";

/* ── 数据模型（镜像 Python FillEntry / FillGrid）────────────────── */

export interface FillGridCellJson {
  u: string;
  dx: string;
  dy: string;
  dz: string;
}

export interface FillGridJson {
  lat: string;              // "1" | "2" | ""
  kind: string;             // "lattice" | "translated"
  range: string[];          // 范围 token，如 ["0:16","0:16","0:0"]
  dims: number[];           // 每轴格数，如 [17,17,1]
  cells: FillGridCellJson[]; // 行主序（i 最快）
  raw: string;              // FILL= 之后原始 token 流（round-trip 兜底）
}

/** 脏 JSON → null（镜像 Python FillGrid.from_json 的健壮性） */
export function parseFillGrid(jsonStr: string): FillGridJson | null {
  if (!jsonStr) return null;
  let d: any;
  try {
    d = JSON.parse(jsonStr);
  } catch {
    return null;
  }
  if (typeof d !== "object" || d === null || Array.isArray(d)) return null;
  const cells: FillGridCellJson[] = [];
  const srcCells = Array.isArray(d.cells) ? d.cells : [];
  for (const c of srcCells) {
    if (typeof c === "object" && c !== null) {
      cells.push({
        u: String(c.u ?? ""),
        dx: String(c.dx ?? ""),
        dy: String(c.dy ?? ""),
        dz: String(c.dz ?? ""),
      });
    }
  }
  return {
    lat: String(d.lat ?? ""),
    kind: String(d.kind ?? "lattice"),
    range: Array.isArray(d.range) ? d.range.map((r: any) => String(r)) : [],
    dims: Array.isArray(d.dims)
      ? d.dims
          .map((x: any) => parseInt(String(x), 10))
          .filter((x: number) => Number.isFinite(x) && x >= 0)
      : [],
    cells,
    raw: String(d.raw ?? ""),
  };
}

/** 序列化（to_json 镜像）：键序 lat/kind/range/dims/cells/raw 与 Python 一致 */
export function serializeFillGrid(fg: FillGridJson): string {
  return JSON.stringify({
    lat: fg.lat,
    kind: fg.kind,
    range: fg.range,
    dims: fg.dims,
    cells: fg.cells.map((c) => ({ u: c.u, dx: c.dx, dy: c.dy, dz: c.dz })),
    raw: fg.raw,
  });
}

/* ── 矩形（lat=1）网格 ─────────────────────────────────────── */

export interface RectGrid {
  dims: number[];
  count: number;
  /** (i,j,k) → 行主序扁平 idx（i 最快）：idx = i + dims[0]*(j + dims[1]*k) */
  idxOf: (i: number, j: number, k: number) => number;
  /** idx → (i,j,k)（逆映射） */
  coordsOf: (idx: number) => [number, number, number];
}

export function rectGrid(dims: number[]): RectGrid {
  const d0 = Math.max(1, dims[0] ?? 1);
  const d1 = Math.max(1, dims[1] ?? 1);
  const d2 = Math.max(1, dims[2] ?? 1);
  const count = d0 * d1 * d2;
  return {
    dims: [d0, d1, d2],
    count,
    idxOf: (i: number, j: number, k: number) => i + d0 * (j + d1 * k),
    coordsOf: (idx: number): [number, number, number] => [
      idx % d0,
      Math.floor(idx / d0) % d1,
      Math.floor(idx / (d0 * d1)),
    ],
  };
}

/* ── 六棱柱（lat=2）蜂窝 ───────────────────────────────────── */

/** 蜂窝环行长度：rings=1 → [2,3,2]，总和 = 1+3·rings·(rings+1)（画布与阶段3共用权威） */
export function hexRingRows(rings: number): number[] {
  const rows: number[] = [];
  for (let j = 0; j <= 2 * rings; j++) {
    rows.push(rings + 1 + Math.min(j, 2 * rings - j));
  }
  return rows;
}

/** 蜂窝总格数：1+3r(r+1)（与 hexRingRows 总和一致） */
export function hexRingCellCount(rings: number): number {
  return 1 + 3 * rings * (rings + 1);
}

/**
 * 顶点朝 +X（flat-top）蜂窝格位中心（画布 / LatticePreview3D / latticeInstances 共用，
 * golden 锁死——跨语言 L1，权威公式不可改）：
 *   x = i·(pitch·√3/2)  （列水平步距）
 *   y = j·pitch + (i%2)·(pitch/2)  （行垂直步距 pitch，奇数列下移半格）
 * 自洽核验：相邻 (0,0)→(1,0) 距=p、相邻 (0,0)→(0,1) 距=√((p/2)²+(p·√3/2)²)=p。
 */
export function hexCenter(col: number, row: number, pitch: number): { x: number; y: number } {
  // MCNP LAT=2（交叉验证自官方库 u233-comp-therm-001-case-6.i，flat-top 基向量
  // a1=(2a,0)、a2=(a,a√3)）：x=(col+row/2)·pitch, y=row·pitch·√3/2
  return {
    x: col * pitch + row * (pitch / 2),
    y: row * pitch * (Math.sqrt(3) / 2),
  };
}

export interface HexCell {
  idx: number;   // 填充序（行主序，i 最快；与 FillGridJson.cells 下标对齐）
  col: number;
  row: number;
  layer: number;
  x: number;
  y: number;
}

/** 六棱柱格位（矩形交错蜂窝，MCNP hex fill 为 (i,j,k) 矩形盒；环形蜂窝由 void 角位构成）。
 *  居中：与后端 expand_positions 的 hex 分支一致，用 (i-(cols-1)/2, j-(rows-1)/2) 偏移
 *  使格阵几何中心落在原点（MCNP LAT=2 的 -N:N 对称索引以此中心为原点）。 */
export function hexGrid(dims: number[], pitch: number): HexCell[] {
  const cols = Math.max(1, dims[0] ?? 1);
  const rows = Math.max(1, dims[1] ?? 1);
  const layers = Math.max(1, dims[2] ?? 1);
  const out: HexCell[] = [];
  for (let k = 0; k < layers; k++) {
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        const idx = i + cols * (j + rows * k);
        const c = hexCenter(i - (cols - 1) / 2, j - (rows - 1) / 2, pitch);
        out.push({ idx, col: i, row: j, layer: k, x: c.x, y: c.y });
      }
    }
  }
  return out;
}

/* ── 宇宙调色板 ──────────────────────────────────────────── */

/** 12 色板：u 数值升序分配（dataviz 校验分类色板 8 槽 + 4 扩增色相） */
export const UNIVERSE_PALETTE_12: string[] = [
  "#4c9fe8", // 1 blue
  "#f08c3a", // 2 orange
  "#1fae8f", // 3 teal
  "#e0b21e", // 4 yellow
  "#d95f9b", // 5 magenta
  "#2e8b3d", // 6 green
  "#7d6bd8", // 7 violet
  "#d84040", // 8 red
  "#35b3cf", // 9 cyan
  "#9a6a38", // 10 brown
  "#6a7d9e", // 11 slate
  "#7a8f2b", // 12 olive
];

/** 未命中回退灰（u 不在色板） */
export const UNIVERSE_GRAY = "#9a9a9a";

/**
 * 构建宇宙→颜色映射：u 数值升序，从 12 色板依序取色。
 * 空串 / "0"（void）不占色板（void 由画布特判渲染为透明）。
 */
export function buildUniversePalette(us: (string | number)[]): Record<string, string> {
  const uniq = Array.from(new Set(us.map((u) => String(u))));
  uniq.sort((a, b) => Number(a) - Number(b));
  const palette: Record<string, string> = {};
  let rank = 0;
  for (const u of uniq) {
    if (!u || u === "0") continue;
    palette[u] = UNIVERSE_PALETTE_12[rank % UNIVERSE_PALETTE_12.length];
    rank++;
  }
  return palette;
}

/** 取宇宙色；未命中回退灰 */
export function getUniverseColor(u: string | number, palette: Record<string, string>): string {
  const key = String(u);
  return palette[key] ?? UNIVERSE_GRAY;
}

/* ── 调色板来源合并（项 7）──────────────────────────────── */

/** 调色板输入 cell 的最小形状（deck 栅元或 fill_grid 宿主） */
export interface LatticeCellLike {
  u?: string;
  fill_grid?: string;
}

/**
 * 调色板宇宙来源合并三路（项 7 权威契约）：
 *   void "0" 恒在首位 ∪ deck cells 的 u= 去重（排除空/void）∪ 各格阵 cell 的
 *   fill_grid JSON cells[].u 去重，数值升序。fill_grid 脏 JSON 容错（parseFillGrid 兜底）。
 */
export function collectFillUniverses(cells: LatticeCellLike[]): string[] {
  const set = new Set<string>(["0"]);
  for (const c of cells) {
    const u = (c.u ?? "").trim();
    if (u && u !== "0") set.add(u);
    const fg = parseFillGrid(c.fill_grid ?? "");
    if (fg) {
      for (const gc of fg.cells) {
        const gu = (gc.u ?? "").trim();
        if (gu) set.add(gu);
      }
    }
  }
  return Array.from(set).sort((a, b) => Number(a) - Number(b));
}

/* ── 尺寸 / 范围 / raw 派生 ───────────────────────────────── */

/** 由 dims 派生 MCNP 范围 token：dims=[17,17,1] → ["0:16","0:16","0:0"] */
export function rangeFromDims(dims: number[]): string[] {
  return dims.map((d) => `0:${Math.max(0, d - 1)}`);
}

/**
 * 方向块数（负/正复制块数）→ MCNP 范围 token "-L:R"（跨语言 L3）。
 * dims = L+R+1；`0:16` = L=0,R=16 角起；`-8:8` = L=8,R=8 居中。
 */
export function rangeFromDirCounts(neg: number, pos: number): string {
  return `${-neg}:${pos}`;
}

/** 反派生：token "a:b" → {neg: L=-a, pos: R=b, dims: b-a+1}；非法 token 兜底 {0,0,1} */
export function dirCountsFromRange(token: string): { neg: number; pos: number; dims: number } {
  const m = token.trim().match(/^(-?\d+):(-?\d+)$/);
  if (!m) return { neg: 0, pos: 0, dims: 1 };
  const a = parseInt(m[1], 10);
  const b = parseInt(m[2], 10);
  const neg = -a;
  return { neg: neg === 0 ? 0 : neg, pos: b, dims: b - a + 1 };
}

/** 初始矩形格阵：全部格位填 defaultU（k 层，行主序） */
export function initialRectCells(cols: number, rows: number, layers: number, defaultU: string): FillGridCellJson[] {
  const cells: FillGridCellJson[] = [];
  for (let k = 0; k < layers; k++) {
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        cells.push({ u: defaultU, dx: "", dy: "", dz: "" });
      }
    }
  }
  return cells;
}

/**
 * 蜂窝环内判定（flat-top 顶点+X）：cell (col,row) 是否在半径 rings 六边形内。
 * 中心坐标 i=col−rings, j=row−rings；hex 距离 = max(|i|,|j|,|i+j|)（与
 * hexRingRows 的 +30° 共线方向环行长一致，总和 1+3r(r+1)）。
 */
export function inHexRing(col: number, row: number, rings: number): boolean {
  const i = col - rings;
  const j = row - rings;
  return Math.max(Math.abs(i), Math.abs(j), Math.abs(i + j)) <= rings;
}

/** 初始环形蜂窝：六边形环外角位（inHexRing=false）填 "0"（void），环内填 defaultU */
export function initialHexCells(rings: number, layers: number, defaultU: string): FillGridCellJson[] {
  const cols = 2 * rings + 1;
  const cells: FillGridCellJson[] = [];
  for (let k = 0; k < layers; k++) {
    for (let j = 0; j < cols; j++) {
      for (let i = 0; i < cols; i++) {
        cells.push({ u: inHexRing(i, j, rings) ? defaultU : "0", dx: "", dy: "", dz: "" });
      }
    }
  }
  return cells;
}

/** cells 反算覆盖 raw：range token + 每格 u（含 (dx dy dz) 偏移） */
export function cellsToRaw(fg: FillGridJson): string {
  const tokens: string[] = [...fg.range];
  for (const c of fg.cells) {
    if (c.dx || c.dy || c.dz) tokens.push(`${c.u} (${c.dx} ${c.dy} ${c.dz})`);
    else tokens.push(c.u);
  }
  return tokens.join(" ");
}

/**
 * 条目流 ≠ dims 乘积 → 非阻塞警告文案（parse_fill_entries 会静默截断/补 0，
 * QA 建议：画布给用户提示）。匹配时返回 null。
 */
export function latticeMismatchMessage(dims: number[], cells: unknown[]): string | null {
  const product = dims.reduce((a, b) => a * b, 1);
  if (product > 0 && cells.length !== product) {
    return `条目数与格阵尺寸不匹配，已按 ${dims.join("×")} 截断/补 0`;
  }
  return null;
}

/**
 * nR 压缩（项 12，跨语言 L8）：连续重复 run → `u nR` 回缩（nR=前一条目再重复 n 次语义，
 * 与 parse_fill_entries 一致）。幂等不动点：压缩流 → parse 展开 → cells 相等 → 再压缩 = 同串。
 * 仅编辑器保存路径启用（导入路径保持源 raw 原样，防 parse→gen→parse 字节漂移）。
 * 样例：["1","1","1","2","2"] → "1 2r 2 1r"。
 */
export function compressRaw(input: string | string[]): string {
  const tokens = typeof input === "string" ? input.split(/\s+/) : input;
  const out: string[] = [];
  let i = 0;
  while (i < tokens.length) {
    const t = tokens[i];
    let run = 1;
    while (i + run < tokens.length && tokens[i + run] === t) run++;
    out.push(run >= 2 ? `${t} ${run - 1}r` : t);
    i += run;
  }
  return out.join(" ");
}

/**
 * 体积告警（项 12）：serializeFillGrid 序列化长度 > 64KB 或 cells.length > 8000
 * → 保存前非阻塞提示文案；否则返回 null。
 */
export function latticeVolumeWarning(fg: FillGridJson): string | null {
  const len = serializeFillGrid(fg).length;
  if (len > 64 * 1024 || fg.cells.length > 8000) {
    return `格阵体积过大（约 ${Math.round(len / 1024)} KB），保存后工作区可能变慢`;
  }
  return null;
}

/* ── 循环嵌套检测（项 13，跨语言 L6）──────────────────────── */

/** detectFillCycle 输入 cell 的最小形状（镜像后端 sub_by_u 结构） */
export interface CycleCellLike {
  cellNum?: number | string;
  material?: string;
  fill?: string;
  fill_grid?: string;
}

export interface FillCycleResult {
  cycle: boolean;
  chain: string[];
}

/**
 * 循环嵌套检测（TS 镜像 Python detect_fill_cycle）。
 * 基于 sub_by_u fill 图：universe U 内任一 cell 的 fill_grid(lattice/translated)
 * cells[].u == V，或 fill 单值 == V（V≠"0"/""）→ 边 U→V。DFS 递归栈成员判环；
 * 命中环 → chain = stack[stack.indexOf(U):] + [U]（如 ["1","2","1"]）。
 */
export function detectFillCycle(subByU: Record<string, CycleCellLike[]>): FillCycleResult {
  const adj = new Map<string, Set<string>>();
  for (const [u, cells] of Object.entries(subByU)) {
    const targets = new Set<string>();
    for (const c of cells || []) {
      const fv = (c.fill ?? "").trim();
      if (fv && fv !== "0") targets.add(fv);
      if (c.fill_grid) {
        const fg = parseFillGrid(c.fill_grid);
        if (fg && (fg.kind === "lattice" || fg.kind === "translated")) {
          for (const gc of fg.cells) {
            const gu = (gc.u ?? "").trim();
            if (gu) targets.add(gu);
          }
        }
      }
    }
    if (targets.size) adj.set(u, targets);
  }
  const state = new Map<string, "visiting" | "done">();
  const stack: string[] = [];
  let chain: string[] = [];
  let found = false;
  const dfs = (u: string) => {
    if (found) return;
    const st = state.get(u);
    if (st === "done") return;
    if (st === "visiting") {
      const i = stack.indexOf(u);
      chain = [...stack.slice(i), u];
      found = true;
      return;
    }
    state.set(u, "visiting");
    stack.push(u);
    for (const v of adj.get(u) ?? []) {
      if (Object.prototype.hasOwnProperty.call(subByU, v)) dfs(v);
    }
    stack.pop();
    state.set(u, "done");
  };
  for (const u of Object.keys(subByU)) dfs(u);
  return { cycle: found, chain };
}

/** 格阵物理范围估算（阶段2 用单位 pitch≈1；阶段3 由 surface_expr 提供真实格距） */
export interface LatticeExtent {
  x: number;
  y: number;
  z: number;
}

export function estimateLatticeExtent(fg: FillGridJson | null): LatticeExtent {
  if (!fg) return { x: 0, y: 0, z: 0 };
  if (fg.kind === "translated") return { x: 1, y: 1, z: 1 };
  const dims = fg.dims;
  if (!dims.length) return { x: 0, y: 0, z: 0 };
  if (fg.lat === "2") {
    const pitch = 1;
    const cells = hexGrid(dims, pitch);
    // 外沿取跨度（max-min），不依赖格阵绝对位置（居中/未居中 span 相同）
    let minX = 0, maxX = 0, minY = 0, maxY = 0;
    for (const c of cells) {
      if (c.x < minX) minX = c.x;
      if (c.x > maxX) maxX = c.x;
      if (c.y < minY) minY = c.y;
      if (c.y > maxY) maxY = c.y;
    }
    // 顶点+X 蜂窝：格元半宽 = pitch/√3（顶点-顶点宽 2pitch/√3），半高 = pitch/2（flat-flat 高 pitch）
    return {
      x: (maxX - minX) + pitch / Math.sqrt(3),
      y: (maxY - minY) + pitch / 2,
      z: Math.max(1, dims[2] ?? 1),
    };
  }
  return { x: Math.max(1, dims[0] ?? 1), y: Math.max(1, dims[1] ?? 1), z: Math.max(1, dims[2] ?? 1) };
}

/**
 * 曲面卡最大曲面号（自动生成平面时从既有曲面卡找编号顺延）。
 */
export function maxSurfaceNumber(surfacesText: string): number {
  let max = 0;
  for (const line of surfacesText.split("\n")) {
    const m = line.match(/^\s*(\d+)\s/);
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return max;
}

export interface AutoGenParams {
  rect?: { L: number; W: number; H: number; cx: number; cy: number; cz: number };
  hex?: { side: number; H: number; cx: number; cy: number; cz: number };
}

/**
 * 自动生成格阵格元曲面：
 *   矩形(lat=1)：6 平面 PX/PY/PZ（长宽高+中心）→ 盒内 = +x0 -x1 +y0 -y1 +z0 -z1
 *   六棱柱(lat=2)：6 侧 P 平面（30/90/150/210/270/330°，pointy-top 顶点+X）+ 2 PZ 盖
 *   （外接半径 = 边长；仿 fixtures/hex_lattice.inp 平面法）
 * 生成的面卡行追加到曲面卡文本（编号从既有最大号顺延）。
 */
export function autoGenerateSurfaces(
  lat: "1" | "2",
  params: AutoGenParams,
  surfacesText: string,
): { lines: string[]; surfaceExpr: string; surfacesText: string } {
  const start = maxSurfaceNumber(surfacesText) + 1;
  const lines: string[] = [];
  const sids: number[] = [];

  if (lat === "2") {
    const p = params.hex!;
    const R = p.side; // 正六边形外接半径 = 边长
    const apo = (R * Math.sqrt(3)) / 2;
    // 面法向 0°/60°/120°/180°/240°/300°（⊥ 六条格矢方向，对齐 a1=0° 蜂窝；原 30° 序列错）
    for (const deg of [0, 60, 120, 180, 240, 300]) {
      const a = (deg * Math.PI) / 180;
      const nx = Number(Math.cos(a).toFixed(6));
      const ny = Number(Math.sin(a).toFixed(6));
      const D = Number(-(nx * p.cx + ny * p.cy) - apo).toFixed(6);
      const n = start + lines.length;
      lines.push(`${n}  p   ${nx}  ${ny}  0   ${D}`);
      sids.push(n);
    }
    lines.push(`${start + 6}  pz  ${Number((p.cz + p.H / 2).toFixed(6))}`);
    lines.push(`${start + 7}  pz  ${Number((p.cz - p.H / 2).toFixed(6))}`);
    sids.push(start + 6, start + 7);
  } else {
    const p = params.rect!;
    const xs = [Number((p.cx - p.L / 2).toFixed(6)), Number((p.cx + p.L / 2).toFixed(6))];
    const ys = [Number((p.cy - p.W / 2).toFixed(6)), Number((p.cy + p.W / 2).toFixed(6))];
    const zs = [Number((p.cz - p.H / 2).toFixed(6)), Number((p.cz + p.H / 2).toFixed(6))];
    lines.push(`${start}  px  ${xs[0]}`, `${start + 1}  px  ${xs[1]}`);
    lines.push(`${start + 2}  py  ${ys[0]}`, `${start + 3}  py  ${ys[1]}`);
    lines.push(`${start + 4}  pz  ${zs[0]}`, `${start + 5}  pz  ${zs[1]}`);
    sids.push(start, start + 1, start + 2, start + 3, start + 4, start + 5);
  }

  // 六棱柱：6 侧 P 全负（外向法向内侧）+ 顶 PZ 负（z<顶）+ 底 PZ 正（z>底），一正一负（对齐 backend 校验规则）
  const surfaceExpr =
    lat === "2"
      ? `${sids.slice(0, 6).map((s) => `-${s}`).join(" ")} -${start + 6} +${start + 7}`
      : `+${sids[0]} -${sids[1]} +${sids[2]} -${sids[3]} +${sids[4]} -${sids[5]}`;
  const next = surfacesText.trim() ? `${surfacesText.trimEnd()}\n${lines.join("\n")}` : lines.join("\n");
  return { lines, surfaceExpr, surfacesText: next };
}

/** 尺寸变化时保持已涂色格位（新格位按 fresh 默认值填充） */
export function resizeLatticeCells(prev: FillGridCellJson[], fresh: FillGridCellJson[]): FillGridCellJson[] {
  return fresh.map((c, i) => (prev[i] ? { ...prev[i] } : c));
}

/* ── 宏体自动生成（项 3/4，跨语言 L4/L5）────────────────────── */

/** 3 位小数格式化（strip 尾零），对齐 RHP 卡 golden 期望值 */
function fmt3(n: number): string {
  return String(parseFloat(n.toFixed(3)));
}

/** RHP 卡参数（V=底面中心 / H=底面→顶面 / R1=轴→第一小面中点，MCNP RHP/HEX 语法） */
export interface RhpParams {
  v: [number, number, number];
  h: [number, number, number];
  r1: [number, number, number];
}

/** 渲染 RHP 卡行（无编号，形如 "rhp 0 0 -5  0 0 10  1.732 1 0"） */
export function rhpCard(p: RhpParams): string {
  return `rhp ${p.v.map(fmt3).join(" ")}  ${p.h.map(fmt3).join(" ")}  ${p.r1.map(fmt3).join(" ")}`;
}

/**
 * 模式 B：中心 + 外接半径 + 高 → RHP 参数（跨语言 L4 权威：默认轴向 +Z、
 * 第一面法向 0°（沿 a1）——hexCenter a1=(pitch,0) 邻位共享 0° 面，R1 必须 ∥ a1，
 * 否则棱柱面会切进格子（项 16 方向修正：原 30° 是几何错误）。V = C−H/2；
 * R1 = (R·cos30°, 0, 0)（R=外接半径，R1 长=apothem）。
 */
export function rhpFromCenterRadiusHeight(
  C: [number, number, number],
  R: number,
  H: number,
): RhpParams {
  return {
    v: [C[0], C[1], C[2] - H / 2],
    h: [0, 0, H],
    r1: [R * Math.cos(Math.PI / 6), 0, 0],
  };
}

/**
 * 模式 A：三点 + 高度 → RHP 参数。H = T−V；R1 = M−V（调用方校验 ⊥H / |R1|）。
 */
export function rhpFromThreePoints(
  V: [number, number, number],
  T: [number, number, number],
  M: [number, number, number],
): RhpParams {
  return {
    v: [V[0], V[1], V[2]],
    h: [T[0] - V[0], T[1] - V[1], T[2] - V[2]],
    r1: [M[0] - V[0], M[1] - V[1], M[2] - V[2]],
  };
}

/**
 * 模式 A 校验（项 4）：|T−V| 须等于高度 h；R1=M−V 须 ⊥ H。返回错误文案或 null。
 */
export function rhpModeAError(
  V: [number, number, number],
  T: [number, number, number],
  M: [number, number, number],
  h: number,
): string | null {
  const hMag = Math.hypot(T[0] - V[0], T[1] - V[1], T[2] - V[2]);
  if (Math.abs(hMag - h) > 1e-6) return `顶面与底面距离 ${hMag.toFixed(3)} ≠ 高度 ${h}`;
  const r1 = [M[0] - V[0], M[1] - V[1], M[2] - V[2]];
  const dot = (T[0] - V[0]) * r1[0] + (T[1] - V[1]) * r1[1] + (T[2] - V[2]) * r1[2];
  if (hMag > 1e-12 && Math.abs(dot) / hMag > 1e-4) return "第一小面中点矢量 R1 不垂直于轴向 H";
  return null;
}

/**
 * 六棱柱外接半径建议（项 16）：给定 i/j 格矢范围（负/正层数）与格距 pitch，返回恰好
 * 包住全部格位（fill 平行四边形）的 RHP 外接半径。格位中心 = i·a1 + j·a2
 * （a1=(pitch,0), a2=(pitch/2,√3·pitch/2)），R = max 四角 |中心| + 单格外接半径(pitch/√3)。
 */
export function hexPrismCircumradius(iNeg: number, iPos: number, jNeg: number, jPos: number, pitch: number): number {
  const c = Math.sqrt(3) / 2;
  let maxD = 0;
  for (const i of [iNeg, iPos]) {
    for (const j of [jNeg, jPos]) {
      const x = i * pitch + (j * pitch) / 2;
      const y = j * pitch * c;
      maxD = Math.max(maxD, Math.hypot(x, y));
    }
  }
  return maxD + pitch / Math.sqrt(3);
}

/**
 * 格距推导（项 16）：给定 RHP apothem（= 外接半径·√3/2）与 i/j 范围，求格距 pitch。
 * 面法向 0°/60°/120°（⊥ 格矢，负向对称）；格位单位中心 = (i + j/2, j·√3/2)，
 * max 面投影 + 单格半对边(0.5) → apothem。
 */
export function hexLatticePitch(apothem: number, iNeg: number, iPos: number, jNeg: number, jPos: number): number {
  if (apothem <= 0) return 1;
  const c = Math.sqrt(3) / 2;
  let maxProj = 0;
  for (const [nx, ny] of [
    [1, 0], [0.5, c], [-0.5, c],
  ] as const) {
    for (const i of [iNeg, iPos]) {
      for (const j of [jNeg, jPos]) {
        const proj = nx * (i + j / 2) + ny * (j * c);
        maxProj = Math.max(maxProj, proj);
      }
    }
  }
  return apothem / (maxProj + 0.5);
}

/**
 * 六棱柱画布格距适配（项 16）：hex 画布在给定可用宽度内完整显示全部格位。
 * 格位中心 x=(i+j/2)·pitch，跨距（pitch 单位）= (cols−1) + (rows−1)/2；加左右半格(2/√3)。
 * 返回夹在 [6, 22] 的格距 px。矩形画布固定 26px 格不参与。
 */
export function fitHexPitch(dims: number[], targetWidth: number): number {
  const cols = Math.max(1, dims[0] ?? 1);
  const rows = Math.max(1, dims[1] ?? 1);
  const spanUnits = cols - 1 + (rows - 1) / 2;
  const widthUnits = spanUnits + 2 / Math.sqrt(3);
  const p = targetWidth / widthUnits;
  return Math.max(6, Math.min(22, p));
}

export interface MacrobodyResult {
  /** 单个宏体卡行（含编号，如 "6 rpp -10 10 -10 10 -5 5"） */
  line: string;
  /** 格元表达式（"-6"） */
  surfaceExpr: string;
  /** 追加后的曲面卡文本 */
  surfacesText: string;
  /** 宏体类型 + 参数（无编号，如 "rpp -10 10 -10 10 -5 5"） */
  card: string;
}

/**
 * 自动生成宏体卡（项 3 权威公式，跨语言 L4）：
 *   rect(lat=1) → 单个 RPP：xmin=cx−L/2 … zmax=cz+H/2，expr="−<num>"
 *   hex(lat=2)  → 单个 RHP：R1 = ((side/2)·cos30°, (side/2)·sin30°, 0)（side = 对边宽/flat-flat）
 * 编号 maxSurfaceNumber+1 顺延。旧六面体/6P 平面路径迁为「手动」可选项。
 */
export function autoGenMacrobody(
  lat: "1" | "2",
  params: AutoGenParams,
  surfacesText: string,
): MacrobodyResult {
  const n = maxSurfaceNumber(surfacesText) + 1;
  const card =
    lat === "2"
      ? rhpCard(rhpFromCenterRadiusHeight([params.hex!.cx, params.hex!.cy, params.hex!.cz], params.hex!.side / 2, params.hex!.H))
      : (() => {
          const p = params.rect!;
          return `rpp ${fmt3(p.cx - p.L / 2)} ${fmt3(p.cx + p.L / 2)} ${fmt3(p.cy - p.W / 2)} ${fmt3(p.cy + p.W / 2)} ${fmt3(p.cz - p.H / 2)} ${fmt3(p.cz + p.H / 2)}`;
        })();
  const line = `${n} ${card}`;
  const surfaceExpr = `-${n}`;
  const next = surfacesText.trim() ? `${surfacesText.trimEnd()}\n${line}` : line;
  return { line, surfaceExpr, surfacesText: next, card };
}

/* ── 后端曲面校验（阶段2 后端提供 /api/validate-lattice-surfaces）── */

export interface ValidateLatticeResult {
  ok: boolean;
  msg: string;
}

/** 曲面校验：失焦调用；后端不可达时返回非 ok 提示（不阻断流程） */
export async function validateLatticeSurfaces(
  surfaceExpr: string,
  lat: string,
  surfacesText = "",
): Promise<ValidateLatticeResult> {
  try {
    const r = await fetch(apiUrl("/api/validate-lattice-surfaces"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surface_expr: surfaceExpr, lat, surfaces_text: surfacesText }),
    });
    const j = await r.json();
    return { ok: !!j.ok, msg: String(j.msg ?? "") };
  } catch {
    return { ok: false, msg: "无法连接后端校验曲面" };
  }
}
