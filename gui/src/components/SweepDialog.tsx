/**
 * 参数扫描弹窗（免正则版）：基于当前工作区 deck 生成 INP 文本。
 *
 * 用法三步：
 *   1) 在下方"基准 INP"预览里用鼠标选中要变的数字/文本（如 nps 1000000 里的 1000000）；
 *   2) 点「＋ 设为扫描参数」→ 底部参数行自动出现（名称自动取卡片名，可改），填要试的取值；
 *   3) 选"同时跑几个"（检测本机核数，默认最多 8），点「开始扫描」。
 *
 * 后端对参数做笛卡尔积；支持多参数（可反复添加，哪怕同一行里的多个数也能各自扫）。
 * 每个组合独立子进程 + name=sweep-XXX. 输出文件（sweep-001.o …），并发互不覆盖。
 */
import React, { useEffect, useMemo, useState } from "react";
import { apiUrl, errorHint } from "../utils/api";
import { useDeck } from "../utils/DeckContext";
import { generateInp } from "../utils/dataCollector";
import FloatingDialog from "./FloatingDialog";
import SweepDashboard from "./SweepDashboard";

/** doRun 请求级超时（ms）：后端负责预算拒绝/请求级超时（返回明确错误消息），
 *  前端超时只作兜底，防止大组合 fetch 无限挂起。MCNP 逐组合运行较久，故给 120s。 */
const SWEEP_RUN_TIMEOUT_MS = 120000;

/** 本机逻辑核数（Tauri WebView / 浏览器均支持 navigator.hardwareConcurrency） */
const DETECTED_CORES = Math.max(1, (typeof navigator !== "undefined" && navigator.hardwareConcurrency) || 4);

/** 参数行：anchor=用户选中的原文（要替换的值）；context=所在整行（用于唯一定位） */
export interface ParamRow { name: string; anchor: string; context: string; values: string; }
interface RunRecord {
  index: number;
  parameters: Record<string, string | number>;
  exitCode: number | null;
  keff: number | null;
  keffStd?: number | null;
  convergence?: { cycles: number[]; mean: number[]; std: number[] } | null;
}
interface RunResult { baseDir: string; records: RunRecord[]; summaryTsv: string; }

