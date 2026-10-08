/**
 * 材料预设库 — 49 种预设材料，6 个分类（另有 PNNL-15870 精选 48 种同位素级预设，
 * 见 ../data/pnnlPresets，经 PNNL_CATEGORIES 合并进本表）
 * density: 负值 = MCNP 质量密度 (g/cm³)，两位小数（空气/气体保留足够精度）
 * 已移除非天然同位素预设（重水 D₂O / 贫铀 / 富集⁶Li LiF），它们的 formula 展开是天然同位素、与名称不符
 * 组织等效材料（icru_*）元素组成对齐 NIST X-Ray Mass Attenuation Table 2（源 ICRU Report 44）
 */

import { PNNL_CATEGORIES } from "../data/pnnlPresets";

export interface PresetItem {
  key: string;
  name: string;
  formula: string;
  desc: string;
  /** MCNP 质量密度 (g/cm³，负值)。用户预设可能没有，内置预设都有 */
  density?: string;
  /** 同位素级 ZAID+份额（负号=质量份额）。有则选预设直接填「手动 ZAID」模式 */
  rows?: [string, string][];
  /** 额外 MCNP 选项（nlib=.66c 等）。可随预设保存/导入导出 */
  options?: string;
  /** 热中子 MT 卡（lwtr.10t）。可随预设保存/导入导出 */
  mtCard?: string;
}

