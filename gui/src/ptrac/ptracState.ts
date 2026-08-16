/**
 * ptracState — PTRAC 卡体 ↔ 结构化状态（契约 ptrac-visualization.md §4.5）
 *
 * 计数标签页「粒子径迹（PTRAC）」表单状态，落在 deck.tally.ptrac（加性字段，
 * JSON key 与后端生成/解析同步）。纯函数：emptyPtracState / ptracFromDict /
 * cardTextToPtrac / ptracToCardText。
 *
 * 卡体生成用 `KEY=value` 连写（`PTRAC FILE=ASC WRITE=ALL MAX=-1 TYPE=N P …`），
 * 解析同时容错 `KEY value` 空格分隔与大小写（镜像后端 fmesh_parser 等号可选先例）。
 */

export interface PtracState {
  /** 勾选启用 → 生成 PTRAC 卡；false 不生成 */
  enabled: boolean;
  /** FILE=ASC|BIN（默认 ASC） */
  file: string;
  /** WRITE=ALL|SOURCE|EVENT（默认 ALL） */
  write: string;
  /** MAX=数字（默认 -1） */
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
  /** EVENT=值（高级折叠） */
  event: string;
}

export const PTRAC_FILE_OPTIONS = ["ASC", "BIN"];
export const PTRAC_WRITE_OPTIONS = ["ALL", "SOURCE", "EVENT"];
export const PTRAC_TYPE_OPTIONS = ["N", "P", "E"];

/** 默认状态：未启用；FILE=ASC / WRITE=ALL / MAX=-1（契约 §4.5） */
export function emptyPtracState(): PtracState {
  return {
    enabled: false,
    file: "ASC",
    write: "ALL",
    max: "-1",
    types: [],
    nps: "",
    cell: "",
    surface: "",
    value: "",
    event: "",
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
  if (d.write != null) s.write = String(d.write).trim().toUpperCase() || "ALL";
  if (d.max != null) s.max = String(d.max).trim();
  if (Array.isArray(d.types)) {
    s.types = d.types
      .map((t: any) => String(t).trim().toUpperCase())
      .filter((t: string) => PTRAC_TYPE_OPTIONS.includes(t));
  }
  for (const k of ["nps", "cell", "surface", "value", "event"] as const) {
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
  parts.push(`MAX=${state.max ?? "-1"}`);
  const types = (state.types || []).map((t) => t.toUpperCase()).filter(Boolean);
  if (types.length) parts.push(`TYPE=${types.join(" ")}`);
  if ((state.nps || "").trim()) parts.push(`NPS=${state.nps.trim()}`);
  if ((state.cell || "").trim()) parts.push(`CELL=${state.cell.trim()}`);
  if ((state.surface || "").trim()) parts.push(`SURFACE=${state.surface.trim()}`);
  if ((state.value || "").trim()) parts.push(`VALUE=${state.value.trim()}`);
  if ((state.event || "").trim()) parts.push(`EVENT=${state.event.trim()}`);
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
  // 归一化：FILE/WRITE 大写（MCNP 大小写不敏感）；空值回退默认
  if (state.file) state.file = state.file.toUpperCase();
  if (state.write) state.write = state.write.toUpperCase();
  return state;
}
