/**
 * 快捷建栅元 — 纯函数深模块（vitest 可测，零依赖）
 *
 * 在几何标签页「曲面卡 & TR 变换」一键生成体：
 * - RCC 圆柱：底面中心 + 轴向向量 + 半径，切 N 个等距圆环 × M 个等距轴段
 * - RPP 六面体：8 个角点（v0..v3 底面一圈 + v4..v7 顶面对应），
 *   轴对齐 → RPP 宏体 + PX/PY/PZ；
 *   斜向 → 6 个局部 PX/PY/PZ + TRn 旋转（行=局部轴方向余弦）。
 *   斜向不用「RPP 宏体 + TR」：FreeCAD worker 对带 Placement 的宏体半空间
 *   做补集布尔会返回垃圾体积（bound.cut(placed compound) 失效），普通平面可靠。
 * - SPH 球：球心 + 半径，从内向外切 K 个等距球壳
 *
 * 编号规则（用户约定）：
 * - 曲面：无输入则 101 起；有输入则取用户最大曲面编号 + 1
 * - cell：无则 1 起；有则取最大 cell 编号 + 1
 * - TR：与 cell 同理（无则 1 起；有则取最大 TR 编号 + 1）
 *
 * 生成的 cell 卡：材料号（默认 0 真空）、密度（材料卡有则自动带出）、
 * imp:n/p/e（勾选才写 1）、注释；其余高级参数留空。
 */

export type QuickShape = "rcc" | "rpp" | "sph";

export interface RccConfig {
  center: [number, number, number];
  axis: [number, number, number];
  radius: number;
  rings: number;      // 半径方向等距环数 N（第 1 环为实心柱）
  segments: number;   // 轴向等距段数 M
}

export interface RppConfig {
  /** 8 个角点：v0..v3 底面一圈，v4..v7 顶面对应（v4 在 v0 正上方方向） */
  points: [number, number, number][];
  nx: number;
  ny: number;
  nz: number;
}

export interface SphConfig {
  center: [number, number, number];
  radius: number;
  shells: number;     // 从内向外等距球壳数 K（第 1 层为实心球）
}

export interface QuickCellContext {
  surfacesText: string;
  trCardsText: string;
  /** 现有 cell 编号（kind=="cell" 行的 num） */
  cellNumbers: number[];
  /** 材料卡（密度有则自动带出到栅元） */
  materials?: { number: number; density?: string }[];
  /** 生成的栅元材料号（默认 "0" 真空） */
  material?: string;
  impN?: boolean;
  impP?: boolean;
  impE?: boolean;
}

export interface GeneratedCell {
  num: string;
  mat: string;
  density: string;
  surfaces: string;
  impN: string;
  impP: string;
  impE: string;
  comment: string;
}

export interface QuickCellResult {
  /** 追加到曲面卡文本区的块（行尾带 \n） */
  surfacesText: string;
  /** 追加到 TR 卡文本区的块（无 TR 时为空串） */
  trCardsText: string;
  cells: GeneratedCell[];
  surfaceCount: number;
  cellCount: number;
}

export interface QuickCellCounts {
  surfaceCount: number;
  cellCount: number;
}

/* ── 编号规则 ──────────────────────────────────────────── */

