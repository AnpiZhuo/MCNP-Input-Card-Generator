import { describe, it, expect } from "vitest";
import { workflowStep, noFileMessage } from "../../src/volume/workflow";

/**
 * 引导式工作流空态纯逻辑（契约 meshtal-visualization.md §12 F1）
 * F1.1 空态三步引导；F1.2 没找到文件可操作提示（非报错）。
 */
describe("workflowStep（F1.1 空态三步引导）", () => {
  it("idle：无 meshtal 数据 → 三步引导 ①②③", () => {
    const wf = workflowStep("idle");
    expect(wf.title).toBe("还没有网格计数数据");
    expect(wf.steps.map((s) => s.no)).toEqual(["①", "②", "③"]);
    expect(wf.steps[0].text).toContain("先运行 MCNP");
    expect(wf.steps[1].text).toContain("解析");
    expect(wf.steps[2].text).toContain("看结果");
  });

  it("noFiles：找不到文件 → 仍给三步引导 + 明确标题", () => {
    const wf = workflowStep("noFiles");
    expect(wf.title).toContain("没有找到");
    expect(wf.steps.length).toBe(3);
    expect(wf.steps[0].text).toContain("先运行 MCNP");
  });

  it("parsed：数据就绪 → 引导打开结果窗口", () => {
    const wf = workflowStep("parsed");
    expect(wf.title).toContain("已就绪");
    expect(wf.steps[0].no).toBe("✓");
  });
});

describe("noFileMessage（F1.2 没找到文件可操作提示）", () => {
  it("无文件 → 提示文案 + 可操作动作（触发 choose-file，非报错）", () => {
    const m = noFileMessage(false);
    expect(m.text).toBe("未在输出目录找到 MESHTAL 文件");
    expect(m.action).toContain("点这里");
    expect(m.action).toContain("选择 meshtal 文件");
  });

  it("有文件 → 空提示", () => {
    const m = noFileMessage(true);
    expect(m.text).toBe("");
    expect(m.action).toBe("");
  });
});
