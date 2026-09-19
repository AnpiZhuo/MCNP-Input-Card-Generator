/**
 * figureCanvas — 把「视图 + 图例 + 参数说明」排成**一张论文图**（栅格版）。
 *
 * ## 这个模块存在的理由
 * 用户的原话是"要尽可能像是学术汇报的图"，且"不能把原界面截进去"。
 * 于是出图不是"截屏"，而是**排版**：视图多大、图例放哪、参数写在哪、留白多少、
 * 字体字号、色带刻度——这些规则集中在这里，而不是散进 6 个窗口各写一遍。
 * 删掉它，这套版面逻辑会在每个窗口里重现一次，且慢慢长得各不相同。
 *
 * ## 接口边界
 * 调用方只回答两件事：**这张图由哪些块组成**（`panels`）、**图上要写什么**
 * （`title` / `subtitle`）。像素、留白、缩放、字体、色带刻度全部由这里决定。
 * 2D 矢量图不走这里（走 `vectorFigure`），但**共用同一个 `FigureSpec`**，
 * 这样"图的组成"只描述一次，栅格/矢量两条出口吃同一份描述。
 */
import { themeFor, rgbOf, type PlotTheme } from "./plotTheme";
import { svgToRaster } from "./captureFrame";
import { splitSvg } from "./vectorFigure";

/** 一个图例条目（材料图例 / 迹线说明） */
export interface LegendItem {
  color: string;
  label: string;
}

export type FigurePanel =
  | {
      kind: "image";
      /** 已经栅格化好的画布（3D 视图、切面热图等） */
      canvas: HTMLCanvasElement;
      /** 面板标题（可选，画在面板上方） */
      heading?: string;
    }
  | {
      kind: "svg";
      svg: string;
      /** 该 SVG 的自然尺寸（缩放前的像素） */
      width: number;
      height: number;
      heading?: string;
    }
  | {
      kind: "legend";
      heading?: string;
      items: LegendItem[];
    }
  | {
      kind: "colorbar";
      heading?: string;
      min: number;
      max: number;
      unit: string;
      /** 刻度标签格式（缺省用紧凑科学计数） */
      format?: (v: number) => string;
    };

export interface FigureSpec {
  /** 主标题（一般写视图名，如「3D 几何 + 体积计数」） */
  title?: string;
  /** 副标题（参数行：tally 号 / 能量区间 / 分辨率 / 视角等） */
  subtitle?: string;
  panels: FigurePanel[];
  /** 脚注（数据来源、文件路径等） */
  caption?: string;
  theme?: "paper" | "screen";
  /** 内容区高度（像素）；缺省 420。所有面板按此高度等比缩放，行内对齐 */
  contentHeight?: number;
  /**
   * 面板最长边的上限（像素，缺省 `PRINT_MAX_PANEL_SIDE`）。
   *
   * 为什么要有这一条：面板尺寸原先**完全跟着源画布走** —— 3D 视图的 WebGL 画布
   * 是「窗口再乘 DPR」，同一张卡在不同人机器上导出的图尺寸能差一倍（实测见过
   * 280×233 与 609×822 两种）。出图是**交付物**，尺寸不该由谁的窗口大决定。
   * 这里只做"缩到不再超过上限"，源本来就小就原样用，不做放大。
   */
  maxPanelSide?: number;
  /**
   * 底色：缺省 `null`（**透明**）。
   *
   * PNG 支持 alpha，透明底叠在任意底色上都干净，所以默认透明；
   * "整幅颜色填充"的图（fmesh 切面热图）由调用方显式传 `"#ffffff"`。
   * 与 `renderFigure(spec, { background })` 的同名选项等价，写进 spec 是为了
   * 让"这张图要不要白底"这条决策跟图一起走，而不是散在门面里。
   */
  background?: string | null;
}

/**
 * 出图版面的**印张基准**：任意面板最长边不超过这个像素数。
 *
 * 依据：导出栅格一律 2×（见 `exportFigure.RASTER_SCALE`），
 * 所以 640 → 1280px 实物图；按论文双栏 96 mm 摆放时约 340 dpi，
 * 标题（15px × 2）约 9 pt —— 缩放后仍然读得清。在此之前 3D 图会按画布原始
 * 尺寸出图，窄窗口下能导出 609×822 的竖长条，字却只有 6 pt。
 */
export const PRINT_MAX_PANEL_SIDE = 640;

/** 内容区高度上限：竖长条画面不许把版面撑成"一米长的图" */
const PRINT_MAX_CONTENT_HEIGHT = 560;

export interface FigureLayout {
  canvas: HTMLCanvasElement;
  width: number;
  height: number;
}

