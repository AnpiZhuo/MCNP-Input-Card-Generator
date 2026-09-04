/**
 * Preview3D — Three.js 3D 预览窗口
 *
 * 优先从后端 FreeCAD STL 加载真实几何，不可用时回退到模拟几何体。
 *
 * 性能修复接线（契约 preview3d-performance.md §4/§5）：
 * - TickGrid     刻度生命周期（dispose 台账 + 步长表扩到 1e6）
 * - renderGate   dirty 按需渲染（idle 0 渲染）
 * - cellMaterial 默认 opaque（消除透明 overdraw），面板半透明开关
 * - computeCameraParams 几何归一化 + far/near ≤1e4（大坐标深度）
 */
import React, { useRef, useEffect, useState, useCallback } from "react";
import CrossSectionView from "./CrossSectionView";
import QuickCellForm from "./QuickCellForm";
import { buildLatticeInstances, DETAIL_MAX_INSTANCES } from "../three/latticeInstances";
import { buildUniversePalette } from "../utils/lattice";

/** base64 STL → THREE.BufferGeometry（格阵装配 STL 解码，与 loadStlMeshes 同法） */
function decodeStlBase64(b64: string): THREE.BufferGeometry {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const geo = new STLLoader().parse(bytes.buffer);
  geo.computeBoundingBox();
  return geo;
}

/** 格位是否落在最外层容器（外壳）边界内——超外壳格位（如 17×17 方形格阵角部
 *  超出圆柱壳）不显示，保证色块总览不冒出原卡规定的外壳尺寸。 */
function inOuter(p: { x: number; y: number; z: number }, ob: any): boolean {
  if (!ob) return true;
  if (ob.shape === "cylinder") {
    const dx = p.x - (ob.cx || 0);
    const dy = p.y - (ob.cy || 0);
    return dx * dx + dy * dy <= ob.r * ob.r;
  }
  if (ob.shape === "box") {
    if (p.x < ob.x[0] || p.x > ob.x[1] || p.y < ob.y[0] || p.y > ob.y[1]) return false;
    if (ob.z && (p.z < ob.z[0] || p.z > ob.z[1])) return false;
    return true;
  }
  return true;
}

/* ---- 类型定义 ---- */
interface CellView {
  num: string;
  mat: string;
  comment: string;
  visible: boolean;
  color: string;
}

interface Preview3DProps {
  cells: { num: string; mat: string; density?: string; surfaces?: string; comment?: string; render?: boolean; u?: string; fill?: string; lat?: string; trcl?: string; fill_grid?: string; impN?: string; impP?: string; impE?: string }[];
  surfaces?: string;
  trCards?: string;
  onClose: () => void;
  /** 用户改了某个栅元的材料号后回调（num=栅元号, newMat=新材料号） */
  onMaterialChange?: (cellNum: string, newMat: string) => void;
  /** 独立窗口模式：由宿主传入材料列表（{number, comment}），替代 useDeck() */
  materials?: { number: number; comment?: string }[];
  /** 快捷建栅元生成结果回调（宿主把曲面/TR/栅元写回 deck） */
  onQuickCellGenerate?: (result: QuickCellResult) => void;
}

/* ---- 色板（10 色，按材料号取模） ---- */
import { getMatColor as getColor } from "../utils/materialColors";
import { MaterialLegend, CellList, UniverseCellList } from "./MaterialPanel";
import { useDeck } from "../utils/DeckContext";
import { openCrossSection } from "../utils/windows";
import { apiUrl } from "../utils/api";

/* ---- 深模块（3D 性能修复） ---- */
import { computeCameraParams } from "../three/cameraParams";
import { buildCellMaterial, type TransparentMode } from "../three/cellMaterial";
import { createRenderLoop } from "../three/renderGate";
import { createTickGrid } from "../three/TickGrid";
import { AXIS_CONFIG } from "../three/axisConfig";
import { offsetPlaneForStl } from "../three/planeOffset";
import { buildQuickCellPreview, wireColorForMaterial } from "../three/quickCellPreview";
import { type QuickCellResult, type QuickShape } from "../utils/quickCell";
import { useQuickAddOverlap } from "../utils/useQuickAddOverlap";
import FloatingDialog from "./FloatingDialog";

/* ---- plane eq formatting/parsing ---- */
function planeToStr(plane: any): string {
  var fmt = function(v: number): string {
    if (v === 1) return '';
    if (v === -1) return '-';
    if (v === Math.floor(v) && isFinite(v)) return String(v);
    return v.toFixed(3).replace(/\.?0+$/, '');
  };
  var parts: string[] = [];
  if (plane.A !== 0) parts.push(fmt(plane.A) + 'X');
  if (plane.B !== 0) parts.push(fmt(plane.B) + 'Y');
  if (plane.C !== 0) parts.push(fmt(plane.C) + 'Z');
  if (parts.length === 0) parts.push('0');
  var dStr = (function(v: number): string {
    if (v === Math.floor(v) && isFinite(v)) return String(v);
    return v.toFixed(3).replace(/\.?0+$/, '');
  })(plane.D);
  return parts.join(' + ') + ' = ' + dStr;
}

function parsePlane(s: string): any {
  var cleaned = s.replace(/\s+/g, '');
  var pc = function(v: string): number {
    if (v === '' || v === '+') return 1;
    if (v === '-') return -1;
    return parseFloat(v);
  };
  var a=0,b=0,c=0,d=0;
  var xm = cleaned.match(/([+-]?\d*\.?\d*)x/i);
  if (xm) a = pc(xm[1]);
  var ym = cleaned.match(/([+-]?\d*\.?\d*)y/i);
  if (ym) b = pc(ym[1]);
  var zm = cleaned.match(/([+-]?\d*\.?\d*)z/i);
  if (zm) c = pc(zm[1]);
  var dm = cleaned.match(/=([+-]?\d*\.?\d+)/);
  if (dm) d = parseFloat(dm[1]);
  if (!xm && !ym && !zm && !dm) return null;
  return {A:a, B:b, C:c, D:d};
}



/* ---- 场景管理器（封装 Three.js 生命周期） ---- */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

