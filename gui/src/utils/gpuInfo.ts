/**
 * gpuInfo — 3D 预览实际使用的 GPU 检测深模块（项4 辅助）。
 *
 * 背景：Tauri/WebView2 应用的真实 WebGL 渲染跑在 msedgewebview2.exe，网页只能给
 * `powerPreference: "high-performance"` 提示，无法硬锁独显。此模块读取当前 WebGL
 * 上下文实际绑定的 GPU（`WEBGL_debug_renderer_info` 扩展），供界面显示「当前到底
 * 用的核显还是独显」，配合 tools/set-discrete-gpu.ps1 验证是否切到独显。
 *
 * 纯函数可测（classifyGpu），detectWebGLGpu 依赖 DOM/WebGL（浏览器运行）。
 */
export interface GpuInfo {
  /** 厂商：nvidia | amd | intel | apple | unknown */
  vendor: string;
  /** true=独立显卡（高性能），false=集成/核显 */
  discrete: boolean;
  /** 人类可读的 GPU 名称（原始 renderer/vendor 串） */
  name: string;
}

export interface GpuRawResult {
  vendor: string;
  renderer: string;
}

/**
 * 分类 GPU：根据 vendor/renderer 字符串判断厂商与是否独立显卡。
 * 规则：
 *   - nvidia（GeForce/Quadro/RTX/GTX）→ 独显
 *   - amd（Radeon/RX/FirePro/Vega64 等）→ 独显（移动 APU 核显少见单独标出，可接受）
 *   - intel（UHD/Iris/AlderLake/…）→ 默认核显；含 Arc 视为独显
 *   - apple（Apple M 系列）→ 独显
 *   - 未知 → 按核显（保守）
 */
export function classifyGpu(vendorRaw: string | null, rendererRaw: string | null): GpuInfo | null {
  const vendor = (vendorRaw || "").toLowerCase();
  const renderer = (rendererRaw || "").toLowerCase();
  const name = rendererRaw || vendorRaw || "";
  if (!vendor && !renderer) return null;

  if (/nvidia|geforce|quadro|\brtx\b|\bgtx\b/.test(renderer) || /nvidia/.test(vendor)) {
    return { vendor: "nvidia", discrete: true, name };
  }
  if (/amd|radeon|firepro/.test(renderer) || /amd|ati/.test(vendor)) {
    // 含 "graphics"（如 Radeon(TM) Graphics）= APU 核显；否则按型号(RX/FirePro/Vega20-64/PRO)判独显
    const discrete = !/graphics|integrated/.test(renderer) && /rx\s?\d|firepro|vega\s?(20|56|64)|pro\b/.test(renderer);
    return { vendor: "amd", discrete, name };
  }
  if (/intel/.test(renderer) || /intel/.test(vendor)) {
    const discrete = /\barc\b|iris xe max|discrete/.test(renderer);
    return { vendor: "intel", discrete, name };
  }
  if (/apple/.test(renderer) || /apple/.test(vendor)) {
    return { vendor: "apple", discrete: true, name };
  }
  return { vendor: "unknown", discrete: false, name };
}

/**
 * 读取当前 WebGL 上下文实际绑定的渲染器/厂商（浏览器环境）。
 * 不可用（无 WebGL / jsdom）→ null。
 * 创建临时 context 后立即释放（WEBGL_lose_context），避免占资源。
 */
export function detectWebGLGpu(): GpuRawResult | null {
  try {
    const canvas = document.createElement("canvas");
    const gl = (canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    if (!gl) return null;
    let vendor: string;
    let renderer: string;
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    try {
      if (dbg) {
        vendor = String(gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL));
        renderer = String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL));
      } else {
        vendor = String(gl.getParameter(gl.VENDOR));
        renderer = String(gl.getParameter(gl.RENDERER));
      }
    } finally {
      const lose = gl.getExtension("WEBGL_lose_context");
      if (lose) lose.loseContext();
    }
    return { vendor, renderer };
  } catch {
    return null;
  }
}

/** 把 GpuInfo 变成一行提示文案（供界面显示 + 测试断言） */
export function gpuStatusText(info: GpuInfo | null): string {
  if (!info) return "🎮 GPU: 不可用/未知";
  const kind = info.discrete ? "独显" : "核显（集显）";
  return `🎮 GPU: ${info.name || info.vendor} · ${kind}`;
}
