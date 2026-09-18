/**
 * contour — 标量场 → **等值线矢量路径**（marching squares）。
 *
 * ## 为什么需要它（而不是继续用"每体素一个方块"）
 * 旧的 `sliceToSvg` 给每个体素画一个 `<rect>`：128² 切面就是 16 384 个矩形，
 * 文件十几 MB、在 Word/Illustrator 里卡死，而且放大后仍是**马赛克** ——
 * 它只是"可缩放的位图"，不含等值线。要真矢量就得提轮廓。
 *
 * ## 实现取舍
 * - 16 种 case 的线段表照搬后端已有的 `app/analytic_slice.py`（同一套拓扑约定，
 *   前后端看同一张图不会出现"轮廓不一致"）；后端那份是**二值**（栅元内外），
 *   这里升级成**标量 + 线性插值**（等值线要落在真实数值位置上，不能只取边中点）。
 * - **共享边必须规范化**：同一条网格边无论从哪个相邻 cell 看，都必须是同一个插值点。
 *   若按各自 cell 从顶点插值，浮点尾差会让端点哈希不上、闭合环串不成环
 *   （实测：金字塔场断成碎片）。所以点位按「边 id」缓存，只插值一次。
 * - 串链用端点哈希贪心：等值线是给人看的，断成几段视觉上无差别，
 *   写全局最优欧拉路径在这个规模上收益低、出错面大。
 * - 全程纯函数、零 DOM：可在 vitest 里直接断言几何，不必起画布。
 */

/** 顶点：0=(0,0) 1=(1,0) 2=(1,1) 3=(0,1)；边：0=下 1=右 2=上 3=左 */
const MS_TABLE: number[][][] = [
  [], [[0, 3]], [[0, 1]], [[1, 3]],
  [[1, 2]], [[0, 3], [1, 2]], [[0, 2]], [[2, 3]],
  [[2, 3]], [[0, 2]], [[0, 1], [2, 3]], [[1, 2]],
  [[1, 3]], [[0, 1]], [[0, 3]], [],
];

export interface ContourPath {
  /** 路径点（列,行 的浮点坐标，与切面像素坐标同系） */
  points: [number, number][];
  /** 是否为闭合环 */
  closed: boolean;
}

/** 场值采样器：(col,row) → 标量（行主序栅格，宽 w 高 h） */
export interface ScalarField {
  width: number;
  height: number;
  at: (col: number, row: number) => number;
}

/** 从一维数组构造标量场（行主序：idx = row*width + col） */
export function fieldFromArray(data: ArrayLike<number>, width: number, height: number): ScalarField {
  return { width, height, at: (c, r) => data[r * width + c] };
}

/**
 * 从 8-bit 量化帧 + 源值域构造标量场（切面用）。
 *
 * 帧是 `u8 ∈ [0,255]`，真值 `f = u8*(max-min)/255 + min` —— 与 `sliceExport.bytesToFloat`
 * 同一口径（**不然等值线标注的数值会和屏幕上对不上**）。
 */
export function fieldFromQuantized(bytes: ArrayLike<number>, width: number, height: number, min: number, max: number): ScalarField {
  const span = (max - min) / 255;
  return { width, height, at: (c, r) => bytes[r * width + c] * span + min };
}

/* ── 规范化边 id（同一条边只有一个 id，插值点只算一次） ── */
type EdgeRef = string;
const hEdge = (c: number, r: number): EdgeRef => `h${c},${r}`; // 水平边：(c,r)—(c+1,r)
const vEdge = (c: number, r: number): EdgeRef => `v${c},${r}`; // 垂直边：(c,r)—(c,r+1)

/** cell 的四条边（顺序与 MS_TABLE 的边编号一致：下/右/上/左） */
function cellEdges(c: number, r: number): [EdgeRef, EdgeRef, EdgeRef, EdgeRef] {
  return [hEdge(c, r), vEdge(c + 1, r), hEdge(c, r + 1), vEdge(c, r)];
}

