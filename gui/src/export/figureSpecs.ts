/**
 * figureSpecs — 各视图「这张图由哪些块组成」的**集中描述**。
 *
 * 各窗口只调用这里的构造函数并把结果交给 `exportFigure`；版面、配色、格式、落盘
 * 都不在窗口里出现。这样做的实际收益：**改一次图的样子，八个窗口同时变**；
 * 而且每个 spec 都是纯数据 + 纯函数，可以脱离 React 单测（不必起 WebGL）。
 */
import type { FigurePanel, FigureSpec, LegendItem } from "./figureCanvas";
import type { VectorPanel, VectorFigureSpec } from "./vectorFigure";
import { COLORMAP } from "./plotTheme";

/** 参数行拼接：跳过空值，用 ` · ` 连接（图里那行小字） */
export function subtitleOf(parts: (string | number | undefined | null)[]): string {
  return parts.filter((p) => p !== undefined && p !== null && String(p) !== "").map(String).join(" · ");
}

/**
 * ⚠️ **出图不带图序（用户 2026-09-19 裁决）**。
 *
 * 规范要求"图题带图序（图1、图2…）"，但**图序属于正文语境**：
 * 同一份文稿里哪个图排第几，只有作者知道；程序每次导出都写"图1"反而是错的
 * （第二张图也会印成"图1"）。所以这里只画**纯标题**，编号由作者在 Word 里自己打
 * —— 国标要求的是"图题不得省略图序"，并不要求"图序必须印在图内"。
 *
 * 曾短暂实现过 `figureTitle()` 自动加 `图N` 前缀，**已按用户裁决撤除**，别再加回来。
 */

/** 材料图例条目：色块用 `getMatColor` 的口径（与屏幕、截面、3D 完全一致） */
export function materialLegendItems(entries: { mat: string; label?: string; color: string }[]): LegendItem[] {
  return entries.map((e) => ({ color: e.color, label: e.mat === "0" ? "M0 真空" : `M${e.mat}${e.label ? " " + e.label : ""}` }));
}

export interface ThreeDExportInput {
  /** 同步重画后拿到的 canvas */
  canvas: HTMLCanvasElement;
  title: string;
  subtitle?: string;
  legend?: LegendItem[];
  colorbar?: { min: number; max: number; unit: string };
  caption?: string;
  /** 内容高度（px）；缺省 420。多面板（视图 + 图例 + 色带）时按此高度对齐 */
  contentHeight?: number;
}

/**
 * 3D 类视图（3D 预览 / 体积结果 / 径迹 / 演示源）的出图描述。
 *
 * 面板顺序固定为「视图 → 图例 → 色带」：视图永远是主角、占最大宽度，
 * 图例色带靠右——与用户"这是张汇报图"的预期一致。
 */
export function build3dSpec(input: ThreeDExportInput): FigureSpec {
  const panels: FigurePanel[] = [{ kind: "image", canvas: input.canvas }];
  if (input.legend && input.legend.length) {
    panels.push({ kind: "legend", heading: "材料", items: input.legend });
  }
  if (input.colorbar) {
    panels.push({ kind: "colorbar", heading: "色阶", min: input.colorbar.min, max: input.colorbar.max, unit: input.colorbar.unit });
  }
  return {
    title: input.title,
    subtitle: input.subtitle,
    caption: input.caption,
    panels,
    theme: "paper",
    contentHeight: input.contentHeight ?? 420,
  };
}

export interface TwoDExportInput {
  title: string;
  subtitle?: string;
  /** 主图（矢量 SVG 文本） */
  panels: VectorPanel[];
  caption?: string;
  contentHeight?: number;
  /** 追加在右侧的矢量片段（色带图例等）；有颜色填充的图必须给，否则颜色无刻度可读 */
  trailing?: { svg: string; width: number; heading?: string };
}

/** 2D 类视图（截面 / tally 曲线 / 切面）的出图描述：先做矢量合成，再按目标 dpi 栅格成 PNG */
export function build2dSpec(input: TwoDExportInput): VectorFigureSpec {
  return {
    title: input.title,
    subtitle: input.subtitle,
    panels: input.panels,
    caption: input.caption,
    theme: "paper",
    contentHeight: input.contentHeight ?? 360,
    trailing: input.trailing,
  };
}

/**
 * 体积类视图的色阶信息（体积结果 / fmesh 切面共用）。
 * 单位来自 meshtal 判定（`MeV/g` 能量沉积 vs `归一化计数`），与屏幕上 `ColorLegend` 同源。
 */
export function volumeColorbar(min: number, max: number, unit: string): { min: number; max: number; unit: string } {
  return { min, max, unit };
}

/** 色带颜色（与屏幕一致；供 spec 组合时传参，避免各处硬编码） */
export const FIGURE_COLORMAP = COLORMAP;
