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
import React, { useEffect, useMemo, useRef, useState } from "react";
import { readVolumeData, closeCurrentWindow } from "../utils/windows";
import { meshtalTexture, errorHint, type MeshtalTextureFrame } from "../utils/api";
import { getMatColor } from "../utils/materialColors";
import { CellList } from "../components/MaterialPanel";
import {
  createVolumeRenderer,
  base64ToBytes,
  DEFAULT_VOLUME_OPACITY,
  type VolumeRendererHandle,
  type VolumeFrame,
} from "./VolumeRenderer";
import { DEFAULT_SHELL_OPACITY } from "../three/cellMaterial";
import { defaultDisplayMin, minPositiveOfBytes } from "./colorize";
import VolumeControlPanel from "./VolumeControlPanel";
import SliceExportPanel from "./SliceExportPanel";
import { ExportButton } from "../export/useFigureExport";
import { build3dSpec, subtitleOf, volumeColorbar } from "../export/figureSpecs";
import type { AABB } from "../export/planeSample";

interface BridgeData {
  stlData: Record<string, string>;
  cells: { num: string; mat: string; comment?: string }[];
  meshtal: { path: string; tallyNumber: number; resolution: number; particle: string; geom: string };
  energyOptions: { index: number; label: string }[];
  timeOptions: { index: number; label: string }[];
  worldBox: { min: [number, number, number]; max: [number, number, number] } | null;
  scalarRange: { min: number; max: number };
  match: { matched: boolean; overlapFraction: number; centerOffsetFrac: number; reason: string; message: string } | null;
  unit: string;
}

