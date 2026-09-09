import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import TabPanels from "./components/TabPanels";
import PreviewDialog from "./components/PreviewDialog";
import Preview3DWindow from "./components/Preview3DWindow";
import CrossSectionWindow from "./components/CrossSectionWindow";
import ResultWindow from "./volume/ResultWindow";
import PtracWindow from "./ptrac/PtracWindow";
import { generateInp } from "./utils/dataCollector";
import { currentWindowLabel, clearStlSession } from "./utils/windows";

import { DeckProvider, useDeck } from "./utils/DeckContext";
import { useAiWorkspace } from "./hooks/useAiWorkspace";
import AiAccessPanel from "./components/AiAccessPanel";
import { normalizeImportedMaterials } from "./components/MaterialEditDialog";
import { buildGridsFromTally, buildTallyFromGrids } from "./utils/gridState";
import { buildFmeshPayload, fmeshDefsToRows } from "./volume/fmeshState";
import { startPythonBackend, stopPythonBackend } from "./utils/backend";
import { apiUrl } from "./utils/api";
import { buildRawOverrides } from "./utils/rawOverrides";
import { canonicalSourceMode } from "./utils/sourceAdv";
import AppScaleProvider from "./utils/appScale";

const TABS = [
  { key: "basic", label: "基本" },
  { key: "mat", label: "材料" }, { key: "geo", label: "几何" },
  { key: "src", label: "源项" }, { key: "tally", label: "计数" },
  { key: "adv", label: "高级" }, { key: "output", label: "输出" },
];

type Theme = "dark" | "light" | "dopamine" | "traditional";

/** 主题独立持久化键——清空工作区（mcnp_workspace_v1）不影响主题 */
const THEME_KEY = "mcnp_theme";
const isTheme = (t: any): t is Theme =>
  t === "dark" || t === "light" || t === "dopamine" || t === "traditional";

