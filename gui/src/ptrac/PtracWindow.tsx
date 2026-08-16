/**
 * PtracWindow — 独立「3D 径迹」（PTRAC）窗口宿主（契约 ptrac-visualization.md §4）
 *
 * 照 ResultWindow 范式：读桥（readPtracData）→ /api/ptrac-parse → 几何外壳 + 每条历史
 * 一条 LineSegments 径迹（顶点色 = 粒子类型三色 × 能量深浅）+ 归一化 offset + OrbitControls。
 *
 * 右 300px 面板：标题/关闭、统计行、粒子类型三勾选、能量深浅图例、径迹透明度滑杆、
 * 密度抽样滑杆（1/1…1/10000）、单径迹高亮（NPS 输入）、外壳开关、关闭按钮。
 */
import React, { useEffect, useRef, useState } from "react";
import { readPtracData, closeCurrentWindow } from "../utils/windows";
import { ptracParse, errorHint, type PtracParseResult, type PtracTrack } from "../utils/api";
import { getMatColor } from "../utils/materialColors";
import { DEFAULT_SHELL_OPACITY } from "../three/cellMaterial";
import { createPtracRenderer, type PtracRendererHandle } from "./PtracRenderer";
import { sampleTracks } from "./decimateTracks";
import { TRACK_LEGEND, energyRangeOfTracks } from "./trackColors";

interface BridgeData {
  stlData: Record<string, string>;
  cells: { num: string; mat: string; comment?: string }[];
  ptracPath: string;
  maxTracks: number;
  maxPoints: number;
}

const SAMPLE_STEPS = [1, 10, 100, 1000, 10000];
const SAMPLE_LABELS = ["1/1", "1/10", "1/100", "1/1000", "1/10000"];

