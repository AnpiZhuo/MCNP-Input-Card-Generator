/**
 * TasksIncompatibleHint — 「该设置与 MCNP 多核（tasks > 1）不兼容」的统一提示。
 *
 * **权威依据**（C810.pdf 页 875）::
 *
 *     "DBCN(2,3,4), SSW, and PTRAC are incompatible with tasks > 1 (FATAL error)."
 *
 * ⇒ 用户在 UI 上**一旦选中这些模式**就地提醒，而不是等他点了「运行 MCNP」才吃到 FATAL。
 *
 * **后端另有兜底**（两层防线）：即使这条提示被忽略、或这些卡是从「高级 → 额外卡片」
 * 手写进来的，`_handle_run_mcnp` 也会扫卡并把 `tasks` 压回 1，原因随响应回传、前端 alert 显示。
 * 纯逻辑在 `app/mcnp_tasks.py`（可单测），见 `tests/unit/test_mcnp_tasks.py`。
 */
import React from "react";

export default function TasksIncompatibleHint({
  what,
  style,
}: {
  /** 功能名，如 "PTRAC 粒子径迹" / "SSW / SSR 面源" */
  what: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        alignItems: "flex-start",
        fontSize: 11,
        lineHeight: 1.6,
        padding: "8px 12px",
        marginBottom: 10,
        borderRadius: 6,
        background: "rgba(234,179,8,0.10)",
        border: "1px solid rgba(234,179,8,0.35)",
        color: "var(--text-primary)",
        ...style,
      }}
    >
      <span style={{ color: "#eab308", flexShrink: 0, fontWeight: 700 }}>⚠</span>
      <span>
        <b>{what}</b> 与 MCNP 多核（<code>tasks &gt; 1</code>）<b>不兼容</b>：C810 规定两者同时使用会直接
        FATAL。运行时会自动改用单线程（<code>tasks 1</code>）—— 想跑多核就别用该模式。
      </span>
    </div>
  );
}
