"""
STEP → MCNP 转换：封装 FreeCAD 检测 + GEOUNED 调用 + 输出解析

使用方法：
    from app.step_importer import StepImporter

    bin_path = StepImporter.detect_freecad()
    if bin_path:
        mcnp_text = StepImporter.import_step("model.stp", bin_path)
"""

import os
import json
import re
import shutil
import subprocess
import tempfile
import winreg
import time as _time

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import QMessageBox


# ---------------------------------------------------------------------------
# FreeCAD 检测
# ---------------------------------------------------------------------------

def _reg_query(key_path: str, value_name: str = "",
               wow64_flag: int = 0) -> str | None:
    """读取 Windows 注册表字符串值，返回 None 表示未找到。

    Args:
        wow64_flag: winreg.KEY_WOW64_64KEY 或 KEY_WOW64_32KEY。
                    0 = 用 Python 进程默认位宽。
    """
    try:
        access = winreg.KEY_READ | wow64_flag if wow64_flag else winreg.KEY_READ
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, access) as k:
            return winreg.QueryValueEx(k, value_name)[0]
    except OSError:
        return None


def _find_freecad_from_registry() -> str | None:
    """尝试从注册表定位 FreeCAD.exe，同时检查 64/32 位视图。"""
    # 64 位视图
    path = _reg_query(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FreeCAD.exe",
        wow64_flag=winreg.KEY_WOW64_64KEY,
    )
    if path and os.path.isfile(path):
        return path
    # 32 位视图（WOW6432Node）
    path = _reg_query(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FreeCAD.exe",
        wow64_flag=winreg.KEY_WOW64_32KEY,
    )
    if path and os.path.isfile(path):
        return path
    return None


def _find_freecad_from_common_dirs() -> str | None:
    """在常见安装目录下搜索 FreeCAD.exe。"""
    _SEARCH_BASES = [
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "D:\\",
        os.path.expanduser("~"),
    ]
    for base in _SEARCH_BASES:
        try:
            for name in os.listdir(base):
                if "FreeCAD" not in name:
                    continue
                freecad_dir = os.path.join(base, name)
                # 直接：FreeCAD/bin/FreeCAD.exe
                exe = os.path.join(freecad_dir, "bin", "FreeCAD.exe")
                if os.path.isfile(exe):
                    return exe
                # 间接：FreeCAD/FreeCAD_*/bin/FreeCAD.exe
                try:
                    for subname in os.listdir(freecad_dir):
                        if "FreeCAD" in subname:
                            exe = os.path.join(freecad_dir, subname, "bin", "FreeCAD.exe")
                            if os.path.isfile(exe):
                                return exe
                except PermissionError:
                    continue
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            continue
    return None


# cached result: 0=未检测, 1=找到(值在_cache_path), None=未找到
_freecad_cache_state: int = 0
_freecad_cache_path: str | None = None


def _cached_detect() -> str | None:
    """带缓存的 FreeCAD 检测，避免重复扫描磁盘。"""
    global _freecad_cache_state, _freecad_cache_path
    if _freecad_cache_state == 0:
        settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = settings.value("freecad_path", "")
        if saved and os.path.isfile(saved):
            _freecad_cache_state = 1
            _freecad_cache_path = saved
            return os.path.dirname(saved)
        exe = _find_freecad_from_registry()
        if not exe:
            exe = _find_freecad_from_common_dirs()
        if exe and os.path.isfile(exe):
            settings.setValue("freecad_path", exe)
            _freecad_cache_state = 1
            _freecad_cache_path = exe
            return os.path.dirname(exe)
        _freecad_cache_state = -1  # 未找到，缓存 miss
        _freecad_cache_path = None
    if _freecad_cache_state == 1 and _freecad_cache_path:
        return os.path.dirname(_freecad_cache_path)
    return None


# ---------------------------------------------------------------------------
# GEOUNED 输出解析
# ---------------------------------------------------------------------------

