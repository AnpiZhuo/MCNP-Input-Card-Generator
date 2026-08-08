/**
 * Preview3D — Three.js 3D 预览窗口
 *
 * 优先从后端 FreeCAD STL 加载真实几何，不可用时回退到模拟几何体。
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
  
  /* 相机 — 尺寸由 ResizeObserver 驱动，初始用容器实际尺寸 */
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(rect.width, 1);
  const h = Math.max(rect.height, 1);
  const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, viewDist * 100);
  camera.position.set(viewDist * 0.6, viewDist * 0.6, viewDist * 0.5);
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

  /* 网格 — 大范围覆盖 */
  
  /* ---- 动态数轴线（正负双向无限延伸） ---- */
  const AXIS_COLORS = [0xff4444, 0x44ff44, 0x4488ff];
  const AXIS_LABELS = ["X", "Y", "Z"];
  const AXIS_EXTENT = sceneExtent * 3;

  // 三条彩色轴线（从 -extent 到 +extent）；标签存数组以便 updateAxes 重定位
  const axisLines: THREE.Line[] = [];
  const axisLabels: { sprite: THREE.Sprite; dir: THREE.Vector3; sign: number }[] = [];
  const axisDirs = [
    new THREE.Vector3(1, 0, 0),
    new THREE.Vector3(0, 0, 1),
    new THREE.Vector3(0, 1, 0),
  ];
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

  // 动态刻度标签容器
  const tickGroup = new THREE.Group();
  scene.add(tickGroup);

  function makeNumberSprite(text: string, color: number, scale = 0.6): THREE.Sprite | null {
    try {
      const c = document.createElement("canvas"); c.width = 128; c.height = 48;
      const ctx = c.getContext("2d");
      if (!ctx) return null;
      ctx.fillStyle = "rgba(0,0,0,0.4)";
      ctx.fillRect(0, 4, 128, 40);
      ctx.fillStyle = "#" + color.toString(16).padStart(6, "0");
      ctx.font = "Bold 28px Arial"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(text, 64, 26);
      const tex = new THREE.CanvasTexture(c);
      const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, sizeAttenuation: true });
      const sprite = new THREE.Sprite(mat);
      if (sprite && sprite.scale) sprite.scale.set(scale, scale * 0.35, 1);
      return sprite;
    } catch(e) { console.warn("[3D] makeNumberSprite error:", e); return null; }
  }

  function rebuildTicks() {
    try {
    // 清除旧刻度
    while (tickGroup.children.length) {
      const child = tickGroup.children[0];
      if ((child as THREE.Sprite).material) ((child as THREE.Sprite).material as THREE.Material).dispose();
      tickGroup.remove(child);
    }

    // 严格步长查表：基于镜头视野可见高度，保证始终约 8~10 个刻度
    const STEPS = [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 20, 50, 100, 200, 500];
    const dist = camera.position.length();
    const rawStep = dist / 10;
    let step = STEPS[0];
    for (const s of STEPS) { if (s >= rawStep) { step = s; break; } }
    const tickDecimals = Math.max(0, Math.ceil(-Math.log10(step)));

    const extent = dist * 2;
    const tickLen = 0.15 * (dist / 8);

    for (let ai = 0; ai < 3; ai++) {
      const dir = axisDirs[ai];
      const color = AXIS_COLORS[ai];
      const perp1 = new THREE.Vector3();
      const perp2 = new THREE.Vector3();
      if (ai === 0) { perp1.set(0, 0, 1); perp2.set(0, 1, 0); }
      else if (ai === 1) { perp1.set(1, 0, 0); perp2.set(0, 1, 0); }
      else { perp1.set(1, 0, 0); perp2.set(0, 0, 1); }

      const start = Math.ceil(-extent / step) * step;
      for (let s = start; s <= extent; s += step) {
        if (Math.abs(s) < step * 0.01) continue;
        const pos = dir.clone().multiplyScalar(s);
        const tA = pos.clone().add(perp1.clone().multiplyScalar(-tickLen));
        const tB = pos.clone().add(perp1.clone().multiplyScalar(tickLen));
        const tickGeo = new THREE.BufferGeometry().setFromPoints([tA, tB]);
        const tickLine = new THREE.Line(tickGeo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 }));
        tickGroup.add(tickLine);
        const label = s.toFixed(tickDecimals);
        const sprite = makeNumberSprite(label, color, dist / 12);
        if (sprite) {
          sprite.position.copy(pos.clone().add(perp1.clone().multiplyScalar(-tickLen * 2.5)).add(perp2.clone().multiplyScalar(-tickLen * 1.5)));
          tickGroup.add(sprite);
        }
      }
    }
    } catch(e) { console.warn("[3D] rebuildTicks error:", e); }
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
  controls.minDistance = sceneExtent * 0.1;
  controls.maxDistance = sceneExtent * 50;
  controls.target.set(0, 0, 0);
  controls.addEventListener("change", scheduleRebuild);

  /* ---- WASD+Shift+Space 镜头控制 ---- */
  const keys: Record<string, boolean> = {};
  function onKeyDown(e: KeyboardEvent) {
    if (e.code === "KeyW" || e.code === "KeyA" || e.code === "KeyS" || e.code === "KeyD") keys[e.code] = true;
    if (e.code === "ShiftLeft" || e.code === "ShiftRight") keys.shift = true;
    if (e.code === "Space") keys.space = true;
  }
  function onKeyUp(e: KeyboardEvent) {
    if (e.code === "KeyW" || e.code === "KeyA" || e.code === "KeyS" || e.code === "KeyD") keys[e.code] = false;
    if (e.code === "ShiftLeft" || e.code === "ShiftRight") keys.shift = false;
    if (e.code === "Space") keys.space = false;
  }
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);

  /* 创建栅元几何体（带 LOD 动态细节） */
  // 不创建模拟几何，等 STL 数据到达后由 loadStlMeshes 加载
  var meshes: THREE.Object3D[] = [];
  var cellColors: string[] = [];
  var cellNums: string[] = [];

  function loadStlMeshes(stlData: any, cellViews: CellView[]) {
    // 清掉旧网格，避免重复加载产生副本（否则 setVisible 只隐藏第一个，副本残留）
    meshes.forEach(m => {
      scene.remove(m);
      (m as any).geometry?.dispose();
      (m as any).material?.dispose();
    });
    meshes.length = 0;
    cellColors.length = 0;
    cellNums.length = 0;
    var loader = new STLLoader();
    var stlCount = 0;
    var allBounds: THREE.Box3[] = [];
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
        var color = new THREE.Color(cv.color === "transparent" ? "#000000" : cv.color);
        var mat = new THREE.MeshStandardMaterial({ color: color, roughness: 0.3, metalness: 0.0, transparent: true, opacity: cv.color === "transparent" ? 0 : 0.6, depthWrite: false, side: THREE.FrontSide });
        var mesh = new THREE.Mesh(geo, mat);
        mesh.userData.index = idx;
        scene.add(mesh);
        meshes.push(mesh);
        cellColors.push(cv.color);
        cellNums.push(cv.num);
        geo.computeBoundingBox();
        if (geo.boundingBox) allBounds.push(geo.boundingBox);
        stlCount++;
      } catch(e) { console.error("STL load error for cell", key, e); }
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
    // 根据实际几何重新定位相机
    if (allBounds.length > 0) {
      var totalBox = new THREE.Box3();
      for (var _b of allBounds) totalBox.union(_b);
      var _s = totalBox.getSize(new THREE.Vector3());
      var realExt = Math.max(_s.x, _s.y, _s.z, 1) * 0.5;
      var realVD = realExt * 3.5;
      camera.position.set(realVD * 0.6, realVD * 0.6, realVD * 0.5);
      controls.target.set(0, 0, 0);
      controls.minDistance = realExt * 0.1;
      controls.maxDistance = realExt * 50;
      camera.far = realVD * 100;
      camera.updateProjectionMatrix();
      updateAxes(realExt);  // 轴线随实际几何范围伸缩，呈现"无限长"效果
    }
    return stlCount;
  }


  /* 动画循环 */
  let running = true;
  function animate() {
    if (!running) return;
    requestAnimationFrame(animate);
    // WASD 镜头移动
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
    }
    controls.update();
    for (const obj of meshes) {
      if (obj instanceof THREE.LOD) obj.update(camera);
    }
    renderer.render(scene, camera);
  }
  animate();

  /* 大小自适应 — 用 ResizeObserver 确保 canvas 始终有尺寸 */
  function resizeRenderer() {
    const r = canvas.getBoundingClientRect();
    const w2 = Math.max(r.width, 1);
    const h2 = Math.max(r.height, 1);
    if (w2 <= 1 || h2 <= 1) { setTimeout(resizeRenderer, 50); return; }
    camera.aspect = w2 / h2;
    camera.updateProjectionMatrix();
    renderer.setSize(w2, h2, false);
  }
  var ro = new ResizeObserver(function() { resizeRenderer(); });
  if (canvas.parentElement) ro.observe(canvas.parentElement);
  setTimeout(resizeRenderer, 100); // 首次初始化延迟执行，等待布局

  /* 返回控制接口 */
  return {
    loadStlMeshes: loadStlMeshes,
    updateAxes: updateAxes,
    setVisible(index: number, vis: boolean) {
      for (var _mi = 0; _mi < meshes.length; _mi++) {
        if (meshes[_mi].userData.index === index) { meshes[_mi].visible = vis; return; }
      }
    },
    setColor(index: number, color: string) {
      for (var _mi = 0; _mi < meshes.length; _mi++) {
        if (meshes[_mi].userData.index === index) {
          var _mat = (meshes[_mi] as THREE.Mesh).material as THREE.MeshStandardMaterial;
          if (color === "transparent") {
            _mat.color.set("#000000");
            _mat.opacity = 0;   // M0 真空 → 全透明
          } else {
            _mat.color.set(color);
            _mat.opacity = 0.6; // 实体材料 → 恢复半透明
          }
          return;
        }
      }
    },
    selectAll(vis: boolean) {
      meshes.forEach((m) => { m.visible = vis; });
    },
    dispose() {
      running = false;
      ro.disconnect();
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      controls.dispose();
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
    fetch("http://localhost:5001/api/cross-section", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cellNums: cellNums,
        plane: newPlane,
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
    // 用实际曲面和栅元数据调用后端生成 STL
    var cellsForBackend = rawCells.map(function(c) {
      return { number: parseInt(c.num) || 0, material: c.mat, density: (c as any).density || "", surface_expr: (c as any).surfaces || (c as any).surface_expr || "" };
    });
    fetch("http://localhost:5001/api/preview-3d", {
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
    }).catch(function() { setFreecadStatus("  "); });
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
