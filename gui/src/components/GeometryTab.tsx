import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import CellEditDialog, { type CellData } from "./CellEditDialog";
import McnpEditor from "./McnpEditor";
import TextModeSection from "./TextModeSection";
import DocViewer from "./DocViewer";
import Preview3D from "./Preview3D";
import StepImportDialog from "./StepImportDialog";
import QuickCellDialog from "./QuickCellDialog";
import FloatingDialog from "./FloatingDialog";
import { useDeck } from "../utils/DeckContext";
import { useFreecadStatus } from "../utils/useFreecadStatus";
import { useRowDrag } from "../utils/useRowDrag";
import { openPreview3D, onMaterialChange, onQuickCellGenerate } from "../utils/windows";
import { apiUrl } from "../utils/api";
import { useSectionTextMode } from "../utils/useSectionTextMode";
import { textToSection } from "../utils/sectionConvert";
import { appendCardText, applyQuickAddChoice, generatedCellToRow, type QuickAddChoice, type QuickCellResult } from "../utils/quickCell";

/** 下拉右缘防溢出：x 超过视口右缘时 clamp 到 viewportWidth - dropdownWidth - 20。
 *  对齐现行为（现 220 = 200 宽 + 20 边距）。viewportWidth 为 0/负数时 Math.min 自然兜底（返回 min(x, 负数)）。 */
export function clampDropdownLeft(x: number, viewportWidth: number, dropdownWidth = 200): number {
  return Math.min(x, viewportWidth - dropdownWidth - 20);
}

interface GeoProps {
  pendingCellFromMaterial?: number;
}

/** 本地栅元行：真正的栅元(camelCase) 或原样条件行 */
type LocalCellRow = { kind: "cell"; cell: CellData } | { kind: "raw"; text: string };

