// @vitest-environment jsdom
/**
 * MaterialLegend DOM 测试：图例渲染 `M{材料号} - {材料页注释}`，材料页没注释就只显示 M{n}。
 *
 * 与 materialLegend.test.ts 配套：那边锁"注释来源"，这边锁"渲染结果"。
 */
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { MaterialLegend } from "../src/components/MaterialPanel";
import { materialLegendEntries } from "../src/utils/materialLegend";

afterEach(cleanup);

describe("MaterialLegend（材料页注释渲染）", () => {
  it("显示 M1 - 材料页注释，并按材料去重", () => {
    const entries = materialLegendEntries(
      ["1", "1", "2"],
      [{ number: 1, comment: "UO2 燃料" }, { number: 2, comment: "锆包壳" }],
    );
    const { container } = render(React.createElement(MaterialLegend, { entries }));
    const text = container.textContent || "";
    expect(text).toContain("M1 - UO2 燃料");
    expect(text).toContain("M2 - 锆包壳");
    expect(text.match(/M1/g)?.length).toBe(1);        // 去重
  });

  it("材料页没写注释 → 只显示 M3（不显示栅元注释）", () => {
    const entries = materialLegendEntries(["3"], [{ number: 3 }]);
    const { container } = render(React.createElement(MaterialLegend, { entries }));
    const text = container.textContent || "";
    expect(text).toContain("M3");
    expect(text).not.toContain("M3 - ");
  });

  it("M0 真空固定显示「M0 - 真空」", () => {
    const { container } = render(React.createElement(MaterialLegend, {
      entries: materialLegendEntries(["0"], []),
    }));
    expect(container.textContent || "").toContain("M0 - 真空");
  });
});
