"""GPU 偏好写入（app/gpu_pref.py）单测。

避免真正写注册表：用 monkeypatch 替换 find_*/set_gpu_preference，验证 apply_gpu_preference
的 target/changed 逻辑；find_msedgewebview2_exe 只断言返回 list（不依赖具体路径）。
"""
import app.gpu_pref as g


def test_pref_map():
    assert g._PREF_MAP == {"high": "2", "power": "1", "default": "0"}


def test_find_msedgewebview2_exe_returns_list():
    assert isinstance(g.find_msedgewebview2_exe(), list)


def test_set_gpu_preference_invalid_returns_false():
    # 非法 preference 或空路径直接失败（非 Windows 也会失败，不触发 winreg）
    assert g.set_gpu_preference(r"C:\x\msedgewebview2.exe", "bogus") is False
    assert g.set_gpu_preference("", "high") is False


def test_apply_gpu_preference_no_targets(monkeypatch):
    monkeypatch.setattr(g, "find_msedgewebview2_exe", lambda: [])
    monkeypatch.setattr(g, "find_app_exe", lambda: [])
    monkeypatch.setattr(g, "set_gpu_preference", lambda p, pr: True)
    res = g.apply_gpu_preference("high")
    assert res == {"targets": [], "changed": 0}


def test_apply_gpu_preference_writes(monkeypatch):
    web = r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application\151\msedgewebview2.exe"
    app = r"D:\MCNP\MCNP输入卡生成器\MCNP 输入卡生成器.exe"
    written = []
    monkeypatch.setattr(g, "find_msedgewebview2_exe", lambda: [web])
    monkeypatch.setattr(g, "find_app_exe", lambda: [app])
    monkeypatch.setattr(g, "set_gpu_preference", lambda p, pr: written.append(p) or True)
    res = g.apply_gpu_preference("default")
    assert res["changed"] == 2
    assert res["targets"] == [web, app]
    assert written == [web, app]


# ── 2026-10-04：随包固定版 WebView2 + 首次运行默认独显 ──────────────

def test_find_bundled_fixed_runtime(monkeypatch, tmp_path):
    """随包固定版 `<sidecar 目录>\\WebView2\\msedgewebview2.exe` 必须被发现。

    本程序实际渲染的是它（main.rs::prefer_bundled_webview2）；旧实现只找共享 Evergreen
    ⇒ 偏好写到没在跑的进程上、点了"高性能独显"也不生效。
    """
    dep = tmp_path / "delivery"
    (dep / "WebView2").mkdir(parents=True)
    bundled = dep / "WebView2" / "msedgewebview2.exe"
    bundled.write_bytes(b"x")
    monkeypatch.setattr(g.sys, "executable", str(dep / "python.exe"))
    monkeypatch.setattr(g.os, "getcwd", lambda: str(dep))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "none"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "none"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "none"))
    found = g.find_msedgewebview2_exe()
    assert str(bundled) in found
    assert found[0] == str(bundled), "随包固定版应排在共享版之前（优先）"


def test_read_gpu_preference_parses(monkeypatch):
    """读值解析：GpuPreference=2/1/0 → high/power/default；无键/无值 → None。"""
    import sys as _s
    import types

    fake = types.ModuleType("winreg")
    fake.HKEY_CURRENT_USER = 1
    fake.REG_SZ = 1

    class _K:
        pass

    fake.OpenKey = lambda *a: _K()
    fake.CloseKey = lambda k: None
    fake.QueryValueEx = lambda k, name: ("GpuPreference=1;", 1)
    monkeypatch.setitem(_s.modules, "winreg", fake)
    monkeypatch.setattr(g, "_is_windows", lambda: True)
    assert g.read_gpu_preference(r"C:\x\msedgewebview2.exe") == "power"

    fake.QueryValueEx = lambda k, name: ("GpuPreference=2;", 1)
    assert g.read_gpu_preference(r"C:\x\msedgewebview2.exe") == "high"

    def _boom(*a):
        raise FileNotFoundError("no key")

    fake.OpenKey = _boom
    assert g.read_gpu_preference(r"C:\x\msedgewebview2.exe") is None


def test_own_targets_bundled_only_not_shared(monkeypatch, tmp_path):
    """自有目标 = 随包固定版 WebView2（+ 打包时的应用主 exe）；**不含共享 Evergreen**。

    共享版 msedgewebview2.exe 是全机 WebView2 应用共用的 exe，自动默认改它等于替别的程序
    改偏好 —— 所以自动只负责"本程序自己那份"。
    """
    dep = tmp_path / "delivery"
    (dep / "WebView2").mkdir(parents=True)
    bundled = dep / "WebView2" / "msedgewebview2.exe"
    bundled.write_bytes(b"x")
    monkeypatch.setattr(g.sys, "executable", str(dep / "python.exe"))
    monkeypatch.setattr(g.os, "getcwd", lambda: str(dep))
    monkeypatch.setattr(g, "find_msedgewebview2_exe",
                        lambda: [r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application\151\msedgewebview2.exe"])
    monkeypatch.setattr(g, "find_app_exe", lambda: [str(dep / "MCNP 输入卡生成器.exe")])
    monkeypatch.delattr(g.sys, "frozen", raising=False)
    assert g.own_gpu_targets() == [str(bundled)], "源码运行：只有随包固定版，不含共享版/应用 exe"
    monkeypatch.setattr(g.sys, "frozen", True, raising=False)
    assert g.own_gpu_targets() == [str(bundled), str(dep / "MCNP 输入卡生成器.exe")], "打包运行：加应用主 exe"
    monkeypatch.delattr(g.sys, "frozen", raising=False)


def test_ensure_default_writes_only_when_absent(monkeypatch):
    """首次运行：只对"还没有值"的目标写 high；已有值（用户选过）一律保留。"""
    web = r"D:\MCNP\MCNP输入卡生成器\WebView2\msedgewebview2.exe"
    app = r"D:\MCNP\MCNP输入卡生成器\MCNP 输入卡生成器.exe"
    existing = {"pref": "power"}

    def _read(p):
        return existing["pref"] if p == app else None

    written = []
    monkeypatch.setattr(g, "own_gpu_targets", lambda: [web, app])
    monkeypatch.setattr(g, "read_gpu_preference", _read)
    monkeypatch.setattr(g, "set_gpu_preference", lambda p, pr: written.append((p, pr)) or True)
    res = g.ensure_default_gpu_preference("high")
    assert written == [(web, "high")], "只应写缺失值的目标"
    assert res["written"] == 1 and res["skipped"] == 1
    acts = {d["path"]: d["action"] for d in res["details"]}
    assert acts[web] == "write" and acts[app] == "keep"


def test_ensure_default_skips_all_when_present(monkeypatch):
    """全部目标都已有值（用户显式选过）→ 一个都不写（不被每次启动覆盖）。"""
    web = r"D:\MCNP\MCNP输入卡生成器\WebView2\msedgewebview2.exe"
    monkeypatch.setattr(g, "own_gpu_targets", lambda: [web])
    monkeypatch.setattr(g, "read_gpu_preference", lambda p: "default")
    written = []
    monkeypatch.setattr(g, "set_gpu_preference", lambda p, pr: written.append(p) or True)
    res = g.ensure_default_gpu_preference("high")
    assert written == [] and res["written"] == 0 and res["skipped"] == 1
