/**
 * TallyChartWindow — 独立「Tally 通量图」窗口宿主。
 *
 * 由输出页「绘图」按钮打开（`openTallyChart` 写桥 → Rust 开窗 → 这里读桥渲染）。
 * 图按窗口尺寸自适应，导出按钮与其它结果图窗口位置一致。
 *
 * 为什么不再用弹窗（原实现）：`maxWidth:640` 的卡片里塞一张 560×300 的图，
 * 下面还压着数据表 —— 图小、不能调大小、两边都挤。独立窗口后图铺满、表留在输出页。
 */
import React, { useEffect, useRef, useState } from "react";
import { readTallyChartData, closeCurrentWindow } from "../utils/windows";
import { buildPaperTallyChart } from "../utils/tallyChartPaper";
import type { TallyRow } from "../utils/outputParser";
import { ExportButton } from "../export/useFigureExport";
import { build2dSpec } from "../export/figureSpecs";

interface BridgeData {
  tallyNumber: string;
  rows: TallyRow[];
  title?: string;
  path?: string;
}

export default function TallyChartWindow() {
  const [data] = useState<BridgeData | null>(() => readTallyChartData() as BridgeData | null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 900, h: 600 });

  // 按窗口尺寸自适应（图随窗口缩放，不再写死 560×300）
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) setSize({ w: Math.round(r.width), h: Math.round(r.height) });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [data]);

  const buildChart = (w: number, h: number) => (data ? buildPaperTallyChart(data.rows || [], { width: w, height: h }) : null);

  const containerStyle: React.CSSProperties = {
    position: "absolute", inset: 0, display: "flex", flexDirection: "column",
    background: "#0a0a1e", color: "#fff", overflow: "hidden",
  };

  if (!data) {
    return React.createElement("div", { style: containerStyle },
      React.createElement("div", { style: { margin: "auto", fontSize: 14, color: "#888" } },
        "没有 Tally 数据（请从主窗口「输出」标签页解析 .outp 后点「绘图」）"),
    );
  }

  const chart = buildChart(size.w - 32, size.h - 96);

  return React.createElement("div", { style: containerStyle },
    React.createElement("div", {
      style: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.08)" },
    },
      React.createElement("span", { style: { fontSize: 13, fontWeight: 700 } },
        `📈 Tally ${data.tallyNumber} 通量图${data.title ? ` — ${data.title}` : ""}`),
      React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8 } },
        React.createElement("span", { style: { fontSize: 11, color: "var(--text-tertiary)" } },
          `${(data.rows || []).length} 个能量点`),
        React.createElement(ExportButton, {
          label: "Tally 通量图",
          build: () => {
            // 导出用固定画幅（不跟随窗口，保证出图尺寸稳定、可复现）
            const svg = buildChart(760, 460);
            return {
              view: "Tally通量图",
              nameParts: [`tally${data.tallyNumber}`, `${(data.rows || []).length}点`],
              vector: build2dSpec({
                title: `Tally ${data.tallyNumber} 通量谱`,
                subtitle: data.title || undefined,
                panels: svg ? [{ svg }] : [],
                caption: "红短线为相对误差（1σ）；通量跨 100 倍以上时 y 轴自动切换对数刻度",
              }),
            };
          },
        }),
        React.createElement("button", {
          className: "btn btn-ghost btn-xs",
          onClick: () => { closeCurrentWindow(); },
          style: { fontSize: 16, padding: "4px 10px" },
        }, "✕"),
      ),
    ),
    React.createElement("div", {
      ref: wrapRef,
      style: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 16, minHeight: 0, background: "#0a0a1e" },
    },
      chart
        ? React.createElement("div", {
            /* 论文配色的图直接放在**白纸**上显示：所见即导出（WYSIWYG），
               也能立刻看出"导出的图长什么样"，不必先导出再确认。 */
            style: {
              width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
              background: "#ffffff", borderRadius: 6, padding: 8, overflow: "hidden",
            },
            dangerouslySetInnerHTML: { __html: chart },
          })
        : React.createElement("div", { style: { color: "#888", fontSize: 13 } }, "无有效数据点"),
    ),
  );
}
