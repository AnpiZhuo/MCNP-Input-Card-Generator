/**
 * exportFigure — 出图的**唯一门面**：调用方只说"我这张图由哪些块组成"，其余全在这里决定。
 *
 * ## 用户怎么用（这就是全部交互）
 * 点窗口标题栏那个「导出」按钮。不弹格式框、不弹参数框、不问落盘位置（走系统「另存为」）。
 *
 * ## 我们替他决定的事（2026-09-19 用户裁决后**只有一种产物**）
 * | 情况 | 产物 | 依据 |
 * | :--- | :--- | :--- |
 * | 任何视图（3D / 截面 / 曲线 / 切面 / keff） | **PNG（2×、白底）** | 用户原话（2026-09-19）："png 都改为白底" |
 *
 * ## 为什么不再出 PDF/SVG（这是有代价的选择，写在这里免得后人再问）
 * 2D 图原先出矢量 PDF+SVG（放大不糊、可编辑），改成 PNG 后**丢掉矢量性**：
 * 放大到海报尺寸会糊，也不能再进 Illustrator 改线。换来的是一致性 ——
 * 用户拿到的永远是同一类文件、"另存为"只问一次、不用再纠结选哪个格式。
 * 若将来要恢复矢量出口，缺的不是渲染能力，而是**格式决策的口径**（问用户 / 加开关），
 * 代码路径本身（`buildVectorFigure` → `figureToPdf`）还原样保留着。
 */
import { capturePngBytes, svgToRaster } from "./captureFrame";
import { preparePanels, renderFigure, type FigureSpec } from "./figureCanvas";
import { figureFileName, saveFile, type SaveOutcome } from "./saveFile";
import { buildVectorFigure, type VectorFigureSpec } from "./vectorFigure";

/** 位图出口的放大倍数（用户要的"2×"） */
export const RASTER_SCALE = 2;

export interface ExportFigureRequest {
  /** 视图名（进文件名与图标题），如 "3D几何" / "截面" / "Tally通量" */
  view: string;
  /** 文件名里的参数段（tally 号、能量区间、分辨率、层号……） */
  nameParts?: (string | number | undefined | null)[];
  /** 栅格出口的规格（3D 视图 / 含热图的合成图） */
  raster?: Omit<FigureSpec, "theme">;
  /** 二维图的规格（先组合成矢量，再栅格成 PNG —— 保住文字锐度） */
  vector?: Omit<VectorFigureSpec, "theme">;
  /** 保存位置（Tauri fs 降级时用）；不给则走系统对话框/浏览器下载 */
  dir?: string;
}

export interface ExportedFile {
  /** 一律 "png" */
  format: string;
  path: string;
  bytes: number;
  /** true = 走了降级路径（如中文字形缺失改浏览器默认字体），便于界面提示与问题排查 */
  degraded?: boolean;
  degradeReason?: string;
}

export type ExportResult =
  | { status: "exported"; files: ExportedFile[] }
  | { status: "cancelled" }
  | { status: "error"; message: string };

/**
 * 出图底色：**白底**（2026-09-19 用户裁决，取代当天的"缺省透明底"）。
 *
 * ## 为什么改成白底
 * 用户先要"该用透明底的用透明底"，实机看过之后改口"png 都改为白底"。白底的现实好处：
 * 贴进 Word/LaTeX 不会因为页面底色不同而出现"文字看不清"（论文主题的轴与文字是深色，
 * 叠在深色幻灯片上时确实会糊）；也省掉"这张要不要透明"的判断负担。
 *
 * ## 那"透明取帧"还留着吗——留着，但不是给最终产物用的
 * 3D 的 `renderTransparentNow()`（`captureFrame.captureTransparent3D`）仍在用：
 * 取到**透明底**的一帧，才能把它干净地合成到这张白底版面上（否则会把 WebGL 的深色场景底
 * 一起贴上来）。**产物是白底，中间帧是透明**——两件事，别混。
 */
