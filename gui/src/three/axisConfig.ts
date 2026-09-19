/**
 * 3D 预览坐标轴配置（单一事实来源，vitest 可测）。
 *
 * 2026-08-18 修复：此前 axisDirs 写成 [X, Z, Y] 而标签顺序是 [X, Y, Z]，
 * 绿色线画在 Z 方向却标 "Y"、蓝色线画在 Y 方向却标 "Z"。
 * 此处固定 X 红 / Y 绿 / Z 蓝，与 Three.js 右手系 + 相机 Z-up 一致。
 *
 * ## 为什么每条轴有两个色（2026-09-19 出图透明底）
 * `color` 是**屏幕色**：给深色场景用的亮色（0xff4444 / 0x44ff44 / 0x4488ff）。
 * `paperInk` 是**印刷墨色**：出图改透明底后，亮绿（0x44ff44）落在白纸/浅底上几乎看不见。
 * 出图时把轴线、刻度线、刻度标签、轴字母一律换成 `paperInk`，
 * **屏上观感不变**（只在取图那一帧里切）。这与 `plotTheme` 的"色相不动、只加深"
 * 是同一条口径：3D 与 2D 出图对颜色的处理方式保持一致。
 */
export interface AxisConfig {
  dir: [number, number, number];
  color: number;
  /** 出图（透明底/白底）用的深色墨；同色相、压暗到浅底上可读 */
  paperInk: number;
  label: string;
}

export const AXIS_CONFIG: AxisConfig[] = [
  { dir: [1, 0, 0], color: 0xff4444, paperInk: 0xa11212, label: "X" },
  { dir: [0, 1, 0], color: 0x44ff44, paperInk: 0x14701f, label: "Y" },
  { dir: [0, 0, 1], color: 0x4488ff, paperInk: 0x144a9e, label: "Z" },
];
