/**
 * SliceExportPanel — 切面预览 + 出图（轴对齐快捷定位 / **自由平面** / 成叠导出）。
 *
 * ## 这次改造的三件事
 * 1. **自由平面**：平面方程输入框与 3D 预览的截面同源（`planeEquation` + `PlaneControls`），
 *    不再只有 X/Y/Z 三个方向。方程里的坐标就是体积网格的世界坐标（与 `worldBox` 同系）。
 * 2. **成叠导出**：给了步长就能沿法向摊成一串平面，**每片一张矢量图**、文件名自动编号。
 *    写报告时"沿轴向一串切片"是常态，一张张点太累。
 * 3. 屏幕预览仍是快路径（轴对齐、直接按层号取体素）；自由平面预览走按需取样。
 *
 * ## 为什么"轴+层号"还留着
 * 它是最常用的一键定位（层号滑杆比手写方程快得多）。它现在**只是平面的快捷输入**：
 * 拖动时把平面设成对应的轴对齐平面；反过来，输入轴对齐方程时滑杆位置也跟着变。
 * 两条路最终都归到同一个 `plane` 状态，不会出现"滑杆和方程各说各话"。
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { sliceFrame, frameToCsv, type SliceAxis, type SliceFrameInput } from "./sliceExport";
import { formatLegendValue } from "./ColorLegend";
import { ExportButton } from "../export/useFigureExport";
import { build2dSpec, subtitleOf } from "../export/figureSpecs";
import { themeFor } from "../export/plotTheme";
import { fieldFromQuantized, contourSvgPath } from "../export/contour";
import { rgbaToPngDataUrl, base64ToBytes } from "../export/captureFrame";
import { PlaneControls } from "../components/PlaneControls";
import { axisPlane, planeSeries, parsePlane, planeToStr, type PlaneEq } from "../three/planeEquation";
import { samplePlane, sampleHeatPng, sampleContours, planeRangeInBox, type AABB } from "../export/planeSample";
import { COLORMAP } from "../export/plotTheme";
import { vectorColorbar } from "../export/vectorFigure";
import { exportFigure } from "../export/exportFigure";

/** 导出图里等值线的条数（论文图 8 条左右最耐看；屏幕上不显示，只在导出时画） */
const EXPORT_CONTOUR_LEVELS = 8;
/** 导出图的每个体素放大倍数 */
const EXPORT_CELL = 4;
/** 成叠导出的片数上限（防手滑把步长设成 0.001 卡死界面） */
const MAX_STACK = 200;
/** 色带面板宽度（出图版面里留给色阶的列宽） */
const COLORBAR_W = 150;

interface SliceExportPanelProps {
  /** 当前 (energy,time) 帧标量（null = 尚无数据，禁用） */
  frame: SliceFrameInput | null;
  /** 色阶下限（显示阈值，低于不显示） */
  displayMin: number;
  /** 网格世界坐标范围（自由平面取样用；缺省退回按网格下标估算） */
  scalarBox?: AABB | null;
  /** 受控平面（与 3D 预览同一套语义）；缺省内部自持有 */
  plane?: PlaneEq;
  onPlaneChange?: (p: PlaneEq) => void;
}

const AXIS_OPTIONS: { value: SliceAxis; label: string }[] = [
  { value: "x", label: "X 轴" },
  { value: "y", label: "Y 轴" },
  { value: "z", label: "Z 轴" },
];

