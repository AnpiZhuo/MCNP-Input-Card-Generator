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