function AppInner() {
  const [activeTab, setActiveTab] = useState("basic");
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const t = localStorage.getItem(THEME_KEY);
      if (isTheme(t)) return t;
      // 兼容旧版：主题曾存在工作区 JSON 里，首次读一次后由下面 useEffect 迁移到独立键
      const s = JSON.parse(localStorage.getItem("mcnp_workspace_v1") || "null");
      if (isTheme(s?.theme)) return s.theme;
    } catch {}
    return "dark";
  });
  const [preview, setPreview] = useState<string | null>(null);
  const [closureGenerateWarn, setClosureGenerateWarn] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"form" | "raw">("form");
  const [rawInp, setRawInp] = useState("");
  const [generating, setGenerating] = useState(false);
  const [outputPath, setOutputPath] = useState("D:/MCNP/new");
  const [suffix, setSuffix] = useState(".i");
  const [dragOver, setDragOver] = useState(false);
  const [pendingCell, setPendingCell] = useState(0);
  const [mcnpInfo, setMcnpInfo] = useState({found:false, exe:"", label:"MCNP?"});
  const [backendState, setBackendState] = useState<"connecting" | "ready" | "offline">("connecting");

  // MCNP 检测：后端就绪后才查（否则 mount 时 5001 未起 → 图标永远不更新）
  useEffect(() => {
    if (backendState !== "ready") return;
    fetch(apiUrl("/api/mcnp-detect"), {method:"POST"})
      .then(r => r.json()).then(j => { if (j.status === "ok") setMcnpInfo(j); })
      .catch(() => {});
  }, [backendState]);

  // 后端连接状态轮询：sidecar 启动需要时间（首次 Defender 扫描），就绪前提示用户
  useEffect(() => {
    let stopped = false;
    const poll = async () => {
      for (let i = 0; i < 90 && !stopped; i++) {
        try {
          const r = await fetch(apiUrl("/api/xsdir-check"), { signal: AbortSignal.timeout(2000) });
          if (r.ok) { setBackendState("ready"); return; }
        } catch { /* 未就绪，继续等 */ }
        await new Promise(res => setTimeout(res, 2000));
      }
      if (!stopped) setBackendState("offline");
    };
    poll();
    return () => { stopped = true; };
  }, []);
  const { deck, patch, loadDeck } = useDeck();
  // AI 接入：当前工作区同步到 /workspace + 轮询回显 + 状态（MCP over HTTP）
  const [aiOpen, setAiOpen] = useState(false);
  // deck.adv 已是源/高级唯一权威。AI 回显直接把后端 deck（adv 权威）整份并入，loadDeck 内做旧存档迁移兜底；
  // 「源项」页从 deck.adv 派生 → AI 改 adv 后界面自动跟随（无需 aiProject 中间态投影）。
  const ai = useAiWorkspace(deck, (aiDeck: any) => loadDeck({ ...deck, ...aiDeck }));

  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);
  // 主题一变就持久化到独立键（清空工作区不影响主题）
  useEffect(() => { try { localStorage.setItem(THEME_KEY, theme); } catch {} }, [theme]);

  // 打包后自动启动 Python 后端（浏览器模式自动失效）；卸载/关闭时一起关
  useEffect(() => {
    startPythonBackend();
    return () => { stopPythonBackend(); };
  }, []);

  // 重置 pendingCell，让 GeometryTab 每次都能检测到变化
  useEffect(() => { if (pendingCell > 0) { const t = setTimeout(() => setPendingCell(0), 100); return () => clearTimeout(t); } }, [pendingCell]);

  // ── 工作区保存 / 恢复 / 清空（所有值都在 deck，单一权威）──
  const SAVE_KEY = "mcnp_workspace_v1";
  const skipAutoSaveRef = React.useRef(false);

  const saveWorkspace = () => {
    try {
      localStorage.setItem(SAVE_KEY, JSON.stringify({ version: 1, deck, outputPath, suffix }));
      return true;
    } catch { return false; }
  };

  // 结构校验：防止 localStorage 里的损坏 deck 在二次启动时崩掉下游渲染
  const isValidDeck = (d: any): boolean => {
    if (!d || typeof d !== "object") return false;
    if (d.basic !== undefined && (typeof d.basic !== "object" || d.basic === null)) return false;
    for (const k of ["cells", "materials", "sources", "tallies"])
      if (d[k] !== undefined && !Array.isArray(d[k])) return false;
    for (const k of ["tally", "grids", "adv", "rawOverrides"])
      if (d[k] !== undefined && (typeof d[k] !== "object" || d[k] === null)) return false;
    return true;
  };
  const saveWorkspaceRef = React.useRef(saveWorkspace);
  saveWorkspaceRef.current = saveWorkspace;

  const handleSave = () => { alert(saveWorkspace() ? "✅ 已保存当前工作区" : "⚠ 保存失败"); };
  const handleClear = () => {
    if (!window.confirm("确定一键清空？所有输入内容将丢失且不可恢复。")) return;
    skipAutoSaveRef.current = true;   // 阻止 beforeunload 把清空前的旧状态又存回去
    localStorage.removeItem(SAVE_KEY);
    clearStlSession();                // 一并清掉 3D 预览 STL 会话
    window.location.reload();
  };

  // 启动时恢复上次保存的工作区（结构校验 + 版本检查，损坏则跳过防崩溃）
  useEffect(() => {
    try {
      const raw = localStorage.getItem(SAVE_KEY);
      if (!raw) return;
      const s = JSON.parse(raw);
      if (s && s.version !== 1) { console.warn("[Restore] 工作区版本不匹配，跳过恢复"); return; }
      if (s?.deck && isValidDeck(s.deck)) {
        loadDeck(s.deck);
      } else {
        console.warn("[Restore] 工作区 deck 结构损坏，跳过恢复");
      }
      if (s?.outputPath) setOutputPath(s.outputPath);
      if (s?.suffix) setSuffix(s.suffix);
    } catch (e) { console.warn("[Restore] 恢复失败", e); }
  }, []);

  // 关闭 / 刷新时自动保存（用 ref 拿最新闭包）
  useEffect(() => {
    const onBeforeUnload = () => { if (!skipAutoSaveRef.current) saveWorkspaceRef.current(); };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  // ── INP 导入：原生文件对话框 + 拖放共用同一解析链 ──
  const importInpText = useCallback(async (text: string) => {
    try {
      const vr = await fetch(apiUrl('/api/validate-inp'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ inp: text }) });
      const vj = await vr.json();
      if (vj.status === 'ok' && !vj.valid) { alert('⚠ INP 文件校验未通过:\n\n' + vj.errors.slice(0,5).join('\n')); return; }
      const r = await fetch(apiUrl('/api/parse-inp'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inp: text }),
      });
      const j = await r.json();
      if (j.status !== 'ok') throw new Error(j.message);
      const d = j.deck;
      loadDeck({
        basic: d.basic || {}, surfaces: d.surfaces || '', tr_cards: d.tr_cards || '',
        cells: d.cells || [], materials: normalizeImportedMaterials(d.materials || []),
        sources: d.sources || [], tallies: d.tallies || [],
        tally: {
          ...(d.tally || {}),
          // 后端返回 fmesh_defs → 前端 deck.tally.fmesh（fmeshState FmeshRow[]）
          fmesh: fmeshDefsToRows((d.tally?.fmesh_defs || [])),
        },
        grids: buildGridsFromTally(d.tally || {}),
        adv: d.adv || {},          // parse 已产出权威 source_mode + sdef_*/kcode_*/…；不再读顶层中间态
        rawOverrides: d.rawOverrides || {},
        textMode: d.textMode || {},
        sourceTemplate: d.sourceTemplate || 'free',
      });
      alert('导入成功: ' + (d.basic?.title || '无标题'));
    } catch (err: any) {
      alert('导入失败: ' + (err.message || '解析错误'));
    }
  }, [loadDeck]);

  // 示例库一键导入：ExamplesDialog dispatch 自定义事件 → 复用同一导入管线
  useEffect(() => {
    const onImport = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail && typeof detail.text === 'string') importInpText(detail.text);
    };
    window.addEventListener('mcnp:import-inp', onImport);
    return () => window.removeEventListener('mcnp:import-inp', onImport);
  }, [importInpText]);

  // 导入按钮 → Windows 原生文件选择对话框
  const handleImportNative = useCallback(async () => {
    try {
      const r = await fetch(apiUrl('/api/choose-file'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
      const j = await r.json();
      if (j.status !== 'ok') throw new Error(j.message);
      if (j.cancelled || !j.content) return;  // 用户取消
      const name = (j.path || '').toLowerCase();
      if (name.match(/\.(step|stp)$/)) { alert('STEP 导入需要后端 + FreeCAD 支持'); return; }
      await importInpText(j.content);
    } catch (err: any) {
      alert('导入失败: ' + (err.message || '无法打开文件选择器'));
    }
  }, [importInpText]);

  const handleDrag = useCallback((e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); }, []);
  const handleDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); }, []);
  const handleDragEnter = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragOver(true); }, []);
  const handleDragLeave = useCallback((e: React.DragEvent) => { e.preventDefault(); }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const name = file.name.toLowerCase();

    // STEP → 导入几何
    if (name.match(/\.(step|stp)$/)) {
      alert("STEP 导入需要后端 + FreeCAD 支持");
      return;
    }

    // INP / I / TXT → 解析回填
    if (!name.match(/\.(inp|i|txt)$/)) {
      alert("支持 .INP / .I / .TXT（导入参数）或 .STEP / .STP（导入几何）");
      return;
    }

    try {
      const text = await file.text();
      await importInpText(text);
    } catch (err: any) {
      alert("导入失败: " + (err.message || "请确认后端已重启（添加新接口后需重启）"));
    }
  }, [importInpText]);

  // 打包后（Tauri）文件拖放走 tauri://file-drop 事件——HTML5 drag 事件被 Tauri 拦截不触发
  const handleTauriDrop = useCallback(async (path: string) => {
    const name = path.toLowerCase();
    if (name.match(/\.(step|stp)$/)) { alert("STEP 导入需要后端 + FreeCAD 支持"); return; }
    if (!name.match(/\.(inp|i|txt)$/)) { alert("支持 .INP / .I / .TXT（导入参数）或 .STEP / .STP（导入几何）"); return; }
    try {
      const { readTextFile } = await import("@tauri-apps/api/fs");
      const text = await readTextFile(path);
      await importInpText(text);
    } catch (err: any) {
      alert("导入失败: " + (err.message || "请确认后端已启动"));
    }
  }, [importInpText]);

  // Tauri 原生拖入判定：hover 亮覆盖层，drop 导入、取消熄灭
  useEffect(() => {
    let unlisteners: (() => void)[] = [];
    import("@tauri-apps/api/event").then(async (m) => {
      try {
        unlisteners = await Promise.all([
          m.listen("tauri://file-drop-hover", () => setDragOver(true)),
          m.listen("tauri://file-drop-cancelled", () => setDragOver(false)),
          m.listen("tauri://file-drop", (e: any) => {
            setDragOver(false);
            const p = Array.isArray(e.payload) ? e.payload[0] : undefined;
            if (p) handleTauriDrop(p);
          }),
        ]);
      } catch { /* 非 Tauri 环境 */ }
    }).catch(() => {});
    return () => { unlisteners.forEach(u => u()); };
  }, [handleTauriDrop]);

  const handleBrowse = async () => {
    try {
      const r = await fetch(apiUrl("/api/choose-dir"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initialDir: outputPath }),
      });
      const j = await r.json();
      if (j.status === "ok") { if (j.path) setOutputPath(j.path); }  // 取消 → 不改
      else throw new Error(j.message);
    } catch {
      const p = prompt("输出目录:", outputPath);  // 后端不可用 → 降级
      if (p) setOutputPath(p);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setClosureGenerateWarn(null);
    try {
      // 载荷全部来自 deck（单一权威）——已无 DOM 采集
      const b: Record<string, any> = deck.basic || {};
      const gridPayload = buildTallyFromGrids(deck.grids, deck.tallies);
      // CUT 截断（AdvancedTab 受控写 deck.tally.cut_*）
      const cutFields: Record<string, string> = {};
      for (const p of ["n","p","e","h","he","d","t","a"])
        for (const f of ["t","e","wc1","wc2","swtm"])
          cutFields[`cut_${p}_${f}`] = deck.tally?.[`cut_${p}_${f}`] || "";
      const body = {
        basic: {
          title: b.title || "", nps: b.nps || "", ctme: b.ctme || "",
          act: b.act || "", print_pr: b.print_pr || "",
          phys_fis: b.phys_fis !== false,
          mode_n: !!b.mode_n, mode_p: !!b.mode_p, mode_e: !!b.mode_e,
          mode_h: !!b.mode_h, mode_he: !!b.mode_he, mode_d: !!b.mode_d,
          mode_t: !!b.mode_t, mode_a: !!b.mode_a,
        },
        surfaces: deck.surfaces || "", tr_cards: deck.tr_cards || "",
        cells: deck.cells, materials: deck.materials, sources: deck.sources,
        universe_comments: deck.universeComments || {},
        tally: {
          tallies: deck.tallies,
          ...gridPayload,
          ...cutFields,
          // FMESH/TMESH 结构化卡（fmeshState 双向转换，后端 key=fmesh_defs）
          fmesh_defs: buildFmeshPayload((deck.tally as any)?.fmesh || []),
          // PTRAC 粒子径迹卡（ptracState，后端 key=ptrac；未启用时 undefined → JSON 省略）
          ptrac: (deck.tally as any)?.ptrac,
        },
        // 源/高级：deck.adv 是唯一权威（源项页直接读写 deck.adv.*，含 source_mode/sdef_*/kcode_*/ssw_*/ssr_*/ksrc_points/sdef_distributions）。
        // canonicalSourceMode 兜底：非 kcode/surface 一律 distribution（不再有独立 sourceMode 副本）。
        adv: { ...(deck.adv || {}), source_mode: canonicalSourceMode(deck.adv) },
        // 文本模式：当前处于文本模式的 section 用文本数据，表单模式的用表单数据
        raw_overrides: buildRawOverrides(deck),
      };
      const inp = await generateInp(body);
      setPreview(inp);
      // 生成时栅元封闭性复核：优先读几何页已缓存的自检结果，无则自动检测
      runGenerateClosureCheck(body, inp);
    } catch (e: any) { setPreview("// 生成失败: " + e.message); }
    finally { setGenerating(false); }
  };

  // 生成后封闭性复核（后台平行；有未封闭/空/未解析栅元才提示）
  const runGenerateClosureCheck = async (body: any, inp: string) => {
    try {
      let report: any = (deck as any).cellClosureReport || null;
      if (!report || Object.keys(report).length === 0) {
        const r = await fetch(apiUrl("/api/check-cell-closure"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            surfaces: body.surfaces || "",
            cells: body.cells || [],
            tr_cards: body.tr_cards || "",
          }),
        });
        const j = await r.json();
        if (j.status !== "ok") return;
        report = j.closure_report || {};
        patch({ cellClosureReport: report });
      }
      const bad: string[] = [];
      for (const [num, info] of Object.entries(report || {})) {
        const st = (info as any)?.status;
        if (st === "infinite" || st === "semi_infinite") bad.push(`栅元 ${num}（外无限）`);
        else if (st === "empty") bad.push(`栅元 ${num}（空/退化）`);
        else if (st === "unresolvable") bad.push(`栅元 ${num}（未解析）`);
      }
      if (bad.length) {
        setClosureGenerateWarn(`⚠ 生成前封闭性自检发现：${bad.join("、")}。` +
          "外无限栅元若为模型边界（imp=0 包围）属正常；空/未解析栅元请检查几何。");
      }
    } catch { /* 后端不可用 → 静默 */ }
  };

  const handleImport = () => { setViewMode("raw"); setRawInp("粘贴 INP 内容..."); };

  // Tauri 自定义窗口命令（Rust main.rs 实现，不依赖 Cargo window-* features）
  const winCmd = (cmd: string) => {
    import("@tauri-apps/api/tauri").then(m => m.invoke(cmd)).catch(() => {});
  };
  // 顶栏拖拽：交互元素（按钮/输入框等）不触发，其余区域按下即拖
  const handleTopbarDrag = (e: React.MouseEvent) => {
    const t = e.target as HTMLElement;
    if (t.closest("button, input, select, textarea, a")) return;
    winCmd("start_dragging_window");
  };

  return (
    <div className="app-shell"
      onDrag={handleDrag} onDragStart={handleDrag} onDragEnd={handleDrag}
      onDragOver={handleDragOver} onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave} onDrop={handleDrop}
      style={{ position: "relative" }}>
      {dragOver && <div style={{ position: "fixed", inset: 0, zIndex: 9999, background: "rgba(255,0,128,0.15)", backdropFilter: "blur(8px)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, fontWeight: 700, color: "#fff" }}>释放以导入 INP 文件</div>}
      <Sidebar active={activeTab} onSelect={setActiveTab} tabs={TABS} theme={theme} onThemeChange={(t) => setTheme(t as Theme)} onImport={handleImportNative} />
      <div className="main-area">
        <div className="topbar" onMouseDown={handleTopbarDrag}>
          <div className="topbar-left" style={{ flex: 1, display: "flex", alignItems: "center", gap: 8 }}>
            <input className="form-input" value={outputPath} onChange={e => setOutputPath(e.target.value)} placeholder="输出路径" style={{ flex: 1, height: 28, fontSize: 12 }} />
            <button className="btn btn-ghost btn-xs" onClick={handleBrowse}>浏览</button>
            <select className="form-select" value={suffix} onChange={e => setSuffix(e.target.value)} style={{ width: 70, height: 28, fontSize: 11 }}>
              <option>.i</option><option>.inp</option><option>.txt</option>
            </select>
            <span className="status-dot" />
            <span style={{ fontSize: 11, color: mcnpInfo.found ? "#2e7d32" : "#c62828", whiteSpace: "nowrap" }}>{mcnpInfo.label}</span>
            <span style={{ fontSize: 11, color: backendState === "ready" ? "#2e7d32" : backendState === "connecting" ? "#f9a825" : "#c62828", whiteSpace: "nowrap" }}>
              {backendState === "ready" ? "后端已连接" : backendState === "connecting" ? "后端启动中…" : "后端不可用"}
            </span>
          </div>
          <div className="topbar-right">
            <button className="btn btn-ghost btn-sm" onClick={() => setAiOpen(true)}
              title="让外部分 agent 读/改本程序（MCP）"
              style={{ color: ai.status === "ok" ? "#2e7d32" : "var(--text-secondary)" }}>
              🤖 AI{ai.status === "ok" ? "" : " •"}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={handleSave} title="保存工作区到本地，关闭时也会自动保存">💾 保存</button>
            <button className="btn btn-ghost btn-sm" onClick={handleClear} title="清空所有输入内容" style={{ color: "var(--red)" }}>🧹 清空</button>
            <button className="btn btn-primary btn-sm" onClick={handleGenerate} disabled={generating}>
              {generating ? "生成中..." : "生成"}
            </button>
            <div className="titlebar-btns">
              <button className="tb-btn" onClick={() => winCmd("minimize_window")} title="最小化" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="12" height="12" viewBox="0 0 12 12"><line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="1.2" /></svg>
              </button>
              <button className="tb-btn" onClick={() => winCmd("toggle_maximize_window")} title="最大化/还原" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="12" height="12" viewBox="0 0 12 12"><rect x="2" y="2" width="8" height="8" fill="none" stroke="currentColor" strokeWidth="1.2" /></svg>
              </button>
              <button className="tb-btn close" onClick={() => winCmd("close_window")} title="关闭" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 3 L9 9 M9 3 L3 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" /></svg>
              </button>
            </div>
          </div>
        </div>
        {viewMode === "raw" ? (
          <textarea className="form-input" value={rawInp} onChange={e => setRawInp(e.target.value)}
            style={{width:"100%",minHeight:400,fontFamily:"Consolas,monospace",fontSize:13}} placeholder="INP 原始文本..." />
        ) : (
          <TabPanels activeTab={activeTab} onMaterialAdded={(n) => setPendingCell(n)} pendingCellFromMaterial={pendingCell} />
        )}
      </div>
      {preview && <PreviewDialog content={preview} onClose={() => setPreview(null)} onRegenerate={handleGenerate} outputPath={outputPath} fileName={(deck.basic?.title || "MCNP_Input").replace(/[^a-zA-Z0-9_\-]/g,"_") + suffix} mcnpExe={mcnpInfo.exe || "mcnp6.exe"} closureGenerateWarn={closureGenerateWarn} onClearClosureGenerateWarn={() => setClosureGenerateWarn(null)} />}
      {aiOpen && <AiAccessPanel mcpUrl={ai.mcpUrl} status={ai.status} onClose={() => setAiOpen(false)} />}
      {/* Portal 根节点：createPortal 弹窗挂到这里才能随缩放容器一起等比缩放（见 utils/appScale.tsx）。
          零尺寸 + absolute：不占布局、不遮挡点击；挂进来的固定定位弹窗按缩放容器（zoom）坐标系定位并缩放 */}
      <div id="app-portal-root" style={{ position: "absolute", width: 0, height: 0 }} />
    </div>
  );
}

/** 独立窗口路由：按当前窗口 label 分派渲染（主界面 / 3D 预览 / 截面 / 3D 结果 / 3D 径迹）
 *
 * 同步初始化策略：URL hash 在 DOM 挂载前即可读取，免去 useEffect 异步
 * `currentWindowLabel()` 导致的「先闪主界面再切子窗口」闪烁（P0，2026-09）。
 * Tauri 子窗口打开时 Rust 侧已写入 `index.html#/preview3d` 等 hash，
 * 主窗口无 hash → 直接渲染 AppInner。
 */
function WindowRouter() {
  const [label, setLabel] = useState<string>(() => {
    const h = window.location.hash.replace(/^#\/?/, "");
    if (h === "preview3d" || h === "cross_section" || h === "volume" || h === "ptrac") return h;
    return "main";
  });
  useEffect(() => {
    // 调试入口：URL hash #/preview3d / #/cross_section / #/volume / #/ptrac 可强制窗口类型（浏览器模式测试用）
    const h = window.location.hash.replace(/^#\/?/, "");
    if (h === "preview3d" || h === "cross_section" || h === "volume" || h === "ptrac") { setLabel(h); return; }
    // 无 hash 时回退到 Tauri window label（鲁棒性兜底）
    currentWindowLabel().then(setLabel).catch(() => setLabel("main"));
  }, []);
  if (label === "preview3d") return <AppScaleProvider designWidth={1300} designHeight={820}><Preview3DWindow /></AppScaleProvider>;
  if (label === "cross_section") return <AppScaleProvider designWidth={1000} designHeight={700}><CrossSectionWindow /></AppScaleProvider>;
  if (label === "volume") return <AppScaleProvider designWidth={1300} designHeight={820}><ResultWindow /></AppScaleProvider>;
  if (label === "ptrac") return <AppScaleProvider designWidth={1300} designHeight={820}><PtracWindow /></AppScaleProvider>;
  return <AppScaleProvider><DeckProvider><AppInner /></DeckProvider></AppScaleProvider>;
}

export default function App() { return <WindowRouter />; }
