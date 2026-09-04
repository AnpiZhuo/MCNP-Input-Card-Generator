/**
 * AiAccessPanel — 「AI 接入」面板。
 * 「复制」复制的是一段**给 AI 的自配置提示词**：用户把它粘贴给 AI（如 Claude Code），
 * AI 读懂后自己把 MCP server 配置好并能读写本程序当前工作区。手动填 URL 亦给出。
 */
import React from "react";
import FloatingDialog from "./FloatingDialog";
import type { AiStatus } from "../hooks/useAiWorkspace";

interface Props {
  mcpUrl: string;
  status: AiStatus;
  onClose: () => void;
}

/** 给 AI 的一段自配置提示词（用户粘贴到 AI 对话，AI 自己完成 MCP 配置） */
const AI_SETUP_PROMPT =
  `请为我在支持 MCP 的客户端里添加/配置下面这个服务器，让我能读写这台程序（MCNP 输入卡生成器）当前打开的全部标签页内容：\n` +
  `- 服务器名：inputcard-mcp\n` +
  `- 类型：http\n` +
  `- URL：http://127.0.0.1:8100/mcp\n` +
  `\n` +
  `请用你支持的方式（如 "添加 MCP server / mcpServers 配置入口"）把它加上；如无法自动改配置，请把上面的 http URL 明确告诉我，并提醒我手动填入。加好后我即可调用 read_document / list_section / patch_section / add_shape / validate_document / generate_document 等工具读写本程序工作区。`;

export default function AiAccessPanel({ mcpUrl, status, onClose }: Props) {
  const copyPrompt = () => {
    (navigator.clipboard?.writeText(AI_SETUP_PROMPT) ?? Promise.reject()).catch(() => {});
  };
  const copyUrl = () => {
    (navigator.clipboard?.writeText(mcpUrl) ?? Promise.reject()).catch(() => {});
  };
  return React.createElement(FloatingDialog, { title: "🤖 AI 接入（inputcard-mcp）", onClose, width: 560 },
    React.createElement("div", { style: { fontSize: 12, lineHeight: 1.8 } },
      React.createElement("div", { style: { marginBottom: 10 } },
        "让外部 agent（claude / codex / dsh 等）直接读/改本程序当前全部标签页；程序不做 AI 聊天。"),
      React.createElement("div", { style: { marginBottom: 6 } },
        "接入状态：", React.createElement("b", { style: { color: status === "ok" ? "#2e7d32" : "#c62828" } },
          status === "ok" ? "已就绪（AI 可连接）" : "未运行（需启动 MCP over HTTP）")),
      React.createElement("div", { style: { margin: "8px 0" } },
        React.createElement("code", { style: { padding: "4px 6px", background: "var(--bg-input)", borderRadius: 4, fontSize: 12 } }, mcpUrl)),
      React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap" } },
        React.createElement("button", { className: "btn btn-primary btn-sm", onClick: copyPrompt },
          "📋 复制「给 AI 的自配置提示词」"),
        React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: copyUrl }, "仅复制 URL"),
      ),
      React.createElement("div", { style: { marginTop: 12, color: "var(--text-secondary)", fontSize: 11 } },
        "用法：把上一步复制的**提示词**粘贴到你的 AI（如 Claude Code）那里，AI 会自己给 MCP 服务器做好配置；" +
        "若它无法自动改配置，会把这行 URL 告诉你，你再手动填入即可。"),
    ),
  );
}
