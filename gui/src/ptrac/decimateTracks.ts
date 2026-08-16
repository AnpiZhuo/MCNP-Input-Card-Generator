/**
 * decimateTracks — 径迹点均匀抽稀 + 密度抽样（契约 ptrac-visualization.md §4）
 *
 * - decimatePoints(points, maxPoints)：超 maxPoints 按步长均匀跳点，保持首尾
 *   （与后端同规则，前端显示前兜底）。
 * - sampleTracks(tracks, step)：每 step 条取 1（1/1、1/10、1/100、1/1000、1/10000），
 *   固定按 nps 序号稳定抽样（tracks 已按 nps 升序）。
 * - decimateTracks(tracks, maxPoints)：聚合兜底——把总点预算均摊到每条再逐条抽稀。
 */

export type Point = number[];

export interface TrackLike {
  points: Point[];
}

/** 均匀抽稀：超 maxPoints 按步长跳点，保持首尾（含去重，防极小区间产生重复点） */
export function decimatePoints(points: Point[], maxPoints: number): Point[] {
  if (!points || points.length === 0) return [];
  if (maxPoints <= 0) return [];
  if (points.length <= maxPoints) return points;
  const last = points.length - 1;
  const span = maxPoints - 1;
  const out: Point[] = [];
  for (let i = 0; i < maxPoints; i++) {
    const idx = Math.round((i / span) * last);
    const p = points[idx];
    if (out.length > 0 && out[out.length - 1] === p) continue; // 去重
    out.push(p);
  }
  // 保证末点（抽稀步长取整时末点可能漂移）
  if (out[out.length - 1] !== points[last]) out[out.length - 1] = points[last];
  return out;
}

/** 密度抽样：每 step 条取 1（索引 i % step === 0，首条必留），step<=1 全量 */
export function sampleTracks<T extends { nps: number }>(tracks: T[], step: number): T[] {
  if (!tracks || tracks.length === 0) return [];
  const s = step && step >= 1 ? Math.floor(step) : 1;
  return tracks.filter((_, i) => i % s === 0);
}

/** 聚合兜底：总点预算 maxPoints 均摊到每条（至少 2 点/条），逐条均匀抽稀保持首尾 */
export function decimateTracks<T extends TrackLike>(tracks: T[], maxPoints: number): T[] {
  if (!tracks || tracks.length === 0) return tracks;
  if (maxPoints <= 0) return tracks;
  const withPoints = tracks.filter((t) => t.points && t.points.length > 0);
  const n = withPoints.length;
  if (n === 0) return tracks;
  const perTrack = Math.max(2, Math.floor(maxPoints / n));
  return tracks.map((t) => {
    if (!t.points || t.points.length <= perTrack) return t;
    return { ...t, points: decimatePoints(t.points, perTrack) };
  });
}
