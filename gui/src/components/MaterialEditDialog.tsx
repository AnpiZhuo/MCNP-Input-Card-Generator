import React, { useState, useEffect } from "react";
import FloatingDialog from "./FloatingDialog";

interface Nuclide { zaid: string; fraction: string }
interface MaterialFormData { matNum: string; name: string; nuclides: MaterialRow[]; options: string; mtCard: string; density: string }
interface Props { matNum: string; name: string; nuclides: MaterialRow[]; density?: string; options?: string; mtCard?: string; onSave: (d: MaterialFormData) => void; onClose: () => void }

import { PRESET_CATEGORIES, filterPresets, type PresetItem } from "./MaterialPresets";
import type { MaterialRow } from "../utils/DeckContext";
import { useRowDrag } from "../utils/useRowDrag";
import { apiUrl } from "../utils/api";

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

/**
 * 把任意 ZAID 拆成 { el, mass }，兼容三种形态：
 *   数值 ZAID（导入/展开，如 26057、26057.50c）→ { el:"Fe", mass:"57" }
 *   自然元素（6000，质量位 AAA=000）→ { el:"C", mass:"" }
 *   手写 "元素-质量数"（如 Fe-57、Fe-57.50c）→ { el:"Fe", mass:"57" }
 */
export function splitZaid(zaid: string): { el: string; mass: string } {
  if (!zaid) return { el: "", mass: "" };
  var dash = zaid.split("-");
  if (dash.length >= 2 && !/^\d+$/.test(dash[0])) {
    // "Fe-57" 形态：元素段含字母，质量段取第二段
    return { el: dash[0], mass: dash[1].split(".")[0] || "" };
  }
  // 数值形态（26057 / 26057.50c / 6000）
  var num = zaid.replace(/\..*$/, "").replace(/^0+/, "");
  var znum = num.slice(0, -3) || "";
  var mass = num.slice(-3) || "";
  var parsed = parseInt(mass, 10);
  return { el: Z_EL[znum] || "", mass: parsed ? String(parsed) : "" };
}

/**
 * 由 { 元素, 质量数 } 组装数值 ZAID（对齐旧 elToZaid 语义）：
 *   合法符号（Fe）→ 质子数 + 三位质量数（26 + 057 = 26057）；
 *   数字元素（92）→ 原样作质子数（92235）；非法元素 → 0 兜底。
 *   质量数为空 → 000（自然元素）。
 */
export function buildZaid(el: string, mass: string): string {
  var z = EL_Z[el.charAt(0).toUpperCase() + el.slice(1).toLowerCase()];
  if (!z) z = el.replace(/[^0-9]/g, "");
  if (!z || z === "") z = "0";
  return z + (mass || "").trim().padStart(3, "0");
}

/** 由 { 元素, 质量数 } 草稿解析数值 ZAID；元素为空 → null（不提交，保留草稿继续编辑） */
export function resolveZaid(ed: { el: string; mass: string }): string | null {
  var el = ed.el.trim();
  if (!el) return null;
  return buildZaid(el, ed.mass);
}

/**
 * 剥 ZAID 截面库后缀（所见即所得：导入时在【数据层】剥掉，而不是只剥显示层）。
 * 规则：表单只表示 元素+质量数；后缀一律丢弃（用户手填截面库走材料卡「其他」框 nlib=）。
 */
export function stripZaidSuffix(zaid: string): string {
  if (!zaid) return zaid;
  var i = zaid.indexOf(".");
  return i >= 0 ? zaid.slice(0, i) : zaid;
}

/**
 * 导入材料归一化：核素行 zaid 剥后缀（.50d/.40c/.60c → 裸 ZAID），
 * raw 行（#ifdef 等）原样；rows/nuclides 两个别名键同步归一。
 * 保证「表单里看到什么，生成就出什么」。
 */
export function normalizeImportedMaterials(materials: any[]): any[] {
  return (materials || []).map((m: any) => {
    const out: any = { ...m };
    for (const key of ["rows", "nuclides"]) {
      if (Array.isArray(m[key])) {
        out[key] = m[key].map((r: any) =>
          r && r.kind === "nuclide" && typeof r.zaid === "string"
            ? { ...r, zaid: stripZaidSuffix(r.zaid) }
            : r);
      }
    }
    return out;
  });
}

