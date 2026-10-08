"""
GEOUNED STEP→MCNP 转换器封装。

用法:
    from step_importer_geouned import GeoUnedConverter
    conv = GeoUnedConverter()
    if conv.is_available():
        mcnp_path = conv.run("input.stp", "MAT", -7.93, work_dir, settings_dict)
"""
import os
import sys
import json
import tempfile
import subprocess

from typing import Optional


# geouned 定位缓存（进程内；探测含一次 FreeCAD 解释器子进程，故只做一次）
_geouned_cache: str = ""
_geouned_probed: bool = False


def _resolve_geouned_path() -> str:
    """后端解释器里能找到的 geouned 包父目录（找不到返回 ""）。

    注意：geouned 是装给 **FreeCAD 的 Python** 用的（见 requirements.txt），
    后端解释器里 find_spec 找不到它是常态；真正权威的探测是
    ``GeoUnedConverter._probe_freecad_geouned``。本函数只是候选之一
    （开发机上把 geouned pip 装进后端环境时命中）。
    """
    try:
        import importlib.util
        spec = importlib.util.find_spec("geouned")
        if spec and spec.submodule_search_locations:
            pkg_dir = list(spec.submodule_search_locations)[0]
            return os.path.dirname(pkg_dir)
    except Exception:
        pass
    return ""


def _is_geouned_dir(path: str) -> bool:
    """path（geouned 包的父目录）下是否有**可用**的 geouned 包。

    只认完整包：``geouned/__init__.py`` + ``geouned/GEOUNED/__init__.py``
    （``from geouned import CadToCsg`` 靠这两层）。机器上出现过只有
    GEOReverse 的残缺 namespace 包（无 __init__.py），光判 isdir 会误判为可用，
    worker 起来后才炸 ImportError。
    """
    if not path:
        return False
    base = os.path.join(path, "geouned")
    return (os.path.isfile(os.path.join(base, "__init__.py"))
            and os.path.isfile(os.path.join(base, "GEOUNED", "__init__.py")))


def _probe_geouned_in(python_exe: str) -> str:
    """问某个解释器 geouned 装在哪，返回包父目录（问不到返回 ""）。

    worker 是在 FreeCAD 的 python.exe 里跑的，所以必须问**那个**解释器。
    """
    code = ("import importlib.util, os;"
            "s = importlib.util.find_spec('geouned');"
            "print(os.path.dirname(list(s.submodule_search_locations)[0])"
            " if s and s.submodule_search_locations else '')")
    try:
        proc = subprocess.run([python_exe, "-c", code],
                              capture_output=True, text=True, timeout=60)
    except Exception:
        return ""
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 or not out:
        return ""
    return out.splitlines()[-1].strip()


# ───────────────── app 设置 → GEOUNED 参数（表驱动白名单） ─────────────────
#
# 与前端 gui/src/components/StepImportDialog.tsx 的 PARAM_SPECS 一一对应。
#
# 三条约定：
#
# 1. **键缺失 / 类型不符 / 越界 → 该键不进结果**，即交给 GEOUNED 自己的默认值。
#    前端「留空 = 不发送」的语义在这里被保持住。绝不替用户补默认值 —— 否则将来
#    GEOUNED 升版改了默认值，会被本程序钉死。
#
# 2. 四个历史键（voidGeneration / compoundIsSingleCell / startCellNum /
#    startSurfNum）例外：它们从旧版本起就始终随请求发送，这里保留内置兜底，
#    保证老调用方（MCP、测试）不传时行为不变。
#
# 3. GEOUNED 的 setter 是**严格类型**：float 字段必须 float（传 int 会被拒）、
#    int 字段必须 int、bool 字段必须 bool、voidMat 必须是长度 3 的
#    (int, int|float, str) 或空 list（长度不对直接 TypeError）。所以转换器必须
#    把 JSON 来的值精确落型，否则 worker 会抛出很难懂的类型错误。


class _Invalid(Exception):
    """值不可用（缺失/类型不符/越界）——调用方跳过该键，不报错。"""


def _as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        low = v.strip().lower()
        if low in ("true", "1", "on", "yes"):
            return True
        if low in ("false", "0", "off", "no", ""):
            return False
    if isinstance(v, (int, float)):
        return bool(v)
    raise _Invalid()


def _num(v) -> float:
    """数字或数字字符串 → float（拒绝 bool）。"""
    if isinstance(v, bool):
        raise _Invalid()
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.strip():
        try:
            return float(v.strip())
        except ValueError:
            raise _Invalid()
    raise _Invalid()