/** 曲面编号：无输入 → 101；有 → 最大编号 + 1 */
export function nextSurfaceNumber(surfacesText: string): number {
  let max = 0;
  for (const raw of (surfacesText || "").split("\n")) {
    const line = raw.split("$")[0].trim();
    if (!line || /^[cC]/.test(line)) continue;
    const m = line.match(/^(\d+)/);
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return max > 0 ? max + 1 : 101;
}

/** TR 编号：无 → 1；有 → 最大编号 + 1 */
export function nextTrNumber(trCardsText: string): number {
  let max = 0;
  for (const raw of (trCardsText || "").split("\n")) {
    const m = raw.trim().match(/^\*?TR\s*(\d+)/i);
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return max + 1;
}

/** cell 编号：无 → 1；有 → 最大编号 + 1 */
export function nextCellNumber(cellNumbers: number[]): number {
  const max = cellNumbers && cellNumbers.length ? Math.max(...cellNumbers) : 0;
  return max + 1;
}

/* ── 数字/向量工具 ─────────────────────────────────────── */

export function fmtNum(v: number): string {
  if (!Number.isFinite(v)) return "0";
  if (Number.isInteger(v) && Math.abs(v) < 1e15) return String(v);
  const s = v.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  return s;
}

function sub(a: number[], b: number[]): number[] {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function add(a: number[], b: number[]): number[] {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

function dot(a: number[], b: number[]): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function scale(a: number[], s: number): number[] {
  return [a[0] * s, a[1] * s, a[2] * s];
}

function len(a: number[]): number {
  return Math.hypot(a[0], a[1], a[2]);
}

function unit(a: number[]): number[] {
  const l = len(a);
  return l > 1e-12 ? scale(a, 1 / l) : [0, 0, 0];
}

/* ── 校验 ──────────────────────────────────────────────── */

/** 返回错误信息（合法返回 null） */
export function validateQuickCell(shape: QuickShape, config: RccConfig | RppConfig | SphConfig): string | null {
  if (shape === "rcc") {
    const c = config as RccConfig;
    if (!(c.radius > 0)) return "半径必须 > 0";
    if (len(c.axis) < 1e-9) return "轴向向量不能为零向量";
    if (!Number.isInteger(c.rings) || c.rings < 1) return "环数必须是 ≥1 的整数";
    if (!Number.isInteger(c.segments) || c.segments < 1) return "段数必须是 ≥1 的整数";
    return null;
  }
  if (shape === "sph") {
    const c = config as SphConfig;
    if (!(c.radius > 0)) return "半径必须 > 0";
    if (!Number.isInteger(c.shells) || c.shells < 1) return "球壳数必须是 ≥1 的整数";
    return null;
  }
  const c = config as RppConfig;
  if (!Array.isArray(c.points) || c.points.length !== 8) return "需要 8 个角点（底面 v0..v3 + 顶面 v4..v7）";
  if (!Number.isInteger(c.nx) || c.nx < 1) return "X 方向份数必须是 ≥1 的整数";
  if (!Number.isInteger(c.ny) || c.ny < 1) return "Y 方向份数必须是 ≥1 的整数";
  if (!Number.isInteger(c.nz) || c.nz < 1) return "Z 方向份数必须是 ≥1 的整数";
  const [v0, v1, v2, v3, v4, v5, v6, v7] = c.points;
  const a = sub(v1, v0);
  const b = sub(v3, v0);
  const cc = sub(v4, v0);
  const maxLen = Math.max(len(a), len(b), len(cc), 1e-9);
  const tol = Math.max(1e-6, 1e-4 * maxLen);
  const near = (x: number[], y: number[]) => len(sub(x, y)) < tol;
  if (!near(v2, add(v0, add(a, b)))) return "8 个角点不能构成平行六面体（底面 v0,v1,v2,v3 需是平行四边形）";
  if (!near(v5, add(v1, cc))) return "8 个角点不能构成平行六面体（v5 需 = v1 + (v4−v0)）";
  if (!near(v6, add(v2, cc))) return "8 个角点不能构成平行六面体（v6 需 = v2 + (v4−v0)）";
  if (!near(v7, add(v3, cc))) return "8 个角点不能构成平行六面体（v7 需 = v3 + (v4−v0)）";
  if (len(a) < 1e-9 || len(b) < 1e-9 || len(cc) < 1e-9) return "六面体边长不能为 0";
  if (Math.abs(dot(a, b)) > tol * len(a) || Math.abs(dot(a, cc)) > tol * len(a) || Math.abs(dot(b, cc)) > tol * len(b)) {
    return "六面体的三条边必须两两垂直（RPP/BOX 要求正交）";
  }
  return null;
}

/** 生成的曲面/栅元数量（弹窗实时显示用） */
export function quickCellCounts(shape: QuickShape, config: RccConfig | RppConfig | SphConfig): QuickCellCounts {
  if (shape === "rcc") {
    const c = config as RccConfig;
    return { surfaceCount: c.rings + Math.max(0, c.segments - 1), cellCount: c.rings * c.segments };
  }
  if (shape === "sph") {
    const c = config as SphConfig;
    return { surfaceCount: c.shells, cellCount: c.shells };
  }
  const c = config as RppConfig;
  return {
    surfaceCount: (rppAlignedCount(c) ? 1 : 6) + Math.max(0, c.nx - 1) + Math.max(0, c.ny - 1) + Math.max(0, c.nz - 1),
    cellCount: c.nx * c.ny * c.nz,
  };
}

function rppEdges(c: RppConfig): { a: number[]; b: number[]; cc: number[]; tol: number } {
  const [v0, v1, v2, v3, v4] = c.points;
  const a = sub(v1, v0);
  const b = sub(v3, v0);
  const cc = sub(v4, v0);
  const maxLen = Math.max(len(a), len(b), len(cc), 1e-9);
  return { a, b, cc, tol: Math.max(1e-6, 1e-4 * maxLen) };
}

/** 是否为轴对齐（空/退化输入按轴对齐计数，避免空默认值误显示 6 平面） */
function rppAlignedCount(c: RppConfig): boolean {
  if (!Array.isArray(c.points) || c.points.length !== 8) return true;
  const { a, b, cc, tol } = rppEdges(c);
  if (len(a) < 1e-9 || len(b) < 1e-9 || len(cc) < 1e-9) return true;
  return isAxisAligned(a, b, cc, tol);
}

/* ── 密度自动带出 ──────────────────────────────────────── */

export function densityForMaterial(mat: string, materials?: { number: number; density?: string }[]): string {
  const m = parseInt(mat, 10);
  if (!m || !materials || !materials.length) return "";
  const found = materials.find((x) => x.number === m);
  return (found?.density ?? "").trim();
}

/* ── 生成 ──────────────────────────────────────────────── */

function cellBase(ctx: QuickCellContext, num: number, surfaces: string, comment: string): GeneratedCell {
  const mat = (ctx.material ?? "0").trim();
  return {
    num: String(num),
    mat,
    density: mat === "0" ? "" : densityForMaterial(mat, ctx.materials),
    surfaces,
    impN: ctx.impN ? "1" : "",
    impP: ctx.impP ? "1" : "",
    impE: ctx.impE ? "1" : "",
    comment,
  };
}

function joinExpr(parts: string[]): string {
  return parts.filter(Boolean).join(" ").trim();
}

function generateRcc(c: RccConfig, ctx: QuickCellContext): QuickCellResult {
  let surf = nextSurfaceNumber(ctx.surfacesText);
  let cell = nextCellNumber(ctx.cellNumbers);
  const lines: string[] = [`c ---- 快捷建栅元：RCC 圆柱（环${c.rings} × 段${c.segments}） ----`];
  const u = unit(c.axis);
  const axisLen = len(c.axis);
  const baseD = dot(u, c.center);
  const rccNums: number[] = [];
  for (let k = 1; k <= c.rings; k++) {
    const num = surf++;
    rccNums.push(num);
    lines.push(`${num} rcc ${fmtNum(c.center[0])} ${fmtNum(c.center[1])} ${fmtNum(c.center[2])} ${fmtNum(c.axis[0])} ${fmtNum(c.axis[1])} ${fmtNum(c.axis[2])} ${fmtNum((c.radius * k) / c.rings)}`);
  }
  const pNums: number[] = [];
  if (c.segments > 1) {
    for (let k = 1; k < c.segments; k++) {
      const num = surf++;
      pNums.push(num);
      const d = baseD + (axisLen * k) / c.segments;
      lines.push(`${num} p ${fmtNum(u[0])} ${fmtNum(u[1])} ${fmtNum(u[2])} ${fmtNum(d)}`);
    }
  }
  const cells: GeneratedCell[] = [];
  for (let i = 1; i <= c.rings; i++) {
    const ringExpr = i === 1 ? `-${rccNums[0]}` : `+${rccNums[i - 2]} -${rccNums[i - 1]}`;
    for (let k = 1; k <= c.segments; k++) {
      let segExpr = "";
      if (c.segments > 1) {
        if (k === 1) segExpr = `-${pNums[0]}`;
        else if (k === c.segments) segExpr = `+${pNums[k - 2]}`;
        else segExpr = `+${pNums[k - 2]} -${pNums[k - 1]}`;
      }
      cells.push(cellBase(ctx, cell++, joinExpr([ringExpr, segExpr]), `RCC 环${i}/${c.rings} 段${k}/${c.segments}`));
    }
  }
  return { surfacesText: lines.join("\n") + "\n", trCardsText: "", cells, surfaceCount: lines.length - 1, cellCount: cells.length };
}

function generateSph(c: SphConfig, ctx: QuickCellContext): QuickCellResult {
  let surf = nextSurfaceNumber(ctx.surfacesText);
  let cell = nextCellNumber(ctx.cellNumbers);
  const lines: string[] = [`c ---- 快捷建栅元：SPH 球（球壳${c.shells} 层） ----`];
  const sphNums: number[] = [];
  for (let k = 1; k <= c.shells; k++) {
    const num = surf++;
    sphNums.push(num);
    lines.push(`${num} sph ${fmtNum(c.center[0])} ${fmtNum(c.center[1])} ${fmtNum(c.center[2])} ${fmtNum((c.radius * k) / c.shells)}`);
  }
  const cells: GeneratedCell[] = [];
  for (let k = 1; k <= c.shells; k++) {
    const expr = k === 1 ? `-${sphNums[0]}` : `+${sphNums[k - 2]} -${sphNums[k - 1]}`;
    cells.push(cellBase(ctx, cell++, expr, `SPH 壳${k}/${c.shells}`));
  }
  return { surfacesText: lines.join("\n") + "\n", trCardsText: "", cells, surfaceCount: lines.length - 1, cellCount: cells.length };
}

/** 判断三边是否分别平行于 X/Y/Z 坐标轴 */
function isAxisAligned(a: number[], b: number[], cc: number[], tol: number): boolean {
  const ax = (v: number[]) => v.map((x) => (Math.abs(x) > tol ? 1 : 0)).join("");
  const dirs = [ax(a), ax(b), ax(cc)];
  return dirs.every((d) => d === "100" || d === "010" || d === "001") && new Set(dirs).size === 3;
}

function generateRpp(c: RppConfig, ctx: QuickCellContext): QuickCellResult {
  const [v0, v1, v2, v3, v4] = c.points;
  const { a, b, cc, tol } = rppEdges(c);
  const aligned = isAxisAligned(a, b, cc, tol);

  let surf = nextSurfaceNumber(ctx.surfacesText);
  let cell = nextCellNumber(ctx.cellNumbers);
  const lines: string[] = [`c ---- 快捷建栅元：RPP 六面体（${c.nx}×${c.ny}×${c.nz}）${aligned ? "" : "（斜向 + TR）"} ----`];
  const trLines: string[] = [];
  let trSuffix = "";

  let xLo = 0, xHi = 0, yLo = 0, yHi = 0, zLo = 0, zHi = 0;
  let rppNum = 0;
  if (aligned) {
    rppNum = surf++;
    const xs = c.points.map((p) => p[0]);
    const ys = c.points.map((p) => p[1]);
    const zs = c.points.map((p) => p[2]);
    xLo = Math.min(...xs); xHi = Math.max(...xs);
    yLo = Math.min(...ys); yHi = Math.max(...ys);
    zLo = Math.min(...zs); zHi = Math.max(...zs);
    lines.push(`${rppNum} rpp ${fmtNum(xLo)} ${fmtNum(xHi)} ${fmtNum(yLo)} ${fmtNum(yHi)} ${fmtNum(zLo)} ${fmtNum(zHi)}`);
  } else {
    const trNum = nextTrNumber(ctx.trCardsText);
    const la = len(a), lb = len(b), lc = len(cc);
    const u = unit(a), v = unit(b), w = unit(cc);
    trSuffix = ` *TR${trNum}`;
    trLines.push(`TR${trNum} ${fmtNum(v0[0])} ${fmtNum(v0[1])} ${fmtNum(v0[2])} ${fmtNum(u[0])} ${fmtNum(u[1])} ${fmtNum(u[2])} ${fmtNum(v[0])} ${fmtNum(v[1])} ${fmtNum(v[2])} ${fmtNum(w[0])} ${fmtNum(w[1])} ${fmtNum(w[2])}`);
    xLo = 0; xHi = la; yLo = 0; yHi = lb; zLo = 0; zHi = lc;
  }

  // 平面编号数组（有序）：轴对齐 = RPP 宏体 + 内部切分平面；
  // 斜向 = 6 个局部外表面平面 + 内部切分平面（全部 *TRn）。
  const px: number[] = [];
  const py: number[] = [];
  const pz: number[] = [];
  const mkPlane = (kw: string, d: number): number => {
    const num = surf++;
    lines.push(`${num} ${kw} ${fmtNum(d)}${trSuffix}`);
    return num;
  };
  if (aligned) {
    for (let k = 1; k < c.nx; k++) px.push(mkPlane("px", xLo + ((xHi - xLo) * k) / c.nx));
    for (let k = 1; k < c.ny; k++) py.push(mkPlane("py", yLo + ((yHi - yLo) * k) / c.ny));
    for (let k = 1; k < c.nz; k++) pz.push(mkPlane("pz", zLo + ((zHi - zLo) * k) / c.nz));
  } else {
    px.push(mkPlane("px", xLo), mkPlane("px", xHi));
    py.push(mkPlane("py", yLo), mkPlane("py", yHi));
    pz.push(mkPlane("pz", zLo), mkPlane("pz", zHi));
    for (let k = 1; k < c.nx; k++) px.splice(px.length - 1, 0, mkPlane("px", xLo + ((xHi - xLo) * k) / c.nx));
    for (let k = 1; k < c.ny; k++) py.splice(py.length - 1, 0, mkPlane("py", yLo + ((yHi - yLo) * k) / c.ny));
    for (let k = 1; k < c.nz; k++) pz.splice(pz.length - 1, 0, mkPlane("pz", zLo + ((zHi - zLo) * k) / c.nz));
  }

  const cells: GeneratedCell[] = [];
  for (let i = 1; i <= c.nx; i++) {
    const xExpr = aligned
      ? [i > 1 ? `+${px[i - 2]}` : "", i < c.nx ? `-${px[i - 1]}` : ""].filter(Boolean).join(" ")
      : `+${px[i - 1]} -${px[i]}`;
    for (let j = 1; j <= c.ny; j++) {
      const yExpr = aligned
        ? [j > 1 ? `+${py[j - 2]}` : "", j < c.ny ? `-${py[j - 1]}` : ""].filter(Boolean).join(" ")
        : `+${py[j - 1]} -${py[j]}`;
      for (let k = 1; k <= c.nz; k++) {
        const zExpr = aligned
          ? [k > 1 ? `+${pz[k - 2]}` : "", k < c.nz ? `-${pz[k - 1]}` : ""].filter(Boolean).join(" ")
          : `+${pz[k - 1]} -${pz[k]}`;
        cells.push(cellBase(ctx, cell++, joinExpr([aligned ? `-${rppNum}` : "", xExpr, yExpr, zExpr]), `RPP ${i}/${c.nx} ${j}/${c.ny} ${k}/${c.nz}`));
      }
    }
  }
  return {
    surfacesText: lines.join("\n") + "\n",
    trCardsText: trLines.length ? trLines.join("\n") + "\n" : "",
    cells,
    surfaceCount: lines.length - 1,
    cellCount: cells.length,
  };
}

/** 生成快捷栅元（假定已通过 validateQuickCell；非法配置直接抛错） */
export function generateQuickCell(shape: QuickShape, config: RccConfig | RppConfig | SphConfig, ctx: QuickCellContext): QuickCellResult {
  if (shape === "rcc") return generateRcc(config as RccConfig, ctx);
  if (shape === "sph") return generateSph(config as SphConfig, ctx);
  return generateRpp(config as RppConfig, ctx);
}