def _parse_geouned_output(mcnp_text: str) -> str:
    """解析 GEOUNED 输出，返回 UI 可加载的合并文本。

    返回格式：
        [曲面定义]

        [TR/*TR 卡]
        # Cells (从 STEP 导入)

    GEOUNED 输出结构（实际观察）：
        C 标题/注释
        CELL_NO  ...
           Vol=...
           imp:n=...
        C ######... SURFACE DEFINITION ######
        SURF_NO  TYPE  params...
        (空白行/空格行)
        MODE / VOID / NPS / *TRn / ...

    现有程序约定：曲面编辑器上段 = 曲面卡，下段（空行后）= TRn 卡。
    """
    lines = mcnp_text.splitlines()

    surfaces: list[str] = []
    tr_lines: list[str] = []
    in_surfaces = False

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()

        if "SURFACE" in upper and stripped.startswith("C"):
            in_surfaces = True
            continue

        if not in_surfaces:
            continue

        if not stripped or stripped.startswith("C") or stripped.startswith("c"):
            continue

        parts = stripped.split()
        if not parts:
            continue

        # 曲面定义：编号 + 字母类型（支持 C/X, K/Y 等含 / 的类型）
        if len(parts) >= 2 and parts[0].isdigit() and parts[1][0].isalpha():
            surfaces.append(stripped)
            continue

        # TR/*TR 变换卡
        upper_no_star = upper.lstrip("*")
        if upper_no_star.startswith("TR") and len(upper_no_star) > 2:
            rest = upper_no_star[2:].lstrip()
            if rest and rest[0].isdigit():
                tr_lines.append(stripped)
                continue

    parts_out = []
    if surfaces:
        parts_out.append("\n".join(surfaces))
    if tr_lines:
        parts_out.append("")
        parts_out.append("\n".join(tr_lines))
    if surfaces:
        parts_out.append("")
        parts_out.append("# Cells (从 STEP 导入，请核对并录入栅元表格)")

    return "\n".join(parts_out)


# ---------------------------------------------------------------------------
# 错误弹窗
# ---------------------------------------------------------------------------

def _show_error_dialog(msg: str, parent=None) -> None:
    """弹错误对话框（文本可复制）。"""
    box = QMessageBox(parent) if parent else QMessageBox()
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle("STEP 导入失败")
    box.setText(msg)
    box.setTextInteractionFlags(
        Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
    )
    box.exec_()


def _install_geouned(python_exe: str, parent=None) -> bool:
    """在 FreeCAD Python 中安装 GEOUNED，返回是否成功。"""
    msg = QMessageBox(parent) if parent else QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle("安装依赖")
    msg.setText("GEOUNED（STEP 转换引擎）未在 FreeCAD 中安装。")
    msg.setInformativeText("是否自动安装？（约 2 MB，仅 numpy + tqdm）")
    btn_yes = msg.addButton("安装", QMessageBox.ActionRole)
    msg.addButton("取消", QMessageBox.RejectRole)
    msg.exec_()

    if msg.clickedButton() != btn_yes:
        return False

    # 镜像列表，依次尝试
    mirrors = [
        "https://pypi.tuna.tsinghua.edu.cn/simple",
        "https://pypi.org/simple",
    ]
    stderr_log = ""
    for mirror in mirrors:
        try:
            install = subprocess.run(
                [python_exe, "-m", "pip", "install", "geouned", "-i", mirror],
                capture_output=True, text=True, timeout=120,
            )
            if install.returncode == 0:
                # 安装成功提示
                success = QMessageBox(parent) if parent else QMessageBox()
                success.setIcon(QMessageBox.Information)
                success.setWindowTitle("安装完成")
                success.setText("GEOUNED 安装成功，现在可以使用 STEP 导入功能。")
                success.exec_()
                return True
            stderr_log += f"\n[{mirror}]: {install.stderr.strip()[:200]}"
        except subprocess.TimeoutExpired:
            stderr_log += f"\n[{mirror}]: 超时"

    _show_error_dialog(
        f"GEOUNED 安装失败（可手动安装）：\n"
        f"{python_exe} -m pip install geouned\n\n"
        f"{stderr_log[:500]}",
        parent,
    )
    return False


