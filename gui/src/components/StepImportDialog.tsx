/**
 * StepImportDialog — GEOUNED STEP 导入设置对话框（4 个子标签页）
 *
 *   基本 / 常用调节 / 进阶与少见 / 高危 ⚠
 *
 * 四条不可回退的设计约定：
 *
 * 1. **参数元数据单一来源**：PARAM_SPECS 一张表同时驱动「中文标签、控件类型、
 *    placeholder 默认值、悬停释义（子弹框）、前端校验、所属页」。改文案只改这一处，
 *    不会出现「控件在这儿、说明在那儿」的漂移。
 *
 * 2. **留空 = 该键不发送 = 用 GEOUNED 自己的默认值**（不是传 0）。只有用户真动过的
 *    项才进入 settings。好处：留空天然安全；将来 GEOUNED 升版改了默认值，也不会被
 *    本程序钉死；`newSplitPlane`/`scaleUp`/`cellSummaryFile` 这类**默认是「开」**的项，
 *    按钮初态就显示「开」，用户不动就不发送。
 *
 * 3. **颜色一律走主题 CSS 变量，禁止硬编码**：4 套主题（夜之城·霓虹 / 青空·石松蓝 /
 *    多巴胺 / 护眼·棕褐）+ `.preview3d-root` 作用域自动正确。暗色主题下正文
 *    `--text-primary` = #F1F1F9（近白）。
 *    ⚠ 特别注意 `--accent-glow` 在多巴胺主题是 #FF8FAB（浅粉），压在
 *    `--dialog-bg` = rgba(255,222,240,0.96) 上对比度约 1.6:1 —— **绝不可作为文字颜色**，
 *    只用作装饰色条。同理 `--red` 在多巴胺是粉色，也不作正文色：红只出现在
 *    ⚠ 图标 / 左侧色条 / 12% 淡红底上，文字仍是 `--text-primary`。
 *
 * 4. **子弹框必须 portal 到 `getAppPortalRoot()`**（`#root` 内的 `#app-portal-root`）。
 *    挂 `document.body` 会脱离 `#root { zoom: var(--app-scale) }`，位置与字号与控件错位
 *    （见 utils/appScale.tsx:42）。主题变量不会丢（`data-theme` 设在 `<html>`，变量沿
 *    DOM 继承），丢的是缩放。
 */
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import FloatingDialog from "./FloatingDialog";
import { getAppPortalRoot, useAppScale } from "../utils/appScale";
import { loadPrefs, savePrefs } from "../utils/stepImportPrefs";
import { openPreview3D } from "../utils/windows";
import { apiUrl } from "../utils/api";
import Preview3D from "./Preview3D";

// ─────────────────────────── 类型 ───────────────────────────

type PageId = "basic" | "common" | "advanced" | "risk";

/** 控件形态。留空语义对所有 kind 一致：不发送该键。 */
type Kind =
  | "text"     // 自由文本
  | "int"      // 整数（原有项：起始栅元/曲面号）
  | "number"   // 数值，支持 1e-4 写法
  | "select"   // 下拉
  | "toggle"   // 点选按钮（开/关）
  | "triple"   // 三格填空（真空栅元赋材料）
  | "list";    // 逗号/换行分隔的列表

interface TipOption { label: string; desc: string }

/** 子弹框内容。全部中文；英文字段名只出现在末尾的「对应 GEOUNED 参数」行。 */
interface TipSpec {
  role: string;
  blank?: string;
  tune?: string;
  open?: string;
  shut?: string;
  options?: TipOption[];
  warn?: string;
  note?: string;
  /** 官方未文档化：释义来自源码行为，如实标注 */
  undocumented?: string;
}

interface ParamSpec {
  key: string;
  label: string;
  /** 对应 GEOUNED 参数（英文，保留给用户查官方文档） */
  geouned: string;
  kind: Kind;
  /** GEOUNED 默认：填空的 placeholder / 点选按钮的初态 / 下拉首项文案 */
  def?: string | boolean;
  unit?: string;
  // 注意：**没有 page 字段** —— 页归属由 PAGE_LAYOUT 单一来源派生（见 pageOf）
  tip: TipSpec;
  /** 原始 7 项：始终发送（保持既有行为与既有测试） */
  always?: boolean;
  /**
   * 本程序自用 / 流水线开关：**不跨 GEOUNED 参数映射那道 seam**。
   * 契约测试据此把它们排除在「前端键集 == 后端 GEOUNED 表」之外。
   * 用途：材料名/密度/TMP（本程序填料）、实体预分解开关与面数上限（传 payload 的 cut 段）。
   */
  local?: boolean;
  /** 原始项的初始值 */
  initial?: string | boolean;
  choices?: { value: string; label: string }[];
  check?: (raw: string) => string | null;
  /** triple 的三个子键 */
  subKeys?: [string, string, string];
  /** list 元素是否必须是整数 */
  intList?: boolean;
  /** select 的可选项 */
  placeholder?: string;
}

// ─────────────────── 参数元数据（单一来源） ───────────────────

const V = {
  txt: { fontSize: 10, fontWeight: 500, color: "var(--text-tertiary)" } as React.CSSProperties,
  inp: {
    height: 30, padding: "0 8px", borderRadius: 6, border: "1px solid var(--border-glass)",
    background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 11, outline: "none",
    width: "100%", boxSizing: "border-box", fontFamily: "inherit",
  } as React.CSSProperties,
};

const numeric = (ok: (n: number) => boolean, msg: string) => (raw: string) => {
  const t = raw.trim();
  if (!t) return null;
  const n = Number(t);
  if (!Number.isFinite(n)) return "请输入数字（支持 1e-4 这种写法）";
  return ok(n) ? null : msg;
};

