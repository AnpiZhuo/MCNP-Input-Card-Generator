/**
 * ExportButton / useFigureExport — 各窗口接出图的**唯一方式**（一行接线）。
 *
 * 用法（窗口里只写这一行）：
 * ```tsx
 * <ExportButton
 *   label="3D 预览图"
 *   build={() => ({
 *     view: "3D几何",
 *     nameParts: [tallyNumber, resolution],
 *     // ⚠️ 3D 视图一律用 renderTransparentNow()：透明底出图必须在这一帧里
 *     //    关掉场景底色并按 alpha=0 清屏（见 export/captureFrame）
 *     raster: build3dSpec({ canvas: ctrl.renderTransparentNow(), title: "3D 几何", legend }),
 *   })}
 * />
 * ```
 *
 * 为什么把"点按钮"和"取数据"分开：取数据（同步重画一帧、读图例）必须发生在**点击那一刻**，
 * 不能在渲染期算好（那时画布可能还没画、视角也已经变了）。所以这里收的是**构建函数**。
 */
import React, { useCallback, useState } from "react";
import { exportFigure, exportMessage, type ExportFigureRequest, type ExportResult } from "./exportFigure";

export interface UseFigureExportResult {
  /** 正在导出（用来禁用按钮、防重复点击） */
  busy: boolean;
  /** 执行导出（供自定义按钮位置调用） */
  run: () => Promise<ExportResult>;
}

/**
 * @param build 点击那一刻构建导出请求（**必须同步**取画布；见 `captureFrame` 的模块说明）
 */
export function useFigureExport(build: () => ExportFigureRequest, label?: string): UseFigureExportResult {
  const [busy, setBusy] = useState(false);
  const run = useCallback(async () => {
    if (busy) return { status: "error", message: "正在导出…" } as ExportResult;
    setBusy(true);
    try {
      const req = build();
      const r = await exportFigure(req);
      const msg = exportMessage(r, label ?? req.view);
      if (msg) {
        try { alert(msg); } catch { /* 非浏览器环境 */ }
      }
      return r;
    } catch (e: any) {
      const msg = `❌ 导出失败：${e?.message || e}`;
      try { alert(msg); } catch { /* 非浏览器环境 */ }
      return { status: "error", message: msg } as ExportResult;
    } finally {
      setBusy(false);
    }
  }, [build, busy, label]);
  return { busy, run };
}

export interface ExportButtonProps {
  build: () => ExportFigureRequest;
  /** 提示里显示的图名，缺省用请求里的 view */
  label?: string;
  /** 标题栏用的紧凑样式（默认） */
  compact?: boolean;
  title?: string;
}

/**
 * 标题栏「导出」按钮。**不需要用户选任何东西**：
 * 点一下 → 出一张 **2× PNG**（透明底；整幅颜色填充的图铺白底），一律论文配色。
 */
export function ExportButton({ build, label, compact = true, title }: ExportButtonProps) {
  const [busy, setBusy] = useState(false);
  const onClick = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      const req = build();
      const r = await exportFigure(req);
      const msg = exportMessage(r, label ?? req.view);
      if (msg) {
        try { alert(msg); } catch { /* 非浏览器环境 */ }
      }
    } catch (e: any) {
      try { alert(`❌ 导出失败：${e?.message || e}`); } catch { /* 非浏览器环境 */ }
    } finally {
      setBusy(false);
    }
  }, [build, busy, label]);

  return React.createElement(
    "button",
    {
      className: compact ? "btn btn-ghost btn-xs" : "btn btn-primary btn-sm",
      onClick,
      disabled: busy,
      title: title ?? "导出当前视图为 2× PNG（透明底；论文配色）",
      style: compact ? { fontSize: 12, whiteSpace: "nowrap" } : undefined,
    },
    busy ? "导出中…" : "⬇ 导出",
  );
}
