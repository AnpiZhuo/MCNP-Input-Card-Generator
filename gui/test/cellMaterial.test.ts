import { describe, it, expect } from "vitest";
import { buildCellMaterial } from "../src/three/cellMaterial";

describe("buildCellMaterial", () => {
  it("default is opaque (no transparent overdraw)", () => {
    const spec = buildCellMaterial({ color: "#3366ff" });
    expect(spec.transparent).toBe(false);
    expect(spec.depthWrite).toBe(true);
    expect(spec.opacity).toBe(1);
  });

  it("see-through mode is transparent (opacity 0.6, depthWrite off)", () => {
    const spec = buildCellMaterial({ color: "#3366ff", transparentMode: "see-through" });
    expect(spec.transparent).toBe(true);
    expect(spec.depthWrite).toBe(false);
    expect(spec.opacity).toBe(0.6);
  });

  it("vacuum color (M0) keeps opacity 0 in both modes", () => {
    const opaque = buildCellMaterial({ color: "transparent" });
    expect(opaque.opacity).toBe(0);
    const see = buildCellMaterial({ color: "transparent", transparentMode: "see-through" });
    expect(see.opacity).toBe(0);
  });

  // 2026-10-11 用户：「真空也要生成 STL，只是在 3D 预览的时候改为透明，不影响实体查看」
  // 默认（不传 vacuumOpacity）必须保持 opacity 0 —— 体积窗口/源演示/径迹等多个渲染器
  // 共用本函数，改默认值会把它们的外壳一起改亮。
  it("真空档位可由调用方显式开启（默认仍 0，不影响其它渲染器）", () => {
    const semi = buildCellMaterial({
      color: "transparent", vacuumOpacity: 0.15, vacuumColor: "#b0bec5",
    });
    expect(semi.opacity).toBe(0.15);
    expect(semi.color).toBe("#b0bec5");
    expect(semi.transparent).toBe(true);
    expect(semi.depthWrite).toBe(false);
    // 任意透明档位下真空都保持调用方给的档位（不被 see-through 的 0.6 覆盖）
    const inSeeThrough = buildCellMaterial({
      color: "transparent", transparentMode: "see-through", vacuumOpacity: 0.15,
    });
    expect(inSeeThrough.opacity).toBe(0.15);
  });
});
