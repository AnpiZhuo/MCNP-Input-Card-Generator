"""
材料预设库：常用材料的化学式/核素组成定义
每种材料提供 formula（化学式，用于 pymcnp from_formula）或 zaids（手动 ZAID 列表）
"""

PRESET_CATEGORIES = [
    ("常见化合物", [
        ("water",        "水 (H₂O)",        "H2O: 1",                       "轻水，密度 ~1.0 g/cm³"),
        ("heavy_water",  "重水 (D₂O)",      "D2O: 1",                       "重水，密度 ~1.11 g/cm³"),
        ("air",          "空气 (dry)",       "N2: 0.755, O2: 0.232, Ar: 0.013", "干燥空气，密度 ~0.0012 g/cm³"),
        ("concrete",     "混凝土 (普通)",     "H: 0.01, O: 0.529, Si: 0.337, Ca: 0.044, Al: 0.034, Na: 0.016, Fe: 0.014, K: 0.013, Mg: 0.003", "普通混凝土，密度 ~2.3 g/cm³"),
        ("borated_conc", "含硼混凝土",        "H: 0.009, B: 0.01, O: 0.525, Si: 0.330, Ca: 0.043, Al: 0.034, Na: 0.016, Fe: 0.014, K: 0.013, Mg: 0.003", "含硼混凝土，密度 ~2.3 g/cm³"),
        ("polyethylene", "聚乙烯 (PE)",       "C2H4: 1",                     "聚乙烯，密度 ~0.93 g/cm³"),
        ("borated_pe",   "含硼聚乙烯 (BPE)",  "C2H4: 0.95, B: 0.05",        "5% 硼聚乙烯，密度 ~0.95 g/cm³"),
        ("paraffin",     "石蜡",              "C25H52: 1",                   "石蜡，密度 ~0.9 g/cm³"),
        ("pmma",         "有机玻璃 (PMMA)",   "C5H8O2: 1",                   "有机玻璃/亚克力，密度 ~1.18 g/cm³"),
        ("teflon",       "特氟龙 (PTFE)",     "C2F4: 1",                     "聚四氟乙烯，密度 ~2.2 g/cm³"),
        ("pvc",          "聚氯乙烯 (PVC)",    "C2H3Cl: 1",                   "PVC，密度 ~1.4 g/cm³"),
        ("scintillator", "塑料闪烁体",        "C10H11: 1",                   "塑料闪烁体 (乙烯基甲苯基)，密度 ~1.03 g/cm³"),
    ]),
    ("纯元素", [
        ("h",           "氢 (H)",            "H: 1",                         "密度 ~0.000089 g/cm³ (气态)"),
        ("be",          "铍 (Be)",           "Be: 1",                        "密度 ~1.85 g/cm³"),
        ("b",           "硼 (B)",            "B: 1",                         "天然硼，密度 ~2.34 g/cm³"),
        ("c",           "碳 (C, 石墨)",      "C: 1",                         "石墨，密度 ~1.7 g/cm³"),
        ("al",          "铝 (Al)",           "Al: 1",                        "密度 ~2.7 g/cm³"),
        ("fe",          "铁 (Fe)",           "Fe: 1",                        "密度 ~7.87 g/cm³"),
        ("ni",          "镍 (Ni)",           "Ni: 1",                        "密度 ~8.9 g/cm³"),
        ("cu",          "铜 (Cu)",           "Cu: 1",                        "密度 ~8.96 g/cm³"),
        ("w",           "钨 (W)",            "W: 1",                         "密度 ~19.3 g/cm³"),
        ("pb",          "铅 (Pb)",           "Pb: 1",                        "密度 ~11.34 g/cm³"),
        ("bi",          "铋 (Bi)",           "Bi: 1",                        "密度 ~9.78 g/cm³"),
        ("u_nat",       "天然铀 (U)",        "U: 1",                         "天然铀，密度 ~19.1 g/cm³"),
    ]),
    ("合金 & 特殊材料", [
        ("stainless304","不锈钢 304",        "Fe: 0.694, Cr: 0.19, Ni: 0.095, Mn: 0.02, Si: 0.001", "304 不锈钢，密度 ~8.0 g/cm³"),
        ("stainless316","不锈钢 316",        "Fe: 0.654, Cr: 0.17, Ni: 0.12, Mo: 0.025, Mn: 0.02, Si: 0.01, C: 0.001", "316 不锈钢，密度 ~8.0 g/cm³"),
        ("carbon_steel","碳钢",              "Fe: 0.99, C: 0.01",           "碳钢，密度 ~7.85 g/cm³"),
        ("lead_glass",  "铅玻璃",            "Pb: 0.55, O: 0.25, Si: 0.15, K: 0.05", "铅玻璃 (辐射屏蔽窗)，密度 ~4.8 g/cm³"),
        ("sodium_iodide","NaI 闪烁体",       "Na: 0.153, I: 0.847",         "NaI(Tl) 探测器，密度 ~3.67 g/cm³"),
        ("lif",         "氟化锂 (LiF)",      "LiF: 1",                       "LiF 热释光剂量计，密度 ~2.64 g/cm³"),
        ("caf2",        "氟化钙 (CaF₂)",     "CaF2: 1",                      "CaF₂ 闪烁体，密度 ~3.18 g/cm³"),
        ("bgo",         "BGO 闪烁体",        "Bi4Ge3O12: 1",                 "锗酸铋 BGO，密度 ~7.13 g/cm³"),
        ("csi",         "碘化铯 (CsI)",      "CsI: 1",                       "CsI 闪烁体，密度 ~4.51 g/cm³"),
        ("cdte",        "碲化镉 (CdTe)",     "CdTe: 1",                      "CdTe 探测器，密度 ~6.2 g/cm³"),
        ("hpge",        "高纯锗 (HPGe)",     "Ge: 1",                        "HPGe 探测器，密度 ~5.32 g/cm³"),
        ("brass",       "黄铜",              "Cu: 0.7, Zn: 0.3",            "黄铜，密度 ~8.5 g/cm³"),
        ("solder",      "焊锡",              "Sn: 0.6, Pb: 0.4",            "焊锡，密度 ~9.0 g/cm³"),
        ("zircaloy",    "锆合金 (Zircaloy)", "Zr: 0.98, Sn: 0.015, Fe: 0.002, Cr: 0.001, Ni: 0.001, O: 0.001", "锆合金，密度 ~6.55 g/cm³"),
        ("inconel",     "因科镍 (Inconel)",  "Ni: 0.58, Cr: 0.21, Fe: 0.10, Mo: 0.08, Nb: 0.02, Ti: 0.01", "Inconel 625，密度 ~8.4 g/cm³"),
    ]),
    ("屏蔽材料", [
        ("pb_shield",   "铅屏蔽",            "Pb: 1",                        "纯铅屏蔽，密度 ~11.34 g/cm³"),
        ("w_shield",    "钨屏蔽",            "W: 1",                         "钨屏蔽，密度 ~19.3 g/cm³"),
        ("fe_shield",   "铁屏蔽",            "Fe: 1",                        "铁屏蔽，密度 ~7.87 g/cm³"),
        ("conc_shield", "混凝土屏蔽",         "H: 0.01, O: 0.529, Si: 0.337, Ca: 0.044, Al: 0.034, Na: 0.016, Fe: 0.014, K: 0.013, Mg: 0.003", "普通混凝土屏蔽，密度 ~2.3 g/cm³"),
        ("depleted_u",  "贫铀 (DU)",          "U238: 0.997, U235: 0.003",    "贫化铀，密度 ~19.1 g/cm³"),
    ]),
    ("组织等效材料", [
        ("icru_soft",  "ICRU 软组织",        "H: 0.102, C: 0.143, N: 0.034, O: 0.708, Na: 0.002, P: 0.003, S: 0.003, Cl: 0.002, K: 0.003", "ICRU 四元素软组织，密度 ~1.0 g/cm³"),
        ("icru_bone",  "ICRU 骨骼",          "H: 0.034, C: 0.155, N: 0.042, O: 0.435, Na: 0.002, Mg: 0.002, P: 0.103, S: 0.003, Ca: 0.225", "ICRU 骨骼 (皮质骨)，密度 ~1.85 g/cm³"),
        ("icru_lung",  "ICRU 肺组织",        "H: 0.101, C: 0.102, N: 0.028, O: 0.756, Na: 0.002, P: 0.001, S: 0.002, Cl: 0.003, K: 0.002, Ca: 0.002, Mg: 0.001, Fe: 0.001", "ICRU 肺组织，密度 ~0.26 g/cm³"),
        ("a150",       "A-150 组织等效塑料",  "H: 0.101, C: 0.775, N: 0.035, O: 0.052, F: 0.017, Ca: 0.018", "A-150 组织等效塑料，密度 ~1.12 g/cm³"),
    ]),
    ("中子慢化/吸收", [
        ("boron_carbide", "碳化硼 (B₄C)",    "B4C: 1",                       "碳化硼，密度 ~2.52 g/cm³"),
        ("cadmium",       "镉 (Cd)",         "Cd: 1",                        "镉 (热中子吸收体)，密度 ~8.65 g/cm³"),
        ("gd",            "钆 (Gd)",         "Gd: 1",                        "钆 (热中子吸收体)，密度 ~7.9 g/cm³"),
        ("lif_enriched",  "⁶LiF (富集锂)",   "Li: 0.268, F: 0.732",         "富集⁶Li 的 LiF (需手动指定⁶Li丰度)，密度 ~2.64 g/cm³"),
    ]),
]


def get_all_presets() -> list[dict]:
    """返回所有预设的扁平列表"""
    result = []
    for category, items in PRESET_CATEGORIES:
        for key, name, formula, desc in items:
            result.append({
                "key": key,
                "name": name,
                "category": category,
                "formula": formula,
                "description": desc,
            })
    return result


def get_preset_by_key(key: str) -> dict | None:
    """按 key 查找预设"""
    for preset in get_all_presets():
        if preset["key"] == key:
            return preset
    return None
