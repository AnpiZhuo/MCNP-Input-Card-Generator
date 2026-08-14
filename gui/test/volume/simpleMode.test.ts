import { describe, it, expect } from "vitest";
import {
  FMESH_SIMPLE_FIELDS, FMESH_ADVANCED_FIELDS, simpleModeVisibleFields,
} from "../../src/volume/fmeshState";

/**
 * 简单/高级模式（PM 指令 2026-08-14：傻瓜友好改造）。
 * 简单模式默认只露核心 4 项：粒子（N/P/E）+ IMESH/JMESH/KMESH 三个范围输入；
 * 其余字段（ORIGIN/INTS×3/EMESH/EMINTS/TMESH/TMINTS/MAT/OUT/AXS/VEC/TR/factor/GEOM）
 * 折叠进高级模式。展开/收起状态存组件本地 state（不落 deck）。
 * 字段可见性抽为可测纯函数 simpleModeVisibleFields(mode)。
 */

describe("FMESH_SIMPLE_FIELDS（核心 4 项）", () => {
  it("粒子 + 三向网格范围，无其他字段", () => {
    expect(FMESH_SIMPLE_FIELDS).toEqual(["particle", "imesh", "jmesh", "kmesh"]);
  });
});

describe("FMESH_ADVANCED_FIELDS（高级追加）", () => {
  it("ORIGIN/INTS×3/能量/时间/MAT/OUT/AXS/VEC/TR/factor/GEOM 齐备", () => {
    for (const f of [
      "geom", "origin", "iints", "jints", "kints",
      "emesh", "emints", "tmesh", "tmints",
      "mat", "out", "axs", "vec", "tr", "factor",
    ]) {
      expect(FMESH_ADVANCED_FIELDS).toContain(f);
    }
    // factor 明确在高级模式
    expect(FMESH_ADVANCED_FIELDS).toContain("factor");
  });
});

describe("simpleModeVisibleFields(mode)", () => {
  it("简单模式只露核心 4 项", () => {
    expect(simpleModeVisibleFields("simple")).toEqual(["particle", "imesh", "jmesh", "kmesh"]);
  });

  it("高级模式 = 核心 4 项 + 高级追加（无重复）", () => {
    const adv = simpleModeVisibleFields("advanced");
    const set = new Set(adv);
    expect(set.size).toBe(adv.length);
    for (const f of ["particle", "imesh", "jmesh", "kmesh"]) expect(adv).toContain(f);
    for (const f of FMESH_ADVANCED_FIELDS) expect(adv).toContain(f);
    expect(adv).toContain("factor");
    expect(adv).toContain("out");
  });
});
