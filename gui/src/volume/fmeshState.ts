/**
 * fmeshState — FMESH/TMESH 卡体 ↔ 结构化（契约 meshtal-visualization.md §4.7.1 / §5.3）
 *
 * ⚠️ UI 现状（2026-08-14 用户决定）：TMESH 计数卡「创建/选择」入口已从 UI 隐藏（FMeshForm
 *    只暴露 FMESH 下拉），但本模块 TMESH/RMESH/CMESH 的解析吸收、emit、序列化路径**全部保留**
 *    （未来启用时直接放开 UI 即可，无需改本模块）。导入的 TMESH 行数据原样保留、round-trip 保真。
 *
 * ✅ 字段对齐 MCNP6（2026-08-14 PM 指令，镜像后端 fmesh_parser.py / api_server `_fmesh_from_list`）：
 * - `eints → emints`、`t_ints → tmints`（旧名废弃）；新增 `axs`/`vec`/`tr`；`out` 已有。
 * - 卡体生成发 `EMINTS=`/`TMINTS=`（非 EINTS/TINTS）；导入容错 `EINTS`/`EMINTS`、`TINTS`/`TMINTS`。
 * - GEOM 值**连写单 token**（XYZ/REC 直角、CYL/RZT 圆柱），后端存首 token。
 * - 校验规则抽为纯函数 `validateFmeshRow` / `vectorsParallel`（表单提交/卡体生成前友好提示）。
 *
 * 镜像后端 `app/meshtal/fmesh_parser.py`：
 * - FMESH 语法：`FMESHn:N/P/E GEOM=xyz ORIGIN=x0 y0 z0`（续行 IMESH=/IINTS/…）
 * - TMESH 语法：`TMESHn`（标题行）+ 子卡 `RMESHn:…`（rect）/ `CMESHn:…`（cyl）
 * - 边界值以原文保存（不数值化），生成回放逐字（保 R1 不动点）
 * - structured 字段为空时回放 `raw`（round-trip 兜底）
 *
 * 幽灵文字映射（§4.7.1）供 FMeshForm placeholder/title 使用。
 */
export type FmeshKind = "FMESH" | "TMESH";

export interface FmeshRow {
  number: string;
  kind: FmeshKind;
  particle: string; // N/P/E（FMESH 卡头设计符）
  geom: string; // 单 token 连写：XYZ/REC（直角）、CYL/RZT（圆柱）
  origin: string;
  imesh: string;
  iints: string;
  jmesh: string;
  jints: string;
  kmesh: string;
  kints: string;
  emesh: string;
  emints: string; // MCNP6 关键字（旧 eints 废弃，导入容错 EINTS/EMINTS）
  tmesh: string; // FMESH 卡时间分箱关键字（TMESH=时间边界；与 TMESH 计数卡种类别区分）
  tmints: string; // MCNP6 关键字（旧 t_ints 废弃，导入容错 TINTS/TMINTS）
  mat: string;
  out: string;
  axs: string; // 圆柱轴向量（CYL/RZT 系）
  vec: string; // 圆柱网格方向向量（与 AXS 不平行）
  tr: string; // 可选变换编号（正整数）
  raw: string; // 原文卡体（round-trip 兜底）
}

export const emptyFmeshRow = (): FmeshRow => ({
  number: "",
  kind: "FMESH",
  particle: "N",
  geom: "XYZ",
  origin: "",
  imesh: "", iints: "",
  jmesh: "", jints: "",
  kmesh: "", kints: "",
  emesh: "", emints: "",
  tmesh: "", tmints: "",
  mat: "", out: "",
  axs: "", vec: "", tr: "",
  raw: "",
});

/* ── GEOM / OUT 下拉选项（字段契约，FMeshForm 消费） ── */
export interface FmeshGeomOption {
  value: string;
  label: string;
  family: "cart" | "cyl";
}

export const FMESH_GEOM_OPTIONS: FmeshGeomOption[] = [
  { value: "XYZ", label: "XYZ（直角，默认）", family: "cart" },
  { value: "REC", label: "REC（直角）", family: "cart" },
  { value: "CYL", label: "CYL（圆柱）", family: "cyl" },
  { value: "RZT", label: "RZT（圆柱）", family: "cyl" },
];

