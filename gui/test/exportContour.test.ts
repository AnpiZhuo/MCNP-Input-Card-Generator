// @vitest-environment jsdom
/**
 * 等值线（marching squares）单测。
 *
 * 锁的是**几何正确性**，不是实现细节：
 * - 线性场上的等值线必须落在解析解上（45° 对角线，位置精确）；
 * - 等值线必须落在数值区间内（不能跑到 cell 外）；
 * - 线段必须串成连续折线（端到端相接），而不是一堆碎片；
 * - 输出 SVG 的路径点数远小于逐体素矩形数（这正是换算法的理由）。
 */
import { describe, it, expect } from "vitest";
import { fieldFromArray, contourSegments, joinSegments, contourSvgPath } from "../src/export/contour";

/** 线性场 f = col（0..w-1），等值线 level 必为竖直直线 col = level */
function linearField(w: number, h: number) {
  const data = new Float64Array(w * h);
  for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) data[r * w + c] = c;
  return fieldFromArray(data, w, h);
}

describe("contourSegments", () => {
  it("线性场：等值线落在解析位置（col = level）", () => {
    const f = linearField(10, 5);
    const segs = contourSegments(f, 3.5);
    expect(segs.length).toBeGreaterThan(0);
    for (const [x1, y1, x2, y2] of segs) {
      expect(x1).toBeCloseTo(3.5, 6);
      expect(x2).toBeCloseTo(3.5, 6);
      expect(y1).toBeGreaterThanOrEqual(0);
      expect(y2).toBeLessThanOrEqual(4);
    }
  });

  it("全部低于等值面 → 无线段；全部高于 → 无线段（不产生噪声）", () => {
    const f = linearField(8, 8);
    expect(contourSegments(f, -1)).toEqual([]);
    expect(contourSegments(f, 100)).toEqual([]);
  });

  it("等值线坐标恒落在网格范围内（不越界）", () => {
    const w = 6, h = 4;
    const data = new Float64Array(w * h);
    for (let i = 0; i < data.length; i++) data[i] = Math.sin(i * 0.7) * 5 + 5;
    const f = fieldFromArray(data, w, h);
    for (const level of [1, 3, 5, 7]) {
      for (const [x1, y1, x2, y2] of contourSegments(f, level)) {
        for (const [x, y] of [[x1, y1], [x2, y2]] as [number, number][]) {
          expect(x).toBeGreaterThanOrEqual(0);
          expect(x).toBeLessThanOrEqual(w - 1);
          expect(y).toBeGreaterThanOrEqual(0);
          expect(y).toBeLessThanOrEqual(h - 1);
        }
      }
    }
  });
});

describe("joinSegments", () => {
  it("竖直等值线串成一条连续折线（端到端相接）", () => {
    const segs = contourSegments(linearField(10, 6), 4.5);
    const paths = joinSegments(segs);
    expect(paths.length).toBe(1);
    const pts = paths[0].points;
    expect(pts.length).toBeGreaterThanOrEqual(6);
    // 相邻点必须相接（无跳跃）
    for (let i = 1; i < pts.length; i++) {
      const dx = Math.abs(pts[i][0] - pts[i - 1][0]);
      const dy = Math.abs(pts[i][1] - pts[i - 1][1]);
      expect(dx + dy).toBeLessThanOrEqual(1.0001);
    }
  });

  it("空输入 → 空输出（不抛）", () => {
    expect(joinSegments([])).toEqual([]);
  });

  it("闭合环被标记为 closed", () => {
    // 中心高、四周低的"金字塔" → 等值线必须是闭合环
    // ⚠️ level 必须落在**值域之内**：该场最小 10-√32≈4.34，取 4 会得到"全场在等值面之上"= 无轮廓
    const w = 9, h = 9;
    const data = new Float64Array(w * h);
    for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
      const d = Math.hypot(c - 4, r - 4);
      data[r * w + c] = 10 - d;
    }
    const segs = contourSegments(fieldFromArray(data, w, h), 6);
    expect(segs.length).toBeGreaterThan(0);
    const paths = joinSegments(segs);
    const closed = paths.filter((p) => p.closed);
    expect(closed.length).toBe(1);
    // 闭合环的首尾必为同一点（否则 SVG 里会出现缺口）
    const pts = closed[0].points;
    expect(pts[0]).toEqual(pts[pts.length - 1]);
  });
});

describe("contourSvgPath", () => {
  it("输出 path 且不含位图/背景（透明底）", () => {
    const svg = contourSvgPath(linearField(12, 8), 0, 11, { levels: 4 });
    expect(svg).toContain("<path");
    expect(svg).not.toContain("<image");
    expect(svg).not.toContain("<rect");
    expect(svg).toContain('fill="none"');
  });

  it("路径点数远小于逐体素矩形数（这就是换算法的收益）", () => {
    const w = 48, h = 48;
    const data = new Float64Array(w * h);
    for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
      data[r * w + c] = Math.sin(c / 6) * Math.cos(r / 7) * 50 + 50;
    }
    const svg = contourSvgPath(fieldFromArray(data, w, h), 0, 100, { levels: 6 });
    const pathCount = (svg.match(/<path/g) || []).length;
    const pointCount = (svg.match(/[ML]/g) || []).length;
    expect(pathCount).toBeGreaterThan(0);
    expect(pointCount).toBeLessThan(w * h); // 3840 个点以下就算达标
  });

  it("值域退化（max<=min）→ 空串，不抛", () => {
    expect(contourSvgPath(linearField(5, 5), 3, 3)).toBe("");
  });

  it("低于显示阈值的等值线被跳过", () => {
    const low = contourSvgPath(linearField(12, 6), 0, 11, { levels: 8, minValue: 0 });
    const high = contourSvgPath(linearField(12, 6), 0, 11, { levels: 8, minValue: 8 });
    expect((high.match(/<path/g) || []).length).toBeLessThan((low.match(/<path/g) || []).length);
  });
});
