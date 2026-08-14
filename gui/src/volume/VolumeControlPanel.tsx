/**
 * VolumeControlPanel — 「3D 结果」窗口控制面板（契约 meshtal-visualization.md §4.7 / §12 F2）
 *
 * F2 默认值即好用：透明度、256³ 选择、手改色阶、几何外壳开关 = 高级控件，默认折叠/隐藏；
 * 基础（自适应色阶、自动取景、外壳开）开箱即用。
 */
import React, { useState } from "react";
import ColorLegend from "./ColorLegend";

export interface TimeOption {
  index: number;
  label: string;
}

export interface VolumeControlPanelProps {
  // 透明度（高级控件，F2 默认折叠）
  opacity: number;
  onOpacityChange: (v: number) => void;
  // 能量区间选择
  energyOptions: TimeOption[];
  energyIndex: number;
  onEnergyChange: (i: number) => void;
  // 时间轴
  timeOptions: TimeOption[];
  timeIndex: number;
  playing: boolean;
  onPlayToggle: () => void;
  onSeek: (idx: number) => void;
  // 几何外壳开关（高级控件）
  shellVisible: boolean;
  onShellVisibleChange: (v: boolean) => void;
  // 半透明查看
  seeThrough: boolean;
  onSeeThroughChange: (v: boolean) => void;
  // 色阶（高级控件：手改上下限；图例常显 F5.2）
  colorMin: number;
  colorMax: number;
  scalarMin: number;
  scalarMax: number;
  onColorRangeChange: (min: number, max: number) => void;
  unit?: string;
}

export default function VolumeControlPanel(props: VolumeControlPanelProps) {
  const {
    opacity, onOpacityChange,
    energyOptions, energyIndex, onEnergyChange,
    timeOptions, timeIndex, playing, onPlayToggle, onSeek,
    shellVisible, onShellVisibleChange, seeThrough, onSeeThroughChange,
    colorMin, colorMax, scalarMin, scalarMax, onColorRangeChange,
    unit = "归一化计数",
  } = props;
  const [showAdvanced, setShowAdvanced] = useState(false);

  const row: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, padding: "6px 14px", fontSize: 11 };
  const label: React.CSSProperties = { color: "var(--text-secondary)", flexShrink: 0, width: 56 };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* 色条图例（常显，F5.2 单位 + 上下限数值） */}
      <div style={{ padding: "8px 14px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
        <ColorLegend min={colorMin} max={colorMax} unit={unit} />
      </div>

      {/* 能量区间选择 */}
      {energyOptions.length > 0 && (
        <div style={row}>
          <span style={label}>能量区间</span>
          <select
            className="form-select"
            value={energyIndex}
            onChange={(e) => onEnergyChange(parseInt(e.target.value, 10) || 0)}
            style={{ flex: 1, height: 26, fontSize: 11 }}
          >
            {energyOptions.map((o) => (
              <option key={o.index} value={o.index}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* 时间轴（timeBins>1 才显示） */}
      {timeOptions.length > 1 && (
        <div style={{ padding: "6px 14px", fontSize: 11, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
          <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>时间轴</div>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <button className="btn btn-ghost btn-xs" onClick={onPlayToggle} style={{ fontSize: 10, flexShrink: 0 }}>
              {playing ? "⏸ 暂停" : "▶ 播放"}
            </button>
            <input
              type="range"
              min={0}
              max={Math.max(0, timeOptions.length - 1)}
              value={Math.min(timeIndex, Math.max(0, timeOptions.length - 1))}
              onChange={(e) => onSeek(parseInt(e.target.value, 10) || 0)}
              style={{ flex: 1, accentColor: "var(--accent)" }}
            />
            <span style={{ color: "var(--text-tertiary)", fontSize: 10, flexShrink: 0, width: 34, textAlign: "right" }}>
              {timeIndex + 1}/{timeOptions.length}
            </span>
          </div>
        </div>
      )}

      {/* 高级控件（F2 默认折叠） */}
      <div style={{ padding: "4px 14px" }}>
        <button
          className="btn btn-ghost btn-xs"
          onClick={() => setShowAdvanced((v) => !v)}
          style={{ fontSize: 10, width: "100%" }}
        >
          {showAdvanced ? "▲ 收起高级设置" : "▼ 高级设置"}
        </button>
      </div>
      {showAdvanced && (
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}>
          {/* 透明度 */}
          <div style={row}>
            <span style={label}>透明度</span>
            <input
              type="range" min={0} max={1} step={0.05} value={opacity}
              onChange={(e) => onOpacityChange(parseFloat(e.target.value))}
              style={{ flex: 1, accentColor: "var(--accent)" }}
            />
            <span style={{ color: "var(--text-tertiary)", fontSize: 10, width: 34, textAlign: "right" }}>
              {Math.round(opacity * 100)}%
            </span>
          </div>
          {/* 几何外壳开关 */}
          <div style={row}>
            <span style={label}>几何外壳</span>
            <input
              type="checkbox" checked={shellVisible}
              onChange={(e) => onShellVisibleChange(e.target.checked)}
              style={{ accentColor: "var(--accent)" }}
            />
            <span style={{ color: "var(--text-tertiary)" }}>显示半透明模型外壳</span>
          </div>
          {/* 半透明查看 */}
          <div style={row}>
            <span style={label}>半透明</span>
            <input
              type="checkbox" checked={seeThrough}
              onChange={(e) => onSeeThroughChange(e.target.checked)}
              style={{ accentColor: "var(--accent)" }}
            />
            <span style={{ color: "var(--text-tertiary)" }}>可看穿外壳查看体积层</span>
          </div>
          {/* 手改色阶上下限（A2.2 默认自适应 scalarRange） */}
          <div style={{ padding: "6px 14px", fontSize: 11 }}>
            <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>色阶上下限（默认自适应数据范围）</div>
            <div style={{ display: "flex", gap: 6 }}>
              <input
                className="form-input" type="number" step="any"
                value={Number.isFinite(colorMin) ? colorMin : ""}
                placeholder={String(Math.round(scalarMin * 1000) / 1000)}
                onChange={(e) => onColorRangeChange(parseFloat(e.target.value) || scalarMin, colorMax)}
                style={{ flex: 1, height: 26, fontSize: 11 }}
                title="色阶下限（低于此值不显示）"
              />
              <span style={{ color: "var(--text-tertiary)", alignSelf: "center" }}>至</span>
              <input
                className="form-input" type="number" step="any"
                value={Number.isFinite(colorMax) ? colorMax : ""}
                placeholder={String(Math.round(scalarMax * 1000) / 1000)}
                onChange={(e) => onColorRangeChange(colorMin, parseFloat(e.target.value) || scalarMax)}
                style={{ flex: 1, height: 26, fontSize: 11 }}
                title="色阶上限"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
