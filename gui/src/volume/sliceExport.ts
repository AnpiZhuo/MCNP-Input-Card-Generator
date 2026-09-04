/**
 * sliceExport — 体积标量帧的切面（2D 热图）与导出（PNG/SVG/CSV）
 * （能量沉积 3D 解析待办：在 3D 结果窗口按 MeV/g 渲染、切面、导出 PNG/SVG + CSV）
 *
 * 数据事实（镜像后端 numpy 布局）：
 * - frame.resolution = [ni, nj, nk]（x 最慢，i 外层）
 * - frame.dataBase64 为 Uint8 标量，C 序扁平：idx = i*(nj*nk) + j*nk + k（z 最快）
 * - frame.scalarRange = {min,max} 为后端归一化源范围；float 重建 f = u8*(max-min)/255 + min
 *
 * 纯函数、零 DOM 依赖、vitest 可测。PNG 由宿主用 canvas.toDataURL 生成（浏览器原生）。
 */
import { weatherLut, type ScalarRange } from "./colorize";
import { base64ToBytes } from "./VolumeRenderer";

export type SliceAxis = "x" | "y" | "z";

/** 与 VolumeFrame 字段兼容的最小输入（只取切面/导出所需） */
export interface SliceFrameInput {
  resolution: [number, number, number];
  dataBase64: string;
  scalarRange: ScalarRange;
}

export interface SliceResult {
  axis: SliceAxis;
  sliceIndex: number;
  /** 2D 切面维度：x 切 → width=nk、height=nj；y 切 → width=nk、height=ni；z 切 → width=ni、height=nj */
  width: number;
  height: number;
  /** RGBA 像素（width*height*4），weather LUT 映射，v<displayMin → alpha 0 */
  rgba: Uint8ClampedArray;
  min: number;
  max: number;
}

function bytesToFloat(u8: number, sr: ScalarRange): number {
  return (u8 * (sr.max - sr.min)) / 255 + sr.min;
}

function unpack(frame: SliceFrameInput) {
  const [ni, nj, nk] = frame.resolution;
  const bytes = base64ToBytes(frame.dataBase64);
  return { ni, nj, nk, bytes, sr: frame.scalarRange };
}

/** 把 2D(float 标量值) 像素映射进已分配 RGBA 缓冲（shared by 三轴） */
function fillRgba(u8At: (row: number, col: number) => number, width: number, height: number, sr: ScalarRange,
  displayMin: number): Uint8ClampedArray {
  const lut = weatherLut(256);
  const lutMul = (lut.length >> 2) - 1;
  const hasRange = sr.max > sr.min;
  const rgba = new Uint8ClampedArray(width * height * 4);
  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      const f = bytesToFloat(u8At(row, col), sr);
      const p = (row * width + col) * 4;
      if (f < displayMin || !hasRange) { rgba[p + 3] = 0; continue; }
      const frac = (f - sr.min) / (hasRange ? sr.max - sr.min : 1);
      let idx = Math.floor(frac * lutMul);
      if (idx < 0) idx = 0; else if (idx > lutMul) idx = lutMul;
      const base = idx * 4;
      rgba[p] = lut[base]; rgba[p + 1] = lut[base + 1]; rgba[p + 2] = lut[base + 2]; rgba[p + 3] = 255;
    }
  }
  return rgba;
}

/** 生成单轴切面 2D 热图像素。 */
export function sliceFrame(frame: SliceFrameInput, axis: SliceAxis, sliceIndex: number, displayMin: number): SliceResult {
  const { ni, nj, nk, bytes, sr } = unpack(frame);
  let width: number, height: number;
  if (axis === "x") {
    const i = Math.max(0, Math.min(ni - 1, sliceIndex));
    width = nk; height = nj;
    const rgba = fillRgba((row, col) => bytes[i * (nj * nk) + row * nk + col], width, height, sr, displayMin);
    return { axis, sliceIndex: i, width, height, rgba, min: 0, max: 0 };
  }
  if (axis === "y") {
    const j = Math.max(0, Math.min(nj - 1, sliceIndex));
    width = nk; height = ni;
    const rgba = fillRgba((row, col) => bytes[row * (nj * nk) + j * nk + col], width, height, sr, displayMin);
    return { axis, sliceIndex: j, width, height, rgba, min: 0, max: 0 };
  }
  const k = Math.max(0, Math.min(nk - 1, sliceIndex));
  width = ni; height = nj;
  const rgba = fillRgba((row, col) => bytes[row * (nj * nk) + col * nk + k], width, height, sr, displayMin);
  return { axis, sliceIndex: k, width, height, rgba, min: 0, max: 0 };
}

/** 当前帧全数据 → CSV（按体素 i,j,k,value，float 重建原值，能量沉积为 MeV/g） */
export function frameToCsv(frame: SliceFrameInput): string {
  const { ni, nj, nk, bytes, sr } = unpack(frame);
  const rows: string[] = ["i,j,k,value"];
  for (let i = 0; i < ni; i++) {
    for (let j = 0; j < nj; j++) {
      for (let k = 0; k < nk; k++) {
        const u8 = bytes[i * (nj * nk) + j * nk + k];
        rows.push(`${i},${j},${k},${bytesToFloat(u8, sr)}`);
      }
    }
  }
  return rows.join("\n");
}

/** 切面 → 矢量 SVG（每体素一个 <rect>，真正矢量、可无损缩放） */
export function sliceToSvg(slice: SliceResult): string {
  const { width, height, rgba } = slice;
  const cell = 2; // 每体素 2px，128² 切面约 256×256
  const rects: string[] = [];
  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      const p = (row * width + col) * 4;
      const a = rgba[p + 3];
      if (a === 0) continue;
      const r = rgba[p], g = rgba[p + 1], b = rgba[p + 2];
      rects.push(`<rect x="${col * cell}" y="${row * cell}" width="${cell}" height="${cell}" fill="rgb(${r},${g},${b})" opacity="${(a / 255).toFixed(2)}"/>`);
    }
  }
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width * cell}" height="${height * cell}" viewBox="0 0 ${width * cell} ${height * cell}">`,
    `<rect width="${width * cell}" height="${height * cell}" fill="#0a0a1e"/>`,
    ...rects,
    `</svg>`,
  ].join("");
}
