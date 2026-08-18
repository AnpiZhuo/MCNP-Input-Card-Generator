import React, { useState, useRef, useMemo } from "react";
import { parseOutp, type ParsedOutput } from "../utils/outputParser";
import DocViewer from "./DocViewer";
import { apiUrl, errorHint, meshtalDetect, meshtalParse, ptracDetect, ptracParse, type MeshtalDetectFile, type MeshtalParseResult, type MeshtalTallyMeta, type PtracParseResult } from "../utils/api";
import { useDeck } from "../utils/DeckContext";
import { workflowStep, noFileMessage, type MeshWorkflowState } from "../volume/workflow";
import { decideResolution, DEFAULT_RESOLUTION, MAX_RESOLUTION, OVER_BUDGET_POPUP_COPY } from "../volume/downsampleRequest";
import { openVolume3DWindow, readOutputDir } from "../volume/openVolume3DWindow";
import { openPtrac3DWindow } from "../ptrac/openPtracWindow";
import { buildFluxChartSvg } from "../utils/tallyChart";

export default function OutputTab() {
  const [doc, setDoc] = useState<{path:string;title:string}|null>(null);
  const [parsed, setParsed] = useState<ParsedOutput | null>(null);
  const [filePath, setFilePath] = useState("");
  const [selectedTally, setSelectedTally] = useState("1");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [chartTally, setChartTally] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { deck } = useDeck();

  const handleBrowse = () => {
    fileInputRef.current?.click();
  };

  const parseFileContent = async (file: File) => {
    try {
      const text = await file.text();
      // 先尝试后端 pymcnp 解析
      try {
        const r = await fetch(apiUrl("/api/parse-outp"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outp: text }), signal: AbortSignal.timeout(10000) });
        const j = await r.json();
        if (j.status === "ok" && j.tallies) { setParsed(j); setSelectedTally(Object.keys(j.tallies)[0]); return; }
      } catch {}
      // Fallback: 本地解析器
      const result = parseOutp(text);
      setParsed(result);
      if (Object.keys(result.tallies).length > 0) {
        setSelectedTally(Object.keys(result.tallies)[0]);
      }
    } catch (err: any) {
      alert("解析失败: " + err.message);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFilePath(file.name);
    setSelectedFile(file);
    await parseFileContent(file);
  };

  const handleExportCsv = () => {
    if (!parsed) return;
    const tallyNum = Number(selectedTally);
    const tally = parsed.tallies[tallyNum];
    if (!tally) return;
    let csv = "Energy (MeV),Flux,Error\n";
    for (const row of tally.rows) {
      csv += `${row.energy},${row.flux},${row.error}\n`;
    }
    const total = tally.total;
    csv += `total,${total.flux},${total.error}\n`;
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `tally_${selectedTally}.csv`;
    a.click();
  };

  /* ── 网格计数 3D 结果（入口统一到输出页；交互照 FMeshForm 启动器，开窗走 openVolume3DWindow 共享函数）── */
  const [meshOutputDir] = useState(() => readOutputDir());
  const [meshBusy, setMeshBusy] = useState(false);
  const [meshWorkflow, setMeshWorkflow] = useState<MeshWorkflowState>("idle");
  const [meshFiles, setMeshFiles] = useState<MeshtalDetectFile[]>([]);
  const [meshParse, setMeshParse] = useState<MeshtalParseResult | null>(null);
  const [meshParseError, setMeshParseError] = useState<string | null>(null);
  const [meshSelectedTally, setMeshSelectedTally] = useState<MeshtalTallyMeta | null>(null);
  const [meshBudget, setMeshBudget] = useState<{ path: string; tally: MeshtalTallyMeta; native: number[] } | null>(null);

  /* ── 粒子径迹（PTRAC）：选择文件 → 解析 → 开窗（契约 ptrac-visualization.md §4）── */
  const [ptracPath, setPtracPath] = useState("");
  const [ptracBusy, setPtracBusy] = useState(false);
  const [ptracError, setPtracError] = useState<string | null>(null);
  const [ptracParseResult, setPtracParseResult] = useState<PtracParseResult | null>(null);

  // 几何外壳模型（照 TallyTab → FMeshForm 的 cells 映射）
  const meshCells = useMemo(() => (deck.cells || [])
    .filter((c) => c.kind === "cell")
    .map((c) => {
      const cell = (c as any).cell || {};
      return {
        num: String(cell.number),
        mat: cell.material,
        comment: cell.comment,
        density: cell.density,
        surface_expr: cell.surface_expr,
      };
    }), [deck.cells]);
  const meshModel = useMemo(() => ({ cells: meshCells, surfaces: deck.surfaces, trCards: deck.tr_cards }), [meshCells, deck.surfaces, deck.tr_cards]);
  const meshHasModel = !!(meshCells && meshCells.length) || !!deck.surfaces;
  const meshCellsForBackend = meshCells.map((c) => ({
    number: parseInt(c.num, 10) || 0,
    material: c.mat,
    density: c.density || "",
    surface_expr: c.surface_expr || "",
  }));

  const meshTallies = (meshParse?.tallies || []).filter((t) => !t.unsupportedGeom);

  /** 开窗（共享函数）：ok → parsed；非 Tauri fallback → 提示 #/volume；异常 → error hint */
  const launchMeshWindow = async (path: string, tally: MeshtalTallyMeta, resolution: number, parseResult: MeshtalParseResult | null) => {
    setMeshBusy(true);
    try {
      const out = await openVolume3DWindow({ path, tally, resolution, model: meshModel, parseResult });
      if (out.ok) {
        setMeshWorkflow("parsed");
      } else if (out.kind === "fallback") {
        setMeshParseError(out.message); // 浏览器模式：数据已写入，提示 #/volume
        setMeshWorkflow("parsed");
      } else {
        setMeshParseError(out.message);
        setMeshWorkflow("error");
      }
    } finally {
      setMeshBusy(false);
    }
  };

  const runMeshParse = async (explicitPath?: string) => {
    setMeshBusy(true);
    setMeshParseError(null);
    try {
      let path = explicitPath || "";
      if (!path) {
        const det = await meshtalDetect(meshOutputDir);
        setMeshFiles(det.files || []);
        if (!det.files || det.files.length === 0) {
          setMeshWorkflow("noFiles"); // F1.2 没找到文件可操作提示
          return;
        }
        path = det.files[0].path;
      }
      const pr = await meshtalParse(path, meshHasModel ? { surfaces: deck.surfaces || "", cells: meshCellsForBackend, tr_cards: deck.tr_cards || "" } : undefined);
      if (pr.status === "error") throw new Error(errorHint(pr));
      setMeshParse(pr);
      const tally = (pr.tallies || []).filter((t) => !t.unsupportedGeom)[0];
      if (!tally) {
        setMeshParseError("meshtal 中没有 GEOM=xyz 的矩形网格计数（圆柱网格 TMESH 暂不支持体积渲染）");
        setMeshWorkflow("error");
        return;
      }
      setMeshSelectedTally(tally);
      const native = [tally.dims.ni, tally.dims.nj, tally.dims.nk];
      const decision = decideResolution(native, DEFAULT_RESOLUTION);
      if (decision.popup) {
        setMeshBudget({ path, tally, native }); // F3 弹窗素材
        return;
      }
      await launchMeshWindow(path, tally, decision.resolution, pr);
    } catch (e: any) {
      setMeshParseError(errorHint(e, "解析失败"));
      setMeshWorkflow("error");
    } finally {
      setMeshBusy(false);
    }
  };

  const chooseMeshMeshtalFile = async () => {
    try {
      const j: any = await fetch(apiUrl("/api/choose-file"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
      }).then((r) => r.json());
      if (j.status === "ok" && !j.cancelled && j.path) {
        await runMeshParse(j.path);
      }
    } catch (e: any) {
      setMeshParseError(errorHint(e, "打开文件选择器失败"));
    }
  };

  const meshMatchBanner = meshParse?.match && !meshParse.match.matched
    ? `网格数据与当前模型几何可能不匹配（网格范围 X vs 模型范围 Y），可能显示错位`
    : null;
  const meshWf = workflowStep(meshWorkflow);
  const meshNoFile = noFileMessage(meshFiles.length > 0);

  const openMesh3D = () => {
    const t = meshSelectedTally;
    const p = meshParse?.file?.path || "";
    if (!t || !p) return;
    const native = [t.dims.ni, t.dims.nj, t.dims.nk];
    const decision = decideResolution(native, DEFAULT_RESOLUTION);
    if (decision.popup) {
      setMeshBudget({ path: p, tally: t, native });
      return;
    }
    launchMeshWindow(p, t, decision.resolution, meshParse);
  };

  /* ── PTRAC 入口：选择文件 + 解析并开窗 ── */
  const choosePtracFile = async () => {
    try {
      const j: any = await fetch(apiUrl("/api/choose-file"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
      }).then((r) => r.json());
      if (j.status === "ok" && !j.cancelled && j.path) {
        setPtracPath(j.path);
        setPtracParseResult(null);
        setPtracError(null);
      }
    } catch (e: any) {
      setPtracError(errorHint(e, "打开文件选择器失败"));
    }
  };

  /** 解析校验 + 开窗（手动/自动共用）：错误带 hint；开窗窗口内二次解析渲染 */
  const parseAndOpenPtrac = async (path: string) => {
    setPtracBusy(true);
    setPtracError(null);
    try {
      const pr = await ptracParse(path, 100000, 200000);
      if (pr.status === "error" || !pr.tracks) {
        setPtracError(errorHint(pr, "解析 PTRAC 失败"));
        return;
      }
      setPtracParseResult(pr);
      const out = await openPtrac3DWindow({ path, model: meshModel });
      if (!out.ok) setPtracError(out.message); // fallback / error 提示
    } catch (e: any) {
      setPtracError(errorHint(e, "解析 PTRAC 文件失败"));
    } finally {
      setPtracBusy(false);
    }
  };

  const openPtrac3D = () => {
    if (!ptracPath) return;
    parseAndOpenPtrac(ptracPath);
  };

  /** 自动探测：扫描输出目录找 ptrac → 解析并开窗（照「解析 MESHTAL」） */
  const runPtracAuto = async () => {
    setPtracError(null);
    try {
      const det = await ptracDetect(meshOutputDir);
      if (!det.files || det.files.length === 0) {
        setPtracError("输出目录里没找到 PTRAC 径迹文件（文件名应为 ptrac）。请先用 PTRAC FILE=ASC 运行 MCNP，或点「选择 ptrac 文件」手动指定。");
        return;
      }
      setPtracPath(det.files[0].path);
      await parseAndOpenPtrac(det.files[0].path);
    } catch (e: any) {
      setPtracError(errorHint(e, "探测 PTRAC 文件失败"));
    }
  };

  return (
    <>
      <input ref={fileInputRef} type="file" accept=".outp,.o,.out" style={{ display: "none" }} onChange={handleFileSelect} />
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title" style={{ flexShrink: 0 }}>输出文件</span>
          <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
            <button className="btn btn-ghost btn-xs" onClick={() => setDoc({path:"/docs/MCNP6_输出卡结构参考.md",title:"输出卡结构参考"})}>📖</button>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">MCNP 输出文件路径 (.outp/.o/.out)</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input className="form-input" style={{ flex: 1 }}
                value={filePath} readOnly placeholder="选择 MCNP 输出文件..." />
              <button className="btn btn-ghost btn-sm" onClick={handleBrowse}>浏览</button>
              <button className="btn btn-primary btn-sm" onClick={() => {
                if (selectedFile) { parseFileContent(selectedFile); return; }
                alert("请先选择输出文件");
                fileInputRef.current?.click();
              }}>解析</button>
            </div>
          </div>
        </div>
      </div>

      <div className="glass-card">
        <div className="card-header">
          <span className="card-title">Tally 结果</span>
          <div style={{ display: "flex", gap: 6 }}>
            <select className="form-select" style={{ height: 28, fontSize: 11, width: 120 }}
              value={selectedTally} onChange={e => setSelectedTally(e.target.value)}>
              {parsed ? Object.keys(parsed.tallies).map(k => (
                <option key={k} value={k}>Tally {k}</option>
              )) : <option>请先解析</option>}
            </select>
            <button className="btn btn-ghost btn-xs" onClick={() => {
              if (!parsed) { alert("请先解析输出文件"); return; }
              const tally = parsed.tallies[Number(selectedTally)];
              if (!tally || !tally.rows.length) { alert("该计数无数据"); return; }
              setChartTally(selectedTally);
            }}>绘图</button>
            <button className="btn btn-ghost btn-xs" onClick={handleExportCsv}>导出 CSV</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>能量 (MeV)</th><th>通量</th><th>相对误差</th></tr></thead>
            <tbody>
              {parsed && parsed.tallies[Number(selectedTally)] ? parsed.tallies[Number(selectedTally)].rows.concat([parsed.tallies[Number(selectedTally)].total]).map((r, i) => (
                <tr key={i} className={i === parsed.tallies[Number(selectedTally)].rows.length ? "total-row" : ""}>
                  <td>{r.energy}</td><td>{r.flux}</td><td>{r.error}</td>
                </tr>
              )) : (
                <tr><td colSpan={3} style={{ textAlign: "center", color: "var(--text-tertiary)", padding: 20 }}>
                  选择 .outp 文件并点击解析
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 网格计数 3D 结果（入口统一到输出页；契约 meshtal-visualization.md §4.7 / §12 F1/F3/F4） */}
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title" style={{ flexShrink: 0 }}>网格计数 3D 结果</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-ghost btn-xs" onClick={() => runMeshParse()} disabled={meshBusy} style={{ fontSize: 11 }}>
              {meshBusy ? "解析中…" : "解析 MESHTAL"}
            </button>
            <button className="btn btn-ghost btn-xs" onClick={chooseMeshMeshtalFile} disabled={meshBusy} style={{ fontSize: 11 }}>
              选择 meshtal 文件
            </button>
            <button
              className="btn btn-primary btn-xs"
              onClick={openMesh3D}
              disabled={meshBusy || !meshSelectedTally || !meshParse?.file?.path}
              style={{ fontSize: 11 }}
            >
              3D 体积可视化
            </button>
          </div>
        </div>

        {/* F1.1 空态三步引导 */}
        {!meshParse && !meshParseError && (
          <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.8, background: "rgba(255,255,255,0.03)", padding: "8px 10px", borderRadius: 6 }}>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>{meshWf.title}</div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {meshWf.steps.map((s) => (
                <span key={s.no} style={{ color: "var(--text-tertiary)" }}>{s.no} {s.text}</span>
              ))}
            </div>
          </div>
        )}

        {/* F1.2 没找到文件可操作提示 */}
        {meshWorkflow === "noFiles" && (
          <div style={{ fontSize: 11, marginTop: 6, color: "#ff9800" }}>
            {meshNoFile.text}，<button className="btn btn-ghost btn-xs" onClick={chooseMeshMeshtalFile} style={{ fontSize: 11, padding: "0 6px" }}>{meshNoFile.action}</button>
          </div>
        )}

        {/* A1.2 不匹配横幅（绝不静默） */}
        {meshMatchBanner && (
          <div style={{ fontSize: 11, marginTop: 6, padding: "6px 10px", background: "rgba(255,152,0,0.12)", borderRadius: 6, color: "#ff9800" }}>
            ⚠ {meshMatchBanner}
          </div>
        )}

        {/* F4 错误 hint 优先 */}
        {meshParseError && (
          <div style={{ fontSize: 11, marginTop: 6, padding: "6px 10px", background: "rgba(229,57,53,0.12)", borderRadius: 6, color: "#e53935" }}>
            {meshParseError}
          </div>
        )}

        {meshParse && (
          <div style={{ fontSize: 11, marginTop: 8, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
              计数：
              <select
                className="form-select"
                style={{ height: 26, fontSize: 11 }}
                value={meshSelectedTally ? String(meshSelectedTally.number) : ""}
                onChange={(e) => {
                  const t = meshTallies.find((x) => String(x.number) === e.target.value);
                  setMeshSelectedTally(t || null);
                }}
              >
                {meshTallies.map((t) => (
                  <option key={t.number} value={String(t.number)}>
                    Tally {t.number}（{t.particle} 网格 {t.dims.ni}×{t.dims.nj}×{t.dims.nk}）
                  </option>
                ))}
              </select>
            </label>
            <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
              已解析：{meshParse.file?.path || ""}（{meshParse.tallies?.length || 0} 个计数{meshParse.warnings?.length ? `；警告 ${meshParse.warnings.length} 条` : ""}）
            </div>
          </div>
        )}
      </div>

      {/* 粒子径迹（PTRAC）：选择/解析/开窗（契约 ptrac-visualization.md §4） */}
      <div className="glass-card">
        <div className="card-header">
          <span className="card-title" style={{ flexShrink: 0 }}>粒子径迹（PTRAC）</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-ghost btn-xs" onClick={runPtracAuto} disabled={ptracBusy} style={{ fontSize: 11 }}>
              {ptracBusy ? "解析中…" : "解析 PTRAC"}
            </button>
            <button className="btn btn-ghost btn-xs" onClick={choosePtracFile} disabled={ptracBusy} style={{ fontSize: 11 }}>
              选择 ptrac 文件
            </button>
            <button
              className="btn btn-primary btn-xs"
              onClick={openPtrac3D}
              disabled={ptracBusy || !ptracPath}
              style={{ fontSize: 11 }}
            >
              {ptracBusy ? "解析中…" : "解析并查看 3D 径迹"}
            </button>
          </div>
        </div>

        {ptracPath && (
          <div style={{ fontSize: 11, marginTop: 6, color: "var(--text-tertiary)" }}>
            已选择：{ptracPath}
          </div>
        )}

        {/* F4 错误 hint 优先 */}
        {ptracError && (
          <div style={{ fontSize: 11, marginTop: 6, padding: "6px 10px", background: "rgba(229,57,53,0.12)", borderRadius: 6, color: "#e53935" }}>
            {ptracError}
          </div>
        )}

        {ptracParseResult && (
          <div style={{ fontSize: 11, marginTop: 8, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", color: "var(--text-tertiary)" }}>
            <span>
              {ptracParseResult.stats?.nps != null ? `径迹（粒子）${ptracParseResult.stats.nps} 条` : ""}
              {ptracParseResult.stats?.events != null ? ` · 事件 ${ptracParseResult.stats.events}` : ""}
              {ptracParseResult.stats?.points != null ? ` · 点 ${ptracParseResult.stats.points}` : ""}
              {ptracParseResult.truncated ? " · ⚠ 已截断" : ""}
            </span>
          </div>
        )}
      </div>

      {/* 绘图弹窗：Tally 通量 SVG 折线图 */}
      {chartTally !== null && parsed && parsed.tallies[Number(chartTally)] && (
        <div style={{ position: "fixed", inset: 0, zIndex: 1300, background: "rgba(0,0,0,0.55)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="glass-card" style={{ maxWidth: 640, padding: 16, width: "92%" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>Tally {chartTally} 通量图</span>
              <button className="btn btn-ghost btn-xs" onClick={() => setChartTally(null)}>✕ 关闭</button>
            </div>
            <div style={{ overflowX: "auto" }}
              dangerouslySetInnerHTML={{ __html: buildFluxChartSvg(parsed.tallies[Number(chartTally)].rows) }} />
            <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 8 }}>
              红短线为相对误差（1σ）；通量跨 100 倍以上时 y 轴自动切换对数刻度。
            </div>
          </div>
        </div>
      )}

      {/* F3 超预算弹窗：要更流畅，还是要更精细？ */}
      {meshBudget && (
        <div style={{ position: "fixed", inset: 0, zIndex: 1300, background: "rgba(0,0,0,0.55)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="glass-card" style={{ maxWidth: 420, padding: 16, width: "90%" }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>{OVER_BUDGET_POPUP_COPY}</div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 12 }}>
              网格较大，全精度渲染可能卡顿。选「流畅」自动降采样保证交互顺滑；选「精细」保留原精度。
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="btn btn-primary btn-sm"
                style={{ flex: 1 }}
                onClick={() => {
                  const p = meshBudget;
                  setMeshBudget(null);
                  launchMeshWindow(p.path, p.tally, DEFAULT_RESOLUTION, meshParse); // 流畅=自动降采样
                }}
              >
                流畅（自动降采样）
              </button>
              <button
                className="btn btn-ghost btn-sm"
                style={{ flex: 1 }}
                onClick={() => {
                  const p = meshBudget;
                  setMeshBudget(null);
                  launchMeshWindow(p.path, p.tally, MAX_RESOLUTION, meshParse); // 精细=保原精度（256 显式）
                }}
              >
                精细（保原精度）
              </button>
            </div>
          </div>
        </div>
      )}

      {doc && <DocViewer path={doc.path} title={doc.title} onClose={() => setDoc(null)} />}
    </>
  );
}
