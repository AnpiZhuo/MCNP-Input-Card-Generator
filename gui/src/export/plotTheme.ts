/**
 * plotTheme — 出图配色的**单一权威**（屏幕一套 / 论文一套）。
 *
 * ## 为什么要有这个模块
 * 屏幕上整套 UI 是深色主题（浅色轴线 + 亮色曲线），而导出的图要贴进论文/报告
 * （白底、深色轴线文字）。如果每个图各自写一套导出颜色，以后调色要满仓库找。
 * 所以：**出图相关的颜色只在这里定义**，出图链路一律从 `themeFor(kind)` 取。
 *
 * ## ⚠️ 色带不在这里定义（避免成为"第三份色表"）
 * 色带锚点的单一事实来源是 `volume/colorize.WEATHER_STOPS`
 * （契约 `docs/contracts/meshtal-visualization.md` §4.3.1：python 与 TS 必须一致）。
 * 本模块的 `COLORMAP` 是从它**派生**的十六进制视图，不是另一份定义；
 * 改色请改锚点。曾一度在这里硬编码 5 色，等于新开一份必分叉的色表 —— 已改回派生。
 *
 * ## 两条硬规则
 * 1. `screen` 与 `paper` 只差"背景明暗"，**色相不动**——材料色、色带色相在屏幕与
 *    导出图上必须能一一对应，否则用户无法照着屏幕认导出的图。
 * 2. 论文主题只负责"把深色底换成白底后仍然看得见"：轴线/文字加深、网格变浅灰。
 *    **不做全局反色**（把材料的亮色反成暗色会让图与屏幕对不上）。
 */
import { WEATHER_STOPS } from "../volume/colorize";

export type PlotThemeKind = "screen" | "paper";

export interface PlotTheme {
  kind: PlotThemeKind;
  /** 画布底色；null = 透明（导出矢量图默认透明底） */
  background: string | null;
  /** 坐标轴 / 外框 */
  axis: string;
  /** 网格线 */
  grid: string;
  /** 主文字（标题、量值） */
  text: string;
  /** 次级文字（刻度、单位） */
  textMuted: string;
  /** 图注 / 元信息行 */
  caption: string;
  /** 参考线（截面轮廓、体素网格） */
  outline: string;
  /** 图例边框 */
  border: string;
  /** 色带（蓝→青→黄→橙→红，与屏幕上 `ColorLegend` 逐色一致） */
  colormap: string[];
  /** 主数据色（通量曲线等单序列图） */
  series: string;
  /** 误差棒 / 次要数据色 */
  seriesAlt: string;
  /** 版面（出图用；单位 px） */
  page: {
    padding: number;
    titleSize: number;
    labelSize: number;
    tickSize: number;
    captionSize: number;
    /** 图表区线宽 */
    stroke: number;
  };
  /** 字体栈：中英文都要能显示（导出 PDF 时字体需内嵌，故用系统无衬线） */
  fontFamily: string;
}

/** 色带 5 色——**从契约锚点派生，不另存一份**（见下） */
export const COLORMAP: string[] = WEATHER_STOPS.map(([, [r, g, b]]) =>
  "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join(""),
);

const FONT = '"Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif';

const SCREEN: PlotTheme = {
  kind: "screen",
  background: "#0a0a1e",
  axis: "rgba(241,241,249,0.85)",
  grid: "rgba(255,255,255,0.10)",
  text: "#f1f1f9",
  textMuted: "#9aa0b5",
  caption: "#9aa0b5",
  outline: "rgba(255,255,255,0.35)",
  border: "rgba(255,255,255,0.15)",
  colormap: COLORMAP,
  series: "#00e5ff",
  seriesAlt: "#FF5252",
  page: { padding: 16, titleSize: 14, labelSize: 12, tickSize: 10, captionSize: 10, stroke: 1.5 },
  fontFamily: FONT,
};

