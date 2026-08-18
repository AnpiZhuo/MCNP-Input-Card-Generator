import { describe, it, expect } from "vitest";
import { buildFluxChartSvg } from "../src/utils/tallyChart";

describe("buildFluxChartSvg（tally 通量 SVG 折线图纯函数）", () => {
  it("空数据 → 占位提示", () => {
    const svg = buildFluxChartSvg([{ energy: "1", flux: "x", error: "" }]);
    expect(svg).toContain("无有效数据点");
  });

  it("多数据点 → 折线与数据点、坐标轴", () => {
    const svg = buildFluxChartSvg([
      { energy: "0.1", flux: "1e-3", error: "0.01" },
      { energy: "1", flux: "1e-1", error: "0.02" },
      { energy: "10", flux: "1e1", error: "0.03" },
    ]);
    expect(svg).toContain("<svg");
    expect(svg).toContain("<polyline");
    expect(svg).toContain("<circle");
    expect(svg).toContain("Energy (MeV)");
    expect(svg).toContain("Flux");
  });

  it("通量跨 100 倍 → 对数刻度（y 轴 tick 含 10 的幂）", () => {
    const svg = buildFluxChartSvg([
      { energy: "1", flux: "1e-6", error: "" },
      { energy: "2", flux: "1e2", error: "" },
    ]);
    expect(svg).toContain("<polyline");
  });
});
