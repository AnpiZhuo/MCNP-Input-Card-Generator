/*
 * 契约映射表 — 前端 deck 字段 ↔ 后端模型字段 ↔ MCNP 卡（唯一权威）
 *
 * 规则：新增/修改任何字段必须三处同步（前端类型 + 后端模型 + 本表）。
 * 防止"同一概念两端字段名不一致"类 bug（如 nuclides/rows、prob/probability、sdef/distribution）。
 */
export interface ContractField {
  /** 前端 deck 字段名（DeckContext.tsx 类型） */
  frontend: string;
  /** 后端模型字段名（app/models.py） */
  backend: string;
  /** 对应 MCNP 卡 / 变量 */
  mcnp: string;
  /** 所在分区 */
  section: "source" | "materials" | "cells" | "basic" | "tally" | "adv" | "kcode" | "sswssr";
}

/* ── 源项（SDEF / 分布）── */
export const SOURCE_CONTRACT: ContractField[] = [
  { frontend: "sdefFields.sdef_par",   backend: "sdef_par",   mcnp: "SDEF PAR",        section: "source" },
  { frontend: "sdefFields.sdef_erg",   backend: "sdef_erg",   mcnp: "SDEF ERG",        section: "source" },
  { frontend: "sdefFields.sdef_pos_x", backend: "sdef_pos_x", mcnp: "SDEF POS X",      section: "source" },
  { frontend: "sdefFields.sdef_pos_y", backend: "sdef_pos_y", mcnp: "SDEF POS Y",      section: "source" },
  { frontend: "sdefFields.sdef_pos_z", backend: "sdef_pos_z", mcnp: "SDEF POS Z",      section: "source" },
  { frontend: "sdefFields.sdef_wgt",   backend: "sdef_wgt",   mcnp: "SDEF WGT",        section: "source" },
  { frontend: "sdefFields.sdef_dir",   backend: "sdef_dir",   mcnp: "SDEF DIR",        section: "source" },
  { frontend: "sdefFields.sdef_cel",   backend: "sdef_cel",   mcnp: "SDEF CEL",        section: "source" },
  { frontend: "sdefFields.sdef_tme",   backend: "sdef_tme",   mcnp: "SDEF TME",        section: "source" },
  { frontend: "sdefFields.sdef_vec",   backend: "sdef_vec",   mcnp: "SDEF VEC",        section: "source" },
  { frontend: "sdefFields.sdef_axs",   backend: "sdef_axs",   mcnp: "SDEF AXS",        section: "source" },
  { frontend: "sdefFields.sdef_rad",   backend: "sdef_rad",   mcnp: "SDEF RAD",        section: "source" },
  { frontend: "sdefFields.sdef_ext",   backend: "sdef_ext",   mcnp: "SDEF EXT",        section: "source" },
  { frontend: "sdefFields.sdef_sur",   backend: "sdef_sur",   mcnp: "SDEF SUR",        section: "source" },
  { frontend: "sdefFields.sdef_nrm",   backend: "sdef_nrm",   mcnp: "SDEF NRM",        section: "source" },
  { frontend: "sdefFields.sdef_tr",    backend: "sdef_tr",    mcnp: "SDEF TR",         section: "source" },
  { frontend: "sdefFields.sdef_ccc",   backend: "sdef_ccc",   mcnp: "SDEF CCC",        section: "source" },
  { frontend: "sdefFields.sdef_ara",   backend: "sdef_ara",   mcnp: "SDEF ARA",        section: "source" },
  { frontend: "sdefFields.sdef_rate",  backend: "sdef_rate",  mcnp: "SDEF RATE",       section: "source" },
  // 结构化分布（新）
  { frontend: "distributions",         backend: "sdef_distributions", mcnp: "SI/SP/SB/DS", section: "source" },
  // 旧路径（兼容）
  { frontend: "sdefRawText",           backend: "sdef_raw_text",      mcnp: "SI/SP 原文",  section: "source" },
];

