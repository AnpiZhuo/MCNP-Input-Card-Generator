/**
 * VolumeRenderer — Three.js 体积渲染器（契约 meshtal-visualization.md §4.7 / §7 / §8）
 *
 * 场景组装：外壳 STL（复用 STLLoader + cellMaterial + renderGate + computeCameraParams）
 * + 体积盒（ShaderMaterial + DataTexture3D）+ OrbitControls + 归一化对齐（alignWorld §7）。
 *
 * 对齐（§7.2）：volumeWorldBox 与 shellBox 求 union → offset=-unionBox.center →
 * 外壳 STL 与体积盒共用同一 offset（世界坐标相对几何逐点保留，两者重合关系一致）。
 *
 * 数据（§2.2 流）：meshtal-texture 返回标量帧 → colorize CPU 上色（RGBA）→
 * DataTexture3D 一次创建，`texSubImage3D` 复用上传当前帧（setFrame 只改 image.data）。
 *
 * A2.1 开窗自动取景：相机按「几何+体积联合包围盒」摆位（computeVolumeCamera）。
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { computeCameraParams, type CameraParams } from "../three/cameraParams";
import { createRenderLoop } from "../three/renderGate";
import {
  buildCellMaterial,
  DEFAULT_SHELL_OPACITY,
  type CellMaterialSpec,
  type TransparentMode,
} from "../three/cellMaterial";
import { buildRayMarchMaterial, isWebGL2, WEBGL2_UNAVAILABLE } from "./volumeShader";
import { colorizeScalar, weatherLut, defaultDisplayMin, type ScalarRange } from "./colorize";
import {
  unionBoxes,
  boxCenter,
  boxSize,
  translateToCenter,
  computeFramingBox,
  applyOffset,
  applyOffsetToBox,
  type AABB,
  type Vec3,
} from "./alignWorld";

export interface VolumeFrame {
  resolution: [number, number, number];
  worldBox: { min: [number, number, number]; max: [number, number, number] };
  dataBase64: string;
  scalarRange: ScalarRange;
}

export interface CellView {
  num: string;
  mat: string;
  comment: string;
  visible: boolean;
  color: string;
}

export interface TimeOption {
  index: number;
  label: string;
}

export interface VolumeRendererOptions {
  stlData: Record<string, string>;
  cellViews: CellView[];
  frame: VolumeFrame;
  /** 初始色阶下限（自适应显示阈值）；缺省 → defaultDisplayMin(frame.scalarRange) 保守兜底 */
  initialDisplayMin?: number;
  /** 能量/时间选项（时间轴动画用；timeOptions.length>1 才有时间轴） */
  energyOptions?: TimeOption[];
  timeOptions?: TimeOption[];
  /** 时间轴帧回调（seek/play 时由宿主取纹理并 setFrame） */
  onTimeSeek?: (timeIdx: number) => void;
  timeIntervalMs?: number;
  onError?: (msg: string) => void;
}

export interface VolumeRendererHandle {
  /** 体积透明度（体积数据层 uOpacity uniform） */
  setOpacity(v: number): void;
  /** 栅元透明度（几何外壳连续透明度 0~1） */
  setShellOpacity(v: number): void;
  setShellVisible(v: boolean): void;
  setFrame(frame: VolumeFrame): void;
  setColorizeRange(range: ScalarRange, displayMin: number): void;
  setTransparentMode(mode: TransparentMode): void;
  setCellVisible(index: number, vis: boolean): void;
  selectAll(vis: boolean): void;
  play(): void;
  pause(): void;
  seek(timeIdx: number): void;
  dispose(): void;
  markDirty(): void;
}

/** A2.1 开窗自动取景：按「几何+体积」联合包围盒摆相机（纯函数，vitest 可测） */
export function computeVolumeCamera(unionBox: AABB): CameraParams {
  const c = boxCenter(unionBox);
  const s = boxSize(unionBox);
  return computeCameraParams(c, s);
}

/** 体积透明度默认值（体积数据层 uOpacity；100% 最实） */
export const DEFAULT_VOLUME_OPACITY = 1;

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

export interface DerivedOpacity {
  /** 栅元外壳材质参数（由「栅元透明度」滑杆派生） */
  shellSpec: CellMaterialSpec;
  /** 体积数据层 uniform 值（由「体积透明度」滑杆派生） */
  volumeUniform: number;
}

