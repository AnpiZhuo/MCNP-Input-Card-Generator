/**
 * ResultWindow — 独立「3D 结果」（体积可视化）窗口宿主（契约 meshtal-visualization.md §4.7 / §14）
 *
 * 照 Preview3DWindow 范式：读 localStorage 桥（readVolumeData）→ 渲染几何外壳 + 体积层。
 *
 * 生命周期（§14 铁律 3）：**关闭只 `close_window`，不调 `clearStlSession()`**——
 * STL 会话由主窗口 3D 预览生命周期管理，体积窗口关闭不清 preview-3d 的 STL 会话。
 *
 * 首帧：读桥 → meshtal-texture 取当前帧 → createVolumeRenderer → 后续帧 texSubImage3D 复用。
 */
import React, { useEffect, useRef, useState } from "react";
import { readVolumeData, closeCurrentWindow } from "../utils/windows";
import { meshtalTexture, errorHint, type MeshtalTextureFrame } from "../utils/api";
import { getMatColor } from "../utils/materialColors";
import { CellList } from "../components/MaterialPanel";
import { createVolumeRenderer, type VolumeRendererHandle, type VolumeFrame } from "./VolumeRenderer";
import VolumeControlPanel from "./VolumeControlPanel";

interface BridgeData {
  stlData: Record<string, string>;
  cells: { num: string; mat: string; comment?: string }[];
  meshtal: { path: string; tallyNumber: number; resolution: number; particle: string; geom: string };
  energyOptions: { index: number; label: string }[];
  timeOptions: { index: number; label: string }[];
  worldBox: { min: [number, number, number]; max: [number, number, number] } | null;
  scalarRange: { min: number; max: number };
  match: { matched: boolean; overlapFraction: number; centerOffsetFrac: number; reason: string; message: string } | null;
}