export default function PtracWindow() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<PtracRendererHandle | null>(null);
  const [data] = useState<BridgeData | null>(() => readPtracData() as BridgeData | null);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<PtracParseResult["stats"] | null>(null);
  const [header, setHeader] = useState<PtracParseResult["header"] | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [trackCount, setTrackCount] = useState(0);
  const [energyRange, setEnergyRange] = useState({ min: 0, max: 1 });
  const [shellVisible, setShellVisible] = useState(true);
  const [shellOpacity, setShellOpacity] = useState(DEFAULT_SHELL_OPACITY);
  const [trackOpacity, setTrackOpacity] = useState(1);
  const [visibleParticles, setVisibleParticles] = useState({ n: true, p: true, e: true });
  const [sampleIdx, setSampleIdx] = useState(0);
  const [highlightNps, setHighlightNps] = useState("");

  const tracksRef = useRef<PtracTrack[]>([]);

  // 首帧：读桥 → 初始化渲染器 → /api/ptrac-parse → 填径迹
  useEffect(() => {
    if (!data || !canvasRef.current) return;
    let disposed = false;
    const cellViews = (data.cells || []).map((c) => ({
      num: String(c.num),
      mat: c.mat,
      comment: c.comment || "",
      color: getMatColor(c.mat),
    }));
    const renderer = createPtracRenderer(canvasRef.current!, {
      stlData: data.stlData || {},
      cellViews,
      onError: (m) => setError(m),
    });
    rendererRef.current = renderer;
    (async () => {
      try {
        const res = await ptracParse(data.ptracPath, data.maxTracks, data.maxPoints);
        if (disposed) return;
        if (res.status === "error" || !res.tracks) throw new Error(errorHint(res));
        const tracks = res.tracks || [];
        tracksRef.current = tracks;
        setTrackCount(tracks.length);
        setStats(res.stats || null);
        setHeader(res.header || null);
        setTruncated(!!res.truncated);
        setEnergyRange(energyRangeOfTracks(tracks));
        renderer.setTracks(tracks); // 初始 1/1（全量）
      } catch (e: any) {
        if (!disposed) setError(errorHint(e, "解析 PTRAC 文件失败"));
      }
    })();
    return () => {
      disposed = true;
      renderer.dispose();
      rendererRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 密度抽样变化 → 重建径迹
  useEffect(() => {
    if (tracksRef.current.length === 0) return;
    rendererRef.current?.setTracks(sampleTracks(tracksRef.current, SAMPLE_STEPS[sampleIdx]));
  }, [sampleIdx]);

  // 粒子类型显隐
  useEffect(() => {
    const r = rendererRef.current;
    if (!r) return;
    r.setParticleVisible("n", visibleParticles.n);
    r.setParticleVisible("p", visibleParticles.p);
    r.setParticleVisible("e", visibleParticles.e);
  }, [visibleParticles]);

  // 单径迹高亮（NPS 输入，空=全部）
  useEffect(() => {
    const v = highlightNps.trim();
    const n = v && /^\d+$/.test(v) ? parseInt(v, 10) : null;
    rendererRef.current?.setHighlight(n);
  }, [highlightNps]);

  useEffect(() => { rendererRef.current?.setTrackOpacity(trackOpacity); }, [trackOpacity]);
  useEffect(() => { rendererRef.current?.setShellOpacity(shellOpacity); }, [shellOpacity]);
  useEffect(() => { rendererRef.current?.setShellVisible(shellVisible); }, [shellVisible]);

  const containerStyle: React.CSSProperties = {
    position: "absolute", inset: 0, display: "flex", background: "#0a0a1e", color: "#fff", overflow: "hidden",
  };

  if (!data) {
    return React.createElement("div", { style: containerStyle },
      React.createElement("div", { style: { margin: "auto", fontSize: 14, color: "#888" } },
        "没有 3D 径迹数据（请从主窗口「输出」标签页解析 PTRAC 后打开）"),
    );
  }

  const displayedCount = sampleTracks(tracksRef.current, SAMPLE_STEPS[sampleIdx]).length;

  return (
    <div style={containerStyle}>
      <div style={{ flex: 1, display: "flex", position: "relative", minWidth: 0 }}>
        <canvas ref={canvasRef} style={{ flex: 1, display: "block", minWidth: 0 }} />
        {error && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.7)", color: "#e53935", fontSize: 13, padding: 20, textAlign: "center" }}>
            {error}
          </div>
        )}
      </div>
      <div style={{ width: 300, borderLeft: "1px solid rgba(255,255,255,0.08)", background: "rgba(10,10,30,0.6)", display: "flex", flexDirection: "column", flexShrink: 0, overflow: "hidden" }}>
        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(241,241,249,0.85)" }}>🧭 3D 径迹 — PTRAC</span>
          <button className="btn btn-ghost btn-xs" onClick={() => { closeCurrentWindow(); }} style={{ fontSize: 16, padding: "4px 10px" }}>✕</button>
        </div>

        {/* 统计行 */}
        <div style={{ padding: "8px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11, lineHeight: 1.7, color: "var(--text-secondary)" }}>
          <div style={{ color: "var(--text-tertiary)", marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {header?.title ? `「${header.title}」` : "PTRAC 径迹"}
          </div>
          {stats ? (
            <div>
              径迹（粒子）{trackCount} 条 · 事件 {stats.events} · 点 {stats.points}
              {truncated && <span style={{ color: "#ff9800" }}> · ⚠ 已截断</span>}
            </div>
          ) : (
            <div style={{ color: "var(--text-tertiary)" }}>解析中…</div>
          )}
          <div style={{ color: "var(--text-tertiary)" }}>显示 {displayedCount}/{trackCount} 条径迹</div>
          {trackCount === 0 && stats && (
            <div style={{ marginTop: 4, padding: "6px 8px", background: "rgba(255,152,0,0.12)", borderRadius: 6, color: "#ff9800", lineHeight: 1.5 }}>
              ⚠ 该 PTRAC 文件没有径迹（0 个事件）。通常是 PTRAC 卡的 TYPE 与问题 MODE 不匹配（如 MODE P 却写 TYPE=E/N），或 WRITE/MAX 过滤太严。检查输入卡后重新运行 MCNP。
            </div>
          )}
          {trackCount > 0 && tracksRef.current.every((t) => (t.points?.length || 0) < 2) && (
            <div style={{ marginTop: 4, padding: "6px 8px", background: "rgba(255,152,0,0.12)", borderRadius: 6, color: "#ff9800", lineHeight: 1.5 }}>
              ⚠ 每条径迹仅 1 个点，无法连线（可能 PTRAC 卡过滤过严：TYPE 与 MODE 冲突、MAX 过小或运行在 nps=1 提前终止）。检查输入卡后重新运行 MCNP。
            </div>
          )}
          {trackCount > 0 && stats && stats.events > trackCount * 2 && (
            <div style={{ marginTop: 4, padding: "6px 8px", background: "rgba(255,152,0,0.12)", borderRadius: 6, color: "#ff9800", lineHeight: 1.5 }}>
              ⚠ 事件数（{stats.events}）远大于径迹数（{trackCount}）：这是 WRITE=ALL 的正常现象——每个粒子的每次碰撞都记 1 个事件，所以“事件数”≠“粒子数”。本文件只有 {trackCount} 个粒子。想看全部粒子，请在 PTRAC 卡改用 WRITE=SOURCE（每粒子 1 点）。
            </div>
          )}
        </div>

        {/* 粒子类型三勾选 */}
        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>粒子类型</div>
          {TRACK_LEGEND.map((l) => (
            <label key={l.key} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={visibleParticles[l.key]}
                onChange={(e) => setVisibleParticles((prev) => ({ ...prev, [l.key]: e.target.checked }))}
                style={{ accentColor: l.color }}
              />
              <span style={{ width: 10, height: 10, borderRadius: 2, background: l.color, display: "inline-block", flexShrink: 0 }} />
              <span style={{ color: "var(--text-secondary)" }}>{l.label}</span>
            </label>
          ))}
        </div>

        {/* 能量深浅图例 */}
        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>能量深浅</div>
          <div style={{ height: 10, borderRadius: 4, background: "linear-gradient(to right, #f1f5f9, #334155)" }} />
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-tertiary)", fontSize: 10, marginTop: 3 }}>
            <span>低能（浅）</span>
            <span>{energyRange.min === energyRange.max ? "无能量" : `${fmt(energyRange.min)} → ${fmt(energyRange.max)} MeV`}</span>
            <span>高能（深）</span>
          </div>
        </div>

        {/* 径迹透明度滑杆 */}
        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)", marginBottom: 4 }}>
            <span>径迹透明度</span>
            <span style={{ color: "var(--text-tertiary)" }}>{Math.round(trackOpacity * 100)}%</span>
          </div>
          <input type="range" min={0} max={1} step={0.01} value={trackOpacity}
            onChange={(e) => setTrackOpacity(parseFloat(e.target.value))} style={{ width: "100%" }} />
        </div>

        {/* 密度抽样滑杆 */}
        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)", marginBottom: 4 }}>
            <span>密度抽样</span>
            <span style={{ color: "var(--text-tertiary)" }}>{SAMPLE_LABELS[sampleIdx]}</span>
          </div>
          <input type="range" min={0} max={SAMPLE_STEPS.length - 1} step={1} value={sampleIdx}
            onChange={(e) => setSampleIdx(parseInt(e.target.value, 10))} style={{ width: "100%" }} />
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-tertiary)", fontSize: 10, marginTop: 2 }}>
            <span>密</span><span>疏</span>
          </div>
        </div>

        {/* 单径迹高亮 */}
        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>单径迹高亮</div>
          <input
            className="form-input"
            type="text"
            inputMode="numeric"
            value={highlightNps}
            onChange={(e) => setHighlightNps(e.target.value)}
            placeholder="NPS 编号（空 = 全部）"
            style={{ width: "100%", height: 26, fontSize: 11 }}
          />
        </div>

        {/* 外壳开关 */}
        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <input type="checkbox" checked={shellVisible} onChange={(e) => setShellVisible(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
            <span style={{ color: "var(--text-secondary)" }}>显示几何外壳</span>
          </label>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-tertiary)", marginTop: 6 }}>
            <span>外壳透明度</span>
            <span>{Math.round(shellOpacity * 100)}%</span>
          </div>
          <input type="range" min={0} max={1} step={0.01} value={shellOpacity}
            onChange={(e) => setShellOpacity(parseFloat(e.target.value))} style={{ width: "100%" }} />
        </div>

        <div style={{ padding: "10px 14px", borderTop: "1px solid rgba(255,255,255,0.06)", display: "flex", justifyContent: "flex-end" }}>
          <button className="btn btn-primary btn-xs" onClick={() => { closeCurrentWindow(); }}>关闭</button>
        </div>
      </div>
    </div>
  );
}

function fmt(v: number): string {
  if (!Number.isFinite(v)) return "-";
  if (v === 0) return "0";
  if (Math.abs(v) >= 1000 || Math.abs(v) < 0.001) return v.toExponential(1);
  return String(Math.round(v * 1000) / 1000);
}
