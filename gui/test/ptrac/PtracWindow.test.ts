import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import PtracWindow from "../../src/ptrac/PtracWindow";

/**
 * PtracWindow SSR 兜底（契约 ptrac-visualization.md §5）
 * 无 localStorage 桥数据（SSR / 浏览器模式直接访问 #/ptrac）时，
 * 渲染兜底文案而非崩溃（三.js/WebGL 只在 useEffect 内初始化，SSR 不触发）。
 */
describe("PtracWindow SSR 兜底", () => {
  it("无桥数据 → 兜底文案，渲染不抛异常", () => {
    let html = "";
    expect(() => { html = renderToString(React.createElement(PtracWindow)); }).not.toThrow();
    expect(html).toContain("没有 3D 径迹数据");
  });
});
