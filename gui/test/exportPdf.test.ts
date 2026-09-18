// @vitest-environment jsdom
/**
 * tallyChartPaper / exportPdf — 出图版 tally 曲线与**中文矢量 PDF**。
 *
 * 中文这条最值得锁死：PDF 标准字体不含中文，而本程序每张图都带中文；
 * 字体一旦没接上，导出的 PDF 会"打得开、只是中文全空白"—— 最恶劣的一类失败
 * （用户以为是图没导全，而不是字体缺失）。
 *
 * 这里用真实系统中文字体（Deng.ttf）跑通"矢量 PDF + 中文"，并钉住**体积**：
 * jsPDF 会做字体子集化（16 MB 字体 → 0.3 MB 级 PDF），
 * 换字体/换写法后若变成十几 MB，`tooLarge` 分支必须接住并转位图。
 */
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { buildPaperTallyChart } from "../src/utils/tallyChartPaper";
import { buildVectorFigure, figureToPdf, needsCjkFont } from "../src/export/vectorFigure";
import type { TallyRow } from "../src/utils/outputParser";

const ROWS: TallyRow[] = [
  { energy: "1e-8", flux: "1.2e-3", error: "0.02" },
  { energy: "1e-6", flux: "3.4e-2", error: "0.01" },
  { energy: "1e-4", flux: "2.0e-1", error: "0.01" },
  { energy: "1e-2", flux: "8.0e-2", error: "0.02" },
  { energy: "1", flux: "1.0e-2", error: "0.05" },
];

describe("buildPaperTallyChart（出图版）", () => {
  it("产出透明底 SVG：轴为论文主题深色，含带单位的轴标题", () => {
    const svg = buildPaperTallyChart(ROWS, { width: 760, height: 460 })!;
    expect(svg).toContain("<svg");
    // 这组数据能量跨 8 个数量级 ⇒ x 轴自动走对数（线性轴会把低能点全挤在左端）
    expect(svg).toContain("Energy (MeV, log scale)");
    expect(svg).toContain('stroke="#1a1a1a"'); // 论文主题轴色
  });

  it("能量跨数量级 → x 轴走对数；等距能量 → 线性轴", () => {
    const wide = buildPaperTallyChart(ROWS, { width: 760, height: 460 })!;
    expect(wide).toContain("log scale");
    const linear: TallyRow[] = [
      { energy: "1", flux: "1", error: "0.01" },
      { energy: "2", flux: "3", error: "0.01" },
      { energy: "3", flux: "2", error: "0.01" },
      { energy: "4", flux: "4", error: "0.01" },
    ];
    const lin = buildPaperTallyChart(linear, { width: 600, height: 400 })!;
    expect(lin).toContain(">Energy (MeV)<");
    expect(lin).not.toContain("log scale");
  });

  it("尺寸按传入画幅（自适应），不是写死 560×300", () => {
    const a = buildPaperTallyChart(ROWS, { width: 760, height: 460 })!;
    const b = buildPaperTallyChart(ROWS, { width: 1100, height: 700 })!;
    expect(a).toContain('width="760" height="460"');
    expect(b).toContain('width="1100" height="700"');
    expect(a).not.toEqual(b);
  });

  it("误差棒是矢量线段；图例写明红短线含义", () => {
    const svg = buildPaperTallyChart(ROWS, { width: 700, height: 420 })!;
    expect(svg).toMatch(/stroke="#b3261e"/); // seriesAlt = 误差棒
    expect(svg).toContain("1σ 误差");
    expect(svg).toContain("通量");
  });

  it("数据跨 100 倍以上 → y 轴走对数并标注 log scale", () => {
    const wide: TallyRow[] = [
      { energy: "1", flux: "1", error: "0.01" },
      { energy: "2", flux: "1000", error: "0.01" },
    ];
    const svg = buildPaperTallyChart(wide, { width: 600, height: 400 })!;
    expect(svg).toContain("log scale");
    expect(svg).toContain("10^"); // 对数刻度标注
  });

  it("无有效数据点 → null（调用方画提示，不出空图）", () => {
    expect(buildPaperTallyChart([], { width: 600, height: 400 })).toBeNull();
    expect(buildPaperTallyChart([{ energy: "", flux: "abc", error: "" }], { width: 600, height: 400 })).toBeNull();
  });
});

describe("中文矢量 PDF", () => {
  const FONT = "C:/Windows/Fonts/Deng.ttf";
  const hasFont = existsSync(FONT);

  it("含中文的图被识别为需要 CJK 字体（不静默出空白中文）", () => {
    expect(needsCjkFont("<svg><text>能量</text></svg>")).toBe(true);
    expect(needsCjkFont("<svg><text>Energy</text></svg>")).toBe(false);
  });

  it.skipIf(!hasFont)("用真实系统中文字体转出可用矢量 PDF，且体积远小于字体本身", async () => {
    const data = new Uint8Array(readFileSync(FONT));
    const fig = buildVectorFigure({
      title: "计数卡 3D 结果",
      subtitle: "tally 4 · 分辨率 128 · Z 轴第 7 层",
      caption: "数据来源：meshtal",
      panels: [{ svg: buildPaperTallyChart(ROWS, { width: 600, height: 360 })! }],
    });
    const out = await figureToPdf(fig, { font: { name: "DengXian", data }, maxBytes: 999_000_000 });
    expect(out.ok).toBe(true);
    if (out.ok) {
      expect(String.fromCharCode(...out.bytes.slice(0, 5))).toBe("%PDF-");
      // 字体 16 MB，PDF 必须远小于它（说明做了子集化；否则应被 6 MB 上限拦下转位图）
      expect(out.bytes.byteLength).toBeLessThan(3_000_000);
    }
  }, 120_000);

  it.skipIf(!hasFont)("体积超上限 → 明确返回 tooLarge（让调用方转位图），不交出巨型 PDF", async () => {
    const data = new Uint8Array(readFileSync(FONT));
    const fig = buildVectorFigure({ panels: [{ svg: buildPaperTallyChart(ROWS, { width: 400, height: 300 })! }] });
    const out = await figureToPdf(fig, { font: { name: "DengXian", data }, maxBytes: 1000 });
    expect(out.ok).toBe(false);
    if (!out.ok) expect(out.reason).toBe("tooLarge");
  }, 120_000);

  it("含中文但没给字体 → needsCjkFont（调用方改走位图 PDF）", async () => {
    const fig = buildVectorFigure({ title: "计数", panels: [{ svg: buildPaperTallyChart(ROWS, { width: 400, height: 300 })! }] });
    const out = await figureToPdf(fig, {});
    expect(out.ok).toBe(false);
    if (!out.ok) expect(out.reason).toBe("needsCjkFont");
  }, 60_000);
});
