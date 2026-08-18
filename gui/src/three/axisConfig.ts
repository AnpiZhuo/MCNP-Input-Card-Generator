/**
 * 3D 预览坐标轴配置（单一事实来源，vitest 可测）。
 *
 * 2026-08-18 修复：此前 axisDirs 写成 [X, Z, Y] 而标签顺序是 [X, Y, Z]，
 * 绿色线画在 Z 方向却标 "Y"、蓝色线画在 Y 方向却标 "Z"。
 * 此处固定 X 红 / Y 绿 / Z 蓝，与 Three.js 右手系 + 相机 Z-up 一致。
 */
export interface AxisConfig {
  dir: [number, number, number];
  color: number;
  label: string;
}

export const AXIS_CONFIG: AxisConfig[] = [
  { dir: [1, 0, 0], color: 0xff4444, label: "X" },
  { dir: [0, 1, 0], color: 0x44ff44, label: "Y" },
  { dir: [0, 0, 1], color: 0x4488ff, label: "Z" },
];
