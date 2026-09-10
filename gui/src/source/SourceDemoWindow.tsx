/**
 * SourceDemoWindow — 独立「演示源」窗口宿主（契约 source-demo-visualization.md §5）
 *
 * 照 PtracWindow 范式：读桥（readSourceDemoData）→ fetchPreview3dStl 外壳 →
 * createSourceDemoRenderer → setParticles（桥里已由主窗口抽样）。右 300px 面板：
 * 标题「🎬 演示源」、统计、能量深浅图例、粒子透明度、方向线长度、外壳开关、
 * 重新抽样按钮、关闭。
 */
import React, { useEffect, useRef, useState } from "react";
import { readSourceDemoData, closeCurrentWindow } from "../utils/windows";
import { fetchPreview3dStl, sourceDemoSample, type SourceParticle } from "../utils/api";
import { getMatColor } from "../utils/materialColors";
import { DEFAULT_SHELL_OPACITY } from "../three/cellMaterial";
import { createSourceDemoRenderer, type SourceDemoRendererHandle } from "./SourceDemoRenderer";
import { TRACK_LEGEND, TRACK_PARTICLE_LABELS, TRACK_COLORS } from "../ptrac/trackColors";

interface BridgeData {
  cells: { num: string; mat: string; comment?: string }[];
  surfaces: string;
  trCards: string;
  materials: { number: number; comment?: string }[];
  particles: SourceParticle[];
  energyRange: { min: number; max: number };
  sdefFields: Record<string, string>;
  sdefDistributions: any[];
}

