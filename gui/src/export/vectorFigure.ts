/**
 * vectorFigure — 把「二维矢量图 + 图例 + 参数说明」组合成**一张真矢量图**，并转 PDF。
 *
 * ## 与 figureCanvas（栅格版）的分工
 * 同一个 `FigureSpec` 描述"这张图由哪些块组成"，两条出口各取所需：
 *   - `figureCanvas` → 位图（3D 视图这类**没法矢量化**的必须走它）；
 *   - 本模块        → 纯矢量（截面、tally 曲线、切面等值线……放大不糊，可投期刊）。
 * 之所以不合成一个"万能"模块：位图合成必须同步画 canvas，矢量必须保持 `<path>` 不被栅格化，
 * 两者的实现没有可复用的部分，硬合只会让接口变宽。
 *
 * ## 关键取舍：不解析、不重绘，只做**搬移**
 * 面板内容按原样内联（连同 `<style>` / `<defs>`），只加一层 `translate+scale`。
 * 这样各图自己的生成器（`buildFluxChartSvg`、截面多边形、等值线）仍是唯一权威，
 * 本模块不重复实现任何绘图，只负责**版面**。
 *
 * ## PDF 的一条硬约束（写在接口上，不是藏在实现里）
 * svg2pdf 只能内嵌**已注册**的字体。PDF 标准字体不含中文，而本程序的图注几乎都带中文
 * （"计数"、"能量"、"材料"）。所以 `figureToPdf` 接受一个 `font`（可选，CJK TTF 字节）：
 * 给了 → 真矢量 + 中文可选中；没给 → 调用方**应当**改走栅格 PDF（`figureToPdf` 的返回值
 * `needsRaster` 会明确告知），绝不静默产出"中文全空白"的 PDF。
 */
import { themeFor, type PlotTheme } from "./plotTheme";
import { figureTextBlocks, layoutFigure } from "./figureLayout";

/** 矢量面板：内联进版面的一段 SVG（自带坐标与样式） */
export interface VectorPanel {
  /** 该面板的 SVG 文本 */
  svg: string;
  /** 面板标题（可选） */
  heading?: string;
}

export interface VectorFigureSpec {
  title?: string;
  subtitle?: string;
  panels: VectorPanel[];
  caption?: string;
  theme?: "paper" | "screen";
  /** 内容区高度（px）；缺省 360 */
  contentHeight?: number;
  /**
   * 面板最长边的上限（像素，缺省 640）。与 `FigureSpec.maxPanelSide` 同一口径：
   * 出图是交付物，尺寸不该由源 SVG 的用户单位大小决定（截面 SVG 的 viewBox 是
   * **平面用户坐标**，几毫米的模型与几米的模型能差三个数量级）。
   */
  maxPanelSide?: number;
  /**
   * 底色：`"#ffffff"` 白底 / `null` 透明。
   *
   * ⚠️ 这里**缺省什么都不铺**（保持透明），当前口径与栅格版相反 ——
   * 门面 `exportFigure` 一律显式传 `"#ffffff"`，所以产物仍是白底；
   * 保留"缺省不铺"是为了让矢量出口在将来被直接调用时不会被迫带底。
   * 有颜色填充的图（热图、色块、地图式等值线）**必须**白底，否则透出底色后颜色与色阶对不上。
   */
  background?: string | null;
  /**
   * 材料图例（带色块）。几何面板本身是矢量色块图，"哪个颜色是哪种材料"必须能在图里查到
   * —— 这是期刊硬要求（图内符号必须有说明），也是黑白打印下唯一还能读懂的线索。
   * 排在图右侧、与几何面板同高，与栅格版 `FigurePanel.legend` 同口径。
   */
  legend?: { color: string; label: string }[];
  /**
   * 追加到面板**右侧**的矢量片段（如色带图例），随内容高度对齐。
   * 为什么要这个：有颜色填充的图**必须带色阶刻度**，否则读者无法把颜色换算成数值
   * ——「视图 + 图例/元信息」是出图规格里明确要求的，不是可选装饰。
   * 宽度由调用方在片段内自定（约定 ≤220px）。
   */
  trailing?: { svg: string; width: number; heading?: string };
}

export interface VectorFigure {
  svg: string;
  width: number;
  height: number;
}

/** 从 SVG 文本取出 inner 内容 / 尺寸 / viewBox */
export interface SvgParts {
  inner: string;
  width: number;
  height: number;
  /** 源 viewBox（`[minX,minY,w,h]`）；无 viewBox → null */
  viewBox: [number, number, number, number] | null;
}

