/**
 * useAiWorkspace — 前端「AI 接入」同步 hook。
 *
 * ① 同步：当前工作区（deck）变化 → 防抖 PUT 到 /workspace；
 * ② 回显：轮询 /workspace 的 revision，若超过本地（说明是 AI 改动）→ applyAiDeck(deck) 回显。
 * ③ 状态：MCP over HTTP 是否可达。
 *
 * ## 两条不变量（2026-09-17 实证的"改动变回初始状态"就是踩了它们）
 *
 * 1. **只回显自己写上去的工作区**。后端把每次 PUT 的 `client_id` 记成 `writer` 并在 GET 带回；
 *    writer 不是本实例时**一律不采纳**。否则两个实例（打包版 + dev 版，或残留旧实例）共用
 *    8100 时，A 的工作区会把 B 的界面整份覆盖 —— B 上表现为"我改的全没了"，且两边都不报错。
 * 2. **回显按最新 deck 合并**，不用渲染时闭包里的旧快照。`applyDeckRef` 由调用方以 ref 形式
 *    传入最新 deck（`App.tsx` 的 `deckRef`），避免"回显时把已删除/旧内容复活"。
 */
import { useEffect, useRef, useState } from "react";
import { putWorkspace, getWorkspace, aiMcpUrl, AI_HTTP_BASE, CLIENT_ID } from "../utils/aiWorkspace";

export type AiStatus = "off" | "ok";

/** 回显时用于合并「最新本地 deck」的读取口（ref，避免闭包拿到渲染时快照） */
export interface AiWorkspaceOpts {
  /** 读最新 deck（每次回显时现取，不用闭包快照） */
  getLatestDeck: () => any;
}

export function useAiWorkspace(deck: any, applyAiDeck: (aiDeck: any) => void, opts?: AiWorkspaceOpts) {
  const [status, setStatus] = useState<AiStatus>("off");
  const [revision, setRevision] = useState(0);
  /** 已知 revision 的水位线（PUT 成功与 GET 采纳都会抬它；只有 GET > 它才回显） */
  const lastRevRef = useRef(0);
  /** 后端最后一次 PUT 是否由本实例发出（多实例隔离的开关） */
  const ownedRef = useRef(true);
  const applyRef = useRef(applyAiDeck);
  applyRef.current = applyAiDeck;
  const optsRef = useRef(opts);
  optsRef.current = opts;

  // ① 同步：deck 变化 → 防抖推给后端（连同本实例身份，供后端记 writer）
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
      // 多实例隔离：工作区不是自己写上去的 → 记水位线但**不采纳**（否则被别的实例覆盖）
      if (ws.writer && ws.writer !== CLIENT_ID) {
        ownedRef.current = false;
        lastRevRef.current = Math.max(lastRevRef.current, ws.revision);
        return;
      }
      ownedRef.current = true;
      if (ws.revision > lastRevRef.current) {
        lastRevRef.current = ws.revision;
        setRevision(ws.revision);
        if (ws.deck) {
          // 按最新 deck 合并（getLatestDeck 现取，避免闭包旧快照复活旧内容）
          const latest = optsRef.current?.getLatestDeck?.();
          applyRef.current(latest ? { ...latest, ...ws.deck } : ws.deck);
        }
      }
    }, 2000);
    return () => clearInterval(iv);
  }, []);

  return { status, revision, mcpUrl: aiMcpUrl(), base: AI_HTTP_BASE, owned: ownedRef };
}