def _as_float(v) -> float:
    return _num(v)


def _as_int(v) -> int:
    n = _num(v)
    if not float(n).is_integer():
        raise _Invalid()
    return int(n)


def _as_choice(allowed: tuple):
    def conv(v) -> str:
        if not isinstance(v, str):
            raise _Invalid()
        low = v.strip().lower()
        if low not in allowed:
            raise _Invalid()
        return low
    return conv


def _as_int_list(v) -> list:
    if isinstance(v, str):
        v = [s for s in v.replace("，", ",").replace(";", ",").split(",") if s.strip()]
    if not isinstance(v, (list, tuple)):
        raise _Invalid()
    out = []
    for item in v:
        n = _as_int(item)
        if n < 0:
            raise _Invalid()
        out.append(n)
    if not out:
        raise _Invalid()
    return out


def _as_str_list(v) -> list:
    if isinstance(v, str):
        v = [s.strip() for s in v.replace("，", ",").replace(";", "\n").replace(",", "\n").split("\n") if s.strip()]
    if not isinstance(v, (list, tuple)):
        raise _Invalid()
    out = []
    for item in v:
        if not isinstance(item, str) or not item.strip():
            raise _Invalid()
        out.append(item.strip())
    if not out:
        raise _Invalid()
    return out


def _as_void_mat(v) -> list:
    """geouned.Settings.voidMat 只接受空 list 或长度 3 的 (int, int|float, str)。"""
    if v in ([], (), None, ""):
        return []
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise _Invalid()
    label, rho, desc = v
    label = _as_int(label)
    rho = _num(rho)
    if not isinstance(desc, str):
        raise _Invalid()
    return [label, rho, desc]


_AS_SIMPLIFY = _as_choice(("no", "void", "voidfull", "full"))
_AS_SPLINE = _as_choice(("stop", "remove", "ignore"))

# (app 键, 区段, GEOUNED 键, 转换器, 合法域)
_PARAM_TABLE = (
    # ── geouned.Settings ──
    ("voidGeneration",       "settings", "voidGen",        _as_bool,     None),
    ("compoundIsSingleCell", "settings", "compSolids",     _as_bool,     None),
    ("startCellNum",         "settings", "startCell",      _as_int,      lambda n: n >= 1),
    ("startSurfNum",         "settings", "startSurf",      _as_int,      lambda n: n >= 1),
    ("maxSurf",              "settings", "maxSurf",        _as_int,      lambda n: n >= 1),
    ("maxBracket",           "settings", "maxBracket",     _as_int,      lambda n: n >= 1),
    ("minVoidSize",          "settings", "minVoidSize",    _as_float,    lambda n: n > 0),
    ("simplify",             "settings", "simplify",       _AS_SIMPLIFY, None),
    ("sortEnclosure",        "settings", "sort_enclosure", _as_bool,     None),
    ("debug",                "settings", "debug",          _as_bool,     None),
    ("voidMat",              "settings", "voidMat",        _as_void_mat, None),
    ("voidExclude",          "settings", "voidExclude",    _as_str_list, None),
    # ── geouned.Options ──
    ("forceNoOverlap",       "options",  "forceNoOverlap", _as_bool,     None),
    ("facets",               "options",  "Facets",         _as_bool,     None),
    ("forceCylinder",        "options",  "forceCylinder",  _as_bool,     None),
    ("newSplitPlane",        "options",  "newSplitPlane",  _as_bool,     None),
    ("scaleUp",              "options",  "scaleUp",        _as_bool,     None),
    ("splitTolerance",       "options",  "splitTolerance", _as_float,    lambda n: n >= 0),
    ("enlargeBox",           "options",  "enlargeBox",     _as_float,    lambda n: n >= 0),
    ("prnt3PPlane",          "options",  "prnt3PPlane",    _as_bool,     None),
    ("delLastNumber",        "options",  "delLastNumber",  _as_bool,     None),
    ("nPlaneReverse",        "options",  "nPlaneReverse",  _as_int,      None),
    # ── geouned.Tolerances（全部 float，GEOUNED 的 setter 拒收 int）──
    ("relativeTol",          "tolerances", "relativeTol",       _as_bool,  None),
    ("relativePrecision",    "tolerances", "relativePrecision", _as_float, lambda n: n > 0),
    ("tolValue",             "tolerances", "value",             _as_float, lambda n: n > 0),
    ("distance",             "tolerances", "distance",          _as_float, lambda n: n > 0),
    ("angle",                "tolerances", "angle",             _as_float, lambda n: n > 0),
    ("plnDistance",          "tolerances", "pln_distance",      _as_float, lambda n: n > 0),
    ("plnAngle",             "tolerances", "pln_angle",         _as_float, lambda n: n > 0),
    ("cylDistance",          "tolerances", "cyl_distance",      _as_float, lambda n: n > 0),
    ("cylAngle",             "tolerances", "cyl_angle",         _as_float, lambda n: n > 0),
    ("sphDistance",          "tolerances", "sph_distance",      _as_float, lambda n: n > 0),
    ("kneDistance",          "tolerances", "kne_distance",      _as_float, lambda n: n > 0),
    ("kneAngle",             "tolerances", "kne_angle",         _as_float, lambda n: n > 0),
    ("torDistance",          "tolerances", "tor_distance",      _as_float, lambda n: n > 0),
    ("torAngle",             "tolerances", "tor_angle",         _as_float, lambda n: n > 0),
    ("minArea",              "tolerances", "min_area",          _as_float, lambda n: n > 0),
    # ── load_step_file 的两个可选参数 ──
    ("splineSurfaces",       "load_step", "spline_surfaces", _AS_SPLINE,   None),
    ("skipSolids",           "load_step", "skip_solids",     _as_int_list, None),
    # ── export_csg 的可选参数（title/geometryName/outFormat 由本程序固定，不对外开放）──
    ("volSDEF",              "export", "volSDEF",          _as_bool, None),
    ("ucard",                "export", "UCARD",            _as_int,  lambda n: n >= 0),
    ("dummyMat",             "export", "dummyMat",         _as_bool, None),
    ("cellCommentFile",      "export", "cellCommentFile",  _as_bool, None),
    ("cellSummaryFile",      "export", "cellSummaryFile",  _as_bool, None),
)

