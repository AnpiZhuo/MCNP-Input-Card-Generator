import React, { createContext, useContext, useState, useCallback } from "react";
import type { GridValue } from "./gridState";

/* 数据模型 */
export interface Nuclide { zaid: string; fraction: string }
export interface MaterialData { number: number; comment: string; nuclides: Nuclide[]; density: string; options: string; mt_card: string }
export interface CellData { number: number; material: string; density: string; surface_expr: string; imp_n: string; imp_p: string; imp_e: string; vol: string; pwt: string; ext: string; fcl: string; u: string; fill: string; lat: string; trcl: string; tmp: string; other_params: string; render: boolean; comment: string }
export interface SourceItem {
  number: number; par: string; erg: string;
  pos_x: string; pos_y: string; pos_z: string;
  wgt: string; dir_: string; cel: string; tme: string;
  vec: string; axs: string; rad: string; ext: string;
  sur: string; nrm: string; tr: string;
  ccc: string; ara: string; rate: string;
  prob: string;
}
export interface TallyDef { type: string; number: number; particle: string; params: string; enableEn: boolean; enableTn: boolean }

/* ── 源项结构化分布（对齐 MCNP 源分布卡说明.md）── */
export interface SiEntry { type: "L" | "H" | "A" | "S" | "Q" | "T" | "F"; values: string[] }
export interface SpEntry { type: "D" | "C" | "V" | ""; values: string[]; fnCode: string; fnParams: string[] }
export interface SbEntry { type: "D" | "-21" | "-31"; values: string[] }
export interface DsEntry { type: "H" | "L" | "S" | "T" | "Q"; param: string; distributionIds: string[] }
export interface DistEntry {
  id: number;
  paramRef: string;          // 引用的 SDEF 变量（ERG/POS/PAR...）
  si: SiEntry;
  sp: SpEntry;
  sb: SbEntry | null;
  ds: DsEntry | null;
  auto: boolean;
}
export type SourceTemplateType =
  | "point" | "multi_point" | "sphere" | "cylinder" | "volume_xyz"
  | "volume_cel" | "surface" | "energy" | "directional" | "free";
export interface SswFields { surf: string; sym: string; pty: string; cel: string }
export interface SsrFields { surf: string; mode: string; cel: string; pty: string; col: string; wgt: string; tr: string; psc: string }

export interface DeckData {
  basic: Record<string, any>;
  surfaces: string; tr_cards: string;
  cells: CellData[];
  materials: MaterialData[];
  sources: SourceItem[];
  tallies: TallyDef[];
  tally: Record<string, any>;
  grids: Record<string, GridValue>;  // E0/En/T0/Tn 网格单一权威（prefix: "e"|"t"|"e25"|"t85"...）
  adv: Record<string, any>;
  // Source mode state
  sourceMode: "fixed" | "sdef" | "kcode" | "surface";
  sdefFields: Record<string, string>;
  sdefRawText: string;
  sourceTemplate: SourceTemplateType;   // 当前源类型模板
  distributions: DistEntry[];           // 结构化 SI/SP/SB/DS 分布
  sswFields: SswFields;                 // SSW 写面源
  ssrFields: SsrFields;                 // SSR 读面源
  kcodeFields: Record<string, string>;
  ksrcPoints: string;
  // Raw text overrides (for TextModeSection)
  rawOverrides: Record<string, string>;  // key: "materials"|"cells"|"sdef"|"tally"|"phys"|"e0"|"cut"
}

const DEFAULT: DeckData = {
  basic: { title: "", mode_n: false, mode_p: false, mode_e: false, nps: "", ctme: "", phys_fis: true },
  surfaces: "", tr_cards: "", cells: [], materials: [], sources: [], tallies: [],
  tally: {}, grids: {}, adv: {},
  sourceMode: "fixed", sdefFields: {}, sdefRawText: "",
  sourceTemplate: "free", distributions: [],
  sswFields: { surf: "", sym: "", pty: "", cel: "" },
  ssrFields: { surf: "", mode: "", cel: "", pty: "", col: "", wgt: "", tr: "", psc: "" },
  kcodeFields: {}, ksrcPoints: "", rawOverrides: {},
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
  // 加载外部 deck 时兜底：结构损坏/解析出错则回退默认，避免二次启动白屏
  const loadDeck = useCallback((d: DeckData) => {
    try {
      setDeck({ ...DEFAULT, ...(d && typeof d === "object" ? d : {}) });
    } catch (e) {
      console.warn("[Deck] loadDeck 失败，重置为默认", e);
      setDeck(DEFAULT);
    }
  }, []);
  return <Ctx.Provider value={{ deck, patch, loadDeck }}>{children}</Ctx.Provider>;
}
