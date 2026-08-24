/**
 * LatticeEditDialog — 格阵 FILL 编辑器（5 步状态机：0 类型尺寸 → 1 材料曲面 →
 * 2 延伸方向 → 3 宇宙调色板 → 4 画布涂色 → 5 保存）。
 *
 * 保存写回：fill=range.join(" ")、lat、fill_grid=serializeFillGrid(fg)、surface_expr、
 * material="0"、density=""；保存时 cells 反算覆盖 raw。
 * 曲面失焦调后端 validate-lattice-surfaces（测试中 mock fetch）。
 */
import React, { useEffect, useMemo, useState } from "react";
import FloatingDialog from "./FloatingDialog";
import LatticeCanvas from "./LatticeCanvas";
import LatticePreview3D from "./LatticePreview3D";
import type { CellData } from "./CellEditDialog";
import {
  autoGenerateSurfaces,
  buildUniversePalette,
  cellsToRaw,
  getUniverseColor,
  initialHexCells,
  initialRectCells,
  parseFillGrid,
  rangeFromDims,
  resizeLatticeCells,
  serializeFillGrid,
  validateLatticeSurfaces,
} from "../utils/lattice";
import type { FillGridCellJson, FillGridJson, ValidateLatticeResult } from "../utils/lattice";

const STEPS = ["类型与尺寸", "材料与曲面", "延伸方向", "宇宙调色板", "画布涂色", "保存"];

interface Props {
  surfacesText: string;
  deckCells: CellData[];
  initialCell?: CellData | null;
  nextCellNum: number;
  onSave: (result: { cell: CellData; surfacesText: string }) => void;
  onClose: () => void;
}

const lbl: React.CSSProperties = { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)", marginBottom: 3 };
const inp: React.CSSProperties = {
  height: 30, padding: "0 10px", borderRadius: 6, border: "1px solid var(--border-glass)",
  background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 12, outline: "none", width: "100%", boxSizing: "border-box",
};
const tarea: React.CSSProperties = {
  ...inp, height: 64, resize: "vertical", fontFamily: "Consolas,monospace", fontSize: 11, paddingTop: 6, paddingBottom: 6,
};

