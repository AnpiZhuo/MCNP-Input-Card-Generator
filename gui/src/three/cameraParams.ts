/**
 * cameraParams — 相机参数计算（纯函数，无 THREE 依赖）
 *
 * 大坐标闪烁根因：near=0.1 固定 + far=realVD*100 → ±10000 时 far≈17.5M 超 2^24
 * 深度极限；几何不归一化 + target 恒原点 → 深度精度进一步恶化。
 *
 * 本模块按几何包围盒动态收紧 near/far：far/near 恒 = 5000（≤ 1e4，远离 2^24），
 * position 相对 bboxCenter 偏移、target=center，配合 §5.2.2 几何归一化
 * （先把几何平移到中心 → 相机以原点为靶）对齐轴线/刻度。
 */
export interface CameraParams {
  near: number;
  far: number;
  farNear: number;
  position: [number, number, number];
  target: [number, number, number];
  minDistance: number;
  maxDistance: number;
}

export function computeCameraParams(
  bboxCenter: [number, number, number],
  bboxSize: [number, number, number],
): CameraParams {
  const maxDim = Math.max(bboxSize[0], bboxSize[1], bboxSize[2]);
  const realExt = (maxDim > 0 ? maxDim : 1) * 0.5;
  const near = realExt * 0.02;
  const far = realExt * 100;
  const viewDist = realExt * 3.5;
  return {
    near,
    far,
    farNear: far / near,
    position: [
      bboxCenter[0] + viewDist * 0.6,
      bboxCenter[1] + viewDist * 0.6,
      bboxCenter[2] + viewDist * 0.5,
    ],
    target: [bboxCenter[0], bboxCenter[1], bboxCenter[2]],
    minDistance: realExt * 0.1,
    maxDistance: realExt * 50,
  };
}