export interface FmeshOutOption {
  value: string;
  label: string;
  hint: string;
}

export const FMESH_OUT_OPTIONS: FmeshOutOption[] = [
  { value: "COL", label: "COL", hint: "标准柱状输出（默认）" },
  { value: "CF", label: "CF", hint: "累计通量：额外输出体积 + 结果×体积" },
  { value: "COLSC", label: "COLSC", hint: "彩色刻度柱状输出" },
  { value: "CFSC", label: "CFSC", hint: "CF + 彩色刻度" },
  { value: "IJ", label: "IJ", hint: "按 I×J 平面输出" },
  { value: "IK", label: "IK", hint: "按 I×K 平面输出" },
  { value: "JK", label: "JK", hint: "按 J×K 平面输出" },
  { value: "NONE", label: "NONE", hint: "不打印 meshtal 输出" },
  { value: "XDMF", label: "XDMF", hint: "ParaView 可视化（XDMF）" },
];

/** GEOM 归一化：大写单 token（连写），空值默认 XYZ（镜像后端 `_card_lines` 只取首 token） */
export function normalizeGeom(g: string): string {
  const first = (g || "").trim().split(/\s+/)[0];
  return (first || "XYZ").toUpperCase();
}

/** 是否圆柱系（CYL/RZT）：AXS/VEC 显示 + kmesh 末值=1 校验 + 平行检测的前提 */
export function isCylGeom(g: string): boolean {
  const t = normalizeGeom(g);
  return t === "CYL" || t === "RZT";
}

/** §4.7.1 幽灵文字映射：每个关键字的作用说明（placeholder/title） */
export const FMESH_PLACEHOLDERS: Record<string, string> = {
  kind: "网格类型",
  geom: "网格几何：XYZ/REC（直角）、CYL/RZT（圆柱）",
  origin: "网格原点坐标（MCNP 全局坐标）",
  imesh: "X/径向 网格边界（多值=多区间，与 IINTS 条目一一对应）",
  iints: "X/径向 区间数（正整数）",
  jmesh: "Y/轴向 网格边界（多值=多区间）",
  jints: "Y/轴向 区间数（正整数）",
  kmesh: "Z/θ 网格边界（圆柱系末值须为 1）",
  kints: "Z/θ 区间数（正整数）",
  emesh: "能量边界（多值，单调递增；空=不分箱）",
  emints: "能量区间数（正整数）",
  tmesh: "时间边界（多值，单调递增）",
  tmints: "时间区间数（正整数）",
  mat: "材料过滤：0=粒子所在格材料（默认），非 0=指定材料号",
  out: "输出单位：COL（默认）/ CF / COLSC / CFSC / IJ / IK / JK / NONE / XDMF",
  axs: "圆柱轴向量（CYL/RZT 系，3 分量）",
  vec: "圆柱方向向量（3 分量，与 AXS 不平行）",
  tr: "可选变换编号（正整数）",
};

const FAMILY_RE = /^(FMESH|TMESH|RMESH|CMESH)(\d*):?([NPEHAS]?)$/i;
const KEY_RE = /^([A-Za-z]+)=(.*)$/;

/** 仅字符串字段（kind 为判别联合，不在关键字映射内） */
type FmeshStringField = Exclude<keyof FmeshRow, "kind">;

const KEY_TO_FIELD: Record<string, FmeshStringField> = {
  GEOM: "geom", ORIGIN: "origin", IMESH: "imesh", IINTS: "iints",
  JMESH: "jmesh", JINTS: "jints", KMESH: "kmesh", KINTS: "kints",
  EMESH: "emesh", EMINTS: "emints", EINTS: "emints", // EINTS/EMINTS 容错
  TMESH: "tmesh", TMINTS: "tmints", TINTS: "tmints", // TINTS/TMINTS 容错
  AXS: "axs", VEC: "vec", TR: "tr",
  MAT: "mat", OUT: "out",
};

