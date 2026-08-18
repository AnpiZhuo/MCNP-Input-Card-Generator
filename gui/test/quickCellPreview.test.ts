import { describe, it, expect } from "vitest";
import * as THREE from "three";
import type { Line } from "three";
import { buildQuickCellPreview, wireColorForMaterial } from "../src/three/quickCellPreview";
import { computeCameraParams } from "../src/three/cameraParams";

function frame(shape: any, config: any): void {
  const prev = buildQuickCellPreview(shape, config);
  const box = new THREE.Box3().setFromObject(prev.group);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const ext = Math.max(size.x, size.y, size.z, 1e-3);
  const cp = computeCameraParams([center.x, center.y, center.z], [ext, ext, ext]);
  expect(cp.far).toBeGreaterThan(cp.near);
  prev.dispose();
}

function collectLines(shape: any, config: any): [number, number, number][][] {
  const prev = buildQuickCellPreview(shape, config);
  const segs: [number, number, number][][] = [];
  prev.group.traverse((obj) => {
    const pos = (obj as Line).geometry?.getAttribute?.("position");
    if (!pos) return;
    const pts: [number, number, number][] = [];
    for (let i = 0; i < pos.count; i++) pts.push([pos.getX(i), pos.getY(i), pos.getZ(i)]);
    segs.push(pts);
  });
  prev.dispose();
  return segs;
}

describe("快捷建栅元线框预览（RPP）", () => {
  it("wireColorForMaterial：M0 白线，其余用材料色", () => {
    expect(wireColorForMaterial("0")).toBe(0xffffff);
    // getMatColor("1") = COLORS[1] = "#00C853"
    expect(wireColorForMaterial("1")).toBe(0x00c853);
  });

  it("各种配置取景正常（不抛错、far>near）", () => {
    frame("rpp", { size: [2, 2, 2], center: [0, 0, 0], angles: [0, 0, 0], nx: 2, ny: 2, nz: 2 });
    frame("rpp", { size: [2, 2, 2], center: [10, 0, 0], angles: [0, 0, Math.PI / 2], nx: 2, ny: 1, nz: 1 });
    frame("rpp", { size: [2, 4, 6], center: [0, 0, 5], angles: [0, Math.PI / 6, Math.PI / 4], nx: 2, ny: 3, nz: 4 });
  });

  it("2×2×2 切分矩形跨满截面（回归：曾只画中心象限，看不出 8 个立方体）", () => {
    const segs = collectLines("rpp", { size: [2, 2, 2], center: [0, 0, 0], angles: [0, 0, 0], nx: 2, ny: 2, nz: 2 });
    const has = (p: [number, number, number]) => segs.some((s) => s.some((q) => q.every((v, k) => Math.abs(v - p[k]) < 1e-6)));
    // x=0 截面：整条 y∈[-1,1]、z∈[-1,1] 的矩形四角
    expect(has([0, -1, -1])).toBe(true);
    expect(has([0, 1, 1])).toBe(true);
    // y=0 截面
    expect(has([-1, 0, -1])).toBe(true);
    expect(has([1, 0, 1])).toBe(true);
    // z=0 截面
    expect(has([-1, -1, 0])).toBe(true);
    expect(has([1, 1, 0])).toBe(true);
  });

  it("坐标轴固定在原点 (0,0,0) 的世界 X/Y/Z（不随体移动/旋转）", () => {
    const all = collectLines("rpp", { size: [2, 2, 2], center: [10, 0, 0], angles: [0, 0, Math.PI / 2], nx: 1, ny: 1, nz: 1 }).flat();
    const has = (p: [number, number, number]) => all.some((q) => q.every((v, k) => Math.abs(v - p[k]) < 1e-6));
    // 体中心在 (10,0,0) 时轴仍在原点：alen = max(1, 10*0.35=3.5, 0.5) = 3.5
    expect(has([0, 0, 0])).toBe(true);   // 轴起点在原点
    expect(has([3.5, 0, 0])).toBe(true); // +X 红
    expect(has([0, 3.5, 0])).toBe(true); // +Y 绿
    expect(has([0, 0, 3.5])).toBe(true); // +Z 蓝
  });
});
