/**
 * 3D 预览截面平面坐标换算（纯函数，vitest 可测）。
 *
 * 3D 预览把 STL 几何平移到模型包围盒中心（显示坐标系），但 /api/cross-section
 * 在后端切的是未平移的原始 STL。用户在预览里输入的平面是显示坐标系：
 *   n·p' = D'（p' = p_raw − center）
 * 换算回原始坐标系：
 *   n·p_raw = D' + n·center
 *
 * 2026-08-18 修复：此前直接把显示系平面发给后端，模型中心偏离原点时
 * 全部栅元切位偏移，与面重合/在原点附近时表现成「部分实体切错」。
 */
export interface PlaneEq {
  A: number;
  B: number;
  C: number;
  D: number;
}

export interface Vec3Like {
  x: number;
  y: number;
  z: number;
}

export function offsetPlaneForStl(plane: PlaneEq, center: Vec3Like): PlaneEq {
  return {
    A: plane.A,
    B: plane.B,
    C: plane.C,
    D: plane.D + plane.A * center.x + plane.B * center.y + plane.C * center.z,
  };
}