const PARAM_SPECS: ParamSpec[] = [
  // ───────── 第 1 页：基本（原有 7 项，位置与初值都不动） ─────────
  {
    key: "materialName", label: "材料名称", local: true, geouned: "（本程序使用，不传给 GEOUNED）",
    kind: "text", always: true, initial: "MAT",
    tip: {
      role: "导入成功后回填到栅元卡上的材料号名称，同时写进输出文件的标题行。",
      note: "这里填的是材料号（如 MAT、1、M1），密度由右边一栏给出。",
    },
  },
  {
    key: "density", label: "密度", unit: "g/cm³", local: true, geouned: "（本程序使用，不传给 GEOUNED）",
    kind: "text", always: true, initial: "-1.0",
    tip: {
      role: "回填到栅元卡的材料密度。负数表示质量密度，正数表示原子密度。",
      note: "GEOUNED 本身不写密度，这一项由本程序在导入结果里补上。",
    },
  },
  {
    key: "tmp", label: "TMP 温度", unit: "MeV", local: true, geouned: "（本程序使用，不传给 GEOUNED）",
    kind: "text", always: true, initial: "",
    tip: {
      role: "给导入的栅元统一加 TMP 温度卡。",
      blank: "留空 = 不写 TMP 卡",
      note: "只有需要按温度做自由气体修正时才填。",
    },
  },
  {
    key: "compoundIsSingleCell", label: "复合体合并", geouned: "Settings.compSolids",
    kind: "toggle", always: true, initial: false, def: false,
    tip: {
      role: "把 STEP 里的复合实体（compound solid）当成一个整体，只产出一个 MCNP 栅元。",
      open: "● 开 —— 复合实体合并为单栅元",
      shut: "○ 关 —— 复合实体拆开，每个子实体一个栅元（默认）",
      note: "SpaceClaim 导出的 STEP 里，本来分开的实体可能被 FreeCAD 读成一个复合实体 —— 这时应设为「关」。",
    },
  },
  {
    key: "startCellNum", label: "起始栅元号", geouned: "Settings.startCell",
    kind: "int", always: true, initial: "1",
    tip: { role: "GEOUNED 生成的第一个栅元使用的编号，之后的栅元依次递增。", blank: "默认从 1 开始" },
  },
  {
    key: "startSurfNum", label: "起始曲面号", geouned: "Settings.startSurf",
    kind: "int", always: true, initial: "100",
    tip: { role: "GEOUNED 生成的第一个曲面使用的编号，之后的曲面依次递增。", blank: "默认从 1 开始" },
  },

  // ───────── 第 1 页：真空栅元切割 ─────────
  {
    key: "maxSurf", label: "真空栅元最大曲面数", geouned: "Settings.maxSurf",
    kind: "number", def: "50",
    check: numeric((n) => n >= 1, "应为不小于 1 的整数"),
    tip: {
      role: "真空盒子里累计的曲面总数超过这个值（且括号数也超过上限）时，GEOUNED 会把这个盒子沿最长边对半切开，变成两个更小的真空栅元。",
      blank: "留空 = 50（GEOUNED 默认）",
      tune: "调小 → 切得更细，真空栅元变多；调大 → 切得更粗，真空栅元变少但单个栅元的表达式更复杂。",
      note: "GEOUNED 的判定是「曲面数与括号数同时超限」，只调这一项可能仍不触发切割；切割最多进行 50 轮（内建，不可调）。",
    },
  },
  {
    key: "maxBracket", label: "真空补集括号上限", geouned: "Settings.maxBracket",
    kind: "number", def: "30",
    check: numeric((n) => n >= 1, "应为不小于 1 的整数"),
    tip: {
      role: "真空盒子里累计的布尔括号数超过这个值（且曲面数也超过上限）时，盒子才会被切开。",
      blank: "留空 = 30（GEOUNED 默认）",
      tune: "与「真空栅元最大曲面数」配套使用 —— 两个都要降下来，切割才会变得更细。",
      note: "括号数越多，单个真空栅元的表达式越长，MCNP 粒子追踪越慢。",
    },
  },
  {
    key: "minVoidSize", label: "真空栅元最小尺寸", unit: "mm", geouned: "Settings.minVoidSize",
    kind: "number", def: "200",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: {
      role: "盒子还能不能再切的「尺寸地板」：若某一维的一半小于这个值，该维就不能再切；三维都不能切时，这个盒子直接生成真空栅元。",
      blank: "留空 = 200（GEOUNED 默认）",
      tune: "调小 → 允许切出更小的真空栅元（更细）；调大 → 尽早停止切割（更粗）。",
      note: "它只决定「还能不能切」，不决定「切出来多大」—— GEOUNED 是按最长边对半二分，实际边长可能远大于这个值。",
    },
  },

  // ───────── 第 1 页：基本（实体预分解） ─────────
  {
    key: "cutSolids", label: "启用实体预分解", local: true,
    geouned: "（本程序流水线，不传给 GEOUNED）",
    kind: "toggle", def: false,
    tip: {
      role: "开启后，先用 FreeCAD 把实体按「每块面数上限」预分解成多个块，再交给 GEOUNED 转换 —— 每个块独立成一个栅元。",
      open: "● 开 —— 实体先被切开：栅元数变多，但每个栅元的面数大幅下降",
      shut: "○ 关 —— 直接把原始实体交给 GEOUNED（默认）",
      blank: "默认 = 关",
      tune: "实测（274 m³ 厂房模型 / 3 个实体 / 原面数 27、41、202）：上限 30 面时切成 18 块，最终 47 个栅元，实体栅元最大面数 146 → 25，实体体积比 1.0000000",
      note: "代价：栅元数变多，MCNP 粒子追踪变慢 —— 这是纯粹的取舍，没有「更细更好」。分解失败时会自动跳过并在结果提示里说明原因，不会中断导入。",
    },
  },
  {
    key: "cadUpAxis", label: "STEP 上轴", local: true,
    geouned: "（本程序流水线，不传给 GEOUNED）",
    kind: "select", def: "Z 朝上（不旋转）",
    choices: [
      { value: "Z", label: "Z 朝上 —— FreeCAD / UG(NX) / CATIA / Creo 类（不旋转）" },
      { value: "Y", label: "Y 朝上 —— SolidWorks / Inventor / Maya 类（绕 X 转 90°）" },
    ],
    tip: {
      role: "源 CAD 的默认「上」方向。STEP 文件本身没有这个字段，无法自动判断，只能你告诉程序：选 Y 时，导入会先绕 X 转 +90°（CAD 的 +Y 变成 MCNP 的 +Z），导出 STEP 时按逆变换转出去，两个方向互为逆、往返自洽。",
      options: [
        { label: "Z 朝上", desc: "FreeCAD / UG(NX) / CATIA / Creo / Solid Edge / AutoCAD / 3ds Max —— 与 MCNP 一致，不旋转（默认）" },
        { label: "Y 朝上", desc: "SolidWorks / Inventor / Maya / Unity —— 不选它，模型在你的 CAD 里会躺倒 90°" },
      ],
      blank: "留空 = Z 朝上（不旋转，与旧行为一致）",
      note: "选错不会报错，只是方向不对（看着躺倒或转了头）—— 换个选项重导即可；结果提示里会写明本次按哪种约定转过。",
    },
  },
  {
    key: "cadAzimuthDeg", label: "绕上轴方位角", local: true,
    geouned: "（本程序流水线，不传给 GEOUNED）",
    kind: "select", def: "0°（不转）",
    choices: [
      { value: "0", label: "0°（不转）" },
      { value: "90", label: "90°" },
      { value: "180", label: "180°" },
      { value: "270", label: "270°" },
    ],
    tip: {
      role: "把上轴摆正之后，再绕上轴（MCNP 的 Z）转一个整直角 —— 用于「立起来了但转过头/朝向不对」的情况。上轴本身不受它影响。",
      blank: "留空 = 0°",
      note: "四个离散值：0 / 90 / 180 / 270。",
    },
  },
  {
    key: "cadOrigin", label: "原点口径", local: true,
    geouned: "（本程序流水线，不传给 GEOUNED）",
    kind: "select", def: "按原本建模（不平移）",
    choices: [
      { value: "keep", label: "按原本建模 —— CAD 坐标 = MCNP 坐标（不平移，默认）" },
      { value: "center", label: "体心归零 —— 包围盒中心搬到原点" },
      { value: "bottom", label: "坐在底面上 —— 水平居中、底在 z=0 平面上" },
    ],
    tip: {
      role: "决定这套几何的原点落在哪。三个口径见下；预览/3D 窗口显示的永远是**真实坐标**，不做归一化，所以选完能直接看到效果。",
      options: [
        { label: "按原本建模（keep）", desc: "不平移。CAD 里的坐标就是 MCNP 里的坐标 —— 逐字对应、往返自洽，也便于拿 CAD 标注核对卡（默认）" },
        { label: "体心归零（center）", desc: "包围盒中心搬到原点。MCNP 里坐标小、对称，适合新建独立模型" },
        { label: "坐在底面上（bottom）", desc: "水平两轴居中、竖直方向从 0 起（导入到 MCNP 即 z=0）。符合 CAD「坐在原点平面上」的习惯" },
      ],
      blank: "留空 = 按原本建模（不平移）",
      note: "体心/底面都要先量一次整体包围盒 —— 若含墓区等巨型真空实体，中心会被它们带偏；这种卡建议先只导入实体，或就用默认的按原本建模。",
    },
  },
  {
    key: "tangentFix", label: "相切退化自动修复", local: true,
    geouned: "（本程序流水线，不传给 GEOUNED）",
    kind: "toggle", def: true,
    tip: {
      role: "当某个零件的外圆柱面与一个**同轴、同半径**的球面正好相切时，GEOUNED 会丢掉一个定界面，产出的栅元沿轴向无限延伸（体积暴涨、与邻居重叠，MCNP 会丢粒子）。开启后，导入前把那个球面沿径向**外移 0.1%**，破除这个退化。",
      open: "● 开 —— 只在检测到「同轴同半径的球/柱相切」时动手，其余几何一字不改；做了什么会写进导入结果（默认）",
      shut: "○ 关 —— 原样交给 GEOUNED（这类零件会得到体积错误且互相重叠的栅元）",
      blank: "默认 = 开",
      tune: "实测（用户文件 筒子1.STEP / 6 实体）：出问题的恰好是唯一两个含这种相切的实体 —— 栅元 3 体积 28268 cm³ 而 CAD 实体 3645（大 7.8 倍），栅元 4 为 29424 而实体 3630（大 8.1 倍），且 3∩4 重叠 7275 cm³、3∩5 重叠 35.4 cm³。修复后：栅元 3 = 3645.1、栅元 4 = 3629.5（与实体吻合），error 级重叠清零，每个实体体积只变化 0.0215%。受控实验：球半径与柱半径相等 ⇒ 丢边界；差 0.1%（49.95 或 50.05）⇒ 转换正确。",
      note: "代价极小但确实动了 CAD 几何 0.1%（50 mm 球 → 外移 0.05 mm）。因此有三条纪律：只在退化相切时动手、单个实体体积变化超 0.5% 就放弃、把改动如实写进结果提示。不接受就关掉。",
    },
  },
  {
    key: "cutDegree", label: "每块面数上限", local: true,
    geouned: "（本程序流水线，不传给 GEOUNED）",
    // 用户 2026-10-08：「切分面数用户可以自己键入」—— 三档下拉（50/30/20）改成自由数字框。
    // 为什么 kind 是 number 而不是 int：buildSettings 对 number 发**数字**、对 int 发字符串，
    // 而后端 degree_to_face_limit 两者都认；发数字语义更准（"这是面数，不是编号"）。
    kind: "number", def: "30",
    check: numeric((n) => Number.isInteger(n) && n >= 1, "应为不小于 1 的整数"),
    tip: {
      role: "切分的收敛目标：每块最多允许多少个面。自己填数字（切分逐块判断还要不要再切一刀）。",
      blank: "留空 = 30 面",
      tune: "常用值：50（较粗，块数最少）/ 30（默认）/ 20（较细，单块最简单）。实测 274 m³ 厂房模型（3 个实体）：上限 50 → 9 块、上限 30 → 18 块、上限 20 → 41 块（其中 2 块切不动）。",
      note: "块数是被算出来的结果，不是你填的 —— 同一个上限在不同模型上的块数完全不同。填得比 4 还小基本无意义（切不出那么简单的块），切不到的块会在结果提示里如实报出来（不假装达标）。只在「启用实体预分解」打开时才有意义。",
    },
  },

  // ───────── 第 2 页：常用调节 ─────────
  {
    key: "simplify", label: "栅元化简", geouned: "Settings.simplify",
    kind: "select", def: "不化简",
    choices: [
      { value: "no", label: "不化简" },
      { value: "void", label: "仅真空（快）" },
      { value: "voidfull", label: "仅真空（最优·慢）" },
      { value: "full", label: "全部化简" },
    ],
    tip: {
      role: "整理每个栅元的布尔表达式，消掉冗余项。",
      options: [
        { label: "不化简", desc: "原样输出，最快，表达式最冗长" },
        { label: "仅真空（快）", desc: "只整理真空栅元，算法较快" },
        { label: "仅真空（最优·慢）", desc: "只整理真空栅元，用最优算法，耗时可达 5 倍以上" },
        { label: "全部化简", desc: "实体与真空都整理，最慢" },
      ],
      blank: "留空 = 不化简（GEOUNED 默认）",
      // 用户 2026-10-08 报「GEOUNED 生成的文件写进栅元卡时括号被吞了」——
      // 实测（他的真实 STEP，同一套曲面号）**括号的有无是 GEOUNED 自己的写法，由这一档决定**：
      //   不化简 → 紧凑式 `-103 -100 101:104 105 …`（MCNP 里 ':' 优先级最低，等价且合法）
      //   全部化简 → 重建表达式并显式加括号 `(-100:105:-106) 104 -103 -102 101`
      // 两种写法实体体积完全一致（41862.640）⇒ 几何等价；本程序对产物括号逐字保留。
      note: "化简会重建栅元表达式，因此括号写法跟着变（实测：同一模型化简后并集分支被显式加括号）。"
        + "两种写法的几何等价（实体体积一致），本程序对 GEOUNED 产物的括号是逐字保留的。",
    },
  },
  {
    key: "splineSurfaces", label: "样条曲面处理", geouned: "load_step_file.spline_surfaces",
    // 用户 2026-10-08：「遇到样条曲线了就跳过而不是终止或暂停，并报告」——
    // 留空（= 没动过）时**本程序**按「跳过该实体」发（worker 的默认档），
    // 而不是 GEOUNED 自己的默认档「停止转换」（它直接 exit()，用户只看到一句
    // "GEOUNED 终止: None"）。前端这里只负责把「默认 = 跳过」显示出来。
    kind: "select", def: "跳过该实体",
    choices: [
      { value: "remove", label: "跳过该实体（推荐）" },
      { value: "stop", label: "停止转换（整份导入报错退出）" },
      { value: "ignore", label: "强行翻译（可能出错）" },
    ],
    tip: {
      role: "STEP 里含样条（NURBS / 旋转面 / 拉伸面）曲面时怎么办 —— GEOUNED 无法把样条面写成 MCNP 曲面。默认「跳过该实体」：含样条面的实体不参与转换，其余实体照常转换，导入**不会被中断**。",
      options: [
        { label: "跳过该实体（本程序默认）", desc: "含样条面的实体整块不转换，其余照常；被跳过的实体序号与曲面类型会写在导入结果提示里" },
        { label: "停止转换", desc: "一遇到含样条面的实体就终止整份导入并报错（GEOUNED 自己的默认档）" },
        { label: "强行翻译（可能出错）", desc: "把样条面并入转换，几何可能有误 —— 事后务必核对体积与重叠" },
      ],
      blank: "留空 = 跳过含样条面的实体（本程序默认；GEOUNED 原生的默认是「停止转换」）",
      note: "若整份 STEP 的实体**全部**含样条面，跳过之后就没有可转换的东西了 —— 这时导入会失败并写明原因（不会给你一份空卡）。被跳过的实体序号从 0 开始，与「跳过实体编号」是同一口径。",
    },
  },
  {
    key: "voidMat", label: "真空栅元赋材料", geouned: "Settings.voidMat",
    kind: "triple", subKeys: ["voidMatNum", "voidMatRho", "voidMatDesc"],
    tip: {
      role: "给自动生成的真空栅元指定材料，而不是留成真空（例如把空隙填成空气）。三格分别填：材料号、密度、描述文字。",
      blank: "三格全空 = 不赋材料（保持真空）",
      warn: "三格必须「全填」或「全空」：只填一部分无法提交。",
      note: "材料号是整数，密度是数字（g/cm³），描述随便写、只作为注释。",
    },
  },
  {
    key: "skipSolids", label: "跳过实体编号", geouned: "load_step_file.skip_solids",
    kind: "list", intList: true,
    tip: {
      role: "按序号跳过不参与转换的实体。序号从 0 开始，对应 GEOUNED 读入 CAD 的顺序。",
      blank: "留空 = 不跳过任何实体",
      tune: "多个序号用逗号或换行分隔，例如 3, 7, 12",
      note: "跳错了会丢几何。建议先勾「输出调试文件」确认序号再跳。",
    },
  },
  {
    key: "sortEnclosure", label: "真空栅元排序", geouned: "Settings.sort_enclosure",
    kind: "toggle", def: false,
    tip: {
      role: "控制有 enclosure（包壳）时，真空栅元在输出文件里的排列位置。",
      open: "● 开 —— 实体栅元与其配套的真空栅元相邻排列，按 CAD 树就近成组",
      shut: "○ 关 —— 实体集中在前、真空集中在后",
      blank: "默认 = 关（GEOUNED 默认）",
    },
  },
  {
    key: "debug", label: "输出调试文件", geouned: "Settings.debug",
    kind: "toggle", def: false,
    tip: {
      role: "转换时额外输出排查用的中间文件：每个实体拆解后的 STEP 文件 + GEOUNED 日志。",
      open: "● 开 —— 出调试文件，便于定位某个实体为什么转不出来",
      shut: "○ 关 —— 只输出最终结果",
      blank: "默认 = 关（GEOUNED 默认）",
      note: "大装配体下会生成很多文件、并明显变慢，只在排查时开。",
    },
  },

  // ───────── 第 3 页：进阶与少见 ─────────
  {
    key: "forceNoOverlap", label: "强制无重叠栅元", geouned: "Options.forceNoOverlap",
    kind: "toggle", def: false,
    tip: {
      role: "把相邻栅元的定义做差，强制栅元之间不重叠。",
      open: "● 开 —— 相邻栅元互相扣除，几何严格无重叠",
      shut: "○ 关 —— 各实体独立定义（默认）",
      note: "MCNP 里几何重叠是致命错误。开了之后输出更啰嗦、转换更慢，但能根治「几何重叠」类报错。",
    },
  },
  {
    key: "facets", label: "三角面片几何模式", geouned: "Options.Facets",
    kind: "toggle", def: false,
    tip: {
      role: "当模型完全由三角平面片构成时（网格化 / STL 风味的 CAD），改用专门的转换模块。",
      open: "● 开 —— 走三角面片专用转换模块",
      shut: "○ 关 —— 走常规 B-Rep 转换（默认）",
      note: "普通实体别开；只有整个模型都是三角面片时才有效。",
    },
  },
  {
    key: "forceCylinder", label: "未闭合圆环面改用圆柱", geouned: "Options.forceCylinder",
    kind: "toggle", def: false,
    tip: {
      role: "实体定义里出现未闭合的圆环面（torus）时，用圆柱代替圆锥作为辅助面。",
      open: "● 开 —— 未闭合圆环面用圆柱做辅助面",
      shut: "○ 关 —— 用圆锥做辅助面（默认）",
      note: "圆环面转换报错时可以试试打开。",
    },
  },
  {
    key: "newSplitPlane", label: "新版面分解算法", geouned: "Options.newSplitPlane",
    kind: "toggle", def: true,
    tip: {
      role: "选择实体分解时的切面顺序算法。",
      open: "● 开 —— 新版：把所有平行面归成一组，先切平行面最多的那组（默认）",
      shut: "○ 关 —— 旧版：先切垂直于 X/Y/Z 轴的面，再切其他面",
      note: "几何分解失败时，换一版算法有时能过。",
    },
  },
  {
    key: "scaleUp", label: "容差过小时自动放大", geouned: "Options.scaleUp",
    kind: "toggle", def: true,
    tip: {
      role: "模糊容差掉到 1e-12 以下时自动放大，避免浮点精度导致布尔运算失败。",
      open: "● 开 —— 自动放大（默认）",
      shut: "○ 关 —— 不放大",
      note: "一般不要关。",
    },
  },
  {
    key: "splitTolerance", label: "分解模糊容差", geouned: "Options.splitTolerance",
    kind: "number", def: "0",
    check: numeric((n) => n >= 0, "不能为负数"),
    tip: {
      role: "实体分解时 FreeCAD 切片函数（BOPTools.SplitAPI.slice）使用的模糊容差，单位 mm。",
      blank: "留空 = 0（GEOUNED 默认）",
      tune: "几何切不开、实体分解失败时从这里加，例如 1e-4",
      note: "太大可能把本该分开的面粘在一起。",
    },
  },
  {
    key: "enlargeBox", label: "简化时包围盒外扩", unit: "mm", geouned: "Options.enlargeBox",
    kind: "number", def: "2",
    check: numeric((n) => n >= 0, "不能为负数"),
    tip: {
      role: "评估真空定义的约束表时，把包围盒向外扩这个尺寸，避免临界面被误判。",
      blank: "留空 = 2（GEOUNED 默认）",
      tune: "简化结果丢面、错判时适当加大",
    },
  },
  {
    key: "prnt3PPlane", label: "平面用三点坐标输出", geouned: "Options.prnt3PPlane",
    kind: "toggle", def: false,
    tip: {
      role: "一般平面（P）的写法：用三点坐标式，还是用 A B C D 系数式。",
      open: "● 开 —— P 卡写成 x1 y1 z1 x2 y2 z2 x3 y3 z3",
      shut: "○ 关 —— P 卡写成 A B C D 系数式（默认）",
      note: "两种写法数值单位一致（cm），本程序也都能解析；只是输出文本形态不同，做历史对比时注意。",
    },
  },
  {
    key: "ucard", label: "输出宇宙卡号", geouned: "export_csg.UCARD",
    kind: "number", def: "",
    check: numeric((n) => Number.isInteger(n) && n >= 0, "应为不小于 0 的整数"),
    tip: {
      role: "给所有栅元写 UNIVERSE 卡，指定宇宙号。",
      blank: "留空 = 不写宇宙卡",
      tune: "需要把导入的几何整体塞进某个 universe 做填充（FILL）时填这里，例如 10",
      note: "填 0 等于不写。",
    },
  },
  {
    key: "volSDEF", label: "随机体积校核（SDEF）", geouned: "export_csg.volSDEF",
    kind: "toggle", def: false,
    tip: {
      role: "额外写 SDEF 定义与体积计数卡，用蒙特卡罗方法核对栅元体积。",
      open: "● 开 —— 输出 SDEF + 体积计数卡",
      shut: "○ 关 —— 不输出（默认）",
      note: "只在核对体积时开。",
    },
  },
  {
    key: "cellSummaryFile", label: "栅元汇总文件", geouned: "export_csg.cellSummaryFile",
    kind: "toggle", def: true,
    tip: {
      role: "额外输出一个记录各 CAD 栅元转换信息的汇总文件。",
      open: "● 开 —— 生成汇总文件（GEOUNED 默认）",
      shut: "○ 关 —— 不生成",
      note: "本程序不读这个文件，不需要的话可以直接关掉，少写一个文件。",
    },
  },
  {
    key: "cellCommentFile", label: "栅元注释文件", geouned: "export_csg.cellCommentFile",
    kind: "toggle", def: false,
    tip: {
      role: "额外输出一个把每个 CAD 栅元与其注释对应起来的文件。",
      open: "● 开 —— 生成注释对照文件",
      shut: "○ 关 —— 不生成（默认）",
    },
  },
  {
    key: "dummyMat", label: "假材料卡", geouned: "export_csg.dummyMat",
    kind: "toggle", def: false,
    tip: {
      role: "为模型里出现的每个材料号写一张占位材料卡（MX 1001 1），让文件能直接跑起来。",
      open: "● 开 —— 写占位材料卡",
      shut: "○ 关 —— 不写（默认）",
      note: "本程序会按你的材料表自己生成材料卡，一般不用开。",
    },
  },
  {
    key: "delLastNumber", label: "删除注释末尾数字", geouned: "Options.delLastNumber",
    kind: "toggle", def: false,
    tip: {
      role: "从 CAD 实体名生成的注释里，把末尾的数字去掉。",
      open: "● 开 —— 去掉注释末尾数字",
      shut: "○ 关 —— 保留（默认）",
      note: "只影响注释文本，不影响几何。",
    },
  },

  // ───────── 第 4 页：高危 ─────────
  {
    key: "distance", label: "通用距离容差", geouned: "Tolerances.distance",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: {
      warn: "改动会直接影响「两个面 / 两根轴是否算同一个」的判定：改错会把两个面粘成一个，或把一个面劈成两个。",
      role: "判断两个几何对象之间的距离多近才被认为重合或等价，单位 mm。",
      blank: "留空 = 1e-4（GEOUNED 默认）",
      tune: "只在几何出现重叠 / 缝隙类报错时微调",
      note: "改完必须核对体积与重叠。",
    },
  },
  {
    key: "angle", label: "通用角度容差", geouned: "Tolerances.angle",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: {
      warn: "改动会直接影响方向是否算平行的判定，可能把两根轴并成一根。",
      role: "判断两个方向是否平行的角度阈值，单位弧度。",
      blank: "留空 = 1e-4（GEOUNED 默认）",
    },
  },
  {
    key: "minArea", label: "最小面面积", geouned: "Tolerances.min_area",
    kind: "number", def: "1e-2",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: {
      warn: "调太大会把真实的小面也丢掉，几何出现孔洞。",
      role: "小于这个面积的面片，在栅元定义里被忽略，单位 cm²。",
      blank: "留空 = 1e-2（GEOUNED 默认）",
      tune: "CAD 里有大量碎面导致转换报错时，可以适当加大",
    },
  },
  {
    key: "relativeTol", label: "相对容差模式", geouned: "Tolerances.relativeTol",
    kind: "toggle", def: false,
    tip: {
      warn: "高危：容差判定改用相对值，影响面比单项容差更广。除非明确知道自己在做什么，否则保持关闭。",
      role: "把容差判定从绝对值改为相对值。",
      open: "● 开 —— 使用相对容差",
      shut: "○ 关 —— 使用绝对容差（默认）",
    },
  },
  {
    key: "relativePrecision", label: "相对精度", geouned: "Tolerances.relativePrecision",
    kind: "number", def: "1e-6",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: {
      warn: "高危：只在「相对容差模式」打开时才有意义。",
      role: "相对容差模式下使用的精度值。",
      blank: "留空 = 1e-6（GEOUNED 默认）",
    },
  },
  {
    key: "tolValue", label: "单值比较容差", geouned: "Tolerances.value",
    kind: "number", def: "1e-6",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: {
      warn: "高危：影响单值相等判定（例如两个半径是否相等）。",
      role: "单个数值比较时使用的容差。",
      blank: "留空 = 1e-6（GEOUNED 默认）",
    },
  },
  {
    key: "plnDistance", label: "平面距离容差", geouned: "Tolerances.pln_distance",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响平面（PX/PY/PZ/P）。", role: "判断两个平面是否重合的距离阈值。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "plnAngle", label: "平面角度容差", geouned: "Tolerances.pln_angle",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响平面。", role: "判断两个平面是否平行的角度阈值，单位弧度。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "cylDistance", label: "圆柱距离容差", geouned: "Tolerances.cyl_distance",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响圆柱／圆锥面。", role: "判断两个圆柱面是否重合（半径与轴心）的距离阈值。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "cylAngle", label: "圆柱角度容差", geouned: "Tolerances.cyl_angle",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响圆柱／圆锥面。", role: "判断两根圆柱轴是否平行的角度阈值。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "sphDistance", label: "球距离容差", geouned: "Tolerances.sph_distance",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响球面。", role: "判断两个球面是否重合（半径与球心）的距离阈值。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "kneDistance", label: "圆锥距离容差", geouned: "Tolerances.kne_distance",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响圆锥面。", role: "判断两个圆锥面是否重合（锥顶位置）的距离阈值。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "kneAngle", label: "圆锥角度容差", geouned: "Tolerances.kne_angle",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响圆锥面。", role: "判断两个圆锥的半锥角／轴是否相同的角度阈值。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "torDistance", label: "圆环距离容差", geouned: "Tolerances.tor_distance",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响圆环面（torus）。", role: "判断两个圆环面是否重合（主／次半径与圆心）的距离阈值。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "torAngle", label: "圆环角度容差", geouned: "Tolerances.tor_angle",
    kind: "number", def: "1e-4",
    check: numeric((n) => n > 0, "应大于 0"),
    tip: { warn: "高危：只影响圆环面。", role: "判断两个圆环面的轴是否相同的角度阈值。", blank: "留空 = 1e-4（GEOUNED 默认）" },
  },
  {
    key: "nPlaneReverse", label: "平行面切割阈值", geouned: "Options.nPlaneReverse",
    kind: "number", def: "0",
    check: numeric((n) => Number.isInteger(n), "应为整数"),
    tip: {
      warn: "高危：影响实体分解的切面顺序，改错会让分解结果变形。",
      role: "决定「用平行面切割」是否被优先执行的阈值。",
      blank: "留空 = 0（GEOUNED 默认）",
      undocumented: "GEOUNED 官方未文档化，本释义来自源码行为（GEOUNED/utils/data_classes.py:25 与 decompose 模块）。",
    },
  },
  {
    key: "voidExclude", label: "真空排除实体", geouned: "Settings.voidExclude",
    kind: "list",
    tip: {
      warn: "高危：排除错了会留下未定义的空隙，MCNP 会报几何错误。",
      role: "指定不参与自动真空生成的实体（按 CAD 树中的标签匹配）。",
      blank: "留空 = 不排除任何实体",
      tune: "多个标签用逗号或换行分隔",
      undocumented: "GEOUNED 官方未文档化（源码仅标注 see issue 87），本释义来自源码行为（GEOUNED/core.py:505）。",
    },
  },
];

