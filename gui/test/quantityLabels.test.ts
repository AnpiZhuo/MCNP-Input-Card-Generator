/**
 * quantityLabels — 图片里"量名称 / 量符号 / 单位"的格式锁（GB 3100~3102 口径）。
 *
 * 锁的不是"某张图长什么样"，而是**若干条排版规则**：
 *  - 轴标必须同时含量名称、量符号、单位（只写单位不合规）；
 *  - 单位里的幂用 Unicode 上标（canvas 不解析 `<sup>`，这是唯一画得对的写法）；
 *  - 复杂单位把负指数放进括号、括号外只有一个斜线（`cm⁻²·MeV⁻¹`，不是 `cm-2/MeV`）；
 *  - 带单位的数值**数值与单位间留一空格**，但 `%` 与 `°` 不留。
 */
import { describe, it, expect } from "vitest";
import { QUANTITIES, axisLabel, superscriptUnit, withUnit } from "../src/export/quantityLabels";

describe("superscriptUnit（单位幂 → Unicode 上标）", () => {
  it("cm-2 → cm⁻²", () => {
    expect(superscriptUnit("cm-2")).toBe("cm⁻²");
  });

  it("多段与多位指数都对", () => {
    expect(superscriptUnit("cm-2·s-1")).toBe("cm⁻²·s⁻¹");
    expect(superscriptUnit("m-10")).toBe("m⁻¹⁰");
  });

  it("没有幂的单位原样返回", () => {
    expect(superscriptUnit("MeV")).toBe("MeV");
    expect(superscriptUnit("mm")).toBe("mm");
    expect(superscriptUnit("归一化计数")).toBe("归一化计数");
  });
});

describe("axisLabel（量名称 量符号/单位）", () => {
  it("长度：长度 L/cm（MCNP 长度单位是 cm）", () => {
    expect(axisLabel("length")).toBe("长度 L/cm");
  });

  it("复合单位加括号，且**只有一个斜线**", () => {
    expect(axisLabel("fluxPerEnergy")).toBe("通量密度 φ/(cm⁻²·MeV⁻¹)");
    const s = axisLabel("fluxPerEnergy");
    expect((s.match(/\//g) || []).length).toBe(1);
  });

  it("带幂的单因子单位也加括号（避免'斜线接幂'的坏写法）", () => {
    expect(axisLabel("cellFlux")).toBe("体通量 Φ/(cm⁻²)");
  });

  it("不带幂的简单单位不加括号", () => {
    expect(axisLabel({ name: "长度", symbol: "x", unit: "mm" })).toBe("长度 x/mm");
    expect(axisLabel("energy")).toBe("能量 E/MeV");
  });

  it("无量纲量（keff）只到量符号", () => {
    expect(axisLabel("keff")).toBe("有效增殖因子 k");
  });

  it("可以直接传自定义量（不查表）", () => {
    expect(axisLabel({ name: "密度", symbol: "ρ", unit: "g·cm-3" })).toBe("密度 ρ/(g·cm⁻³)");
  });

  it("字典里每条都能排出非空轴标", () => {
    for (const k of Object.keys(QUANTITIES) as (keyof typeof QUANTITIES)[]) {
      const s = axisLabel(k);
      expect(s.length).toBeGreaterThan(0);
      expect(s).toContain(QUANTITIES[k].name);
      expect(s).toContain(QUANTITIES[k].symbol);
    }
  });
});

describe("withUnit（数值与单位之间留空格）", () => {
  it("普通单位留空格", () => {
    expect(withUnit("12.3", "MeV")).toBe("12.3 MeV");
  });

  it("百分号与角度符号不留空格", () => {
    expect(withUnit("5", "%")).toBe("5%");
    expect(withUnit("30", "°")).toBe("30°");
  });

  it("空单位只有数值", () => {
    expect(withUnit("1.004", "")).toBe("1.004");
  });
});
