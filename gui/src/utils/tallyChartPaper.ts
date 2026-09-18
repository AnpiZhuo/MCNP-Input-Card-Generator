/**
 * tallyChartPaper — tally 通量图的**出图版**（论文配色、透明底、尺寸自适应）。
 *
 * ## 为什么不直接改 `buildFluxChartSvg`
 * 那个是**屏幕上**的弹窗用的：深色配色（浅灰轴线、亮绿曲线）是为深底调的，
 * 尺寸也是写死 560×300。出图要的是另一套（白/透明底、黑轴、深色相、按窗口尺寸自适应）。
 * 硬把两者合成一个函数，就得在调用处到处传"我现在是要出图还是要在屏幕上看"——
 * 那是把两件事塞进一个接口。所以并排放：屏幕版留原样（零回归风险），出图版是本模块。
 *
 * ## 出图版比屏幕版多做的事
 * - 轴标题带单位与**刻度标注**（对数轴标 `10^n`，一眼能看出是对数）；
 * - 图例（通量 / 1σ 误差棒）——论文图必须有，否则读者不知道红短线是什么；
 * - 误差棒用矢量线段（放大不糊）、数据点用小圆点；
 * - 值域标注（数据点数、是否对数）。
 */
import { themeFor, type PlotTheme } from "../export/plotTheme";
import type { TallyRow } from "./outputParser";
import { estimateTextWidth, esc } from "../export/vectorFigure";

export interface PaperChartOptions {
  width: number;
  height: number;
  theme?: PlotTheme;
  /** 图标题（一般留空：出图版面已有标题，避免重复） */
  title?: string;
}

/** 论文版数值格式 */
function fmt(v: number): string {
  if (!Number.isFinite(v)) return "";
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e5 || a < 1e-3)) return v.toExponential(1);
  return Number.isInteger(v) ? String(v) : String(parseFloat(v.toPrecision(3)));
}

/** 对数轴刻度标注：10^n（比 0.0001 这种好读得多） */
function fmtLog(v: number): string {
  const e = Math.round(Math.log10(v));
  if (Math.abs(Math.pow(10, e) - v) / v < 1e-6) return `10^${e}`;
  return fmt(v);
}

/**
 * 生成论文版 tally 通量图 SVG（**透明底**，由版面/PDF 决定底色）。
 * 无有效数据点 → 返回 null（调用方画"无数据"提示，而不是出一张空图）。
 */
