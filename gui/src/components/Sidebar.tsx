import React from "react";

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
  const cycleTheme = () => { const idx = THEMES.findIndex(t => t.key === theme); onThemeChange(THEMES[(idx + 1) % THEMES.length].key); };
  const cur = THEMES.find(t => t.key === theme) || THEMES[0];
  return (
    <nav className="sidebar" style={{ width: expanded ? 96 : 52 }}
      onMouseEnter={() => { if (timer.current) clearTimeout(timer.current); setExpanded(true); }}
      onMouseLeave={() => { timer.current = window.setTimeout(() => setExpanded(false), 180); }}>
      <div className="sidebar-avatar" style={{ margin: "0 0 8px 6px", overflow: "hidden" }}>
        <img src="/app_icon.png" alt="" style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" }} />
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
          onMouseEnter={(e) => { const r = e.currentTarget.getBoundingClientRect(); setTip({ x: r.right + 10, y: r.top + r.height / 2 }); }}
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
