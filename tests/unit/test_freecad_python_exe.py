"""FreeCAD python.exe 定位 + 「不要硬编路径」回归测试（2026-10-08 用户要求）。

用户原话：「便携版和安装版本都要考虑到，不要硬编路径」。

背景：STEP 方向预览要拿 FreeCAD 的 python 跑一个镶嵌 worker。第一版在 handler 里自己拼了
一份"候选路径"（与 GEOUNED 转换器重复），而且 worker **脚本**路径用了 `APP_DIR`
（冻结版算出来是 `D:\\MCNP\\app`，不存在）⇒ 实机报
`can't open file 'D:\\MCNP\\app\\_freecad_step_preview_worker.py'`。
现在：python.exe 定位统一走 `freecad_locator.python_exe()`，脚本路径统一走
`api_server.app_script_path()`，两处都不含任何盘符/目录名常量。

本文件锁三件事：
  1. **便携版布局**（python.exe 与 freecad.exe 同目录）能定位；
  2. **安装版布局**（python.exe 在 bin\\ 子目录）能定位；
  3. 相关源码里**不得出现硬编盘符路径**（`X:\\...`）—— 防止下次又写死。
"""

import os
import re
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "app"))
sys.path.insert(0, os.path.join(_ROOT, "gui", "backend"))

import freecad_locator  # noqa: E402


def _fake_root(tmp_path, layout: str) -> str:
    root = tmp_path / ("portable" if layout == "portable" else "installed")
    (root / "bin").mkdir(parents=True)
    if layout == "portable":
        (root / "python.exe").write_bytes(b"")
    else:
        (root / "bin" / "python.exe").write_bytes(b"")
    return str(root)


def test_portable_layout(tmp_path):
    """便携版：python.exe 就在传入目录里。"""
    root = _fake_root(tmp_path, "portable")
    assert freecad_locator.python_exe(root) == os.path.join(root, "python.exe")


def test_installed_layout(tmp_path):
    """安装版：python.exe 在 bin\\ 子目录（调用方拿到的是安装根）。"""
    root = _fake_root(tmp_path, "installed")
    assert freecad_locator.python_exe(root) == os.path.join(root, "bin", "python.exe")


def test_missing_returns_none_not_guess(tmp_path):
    """两种布局都没有就返回 None（**不猜路径**），由调用方报清楚。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert freecad_locator.python_exe(str(empty)) is None


def test_without_arg_uses_locator(tmp_path, monkeypatch):
    """不传参数时走 `bin_dir()`（注册表/config/PATH 定位的结果），同样两种布局通吃。"""
    root = _fake_root(tmp_path, "installed")
    monkeypatch.setattr(freecad_locator, "bin_dir", lambda: root)
    assert freecad_locator.python_exe() == os.path.join(root, "bin", "python.exe")


def test_geouned_converter_delegates_to_locator(tmp_path):
    """GEOUNED 转换器那份必须与本函数同源（不允许两套候选路径）。"""
    from step_importer_geouned import GeoUnedConverter
    root = _fake_root(tmp_path, "installed")
    assert GeoUnedConverter._find_python_exe(root) == freecad_locator.python_exe(root)


# ─────────── 不要硬编路径 ───────────

_DRIVE = re.compile(r"[A-Za-z]:\\")


@pytest.mark.parametrize("rel", [
    "app/cad_orientation.py",
    "app/stl_transform.py",
    "app/_freecad_step_preview_worker.py",
])
def test_new_modules_have_no_hardcoded_drive_paths(rel):
    """本批新增的纯模块里不得出现 `X:\\...` 形式的硬编路径。"""
    src = open(os.path.join(_ROOT, rel), encoding="utf-8").read()
    bad = [f"{rel}:{i}: {line.strip()[:90]}"
           for i, line in enumerate(src.splitlines(), 1) if _DRIVE.search(line)]
    assert bad == [], "发现硬编盘符路径：\n" + "\n".join(bad)


def test_locator_searches_but_never_returns_a_literal():
    """`freecad_locator` 允许有**候选搜索表**（那是定位器该干的：注册表/PATH/config/常见目录），
    但 `python_exe` 的返回必须是"就着传入目录拼相对名"，不许直接吐一个写死的路径。"""
    src = open(os.path.join(_ROOT, "app", "freecad_locator.py"), encoding="utf-8").read()
    start = src.index("def python_exe")
    body = src[start:src.index("def reset_cache")]
    assert 'os.path.join(root, rel)' in body          # 相对拼接
    assert 'for rel in ("python.exe"' in body         # 只认相对名
    # 返回语句里不出现盘符
    for line in body.splitlines():
        if "return" in line:
            assert not _DRIVE.search(line), line


def test_step_preview_handler_uses_locator_and_app_script_path():
    """handler 必须走单一来源：`freecad_locator.python_exe` + `app_script_path`，
    不得再出现自己拼的 `python.exe` 或 `APP_DIR` 拼接。"""
    src = open(os.path.join(_ROOT, "gui", "backend", "api_server.py"), encoding="utf-8").read()
    start = src.index("def _handle_step_preview")
    end = src.index("def _handle_mcnp_detect", start)
    body = src[start:end]
    assert 'python_exe(freecad_bin)' in body
    assert 'app_script_path("_freecad_step_preview_worker.py")' in body
    assert 'os.path.join(APP_DIR' not in body
    assert '"python.exe"' not in body and "'python.exe'" not in body
