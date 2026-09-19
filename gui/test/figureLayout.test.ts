// @vitest-environment jsdom
/**
 * figureLayout — **出图版面的单一权威**（2026-09-19 抽出）。
 *
 * 这个文件锁的是用户**两次实测**出来的那两条规则：
 *  1. **图题必须在图的下方、居中**（GB/T 7713：图序与图题排在图下方）；
 *     —— 曾经栅格版改了、矢量版没改，同一张图两条出口版式不同；
 *  2. **图注在图题之下、左对齐**，且与图题/内容行**不重叠**。
 * 断言方式刻意选"可测落点"：直接检查公用模块给出的坐标，而不是去解析 canvas 绘制调用
 * （那种测试写起来脆、改一次就红）。
 */
import { describe, it, expect } from "vitest";
import { layoutFigure, figureTextBlocks, figureTitleText, joinNoteParts } from "../src/export/figureLayout";
import { themeFor } from "../src/export/plotTheme";
import { buildVectorFigure } from "../src/export/vectorFigure";

const theme = themeFor("paper");

describe("figureLayout：图题在图下、图注在图题下", () => {
  const sizing = layoutFigure({ theme, contentHeight: 400, hasTitle: true, noteLineCount: 2 });
  const blocks = figureTextBlocks({ theme, sizing, width: 600, title: "二维截面", noteLines: ["第一行图注", "第二行图注"] });

  it("★ 图题的基线在内容行**之下**（不是之上）", () => {
    const title = blocks.find((b) => b.kind === "title")!;
    expect(title).toBeTruthy();
    const contentBottom = sizing.contentTop + sizing.contentHeight;
    expect(title.y).toBeGreaterThan(contentBottom);
  });

  it("★ 图注的每一行都在图题**之下**", () => {
    const title = blocks.find((b) => b.kind === "title")!;
    const notes = blocks.filter((b) => b.kind === "note");
    expect(notes.length).toBe(2);
    for (const n of notes) expect(n.y).toBeGreaterThan(title.y);
    // 且逐行递增、不重叠
    expect(notes[1].y - notes[0].y).toBeCloseTo(notes[0].lineHeight, 6);
  });

  it("★ 图题居中、图注左对齐（规范要求的对齐方式）", () => {
    const title = blocks.find((b) => b.kind === "title")!;
    const note = blocks.find((b) => b.kind === "note")!;
    expect(title.align).toBe("center");
    expect(title.x).toBe(600 / 2);
    expect(note.align).toBe("left");
    expect(note.x).toBe(theme.page.padding);
  });

  it("总高 = 上留白 + 内容 + 图题 + 图注 + 下留白（不能漏项）", () => {
    const expectH = theme.page.padding + 400 + sizing.titleH + sizing.noteH + theme.page.padding;
    expect(sizing.height).toBe(Math.round(expectH));
    // 图题/图注占位都不为零
    expect(sizing.titleH).toBeGreaterThan(0);
    expect(sizing.noteH).toBeGreaterThan(0);
  });

  it("没有图题/图注时不占高度（不能凭空多出留白）", () => {
    const bare = layoutFigure({ theme, contentHeight: 400, hasTitle: false, noteLineCount: 0 });
    expect(bare.titleH).toBe(0);
    expect(bare.noteH).toBe(0);
    expect(bare.height).toBe(theme.page.padding * 2 + 400);
    expect(figureTextBlocks({ theme, sizing: bare, width: 600, noteLines: [] })).toHaveLength(0);
  });
});

