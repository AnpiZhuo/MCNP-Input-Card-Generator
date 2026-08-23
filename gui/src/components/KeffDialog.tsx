/**
 * 主动解析 keff：输入 mctal 文件路径或运行目录 → /api/parse-keff →
 * 显示最终 keff（combined 优先）+ 逐周期收敛曲线（Recharts）。
 */
import React, { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import FloatingDialog from "./FloatingDialog";
import { apiUrl, errorHint } from "../utils/api";
import { convergencePoints } from "../utils/sweepDashboard";

interface KeffResult {
  cycles: number[];
  mean: number[];
  std: number[];
  combined: { mean: number; std: number } | null;
}

export default function KeffDialog({ onClose }: { onClose: () => void }) {
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [keff, setKeff] = useState<KeffResult | null>(null);

  const browse = async () => {
    setErr("");
    try {
      const r = await fetch(apiUrl("/api/choose-file"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      const j = await r.json();
      if (j.status !== "ok") throw new Error(j.message);
      if (j.cancelled || !j.path) return;
      setPath(j.path);
      setKeff(null);
    } catch (e: any) {
      setErr(errorHint(e, "选择文件失败"));
    }
  };

  const doParse = async () => {
    setErr("");
    if (!path.trim()) { setErr("请先输入 mctal 路径或运行目录，或点「浏览」选择"); return; }
    setBusy(true);
    setKeff(null);
    try {
      const r = await fetch(apiUrl("/api/parse-keff"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path.trim() }),
        signal: AbortSignal.timeout(30000),
      });
      const j = await r.json();
      if (j.status === "error") throw new Error(j.message);
      setKeff(j.keff);
    } catch (e: any) {
      setErr(errorHint(e, "keff 解析失败"));
    } finally {
      setBusy(false);
    }
  };

  const points = useMemo(
    () => (keff ? convergencePoints({ cycles: keff.cycles, mean: keff.mean, std: keff.std }) : []),
    [keff],
  );

  const finalKeff = keff?.combined?.mean ?? (keff && keff.mean.length ? keff.mean[keff.mean.length - 1] : null);
  const finalStd = keff?.combined?.std ?? (keff && keff.std.length ? keff.std[keff.std.length - 1] : null);

  return (
    <FloatingDialog
      title="主动解析 keff（mctal 收敛）"
      onClose={onClose}
      width={680}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>关闭</button>
          <button className="btn btn-primary btn-sm" onClick={doParse} disabled={busy}>
            {busy ? "解析中…" : "解析 keff"}
          </button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="form-input"
            style={{ flex: 1, fontFamily: "Consolas,monospace", fontSize: 11 }}
            value={path}
            onChange={(e) => { setPath(e.target.value); setKeff(null); }}
            placeholder="mctal 文件路径，或含 mctal 的运行目录（自动找 mctal*）"
          />
          <button className="btn btn-ghost btn-sm" onClick={browse}>浏览</button>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)", lineHeight: 1.5 }}>
          MCNP 临界计算的 mctal 文件通常无扩展名（如 run 目录下的 mctal / mctal_xxx），选目录也行。
        </div>
        {err && <div style={{ color: "#e53935", fontSize: 12 }}>{err}</div>}

        {keff && (
          <>
            <div style={{ display: "flex", gap: 16, alignItems: "baseline" }}>
              <div>
                <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>最终 k-eff</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "var(--accent-glow, #38bdf8)" }}>
                  {finalKeff === null ? "n/a" : finalKeff.toFixed(5)}
                  {finalStd !== null && (
                    <span style={{ fontSize: 12, fontWeight: 400, color: "var(--text-tertiary)", marginLeft: 6 }}>
                      ± {finalStd.toFixed(5)}
                    </span>
                  )}
                </div>
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                周期数：{keff.cycles.length}（{keff.combined ? "combined keff" : "末周期均值"}）
              </div>
            </div>
            <LineChart width={640} height={240} data={points} margin={{ top: 8, right: 20, bottom: 4, left: 4 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
              <XAxis dataKey="cycle" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: "var(--text-tertiary, #94a3b8)" }} label={{ value: "cycle", position: "insideBottomRight", offset: -2, style: { fontSize: 10, fill: "var(--text-tertiary, #94a3b8)" } }} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "var(--text-tertiary, #94a3b8)" }} width={56} />
              <Tooltip
                contentStyle={{ background: "var(--bg-input, #121a2e)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, fontSize: 12, color: "var(--text-primary, #e2e8f0)" }}
              />
              <ReferenceLine y={1} stroke="#f87171" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="mean" stroke="#38bdf8" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </>
        )}
      </div>
    </FloatingDialog>
  );
}
