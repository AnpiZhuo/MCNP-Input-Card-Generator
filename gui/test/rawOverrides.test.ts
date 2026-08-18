import { describe, it, expect } from "vitest";
import { buildRawOverrides } from "../src/utils/rawOverrides";

describe("buildRawOverrides（生成时 raw_overrides 载荷构造）", () => {
  it("源卡文本模式：textMode.sdef + rawOverrides.sdef → 载荷带上 sdef 原文本（回归：源卡漏生成）", () => {
    const ro = buildRawOverrides({
      textMode: { sdef: true },
      rawOverrides: { sdef: "SDEF ERG=14 POS=0 0 0" },
    });
    expect(ro.sdef).toBe("SDEF ERG=14 POS=0 0 0");
  });

  it("非文本模式（textMode.sdef 缺省/false）→ 载荷不带 sdef", () => {
    expect(buildRawOverrides({ rawOverrides: { sdef: "SDEF ERG=14" } })).toEqual({});
    expect(
      buildRawOverrides({
        textMode: { sdef: false },
        rawOverrides: { sdef: "SDEF ERG=14" },
      }),
    ).toEqual({});
  });

  it("材料/栅元/计数文本模式原有行为不回归", () => {
    const ro = buildRawOverrides({
      textMode: { materials: true, cells: true, tally: true },
      rawOverrides: {
        materials: "M1 1001 -1",
        cells: "1 1 -1 -1",
        tally: "F4:N 1",
        sdef: "SDEF ERG=14",
      },
    });
    expect(ro).toEqual({
      materials: "M1 1001 -1",
      cells: "1 1 -1 -1",
      tally: "F4:N 1",
    });
  });
});
