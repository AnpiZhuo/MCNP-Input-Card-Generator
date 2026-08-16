/**
 * PtracForm — 计数标签页「粒子径迹（PTRAC）」小节表单（契约 ptrac-visualization.md §4.5）
 *
 * 状态 deck.tally.ptrac（PtracState）：勾选启用 → 生成 PTRAC 卡。
 * 常用 7 项平铺（FILE/WRITE/MAX/TYPE/NPS/CELL/SURFACE）+ 高级折叠（VALUE/EVENT）。
 * 纯状态读写，往返由 ptracState.ts 纯函数保证（round-trip 测试）。
 */
import React, { useState } from "react";
import {
  type PtracState, emptyPtracState,
  PTRAC_FILE_OPTIONS, PTRAC_WRITE_OPTIONS, PTRAC_TYPE_OPTIONS,
} from "./ptracState";

interface Props {
  value: PtracState | undefined;
  onChange: (state: PtracState) => void;
}

export default function PtracForm({ value, onChange }: Props) {
  const s: PtracState = value && typeof value === "object" ? value : emptyPtracState();
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const set = (patch: Partial<PtracState>) => onChange({ ...s, ...patch });

  const toggleType = (t: string) => {
    const has = s.types.includes(t);
    set({ types: has ? s.types.filter((x) => x !== t) : [...s.types, t] });
  };

  return (
    <div className="glass-card">
      <div className="card-header">
        <span className="card-title" style={{ flexShrink: 0 }}>粒子径迹（PTRAC）</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" }}>
            <input type="checkbox" checked={s.enabled} onChange={(e) => set({ enabled: e.target.checked })} style={{ accentColor: "var(--accent)" }} />
            启用（生成 PTRAC 卡）
          </label>
        </div>
      </div>

      {!s.enabled ? (
        <div style={{ fontSize: 11, color: "var(--text-tertiary)", padding: "8px 14px" }}>
          勾选启用后生成 PTRAC 卡（ASCII 粒子径迹文件），输出页可解析并在「3D 径迹」窗口查看。
        </div>
      ) : (
        <>
          {/* 常用 7 项平铺 */}
          <div style={{ padding: "8px 14px", display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
            <Field label="FILE">
              <select className="form-select" value={s.file} onChange={(e) => set({ file: e.target.value })} style={{ height: 28, fontSize: 12, width: 90 }}>
                {PTRAC_FILE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </Field>
            <Field label="WRITE">
              <select className="form-select" value={s.write} onChange={(e) => set({ write: e.target.value })} style={{ height: 28, fontSize: 12, width: 100 }}>
                {PTRAC_WRITE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </Field>
            <Field label="MAX">
              <input className="form-input" value={s.max} onChange={(e) => set({ max: e.target.value })} placeholder="留空=不输出" style={{ height: 28, fontSize: 12, width: 90 }} />
            </Field>
            <Field label="TYPE">
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {PTRAC_TYPE_OPTIONS.map((t) => (
                  <label key={t} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, cursor: "pointer", color: "var(--text-secondary)" }}>
                    <input type="checkbox" checked={s.types.includes(t)} onChange={() => toggleType(t)} style={{ accentColor: "var(--accent)" }} />
                    {t}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="NPS">
              <input className="form-input" value={s.nps} onChange={(e) => set({ nps: e.target.value })} placeholder="空" style={{ height: 28, fontSize: 12, width: 90 }} />
            </Field>
            <Field label="CELL">
              <input className="form-input" value={s.cell} onChange={(e) => set({ cell: e.target.value })} placeholder="空" style={{ height: 28, fontSize: 12, width: 90 }} />
            </Field>
            <Field label="SURFACE">
              <input className="form-input" value={s.surface} onChange={(e) => set({ surface: e.target.value })} placeholder="空" style={{ height: 28, fontSize: 12, width: 90 }} />
            </Field>
          </div>

          {/* 高级折叠 */}
          <div style={{ padding: "0 14px 8px", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
            <button className="btn btn-ghost btn-xs" style={{ fontSize: 11 }} onClick={() => setAdvancedOpen((v) => !v)}>
              {advancedOpen ? "▾ 高级（VALUE / EVENT）" : "▸ 高级（VALUE / EVENT）"}
            </button>
            {advancedOpen && (
              <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                <Field label="VALUE">
                  <input className="form-input" value={s.value} onChange={(e) => set({ value: e.target.value })} placeholder="tally 截止值" style={{ height: 28, fontSize: 12, width: 130 }} />
                </Field>
                <Field label="EVENT">
                  <input className="form-input" value={s.event} onChange={(e) => set({ event: e.target.value })} placeholder="src/bnk/sur/col/ter" style={{ height: 28, fontSize: 12, width: 130 }} />
                </Field>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <label style={{ fontSize: 10, color: "var(--text-tertiary)" }}>{label}</label>
      {children}
    </div>
  );
}