function downloadBlob(name: string, blob: Blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

/**
 * 轴对齐平面 → {轴, 层号}；非轴对齐返回 null（自由平面时滑杆不参与）。
 *
 * ⚠️ 层号是**网格下标**，换算必须与取样口径一致：本仓库用**节点口径**
 * （`min + k*(max-min)/(size-1)` 对应第 k 层，与 `sliceFrame`、体积渲染一致）。
 * 曾直接 `round(D/coef)` 当层号：worldBox=[0,100]、51 层时拖到第 10 层得到 D=20，
 * 回算就跳成第 21 层（滑杆与方程互相打架）。
 */
function axisInfoOf(
  plane: PlaneEq,
  box: AABB,
  res: [number, number, number],
): { axis: SliceAxis; index: number } | null {
  const mags: [SliceAxis, number][] = [["x", Math.abs(plane.A)], ["y", Math.abs(plane.B)], ["z", Math.abs(plane.C)]];
  mags.sort((a, b) => b[1] - a[1]);
  const [axis, m] = mags[0];
  const others = mags.slice(1).every(([, v]) => v < 1e-9);
  if (!others || m < 1e-9) return null;
  const coef = axis === "x" ? plane.A : axis === "y" ? plane.B : plane.C;
  const size = axis === "x" ? res[0] : axis === "y" ? res[1] : res[2];
  const lo = axis === "x" ? box.min[0] : axis === "y" ? box.min[1] : box.min[2];
  const hi = axis === "x" ? box.max[0] : axis === "y" ? box.max[1] : box.max[2];
  if (size < 2) return { axis, index: 0 };
  const pitch = (hi - lo) / (size - 1); // 节点间距（与 samplePlane 同一口径）
  const world = plane.D / coef;
  const k = pitch > 0 ? (world - lo) / pitch : 0;
  return { axis, index: Math.max(0, Math.min(size - 1, Math.round(k))) };
}

export default function SliceExportPanel({ frame, displayMin, scalarBox, plane: planeProp, onPlaneChange }: SliceExportPanelProps) {
  const [axis, setAxis] = useState<SliceAxis>("z");
  const [index, setIndex] = useState(0);
  const [planeLocal, setPlaneLocal] = useState<PlaneEq>(() => axisPlane("z", 0));
  const plane = planeProp ?? planeLocal;
  const [axisFree, setAxisFree] = useState(false);
  const [step, setStep] = useState(1);
  const [stack, setStack] = useState(false);
  const [busy, setBusy] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  /**
   * 平面变化 → 同步「轴 + 层号」快捷定位。
   * 轴对齐方程（只有一项非零）→ 滑杆跟着走；自由平面 → 滑杆停用（`axisFree`），
   * 避免"滑杆位置和方程各说各话"。
   */
  const applyPlane = (p: PlaneEq) => {
    setPlaneLocal(p);
    onPlaneChange?.(p);
    const info = axisInfoOf(p, worldBox, frame?.resolution ?? [1, 1, 1]);
    setAxisFree(info === null);
    if (info) { setAxis(info.axis); setIndex(info.index); }
  };

  /**
   * 体积盒（世界坐标）。
   * 缺省 `[0, res-1]` —— 与**节点口径**取样一致（体积渲染与轴对齐切面都按此约定）。
   */
  const worldBox: AABB = useMemo(() => {
    if (scalarBox) return scalarBox;
    const [ni, nj, nk] = frame?.resolution ?? [1, 1, 1];
    return { min: [0, 0, 0], max: [Math.max(1, ni - 1), Math.max(1, nj - 1), Math.max(1, nk - 1)] };
  }, [scalarBox, frame]);

  const axisSize = useMemo(() => {
    if (!frame) return 0;
    const [ni, nj, nk] = frame.resolution;
    if (axis === "x") return ni;
    if (axis === "y") return nj;
    return nk;
  }, [frame, axis]);

  const sliceIndex = Math.max(0, Math.min(index, Math.max(0, axisSize - 1)));

  const slice = useMemo(() => {
    if (!frame || axisFree) return null;
    return sliceFrame(frame, axis, sliceIndex, displayMin);
  }, [frame, axis, sliceIndex, displayMin, axisFree]);

  /** 自由平面的取样结果（轴对齐时不取样：屏幕预览走快路径） */
  const freeSample = useMemo(() => {
    if (!frame || !axisFree) return null;
    const bytes = base64ToBytes(frame.dataBase64);
    return samplePlane(plane, worldBox, frame.resolution, bytes, frame.scalarRange, { samples: 160 });
  }, [frame, plane, worldBox, axisFree]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (slice) {
      canvas.width = slice.width;
      canvas.height = slice.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const img = ctx.createImageData(slice.width, slice.height);
      img.data.set(slice.rgba);
      ctx.putImageData(img, 0, 0);
      return;
    }
    // 自由平面：直接把取样热图画进预览 canvas
    if (freeSample) {
      const png = sampleHeatPng(freeSample, displayMin, 1);
      if (!png) return;
      const img = new Image();
      img.onload = () => {
        canvas.width = freeSample.width;
        canvas.height = freeSample.height;
        canvas.getContext("2d")?.drawImage(img, 0, 0);
      };
      img.src = png;
    }
  }, [slice, freeSample, displayMin]);

  /**
   * 预览区的小图导出（PNG）。
   *
   * ⚠️ 它只导**屏幕预览那块小 canvas**（约 200px 宽），是"快速拿一张看看"的便利入口；
   * 要贴报告/论文请用上面的正式导出（论文配色 + 色带 + 高分辨率）。
   * 保留它是为了不改变用户已习惯的操作，但**不再**提供"逐体素方块"的深色 SVG 导出
   * ——那与正式导出配色/质量都不一致，两个入口并存只会让人不知道该点哪个。
   */
  const exportSlicePng = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const name = `slice_preview_${axis}_${sliceIndex}.png`;
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = name;
    a.click();
  };

  const exportFrameCsv = () => {
    if (!frame) return;
    const blob = new Blob([frameToCsv(frame)], { type: "text/csv" });
    downloadBlob(`frame_${axis}_slice.csv`, blob);
  };

  /**
   * 从体积帧里取出当前切面的 8bit 标量（**与 `sliceExport.sliceFrame` 逐字节同布局**，
   * 否则等值线会与热图错位）：
   *   x 切 → (row=j, col=k) → idx = i*(nj*nk) + j*nk + k
   *   y 切 → (row=i, col=k) → idx = i*(nj*nk) + j*nk + k
   *   z 切 → (row=j, col=i) → idx = i*(nj*nk) + j*nk + k
   */
  const sliceFieldBytes = (w: number, h: number, ax: SliceAxis, k: number): Uint8Array => {
    if (!frame) return new Uint8Array(0);
    const [ni, nj, nk] = frame.resolution;
    const bytes = base64ToBytes(frame.dataBase64);
    void ni;
    const out = new Uint8Array(w * h);
    for (let row = 0; row < h; row++) {
      for (let col = 0; col < w; col++) {
        let i = 0, j = 0, kk = 0;
        if (ax === "x") { i = k; j = row; kk = col; }
        else if (ax === "y") { i = row; j = k; kk = col; }
        else { i = col; j = row; kk = k; }
        out[row * w + col] = bytes[i * (nj * nk) + j * nk + kk] ?? 0;
      }
    }
    return out;
  };

  /** 当前平面的标题/文件名段 */
  const planeTag = (p: PlaneEq = plane) => {
    const info = axisInfoOf(p, worldBox, frame?.resolution ?? [1, 1, 1]);
    return info ? `${info.axis.toUpperCase()}${info.index + 1}` : planeToStr(p).replace(/\s+/g, "");
  };

  /**
   * 出图：**位图热图作底 + 真矢量等值线**，走纯矢量出口（PDF+SVG、论文配色、透明底）。
   *
   * ⚠️ 轴与层号**必须从传入的 `p` 现算**，不能用组件闭包里的 `axis/sliceIndex`：
   * 成叠导出会一次性遍一叠平面，闭包值永远是"当前屏幕上那一片"——
   * 那样导出的 20 片会长得一模一样（实测踩过）。
   */
  const buildExportFor = (p: PlaneEq, tag: string) => {
    const cells = EXPORT_CELL;
    const theme = themeFor("paper");
    if (!frame) return { view: "fmesh切面" };
    const info = axisInfoOf(p, worldBox, frame?.resolution ?? [1, 1, 1]);
    const isFree = info === null;

    let width = 0, height = 0, heatLayer = "", contours = "", sub = "";
    // 色带上下限：自由平面用取样实际值域；轴对齐用体素网格级（与屏幕预览同一坐标系）
    let cbMin = frame.scalarRange.min, cbMax = frame.scalarRange.max;

    if (isFree) {
      const bytes = base64ToBytes(frame.dataBase64);
      const s = samplePlane(p, worldBox, frame.resolution, bytes, frame.scalarRange, { samples: 160 });
      if (s) {
        width = s.width * cells;
        height = s.height * cells;
        const png = sampleHeatPng(s, displayMin, cells);
        heatLayer = png
          ? `<image x="0" y="0" width="${width}" height="${height}" preserveAspectRatio="none" xlink:href="${png}" href="${png}"/>`
          : "";
        contours = sampleContours(s, {
          levels: EXPORT_CONTOUR_LEVELS, cell: cells, color: theme.axis,
          minValue: displayMin,
        });
        cbMin = s.min; cbMax = s.max;
        sub = subtitleOf([`平面 ${planeToStr(p)}`, `取样 ${s.width}×${s.height}`, `值域 ${formatLegendValue(s.min)} ~ ${formatLegendValue(s.max)}`]);
      }
    } else {
      const sl = sliceFrame(frame, info.axis, info.index, displayMin);
      width = sl.width * cells;
      height = sl.height * cells;
      const png = rgbaToPngDataUrl(sl.rgba, sl.width, sl.height);
      heatLayer = png
        ? `<image x="0" y="0" width="${width}" height="${height}" preserveAspectRatio="none" xlink:href="${png}" href="${png}"/>`
        : "";
      const field = fieldFromQuantized(sliceFieldBytes(sl.width, sl.height, info.axis, info.index), sl.width, sl.height, frame.scalarRange.min, frame.scalarRange.max);
      const hi = frame.scalarRange.max;
      contours = contourSvgPath(field, Math.max(sl.min, frame.scalarRange.min), hi, {
        levels: EXPORT_CONTOUR_LEVELS, cell: cells, color: theme.axis, strokeWidth: 1.1,
        minValue: displayMin, opacity: 0.8,
      });
      cbMin = Math.max(sl.min, frame.scalarRange.min); cbMax = hi;
      sub = subtitleOf([
        `${info.axis.toUpperCase()} 轴第 ${info.index + 1}/${Math.max(axisSize, 1)} 层`,
        `显示阈值 ${formatLegendValue(displayMin)} ~ ${formatLegendValue(hi)}`,
        `${sl.width}×${sl.height} 个体素`,
      ]);
    }

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${heatLayer}${contours}</svg>`;
    return {
      view: "fmesh切面",
      nameParts: [tag],
      vector: build2dSpec({
        title: "网格计数切面",
        subtitle: sub,
        panels: width && height ? [{ svg, heading: isFree ? "自由平面 · 热图 + 等值线" : "热图 + 等值线" }] : [],
        // 热图**必须**配色阶刻度，否则读者无法把颜色换算成计数
        // ——「视图 + 图例/元信息」是出图规格的硬要求，不是可选装饰。
        trailing: width && height
          ? {
              heading: "色阶",
              width: COLORBAR_W,
              svg:
                `<svg xmlns="http://www.w3.org/2000/svg" width="${COLORBAR_W}" height="320" viewBox="0 0 ${COLORBAR_W} 320">` +
                vectorColorbar(4, 10, 22, 250, COLORMAP, cbMin, cbMax, "计数") +
                `</svg>`,
            }
          : undefined,
        caption: `等值线 ${EXPORT_CONTOUR_LEVELS} 条（矢量）叠加在热图上；低于显示阈值 ${formatLegendValue(displayMin)} 的区域淡出`,
      }),
    };
  };

  const buildExport = () => buildExportFor(plane, planeTag(plane));

  /** 成叠导出：沿法向按步长摊开，每片一张矢量图（文件名自动编号） */
  const exportStack = async () => {
    if (!frame || busy) return;
    const { min, max } = planeRangeInBox(plane, worldBox);
    const list = planeSeries(plane, step, min, max, MAX_STACK);
    if (!list.length) { alert("按当前步长算不出任何切片（请检查步长/平面）"); return; }
    setBusy(true);
    try {
      const files: string[] = [];
      let degraded = 0;
      for (const item of list) {
        const tag = `${planeTag(item.plane)}_d${item.d.toFixed(3)}`;
        const r = await exportFigure(buildExportFor(item.plane, tag));
        if (r.status === "cancelled") break;          // 用户在「另存为」里取消 → 停
        if (r.status === "error") { alert(`第 ${item.index} 片导出失败：${r.message}`); break; }
        files.push(`${item.index}. ${tag}`);
        degraded += r.files.filter((f) => f.degraded).length;
      }
      alert(`✅ 成叠导出完成：${files.length} 片（步长 ${step}，共 ${list.length} 片）\n` +
        files.slice(0, 5).join("\n") + (files.length > 5 ? `\n…以及另外 ${files.length - 5} 片` : "") +
        (degraded ? `\n\n注：其中 ${degraded} 个文件走了位图降级（无中文字体或体积超限）` : ""));
    } finally {
      setBusy(false);
    }
  };

  if (!frame) {
    return null;
  }

  return (
    <div style={{ padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 6 }}>
        ✂ 切面 / 导出
      </div>

      {/* 平面（方程 + 步长，与 3D 预览的截面同一套控件与语义） */}
      <PlaneControls
        plane={plane}
        onPlaneChange={applyPlane}
        step={step}
        onStepChange={setStep}
        compact
      />

      {/* 快捷定位：轴 + 层号（把平面设成轴对齐平面；自由平面时禁用） */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6, marginBottom: 6, flexWrap: "wrap" }}>
        <select
          className="form-select"
          value={axisFree ? "" : axis}
          onChange={(e) => {
            const a = e.target.value as SliceAxis;
            if (!a) { setAxisFree(true); return; }
            setAxisFree(false);
            setAxis(a);
            setIndex(0);
            applyPlane(axisPlane(a, 0));
          }}
          style={{ height: 26, fontSize: 11, width: 110 }}
          title="快捷定位：按轴对齐切（也可以直接写平面方程）"
        >
          {axisFree && <option value="">自由平面</option>}
          {AXIS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <input
          type="range"
          min={0}
          max={Math.max(0, axisSize - 1)}
          value={sliceIndex}
          disabled={axisFree}
          onChange={(e) => {
            const k = parseInt(e.target.value, 10) || 0;
            setIndex(k);
            // 层号 → 世界坐标（用网格边界线性映射，切出来的位置与滑杆一致）
            const lo = axis === "x" ? worldBox.min[0] : axis === "y" ? worldBox.min[1] : worldBox.min[2];
            const hi = axis === "x" ? worldBox.max[0] : axis === "y" ? worldBox.max[1] : worldBox.max[2];
            const t = axisSize > 1 ? k / (axisSize - 1) : 0;
            applyPlane(axisPlane(axis, lo + (hi - lo) * t));
          }}
          style={{ flex: 1, accentColor: "var(--accent)" }}
          title={axisFree ? "自由平面模式下由方程决定位置" : "层号"}
        />
        <span style={{ color: "var(--text-tertiary)", fontSize: 10, flexShrink: 0 }}>
          {axisFree ? "自由平面" : `${sliceIndex + 1}/${Math.max(axisSize, 1)}`}
        </span>
      </div>

      {/* 成叠导出 */}
      <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 6, flexWrap: "wrap" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: "var(--text-secondary)", cursor: "pointer" }}>
          <input type="checkbox" checked={stack} onChange={(e) => setStack(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
          成叠导出（按步长切一叠）
        </label>
        {stack && (
          <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
            将导出 {Math.min(planeSeries(plane, step, planeRangeInBox(plane, worldBox).min, planeRangeInBox(plane, worldBox).max, MAX_STACK).length, MAX_STACK)} 片
          </span>
        )}
      </div>

      {(slice || freeSample) && (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
          <canvas ref={canvasRef} style={{ maxWidth: 200, maxHeight: 140, borderRadius: 3, border: "1px solid rgba(255,255,255,0.12)", imageRendering: "pixelated", background: "#0a0a1e" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 10, flex: 1 }}>
            <span style={{ color: "var(--text-tertiary)" }}>
              {axisFree
                ? `自由平面取样 ${freeSample?.width}×${freeSample?.height} · 值域 ${formatLegendValue(freeSample?.min ?? 0)} ~ ${formatLegendValue(freeSample?.max ?? 0)}`
                : `切面值域：${formatLegendValue(slice?.min ?? 0)} ~ ${formatLegendValue(slice?.max ?? 0)}`}
            </span>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {stack ? (
                <button className="btn btn-primary btn-xs" onClick={exportStack} disabled={busy} style={{ fontSize: 10 }}>
                  {busy ? "导出中…" : "⬇ 导出这一叠"}
                </button>
              ) : (
                <ExportButton build={buildExport} label="fmesh 切面图" />
              )}
              <button
                className="btn btn-ghost btn-xs"
                onClick={exportSlicePng}
                disabled={axisFree}
                style={{ fontSize: 10 }}
                title="只导出屏幕预览那块小图；要贴报告请用左边的正式导出（论文配色 + 色带 + 高分辨率）"
              >预览 PNG</button>
              <button className="btn btn-ghost btn-xs" onClick={exportFrameCsv} style={{ fontSize: 10 }}>导出 CSV</button>
            </div>
            <span style={{ color: "var(--text-tertiary)", fontSize: 9, lineHeight: 1.4 }}>
              {axisFree
                ? "自由平面：等值线为矢量，热图为位图底；成叠导出按步长沿法向摊开"
                : `切面 = ${axis.toUpperCase()} 固定第 ${sliceIndex + 1} 层；CSV 导出当前帧全部体素（i,j,k,value）`}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}


