/**
 * QuickCellForm — 快捷建栅元参数表单（弹窗与 3D 预览侧栏共用）
 *
 * - 所有数值输入框默认空；空值按 0 处理（分块类环数/段数/份数/壳数按 1）
 * - 材料默认 M0 真空；材料为 0 时生成需自定义确认弹窗（酷炫风格，贴合主题）
 * - onConfigChange 把当前形状/配置/材料回调给宿主（画线框预览）
 * - keepOpenAfterGenerate=true（3D 预览侧栏）生成后表单保持，由宿主决定何时恢复
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  generateQuickCell,
  parseAngleExpr,
  quickCellCounts,
  validateQuickCell,
  type QuickCellResult,
  type QuickShape,
} from "../utils/quickCell";

interface QuickCellFormProps {
  surfacesText: string;
  trCardsText: string;
  cellNumbers: number[];
  materials: { number: number; comment?: string; density?: string }[];
  onGenerate: (result: QuickCellResult) => void;
  /** 形状/配置/材料变化回调（宿主画线框预览，宿主自行防抖） */
  onConfigChange?: (shape: QuickShape, config: any, valid: boolean, material: string) => void;
  /** 取消/恢复栅元控制 */
  onCancel?: () => void;
  /** 生成后是否保持表单打开（3D 预览侧栏 true；弹窗 false） */
  keepOpenAfterGenerate?: boolean;
  /** 基础页启用的粒子模式（N/P/E）——imp 不勾选时按此填 1 */
  modeN?: boolean;
  modeP?: boolean;
  modeE?: boolean;
}

const style: Record<string, React.CSSProperties> = {
  row: { display: "flex", gap: 10, marginBottom: 8, alignItems: "flex-end" },
  grp: { display: "flex", flexDirection: "column", gap: 3, flex: 1, minWidth: 0 },
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)" },
  inp: {
    height: 28, padding: "0 8px", borderRadius: 5, border: "1px solid var(--border-glass)",
    background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 11,
    outline: "none", width: "100%", boxSizing: "border-box",
  },
  seg: {
    flex: 1, padding: "5px 4px", borderRadius: 5, border: "1px solid var(--border-glass)",
    background: "transparent", color: "var(--text-secondary)", fontSize: 11, cursor: "pointer",
  },
  segOn: {
    flex: 1, padding: "5px 4px", borderRadius: 5, border: "1px solid var(--accent)",
    background: "rgba(98,140,255,0.15)", color: "var(--accent)", fontSize: 11, cursor: "pointer",
  },
  err: { color: "#e57373", fontSize: 11, marginTop: 4 },
  info: { color: "var(--text-secondary)", fontSize: 11, marginTop: 4 },
};

function num(s: string, d = 0): number {
  const v = parseFloat(s);
  return Number.isFinite(v) ? v : d;
}

function intPos(s: string, d = 1): number {
  const v = parseInt(s, 10);
  return Number.isFinite(v) && v > 0 ? v : d;
}

