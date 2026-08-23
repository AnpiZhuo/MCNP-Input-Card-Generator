import { describe, expect, it } from "vitest";
import { filterPresets, PRESET_CATEGORIES } from "../src/components/MaterialPresets";

describe("filterPresets", () => {
  it("returns everything for an empty query", () => {
    const out = filterPresets(PRESET_CATEGORIES, "");
    expect(out).toBe(PRESET_CATEGORIES);
    expect(filterPresets(PRESET_CATEGORIES, "   ")).toBe(PRESET_CATEGORIES);
  });

  it("matches name case-insensitively and trims categories to hits", () => {
    const out = filterPresets(PRESET_CATEGORIES, "不锈钢");
    expect(out.length).toBeGreaterThan(0);
    const names = out.flatMap(([, items]) => items.map((i) => i.name));
    expect(names.every((n) => n.includes("不锈钢"))).toBe(true);
  });

  it("matches formula and desc fields too", () => {
    const byFormula = filterPresets(PRESET_CATEGORIES, "Bi4Ge3O12");
    expect(byFormula.flatMap(([, items]) => items.map((i) => i.key))).toContain("bgo");
    const byDesc = filterPresets(PRESET_CATEGORIES, "BGO 闪烁体");
    expect(byDesc.flatMap(([, items]) => items.map((i) => i.key))).toContain("bgo");
  });

  it("returns empty array when nothing matches", () => {
    expect(filterPresets(PRESET_CATEGORIES, "zzz-no-such-material-zzz")).toEqual([]);
  });
});
