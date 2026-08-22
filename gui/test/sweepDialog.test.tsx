/**
 * SweepDialog 组件测试（沿用项目 SSR 测试模式：renderToString，不依赖
 * jsdom/testing-library——零新依赖红线）。
 *
 * 覆盖：
 * - SSR 初始渲染不崩溃，含标题/默认参数行/按钮/组合数；
 * - 无基准 INP 时「规划预览/开始扫描」禁用（SSR 初始态 baseText=""）；
 * - 纯函数 parseValues / cartesianSize（取值解析与组合数）。
 */
import React from "react";
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import SweepDialog, { cartesianSize, parseValues } from "../src/components/SweepDialog";
import { DeckProvider } from "../src/utils/DeckContext";


function renderSweep(): string {
  return renderToString(
    React.createElement(DeckProvider, null,
      React.createElement(SweepDialog, { onClose: () => {} })));
}

describe("SweepDialog SSR 渲染", () => {
  it("初始渲染不崩溃，含标题/按钮/默认参数行", () => {
    let html = "";
    expect(() => { html = renderSweep(); }).not.toThrow();
    expect(html).toContain("参数扫描");
    expect(html).toContain("规划预览");
    expect(html).toContain("开始扫描");
    expect(html).toContain("NPS");          // 默认参数行
    expect(html).toContain("1000 5000 10000");
    expect(html).toContain("3 组合");       // 默认组合数
  });

  it("无基准 INP（SSR 初始态）时规划/扫描按钮禁用", () => {
    const html = renderSweep();
    // SSR 初始 baseText="" → 两个执行按钮 disabled
    expect(html).toMatch(/disabled[^>]*>\s*规划预览/);
    expect(html).toMatch(/disabled[^>]*>\s*开始扫描/);
  });
});

describe("SweepDialog 纯函数", () => {
  it("parseValues：数字保留为数字，文本保留为字符串，支持空格/逗号/中文逗号/科学计数", () => {
    expect(parseValues("1000 5000,1e3，2")).toEqual([1000, 5000, 1000, 2]);
    expect(parseValues("leu heu")).toEqual(["leu", "heu"]);
    expect(parseValues("")).toEqual([]);
    expect(parseValues("1.5 -0.25")).toEqual([1.5, -0.25]);
  });

  it("cartesianSize：默认行=3，多参数相乘，空参数=1", () => {
    const defaultRows = [{ name: "nps", pattern: "", values: "1000 5000 10000" }];
    expect(cartesianSize(defaultRows)).toBe(3);
    expect(cartesianSize([
      { name: "a", pattern: "", values: "1 2" },
      { name: "b", pattern: "", values: "x y z" },
    ])).toBe(6);
    expect(cartesianSize([])).toBe(1);
    expect(cartesianSize([{ name: "a", pattern: "", values: "" }])).toBe(1);
  });
});
