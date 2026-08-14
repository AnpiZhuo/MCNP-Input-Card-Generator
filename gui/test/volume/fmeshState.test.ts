import { describe, it, expect } from "vitest";
import {
  emptyFmeshRow, cardTextToFmesh, fmeshToCardText, buildFmeshPayload,
  fmeshDefsToRows, FMESH_PLACEHOLDERS,
} from "../../src/volume/fmeshState";

/**
 * FMESH/TMESH 卡体 ↔ 结构化（契约 meshtal-visualization.md §5.3 / §4.7.1）
 * 镜像后端 fmesh_parser.py：结构化字段原文保留 + raw 兜底（round-trip 保真）。
 */
describe("FMESH 卡体 → 结构化 → 回放", () => {
  it("FMESHn:N 单卡往返", () => {
    const text = [
      "FMESH4:N GEOM=xyz ORIGIN=-100 -100 -150",
      "     IMESH=100 IINTS=10",
      "     JMESH=100 JINTS=10",
      "     KMESH=-50 KINTS=100",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].kind).toBe("FMESH");
    expect(rows[0].number).toBe("4");
    expect(rows[0].particle).toBe("N");
    expect(rows[0].geom).toBe("xyz");
    expect(rows[0].origin).toBe("-100 -100 -150");
    expect(rows[0].imesh).toBe("100");
    expect(rows[0].iints).toBe("10");
    expect(rows[0].kmesh).toBe("-50");
    expect(rows[0].kints).toBe("100");

    const back = fmeshToCardText(rows);
    expect(back).toContain("FMESH4:N GEOM=xyz ORIGIN=-100 -100 -150");
    expect(back).toContain("IMESH=100");
    expect(back).toContain("IINTS=10");
  });

  it("多区间 IMESH=a b IINTS=2 2 保留原文", () => {
    const text = "FMESH1:P GEOM=xyz ORIGIN=0 0 0\n     IMESH=10 20 IINTS=2 2\n     JMESH=10 JINTS=2\n     KMESH=10 KINTS=2";
    const rows = cardTextToFmesh(text);
    expect(rows[0].imesh).toBe("10 20");
    expect(rows[0].iints).toBe("2 2");
    expect(rows[0].jmesh).toBe("10");
    expect(rows[0].jints).toBe("2");
  });

  it("能量/时间边界 EMESH/TMESH + TINTS 字段映射", () => {
    const text = [
      "FMESH5:N GEOM=xyz ORIGIN=0 0 0",
      "     IMESH=10 IINTS=2",
      "     JMESH=10 IINTS=2",
      "     KMESH=10 KINTS=2",
      "     EMESH=1e-6 1 14 EINTS=2 2",
      "     TMESH=1 10 TINTS=2",
      "     MAT=3",
      "     OUT=f",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows[0].emesh).toBe("1e-6 1 14");
    expect(rows[0].eints).toBe("2 2");
    expect(rows[0].tmesh).toBe("1 10");
    expect(rows[0].t_ints).toBe("2");
    expect(rows[0].mat).toBe("3");
    expect(rows[0].out).toBe("f");
  });
});

describe("TMESH RMESHn 吸收", () => {
  it("TMESHn 标题行 + RMESHn 子卡 → TMESH kind 行", () => {
    const text = [
      "TMESH4",
      "     RMESH4:N GEOM=xyz ORIGIN=0 0 0",
      "     IMESH=10 IINTS=2",
      "     JMESH=10 IINTS=2",
      "     KMESH=10 KINTS=2",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].kind).toBe("TMESH");
    expect(rows[0].number).toBe("4");
    const back = fmeshToCardText(rows);
    expect(back).toContain("TMESH4");
    expect(back).toContain("RMESH4:N GEOM=xyz ORIGIN=0 0 0");
  });
});

describe("raw 兜底（round-trip 保真）", () => {
  it("结构化字段为空 → 回放 raw 原文", () => {
    const raw = "FMESH9:N GEOM=xyz\n     ORIGIN=1 2 3";
    const rows = cardTextToFmesh(raw);
    // ORIGIN 有值 → 结构化回放；此处测结构化为空场景
    const empty = { ...emptyFmeshRow(), kind: "FMESH" as const, number: "7", raw: "FMESH7:P GEOM=cyl" };
    const back = fmeshToCardText([empty]);
    expect(back).toContain("FMESH7:P GEOM=cyl");
    expect(rows.length).toBeGreaterThanOrEqual(1);
  });
});

describe("buildFmeshPayload（→ tally.fmesh_defs，后端 key 对齐）", () => {
  it("number 数值化 + 字段名含 t_ints", () => {
    const rows = cardTextToFmesh("FMESH4:N GEOM=xyz ORIGIN=0 0 0\n     IMESH=10 IINTS=2\n     TMESH=1 10 TINTS=2");
    const payload = buildFmeshPayload(rows);
    expect(payload[0].number).toBe(4);
    expect(payload[0].t_ints).toBe("2");
    expect(payload[0].imesh).toBe("10");
    expect(payload[0].kind).toBe("FMESH");
  });

  it("空 → 空数组", () => {
    expect(buildFmeshPayload([])).toEqual([]);
  });
});

describe("fmeshDefsToRows（后端 parse → 前端 FmeshRow）", () => {
  it("缺 key 容忍 + t_ints 映射", () => {
    const rows = fmeshDefsToRows([
      { number: 4, kind: "FMESH", particle: "N", origin: "0 0 0", t_ints: "2" },
    ]);
    expect(rows[0].number).toBe("4");
    expect(rows[0].t_ints).toBe("2");
    expect(rows[0].geom).toBe("xyz");
  });
});

describe("FMESH_PLACEHOLDERS 幽灵文字（F5.1）", () => {
  it("关键字作用说明齐备", () => {
    expect(FMESH_PLACEHOLDERS.origin).toContain("网格原点坐标");
    expect(FMESH_PLACEHOLDERS.imesh).toContain("网格边界");
    expect(FMESH_PLACEHOLDERS.out).toContain("f|q|n");
    expect(FMESH_PLACEHOLDERS.mat).toContain("材料");
    expect(FMESH_PLACEHOLDERS.geom).toContain("xyz");
  });
});