/** 紧凑数值格式（色带刻度用）：整数直出，大/小值走指数 */
export function formatTick(v: number): string {
  if (!Number.isFinite(v)) return String(v);
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e5 || a < 1e-3)) return v.toExponential(1);
  return Number.isInteger(v) ? String(v) : String(parseFloat(v.toPrecision(3)));
}

/** 色带刻度：等距 n+1 个（与 `ColorLegend.legendTicks` 同口径） */
export function colorbarTicks(min: number, max: number, n = 4): number[] {
  const count = Math.max(1, Math.floor(n));
  const out: number[] = [];
  for (let i = 0; i <= count; i++) out.push(min + ((max - min) * i) / count);
  return out;
}

const LEGEND_ROW_H = 22;
const LEGEND_MAX_ROWS = 14;
const LEGEND_SWATCH = 10;
const LEGEND_TEXT_GAP = 4;

/**
 * 图例面板的实测尺寸。
 *
 * ⚠️ **单列竖排，不分成两列**。历史实现是"每行两个条目"，
 * 于是两条短标签就被排在两个相隔 90px 的列上、图例面板因此恒有半幅空白；
 * 实测一张 560px 宽的 3D 导出图里，右侧约 35% 是"只有第二列小字"的死区。
 * 论文图的图例本来就该是竖排列表，这里不再按条目数改列数。
 *
 * 宽度按最长文字估（中文字宽≈字号，ASCII≈0.55 字号，与 `estimateTextWidth` 同口径）。
 */
function legendMetrics(panel: Extract<FigurePanel, { kind: "legend" }>, theme: PlotTheme) {
  const total = panel.items.length;
  const shown = panel.items.slice(0, LEGEND_MAX_ROWS);
  const truncated = total - shown.length;
  const rows = shown.length + (truncated > 0 ? 1 : 0);
  const longest = shown.reduce((m, it) => estimateLabelWidth(it.label, theme.page.tickSize), 0);
  const width = Math.round(Math.max(120, Math.min(260, LEGEND_SWATCH + LEGEND_TEXT_GAP + longest + 12)));
  const height = Math.max(LEGEND_ROW_H * 2, rows * LEGEND_ROW_H + 8);
  return { width, height, shown, truncated, rows };
}

/** 标签宽度估算（中文字宽 = 字号，ASCII = 0.55 字号） */
function estimateLabelWidth(text: string, fontSize: number): number {
  let w = 0;
  for (const ch of String(text)) w += /[\u2E80-\u9FFF\uFF00-\uFFEF]/.test(ch) ? fontSize : fontSize * 0.55;
  return w;
}

/**
 * 排版并画出一整张图（栅格）。返回的 canvas 可直接编码 PNG。
 *
 * 版面：标题（+副标题）→ 内容行（各面板等高、居中、水平排列）→ 脚注。
 * 每栏之间有分隔线。
 *
 * **底色默认透明**（`opts.background` 缺省 null）—— 出图一律 PNG，PNG 支持 alpha，
 * 透明底叠在任意底色上都干净；确实需要白底的调用方显式传 `"#ffffff"`。
 */
