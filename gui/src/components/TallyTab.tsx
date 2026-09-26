import React, { useState, useRef } from "react";
import GridEditor from "./GridEditor";
import TextModeSection from "./TextModeSection";
import DocViewer from "./DocViewer";
import FMeshForm from "../volume/FMeshForm";
import PtracForm from "../ptrac/PtracForm";
import { ptracFromDict } from "../ptrac/ptracState";
import { fmeshDefsToRows } from "../volume/fmeshState";
import { useDeck } from "../utils/DeckContext";
import { deckTalliesToRows, rowsToDeckTallies, splitTallyNumber, TALLY_PREFIX_OPTIONS, type TallyRow } from "../utils/tallyBridge";
import { useSectionTextMode } from "../utils/useSectionTextMode";
import { useDeckSynced } from "../utils/useDeckSynced";

type TallyType = "F1" | "F2" | "F4" | "F5" | "F6" | "F7" | "F8";

const TYPE_LABELS: Record<TallyType, string> = {
  F1: "曲面粒子流", F2: "曲面平均通量", F4: "栅元平均通量",
  F5: "点探测器", F6: "能量沉积", F7: "裂变能沉积", F8: "脉冲高度谱",
};

const TYPE_PARAM_PLACEHOLDER: Record<TallyType, string> = {
  F1: "曲面号，如 1 2 3", F2: "曲面号，如 1 2 3", F4: "栅元号，如 1 2 3",
  F5: "x y z R0", F6: "栅元号，如 1 2 3", F7: "栅元号，如 1 2 3", F8: "栅元号，如 1 2 3",
};

const TYPE_TOOLTIP: Record<TallyType, string> = {
  F1: "穿过指定曲面的粒子流", F2: "曲面平均通量", F4: "栅元平均通量，最常用",
  F5: "空间点的通量，不需栅元", F6: "能量沉积 (MeV/g)", F7: "裂变能沉积 (MeV/g)", F8: "脉冲高度分布",
};

const TYPE_BY_DIGIT: Record<number, TallyType> = { 1: "F1", 2: "F2", 4: "F4", 5: "F5", 6: "F6", 7: "F7", 8: "F8" };
const numberToType = (n: number): TallyType | null => TYPE_BY_DIGIT[n % 10] || null;

const F5_IMAGING_PREFIXES = ["IC", "IR", "IP"];

/**
 * 从计数编号输入解析 { 类型, 编号 }（剥前导 F + 剥 X/Y/Z 后缀，按个位数映射类型）：
 *   25 / F25 / 25X / F25X / 5 → { type:"F5", number:"25"|"5" }
 *   12 → { type:"F2", number:"12" }；无效（""/abc/F/0/成像前缀…）→ { type:null, number:原样 }
 */
export function parseTallyTypeNumber(raw: string): { type: TallyType | null; number: string } {
  const up = raw.trim().toUpperCase();
  const base = up.replace(/^F/, "").replace(/[XYZ]$/, "");
  const m = base.match(/^\d+$/);
  if (!m) return { type: null, number: raw };
  return { type: numberToType(parseInt(m[0], 10)), number: m[0] };
}

/**
 * F5 成像（IC/IR/IP）变体解析；普通编号（含 F 前缀 / X/Y/Z 后缀）走 parseTallyTypeNumber。
 * 返回值仅供 handleNumberChange 判断是否命中 F5 类型。
 */
export function parseF5Variant(val: string): { num: string; label: string } {
  const up = val.toUpperCase();
  for (const p of F5_IMAGING_PREFIXES) {
    if (up.startsWith(p)) { const rest = up.slice(p.length); return { num: rest, label: `F${p}${rest}` }; }
  }
  const parsed = parseTallyTypeNumber(up);
  if (parsed.type === "F5") return { num: parsed.number, label: "F5" };
  return { num: up, label: `F${up}` };
}

