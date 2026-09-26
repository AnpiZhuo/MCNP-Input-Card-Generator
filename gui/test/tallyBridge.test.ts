import { describe, it, expect } from "vitest";
import { deckTalliesToRows, rowsToDeckTallies, splitTallyNumber, type TallyRow } from "../src/utils/tallyBridge";

/*
 * tallyBridge —— 计数卡行桥接纯函数（TallyTab ↔ deck.tallies）。
 *
 * 用户报告（2026-09-26）：「* 号解析时无法传入，自己点选后生成时也没有」。
 * 根因是本地行与 deck 定义之间的映射漏了 `fn_prefix` / `number_suffix`
 * （组件内部闭包里的两处 map，没有任何测试看得见）。本文件把映射抽成纯函数并锁住。
 */

const row = (over: Partial<TallyRow> = {}): TallyRow => ({
  id: 1, prefix: "", type: "F4", number: "4", suffix: "",
  particle: "n", params: "1", multiplier: "",
  enableEn: false, enableTn: false, ...over,
});

/** 后端 `_deck_to_frontend_dict` 的真实回显口径 */
const deckTally = (over: Record<string, unknown> = {}) => ({
  type: "F4", number: 4, particle: "n", params: "1",
  enableEn: false, enableTn: false, multiplier: "",
  fn_prefix: "", number_suffix: "", ...over,
});

describe("deckTalliesToRows（后端回显 → 本地行）", () => {
  it("带上 fn_prefix 与 number_suffix（旧实现在这里硬编码 prefix: \"\"）", () => {
    const [r] = deckTalliesToRows([deckTally({ fn_prefix: "*", number_suffix: "" })]);
    expect(r.prefix).toBe("*");
    expect(r.suffix).toBe("");
    expect(r.type).toBe("F4");
  });

  it("F5X 环探测器的轴字母带出来", () => {
    const [r] = deckTalliesToRows([deckTally({ type: "F5", number: 5, number_suffix: "X" })]);
    expect(r.suffix).toBe("X");
  });

  it("容忍 camelCase 与缺键（外部接入/旧数据）", () => {
    const [a] = deckTalliesToRows([{ type: "F4", number: 4, fnPrefix: "+", numberSuffix: "y" } as any]);
    expect(a.prefix).toBe("+");
    expect(a.suffix).toBe("y");
    const [b] = deckTalliesToRows([{ type: "F6", number: 6 } as any]);
    expect(b).toMatchObject({ prefix: "", suffix: "", particle: "n", params: "" });
  });

  it("空输入不炸", () => {
    expect(deckTalliesToRows(undefined)).toEqual([]);
    expect(deckTalliesToRows([])).toEqual([]);
  });
});

describe("rowsToDeckTallies（本地行 → 生成载荷）", () => {
  it("把下拉框选的前缀写进 fn_prefix（旧实现在这里整个丢掉）", () => {
    const [d] = rowsToDeckTallies([row({ prefix: "*" })]);
    expect(d.fn_prefix).toBe("*");
    expect(d.number_suffix).toBe("");
  });

  it("成像前缀 FIC 原样透传", () => {
    const [d] = rowsToDeckTallies([row({ prefix: "FIC", type: "F5", number: "5" })]);
    expect(d.fn_prefix).toBe("FIC");
  });

  it("编号非法时回落到 0（保持既有行为，不产生 NaN）", () => {
    const [d] = rowsToDeckTallies([row({ number: "" })]);
    expect(d.number).toBe(0);
  });
});

describe("往返不变量（useDeckSynced 判等价靠它）", () => {
  it.each([
    ["无前缀 F4", deckTally()],
    ["*F4", deckTally({ fn_prefix: "*" })],
    ["+F8", deckTally({ type: "F8", number: 8, fn_prefix: "+" })],
    ["F5X", deckTally({ type: "F5", number: 5, number_suffix: "X" })],
    ["FIC5", deckTally({ type: "F5", number: 5, fn_prefix: "FIC" })],
  ])("%s：deck → 行 → deck 逐字段不变", (_name, t) => {
    const [back] = rowsToDeckTallies(deckTalliesToRows([t]) as TallyRow[]);
    expect(back).toEqual(t);
  });
});

describe("splitTallyNumber（编号框里的 X/Y/Z 后缀）", () => {
  it.each([
    ["25", { number: "25", suffix: "" }],
    ["25X", { number: "25", suffix: "X" }],
    ["F25X", { number: "25", suffix: "X" }],
    ["25y", { number: "25", suffix: "Y" }],
    ["5", { number: "5", suffix: "" }],
    ["", { number: "", suffix: "" }],
    ["abc", { number: "abc", suffix: "" }],
  ])("%s → %o", (raw, expected) => {
    expect(splitTallyNumber(raw)).toEqual(expected);
  });
});
