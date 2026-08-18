import React from "react";
import { describe, it, expect } from "vitest";
import { renderToString } from "react-dom/server";
import Sidebar from "../src/components/Sidebar";
import pkg from "../package.json";

/**
 * 侧边栏版本号显示（用户需求：悬停展开时应用图标右侧显示程序版本号）。
 * 版本来自 package.json（单一来源，与打包四处版本同步）。
 */
describe("Sidebar 版本号显示", () => {
  it(`渲染包含 v{package.json 版本}（当前 ${pkg.version}）`, () => {
    const html = renderToString(React.createElement(Sidebar, {
      active: "basic",
      onSelect: () => {},
      tabs: [{ key: "basic", label: "基本" }],
      theme: "dark",
      onThemeChange: () => {},
    }));
    // React SSR 在文本节点与表达式间插入 <!-- --> 注释：v<!-- -->1.7.1
    expect(html).toContain(pkg.version);
    expect(html).toContain(`v<!-- -->${pkg.version}`);
  });

  it("版本标签初始折叠（opacity 0），展开后显示", () => {
    const html = renderToString(React.createElement(Sidebar, {
      active: "basic",
      onSelect: () => {},
      tabs: [{ key: "basic", label: "基本" }],
      theme: "dark",
      onThemeChange: () => {},
    }));
    // 初始 expanded=false → opacity:0
    expect(html).toMatch(/opacity:\s*0/);
  });
});
