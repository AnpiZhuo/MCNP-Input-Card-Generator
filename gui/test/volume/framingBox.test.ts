import { describe, it, expect } from "vitest";
import { computeFramingBox, VOLUME_FRAMING_RATIO, type AABB } from "../../src/volume/alignWorld";

/**
 * 用户实测反馈「默认视距特别大、把栅元弄的特别小」（PM 修复要求 3）：
 * 外壳远大于体积盒时取景以体积盒为主（避免视距过大、体积层小到看不见）；
 * 外壳较小 / 无外壳 / 体积可比时保持并集取景（既有行为，中心重合不回归）。
 * 纯函数（alignWorld），vitest 可测，不破坏 computeCameraParams 契约。
 */
describe("computeFramingBox（外壳≫体积时以体积为主）", () => {
  it("VOLUME_FRAMING_RATIO = 0.25（体积盒最大边 / 并集最大边阈值）", () => {
    expect(VOLUME_FRAMING_RATIO).toBe(0.25);
  });

  it("外壳远大于体积盒（200³ 外壳包 1×2×2 微网格）→ 以体积盒为主", () => {
    const shell: AABB = { min: [-100, -100, -100], max: [100, 100, 100] };
    const volume: AABB = { min: [0, 0, 0], max: [1, 2, 2] };
    const box = computeFramingBox(shell, volume);
    expect(box.min).toEqual(volume.min);
    expect(box.max).toEqual(volume.max);
  });

  it("无外壳（null）→ 体积盒", () => {
    const volume: AABB = { min: [-100, -100, -150], max: [100, 100, -50] };
    const box = computeFramingBox(null, volume);
    expect(box.min).toEqual(volume.min);
    expect(box.max).toEqual(volume.max);
  });

  it("外壳 ⊆ 体积（无独立外壳）→ 并集（= 体积）", () => {
    const shell: AABB = { min: [-10, -10, -10], max: [10, 10, 10] };
    const volume: AABB = { min: [-100, -100, -100], max: [100, 100, 100] };
    const box = computeFramingBox(shell, volume);
    expect(box).toEqual(volume);
  });

  it("外壳与体积盒可比（体积 ≥25% 并集）→ 保持并集取景（既有行为）", () => {
    const shell: AABB = { min: [-100, -100, -100], max: [100, 100, 100] };
    const volume: AABB = { min: [-30, -30, -30], max: [30, 30, 30] }; // 60/200 = 0.3 ≥ 0.25
    const box = computeFramingBox(shell, volume);
    expect(box.min).toEqual(shell.min);
    expect(box.max).toEqual(shell.max);
  });

  it("阈值边界：体积 24% 并集 → 体积为主；25% → 并集", () => {
    const shell: AABB = { min: [-100, -100, -100], max: [100, 100, 100] }; // 200
    const below: AABB = { min: [-24, -24, -24], max: [24, 24, 24] }; // 48/200 = 0.24 < 0.25
    const at: AABB = { min: [-25, -25, -25], max: [25, 25, 25] }; // 50/200 = 0.25
    const b1 = computeFramingBox(shell, below);
    expect(b1.min).toEqual(below.min);
    const b2 = computeFramingBox(shell, at);
    expect(b2.min).toEqual(shell.min);
  });

  it("体积⊂外壳 但比例 ≥0.25 → 保持并集取景（中心重合场景不回归）", () => {
    const shell: AABB = { min: [-100, -100, -100], max: [100, 100, 100] }; // 200
    const volume: AABB = { min: [-25, -25, -25], max: [25, 25, 25] }; // 50/200 = 0.25
    const box = computeFramingBox(shell, volume);
    expect(box).toEqual(shell);
  });

  it("用户真实场景：真实几何外壳包 1×2×2 微网格 → 以体积盒为主取景", () => {
    // 真实文件（tests/fixtures/real_meshtal_jk.meshtal，tally14/p/1×2×2）
    // grid_bounds 49,-10,90 ~ 51,10,110；外壳为实际 deck 模型（远大于网格）
    const shell: AABB = { min: [-100, -100, -150], max: [100, 100, 150] };
    const volume: AABB = { min: [49, -10, 90], max: [51, 10, 110] }; // 20/300 = 0.067 < 0.25
    const box = computeFramingBox(shell, volume);
    expect(box.min).toEqual(volume.min);
    expect(box.max).toEqual(volume.max);
  });
});