/**
 * 拆 SVG 文本 → { inner, width, height, viewBox }。
 *
 * ⚠️ **必须带上 viewBox**：截面窗口导出的 `<svg>` 的 viewBox 是**平面用户坐标**
 * （形如 `-5 -5 10 10`，且宽高比与屏幕像素无关）。若只取 inner 内容而丢掉 viewBox，
 * 用户单位会被当成像素直接画 —— 一张 10 单位宽的截面会被当作 10px 塞进面板，
 * 缩成几个像素的墨点（实测踩过）。调用方据 `viewBox` 决定 translate/scale。
 *
 * 尺寸优先 `width/height`，退回 viewBox 宽高；都没有则 400×300 兜底
 * （宁可画大一点，也不静默给 0 —— 0 会在 JSON 里变成 0 宽面板，排查起来很难）。
 */
export function splitSvg(svg: string): SvgParts {
  const stripped = svg
    .replace(/<\?xml[^>]*\?>/g, "")
    .replace(/<!DOCTYPE[^>]*>/gi, "")
    .trim();
  const open = /<svg\b[^>]*>/i.exec(stripped);
  if (!open) return { inner: stripped, width: 400, height: 300, viewBox: null };
  const inner = stripped
    .slice(open.index + open[0].length)
    .replace(/<\/svg\s*>\s*$/i, "");
  const tag = open[0];
  const num = (re: RegExp) => {
    const m = re.exec(tag);
    return m ? parseFloat(m[1]) : NaN;
  };
  let width = num(/\bwidth\s*=\s*"([\d.]+)/i);
  let height = num(/\bheight\s*=\s*"([\d.]+)/i);
  const vbm = /\bviewBox\s*=\s*"([-\d.eE+]+)[\s,]+([-\d.eE+]+)[\s,]+([\d.eE+]+)[\s,]+([\d.eE+]+)"/i.exec(tag);
  const viewBox: [number, number, number, number] | null = vbm
    ? [parseFloat(vbm[1]), parseFloat(vbm[2]), parseFloat(vbm[3]), parseFloat(vbm[4])]
    : null;
  if (!isFinite(width) || width <= 0) width = viewBox && viewBox[2] > 0 ? viewBox[2] : 400;
  if (!isFinite(height) || height <= 0) height = viewBox && viewBox[3] > 0 ? viewBox[3] : 300;
  return { inner, width, height, viewBox };
}

/**
 * 面板内嵌变换：把源 SVG（含其 viewBox 用户坐标系）等比放进 `w×h` 的框并居中。
 * 返回 `translate(...) scale(...)` 的数值；源内容若带 viewBox 负原点，这里会把它平移到框内。
 */
export function panelTransform(
  parts: SvgParts,
  w: number,
  h: number,
): { tx: number; ty: number; scale: number } {
  // 源内容的**用户坐标**范围：优先 viewBox（真坐标系），否则退回 width/height（像素）
  const vb = parts.viewBox;
  const srcW = vb ? vb[2] : parts.width;
  const srcH = vb ? vb[3] : parts.height;
  const srcX = vb ? vb[0] : 0;
  const srcY = vb ? vb[1] : 0;
  const s = Math.min(w / Math.max(1e-9, srcW), h / Math.max(1e-9, srcH));
  const tx = (w - srcW * s) / 2 - srcX * s;
  const ty = (h - srcH * s) / 2 - srcY * s;
  return { tx, ty, scale: s };
}

/** 转义 XML 文本 */
export function esc(s: string): string {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** 粗略文字宽度估算（无 DOM 时的排版用；中文字宽≈字号，ASCII≈0.55 字号） */
export function estimateTextWidth(text: string, fontSize: number): number {
  let w = 0;
  for (const ch of String(text)) w += /[\u2E80-\u9FFF\uFF00-\uFFEF]/.test(ch) ? fontSize : fontSize * 0.55;
  return w;
}

/**
 * SVG 文本折行（与栅格版 `figureCanvas.wrapText` 同口径）。
 *
 * 为什么矢量侧单独一份而不是共用：栅格版要 `CanvasRenderingContext2D.measureText`
 * （精确但依赖 DOM），矢量侧只该依赖 `estimateTextWidth`（纯函数、可离线测）；
 * 强行共用会让矢量合成在无 DOM 环境（单测/PDF 生成）里挂掉。
 * **两份必须同口径**（中文按字断、ASCII 按词断），改一处要同步另一处。
 */
export function wrapSvgText(text: string, maxWidth: number, fontSize: number): string[] {
  if (!text) return [];
  if (maxWidth <= 0 || estimateTextWidth(text, fontSize) <= maxWidth) return [text];
  const lines: string[] = [];
  let line = "";
  const tokens = String(text).match(/[\u2E80-\u9FFF\uFF00-\uFFEF]|[^\s\u2E80-\u9FFF\uFF00-\uFFEF]+|\s+/g) ?? [];
  for (const token of tokens) {
    if (estimateTextWidth(line + token, fontSize) <= maxWidth || !line) {
      line += token;
      continue;
    }
    if (line) lines.push(line);
    line = token.replace(/^\s+/, "");
  }
  if (line) lines.push(line);
  return lines.length ? lines : [text];
}

/** 色带刻度：等距 n+1 个（与 `ColorLegend.legendTicks` 同口径） */
export function vectorTicks(min: number, max: number, n = 4): number[] {
  const count = Math.max(1, Math.floor(n));
  const out: number[] = [];
  for (let i = 0; i <= count; i++) out.push(min + ((max - min) * i) / count);
  return out;
}

/** 刻度数值格式：整数直出，大/小值指数 */
export function tickText(v: number): string {
  if (!Number.isFinite(v)) return String(v);
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e5 || a < 1e-3)) return v.toExponential(1);
  return Number.isInteger(v) ? String(v) : String(parseFloat(v.toPrecision(3)));
}

const GAP = 14;

/**
 * 组合矢量图。
 *
 * 版面与栅格版一致（标题 / 副标题 / 面板行 / 脚注）。
 * 底色由调用方给（`spec.background`）；当前门面 `exportFigure` 一律传白底
 * （2026-09-19 用户裁决"png 都改为白底"），因此产物是不透明的白底 PNG。
 */
export function buildVectorFigure(spec: VectorFigureSpec): VectorFigure {
  const theme = themeFor(spec.theme ?? "paper");
  const pad = theme.page.padding;
  const maxSide = Math.max(120, spec.maxPanelSide ?? 640);
  const parts: string[] = [];
  const defs: string[] = [];

  // ── 面板量测：先按"最长边不超过 maxSide"定印张基准，再统一内容高度 ──
  const measured = spec.panels.map((p) => {
    const s = splitSvg(p.svg);
    const ar = (s.viewBox ? s.viewBox[2] : s.width) / Math.max(1e-9, s.viewBox ? s.viewBox[3] : s.height);
    const long = Math.max(s.viewBox ? s.viewBox[2] : s.width, s.viewBox ? s.viewBox[3] : s.height);
    const k = Math.min(1, maxSide / Math.max(1e-9, long));
    return { panel: p, parts: s, ar, native: Math.max(120, Math.round(long * k)) };
  });
  const contentH = spec.contentHeight
    ?? Math.min(640, Math.max(200, ...measured.map((m) => (m.ar >= 1 ? Math.round(m.native / m.ar) : m.native))));

  const sized = measured.map((m) => ({ ...m, w: Math.max(40, Math.round(contentH * m.ar)), h: contentH }));

  /** 图例面板宽度：按最长标签估（与栅格版 `legendMetrics` 同口径，单列竖排、上限 260） */
  const legendItems = spec.legend ?? [];
  const legendW = legendItems.length
    ? Math.round(Math.max(120, Math.min(260, 10 + 4 + legendItems.reduce((m, it) => Math.max(m, estimateTextWidth(it.label, theme.page.tickSize)), 0) + 12)))
    : 0;

  const contentW = sized.reduce((s, m) => s + m.w, 0) + GAP * Math.max(0, sized.length - 1)
    + (legendW ? legendW + GAP : 0)
    + (spec.trailing ? spec.trailing.width + GAP : 0);
  const width = Math.max(320, Math.round(contentW + pad * 2));

  /**
   * ── 图下区（版面规则见 `figureLayout` 模块说明）──
   * **图题在图的下方居中、图注在左下**：顺序与间距由公用模块算出，本渲染器只画。
   * 原先本文件自己算了一份（而且**标题还画在图上方**，与栅格版不一致 —— 用户实机看到的就是这种）。
   */
  const noteTexts = [spec.subtitle, spec.caption].filter((t): t is string => !!t && String(t) !== "");
  const noteLines: string[] = [];
  for (const t of noteTexts) noteLines.push(...wrapSvgText(t, width - pad * 2, theme.page.captionSize));
  const sizing = layoutFigure({
    theme,
    contentHeight: contentH,
    hasTitle: !!spec.title,
    noteLineCount: noteLines.length,
  });
  const height = sizing.height;

  // 底色（缺省透明）：铺在**最底层**，让所有面板叠在它上面
  if (spec.background) {
    parts.push(`<rect x="0" y="0" width="${width}" height="${height}" fill="${spec.background}"/>`);
  }

  /** 图下区起点（内容行之后），供标题/图注共用 */
  const belowTop = sizing.belowTop;

  // 内容行从顶部开始（标题已移到图下，见上方说明）
  const contentTop = sizing.contentTop;
  let x = pad;
  sized.forEach((m, i) => {
    if (i > 0) {
      parts.push(
        `<line x1="${x - GAP / 2}" y1="${contentTop + 6}" x2="${x - GAP / 2}" y2="${contentTop + m.h - 6}" stroke="${theme.border}" stroke-width="1"/>`,
      );
    }
    let top = contentTop;
    if (m.panel.heading) {
      parts.push(
        `<text x="${x}" y="${top + theme.page.labelSize}" font-family="${esc(theme.fontFamily)}" font-size="${theme.page.labelSize}" font-weight="600" fill="${theme.textMuted}">${esc(m.panel.heading)}</text>`,
        `<line x1="${x}" y1="${top + theme.page.labelSize + 4}" x2="${x + m.w}" y2="${top + theme.page.labelSize + 4}" stroke="${theme.border}" stroke-width="1"/>`,
      );
      top += theme.page.labelSize + 8;
    }
    const h = m.h - (top - contentTop);
    // 用 viewBox 参与变换（源可能是"用户坐标 + 负原点"，见 splitSvg 的说明）
    const tf = panelTransform(m.parts, m.w, h);
    parts.push(
      `<g transform="translate(${round(tf.tx)},${round(tf.ty)}) scale(${round(tf.scale, 5)})">${m.parts.inner}</g>`,
    );
    x += m.w + GAP;
  });

  // ── 材料图例（带色块，单列竖排；与栅格版 `drawLegend` 同口径）──
  if (legendItems.length) {
    const lx = x;
    parts.push(
      `<line x1="${lx - GAP / 2}" y1="${contentTop + 6}" x2="${lx - GAP / 2}" y2="${contentTop + contentH - 6}" stroke="${theme.border}" stroke-width="1"/>`,
    );
    const ROW = 22;
    const SW = 10;
    legendItems.slice(0, 14).forEach((it, i) => {
      const cy = contentTop + 6 + i * ROW + ROW / 2;
      parts.push(
        `<rect x="${lx}" y="${round(cy - SW / 2)}" width="${SW}" height="${SW}" fill="${it.color}" stroke="${theme.border}" stroke-width="1"/>`,
        `<text x="${lx + SW + 4}" y="${round(cy + theme.page.tickSize / 3)}" font-family="${esc(theme.fontFamily)}" font-size="${theme.page.tickSize}" fill="${theme.text}">${esc(it.label)}</text>`,
      );
    });
    x += legendW + GAP;
  }

  // 尾随片段（色带图例）：与内容同高、贴右，独立不参与面板等比缩放（色带是标尺，不该被拉伸）
  if (spec.trailing) {
    const t = spec.trailing;
    parts.push(
      `<line x1="${x - GAP / 2}" y1="${contentTop + 6}" x2="${x - GAP / 2}" y2="${contentTop + contentH - 6}" stroke="${theme.border}" stroke-width="1"/>`,
    );
    let top = contentTop;
    if (t.heading) {
      parts.push(
        `<text x="${x}" y="${top + theme.page.labelSize}" font-family="${esc(theme.fontFamily)}" font-size="${theme.page.labelSize}" font-weight="600" fill="${theme.textMuted}">${esc(t.heading)}</text>`,
        `<line x1="${x}" y1="${top + theme.page.labelSize + 4}" x2="${x + t.width}" y2="${top + theme.page.labelSize + 4}" stroke="${theme.border}" stroke-width="1"/>`,
      );
      top += theme.page.labelSize + 8;
    }
    const inner = splitSvg(t.svg);
    parts.push(`<g transform="translate(${round(x)},${round(top)})">${inner.inner}</g>`);
  }

  // ── 图下区：居中图题 → 左对齐图注（坐标全部来自公用版面模块 figureLayout）──
  for (const b of figureTextBlocks({ theme, sizing, width, title: spec.title, noteLines })) {
    // ⚠️ 图题**不加 font-weight="600"**：PDF 里只注册了 normal 字重，
    // svg2pdf 遇到 600 会去找 '600normal' 字体并告警（"Unable to look up font label"），
    // 中文环境下还可能导致该行落回缺中文字形的标准字体。宁可少一个粗细层次。
    const weight = b.kind === "title" ? "" : "";
    const anchor = b.align === "center" ? ` text-anchor="middle"` : "";
    parts.push(
      `<text x="${round(b.x)}" y="${round(b.y)}"${anchor} font-family="${esc(theme.fontFamily)}" font-size="${b.size}"${weight} fill="${b.color}">${esc(b.text)}</text>`,
    );
  }

  const svg = [
    `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    defs.length ? `<defs>${defs.join("")}</defs>` : "",
    ...parts,
    `</svg>`,
  ].join("");
  return { svg, width, height };
}

function round(v: number, digits = 2): number {
  const p = Math.pow(10, digits);
  return Math.round(v * p) / p;
}

/** 色带（矢量）：给 fmesh 切面图当图例用 */
export function vectorColorbar(x: number, y: number, w: number, h: number, colors: string[], min: number, max: number, unit: string, theme?: PlotTheme): string {
  const t = theme ?? themeFor("paper");
  const id = "cb" + Math.abs(hash(`${x},${y},${w},${h},${min},${max}`));
  const stops = colors
    .map((c, i) => `<stop offset="${(i / (colors.length - 1)).toFixed(3)}" stop-color="${c}"/>`)
    .join("");
  const ticks = vectorTicks(min, max, 4);
  const tickEls = ticks
    .map((v, i) => {
      const ty = y + (h * i) / (ticks.length - 1);
      return (
        `<line x1="${x + w}" y1="${round(ty)}" x2="${x + w + 5}" y2="${round(ty)}" stroke="${t.axis}" stroke-width="1"/>` +
        `<text x="${x + w + 9}" y="${round(ty + 3)}" font-family="${esc(t.fontFamily)}" font-size="${t.page.tickSize}" fill="${t.text}">${esc(tickText(v))}</text>`
      );
    })
    .join("");
  return (
    `<defs><linearGradient id="${id}" x1="0" y1="1" x2="0" y2="0">${stops}</linearGradient></defs>` +
    `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="url(#${id})" stroke="${t.border}" stroke-width="1"/>` +
    tickEls +
    `<text x="${x}" y="${round(y + h + 16)}" font-family="${esc(t.fontFamily)}" font-size="${t.page.tickSize}" font-weight="600" fill="${t.textMuted}">${esc(unit)}</text>`
  );
}

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}

/** 图例（矢量）：材料色块 + 名称 */
export function vectorLegend(x: number, y: number, items: { color: string; label: string }[], theme?: PlotTheme): string {
  const t = theme ?? themeFor("paper");
  const rowH = 18;
  return items
    .map((it, i) => {
      const cy = y + i * rowH;
      return (
        `<rect x="${x}" y="${round(cy)}" width="10" height="10" fill="${it.color}" stroke="${t.border}" stroke-width="1"/>` +
        `<text x="${x + 15}" y="${round(cy + 9)}" font-family="${esc(t.fontFamily)}" font-size="${t.page.tickSize}" fill="${t.text}">${esc(it.label)}</text>`
      );
    })
    .join("");
}

/* ─────────────────────────── SVG → PDF ─────────────────────────── */

export interface PdfFont {
  /** 字体名（注册到 PDF 里的名字） */
  name: string;
  /** TTF 字节（必须覆盖图中出现的所有字符，通常是中文） */
  data: Uint8Array;
}

export type PdfOutcome =
  | { ok: true; bytes: Uint8Array }
  /** 图里含中文但没有可用中文字体 → 调用方应改走栅格 PDF（**不要**静默出空白中文） */
  | { ok: false; reason: "needsCjkFont" }
  /** 产物体积超上限（字体未子集化时会把整份字体塞进去）→ 调用方改走栅格 PDF */
  | { ok: false; reason: "tooLarge"; bytes: number }
  | { ok: false; reason: "error"; message: string };

/** 判断一段文本是否含非 ASCII（即需要 CJK 字体） */
export function needsCjkFont(svg: string): boolean {
  return /[^\x00-\x7F]/.test(stripMarkup(svg));
}

/** 去掉标签/属性，只留文本节点，避免把属性里的中文也算进来（保守即可） */
function stripMarkup(svg: string): string {
  return svg.replace(/<[^>]*>/g, (m) => (/^<text/i.test(m) ? m : " "));
}

/**
 * SVG 文本 → PDF 时需要量文字宽度，svg2pdf 默认走 `SVGTextElement.getBBox()`。
 * 真实 WebView2 有它；但**任何缺 `getBBox` 的环境会让整条导出直接失败**
 * （实测 jsdom：`TypeError: s.getBBox is not a function`）。
 * 这里补一层 canvas `measureText` 兜底：量得略粗，但保证导出不因测量能力缺失而整体失败。
 * 幂等——已有 `getBBox` 的环境（真机）完全不受影响。
 */
export function ensureTextMeasurement(): void {
  if (typeof document === "undefined") return;
  const proto = (globalThis as any)?.SVGElement?.prototype;
  if (!proto || typeof proto.getBBox === "function") return;
  proto.getBBox = function (this: SVGElement) {
    const text = (this as any).textContent ?? "";
    let size = 12;
    try {
      const fs = (this as any).getAttribute?.("font-size");
      if (fs) size = parseFloat(fs) || 12;
    } catch { /* 用默认字号 */ }
    const w = measureTextWidth(text, size);
    return { x: 0, y: -size, width: w, height: size * 1.2 };
  };
}

let measureCtx: CanvasRenderingContext2D | null | undefined;
function measureTextWidth(text: string, fontSize: number): number {
  if (measureCtx === undefined) {
    try {
      measureCtx = document.createElement("canvas").getContext("2d");
    } catch {
      measureCtx = null;
    }
  }
  if (measureCtx) {
    measureCtx.font = `${fontSize}px sans-serif`;
    return measureCtx.measureText(text).width;
  }
  return estimateTextWidth(text, fontSize);
}

/**
 * 矢量 SVG → PDF 字节。
 *
 * @param font 中文字体（含中文的图必传，否则返回 `needsCjkFont`）
 * @param maxBytes 体积上限：jsPDF 对嵌入字体**不保证子集化**，一份 15 MB 的系统中文字体
 *   可能整份进 PDF。超限就返回 `tooLarge` 让调用方走栅格（**宁可位图，不要 15 MB 的图**）。
 */
export async function figureToPdf(
  fig: { svg: string; width: number; height: number },
  opts: { font?: PdfFont; background?: string | null; maxBytes?: number } = {},
): Promise<PdfOutcome> {
  const maxBytes = opts.maxBytes ?? 6_000_000;
  try {
    ensureTextMeasurement();
    const { jsPDF } = await import("jspdf");
    // ⚠️ 必须引 ES 构建（见 vite.config.ts 的 alias 注释）：UMD 在 ESM 里加载即崩
    await import("svg2pdf.js");
    const doc: any = new jsPDF({ unit: "pt", format: [fig.width, fig.height], orientation: fig.width >= fig.height ? "landscape" : "portrait" });
    if (opts.font) {
      doc.addFileToVFS(opts.font.name, bytesToBase64(opts.font.data));
      doc.addFont(opts.font.name, opts.font.name, "normal");
      doc.setFont(opts.font.name);
    } else if (needsCjkFont(fig.svg)) {
      return { ok: false, reason: "needsCjkFont" };
    }
    const host = document.createElement("div");
    host.style.position = "fixed";
    host.style.left = "-10000px";
    host.innerHTML = fig.svg;
    const el = host.querySelector("svg") as SVGElement | null;
    if (!el) return { ok: false, reason: "error", message: "SVG 解析失败" };
    document.body.appendChild(host);
    try {
      if (opts.background) {
        doc.setFillColor(opts.background);
        doc.rect(0, 0, fig.width, fig.height, "F");
      }
      await doc.svg(el, { x: 0, y: 0, width: fig.width, height: fig.height });
      const buf = doc.output("arraybuffer") as ArrayBuffer;
      const bytes = new Uint8Array(buf);
      if (bytes.byteLength > maxBytes) return { ok: false, reason: "tooLarge", bytes: bytes.byteLength };
      return { ok: true, bytes };
    } finally {
      host.remove();
    }
  } catch (e: any) {
    return { ok: false, reason: "error", message: String(e?.message || e) };
  }
}

function bytesToBase64(bytes: Uint8Array): string {
  let bin = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
}