const FIGURE_BACKGROUND = "#ffffff";

/**
 * 出一张图。**只有 PNG 一种产物，一律白底**。
 *
 * 两条通路的差别只在于"先组合什么"：
 * - `vector` 给了 → 先做矢量合成（版面用真 `<text>`/`<path>`），再按 2× 栅格化；
 * - 否则用 `raster`（3D 视图这类本来就是位图的）。
 */
export async function exportFigure(req: ExportFigureRequest): Promise<ExportResult> {
  const files: ExportedFile[] = [];

  // ── 矢量通路：合成矢量（白底铺在最底层）→ 2× 栅格 → PNG ──
  if (req.vector) {
    const built = buildVectorFigure({ theme: "paper", background: FIGURE_BACKGROUND, ...req.vector });
    const canvas = await svgToRaster(built.svg, { scale: RASTER_SCALE, background: FIGURE_BACKGROUND });
    if (!canvas) return { status: "error", message: "图像生成失败（矢量栅格化失败）" };
    // 产物不透明：这里再按白底编码一次，保证 alpha 通道也干净（不依赖上游每一步都不漏底）
    const bytes = await capturePngBytes(canvas, { scale: 1, background: FIGURE_BACKGROUND });
    if (!bytes) return { status: "error", message: "图像生成失败（编码失败）" };
    return await savePng(bytes, req);
  }

  // ── 栅格通路（3D 视图、含热图的合成图） ──
  if (req.raster) {
    const prepared = await preparePanels({ theme: "paper", ...req.raster }, RASTER_SCALE);
    // 白底铺在合成图最底层；3D 面板本身是透明取帧，叠上来正好
    const { canvas } = renderFigure(prepared, { background: FIGURE_BACKGROUND });
    const bytes = await capturePngBytes(canvas, { scale: 1, background: FIGURE_BACKGROUND });
    if (!bytes) return { status: "error", message: "图像生成失败（画布为空）" };
    return await savePng(bytes, req);
  }

  return { status: "error", message: "没有可导出的内容" };
}

/** PNG 落盘（名称、提示、取消语义都收在这里，两条通路共用） */
async function savePng(bytes: Uint8Array, req: ExportFigureRequest): Promise<ExportResult> {
  const name = figureFileName(req.view, req.nameParts ?? [], "png");
  const out = await saveFile({ data: bytes, fileName: name, mime: "image/png", dir: req.dir });
  if (out.status === "cancelled") return { status: "cancelled" };
  if (out.status === "error") return { status: "error", message: out.message };
  return { status: "exported", files: [{ format: "png", path: out.path, bytes: bytes.byteLength }] };
}

/** 把 `ExportResult` 变成一句给用户看的话（各窗口共用，避免提示文案分叉） */
export function exportMessage(r: ExportResult, viewLabel = "图"): string {
  if (r.status === "cancelled") return ""; // 用户主动取消：不打扰
  if (r.status === "error") return `❌ ${viewLabel}导出失败：${r.message}`;
  const lines = r.files.map((f) => {
    const size = f.bytes > 1024 * 1024 ? `${(f.bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(f.bytes / 1024))} KB`;
    const note = f.degraded ? `（${f.degradeReason}）` : "";
    return `  · ${f.format.toUpperCase()}  ${size}${note}`;
  });
  return `✅ 已导出${viewLabel}：\n${lines.join("\n")}\n\n位置：${r.files[0]?.path ?? ""}`;
}

/** 便捷：导出并提示（各窗口一行接线用；测试里不调它，避免绑死 UI） */
export async function exportFigureWithToast(req: ExportFigureRequest, viewLabel?: string): Promise<ExportResult> {
  const r = await exportFigure(req);
  const msg = exportMessage(r, viewLabel ?? req.view);
  if (msg) {
    // 用 alert 而不是 toast：导出是"用户主动等结果"的动作，需要明确回执
    try { alert(msg); } catch { /* 非浏览器环境 */ }
  }
  return r;
}

export type { SaveOutcome };

