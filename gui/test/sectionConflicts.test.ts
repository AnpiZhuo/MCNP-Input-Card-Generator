/**
 * sectionConflicts 纯函数测试 —— 截面上的「重叠区」检测。
 *
 * 用户口径沿革：
 * · 2026-10-07：「重叠/空隙现在靠'谁后声明谁盖住'，这是把问题藏起来」⇒ 标出**重叠**；
 * · 2026-10-08：**「空腔就应该是空的」** ⇒ 上一版把"被材料围住的空白"也标成"空隙"是错的，
 *   正好把用户模型里本该为空的空腔涂上了标记（他看到的"莫名其妙的东西"）。空白一律不标。
 */
import { describe, it, expect } from "vitest";
import { sectionConflicts, type P2 } from "../src/utils/sectionConflicts";

function disk(cx: number, cy: number, r: number, n = 72): P2[] {
  const out: P2[] = [];
  for (let i = 0; i < n; i++) {
    const t = (2 * Math.PI * i) / n;
    out.push({ x: cx + r * Math.cos(t), y: cy + r * Math.sin(t) });
  }
  return out;
}

describe("sectionConflicts（只标重叠）", () => {
  it("两盘同心（一个套在另一个里）⇒ 重叠面积 ≈ 小盘面积", () => {
    const c = sectionConflicts([{ polygons: [disk(0, 0, 4)] }, { polygons: [disk(0, 0, 2)] }]);
    expect(c.overlapArea).toBeGreaterThan(0);
    expect(c.overlapArea).toBeCloseTo(Math.PI * 4, -1);   // ≈12.57，允许 10% 级误差
    expect(c.overlapLoops.length).toBeGreaterThan(0);
  });

  it("部分重叠的两盘 ⇒ 重叠 = 透镜面积（估到 15% 以内）", () => {
    // 半径 3、圆心距 4 ⇒ 透镜面积 ≈ 8.16
    const c = sectionConflicts([
      { polygons: [disk(-2, 0, 3)] },
      { polygons: [disk(2, 0, 3)] },
    ]);
    expect(c.overlapArea).toBeGreaterThan(8.16 * 0.7);
    expect(c.overlapArea).toBeLessThan(8.16 * 1.3);
  });

  it("单个盘 ⇒ 无重叠", () => {
    const c = sectionConflicts([{ polygons: [disk(0, 0, 5)] }]);
    expect(c.overlapArea).toBe(0);
    expect(c.overlapLoops).toEqual([]);
  });

  it("★环带（外环 + 内孔，孔里没有别的栅元）⇒ **什么也不标**（空腔就应该是空的）", () => {
    const c = sectionConflicts([{ polygons: [disk(0, 0, 5), disk(0, 0, 3)] }]);
    expect(c.overlapArea).toBe(0);
    expect(c.overlapLoops).toEqual([]);
  });

  it("两个不相交的盘 ⇒ 无重叠（它们之间的空白也不标）", () => {
    const c = sectionConflicts([
      { polygons: [disk(-10, 0, 2)] },
      { polygons: [disk(10, 0, 2)] },
    ]);
    expect(c.overlapArea).toBe(0);
  });

  it("空输入 / 无点 / 单栅元 ⇒ 全 0（不抛）", () => {
    expect(sectionConflicts([]).overlapArea).toBe(0);
    expect(sectionConflicts([{ polygons: [] }]).overlapArea).toBe(0);
    expect(sectionConflicts([{ polygons: [disk(0, 0, 3)] }, { polygons: [] }]).overlapArea).toBe(0);
  });
});
