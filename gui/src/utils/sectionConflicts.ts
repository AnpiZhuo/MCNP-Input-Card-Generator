/**
 * sectionConflicts — 截面上的「重叠区」检测（纯函数，深模块）。
 *
 * ## 只标重叠，不标空白（2026-10-08 用户裁决）
 * 用户原话：**「空腔就应该是空的」**。
 * 上一版把「不属于任何栅元、且被材料围住」的空白也标成"空隙"（橙色点纹），结果在用户的卡上
 * 正好把中间那个**本该是空的空腔**涂上了标记 ⇒ 用户看到的是"空腔里有个莫名其妙的东西、
 * 悬停又没读数"。**空腔不是异常**；无栅元的空白也不是可判定的错误（在本项目这种没有外层栅元的
 * 模型里，平面上大面积空白本来就是常态）⇒ 一律留空：不画、不计数、不提示。
 *
 * 真正可判定的违反只有一条：**同一点被 ≥2 个栅元同时认领**（重叠）。
 * MCNP 自己的口径（C810 §3.H "Geometry Errors"）正是这条：
 * *"MCNP cannot detect overlapping cells or gaps between cells until a particle track
 * actually gets lost."*；几何绘图里 *"…is drawn as a dashed line if there is not exactly
 * one cell on each side of the surface at each point."*
 * 另：「该平面上这个栅元到底在不在」由后端**按定义**判定（`app/section_region.py`），
 * 界面把它的 `warnings` 原样显示出来解释，而不是靠涂色去猜。
 *
 * ## 实现与精度
 * 栅格采样 + 扫描线奇偶填充 → 计数栅格 → 重叠掩码 → marching squares 取轮廓。
 * **这是采样估计**：轮廓位置误差 ≤ 一个栅格步长（较长边默认分 240 份），面积同量级
 * —— 界面上按"估计值"表述，不写成精确值。
 */

export type P2 = { x: number; y: number };

export interface ConflictGrid {
  cols: number;
  rows: number;
  minX: number;
  minY: number;
  dx: number;
  dy: number;
}

export interface SectionConflicts {
  grid: ConflictGrid;
  /** 重叠区轮廓（用户坐标；可能多个环） */
  overlapLoops: P2[][];
  /** 重叠面积（用户坐标单位²，栅格估计） */
  overlapArea: number;
}

const DEFAULT_RES = 240;
const MAX_SAMPLES = 400_000;

/** 一个栅元的区域掩码（扫描线 + 奇偶填充；内孔自然被挖掉） */
function cellMask(loops: readonly P2[][], g: ConflictGrid): Uint8Array {
  const mask = new Uint8Array(g.cols * g.rows);
  const xs: number[] = [];
  for (let r = 0; r < g.rows; r++) {
    const y = g.minY + (r + 0.5) * g.dy;
    xs.length = 0;
    for (const lp of loops) {
      for (let i = 0, j = lp.length - 1; i < lp.length; j = i++) {
        const a = lp[i], b = lp[j];
        if ((a.y > y) !== (b.y > y)) {
          xs.push(a.x + ((y - a.y) * (b.x - a.x)) / (b.y - a.y));
        }
      }
    }
    if (xs.length < 2) continue;
    xs.sort((p, q) => p - q);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      const c0 = Math.max(0, Math.ceil((xs[k] - g.minX) / g.dx - 0.5));
      const c1 = Math.min(g.cols - 1, Math.floor((xs[k + 1] - g.minX) / g.dx - 0.5));
      for (let c = c0; c <= c1; c++) mask[r * g.cols + c] = 1;
    }
  }
  return mask;
}

/* ── 布尔掩码上的 marching squares：16 种 case → 线段 → 走环 ──
 * ⚠️ 位序必须与 EDGE_MID 的顶点约定一致（这里踩过一次坑）：本文件里 r 是 y 方向、
 * c 是 x 方向，而表约定顶点 0/1/2/3 = 左下/右下/右上/左上 ⇒ 位序为
 *   bit0=(r,c)  bit1=(r,c+1)  bit2=(r+1,c+1)  bit3=(r+1,c)
 * 写错成 (r+1,c)/(r,c+1) 的顺序时，线段端点会两两错开（实测 132 条线段里 208 个顶点
 * 度数为 1）⇒ 走不出任何闭合环。
 */
const MS_TABLE: number[][][] = [
  [], [[0, 3]], [[0, 1]], [[1, 3]], [[1, 2]], [[0, 3], [1, 2]], [[0, 2]], [[2, 3]],
  [[2, 3]], [[0, 2]], [[0, 1], [2, 3]], [[1, 2]], [[1, 3]], [[0, 1]], [[0, 3]], [],
];
const EDGE_MID: P2[] = [
  { x: 0.5, y: 0 }, { x: 1, y: 0.5 }, { x: 0.5, y: 1 }, { x: 0, y: 0.5 },
];

