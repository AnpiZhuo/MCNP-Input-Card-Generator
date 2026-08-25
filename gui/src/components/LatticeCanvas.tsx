/**
 * LatticeCanvas — 格阵 2D 涂色画布（矩形 lat=1 = CSS grid；六棱柱 lat=2 = 蜂窝交错）。
 *
 * cells 为行主序（i 最快），与 FillGridJson.cells 下标对齐；点击格位 → onCellChange(idx, selectedU)。
 * void 格位（u 空 / "0"）渲染为暗底占位。条目流 ≠ dims 乘积时显示非阻塞警告（QA 建议3）。
 */
import React, { useMemo } from "react";
import { getUniverseColor, hexGrid, latticeMismatchMessage } from "../utils/lattice";
import type { FillGridCellJson } from "../utils/lattice";

interface Props {
  lat: string;                    // "1" | "2"
  dims: number[];                 // [cols, rows, layers]（六棱柱为 [2r+1, 2r+1, layers] 盒）
  cells: FillGridCellJson[];
  palette: Record<string, string>;
  selectedU: string;
  onCellChange: (idx: number, u: string) => void;
  disabled?: boolean;
  pitch?: number;
}

const VOID_BG = "rgba(255,255,255,0.04)";
/* 顶点朝 +X（flat-top）蜂窝：clipPath 顶点在左/右中点（±X 顶点），顶/底为平边 */
const HEX_CLIP = "polygon(0% 50%, 25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%)";

export default function LatticeCanvas({ lat, dims, cells, palette, selectedU, onCellChange, disabled, pitch = 18 }: Props) {
  const cols = Math.max(1, dims[0] ?? 1);
  const rows = Math.max(1, dims[1] ?? 1);
  const layers = Math.max(1, dims[2] ?? 1);
  const mismatch = latticeMismatchMessage(dims, cells);
  const layerSize = cols * rows;

  const hexCells = useMemo(
    () => (lat === "2" ? hexGrid([cols, rows, layers], pitch) : []),
    [lat, cols, rows, layers, pitch],
  );

  const cellBg = (u: string): string => {
    if (!u || u === "0") return VOID_BG;
    return getUniverseColor(u, palette);
  };
  const cellLabel = (u: string): string => (!u || u === "0" ? "" : u);

  const handleClick = (idx: number) => {
    if (disabled) return;
    onCellChange(idx, selectedU);
  };

  /* 矩形：每层一个 CSS grid（行主序自动填位） */
  const renderRectLayer = (k: number) => (
    <div key={k} className="lattice-layer">
      {layers > 1 && <div className="lattice-layer-label">层 {k}</div>}
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 26px)`, gap: 2 }}>
        {cells.slice(k * layerSize, (k + 1) * layerSize).map((c, li) => {
          const idx = k * layerSize + li;
          const i = li % cols;
          const j = Math.floor(li / cols);
          return (
            <button
              key={idx}
              type="button"
              data-testid={`lcell-${idx}`}
              aria-label={`格位 ${idx} U=${c.u}`}
              title={`(${i},${j},${k}) U=${c.u}`}
              onClick={() => handleClick(idx)}
              disabled={disabled}
              style={{
                width: 26, height: 26, border: "1px solid rgba(255,255,255,0.16)", borderRadius: 3,
                background: cellBg(c.u), color: "var(--text-secondary)", fontSize: 9,
                cursor: disabled ? "default" : "pointer", padding: 0, lineHeight: 1,
              }}
            >{cellLabel(c.u)}</button>
          );
        })}
      </div>
    </div>
  );

  /* 六棱柱：每层绝对定位的蜂窝（hexCenter 项5 权威公式交错排布，顶点+X） */
  const renderHexLayer = (k: number) => {
    const layerCells = hexCells.filter((c) => c.layer === k);
    const maxX = layerCells.length ? Math.max(...layerCells.map((c) => c.x)) : 0;
    const maxY = layerCells.length ? Math.max(...layerCells.map((c) => c.y)) : 0;
    // 顶点+X 格元盒：顶点-顶点宽 = 2pitch/√3（=2R），flat-flat 高 = pitch
    const cellW = (2 * pitch) / Math.sqrt(3);
    const cellH = pitch;
    return (
      <div key={k} className="lattice-layer">
        {layers > 1 && <div className="lattice-layer-label">层 {k}</div>}
        <div style={{ position: "relative", width: maxX + cellW, height: maxY + cellH }}>
          {layerCells.map((h) => {
            const c = cells[h.idx];
            if (!c) return null;
            return (
              <button
                key={h.idx}
                type="button"
                data-testid={`lcell-${h.idx}`}
                aria-label={`格位 ${h.idx} U=${c.u}`}
                title={`(col${h.col},row${h.row},k${k}) U=${c.u}`}
                onClick={() => handleClick(h.idx)}
                disabled={disabled}
                style={{
                  position: "absolute",
                  left: h.x - cellW / 2,
                  top: h.y - cellH / 2,
                  width: cellW,
                  height: cellH,
                  clipPath: HEX_CLIP,
                  background: cellBg(c.u),
                  border: "none",
                  cursor: disabled ? "default" : "pointer",
                  color: "var(--text-secondary)", fontSize: Math.max(7, pitch * 0.45), lineHeight: 1,
                  padding: 0,
                }}
              >{cellLabel(c.u)}</button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="lattice-canvas">
      {mismatch && (
        <div className="lattice-warn" style={{ fontSize: 11, color: "#e0a12e", marginBottom: 6 }}>
          ⚠ {mismatch}
        </div>
      )}
      {Array.from({ length: layers }).map((_, k) => (lat === "2" ? renderHexLayer(k) : renderRectLayer(k)))}
    </div>
  );
}
