/**
 * CrossSectionView — 平面截面 2D 矢量图（填充多边形）
 *
 * 后端返回每个栅元在切割平面上的多边形顶点 + 材料号，
 * 前端投影到 2D 并按材料颜色填充渲染。
 */
import React, { useRef, useEffect, useState } from "react";
import { useDeck } from "../utils/DeckContext";
import { useAppScale } from "../utils/appScale";

/* ---- 类型 ---- */
interface Polygon3D {
  number: number;
  material: string;
  polygons: { x: number; y: number; z: number }[][];
}

interface Props {
  slices: Polygon3D[];
  plane: { A: number; B: number; C: number; D: number };
  onClose: () => void;
  onPlaneChange?: (plane: { A: number; B: number; C: number; D: number }) => void;
  /** 独立窗口模式：由宿主传入栅元注释（{number, comment}），替代 useDeck() */
  cellComments?: { number: number; comment?: string }[];
  /** 材料页材料表（{number, comment}）：材料图例注释的**权威来源**；缺省回退 useDeck() */
  materials?: { number: number; comment?: string }[];
  /** 标题栏里的导出按钮（由宿主给，保持本组件不依赖出图链路） */
  exportButton?: React.ReactNode;
  /**
   * 把"当前这张矢量图 → 导出请求"的构建函数回填给宿主（宿主负责按钮与触发）。
   * 为什么用回填而不是让本组件自己导出：`svgRef` 在这里，而按钮在宿主手上；
   * 这样两个职责各归其位，本组件仍可独立测试。
   */
  registerExportBuilder?: (fn: (() => ExportFigureRequest) | null) => void;
}

/* ---- 色板（按材料号取模） ---- */
import { getMatColor as matColor } from "../utils/materialColors";
import { MaterialLegend, CellList } from "./MaterialPanel";
import { materialLegendEntries } from "../utils/materialLegend";
import { PlaneControls } from "./PlaneControls";
import { snapshotSvg } from "../export/captureFrame";
import { topMostHit } from "../utils/sectionHit";
import { panAfterDrag, sliceGroupTransform, sliceViewBoxString } from "../utils/sectionView";
import { build2dSpec, subtitleOf } from "../export/figureSpecs";
import type { ExportFigureRequest } from "../export/exportFigure";

/* ---- 叉积 ---- */
function cross(a: number[], b: number[]): number[] {
  return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]];
}

/* ---- 3D→2D 投影（Z+ 向上，用户可旋转） ---- */
// 固定 Z+ 为屏幕上方，返回基础投影函数（不含旋转）
function buildBaseProjection(A: number, B: number, C: number, D: number) {
  const nLen = Math.sqrt(A*A + B*B + C*C);
  if (nLen < 1e-12) return null;
  const n = [A/nLen, B/nLen, C/nLen];

  let ox = 0, oy = 0, oz = 0;
  if (Math.abs(n[0]) > 1e-12) ox = D / n[0];
  else if (Math.abs(n[1]) > 1e-12) oy = D / n[1];
  else oz = D / n[2];

  // v (屏幕 Y) = 世界 Z 投影到平面 → Z+ 为上
  let v: number[];
  const dotZn = n[2];
  if (Math.abs(dotZn) > 0.999) {
    v = [0, 1, 0];  // 水平面：Y 朝上（SVG 用 Y-flip 显示）
  } else {
    const vz = 1 - dotZn * n[2];
    v = [-dotZn * n[0], -dotZn * n[1], vz];
    const vLen = Math.sqrt(v[0]**2 + v[1]**2 + v[2]**2);
    if (vLen > 1e-12) v = v.map(x => x / vLen); else v = [0, 1, 0];
  }

  // u (屏幕 X) = n × v
  let u = cross(n, v);
  const uLen = Math.sqrt(u[0]**2 + u[1]**2 + u[2]**2);
  if (uLen > 1e-12) u = u.map(x => x / uLen); else u = [1, 0, 0];

  return { u, v, ox, oy, oz };
}

