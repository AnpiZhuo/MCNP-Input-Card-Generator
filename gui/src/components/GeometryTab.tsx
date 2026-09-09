import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import CellEditDialog, { type CellData } from "./CellEditDialog";
import { deckToLocalCells, localToDeckCells, type LocalCellRow } from "../utils/cellBridge";
import BatchCellEditDialog from "./BatchCellEditDialog";
import McnpEditor from "./McnpEditor";
import TextModeSection from "./TextModeSection";
import DocViewer from "./DocViewer";
import Preview3D from "./Preview3D";
import StepImportDialog from "./StepImportDialog";
import QuickCellDialog from "./QuickCellDialog";
import FloatingDialog from "./FloatingDialog";
import LatticeEditDialog from "./LatticeEditDialog";
import { useDeck } from "../utils/DeckContext";
import { useFreecadStatus } from "../utils/useFreecadStatus";
import { useRowDrag } from "../utils/useRowDrag";
import { useDragToGroup } from "../utils/useDragToGroup";
import { applyRegroupToRows, groupByUniverse, groupHeaderLabel, isUngroupedU } from "../utils/universeGroups";
import { openPreview3D, onMaterialChange, onQuickCellGenerate } from "../utils/windows";
import { useCellClosure } from "../utils/useCellClosure";
import { closureMeta } from "../utils/cellClosure";
import { apiUrl } from "../utils/api";
import { useSectionTextMode } from "../utils/useSectionTextMode";
import { useDeckSynced } from "../utils/useDeckSynced";
import { useAppScale, getAppPortalRoot } from "../utils/appScale";
import { textToSection } from "../utils/sectionConvert";
import { appendCardText, generatedCellToRow, quickAddCheckFailedMessage, type QuickCellResult } from "../utils/quickCell";
import { useQuickAddOverlap } from "../utils/useQuickAddOverlap";
import { applyBatchEditToRows, pruneSelectedNums, selectedCellsFromNums, toggleCellNum, type BatchCellEditValues } from "../utils/batchCellEdit";
import { detectWebGLGpu, classifyGpu, gpuShortText, gpuStatusText, setGpuPreference, type GpuInfo, type GpuPreference } from "../utils/gpuInfo";

/** 下拉右缘防溢出：x 超过视口右缘时 clamp 到 viewportWidth - dropdownWidth - 20。
 *  对齐现行为（现 220 = 200 宽 + 20 边距）。viewportWidth 为 0/负数时 Math.min 自然兜底（返回 min(x, 负数)）。 */
export function clampDropdownLeft(x: number, viewportWidth: number, dropdownWidth = 200): number {
  return Math.min(x, viewportWidth - dropdownWidth - 20);
}

interface GeoProps {
  pendingCellFromMaterial?: number;
}

