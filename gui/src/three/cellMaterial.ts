/**
 * cellMaterial — 栅元材质参数（模块默认 opaque；体积窗口经显式 mode/opacity 用半透明档）
 *
 * 透明 overdraw 根因：全栅元 transparent+opacity0.6+depthWrite:false → 透明通道
 * 每帧重复叠加。MCNP 栅元互斥（#n 已挖空），opaque 渲染几何本就正确。
 *
 * - 默认 opaque：{transparent:false, depthWrite:true, opacity:1}（无 overdraw）
 *   —— Preview3D 主组件默认 opaque，本模块默认契约不变。
 * - semi（体积窗口默认外壳）：{transparent:true, depthWrite:false, opacity:0.4}
 *   —— 用户反馈「栅元默认应半透明」：不透明外壳 depthWrite 挡住体积层。
 *     depthWrite:false 是体积层透出的关键（外壳不再写深度），MCNP 栅元互斥，
 *     相邻面 overdraw 极小，可接受。
 * - see-through：透传现状半透明配置（opacity:0.6, depthWrite:false）
 * - opacity 可选参数：半透明档位的连续透明度覆盖（栅元透明度滑杆 0~1）。
 * - M0 真空色 "transparent" 维持 opacity 0（所有档位都不可见）
 */
export type TransparentMode = "opaque" | "semi" | "see-through";

/** 体积窗口栅元外壳默认半透明透明度（用户反馈 #3：默认半透明而非不透明） */
export const DEFAULT_SHELL_OPACITY = 0.4;

export interface CellMaterialSpec {
  color: string;
  transparent: boolean;
  depthWrite: boolean;
  opacity: number;
}

export function buildCellMaterial(opts: {
  color: string;
  transparentMode?: TransparentMode;
  /** 半透明档位连续透明度覆盖（0~1）；缺省按档位默认（semi=0.4 / see-through=0.6） */
  opacity?: number;
}): CellMaterialSpec {
  const vacuum = opts.color === "transparent";
  if (vacuum) {
    // M0 真空：维持 opacity 0（全透明），不参与 overdraw
    return { color: "#000000", transparent: true, depthWrite: false, opacity: 0 };
  }
  const mode = opts.transparentMode ?? "opaque";
  if (mode === "opaque") {
    return { color: opts.color, transparent: false, depthWrite: true, opacity: 1 };
  }
  const fallback = mode === "see-through" ? 0.6 : DEFAULT_SHELL_OPACITY;
  return { color: opts.color, transparent: true, depthWrite: false, opacity: opts.opacity ?? fallback };
}
