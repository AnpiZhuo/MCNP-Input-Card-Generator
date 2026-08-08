/**
 * CrossSectionWindow — 独立窗口宿主：读取 localStorage 数据桥 → 渲染 CrossSectionView
 *
 * 3D 窗口点「截面」→ windows.ts openCrossSection() 写桥 + 开窗。
 * 步进（onPlaneChange）重新请求后端 /api/cross-section，更新本地 slices。
 */
import React, { useState } from "react";
import CrossSectionView from "./CrossSectionView";
import { readCrossSectionData, closeCurrentWindow } from "../utils/windows";

export default function CrossSectionWindow() {
  const [init] = useState(() => readCrossSectionData());
  const [slices, setSlices] = useState<any[] | null>(init?.slices || null);
  const [plane, setPlane] = useState(init?.plane || { A: 0, B: 0, C: 1, D: 0 });

  // 步进：重新请求后端（从 STL 切，只切勾选+非真空栅元）
  const fetchSlices = (newPlane: { A: number; B: number; C: number; D: number }) => {
    setPlane(newPlane);
    if (!init) return;
    const cellNums = init.cellNums && init.cellNums.length > 0
      ? init.cellNums
      : (init.cells || [])
          .filter((c: any) => String(c.mat).split(" ")[0] !== "0")
          .map((c: any) => parseInt(c.num) || 0);
    fetch("http://localhost:5001/api/cross-section", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cellNums: cellNums, plane: newPlane }),
    }).then((r) => r.json()).then((j) => {
      if (j.slices && j.slices.length > 0) setSlices(j.slices);
      else setSlices(null);
    }).catch(() => {});
  };

  const containerStyle: React.CSSProperties = {
    position: "absolute", inset: 0, display: "flex",
    background: "#0a0a1e", color: "#fff",
  };

  if (!init || !slices) {
    return React.createElement("div", { style: containerStyle },
      React.createElement("div", { style: { margin: "auto", fontSize: 14, color: "#888" } },
        init ? "截面无结果" : "没有截面数据（请从 3D 预览窗口打开）"),
    );
  }

  return React.createElement("div", { style: containerStyle },
    React.createElement(CrossSectionView, {
      slices: slices,
      plane: plane,
      onClose: () => { closeCurrentWindow(); },
      onPlaneChange: fetchSlices,
      cellComments: (init.cells || []).map((c) => ({ number: parseInt(c.num) || 0, comment: c.comment })),
    }),
  );
}
