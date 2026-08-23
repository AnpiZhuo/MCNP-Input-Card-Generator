import { describe, expect, it } from "vitest";
import {
  buildDashboard,
  chooseSweepAxis,
  convergencePoints,
  type SweepParameter,
  type SweepRunRecord,
} from "../src/utils/sweepDashboard";

const params: SweepParameter[] = [
  { name: "nps", pattern: "NPS\\s+(\\d+)", values: [1000, 2000, 3000] },
  { name: "rkk", pattern: "kcode \\d+ ([\\d.]+)", values: [1.0] },
];

function rec(partial: Partial<SweepRunRecord>): SweepRunRecord {
  return {
    index: 1,
    parameters: { nps: 1000, rkk: 1.0 },
    exitCode: 0,
    keff: 1.001,
    ...partial,
  };
}

describe("chooseSweepAxis", () => {
  it("picks the first parameter with more than one distinct value", () => {
    expect(chooseSweepAxis(params)).toBe("nps");
  });

  it("falls back to the first parameter when all are constant", () => {
    expect(chooseSweepAxis([{ name: "rkk", pattern: "", values: [1.0] }])).toBe("rkk");
    expect(chooseSweepAxis([])).toBeNull();
  });
});

describe("buildDashboard", () => {
  it("sorts points by numeric axis value and maps keff/keffStd", () => {
    const records = [
      rec({ index: 1, parameters: { nps: 3000 }, keff: 1.003, keffStd: 0.002 }),
      rec({ index: 2, parameters: { nps: 1000 }, keff: 1.001, keffStd: 0.001 }),
      rec({ index: 3, parameters: { nps: 2000 }, keff: null, keffStd: null }),
    ];
    const d = buildDashboard(records, params);
    expect(d.paramName).toBe("nps");
    expect(d.points.map((p) => p.x)).toEqual([1000, 2000, 3000]);
    expect(d.points[0]).toEqual({ x: 1000, keff: 1.001, keffStd: 0.001 });
    expect(d.points[1]).toEqual({ x: 2000, keff: null, keffStd: null });
    expect(d.otherParams).toEqual(["rkk"]);
  });

  it("returns empty points when the axis value is not numeric", () => {
    const records = [rec({ parameters: { nps: "1e3" }, keff: 1.0 })];
    const d = buildDashboard(records, params);
    expect(d.points).toEqual([{ x: 1000, keff: 1.0, keffStd: null }]);
    const bad = buildDashboard(
      [rec({ parameters: { nps: "abc" } })],
      params,
    );
    expect(bad.points).toEqual([]);
  });

  it("no axis -> empty points but keeps runs", () => {
    const d = buildDashboard([rec({})], []);
    expect(d.paramName).toBeNull();
    expect(d.points).toEqual([]);
    expect(d.runs).toHaveLength(1);
  });
});

describe("convergencePoints", () => {
  it("zips cycles and mean, trimming to the shorter side", () => {
    const pts = convergencePoints({ cycles: [1, 2, 3], mean: [1.0, 1.001], std: [0.01, 0.011] });
    expect(pts).toEqual([
      { cycle: 1, mean: 1.0 },
      { cycle: 2, mean: 1.001 },
    ]);
  });

  it("handles null/empty input", () => {
    expect(convergencePoints(null)).toEqual([]);
    expect(convergencePoints(undefined)).toEqual([]);
    expect(convergencePoints({ cycles: [], mean: [], std: [] })).toEqual([]);
  });
});
