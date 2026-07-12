"""
项目文件保存/加载与序列化辅助
"""

import json
import dataclasses

from app.models import (
    BasicSettings, CellData, MaterialData, MaterialRow,
    SourceData, TallySettings, AdvancedSettings, DeckData,
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


def deck_from_dict(data: dict) -> DeckData:
    """JSON 字典 → DeckData"""
    basic = BasicSettings(**(data.get("basic") or {}))
    tally = TallySettings(**(data.get("tally") or {}))
    adv = AdvancedSettings(**(data.get("adv") or {}))
    cells = [CellData(**c) for c in data.get("cells", [])]
    mats = []
    for m in data.get("materials", []):
        rows = [MaterialRow(**r) for r in m.get("rows", [])]
        mats.append(MaterialData(
            number=m.get("number", 0), rows=rows,
            comment=m.get("comment", ""),
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