export const PRESET_CATEGORIES: [string, PresetItem[]][] = [
  ["常见化合物", [
    { key: "water", name: "水 (H₂O)", formula: "H2O: 1", desc: "轻水（20 °C），密度 1.00 g/cm³", density: "-1.00" },
    { key: "air", name: "空气 (dry)", formula: "N2: 0.755268, O2: 0.231781, Ar: 0.012827, C: 0.000124", desc: "干燥空气（近海平面，NIST 质量份额；20 °C、1 atm = 1.205e-3 g/cm³）", density: "-0.0012" },
    { key: "concrete", name: "混凝土 (普通)", formula: "H: 0.022100, C: 0.002484, O: 0.574931, Na: 0.015208, Mg: 0.001266, Al: 0.019953, Si: 0.304627, K: 0.010045, Ca: 0.042951, Fe: 0.006435", desc: "普通混凝土（NIST 质量衰减表 2 = PNNL-15870 记录 107，质量份额），密度 2.30 g/cm³", density: "-2.30" },
    { key: "borated_conc", name: "含硼混凝土", formula: "H: 0.021879, C: 0.002459, O: 0.569181, Na: 0.015056, Mg: 0.001253, Al: 0.019753, Si: 0.301581, K: 0.009945, Ca: 0.042521, Fe: 0.006371, B: 0.01", desc: "含硼混凝土（NIST 普通混凝土 + 1 wt% B 换算），密度 ~2.30 g/cm³", density: "-2.30" },
    { key: "polyethylene", name: "聚乙烯 (PE)", formula: "C2H4: 1", desc: "聚乙烯，密度 ~0.93 g/cm³", density: "-0.93" },
    { key: "borated_pe", name: "含硼聚乙烯 (BPE)", formula: "C2H4: 0.95, B: 0.05", desc: "5% 硼聚乙烯，密度 ~0.95 g/cm³", density: "-0.95" },
    { key: "paraffin", name: "石蜡", formula: "C25H52: 1", desc: "石蜡，密度 ~0.9 g/cm³", density: "-0.90" },
    { key: "pmma", name: "有机玻璃 (PMMA)", formula: "C5H8O2: 1", desc: "有机玻璃/亚克力，密度 ~1.18 g/cm³", density: "-1.18" },
    { key: "teflon", name: "特氟龙 (PTFE)", formula: "C2F4: 1", desc: "聚四氟乙烯，密度 ~2.2 g/cm³", density: "-2.20" },
    { key: "pvc", name: "聚氯乙烯 (PVC)", formula: "C2H3Cl: 1", desc: "PVC，密度 ~1.4 g/cm³", density: "-1.40" },
    { key: "scintillator", name: "塑料闪烁体", formula: "C10H11: 1", desc: "塑料闪烁体 (EJ-200/BC-400)，密度 ~1.02 g/cm³", density: "-1.02" },
  ]],
  ["纯元素", [
    { key: "h", name: "氢 (H)", formula: "H: 1", desc: "氢气 H₂（20 °C、1 atm 文献值 8.3748e-5 g/cm³；0 °C 为 8.99e-5）", density: "-0.000083748" },
    { key: "be", name: "铍 (Be)", formula: "Be: 1", desc: "密度 ~1.85 g/cm³", density: "-1.85" },
    { key: "b", name: "硼 (B)", formula: "B: 1", desc: "天然硼，密度 ~2.34 g/cm³", density: "-2.34" },
    { key: "c", name: "碳 (C, 石墨)", formula: "C: 1", desc: "石墨，密度 ~1.7 g/cm³", density: "-1.70" },
    { key: "al", name: "铝 (Al)", formula: "Al: 1", desc: "密度 ~2.7 g/cm³", density: "-2.70" },
    { key: "fe", name: "铁 (Fe)", formula: "Fe: 1", desc: "密度 ~7.87 g/cm³", density: "-7.87" },
    { key: "ni", name: "镍 (Ni)", formula: "Ni: 1", desc: "密度 ~8.9 g/cm³", density: "-8.90" },
    { key: "cu", name: "铜 (Cu)", formula: "Cu: 1", desc: "密度 ~8.96 g/cm³", density: "-8.96" },
    { key: "w", name: "钨 (W)", formula: "W: 1", desc: "密度 ~19.3 g/cm³", density: "-19.30" },
    { key: "pb", name: "铅 (Pb)", formula: "Pb: 1", desc: "密度 ~11.34 g/cm³", density: "-11.34" },
    { key: "bi", name: "铋 (Bi)", formula: "Bi: 1", desc: "密度 ~9.78 g/cm³", density: "-9.78" },
    { key: "u_nat", name: "天然铀 (U)", formula: "U: 1", desc: "天然铀金属，18.95 g/cm³（PNNL-15870 记录 385 / NIST）", density: "-18.95" },
  ]],
  ["合金 & 特殊材料", [
    { key: "stainless304", name: "不锈钢 304", formula: "Fe: 0.686, Cr: 0.19, Ni: 0.095, Mn: 0.02, Si: 0.0075, C: 0.0008", desc: "304 不锈钢，密度 ~8.0 g/cm³", density: "-8.00" },
    { key: "stainless316", name: "不锈钢 316", formula: "Fe: 0.654, Cr: 0.17, Ni: 0.12, Mo: 0.025, Mn: 0.02, Si: 0.0075, C: 0.0008", desc: "316 不锈钢，密度 ~8.0 g/cm³", density: "-8.00" },
    { key: "carbon_steel", name: "碳钢", formula: "Fe: 0.99, C: 0.01", desc: "碳钢，密度 ~7.85 g/cm³", density: "-7.85" },
    { key: "lead_glass", name: "铅玻璃", formula: "Pb: 0.5650, O: 0.2297, Si: 0.1540, K: 0.0513", desc: "铅玻璃（≈60.9% PbO + 33.0% SiO₂ + 6.2% K₂O 换算，屏蔽窗），密度 ~4.8 g/cm³", density: "-4.80" },
    { key: "sodium_iodide", name: "NaI 闪烁体", formula: "Na: 0.153, I: 0.847", desc: "NaI(Tl) 探测器，密度 ~3.67 g/cm³", density: "-3.67" },
    { key: "lif", name: "氟化锂 (LiF)", formula: "LiF: 1", desc: "LiF 热释光剂量计，密度 ~2.64 g/cm³", density: "-2.64" },
    { key: "caf2", name: "氟化钙 (CaF₂)", formula: "CaF2: 1", desc: "CaF₂ 闪烁体，密度 ~3.18 g/cm³", density: "-3.18" },
    { key: "bgo", name: "BGO 闪烁体", formula: "Bi4Ge3O12: 1", desc: "锗酸铋 BGO，密度 ~7.13 g/cm³", density: "-7.13" },
    { key: "csi", name: "碘化铯 (CsI)", formula: "CsI: 1", desc: "CsI 闪烁体，密度 ~4.51 g/cm³", density: "-4.51" },
    { key: "cdte", name: "碲化镉 (CdTe)", formula: "CdTe: 1", desc: "CdTe 探测器，密度 ~6.2 g/cm³", density: "-6.20" },
    { key: "hpge", name: "高纯锗 (HPGe)", formula: "Ge: 1", desc: "HPGe 探测器，密度 ~5.32 g/cm³", density: "-5.32" },
    { key: "brass", name: "黄铜", formula: "Cu: 0.7, Zn: 0.3", desc: "黄铜，密度 ~8.5 g/cm³", density: "-8.50" },
    { key: "solder", name: "焊锡", formula: "Sn: 0.6, Pb: 0.4", desc: "焊锡，密度 ~9.0 g/cm³", density: "-9.00" },
    { key: "zircaloy", name: "锆合金 (Zircaloy)", formula: "Zr: 0.98, Sn: 0.015, Fe: 0.002, Cr: 0.001, Ni: 0.001, O: 0.001", desc: "锆合金，密度 ~6.55 g/cm³", density: "-6.55" },
    { key: "inconel", name: "因科镍 (Inconel)", formula: "Ni: 0.624, Cr: 0.215, Mo: 0.090, Nb: 0.0365, Fe: 0.025, Mn: 0.0025, Si: 0.0025, Al: 0.002, Ti: 0.002, C: 0.0005", desc: "Inconel 625 (UNS N06625)：规格中值 + Ni 余量，密度 ~8.44 g/cm³", density: "-8.44" },
  ]],
  ["屏蔽材料", [
    { key: "pb_shield", name: "铅屏蔽", formula: "Pb: 1", desc: "纯铅屏蔽，密度 ~11.34 g/cm³", density: "-11.34" },
    { key: "w_shield", name: "钨屏蔽", formula: "W: 1", desc: "钨屏蔽，密度 ~19.3 g/cm³", density: "-19.30" },
    { key: "fe_shield", name: "铁屏蔽", formula: "Fe: 1", desc: "铁屏蔽，密度 ~7.87 g/cm³", density: "-7.87" },
    { key: "conc_shield", name: "混凝土屏蔽", formula: "H: 0.022100, C: 0.002484, O: 0.574931, Na: 0.015208, Mg: 0.001266, Al: 0.019953, Si: 0.304627, K: 0.010045, Ca: 0.042951, Fe: 0.006435", desc: "普通混凝土屏蔽（同 NIST 普通混凝土），密度 2.30 g/cm³", density: "-2.30" },
  ]],
  ["组织等效材料", [
    { key: "icru_soft", name: "ICRU 软组织", formula: "H: 0.102, C: 0.143, N: 0.034, O: 0.708, Na: 0.002, P: 0.003, S: 0.003, Cl: 0.002, K: 0.003", desc: "ICRU-44 软组织（9 元素，含 Na/P/S/Cl/K 微量组分），密度 1.06 g/cm³", density: "-1.06" },
    { key: "icru_bone", name: "ICRU 骨骼", formula: "H: 0.034, C: 0.155, N: 0.042, O: 0.435, Na: 0.001, Mg: 0.002, P: 0.103, S: 0.003, Ca: 0.225", desc: "ICRU-44 皮质骨，密度 1.92 g/cm³", density: "-1.92" },
    { key: "icru_lung", name: "ICRU 肺组织", formula: "H: 0.103, C: 0.105, N: 0.031, O: 0.749, Na: 0.002, P: 0.002, S: 0.003, Cl: 0.003, K: 0.002", desc: "ICRU-44 肺组织（含血），密度 1.05 g/cm³；充气肺常按 ~0.26 建模（属 ICRP-89 口径）", density: "-1.05" },
    { key: "a150", name: "A-150 组织等效塑料", formula: "H: 0.101, C: 0.775, N: 0.035, O: 0.052, F: 0.017, Ca: 0.018", desc: "A-150 组织等效塑料（NIST 成分），密度 1.127 g/cm³", density: "-1.127" },
  ]],
  ["中子慢化/吸收", [
    { key: "boron_carbide", name: "碳化硼 (B₄C)", formula: "B4C: 1", desc: "碳化硼，密度 ~2.52 g/cm³", density: "-2.52" },
    { key: "cadmium", name: "镉 (Cd)", formula: "Cd: 1", desc: "镉 (热中子吸收体)，密度 ~8.65 g/cm³", density: "-8.65" },
    { key: "gd", name: "钆 (Gd)", formula: "Gd: 1", desc: "钆 (热中子吸收体)，密度 ~7.9 g/cm³", density: "-7.90" },
  ]],
  ...PNNL_CATEGORIES,
];

/** 拍平成 key→item 映射 */
const flat: Record<string, PresetItem> = {};
for (const [, items] of PRESET_CATEGORIES) {
  for (const item of items) flat[item.key] = item;
}
export const PRESETS = flat;
export type PresetKey = keyof typeof PRESETS;

/** 预设搜索过滤：名称/化学式/描述命中（大小写不敏感）；空关键词返回全量。 */
export function filterPresets(
  categories: [string, PresetItem[]][],
  query: string,
): [string, PresetItem[]][] {
  const q = (query || "").trim().toLowerCase();
  if (!q) return categories;
  return categories
    .map(([cat, items]) => [
      cat,
      items.filter((i) =>
        (i.name + " " + (i.formula || "") + " " + (i.desc || "")).toLowerCase().includes(q)),
    ] as [string, PresetItem[]])
    .filter(([, items]) => items.length > 0);
}
