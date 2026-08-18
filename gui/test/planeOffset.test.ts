import { describe, it, expect } from "vitest";
import { offsetPlaneForStl } from "../src/three/planeOffset";

describe("offsetPlaneForStl（预览显示系 → 原始 STL 坐标系）", () => {
  it("X=0 平面 + 模型中心 (6,0,0) → 原始 D=6（正中切偏移盒）", () => {
    const p = offsetPlaneForStl({ A: 1, B: 0, C: 0, D: 0 }, { x: 6, y: 0, z: 0 });
    expect(p).toEqual({ A: 1, B: 0, C: 0, D: 6 });
  });

  it("模型中心在原点时保持不变", () => {
    const p = offsetPlaneForStl({ A: 0, B: 0, C: 1, D: 2 }, { x: 0, y: 0, z: 0 });
    expect(p).toEqual({ A: 0, B: 0, C: 1, D: 2 });
  });

  it("一般平面按 n·center 平移 D，法向不变", () => {
    const p = offsetPlaneForStl({ A: 1, B: 2, C: 3, D: 4 }, { x: 5, y: 6, z: 7 });
    expect(p.A).toBe(1);
    expect(p.B).toBe(2);
    expect(p.C).toBe(3);
    expect(p.D).toBeCloseTo(4 + 5 + 12 + 21); // 42
  });
});
