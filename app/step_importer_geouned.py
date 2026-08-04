"""
GEOUNED STEP→MCNP 转换器封装（与 McCADConverter 同接口，作为转换器 seam 的第二个 adapter）。

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


def _resolve_geouned_path() -> str:
    """返回 geouned 包所在父目录（加到 sys.path 后即可 import geouned）。"""
    # 打包环境：geouned 在 _internal/vendor/geouned，父目录即 vendor
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "vendor")
    # 开发环境：找已安装的 geouned 包（find_spec 不触发 import，无需 FreeCAD）
    try:
        import importlib.util
        spec = importlib.util.find_spec("geouned")
        if spec and spec.submodule_search_locations:
            pkg_dir = list(spec.submodule_search_locations)[0]
            return os.path.dirname(pkg_dir)
    except Exception:
        pass
    # 兜底：开发机上的独立安装目录
    return r"D:/MCNP/GEOUNED"


def _map_app_settings_to_geouned(app_settings: dict) -> dict:
    """把 app 的 StepSettings（McCAD 风格）映射为 geouned worker 设置。"""
    return {
        "voidGen": bool(app_settings.get("voidGeneration", True)),
        "compSolids": bool(app_settings.get("compoundIsSingleCell", False)),
        "simplify": "no",  # 安全默认；"voidfull" 可更优但耗时可增 5 倍
        # McCAD 的 minVoidVolume(cm³) 与 GEOUNED 的 minVoidSize(mm 边长) 概念不同，
        # 忽略 McCAD 值，用 GEOUNED 默认 200.0 mm
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

    def is_available(self) -> bool:
        """检查 FreeCAD python.exe、geouned 包、worker 脚本是否齐全。"""
        freecad_bin = self._get_freecad_bin()
        if not freecad_bin:
            return False
        python_exe = os.path.join(freecad_bin, "python.exe")
        if not os.path.isfile(python_exe):
            return False
        if not os.path.isfile(self._WORKER_SCRIPT):
            return False
        geouned_path = self._resolve_geouned_path()
        return os.path.isdir(os.path.join(geouned_path, "geouned"))

    # ── 转换 ──

    def run(self, step_path: str, material: str, density: float,
            work_dir: Optional[str] = None,
            settings: Optional[dict] = None) -> str:
        """运行 GEOUNED 转换，返回输出 MCNP 文件路径。"""
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

        python_exe = os.path.join(self._get_freecad_bin(), "python.exe")
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

    def _get_freecad_bin(self) -> Optional[str]:
        if self._freecad_bin:
            return self._freecad_bin
        from step_importer import StepImporter
        self._freecad_bin = StepImporter.detect_freecad()
        return self._freecad_bin

    def _resolve_geouned_path(self) -> str:
        if self._geouned_path:
            return self._geouned_path
        return _resolve_geouned_path()
