/**
 * ColorLegend — 色条图例（契约 meshtal-visualization.md §12 F5.2）
 *
 * 色条两端显示当前 displayMin/displayMax 数值 + 单位标签（如「归一化计数」）。
 * `legendTicks(min, max, n)` 纯函数生成等距刻度（vitest 可测）。
 */
import React from "react";

/** 等距刻度（含两端）：legendTicks(0, 100, 4) → [0, 25, 50, 75, 100] */
export function legendTicks(min: number, max: number, n = 4): number[] {
  const count = Math.max(1, Math.floor(n));
  const out: number[] = [];
  const span = max - min;
  for (let i = 0; i <= count; i++) {
    out.push(min + (span * i) / count);
  }
  return out;
}

/** 数值格式化：整数省略小数位，大/小值用指数紧凑表示 */
export function formatLegendValue(v: number): string {
  if (!Number.isFinite(v)) return String(v);
  const abs = Math.abs(v);
  if (abs !== 0 && (abs >= 1e5 || abs < 1e-3)) {
    return v.toExponential(2);
  }
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 1000) / 1000);
}

export interface ColorLegendProps {
  min: number; // 色阶下限（displayMin，float 单位）
  max: number; // 色阶上限（displayMax）
  unit?: string; // 单位标签（默认「归一化计数」）
}

export default function ColorLegend({ min, max, unit = "归一化计数" }: ColorLegendProps) {
  const ticks = legendTicks(min, max, 4);
  const colors = [
    "#3b4cc0", "#00e5ff", "#fde047", "#f97316", "#dc2626",
  ];
  const height = 10;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, width: "100%", fontSize: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-tertiary)" }}>
        <span>{formatLegendValue(ticks[0])}</span>
        <span>{unit}</span>
        <span>{formatLegendValue(ticks[ticks.length - 1])}</span>
      </div>
      <div
        style={{
          height,
          borderRadius: 3,
          background: `linear-gradient(to right, ${colors.join(", ")})`,
          border: "1px solid rgba(255,255,255,0.15)",
        }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-tertiary)" }}>
        {ticks.slice(1, -1).map((t, i) => (
          <span key={i}>{formatLegendValue(t)}</span>
        ))}
      </div>
    </div>
  );
}
