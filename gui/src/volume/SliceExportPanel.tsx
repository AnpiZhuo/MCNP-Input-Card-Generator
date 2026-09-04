/**
 * SliceExportPanel — 体积标量帧的切面预览 + 导出（PNG/SVG/CSV）
 * （能量沉积 3D 解析待办：切面、导出）
 *
 * 在「3D 结果」窗口底部提供：选切面轴(X/Y/Z) + 切片索引滑块 → 2D 热图预览（canvas），
 * 并可导出当前切面为 PNG / SVG、当前帧全数据为 CSV。全部用浏览器原生能力，零新依赖。
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { sliceFrame, frameToCsv, sliceToSvg, type SliceAxis, type SliceFrameInput } from "./sliceExport";
import { formatLegendValue } from "./ColorLegend";

interface SliceExportPanelProps {
  /** 当前 (energy,time) 帧标量（null = 尚无数据，禁用） */
  frame: SliceFrameInput | null;
  /** 色阶下限（显示阈值，低于不显示） */
  displayMin: number;
}

const AXIS_OPTIONS: { value: SliceAxis; label: string }[] = [
  { value: "x", label: "X 轴（i）" },
  { value: "y", label: "Y 轴（j）" },
  { value: "z", label: "Z 轴（k）" },
];

function downloadBlob(name: string, blob: Blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function SliceExportPanel({ frame, displayMin }: SliceExportPanelProps) {
  const [axis, setAxis] = useState<SliceAxis>("z");
  const [index, setIndex] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const axisSize = useMemo(() => {
    if (!frame) return 0;
    const [ni, nj, nk] = frame.resolution;
    if (axis === "x") return ni;
    if (axis === "y") return nj;
    return nk;
  }, [frame, axis]);

  const sliceIndex = Math.max(0, Math.min(index, Math.max(0, axisSize - 1)));

  const slice = useMemo(() => {
    if (!frame) return null;
    return sliceFrame(frame, axis, sliceIndex, displayMin);
  }, [frame, axis, sliceIndex, displayMin]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !slice) return;
    canvas.width = slice.width;
    canvas.height = slice.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const img = ctx.createImageData(slice.width, slice.height);
    img.data.set(slice.rgba);
    ctx.putImageData(img, 0, 0);
  }, [slice]);

  const exportSlicePng = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const name = `slice_${axis}_${sliceIndex}.png`;
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = name;
    a.click();
  };

  const exportSliceSvg = () => {
    if (!slice) return;
    const blob = new Blob([sliceToSvg(slice)], { type: "image/svg+xml" });
    downloadBlob(`slice_${axis}_${sliceIndex}.svg`, blob);
  };

  const exportFrameCsv = () => {
    if (!frame) return;
    const blob = new Blob([frameToCsv(frame)], { type: "text/csv" });
    downloadBlob(`frame_${axis}_slice.csv`, blob);
  };

  if (!frame) {
    return null;
  }

  return (
    <div style={{ padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 6 }}>
        ✂ 切面 / 导出
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6, flexWrap: "wrap" }}>
        <select
          className="form-select"
          value={axis}
          onChange={(e) => { setAxis(e.target.value as SliceAxis); setIndex(0); }}
          style={{ height: 26, fontSize: 11, width: 110 }}
        >
          {AXIS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <input
          type="range"
          min={0}
          max={Math.max(0, axisSize - 1)}
          value={sliceIndex}
          onChange={(e) => setIndex(parseInt(e.target.value, 10) || 0)}
          style={{ flex: 1, accentColor: "var(--accent)" }}
          title="切片索引"
        />
        <span style={{ color: "var(--text-tertiary)", fontSize: 10, flexShrink: 0 }}>{sliceIndex + 1}/{Math.max(axisSize, 1)}</span>
      </div>
      {slice && (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
          <canvas ref={canvasRef} style={{ maxWidth: 200, maxHeight: 140, borderRadius: 3, border: "1px solid rgba(255,255,255,0.12)", imageRendering: "pixelated", background: "#0a0a1e" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 10, flex: 1 }}>
            <span style={{ color: "var(--text-tertiary)" }}>
              切面值域：{formatLegendValue(slice.min)} ~ {formatLegendValue(slice.max)}
            </span>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <button className="btn btn-ghost btn-xs" onClick={exportSlicePng} style={{ fontSize: 10 }}>导出 PNG</button>
              <button className="btn btn-ghost btn-xs" onClick={exportSliceSvg} style={{ fontSize: 10 }}>导出 SVG</button>
              <button className="btn btn-ghost btn-xs" onClick={exportFrameCsv} style={{ fontSize: 10 }}>导出 CSV</button>
            </div>
            <span style={{ color: "var(--text-tertiary)", fontSize: 9, lineHeight: 1.4 }}>
              切面 = {axis.toUpperCase()} 固定第 {sliceIndex + 1} 层；CSV 导出当前帧全部体素（i,j,k,value）
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
