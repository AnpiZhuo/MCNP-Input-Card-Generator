import { describe, it, expect } from "vitest";
import {
  emptyFmeshRow, cardTextToFmesh, fmeshToCardText, buildFmeshPayload,
  fmeshDefsToRows, validateFmeshRow,
  type FmeshRow,
} from "../../src/volume/fmeshState";

/**
 * FACTOR 字段（PM 指令 2026-08-14：傻瓜友好改造 + factor 字段）。
 * 后端已同步：字段名 factor / 关键字 FACTOR= / 默认 1 / 序列化 JSON key= factor。
 * - FmeshRow.factor 默认 "1"（放高级模式）；
 * - 卡体生成发 `FACTOR=`（非空才发）；解析 `FACTOR=` → factor；
 * - validateFmeshRow 正整数校验（非法友好提示）。
 */

function row(partial: Partial<FmeshRow>): FmeshRow {
  return { ...emptyFmeshRow(), ...partial };
}

/** 带网格字段的合法行（干净，factor 为默认 1） */
const meshRow = () => row({
  number: "4",
  geom: "XYZ", origin: "0 0 0",
  imesh: "10", iints: "2",
  jmesh: "10", jints: "2",
  kmesh: "10", kints: "2",
});

describe("factor 字段 · 默认值", () => {
  it("emptyFmeshRow().factor 默认 '1'", () => {
    expect(emptyFmeshRow().factor).toBe("1");
  });
});

describe("factor · 卡体生成 FACTOR=", () => {
  it("结构化行非空 factor 生成 FACTOR=n（默认 1 也发）", () => {
    expect(fmeshToCardText([meshRow()])).toContain("FACTOR=1");
    expect(fmeshToCardText([row({ ...meshRow(), factor: "2" })])).toContain("FACTOR=2");
  });

  it("factor 空串不生成 FACTOR=", () => {
    const text = fmeshToCardText([row({ ...meshRow(), factor: "" })]);
    expect(text).not.toMatch(/FACTOR=/);
  });
});

describe("factor · 解析 FACTOR= → factor（round-trip 不丢）", () => {
  it("卡体含 FACTOR= → factor 字段，回放保留", () => {
    const text = "FMESH4:N GEOM=XYZ ORIGIN=0 0 0\n     IMESH=10 IINTS=2\n     JMESH=10 JINTS=2\n     KMESH=10 KINTS=2\n     FACTOR=3";
    const rows = cardTextToFmesh(text);
    expect(rows[0].factor).toBe("3");
    expect(fmeshToCardText(rows)).toContain("FACTOR=3");
    // 二次解析仍保留
    expect(cardTextToFmesh(fmeshToCardText(rows))[0].factor).toBe("3");
  });
});

describe("factor · 载荷 / 解析双向透传（JSON key = factor）", () => {
  it("buildFmeshPayload 带 factor key", () => {
    const rows = cardTextToFmesh("FMESH4:N GEOM=XYZ ORIGIN=0 0 0\n     IMESH=10 IINTS=2\n     JMESH=10 JINTS=2\n     KMESH=10 KINTS=2\n     FACTOR=2");
    expect(buildFmeshPayload(rows)[0].factor).toBe("2");
  });

  it("fmeshDefsToRows 读 factor（缺省默认 1）", () => {
    const rows = fmeshDefsToRows([{ number: 4, kind: "FMESH", particle: "N", geom: "XYZ", factor: "2" }]);
    expect(rows[0].factor).toBe("2");
    expect(fmeshDefsToRows([{ number: 4, kind: "FMESH", particle: "N", geom: "XYZ" }])[0].factor).toBe("1");
  });
});

describe("factor · 校验正整数", () => {
  it("合法正整数不报错（默认 1 干净行）", () => {
    expect(validateFmeshRow(meshRow()).filter((i) => i.field === "FACTOR")).toEqual([]);
  });

  it("0 / 负数 / 小数 / 非数值 / 科学计数法 报错 FACTOR（error）", () => {
    for (const bad of ["0", "-1", "1.5", "abc", "1e2", " 2 2"]) {
      const issues = validateFmeshRow(row({ ...meshRow(), factor: bad }));
      expect(issues.some((i) => i.field === "FACTOR" && i.level === "error")).toBe(true);
    }
  });

  it("空串不报错（未填不校验）", () => {
    const issues = validateFmeshRow(row({ ...meshRow(), factor: "" }));
    expect(issues.filter((i) => i.field === "FACTOR")).toEqual([]);
  });
});
