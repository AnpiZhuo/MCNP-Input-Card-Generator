import React, { useState } from "react";
import FloatingDialog from "./FloatingDialog";

interface Nuclide { zaid: string; fraction: string }
interface MaterialFormData { matNum: string; name: string; nuclides: MaterialRow[]; options: string; mtCard: string; density: string }
interface Props { matNum: string; name: string; nuclides: MaterialRow[]; density?: string; options?: string; mtCard?: string; onSave: (d: MaterialFormData) => void; onClose: () => void }

import { PRESET_CATEGORIES, type PresetItem } from "./MaterialPresets";
import type { MaterialRow } from "../utils/DeckContext";
import { useRowDrag } from "../utils/useRowDrag";

// 元素→质子数映射
const Z_EL: Record<string, string> = {};
const EL_Z: Record<string, string> = {
  H:"1", He:"2", Li:"3", Be:"4", B:"5", C:"6", N:"7", O:"8", F:"9", Ne:"10",
  Na:"11", Mg:"12", Al:"13", Si:"14", P:"15", S:"16", Cl:"17", Ar:"18",
  K:"19", Ca:"20", Sc:"21", Ti:"22", V:"23", Cr:"24", Mn:"25", Fe:"26",
  Co:"27", Ni:"28", Cu:"29", Zn:"30", Ga:"31", Ge:"32", As:"33", Se:"34",
  Br:"35", Kr:"36", Rb:"37", Sr:"38", Y:"39", Zr:"40", Nb:"41", Mo:"42",
  Tc:"43", Ru:"44", Rh:"45", Pd:"46", Ag:"47", Cd:"48", In:"49", Sn:"50",
  Sb:"51", Te:"52", I:"53", Xe:"54", Cs:"55", Ba:"56", La:"57", Ce:"58",
  Pr:"59", Nd:"60", Pm:"61", Sm:"62", Eu:"63", Gd:"64", Tb:"65", Dy:"66",
  Ho:"67", Er:"68", Tm:"69", Yb:"70", Lu:"71", Hf:"72", Ta:"73", W:"74",
  Re:"75", Os:"76", Ir:"77", Pt:"78", Au:"79", Hg:"80", Tl:"81", Pb:"82",
  Bi:"83", Po:"84", At:"85", Rn:"86", Fr:"87", Ra:"88", Ac:"89", Th:"90",
  Pa:"91", U:"92", Np:"93", Pu:"94", Am:"95", Cm:"96", Bk:"97", Cf:"98",
  Es:"99", Fm:"100",
};
for (var _k in EL_Z) Z_EL[EL_Z[_k]] = _k;

function zaidToEl(zaid: string): string {
  var z = zaid.replace(/\..*$/, "").replace(/^0+/, "");
  var znum = z.slice(0, -3) || "0";
  var mass = z.slice(-3) || "";
  var el = Z_EL[znum] || znum;
  return el + (mass ? "-" + parseInt(mass) : "");
}

function elToZaid(el: string, mass: string): string {
  var z = EL_Z[el.charAt(0).toUpperCase() + el.slice(1).toLowerCase()];
  if (!z) z = el.replace(/[^0-9]/g, "");
  if (!z || z === "") z = "0";
  return z + mass.padStart(3, "0");
}

const UP_KEY = "mcnp_user_presets";
function loadUP(): PresetItem[] { try { return JSON.parse(localStorage.getItem(UP_KEY) || "[]"); } catch { return []; } }
function saveUP(ps: PresetItem[]) { localStorage.setItem(UP_KEY, JSON.stringify(ps)); }

const s: Record<string, React.CSSProperties> = {
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", display: "block", marginBottom: 4 },
  inp: { height: 32, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none", width: "100%" },
};

async function expandFormula(formula: string): Promise<Nuclide[]> {
  const r = await fetch("http://localhost:5001/api/expand-formula", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ formula }),
  });
  const j = await r.json();
  if (j.status === "error") throw new Error(j.message);
  return j.nuclides;
}

