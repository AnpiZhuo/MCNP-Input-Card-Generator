import React, { useState, useEffect, useRef } from "react";
import CellEditDialog, { type CellData } from "./CellEditDialog";
import McnpEditor from "./McnpEditor";
import TextModeSection from "./TextModeSection";
import DocViewer from "./DocViewer";
import Preview3D from "./Preview3D";
import StepImportDialog from "./StepImportDialog";
import FloatingDialog from "./FloatingDialog";
import { useDeck } from "../utils/DeckContext";
import { useFreecadStatus } from "../utils/useFreecadStatus";

interface GeoProps {
  pendingCellFromMaterial?: number;
}

/** 本地栅元行：真正的栅元(camelCase) 或原样条件行 */
type LocalCellRow = { kind: "cell"; cell: CellData } | { kind: "raw"; text: string };

export default function GeometryTab({ pendingCellFromMaterial }: GeoProps) {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const [cells, setCells] = useState<LocalCellRow[]>([]);
  const cellDragIdx = useRef<number | null>(null);
  const addCellRow = () => setCells([...cells, { kind: "cell", cell: { num:String(cells.length+1), mat:"0", density:"", surfaces:"", impN:"", impP:"", impE:"", vol:"", pwt:"", ext:"", fcl:"", u:"", fill:"", lat:"", trcl:"", tmp:"", otherParams:"", render:false, comment:"" } }]);
  const addRawCell = (text: string) => setCells([...cells, { kind: "raw", text }]);
  const addConditionalCells = () => {
    const name = window.prompt("条件名（如 ENDF7）", "ENDF7");
    if (name === null) return;
    setCells([...cells, { kind: "raw", text: `#ifdef ${name.trim()}` }, { kind: "raw", text: "#else" }, { kind: "raw", text: "#endif" }]);
  };
  const moveCellRow = (from: number, to: number) => {
    if (from === to) return;
    const c = [...cells]; const [m] = c.splice(from, 1); c.splice(to, 0, m); setCells(c);
  };
  const [editCell, setEditCell] = useState<number | null>(null);
  const [surfText, setSurfText] = useState("");
  const [trText, setTrText] = useState("");
  const [cellRawMode, setCellRawMode] = useState(false);
  const [cellRawText, setCellRawText] = useState("");
  const [show3D, setShow3D] = useState(false);
  const [showStepDlg, setShowStepDlg] = useState(false);
  const fc = useFreecadStatus();
  const cellsRef = useRef(cells);
  cellsRef.current = cells;
  const surfRef = useRef(surfText);
  surfRef.current = surfText;
  const trRef = useRef(trText);
  trRef.current = trText;
  const { deck, patch } = useDeck();

  // 材料→栅元联动：新材料添加时自动创建栅元行
  useEffect(() => {
    if (pendingCellFromMaterial && pendingCellFromMaterial > 0) {
      const maxNum = cells.length > 0 ? Math.max(...cells.map(c => c.kind === "cell" ? parseInt(c.cell.num) || 0 : 0)) : 0;
      setCells([...cells, { kind: "cell", cell: {
        num: String(maxNum + 1), mat: String(pendingCellFromMaterial),
        density: "-1.0", surfaces: "", impN: "", impP: "", impE: "",
        vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "",
        trcl: "", tmp: "", otherParams: "", render: true,
        comment: `材料 M${pendingCellFromMaterial} 对应栅元`,
      } }]);
    }
  }, [pendingCellFromMaterial]);

  const handleStepImport = async (settings: any, file: File) => {
    if (!fc.require()) { setShowStepDlg(false); return; }
    try {
      const text = await file.text();
      const r = await fetch("http://localhost:5001/api/import-step", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, data: text, settings }),
      });
      const j = await r.json();
      if (j.status === "ok" && j.deck) {
        patch({ surfaces: j.deck.surfaces || "", tr_cards: j.deck.tr_cards || "", cells: j.deck.cells || [] });
        alert("✅ STEP 导入成功");
        setShowStepDlg(false);
        return;
      }
      alert(j.message || "STEP 导入失败");
    } catch {
      alert("STEP 导入需要后端服务");
    }
    setShowStepDlg(false);
  };
  const handlePreview3D = () => {
    if (cells.length === 0) { alert("请先添加栅元"); return; }
    if (!fc.require()) return;
    setShow3D(true);
  };
  const handleExportSTEP = async () => {
    if (!fc.require()) return;
    try {
      const r = await fetch("http://localhost:5001/api/export-step",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({surfaces:surfText,cells:cells,tr_cards:trText})});
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

  // 3D 预览里点击材料号改材料 → 更新本地 cells，local→deck 同步自动 patch
  const handleCellMaterialChange = (cellNum: string, newMat: string) => {
    setCells(prev => prev.map(c => c.kind === "cell" && c.cell.num === cellNum ? { ...c, cell: { ...c.cell, mat: newMat } } : c));
  };

  // local → deck（只推 cells，曲面/TR 由 DOM 采集，避免频闪）
  const lastCellsRef = useRef("");
  const lastSurfRef = useRef("");
  const lastTrRef = useRef("");
  useEffect(() => {
    // local → deck：cells（CellRow 判别联合）/ surfaces / tr 全部受控推送
    const curCells = JSON.stringify(cells.map(c => c.kind === "raw"
      ? { kind: "raw", text: c.text }
      : { kind: "cell", cell: { number: parseInt(c.cell.num) || 0, material: c.cell.mat, density: c.cell.density, surface_expr: c.cell.surfaces, imp_n: c.cell.impN, imp_p: c.cell.impP, imp_e: c.cell.impE, vol: c.cell.vol, pwt: c.cell.pwt, ext: c.cell.ext, fcl: c.cell.fcl, u: c.cell.u, fill: c.cell.fill, lat: c.cell.lat, trcl: c.cell.trcl, tmp: c.cell.tmp, other_params: c.cell.otherParams, render: c.cell.render, comment: c.cell.comment } }));
    const p: Record<string, any> = {};
    if (curCells !== lastCellsRef.current) { lastCellsRef.current = curCells; p.cells = JSON.parse(curCells); }
    if (surfText !== lastSurfRef.current) { lastSurfRef.current = surfText; p.surfaces = surfText; }
    if (trText !== lastTrRef.current) { lastTrRef.current = trText; p.tr_cards = trText; }
    if (Object.keys(p).length) patch(p);
  }, [cells, surfText, trText]);
  useEffect(() => {
    const newSurf = deck.surfaces || "";
    const newTr = deck.tr_cards || "";
    const newCells = deck.cells?.length ? deck.cells.map((c: any) =>
      c.kind === "raw"
        ? { kind: "raw" as const, text: c.text }
        : { kind: "cell" as const, cell: { num: String(c.cell.number), mat: c.cell.material, density: c.cell.density, surfaces: c.cell.surface_expr, impN: c.cell.imp_n || "", impP: c.cell.imp_p || "", impE: c.cell.imp_e || "", vol: c.cell.vol || "", pwt: c.cell.pwt || "", ext: c.cell.ext || "", fcl: c.cell.fcl || "", u: c.cell.u || "", fill: c.cell.fill || "", lat: c.cell.lat || "", trcl: c.cell.trcl || "", tmp: c.cell.tmp || "", otherParams: c.cell.other_params || "", render: c.cell.render !== false, comment: c.cell.comment || "" } }
    ) : [];
    if (newSurf !== surfText) setSurfText(newSurf);
    if (newTr !== trText) setTrText(newTr);
    if (newCells.length && JSON.stringify(newCells) !== JSON.stringify(cellsRef.current)) {
      setCells(newCells);
    }
  }, [deck.surfaces, deck.tr_cards, deck.cells]);

  return (
    <>
      {editCell !== null && cells[editCell]?.kind === "cell" && <CellEditDialog cell={cells[editCell].cell} onSave={(d) => { const c = [...cells]; c[editCell] = { kind: "cell", cell: d }; setCells(c); setEditCell(null); }} onClose={() => setEditCell(null)} availableMats={deck.materials} />}
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
          <span style={{fontSize:11, color:fc.status === "ok" ? "#2e7d32" : "#c62828", alignSelf:"center"}}>{fc.status === "checking" ? "检测中..." : fc.status === "ok" ? "✅ FreeCAD 已安装" : "⚠ 需要 FreeCAD"}</span>
          {fc.status === "missing" && <button className="btn btn-ghost btn-xs" onClick={fc.pickPath}>指定 FreeCAD 路径</button>}
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
          <span className="card-title">栅元列表（所有行可拖动排序）</span>
          <div className="btn-group">
            <button className="btn btn-success btn-xs" onClick={addCellRow}>+ 栅元</button>
            <button className="btn btn-ghost btn-xs" onClick={addConditionalCells} title="插入 #ifdef 名称 / #else / #endif 三行"># 条件</button>
            <button className="btn btn-ghost btn-xs" onClick={() => addRawCell("#ifdef ENDF7")}># 行</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>#</th><th>材料</th><th>密度</th><th>曲面表达式</th><th>IMP:N</th><th>注释</th><th>操作</th></tr></thead>
            <tbody>
              {cells.map((c, i) => c.kind === "raw" ? (
                <tr key={i} draggable onDragStart={(e) => { cellDragIdx.current = i; e.dataTransfer.effectAllowed = "move"; }} onDragOver={(e) => e.preventDefault()} onDrop={() => { if (cellDragIdx.current !== null) { moveCellRow(cellDragIdx.current, i); cellDragIdx.current = null; } }}
                  style={{ background: "rgba(255,255,255,0.04)", cursor: "grab" }}>
                  <td colSpan={6} style={{ fontFamily: "Consolas,monospace", fontSize: 12, color: "#ce93d8" }}>{c.text}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="btn btn-danger btn-xs" onClick={() => setCells(cells.filter((_, j) => j !== i))}>×</button>
                  </td>
                </tr>
              ) : (
                <tr key={i} draggable onDragStart={(e) => { cellDragIdx.current = i; e.dataTransfer.effectAllowed = "move"; }} onDragOver={(e) => e.preventDefault()} onDrop={() => { if (cellDragIdx.current !== null) { moveCellRow(cellDragIdx.current, i); cellDragIdx.current = null; } }}
                  style={{ cursor: "grab" }}>
                  <td style={{fontWeight:600,color:"var(--text-primary)"}}>{c.cell.num}</td>
                  <td>{c.cell.mat}</td><td>{c.cell.density}</td><td>{c.cell.surfaces}</td><td>{c.cell.impN}</td>
                  <td style={{fontSize:11,color:"var(--text-secondary)",maxWidth:120,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{c.cell.comment||"—"}</td>
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
      {show3D && <Preview3D cells={cells.filter(c => c.kind === "cell").map(c => ({ num: c.cell.num, mat: c.cell.mat, density: c.cell.density, surfaces: c.cell.surfaces, comment: c.cell.comment, render: c.cell.render }))} surfaces={surfText} trCards={trText} onClose={() => setShow3D(false)} onMaterialChange={handleCellMaterialChange} />}
      {showStepDlg && <StepImportDialog onImport={handleStepImport} onClose={() => setShowStepDlg(false)} />}
      {fc.showDialog && <FloatingDialog title="⚠ 需要 FreeCAD" onClose={fc.closeDialog} width={460}
        footer={React.createElement("button", { className: "btn btn-primary btn-sm", onClick: fc.closeDialog }, "知道了")}>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.7 }}>
          <p>未检测到 FreeCAD。STEP 导入 / 导出 / 3D 预览 需要 FreeCAD 参与几何计算。</p>
          <p>请前往 <a href="https://www.freecad.org/downloads.php?lang=zh_CN" target="_blank" rel="noreferrer" style={{ color: "var(--accent)", textDecoration: "underline" }}>FreeCAD 官网下载</a>，安装后在本页点「指定 FreeCAD 路径」。</p>
        </div>
      </FloatingDialog>}
    </>
  );
}
