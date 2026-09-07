/**
 * 前端「按窗口等比缩放」基础设施（appScale）。
 *
 * 背景：程序采用固定像素设计（主窗口 1200×800），在屏幕缩放（DPI）较高或分辨率较低的机器上，
 * 浏览器实际可用的 CSS 视口会比内容需要的尺寸小，导致内容过大、右上角按钮 / 最小化最大化关闭按钮被裁切。
 *
 * 方案：把所有窗口内容整体按比例缩放（scale ≤ 1，仅缩小），使内容恰好适配可用视口。
 * - CSS：在根容器 #root 上应用 `zoom: var(--app-scale, 1)`，并用
 *   `width: calc(100vw / var(--app-scale))` / `height: calc(100vh / var(--app-scale))`
 *   抵消 zoom 对布局尺寸的影响，保证容器始终铺满窗口（详见 global.css）。
 * - JS：每个窗口由 AppScaleProvider（按窗口传入自己的 designWidth/designHeight）设置 --app-scale
 *   并提供缩放比；组件用 useAppScale() 读取，把「从 window.innerWidth / clientX /
 *   getBoundingClientRect 等真实像素值换算出来的坐标」除以缩放比，与 CSS 缩放后的坐标系保持一致。
 * - Portal 弹窗：挂到 #app-portal-root（缩放容器内部）才能随缩放；见 getAppPortalRoot()。
 */
import React, { createContext, useContext, useState, useLayoutEffect, ReactNode } from "react";

/** 设计基准尺寸（与 .app-shell 在 1200×800 窗口下的视觉一致） */
export const DESIGN_WIDTH = 1200;
export const DESIGN_HEIGHT = 800;

/** 缩放下限，避免极端小视口下内容小到不可用 */
const MIN_SCALE = 0.3;

/** 计算当前缩放比：取「窗口/设计」的较小值（等比、只缩小），并钳制上下限。 */
export function computeAppScale(designW = DESIGN_WIDTH, designH = DESIGN_HEIGHT): number {
  const w = window.innerWidth;
  const h = window.innerHeight;
  if (!w || !h) return 1;
  return Math.max(MIN_SCALE, Math.min(1, w / designW, h / designH));
}

const AppScaleContext = createContext<number>(1);

/** 读取当前缩放比（无 Provider 时返回 1，即不缩放）。 */
export function useAppScale(): number {
  return useContext(AppScaleContext);
}

/**
 * 缩放容器内的 portal 根节点。用 createPortal 挂到 body 的弹窗不会随 .app-shell 缩放，
 * 改为挂到 #app-portal-root（.app-shell 内部，随 zoom 缩放）即可让弹窗也等比缩放。
 * 找不到时回退 document.body（保证不报错）。
 */
export function getAppPortalRoot(): HTMLElement {
  return (document.getElementById("app-portal-root") as HTMLElement) || document.body;
}

/**
 * 每个窗口的缩放 Provider：按该窗口的 designWidth/designHeight 计算缩放比，写入 CSS 变量
 * --app-scale（供 #root 的 zoom 使用），并通过 context 向下传递缩放比，供需要换算坐标的组件使用。
 * 主窗口默认 1200×800；3D 预览/结果/径迹 1300×820；截面 1000×700（见 App.tsx WindowRouter）。
 */
export default function AppScaleProvider({ children, designWidth = DESIGN_WIDTH, designHeight = DESIGN_HEIGHT }: { children: ReactNode; designWidth?: number; designHeight?: number }) {
  const [scale, setScale] = useState<number>(() =>
    typeof window === "undefined" ? 1 : computeAppScale(designWidth, designHeight)
  );

  useLayoutEffect(() => {
    let raf = 0;
    const apply = () => {
      const s = computeAppScale(designWidth, designHeight);
      document.documentElement.style.setProperty("--app-scale", String(s));
      setScale(s);
    };
    apply();
    const onResize = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(apply);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(raf);
    };
  }, [designWidth, designHeight]);

  return <AppScaleContext.Provider value={scale}>{children}</AppScaleContext.Provider>;
}
