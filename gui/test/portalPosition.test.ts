import { describe, it, expect } from "vitest";
import { clampDropdownLeft } from "../src/components/GeometryTab";

/*
 * 材料下拉 portal 右缘防溢出（GeometryTab.tsx 材料选择器）—— 纯函数定位计算。
 *
 * 契约（PM 定稿）：clampDropdownLeft(x, viewportWidth, dropdownWidth = 200)
 *   => Math.min(x, viewportWidth - dropdownWidth - 20)
 * 对齐现内联表达式 `left: Math.min(matPicker.x, (window.innerWidth || 0) - 220)`
 * （width 200 + 20px 右缘边距）。
 *
 * 行为：x 在视口内原样返回；x 超出右缘（viewportWidth - dropdownWidth - 20）
 * 时被 clamp，保证下拉右缘不越出视口（留 20px 边距）。
 */
describe("clampDropdownLeft", () => {
  it("x 在视口内时原样返回（不 clamp）", () => {
    expect(clampDropdownLeft(100, 1200)).toBe(100);
    expect(clampDropdownLeft(0, 1200)).toBe(0);
    expect(clampDropdownLeft(979, 1200)).toBe(979); // 恰在 clamp 边界内
  });

  it("x 超出右缘时被 clamp 到 viewportWidth - dropdownWidth - 20", () => {
    // 1500 超右缘 → 980；右缘 = 980 + 200 = 1180 ≤ 1200（留 20px 边距）
    expect(clampDropdownLeft(1500, 1200)).toBe(980);
    expect(clampDropdownLeft(10000, 800)).toBe(800 - 200 - 20);
  });

  it("x 恰在 clamp 边界时原样返回（Math.min 边界语义）", () => {
    expect(clampDropdownLeft(980, 1200)).toBe(980);
    expect(clampDropdownLeft(981, 1200)).toBe(980); // 超 1 → clamp
  });

  it("viewportWidth=0 时 Math.min 自然兜底（pin 既有语义）", () => {
    // 现内联表达式 `(window.innerWidth || 0) - 220`：viewportWidth=0 → -220，
    // Math.min(x, -220) = -220。pin 当前行为（负 left 是潜在边界，见汇报）。
    expect(clampDropdownLeft(100, 0)).toBe(-220);
  });

  it("自定义 dropdownWidth 参与 clamp（右侧预算随之变化）", () => {
    expect(clampDropdownLeft(1500, 1200, 300)).toBe(1200 - 300 - 20); // 880
    expect(clampDropdownLeft(1500, 1200, 100)).toBe(1200 - 100 - 20); // 1080
  });

  it("单调性：x 从 0 扫到 2 倍视口，结果不超 viewportWidth - 220", () => {
    const viewport = 1200;
    const cap = viewport - 200 - 20;
    let prev = -1;
    for (let x = 0; x <= 2400; x += 7) {
      const v = clampDropdownLeft(x, viewport);
      expect(v).toBeLessThanOrEqual(cap);
      expect(v).toBeGreaterThanOrEqual(prev); // 非递减
      prev = v;
    }
    // 到达右缘后不再增长
    expect(clampDropdownLeft(2000, viewport)).toBe(cap);
  });
});
