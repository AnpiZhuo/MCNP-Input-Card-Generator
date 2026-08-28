/**
 * LatticePreview3D — 格阵子预览线框（纯前端，跟手重建）。
 *
 * 复用 useThreeCanvas（WebGL 挂载）+ computeCameraParams（取景）+ buildHexPrism / 盒线框。
 * 矩形=每格盒线框；六棱柱=每格 pointy-top 六棱柱（外接半径 R=pitch/√3）。
 * 输入变即重建（dispose 旧 group），配合按需渲染不卡。
 *
 * 项6：几何随定义变化——矩形用 pitchX×pitchY×height 盒、六棱柱用 pitch（对边距）+
 * height 棱柱（调用方从曲面/宏体参数传真实尺寸，而非固定 pitch=1）；并补 XYZ 坐标轴显示
 * （AXIS_CONFIG：X 红 / Y 绿 / Z 蓝，数学/物理三维表达系）。
 */
import React, { useEffect, useRef } from "react";
import * as THREE from "three";
import { useThreeCanvas } from "../three/useThreeCanvas";
import { buildHexPrism } from "../three/hexPrism";
import { disposeObjectGroup } from "../three/disposeObject";
import { computeCameraParams } from "../three/cameraParams";
import { AXIS_CONFIG } from "../three/axisConfig";
import { getUniverseColor, hexCenter } from "../utils/lattice";
import type { FillGridCellJson } from "../utils/lattice";

interface Props {
  lat: string;
  dims: number[];
  cells: FillGridCellJson[];
  palette: Record<string, string>;
  /** 格距（中心距）。rect 用 pitchX（x 向）/pitchY（y 向）；hex 用 pitch（对边距） */
  pitch?: number;
  /** rect：y 向格距（缺省 = pitch） */
  pitchY?: number;
  /** 单格高度（z 向） */
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

/** 数学/物理 XYZ 坐标轴（AXIS_CONFIG 单一事实来源；X 红 / Y 绿 / Z 蓝）——项6 */
function buildAxes(): { group: THREE.Group; dispose(): void } {
  const group = new THREE.Group();
  const disposers: (() => void)[] = [];
  const EXT = 100; // 轴长（随取景在 rebuild 中按范围伸缩，这里用大值覆盖视域）
  for (const a of AXIS_CONFIG) {
    const dir = new THREE.Vector3(...a.dir);
    const pts = [dir.clone().multiplyScalar(-EXT), dir.clone().multiplyScalar(EXT)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: a.color, transparent: true, opacity: 0.9 });
    group.add(new THREE.Line(geo, mat));
    disposers.push(() => { geo.dispose(); mat.dispose(); });
    // 正端字母标签（sprite）
    const c = document.createElement("canvas");
    c.width = 64; c.height = 64;
    const ctx = c.getContext("2d")!;
    ctx.fillStyle = "#" + a.color.toString(16).padStart(6, "0");
    ctx.font = "Bold 40px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(a.label, 32, 34);
    const tex = new THREE.CanvasTexture(c);
    const lbl = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
    lbl.position.copy(dir.clone().multiplyScalar(EXT + 8));
    lbl.scale.set(4, 4, 1);
    group.add(lbl);
    disposers.push(() => { tex.dispose(); (lbl.material as THREE.Material).dispose(); });
  }
  return {
    group,
    dispose() { for (const d of disposers) d(); group.clear(); },
  };
}

export default function LatticePreview3D({ lat, dims, cells, palette, pitch = 1, pitchY, height = 1 }: Props) {
  const { canvasRef, wrapRef, sceneRef, cameraRef, controlsRef, markDirty } = useThreeCanvas();
  const groupRef = useRef<THREE.Group | null>(null);
  const axesRef = useRef<{ group: THREE.Group; dispose(): void } | null>(null);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (groupRef.current) {
      scene.remove(groupRef.current);
      disposeObjectGroup(groupRef.current);
      groupRef.current = null;
    }
    if (axesRef.current) {
      scene.remove(axesRef.current.group);
      axesRef.current.dispose();
      axesRef.current = null;
    }
    // XYZ 坐标轴（项6）
    const axes = buildAxes();
    scene.add(axes.group);
    axesRef.current = axes;

    const cols = Math.max(1, dims[0] ?? 1);
    const rows = Math.max(1, dims[1] ?? 1);
    const layers = Math.max(1, dims[2] ?? 1);
    const py = pitchY ?? pitch;
    const group = new THREE.Group();

    if (lat === "2") {
      const R = pitch / 2; // buildHexPrism 参数=半对边距（外接半径 = pitch/√3，相邻格面相切）
      cells.forEach((c, idx) => {
        const i = idx % cols;
        const j = Math.floor(idx / cols) % rows;
        const k = Math.floor(idx / (cols * rows));
        // 居中：与后端 expand_positions hex 分支一致，格阵几何中心落在原点
        const center = hexCenter(i - (cols - 1) / 2, j - (rows - 1) / 2, pitch);
        const wire = buildHexPrism(R, height, colorOf(c.u, palette));
        wire.group.position.set(center.x, center.y, (k - (layers - 1) / 2) * height);
        group.add(wire.group);
      });
    } else {
      cells.forEach((c, idx) => {
        const i = idx % cols;
        const j = Math.floor(idx / cols) % rows;
        const k = Math.floor(idx / (cols * rows));
        const wire = buildBoxWireframe(pitch, py, height, colorOf(c.u, palette));
        wire.group.position.set(
          (i - (cols - 1) / 2) * pitch,
          (j - (rows - 1) / 2) * py,
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
  }, [lat, JSON.stringify(dims), JSON.stringify(cells), JSON.stringify(palette), pitch, pitchY, height]);

  return (
    <div ref={wrapRef} style={{ flex: 1, minWidth: 220, position: "relative", border: "1px solid var(--border-glass)", borderRadius: 8, overflow: "hidden" }}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
      <div style={{ position: "absolute", left: 8, bottom: 8, fontSize: 10, color: "rgba(241,241,249,0.55)", pointerEvents: "none" }}>
        XYZ 轴 · 滚轮缩放 · 拖拽旋转
      </div>
    </div>
  );
}