/** 是否有可回放的结构化字段（否则回放 raw） */
const STRUCTURED_KEYS: (keyof FmeshRow)[] = [
  "origin", "imesh", "iints", "jmesh", "jints", "kmesh", "kints",
  "emesh", "emints", "tmesh", "tmints", "mat", "out", "axs", "vec", "tr",
];
function hasStructured(r: FmeshRow): boolean {
  return STRUCTURED_KEYS.some((k) => !!r[k]);
}

/**
 * 卡体文本 → FmeshRow[]（镜像 parse_fmesh_lines）。
 * 吸收 FMESHn / RMESHn（rect）/ CMESHn（cyl）；TMESHn 标题行仅记录卡号。
 */
export function cardTextToFmesh(text: string): FmeshRow[] {
  const lines = (text || "").split(/\r?\n/);
  const tokens: string[] = [];
  for (const ln of lines) {
    const s = ln.trim();
    if (s) tokens.push(...s.split(/\s+/));
  }

  const rows: FmeshRow[] = [];
  let current: FmeshRow | null = null;
  let pendingTmeshNumber: string | null = null;

  let i = 0;
  while (i < tokens.length) {
    const tok = tokens[i];
    const m = tok.match(FAMILY_RE);
    if (m) {
      const family = m[1].toUpperCase();
      const numberStr = m[2] || "";
      const particle = m[3] || "";
      if (family === "TMESH") {
        pendingTmeshNumber = numberStr || null;
        i += 1;
        continue;
      }
      const number = numberStr || pendingTmeshNumber || "";
      const kind: FmeshKind = family === "FMESH" ? "FMESH" : "TMESH";
      const geom = family === "FMESH" || family === "RMESH" ? "XYZ" : "CYL";
      current = {
        ...emptyFmeshRow(),
        number,
        kind,
        particle,
        geom,
      };
      rows.push(current);
      i += 1;
      continue;
    }
    const km = tok.match(KEY_RE);
    if (km) {
      const key = km[1].toUpperCase();
      const field = KEY_TO_FIELD[key];
      if (!field || !current) {
        i += 1;
        continue;
      }
      const vals: string[] = [km[2]].filter(Boolean);
      let j = i + 1;
      while (j < tokens.length) {
        const nt = tokens[j];
        if (FAMILY_RE.test(nt) || KEY_RE.test(nt)) break;
        vals.push(nt);
        j += 1;
      }
      if (field === "geom") {
        // GEOM 值必须单 token（`GEOM=X Y Z` 非法，MCNP 只认 GEOM=XYZ/CYL）；只取首值，防御空格拆开
        current[field] = normalizeGeom(vals[0] || "");
      } else {
        current[field] = vals.join(" ").trim();
      }
      i = j;
      continue;
    }
    i += 1;
  }

  // raw 兜底：结构化字段为空时保 raw 原文
  const joinedRaw = lines.filter((l) => l.trim()).join("\n");
  for (const r of rows) {
    if (!hasStructured(r) && !r.raw) r.raw = joinedRaw;
  }

  if (rows.length === 0 && pendingTmeshNumber == null && tokens.length > 0) {
    const first = tokens[0].match(FAMILY_RE);
    if (first) {
      rows.push({
        ...emptyFmeshRow(),
        number: first[2] || "",
        kind: first[1].toUpperCase() === "FMESH" ? "FMESH" : "TMESH",
        raw: joinedRaw,
      });
    }
  }
  return rows;
}

function cardLines(r: FmeshRow, sub: string): string[] {
  const particle = r.particle ? `:${r.particle}` : "";
  let head = `${sub}${r.number}${particle} GEOM=${normalizeGeom(r.geom)}`;
  if (r.origin) head += ` ORIGIN=${r.origin}`;
  const lines = [head];
  const order: [string, keyof FmeshRow][] = [
    ["IMESH", "imesh"], ["IINTS", "iints"], ["JMESH", "jmesh"], ["JINTS", "jints"],
    ["KMESH", "kmesh"], ["KINTS", "kints"], ["EMESH", "emesh"], ["EMINTS", "emints"],
    ["TMESH", "tmesh"], ["TMINTS", "tmints"], ["MAT", "mat"], ["OUT", "out"],
    ["AXS", "axs"], ["VEC", "vec"], ["TR", "tr"],
  ];
  for (const [k, v] of order) {
    const val = r[v];
    if (val) lines.push(`     ${k}=${val}`);
  }
  return lines;
}

