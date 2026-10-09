// @vitest-environment jsdom
/**
 * StepImportDialog DOM 测试 —— 点「📥 导入」即刻自我关闭。
 *
 * 用户反馈（2026-09-12，部署版真机）：「导入按钮有用，只是这个界面不会自己关」。
 * 旧行为：窗口一直开着等 `/api/import-step` 回来（GEOUNED 转换小件 3~4 s、真实
 * CAD 装配体可达分钟级），转换完弹完 alert 才关 —— 观感就是"点了没反应"。
 *
 * 契约（本次锁死）：
 *   1. 未选文件点导入 → 弹 alert 提示、**不**关窗、不调用 onImport；
 *   2. 选了文件点导入 → **同步**把 (settings, file) 交给 onImport 并立刻 onClose，
 *      **不等** onImport 的 Promise 落地（转换在后台跑，结果由 alert 告知）；
 *   3. 设置项原样透传给 onImport。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import StepImportDialog from "../src/components/StepImportDialog";

afterEach(() => cleanup());

// 每个用例都从**干净的存储**开始：导入设置会持久化到独立 localStorage 键
// （见 utils/stepImportPrefs），不清理的话上一个用例的值会被下一个用例的对话框读回来。
beforeEach(() => { localStorage.clear(); });

/** 复刻 GeometryTab 的父子关系：onClose → 卸载对话框。 */
function Harness({ onImport }: { onImport: (s: any, f: File) => void }) {
  const [open, setOpen] = React.useState(true);
  return React.createElement(React.Fragment, null,
    React.createElement("div", null, open ? "OPEN" : "CLOSED"),
    open ? React.createElement(StepImportDialog, {
      onImport, onClose: () => setOpen(false),
    }) : null);
}

/** onImport 的 mock：显式声明 (settings, file) 签名，否则 mock.calls[i][1] 类型越界。 */
function importSpy(impl?: (s: any, f: File) => unknown) {
  return vi.fn((s: any, f: File) => (impl ? impl(s, f) : undefined));
}

function pickFile(name = "box.step") {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["ISO-10303-21;\nENDSEC;\n"], name, { type: "application/step" });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

const btn = () => screen.getByRole("button", { name: /导入/ }) as HTMLButtonElement;

describe("StepImportDialog 点导入即关窗", () => {
  let alertSpy: any;
  beforeEach(() => { alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {}); });
  afterEach(() => { alertSpy.mockRestore(); });

  it("未选文件：提示且不关窗、不触发导入", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    // 初始「导入」禁用（未选文件）
    expect(btn().disabled).toBe(true);
    fireEvent.click(btn());
    expect(onImport).not.toHaveBeenCalled();
    expect(screen.getByText("OPEN")).toBeTruthy();
    expect(screen.getByText(/GEOUNED 导入设置/)).toBeTruthy();
  });

  it("选了文件：onImport 后立刻关窗（不等转换完成）", () => {
    // 永不 resolve —— 模拟"转换还在跑"
    const onImport = importSpy(() => new Promise<void>(() => {}));
    render(React.createElement(Harness, { onImport }));
    const file = pickFile("part.step");
    expect(btn().disabled).toBe(false);

    fireEvent.click(btn());

    // 同步即可断言：文件已交出去，窗口已关
    expect(onImport).toHaveBeenCalledTimes(1);
    expect(onImport.mock.calls[0][1]).toBe(file);
    expect(screen.getByText("CLOSED")).toBeTruthy();
    expect(screen.queryByText(/GEOUNED 导入设置/)).toBeNull();
  });

  it("设置项原样透传（材料名 / 密度 / 起始栅元与曲面号）", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.change(screen.getByDisplayValue("MAT"), { target: { value: "SS316" } });
    fireEvent.change(screen.getByDisplayValue("-1.0"), { target: { value: "-7.93" } });
    fireEvent.change(screen.getByDisplayValue("100"), { target: { value: "500" } });
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0]).toMatchObject({
      materialName: "SS316", density: "-7.93", startSurfNum: 500,
    });
  });
});