# 历史键的内置兜底（旧调用方不传时保持旧行为）
_LEGACY_DEFAULTS = {
    "voidGeneration": True,
    "compoundIsSingleCell": False,
    "startCellNum": 1,
    "startSurfNum": 1,
}

_SECTIONS = ("settings", "options", "tolerances", "load_step", "export")

_MISSING = object()


def _map_app_settings_to_geouned(app_settings: dict) -> dict:
    """把 app 的 StepSettings 映射为 geouned worker 的五个参数区段。

    返回 ``{"settings": {...}, "options": {...}, "tolerances": {...},
    "load_step": {...}, "export": {...}}``；
    非法/缺失的键**不在结果里**（= 用 GEOUNED 默认值）。
    """
    app_settings = app_settings or {}
    out: dict = {name: {} for name in _SECTIONS}

    for app_key, section, geo_key, conv, ok in _PARAM_TABLE:
        raw = app_settings.get(app_key, _MISSING)
        if raw is _MISSING or raw is None or raw == "":
            # 历史键：用内置兜底；其余：不出现 = 用 GEOUNED 默认
            if app_key in _LEGACY_DEFAULTS:
                out[section][geo_key] = conv(_LEGACY_DEFAULTS[app_key])
            continue
        try:
            val = conv(raw)
        except _Invalid:
            if app_key in _LEGACY_DEFAULTS:
                out[section][geo_key] = conv(_LEGACY_DEFAULTS[app_key])
            continue
        if ok is not None and not ok(val):
            if app_key in _LEGACY_DEFAULTS:
                out[section][geo_key] = conv(_LEGACY_DEFAULTS[app_key])
            continue
        out[section][geo_key] = val

    # 空区段不发送（worker 缺失即用 GEOUNED 默认）
    return {name: sec for name, sec in out.items() if sec}



