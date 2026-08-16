/**
 * ptracState — PTRAC 卡体 ↔ 结构化状态（契约 ptrac-visualization.md §4.5）
 *
 * 计数标签页「粒子径迹（PTRAC）」表单状态，落在 deck.tally.ptrac（加性字段，
 * JSON key 与后端生成/解析同步）。纯函数：emptyPtracState / ptracFromDict /
 * cardTextToPtrac / ptracToCardText。
 *
 * 卡体生成用 `KEY=value` 连写（`PTRAC FILE=ASC WRITE=ALL TYPE=N P …`），
 * 解析同时容错 `KEY value` 空格分隔与大小写（镜像后端 fmesh_parser 等号可选先例）。
 */

export interface PtracState {
  /** 勾选启用 → 生成 PTRAC 卡；false 不生成 */
  enabled: boolean;
  /** FILE=ASC|BIN（默认 ASC） */
  file: string;
  /** WRITE=ALL|POS（默认 ALL；控制写哪些参数——pos=只坐标，all=坐标+方向+能量+权重+时间） */
  write: string;
  /** MAX=数字（留空=不输出，用 MCNP 默认 10000 事件） */
  max: string;
  /** TYPE=N/P/E 多选（可空） */
  types: string[];
  /** NPS=数字（可空） */
  nps: string;
  /** CELL=数字（可空） */
  cell: string;
  /** SURFACE=数字（可空） */
  surface: string;
  /** VALUE=值（高级折叠） */
  value: string;
  /** EVENT=src/bnk/sur/col/ter（高级折叠；控制写哪些事件——想看全部粒子用 src） */
  event: string;
  /** BUFFER=整数（高级折叠；事件缓冲大小） */
  buffer: string;
  /** FILTER=过滤条件（高级折叠；如 1,8,erg） */
  filter: string;
  /** TALLY=计数号（高级折叠；如 14,24） */
  tally: string;
  /** MEPH=整数（高级折叠；每历史最大事件数） */
  meph: string;
}

export const PTRAC_FILE_OPTIONS = ["ASC", "BIN"];
/** MCNP WRITE 关键字只接受 pos/all（控制写哪些参数）；SOURCE/EVENT 属 EVENT 关键字，不是 WRITE 值 */
export const PTRAC_WRITE_OPTIONS = ["ALL", "POS"];
export const PTRAC_TYPE_OPTIONS = ["N", "P", "E"];

/** 默认状态：未启用；FILE=ASC / WRITE=ALL / MAX 留空（不输出，MCNP 默认 10000 事件） */
export function emptyPtracState(): PtracState {
  return {
    enabled: false,
    file: "ASC",
    write: "ALL",
    max: "",
    types: [],
    nps: "",
    cell: "",
    surface: "",
    value: "",
    event: "",
    buffer: "",
    filter: "",
    tally: "",
    meph: "",
  };
}

const KEY_FIELDS: Record<string, keyof PtracState> = {
  FILE: "file",
  WRITE: "write",
  MAX: "max",
  NPS: "nps",
  CELL: "cell",
  SURFACE: "surface",
  VALUE: "value",
  EVENT: "event",
  BUFFER: "buffer",
  FILTER: "filter",
  TALLY: "tally",
  MEPH: "meph",
};

/** token 是否为已知 PTRAC 关键字（KEY / KEY=value，大小写不敏感） */
function keyOfToken(tok: string): string | null {
  const m = tok.match(/^([A-Za-z]+)(?:=.*)?$/);
  if (!m) return null;
  const k = m[1].toUpperCase();
  if (k === "TYPE" || k in KEY_FIELDS) return k;
  return null;
}