const SPEC_BY_KEY: Record<string, ParamSpec> = Object.fromEntries(
  PARAM_SPECS.map((p) => [p.key, p]),
);

// ─────────────────── 页面布局（顺序 / 分组 / 提示） ───────────────────
//
// **页归属的唯一来源就是这里**（键出现在哪个页的 row 里，它就属于哪一页）。
// 元数据表刻意不再写 `page`：同一件事写两处，搬家时必漏一处 ——
// 2026-09-23 把真空三件套从「基本」搬到「常用调节」时正是这样漏的
// （校验报错跳到错的页、改动计数记到错的页签）。
type Block =
  | { t: "file" }
  | { t: "stepPreview" }
  | { t: "row"; keys: string[] }
  | { t: "group"; title: string; hint?: string }
  | { t: "note"; text: string }
  | { t: "banner" };

const PAGES: { id: PageId; label: string }[] = [
  { id: "basic", label: "基本" },
  { id: "common", label: "常用调节" },
  { id: "advanced", label: "进阶与少见" },
  { id: "risk", label: "高危 ⚠" },
];

const PAGE_LAYOUT: Record<PageId, Block[]> = {
  basic: [
    { t: "file" },
    { t: "row", keys: ["materialName", "density", "tmp"] },
    { t: "row", keys: ["compoundIsSingleCell"] },
    { t: "row", keys: ["startCellNum", "startSurfNum"] },
    // 真空栅元切割三件套**已搬到「常用调节」页**；这里只留实体预分解
    { t: "group", title: "实体预分解", hint: "先用 FreeCAD 把实体按「每块面数上限」切开，再交给 GEOUNED 转换：每个块独立成栅元，单栅元面数大幅下降；代价是栅元数变多" },
    { t: "row", keys: ["cutSolids", "cutDegree"] },
    { t: "group", title: "转换退化修复", hint: "GEOUNED 对某些退化几何会丢定界面（栅元体积暴涨并与邻居重叠）。这里的开关在导入前先把退化破除，做了什么都写在结果提示里" },
    { t: "row", keys: ["tangentFix"] },
    { t: "group", title: "坐标约定（STEP 上轴）", hint: "STEP 文件**不带上轴信息**（ISO 10303 只有坐标值+单位），差别来自源软件默认坐标系。本程序与 MCNP 都是 Z 朝上，所以源文件是 Y 朝上的软件（SolidWorks/Inventor/Maya）导出的，就要选 Y 才会「立着」进来" },
    { t: "row", keys: ["cadUpAxis", "cadAzimuthDeg"] },
    { t: "group", title: "原点口径", hint: "三个选项：按原本建模（不平移，默认）/ 体心归零 / 坐在底面上。预览与 3D 窗口始终显示真实坐标，不做归一化，选完直接看得出效果" },
    { t: "row", keys: ["cadOrigin"] },
    { t: "stepPreview" },
  ],
  common: [
    { t: "group", title: "真空栅元切割", hint: "三项需同时超限才触发切割；数值越小，真空栅元切得越细" },
    { t: "row", keys: ["maxSurf", "maxBracket", "minVoidSize"] },
    { t: "note", text: "GEOUNED 内建最多切 50 轮，不可调。" },
    { t: "row", keys: ["simplify", "splineSurfaces"] },
    { t: "row", keys: ["sortEnclosure", "debug"] },
    { t: "row", keys: ["voidMat"] },
    { t: "row", keys: ["skipSolids"] },
  ],
  advanced: [
    { t: "row", keys: ["forceNoOverlap", "facets"] },
    { t: "row", keys: ["forceCylinder", "newSplitPlane"] },
    { t: "row", keys: ["scaleUp", "splitTolerance"] },
    { t: "row", keys: ["enlargeBox", "prnt3PPlane"] },
    { t: "row", keys: ["ucard", "volSDEF"] },
    { t: "row", keys: ["cellSummaryFile", "cellCommentFile"] },
    { t: "row", keys: ["dummyMat", "delLastNumber"] },
  ],
  risk: [
    { t: "banner" },
    { t: "row", keys: ["distance", "angle", "minArea"] },
    { t: "row", keys: ["relativeTol", "relativePrecision", "tolValue"] },
    { t: "row", keys: ["plnDistance", "plnAngle"] },
    { t: "row", keys: ["cylDistance", "cylAngle"] },
    { t: "row", keys: ["sphDistance"] },
    { t: "row", keys: ["kneDistance", "kneAngle"] },
    { t: "row", keys: ["torDistance", "torAngle"] },
    { t: "group", title: "未文档化参数", hint: "GEOUNED 官方无说明，释义来自源码行为，仅供排查" },
    { t: "row", keys: ["nPlaneReverse", "voidExclude"] },
  ],
};

