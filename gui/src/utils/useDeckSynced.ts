/**
 * useDeckSynced — 页签「deck 单一权威 ↔ 本地工作副本」的共享深模块。
 *
 * 收敛多页签各自手写的 ad-hoc 守卫（lastPushRef/lastPullRef/JSON 比较 + 双向 effect）：
 * 一个 hook 同时负责：
 *   ① 本地值变化 → 写回 deck（deck 是权威存储）
 *   ② deck 被外部替换（AI 回显 / 导入 / 恢复 / 其它写点）→ 本地跟随
 * 用 lastPushed 串去重，避免「本地 push → deck 变化 → effect 又拉回」的死循环。
 *
 * 通用性：值可为数组或字符串（如 cells 数组 / surfaces 文本）；norm/denorm（fromDeck/toDeck）
 * 由调用方给出（例如 cells 经 cellBridge 在 LocalCellRow ↔ 后端 CellRow 间转换；tally 的稳定 id 只在本地）。
 */
import { useState, useRef, useCallback, useEffect } from "react";

export interface UseDeckSyncedOpts<S, D> {
  deck: Record<string, any>;
  patch: (p: Record<string, any>) => void;
  /** deck 上的键（materials/tallies/cells/surfaces/tr_cards…） */
  key: string;
  /** deck 值 → 本地工作副本 */
  fromDeck: (deckVal: D) => S;
  /** 本地工作副本 → deck 值 */
  toDeck: (local: S) => D;
  /** 深度相等判定（默认 JSON 序列化比较） */
  eq?: (a: D, b: D) => boolean;
}

const json = (v: unknown): string => {
  try { return JSON.stringify(v ?? null); } catch { return String(v); }
};

export function useDeckSynced<S, D>(opts: UseDeckSyncedOpts<S, D>): [S, (next: S | ((prev: S) => S)) => void] {
  const { deck, patch, key } = opts;
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const [local, setLocalState] = useState<S>(() => opts.fromDeck(deck[key] as D));
  const localRef = useRef(local);
  const lastPushedRef = useRef<string | null>(null);

  const setValue = useCallback((next: S | ((prev: S) => S)) => {
    const prev = localRef.current;
    const val = typeof next === "function" ? (next as (p: S) => S)(prev) : next;
    if (val === prev) return;
    const deckVal = optsRef.current.toDeck(val);
    lastPushedRef.current = json(deckVal);
    localRef.current = val;
    setLocalState(val);
    optsRef.current.patch({ [optsRef.current.key]: deckVal });
  }, []);

  // 外部 deck 替换 → 本地跟随（自己的 push 由 lastPushed 串去重，不会拉回造成闪动）
  useEffect(() => {
    const cur = deck[key] as D;
    const serialized = json(cur);
    if (serialized === lastPushedRef.current) return; // 刚由本 hook 写入
    const eq = optsRef.current.eq;
    const adopted = optsRef.current.fromDeck(cur);
    if (eq ? eq(cur, optsRef.current.toDeck(localRef.current)) : serialized === json(optsRef.current.toDeck(localRef.current))) {
      lastPushedRef.current = serialized;
      return; // 与当前本地等价，仅同步 lastPushed 防止下次误拉
    }
    lastPushedRef.current = serialized;
    localRef.current = adopted;
    setLocalState(adopted);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, deck[key]]);

  return [local, setValue];
}
