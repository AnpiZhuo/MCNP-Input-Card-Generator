"""`app_script_path()` 回归测试 —— 冻结版路径 bug（2026-10-08 用户实机报错）。

现场报错原文：
    STEP 预览镶嵌失败：…\\python.exe: can't open file
    'D:\\MCNP\\app\\_freecad_step_preview_worker.py': [Errno 2] No such file or directory

根因：handler 里用 `APP_DIR`（= `PROJECT_DIR/app`，而 `PROJECT_DIR` 是拿 `api_server.__file__`
往上两级算的）拼 worker 路径。冻结版里 `__file__` 指向 exe 旁的虚拟路径 ⇒ 算出 `D:\\MCNP\\app`，
**该目录不存在**；松散 .py 实际落在 `_internal/app/`（`sys._MEIPASS/app`）。
它之所以"看起来能用"，只是因为 `mcnp_bridge` 已把 `_MEIPASS/app` 加进 sys.path ——
于是 **import 找得到、取文件路径找不到**。

本测试锁两件事：
  1. 源码树里能定位到真实存在的 worker 脚本；
  2. **模拟冻结环境**（sys.frozen + sys._MEIPASS）时，必须优先取 `_MEIPASS/app` 下的那份，
     即使 `APP_DIR` 指向一个不存在的目录也不能失败。
"""

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "gui", "backend"))

from api_server import app_script_path  # noqa: E402


def test_finds_worker_in_source_tree():
    p = app_script_path("_freecad_step_preview_worker.py")
    assert os.path.isfile(p)
    assert os.path.basename(p) == "_freecad_step_preview_worker.py"
    # 与本批其它 worker 同目录（松散 .py 一起随包）
    assert os.path.isfile(os.path.join(os.path.dirname(p), "_freecad_csg_worker.py"))


def test_missing_script_raises_clearly():
    """找不到就抛 FileNotFoundError（让调用方报清楚），而不是把 subprocess 的 stderr 糊出去。"""
    with pytest.raises(FileNotFoundError):
        app_script_path("__no_such_worker__.py")


def test_frozen_prefers_meipass_app(tmp_path, monkeypatch):
    """★模拟冻结环境：worker 只在 `_MEIPASS/app` 下存在时必须取到它。

    这正是本次实机 bug 的形状 —— `APP_DIR` 那侧（模拟成不存在的目录）不该成为障碍。
    """
    mei = tmp_path / "_internal"
    (mei / "app").mkdir(parents=True)
    fake = mei / "app" / "_freecad_step_preview_worker.py"
    fake.write_text("# frozen build copy\n", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(mei), raising=False)
    monkeypatch.setattr("api_server.APP_DIR", str(tmp_path / "nonexistent_app"), raising=False)

    got = app_script_path("_freecad_step_preview_worker.py")
    assert os.path.normcase(got) == os.path.normcase(str(fake))


def test_frozen_falls_back_to_app_dir_when_meipass_lacks_it(tmp_path, monkeypatch):
    """`_MEIPASS/app` 里没有时，仍要能退回 `APP_DIR`（不能因为冻结就只会一条路）。"""
    mei = tmp_path / "_internal"
    (mei / "app").mkdir(parents=True)
    app_dir = tmp_path / "app"
    app_dir.mkdir(parents=True)
    real = app_dir / "some_worker.py"
    real.write_text("# x\n", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(mei), raising=False)
    monkeypatch.setattr("api_server.APP_DIR", str(app_dir), raising=False)

    assert os.path.normcase(app_script_path("some_worker.py")) == os.path.normcase(str(real))