/**
 * FmeshRow[] → 卡体文本（镜像 fmesh_defs_to_lines）。
 * structured 字段齐全走结构化；否则回放 raw（round-trip 兜底）。
 */
export function fmeshToCardText(rows: FmeshRow[]): string {
  const out: string[] = [];
  for (const r of rows || []) {
    if (!hasStructured(r)) {
      const raw = r.raw;
      if (raw) {
        for (const ln of raw.split(/\r?\n/)) {
          if (ln.trim()) out.push(ln.trimEnd());
        }
      }
      continue;
    }
    if (r.kind === "TMESH") {
      out.push(`TMESH${r.number}`);
      out.push(...cardLines(r, "RMESH"));
    } else {
      out.push(...cardLines(r, "FMESH"));
    }
  }
  return out.join("\n");
}

/**
 * FmeshRow[] → 后端 generate 载荷 `tally.fmesh_defs` 数组（照 _fmesh_from_list key 对齐）。
 * number 数值化（空→0）；字段名 emints/tmints/axs/vec/tr 对齐后端 JSON key。
 */
export function buildFmeshPayload(rows: FmeshRow[]): Record<string, any>[] {
  return (rows || []).map((r) => ({
    number: parseInt(r.number, 10) || 0,
    kind: r.kind,
    particle: r.particle,
    geom: r.geom,
    origin: r.origin,
    imesh: r.imesh,
    iints: r.iints,
    jmesh: r.jmesh,
    jints: r.jints,
    kmesh: r.kmesh,
    kints: r.kints,
    emesh: r.emesh,
    emints: r.emints,
    tmesh: r.tmesh,
    tmints: r.tmints,
    mat: r.mat,
    out: r.out,
    axs: r.axs,
    vec: r.vec,
    tr: r.tr,
    raw: r.raw,
  }));
}

/** 后端 parse 返回的 fmesh_defs 字典 → FmeshRow[]（缺 key 容忍；emints/tmints 向后兼容旧 eints/t_ints） */
export function fmeshDefsToRows(defs: Record<string, any>[]): FmeshRow[] {
  return (defs || []).map((f) => ({
    number: String(f.number ?? ""),
    kind: (f.kind === "TMESH" ? "TMESH" : "FMESH") as FmeshKind,
    particle: f.particle || "",
    geom: normalizeGeom(f.geom || ""),
    origin: f.origin || "",
    imesh: f.imesh || "",
    iints: f.iints || "",
    jmesh: f.jmesh || "",
    jints: f.jints || "",
    kmesh: f.kmesh || "",
    kints: f.kints || "",
    emesh: f.emesh || "",
    emints: f.emints ?? f.eints ?? "",
    tmesh: f.tmesh || "",
    tmints: f.tmints ?? f.t_ints ?? "",
    mat: f.mat || "",
    out: f.out || "",
    axs: f.axs || "",
    vec: f.vec || "",
    tr: f.tr || "",
    raw: f.raw || "",
  }));
}

/* ── 校验规则（纯函数，表单提交/卡体生成前友好提示；PM 指令第 8 项） ── */
export type FmeshIssueLevel = "error" | "warning";

export interface FmeshValidationIssue {
  field: string;
  level: FmeshIssueLevel;
  message: string;
}

/** 空格分隔数值列表 → number[]；任一 token 非数值返回 null */
export function parseNumberList(s: string): number[] | null {
  const toks = (s || "").trim().split(/\s+/).filter(Boolean);
  if (toks.length === 0) return [];
  const nums: number[] = [];
  for (const t of toks) {
    if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(t)) return null;
    nums.push(parseFloat(t));
  }
  return nums;
}

