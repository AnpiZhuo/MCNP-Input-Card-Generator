/**
 * INP 生成预览 + 参数扫描（内置，不另外弹窗）。
 *
 * 功能：
 * - 展示生成的 INP 文本（可框选其中的数字来设扫描参数）
 * - 保存到目录 / 运行 MCNP / 复制 / 关闭
 * - 框选 → 设为扫描参数 → 均分快捷取值 → 多核并行扫描（内嵌面板）
 * - 每条参数一个颜色：被扫参数所在行在 textarea 背后衬一整行同色底条
 *   （按行定位而非逐字符定位，不受字体渲染差异影响，滚动同步）
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import FloatingDialog from "./FloatingDialog";
import SweepDashboard from "./SweepDashboard";
import { apiUrl, errorHint, meshtalDetect } from "../utils/api";

interface Props {
  content: string;
  onClose: () => void;
  onRegenerate?: () => void;
  outputPath?: string;
  fileName?: string;
  mcnpExe?: string;
}

const DETECTED_CORES = Math.max(1, (typeof navigator !== "undefined" && navigator.hardwareConcurrency) || 4);

const bodyStyle: React.CSSProperties = {
  flex: 1, padding: 0, fontFamily: "Consolas,monospace",
  fontSize: 12, lineHeight: 1.6, color: "var(--text-primary)",
  whiteSpace: "pre", background: "var(--editor-bg)",
};

interface ParamRow {
  name: string;
  anchor: string;
  context: string;
  values: string;
  color: string;
  lineIdx?: number;   // 参数所在行号（0-based，按 \n 分行）
}

const COLOR_PALETTE = ["#facc15", "#22d3ee", "#4ade80", "#fb923c", "#c084fc", "#f472b6"];

function hexA(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function parseValues(text: string): Array<string | number> {
  return text.split(/[\s,，]+/).filter(Boolean).map(t =>
    /^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(t) ? Number(t) : t);
}

function cartesianSize(params: ParamRow[]): number {
  return params.reduce((n, p) => n * Math.max(1, parseValues(p.values).length), 1);
}

function guessParamName(context: string, anchor: string): string {
  const kw = context.match(/[A-Za-z][A-Za-z0-9]*/);
  if (kw) return kw[0].toLowerCase();
  const a = anchor.match(/[A-Za-z]+/);
  return a ? a[0].toLowerCase() : "param";
}

function rangeValues(a: number, b: number, seg: number): number[] {
  const n = Math.max(2, Math.round(seg) + 1);
  const out: number[] = [];
  for (let k = 0; k < n; k++) out.push(a + (b - a) * k / (n - 1));
  return out;
}

function fmtNum(v: number): string {
  const r = parseFloat(v.toPrecision(12));
  return Object.is(r, -0) ? "0" : String(r);
}

const LINE_HEIGHT = 19.2;   // 12px × 1.6
const EDIT_PAD_Y = 8;
const EDIT_PAD_X = 8;

