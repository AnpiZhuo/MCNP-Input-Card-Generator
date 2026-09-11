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

/**
 * 已登记的弹出窗口 label（**单一期望清单**）。
 * main.rs create_or_focus 与 App.tsx WindowRouter 两侧都必须恰好是这一组。
 * 新增窗口时**必须**把 label 加进本数组，否则「未登记窗口」用例会红（T3 FE-11/FE-12 加固）。
 */
const EXPECTED_WINDOW_LABELS: string[] = ["preview3d", "cross_section", "volume", "ptrac", "source-demo"];

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
  it("★守卫自检：两处正则都必须真的抽到 label（防「空对空」假绿）", () => {
    // 背景（T3 FE-12）：本文件靠正则从 main.rs / App.tsx 源码抽 label。若有人把双引号改单引号、
    // 或把调用拆成多行，两处正则可能同时抽成空数组，而 expect([]).toEqual([]) 会**通过** —— 守卫
    // 在「全绿」状态下失效却无人报警。故先钉住抽取结果非空且条数正确。
    const m = mainRsWindowLabels(MAIN_RS);
    const a = appRouteLabels(APP_TSX);
    expect(m.length).toBeGreaterThan(0);
    expect(a.length).toBeGreaterThan(0);
    expect(m).toHaveLength(EXPECTED_WINDOW_LABELS.length);
    expect(a).toHaveLength(EXPECTED_WINDOW_LABELS.length);
  });

  it("main.rs create_or_focus 建窗 label 集合 == App.tsx WindowRouter 路由分支 label 集合", () => {
    expect(mainRsWindowLabels(MAIN_RS)).toEqual(appRouteLabels(APP_TSX));
  });

  it("弹出窗口 label 各自与路由分支同值（preview3d/cross_section/volume/ptrac/source-demo，绝无 volume3d）", () => {
    const m = mainRsWindowLabels(MAIN_RS);
    const a = appRouteLabels(APP_TSX);
    for (const label of EXPECTED_WINDOW_LABELS) {
      expect(m).toContain(label);
      expect(a).toContain(label);
    }
    // volume 必须是「3D 结果」窗口的 label（而非 volume3d），否则子窗口渲染整个主应用
    expect(m).not.toContain("volume3d");
  });

  it("★新增第 6 个窗口必须登记：main.rs / App.tsx 出现未登记的 create_or_focus label 即红", () => {
    // 背景（T3 FE-11）：原先「集合相等」那一问无法约束**未来**新增窗口 —— 新窗口只要
    // main.rs 与 App.tsx 同步改就会通过，但若漏加进上面的 EXPECTED_WINDOW_LABELS，
    // 守卫就失去「逐个同值」的独立校验。此用例把「未登记的窗口 label」显式暴露出来：
    // 新增窗口时必须同时把 label 加进 EXPECTED_WINDOW_LABELS，否则本用例红并打印缺失项。
    const m = mainRsWindowLabels(MAIN_RS);
    const a = appRouteLabels(APP_TSX);
    const registered = new Set<string>(EXPECTED_WINDOW_LABELS);
    const unregistered = [...new Set([...m, ...a])].filter((l) => !registered.has(l)).sort();
    expect(unregistered, `发现未登记的窗口 label：${unregistered.join(", ")}（请加进 EXPECTED_WINDOW_LABELS）`).toEqual([]);
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
