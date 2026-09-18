// @vitest-environment jsdom
/**
 * 出图基础设施单测。
 *
 * 这些用例锁的是**接口承诺**，不是实现细节：
 * - 配色只有一处权威（论文主题必须透明底 + 深色轴，屏幕主题必须深底）；
 * - 版面把"图由哪些块组成"翻成确定的像素（图例/色带/标题各自占位正确）；
 * - 矢量 SVG 组合只做搬移（面板内容原样保留）且透明底；
 * - 中文字体的三态判定与 TTF 魔数校验（ttc 必须被判不可用——那正是我们要避开的坑）。
 */
import { describe, it, expect } from "vitest";
import { themeFor, sceneBackgroundFor, rgbOf, COLORMAP } from "../src/export/plotTheme";
import { buildVectorFigure, splitSvg, estimateTextWidth, vectorTicks, needsCjkFont, vectorLegend, vectorColorbar } from "../src/export/vectorFigure";
import { formatTick, colorbarTicks, sampleColormap, renderFigure } from "../src/export/figureCanvas";
import { figureFileName } from "../src/export/saveFile";
import { looksLikeTtf, loadCjkFont, setFontReader } from "../src/export/cjkFont";
import { svgSize } from "../src/export/captureFrame";

describe("plotTheme", () => {
  it("论文主题透明底 + 深色轴；屏幕主题深底", () => {
    const paper = themeFor("paper");
    expect(paper.background).toBeNull();
    expect(paper.axis).toBe("#1a1a1a");
    expect(themeFor("screen").background).toBe("#0a0a1e");
  });

  it("色相不动：两套主题共用同一色带（材料/数值颜色必须与屏幕一一对应）", () => {
    expect(themeFor("paper").colormap).toEqual(themeFor("screen").colormap);
    expect(themeFor("paper").colormap).toEqual(COLORMAP);
  });

  it("未知主题退化为论文主题，而不是抛错", () => {
    expect(themeFor("nonsense" as any).kind).toBe("paper");
  });

  it("3D 场景背景：论文 → 透明(null)；屏幕 → 数值色", () => {
    expect(sceneBackgroundFor("paper")).toBeNull();
    expect(sceneBackgroundFor("screen")).toBe(0x0a0a1e);
  });

  it("rgbOf 支持 6 位与 3 位十六进制", () => {
    expect(rgbOf("#ff8800")).toEqual({ r: 255, g: 136, b: 0 });
    expect(rgbOf("#f80")).toEqual({ r: 255, g: 136, b: 0 });
  });
});

describe("splitSvg", () => {
  it("取出 inner 与尺寸，并剥掉 xml 声明", () => {
    const s = `<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100"><rect x="1" y="2" width="3" height="4"/></svg>`;
    const p = splitSvg(s);
    expect(p.width).toBe(200);
    expect(p.height).toBe(100);
    expect(p.inner).toContain("<rect");
    expect(p.inner).not.toContain("<svg");
    expect(p.inner).not.toContain("<?xml");
  });

  it("没有 width/height 时退回 viewBox", () => {
    const p = splitSvg(`<svg viewBox="0 0 640 480"><g/></svg>`);
    expect(p.width).toBe(640);
    expect(p.height).toBe(480);
  });

  it("两者都没有 → 保守兜底 400×300（绝不返回 0，否则版面会出现 0 宽面板）", () => {
    const p = splitSvg(`<svg><g/></svg>`);
    expect(p.width).toBeGreaterThan(0);
    expect(p.height).toBeGreaterThan(0);
  });
});