export function renderFigure(spec: FigureSpec, opts: { background?: string | null } = {}): FigureLayout {
  const theme = themeFor(spec.theme ?? "paper");
  const bg = opts.background !== undefined ? opts.background : null;
  const pad = theme.page.padding;
  const gap = 16;
  const maxSide = Math.max(120, spec.maxPanelSide ?? PRINT_MAX_PANEL_SIDE);

  // ── 单遍量测：先把每个面板按"最长边不超过 maxSide"缩到印张基准，再共用同一内容高度 ──
  type Measured = { panel: FigurePanel; w: number; h: number; heading?: string };
  const sized = spec.panels.map((panel) => {
    if (panel.kind === "image") {
      const cw = Math.max(1, panel.canvas.width);
      const ch = Math.max(1, panel.canvas.height);
      // 只缩不放：源画布本来就小就原样用（放大会糊）
      const s = Math.min(1, maxSide / Math.max(cw, ch));
      return { panel, ar: cw / ch, w: Math.max(40, Math.round(cw * s)), h: Math.max(40, Math.round(ch * s)), heading: panel.heading };
    }
    if (panel.kind === "svg") {
      // 等比用**用户坐标范围**（viewBox 优先）算长宽比：只按 width/height 会与
      // 负原点/用户单位的 SVG 不一致（截面窗口导出的 SVG 正是这种）。
      const vb = splitSvg(panel.svg).viewBox;
      const sw = vb ? vb[2] : panel.width;
      const sh = Math.max(1e-9, vb ? vb[3] : panel.height);
      const s = Math.min(1, maxSide / Math.max(sw, sh));
      return { panel, ar: sw / sh, w: Math.max(40, Math.round(sw * s)), h: Math.max(40, Math.round(sh * s)), heading: panel.heading };
    }
    if (panel.kind === "colorbar") {
      return { panel, ar: 0, w: 0, h: 0, heading: panel.heading };
    }
    const m = legendMetrics(panel, theme);
    return { panel, ar: 0, w: m.width, h: m.height, heading: panel.heading };
  });

  // 内容高度 = 最高的位图面板（钳到上限），缺省用调用方的 contentHeight
  const naturalH = Math.max(0, ...sized.filter((s) => s.h > 0).map((s) => s.h));
  const contentH = Math.min(PRINT_MAX_CONTENT_HEIGHT, Math.max(160, naturalH || (spec.contentHeight ?? 420)));

  const measured: Measured[] = sized.map((s) => {
    if (s.panel.kind === "image" || s.panel.kind === "svg") {
      // 面板框 = 等比缩放到内容高度（图不会被拉伸；窄画面两侧留白）
      return { panel: s.panel, w: Math.max(40, Math.round(contentH * s.ar)), h: contentH, heading: s.heading };
    }
    if (s.panel.kind === "colorbar") {
      return { panel: s.panel, w: 220, h: contentH, heading: s.heading };
    }
    return { panel: s.panel, w: s.w, h: contentH, heading: s.heading };
  });

  const contentW = measured.reduce((s, m) => s + m.w, 0) + gap * Math.max(0, measured.length - 1);
  const headH = spec.title ? theme.page.titleSize + 10 + (spec.subtitle ? theme.page.labelSize + 8 : 0) : 0;
  const width = Math.max(320, Math.round(contentW + pad * 2));

  // 脚注可能很长：先按可用宽度折行，再据实际行数算高度（原先单行直接画出边界外）
  const capLines: string[] = [];
  if (spec.caption) {
    ctxProbe.font = `${theme.page.captionSize}px ${theme.fontFamily}`;
    capLines.push(...wrapText(ctxProbe, spec.caption, width - pad * 2));
  }
  const capH = capLines.length ? capLines.length * (theme.page.captionSize + 4) + 8 : 0;
  const height = Math.round(pad + headH + contentH + capH + pad);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return { canvas, width, height };

  if (bg !== null) {
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, width, height);
  }

  let y = pad;
  // ── 标题 / 副标题 ──
  if (spec.title) {
    ctx.fillStyle = theme.text;
    ctx.font = `600 ${theme.page.titleSize}px ${theme.fontFamily}`;
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(spec.title, pad, y);
    y += theme.page.titleSize + 10;
    if (spec.subtitle) {
      ctx.fillStyle = theme.textMuted;
      ctx.font = `${theme.page.labelSize}px ${theme.fontFamily}`;
      ctx.fillText(spec.subtitle, pad, y);
      y += theme.page.labelSize + 8;
    }
  }

  // ── 内容行：逐面板绘制 ──
  const contentTop = y;
  let x = pad;
  measured.forEach((m, i) => {
    if (i > 0) {
      ctx.strokeStyle = theme.border;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x - gap / 2, contentTop + 6);
      ctx.lineTo(x - gap / 2, contentTop + m.h - 6);
      ctx.stroke();
    }
    m.heading && drawHeading(ctx, m.heading, x, contentTop, m.w, theme);
    const top = m.heading ? contentTop + headingHeight(theme) : contentTop;
    const h = m.h - (m.heading ? headingHeight(theme) : 0);
    drawPanel(ctx, m.panel, x, top, m.w, h, theme);
    x += m.w + gap;
  });

  // ── 脚注（可多行；行数在量测阶段已经算出） ──
  if (capLines.length) {
    ctx.fillStyle = theme.caption;
    ctx.font = `${theme.page.captionSize}px ${theme.fontFamily}`;
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    const lineH = theme.page.captionSize + 4;
    capLines.forEach((line, i) => {
      ctx.fillText(line, pad, height - pad - (capLines.length - 1 - i) * lineH);
    });
  }

  return { canvas, width, height };
}

/**
 * 量文字用的探针 ctx。
 *
 * canvas 的 `measureText` 必须挂在某个 2D 上下文上；拿不到（jsdom 无 canvas 包）
 * 时退回 `vectorFigure.estimateTextWidth` 的粗估，**不因此抛错**——
 * 出图链路里"少一次精确量宽"远好过"整张图导不出来"。
 */
