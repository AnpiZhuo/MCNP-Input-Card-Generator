import React, { useState } from "react";
import type { MaterialData } from "../utils/DeckContext";
import FloatingDialog from "./FloatingDialog";

export interface CellData {
  num: string;
  mat: string;
  density: string;
  surfaces: string;
  impN: string;
  impP: string;
  impE: string;
  vol: string;
  pwt: string;
  ext: string;
  fcl: string;
  u: string;
  fill: string;
  lat: string;
  trcl: string;
  tmp: string;
  otherParams: string;
  render: boolean;
  comment: string;
}

interface Props {
  cell: CellData;
  onSave: (cell: CellData) => void;
  onClose: () => void;
  availableMats?: MaterialData[];
}

const style: Record<string, React.CSSProperties> = {
  row: { display: "flex", gap: 12, marginBottom: 12 },
  grp: { display: "flex", flexDirection: "column", gap: 4, flex: 1 },
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)" },
  inp: { height: 32, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none" },
};
const tarea = { ...style.inp, height: 50, resize: "vertical" as const, fontFamily: "Consolas,monospace" as const, fontSize: 11, paddingTop: 6 };

export default function CellEditDialog({ cell, onSave, onClose, availableMats }: Props) {
  const [data, setData] = useState(cell);
  const set = (k: keyof CellData, v: string) => {
    if (k === "mat" && availableMats?.length) {
      const matNum = parseInt(v);
      const mat = availableMats.find(m => m.number === matNum);
      if (mat && mat.density && !data.density) {
        setData({ ...data, mat: v, density: mat.density });
        return;
      }
    }
    setData({ ...data, [k]: v });
  };

  return React.createElement(FloatingDialog, {
    title: `栅元 ${data.num} 编辑`,
    onClose: onClose,
    width: 580,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
      React.createElement("button", { className: "btn btn-primary btn-sm", onClick: () => onSave(data) }, "保存"),
    ),
  },
    React.createElement("div", { style: style.row },
      React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
        React.createElement("label", { style: style.lbl }, "栅元号"),
        React.createElement("input", { style: style.inp, value: data.num, onChange: (e) => set("num", e.target.value) }),
      ),
      React.createElement("div", { style: style.grp },
        React.createElement("label", { style: style.lbl }, "材料号 (0=void)"),
        React.createElement("select", { style: style.inp, value: data.mat, onChange: (e) => set("mat", e.target.value) },
          React.createElement("option", { value: "0" }, "0 = void"),
          ...(availableMats || []).map(m =>
            React.createElement("option", { key: m.number, value: String(m.number) },
              `${m.number}` + (m.comment ? ` - ${m.comment}` : "")
            )
          ),
        ),
      ),
      React.createElement("div", { style: { ...style.grp, maxWidth: 100 } },
        React.createElement("label", { style: style.lbl }, "密度 (g/cm³)"),
        React.createElement("input", { style: style.inp, value: data.density, onChange: (e) => set("density", e.target.value) }),
      ),
    ),
    React.createElement("div", { style: style.row },
      React.createElement("div", { style: style.grp },
        React.createElement("label", { style: style.lbl }, "曲面表达式"),
        React.createElement("textarea", {
          style: { ...style.inp, height: 60, resize: "vertical", fontFamily: "Consolas,monospace", fontSize: 11, paddingTop: 6 },
          value: data.surfaces,
          onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => set("surfaces", e.target.value),
          placeholder: "如: -1 2 -3 4 -5 6"
        }),
      ),
    ),
    React.createElement("div", { style: style.row },
      React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
        React.createElement("label", { style: style.lbl }, "IMP:N"),
        React.createElement("input", { style: style.inp, value: data.impN, onChange: (e) => set("impN", e.target.value), placeholder: "0-1" }),
      ),
      React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
        React.createElement("label", { style: style.lbl }, "IMP:P"),
        React.createElement("input", { style: style.inp, value: data.impP, onChange: (e) => set("impP", e.target.value), placeholder: "0-1" }),
      ),
      React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
        React.createElement("label", { style: style.lbl }, "IMP:E"),
        React.createElement("input", { style: style.inp, value: data.impE, onChange: (e) => set("impE", e.target.value), placeholder: "0-1" }),
      ),
      React.createElement("div", { style: style.grp },
        React.createElement("label", { style: style.lbl }, "注释"),
        React.createElement("input", { style: style.inp, value: data.comment, onChange: (e) => set("comment", e.target.value), placeholder: "可选" }),
      ),
    ),
    // Advanced collapsible params
    React.createElement("details", { style: { marginTop: 4 } },
      React.createElement("summary", { style: { fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" } }, "高级参数 (VOL/PWT/EXT/FCL/U/FILL/LAT/TRCL/TMP)"),
      React.createElement(React.Fragment, null,
        React.createElement("div", { style: { ...style.row, marginTop: 8 } },
          React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
            React.createElement("label", { style: style.lbl }, "VOL 体积"),
            React.createElement("input", { style: style.inp, value: data.vol, onChange: (e) => set("vol", e.target.value), placeholder: "体积" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
            React.createElement("label", { style: style.lbl }, "PWT"),
            React.createElement("input", { style: style.inp, value: data.pwt, onChange: (e) => set("pwt", e.target.value), placeholder: "光子权重" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
            React.createElement("label", { style: style.lbl }, "EXT 指数"),
            React.createElement("input", { style: style.inp, value: data.ext, onChange: (e) => set("ext", e.target.value), placeholder: "指数变换" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
            React.createElement("label", { style: style.lbl }, "FCL 碰撞"),
            React.createElement("input", { style: style.inp, value: data.fcl, onChange: (e) => set("fcl", e.target.value), placeholder: "强制碰撞" }),
          ),
        ),
        React.createElement("div", { style: style.row },
          React.createElement("div", { style: { ...style.grp, maxWidth: 70 } },
            React.createElement("label", { style: style.lbl }, "U 宇宙"),
            React.createElement("input", { style: style.inp, value: data.u, onChange: (e) => set("u", e.target.value) }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 80 } },
            React.createElement("label", { style: style.lbl }, "FILL 填充"),
            React.createElement("input", { style: style.inp, value: data.fill, onChange: (e) => set("fill", e.target.value) }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 70 } },
            React.createElement("label", { style: style.lbl }, "LAT 格阵"),
            React.createElement("input", { style: style.inp, value: data.lat, onChange: (e) => set("lat", e.target.value), placeholder: "1/2" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "TRCL 变换"),
            React.createElement("input", { style: style.inp, value: data.trcl, onChange: (e) => set("trcl", e.target.value), placeholder: "编号" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "TMP 温度"),
            React.createElement("input", { style: style.inp, value: data.tmp, onChange: (e) => set("tmp", e.target.value), placeholder: "如 2.53e-8" }),
          ),
        ),
        React.createElement("div", { style: style.row },
          React.createElement("div", { style: style.grp },
            React.createElement("label", { style: style.lbl }, "其他参数 (other_params)"),
            React.createElement("input", { style: style.inp, value: data.otherParams, onChange: (e) => set("otherParams", e.target.value), placeholder: "如 TMP=2.53E-8" }),
          ),
        ),
      ),
    ),
    React.createElement("div", { style: { ...style.row, marginTop: 4 } }, null,
      React.createElement("label", { style: { ...style.lbl, display: "flex", alignItems: "center", gap: 6, cursor: "pointer" } },
        React.createElement("input", { type: "checkbox", checked: data.render, onChange: (e) => setData({ ...data, render: e.target.checked }) }),
        "3D 预览显示此栅元"
      ),
    ),
  );
}
