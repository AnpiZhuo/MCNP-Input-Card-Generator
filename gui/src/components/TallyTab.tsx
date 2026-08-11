import React, { useState, useEffect, useRef } from "react";
import GridEditor from "./GridEditor";
import TextModeSection from "./TextModeSection";
import DocViewer from "./DocViewer";
import { useDeck } from "../utils/DeckContext";
import { useSectionTextMode } from "../utils/useSectionTextMode";

type TallyType = "F1" | "F2" | "F4" | "F5" | "F6" | "F7" | "F8";
type TallyPrefix = "" | "*" | "+";

interface Tally {
  id: number;
  prefix: TallyPrefix;
  type: TallyType;
  number: string;
  particle: string;
  params: string;
  enableEn: boolean;
  enableTn: boolean;
}

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
const F5_RING_SUFFIXES = ["X", "Y", "Z"];

const parseF5Variant = (val: string): { num: string; label: string } => {
  const up = val.toUpperCase();
  for (const p of F5_IMAGING_PREFIXES) {
    if (up.startsWith(p)) { const rest = up.slice(p.length); return { num: rest, label: `F${p}${rest}` }; }
  }
  for (const s of F5_RING_SUFFIXES) {
    if (up.endsWith(s)) { const base = up.slice(0, -1); if (/^\d+$/.test(base)) return { num: base, label: `F5${s}` }; }
  }
  return { num: up, label: `F${up}` };
};

