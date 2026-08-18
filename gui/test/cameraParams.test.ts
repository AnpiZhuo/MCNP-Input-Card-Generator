import { describe, it, expect } from "vitest";
import { computeCameraParams } from "../src/three/cameraParams";

describe("computeCameraParams", () => {
  it("far/near bounded for inp01 bbox (center≈[0,0,5000], size≈[4000,4000,10000])", () => {
    // ±10000 大坐标场景：far/near 从 17.5M 收紧到 ≤1e4（远离 2^24 深度极限）
    const cp = computeCameraParams([0, 0, 5000], [4000, 4000, 10000]);
    expect(cp.farNear).toBeLessThanOrEqual(1e4);
    expect(cp.farNear).toBeGreaterThan(1);
    expect(cp.target).toEqual([0, 0, 5000]);
    expect(cp.far).toBeLessThan(2e6);
  });

  it("far/near bounded for shield bbox (±2000, 20m deck)", () => {
    const cp = computeCameraParams([0, 0, 0], [4000, 4000, 4000]);
    expect(cp.farNear).toBeLessThanOrEqual(1e4);
    expect(cp.near).toBeGreaterThan(0);
    expect(cp.far).toBeGreaterThan(cp.near);
    expect(cp.minDistance).toBeGreaterThan(cp.near);
  });

  it("monotonic bounded across bboxSize [1e-2, 1e5]", () => {
    for (const dim of [1e-2, 0.1, 1, 100, 1e3, 1e4, 1e5]) {
      const cp = computeCameraParams([0, 0, 0], [dim, dim, dim]);
      expect(cp.farNear).toBeLessThanOrEqual(1e4);
      expect(cp.near).toBeGreaterThan(0);
      expect(cp.near).toBeLessThan(cp.far);
      // near < minDistance：公式保证近裁剪面不越过相机轨道最小距离，几何不被裁剪
      expect(cp.minDistance).toBeGreaterThan(cp.near);
    }
  });

  it("position is center-relative with target=center", () => {
    const cp = computeCameraParams([100, 200, 300], [10, 20, 30]);
    expect(cp.target).toEqual([100, 200, 300]);
    const realExt = (30 * 0.5); // max(10,20,30)/2
    const viewDist = realExt * 3.5;
    expect(cp.position[0]).toBeCloseTo(100 + viewDist * 0.6);
    expect(cp.position[1]).toBeCloseTo(200 + viewDist * 0.6);
    expect(cp.position[2]).toBeCloseTo(300 + viewDist * 0.5);
  });

  it("取景框含原点时相机能看到原点（坐标轴在原点）", () => {
    // 主 3D 预览：模型中心 (10,0,0)、尺寸 2，取景框 = 模型 ∪ 原点 → 尺寸需覆盖 2*|center|
    const cp = computeCameraParams([10, 0, 0], [20, 20, 20]);
    const distToOrigin = Math.hypot(cp.position[0], cp.position[1], cp.position[2]);
    expect(distToOrigin).toBeLessThan(cp.far);
    expect(distToOrigin).toBeGreaterThan(cp.near);
    // far/near 仍受限（远离 2^24 深度极限）
    expect(cp.farNear).toBeLessThanOrEqual(1e4);
    expect(cp.target).toEqual([10, 0, 0]); // 旋转围绕模型中心
  });
});