/** 化学式份额模式：weight=质量份额（负号），atomic=原子份额（正号） */
export type ShareMode = "weight" | "atomic";
/** 全部合法份额模式（UI 切换与测试穷举共用） */
export const SHARE_MODES: ShareMode[] = ["weight", "atomic"];
/** MCNP 正负号约定（负号=质量份额，正号=原子份额） */
export const SIGN_CONVENTION_NOTE = "MCNP 负号=质量份额，正号=原子份额";
/** 质量/原子两种份额的含义说明 */
export const SHARE_CONVERSION_NOTE = "质量份额按各核素质量占比；原子份额按原子数占比";
/** 份额模式 → 后端 is_weight（body JSON 布尔，缺省 true=质量份额→负号） */
export function shareModeToIsWeight(mode: ShareMode): boolean {
  return mode === "weight";
}
/** 份额模式显示名 */
export function shareModeLabel(mode: ShareMode): string {
  return mode === "weight" ? "质量份额" : "原子份额";
}

const UP_KEY = "mcnp_user_presets";
function loadUP(): PresetItem[] { try { return JSON.parse(localStorage.getItem(UP_KEY) || "[]"); } catch { return []; } }
function saveUP(ps: PresetItem[]) { localStorage.setItem(UP_KEY, JSON.stringify(ps)); }

const s: Record<string, React.CSSProperties> = {
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", display: "block", marginBottom: 4 },
  inp: { height: 32, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none", width: "100%" },
};

async function expandFormula(formula: string, isWeight: boolean = true): Promise<Nuclide[]> {
  const r = await fetch(apiUrl("/api/expand-formula"), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ formula, is_weight: isWeight }),
  });
  const j = await r.json();
  if (j.status === "error") throw new Error(j.message);
  return j.nuclides;
}

