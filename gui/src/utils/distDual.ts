/*
 * distDual — 分布 v2 双态（raw 原文 ⇄ structured 表单）的 TS 镜像（codebase-design）。
 *
 * 权威实现在 app/generator/distributions.py；本文件只镜像「单条分布」的
 * structured→卡行格式 与 原文→structured 解析，供前端形态切换时预览/回填：
 *   - structuredToRaw(entry)  表单 → 原文卡行（规范重建，SC/SI/SP/SB/DS 序）
 *   - rawToStructured(text,id) 原文 → 结构化字段（无字母 SI → type ""，不再回填 L）
 *   - parseDistributionLines(text) 多条原文 → DistEntry[]（镜像后端
 *     `app/generator/distributions.py:parse_distribution_lines`，按行首数字 id 分组；
 *     用于旧存档 sdefRawText 一次性迁移进 adv.sdef_distributions）
 *
 * 与后端一致的硬性约束：
 *   - SI 无字母（""）永不被打成 L；发射时 type="" 不带字母（MCNP 缺省 H）
 *   - SP type D 发射即裸值（与省略同义）；C/V 带字母；fnCode(-2..-41) 走内置函数
 *   - SB：-21/-31 函数码；DS：T 无 param，其余 type+param+refs
 */
import type { DistEntry, SiEntry, SpEntry, SbEntry, DsEntry } from "./DeckContext";

const SI_LETTERS = ["L", "H", "A", "S", "Q", "T", "F", "V"];
const SP_LETTERS = ["D", "C", "V"];
const DS_LETTERS = ["H", "L", "S", "T", "Q"];
const SB_FN = ["-21", "-31"];

function clean(v: unknown): string {
  return String(v ?? "").trim();
}

function stripInlineComment(line: string): string {
  const i = line.indexOf("$");
  return (i >= 0 ? line.slice(0, i) : line).trim();
}

function parseSi(toks: string[]): SiEntry {
  const out: SiEntry = { type: "", values: toks };
  if (toks.length && SI_LETTERS.includes(toks[0].toUpperCase())) {
    out.type = toks[0].toUpperCase() as SiEntry["type"];
    out.values = toks.slice(1);
  }
  return out;
}

function parseSp(toks: string[]): SpEntry {
  const out: SpEntry = { type: "", values: [], fnCode: "", fnParams: [] };
  if (toks.length && /^-\d+$/.test(toks[0])) {
    out.fnCode = toks[0];
    out.fnParams = toks.slice(1);
  } else if (toks.length && SP_LETTERS.includes(toks[0].toUpperCase())) {
    out.type = toks[0].toUpperCase() as SpEntry["type"];
    out.values = toks.slice(1);
  } else {
    out.values = toks;
  }
  return out;
}

function parseSb(toks: string[]): SbEntry {
  const out: SbEntry = { type: "D", values: toks };
  if (toks.length && SB_FN.includes(toks[0])) {
    out.type = toks[0] as SbEntry["type"];
    out.values = toks.slice(1);
  } else if (toks.length && toks[0].toUpperCase() === "D") {
    out.values = toks.slice(1);
  }
  return out;
}

function parseDs(toks: string[]): DsEntry {
  const out: DsEntry = { type: "S", param: "", distributionIds: [] };
  let rest = toks;
  if (rest.length && DS_LETTERS.includes(rest[0].toUpperCase())) {
    out.type = rest[0].toUpperCase() as DsEntry["type"];
    rest = rest.slice(1);
  }
  // C810 3-66 的 DS 卡 Form 没有「变量名」字段（`DSn option J1 ... Jk`），数据**从首 token 起**：
  //   DS1 S 2 3   ⇒ ids ["2","3"]（旧实现无条件吃掉首 token 当 param ⇒ ids 只剩 ["3"]，丢数据）
  // 仅当首 token **不是数值**时才当 param 保留（历史文件里出现过 `DS2 S ERG 3 4` 这种写法，
  // 后端 `_parse_ds` 同口径容忍、抽样侧不消费 param），保证前后端解析结果一致。
  if (out.type !== "T" && rest.length && !isNumericToken(rest[0])) {
    out.param = rest[0];
    rest = rest.slice(1);
  }
  out.distributionIds = rest;
  return out;
}

