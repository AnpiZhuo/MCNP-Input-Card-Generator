/**
 * PtracRenderer — Three.js 径迹渲染器（契约 ptrac-visualization.md §4）
 *
 * 场景组装：几何外壳 STL（复用 STLLoader + cellMaterial semi 半透明）+ 每条历史一条
 * THREE.LineSegments 折线（顶点色 = 粒子类型基色 × 能量深浅 trackShade）+ OrbitControls
 * + 归一化 offset（alignWorld 复用，与体积窗口同一不变量）。
 *
 * 数据流：宿主 PtracWindow 读桥 → ptracParse → setTracks(tracks) → 外壳+径迹共 offset
 * 对齐 + computeFramingBox 自动取景。交互：粒子类型显隐 / 透明度 / 单径迹高亮 / 外壳开关。
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { computeCameraParams, type CameraParams } from "../three/cameraParams";
import { createRenderLoop } from "../three/renderGate";
import { buildCellMaterial, DEFAULT_SHELL_OPACITY } from "../three/cellMaterial";
import {
  unionBoxes, boxCenter, boxSize, translateToCenter, computeFramingBox, applyOffsetToBox,
  type AABB, type Vec3, type Translatable,
} from "../volume/alignWorld";
import { trackColor, trackShade, normalizeEnergy01, energyRangeOfTracks } from "./trackColors";
import type { PtracTrack } from "../utils/api";

export interface PtracCellView {
  num: string;
  mat: string;
  comment: string;
  color: string;
}

export interface PtracRendererOptions {
  stlData: Record<string, string>;
  cellViews: PtracCellView[];
  onError?: (msg: string) => void;
}

export interface PtracRendererHandle {
  setTracks(tracks: PtracTrack[]): void;
  setShellVisible(v: boolean): void;
  setShellOpacity(v: number): void;
  setTrackOpacity(v: number): void;
  setParticleVisible(particle: string, vis: boolean): void;
  setHighlight(nps: number | null): void;
  dispose(): void;
}

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

/** 粒子类型 → 显隐分组 key（n/p/e/other） */
function particleGroup(particle: string): string {
  return particle === "n" || particle === "p" || particle === "e" ? particle : "other";
}

/** 单条径迹 → LineSegments 几何（顶点色 = 类型色 × 能量深浅；世界坐标，待统一 offset） */
function buildTrackGeometry(track: PtracTrack, energyRange: { min: number; max: number }): THREE.BufferGeometry | null {
  const pts = track.points || [];
  const n = pts.length;
  if (n < 2) return null;
  const base = trackColor(track.particle);
  const segs = n - 1;
  const positions = new Float32Array(segs * 2 * 3);
  const colors = new Float32Array(segs * 2 * 3);
  for (let i = 0; i < segs; i++) {
    const a = pts[i];
    const b = pts[i + 1];
    const ea = normalizeEnergy01(Number(a[4] ?? 0), energyRange);
    const eb = normalizeEnergy01(Number(b[4] ?? 0), energyRange);
    const ca = new THREE.Color(trackShade(base, ea));
    const cb = new THREE.Color(trackShade(base, eb));
    const o = i * 6;
    positions[o] = a[0]; positions[o + 1] = a[1]; positions[o + 2] = a[2];
    positions[o + 3] = b[0]; positions[o + 4] = b[1]; positions[o + 5] = b[2];
    colors[o] = ca.r; colors[o + 1] = ca.g; colors[o + 2] = ca.b;
    colors[o + 3] = cb.r; colors[o + 4] = cb.g; colors[o + 5] = cb.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  return geo;
}

function box3ToAabb(b: THREE.Box3): AABB {
  return { min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] };
}

