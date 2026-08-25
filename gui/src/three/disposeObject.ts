/**
 * disposeObjectGroup — 深度释放 THREE.Group（几何 + 材质递归 dispose + 清空）。
 *
 * 格阵/宏体子预览共用（LatticePreview3D / MacrobodyPreview），避免各自复制。
 */
import * as THREE from "three";

export function disposeObjectGroup(group: THREE.Group): void {
  group.traverse((obj) => {
    const anyObj = obj as any;
    anyObj.geometry?.dispose?.();
    const mat = anyObj.material;
    if (mat) {
      if (Array.isArray(mat)) mat.forEach((m: any) => m?.dispose?.());
      else mat.dispose?.();
    }
  });
  group.clear();
}
