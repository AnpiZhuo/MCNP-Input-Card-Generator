/**
 * useThreeCanvas — 把 QuickCellDialog 的「canvasRef + WebGLRenderer + OrbitControls」
 * 挂载范式提取为共享 hook（按需渲染 + ResizeObserver + 清理）。
 *
 * 用方：
 *   const { canvasRef, wrapRef, sceneRef, cameraRef, controlsRef, markDirty } = useThreeCanvas();
 *   <div ref={wrapRef}><canvas ref={canvasRef}/></div>
 *   场景对象增删后调 markDirty() 触发一次渲染。
 */
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export function useThreeCanvas(background = 0x0d0d22) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const dirtyRef = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    const w = Math.max(rect.width, 120);
    const h = Math.max(rect.height, 120);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(background);
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 1e5);
    camera.up.set(0, 0, 1); // Z 朝上（数学/物理/MCNP 惯例）
    /**
     * ⚠️ `alpha: true` 是**出图透明底**的前提（2026-09-19）。
     * 出图时要把这一帧清成 `alpha = 0`（见 `captureFrame.captureTransparent3D`），
     * 而 drawing buffer 没有 alpha 通道时，`setClearColor(_, 0)` 只会得到黑底 ——
     * 透明 PNG 就会变成"黑底 PNG"。开 alpha 对屏幕观感无影响：
     * 场景 `background` 是实色，正常渲染时不透明。
     */
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
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
  }, [background]);

  const markDirty = () => { dirtyRef.current = true; };

  return { canvasRef, wrapRef, sceneRef, cameraRef, controlsRef, markDirty };
}
