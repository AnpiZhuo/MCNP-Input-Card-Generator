/**
 * figureLayout — **出图版面的单一权威**（2026-09-19 抽出，用户要求"把这些能导出图的抽成一个公用函数"）。
 *
 * ## 这个模块解决什么问题
 * 出图有两个渲染器（栅格 `figureCanvas` / 矢量 `vectorFigure`），再加 **8 个能出图的视图**
 * （3D 预览 / 体积 / 径迹 / 演示源 / 截面 / tally / 切面 / keff）。在这之前：
 *  - "图题放哪、图注放哪、字号多大、留白多少"这套规则**在两个渲染器里各写一份**；
 *  - 于是出现了真实的漂移：我把栅格版改成"图题在图下"之后，**矢量版还是标题在上**
 *    （用户实机导出的截面图就是标题压在图上），而且两边的标题/图注间距算得还不一样。
 * 抽到这里之后：**改一次，8 个视图两条出口同时变**；两个渲染器只负责"怎么把字画上去"。
 *
 * ## 版面规则（自下而上说，因为顺序是硬要求）
 * ```
 * ┌─────────────────────────────┐
 * │  内容行：视图 / 图例 / 色带     │   ← contentH（由调用方或面板决定）
 * ├─────────────────────────────┤
 * │            图题              │   ← 居中（GB/T 7713：图序与图题排在图下方、居中）
 * │  图注第一行                  │   ← 左对齐、小字（参数 / 来源 / 符号说明）
 * │  图注第二行 …                │   ← 折行由 renderer 按可用宽度算
 * └─────────────────────────────┘
 * ```
 * ⚠️ **图题必须在内容行之下**。这条不是审美偏好：规范要求"图序和图题排在图的下方"，
 * 而且"标题在上"会与几何面板自带的 heading + 下划线**叠在一起**（用户实测到过，
 * 表现为同一行出现两个平面方程、还有一条线压在字上）。
 */

import type { PlotTheme } from "./plotTheme";

/** 图下区里一段文字（两个渲染器共用同一份"算在哪、多大、什么色"） */
export interface FigureTextBlock {
  kind: "title" | "note";
  /** 要画的文字 */
  text: string;
  /** x 坐标（图题居中 → 取宽度一半；图注左对齐 → 取左留白） */
  x: number;
  /** 该行的基线 y（相对成品图左上角，px） */
  y: number;
  /** 字号（px） */
  size: number;
  /** 颜色（走主题，不在这里硬编码色值） */
  color: string;
  /** 是否居中（图题居中、图注左对齐） */
  align: "center" | "left";
  /** 字重：图题 600，图注常规 */
  weight: number | null;
  /** 行高（多行图注用；图题只有一行） */
  lineHeight: number;
}

export interface FigureSizing {
  /** 内容行高度 */
  contentHeight: number;
  /** 图题占的高度（无标题则 0） */
  titleH: number;
  /** 图注占的高度（无图注则 0） */
  noteH: number;
  /** 成品图总高 */
  height: number;
  /** 内容行顶部 y（= 上留白） */
  contentTop: number;
  /** 图下区顶部 y（内容行底部） */
  belowTop: number;
}

/**
 * 量出**整张图的垂直版面**：内容行高度 + 图题 + 图注 + 上下留白。
 *
 * 两个渲染器都必须用这个函数算高度 —— 否则"栅格版留白 8px、矢量版留白 12px"这类
 * 1~4px 的漂移就会永久存在（用户的图里就是这么来的）。
 *
 * @param contentHeight 内容行高度（px）
 * @param hasTitle 有没有图题
 * @param noteLineCount 图注**折行后**的行数（0 = 没有图注）
 */
export function layoutFigure(info: {
  theme: PlotTheme;
  contentHeight: number;
  hasTitle: boolean;
  noteLineCount: number;
}): FigureSizing {
  const { theme, contentHeight, hasTitle, noteLineCount } = info;
  const pad = theme.page.padding;
  const titleH = hasTitle ? theme.page.titleSize + 8 : 0;
  const noteH = noteLineCount > 0 ? noteLineCount * (theme.page.captionSize + 4) + 8 : 0;
  return {
    contentHeight,
    titleH,
    noteH,
    height: Math.round(pad + contentHeight + titleH + noteH + pad),
    contentTop: pad,
    belowTop: pad + contentHeight,
  };
}

/**
 * 图下区的**文字块清单**（渲染器照着画即可，不必自己算坐标）。
 *
 * 这里同时是"图题在图下"这条规则的**可测落点**：两个渲染器都从本函数取 y，
 * 单测只要断言 `title.y > contentTop + contentHeight` 就能锁住顺序，
 * 不必去解析 canvas 的绘制调用。
 */
export function figureTextBlocks(info: {
  theme: PlotTheme;
  sizing: FigureSizing;
  /** 可用宽度（图题居中要用） */
  width: number;
  title?: string;
  /** 图注**折行后**的每一行（顺序即自上而下） */
  noteLines: string[];
}): FigureTextBlock[] {
  const { theme, sizing, width } = info;
  const pad = theme.page.padding;
  const blocks: FigureTextBlock[] = [];
  if (info.title) {
    blocks.push({
      kind: "title",
      text: info.title,
      x: width / 2,
      y: sizing.belowTop + 4 + theme.page.titleSize, // 基线 = 顶部 + 字号
      size: theme.page.titleSize,
      color: theme.text,
      align: "center",
      weight: 600,
      lineHeight: theme.page.titleSize + 8,
    });
  }
  const noteTop = sizing.belowTop + sizing.titleH + 4;
  info.noteLines.forEach((line, i) => {
    blocks.push({
      kind: "note",
      text: line,
      x: pad,
      y: noteTop + i * (theme.page.captionSize + 4) + theme.page.captionSize,
      size: theme.page.captionSize,
      color: theme.caption,
      align: "left",
      weight: null,
      lineHeight: theme.page.captionSize + 4,
    });
  });
  return blocks;
}

/**
 * 图的标题行文本（**只出标题本身**）。
 *
 * ⚠️ 不带图序（用户 2026-09-19 裁决）：同一文稿里哪个图排第几只有作者知道，
 * 程序每次导出都写"图1"会让第二张图也印成图1。规范要求"图题不得省略图序"，
 * 但**不要求图序印在图内** —— 编号由作者在正文里打。
 * 曾短暂实现过自动加 `图N`，**已撤除，别再加回来**。
 */
export function figureTitleText(title: string): string {
  return title;
}

/** 图注行：过滤空值后用 ` · ` 连接（各视图参数行的统一写法） */
export function joinNoteParts(parts: (string | number | undefined | null)[]): string {
  return parts.filter((p) => p !== undefined && p !== null && String(p) !== "").map(String).join(" · ");
}
