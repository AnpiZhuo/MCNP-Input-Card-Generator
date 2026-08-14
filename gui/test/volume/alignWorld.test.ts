import { describe, it, expect } from "vitest";
import {
  worldBoxFromEdges, unionBoxes, translateToCenter, applyOffset, boxCenter, boxSize,
  type AABB, type Vec3, type Translatable,
} from "../../src/volume/alignWorld";

/**
 * 几何外壳与体积盒世界坐标对齐（契约 meshtal-visualization.md §7.3 四断言）
 * 1. shared_offset_invariant：SminScene==Smin+offset、VminScene==Vmin+offset
 * 2. world_box_from_edges：每轴 min=edge[0]、max=edge[-1]
 * 3. volume_inside_shell：归一化后体积盒 ⊆ 外壳（容差 1e-6）
 * 4. 尺寸保持 / 相对位移保持
 */

class MockGeo implements Translatable {
  public min: Vec3;
  public max: Vec3;
  constructor(min: Vec3, max: Vec3) {
    this.min = [...min] as Vec3;
    this.max = [...max] as Vec3;
  }
  translate(x: number, y: number, z: number): void {
    this.min = [this.min[0] + x, this.min[1] + y, this.min[2] + z];
    this.max = [this.max[0] + x, this.max[1] + y, this.max[2] + z];
  }
  bbox(): AABB {
    return { min: [...this.min] as Vec3, max: [...this.max] as Vec3 };
  }
}

describe("worldBoxFromEdges（§7.3 world_box_from_edges）", () => {
  it("每轴 min=edge[0]、max=edge[-1]", () => {
    const box = worldBoxFromEdges({
      x: [-100, -90, 0, 100],
      y: [0, 5, 10],
      z: [-150, -100, -50],
    });
    expect(box.min).toEqual([-100, 0, -150]);
    expect(box.max).toEqual([100, 10, -50]);
  });
});

describe("translateToCenter（§7.3 shared_offset_invariant）", () => {
  it("共享 offset 不变量：SminScene==Smin+offset、VminScene==Vmin+offset", () => {
    const shellBox: AABB = { min: [-100, -100, -150], max: [100, 100, 150] };
    const volumeBox: AABB = { min: [-20, -20, -30], max: [20, 20, 30] }; // V ⊆ S
    const unionBox = unionBoxes([shellBox, volumeBox]);
    const geo = new MockGeo(shellBox.min, shellBox.max);
    const offset = translateToCenter([geo], unionBox);

    // offset = -union 中心
    const uc = boxCenter(unionBox);
    expect(offset[0]).toBeCloseTo(-uc[0]);
    expect(offset[1]).toBeCloseTo(-uc[1]);
    expect(offset[2]).toBeCloseTo(-uc[2]);

    // SminScene == Smin + offset（外壳平移）
    const SminScene = geo.bbox().min;
    const SminPlus = applyOffset(shellBox.min, offset);
    expect(SminScene[0]).toBeCloseTo(SminPlus[0]);
    expect(SminScene[1]).toBeCloseTo(SminPlus[1]);
    expect(SminScene[2]).toBeCloseTo(SminPlus[2]);

    // VminScene == Vmin + offset（体积盒用同一 offset）
    const VminScene = applyOffset(volumeBox.min, offset);
    const VminPlus = applyOffset(volumeBox.min, offset);
    expect(VminScene).toEqual(VminPlus);
  });

  it("尺寸保持：VsizeScene == Vmax - Vmin", () => {
    const shellBox: AABB = { min: [-100, -100, -150], max: [100, 100, 150] };
    const volumeBox: AABB = { min: [-20, -20, -30], max: [20, 20, 30] };
    const unionBox = unionBoxes([shellBox, volumeBox]);
    const geo = new MockGeo(shellBox.min, shellBox.max);
    translateToCenter([geo], unionBox);
    const offset = unionBoxCenterNeg(unionBox);

    const VminScene = applyOffset(volumeBox.min, offset);
    const VmaxScene = applyOffset(volumeBox.max, offset);
    const VsizeScene: Vec3 = [
      VmaxScene[0] - VminScene[0],
      VmaxScene[1] - VminScene[1],
      VmaxScene[2] - VminScene[2],
    ];
    const vs = boxSize(volumeBox);
    expect(VsizeScene[0]).toBeCloseTo(vs[0]);
    expect(VsizeScene[1]).toBeCloseTo(vs[1]);
    expect(VsizeScene[2]).toBeCloseTo(vs[2]);
  });

  it("相对位移保持：(VminScene - SminScene) == (Vmin - Smin)", () => {
    const shellBox: AABB = { min: [-100, -100, -150], max: [100, 100, 150] };
    const volumeBox: AABB = { min: [-20, -20, -30], max: [20, 20, 30] };
    const unionBox = unionBoxes([shellBox, volumeBox]);
    const geo = new MockGeo(shellBox.min, shellBox.max);
    translateToCenter([geo], unionBox);
    const offset = unionBoxCenterNeg(unionBox);

    const VminScene = applyOffset(volumeBox.min, offset);
    const SminScene = geo.bbox().min;
    expect(VminScene[0] - SminScene[0]).toBeCloseTo(volumeBox.min[0] - shellBox.min[0]);
    expect(VminScene[1] - SminScene[1]).toBeCloseTo(volumeBox.min[1] - shellBox.min[1]);
    expect(VminScene[2] - SminScene[2]).toBeCloseTo(volumeBox.min[2] - shellBox.min[2]);
  });
});

describe("volume_inside_shell（§7.3 volume_inside_shell）", () => {
  it("归一化后体积盒场景包围盒 ⊆ 外壳场景包围盒（容差 1e-6）", () => {
    const shellBox: AABB = { min: [-100, -100, -150], max: [100, 100, 150] };
    const volumeBox: AABB = { min: [-20, -20, -30], max: [20, 20, 30] };
    const unionBox = unionBoxes([shellBox, volumeBox]);
    const geo = new MockGeo(shellBox.min, shellBox.max);
    translateToCenter([geo], unionBox);
    const offset = unionBoxCenterNeg(unionBox);

    const Smin = geo.bbox().min;
    const Smax = geo.bbox().max;
    const Vmin = applyOffset(volumeBox.min, offset);
    const Vmax = applyOffset(volumeBox.max, offset);
    for (let i = 0; i < 3; i++) {
      expect(Vmin[i]).toBeGreaterThanOrEqual(Smin[i] - 1e-6);
      expect(Vmax[i]).toBeLessThanOrEqual(Smax[i] + 1e-6);
    }
  });
});

function unionBoxCenterNeg(unionBox: AABB): Vec3 {
  const c = boxCenter(unionBox);
  return [-c[0], -c[1], -c[2]];
}