/**
 * 双透明度滑杆 → 渲染参数派生（纯函数）：
 * - 栅元透明度（控外壳）：0 → 全透明；1 → 不透明（depthWrite 恢复，无 overdraw）；(0,1) → semi 半透明
 * - 体积透明度（控体积数据层）：直接映射 uOpacity uniform
 * 两者独立、可叠加（用户反馈：一个滑杆语义不清、且原滑杆只控体积层）。
 */
export function deriveOpacity(shellOpacity: number, volumeOpacity: number, color = "#3366ff"): DerivedOpacity {
  const so = clamp01(shellOpacity);
  const vo = clamp01(volumeOpacity);
  return {
    shellSpec: buildCellMaterial({
      color,
      transparentMode: so >= 1 ? "opaque" : "semi",
      opacity: so,
    }),
    volumeUniform: vo,
  };
}

export interface VolumeBoxScene {
  /** 体积盒 Mesh position（世界盒中心 + 归一化 offset） */
  position: Vec3;
  /** 体积盒 Mesh scale（世界尺寸，单位盒放大到真实体积） */
  scale: Vec3;
  /** shader uBoxMin（场景空间） */
  boxMin: Vec3;
  /** shader uBoxMax（场景空间） */
  boxMax: Vec3;
}

/**
 * 体积盒场景变换（纯函数，PM 补充指令：真实文件体积层链路可测性）：
 * 世界盒 + 归一化 offset → Mesh position/scale + ray-march shader uBoxMin/uBoxMax。
 * 渲染链路关键一环：position/scale 错了体积层就显示错位，uBoxMin/uBoxMax 错了光线步进盒就错。
 */
export function volumeBoxSceneTransform(volumeWorldBox: AABB, offset: Vec3): VolumeBoxScene {
  const vc = boxCenter(volumeWorldBox);
  const vs = boxSize(volumeWorldBox);
  return {
    position: [vc[0] + offset[0], vc[1] + offset[1], vc[2] + offset[2]],
    scale: [vs[0], vs[1], vs[2]],
    boxMin: applyOffset(volumeWorldBox.min, offset),
    boxMax: applyOffset(volumeWorldBox.max, offset),
  };
}

/**
 * Data3DTexture 维度：后端 numpy (x,y,z) 扁平布局（z 最快）→ dims=(nk,nj,ni)，
 * 与 frame.resolution=[ni,nj,nk] 一一对应（纹理维度错则体积层采样错位/不可见）。
 */
export function textureDimsFromResolution(resolution: [number, number, number]): [number, number, number] {
  const [ni, nj, nk] = resolution;
  return [nk, nj, ni];
}

/** base64 → Uint8Array */
export function base64ToBytes(b64: string): Uint8Array {
  const raw = atob(b64);
  const buf = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i) & 0xff;
  return buf;
}

