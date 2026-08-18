/**
 * tally 通量 SVG 折线图（纯函数，vitest 可测）。
 * 无图表依赖：直接生成内联 SVG 字符串，OutputTab 弹窗渲染。
 * y 轴自动选择：通量跨 >100 倍时用对数刻度，否则线性。
 */
import type { TallyRow } from "./outputParser";

const M = { l: 70, r: 20, t: 20, b: 45 };

function fmt(v: number): string {
  if (v >= 1000 || (v !== 0 && Math.abs(v) < 0.001)) return v.toExponential(1);
  return String(parseFloat(v.toPrecision(3)));
}

export function buildFluxChartSvg(rows: TallyRow[], width = 560, height = 300): string {
  const pts = rows
    .map((r, i) => ({
      i,
      energy: r.energy !== "" ? parseFloat(r.energy) : NaN,
      flux: parseFloat(r.flux),
      err: r.error ? parseFloat(r.error) : NaN,
    }))
    .filter((p) => isFinite(p.flux) && p.flux >= 0);
  if (!pts.length) return '<div class="chart-empty" style="text-align:center;color:#aaa;padding:40px">无有效数据点</div>';

  const pw = width - M.l - M.r;
  const ph = height - M.t - M.b;
  const xs = pts.map((p) => (isFinite(p.energy) ? p.energy : p.i + 1));
  let xMin = Math.min(...xs);
  let xMax = Math.max(...xs);
  if (xMax === xMin) {
    xMin -= 0.5;
    xMax += 0.5;
  }
  const yMax = Math.max(...pts.map((p) => p.flux));
  const yPos = pts.map((p) => p.flux).filter((v) => v > 0);
  const yMinPos = yPos.length ? Math.min(...yPos) : 1;
  const logY = yMinPos > 0 && yMax / yMinPos > 100;
  const yBottom = logY ? yMinPos : 0;
  const yTop = yMax * (logY ? 1.15 : 1.1);

  const X = (v: number) => M.l + ((v - xMin) / (xMax - xMin || 1)) * pw;
  const Y = (v: number) => {
    if (logY) {
      const a = Math.log10(Math.max(v, yBottom));
      const b = Math.log10(yTop);
      const c = Math.log10(yBottom);
      return M.t + ph - ((a - c) / ((b - c) || 1)) * ph;
    }
    return M.t + ph - ((v - yBottom) / ((yTop - yBottom) || 1)) * ph;
  };

  const yTicks: number[] = [];
  if (logY) {
    for (let p = Math.pow(10, Math.floor(Math.log10(yBottom))); p <= yTop * 1.0001; p *= 10) {
      yTicks.push(p);
    }
  } else {
    const step = (yTop - yBottom) / 5;
    for (let k = 0; k <= 5; k++) yTicks.push(yBottom + step * k);
  }
  const nTicks = Math.min(8, pts.length);
  const xTicks: number[] = [];
  for (let k = 0; k < nTicks; k++) {
    xTicks.push(xMin + ((xMax - xMin) * k) / (nTicks - 1 || 1));
  }

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="Consolas,monospace" font-size="10">`;
  svg += `<line x1="${M.l}" y1="${M.t}" x2="${M.l}" y2="${M.t + ph}" stroke="#888"/>`;
  svg += `<line x1="${M.l}" y1="${M.t + ph}" x2="${M.l + pw}" y2="${M.t + ph}" stroke="#888"/>`;
  for (const t of yTicks) {
    const y = Y(t);
    svg += `<line x1="${M.l}" y1="${y.toFixed(1)}" x2="${M.l + pw}" y2="${y.toFixed(1)}" stroke="#444" stroke-dasharray="2 3"/>`;
    svg += `<text x="${M.l - 6}" y="${(y + 3).toFixed(1)}" text-anchor="end" fill="#aaa">${fmt(t)}</text>`;
  }
  for (const t of xTicks) {
    const x = X(t);
    svg += `<line x1="${x.toFixed(1)}" y1="${M.t + ph}" x2="${x.toFixed(1)}" y2="${M.t + ph + 4}" stroke="#888"/>`;
    svg += `<text x="${x.toFixed(1)}" y="${M.t + ph + 14}" text-anchor="middle" fill="#aaa">${fmt(t)}</text>`;
  }

  const poly = pts
    .map((p) => `${X(isFinite(p.energy) ? p.energy : p.i + 1).toFixed(2)},${Y(p.flux).toFixed(2)}`)
    .join(" ");
  svg += `<polyline points="${poly}" fill="none" stroke="#4caf50" stroke-width="1.5"/>`;
  for (const p of pts) {
    const x = X(isFinite(p.energy) ? p.energy : p.i + 1);
    const y = Y(p.flux);
    if (isFinite(p.err) && p.err > 0) {
      const e = Math.abs(p.flux * p.err);
      const y1 = Y(p.flux + e);
      const y2 = Y(Math.max(p.flux - e, 0));
      svg += `<line x1="${x.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="#ef5350" stroke-width="1"/>`;
    }
    svg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.5" fill="#4caf50"/>`;
  }
  svg += `<text x="${(M.l + pw / 2).toFixed(1)}" y="${height - 4}" text-anchor="middle" fill="#ccc">Energy (MeV)</text>`;
  svg += `<text x="14" y="${(M.t + ph / 2).toFixed(1)}" fill="#ccc" transform="rotate(-90 14 ${(M.t + ph / 2).toFixed(1)})" text-anchor="middle">Flux</text>`;
  svg += "</svg>";
  return svg;
}
