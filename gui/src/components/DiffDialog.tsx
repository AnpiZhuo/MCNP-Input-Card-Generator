/**
 * INP 对比：当前工作区生成文本 vs 磁盘文件（或手动粘贴）。
 * diff 计算走后端 /api/diff-inp（Python difflib），前端只做行着色渲染。
 */
import React, { useEffect, useMemo, useState } from "react";
import FloatingDialog from "./FloatingDialog";
import { apiUrl, errorHint } from "../utils/api";
import { generateInp } from "../utils/dataCollector";
import { useDeck } from "../utils/DeckContext";
import { parseDiffLines, type DiffLineType } from "../utils/diffRender";

const LINE_COLOR: Record<DiffLineType, string> = {
  header: "#7dd3fc",
  add: "#86efac",
  del: "#fca5a5",
  ctx: "var(--text-secondary, #cbd5e1)",
};

const LINE_BG: Record<DiffLineType, string> = {
  header: "rgba(125,211,252,0.08)",
  add: "rgba(134,239,172,0.10)",
  del: "rgba(252,165,165,0.10)",
  ctx: "transparent",
};

export default function DiffDialog({ onClose }: { onClose: () => void }) {
  const { deck } = useDeck();
  const [textA, setTextA] = useState("");
  const [textB, setTextB] = useState("");
  const [diff, setDiff] = useState("");
  const [stats, setStats] = useState<{ added: number; removed: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const genA = async () => {
    setErr("");
    try {
      setTextA(await generateInp(deck));
    } catch (e: any) {
      setErr(errorHint(e, "生成当前工作区 INP 失败"));
    }
  };
  useEffect(() => { genA(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const loadB = async () => {
    setErr("");
    try {
      const r = await fetch(apiUrl("/api/choose-file"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      const j = await r.json();
      if (j.status !== "ok") throw new Error(j.message);
      if (j.cancelled || j.content == null) return;
      setTextB(j.content);
    } catch (e: any) {
      setErr(errorHint(e, "读取文件失败"));
    }
  };

  const doDiff = async () => {
    setErr("");
    setBusy(true);
    try {
      const r = await fetch(apiUrl("/api/diff-inp"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text_a: textA, text_b: textB }),
        signal: AbortSignal.timeout(20000),
      });
      const j = await r.json();
      if (j.status === "error") throw new Error(j.message);
      setDiff(j.diff || "");
      setStats(j.stats || { added: 0, removed: 0 });
    } catch (e: any) {
      setErr(errorHint(e, "对比失败"));
    } finally {
      setBusy(false);
    }
  };

  const lines = useMemo(() => parseDiffLines(diff), [diff]);

  return (
    <FloatingDialog
      title="INP 对比"
      onClose={onClose}
      width={860}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>关闭</button>
          <button className="btn btn-primary btn-sm" onClick={doDiff} disabled={busy}>
            {busy ? "对比中…" : "对比"}
          </button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12 }}>
        <div style={{ display: "flex", gap: 12 }}>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 10, color: "var(--text-tertiary)", fontWeight: 600 }}>
              A · 当前工作区
              <button className="btn btn-ghost btn-xs" style={{ marginLeft: 8 }} onClick={genA}>重新生成</button>
            </label>
            <textarea
              value={textA}
              onChange={(e) => setTextA(e.target.value)}
              spellCheck={false}
              style={{ height: 180, fontFamily: "Consolas,monospace", fontSize: 11, background: "var(--bg-input)", color: "var(--text-primary)", border: "1px solid var(--border-glass)", borderRadius: 6, padding: 8, resize: "vertical" }}
            />
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 10, color: "var(--text-tertiary)", fontWeight: 600 }}>
              B · 对比对象
              <button className="btn btn-ghost btn-xs" style={{ marginLeft: 8 }} onClick={loadB}>从文件加载</button>
            </label>
            <textarea
              value={textB}
              onChange={(e) => setTextB(e.target.value)}
              placeholder={"粘贴文本，或点「从文件加载」选择 .i 文件"}
              spellCheck={false}
              style={{ height: 180, fontFamily: "Consolas,monospace", fontSize: 11, background: "var(--bg-input)", color: "var(--text-primary)", border: "1px solid var(--border-glass)", borderRadius: 6, padding: 8, resize: "vertical" }}
            />
          </div>
        </div>

        {stats && (
          <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
            {stats.added + stats.removed === 0
              ? "✅ 两段文本无差异"
              : `新增 ${stats.added} 行 / 删除 ${stats.removed} 行`}
          </div>
        )}
        {err && <div style={{ color: "#e53935", fontSize: 12 }}>{err}</div>}

        {diff && (
          <div style={{ maxHeight: 300, overflow: "auto", border: "1px solid var(--border-glass)", borderRadius: 6 }}>
            <pre style={{ margin: 0, padding: 8, fontFamily: "Consolas,monospace", fontSize: 11, lineHeight: 1.6 }}>
              {lines.map((l, i) => (
                <div key={i} style={{ color: LINE_COLOR[l.type], background: LINE_BG[l.type], whiteSpace: "pre" }}>
                  {l.text || " "}
                </div>
              ))}
            </pre>
          </div>
        )}
      </div>
    </FloatingDialog>
  );
}
