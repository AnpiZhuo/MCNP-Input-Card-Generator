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

/** pointy-top 顶点朝 +X 的蜂窝格位中心（画布与阶段3共用，golden 测试锁死） */
export function hexCenter(col: number, row: number, pitch: number): { x: number; y: number } {
  return {
    x: col * pitch + (row % 2) * (pitch / 2),
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

/** 六棱柱格位（矩形交错蜂窝，MCNP hex fill 为 (i,j,k) 矩形盒；环形蜂窝由 void 角位构成） */
export function hexGrid(dims: number[], pitch: number): HexCell[] {
  const cols = Math.max(1, dims[0] ?? 1);
  const rows = Math.max(1, dims[1] ?? 1);
  const layers = Math.max(1, dims[2] ?? 1);
  const out: HexCell[] = [];
  for (let k = 0; k < layers; k++) {
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        const idx = i + cols * (j + rows * k);
        const c = hexCenter(i, j, pitch);
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

/* ── 尺寸 / 范围 / raw 派生 ───────────────────────────────── */

/** 由 dims 派生 MCNP 范围 token：dims=[17,17,1] → ["0:16","0:16","0:0"] */
export function rangeFromDims(dims: number[]): string[] {
  return dims.map((d) => `0:${Math.max(0, d - 1)}`);
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

/** 初始环形蜂窝：菱形角位（蜂窝环外）填 "0"（void），环内填 defaultU */
export function initialHexCells(rings: number, layers: number, defaultU: string): FillGridCellJson[] {
  const cols = 2 * rings + 1;
  const rowLens = hexRingRows(rings);
  const cells: FillGridCellJson[] = [];
  for (let k = 0; k < layers; k++) {
    for (let j = 0; j < cols; j++) {
      for (let i = 0; i < cols; i++) {
        cells.push({ u: i < rowLens[j] ? defaultU : "0", dx: "", dy: "", dz: "" });
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
    let maxX = 0;
    let maxY = 0;
    for (const c of cells) {
      maxX = Math.max(maxX, c.x);
      maxY = Math.max(maxY, c.y);
    }
    return {
      x: maxX + pitch / 2,
      y: maxY + pitch * (Math.sqrt(3) / 2),
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
    for (const deg of [30, 90, 150, 210, 270, 330]) {
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
