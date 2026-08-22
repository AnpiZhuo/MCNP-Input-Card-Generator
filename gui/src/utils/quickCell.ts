/**
 * 快捷建栅元 — 纯函数深模块（vitest 可测，零依赖）
 *
 * 在几何标签页「曲面卡 & TR 变换」一键生成体：
 * - RCC 圆柱：底面中心 + 轴向向量 + 半径，切 N 个等距圆环 × M 个等距轴段
 * - RPP 六面体：用户输入长×宽×高 + 体中心 + 倾斜角度（弧度，依次绕 X/Y/Z
 *   外旋 R=Rz·Ry·Rx，DEG/RAD 切换在弹窗层）；
 *   全零角度（轴对齐）→ RPP 宏体 + PX/PY/PZ，无 TR；
 *   有倾斜 → 6 个局部 PX/PY/PZ + TRn（行=局部轴方向余弦，程序按角度算）。
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
 * imp:n/p/e（勾选写 0=杀粒子；不勾选按基础页粒子模式填 1，未启用模式留空）、
 * 注释；其余高级参数留空。
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
  /** 长(L, X 方向)、宽(W, Y 方向)、高(H, Z 方向) */
  size: [number, number, number];
  /** 体中心坐标 */
  center: [number, number, number];
  /** 倾斜角（弧度）：依次绕 X、Y、Z（固定轴外旋 R=Rz·Ry·Rx）；全 0 = 轴对齐无 TR */
  angles: [number, number, number];
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
  /** 基础页启用的粒子模式（N/P/E）——不勾选 imp 时按此填 1 */
  modeN?: boolean;
  modeP?: boolean;
  modeE?: boolean;
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
  /** 添加后是否做重合检测（GeometryTab 据此决定是否弹补集决策） */
  checkOverlap?: boolean;
  /** 已有栅元表达式补丁（方向 B：给这些栅元追加 #新号） */
  existingExprPatch?: { num: string; surfaces: string }[];
  /** 已由生成入口（如 3D 预览）处理过重合决策，接收方不再重复弹窗 */
  overlapHandled?: boolean;
}

/** 快捷添加重合决策方向 */
export type QuickAddChoice = "new_hole" | "existing_hole" | "void_only" | "none";

/**
 * 把重合决策应用到生成结果（纯函数，支持一次性多栅元）。
 *
 * 语义（MCNP 中 `expr #n` = 在 expr 内且不在栅元 n 内）：
 * - new_hole：每个新栅元追加 `#` 其重合的已有栅元（挖掉已有）；
 * - existing_hole：每个重合的已有栅元追加 `#` 与其重合的新栅元（已有让位）；
 * - void_only（侵占真空、不侵占已有）：新栅元追加 `#` 重合的**非真空**已有栅元；
 *   重合的**真空**已有栅元追加 `#` 新栅元（真空让位）；
 * - none：不改。
 *
 * overlaps 只取「新 × 已有」对（两边都是新栅元的对忽略）。
 * 返回打补丁后的 result（existingExprPatch 由接收方应用到已有行）。
 */
