import { describe, it, expect } from "vitest";
import {
  emptyFmeshRow,
  validateFmeshRow,
  vectorsParallel,
  normalizeGeom,
  isCylGeom,
  gridCellCount,
  parseNumberList,
  type FmeshRow,
} from "../../src/volume/fmeshState";

/**
 * FMESH 表单校验纯函数（契约：PM 指令 2026-08-14 第 8 项）。
 * 校验逻辑抽为可测纯函数 validateFmeshRow / vectorsParallel，供表单提交/卡体生成前友好提示。
 */
function row(partial: Partial<FmeshRow>): FmeshRow {
  return { ...emptyFmeshRow(), ...partial };
}

const clean = row({
  geom: "XYZ",
  origin: "0 0 0",
  imesh: "10 20", iints: "2 2",
  jmesh: "10", jints: "2",
  kmesh: "10", kints: "2",
});

describe("normalizeGeom / isCylGeom（GEOM 单 token 连写）", () => {
  it("归一化为大写单 token，空值默认 XYZ", () => {
    expect(normalizeGeom("xyz")).toBe("XYZ");
    expect(normalizeGeom("CYL")).toBe("CYL");
    expect(normalizeGeom("rzt")).toBe("RZT");
    expect(normalizeGeom("")).toBe("XYZ");
  });

  it("cyl 系识别：CYL/RZT 是，XYZ/REC 否", () => {
    expect(isCylGeom("CYL")).toBe(true);
    expect(isCylGeom("rzt")).toBe(true);
    expect(isCylGeom("XYZ")).toBe(false);
    expect(isCylGeom("REC")).toBe(false);
  });
});

describe("validateFmeshRow · 正整数规则（iints/jints/kints/emints/tmints）", () => {
  it("合法正整数不报错", () => {
    expect(validateFmeshRow(clean)).toEqual([]);
  });

  it("0 / 负数 / 小数 / 非数值都报错", () => {
    for (const [f, label] of [["iints", "IINTS"], ["jints", "JINTS"], ["kints", "KINTS"], ["emints", "EMINTS"], ["tmints", "TMINTS"]] as [string, string][]) {
      const bad = row({ ...clean, [f]: "0" } as any);
      const issues = validateFmeshRow(bad);
      expect(issues.some((i) => i.field === label && i.level === "error")).toBe(true);

      const neg = row({ ...clean, [f]: "-1" } as any);
      expect(validateFmeshRow(neg).some((i) => i.field === label)).toBe(true);

      const dec = row({ ...clean, [f]: "2.5" } as any);
      expect(validateFmeshRow(dec).some((i) => i.field === label)).toBe(true);

      const non = row({ ...clean, [f]: "abc" } as any);
      expect(validateFmeshRow(non).some((i) => i.field === label)).toBe(true);
    }
  });

  it("多值区间数每个都须为正整数", () => {
    const issues = validateFmeshRow(row({ ...clean, iints: "2 0" }));
    expect(issues.some((i) => i.field === "IINTS")).toBe(true);
  });
});

describe("validateFmeshRow · *ints 条目数与 *mesh 条目数匹配", () => {
  it("匹配时不报错（IMESH=10 20 IINTS=2 2）", () => {
    expect(validateFmeshRow(clean).filter((i) => i.field === "IINTS")).toEqual([]);
  });

  it("条目数不等报错（IMESH=10 20 IINTS=2）", () => {
    const issues = validateFmeshRow(row({ ...clean, iints: "2" }));
    const hit = issues.find((i) => i.field === "IINTS");
    expect(hit).toBeTruthy();
    expect(hit!.level).toBe("error");
    expect(hit!.message).toContain("不匹配");
  });

  it("只有 ints 缺 mesh 报错，只有 mesh 缺 ints 报错", () => {
    expect(validateFmeshRow(row({ ...clean, imesh: "" })).some((i) => i.field === "IINTS")).toBe(true);
    expect(validateFmeshRow(row({ ...clean, iints: "" })).some((i) => i.field === "IMESH")).toBe(true);
  });

  it("能量/时间对同样校验（EMESH vs EMINTS）", () => {
    const issues = validateFmeshRow(row({ ...clean, emesh: "1e-6 1 14", emints: "2" }));
    expect(issues.some((i) => i.field === "EMINTS" && i.message.includes("不匹配"))).toBe(true);
  });
});

describe("validateFmeshRow · 网格/能量值单调递增 + 从 ORIGIN 起", () => {
  it("单调递增合法（含科学计数法能量）", () => {
    const r = row({ ...clean, emesh: "1e-6 1 14", emints: "2 2" });
    expect(validateFmeshRow(r).filter((i) => i.field === "EMESH")).toEqual([]);
  });

  it("mesh 列表非递增报错", () => {
    const issues = validateFmeshRow(row({ ...clean, imesh: "10 5" }));
    expect(issues.some((i) => i.field === "IMESH" && i.message.includes("单调递增"))).toBe(true);
    const e = validateFmeshRow(row({ ...clean, emesh: "14 1", emints: "1" }));
    expect(e.some((i) => i.field === "EMESH")).toBe(true);
  });

  it("直角系从 ORIGIN 起：首值须大于 ORIGIN 坐标", () => {
    // ORIGIN x=0，IMESH=-10 → 报错
    const issues = validateFmeshRow(row({ origin: "0 0 0", imesh: "-10", iints: "2", jmesh: "10", jints: "2", kmesh: "10", kints: "2" }));
    expect(issues.some((i) => i.field === "IMESH")).toBe(true);
    // ORIGIN z=-150，KMESH=-50 → 合法（-50 > -150）
    const ok = validateFmeshRow(row({ origin: "-100 -100 -150", imesh: "100", iints: "10", jmesh: "100", jints: "10", kmesh: "-50", kints: "100" }));
    expect(ok.filter((i) => i.field === "KMESH")).toEqual([]);
  });
});

