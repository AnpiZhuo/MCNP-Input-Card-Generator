/**
 * Preview3DLattice — 格阵 3D 预览（universe 实例化方案，阶段3）。
 *
 * 后端 /api/preview-lattice 完成 compose_lattice_tree 嵌套递归，返回 FLAT
 * leafInstances（绝对坐标）+ 每格阵 universes STL（base64）+ count/detailViable；
 * 前端 InstancedMesh 直食，无需再做位置组合（TS 镜像 composeNestedPositions 只
 * 用于跨语言 golden 测试锁死，运行时以后端权威为准）。
 *
 * - 详细模式：每 (u, cellNum) 一个 InstancedMesh（色=getMatColor，M0 透明）。
 * - 色块总览：单 InstancedMesh 色块（rect box / hex prism，色=getUniverseColor）。
 * - 超大规模（> DETAIL_MAX_INSTANCES 或后端 detailViable=false）自动切总览 + 提示。
 *
 * 复用 useThreeCanvas（WebGL 挂载 + dirty 渲染循环）+ computeCameraParams（取景）
 * + STLLoader（base64 解码）。
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { useThreeCanvas } from "../three/useThreeCanvas";
import { computeCameraParams } from "../three/cameraParams";
import {
  buildLatticeInstances,
  DETAIL_MAX_INSTANCES,
  instanceIndexAt,
  nonVoidFrameLeaves,
  parseTrclDeg,
} from "../three/latticeInstances";
import type { LatticeInstance, LatticeInstancesHandle } from "../three/latticeInstances";
import { buildUniversePalette } from "../utils/lattice";
import { apiUrl } from "../utils/api";

/* ── 类型（镜像后端契约） ── */

export interface LatticeCellLike {
  num: string;
  mat: string;
  density?: string;
  surfaces?: string;
  comment?: string;
  render?: boolean;
  u?: string;
  fill?: string;
  lat?: string;
  trcl?: string;
  fill_grid?: string;
}

interface Preview3DLatticeProps {
  cells: LatticeCellLike[];
  surfaces?: string;
  trCards?: string;
  onClose?: () => void;
}

/** 每格阵一条（含嵌套；universes 只含该格阵直接引用的叶 universe 裁剪 STL） */
interface LatticeItem {
  num: string | number;
  lat: string;
  kind: string;
  dims: number[];
  range: string[];
  center: [number, number, number];
  pitch: [number, number, number];
  height: number;
  trclRotationDeg: number;
  positions: { idx: number; u: string; x: number; y: number; z: number; dx: number; dy: number; dz: number }[];
  universes: Record<string, Record<string, string>>; // u → cellNum → base64 STL
}

interface PreviewLatticeResponse {
  status?: string;
  lattices?: LatticeItem[];
  leafInstances?: LatticeInstance[];
  tree?: unknown[];
  count?: number;
  detailViable?: boolean;
  message?: string;
}

interface LatticeExtentResponse {
  status?: string;
  ok?: boolean;
  extent?: {
    x_min: number; x_max: number; y_min: number; y_max: number;
    z_min: number | null; z_max: number | null;
  } | null;
  msg?: string;
}

interface LatticeData {
  leaves: LatticeInstance[];
  /** 色块总览位置 = 根（最外层）格阵 positions（完整；leaves 超限截断时仍完整） */
  overviewPositions: LatticeInstance[];
  universeStl: Record<string, Record<string, THREE.BufferGeometry>>;
  cellMaterials: Record<string, Record<string, string>>;
  palette: Record<string, string>;
  trclDeg: number;
  blockSize: { x: number; y: number; z: number; hex: boolean };
  count: number;
  detailViable: boolean;
}

/* ── 纯辅助 ── */

async function postJson<T = any>(path: string, body: unknown): Promise<T> {
  const r = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  return (await r.json()) as T;
}

function latticePayload(cells: LatticeCellLike[], surfaces: string, trCards: string): Record<string, unknown> {
  return {
    surfaces: surfaces || "",
    tr_cards: trCards || "",
    cells: cells.map((c) => ({
      number: parseInt(c.num) || 0,
      material: c.mat || "",
      density: c.density || "",
      surface_expr: c.surfaces || "",
      u: c.u || "",
      fill: c.fill || "",
      lat: c.lat || "",
      trcl: c.trcl || "",
      render: c.render !== false,
      fill_grid: c.fill_grid || "",
    })),
  };
}

