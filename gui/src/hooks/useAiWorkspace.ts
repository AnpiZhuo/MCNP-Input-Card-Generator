/**
 * useAiWorkspace — 前端「AI 接入」同步 hook。
 *
 * ① 同步：当前工作区（deck）变化 → 防抖 PUT 到 /workspace；
 * ② 回显：轮询 /workspace 的 revision，若超过本地（说明是 AI 改动）→ applyAiDeck(deck) 回显。
 * ③ 状态：MCP over HTTP 是否可达。
 */
import { useEffect, useRef, useState } from "react";
import { putWorkspace, getWorkspace, aiMcpUrl, AI_HTTP_BASE } from "../utils/aiWorkspace";

export type AiStatus = "off" | "ok";

export function useAiWorkspace(deck: any, applyAiDeck: (aiDeck: any) => void) {
  const [status, setStatus] = useState<AiStatus>("off");
  const [revision, setRevision] = useState(0);
  const lastRevRef = useRef(0);
  const applyRef = useRef(applyAiDeck);
  applyRef.current = applyAiDeck;

  // ① 同步：deck 变化 → 防抖推给后端
  useEffect(() => {
    if (!deck) return;
    const t = setTimeout(() => {
      putWorkspace(deck).then((r) => {
        if (r.ok) {
          lastRevRef.current = Math.max(lastRevRef.current, r.revision);
          setRevision(r.revision);
          setStatus("ok");
        }
      });
    }, 300);
    return () => clearTimeout(t);
  }, [deck]);

  // ② 回显 + ③ 状态：轮询 /workspace
  useEffect(() => {
    const iv = setInterval(async () => {
      const ws = await getWorkspace();
      if (!ws) { setStatus("off"); return; }
      setStatus("ok");
      if (ws.revision > lastRevRef.current) {
        lastRevRef.current = ws.revision;
        setRevision(ws.revision);
        if (ws.deck) applyRef.current(ws.deck);
      }
    }, 2000);
    return () => clearInterval(iv);
  }, []);

  return { status, revision, mcpUrl: aiMcpUrl(), base: AI_HTTP_BASE };
}
