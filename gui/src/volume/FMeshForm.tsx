/**
 * FMeshForm — 网格计数（FMESH/TMESH）结构化表单（契约 meshtal-visualization.md §4.7.1 / §5.3 / §12 F5.1）
 *
 * 只做卡体结构化编辑：网格定义（每输入框幽灵文字注明关键字作用）+ 卡体预览 + 空态提示。
 * 「3D 体积可视化」启动入口已统一到「输出」标签页（开窗逻辑见 openVolume3DWindow.ts 共享模块）。
 */
import React, { useEffect, useMemo, useState } from "react";
import {
  emptyFmeshRow, fmeshToCardText, FMESH_PLACEHOLDERS,
  type FmeshRow,
} from "./fmeshState";

interface RowWithId extends FmeshRow {
  _uid: number;
}

const FMESH_FIELD_LABELS: { key: keyof FmeshRow; label: string; placeholder: string; width?: number }[] = [
  { key: "geom", label: "GEOM", placeholder: FMESH_PLACEHOLDERS.geom, width: 120 },
  { key: "origin", label: "ORIGIN", placeholder: FMESH_PLACEHOLDERS.origin, width: 200 },
  { key: "imesh", label: "IMESH", placeholder: FMESH_PLACEHOLDERS.imesh, width: 200 },
  { key: "iints", label: "IINTS", placeholder: FMESH_PLACEHOLDERS.iints, width: 90 },
  { key: "jmesh", label: "JMESH", placeholder: FMESH_PLACEHOLDERS.jmesh, width: 200 },
  { key: "jints", label: "JINTS", placeholder: FMESH_PLACEHOLDERS.jints, width: 90 },
  { key: "kmesh", label: "KMESH", placeholder: FMESH_PLACEHOLDERS.kmesh, width: 200 },
  { key: "kints", label: "KINTS", placeholder: FMESH_PLACEHOLDERS.kints, width: 90 },
  { key: "emesh", label: "EMESH", placeholder: FMESH_PLACEHOLDERS.emesh, width: 200 },
  { key: "eints", label: "EINTS", placeholder: FMESH_PLACEHOLDERS.eints, width: 90 },
  { key: "tmesh", label: "TMESH", placeholder: FMESH_PLACEHOLDERS.tmesh, width: 200 },
  { key: "t_ints", label: "TINTS", placeholder: FMESH_PLACEHOLDERS.t_ints, width: 90 },
  { key: "mat", label: "MAT", placeholder: FMESH_PLACEHOLDERS.mat, width: 90 },
  { key: "out", label: "OUT", placeholder: FMESH_PLACEHOLDERS.out, width: 70 },
];

export interface FMeshFormProps {
  /** FMESH/TMESH 行（受控自 deck.tally.fmesh） */
  value: FmeshRow[];
  /** 更新 rows（写回 deck.tally.fmesh） */
  onChange: (rows: FmeshRow[]) => void;
}

