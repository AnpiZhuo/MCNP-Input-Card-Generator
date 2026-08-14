import { describe, it, expect } from "vitest";
import { splitZaid, buildZaid, resolveZaid } from "../src/components/MaterialEditDialog";

/*
 * 材料编辑对话框核素 元素/质量数 拆组（MaterialEditDialog.tsx）—— 纯函数。
 *
 * 背景：Bug 2（用户报"Fe57 改不动/删 Fe 删掉 7"）。导入 INP 的核素是数值 ZAID
 * （如 26057），旧代码两个受控输入框的 value 都从 nu.zaid 派生、onChange 又用
 * `nu.zaid.split("-")` 重建 —— 数值串 split("-") 把整个 "26057" 当"元素"、
 * mass 段丢失 → 改 57 变 2605、删 Fe 连 57 一起没了。
 *
 * 修法：抽 splitZaid/buildZaid/resolveZaid 纯函数，输入框持有本地草稿、失焦提交
 * 时再回写。以下用例 pin 拆组/组装/往返稳定，杜绝派生回写丢失。
 */

describe("splitZaid（ZAID → {el, mass}）", () => {
  it("数值 ZAID（导入/展开形态）：26057 → Fe/57", () => {
    expect(splitZaid("26057")).toEqual({ el: "Fe", mass: "57" });
    expect(splitZaid("92235")).toEqual({ el: "U", mass: "235" });
    expect(splitZaid("1001")).toEqual({ el: "H", mass: "1" });
  });

  it("带库后缀的数值 ZAID：26057.50c → Fe/57", () => {
    expect(splitZaid("26057.50c")).toEqual({ el: "Fe", mass: "57" });
    expect(splitZaid("92235.80c")).toEqual({ el: "U", mass: "235" });
  });

  it("自然元素（质量位 AAA=000）→ 质量数为空串", () => {
    expect(splitZaid("6000")).toEqual({ el: "C", mass: "" });
    expect(splitZaid("26000")).toEqual({ el: "Fe", mass: "" });
  });

  it("手写 '元素-质量数' 形态：Fe-57 → Fe/57", () => {
    expect(splitZaid("Fe-57")).toEqual({ el: "Fe", mass: "57" });
    expect(splitZaid("Fe-57.50c")).toEqual({ el: "Fe", mass: "57" });
  });

  it("空串/无内容 → 空草稿", () => {
    expect(splitZaid("")).toEqual({ el: "", mass: "" });
  });
});

describe("buildZaid（{el, mass} → ZAID）", () => {
  it("合法元素符号 + 质量数 → 质子数补三位质量数", () => {
    expect(buildZaid("Fe", "57")).toBe("26057");
    expect(buildZaid("U", "235")).toBe("92235");
    expect(buildZaid("H", "1")).toBe("1001");
    expect(buildZaid("Fe", "56")).toBe("26056");
  });

  it("质量数为空 → 自然元素（000 补位）", () => {
    expect(buildZaid("C", "")).toBe("6000");
    expect(buildZaid("Fe", "")).toBe("26000");
  });

  it("数字元素（如 92）原样作质子数（对齐旧 elToZaid 语义）", () => {
    expect(buildZaid("92", "235")).toBe("92235");
    expect(buildZaid("26", "57")).toBe("26057");
  });

  it("非法元素符号 → 0 兜底（对齐旧 elToZaid 语义）", () => {
    expect(buildZaid("Zz", "57")).toBe("0057");
  });
});

describe("往返稳定（splitZaid ∘ buildZaid 恒等）", () => {
  const stable: Array<[string, string]> = [
    ["26057", "26057"],   // Fe-57
    ["92235", "92235"],   // U-235
    ["1001", "1001"],     // H-1
    ["6000", "6000"],     // 自然 C
    ["26000", "26000"],   // 自然 Fe
    ["8016", "8016"],     // O-16
    ["28058", "28058"],   // Ni-58
  ];
  it.each(stable)("对 %s 拆后再组不漂移", (src, want) => {
    const p = splitZaid(src);
    expect(buildZaid(p.el, p.mass)).toBe(want);
  });
});

describe("Bug 2 回归：编辑一个字段不丢另一个（组合语义 = commitRow 做的运算）", () => {
  it("改质量数：26057 的 mass 57 → 56，元素段保持 Fe", () => {
    const p = splitZaid("26057");                 // {el:"Fe", mass:"57"}
    expect(buildZaid(p.el, "56")).toBe("26056");  // 元素 Fe 不变，仅质量数改 56
    expect(p.mass).toBe("57");                    // 拆组不丢质量数
  });

  it("改元素：26057 的 el Fe → U，质量段保持 57", () => {
    const p = splitZaid("26057");
    expect(buildZaid("U", p.mass)).toBe("92057"); // U-57：质量 57 不被"删掉"
  });

  it("删元素字段（Fe→F）不把质量数一起清掉", () => {
    const p = splitZaid("26057");                 // 用户删掉 e → el 变 "F"
    expect(p.mass).toBe("57");                    // mass 草稿独立，不受元素编辑影响
  });
});

describe("resolveZaid（草稿 → ZAID，元素为空不提交）", () => {
  it("元素 + 质量数有效 → 数值 ZAID", () => {
    expect(resolveZaid({ el: "Fe", mass: "57" })).toBe("26057");
    expect(resolveZaid({ el: "Fe", mass: "" })).toBe("26000");
  });

  it("元素为空 → null（保留草稿继续编辑，不写回）", () => {
    expect(resolveZaid({ el: "", mass: "57" })).toBeNull();
    expect(resolveZaid({ el: "  ", mass: "" })).toBeNull();
  });

  it("空白质量数按自然元素处理", () => {
    expect(resolveZaid({ el: " C ", mass: "  " })).toBe("6000");
  });
});
