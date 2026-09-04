/**
 * aiWorkspace — 前端「AI 接入」通道（纯函数，无 React 依赖）。
 *
 * 前后端协同：程序把「当前工作区」（所有标签页合成的 deck）推给 MCP over HTTP 的 /workspace，
 * 外部 agent（claude/codex/dsh）经 /mcp 读/改这份工作区；AI 改后前端轮询拿到 revision→回显。
 * MCP over HTTP 由 inputcard-mcp 的 --mcp-http 提供（本机环回端口 8100）。
 */
export const AI_HTTP_BASE = "http://127.0.0.1:8100";

/** MCP 协议端点：AI 客户端把这个作为 MCP server URL */
export const aiMcpUrl = (): string => AI_HTTP_BASE + "/mcp";
/** 前端同步「当前工作区」的端点 */
export const aiWorkspaceUrl = (): string => AI_HTTP_BASE + "/workspace";

export interface WorkspacePutResult { ok: boolean; revision: number }

/** 把当前工作区（前端 deck 形态）推给后端 /workspace，作为 AI 读写的权威工作区 */
export async function putWorkspace(deck: unknown): Promise<WorkspacePutResult> {
  try {
    const r = await fetch(aiWorkspaceUrl(), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deck }),
      signal: AbortSignal.timeout(8000),
    });
    const j = await r.json();
    return { ok: r.ok, revision: Number(j?.revision ?? 0) };
  } catch {
    return { ok: false, revision: 0 };
  }
}

/** 读取当前工作区（revision + 前端 deck 形态）；AI 未改动时 revision 不变 */
export async function getWorkspace(): Promise<{ revision: number; deck?: any } | null> {
  try {
    const r = await fetch(aiWorkspaceUrl(), { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}