export default function ResultWindow() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<VolumeRendererHandle | null>(null);
  const [data] = useState<BridgeData | null>(() => readVolumeData() as BridgeData | null);
  const [error, setError] = useState("");
  const [opacity, setOpacity] = useState(1);
  const [shellVisible, setShellVisible] = useState(true);
  const [seeThrough, setSeeThrough] = useState(false);
  const [energyIndex, setEnergyIndex] = useState(0);
  const [timeIndex, setTimeIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [colorRange, setColorRange] = useState(() =>
    data ? { min: data.scalarRange?.min ?? 0, max: data.scalarRange?.max ?? 1 } : { min: 0, max: 1 },
  );
  const dataRef = useRef(data);
  dataRef.current = data;
  const energyIndexRef = useRef(0);
  energyIndexRef.current = energyIndex;
  const timeIndexRef = useRef(0);
  timeIndexRef.current = timeIndex;

  /** 取 (energy,time) 帧 → VolumeFrame（异常带 hint） */
  const fetchTexture = async (energyBin: number, timeIdx: number): Promise<VolumeFrame> => {
    const d = dataRef.current!;
    const res = await meshtalTexture({
      path: d.meshtal.path,
      tallyNumber: d.meshtal.tallyNumber,
      energyBin,
      timeBin: timeIdx,
      resolution: d.meshtal.resolution,
    });
    if (res.status === "error" || !res.frame) throw new Error(errorHint(res));
    return {
      resolution: res.frame.resolution,
      worldBox: res.frame.worldBox,
      dataBase64: res.frame.dataBase64,
      scalarRange: res.frame.scalarRange,
    };
  };

  /** 取帧并复用上传当前帧（texSubImage3D） */
  const loadFrame = async (energyBin: number, timeIdx: number) => {
    const r = rendererRef.current;
    if (!r) return;
    try {
      r.setFrame(await fetchTexture(energyBin, timeIdx));
    } catch (e: any) {
      setError(errorHint(e, "切换体积帧失败"));
    }
  };

  // 首帧：读桥 → meshtal-texture → createVolumeRenderer
  useEffect(() => {
    if (!data || !canvasRef.current) return;
    let disposed = false;
    const d = data;
    (async () => {
      try {
        const frame = await fetchTexture(0, 0);
        if (disposed) return;
        const cellViews = d.cells.map((c) => ({
          num: String(c.num),
          mat: c.mat,
          comment: c.comment || "",
          visible: c.mat !== "0",
          color: getMatColor(c.mat),
        }));
        rendererRef.current = createVolumeRenderer(canvasRef.current!, {
          stlData: d.stlData || {},
          cellViews,
          frame,
          energyOptions: d.energyOptions || [],
          timeOptions: d.timeOptions || [],
          onTimeSeek: (idx: number) => {
            setTimeIndex(idx);
            loadFrame(energyIndexRef.current, idx);
          },
          onError: (msg) => setError(msg),
        });
      } catch (e: any) {
        if (!disposed) setError(errorHint(e, "获取体积帧失败"));
      }
    })();
    return () => {
      disposed = true;
      rendererRef.current?.dispose();
      rendererRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onPlayToggle = () => {
    if (playing) {
      rendererRef.current?.pause();
      setPlaying(false);
    } else {
      rendererRef.current?.play();
      setPlaying(true);
    }
  };
  const onSeek = (idx: number) => {
    setTimeIndex(idx);
    rendererRef.current?.seek(idx);
  };

  const onEnergyChange = (i: number) => {
    setEnergyIndex(i);
    loadFrame(i, timeIndexRef.current); // 能量区间切换 → 取新帧
  };

  const onShellVisibleChange = (v: boolean) => {
    setShellVisible(v);
    rendererRef.current?.setShellVisible(v);
  };
  const onSeeThroughChange = (v: boolean) => {
    setSeeThrough(v);
    rendererRef.current?.setTransparentMode(v ? "see-through" : "opaque");
  };
  const onOpacityChange = (v: number) => {
    setOpacity(v);
    rendererRef.current?.setOpacity(v);
  };
  const onColorRangeChange = (min: number, max: number) => {
    setColorRange({ min, max });
    rendererRef.current?.setColorizeRange({ min, max }, min);
  };

  const [cellVisible, setCellVisibleState] = useState<boolean[]>(() =>
    (data?.cells || []).map((c) => c.mat !== "0"),
  );
  const toggleCell = (i: number) => {
    const d = dataRef.current;
    if (!d || !rendererRef.current) return;
    if (d.cells[i]?.mat === "0") return;
    setCellVisibleState((prev) => {
      const next = prev.map((v, ci) => (ci === i ? !v : v));
      rendererRef.current?.setCellVisible(i, next[i]);
      return next;
    });
  };
  const setAll = (vis: boolean) => {
    rendererRef.current?.selectAll(vis);
    setCellVisibleState((prev) => prev.map(() => vis));
  };

  const containerStyle: React.CSSProperties = {
    position: "absolute", inset: 0, display: "flex", background: "#0a0a1e", color: "#fff", overflow: "hidden",
  };

  if (!data) {
    return React.createElement("div", { style: containerStyle },
      React.createElement("div", { style: { margin: "auto", fontSize: 14, color: "#888" } },
        "没有 3D 结果数据（请从主窗口「计数」标签页解析 MESHTAL 后打开）"),
    );
  }

  const cellRows = data.cells.map((c, i) => ({
    num: c.num, mat: c.mat, comment: c.comment,
    visible: cellVisible[i] ?? (c.mat !== "0"),
    locked: c.mat === "0",
  }));

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
          <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(241,241,249,0.85)" }}>🧊 3D 结果 — 网格计数体积</span>
          <button className="btn btn-ghost btn-xs" onClick={() => { closeCurrentWindow(); }} style={{ fontSize: 16, padding: "4px 10px" }}>✕</button>
        </div>

        {/* A1.2 不匹配横幅 */}
        {data.match && !data.match.matched && (
          <div style={{ fontSize: 11, padding: "8px 14px", background: "rgba(255,152,0,0.12)", color: "#ff9800", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
            ⚠ 网格数据与当前模型几何可能不匹配，可能显示错位
          </div>
        )}

        <VolumeControlPanel
          opacity={opacity}
          onOpacityChange={onOpacityChange}
          energyOptions={data.energyOptions || []}
          energyIndex={energyIndex}
          onEnergyChange={onEnergyChange}
          timeOptions={data.timeOptions || []}
          timeIndex={timeIndex}
          playing={playing}
          onPlayToggle={onPlayToggle}
          onSeek={onSeek}
          shellVisible={shellVisible}
          onShellVisibleChange={onShellVisibleChange}
          seeThrough={seeThrough}
          onSeeThroughChange={onSeeThroughChange}
          colorMin={colorRange.min}
          colorMax={colorRange.max}
          scalarMin={data.scalarRange?.min ?? 0}
          scalarMax={data.scalarRange?.max ?? 1}
          onColorRangeChange={onColorRangeChange}
        />

        <div style={{ padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,0.04)", display: "flex", gap: 6 }}>
          <button className="btn btn-ghost btn-xs" style={{ flex: 1, fontSize: 11 }} onClick={() => setAll(true)}>全部选中</button>
          <button className="btn btn-ghost btn-xs" style={{ flex: 1, fontSize: 11 }} onClick={() => setAll(false)}>全部取消</button>
        </div>
        <CellList rows={cellRows} onToggle={toggleCell} />
        <div style={{ padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>粒子 {data.meshtal.particle || "-"} · 网格 {data.meshtal.geom}</span>
          <button className="btn btn-primary btn-xs" onClick={() => { closeCurrentWindow(); }}>关闭</button>
        </div>
      </div>
    </div>
  );
}