/** 后端 parse 返回的 dict → PtracState（缺 key 容忍 + 归一化，供 import 回填） */
export function ptracFromDict(d: Record<string, any> | undefined): PtracState {
  if (!d || typeof d !== "object") return emptyPtracState();
  const s = emptyPtracState();
  s.enabled = !!d.enabled;
  if (d.file != null) s.file = String(d.file).trim().toUpperCase() || "ASC";
  if (d.write != null) {
    const w = String(d.write).trim().toUpperCase() || "ALL";
    s.write = PTRAC_WRITE_OPTIONS.includes(w) ? w : "ALL"; // 归一化非法值（旧版 SOURCE/EVENT → ALL）
  }
  if (d.max != null) s.max = String(d.max).trim();
  if (Array.isArray(d.types)) {
    s.types = d.types
      .map((t: any) => String(t).trim().toUpperCase())
      .filter((t: string) => PTRAC_TYPE_OPTIONS.includes(t));
  }
  for (const k of ["nps", "cell", "surface", "value", "event", "buffer", "filter", "tally", "meph"] as const) {
    if (d[k] != null) s[k] = String(d[k]).trim();
  }
  return s;
}

/** PtracState → PTRAC 卡体文本（enabled=false → 空串） */
export function ptracToCardText(state: PtracState): string {
  if (!state || !state.enabled) return "";
  const parts: string[] = ["PTRAC"];
  parts.push(`FILE=${(state.file || "ASC").toUpperCase()}`);
  parts.push(`WRITE=${(state.write || "ALL").toUpperCase()}`);
  if ((state.max || "").trim()) parts.push(`MAX=${state.max.trim()}`);
  const types = (state.types || []).map((t) => t.toUpperCase()).filter(Boolean);
  if (types.length) parts.push(`TYPE=${types.join(" ")}`);
  if ((state.nps || "").trim()) parts.push(`NPS=${state.nps.trim()}`);
  if ((state.cell || "").trim()) parts.push(`CELL=${state.cell.trim()}`);
  if ((state.surface || "").trim()) parts.push(`SURFACE=${state.surface.trim()}`);
  if ((state.value || "").trim()) parts.push(`VALUE=${state.value.trim()}`);
  if ((state.event || "").trim()) parts.push(`EVENT=${state.event.trim()}`);
  if ((state.buffer || "").trim()) parts.push(`BUFFER=${state.buffer.trim()}`);
  if ((state.filter || "").trim()) parts.push(`FILTER=${state.filter.trim()}`);
  if ((state.tally || "").trim()) parts.push(`TALLY=${state.tally.trim()}`);
  if ((state.meph || "").trim()) parts.push(`MEPH=${state.meph.trim()}`);
  return parts.join(" ");
}

/** PTRAC 卡体文本 → PtracState（enabled=true；空文本 → disabled） */
export function cardTextToPtrac(text: string): PtracState {
  const state = emptyPtracState();
  const src = (text || "").trim();
  if (!src) return state;
  const tokens = src.split(/\s+/);
  let i = tokens[0].toUpperCase() === "PTRAC" ? 1 : 0;
  state.enabled = true;
  while (i < tokens.length) {
    const tok = tokens[i];
    const m = tok.match(/^([A-Za-z]+)(?:=(.*))?$/);
    if (!m) {
      i += 1;
      continue;
    }
    const key = m[1].toUpperCase();
    const inline = m[2] ?? "";
    // 收集后续值 token，直到遇到下一个已知关键字（KEY / KEY=value）
    const vals: string[] = inline ? [inline] : [];
    let j = i + 1;
    while (j < tokens.length) {
      if (keyOfToken(tokens[j])) break;
      vals.push(tokens[j]);
      j += 1;
    }
    const joined = vals.join(" ").trim();
    if (key === "TYPE") {
      state.types = joined
        ? joined.split(/\s+/).map((t) => t.toUpperCase()).filter((t) => PTRAC_TYPE_OPTIONS.includes(t))
        : [];
    } else if (key in KEY_FIELDS) {
      (state as unknown as Record<string, string>)[KEY_FIELDS[key]] = joined;
    }
    i = j;
  }
  // 归一化：FILE/WRITE 大写（MCNP 大小写不敏感）；空值回退默认；非法 WRITE → ALL
  if (state.file) state.file = state.file.toUpperCase();
  if (state.write) {
    state.write = state.write.toUpperCase();
    if (!PTRAC_WRITE_OPTIONS.includes(state.write)) state.write = "ALL";
  }
  return state;
}
