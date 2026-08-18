import React from "react";
import type { DistEntry, SiEntry, SpEntry, SbEntry, DsEntry } from "../utils/DeckContext";
import { SI_TYPES, SP_TYPES, BUILTIN_FNS, builtinFn } from "../utils/sourceTemplates";

/* 结构化 SI/SP/SB/DS 分布编辑器（源分布卡说明.md 三/四节） */

interface Props {
  entry: DistEntry;
  refs?: string[];          // 引用此 D{n} 的 SDEF 变量名（可多个）
  onChange: (e: DistEntry) => void;
  onDelete: () => void;
}

export default function DistributionEditor({ entry, onChange, onDelete }: Props) {
  const si = entry.si || { type: "L", values: [""] };
  const sp = entry.sp || { type: "D", values: [""], fnCode: "", fnParams: [] };

  const setSi = (s: SiEntry) => onChange({ ...entry, si: s });
  const setSp = (s: SpEntry) => onChange({ ...entry, sp: s });
  const setSb = (s: SbEntry | null) => onChange({ ...entry, sb: s });
  const setDs = (s: DsEntry | null) => onChange({ ...entry, ds: s });

  const row = (vals: string[], setVals: (v: string[]) => void) =>
    React.createElement("div", { style: { display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" } },
      vals.map((v, i) =>
        React.createElement("div", { key: i, style: { display: "flex", gap: 2, alignItems: "center" } },
          React.createElement("input", {
            className: "form-input", style: { width: 72, height: 26, fontSize: 11 },
            value: v,
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
              const c = [...vals]; c[i] = e.target.value; setVals(c);
            },
          }),
          React.createElement("button", { className: "btn btn-danger btn-xs", style: { padding: "0 4px" }, onClick: () => setVals(vals.filter((_, j) => j !== i)) }, "×"),
        )
      ),
      React.createElement("button", { className: "btn btn-success btn-xs", onClick: () => setVals([...vals, ""]) }, "+"),
    );

  const secTitle = (t: string) =>
    React.createElement("div", { style: { fontSize: 10, fontWeight: 600, color: "var(--text-secondary)", margin: "6px 0 3px" } }, t);

  // 内置函数选择
  let fnSection = null;
  if (sp.fnCode) {
    const fn = builtinFn(sp.fnCode);
    const params = (fn?.params || []).map(p => p.name);
    fnSection = React.createElement("div", { style: { display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" } },
      React.createElement("span", { style: { fontSize: 11, color: "var(--text-secondary)" } }, `${fn?.name || sp.fnCode}:`),
      params.map((pn, i) =>
        React.createElement("input", {
          key: i, className: "form-input", style: { width: 64, height: 26, fontSize: 11 },
          placeholder: pn,
          value: sp.fnParams[i] || "",
          onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
            const c = [...(sp.fnParams || [])]; c[i] = e.target.value; setSp({ ...sp, fnParams: c });
          },
        })
      ),
    );
  }

  return React.createElement("div", {
    style: { border: "1px solid var(--border-glass)", borderRadius: 8, padding: "8px 10px", marginBottom: 8, background: "var(--bg-input)" },
  },
    // 头部：D{n} + 参数 + 删除
    React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 6 } },
      React.createElement("span", { style: { fontSize: 12, fontWeight: 700, color: "var(--accent-glow)", minWidth: 30 } }, `D${entry.id}`),
      React.createElement("span", { style: { flex: 1 } }),
      React.createElement("button", { className: "btn btn-danger btn-xs", onClick: onDelete, title: "删除分布" }, "×"),
    ),
    // SCn 源注释（只读展示，随条目往返保留）
    entry.sc
      ? React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)", margin: "4px 0 2px" } }, "📝 " + entry.sc)
      : null,
    // SI
    secTitle("SI 源信息"),
    React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "flex-start" } },
      React.createElement("select", {
        className: "form-select", style: { width: 84, height: 26, fontSize: 11 },
        value: si.type || "L", title: (SI_TYPES.find(t => t.v === si.type) || {}).d,
        onChange: (e: React.ChangeEvent<HTMLSelectElement>) => setSi({ ...si, type: e.target.value as SiEntry["type"] }),
      },
        SI_TYPES.map(t => React.createElement("option", { key: t.v, value: t.v, title: t.d }, `${t.v} ${t.n}`)),
      ),
      row(si.values || [""], (v) => setSi({ ...si, values: v })),
    ),
    // SP
    secTitle("SP 源概率"),
    React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" } },
      React.createElement("select", {
        className: "form-select", style: { width: 150, height: 26, fontSize: 11 },
        value: sp.fnCode ? "FN" : sp.type || "D",
        onChange: (e: React.ChangeEvent<HTMLSelectElement>) => {
          const v = e.target.value;
          if (v === "FN") setSp({ ...sp, fnCode: "-2", fnParams: [], type: "", values: [] });
          else if (v === "D" || v === "C" || v === "V") setSp({ ...sp, fnCode: "", type: v, fnParams: [] });
        },
      },
        SP_TYPES.map(t => React.createElement("option", { key: t.v, value: t.v }, `${t.v} ${t.n}`)),
        React.createElement("option", { value: "FN" }, "内置函数"),
      ),
      sp.fnCode
        ? React.createElement("select", {
            className: "form-select", style: { width: 140, height: 26, fontSize: 11 },
            value: sp.fnCode,
            onChange: (e: React.ChangeEvent<HTMLSelectElement>) => {
              const code = e.target.value;
              const fn = builtinFn(code);
              setSp({ ...sp, fnCode: code, fnParams: (fn?.params || []).map(() => "") });
            },
          },
            BUILTIN_FNS.map(f => React.createElement("option", { key: f.code, value: f.code, title: f.desc }, `${f.code} ${f.name}`)),
          )
        : null,
      sp.fnCode ? fnSection : row(sp.values || [""], (v) => setSp({ ...sp, values: v })),
    ),
    // SB（折叠）
    React.createElement("details", { style: { marginTop: 4 } },
      React.createElement("summary", { style: { fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" } }, "SB 偏倚" + (entry.sb ? " ✓" : "")),
      entry.sb
        ? React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 4 } },
            React.createElement("select", {
              className: "form-select", style: { width: 84, height: 26, fontSize: 11 },
              value: entry.sb.type,
              onChange: (e: React.ChangeEvent<HTMLSelectElement>) => setSb({ ...entry.sb, type: e.target.value as SbEntry["type"] } as SbEntry),
            },
              React.createElement("option", { value: "D" }, "D 概率"),
              React.createElement("option", { value: "-21" }, "-21 幂律"),
              React.createElement("option", { value: "-31" }, "-31 指数"),
            ),
            row(entry.sb.values || [""], (v) => setSb({ ...entry.sb, values: v } as SbEntry)),
            React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setSb(null) }, "移除"),
          )
        : React.createElement("button", { className: "btn btn-ghost btn-xs", style: { marginTop: 4 }, onClick: () => setSb({ type: "D", values: [""] }) }, "+ 添加偏倚"),
    ),
    // DS（折叠）
    React.createElement("details", { style: { marginTop: 4 } },
      React.createElement("summary", { style: { fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" } }, "DS 依赖分布" + (entry.ds ? " ✓" : "")),
      entry.ds
        ? React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 4 } },
            React.createElement("select", {
              className: "form-select", style: { width: 84, height: 26, fontSize: 11 },
              value: entry.ds.type,
              onChange: (e: React.ChangeEvent<HTMLSelectElement>) => setDs({ ...entry.ds, type: e.target.value as DsEntry["type"] } as DsEntry),
            },
              ["H", "L", "S", "T", "Q"].map(t => React.createElement("option", { key: t, value: t }, t)),
            ),
            entry.ds.type !== "T"
              ? React.createElement("input", {
                  className: "form-input", style: { width: 70, height: 26, fontSize: 11 }, placeholder: "变量 ERG",
                  value: entry.ds.param, onChange: (e: React.ChangeEvent<HTMLInputElement>) => setDs({ ...entry.ds, param: e.target.value } as DsEntry),
                })
              : null,
            React.createElement("input", {
              className: "form-input", style: { width: 110, height: 26, fontSize: 11 }, placeholder: "依赖 Dn 编号",
              value: entry.ds.distributionIds.join(" "),
              onChange: (e: React.ChangeEvent<HTMLInputElement>) => setDs({ ...entry.ds, distributionIds: e.target.value.trim().split(/\s+/) } as DsEntry),
            }),
            React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setDs(null) }, "移除"),
          )
        : React.createElement("button", { className: "btn btn-ghost btn-xs", style: { marginTop: 4 }, onClick: () => setDs({ type: "S", param: "", distributionIds: [] }) }, "+ 添加依赖"),
    ),
  );
}
