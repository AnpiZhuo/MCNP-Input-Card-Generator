# -*- coding: utf-8 -*-
"""`app/step_importer_geouned.py` 映射表白名单单测。

锁死的契约（前端「留空 = 不发送」的语义必须在这里保持住）：

1. **缺省 / 类型不符 / 越界 → 该键不出现在结果里** = 用 GEOUNED 自己的默认值。
   绝不替用户补默认值 —— 否则 GEOUNED 升版改了默认值会被本程序钉死。
2. **显式 false 必须能传出去**：`newSplitPlane` / `scaleUp` / `cellSummaryFile`
   在 GEOUNED 里默认是**开**，用户把按钮点成「关」时必须真的传到 worker，
   不能被「留空」逻辑顺手吞掉。
3. **严格落型**：GEOUNED 的 setter 是严格类型 —— `minVoidSize` 必须 float
   （传 int 会被拒）、`maxSurf`/`maxBracket` 必须 int、bool 项必须 bool。
4. **前后端键集双向一致**：前端 `StepImportDialog.tsx` 的 PARAM_SPECS 里每个
   `key` 都必须在后端表里（否则「界面能填、后端丢弃」这种哑巴 bug），
   后端表也不许有前端不认识的键（死参数）。
"""
import re
from pathlib import Path

from app.step_importer_geouned import (
    _LEGACY_DEFAULTS,
    _PARAM_TABLE,
    _map_app_settings_to_geouned,
)

PROJECT_DIR = Path(__file__).resolve().parents[2]
TSX_PATH = PROJECT_DIR / "gui" / "src" / "components" / "StepImportDialog.tsx"
WORKER_PATH = PROJECT_DIR / "app" / "geouned_worker.py"

SECTIONS = ("settings", "options", "tolerances", "load_step", "export")

# 文件选择框的伪 key（不是参数）
FILE_PSEUDO_KEY = "__file"


def mapped(app_settings):
    return _map_app_settings_to_geouned(app_settings)


# ── 1. 缺省 / 历史键兜底 ────────────────────────────────────────

def test_only_legacy_keys_when_nothing_given():
    """老调用方一个 GEOUNED 参数都不传 → 只剩 4 个历史键（旧行为一字不变）。"""
    for data in ({}, None, {"materialName": "MAT"}):
        out = mapped(data)
        assert out == {
            "settings": {
                "voidGen": True,
                "compSolids": False,
                "startCell": 1,
                "startSurf": 1,
            }
        }, out


def test_legacy_keys_always_present_with_historical_defaults():
    """4 个历史键的内置兜底与旧代码一致（避免老调用方漏传导致编号错乱）。"""
    assert _LEGACY_DEFAULTS == {
        "voidGeneration": True,
        "compoundIsSingleCell": False,
        "startCellNum": 1,
        "startSurfNum": 1,
    }


def test_legacy_key_falls_back_when_invalid():
    """历史键传了非法值 → 回落历史默认，而不是丢弃（丢了会变成 GEOUNED 默认，语义不同）。"""
    out = mapped({"startSurfNum": "abc", "voidGeneration": "maybe", "startCellNum": 0})
    assert out["settings"]["startSurf"] == 1
    assert out["settings"]["voidGen"] is True
    assert out["settings"]["startCell"] == 1


def test_new_key_absent_from_result_when_invalid():
    """新参数非法 → 该键**不出现**（= 用 GEOUNED 默认），不是回落成本程序的默认值。"""
    out = mapped({"simplify": "YES", "minVoidSize": 0, "maxSurf": 3.5,
                  "ucard": -1, "forceNoOverlap": "maybe"})
    assert "simplify" not in out["settings"]
    assert "minVoidSize" not in out["settings"]
    assert "maxSurf" not in out["settings"]
    assert "options" not in out          # 唯一的 options 参数非法 → 整个区段不出现
    assert "export" not in out


def test_unknown_keys_are_ignored():
    out = mapped({"hackerParam": 1, "__proto__": 2, "voidGen": False})
    flat = {k for sec in out.values() for k in sec}
    assert "hackerParam" not in flat and "__proto__" not in flat


# ── 2. 严格落型 ────────────────────────────────────────────────

def test_numeric_types_match_geouned_setters():
    """GEOUNED 的 setter 拒收错误类型：float 字段必须 float，int 字段必须 int。"""
    out = mapped({
        "minVoidSize": 50, "enlargeBox": 2, "splitTolerance": 0,
        "maxSurf": 20, "maxBracket": 10, "nPlaneReverse": 0, "ucard": 10,
        "distance": 1e-4, "minArea": 1e-2, "relativePrecision": 1e-6,
        "relativeTol": False, "prnt3PPlane": True,
    })
    assert isinstance(out["settings"]["minVoidSize"], float)
    assert isinstance(out["options"]["enlargeBox"], float)
    assert isinstance(out["options"]["splitTolerance"], float)
    assert isinstance(out["settings"]["maxSurf"], int)
    assert isinstance(out["settings"]["maxBracket"], int)
    assert isinstance(out["options"]["nPlaneReverse"], int)
    assert isinstance(out["export"]["UCARD"], int)
    assert isinstance(out["tolerances"]["distance"], float)
    assert isinstance(out["tolerances"]["min_area"], float)
    assert isinstance(out["tolerances"]["relativePrecision"], float)
    assert isinstance(out["tolerances"]["relativeTol"], bool)
    assert isinstance(out["options"]["prnt3PPlane"], bool)
    assert not isinstance(out["settings"]["minVoidSize"], int)


