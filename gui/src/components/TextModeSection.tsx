import React from "react";

/**
 * 表单⇄文本模式切换 header 组件。
 * 纯受控组件——状态由父组件管理。
 */
interface Props {
  label: string;
  active: boolean;
  onToggle: () => void;
  onDiscard?: () => void;
  extra?: React.ReactNode;  // 标题后追加内容（如联系方式）
}

export default function TextModeSection({ label, active, onToggle, onDiscard, extra }: Props) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", flexShrink: 0 }}>
        {label}
      </span>
      {extra}
      <div style={{ flex: 1 }} />
      <button
        className={"btn btn-xs " + (active ? "btn-primary" : "btn-ghost")}
        onClick={onToggle}
        style={{ whiteSpace: "nowrap" }}
      >
        {active ? "← 回到表单" : "✎ 文本模式"}
      </button>
      {active && onDiscard && (
        <button
          className="btn btn-xs btn-ghost"
          onClick={onDiscard}
          style={{ color: "#e53935", whiteSpace: "nowrap" }}
        >
          放弃文本
        </button>
      )}
    </div>
  );
}
