/**
 * 参数扫描 keff 仪表盘（Recharts）：
 *  - 主图：k-eff vs 扫描参数（误差棒 + y=1 临界参考线）
 *  - 小多图：每个 run 的 k-eff 逐周期收敛曲线
 * 数据聚合走 utils/sweepDashboard.ts（纯函数，可单测）。
 */
import React from "react";
import {
  CartesianGrid,
  ErrorBar,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  buildDashboard,
  convergencePoints,
  type SweepParameter,
  type SweepRunRecord,
} from "../utils/sweepDashboard";

interface Props {
  records: SweepRunRecord[];
  parameters: SweepParameter[];
  width?: number;
  height?: number;
}

const axisStyle = { fontSize: 11, fill: "var(--text-tertiary, #94a3b8)" };
const gridColor = "rgba(255,255,255,0.08)";

export default function SweepDashboard({ records, parameters, width = 720, height = 280 }: Props) {
  const data = React.useMemo(
    () => buildDashboard(records, parameters),
    [records, parameters],
  );
  const hasAxis = data.paramName !== null && data.points.length > 0;
  const convergedRuns = data.runs.filter((r) => (r.convergence?.mean?.length ?? 0) > 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div>
        <div style={{ fontSize: 11, color: "var(--text-tertiary, #94a3b8)", marginBottom: 4 }}>
          k-eff vs {data.paramName ?? "参数"}（误差棒 = 末周期 std，虚线 = 临界 1.0）
          {data.otherParams.length > 0 && (
            <span> ｜ 固定参数：{data.otherParams.join(" / ")}</span>
          )}
        </div>
        {hasAxis ? (
          <LineChart width={width} height={height} data={data.points} margin={{ top: 8, right: 20, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
            <XAxis
              dataKey="x"
              type="number"
              domain={["dataMin", "dataMax"]}
              tick={{ ...axisStyle }}
              label={{ value: data.paramName ?? "", position: "insideBottomRight", offset: -2, style: { fill: "var(--text-tertiary, #94a3b8)", fontSize: 10 } }}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ ...axisStyle }}
              width={52}
              label={{ value: "k-eff", angle: -90, position: "insideLeft", style: { fill: "var(--text-tertiary, #94a3b8)", fontSize: 10, textAnchor: "middle" } }}
            />
            <Tooltip
              contentStyle={{
                background: "var(--bg-input, #121a2e)",
                border: "1px solid rgba(255,255,255,0.12)",
                borderRadius: 6,
                fontSize: 12,
                color: "var(--text-primary, #e2e8f0)",
              }}
              formatter={(value) =>
                typeof value === "number"
                  ? [value.toFixed(5), "k-eff"]
                  : Array.isArray(value)
                    ? [value.join(", "), "k-eff"]
                    : [value === undefined ? "n/a" : String(value), "k-eff"]
              }
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ReferenceLine y={1} stroke="#f87171" strokeDasharray="4 4" />
            <Line
              type="monotone"
              dataKey="keff"
              stroke="#38bdf8"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            >
              <ErrorBar dataKey="keffStd" stroke="#fbbf24" strokeWidth={1.5} width={4} />
            </Line>
          </LineChart>
        ) : (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-tertiary, #94a3b8)", fontSize: 12 }}>
            无可用主图数据（扫描轴参数缺失或数值解析失败）
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: 11, color: "var(--text-tertiary, #94a3b8)", marginBottom: 4 }}>
          逐 run 收敛（{convergedRuns.length}/{data.runs.length} 个 run 有 mctal 收敛序列）
        </div>
        {convergedRuns.length === 0 ? (
          <div style={{ padding: 16, textAlign: "center", color: "var(--text-tertiary, #94a3b8)", fontSize: 12 }}>
            无收敛数据（确认 MCNP 已产出 mctal 且 run 目录未被清理）
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
            {convergedRuns.map((r) => {
              const pts = convergencePoints(r.convergence);
              return (
                <div key={r.index} style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: 6, background: "var(--bg-card, #121a2e)" }}>
                  <div style={{ fontSize: 10, color: "var(--text-tertiary, #94a3b8)", padding: "2px 4px 4px" }}>
                    run #{r.index}（k-eff {r.keff === null ? "n/a" : r.keff.toFixed(5)}）
                  </div>
                  <LineChart width={208} height={110} data={pts} margin={{ top: 6, right: 10, bottom: 0, left: -18 }}>
                    <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
                    <XAxis dataKey="cycle" type="number" domain={["dataMin", "dataMax"]} tick={{ ...axisStyle, fontSize: 9 }} tickCount={4} />
                    <YAxis domain={["auto", "auto"]} tick={{ ...axisStyle, fontSize: 9 }} tickCount={4} width={44} />
                    <ReferenceLine y={1} stroke="#f87171" strokeDasharray="3 3" />
                    <Line type="monotone" dataKey="mean" stroke="#38bdf8" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  </LineChart>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