/** key → 所属页，**由 PAGE_LAYOUT 派生**（唯一来源；见上面的注释） */
const PAGE_OF_KEY: Record<string, PageId> = (() => {
  const map: Record<string, PageId> = {};
  for (const pg of PAGES) {
    for (const b of PAGE_LAYOUT[pg.id]) {
      if (b.t === "row") for (const k of b.keys) map[k] = pg.id;
    }
  }
  return map;
})();

/** 取某键所属页；不在任何页上（如文件选择框）时回落到第 1 页 */
const pageOf = (key: string): PageId => PAGE_OF_KEY[key] ?? "basic";

// ─────────────────── 子弹框 ───────────────────

const TIP_WIDTH = 340;

interface Anchor { left: number; right: number; top: number }

function rectOf(el: HTMLElement): Anchor {
  const r = el.getBoundingClientRect();
  return { left: r.left, right: r.right, top: r.top };
}

const tipLine = { marginTop: 4 } as React.CSSProperties;

/**
 * 子弹框。因为「鼠标移开触发器即消失」，指针永远不会到达这里，
 * 所以它**不接** mouseenter/mouseleave —— 没有"移进去保住"的接力逻辑。
 */
function TipBubble({ spec, anchor }: { spec: ParamSpec; anchor: Anchor }) {
  const scale = useAppScale();
  const ref = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number }>({ left: -9999, top: -9999 });

  // 先渲染到屏外量真实尺寸，再决定左右翻转与上下夹取（避免越出窗口）
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof window === "undefined") return;
    const r = el.getBoundingClientRect();
    const w = r.width / (scale || 1);
    const h = r.height / (scale || 1);
    const vw = (window.innerWidth || 0) / (scale || 1);
    const vh = (window.innerHeight || 0) / (scale || 1);
    let left = anchor.right / (scale || 1) + 10;
    if (left + w > vw - 8) left = anchor.left / (scale || 1) - w - 10;   // 右侧放不下 → 翻到左侧
    if (left < 8) left = 8;
    let top = anchor.top / (scale || 1);
    if (top + h > vh - 8) top = Math.max(8, vh - h - 8);
    setPos({ left, top });
  }, [spec.key, anchor, scale]);

  const t = spec.tip;
  const body = React.createElement("div", {
    ref,
    style: {
      position: "fixed", left: pos.left, top: pos.top, width: TIP_WIDTH,
      maxWidth: "calc(100vw - 24px)", maxHeight: "70vh", overflow: "auto",
      zIndex: 1300,
      // 颜色全部走主题变量：4 套主题自动正确。装饰色条用 accent-glow（不作文字色）。
      background: "var(--bg-surface)",
      color: "var(--text-primary)",
      border: "1px solid var(--border-glass)",
      borderLeft: "3px solid " + (t.warn ? "var(--red)" : "var(--accent-glow)"),
      borderRadius: 10, padding: "10px 12px",
      // 阴影也走主题变量：--dialog-overlay 在 4 套主题里深浅不同
      boxShadow: "0 8px 32px var(--dialog-overlay)",
      fontSize: 11, lineHeight: 1.7,
    } as React.CSSProperties,
  },
    // 标题：文字用 text-primary，不用 accent-glow（多巴胺主题下粉压粉不可读）
    React.createElement("div", {
      style: { fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 2 },
    }, `【${spec.label}】`),
    t.warn ? React.createElement("div", {
      style: {
        color: "var(--text-primary)",
        background: "color-mix(in srgb, var(--red) 12%, transparent)",
        borderLeft: "3px solid var(--red)", borderRadius: 4,
        padding: "5px 8px", margin: "4px 0",
      },
    }, "⚠ " + t.warn) : null,
    React.createElement("div", { style: tipLine },
      React.createElement("span", { style: { color: "var(--text-secondary)" } }, "作用："),
      t.role),
    t.open ? React.createElement("div", { style: tipLine }, t.open) : null,
    t.shut ? React.createElement("div", { style: tipLine }, t.shut) : null,
    t.options ? React.createElement("div", { style: { marginTop: 4 } },
      t.options.map((o, i) => React.createElement("div", { key: i, style: { display: "flex", gap: 6 } },
        React.createElement("span", { style: { color: "var(--accent-glow)", flexShrink: 0 } }, "·"),
        React.createElement("span", null,
          React.createElement("span", { style: { color: "var(--text-primary)" } }, o.label),
          React.createElement("span", { style: { color: "var(--text-secondary)" } }, " —— " + o.desc)),
      ))) : null,
    t.blank ? React.createElement("div", { style: tipLine },
      React.createElement("span", { style: { color: "var(--text-secondary)" } }, "默认："),
      t.blank) : null,
    t.tune ? React.createElement("div", { style: tipLine },
      React.createElement("span", { style: { color: "var(--text-secondary)" } }, "怎么调："),
      t.tune) : null,
    t.note ? React.createElement("div", { style: tipLine },
      React.createElement("span", { style: { color: "var(--text-secondary)" } }, "注意："),
      t.note) : null,
    t.undocumented ? React.createElement("div", { style: { ...tipLine, color: "var(--text-secondary)" } }, "※ " + t.undocumented) : null,
    React.createElement("div", {
      style: {
        marginTop: 8, paddingTop: 6, borderTop: "1px solid var(--border-glass)",
        color: "var(--text-tertiary)", fontFamily: "Consolas, monospace", fontSize: 10,
        wordBreak: "break-all",
      },
    }, "对应 GEOUNED 参数：" + spec.geouned),
  );

  return createPortal(body, getAppPortalRoot());
}