const PAPER: PlotTheme = {
  kind: "paper",
  background: null, // 透明底：叠在任意底色上都干净，期刊自己会给白底
  axis: "#1a1a1a",
  grid: "#d8d8d8",
  text: "#111111",
  textMuted: "#555555",
  caption: "#444444",
  outline: "#333333",
  border: "#bbbbbb",
  colormap: COLORMAP,
  series: "#0b5fa5",
  seriesAlt: "#b3261e",
  page: { padding: 18, titleSize: 15, labelSize: 12, tickSize: 10, captionSize: 10, stroke: 1.4 },
  fontFamily: FONT,
};

const THEMES: Record<PlotThemeKind, PlotTheme> = { screen: SCREEN, paper: PAPER };

/** 取主题（唯一入口）。论文主题是**导出默认**；屏幕主题只给"屏幕内 SVG"用。 */
export function themeFor(kind: PlotThemeKind = "paper"): PlotTheme {
  return THEMES[kind] ?? PAPER;
}

/**
 * 3D 场景背景 → 出图用背景。
 *
 * 3D 用的是 WebGL 光栅渲染，**没法做矢量**。所以 3D 出图做三件事：换底（透明底 / 白底）、
 * 把**场景底色**清成透明、以及把**刻度与轴**换成印刷墨色。
 *
 * ## 3D 的"论文配色"是怎么落地的（2026-09-19 补齐）
 * 刻度标签的底色与字色烧在 `CanvasTexture` 里（`three/TickGrid`），轴字母同理，
 * 材料色则由 `cellMaterial` 直接上到材质 —— 三者的取色点各不相同，所以：
 * - 场景底色：`captureFrame.captureTransparent3D` 在这一帧里置空 + `alpha=0` 清屏；
 * - 刻度/轴线/轴字母：`Preview3D.renderTransparentNow` 切到 `axisConfig.paperInk`
 *   （刻度标签同时切 `TickGrid.setLabelTheme("paper")`：**透明底 + 深色字**，
 *   不再有屏幕上的深色药丸方块）；
 * - 材料色：**不动**（色相必须与屏幕一一对应，否则用户没法照着屏幕认图）。
 *
 * 以上都只发生在**取图那一帧**内，屏幕观感不变。
 */
export function sceneBackgroundFor(kind: PlotThemeKind): number | null {
  const t = themeFor(kind);
  if (t.background === null) return null; // 透明：调用方用 alpha=0 清屏
  return parseInt(t.background.replace("#", ""), 16);
}

/** hex → "r,g,b"（给 canvas / SVG 需要分量时用） */
export function rgbOf(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

/**
 * hex → WebGL/three 用的 0xRRGGBB。
 *
 * 为什么要这个函数：3D 视图的**场景底色**是 `new THREE.Color(0x0d0d22)` 这种数值，
 * 而主题里的 `background` 是 `"#0a0a1e"` 字符串。出图要把场景底色临时换成透明，
 * 从主题取色时就必须走这一条转换 —— 别在各窗口里再写一遍 `parseInt(...)`。
 */
export function hexToInt(hex: string): number {
  return parseInt(hex.replace("#", ""), 16);
}

/**
 * 截图/出图时的清屏色（`THREE.WebGLRenderer` 的 `setClearColor` 参数）。
 *
 * ⚠️ `preserveDrawingBuffer:false` 的 WebGL 画布，**未清屏的像素是未定义的**。
 * 所以"透明出图"不能只把 `scene.background` 设成 null —— 必须**显式**清成
 * `alpha = 0`，否则取到的帧可能带着上一帧或垃圾值。这就是本函数返回四元组的原因。
 */
export function clearColorFor(kind: PlotThemeKind): [number, number, number, number] {
  const bg = themeFor(kind).background;
  if (bg === null) return [0, 0, 0, 0];
  const { r, g, b } = rgbOf(bg);
  return [r / 255, g / 255, b / 255, 1];
}