def test_bool_accepts_string_and_number_forms():
    """其他调用方（MCP / 手写 JSON）可能传字符串或 0/1。"""
    out = mapped({"forceNoOverlap": "true", "facets": "0", "newSplitPlane": 1,
                  "scaleUp": "off", "prnt3PPlane": "on"})
    assert out["options"]["forceNoOverlap"] is True
    assert out["options"]["Facets"] is False
    assert out["options"]["newSplitPlane"] is True
    assert out["options"]["scaleUp"] is False
    assert out["options"]["prnt3PPlane"] is True


def test_explicit_false_survives():
    """反向坑：GEOUNED 默认是「开」的项，用户点成「关」必须真的传出去。"""
    out = mapped({"newSplitPlane": False, "scaleUp": False, "cellSummaryFile": False})
    assert out["options"]["newSplitPlane"] is False
    assert out["options"]["scaleUp"] is False
    assert out["export"]["cellSummaryFile"] is False


def test_zero_is_not_treated_as_blank():
    """0 是合法值（nPlaneReverse 默认就是 0），不能被「留空」逻辑当成没填。"""
    out = mapped({"nPlaneReverse": 0, "splitTolerance": 0})
    assert out["options"]["nPlaneReverse"] == 0
    assert out["options"]["splitTolerance"] == 0.0


# ── 3. 白名单归一 ─────────────────────────────────────────────

def test_simplify_whitelist_normalized():
    assert mapped({"simplify": "VOID"})["settings"]["simplify"] == "void"
    assert mapped({"simplify": "VoidFull"})["settings"]["simplify"] == "voidfull"
    assert mapped({"simplify": " no "})["settings"]["simplify"] == "no"
    assert "simplify" not in mapped({"simplify": "fast"})["settings"]


def test_spline_surfaces_whitelist():
    """load_step_file.spline_surfaces 只认 stop/remove/ignore（源码里就是这三档）。"""
    assert mapped({"splineSurfaces": "Remove"})["load_step"]["spline_surfaces"] == "remove"
    assert mapped({"splineSurfaces": "ignore"})["load_step"]["spline_surfaces"] == "ignore"
    assert "load_step" not in mapped({"splineSurfaces": "skip"})


# ── 4. 列表类 ─────────────────────────────────────────────────

def test_skip_solids_parses_comma_and_space():
    assert mapped({"skipSolids": "3, 7,12"})["load_step"]["skip_solids"] == [3, 7, 12]
    assert mapped({"skipSolids": [3, 7]})["load_step"]["skip_solids"] == [3, 7]
    assert "load_step" not in mapped({"skipSolids": "3, x"})     # 非整数 → 丢弃
    assert "load_step" not in mapped({"skipSolids": "-1"})       # 负序号 → 丢弃
    assert "load_step" not in mapped({"skipSolids": ""})         # 空 → 丢弃


def test_void_exclude_splits_chinese_punctuation():
    """中文逗号/分号/换行都要能吃（用户是中文输入）。"""
    assert mapped({"voidExclude": "a，b;c\nd"})["settings"]["voidExclude"] == ["a", "b", "c", "d"]
    assert mapped({"voidExclude": ["a", "b"]})["settings"]["voidExclude"] == ["a", "b"]
    assert "voidExclude" not in mapped({"voidExclude": "  "})["settings"]


def test_void_mat_requires_exactly_three():
    """geouned.Settings.voidMat 只接受空 list 或长度 3 的 (int, int|float, str)。"""
    out = mapped({"voidMat": [100, 1.2e-3, "air"]})["settings"]["voidMat"]
    assert out == [100, 0.0012, "air"]
    assert isinstance(out[0], int) and isinstance(out[1], float) and isinstance(out[2], str)
    assert "voidMat" not in mapped({"voidMat": [1, 2]})["settings"]      # 半套 → 丢弃
    assert "voidMat" not in mapped({"voidMat": [1, 2, 3, 4]})["settings"]
    assert "voidMat" not in mapped({"voidMat": ["x", 1.0, "d"]})["settings"]


# ── 5. 区段裁剪 ───────────────────────────────────────────────

def test_empty_sections_are_dropped():
    """空区段不发送 —— worker 缺区段即用 GEOUNED 默认值。"""
    out = mapped({"distance": 1e-4})
    assert set(out) == {"settings", "tolerances"}
    assert set(out["settings"]) == {"voidGen", "compSolids", "startCell", "startSurf"}


def test_all_sections_present_when_fully_specified():
    out = mapped({
        "maxSurf": 20, "splineSurfaces": "stop", "skipSolids": "1",
        "forceNoOverlap": True, "distance": 1e-4, "volSDEF": True,
    })
    assert set(out) == set(SECTIONS)


