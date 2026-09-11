// Python backend bridge via Tauri or HTTP
import { apiUrl } from "./api";

let pythonProcess: any = null;
let mcpProcess: any = null;
let closeUnlisten: (() => void) | null = null;

/** 启动 AI 接入通道：MCP over HTTP（inputcard-mcp --mcp-http → 本机 8100 /mcp + /workspace） */
async function startMcpHttp(): Promise<void> {
  if (mcpProcess) return;
  try {
    const { Command } = await import("@tauri-apps/api/shell");
    mcpProcess = Command.sidecar("python", ["--mcp-http"]);
    mcpProcess.stdout?.on("data", (line: string) => console.log("[MCP HTTP]", line));
    mcpProcess.stderr?.on("data", (line: string) => console.error("[MCP HTTP ERROR]", line));
    await mcpProcess.spawn();
    console.log("MCP over HTTP (AI access) started on 8100");
  } catch (e) {
    console.warn("MCP over HTTP not available (browser mode?)", e);
  }
}

/** 启动 Python 后端（Tauri sidecar 拉起 api_server → 常驻 5001）；浏览器模式自动失效 */
export async function startPythonBackend(): Promise<void> {
  // 无论 5001 是否已在跑，都要保证 AI 接入通道（8100）
  await startMcpHttp();
  if (pythonProcess) return;
  try {
    // 5001 已有后端在跑则不再拉起（避免双实例 / 重复绑定）
    try {
      const r = await fetch(apiUrl("/api/xsdir-check"), { signal: AbortSignal.timeout(2000) });
      if (r.ok) { console.log("Backend already running on 5001, skip spawn"); return; }
    } catch { /* 5001 无响应 → 需要拉起 */ }
    const { Command } = await import("@tauri-apps/api/shell");
    pythonProcess = Command.sidecar("python", [
      "-u", "backend/mcnp_bridge.py"
    ]);
    pythonProcess.stdout.on("data", (line: string) => {
      console.log("[Python]", line);
    });
    pythonProcess.stderr.on("data", (line: string) => {
      console.error("[Python ERROR]", line);
    });
    await pythonProcess.spawn();
    console.log("Python backend started");
    // 窗口关闭时一起关后端
    try {
      const { appWindow } = await import("@tauri-apps/api/window");
      let closing = false;               // 防重入：第二次 close-requested 不再拦截
      closeUnlisten = await appWindow.onCloseRequested(async (event) => {
        if (closing) return;             // 已清理完毕，放行关闭
        closing = true;
        event.preventDefault();          // 拦下第一次，先杀后端再关窗
        await stopPythonBackend();
        // 用自定义命令关窗（Rust window.close()），不用 appWindow.close()
        // —— 后者走 plugin:window|close，缺 window-close feature 时会失败导致窗口卡住
        const { invoke } = await import("@tauri-apps/api/tauri");
        try { await invoke("close_window"); } catch { /* 兜底：用户可再次关闭 */ }
      });
    } catch { /* 非 Tauri 环境无 close 事件 */ }
  } catch (e) {
    console.warn("Python backend not available (running in browser mode)");
  }
}

/** 停止 Python 后端（关闭窗口 / App 卸载时调用） */
export async function stopPythonBackend(): Promise<void> {
  if (closeUnlisten) { closeUnlisten(); closeUnlisten = null; }
  if (mcpProcess) { try { mcpProcess.kill(); } catch { /* 已退出 */ } mcpProcess = null; }
  if (pythonProcess) { try { pythonProcess.kill(); } catch { /* 已退出 */ } pythonProcess = null; }
}