// ══════════════════════════════════════════════════════════════════════
// 4 个子标签页 + 子弹框（2026-09 新增）
//
// 锁死的契约：
//   1. 第 1 页「基本」= 原有 7 项去掉「生成真空栅元」+ **实体预分解**（用户指定）；
//      真空栅元切割三件套**在「常用调节」页**（用户二次指定：搬过去）；
//   2. **留空 = 该键不发送** = 用 GEOUNED 默认值（不是传 0）；
//   3. 下拉/开关/填空三类控件的中文释义都在子弹框里，点 `?` 可展开；
//   4. 子弹框颜色只走主题 CSS 变量（暗色主题近白字，4 套主题自动正确）；
//   5. 越界值拦住导入并跳到出错那一页，而不是把坏值发给后端；
//   6. 设置在**独立键**里持久化（开/关都记住），主界面「清空」不影响它。
// ══════════════════════════════════════════════════════════════════════

const fileInput = () => document.querySelector('input[type="file"]') as HTMLInputElement;
/** 页签文字后面会带改动计数（如「基本 ●1」），所以用前缀匹配。 */
const tab = (name: string) =>
  screen.getByRole("button", { name: new RegExp("^" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }) as HTMLButtonElement;
const val = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const toggle = (label: string) => screen.getByRole("button", { name: label }) as HTMLButtonElement;
const gotoCommon = () => fireEvent.click(tab("常用调节"));

describe("StepImportDialog 子标签页", () => {
  let alertSpy: any;
  beforeEach(() => { alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {}); });
  afterEach(() => { alertSpy.mockRestore(); });

  it("第 1 页 = 基本项（已按用户指示去掉「生成真空栅元」）+ 实体预分解；真空三件套不在这一页", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    // 原有 7 项（其中「生成真空栅元」已于 2026-10-10 按用户指示移除）
    ["材料名称", "密度", "TMP 温度", "起始栅元号", "起始曲面号"].forEach((l) => {
      expect(val(l)).toBeTruthy();
    });
    expect(toggle("复合体合并")).toBeTruthy();
    // 防它悄悄回来：默认不生成真空栅元 ⇒ 界面上不该再有这个开关
    expect(screen.queryByLabelText("生成真空栅元")).toBeNull();
    // 实体预分解（用户指定放基本页）：开关 + 每块面数上限
    expect(toggle("启用实体预分解").getAttribute("aria-pressed")).toBe("false");  // 默认关
    expect(val("每块面数上限")).toBeTruthy();
    // 真空三件套已搬到「常用调节」，本页不该有
    expect(screen.queryByLabelText("真空栅元最大曲面数")).toBeNull();
    expect(screen.queryByLabelText("栅元化简")).toBeNull();
  });

  it("真空栅元切割三件套在「常用调节」页（含组标题与两行灰字）", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    expect(val("真空栅元最大曲面数").placeholder).toBe("50");
    expect(val("真空补集括号上限").placeholder).toBe("30");
    expect(val("真空栅元最小尺寸").placeholder).toBe("200");
    expect(screen.getByText(/三项需同时超限才触发切割/)).toBeTruthy();
    expect(screen.getByText(/最多切 50 轮/)).toBeTruthy();
  });

  it("切页签显示对应参数，切回不丢已填内容", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.change(val("真空栅元最大曲面数"), { target: { value: "20" } });
    expect(val("栅元化简")).toBeTruthy();
    expect(val("样条曲面处理")).toBeTruthy();
    fireEvent.click(tab("基本"));
    expect(screen.queryByLabelText("真空栅元最大曲面数")).toBeNull();
    gotoCommon();
    expect(val("真空栅元最大曲面数").value).toBe("20");   // 切页不重置
  });

  it("页签下方的常驻提示说明「鼠标停在 ? 上可看释义」", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    expect(screen.getByText(/鼠标停在.*\?.*详细释义/)).toBeTruthy();
  });

  it("高危页默认折叠并给出红字警告，展开后才出现容差项", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.click(tab("高危 ⚠"));
    expect(screen.getByText(/⚠ 高危/)).toBeTruthy();
    expect(screen.queryByLabelText("通用距离容差")).toBeNull();     // 折叠中
    fireEvent.click(screen.getByRole("button", { name: /展开参数/ }));
    expect(val("通用距离容差")).toBeTruthy();
    expect(val("通用距离容差").placeholder).toBe("1e-4");
  });
});