export function applyQuickAddChoice(
  result: QuickCellResult,
  overlaps: { a: number; b: number }[],
  existingCells: { num: number; mat: string; surfaces: string }[],
  choice: QuickAddChoice,
): QuickCellResult {
  const newNums = new Set(result.cells.map(c => parseInt(c.num, 10)));
  const pairs = overlaps
    .map(o => {
      const a = Number(o.a);
      const b = Number(o.b);
      return { newNum: newNums.has(a) ? a : b, existingNum: newNums.has(a) ? b : a };
    })
    .filter(p => newNums.has(p.newNum) && !newNums.has(p.existingNum));
  const matOf = new Map(existingCells.map(c => [c.num, c.mat]));
  const surfOf = new Map(existingCells.map(c => [c.num, c.surfaces]));
  const out: QuickCellResult = { ...result, cells: result.cells.map(c => ({ ...c })) };

  if (choice === "new_hole" || choice === "void_only") {
    for (const c of out.cells) {
      const num = parseInt(c.num, 10);
      let nums = pairs.filter(p => p.newNum === num).map(p => p.existingNum);
      if (choice === "void_only") {
        nums = nums.filter(n => String(matOf.get(n) ?? "0").trim() !== "0");
      }
      if (nums.length) {
        c.surfaces = (c.surfaces + " " + nums.map(n => "#" + n).join(" ")).trim();
      }
    }
  }
  if (choice === "existing_hole" || choice === "void_only") {
    const existingNums = Array.from(new Set(pairs.map(p => p.existingNum)));
    const patches: { num: string; surfaces: string }[] = [];
    for (const en of existingNums) {
      const isVoid = String(matOf.get(en) ?? "0").trim() === "0";
      if (choice === "void_only" && !isVoid) continue; // 只占真空：材料栅元不动（由新栅元 # 材料）
      const newOver = pairs.filter(p => p.existingNum === en).map(p => p.newNum);
      patches.push({
        num: String(en),
        surfaces: ((surfOf.get(en) ?? "") + " " + newOver.map(n => "#" + n).join(" ")).trim(),
      });
    }
    if (patches.length) out.existingExprPatch = patches;
  }
  return out;
}

/** GeometryTab 本地栅元行（camelCase，与 CellEditDialog.CellData 一致） */
export interface QuickCellLocalRow {
  kind: "cell";
  cell: {
    num: string;
    mat: string;
    density: string;
    surfaces: string;
    impN: string;
    impP: string;
    impE: string;
    vol: string;
    pwt: string;
    ext: string;
    fcl: string;
    u: string;
    fill: string;
    lat: string;
    trcl: string;
    tmp: string;
    otherParams: string;
    render: boolean;
    comment: string;
  };
}

/** 追加卡文本块：两块之间只保留一个换行；空块不追加 */
export function appendCardText(prev: string, block: string): string {
  if (!block) return prev;
  return (prev.trim() ? prev.replace(/\s*$/, "") + "\n" : "") + block;
}