/** 3 分量向量解析（空格分隔 3 个数值） */
export function parseVector(s: string): [number, number, number] | null {
  const nums = parseNumberList(s);
  if (!nums || nums.length !== 3) return null;
  return [nums[0], nums[1], nums[2]];
}

/**
 * 两向量是否平行：归一化叉积 = |sin θ| < eps（θ≈0 或 π → 平行/反平行）。
 * 零向量或非法输入返回 false（不误判）。
 */
export function vectorsParallel(a: string, b: string, eps = 1e-6): boolean {
  const va = parseVector(a);
  const vb = parseVector(b);
  if (!va || !vb) return false;
  const [ax, ay, az] = va;
  const [bx, by, bz] = vb;
  const aNorm = Math.hypot(ax, ay, az);
  const bNorm = Math.hypot(bx, by, bz);
  if (aNorm < 1e-12 || bNorm < 1e-12) return false;
  const cx = ay * bz - az * by;
  const cy = az * bx - ax * bz;
  const cz = ax * by - ay * bx;
  return Math.hypot(cx, cy, cz) / (aNorm * bNorm) < eps;
}

/** 每个 token 都是正整数（区间数 ≥ 1） */
function isPositiveInts(s: string): boolean {
  const toks = (s || "").trim().split(/\s+/).filter(Boolean);
  if (toks.length === 0) return true;
  return toks.every((t) => /^[1-9]\d*$/.test(t));
}

function tokenCount(s: string): number {
  return (s || "").trim().split(/\s+/).filter(Boolean).length;
}

function isStrictlyIncreasing(nums: number[]): boolean {
  for (let i = 1; i < nums.length; i++) {
    if (nums[i] <= nums[i - 1]) return false;
  }
  return true;
}

/** *ints 数值求和（该方向实际区间总数）；任一 token 非整数返回 null */
function sumInts(s: string): number | null {
  const toks = (s || "").trim().split(/\s+/).filter(Boolean);
  if (toks.length === 0) return 0;
  let sum = 0;
  for (const t of toks) {
    if (!/^\d+$/.test(t)) return null;
    sum += parseInt(t, 10);
  }
  return sum;
}

/** 三方向区间总数乘积（实际网格单元数）；任一方向非数值返回 null */
export function gridCellCount(r: FmeshRow): number | null {
  const i = sumInts(r.iints);
  const j = sumInts(r.jints);
  const k = sumInts(r.kints);
  if (i === null || j === null || k === null) return null;
  return i * j * k;
}

/** 大网格内存风险阈值：超出 128³ 默认渲染预算即提示（meshtal-visualization §2 128³ 默认 / §12 256³ 显式） */
export const FMESH_MEMORY_WARNING_THRESHOLD = 2_097_152; // 128³

const INTS_FIELDS: [keyof FmeshRow, string][] = [
  ["iints", "IINTS"], ["jints", "JINTS"], ["kints", "KINTS"],
  ["emints", "EMINTS"], ["tmints", "TMINTS"],
];
const MESH_PAIRS: [keyof FmeshRow, keyof FmeshRow, string, string][] = [
  ["imesh", "iints", "IMESH", "IINTS"],
  ["jmesh", "jints", "JMESH", "JINTS"],
  ["kmesh", "kints", "KMESH", "KINTS"],
  ["emesh", "emints", "EMESH", "EMINTS"],
  ["tmesh", "tmints", "TMESH", "TMINTS"],
];
const MESH_LABELS: [keyof FmeshRow, string][] = [
  ["imesh", "IMESH"], ["jmesh", "JMESH"], ["kmesh", "KMESH"],
  ["emesh", "EMESH"], ["tmesh", "TMESH"],
];

