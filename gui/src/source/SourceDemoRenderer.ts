/**
 * SourceDemoRenderer — SDEF 源粒子演示渲染器（契约 source-demo-visualization.md §5）
 *
 * 场景组装：几何外壳 STL（复用 STLLoader + cellMaterial semi 半透明）+ 500 粒子
 * Points 点云（vertexColors：粒子类型基色 × 能量深浅 trackColors）+ 方向短线
 * LineSegments（出生点 → 沿方向一小段）+ OrbitControls + 归一化 offset（alignWorld
 * 复用，与 PTRAC/体积窗口同一不变量）。
 *
 * 数据流：宿主 SourceDemoWindow 读桥 → fetchPreview3dStl 外壳 + sourceDemoSample
 * 抽样 → setParticles(particles, energyRange) → 外壳+粒子共 offset 对齐 + 自动取景。
 * 交互：外壳开关 / 透明度 / 方向线长度 / 粒子透明度。
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { computeCameraParams, type CameraParams } from "../three/cameraParams";
import { createRenderLoop } from "../three/renderGate";
import { buildCellMaterial, DEFAULT_SHELL_OPACITY } from "../three/cellMaterial";
import {
  unionBoxes, boxCenter, boxSize, translateToCenter, applyOffsetToBox,
  type AABB, type Vec3, type Translatable,
} from "../volume/alignWorld";
import { trackColor, trackShade, normalizeEnergy01, type ParticleKey } from "../ptrac/trackColors";
import type { SourceParticle } from "../utils/api";

export interface SourceCellView {
  num: string;
  mat: string;
  comment: string;
  color: string;
}

export interface SourceDemoRendererOptions {
  stlData: Record<string, string>;
  cellViews: SourceCellView[];
  onError?: (msg: string) => void;
}

export interface SourceDemoRendererHandle {
  setParticles(particles: SourceParticle[], energyRange: { min: number; max: number }): void;
  setShellVisible(v: boolean): void;
  setShellOpacity(v: number): void;
  setParticleOpacity(v: number): void;
  setDirectionLength(scale: number): void;
  dispose(): void;
}

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

function box3ToAabb(b: THREE.Box3): AABB {
  return { min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] };
}

export function createSourceDemoRenderer(
  canvas: HTMLCanvasElement,
  opts: SourceDemoRendererOptions,
): SourceDemoRendererHandle {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(rect.width || 800, 1);
  const h = Math.max(rect.height || 600, 1);

  const initCam = computeCameraParams([0, 0, 0], [10, 10, 10]);
  const camera = new THREE.PerspectiveCamera(45, w / h, initCam.near, initCam.far);
  camera.up.set(0, 0, 1); // Z-up（MCNP 全局坐标）

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
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

  /* ── 外壳 STL ── */
  const shellMeshes: THREE.Mesh[] = [];
  const shellRawBounds: THREE.Box3[] = [];
  let shellOpacity = DEFAULT_SHELL_OPACITY;
  let shellVisible = true;

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
        // 按栅元号取色（stlData 的 key 就是栅元号）；取不到才回退首个栅元。
        // 旧实现恒用 cellViews[0] ⇒ 所有外壳同色（多材料模型看不出栅元区分）。
        const cv =
          (opts.cellViews || []).find((v) => String(v.num) === String(key)) ||
          (opts.cellViews || [])[0] ||
          { color: "#888888" };
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
        console.error("[source-demo] STL load error for cell", key, e);
      }
    }
  }

  /* ── 粒子点云 + 方向线 ── */
  let particlePoints: THREE.Points | null = null;
  let directionLines: THREE.LineSegments | null = null;
  let particleOpacity = 1;
  let directionScale = 1;
  let alignedOffset: Vec3 | null = null;

  function clearParticles(): void {
    if (particlePoints) {
      scene.remove(particlePoints);
      particlePoints.geometry.dispose();
      (particlePoints.material as THREE.Material).dispose();
      particlePoints = null;
    }
    if (directionLines) {
      scene.remove(directionLines);
      directionLines.geometry.dispose();
      (directionLines.material as THREE.Material).dispose();
      directionLines = null;
    }
  }

  function setParticles(particles: SourceParticle[], energyRange: { min: number; max: number }): void {
    clearParticles();
    const list = particles || [];
    // 粒子世界包围盒（取景用）
    let min: Vec3 = [Infinity, Infinity, Infinity];
    let max: Vec3 = [-Infinity, -Infinity, -Infinity];
    for (const p of list) {
      const c = [p.x, p.y, p.z] as Vec3;
      for (let i = 0; i < 3; i++) {
        if (c[i] < min[i]) min[i] = c[i];
        if (c[i] > max[i]) max[i] = c[i];
      }
    }
    const hasPoints = list.length > 0 && Number.isFinite(min[0]);

    // 方向线长度 = 粒子跨度对角线的 3%（× directionScale）
    const span = hasPoints
      ? Math.sqrt((max[0] - min[0]) ** 2 + (max[1] - min[1]) ** 2 + (max[2] - min[2]) ** 2)
      : 1;
    const arrowLen = Math.max(span * 0.03, 1e-6) * directionScale;

    // 点云
    const posArr = new Float32Array(list.length * 3);
    const colArr = new Float32Array(list.length * 3);
    list.forEach((p, i) => {
      posArr[i * 3] = p.x;
      posArr[i * 3 + 1] = p.y;
      posArr[i * 3 + 2] = p.z;
      const e01 = normalizeEnergy01(Number(p.energy ?? 0), energyRange);
      const c = new THREE.Color(trackShade(trackColor(p.particle || "other"), e01));
      colArr[i * 3] = c.r;
      colArr[i * 3 + 1] = c.g;
      colArr[i * 3 + 2] = c.b;
    });
    const ptsGeo = new THREE.BufferGeometry();
    ptsGeo.setAttribute("position", new THREE.BufferAttribute(posArr, 3));
    ptsGeo.setAttribute("color", new THREE.BufferAttribute(colArr, 3));
    const ptsMat = new THREE.PointsMaterial({
      vertexColors: true, size: 6, sizeAttenuation: true,
      transparent: particleOpacity < 1, opacity: particleOpacity, depthTest: true,
    });
    particlePoints = new THREE.Points(ptsGeo, ptsMat);
    scene.add(particlePoints);

    // 方向线（出生点 → 沿方向 arrowLen）
    const dirPos = new Float32Array(list.length * 6);
    const dirCol = new Float32Array(list.length * 6);
    list.forEach((p, i) => {
      const nx = p.dx, ny = p.dy, nz = p.dz;
      const base = i * 6;
      dirPos[base] = p.x;
      dirPos[base + 1] = p.y;
      dirPos[base + 2] = p.z;
      dirPos[base + 3] = p.x + nx * arrowLen;
      dirPos[base + 4] = p.y + ny * arrowLen;
      dirPos[base + 5] = p.z + nz * arrowLen;
      const e01 = normalizeEnergy01(Number(p.energy ?? 0), energyRange);
      const c = new THREE.Color(trackShade(trackColor(p.particle || "other"), e01));
      dirCol[base] = c.r; dirCol[base + 1] = c.g; dirCol[base + 2] = c.b;
      dirCol[base + 3] = c.r; dirCol[base + 4] = c.g; dirCol[base + 5] = c.b;
    });
    const dirGeo = new THREE.BufferGeometry();
    dirGeo.setAttribute("position", new THREE.BufferAttribute(dirPos, 3));
    dirGeo.setAttribute("color", new THREE.BufferAttribute(dirCol, 3));
    const dirMat = new THREE.LineBasicMaterial({
      vertexColors: true, transparent: particleOpacity < 1, opacity: particleOpacity * 0.8,
      depthTest: true,
    });
    directionLines = new THREE.LineSegments(dirGeo, dirMat);
    scene.add(directionLines);

    // 对齐 + 取景（外壳 + 粒子并集；后续抽样重建用已存 offset）
    const geoList: Translatable[] = [
      ...shellMeshes.map((m) => m.geometry),
      particlePoints.geometry,
      directionLines.geometry,
    ];
    if (alignedOffset) {
      const off = alignedOffset;
      particlePoints.geometry.translate(off[0], off[1], off[2]);
      directionLines.geometry.translate(off[0], off[1], off[2]);
    } else if (hasPoints) {
      const shellBox: AABB | null = shellRawBounds.length > 0
        ? (() => {
            const tb = new THREE.Box3();
            for (const b of shellRawBounds) tb.union(b);
            return box3ToAabb(tb);
          })()
        : null;
      const worldBox: AABB = { min, max };
      const boxes: AABB[] = [];
      if (shellBox) boxes.push(shellBox);
      boxes.push(worldBox);
      const union = unionBoxes(boxes);
      const offset = translateToCenter(geoList, union);
      // ⚠️ 演示源**不复用** computeFramingBox：那条 VOLUME_FRAMING_RATIO(=0.25) 规则是为
      // 体积窗口设计的（网格层远小于模型时聚焦网格层），搬到演示源上会把外壳挤出视野——
      // 而"源在屏蔽体内部"恰是演示源的常态。2026-09-11 实测本卡：源区 15×20×30 在热室
      // 500×500×528 内，ratio≈0.057 < 0.25 ⇒ 只框粒子盒 ⇒ 外壳在视野外。
      // 演示源一律按并集取景（外壳优先），粒子再靠 OrbitControls 自己放大。
      const framing = shellBox ? unionBoxes([shellBox, worldBox]) : worldBox;
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
    markDirty();
  }

  /* ── 渲染门 ── */
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

  loadShell();
  markDirty();

  return {
    setParticles,
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
    setParticleOpacity(v: number) {
      particleOpacity = clamp01(v);
      if (particlePoints) {
        const mat = particlePoints.material as THREE.PointsMaterial;
        mat.transparent = particleOpacity < 1;
        mat.opacity = particleOpacity;
        mat.needsUpdate = true;
      }
      if (directionLines) {
        const mat = directionLines.material as THREE.LineBasicMaterial;
        mat.transparent = particleOpacity < 1;
        mat.opacity = particleOpacity * 0.8;
        mat.needsUpdate = true;
      }
      markDirty();
    },
    setDirectionLength(scale: number) {
      directionScale = scale;
      markDirty();
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
      clearParticles();
      scene.clear();
    },
  };
}