/** token 是否纯数值（用于区分 DS 的 param（变量名）与数据起点，与后端 `_is_number_tok` 同口径）。 */
function isNumericToken(tok: string): boolean {
  return /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(clean(tok));
}

const KIND_RE = /^(SI|SP|SB|DS|SC)(\d+)/;

/**
 * 原文（\n 分隔的 SI/SP/SB/DS/SC 卡行）→ 结构化字段。
 * 只认行首前缀且数字 == id 的行；返回 {si,sp,sb,ds,sc}，缺失键为 null。
 * 解析不了的内容不回退成默认类型——保持 type ""（直方图省略，MCNP 缺省）。
 */
export function rawToStructured(text: string, id: number): {
  si: SiEntry | null; sp: SpEntry | null; sb: SbEntry | null;
  ds: DsEntry | null; sc: string | null;
} {
  const out: {
    si: SiEntry | null; sp: SpEntry | null; sb: SbEntry | null;
    ds: DsEntry | null; sc: string | null;
  } = { si: null, sp: null, sb: null, ds: null, sc: null };
  for (const rawLine of String(text ?? "").split("\n")) {
    const s = rawLine.trim();
    if (!s) continue;
    const m = KIND_RE.exec(s.toUpperCase());
    if (!m) continue;
    const kind = m[1];
    const num = parseInt(m[2], 10);
    if (num !== id) continue;
    const toks = stripInlineComment(s.slice(m[0].length)).split(/\s+/).filter(Boolean);
    if (kind === "SI") out.si = parseSi(toks);
    else if (kind === "SP") out.sp = parseSp(toks);
    else if (kind === "SB") out.sb = parseSb(toks);
    else if (kind === "DS") out.ds = parseDs(toks);
    else if (kind === "SC") out.sc = s.slice(m[0].length).trim();
  }
  return out;
}

/** 卡行数组拼接 → 原文文本（供编辑器 textarea / 发射预览）。 */
export function linesToRaw(lines: string[]): string {
  return lines.filter(Boolean).join("\n");
}

/**
 * 多条原文（\n 分隔的 SI/SP/SB/DS/SC 行）→ DistEntry[]，**镜像后端**
 * `app/generator/distributions.py:parse_distribution_lines` 的分组语义：
 *   - 按行首卡号分组（`SI1`/`SP1`… → 同一 id）；组按 id **首次出现顺序**排列；
 *   - 每条的 `rawText` 是该条**自己的原文行**（逐字保留，发射以原文为权威）；
 *   - `editMode="raw"`（导入/原文形态）；其余结构化字段由 `rawToStructured` 派生；
 *   - `paramRef` 留空（与后端解析产物一致——该字段仅供 UI 手工标注引用变量）；
 *   - 非分布卡行（如 `SDEF ERG=D1`）按 `KIND_RE` 自然跳过，不进任何条目。
 *
 * 用途：旧存档 `deck.sdefRawText` 一次性迁移进 `adv.sdef_distributions`（TD-23/§3.1）。
 */
