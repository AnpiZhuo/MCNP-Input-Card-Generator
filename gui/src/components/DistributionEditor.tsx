import React, { useState, useRef, useEffect } from "react";
import type { DistEntry, SiEntry, SpEntry, SbEntry, DsEntry } from "../utils/DeckContext";
import { SI_TYPES, SP_TYPES, BUILTIN_FNS, builtinFn } from "../utils/sourceTemplates";
import {
  isRawMode, switchToRaw, switchToStructured, structuredToRawLines, withStructuredEdit,
} from "../utils/distDual";

/* 结构化 SI/SP/SB/DS 分布编辑器（源分布卡说明.md 三/四节）+ v2 双形态切换。
 *
 * 形态（v2，app/generator/distributions.py schema）：
 *   - editMode="raw"（导入文件时解析产物）→ 直接形态：MCNP 原文逐字权威，可自由编辑；
 *   - editMode="structured"/缺省（新建默认）→ 规范形态：结构化表单。
 * 切换：raw⇄structured 经 distDual 互转（structuredToRawLines / rawToStructured），
 * 输出与切换前语义一致（无字母 SI 保持 type ""，绝不回填 L）。
 */

interface Props {
  entry: DistEntry;
  onChange: (e: DistEntry) => void;
  onDelete: () => void;
}

