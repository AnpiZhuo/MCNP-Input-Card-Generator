/**
 * hexPrism — pointy-top 六棱柱线框构建器（纯 THREE 场景对象，输入变重建）。
 *
 * 外接半径 R = pitch / √3（蜂窝中心距 pitch 与正六边形外接半径的关系），
 * 顶点朝 +X（pointy-top，与 hexCenter 的蜂窝排布对齐）；轴向 +Z。
 */
import * as THREE from "three";

export interface HexPrismWireframe {
  group: THREE.Group;
  dispose(): void;
}

/** 六棱柱线框：radius=外接半径 R，height=轴向高度，color=线框色 */
export function buildHexPrism(radius: number, height: number, color = 0x66ccff): HexPrismWireframe {
  const group = new THREE.Group();
  const half = height / 2;

  // pointy-top：顶点在角度 0°（+X）处，逆时针 0/60/120/180/240/300
  const top: THREE.Vector3[] = [];
  const bottom: THREE.Vector3[] = [];
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    top.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, half));
    bottom.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, -half));
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
