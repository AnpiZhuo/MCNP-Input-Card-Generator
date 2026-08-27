"""GPU 偏好写入（Windows DirectX per-app UserGpuPreferences）。

背景：Tauri/WebView2 应用的 3D 渲染跑在共享的 msedgewebview2.exe。要让电脑用独显，
就是把这个进程写进 `HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences\\<exe>` =
`GpuPreference=<2|1|0>;`（2=高性能独显，1=省电/核显，0=系统默认）。

本模块负责：① 找 msedgewebview2.exe（共享版 + 固定版）；② 找应用主 exe（与 sidecar
同目录，尽力）；③ 写注册表。纯函数可测（winreg 在非 Windows 用 try 导入）。
"""
import os
import sys

_PREF_MAP = {"high": "2", "power": "1", "default": "0"}
_USER_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def find_msedgewebview2_exe() -> list[str]:
    """搜索 WebView2 的 msedgewebview2.exe 路径列表（共享 Evergreen + 应用目录固定版）。"""
    roots = [
        os.path.join(os.getenv("ProgramFiles(x86)", ""), "Microsoft", "EdgeWebView", "Application"),
        os.path.join(os.getenv("ProgramFiles", ""), "Microsoft", "EdgeWebView", "Application"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "EdgeWebView", "Application"),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            if name[:1].isdigit():  # 版本号目录（如 151.0.4129.107）
                p = os.path.join(root, name, "msedgewebview2.exe")
                if os.path.isfile(p) and p not in seen:
                    seen.add(p)
                    out.append(p)
    # 固定版（紧邻应用/侧车目录）
    for base in (os.path.dirname(os.path.abspath(sys.executable)), os.getcwd()):
        p = os.path.join(base, "msedgewebview2.exe")
        if os.path.isfile(p) and p not in seen:
            seen.add(p)
            out.append(p)
    return sorted(out)


def find_app_exe() -> list[str]:
    """找到应用主 exe（与 sidecar python.exe 同目录，排除 sidecar/WebView2/卸载器）。"""
    d = os.path.dirname(os.path.abspath(sys.executable))
    if not os.path.isdir(d):
        return []
    exclude = ("python", "msedgewebview2", "unins", "uninstall", "crashpad")
    out: list[str] = []
    try:
        for name in sorted(os.listdir(d)):
            low = name.lower()
            if not low.endswith(".exe"):
                continue
            if any(x in low for x in exclude):
                continue
            out.append(os.path.join(d, name))
    except OSError:
        pass
    return out


def set_gpu_preference(exe_path: str, preference: str) -> bool:
    """写单个 exe 的 GPU 偏好。preference ∈ {high, power, default}。成功 True；非 Windows/失败 False。"""
    value = _PREF_MAP.get(str(preference))
    if value is None or not exe_path or not _is_windows():
        return False
    try:
        import winreg  # Windows only

        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _USER_KEY)
        try:
            winreg.SetValueEx(key, exe_path, 0, winreg.REG_SZ, "GpuPreference=%s;" % value)
        finally:
            winreg.CloseKey(key)
        return True
    except Exception:
        return False


def apply_gpu_preference(preference: str) -> dict:
    """对 msedgewebview2.exe + 应用主 exe 写入偏好，返回 {"targets", "changed"}。"""
    targets: list[str] = []
    for p in find_msedgewebview2_exe():
        targets.append(p)
    for p in find_app_exe():
        if p not in targets:
            targets.append(p)
    changed = 0
    for t in targets:
        if set_gpu_preference(t, preference):
            changed += 1
    return {"targets": targets, "changed": changed}
