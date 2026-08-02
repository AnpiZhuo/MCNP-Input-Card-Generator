import React, { useState, useEffect, useCallback } from "react";
import SourceEditDialog from "./SourceEditDialog";
import DistributionEditor from "./DistributionEditor";
import SswSsrForm from "./SswSsrForm";
import DocViewer from "./DocViewer";
import { useDeck } from "../utils/DeckContext";
import type { DistEntry, SourceItem } from "../utils/DeckContext";
import { SOURCE_TEMPLATES, fieldsForTemplate, SDEF_FIELD_META, TEMPLATE_DEFAULTS } from "../utils/sourceTemplates";
import TextModeSection from "./TextModeSection";

interface KsrcPoint { x: string; y: string; z: string }
/* 本地固定源（camelCase，推送 deck 时转 snake_case） */
interface FixedSource {
  number: number; par: string; erg: string;
  posX: string; posY: string; posZ: string;
  wgt: string; dir_: string; cel: string; tme: string;
  vec: string; axs: string; rad: string; ext: string;
  sur: string; nrm: string; tr: string;
  ccc: string; ara: string; rate: string; prob: string;
}

const PAR_LABELS: Record<string, string> = {
  "1": "1-中子", "2": "2-光子", "3": "3-电子",
  "H": "H-质子", "A": "A-α粒子", "S": "S-裂片",
};

const KCODE_FIELDS = [
  ["kcode_nsrc", "NSRC 每代粒子数", "如 50000"],
  ["kcode_rkk", "RKK 初始 keff", "如 1.0"],
  ["kcode_ikz", "IKZ 非活跃代数", "如 50"],
  ["kcode_kct", "KCT 总代数", "如 200"],
  ["kcode_msrk", "MSRK 源点存储", "可选"],
  ["kcode_knrm", "KNRM 归一", "0/1"],
  ["kcode_mrkp", "MRKP 保存周期", "可选"],
  ["kcode_kc8", "KC8", "0/1"],
];