export default function MaterialEditDialog({ matNum, name, nuclides: initial, density: initDensity, options: initOptions, mtCard: initMtCard, onSave, onClose }: Props) {
  const [userPresets, setUserPresets] = useState<PresetItem[]>(() => loadUP());
  const [mode, setMode] = useState<"manual" | "formula">(initial.length > 0 ? "manual" : "formula");
  const [nucs, setNucs] = useState<MaterialRow[]>(initial.length > 0 ? initial : [{ kind: "nuclide", zaid: "", fraction: "" }]);
  const [comment, setComment] = useState(name);
  const [options, setOptions] = useState(initOptions || "");
  const [mtCard, setMtCard] = useState(initMtCard || "");
  const [density, setDensity] = useState(initDensity || "");
  const [formulaText, setFormulaText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [parsed, setParsed] = useState<Nuclide[] | null>(null);
  const [zaidValid, setZaidValid] = useState<Record<number, boolean|null>>({});

  // 用拍平映射快速查找
  const flatPresets: Record<string, PresetItem> = {};
  for (const [, items] of PRESET_CATEGORIES) for (const item of items) flatPresets[item.key] = item;
  const handlePreset = (key: string) => {
    const p = flatPresets[key]; if (!p) return;
    setComment(p.name); setFormulaText(p.formula); setMode("formula");
    setParsed(null); parseFormula(p.formula);
    if (p.density) setDensity(p.density);  // 预设密度自动填入密度栏
  };

  const parseFormula = async (text?: string) => {
    const t = text || formulaText; if (!t.trim()) return;
    setParsing(true);
    try {
      const result = await expandFormula(t);
      setParsed(result);
      setNucs(result.map(n => ({ kind: "nuclide" as const, zaid: n.zaid, fraction: n.fraction })));
      // 验证每个解析出来的 ZAID
      const valMap: Record<number, boolean|null> = {};
      result.forEach((n: Nuclide) => {
        var zaidNum = n.zaid.replace(/\..*$/, "").replace(/^0+/, "");
        if (zaidNum) {
          var idx = result.indexOf(n);
          fetch("http://localhost:5001/api/validate-zaid?zaid=" + encodeURIComponent(zaidNum))
            .then(function(r){return r.json();})
            .then(function(j){ setZaidValid(function(p){var m={...p}; m[idx]=j.in_db; return m;}); })
            .catch(function(){});
        }
      });
    } catch (e: any) { alert("解析失败: " + e.message); }
    finally { setParsing(false); }
  };

  const addRow = () => setNucs([...nucs, { kind: "nuclide", zaid: "", fraction: "" }]);
  const delRow = (i: number) => { if (nucs.length > 1) setNucs(nucs.filter((_, j) => j !== i)); };
  // 插入一条原样条件行（#ifdef/#else/#endif/其它）
  const addRawRow = (text: string) => setNucs([...nucs, { kind: "raw", text }]);
  // 一键生成 #ifdef 名称 / #else / #endif 三行（名称用 prompt 填）
  const addConditional = () => {
    const name = window.prompt("条件名（如 ENDF7）", "ENDF7");
    if (name === null) return;
    setNucs([...nucs, { kind: "raw", text: `#ifdef ${name.trim()}` }, { kind: "raw", text: "#else" }, { kind: "raw", text: "#endif" }]);
  };
  // 拖动排序：把 from 行移到 to 行位置
  const moveRow = (from: number, to: number) => {
    if (from === to) return;
    const c = [...nucs];
    const [m] = c.splice(from, 1);
    c.splice(to, 0, m);
    setNucs(c);
  };
  const drag = useRowDrag(moveRow);

  return React.createElement(FloatingDialog, {
    title: `材料 M${matNum}`,
    onClose,
    width: 600,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
      React.createElement("button", { className: "btn btn-primary btn-sm", onClick: () => onSave({ matNum, name: comment, nuclides: (mode === "formula" && parsed ? parsed.map(n => ({ kind: "nuclide" as const, zaid: n.zaid, fraction: n.fraction })) : nucs), options, mtCard, density }) }, "保存"),
    ),
  },
    React.createElement("div", { style: { padding: 0 } },
        // 预设 + 用户预设管理
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("label", { style: s.lbl }, "预设材料"),
          React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "center" } },
            React.createElement("select", { className: "form-select", style: { height: 34, flex: 1 }, onChange: (e: React.ChangeEvent<HTMLSelectElement>) => e.target.value && handlePreset(e.target.value), value: "" },
              React.createElement("option", { value: "" }, "-- " + (PRESET_CATEGORIES.flatMap(([, items]) => items).length + userPresets.length) + " 种预设材料 --"),
              userPresets.length > 0 ? React.createElement(React.Fragment, null,
                React.createElement("optgroup", { key: "_user", label: "用户预设" }),
                userPresets.map((p, ui) => React.createElement("option", { key: p.key, value: p.key }, p.name)),
              ) : null,
              ...PRESET_CATEGORIES.flatMap(([cat, items]) => [
                React.createElement("optgroup", { key: cat, label: cat }),
                ...items.map(item => React.createElement("option", { key: item.key, value: item.key }, item.name)),
              ]),
            ),
            React.createElement("button", {
              className: "btn btn-success btn-xs",
              style: { whiteSpace: "nowrap" },
              onClick: () => {
                var nm = prompt("预设名称:", comment || "自定义材料");
                if (!nm) return;
                var key = "user_" + Date.now();
                var newPs = [...userPresets, { key: key, name: nm, formula: formulaText, desc: "", density: density || "" }];
                setUserPresets(newPs); saveUP(newPs);
              },
            }, "+ 保存"),
          ),
          // 用户预设删除
          userPresets.length > 0 ? React.createElement("div", { style: { display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 } },
            userPresets.map((p, ui) =>
              React.createElement("span", { key: p.key, style: { display: "flex", alignItems: "center", gap: 2, fontSize: 10, background: "rgba(255,255,255,0.05)", borderRadius: 4, padding: "1px 6px" } as React.CSSProperties },
                React.createElement("span", { style: { color: "var(--text-secondary)" } }, p.name),
                React.createElement("button", {
                  style: { background: "none", border: "none", color: "#e53935", cursor: "pointer", fontSize: 12, padding: "0 2px" },
                  onClick: () => {
                    var newPs = userPresets.filter(function(_, j) { return j !== ui; });
                    setUserPresets(newPs); saveUP(newPs);
                  },
                }, "×"),
              )
            ),
          ) : null,
        ),
        React.createElement("label", { style: s.lbl }, "材料名称/注释"),
        React.createElement("input", { style: { ...s.inp, marginBottom: 10 }, value: comment, onChange: (e: React.ChangeEvent<HTMLInputElement>) => setComment(e.target.value), placeholder: "如 水、不锈钢" }),
        React.createElement("label", { style: s.lbl }, "密度 (g/cm³，可选)"),
        React.createElement("input", { style: { ...s.inp, marginBottom: 10 }, value: density, onChange: (e: React.ChangeEvent<HTMLInputElement>) => setDensity(e.target.value), placeholder: "如 -1.0（负号=质量密度，正号=原子密度）" }),
        // 模式切换
        React.createElement("div", { style: { display: "flex", gap: 8, marginBottom: 10 } },
          ["manual", "formula"].map(m => React.createElement("button", {
            key: m, className: "btn btn-sm " + (mode === m ? "btn-primary" : "btn-ghost"),
            onClick: () => setMode(m as any),
          }, m === "manual" ? "手动 ZAID" : "化学式")),
        ),
        mode === "formula" ? (
          React.createElement(React.Fragment, null,
            React.createElement("label", { style: s.lbl }, "化学式（每行一个或逗号分隔，如 H2O: 1, N2: 0.8）"),
            React.createElement("textarea", {
              style: { ...s.inp, minHeight: 60, fontFamily: "Consolas,monospace", fontSize: 12, marginBottom: 8, resize: "vertical" },
              value: formulaText,
              onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => setFormulaText(e.target.value),
              placeholder: "H2O: 1\nN2: 0.8, O2: 0.2\nUO2: 1",
            }),
            React.createElement("button", {
              className: "btn btn-primary btn-sm",
              style: { marginBottom: 10 },
              onClick: () => parseFormula(),
              disabled: parsing,
            }, parsing ? "解析中..." : "解析化学式"),
            parsed && React.createElement("div", { style: { fontSize: 11, color: "var(--text-tertiary)", marginBottom: 8 } },
              `共 ${parsed.length} 个核素（含 >0.1% 天然丰度组分）`,
            ),
            parsed && React.createElement("div", { style: { maxHeight: 150, overflow: "auto", marginBottom: 8 } },
              React.createElement("table", { style: { width: "100%", fontSize: 11, borderCollapse: "collapse" } },
                React.createElement("thead", null, React.createElement("tr", null,
                  React.createElement("th", { style: { width: 16, padding: "4px 4px" } }),
                  React.createElement("th", { style: { padding: "4px 8px", textAlign: "left" } }, "ZAID"),
                  React.createElement("th", { style: { padding: "4px 8px", textAlign: "left" } }, "份额"),
                )),
                React.createElement("tbody", null, parsed.map((n, i) =>
                  React.createElement("tr", { key: i, style: { borderBottom: "1px solid rgba(255,255,255,0.03)" } },
                    React.createElement("td", { style: { padding: "3px 4px" } },
                      React.createElement("span", { style: { width: 8, height: 8, borderRadius: "50%", display: "inline-block", background: zaidValid[i] === true ? "#4caf50" : zaidValid[i] === false ? "#e53935" : "#555", verticalAlign: "middle" } }),
                    ),
                    React.createElement("td", { style: { padding: "3px 8px", fontWeight: 600 } }, n.zaid),
                    React.createElement("td", { style: { padding: "3px 8px" } }, n.fraction),
                  )
                )),
              ),
            ),
          )
        ) : (
          React.createElement(React.Fragment, null,
            React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 } },
              React.createElement("span", { style: s.lbl }, "核素组成（核素/条件行，所有行可拖动排序）"),
              React.createElement("div", { style: { display: "flex", gap: 6 } },
                React.createElement("button", { className: "btn btn-success btn-xs", onClick: addRow }, "+ 核素"),
                React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: addConditional, title: "插入 #ifdef 名称 / #else / #endif 三行" }, "# 条件"),
              ),
            ),
            ...nucs.map((nu, i) =>
              React.createElement("div", {
                key: i,
                ...drag.rowHandlers(i),
                style: { display: "flex", gap: 8, marginBottom: 6, alignItems: "center", ...drag.rowStyle(i), ...(nu.kind === "raw" ? { background: "rgba(255,255,255,0.05)", padding: "4px 8px", borderRadius: 4 } : {}) } as React.CSSProperties,
              },
                nu.kind === "raw" ? (
                  React.createElement(React.Fragment, null,
                    React.createElement("span", { style: { width: 8, height: 8, borderRadius: "50%", background: "#9c27b0", flexShrink: 0, display: "inline-block" } }),
                    React.createElement("input", { style: { ...s.inp, flex: 1, fontFamily: "Consolas,monospace" } as React.CSSProperties, value: nu.text, onChange: (e: React.ChangeEvent<HTMLInputElement>) => { const c = [...nucs]; c[i] = { kind: "raw", text: e.target.value }; setNucs(c); }, placeholder: "#ifdef ENDF7 / #else / #endif" }),
                    React.createElement("button", { className: "btn btn-danger btn-xs", onClick: () => delRow(i) }, "x"),
                  )
                ) : (
                  React.createElement(React.Fragment, null,
                    React.createElement("span", { style: { width: 8, height: 8, borderRadius: "50%", background: zaidValid[i] === true ? "#4caf50" : zaidValid[i] === false ? "#e53935" : "#555", flexShrink: 0, display: "inline-block" } as React.CSSProperties }),
                    React.createElement("span", { style: { fontSize: 9, color: "var(--text-tertiary)", minWidth: 20 } }, (i+1) + "."),
                    React.createElement("input", { style: { ...s.inp, flex: 1 } as React.CSSProperties, placeholder: "元素 (如 U, 92, H, Fe)", value: (nu.zaid.match(/^\d/) ? zaidToEl(nu.zaid).split("-")[0] : nu.zaid.split("-")[0]) || "",
                      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
                        const c = [...nucs]; var old = nu.zaid.split("-"); c[i] = { kind: "nuclide", zaid: e.target.value + "-" + (old[1] || ""), fraction: nu.fraction }; setNucs(c);
                        var el = e.target.value.trim(); var mass = (old[1] || "");
                        if (!el || !mass) { setZaidValid(function(p){var n={...p}; n[i]=null; return n;}); return; }
                        var z = elToZaid(el, mass); var idx = i;
                        fetch("http://localhost:5001/api/validate-zaid?zaid=" + encodeURIComponent(z)).then(function(r){return r.json();}).then(function(j){ setZaidValid(function(p){var n={...p}; n[idx]=j.in_db; return n;}); }).catch(function(){});
                      },
                    }),
                    React.createElement("span", { style: { color: "var(--text-tertiary)", fontSize: 11 } }, "-"),
                    React.createElement("input", { style: { ...s.inp, maxWidth: 70 } as React.CSSProperties, placeholder: "质量数", value: (nu.zaid.match(/^\d/) ? zaidToEl(nu.zaid).split("-")[1] : nu.zaid.split("-")[1]) || "",
                      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
                        const c = [...nucs]; var el = nu.zaid.split("-")[0]; c[i] = { kind: "nuclide", zaid: el + "-" + e.target.value, fraction: nu.fraction }; setNucs(c);
                        var mass = e.target.value.trim();
                        if (!el || !mass) { setZaidValid(function(p){var n={...p}; n[i]=null; return n;}); return; }
                        var z = elToZaid(el, mass); var idx = i;
                        fetch("http://localhost:5001/api/validate-zaid?zaid=" + encodeURIComponent(z)).then(function(r){return r.json();}).then(function(j){ setZaidValid(function(p){var n={...p}; n[idx]=j.in_db; return n;}); }).catch(function(){});
                      },
                    }),
                    React.createElement("input", { style: { ...s.inp, maxWidth: 90 } as React.CSSProperties, placeholder: "份额", value: nu.fraction, onChange: (e: React.ChangeEvent<HTMLInputElement>) => { const c = [...nucs]; c[i] = { kind: "nuclide", zaid: nu.zaid, fraction: e.target.value }; setNucs(c); } }),
                    React.createElement("button", { className: "btn btn-danger btn-xs", onClick: () => delRow(i) }, "x"),
                  )
                ),
              )
            ),
          )
        ),
        // 高级选项
        React.createElement("details", { style: { marginTop: 10 } },
          React.createElement("summary", { style: { fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" } }, "高级选项"),
          React.createElement("div", { style: { marginTop: 8 } },
            React.createElement("label", { style: s.lbl }, "nlib= / gas= / plib="),
            React.createElement("input", { style: { ...s.inp, marginBottom: 8 }, value: options, onChange: (e: React.ChangeEvent<HTMLInputElement>) => setOptions(e.target.value), placeholder: "例: nlib=.66c" }),
            React.createElement("label", { style: s.lbl }, "热中子 MT 卡"),
            React.createElement("input", { style: s.inp, value: mtCard, onChange: (e: React.ChangeEvent<HTMLInputElement>) => setMtCard(e.target.value), placeholder: "例: lwtr.10t" }),
          ),
        ),
      ),
  );
}
