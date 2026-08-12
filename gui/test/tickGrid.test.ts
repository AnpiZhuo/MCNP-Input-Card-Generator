import { describe, it, expect, vi } from "vitest";
import * as THREE from "three";
import { createTickGrid, planTickStep } from "../src/three/TickGrid";

const AXES: { dir: [number, number, number]; color: number }[] = [
  { dir: [1, 0, 0], color: 0xff4444 },
  { dir: [0, 0, 1], color: 0x44ff44 },
  { dir: [0, 1, 0], color: 0x4488ff },
];

/** 假纹理工厂：记账 dispose，验证纹理泄漏 */
function fakeTextureFactory(disposed: number[]) {
  return (_label: string, _color: number): THREE.Texture => {
    return { dispose: vi.fn(() => { disposed[0] += 1; }) } as unknown as THREE.Texture;
  };
}

describe("planTickStep", () => {
  it("does not saturate at 500 for large dist (STEPS extended to 1e6)", () => {
    expect(planTickStep(1e5)).toBeGreaterThan(500);
    expect(planTickStep(1e5)).toBeGreaterThanOrEqual(500);
    expect(planTickStep(1e6)).toBeGreaterThan(500);
    expect(planTickStep(35)).toBeGreaterThan(0);
    expect(planTickStep(1e5)).toBe(2e4);
  });
});

describe("createTickGrid", () => {
  it("rebuild fully disposes the previous batch (disposed == created)", () => {
    const group = new THREE.Group();
    const disposed = [0];
    const grid = createTickGrid(group, fakeTextureFactory(disposed));
    const r1 = grid.rebuild({ dist: 1000, axes: AXES });
    expect(r1.created).toBeGreaterThan(0);
    const r2 = grid.rebuild({ dist: 1000, axes: AXES });
    // 重建后：上一批对象全部释放（disposed==created，台账归零）
    expect(r2.disposed).toBe(r1.created);
    expect(r2.disposed).toBe(r2.created);
    // 上一批纹理也全部释放
    expect(disposed[0]).toBe(r1.textures);
  });

  it("object budget ≤ 60 / textures ≤ 30 for dist=1e5 (100m deck)", () => {
    const group = new THREE.Group();
    const grid = createTickGrid(group, fakeTextureFactory([0]));
    const r = grid.rebuild({ dist: 1e5, axes: AXES });
    expect(r.created).toBeLessThanOrEqual(60);
    expect(r.textures).toBeLessThanOrEqual(30);
  });

  it("dispose releases every object from the group", () => {
    const group = new THREE.Group();
    const grid = createTickGrid(group, fakeTextureFactory([0]));
    grid.rebuild({ dist: 1000, axes: AXES });
    expect(group.children.length).toBeGreaterThan(0);
    grid.dispose();
    expect(group.children.length).toBe(0);
  });
});
