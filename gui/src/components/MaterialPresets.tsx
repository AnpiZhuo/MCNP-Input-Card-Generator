/**
 * 材料预设库 — 58 种预设材料，6 个分类
 * 数据来源: app/material_presets.py
 */

export interface PresetItem {
  key: string;
  name: string;
  formula: string;
  desc: string;
}

export const PRESET_CATEGORIES: [string, PresetItem[]][] = [
  ["常见化合物", [
    { key: "water", name: "水 (H₂O)", formula: "H2O: 1", desc: "轻水，密度 ~1.0 g/cm³" },
    { key: "heavy_water", name: "重水 (D₂O)", formula: "H2O: 1", desc: "重水，密度 ~1.11 g/cm³，选择后手动将 ¹H 替换为 ²H" },
    { key: "air", name: "空气 (dry)", formula: "N2: 0.755, O2: 0.232, Ar: 0.013", desc: "干燥空气，密度 ~0.0012 g/cm³" },
    { key: "concrete", name: "混凝土 (普通)", formula: "H: 0.01, O: 0.529, Si: 0.337, Ca: 0.044, Al: 0.034, Na: 0.016, Fe: 0.014, K: 0.013, Mg: 0.003", desc: "普通混凝土，密度 ~2.3 g/cm³" },
    { key: "borated_conc", name: "含硼混凝土", formula: "H: 0.009, B: 0.01, O: 0.525, Si: 0.330, Ca: 0.043, Al: 0.034, Na: 0.016, Fe: 0.014, K: 0.013, Mg: 0.003", desc: "含硼混凝土，密度 ~2.3 g/cm³" },
    { key: "polyethylene", name: "聚乙烯 (PE)", formula: "C2H4: 1", desc: "聚乙烯，密度 ~0.93 g/cm³" },
    { key: "borated_pe", name: "含硼聚乙烯 (BPE)", formula: "C2H4: 0.95, B: 0.05", desc: "5% 硼聚乙烯，密度 ~0.95 g/cm³" },
    { key: "paraffin", name: "石蜡", formula: "C25H52: 1", desc: "石蜡，密度 ~0.9 g/cm³" },
    { key: "pmma", name: "有机玻璃 (PMMA)", formula: "C5H8O2: 1", desc: "有机玻璃/亚克力，密度 ~1.18 g/cm³" },
    { key: "teflon", name: "特氟龙 (PTFE)", formula: "C2F4: 1", desc: "聚四氟乙烯，密度 ~2.2 g/cm³" },
    { key: "pvc", name: "聚氯乙烯 (PVC)", formula: "C2H3Cl: 1", desc: "PVC，密度 ~1.4 g/cm³" },
    { key: "scintillator", name: "塑料闪烁体", formula: "C10H11: 1", desc: "塑料闪烁体，密度 ~1.03 g/cm³" },
  ]],
  ["纯元素", [
    { key: "h", name: "氢 (H)", formula: "H: 1", desc: "密度 ~0.000089 g/cm³ (气态)" },
    { key: "be", name: "铍 (Be)", formula: "Be: 1", desc: "密度 ~1.85 g/cm³" },
    { key: "b", name: "硼 (B)", formula: "B: 1", desc: "天然硼，密度 ~2.34 g/cm³" },
    { key: "c", name: "碳 (C, 石墨)", formula: "C: 1", desc: "石墨，密度 ~1.7 g/cm³" },
    { key: "al", name: "铝 (Al)", formula: "Al: 1", desc: "密度 ~2.7 g/cm³" },
    { key: "fe", name: "铁 (Fe)", formula: "Fe: 1", desc: "密度 ~7.87 g/cm³" },
    { key: "ni", name: "镍 (Ni)", formula: "Ni: 1", desc: "密度 ~8.9 g/cm³" },
    { key: "cu", name: "铜 (Cu)", formula: "Cu: 1", desc: "密度 ~8.96 g/cm³" },
    { key: "w", name: "钨 (W)", formula: "W: 1", desc: "密度 ~19.3 g/cm³" },
    { key: "pb", name: "铅 (Pb)", formula: "Pb: 1", desc: "密度 ~11.34 g/cm³" },
    { key: "bi", name: "铋 (Bi)", formula: "Bi: 1", desc: "密度 ~9.78 g/cm³" },
    { key: "u_nat", name: "天然铀 (U)", formula: "U: 1", desc: "天然铀，密度 ~19.1 g/cm³" },
  ]],
  ["合金 & 特殊材料", [
    { key: "stainless304", name: "不锈钢 304", formula: "Fe: 0.686, Cr: 0.19, Ni: 0.095, Mn: 0.02, Si: 0.0075, C: 0.0008", desc: "304 不锈钢，密度 ~8.0 g/cm³" },
    { key: "stainless316", name: "不锈钢 316", formula: "Fe: 0.654, Cr: 0.17, Ni: 0.12, Mo: 0.025, Mn: 0.02, Si: 0.0075, C: 0.0008", desc: "316 不锈钢，密度 ~8.0 g/cm³" },
    { key: "carbon_steel", name: "碳钢", formula: "Fe: 0.99, C: 0.01", desc: "碳钢，密度 ~7.85 g/cm³" },
    { key: "lead_glass", name: "铅玻璃", formula: "Pb: 0.55, O: 0.25, Si: 0.15, K: 0.05", desc: "铅玻璃 (辐射屏蔽窗)，密度 ~4.8 g/cm³" },
    { key: "sodium_iodide", name: "NaI 闪烁体", formula: "Na: 0.153, I: 0.847", desc: "NaI(Tl) 探测器，密度 ~3.67 g/cm³" },
    { key: "lif", name: "氟化锂 (LiF)", formula: "LiF: 1", desc: "LiF 热释光剂量计，密度 ~2.64 g/cm³" },
    { key: "caf2", name: "氟化钙 (CaF₂)", formula: "CaF2: 1", desc: "CaF₂ 闪烁体，密度 ~3.18 g/cm³" },
    { key: "bgo", name: "BGO 闪烁体", formula: "Bi4Ge3O12: 1", desc: "锗酸铋 BGO，密度 ~7.13 g/cm³" },
    { key: "csi", name: "碘化铯 (CsI)", formula: "CsI: 1", desc: "CsI 闪烁体，密度 ~4.51 g/cm³" },
    { key: "cdte", name: "碲化镉 (CdTe)", formula: "CdTe: 1", desc: "CdTe 探测器，密度 ~6.2 g/cm³" },
    { key: "hpge", name: "高纯锗 (HPGe)", formula: "Ge: 1", desc: "HPGe 探测器，密度 ~5.32 g/cm³" },
    { key: "brass", name: "黄铜", formula: "Cu: 0.7, Zn: 0.3", desc: "黄铜，密度 ~8.5 g/cm³" },
    { key: "solder", name: "焊锡", formula: "Sn: 0.6, Pb: 0.4", desc: "焊锡，密度 ~9.0 g/cm³" },
    { key: "zircaloy", name: "锆合金 (Zircaloy)", formula: "Zr: 0.98, Sn: 0.015, Fe: 0.002, Cr: 0.001, Ni: 0.001, O: 0.001", desc: "锆合金，密度 ~6.55 g/cm³" },
    { key: "inconel", name: "因科镍 (Inconel)", formula: "Ni: 0.58, Cr: 0.21, Fe: 0.10, Mo: 0.08, Nb: 0.02, Ti: 0.01", desc: "Inconel 625，密度 ~8.4 g/cm³" },
  ]],
  ["屏蔽材料", [
    { key: "pb_shield", name: "铅屏蔽", formula: "Pb: 1", desc: "纯铅屏蔽，密度 ~11.34 g/cm³" },
    { key: "w_shield", name: "钨屏蔽", formula: "W: 1", desc: "钨屏蔽，密度 ~19.3 g/cm³" },
    { key: "fe_shield", name: "铁屏蔽", formula: "Fe: 1", desc: "铁屏蔽，密度 ~7.87 g/cm³" },
    { key: "conc_shield", name: "混凝土屏蔽", formula: "H: 0.01, O: 0.529, Si: 0.337, Ca: 0.044, Al: 0.034, Na: 0.016, Fe: 0.014, K: 0.013, Mg: 0.003", desc: "普通混凝土屏蔽，密度 ~2.3 g/cm³" },
    { key: "depleted_u", name: "贫铀 (DU)", formula: "U: 1", desc: "贫化铀，密度 ~19.1 g/cm³" },
  ]],
  ["组织等效材料", [
    { key: "icru_soft", name: "ICRU 软组织", formula: "H: 0.102, C: 0.143, N: 0.034, O: 0.708, Na: 0.002, P: 0.003, S: 0.003, Cl: 0.002, K: 0.003", desc: "ICRU 四元素软组织，密度 ~1.0 g/cm³" },
    { key: "icru_bone", name: "ICRU 骨骼", formula: "H: 0.034, C: 0.155, N: 0.042, O: 0.435, Na: 0.002, Mg: 0.002, P: 0.103, S: 0.003, Ca: 0.225", desc: "ICRU 骨骼 (皮质骨)，密度 ~1.85 g/cm³" },
    { key: "icru_lung", name: "ICRU 肺组织", formula: "H: 0.101, C: 0.102, N: 0.028, O: 0.756, Na: 0.002, P: 0.001, S: 0.002, Cl: 0.003, K: 0.002, Ca: 0.002, Mg: 0.001, Fe: 0.001", desc: "ICRU 肺组织，密度 ~0.26 g/cm³" },
    { key: "a150", name: "A-150 组织等效塑料", formula: "H: 0.101, C: 0.775, N: 0.035, O: 0.052, F: 0.017, Ca: 0.018", desc: "A-150 组织等效塑料，密度 ~1.12 g/cm³" },
  ]],
  ["中子慢化/吸收", [
    { key: "boron_carbide", name: "碳化硼 (B₄C)", formula: "B4C: 1", desc: "碳化硼，密度 ~2.52 g/cm³" },
    { key: "cadmium", name: "镉 (Cd)", formula: "Cd: 1", desc: "镉 (热中子吸收体)，密度 ~8.65 g/cm³" },
    { key: "gd", name: "钆 (Gd)", formula: "Gd: 1", desc: "钆 (热中子吸收体)，密度 ~7.9 g/cm³" },
    { key: "lif_enriched", name: "⁶LiF (富集锂)", formula: "Li: 0.268, F: 0.732", desc: "富集⁶Li 的 LiF，密度 ~2.64 g/cm³" },
  ]],
];

/** 拍平成 key→item 映射 */
const flat: Record<string, PresetItem> = {};
for (const [, items] of PRESET_CATEGORIES) {
  for (const item of items) flat[item.key] = item;
}
export const PRESETS = flat;
export type PresetKey = keyof typeof PRESETS;