# ── 6. 前后端键集契约（双向） ──────────────────────────────────

def _frontend_specs() -> dict:
    """前端参数元数据表：`{key: is_local}`。

    只认元数据行（`key: "x", …, label: …`）—— JSX 里 React 的 `key: "file"` 之类
    不能混进来。`local: true` 按约定与 `key:` **同一行**（一行自描述），所以这里
    不做跨行扫描。
    """
    text = TSX_PATH.read_text(encoding="utf-8")
    specs = {}
    for m in re.finditer(r'^\s*key: "([^"]+)",(.*)$', text, re.M):
        key, rest = m.group(1), m.group(2)
        if "label:" not in rest:
            continue
        specs[key] = "local: true" in rest
    assert len(specs) >= 40, f"元数据表解析异常，只认出 {len(specs)} 个键（正则可能失效）"
    return specs


def _frontend_keys() -> set:
    return set(_frontend_specs())


def _backend_keys() -> set:
    return {row[0] for row in _PARAM_TABLE}


def test_frontend_and_backend_key_sets_agree():
    """前端能填的每个 **GEOUNED 参数** 后端都必须认；后端也不许有前端不认识的死参数。

    这条防的是最容易发生的哑巴 bug：界面加了控件、后端表没加 →
    用户填了值却静默丢弃（不报错、不生效）。
    `local: true` 的键**不跨这道 seam**（材料名/密度/TMP 本程序自用；
    实体预分解开关与面数上限走 payload 的 `cut` 段），故排除。
    """
    assert TSX_PATH.is_file(), f"前端文件缺失: {TSX_PATH}"
    specs = _frontend_specs()
    front = {k for k, is_local in specs.items() if not is_local} - {FILE_PSEUDO_KEY}
    back = _backend_keys()
    assert front == back, (
        f"前端独有（后端会静默丢弃）: {sorted(front - back)}；"
        f"后端独有（界面上没有）: {sorted(back - front)}"
    )


def test_local_keys_are_exactly_the_two_groups():
    """`local` 键集不许静默膨胀 —— 每加一个都要先想清它走哪条通道。

    当前 9 个，按**通道**分四组（断言跟着分组走，不是一坨名字）：
      · 材料名 / 密度 / TMP                     → 本程序填料（导入结果回填）
      · cutSolids / cutDegree                   → payload 的 `cut` 段（实体预分解）
      · cadUpAxis / cadAzimuthDeg / cadOrigin   → payload 的 `cad_orientation` 段
      · tangentFix                              → payload 的 `tangent_fix` 开关

    ⚠️ 2026-10-08：后四条是上一批（STEP 上轴/原点口径/相切修复）加进界面的，那一批漏改了
    这条断言 ⇒ 门禁一直是红的（与本次改动无关）。这里按通道补全，**不是放宽**：
    「界面上的 GEOUNED 参数 == 后端白名单」仍由上面一条守着。
    """
    specs = _frontend_specs()
    local = {k for k, is_local in specs.items() if is_local}
    assert local == {"materialName", "density", "tmp", "cutSolids", "cutDegree",
                     "cadUpAxis", "cadAzimuthDeg", "cadOrigin", "tangentFix"}
    # 还要"真的走通道"：每个流水线开关都必须在转换器里被读出来，否则就是
    # "界面能填、后端收不到"的哑巴 bug（本测试存在的理由）。
    src = (PROJECT_DIR / "app" / "step_importer_geouned.py").read_text(encoding="utf-8")
    for key in ("cutSolids", "cutDegree", "cadUpAxis", "cadAzimuthDeg",
                "cadOrigin", "tangentFix"):
        assert f'settings.get("{key}"' in src, f"{key} 没有进入 payload"


def test_pipeline_flags_never_reach_the_geouned_mapping():
    """预分解开关/面数上限是流水线开关，**不得**出现在 GEOUNED 参数映射结果里。"""
    out = mapped({"cutSolids": True, "cutDegree": "fine"})
    flat = {k for sec in out.values() for k in sec}
    assert "cutSolids" not in flat and "cutDegree" not in flat
    # 也不该有任何区段被它们凭空造出来
    assert set(out) == {"settings"}


def test_converter_payload_carries_cut_section():
    """payload 必须单独带 `cut` 段（源码锁：这两项不走 _PARAM_TABLE）。"""
    src = (PROJECT_DIR / "app" / "step_importer_geouned.py").read_text(encoding="utf-8")
    assert '"cut": {' in src
    assert 'settings.get("cutSolids"' in src
    assert 'settings.get("cutDegree")' in src


# ── 7. worker 侧五区段读取守卫 ────────────────────────────────

def test_worker_reads_all_five_sections():
    """worker 必须真的读五区段 —— 防止将来重构时漏接一段（参数静默失效）。"""
    src = WORKER_PATH.read_text(encoding="utf-8")
    for name in SECTIONS:
        assert f'data.get("{name}")' in src, f"worker 未读取 {name} 区段"
    assert "Options(**options)" in src
    assert "Tolerances(**tolerances)" in src
    assert 'load_step.get("spline_surfaces"' in src
