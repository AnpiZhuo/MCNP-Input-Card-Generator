import { describe, it, expect } from "vitest";
import { computeVolumeCamera } from "../../src/volume/VolumeRenderer";
import type { AABB } from "../../src/volume/alignWorld";

/**
 * A2.1 开窗自动取景：相机按「几何+体积」联合包围盒自动摆好（纯函数，DOM-lite）
 * 契约 meshtal-visualization.md §12 A2.1 / §7.2 第 7 步。
 */
describe("computeVolumeCamera（A2.1 开窗自动取景）", () => {
  const unionBox: AABB = {
    min: [-100, -100, -150],
    max: [100, 100, -50],
  };

  it("target = 联合包围盒中心（开窗即见全貌）", () => {
    const cp = computeVolumeCamera(unionBox);
    expect(cp.target[0]).toBeCloseTo(0);
    expect(cp.target[1]).toBeCloseTo(0);
    expect(cp.target[2]).toBeCloseTo(-100);
  });

  it("position 相对中心偏移（视角 0.6/0.6/0.5）", () => {
    const cp = computeVolumeCamera(unionBox);
    // size = [200,200,100] → maxDim=200 → realExt=100 → viewDist=350
    const viewDist = 100 * 3.5;
    expect(cp.position[0]).toBeCloseTo(viewDist * 0.6);
    expect(cp.position[1]).toBeCloseTo(viewDist * 0.6);
    expect(cp.position[2]).toBeCloseTo(-100 + viewDist * 0.5);
  });

  it("near/far 收紧（farNear ≤ 1e4，深度精度）", () => {
    const cp = computeVolumeCamera(unionBox);
    expect(cp.farNear).toBeLessThanOrEqual(1e4);
    expect(cp.near).toBeGreaterThan(0);
    expect(cp.minDistance).toBeGreaterThan(cp.near);
  });

  it("联合包围盒变大 → 相机距离随之放大（视角覆盖全貌）", () => {
    const small = computeVolumeCamera({ min: [-10, -10, -10], max: [10, 10, 10] });
    const big = computeVolumeCamera({ min: [-1000, -1000, -1000], max: [1000, 1000, 1000] });
    const dist = (cp: { position: number[] }) => Math.hypot(cp.position[0], cp.position[1], cp.position[2]);
    expect(dist(big)).toBeGreaterThan(dist(small) * 50);
  });

  it("体积盒 ⊆ 外壳时（union=外壳）取景仍覆盖体积盒（中心重合）", () => {
    // 体积盒在内部偏置，联合盒中心 = 外壳中心
    const shell: AABB = { min: [-100, -100, -150], max: [100, 100, 150] };
    const volume: AABB = { min: [-20, -20, -30], max: [20, 20, 30] };
    const union: AABB = {
      min: [Math.min(shell.min[0], volume.min[0]), Math.min(shell.min[1], volume.min[1]), Math.min(shell.min[2], volume.min[2])],
      max: [Math.max(shell.max[0], volume.max[0]), Math.max(shell.max[1], volume.max[1]), Math.max(shell.max[2], volume.max[2])],
    };
    const cp = computeVolumeCamera(union);
    // union 盒中心 = 外壳中心 ≈ 原点
    expect(cp.target[0]).toBeCloseTo(0);
    expect(cp.target[1]).toBeCloseTo(0);
    expect(cp.target[2]).toBeCloseTo(0);
    expect(cp.farNear).toBeLessThanOrEqual(1e4);
  });
});