describe("validateFmeshRow · 圆柱系 kmesh 末值须为 1", () => {
  it("geom=CYL kmesh 末值 1 合法；末值非 1 报错", () => {
    // kmesh "0.5 1"（2 条目）须配 kints "2 2"，否则命中条目数匹配规则
    expect(validateFmeshRow(row({ ...clean, geom: "CYL", kmesh: "0.5 1", kints: "2 2" }))).toEqual([]);
    const issues = validateFmeshRow(row({ ...clean, geom: "CYL", kmesh: "0.5", kints: "10" }));
    expect(issues.some((i) => i.field === "KMESH" && i.message.includes("1"))).toBe(true);
  });

  it("RZT 同样适用", () => {
    const issues = validateFmeshRow(row({ ...clean, geom: "RZT", kmesh: "0.25", kints: "10" }));
    expect(issues.some((i) => i.field === "KMESH")).toBe(true);
  });

  it("直角系不受此规则约束", () => {
    expect(validateFmeshRow(row({ ...clean, geom: "XYZ", kmesh: "5", kints: "10" }))).toEqual([]);
  });
});

describe("vectorsParallel（AXS/VEC 平行检测）", () => {
  it("平行 / 反平行 → true", () => {
    expect(vectorsParallel("0 0 1", "0 0 2")).toBe(true);
    expect(vectorsParallel("1 0 0", "-1 0 0")).toBe(true);
  });

  it("不平行 → false", () => {
    expect(vectorsParallel("0 0 1", "0 1 0")).toBe(false);
    expect(vectorsParallel("1 0 0", "1 1 0")).toBe(false);
  });

  it("零向量退化 / 非法输入 → false（不误判）", () => {
    expect(vectorsParallel("0 0 0", "1 0 0")).toBe(false);
    expect(vectorsParallel("1 2 3", "abc def ghi")).toBe(false);
    expect(vectorsParallel("0 0 1", "")).toBe(false);
  });

  it("validateFmeshRow：cyl 系 AXS∥VEC 报错，直角系不查", () => {
    const p = validateFmeshRow(row({ ...clean, geom: "CYL", kmesh: "1", kints: "10", axs: "0 0 1", vec: "0 0 2" }));
    expect(p.some((i) => i.field === "AXS" && i.message.includes("平行"))).toBe(true);
    const n = validateFmeshRow(row({ ...clean, geom: "CYL", kmesh: "1", kints: "10", axs: "0 0 1", vec: "1 0 0" }));
    expect(n.filter((i) => i.field === "AXS")).toEqual([]);
    const c = validateFmeshRow(row({ ...clean, axs: "0 0 1", vec: "0 0 2" }));
    expect(c.filter((i) => i.field === "AXS")).toEqual([]);
  });
});

describe("validateFmeshRow · TR 变换编号", () => {
  it("正整数合法，负数/小数/非数值报错", () => {
    expect(validateFmeshRow(row({ ...clean, tr: "3" })).filter((i) => i.field === "TR")).toEqual([]);
    for (const bad of ["-1", "1.5", "abc", "TR3"]) {
      expect(validateFmeshRow(row({ ...clean, tr: bad })).some((i) => i.field === "TR")).toBe(true);
    }
  });
});

describe("gridCellCount / 大网格内存警告", () => {
  it("三方向区间总数乘积（200³ = 8e6）", () => {
    expect(gridCellCount(row({ iints: "200", jints: "200", kints: "200" }))).toBe(8_000_000);
    // iints "2 2" 求和 = 4，4×2×2 = 16
    expect(gridCellCount(row({ iints: "2 2", jints: "2", kints: "2" }))).toBe(16);
  });

  it("非数值 → null（不误报）", () => {
    expect(gridCellCount(row({ iints: "abc", jints: "2", kints: "2" }))).toBeNull();
  });

  it("超过 128³ 阈值给 warning，等于阈值不报", () => {
    const over = validateFmeshRow(row({ iints: "200", jints: "200", kints: "200" }));
    expect(over.some((i) => i.level === "warning" && i.message.includes("网格规模"))).toBe(true);
    const exact = validateFmeshRow(row({ iints: "128", jints: "128", kints: "128" }));
    expect(exact.some((i) => i.level === "warning")).toBe(false);
  });
});

describe("parseNumberList（数值列表解析）", () => {
  it("科学计数法与多值", () => {
    expect(parseNumberList("1e-6 1 14")).toEqual([1e-6, 1, 14]);
    expect(parseNumberList("-50 0.5")).toEqual([-50, 0.5]);
    expect(parseNumberList("")).toEqual([]);
    expect(parseNumberList("10 abc")).toBeNull();
  });
});