// ─────────────────── 主对话框 ───────────────────

export interface StepSettings {
  materialName: string;
  density: string;
  tmp: string;
  /* ⚠️ `voidGeneration` 已按用户指示（2026-10-10「把那个生成真空栅元的按钮去掉，默认不生成真空栅元」）
     从界面**移除**：本程序现在**不发送**该键 ⇒ 后端 `_LEGACY_DEFAULTS` 兜底为 `voidGen=False`
     ⇒ GEOUNED 只输出实体栅元（不再生成 enclosure/void/墓区那一堆盒子）。
     要恢复"生成真空栅元"，把 PARAM_SPECS 里的 toggle 与 `basic` 页的 row 加回来即可。 */
  startCellNum: number;
  startSurfNum: number;
  compoundIsSingleCell: boolean;
  [key: string]: unknown;
}

interface Props {
  onImport: (settings: StepSettings, file: File) => void;
  onClose: () => void;
}

type Val = string | boolean | undefined;

function isUntouched(v: Val): boolean {
  return v === undefined || v === "";
}

/** triple 参数的三个子键（恒返回三元组，避免 undefined 下标） */
function subKeysOf(p: ParamSpec): [string, string, string] {
  return p.subKeys ?? ["", "", ""];
}

/** 全默认状态：只含 `always` 初值 ⇒ 所有"可记忆项"都回到**没动过**（三态里的第一态） */
function pristineState(): Record<string, Val> {
  const init: Record<string, Val> = {};
  for (const p of PARAM_SPECS) if (p.always) init[p.key] = p.initial;
  return init;
}

