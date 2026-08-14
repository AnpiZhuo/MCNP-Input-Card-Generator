/**
 * fmeshState — FMESH/TMESH 卡体 ↔ 结构化（契约 meshtal-visualization.md §4.7.1 / §5.3）
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
  geom: string; // xyz（v1 仅渲染此）
  origin: string;
  imesh: string;
  iints: string;
  jmesh: string;
  jints: string;
  kmesh: string;
  kints: string;
  emesh: string;
  eints: string;
  tmesh: string; // TMESH 时间（与 TMESH 卡种类别区分）
  t_ints: string;
  mat: string;
  out: string;
  raw: string; // 原文卡体（round-trip 兜底）
}

export const emptyFmeshRow = (): FmeshRow => ({
  number: "",
  kind: "FMESH",
  particle: "N",
  geom: "xyz",
  origin: "",
  imesh: "", iints: "",
  jmesh: "", jints: "",
  kmesh: "", kints: "",
  emesh: "", eints: "",
  tmesh: "", t_ints: "",
  mat: "", out: "",
  raw: "",
});

/** §4.7.1 幽灵文字映射：每个关键字的作用说明（placeholder/title） */
export const FMESH_PLACEHOLDERS: Record<string, string> = {
  kind: "网格类型",
  geom: "网格几何：xyz 矩形（v1 仅此渲染）",
  origin: "网格原点坐标（MCNP 全局坐标）",
  imesh: "X 向网格边界（可多值或 1INTS n 语法）",
  iints: "X 向区间数",
  jmesh: "Y 向网格边界（可多值或 1INTS n 语法）",
  jints: "Y 向区间数",
  kmesh: "Z 向网格边界（可多值或 1INTS n 语法）",
  kints: "Z 向区间数",
  emesh: "能量边界（多值；空=不分箱）",
  eints: "能量区间数",
  tmesh: "时间边界（多值）",
  t_ints: "时间区间数",
  mat: "材料过滤：只统计该材料栅元",
  out: "输出单位：f|q|n（通量/电荷/径迹长度）",
};

const FAMILY_RE = /^(FMESH|TMESH|RMESH|CMESH)(\d*):?([NPEHAS]?)$/i;
const KEY_RE = /^([A-Za-z]+)=(.*)$/;

/** 仅字符串字段（kind 为判别联合，不在关键字映射内） */
type FmeshStringField = Exclude<keyof FmeshRow, "kind">;

const KEY_TO_FIELD: Record<string, FmeshStringField> = {
  GEOM: "geom", ORIGIN: "origin", IMESH: "imesh", IINTS: "iints",
  JMESH: "jmesh", JINTS: "jints", KMESH: "kmesh", KINTS: "kints",
  EMESH: "emesh", EINTS: "eints", TMESH: "tmesh", TINTS: "t_ints",
  MAT: "mat", OUT: "out",
};

/** 是否有可回放的结构化字段（否则回放 raw） */
function hasStructured(r: FmeshRow): boolean {
  const keys: (keyof FmeshRow)[] = [
    "origin", "imesh", "iints", "jmesh", "jints", "kmesh", "kints",
    "emesh", "eints", "tmesh", "t_ints", "mat", "out",
  ];
  return keys.some((k) => !!r[k]);
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
      const geom = family === "FMESH" || family === "RMESH" ? "xyz" : "cyl";
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
      current[field] = vals.join(" ").trim();
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
  let head = `${sub}${r.number}${particle} GEOM=${r.geom || "xyz"}`;
  if (r.origin) head += ` ORIGIN=${r.origin}`;
  const lines = [head];
  const order: [string, keyof FmeshRow][] = [
    ["IMESH", "imesh"], ["IINTS", "iints"], ["JMESH", "jmesh"], ["JINTS", "jints"],
    ["KMESH", "kmesh"], ["KINTS", "kints"], ["EMESH", "emesh"], ["EINTS", "eints"],
    ["TMESH", "tmesh"], ["TINTS", "t_ints"], ["MAT", "mat"], ["OUT", "out"],
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
 * number 数值化（空→0），字段名含 t_ints（后端 key）。
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
    eints: r.eints,
    tmesh: r.tmesh,
    t_ints: r.t_ints,
    mat: r.mat,
    out: r.out,
    raw: r.raw,
  }));
}

/** 后端 parse 返回的 fmesh_defs 字典 → FmeshRow[]（缺 key 容忍） */
export function fmeshDefsToRows(defs: Record<string, any>[]): FmeshRow[] {
  return (defs || []).map((f) => ({
    number: String(f.number ?? ""),
    kind: (f.kind === "TMESH" ? "TMESH" : "FMESH") as FmeshKind,
    particle: f.particle || "",
    geom: f.geom || "xyz",
    origin: f.origin || "",
    imesh: f.imesh || "",
    iints: f.iints || "",
    jmesh: f.jmesh || "",
    jints: f.jints || "",
    kmesh: f.kmesh || "",
    kints: f.kints || "",
    emesh: f.emesh || "",
    eints: f.eints || "",
    tmesh: f.tmesh || "",
    t_ints: f.t_ints || "",
    mat: f.mat || "",
    out: f.out || "",
    raw: f.raw || "",
  }));
}
