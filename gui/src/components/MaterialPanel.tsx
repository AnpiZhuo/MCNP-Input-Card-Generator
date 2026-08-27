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
        {uniq.map((e, i) => {
          const isVoid = e.mat === "0";
          return (
            <span key={i} style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 10, color: "var(--text-secondary)" }}>
              {isVoid ? (
                <span style={{ width: 10, height: 10, borderRadius: "50%", border: "2px solid rgba(255,255,255,0.35)", flexShrink: 0 }} />
              ) : (
                <span style={{ color: getMatColor(e.mat), fontSize: 16, lineHeight: 1 }}>●</span>
              )}
              {isVoid ? "M0 - 真空" : (e.comment ? `M${e.mat} - ${e.comment}` : `M${e.mat}`)}
            </span>
          );
        })}
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
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: r.mat === "0" ? "transparent" : getMatColor(r.mat), flexShrink: 0, border: r.mat === "0" ? "1px dashed rgba(255,255,255,0.45)" : "1px solid rgba(255,255,255,0.2)" }} />
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

/** 3D 预览格阵侧边栏：U 组条目（每个 u 非空一条）+ 未分组（u 为空）栅元行。
 *  「组成 U 的栅元」不作为独立行平铺，改由 U 组呈现；U 为空的栅元照常列出。 */
export interface UniverseGroupRow {
  u: number;
  count: number;
  color: string;      // 该组代表色（组内首个非 void 栅元材料色，void 则灰）
  visible?: boolean;  // 组内是否 all-visible（无 locked 概念，组可整体切换）
}

export function UniverseCellList({ groups, ungrouped, onToggleGroup, onToggle, onMaterialClick }: {
  groups: UniverseGroupRow[];
  ungrouped: MaterialCellRow[];
  onToggleGroup?: (u: number) => void;
  onToggle?: (i: number) => void;
  onMaterialClick?: (i: number, e: React.MouseEvent) => void;
}) {
  const groupStyle: React.CSSProperties = {
    display: "flex", alignItems: "center", gap: 6, padding: "6px 14px",
    cursor: onToggleGroup ? "pointer" : "default",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    background: "rgba(76,159,232,0.06)",
  };
  return (
    <div style={{ flex: 1, overflow: "auto" }}>
      <div style={{ padding: "6px 14px", fontSize: 10, color: "var(--text-tertiary)", fontWeight: 600 }}>
        U 组（{groups.length}）
      </div>
      {groups.map((g) => (
        <div
          key={`u-${g.u}`}
          style={groupStyle}
          onClick={onToggleGroup ? () => onToggleGroup(g.u) : undefined}
          title="点击切换该 universe 全部栅元可见性"
        >
          <input
            type="checkbox" checked={g.visible !== false} readOnly
            style={{ pointerEvents: "none", flexShrink: 0 }}
          />
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: g.color, flexShrink: 0, border: "1px solid rgba(255,255,255,0.2)" }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-primary)", flexShrink: 0 }}>{`U=${g.u}`}</span>
          <span style={{ fontSize: 10, color: "var(--text-secondary)", flexShrink: 0 }}>{`· ${g.count} 栅元`}</span>
        </div>
      ))}
      {ungrouped.length > 0 && (
        <div style={{ padding: "6px 14px", fontSize: 10, color: "var(--text-tertiary)", fontWeight: 600, borderTop: "1px solid rgba(255,255,255,0.04)" }}>
          未分组栅元（{ungrouped.length}）
        </div>
      )}
      <CellList rows={ungrouped} onToggle={onToggle} onMaterialClick={onMaterialClick} />
    </div>
  );
}
