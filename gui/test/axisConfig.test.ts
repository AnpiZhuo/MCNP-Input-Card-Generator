import { describe, it, expect } from "vitest";
import { AXIS_CONFIG } from "../src/three/axisConfig";

describe("AXIS_CONFIG（3D 预览坐标轴）", () => {
  it("标签顺序 X/Y/Z 与方向一一对应（Y 不再与 Z 互换）", () => {
    expect(AXIS_CONFIG.map((a) => a.label)).toEqual(["X", "Y", "Z"]);
    expect(AXIS_CONFIG[0].dir).toEqual([1, 0, 0]);
    expect(AXIS_CONFIG[1].dir).toEqual([0, 1, 0]);
    expect(AXIS_CONFIG[2].dir).toEqual([0, 0, 1]);
  });

  it("颜色符合 RGB 惯例：X 红 / Y 绿 / Z 蓝", () => {
    expect(AXIS_CONFIG[0].color).toBe(0xff4444);
    expect(AXIS_CONFIG[1].color).toBe(0x44ff44);
    expect(AXIS_CONFIG[2].color).toBe(0x4488ff);
  });
});
