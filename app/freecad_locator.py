"""
FreeCAD 定位模块 — 唯一负责「找到 FreeCAD」的地方。

所有需要 FreeCAD 的调用方都收敛到这个 seam：
    api_server 的 /api/check-freecad、/api/set-freecad-path、
    step_importer 的 detect_freecad / save_freecad_path。

定位顺序：
    1. 用户手动保存的路径（config.json，唯一持久化存储）
    2. Windows 注册表（App Paths 64/32 位视图 + InstallPath 递归）
    3. PATH 环境变量（进程 PATH + 系统/用户环境变量注册表）
    4. 常见安装目录递归搜索

接口：
    saved()        -> str | None   用户手动保存的 FreeCAD.exe 完整路径
    save(path)     -> None         持久化用户路径（config.json）
    locate()       -> str | None   FreeCAD.exe 完整路径（带进程内缓存）
    bin_dir()      -> str | None   FreeCAD 的 bin 目录（detect_freecad 契约）
    reset_cache()  -> None         清除进程内缓存（保存新路径后调用）
"""

import glob
import os
import winreg
from typing import Optional

# 两种导入路径都得活：api_server 把 app/ 直接挂 sys.path（顶层名），
# 单测/打包走包路径（app.freecad_locator）—— 见 app/step_importer.py 的同款写法。
try:
    import user_config
except ImportError:  # pragma: no cover - 取决于调用方怎么挂 sys.path
    from app import user_config

_EXE_NAMES = ("freecad.exe", "freecadcmd.exe")


def _is_freecad_exe(p: str) -> bool:
    return bool(p) and os.path.isfile(p) and \
        os.path.basename(p).lower() in _EXE_NAMES


# ===================================================================
# 持久化：config.json（唯一存储，读写口在 app/user_config.py）
# ===================================================================

def _config_path() -> str:
    """历史接口，转发到唯一读写口（保留是因为它在文档/工具里被引用过）。"""
    return user_config.path()


def _from_config_json() -> Optional[str]:
    path = user_config._value("freecad_path")
    return path if _is_freecad_exe(path or "") else None


def saved() -> Optional[str]:
    """用户手动指定的 FreeCAD.exe 路径。"""
    return _from_config_json()


def save(path: str) -> None:
    """持久化用户手动指定的 FreeCAD.exe 路径（config.json + 清缓存）。

    **必须读-改-写**：config.json 是共享文件（还有 `mcnp_exe` 等键），
    整体覆盖会把别人的键抹掉 —— 实测路径：先选 FreeCAD、再在顶栏选 MCNP 版本。
    """
    user_config.set_values(freecad_path=path)
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
    """FreeCAD 的 bin 目录（StepImporter.detect_freecad 的契约）。

    便携版（免安装）FreeCAD 的 freecad.exe 可能直接放在根目录（如
    D:\\FreeCAD\\FreeCAD.exe），而 python.exe 在 bin\\ 子目录。
    本函数自动检测：如果 freecad.exe 所在目录不含 python.exe，
    则尝试 bin/ 子目录。
    """
    p = locate()
    if not p:
        return None
    d = os.path.dirname(p)
    # 便携版：freecad.exe 在根目录，python.exe 在 bin/ 子目录
    if not os.path.isfile(os.path.join(d, "python.exe")):
        alt = os.path.join(d, "bin")
        if os.path.isfile(os.path.join(alt, "python.exe")):
            return alt
    return d


def python_exe(bin_root: Optional[str] = None) -> Optional[str]:
    """FreeCAD 自带的 python.exe —— **定位它的唯一来源**（便携版与安装版两种布局都覆盖）。

    为什么要单独一个函数（2026-10-08）：STEP 方向预览需要拿 FreeCAD 的 python 跑一个小 worker，
    当时在 handler 里自己拼了一遍"候选路径"，与 GEOUNED 转换器那份重复 ⇒ 两份逻辑迟早漂移。
    现在两处都走这里：

    * **便携版（免安装）**：`freecad.exe` 与 `python.exe` 同在根目录
      （如 `D:\\FreeCAD\\FreeCAD_1.1.1-...\\bin\\python.exe`，`bin_dir()` 已把它算准）；
    * **安装版**：调用方可能拿到的是安装根（`…\\FreeCAD 1.1\\`），python 在 `bin\\` 子目录。

    传入 `bin_root`（例如 `StepImporter.detect_freecad()` 的返回值）时只在该目录找；
    不传则先 `bin_dir()` 自行定位。找不到返回 None —— **不猜、不硬编任何盘符或目录名**。
    """
    roots = []
    if bin_root:
        roots.append(bin_root)
    else:
        d = bin_dir()
        if d:
            roots.append(d)
    for root in roots:
        for rel in ("python.exe", os.path.join("bin", "python.exe")):
            cand = os.path.join(root, rel)
            if os.path.isfile(cand):
                return cand
    return None


def reset_cache() -> None:
    global _cache_state, _cache_path
    _cache_state, _cache_path = 0, None
