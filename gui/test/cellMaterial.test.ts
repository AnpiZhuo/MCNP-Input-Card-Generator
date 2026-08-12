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
});
