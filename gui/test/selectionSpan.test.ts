/**
 * selectionSpan 回归：把「鼠标划中的那几个字符」换算成要删掉的字符区间。
 *
 * 这是参数扫描「文本级替换」的**定位权威** —— 后端只认这里算出的 start/end
 * （用例覆盖旧缺陷：同一个字出现两次时改错地方）。
 */
import { describe, expect, it } from "vitest";
import { selectionSpan } from "../src/utils/selectionSpan";

const TEXT = "SO 1 2323255 6\nNPS 1000\n";

describe("selectionSpan — 只删划中的那几个字符", () => {
  it("只划数字中间的一个字符：区间就是那一个字符", () => {
    const s = selectionSpan(TEXT, 11, 12)!;      // "2323255" 里第二个 5
    expect(s.anchor).toBe("5");
    expect(s.start).toBe(11);
    expect(s.end).toBe(12);
    expect(TEXT.slice(s.start, s.end)).toBe("5");
  });

  it("划中两个字符：区间就是那两个字符", () => {
    const s = selectionSpan(TEXT, 10, 12)!;      // "55"
    expect(s.anchor).toBe("55");
    expect(TEXT.slice(s.start, s.end)).toBe("55");
  });

  it("划中整个数：区间是整个数", () => {
    const s = selectionSpan(TEXT, 5, 12)!;       // "2323255"
    expect(s.anchor).toBe("2323255");
    expect(TEXT.slice(s.start, s.end)).toBe("2323255");
  });

  it("选区两端多带了空白 → 收窄到真实内容（保证 slice === anchor）", () => {
    const s = selectionSpan(TEXT, 10, 13)!;      // 实际是 "55 "
    expect(s.anchor).toBe("55");
    expect(TEXT.slice(s.start, s.end)).toBe("55");
  });

  it("不变式：任何合法选区都必须满足 content.slice(start,end) === anchor", () => {
    for (let a = 0; a < TEXT.length; a++) {
      for (let b = a + 1; b <= TEXT.length; b++) {
        const s = selectionSpan(TEXT, a, b);
        if (s) expect(TEXT.slice(s.start, s.end)).toBe(s.anchor);
      }
    }
  });

  it("跨行选区 / 空选区 / 越界 → null（调用方给提示，不做替换）", () => {
    expect(selectionSpan(TEXT, 0, TEXT.length)).toBeNull();   // 跨行
    expect(selectionSpan(TEXT, 5, 5)).toBeNull();             // 空
    expect(selectionSpan(TEXT, 4, 5)).toBeNull();             // 只有空白 " "（TEXT[4] 是空格）
    expect(selectionSpan(TEXT, -1, 5)).toBeNull();            // 越界
    expect(selectionSpan(TEXT, 5, TEXT.length + 10)).toBeNull();
  });

  it("反向选区（从右往左划）与正向等价", () => {
    expect(selectionSpan(TEXT, 12, 10)).toEqual(selectionSpan(TEXT, 10, 12));
  });
});