function initScene(
  canvas: HTMLCanvasElement,
  cells: CellView[],
) {
  /* 初始场景尺寸（等 STL 加载后根据实际几何更新） */
  var sceneExtent = 10;
  var viewDist = 35;

  /* 场景 */
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);

  /* 相机 — 初始用默认包围盒参数（realExt=10 → viewDist=35）；STL 加载后按实际几何 reframe */
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(rect.width, 1);
  const h = Math.max(rect.height, 1);
  const initCam = computeCameraParams([0, 0, 0], [sceneExtent * 2, sceneExtent * 2, sceneExtent * 2]);
  const camera = new THREE.PerspectiveCamera(45, w / h, initCam.near, initCam.far);
  camera.position.set(initCam.position[0], initCam.position[1], initCam.position[2]);
  camera.lookAt(0, 0, 0);
  camera.up.set(0, 0, 1); // Z-up

  /* 渲染器 — 不设 CSS 尺寸（让 flex 布局控制），避免 1x1 钉死 */
  // powerPreference: high-performance → 优先独显（全堆芯等大场景集显卡死）
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setSize(w, h, false);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = false;
  renderer.toneMapping = THREE.NoToneMapping;

  /* 灯光 — 均匀照亮，无阴影 */
  const ambient = new THREE.AmbientLight(0x8888aa, 0.35);
  scene.add(ambient);
  const dirlight1 = new THREE.DirectionalLight(0xffffff, 1.8);
  dirlight1.position.set(viewDist * 0.8, viewDist, viewDist * 0.6);
  scene.add(dirlight1);
  const dirlight2 = new THREE.DirectionalLight(0x4488ff, 0.5);
  dirlight2.position.set(-viewDist * 0.5, viewDist * 0.2, -viewDist * 0.8);
  scene.add(dirlight2);

  /* ---- 动态数轴线（正负双向无限延伸） ---- */
  // 轴顺序单一事实来源 = AXIS_CONFIG（X 红 / Y 绿 / Z 蓝；2026-08-18 修复 Y/Z 互换）
  const AXIS_COLORS = AXIS_CONFIG.map((a) => a.color);
  const AXIS_LABELS = AXIS_CONFIG.map((a) => a.label);
  const AXIS_EXTENT = sceneExtent * 3;

  // 三条彩色轴线（从 -extent 到 +extent）；标签存数组以便 updateAxes 重定位
  const axisLines: THREE.Line[] = [];
  const axisLabels: { sprite: THREE.Sprite; dir: THREE.Vector3; sign: number }[] = [];
  const axisDirs = AXIS_CONFIG.map((a) => new THREE.Vector3(...a.dir));
  axisDirs.forEach((dir, ai) => {
    const pts = [dir.clone().multiplyScalar(-AXIS_EXTENT), dir.clone().multiplyScalar(AXIS_EXTENT)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: AXIS_COLORS[ai] }));
    scene.add(line);
    axisLines.push(line);
    // 正端字母
    const mkLabel = (text: string, color: number, pos: THREE.Vector3, scale = 3) => {
      const c = document.createElement("canvas"); c.width = 64; c.height = 64;
      const ctx = c.getContext("2d")!;
      ctx.fillStyle = "#" + color.toString(16).padStart(6, "0");
      ctx.font = "Bold 40px Arial"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(text, 32, 34);
      const tex = new THREE.CanvasTexture(c);
      const lbl = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }));
      lbl.position.copy(pos);
      lbl.scale.set(scale, scale, 1);
      scene.add(lbl);
      return lbl;
    };
    axisLabels.push({ sprite: mkLabel(AXIS_LABELS[ai], AXIS_COLORS[ai], dir.clone().multiplyScalar(AXIS_EXTENT + 20)), dir, sign: 1 });
    axisLabels.push({ sprite: mkLabel("-" + AXIS_LABELS[ai], AXIS_COLORS[ai], dir.clone().multiplyScalar(-AXIS_EXTENT - 20)), dir, sign: -1 });
  });

  // 根据实际几何范围重算轴线长度与标签位置（让轴相对几何"无限长"）
  function updateAxes(newExtent: number) {
    const extent = Math.max(newExtent, 1) * 5;
    axisDirs.forEach((dir, ai) => {
      const pts = [dir.clone().multiplyScalar(-extent), dir.clone().multiplyScalar(extent)];
      const old = axisLines[ai].geometry;
      axisLines[ai].geometry = new THREE.BufferGeometry().setFromPoints(pts);
      old.dispose();
    });
    axisLabels.forEach((l) => {
      l.sprite.position.copy(l.dir.clone().multiplyScalar((extent + 20) * l.sign));
    });
  }

  // 动态刻度：TickGrid 深模块（台账 + 完整 dispose，步长表扩到 1e6）
  const tickGroup = new THREE.Group();
  scene.add(tickGroup);
  const tickGrid = createTickGrid(tickGroup);

  function rebuildTicks() {
    try {
      const dist = camera.position.length();
      tickGrid.rebuild({
        dist,
        axes: axisDirs.map((d, ai) => ({ dir: [d.x, d.y, d.z], color: AXIS_COLORS[ai] })),
      });
    } catch (e) { console.warn("[3D] rebuildTicks error:", e); }
  }

  rebuildTicks();

  // 防抖：相机停止变化后再重建刻度
  let tickTimer: number | null = null;
  function scheduleRebuild() {
    if (tickTimer) cancelAnimationFrame(tickTimer);
    tickTimer = requestAnimationFrame(() => { rebuildTicks(); tickTimer = null; });
  }

  /* 控件 */
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.rotateSpeed = 0.4;
  controls.minDistance = initCam.minDistance;
  controls.maxDistance = initCam.maxDistance;
  controls.target.set(0, 0, 0);

  /* ---- WASD+Shift+Space 镜头控制 ---- */
  const keys: Record<string, boolean> = {};
  function onKeyDown(e: KeyboardEvent) {
    if (e.code === "KeyW" || e.code === "KeyA" || e.code === "KeyS" || e.code === "KeyD") keys[e.code] = true;
    if (e.code === "ShiftLeft" || e.code === "ShiftRight") keys.shift = true;
    if (e.code === "Space") keys.space = true;
    markDirty();  // 任一镜头键按下 → 驱动一帧渲染（持续移动由 onRender 内续 dirty）
  }
  function onKeyUp(e: KeyboardEvent) {
    if (e.code === "KeyW" || e.code === "KeyA" || e.code === "KeyS" || e.code === "KeyD") keys[e.code] = false;
    if (e.code === "ShiftLeft" || e.code === "ShiftRight") keys.shift = false;
    if (e.code === "Space") keys.space = false;
  }
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);

  /* ---- 半透明模式（默认 opaque）---- */
  let transparentMode: TransparentMode = "opaque";
  function applyMeshMaterial(mesh: THREE.Object3D, color: string) {
    const spec = buildCellMaterial({ color, transparentMode });
    const mat = (mesh as THREE.Mesh).material as THREE.MeshStandardMaterial;
    mat.color.set(spec.color);
    mat.transparent = spec.transparent;
    mat.depthWrite = spec.depthWrite;
    mat.opacity = spec.opacity;
    mat.needsUpdate = true;
  }
  function applyTransparentMode() {
    for (const mesh of meshes) {
      applyMeshMaterial(mesh, mesh.userData.color);
    }
    markDirty();
  }

  /* 创建栅元几何体（带 LOD 动态细节） */
  // 不创建模拟几何，等 STL 数据到达后由 loadStlMeshes 加载
  var meshes: THREE.Object3D[] = [];
  // 模型不再归一化：显示坐标系 = 原始 STL 坐标系，截面平面无需换算（center 恒 0，offsetPlaneForStl 恒等）
  const modelCenter = { x: 0, y: 0, z: 0 };

  function loadStlMeshes(stlData: any, cellViews: CellView[]) {
    // 清掉旧网格，避免重复加载产生副本（否则 setVisible 只隐藏第一个，副本残留）
    meshes.forEach(m => {
      scene.remove(m);
      (m as any).geometry?.dispose();
      (m as any).material?.dispose();
    });
    meshes.length = 0;
    var loader = new STLLoader();
    var stlCount = 0;
    // 按栅元号查找 cellViews 中的索引
    function cellIndex(cellNum: string): number {
      for (var ci = 0; ci < cellViews.length; ci++) { if (cellViews[ci].num === cellNum) return ci; }
      return 0;
    }
    for (var key in stlData) {
      try {
        var raw = atob(stlData[key]);
        var buf = new Uint8Array(raw.length);
        for (var bi = 0; bi < raw.length; bi++) buf[bi] = raw.charCodeAt(bi) & 0xff;
        var geo = loader.parse(buf.buffer);
        var idx = cellIndex(key);
        var cv = cellViews[idx] || cellViews[0];
        var spec = buildCellMaterial({ color: cv.color, transparentMode });
        var mat = new THREE.MeshStandardMaterial({ color: spec.color, roughness: 0.3, metalness: 0.0, transparent: spec.transparent, opacity: spec.opacity, depthWrite: spec.depthWrite, side: THREE.FrontSide });
        var mesh = new THREE.Mesh(geo, mat);
        mesh.userData.index = idx;
        mesh.userData.color = cv.color;
        mesh.userData.num = key;
        scene.add(mesh);
        meshes.push(mesh);
        geo.computeBoundingBox();
        stlCount++;
      } catch(e) { console.error("STL load error for cell", key, e); }
    }

    /* 保留真实世界坐标（不归一化）：坐标轴固定在原点 (0,0,0)，模型显示在真实位置。
       仅重新计算 bbox 供 renderOrder 排序与取景使用，不平移几何。 */
    for (var _m of meshes) {
      (_m as THREE.Mesh).geometry.computeBoundingBox();
    }

    // 按体积排序：外层（大）先渲染，内层（小）后渲染，嵌套时内层可见
    meshes.sort(function(a: any, b: any) {
      var va = a.geometry?.boundingBox?.getSize(new THREE.Vector3()).length() || 0;
      var vb = b.geometry?.boundingBox?.getSize(new THREE.Vector3()).length() || 0;
      return vb - va; // 大的在前（先渲染），小的在后（后渲染）
    });
    for (var mi = 0; mi < meshes.length; mi++) {
      meshes[mi].renderOrder = mi;
    }

    if (meshes.length > 0) {
      frameCamera();  // 取景框 = 模型 ∪ 原点；target=模型中心
    }
    markDirty();
    return stlCount;
  }

  // 相机取景：模型 ∪（可选线框预览）∪ 原点（坐标轴在原点），target=模型中心
  function frameCamera(extra?: THREE.Object3D) {
    var modelBox = new THREE.Box3();
    for (var _m4 of meshes) {
      var bb4 = (_m4 as THREE.Mesh).geometry?.boundingBox;
      if (bb4) modelBox.union(bb4);
    }
    var frameBox = modelBox.clone();
    if (extra) {
      try { frameBox.union(new THREE.Box3().setFromObject(extra)); } catch (e) { /* 忽略线框取景异常 */ }
    }
    // 无网格且无 extra（如格阵 deck：universe 栅元已排除、装配由 extra 提供）→ 不取景
    if (modelBox.isEmpty() && !extra) return;
    frameBox.expandByPoint(new THREE.Vector3(0, 0, 0));
    var target = modelBox.getCenter(new THREE.Vector3());
    var fSize = frameBox.getSize(new THREE.Vector3());
    var cp = computeCameraParams([target.x, target.y, target.z], [Math.max(fSize.x, 1e-3), Math.max(fSize.y, 1e-3), Math.max(fSize.z, 1e-3)]);
    camera.near = cp.near;
    camera.far = cp.far;
    camera.position.set(cp.position[0], cp.position[1], cp.position[2]);
    controls.target.set(cp.target[0], cp.target[1], cp.target[2]);
    controls.minDistance = cp.minDistance;
    controls.maxDistance = cp.maxDistance;
    camera.updateProjectionMatrix();
    controls.update();
    var mSize = modelBox.getSize(new THREE.Vector3());
    updateAxes(Math.max(mSize.x, mSize.y, mSize.z, 1) * 0.5);  // 轴线随模型范围伸缩
  }

  /* ---- 按需渲染门（renderGate）---- */
  var markDirty: () => void = () => {};
  const renderLoop = createRenderLoop({
    onRender: () => {
      // WASD 镜头移动
      var moved = false;
      const moveSpeed = camera.position.length() * 0.015;
      if (keys.KeyW || keys.KeyA || keys.KeyS || keys.KeyD || keys.shift || keys.space) {
        const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
        const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion);
        const up = new THREE.Vector3(0, 1, 0);
        const delta = new THREE.Vector3(0, 0, 0);
        if (keys.KeyW) delta.add(fwd);
        if (keys.KeyS) delta.sub(fwd);
        if (keys.KeyA) delta.sub(right);
        if (keys.KeyD) delta.add(right);
        if (keys.space) delta.add(up);
        if (keys.shift) delta.sub(up);
        delta.normalize().multiplyScalar(moveSpeed);
        camera.position.add(delta);
        // 移动后：目标点固定在相机正前方当前距离处，旋转不漂移
        const fwd2 = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
        const pivotDist = camera.position.length();
        controls.target.copy(camera.position).add(fwd2.multiplyScalar(pivotDist));
        moved = true;
      }
      controls.update();
      for (const obj of meshes) {
        if (obj instanceof THREE.LOD) obj.update(camera);
      }
      renderer.render(scene, camera);
      // 按键仍按住 → 续 dirty，保持连续移动
      if (moved) markDirty();
    },
  });
  markDirty = renderLoop.markDirty;

  /* 控件变化（旋转/缩放/平移）→ 置 dirty 渲染 + 防抖重建刻度 */
  controls.addEventListener("change", () => { markDirty(); scheduleRebuild(); });
  markDirty();  // 初始渲染一帧基座（轴线/刻度）

  /* 大小自适应 — 用 ResizeObserver 确保 canvas 始终有尺寸 */
  function resizeRenderer() {
    const r = canvas.getBoundingClientRect();
    const w2 = Math.max(r.width, 1);
    const h2 = Math.max(r.height, 1);
    if (w2 <= 1 || h2 <= 1) { setTimeout(resizeRenderer, 50); return; }
    camera.aspect = w2 / h2;
    camera.updateProjectionMatrix();
    renderer.setSize(w2, h2, false);
    markDirty();
  }
  var ro = new ResizeObserver(function() { resizeRenderer(); });
  if (canvas.parentElement) ro.observe(canvas.parentElement);
  setTimeout(resizeRenderer, 100); // 首次初始化延迟执行，等待布局

  /* 返回控制接口 */
  return {
    loadStlMeshes: loadStlMeshes,
    updateAxes: updateAxes,
    modelCenter: modelCenter,
    scene: scene,
    markDirty: markDirty,
    frameCamera: frameCamera,
    setVisible(index: number, vis: boolean) {
      for (var _mi = 0; _mi < meshes.length; _mi++) {
        if (meshes[_mi].userData.index === index) { meshes[_mi].visible = vis; markDirty(); return; }
      }
    },
    setColor(index: number, color: string) {
      for (var _mi = 0; _mi < meshes.length; _mi++) {
        if (meshes[_mi].userData.index === index) {
          meshes[_mi].userData.color = color;
          applyMeshMaterial(meshes[_mi], color);
          markDirty();
          return;
        }
      }
    },
    setHighlight(nums: string[]) {
      var set = new Set(nums);
      for (var _mi = 0; _mi < meshes.length; _mi++) {
        var m = meshes[_mi];
        var mat = (m as THREE.Mesh).material as THREE.MeshStandardMaterial;
        if (set.has(String(m.userData.num))) {
          mat.color.set("#ff3b30");
          mat.emissive.set(0xff0000);
          mat.emissiveIntensity = 0.4;
        } else {
          mat.color.set(m.userData.color);
          mat.emissive.set(0x000000);
          mat.emissiveIntensity = 0;
        }
        mat.needsUpdate = true;
      }
      markDirty();
    },
    selectAll(vis: boolean) {
      meshes.forEach((m) => { m.visible = vis; });
      markDirty();
    },
    setTransparentMode(mode: TransparentMode) {
      transparentMode = mode;
      applyTransparentMode();
    },
    dispose() {
      ro.disconnect();
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      controls.dispose();
      tickGrid.dispose();
      renderLoop.dispose();
      renderer.dispose();
      meshes.forEach((m) => {
        if (m instanceof THREE.LOD) {
          for (const lvl of m.levels) {
            if (lvl && (lvl as any).geometry) {
              (lvl as any).geometry?.dispose();
              (lvl as any).material?.dispose();
            }
          }
        } else {
          (m as any).geometry?.dispose();
          ((m as any).material as THREE.Material)?.dispose();
        }
      });
      scene.clear();
    },
  };
}

