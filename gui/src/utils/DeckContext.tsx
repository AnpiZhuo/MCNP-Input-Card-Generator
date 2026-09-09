import React, { createContext, useContext, useState, useCallback } from "react";
import type { GridValue } from "./gridState";
import { migrateLegacySourceKeys } from "./sourceAdv";

/* 数据模型 */
export interface Nuclide { zaid: string; fraction: string }
/** 材料行：核素行或原样条件/预处理器行（判别联合，语义由 kind 决定） */
export type MaterialRow =
  | { kind: "nuclide"; zaid: string; fraction: string }
  | { kind: "raw"; text: string };
export interface MaterialData { number: number; comment: string; nuclides: MaterialRow[]; density: string; options: string; mt_card: string }
export interface CellData { number: number; material: string; density: string; surface_expr: string; imp_n: string; imp_p: string; imp_e: string; vol: string; pwt: string; ext: string; fcl: string; u: string; fill: string; lat: string; trcl: string; tmp: string; other_params: string; render: boolean; fill_grid: string; comment: string }
/** 栅元行：真正的栅元或原样条件/预处理器行（判别联合） */
export type CellRow =
  | { kind: "cell"; cell: CellData }
  | { kind: "raw"; text: string };
export interface SourceItem {
  number: number; par: string; erg: string;
  pos_x: string; pos_y: string; pos_z: string;
  wgt: string; dir_: string; cel: string; tme: string;
  vec: string; axs: string; rad: string; ext: string;
  sur: string; nrm: string; tr: string;
  ccc: string; ara: string; rate: string;
  prob: string;
}
export interface TallyDef { type: string; number: number; particle: string; params: string; multiplier?: string; enableEn: boolean; enableTn: boolean }

/* ── 源项结构化分布（对齐 MCNP 源分布卡说明.md；v2 双态：raw 原文 ↔ structured 表单）── */
/** SI 类型；"" = 无字母（MCNP 缺省 H 直方图，不得再回填 L） */
export interface SiEntry { type: "" | "L" | "H" | "A" | "S" | "Q" | "T" | "F"; values: string[] }
export interface SpEntry { type: "" | "D" | "C" | "V"; values: string[]; fnCode: string; fnParams: string[] }
export interface SbEntry { type: "D" | "-21" | "-31"; values: string[] }
export interface DsEntry { type: "H" | "L" | "S" | "T" | "Q"; param: string; distributionIds: string[] }
export interface DistEntry {
  id: number;
  paramRef: string;          // 引用的 SDEF 变量（ERG/POS/PAR...）
  si: SiEntry | null;
  sp: SpEntry | null;
  sb: SbEntry | null;
  ds: DsEntry | null;
  sc?: string;               // SCn 源注释卡文字（可选，导入自 inp 时携带）
  auto: boolean;
  // ── v2 双态（app/generator/distributions.py schema）──
  /** "raw" = 直接形态（导入文件时逐字原文权威）；"structured"/缺省 = 规范形态（新建默认） */
  editMode?: "raw" | "structured";
  /** 原文行（\n 分隔；editMode=raw 时发射逐字直通） */
  rawText?: string;
}
export type SourceTemplateType =
  | "point" | "multi_point" | "free";
export interface SswFields { surf: string; sym: string; pty: string; cel: string }
export interface SsrFields { surf: string; mode: string; cel: string; pty: string; col: string; wgt: string; tr: string; psc: string }

export interface DeckData {
  basic: Record<string, any>;
  surfaces: string; tr_cards: string;
  cells: CellRow[];
  materials: MaterialData[];
  sources: SourceItem[];
  tallies: TallyDef[];
  tally: Record<string, any>;
  grids: Record<string, GridValue>;  // E0/En/T0/Tn 网格单一权威（prefix: "e"|"t"|"e25"|"t85"...）
  adv: Record<string, any>;             // 源/高级唯一权威（后端模型 adv：source_mode + sdef_*/kcode_*/ssw_*/ssr_*/ksrc_points/sdef_distributions…）
  sourceTemplate: SourceTemplateType;   // 当前源类型模板（纯 UI 向导分组；不参与生成）
  // Raw text overrides (for TextModeSection)
  rawOverrides: Record<string, string>;  // key: "materials"|"cells"|"sdef"|"tally"|"phys"|"e0"|"cut"
  // 各标签页当前是否处于文本模式（生成时决定用文本还是表单数据）
  textMode: Record<string, boolean>;     // key: "materials"|"cells"|"tally"|"sdef"
  // U 组头文字（项9，snake_case 与后端一致）：universeComments[U] = 用户自定义组头文本。
  // 可选（旧 deck / 旧 loadDeck 数据无此字段，向后兼容；DEFAULT 恒提供 {}）
  universeComments?: Record<string, string>;
  /** 栅元封闭性检测结果缓存（GeometryTab 自检用，不参与 INP 生成） */
  cellClosureReport?: Record<string, {status:string;volume?:number|null;aabb?:any;infinite_axes?:string[]}> | null;
}

const DEFAULT: DeckData = {
  basic: { title: "", mode_n: false, mode_p: false, mode_e: false, nps: "", ctme: "", phys_fis: true },
  surfaces: "", tr_cards: "", cells: [], materials: [], sources: [], tallies: [],
  tally: {}, grids: {}, adv: {},
  sourceTemplate: "free",
  rawOverrides: {}, textMode: {},
  universeComments: {},
  cellClosureReport: null,
};

interface Ctx {
  deck: DeckData;
  patch: (partial: Partial<DeckData>) => void;
  loadDeck: (d: DeckData) => void;
}

const Ctx = createContext<Ctx>({ deck: DEFAULT, patch: () => {}, loadDeck: () => {} });
export const useDeck = () => useContext(Ctx);

export function DeckProvider({ children }: { children: React.ReactNode }) {
  const [deck, setDeck] = useState(DEFAULT);
  const patch = useCallback((p: Partial<DeckData>) => setDeck(d => ({ ...d, ...p })), []);
  // 加载外部 deck 时兜底：结构损坏/解析出错则回退默认，避免二次启动白屏。
  // 统一迁移入口：restore / import / AI 回显都经 loadDeck → 旧顶层源中间态折叠进 deck.adv。
  const loadDeck = useCallback((d: DeckData) => {
    try {
      const migrated = migrateLegacySourceKeys(d);
      setDeck({ ...DEFAULT, ...(migrated && typeof migrated === "object" ? (migrated as DeckData) : {}) });
    } catch (e) {
      console.warn("[Deck] loadDeck 失败，重置为默认", e);
      setDeck(DEFAULT);
    }
  }, []);
  return <Ctx.Provider value={{ deck, patch, loadDeck }}>{children}</Ctx.Provider>;
}
