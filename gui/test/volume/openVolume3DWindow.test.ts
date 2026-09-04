import { describe, it, expect } from "vitest";
import { isDepositionTally } from "../../src/volume/openVolume3DWindow";
import { cardTextToFmesh } from "../../src/volume/fmeshState";

describe("isDepositionTally — *fmesh 能量沉积判定", () => {
  it("卡号匹配且 fn_prefix='*' → 能量沉积", () => {
    const fmesh = cardTextToFmesh([
      "*fmesh14:N GEOM=XYZ ORIGIN=0 0 0",
      "     IMESH=10 IINTS=2",
      "     JMESH=10 JINTS=2",
    ].join("\n"));
    expect(isDepositionTally(fmesh, 14)).toBe(true);
  });

  it("卡号匹配但无 *（普通 fefm）→ 非能量沉积", () => {
    const fmesh = cardTextToFmesh("FMESH14:N GEOM=XYZ ORIGIN=0 0 0\n     IMESH=10 IINTS=2");
    expect(isDepositionTally(fmesh, 14)).toBe(false);
  });

  it("卡号不匹配 → 非能量沉积；空列表 → false", () => {
    const fmesh = cardTextToFmesh("*fmesh14:N GEOM=XYZ ORIGIN=0 0 0\n     IMESH=10 IINTS=2");
    expect(isDepositionTally(fmesh, 15)).toBe(false);
    expect(isDepositionTally([], 14)).toBe(false);
    expect(isDepositionTally(undefined, 14)).toBe(false);
  });
});
