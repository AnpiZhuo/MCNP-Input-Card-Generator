/**
 * CrossSectionView — 平面截面 2D 矢量图（填充多边形）
 *
 * 后端返回每个栅元在切割平面上的多边形顶点 + 材料号，
 * 前端投影到 2D 并按材料颜色填充渲染。
 */
import React, { useRef, useEffect, useState } from "react";
import { useDeck } from "../utils/DeckContext";

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
}

/* ---- 色板（按材料号取模） ---- */
import { getMatColor as matColor } from "../utils/materialColors";
import { MaterialLegend, CellList } from "./MaterialPanel";

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
export default function CrossSectionView({ slices, plane, onClose, onPlaneChange }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const groupRef = useRef<SVGGElement>(null);
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 600, h: 500 });
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [rotation, setRotation] = useState(0);
  const [step, setStep] = useState(1);
  const [hoverInfo, setHoverInfo] = useState<{ num: number; mat: string; x: number; y: number; z: number } | null>(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });
  const dragStart = useRef({ x: 0, y: 0, px: 0, py: 0 });
  // 从 deck 查栅元注释（slice 数据不带注释）
  const { deck } = useDeck();
  const commentOf = (num: number): string => deck.cells?.find(c => c.number === num)?.comment || "";

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
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragging) return;
    setPan({ x: dragStart.current.px + (e.clientX - dragStart.current.x) / zoom,
             y: dragStart.current.py + (e.clientY - dragStart.current.y) / zoom });
  };
  const handleMouseUp = () => setDragging(false);

  // SVG viewBox + 旋转中心（以 2D 数据中点为中心旋转）
  const vb = `${viewBox.x - pan.x} ${viewBox.y - pan.y} ${viewBox.w / zoom} ${viewBox.h / zoom}`;
  const rotCx = (viewBox.x - pan.x) + (viewBox.w / zoom) / 2;
  const rotCy = (viewBox.y - pan.y) + (viewBox.h / zoom) / 2;

  // 悬停检测：鼠标位置 → 命中多边形 → 3D 坐标
  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    const g = groupRef.current;
    if (!svg || !g || !baseProj) return;
    const r = svg.getBoundingClientRect();
    setHoverPos({ x: e.clientX - r.left + 10, y: e.clientY - r.top - 10 });
    // 用 SVG DOM 自带的屏幕矩阵（getScreenCTM）换算鼠标坐标到 <g> 本地用户坐标。
    // 该矩阵已包含 viewBox 缩放 + preserveAspectRatio 留白 + 组变换
    // scale(1,-1) rotate(θ)，一键求逆即可，不再手工拆解变换 —— 消除所有位移偏差。
    const ctm = g.getScreenCTM();
    if (!ctm) return;
    const local = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    const mx = local.x, my = local.y;
    // 命中检测（多边形点即 <g> 本地坐标，无需再变换）
    let found: { num: number; mat: string } | null = null;
    for (const cd of cellData) {
      for (const poly of cd.polygons) {
        let inside = false;
        for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
          const xi = poly[i].x, yi = poly[i].y;
          const xj = poly[j].x, yj = poly[j].y;
          if ((yi > my) !== (yj > my) && mx < (xj - xi) * (my - yi) / (yj - yi) + xi) inside = !inside;
        }
        if (inside) { found = { num: cd.number, mat: cd.material }; break; }
      }
      if (found) break;
    }
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

  return React.createElement("div", {
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
        React.createElement("g", { ref: groupRef, transform: `scale(1,-1) rotate(${rotation} ${rotCx} ${rotCy})` },
          cellData.map(cd =>
            cd.polygons.map((poly, pi) =>
              React.createElement("polygon", {
                key: `${cd.number}-${pi}`,
                points: poly.map(p => `${p.x},${p.y}`).join(" "),
                fill: cd.color,
                fillOpacity: 0.45,
                stroke: cd.color,
                strokeWidth: 1.5 / zoom,
                strokeOpacity: 0.9,
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
          width: 220, borderLeft: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(10,10,30,0.6)", display: "flex", flexDirection: "column",
          flexShrink: 0, padding: "12px 14px", gap: 4, overflow: "auto",
        } as React.CSSProperties,
      },
        /* 材料颜色对照（与 3D 预览同一共享组件，带注释） */
        React.createElement(MaterialLegend, {
          entries: cellData.map(cd => ({ mat: cd.material, comment: cd.comment })),
        }),
        React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 4, margin: "8px 0 4px" } as React.CSSProperties },
          React.createElement("span", { style: { fontSize: 11, color: "var(--text-secondary)", flex: 1 } }, "📏 步进"),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => { if (onPlaneChange) onPlaneChange({ ...plane, D: plane.D - step }); }, style: { fontSize: 10 } }, "◀"),
          React.createElement("input", {
            type: "text", value: String(step),
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v > 0) setStep(v); },
            style: { width: 40, height: 20, fontSize: 10, textAlign: "center", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "var(--text-primary)", borderRadius: 3, outline: "none" } as React.CSSProperties,
          }),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => { if (onPlaneChange) onPlaneChange({ ...plane, D: plane.D + step }); }, style: { fontSize: 10 } }, "▶"),
        ),
        React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 4, margin: "8px 0 4px" } as React.CSSProperties },
          React.createElement("span", { style: { fontSize: 11, color: "var(--text-secondary)", flex: 1 } }, "🔄 旋转"),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setRotation(r => r - 15), style: { fontSize: 10 } }, "◀"),
          React.createElement("input", {
            type: "text",
            value: `${rotation}°`,
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
              const v = parseInt(e.target.value.replace(/[°]/g, ""));
              if (!isNaN(v)) setRotation(v);
            },
            style: { width: 40, height: 20, fontSize: 10, textAlign: "center", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "var(--text-primary)", borderRadius: 3, outline: "none" } as React.CSSProperties,
          }),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setRotation(r => r + 15), style: { fontSize: 10 } }, "▶"),
          React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: () => setRotation(0), style: { fontSize: 9 } }, "复位"),
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