export default function MaterialEditDialog({ matNum, name, nuclides: initial, density: initDensity, options: initOptions, mtCard: initMtCard, onSave, onClose }: Props) {
  const [userPresets, setUserPresets] = useState<PresetItem[]>(() => loadUP());
  const [presetSearch, setPresetSearch] = useState("");
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
  const [shareMode, setShareMode] = useState<ShareMode>("weight");  // 化学式份额模式：质量(负号)/原子(正号)
  // 每行核素的本地编辑草稿（元素/质量数）：载入时由 zaid 初始化一次，
  // 编辑期间不受 nu.zaid 派生回写干扰，失焦/提交时再 buildZaid 回写 nu.zaid + 触发校验。
  const [rowEdits, setRowEdits] = useState<Record<number, { el: string; mass: string }>>(() => {
    const m: Record<number, { el: string; mass: string }> = {};
    initial.forEach((r, i) => { if (r.kind === "nuclide" && r.zaid) m[i] = splitZaid(r.zaid); });
    return m;
  });

  // 用拍平映射快速查找
  const presetFiltered: [string, PresetItem[]][] = filterPresets(PRESET_CATEGORIES, presetSearch);

  const flatPresets: Record<string, PresetItem> = {};
  for (const [, items] of PRESET_CATEGORIES) for (const item of items) flatPresets[item.key] = item;
  const handlePreset = (key: string) => {
    const p = flatPresets[key]; if (!p) return;
    setComment(p.name);
    if (p.density) setDensity(p.density);  // 预设密度自动填入密度栏
    if (p.rows && p.rows.length > 0) {
      // PNNL 精选：同位素级 ZAID 行直接填「手动 ZAID」模式（不走化学式展开）
      setMode("manual");
      setFormulaText("");
      setParsed(null);
      const rows: MaterialRow[] = p.rows.map(([zaid, fraction]) => ({
        kind: "nuclide" as const, zaid, fraction,
      }));
      setNucs(rows);
      setRowEdits({});
      p.rows.forEach(([zaid], i) => { if (zaid) validateZaid(i, zaid); });
    } else {
      // 化学式预设：展开后填「手动 ZAID」模式；formulaText 保留供切回化学式查看
      setFormulaText(p.formula); setMode("manual");
      setParsed(null); parseFormula(p.formula);
    }
  };

  // 对第 i 行核素调 /api/validate-zaid 并回写 zaidValid（载入/公式/手动失焦提交共用）
  const validateZaid = (i: number, zaid: string) => {
    const zaidNum = zaid.replace(/\..*$/, "").replace(/^0+/, "");
    if (!zaidNum) { setZaidValid(p => { const n = { ...p }; n[i] = null; return n; }); return; }
    fetch(apiUrl("/api/validate-zaid?zaid=" + encodeURIComponent(zaidNum)))
      .then(r => r.json())
      .then(j => setZaidValid(p => { const n = { ...p }; n[i] = j.in_db; return n; }))
      .catch(() => {});
  };

  // Bug 1 修复：载入时（含导入 INP 的核素）自动逐个查截面库，行内立即显示 ✓/✗
  useEffect(() => {
    initial.forEach((r, i) => { if (r.kind === "nuclide" && r.zaid) validateZaid(i, r.zaid); });
    // initial 在对话框打开期间不变（打开=每次新建）；若外部喂入新核素则顺带重新校验
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  // 保持每个核素行都有本地编辑草稿（新增行/结构变更后补初始化，不覆盖正在编辑的行）
  useEffect(() => {
    setRowEdits(prev => {
      let m = prev;
      nucs.forEach((r, i) => {
        if (r.kind === "nuclide" && m[i] === undefined) {
          if (m === prev) m = { ...prev };
          m[i] = splitZaid(r.zaid);
        }
      });
      return m;
    });
  }, [nucs]);

  // Bug 2 修复：失焦/提交时把草稿 元素/质量数 组装回数值 ZAID，写回 nu.zaid 并触发校验
  const commitRow = (i: number) => {
    const ed = rowEdits[i];
    if (!ed) return;
    const newZaid = resolveZaid(ed);
    if (newZaid === null) return;  // 元素为空：不提交，保留草稿继续编辑
    const c = [...nucs];
    if (c[i] && c[i].kind === "nuclide" && c[i].zaid !== newZaid) {
      c[i] = { kind: "nuclide", zaid: newZaid, fraction: c[i].fraction };
      setNucs(c);
    }
    validateZaid(i, newZaid);
    setRowEdits(prev => { const m = { ...prev }; delete m[i]; return m; });
  };

  // 保存前把未失焦的草稿并入 nucs（onBlur 通常在点击保存前触发，这里兜底防漏）
  const mergePendingEdits = (): MaterialRow[] => {
    let changed = false;
    const merged = nucs.map((r, i) => {
      if (r.kind !== "nuclide") return r;
      const ed = rowEdits[i];
      if (!ed) return r;
      const newZaid = resolveZaid(ed);
      if (newZaid === null || newZaid === r.zaid) return r;
      changed = true;
      return { kind: "nuclide" as const, zaid: newZaid, fraction: r.fraction };
    });
    if (changed) setNucs(merged);
    return merged;
  };

  const parseFormula = async (text?: string, mode?: ShareMode) => {
    const t = text || formulaText; if (!t.trim()) return;
    setParsing(true);
    try {
      const result = await expandFormula(t, shareModeToIsWeight(mode ?? shareMode));
      setParsed(result);
      setNucs(result.map(n => ({ kind: "nuclide" as const, zaid: n.zaid, fraction: n.fraction })));
      setRowEdits({});  // 公式展开整体重建行，丢弃旧草稿（sync effect 按新行重新初始化）
      // 验证每个解析出来的 ZAID
      result.forEach((n, i) => {
        if (n.zaid.replace(/\..*$/, "").replace(/^0+/, "")) validateZaid(i, n.zaid);
      });
    } catch (e: any) { alert("解析失败: " + e.message); }
    finally { setParsing(false); }
  };

  // 切换份额模式：质量份额(is_weight:true→负号) / 原子份额(is_weight:false→正号)；已填公式则立即按新模式重解析
  const toggleShareMode = (m: ShareMode) => {
    if (m === shareMode) return;
    setShareMode(m);
    if (formulaText.trim()) parseFormula(formulaText, m);
  };

  const addRow = () => setNucs([...nucs, { kind: "nuclide", zaid: "", fraction: "" }]);
  const delRow = (i: number) => { if (nucs.length > 1) { setNucs(nucs.filter((_, j) => j !== i)); setRowEdits({}); } };
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
    setRowEdits({});  // 排序后行号重排，丢弃按位置缓存的草稿（sync effect 按新行重新初始化）
  };
  const drag = useRowDrag(moveRow);

  return React.createElement(FloatingDialog, {
    title: `材料 M${matNum}`,
    onClose,
    width: 600,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
      React.createElement("button", { className: "btn btn-primary btn-sm", onClick: () => onSave({ matNum, name: comment, nuclides: (mode === "formula" && parsed ? parsed.map(n => ({ kind: "nuclide" as const, zaid: n.zaid, fraction: n.fraction })) : mergePendingEdits()), options, mtCard, density }) }, "保存"),
    ),
  },
    React.createElement("div", { style: { padding: 0 } },
        // 预设 + 用户预设管理
        React.createElement("div", { style: { marginBottom: 12 } },
          React.createElement("label", { style: s.lbl }, "预设材料"),
          React.createElement("input", {
            style: { ...s.inp, marginBottom: 6, height: 28 },
            placeholder: "搜索预设（名称/化学式/描述）",
            value: presetSearch,
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => setPresetSearch(e.target.value),
          }),
          React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "center" } },
            React.createElement("select", { className: "form-select", style: { height: 34, flex: 1 }, onChange: (e: React.ChangeEvent<HTMLSelectElement>) => e.target.value && handlePreset(e.target.value), value: "" },
              React.createElement("option", { value: "" }, "-- " + (presetFiltered.flatMap(([, items]) => items).length + userPresets.length) + " 种预设材料 --"),
              userPresets.length > 0 ? React.createElement(React.Fragment, null,
                React.createElement("optgroup", { key: "_user", label: "用户预设" }),
                userPresets.map((p, ui) => React.createElement("option", { key: p.key, value: p.key }, p.name)),
              ) : null,
              ...presetFiltered.flatMap(([cat, items]) => [
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
              placeholder: "如 H2O: 1 / N2: 0.8, O2: 0.2\n（份额符号由右侧模式决定：负号=质量份额，正号=原子份额）",
            }),
            // 份额模式切换：质量份额=is_weight:true→负号 / 原子份额=is_weight:false→正号
            React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center", marginBottom: 8 } },
              React.createElement("button", {
                className: "btn btn-primary btn-sm",
                onClick: () => parseFormula(),
                disabled: parsing,
              }, parsing ? "解析中..." : "解析化学式"),
              React.createElement("span", { style: { fontSize: 11, color: "var(--text-secondary)" } }, "份额模式"),
              SHARE_MODES.map(m => React.createElement("button", {
                key: m,
                className: "btn btn-xs " + (shareMode === m ? "btn-primary" : "btn-ghost"),
                onClick: () => toggleShareMode(m),
                title: m === "weight" ? "负号输出（is_weight:true，默认）" : "正号输出（is_weight:false）",
              }, shareModeLabel(m))),
            ),
            // 份额语义标注：当前模式 + MCNP 正负号约定 + 两种份额含义
            React.createElement("div", { style: { fontSize: 10, color: "var(--text-tertiary)", marginBottom: 8, lineHeight: 1.5 } },
              `份额 = ${shareModeLabel(shareMode)} · ${SIGN_CONVENTION_NOTE} · ${SHARE_CONVERSION_NOTE}`,
            ),
            parsed && React.createElement("div", { style: { fontSize: 11, color: "var(--text-tertiary)", marginBottom: 8 } },
              `共 ${parsed.length} 个核素（含 >0.1% 天然丰度组分）`,
            ),
            // 归一化提示：份额总和恒为 1；化学式:比例 只影响各成分相对比例，结果仍会归一化
            parsed && React.createElement("div", { style: { fontSize: 10, color: "var(--text-tertiary)", marginBottom: 8, lineHeight: 1.5 } },
              "份额已归一化（总和=1）；化学式:比例 只影响各成分的相对比例，结果仍会归一化",
            ),
            parsed && React.createElement("div", { style: { maxHeight: 150, overflow: "auto", marginBottom: 8 } },
              React.createElement("table", { style: { width: "100%", fontSize: 11, borderCollapse: "collapse" } },
                React.createElement("thead", null, React.createElement("tr", null,
                  React.createElement("th", { style: { width: 16, padding: "4px 4px" } }),
                  React.createElement("th", { style: { padding: "4px 8px", textAlign: "left" } }, "ZAID"),
                  React.createElement("th", { style: { padding: "4px 8px", textAlign: "left" }, title: SIGN_CONVENTION_NOTE }, "份额"),
                )),
                React.createElement("tbody", null, parsed.map((n, i) =>
                  React.createElement("tr", { key: i, style: { borderBottom: "1px solid rgba(255,255,255,0.03)" } },
                    React.createElement("td", { style: { padding: "3px 4px" } },
                      React.createElement("span", { style: { width: 8, height: 8, borderRadius: "50%", display: "inline-block", background: zaidValid[i] === true ? "#4caf50" : zaidValid[i] === false ? "#e53935" : "#555", verticalAlign: "middle" } }),
                    ),
                    React.createElement("td", { style: { padding: "3px 8px", fontWeight: 600 } }, n.zaid),
                    React.createElement("td", { style: { padding: "3px 8px" }, title: SIGN_CONVENTION_NOTE }, n.fraction),
                  )
                )),
              ),
            ),
          )
        ) : (
          React.createElement(React.Fragment, null,
            React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 } },
              React.createElement("span", { style: s.lbl }, "核素组成（核素/条件行，所有行可拖动排序）"),
              React.createElement("div", { style: { display: "flex", gap: 6 } },
                React.createElement("button", { className: "btn btn-success btn-xs", onClick: addRow }, "+ 核素"),
                React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: addConditional, title: "插入 #ifdef 名称 / #else / #endif 三行" }, "# 条件"),
              ),
            ),
            // 导入 INP 的份额保留原样，仅提示其正负含义，不擅自转换
            React.createElement("div", { style: { fontSize: 10, color: "var(--text-tertiary)", marginBottom: 6 } },
              "份额保留原样：负号=质量份额、正号=原子份额（导入 INP 不自动转换）",
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
                    React.createElement("input", { style: { ...s.inp, flex: 1 } as React.CSSProperties, placeholder: "元素 (如 U, 92, H, Fe)", value: (rowEdits[i] ? rowEdits[i].el : splitZaid(nu.zaid).el) || "",
                      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
                        setRowEdits(prev => ({ ...prev, [i]: { el: e.target.value, mass: (prev[i] ? prev[i].mass : splitZaid(nu.zaid).mass) || "" } }));
                      },
                      onBlur: () => commitRow(i),
                    }),
                    React.createElement("span", { style: { color: "var(--text-tertiary)", fontSize: 11 } }, "-"),
                    React.createElement("input", { style: { ...s.inp, maxWidth: 70 } as React.CSSProperties, placeholder: "质量数", value: (rowEdits[i] ? rowEdits[i].mass : splitZaid(nu.zaid).mass) || "",
                      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
                        setRowEdits(prev => ({ ...prev, [i]: { el: (prev[i] ? prev[i].el : splitZaid(nu.zaid).el) || "", mass: e.target.value } }));
                      },
                      onBlur: () => commitRow(i),
                    }),
                    React.createElement("input", { style: { ...s.inp, maxWidth: 90 } as React.CSSProperties, placeholder: "份额(负=质量)", title: SIGN_CONVENTION_NOTE, value: nu.fraction, onChange: (e: React.ChangeEvent<HTMLInputElement>) => { const c = [...nucs]; c[i] = { kind: "nuclide", zaid: nu.zaid, fraction: e.target.value }; setNucs(c); } }),
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
            React.createElement("label", { style: s.lbl }, "其他"),
            React.createElement("textarea", {
              style: { ...s.inp, minHeight: 60, fontFamily: "Consolas,monospace", fontSize: 12, marginBottom: 8, resize: "vertical" },
              value: options,
              onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => setOptions(e.target.value),
              placeholder: "例: nlib=.66c\nplib=.84p\ngas=1",
            }),
            React.createElement("label", { style: s.lbl }, "热中子 MT 卡"),
            React.createElement("input", { style: s.inp, value: mtCard, onChange: (e: React.ChangeEvent<HTMLInputElement>) => setMtCard(e.target.value), placeholder: "例: lwtr.10t" }),
          ),
        ),
      ),
  );
}
