// Python backend bridge via Tauri or HTTP
import { apiUrl } from "./api";

let pythonProcess: any = null;
let mcpProcess: any = null;
let closeUnlisten: (() => void) | null = null;

/** MCP over HTTP 工作区端口（inputcard_mcp.main 默认 8100） */
const MCP_HTTP_PORT = 8100;

/**
 * 本机环回端口是否已有服务在跑。
 *
 * 与 backend.ts 里 5001 的「先探测再拉起」同一套路（首次尝试 mcp 时实测有坑：
 * 残留旧进程占着 8100 ⇒ sidecar spawn 出来 bind 失败即退，前端却以为自己在用新实例，
 * 实际读写的是**旧进程里的旧工作区** ⇒ 界面莫名其妙回弹且无任何报错）。
 *
 * 走 CSP 允许的 `http://127.0.0.1:<port>/`（Tauri 生产环境 CSP 里没有裸 TCP 的余地），
 * `cache: "no-store"` + 短超时：只关心「连得上 / 连不上」，不看内容。
 * 任何响应（含 404/405）都算「有服务在监听」。
 */
export async function isLocalPortServing(port: number): Promise<boolean> {
  try {
    await fetch(`http://127.0.0.1:${port}/`, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    return true;
  } catch {
    return false;
  }
}

/* ── 后端启动诊断 ─────────────────────────────────────────────
 *
 * 为什么要有它：后端**只由前端 JS 拉起**（`src-tauri/src/main.rs` 里没有任何 spawn），
 * 而失败原来被 catch 吞掉、只留一句 `console.warn`。于是用户看到的只有顶栏
 * "后端不可用"四个字，没有任何线索——2026-09-20 排查"用户机器上 python.exe 一闪就没"
 * 时，就是卡在这里反复要远程猜测。
 *
 * 现在把三样东西留住并显示出来：**归因 + 子进程退出码 + 子进程输出尾巴**。
 * 其中输出尾巴最关键：sidecar 的 PyInstaller 引导错误（`Failed to load Python DLL …`）
 * 只在 stderr 里闪现 263 ms，肉眼看不到，但这里能原样留下。
 */

export type BackendDiagState = "unknown" | "skipped" | "started" | "exited" | "spawn-failed";

export interface BackendDiag {
  state: BackendDiagState;
  /** 中文归因，直接显示给用户 */
  reason: string;
  exitCode?: number | null;
  /** 子进程 stdout/stderr 尾巴 */
  log?: string;
}

let diag: BackendDiag = { state: "unknown", reason: "" };
let onDiagChange: ((d: BackendDiag) => void) | null = null;

function setDiag(next: BackendDiag): void {
  diag = next;
  try { onDiagChange?.(next); } catch { /* 回调不该影响启动流程 */ }
}

/** 当前诊断（App 在"后端不可用"时取它显示原因） */
export function backendDiagnostics(): BackendDiag {
  return diag;
}

/**
 * 由退出码 + 子进程输出判定"为什么起不来"（纯函数，可单测）。
 *
 * 判据顺序：**先看输出文本**（PyInstaller 的引导错误是自解释的、且与退出码无关），
 * 再看退出码。退出码同时接受无符号与有符号写法（Node 在不同路径上给的形式不同）。
 */
export function classifySidecarFailure(exitCode: number | null | undefined, log: string): string {
  const t = log || "";
  if (/Failed to load Python DLL/i.test(t)) {
    return "python.exe 载入失败：同目录的 _internal 缺失或不完整，或其中的 dll 被杀软清理。"
         + "（把交付目录里的 python.exe、_internal 与主程序一起重新完整复制；"
         + "也可双击同目录的 自检.bat 一次确认）";
  }
  if (/Failed to execute script/i.test(t)) {
    return "后端脚本启动时抛异常（打包漏了模块或归档损坏）：请把本提示与下面的输出一起反馈";
  }
  if (/No module named/i.test(t)) {
    return "后端缺少模块（打包版特有）：请把本提示与下面的输出一起反馈";
  }
  const code = exitCode ?? null;
  // 0xC0000135 = 找不到 DLL；0xC000007B = 映像无效（文件被截断/篡改）
  const KNOWN: Record<number, string> = {
    3221225781: "缺少系统 DLL（0xC0000135）：_internal 不完整或被杀软清理",
    [-1073741515]: "缺少系统 DLL（0xC0000135）：_internal 不完整或被杀软清理",
    3221225595: "映像无效（0xC000007B）：python.exe 或依赖 DLL 被截断/篡改",
    [-1073741701]: "映像无效（0xC000007B）：python.exe 或依赖 DLL 被截断/篡改",
  };
  if (code !== null && KNOWN[code]) return KNOWN[code];
  if (code !== null) return `后端进程启动后立即退出（退出码 ${code}，多半是包不完整或被杀软拦截）`;
  return "后端进程已退出（未拿到退出码）";
}

/** 一句话总结，给界面 title / alert 用。 */
export function describeBackendFailure(): string {
  const d = backendDiagnostics();
  const parts: string[] = [d.reason || "后端未就绪"];
  if (d.exitCode != null) parts.push(`子进程退出码：${d.exitCode}`);
  if (d.log) parts.push(`子进程输出：\n${d.log}`);
  parts.push("可双击程序目录里的 自检.bat 做一次环境自检（它会给出 [RESULT] 结论）。");
  return parts.join("\n");
}

/** 只保留最后 N 行输出，避免把整段 stdout 挂在 tooltip 上。 */
function makeTail(maxLines = 12) {
  const lines: string[] = [];
  return {
    push(chunk: string) {
      for (const l of String(chunk).split(/\r?\n/)) {
        if (l.trim()) lines.push(l);
      }
      if (lines.length > maxLines) lines.splice(0, lines.length - maxLines);
    },
    text() { return lines.join("\n"); },
  };
}

/** 启动 AI 接入通道：MCP over HTTP（inputcard-mcp --mcp-http → 本机 8100 /mcp + /workspace） */
async function startMcpHttp(): Promise<void> {
  if (mcpProcess) return;
  // 8100 已有实例在跑 → 复用，不再拉起（避免双实例：新进程 bind 失败静默退出，
  // 前端连到旧进程的旧工作区，回显把界面改回旧状态且查不出原因）
  if (await isLocalPortServing(MCP_HTTP_PORT)) {
    console.log(`MCP over HTTP already running on ${MCP_HTTP_PORT}, skip spawn (reuse)`);
    return;
  }
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

/**
 * 启动 Python 后端（Tauri sidecar 拉起 api_server → 常驻 5001）；浏览器模式自动失效。
 *
 * `onDiag` 在每次诊断变化时回调：进程**秒退/拉不起来**时立刻把原因交给界面，
 * 不必等 90×2s 的轮询超时才让用户看到一句"后端不可用"。
 */
export async function startPythonBackend(onDiag?: (d: BackendDiag) => void): Promise<void> {
  onDiagChange = onDiag ?? null;
  // 无论 5001 是否已在跑，都要保证 AI 接入通道（8100）
  await startMcpHttp();
  if (pythonProcess) return;
  try {
    // 5001 已有后端在跑则不再拉起（避免双实例 / 重复绑定）
    try {
      const r = await fetch(apiUrl("/api/xsdir-check"), { signal: AbortSignal.timeout(2000) });
      if (r.ok) {
        setDiag({ state: "skipped", reason: "5001 上已有后端在跑，复用（未重复拉起）" });
        console.log("Backend already running on 5001, skip spawn");
        return;
      }
    } catch { /* 5001 无响应 → 需要拉起 */ }
    const { Command } = await import("@tauri-apps/api/shell");
    pythonProcess = Command.sidecar("python", [
      "-u", "backend/mcnp_bridge.py"
    ]);
    const tail = makeTail();
    pythonProcess.stdout.on("data", (line: string) => {
      tail.push(line);
      console.log("[Python]", line);
    });
    pythonProcess.stderr.on("data", (line: string) => {
      tail.push(line);
      console.error("[Python ERROR]", line);
    });
    // 秒退就发生在这里 —— 这正是"后端没拉起来"的现场，必须留下原因
    pythonProcess.on("close", (payload: { code?: number | null } | undefined) => {
      const code = payload?.code ?? null;
      const text = tail.text();
      setDiag({
        state: "exited",
        reason: classifySidecarFailure(code, text),
        exitCode: code,
        log: text,
      });
      console.error("[backend] sidecar 进程退出：", diag.reason, "\n", text);
    });
    pythonProcess.on("error", (e: unknown) => {
      setDiag({ state: "spawn-failed", reason: `sidecar 进程出错：${String(e)}`, log: tail.text() });
    });
    await pythonProcess.spawn();
    setDiag({ state: "started", reason: "已拉起后端，正在等它绑定 5001" });
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
    // 原来这里只有一句 console.warn（"running in browser mode"）——把真实原因也记下来，
    // 否则"后端不可用"就永远是四个字。
    setDiag({
      state: "spawn-failed",
      reason: `无法拉起 sidecar（python.exe）：${e instanceof Error ? e.message : String(e)}。`
            + "若为 Tauri 环境，请确认程序目录里 python.exe 与 _internal 都在。",
    });
    console.warn("Python backend not available (running in browser mode)", e);
  }
}

/** 停止 Python 后端（关闭窗口 / App 卸载时调用） */
export async function stopPythonBackend(): Promise<void> {
  if (closeUnlisten) { closeUnlisten(); closeUnlisten = null; }
  if (mcpProcess) { try { mcpProcess.kill(); } catch { /* 已退出 */ } mcpProcess = null; }
  if (pythonProcess) { try { pythonProcess.kill(); } catch { /* 已退出 */ } pythonProcess = null; }
}