describe("buildVectorFigure", () => {
  const panel = (w: number, h: number, mark: string) =>
    `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><path d="M0 0" data-mark="${mark}"/></svg>`;

  it("组合后是自洽 SVG：尺寸属性与 viewBox 一致、透明底（无背景矩形）", () => {
    const fig = buildVectorFigure({ title: "截面", panels: [{ svg: panel(400, 300, "a") }] });
    expect(fig.svg.startsWith("<svg")).toBe(true);
    expect(fig.svg).toContain(`width="${fig.width}"`);
    expect(fig.svg).toContain(`viewBox="0 0 ${fig.width} ${fig.height}"`);
    expect(/<rect[^>]*width="\d+"[^>]*height="\d+"[^>]*fill="#fff/i.test(fig.svg)).toBe(false);
  });

  it("只做搬移：各面板内容原样保留（含自有样式与标记）", () => {
    const fig = buildVectorFigure({
      panels: [{ svg: panel(100, 100, "first"), heading: "左" }, { svg: panel(100, 100, "second") }],
    });
    expect(fig.svg).toContain('data-mark="first"');
    expect(fig.svg).toContain('data-mark="second"');
    expect(fig.svg).toContain(">左<");
  });

  it("面板等比缩放且居中：transform 的 scale 与 translate 都是有限数", () => {
    const fig = buildVectorFigure({ panels: [{ svg: panel(300, 100, "wide") }], contentHeight: 200 });
    const m = /<g transform="translate\(([-\d.]+),([-\d.]+)\) scale\(([\d.]+)\)">/.exec(fig.svg);
    expect(m).toBeTruthy();
    const [, dx, dy, s] = m!;
    expect(Number(dx)).toBeGreaterThanOrEqual(0);
    expect(Number(dy)).toBeGreaterThanOrEqual(0);
    expect(Number(s)).toBeGreaterThan(0);
    expect(Number.isFinite(Number(s))).toBe(true);
  });

  it("标题/副标题/脚注都进图；宽度随面板数增长", () => {
    const one = buildVectorFigure({ title: "T", subtitle: "S", caption: "C", panels: [{ svg: panel(100, 100, "a") }] });
    const two = buildVectorFigure({ title: "T", subtitle: "S", caption: "C", panels: [{ svg: panel(100, 100, "a") }, { svg: panel(100, 100, "b") }] });
    expect(one.svg).toContain(">T<");
    expect(one.svg).toContain(">S<");
    expect(one.svg).toContain(">C<");
    expect(two.width).toBeGreaterThan(one.width);
  });
});

describe("文本与刻度", () => {
  it("estimateTextWidth 中文按整字宽、ASCII 按半宽", () => {
    expect(estimateTextWidth("计数", 10)).toBeCloseTo(20, 5);
    expect(estimateTextWidth("abcd", 10)).toBeCloseTo(22, 5);
  });

  it("vectorTicks/colorbarTicks 等距且含两端", () => {
    expect(vectorTicks(0, 100, 4)).toEqual([0, 25, 50, 75, 100]);
    expect(colorbarTicks(0, 100, 4)).toEqual(vectorTicks(0, 100, 4));
  });

  it("刻度格式：整数直出、极端值走指数", () => {
    expect(formatTick(25)).toBe("25");
    expect(formatTick(1.91e-5)).toBe("1.9e-5");
  });

  it("sampleColormap 两端取到原色、中间为插值", () => {
    expect(sampleColormap(["#000000", "#ffffff"], 0)).toBe("rgb(0,0,0)");
    expect(sampleColormap(["#000000", "#ffffff"], 1)).toBe("rgb(255,255,255)");
    expect(sampleColormap(["#000000", "#ffffff"], 0.5)).toBe("rgb(128,128,128)");
  });
});

describe("needsCjkFont", () => {
  it("SVG 文本含中文 → 需要中文字体", () => {
    expect(needsCjkFont(`<svg><text>能量</text></svg>`)).toBe(true);
  });

  it("纯 ASCII 图 → 不需要（可以用 PDF 标准字体，体积小）", () => {
    expect(needsCjkFont(`<svg><text>Energy (MeV)</text></svg>`)).toBe(false);
  });
});

describe("figureFileName", () => {
  it("清洗非法字符并带时间戳与扩展名", () => {
    const n = figureFileName("3D 结果", ["tally 4", "1.5→20"], "png");
    expect(n).toMatch(/\.png$/);
    expect(n).not.toMatch(/[\\/:*?"<>|\s]/);
    expect(n).toContain("3D");
    expect(n).toMatch(/\d{8}_\d{6}/);
  });

  it("空参数段被丢弃，不留下多余下划线", () => {
    const n = figureFileName("截面", [undefined, "", null], "pdf");
    expect(n).not.toContain("__");
    expect(n).toMatch(/^截面_/);
  });
});

describe("中文字体三态", () => {
  it("TTF 魔数：真 TTF 通过，TTC 字体集合被拒（jsPDF 解析集合不可靠）", () => {
    const ttf = new Uint8Array([0x00, 0x01, 0x00, 0x00, 0, 0, 0, 0, 0, 0, 0, 0]);
    const otto = new Uint8Array([0x4f, 0x54, 0x54, 0x4f, 0, 0, 0, 0, 0, 0, 0, 0]);
    const ttcf = new Uint8Array([0x74, 0x74, 0x63, 0x66, 0, 0, 0, 0, 0, 0, 0, 0]);
    expect(looksLikeTtf(ttf)).toBe(true);
    expect(looksLikeTtf(otto)).toBe(true);
    expect(looksLikeTtf(ttcf)).toBe(false);
    expect(looksLikeTtf(new Uint8Array(4))).toBe(false);
  });

  it("读取器抛错 → notFound/error 明确区分，不抛异常给调用方", async () => {
    setFontReader(async () => { throw new Error("no such file"); });
    const r = await loadCjkFont();
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe("error");
  });

  it("读到有效 TTF → 返回字体字节与名字", async () => {
    const fake = new Uint8Array(20_000);
    fake[0] = 0; fake[1] = 1; fake[2] = 0; fake[3] = 0;
    setFontReader(async () => fake);
    const r = await loadCjkFont();
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.data.byteLength).toBe(20_000);
      expect(r.name).toBeTruthy();
    }
    setFontReader(null);
  });
});

describe("svgSize", () => {
  it("优先 width/height，退回 viewBox", () => {
    expect(svgSize(`<svg width="120" height="80"></svg>`)).toEqual({ width: 120, height: 80 });
    expect(svgSize(`<svg viewBox="0 0 300 150"></svg>`)).toEqual({ width: 300, height: 150 });
    expect(svgSize(`<svg></svg>`)).toEqual({ width: 0, height: 0 });
  });
});

describe("renderFigure 版面（栅格合成）", () => {
  it("图例与色带都占位，且总尺寸包含标题与内边距", () => {
    const canvas = document.createElement("canvas");
    canvas.width = 200; canvas.height = 100;
    const layout = renderFigure({
      title: "3D 结果",
      subtitle: "tally 4 · 128³",
      caption: "MESHTAL",
      panels: [
        { kind: "image", canvas },
        { kind: "legend", heading: "材料", items: [{ color: "#FF5252", label: "M1 水" }] },
        { kind: "colorbar", heading: "计数", min: 1e-5, max: 1e-2, unit: "归一化计数" },
      ],
    });
    expect(layout.width).toBeGreaterThan(600);
    expect(layout.height).toBeGreaterThan(300);
    expect(layout.canvas.width).toBe(layout.width);
  });

  it("无面板时也给一张最小画布（不返回 0 尺寸）", () => {
    const layout = renderFigure({ panels: [] });
    expect(layout.width).toBeGreaterThan(0);
    expect(layout.height).toBeGreaterThan(0);
  });
});

describe("矢量图例与色带", () => {
  it("图例逐条目出矩形 + 文本", () => {
    const s = vectorLegend(10, 20, [{ color: "#2979FF", label: "M2" }, { color: "#FF5252", label: "M1" }]);
    expect((s.match(/<rect/g) || []).length).toBe(2);
    expect(s).toContain(">M2<");
    expect(s).toContain(">M1<");
  });

  it("色带用渐变且刻度含两端数值与单位", () => {
    const s = vectorColorbar(0, 0, 20, 200, COLORMAP, 0, 10, "归一化计数");
    expect(s).toContain("linearGradient");
    expect(s).toContain("url(#");
    expect(s).toContain(">0<");
    expect(s).toContain(">10<");
    expect(s).toContain("归一化计数");
  });
});
