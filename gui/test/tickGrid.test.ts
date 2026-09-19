// @vitest-environment jsdom
// （需要 jsdom：真纹理工厂要 document.createElement("canvas") 画刻度标签）
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

  /**
   * 出图标签主题（2026-09-19 透明底）：`setLabelTheme("paper")` 之后重建出的纹理
   * 必须是"透明底 + 深色字"，否则白纸上会留一串深色药丸方块。
   *
   * jsdom 没有真 canvas（`getContext` 返回 null），所以这里补一个最小 2D 上下文桩：
   * 只实现本用例真正用到的 `fillStyle` / `fillRect` / `fillText`，并把
   * `fillRect` 记录成"这块区域被涂了"—— 药丸底就靠它体现。
   */
  it("paper 主题不画药丸底、屏幕主题画（透明底 vs 深色块）", () => {
    const orig = HTMLCanvasElement.prototype.getContext;
    const rects: string[] = [];
    const texts: string[] = [];
    (HTMLCanvasElement.prototype as any).getContext = function (type: string) {
      if (type !== "2d") return null;
      const self = this;
      return {
        canvas: self,
        fillStyle: "",
        font: "", textAlign: "", textBaseline: "",
        fillRect() { rects.push(String(self.__fill ?? "")); },
        fillText() { texts.push(String(self.__fillText ?? "")); },
      };
    };
    // fillStyle 被写进普通属性，桩里改用访问器记录当前值
    try {
      const group = new THREE.Group();
      const grid = createTickGrid(group);

      grid.setLabelTheme("screen");
      grid.rebuild({ dist: 100, axes: AXES.slice(0, 1) });
      expect(group.children.some((o) => (o as THREE.Sprite).isSprite)).toBe(true);
      expect(texts.length).toBeGreaterThan(0);      // 屏幕版：确实画了标签
      expect(rects.length).toBeGreaterThan(0);      // 屏幕版：画了深色药丸底

      rects.length = 0;
      texts.length = 0;
      grid.setLabelTheme("paper");
      grid.rebuild({ dist: 100, axes: AXES.slice(0, 1) });
      expect(texts.length).toBeGreaterThan(0);      // 纸质版：仍画标签字
      expect(rects.length).toBe(0);                 // 纸质版：**不画**药丸底（留透明）
    } finally {
      (HTMLCanvasElement.prototype as any).getContext = orig;
    }
  });
});