/** 边的两个端点坐标（插值用；口径与边 id 严格一致） */
function edgeVertices(e: EdgeRef): [[number, number], [number, number]] {
  const horiz = e[0] === "h";
  const [a, b] = e.slice(1).split(",").map(Number);
  return horiz ? [[a, b], [a + 1, b]] : [[a, b], [a, b + 1]];
}

/** 点位注册表：规范边 id → 量化后的 (x,y) */
export type EdgePointRegistry = Map<EdgeRef, [number, number]>;

/** 线性插值位置（0..1）；两端相等时取中点，避免除零 */
function frac(a: number, b: number, level: number): number {
  const d = b - a;
  if (Math.abs(d) < 1e-12) return 0.5;
  const t = (level - a) / d;
  return t < 0 ? 0 : t > 1 ? 1 : t;
}

function round4(v: number): number {
  return Math.round(v * 1e4) / 1e4;
}

/** 端点量化键（1e-4 网格）：浮点坐标要能"接上"必须量化 */
function key(x: number, y: number): string {
  return `${Math.round(x * 1e4)}:${Math.round(y * 1e4)}`;
}

/**
 * 鞍点消歧（marching squares 的标准做法，**闭合环能不能串成全靠它**）。
 *
 * case 5（{0,2}）与 case 10（{1,3}）的对角情形有两种配对方式；若各 cell 各配各的，
 * 同一条等值线会在共享边处出现"分叉"，端点点度数 > 2，贪心串链就断成碎片
 * （实测：金字塔场里本该是闭合圆的等值线断成多段）。
 * 用**格心值**做唯一判据（同一格心值 ⇒ 同一配对），相邻 cell 的配对自然相容。
 */
function pairForCase(code: number, center: number, level: number): number[][] {
  if (code === 5) {
    return center >= level ? [[0, 3], [1, 2]] : [[0, 1], [2, 3]];
  }
  if (code === 10) {
    return center >= level ? [[0, 1], [2, 3]] : [[0, 3], [1, 2]];
  }
  return MS_TABLE[code];
}

/**
 * 提取某个等值面的**线段集合**（未串链）。
 *
 * @param level 等值（标量值）
 * @param reg 可选：外部点位注册表（跨多条等值线复用）
 */
export function contourSegments(field: ScalarField, level: number, reg?: EdgePointRegistry): [number, number, number, number][] {
  const { width: w, height: h } = field;
  const segs: [number, number, number, number][] = [];
  if (w < 2 || h < 2) return segs;
  const v = (c: number, r: number) => field.at(c, r);
  const registry: EdgePointRegistry = reg ?? new Map();

  const pointOf = (e: EdgeRef): [number, number] => {
    const cached = registry.get(e);
    if (cached) return cached;
    const [[x1, y1], [x2, y2]] = edgeVertices(e);
    const t = frac(v(x1, y1), v(x2, y2), level);
    const p: [number, number] = [round4(x1 + (x2 - x1) * t), round4(y1 + (y2 - y1) * t)];
    registry.set(e, p);
    return p;
  };

  for (let r = 0; r < h - 1; r++) {
    for (let c = 0; c < w - 1; c++) {
      const v0 = v(c, r), v1 = v(c + 1, r), v2 = v(c + 1, r + 1), v3 = v(c, r + 1);
      let code = 0;
      if (v0 >= level) code |= 1;
      if (v1 >= level) code |= 2;
      if (v2 >= level) code |= 4;
      if (v3 >= level) code |= 8;
      if (code === 0 || code === 15) continue;
      const center = (v0 + v1 + v2 + v3) / 4;
      const table = pairForCase(code, center, level);
      if (!table.length) continue;
      const e = cellEdges(c, r);
      for (const [e1, e2] of table) {
        const p1 = pointOf(e[e1]);
        const p2 = pointOf(e[e2]);
        segs.push([p1[0], p1[1], p2[0], p2[1]]);
      }
    }
  }
  return segs;
}

