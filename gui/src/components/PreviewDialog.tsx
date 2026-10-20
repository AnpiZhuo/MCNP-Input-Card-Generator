/**
 * INP 生成预览 + 参数扫描（内置，不另外弹窗）。
 *
 * 功能：
 * - 展示生成的 INP 文本（**与「曲面卡」同一编辑器模块** = `McnpEditor`(Monaco)；
 *   可框选其中的任意字符来设扫描参数）
 * - 保存到目录 / 运行 MCNP / 复制 / 关闭
 * - 框选 → 设为扫描参数 → 均分快捷取值 → 多核并行扫描（内嵌面板）
 * - **显式计算（2026-10-20）**：每个组合由后端开一个可见 MCNP 控制台窗口（标题 sweep-00N）；
 *   前端不设超时、不 abort —— 关掉那个窗口 = 中止该组合，其余组合照常。
 * - 每条参数一个颜色，**局部高亮它自己的那几个字符**（Monaco decoration 按字符区间画；
 *   2026-10-11 用户要求：原先的"整行色底条 + textarea 叠层"已删除）
 *
 * 替换语义（用户 2026-10-11 逐字确认）：**只删掉框选中的那几个字符**，把取值原样插进去，
 * 长度不限 —— 位置（start/end）随参数一起发给后端，后端只认这个区间。
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import FloatingDialog from "./FloatingDialog";
import McnpEditor from "./McnpEditor";
import SweepDashboard from "./SweepDashboard";
import { apiUrl, errorHint, meshtalDetect } from "../utils/api";
import { selectionSpan } from "../utils/selectionSpan";
import { parseValues } from "../utils/sweepValues";
import { SWEEP_COLORS, ensureSweepHighlightStyles, sweepHighlightClass } from "../utils/sweepHighlight";

interface Props {
  content: string;
  onClose: () => void;
  onRegenerate?: () => void;
  outputPath?: string;
  fileName?: string;
  mcnpExe?: string;
  /** 生成时栅元封闭性自检警告（可选） */
  closureGenerateWarn?: string | null;
  onClearClosureGenerateWarn?: () => void;
}

import { DETECTED_CORES, DEFAULT_WORKERS, SUGGESTED_WORKERS, clampWorkers } from "../utils/detectedCores";

interface ParamRow {
  /** 给人看的标签 = **用户框选到的原文**（允许重复 —— 界面上不挂 `#1`/`#2` 后缀） */
  name: string;
  /** 取值的内部键（唯一；`records[].parameters` / 组合字典按它查） */
  key: string;
  anchor: string;
  context: string;
  values: string;
  color: string;
  lineIdx?: number;   // 参数所在行号（0-based，按 \n 分行）
  /** 选区在 deck 文本里的字符偏移：后端**只认这个区间**（删掉它、插入新值，长度不限） */
  start: number;
  end: number;
}

