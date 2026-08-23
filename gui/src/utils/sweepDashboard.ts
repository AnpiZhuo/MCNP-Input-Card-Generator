/**
 * 参数扫描仪表盘聚合纯函数（对齐 OWEN sweepDashboardCore.ts，零依赖可单测）。
 *
 * 输入：sweep-run 响应的 records + parameters；
 * 输出：k-eff vs 扫描参数主图数据（含误差棒）、每 run 收敛序列、运行表行。
 */

export interface SweepParameter {
  name: string;
  pattern: string;
  values: Array<string | number>;
}

export interface Convergence {
  cycles: number[];
  mean: number[];
  std: number[];
}

export interface SweepRunRecord {
  index: number;
  parameters: Record<string, string | number>;
  exitCode: number | null;
  keff: number | null;
  keffStd?: number | null;
  convergence?: Convergence | null;
}

export interface DashboardPoint {
  x: number;
  keff: number | null;
  keffStd: number | null;
}

export interface SweepDashboardData {
  /** 扫描轴参数名（第一个有多取值的参数）；全常量时取第一个参数名。 */
  paramName: string | null;
  points: DashboardPoint[];
  runs: SweepRunRecord[];
  otherParams: string[];
}

/** 扫描轴 = 第一个取值集合 size>1 的参数；无参数返回 null。 */
export function chooseSweepAxis(parameters: SweepParameter[]): string | null {
  for (const p of parameters) {
    const distinct = new Set(p.values.map((v) => String(v)));
    if (distinct.size > 1) return p.name;
  }
  return parameters.length > 0 ? parameters[0].name : null;
}

function toNumber(v: string | number | undefined): number | null {
  if (v === undefined || v === null) return null;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * 聚合扫描结果 → 仪表盘数据。keff/keffStd 缺失（未跑/解析失败）保留 null，
 * 主图跳过非数值轴点；points 按 x 升序。
 */
export function buildDashboard(
  records: SweepRunRecord[],
  parameters: SweepParameter[],
): SweepDashboardData {
  const paramName = chooseSweepAxis(parameters);
  const points: DashboardPoint[] = [];
  if (paramName) {
    for (const r of records) {
      const x = toNumber(r.parameters[paramName]);
      if (x === null) continue;
      points.push({ x, keff: r.keff ?? null, keffStd: r.keffStd ?? null });
    }
    points.sort((a, b) => a.x - b.x);
  }
  return {
    paramName,
    points,
    runs: records.map((r) => ({ ...r })),
    otherParams: parameters.map((p) => p.name).filter((n) => n !== paramName),
  };
}

/** 收敛序列 → Recharts 点集（cycle → mean，用于小多图）。 */
export function convergencePoints(c: Convergence | null | undefined): Array<{ cycle: number; mean: number }> {
  if (!c || !Array.isArray(c.cycles) || !Array.isArray(c.mean)) return [];
  const out: Array<{ cycle: number; mean: number }> = [];
  const n = Math.min(c.cycles.length, c.mean.length);
  for (let i = 0; i < n; i++) {
    out.push({ cycle: c.cycles[i], mean: c.mean[i] });
  }
  return out;
}