export function createVolumeRenderer(
  canvas: HTMLCanvasElement,
  opts: VolumeRendererOptions,
): VolumeRendererHandle {
  if (!isWebGL2()) {
    opts.onError?.(WEBGL2_UNAVAILABLE);
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(rect.width || 800, 1);
  const h = Math.max(rect.height || 600, 1);

  const initCam = computeCameraParams([0, 0, 0], [10, 10, 10]);
  const camera = new THREE.PerspectiveCamera(45, w / h, initCam.near, initCam.far);
  camera.up.set(0, 0, 1); // Z-up

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

  /* ── 外壳 STL 网格（独立场景，复用 cellMaterial 勾选显隐）── */
  const shellMeshes: THREE.Mesh[] = [];
  // 栅元外壳默认半透明（用户反馈 #3），连续透明度由「栅元透明度」滑杆控制
  let shellOpacity = DEFAULT_SHELL_OPACITY;

  function cellIndex(cellNum: string): number {
    const views = opts.cellViews || [];
    for (let i = 0; i < views.length; i++) if (views[i].num === cellNum) return i;
    return 0;
  }

  /** 外壳材质规格：透明度滑杆 0~1 → semi 半透明；1 → opaque（无 overdraw） */
  function shellSpecFor(color: string): CellMaterialSpec {
    return buildCellMaterial({
      color,
      transparentMode: shellOpacity >= 1 ? "opaque" : "semi",
      opacity: shellOpacity,
    });
  }

  function applyShellMaterial(mesh: THREE.Mesh, color: string) {
    const spec = shellSpecFor(color);
    const mat = mesh.material as THREE.MeshStandardMaterial;
    mat.color.set(spec.color);
    mat.transparent = spec.transparent;
    mat.depthWrite = spec.depthWrite;
    mat.opacity = spec.opacity;
    mat.needsUpdate = true;
  }

  function loadShell() {
    for (const m of shellMeshes) {
      scene.remove(m);
      m.geometry.dispose();
      (m.material as THREE.Material).dispose();
    }
    shellMeshes.length = 0;
    const loader = new STLLoader();
    const rawBounds: THREE.Box3[] = [];
    const stlData = opts.stlData || {};
    for (const key in stlData) {
      try {
        const bytes = base64ToBytes(stlData[key]);
        const geo = loader.parse(bytes.buffer as ArrayBuffer);
        const idx = cellIndex(key);
        const cv = (opts.cellViews || [])[idx] || { color: "#888888", visible: true };
        const spec = shellSpecFor(cv.color);
        const mat = new THREE.MeshStandardMaterial({
          color: spec.color, roughness: 0.3, metalness: 0,
          transparent: spec.transparent, opacity: spec.opacity,
          depthWrite: spec.depthWrite, side: THREE.FrontSide,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.userData.index = idx;
        mesh.userData.color = cv.color;
        scene.add(mesh);
        shellMeshes.push(mesh);
        geo.computeBoundingBox();
        if (geo.boundingBox) rawBounds.push(geo.boundingBox.clone());
      } catch (e) {
        console.error("[volume] STL load error for cell", key, e);
      }
    }
    return rawBounds;
  }

  /* ── 体积盒 + DataTexture3D ── */
  const volumeWorldBox: AABB = { min: [...opts.frame.worldBox.min] as [number, number, number], max: [...opts.frame.worldBox.max] as [number, number, number] };
  const [ni, nj, nk] = opts.frame.resolution;

  // Data3DTexture 一次创建：dims=(nk,nj,ni) 匹配后端 numpy (x,y,z) 扁平布局（z 最快）
  // （three 0.160 类名 Data3DTexture，DataTexture3D 为旧名）
  const dataTexture = new THREE.Data3DTexture(null, nk, nj, ni);
  dataTexture.format = THREE.RGBAFormat;
  dataTexture.type = THREE.UnsignedByteType;
  dataTexture.minFilter = THREE.LinearFilter;
  dataTexture.magFilter = THREE.LinearFilter;
  dataTexture.generateMipmaps = false;

  const volumeMat = buildRayMarchMaterial({ texture: dataTexture });
  const volumeBox = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), volumeMat);
  scene.add(volumeBox);

  let lut = weatherLut(256);
  let colorRange: ScalarRange = { min: opts.frame.scalarRange.min, max: opts.frame.scalarRange.max };
  // 自适应色阶下限（数量级自适应）：宿主可传 initialDisplayMin（由帧数据最小正值推算），
  // 缺省走保守兜底 max*1e-6（隐去纯零背景）
  let displayMin = opts.initialDisplayMin ?? defaultDisplayMin(opts.frame.scalarRange);

  function applyColorize(frame: VolumeFrame) {
    const scalar = base64ToBytes(frame.dataBase64);
    const rgba = colorizeScalar(scalar, lut, colorRange, displayMin, frame.scalarRange);
    // image.data 类型为联合（Uint8Array/Uint8ClampedArray…），运行期赋值 Uint8Array 合法
    (dataTexture.image as any).data = rgba;
    dataTexture.needsUpdate = true; // 复用纹理对象，texSubImage3D 更新当前帧
  }

  /* ── 统一归一化对齐（§7.2）：外壳与体积盒共用同一 offset ── */
  function alignAndFrame() {
    const rawBounds = loadShell();
    let shellBox: AABB;
    if (rawBounds.length > 0) {
      const tb = new THREE.Box3();
      for (const b of rawBounds) tb.union(b);
      shellBox = { min: [tb.min.x, tb.min.y, tb.min.z], max: [tb.max.x, tb.max.y, tb.max.z] };
    } else {
      shellBox = { min: [...volumeWorldBox.min], max: [...volumeWorldBox.max] };
    }
    const unionBox = unionBoxes([shellBox, volumeWorldBox]);
    const offset = translateToCenter(
      shellMeshes.map((m) => m.geometry as unknown as { translate(x: number, y: number, z: number): void }),
      unionBox,
    );
    // 体积盒场景变换（Mesh position/scale + shader uBoxMin/uBoxMax，统一 offset）
    const vt = volumeBoxSceneTransform(volumeWorldBox, offset);
    volumeBox.position.set(vt.position[0], vt.position[1], vt.position[2]);
    volumeBox.scale.set(vt.scale[0], vt.scale[1], vt.scale[2]);
    volumeMat.uniforms.uBoxMin.value.set(vt.boxMin[0], vt.boxMin[1], vt.boxMin[2]);
    volumeMat.uniforms.uBoxMax.value.set(vt.boxMax[0], vt.boxMax[1], vt.boxMax[2]);

    // A2.1 自动取景：外壳≫体积盒时以体积盒为主（避免视距过大），否则并集取景。
    // ⚠️ 相机必须用 offset 后的【场景坐标】：物体已被 translateToCenter 平移到中心
    // （offset = -unionBox.center），若用未 offset 的 world 盒 → 相机盯着原中心、
    // 物体偏出视锥（用户实测 v1.7.2「摄像机位置不对，渲染出来的位置也不对」根因）。
    const framingWorld = computeFramingBox(shellBox, volumeWorldBox);
    const cp = computeVolumeCamera(applyOffsetToBox(framingWorld, offset));
    camera.near = cp.near;
    camera.far = cp.far;
    camera.position.set(cp.position[0], cp.position[1], cp.position[2]);
    controls.target.set(cp.target[0], cp.target[1], cp.target[2]);
    controls.minDistance = cp.minDistance;
    controls.maxDistance = cp.maxDistance;
    camera.updateProjectionMatrix();
    controls.update();
  }

  /* ── 按需渲染门（renderGate 复用）── */
  const renderLoop = createRenderLoop({
    onRender: () => {
      volumeMat.uniforms.uCameraPos.value.copy(camera.position);
      controls.update();
      renderer.render(scene, camera);
    },
  });
  const markDirty = renderLoop.markDirty;
  controls.addEventListener("change", () => markDirty());

  function resizeRenderer() {
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

  alignAndFrame();
  applyColorize(opts.frame);
  markDirty();

  /* ── 时间轴动画（play/pause/seek）── */
  let playing = false;
  let timeIdx = 0;
  let timer: ReturnType<typeof setInterval> | null = null;
  function clearTimer() {
    if (timer != null) { clearInterval(timer); timer = null; }
  }

  const handle: VolumeRendererHandle = {
    setOpacity(v: number) {
      volumeMat.uniforms.uOpacity.value = v;
      markDirty();
    },
    setShellVisible(v: boolean) {
      shellMeshes.forEach((m) => { m.visible = v; });
      markDirty();
    },
    setFrame(frame: VolumeFrame) {
      applyColorize(frame);
      markDirty();
    },
    setColorizeRange(range: ScalarRange, min: number) {
      colorRange = { min: range.min, max: range.max };
      displayMin = min;
      applyColorize(opts.frame);
      markDirty();
    },
    setTransparentMode(mode: TransparentMode) {
      // 档位 → 连续透明度（向后兼容）；「栅元透明度」滑杆走 setShellOpacity
      shellOpacity = mode === "opaque" ? 1 : mode === "see-through" ? 0.6 : DEFAULT_SHELL_OPACITY;
      for (const m of shellMeshes) applyShellMaterial(m, m.userData.color);
      markDirty();
    },
    setShellOpacity(v: number) {
      shellOpacity = clamp01(v);
      for (const m of shellMeshes) applyShellMaterial(m, m.userData.color);
      markDirty();
    },
    setCellVisible(index: number, vis: boolean) {
      for (const m of shellMeshes) {
        if (m.userData.index === index) { m.visible = vis; markDirty(); return; }
      }
    },
    selectAll(vis: boolean) {
      shellMeshes.forEach((m) => { m.visible = vis; });
      markDirty();
    },
    play() {
      const n = opts.timeOptions?.length ?? 0;
      if (playing || n <= 1) return;
      playing = true;
      clearTimer();
      timer = setInterval(() => {
        timeIdx = (timeIdx + 1) % n;
        opts.onTimeSeek?.(timeIdx);
      }, opts.timeIntervalMs ?? 500);
    },
    pause() {
      playing = false;
      clearTimer();
    },
    seek(idx: number) {
      const n = opts.timeOptions?.length ?? 1;
      timeIdx = Math.max(0, Math.min(n - 1, idx));
      opts.onTimeSeek?.(timeIdx);
    },
    markDirty,
    dispose() {
      clearTimer();
      ro?.disconnect();
      controls.dispose();
      renderLoop.dispose();
      renderer.dispose();
      shellMeshes.forEach((m) => {
        m.geometry.dispose();
        (m.material as THREE.Material).dispose();
      });
      volumeBox.geometry.dispose();
      volumeMat.dispose();
      dataTexture.dispose();
      scene.clear();
    },
  };
  return handle;
}
