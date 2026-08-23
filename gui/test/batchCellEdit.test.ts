import { describe, it, expect } from "vitest";
import { applyBatchCellEdit, batchEditEmpty, type BatchCellEditValues } from "../src/utils/batchCellEdit";

const base = {
  num: "1",
  mat: "1",
  density: "-1.0",
  surfaces: "-1 2 -3",
  impN: "",
  impP: "",
  impE: "",
  vol: "",
  pwt: "",
  ext: "",
  fcl: "",
  u: "",
  fill: "",
  lat: "",
  trcl: "",
  tmp: "",
  otherParams: "",
  render: true,
  comment: "",
};

describe("applyBatchCellEdit", () => {
  it("空值不改对应字段（保持原值）", () => {
    const out = applyBatchCellEdit(base, { mat: "", density: "" });
    expect(out.mat).toBe("1");
    expect(out.density).toBe("-1.0");
    expect(out.surfaces).toBe("-1 2 -3");
  });

  it("填写材料/密度/IMP 覆盖对应字段", () => {
    const out = applyBatchCellEdit(base, { mat: "5", density: "0.5", impN: "1", impP: "1" });
    expect(out.mat).toBe("5");
    expect(out.density).toBe("0.5");
    expect(out.impN).toBe("1");
    expect(out.impP).toBe("1");
    expect(out.impE).toBe("");
  });

  it("高级参数批量覆盖", () => {
    const out = applyBatchCellEdit(base, { vol: "100", u: "2", tmp: "2.53e-8", otherParams: "TMP=2.53E-8" });
    expect(out.vol).toBe("100");
    expect(out.u).toBe("2");
    expect(out.tmp).toBe("2.53e-8");
    expect(out.otherParams).toBe("TMP=2.53E-8");
  });

  it("曲面表达式只追加，不覆盖已有内容", () => {
    const out = applyBatchCellEdit(base, { surfaceAppend: "4 -5" });
    expect(out.surfaces).toBe("-1 2 -3 4 -5");
  });

  it("有曲面表达式时为追加加空格分隔；无表达式时直接使用追加内容", () => {
    expect(applyBatchCellEdit(base, { surfaceAppend: "  4 " }).surfaces).toBe("-1 2 -3 4");
    expect(applyBatchCellEdit({ ...base, surfaces: "" }, { surfaceAppend: "4" }).surfaces).toBe("4");
  });

  it("追加内容空白时不改动曲面表达式", () => {
    const out = applyBatchCellEdit(base, { surfaceAppend: "   " });
    expect(out.surfaces).toBe("-1 2 -3");
  });

  it("不改原对象（不可变性）", () => {
    const cell = { ...base };
    applyBatchCellEdit(cell, { mat: "9", surfaceAppend: "4" });
    expect(cell.mat).toBe("1");
    expect(cell.surfaces).toBe("-1 2 -3");
  });
});

describe("batchEditEmpty", () => {
  it("全部为空视为无写操作", () => {
    expect(batchEditEmpty({})).toBe(true);
    expect(batchEditEmpty({ mat: "" })).toBe(true);
    expect(batchEditEmpty({ surfaceAppend: "  " })).toBe(true);
  });

  it("任一字段有值即非空", () => {
    expect(batchEditEmpty({ mat: "3" })).toBe(false);
    expect(batchEditEmpty({ impN: "1" })).toBe(false);
    expect(batchEditEmpty({ surfaceAppend: "4" })).toBe(false);
  });
});
