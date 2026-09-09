/**
 * SweepDialog 组件测试（沿用项目 SSR 测试模式：renderToString，不依赖
 * jsdom/testing-library——零新依赖红线）。
 *
 * 覆盖：
 * - SSR 初始渲染不崩溃，含标题/空态提示/按钮/组合数 0；
 * - 无基准 INP（SSR 初始态）时「规划预览/开始扫描」禁用；
 * - 纯函数 parseValues / cartesianSize / guessParamName。
 */
import React from "react";
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import SweepDialog, { cartesianSize, guessParamName, parseValues } from "../src/components/SweepDialog";
import { DeckProvider } from "../src/utils/DeckContext";


function renderSweep(): string {
  return renderToString(
    React.createElement(DeckProvider, null,
      React.createElement(SweepDialog, { onClose: () => {} })));
}

describe("SweepDialog SSR 渲染", () => {
  it("初始渲染不崩溃，含标题/空态提示/按钮/组合数", () => {
    let html = "";
    expect(() => { html = renderSweep(); }).not.toThrow();
    expect(html).toContain("参数扫描");
    expect(html).toContain("规划预览");
    expect(html).toContain("开始扫描");
    expect(html).toContain("还没有参数");      // 免正则版：引导用户先框选
    expect(html).toContain("组合数：");        // 无默认参数行（空态显示 —）
    expect(html).toContain("设为扫描参数");
  });

  it("无基准 INP（SSR 初始态）时规划/扫描按钮禁用", () => {
    const html = renderSweep();
    // SSR 初始 baseText="" 且无参数 → 两个执行按钮 disabled
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

  it("cartesianSize：单参数=N，多参数相乘，空参数=1", () => {
    const row = (name: string, values: string) =>
      ({ name, anchor: "x", context: "line", values });
    expect(cartesianSize([row("nps", "1000 5000 10000")])).toBe(3);
    expect(cartesianSize([
      row("a", "1 2"),
      row("b", "x y z"),
    ])).toBe(6);
    expect(cartesianSize([])).toBe(1);
    expect(cartesianSize([row("a", "")])).toBe(1);
  });

  it("guessParamName：取行内首个英文字母词（小写）；无字母则回退 anchor 字母或 param", () => {
    expect(guessParamName("NPS 1000", "1000")).toBe("nps");
    expect(guessParamName("kcode 1000 1.0 50 100", "1.0")).toBe("kcode");
    expect(guessParamName("m1 1001 -1.0", "-1.0")).toBe("m1");
    expect(guessParamName("2 1 1.0 -1", "1.0")).toBe("param"); // 全是数字
    expect(guessParamName("", "5cm")).toBe("cm");
  });
});
