import { describe, it, expect } from "vitest";
import {
  cardTextToFmesh, fmeshDefsToRows, fmeshToCardText,
  normalizeParticle, normalizeOut,
} from "../../src/volume/fmeshState";

/**
 * Bug 1 回归：FMESH 导入时下拉字段不更新（2026-08-15 PM 指令）。
 *
 * 根因：导入值小写（`fmesh14:p geom=xyz out=jk` → particle="p"/geom="xyz"/out="jk"），
 *       下拉选项大写（P/XYZ/JK）。geom 已有 normalizeGeom 归一化，particle/out 未归一化
 *       → React select 受控 value 不匹配任何 option → 下拉空白不更新。
 * 修复：导入/解析路径 particle/out/geom 统一归一化为下拉选项值（大小写不敏感匹配）。
 *
 * 回归样本 = tests/fixtures/official_fmesh_case1.i 的 FMESH 卡（原样复制，含尾部空格）。
 */
const OFFICIAL_FMESH_CARD = [
  "fmesh14:p geom=xyz out=jk ",
  "       origin= 49.0 -10.0 90.0  ",
  "       imesh 51  iints 1",
  "       jmesh 10 jints 2 ",
  "       kmesh 110.0 kints 2",
].join("\n");

describe("normalizeParticle / normalizeOut（归一化纯函数）", () => {
  it("normalizeParticle：小写 p/n → P/N，已大写不变，空 → 空", () => {
    expect(normalizeParticle("p")).toBe("P");
    expect(normalizeParticle("n")).toBe("N");
    expect(normalizeParticle("E")).toBe("E");
    expect(normalizeParticle("")).toBe("");
  });

  it("normalizeOut：小写 jk/col → JK/COL（命中下拉选项），未知值 f 保留原文（round-trip 保真）", () => {
    expect(normalizeOut("jk")).toBe("JK");
    expect(normalizeOut("col")).toBe("COL");
    expect(normalizeOut("xdmf")).toBe("XDMF");
    expect(normalizeOut("XDMF")).toBe("XDMF");
    expect(normalizeOut("f")).toBe("f"); // 非选项值：原文保留
    expect(normalizeOut("")).toBe("");
  });
});

describe("官方 case 导入 → 下拉选项值（Bug 1 回归）", () => {
  it("cardTextToFmesh：fmesh14:p geom=xyz out=jk → particle=P / geom=XYZ / out=JK", () => {
    const rows = cardTextToFmesh(OFFICIAL_FMESH_CARD);
    expect(rows.length).toBe(1);
    expect(rows[0].particle).toBe("P");
    expect(rows[0].geom).toBe("XYZ");
    expect(rows[0].out).toBe("JK");
  });

  it("fmeshDefsToRows（后端 parse 载荷，小写值）→ 同样归一化为下拉值", () => {
    const rows = fmeshDefsToRows([
      { number: 14, kind: "FMESH", particle: "p", geom: "xyz", out: "jk", origin: "49.0 -10.0 90.0", imesh: "51", iints: "1", jmesh: "10", jints: "2", kmesh: "110.0", kints: "2" },
    ]);
    expect(rows[0].particle).toBe("P");
    expect(rows[0].geom).toBe("XYZ");
    expect(rows[0].out).toBe("JK");
  });

  it("round-trip：解析 → 生成 → 再解析，粒子/GEOM/OUT 保持大写下拉值（不破坏生成）", () => {
    const rows = cardTextToFmesh(OFFICIAL_FMESH_CARD);
    const back = fmeshToCardText(rows);
    expect(back).toContain("FMESH14:P GEOM=XYZ ORIGIN=49.0 -10.0 90.0");
    expect(back).toContain("OUT=JK");
    const rows2 = cardTextToFmesh(back);
    expect(rows2[0].particle).toBe("P");
    expect(rows2[0].geom).toBe("XYZ");
    expect(rows2[0].out).toBe("JK");
    expect(rows2[0].imesh).toBe("51");
    expect(rows2[0].iints).toBe("1");
    expect(rows2[0].kmesh).toBe("110.0");
  });
});

describe("官方 case2~5 变体（含未知关键字 inc=）", () => {
  it("inc= 不污染字段，out=jk 仍归一化为 JK，round-trip 不丢", () => {
    const text = [
      "fmesh14:p geom=xyz out=jk  inc= 0",
      "       origin= 49.0 -10.0 90.0  ",
      "       imesh 51  iints 1",
      "       jmesh 10 jints 2 ",
      "       kmesh 110.0 kints 2",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].particle).toBe("P");
    expect(rows[0].out).toBe("JK");
    expect(rows[0].imesh).toBe("51");
    const back = fmeshToCardText(rows);
    const rows2 = cardTextToFmesh(back);
    expect(rows2[0].out).toBe("JK");
    expect(rows2[0].imesh).toBe("51");
  });
});
