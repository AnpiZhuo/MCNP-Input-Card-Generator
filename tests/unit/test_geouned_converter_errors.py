# -*- coding: utf-8 -*-
"""`GeoUnedConverter.run()` 的**错误信封**判据（2026-10-08 部署版冒烟查实）。

背景（真机实测，不是推测）：worker 的每条失败路径都把 `{"status":"error","message":…}`
写进 **stdout** 并以 `sys.exit(1)` 退出。旧写法先查 `returncode`，于是把 worker 写好的
中文原因换成一句"退出码 1 + stdout 末尾 300 字符" —— 而那 300 字符是 **JSON 转义后的碎片**：

    部署版实测原文（用户会看到的）：
        GEOUNED 转换失败：GEOUNED worker 退出码 1
        stdout: 0c\u505c\u6b62\u8f6c\u6362\u300d\uff0c\u5bfc\u5165\u5df2\u7ec8\u6b62 …

本文件锁死修好后的判据：
  1. returncode≠0 **且** stdout 是可解析的错误信封 ⇒ 用信封里的 message（中文、可操作）；
  2. returncode≠0 而 stdout 不是 JSON ⇒ 保留旧的"退出码 + stdout/stderr 尾部"（不吞原始信息）；
  3. returncode=0 而信封说 error ⇒ `GEOUNED 错误: …`；
  4. returncode=0 而 stdout 不是 JSON ⇒ `输出非 JSON`（协议被污染时的判据）。

跑法不需要 FreeCAD/GEOUNED：可用性检查与子进程都被替换掉。
"""
import json
from pathlib import Path

import pytest

from app import step_importer_geouned as M


class _Proc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


@pytest.fixture
def conv(monkeypatch):
    """一个"看起来可用"的转换器：可用性/解释器/geouned 路径全部替换掉。"""
    monkeypatch.setattr(M.GeoUnedConverter, "_availability_reason", lambda self: None)
    monkeypatch.setattr(M.GeoUnedConverter, "_resolve_geouned_path", lambda self: "X")
    monkeypatch.setattr(M.GeoUnedConverter, "_find_python_exe",
                        staticmethod(lambda bin_root: "python"))
    c = M.GeoUnedConverter(freecad_bin="X")
    return c


def _stub(monkeypatch, proc):
    monkeypatch.setattr(M.subprocess, "run", lambda *a, **kw: proc)


BLOCKED = ("样条曲面：实体 1 共 1 个含样条类曲面（拉伸面，1 个面）。当前「样条曲面处理」设为"
           "「停止转换」，导入已终止 —— 把它改成「跳过该实体」即可继续。")


def test_nonzero_exit_prefers_the_json_envelope(conv, monkeypatch, tmp_path):
    """核心用例：worker 的中文原因必须**原样**上来（这条在部署版上是**实测失败过**的）。

    断言"逐字等于"是有意的：内层只回原因原文，标签（`GEOUNED 转换失败：`）由最外层
    `run_step_converter` 加**一次** —— 内层再加就变成"…失败：…失败：…"
    （2026-10-08 部署版冒烟看到的就是这处重复）。
    """
    env = json.dumps({"status": "error", "message": BLOCKED}, ensure_ascii=False)
    _stub(monkeypatch, _Proc(1, stdout=env + "\n"))
    with pytest.raises(RuntimeError) as ei:
        conv.run("a.step", "MAT", -1.0, str(tmp_path))
    msg = str(ei.value)
    assert msg == BLOCKED                          # 原样、不打标签、不重复
    assert "退出码" not in msg                      # 不再是"退出码 1 + 转义碎片"
    assert "\\u" not in msg
    assert msg.count("GEOUNED 转换失败") == 0        # 标签只在最外层加一次


def test_nonzero_exit_without_json_keeps_the_raw_tail(conv, monkeypatch, tmp_path):
    """stdout 不是 JSON（真的崩了/被污染）⇒ 旧的诊断口径一字不动（不吞原始信息）。"""
    _stub(monkeypatch, _Proc(1, stdout="boom 部分输出", stderr="errline 崩了"))
    with pytest.raises(RuntimeError) as ei:
        conv.run("a.step", "MAT", -1.0, str(tmp_path))
    msg = str(ei.value)
    assert "退出码 1" in msg and "boom 部分输出" in msg and "errline 崩了" in msg


def test_ok_exit_but_error_status_is_reported(conv, monkeypatch, tmp_path):
    """退出码 0 但信封说 error（老 worker 的形态）也要报出来。"""
    _stub(monkeypatch, _Proc(0, stdout=json.dumps({"status": "error", "message": "转换中途失败"})))
    with pytest.raises(RuntimeError, match="转换中途失败"):
        conv.run("a.step", "MAT", -1.0, str(tmp_path))


def test_ok_exit_with_non_json_stdout(conv, monkeypatch, tmp_path):
    _stub(monkeypatch, _Proc(0, stdout="<html>nope</html>"))
    with pytest.raises(RuntimeError, match="输出非 JSON"):
        conv.run("a.step", "MAT", -1.0, str(tmp_path))


def test_ok_envelope_missing_file_is_reported(conv, monkeypatch, tmp_path):
    _stub(monkeypatch, _Proc(0, stdout=json.dumps({"status": "ok", "mcnp_path": ""})))
    with pytest.raises(RuntimeError, match="未产出文件"):
        conv.run("a.step", "MAT", -1.0, str(tmp_path))


def test_ok_envelope_returns_path_and_warnings(conv, monkeypatch, tmp_path):
    f = tmp_path / "csg.mcnp"
    f.write_text("c hi\n", encoding="utf-8")
    _stub(monkeypatch, _Proc(0, stdout=json.dumps(
        {"status": "ok", "mcnp_path": str(f), "warnings": ["样条曲面：实体 1 …已跳过"]})))
    assert conv.run("a.step", "MAT", -1.0, str(tmp_path)) == str(f)
    assert conv.last_warnings == ["样条曲面：实体 1 …已跳过"]


def test_worker_user_facing_failures_have_no_traceback():
    """接线锁：预期内的失败必须走 `_UserFacing`（只回原因，不缀 traceback 淹掉那句话）。"""
    worker = Path(M.__file__).with_name("geouned_worker.py")
    text = worker.read_text(encoding="utf-8")
    assert "class _UserFacing(RuntimeError)" in text
    assert "raise _UserFacing(blocked)" in text
    assert "except _UserFacing as e:" in text
    # 兜底那条 `except Exception` 仍保留 traceback（真 bug 需要它）
    assert "traceback.format_exc()" in text
