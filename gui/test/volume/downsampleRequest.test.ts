import { describe, it, expect } from "vitest";
import {
  decideResolution, planDownsample, estimateTextureBytes,
  DEFAULT_RESOLUTION, MAX_RESOLUTION, GPU_BUDGET_BYTES, OVER_BUDGET_POPUP_COPY,
} from "../../src/volume/downsampleRequest";

/**
 * 分辨率决策 + 超预算弹窗（契约 meshtal-visualization.md §4.4 / §8 / §12 A2.3 / F3）
 * 镜像后端 downsample_plan.py：128 默认 / 256 显式 / native 更小保 native / 弹窗素材。
 */
describe("estimateTextureBytes", () => {
  it("128³=8MiB、256³=64MiB（RGBA 4B/体素）", () => {
    expect(estimateTextureBytes([128, 128, 128])).toBe(128 * 128 * 128 * 4);
    expect(estimateTextureBytes([256, 256, 256])).toBe(256 * 256 * 256 * 4);
    expect(estimateTextureBytes([128, 128, 128])).toBeLessThan(GPU_BUDGET_BYTES);
  });
});

describe("decideResolution（A2.3 自动 128³ / 256³ 显式）", () => {
  it("无请求 → 默认 128³（自动决策）", () => {
    const d = decideResolution([256, 256, 256], undefined);
    expect(d.resolution).toBe(DEFAULT_RESOLUTION);
    expect(d.popup).toBe(false);
  });

  it("显式 256 → 256³", () => {
    const d = decideResolution([256, 256, 256], 256);
    expect(d.resolution).toBe(MAX_RESOLUTION);
    expect(d.popup).toBe(false);
  });

  it("native 更小保 native（avgFactor=1，不弹窗）", () => {
    const d = decideResolution([64, 64, 64], undefined);
    expect(d.resolution).toBe(DEFAULT_RESOLUTION);
    const plan = planDownsample([64, 64, 64], d.resolution);
    expect(plan.outDims).toEqual([64, 64, 64]);
    expect(plan.avgFactor).toEqual([1, 1, 1]);
    expect(plan.overBudget).toBe(false);
  });
});

describe("超预算弹窗（F3 大白话文案）", () => {
  it("预算极小 → popup:true + 弹窗文案「要更流畅，还是要更精细？」", () => {
    const tinyBudget = 1000; // 远小于 128³ RGBA
    const d = decideResolution([128, 128, 128], undefined, tinyBudget);
    expect(d.popup).toBe(true);
    expect(d.recommended).toBe("smooth");
    expect(d.popupCopy).toBe(OVER_BUDGET_POPUP_COPY);
    expect(d.popupCopy).toBe("要更流畅，还是要更精细？");
  });

  it("预算充足 → popup:false、无弹窗文案", () => {
    const d = decideResolution([128, 128, 128], undefined, GPU_BUDGET_BYTES);
    expect(d.popup).toBe(false);
    expect(d.recommended).toBe("");
    expect(d.popupCopy).toBe("");
  });

  it("over_budget 与 avgFactor 联动（planDownsample）", () => {
    const plan = planDownsample([100, 100, 100], 50, 1000);
    expect(plan.overBudget).toBe(true);
    expect(plan.outDims).toEqual([50, 50, 50]);
    expect(plan.avgFactor).toEqual([2, 2, 2]);
  });
});