describe("StepImportDialog 留空 = 不发送 = 用 GEOUNED 默认", () => {
  let alertSpy: any;
  beforeEach(() => { alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {}); });
  afterEach(() => { alertSpy.mockRestore(); });

  it("什么都不动直接导入：settings 里没有任何新参数键", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.click(btn());
    const s = onImport.mock.calls[0][0];
    ["maxSurf", "maxBracket", "minVoidSize", "simplify", "splineSurfaces",
     "voidMat", "skipSolids", "sortEnclosure", "debug", "distance", "forceNoOverlap",
    ].forEach((k) => expect(s[k]).toBeUndefined());
    // 基本项照旧始终发送（「生成真空栅元」已移除 ⇒ 本条不含它；后端按 _LEGACY_DEFAULTS 兜底为 False）
    expect(s).toMatchObject({
      materialName: "MAT", density: "-1.0", tmp: "",
      startCellNum: 1, startSurfNum: 100,
      compoundIsSingleCell: false,
    });
  });

  it("下拉选值后按字符串发送（simplify）", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.click(tab("常用调节"));
    fireEvent.change(val("栅元化简"), { target: { value: "voidfull" } });
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].simplify).toBe("voidfull");
  });

  it("点选按钮：默认「开」的项也能被显式设成「关」", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.click(tab("进阶与少见"));
    // 新版面分解算法 GEOUNED 默认是开
    expect(toggle("新版面分解算法").getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(toggle("新版面分解算法"));
    expect(toggle("新版面分解算法").getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].newSplitPlane).toBe(false);
  });

  it("数值填空按数字发送，不是字符串", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    gotoCommon();
    fireEvent.change(val("真空栅元最大曲面数"), { target: { value: "20" } });
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].maxSurf).toBe(20);
  });

  it("列表填空：中文逗号/换行混用也能解析成数组", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.click(tab("常用调节"));
    fireEvent.change(val("跳过实体编号"), { target: { value: "3，7\n12" } });
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].skipSolids).toEqual([3, 7, 12]);
  });

  it("真空栅元赋材料三格全填才发送", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.click(tab("常用调节"));
    fireEvent.change(val("真空栅元赋材料 材料号"), { target: { value: "100" } });
    fireEvent.change(val("真空栅元赋材料 密度"), { target: { value: "1.2e-3" } });
    fireEvent.change(val("真空栅元赋材料 描述"), { target: { value: "air" } });
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].voidMat).toEqual([100, 1.2e-3, "air"]);
  });

  it("「全部恢复默认」清掉所有自定义", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.change(val("真空栅元最大曲面数"), { target: { value: "20" } });
    expect(screen.getByText(/已自定义 1 项/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "全部恢复默认" }));
    expect(val("真空栅元最大曲面数").value).toBe("");
    expect(screen.getByText(/全部使用 GEOUNED 默认/)).toBeTruthy();
  });

  it("样条曲面处理：默认档显示「跳过该实体」，留空即跳过（不发送该键）", () => {
    // 用户指定：「遇到样条曲线了就跳过而不是终止或暂停」。本程序默认 = remove；
    // 留空（没动过）由 worker 的默认档决定，前端只负责把这个事实显示出来。
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();                       // 文件框只在「基本」页上，必须先选文件再切页
    gotoCommon();
    const sel = val("样条曲面处理") as unknown as HTMLSelectElement;
    const options = Array.from(sel.querySelectorAll("option"));
    expect(options[0].textContent).toBe("默认（跳过该实体）");
    expect(options.map((o) => o.value)).toEqual(["", "remove", "stop", "ignore"]);
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].splineSurfaces).toBeUndefined();
  });

  it("样条曲面处理：显式选的档位照旧发得出去（用户的选择不被默认值顶掉）", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    gotoCommon();
    fireEvent.change(val("样条曲面处理"), { target: { value: "stop" } });
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].splineSurfaces).toBe("stop");
  });
});

