/**
 * LatticePreview3D — 格阵子预览线框（纯前端，跟手重建）。
 *
 * 复用 useThreeCanvas（WebGL 挂载）+ computeCameraParams（取景）+ buildHexPrism / 盒线框。
 * 矩形=每格盒线框；六棱柱=每格 pointy-top 六棱柱（外接半径 R=pitch/√3）。
 * 输入变即重建（dispose 旧 group），配合按需渲染不卡。
 */
import React, { useEffect, useRef } from "react";
import * as THREE from "three";
import { useThreeCanvas } from "../three/useThreeCanvas";
import { buildHexPrism } from "../three/hexPrism";
import { disposeObjectGroup } from "../three/disposeObject";
import { computeCameraParams } from "../three/cameraParams";
import { getUniverseColor, hexCenter } from "../utils/lattice";
import type { FillGridCellJson } from "../utils/lattice";

interface Props {
  lat: string;
  dims: number[];
  cells: FillGridCellJson[];
  palette: Record<string, string>;
  pitch?: number;
  height?: number;
}

const VOID_COLOR = 0x3a3a5a;

function colorOf(u: string, palette: Record<string, string>): number {
  if (!u || u === "0") return VOID_COLOR;
  const hex = getUniverseColor(u, palette).replace("#", "");
  const n = parseInt(hex, 16);
  return Number.isFinite(n) ? n : VOID_COLOR;
}

function buildBoxWireframe(w: number, d: number, h: number, color: number) {
  const geo = new THREE.BoxGeometry(w, d, h);
  const edges = new THREE.EdgesGeometry(geo);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.85 });
  const line = new THREE.LineSegments(edges, mat);
  const group = new THREE.Group();
  group.add(line);
  return {
    group,
    dispose() {
      geo.dispose();
      edges.dispose();
      mat.dispose();
      group.clear();
    },
  };
}

export default function LatticePreview3D({ lat, dims, cells, palette, pitch = 1, height = 1 }: Props) {
  const { canvasRef, wrapRef, sceneRef, cameraRef, controlsRef, markDirty } = useThreeCanvas();
  const groupRef = useRef<THREE.Group | null>(null);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (groupRef.current) {
      scene.remove(groupRef.current);
      disposeObjectGroup(groupRef.current);
      groupRef.current = null;
    }

    const cols = Math.max(1, dims[0] ?? 1);
    const rows = Math.max(1, dims[1] ?? 1);
    const layers = Math.max(1, dims[2] ?? 1);
    const group = new THREE.Group();

    if (lat === "2") {
      const R = pitch / Math.sqrt(3);
      cells.forEach((c, idx) => {
        const i = idx % cols;
        const j = Math.floor(idx / cols) % rows;
        const k = Math.floor(idx / (cols * rows));
        const center = hexCenter(i, j, pitch);
        const wire = buildHexPrism(R, height, colorOf(c.u, palette));
        wire.group.position.set(center.x, center.y, (k - (layers - 1) / 2) * height);
        group.add(wire.group);
      });
    } else {
      cells.forEach((c, idx) => {
        const i = idx % cols;
        const j = Math.floor(idx / cols) % rows;
        const k = Math.floor(idx / (cols * rows));
        const wire = buildBoxWireframe(pitch, pitch, height, colorOf(c.u, palette));
        wire.group.position.set(
          (i - (cols - 1) / 2) * pitch,
          (j - (rows - 1) / 2) * pitch,
          (k - (layers - 1) / 2) * height,
        );
        group.add(wire.group);
      });
    }

    scene.add(group);
    groupRef.current = group;

    if (group.children.length > 0) {
      const box = new THREE.Box3().setFromObject(group);
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
    markDirty();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, JSON.stringify(dims), JSON.stringify(cells), JSON.stringify(palette), pitch, height]);

  return (
    <div ref={wrapRef} style={{ flex: 1, minWidth: 220, position: "relative", border: "1px solid var(--border-glass)", borderRadius: 8, overflow: "hidden" }}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
      <div style={{ position: "absolute", left: 8, bottom: 8, fontSize: 10, color: "rgba(241,241,249,0.55)", pointerEvents: "none" }}>
        滚轮缩放 · 拖拽旋转
      </div>
    </div>
  );
}
