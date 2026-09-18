/**
 * planeEquation — 切割平面方程的**单一权威**（解析 / 格式化 / 步进）。
 *
 * ## 为什么要有这个模块
 * 这套东西原先**散在两处**：`Preview3D.tsx` 里私有的 `parsePlane` / `planeToStr`
 * （平面方程输入框用），`CrossSectionView.tsx` 里又自己写了一套 `D ± step` 的步进 UI。
 * 现在三处都要用同一件事（3D 预览的截面、截面窗口的步进、3D 结果窗口的切面），
 * 所以收敛到这里：**一处定义，处处一致**——否则"步长"在两个窗口里语义会慢慢分叉
 * （一个按 D 走、一个按层号走，用户会以为程序坏了）。
 *
 * ## 约定
 * - 平面方程 `A X + B Y + C Z = D`，法向量 `(A,B,C)`；**不要求归一化**。
 *   步进量是 **D 的增量**（不是几何距离）——与 3D 预览既有行为一致，换成几何距离
 *   会让老用户的"步长 1"含义突变。
 * - 解析接受：`X + Y = 0`、`2x-3y+0.5z=10`、`-X = 1.5`，大小写与空格随意；
 *   系数省略算 1（`X` → 1，`-Y` → -1）。
 */

export interface PlaneEq {
  A: number;
  B: number;
  C: number;
  D: number;
}

/** 数值 → 紧凑字符串（整数直出；小数去尾零） */
function fmtNum(v: number): string {
  if (!isFinite(v)) return "0";
  if (v === Math.floor(v)) return String(v);
  return v.toFixed(3).replace(/\.?0+$/, "");
}

/** 系数 → 紧凑写法：1 → ""，-1 → "-" */
function fmtCoef(v: number): string {
  if (v === 1) return "";
  if (v === -1) return "-";
  return fmtNum(v);
}

/** 平面 → 方程文本（`X + Y = 0`；全零法向 → `0 = D`，不做静默假平面） */
export function planeToStr(plane: PlaneEq): string {
  const parts: string[] = [];
  if (plane.A !== 0) parts.push(fmtCoef(plane.A) + "X");
  if (plane.B !== 0) parts.push(fmtCoef(plane.B) + "Y");
  if (plane.C !== 0) parts.push(fmtCoef(plane.C) + "Z");
  if (parts.length === 0) parts.push("0");
  return parts.join(" + ") + " = " + fmtNum(plane.D);
}

/**
 * 方程文本 → 平面。解析不出任何一项 → null（调用方保留原平面并提示，
 * **不要**静默当成 `0 = 0`——那是个"切不出来任何东西"的假平面）。
 */
export function parsePlane(s: string): PlaneEq | null {
  const cleaned = String(s ?? "").replace(/\s+/g, "");
  if (!cleaned) return null;
  const coef = (raw: string): number => {
    if (raw === "" || raw === "+") return 1;
    if (raw === "-") return -1;
    const v = parseFloat(raw);
    return isFinite(v) ? v : 0;
  };
  const xm = cleaned.match(/([+-]?\d*\.?\d*)x/i);
  const ym = cleaned.match(/([+-]?\d*\.?\d*)y/i);
  const zm = cleaned.match(/([+-]?\d*\.?\d*)z/i);
  const dm = cleaned.match(/=([+-]?\d*\.?\d+)/);
  if (!xm && !ym && !zm && !dm) return null;
  return {
    A: xm ? coef(xm[1]) : 0,
    B: ym ? coef(ym[1]) : 0,
    C: zm ? coef(zm[1]) : 0,
    D: dm ? parseFloat(dm[1]) : 0,
  };
}

/** 轴对齐平面（`"x" | "y" | "z"` + 位置）→ 平面方程 */
export function axisPlane(axis: "x" | "y" | "z", d: number): PlaneEq {
  return {
    A: axis === "x" ? 1 : 0,
    B: axis === "y" ? 1 : 0,
    C: axis === "z" ? 1 : 0,
    D: d,
  };
}

/** 沿平面法向步进（只动 D，与 3D 预览既有语义一致） */
export function stepPlane(plane: PlaneEq, step: number): PlaneEq {
  return { ...plane, D: plane.D + step };
}

/**
 * 步长折半。
 *
 * `step` 非法（0/负/NaN）时**按"已经是最小步长"处理**（返回 0.001），
 * 而不是"当成 1 再折半"——后者会让用户连点几次 ◀ 之后悄悄把步长从 0.5 掉到下限，
 * 与他看到的初值不符；这里保证"点 ◀ 只会变小、永远不为 0 或负数"这一条硬性质。
 */
export function halveStep(step: number): number {
  const s = isFinite(step) && step > 0 ? step : 0.001;
  return Math.max(0.001, s / 2);
}

/** 步长加倍 */
export function doubleStep(step: number): number {
  return (isFinite(step) && step > 0 ? step : 1) * 2;
}

/** 法向量长度（为 0 表示不是合法平面，切不出东西） */
export function normalLength(plane: PlaneEq): number {
  return Math.hypot(plane.A, plane.B, plane.C);
}

/**
 * 按步长把平面沿法向摊成**一串**平面（成叠切片的输入）。
 *
 * 含两端、`count` 封顶（防止用户在步长很小 + 范围很大时把程序点到假死）。
 * 返回的每个平面都带 `index`（1 起，用于文件名与图内编号）。
 */
export function planeSeries(
  plane: PlaneEq,
  step: number,
  dMin: number,
  dMax: number,
  maxCount = 200,
): { plane: PlaneEq; index: number; d: number }[] {
  const out: { plane: PlaneEq; index: number; d: number }[] = [];
  const s = isFinite(step) && step > 0 ? step : 1;
  const lo = Math.min(dMin, dMax);
  const hi = Math.max(dMin, dMax);
  let i = 0;
  for (let d = lo; d <= hi + 1e-9 && out.length < maxCount; d += s, i++) {
    out.push({ plane: { ...plane, D: d }, index: i + 1, d });
  }
  return out;
}
