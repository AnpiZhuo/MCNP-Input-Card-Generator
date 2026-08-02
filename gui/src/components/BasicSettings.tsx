import React, { useState } from "react";
import DocViewer from "./DocViewer";
import TextModeSection from "./TextModeSection";
import { useDeck } from "../utils/DeckContext";

const MODE_LABELS = ["N 中子", "P 光子", "E 电子", "H 质子", "HE 重离子", "D 氘核", "T 氚核", "A α粒子"];
const MODE_IDS = ["mode-n", "mode-p", "mode-e", "mode-h", "mode-he", "mode-d", "mode-t", "mode-a"];

export default function BasicSettings() {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const [rawMode, setRawMode] = useState(false);
  const [rawText, setRawText] = useState("");
  const { deck, patch } = useDeck();
  const b: Record<string, any> = deck.basic || {};
  const setB = (key: string, v: any) => patch({ basic: { ...b, [key]: v } });

  return (
    <>
      <TextModeSection label="基本设置" active={rawMode} onToggle={() => setRawMode(!rawMode)} onDiscard={() => { setRawMode(false); setRawText(""); patch({rawOverrides:{...deck.rawOverrides,basic:""}}); }}
        extra={<a href="mailto:1378963177@qq.com" style={{ color: "var(--accent-glow)", fontSize: 13, whiteSpace: "nowrap", textDecoration: "none" }}>发现 Bug 或有好建议？欢迎联系 → 1378963177@qq.com</a>} />
      {rawMode ? (
        <textarea className="form-input" value={rawText} onChange={e => {setRawText(e.target.value);patch({rawOverrides:{...deck.rawOverrides,basic:e.target.value}});}}
          style={{width:"100%",minHeight:300,fontFamily:"Consolas,monospace",fontSize:12}} placeholder="基本设置原始文本..." />
      ) : (
      <><div className="glass-card">
        <div className="card-header">
          <span className="card-title" style={{ flexShrink: 0 }}>标题 & 运行控制</span>
          <div style={{ flex: 1, display: "flex", justifyContent: "center", gap: 6 }}>
            <button className="btn btn-ghost btn-xs" onClick={() => setDoc({path:"/docs/C810_卡片格式详细.md",title:"C810 卡片格式参考"})}>📖 C810</button>
            <button className="btn btn-ghost btn-xs" onClick={() => setDoc({path:"/docs/sample_format.md",title:"INP 示例格式"})}>📄 示例</button>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ flex: 2 }}>
            <label className="form-label">标题 (Title) — 纯英文，禁止中文</label>
            <input id="basic-title" className="form-input" value={b.title || ""} onChange={e => setB("title", e.target.value)} placeholder="纯英文，禁止中文" />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 140 }}>
            <label className="form-label">NPS 粒子数</label>
            <input id="basic-nps" className="form-input" value={b.nps || ""} onChange={e => setB("nps", e.target.value)} placeholder="如 1000000" />
          </div>
          <div className="form-group" style={{ maxWidth: 120 }}>
            <label className="form-label">CTME (min)</label>
            <input id="basic-ctme" className="form-input" value={b.ctme || ""} onChange={e => setB("ctme", e.target.value)} placeholder="留空=不限" />
          </div>
          <div className="form-group" style={{ maxWidth: 140 }}>
            <label className="form-label">ACT</label>
            <input id="basic-act" className="form-input" value={b.act || ""} onChange={e => setB("act", e.target.value)} placeholder="如 FISSION=N" />
          </div>
          <div className="form-group" style={{ maxWidth: 140 }}>
            <label className="form-label">PRINT</label>
            <input id="basic-print" className="form-input" value={b.print_pr || ""} onChange={e => setB("print_pr", e.target.value)} placeholder="如 110 40 150" />
          </div>
        </div>
      </div>
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title">粒子模式 (MODE)</span>
        </div>
        <div className="check-group">
          {MODE_LABELS.map((name, i) => {
            const modeId = MODE_IDS[i];
            const key = "mode_" + modeId.replace("mode-", "");
            return (
              <label className="check-item" key={name}>
                <input id={modeId} type="checkbox" checked={!!b[key]} onChange={e => setB(key, e.target.checked)} /> {name}
              </label>
            );
          })}
        </div>
      </div>
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title">NONU — 中子裂变开关</span>
        </div>
        <div className="check-group">
          <label className="check-item">
            <input id="basic-nonu" type="checkbox" checked={b.phys_fis === false} onChange={e => setB("phys_fis", !e.target.checked)} /> 关闭裂变（NONU）— 中子不会引发裂变，适合纯散射或屏蔽计算
          </label>
        </div>
      </div>
      </>)}
      {doc && <DocViewer path={doc.path} title={doc.title} onClose={() => setDoc(null)} />}
    </>
  );
}
