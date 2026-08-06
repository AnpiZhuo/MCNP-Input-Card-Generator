/**
 * 材料图例 + 栅元列表 — 3D 预览与二维截面共用的统一面板
 * 颜色单一权威（getMatColor），两种视图渲染结构完全一致。
 */
import React from "react";
import { getMatColor } from "../utils/materialColors";

export interface MaterialCellRow {
  num: number | string;
  mat: string;
  comment?: string;     // 栅元注释（显示在行尾）
  trailing?: string;    // 右侧额外信息（如 "2 面"），无 comment 时显示
  visible?: boolean;    // checkbox 状态（提供 onToggle 时生效）
  locked?: boolean;     // 材料 0 → checkbox 禁用
}

/** 材料颜色对照：● + M{mat} - {comment}（按材料去重） */
export function MaterialLegend({ entries }: { entries: { mat: string; comment?: string }[] }) {
  const seen = new Set<string>();
  const uniq = entries.filter(e => { if (seen.has(e.mat)) return false; seen.add(e.mat); return true; });
  return (
    <div style={{ padding: "8px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
      <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>材料颜色对照</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 10px" }}>
        {uniq.map((e, i) => (
          <span key={i} style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 10, color: "var(--text-secondary)" }}>
            <span style={{ color: getMatColor(e.mat), fontSize: 16, lineHeight: 1 }}>●</span>
            {e.comment ? `M${e.mat} - ${e.comment}` : `M${e.mat}`}
          </span>
        ))}
      </div>
    </div>
  );
}

/** 栅元列表：checkbox(可选) + 栅元N + 色点 + M材料号(可点) + 注释/trailing */
export function CellList({ rows, onToggle, onMaterialClick }: {
  rows: MaterialCellRow[];
  onToggle?: (i: number) => void;
  onMaterialClick?: (i: number, e: React.MouseEvent) => void;
}) {
  return (
    <div style={{ flex: 1, overflow: "auto" }}>
      {rows.map((r, i) => (
        <div
          key={i}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "5px 14px", cursor: onToggle ? "pointer" : "default",
            borderBottom: "1px solid rgba(255,255,255,0.03)",
            opacity: r.visible === undefined || r.visible ? 1 : 0.4,
          } as React.CSSProperties}
          onClick={onToggle ? () => { if (!r.locked) onToggle(i); } : undefined}
        >
          {onToggle && (
            <input
              type="checkbox" checked={!!r.visible} disabled={r.locked}
              onClick={(e) => e.stopPropagation()}  // 阻止冒泡到行 onClick，避免双触发
              onChange={() => { if (!r.locked) onToggle(i); }}
              style={{ cursor: r.locked ? "not-allowed" : "pointer", flexShrink: 0 }}
            />
          )}
          <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-primary)", minWidth: 52 }}>{`栅元 ${r.num}`}</span>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: getMatColor(r.mat), flexShrink: 0, border: "1px solid rgba(255,255,255,0.2)" }} />
          {onMaterialClick ? (
            <button
              onClick={(e) => { e.stopPropagation(); onMaterialClick(i, e); }}
              title="点击更改材料"
              style={{
                fontSize: 10, color: "var(--accent)", background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.15)", borderRadius: 3,
                padding: "0 5px", cursor: "pointer", lineHeight: "16px",
                flexShrink: 0, minWidth: 30,
              } as React.CSSProperties}
            >{`M${r.mat}`}</button>
          ) : (
            <span style={{ fontSize: 10, color: "var(--text-secondary)", minWidth: 30 }}>{`M${r.mat}`}</span>
          )}
          {r.comment ? (
            <span style={{ fontSize: 10, color: "var(--text-tertiary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{`(${r.comment})`}</span>
          ) : r.trailing ? (
            <span style={{ fontSize: 10, color: "var(--text-tertiary)", marginLeft: "auto" }}>{r.trailing}</span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
