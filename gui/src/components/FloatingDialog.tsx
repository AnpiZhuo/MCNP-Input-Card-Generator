import React, { useRef, useState, useEffect } from "react";

/*
 * 非模态可拖动浮窗：无全屏遮罩（点击穿透到下方页面）、标题栏可拖、ESC 关闭。
 * 全部颜色走主题 CSS 变量，浅色主题可读。
 */
interface Props {
  title: string;
  onClose: () => void;
  width?: number;
  maxHeight?: string;
  zIndex?: number;
  children?: React.ReactNode;
  footer?: React.ReactNode;
}

export default function FloatingDialog({ title, onClose, width = 600, maxHeight = "85vh", zIndex = 1000, children, footer }: Props) {
  // SSR 安全：测试/服务端渲染无 window（浏览器行为不变）
  const [pos, setPos] = useState(() => (
    typeof window === "undefined"
      ? { x: 60, y: 60 }
      : { x: Math.max(10, (window.innerWidth - width) / 2), y: 60 }
  ));
  const dragRef = useRef({ active: false, dx: 0, dy: 0 });

  const onDragStart = (e: React.MouseEvent) => {
    dragRef.current = { active: true, dx: e.clientX - pos.x, dy: e.clientY - pos.y };
  };

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragRef.current.active) return;
      setPos({ x: e.clientX - dragRef.current.dx, y: e.clientY - dragRef.current.dy });
    };
    const onUp = () => { dragRef.current.active = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return React.createElement("div", {
    style: {
      position: "fixed", left: pos.x, top: pos.y,
      width, maxHeight,
      background: "var(--dialog-bg)",
      border: "1px solid var(--border-glass)",
      borderRadius: 16,
      display: "flex", flexDirection: "column",
      overflow: "hidden",
      boxShadow: "0 8px 32px rgba(0,0,0,0.35)",
      zIndex,
      pointerEvents: "auto",
      backdropFilter: "blur(16px)",
    } as React.CSSProperties,
  },
    React.createElement("div", {
      style: {
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "12px 16px", borderBottom: "1px solid var(--border-glass)",
        cursor: "move", userSelect: "none", flexShrink: 0,
      },
      onMouseDown: onDragStart,
    },
      React.createElement("span", { style: { fontSize: 13, fontWeight: 600, color: "var(--text-primary)" } }, title),
      React.createElement("button", {
        style: { background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: 16, padding: "2px 6px", borderRadius: 4 },
        onClick: onClose,
        title: "关闭 (Esc)",
      }, "✕"),
    ),
    React.createElement("div", { style: { flex: 1, overflow: "auto", padding: "16px 20px" } }, children),
    footer ? React.createElement("div", {
      style: {
        padding: "12px 16px", borderTop: "1px solid var(--border-glass)",
        display: "flex", gap: 8, justifyContent: "flex-end", flexShrink: 0,
      },
    }, footer) : null,
  );
}