export function createPtracRenderer(canvas: HTMLCanvasElement, opts: PtracRendererOptions): PtracRendererHandle {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(rect.width || 800, 1);
  const h = Math.max(rect.height || 600, 1);

  const initCam = computeCameraParams([0, 0, 0], [10, 10, 10]);
  const camera = new THREE.PerspectiveCamera(45, w / h, initCam.near, initCam.far);
  camera.up.set(0, 0, 1); // Z-up（MCNP 全局坐标）

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setSize(w, h, false);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const ambient = new THREE.AmbientLight(0x8888aa, 0.35);
  scene.add(ambient);
  const dirlight = new THREE.DirectionalLight(0xffffff, 1.6);
  dirlight.position.set(30, 40, 25);
  scene.add(dirlight);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;

  /* ── 外壳 STL（复用 cellMaterial semi 半透明）── */
  const shellMeshes: THREE.Mesh[] = [];
  const shellRawBounds: THREE.Box3[] = [];
  let shellOpacity = DEFAULT_SHELL_OPACITY;
  let shellVisible = true;

  function cellIndex(cellNum: string): number {
    const views = opts.cellViews || [];
    for (let i = 0; i < views.length; i++) if (views[i].num === cellNum) return i;
    return 0;
  }

  function shellSpecFor(color: string) {
    return buildCellMaterial({
      color,
      transparentMode: shellOpacity >= 1 ? "opaque" : "semi",
      opacity: shellOpacity,
    });
  }

  function loadShell(): void {
    const loader = new STLLoader();
    const stlData = opts.stlData || {};
    for (const key in stlData) {
      try {
        const raw = atob(stlData[key]);
        const buf = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i) & 0xff;
        const geo = loader.parse(buf.buffer as ArrayBuffer);
        const cv = (opts.cellViews || [])[cellIndex(key)] || { color: "#888888" };
        const spec = shellSpecFor(cv.color);
        const mat = new THREE.MeshStandardMaterial({
          color: spec.color, roughness: 0.3, metalness: 0,
          transparent: spec.transparent, opacity: spec.opacity,
          depthWrite: spec.depthWrite, side: THREE.FrontSide,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.userData.color = cv.color;
        scene.add(mesh);
        shellMeshes.push(mesh);
        geo.computeBoundingBox();
        if (geo.boundingBox) shellRawBounds.push(geo.boundingBox.clone());
      } catch (e) {
        console.error("[ptrac] STL load error for cell", key, e);
      }
    }
  }

  /* ── 径迹 LineSegments ── */
  const trackLines: THREE.LineSegments[] = [];
  let pointMesh: THREE.Points | null = null; // 单点径迹（<2 点无法连线）→ 圆点
  let worldBox: AABB | null = null;
  let trackOpacity = 1;
  const particleVisible: Record<string, boolean> = { n: true, p: true, e: true, other: true };
  let highlightNps: number | null = null;

  function applyVisibility(): void {
    for (const l of trackLines) {
      if (highlightNps != null) {
        l.visible = l.userData.nps === highlightNps;
      } else {
        l.visible = particleVisible[particleGroup(l.userData.particle)];
      }
    }
    if (pointMesh) {
      pointMesh.visible = highlightNps == null; // 单点云不做高亮（点极少，保持可见）
    }
    markDirty();
  }

  function clearTracks(): void {
    for (const l of trackLines) {
      scene.remove(l);
      l.geometry.dispose();
      (l.material as THREE.Material).dispose();
    }
    trackLines.length = 0;
    if (pointMesh) {
      scene.remove(pointMesh);
      pointMesh.geometry.dispose();
      (pointMesh.material as THREE.Material).dispose();
      pointMesh = null;
    }
  }

  /** 单点径迹（<2 点）→ 圆点云几何；无则 null */
  function buildPointGeometry(list: PtracTrack[]): THREE.BufferGeometry | null {
    const singles: { x: number; y: number; z: number; particle: string }[] = [];
    for (const t of list) {
      const pts = t.points || [];
      if (pts.length === 1) {
        singles.push({ x: Number(pts[0][0]), y: Number(pts[0][1]), z: Number(pts[0][2]), particle: t.particle });
      }
    }
    if (singles.length === 0) return null;
    const positions = new Float32Array(singles.length * 3);
    const colors = new Float32Array(singles.length * 3);
    const fallback = trackShade(trackColor("other"), 0.5);
    singles.forEach((s, i) => {
      positions[i * 3] = s.x; positions[i * 3 + 1] = s.y; positions[i * 3 + 2] = s.z;
      const c = new THREE.Color(trackShade(trackColor(s.particle), 0.2) || fallback);
      colors[i * 3] = c.r; colors[i * 3 + 1] = c.g; colors[i * 3 + 2] = c.b;
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return geo;
  }

  /* ── 统一归一化对齐（alignWorld 复用）：外壳与径迹共 offset ──
   * offset 只在首帧算一次（外壳 + 全量径迹并集中心）；后续抽样重建的径迹
   * 直接用已存 offset 平移，避免重复平移外壳（否则外壳被二次位移）。 */
  let alignedOffset: Vec3 | null = null;
  function alignAndFrame(): void {
    if (alignedOffset) return;
    const shellBox: AABB | null = shellRawBounds.length > 0
      ? (() => {
          const tb = new THREE.Box3();
          for (const b of shellRawBounds) tb.union(b);
          return box3ToAabb(tb);
        })()
      : null;
    // 径迹为空（PTRAC 文件 0 事件，如 TYPE 与 MODE 不匹配）时退化为只给外壳取景——
    // 否则 camera 停在 init、外壳缩在画面角落像一块"莫名其妙的底面"（用户实测反馈）。
    if (!shellBox && !worldBox) return;
    const boxes: AABB[] = [];
    if (shellBox) boxes.push(shellBox);
    if (worldBox) boxes.push(worldBox);
    const union = unionBoxes(boxes);
    const geos: Translatable[] = [
      ...shellMeshes.map((m) => m.geometry),
      ...trackLines.map((l) => l.geometry),
    ];
    if (pointMesh) geos.push(pointMesh.geometry);
    const offset = translateToCenter(geos, union);
    // A2.1 同款自动取景：外壳≫径迹时以径迹为主；相机用 offset 后的场景坐标
    const framing = computeFramingBox(shellBox, worldBox ?? shellBox!);
    const sceneBox = applyOffsetToBox(framing, offset);
    const cp: CameraParams = computeCameraParams(boxCenter(sceneBox), boxSize(sceneBox));
    camera.near = cp.near;
    camera.far = cp.far;
    camera.position.set(cp.position[0], cp.position[1], cp.position[2]);
    controls.target.set(cp.target[0], cp.target[1], cp.target[2]);
    controls.minDistance = cp.minDistance;
    controls.maxDistance = cp.maxDistance;
    camera.updateProjectionMatrix();
    controls.update();
    alignedOffset = offset;
  }

  /* ── 按需渲染门（renderGate 复用）── */
  const renderLoop = createRenderLoop({
    onRender: () => {
      controls.update();
      renderer.render(scene, camera);
    },
  });
  const markDirty = renderLoop.markDirty;
  controls.addEventListener("change", () => markDirty());

  function resizeRenderer(): void {
    const r = canvas.getBoundingClientRect();
    const w2 = Math.max(r.width, 1);
    const h2 = Math.max(r.height, 1);
    camera.aspect = w2 / h2;
    camera.updateProjectionMatrix();
    renderer.setSize(w2, h2, false);
    markDirty();
  }
  let ro: ResizeObserver | null = null;
  if (typeof ResizeObserver !== "undefined") {
    ro = new ResizeObserver(resizeRenderer);
    if (canvas.parentElement) ro.observe(canvas.parentElement);
  }
  setTimeout(resizeRenderer, 100);

  // 首帧：加载外壳（径迹由 setTracks 到达后统一对齐）
  loadShell();
  markDirty();

  const handle: PtracRendererHandle = {
    setTracks(tracks: PtracTrack[]) {
      clearTracks();
      const list = tracks || [];
      const energyRange = energyRangeOfTracks(list);
      // 径迹点全局 worldBox（对齐 + 取景用）
      let min: Vec3 = [Infinity, Infinity, Infinity];
      let max: Vec3 = [-Infinity, -Infinity, -Infinity];
      for (const t of list) {
        for (const p of t.points || []) {
          for (let i = 0; i < 3; i++) {
            const v = Number(p[i]);
            if (Number.isFinite(v)) {
              if (v < min[i]) min[i] = v;
              if (v > max[i]) max[i] = v;
            }
          }
        }
      }
      worldBox = Number.isFinite(min[0])
        ? { min, max }
        : null;
      for (const t of list) {
        const geo = buildTrackGeometry(t, energyRange);
        if (!geo) continue;
        const mat = new THREE.LineBasicMaterial({
          vertexColors: true,
          transparent: trackOpacity < 1,
          opacity: trackOpacity,
          depthTest: true,
        });
        const line = new THREE.LineSegments(geo, mat);
        line.userData.nps = t.nps;
        line.userData.particle = t.particle;
        scene.add(line);
        trackLines.push(line);
      }
      // 单点径迹（<2 点无法连线）→ 圆点云，避免文件稀疏时画布空白（用户实测反馈）
      const pGeo = buildPointGeometry(list);
      if (pGeo) {
        const pMat = new THREE.PointsMaterial({
          vertexColors: true,
          size: 6,
          sizeAttenuation: true,
          transparent: trackOpacity < 1,
          opacity: trackOpacity,
          depthTest: true,
        });
        pointMesh = new THREE.Points(pGeo, pMat);
        scene.add(pointMesh);
      }
      // 已对齐（首帧后）→ 新径迹直接用已存 offset 平移；否则首帧统一对齐
      if (alignedOffset) {
        for (const l of trackLines) {
          l.geometry.translate(alignedOffset[0], alignedOffset[1], alignedOffset[2]);
        }
        pointMesh?.geometry.translate(alignedOffset[0], alignedOffset[1], alignedOffset[2]);
      } else {
        alignAndFrame();
      }
      applyVisibility();
      markDirty();
    },
    setShellVisible(v: boolean) {
      shellVisible = v;
      for (const m of shellMeshes) m.visible = v;
      markDirty();
    },
    setShellOpacity(v: number) {
      shellOpacity = clamp01(v);
      for (const m of shellMeshes) {
        const spec = shellSpecFor(m.userData.color);
        const mat = m.material as THREE.MeshStandardMaterial;
        mat.color.set(spec.color);
        mat.transparent = spec.transparent;
        mat.depthWrite = spec.depthWrite;
        mat.opacity = spec.opacity;
        mat.needsUpdate = true;
      }
      markDirty();
    },
    setTrackOpacity(v: number) {
      trackOpacity = clamp01(v);
      for (const l of trackLines) {
        const mat = l.material as THREE.LineBasicMaterial;
        mat.transparent = trackOpacity < 1;
        mat.opacity = trackOpacity;
        mat.needsUpdate = true;
      }
      markDirty();
    },
    setParticleVisible(particle: string, vis: boolean) {
      particleVisible[particleGroup(particle)] = vis;
      applyVisibility();
    },
    setHighlight(nps: number | null) {
      highlightNps = nps;
      applyVisibility();
    },
    dispose() {
      ro?.disconnect();
      controls.dispose();
      renderLoop.dispose();
      renderer.dispose();
      shellMeshes.forEach((m) => {
        m.geometry.dispose();
        (m.material as THREE.Material).dispose();
      });
      trackLines.forEach((l) => {
        l.geometry.dispose();
        (l.material as THREE.Material).dispose();
      });
      scene.clear();
    },
  };
  return handle;
}
