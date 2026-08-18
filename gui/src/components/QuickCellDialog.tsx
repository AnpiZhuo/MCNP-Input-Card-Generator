/**
 * QuickCellDialog — 「快捷建栅元」弹窗
 *
 * 左侧：QuickCellForm（形状/参数/材料/imp，与 3D 预览侧栏共用）；
 * 右侧：实时线框预览画布（颜色随所选材料，M0 白线）。
 *
 * 生成结果由父组件（GeometryTab）追加到曲面卡/TR 卡/栅元列表；
 * 编号规则与生成逻辑在 gui/src/utils/quickCell.ts（纯函数）。
 */
import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import FloatingDialog from "./FloatingDialog";
import QuickCellForm from "./QuickCellForm";
import { computeCameraParams } from "../three/cameraParams";
import { buildQuickCellPreview, wireColorForMaterial } from "../three/quickCellPreview";
import type { QuickCellResult, QuickShape } from "../utils/quickCell";

interface Props {
  surfacesText: string;
  trCardsText: string;
  cellNumbers: number[];
  materials: { number: number; comment?: string; density?: string }[];
  onClose: () => void;
  onGenerate: (result: QuickCellResult) => void;
}

interface PreviewState {
  shape: QuickShape;
  config: any;
  valid: boolean;
  material: string;
}

export default function QuickCellDialog({ surfacesText, trCardsText, cellNumbers, materials, onClose, onGenerate }: Props) {
  /* ── 预览画布：场景/相机/渲染（按需渲染） ── */
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
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
    camera.up.set(0, 0, 1); // Z 朝上（数学/物理/MCNP 惯例）
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
    };
  }, []);

  /* ── 表单配置 → 防抖重建画布线框（颜色随材料，M0 白线） ── */
  const [preview, setPreview] = useState<PreviewState | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => {
      const scene = sceneRef.current;
      if (!scene) return;
      // 只在线框首次出现时取景一次；后续参数变化保持用户当前视角（不再强制矫正摄像头）
      const wasVisible = !!previewRef.current;
      if (previewRef.current) {
        scene.remove(previewRef.current.group);
        previewRef.current.dispose();
        previewRef.current = null;
      }
      if (preview && preview.valid) {
        const prev = buildQuickCellPreview(preview.shape, preview.config, wireColorForMaterial(preview.material));
        scene.add(prev.group);
        previewRef.current = prev;
        if (!wasVisible) {
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
      }
      dirtyRef.current = true;
    }, 100);
    return () => clearTimeout(timer);
  }, [preview]);

  const onConfigChange = (shape: QuickShape, config: any, valid: boolean, material: string) => {
    setPreview({ shape, config, valid, material });
  };

  return React.createElement(FloatingDialog, {
    title: "⚡ 快捷建栅元（一次一种形状）",
    onClose,
    width: 940,
  },
    React.createElement("div", { style: { display: "flex", gap: 14, minHeight: 480 } },
      React.createElement("div", { style: { width: 360, flexShrink: 0, overflowY: "auto", paddingRight: 4 } },
        React.createElement(QuickCellForm, {
          surfacesText, trCardsText, cellNumbers, materials,
          onGenerate, onCancel: onClose, onConfigChange,
        }),
      ),
      React.createElement("div", {
        ref: wrapRef,
        style: { flex: 1, minWidth: 260, position: "relative", border: "1px solid var(--border-glass)", borderRadius: 8, overflow: "hidden" },
      },
        React.createElement("canvas", { ref: canvasRef, style: { width: "100%", height: "100%", display: "block" } }),
        React.createElement("div", { style: { position: "absolute", left: 8, bottom: 8, fontSize: 10, color: "rgba(241,241,249,0.55)", pointerEvents: "none" } },
          "滚轮缩放 · 拖拽旋转（红 X / 绿 Y / 蓝 Z；线框色随材料）"),
      ),
    ),
  );
}