describe("StepImportDialog 校验与子弹框", () => {
  let alertSpy: any;
  beforeEach(() => { alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {}); });
  afterEach(() => { alertSpy.mockRestore(); });

  it("越界值拦住导入、给中文提示、并自动跳到出错那一页", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    gotoCommon();
    fireEvent.change(val("真空栅元最小尺寸"), { target: { value: "0" } });   // 必须 > 0
    fireEvent.click(btn());
    expect(onImport).not.toHaveBeenCalled();                 // 拦住了
    expect(screen.getByText("⚠ 应大于 0")).toBeTruthy();     // 中文提示
    expect(screen.getByText("OPEN")).toBeTruthy();           // 没关窗，让用户改
  });

  it("越界项在别的页时：点导入自动跳到那一页并显示提示", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    gotoCommon();
    fireEvent.change(val("真空栅元最小尺寸"), { target: { value: "0" } });
    fireEvent.click(tab("基本"));                            // 故意切走
    expect(screen.queryByLabelText("真空栅元最小尺寸")).toBeNull();
    fireEvent.click(btn());
    expect(onImport).not.toHaveBeenCalled();
    expect(val("真空栅元最小尺寸")).toBeTruthy();             // 自动跳回出错那一页
    expect(screen.getByText("⚠ 应大于 0")).toBeTruthy();
  });

  it("真空栅元赋材料只填一部分 → 拦住并提示三格全填或全空", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.click(tab("常用调节"));
    fireEvent.change(val("真空栅元赋材料 材料号"), { target: { value: "100" } });
    fireEvent.click(btn());
    expect(onImport).not.toHaveBeenCalled();
    expect(screen.getByText("⚠ 三格要么全填、要么全空")).toBeTruthy();
  });

  it("点 ? 弹出子弹框：中文释义 + 英文字段名", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.click(screen.getByRole("button", { name: "真空栅元最大曲面数 的详细说明" }));
    expect(screen.getByText("【真空栅元最大曲面数】")).toBeTruthy();
    expect(screen.getByText(/对半切开/)).toBeTruthy();                       // 中文作用说明
    expect(screen.getByText(/曲面数与括号数同时超限/)).toBeTruthy();          // 中文注意
    expect(screen.getByText(/Settings\.maxSurf/)).toBeTruthy();              // 保留英文字段名
  });

  it("点选按钮的子弹框写清开/关各是什么", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.click(tab("常用调节"));
    fireEvent.click(screen.getByRole("button", { name: "真空栅元排序 的详细说明" }));
    expect(screen.getByText(/● 开 —— 实体栅元与其配套的真空栅元相邻排列/)).toBeTruthy();
    expect(screen.getByText(/○ 关 —— 实体集中在前、真空集中在后/)).toBeTruthy();
  });

  it("下拉的子弹框带逐选项释义", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.click(tab("常用调节"));
    fireEvent.click(screen.getByRole("button", { name: "栅元化简 的详细说明" }));
    // 选项名在下拉与子弹框里各出现一次
    expect(screen.getAllByText("仅真空（最优·慢）").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/耗时可达 5 倍以上/)).toBeTruthy();
  });

  it("子弹框颜色只走主题变量（暗色主题近白字，4 套主题自动正确）", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.click(screen.getByRole("button", { name: "真空栅元最大曲面数 的详细说明" }));
    const bubble = screen.getByText("【真空栅元最大曲面数】").parentElement as HTMLElement;
    // 正文色/底色必须是主题变量 —— 硬编码色值会在浅色/多巴胺主题下不可读
    expect(bubble.style.color).toBe("var(--text-primary)");
    expect(bubble.style.background).toContain("var(--bg-surface)");
    expect(bubble.style.borderLeft).toContain("var(--accent-glow)");
    expect(bubble.style.position).toBe("fixed");
    expect(Number(bubble.style.zIndex)).toBeGreaterThan(1000);   // 高于对话框(1000)
    // 子弹框自身零硬编码颜色（FloatingDialog 的阴影不在此子树内）
    expect(/#[0-9a-fA-F]{6}\b/.test(bubble.outerHTML)).toBe(false);
    expect(/rgba?\(/.test(bubble.outerHTML)).toBe(false);
  });

  it("高危参数的子弹框带红字警告（红只做图标/色条，文字仍是 text-primary）", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.click(tab("高危 ⚠"));
    fireEvent.click(screen.getByRole("button", { name: /展开参数/ }));
    fireEvent.click(screen.getByRole("button", { name: "通用距离容差 的详细说明" }));
    expect(screen.getByText(/⚠ 改动会直接影响/)).toBeTruthy();
    const bubble = screen.getByText("【通用距离容差】").parentElement as HTMLElement;
    expect(bubble.style.color).toBe("var(--text-primary)");
    expect(bubble.style.borderLeft).toContain("var(--red)");
  });

  // ── 触发器 = 只有 ? 图标（用户 2026-09-23 两次指定：
  //    「鼠标移开时就立即消失」+「鼠标停在问号上的时候再出弹窗」）──
  /** 触发器：参数右侧的 ? 图标（唯一入口） */
  const q = (label: string) => screen.getByRole("button", { name: `${label} 的详细说明` }) as HTMLButtonElement;
  const tip = (label: string) => screen.queryByText(`【${label}】`);

  it("鼠标停在 ? 上：200ms 后才出现（防止划过就闪）", async () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.mouseEnter(q("真空栅元最大曲面数"));
    expect(tip("真空栅元最大曲面数")).toBeNull();                     // 立刻不该出现
    await waitFor(() => expect(tip("真空栅元最大曲面数")).toBeTruthy(), { timeout: 1500 });
  });

  it("鼠标移开 ? ：子弹框立即消失，不留缓冲", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.mouseEnter(q("真空栅元最大曲面数"));
    fireEvent.click(q("真空栅元最大曲面数"));
    expect(tip("真空栅元最大曲面数")).toBeTruthy();

    fireEvent.mouseLeave(q("真空栅元最大曲面数"));

    // 同步断言：若还留着老的 140ms 缓冲，这里此刻仍能找到子弹框
    expect(tip("真空栅元最大曲面数")).toBeNull();
  });

  it("划过输入框 / 下拉 / 点选按钮都**不**弹窗（触发器只有 ?）", async () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.mouseEnter(val("起始栅元号"));
    fireEvent.mouseEnter(toggle("复合体合并"));
    fireEvent.mouseEnter(val("每块面数上限"));
    // 等过 200ms 的出现延时，确认不是"延迟出现"而是"根本不出现"
    await new Promise((r) => setTimeout(r, 320));
    expect(tip("起始栅元号")).toBeNull();
    expect(tip("复合体合并")).toBeNull();
    expect(tip("每块面数上限")).toBeNull();
  });

  it("切页签会立即收起子弹框", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.click(q("真空栅元最大曲面数"));
    expect(tip("真空栅元最大曲面数")).toBeTruthy();
    fireEvent.click(tab("基本"));
    expect(tip("真空栅元最大曲面数")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════
// 实体预分解 + 设置持久化（2026-09-23 新增，2026-09-24 由 MCCAD 换成 FreeCAD 自切）
//
// 用户要求：「在基本页里加个按钮，是否启用切割」+
//           「保留用户设置的内容，开启和关闭都记忆，就算程序主页面那个清空点了也不要改」+
//           「考虑到 freecad 性能，每块面数控制在 30 以下」。
// ══════════════════════════════════════════════════════════════════════

describe("StepImportDialog 实体预分解开关", () => {
  let alertSpy: any;
  beforeEach(() => { alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {}); });
  afterEach(() => { alertSpy.mockRestore(); });

  it("默认关闭，且默认不发送这两个键（留空语义）", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    expect(toggle("启用实体预分解").getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(btn());
    const s = onImport.mock.calls[0][0];
    expect(s.cutSolids).toBeUndefined();
    expect(s.cutDegree).toBeUndefined();
  });

  it("打开开关 → cutSolids=true；再关掉 → 显式 false（两种状态都发得出去）", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.click(toggle("启用实体预分解"));
    expect(toggle("启用实体预分解").getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].cutSolids).toBe(true);

    // 重新打开对话框（上一轮点导入后已关窗）→ 再点一下 = 显式关
    render(React.createElement(Harness, { onImport }));
    pickFile();
    expect(toggle("启用实体预分解").getAttribute("aria-pressed")).toBe("true");   // 记忆住了
    fireEvent.click(toggle("启用实体预分解"));
    expect(toggle("启用实体预分解").getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(btn());
    expect(onImport.mock.calls[1][0].cutSolids).toBe(false);
  });

  it("每块面数上限可以自己键入数字（用户指定：不再只有三档下拉）", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    // 是文本框（不是 select）：用户可以填任意面数
    expect(val("每块面数上限").tagName).toBe("INPUT");
    expect(val("每块面数上限").placeholder).toBe("30");
    fireEvent.change(val("每块面数上限"), { target: { value: "12" } });
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].cutDegree).toBe(12);     // 发数字，不是 "12"
  });

  it("面数上限填 0 / 小数 / 非数字 → 拦住导入并给中文提示", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.change(val("每块面数上限"), { target: { value: "0" } });
    fireEvent.click(btn());
    expect(onImport).not.toHaveBeenCalled();
    expect(screen.getByText("⚠ 应为不小于 1 的整数")).toBeTruthy();

    fireEvent.change(val("每块面数上限"), { target: { value: "12.5" } });
    fireEvent.click(btn());
    expect(onImport).not.toHaveBeenCalled();

    fireEvent.change(val("每块面数上限"), { target: { value: "abc" } });
    fireEvent.click(btn());
    expect(onImport).not.toHaveBeenCalled();
    expect(screen.getByText(/请输入数字/)).toBeTruthy();
  });

  it("旧版三档下拉记住的值会被迁移成面数（老用户开窗不被自己的记忆拦住）", () => {
    localStorage.setItem("mcnp_step_import_v1",
      JSON.stringify({ version: 1, vals: { cutSolids: true, cutDegree: "fine" } }));
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    expect(val("每块面数上限").value).toBe("20");            // fine → 20 面
    pickFile();
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0].cutDegree).toBe(20);
  });

  it("子弹框写清作用、实测效果与代价（不再提 MCCAD）", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.click(screen.getByRole("button", { name: "启用实体预分解 的详细说明" }));
    expect(screen.getByText("【启用实体预分解】")).toBeTruthy();
    expect(screen.getByText(/独立成一个栅元/)).toBeTruthy();            // 组提示用词不同，取子弹框独有措辞
    expect(screen.getByText(/上限 30 面时切成 18 块/)).toBeTruthy();     // 实测数字
    expect(screen.getByText(/实体体积比 1.0000000/)).toBeTruthy();
    expect(screen.getByText(/自动跳过并在结果提示里说明原因/)).toBeTruthy();  // 失败不中断导入
    expect(screen.queryByText(/MCCAD/)).toBeNull();                     // 外部程序已彻底移除
  });

  it("面数上限是「结果指标」而不是「块数输入」—— 文案要说清并给出切不动的情形", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.click(screen.getByRole("button", { name: "每块面数上限 的详细说明" }));
    expect(screen.getByText("【每块面数上限】")).toBeTruthy();
    expect(screen.getByText(/块数是被算出来的结果，不是你填的/)).toBeTruthy();
    expect(screen.getByText(/2 块切不动/)).toBeTruthy();                 // 较细档的诚实提示
    expect(screen.getByText(/不假装达标/)).toBeTruthy();
  });
});