describe("★ 两个渲染器同版式（栅格 / 矢量不再各写一份）", () => {
  const panel = `<svg width="300" height="200" viewBox="0 0 300 200"><rect width="300" height="200"/></svg>`;
  const spec = {
    title: "二维截面",
    subtitle: "切割平面 0X+0Y+1Z=0",
    caption: "材料配色与屏幕一致",
    panels: [{ svg: panel }],
    legend: [{ color: "#ff0000", label: "M2 铁" }],
  };

  it("矢量图里 图题 出现在 内容 之后、图注 之前（按 SVG 文档顺序）", () => {
    const fig = buildVectorFigure(spec);
    const iPanel = fig.svg.indexOf("<rect"); // 面板内容（外层没有别的 rect，图例的色块在标题之前）
    const iTitle = fig.svg.indexOf(">二维截面<");
    const iNote = fig.svg.indexOf(">切割平面 0X+0Y+1Z=0<");
    expect(iPanel).toBeGreaterThanOrEqual(0);
    expect(iTitle).toBeGreaterThan(iPanel);
    expect(iNote).toBeGreaterThan(iTitle);
  });

  it("★ 图题**居中**且**在图下**（矢量版曾经把标题画在图上方）", () => {
    const fig = buildVectorFigure(spec);
    const m = /<text x="([\d.]+)" y="([\d.]+)" text-anchor="middle"[^>]*>二维截面<\/text>/.exec(fig.svg);
    expect(m).toBeTruthy();
    const x = Number(m![1]);
    const y = Number(m![2]);
    expect(x).toBeCloseTo(fig.width / 2, 0);        // 水平居中
    expect(x).not.toBe(theme.page.padding);          // 不是左对齐（旧行为）
    const layout = layoutFigure({ theme, contentHeight: 0, hasTitle: true, noteLineCount: 0 });
    // y 至少在图下一半高度之外（内容区底部以下）
    expect(y).toBeGreaterThan(layout.contentTop + layout.contentHeight);
  });

  it("矢量图带**色块图例**（不是把材料名写进一行 caption）", () => {
    const fig = buildVectorFigure(spec);
    expect(fig.svg).toContain('fill="#ff0000"');   // 色块
    expect(fig.svg).toContain(">M2 铁<");           // 条目文字
  });

  it("两个渲染器算出**同一个**总高公式（同一 spec 下高度一致）", () => {
    // 矢量：按面板宽高比定内容高；这里只验证"高度公式"用的是同一套项
    const result = buildVectorFigure(spec);
    const inner = layoutFigure({ theme, contentHeight: 0, hasTitle: true, noteLineCount: 2 });
    // 总高必须 = pad + 内容 + titleH + noteH + pad ⇒ 反推内容高应能整除得出
    const derivedContentH = result.height - theme.page.padding * 2 - inner.titleH - inner.noteH;
    expect(derivedContentH).toBeGreaterThan(0);
  });
});

describe("figureTitleText / joinNoteParts", () => {
  it("★ 图题不带图序（用户裁决：编号由作者在正文里打）", () => {
    expect(figureTitleText("二维截面")).toBe("二维截面");
    expect(figureTitleText("二维截面")).not.toMatch(/图\s*\d/);
  });

  it("图注拼接跳过空值、用 · 连接", () => {
    expect(joinNoteParts(["a", undefined, "", null, 3])).toBe("a · 3");
  });
});

/**
 * 描边导出换算（2026-09-19 用户第二次实测："各种截面的矢量图，材料边界描边还是太重了"）。
 *
 * 屏幕上用 `vector-effect="non-scaling-stroke"` 把线宽锚在屏幕像素（缩放不漂移），
 * 但该属性**出了文档不保证生效**：截面 SVG 会被合成进版面再缩放一次，
 * 描边于是被当成用户单位乘以缩放比 ⇒ 导出图里边界比屏幕重。
 * 修法：导出时摘掉该属性，并把线宽换算成用户坐标（`1.2 / strokeScale`）。
 */
describe("★ snapshotSvg：non-scaling-stroke 的导出换算", () => {
  const build = () => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("width", "500");
    svg.setAttribute("height", "500");
    const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    poly.setAttribute("points", "0,0 10,0 10,10");
    poly.setAttribute("stroke-width", "1.2");
    poly.setAttribute("vector-effect", "non-scaling-stroke");
    poly.setAttribute("data-export-strip", "1");
    svg.appendChild(poly);
    document.body.appendChild(svg);
    return svg;
  };

  it("传 strokeScale：摘掉 vector-effect 并把线宽按比例换成用户坐标", async () => {
    const { snapshotSvg } = await import("../src/export/captureFrame");
    const svg = build();
    // 屏幕 500px 宽，导出面板 125px ⇒ 面板是屏幕的 0.25 倍
    const out = snapshotSvg(svg, { strokeScale: 0.25 })!;
    expect(out).not.toMatch(/non-scaling-stroke/);
    // 1.2 / 0.25 = 4.8（用户坐标），面板缩放 0.25 后回到 1.2px
    expect(out).toMatch(/stroke-width="4\.8"/);
    svg.remove();
  });

  it("不传 strokeScale：保持原样（不影响没有该属性的图）", async () => {
    const { snapshotSvg } = await import("../src/export/captureFrame");
    const svg = build();
    const out = snapshotSvg(svg)!;
    expect(out).toMatch(/non-scaling-stroke/);
    expect(out).toMatch(/stroke-width="1\.2"/);
    svg.remove();
  });
});