/**
 * 把线段串成折线（端点哈希贪心）。
 *
 * 不追求把每一条都串到最优：等值线是给人看的，**断成几段在视觉上无差别**，
 * 而写一个全局最优的图遍历（欧拉路径）在这个规模上收益很低、出错面更大。
 */
export function joinSegments(segs: [number, number, number, number][]): ContourPath[] {
  if (!segs.length) return [];
  const byKey = new Map<string, number[]>();
  segs.forEach((s, i) => {
    for (const k of [key(s[0], s[1]), key(s[2], s[3])]) {
      const list = byKey.get(k);
      if (list) list.push(i);
      else byKey.set(k, [i]);
    }
  });
  const used = new Array<boolean>(segs.length).fill(false);
  const paths: ContourPath[] = [];

  for (let i = 0; i < segs.length; i++) {
    if (used[i]) continue;
    used[i] = true;
    const pts: [number, number][] = [[segs[i][0], segs[i][1]], [segs[i][2], segs[i][3]]];
    // 两端各自向前延伸
    for (const end of ["tail", "head"] as const) {
      for (;;) {
        const tip = end === "tail" ? pts[pts.length - 1] : pts[0];
        const cands = byKey.get(key(tip[0], tip[1])) || [];
        const next = cands.find((j) => !used[j]);
        if (next === undefined) break;
        used[next] = true;
        const s = segs[next];
        const tipIsStart = key(s[0], s[1]) === key(tip[0], tip[1]);
        const other: [number, number] = tipIsStart ? [s[2], s[3]] : [s[0], s[1]];
        if (end === "tail") pts.push(other);
        else pts.unshift(other);
      }
    }
    const closed = pts.length > 3 && key(pts[0][0], pts[0][1]) === key(pts[pts.length - 1][0], pts[pts.length - 1][1]);
    paths.push({ points: pts, closed });
  }
  return paths;
}

export interface ContourOptions {
  /** 等值线条数（按值域等距切），默认 8 */
  levels?: number;
  /** 每个像素放大倍数（与位图底图的缩放一致），默认 2 */
  cell?: number;
  /** 线宽（px），默认 1 */
  strokeWidth?: number;
  color?: string;
  /** 低于该值的等值线不画（与色阶显示阈值一致） */
  minValue?: number;
  /** 线不透明度，默认 0.75 */
  opacity?: number;
}

/**
 * 标量场 → 等值线 SVG 片段（`<path>` 集合，透明底、不含位图）。
 * 返回的是一段 SVG 内容（不含 `<svg>` 外壳），便于直接内联进出图版面。
 */
export function contourSvgPath(field: ScalarField, min: number, max: number, opts: ContourOptions = {}): string {
  const levels = Math.max(1, opts.levels ?? 8);
  const cell = opts.cell ?? 2;
  const stroke = opts.strokeWidth ?? 1;
  const color = opts.color ?? "#222222";
  const opacity = opts.opacity ?? 0.75;
  const lo = opts.minValue ?? min;
  if (!(max > min)) return "";
  const out: string[] = [];
  for (let i = 1; i <= levels; i++) {
    const level = min + ((max - min) * i) / (levels + 1);
    if (level < lo) continue;
    const paths = joinSegments(contourSegments(field, level));
    for (const p of paths) {
      if (p.points.length < 2) continue;
      const d = p.points
        .map(([x, y], idx) => `${idx === 0 ? "M" : "L"}${round2(x * cell)},${round2(y * cell)}`)
        .join(" ") + (p.closed ? " Z" : "");
      out.push(`<path d="${d}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-opacity="${opacity}"/>`);
    }
  }
  return out.join("");
}

function round2(v: number): number {
  return Math.round(v * 100) / 100;
}