export default function ResultWindow() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<VolumeRendererHandle | null>(null);
  const [data] = useState<BridgeData | null>(() => readVolumeData() as BridgeData | null);
  const [error, setError] = useState("");
  // 双透明度滑杆：栅元透明度（外壳，默认半透明 0.4）+ 体积透明度（数据层，默认 1）
  const [shellOpacity, setShellOpacityState] = useState(DEFAULT_SHELL_OPACITY);
  const [volumeOpacity, setVolumeOpacityState] = useState(DEFAULT_VOLUME_OPACITY);
  const [shellVisible, setShellVisible] = useState(true);
  const [energyIndex, setEnergyIndex] = useState(0);
  const [timeIndex, setTimeIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [colorRange, setColorRange] = useState(() =>
    data ? {
      min: defaultDisplayMin(data.scalarRange ?? { min: 0, max: 1 }),
      max: data.scalarRange?.max ?? 1,
    } : { min: 0, max: 1 },
  );
  const dataRef = useRef(data);
  dataRef.current = data;
  const energyIndexRef = useRef(0);
  energyIndexRef.current = energyIndex;
  const timeIndexRef = useRef(0);
  timeIndexRef.current = timeIndex;
  // 当前 (energy,time) 帧标量（供切面/导出）
  const [currentFrame, setCurrentFrame] = useState<VolumeFrame | null>(null);

  /**
   * 网格世界坐标范围（自由平面取样用）。
   * 优先用 meshtal 解析出的 `worldBox`（真实网格边界）；没有就按下标当坐标兜底
   * —— 兜底时平面方程里的数值不是真实物理坐标，但方向/步长/等值线仍然可用，
   * 且界面会照常显示，不会静默切成空图。
   */
  const scalarBox = useMemo<AABB | null>(() => {
    const wb = data?.worldBox;
    if (wb && wb.min && wb.max) {
      return { min: [wb.min[0], wb.min[1], wb.min[2]], max: [wb.max[0], wb.max[1], wb.max[2]] };
    }
    const r = currentFrame?.resolution;
    if (r) return { min: [0, 0, 0], max: [Math.max(1, r[0] - 1), Math.max(1, r[1] - 1), Math.max(1, r[2] - 1)] };
    return null;
  }, [data, currentFrame]);

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
      const fr = await fetchTexture(energyBin, timeIdx);
      r.setFrame(fr);
      setCurrentFrame(fr);
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
        setCurrentFrame(frame);
        // 数量级自适应色阶下限：由帧数据最小正值推算（sqrt(minPositive*max)），
        // 隐去零通量背景；同步到色阶输入框，与渲染器实际阈值一致
        const mp = minPositiveOfBytes(base64ToBytes(frame.dataBase64), frame.scalarRange);
        const dm = defaultDisplayMin(frame.scalarRange, mp);
        setColorRange({ min: dm, max: frame.scalarRange.max });
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
          initialDisplayMin: dm,
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
  // 栅元透明度滑杆 → 外壳连续透明度（默认半透明）
  const onShellOpacityChange = (v: number) => {
    setShellOpacityState(v);
    rendererRef.current?.setShellOpacity(v);
  };
  // 体积透明度滑杆 → 体积数据层 uniform
  const onVolumeOpacityChange = (v: number) => {
    setVolumeOpacityState(v);
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

  /** 出图：3D 体积视图 + 材料图例 + 色阶（当前能量/时间帧与屏幕上一致；**透明底**） */
  const buildExport = () => {
    const canvas = rendererRef.current?.renderTransparentNow();
    const seen = new Set<string>();
    const legend: { color: string; label: string }[] = [];
    for (const c of data.cells) {
      if (seen.has(c.mat)) continue;
      seen.add(c.mat);
      legend.push({ color: getMatColor(c.mat), label: c.mat === "0" ? "M0 真空" : `M${c.mat}${c.comment ? " " + c.comment : ""}` });
    }
    const eLabel = data.energyOptions?.[energyIndex]?.label;
    const tLabel = data.timeOptions?.[timeIndex]?.label;
    return {
      view: "3D体积",
      nameParts: [`tally${data.meshtal.tallyNumber}`, data.meshtal.resolution, eLabel, tLabel],
      raster: canvas
        ? build3dSpec({
            canvas,
            title: "3D 网格计数体积",
            subtitle: subtitleOf([
              `tally ${data.meshtal.tallyNumber}`,
              `${data.meshtal.particle || "-"} / ${data.meshtal.geom}`,
              `分辨率 ${data.meshtal.resolution}³`,
              eLabel ? `能量 ${eLabel}` : undefined,
              tLabel ? `时间 ${tLabel}` : undefined,
            ]),
            legend,
            colorbar: volumeColorbar(colorRange.min, colorRange.max, data.unit || "归一化计数"),
            caption: "色阶下限为当前显示阈值；体积与几何外壳透明度与屏幕一致",
          })
        : undefined,
    };
  };

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
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <ExportButton build={buildExport} label="3D 体积图" />
            <button className="btn btn-ghost btn-xs" onClick={() => { closeCurrentWindow(); }} style={{ fontSize: 16, padding: "4px 10px" }}>✕</button>
          </div>
        </div>

        {/* A1.2 不匹配横幅 */}
        {data.match && !data.match.matched && (
          <div style={{ fontSize: 11, padding: "8px 14px", background: "rgba(255,152,0,0.12)", color: "#ff9800", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
            ⚠ 网格数据与当前模型几何可能不匹配，可能显示错位
          </div>
        )}

        <VolumeControlPanel
          shellOpacity={shellOpacity}
          onShellOpacityChange={onShellOpacityChange}
          volumeOpacity={volumeOpacity}
          onVolumeOpacityChange={onVolumeOpacityChange}
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
          colorMin={colorRange.min}
          colorMax={colorRange.max}
          scalarMin={data.scalarRange?.min ?? 0}
          scalarMax={data.scalarRange?.max ?? 1}
          onColorRangeChange={onColorRangeChange}
          unit={data.unit || "归一化计数"}
        />

        <div style={{ padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,0.04)", display: "flex", gap: 6 }}>
          <button className="btn btn-ghost btn-xs" style={{ flex: 1, fontSize: 11 }} onClick={() => setAll(true)}>全部选中</button>
          <button className="btn btn-ghost btn-xs" style={{ flex: 1, fontSize: 11 }} onClick={() => setAll(false)}>全部取消</button>
        </div>
        <CellList rows={cellRows} onToggle={toggleCell} />
        <SliceExportPanel frame={currentFrame} displayMin={colorRange.min} scalarBox={scalarBox} />
        <div style={{ padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>粒子 {data.meshtal.particle || "-"} · 网格 {data.meshtal.geom}</span>
          <button className="btn btn-primary btn-xs" onClick={() => { closeCurrentWindow(); }}>关闭</button>
        </div>
      </div>
    </div>
  );
}
