import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

/**
 * P0 修复回归：3D 结果窗口渲染整棵主应用树（2026-08-15 PM 指令，测试先行）。
 *
 * 根因：main.rs open_volume3d_window 用 create_or_focus 建窗 label="volume3d"，而
 *       App.tsx WindowRouter 只路由 label==="volume"（浏览器调试 hash #/volume）→
 *       volume3d 窗口落空到 <AppInner/>（整个主应用）——用户实测「弹出一个客户端」。
 *       对照 preview3d/cross_section 两窗 main.rs label 与 App.tsx 路由分支一致，唯独 volume3d 例外。
 * 修法：main.rs create_or_focus label "volume3d"→"volume"，单值统一（对齐 preview3d/cross_section 惯例）。
 *
 * 本测试做源码级守卫：main.rs 的 create_or_focus 建窗 label 集合 == App.tsx WindowRouter 的
 * 路由分支 label 集合；且 localStorage 桥 key（mcnp_win_volume3d）不随窗口 label 更名。
 */
const HERE = dirname(fileURLToPath(import.meta.url)); // gui/test/volume
const MAIN_RS = readFileSync(join(HERE, "../../src-tauri/src/main.rs"), "utf-8");
const APP_TSX = readFileSync(join(HERE, "../../src/App.tsx"), "utf-8");
const WINDOWS_TS = readFileSync(join(HERE, "../../src/utils/windows.ts"), "utf-8");

/** main.rs 里所有 create_or_focus(&app, "<label>", ...) 的窗口 label */
function mainRsWindowLabels(src: string): string[] {
  const labels: string[] = [];
  for (const m of src.matchAll(/create_or_focus\(&app, "([^"]+)"/g)) labels.push(m[1]);
  return labels.sort();
}

/** App.tsx WindowRouter 里所有 if (label === "<label>") return ... 的路由分支 label */
function appRouteLabels(src: string): string[] {
  const labels: string[] = [];
  for (const m of src.matchAll(/if \(label === "([^"]+)"\) return/g)) labels.push(m[1]);
  return labels.sort();
}

describe("窗口 label ↔ App.tsx 路由一致性（P0 回归）", () => {
  it("main.rs create_or_focus 建窗 label 集合 == App.tsx WindowRouter 路由分支 label 集合", () => {
    expect(mainRsWindowLabels(MAIN_RS)).toEqual(appRouteLabels(APP_TSX));
  });

  it("弹出窗口 label 各自与路由分支同值（preview3d/cross_section/volume/ptrac/source-demo，绝无 volume3d）", () => {
    const m = mainRsWindowLabels(MAIN_RS);
    const a = appRouteLabels(APP_TSX);
    for (const label of ["preview3d", "cross_section", "volume", "ptrac", "source-demo"]) {
      expect(m).toContain(label);
      expect(a).toContain(label);
    }
    // volume 必须是「3D 结果」窗口的 label（而非 volume3d），否则子窗口渲染整个主应用
    expect(m).not.toContain("volume3d");
  });

  it("localStorage 桥 key mcnp_win_volume3d（KEY_VOLUME3D）保持不动，不随窗口 label 更名", () => {
    expect(WINDOWS_TS).toMatch(/KEY_VOLUME3D = "mcnp_win_volume3d"/);
  });

  it("PTRAC 桥 key mcnp_win_ptrac（KEY_PTRAC）存在（契约 §4）", () => {
    expect(WINDOWS_TS).toMatch(/KEY_PTRAC = "mcnp_win_ptrac"/);
  });

  it("演示源桥 key mcnp_win_source_demo（KEY_SOURCE_DEMO）存在（契约 §5）", () => {
    expect(WINDOWS_TS).toMatch(/KEY_SOURCE_DEMO = "mcnp_win_source_demo"/);
  });
});
