/**
 * AiAccessPanel — 「AI 接入」面板：显示 MCP 地址、复制给 agent、接入状态。
 * 程序不做 harness/chat；这只是让外部 agent（claude/codex/dsh）连上本程序工作区的入口。
 */
import React from "react";
import FloatingDialog from "./FloatingDialog";
import type { AiStatus } from "../hooks/useAiWorkspace";

interface Props {
  mcpUrl: string;
  status: AiStatus;
  onClose: () => void;
}

export default function AiAccessPanel({ mcpUrl, status, onClose }: Props) {
  const copy = () => {
    (navigator.clipboard?.writeText(mcpUrl) ?? Promise.reject()).catch(() => {});
  };
  return React.createElement(FloatingDialog, { title: "🤖 AI 接入（inputcard-mcp）", onClose, width: 540 },
    React.createElement("div", { style: { fontSize: 12, lineHeight: 1.8 } },
      React.createElement("div", { style: { marginBottom: 10 } },
        "让外部 agent（claude / codex / dsh 等）直接**读/改本程序的当前工作区**（所有标签页）。程序本身不做 AI 聊天。"),
      React.createElement("div", { style: { marginBottom: 6 } },
        "接入状态：", React.createElement("b", { style: { color: status === "ok" ? "#2e7d32" : "#c62828" } },
          status === "ok" ? "已就绪（AI 可连接）" : "未运行（需启动 MCP over HTTP）")),
      React.createElement("div", { style: { margin: "8px 0" } },
        React.createElement("code", { style: { padding: "4px 6px", background: "var(--bg-input)", borderRadius: 4, fontSize: 12 } }, mcpUrl)),
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: copy }, "复制 MCP 地址"),
      React.createElement("div", { style: { marginTop: 12, color: "var(--text-secondary)", fontSize: 11 } },
        "在你常用的 agent 里把它填成「MCP server URL」即可连接；连上后 agent 能读取/修改本程序全部标签页内容。"),
    ),
  );
}