function hexA(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function cartesianSize(params: ParamRow[]): number {
  return params.reduce((n, p) => n * Math.max(1, parseValues(p.values).values.length), 1);
}

/**
 * 参数名 = **用户划到的内容**（用户 2026-10-11：不要 `df4`/`param` 这种猜出来的名字，
 * 也**不要** `#1`/`#2` 重名后缀）。重名靠看不见的 `key` 区分（见 ParamRow）。
 */

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


const s = {
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", display: "block", marginBottom: 4 },
  inp: { height: 32, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none", width: "100%" },
  hint: { fontSize: 11, color: "var(--text-tertiary)", marginTop: 6, lineHeight: 1.5 },
  err: { color: "#e53935", fontSize: 12, marginTop: 8 },
};

export default function PreviewDialog({ content, onClose, onRegenerate, outputPath, fileName, mcnpExe, closureGenerateWarn, onClearClosureGenerateWarn }: Props) {
  const safeName = fileName || "output.inp";

  const [sweeping, setSweeping] = useState(false);
  const [params, setParams] = useState<ParamRow[]>([]);
  const [selection, setSelection] = useState<{ start: number; end: number } | null>(null);
  const [selHint, setSelHint] = useState("");
  const [quickIdx, setQuickIdx] = useState<number | null>(null);
  const [quickA, setQuickA] = useState("");
  const [quickB, setQuickB] = useState("");
  const [quickC, setQuickC] = useState("5");
  const [workers, setWorkers] = useState(DEFAULT_WORKERS);
  const [run, setRun] = useState<{ baseDir: string; records: any[]; summaryTsv: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  /** 后端回传的定位类告警（框选位置失效等）：必须显示出来，绝不静默 */
  const [warnings, setWarnings] = useState<string[]>([]);
  const [view, setView] = useState<"table" | "dash">("dash");
  /** 参数内部键序号（名称可以重复，键不行；见 ParamRow.key） */
  const keySeq = useRef(0);

  useEffect(() => { setParams([]); setRun(null); setSelHint(""); setSelection(null); setQuickIdx(null); setErr(""); }, [content]);
  // 参数高亮的 CSS 类（Monaco 的 inlineClassName 只认类名）——幂等注入一次
  useEffect(() => { ensureSweepHighlightStyles(); }, []);

  const payload = useMemo(() => ({
    deck: content, workers,
    parameters: params.map(p => ({ name: p.name.trim() || p.key, key: p.key,
                                   anchor: p.anchor, context: p.context,
                                   start: p.start, end: p.end,
                                   values: parseValues(p.values).values }))
                      .filter(p => p.anchor && p.values.length > 0),
  }), [content, params, workers]);

  const comboCount = useMemo(() => cartesianSize(params), [params]);
  /** 取值语法错误（如引号没配对）：有错就不许开始扫描（否则会静默少跑或跑错内容） */
  const valuesError = useMemo(
    () => params.map(p => parseValues(p.values).error).find(e => e) || "",
    [params]);

  /** 参数扫描的**局部高亮**：每条参数标出它自己的那几个字符（Monaco decoration，按区间） */
  const highlights = useMemo(
    () => params.map(p => ({
      start: p.start, end: p.end,
      className: sweepHighlightClass(SWEEP_COLORS.indexOf(p.color)),
    })),
    [params]);

  /** 选区变化（Monaco 回报字符偏移）：记住"用户划了哪几个字符" */
  const handleSelect = (start: number, end: number) => {
    setSelection({ start, end });
    const len = end - start;
    if (len > 0) {
      const txt = content.slice(start, end).replace(/\n/g, "⏎");
      setSelHint(`已选中 ${len} 字符「${txt.length > 40 ? txt.slice(0, 40) + "…" : txt}」→ 点「设为扫描参数」`);
    } else setSelHint("");
  };

  const addParamFromSelection = () => {
    setErr("");
    if (!selection || !content) { setSelHint("请先在 INP 文本里框选要变的数字"); return; }
    // 「我划了这些文字，你就把这些文字删掉、用我给的内容替换」——位置必须一起记住，
    // 否则后端只能自己猜"首个匹配"，同一个字出现两次就改错地方。
    const span = selectionSpan(content, selection.start, selection.end);
    if (!span) {
      setSelHint(selection.start === selection.end
        ? "选中的是空白，请重新框选"
        : "只能框选同一行里的内容");
      return;
    }
    const { anchor, start, end } = span;
    const lineStart = content.lastIndexOf("\n", start - 1) + 1;
    let lineEnd = content.indexOf("\n", end); if (lineEnd < 0) lineEnd = content.length;
    const context = content.slice(lineStart, lineEnd);
    // 名称 = **框选到的内容本身**（可重复）；唯一性放在看不见的 key 上
    // （用户 2026-10-11：界面上不许出现 `#1`/`#2` 这类后缀，看着像色号）
    keySeq.current += 1;
    const key = `p${keySeq.current}`;
    const color = SWEEP_COLORS[params.length % SWEEP_COLORS.length];
    // 计算所在行号
    const lineIdx = (content.slice(0, start).match(/\n/g) || []).length;
    setParams(ps => [...ps, { name: anchor, key, anchor, context, values: anchor, color, lineIdx, start, end }]);
    setQuickIdx(null);
    setSelHint(`已添加参数「${anchor}」：将替换第 ${lineIdx + 1} 行的这几个字符，当前值已填入`);
    setSelection(null);
  };

  const fillQuickRange = (idx: number) => {
    const a = parseFloat(quickA), b = parseFloat(quickB), c = parseInt(quickC);
    if (isNaN(a) || isNaN(b) || isNaN(c) || c < 1) { setErr("起点/终点/段数 不合法"); return; }
    setParams(ps => ps.map((p, i) => i === idx ? { ...p, values: rangeValues(a, b, c).map(fmtNum).join(" ") } : p));
    setQuickIdx(null); setErr("");
  };

  const doRun = async () => {
    setErr(""); setBusy(true); setRun(null); setWarnings([]);
    // 显式计算（2026-10-20 用户口径）：每个组合由后端开一个可见 MCNP 控制台窗口，
    // **前端不设超时**、不带 AbortSignal —— 等所有窗口结束（算完自动关，或用户手动关掉
    // 中止该组合）。中止 MCNP 的唯一方式就是关那个控制台窗口，程序不主动 abort。
    try {
      const r = await fetch(apiUrl("/api/sweep-run"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const j = await r.json();
      if (j.status === "error") throw new Error(j.message);
      setRun({ baseDir: j.baseDir, records: j.records, summaryTsv: j.summaryTsv });
      setWarnings(j.warnings || []);
    } catch (e: any) {
      setErr(errorHint(e, "扫描失败"));
    } finally { setBusy(false); }
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
    // tasks = 本对话框的核数（与「扫描参数」面板共享同一 workers，见 detectedCores.ts）。
    // 后端会扫卡：命中 PTRAC / SSW / SSR / DBCN(2,3,4) 时强制降为 1 并回传 tasksNote
    //（C810 页 875：这些与 tasks > 1 不兼容，MCNP 会直接 FATAL）。
    fetch(apiUrl("/api/run-mcnp"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inp: content, filename: safeName, outputDir: dir, mcnpExe: mcnpExe || "", tasks: workers }) })
      .then(r => r.json()).then(j => {
        if (j.status === "ok" || j.status === "started") {
          alert("🚀 MCNP 已启动" + (j.tasks ? `（tasks ${j.tasks}）` : "") + (j.tasksNote ? "\n\n⚠ " + j.tasksNote : ""));
          meshtalDetect(dir).then(det => { if (det.status === "ok" && det.files?.length > 0) alert("发现 " + det.files.length + " 个 MESHTAL 文件"); }).catch(() => {});
        }
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
        <label style={s.lbl}>参数（同色 = INP 里高亮的**那几个字符**；多条会两两搭配生成全部组合）</label>
        {params.length === 0 && <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 6 }}>还没有参数——框选 INP 里的数字后点「设为扫描参数」，你划中的那几个字符会被涂成同色高亮</div>}
        {params.map((p, i) => (
          <div key={i} style={{ marginBottom: 6 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", background: hexA(p.color, 0.06), borderLeft: `3px solid ${p.color}`, borderRadius: 6, padding: "2px 8px 2px 6px" }}>
            <span style={{ width: 8, height: 8, borderRadius: 3, background: p.color, flexShrink: 0 }} title="与 INP 里高亮那几个字符的颜色相同" />
            <input style={{ ...s.inp, width: 100 }} placeholder="名称" value={p.name} onChange={e => setParams(ps => ps.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
            <input style={{ ...s.inp, flex: 1 }} placeholder={`取值列表，如 ${p.anchor} 1000 5000；含空格的用引号，如 "n p"`} value={p.values} onChange={e => setParams(ps => ps.map((x, j) => j === i ? { ...x, values: e.target.value } : x))} />
            <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>第{p.lineIdx! + 1}行</span>
            <button className="btn btn-ghost btn-xs" title="等分快捷取值" onClick={() => { const n = parseFloat(p.anchor); if (quickIdx === i) { setQuickIdx(null); return; } setQuickIdx(i); setQuickA(isNaN(n) ? "0" : fmtNum(n)); setQuickB(isNaN(n) ? "100" : fmtNum(n * 10)); setQuickC("5"); }}><u>等分</u></button>
            <button className="btn btn-ghost btn-xs" onClick={() => setParams(ps => ps.filter((_, j) => j !== i))}>×</button>
          </div>
          {/* 取值语法错误（如引号没配对）就地显示：非静默，且禁止开始扫描 */}
          {parseValues(p.values).error && (
            <div style={{ fontSize: 10, color: "#e53935", marginLeft: 14 }}>{parseValues(p.values).error}</div>
          )}
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
        <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
          <button className="btn btn-primary btn-sm" onClick={doRun} disabled={busy || params.length === 0 || comboCount > 50 || !!valuesError}>
            {busy ? "扫描中（等 MCNP 窗口结束）…" : `开始扫描（${comboCount} 组合${workers > 1 ? ` · ${workers} 路` : ""}）`}
          </button>
          <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
            每个组合弹一个 MCNP 控制台窗口（标题 sweep-00N）；<b>本程序不设超时</b> —— MCNP 算完窗口自动关闭，
            发现异常直接关掉那个窗口就是中止它，其余组合照常跑完。
          </span>
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
              : <div className="table-wrap" style={{ maxHeight: 180, overflow: "auto" }}><table><thead><tr><th>序号</th>{payload.parameters.map(p => <th key={p.key}>{p.name}</th>)}<th>exit</th><th>keff</th></tr></thead><tbody>{run.records.map(rec => (<tr key={rec.index}><td>{rec.index}</td>{payload.parameters.map(p => <td key={p.key}>{String(rec.parameters[p.key] ?? "n/a")}</td>)}<td>{rec.exitCode === null ? "n/a" : String(rec.exitCode)}</td><td>{rec.keff === null ? "n/a" : rec.keff.toFixed(6)}</td></tr>))}</tbody></table></div>}
            <div style={s.hint}>运行目录：{run.baseDir}</div>
          </div>
        )}
        {warnings.length > 0 && (
          <div style={{ ...s.err, background: "rgba(255,152,0,0.15)", color: "#ff9800" }}>
            ⚠ {warnings.length} 条参数没能在输入卡里定位（这些组合按下的是原始内容）：
            <ul style={{ margin: "4px 0 0 16px" }}>
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
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
        {/* 核数：同时决定「运行 MCNP」的 tasks 与「扫描参数」的并发路数（共享同一 workers state）。
            ⚠️ MCNP 的 tasks 取**物理核数**最优 —— 实测本机（8 物理核/16 逻辑核）tasks 8 用 8.36s，
            而 tasks 16 反而要 15.06s（超订，SMT 无吞吐收益且大量自旋）。见 utils/detectedCores.ts。 */}
        <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}
          title={`本机 ${DETECTED_CORES} 个逻辑核；MCNP 的 tasks 取物理核数最优（推荐 ${SUGGESTED_WORKERS}）—— 超过物理核会因超订反而变慢`}>CPU</span>
        <input type="range" min={1} max={DETECTED_CORES} step={1} value={workers}
          style={{ width: 76 }} onChange={e => setWorkers(clampWorkers(Number(e.target.value)))} />
        <span style={{ fontSize: 11, color: workers === SUGGESTED_WORKERS ? "var(--accent)" : "var(--text-tertiary)" }}>{workers}</span>
        <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard.writeText(content)}>复制</button>
        {onRegenerate && <button className="btn btn-ghost btn-sm" onClick={onRegenerate}>重新生成</button>}
        <button className="btn btn-ghost btn-sm" onClick={() => { setSweeping(!sweeping); setRun(null); setErr(""); }}>⚙ 扫描参数</button>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>关闭</button>
      </div>}>
      {closureGenerateWarn && (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "8px 12px", marginBottom: 8, borderRadius: 6, background: "rgba(229,57,53,0.08)", border: "1px solid rgba(229,57,53,0.3)", fontSize: 11, lineHeight: 1.6 }}>
          <span style={{ color: "#e53935", flexShrink: 0, fontWeight: 700 }}>⚠</span>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap", color: "var(--text-primary)" }}>{closureGenerateWarn}</pre>
          {onClearClosureGenerateWarn && <button className="btn btn-ghost btn-xs" style={{ flexShrink: 0, marginLeft: "auto" }} onClick={onClearClosureGenerateWarn}>×</button>}
        </div>
      )}
      {sweeping ? (
        <div style={{ border: "1px solid var(--border-glass)", borderRadius: 6, overflow: "hidden" }}>
          {/* 文字层：与「曲面卡」同一个编辑器模块（Monaco）。
              高亮 = 参数扫到的**那几个字符**（按字符区间画），不再是整行色条。 */}
          <McnpEditor id="preview-inp" value={content} mode="deck" readOnly minHeight={380}
            highlights={highlights} onSelect={handleSelect} />
        </div>
      ) : (
        <McnpEditor id="preview-inp-view" value={content} mode="deck" readOnly minHeight={380} />
      )}
      {sweeping && ScanPanel()}
      {nonAsciiWarn}
    </FloatingDialog>
  );
}