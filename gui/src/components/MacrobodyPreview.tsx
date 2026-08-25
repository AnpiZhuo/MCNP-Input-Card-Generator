/**
 * MacrobodyPreview — 宏体子预览（项 3/4）。
 *
 * 自动生成宏体（RPP/RHP）后实时显示几何线框：POST /api/lattice-extent 拿格元盒，
 * RPP → 盒线框；RHP → 顶点+X flat-top 六棱柱线框（由盒的 vertex-vertex 宽 / flat-flat
 * 高重建）。复用 useThreeCanvas（WebGL 挂载 + 按需渲染）+ computeCameraParams（取景）。
 * 输入变即重建（dispose 旧 group）。
 */
import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { useThreeCanvas } from "../three/useThreeCanvas";
import { computeCameraParams } from "../three/cameraParams";
import { disposeObjectGroup } from "../three/disposeObject";
import { buildHexPrism } from "../three/hexPrism";
import { apiUrl } from "../utils/api";

interface Props {
  lat: string;              // "1" | "2"
  surfaceExpr: string;      // 宏体表达式（"-6"）
  surfacesText: string;     // 含宏体卡的曲面卡文本
}

interface Extent {
  x_min: number; x_max: number; y_min: number; y_max: number;
  z_min: number | null; z_max: number | null;
}

const LINE_COLOR = 0x66ccff;

/** RPP 盒线框 */
function buildBoxWireframe(x0: number, x1: number, y0: number, y1: number, z0: number, z1: number, color: number): THREE.Group {
  const group = new THREE.Group();
  const geo = new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0);
  const edges = new THREE.EdgesGeometry(geo);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 });
  group.add(new THREE.LineSegments(edges, mat));
  group.position.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
  return group;
}

export default function MacrobodyPreview({ lat, surfaceExpr, surfacesText }: Props) {
  const { canvasRef, wrapRef, sceneRef, cameraRef, controlsRef, markDirty } = useThreeCanvas();
  const groupRef = useRef<THREE.Group | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!surfaceExpr.trim()) {
      setErr("");
      return;
    }
    (async () => {
      setErr("");
      try {
        const r = await fetch(apiUrl("/api/lattice-extent"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ surface_expr: surfaceExpr, lat, surfaces_text: surfacesText }),
        });
        const j = await r.json();
        if (cancelled) return;
        if (j.status === "error" || !j.extent) {
          setErr((j as any).msg || "格元盒解析失败");
          return;
        }
        const scene = sceneRef.current;
        if (!scene) return;
        if (groupRef.current) {
          scene.remove(groupRef.current);
          disposeObjectGroup(groupRef.current);
          groupRef.current = null;
        }
        const e = j.extent as Extent;
        const z0 = e.z_min ?? -0.5;
        const z1 = e.z_max ?? 0.5;
        // RHP：外接半径 = 顶点-顶点宽 /2（buildHexPrism 顶点朝 +X，与 autoGenMacrobody 一致）
        const group = lat === "2"
          ? buildHexPrism((e.x_max - e.x_min) / 2, z1 - z0, LINE_COLOR).group
          : buildBoxWireframe(e.x_min, e.x_max, e.y_min, e.y_max, z0, z1, LINE_COLOR);
        scene.add(group);
        groupRef.current = group;
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
        markDirty();
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || "格元盒请求失败");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, surfaceExpr, surfacesText, sceneRef, cameraRef, controlsRef]);

  return (
    <div ref={wrapRef} style={{ flex: 1, minWidth: 200, height: 200, position: "relative", border: "1px solid var(--border-glass)", borderRadius: 8, overflow: "hidden" }}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
      {err ? (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "#e53935", background: "rgba(0,0,0,0.5)" }}>
          {err}
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 8, top: 8, fontSize: 10, color: "rgba(241,241,249,0.6)", pointerEvents: "none" }}>
        宏体子预览 · {lat === "2" ? "RHP 六棱柱" : "RPP 盒"}
      </div>
    </div>
  );
}