export default function SourceDemoWindow() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<SourceDemoRendererHandle | null>(null);
  const [data] = useState<BridgeData | null>(() => readSourceDemoData() as BridgeData | null);
  const [error, setError] = useState("");
  const [count, setCount] = useState(0);
  const [energyRange, setEnergyRange] = useState({ min: 0, max: 1 });
  const [shellVisible, setShellVisible] = useState(true);
  const [shellOpacity, setShellOpacity] = useState(DEFAULT_SHELL_OPACITY);
  const [particleOpacity, setParticleOpacity] = useState(1);
  const [dirScale, setDirScale] = useState(1);
  const [sampling, setSampling] = useState(false);

  const dataRef = useRef<BridgeData | null>(null);

  // 首帧：读桥 → 外壳 → 渲染器 → 填粒子
  useEffect(() => {
    if (!data || !canvasRef.current) return;
    dataRef.current = data;
    let disposed = false;
    const cellViews = (data.cells || []).map((c) => ({
      num: String(c.num), mat: c.mat, comment: c.comment || "", color: getMatColor(c.mat),
    }));
    const renderer = createSourceDemoRenderer(canvasRef.current!, {
      stlData: {},
      cellViews,
      onError: (m) => setError(m),
    });
    rendererRef.current = renderer;
    setCount((data.particles || []).length);
    setEnergyRange(data.energyRange || { min: 0, max: 1 });
    (async () => {
      try {
        const stl = await fetchPreview3dStl(data.cells || [], data.surfaces, data.trCards);
        if (disposed) return;
        // 外壳到达后重建渲染器（stlData 固定）——或直接 setParticles 由 renderer 补外壳
        renderer.dispose();
        const renderer2 = createSourceDemoRenderer(canvasRef.current!, {
          stlData: stl || {},
          cellViews,
          onError: (m) => setError(m),
        });
        rendererRef.current = renderer2;
        renderer2.setParticles(data.particles || [], data.energyRange || { min: 0, max: 1 });
      } catch (e: any) {
        if (!disposed) setError(String(e?.message || e));
      }
    })();
    return () => {
      disposed = true;
      rendererRef.current?.dispose();
      rendererRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resample = async () => {
    const d = dataRef.current;
    if (!d || sampling) return;
    setSampling(true);
    setError("");
    try {
      const res = await sourceDemoSample({
        sdefFields: d.sdefFields,
        sdefDistributions: d.sdefDistributions,
        surfaces: d.surfaces,
        cells: d.cells,
        trCards: d.trCards,
        nParticles: 500,
      });
      if (res.status === "error" || !res.particles) {
        setError(res.error || "抽样失败");
      } else {
        setCount(res.particles.length);
        setEnergyRange(res.energyRange || { min: 0, max: 1 });
        rendererRef.current?.setParticles(res.particles, res.energyRange || { min: 0, max: 1 });
      }
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setSampling(false);
    }
  };

  useEffect(() => { rendererRef.current?.setShellVisible(shellVisible); }, [shellVisible]);
  useEffect(() => { rendererRef.current?.setShellOpacity(shellOpacity); }, [shellOpacity]);
  useEffect(() => { rendererRef.current?.setParticleOpacity(particleOpacity); }, [particleOpacity]);
  useEffect(() => { rendererRef.current?.setDirectionLength(dirScale); }, [dirScale]);

  const containerStyle: React.CSSProperties = {
    position: "absolute", inset: 0, display: "flex", background: "#0a0a1e", color: "#fff", overflow: "hidden",
  };

  if (!data) {
    return React.createElement("div", { style: containerStyle },
      React.createElement("div", { style: { margin: "auto", fontSize: 14, color: "#888" } },
        "没有演示源数据（请从主窗口「源」标签页点「演示源」打开）"),
    );
  }

  const particleCounts: Record<string, number> = {};
  for (const p of data.particles || []) {
    particleCounts[p.particle] = (particleCounts[p.particle] || 0) + 1;
  }

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
          <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(241,241,249,0.85)" }}>🎬 演示源 — SDEF</span>
          <button className="btn btn-ghost btn-xs" onClick={() => { closeCurrentWindow(); }} style={{ fontSize: 16, padding: "4px 10px" }}>✕</button>
        </div>

        <div style={{ padding: "8px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11, lineHeight: 1.7, color: "var(--text-secondary)" }}>
          <div style={{ color: "var(--text-tertiary)" }}>粒子 {count} 个 · 只表从哪发出/往哪飞</div>
          <div style={{ display: "flex", gap: 10, marginTop: 3, flexWrap: "wrap" }}>
            {TRACK_LEGEND.map((l) => (
              <span key={l.key} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: l.color, display: "inline-block", flexShrink: 0 }} />
                <span style={{ color: "var(--text-secondary)" }}>{l.label} {particleCounts[l.key] || 0}</span>
              </span>
            ))}
          </div>
        </div>

        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>能量深浅</div>
          <div style={{ height: 10, borderRadius: 4, background: "linear-gradient(to right, #f1f5f9, #334155)" }} />
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-tertiary)", fontSize: 10, marginTop: 3 }}>
            <span>低能（浅）</span>
            <span>{energyRange.min === energyRange.max ? "无能量" : `${fmt(energyRange.min)} → ${fmt(energyRange.max)} MeV`}</span>
            <span>高能（深）</span>
          </div>
        </div>

        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)", marginBottom: 4 }}>
            <span>粒子透明度</span>
            <span style={{ color: "var(--text-tertiary)" }}>{Math.round(particleOpacity * 100)}%</span>
          </div>
          <input type="range" min={0} max={1} step={0.01} value={particleOpacity}
            onChange={(e) => setParticleOpacity(parseFloat(e.target.value))} style={{ width: "100%" }} />
        </div>

        <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11 }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)", marginBottom: 4 }}>
            <span>方向线长度</span>
            <span style={{ color: "var(--text-tertiary)" }}>{Math.round(dirScale * 100)}%</span>
          </div>
          <input type="range" min={0.2} max={5} step={0.1} value={dirScale}
            onChange={(e) => setDirScale(parseFloat(e.target.value))} style={{ width: "100%" }} />
        </div>

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

        <div style={{ padding: "10px 14px", borderTop: "1px solid rgba(255,255,255,0.06)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn btn-ghost btn-xs" onClick={resample} disabled={sampling}>
            {sampling ? "抽样中…" : "↻ 重新抽样"}
          </button>
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