export default function GeometryTab({ pendingCellFromMaterial }: GeoProps) {
  const { deck, patch } = useDeck();
  // 主窗口等比缩放时，getBoundingClientRect / clientX 为「真实像素」，材料下拉（portal 到缩放容器）需除以 scale。
  const scale = useAppScale();
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  // cells / surfaces / tr_cards：deck 单一权威，本地工作副本经共享 hook 推拉（收敛 ad-hoc 守卫）
  const [cells, setCells] = useDeckSynced<LocalCellRow[], any[]>({
    deck, patch, key: "cells",
    fromDeck: (v) => deckToLocalCells(v || []),
    toDeck: (v) => localToDeckCells(v),
  });
  const cellsRef = useRef(cells);
  cellsRef.current = cells;
  const moveCellRow = (from: number, to: number) => {
    if (from === to) return;
    const c = [...cells]; const [m] = c.splice(from, 1); c.splice(to, 0, m); setCells(c);
  };
  const cellDrag = useRowDrag(moveCellRow);
  const addCellRow = () => setCells([...cells, { kind: "cell", cell: { num:String(cells.length+1), mat:"0", density:"", surfaces:"", impN:"", impP:"", impE:"", vol:"", pwt:"", ext:"", fcl:"", u:"", fill:"", lat:"", trcl:"", tmp:"", otherParams:"", render:false, fill_grid:"", comment:"" } }]);
  const addRawCell = (text: string) => setCells([...cells, { kind: "raw", text }]);
  const addConditionalCells = () => {
    const name = window.prompt("条件名（如 ENDF7）", "ENDF7");
    if (name === null) return;
    setCells([...cells, { kind: "raw", text: `#ifdef ${name.trim()}` }, { kind: "raw", text: "#else" }, { kind: "raw", text: "#endif" }]);
  };
  const [editCell, setEditCell] = useState<number | null>(null);
  const [selectedCells, setSelectedCells] = useState<string[]>([]);
  const [batchOpen, setBatchOpen] = useState(false);
  const [surfText, setSurfText] = useDeckSynced<string, string>({
    deck, patch, key: "surfaces", fromDeck: (s) => s || "", toDeck: (s) => s,
  });
  const [trText, setTrText] = useDeckSynced<string, string>({
    deck, patch, key: "tr_cards", fromDeck: (s) => s || "", toDeck: (s) => s,
  });
  // 最新值 ref（writeBack / 快捷添加重合检测请求用，避免 state 未 flush 读到旧文本）
  const surfTextRef = useRef(surfText);
  const trTextRef = useRef(trText);
  surfTextRef.current = surfText;
  trTextRef.current = trText;
  // 项4 辅助：读取当前 WebGL 实际使用的 GPU（主界面与 3D 预览同进程，可反映 3D 用卡）
  const [gpu, setGpu] = useState<GpuInfo | null>(null);
  const [gpuPrefBusy, setGpuPrefBusy] = useState(false);
  const [gpuPrefSel, setGpuPrefSel] = useState("");
  const [gpuPrefMsg, setGpuPrefMsg] = useState<{ color: string; text: string } | null>(null);
  useEffect(() => {
    const d = detectWebGLGpu();
    if (d) setGpu(classifyGpu(d.vendor, d.renderer));
  }, []);

  // 选 GPU 偏好 → 调后端写注册表；结果用内联提示条（不用 window.alert，避免 WebView2 弹窗不可靠）
  const applyGpuPref = (pref: GpuPreference) => {
    const label = pref === "high" ? "高性能独显" : pref === "power" ? "省电核显" : "系统默认";
    setGpuPrefSel(pref);
    setGpuPrefBusy(true);
    setGpuPrefMsg(null);
    setGpuPreference(pref).then((r) => {
      setGpuPrefBusy(false);
      if (r.ok) setGpuPrefMsg({ color: "#2e7d32", text: `已设为「${label}」，重启应用后生效（3D 用卡在启动时读取）` });
      else setGpuPrefMsg({ color: "#c62828", text: `设置失败：${r.message || "未知"}（仅 Windows 下生效）` });
    });
  };
  const [show3D, setShow3D] = useState(false);
  const [showStepDlg, setShowStepDlg] = useState(false);
  const [quickCellOpen, setQuickCellOpen] = useState(false);
  // 格阵 fill 阶段2：栅格编辑器 + 按 U 分组显示
  const [latticeOpen, setLatticeOpen] = useState(false);
  const [latticeEditIdx, setLatticeEditIdx] = useState<number | null>(null);
  // 项 8：分组默认开启 + localStorage 持久化（键 mcnp_groupbyu_v1，初始 true；不跨标签页/多窗口同步）
  const [groupByU, setGroupByU] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem("mcnp_groupbyu_v1");
      return stored === null ? true : stored === "true";
    } catch {
      return true;
    }
  });
  useEffect(() => {
    try { localStorage.setItem("mcnp_groupbyu_v1", String(groupByU)); } catch { /* ignore */ }
  }, [groupByU]);
  // 项9：U 组头文字可编辑（双击内联 input → patch deck.universeComments）
  const [editingGroupU, setEditingGroupU] = useState<number | null>(null);
  const [groupDraft, setGroupDraft] = useState("");
  const commitGroupComment = () => {
    if (editingGroupU == null || editingGroupU < 0) { setEditingGroupU(null); return; }
    const key = String(editingGroupU);
    const next = { ...(deck.universeComments || {}) };
    const text = groupDraft.trim();
    if (text) next[key] = text;
    else delete next[key];
    patch({ universeComments: next });
    setEditingGroupU(null);
  };
  const groupDrag = useDragToGroup({
    onMove: moveCellRow,
    onDropOnGroup: (from, u) => {
      // 纯函数应用归组（未分组组头=清空 u）：本地显示 + deck 单一权威同时更新（项 11 防回弹）
      const nextCells = applyRegroupToRows(cells, from, u);
      setCells(nextCells);
      patch({ cells: localToDeckCells(nextCells) });
    },
  });
  // T2：快捷添加重合检测失败 → 非阻塞警告（仍追加栅元，但告知未校验重叠）
  const [quickCheckWarn, setQuickCheckWarn] = useState<string | null>(null);
  // 栅元表材料列点击下拉：i=正在编辑材料号的栅元行索引，x/y=按钮位置（用于 portal 定点浮层）
  const [matPicker, setMatPicker] = useState<{ i: number; x: number; y: number } | null>(null);
  const fc = useFreecadStatus();
  // 文本↔表单互转（深模块：逻辑在 useSectionTextMode 一处）
  // 切回表单时，把解析出的 cells（后端 CellRow 判别联合）映射回本地 LocalCellRow
  const cellsText = useSectionTextMode("cells", {
    deck, patch, overrideKey: "cells",
    onBackToForm: (data) => {
      const mapped = deckToLocalCells(data.cells || []);
      if (mapped.length) setCells(mapped);
    },
  });
  const { rawMode: cellRawMode, rawText: cellRawText, busy: cellBusy, toggleRawMode: toggleCellRawMode, onDiscard: discardCellRaw } = cellsText;

  // 材料→栅元联动：新材料添加时自动创建栅元行
  useEffect(() => {
    if (pendingCellFromMaterial && pendingCellFromMaterial > 0) {
      const maxNum = cells.length > 0 ? Math.max(...cells.map(c => c.kind === "cell" ? parseInt(c.cell.num) || 0 : 0)) : 0;
      setCells([...cells, { kind: "cell", cell: {
        num: String(maxNum + 1), mat: String(pendingCellFromMaterial),
        density: "-1.0", surfaces: "", impN: "", impP: "", impE: "",
        vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "",
        trcl: "", tmp: "", otherParams: "", render: true, fill_grid: "",
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
          const mapped = deckToLocalCells(data.cells || []);
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
        u: (c as any).cell.u, fill: (c as any).cell.fill, lat: (c as any).cell.lat,
        trcl: (c as any).cell.trcl, fill_grid: (c as any).cell.fill_grid,
        impN: (c as any).cell.impN, impP: (c as any).cell.impP, impE: (c as any).cell.impE,
      })),
      surfaces: surfText,
      trCards: trText,
      deck,
    });
    if (!opened) setShow3D(true); // 非 Tauri 环境回退
    // 3D 预览后触发封闭性检测刷新（深模块内部不重复请求同 deck）
    setTimeout(refreshClosure, 100);
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
  // 统一写回：曲面/TR 文本 + 补集补丁 + 新栅元（直接/决策后/已处理均走这里）
  const writeBack = (r: QuickCellResult) => {
    setSurfText(appendCardText(surfTextRef.current, r.surfacesText));
    setTrText(appendCardText(trTextRef.current, r.trCardsText));
    if (r.existingExprPatch && r.existingExprPatch.length) {
      const patchMap = new Map(r.existingExprPatch.map(p => [p.num, p.surfaces]));
      setCells(prev => prev.map(c => c.kind === "cell" && patchMap.has(c.cell.num)
        ? { ...c, cell: { ...c.cell, surfaces: patchMap.get(c.cell.num)! } }
        : c));
    }
    setCells(prev => [...prev, ...r.cells.map(generatedCellToRow)]);
  };
  const { quickCheck, runCheck: runQuickCheck, applyChoice: applyQuickCheck } = useQuickAddOverlap({
    getExistingCells: () => cellsRef.current.filter(c => c.kind === "cell").map(c => ({
      num: parseInt(c.cell.num, 10),
      mat: c.cell.mat,
      density: c.cell.density,
      surfaces: c.cell.surfaces,
    })),
    getSurfaces: () => surfTextRef.current,
    getTrCards: () => trTextRef.current,
    onApplyResult: writeBack,
    onCheckFail: (e) => setQuickCheckWarn(quickAddCheckFailedMessage(e)),
  });

  // ── 栅元封闭性检测（深模块 useCellClosure，3D 预览后自动刷新）──
  const { statusOf, refresh: refreshClosure } = useCellClosure(() => ({
    surfaces: surfTextRef.current,
    cells: cellsRef.current,
    tr_cards: trTextRef.current,
  }));

  // 状态列渲染（用深模块的 closureMeta 纯函数）
  const renderClosureStatus = (cellNum: string) => {
    const entry = statusOf(cellNum);
    if (!entry) return <span style={{ color: "var(--text-tertiary)", fontSize: 11 }}>—</span>;
    const meta = closureMeta(entry.status);
    const extra = (entry.status === "infinite" || entry.status === "semi_infinite")
      ? `（${(entry.infinite_axes || []).join("/")}轴）`
      : "";
    return <span style={{ color: meta.color, fontSize: 12, fontWeight: meta.allowed ? 400 : 700 }} title={meta.title + extra}>{meta.icon}</span>;
  };

  // 保存栅元
  const saveCell = (d: CellData) => {
    const c = [...cells];
    c[editCell!] = { kind: "cell", cell: d };
    setCells(c);
    setEditCell(null);
  };

  const handleQuickCellGenerate = (result: QuickCellResult) => {
    // 生成入口（3D 预览）已处理重合决策：应用补丁后直接加入，不再重复弹窗
    if (result.overlapHandled || result.checkOverlap === false) {
      writeBack(result);
      return;
    }
    // 快捷添加重合检查：新栅元 vs 已有 → 有重叠由 hook 弹 A/B/C 补集决策，否则直接写回
    runQuickCheck(result);
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

  // ── 批量编辑栅元：勾选（存栅元 num）+ 按钮（常态灰，勾选后可用）──
  // T1 修复：勾选状态存「栅元 num」而非数组下标——moveCellRow（拖拽重排）/删除行
  // 改 cells 顺序后，按 num 解析到当前行，批量编辑仍改到原勾选栅元（不静默写错）。
  const cellRowNums = cells.filter(c => c.kind === "cell").map(c => c.cell.num);
  const allSelected = cellRowNums.length > 0 && cellRowNums.every(n => selectedCells.includes(n));
  const toggleSelect = (num: string) => {
    setSelectedCells(prev => toggleCellNum(prev, num));
  };
  const toggleSelectAll = () => {
    if (allSelected) setSelectedCells([]);
    else setSelectedCells(cellRowNums);
  };
  // 勾选集 → 实际要编辑的栅元（按 num 解析到当前行；已删除/原始行自动失效）
  const selectedCellRows = selectedCellsFromNums(cells, selectedCells);
  const openBatchEdit = () => {
    if (selectedCellRows.length === 0) return;
    setBatchOpen(true);
  };
  const applyBatchEdit = (values: BatchCellEditValues) => {
    setCells(prev => applyBatchEditToRows(prev, selectedCells, values));
    setBatchOpen(false);
    setSelectedCells([]);
  };

  // 格阵 fill 阶段2：栅格编辑器保存（新建追加 / 编辑替换；自动生成的面卡追加到曲面卡）
  const handleLatticeSave = (result: { cell: CellData; surfacesText: string }) => {
    setSurfText(result.surfacesText);
    setCells(prev => {
      if (latticeEditIdx != null && latticeEditIdx >= 0 && prev[latticeEditIdx]?.kind === "cell") {
        const next = [...prev];
        next[latticeEditIdx] = { kind: "cell" as const, cell: result.cell };
        return next;
      }
      return [...prev, { kind: "cell" as const, cell: result.cell }];
    });
    setLatticeOpen(false);
    setLatticeEditIdx(null);
  };
  const openLatticeCreate = () => { setLatticeEditIdx(null); setLatticeOpen(true); };
  const openLatticeEdit = (idx: number) => { setEditCell(null); setLatticeEditIdx(idx); setLatticeOpen(true); };
  // 栅元被删除/同步替换后，剔除勾选集中已不存在的栅元 num（重排不影响——存的是 num）
  useEffect(() => {
    setSelectedCells(prev => {
      const next = pruneSelectedNums(prev, cells);
      return next.length === prev.length ? prev : next;
    });
  }, [cells]);

  // 独立 3D 窗口里改材料号 → storage 事件回写主窗口（双向同步）
  useEffect(() => {
    const offMat = onMaterialChange((cellNum, newMat) => {
      setCells(prev => prev.map(c => c.kind === "cell" && c.cell.num === cellNum ? { ...c, cell: { ...c.cell, mat: newMat } } : c));
    });
    // 独立 3D 窗口里快捷建栅元 → storage 事件回写主窗口（追加曲面/TR/栅元）
    const offQuick = onQuickCellGenerate(handleQuickCellGenerate);
    return () => { offMat(); offQuick(); };
  }, []);


  // 按 U 分组显示：raw 行原样 + 组间分隔头行（复用 raw 行分隔样式，拖到组头改 u）
  const renderGroupedBody = () => {
    const groups = groupByUniverse(cells);
    const out: React.ReactNode[] = [];
    const badgeStyle: React.CSSProperties = { display: "inline-block", marginRight: 4, padding: "0 4px", borderRadius: 3, fontSize: 10, fontWeight: 600, background: "rgba(76,159,232,0.18)", color: "#7db8f0", border: "1px solid rgba(76,159,232,0.4)", verticalAlign: "1px" };
    cells.forEach((c, i) => {
      if (c.kind !== "raw") return;
      out.push(
        <tr key={`raw-${i}`} style={{ background: "rgba(255,255,255,0.04)" }}>
          <td style={{ textAlign: "center" }}><input type="checkbox" disabled /></td>
          <td colSpan={7} style={{ fontFamily: "Consolas,monospace", fontSize: 12, color: "#ce93d8" }}>{c.text}</td>
          <td style={{ whiteSpace: "nowrap" }}>
            <button className="btn btn-danger btn-xs" onClick={() => setCells(cells.filter((_, j) => j !== i))}>×</button>
          </td>
        </tr>
      );
    });
    for (const g of groups) {
      const groupComment = g.u >= 0 ? (deck.universeComments?.[String(g.u)] ?? "") : "";
      const groupNums = g.indices.map((fi) => {
        const gr = cells[fi];
        return gr && gr.kind === "cell" ? gr.cell.num : undefined;
      }).filter(Boolean) as string[];
      const groupAllSel = groupNums.length > 0 && groupNums.every((n) => selectedCells.includes(n));
      out.push(
        <tr key={`hdr-${g.u}`} {...groupDrag.groupHandlers(g.u)}
          style={{ background: "rgba(255,255,255,0.04)", cursor: "grab", ...groupDrag.groupStyle(g.u) }}>
          <td style={{ textAlign: "center" }}>
            <input type="checkbox"
              checked={groupAllSel}
              onChange={() => {
                setSelectedCells(prev => groupAllSel
                  ? prev.filter((n) => !groupNums.includes(n))
                  : Array.from(new Set([...prev, ...groupNums])));
              }}
              title="勾选 / 取消该 U 组全部栅元"
            />
          </td>
          <td colSpan={8} style={{ fontFamily: "Consolas,monospace", fontSize: 12, color: "#ce93d8", fontWeight: 600 }}
            onDoubleClick={g.u < 0 ? undefined : () => { setEditingGroupU(g.u); setGroupDraft(groupComment); }}
            title={g.u < 0 ? undefined : "双击编辑组头文字（生成 INP 时输出 C 注释）"}>
            {editingGroupU === g.u ? (
              <input
                autoFocus
                value={groupDraft}
                onChange={(e) => setGroupDraft(e.target.value)}
                onBlur={commitGroupComment}
                onKeyDown={(e) => { if (e.key === "Enter") commitGroupComment(); if (e.key === "Escape") setEditingGroupU(null); }}
                placeholder="组头文字（如 燃料棒）"
                data-testid={`group-comment-${g.u}`}
                style={{ fontFamily: "inherit", fontSize: 12, background: "var(--bg-input)", border: "1px solid var(--accent)", color: "var(--text-primary)", borderRadius: 4, padding: "2px 6px", width: 260 }}
              />
            ) : (
              <>⬚ {groupHeaderLabel(g.u, g.count, g.u >= 0 ? groupComment : undefined)}{g.u >= 0 ? " · 双击编辑" : ""}</>
            )}
          </td>
        </tr>
      );
      g.rows.forEach((row, k) => {
        if (row.kind !== "cell") return; // 组内均为栅元行（类型收窄）
        const r = row.cell;
        const fi = g.indices[k];
        out.push(
          <tr key={`g-${g.u}-${fi}`} {...groupDrag.cellHandlers(fi)} style={groupDrag.cellStyle(fi)}>
            <td style={{ textAlign: "center" }}>
              <input type="checkbox" checked={selectedCells.includes(r.num)} onChange={() => toggleSelect(r.num)} />
            </td>
            <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>{r.num}</td>
            <td style={{ textAlign: "center" }}>{renderClosureStatus(r.num)}</td>
            <td style={{ fontSize: 11, color: "var(--text-secondary)" }}>{r.mat}</td>
            <td>{r.density}</td>
            <td>
              {r.fill_grid ? <span style={badgeStyle}>格阵</span> : null}
              {r.surfaces}
            </td>
            <td>{r.impN}</td>
            <td style={{ fontSize: 11, color: "var(--text-secondary)", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.comment || "—"}</td>
            <td style={{ whiteSpace: "nowrap" }}>
              <button className="btn btn-ghost btn-xs" onClick={() => setEditCell(fi)}>✎</button>
              <button className="btn btn-danger btn-xs" onClick={() => setCells(cells.filter((_, j) => j !== fi))}>×</button>
            </td>
          </tr>
        );
      });
    }
    return out;
  };

  return (
    <>
      {editCell !== null && cells[editCell]?.kind === "cell" && <CellEditDialog cell={cells[editCell].cell} onSave={saveCell} onClose={() => setEditCell(null)} availableMats={deck.materials} onOpenLattice={() => openLatticeEdit(editCell)} surfacesText={surfText} trCardsText={trText} />}
      {latticeOpen && <LatticeEditDialog
        surfacesText={surfText}
        deckCells={cells.filter(c => c.kind === "cell").map(c => c.cell)}
        initialCell={latticeEditIdx != null && cells[latticeEditIdx]?.kind === "cell" ? cells[latticeEditIdx].cell : null}
        nextCellNum={cells.filter(c => c.kind === "cell").reduce((m, c) => Math.max(m, parseInt(c.cell.num, 10) || 0), 0) + 1}
        onSave={handleLatticeSave}
        onClose={() => { setLatticeOpen(false); setLatticeEditIdx(null); }}
      />}
      {batchOpen && selectedCellRows.length > 0 && <BatchCellEditDialog
        cells={selectedCellRows.map(c => ({ num: c.num, mat: c.mat, density: c.density }))}
        availableMats={deck.materials}
        onApply={applyBatchEdit}
        onClose={() => setBatchOpen(false)}
      />}
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
      {quickCheckWarn && React.createElement(FloatingDialog, {
        title: "⚠ 重合检测失败",
        onClose: () => setQuickCheckWarn(null),
        width: 420,
        footer: React.createElement("button", { className: "btn btn-primary btn-sm", onClick: () => setQuickCheckWarn(null) }, "知道了"),
      },
        React.createElement("div", { style: { fontSize: 12, lineHeight: 1.7, color: "var(--text-secondary)" } },
          `${quickCheckWarn}。栅元已直接添加，请自行核对是否与已有栅元重叠。`),
      )}
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
        <div style={{display:"flex", gap:8, justifyContent:"flex-end", marginTop:8, alignItems:"center"}}>
          <span style={{fontSize:11, color:fc.status === "ok" ? "#2e7d32" : "#c62828", alignSelf:"center"}}>{fc.status === "checking" ? "检测中..." : fc.status === "ok" ? "✅ FreeCAD 已安装" : "⚠ 需要 FreeCAD"}</span>
          <span
            title={gpu ? (gpu.discrete ? "当前 3D 预览走独立显卡" : "当前 3D 预览走核显（可切独显）") : "未检测到 WebGL（浏览器环境）"}
            style={{ fontSize: 11, alignSelf: "center", color: gpu?.discrete ? "#2e7d32" : (gpu ? "#b5881a" : "var(--text-tertiary)"), cursor: "default" }}
          >
            {gpuShortText(gpu)}
          </span>
          <select
            value={gpuPrefSel}
            disabled={gpuPrefBusy}
            onChange={(e) => { const v = e.target.value as GpuPreference; if (v) applyGpuPref(v); }}
            style={{ fontSize: 11, alignSelf: "center", background: "var(--bg-input)", border: "1px solid var(--border-glass)", color: "var(--text-primary)", borderRadius: 4, padding: "1px 4px" }}
            title="设置 GPU 偏好（重启生效）：改写到 msedgewebview2.exe 的 UserGpuPreferences"
          >
            <option value="">GPU 偏好▾</option>
            <option value="high">高性能独显</option>
            <option value="power">省电核显</option>
            <option value="default">系统默认</option>
          </select>
          {fc.status === "missing" && <button className="btn btn-ghost btn-xs" onClick={fc.pickPath}>指定 FreeCAD 路径</button>}
          <button className="btn btn-ghost btn-xs" onClick={() => setShowStepDlg(true)}>📥 导入 STEP</button>
          <button className="btn btn-primary btn-xs" onClick={handlePreview3D}>🔍 3D 预览</button>
          <button className="btn btn-ghost btn-xs" onClick={handleExportSTEP}>📐 导出 STEP</button>
        </div>
        {/* 栅元封闭性检测结果（3D 预览后自动获得；无面板，直接在栅元行标注） */}
        {/* GPU 偏好提示（独占一行，右对齐，位于按钮行下方）：自检 / 设置结果 */}
        {(gpuPrefMsg || (gpu && !gpu.discrete && !gpuPrefSel)) && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 6 }}>
            <span style={{ fontSize: 10, color: gpuPrefMsg ? gpuPrefMsg.color : "#b5881a" }}>
              {gpuPrefMsg ? gpuPrefMsg.text : "当前 3D 走核显，可选「高性能独显」切换（重启生效）"}
            </span>
          </div>
        )}
      </div>
      <div className="glass-card">
        <TextModeSection label="栅元列表" active={cellRawMode} onToggle={toggleCellRawMode} onDiscard={discardCellRaw} />
        {cellRawMode ? (
          <textarea className="form-input" value={cellRawText} onChange={e => patch({rawOverrides:{...deck.rawOverrides,cells:e.target.value}})}
            style={{width:"100%",minHeight:200,fontFamily:"Consolas,monospace",fontSize:12}} placeholder="栅元卡原始文本..." />
        ) : (
        <><div className="card-header">
          <span className="card-title">栅元列表（所有行可拖动排序）</span>
          <div className="btn-group">
            <button className="btn btn-success btn-xs" onClick={addCellRow}>+ 栅元</button>
            <button className="btn btn-ghost btn-xs" onClick={addConditionalCells} title="插入 #ifdef 名称 / #else / #endif 三行"># 条件</button>
            <button
              className="btn btn-primary btn-xs"
              disabled={selectedCellRows.length === 0}
              onClick={openBatchEdit}
              title={selectedCellRows.length === 0 ? "请先勾选栅元" : "批量编辑勾选的栅元"}
              style={selectedCellRows.length === 0
                ? { background: "var(--bg-glass)", color: "var(--text-tertiary)", cursor: "not-allowed", boxShadow: "none", opacity: 0.6 }
                : undefined}
            >⚡ 批量编辑</button>
            <button className="btn btn-ghost btn-xs" onClick={openLatticeCreate} title="创建/编辑格阵 FILL 栅元（矩形/六棱柱涂色画布）">⬚ 栅格编辑</button>
            <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "inline-flex", alignItems: "center", gap: 4, cursor: "pointer", marginLeft: 6 }}>
              <input type="checkbox" checked={groupByU} onChange={(e) => setGroupByU(e.target.checked)} />
              按 U 分组
            </label>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th style={{ width: 28 }}>
                <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} title="全选 / 取消全选" />
              </th>
              <th>#</th>
              <th style={{ width: 28, fontSize: 10, fontWeight: 400, color: "var(--text-secondary)" }}>封闭</th>
              <th>材料</th>
              <th>密度</th>
              <th>曲面表达式</th>
              <th>IMP:N</th>
              <th>注释</th>
              <th>操作</th>
            </tr></thead>
            <tbody>
              {groupByU ? renderGroupedBody() : cells.map((c, i) => c.kind === "raw" ? (
                <tr key={i} {...cellDrag.rowHandlers(i)}
                  style={{ background: "rgba(255,255,255,0.04)", ...cellDrag.rowStyle(i) }}>
                  <td style={{ textAlign: "center" }}><input type="checkbox" disabled /></td>
                  <td colSpan={7} style={{ fontFamily: "Consolas,monospace", fontSize: 12, color: "#ce93d8" }}>{c.text}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="btn btn-danger btn-xs" onClick={() => setCells(cells.filter((_, j) => j !== i))}>×</button>
                  </td>
                </tr>
              ) : (
                <tr key={i} {...cellDrag.rowHandlers(i)}
                  style={cellDrag.rowStyle(i)}>
                  <td style={{ textAlign: "center" }}>
                    <input type="checkbox" checked={selectedCells.includes(c.cell.num)} onChange={() => toggleSelect(c.cell.num)} />
                  </td>
                  <td style={{fontWeight:600,color:"var(--text-primary)"}}>{c.cell.num}</td>
                  <td style={{ textAlign: "center" }}>{renderClosureStatus(c.cell.num)}</td>
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
                    {/* 材料下拉用 portal 渲染到缩放容器（#app-portal-root）：逃出 table-wrap 的 overflow 裁剪和 glass-card 的层叠上下文，同时随 .app-shell 等比缩放 */}
                    {matPicker && matPicker.i === i && createPortal(
                      <>
                        <div onClick={() => setMatPicker(null)} style={{ position: "fixed", inset: 0, zIndex: 1100, background: "transparent" }} />
                        <div className="preview-overlay"
                          style={{ position: "fixed", left: clampDropdownLeft(matPicker.x / scale, (window.innerWidth / scale) || 0), top: matPicker.y / scale, zIndex: 1200, width: 200, maxHeight: 260, overflow: "auto", background: "rgba(15,15,40,0.97)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 6, boxShadow: "0 8px 24px rgba(0,0,0,0.5)", padding: "6px" }}>
                          {matOptions.map(o => (
                            <button key={o.num} type="button"
                              onClick={() => applyMatFromPicker(i, o.num)}
                              style={{ display: "block", width: "100%", textAlign: "left", padding: "5px 8px", marginBottom: 2, fontSize: 11, borderRadius: 4, cursor: "pointer", border: "none", background: o.num === c.cell.mat ? "rgba(255,255,255,0.12)" : "transparent", color: o.num === c.cell.mat ? "var(--accent)" : "var(--text-primary)" }}>
                              {o.label}{o.density ? `  ·  ρ=${o.density}` : ""}
                            </button>
                          ))}
                        </div>
                      </>,
                      getAppPortalRoot()
                    )}
                  </td>
                  <td>{c.cell.density}</td>
                  <td style={{ position: "relative" }}>
                    {c.cell.fill_grid ? <span className="lattice-badge" style={{ display: "inline-block", marginRight: 4, padding: "0 4px", borderRadius: 3, fontSize: 10, fontWeight: 600, background: "rgba(76,159,232,0.18)", color: "#7db8f0", border: "1px solid rgba(76,159,232,0.4)", verticalAlign: "1px" }}>格阵</span> : null}
                    {c.cell.surfaces}
                  </td>
                  <td>{c.cell.impN}</td>
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
      {show3D && <Preview3D cells={cells.filter(c => c.kind === "cell").map(c => ({ num: c.cell.num, mat: c.cell.mat, density: c.cell.density, surfaces: c.cell.surfaces, comment: c.cell.comment, render: c.cell.render, u: c.cell.u, fill: c.cell.fill, lat: c.cell.lat, trcl: c.cell.trcl, fill_grid: c.cell.fill_grid, impN: c.cell.impN, impP: c.cell.impP, impE: c.cell.impE }))} surfaces={surfText} trCards={trText} onClose={() => setShow3D(false)} onMaterialChange={handleCellMaterialChange} onQuickCellGenerate={handleQuickCellGenerate} />}
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
