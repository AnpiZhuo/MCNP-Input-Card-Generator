import { describe, it, expect } from "vitest";
import { parseTallyTypeNumber, parseF5Variant } from "../src/components/TallyTab";

/*
 * 计数编号 → 类型自动映射（TallyTab.tsx）—— 纯函数。
 *
 * 背景：用户在编号框输入带 F 前缀（F25 / F25X）时，类型字段不自动跳到 F5
 * （旧逻辑只对纯数字走 numberToType，parseF5Variant 对 "F25" 的 num 段是 "F25"、
 * parseInt → NaN，pn>0 分支跳过）。修法 = 抽 parseTallyTypeNumber：剥前导 F +
 * 剥 X/Y/Z 后缀 → 按个位数映射类型，handleNumberChange / parseF5Variant 共用。
 * 以下用例 pin 映射与无效兜底，不删弱既有。
 */

describe("parseTallyTypeNumber（编号 → 类型 + 编号）", () => {
  it.each([
    ["25", "F5", "25"],
    ["F25", "F5", "25"],
    ["25X", "F5", "25"],
    ["F25X", "F5", "25"],
    ["5", "F5", "5"],
    ["F5", "F5", "5"],
  ])("F 前缀/X/Y/Z 后缀：%s → 类型 %s、编号 %s", (raw, type, num) => {
    expect(parseTallyTypeNumber(raw)).toEqual({ type, number: num });
  });

  it("按个位数映射其它计数类型（1/2/4/6/7/8）", () => {
    expect(parseTallyTypeNumber("1")).toEqual({ type: "F1", number: "1" });
    expect(parseTallyTypeNumber("12")).toEqual({ type: "F2", number: "12" });
    expect(parseTallyTypeNumber("24")).toEqual({ type: "F4", number: "24" });
    expect(parseTallyTypeNumber("6")).toEqual({ type: "F6", number: "6" });
    expect(parseTallyTypeNumber("17")).toEqual({ type: "F7", number: "17" });
    expect(parseTallyTypeNumber("8")).toEqual({ type: "F8", number: "8" });
    expect(parseTallyTypeNumber("F4")).toEqual({ type: "F4", number: "4" });
  });

  it("无效输入兜底：类型 null、编号原样返回（不改类型）", () => {
    expect(parseTallyTypeNumber("")).toEqual({ type: null, number: "" });
    expect(parseTallyTypeNumber("abc")).toEqual({ type: null, number: "abc" });
    expect(parseTallyTypeNumber("F")).toEqual({ type: null, number: "F" });
    expect(parseTallyTypeNumber("0")).toEqual({ type: null, number: "0" });
    expect(parseTallyTypeNumber("F5IC123")).toEqual({ type: null, number: "F5IC123" });
  });
});

describe("parseF5Variant（F5 成像变体，保留既有语义）", () => {
  it("成像前缀 IC/IR/IP：编号段取前缀后剩余", () => {
    expect(parseF5Variant("IC123")).toEqual({ num: "123", label: "FIC123" });
  });

  it("普通 F5 编号 / 环形后缀：走通用解析命中 F5", () => {
    expect(parseF5Variant("5")).toEqual({ num: "5", label: "F5" });
    expect(parseF5Variant("25X")).toEqual({ num: "25", label: "F5" });
    expect(parseF5Variant("F25")).toEqual({ num: "25", label: "F5" });
  });
});