const s = {
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", display: "block", marginBottom: 4 },
  inp: { height: 32, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none", width: "100%" },
  area: { width: "100%", minHeight: 120, maxHeight: 220, resize: "vertical", padding: 8, borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 11, fontFamily: "Consolas,monospace", lineHeight: 1.5, outline: "none" },
  err: { color: "#e53935", fontSize: 12, marginTop: 8 },
  hint: { fontSize: 11, color: "var(--text-tertiary)", marginTop: 6, lineHeight: 1.5 },
};

export function parseValues(text: string): Array<string | number> {
  return text.split(/[\s,，]+/).filter(Boolean).map(t =>
    /^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(t) ? Number(t) : t);
}

export function cartesianSize(params: ParamRow[]): number {
  return params.reduce((n, p) => n * Math.max(1, parseValues(p.values).length), 1);
}

/** 从选中处所在的整行猜参数名：优先取行内英文字母词（nps/kcode/m1…），否则退 anchor 里的字母 */
export function guessParamName(context: string, anchor: string): string {
  const kw = context.match(/[A-Za-z][A-Za-z0-9]*/);
  if (kw) return kw[0].toLowerCase();
  const a = anchor.match(/[A-Za-z]+/);
  return a ? a[0].toLowerCase() : "param";
}

export default function SweepDialog({ onClose }: { onClose: () => void }) {
  const { deck } = useDeck();
  const [baseText, setBaseText] = useState("");
  const [genBusy, setGenBusy] = useState(false);
  const [params, setParams] = useState<ParamRow[]>([]);
  const [selHint, setSelHint] = useState("");          // 选中状态提示（选了几个字符/在哪个位置）
  const [selection, setSelection] = useState<{ start: number; end: number } | null>(null);
  const [workers, setWorkers] = useState(Math.min(8, DETECTED_CORES));
  const [plan, setPlan] = useState<{ count: number; previews: string[] } | null>(null);
  const [run, setRun] = useState<RunResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [view, setView] = useState<"table" | "dash">("dash");
  // T3：doRun 进行中的 AbortController（供「取消」按钮中止请求；完成后/中止后置 null）
  const [runAbort, setRunAbort] = useState<AbortController | null>(null);

  const gen = async () => {
    setGenBusy(true); setErr("");
    try {
      const text = await generateInp(deck);
      setBaseText(text);
      // 文本变了，旧的选中/锚点可能错位 → 清空参数与规划，防止替换到错位置
      setParams([]); setPlan(null); setSelection(null); setSelHint("");
    } catch (e: any) { setErr(errorHint(e, "生成 INP 失败（请先检查表单）")); }
    finally { setGenBusy(false); }
  };
  useEffect(() => { gen(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  /** 记录 textarea 当前选区（含整行 context 预览提示） */
  const handleSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const ta = e.currentTarget;
    const start = Math.min(ta.selectionStart, ta.selectionEnd);
    const end = Math.max(ta.selectionStart, ta.selectionEnd);
    setSelection({ start, end });
    const len = end - start;
    if (len > 0) {
      const text = ta.value.slice(start, end).replace(/\n/g, "⏎");
      setSelHint(`已选中 ${len} 个字符：「${text.length > 40 ? text.slice(0, 40) + "…" : text}」→ 点下面「设为扫描参数」`);
    } else {
      setSelHint("");
    }
  };

  /** 把当前选区变成一条扫描参数（anchor=选中原文，context=选中处所在整行） */
  const addParamFromSelection = () => {
    setErr("");
    if (!selection || !baseText) { setSelHint("请先在基准 INP 里用鼠标选中要变的数字或文本"); return; }
    const { start, end } = selection;
    const anchor = baseText.slice(start, end);
    if (!anchor.trim()) { setSelHint("选中的内容为空，请重新框选"); return; }
    if (anchor.includes("\n")) { setSelHint("只能选中同一行里的内容，请重新框选"); return; }
    // 所在整行
    const lineStart = baseText.lastIndexOf("\n", start - 1) + 1;
    let lineEnd = baseText.indexOf("\n", end);
    if (lineEnd < 0) lineEnd = baseText.length;
    const context = baseText.slice(lineStart, lineEnd);
    const name = guessParamName(context, anchor);
    setParams(ps => [...ps, { name, anchor, context, values: anchor }]);
    setSelection(null);
    setPlan(null);
    setSelHint(`已添加参数「${name}」：替换行内「${anchor}」，取值默认填了当前值，可改成多个（空格分隔）`);
  };

  const payload = useMemo(() => ({
    deck: baseText,
    workers,
    parameters: params
      .map(p => ({ name: p.name.trim(), anchor: p.anchor, context: p.context, values: parseValues(p.values) }))
      .filter(p => p.name && p.anchor && p.values.length > 0),
  }), [baseText, params, workers]);

  const comboCount = useMemo(() => cartesianSize(params), [params]);

  const doPlan = async () => {
    setErr(""); setBusy(true); setPlan(null);
    try {
      const r = await fetch(apiUrl("/api/sweep-plan"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload), signal: AbortSignal.timeout(15000),
      });
      const j = await r.json();
      if (j.status === "error") throw new Error(j.message);
      setPlan({ count: j.count, previews: j.previews || [] });
    } catch (e: any) { setErr(errorHint(e, "规划失败")); }
    finally { setBusy(false); }
  };

  const doRun = async () => {
    setErr(""); setBusy(true); setRun(null);
    // T3：可取消 + 超时兜底（后端拒绝超预算请求时由 catch 显示后端错误消息）
    const ctrl = new AbortController();
    setRunAbort(ctrl);
    const timer = setTimeout(() => {
      if (!ctrl.signal.aborted) ctrl.abort(new DOMException("扫描超时（120s），已中止", "TimeoutError"));
    }, SWEEP_RUN_TIMEOUT_MS);
    try {
      const r = await fetch(apiUrl("/api/sweep-run"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload), signal: ctrl.signal,
      });
      const j = await r.json();
      if (j.status === "error") throw new Error(j.message);
      setRun({ baseDir: j.baseDir, records: j.records, summaryTsv: j.summaryTsv });
    } catch (e: any) {
      if (ctrl.signal.aborted) {
        // 主动取消/超时：用固定文案（不要取 e.message，AbortError.message 无用户语义）
        setErr((e && e.name === "TimeoutError") ? "扫描超时（120s），已中止" : "扫描已取消");
      } else {
        setErr(errorHint(e, "扫描失败"));
      }
    } finally {
      clearTimeout(timer);
      setRunAbort(null);
      setBusy(false);
    }
  };

  const downloadTsv = () => {
    if (!run) return;
    const blob = new Blob(["\uFEFF" + run.summaryTsv + "\n"],
      { type: "text/tab-separated-values;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "sweep-summary.tsv";
    a.click();
  };

  return (
    <FloatingDialog title="参数扫描（批量改参数 · 多核并行跑 MCNP）" onClose={onClose} width={820}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>关闭</button>
          <button className="btn btn-ghost btn-sm" onClick={doPlan} disabled={busy || !baseText || params.length === 0}>
            {busy ? "处理中…" : "规划预览"}
          </button>
          {runAbort
            ? <button className="btn btn-danger btn-sm" onClick={() => runAbort.abort()} disabled={!busy}>取消</button>
            : null}
          <button className="btn btn-primary btn-sm" onClick={doRun} disabled={busy || !baseText || params.length === 0 || comboCount > 50}>
            {busy ? "扫描中…" : `开始扫描（${comboCount} 组合${workers > 1 ? ` · ${workers} 路并行` : ""}）`}
          </button>
        </>
      }>
      <div style={{ fontSize: 12 }}>
        {/* ① 基准 INP：可框选 */}
        <div style={{ marginBottom: 8 }}>
          <label style={s.lbl}>① 基准 INP —— 用鼠标<b>框选</b>要变的数字/文本（改动表单后点重新生成）</label>
          <textarea style={s.area} readOnly value={genBusy ? "正在生成…" : baseText}
            placeholder="点击「重新生成」从当前工作区生成基准 INP…" spellCheck={false}
            onSelect={handleSelect} />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
            <button className="btn btn-ghost btn-xs" onClick={gen} disabled={genBusy}>重新生成</button>
            <button className="btn btn-primary btn-xs" onClick={addParamFromSelection}
              disabled={!selection || genBusy}>＋ 设为扫描参数（用选中的内容）</button>
            <span style={{ fontSize: 11, color: "var(--text-tertiary)", flex: 1 }}>{selHint}</span>
          </div>
        </div>

        {/* ② 参数行 */}
        <label style={s.lbl}>② 扫描参数（可加多条，取值用空格/逗号分隔；多条之间做笛卡尔组合）</label>
        {params.length === 0
          ? <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 6 }}>
              还没有参数 —— 在上方框选一个数字后点「设为扫描参数」，比如把 nps 1000000 里的 1000000 框选出来。
            </div>
          : null}
        {params.map((p, i) => (
          <div key={i} style={{ display: "flex", gap: 6, marginBottom: 6, alignItems: "center" }}>
            <input style={{ ...s.inp, width: 100 }} placeholder="名称" value={p.name}
              onChange={e => setParams(ps => ps.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
            <input style={{ ...s.inp, flex: 1 }} placeholder={`取值列表，如 ${p.anchor} 5000 10000`} value={p.values}
              title="空格/逗号分隔的多个取值，会替换掉选中位置"
              onChange={e => setParams(ps => ps.map((x, j) => j === i ? { ...x, values: e.target.value } : x))} />
            <span style={{ fontSize: 10, color: "var(--text-tertiary)", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
              title={`定位行：${p.context}\n选中的原文：${p.anchor}`}>
              ↳ {p.context}
            </span>
            <button className="btn btn-ghost btn-xs" onClick={() => setParams(ps => ps.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
            组合数：{params.length === 0 ? "—" : comboCount}（后端上限 50）
            {comboCount > 50 ? <span style={{ color: "#e53935" }}> —— 超上限，请减少参数或取值个数</span> : null}
          </span>
        </div>

        {/* ③ 并行数 */}
        <div style={{ marginBottom: 10 }}>
          <label style={s.lbl}>③ 同时跑几个（本机检测到 {DETECTED_CORES} 个逻辑核；MCNP 每个组合用 1 核，多路并行才能吃满 CPU）</label>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <input type="range" min={1} max={DETECTED_CORES} step={1} value={workers}
              style={{ flex: 1 }}
              onChange={e => setWorkers(Number(e.target.value))} />
            <input type="number" min={1} max={DETECTED_CORES} value={workers}
              style={{ ...s.inp, width: 70, textAlign: "center" }}
              onChange={e => {
                const v = Number(e.target.value);
                setWorkers(Number.isFinite(v) ? Math.max(1, Math.min(DETECTED_CORES, v)) : 1);
              }} />
            <button className="btn btn-ghost btn-xs" onClick={() => setWorkers(Math.min(8, DETECTED_CORES))}>默认 8</button>
            <button className="btn btn-ghost btn-xs" onClick={() => setWorkers(DETECTED_CORES)}>全核 {DETECTED_CORES}</button>
          </div>
        </div>

        {/* 规划预览 */}
        {plan ? (
          <div style={{ marginBottom: 10 }}>
            <label style={s.lbl}>规划：{plan.count} 组合（前 3 组预览，检查替换位置是否正确）</label>
            {plan.previews.map((t, i) => (
              <pre key={i} style={{ background: "var(--bg-input)", padding: 8, borderRadius: 6, fontSize: 11, maxHeight: 90, overflow: "auto", margin: "4px 0" }}>{t}</pre>
            ))}
          </div>
        ) : null}

        {/* 结果 */}
        {run ? (
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600 }}>执行结果（{run.records.length} 组合）</label>
              <button className="btn btn-ghost btn-xs" onClick={downloadTsv}>下载 TSV</button>
              <button className="btn btn-ghost btn-xs" onClick={() => setView("dash")}>仪表盘</button>
              <button className="btn btn-ghost btn-xs" onClick={() => setView("table")}>结果表</button>
            </div>
            {view === "dash"
              ? <div style={{ maxHeight: 460, overflow: "auto" }}>
                  <SweepDashboard records={run.records} parameters={payload.parameters} />
                </div>
              : <div className="table-wrap" style={{ maxHeight: 240, overflow: "auto" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        {payload.parameters.map(p => <th key={p.name}>{p.name}</th>)}
                        <th>exit</th>
                        <th>keff</th>
                      </tr>
                    </thead>
                    <tbody>
                      {run.records.map(rec => (
                        <tr key={rec.index}>
                          <td>{rec.index}</td>
                          {payload.parameters.map(p => <td key={p.name}>{String(rec.parameters[p.name] ?? "n/a")}</td>)}
                          <td>{rec.exitCode === null ? "n/a" : String(rec.exitCode)}</td>
                          <td>{rec.keff === null ? "n/a" : rec.keff.toFixed(6)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>}
            <div style={s.hint}>运行目录：{run.baseDir}（每个组合一个 run_XXX 子目录，MCNP 输出为 sweep-001.o / sweep-001.r …，与组合号对应）</div>
          </div>
        ) : null}

        <div style={s.hint}>
          用法：框选要变的数字 → 「设为扫描参数」→ 填多个取值（空格分隔）→ 选并行路数 → 开始扫描。
          多参数会做组合（如 NPS 3 个值 × keff 2 个值 = 6 组）。每个组合都从基准 INP 重新替换，互不影响。
        </div>
        {err ? <div style={s.err}>{err}</div> : null}
      </div>
    </FloatingDialog>
  );
}
