"""
FreeCAD 定位模块 — 唯一负责「找到 FreeCAD」的地方。

所有需要 FreeCAD 的调用方都收敛到这个 seam：
    api_server 的 /api/check-freecad、/api/set-freecad-path、
    step_importer 的 detect_freecad / save_freecad_path、
    Qt 界面保存 FreeCAD 路径。

定位顺序：
    1. 用户手动保存的路径（config.json 与 QSettings 双读，取任一有效）
    2. Windows 注册表（App Paths 64/32 位视图 + InstallPath 递归）
    3. PATH 环境变量（进程 PATH + 系统/用户环境变量注册表）
    4. 常见安装目录递归搜索

接口：
    saved()        -> str | None   用户手动保存的 FreeCAD.exe 完整路径
    save(path)     -> None         持久化用户路径（config.json + QSettings 双写）
    locate()       -> str | None   FreeCAD.exe 完整路径（带进程内缓存）
    bin_dir()      -> str | None   FreeCAD 的 bin 目录（detect_freecad 契约）
    reset_cache()  -> None         清除进程内缓存（保存新路径后调用）
"""

import json as _json
import glob
import os
import winreg
from typing import Optional

_EXE_NAMES = ("freecad.exe", "freecadcmd.exe")


def _is_freecad_exe(p: str) -> bool:
    return bool(p) and os.path.isfile(p) and \
        os.path.basename(p).lower() in _EXE_NAMES


# ===================================================================
# 持久化：config.json（web 端）+ QSettings（Qt 端）双写，保持两端同步
# ===================================================================

def _config_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "mcnp_generator")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "config.json")


def _from_config_json() -> Optional[str]:
    try:
        p = _config_path()
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                data = _json.load(f)
            path = (data.get("freecad_path") or "").strip().strip('"')
            if _is_freecad_exe(path):
                return path
    except Exception:
        pass
    return None


def _from_qsettings() -> Optional[str]:
    try:
        from PyQt5.QtCore import QSettings
        path = str(QSettings("MCNPGen", "MCNPGenerator").value("freecad_path", ""))
        path = path.strip().strip('"')
        if _is_freecad_exe(path):
            return path
    except Exception:
        pass
    return None


def saved() -> Optional[str]:
    """用户手动指定的 FreeCAD.exe 路径（config.json 优先，其次 QSettings）。"""
    return _from_config_json() or _from_qsettings()


def save(path: str) -> None:
    """持久化用户手动指定的 FreeCAD.exe 路径（双写 + 清缓存）。"""
    with open(_config_path(), "w", encoding="utf-8") as f:
        _json.dump({"freecad_path": path}, f)
    try:
        from PyQt5.QtCore import QSettings
        QSettings("MCNPGen", "MCNPGenerator").setValue("freecad_path", path)
    except Exception:
        pass
    reset_cache()


# ===================================================================
# 自动搜索策略
# ===================================================================

def _from_registry() -> Optional[str]:
    # App Paths（分别看 64/32 位注册表视图）
    for flag in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FreeCAD.exe",
                0, winreg.KEY_READ | flag,
            ) as k:
                p = winreg.QueryValueEx(k, "")[0]
                if _is_freecad_exe(p):
                    return p
        except OSError:
            pass
    # 注册表 InstallPath → bin 目录递归
    for key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey in (r"SOFTWARE\FreeCAD", r"SOFTWARE\FreeCAD\Application"):
            try:
                with winreg.OpenKey(key, subkey) as h:
                    install = winreg.QueryValueEx(h, "InstallPath")[0]
                    bin_dir = os.path.join(install, "bin")
                    if os.path.isdir(bin_dir):
                        for root, _, files in os.walk(bin_dir):
                            for fn in files:
                                if fn.lower() in _EXE_NAMES:
                                    return os.path.join(root, fn)
            except OSError:
                pass
    return None


def _from_env_path() -> Optional[str]:
    dirs = []
    for p in os.environ.get("PATH", "").split(os.pathsep):
        p = p.strip().strip('"')
        if p:
            dirs.append(p)
    # 系统/用户环境变量注册表里的 PATH
    for key, subkey in (
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ):
        try:
            with winreg.OpenKey(key, subkey) as h:
                val = winreg.QueryValueEx(h, "Path")[0]
                if val:
                    dirs += [p.strip().strip('"') for p in val.split(";") if p.strip().strip('"')]
        except OSError:
            pass
    seen = set()
    for d in dirs:
        if not d or d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        for f in os.listdir(d):
            if f.lower() in _EXE_NAMES:
                return os.path.join(d, f)
    return None


def _from_common_dirs() -> Optional[str]:
    patterns = [
        r"C:\Program Files\FreeCAD*",
        r"C:\Program Files (x86)\FreeCAD*",
        r"D:\FreeCAD*",
        r"D:\MCNP",
        os.path.expandvars(r"%PROGRAMFILES%\FreeCAD*"),
        os.path.expanduser(r"~\FreeCAD*"),
    ]
    for pat in patterns:
        for d in glob.glob(pat):
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for fn in files:
                    if fn.lower() in _EXE_NAMES:
                        return os.path.join(root, fn)
    return None


# ===================================================================
# 带缓存的完整定位
# ===================================================================

_cache_state: int = 0          # 0=未检测, 1=已找到, -1=未找到
_cache_path: Optional[str] = None


def locate() -> Optional[str]:
    """完整定位 FreeCAD.exe：saved → registry → env PATH → common dirs（带缓存）。"""
    global _cache_state, _cache_path
    if _cache_state == 0:
        path = (saved() or _from_registry()
                or _from_env_path() or _from_common_dirs())
        if _is_freecad_exe(path):
            _cache_state, _cache_path = 1, path
        else:
            _cache_state, _cache_path = -1, None
    return _cache_path


def bin_dir() -> Optional[str]:
    """FreeCAD 的 bin 目录（StepImporter.detect_freecad 的契约）。"""
    p = locate()
    return os.path.dirname(p) if p else None


def reset_cache() -> None:
    global _cache_state, _cache_path
    _cache_state, _cache_path = 0, None