class GeoUnedConverter:
    """GEOUNED 外部转换器封装：FreeCAD python + geouned_worker.py 子进程。"""

    _WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "geouned_worker.py")

    def __init__(self, freecad_bin: Optional[str] = None,
                 geouned_path: Optional[str] = None):
        self._freecad_bin = freecad_bin
        self._geouned_path = geouned_path
        # worker 回传的提示（"实体预分解已生效 / 已跳过：原因"）。调用方读它做界面提示 ——
        # 放在实例上而不是改 run() 的返回值，避免动这个已经稳定的接口。
        self.last_warnings: list = []

    # ── 可用性 ──

    def _availability_reason(self) -> Optional[str]:
        """不可用的原因；可用时返回 None。"""
        freecad_bin = self._get_freecad_bin()
        if not freecad_bin:
            return "未检测到 FreeCAD，请安装或指定 FreeCAD 路径"
        python_exe = self._find_python_exe(freecad_bin)
        if not python_exe:
            return f"FreeCAD 缺少 python.exe: {freecad_bin}"
        if not os.path.isfile(self._WORKER_SCRIPT):
            return f"缺少 geouned worker 脚本: {self._WORKER_SCRIPT}"
        geouned_path = self._resolve_geouned_path()
        if not _is_geouned_dir(geouned_path):
            return (f"未检测到可用的 geouned 包（已在 FreeCAD 解释器 "
                    f"{python_exe} 与后端解释器里查找）。请把 geouned 装到 "
                    f"FreeCAD 的 Python 里，或设置环境变量 GEOUNED_PATH 指向 "
                    f"geouned 的父目录（该目录下应有 geouned/GEOUNED/__init__.py）"
                    f"后重启后端。")
        return None

    def is_available(self) -> bool:
        """检查 FreeCAD python.exe、geouned 包、worker 脚本是否齐全。"""
        return self._availability_reason() is None

    def unavailable_reason(self) -> Optional[str]:
        """不可用的具体原因（可展示给用户）；可用时返回 None。"""
        return self._availability_reason()

    # ── 转换 ──

    def run(self, step_path: str, material: str, density: float,
            work_dir: Optional[str] = None,
            settings: Optional[dict] = None) -> str:
        """运行 GEOUNED 转换，返回输出 MCNP 文件路径。

        不可用或失败时抛 RuntimeError，message 为可展示的具体原因。
        """
        reason = self._availability_reason()
        if reason:
            raise RuntimeError(f"GEOUNED 不可用：{reason}")
        if settings is None:
            settings = {}
        if work_dir is None:
            work_dir = tempfile.mkdtemp(prefix="geouned_")
        os.makedirs(work_dir, exist_ok=True)

        geouned_path = self._resolve_geouned_path()
        # 五个参数区段直接摊进 payload：settings / options / tolerances /
        # load_step / export。
        # 兼容性注记：`settings` 区段的键名与**旧 worker** 读的扁平键名完全一致
        # （voidGen/compSolids/simplify/minVoidSize/maxSurf/maxBracket/startCell/
        # startSurf/sort_enclosure），所以万一新转换器配上旧 worker，旧路径仍能
        # 拿到这几项；options/tolerances/load_step/export 是旧 worker 会忽略的
        # 额外顶层键。反之旧转换器配新 worker 也安全 —— 新 worker 对缺失区段
        # 一律用 GEOUNED 默认值。
        worker_input = json.dumps({
            "step_path": os.path.abspath(step_path),
            "output_dir": work_dir,
            "geometry_name": "csg",
            "title": f"{material} density={density}",
            "geouned_path": geouned_path,
            # 实体预分解（流水线开关，**不是** GEOUNED 参数，故不进 _PARAM_TABLE）。
            # 只需传开关与档位：跑它的解释器就是 worker 自己（FreeCAD python），
            # 不再有外部程序那种"worker 看不到随包目录"的路径发现问题。
            "cut": {
                "enabled": bool(settings.get("cutSolids", False)),
                "degree": settings.get("cutDegree") or None,
            },
            # CAD 上轴/方位约定（**不是** GEOUNED 参数，故不进 _PARAM_TABLE）：
            # STEP 文件不带上轴信息，差别来自源软件默认坐标系；本程序与 MCNP 是 Z 朝上，
            # 所以导入时按这个约定旋进 MCNP 系（导出侧按逆变换转出去）。默认不旋转。
            "cad_orientation": {
                "up": settings.get("cadUpAxis") or "Z",
                "azimuthDeg": settings.get("cadAzimuthDeg") or 0,
                # 原点口径：keep 按原本建模 / center 体心归零 / bottom 坐在底面上（MCNP 的 z=0）
                "origin": settings.get("cadOrigin") or "keep",
            },
            # 相切退化修复（流水线开关，**不是** GEOUNED 参数）：默认开。见 app/tangent_fix.py
            "tangent_fix": settings.get("tangentFix", True) is not False,
            **_map_app_settings_to_geouned(settings),
        })

        python_exe = self._find_python_exe(self._get_freecad_bin())
        if not python_exe:
            raise RuntimeError("FreeCAD python.exe 未找到")
        proc = subprocess.run(
            [python_exe, self._WORKER_SCRIPT],
            input=worker_input,
            capture_output=True, text=True, timeout=600,
            env=os.environ,
        )

        # ⚠️ **先**解析 stdout 的 JSON 信封，再看退出码 —— 顺序反了就会把 worker 写好的
        # 中文原因换成一句乱码（2026-10-08 部署版冒烟实测）：
        # worker 的每条失败路径都会把 `{"status":"error","message":…}` 写进 **stdout**
        # （那是它唯一的协议通道），而它同时会以 `sys.exit(1)` 退出。旧写法先查 returncode
        # 就 raise"退出码 1 + stdout 末尾 300 字符"，用户看到的是 JSON 转义碎片
        # （`0c\u505c\u6b62\u8f6c\u6362\u300d…`）而不是"把「样条曲面处理」改成「跳过该实体」即可继续"。
        envelope = None
        try:
            parsed = json.loads((proc.stdout or "").strip())
            if isinstance(parsed, dict):
                envelope = parsed
        except json.JSONDecodeError:
            envelope = None

        if proc.returncode != 0:
            if envelope and envelope.get("message"):
                # ⚠️ 这里**不要**自己加"GEOUNED 转换失败："前缀：外层 `run_step_converter` 已经加了
                # 一次，再加就出现"GEOUNED 转换失败：GEOUNED 转换失败：…"（2026-10-08 部署版冒烟看到）。
                # 纪律：内层只回**原因原文**，标签由最外层加一次。
                raise RuntimeError(envelope["message"])
            raise RuntimeError(
                f"GEOUNED worker 退出码 {proc.returncode}\n"
                f"stdout: {proc.stdout[-300:]}\n"
                f"stderr: {proc.stderr[-300:]}"
            )
        if envelope is None:
            raise RuntimeError(
                f"GEOUNED 输出非 JSON: {proc.stdout[:500]}")
        result = envelope
        if result.get("status") != "ok":
            raise RuntimeError(
                f"GEOUNED 错误: {result.get('message', '未知')}")

        mcnp_path = result.get("mcnp_path")
        if not mcnp_path or not os.path.isfile(mcnp_path):
            raise RuntimeError(f"GEOUNED 未产出文件: {mcnp_path}")
        # worker 的提示（切割已生效/已跳过）带回给调用方展示
        self.last_warnings = list(result.get("warnings") or [])
        return mcnp_path

    # ── 辅助 ──

    @staticmethod
    def _find_python_exe(freecad_bin: str) -> str | None:
        """在 FreeCAD 目录中查找 python.exe（便携版 / 安装版两种布局）。

        2026-10-08：实现统一挪到 `freecad_locator.python_exe()` —— STEP 方向预览也要用它，
        两份候选路径逻辑重复迟早漂移。这里保留原签名，只做转发。
        """
        from freecad_locator import python_exe
        return python_exe(freecad_bin)

    def _get_freecad_bin(self) -> Optional[str]:
        if self._freecad_bin:
            return self._freecad_bin
        from step_importer import StepImporter
        self._freecad_bin = StepImporter.detect_freecad()
        return self._freecad_bin

    def _geouned_candidates(self):
        """geouned 包父目录的候选（按优先级，含未验证的）。"""
        yield os.environ.get("GEOUNED_PATH", "")
        # 打包环境：geouned 在 _internal/vendor/geouned，父目录即 vendor
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            yield os.path.join(sys._MEIPASS, "vendor")
        yield _resolve_geouned_path()          # 后端解释器（pip 装进后端环境时）
        yield self._probe_freecad_geouned()    # FreeCAD 解释器（正规安装位置）

    def _probe_freecad_geouned(self) -> str:
        """问 FreeCAD 的 python.exe geouned 装在哪（worker 用的就是它）。"""
        freecad_bin = self._get_freecad_bin()
        if not freecad_bin:
            return ""
        python_exe = self._find_python_exe(freecad_bin)
        if not python_exe:
            return ""
        return _probe_geouned_in(python_exe)

    def _resolve_geouned_path(self) -> str:
        """第一个**验证可用**的 geouned 包父目录（含探测缓存）。"""
        if self._geouned_path:
            return self._geouned_path
        global _geouned_cache, _geouned_probed
        if _geouned_probed:
            return _geouned_cache
        for cand in self._geouned_candidates():
            if _is_geouned_dir(cand):
                _geouned_cache = cand
                break
        _geouned_probed = True
        return _geouned_cache
