/**
 * Preview3DWindow — 独立窗口宿主：读取 localStorage 数据桥 → 渲染 Preview3D
 *
 * 主窗口点「3D 预览」→ windows.ts openPreview3D() 写桥 + 开窗。
 * 本组件在本窗口启动时读取桥数据并渲染，窗口关闭时清理。
 */
import React, { useEffect, useState } from "react";
import Preview3D from "./Preview3D";
import { readPreview3DData, closeCurrentWindow, clearStlSession } from "../utils/windows";
import { appendCardText, type QuickCellResult } from "../utils/quickCell";

export default function Preview3DWindow() {
  const [data] = useState(() => readPreview3DData());
  // 快捷建栅元需在窗口内追加曲面/TR/栅元并重拉 STL（deck 由主窗口回写同步）
  const [deckCells, setDeckCells] = useState<any[]>(() => data?.cells || []);
  const [surfaces, setSurfaces] = useState(() => data?.surfaces || "");
  const [trCards, setTrCards] = useState(() => data?.trCards || "");

  // 材料改号 → 通过 storage 事件回写主窗口
  const handleMaterialChange = (cellNum: string, newMat: string) => {
    // 宿主层：先回写主窗口（emitMaterialChange），Preview3D 自身 onMaterialChange
    // 已处理窗口内视觉。主窗口通过 storage 事件收到后 patch deck。
    import("../utils/windows").then((m) => m.emitMaterialChange(cellNum, newMat));
  };

  const handleQuickCellGenerate = (result: QuickCellResult) => {
    setSurfaces((prev) => appendCardText(prev, result.surfacesText));
    setTrCards((prev) => appendCardText(prev, result.trCardsText));
    setDeckCells((prev) => [
      ...prev,
      ...result.cells.map((c) => ({ num: c.num, mat: c.mat, comment: c.comment, surfaces: c.surfaces })),
    ]);
    import("../utils/windows").then((m) => m.emitQuickCellGenerate(result));
  };

  // 独立窗口容器样式：无主界面外壳，纯预览
  const containerStyle: React.CSSProperties = {
    position: "absolute", inset: 0, display: "flex",
    background: "#000", color: "#fff",
    overflow: "hidden",
  };

  if (!data) {
    return React.createElement("div", { className: "preview3d-root", style: containerStyle },
      React.createElement("div", { style: { margin: "auto", fontSize: 14, color: "var(--text-tertiary)" } },
        "没有 3D 预览数据（请从主窗口打开）"),
    );
  }

  return React.createElement("div", { className: "preview3d-root", style: containerStyle },
    React.createElement(Preview3D, {
      cells: deckCells,
      surfaces,
      trCards,
      materials: data.materials,
      onClose: () => { clearStlSession(); closeCurrentWindow(); },
      onMaterialChange: handleMaterialChange,
      onQuickCellGenerate: handleQuickCellGenerate,
    }),
  );
}
