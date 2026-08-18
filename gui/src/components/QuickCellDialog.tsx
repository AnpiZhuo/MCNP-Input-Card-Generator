/**
 * QuickCellDialog — 「快捷建栅元」弹窗
 *
 * 左侧：形状选择（RCC/RPP/SPH，一次一种）+ 参数输入 + 材料/imp；
 * 右侧：实时线框预览（只对该窗口正在编辑的体生效，形状+切分线+局部坐标轴）。
 *
 * 生成结果由父组件（GeometryTab）追加到曲面卡/TR 卡/栅元列表；
 * 编号规则与生成逻辑全部在 gui/src/utils/quickCell.ts（纯函数）。
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import FloatingDialog from "./FloatingDialog";
import { computeCameraParams } from "../three/cameraParams";
import { buildQuickCellPreview } from "../three/quickCellPreview";
import {
  generateQuickCell,
  parseAngleExpr,
  quickCellCounts,
  validateQuickCell,
  type QuickCellResult,
  type QuickShape,
} from "../utils/quickCell";

interface Props {
  surfacesText: string;
  trCardsText: string;
  cellNumbers: number[];
  materials: { number: number; comment?: string; density?: string }[];
  onClose: () => void;
  onGenerate: (result: QuickCellResult) => void;
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

export default function QuickCellDialog({ surfacesText, trCardsText, cellNumbers, materials, onClose, onGenerate }: Props) {
  const [shape, setShape] = useState<QuickShape>("rcc");
  const [rcc, setRcc] = useState({ cx: "0", cy: "0", cz: "0", hx: "0", hy: "0", hz: "10", r: "2", rings: "2", segments: "3" });
  const [sph, setSph] = useState({ x: "0", y: "0", z: "0", r: "5", shells: "3" });
  const [rpp, setRpp] = useState({
    L: "2", W: "2", H: "2",
    cx: "0", cy: "0", cz: "0",
    roll: "0", pitch: "0", yaw: "0",
    nx: "2", ny: "2", nz: "2",
  });
  const [unit, setUnit] = useState<"deg" | "rad">("deg");
  const angleFocusRef = useRef<"roll" | "pitch" | "yaw">("roll");
  const [material, setMaterial] = useState("0");
  const [impN, setImpN] = useState(false);
  const [impP, setImpP] = useState(false);
  const [impE, setImpE] = useState(false);

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

  /* ── 预览：场景/相机/渲染（按需渲染，输入变化才重建） ── */
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const previewRef = useRef<ReturnType<typeof buildQuickCellPreview> | null>(null);
  const dirtyRef = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    const w = Math.max(rect.width, 120);
    const h = Math.max(rect.height, 120);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d0d22);
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 1e5);
    camera.up.set(0, 0, 1); // Z 朝上（数学/物理/MCNP 惯例，与主 3D 预览/体积窗口一致）
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setSize(w, h, false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    camera.position.set(8, 6, 10);
    camera.lookAt(0, 0, 0);
    controls.target.set(0, 0, 0);

    sceneRef.current = scene;
    cameraRef.current = camera;
    controlsRef.current = controls;
    rendererRef.current = renderer;

    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      controls.update();
      if (dirtyRef.current) {
        renderer.render(scene, camera);
        dirtyRef.current = false;
      }
    };
    raf = requestAnimationFrame(loop);
    controls.addEventListener("change", () => { dirtyRef.current = true; });

    const ro = new ResizeObserver(() => {
      const r = wrap.getBoundingClientRect();
      if (r.width > 10 && r.height > 10) {
        renderer.setSize(r.width, r.height, false);
        camera.aspect = r.width / r.height;
        camera.updateProjectionMatrix();
        dirtyRef.current = true;
      }
    });
    ro.observe(wrap);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      sceneRef.current = null;
      cameraRef.current = null;
      controlsRef.current = null;
      rendererRef.current = null;
    };
  }, []);

  // 输入变化（防抖 100ms）→ 重建线框并取景
  useEffect(() => {
    const timer = setTimeout(() => {
      const scene = sceneRef.current;
      if (!scene) return;
      if (previewRef.current) {
        scene.remove(previewRef.current.group);
        previewRef.current.dispose();
        previewRef.current = null;
      }
      if (!error) {
        const prev = buildQuickCellPreview(config.shape as QuickShape, config.config as any);
        scene.add(prev.group);
        previewRef.current = prev;
        const box = new THREE.Box3().setFromObject(prev.group);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const ext = Math.max(size.x, size.y, size.z, 1e-3);
        const cp = computeCameraParams([center.x, center.y, center.z], [ext, ext, ext]);
        const camera = cameraRef.current;
        const controls = controlsRef.current;
        if (camera && controls) {
          camera.position.set(cp.position[0], cp.position[1], cp.position[2]);
          camera.near = cp.near;
          camera.far = cp.far;
          camera.updateProjectionMatrix();
          controls.target.set(cp.target[0], cp.target[1], cp.target[2]);
          controls.update();
        }
      }
      dirtyRef.current = true;
    }, 100);
    return () => clearTimeout(timer);
  }, [cfgKey, error]);

  const matDensity = material !== "0" && material !== "" ? materials.find((m) => String(m.number) === material)?.density ?? "" : "";

  const handleGenerate = () => {
    const result = generateQuickCell(config.shape as QuickShape, config.config as any, {
      surfacesText,
      trCardsText,
      cellNumbers,
      materials,
      material,
      impN,
      impP,
      impE,
    });
    onGenerate(result);
    onClose();
  };

  const segBtn = (s: QuickShape, label: string) =>
    React.createElement("button", {
      key: s,
      type: "button",
      style: shape === s ? style.segOn : style.seg,
      onClick: () => setShape(s),
    }, label);

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

  return React.createElement(FloatingDialog, {
    title: "⚡ 快捷建栅元（一次一种形状）",
    onClose,
    width: 940,
    footer: React.createElement(React.Fragment, null,
      React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
      React.createElement("button", {
        className: "btn btn-primary btn-sm",
        disabled: !!error,
        style: { marginLeft: 8, opacity: error ? 0.5 : 1 },
        onClick: handleGenerate,
      }, "生成并加入"),
    ),
  },
    React.createElement("div", { style: { display: "flex", gap: 14, minHeight: 480 } },
      /* 左：参数 */
      React.createElement("div", { style: { width: 360, flexShrink: 0, overflowY: "auto", paddingRight: 4 } },
        React.createElement("div", { style: { ...style.row, marginBottom: 10 } },
          segBtn("rcc", "圆柱 RCC"),
          segBtn("rpp", "六面体 RPP"),
          segBtn("sph", "球 SPH"),
        ),
        inputGroup(),
        React.createElement("div", { style: { ...style.row, marginTop: 8 } },
          React.createElement("div", { style: { ...style.grp, maxWidth: 150 } },
            React.createElement("label", { style: style.lbl }, "材料"),
            React.createElement("select", {
              style: style.inp,
              value: material,
              onChange: (e: React.ChangeEvent<HTMLSelectElement>) => setMaterial(e.target.value),
            },
              React.createElement("option", { value: "0" }, "M0 — 真空"),
              materials.map((m) => React.createElement("option", { key: m.number, value: String(m.number) }, `M${m.number}${m.comment ? " — " + m.comment : ""}`)),
            ),
          ),
          React.createElement("div", { style: { ...style.grp, maxWidth: 130 } },
            React.createElement("label", { style: style.lbl }, "IMP"),
            React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center", height: 28 } },
              React.createElement("label", { style: { fontSize: 11, color: "var(--text-secondary)", display: "flex", gap: 3, alignItems: "center" } },
                React.createElement("input", { type: "checkbox", checked: impN, onChange: (e) => setImpN(e.target.checked) }), "N"),
              React.createElement("label", { style: { fontSize: 11, color: "var(--text-secondary)", display: "flex", gap: 3, alignItems: "center" } },
                React.createElement("input", { type: "checkbox", checked: impP, onChange: (e) => setImpP(e.target.checked) }), "P"),
              React.createElement("label", { style: { fontSize: 11, color: "var(--text-secondary)", display: "flex", gap: 3, alignItems: "center" } },
                React.createElement("input", { type: "checkbox", checked: impE, onChange: (e) => setImpE(e.target.checked) }), "E"),
            ),
          ),
        ),
        React.createElement("div", { style: style.info },
          `将生成 ${counts.surfaceCount} 个曲面 / ${counts.cellCount} 个栅元`
          + (material !== "0" && matDensity ? `；材料 M${material} 密度自动填入 ${matDensity}` : material !== "0" ? "；材料未定义密度，密度留空待填" : ""),
        ),
        error && React.createElement("div", { style: style.err }, error),
      ),
      /* 右：实时预览 */
      React.createElement("div", {
        ref: wrapRef,
        style: { flex: 1, minWidth: 260, position: "relative", border: "1px solid var(--border-glass)", borderRadius: 8, overflow: "hidden" },
      },
        React.createElement("canvas", { ref: canvasRef, style: { width: "100%", height: "100%", display: "block" } }),
        React.createElement("div", { style: { position: "absolute", left: 8, bottom: 8, fontSize: 10, color: "rgba(241,241,249,0.55)", pointerEvents: "none" } },
          "滚轮缩放 · 拖拽旋转（红 X / 绿 Y / 蓝 Z）"),
      ),
    ),
  );
}
