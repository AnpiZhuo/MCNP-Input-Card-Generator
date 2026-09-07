import React from "react";
import pkg from "../../package.json";
import { useAppScale } from "../utils/appScale";

interface Props {
  active: string;
  onSelect: (key: string) => void;
  tabs: { key: string; label: string }[];
  theme: string;
  onThemeChange: (t: string) => void;
  onImport?: () => void;
}

const THEMES = [
  { key: "dark", icon: "🌙", label: "夜之城" },
  { key: "light", icon: "☀", label: "青空" },
  { key: "dopamine", icon: "🌈", label: "多巴胺" },
  { key: "traditional", icon: "🌿", label: "护眼" },
];
const ICONS: Record<string,string> = { basic: "⚙", geo: "◇", mat: "⚗", src: "◎", tally: "≡", adv: "⚒", output: "▤" };

export default function Sidebar({ active, onSelect, tabs, theme, onThemeChange, onImport }: Props) {
  const [expanded, setExpanded] = React.useState(false);
  const [tip, setTip] = React.useState<{ x: number; y: number } | null>(null);
  const timer = React.useRef<number | null>(null);
  // 主窗口等比缩放时，getBoundingClientRect 返回「缩放后」坐标，而浮窗走缩放后的坐标系，
  // 需除以 scale 转回设计坐标才能与按钮位置对齐（子窗口不缩放，scale=1，行为不变）。
  const scale = useAppScale();
  const cycleTheme = () => { const idx = THEMES.findIndex(t => t.key === theme); onThemeChange(THEMES[(idx + 1) % THEMES.length].key); };
  const cur = THEMES.find(t => t.key === theme) || THEMES[0];
  return (
    <nav className="sidebar" style={{ width: expanded ? 96 : 52 }}
      onMouseEnter={() => { if (timer.current) clearTimeout(timer.current); setExpanded(true); }}
      onMouseLeave={() => { timer.current = window.setTimeout(() => setExpanded(false), 180); }}>
      <div style={{ display: "flex", alignItems: "center", margin: "0 0 8px 6px", overflow: "hidden" }}>
        <div className="sidebar-avatar" style={{ flexShrink: 0, overflow: "hidden" }}>
          <img src="/app_icon.png" alt="" style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" }} />
        </div>
        {/* 悬停展开时在应用图标右侧显示版本号（用户需求；版本随 package.json 单一来源） */}
        <span
          className="sidebar-label"
          style={{ opacity: expanded ? 1 : 0, marginLeft: 8, fontSize: 10, color: "var(--text-tertiary)", whiteSpace: "nowrap" }}
          title="程序版本号"
        >
          v{pkg.version}
        </span>
      </div>
      {tabs.map(tab => (
        <button key={tab.key} className={"sidebar-btn" + (active === tab.key ? " active" : "")}
          onClick={() => onSelect(tab.key)} title={tab.label}>
          <span className="sidebar-icon">{ICONS[tab.key] || "?"}</span>
          <span className="sidebar-label" style={{ opacity: expanded ? 1 : 0 }}>{tab.label}</span>
        </button>
      ))}
      <div style={{ marginTop: "auto" }}>
        <button className="sidebar-btn" onClick={onImport}
          onMouseEnter={(e) => { const r = e.currentTarget.getBoundingClientRect(); setTip({ x: (r.right + 10) / scale, y: (r.top + r.height / 2) / scale }); }}
          onMouseLeave={() => setTip(null)}>
          <span className="sidebar-icon">📂</span>
          <span className="sidebar-label" style={{ opacity: expanded ? 1 : 0 }}>导入</span>
        </button>
        {tip && (
          <div style={{ position: "fixed", left: tip.x, top: tip.y, transform: "translateY(-50%)", zIndex: 1000,
            background: "var(--bg-surface)", border: "1px solid var(--border-glass)", color: "var(--accent-glow)",
            fontSize: 11, padding: "4px 9px", borderRadius: 6, whiteSpace: "nowrap",
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)", pointerEvents: "none" }}>
            点击选择 INP 文件，或直接拖入窗口即可
          </div>
        )}
        <button className="sidebar-btn" onClick={cycleTheme} title={cur.label}>
          <span className="sidebar-icon">{cur.icon}</span>
          <span className="sidebar-label" style={{ opacity: expanded ? 1 : 0 }}>{cur.label}</span>
        </button>
      </div>
    </nav>
  );
}