export default function TallyTab() {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const { deck, patch } = useDeck();
  // 计数列表：deck.tallies(snake) 单一权威，本地工作副本带稳定 id（共享 hook 收敛推拉守卫）
  const idsRef = useRef<number[]>([]);   // 按位置缓存上次的 tally id：number 变化不复位 key，避免输入光标丢失
  const deckToLocalT = (ds: any[]): TallyRow[] => {
    const used = new Set<number>();
    // 字段映射（含 fn_prefix / number_suffix 两个身份字段）统一在 tallyBridge——组件只补稳定 id
    return deckTalliesToRows(ds).map((t, i) => {
      let id = idsRef.current[i];
      if (id === undefined || used.has(id)) {
        id = (t.number && t.type) ? (parseInt(t.number) * 10 + (t.type.charCodeAt(1) - 48) + (t.particle?.charCodeAt(0) || 0)) : (i + 1);
        while (used.has(id)) id++;
      }
      used.add(id);
      return { ...t, id };
    });
  };
  const [tallies, setTallies] = useDeckSynced<TallyRow[], any[]>({
    deck, patch, key: "tallies",
    fromDeck: (v) => { const next = deckToLocalT(v || []); idsRef.current = next.map(t => t.id); return next; },
    toDeck: rowsToDeckTallies,
  });
  // 文本↔表单互转（深模块：逻辑在 useSectionTextMode 一处）
  const tallyText = useSectionTextMode("tally", {
    deck, patch, overrideKey: "tally",
    onBackToForm: (data) => {
      // 后端口径（snake_case，含 fn_prefix/number_suffix）→ 本地行：必须过同一座桥，
      // 否则文本模式导入 `*F4` 后前缀仍是空（本地行没有 `prefix` 字段）。
      if (data.tallies?.length) setTallies(deckToLocalT(data.tallies));
      // FMESH/TMESH 卡：后端 fmesh_defs → deck.tally.fmesh
      if (data.tally?.fmesh_defs) {
        patch({ tally: { ...(deck.tally || {}), fmesh: fmeshDefsToRows(data.tally.fmesh_defs) } });
      }
      // Fn 卡带其它字段（如 ft14=1）：弹窗提示并填入高级「其他卡片」
      const others = (data.tallies || [])
        .map((t: any) => String(t.params || ""))
        .filter((p: string) => /=/.test(p));
      if (others.length) {
        const merged = [...others, (deck.adv?.other_cards || "")].filter(Boolean).join("\n");
        patch({ adv: { ...(deck.adv || {}), other_cards: merged } });
        alert("F 计数卡含其它字段，已填入高级标签页的『其他卡片』框：\n\n" + others.join("\n"));
      }
    },
  });
  const { rawMode: tallyRawMode, rawText: tallyRawText, busy: tallyBusy, toggleRawMode: toggleTallyRawMode, onDiscard: discardTallyRaw } = tallyText;
  const addTally = () => {
    const nums = tallies.map((t) => parseInt(t.number) || 0);
    const maxNum = nums.length > 0 ? Math.max(...nums) : 0;
    const newNum = Math.max(maxNum + 10, 10);
    const digit = newNum % 10;
    const newType = TYPE_BY_DIGIT[digit] || "F4";
    setTallies([...tallies, { id: Date.now(), prefix: "", type: newType, number: String(newNum), suffix: "", particle: "n", params: "", multiplier: "", enableEn: false, enableTn: false }]);
  };
  const delTally = (id: number) => setTallies(tallies.filter((t) => t.id !== id));
  const updateTally = (id: number, field: keyof TallyRow, value: any) => setTallies(tallies.map((t) => (t.id === id ? { ...t, [field]: value } : t)));

  const handleNumberChange = (id: number, val: string) => {
    // X/Y/Z 后缀（F5 环探测器）不再是"输入即丢"：卡号框写 25X / F25X 时把 X 存进 suffix，
    // 生成侧才能还原成 `F5X:N`（否则环探测器静默变点探测器）。
    const { suffix } = splitTallyNumber(val);
    setTallies(tallies.map((t) => {
      if (t.id !== id) return t;
      // 通用解析：剥 F 前缀 + X/Y/Z 后缀 → 按个位数映射类型（25/F25/25X/F25X/5 → F5）
      const parsed = parseTallyTypeNumber(val);
      if (parsed.type) return { ...t, number: parsed.number, suffix, type: parsed.type };
      // F5 成像变体（IC/IR/IP）：保留既有语义
      const v = parseF5Variant(val);
      if (v.num) { const pn = parseInt(v.num) || 0; if (pn > 0 && pn % 10 === 5) return { ...t, number: val, suffix, type: "F5" }; }
      return { ...t, number: val };
    }));
  };

  return (
    <>
      <div className="glass-card">
        <TextModeSection label="计数卡" active={tallyRawMode} onToggle={toggleTallyRawMode} onDiscard={discardTallyRaw} />
        {tallyRawMode ? (
          <textarea className="form-input" value={tallyRawText} onChange={e => patch({rawOverrides:{...deck.rawOverrides,tally:e.target.value}})}
            style={{width:"100%",minHeight:200,fontFamily:"Consolas,monospace",fontSize:12}} placeholder="计数卡原始文本..." />
        ) : (
        <><div className="card-header"><span className="card-title" style={{flexShrink:0}}>计数卡 (Tally)</span>
            <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
              <button className="btn btn-ghost btn-xs" style={{marginRight:6}} onClick={() => setDoc({path:"/docs/MCNP6_FN卡结构参考.md",title:"FN 计数卡结构参考"})}>📖 FN参考</button>
            </div>
            <button className="btn btn-success btn-sm" onClick={addTally}>+ 添加计数</button></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>前缀</th><th>类型</th><th>编号</th><th>粒子</th><th>参数</th><th>乘子</th><th>En</th><th>Tn</th><th>操作</th></tr></thead>
            <tbody>{tallies.map((t) => (
              <tr key={t.id}>
                <td><select className="form-select" aria-label="计数卡前缀" value={t.prefix} onChange={e => updateTally(t.id,"prefix",e.target.value)} style={{height:30,fontSize:12,width:56}} title="*Fn=能量通量（乘能量）/ +Fn=计数修饰；FIP/FIR/FIC=F5 成像">{TALLY_PREFIX_OPTIONS.map(p => <option key={p || "none"} value={p}>{p || "无"}</option>)}{/* 导入来的成像前缀（FIP/FIR/FIC）不在固定选项里：补一个动态项，免得 select 显示空白并把值写丢 */}{t.prefix && !(TALLY_PREFIX_OPTIONS as readonly string[]).includes(t.prefix) && <option value={t.prefix}>{t.prefix}</option>}</select></td>
                <td><select className="form-select" value={t.type} onChange={e => updateTally(t.id,"type",e.target.value)} style={{height:30,fontSize:12,width:130}}>{(Object.keys(TYPE_LABELS) as TallyType[]).map(tp => <option key={tp} value={tp}>{tp} {TYPE_LABELS[tp]}</option>)}</select></td>
                <td style={{whiteSpace:"nowrap"}}>
                  <input className="form-input" aria-label="计数卡编号" value={t.number} onChange={e => handleNumberChange(t.id, e.target.value)} style={{height:28,fontSize:12,width:70}} placeholder="如 4" title="计数卡号（数字）；F5 环探测器用右侧轴字母" />
                  {/* F5X/F5Y/F5Z 环探测器：轴字母是**卡片身份**的一部分（丢了就把环探测器变成点探测器），
                      必须有可见可改的控件 —— 旧实现里连导入都会被抹掉。仅在 F5 行出现。 */}
                  {t.type === "F5" && (
                    <select className="form-select" aria-label="环探测器轴" value={t.suffix} onChange={e => updateTally(t.id, "suffix", e.target.value)} style={{height:28,fontSize:12,width:46,marginLeft:4}} title="F5 环探测器轴：空=点探测器；X/Y/Z=沿该轴的环探测器（生成 F5X:N …）">
                      <option value="">—</option><option value="X">X</option><option value="Y">Y</option><option value="Z">Z</option>
                    </select>
                  )}
                </td>
                <td><input className="form-input" value={t.particle} onChange={e => updateTally(t.id,"particle",e.target.value)} onBlur={e => {
                  const v = e.target.value;
                  const parts = v.split(/[\s,]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
                  const valid = ["N","P","E"];
                  const bad = parts.filter(p => !valid.includes(p));
                  const warns: string[] = [];
                  if (bad.length) warns.push("MCNP 只支持 N/P/E: " + bad.join(", "));
                  // 按计数类型限制
                  const type = t.type;
                  const allowed: Record<string, string[]> = {F5:["N","P"],F6:["N","P"],F7:["N"],F8:["P","E"]};
                  const perType = allowed[type];
                  if (perType) {
                    const invalid = parts.filter(p => valid.includes(p) && !perType.includes(p));
                    if (invalid.length) warns.push(type + " 不支持 " + invalid.join(", "));
                  }
                  if (warns.length) alert(warns.join("\n"));
                  updateTally(t.id, "particle", [...new Set(parts.filter(p => valid.includes(p) && (!perType || perType.includes(p))))].join(",") || (type === "F7" ? "N" : type === "F8" ? "P" : "N"));
                }} style={{height:28,fontSize:12,width:100}} placeholder="如 N,P,E" /></td>
                <td><input className="form-input" value={t.params} onChange={e => updateTally(t.id,"params",e.target.value)} style={{height:28,fontSize:12,width:180}} placeholder={TYPE_PARAM_PLACEHOLDER[t.type as TallyType] || "参数"} title={TYPE_TOOLTIP[t.type as TallyType] || ""} /></td>
                <td><input className="form-input" value={t.multiplier} onChange={e => updateTally(t.id,"multiplier",e.target.value)} style={{height:28,fontSize:12,width:150}} placeholder="如 8.65E10 1 -5 -6" title="FM 响应乘子：C m r1 r2 ...（空 = 不生成 FM 卡）" /></td>
                <td style={{textAlign:"center"}}><input type="checkbox" checked={t.enableEn} onChange={e => updateTally(t.id,"enableEn",e.target.checked)} style={{accentColor:"var(--accent)"}} title="生成 En 能量卡" /></td>
                <td style={{textAlign:"center"}}><input type="checkbox" checked={t.enableTn} onChange={e => updateTally(t.id,"enableTn",e.target.checked)} style={{accentColor:"var(--accent)"}} title="生成 Tn 时间卡" /></td>
                <td><button className="btn btn-danger btn-xs" onClick={() => delTally(t.id)}>x</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        </>)}
      </div>

      <div style={{display:"flex",gap:16,alignItems:"flex-start"}}>
        <div className="glass-card" style={{flex:1}}>
          <div className="card-header"><span className="card-title">E0 / En 能量网格</span></div>
          <GridEditor prefix="e" label="E0 全局" unit="MeV" />
          {tallies.filter(t => t.enableEn).map(t => (
            <div key={`en-${t.id}`} style={{marginTop:12,borderTop:"1px solid rgba(255,255,255,0.06)",paddingTop:12}}>
              <GridEditor prefix={`e${t.number}`} label={`E${t.number} 计数F${t.number}`} unit="MeV" />
            </div>
          ))}
          {tallies.filter(t => t.enableEn).length === 0 && <div style={{marginTop:8,fontSize:11,color:"var(--text-tertiary)"}}>在计数卡中勾选 En 即可在此编辑对应能量网格</div>}
        </div>
        
      
      <div className="glass-card" style={{flex:1}}>
          <div className="card-header"><span className="card-title">T0 / Tn 时间网格</span></div>
          <GridEditor prefix="t" label="T0 全局" unit="shake" />
          {tallies.filter(t => t.enableTn).map(t => (
            <div key={`tn-${t.id}`} style={{marginTop:12,borderTop:"1px solid rgba(255,255,255,0.06)",paddingTop:12}}>
              <GridEditor prefix={`t${t.number}`} label={`T${t.number} 计数F${t.number}`} unit="shake" />
            </div>
          ))}
          {tallies.filter(t => t.enableTn).length === 0 && <div style={{marginTop:8,fontSize:11,color:"var(--text-tertiary)"}}>在计数卡中勾选 Tn 即可在此编辑对应时间网格</div>}
        </div>
      </div>

      {/* 网格计数（FMESH/TMESH）：结构化表单（契约 meshtal-visualization.md §4.7.1）；3D 结果入口在「输出」标签页 */}
      <FMeshForm
        value={(deck.tally as any)?.fmesh || []}
        onChange={(rows) => patch({ tally: { ...(deck.tally || {}), fmesh: rows } })}
      />

      {/* 粒子径迹（PTRAC）表单（契约 ptrac-visualization.md §4.5）：状态 deck.tally.ptrac */}
      <PtracForm
        value={ptracFromDict((deck.tally as any)?.ptrac)}
        onChange={(st) => patch({ tally: { ...(deck.tally || {}), ptrac: st } })}
      />
      {doc && <DocViewer path={doc.path} title={doc.title} onClose={() => setDoc(null)} />}
    </>
  );
}