export default function QuickCellForm({
  surfacesText, trCardsText, cellNumbers, materials,
  onGenerate, onConfigChange, onCancel, keepOpenAfterGenerate,
  modeN, modeP, modeE,
}: QuickCellFormProps) {
  const [shape, setShape] = useState<QuickShape>("rcc");
  // 所有数值输入默认空：空按 0（分块按 1）处理
  const [rcc, setRcc] = useState({ cx: "", cy: "", cz: "", hx: "", hy: "", hz: "", r: "", rings: "", segments: "" });
  const [sph, setSph] = useState({ x: "", y: "", z: "", r: "", shells: "" });
  const [rpp, setRpp] = useState({
    L: "", W: "", H: "", cx: "", cy: "", cz: "",
    roll: "", pitch: "", yaw: "", nx: "", ny: "", nz: "",
  });
  const [unit, setUnit] = useState<"deg" | "rad">("deg");
  const angleFocusRef = useRef<"roll" | "pitch" | "yaw">("roll");
  const [material, setMaterial] = useState("0");
  const [impN, setImpN] = useState(false);
  const [impP, setImpP] = useState(false);
  const [impE, setImpE] = useState(false);
  const [checkOverlap, setCheckOverlap] = useState(true);
  const [confirmVoid, setConfirmVoid] = useState(false);

  const config = useMemo(() => {
    if (shape === "rcc") {
      return {
        shape,
        config: {
          center: [num(rcc.cx), num(rcc.cy), num(rcc.cz)],
          axis: [num(rcc.hx), num(rcc.hy), num(rcc.hz)],
          radius: num(rcc.r),
          rings: intPos(rcc.rings),
          segments: intPos(rcc.segments),
        },
      };
    }
    if (shape === "sph") {
      return {
        shape,
        config: {
          center: [num(sph.x), num(sph.y), num(sph.z)],
          radius: num(sph.r),
          shells: intPos(sph.shells),
        },
      };
    }
    const ang = (s: string) => parseAngleExpr(s) ?? 0;
    const raw = [ang(rpp.roll), ang(rpp.pitch), ang(rpp.yaw)];
    const angles = (unit === "deg" ? raw.map((d) => (d * Math.PI) / 180) : raw) as [number, number, number];
    return {
      shape,
      config: {
        size: [num(rpp.L), num(rpp.W), num(rpp.H)],
        center: [num(rpp.cx), num(rpp.cy), num(rpp.cz)],
        angles,
        nx: intPos(rpp.nx),
        ny: intPos(rpp.ny),
        nz: intPos(rpp.nz),
      },
    };
  }, [shape, rcc, sph, rpp, unit]);

  const error = useMemo(() => validateQuickCell(config.shape as QuickShape, config.config as any), [config]);
  const counts = useMemo(() => quickCellCounts(config.shape as QuickShape, config.config as any), [config]);
  const cfgKey = useMemo(() => JSON.stringify(config.config), [config]);

  // 配置/材料变化 → 宿主画线框预览
  useEffect(() => {
    onConfigChange?.(config.shape as QuickShape, config.config as any, !error, material);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfgKey, error, material, shape]);

  const doGenerate = () => {
    const result = generateQuickCell(config.shape as QuickShape, config.config as any, {
      surfacesText, trCardsText, cellNumbers, materials, material,
      impN, impP, impE, modeN, modeP, modeE,
    });
    result.checkOverlap = checkOverlap;
    onGenerate(result);
    if (!keepOpenAfterGenerate) onCancel?.();
  };

  const handleGenerate = () => {
    if (material === "0") setConfirmVoid(true);
    else doGenerate();
  };

  const matDensity = material !== "0" && material !== "" ? materials.find((m) => String(m.number) === material)?.density ?? "" : "";

  const numRow = (label: string, fields: { key: string; ph: string; w?: number }[], vals: Record<string, string>, set: (k: string, v: string) => void) =>
    React.createElement("div", { style: style.row, key: label },
      React.createElement("div", { style: { ...style.grp, maxWidth: 64 } },
        React.createElement("label", { style: style.lbl }, label),
      ),
      fields.map((f) =>
        React.createElement("div", { key: f.key, style: { ...style.grp, maxWidth: f.w ?? 70 } },
          React.createElement("label", { style: style.lbl }, f.ph),
          React.createElement("input", { style: style.inp, value: vals[f.key], onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(f.key, e.target.value) }),
        ),
      ),
    );

  const segBtn = (s: QuickShape, label: string) =>
    React.createElement("button", {
      key: s,
      type: "button",
      style: shape === s ? style.segOn : style.seg,
      onClick: () => setShape(s),
    }, label);

  const inputGroup = () => {
    if (shape === "rcc") {
      return React.createElement(React.Fragment, null,
        numRow("底面中心", [{ key: "cx", ph: "X" }, { key: "cy", ph: "Y" }, { key: "cz", ph: "Z" }], rcc, (k, v) => setRcc((p) => ({ ...p, [k]: v }))),
        numRow("轴向量", [{ key: "hx", ph: "HX" }, { key: "hy", ph: "HY" }, { key: "hz", ph: "HZ" }], rcc, (k, v) => setRcc((p) => ({ ...p, [k]: v }))),
        numRow("半径 / 切分", [{ key: "r", ph: "半径" }, { key: "rings", ph: "环数 N" }, { key: "segments", ph: "段数 M" }], rcc, (k, v) => setRcc((p) => ({ ...p, [k]: v }))),
      );
    }
    if (shape === "sph") {
      return React.createElement(React.Fragment, null,
        numRow("球心", [{ key: "x", ph: "X" }, { key: "y", ph: "Y" }, { key: "z", ph: "Z" }], sph, (k, v) => setSph((p) => ({ ...p, [k]: v }))),
        numRow("半径 / 壳数", [{ key: "r", ph: "半径" }, { key: "shells", ph: "壳数 K" }], sph, (k, v) => setSph((p) => ({ ...p, [k]: v }))),
      );
    }
    const angleFields: { key: "roll" | "pitch" | "yaw"; ph: string }[] = [
      { key: "roll", ph: "Roll(X)" },
      { key: "pitch", ph: "Pitch(Y)" },
      { key: "yaw", ph: "Yaw(Z)" },
    ];
    return React.createElement(React.Fragment, null,
      numRow("尺寸", [{ key: "L", ph: "长 L" }, { key: "W", ph: "宽 W" }, { key: "H", ph: "高 H" }], rpp, (k, v) => setRpp((p) => ({ ...p, [k]: v }))),
      numRow("中心", [{ key: "cx", ph: "X" }, { key: "cy", ph: "Y" }, { key: "cz", ph: "Z" }], rpp, (k, v) => setRpp((p) => ({ ...p, [k]: v }))),
      React.createElement("div", { style: style.row },
        React.createElement("div", { style: { ...style.grp, maxWidth: 64 } },
          React.createElement("label", { style: style.lbl }, "倾斜角"),
        ),
        angleFields.map((f) =>
          React.createElement("div", { key: f.key, style: { ...style.grp, maxWidth: 70 } },
            React.createElement("label", { style: style.lbl }, f.ph),
            React.createElement("input", {
              style: style.inp,
              value: rpp[f.key],
              onFocus: () => { angleFocusRef.current = f.key; },
              onChange: (e: React.ChangeEvent<HTMLInputElement>) => setRpp((p) => ({ ...p, [f.key]: e.target.value })),
            }),
          ),
        ),
      ),
      React.createElement("div", { style: { ...style.row, alignItems: "center" } },
        React.createElement("label", { style: { ...style.lbl, flexShrink: 0 } }, "角度单位"),
        React.createElement("button", { type: "button", style: unit === "deg" ? style.segOn : style.seg, onClick: () => setUnit("deg") }, "DEG（度）"),
        React.createElement("button", { type: "button", style: unit === "rad" ? style.segOn : style.seg, onClick: () => setUnit("rad") }, "RAD（弧度）"),
        unit === "rad" && React.createElement("button", {
          type: "button",
          style: { ...style.seg, flex: 0, padding: "5px 10px" },
          title: "在当前角度框插入 π（支持 π/2、2π）",
          onClick: () => setRpp((p) => ({ ...p, [angleFocusRef.current]: p[angleFocusRef.current] + "π" })),
        }, "插入 π"),
      ),
      React.createElement("div", { style: { fontSize: 10, color: "var(--text-tertiary)", marginBottom: 4 } },
        "倾斜角依次绕 X→Y→Z（外旋 = Roll→Pitch→Yaw），R = Rz(Yaw)·Ry(Pitch)·Rx(Roll)；全 0 时轴对齐（RPP 宏体，无 TR），非 0 时程序自动生成 TR 卡"),
      numRow("切分", [{ key: "nx", ph: "X 份" }, { key: "ny", ph: "Y 份" }, { key: "nz", ph: "Z 份" }], rpp, (k, v) => setRpp((p) => ({ ...p, [k]: v }))),
    );
  };

  return React.createElement(React.Fragment, null,
    React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 10 } },
      segBtn("rcc", "圆柱 RCC"),
      segBtn("rpp", "六面体 RPP"),
      segBtn("sph", "球 SPH"),
    ),
    inputGroup(),
    React.createElement("div", { style: { ...style.row, marginTop: 8 } },
      React.createElement("div", { style: { ...style.grp, maxWidth: 150 } },
        React.createElement("label", { style: style.lbl }, "材料"),
        React.createElement("select", {
        className: "form-select",
          style: style.inp,
          value: material,
          onChange: (e: React.ChangeEvent<HTMLSelectElement>) => setMaterial(e.target.value),
        },
          React.createElement("option", { value: "0" }, "M0 — 真空"),
          materials.map((m) => React.createElement("option", { key: m.number, value: String(m.number) }, `M${m.number}${m.comment ? " — " + m.comment : ""}`)),
        ),
      ),
      React.createElement("div", { style: { ...style.grp, maxWidth: 130 } },
        React.createElement("label", { style: style.lbl }, "IMP（勾选=0，不勾选按基础页填1）"),
        React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center", height: 28 } },
          React.createElement("label", { style: { fontSize: 11, color: "var(--text-secondary)", display: "flex", gap: 3, alignItems: "center" } },
            React.createElement("input", { type: "checkbox", checked: impN, onChange: (e) => setImpN(e.target.checked) }), "N"),
          React.createElement("label", { style: { fontSize: 11, color: "var(--text-secondary)", display: "flex", gap: 3, alignItems: "center" } },
            React.createElement("input", { type: "checkbox", checked: impP, onChange: (e) => setImpP(e.target.checked) }), "P"),
          React.createElement("label", { style: { fontSize: 11, color: "var(--text-secondary)", display: "flex", gap: 3, alignItems: "center" } },
            React.createElement("input", { type: "checkbox", checked: impE, onChange: (e) => setImpE(e.target.checked) }), "E"),
        ),
      ),
      React.createElement("div", { style: { ...style.grp, maxWidth: 170 } },
        React.createElement("label", { style: style.lbl }, "重合检测"),
        React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center", height: 28 } },
          React.createElement("label", { style: { fontSize: 11, color: "var(--text-secondary)", display: "flex", gap: 3, alignItems: "center" } },
            React.createElement("input", { type: "checkbox", checked: checkOverlap, onChange: (e) => setCheckOverlap(e.target.checked) }),
            "添加时检测与已有栅元重合"),
        ),
      ),
    ),
    React.createElement("div", { style: style.info },
      `将生成 ${counts.surfaceCount} 个曲面 / ${counts.cellCount} 个栅元`
      + (material !== "0" && matDensity ? `；材料 M${material} 密度自动填入 ${matDensity}` : material !== "0" ? "；材料未定义密度，密度留空待填" : ""),
    ),
    error && React.createElement("div", { style: style.err }, error),
    React.createElement("div", { style: { display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 10 } },
      onCancel && React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onCancel }, keepOpenAfterGenerate ? "恢复栅元控制" : "取消"),
      React.createElement("button", {
        className: "btn btn-primary btn-sm",
        disabled: !!error,
        style: { opacity: error ? 0.5 : 1 },
        onClick: handleGenerate,
      }, "生成并加入"),
    ),
    /* 材料 0 自定义确认弹窗（贴合主题的玻璃拟态 + 强调光晕） */
    confirmVoid && React.createElement("div", {
      style: {
        position: "fixed", inset: 0, zIndex: 1300, display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(5,5,18,0.65)", backdropFilter: "blur(8px)",
      } as React.CSSProperties,
    },
      React.createElement("div", {
        style: {
          width: 360, background: "linear-gradient(160deg, rgba(18,20,42,0.98), rgba(10,10,30,0.98))",
          border: "1px solid rgba(255,179,71,0.35)", borderRadius: 14, padding: 22,
          boxShadow: "0 0 0 1px rgba(255,179,71,0.12), 0 18px 60px rgba(0,0,0,0.65), 0 0 42px rgba(255,179,71,0.18)",
          color: "var(--text-primary)", fontFamily: "inherit",
        } as React.CSSProperties,
      },
        React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 10, marginBottom: 10 } },
          React.createElement("div", {
            style: {
              width: 38, height: 38, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 18, background: "radial-gradient(circle at 30% 30%, rgba(255,179,71,0.35), rgba(255,138,0,0.12))",
              border: "1px solid rgba(255,179,71,0.45)", boxShadow: "0 0 16px rgba(255,179,71,0.35)",
            } as React.CSSProperties,
          }, "⚠"),
          React.createElement("span", { style: { fontSize: 15, fontWeight: 700, letterSpacing: 0.5 } }, "确认材料"),
        ),
        React.createElement("div", { style: { fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 18 } },
          "材料为 M0 真空（void），生成的栅元将按真空处理（无密度、不参与实体渲染）。确认继续生成？"),
        React.createElement("div", { style: { display: "flex", gap: 8, justifyContent: "flex-end" } },
          React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: () => setConfirmVoid(false) }, "取消"),
          React.createElement("button", {
            className: "btn btn-primary btn-sm",
            style: { background: "linear-gradient(135deg, #ff9d2e, #ff5e3a)", borderColor: "transparent" },
            onClick: () => { setConfirmVoid(false); doGenerate(); },
          }, "确认生成"),
        ),
      ),
    ),
  );
}