function decodeStl(base64: string): THREE.BufferGeometry {
  const bin = atob(base64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const geo = new STLLoader().parse(bytes.buffer);
  geo.computeBoundingBox();
  return geo;
}

/** 格元盒（pitch×pitch×高度），总览色块尺寸：hex 用 x 为对边宽 */
function blockSizeFrom(lattice: LatticeItem | undefined, lat: string): { x: number; y: number; z: number; hex: boolean } {
  const isHex = (lattice?.lat ?? lat) === "2";
  const px = lattice?.pitch?.[0] || 1;
  const py = isHex ? px : (lattice?.pitch?.[1] || px);
  return { x: px, y: py, z: lattice?.height || 1, hex: isHex };
}

/** 有效总览判定：用户强制总览，或后端 detailViable=false，或叶数超 DETAIL_MAX_INSTANCES */
function isOverview(overviewUser: boolean, detailViable: boolean | undefined, count: number): boolean {
  return overviewUser || detailViable === false || count > DETAIL_MAX_INSTANCES;
}

/* ── 组件 ── */

export default function Preview3DLattice({ cells, surfaces, trCards, onClose }: Preview3DLatticeProps) {
  const { canvasRef, wrapRef, sceneRef, cameraRef, controlsRef, markDirty } = useThreeCanvas(0x000000);

  const propsRef = useRef({ cells, surfaces, trCards });
  propsRef.current = { cells, surfaces, trCards };
  const dataRef = useRef<LatticeData | null>(null);
  const handleRef = useRef<LatticeInstancesHandle | null>(null);
  const positionsRef = useRef<LatticeInstance[] | null>(null);

  const [dataVersion, setDataVersion] = useState(0);
  const [overviewUser, setOverviewUser] = useState(false); // 用户「色块总览」toggle
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [count, setCount] = useState(0);
  const [selected, setSelected] = useState<LatticeInstance | null>(null);

  /* 灯光（useThreeCanvas 不建灯；InstancedMesh 走 MeshStandardMaterial 需光照） */
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || scene.userData.latticeLights) return;
    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const dir = new THREE.DirectionalLight(0xffffff, 1.4);
    dir.position.set(80, 60, 100);
    scene.add(dir);
    const dir2 = new THREE.DirectionalLight(0x4488ff, 0.4);
    dir2.position.set(-60, 30, -80);
    scene.add(dir2);
    scene.userData.latticeLights = true;
  }, [sceneRef]);

  /* 加载：lattice-extent（格元盒诊断）+ preview-lattice（主，含 STL/leafInstances） */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { cells: cs, surfaces: s, trCards: t } = propsRef.current;
      const latCell = cs.find((c) => c.fill_grid && c.fill_grid.trim() !== "");
      if (!latCell) {
        if (!cancelled) { setError("未找到含 fill_grid 的格阵栅元"); setLoading(false); }
        return;
      }
      setLoading(true);
      setError("");
      const payload = latticePayload(cs, s || "", t || "");
      let j: PreviewLatticeResponse | null = null;
      try {
        const [extJ, stlJ] = await Promise.all([
          postJson<LatticeExtentResponse>("/api/lattice-extent", {
            surface_expr: latCell.surfaces || "",
            lat: latCell.lat || "",
            surfaces_text: s || "",
          }),
          postJson<PreviewLatticeResponse>("/api/preview-lattice", payload),
        ]);
        if (cancelled) return;
        j = stlJ;
        if (stlJ.status === "error" || !stlJ.leafInstances) {
          setError(stlJ.message || (extJ?.ok === false ? (extJ.msg || "格元盒解析失败") : "格阵预览失败"));
          setLoading(false);
          return;
        }
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || "格阵预览请求失败");
        setLoading(false);
        return;
      }
      const leaves = j.leafInstances!;
      const lattices = j.lattices ?? [];
      const primary = lattices[0];
      const n = j.count ?? leaves.length;

      // STL 解码（lattice-extent 端不返回 STL，只有 preview-lattice）
      const universeStl: Record<string, Record<string, THREE.BufferGeometry>> = {};
      for (const lt of lattices) {
        for (const u of Object.keys(lt.universes || {})) {
          const target = (universeStl[u] ??= {});
          for (const cellNum of Object.keys(lt.universes[u])) {
            try {
              target[cellNum] = decodeStl(lt.universes[u][cellNum]);
            } catch (err) {
              console.warn("STL 解码失败", u, cellNum, err);
            }
          }
        }
      }

      // 材料：按 cellNum 在 deck.cells 查询（与 preview-3d 一致）；缺失回退 leaf.mat
      const matByNum: Record<string, string> = {};
      for (const c of cs) matByNum[String(c.num)] = c.mat;
      const cellMaterials: Record<string, Record<string, string>> = {};
      for (const p of leaves) {
        const m = matByNum[p.cellNum];
        if (m != null) (cellMaterials[p.u] ??= {})[p.cellNum] = m;
      }

      const trclDeg = primary ? (primary.trclRotationDeg ?? 0) : parseTrclDeg(latCell.trcl, latCell.lat);
      const blockSize = blockSizeFrom(primary, latCell.lat || "");
      const detailViable = j.detailViable !== false;
      const auto = isOverview(false, detailViable, n);
      // 色块总览用根格阵 positions（完整）；叶子超上限时后端已裁空
      const overviewPositions = (primary?.positions ?? []).map((p) => ({
        path: String(p.idx), u: p.u, cellNum: "", mat: "",
        x: p.x + (p.dx ?? 0), y: p.y + (p.dy ?? 0), z: p.z + (p.dz ?? 0), depth: 1,
      }));
      // 调色板：总览模式用根格阵 positions 的宇宙（leaves 已裁空）；否则用叶宇宙
      const palette = buildUniversePalette((auto ? overviewPositions : leaves).map((p) => p.u));

      dataRef.current = { leaves, overviewPositions, universeStl, cellMaterials, palette, trclDeg, blockSize, count: n, detailViable };
      if (!cancelled) {
        setCount(n);
        setHint(auto ? `格位过多（${n.toLocaleString()}），已自动切换色块总览` : "");
        setDataVersion((v) => v + 1);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* 取景：按 leafInstances 包围盒（项15：void 叶 mat="0" 不计入，防巨型边界 void 撑大取景拉远相机） */
  const frameCamera = useCallback((leaves: LatticeInstance[]) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    const frameLeaves = nonVoidFrameLeaves(leaves);
    let min = [Infinity, Infinity, Infinity];
    let max = [-Infinity, -Infinity, -Infinity];
    for (const p of frameLeaves) {
      if (p.x < min[0]) min[0] = p.x;
      if (p.y < min[1]) min[1] = p.y;
      if (p.z < min[2]) min[2] = p.z;
      if (p.x > max[0]) max[0] = p.x;
      if (p.y > max[1]) max[1] = p.y;
      if (p.z > max[2]) max[2] = p.z;
    }
    if (!Number.isFinite(min[0])) { min = [-1, -1, -1]; max = [1, 1, 1]; }
    const center: [number, number, number] = [
      (min[0] + max[0]) / 2,
      (min[1] + max[1]) / 2,
      (min[2] + max[2]) / 2,
    ];
    const size: [number, number, number] = [
      Math.max(max[0] - min[0], 1e-3),
      Math.max(max[1] - min[1], 1e-3),
      Math.max(max[2] - min[2], 1e-3),
    ];
    const cp = computeCameraParams(center, size);
    camera.position.set(cp.position[0], cp.position[1], cp.position[2]);
    camera.near = cp.near;
    camera.far = cp.far;
    camera.updateProjectionMatrix();
    controls.target.set(cp.target[0], cp.target[1], cp.target[2]);
    controls.minDistance = cp.minDistance;
    controls.maxDistance = cp.maxDistance;
    controls.update();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraRef, controlsRef]);

  /* 构建实例（数据或总览 toggle 变化时重建；不重拉 STL） */
  useEffect(() => {
    const data = dataRef.current;
    const scene = sceneRef.current;
    if (!data || !scene) return;
    if (handleRef.current) {
      scene.remove(handleRef.current.group);
      handleRef.current.dispose();
      handleRef.current = null;
    }
    const effOverview = isOverview(overviewUser, data.detailViable, data.count);
    // 总览：用根格阵 positions（完整），不用截断的 leaves
    const positions = effOverview ? data.overviewPositions : data.leaves;
    const handle = buildLatticeInstances({
      positions,
      universeStl: data.universeStl,
      cellMaterials: data.cellMaterials,
      palette: data.palette,
      materialMode: true,
      trclRotationDeg: data.trclDeg,
      overviewMode: effOverview,
      blockSize: data.blockSize,
    });
    scene.add(handle.group);
    handleRef.current = handle;
    positionsRef.current = positions;
    frameCamera(positions);
    markDirty();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataVersion, overviewUser]);

  /* 卸载清理 */
  useEffect(() => {
    return () => {
      if (handleRef.current) {
        sceneRef.current?.remove(handleRef.current.group);
        handleRef.current.dispose();
        handleRef.current = null;
      }
    };
  }, [sceneRef]);

  /* 点击实例 → 格位信息 */
  const onPointerDown = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    const camera = cameraRef.current;
    const handle = handleRef.current;
    if (!canvas || !camera || !handle) return;
    const rect = canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / Math.max(rect.width, 1)) * 2 - 1,
      -((e.clientY - rect.top) / Math.max(rect.height, 1)) * 2 + 1,
    );
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, camera);
    const idx = instanceIndexAt(ray, handle.group.userData.instancedMeshes as THREE.InstancedMesh[]);
    if (idx != null && positionsRef.current) setSelected(positionsRef.current[idx]);
    else setSelected(null);
  }, [canvasRef, cameraRef]);

  const effectiveOverview = isOverview(overviewUser, dataRef.current?.detailViable, count);

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, display: "flex", flexDirection: "column", background: "#000", fontFamily: "system-ui, -apple-system, sans-serif" } as React.CSSProperties}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 20px", borderBottom: "1px solid rgba(255,255,255,0.1)", background: "rgba(15,15,40,0.92)",
      } as React.CSSProperties}>
        <span style={{ fontSize: 14, fontWeight: 600, color: "rgba(241,241,249,0.9)" } as React.CSSProperties}>
          🎨 3D 预览 — 格阵装配（universe 实例化）{effectiveOverview ? "（色块总览）" : ""}
        </span>
        <div style={{ display: "flex", gap: 10, alignItems: "center" } as React.CSSProperties}>
          {hint ? <span style={{ fontSize: 11, color: "#e6a23c" } as React.CSSProperties}>{hint}</span> : null}
          <span style={{ fontSize: 11, color: "rgba(241,241,249,0.45)" } as React.CSSProperties}>
            {count > 0 ? `${count.toLocaleString()} 格位` : ""}
          </span>
          <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 11, color: "rgba(241,241,249,0.75)", cursor: "pointer" } as React.CSSProperties}>
            <input
              type="checkbox"
              checked={overviewUser}
              onChange={(e) => setOverviewUser(e.target.checked)}
              style={{ accentColor: "#ff4d6d" } as React.CSSProperties}
            />
            色块总览
          </label>
          <button className="btn btn-ghost btn-xs" onClick={onClose} style={{ fontSize: 16, padding: "4px 10px" } as React.CSSProperties}>
            ✕
          </button>
        </div>
      </div>
      <div ref={wrapRef} style={{ flex: 1, position: "relative", minHeight: 0 } as React.CSSProperties}>
        <canvas
          ref={canvasRef}
          onPointerDown={onPointerDown}
          style={{ width: "100%", height: "100%", display: "block", touchAction: "none" } as React.CSSProperties}
        />
        {loading ? (
          <div style={{
            position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
            background: "rgba(0,0,0,0.7)", color: "rgba(241,241,249,0.9)", fontSize: 14, letterSpacing: 1,
          } as React.CSSProperties}>
            正在加载格阵几何…
          </div>
        ) : null}
        {error ? (
          <div style={{
            position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
            background: "rgba(0,0,0,0.75)", color: "#e53935", fontSize: 13, padding: 24, textAlign: "center",
          } as React.CSSProperties}>
            {error}
          </div>
        ) : null}
        <div style={{ position: "absolute", left: 10, top: 8, fontSize: 10, color: "rgba(241,241,249,0.45)", pointerEvents: "none" } as React.CSSProperties}>
          🖱 拖拽旋转 · 滚轮缩放 · 右键平移 · 点击实例查看格位
        </div>
        {selected ? (
          <div style={{
            position: "absolute", left: 10, bottom: 10, fontSize: 11,
            color: "rgba(241,241,249,0.9)", background: "rgba(15,15,40,0.92)",
            padding: "6px 10px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.14)",
          } as React.CSSProperties}>
            U={selected.u} · 栅元 {selected.cellNum} · 材料 {selected.mat} · 路径 {selected.path}
          </div>
        ) : null}
      </div>
    </div>
  );
}
