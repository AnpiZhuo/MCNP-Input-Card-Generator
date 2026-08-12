/**
 * cellMaterial — 栅元材质参数（默认 opaque）
 *
 * 透明 overdraw 根因：全栅元 transparent+opacity0.6+depthWrite:false → 透明通道
 * 每帧重复叠加。MCNP 栅元互斥（#n 已挖空），opaque 渲染几何本就正确。
 *
 * - 默认 opaque：{transparent:false, depthWrite:true, opacity:1}（无 overdraw）
 * - see-through：透传现状半透明配置（opacity:0.6, depthWrite:false）
 * - M0 真空色 "transparent" 维持 opacity 0（两种模式都不可见）
 */
export type TransparentMode = "opaque" | "see-through";

export interface CellMaterialSpec {
  color: string;
  transparent: boolean;
  depthWrite: boolean;
  opacity: number;
}

export function buildCellMaterial(opts: {
  color: string;
  transparentMode?: TransparentMode;
}): CellMaterialSpec {
  const vacuum = opts.color === "transparent";
  if (vacuum) {
    // M0 真空：维持 opacity 0（全透明），不参与 overdraw
    return { color: "#000000", transparent: true, depthWrite: false, opacity: 0 };
  }
  if (opts.transparentMode === "see-through") {
    return { color: opts.color, transparent: true, depthWrite: false, opacity: 0.6 };
  }
  return { color: opts.color, transparent: false, depthWrite: true, opacity: 1 };
}
