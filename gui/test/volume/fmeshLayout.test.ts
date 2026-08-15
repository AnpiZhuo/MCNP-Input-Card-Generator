import { describe, it, expect } from "vitest";
import { FMESH_ROW_LAYOUT } from "../../src/volume/fmeshState";

/**
 * FMeshForm 字段控件布局（2026-08-15 PM 指令：去掉简单/高级模式切换，改为按 MCNP 卡结构 9 行分组）。
 * - 始终显示完整字段表单（无简单/高级折叠）；FMESH_ROW_LAYOUT 决定控件排列。
 * - 每行对应 FMESH 卡体的一行结构：卡头（粒子/GEOM/OUT）→ ORIGIN →
 *   每轴 IMESH/IINTS → EMESH/EMINTS → TMESH/TMINTS → MAT/FACTOR/TR → AXS/VEC（圆柱系才显示）。
 * - 纯布局数据：字段值/placeholder/校验/round-trip 均不受影响。
 * 由原 simpleMode.test.ts（简单/高级模式可见性）按布局方向迁移而来。
 */

const ALL_FIELDS = [
  "particle", "geom", "origin", "imesh", "iints", "jmesh", "jints",
  "kmesh", "kints", "emesh", "emints", "tmesh", "tmints",
  "mat", "out", "axs", "vec", "tr", "factor",
];

describe("FMESH_ROW_LAYOUT（9 行分组，按 MCNP 卡结构）", () => {
  it("9 行分组结构正确（卡头→ORIGIN→各轴→能量/时间→MAT/FACTOR/TR→AXS/VEC）", () => {
    expect(FMESH_ROW_LAYOUT).toEqual([
      ["particle", "geom", "out"], // 第1行 卡头
      ["origin"],                  // 第2行 ORIGIN
      ["imesh", "iints"],          // 第3行 IMESH/IINTS
      ["jmesh", "jints"],          // 第4行 JMESH/JINTS
      ["kmesh", "kints"],          // 第5行 KMESH/KINTS
      ["emesh", "emints"],         // 第6行 EMESH/EMINTS
      ["tmesh", "tmints"],         // 第7行 TMESH/TMINTS
      ["mat", "factor", "tr"],     // 第8行 MAT/FACTOR/TR
      ["axs", "vec"],              // 第9行 AXS/VEC（仅圆柱系显示）
    ]);
  });

  it("全部字段恰好出现一次（无遗漏无重复，始终完整显示）", () => {
    const all = FMESH_ROW_LAYOUT.flat();
    expect(all.length).toBe(ALL_FIELDS.length);
    expect(new Set(all).size).toBe(all.length);
    for (const f of ALL_FIELDS) expect(all).toContain(f);
    for (const f of all) expect(ALL_FIELDS).toContain(f);
  });

  it("每组（边界+区间数）在同一行（IMESH/IINTS 等成对）", () => {
    for (const pair of [
      ["imesh", "iints"], ["jmesh", "jints"], ["kmesh", "kints"],
      ["emesh", "emints"], ["tmesh", "tmints"],
    ]) {
      const row = FMESH_ROW_LAYOUT.find((r) => r.includes(pair[0]));
      expect(row).toContain(pair[1]);
    }
  });

  it("MAT/FACTOR/TR 一行、AXS/VEC 一行（圆柱系才显示）", () => {
    expect(FMESH_ROW_LAYOUT[7]).toEqual(["mat", "factor", "tr"]);
    expect(FMESH_ROW_LAYOUT[8]).toEqual(["axs", "vec"]);
  });
});
