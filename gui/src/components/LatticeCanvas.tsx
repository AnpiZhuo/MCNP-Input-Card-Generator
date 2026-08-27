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
/* 面法向 0°/60°/120°（项16）：clipPath 左右为平边（面 ⊥ a1=0°）、顶/底为顶点，
 * 与 RHP R1∥a1 及 hexCenter 蜂窝排布一致（原左右顶点=30° 朝向是几何错）。 */
const HEX_CLIP = "polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)";

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
        {/* 项5：XY 按数学平面（X 右 / Y 上）——行 j 从下往上排（首 DOM 行 = 最大 j 行） */}
        {Array.from({ length: rows }).map((_, jr) =>
          Array.from({ length: cols }).map((_, ic) => {
            const j = rows - 1 - jr;
            const i = ic;
            const li = j * cols + i;
            const idx = k * layerSize + li;
            const c = cells[idx];
            if (!c) return null;
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
          }),
        )}
      </div>
    </div>
  );

  /* 六棱柱：每层绝对定位的蜂窝（hexCenter 项5 权威公式交错排布，顶点+X）。
   * 格心从 (0,0) 起，整体平移 minX/minY 到非负坐标，避免第一列左半被容器裁掉（显示不全）。 */
  const renderHexLayer = (k: number) => {
    const layerCells = hexCells.filter((c) => c.layer === k);
    const minX = layerCells.length ? Math.min(...layerCells.map((c) => c.x)) : 0;
    const minY = layerCells.length ? Math.min(...layerCells.map((c) => c.y)) : 0;
    const maxX = layerCells.length ? Math.max(...layerCells.map((c) => c.x)) : 0;
    const maxY = layerCells.length ? Math.max(...layerCells.map((c) => c.y)) : 0;
    // 顶点+X 格元盒：顶点-顶点宽 = 2pitch/√3（=2R），flat-flat 高 = pitch
    const cellW = (2 * pitch) / Math.sqrt(3);
    const cellH = pitch;
    return (
      <div key={k} className="lattice-layer">
        {layers > 1 && <div className="lattice-layer-label">层 {k}</div>}
        <div style={{ position: "relative", width: maxX - minX + cellW, height: maxY - minY + cellH }}>
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
                  left: h.x - minX,
                  top: maxY - h.y, // 项5：Y 向上（数学平面）；Y 越大越靠上
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
