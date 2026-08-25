/**
 * LatticeEditDialog — 格阵 FILL 编辑器（Wave 2b 4 步状态机）：
 *   0 类型与尺寸 + 延伸方向（lat 选择 + 六个方向层数空 -N:M：x 左/右、y 前/后、z 下/上）
 *   1 材料与曲面（材料锁死 0 + 本格阵 U + 自动生成宏体 / 手动填写曲面 互斥 + 校验 + 宏体子预览）
 *   2 画布涂色 + 调色板（同屏：LatticeCanvas + 常驻调色板侧栏 + 自定义宇宙号 + 3D 子预览）
 *   3 保存摘要（体积告警 + 保存）
 *
 * 范围层数按 MCNP 习惯：六个方向负/正层数 → -N:M 范围（六棱柱 I/J 对称，x/y 层数取环数）。
 * 保存写回：fill=range.join(" ")、lat、fill_grid=serializeFillGrid(fg)、surface_expr、
 * material="0"、density=""；保存时 fg.raw = compressRaw(cellsToRaw(fg))（项12 编辑器路径 nR 压缩）；
 * 保存前 detectFillCycle（项13）命中 → 阻止保存 + 提示。
 */
import React, { useEffect, useMemo, useState } from "react";
import FloatingDialog from "./FloatingDialog";
import LatticeCanvas from "./LatticeCanvas";
import LatticePreview3D from "./LatticePreview3D";
import MacrobodyPreview from "./MacrobodyPreview";
import type { CellData } from "./CellEditDialog";
import {
  autoGenMacrobody,
  autoGenerateSurfaces,
  buildUniversePalette,
  cellsToRaw,
  collectFillUniverses,
  compressRaw,
  detectFillCycle,
  dirCountsFromRange,
  fitHexPitch,
  getUniverseColor,
  hexLatticePitch,
  hexPrismCircumradius,
  initialRectCells,
  latticeVolumeWarning,
  maxSurfaceNumber,
  parseFillGrid,
  rangeFromDirCounts,
  resizeLatticeCells,
  rhpCard,
  rhpFromThreePoints,
  rhpModeAError,
  serializeFillGrid,
  validateLatticeSurfaces,
} from "../utils/lattice";
import type { CycleCellLike, FillGridCellJson, FillGridJson, ValidateLatticeResult } from "../utils/lattice";

