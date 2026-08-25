/**
 * hexPrism — 六棱柱线框构建器（纯 THREE 场景对象，输入变重建）。
 *
 * 面法向 0°/60°/120°（⊥ 六条格矢方向，对齐 hexCenter a1=0° 蜂窝；RHP R1=∥a1），
 * 顶点在 30°+k·60°；轴向 +Z。参数为 apothem（半对边距/面心到轴距离），
 * 外接半径 = apothem·2/√3（与 RHP 卡 R1=(apothem,0,0) 一致）。
 */
import * as THREE from "three";

export interface HexPrismWireframe {
  group: THREE.Group;
  dispose(): void;
}

/** 六棱柱线框：apothem=半对边距（面心到轴），height=轴向高度，color=线框色 */
export function buildHexPrism(apothem: number, height: number, color = 0x66ccff): HexPrismWireframe {
  const group = new THREE.Group();
  const half = height / 2;
  const R = (apothem * 2) / Math.sqrt(3); // 外接半径

  // 面法向 0°/60°/120° → 顶点在 30°+k·60°，逆时针
  const top: THREE.Vector3[] = [];
  const bottom: THREE.Vector3[] = [];
  for (let i = 0; i < 6; i++) {
    const a = Math.PI / 6 + (i / 6) * Math.PI * 2;
    top.push(new THREE.Vector3(Math.cos(a) * R, Math.sin(a) * R, half));
    bottom.push(new THREE.Vector3(Math.cos(a) * R, Math.sin(a) * R, -half));
  }

  const geo: THREE.Vector3[] = [];
  // 顶部循环 + 底部循环 + 6 竖棱
  for (let i = 0; i < 6; i++) {
    const n = (i + 1) % 6;
    geo.push(top[i], top[n], bottom[i], bottom[n], top[i], bottom[i]);
  }

  const geom = new THREE.BufferGeometry().setFromPoints(geo);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 });
  const line = new THREE.LineSegments(geom, mat);
  group.add(line);

  return {
    group,
    dispose() {
      geom.dispose();
      mat.dispose();
      group.clear();
    },
  };
}
