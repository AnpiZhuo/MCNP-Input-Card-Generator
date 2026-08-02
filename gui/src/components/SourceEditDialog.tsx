import React, { useState } from "react";
import FloatingDialog from "./FloatingDialog";

interface SourceData {
  number: number;
  par: string;
  erg: string;
  posX: string;
  posY: string;
  posZ: string;
  wgt: string;
  dir_: string;
  cel: string;
  tme: string;
  vec: string;
  axs: string;
  rad: string;
  ext: string;
  sur: string;
  nrm: string;
  tr: string;
  ccc: string;
  ara: string;
  rate: string;
  prob: string;
}

interface KsrcPoint { x: string; y: string; z: string }

type PointData = SourceData | KsrcPoint;

interface Props {
  point: PointData;
  index: number;
  isKsrc: boolean;
  onSave: (p: PointData) => void;
  onClose: () => void;
}

const s: Record<string, React.CSSProperties> = {
  inp: { height: 30, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none", width: "100%" },
  row: { display: "flex", gap: 8, marginBottom: 8, alignItems: "center" },
  grp: { display: "flex", flexDirection: "column", gap: 2, flex: 1 },
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)" },
};

export default function SourceEditDialog({ point, index, isKsrc, onSave, onClose }: Props) {
  const [d, setD] = useState<Record<string, string>>(
    isKsrc
      ? { x: (point as KsrcPoint).x || "0", y: (point as KsrcPoint).y || "0", z: (point as KsrcPoint).z || "0" }
      : {
          par: (point as SourceData).par || "1",
          erg: (point as SourceData).erg || "",
          posX: (point as SourceData).posX || "0",
          posY: (point as SourceData).posY || "0",
          posZ: (point as SourceData).posZ || "0",
          wgt: (point as SourceData).wgt || "1",
          dir_: (point as SourceData).dir_ || "",
          cel: (point as SourceData).cel || "",
          tme: (point as SourceData).tme || "",
          vec: (point as SourceData).vec || "",
          axs: (point as SourceData).axs || "",
          rad: (point as SourceData).rad || "",
          ext: (point as SourceData).ext || "",
          sur: (point as SourceData).sur || "",
          nrm: (point as SourceData).nrm || "",
          tr: (point as SourceData).tr || "",
          ccc: (point as SourceData).ccc || "",
          ara: (point as SourceData).ara || "",
          rate: (point as SourceData).rate || "",
          prob: (point as SourceData).prob || "",
        }
  );

  const set = (k: string, v: string) => setD({ ...d, [k]: v });

  if (isKsrc) {
    return React.createElement(FloatingDialog, {
      title: `KSRC 点 #${index + 1}`,
      onClose,
      width: 360,
      footer: React.createElement(React.Fragment, null,
        React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
        React.createElement("button", { className: "btn btn-primary btn-sm", onClick: () => onSave({ x: d.x || "0", y: d.y || "0", z: d.z || "0" }) }, "保存"),
      ),
    },
      React.createElement("div", { style: { padding: 0 } },
        ["x", "y", "z"].map(ax =>
          React.createElement("div", { style: { marginBottom: 10 }, key: ax },
            React.createElement("label", { style: s.lbl }, `${ax.toUpperCase()} (cm)`),
            React.createElement("input", { style: { ...s.inp, width: "100%" }, value: d[ax], onChange: (e) => set(ax, e.target.value) }),
          )
        ),
      ),
    );
  }

  return React.createElement(FloatingDialog, {
    title: `源 #${index + 1} 编辑`,
    onClose,
    width: 600,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
      React.createElement("button", { className: "btn btn-primary btn-sm", onClick: () => onSave({
        number: (point as SourceData).number,
        par: d.par, erg: d.erg,
        posX: d.posX, posY: d.posY, posZ: d.posZ,
        wgt: d.wgt, dir_: d.dir_, cel: d.cel, tme: d.tme,
        vec: d.vec, axs: d.axs, rad: d.rad, ext: d.ext,
        sur: d.sur, nrm: d.nrm, tr: d.tr,
        ccc: d.ccc, ara: d.ara, rate: d.rate, prob: d.prob,
      } as SourceData) }, "保存"),
    ),
  },
    React.createElement("div", { style: { padding: 0 } },
        // Row 1: PAR, ERG, POS
        React.createElement("div", { style: s.row },
          React.createElement("div", { style: { ...s.grp, maxWidth: 80 } },
            React.createElement("label", { style: s.lbl }, "PAR 粒子"),
            React.createElement("select", { style: { ...s.inp, height: 32 }, value: d.par, onChange: (ev: React.ChangeEvent<HTMLSelectElement>) => set("par", ev.target.value) },
              React.createElement("option", { value: "1" }, "1 - 中子"),
              React.createElement("option", { value: "2" }, "2 - 光子"),
              React.createElement("option", { value: "3" }, "3 - 电子"),
              React.createElement("option", { value: "H" }, "H - 质子"),
              React.createElement("option", { value: "A" }, "A - α粒子"),
              React.createElement("option", { value: "S" }, "S - 裂片"),
            ),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 100 } },
            React.createElement("label", { style: s.lbl }, "ERG 能量 (MeV)"),
            React.createElement("input", { style: s.inp, value: d.erg, onChange: (e) => set("erg", e.target.value), placeholder: "必填" }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
            React.createElement("label", { style: s.lbl }, "POS X"),
            React.createElement("input", { style: s.inp, value: d.posX, onChange: (e) => set("posX", e.target.value) }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
            React.createElement("label", { style: s.lbl }, "POS Y"),
            React.createElement("input", { style: s.inp, value: d.posY, onChange: (e) => set("posY", e.target.value) }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
            React.createElement("label", { style: s.lbl }, "POS Z"),
            React.createElement("input", { style: s.inp, value: d.posZ, onChange: (e) => set("posZ", e.target.value) }),
          ),
        ),
        // Row 2: DIR, WGT, CEL, TME
        React.createElement("div", { style: s.row },
          React.createElement("div", { style: { ...s.grp, maxWidth: 80 } },
            React.createElement("label", { style: s.lbl }, "DIR 方向"),
            React.createElement("input", { style: s.inp, value: d.dir_, onChange: (e) => set("dir_", e.target.value), placeholder: "留空=各向同性" }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
            React.createElement("label", { style: s.lbl }, "WGT 权重"),
            React.createElement("input", { style: s.inp, value: d.wgt, onChange: (e) => set("wgt", e.target.value), placeholder: "1" }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
            React.createElement("label", { style: s.lbl }, "CEL 栅元"),
            React.createElement("input", { style: s.inp, value: d.cel, onChange: (e) => set("cel", e.target.value), placeholder: "栅元号" }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 80 } },
            React.createElement("label", { style: s.lbl }, "TME 时间"),
            React.createElement("input", { style: s.inp, value: d.tme, onChange: (e) => set("tme", e.target.value), placeholder: "时间" }),
          ),
        ),
        // Row 3: VEC, AXS, RAD, EXT
        React.createElement("div", { style: s.row },
          React.createElement("div", { style: { ...s.grp, maxWidth: 140 } },
            React.createElement("label", { style: s.lbl }, "VEC (x y z)"),
            React.createElement("input", { style: s.inp, value: d.vec, onChange: (e) => set("vec", e.target.value), placeholder: "0 0 1" }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
            React.createElement("label", { style: s.lbl }, "AXS 轴"),
            React.createElement("input", { style: s.inp, value: d.axs, onChange: (e) => set("axs", e.target.value) }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
            React.createElement("label", { style: s.lbl }, "RAD 径向"),
            React.createElement("input", { style: s.inp, value: d.rad, onChange: (e) => set("rad", e.target.value) }),
          ),
          React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
            React.createElement("label", { style: s.lbl }, "EXT 轴向"),
            React.createElement("input", { style: s.inp, value: d.ext, onChange: (e) => set("ext", e.target.value) }),
          ),
        ),
        // Row 4: prob（概率）
        React.createElement("div", { style: s.row },
          React.createElement("div", { style: { ...s.grp, maxWidth: 100 } },
            React.createElement("label", { style: s.lbl }, "概率 (多源时)"),
            React.createElement("input", { style: s.inp, value: d.prob, onChange: (e) => set("prob", e.target.value), placeholder: "如 0.5" }),
          ),
        ),
        // Extra collapsible
        React.createElement("details", { style: { marginTop: 8 } },
          React.createElement("summary", { style: { fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" } }, "额外参数 (SUR/NRM/TR/CCC/ARA/RATE)"),
          React.createElement("div", { style: { marginTop: 8 } },
            React.createElement("div", { style: s.row },
              React.createElement("div", { style: { ...s.grp, maxWidth: 90 } },
                React.createElement("label", { style: s.lbl }, "SUR 曲面"),
                React.createElement("input", { style: s.inp, value: d.sur, onChange: (e) => set("sur", e.target.value) }),
              ),
              React.createElement("div", { style: { ...s.grp, maxWidth: 90 } },
                React.createElement("label", { style: s.lbl }, "NRM 法线"),
                React.createElement("input", { style: s.inp, value: d.nrm, onChange: (e) => set("nrm", e.target.value) }),
              ),
              React.createElement("div", { style: { ...s.grp, maxWidth: 70 } },
                React.createElement("label", { style: s.lbl }, "TR 变换"),
                React.createElement("input", { style: s.inp, value: d.tr, onChange: (e) => set("tr", e.target.value) }),
              ),
            ),
            React.createElement("div", { style: s.row },
              React.createElement("div", { style: { ...s.grp, maxWidth: 100 } },
                React.createElement("label", { style: s.lbl }, "CCC"),
                React.createElement("input", { style: s.inp, value: d.ccc, onChange: (e) => set("ccc", e.target.value) }),
              ),
              React.createElement("div", { style: { ...s.grp, maxWidth: 100 } },
                React.createElement("label", { style: s.lbl }, "ARA"),
                React.createElement("input", { style: s.inp, value: d.ara, onChange: (e) => set("ara", e.target.value) }),
              ),
              React.createElement("div", { style: { ...s.grp, maxWidth: 100 } },
                React.createElement("label", { style: s.lbl }, "RATE 强度"),
                React.createElement("input", { style: s.inp, value: d.rate, onChange: (e) => set("rate", e.target.value) }),
              ),
            ),
          ),
        ),
      ),
  );
}