/** GeneratedCell → GeometryTab 本地行（高级参数留空，render 默认 true） */
export function generatedCellToRow(c: GeneratedCell): QuickCellLocalRow {
  return {
    kind: "cell",
    cell: {
      num: c.num,
      mat: c.mat,
      density: c.density,
      surfaces: c.surfaces,
      impN: c.impN,
      impP: c.impP,
      impE: c.impE,
      vol: "",
      pwt: "",
      ext: "",
      fcl: "",
      u: "",
      fill: "",
      lat: "",
      trcl: "",
      tmp: "",
      otherParams: "",
      render: true,
      comment: c.comment,
    },
  };
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
  const [L, W, H] = c.size;
  if (!(L > 0) || !(W > 0) || !(H > 0)) return "长/宽/高必须 > 0";
  if (!c.center.every((v) => Number.isFinite(v))) return "中心坐标必须是有效数字";
  if (!c.angles.every((v) => Number.isFinite(v))) return "倾斜角度必须是有效数字";
  if (!Number.isInteger(c.nx) || c.nx < 1) return "X 方向份数必须是 ≥1 的整数";
  if (!Number.isInteger(c.ny) || c.ny < 1) return "Y 方向份数必须是 ≥1 的整数";
  if (!Number.isInteger(c.nz) || c.nz < 1) return "Z 方向份数必须是 ≥1 的整数";
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
  const rotated = c.angles.some((v) => Math.abs(v) > 1e-9);
  return {
    surfaceCount: (rotated ? 6 : 1) + Math.max(0, c.nx - 1) + Math.max(0, c.ny - 1) + Math.max(0, c.nz - 1),
    cellCount: c.nx * c.ny * c.nz,
  };
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
    impN: ctx.impN ? "0" : (ctx.modeN ? "1" : ""),
    impP: ctx.impP ? "0" : (ctx.modeP ? "1" : ""),
    impE: ctx.impE ? "0" : (ctx.modeE ? "1" : ""),
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

/**
 * 解析角度输入表达式（支持 π）：如 "45"、"π/2"、"2π"、"π"、"90"。
 * 只允许数字/π/四则/括号/一元正负；非法返回 null。
 */
export function parseAngleExpr(s: string): number | null {
  const text = (s ?? "").replace(/\s+/g, "").replace(/π/g, "PI").replace(/pi/gi, "PI");
  if (!text) return null;
  let i = 0;
  const peek = () => text[i] ?? "";

  function parseFactor(): number | null {
    if (peek() === "(") {
      i++;
      const v = parseExpr();
      if (v === null || peek() !== ")") return null;
      i++;
      return v;
    }
    if (peek() === "-") { i++; const v = parseFactor(); return v === null ? null : -v; }
    if (peek() === "+") { i++; return parseFactor(); }
    if (text.startsWith("PI", i)) { i += 2; return Math.PI; }
    const m = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?/.exec(text.slice(i));
    if (m) { i += m[0].length; return parseFloat(m[0]); }
    return null;
  }

  function parseTerm(): number | null {
    let v = parseFactor();
    if (v === null) return null;
    for (;;) {
      const op = peek();
      if (op === "*" || op === "/") {
        i++;
        const r = parseFactor();
        if (r === null) return null;
        v = op === "*" ? v * r : v / r;
      } else if (op === "(" || text.startsWith("PI", i)) {
        // 隐式乘法：2π、2(π/2)
        const r = parseFactor();
        if (r === null) return null;
        v = v * r;
      } else break;
    }
    return v;
  }

  function parseExpr(): number | null {
    let v = parseTerm();
    if (v === null) return null;
    for (;;) {
      const op = peek();
      if (op === "+" || op === "-") {
        i++;
        const r = parseTerm();
        if (r === null) return null;
        v = op === "+" ? v + r : v - r;
      } else break;
    }
    return v;
  }

  const v = parseExpr();
  return v !== null && i === text.length ? v : null;
}

/** 欧拉角旋转矩阵 R = Rz(γ)·Ry(β)·Rx(α)（行主序），依次绕 X、Y、Z 外旋 */
export function eulerRotation(angles: [number, number, number]): number[][] {
  const [ax, ay, az] = angles;
  const cx = Math.cos(ax), sx = Math.sin(ax);
  const cy = Math.cos(ay), sy = Math.sin(ay);
  const cz = Math.cos(az), sz = Math.sin(az);
  const rx: number[][] = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]];
  const ry: number[][] = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]];
  const rz: number[][] = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]];
  const mul = (A: number[][], B: number[][]) =>
    A.map((row, r) => [0, 1, 2].map((col) => row[0] * B[0][col] + row[1] * B[1][col] + row[2] * B[2][col]));
  return mul(mul(rz, ry), rx);
}

/** TR 卡 B 矩阵 9 值：行 = 局部轴在全局的方向余弦（= R 的列） */
export function trBFromAngles(angles: [number, number, number]): number[] {
  const R = eulerRotation(angles);
  return [
    R[0][0], R[1][0], R[2][0],
    R[0][1], R[1][1], R[2][1],
    R[0][2], R[1][2], R[2][2],
  ];
}

