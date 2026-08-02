/**
 * 网格编辑器 — 线性/对数/自定义 三选一（互斥显示，但三者都存在于 DOM）
 * 受控组件：值在 deck.grids[prefix]，读写都走 Context，无 DOM 操作。
 */
import React from "react";
import { useDeck } from "../utils/DeckContext";
import type { GridValue, GridMode } from "../utils/gridState";

interface Props {
  prefix: string;     // "e" | "t" | "e25" | "t85"...
  label: string;       // 显示名
  unit?: string;       // 单位
  defaultMin?: string;
  defaultMax?: string;
  defaultBins?: string;
}

const MODES: { v: GridMode; l: string }[] = [
  { v: "linear", l: "线性" },
  { v: "log", l: "对数" },
  { v: "custom", l: "自定义" },
];

export default function GridEditor({ prefix, label, unit, defaultMin, defaultMax, defaultBins }: Props) {
  const { deck, patch } = useDeck();
  const gv: GridValue = deck.grids?.[prefix] || { mode: "custom", min: "", max: "", bins: "", log: false, custom: "" };
  const set = (next: Partial<GridValue>) =>
    patch({ grids: { ...(deck.grids || {}), [prefix]: { ...gv, ...next } } });

  const showParams = gv.mode !== "custom";
  const showCustom = gv.mode === "custom";

  return (
    <div>
      <div style={{ display: "flex", gap: 8, margin: "6px 0", flexWrap: "wrap" }}>
        {MODES.map((opt) => (
          <label key={opt.v} className="check-item" style={{ fontSize: 12 }}>
            <input
              type="radio"
              id={`${prefix}-grid-${opt.v}`}
              name={`grid-${prefix}`}
              value={opt.v}
              checked={gv.mode === opt.v}
              onChange={() => set({ mode: opt.v, log: opt.v === "log" })}
            />
            {" "}{opt.l}
          </label>
        ))}
      </div>
      {/* 线性/对数：min/max/bins（常驻 DOM，自定义时隐藏） */}
      <div id={`${prefix}-params`} className="form-row" style={{ display: showParams ? "" : "none" }}>
        <div className="form-group" style={{ maxWidth: 120 }}>
          <label className="form-label">{label} 最小值{unit ? ` (${unit})` : ""}</label>
          <input id={`${prefix}-min`} className="form-input" value={gv.min} onChange={e => set({ min: e.target.value })} placeholder={defaultMin ? `如 ${defaultMin}` : ""} />
        </div>
        <div className="form-group" style={{ maxWidth: 120 }}>
          <label className="form-label">{label} 最大值</label>
          <input id={`${prefix}-max`} className="form-input" value={gv.max} onChange={e => set({ max: e.target.value })} placeholder={defaultMax ? `如 ${defaultMax}` : ""} />
        </div>
        <div className="form-group" style={{ maxWidth: 90 }}>
          <label className="form-label">Bin 数</label>
          <input id={`${prefix}-bins`} className="form-input" value={gv.bins} onChange={e => set({ bins: e.target.value })} placeholder={defaultBins ? `如 ${defaultBins}` : ""} />
        </div>
      </div>
      {/* 自定义：textarea（常驻 DOM，线性/对数时隐藏） */}
      <div id={`${prefix}-custom-box`} style={{ display: showCustom ? "" : "none" }}>
        <div className="form-group">
          <label className="form-label">自定义 {label} 卡（每行一张）</label>
          <textarea id={`${prefix}-custom`} className="form-input" value={gv.custom} onChange={e => set({ custom: e.target.value })}
            style={{ minHeight: 80, fontFamily: "Consolas,monospace", fontSize: 12 }}
            placeholder={`${prefix.toUpperCase()}  ${unit === "shake" ? "0 50i 1e8" : "1e-11 100i 20.0"}`} />
        </div>
      </div>
    </div>
  );
}
