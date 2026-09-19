/**
 * keff 解析玻璃卡 —— 两个子按钮：「解析 mctal」/「解析 .o」。
 *
 * 为什么要分两个按钮（而不是一个按钮 + 手动切类型下拉）：
 * MCNP 的 mctal 文件**本体没有扩展名**（运行目录下就叫 `mctal`），而 outp 是
 * `.o`。一个按钮只能给一套默认过滤 ⇒ 用户总有一边打开窗口后**看不见自己的文件**，
 * 得手动把下拉切到"所有文件"。两个按钮各带一套默认过滤（规格在服务端
 * `app/file_dialog.py`：mctal 首项过滤 = 无后缀），这一步就没了。
 *
 * 本卡只负责"选文件"：选中路径交给父级开 KeffDialog（结果窗口：最终 k-eff +
 * 逐周期收敛曲线 + 出图）。`withContent:false` —— 只要路径，别把几百 MB 的 outp
 * 读回成 JSON。
 */
import React, { useState } from "react";
import { apiUrl, errorHint } from "../utils/api";

type Kind = "mctal" | "outp";

const BTN: Record<Kind, { label: string; title: string }> = {
  mctal: {
    label: "📄 解析 mctal",
    title: "选择 mctal 文件：默认按“无后缀”显示（mctal 本体没有扩展名）",
  },
  outp: {
    label: "🧾 解析 .o",
    title: "选择 MCNP 输出文件（.o / .outp / .out）",
  },
};

export default function KeffParseCard({ onOpen }: { onOpen: (path: string) => void }) {
  const [busy, setBusy] = useState<Kind | null>(null);
  const [err, setErr] = useState("");

  const pick = async (kind: Kind) => {
    setErr("");
    setBusy(kind);
    try {
      // 不加超时：系统文件选择窗口是模态的，用户可能挑很久
      const r = await fetch(apiUrl("/api/choose-file"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, withContent: false }),
      });
      const j = await r.json();
      if (j.status !== "ok") throw new Error(j.message || "选择文件失败");
      if (j.cancelled || !j.path) return;      // 取消：静默回退，不报错
      onOpen(String(j.path));
    } catch (e: any) {
      setErr(errorHint(e, "打开文件选择器失败"));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="glass-card">
      <div className="card-header">
        <span className="card-title" style={{ flexShrink: 0 }}>keff 解析</span>
        <span style={{ flex: 1, fontSize: 11, color: "var(--text-tertiary)", textAlign: "center" }}>
          临界计算的逐周期收敛曲线（mctal 无扩展名 / outp 为 .o）
        </span>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        {(Object.keys(BTN) as Kind[]).map((kind) => (
          <button
            key={kind}
            className="btn btn-ghost btn-sm"
            disabled={busy !== null}
            title={BTN[kind].title}
            onClick={() => pick(kind)}
          >
            {BTN[kind].label}
          </button>
        ))}
        {busy && (
          <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
            等待选择 {busy === "mctal" ? "mctal" : "outp(.o)"} 文件…
          </span>
        )}
        {err && <span style={{ fontSize: 11, color: "#e53935" }}>{err}</span>}
      </div>
    </div>
  );
}