// 带旋转角度的投影函数
function makeProjector(base: { u: number[]; v: number[]; ox: number; oy: number; oz: number }, angleDeg: number) {
  const rad = angleDeg * Math.PI / 180;
  const c = Math.cos(rad), s = Math.sin(rad);
  // 旋转 u,v
  const u = [base.u[0]*c + base.v[0]*s, base.u[1]*c + base.v[1]*s, base.u[2]*c + base.v[2]*s];
  const v = [-base.u[0]*s + base.v[0]*c, -base.u[1]*s + base.v[1]*c, -base.u[2]*s + base.v[2]*c];
  const { ox, oy, oz } = base;
  return (px: number, py: number, pz: number): { x: number; y: number } => ({
    x: (px-ox)*u[0] + (py-oy)*u[1] + (pz-oz)*u[2],
    y: (px-ox)*v[0] + (py-oy)*v[1] + (pz-oz)*v[2],
  });
}

/* ---- 主组件（SVG 渲染） ---- */
export default function CrossSectionView({ slices, plane, onClose, onPlaneChange, cellComments, materials, exportButton, registerExportBuilder }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const groupRef = useRef<SVGGElement>(null);
  // 主/子窗口等比缩放时，悬停标签定位用「真实像素」坐标而容器走缩放后坐标系，需除以 scale。
  const scale = useAppScale();
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 600, h: 500 });
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [rotation, setRotation] = useState(0);
  const [step, setStep] = useState(1);
  const [hoverInfo, setHoverInfo] = useState<{ num: number; mat: string; x: number; y: number; z: number } | null>(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });
  const dragStart = useRef({ x: 0, y: 0, px: 0, py: 0 });
  // 从 deck 查栅元注释（slice 数据不带注释）；独立窗口用 props，否则回退 useDeck
  const { deck } = useDeck();
  const commentOf = (num: number): string => {
    if (cellComments) {
      return cellComments.find((c) => c.number === num)?.comment || "";
    }
    return ((deck.cells?.find((c: any) => c.kind === "cell" && c.cell?.number === num) as any)?.cell?.comment) || "";
  };

  // 投影：Z+ 向上（不带旋转，旋转由 SVG transform 处理）
  const baseProj = buildBaseProjection(plane.A, plane.B, plane.C, plane.D);
  const projFn = baseProj ? makeProjector(baseProj, 0) : null;

  // 计算所有多边形在 2D 投影后的坐标
  const cellData = slices.map(s => {
    const color = matColor(s.material);
    const allPts: { x: number; y: number }[] = [];
    const poly2d = s.polygons.map(poly => {
      const pts = poly.map(p => projFn ? projFn(p.x, p.y, p.z) : { x: p.x, y: p.y });
      allPts.push(...pts);
      return pts;
    });
    return { number: s.number, material: s.material, color, comment: commentOf(s.number), polygons: poly2d, allPts };
  });

  // 自动缩放（仅挂载时执行一次）
  useEffect(() => {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const cd of cellData) {
      for (const p of cd.allPts) {
        if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y;
      }
    }
    if (!isFinite(minX)) { minX = -10; maxX = 10; minY = -10; maxY = 10; }
    const rangeX = maxX - minX || 1, rangeY = maxY - minY || 1;
    const m = Math.max(rangeX, rangeY) * 0.1;
    setViewBox({ x: minX - m, y: minY - m, w: rangeX + 2 * m, h: rangeY + 2 * m });
    setZoom(0.9);
  }, []);

  // 滚轮缩放
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 1.15 : 1 / 1.15;
    setZoom(z => Math.max(0.1, Math.min(z * factor, 50)));
  };

  // 拖拽平移
  // ⚠️ 像素↔用户单位的换算与"内容必须跟手"这条不变量都收敛在 utils/sectionView
  // （纯函数 + 属性测试）。这里曾经就地写 `(viewBox.w/zoom)/r.width` 且旋转中心跟着 pan 走，
  // 结果"截面转过角度之后拖动就变怪"（详见该模块头注释）。
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragging) return;
    const svg = svgRef.current;
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    setPan(panAfterDrag({ x: dragStart.current.px, y: dragStart.current.py },
      e.clientX - dragStart.current.x, e.clientY - dragStart.current.y,
      { viewBox, zoom, pan, rotation }, { width: r.width, height: r.height }));
  };
  const handleMouseUp = () => setDragging(false);

  // SVG viewBox + 旋转中心（由 utils/sectionView 单一计算：旋转中心**不含 pan**）
  const viewState = { viewBox, zoom, pan, rotation };
  const vb = sliceViewBoxString(viewState);
  const groupTransform = sliceGroupTransform(viewState);

  // 悬停检测：鼠标位置 → 命中多边形 → 3D 坐标
  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    const g = groupRef.current;
    if (!svg || !g || !baseProj) return;
    const r = svg.getBoundingClientRect();
    setHoverPos({ x: (e.clientX - r.left + 10) / scale, y: (e.clientY - r.top - 10) / scale });
    // 用 SVG DOM 自带的屏幕矩阵（getScreenCTM）换算鼠标坐标到 <g> 本地用户坐标。
    // 该矩阵已包含 viewBox 缩放 + preserveAspectRatio 留白 + 组变换
    // scale(1,-1) rotate(θ)，一键求逆即可，不再手工拆解变换 —— 消除所有位移偏差。
    const ctm = g.getScreenCTM();
    if (!ctm) return;
    const local = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    const mx = local.x, my = local.y;
    // 命中检测（多边形点即 <g> 本地坐标，无需再变换）
    // ⚠️ 必须与**绘制次序**一致：后声明的栅元画在上面 ⇒ 从后往前找第一个命中的那个。
    // 旧实现从数组头开始找，报的是"最先声明的栅元"，与图上看到的层相反
    // （q1112 卡 X=0 平面上，图上钢盘盖住水芯，悬停却报 2 · M1）。
    const hit = topMostHit(cellData, (cd) => cd.polygons, mx, my);
    const found: { num: number; mat: string } | null = hit ? { num: hit.number, mat: hit.material } : null;
    // 反向投影：2D → 3D 平面坐标
    const p3d = {
      x: baseProj.ox + mx * baseProj.u[0] + my * baseProj.v[0],
      y: baseProj.oy + mx * baseProj.u[1] + my * baseProj.v[1],
      z: baseProj.oz + mx * baseProj.u[2] + my * baseProj.v[2],
    };
    setHoverInfo(found ? { ...found, ...p3d } : null);
  };
  const handleSvgMouseLeave = () => setHoverInfo(null);
  const planeLabel = `${plane.A}X + ${plane.B}Y + ${plane.C}Z = ${plane.D}`;
  const totalPolys = cellData.reduce((s, c) => s + c.polygons.length, 0);

  /**
   * 出图：把屏幕上这张 SVG **连样式一起抓下来**（脱离文档后没有 CSS 环境，
   * 不内联样式会整片变黑），配材料图例，组合后出**透明底 PNG**。
   */
  const buildExport = () => {
    /**
     * 描边换算比：**导出面板的显示宽度 / 屏幕上的像素宽度**。
     *
     * 为什么要在导出时手动换算：屏幕上的描边靠 `vector-effect="non-scaling-stroke"`
     * 锚在屏幕像素上，而该属性出了文档（被合成进版面、再光栅化）不保证生效
     * —— 那样描边会被当成用户单位乘以面板缩放比，导出图里的材料边界就比屏幕重。
     * 这里把比例交给 `snapshotSvg({ strokeScale })`，由它摘掉该属性并把线宽换成用户坐标。
     * `panelWidth` 用导出时的印张基准（与 `vectorFigure` 的 `PRINT_MAX_PANEL_SIDE` 同口径）。
     */
    const screenRect = svgRef.current?.getBoundingClientRect();
    const panelW = Math.min(640, Math.round(screenRect?.width ?? 640)) || 640;
    const strokeScale = screenRect && screenRect.width > 0 ? panelW / screenRect.width : 1;
    const svg = snapshotSvg(svgRef.current, {
      stripSelector: '[data-export-strip="1"]',
      strokeScale,
    });
    const legend = materialLegendEntries(
      cellData.map((cd) => cd.material),
      materials ?? (deck as any)?.materials,
    ).map((e) => ({ color: matColor(e.mat), label: `M${e.mat}${e.comment ? " " + e.comment : ""}` }));
    /**
     * ⚠️ **不再给面板加 heading**（2026-09-19 用户实测：导出图里"面板标题 + 下划线"
     * 与副标题叠在一起）。
     * 原因：副标题已写"切割平面 0X+0Y+1Z=0"，heading 又写一遍同一个方程，
     * 而 heading 的强调线正好落在副标题的基线高度上 ⇒ 叠字 + 多一条红线。
     * 平面方程与栅元/多边形计数属**图注**信息，留在 subtitle 一处即可。
     */
    const panels = svg ? [{ svg }] : [];
    /**
     * 材料图例：**带色块的图例**，不是一行材料名清单。
     * 原来只把材料名拼进 caption ⇒ 黑白打印后读者无法把图里的颜色对应到材料，
     * 而"图内符号必须有说明"是期刊硬要求。
     * 几何面板保持**矢量**（截面本来就是多边形，栅格化会把文字与轮廓糊掉）。
     */
    return {
      view: "截面",
      nameParts: [`${plane.A}/${plane.B}/${plane.C}`, plane.D],
      vector: build2dSpec({
        title: "二维截面",
        subtitle: subtitleOf([`切割平面 ${planeLabel}`, `栅元 ${cellData.length} 个 / 多边形 ${totalPolys} 个`]),
        panels,
        legend: legend.length ? legend : undefined,
        caption: "材料配色与屏幕一致；同一平面内重叠区按先声明者占有显示",
      }),
    };
  };

  useEffect(() => {
    registerExportBuilder?.(buildExport);
    return () => registerExportBuilder?.(null);
  });

  return React.createElement("div", {
    className: "preview-overlay",
    style: {
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
      backdropFilter: "blur(8px)", display: "flex",
      flexDirection: "column", zIndex: 1000,
    } as React.CSSProperties,
  },
    /* 顶部栏 */
    React.createElement("div", {
      style: {
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 20px", borderBottom: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(10,10,30,0.8)",
      } as React.CSSProperties,
    },
      React.createElement("span", { style: { fontSize: 14, fontWeight: 600, color: "rgba(241,241,249,0.85)" } },
        `📐 截面: ${planeLabel}`),
      React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center" } },
        React.createElement("span", { style: { fontSize: 11, color: "var(--text-tertiary)" } },
          "滚轮缩放 · 拖拽平移"),
        React.createElement("span", { style: { fontSize: 11, color: "var(--text-tertiary)" } },
          `${cellData.length} 栅元 / ${totalPolys} 多边形`),
        exportButton ?? null,
        React.createElement("button", {
          className: "btn btn-ghost btn-xs", onClick: onClose,
          style: { fontSize: 16, padding: "4px 10px" },
        }, "✕"),
      ),
    ),
    /* 主体 */
    React.createElement("div", {
      style: { flex: 1, display: "flex", overflow: "hidden", position: "relative" } as React.CSSProperties,
    },
      /* SVG 画布 */
      React.createElement("svg", {
        ref: svgRef,
        viewBox: vb,
        style: { flex: 1, background: "#0a0a1e", cursor: dragging ? "grabbing" : "grab", minWidth: 0 } as React.CSSProperties,
        onWheel: handleWheel,
        onMouseDown: handleMouseDown,
        onMouseMove: function(e: React.MouseEvent<SVGSVGElement>) { handleMouseMove(e); handleSvgMouseMove(e); },
        onMouseUp: handleMouseUp,
        onMouseLeave: function() { handleMouseUp(); handleSvgMouseLeave(); },
      },
        React.createElement("g", { ref: groupRef, transform: groupTransform },
          cellData.map(cd =>
            cd.polygons.map((poly, pi) =>
              React.createElement("polygon", {
                key: `${cd.number}-${pi}`,
                points: poly.map(p => `${p.x},${p.y}`).join(" "),
                fill: cd.color,
                fillOpacity: 0.45,
                stroke: cd.color,
                /**
                 * ── 描边为什么这么定（2026-09-19 用户实测"材料边界描边还是太重"）──
                 *
                 * 旧实现 `1.5 / zoom`：数值**写在用户坐标里**，于是
                 *   ① 视图缩放到 0.9 时线反而**变粗**（1.5/0.9 = 1.67 用户单位）；
                 *   ② 滚轮拉近（zoom→1.5）线**变细**；拉远（zoom→0.2）线粗到 6.5 用户单位
                 *      —— **缩放时线宽自己乱变**，这是当初"加粗"观感的来源。
                 *   ③ 导出到矢量面板时，整张 SVG 还要被 `panelTransform` 缩放，
                 *      描边**再被放大一次** ⇒ 导出图里的边界比屏幕上更重（用户这次报的就是它）。
                 *
                 * 现在：**屏幕空间恒定** —— 用 `vector-effect="non-scaling-stroke"` 把线宽锚在
                 * 屏幕像素上（1.2px，细而清楚），缩放时线宽不再漂移；
                 * 导出时 `snapshotSvg({ strokeScale })` 会把该属性摘掉并**换算成用户坐标**
                 * （`1.2 / strokeScale`），保证导出图里边界同样是 1.2px 的细线。
                 */
                strokeWidth: 1.2,
                vectorEffect: "non-scaling-stroke",
                strokeOpacity: 0.85,
              })
            )
          ),
        ),
      ),
      hoverInfo ? React.createElement("div", {
        style: {
          position: "absolute", left: hoverPos.x, top: hoverPos.y, pointerEvents: "none",
          background: "rgba(0,0,0,0.8)", color: "#fff", fontSize: 11, padding: "4px 8px",
          borderRadius: 4, whiteSpace: "nowrap", zIndex: 10, border: "1px solid rgba(255,255,255,0.15)",
        } as React.CSSProperties,
      }, `${hoverInfo.num} · M${hoverInfo.mat} · (${hoverInfo.x.toFixed(1)}, ${hoverInfo.y.toFixed(1)}, ${hoverInfo.z.toFixed(1)})`) : null,
      /* 右侧控制面板 */
      React.createElement("div", {
        style: {
          /**
           * 宽度 220 → **280**（2026-09-19 用户实测"截面界面排版有问题"）。
           * 根因：共享控件 `PlaneControls` 在 `showStepButtons` 打开时，步长那行要
           * 4 个按钮 + 1 个输入框（实测 **274px**），而 220 的面板减去左右 padding 只剩 ~190px
           * ⇒ 横向溢出、面板底部出现横向滚动条、控件被切掉。
           * 修法两条一起上：**面板加宽** + `PlaneControls` 传 `stacked`（拆成三行，每行只需 ~148px）。
           */
          width: 280, borderLeft: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(10,10,30,0.6)", display: "flex", flexDirection: "column",
          flexShrink: 0, padding: "12px 14px", gap: 4, overflowY: "auto", overflowX: "hidden",
        } as React.CSSProperties,
      },
        /* 材料颜色对照（与 3D 预览同一共享组件）：注释**只**取材料页，栅元注释留在栅元列表 */
        React.createElement(MaterialLegend, {
          entries: materialLegendEntries(
            cellData.map(cd => cd.material),
            materials ?? (deck as any)?.materials,
          ),
        }),
        /* 平面 + 步进（共享控件：方程解析/步长语义与 3D 预览、切面面板完全一致）
           stacked：本栏窄，步长与步进拆成上下两行，避免 274px 的行宽撑破 280px 的面板 */
        React.createElement(PlaneControls, {
          plane: plane,
          onPlaneChange: (p) => { if (onPlaneChange) onPlaneChange(p); },
          step: step,
          onStepChange: setStep,
          showStepButtons: !!onPlaneChange,
          stacked: true,
          onStepMove: (p) => { if (onPlaneChange) onPlaneChange(p); },
          stepTitle: "沿法向平移一个步长并重新切",
        }),
        React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 4, margin: "8px 0 4px", minWidth: 0 } as React.CSSProperties },
          React.createElement("span", { style: { fontSize: 11, color: "var(--text-secondary)", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, "🔄 旋转"),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setRotation(r => r - 15), style: { fontSize: 10, flexShrink: 0 } }, "◀"),
          React.createElement("input", {
            type: "text",
            "aria-label": "截面旋转角度",
            value: `${rotation}°`,
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
              const v = parseInt(e.target.value.replace(/[°]/g, ""));
              if (!isNaN(v)) setRotation(v);
            },
            style: { width: 40, height: 20, fontSize: 10, textAlign: "center", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "var(--text-primary)", borderRadius: 3, outline: "none", flexShrink: 0 } as React.CSSProperties,
          }),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setRotation(r => r + 15), style: { fontSize: 10, flexShrink: 0 } }, "▶"),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setRotation(0), style: { fontSize: 9, flexShrink: 0 } }, "复位"),
        ),
        React.createElement("hr", { style: { width: "100%", border: "none", borderTop: "1px solid rgba(255,255,255,0.06)", margin: "8px 0" } }),
        React.createElement("span", { style: { fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 } }, "栅元列表"),
        /* 与 3D 预览同一共享组件（只读，注释 + 尾部面数） */
        React.createElement(CellList, {
          rows: cellData.map(cd => ({ num: cd.number, mat: cd.material, comment: cd.comment, trailing: `${cd.polygons.length} 面` })),
        }),
        React.createElement("div", { style: { marginTop: "auto", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 8 } },
          React.createElement("button", {
            className: "btn btn-primary btn-sm",
            onClick: onClose, style: { width: "100%" },
          }, "关闭"),
        ),
      ),
    ),
  );
}
