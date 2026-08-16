import { describe, it, expect } from "vitest";
import {
  decimatePoints, decimateTracks, sampleTracks,
} from "../../src/ptrac/decimateTracks";

/**
 * 径迹点均匀抽稀 + 密度抽样（契约 ptrac-visualization.md §4 / §5）
 * - decimatePoints：超 maxPoints 按步长均匀跳点，保持首尾（与后端同规则）。
 * - sampleTracks：每 step 条取 1，固定按 nps 序号稳定抽样。
 */

function seq(n: number): number[][] {
  return Array.from({ length: n }, (_, i) => [i, 0, 0, 0, 0]);
}

describe("decimatePoints（均匀抽稀保持首尾）", () => {
  it("不超过 maxPoints → 原样返回", () => {
    const pts = seq(5);
    expect(decimatePoints(pts, 10)).toBe(pts);
    expect(decimatePoints(pts, 5)).toBe(pts);
  });

  it("超 maxPoints → 抽稀到 maxPoints 且保持首尾", () => {
    const pts = seq(100);
    const out = decimatePoints(pts, 10);
    expect(out.length).toBe(10);
    expect(out[0]).toBe(pts[0]);
    expect(out[out.length - 1]).toBe(pts[99]);
  });

  it("maxPoints<=0 / 空 → 空数组", () => {
    expect(decimatePoints(seq(3), 0)).toEqual([]);
    expect(decimatePoints([], 5)).toEqual([]);
  });

  it("抽稀结果均匀（索引等距递增）", () => {
    const pts = seq(100);
    const out = decimatePoints(pts, 10);
    // 首尾固定，中间按步长 99/9=11 均匀取
    expect(out[1][0]).toBe(11);
    expect(out[2][0]).toBe(22);
    expect(out[5][0]).toBe(55);
  });
});

describe("sampleTracks（密度抽样，按 nps 序号稳定）", () => {
  const tracks = Array.from({ length: 100 }, (_, i) => ({ nps: i + 1, particle: "n", points: [[0, 0, 0, 0, 0]] }));

  it("step=1 → 全量", () => {
    expect(sampleTracks(tracks, 1).length).toBe(100);
  });

  it("step=10 → 每 10 条取 1（1/10），首条保留", () => {
    const out = sampleTracks(tracks, 10);
    expect(out.length).toBe(10);
    expect(out[0].nps).toBe(1);   // 序号 1
    expect(out[1].nps).toBe(11);  // 序号 11
    expect(out[9].nps).toBe(91);  // 序号 91
  });

  it("step=100 → 1/100", () => {
    expect(sampleTracks(tracks, 100).length).toBe(1);
  });

  it("step<=1 → 全量（防御）", () => {
    expect(sampleTracks(tracks, 0).length).toBe(100);
    expect(sampleTracks(tracks, -1).length).toBe(100);
  });

  it("空 tracks → 空", () => {
    expect(sampleTracks([], 10)).toEqual([]);
  });
});

describe("decimateTracks（聚合，显示前兜底）", () => {
  it("总点数超预算 → 每条均匀抽稀，总点数 <= 预算", () => {
    const tracks = Array.from({ length: 10 }, (_, i) => ({
      nps: i + 1, particle: "n", points: seq(100),
    }));
    const out = decimateTracks(tracks, 200); // 预算 200 点，10 条 → 每条 20 点
    const total = out.reduce((s, t) => s + t.points.length, 0);
    expect(total).toBe(200);
    expect(out[0].points[0]).toBe(tracks[0].points[0]);        // 保持首
    expect(out[0].points[out[0].points.length - 1]).toBe(tracks[0].points[99]); // 保持尾
  });

  it("预算充足 → 不抽稀", () => {
    const tracks = [{ nps: 1, particle: "n", points: seq(10) }];
    const out = decimateTracks(tracks, 100);
    expect(out[0].points.length).toBe(10);
  });
});