export default function GeometryTab({ pendingCellFromMaterial }: GeoProps) {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const [cells, setCells] = useState<LocalCellRow[]>([]);
  const moveCellRow = (from: number, to: number) => {
    if (from === to) return;
    const c = [...cells]; const [m] = c.splice(from, 1); c.splice(to, 0, m); setCells(c);
  };
  const cellDrag = useRowDrag(moveCellRow);
  const addCellRow = () => setCells([...cells, { kind: "cell", cell: { num:String(cells.length+1), mat:"0", density:"", surfaces:"", impN:"", impP:"", impE:"", vol:"", pwt:"", ext:"", fcl:"", u:"", fill:"", lat:"", trcl:"", tmp:"", otherParams:"", render:false, comment:"" } }]);
  const addRawCell = (text: string) => setCells([...cells, { kind: "raw", text }]);
  const addConditionalCells = () => {
    const name = window.prompt("条件名（如 ENDF7）", "ENDF7");
    if (name === null) return;
    setCells([...cells, { kind: "raw", text: `#ifdef ${name.trim()}` }, { kind: "raw", text: "#else" }, { kind: "raw", text: "#endif" }]);
  };
  const [editCell, setEditCell] = useState<number | null>(null);
  const [surfText, setSurfText] = useState("");
  const [trText, setTrText] = useState("");
  const [show3D, setShow3D] = useState(false);
  const [showStepDlg, setShowStepDlg] = useState(false);
  const [quickCellOpen, setQuickCellOpen] = useState(false);
  const [quickCheck, setQuickCheck] = useState<{
    result: QuickCellResult;
    overlaps: any[];
    recommended: "new_hole" | "existing_hole" | "none";
    existingNums: number[];
    zeroVolume: number[];
  } | null>(null);
  // 栅元表材料列点击下拉：i=正在编辑材料号的栅元行索引，x/y=按钮位置（用于 portal 定点浮层）
  const [matPicker, setMatPicker] = useState<{ i: number; x: number; y: number } | null>(null);
  const fc = useFreecadStatus();
  const cellsRef = useRef(cells);
  cellsRef.current = cells;
  const surfRef = useRef(surfText);
  surfRef.current = surfText;
  const trRef = useRef(trText);
  trRef.current = trText;
  const { deck, patch } = useDeck();

  // 文本↔表单互转（深模块：逻辑在 useSectionTextMode 一处）
  // 切回表单时，把解析出的 cells（后端 CellRow 判别联合）映射回本地 LocalCellRow
  const cellsText = useSectionTextMode("cells", {
    deck, patch, overrideKey: "cells",
    onBackToForm: (data) => {
      const arr: any[] = data.cells || [];
      const mapped = arr.map((c: any) => {
        if (c?.kind === "raw") return { kind: "raw" as const, text: c.text };
        const cell = c?.kind === "cell" ? c.cell : c;
        return { kind: "cell" as const, cell: { num: String(cell?.number ?? cell?.num ?? ""), mat: cell?.material ?? cell?.mat ?? "", density: cell?.density ?? "", surfaces: cell?.surface_expr ?? cell?.surfaces ?? "", impN: cell?.imp_n ?? cell?.impN ?? "", impP: cell?.imp_p ?? cell?.impP ?? "", impE: cell?.imp_e ?? cell?.impE ?? "", vol: cell?.vol ?? "", pwt: cell?.pwt ?? "", ext: cell?.ext ?? "", fcl: cell?.fcl ?? "", u: cell?.u ?? "", fill: cell?.fill ?? "", lat: cell?.lat ?? "", trcl: cell?.trcl ?? "", tmp: cell?.tmp ?? "", otherParams: cell?.other_params ?? cell?.otherParams ?? "", render: cell?.render !== false, comment: cell?.comment ?? "" } };
      });
      if (mapped.length) setCells(mapped);
    },
    initialText: deck.rawOverrides?.cells || "",
    initialMode: deck.textMode?.cells,
  });
  const { rawMode: cellRawMode, rawText: cellRawText, busy: cellBusy, setRawText: setCellRawText, toggleRawMode: toggleCellRawMode, onDiscard: discardCellRaw } = cellsText;

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
      const r = await fetch(apiUrl("/api/import-step"), {
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
  const handlePreview3D = async () => {
    if (cells.length === 0 && !cellRawMode) { alert("请先添加栅元"); return; }
    if (!fc.require()) return;
    // 若栅元在文本模式：先解析文本回填表单 cells，再取表单 cells 预览（用当前实际内容）
    if (cellRawMode) {
      const txt = cellRawText || deck.rawOverrides?.cells || "";
      if (txt.trim()) {
        try {
          const data = await textToSection("cells", txt);
          const arr: any[] = data.cells || [];
          const mapped = arr.map((c: any) => {
            if (c?.kind === "raw") return { kind: "raw" as const, text: c.text };
            const cell = c?.kind === "cell" ? c.cell : c;
            return { kind: "cell" as const, cell: { num: String(cell?.number ?? cell?.num ?? ""), mat: cell?.material ?? cell?.mat ?? "", density: cell?.density ?? "", surfaces: cell?.surface_expr ?? cell?.surfaces ?? "", impN: cell?.imp_n ?? cell?.impN ?? "", impP: cell?.imp_p ?? cell?.impP ?? "", impE: cell?.imp_e ?? cell?.impE ?? "", vol: cell?.vol ?? "", pwt: cell?.pwt ?? "", ext: cell?.ext ?? "", fcl: cell?.fcl ?? "", u: cell?.u ?? "", fill: cell?.fill ?? "", lat: cell?.lat ?? "", trcl: cell?.trcl ?? "", tmp: cell?.tmp ?? "", otherParams: cell?.other_params ?? cell?.otherParams ?? "", render: cell?.render !== false, comment: cell?.comment ?? "" } };
          });
          if (mapped.length) setCells(mapped);
        } catch (e: any) {
          alert("栅元文本解析失败: " + (e?.message || e));
          return;
        }
      }
    }
    // 3D 预览 → 独立系统窗口（Tauri）；浏览器模式回退原有覆盖层
    const opened = await openPreview3D({
      cells: cells.filter(c => c.kind === "cell").map(c => ({
        num: (c as any).cell.num, mat: (c as any).cell.mat,
        density: (c as any).cell.density, surfaces: (c as any).cell.surfaces,
        comment: (c as any).cell.comment, render: (c as any).cell.render,
      })),
      surfaces: surfText,
      trCards: trText,
      deck,
    });
    if (!opened) setShow3D(true); // 非 Tauri 环境回退
  };
  const handleExportSTEP = async () => {
    if (!fc.require()) return;
    try {
      const r = await fetch(apiUrl("/api/export-step"),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({surfaces:surfText,cells:cells,tr_cards:trText})});
      const j = await r.json();
      if (j.status !== "ok") { alert(j.message || "导出失败"); return; }
      // 获取文件内容（支持新旧格式）
      let content: string;
      if (j.data) {
        content = atob(j.data);
      } else {
        // 旧格式：通过 serve-file 端点获取
        const fr = await fetch(apiUrl("/api/serve-file?path=" + encodeURIComponent(j.file)));
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

  // 快捷建栅元：文本模式禁用（弹窗警告）；生成结果追加到曲面卡/TR 卡/栅元列表
  const openQuickCell = () => {
    if (cellRawMode) {
      alert("栅元当前处于文本模式。请先切回表单模式并检查内容，再使用「快捷建栅元」。");
      return;
    }
    setQuickCellOpen(true);
  };
  const handleQuickCellGenerate = (result: QuickCellResult) => {
    const nextSurf = appendCardText(surfTextRef.current, result.surfacesText);
    const nextTr = appendCardText(trTextRef.current, result.trCardsText);
    setSurfText(nextSurf);
    setTrText(nextTr);
  const newRows = result.cells.map(generatedCellToRow);
  // 生成入口（3D 预览）已处理重合决策：应用补丁后直接加入，不再重复弹窗
  if (result.existingExprPatch && result.existingExprPatch.length) {
    const patchMap = new Map(result.existingExprPatch.map(p => [p.num, p.surfaces]));
    setCells(prev => prev.map(c => c.kind === "cell" && patchMap.has(c.cell.num)
      ? { ...c, cell: { ...c.cell, surfaces: patchMap.get(c.cell.num)! } }
      : c));
  }
  if (result.overlapHandled || result.checkOverlap === false) {
    setCells(prev => [...prev, ...newRows]);
    return;
  }
    // 快捷添加重合检查：新栅元 vs 已有 → 弹出 A/B/C 补集决策
    const cellRows = newRows.filter(r => r.kind === "cell");
    if (!cellRows.length) { setCells(prev => [...prev, ...newRows]); return; }
    const newCellsPayload = cellRows.map(r => ({
      number: parseInt(r.cell.num, 10) || 0,
      material: r.cell.mat,
      density: r.cell.density,
      surface_expr: r.cell.surfaces,
    }));
    const existingCells = cellsRef.current.filter(c => c.kind === "cell").map(c => ({
      kind: "cell",
      cell: {
        number: parseInt(c.cell.num, 10) || 0,
        material: c.cell.mat,
        density: c.cell.density,
        surface_expr: c.cell.surfaces,
      },
    }));
    (async () => {
      try {
        const r = await fetch(apiUrl("/api/quick-add-check"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            surfaces: nextSurf,
            cells: existingCells,
            tr_cards: nextTr,
            new_cells: newCellsPayload,
          }),
          signal: AbortSignal.timeout(60000),
        });
        const j = await r.json();
        if (j.status !== "error" && j.overlaps && j.overlaps.length > 0) {
          const newNums = new Set(newCellsPayload.map(c => c.number));
          const existingNums = Array.from(new Set<number>(
            j.overlaps
              .filter((o: any) => newNums.has(o.a) !== newNums.has(o.b))
              .map((o: any) => Number(newNums.has(o.a) ? o.b : o.a)),
          ));
          setQuickCheck({
            result, overlaps: j.overlaps, recommended: j.recommended,
            existingNums, zeroVolume: j.zero_volume || [],
          });
          return;
        }
      } catch (e) { /* 检测失败 → 直接追加，不影响生成 */ }
      setCells(prev => [...prev, ...newRows]);
    })();
  };

  // 快捷添加补集决策（纯函数，支持多栅元）：A=新避开已有 / B=已有让位 / D=只占真空 / C=不处理
  const applyQuickCheck = (choice: QuickAddChoice) => {
    if (!quickCheck) return;
    const qc = quickCheck;
    const existing = cells.filter(c => c.kind === "cell").map(c => ({
      num: parseInt(c.cell.num, 10),
      mat: c.cell.mat,
      surfaces: c.cell.surfaces,
    }));
    const patched = applyQuickAddChoice(qc.result, qc.overlaps, existing, choice);
    if (patched.existingExprPatch && patched.existingExprPatch.length) {
      const patchMap = new Map(patched.existingExprPatch.map(p => [p.num, p.surfaces]));
      setCells(prev => prev.map(c => c.kind === "cell" && patchMap.has(c.cell.num)
        ? { ...c, cell: { ...c.cell, surfaces: patchMap.get(c.cell.num)! } }
        : c));
    }
    setCells(prev => [...prev, ...patched.cells.map(generatedCellToRow)]);
    setQuickCheck(null);
  };

  // 3D 预览里点击材料号改材料 → 更新本地 cells，local→deck 同步自动 patch
  const handleCellMaterialChange = (cellNum: string, newMat: string) => {
    setCells(prev => prev.map(c => c.kind === "cell" && c.cell.num === cellNum ? { ...c, cell: { ...c.cell, mat: newMat } } : c));
  };

  // 主页面栅元表：点击材料号选材料 → 更新材料号 + 自动填充该材料密度
  const applyMatFromPicker = (i: number, newMat: string) => {
    const m = newMat.trim();
    if (!m) return;
    setCells(prev => prev.map((c, ci) => {
      if (ci !== i || c.kind !== "cell") return c;
      const next = { ...c, cell: { ...c.cell, mat: m } };
      // 自动填充密度：查 deck.materials 对应材料（M0 真空 → 密度清空）
      if (m === "0") {
        next.cell.density = "";
      } else {
        const found = deck.materials.find(mt => String(mt.number) === m);
        if (found && found.density) next.cell.density = found.density;
      }
      return next;
    }));
    setMatPicker(null);
  };

  // 材料选项（与 3D 预览一致）：M0 真空 + deck.materials（带注释）
  const matOptions: { num: string; label: string; density: string }[] = [
    { num: "0", label: "M0 - 真空", density: "" },
    ...deck.materials.map(mt => ({
      num: String(mt.number),
      label: `M${mt.number}${mt.comment ? " - " + mt.comment : ""}`,
      density: mt.density || "",
    })),
  ].sort((a, b) => parseInt(a.num) - parseInt(b.num));

  // 独立 3D 窗口里改材料号 → storage 事件回写主窗口（双向同步）
  useEffect(() => {
    const offMat = onMaterialChange((cellNum, newMat) => {
      setCells(prev => prev.map(c => c.kind === "cell" && c.cell.num === cellNum ? { ...c, cell: { ...c.cell, mat: newMat } } : c));
    });
    // 独立 3D 窗口里快捷建栅元 → storage 事件回写主窗口（追加曲面/TR/栅元）
    const offQuick = onQuickCellGenerate(handleQuickCellGenerate);
    return () => { offMat(); offQuick(); };
  }, []);

  // local → deck（只推 cells，曲面/TR 由 DOM 采集，避免频闪）
  const lastCellsRef = useRef("");
  const lastSurfRef = useRef("");
  const lastTrRef = useRef("");
  // 最新值 ref（快捷添加重合检测请求用，避免 state 未 flush 读到旧文本）
  const surfTextRef = useRef(surfText);
  const trTextRef = useRef(trText);
  surfTextRef.current = surfText;
  trTextRef.current = trText;
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
    const newCells = deck.cells?.length ? deck.cells.map((c: any) => {
      if (c?.kind === "raw") return { kind: "raw" as const, text: c.text };
      // CellRow（嵌套 cell）或旧平铺格式（STEP 导入）都兼容
      const cell = c?.kind === "cell" ? c.cell : c;
      return { kind: "cell" as const, cell: { num: String(cell?.number ?? cell?.num ?? ""), mat: cell?.material ?? cell?.mat ?? "", density: cell?.density ?? "", surfaces: cell?.surface_expr ?? cell?.surfaces ?? "", impN: cell?.imp_n ?? cell?.impN ?? "", impP: cell?.imp_p ?? cell?.impP ?? "", impE: cell?.imp_e ?? cell?.impE ?? "", vol: cell?.vol ?? "", pwt: cell?.pwt ?? "", ext: cell?.ext ?? "", fcl: cell?.fcl ?? "", u: cell?.u ?? "", fill: cell?.fill ?? "", lat: cell?.lat ?? "", trcl: cell?.trcl ?? "", tmp: cell?.tmp ?? "", otherParams: cell?.other_params ?? cell?.otherParams ?? "", render: cell?.render !== false, comment: cell?.comment ?? "" } };
    }) : [];
    if (newSurf !== surfText) setSurfText(newSurf);
    if (newTr !== trText) setTrText(newTr);
    if (newCells.length && JSON.stringify(newCells) !== JSON.stringify(cellsRef.current)) {
      setCells(newCells);
    }
  }, [deck.surfaces, deck.tr_cards, deck.cells]);

  return (
    <>
      {editCell !== null && cells[editCell]?.kind === "cell" && <CellEditDialog cell={cells[editCell].cell} onSave={(d) => { const c = [...cells]; c[editCell] = { kind: "cell", cell: d }; setCells(c); setEditCell(null); }} onClose={() => setEditCell(null)} availableMats={deck.materials} />}
      {quickCellOpen && <QuickCellDialog
        surfacesText={surfText}
        trCardsText={trText}
        cellNumbers={cells.filter((c) => c.kind === "cell").map((c) => parseInt(c.cell.num, 10) || 0)}
        materials={(deck.materials || []).map((m) => ({ number: m.number, comment: m.comment, density: m.density }))}
        modeN={!!(deck.basic as any)?.mode_n}
        modeP={!!(deck.basic as any)?.mode_p}
        modeE={!!(deck.basic as any)?.mode_e}
        onClose={() => setQuickCellOpen(false)}
        onGenerate={handleQuickCellGenerate}
      />}
      {quickCheck && (() => {
        const qc = quickCheck;
        const others = qc.existingNums;
        return React.createElement(FloatingDialog, {
          title: `新栅元与栅元 ${others.join("、")} 重合`,
          onClose: () => applyQuickCheck("none"),
          width: 440,
        },
          React.createElement("div", { style: { fontSize: 12, lineHeight: 1.8 } },
            React.createElement("div", { style: { marginBottom: 8, color: "var(--text-secondary)" } }, "选择如何处理（点击即应用）："),
            qc.zeroVolume.length > 0
              ? React.createElement("div", { style: { marginBottom: 8, color: "#e53935", fontSize: 11 } },
                  `⚠ 体积为零的栅元：${qc.zeroVolume.join("、")}（空/退化几何，请检查参数）`)
              : null,
            React.createElement("button", { className: "btn btn-sm", style: { display: "block", width: "100%", marginBottom: 6, textAlign: "left" },
              onClick: () => applyQuickCheck("new_hole") },
              `新栅元避开已有（新 # ${others.join(" #") || "—"}）${qc.recommended === "new_hole" ? "  · 推荐" : ""}`),
            React.createElement("button", { className: "btn btn-sm", style: { display: "block", width: "100%", marginBottom: 6, textAlign: "left" },
              onClick: () => applyQuickCheck("existing_hole") },
              `被侵占栅元让位（${others.join("、") || "—"} # 新栅元）${qc.recommended === "existing_hole" ? "  · 推荐" : ""}`),
            React.createElement("button", { className: "btn btn-sm", style: { display: "block", width: "100%", marginBottom: 6, textAlign: "left" },
              onClick: () => applyQuickCheck("void_only") },
              "只占真空（真空让位 # 新；新栅元 # 非真空栅元）"),
            React.createElement("button", { className: "btn btn-ghost btn-sm", style: { display: "block", width: "100%", textAlign: "left" },
              onClick: () => applyQuickCheck("none") },
              "保持原样（可能重叠）"),
          ),
        );
      })()}
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title" style={{ flexShrink: 0 }}>曲面卡 &amp; TR 变换</span>
          <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
            <button className="btn btn-ghost btn-xs" onClick={() => setDoc({path:"/docs/MCNP6_曲面卡格式参考.md",title:"曲面卡格式参考"})}>📖 曲面参考</button>
            <button className="btn btn-primary btn-xs" style={{ marginLeft: 8 }} onClick={openQuickCell}>⚡ 快捷建栅元</button>
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
        <TextModeSection label="栅元列表" active={cellRawMode} onToggle={toggleCellRawMode} onDiscard={discardCellRaw} />
        {cellRawMode ? (
          <textarea className="form-input" value={cellRawText} onChange={e => {setCellRawText(e.target.value);patch({rawOverrides:{...deck.rawOverrides,cells:e.target.value}});}}
            style={{width:"100%",minHeight:200,fontFamily:"Consolas,monospace",fontSize:12}} placeholder="栅元卡原始文本..." />
        ) : (
        <><div className="card-header">
          <span className="card-title">栅元列表（所有行可拖动排序）</span>
          <div className="btn-group">
            <button className="btn btn-success btn-xs" onClick={addCellRow}>+ 栅元</button>
            <button className="btn btn-ghost btn-xs" onClick={addConditionalCells} title="插入 #ifdef 名称 / #else / #endif 三行"># 条件</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>#</th><th>材料</th><th>密度</th><th>曲面表达式</th><th>IMP:N</th><th>注释</th><th>操作</th></tr></thead>
            <tbody>
              {cells.map((c, i) => c.kind === "raw" ? (
                <tr key={i} {...cellDrag.rowHandlers(i)}
                  style={{ background: "rgba(255,255,255,0.04)", ...cellDrag.rowStyle(i) }}>
                  <td colSpan={6} style={{ fontFamily: "Consolas,monospace", fontSize: 12, color: "#ce93d8" }}>{c.text}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="btn btn-danger btn-xs" onClick={() => setCells(cells.filter((_, j) => j !== i))}>×</button>
                  </td>
                </tr>
              ) : (
                <tr key={i} {...cellDrag.rowHandlers(i)}
                  style={cellDrag.rowStyle(i)}>
                  <td style={{fontWeight:600,color:"var(--text-primary)"}}>{c.cell.num}</td>
                  <td style={{ position: "relative" }}>
                    {/* 材料号可点击，弹下拉选择（同 3D 预览）；样式：可点外观 */}
                    <button type="button" className="mat-cell-btn" title="点击选择材料"
                      onClick={(e) => {
                        if (matPicker?.i === i) { setMatPicker(null); return; }
                        const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
                        setMatPicker({ i, x: r.right, y: r.bottom + 4 });
                      }}
                      style={{ background: "transparent", border: "none", cursor: "pointer", padding: "0 4px", fontWeight: 600, color: c.cell.mat === "0" ? "var(--text-tertiary)" : "var(--accent)", fontFamily: "inherit", fontSize: "inherit" }}>
                      {c.cell.mat}
                    </button>
                    {/* 材料下拉用 portal 渲染到 body：逃出 table-wrap 的 overflow 裁剪和 glass-card 的层叠上下文 */}
                    {matPicker && matPicker.i === i && createPortal(
                      <>
                        <div onClick={() => setMatPicker(null)} style={{ position: "fixed", inset: 0, zIndex: 1100, background: "transparent" }} />
                        <div className="preview-overlay"
                          style={{ position: "fixed", left: clampDropdownLeft(matPicker.x, window.innerWidth || 0), top: matPicker.y, zIndex: 1200, width: 200, maxHeight: 260, overflow: "auto", background: "rgba(15,15,40,0.97)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 6, boxShadow: "0 8px 24px rgba(0,0,0,0.5)", padding: "6px" }}>
                          {matOptions.map(o => (
                            <button key={o.num} type="button"
                              onClick={() => applyMatFromPicker(i, o.num)}
                              style={{ display: "block", width: "100%", textAlign: "left", padding: "5px 8px", marginBottom: 2, fontSize: 11, borderRadius: 4, cursor: "pointer", border: "none", background: o.num === c.cell.mat ? "rgba(255,255,255,0.12)" : "transparent", color: o.num === c.cell.mat ? "var(--accent)" : "var(--text-primary)" }}>
                              {o.label}{o.density ? `  ·  ρ=${o.density}` : ""}
                            </button>
                          ))}
                        </div>
                      </>,
                      document.body
                    )}
                  </td>
                  <td>{c.cell.density}</td><td>{c.cell.surfaces}</td><td>{c.cell.impN}</td>
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
      {show3D && <Preview3D cells={cells.filter(c => c.kind === "cell").map(c => ({ num: c.cell.num, mat: c.cell.mat, density: c.cell.density, surfaces: c.cell.surfaces, comment: c.cell.comment, render: c.cell.render }))} surfaces={surfText} trCards={trText} onClose={() => setShow3D(false)} onMaterialChange={handleCellMaterialChange} onQuickCellGenerate={handleQuickCellGenerate} />}
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
