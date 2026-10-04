"""GPU 偏好写入（Windows DirectX per-app UserGpuPreferences）。

背景：Tauri/WebView2 应用的 3D 渲染跑在共享的 msedgewebview2.exe。要让电脑用独显，
就是把这个进程写进 `HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences\\<exe>` =
`GpuPreference=<2|1|0>;`（2=高性能独显，1=省电/核显，0=系统默认）。

本模块负责：① 找 msedgewebview2.exe（共享版 + 固定版）；② 找应用主 exe（与 sidecar
同目录，尽力）；③ 写注册表。纯函数可测（winreg 在非 Windows 用 try 导入）。
"""
import os
import re
import sys

_PREF_MAP = {"high": "2", "power": "1", "default": "0"}
_USER_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def find_msedgewebview2_exe() -> list[str]:
    """搜索 WebView2 的 msedgewebview2.exe 路径列表（**随包固定版优先**，再共享 Evergreen）。

    ⚠ 2026-10-04 修（真 bug）：本程序 2026-09-29 起随包分发「固定版运行时」，实际渲染的是
    `<交付目录>\\WebView2\\msedgewebview2.exe`（`gui/src-tauri/src/main.rs::prefer_bundled_webview2()`
    把它指给 WebView2）。旧实现只找 `%ProgramFiles(x86)%\\Microsoft\\EdgeWebView\\Application\\<ver>\\`
    这些**共享版**路径 ⇒ 偏好写到了「没在跑的那个进程」上，等于没生效（用户点"高性能独显"也不动）。
    现同时登记 ①`<sidecar 目录>\\WebView2\\`（随包固定版）②同目录直放 ③共享 Evergreen。
    """
    bases = [os.path.dirname(os.path.abspath(sys.executable)), os.getcwd()]
    seen: set[str] = set()
    out: list[str] = []
    # ① 随包固定版 + ② 同目录直放
    for base in bases:
        for sub in ("WebView2", ""):
            p = os.path.join(base, sub, "msedgewebview2.exe") if sub else os.path.join(base, "msedgewebview2.exe")
            if os.path.isfile(p) and p not in seen:
                seen.add(p)
                out.append(p)
    # ③ 共享 Evergreen（系统装的 WebView2 运行时）
    roots = [
        os.path.join(os.getenv("ProgramFiles(x86)", ""), "Microsoft", "EdgeWebView", "Application"),
        os.path.join(os.getenv("ProgramFiles", ""), "Microsoft", "EdgeWebView", "Application"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "EdgeWebView", "Application"),
    ]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            if name[:1].isdigit():  # 版本号目录（如 151.0.4129.107）
                p = os.path.join(root, name, "msedgewebview2.exe")
                if os.path.isfile(p) and p not in seen:
                    seen.add(p)
                    out.append(p)
    return out


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


def own_gpu_targets() -> list[str]:
    """应用**自有**的 GPU 偏好目标：随包固定版 WebView2（在的话）+ 应用主 exe（仅打包运行时）。

    为什么不含共享 Evergreen 的 `msedgewebview2.exe`：那是**全机所有 WebView2 应用共用**的 exe
    （Outlook/Teams…都跑它），自动改它等于替别的程序改了偏好。所以自动默认只负责"本程序自己那份"；
    用户**显式**在界面点选时仍走 `apply_gpu_preference()`（含共享版，语义=用户主动要求）。
    """
    out: list[str] = []
    for base in (os.path.dirname(os.path.abspath(sys.executable)), os.getcwd()):
        p = os.path.join(base, "WebView2", "msedgewebview2.exe")
        if os.path.isfile(p) and p not in out:
            out.append(p)
    if getattr(sys, "frozen", False):      # 打包运行时才有"应用主 exe"这一说
        for p in find_app_exe():
            if p not in out:
                out.append(p)
    return out


def read_gpu_preference(exe_path: str) -> str | None:
    """读单个 exe 的现有偏好 → "high"/"power"/"default"；无值/非 Windows/失败 → None。"""
    if not exe_path or not _is_windows():
        return None
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _USER_KEY)  # 只读：不 CreateKey
        try:
            raw, _t = winreg.QueryValueEx(key, exe_path)
        finally:
            winreg.CloseKey(key)
    except Exception:
        return None
    m = re.search(r"GpuPreference\s*=\s*([012])", str(raw))
    if not m:
        return None
    return {"2": "high", "1": "power", "0": "default"}[m.group(1)]


def ensure_default_gpu_preference(preference: str = "high") -> dict:
    """**首次运行**写默认偏好：只对「应用自有目标里还没有值」的写；已有值一律不动。

    为什么"只写缺失的"：用户在界面下拉框或 Windows「设置 → 显示 → 图形」里显式选过之后
    （值已存在），每次启动再覆盖会把用户的选择改回去。所以默认只负责"第一次"。
    返回值 {targets, written, skipped, details}（details 便于排障：写没写对目标）。
    """
    written, skipped, details = 0, 0, []
    targets = own_gpu_targets()
    for t in targets:
        cur = read_gpu_preference(t)
        if cur is None:
            ok = set_gpu_preference(t, preference)
            written += 1 if ok else 0
            details.append({"path": t, "action": "write" if ok else "write-failed",
                            "preference": preference})
        else:
            skipped += 1
            details.append({"path": t, "action": "keep", "preference": cur})
    return {"targets": targets, "written": written, "skipped": skipped, "details": details}
