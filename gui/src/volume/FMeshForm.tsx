/**
 * FMeshForm — 网格计数（FMESH/TMESH）表单 + 3D 体积可视化启动器
 * （契约 meshtal-visualization.md §4.7.1 / §12 F1/F2/F3/F4/F5.1）
 *
 * 两段：
 *  1. FMESH/TMESH 卡结构化表单（每输入框幽灵文字注明关键字作用，F5.1）
 *  2. 网格计数 3D 可视化启动器：F1 空态三步引导 / F1.2 没找到文件可操作提示 /
 *     F3 超预算弹窗「要更流畅，还是要更精细？」/ F4 错误 hint 优先 /
 *     A1.2 deck↔meshtal 不匹配友好横幅。
 */
import React, { useEffect, useMemo, useState } from "react";
import {
  emptyFmeshRow, fmeshToCardText, cardTextToFmesh, buildFmeshPayload,
  FMESH_PLACEHOLDERS, type FmeshKind, type FmeshRow,
} from "./fmeshState";
import { workflowStep, noFileMessage, type MeshWorkflowState } from "./workflow";
import { decideResolution, MAX_RESOLUTION, DEFAULT_RESOLUTION, OVER_BUDGET_POPUP_COPY } from "./downsampleRequest";
import {
  meshtalDetect, meshtalParse, fetchPreview3dStl, errorHint, apiUrl,
  type MeshtalParseResult, type MeshtalDetectFile, type MeshtalTallyMeta,
} from "../utils/api";
import { openVolume3D } from "../utils/windows";

interface RowWithId extends FmeshRow {
  _uid: number;
}

const FMESH_FIELD_LABELS: { key: keyof FmeshRow; label: string; placeholder: string; width?: number }[] = [
  { key: "geom", label: "GEOM", placeholder: FMESH_PLACEHOLDERS.geom, width: 120 },
  { key: "origin", label: "ORIGIN", placeholder: FMESH_PLACEHOLDERS.origin, width: 200 },
  { key: "imesh", label: "IMESH", placeholder: FMESH_PLACEHOLDERS.imesh, width: 200 },
  { key: "iints", label: "IINTS", placeholder: FMESH_PLACEHOLDERS.iints, width: 90 },
  { key: "jmesh", label: "JMESH", placeholder: FMESH_PLACEHOLDERS.jmesh, width: 200 },
  { key: "jints", label: "JINTS", placeholder: FMESH_PLACEHOLDERS.jints, width: 90 },
  { key: "kmesh", label: "KMESH", placeholder: FMESH_PLACEHOLDERS.kmesh, width: 200 },
  { key: "kints", label: "KINTS", placeholder: FMESH_PLACEHOLDERS.kints, width: 90 },
  { key: "emesh", label: "EMESH", placeholder: FMESH_PLACEHOLDERS.emesh, width: 200 },
  { key: "eints", label: "EINTS", placeholder: FMESH_PLACEHOLDERS.eints, width: 90 },
  { key: "tmesh", label: "TMESH", placeholder: FMESH_PLACEHOLDERS.tmesh, width: 200 },
  { key: "t_ints", label: "TINTS", placeholder: FMESH_PLACEHOLDERS.t_ints, width: 90 },
  { key: "mat", label: "MAT", placeholder: FMESH_PLACEHOLDERS.mat, width: 90 },
  { key: "out", label: "OUT", placeholder: FMESH_PLACEHOLDERS.out, width: 70 },
];

/** 从工作区读取 outputDir（App 把 outputPath 存进 mcnp_workspace_v1） */
function readOutputDir(): string {
  try {
    const s = JSON.parse(localStorage.getItem("mcnp_workspace_v1") || "null");
    if (s && s.outputPath) return s.outputPath;
  } catch {}
  return "D:/MCNP/new/claude";
}

export interface FMeshFormProps {
  /** FMESH/TMESH 行（受控自 deck.tally.fmesh） */
  value: FmeshRow[];
  /** 更新 rows（写回 deck.tally.fmesh） */
  onChange: (rows: FmeshRow[]) => void;
  /** 当前 deck 几何（A1.2 匹配检测 / 外壳 STL） */
  cells?: any[];
  surfaces?: string;
  trCards?: string;
}

