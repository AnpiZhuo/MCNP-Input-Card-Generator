/**
 * StepImportDialog — McCAD 导入设置对话框（参考参考版 v1.5.3 的 StepImportDialog）
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
  units: string;
  // 分解设置
  decompose: boolean;
  recurrenceDepth: number;
  minSolidVolume: number;
  minFaceArea: number;
  scalingFactor: number;
  precision: number;
  faceTolerance: number;
  edgeTolerance: number;
  parameterTolerance: number;
  angularTolerance: number;
  distanceTolerance: number;
  simplifyTori: boolean;
  simplifyAllTori: boolean;
  torusSplitAngle: number;
  // 转换设置
  compoundIsSingleCell: boolean;
  minVoidVolume: number;
  maxSolidsPerVoidCell: number;
  BVHVoid: boolean;
  maxLineWidth: number;
  debugLevel: number;
  startMatNum: number;
}

interface Props {
  onImport: (settings: StepSettings, file: File) => void;
  onClose: () => void;
}

const DEFAULTS: StepSettings = {
  materialName: "MAT", density: "-1.0", tmp: "",
  voidGeneration: true, startCellNum: 1, startSurfNum: 100, units: "cm",
  decompose: true, recurrenceDepth: 20,
  minSolidVolume: 1e-3, minFaceArea: 1e-4, scalingFactor: 100, precision: 1e-6,
  faceTolerance: 1e-8, edgeTolerance: 1e-8, parameterTolerance: 1e-8,
  angularTolerance: 1e-4, distanceTolerance: 1e-6,
  simplifyTori: false, simplifyAllTori: false, torusSplitAngle: 30,
  compoundIsSingleCell: false, minVoidVolume: 1.0, maxSolidsPerVoidCell: 20,
  BVHVoid: false, maxLineWidth: 80, debugLevel: 0, startMatNum: 1,
};

const s: Record<string, React.CSSProperties> = {
  body: { flex: 1, overflow: "auto", padding: 0 },
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", display: "block", marginBottom: 3 },
  inp: { height: 30, padding: "0 8px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 11, outline: "none", width: "100%" },
  row: { display: "flex", gap: 8, marginBottom: 8, alignItems: "center" },
  collHeader: { fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", cursor: "pointer", padding: "6px 0", borderTop: "1px solid var(--border-subtle)", marginTop: 6 },
};

function CollapsibleSection({ title, children, open: initOpen }: { title: string; children: React.ReactNode; open?: boolean }) {
  const [open, setOpen] = useState(initOpen || false);
  return React.createElement("div", null,
    React.createElement("div", { style: s.collHeader as React.CSSProperties, onClick: () => setOpen(!open) },
      open ? "▼ " : "▶ ", title),
    open ? React.createElement("div", { style: { padding: "4px 0 8px 12px" } }, children) : null,
  );
}

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
    title: "📥 McCAD 导入设置",
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
        React.createElement("div", { style: { fontWeight: 600, fontSize: 12, color: "var(--text-secondary)", margin: "8px 0 6px" } }, "通用设置"),
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
          React.createElement("div", { style: { flex: 1 } },
            React.createElement("label", { style: s.lbl }, "STEP 单位"),
            React.createElement("select", { className: "form-select", style: { height: 30, fontSize: 11 }, value: settings.units, onChange: e => set("units", e.target.value) },
              React.createElement("option", { value: "cm" }, "cm"), React.createElement("option", { value: "m" }, "m"), React.createElement("option", { value: "mm" }, "mm"),
            ),
          ),
        ),
        React.createElement("div", { style: s.row as React.CSSProperties },
          React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-secondary)" } as React.CSSProperties },
            React.createElement("input", { type: "checkbox", checked: settings.voidGeneration, onChange: e => set("voidGeneration", e.target.checked) }), "生成真空栅元",
          ),
          React.createElement("div", { style: { flex: 1, display: "flex", gap: 8 } },
            React.createElement("div", { style: { flex: 1 } },
              React.createElement("label", { style: s.lbl }, "起始栅元号"),
              React.createElement("input", { style: s.inp, type: "number", value: settings.startCellNum, onChange: e => set("startCellNum", parseInt(e.target.value) || 1) }),
            ),
            React.createElement("div", { style: { flex: 1 } },
              React.createElement("label", { style: s.lbl }, "起始曲面号"),
              React.createElement("input", { style: s.inp, type: "number", value: settings.startSurfNum, onChange: e => set("startSurfNum", parseInt(e.target.value) || 1) }),
            ),
          ),
        ),
        // Decomposition settings
        React.createElement(CollapsibleSection, { title: "分解设置" },
          React.createElement("div", { style: s.row as React.CSSProperties },
            React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-secondary)" } as React.CSSProperties },
              React.createElement("input", { type: "checkbox", checked: settings.decompose, onChange: e => set("decompose", e.target.checked) }), "启用分解",
            ),
          ),
          ...[
            ["recurrenceDepth", "递归深度", 1, 100],
            ["minSolidVolume", "最小实体体积 (cm³)", 1e-6, 1e6],
            ["minFaceArea", "最小面面积 (cm²)", 1e-6, 1e6],
            ["scalingFactor", "缩放因子", 0.1, 1000],
            ["precision", "精度", 1e-12, 1],
          ].map(([key, label, min, max]) =>
            React.createElement("div", { key: key as string, style: { ...s.row, marginBottom: 4 } as React.CSSProperties },
              React.createElement("label", { style: { ...s.lbl, width: 180, marginBottom: 0 } }, label),
              React.createElement("input", { style: { ...s.inp, width: 100 }, type: "number", step: "any",
                value: (settings as any)[key as string], min, max,
                onChange: e => set(key as keyof StepSettings, parseFloat(e.target.value) || 0) }),
            )
          ),
        ),
        // Conversion settings
        React.createElement(CollapsibleSection, { title: "转换设置" },
          React.createElement("div", { style: s.row as React.CSSProperties },
            React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-secondary)" } as React.CSSProperties },
              React.createElement("input", { type: "checkbox", checked: settings.compoundIsSingleCell, onChange: e => set("compoundIsSingleCell", e.target.checked) }), "复合体合并为单栅元",
            ),
            React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-secondary)" } as React.CSSProperties },
              React.createElement("input", { type: "checkbox", checked: settings.BVHVoid, onChange: e => set("BVHVoid", e.target.checked) }), "BVH 真空",
            ),
          ),
          ...[
            ["minVoidVolume", "最小真空体积", "float"],
            ["maxSolidsPerVoidCell", "每真空栅元最大实体数", "int"],
            ["maxLineWidth", "最大行宽", "int", 40, 200],
            ["debugLevel", "调试级别", "int", 0, 3],
            ["startMatNum", "起始材料号", "int", 1, 99999],
          ].map(([key, label, typ, ...range]: any[]) =>
            React.createElement("div", { key, style: { ...s.row, marginBottom: 4 } as React.CSSProperties },
              React.createElement("label", { style: { ...s.lbl, width: 180, marginBottom: 0 } }, label),
              React.createElement("input", { style: { ...s.inp, width: 100 }, type: "number", step: typ === "float" ? "any" : "1",
                value: (settings as any)[key],
                onChange: e => set(key, typ === "float" ? parseFloat(e.target.value) || 0 : parseInt(e.target.value) || 0) }),
            )
          ),
        ),
    ),
  );
}
