/**
 * PNNL 精选材料数据契约：
 * - 现有预设 + PNNL 精选合计 ≤ 100 种（用户要求）；
 * - PNNL 精选条目必须带同位素级 rows（ZAID + 负质量份额），直接填手动 ZAID 模式；
 * - density 为负（MCNP 质量密度 g/cm³）；key 全局唯一。
 */
import { describe, expect, it } from "vitest";
import { PRESET_CATEGORIES } from "../src/components/MaterialPresets";
import { PNNL_CATEGORIES } from "../src/data/pnnlPresets";

describe("pnnlPresets 精选数据", () => {
  it("现有 + PNNL 合计 ≤ 100 种", () => {
    const total = PRESET_CATEGORIES.flatMap(([, items]) => items).length;
    expect(total).toBeLessThanOrEqual(100);
    expect(total).toBeGreaterThan(90);
  });

  it("PNNL 条目均有 rows、density 为负、份额为负、ZAID 为纯数字", () => {
    const items = PNNL_CATEGORIES.flatMap(([, list]) => list);
    expect(items.length).toBeGreaterThan(40);
    for (const it of items) {
      expect(it.rows.length, `${it.key} 无 rows`).toBeGreaterThan(0);
      expect(it.density, `${it.key} 密度缺失`).toBeTruthy();
      expect(it.density![0]).toBe("-");
      for (const [zaid, fraction] of it.rows) {
        expect(zaid, `${it.key} ZAID 非数字`).toMatch(/^\d+$/);
        expect(Number(fraction), `${it.key} ${zaid} 份额应<0`).toBeLessThan(0);
      }
    }
  });

  it("全局 key 无重复", () => {
    const keys = PRESET_CATEGORIES.flatMap(([, items]) => items.map(i => i.key));
    expect(new Set(keys).size).toBe(keys.length);
  });
});
