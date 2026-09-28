import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import SourceDemoWindow, { demoLegendFor } from "../../src/source/SourceDemoWindow";

/**
 * SourceDemoWindow SSR 兜底（契约 source-demo-visualization.md §5）
 * 无 localStorage 桥数据（SSR / 浏览器模式直接访问 #/source-demo）时，
 * 渲染兜底文案而非崩溃（three.js/WebGL 只在 useEffect 内初始化，SSR 不触发）。
 */
describe("SourceDemoWindow SSR 兜底", () => {
  it("无桥数据 → 兜底文案，渲染不抛异常", () => {
    let html = "";
    expect(() => { html = renderToString(React.createElement(SourceDemoWindow)); }).not.toThrow();
    expect(html).toContain("没有演示源数据");
  });
});

/**
 * 源演示图例（契约 source-demo-visualization.md §1：`particle` ∈ {n,p,e,f,h,a,s,other}）
 * 三色常显；正电子（SDEF `PAR=4/F`，C810 3-56）只在确实抽到时补一行。
 */
describe("源演示图例 demoLegendFor", () => {
  it("只有 n/p/e 时不出现正电子行", () => {
    expect(demoLegendFor({ n: 500 }).map((l) => l.key)).toEqual(["n", "p", "e"]);
    expect(demoLegendFor({}).map((l) => l.key)).toEqual(["n", "p", "e"]);
  });

  it("抽到正电子 → 补第四行「正电子」", () => {
    const legend = demoLegendFor({ e: 1, f: 2 });
    expect(legend.map((l) => l.key)).toEqual(["n", "p", "e", "f"]);
    expect(legend[3].label).toBe("正电子");
    expect(legend[3].color).toBe("#a855f7");
  });
});