/* ── 面源 SSW / SSR ── */
export const SSW_SSR_CONTRACT: ContractField[] = [
  { frontend: "sswFields.surf", backend: "ssw_surf", mcnp: "SSW S",         section: "sswssr" },
  { frontend: "sswFields.sym",  backend: "ssw_sym",  mcnp: "SSW SYM",       section: "sswssr" },
  { frontend: "sswFields.pty",  backend: "ssw_pty",  mcnp: "SSW PTY",       section: "sswssr" },
  { frontend: "sswFields.cel",  backend: "ssw_cel",  mcnp: "SSW CEL",       section: "sswssr" },
  { frontend: "ssrFields.surf", backend: "ssr_surf", mcnp: "SSR S/OLD/NEW", section: "sswssr" },
  { frontend: "ssrFields.mode", backend: "ssr_mode", mcnp: "SSR OLD/NEW",   section: "sswssr" },
  { frontend: "ssrFields.cel",  backend: "ssr_cel",  mcnp: "SSR CEL",       section: "sswssr" },
  { frontend: "ssrFields.pty",  backend: "ssr_pty",  mcnp: "SSR PTY",       section: "sswssr" },
  { frontend: "ssrFields.col",  backend: "ssr_col",  mcnp: "SSR COL",       section: "sswssr" },
  { frontend: "ssrFields.wgt",  backend: "ssr_wgt",  mcnp: "SSR WGT",       section: "sswssr" },
  { frontend: "ssrFields.tr",   backend: "ssr_tr",   mcnp: "SSR TR",        section: "sswssr" },
  { frontend: "ssrFields.psc",  backend: "ssr_psc",  mcnp: "SSR PSC",       section: "sswssr" },
];

/* ── KCODE / KSRC / HSRC ── */
export const KCODE_CONTRACT: ContractField[] = [
  { frontend: "kcodeFields.kcode_nsrc", backend: "kcode_nsrc", mcnp: "KCODE NSRC",  section: "kcode" },
  { frontend: "kcodeFields.kcode_rkk",  backend: "kcode_rkk",  mcnp: "KCODE RKK",   section: "kcode" },
  { frontend: "kcodeFields.kcode_ikz",  backend: "kcode_ikz",  mcnp: "KCODE IKZ",   section: "kcode" },
  { frontend: "kcodeFields.kcode_kct",  backend: "kcode_kct",  mcnp: "KCODE KCT",   section: "kcode" },
  { frontend: "kcodeFields.kcode_msrk", backend: "kcode_msrk", mcnp: "KCODE MSRK",  section: "kcode" },
  { frontend: "kcodeFields.kcode_knrm", backend: "kcode_knrm", mcnp: "KCODE KNRM",  section: "kcode" },
  { frontend: "kcodeFields.kcode_mrkp", backend: "kcode_mrkp", mcnp: "KCODE MRKP",  section: "kcode" },
  { frontend: "kcodeFields.kcode_kc8",  backend: "kcode_kc8",  mcnp: "KCODE KC8",   section: "kcode" },
  { frontend: "kcodeFields.hsrc_enabled", backend: "hsrc_enabled", mcnp: "HSRC 启用", section: "kcode" },
  { frontend: "kcodeFields.hsrc_text",    backend: "hsrc_text",    mcnp: "HSRC 网格", section: "kcode" },
  { frontend: "ksrcPoints",             backend: "ksrc_points",  mcnp: "KSRC 点",   section: "kcode" },
];

/* 全部源相关契约（供导入/导出 / 校验使用） */
export const SOURCE_ALL = [...SOURCE_CONTRACT, ...SSW_SSR_CONTRACT, ...KCODE_CONTRACT];

/** 按前端字段名查后端字段名 */
export function backendName(frontendKey: string): string | undefined {
  const f = SOURCE_ALL.find(c => c.frontend === frontendKey);
  return f?.backend;
}

/** 按后端字段名查前端字段名 */
export function frontendName(backendKey: string): string | undefined {
  const f = SOURCE_ALL.find(c => c.backend === backendKey);
  return f?.frontend;
}