export default function SourceTab() {
  const { deck, patch } = useDeck();
  // fixed 模式已并入 SDEF 多点源模板
  const [mode, setMode] = useState<"sdef" | "surface" | "kcode" | "text">(
    deck.sourceMode === "surface" ? "surface" : deck.sourceMode === "kcode" ? "kcode" : "sdef"
  );
  const template = deck.sourceTemplate || "free";
  const sdefFields = deck.sdefFields || {};
  const distributions = deck.distributions || [];

  const [fixedSources, setFixedSources] = useState<FixedSource[]>([]);
  const [editSrcIdx, setEditSrcIdx] = useState<number | null>(null);
  const [ksrcPoints, setKsrc] = useState<KsrcPoint[]>([]);
  const [editPt, setEditPt] = useState<number | null>(null);
  const [doc, setDoc] = useState<{ path: string; title: string } | null>(null);

  // 旧 fixed 模式迁移 → SDEF 多点源模板（源模式已并入 SDEF）
  useEffect(() => {
    if (deck.sourceMode === "fixed" && deck.sources?.length) {
      patch({ sourceMode: "sdef", sourceTemplate: "multi_point" });
    }
  }, [deck.sourceMode, deck.sources]);

  const setSdefField = (k: string, v: string) => patch({ sdefFields: { ...sdefFields, [k]: v } });
  const setDistributions = (d: DistEntry[]) => patch({ distributions: d });
  const setTemplate = (t: string) => { patch({ sourceTemplate: t as any, sourceMode: "sdef" }); setMode("sdef"); };

  // 导入时同步 sources / ksrc（deck snake_case → 本地 camelCase）
  useEffect(() => {
    if (deck.sources?.length && !fixedSources.length) {
      setFixedSources(deck.sources.map(s => ({
        number: s.number, par: s.par, erg: s.erg,
        posX: s.pos_x || "", posY: s.pos_y || "", posZ: s.pos_z || "",
        wgt: s.wgt, dir_: s.dir_ || "", cel: s.cel || "", tme: s.tme || "",
        vec: s.vec || "", axs: s.axs || "", rad: s.rad || "", ext: s.ext || "",
        sur: s.sur || "", nrm: s.nrm || "", tr: s.tr || "",
        ccc: s.ccc || "", ara: s.ara || "", rate: s.rate || "", prob: s.prob || "",
      } as any)));
    }
  }, [deck.sources]);
  useEffect(() => {
    if (deck.ksrcPoints) { try { setKsrc(JSON.parse(deck.ksrcPoints)); } catch {} }
  }, [deck.ksrcPoints]);

  // Dn 自动检测：sdef 字段含 D{n} → 自动建分布条目
  const handleSdefChange = (k: string, v: string) => {
    setSdefField(k, v);
    const m = v.match(/D(\d+)/);
    if (m) {
      const id = parseInt(m[1]);
      if (!distributions.some(d => d.id === id)) {
        const param = SDEF_FIELD_META.find(f => f.key === k)?.keyword || "";
        setDistributions([...distributions, {
          id, paramRef: param, auto: true,
          si: { type: "L", values: ["", ""] },
          sp: { type: "D", values: [], fnCode: "", fnParams: [] },
          sb: null, ds: null,
        }]);
      }
    }
  };

  const addFixedSource = () => {
    const n = fixedSources.length > 0 ? Math.max(...fixedSources.map(s => s.number)) + 1 : 1;
    setFixedSources([...fixedSources, {
      number: n, par: "", erg: "", posX: "", posY: "", posZ: "",
      wgt: "", dir_: "", cel: "", tme: "", vec: "", axs: "", rad: "", ext: "",
      sur: "", nrm: "", tr: "", ccc: "", ara: "", rate: "", prob: "",
    } as any]);
  };
  const deleteFixedSource = (idx: number) => setFixedSources(fixedSources.filter((_, i) => i !== idx));
  const saveFixedSource = (idx: number, data: any) => {
    const c = [...fixedSources]; c[idx] = data; setFixedSources(c); setEditSrcIdx(null);
  };
  // 本地 camelCase → deck snake_case（后端 _sources_from_list 读 snake_case）
  useEffect(() => {
    if (fixedSources.length) {
      patch({ sources: fixedSources.map(s => ({
        number: s.number, par: s.par, erg: s.erg,
        pos_x: s.posX, pos_y: s.posY, pos_z: s.posZ,
        wgt: s.wgt, dir_: s.dir_, cel: s.cel, tme: s.tme,
        vec: s.vec, axs: s.axs, rad: s.rad, ext: s.ext,
        sur: s.sur, nrm: s.nrm, tr: s.tr,
        ccc: s.ccc, ara: s.ara, rate: s.rate, prob: s.prob,
      })) });
    }
  }, [fixedSources]);
  useEffect(() => { patch({ ksrcPoints: JSON.stringify(ksrcPoints) }); }, [ksrcPoints]);

  // 模板切换默认值（对照说明书：体积源各轴独立分布、能谱源用内置函数）
  const applyTemplate = (id: string) => {
    setTemplate(id);
    const def = TEMPLATE_DEFAULTS[id];
    if (def?.sdefVals) { patch({ sdefFields: { ...sdefFields, ...def.sdefVals } }); }
    if (def?.dists?.length) {
      let maxId = distributions.reduce((m, d) => Math.max(m, d.id), 0) || 0;
      const newDists = [...distributions];
      const fieldPatch: Record<string, string> = {};
      for (const td of def.dists) {
        maxId++;
        const nd: DistEntry = {
          id: maxId, paramRef: SDEF_FIELD_META.find(f => f.key === td.paramKey)?.keyword || td.paramKey, auto: false,
          si: { type: td.siType, values: [...td.siValues] },
          sp: { type: td.spType, values: [...(td.spValues || [])], fnCode: td.fnCode || "", fnParams: [...(td.fnParams || [])] },
          sb: null, ds: null,
        };
        newDists.push(nd);
        fieldPatch[td.paramKey] = "D" + maxId;
      }
      setDistributions(newDists);
      patch({ sdefFields: { ...sdefFields, ...fieldPatch } });
    }
  };

  const tplFields = fieldsForTemplate(template);

  return (
    <>
      {editSrcIdx !== null && (
        <SourceEditDialog point={fixedSources[editSrcIdx] as any} index={editSrcIdx} isKsrc={false}
          onSave={(d) => saveFixedSource(editSrcIdx, d)} onClose={() => setEditSrcIdx(null)} />
      )}
      {editPt !== null && (
        <SourceEditDialog point={ksrcPoints[editPt]} index={editPt} isKsrc={true}
          onSave={(d: any) => { const c = [...ksrcPoints]; c[editPt] = d; setKsrc(c); setEditPt(null); }}
          onClose={() => setEditPt(null)} />
      )}

      {/* 模式选择 */}
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title" style={{ flexShrink: 0 }}>源项模式</span>
          <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
            <button className="btn btn-ghost btn-xs" onClick={() => setDoc({ path: "/docs/源分布卡说明.md", title: "源分布卡说明" })}>📖 源参考</button>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[
            { k: "sdef", l: "SDEF 通用源" },
            { k: "surface", l: "面源 (SSW/SSR)" },
            { k: "kcode", l: "KCODE 临界源" },
            { k: "text", l: "✎ 文本模式" },
          ].map((opt) => (
            <button key={opt.k} className={"btn btn-sm " + (mode === opt.k ? "btn-primary" : "btn-ghost")}
              onClick={() => {
                setMode(opt.k as any);
                // 切回表单模式时清掉 raw_overrides.sdef，让表单接管
                if (opt.k !== "text") patch({ sourceMode: opt.k, rawOverrides: { ...deck.rawOverrides, sdef: "" } });
              }}>
              {opt.l}
            </button>
          ))}
        </div>
      </div>

      {/* ═══ 文本模式：整页手动输入源卡 ═══ */}
      {mode === "text" && (
        <div className="glass-card">
          <div className="card-header">
            <span className="card-title" style={{ flexShrink: 0 }}>源卡文本模式</span>
            <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
              <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>手动输入整个源段，生成时原样输出（SDEF/SI/SP/SB/DS/KCODE/KSRC/SSW/SSR）</span>
            </div>
            <button className="btn btn-ghost btn-xs" onClick={() => { setMode("sdef"); patch({ rawOverrides: { ...deck.rawOverrides, sdef: "" } }); }} style={{ whiteSpace: "nowrap" }}>← 返回表单</button>
          </div>
          <textarea className="form-input" value={deck.rawOverrides?.sdef || ""}
            onChange={e => patch({ rawOverrides: { ...deck.rawOverrides, sdef: e.target.value } })}
            style={{ width: "100%", minHeight: 360, fontFamily: "Consolas,monospace", fontSize: 12 }}
            placeholder={"SDEF ERG=14 POS=0 0 0\nSI1 ...\nSP1 ...\n\n或：\nKCODE 10000 1.0 50 150\nKSRC 0 0 0\n\n或：\nSSW 2 3"} />
          <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 4 }}>提示：切回表单模式会清空此文本</div>
        </div>
      )}

      {/* ═══ SDEF 通用源 ═══ */}
      {mode === "sdef" && (
        <>
          {/* 模板向导 */}
          <div className="glass-card">
            <div className="card-header">
              <span className="card-title" style={{ flexShrink: 0 }}>源类型模板</span>
              <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
                <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>选一个源类型，只需填该类型需要的参数（新手友好）</span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {SOURCE_TEMPLATES.map(t => (
                <button key={t.id}
                  className={"btn btn-xs " + (template === t.id ? "btn-primary" : "btn-ghost")}
                  style={{ flexDirection: "column", alignItems: "center", height: "auto", padding: "6px 10px", gap: 2 }}
                  title={t.desc + "（对照说明书：" + t.doc + "）"}
                  onClick={() => applyTemplate(t.id)}>
                  <span style={{ fontSize: 15 }}>{t.icon}</span>
                  <span style={{ fontSize: 10 }}>{t.name}</span>
                </button>
              ))}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 8, padding: "6px 10px", background: "var(--bg-input)", borderRadius: 6, border: "1px solid var(--border-glass)" }}>
              {SOURCE_TEMPLATES.find(t => t.id === template)?.desc}（对照说明书：{SOURCE_TEMPLATES.find(t => t.id === template)?.doc}）
            </div>
          </div>

          {/* SDEF 字段（按模板过滤） */}
          {template !== "multi_point" && (
            <div className="glass-card">
              <div className="card-header"><span className="card-title">SDEF 源参数</span></div>
              <div className="form-row" style={{ flexWrap: "wrap", gap: 6 }}>
                {tplFields.map(f => (
                  <div key={f.key} className="form-group" style={{ maxWidth: f.key === "sdef_vec" || f.key === "sdef_axs" ? 160 : 100 }}>
                    <label className="form-label" style={{ fontSize: 9 }} title={f.hint}>{f.keyword} {f.label}</label>
                    <input id={f.key} className="form-input" placeholder={f.placeholder} title={f.hint}
                      value={sdefFields[f.key] || ""}
                      onChange={e => handleSdefChange(f.key, e.target.value)}
                      style={{ height: 30, fontSize: 11 }} />
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 6 }}>
                <details>
                  <summary style={{ fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" }}>额外参数 (AXS/RAD/EXT/CEL/SUR/NRM/TR/CCC/ARA/RATE)</summary>
                  <div className="form-row" style={{ flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                    {SDEF_FIELD_META.filter(f => !tplFields.some(tf => tf.key === f.key) && f.group === "extra").map(f => (
                      <div key={f.key} className="form-group" style={{ maxWidth: 120 }}>
                        <label className="form-label" style={{ fontSize: 9 }} title={f.hint}>{f.keyword} {f.label}</label>
                        <input id={f.key} className="form-input" placeholder={f.placeholder} title={f.hint}
                          value={sdefFields[f.key] || ""}
                          onChange={e => handleSdefChange(f.key, e.target.value)}
                          style={{ height: 30, fontSize: 11 }} />
                      </div>
                    ))}
                  </div>
                </details>
              </div>
            </div>
          )}

          {/* 多点源表格 */}
          {template === "multi_point" && (
            <div className="glass-card">
              <div className="card-header">
                <span className="card-title">多点源列表（自动生成 SDEF POS=D1 + SI/SP）</span>
                <button className="btn btn-success btn-sm" onClick={addFixedSource}>+ 添加源</button>
              </div>
              {fixedSources.length === 0 ? (
                <div style={{ padding: 20, textAlign: "center", color: "var(--text-tertiary)", fontSize: 13 }}>暂无源，点击"+ 添加源"</div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>源#</th><th>粒子</th><th>能量</th><th>位置</th><th>权重</th><th>概率</th><th>操作</th></tr></thead>
                    <tbody>
                      {fixedSources.map((src, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{src.number}</td>
                          <td>{PAR_LABELS[src.par] || src.par}</td>
                          <td>{src.erg}</td>
                          <td>{`${src.posX} ${src.posY} ${src.posZ}`}</td>
                          <td>{src.wgt}</td>
                          <td>{src.prob || "—"}</td>
                          <td>
                            <button className="btn btn-ghost btn-xs" onClick={() => setEditSrcIdx(i)}>✎</button>
                            <button className="btn btn-danger btn-xs" onClick={() => deleteFixedSource(i)}>×</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* 分布编辑器 */}
          <div className="glass-card">
            <div className="card-header">
              <span className="card-title">SI/SP/SB/DS 分布</span>
              <button className="btn btn-success btn-xs" onClick={() => {
                const nextId = distributions.reduce((m, d) => Math.max(m, d.id), 0) + 1 || 1;
                setDistributions([...distributions, {
                  id: nextId, paramRef: "", auto: false,
                  si: { type: "L", values: ["", ""] },
                  sp: { type: "D", values: [""], fnCode: "", fnParams: [] },
                  sb: null, ds: null,
                }]);
              }}>+ 添加分布</button>
            </div>
            {distributions.length === 0 ? (
              <div style={{ padding: 12, textAlign: "center", color: "var(--text-tertiary)", fontSize: 12 }}>
                在 SDEF 字段中输入 D1/D2/… 自动生成，或点"+ 添加分布"；支持 SI/SP/SB/DS 与内置函数（对照说明书三/四节）
              </div>
            ) : (
              distributions.map((d, i) => (
                <DistributionEditor key={d.id} entry={d}
                  onChange={(nd) => { const c = [...distributions]; c[i] = nd; setDistributions(c); }}
                  onDelete={() => setDistributions(distributions.filter((_, j) => j !== i))} />
              ))
            )}
          </div>
        </>
      )}

      {/* ═══ 面源 SSW/SSR ═══ */}
      {mode === "surface" && (
        <div className="glass-card">
          <div className="card-header"><span className="card-title">面源 (SSW/SSR)</span></div>
          <SswSsrForm
            ssw={deck.sswFields || { surf: "", sym: "", pty: "", cel: "" }}
            ssr={deck.ssrFields || { surf: "", mode: "", cel: "", pty: "", col: "", wgt: "", tr: "", psc: "" }}
            onChangeSsw={(s) => patch({ sswFields: s })}
            onChangeSsr={(s) => patch({ ssrFields: s })} />
        </div>
      )}

      {/* ═══ KCODE 临界源 ═══ */}
      {mode === "kcode" && (
        <>
          <div className="glass-card">
            <div className="card-header"><span className="card-title">KCODE 参数（对照说明书五）</span></div>
            <div className="form-row" style={{ flexWrap: "wrap", gap: 6 }}>
              {KCODE_FIELDS.map(([id, label, ph]) => (
                <div key={id} className="form-group" style={{ maxWidth: 150 }}>
                  <label className="form-label">{label}</label>
                  <input id={id} className="form-input" placeholder={ph}
                    value={(deck.kcodeFields || {})[id] || ""}
                    onChange={e => patch({ kcodeFields: { ...(deck.kcodeFields || {}), [id]: e.target.value } })}
                    style={{ height: 30, fontSize: 11 }} />
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--text-secondary)" }}>
                <input type="checkbox" checked={!!(deck.kcodeFields || {}).hsrc_enabled}
                  onChange={e => patch({ kcodeFields: { ...(deck.kcodeFields || {}), hsrc_enabled: e.target.checked ? "1" : "" } })} />
                HSRC 香农熵网格
              </label>
              <input className="form-input" style={{ flex: 1, height: 28, fontSize: 11 }} placeholder="nx xmin xmax ny ymin ymax nz zmin zmax，如 10 -100 100 10 -100 100 10 -100 100"
                value={(deck.kcodeFields || {}).hsrc_text || ""}
                onChange={e => patch({ kcodeFields: { ...(deck.kcodeFields || {}), hsrc_text: e.target.value } })} />
            </div>
          </div>
          <div className="glass-card">
            <div className="card-header">
              <span className="card-title">KSRC 源点</span>
              <button className="btn btn-success btn-xs" onClick={() => setKsrc([...ksrcPoints, { x: "0", y: "0", z: "0" }])}>+ 添加点</button>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>X</th><th>Y</th><th>Z</th><th>操作</th></tr></thead>
                <tbody>
                  {ksrcPoints.map((p, i) => (
                    <tr key={i}>
                      <td><input className="form-input" value={p.x} onChange={e => { const c = [...ksrcPoints]; c[i] = { ...c[i], x: e.target.value }; setKsrc(c); }} style={{ height: 28, fontSize: 12 }} /></td>
                      <td><input className="form-input" value={p.y} onChange={e => { const c = [...ksrcPoints]; c[i] = { ...c[i], y: e.target.value }; setKsrc(c); }} style={{ height: 28, fontSize: 12 }} /></td>
                      <td><input className="form-input" value={p.z} onChange={e => { const c = [...ksrcPoints]; c[i] = { ...c[i], z: e.target.value }; setKsrc(c); }} style={{ height: 28, fontSize: 12 }} /></td>
                      <td>
                        <button className="btn btn-ghost btn-xs" onClick={() => setEditPt(i)}>✎</button>
                        <button className="btn btn-danger btn-xs" onClick={() => setKsrc(ksrcPoints.filter((_, j) => j !== i))}>×</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
      {doc && <DocViewer path={doc.path} title={doc.title} onClose={() => setDoc(null)} />}
    </>
  );
}
