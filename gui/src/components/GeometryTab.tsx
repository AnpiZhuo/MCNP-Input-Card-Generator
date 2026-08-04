import React, { useState, useEffect, useRef } from "react";
import CellEditDialog, { type CellData } from "./CellEditDialog";
import McnpEditor from "./McnpEditor";
import TextModeSection from "./TextModeSection";
import DocViewer from "./DocViewer";
import Preview3D from "./Preview3D";
import StepImportDialog from "./StepImportDialog";
import { useDeck } from "../utils/DeckContext";

interface GeoProps {
  pendingCellFromMaterial?: number;
}

export default function GeometryTab({ pendingCellFromMaterial }: GeoProps) {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const [cells, setCells] = useState<CellData[]>([]);
  const [editCell, setEditCell] = useState<number | null>(null);
  const [surfText, setSurfText] = useState("");
  const [trText, setTrText] = useState("");
  const [cellRawMode, setCellRawMode] = useState(false);
  const [cellRawText, setCellRawText] = useState("");
  const [show3D, setShow3D] = useState(false);
  const [showStepDlg, setShowStepDlg] = useState(false);
  const [freecadOk, setFreecadOk] = useState<boolean|null>(null);
  const cellsRef = useRef(cells);
  cellsRef.current = cells;
  const surfRef = useRef(surfText);
  surfRef.current = surfText;
  const trRef = useRef(trText);
  trRef.current = trText;
  const { deck, patch } = useDeck();

  useEffect(() => {
    fetch("http://localhost:5001/api/check-freecad", {method:"POST"})
      .then(r => r.json()).then(j => { if (j.status === "ok") setFreecadOk(j.found); })
      .catch(() => setFreecadOk(false));
  }, []);

  // 材料→栅元联动：新材料添加时自动创建栅元行
  useEffect(() => {
    if (pendingCellFromMaterial && pendingCellFromMaterial > 0) {
      const maxNum = cells.length > 0 ? Math.max(...cells.map(c => parseInt(c.num) || 0)) : 0;
      setCells([...cells, {
        num: String(maxNum + 1), mat: String(pendingCellFromMaterial),
        density: "-1.0", surfaces: "", impN: "", impP: "", impE: "",
        vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "",
        trcl: "", tmp: "", otherParams: "", render: true,
        comment: `材料 M${pendingCellFromMaterial} 对应栅元`,
      }]);
    }
  }, [pendingCellFromMaterial]);

  const handleStepImport = async (settings: any, file: File) => {
    try {
      const text = await file.text();
      const r = await fetch("http://localhost:5001/api/import-step", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, data: text, settings }),
      });
      if (r.ok) { const j = await r.json(); if (j.status === "ok") { if (j.deck) patch({ surfaces: j.deck.surfaces || "", cells: j.deck.cells || [] }); alert("✅ STEP 导入成功"); setShowStepDlg(false); return; } }
    } catch {}
    alert("STEP 导入需要后端服务 + FreeCAD/McCAD");
    setShowStepDlg(false);
  };
  const handlePreview3D = () => {
    if (cells.length === 0) { alert("请先添加栅元"); return; }
    setShow3D(true);
  };
  const handleExportSTEP = async () => {
    try {
      const r = await fetch("http://localhost:5001/api/export-step",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({surfaces:surfText,cells:cells})});
      const j = await r.json();
      if (j.status !== "ok") { alert(j.message || "导出失败"); return; }
      // 获取文件内容（支持新旧格式）
      let content: string;
      if (j.data) {
        content = atob(j.data);
      } else {
        // 旧格式：通过 serve-file 端点获取
        const fr = await fetch("http://localhost:5001/api/serve-file?path=" + encodeURIComponent(j.file));
        content = await fr.text();
      }
      const buf = new Uint8Array(content.length);
      for (let i = 0; i < content.length; i++) buf[i] = content.charCodeAt(i);
      const blob = new Blob([buf], { type: "model/step" });
      if ((window as any).showSaveFilePicker) {
        const handle = await (window as any).showSaveFilePicker({ suggestedName: "mcnp_export.step", types: [{ description: "STEP 文件", accept: { "model/step": [".step", ".stp"] } }] });
        const ws = await handle.createWritable();
        await ws.write(blob);
        await ws.close();
      } else {
        const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "mcnp_export.step"; a.click();
      }
    } catch(e) { alert("导出失败: " + ((e as any)?.message || e)); }
  };
  const handleRawCells = (t: string) => patch({ rawOverrides: { ...deck.rawOverrides, cells: t } });

  // local → deck（只推 cells，曲面/TR 由 DOM 采集，避免频闪）
  const lastCellsRef = useRef("");
  const lastSurfRef = useRef("");
  const lastTrRef = useRef("");
  useEffect(() => {
    // local → deck：cells / surfaces / tr 全部受控推送（仅值真正变化时才 patch）
    const curCells = JSON.stringify(cells.map(c => ({ number: parseInt(c.num)||0, material: c.mat, density: c.density, surface_expr: c.surfaces, imp_n: c.impN, imp_p: c.impP, imp_e: c.impE, vol: c.vol, pwt: c.pwt, ext: c.ext, fcl: c.fcl, u: c.u, fill: c.fill, lat: c.lat, trcl: c.trcl, tmp: c.tmp, other_params: c.otherParams, render: c.render, comment: c.comment })));
    const p: Record<string, any> = {};
    if (curCells !== lastCellsRef.current) { lastCellsRef.current = curCells; p.cells = JSON.parse(curCells); }
    if (surfText !== lastSurfRef.current) { lastSurfRef.current = surfText; p.surfaces = surfText; }
    if (trText !== lastTrRef.current) { lastTrRef.current = trText; p.tr_cards = trText; }
    if (Object.keys(p).length) patch(p);
  }, [cells, surfText, trText]);
  useEffect(() => {
    const newSurf = deck.surfaces || "";
    const newTr = deck.tr_cards || "";
    const newCells = deck.cells?.length ? deck.cells.map(c => ({ num: String(c.number), mat: c.material, density: c.density, surfaces: c.surface_expr, impN: c.imp_n || "", impP: c.imp_p || "", impE: c.imp_e || "", vol: c.vol || "", pwt: c.pwt || "", ext: c.ext || "", fcl: c.fcl || "", u: c.u || "", fill: c.fill || "", lat: c.lat || "", trcl: c.trcl || "", tmp: c.tmp || "", otherParams: c.other_params || "", render: c.render !== false, comment: c.comment || "" })) : [];
    if (newSurf !== surfText) setSurfText(newSurf);
    if (newTr !== trText) setTrText(newTr);
    if (newCells.length && JSON.stringify(newCells) !== JSON.stringify(cellsRef.current)) {
      setCells(newCells);
    }
  }, [deck.surfaces, deck.tr_cards, deck.cells]);

  return (
    <>
      {editCell !== null && <CellEditDialog cell={cells[editCell]} onSave={(d) => { const c = [...cells]; c[editCell] = d; setCells(c); setEditCell(null); }} onClose={() => setEditCell(null)} availableMats={deck.materials} />}
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title" style={{ flexShrink: 0 }}>曲面卡 &amp; TR 变换</span>
          <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
            <button className="btn btn-ghost btn-xs" onClick={() => setDoc({path:"/docs/MCNP6_曲面卡格式参考.md",title:"曲面卡格式参考"})}>📖 曲面参考</button>
          </div>
        </div>
        <div style={{display:"flex", gap:12}}>
          <div className="form-group" style={{flex:3}}>
            <label className="form-label">曲面卡（每行一个，支持所有 MCNP 曲面类型）</label>
            <McnpEditor id="geo-surfaces" value={surfText} onChange={setSurfText} mode="surface" minHeight={180}
              placeholder="1  PX  -9   $ X垂面" />
          </div>
          <div className="form-group" style={{flex:2}}>
            <label className="form-label">TR 变换卡（*TRn  Tx Ty Tz  B1..B9）</label>
            <McnpEditor id="geo-tr" value={trText} onChange={setTrText} mode="tr" minHeight={180}
              placeholder="TR1  0 0 0  30 60 90" />
          </div>
        </div>
        {/* 3D 预览 & STEP 操作按钮 */}
        <div style={{display:"flex", gap:8, justifyContent:"flex-end", marginTop:8}}>
          <span style={{fontSize:11, color:freecadOk ? "#2e7d32" : "#c62828", alignSelf:"center"}}>{freecadOk === null ? "检测中..." : freecadOk ? "✅ FreeCAD 已安装" : "⚠ 需要 FreeCAD"}</span>
          {freecadOk === false && <button className="btn btn-ghost btn-xs" onClick={async () => {
            try {
              const r1 = await fetch("http://localhost:5001/api/choose-freecad-path", { method: "POST" });
              const j1 = await r1.json();
              if (j1.cancelled || !j1.path) return;
              const r2 = await fetch("http://localhost:5001/api/set-freecad-path", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: j1.path }),
              });
              const j2 = await r2.json();
              if (j2.status !== "ok") { alert(j2.message || "设置失败"); return; }
              const r3 = await fetch("http://localhost:5001/api/check-freecad", { method: "POST" });
              const j3 = await r3.json();
              if (j3.status === "ok") setFreecadOk(j3.found);
            } catch (e: any) { alert("设置失败: " + (e?.message || "")); }
          }}>指定 FreeCAD 路径</button>}
          <button className="btn btn-ghost btn-xs" onClick={() => setShowStepDlg(true)}>📥 导入 STEP</button>
          <button className="btn btn-primary btn-xs" onClick={handlePreview3D}>🔍 3D 预览</button>
          <button className="btn btn-ghost btn-xs" onClick={handleExportSTEP}>📐 导出 STEP</button>
        </div>
      </div>
      <div className="glass-card">
        <TextModeSection label="栅元列表" active={cellRawMode} onToggle={() => setCellRawMode(!cellRawMode)} onDiscard={() => { setCellRawMode(false); setCellRawText(""); patch({rawOverrides:{...deck.rawOverrides,cells:""}}); }} />
        {cellRawMode ? (
          <textarea className="form-input" value={cellRawText} onChange={e => {setCellRawText(e.target.value);patch({rawOverrides:{...deck.rawOverrides,cells:e.target.value}});}}
            style={{width:"100%",minHeight:200,fontFamily:"Consolas,monospace",fontSize:12}} placeholder="栅元卡原始文本..." />
        ) : (
        <><div className="card-header">
          <span className="card-title">栅元列表</span>
          <div className="btn-group">
            <button className="btn btn-success btn-xs" onClick={() => setCells([...cells, { num:String(cells.length+1), mat:"0", density:"", surfaces:"", impN:"", impP:"", impE:"", vol:"", pwt:"", ext:"", fcl:"", u:"", fill:"", lat:"", trcl:"", tmp:"", otherParams:"", render:false, comment:"" }])}>+ 添加</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>#</th><th>材料</th><th>密度</th><th>曲面表达式</th><th>IMP:N</th><th>注释</th><th>操作</th></tr></thead>
            <tbody>
              {cells.map((c, i) => (
                <tr key={c.num}>
                  <td style={{fontWeight:600,color:"var(--text-primary)"}}>{c.num}</td>
                  <td>{c.mat}</td><td>{c.density}</td><td>{c.surfaces}</td><td>{c.impN}</td>
                  <td style={{fontSize:11,color:"var(--text-secondary)",maxWidth:120,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{c.comment||"—"}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="btn btn-ghost btn-xs" onClick={() => setEditCell(i)}>✎</button>
                    <button className="btn btn-danger btn-xs" onClick={() => setCells(cells.filter((_, j) => j !== i))}>×</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>)}
      </div>
      {doc && <DocViewer path={doc.path} title={doc.title} onClose={() => setDoc(null)} />}
      {show3D && <Preview3D cells={cells} surfaces={surfText} trCards={trText} onClose={() => setShow3D(false)} />}
      {showStepDlg && <StepImportDialog onImport={handleStepImport} onClose={() => setShowStepDlg(false)} />}
    </>
  );
}