let probeCtx: CanvasRenderingContext2D | null | undefined;
const ctxProbe: { font: string; measureText(t: string): { width: number } } = {
  font: "",
  measureText(t: string) {
    if (probeCtx === undefined) {
      try {
        probeCtx = document.createElement("canvas").getContext("2d");
      } catch {
        probeCtx = null;
      }
    }
    if (probeCtx) {
      probeCtx.font = this.font;
      return probeCtx.measureText(t);
    }
    const size = parseFloat(/(\d+(?:\.\d+)?)px/.exec(this.font)?.[1] ?? "10") || 10;
    return { width: estimateLabelWidth(t, size) };
  },
};

/**
 * 按像素宽度折行（中文按字断，ASCII 尽量按空格断）。
 *
 * 为什么不用 canvas 自带的换行：**canvas 没有自动换行**。原先脚注是单行 `fillText`，
 * 实测 55 个中文字符就会顶到画面边缘、再长直接出界（图注是唯一承载"数据来源/参数"
 * 的地方，被截掉等于信息丢失）。
 */
export function wrapText(
  ctx: { measureText(t: string): { width: number } },
  text: string,
  maxWidth: number,
): string[] {
  if (!text) return [];
  if (maxWidth <= 0 || ctx.measureText(text).width <= maxWidth) return [text];
  const lines: string[] = [];
  let line = "";
  const pushLine = () => { if (line) { lines.push(line); line = ""; } };
  // 先按"可断点"切段：ASCII 单词整体不断，中文逐字可断
  for (const token of String(text).match(/[\u2E80-\u9FFF\uFF00-\uFFEF]|[^\s\u2E80-\u9FFF\uFF00-\uFFEF]+|\s+/g) ?? []) {
    const tryLine = line + token;
    if (ctx.measureText(tryLine).width <= maxWidth || !line) {
      line = tryLine;
      continue;
    }
    pushLine();
    line = token.replace(/^\s+/, "");
  }
  pushLine();
  return lines.length ? lines : [text];
}

function headingHeight(theme: PlotTheme): number {
  return theme.page.labelSize + 8;
}

/**
 * 异步准备：把 `svg` 面板栅格化进 `image` 面板，供**同步**的 `renderFigure` 绘制。
 *
 * 这是 `svg` 面板唯一的用途——调用方若已持有 canvas（3D 视图、切面热图），
 * 直接给 `image` 面板即可，**不需要**调本函数。
 *
 * @param scale SVG 栅格化倍数（默认 2：与位图出口一致，避免文字发虚）
 */
export async function preparePanels(spec: FigureSpec, scale = 2): Promise<FigureSpec> {
  const panels: FigurePanel[] = [];
  for (const p of spec.panels) {
    if (p.kind !== "svg") { panels.push(p); continue; }
    const canvas = await svgToRaster(p.svg, { scale, background: null });
    // 栅格化失败 → 保留原面板（renderFigure 会画"未准备"提示，便于发现问题而非静默空白）
    panels.push(canvas ? { kind: "image", canvas, heading: p.heading } : p);
  }
  return { ...spec, panels };
}

function drawHeading(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, w: number, theme: PlotTheme): void {
  ctx.fillStyle = theme.textMuted;
  ctx.font = `600 ${theme.page.labelSize}px ${theme.fontFamily}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText(clip(ctx, text, w), x, y);
  ctx.strokeStyle = theme.border;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x, y + headingHeight(theme) - 4);
  ctx.lineTo(x + w, y + headingHeight(theme) - 4);
  ctx.stroke();
}

function drawPanel(ctx: CanvasRenderingContext2D, panel: FigurePanel, x: number, y: number, w: number, h: number, theme: PlotTheme): void {
  if (panel.kind === "image") {
    // 等比内嵌，水平/垂直居中
    const ar = panel.canvas.width / Math.max(1, panel.canvas.height);
    let dw = w, dh = w / ar;
    if (dh > h) { dh = h; dw = h * ar; }
    ctx.drawImage(panel.canvas, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
    return;
  }
  if (panel.kind === "svg") {
    // SVG 面板必须在**外部异步准备阶段**栅格化成 canvas（见 `preparePanels`）：
    // 浏览器不允许在 canvas 上直接画 SVG 文本，只能走 Image 解码，那是异步的。
    // 走到这里说明调用方漏了准备步骤——画外框提示，而不是静默出空白。
    const ar = panel.width / Math.max(1, panel.height);
    let dw = w, dh = w / ar;
    if (dh > h) { dh = h; dw = h * ar; }
    ctx.strokeStyle = theme.border;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
    ctx.setLineDash([]);
    ctx.fillStyle = theme.textMuted;
    ctx.font = `${theme.page.tickSize}px ${theme.fontFamily}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("（SVG 面板未准备）", x + w / 2, y + h / 2);
    return;
  }
  if (panel.kind === "legend") {
    drawLegend(ctx, panel, x, y, w, h, theme);
    return;
  }
  drawColorbar(ctx, panel, x, y, w, h, theme);
}

