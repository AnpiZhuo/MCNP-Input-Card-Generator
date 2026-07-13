"""
项目文件保存/加载与序列化辅助
"""

import json
import dataclasses

from app.models import (
    BasicSettings, CellData, MaterialData, MaterialRow,
    SourceData, TallySettings, TallyDefinition, AdvancedSettings, DeckData,
)


def deck_to_dict(deck: DeckData) -> dict:
    """DeckData → JSON 可序列化字典"""
    def _convert(obj):
        if dataclasses.is_dataclass(obj):
            return {k: _convert(v) for k, v in dataclasses.asdict(obj).items()}
        elif isinstance(obj, list):
            return [_convert(x) for x in obj]
        else:
            return obj
    return _convert(deck)


def _parse_tally_data(raw: dict) -> dict:
    """从 JSON 字典解析 TallySettings 数据，处理嵌套的 TallyDefinition 和旧版兼容。

    新版格式: {"tallies": [{"type": "F1", "number": 1, "particles": ["n"], "params": ""}, ...]}
    旧版格式: {"f1_enabled": True, "f1_surface": "1", ...}
    """
    # 白名单：TallySettings 当前接受的所有字段
    fields = {
        "tallies", "e_min", "e_max", "e_bins", "e_log",
        "e_custom_enabled", "e_custom_text", "e_cards_text",
        "cut_n_t", "cut_n_e", "cut_n_raw",
        "cut_n_wc1", "cut_n_wc2", "cut_n_swtm",
        "cut_p_t", "cut_p_e", "cut_p_raw",
        "cut_p_wc1", "cut_p_wc2", "cut_p_swtm",
        "cut_e_t", "cut_e_e", "cut_e_raw",
        "cut_e_wc1", "cut_e_wc2", "cut_e_swtm",
        "cut_h_t", "cut_h_e", "cut_h_raw",
        "cut_h_wc1", "cut_h_wc2", "cut_h_swtm",
        "cut_he_t", "cut_he_e", "cut_he_raw",
        "cut_he_wc1", "cut_he_wc2", "cut_he_swtm",
    }
    result = {k: v for k, v in raw.items() if k in fields}

    # 嵌套 dataclass 反序列化
    if "tallies" in result:
        result["tallies"] = [
            TallyDefinition(**t) if not isinstance(t, TallyDefinition) else t
            for t in result["tallies"]
        ]
    else:
        result["tallies"] = []

    return result


def deck_from_dict(data: dict) -> DeckData:
    """JSON 字典 → DeckData"""
    basic = BasicSettings(**(data.get("basic") or {}))
    tally_data = _parse_tally_data(data.get("tally") or {})
    tally = TallySettings(**tally_data)
    adv = AdvancedSettings(**(data.get("adv") or {}))
    cells = [CellData(**c) for c in data.get("cells", [])]
    mats = []
    for m in data.get("materials", []):
        rows = [MaterialRow(**r) for r in m.get("rows", [])]
        mats.append(MaterialData(
            number=m.get("number", 0), rows=rows,
            comment=m.get("comment", ""),
            formula=m.get("formula", ""),
            options=m.get("options", ""),
            mt_card=m.get("mt_card", ""),
        ))
    sources = [SourceData(**s) for s in data.get("sources", [])]
    return DeckData(
        basic=basic, surfaces=data.get("surfaces", ""),
        cells=cells, materials=mats, sources=sources,
        tally=tally, adv=adv,
    )


def save_project_file(deck: DeckData, path: str):
    """将 DeckData 写入 JSON 文件"""
    data = deck_to_dict(deck)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_project_file(path: str) -> dict:
    """从 JSON 文件读取并返回字典"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