function generateRpp(c: RppConfig, ctx: QuickCellContext): QuickCellResult {
  const [L, W, H] = c.size;
  const [cx0, cy0, cz0] = c.center;
  const rotated = c.angles.some((v) => Math.abs(v) > 1e-9);

  let surf = nextSurfaceNumber(ctx.surfacesText);
  let cell = nextCellNumber(ctx.cellNumbers);
  const lines: string[] = [`c ---- 快捷建栅元：RPP 六面体（${c.nx}×${c.ny}×${c.nz}）${rotated ? "（倾斜 + TR）" : ""} ----`];
  const trLines: string[] = [];
  let trSuffix = "";

  let rppNum = 0;
  if (!rotated) {
    rppNum = surf++;
    const xLo = cx0 - L / 2, xHi = cx0 + L / 2;
    const yLo = cy0 - W / 2, yHi = cy0 + W / 2;
    const zLo = cz0 - H / 2, zHi = cz0 + H / 2;
    lines.push(`${rppNum} rpp ${fmtNum(xLo)} ${fmtNum(xHi)} ${fmtNum(yLo)} ${fmtNum(yHi)} ${fmtNum(zLo)} ${fmtNum(zHi)}`);
  } else {
    const trNum = nextTrNumber(ctx.trCardsText);
    trSuffix = ` *TR${trNum}`;
    trLines.push(`TR${trNum} ${fmtNum(cx0)} ${fmtNum(cy0)} ${fmtNum(cz0)} ${trBFromAngles(c.angles).map(fmtNum).join(" ")}`);
  }

  // 平面编号数组（有序）：轴对齐 = RPP 宏体 + 内部切分平面；
  // 倾斜 = 6 个局部外表面平面 + 内部切分平面（全部 *TRn，局部系原点在体中心）。
  const px: number[] = [];
  const py: number[] = [];
  const pz: number[] = [];
  const mkPlane = (kw: string, d: number): number => {
    const num = surf++;
    lines.push(`${num} ${kw} ${fmtNum(d)}${trSuffix}`);
    return num;
  };
  if (!rotated) {
    const xLo = cx0 - L / 2, yLo = cy0 - W / 2, zLo = cz0 - H / 2;
    for (let k = 1; k < c.nx; k++) px.push(mkPlane("px", xLo + (L * k) / c.nx));
    for (let k = 1; k < c.ny; k++) py.push(mkPlane("py", yLo + (W * k) / c.ny));
    for (let k = 1; k < c.nz; k++) pz.push(mkPlane("pz", zLo + (H * k) / c.nz));
  } else {
    px.push(mkPlane("px", -L / 2), mkPlane("px", L / 2));
    py.push(mkPlane("py", -W / 2), mkPlane("py", W / 2));
    pz.push(mkPlane("pz", -H / 2), mkPlane("pz", H / 2));
    for (let k = 1; k < c.nx; k++) px.splice(px.length - 1, 0, mkPlane("px", -L / 2 + (L * k) / c.nx));
    for (let k = 1; k < c.ny; k++) py.splice(py.length - 1, 0, mkPlane("py", -W / 2 + (W * k) / c.ny));
    for (let k = 1; k < c.nz; k++) pz.splice(pz.length - 1, 0, mkPlane("pz", -H / 2 + (H * k) / c.nz));
  }

  const cells: GeneratedCell[] = [];
  for (let i = 1; i <= c.nx; i++) {
    const xExpr = rotated
      ? `+${px[i - 1]} -${px[i]}`
      : [i > 1 ? `+${px[i - 2]}` : "", i < c.nx ? `-${px[i - 1]}` : ""].filter(Boolean).join(" ");
    for (let j = 1; j <= c.ny; j++) {
      const yExpr = rotated
        ? `+${py[j - 1]} -${py[j]}`
        : [j > 1 ? `+${py[j - 2]}` : "", j < c.ny ? `-${py[j - 1]}` : ""].filter(Boolean).join(" ");
      for (let k = 1; k <= c.nz; k++) {
        const zExpr = rotated
          ? `+${pz[k - 1]} -${pz[k]}`
          : [k > 1 ? `+${pz[k - 2]}` : "", k < c.nz ? `-${pz[k - 1]}` : ""].filter(Boolean).join(" ");
        cells.push(cellBase(ctx, cell++, joinExpr([rotated ? "" : `-${rppNum}`, xExpr, yExpr, zExpr]), `RPP ${i}/${c.nx} ${j}/${c.ny} ${k}/${c.nz}`));
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