/**
 * 旧版「每块面数上限」是三档下拉（coarse/medium/fine），现在是自由数字框。
 * 不迁移的话，老用户下次打开对话框会看到输入框里躺着 "coarse" —— 一按导入就被
 * 校验拦住（"请输入数字"），而他还什么都没改。迁移 = 把旧档位换成它对应的面数。
 */
const CUT_DEGREE_LEGACY: Record<string, string> = { coarse: "50", medium: "30", fine: "20" };

function migrate(key: string, v: Val): Val {
  if (key !== "cutDegree" || typeof v !== "string") return v;
  return CUT_DEGREE_LEGACY[v.trim().toLowerCase()] ?? v;
}

/**
 * 初始值 = 全默认状态 + **上次记住的设置**。
 *
 * 只接受元数据表里存在、且不是 `always` 的键 —— 材料名/密度/TMP 是"本次导入的内容"
 * 而不是偏好，按用户要求**不记忆**；存储被篡改时也靠这道过滤兜住。
 */
function initialState(): Record<string, Val> {
  const init = pristineState();
  for (const [k, v] of Object.entries(loadPrefs())) {
    const spec = SPEC_BY_KEY[k];
    if (spec && !spec.always) init[k] = migrate(k, v);
  }
  return init;
}

/** 要落盘的部分：除 `always`（本次导入的内容，不记忆）外，动过的项全记住 */
function persistable(vals: Record<string, Val>): Record<string, string | boolean> {
  const out: Record<string, string | boolean> = {};
  for (const p of PARAM_SPECS) {
    if (p.always) continue;
    const v = vals[p.key];
    if (v === undefined || v === "") continue;   // 没动过 → 不落盘（三态语义的根）
    out[p.key] = v;
  }
  return out;
}