export default function TallyTab() {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const [tallies, setTallies] = useState<Tally[]>([]);
  const { deck, patch } = useDeck();
  // 文本↔表单互转（深模块：逻辑在 useSectionTextMode 一处）
  const tallyText = useSectionTextMode("tally", {
    deck, patch, overrideKey: "tally",
    onBackToForm: (data) => {
      if (data.tallies?.length) setTallies(data.tallies);
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
    initialText: deck.rawOverrides?.tally || "",
    initialMode: deck.textMode?.tally,
  });
  const { rawMode: tallyRawMode, rawText: tallyRawText, busy: tallyBusy, setRawText: setTallyRawText, toggleRawMode: toggleTallyRawMode, onDiscard: discardTallyRaw } = tallyText;
  const lastPushRef = useRef("[]");       // 初始为 []：挂载时空 tallies 不把导入的 deck.tallies 冲成 []
  const lastPullRef = useRef<string|null>(null);  // 只在 deck 数据确实变了才拉
  // local → deck
  useEffect(() => {
    const mapped = tallies.map(t => ({ type: t.type, number: parseInt(t.number)||0, particle: t.particle || "n", params: t.params, enableEn: t.enableEn, enableTn: t.enableTn }));
    const json = JSON.stringify(mapped);
    if (json !== lastPushRef.current) { lastPushRef.current = json; patch({ tallies: mapped }); }
  }, [tallies]);
  // deck → local（仅首次 + deck 真正变化时）
  useEffect(() => {
    if (!deck.tallies?.length) return;
    const json = JSON.stringify(deck.tallies);
    if (json === lastPullRef.current) return;
    lastPullRef.current = json;
    // 给每个 tally 分配稳定 id（用 number+type+particle+params 做种子）
    const next = deck.tallies.map((t, i) => ({
      id: (t.number && t.type) ? (t.number * 10 + (t.type.charCodeAt(1)-48) + (t.particle?.charCodeAt(0)||0)) : (i + 1),
      prefix: "" as const,
      type: t.type as any,
      number: String(t.number),
      particle: t.particle,
      params: t.params,
      enableEn: t.enableEn || false,
      enableTn: t.enableTn || false,
    }));
    setTallies(next);
  }, [deck.tallies]);
  const addTally = () => {
    const nums = tallies.map((t) => parseInt(t.number) || 0);
    const maxNum = nums.length > 0 ? Math.max(...nums) : 0;
    const newNum = Math.max(maxNum + 10, 10);
    const digit = newNum % 10;
    const newType = TYPE_BY_DIGIT[digit] || "F4";
    setTallies([...tallies, { id: Date.now(), prefix: "", type: newType, number: String(newNum), particle: "n", params: "", enableEn: false, enableTn: false }]);
  };
  const delTally = (id: number) => setTallies(tallies.filter((t) => t.id !== id));
  const updateTally = (id: number, field: keyof Tally, value: any) => setTallies(tallies.map((t) => (t.id === id ? { ...t, [field]: value } : t)));

  const handleNumberChange = (id: number, val: string) => {
    setTallies(tallies.map((t) => {
      if (t.id !== id) return t;
      const m = val.match(/^\d+$/);
      if (m) { const num = parseInt(m[0]); const nt = numberToType(num); return { ...t, number: val, ...(nt ? { type: nt } : {}) }; }
      const v = parseF5Variant(val);
      if (v.num) { const pn = parseInt(v.num)||0; if (pn > 0 && pn % 10 === 5) return { ...t, number: val, type: "F5" }; }
      return { ...t, number: val };
    }));
  };

  return (
    <>
      <div className="glass-card">
        <TextModeSection label="计数卡" active={tallyRawMode} onToggle={toggleTallyRawMode} onDiscard={discardTallyRaw} />
        {tallyRawMode ? (
          <textarea className="form-input" value={tallyRawText} onChange={e => {setTallyRawText(e.target.value);patch({rawOverrides:{...deck.rawOverrides,tally:e.target.value}});}}
            style={{width:"100%",minHeight:200,fontFamily:"Consolas,monospace",fontSize:12}} placeholder="计数卡原始文本..." />
        ) : (
        <><div className="card-header"><span className="card-title" style={{flexShrink:0}}>计数卡 (Tally)</span>
            <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
              <button className="btn btn-ghost btn-xs" style={{marginRight:6}} onClick={() => setDoc({path:"/docs/MCNP6_FN卡结构参考.md",title:"FN 计数卡结构参考"})}>📖 FN参考</button>
            </div>
            <button className="btn btn-success btn-sm" onClick={addTally}>+ 添加计数</button></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>前缀</th><th>类型</th><th>编号</th><th>粒子</th><th>参数</th><th>En</th><th>Tn</th><th>操作</th></tr></thead>
            <tbody>{tallies.map((t) => (
              <tr key={t.id}>
                <td><select className="form-select" value={t.prefix} onChange={e => updateTally(t.id,"prefix",e.target.value)} style={{height:30,fontSize:12,width:56}} title="*Fn=能量通量 +F8=电荷沉积"><option value="">无</option><option value="*">*</option><option value="+">+</option></select></td>
                <td><select className="form-select" value={t.type} onChange={e => updateTally(t.id,"type",e.target.value)} style={{height:30,fontSize:12,width:130}}>{(Object.keys(TYPE_LABELS) as TallyType[]).map(tp => <option key={tp} value={tp}>{tp} {TYPE_LABELS[tp]}</option>)}</select></td>
                <td><input className="form-input" value={t.number} onChange={e => handleNumberChange(t.id, e.target.value)} style={{height:28,fontSize:12,width:70}} placeholder="如 4" /></td>
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
                <td><input className="form-input" value={t.params} onChange={e => updateTally(t.id,"params",e.target.value)} style={{height:28,fontSize:12,width:180}} placeholder={TYPE_PARAM_PLACEHOLDER[t.type]} title={TYPE_TOOLTIP[t.type]} /></td>
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

      <details style={{fontSize:12,color:"var(--text-secondary)",marginTop:4}}>
        <summary style={{cursor:"pointer",fontWeight:600,color:"var(--text-secondary)",fontSize:11}}>FN 计数卡结构参考（点击展开）</summary>
        <div style={{maxHeight:400,overflow:"auto",padding:"8px 0",lineHeight:1.7}}>
          <table style={{fontSize:11,width:"100%",borderCollapse:"collapse"}}>
            <thead><tr style={{borderBottom:"1px solid rgba(255,255,255,0.06)"}}><th style={{padding:"6px 8px",textAlign:"left"}}>类型</th><th style={{padding:"6px 8px",textAlign:"left"}}>描述</th><th style={{padding:"6px 8px",textAlign:"left"}}>单位</th><th style={{padding:"6px 8px",textAlign:"left"}}>说明</th></tr></thead>
            <tbody>{[["F1","曲面电流","particles","穿过曲面的粒子数"],["F2","曲面通量","particles/cm2","曲面上平均通量"],["F4","栅元通量","particles/cm2","最常用"],["F5","点探测器","particles/cm2","位置 X Y Z +/-R0"],["F6","能量沉积","MeV/g","裂变除外"],["F7","裂变能沉积","MeV/g","仅中子"],["F8","脉冲高度","pulses","探测器响应"]].map(([t,d,u,nn]) => <tr key={t} style={{borderBottom:"1px solid rgba(255,255,255,0.03)"}}><td style={{padding:"4px 8px",fontWeight:600}}>{t}</td><td style={{padding:"4px 8px"}}>{d}</td><td style={{padding:"4px 8px",color:"var(--text-tertiary)"}}>{u}</td><td style={{padding:"4px 8px"}}>{nn}</td></tr>)}</tbody>
          </table>
        </div>
      </details>
      {doc && <DocViewer path={doc.path} title={doc.title} onClose={() => setDoc(null)} />}
    </>
  );
}
