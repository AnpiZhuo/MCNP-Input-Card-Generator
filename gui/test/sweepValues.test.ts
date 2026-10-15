/**
 * sweepValues 回归：取值框里怎么把一行字切成「取值」。
 *
 * 口径（2026-10-11 用户确认）：
 *   · **空格（含逗号/制表符/换行）仍是取值分隔符** —— `1000 5000` 是 2 个取值；
 *   · **含空格的内容用引号包起来** —— `"n p"` 是 **1** 个取值（内容原样，含那个空格）；
 *   · 引号里的内容**逐字保留**（不做数字归一化：`"1e5"` 就是 `1e5`，不是 `100000`）；
 *   · 引号没配对 ⇒ 明确报错（非静默），不猜。
 *
 * 为什么需要它：文本级替换要求"我填什么就换成什么"，而空格在取值框里是分隔符
 * ⇒ 想替换成 `n p` / `1 0 -1` 这类含空格的内容，必须有个说法。
 */
import { describe, expect, it } from "vitest";
import { parseValues } from "../src/utils/sweepValues";

describe("parseValues — 空格分隔取值，含空格的用引号", () => {
  it("空格分隔：多个取值（保持既有行为）", () => {
    expect(parseValues("1000 5000").values).toEqual([1000, 5000]);
    expect(parseValues("1000000 1e7 2e7").values).toEqual([1000000, 10000000, 20000000]);
  });

  it("单个取值", () => {
    expect(parseValues("7").values).toEqual([7]);
  });

  it("逗号（半角/全角）也是分隔符", () => {
    expect(parseValues("1,2，3").values).toEqual([1, 2, 3]);
  });

  it("引号里的空格是内容，不是分隔符", () => {
    expect(parseValues('"n p"').values).toEqual(["n p"]);
    expect(parseValues('"1 0 -1"').values).toEqual(["1 0 -1"]);
  });

  it("引号里的逗号也是内容", () => {
    expect(parseValues('"a,b"').values).toEqual(["a,b"]);
  });

  it("全角引号同样认", () => {
    expect(parseValues("“n p”").values).toEqual(["n p"]);
  });

  it("引号内容逐字保留（不做数字归一化）", () => {
    expect(parseValues('"1e5"').values).toEqual(["1e5"]);
    expect(parseValues('"0.50"').values).toEqual(["0.50"]);
  });

  it("引号与外层取值混用", () => {
    expect(parseValues('1000 "n p" 2000').values).toEqual([1000, "n p", 2000]);
  });

  it("空串 → 没有取值，不算错", () => {
    expect(parseValues("")).toEqual({ values: [], error: null });
    expect(parseValues("   ")).toEqual({ values: [], error: null });
  });

  it("引号没配对 → 报错并且不给取值（不猜、不静默）", () => {
    const r = parseValues('1000 "n p');
    expect(r.values).toEqual([]);
    expect(r.error).toContain("引号");
  });

  it("空引号（\"\"）不产出取值（不支持'替换为空'）", () => {
    expect(parseValues('""').values).toEqual([]);
  });
});