export default function StepImportDialog({ onImport, onClose }: Props) {
  const [file, setFile] = useState<File | null>(null);
  /**
   * STEP 方向预览（用户 2026-10-08：「给个按钮，点一下先用 STEP 生成预览，方便选上轴」）。
   * 点按钮才生成；此后改「上轴/方位/原点」会立即重取 —— 后端把镶嵌结果按文件 sha1 缓存，
   * 每次切换只做旋转/平移矩阵（毫秒级），所以边看边切不卡。
   */
  const [pvOpen, setPvOpen] = useState(false);
  const [pvBusy, setPvBusy] = useState(false);
  const [pv, setPv] = useState<{ stl: string; bbox: number[][]; notes?: string[]; token: string; windowed: boolean } | null>(null);
  const [pvErr, setPvErr] = useState("");
  const [page, setPage] = useState<PageId>("basic");
  const [riskOpen, setRiskOpen] = useState(false);
  const [vals, setVals] = useState<Record<string, Val>>(initialState);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [tip, setTip] = useState<{ spec: ParamSpec; anchor: Anchor } | null>(null);

  const tipTimer = useRef<number | null>(null);
  const clearTimer = () => {
    if (tipTimer.current !== null) { window.clearTimeout(tipTimer.current); tipTimer.current = null; }
  };
  const openTip = (spec: ParamSpec, el: HTMLElement) => {
    clearTimer();
    const anchor = rectOf(el);
    tipTimer.current = window.setTimeout(() => setTip({ spec, anchor }), 200);
  };
  const openTipNow = (spec: ParamSpec, el: HTMLElement) => {
    clearTimer();
    setTip({ spec, anchor: rectOf(el) });
  };
  // 鼠标移开触发器 → **立即**消失（用户 2026-09-23 指定：不要留缓冲）。
  // 因此子弹框只作"悬停即读"用，不做"指针移进去继续读"的接力。
  const closeTip = () => { clearTimer(); setTip(null); };

  const setVal = (k: string, v: Val) => {
    setVals((prev) => ({ ...prev, [k]: v }));
    setErrors((prev) => { if (!prev[k]) return prev; const n = { ...prev }; delete n[k]; return n; });
  };

  // 记住设置（独立 localStorage 键，主界面「清空」只删工作区键，不影响这里）。
  // 用 effect 而不是在 setVal 里写：① 不在 state 更新器里做副作用；
  // ② 「全部恢复默认」把值清回未动状态后，这里自然落盘成 {} ——
  //    即"恢复默认"同时也是唯一的清除入口，不需要额外的 clear 路径。
  useEffect(() => { savePrefs(persistable(vals)); }, [vals]);

  /** 该控件是否被用户动过（决定「默认」角标与「已自定义」计数） */
  const touched = (p: ParamSpec): boolean => {
    const v = vals[p.key];
    if (p.always) return String(v) !== String(p.initial);
    if (p.kind === "triple") return subKeysOf(p).some((k) => !isUntouched(vals[k]));
    return !isUntouched(v);
  };

  const pageChangedCount = (id: PageId) =>
    PARAM_SPECS.filter((p) => PAGE_OF_KEY[p.key] === id && touched(p)).length;
  const changedCount = PARAM_SPECS.filter(touched).length;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  /** 全量校验：返回第一个出错的 (页, 键, 中文提示) */
  const validate = (): { page: PageId; key: string; msg: string } | null => {
    for (const p of PARAM_SPECS) {
      if (p.kind === "triple") {
        const [a, b, c] = subKeysOf(p);
        const parts = [vals[a], vals[b], vals[c]].map((v) => (typeof v === "string" ? v.trim() : ""));
        const filled = parts.filter((s) => s !== "").length;
        if (filled !== 0 && filled !== 3) {
          return { page: pageOf(p.key), key: p.key, msg: "三格要么全填、要么全空" };
        }
        if (filled === 3) {
          if (!Number.isInteger(Number(parts[0]))) return { page: pageOf(p.key), key: p.key, msg: "材料号应为整数" };
          if (!Number.isFinite(Number(parts[1]))) return { page: pageOf(p.key), key: p.key, msg: "密度应为数字" };
        }
        continue;
      }
      const v = vals[p.key];
      if (typeof v !== "string" || v.trim() === "") continue;
      if (p.kind === "list" && p.intList) {
        const bad = v.split(/[,，;；\n]/).map((s) => s.trim()).filter(Boolean).some((s) => !Number.isInteger(Number(s)));
        if (bad) return { page: pageOf(p.key), key: p.key, msg: "请填整数序号，用逗号或换行分隔" };
        continue;
      }
      if (p.check) {
        const msg = p.check(v);
        if (msg) return { page: pageOf(p.key), key: p.key, msg };
      }
    }
    return null;
  };

  const buildSettings = (): StepSettings => {
    const s: Record<string, unknown> = {};
    for (const p of PARAM_SPECS) {
      const v = vals[p.key];
      if (p.always) {
        // 原有 7 项：始终发送，保持既有行为
        if (p.kind === "toggle") s[p.key] = Boolean(v);
        else if (p.kind === "int") s[p.key] = parseInt(String(v), 10) || 1;
        else s[p.key] = String(v ?? "");
        continue;
      }
      if (p.kind === "toggle") {
        if (typeof v === "boolean") s[p.key] = v;      // 未点过 = 不发送 = 用 GEOUNED 默认
        continue;
      }
      if (p.kind === "triple") {
        const [a, b, c] = subKeysOf(p);
        const parts = [vals[a], vals[b], vals[c]].map((x) => (typeof x === "string" ? x.trim() : ""));
        if (parts.every((x) => x !== "")) {
          s[p.key] = [parseInt(parts[0], 10), Number(parts[1]), parts[2]];
        }
        continue;
      }
      if (typeof v !== "string" || v.trim() === "") continue;
      const raw = v.trim();
      if (p.kind === "number") s[p.key] = Number(raw);
      else if (p.kind === "list") {
        const items = raw.split(/[,，;；\n]/).map((x) => x.trim()).filter(Boolean);
        if (items.length) s[p.key] = p.intList ? items.map((x) => parseInt(x, 10)) : items;
      } else s[p.key] = raw;
    }
    return s as StepSettings;
  };

  const handleImport = () => {
    if (!file) { alert("请先选择 STEP 文件"); return; }
    const bad = validate();
    if (bad) {
      setErrors({ [bad.key]: bad.msg });
      setPage(bad.page);
      if (bad.page === "risk") setRiskOpen(true);
      return;                                   // 拦住，不关窗：让用户改
    }
    // 点「导入」立刻自我关闭：转换在后台跑（GEOUNED 小件 3~4 s、真实 CAD 装配体
    // 分钟级），窗口不该杵在那里等；结果由父级 alert 告知。
    onImport(buildSettings(), file);
    onClose();
  };

  // ── 控件渲染 ──

  const renderControl = (p: ParamSpec) => {
    const v = vals[p.key];
    const err = errors[p.key];
    const base = { ...V.inp, ...(err ? { borderColor: "var(--red)" } : {}) } as React.CSSProperties;

    if (p.kind === "toggle") {
      const def = Boolean(p.def);
      const on = p.always ? Boolean(v) : (typeof v === "boolean" ? v : def);
      const isTouched = p.always ? touched(p) : typeof v === "boolean";
      return React.createElement("button", {
        type: "button",
        "aria-pressed": on,
        "aria-label": p.label,
        onClick: () => setVal(p.key, !on),
        style: {
          height: 30, padding: "0 10px", borderRadius: 6, cursor: "pointer",
          fontSize: 11, fontFamily: "inherit", display: "flex", alignItems: "center", gap: 6,
          background: on ? "color-mix(in srgb, var(--accent) 18%, transparent)" : "transparent",
          border: "1px solid " + (on ? "var(--accent)" : "var(--border-glass)"),
          color: isTouched ? "var(--text-primary)" : "var(--text-secondary)",
        } as React.CSSProperties,
      },
        React.createElement("span", { style: { color: on ? "var(--accent)" : "var(--text-tertiary)" } }, on ? "●" : "○"),
        on ? "开" : "关",
      );
    }

    if (p.kind === "select") {
      // 复用 .form-select：它带 color-scheme 与 option 的主题化配色（global.css:151）
      return React.createElement("select", {
        className: "form-select",
        "aria-label": p.label,
        style: { ...base, height: 30 }, value: typeof v === "string" ? v : "",
        onChange: (e: React.ChangeEvent<HTMLSelectElement>) => setVal(p.key, e.target.value),
      },
        React.createElement("option", { value: "" }, `默认（${p.def}）`),
        ...(p.choices || []).map((c) => React.createElement("option", { key: c.value, value: c.value }, c.label)),
      );
    }

    if (p.kind === "triple") {
      const [a, b, c] = subKeysOf(p);
      const subs: { k: string; ph: string }[] = [
        { k: a, ph: "材料号" }, { k: b, ph: "密度" }, { k: c, ph: "描述" },
      ];
      return React.createElement("div", { style: { display: "flex", gap: 6 } },
        subs.map((s) => React.createElement("input", {
          key: s.k, style: base, value: String(vals[s.k] ?? ""), placeholder: s.ph,
          "aria-label": `${p.label} ${s.ph}`,
          onChange: (e: React.ChangeEvent<HTMLInputElement>) => setVal(s.k, e.target.value),
        })),
      );
    }

    if (p.kind === "list") {
      // 必须用 textarea：<input> 会把换行吞掉（浏览器行为），而释义里承诺了「逗号或换行分隔」
      return React.createElement("textarea", {
        style: {
          ...base, height: "auto", minHeight: 30, padding: "5px 8px",
          fontFamily: "Consolas, monospace", lineHeight: 1.5, resize: "vertical",
        },
        rows: 2,
        "aria-label": p.label,
        value: typeof v === "string" ? v : "",
        placeholder: p.intList ? "如 3, 7, 12" : "逗号或换行分隔",
        onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => setVal(p.key, e.target.value),
      });
    }

    const inputType = p.kind === "int" ? "number" : "text";
    return React.createElement("input", {
      type: inputType,
      ...(p.kind === "number" ? { inputMode: "decimal" as const } : {}),
      style: base,
      "aria-label": p.label,
      value: typeof v === "string" ? v : "",
      placeholder: p.def !== undefined && p.def !== "" ? String(p.def) : "留空",
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => setVal(p.key, e.target.value),
    });
  };

  const renderField = (p: ParamSpec) => {
    const err = errors[p.key];
    return React.createElement("div", {
      key: p.key,
      // 触发器只有右边的 ? 图标（用户 2026-09-23 指定）：鼠标划过输入框/下拉/按钮都不弹窗，
      // 免得填写过程中被释义挡住。
      style: { flex: 1, minWidth: 0 },
    },
      React.createElement("div", {
        style: { display: "flex", alignItems: "center", gap: 5, marginBottom: 3 },
      },
        React.createElement("label", { style: V.txt }, p.label + (p.unit ? `（${p.unit}）` : "")),
        !p.always && !touched(p)
          ? React.createElement("span", {
              style: { fontSize: 9, color: "var(--text-tertiary)", border: "1px solid var(--border-glass)", borderRadius: 3, padding: "0 3px" },
            }, "默认")
          : null,
      ),
      React.createElement("div", { style: { display: "flex", gap: 6, alignItems: "center" } },
        renderControl(p),
        React.createElement("button", {
          type: "button",
          "aria-label": `${p.label} 的详细说明`,
          onMouseEnter: (e: React.MouseEvent<HTMLElement>) => openTip(p, e.currentTarget),
          onMouseLeave: closeTip,
          onClick: (e: React.MouseEvent<HTMLElement>) => (tip && tip.spec.key === p.key ? closeTip() : openTipNow(p, e.currentTarget)),
          onFocus: (e: React.FocusEvent<HTMLElement>) => openTipNow(p, e.currentTarget),
          onBlur: closeTip,
          style: {
            flexShrink: 0, width: 18, height: 18, borderRadius: 9, cursor: "pointer",
            fontSize: 10, lineHeight: 1, padding: 0, fontFamily: "inherit",
            background: "transparent", border: "1px solid var(--border-glass)",
            color: "var(--text-tertiary)",
          } as React.CSSProperties,
        }, "?"),
      ),
      err ? React.createElement("div", {
        style: {
          marginTop: 3, fontSize: 10, color: "var(--text-primary)",
          background: "color-mix(in srgb, var(--red) 12%, transparent)",
          borderLeft: "3px solid var(--red)", borderRadius: 4, padding: "2px 6px",
        },
      }, "⚠ " + err) : null,
    );
  };

  /** 取一份「按当前约定转好」的预览网格：读文件 → POST /api/step-preview */
  const loadPreview = React.useCallback(async () => {
    if (!file) { setPvErr("请先选择 STEP 文件"); return; }
    setPvBusy(true);
    setPvErr("");
    try {
      const dataUrl: string = await new Promise((res, rej) => {
        const fr = new FileReader();
        fr.onload = () => res(String(fr.result || ""));
        fr.onerror = () => rej(new Error("读取文件失败"));
        fr.readAsDataURL(file);
      });
      const b64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
      const r = await fetch(apiUrl("/api/step-preview"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data: b64,
          cad_orientation: {
            up: String(vals.cadUpAxis || "Z"),
            azimuthDeg: Number(vals.cadAzimuthDeg || 0),
            origin: String(vals.cadOrigin || "keep"),
          },
        }),
      });
      const j = await r.json();
      if (j.status !== "ok" || !j.stl) {
        setPv(null);
        setPvErr(j.message || "预览失败");
        return;
      }
      const token = String(Date.now());
      const title = "📐 STEP 方向预览 — " + ((j.notes || [])[0] || "");
      // 与「3D 预览」同一个独立窗口（用户 2026-10-08：要新窗口，不是主窗口里的浮层）：
      // 预置网格随数据桥带过去，窗口里不再调后端。非 Tauri 环境退回窗内浮层。
      const opened = await openPreview3D({
        cells: [{ num: "1", mat: "1", density: "", surfaces: "", comment: "STEP 模型（已按当前方向约定转好）", render: true }],
        surfaces: "",
        trCards: "",
        materials: [],
        preloadedStl: { "1": j.stl },
        preloadToken: token,
        titleOverride: title,
      });
      setPv({ stl: j.stl, bbox: j.bbox, notes: j.notes, token, windowed: opened });
    } catch (e: any) {
      setPv(null);
      setPvErr(e?.message || "预览请求失败");
    } finally {
      setPvBusy(false);
    }
  }, [file, vals.cadUpAxis, vals.cadAzimuthDeg, vals.cadOrigin]);

  // 预览已开时，改「上轴/方位/原点」立即重取（后端按文件 sha1 缓存镶嵌结果，切换只做矩阵）
  useEffect(() => {
    if (pvOpen && file) void loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vals.cadUpAxis, vals.cadAzimuthDeg, vals.cadOrigin]);

  const renderBlock = (b: Block, i: number) => {
    if (b.t === "stepPreview") {
      return React.createElement("div", { key: "stepPreview", style: { marginTop: 8 } },
        React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" } },
          React.createElement("button", {
            type: "button", className: "btn btn-ghost btn-xs",
            "data-step-preview": "1",
            disabled: pvBusy || !file,
            onClick: () => { setPvOpen(true); void loadPreview(); },
            style: { fontSize: 11 },
          }, pvBusy ? "⏳ 生成预览…" : "👁 预览方向（用这个 STEP 生成）"),
          React.createElement("span", { style: { fontSize: 10, color: "var(--text-tertiary)" } },
            file ? "看它在这个约定下长什么样；换上面的上轴/原点会立即重画" : "先选 STEP 文件"),
        ),
        pvErr ? React.createElement("div", { style: { fontSize: 11, color: "#e53935", marginTop: 4 } }, pvErr) : null,
        /* 预览用**真正的 3D 预览窗口**（用户 2026-10-08：别自己搓画布，直接用 3D 预览那一套）——
           灯光/坐标轴/刻度/轨道控制/材料色板/出图全部与正常 3D 预览一致。
           网格是后端按当前方向约定转好的，所以窗口里看到的就是"导入到 MCNP 之后"的样子。 */
        (pv && !pv.windowed) ? React.createElement(Preview3D, {
          cells: [{ num: "1", mat: "1", density: "", surfaces: "", comment: "STEP 模型（已按当前方向约定转好）", render: true }],
          preloadedStl: { "1": pv.stl },
          preloadToken: pv.token,
          titleOverride: "📐 STEP 方向预览 — " + ((pv.notes || [])[0] || ""),
          zIndex: 1300,
          onClose: () => setPv(null),
        }) : null,
      );
    }
    if (b.t === "file") {
      return React.createElement("div", {
        key: "file", style: { marginBottom: 10 },
      },
        React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 5, marginBottom: 3 } },
          React.createElement("label", { style: V.txt }, "STEP 文件"),
          React.createElement("button", {
            type: "button", "aria-label": "STEP 文件 的详细说明",
            onMouseEnter: (e: React.MouseEvent<HTMLElement>) => openTip(FILE_TIP, e.currentTarget),
            onMouseLeave: closeTip,
            onClick: (e: React.MouseEvent<HTMLElement>) => (tip && tip.spec.key === FILE_TIP.key ? closeTip() : openTipNow(FILE_TIP, e.currentTarget)),
            style: {
              width: 18, height: 18, borderRadius: 9, cursor: "pointer", fontSize: 10, lineHeight: 1,
              padding: 0, fontFamily: "inherit", background: "transparent",
              border: "1px solid var(--border-glass)", color: "var(--text-tertiary)",
            } as React.CSSProperties,
          }, "?"),
        ),
        React.createElement("input", {
          type: "file", accept: ".step,.stp", onChange: handleFileChange,
          "aria-label": "STEP 文件",
          style: { ...V.inp, padding: "4px 8px", height: 32 },
        }),
      );
    }
    if (b.t === "group") {
      return React.createElement("div", { key: `g${i}`, style: { margin: "10px 0 6px" } },
        React.createElement("div", { style: { fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" } }, "▌" + b.title),
        b.hint ? React.createElement("div", { style: { fontSize: 10, color: "var(--text-tertiary)", marginTop: 2 } }, b.hint) : null,
      );
    }
    if (b.t === "note") {
      return React.createElement("div", {
        key: `n${i}`, style: { fontSize: 10, color: "var(--text-tertiary)", marginTop: 4 },
      }, b.text);
    }
    if (b.t === "banner") {
      return React.createElement("div", {
        key: `b${i}`,
        style: {
          fontSize: 11, lineHeight: 1.6, color: "var(--text-primary)",
          background: "color-mix(in srgb, var(--red) 12%, transparent)",
          borderLeft: "3px solid var(--red)", borderRadius: 6, padding: "8px 10px", marginBottom: 10,
        },
      }, "⚠ 高危：这些是几何「是否算同一个面 / 同一根轴」的判定阈值，改错会把两个面粘成一个、或把一个面劈成两个。改完务必核对体积与重叠。");
    }
    return React.createElement("div", {
      key: `r${i}`, style: { display: "flex", gap: 10, alignItems: "flex-start", marginBottom: 10 },
    }, b.keys.map((k) => renderField(SPEC_BY_KEY[k])).filter(Boolean));
  };

  const riskCollapsed = page === "risk" && !riskOpen;
  const blocks = PAGE_LAYOUT[page];
  /** 高危页参数项数（折叠时显示在「展开参数」按钮上） */
  const riskParamCount = (PAGE_LAYOUT.risk.filter((b) => b.t === "row") as { t: "row"; keys: string[] }[])
    .reduce((a, b) => a + b.keys.length, 0);

  const tabBar = React.createElement("div", {
    style: { display: "flex", gap: 2, borderBottom: "1px solid var(--border-glass)", flexShrink: 0 },
  }, PAGES.map((pg) => {
    const on = pg.id === page;
    const n = pageChangedCount(pg.id);
    return React.createElement("button", {
      key: pg.id, type: "button", onClick: () => { setPage(pg.id); closeTip(); },
      style: {
        background: "transparent", border: "none", cursor: "pointer", fontFamily: "inherit",
        padding: "6px 10px", fontSize: 11,
        color: on ? "var(--text-primary)" : "var(--text-secondary)",
        fontWeight: on ? 600 : 400,
        borderBottom: "2px solid " + (on ? "var(--accent-glow)" : "transparent"),
        marginBottom: -1,
      } as React.CSSProperties,
    }, pg.label + (n > 0 ? ` ●${n}` : ""));
  }));

  const hintLine = React.createElement("div", {
    style: { fontSize: 10, color: "var(--text-tertiary)", padding: "8px 0 10px", flexShrink: 0 },
  }, "💡 鼠标停在参数右侧的 ? 上，可查看该参数的中文详细释义");

  const content = React.createElement("div", {
    // 只留**一个**滚动条（2026-10-08 用户报「这个页面怎么有两个条」）：
    // 旧写法用 `maxHeight: calc(85vh - 190px)` 估算"除列表外的 chrome 高度"，一旦参数变多
    // （新增坐标约定/原点口径/预览块）这个估算就被吃穿 ⇒ 外层 FloatingDialog 的 body
    // （flex:1 + overflow:auto）与这里同时出条。
    // 改法：本块不再自己算 vh，而是 flex 链里"吃剩下的高度"（flex:1 + minHeight:0），
    // 高度由对话框统一决定 ⇒ 外条不可能出现，列表内部照旧可滚。
    // `data-step-settings-scroll` 给测试用：断言"这里是唯一的滚动区、且不许再用 vh 估算"。
    "data-step-settings-scroll": "1",
    style: { flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden" },
    onScroll: closeTip,
  },
    riskCollapsed
      ? React.createElement(React.Fragment, null,
          renderBlock({ t: "banner" }, 0),
          React.createElement("button", {
            type: "button",
            onClick: () => setRiskOpen(true),
            style: {
              height: 30, padding: "0 12px", borderRadius: 6, cursor: "pointer", fontSize: 11,
              fontFamily: "inherit", background: "transparent",
              border: "1px solid var(--border-glass)", color: "var(--text-secondary)",
            } as React.CSSProperties,
          }, `展开参数（${riskParamCount} 项）`))
      : blocks.map(renderBlock),
  );

  const footer = React.createElement(React.Fragment, null,
    React.createElement("div", {
      style: { flex: 1, display: "flex", alignItems: "center", gap: 10 },
    },
      React.createElement("button", {
        type: "button",
        onClick: () => {
          // 回到全默认（= 所有可记忆项都没动过）⇒ 持久化 effect 随即落盘成 {}，
          // 所以「全部恢复默认」同时也是唯一的"清除记忆"入口。
          setVals(pristineState()); setErrors({}); closeTip();
        },
        style: {
          height: 26, padding: "0 10px", borderRadius: 6, cursor: "pointer", fontSize: 10,
          fontFamily: "inherit", background: "transparent",
          border: "1px solid var(--border-glass)", color: "var(--text-secondary)",
        } as React.CSSProperties,
      }, "全部恢复默认"),
      React.createElement("span", { style: { fontSize: 10, color: "var(--text-tertiary)" } },
        changedCount > 0 ? `已自定义 ${changedCount} 项` : "全部使用 GEOUNED 默认"),
    ),
    React.createElement("button", { className: "btn btn-ghost btn-sm", onClick: onClose }, "取消"),
    React.createElement("button", { className: "btn btn-primary btn-sm", onClick: handleImport, disabled: !file }, "📥 导入"),
  );

  return React.createElement(FloatingDialog, {
    title: "📥 GEOUNED 导入设置",
    onClose,
    width: 660,
    footer,
  },
    React.createElement("div", {
      // flex 链的中间层：tabBar / hintLine 固定（flexShrink:0），content 吃剩余高度并自己滚
      style: {
        padding: 0, display: "flex", flexDirection: "column",
        flex: 1, minHeight: 0, height: "100%",
      },
    },
      tabBar, hintLine, content,
      tip ? React.createElement(TipBubble, { spec: tip.spec, anchor: tip.anchor }) : null,
    ),
  );
}

/** STEP 文件选择框的释义（不是 GEOUNED 参数，单独放） */
const FILE_TIP: ParamSpec = {
  key: "__file", label: "STEP 文件", geouned: "load_step_file.filename",
  kind: "text",
  tip: {
    role: "要转换的 CAD 文件，支持 .step / .stp。文件内容会送到后端，由 FreeCAD + GEOUNED 转成 MCNP 曲面与栅元卡。",
    note: "未选文件时「导入」按钮不可点。转换在后台进行，小件 3~4 秒，真实装配体可能到分钟级。",
  },
};

