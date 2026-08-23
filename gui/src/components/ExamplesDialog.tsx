/**
 * 内置示例库：BEAVRS / 17×17 / pincell MCNP 卡（来自 OWEN prebuilt-models，MIT）。
 * 查看 = DocViewer 直接读 public/examples；导入 = fetch 卡文本 →
 * dispatch "mcnp:import-inp" 自定义事件（App.tsx 监听并复用 importInpText 管线）。
 */
import React, { useState } from "react";
import FloatingDialog from "./FloatingDialog";
import DocViewer from "./DocViewer";

interface ExampleItem {
  path: string;
  name: string;
  desc: string;
}

const EXAMPLES: ExampleItem[] = [
  {
    path: "/examples/pincell_mcnp.i",
    name: "Pincell 单棒",
    desc: "单棒栅元（燃料/气隙/包壳/慢化剂），5 栅元 / 266 曲面 / 4 材料",
  },
  {
    path: "/examples/assembly_17x17_mcnp.i",
    name: "17×17 PWR 组件",
    desc: "264 燃料棒 + 24 导向管 + 1 仪表管，lat=1/fill= 栅格语法，15 栅元 / 275 曲面 / 5 材料",
  },
  {
    path: "/examples/beavrs_fullcore_mcnp.i",
    name: "BEAVRS 全堆芯",
    desc: "193 组件（universe/lattice 展开），331 栅元 / 2101 曲面 / 13 材料",
  },
];

const s = {
  card: {
    border: "1px solid var(--border-glass)",
    borderRadius: 8,
    padding: "10px 12px",
    marginBottom: 8,
    background: "var(--bg-card, #121a2e)",
  },
  name: { fontSize: 13, fontWeight: 600, color: "var(--text-primary)" },
  desc: { fontSize: 11, color: "var(--text-tertiary)", marginTop: 3, lineHeight: 1.5 },
  row: { display: "flex" as const, gap: 8, alignItems: "center", marginTop: 8 },
};

export default function ExamplesDialog({ onClose }: { onClose: () => void }) {
  const [doc, setDoc] = useState<{ path: string; title: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");

  const doImport = async (ex: ExampleItem) => {
    setErr("");
    setBusy(ex.path);
    try {
      const r = await fetch(ex.path);
      if (!r.ok) throw new Error("读取示例失败: " + r.status);
      const text = await r.text();
      window.dispatchEvent(new CustomEvent("mcnp:import-inp", { detail: { text } }));
      onClose();
    } catch (e: any) {
      setErr(e.message || "导入失败");
    } finally {
      setBusy(null);
    }
  };

  return React.createElement(FloatingDialog, {
    title: "内置示例库",
    onClose,
    width: 640,
    footer: React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "关闭"),
  },
    React.createElement("div", { style: { fontSize: 11, color: "var(--text-tertiary)", marginBottom: 10, lineHeight: 1.6 } },
      "示例卡来自 OWEN prebuilt-models（MIT + BEAVRS 公开规范），可作为解析/生成回归素材，未经基准验证，导入后请按需修改。"),
    EXAMPLES.map((ex) =>
      React.createElement("div", { key: ex.path, style: s.card },
        React.createElement("div", { style: s.name }, ex.name),
        React.createElement("div", { style: s.desc }, ex.desc),
        React.createElement("div", { style: s.row },
          React.createElement("button", {
            className: "btn btn-primary btn-xs",
            disabled: busy !== null,
            onClick: () => doImport(ex),
          }, busy === ex.path ? "导入中…" : "一键导入"),
          React.createElement("button", {
            className: "btn btn-ghost btn-xs",
            onClick: () => setDoc({ path: ex.path, title: ex.name }),
          }, "查看卡文本"),
        ),
      ),
    ),
    err ? React.createElement("div", { style: { color: "#e53935", fontSize: 12, marginTop: 6 } }, err) : null,
    doc ? React.createElement(DocViewer, { path: doc.path, title: doc.title, onClose: () => setDoc(null) }) : null,
  );
}