export default function FMeshForm({ value, onChange, cells, surfaces, trCards }: FMeshFormProps) {
  const [rows, setRows] = useState<RowWithId[]>(() =>
    (value || []).map((r, i) => ({ ...r, _uid: i + 1 })),
  );
  const [outputDir] = useState(() => readOutputDir());
  const [busy, setBusy] = useState(false);
  const [workflowState, setWorkflowState] = useState<MeshWorkflowState>("idle");
  const [files, setFiles] = useState<MeshtalDetectFile[]>([]);
  const [parseResult, setParseResult] = useState<MeshtalParseResult | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [pendingBudget, setPendingBudget] = useState<{ path: string; tally: MeshtalTallyMeta; native: number[] } | null>(null);

  // 外部 value 变化（导入/文本模式回填）→ 同步本地 rows
  useEffect(() => {
    setRows((prev) => {
      const sig = JSON.stringify(value || []);
      const cur = JSON.stringify(prev.map((r) => {
        const { _uid, ...rest } = r;
        return rest;
      }));
      if (sig === cur) return prev;
      return (value || []).map((r, i) => ({ ...r, _uid: (prev[i]?._uid) ?? (Date.now() + i) }));
    });
  }, [value]);

  const pushRows = (next: RowWithId[]) => {
    setRows(next);
    onChange(next.map((r) => {
      const { _uid, ...rest } = r;
      return rest;
    }));
  };

  const updateRow = (uid: number, field: keyof FmeshRow, val: string) => {
    pushRows(rows.map((r) => (r._uid === uid ? { ...r, [field]: val } : r)));
  };
  const addRow = () => {
    pushRows([...rows, { ...emptyFmeshRow(), particle: "N", _uid: Date.now() }]);
  };
  const delRow = (uid: number) => {
    pushRows(rows.filter((r) => r._uid !== uid));
  };

  // 导出卡体（供调试/生成；生成载荷由 buildFmeshPayload 由父层调用）
  const cardText = useMemo(() => fmeshToCardText(rows), [rows]);

  const hasModel = !!(cells && cells.length) || !!surfaces;
  const parsedTally = useMemo(() => {
    const t = (parseResult?.tallies || []).filter((x) => !x.unsupportedGeom);
    return t[0] || null;
  }, [parseResult]);

  /* ── 可视化启动器：解析 → 分辨率决策 → 开窗 ── */
  const cellsForBackend = (cells || []).map((c) => ({
    number: parseInt(c.num, 10) || 0,
    material: c.mat,
    density: c.density || "",
    surface_expr: c.surfaces || c.surface_expr || "",
  }));

  async function openWindow(path: string, tally: MeshtalTallyMeta, resolution: number) {
    setBusy(true);
    try {
      const stlData = hasModel ? await fetchPreview3dStl(cellsForBackend, surfaces || "", trCards || "") : {};
      const energyOptions = buildBinOptions(tally.binEdges?.energy || []);
      const timeOptions = buildBinOptions(tally.binEdges?.time || []);
      const opened = await openVolume3D({
        stlData,
        cells: (cells || []).map((c) => ({ num: String(c.num), mat: c.mat, comment: c.comment || "" })),
        meshtal: {
          path,
          tallyNumber: tally.number,
          resolution,
          particle: tally.particle,
          geom: tally.geom,
        },
        energyOptions,
        timeOptions,
        worldBox: parseResult?.grid_bounds || null,
        scalarRange: { min: tally.range.min, max: tally.range.max },
        match: parseResult?.match || null,
      });
      if (!opened) {
        // 非 Tauri（浏览器模式）：桥数据已写 localStorage，提示可用 #/volume 调试入口
        setParseError("已写入 3D 结果数据（浏览器模式无法自动开窗，可访问 #/volume 查看）");
      }
      setWorkflowState("parsed");
    } catch (e: any) {
      setParseError(errorHint(e, "打开 3D 结果窗口失败"));
      setWorkflowState("error");
    } finally {
      setBusy(false);
    }
  }

  async function runParse(explicitPath?: string) {
    setBusy(true);
    setParseError(null);
    try {
      let path = explicitPath || "";
      if (!path) {
        const det = await meshtalDetect(outputDir);
        setFiles(det.files || []);
        if (!det.files || det.files.length === 0) {
          setWorkflowState("noFiles"); // F1.2 没找到文件可操作提示
          return;
        }
        path = det.files[0].path;
      }
      const pr = await meshtalParse(path, hasModel ? { surfaces: surfaces || "", cells: cellsForBackend, tr_cards: trCards || "" } : undefined);
      if (pr.status === "error") throw new Error(errorHint(pr));
      setParseResult(pr);
      const tally = (pr.tallies || []).filter((t) => !t.unsupportedGeom)[0];
      if (!tally) {
        setParseError("meshtal 中没有 GEOM=xyz 的矩形网格计数（圆柱网格 TMESH 暂不支持体积渲染）");
        setWorkflowState("error");
        return;
      }
      const native = [tally.dims.ni, tally.dims.nj, tally.dims.nk];
      const decision = decideResolution(native, DEFAULT_RESOLUTION);
      if (decision.popup) {
        setPendingBudget({ path, tally, native }); // F3 弹窗素材
        return;
      }
      await openWindow(path, tally, decision.resolution);
    } catch (e: any) {
      setParseError(errorHint(e, "解析失败"));
      setWorkflowState("error");
    } finally {
      setBusy(false);
    }
  }

  const chooseMeshtalFile = async () => {
    try {
      const j: any = await fetch(apiUrl("/api/choose-file"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
      }).then((r) => r.json());
      if (j.status === "ok" && !j.cancelled && j.path) {
        await runParse(j.path);
      }
    } catch (e: any) {
      setParseError(errorHint(e, "打开文件选择器失败"));
    }
  };

  const matchBanner = parseResult?.match && !parseResult.match.matched
    ? `网格数据与当前模型几何可能不匹配（网格范围 X vs 模型范围 Y），可能显示错位`
    : null;

  const wf = workflowStep(workflowState);
  const noFile = noFileMessage(files.length > 0);

  /* ── 渲染 ── */
  const input = (uid: number, field: keyof FmeshRow) => {
    const spec = FMESH_FIELD_LABELS.find((f) => f.key === field);
    return (
      <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
        <span style={{ color: "var(--text-tertiary)" }}>{spec?.label}</span>
        <input
          className="form-input"
          value={(rows.find((r) => r._uid === uid) as any)?.[field] || ""}
          onChange={(e) => updateRow(uid, field, e.target.value)}
          placeholder={spec?.placeholder}
          title={spec?.placeholder}
          style={{ height: 26, fontSize: 11, width: spec?.width || 120 }}
        />
      </label>
    );
  };

  return (
    <div className="glass-card" style={{ marginTop: 16 }}>
      <div className="card-header">
        <span className="card-title">网格计数（FMESH/TMESH）</span>
        <button className="btn btn-success btn-sm" onClick={addRow}>+ 添加网格计数</button>
      </div>

      {/* FMESH/TMESH 结构化表单（F5.1 幽灵文字） */}
      {rows.length === 0 ? (
        <div style={{ padding: "8px 14px", fontSize: 11, color: "var(--text-tertiary)" }}>
          尚无网格计数卡。点「+ 添加网格计数」创建 FMESH/TMESH 卡，或从 INP 导入自动识别。
        </div>
      ) : (
        rows.map((r) => (
          <div key={r._uid} style={{ border: "1px solid rgba(255,255,255,0.06)", borderRadius: 6, padding: 8, margin: "8px 0" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 6, flexWrap: "wrap" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                <span style={{ color: "var(--text-tertiary)" }}>类型</span>
                <select
                  className="form-select"
                  value={r.kind}
                  onChange={(e) => updateRow(r._uid, "kind", e.target.value)}
                  style={{ height: 26, fontSize: 11, width: 90 }}
                >
                  <option value="FMESH">FMESH</option>
                  <option value="TMESH">TMESH</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                <span style={{ color: "var(--text-tertiary)" }}>编号</span>
                <input className="form-input" value={r.number} onChange={(e) => updateRow(r._uid, "number", e.target.value)} placeholder="如 4" style={{ height: 26, fontSize: 11, width: 60 }} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                <span style={{ color: "var(--text-tertiary)" }}>粒子设计符</span>
                <select
                  className="form-select"
                  value={r.particle}
                  onChange={(e) => updateRow(r._uid, "particle", e.target.value)}
                  style={{ height: 26, fontSize: 11, width: 70 }}
                  title="粒子设计符：N/P/E"
                >
                  <option value="N">N（中子）</option>
                  <option value="P">P（光子）</option>
                  <option value="E">E（电子）</option>
                </select>
              </label>
              {input(r._uid, "geom")}
              {input(r._uid, "origin")}
              <button className="btn btn-danger btn-xs" onClick={() => delRow(r._uid)} style={{ marginLeft: "auto", alignSelf: "flex-end" }}>x</button>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {input(r._uid, "imesh")}{input(r._uid, "iints")}
              {input(r._uid, "jmesh")}{input(r._uid, "jints")}
              {input(r._uid, "kmesh")}{input(r._uid, "kints")}
              {input(r._uid, "emesh")}{input(r._uid, "eints")}
              {input(r._uid, "tmesh")}{input(r._uid, "t_ints")}
              {input(r._uid, "mat")}{input(r._uid, "out")}
            </div>
          </div>
        ))
      )}

      {/* 网格计数 3D 可视化启动器 */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", padding: "10px 14px", marginTop: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <span className="card-title" style={{ fontSize: 12 }}>网格计数 3D 体积可视化</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-ghost btn-xs" onClick={() => runParse()} disabled={busy} style={{ fontSize: 11 }}>
              {busy ? "解析中…" : "解析 MESHTAL"}
            </button>
            {parsedTally && (
              <button
                className="btn btn-primary btn-xs"
                onClick={() => openWindow(
                  parseResult?.file?.path || "",
                  parsedTally,
                  DEFAULT_RESOLUTION,
                )}
                disabled={busy || !parseResult?.file?.path}
                style={{ fontSize: 11 }}
              >
                打开 3D 结果
              </button>
            )}
          </div>
        </div>

        {/* F1.1 空态三步引导 */}
        {!parseResult && !parseError && (
          <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.8, background: "rgba(255,255,255,0.03)", padding: "8px 10px", borderRadius: 6 }}>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>{wf.title}</div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {wf.steps.map((s) => (
                <span key={s.no} style={{ color: "var(--text-tertiary)" }}>{s.no} {s.text}</span>
              ))}
            </div>
          </div>
        )}

        {/* F1.2 没找到文件可操作提示 */}
        {workflowState === "noFiles" && (
          <div style={{ fontSize: 11, marginTop: 6, color: "#ff9800" }}>
            {noFile.text}，<button className="btn btn-ghost btn-xs" onClick={chooseMeshtalFile} style={{ fontSize: 11, padding: "0 6px" }}>{noFile.action}</button>
          </div>
        )}

        {/* A1.2 不匹配横幅（绝不静默） */}
        {matchBanner && (
          <div style={{ fontSize: 11, marginTop: 6, padding: "6px 10px", background: "rgba(255,152,0,0.12)", borderRadius: 6, color: "#ff9800" }}>
            ⚠ {matchBanner}
          </div>
        )}

        {/* F4 错误 hint 优先 */}
        {parseError && (
          <div style={{ fontSize: 11, marginTop: 6, padding: "6px 10px", background: "rgba(229,57,53,0.12)", borderRadius: 6, color: "#e53935" }}>
            {parseError}
          </div>
        )}

        {parseResult && (
          <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 6 }}>
            已解析：{parseResult.file?.path || ""}（{parseResult.tallies?.length || 0} 个计数，{parsedTally ? `选中 ${parsedTally.particle} 网格 ${parsedTally.dims.ni}×${parsedTally.dims.nj}×${parsedTally.dims.nk}` : ""}）
            {parseResult.warnings?.length ? `；警告 ${parseResult.warnings.length} 条` : ""}
          </div>
        )}
      </div>

      {/* F3 超预算弹窗：要更流畅，还是要更精细？ */}
      {pendingBudget && (
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
                  const p = pendingBudget;
                  setPendingBudget(null);
                  openWindow(p.path, p.tally, DEFAULT_RESOLUTION); // 流畅=自动降采样
                }}
              >
                流畅（自动降采样）
              </button>
              <button
                className="btn btn-ghost btn-sm"
                style={{ flex: 1 }}
                onClick={() => {
                  const p = pendingBudget;
                  setPendingBudget(null);
                  openWindow(p.path, p.tally, MAX_RESOLUTION); // 精细=保原精度（256 显式）
                }}
              >
                精细（保原精度）
              </button>
            </div>
          </div>
        </div>
      )}

      {cardText && (
        <details style={{ fontSize: 10, color: "var(--text-tertiary)", padding: "4px 14px" }}>
          <summary style={{ cursor: "pointer" }}>当前卡体预览（点击展开）</summary>
          <pre style={{ background: "rgba(0,0,0,0.3)", padding: 8, borderRadius: 4, fontFamily: "Consolas,monospace", fontSize: 11, whiteSpace: "pre-wrap" }}>{cardText}</pre>
        </details>
      )}
    </div>
  );
}

function buildBinOptions(edges: number[]): { index: number; label: string }[] {
  if (!edges || edges.length < 2) return [];
  const opts: { index: number; label: string }[] = [];
  for (let i = 0; i < edges.length - 1; i++) {
    opts.push({ index: i, label: fmtBound(edges[i]) + " → " + fmtBound(edges[i + 1]) });
  }
  return opts;
}

function fmtBound(v: number): string {
  if (v === 1e36) return "∞";
  if (Number.isInteger(v)) return String(v);
  return String(Math.round(v * 1000) / 1000);
}
