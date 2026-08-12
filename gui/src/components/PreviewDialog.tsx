import React, { useEffect } from "react";
import FloatingDialog from "./FloatingDialog";
import { apiUrl } from "../utils/api";

interface Props {
  content: string;
  onClose: () => void;
  onRegenerate?: () => void;
  outputPath?: string;
  fileName?: string;
  mcnpExe?: string;
}

const bodyStyle: React.CSSProperties = {
  flex: 1, padding: 0, fontFamily: "Consolas,monospace",
  fontSize: 12, lineHeight: 1.6, color: "var(--text-primary)",
  whiteSpace: "pre", background: "var(--editor-bg)",
};

/** 生成 run.bat 内容 */
function makeRunBat(inpFilename: string, mcnpExe?: string): string {
  const name = inpFilename.replace(/\.inp$/i, "").replace(/\.i$/i, "");
  const exe = mcnpExe || "mcnp6.exe";
  return `@echo off
rem 显卡选择：本机 GPU0 是核显，GPU1 是独显。设 CUDA_VISIBLE_DEVICES=1 让 MCNP 走独显加速
set CUDA_VISIBLE_DEVICES=1
call ${exe} inp=${inpFilename} outp=${name}.o
pause
`;
}

export default function PreviewDialog({ content, onClose, onRegenerate, outputPath, fileName, mcnpExe }: Props) {
  const safeName = fileName || "output.inp";
  const runBatContent = makeRunBat(safeName, mcnpExe);
  const nonAsciiWarn = (() => {
    const lines = content.split("\n");
    const bad = lines.filter((l,i) => /[^\x00-\x7F]/.test(l) && !l.trim().startsWith("$") && !l.trim().startsWith("C "));
    if (bad.length > 0) return React.createElement("div", { style: {padding:"8px 20px",background:"rgba(255,152,0,0.15)",borderTop:"1px solid rgba(255,152,0,0.3)",fontSize:11,color:"#ff9800"} },
      "⚠ " + bad.length + " 行包含非 ASCII 字符，MCNP 可能解析失败"
    );
    return null;
  })();

  const saveToDir = async () => {
    try {
      const r = await fetch(apiUrl("/api/save-inp"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          inp: content,
          filename: safeName,
          outputDir: outputPath || "D:/MCNP/new/claude",
          runBat: runBatContent,
        }),
      });
      const j = await r.json();
      if (j.status === "ok") {
        alert(`✅ 已保存到: ${j.path}\nrun.bat 已生成`);
      } else {
        alert("保存失败: " + (j.message || "未知错误"));
      }
    } catch {
      // Fallback: Blob download
      const blob = new Blob([content], { type: "text/plain" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = safeName;
      a.click();
      // Also save run.bat
      const batBlob = new Blob([runBatContent], { type: "text/plain" });
      const b = document.createElement("a");
      b.href = URL.createObjectURL(batBlob);
      b.download = safeName.replace(/\.\w+$/, "") + ".bat";
      b.click();
      alert("✅ 文件已下载（后端未连接，使用浏览器下载）");
    }
  };

  return React.createElement(FloatingDialog, {
    title: "INP 生成预览 — " + safeName,
    onClose: onClose,
    width: 720,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", {
        className: "btn btn-primary btn-sm",
        onClick: saveToDir,
      }, "💾 保存到目录"),
      React.createElement("button", {
        className: "btn btn-ghost btn-sm",
        onClick: () => {
          try {
            fetch(apiUrl("/api/run-mcnp"), {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ inp: content, filename: safeName, outputDir: outputPath || "D:/MCNP/new/claude", mcnpExe: mcnpExe || "" }),
            }).then(r => r.json()).then(j => {
              alert(j.status === "ok" || j.status === "started" ? "🚀 MCNP 已启动" : "启动失败: " + (j.message || "未知错误"));
            }).catch(() => alert("需要后端支持运行 MCNP"));
          } catch {}
        },
      }, "▶ 运行 MCNP"),
      React.createElement("button", {
        className: "btn btn-ghost btn-sm",
        onClick: () => navigator.clipboard.writeText(content),
      }, "复制"),
      React.createElement("button", {
        className: "btn btn-ghost btn-sm",
        onClick: () => {
          const blob = new Blob([content], { type: "text/plain" });
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = safeName;
          a.click();
        },
      }, "下载 .inp"),
      React.createElement("button", {
        className: "btn btn-ghost btn-sm",
        onClick: () => {
          const batBlob = new Blob([runBatContent], { type: "text/plain" });
          const a = document.createElement("a");
          a.href = URL.createObjectURL(batBlob);
          a.download = safeName.replace(/\.\w+$/, "") + ".bat";
          a.click();
        },
      }, "下载 run.bat"),
      onRegenerate && React.createElement("button", {
        className: "btn btn-ghost btn-sm",
        onClick: onRegenerate,
      }, "重新生成"),
      React.createElement("button", {
        className: "btn btn-ghost btn-sm",
        onClick: onClose,
      }, "关闭"),
    ),
  },
    React.createElement("div", { style: bodyStyle }, content),
    nonAsciiWarn,
  );
}
