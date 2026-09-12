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


def _map_app_settings_to_geouned(app_settings: dict) -> dict:
    """把 app 的 StepSettings 映射为 geouned worker 设置。"""
    return {
        "voidGen": bool(app_settings.get("voidGeneration", True)),
        "compSolids": bool(app_settings.get("compoundIsSingleCell", False)),
        "simplify": "no",  # 安全默认；"voidfull" 可更优但耗时可增 5 倍
        # minVoidSize 用 GEOUNED 默认 200.0 mm（app 无对应设置）
        "minVoidSize": 200.0,
        "startCell": int(app_settings.get("startCellNum", 1)),
        "startSurf": int(app_settings.get("startSurfNum", 1)),
        "maxSurf": 50,
        "maxBracket": 30,
        "sort_enclosure": False,
    }


class GeoUnedConverter:
    """GEOUNED 外部转换器封装：FreeCAD python + geouned_worker.py 子进程。"""

    _WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "geouned_worker.py")

    def __init__(self, freecad_bin: Optional[str] = None,
                 geouned_path: Optional[str] = None):
        self._freecad_bin = freecad_bin
        self._geouned_path = geouned_path

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
        worker_input = json.dumps({
            "step_path": os.path.abspath(step_path),
            "output_dir": work_dir,
            "geometry_name": "csg",
            "title": f"{material} density={density}",
            "geouned_path": geouned_path,
            "settings": _map_app_settings_to_geouned(settings),
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

        if proc.returncode != 0:
            raise RuntimeError(
                f"GEOUNED worker 退出码 {proc.returncode}\n"
                f"stdout: {proc.stdout[-300:]}\n"
                f"stderr: {proc.stderr[-300:]}"
            )
        try:
            result = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            raise RuntimeError(
                f"GEOUNED 输出非 JSON: {proc.stdout[:500]}")
        if result.get("status") != "ok":
            raise RuntimeError(
                f"GEOUNED 错误: {result.get('message', '未知')}")

        mcnp_path = result.get("mcnp_path")
        if not mcnp_path or not os.path.isfile(mcnp_path):
            raise RuntimeError(f"GEOUNED 未产出文件: {mcnp_path}")
        return mcnp_path

    # ── 辅助 ──

    @staticmethod
    def _find_python_exe(freecad_bin: str) -> str | None:
        """在 FreeCAD 目录中查找 python.exe（支持便携版）。"""
        candidates = [
            os.path.join(freecad_bin, "python.exe"),
            os.path.join(freecad_bin, "bin", "python.exe"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

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
