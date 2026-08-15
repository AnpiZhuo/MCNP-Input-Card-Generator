import { describe, it, expect } from "vitest";
import {
  applyOffsetToBox,
  boxCenter,
  computeFramingBox,
  unionBoxes,
  type AABB,
} from "../../src/volume/alignWorld";
import { computeVolumeCamera } from "../../src/volume/VolumeRenderer";

/**
 * P0 第二弹：相机必须用 offset 后的场景坐标（契约 §7 对齐不变式）。
 *
 * 根因（用户实测 v1.7.2「摄像机位置不对，渲染出来的位置也不对」）：
 * VolumeRenderer.alignAndFrame 用 `translateToCenter` 把外壳/体积盒平移到场景中心
 * （offset = -unionBox.center），但相机参数却用**未 offset 的 world 坐标**
 * （computeVolumeCamera(computeFramingBox(worldBox))）→ 相机盯着 world 中心（如 (50,0,100)），
 * 而物体在原点 → 相机对空、物体偏出视锥/极小。
 *
 * 本组断言锁定：相机 target/position 必须基于 offset 后的场景盒。
 */
describe("相机-几何 offset 一致性（P0 相机错位回归）", () => {
  // 用户真实数据：tally14/p/1×2×2，grid_bounds 49,-10,90 ~ 51,10,110，中心 (50,0,100)
  const volumeBox: AABB = { min: [49, -10, 90], max: [51, 10, 110] };
  // 大外壳（包含体积盒）：中心 (50,0,100)，远大于体积盒
  const shellBox: AABB = { min: [-100, -100, -50], max: [200, 100, 250] };

  const unionCenter = () => {
    const union = unionBoxes([shellBox, volumeBox]);
    return boxCenter(union);
  };

  it("applyOffsetToBox：世界盒 + offset → 场景盒（min/max 同步平移，尺寸不变）", () => {
    const offset: [number, number, number] = [-50, 0, -100];
    const s = applyOffsetToBox(volumeBox, offset);
    expect(s.min).toEqual([-1, -10, -10]);
    expect(s.max).toEqual([1, 10, 10]);
  });

  it("相机 target = 场景盒中心（= 世界中心 + offset）；联合盒居中时 target ≈ 原点", () => {
    const c = unionCenter();
    const offset: [number, number, number] = [-c[0], -c[1], -c[2]];
    const scene = applyOffsetToBox(volumeBox, offset);
    const cp = computeVolumeCamera(scene);
    expect(cp.target[0]).toBeCloseTo(boxCenter(volumeBox)[0] + offset[0], 6);
    expect(cp.target[1]).toBeCloseTo(boxCenter(volumeBox)[1] + offset[1], 6);
    expect(cp.target[2]).toBeCloseTo(boxCenter(volumeBox)[2] + offset[2], 6);
    // 用户场景：体积盒中心 = 联合盒中心 = (50,0,100) → offset 后 target ≈ 0
    expect(cp.target[0]).toBeCloseTo(0, 6);
    expect(cp.target[1]).toBeCloseTo(0, 6);
    expect(cp.target[2]).toBeCloseTo(0, 6);
  });

  it("position 相对场景中心偏移（target 居中时 position ≈ viewDist*(0.6,0.6,0.5)）", () => {
    const c = unionCenter();
    const offset: [number, number, number] = [-c[0], -c[1], -c[2]];
    const scene = applyOffsetToBox(volumeBox, offset);
    const cp = computeVolumeCamera(scene);
    // 尺寸平移不变：maxDim=20 → realExt=10 → viewDist=35
    expect(cp.position[0]).toBeCloseTo(35 * 0.6, 6);
    expect(cp.position[1]).toBeCloseTo(35 * 0.6, 6);
    expect(cp.position[2]).toBeCloseTo(35 * 0.5, 6);
  });

  it("farNear ≤ 1e4 铁律保持（offset 不改尺寸，near/far 不受影响）", () => {
    const c = unionCenter();
    const offset: [number, number, number] = [-c[0], -c[1], -c[2]];
    const cp = computeVolumeCamera(applyOffsetToBox(volumeBox, offset));
    expect(cp.farNear).toBeLessThanOrEqual(1e4);
    expect(cp.near).toBeGreaterThan(0);
    expect(cp.minDistance).toBeGreaterThan(cp.near);
  });

  it("场景取景全链路：world framing → applyOffsetToBox → computeVolumeCamera（外壳≫体积时以体积为主）", () => {
    const framingWorld = computeFramingBox(shellBox, volumeBox); // shell≫volume → volumeBox
    expect(framingWorld).toEqual(volumeBox);
    const c = unionCenter();
    const offset: [number, number, number] = [-c[0], -c[1], -c[2]];
    const cp = computeVolumeCamera(applyOffsetToBox(framingWorld, offset));
    expect(cp.target[0]).toBeCloseTo(0, 6);
    expect(cp.target[1]).toBeCloseTo(0, 6);
    expect(cp.target[2]).toBeCloseTo(0, 6);
    // 相机能看到体积盒（position 距 target ≈ viewDist，盒子尺寸 2×20×20 在视锥内）
    expect(cp.position[0]).toBeCloseTo(35 * 0.6, 6);
  });

  it("无外壳场景：shellBox=null → framing=体积盒 → offset 后相机对原点", () => {
    const c = boxCenter(volumeBox); // (50,0,100)
    const offset: [number, number, number] = [-c[0], -c[1], -c[2]];
    const framingWorld = computeFramingBox(null, volumeBox);
    expect(framingWorld).toEqual(volumeBox);
    const cp = computeVolumeCamera(applyOffsetToBox(framingWorld, offset));
    expect(cp.target[0]).toBeCloseTo(0, 6);
    expect(cp.target[1]).toBeCloseTo(0, 6);
    expect(cp.target[2]).toBeCloseTo(0, 6);
  });
});
