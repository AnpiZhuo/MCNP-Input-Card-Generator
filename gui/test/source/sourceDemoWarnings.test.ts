import { describe, it, expect } from "vitest";
import { sourceDemoWarning } from "../../src/utils/sourceDemoWarnings";

/**
 * 源演示非阻断告警文案（契约 source-demo-visualization.md §1/§4）
 * 两类告警都必须出现在警示条上 —— 特别是引擎侧的 ARA 说明（此前被前端整条丢掉）。
 */
describe("sourceDemoWarning", () => {
  it("两类都空 → 空串（不显示警示条）", () => {
    expect(sourceDemoWarning()).toBe("");
    expect(sourceDemoWarning([], [])).toBe("");
  });

  it("几何告警：最多列 3 条 + 总数", () => {
    const one = sourceDemoWarning(["曲面 5: 解析失败"], []);
    expect(one).toContain("部分栅元几何未能解析");
    expect(one).toContain("曲面 5: 解析失败");

    const many = sourceDemoWarning(["a", "b", "c", "d", "e"], []);
    expect(many).toContain("等 5 项");
    expect(many).not.toContain("d");
  });

  it("引擎告警（ARA）单独出现时也进警示条", () => {
    const text = sourceDemoWarning(undefined, ["ARA 面源面积：本程序不使用（只影响点探测器归一化）"]);
    expect(text).toContain("ARA");
    expect(text).toContain("不使用");
  });

  it("两类同时存在 → 几何在前、引擎告警在后，中间有分隔", () => {
    const text = sourceDemoWarning(["曲面 5: 解析失败"], ["ARA 不使用"]);
    expect(text.indexOf("部分栅元几何未能解析")).toBeLessThan(text.indexOf("ARA"));
    expect(text).toContain(" ");
  });
});
