import React from "react";
import type { SswFields, SsrFields } from "../utils/DeckContext";

/* 面源 SSW/SSR 表单（源分布卡说明.md 四） */

interface Props {
  ssw: SswFields;
  ssr: SsrFields;
  onChangeSsw: (s: SswFields) => void;
  onChangeSsr: (s: SsrFields) => void;
}

const inp = { height: 30, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none", width: "100%" } as React.CSSProperties;
const lbl = { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", display: "block", marginBottom: 3 } as React.CSSProperties;
const grp = { display: "flex", flexDirection: "column", gap: 2, flex: 1 } as React.CSSProperties;

export default function SswSsrForm({ ssw, ssr, onChangeSsw, onChangeSsr }: Props) {
  return React.createElement("div", null,
    React.createElement("div", {
      style: { fontSize: 11, color: "var(--text-secondary)", background: "var(--bg-input)", border: "1px solid var(--border-glass)", borderRadius: 8, padding: "10px 12px", marginBottom: 12, lineHeight: 1.6 },
    },
      "📌 两步流程（两个独立 INP，SSW/SSR 不放同一个）：① 用「第一步·写面源」生成含 SSW 的 INP，",
      "跑完后粒子存成 WSSA 文件；② 把 WSSA 重命名为 RSSA；③ 用「第二步·读面源」生成含 SSR 的 INP，MCNP 从 RSSA 读粒子当源。",
    ),
    React.createElement("div", { style: { border: "1px solid var(--border-glass)", borderRadius: 8, padding: 12, marginBottom: 12 } },
      React.createElement("div", { style: { fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 } }, "第一步 · SSW 写面源"),
      React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap" } },
        React.createElement("div", { style: { ...grp, maxWidth: 220 } },
          React.createElement("label", { style: lbl }, "曲面号（空格分隔）"),
          React.createElement("input", { style: inp, value: ssw.surf, placeholder: "如 4 -7 19 (45 -46)", onChange: (e) => onChangeSsw({ ...ssw, surf: e.target.value }) }),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 110 } },
          React.createElement("label", { style: lbl }, "SYM 对称"),
          React.createElement("select", { style: { ...inp, height: 32 }, value: ssw.sym, onChange: (e) => onChangeSsw({ ...ssw, sym: e.target.value }) },
            React.createElement("option", { value: "" }, "0 无"),
            React.createElement("option", { value: "1" }, "1 球对称"),
            React.createElement("option", { value: "2" }, "2 双向"),
          ),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 90 } },
          React.createElement("label", { style: lbl }, "PTY 粒子"),
          React.createElement("select", { style: { ...inp, height: 32 }, value: ssw.pty, onChange: (e) => onChangeSsw({ ...ssw, pty: e.target.value }) },
            React.createElement("option", { value: "" }, "全部"),
            React.createElement("option", { value: "N" }, "N"),
            React.createElement("option", { value: "P" }, "P"),
            React.createElement("option", { value: "E" }, "E"),
          ),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 180 } },
          React.createElement("label", { style: lbl }, "CEL 裂变栅元"),
          React.createElement("input", { style: inp, value: ssw.cel, placeholder: "记录裂变源的栅元", onChange: (e) => onChangeSsw({ ...ssw, cel: e.target.value }) }),
        ),
      ),
    ),
    React.createElement("div", { style: { border: "1px solid var(--border-glass)", borderRadius: 8, padding: 12 } },
      React.createElement("div", { style: { fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 } }, "第二步 · SSR 读面源"),
      React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap" } },
        React.createElement("div", { style: { ...grp, maxWidth: 90 } },
          React.createElement("label", { style: lbl }, "OLD/NEW"),
          React.createElement("select", { style: { ...inp, height: 32 }, value: ssr.mode, onChange: (e) => onChangeSsr({ ...ssr, mode: e.target.value }) },
            React.createElement("option", { value: "" }, "--"),
            React.createElement("option", { value: "old" }, "OLD"),
            React.createElement("option", { value: "new" }, "NEW"),
          ),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 200 } },
          React.createElement("label", { style: lbl }, "曲面号"),
          React.createElement("input", { style: inp, value: ssr.surf, placeholder: "OLD 2 3 / NEW 6 7", onChange: (e) => onChangeSsr({ ...ssr, surf: e.target.value }) }),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 110 } },
          React.createElement("label", { style: lbl }, "PTY 粒子"),
          React.createElement("select", { style: { ...inp, height: 32 }, value: ssr.pty, onChange: (e) => onChangeSsr({ ...ssr, pty: e.target.value }) },
            React.createElement("option", { value: "" }, "全部"),
            React.createElement("option", { value: "N" }, "N"),
            React.createElement("option", { value: "P" }, "P"),
            React.createElement("option", { value: "E" }, "E"),
          ),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 100 } },
          React.createElement("label", { style: lbl }, "COL 碰撞"),
          React.createElement("input", { style: inp, value: ssr.col, placeholder: "0/1/-1", title: "-1=仅直穿 1=仅碰撞 0=全部", onChange: (e) => onChangeSsr({ ...ssr, col: e.target.value }) }),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 90 } },
          React.createElement("label", { style: lbl }, "WGT 权重"),
          React.createElement("input", { style: inp, value: ssr.wgt, placeholder: "1.0", onChange: (e) => onChangeSsr({ ...ssr, wgt: e.target.value }) }),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 100 } },
          React.createElement("label", { style: lbl }, "TR 变换"),
          React.createElement("input", { style: inp, value: ssr.tr, placeholder: "编号/Dn", onChange: (e) => onChangeSsr({ ...ssr, tr: e.target.value }) }),
        ),
        React.createElement("div", { style: { ...grp, maxWidth: 100 } },
          React.createElement("label", { style: lbl }, "PSC 角度幂次"),
          React.createElement("input", { style: inp, value: ssr.psc, placeholder: "0=各向同性", onChange: (e) => onChangeSsr({ ...ssr, psc: e.target.value }) }),
        ),
      ),
    ),
  );
}