const s = {
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", display: "block", marginBottom: 4 },
  inp: { height: 32, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none", width: "100%" },
  hint: { fontSize: 11, color: "var(--text-tertiary)", marginTop: 6, lineHeight: 1.5 },
  err: { color: "#e53935", fontSize: 12, marginTop: 8 },
};

export default function PreviewDialog({ content, onClose, onRegenerate, outputPath, fileName, mcnpExe }: Props) {
  const safeName = fileName || "output.inp";

  const [sweeping, setSweeping] = useState(false);
  const [params, setParams] = useState<ParamRow[]>([]);
  const [selection, setSelection] = useState<{ start: number; end: number } | null>(null);
  const [selHint, setSelHint] = useState("");
  const [quickIdx, setQuickIdx] = useState<number | null>(null);
  const [quickA, setQuickA] = useState("");
  const [quickB, setQuickB] = useState("");
  const [quickC, setQuickC] = useState("5");
  const [workers, setWorkers] = useState(Math.min(8, DETECTED_CORES));
  const [run, setRun] = useState<{ baseDir: string; records: any[]; summaryTsv: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [view, setView] = useState<"table" | "dash">("dash");
  const [runAbort, setRunAbort] = useState<AbortController | null>(null);

  // 行底条滚动层 ref
  const stripeRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setParams([]); setRun(null); setSelHint(""); setSelection(null); setQuickIdx(null); setErr(""); }, [content]);

  const payload = useMemo(() => ({
    deck: content, workers,
    parameters: params.map(p => ({ name: p.name.trim(), anchor: p.anchor, context: p.context, values: parseValues(p.values) })).filter(p => p.name && p.anchor && p.values.length > 0),
  }), [content, params, workers]);

  const comboCount = useMemo(() => cartesianSize(params), [params]);

  /** 每条参数对应的行号 → 颜色数组（同一行可能多条参数，取最后一个颜色覆盖） */
  const lineColors = useMemo(() => {
    const map: Record<number, string> = {};
    params.forEach(p => {
      if (p.lineIdx !== undefined && p.lineIdx >= 0) map[p.lineIdx] = p.color;
    });
    return map;
  }, [params]);

  const totalLines = content.split("\n").length;
  const stripeHeight = EDIT_PAD_Y * 2 + totalLines * LINE_HEIGHT;
  const stripeWidth = `calc(100% - ${EDIT_PAD_X * 2}px)`;

  const syncStripeScroll = (ta: HTMLTextAreaElement) => {
    const s = stripeRef.current;
    if (s) { s.scrollTop = ta.scrollTop; s.scrollLeft = ta.scrollLeft; }
  };

  const handleSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const ta = e.currentTarget;
    const start = Math.min(ta.selectionStart, ta.selectionEnd);
    const end = Math.max(ta.selectionStart, ta.selectionEnd);
    setSelection({ start, end });
    const len = end - start;
    if (len > 0) { const txt = ta.value.slice(start, end).replace(/\n/g, "⏎"); setSelHint(`已选中 ${len} 字符「${txt.length > 40 ? txt.slice(0, 40) + "…" : txt}」→ 点「设为扫描参数」`); }
    else setSelHint("");
  };

  const addParamFromSelection = () => {
    setErr("");
    if (!selection || !content) { setSelHint("请先在 INP 文本里框选要变的数字"); return; }
    const { start, end } = selection;
    const anchor = content.slice(start, end).trim();
    if (!anchor) return;
    if (anchor.includes("\n")) { setSelHint("只能框选同一行里的内容"); return; }
    const lineStart = content.lastIndexOf("\n", start - 1) + 1;
    let lineEnd = content.indexOf("\n", end); if (lineEnd < 0) lineEnd = content.length;
    const context = content.slice(lineStart, lineEnd);
    const name = guessParamName(context, anchor);
    const color = COLOR_PALETTE[params.length % COLOR_PALETTE.length];
    // 计算所在行号
    const lineIdx = (content.slice(0, start).match(/\n/g) || []).length;
    setParams(ps => [...ps, { name, anchor, context, values: anchor, color, lineIdx }]);
    setQuickIdx(null);
    setSelHint(`已添加参数「${name}」：该行已用同色标出，当前值已填入`);
    setSelection(null);
  };

  const fillQuickRange = (idx: number) => {
    const a = parseFloat(quickA), b = parseFloat(quickB), c = parseInt(quickC);
    if (isNaN(a) || isNaN(b) || isNaN(c) || c < 1) { setErr("起点/终点/段数 不合法"); return; }
    setParams(ps => ps.map((p, i) => i === idx ? { ...p, values: rangeValues(a, b, c).map(fmtNum).join(" ") } : p));
    setQuickIdx(null); setErr("");
  };

  const doRun = async () => {
    setErr(""); setBusy(true); setRun(null);
    const ctrl = new AbortController(); setRunAbort(ctrl);
    const timer = setTimeout(() => { if (!ctrl.signal.aborted) ctrl.abort(new DOMException("扫描超时（120s），已中止", "TimeoutError")); }, 120000);
    try {
      const r = await fetch(apiUrl("/api/sweep-run"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal: ctrl.signal });
      const j = await r.json();
      if (j.status === "error") throw new Error(j.message);
      setRun({ baseDir: j.baseDir, records: j.records, summaryTsv: j.summaryTsv });
    } catch (e: any) {
      if (ctrl.signal.aborted) setErr((e?.name === "TimeoutError") ? "扫描超时（120s），已中止" : "扫描已取消");
      else setErr(errorHint(e, "扫描失败"));
    } finally { clearTimeout(timer); setRunAbort(null); setBusy(false); }
  };

  const runBatContent = (() => { const name = safeName.replace(/\.inp$/i, "").replace(/\.i$/i, ""); const exe = mcnpExe || "mcnp6.exe"; return `@echo off\nset CUDA_VISIBLE_DEVICES=1\ncall ${exe} inp=${safeName} outp=${name}.o\npause\n`; })();

  const nonAsciiWarn = (() => {
    const lines = content.split("\n");
    const bad = lines.filter((l, i) => /[^\x00-\x7F]/.test(l) && !l.trim().startsWith("$") && !l.trim().startsWith("C "));
    if (bad.length === 0) return null;
    return <div style={{ padding: "8px 20px", background: "rgba(255,152,0,0.15)", borderTop: "1px solid rgba(255,152,0,0.3)", fontSize: 11, color: "#ff9800" }}>⚠ {bad.length} 行包含非 ASCII 字符，MCNP 可能解析失败</div>;
  })();

  const saveToDir = async () => {
    try {
      const r = await fetch(apiUrl("/api/save-inp"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inp: content, filename: safeName, outputDir: outputPath || "D:/MCNP/new", runBat: runBatContent }) });
      const j = await r.json();
      alert(j.status === "ok" ? `✅ 已保存到: ${j.path}\nrun.bat 已生成` : "保存失败: " + (j.message || "未知错误"));
    } catch {
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([content], { type: "text/plain" })); a.download = safeName; a.click();
      const b = document.createElement("a"); b.href = URL.createObjectURL(new Blob([runBatContent], { type: "text/plain" })); b.download = safeName.replace(/\.\w+$/, "") + ".bat"; b.click();
      alert("✅ 文件已下载（后端未连接，使用浏览器下载）");
    }
  };

  const runMcnp = () => {
    const dir = outputPath || "D:/MCNP/new";
    fetch(apiUrl("/api/run-mcnp"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inp: content, filename: safeName, outputDir: dir, mcnpExe: mcnpExe || "" }) })
      .then(r => r.json()).then(j => {
        if (j.status === "ok" || j.status === "started") { alert("🚀 MCNP 已启动"); meshtalDetect(dir).then(det => { if (det.status === "ok" && det.files?.length > 0) alert("发现 " + det.files.length + " 个 MESHTAL 文件"); }).catch(() => {}); }
        else alert("启动失败: " + (j.message || "未知错误"));
      }).catch(() => alert("需要后端支持运行 MCNP"));
  };

  // 扫描面板
  const ScanPanel = () => {
    const quick = quickIdx !== null ? params[quickIdx] : null;
    const previews = (() => {
      if (quickIdx === null) return null;
      const v = rangeValues(Number(quickA || 0), Number(quickB || 0), Number(quickC || 5));
      return isNaN(v[0]) ? null : v.map(fmtNum).join("  ");
    })();
    return (
      <div style={{ marginTop: 8, borderTop: "1px solid var(--border-glass)", paddingTop: 8, fontSize: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
          <span style={s.lbl}>在 INP 里框选要变的数字</span>
          <button className="btn btn-primary btn-xs" onClick={addParamFromSelection} disabled={!selection}>＋ 设为扫描参数</button>
          <span style={{ fontSize: 11, color: "var(--text-tertiary)", flex: 1 }}>{selHint}</span>
        </div>
        <label style={s.lbl}>参数（同色 = INP 中同色底条所在行；多条会两两搭配生成全部组合）</label>
        {params.length === 0 && <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 6 }}>还没有参数——框选 INP 里的数字后点「设为扫描参数」，该行会出现彩色底条</div>}
        {params.map((p, i) => (
          <div key={i} style={{ display: "flex", gap: 6, marginBottom: 6, alignItems: "center", background: hexA(p.color, 0.06), borderLeft: `3px solid ${p.color}`, borderRadius: 6, padding: "2px 8px 2px 6px" }}>
            <span style={{ width: 8, height: 8, borderRadius: 3, background: p.color, flexShrink: 0 }} title="与上方 INP 行底条同色" />
            <input style={{ ...s.inp, width: 100 }} placeholder="名称" value={p.name} onChange={e => setParams(ps => ps.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
            <input style={{ ...s.inp, flex: 1 }} placeholder={`取值列表，如 ${p.anchor} 1000 5000`} value={p.values} onChange={e => setParams(ps => ps.map((x, j) => j === i ? { ...x, values: e.target.value } : x))} />
            <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>第{p.lineIdx! + 1}行</span>
            <button className="btn btn-ghost btn-xs" title="等分快捷取值" onClick={() => { const n = parseFloat(p.anchor); if (quickIdx === i) { setQuickIdx(null); return; } setQuickIdx(i); setQuickA(isNaN(n) ? "0" : fmtNum(n)); setQuickB(isNaN(n) ? "100" : fmtNum(n * 10)); setQuickC("5"); }}><u>等分</u></button>
            <button className="btn btn-ghost btn-xs" onClick={() => setParams(ps => ps.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        {quick && (
          <div style={{ padding: "6px 10px", background: "var(--bg-input)", borderRadius: 6, marginBottom: 6, borderLeft: `3px solid ${quick.color}` }}>
            <label style={{ ...s.lbl, color: quick.color }}>快速等分 → 对参数「{quick.name}」生成取值</label>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input style={{ ...s.inp, width: 80 }} placeholder="起点" value={quickA} onChange={e => setQuickA(e.target.value)} /><span>→</span>
              <input style={{ ...s.inp, width: 80 }} placeholder="终点" value={quickB} onChange={e => setQuickB(e.target.value)} /><span>等分成</span>
              <input style={{ ...s.inp, width: 60, textAlign: "center" }} placeholder="段" value={quickC} onChange={e => setQuickC(e.target.value)} /><span>段</span>
              {previews && <span style={{ fontSize: 11, color: "var(--accent)", marginLeft: 4 }}>（{quickC} 段 = {previews}）</span>}
              <button className="btn btn-primary btn-xs" onClick={() => { if (quickIdx !== null) fillQuickRange(quickIdx); }}>填入</button>
              <button className="btn btn-ghost btn-xs" onClick={() => setQuickIdx(null)}>收起</button>
            </div>
          </div>
        )}
        <div style={{ display: "flex", gap: 16, marginBottom: 8, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: params.length === 0 ? "var(--text-tertiary)" : "var(--text-primary)" }}>组合：{params.length === 0 ? "—" : comboCount}（上限 50）{comboCount > 50 && <span style={{ color: "#e53935" }}> —— 超上限</span>}</span>
          <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>本机 {DETECTED_CORES} 核，同时跑</span>
          <input type="range" min={1} max={DETECTED_CORES} value={workers} style={{ width: 100 }} onChange={e => setWorkers(Number(e.target.value))} />
          <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{workers} 个</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          {runAbort ? <button className="btn btn-danger btn-sm" onClick={() => runAbort.abort()} disabled={!busy}>取消</button>
            : <button className="btn btn-primary btn-sm" onClick={doRun} disabled={busy || params.length === 0 || comboCount > 50}>开始扫描（{comboCount} 组合{workers > 1 ? ` · ${workers} 路` : ""}）</button>}
        </div>
        {run && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
              <label style={{ fontSize: 12, fontWeight: 600 }}>结果（{run.records.length} 组合）</label>
              <button className="btn btn-ghost btn-xs" onClick={() => { const b = new Blob(["\uFEFF" + run.summaryTsv], { type: "text/tab-separated-values;charset=utf-8" }); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "sweep-summary.tsv"; a.click(); }}>下载 TSV</button>
              <button className="btn btn-ghost btn-xs" onClick={() => setView("dash")}>仪表盘</button>
              <button className="btn btn-ghost btn-xs" onClick={() => setView("table")}>结果表</button>
            </div>
            {view === "dash"
              ? <div style={{ maxHeight: 300, overflow: "auto" }}><SweepDashboard records={run.records} parameters={payload.parameters} /></div>
              : <div className="table-wrap" style={{ maxHeight: 180, overflow: "auto" }}><table><thead><tr><th>#</th>{payload.parameters.map(p => <th key={p.name}>{p.name}</th>)}<th>exit</th><th>keff</th></tr></thead><tbody>{run.records.map(rec => (<tr key={rec.index}><td>{rec.index}</td>{payload.parameters.map(p => <td key={p.name}>{String(rec.parameters[p.name] ?? "n/a")}</td>)}<td>{rec.exitCode === null ? "n/a" : String(rec.exitCode)}</td><td>{rec.keff === null ? "n/a" : rec.keff.toFixed(6)}</td></tr>))}</tbody></table></div>}
            <div style={s.hint}>运行目录：{run.baseDir}</div>
          </div>
        )}
        {err && <div style={s.err}>{err}</div>}
      </div>
    );
  };

  return (
    <FloatingDialog title={`INP 生成预览 — ${safeName}${sweeping ? "（扫描参数）" : ""}`}
      onClose={onClose} width={sweeping ? 1020 : 760} maxHeight="94vh"
      footer={<div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn btn-primary btn-sm" onClick={saveToDir}>💾 保存到目录</button>
        <button className="btn btn-ghost btn-sm" onClick={runMcnp}>▶ 运行 MCNP</button>
        <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard.writeText(content)}>复制</button>
        {onRegenerate && <button className="btn btn-ghost btn-sm" onClick={onRegenerate}>重新生成</button>}
        <button className="btn btn-ghost btn-sm" onClick={() => { setSweeping(!sweeping); setRun(null); setErr(""); }}>⚙ 扫描参数</button>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>关闭</button>
      </div>}>
      {sweeping ? (
        <div style={{ position: "relative", height: 380, border: "1px solid var(--border-glass)", borderRadius: 6, overflow: "hidden" }}>
          {/* 行底条层：每行一条彩色底衬，与 textarea 同行高，随滚动同步 */}
          <div ref={stripeRef} aria-hidden style={{
            position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", zIndex: 0,
          }}>
            <div style={{
              position: "relative", width: `calc(100% - ${EDIT_PAD_X * 2}px)`, height: stripeHeight,
              fontFamily: "Consolas,monospace", fontSize: 12, lineHeight: `${LINE_HEIGHT}px`,
              margin: `${EDIT_PAD_Y}px ${EDIT_PAD_X}px`, boxSizing: "border-box",
            }}>
              {Object.entries(lineColors).map(([row, color]) => (
                <div key={row} style={{
                  position: "absolute",
                  left: 0, top: `${Number(row) * LINE_HEIGHT}px`,
                  width: "100%", height: LINE_HEIGHT,
                  background: hexA(color, 0.18), borderRadius: 3,
                  borderLeft: `3px solid ${color}`,
                  boxSizing: "border-box",
                }} />
              ))}
            </div>
          </div>
          {/* 文字层：正常 textarea，背景透明以透出行底条 */}
          <textarea style={{
            position: "absolute", inset: 0, width: "100%", height: "100%", resize: "none",
            border: "none", outline: "none", zIndex: 1,
            background: "transparent",
            color: "var(--text-primary)",
            fontFamily: "Consolas,monospace", fontSize: 12, lineHeight: 1.6,
            whiteSpace: "pre", padding: `${EDIT_PAD_Y}px ${EDIT_PAD_X}px`, boxSizing: "border-box",
            caretColor: "var(--text-primary)", overflow: "auto",
          } as React.CSSProperties}
            readOnly value={content} wrap="off" spellCheck={false}
            onSelect={handleSelect}
            onScroll={e => syncStripeScroll(e.currentTarget)} />
        </div>
      ) : (
        <div style={bodyStyle}>{content}</div>
      )}
      {sweeping && ScanPanel()}
      {nonAsciiWarn}
    </FloatingDialog>
  );
}