/** 校验单行 FMESH 结构化数据（友好文案，供表单提交/卡体生成前提示） */
export function validateFmeshRow(r: FmeshRow): FmeshValidationIssue[] {
  const issues: FmeshValidationIssue[] = [];
  const push = (field: string, level: FmeshIssueLevel, message: string) => {
    issues.push({ field, level, message });
  };

  // 1) *ints 必须正整数
  for (const [f, label] of INTS_FIELDS) {
    const v = (r[f] as string) || "";
    if (v && !isPositiveInts(v)) {
      push(label, "error", `${label} 须为正整数（每个区间数 ≥ 1）`);
    }
  }

  // 2) *ints 条目数与对应 *mesh 条目数匹配
  for (const [meshF, intsF, meshL, intsL] of MESH_PAIRS) {
    const mesh = (r[meshF] as string) || "";
    const ints = (r[intsF] as string) || "";
    if (!mesh && !ints) continue;
    if (!mesh) {
      push(intsL, "error", `${intsL} 缺少对应的 ${meshL} 网格边界（条目数须一一对应）`);
      continue;
    }
    if (!ints) {
      push(meshL, "error", `${meshL} 缺少对应的 ${intsL} 区间数（条目数须一一对应）`);
      continue;
    }
    const mc = tokenCount(mesh);
    const ic = tokenCount(ints);
    if (mc !== ic) {
      push(intsL, "error", `${intsL} 条目数（${ic}）与 ${meshL}（${mc}）不匹配`);
    }
  }

  // 3) 网格/能量值单调递增；直角系另校验从 ORIGIN 起
  const geom = normalizeGeom(r.geom);
  const cart = geom === "XYZ" || geom === "REC";
  for (const [meshF, label] of MESH_LABELS) {
    const nums = parseNumberList((r[meshF] as string) || "");
    if (!nums || nums.length < 2) continue;
    if (!isStrictlyIncreasing(nums)) {
      push(label, "error", `${label} 值须单调递增`);
    }
  }
  if (cart) {
    const o = parseVector(r.origin);
    if (o) {
      const pairs: [keyof FmeshRow, 0 | 1 | 2, string][] = [
        ["imesh", 0, "IMESH"], ["jmesh", 1, "JMESH"], ["kmesh", 2, "KMESH"],
      ];
      const axisName = ["X", "Y", "Z"];
      for (const [meshF, axis, label] of pairs) {
        const nums = parseNumberList((r[meshF] as string) || "");
        if (nums && nums.length > 0 && nums[0] <= o[axis]) {
          push(label, "error", `${label} 首值 ${nums[0]} 须大于 ORIGIN ${axisName[axis]} 坐标 ${o[axis]}（网格从原点起递增）`);
        }
      }
    }
  }

  // 4) 圆柱系 kmesh 末值 = 1（θ 是转数，末值 1 = 整圈 360°）
  if (isCylGeom(geom)) {
    const nums = parseNumberList(r.kmesh || "");
    if (nums && nums.length > 0 && nums[nums.length - 1] !== 1) {
      push("KMESH", "error", "圆柱系（CYL/RZT）下 KMESH 末值须为 1（θ 为转数，末值 1 = 整圈 360°）");
    }
  }

  // 5) 圆柱系 AXS/VEC 平行检测
  if (isCylGeom(geom)) {
    const axs = r.axs || "";
    const vec = r.vec || "";
    if (axs && vec && vectorsParallel(axs, vec)) {
      push("AXS", "error", "AXS 与 VEC 不能平行（圆柱轴与网格方向需不同）");
    }
  }

  // 6) TR 变换编号（正整数）
  if (r.tr && !/^\d+$/.test(r.tr.trim())) {
    push("TR", "error", "TR 须为变换编号（正整数）");
  }

  // 7) 大网格内存风险（三方向区间总数乘积 > 128³ 默认渲染预算）
  const cells = gridCellCount(r);
  if (cells !== null && cells > FMESH_MEMORY_WARNING_THRESHOLD) {
    const i = sumInts(r.iints) ?? 0;
    const j = sumInts(r.jints) ?? 0;
    const k = sumInts(r.kints) ?? 0;
    push("IINTS", "warning", `网格规模 ${i}×${j}×${k} = ${cells.toLocaleString()} 单元，超出 128³ 渲染预算，3D 体积渲染内存/性能开销大`);
  }

  return issues;
}
