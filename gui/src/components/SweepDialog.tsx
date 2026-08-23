/**
 * 参数扫描弹窗：基于当前工作区 deck 生成 INP 文本，定义参数（正则组1=被替换值），
 * 调 /api/sweep-plan 规划（组合数+预览）与 /api/sweep-run 执行（逐组合跑 MCNP →
 * 提取 keff → 汇总 TSV）。
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

interface ParamRow { name: string; pattern: string; values: string; }
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

export default function SweepDialog({ onClose }: { onClose: () => void }) {
  const { deck } = useDeck();
  const [baseText, setBaseText] = useState("");
  const [genBusy, setGenBusy] = useState(false);
  const [params, setParams] = useState<ParamRow[]>([
    { name: "nps", pattern: "NPS\\s+(\\d+)", values: "1000 5000 10000" },
  ]);
  const [plan, setPlan] = useState<{ count: number; previews: string[] } | null>(null);
  const [run, setRun] = useState<RunResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [view, setView] = useState<"table" | "dash">("dash");
  // T3：doRun 进行中的 AbortController（供「取消」按钮中止请求；完成后/中止后置 null）
  const [runAbort, setRunAbort] = useState<AbortController | null>(null);

  const gen = async () => {
    setGenBusy(true); setErr("");
    try { setBaseText(await generateInp(deck)); }
    catch (e: any) { setErr(errorHint(e, "生成 INP 失败（请先检查表单）")); }
    finally { setGenBusy(false); }
  };
  useEffect(() => { gen(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const payload = useMemo(() => ({
    deck: baseText,
    parameters: params
      .map(p => ({ name: p.name.trim(), pattern: p.pattern, values: parseValues(p.values) }))
      .filter(p => p.name && p.pattern && p.values.length > 0),
  }), [baseText, params]);

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

  return React.createElement(FloatingDialog, {
    title: "参数扫描（批量改参数跑 MCNP）",
    onClose, width: 760,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "关闭"),
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: doPlan, disabled: busy || !baseText },
        busy ? "处理中…" : "规划预览"),
      // T3：取消按钮——扫描进行中点击 abort 请求，中止后清理状态
      runAbort ? React.createElement("button", { className: "btn btn-danger btn-sm", onClick: () => runAbort.abort(), disabled: !busy }, "取消") : null,
      React.createElement("button", { className: "btn btn-primary btn-sm", onClick: doRun, disabled: busy || !baseText || comboCount > 50 },
        busy ? "扫描中…" : `开始扫描（${comboCount} 组合）`),
    ),
  },
    React.createElement("div", { style: { fontSize: 12 } },
      // 基准 INP
      React.createElement("div", { style: { marginBottom: 10 } },
        React.createElement("label", { style: s.lbl }, "基准 INP（来自当前工作区表单，改动表单后点重新生成）"),
        React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center" } },
          React.createElement("input", { style: { ...s.inp, flex: 1, fontFamily: "Consolas,monospace" },
            value: genBusy ? "正在生成…" : (baseText ? `已生成（${baseText.length} 字符）` : "未生成"), readOnly: true }),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: gen, disabled: genBusy }, "重新生成"),
        ),
      ),
      // 参数编辑
      React.createElement("label", { style: s.lbl }, "参数（pattern 为正则，组 1 = 被替换的值；values 空格/逗号分隔）"),
      params.map((p, i) => React.createElement("div", { key: i, style: { display: "flex", gap: 6, marginBottom: 6, alignItems: "center" } },
        React.createElement("input", { style: { ...s.inp, width: 100 }, placeholder: "名称", value: p.name,
          onChange: e => setParams(ps => ps.map((x, j) => j === i ? { ...x, name: e.target.value } : x)) }),
        React.createElement("input", { style: { ...s.inp, flex: 1, fontFamily: "Consolas,monospace" }, placeholder: "NPS\\s+(\\d+)", value: p.pattern,
          onChange: e => setParams(ps => ps.map((x, j) => j === i ? { ...x, pattern: e.target.value } : x)) }),
        React.createElement("input", { style: { ...s.inp, flex: 1 }, placeholder: "1000 5000 10000", value: p.values,
          onChange: e => setParams(ps => ps.map((x, j) => j === i ? { ...x, values: e.target.value } : x)) }),
        React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setParams(ps => ps.filter((_, j) => j !== i)) }, "×"),
      )),
      React.createElement("div", { style: { display: "flex", gap: 8, marginBottom: 8 } },
        React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setParams(ps => [...ps, { name: "", pattern: "", values: "" }]) }, "+ 添加参数"),
        React.createElement("span", { style: { fontSize: 11, color: "var(--text-tertiary)", alignSelf: "center" } },
          `当前笛卡尔组合数：${comboCount}（后端上限 50）`),
      ),
      // 规划预览
      plan ? React.createElement("div", { style: { marginBottom: 10 } },
        React.createElement("label", { style: s.lbl }, `规划：${plan.count} 组合（前 3 组预览）`),
        plan.previews.map((t, i) => React.createElement("pre", { key: i, style: { background: "var(--bg-input)", padding: 8, borderRadius: 6, fontSize: 11, maxHeight: 90, overflow: "auto", margin: "4px 0" } }, t)),
      ) : null,
      // 结果
      run ? React.createElement("div", { style: { marginBottom: 8 } },
        React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center", marginBottom: 6 } },
          React.createElement("label", { style: { fontSize: 12, fontWeight: 600 } }, `执行结果（${run.records.length} 组合）`),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: downloadTsv }, "下载 TSV"),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setView("dash") }, "仪表盘"),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setView("table") }, "结果表"),
        ),
        view === "dash"
          ? React.createElement("div", { style: { maxHeight: 460, overflow: "auto" } },
              React.createElement(SweepDashboard, { records: run.records, parameters: payload.parameters }),
            )
          : React.createElement("div", { className: "table-wrap", style: { maxHeight: 240, overflow: "auto" } },
          React.createElement("table", null,
            React.createElement("thead", null, React.createElement("tr", null,
              React.createElement("th", null, "#"),
              payload.parameters.map(p => React.createElement("th", { key: p.name }, p.name)),
              React.createElement("th", null, "exit"),
              React.createElement("th", null, "keff"),
            )),
            React.createElement("tbody", null, run.records.map(rec =>
              React.createElement("tr", { key: rec.index },
                React.createElement("td", null, rec.index),
                payload.parameters.map(p => React.createElement("td", { key: p.name }, String(rec.parameters[p.name] ?? "n/a"))),
                React.createElement("td", null, rec.exitCode === null ? "n/a" : String(rec.exitCode)),
                React.createElement("td", null, rec.keff === null ? "n/a" : rec.keff.toFixed(6)),
              ),
            )),
          ),
        ),
        React.createElement("div", { style: s.hint }, `运行目录：${run.baseDir}（每个组合一个 run_XXX 子目录，含 sweep.i 与 MCNP 输出）`),
      ) : null,
      React.createElement("div", { style: s.hint },
        "示例：改 NPS → pattern `NPS\\s+(\\d+)`、values `1000 5000 10000`；改 KCODE 初始 keff → pattern `kcode \\d+ ([\\d.]+)`。" +
        "pattern 的正则组 1 会被替换为各取值，组 1 前后文本保留。"),
      err ? React.createElement("div", { style: s.err }, err) : null,
    ),
  );
}