export function buildPaperTallyChart(rows: TallyRow[], opts: PaperChartOptions): string | null {
  const t = opts.theme ?? themeFor("paper");
  const W = Math.max(280, Math.round(opts.width));
  const H = Math.max(200, Math.round(opts.height));
  const fs = t.page.tickSize;
  const font = t.fontFamily;

  const pts = (rows || [])
    .map((r, i) => ({
      i,
      energy: r.energy !== "" ? parseFloat(r.energy) : NaN,
      flux: parseFloat(r.flux),
      err: r.error ? parseFloat(r.error) : NaN,
    }))
    .filter((p) => isFinite(p.flux) && p.flux >= 0);
  if (!pts.length) return null;

  // 边距：右侧留图例、下方留轴标题
  const mL = 62, mR = 16, mT = 14, mB = 46;
  const pw = W - mL - mR;
  const ph = H - mT - mB;
  if (pw < 40 || ph < 40) return null;

  const xs = pts.map((p) => (isFinite(p.energy) ? p.energy : p.i + 1));
  let xMin = Math.min(...xs);
  let xMax = Math.max(...xs);
  if (xMax === xMin) { xMin -= 0.5; xMax += 0.5; }
  /**
   * x 轴对数判定：MCNP 的能量分箱通常跨好几个数量级（1e-8 → 20 MeV）。
   * 线性轴上低能点会**全部挤在最左边**，图基本没法看（实测：720px 宽的图里
   * 前 5 个点全压在 x=1e-8 那一列）。跨 100 倍以上就走 log 轴，与 y 轴同一判据。
   */
  const xAllPos = xs.length > 0 && xs.every((v) => v > 0);
  const logX = xAllPos && xMin > 0 && xMax / xMin > 100;
  const xLo = logX ? Math.log10(xMin) : xMin;
  const xHi = logX ? Math.log10(xMax) : xMax;

  const yMax = Math.max(...pts.map((p) => p.flux));
  const yPos = pts.map((p) => p.flux).filter((v) => v > 0);
  const yMinPos = yPos.length ? Math.min(...yPos) : 1;
  const logY = yMinPos > 0 && yMax / yMinPos > 100;
  const yBottom = logY ? yMinPos : 0;
  const yTop = yMax * (logY ? 1.2 : 1.12);

  const X = (v: number) => {
    const raw = logX ? Math.log10(Math.max(v, xMin)) : v;
    return mL + ((raw - xLo) / ((xHi - xLo) || 1)) * pw;
  };
  const Y = (v: number) => {
    if (logY) {
      const a = Math.log10(Math.max(v, yBottom));
      const lo = Math.log10(yBottom);
      const hi = Math.log10(yTop);
      return mT + ph - ((a - lo) / ((hi - lo) || 1)) * ph;
    }
    return mT + ph - ((v - yBottom) / ((yTop - yBottom) || 1)) * ph;
  };

  const yTicks: number[] = [];
  if (logY) {
    for (let p = Math.pow(10, Math.floor(Math.log10(yBottom))); p <= yTop * 1.0001; p *= 10) yTicks.push(p);
  } else {
    const step = (yTop - yBottom) / 5;
    for (let k = 0; k <= 5; k++) yTicks.push(yBottom + step * k);
  }
  const xTicks: number[] = [];
  if (logX) {
    for (let e = Math.floor(xLo); e <= Math.ceil(xHi) + 1e-9; e++) {
      const v = Math.pow(10, e);
      if (v >= xMin * 0.9999 && v <= xMax * 1.0001) xTicks.push(v);
    }
    // 数量级太少（如只有两个 10^n）→ 补中点，避免只有两根刻度
    if (xTicks.length < 3) {
      xTicks.length = 0;
      const n = 5;
      for (let k = 0; k < n; k++) xTicks.push(Math.pow(10, xLo + ((xHi - xLo) * k) / (n - 1)));
    }
  } else {
    const n = Math.min(8, Math.max(2, pts.length));
    for (let k = 0; k < n; k++) xTicks.push(xMin + ((xMax - xMin) * k) / (n - 1 || 1));
  }

  const out: string[] = [];
  out.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="${esc(font)}" font-size="${fs}">`);

  // 网格（浅灰，细）
  for (const v of yTicks) {
    const y = Y(v);
    out.push(`<line x1="${mL}" y1="${r1(y)}" x2="${mL + pw}" y2="${r1(y)}" stroke="${t.grid}" stroke-width="0.8"/>`);
  }

  // 坐标轴（黑，稍粗）
  out.push(`<line x1="${mL}" y1="${mT}" x2="${mL}" y2="${mT + ph}" stroke="${t.axis}" stroke-width="1.2"/>`);
  out.push(`<line x1="${mL}" y1="${mT + ph}" x2="${mL + pw}" y2="${mT + ph}" stroke="${t.axis}" stroke-width="1.2"/>`);

  // 刻度与标注
  out.push(`<g fill="${t.textMuted}">`);
  for (const v of yTicks) {
    const y = Y(v);
    out.push(`<text x="${mL - 6}" y="${r1(y + 3)}" text-anchor="end">${esc(logY ? fmtLog(v) : fmt(v))}</text>`);
  }
  for (const v of xTicks) {
    const x = X(v);
    out.push(`<line x1="${r1(x)}" y1="${mT + ph}" x2="${r1(x)}" y2="${mT + ph + 4}" stroke="${t.axis}" stroke-width="1"/>`);
    out.push(`<text x="${r1(x)}" y="${mT + ph + 16}" text-anchor="middle">${esc(logX ? fmtLog(v) : fmt(v))}</text>`);
  }
  out.push(`</g>`);

  // 曲线 + 误差棒 + 数据点
  const poly = pts.map((p) => `${r1(X(isFinite(p.energy) ? p.energy : p.i + 1))},${r1(Y(p.flux))}`).join(" ");
  out.push(`<polyline points="${poly}" fill="none" stroke="${t.series}" stroke-width="${t.page.stroke}"/>`);
  for (const p of pts) {
    const x = X(isFinite(p.energy) ? p.energy : p.i + 1);
    const y = Y(p.flux);
    if (isFinite(p.err) && p.err > 0) {
      const e = Math.abs(p.flux * p.err);
      out.push(
        `<line x1="${r1(x)}" y1="${r1(Y(p.flux + e))}" x2="${r1(x)}" y2="${r1(Y(Math.max(p.flux - e, 0)))}" stroke="${t.seriesAlt}" stroke-width="1"/>`,
      );
    }
    out.push(`<circle cx="${r1(x)}" cy="${r1(y)}" r="2" fill="${t.series}"/>`);
  }

  // 轴标题（带单位）
  const xTitle = logX ? "Energy (MeV, log scale)" : "Energy (MeV)";
  out.push(`<text x="${r1(mL + pw / 2)}" y="${H - 6}" text-anchor="middle" fill="${t.text}">${esc(xTitle)}</text>`);
  const yTitle = logY ? "Flux (log scale)" : "Flux";
  const cy = r1(mT + ph / 2);
  out.push(`<text x="12" y="${cy}" fill="${t.text}" transform="rotate(-90 12 ${cy})" text-anchor="middle">${esc(yTitle)}</text>`);

  // 图例（右上角，框内）
  const legend = [
    { color: t.series, text: "通量" },
    { color: t.seriesAlt, text: "1σ 误差" },
  ];
  const lw = Math.max(...legend.map((l) => estimateTextWidth(l.text, fs))) + 26;
  const lh = legend.length * (fs + 6) + 6;
  const lx = mL + pw - lw - 4;
  const ly = mT + 4;
  out.push(`<rect x="${r1(lx)}" y="${r1(ly)}" width="${r1(lw)}" height="${r1(lh)}" fill="none" stroke="${t.border}" stroke-width="0.8"/>`);
  legend.forEach((l, i) => {
    const yy = ly + 9 + i * (fs + 6);
    out.push(`<line x1="${r1(lx + 5)}" y1="${r1(yy)}" x2="${r1(lx + 18)}" y2="${r1(yy)}" stroke="${l.color}" stroke-width="1.6"/>`);
    out.push(`<text x="${r1(lx + 22)}" y="${r1(yy + 3.5)}" fill="${t.text}">${esc(l.text)}</text>`);
  });

  out.push("</svg>");
  return out.join("");
}

function r1(v: number): number {
  return Math.round(v * 10) / 10;
}