function drawLegend(ctx: CanvasRenderingContext2D, panel: Extract<FigurePanel, { kind: "legend" }>, x: number, y: number, w: number, h: number, theme: PlotTheme): void {
  const m = legendMetrics(panel, theme);
  ctx.font = `${theme.page.tickSize}px ${theme.fontFamily}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  const top = y + 6;
  const entries: { color: string; label: string }[] = [...m.shown];
  if (m.truncated > 0) entries.push({ color: theme.textMuted, label: `…等 ${panel.items.length} 项` });
  entries.forEach((it, i) => {
    const cy = top + i * LEGEND_ROW_H + LEGEND_ROW_H / 2;
    if (cy > y + h) return;
    ctx.fillStyle = it.color;
    ctx.fillRect(x, cy - 5, LEGEND_SWATCH, LEGEND_SWATCH);
    ctx.strokeStyle = theme.border;
    ctx.lineWidth = 1;
    ctx.strokeRect(x, cy - 5, LEGEND_SWATCH, LEGEND_SWATCH);
    ctx.fillStyle = theme.text;
    ctx.fillText(clip(ctx, it.label, w - LEGEND_SWATCH - 6), x + LEGEND_SWATCH + LEGEND_TEXT_GAP, cy);
  });
}

function drawColorbar(ctx: CanvasRenderingContext2D, panel: Extract<FigurePanel, { kind: "colorbar" }>, x: number, y: number, w: number, h: number, theme: PlotTheme): void {
  const barH = Math.min(260, h - 60);
  const barW = 22;
  const bx = x + 30;
  const by = y + 24;
  const fmt = panel.format ?? formatTick;
  const steps = Math.max(2, theme.colormap.length * 24);
  for (let i = 0; i < steps; i++) {
    const t = i / (steps - 1);
    ctx.fillStyle = sampleColormap(theme.colormap, 1 - t);
    ctx.fillRect(bx, by + barH * t, barW, barH / steps + 1);
  }
  ctx.strokeStyle = theme.border;
  ctx.lineWidth = 1;
  ctx.strokeRect(bx, by, barW, barH);

  const ticks = colorbarTicks(panel.min, panel.max, 5);
  ctx.font = `${theme.page.tickSize}px ${theme.fontFamily}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ticks.forEach((t, i) => {
    const ty = by + (barH * i) / (ticks.length - 1);
    ctx.strokeStyle = theme.axis;
    ctx.beginPath();
    ctx.moveTo(bx + barW, ty);
    ctx.lineTo(bx + barW + 5, ty);
    ctx.stroke();
    ctx.fillStyle = theme.text;
    ctx.fillText(clip(ctx, fmt(t), w - (bx - x) - barW - 12), bx + barW + 9, ty);
  });
  ctx.fillStyle = theme.textMuted;
  ctx.font = `600 ${theme.page.tickSize}px ${theme.fontFamily}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  // 单位写在色带下方；位置按"色带走完后 26px"，但**不越过面板底边**（长单位名原先会压出框外）
  const unitY = Math.min(by + barH + 26, y + h - 2);
  ctx.fillText(clip(ctx, panel.unit, w - 12), x + 4, unitY);
}

/** 在色带上取色（线性插值；t∈[0,1]） */
export function sampleColormap(colors: string[], t: number): string {
  const n = colors.length - 1;
  const x = Math.min(1, Math.max(0, t)) * n;
  const i = Math.min(n - 1, Math.floor(x));
  const f = x - i;
  const a = rgbOf(colors[i]);
  const b = rgbOf(colors[i + 1]);
  const mix = (p: number, q: number) => Math.round(p + (q - p) * f);
  return `rgb(${mix(a.r, b.r)},${mix(a.g, b.g)},${mix(a.b, b.b)})`;
}

/** 文本超宽截断加省略号（canvas 无自动换行） */
function clip(ctx: CanvasRenderingContext2D, text: string, maxW: number): string {
  if (maxW <= 0) return "";
  if (ctx.measureText(text).width <= maxW) return text;
  let s = text;
  while (s.length > 1 && ctx.measureText(s + "…").width > maxW) s = s.slice(0, -1);
  return s + "…";
}
