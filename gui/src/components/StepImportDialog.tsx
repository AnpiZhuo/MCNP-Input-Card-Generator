/**
 * StepImportDialog — GEOUNED STEP 导入设置对话框
 */
import React, { useState } from "react";
import FloatingDialog from "./FloatingDialog";

interface StepSettings {
  materialName: string;
  density: string;
  tmp: string;
  voidGeneration: boolean;
  startCellNum: number;
  startSurfNum: number;
  compoundIsSingleCell: boolean;
}

interface Props {
  onImport: (settings: StepSettings, file: File) => void;
  onClose: () => void;
}

const DEFAULTS: StepSettings = {
  materialName: "MAT", density: "-1.0", tmp: "",
  voidGeneration: true, startCellNum: 1, startSurfNum: 100,
  compoundIsSingleCell: false,
};

const s: Record<string, React.CSSProperties> = {
  body: { flex: 1, overflow: "auto", padding: 0 },
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", display: "block", marginBottom: 3 },
  inp: { height: 30, padding: "0 8px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 11, outline: "none", width: "100%" },
  row: { display: "flex", gap: 8, marginBottom: 8, alignItems: "center" },
};

export default function StepImportDialog({ onImport, onClose }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<StepSettings>({ ...DEFAULTS });

  const set = (k: keyof StepSettings, v: any) => setSettings({ ...settings, [k]: v });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  const handleImport = () => {
    if (!file) { alert("请先选择 STEP 文件"); return; }
    onImport(settings, file);
  };

  return React.createElement(FloatingDialog, {
    title: "📥 GEOUNED 导入设置",
    onClose,
    width: 520,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
      React.createElement("button", { className: "btn btn-primary btn-sm", onClick: handleImport, disabled: !file }, "📥 导入"),
    ),
  },
    React.createElement("div", { style: s.body as React.CSSProperties },
        // File picker
        React.createElement("div", { style: s.row as React.CSSProperties },
          React.createElement("div", { style: { flex: 1 } },
            React.createElement("label", { style: s.lbl }, "STEP 文件"),
            React.createElement("input", { type: "file", accept: ".step,.stp", onChange: handleFileChange, style: { ...s.inp, padding: "4px 8px" } }),
          ),
        ),
        // Common settings
        React.createElement("div", { style: { fontWeight: 600, fontSize: 12, color: "var(--text-secondary)", margin: "8px 0 6px" } }, "转换设置"),
        React.createElement("div", { style: s.row as React.CSSProperties },
          React.createElement("div", { style: { flex: 1 } },
            React.createElement("label", { style: s.lbl }, "材料名称"),
            React.createElement("input", { style: s.inp, value: settings.materialName, onChange: e => set("materialName", e.target.value) }),
          ),
          React.createElement("div", { style: { flex: 1 } },
            React.createElement("label", { style: s.lbl }, "密度 (g/cm³)"),
            React.createElement("input", { style: s.inp, value: settings.density, onChange: e => set("density", e.target.value) }),
          ),
        ),
        React.createElement("div", { style: s.row as React.CSSProperties },
          React.createElement("div", { style: { flex: 1 } },
            React.createElement("label", { style: s.lbl }, "TMP 温度 (MeV)"),
            React.createElement("input", { style: s.inp, value: settings.tmp, onChange: e => set("tmp", e.target.value) }),
          ),
          React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-secondary)" } as React.CSSProperties },
            React.createElement("input", { type: "checkbox", checked: settings.voidGeneration, onChange: e => set("voidGeneration", e.target.checked) }), "生成真空栅元",
          ),
        ),
        React.createElement("div", { style: s.row as React.CSSProperties },
          React.createElement("div", { style: { flex: 1 } },
            React.createElement("label", { style: s.lbl }, "起始栅元号"),
            React.createElement("input", { style: s.inp, type: "number", value: settings.startCellNum, onChange: e => set("startCellNum", parseInt(e.target.value) || 1) }),
          ),
          React.createElement("div", { style: { flex: 1 } },
            React.createElement("label", { style: s.lbl }, "起始曲面号"),
            React.createElement("input", { style: s.inp, type: "number", value: settings.startSurfNum, onChange: e => set("startSurfNum", parseInt(e.target.value) || 1) }),
          ),
          React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-secondary)" } as React.CSSProperties },
            React.createElement("input", { type: "checkbox", checked: settings.compoundIsSingleCell, onChange: e => set("compoundIsSingleCell", e.target.checked) }), "复合体合并",
          ),
        ),
    ),
  );
}