export function parseDistributionLines(text: string): DistEntry[] {
  const rawLines = String(text ?? "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  // 组内保持原文出现顺序；组间按 id 首次出现顺序（与后端 order 一致）
  const grouped = new Map<number, string[]>();
  for (const line of rawLines) {
    const m = KIND_RE.exec(line.toUpperCase());
    if (!m) continue;
    const id = parseInt(m[2], 10);
    if (!grouped.has(id)) grouped.set(id, []);
    grouped.get(id)!.push(line);
  }

  const out: DistEntry[] = [];
  for (const [id, lines] of grouped) {
    const rawText = lines.join("\n");
    const parsed = rawToStructured(rawText, id);
    out.push({
      id,
      paramRef: "",
      auto: false,
      editMode: "raw",
      rawText,
      si: parsed.si,
      sp: parsed.sp,
      sb: parsed.sb,
      ds: parsed.ds,
      sc: parsed.sc ?? undefined,
    });
  }
  return out;
}

/**
 * 表单（structured 字段）→ 规范 MCNP 卡行（SC/SI/SP/SB/DS 序）。
 * 与后端 _format_entry_cards 逐条同构；type "" 的 SI 不打印字母。
 */
export function structuredToRawLines(entry: DistEntry): string[] {
  const lines: string[] = [];
  const idx = entry.id;
  const sc = clean(entry.sc);
  if (sc) lines.push(`SC${idx}  ${sc}`);
  if (entry.si) {
    const siType = clean(entry.si.type).toUpperCase();
    const vals = (entry.si.values || []).map(clean).filter(Boolean);
    if (vals.length) {
      const head = `SI${idx}` + (siType ? `  ${siType}` : "");
      lines.push(head + "  " + vals.join("  "));
    }
  }
  if (entry.sp) {
    const fn = clean(entry.sp.fnCode);
    const fnParams = (entry.sp.fnParams || []).map(clean).filter(Boolean);
    const vals = (entry.sp.values || []).map(clean).filter(Boolean);
    const spType = clean(entry.sp.type).toUpperCase();
    if (fn) {
      lines.push(`SP${idx}  ${fn}` + (fnParams.length ? "  " + fnParams.join("  ") : ""));
    } else if (spType === "C" || spType === "V") {
      lines.push(`SP${idx}  ${spType}` + (vals.length ? "  " + vals.join("  ") : ""));
    } else if (vals.length) {
      lines.push(`SP${idx}  ${vals.join("  ")}`);
    }
  }
  if (entry.sb) {
    const sbType = clean(entry.sb.type);
    const vals = (entry.sb.values || []).map(clean).filter(Boolean);
    if (sbType === "-21" || sbType === "-31") {
      lines.push(`SB${idx}  ${sbType}` + (vals.length ? "  " + vals.join("  ") : ""));
    } else if (vals.length) {
      lines.push(`SB${idx}  D  ${vals.join("  ")}`);
    }
  }
  if (entry.ds) {
    const dsType = clean(entry.ds.type).toUpperCase() || "S";
    const param = clean(entry.ds.param);
    const refs = (entry.ds.distributionIds || []).map(clean).filter(Boolean);
    if (dsType === "T") {
      // T 可带 I1 J1 … Ik Jk 匹配对（后端 resolve_ds_t 消费 distributionIds），一并回放
      lines.push(`DS${idx}  T` + (refs.length ? "  " + refs.join("  ") : ""));
    } else {
      let head = `DS${idx}  ${dsType}`;
      if (param) head += "  " + param;
      if (refs.length) head += "  " + refs.join("  ");
      lines.push(head);
    }
  }
  return lines;
}

/** entry 是否处于 raw 直接形态（缺省 = structured 规范形态）。 */
export function isRawMode(entry: DistEntry): boolean {
  return entry.editMode === "raw";
}

/** 形态切换（返回新 entry）：structured → raw（用字段规范重建原文）。 */
export function switchToRaw(entry: DistEntry): DistEntry {
  return { ...entry, editMode: "raw", rawText: linesToRaw(structuredToRawLines(entry)) };
}

/** 形态切换（返回新 entry）：raw → structured（解析原文回填字段）。 */
export function switchToStructured(entry: DistEntry): DistEntry {
  const parsed = rawToStructured(entry.rawText || "", entry.id);
  return {
    ...entry,
    editMode: "structured",
    si: parsed.si, sp: parsed.sp, sb: parsed.sb, ds: parsed.ds, sc: parsed.sc ?? entry.sc,
  };
}

/** 表单字段任一被编辑 → 确保 editMode 回 structured（raw 为导入/原文直通专属）。 */
export function withStructuredEdit(entry: DistEntry, patch: Partial<DistEntry>): DistEntry {
  return { ...entry, editMode: "structured", ...patch };
}