const STEPS = ["类型与尺寸", "材料与曲面", "画布涂色", "保存"];

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
const btn: React.CSSProperties = {
  height: 32, padding: "0 14px", borderRadius: 6, cursor: "pointer",
  fontSize: 12, color: "var(--text-primary)",
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
  // 六字段独立（矩形/六棱柱统一）：编辑导入格阵也可改尺寸，范围由负/正层数反派生
  const sizeEditable = true;

  const [step, setStep] = useState(0);
  const [lat, setLat] = useState<"1" | "2">(init ? (init.fg.lat === "2" ? "2" : "1") : "1");
  // 项2：六个方向层数空（负/正层数 → -N:M 范围；编辑旧 deck 从原 range 反派生，保持 0:16 角起写法）
  const [xDir, setXDir] = useState<{ neg: number; pos: number }>(() =>
    init ? dirCountsFromRange(init.fg.range[0] || "0:16") : { neg: 8, pos: 8 });
  const [yDir, setYDir] = useState<{ neg: number; pos: number }>(() =>
    init ? dirCountsFromRange(init.fg.range[1] || "0:16") : { neg: 8, pos: 8 });
  const [zDir, setZDir] = useState<{ neg: number; pos: number }>(() =>
    init ? dirCountsFromRange(init.fg.range[2] || "0:0") : { neg: 0, pos: 0 });
  const [surfaceExpr, setSurfaceExpr] = useState<string>(init ? init.surfaceExpr : "");
  const [latticeU, setLatticeU] = useState<string>(init ? init.latticeU : "");
  const [localSurfaces, setLocalSurfaces] = useState<string>(surfacesText);
  const [validateResult, setValidateResult] = useState<ValidateLatticeResult | null>(null);

  // 项3：自动生成宏体 vs 手动填写曲面（互斥）
  const [autoMode, setAutoMode] = useState<boolean>(true);
  const [genLines, setGenLines] = useState<string[]>([]);
  const [genCard, setGenCard] = useState("");
  // 自动宏体参数：矩形 L/W/H/中心；六棱柱 模式 B（中心+外接半径+高）/ 模式 A（三点+高）
  const [genRect, setGenRect] = useState({ L: 20, W: 20, H: 10, cx: 0, cy: 0, cz: 0 });
  const [rhpMode, setRhpMode] = useState<"B" | "A">("B");
  const [genHexB, setGenHexB] = useState({ R: 2, H: 10, cx: 0, cy: 0, cz: 0 });
  const [genHexA, setGenHexA] = useState({ vx: 0, vy: 0, vz: 0, tx: 0, ty: 0, tz: 10, mx: 1.732, my: 1, mz: 0, h: 10 });
  // 手动可选：旧 6 平面 / 6P+2PZ 生成参数
  const [genPlanes, setGenPlanes] = useState({ L: 20, W: 20, H: 10, side: 2, cx: 0, cy: 0, cz: 0 });

  // 项7：调色板 = void 0 ∪ deck u= ∪ 各格阵 fill_grid.cells[].u 去重，数值升序
  const [universeList, setUniverseList] = useState<string[]>(() => collectFillUniverses(deckCells));
  const [customU, setCustomU] = useState("");
  const palette = useMemo(() => buildUniversePalette(universeList), [universeList]);
  const defaultPaintU = universeList.find((u) => u !== "0") ?? "1";
  const [selectedU, setSelectedU] = useState<string>(defaultPaintU);
  const [cells, setCells] = useState<FillGridCellJson[]>(() => (init ? init.fg.cells : []));

  /* ── 项16：六棱柱宏体外接半径自动随格阵（OWEN 模式：宏体尺寸由格阵范围推导，
   * 参考格距 REF_PITCH 是相对基准；用户手动改 R 后不再覆盖，可点「按格阵重算」恢复）。 ── */
  const [rManual, setRManual] = useState(false);
  const REF_PITCH = 2; // 参考格距（中心距 cm）
  useEffect(() => {
    if (lat !== "2" || !autoMode || rhpMode !== "B" || rManual) return;
    const R = hexPrismCircumradius(xDir.neg, xDir.pos, yDir.neg, yDir.pos, REF_PITCH);
    setGenHexB((prev) => ({ ...prev, R: Number(R.toFixed(3)) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, autoMode, rhpMode, xDir, yDir, rManual]);
  const suggestR = () => {
    setRManual(false);
    const R = hexPrismCircumradius(xDir.neg, xDir.pos, yDir.neg, yDir.pos, REF_PITCH);
    setGenHexB((prev) => ({ ...prev, R: Number(R.toFixed(3)) }));
  };
  // 按当前 RHP 外接半径推导格距（p：六棱柱面恰好切到最外圈格子外缘）
  const hexPitch = useMemo(
    () => (lat === "2" ? hexLatticePitch((genHexB.R * Math.sqrt(3)) / 2, xDir.neg, xDir.pos, yDir.neg, yDir.pos) : 0),
    [lat, genHexB.R, xDir, yDir],
  );

  /* ── dims / range 派生 + 尺寸变化保持已涂色格位 ── */
  const dims = useMemo(() => {
    return [
      xDir.neg + xDir.pos + 1,
      yDir.neg + yDir.pos + 1,
      Math.max(1, zDir.neg + zDir.pos + 1),
    ];
  }, [xDir, yDir, zDir]);
  const dimsKey = dims.join("x");
  useEffect(() => {
    setCells((prev) => resizeLatticeCells(prev, initialRectCells(dims[0], dims[1], dims[2], defaultPaintU)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dimsKey]);

  const effectiveDims = dims;

  const currentRange = useMemo(
    () => [
      rangeFromDirCounts(xDir.neg, xDir.pos),
      rangeFromDirCounts(yDir.neg, yDir.pos),
      rangeFromDirCounts(zDir.neg, zDir.pos),
    ],
    [xDir, yDir, zDir],
  );

  const handleLatChange = (v: "1" | "2") => setLat(v);

  /* ── 曲面失焦校验（手动模式）── */
  const handleSurfaceBlur = async () => {
    const r = await validateLatticeSurfaces(surfaceExpr, lat, localSurfaces);
    setValidateResult(r);
  };

  /* ── 自动生成宏体（项3/4）：rect→RPP / hex→RHP（模式 A/B）── */
  const handleAutoGen = () => {
    if (lat === "2" && rhpMode === "A") {
      const V: [number, number, number] = [genHexA.vx, genHexA.vy, genHexA.vz];
      const T: [number, number, number] = [genHexA.tx, genHexA.ty, genHexA.tz];
      const M: [number, number, number] = [genHexA.mx, genHexA.my, genHexA.mz];
      const err = rhpModeAError(V, T, M, genHexA.h);
      if (err) { setValidateResult({ ok: false, msg: err }); return; }
      const card = rhpCard(rhpFromThreePoints(V, T, M));
      const n = maxSurfaceNumber(localSurfaces) + 1;
      const line = `${n} ${card}`;
      const next = localSurfaces.trim() ? `${localSurfaces.trimEnd()}\n${line}` : line;
      setLocalSurfaces(next);
      setSurfaceExpr(`-${n}`);
      setGenCard(card);
      setGenLines([line]);
      setValidateResult(null);
      return;
    }
    const res = autoGenMacrobody(
      lat,
      lat === "2"
        ? { hex: { side: 2 * genHexB.R, H: genHexB.H, cx: genHexB.cx, cy: genHexB.cy, cz: genHexB.cz } }
        : { rect: genRect },
      localSurfaces,
    );
    setLocalSurfaces(res.surfacesText);
    setSurfaceExpr(res.surfaceExpr);
    setGenCard(res.card);
    setGenLines([res.line]);
    setValidateResult(null);
  };

  /* ── 手动模式可选：旧 6 平面 / 6P+2PZ 生成（「手动」可选项）── */
  const handleGenPlanes = () => {
    const res = autoGenerateSurfaces(
      lat,
      lat === "2"
        ? { hex: { side: genPlanes.side, H: genPlanes.H, cx: genPlanes.cx, cy: genPlanes.cy, cz: genPlanes.cz } }
        : { rect: { L: genPlanes.L, W: genPlanes.W, H: genPlanes.H, cx: genPlanes.cx, cy: genPlanes.cy, cz: genPlanes.cz } },
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

  const numField = (label: string, value: number, setter: (v: number) => void, w = 74, disabled = false) => (
    <div style={{ flex: "0 0 auto", width: w }}>
      <label style={lbl}>{label}</label>
      <input
        type="number"
        style={{ ...inp, opacity: disabled ? 0.5 : 1 }}
        value={value}
        disabled={disabled}
        onChange={(e) => setter(parseInt(e.target.value, 10) || 0)}
      />
    </div>
  );

  const dirField = (
    negLabel: string,
    posLabel: string,
    dir: { neg: number; pos: number },
    setter: (d: { neg: number; pos: number }) => void,
    disabled = false,
  ) => (
    <div style={{ display: "flex", gap: 6, alignItems: "flex-end" }}>
      {numField(negLabel, dir.neg, (v) => setter({ ...dir, neg: Math.max(0, v) }), 64, disabled)}
      {numField(posLabel, dir.pos, (v) => setter({ ...dir, pos: Math.max(0, v) }), 64, disabled)}
    </div>
  );

  /* ── 保存（项12 压缩 + 项13 判环阻止 + 体积告警）── */
  const handleSave = () => {
    // 项13：基于当前 deck cells 构造 sub_by_u fill 图 → 判环 → 阻止保存
    const subByU: Record<string, CycleCellLike[]> = {};
    for (const c of deckCells) {
      const u = (c.u ?? "").trim();
      if (!u) continue;
      (subByU[u] ??= []).push({ cellNum: c.num, material: c.mat, fill: c.fill, fill_grid: c.fill_grid });
    }
    const cyc = detectFillCycle(subByU);
    if (cyc.cycle && cyc.chain.length >= 2) {
      const [a, b] = cyc.chain;
      const pen = cyc.chain[cyc.chain.length - 2];
      alert(`U=${a} 的格元填了 U=${b}，而 U=${pen} 的格元又引用 U=${a}，存在循环嵌套`);
      return;
    }
    const d = effectiveDims;
    const r = currentRange;
    const fg: FillGridJson = { lat, kind: "lattice", range: r, dims: d, cells, raw: "" };
    // 项12：编辑器保存路径 nR 压缩（导入路径保持源 raw）；只压条目段，防相同 range token 被折叠
    const entriesRaw = compressRaw(cellsToRaw({ ...fg, range: [] }));
    fg.raw = `${fg.range.join(" ")} ${entriesRaw}`;
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
  const volumeWarning = useMemo(
    () => latticeVolumeWarning({ lat, kind: "lattice", range: currentRange, dims: effectiveDims, cells, raw: "" }),
    [lat, currentRange, effectiveDims, cells],
  );

  const footer = React.createElement(React.Fragment, null,
    React.createElement("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
    step > 0 &&
      React.createElement("button", { type: "button", className: "btn btn-ghost btn-sm", style: { marginLeft: 8 }, onClick: () => setStep(step - 1) },
        "上一步"),
    step < 3 &&
      React.createElement("button", { type: "button", className: "btn btn-primary btn-sm", style: { marginLeft: 8 }, onClick: () => setStep(step + 1) },
        "下一步"),
    step === 3 &&
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
      /* 步骤0：类型与尺寸 + 六个方向层数空（MCNP 习惯 -N:M） */
      step === 0 &&
        React.createElement("div", null,
          React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 14 } },
            React.createElement("button", {
              type: "button",
              onClick: () => handleLatChange("1"),
              style: { ...btn, border: lat === "1" ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: lat === "1" ? "rgba(76,159,232,0.15)" : "var(--bg-input)" },
            }, "矩形 (lat=1)"),
            React.createElement("button", {
              type: "button",
              onClick: () => handleLatChange("2"),
              style: { ...btn, border: lat === "2" ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: lat === "2" ? "rgba(76,159,232,0.15)" : "var(--bg-input)" },
            }, "六棱柱 (lat=2)"),
          ),
          React.createElement("div", { style: { display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 8 } },
            lat === "1"
              ? React.createElement(React.Fragment, null,
                  dirField("x 向左", "x 向右", xDir, setXDir, !sizeEditable),
                  dirField("y 向前", "y 向后", yDir, setYDir, !sizeEditable),
                  dirField("z 向下", "z 向上", zDir, setZDir, !sizeEditable),
                )
              : React.createElement(React.Fragment, null,
                  dirField("水平 向左", "水平 向右", xDir, setXDir),
                  dirField("斜向 向左下", "斜向 向右上", yDir, setYDir),
                  dirField("轴向 向下", "轴向 向上", zDir, setZDir),
                ),
          ),
          lat === "2" &&
            React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)", marginBottom: 6 } },
              `六棱柱 i:j:k 是沿两条 60° 格矢（a1 水平 / a2 斜向）的格位号 + 轴向 k，不是笛卡尔 x/y；格位中心 x=(i+j/2)·pitch、y=j·pitch·√3/2。三轴层数独立，六边形物理边界由 RHP 宏体截断。`),
          React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)" } },
            `范围：${currentRange.join("  ")} · 共 ${cellCount} 格位`),
        ),
      /* 步骤1：材料锁死 + 曲面（宏体自动 vs 手动互斥，项3/4） */
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
          React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 10 } },
            React.createElement("button", { type: "button", onClick: () => setAutoMode(true), style: { ...btn, border: autoMode ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: autoMode ? "rgba(76,159,232,0.15)" : "var(--bg-input)" } },
              "自动生成宏体"),
            React.createElement("button", { type: "button", onClick: () => setAutoMode(false), style: { ...btn, border: !autoMode ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: !autoMode ? "rgba(76,159,232,0.15)" : "var(--bg-input)" } },
              "手动填写曲面"),
          ),
          autoMode ? (
            /* ── 自动模式：宏体参数 + 生成 + 子预览 ── */
            React.createElement("div", { style: { border: "1px solid var(--border-glass)", borderRadius: 8, padding: 10 } },
              React.createElement("div", { style: { fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 } },
                lat === "2" ? "六棱柱宏体 RHP（MCNP 全量参数）" : "矩形宏体 RPP（长宽高+中心）"),
              React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 8 } },
                lat === "2"
                  ? (rhpMode === "B"
                      ? React.createElement(React.Fragment, null,
                          numField("外接半径 R", genHexB.R, (v) => { setRManual(true); setGenHexB({ ...genHexB, R: v }); }),
                          numField("高 h", genHexB.H, (v) => setGenHexB({ ...genHexB, H: v })),
                          React.createElement("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: suggestR, title: "按当前 i/j 格阵范围重算外接半径（OWEN 模式：宏体包住全部格位）" },
                            "按格阵重算"),
                        )
                      : React.createElement(React.Fragment, null,
                          numField("Vx", genHexA.vx, (v) => setGenHexA({ ...genHexA, vx: v })),
                          numField("Vy", genHexA.vy, (v) => setGenHexA({ ...genHexA, vy: v })),
                          numField("Vz", genHexA.vz, (v) => setGenHexA({ ...genHexA, vz: v })),
                          numField("Tx", genHexA.tx, (v) => setGenHexA({ ...genHexA, tx: v })),
                          numField("Ty", genHexA.ty, (v) => setGenHexA({ ...genHexA, ty: v })),
                          numField("Tz", genHexA.tz, (v) => setGenHexA({ ...genHexA, tz: v })),
                          numField("Mx", genHexA.mx, (v) => setGenHexA({ ...genHexA, mx: v })),
                          numField("My", genHexA.my, (v) => setGenHexA({ ...genHexA, my: v })),
                          numField("Mz", genHexA.mz, (v) => setGenHexA({ ...genHexA, mz: v })),
                          numField("高 h", genHexA.h, (v) => setGenHexA({ ...genHexA, h: v })),
                        ))
                  : React.createElement(React.Fragment, null,
                      numField("长 L", genRect.L, (v) => setGenRect({ ...genRect, L: v })),
                      numField("宽 W", genRect.W, (v) => setGenRect({ ...genRect, W: v })),
                      numField("高 H", genRect.H, (v) => setGenRect({ ...genRect, H: v })),
                    ),
                numField("中心X", lat === "2" ? genHexB.cx : genRect.cx, (v) => lat === "2" ? setGenHexB({ ...genHexB, cx: v }) : setGenRect({ ...genRect, cx: v })),
                numField("中心Y", lat === "2" ? genHexB.cy : genRect.cy, (v) => lat === "2" ? setGenHexB({ ...genHexB, cy: v }) : setGenRect({ ...genRect, cy: v })),
                numField("中心Z", lat === "2" ? genHexB.cz : genRect.cz, (v) => lat === "2" ? setGenHexB({ ...genHexB, cz: v }) : setGenRect({ ...genRect, cz: v })),
                React.createElement("button", { type: "button", className: "btn btn-primary btn-sm", onClick: handleAutoGen },
                  "生成宏体卡并填表达式"),
              ),
              lat === "2" && rhpMode === "B" &&
                React.createElement("div", { style: { fontSize: 10, color: "var(--text-tertiary)", marginBottom: 6 } },
                  `按格阵 i±${xDir.neg}/${xDir.pos}、j±${yDir.neg}/${yDir.pos} 自动建议 R≈${genHexB.R}（参考格距 2cm），RHP 面恰好包住全部格位；格距 p≈${hexPitch.toFixed(3)}cm（面切最外圈格子外缘）。`),
              lat === "2" &&
                React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 8 } },
                  React.createElement("button", { type: "button", onClick: () => setRhpMode("B"), style: { ...btn, border: rhpMode === "B" ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: rhpMode === "B" ? "rgba(76,159,232,0.15)" : "var(--bg-input)" } },
                    "模式 B：中心+外接半径+高"),
                  React.createElement("button", { type: "button", onClick: () => setRhpMode("A"), style: { ...btn, border: rhpMode === "A" ? "1px solid var(--accent)" : "1px solid var(--border-glass)", background: rhpMode === "A" ? "rgba(76,159,232,0.15)" : "var(--bg-input)" } },
                    "模式 A：三点+高度"),
                  React.createElement("span", { style: { fontSize: 10, color: "var(--text-tertiary)", alignSelf: "center" } },
                    "环数 R、轴向层数 k 已在第 0 步设置，不是 RHP 卡参数"),
                ),
              React.createElement("label", { style: lbl }, "曲面表达式（宏体，自动生成后只读）"),
              React.createElement("textarea", {
                style: { ...tarea, width: "100%" },
                value: surfaceExpr,
                readOnly: true,
                placeholder: lat === "2" ? "如 -6（单 RHP）" : "如 -6（单 RPP）",
              }),
              genCard && React.createElement("div", { style: { marginTop: 6, fontSize: 11, fontFamily: "Consolas,monospace", color: "var(--text-secondary)", whiteSpace: "pre-wrap" } },
                genLines.join("\n")),
              genLines.length > 0 && genCard &&
                React.createElement("div", { style: { marginTop: 8, display: "flex", gap: 10, alignItems: "flex-start" } },
                  React.createElement(MacrobodyPreview, { lat, surfaceExpr, surfacesText: localSurfaces }),
                ),
              validateResult &&
                React.createElement("div", { style: { fontSize: 11, marginTop: 4, color: validateResult.ok ? "#2e7d32" : "#e53935" } },
                  validateResult.ok ? "✓ 曲面通过" : `✗ ${validateResult.msg || "曲面不构成合法格元"}`),
            )
          ) : (
            /* ── 手动模式：可编辑 + 失焦校验 + 可选旧平面生成 ── */
            React.createElement("div", null,
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
                  "手动可选：生成 6 平面 / 6P+2PZ（旧路径，可另存为「手动」写法）"),
                React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" } },
                  lat === "2"
                    ? React.createElement(React.Fragment, null,
                        numField("边长", genPlanes.side, (v) => setGenPlanes({ ...genPlanes, side: v })),
                        numField("高", genPlanes.H, (v) => setGenPlanes({ ...genPlanes, H: v })),
                      )
                    : React.createElement(React.Fragment, null,
                        numField("长", genPlanes.L, (v) => setGenPlanes({ ...genPlanes, L: v })),
                        numField("宽", genPlanes.W, (v) => setGenPlanes({ ...genPlanes, W: v })),
                        numField("高", genPlanes.H, (v) => setGenPlanes({ ...genPlanes, H: v })),
                      ),
                  numField("中心X", genPlanes.cx, (v) => setGenPlanes({ ...genPlanes, cx: v })),
                  numField("中心Y", genPlanes.cy, (v) => setGenPlanes({ ...genPlanes, cy: v })),
                  numField("中心Z", genPlanes.cz, (v) => setGenPlanes({ ...genPlanes, cz: v })),
                  React.createElement("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: handleGenPlanes },
                    "生成平面卡"),
                ),
              ),
            )
          ),
        ),
      /* 步骤2：画布涂色 + 调色板（同屏，项6/7）+ 3D 子预览 */
      step === 2 &&
        React.createElement("div", { style: { display: "flex", gap: 14, alignItems: "flex-start" } },
          React.createElement("div", { style: { flex: "0 0 auto", maxWidth: 480, overflow: "auto" } },
            React.createElement(LatticeCanvas, {
              lat,
              dims: effectiveDims,
              cells,
              palette,
              selectedU,
              onCellChange: paintCell,
              // 六棱柱：格距按可用宽度适配（440px 内完整显示全部格位）；矩形固定 22
              pitch: lat === "2" ? fitHexPitch(effectiveDims, 440) : 22,
            }),
          ),
          React.createElement("div", { style: { flex: "0 0 190px" } },
            React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)", marginBottom: 8 } },
              `调色板（${universeList.length} 宇宙：void ∪ 格阵 fill 表 ∪ deck u=）`),
            React.createElement("div", { style: { display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 } },
              universeList.map((u) =>
                React.createElement("button", {
                  key: u,
                  type: "button",
                  "data-testid": `palette-${u}`,
                  onClick: () => setSelectedU(u),
                  title: u === "0" ? "void（涂透明格位）" : `U=${u}`,
                  style: {
                    minWidth: 46, height: 30, borderRadius: 6,
                    border: selectedU === u ? "2px solid #fff" : "1px solid rgba(255,255,255,0.25)",
                    background: u === "0" ? "rgba(255,255,255,0.08)" : getUniverseColor(u, palette),
                    color: "#fff", fontSize: 11, fontWeight: 600, cursor: "pointer",
                    boxShadow: selectedU === u ? "0 0 0 2px var(--accent)" : "none",
                  },
                }, u === "0" ? "∅0" : `U=${u}`),
              ),
            ),
            React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "center", marginBottom: 10 } },
              React.createElement("input", {
                style: { ...inp, width: 96 },
                placeholder: "自定义宇宙号",
                value: customU,
                onChange: (e: React.ChangeEvent<HTMLInputElement>) => setCustomU(e.target.value),
              }),
              React.createElement("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: addCustomUniverse },
                "添加"),
            ),
            React.createElement("div", { style: { fontSize: 12, color: "var(--text-secondary)" } },
              `当前涂色笔：U=${selectedU}`),
          ),
          React.createElement("div", { style: { flex: 1, minWidth: 240, height: 380 } },
            React.createElement(LatticePreview3D, { lat, dims: effectiveDims, cells, palette, pitch: 1, height: Math.max(0.5, effectiveDims[2] || 1) }),
          ),
        ),
      /* 步骤3：保存摘要（体积告警 + 判环已在保存时） */
      step === 3 &&
        React.createElement("div", null,
          React.createElement("div", { style: { fontSize: 11, color: "var(--text-secondary)", marginBottom: 8 } },
            "保存将写入栅元卡："),
          React.createElement("div", { style: { fontFamily: "Consolas,monospace", fontSize: 12, lineHeight: 1.9, background: "var(--bg-input)", border: "1px solid var(--border-glass)", borderRadius: 8, padding: 10 } },
            React.createElement("div", null, `material = 0   density = ""`),
            React.createElement("div", null, `u = ${latticeU || "—"}`),
            React.createElement("div", null, `lat = ${lat}`),
            React.createElement("div", null, `fill = ${currentRange.join(" ")}`),
            React.createElement("div", null, `surface_expr = ${surfaceExpr || "（空）"}`),
            React.createElement("div", null, `fill_grid = ${serializeFillGrid({ lat, kind: "lattice", range: currentRange, dims: effectiveDims, cells, raw: "" })}`),
          ),
          !surfaceExpr.trim() &&
            React.createElement("div", { style: { fontSize: 11, color: "#e0a12e", marginTop: 8 } },
              "⚠ 曲面表达式为空，请回到「材料与曲面」填写或自动生成。"),
          volumeWarning &&
            React.createElement("div", { style: { fontSize: 11, color: "#e0a12e", marginTop: 8 } },
              `⚠ ${volumeWarning}`),
        ),
    ),
  );
}
