import React, { useState } from "react";
import type { MaterialData } from "../utils/DeckContext";
import FloatingDialog from "./FloatingDialog";
import { batchEditEmpty, type BatchCellEditValues } from "../utils/batchCellEdit";

/**
 * BatchCellEditDialog — 「批量编辑栅元」弹窗（GeometryTab 栅元列表勾选后弹出）。
 *
 * 字段约定：材料/密度/IMP/高级参数，留空 = 不改（保持原值）；
 * 曲面表达式只可「追加」，不可批量覆盖/删除（锁死提示 + 后缀输入）。
 * 确认后由 applyBatchCellEdit 回填到勾选栅元（纯函数在 utils/batchCellEdit.ts）。
 */
interface Props {
  /** 勾选的栅元（只含 kind === "cell" 的行） */
  cells: { num: string; mat: string; density: string }[];
  availableMats?: MaterialData[];
  onApply: (values: BatchCellEditValues) => void;
  onClose: () => void;
}

const style: Record<string, React.CSSProperties> = {
  row: { display: "flex", gap: 12, marginBottom: 12 },
  grp: { display: "flex", flexDirection: "column", gap: 4, flex: 1 },
  lbl: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)" },
  inp: { height: 32, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none" },
};

const textValues = {
  impN: "",
  impP: "",
  impE: "",
  vol: "",
  pwt: "",
  ext: "",
  fcl: "",
  u: "",
  fill: "",
  lat: "",
  trcl: "",
  tmp: "",
  otherParams: "",
};

