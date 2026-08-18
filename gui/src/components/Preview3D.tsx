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

/* ---- 类型定义 ---- */
interface CellView {
  num: string;
  mat: string;
  comment: string;
  visible: boolean;
  color: string;
}

interface Preview3DProps {
  cells: { num: string; mat: string; comment?: string; render?: boolean }[];
  surfaces?: string;
  trCards?: string;
  onClose: () => void;
  /** 用户改了某个栅元的材料号后回调（num=栅元号, newMat=新材料号） */
  onMaterialChange?: (cellNum: string, newMat: string) => void;
  /** 独立窗口模式：由宿主传入材料列表（{number, comment}），替代 useDeck() */
  materials?: { number: number; comment?: string }[];
}

/* ---- 色板（10 色，按材料号取模） ---- */
import { getMatColor as getColor } from "../utils/materialColors";
import { MaterialLegend, CellList } from "./MaterialPanel";
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
  console.log("[3D] initScene entry, canvas:", canvas?.width, canvas?.height, "parent:", canvas?.parentElement?.clientWidth);
  /* 初始场景尺寸（等 STL 加载后根据实际几何更新） */
  var sceneExtent = 10;
  var viewDist = 35;

  /* 场景 */
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);

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
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
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
  // 原始 STL 坐标系的模型中心（loadStlMeshes 归一化平移时记录，供截面平面坐标换算）
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
    var rawBounds: THREE.Box3[] = [];
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
        scene.add(mesh);
        meshes.push(mesh);
        geo.computeBoundingBox();   // 归一化前先算原始 bbox（用于求总中心）
        if (geo.boundingBox) rawBounds.push(geo.boundingBox.clone());
        stlCount++;
      } catch(e) { console.error("STL load error for cell", key, e); }
    }

    /* 几何归一化：先把全部栅元平移到总中心 → 相机靶心在原点、轴线/刻度天然对齐。
       顺序关键：geometry.translate 必须先于 computeBoundingBox，否则 renderOrder 排序用旧 bbox。 */
    if (rawBounds.length > 0) {
      var totalBox = new THREE.Box3();
      for (var _b of rawBounds) totalBox.union(_b);
      var c = totalBox.getCenter(new THREE.Vector3());
      modelCenter.x = c.x;
      modelCenter.y = c.y;
      modelCenter.z = c.z;
      for (var _m of meshes) {
        // 平移先于 computeBoundingBox（顺序关键：renderOrder 排序用平移后的 bbox）
        (_m as THREE.Mesh).geometry.translate(-c.x, -c.y, -c.z);
        (_m as THREE.Mesh).geometry.computeBoundingBox();
      }
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

    // 根据归一化后的实际几何重新定位相机（far/near 收紧，target=center≈原点）
    if (meshes.length > 0) {
      var normBox = new THREE.Box3();
      for (var _m3 of meshes) {
        var bb = (_m3 as THREE.Mesh).geometry?.boundingBox;
        if (bb) normBox.union(bb);
      }
      var nC = normBox.getCenter(new THREE.Vector3());
      var nS = normBox.getSize(new THREE.Vector3());
      var cp = computeCameraParams([nC.x, nC.y, nC.z], [nS.x, nS.y, nS.z]);
      camera.near = cp.near;
      camera.far = cp.far;
      camera.position.set(cp.position[0], cp.position[1], cp.position[2]);
      controls.target.set(cp.target[0], cp.target[1], cp.target[2]);
      controls.minDistance = cp.minDistance;
      controls.maxDistance = cp.maxDistance;
      camera.updateProjectionMatrix();
      controls.update();
      updateAxes(Math.max(nS.x, nS.y, nS.z, 1) * 0.5);  // 轴线随实际几何范围伸缩，呈现"无限长"效果
    }
    markDirty();
    return stlCount;
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
export default function Preview3D({ cells: rawCells, surfaces, trCards, onClose, onMaterialChange, materials }: Preview3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ctrlRef = useRef<ReturnType<typeof initScene> | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const { deck } = useDeck();
  // 独立窗口模式：材料列表由宿主传入（materials），否则回退主窗口 deck
  const matList = materials ?? deck.materials;

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
  const [csPlane, setCsPlane] = useState({A:0,B:0,C:1,D:0});
  const [dbgLog, setDbgLog] = useState<string[]>([]);
  const log = (msg: string) => { console.log('[3Ddbg]', msg); setDbgLog(p => [...p, msg]); };
  const [csSlices, setCsSlices] = useState<any[] | null>(null);
  // 材料选择浮层：i=cellViews 索引, x/y=点击屏幕坐标
  const [matPicker, setMatPicker] = useState<{ i: number; x: number; y: number } | null>(null);

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
    // 用实际曲面和栅元数据调用后端生成 STL；fetch 期间显示加载遮罩
    setLoading(true);
    var cellsForBackend = rawCells.map(function(c) {
      return { number: parseInt(c.num) || 0, material: c.mat, density: (c as any).density || "", surface_expr: (c as any).surfaces || (c as any).surface_expr || "" };
    });
    fetch(apiUrl("/api/preview-3d"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        surfaces: surfaces || "",
        cells: cellsForBackend,
        tr_cards: trCards || "",
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
  }, []);

  // 初始化 Three.js 场景
  const [initErr, setInitErr] = useState("");
  useEffect(() => {
    if (!canvasRef.current) return;
      try {
      console.log("[3D] initScene start");
      ctrlRef.current = initScene(canvasRef.current, cellViews);
      console.log("[3D] initScene done");
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
    }
  }, [stlData]);

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
  const CellType = "div"; // placeholder type

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
        padding: "12px 20px", borderBottom: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(10,10,30,0.8)",
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
      ),
      /* 右侧 — 渲染控制面板（参考版 render_ctrl.py 排布） */
      React.createElement("div", {
        ref: panelRef,
        style: {
          width: 300, borderLeft: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(10,10,30,0.6)",
          display: "flex", flexDirection: "column", overflow: "hidden",
          flexShrink: 0,
        } as React.CSSProperties,
      },
        /* 标题：🎨 栅元渲染控制 */
        React.createElement("div", {
          style: {
            padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          } as React.CSSProperties,
        },
          React.createElement("span", {
            style: { fontSize: 13, fontWeight: 700, color: "rgba(241,241,249,0.8)" },
          }, "🎨 栅元渲染控制"),
        ),
        /* 提示 */
        React.createElement("div", {
          style: { padding: "6px 14px", fontSize: 10, color: "var(--text-tertiary)", borderBottom: "1px solid rgba(255,255,255,0.04)" } as React.CSSProperties,
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
            padding: "6px 14px", borderBottom: "1px solid rgba(255,255,255,0.04)",
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
            padding: "8px 14px", borderBottom: "1px solid rgba(255,255,255,0.04)",
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
        /* 截面控制 */
        React.createElement("div", {
          style: {
            padding: "8px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)",
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
              style: { flex: 1, padding: "2px 4px", fontSize: 10, background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.1)", color: "var(--text-primary)", borderRadius: 4, fontFamily: "Consolas,monospace" } as React.CSSProperties,
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
        React.createElement(CellList, {
          rows: cellViews.map(cv => ({ num: cv.num, mat: cv.mat, comment: cv.comment, visible: cv.visible, locked: cv.mat === "0" })),
          onToggle: toggleCell,
          onMaterialClick: (i: number, e: React.MouseEvent) => { setMatPicker({ i, x: e.clientX, y: e.clientY }); },
        }),
        /* 底部：计数 + 关闭 */
        React.createElement("div", {
          style: {
            padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,0.06)",
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
  );
}
