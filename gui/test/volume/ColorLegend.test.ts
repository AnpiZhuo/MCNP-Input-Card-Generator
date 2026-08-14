import React from "react";
import { describe, it, expect } from "vitest";
import { renderToString } from "react-dom/server";
import ColorLegend, { legendTicks, formatLegendValue } from "../../src/volume/ColorLegend";

/**
 * 色条图例（契约 meshtal-visualization.md §12 F5.2）
 * 色条两端显示 displayMin/displayMax 数值 + 单位标签；legendTicks 刻度纯函数。
 */
describe("legendTicks", () => {
  it("等距刻度含两端", () => {
    expect(legendTicks(0, 100, 4)).toEqual([0, 25, 50, 75, 100]);
  });

  it("n 默认 4（5 刻度）", () => {
    expect(legendTicks(0, 1)).toEqual([0, 0.25, 0.5, 0.75, 1]);
  });

  it("自定义 min/max", () => {
    expect(legendTicks(10, 20, 2)).toEqual([10, 15, 20]);
  });

  it("负范围 / 零范围不崩", () => {
    expect(legendTicks(-1, 1, 2)).toEqual([-1, 0, 1]);
    expect(legendTicks(5, 5, 2)).toEqual([5, 5, 5]);
  });
});

describe("formatLegendValue", () => {
  it("整数省略小数位", () => {
    expect(formatLegendValue(3.5e7)).toContain("e");
    expect(formatLegendValue(42)).toBe("42");
  });
  it("小值紧凑", () => {
    expect(formatLegendValue(1e-4)).toContain("e");
  });
});

describe("ColorLegend 渲染（F5.2 单位 + 上下限数值）", () => {
  it("渲染包含单位标签 + 两端数值", () => {
    const html = renderToString(
      React.createElement(ColorLegend, { min: 0, max: 3.5e7, unit: "归一化计数" }),
    );
    expect(html).toContain("归一化计数");
    expect(html).toContain(">0<");
    expect(html).toContain("e+7"); // 上限 3.5e7 → toExponential(2) = "3.50e+7"
  });

  it("默认单位 = 归一化计数", () => {
    const html = renderToString(React.createElement(ColorLegend, { min: 0, max: 1 }));
    expect(html).toContain("归一化计数");
    expect(html).toContain("linear-gradient");
  });
});
