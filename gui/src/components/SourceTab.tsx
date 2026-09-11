import React, { useState, useMemo } from "react";
import SourceEditDialog from "./SourceEditDialog";
import DistributionEditor from "./DistributionEditor";
import SswSsrForm from "./SswSsrForm";
import DocViewer from "./DocViewer";
import { useDeck } from "../utils/DeckContext";
import type { DistEntry, SourceItem } from "../utils/DeckContext";
import { sourceDemoSample } from "../utils/api";
import { localToDeckCells, type LocalCellRow } from "../utils/cellBridge";
import { openSourceDemo } from "../utils/windows";
import { SOURCE_TEMPLATES, fieldsForTemplate, SDEF_FIELD_META } from "../utils/sourceTemplates";
import {
  uiModeFromAdv, vocabForUi,
  parseDistributions, serializeDistributions,
  parseKsrc, serializeKsrc,
  readExtraToken, setExtraToken, SDEF_EFF_KEY,
} from "../utils/sourceAdv";
import type { KsrcPoint, UiSourceMode } from "../utils/sourceAdv";

/* 本地显示用（camelCase）；deck.sources 存 snake_case，经 deckToFixed/fixedToDeck 桥接 */
interface FixedSource {
  number: number; par: string; erg: string;
  posX: string; posY: string; posZ: string;
  wgt: string; dir_: string; cel: string; tme: string;
  vec: string; axs: string; rad: string; ext: string;
  sur: string; nrm: string; tr: string;
  ccc: string; ara: string; rate: string; prob: string;
}

const deckToFixed = (s: SourceItem): FixedSource => ({
  number: s.number, par: s.par || "", erg: s.erg || "",
  posX: s.pos_x || "", posY: s.pos_y || "", posZ: s.pos_z || "",
  wgt: s.wgt || "", dir_: s.dir_ || "", cel: s.cel || "", tme: s.tme || "",
  vec: s.vec || "", axs: s.axs || "", rad: s.rad || "", ext: s.ext || "",
  sur: s.sur || "", nrm: s.nrm || "", tr: s.tr || "",
  ccc: s.ccc || "", ara: s.ara || "", rate: s.rate || "", prob: s.prob || "",
});
const fixedToDeck = (f: FixedSource): SourceItem => ({
  number: f.number, par: f.par, erg: f.erg,
  pos_x: f.posX, pos_y: f.posY, pos_z: f.posZ,
  wgt: f.wgt, dir_: f.dir_, cel: f.cel, tme: f.tme,
  vec: f.vec, axs: f.axs, rad: f.rad, ext: f.ext,
  sur: f.sur, nrm: f.nrm, tr: f.tr,
  ccc: f.ccc, ara: f.ara, rate: f.rate, prob: f.prob,
});

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

const MODE_OPTS: { k: UiSourceMode; l: string }[] = [
  { k: "sdef", l: "SDEF 通用源" },
  { k: "surface", l: "面源 (SSW/SSR)" },
  { k: "kcode", l: "KCODE 临界源" },
  { k: "text", l: "✎ 文本模式" },
];