export default function BatchCellEditDialog({ cells, availableMats = [], onApply, onClose }: Props) {
  const [values, setValues] = useState<BatchCellEditValues>({ mat: "", density: "", ...textValues, surfaceAppend: "" });

  const set = (k: keyof BatchCellEditValues, v: string) => setValues((prev) => ({ ...prev, [k]: v }));

  // 选材料时自动带出该材料密度（沿用单栅元编辑行为）；材料 0 = 真空 → 密度清空
  const onMatChange = (v: string) => {
    if (v === "0") {
      setValues((prev) => ({ ...prev, mat: v, density: "" }));
      return;
    }
    const found = availableMats.find((m) => String(m.number) === v);
    setValues((prev) => ({ ...prev, mat: v, density: found?.density ?? prev.density }));
  };

  const selectedNums = cells.map((c) => c.num).join("、");
  const confirmDisabled = batchEditEmpty(values);

  return React.createElement(FloatingDialog, {
    title: `批量编辑栅元（已勾选 ${cells.length} 个）`,
    onClose,
    width: 620,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
      React.createElement("button", {
        className: "btn btn-primary btn-sm",
        disabled: confirmDisabled,
        onClick: () => onApply(values),
      }, "确认"),
    ),
  },
    React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)", marginBottom: 12 } },
      `将应用到栅元：${selectedNums}。留空的字段保持不变。`),

    // 材料 / 密度
    React.createElement("div", { style: style.row },
      React.createElement("div", { style: { ...style.grp, maxWidth: 140 } },
        React.createElement("label", { style: style.lbl }, "材料号 (0=void，留空不改)"),
        React.createElement("select", { style: style.inp, value: values.mat || "", onChange: (e: React.ChangeEvent<HTMLSelectElement>) => onMatChange(e.target.value) },
          React.createElement("option", { value: "" }, "— 不改 —"),
          React.createElement("option", { value: "0" }, "0 = void"),
          ...availableMats.map((m) =>
            React.createElement("option", { key: m.number, value: String(m.number) },
              `${m.number}` + (m.comment ? ` - ${m.comment}` : "")),
          ),
        ),
      ),
      React.createElement("div", { style: { ...style.grp, maxWidth: 120 } },
        React.createElement("label", { style: style.lbl }, "密度 (g/cm³，留空不改)"),
        React.createElement("input", { style: style.inp, value: values.density || "", onChange: (e) => set("density", e.target.value), placeholder: "如 -1.0" }),
      ),
    ),

    // IMP:N / IMP:P / IMP:E
    React.createElement("div", { style: style.row },
      React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
        React.createElement("label", { style: style.lbl }, "IMP:N"),
        React.createElement("input", { style: style.inp, value: values.impN || "", onChange: (e) => set("impN", e.target.value), placeholder: "如 1" }),
      ),
      React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
        React.createElement("label", { style: style.lbl }, "IMP:P"),
        React.createElement("input", { style: style.inp, value: values.impP || "", onChange: (e) => set("impP", e.target.value), placeholder: "如 1" }),
      ),
      React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
        React.createElement("label", { style: style.lbl }, "IMP:E"),
        React.createElement("input", { style: style.inp, value: values.impE || "", onChange: (e) => set("impE", e.target.value), placeholder: "如 1" }),
      ),
    ),

    // 曲面表达式：锁死提示 + 追加后缀
    React.createElement("div", { style: style.row },
      React.createElement("div", { style: style.grp },
        React.createElement("label", { style: style.lbl }, "曲面表达式"),
        React.createElement("div", {
          style: { ...style.inp, minHeight: 32, display: "flex", alignItems: "center", gap: 6, padding: "0 8px", cursor: "not-allowed" },
          title: "批量编辑不支持覆盖/删除曲面表达式，只能追加",
        },
          React.createElement("span", { style: { color: "var(--text-tertiary)", fontStyle: "italic", whiteSpace: "nowrap" } },
            "无法批量更改曲面表达式，只可添加"),
        ),
        React.createElement("input", {
          style: { ...style.inp, marginTop: 4, fontFamily: "Consolas,monospace", fontSize: 11 },
          value: values.surfaceAppend || "",
          onChange: (e) => set("surfaceAppend", e.target.value),
          placeholder: "追加到勾选栅元曲面表达式之后，如: 3 -4",
        }),
      ),
    ),

    // 高级参数（可折叠）
    React.createElement("details", { style: { marginTop: 4 } },
      React.createElement("summary", { style: { fontSize: 11, cursor: "pointer", color: "var(--text-secondary)" } },
        "高级参数 (VOL/PWT/EXT/FCL/U/FILL/LAT/TRCL/TMP)"),
      React.createElement(React.Fragment, null,
        React.createElement("div", { style: { ...style.row, marginTop: 8 } },
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "VOL 体积"),
            React.createElement("input", { style: style.inp, value: values.vol || "", onChange: (e) => set("vol", e.target.value), placeholder: "体积" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "PWT"),
            React.createElement("input", { style: style.inp, value: values.pwt || "", onChange: (e) => set("pwt", e.target.value), placeholder: "光子权重" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "EXT 指数"),
            React.createElement("input", { style: style.inp, value: values.ext || "", onChange: (e) => set("ext", e.target.value), placeholder: "指数变换" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "FCL 碰撞"),
            React.createElement("input", { style: style.inp, value: values.fcl || "", onChange: (e) => set("fcl", e.target.value), placeholder: "强制碰撞" }),
          ),
        ),
        React.createElement("div", { style: style.row },
          React.createElement("div", { style: { ...style.grp, maxWidth: 70 } },
            React.createElement("label", { style: style.lbl }, "U 宇宙"),
            React.createElement("input", { style: style.inp, value: values.u || "", onChange: (e) => set("u", e.target.value) }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "FILL 填充"),
            React.createElement("input", { style: style.inp, value: values.fill || "", onChange: (e) => set("fill", e.target.value) }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 70 } },
            React.createElement("label", { style: style.lbl }, "LAT 格阵"),
            React.createElement("input", { style: style.inp, value: values.lat || "", onChange: (e) => set("lat", e.target.value), placeholder: "1/2" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "TRCL 变换"),
            React.createElement("input", { style: style.inp, value: values.trcl || "", onChange: (e) => set("trcl", e.target.value), placeholder: "编号" }),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 90 } },
            React.createElement("label", { style: style.lbl }, "TMP 温度"),
            React.createElement("input", { style: style.inp, value: values.tmp || "", onChange: (e) => set("tmp", e.target.value), placeholder: "如 2.53e-8" }),
          ),
        ),
        React.createElement("div", { style: style.row },
          React.createElement("div", { style: style.grp },
            React.createElement("label", { style: style.lbl }, "其他参数 (other_params)"),
            React.createElement("input", { style: style.inp, value: values.otherParams || "", onChange: (e) => set("otherParams", e.target.value), placeholder: "如 TMP=2.53E-8" }),
          ),
        ),
      ),
    ),
  );
}
