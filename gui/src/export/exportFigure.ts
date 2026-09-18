/**
 * exportFigure — 出图的**唯一门面**：调用方只说"我这张图由哪些块组成"，其余全在这里决定。
 *
 * ## 用户怎么用（这就是全部交互）
 * 点窗口标题栏那个「导出」按钮。不弹格式框、不弹参数框、不问落盘位置（走系统「另存为」）。
 *
 * ## 我们替他决定的事
 * | 情况 | 产物 | 依据 |
 * | :--- | :--- | :--- |
 * | 图里有位图（3D 视图、切面热图） | **PNG（2×、白底）** | WebGL 没法矢量化，只能位图；2× 保证印刷够清晰 |
 * | 纯二维矢量图 | **PDF（矢量）+ SVG** | 论文要 PDF，改图/投稿要 SVG；两份同源同构图 |
 * | 有中文字体 | 矢量 PDF（中文可选中、可搜索） | 首选，放大不糊 |
 * | 无中文字体 / 字体塞爆体积 | **300dpi 白底位图 PDF** | 宁可位图，也不出"中文全空白"或 15 MB 的 PDF |
 *
 * ## 为什么降级是"自动"而不是报错
 * 用户不该知道什么叫"字体子集化"。他点一下就该拿到一张能用的图；
 * 拿 PNG/位图 PDF 也比弹一个"请先安装字体"要强。降级路径因此写在实现里，
 * 只有**彻底失败**（连位图都出不来）才回错误。
 */
import { captureCanvas, capturePngBytes, svgToRaster } from "./captureFrame";
import { loadCjkFont } from "./cjkFont";
import { preparePanels, renderFigure, type FigureSpec } from "./figureCanvas";
import { themeFor } from "./plotTheme";
import { figureFileName, saveFile, type SaveOutcome } from "./saveFile";
import { buildVectorFigure, figureToPdf, type VectorFigureSpec } from "./vectorFigure";

/** 位图出口的放大倍数（用户要的"2×"） */
export const RASTER_SCALE = 2;
/** 位图 PDF 的等效分辨率（300 dpi ≈ 每 px 放大 4.17 倍） */
export const PDF_RASTER_SCALE = 4;
/** 矢量 PDF 体积上限：超过就说明字体没子集化，改走位图 */
export const VECTOR_PDF_MAX_BYTES = 6_000_000;

export interface ExportFigureRequest {
  /** 视图名（进文件名与图标题），如 "3D几何" / "截面" / "Tally通量" */
  view: string;
  /** 文件名里的参数段（tally 号、能量区间、分辨率、层号……） */
  nameParts?: (string | number | undefined | null)[];
  /** 栅格出口的规格（3D 视图 / 含热图的合成图） */
  raster?: Omit<FigureSpec, "theme">;
  /** 矢量出口的规格（纯二维图；给了就优先出 PDF+SVG） */
  vector?: Omit<VectorFigureSpec, "theme">;
  /** 保存位置（Tauri fs 降级时用）；不给则走系统对话框/浏览器下载 */
  dir?: string;
}

export interface ExportedFile {
  /** "pdf" | "svg" | "png" */
  format: string;
  path: string;
  bytes: number;
  /** true = 走了降级路径（如无中文字体改位图 PDF），便于界面提示与问题排查 */
  degraded?: boolean;
  degradeReason?: string;
}

export type ExportResult =
  | { status: "exported"; files: ExportedFile[] }
  | { status: "cancelled" }
  | { status: "error"; message: string };

/**
 * 出一张图。**纯二维给矢量（PDF+SVG），含位图给 PNG**；一律论文配色。
 */