describe("StepImportDialog 设置持久化（独立键，清空工作区不影响）", () => {
  let alertSpy: any;
  beforeEach(() => { alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {}); });
  afterEach(() => { alertSpy.mockRestore(); });

  const PREF_KEY = "mcnp_step_import_v1";

  it("关掉对话框再开：改过的参数还在（含预分解开关的「开」）", () => {
    const first = render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.change(val("真空栅元最大曲面数"), { target: { value: "20" } });
    fireEvent.click(tab("基本"));
    fireEvent.click(toggle("启用实体预分解"));
    expect(JSON.parse(localStorage.getItem(PREF_KEY)!).vals)
      .toMatchObject({ maxSurf: "20", cutSolids: true });
    first.unmount();

    // 重新挂载 = 关掉对话框再打开
    render(React.createElement(Harness, { onImport: importSpy() }));
    expect(toggle("启用实体预分解").getAttribute("aria-pressed")).toBe("true");
    gotoCommon();
    expect(val("真空栅元最大曲面数").value).toBe("20");
  });

  it("「关」也记得住：下次打开仍是关（不是回到「没动过」）", () => {
    const first = render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.click(toggle("启用实体预分解"));   // 开
    fireEvent.click(toggle("启用实体预分解"));   // 关
    expect(JSON.parse(localStorage.getItem(PREF_KEY)!).vals.cutSolids).toBe(false);
    first.unmount();

    render(React.createElement(Harness, { onImport: importSpy() }));
    expect(toggle("启用实体预分解").getAttribute("aria-pressed")).toBe("false");
    // 显式 false 仍是"发送 false"，与"没动过（不发送）"不同 —— 语义要保住
    expect(JSON.parse(localStorage.getItem(PREF_KEY)!).vals).toHaveProperty("cutSolids", false);
  });

  it("材料名 / 密度 / TMP **不**记忆（用户指定：它们不是偏好）", () => {
    const first = render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.change(val("材料名称"), { target: { value: "SS316" } });
    fireEvent.change(val("密度"), { target: { value: "-7.93" } });
    const stored = JSON.parse(localStorage.getItem(PREF_KEY)!).vals;
    expect(stored).not.toHaveProperty("materialName");
    expect(stored).not.toHaveProperty("density");
    expect(stored).not.toHaveProperty("tmp");
    first.unmount();

    render(React.createElement(Harness, { onImport: importSpy() }));
    expect(val("材料名称").value).toBe("MAT");       // 回到固定初值
    expect(val("密度").value).toBe("-1.0");
  });

  it("「全部恢复默认」同时清掉记忆（否则重开又回来）", () => {
    const first = render(React.createElement(Harness, { onImport: importSpy() }));
    gotoCommon();
    fireEvent.change(val("真空栅元最大曲面数"), { target: { value: "20" } });
    fireEvent.click(tab("基本"));
    fireEvent.click(toggle("启用实体预分解"));
    fireEvent.click(screen.getByRole("button", { name: "全部恢复默认" }));
    expect(JSON.parse(localStorage.getItem(PREF_KEY)!).vals).toEqual({});
    first.unmount();

    render(React.createElement(Harness, { onImport: importSpy() }));
    expect(toggle("启用实体预分解").getAttribute("aria-pressed")).toBe("false");
    gotoCommon();
    expect(val("真空栅元最大曲面数").value).toBe("");
  });

  it("主界面「清空工作区」只删工作区键 ⇒ 导入设置不受影响", () => {
    render(React.createElement(Harness, { onImport: importSpy() }));
    fireEvent.click(toggle("启用实体预分解"));
    localStorage.setItem("mcnp_workspace_v1", "工作区内容");

    // 复刻 App.tsx handleClear（只删工作区键；不是 localStorage.clear()）
    localStorage.removeItem("mcnp_workspace_v1");

    expect(JSON.parse(localStorage.getItem(PREF_KEY)!).vals.cutSolids).toBe(true);
  });
});