# ---------------------------------------------------------------------------
# 公开接口：StepImporter
# ---------------------------------------------------------------------------

def _detect_step_unit(step_path: str) -> float:
    """解析 STEP 文件头，自动检测长度单位并返回 → cm 的缩放因子。

    从 STEP 文件的 DATA 段查找 SI_UNIT 定义，识别毫米/厘米/米/微米/英寸等。
    未找到单位信息时默认按 mm 处理（STEP 标准惯例），返回 0.1。
    """
    try:
        with open(step_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(100000)  # 只读前 100KB 找单位定义
    except Exception:
        return 0.1  # 默认 mm → cm

    # 查找 LENGTH_UNIT 附近的 SI_UNIT 定义
    # STEP 格式示例:
    #   SI_UNIT($,.MILLI.,.METRE.)  → mm  (×0.1 → cm)
    #   SI_UNIT($,.CENTI.,.METRE.)  → cm  (×1   → cm)
    #   SI_UNIT($,.UNITS.,.METRE.)  → m   (×100 → cm)
    #   SI_UNIT($,.MICRO.,.METRE.)  → μm  (×0.0001 → cm)
    #   NAMED_UNIT(*) / INCHES      → 英寸 (×2.54 → cm)

    # 先找英寸（它用 NAMED_UNIT 而非 SI_UNIT）
    if re.search(r"INCH", content, re.IGNORECASE):
        return 2.54

    # SI_UNIT 模式匹配
    m = re.search(
        r"LENGTH_UNIT\s*\(\).*?SI_UNIT\s*\(\s*[^,]*\s*,\s*\.(\w+)\s*\.\s*,\s*\.METRE\s*\.",
        content, re.DOTALL,
    )
    if m:
        prefix = m.group(1).upper()
        scale_map = {
            "MILLI":  0.1,     # mm → cm
            "CENTI":  1.0,     # cm → cm
            "UNITS":  100.0,   # m  → cm
            "DECI":   10.0,    # dm → cm
            "MICRO":  0.0001,  # μm → cm
            "NANO":   1e-7,    # nm → cm
            "KILO":   100000.0,# km → cm
        }
        return scale_map.get(prefix, 0.1)

    # 也可能是裸 .METRE. 不带前缀（即单位是米）
    if re.search(r"LENGTH_UNIT\s*\(\).*?SI_UNIT\s*\([^)]*METRE", content, re.DOTALL):
        return 100.0

    # 未识别 → 按 STEP 标准惯例 mm
    return 0.1


class StepImporter:
    """深模块：STEP → MCNP 转换。单一 seam，内部封装所有复杂度。"""

    SETTINGS_KEY = "freecad_path"

    # ------------------------------------------------------------------
    # FreeCAD 检测
    # ------------------------------------------------------------------

    @staticmethod
    def detect_freecad() -> str | None:
        """检测 FreeCAD bin 目录路径。

        返回 bin 目录（如 ``D:\\FreeCAD\\...\\bin``），未找到返回 None。
        结果缓存，仅在第一次调用时扫描磁盘和注册表。
        线程安全：需在 Qt 主线程调用（内部使用 QSettings）。
        """
        return _cached_detect()

    @staticmethod
    def save_freecad_path(exe_path: str) -> None:
        """保存用户手动指定的 FreeCAD.exe 路径并刷新缓存。"""
        global _freecad_cache_state, _freecad_cache_path
        if exe_path and os.path.isfile(exe_path):
            QSettings("MCNPGen", "MCNPGenerator").setValue(
                StepImporter.SETTINGS_KEY, exe_path
            )
            _freecad_cache_state = 1
            _freecad_cache_path = exe_path

    @staticmethod
    def invalidate_cache() -> None:
        """清除缓存，下次 detect_freecad() 会重新扫描。"""
        global _freecad_cache_state
        _freecad_cache_state = 0

    # ------------------------------------------------------------------
    # STEP 转换（返回结构化结果，不弹窗，适合后台线程调用）
    # ------------------------------------------------------------------

    @staticmethod
    def import_step(
        step_path: str,
        freecad_bin: str,
    ) -> dict:
        """转换 STEP 文件 → MCNP 输入文本。

        Args:
            step_path: .step / .stp 文件路径。
            freecad_bin: detect_freecad() 返回的 bin 目录。

        Returns:
            {"text": str} 成功时，或 {"error": str} 失败时。
            不弹窗，不抛出异常，适合在 QThread 中安全调用。
        """
        if not os.path.isfile(step_path):
            return {"error": f"STEP 文件不存在:\n{step_path}"}

        python_exe = os.path.join(freecad_bin, "python.exe")
        if not os.path.isfile(python_exe):
            return {"error": f"FreeCAD Python 未找到:\n{python_exe}"}

        # 确保 GEOUNED 就绪（本步骤可能弹窗询问用户，应主线程调用）
        if not _ensure_geouned_ready(python_exe):
            return {"error": "GEOUNED 未安装，用户取消了安装。"}

        # 自动检测 STEP 文件单位并计算 → cm 的缩放因子
        scale = _detect_step_unit(step_path)

        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp(prefix="step_import_")

            config = {
                "load_step_file": {
                    "filename": os.path.abspath(step_path),
                },
                "Settings": {
                    "debug": False,
                    "startCell": 10001,
                    "startSurf": 10001,
                    "compSolids": False,
                    "voidGen": True,
                    "scaleFactor": scale,
                },
                "export_csg": {
                    "geometryName": "Imported",
                    "outFormat": ["mcnp"],
                    "volCARD": False,
                },
            }
            cfg_path = os.path.join(tmpdir, "config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            proc = subprocess.run(
                [python_exe, "-m", "geouned.GEOUNED.scripts.geouned_cadtocsg",
                 "-i", cfg_path],
                cwd=tmpdir,
                timeout=300,
                capture_output=True,
                text=False,  # 二进制模式，手动解码
            )

            if proc.returncode != 0:
                # 用 UTF-8 解码错误输出
                err = _try_decode(proc.stderr) or "未知错误（无输出）"
                return {"error": f"GEOUNED 转换失败 (exit={proc.returncode}):\n{err}"}

            output_path = os.path.join(tmpdir, "Imported.mcnp")
            if not os.path.isfile(output_path):
                return {"error": "GEOUNED 执行完成但未生成输出文件。"}

            with open(output_path, encoding="utf-8") as f:
                raw = f.read()

            return {"text": _parse_geouned_output(raw)}

        except subprocess.TimeoutExpired:
            return {"error": "GEOUNED 转换超时（>5 分钟）。\n文件可能过于复杂，请简化后再试。"}

        except Exception as e:
            return {"error": f"转换过程出错:\n{type(e).__name__}: {e}"}

        finally:
            if tmpdir and os.path.isdir(tmpdir):
                _rmtree_retry(tmpdir)


def _try_decode(data: bytes) -> str:
    """尝试用 UTF-8 解码，失败时用系统编码兜底。"""
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        import locale
        enc = locale.getpreferredencoding()
        return data.decode(enc, errors="replace")


def _rmtree_retry(path: str, max_retries: int = 3) -> None:
    """递归删除目录，遇锁文件时重试。"""
    for attempt in range(max_retries):
        try:
            shutil.rmtree(path)
            return
        except (PermissionError, OSError):
            if attempt < max_retries - 1:
                _time.sleep(0.5)
            else:
                shutil.rmtree(path, ignore_errors=True)


_geouned_available: bool | None = None


def _ensure_geouned_ready(python_exe: str, parent=None) -> bool:
    """检查/安装 GEOUNED，缓存检测结果。"""
    global _geouned_available
    if _geouned_available is not None:
        return _geouned_available

    try:
        check = subprocess.run(
            [python_exe, "-c", "import geouned; print(geouned.__version__)"],
            capture_output=True, text=True, timeout=15,
        )
        if check.returncode == 0:
            _geouned_available = True
            return True
    except subprocess.TimeoutExpired:
        pass

    _geouned_available = _install_geouned(python_exe, parent)
    return _geouned_available
