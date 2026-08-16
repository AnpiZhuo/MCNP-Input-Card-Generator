import { describe, it, expect } from "vitest";
import {
  TRACK_COLORS, TRACK_FALLBACK_COLOR, TRACK_PARTICLE_LABELS, TRACK_LEGEND,
  SHADE_LIGHT, SHADE_DARK,
  trackColor, trackShade, normalizeEnergy01,
} from "../../src/ptrac/trackColors";

/**
 * 粒子类型基色 + 能量深浅渐变（契约 ptrac-visualization.md §4 / §5）
 * 用户敲定：n=蓝(#3b82f6)/p=红(#ef4444)/e=黄(#eab308)、其余灰；低能浅、高能深。
 */

/** hex → HSL lightness（0..1），供深浅渐变区间断言 */
function hexLightness(hex: string): number {
  const c = hex.replace("#", "");
  const r = parseInt(c.slice(0, 2), 16) / 255;
  const g = parseInt(c.slice(2, 4), 16) / 255;
  const b = parseInt(c.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  return (max + min) / 2;
}

describe("三色映射（trackColor）", () => {
  it("n=蓝 #3b82f6 / p=红 #ef4444 / e=黄 #eab308", () => {
    expect(trackColor("n")).toBe("#3b82f6");
    expect(trackColor("p")).toBe("#ef4444");
    expect(trackColor("e")).toBe("#eab308");
  });

  it("未知粒子类型 → 灰（TRACK_FALLBACK_COLOR）", () => {
    expect(trackColor("h")).toBe(TRACK_FALLBACK_COLOR);
    expect(trackColor("")).toBe(TRACK_FALLBACK_COLOR);
    expect(trackColor("photon")).toBe(TRACK_FALLBACK_COLOR);
  });

  it("常量表 TRACK_COLORS 与映射一致（legend 常量齐备）", () => {
    expect(TRACK_COLORS.n).toBe("#3b82f6");
    expect(TRACK_COLORS.p).toBe("#ef4444");
    expect(TRACK_COLORS.e).toBe("#eab308");
    expect(TRACK_PARTICLE_LABELS.n).toBe("中子");
    expect(TRACK_PARTICLE_LABELS.p).toBe("光子");
    expect(TRACK_PARTICLE_LABELS.e).toBe("电子");
    expect(TRACK_LEGEND.map((l) => l.key)).toEqual(["n", "p", "e"]);
  });
});

describe("能量深浅渐变（trackShade）", () => {
  it("低能浅、高能深：lightness 随 energy01 单调下降", () => {
    const lo = hexLightness(trackShade("#3b82f6", 0));
    const mid = hexLightness(trackShade("#3b82f6", 0.5));
    const hi = hexLightness(trackShade("#3b82f6", 1));
    expect(lo).toBeGreaterThan(mid);
    expect(mid).toBeGreaterThan(hi);
  });

  it("端点落在 SHADE_LIGHT / SHADE_DARK 常量（0=浅、1=深）", () => {
    expect(hexLightness(trackShade("#ef4444", 0))).toBeCloseTo(SHADE_LIGHT);
    expect(hexLightness(trackShade("#ef4444", 1))).toBeCloseTo(SHADE_DARK);
    expect(hexLightness(trackShade("#eab308", 0.5))).toBeCloseTo((SHADE_LIGHT + SHADE_DARK) / 2);
  });

  it("energy01 越界钳制到 [0,1]（不产生非法色）", () => {
    expect(hexLightness(trackShade("#3b82f6", -1))).toBeCloseTo(SHADE_LIGHT);
    expect(hexLightness(trackShade("#3b82f6", 2))).toBeCloseTo(SHADE_DARK);
  });

  it("灰度基色（灰）也参与深浅插值（只改 lightness，不改 hue/sat）", () => {
    // 灰 hue/sat 为 0，lightness 仍应随 energy01 变化
    expect(hexLightness(trackShade("#9ca3af", 0))).toBeGreaterThan(hexLightness(trackShade("#9ca3af", 1)));
  });
});

describe("能量归一化（normalizeEnergy01）", () => {
  it("全局 min/max → [0,1] 线性映射", () => {
    expect(normalizeEnergy01(1, { min: 1, max: 15 })).toBeCloseTo(0);
    expect(normalizeEnergy01(15, { min: 1, max: 15 })).toBeCloseTo(1);
    expect(normalizeEnergy01(8, { min: 1, max: 15 })).toBeCloseTo(0.5);
  });

  it("越界/退化区间钳制（range.max<=min → 0）", () => {
    expect(normalizeEnergy01(999, { min: 0, max: 1 })).toBe(1);
    expect(normalizeEnergy01(-5, { min: 0, max: 1 })).toBe(0);
    expect(normalizeEnergy01(5, { min: 5, max: 5 })).toBe(0);
    expect(normalizeEnergy01(NaN, { min: 0, max: 1 })).toBe(0);
  });
});