export default function DistributionEditor({ entry, onChange, onDelete }: Props) {
  const [error, setError] = useState<string>("");
  const rawMode = isRawMode(entry);

  const setEntry = (e: DistEntry) => { setError(""); onChange(e); };

  // 结构化编辑（规范形态）——任一字段变更都回 structured，并同步重建 rawText（双态一致）
  const editStructured = (patch: Partial<DistEntry>) => {
    const next = withStructuredEdit(entry, patch);
    setEntry({ ...next, rawText: structuredToRawLines(next).join("\n") });
  };
  const setSi = (s: SiEntry) => editStructured({ si: s });
  const setSp = (s: SpEntry) => editStructured({ sp: s });
  const setSb = (s: SbEntry | null) => editStructured({ sb: s });
  const setDs = (s: DsEntry | null) => editStructured({ ds: s });

  // 切到原文：用当前结构化字段规范重建 rawText，并置 raw 形态
  const goRaw = () => setEntry(switchToRaw(entry));
  // 切回表单：解析当前原文 → 结构化字段（无字母 SI → type ""），置 structured 形态
  const goForm = () => {
    try {
      setEntry(switchToStructured(entry));
    } catch (e: any) {
      setError("无法解析原文为结构化表单，请检查卡行（SI/SP/SB/DS/SCn 前缀与编号）：" + (e?.message || e));
    }
  };

  const si = entry.si || { type: "" as SiEntry["type"], values: [""] };
  const sp = entry.sp || { type: "D" as SpEntry["type"], values: [""], fnCode: "", fnParams: [] };

  // ── 原文形态（导入/直通）──
  // 每行一条卡：卡名徽标（SI/SP/…）在文本框外提示该框内容，框内是纯文本内容。
  // 导入时程序已按卡行排好；每行编辑框高度随内容自动伸缩（值多时纵向排开，不横向拉长）。
  if (rawMode) {
    const rawText = entry.rawText != null && entry.rawText !== ""
      ? entry.rawText
      : structuredToRawLines(entry).join("\n");
    const rawLines = rawText.split("\n");
    const setRawLines = (lines: string[]) =>
      setEntry({ ...entry, editMode: "raw", rawText: lines.join("\n") });

    // 拆行：前缀（SC/SI/SP/SB/DS + 编号）与内容分开；前缀只做徽标，不入文本框。
    const LEAD_RE = /^(\s*((?:SC|SI|SP|SB|DS)\d*)(?:\s+|$))([\s\S]*)$/i;
    const splitLine = (line: string) => {
      const m = LEAD_RE.exec(line);
      if (!m) return { token: "", content: line };
      return { token: m[2].toUpperCase(), content: m[3].replace(/\s+$/, "") };
    };

    const tagColor: Record<string, string> = {
      SC: "var(--text-tertiary)", SI: "var(--accent-glow)", SP: "#f59e0b",
      SB: "#a78bfa", DS: "#34d399",
    };
    const defaultLead = (kind: string) => kind + entry.id + "  ";
    const cardKinds = ["SC", "SI", "SP", "SB", "DS"] as const;
    const kindOf = (s: string) => cardKinds.find(k => s.toUpperCase().startsWith(k)) || "";

    const setContentAt = (i: number, v: string) => {
      const c = [...rawLines];
      const { token } = splitLine(c[i]);
      c[i] = token ? token + "  " + v : v;
      setRawLines(c);
    };
    const delRawLineAt = (i: number) =>
      setRawLines(rawLines.filter((_, j) => j !== i));
    const addRawLineAt = (i: number, lead: string) => {
      const c = [...rawLines]; c.splice(i + 1, 0, lead); setRawLines(c);
    };

    return (
      <div style={{ border: "1px solid var(--border-glass)", borderRadius: 8, padding: "8px 10px", marginBottom: 8, background: "var(--bg-input)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--accent-glow)", minWidth: 30 }}>D{entry.id}</span>
          <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>原文模式（已按卡行排好，可逐行编辑）</span>
          <span style={{ flex: 1 }} />
          <button className="btn btn-ghost btn-xs" onClick={goForm} title="切换为结构化表单编辑">⇄ 转表单</button>
          <button className="btn btn-danger btn-xs" onClick={onDelete} title="删除分布">×</button>
        </div>
        {error && <div style={{ fontSize: 11, color: "#f66", margin: "4px 0" }}>{error}</div>}

        {rawLines.map((line, i) => {
          const { token, content } = splitLine(line);
          const kind = kindOf(token);
          return (
            <div key={i} style={{ display: "flex", gap: 4, alignItems: "flex-start", marginTop: 4 }}>
              <span style={{ fontSize: 10, width: 20, color: "var(--text-tertiary)", textAlign: "right", flexShrink: 0, lineHeight: "20px", paddingTop: 2 }}>{i + 1}</span>
              {token ? (
                <span style={{
                  fontSize: 9, fontWeight: 700, width: 34, flexShrink: 0, marginTop: 2,
                  color: tagColor[kind] || "var(--text-secondary)", textAlign: "center", lineHeight: "20px",
                }}>{token}</span>
              ) : (
                <span style={{ width: 34, flexShrink: 0 }} />
              )}
              <AutoHeightTextarea
                value={content}
                onChange={(v) => setContentAt(i, v)}
                placeholder={token ? "内容…" : "原文行…"}
                style={{ flex: 1 }}
              />
              <button className="btn btn-ghost btn-xs" style={{ marginTop: 2 }} title="在下方插入一行"
                onClick={() => addRawLineAt(i, token ? defaultLead(kindOf(token) || "SI") : defaultLead("SI"))}>+</button>
              <button className="btn btn-danger btn-xs" style={{ marginTop: 2 }} title="删除此行"
                onClick={() => delRawLineAt(i)}>×</button>
            </div>
          );
        })}

        <div style={{ display: "flex", gap: 4, alignItems: "center", marginTop: 6, flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>＋ 添加卡：</span>
          {cardKinds.map(k => (
            <button key={k} className="btn btn-ghost btn-xs"
              onClick={() => setRawLines([...rawLines, defaultLead(k)])}>
              {k}{entry.id}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 3 }}>
          提示：左侧徽标即卡名，文本框只填内容；值多时框会自动变高排开。
          点「⇄ 转表单」可整组切到控件编辑。
        </div>
      </div>
    );
  }

  // 结构化（规范）形态
  const secTitle = (t: string) =>
    <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-secondary)", margin: "6px 0 3px" }}>{t}</div>;

  const row = (vals: string[], setVals: (v: string[]) => void) => (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(94px, 1fr))", gap: 4, alignItems: "center", flex: 1, minWidth: 0 }}>
      {vals.map((v, i) => (
        <div key={i} style={{ display: "flex", gap: 2, alignItems: "center" }}>
          <input
            className="form-input" style={{ flex: 1, minWidth: 0, width: "100%", height: 26, fontSize: 11 }}
            value={v}
            onChange={(e) => { const c = [...vals]; c[i] = e.target.value; setVals(c); }}
          />
          <button className="btn btn-danger btn-xs" style={{ padding: "0 4px" }} onClick={() => setVals(vals.filter((_, j) => j !== i))}>×</button>
        </div>
      ))}
      <button className="btn btn-success btn-xs" style={{ justifySelf: "start", minWidth: 58 }} onClick={() => setVals([...vals, ""])}>+</button>
    </div>
  );

  // 内置函数选择
  let fnSection: React.ReactNode = null;
  if (sp.fnCode) {
    const fn = builtinFn(sp.fnCode);
    const params = (fn?.params || []).map(p => p.name);
    fnSection = (
      <div style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{fn?.name || sp.fnCode}:</span>
        {params.map((pn, i) => (
          <input
            key={i} className="form-input" style={{ width: 64, height: 26, fontSize: 11 }}
            placeholder={pn}
            value={sp.fnParams[i] || ""}
            onChange={(e) => { const c = [...(sp.fnParams || [])]; c[i] = e.target.value; setSp({ ...sp, fnParams: c }); }}
          />
        ))}
      </div>
    );
  }

  return (
    <div style={{ border: "1px solid var(--border-glass)", borderRadius: 8, padding: "8px 10px", marginBottom: 8, background: "var(--bg-input)" }}>
      {/* 头部：D{n} + 参数 + 形态切换 + 删除 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--accent-glow)", minWidth: 30 }}>D{entry.id}</span>
        <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>表单模式（规范生成）</span>
        <span style={{ flex: 1 }} />
        <button className="btn btn-ghost btn-xs" onClick={goRaw} title="切换为 MCNP 原文自由编辑">⇄ 转原文</button>
        <button className="btn btn-danger btn-xs" onClick={onDelete} title="删除分布">×</button>
      </div>
      {error && <div style={{ fontSize: 11, color: "#f66", margin: "4px 0" }}>{error}</div>}
      {/* SCn 源注释（只读展示，随条目往返保留） */}
      {entry.sc
        ? <div style={{ fontSize: 11, color: "var(--text-secondary)", margin: "4px 0 2px" }}>📝 {entry.sc}</div>
        : null}
      {/* SI */}
      {secTitle("SI 源信息")}
      <div style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
        <select
          className="form-select" style={{ width: 130, height: 26, fontSize: 11 }}
          value={si.type || ""} title={(SI_TYPES.find(t => t.v === si.type) || {}).d}
          onChange={(e) => setSi({ ...si, type: e.target.value as SiEntry["type"] })}
        >
          {SI_TYPES.map(t => <option key={t.v} value={t.v} title={t.d}>{t.n}</option>)}
        </select>
        {row(si.values && si.values.length ? si.values : [""], (v) => setSi({ ...si, values: v }))}
      </div>
      {/* SP */}
      {secTitle("SP 源概率")}
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <select
          className="form-select" style={{ width: 150, height: 26, fontSize: 11 }}
          value={sp.fnCode ? "FN" : sp.type || "D"}
          onChange={(e) => {
            const v = e.target.value;
            if (v === "FN") setSp({ ...sp, fnCode: "-2", fnParams: [], type: "", values: [] });
            else if (v === "D" || v === "C" || v === "V") setSp({ ...sp, fnCode: "", type: v, fnParams: [] });
            else if (v === "") setSp({ ...sp, fnCode: "", type: "", fnParams: [] });
          }}
        >
          {SP_TYPES.map(t => <option key={t.v} value={t.v}>{t.n}</option>)}
          <option value="FN">内置函数</option>
        </select>
        {sp.fnCode ? (
          <>
            <select
              className="form-select" style={{ width: 140, height: 26, fontSize: 11 }}
              value={sp.fnCode}
              onChange={(e) => {
                const code = e.target.value;
                const fn = builtinFn(code);
                setSp({ ...sp, fnCode: code, fnParams: (fn?.params || []).map(() => "") });
              }}
            >
              {BUILTIN_FNS.map(f => <option key={f.code} value={f.code} title={f.desc}>{`${f.code} ${f.name}`}</option>)}
            </select>
            {fnSection}
          </>
        ) : row(sp.values && sp.values.length ? sp.values : [""], (v) => setSp({ ...sp, values: v }))}
      </div>
      {/* SB（折叠） */}
      <details style={{ marginTop: 4 }}>
        <summary style={{ fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" }}>SB 偏倚{entry.sb ? " ✓" : ""}</summary>
        {entry.sb ? (
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 4 }}>
            <select
              className="form-select" style={{ width: 84, height: 26, fontSize: 11 }}
              value={entry.sb.type}
              onChange={(e) => setSb({ ...entry.sb, type: e.target.value as SbEntry["type"] } as SbEntry)}
            >
              <option value="D">D 概率</option>
              <option value="-21">-21 幂律</option>
              <option value="-31">-31 指数</option>
            </select>
            {row(entry.sb.values || [""], (v) => setSb({ ...entry.sb, values: v } as SbEntry))}
            <button className="btn btn-ghost btn-xs" onClick={() => setSb(null)}>移除</button>
          </div>
        ) : <button className="btn btn-ghost btn-xs" style={{ marginTop: 4 }} onClick={() => setSb({ type: "D", values: [""] })}>+ 添加偏倚</button>}
      </details>
      {/* DS（折叠） */}
      <details style={{ marginTop: 4 }}>
        <summary style={{ fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" }}>DS 依赖分布{entry.ds ? " ✓" : ""}</summary>
        {entry.ds ? (
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 4 }}>
            <select
              className="form-select" style={{ width: 84, height: 26, fontSize: 11 }}
              value={entry.ds.type}
              onChange={(e) => setDs({ ...entry.ds, type: e.target.value as DsEntry["type"] } as DsEntry)}
            >
              {["H", "L", "S", "T", "Q"].map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            {entry.ds.type !== "T" ? (
              <input
                className="form-input" style={{ width: 70, height: 26, fontSize: 11 }} placeholder="变量 ERG"
                value={entry.ds.param} onChange={(e) => setDs({ ...entry.ds, param: e.target.value } as DsEntry)}
              />
            ) : null}
            <input
              className="form-input" style={{ width: 110, height: 26, fontSize: 11 }} placeholder="依赖 Dn 编号"
              value={entry.ds.distributionIds.join(" ")}
              onChange={(e) => setDs({ ...entry.ds, distributionIds: e.target.value.trim().split(/\s+/) } as DsEntry)}
            />
            <button className="btn btn-ghost btn-xs" onClick={() => setDs(null)}>移除</button>
          </div>
        ) : <button className="btn btn-ghost btn-xs" style={{ marginTop: 4 }} onClick={() => setDs({ type: "S", param: "", distributionIds: [] })}>+ 添加依赖</button>}
      </details>
    </div>
  );
}

/* 自动增高 textarea：内容多行/超长自动撑高（不横向拉长、无固定矮框）；
 * 单行短内容时保持一行高。 */
function AutoHeightTextarea(props: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }, [props.value]);
  return (
    <textarea
      ref={ref}
      className="form-input" spellCheck={false}
      value={props.value}
      placeholder={props.placeholder}
      onChange={(e) => props.onChange(e.target.value)}
      style={{
        flex: 1, minWidth: 0,
        fontFamily: "Consolas,monospace", fontSize: 11,
        lineHeight: 1.5, resize: "none", overflow: "hidden",
        ...(props.style || {}),
      }}
    />
  );
}