export default function SourceTab() {
  const { deck, patch } = useDeck();
  // deck.adv 是源项唯一权威 → 面板与全部字段都由它派生（受控），外部 AI 回显/loadDeck 换 deck 即自动跟随
  const adv: Record<string, any> = deck.adv || {};
  const mode: UiSourceMode = uiModeFromAdv(adv, deck.textMode?.sdef);
  const template = deck.sourceTemplate || "free";

  const [editSrcIdx, setEditSrcIdx] = useState<number | null>(null);
  const [editPt, setEditPt] = useState<number | null>(null);
  const [doc, setDoc] = useState<{ path: string; title: string } | null>(null);
  const [demoError, setDemoError] = useState("");
  const [demoWarning, setDemoWarning] = useState("");
  const [demoLoading, setDemoLoading] = useState(false);

  /* ── 派生视图（每次 render 从 adv/deck 重算，无本地副本）── */
  const distributions = useMemo(() => parseDistributions(adv.sdef_distributions), [adv.sdef_distributions]);
  const ksrcPoints = useMemo(() => parseKsrc(adv.ksrc_points), [adv.ksrc_points]);
  const fixedSources = useMemo(() => (deck.sources || []).map(deckToFixed), [deck.sources]);

  const setAdvField = (k: string, v: string) => {
    if (k === SDEF_EFF_KEY) {
      // sdef_eff 后端无字段 → 折叠进 adv.sdef_extra 的 EFF 记号（避免静默不发射）
      patch({ adv: { ...adv, sdef_extra: setExtraToken(adv.sdef_extra, "EFF", v) } });
    } else {
      patch({ adv: { ...adv, [k]: v } });
    }
  };
  const sdefVal = (k: string): string =>
    k === SDEF_EFF_KEY ? readExtraToken(adv.sdef_extra, "EFF") : adv[k] || "";
  const writeDistributions = (list: DistEntry[]) =>
    patch({ adv: { ...adv, sdef_distributions: serializeDistributions(list) } });
  const writeKsrc = (next: KsrcPoint[]) =>
    patch({ adv: { ...adv, ksrc_points: serializeKsrc(next) } });
  const writeSources = (next: SourceItem[]) => patch({ sources: next });

  /* ── 模式切换：判别量写回 adv.source_mode（规范词汇）；✎文本写 textMode.sdef ── */
  const pickMode = (k: Exclude<UiSourceMode, "text">) =>
    patch({
      adv: { ...adv, source_mode: vocabForUi(k) },
      rawOverrides: { ...deck.rawOverrides, sdef: "" },
      textMode: { ...deck.textMode, sdef: false },
    });
  const pickText = () => patch({ textMode: { ...deck.textMode, sdef: true } });

  const setTemplate = (t: string) => patch({ sourceTemplate: t as any });

  /* ── 演示源：抽样校验（有错就地报，不开窗）→ 写桥开窗 ──
   *
   * ⚠️ 栅元必须先变成后端认的格式：`deck.cells` 是 CellRow 判别联合（`{kind:"cell",
   * cell:{...}}`），而 `/api/source-demo-sample` 的 `_prepare_source_geometry` 与
   * `/api/preview-3d` 的 `build_cells_data` 都读**扁平** `{number, material, surface_expr, ...}`
   * （source-demo 的 `surface_expr` 是 CEL/SUR 抽样判定几何的唯一来源；preview-3d 用它建外壳 STL）。
   * 此前这里只传了 `{num, mat, comment}`（`SourceTab.tsx:132`）且原样传 `deck.cells`，
   * 两者都会让 `expr` 为空 → 全部栅元被跳过 → **外壳 STL 空 + 粒子全堆原点**（"一坨"）。
   * 修法与 `Preview3D.tsx:679-681` 同口径。
   */
  const demoCellsForBackend = () =>
    localToDeckCells(((deck.cells || []) as LocalCellRow[])).map((r: any) => {
      const c = r?.kind === "cell" ? r.cell : r;
      return {
        number: parseInt(c?.number) || 0,
        material: c?.material ?? "",
        density: c?.density ?? "",
        surface_expr: c?.surface_expr ?? "",
        imp_n: c?.imp_n ?? "", imp_p: c?.imp_p ?? "", imp_e: c?.imp_e ?? "",
        u: c?.u ?? "", fill: c?.fill ?? "", lat: c?.lat ?? "",
        trcl: c?.trcl ?? "", render: c?.render !== false, fill_grid: c?.fill_grid ?? "",
      };
    });

  const handleDemoSource = async () => {
    setDemoError("");
    setDemoWarning("");
    setDemoLoading(true);
    const cellsForBackend = demoCellsForBackend();
    // ⚠️ 位置未配置时不静默演示：后端 `_position` 在无 SUR/CEL/RAD/EXT/D 引用时会兜底
    // `return (0.0, 0.0, 0.0)`，500 个粒子全叠在原点 → 视觉上就是"一坨"（2026-09-10 用户实测）。
    // 这里就地提示，让用户先指定源的位置形态。
    const posKeys = ["sdef_sur", "sdef_cel", "sdef_pos_x", "sdef_pos_y", "sdef_pos_z",
                     "sdef_rad", "sdef_ext"];
    const hasPos = posKeys.some((k) => String((adv as any)[k] ?? "").trim() !== "");
    if (!hasPos) {
      setDemoError("未指定源的位置：请填 SUR（面源）/ CEL（栅元源）/ POS+RAD（球、柱）/ EXT，"
        + "或把 POS 设为 Dn 分布。否则全部粒子会叠在原点，看不到源的形状。");
      setDemoLoading(false);
      return;
    }
    try {
      const res = await sourceDemoSample({
        sdefFields: adv,
        sdefDistributions: distributions,
        surfaces: deck.surfaces || "",
        cells: cellsForBackend,
        trCards: deck.tr_cards || "",
        nParticles: 500,
      });
      if (res.status === "error" || !res.particles) {
        setDemoError(res.error || "源抽样失败");
        return;
      }
      // 几何部分失败时给出警告（非阻断）：后端只在栅元解析失败时返回该字段
      const gw = (res as any).geometryWarnings as string[] | undefined;
      if (gw && gw.length) {
        setDemoWarning("部分栅元几何未能解析（" + gw.slice(0, 3).join("；")
          + (gw.length > 3 ? " 等 " + gw.length + " 项" : "") + "），相关源形状可能不准。");
      }
      await openSourceDemo({
        cells: cellsForBackend,
        surfaces: deck.surfaces || "",
        trCards: deck.tr_cards || "",
        particles: res.particles,
        energyRange: res.energyRange || { min: 0, max: 1 },
        sdefFields: adv,
        sdefDistributions: distributions,
      });
    } catch (e: any) {
      setDemoError(String(e?.message || e));
    } finally {
      setDemoLoading(false);
    }
  };

  // Dn 自动检测：sdef 字段含 D{n} → 自动建分布条目（写 adv.sdef_distributions）
  const handleSdefChange = (k: string, v: string) => {
    setAdvField(k, v);
    const m = v.match(/D(\d+)/);
    if (m) {
      const id = parseInt(m[1]);
      if (!distributions.some((d) => d.id === id)) {
        const param = SDEF_FIELD_META.find((f) => f.key === k)?.keyword || "";
        writeDistributions([...distributions, {
          id, paramRef: param, auto: true,
          // 默认规范形态 + SI 直方图省略（无字母，MCNP 缺省 H；不默认 L）
          si: { type: "", values: ["", ""] },
          sp: { type: "D", values: [], fnCode: "", fnParams: [] },
          sb: null, ds: null,
        }]);
      }
    }
  };

  /* ── 多点源（deck.sources 列表，snake_case）── */
  const addFixedSource = () => {
    const cur = deck.sources || [];
    const n = cur.length > 0 ? Math.max(...cur.map((s) => s.number)) + 1 : 1;
    writeSources([...cur, fixedToDeck({
      number: n, par: "", erg: "", posX: "", posY: "", posZ: "",
      wgt: "", dir_: "", cel: "", tme: "", vec: "", axs: "", rad: "", ext: "",
      sur: "", nrm: "", tr: "", ccc: "", ara: "", rate: "", prob: "",
    })]);
  };
  const deleteFixedSource = (idx: number) =>
    writeSources((deck.sources || []).filter((_, i) => i !== idx));
  const saveFixedSource = (idx: number, data: any) => {
    const cur = deck.sources || [];
    const c = [...cur]; c[idx] = fixedToDeck(data as FixedSource); writeSources(c);
    setEditSrcIdx(null);
  };

  /* ── KSRC 行编辑（受控写 adv.ksrc_points）── */
  const updKsrc = (i: number, axis: "x" | "y" | "z", val: string) => {
    writeKsrc(ksrcPoints.map((p, idx) => (idx === i ? { ...p, [axis]: val } : p)));
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
          onSave={(d: any) => {
            const c = [...ksrcPoints]; c[editPt] = d as KsrcPoint; writeKsrc(c); setEditPt(null);
          }}
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
          {MODE_OPTS.map((opt) => (
            <button key={opt.k} className={"btn btn-sm " + (mode === opt.k ? "btn-primary" : "btn-ghost")}
              onClick={() => (opt.k === "text" ? pickText() : pickMode(opt.k as Exclude<UiSourceMode, "text">))}>
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
            <button className="btn btn-ghost btn-xs" onClick={() => {
              patch({
                rawOverrides: { ...deck.rawOverrides, sdef: "" },
                textMode: { ...deck.textMode, sdef: false },
              });
            }} style={{ whiteSpace: "nowrap" }}>← 返回表单</button>
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
          {/* 演示源入口 */}
          <div className="glass-card">
            <div className="card-header">
              <span className="card-title" style={{ flexShrink: 0 }}>源粒子演示</span>
              <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
                <button className="btn btn-primary btn-sm" onClick={handleDemoSource} disabled={demoLoading}>
                  {demoLoading ? "抽样中…" : "🎬 演示源"}
                </button>
              </div>
            </div>
            {demoError && (
              <div style={{ marginTop: 6, padding: "6px 10px", background: "rgba(229,57,53,0.12)", borderRadius: 6, color: "#e53935", fontSize: 12 }}>
                {demoError}
              </div>
            )}
            {!demoError && demoWarning && (
              <div style={{ marginTop: 6, padding: "6px 10px", background: "rgba(249,168,37,0.12)", borderRadius: 6, color: "#f9a825", fontSize: 12 }}>
                ⚠ {demoWarning}
              </div>
            )}
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 6 }}>
              按当前 SDEF + SI/SP/SB/DS 抽样 500 个粒子，在 3D 窗口显示源的位置分布与发射方向（按粒子类型着色、能量深浅）
            </div>
          </div>

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
                  onClick={() => setTemplate(t.id)}>
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
                      value={sdefVal(f.key)}
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
                          value={sdefVal(f.key)}
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
                writeDistributions([...distributions, {
                  id: nextId, paramRef: "", auto: false,
                  // 默认规范形态 + SI 直方图省略（无字母；新建默认=规范形态）
                  si: { type: "", values: ["", ""] },
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
                  onChange={(nd) => { const c = [...distributions]; c[i] = nd; writeDistributions(c); }}
                  onDelete={() => writeDistributions(distributions.filter((_, j) => j !== i))} />
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
            ssw={{ surf: adv.ssw_surf || "", sym: adv.ssw_sym || "", pty: adv.ssw_pty || "", cel: adv.ssw_cel || "" }}
            ssr={{
              surf: adv.ssr_surf || "", mode: adv.ssr_mode || "", cel: adv.ssr_cel || "", pty: adv.ssr_pty || "",
              col: adv.ssr_col || "", wgt: adv.ssr_wgt || "", tr: adv.ssr_tr || "", psc: adv.ssr_psc || "",
            }}
            onChangeSsw={(s) => patch({ adv: {
              ...adv,
              ssw_surf: s.surf || "", ssw_sym: s.sym || "", ssw_pty: s.pty || "", ssw_cel: s.cel || "",
            } })}
            onChangeSsr={(s) => patch({ adv: {
              ...adv,
              ssr_surf: s.surf || "", ssr_mode: s.mode || "", ssr_cel: s.cel || "", ssr_pty: s.pty || "",
              ssr_col: s.col || "", ssr_wgt: s.wgt || "", ssr_tr: s.tr || "", ssr_psc: s.psc || "",
            } })} />
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
                    value={adv[id] || ""}
                    onChange={e => setAdvField(id, e.target.value)}
                    style={{ height: 30, fontSize: 11 }} />
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--text-secondary)" }}>
                <input type="checkbox" checked={!!adv.hsrc_enabled}
                  onChange={e => patch({ adv: { ...adv, hsrc_enabled: e.target.checked } })} />
                HSRC 香农熵网格
              </label>
              <input className="form-input" style={{ flex: 1, height: 28, fontSize: 11 }} placeholder="nx xmin xmax ny ymin ymax nz zmin zmax，如 10 -100 100 10 -100 100 10 -100 100"
                value={adv.hsrc_text || ""}
                onChange={e => setAdvField("hsrc_text", e.target.value)} />
            </div>
          </div>
          <div className="glass-card">
            <div className="card-header">
              <span className="card-title">KSRC 源点</span>
              <button className="btn btn-success btn-xs" onClick={() => writeKsrc([...ksrcPoints, { x: "0", y: "0", z: "0" }])}>+ 添加点</button>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>X</th><th>Y</th><th>Z</th><th>操作</th></tr></thead>
                <tbody>
                  {ksrcPoints.map((p, i) => (
                    <tr key={i}>
                      <td><input className="form-input" value={p.x} onChange={e => updKsrc(i, "x", e.target.value)} style={{ height: 28, fontSize: 12 }} /></td>
                      <td><input className="form-input" value={p.y} onChange={e => updKsrc(i, "y", e.target.value)} style={{ height: 28, fontSize: 12 }} /></td>
                      <td><input className="form-input" value={p.z} onChange={e => updKsrc(i, "z", e.target.value)} style={{ height: 28, fontSize: 12 }} /></td>
                      <td>
                        <button className="btn btn-ghost btn-xs" onClick={() => setEditPt(i)}>✎</button>
                        <button className="btn btn-danger btn-xs" onClick={() => writeKsrc(ksrcPoints.filter((_, j) => j !== i))}>×</button>
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