export default function FMeshForm({ value, onChange }: FMeshFormProps) {
  const [rows, setRows] = useState<RowWithId[]>(() =>
    (value || []).map((r, i) => ({ ...r, _uid: i + 1 })),
  );

  // 外部 value 变化（导入/文本模式回填）→ 同步本地 rows
  useEffect(() => {
    setRows((prev) => {
      const sig = JSON.stringify(value || []);
      const cur = JSON.stringify(prev.map((r) => {
        const { _uid, ...rest } = r;
        return rest;
      }));
      if (sig === cur) return prev;
      return (value || []).map((r, i) => ({ ...r, _uid: (prev[i]?._uid) ?? (Date.now() + i) }));
    });
  }, [value]);

  const pushRows = (next: RowWithId[]) => {
    setRows(next);
    onChange(next.map((r) => {
      const { _uid, ...rest } = r;
      return rest;
    }));
  };

  const updateRow = (uid: number, field: keyof FmeshRow, val: string) => {
    pushRows(rows.map((r) => (r._uid === uid ? { ...r, [field]: val } : r)));
  };
  const addRow = () => {
    pushRows([...rows, { ...emptyFmeshRow(), particle: "N", _uid: Date.now() }]);
  };
  const delRow = (uid: number) => {
    pushRows(rows.filter((r) => r._uid !== uid));
  };

  // 导出卡体（供调试/生成；生成载荷由 buildFmeshPayload 由父层调用）
  const cardText = useMemo(() => fmeshToCardText(rows), [rows]);

  /* ── 渲染 ── */
  const input = (uid: number, field: keyof FmeshRow) => {
    const spec = FMESH_FIELD_LABELS.find((f) => f.key === field);
    return (
      <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
        <span style={{ color: "var(--text-tertiary)" }}>{spec?.label}</span>
        <input
          className="form-input"
          value={(rows.find((r) => r._uid === uid) as any)?.[field] || ""}
          onChange={(e) => updateRow(uid, field, e.target.value)}
          placeholder={spec?.placeholder}
          title={spec?.placeholder}
          style={{ height: 26, fontSize: 11, width: spec?.width || 120 }}
        />
      </label>
    );
  };

  return (
    <div className="glass-card" style={{ marginTop: 16 }}>
      <div className="card-header">
        <span className="card-title">网格计数（FMESH/TMESH）</span>
        <button className="btn btn-success btn-sm" onClick={addRow}>+ 添加网格计数</button>
      </div>

      {/* FMESH/TMESH 结构化表单（F5.1 幽灵文字） */}
      {rows.length === 0 ? (
        <div style={{ padding: "8px 14px", fontSize: 11, color: "var(--text-tertiary)" }}>
          尚无网格计数卡。点「+ 添加网格计数」创建 FMESH/TMESH 卡，或从 INP 导入自动识别。
        </div>
      ) : (
        rows.map((r) => (
          <div key={r._uid} style={{ border: "1px solid rgba(255,255,255,0.06)", borderRadius: 6, padding: 8, margin: "8px 0" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 6, flexWrap: "wrap" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                <span style={{ color: "var(--text-tertiary)" }}>类型</span>
                <select
                  className="form-select"
                  value={r.kind}
                  onChange={(e) => updateRow(r._uid, "kind", e.target.value)}
                  style={{ height: 26, fontSize: 11, width: 90 }}
                >
                  <option value="FMESH">FMESH</option>
                  <option value="TMESH">TMESH</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                <span style={{ color: "var(--text-tertiary)" }}>编号</span>
                <input className="form-input" value={r.number} onChange={(e) => updateRow(r._uid, "number", e.target.value)} placeholder="如 4" style={{ height: 26, fontSize: 11, width: 60 }} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                <span style={{ color: "var(--text-tertiary)" }}>粒子设计符</span>
                <select
                  className="form-select"
                  value={r.particle}
                  onChange={(e) => updateRow(r._uid, "particle", e.target.value)}
                  style={{ height: 26, fontSize: 11, width: 70 }}
                  title="粒子设计符：N/P/E"
                >
                  <option value="N">N（中子）</option>
                  <option value="P">P（光子）</option>
                  <option value="E">E（电子）</option>
                </select>
              </label>
              {input(r._uid, "geom")}
              {input(r._uid, "origin")}
              <button className="btn btn-danger btn-xs" onClick={() => delRow(r._uid)} style={{ marginLeft: "auto", alignSelf: "flex-end" }}>x</button>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {input(r._uid, "imesh")}{input(r._uid, "iints")}
              {input(r._uid, "jmesh")}{input(r._uid, "jints")}
              {input(r._uid, "kmesh")}{input(r._uid, "kints")}
              {input(r._uid, "emesh")}{input(r._uid, "eints")}
              {input(r._uid, "tmesh")}{input(r._uid, "t_ints")}
              {input(r._uid, "mat")}{input(r._uid, "out")}
            </div>
          </div>
        ))
      )}

      {cardText && (
        <details style={{ fontSize: 10, color: "var(--text-tertiary)", padding: "4px 14px" }}>
          <summary style={{ cursor: "pointer" }}>当前卡体预览（点击展开）</summary>
          <pre style={{ background: "rgba(0,0,0,0.3)", padding: 8, borderRadius: 4, fontFamily: "Consolas,monospace", fontSize: 11, whiteSpace: "pre-wrap" }}>{cardText}</pre>
        </details>
      )}
    </div>
  );
}