function collectSegments(mask: Uint8Array, g: ConflictGrid): [P2, P2][] {
  const at = (r: number, c: number) =>
    (r < 0 || c < 0 || r >= g.rows || c >= g.cols ? 0 : mask[r * g.cols + c]);
  const segs: [P2, P2][] = [];
  for (let r = 0; r + 1 < g.rows; r++) {
    for (let c = 0; c + 1 < g.cols; c++) {
      const k = at(r, c) | (at(r, c + 1) << 1) | (at(r + 1, c + 1) << 2) | (at(r + 1, c) << 3);
      if (k === 0 || k === 15) continue;
      const u0 = g.minX + c * g.dx;
      const v0 = g.minY + r * g.dy;
      for (const [e1, e2] of MS_TABLE[k]) {
        const m1 = EDGE_MID[e1], m2 = EDGE_MID[e2];
        segs.push([
          { x: u0 + m1.x * g.dx, y: v0 + m1.y * g.dy },
          { x: u0 + m2.x * g.dx, y: v0 + m2.y * g.dy },
        ]);
      }
    }
  }
  return segs;
}

/** 线段 → 闭合环（掩码是栅格数据，顶点取格边中点 ⇒ 位置误差 ≤ 半个步长） */
function loopsFromSegments(segs: [P2, P2][]): P2[][] {
  const key = (p: P2) => `${Math.round(p.x * 1e6)},${Math.round(p.y * 1e6)}`;
  const pts = new Map<string, P2>();
  const edges: [string, string][] = [];
  for (const [a, b] of segs) {
    const ka = key(a), kb = key(b);
    pts.set(ka, a);
    pts.set(kb, b);
    if (ka !== kb) edges.push([ka, kb]);
  }
  const incident = new Map<string, number[]>();
  edges.forEach(([ka, kb], id) => {
    if (!incident.has(ka)) incident.set(ka, []);
    if (!incident.has(kb)) incident.set(kb, []);
    incident.get(ka)!.push(id);
    incident.get(kb)!.push(id);
  });
  const used = new Array(edges.length).fill(false);
  const loops: P2[][] = [];
  for (let s = 0; s < edges.length; s++) {
    if (used[s]) continue;
    used[s] = true;
    const chain = [edges[s][0], edges[s][1]];
    for (;;) {
      const cur = chain[chain.length - 1];
      const nxt = (incident.get(cur) || []).find((id) => !used[id]);
      if (nxt === undefined) break;
      used[nxt] = true;
      const [ka, kb] = edges[nxt];
      chain.push(ka === cur ? kb : ka);
      if (chain[chain.length - 1] === chain[0]) break;
    }
    if (chain.length >= 4 && chain[0] === chain[chain.length - 1]) {
      chain.pop();
      loops.push(chain.map((k) => pts.get(k) as P2));
    }
  }
  return loops;
}

function maskLoops(mask: Uint8Array, g: ConflictGrid): P2[][] {
  return loopsFromSegments(collectSegments(mask, g));
}

/** @internal 仅供本模块测试用（内部缝）：掩码 → 轮廓环 */
export const __test = { cellMask, collectSegments, loopsFromSegments, maskLoops };

export function sectionConflicts(
  cells: readonly { polygons: readonly P2[][] }[],
  opts: { resolution?: number } = {},
): SectionConflicts {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const cd of cells) {
    for (const lp of cd.polygons) {
      for (const p of lp) {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
      }
    }
  }
  const empty: SectionConflicts = {
    grid: { cols: 0, rows: 0, minX: 0, minY: 0, dx: 1, dy: 1 },
    overlapLoops: [], overlapArea: 0,
  };
  if (!Number.isFinite(minX) || cells.length < 2) return empty;   // 单个栅元不可能重叠

  const spanX = Math.max(maxX - minX, 1e-9);
  const spanY = Math.max(maxY - minY, 1e-9);
  const margin = Math.max(spanX, spanY) * 0.05;
  minX -= margin; minY -= margin;
  const w = spanX + 2 * margin;
  const h = spanY + 2 * margin;
  const res = Math.max(32, Math.min(opts.resolution ?? DEFAULT_RES, 1200));
  const step = Math.max(w, h) / res;
  const cols = Math.max(3, Math.min(Math.ceil(w / step) + 1, 2000));
  const rows = Math.max(3, Math.min(Math.ceil(h / step) + 1, 2000));
  if (cols * rows > MAX_SAMPLES) return empty;
  const g: ConflictGrid = { cols, rows, minX, minY, dx: w / (cols - 1), dy: h / (rows - 1) };

  const count = new Uint8Array(cols * rows);
  for (const cd of cells) {
    const mask = cellMask(cd.polygons, g);
    for (let i = 0; i < count.length; i++) if (mask[i]) count[i]++;
  }
  const overlap = new Uint8Array(count.length);
  let overlapCells = 0;
  for (let i = 0; i < count.length; i++) {
    if (count[i] >= 2) { overlap[i] = 1; overlapCells++; }
  }
  return {
    grid: g,
    overlapLoops: overlapCells ? maskLoops(overlap, g) : [],
    overlapArea: overlapCells * g.dx * g.dy,
  };
}