export default function LatticeEditDialog({ surfacesText, deckCells, initialCell, nextCellNum, onSave, onClose }: Props) {
  /* ── 编辑已有格阵时从 fill_grid 预填 ── */
  const init = useMemo(() => {
    if (!initialCell) return null;
    const fg = parseFillGrid(initialCell.fill_grid);
    if (!fg) return null;
    return { fg, surfaceExpr: initialCell.surfaces, latticeU: initialCell.u };
  }, [initialCell]);
  const editing = !!init;
  const originalDims = init ? init.fg.dims : null;
  const ringShaped =
    editing && originalDims && originalDims.length >= 2 && originalDims[0] === originalDims[1] && originalDims[0] % 2 === 1;
  // 编辑导入的矩形六棱柱（非环形）时锁定尺寸，避免破坏原格阵
  const sizeEditable = editing ? init?.fg.lat !== "2" || ringShaped : true;

  const [step, setStep] = useState(0);
  const [lat, setLat] = useState<"1" | "2">(init ? (init.fg.lat === "2" ? "2" : "1") : "1");
  const [rectCols, setRectCols] = useState<number>(init && init.fg.lat !== "2" ? init.fg.dims[0] || 17 : 17);
  const [rectRows, setRectRows] = useState<number>(init && init.fg.lat !== "2" ? init.fg.dims[1] || 17 : 17);
  const [hexRings, setHexRings] = useState<number>(
    init && init.fg.lat === "2"
      ? originalDims && originalDims[0] === originalDims[1] && originalDims[0] % 2 === 1
        ? (originalDims[0] - 1) / 2
        : 2
      : 1,
  );
  const [ext3D, setExt3D] = useState<boolean>(init ? (init.fg.dims[2] || 1) > 1 : false);
  const [layers, setLayers] = useState<number>(init ? Math.max(1, init.fg.dims[2] || 1) : 1);
  const [surfaceExpr, setSurfaceExpr] = useState<string>(init ? init.surfaceExpr : "");
  const [latticeU, setLatticeU] = useState<string>(init ? init.latticeU : "");
  const [localSurfaces, setLocalSurfaces] = useState<string>(surfacesText);
  const [genLines, setGenLines] = useState<string[]>([]);
  const [genParams, setGenParams] = useState({ L: 20, W: 20, H: 10, cx: 0, cy: 0, cz: 0, side: 2 });
  const [validateResult, setValidateResult] = useState<ValidateLatticeResult | null>(null);

  /* ── 宇宙调色板：从 deck.cells 去重收集 u= ── */
  const [universeList, setUniverseList] = useState<string[]>(() => {
    const set = new Set<string>();
    for (const c of deckCells) {
      const u = (c.u ?? "").trim();
      if (u && u !== "0") set.add(u);
    }
    return Array.from(set).sort((a, b) => Number(a) - Number(b));
  });
  const [customU, setCustomU] = useState("");
  const palette = useMemo(() => buildUniversePalette(universeList), [universeList]);
  const defaultPaintU = universeList.length ? universeList[0] : "1";
  const [selectedU, setSelectedU] = useState<string>(defaultPaintU);
  const [cells, setCells] = useState<FillGridCellJson[]>(() => (init ? init.fg.cells : []));

  /* ── dims / range 派生 + 尺寸变化保持已涂色格位 ── */
  const dims = useMemo(
    () => (lat === "2" ? [2 * hexRings + 1, 2 * hexRings + 1, layers] : [rectCols, rectRows, layers]),
    [lat, rectCols, rectRows, hexRings, layers],
  );
  const dimsKey = dims.join("x");
  useEffect(() => {
    if (!sizeEditable) return;
    setCells((prev) => {
      const fresh =
        lat === "2"
          ? initialHexCells(hexRings, layers, defaultPaintU)
          : initialRectCells(rectCols, rectRows, layers, defaultPaintU);
      return resizeLatticeCells(prev, fresh);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dimsKey, sizeEditable]);

  const effectiveDims = editing && !sizeEditable && originalDims ? originalDims : dims;

  /* ── 曲面失焦校验（后端 validate-lattice-surfaces）── */
  const handleSurfaceBlur = async () => {
    const r = await validateLatticeSurfaces(surfaceExpr, lat, localSurfaces);
    setValidateResult(r);
  };

  /* ── 自动生成平面（追加到曲面卡 + 填表达式）── */
  const handleAutoGen = () => {
    const res = autoGenerateSurfaces(
      lat,
      lat === "2"
        ? { hex: { side: genParams.side, H: genParams.H, cx: genParams.cx, cy: genParams.cy, cz: genParams.cz } }
        : { rect: { L: genParams.L, W: genParams.W, H: genParams.H, cx: genParams.cx, cy: genParams.cy, cz: genParams.cz } },
      localSurfaces,
    );
    setLocalSurfaces(res.surfacesText);
    setSurfaceExpr(res.surfaceExpr);
    setGenLines(res.lines);
    setValidateResult(null);
  };

  const addCustomUniverse = () => {
    const u = customU.trim();
    if (!u || u === "0") return;
    if (!universeList.includes(u)) setUniverseList([...universeList, u].sort((a, b) => Number(a) - Number(b)));
    setSelectedU(u);
    setCustomU("");
  };

  const paintCell = (idx: number, u: string) => {
    setCells((prev) => prev.map((c, i) => (i === idx ? { ...c, u } : c)));
  };

  const numField = (label: string, value: number, setter: (v: number) => void, w = 74) => (
    <div style={{ flex: "0 0 auto", width: w }}>
      <label style={lbl}>{label}</label>
      <input
        type="number"
        style={inp}
        value={value}
        onChange={(e) => setter(parseInt(e.target.value, 10) || 0)}
      />
    </div>
  );

  /* ── 保存 ── */
  const handleSave = () => {
    const d = effectiveDims;
    const r = rangeFromDims(d);
    const fg: FillGridJson = { lat, kind: "lattice", range: r, dims: d, cells, raw: "" };
    fg.raw = cellsToRaw(fg); // 保存时 cells 反算覆盖 raw
    const cell: CellData = {
      num: initialCell ? initialCell.num : String(nextCellNum),
      mat: "0",
      density: "",
      surfaces: surfaceExpr.trim(),
      impN: "", impP: "", impE: "",
      vol: "", pwt: "", ext: "", fcl: "",
      u: latticeU,
      fill: r.join(" "),
      lat,
      trcl: "", tmp: "", otherParams: "",
      render: true,
      fill_grid: serializeFillGrid(fg),
      comment: "",
    };
    onSave({ cell, surfacesText: localSurfaces });
  };

  const cellCount = effectiveDims.reduce((a, b) => a * b, 1);

  const footer = React.createElement(React.Fragment, null,
    React.createElement("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
    step > 0 &&
      React.createElement("button", { type: "button", className: "btn btn-ghost btn-sm", style: { marginLeft: 8 }, onClick: () => setStep(step - 1) },
        "上一步"),
    step < 5 &&
      React.createElement("button", { type: "button", className: "btn btn-primary btn-sm", style: { marginLeft: 8 }, onClick: () => setStep(step + 1) },
        "下一步"),
    step === 5 &&
      React.createElement("button", { type: "button", className: "btn btn-primary btn-sm", style: { marginLeft: 8 }, onClick: handleSave },
        "保存并写入栅元卡"),
  );

  return React.createElement(
    FloatingDialog,
    { title: "⬚ 栅格编辑（格阵 FILL）", onClose, width: 980, maxHeight: "92vh", footer },
    React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "center", marginBottom: 12, fontSize: 11, color: "var(--text-secondary)" } },
      STEPS.map((s, i) =>
        React.createElement("span", {
          key: s,
          style: {
            padding: "3px 8px", borderRadius: 999, cursor: "pointer",
            background: i === step ? "var(--accent)" : "rgba(255,255,255,0.08)",
            color: i === step ? "#fff" : "var(--text-secondary)",
          },
          onClick: () => setStep(i),
        }, s),
      ),
    ),
    React.createElement("div", { style: { minHeight: 380 } },
      /* 步骤0：类型与尺寸 */
      step === 0 &&
        React.createElement("div", null,
          React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 14 } },
            React.createElement("button", {
              type: "button",
              onClick: () => setLat("1"),
              style: { ...btn, border: lat === "1" ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: lat === "1" ? "rgba(76,159,232,0.15)" : "var(--bg-input)" },
            }, "矩形 (lat=1)"),
            React.createElement("button", {
              type: "button",
              onClick: () => setLat("2"),
              style: { ...btn, border: lat === "2" ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: lat === "2" ? "rgba(76,159,232,0.15)" : "var(--bg-input)" },
            }, "六棱柱 (lat=2)"),
          ),
          lat === "1"
            ? React.createElement("div", { style: { display: "flex", gap: 10, alignItems: "flex-end", marginBottom: 8 } },
                numField("列数 (i)", rectCols, setRectCols),
                numField("行数 (j)", rectRows, setRectRows),
              )
            : React.createElement("div", { style: { display: "flex", gap: 10, alignItems: "flex-end", marginBottom: 8 } },
                numField("环数 (rings)", hexRings, setHexRings),
                React.createElement("span", { style: { fontSize: 11, color: "var(--text-secondary)", paddingBottom: 6 } },
                  `${hexRingCountLabel(hexRings)} 格 · 菱形角位自动补 void(0)`),
              ),
          !sizeEditable &&
            React.createElement("div", { style: { fontSize: 11, color: "#e0a12e", marginBottom: 6 } },
              "⚠ 编辑导入的矩形六棱柱：尺寸保持原样（仅可改涂色/曲面）。"),
          React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)" } },
            `范围：${rangeFromDims(effectiveDims).join("  ")} · 共 ${cellCount} 格位`),
        ),
      /* 步骤1：材料锁死 + 曲面 */
      step === 1 &&
        React.createElement("div", null,
          React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 12 } },
            React.createElement("div", { style: { width: 90 } },
              React.createElement("label", { style: lbl }, "材料号"),
              React.createElement("input", { style: inp, value: "0", readOnly: true, title: "格阵格元材料强制 0（void）" }),
            ),
            React.createElement("div", { style: { width: 120 } },
              React.createElement("label", { style: lbl }, "密度"),
              React.createElement("input", { style: inp, value: "", readOnly: true, placeholder: "空" }),
            ),
            React.createElement("div", { style: { width: 100 } },
              React.createElement("label", { style: lbl }, "本格阵 U（可选）"),
              React.createElement("input", { style: inp, value: latticeU, onChange: (e: React.ChangeEvent<HTMLInputElement>) => setLatticeU(e.target.value), placeholder: "如 10" }),
            ),
          ),
          React.createElement("label", { style: lbl }, "曲面表达式（格元几何，失焦校验）"),
          React.createElement("textarea", {
            style: { ...tarea, width: "100%" },
            value: surfaceExpr,
            onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => setSurfaceExpr(e.target.value),
            onBlur: handleSurfaceBlur,
            placeholder: lat === "2" ? "如 -1 -2 -3 -4 -5 -6 -7 -8" : "如 +1 -2 +3 -4 +5 -6",
          }),
          validateResult &&
            React.createElement("div", { style: { fontSize: 11, marginTop: 4, color: validateResult.ok ? "#2e7d32" : "#e53935" } },
              validateResult.ok ? "✓ 曲面通过" : `✗ ${validateResult.msg || "曲面不构成合法格元"}`),
          React.createElement("div", { style: { marginTop: 14, border: "1px solid var(--border-glass)", borderRadius: 8, padding: 10 } },
            React.createElement("div", { style: { fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 } },
              "自动生成平面（追加到曲面卡）"),
            React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" } },
              lat === "2"
                ? React.createElement(React.Fragment, null,
                    numField("边长", genParams.side, (v) => setGenParams({ ...genParams, side: v })),
                    numField("高", genParams.H, (v) => setGenParams({ ...genParams, H: v })),
                  )
                : React.createElement(React.Fragment, null,
                    numField("长", genParams.L, (v) => setGenParams({ ...genParams, L: v })),
                    numField("宽", genParams.W, (v) => setGenParams({ ...genParams, W: v })),
                    numField("高", genParams.H, (v) => setGenParams({ ...genParams, H: v })),
                  ),
              numField("中心X", genParams.cx, (v) => setGenParams({ ...genParams, cx: v })),
              numField("中心Y", genParams.cy, (v) => setGenParams({ ...genParams, cy: v })),
              numField("中心Z", genParams.cz, (v) => setGenParams({ ...genParams, cz: v })),
              React.createElement("button", { type: "button", className: "btn btn-primary btn-sm", onClick: handleAutoGen },
                "生成平面卡并填表达式"),
            ),
            genLines.length > 0 &&
              React.createElement("div", { style: { marginTop: 8, fontSize: 11, fontFamily: "Consolas,monospace", color: "var(--text-secondary)", whiteSpace: "pre-wrap" } },
                genLines.join("\n")),
          ),
        ),
      /* 步骤2：延伸方向 */
      step === 2 &&
        React.createElement("div", null,
          React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 12 } },
            React.createElement("button", { type: "button", onClick: () => { setExt3D(false); setLayers(1); }, style: { ...btn, border: !ext3D ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: !ext3D ? "rgba(76,159,232,0.15)" : "var(--bg-input)" } },
              "2D 平面（第三轴 0:0）"),
            React.createElement("button", { type: "button", onClick: () => setExt3D(true), style: { ...btn, border: ext3D ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: ext3D ? "rgba(76,159,232,0.15)" : "var(--bg-input)" } },
              "3D 体积（第三轴 0:k）"),
          ),
          ext3D &&
            React.createElement("div", { style: { display: "flex", gap: 10, alignItems: "flex-end" } },
              numField("轴向层数 k", layers, (v) => setLayers(Math.max(1, v))),
            ),
          React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)", marginTop: 8 } },
            `延伸后范围：${rangeFromDims(effectiveDims).join("  ")} · 共 ${effectiveDims.reduce((a, b) => a * b, 1)} 格位`),
        ),
      /* 步骤3：宇宙调色板 */
      step === 3 &&
        React.createElement("div", null,
          React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)", marginBottom: 8 } },
            `从 deck 收集 ${universeList.length} 个宇宙（u=）；点击选择涂色笔。`),
          React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 } },
            universeList.map((u) =>
              React.createElement("button", {
                key: u,
                type: "button",
                onClick: () => setSelectedU(u),
                style: {
                  minWidth: 56, height: 34, borderRadius: 6, border: selectedU === u ? "2px solid #fff" : "1px solid rgba(255,255,255,0.25)",
                  background: getUniverseColor(u, palette), color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer",
                  boxShadow: selectedU === u ? "0 0 0 2px var(--accent)" : "none",
                },
              }, `U=${u}`),
            ),
          ),
          React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center" } },
            React.createElement("input", {
              style: { ...inp, width: 140 },
              placeholder: "自定义宇宙号",
              value: customU,
              onChange: (e: React.ChangeEvent<HTMLInputElement>) => setCustomU(e.target.value),
            }),
            React.createElement("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: addCustomUniverse },
              "添加"),
          ),
          React.createElement("div", { style: { fontSize: 12, marginTop: 10, color: "var(--text-secondary)" } },
            `当前涂色笔：U=${selectedU}`),
        ),
      /* 步骤4：画布涂色 + 3D 子预览 */
      step === 4 &&
        React.createElement("div", { style: { display: "flex", gap: 14, alignItems: "flex-start" } },
          React.createElement("div", { style: { flex: "0 0 auto", maxWidth: 480, overflow: "auto" } },
            React.createElement(LatticeCanvas, {
              lat,
              dims: effectiveDims,
              cells,
              palette,
              selectedU,
              onCellChange: paintCell,
              pitch: 22,
            }),
          ),
          React.createElement("div", { style: { flex: 1, minWidth: 240, height: 380 } },
            React.createElement(LatticePreview3D, { lat, dims: effectiveDims, cells, palette, pitch: 1, height: Math.max(0.5, effectiveDims[2] || 1) }),
          ),
        ),
      /* 步骤5：保存摘要 */
      step === 5 &&
        React.createElement("div", null,
          React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)", marginBottom: 8 } },
            "保存将写入栅元卡："),
          React.createElement("div", { style: { fontFamily: "Consolas,monospace", fontSize: 12, lineHeight: 1.9, background: "var(--bg-input)", border: "1px solid var(--border-glass)", borderRadius: 8, padding: 10 } },
            React.createElement("div", null, `material = 0   density = ""`),
            React.createElement("div", null, `u = ${latticeU || "—"}`),
            React.createElement("div", null, `lat = ${lat}`),
            React.createElement("div", null, `fill = ${rangeFromDims(effectiveDims).join(" ")}`),
            React.createElement("div", null, `surface_expr = ${surfaceExpr || "（空）"}`),
            React.createElement("div", null, `fill_grid = ${serializeFillGrid({ lat, kind: "lattice", range: rangeFromDims(effectiveDims), dims: effectiveDims, cells, raw: "" })}`),
          ),
          !surfaceExpr.trim() &&
            React.createElement("div", { style: { fontSize: 11, color: "#e0a12e", marginTop: 8 } },
              "⚠ 曲面表达式为空，请回到「材料与曲面」填写或自动生成。"),
        ),
    ),
  );
}

/** 按钮基础样式（弹窗内统一） */
const btn: React.CSSProperties = {
  height: 32, padding: "0 14px", borderRadius: 6, cursor: "pointer",
  fontSize: 12, color: "var(--text-primary)",
};

function hexRingCountLabel(rings: number): string {
  const rows = 2 * rings + 1;
  const total = rows * rows; // 包围盒格位数
  return `${total} 盒位`;
}