export async function exportFigure(req: ExportFigureRequest): Promise<ExportResult> {
  const theme = themeFor("paper");
  const files: ExportedFile[] = [];

  // ── 矢量通路优先（用户要的"能用矢量就用矢量"）──
  if (req.vector) {
    const built = buildVectorFigure({ theme: "paper", ...req.vector });
    const base = figureFileName(req.view, req.nameParts ?? [], "svg");
    const svgOut = await saveFile({ data: built.svg, fileName: base, mime: "image/svg+xml", dir: req.dir });
    if (svgOut.status === "cancelled") return { status: "cancelled" };
    if (svgOut.status === "error") return { status: "error", message: svgOut.message };
    files.push({ format: "svg", path: svgOut.path, bytes: byteLength(built.svg) });

    const pdf = await exportVectorPdf(built, req);
    if (pdf.status === "cancelled") return { status: "cancelled" };
    if (pdf.status === "error") return { status: "error", message: pdf.message };
    files.push(...pdf.files);
    return { status: "exported", files };
  }

  // ── 栅格通路（3D 视图、含热图的合成图）──
  if (req.raster) {
    const prepared = await preparePanels({ theme: "paper", ...req.raster }, RASTER_SCALE);
    const { canvas } = renderFigure(prepared, { background: "#ffffff" });
    const bytes = await capturePngBytes(canvas, { scale: 1, background: "#ffffff" });
    if (!bytes) return { status: "error", message: "图像生成失败（画布为空）" };
    const name = figureFileName(req.view, req.nameParts ?? [], "png");
    const out = await saveFile({ data: bytes, fileName: name, mime: "image/png", dir: req.dir });
    if (out.status === "cancelled") return { status: "cancelled" };
    if (out.status === "error") return { status: "error", message: out.message };
    files.push({ format: "png", path: out.path, bytes: bytes.byteLength });
    return { status: "exported", files };
  }

  return { status: "error", message: "没有可导出的内容" };
}

/** 矢量 PDF：有中文字体就真矢量，否则位图（明确标记降级原因） */
async function exportVectorPdf(
  built: { svg: string; width: number; height: number },
  req: ExportFigureRequest,
): Promise<{ status: "ok"; files: ExportedFile[] } | { status: "cancelled" } | { status: "error"; message: string }> {
  const name = figureFileName(req.view, req.nameParts ?? [], "pdf");
  const font = await loadCjkFont();
  const fontOpt = font.ok ? { name: font.name, data: font.data } : undefined;

  let pdfBytes: Uint8Array | null = null;
  let degraded = false;
  let degradeReason: string | undefined;

  const outcome = await figureToPdf(built, { font: fontOpt, maxBytes: VECTOR_PDF_MAX_BYTES, background: "#ffffff" });
  if (outcome.ok) {
    pdfBytes = outcome.bytes;
  } else {
    degraded = true;
    degradeReason = degradeReasonText(outcome);
    pdfBytes = await rasterPdf(built);
  }
  if (!pdfBytes) return { status: "error", message: "PDF 生成失败" };

  const out = await saveFile({ data: pdfBytes, fileName: name, mime: "application/pdf", dir: req.dir });
  if (out.status === "cancelled") return { status: "cancelled" };
  if (out.status === "error") return { status: "error", message: out.message };
  return { status: "ok", files: [{ format: "pdf", path: out.path, bytes: pdfBytes.byteLength, degraded, degradeReason }] };
}

function degradeReasonText(o: { reason: string; message?: string; bytes?: number }): string {
  if (o.reason === "needsCjkFont") return "系统没有可用的中文字体，已改用 300dpi 位图 PDF（内容不缺）";
  if (o.reason === "tooLarge") return `矢量 PDF 体积过大（${Math.round((o.bytes ?? 0) / 1e6)} MB，字体未子集化），已改用 300dpi 位图 PDF`;
  return `矢量转换失败（${o.message ?? "未知"}），已改用位图 PDF`;
}

/**
 * 位图 PDF：把矢量图按高倍率栅格化，再塞进同尺寸 PDF。
 * 这条路的唯一目的是**内容不缺**——中文、等值线、图例全在，只是不可编辑、放大有限。
 */
async function rasterPdf(fig: { svg: string; width: number; height: number }): Promise<Uint8Array | null> {
  const canvas = await svgToRaster(fig.svg, { scale: PDF_RASTER_SCALE / RASTER_SCALE, background: "#ffffff" });
  if (!canvas) return null;
  try {
    const { jsPDF } = await import("jspdf");
    const doc: any = new jsPDF({
      unit: "pt",
      format: [fig.width, fig.height],
      orientation: fig.width >= fig.height ? "landscape" : "portrait",
    });
    const dataUrl = canvas.toDataURL("image/png");
    doc.addImage(dataUrl, "PNG", 0, 0, fig.width, fig.height);
    return new Uint8Array(doc.output("arraybuffer") as ArrayBuffer);
  } catch (e) {
    console.warn("[exportFigure] 位图 PDF 失败", e);
    return null;
  }
}

function byteLength(s: string): number {
  try {
    return new TextEncoder().encode(s).byteLength;
  } catch {
    return s.length;
  }
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
export { captureCanvas };