/* ---- React 组件 ---- */
export default function Preview3D({ cells: rawCells, surfaces, trCards, onClose, onMaterialChange, materials, onQuickCellGenerate }: Preview3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ctrlRef = useRef<ReturnType<typeof initScene> | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const { deck } = useDeck();
  // 独立窗口模式：材料列表由宿主传入（materials），否则回退主窗口 deck
  const matList = materials ?? deck.materials;
  // 格阵装配（用户要求：唯一 3D 预览，MCNP 真实装配）——有 fill/fill_grid 时
  // 把 universe 实例化装配融进主场景（universe 栅元不单独摆），无单独格阵视图。
  const hasLattice = rawCells.some((c) =>
    (c.fill_grid && c.fill_grid.trim() !== "") ||
    (c.fill && c.fill.trim() !== "" && c.fill.trim() !== "0"),
  );

  // 初始化 cellView 状态（非 void 默认可见：否则无 FreeCAD 时截面过滤会滤掉全部栅元）
  const [cellViews, setCellViews] = useState<CellView[]>(() =>
    rawCells.map((c, i) => ({
      num: c.num,
      mat: c.mat,
      comment: c.comment || "",
      visible: c.mat !== "0",
      color: getColor(c.mat),
    }))
  );

  // 尝试从后端获取真实 STL 数据
  const [freecadStatus, setFreecadStatus] = useState("");
  const [stlData, setStlData] = useState<Record<string, string> | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeThrough, setSeeThrough] = useState(false);  // 半透明查看（默认关 → opaque）
  const [sceneReady, setSceneReady] = useState(false);  // 场景初始化完成（装配加载前置）
  const [latticeLoading, setLatticeLoading] = useState(false);  // 格阵装配加载中（覆盖层 + 禁交互）
  const [latticeOverview, setLatticeOverview] = useState(false); // 色块总览（手动切换）
  const latticeDataRef = useRef<{
    positions: any[]; overviewPositions: any[]; universeStl: any; cellMaterials: any;
    palette: Record<string, string>; trclDeg: number; blockSize: any; count: number; detailViable: boolean; outerBound: any; disc: boolean; subPitch: number;
  } | null>(null);
  const [latticeDataVersion, setLatticeDataVersion] = useState(0); // 数据变更触发重建
  const seeThroughRef = useRef(false);
  useEffect(() => { seeThroughRef.current = seeThrough; }, [seeThrough]);
  const [csPlane, setCsPlane] = useState({A:0,B:0,C:1,D:0});
  const [csSlices, setCsSlices] = useState<any[] | null>(null);
  // 材料选择浮层：i=cellViews 索引, x/y=点击屏幕坐标
  const [matPicker, setMatPicker] = useState<{ i: number; x: number; y: number } | null>(null);

  // 快捷建栅元（3D 预览侧栏）：表单覆盖层 + 场景内线框预览 + 生成后重拉
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [genTick, setGenTick] = useState(0);
  const [wireSpec, setWireSpec] = useState<{ shape: QuickShape; config: any; material: string } | null>(null);
  const wirePreviewRef = useRef<ReturnType<typeof buildQuickCellPreview> | null>(null);
  const propsRef = useRef({ cells: rawCells, surfaces: surfaces || "", trCards: trCards || "" });
  propsRef.current = { cells: rawCells, surfaces: surfaces || "", trCards: trCards || "" };

  /* ── 重合检测（异步自动触发 + 面板 + 点击高亮）── */
  const [overlapResult, setOverlapResult] = useState<{
    overlaps: any[]; truncated: boolean; unresolved: any[];
  } | null>(null);
  const [overlapBusy, setOverlapBusy] = useState(false);
  const [highlightNums, setHighlightNums] = useState<string[]>([]);

  const runOverlapCheck = useCallback(async () => {
    setOverlapBusy(true);
    try {
      const p = propsRef.current;
      const body = {
        surfaces: p.surfaces || "",
        cells: p.cells.map((c: any) => ({
          kind: "cell",
          cell: {
            number: parseInt(c.num) || 0,
            material: c.mat,
            density: (c as any).density || "",
            surface_expr: (c as any).surface_expr || (c as any).surfaces || "",
            // 格阵/fill/重要性语义字段必须随请求传给后端，否则 universe 栅元
            // 在本地原点被当绝对坐标比较 → 跨 universe 假重叠（fill套fill 尤甚），
            // 且 fill/graveyard/lattice-fit 检测全部失效。
            u: (c as any).u || "",
            fill: (c as any).fill || "",
            lat: (c as any).lat || "",
            trcl: (c as any).trcl || "",
            render: (c as any).render !== false,
            fill_grid: (c as any).fill_grid || "",
            imp_n: (c as any).impN || (c as any).imp_n || "",
            imp_p: (c as any).impP || (c as any).imp_p || "",
            imp_e: (c as any).impE || (c as any).imp_e || "",
          },
        })),
        tr_cards: p.trCards || "",
      };
      const r = await fetch(apiUrl("/api/check-overlap"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body), signal: AbortSignal.timeout(60000),
      });
      const j = await r.json();
      if (j.status === "error") throw new Error(j.message);
      setOverlapResult(j);
    } catch (e: any) {
      // 检测失败静默降级：不影响预览
      console.error("overlap check failed", e);
    } finally {
      setOverlapBusy(false);
    }
  }, []);

  const highlightPair = useCallback((a: number, b: number) => {
    setHighlightNums((prev) => {
      const same = prev.length === 2
        && prev.includes(String(a)) && prev.includes(String(b));
      const next = same ? [] : [String(a), String(b)];
      ctrlRef.current?.setHighlight(next);
      return next;
    });
  }, []);

  // 截面请求 → 结果写入数据桥并开独立截面窗口；非 Tauri 环境回退内嵌覆盖层
  // 只传勾选且非真空的栅元号 + plane（后端从 3D 预览保留的 STL 切，真空/未勾选不参与）
  const fetchCrossSection = useCallback(function(newPlane: {A:number; B:number; C:number; D:number}) {
    setCsPlane(newPlane);
    var cellNums = rawCells
      .filter(function(_: any, i: number) { return cellViews[i]?.visible !== false; })
      .filter(function(c: any) { return String(c.mat).split(" ")[0] !== "0"; })  // 排除真空
      .map(function(c: any) { return parseInt(c.num) || 0; });
    // 预览显示坐标系 → 后端原始 STL 坐标系（模型中心平移的逆变换）
    var center = ctrlRef.current?.modelCenter ?? { x: 0, y: 0, z: 0 };
    var planeRaw = offsetPlaneForStl(newPlane, center);
    fetch(apiUrl("/api/cross-section"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cellNums: cellNums,
        plane: planeRaw,
      }),
    }).then(function(r: Response) { return r.json(); }).then(function(j: any) {
      if (j.slices && j.slices.length > 0) {
        // 开独立截面窗口；失败（非 Tauri）时回退内嵌覆盖层
        openCrossSection({
          slices: j.slices,
          plane: newPlane,
          cells: rawCells.map(function(c: any) {
            return { num: c.num, mat: c.mat, comment: c.comment || "" };
          }),
          cellNums: cellNums,
          center: center,
        }).then(function(opened) {
          if (!opened) setCsSlices(j.slices);
        });
      } else {
        setCsSlices(null);
        alert("截面无结果: " + (j.message || "无交点"));
      }
    }).catch(function() { alert("截面请求失败"); });
  }, [rawCells, cellViews]);
  const [csStep, setCsStep] = useState("1");
  const [eqInput, setEqInput] = useState(function() { return planeToStr(csPlane); });
  useEffect(function() { setEqInput(planeToStr(csPlane)); }, [csPlane]);

  useEffect(() => {
    // 用最新曲面/栅元/TR 调用后端生成 STL；生成新栅元后 genTick++ 重拉
    setLoading(true);
    var p = propsRef.current;
    // 格阵装配：universe 栅元（u 非空）不单独摆（经装配出现），从 preview-3d 排除
    var cellsForBackend = p.cells.filter(function(c) { return !(hasLattice && c.u); }).map(function(c) {
      return { number: parseInt(c.num) || 0, material: c.mat, density: (c as any).density || "", surface_expr: (c as any).surfaces || (c as any).surface_expr || "" };
    });
    fetch(apiUrl("/api/preview-3d"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        surfaces: p.surfaces,
        cells: cellsForBackend,
        tr_cards: p.trCards,
      }),
    }).then(function(r) { return r.json(); }).then(function(j) {
      if (j.stl_data && Object.keys(j.stl_data).length > 0) {
        setStlData(j.stl_data);
        setFreecadStatus(" " + j.count + " ");
      } else if (j.message) {
        setFreecadStatus("  " + j.message);
      } else {
        setFreecadStatus("  ");
      }
    }).catch(function() { setFreecadStatus("  "); }).finally(function() { setLoading(false); });
  }, [genTick, hasLattice]);

  /* 格阵装配：把 universe 实例化装配融进主 3D 预览场景（用户要求唯一 3D 预览，
     显示 MCNP 真实装配——pin 到位、fill 容器不出实体）。universe 栅元已从
     preview-3d 排除，这里经 preview-lattice 实例化装配。 */
  const latticeAssemblyRef = useRef<{ group: THREE.Group; dispose(): void } | null>(null);
  useEffect(() => {
    if (!hasLattice || !sceneReady || !ctrlRef.current) return;
    const ctrl = ctrlRef.current;
    let cancelled = false;
    setLatticeLoading(true);
    (async () => {
      const p = propsRef.current;
      const payload = {
        surfaces: p.surfaces || "",
        tr_cards: p.trCards || "",
        cells: p.cells.map(function(c: any) {
          return { number: parseInt(c.num) || 0, material: c.mat, density: c.density || "", surface_expr: c.surfaces || "", u: c.u || "", fill: c.fill || "", lat: c.lat || "", trcl: c.trcl || "", render: c.render !== false, fill_grid: c.fill_grid || "" };
        }),
      };
      try {
        const r = await fetch(apiUrl("/api/preview-lattice"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then((x) => x.json());
        if (cancelled || r.status === "error" || !r.lattices) { console.warn("[3D] lattice assembly failed", r); if (!cancelled) setLatticeLoading(false); return; }
        const universeStl: Record<string, Record<string, THREE.BufferGeometry>> = {};
        for (const lt of r.lattices || []) {
          for (const u of Object.keys(lt.universes || {})) {
            const t = (universeStl[u] ??= {});
            for (const cn of Object.keys(lt.universes[u])) {
              try { t[cn] = decodeStlBase64(lt.universes[u][cn]); } catch (e) { console.warn("[3D] lattice STL decode fail", u, cn, e); }
            }
          }
        }
        const matByNum: Record<string, string> = {};
        for (const c of p.cells) matByNum[String(c.num)] = c.mat;
        const cellMaterials: Record<string, Record<string, string>> = {};
        for (const leaf of r.leafInstances || []) { const m = matByNum[String(leaf.cellNum)]; if (m != null) (cellMaterials[leaf.u] ??= {})[String(leaf.cellNum)] = m; }
        const primary = r.lattices?.[0];
        const blockSize = { x: primary?.pitch?.[0] || 1, y: primary?.pitch?.[1] || primary?.pitch?.[0] || 1, z: primary?.height || 1, hex: String(primary?.lat || "1") === "2" };
        const leaves = r.leafInstances || [];
        const n = r.count ?? leaves.length;
        const detailViable = r.detailViable !== false;
        // disc 降级（步骤2）：detail=fidelity.detail==='disc' 时叶数已大降（BEAVRS 5.6 万），
        // InstancedMesh 可实例化，不再受 DETAIL_MAX_INSTANCES(2万) 强制切总览。
        const fidelity = (r as any).fidelity || {};
        const isDisc = fidelity.detail === 'disc';
        const subPitch = (fidelity.subPitch as number) || primary?.pitch?.[0] || 1.26;
        const autoOverview = detailViable === false || (!isDisc && n > DETAIL_MAX_INSTANCES);
        // 项3：色块用「实际几何坐标」而非默认几何中心——
        // 详细可折叠（detailViable 且未超限）时直接用叶实例绝对坐标（与详细模式逐位对齐），
        // 自动总览（超大规模/嵌套 BEAVRS）回落到根格阵完整 positions（根 grid 中心，代表装配格位）。
        const overviewPositions = (!autoOverview && leaves.length > 0)
          ? leaves.map((x: any) => ({ path: x.path, u: x.u, cellNum: "", mat: "", x: x.x, y: x.y, z: x.z, depth: x.depth }))
          : (primary?.positions ?? []).map((x: any) => ({
              path: String(x.idx), u: x.u, cellNum: "", mat: "",
              x: x.x + (x.dx ?? 0), y: x.y + (x.dy ?? 0), z: x.z + (x.dz ?? 0), depth: 1,
            }));
        const palette = buildUniversePalette((autoOverview ? overviewPositions : leaves).map((x: any) => x.u));
        latticeDataRef.current = { positions: leaves, overviewPositions, universeStl, cellMaterials, palette, trclDeg: primary?.trclRotationDeg ?? 0, blockSize, count: n, detailViable, outerBound: r.outer_bound || null, disc: isDisc, subPitch };
        if (!cancelled) { setLatticeDataVersion(v => v + 1); setLatticeLoading(false); }
      } catch (e) { console.warn("[3D] lattice assembly load failed", e); if (!cancelled) setLatticeLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [hasLattice, genTick, sceneReady]);

  /* 格阵装配构建（数据或总览 toggle 变化时重建） */
  useEffect(() => {
    const data = latticeDataRef.current;
    const ctrl = ctrlRef.current;
    if (!data || !ctrl || !sceneReady) return;
    const effOverview = latticeOverview || data.detailViable === false || (!data.disc && data.count > DETAIL_MAX_INSTANCES);
    // 项：色块总览按外壳裁剪——只显示落在外壳（最外层容器 cell）内的格位，角部超壳剔除。
    // disc 详细模式**不**按圆心裁：渲染的是后端「universe ∩ 格元盒 ∩ 容器cell」裁剪 STL
    // （MCNP 窗口裁剪），圆柱外自动无实体。圆角 baffle(圆心 192-198>187.96 但格元盒部分在内)
    // 显示成格元∩圆柱的弧板，按圆心裁会误删它们。fill 层已按「格元盒与容器相交」正确跳过
    // 完全在外的格位(32 个 u=30)，剩余部分在内格位交给容器裁剪 STL。
    let positions;
    if (effOverview) {
      positions = data.outerBound
        ? data.overviewPositions.filter((p: any) => inOuter(p, data.outerBound))
        : data.overviewPositions;
    } else {
      positions = data.positions;
    }
    const handle = buildLatticeInstances({
      positions,
      universeStl: data.universeStl,
      cellMaterials: data.cellMaterials,
      palette: data.palette,
      materialMode: true,
      trclRotationDeg: data.trclDeg,
      overviewMode: effOverview,
      blockSize: data.blockSize,
      disc: data.disc,
      subPitch: data.subPitch,
    });
    if (latticeAssemblyRef.current) { ctrl.scene.remove(latticeAssemblyRef.current.group); latticeAssemblyRef.current.dispose(); }
    ctrl.scene.add(handle.group);
    latticeAssemblyRef.current = handle;
    ctrl.frameCamera(handle.group);  // 以装配为取景目标（格阵 deck 无 STL 网格）
    ctrl.markDirty();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latticeDataVersion, latticeOverview, sceneReady]);

  // 宿主追加新栅元后，把 cellViews 同步补齐（可见性/颜色）
  useEffect(() => {
    setCellViews(prev => {
      if (rawCells.length <= prev.length) return prev;
      const extra = rawCells.slice(prev.length).map(c => ({
        num: c.num,
        mat: c.mat,
        comment: c.comment || "",
        visible: c.mat !== "0",
        color: getColor(c.mat),
      }));
      return [...prev, ...extra];
    });
  }, [rawCells]);

  // 初始化 Three.js 场景
  const [initErr, setInitErr] = useState("");
  useEffect(() => {
    if (!canvasRef.current) return;
      try {
      ctrlRef.current = initScene(canvasRef.current, cellViews);
      setSceneReady(true);
      } catch (e: any) {
      console.error("[3D] init error:", e);
      setInitErr("3D 初始化失败: " + (e?.message || String(e)) + "\n" + (e?.stack?.split("\n").slice(0,3).join(" | ") || ""));
    }
    return () => {
      ctrlRef.current?.dispose();
      ctrlRef.current = null;
    };
  }, []);

  // STL 数据到达后替换模拟几何 + 自动全选（真空除外）
  useEffect(() => {
      if (!stlData || !ctrlRef.current) return;
    var n = ctrlRef.current.loadStlMeshes(stlData, cellViews);
    if (n > 0) {
      setFreecadStatus(n + " ");
      setCellViews(prev => prev.map(c => c.mat === "0" ? c : { ...c, visible: true }));
      ctrlRef.current.selectAll(true);
      runOverlapCheck();  // 异步自动重合检测（渲染完成后）
      setTimeout(() => {
        // STL 加载成功后 0.5s 自动勾选半透明查看（用户要求）
        if (!seeThroughRef.current && ctrlRef.current) {
          setSeeThrough(true);
          ctrlRef.current.setTransparentMode("see-through");
        }
      }, 500);
    }
  }, [stlData, runOverlapCheck]);

  /* 侧栏表单配置变化 → 防抖在场景里画线框（颜色随材料，M0 白线） */
  useEffect(() => {
    const timer = setTimeout(() => {
      const ctrl = ctrlRef.current;
      if (!ctrl) return;
      // 只在线框首次出现时取景一次；后续参数变化保持用户当前视角
      const wasVisible = !!wirePreviewRef.current;
      if (wirePreviewRef.current) {
        ctrl.scene.remove(wirePreviewRef.current.group);
        wirePreviewRef.current.dispose();
        wirePreviewRef.current = null;
      }
      if (wireSpec && quickAddOpen) {
        const prev = buildQuickCellPreview(wireSpec.shape, wireSpec.config, wireColorForMaterial(wireSpec.material));
        ctrl.scene.add(prev.group);
        wirePreviewRef.current = prev;
        if (!wasVisible) ctrl.frameCamera(prev.group);
      }
      ctrl.markDirty();
    }, 100);
    return () => clearTimeout(timer);
  }, [wireSpec, quickAddOpen]);

  const onQuickConfigChange = (shape: QuickShape, config: any, valid: boolean, material: string) => {
    setWireSpec(valid ? { shape, config, material } : null);
  };

  // 快捷建栅元重合检测 + 补集决策（共享 hook；3D 页内弹决策，写回交给宿主 onQuickCellGenerate）
  const { quickCheck, runCheck, applyChoice: applyQuickCheck } = useQuickAddOverlap({
    getExistingCells: () => (propsRef.current.cells as any[]).map(c => ({
      num: parseInt(c.num, 10),
      mat: String(c.mat),
      density: (c as any).density || "",
      surfaces: (c as any).surfaces || (c as any).surface_expr || "",
      u: (c as any).u || "",
      fill: (c as any).fill || "",
      lat: (c as any).lat || "",
      trcl: (c as any).trcl || "",
      render: (c as any).render !== false,
      fill_grid: (c as any).fill_grid || "",
      impN: (c as any).impN || (c as any).imp_n || "",
      impP: (c as any).impP || (c as any).imp_p || "",
      impE: (c as any).impE || (c as any).imp_e || "",
    })),
    getSurfaces: () => propsRef.current.surfaces || "",
    getTrCards: () => propsRef.current.trCards || "",
    onApplyResult: (r) => { onQuickCellGenerate?.(r); setGenTick(t => t + 1); },
  });

  const handleQuickCellGenerate = (result: QuickCellResult) => {
    // 移除本次线框（新栅元由重拉 STL 渲染）
    const ctrl = ctrlRef.current;
    if (ctrl && wirePreviewRef.current) {
      ctrl.scene.remove(wirePreviewRef.current.group);
      wirePreviewRef.current.dispose();
      wirePreviewRef.current = null;
    }
    if (result.checkOverlap === false) {
      onQuickCellGenerate?.(result);
      setGenTick(t => t + 1);
      return;
    }
    // 在 3D 预览页内做重合检测并弹决策（不把提示发回主页面）
    runCheck(result);
  };

  const restoreQuickCellPanel = () => {
    const ctrl = ctrlRef.current;
    if (ctrl && wirePreviewRef.current) {
      ctrl.scene.remove(wirePreviewRef.current.group);
      wirePreviewRef.current.dispose();
      wirePreviewRef.current = null;
    }
    if (ctrl) ctrl.frameCamera();
    setQuickAddOpen(false);
  };

  // 半透明查看开关：切换全栅元 opaque / see-through
  const toggleSeeThrough = useCallback(() => {
    setSeeThrough(prev => {
      ctrlRef.current?.setTransparentMode(prev ? "opaque" : "see-through");
      return !prev;
    });
  }, []);

  // 切换单个可见性（真空栅元不可切换）
  const toggleCell = useCallback((index: number) => {
    setCellViews((prev) => {
      if (prev[index]?.mat === "0") return prev; // 真空不可勾选
      const next = [...prev];
      next[index] = { ...next[index], visible: !next[index].visible };
      ctrlRef.current?.setVisible(index, next[index].visible);
      return next;
    });
  }, []);

  // 全选/全不选（真空栅元不受影响）
  const setAllVisible = useCallback((vis: boolean) => {
    setCellViews((prev) => prev.map((c) => c.mat === "0" ? c : { ...c, visible: vis }));
    ctrlRef.current?.selectAll(vis);
  }, []);

  // 材料变更：更新本地 cellViews（颜色）+ 3D 网格颜色 + 回写 deck
  const applyMaterial = useCallback((i: number, newMat: string) => {
    const m = newMat.trim();
    if (!m || !cellViews[i]) return;
    setCellViews((prev) => prev.map((cv, ci) => ci === i ? { ...cv, mat: m, color: getColor(m) } : cv));
    ctrlRef.current?.setColor(i, getColor(m));
    onMaterialChange?.(cellViews[i].num, m);
    setMatPicker(null);
  }, [cellViews, onMaterialChange]);

  // 材料可选项：材料列表（独立窗口用 props，主窗口用 deck）+ 真空 M0
  const materialOptions: { num: string; label: string }[] = [
    { num: "0", label: "M0 - 真空" },
    ...matList.map((mt) => ({
      num: String(mt.number),
      label: `M${mt.number}${mt.comment ? " - " + mt.comment : ""}`,
    })),
  ].sort((a, b) => parseInt(a.num) - parseInt(b.num));

  // 面板宽度的动态计算（基于 canvas 尺寸）
  const [panelHeight, setPanelHeight] = useState(400);
  useEffect(() => {
    const obs = new ResizeObserver((entries) => {
      for (const e of entries) {
        setPanelHeight(e.contentRect.height);
      }
    });
    if (panelRef.current) obs.observe(panelRef.current);
    return () => obs.disconnect();
  }, []);

  const visibleCount = cellViews.filter((c) => c.visible).length;
  // 自动总览锁定：detailViable=false 或叶数超限（如 BEAVRS 全堆芯 50 万叶）→ 只允许总览，
  // 手动「色块总览」开关不再可切（明示为何点了没反应），避免误导。
  const latticeAuto = latticeDataRef.current
    ? (latticeDataRef.current.detailViable === false || latticeDataRef.current.count > DETAIL_MAX_INSTANCES)
    : false;
  const CellType = "div"; // placeholder type
  // 格阵装配适配：右侧栅元列表过滤 universe 栅元（u 非空，经 fill 装配显示）；
  // displayOrigIdx = 过滤后列表每行对应的 cellViews 原始索引
  const displayOrigIdx = cellViews.map((_cv, i) => i).filter((i) => !(rawCells[i]?.u));
  // 格阵侧边栏：U 组（u 非空，每个 U 一条）+ 未分组栅元（u 为空照常列出）。
  // 「组成 U 的栅元」不作为独立行平铺，改由 U 组呈现；U 为空的栅元保留。
  const uniGroupsMap = new Map<number, { count: number; color: string; idxs: number[] }>();
  for (let _i = 0; _i < cellViews.length; _i++) {
    const uS = (rawCells[_i]?.u || "").trim();
    const u = uS ? Number(uS) : NaN;
    if (Number.isFinite(u)) {
      const g = uniGroupsMap.get(u) || { count: 0, color: "var(--text-tertiary)", idxs: [] };
      g.count++; g.idxs.push(_i);
      if (cellViews[_i]?.mat !== "0") g.color = cellViews[_i].color;
      uniGroupsMap.set(u, g);
    }
  }
  const universeGroups = Array.from(uniGroupsMap.entries())
    .map(([u, g]) => ({ u, count: g.count, color: g.color,
                        visible: g.idxs.every((ix) => cellViews[ix].visible) }))
    .sort((a, b) => a.u - b.u);
  const toggleUniverseGroup = useCallback((u: number) => {
    const g = uniGroupsMap.get(u); if (!g) return;
    const target = !g.idxs.every((ix) => cellViews[ix]?.visible);
    setCellViews((prev) => prev.map((c, ix) =>
      (g.idxs.includes(ix) && c.mat !== "0") ? { ...c, visible: target } : c));
    g.idxs.forEach((ix) => { if (cellViews[ix]?.mat !== "0") ctrlRef.current?.setVisible(ix, target); });
  }, [cellViews]);

  // 材料图例（去重）
  const legendEntries: { mat: string; color: string }[] = [];
  const seenMats = new Set<string>();
  for (const cv of cellViews) {
    if (!seenMats.has(cv.mat)) {
      seenMats.add(cv.mat);
      legendEntries.push({ mat: cv.mat, color: cv.color });
    }
  }

    return React.createElement(React.Fragment, null,
    React.createElement("div", {
    className: "preview-overlay",
    style: {
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
      backdropFilter: "blur(8px)", display: "flex",
      flexDirection: "column", zIndex: 1000,
    } as React.CSSProperties,
  },
    /* 顶部标题栏 */
    React.createElement("div", {
      style: {
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 20px", borderBottom: "1px solid var(--border-glass)",
        background: "var(--bg-glass)",
      } as React.CSSProperties,
    },
      React.createElement("span", {
        style: { fontSize: 14, fontWeight: 600, color: "rgba(241,241,249,0.85)" },
      }, "🎨 3D 预览 — 演示模式"),
      React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center" } },
        React.createElement("span", {
          style: { fontSize: 11, color: "var(--text-tertiary)" },
        }, "🖱 拖拽旋转 · 滚轮缩放 · 右键平移"),
        React.createElement("button", {
          className: "btn btn-ghost btn-xs",
          onClick: onClose,
          style: { fontSize: 16, padding: "4px 10px" },
        }, "✕"),
      ),
    ),
    /* 主体：Canvas + 控制面板 */
    React.createElement("div", {
      style: { flex: 1, display: "flex", overflow: "hidden" } as React.CSSProperties,
    },
      /* 左侧 — 3D 场景 */
      React.createElement("div", { style: { flex: 1, display: "flex", position: "relative", minWidth: 0 } as React.CSSProperties },
        React.createElement("canvas", {
          ref: canvasRef,
          style: { flex: 1, display: "block", minWidth: 0 } as React.CSSProperties,
        }),
        initErr && React.createElement("div", { style: {
          position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(0,0,0,0.7)", color: "#e53935", fontSize: 14,
        } as React.CSSProperties }, initErr),
        loading && React.createElement("div", { style: {
          position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(0,0,0,0.7)", color: "rgba(241,241,249,0.9)", fontSize: 14, letterSpacing: 1,
        } as React.CSSProperties }, "正在生成 3D 几何…"),
        latticeLoading && React.createElement("div", { style: {
          position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(0,0,0,0.7)", color: "rgba(241,241,249,0.9)", fontSize: 14, letterSpacing: 1,
        } as React.CSSProperties }, "正在加载格阵几何…"),
      ),
      /* 右侧 — 渲染控制面板（参考版 render_ctrl.py 排布） */
      React.createElement("div", {
        ref: panelRef,
        style: {
          width: 300, borderLeft: "1px solid var(--border-glass)",
          background: "var(--bg-glass)",
          display: "flex", flexDirection: "column", overflow: "hidden",
          flexShrink: 0, position: "relative",
        } as React.CSSProperties,
      },
        /* 标题：🎨 栅元渲染控制 */
        React.createElement("div", {
          style: {
            padding: "10px 14px", borderBottom: "1px solid var(--border-glass)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          } as React.CSSProperties,
        },
          React.createElement("span", {
            style: { fontSize: 13, fontWeight: 700, color: "var(--text-primary)" },
          }, "🎨 栅元渲染控制"),
          React.createElement("button", {
            className: "btn btn-primary btn-xs",
            style: { fontSize: 10 },
            onClick: () => setQuickAddOpen(true),
          }, "⚡ 快捷建栅元"),
        ),
        /* 提示 */
        React.createElement("div", {
          style: { padding: "6px 14px", fontSize: 10, color: "var(--text-tertiary)", borderBottom: "1px solid var(--border-glass)" } as React.CSSProperties,
        }, "勾选状态实时生效，仅勾选的栅元会导出到 STEP 文件"),
        /* 材料颜色对照（共享组件） */
        React.createElement(MaterialLegend, {
          entries: legendEntries.map(e => ({ mat: e.mat, comment: cellViews.find(cv => cv.mat === e.mat)?.comment })),
        }),
        /* 操作提示 */
        React.createElement("div", {
          style: { padding: "4px 14px 8px", fontSize: 10, color: "var(--text-tertiary)" } as React.CSSProperties,
        }, "← → 旋转 · 滚轮缩放 · 右键平移"),
        /* 全选/全不选 */
        React.createElement("div", {
          style: {
            padding: "6px 14px", borderBottom: "1px solid var(--border-glass)",
            display: "flex", gap: 6,
          } as React.CSSProperties,
        },
          React.createElement("button", {
            className: "btn btn-ghost btn-xs",
            onClick: () => setAllVisible(true),
            style: { flex: 1, fontSize: 11 },
          }, "全部选中"),
          React.createElement("button", {
            className: "btn btn-ghost btn-xs",
            onClick: () => setAllVisible(false),
            style: { flex: 1, fontSize: 11 },
          }, "全部取消"),
        ),
        /* 半透明查看开关（默认关 → opaque；开启 see-through 可看穿外壳） */
        React.createElement("div", {
          style: {
            padding: "8px 14px", borderBottom: "1px solid var(--border-glass)",
            display: "flex", alignItems: "center", gap: 8,
          } as React.CSSProperties,
        },
          React.createElement("input", {
            type: "checkbox",
            id: "see-through-toggle",
            checked: seeThrough,
            onChange: toggleSeeThrough,
            style: { accentColor: "var(--accent)" } as React.CSSProperties,
          }),
          React.createElement("label", {
            htmlFor: "see-through-toggle",
            style: { fontSize: 11, color: "var(--text-secondary)", cursor: "pointer", display: "flex", flexDirection: "column", gap: 2 } as React.CSSProperties,
          },
            React.createElement("span", null, "半透明查看"),
            React.createElement("span", { style: { fontSize: 10, color: "var(--text-tertiary)" } }, "默认不透明渲染（性能最佳）；开启可看穿外壳"),
          ),
        ),
        /* 色块总览开关（项1/2）：位于「半透明查看」下方；切换详细几何 ↔ 色块总览 */
        hasLattice && React.createElement("div", {
          style: {
            padding: "8px 14px", borderBottom: "1px solid var(--border-glass)",
            display: "flex", alignItems: "center", gap: 8,
          } as React.CSSProperties,
        },
          React.createElement("input", {
            type: "checkbox",
            id: "lattice-overview-toggle",
            checked: latticeOverview || latticeAuto,
            disabled: latticeAuto,
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => setLatticeOverview(e.target.checked),
            style: { accentColor: "var(--accent)" } as React.CSSProperties,
          }),
          React.createElement("label", {
            htmlFor: "lattice-overview-toggle",
            style: { fontSize: 11, color: "var(--text-secondary)", cursor: latticeAuto ? "default" : "pointer", display: "flex", flexDirection: "column", gap: 2 } as React.CSSProperties,
          },
            React.createElement("span", null, latticeAuto ? "色块总览（自动·超大）" : "色块总览"),
            React.createElement("span", { style: { fontSize: 10, color: "var(--text-tertiary)" } },
              latticeAuto ? "格位过多，已自动用色块总览（无法显示详细几何）"
                : (latticeOverview ? "按宇宙色块显示装配格位（省性能）" : "显示真实几何（性能优先）")),
          ),
        ),
        /* 截面控制 */
        React.createElement("div", {
          style: {
            padding: "8px 14px", borderBottom: "1px solid var(--border-glass)",
            fontSize: 11,
          } as React.CSSProperties,
        },
          React.createElement("div", { style: { fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 } }, "✂ 截面控制"),
          React.createElement("div", { style: { display: "flex", gap: 4, marginBottom: 4 } as React.CSSProperties },
            React.createElement("input", {
              type: "text",
              value: eqInput,
              onChange: function(e: React.ChangeEvent<HTMLInputElement>) { setEqInput(e.target.value); },
              onBlur: function() { var p = parsePlane(eqInput); if (p) setCsPlane(p); },
              onKeyDown: function(e: React.KeyboardEvent) { if (e.key === "Enter") { var p = parsePlane(eqInput); if (p) setCsPlane(p); } },
              placeholder: "X + Y + Z = 0",
              style: { flex: 1, padding: "2px 4px", fontSize: 10, background: "var(--bg-input)", border: "1px solid var(--border-glass)", color: "var(--text-primary)", borderRadius: 4, fontFamily: "Consolas,monospace" } as React.CSSProperties,
            }),
            React.createElement("button", {
              className: "btn btn-primary btn-xs",
              onClick: function() {
                var p = parsePlane(eqInput);
                if (p) fetchCrossSection(p);
              },
              style: { fontSize: 10, flexShrink: 0 },
            }, "✂ 截面"),
          ),
          React.createElement("div", { style: { display: "flex", gap: 4, alignItems: "center" } as React.CSSProperties },
            React.createElement("span", { style: { fontSize: 10, color: "var(--text-tertiary)", flexShrink: 0 } }, "步长"),
            React.createElement("button", {
              className: "btn btn-ghost btn-xs",
              onClick: function() { var v = parseFloat(csStep) || 1; setCsStep(Math.max(0.001, v / 2).toFixed(3)); },
              style: { fontSize: 10 },
            }, "◀"),
            React.createElement("span", { style: { fontSize: 10, color: "var(--text-primary)", minWidth: 30, textAlign: "center" } as React.CSSProperties }, csStep),
            React.createElement("button", {
              className: "btn btn-ghost btn-xs",
              onClick: function() { var v = parseFloat(csStep) || 1; setCsStep((v * 2).toFixed(3)); },
              style: { fontSize: 10 },
            }, "▶"),
          ),
        ),
        /* 栅元列表（共享组件）—— checkbox + 栅元N + 色点 + M材料号(可点) + 注释 */
        /* 格阵装配适配：universe 栅元（u 非空）经 fill 装配显示，不作为独立栅元列出 */
        hasLattice && React.createElement("div", {
          style: { fontSize: 10, color: "var(--text-tertiary)", padding: "2px 14px" } as React.CSSProperties,
        }, "格阵已装配：universe 栅元经 fill 显示，不单独列出"),
        hasLattice
          ? React.createElement(UniverseCellList, {
              groups: universeGroups,
              ungrouped: displayOrigIdx.map((i) => ({ num: cellViews[i].num, mat: cellViews[i].mat, comment: cellViews[i].comment, visible: cellViews[i].visible, locked: cellViews[i].mat === "0" })),
              onToggleGroup: toggleUniverseGroup,
              onToggle: (rowIndex: number) => toggleCell(displayOrigIdx[rowIndex]),
              onMaterialClick: (rowIndex: number, e: React.MouseEvent) => { setMatPicker({ i: displayOrigIdx[rowIndex], x: e.clientX, y: e.clientY }); },
            })
          : React.createElement(CellList, {
              rows: cellViews.map(cv => ({ num: cv.num, mat: cv.mat, comment: cv.comment, visible: cv.visible, locked: cv.mat === "0" })),
              onToggle: (rowIndex: number) => toggleCell(rowIndex),
              onMaterialClick: (rowIndex: number, e: React.MouseEvent) => { setMatPicker({ i: rowIndex, x: e.clientX, y: e.clientY }); },
            }),
        /* 重合检测面板（点击对 → 两栅元红色高亮） */
        React.createElement("div", {
          style: {
            padding: "8px 14px", borderTop: "1px solid var(--border-glass)",
            maxHeight: 160, overflowY: "auto",
          } as React.CSSProperties,
        },
          React.createElement("div", {
            style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 } as React.CSSProperties,
          },
            React.createElement("span", { style: { fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" } },
              overlapBusy ? "正在检测重合…"
                : (overlapResult && overlapResult.overlaps.length > 0
                  ? `重合检测：${overlapResult.overlaps.length} 对（点击高亮）`
                  : (overlapResult ? "重合检测：未发现重合 ✓" : "重合检测待运行"))),
            React.createElement("button", { className: "btn btn-ghost btn-xs", onClick: runOverlapCheck, disabled: overlapBusy }, "重新检测"),
          ),
          overlapResult && overlapResult.truncated
            ? React.createElement("div", { style: { fontSize: 10, color: "#e6a23c", marginBottom: 4 } }, "⚠ 已达上限，部分重合可能未检出")
            : null,
          overlapResult && overlapResult.overlaps.length > 0
            ? overlapResult.overlaps.map((o, oi) => React.createElement("div", {
                key: oi,
                onClick: () => highlightPair(o.a, o.b),
                style: {
                  display: "flex", gap: 8, fontSize: 11, padding: "3px 4px",
                  borderRadius: 4, cursor: "pointer", background: "rgba(255,255,255,0.03)",
                  marginBottom: 2,
                } as React.CSSProperties,
              },
                React.createElement("span", { style: { color: o.severity === "error" ? "#e53935" : o.severity === "warning" ? "#e6a23c" : "#9e9e9e" } },
                  o.severity === "error" ? "●" : o.severity === "warning" ? "▲" : "·"),
                React.createElement("span", null, `栅元 ${o.a} × 栅元 ${o.b}`),
                React.createElement("span", { style: { color: "var(--text-tertiary)" } },
                  `占比 ${(o.volumeFraction * 100).toFixed(0)}%${o.suspected ? "（疑似）" : ""}`),
              ))
            : null,
          overlapResult && overlapResult.unresolved && overlapResult.unresolved.length > 0
            ? React.createElement("div", { style: { fontSize: 10, color: "var(--text-tertiary)", marginTop: 4 } },
                `${overlapResult.unresolved.length} 对检测不可靠（布尔/采样失败）`)
            : null,
        ),
        /* 底部：计数 + 关闭 */
        React.createElement("div", {
          style: {
            padding: "8px 14px", borderTop: "1px solid var(--border-glass)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          } as React.CSSProperties,
        },
          React.createElement("span", {
            style: { fontSize: 11, color: "var(--text-tertiary)" },
          }, `${visibleCount}/${cellViews.length} 显示`),
          React.createElement("button", {
            className: "btn btn-primary btn-xs",
            onClick: onClose,
          }, "关闭"),
        ),
        /* 快捷建栅元覆盖层（替代侧栏显示；线框直接画进主场景） */
        quickAddOpen && React.createElement("div", {
          style: {
            position: "absolute", inset: 0, zIndex: 20,
            background: "var(--bg-surface)",
            display: "flex", flexDirection: "column", overflow: "hidden",
          } as React.CSSProperties,
        },
          React.createElement("div", {
            style: {
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.08)",
            } as React.CSSProperties,
          },
            React.createElement("span", { style: { fontSize: 13, fontWeight: 700, color: "var(--text-primary)" } }, "⚡ 快捷建栅元"),
            React.createElement("button", {
              className: "btn btn-ghost btn-xs",
              onClick: restoreQuickCellPanel,
            }, "恢复栅元控制"),
          ),
          React.createElement("div", {
            style: { flex: 1, overflowY: "auto", padding: "12px 14px" } as React.CSSProperties,
          },
            React.createElement(QuickCellForm, {
              surfacesText: surfaces || "",
              trCardsText: trCards || "",
              cellNumbers: rawCells.map(c => parseInt(c.num) || 0),
              materials: (matList || []).map(m => ({ number: m.number, comment: (m as any).comment, density: (m as any).density })),
              modeN: !!(deck.basic as any)?.mode_n,
              modeP: !!(deck.basic as any)?.mode_p,
              modeE: !!(deck.basic as any)?.mode_e,
              onGenerate: handleQuickCellGenerate,
              onConfigChange: onQuickConfigChange,
              onCancel: restoreQuickCellPanel,
              keepOpenAfterGenerate: true,
            }),
          ),
        ),
      ),
   ),
  ),
    csSlices && React.createElement(CrossSectionView, {
      slices: csSlices,
      plane: csPlane,
      onClose: function() { setCsSlices(null); },
      onPlaneChange: function(newPlane: any) { fetchCrossSection(newPlane); },
    }),
    /* 材料选择浮层（点击栅元行的 M材料号 弹出）——点击外部遮罩或 ✕ 关闭 */
    matPicker && React.createElement(React.Fragment, { key: "mat-picker" },
      React.createElement("div", {
        onClick: function() { setMatPicker(null); },
        style: { position: "fixed", inset: 0, zIndex: 1150, background: "transparent" } as React.CSSProperties,
      }),
      React.createElement("div", {
        className: "preview-overlay",  // 强制深色文字变量，亮色主题下可读
        style: {
          position: "fixed",
          left: Math.min(matPicker.x, window.innerWidth - 220),
          top: Math.min(matPicker.y, window.innerHeight - 300),
          zIndex: 1200, width: 210, maxHeight: 300, overflow: "auto",
          background: "rgba(15,15,40,0.97)",
          border: "1px solid rgba(255,255,255,0.15)", borderRadius: 8,
          boxShadow: "0 8px 24px rgba(0,0,0,0.5)", padding: "8px",
        } as React.CSSProperties,
      },
        React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 } as React.CSSProperties },
          React.createElement("span", { style: { fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" } as React.CSSProperties },
            `选择材料 — 栅元 ${cellViews[matPicker.i]?.num ?? ""}`),
          React.createElement("button", {
            onClick: function() { setMatPicker(null); },
            style: { background: "transparent", border: "none", color: "var(--text-tertiary)", fontSize: 13, cursor: "pointer", padding: "0 2px", lineHeight: 1 } as React.CSSProperties,
          }, "✕"),
        ),
        materialOptions.map((o) => React.createElement("button", {
          key: o.num,
          onClick: function() { applyMaterial(matPicker.i, o.num); },
          style: {
            display: "block", width: "100%", textAlign: "left", padding: "5px 8px", marginBottom: 2,
            fontSize: 11, borderRadius: 4, cursor: "pointer", border: "none",
            color: o.num === cellViews[matPicker.i]?.mat ? "var(--accent)" : "var(--text-primary)",
            background: o.num === cellViews[matPicker.i]?.mat ? "rgba(255,255,255,0.08)" : "transparent",
          } as React.CSSProperties,
        }, o.label)),
      ),
    ),
    /* 快捷建栅元重合决策（在 3D 预览页内提示） */
    quickCheck && React.createElement(FloatingDialog, {
      title: `新栅元与栅元 ${quickCheck.existingNums.join("、")} 重合`,
      onClose: () => applyQuickCheck("none"),
      width: 440,
    },
      React.createElement("div", { style: { fontSize: 12, lineHeight: 1.7 } },
        React.createElement("div", { style: { marginBottom: 10, color: "var(--text-secondary)" } },
          "选择如何处理（点击即应用）："),
        quickCheck.zeroVolume.length > 0
          ? React.createElement("div", { style: { marginBottom: 8, color: "#e53935", fontSize: 11 } },
              `⚠ 体积为零的栅元：${quickCheck.zeroVolume.join("、")}（空/退化几何，请检查参数）`)
          : null,
        ["new_hole", "existing_hole", "void_only", "none"].map(ch => {
          const label = ch === "new_hole" ? "新栅元避开已有（新 # 重合栅元）"
            : ch === "existing_hole" ? "被侵占栅元让位（重合栅元 # 新栅元）"
            : ch === "void_only" ? "只占真空（真空让位 # 新；新 # 非真空）"
            : "保持原样（可能重叠）";
          return React.createElement("button", {
            key: ch, className: "btn btn-sm", style: { display: "block", width: "100%", marginBottom: 6, textAlign: "left" },
            onClick: () => applyQuickCheck(ch as any),
          }, label);
        }),
      ),
    ),
  );
}
