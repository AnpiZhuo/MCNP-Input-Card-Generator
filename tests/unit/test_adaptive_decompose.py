# -*- coding: utf-8 -*-
"""`app/adaptive_decompose.py` 单测：按「每块面数上限」的实体预分解。

测试策略（对齐 codebase-design）：**全部穿过模块接口**，不外 grep 源码
（唯一的例外是最后那组"接线锁"—— 它锁的是两个文件之间的接线，没有别的观察面）。
子进程用注入的假 runner 驱动，所以本文件**不需要 FreeCAD**；
真 FreeCAD 的端到端用例在文件末尾，装不上就 skip。

锁死的契约：
  1. 档位 → 面数上限的映射必须稳定（界面下拉的取值就是它）；
  2. 与子进程的接口是**一份 JSON 请求 + 一份 JSON 报告** ⇒ 键名逐字稳定；
  3. `decompose()` 失败一律抛 RuntimeError 且 message 带原始原因（**不吞原因**）；
  4. 只在 work_dir 内写文件，**不删**任何文件；
  5. 切不到上限必须如实上报（`over_limit` / `degraded` / `summary()` 里说出来）。
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from app import adaptive_decompose as A

PROJECT_DIR = Path(__file__).resolve().parents[2]


# ── 档位 → 每块面数上限 ───────────────────────────────────────

@pytest.mark.parametrize("degree,expected", [
    ("coarse", 50), ("medium", 30), ("fine", 20),
    ("COARSE", 50), (" fine ", 20),
    (None, 30), ("", 30),                    # 留空 = 默认档（30 面）
    (12, 12), ("35", 35), (30.7, 30),        # 也接受直接给数字
    (0, 0), (-3, 0),                         # 0/负数 = 不限制（调用方据此跳过）
    ("bogus", 30), ("  ", 30),               # 非法 → 默认档，绝不抛异常
    (True, 30),                              # bool 是 int 的子类，别被当成 1
])
def test_degree_to_face_limit(degree, expected):
    assert A.degree_to_face_limit(degree) == expected


def test_default_face_limit_is_the_medium_choice():
    """默认档必须与下拉的 medium 是同一个数，否则界面文案与行为会漂。"""
    assert A.DEFAULT_FACE_LIMIT == A.FACE_LIMIT_CHOICES["medium"]
    assert A.degree_to_face_limit(None) == A.degree_to_face_limit("medium")


# ── 与子进程的接口：请求 JSON（逐键锁） ───────────────────────

def test_build_request_shape():
    req = A.build_request("a/b.step", "w/out.stp", 30)
    assert req == {
        "src": os.path.abspath("a/b.step"),
        "dst": os.path.abspath("w/out.stp"),
        "face_limit": 30,
        "max_depth": 8,
        "eps_cm3": 1e-6,
        "max_pieces": 4000,
    }


def test_build_request_is_json_serialisable_and_ascii_safe():
    """请求体要能落成 JSON 且含中文路径也不炸（用户文件就叫「厂房建模.step」）。"""
    req = A.build_request(r"P:\dekstop\厂房建模.step", r"D:\w\out.stp", 20)
    text = json.dumps(req, ensure_ascii=False)
    assert json.loads(text)["face_limit"] == 20
    assert "厂房建模.step" in text


# ── 报告 → Cutting（判据在父侧，不在子进程的 stdout 里） ──────

def _ok_payload(**over):
    rep = {
        "dst": "/w/decomposed.stp", "face_limit": 30, "blocks": 18,
        "faces": {"min": 19, "median": 25, "max": 30},
        "over_limit": 0, "volume_ratio": 1.0000000028, "seconds": 0.96,
    }
    rep.update(over)
    return {"ok": True, "report": rep}


def test_parse_report_happy_path():
    cut = A.parse_report(_ok_payload(), "/fallback.stp", 30)
    assert (cut.path, cut.blocks, cut.faces_max) == ("/w/decomposed.stp", 18, 30)
    assert cut.volume_ratio == pytest.approx(1.0)
    assert not cut.degraded


def test_parse_report_raises_with_original_reason():
    with pytest.raises(RuntimeError) as ei:
        A.parse_report({"ok": False, "error": "OSError: 文件读不了",
                        "traceback": "Traceback ..."}, "/x.stp", 30)
    msg = str(ei.value)
    assert "OSError: 文件读不了" in msg and "Traceback" in msg


def test_parse_report_rejects_garbage():
    with pytest.raises(RuntimeError, match="报告格式不对"):
        A.parse_report({}, "/x.stp", 30)


def test_dst_falls_back_to_requested_path_when_report_omits_it():
    cut = A.parse_report(_ok_payload(dst=None), "/fallback.stp", 30)
    assert cut.path == "/fallback.stp"


# ── 诚实性：切不到上限要说出来 ────────────────────────────────

def test_cutting_reports_unsplit_blocks():
    cut = A.parse_report(_ok_payload(blocks=41, over_limit=2,
                                     faces={"min": 6, "median": 17, "max": 21}),
                         "/w/decomposed.stp", 20)
    assert cut.degraded
    assert "2 块切不到上限" in cut.summary()
    assert "41 块" in cut.summary()


def test_summary_mentions_the_limit_and_face_range():
    s = A.parse_report(_ok_payload(), "/w/x.stp", 30).summary()
    assert "18 块" in s and "19–30 面" in s and "上限 30" in s


# ── 自证判据（纯函数） ────────────────────────────────────────

def test_boxes_match_within_one_percent():
    a = (1000.0, 2000.0, 3000.0)
    assert A.boxes_match(a, a)
    assert A.boxes_match(a, (1005.0, 1990.0, 3005.0))        # 0.5% 内 → 通过


def test_boxes_match_rejects_scale_error():
    """导出写坏/写空时尺寸会明显不对 —— 必须拦下并回退原文件。"""
    assert not A.boxes_match((1000.0, 2000.0, 3000.0), (100.0, 200.0, 300.0))
    assert not A.boxes_match((1000.0, 2000.0, 3000.0), (1000.0, 2000.0, 300.0))


def test_boxes_match_edge_cases():
    assert not A.boxes_match(None, (1.0, 2.0, 3.0))
    assert not A.boxes_match((1.0, 2.0), (1.0, 2.0, 3.0))    # 维度不一致
    assert A.boxes_match((0.0, 2.0, 3.0), (0.0, 2.0, 3.0))   # 退化轴不参与判定


# ── 可用性（可操作的原因） ────────────────────────────────────

@pytest.fixture
def stub_freecad(monkeypatch, tmp_path):
    """把"这个解释器能 import Part 吗"变成可控：单测不真起 FreeCAD 探测子进程。"""
    exe = tmp_path / "python.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(A, "_imports_freecad", lambda p: True)
    return str(exe)


def test_child_script_exists_in_repo():
    """子进程执行体必须与父模块同目录 —— 冻结后靠 `_keep_py` 落成数据文件。"""
    p = A.child_script_path()
    assert p.endswith("adaptive_cut_freecad.py") and os.path.isfile(p)


def test_find_python_prefers_explicit(stub_freecad, tmp_path, monkeypatch):
    monkeypatch.setattr(A.sys, "executable", "/nope/python.exe")
    assert A.find_python(stub_freecad) == stub_freecad
    # 不存在的路径不算"显式指定"，必须回落，绝不把假路径交给 subprocess
    assert A.find_python(str(tmp_path / "nope.exe")) != str(tmp_path / "nope.exe")
    assert A.find_python(str(tmp_path / "nope.exe")) != ""


def test_unavailable_reason_when_interpreter_lacks_freecad(monkeypatch, tmp_path):
    exe = tmp_path / "python.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(A, "_imports_freecad", lambda p: False)
    reason = A.unavailable_reason(str(exe))
    assert reason and "FreeCAD" in reason and str(exe) in reason


def test_unavailable_reason_when_child_script_missing(monkeypatch, stub_freecad):
    monkeypatch.setattr(A, "child_script_path", lambda: "/nope/adaptive_cut_freecad.py")
    reason = A.unavailable_reason(stub_freecad)
    assert reason and "缺少预分解脚本" in reason


def test_unavailable_reason_none_when_ready(stub_freecad):
    assert A.unavailable_reason(stub_freecad) is None


def test_imports_freecad_is_cached(monkeypatch, tmp_path):
    """探测要起子进程（约 1 秒），每次导入都问一遍 ⇒ 必须按解释器路径缓存。"""
    exe = tmp_path / "python.exe"
    exe.write_bytes(b"MZ")
    A._FREECAD_PROBE_CACHE.clear()
    calls = []

    class _P:
        returncode = 0

    monkeypatch.setattr(A.subprocess, "run", lambda *a, **k: calls.append(a) or _P())
    assert A._imports_freecad(str(exe)) and A._imports_freecad(str(exe))
    assert len(calls) == 1
    A._FREECAD_PROBE_CACHE.clear()


def test_probe_imports_freecad_before_part(monkeypatch, tmp_path):
    """裸 `import Part` 在 FreeCAD 的 python.exe 里必然 ModuleNotFoundError
    （FreeCAD 得先 import 才挂上自己的搜索路径）。顺序错了不会报错，只会**静默跳过
    切割** —— 所以这条顺序是契约，锁住它。"""
    exe = tmp_path / "python.exe"
    exe.write_bytes(b"MZ")
    A._FREECAD_PROBE_CACHE.clear()
    seen = []

    class _P:
        returncode = 0

    monkeypatch.setattr(A.subprocess, "run",
                        lambda cmd, **k: seen.append(cmd[2]) or _P())
    A._imports_freecad(str(exe))
    A._FREECAD_PROBE_CACHE.clear()
    assert seen and seen[0].startswith("import FreeCAD")
    assert "Part" in seen[0] and "BOPTools" in seen[0]


# ── decompose：注入假 runner，无需装 FreeCAD ──────────────────

class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _fake_runner(work_dir_holder, payload=None, *, write_file=True, proc=None):
    """假子进程：照真实协议写 result.json（和 decomposed.stp），并记录命令行。"""
    calls = {}

    def run(cmd, **kw):
        calls["cmd"], calls["kw"] = cmd, kw
        res_path = cmd[3]
        run_dir = os.path.dirname(res_path)
        body = payload if payload is not None else _ok_payload(
            dst=os.path.join(run_dir, "decomposed.stp"))
        if write_file:
            with open(os.path.join(run_dir, "decomposed.stp"), "w") as f:
                f.write("ISO-10303-21;")
        with open(res_path, "w", encoding="utf-8") as f:
            json.dump(body, f)
        return proc or _Proc(stdout="adaptive cut: 3 solids -> 18 blocks")

    return run, calls


def test_decompose_happy_path_and_no_deletion(tmp_path, stub_freecad):
    src = tmp_path / "src.step"
    src.write_text("ISO-10303-21;", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    sentinel = work / "keepme.txt"
    sentinel.write_text("别删我", encoding="utf-8")

    run, calls = _fake_runner(work)
    cut = A.decompose(str(src), str(work), face_limit="medium",
                      python_exe=stub_freecad, _run=run)

    assert cut.blocks == 18 and os.path.isfile(cut.path)
    assert calls["cmd"][0] == stub_freecad
    assert calls["cmd"][1] == A.child_script_path()
    req = json.loads(Path(calls["cmd"][2]).read_text(encoding="utf-8"))
    assert req["src"] == os.path.abspath(str(src))
    assert req["face_limit"] == 30 and req["max_depth"] == 8
    assert sentinel.is_file(), "不得删除 work_dir 里的其它文件"


def test_decompose_writes_nothing_outside_work_dir(tmp_path, stub_freecad):
    work = tmp_path / "w"
    run, calls = _fake_runner(work)
    A.decompose(str(tmp_path / "s.step"), str(work), python_exe=stub_freecad, _run=run)
    run_dir = os.path.dirname(calls["cmd"][2])
    assert os.path.abspath(run_dir).startswith(os.path.abspath(str(work)) + os.sep)


def test_decompose_uses_sys_executable_by_default(stub_freecad, monkeypatch, tmp_path):
    """worker 自己就跑在 FreeCAD 的 python 里 ⇒ 默认解释器就是"能切的那个"。"""
    monkeypatch.setattr(A.sys, "executable", stub_freecad)
    monkeypatch.setattr(A, "find_python", lambda p="": stub_freecad)
    run, calls = _fake_runner(tmp_path / "w")
    A.decompose(str(tmp_path / "s.step"), str(tmp_path / "w"), _run=run)
    assert calls["cmd"][0] == stub_freecad


def test_decompose_rejects_nonpositive_limit(tmp_path, stub_freecad):
    """上限 0/负数 = 不限制 ⇒ 调用方本该跳过；真调用到这里要明确拒绝，别切成无穷块。"""
    run, _ = _fake_runner(tmp_path / "w")
    with pytest.raises(RuntimeError, match="上限必须为正数"):
        A.decompose(str(tmp_path / "s.step"), str(tmp_path / "w"),
                    face_limit=0, python_exe=stub_freecad, _run=run)


def test_decompose_raises_with_child_output_when_no_report(tmp_path, stub_freecad):
    def run(cmd, **kw):
        return _Proc(returncode=1, stdout="部分输出", stderr="errline 崩了")

    with pytest.raises(RuntimeError) as ei:
        A.decompose(str(tmp_path / "s.step"), str(tmp_path / "w"),
                    python_exe=stub_freecad, _run=run)
    msg = str(ei.value)
    assert "未产出报告" in msg
    assert "部分输出" in msg and "errline 崩了" in msg          # 原因不吞


def test_decompose_raises_with_child_error(tmp_path, stub_freecad):
    run, _ = _fake_runner(tmp_path / "w",
                          payload={"ok": False, "error": "OSError: 文件读不了"},
                          write_file=False)
    with pytest.raises(RuntimeError, match="文件读不了"):
        A.decompose(str(tmp_path / "s.step"), str(tmp_path / "w"),
                    python_exe=stub_freecad, _run=run)


def test_decompose_raises_on_empty_output(tmp_path, stub_freecad):
    run, _ = _fake_runner(tmp_path / "w", write_file=False)
    # 报告说成功，但文件根本没写出来
    with pytest.raises(RuntimeError, match="不存在或为空"):
        A.decompose(str(tmp_path / "s.step"), str(tmp_path / "w"),
                    python_exe=stub_freecad, _run=run)


def test_decompose_reports_timeout(tmp_path, stub_freecad):
    def run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 0))

    with pytest.raises(RuntimeError, match="超时"):
        A.decompose(str(tmp_path / "s.step"), str(tmp_path / "w"),
                    python_exe=stub_freecad, timeout=7, _run=run)


def test_decompose_refuses_when_unavailable(tmp_path, monkeypatch):
    """不可用时先抛可操作原因，不浪费一次子进程。"""
    monkeypatch.setattr(A, "_imports_freecad", lambda p: False)
    exe = tmp_path / "python.exe"
    exe.write_bytes(b"MZ")

    def boom(*a, **kw):
        raise AssertionError("不应启动子进程")

    with pytest.raises(RuntimeError, match="FreeCAD"):
        A.decompose(str(tmp_path / "s.step"), str(tmp_path / "w"),
                    python_exe=str(exe), _run=boom)


# ── 接线锁（跨文件，没有别的观察面） ──────────────────────────

def test_worker_uses_its_own_interpreter_and_forwards_the_degree():
    """worker 跑在 FreeCAD python 里 ⇒ 解释器用 sys.executable；档位经 payload 传进来。

    这两条正是被删掉的 MCCAD 路径踩过的坑：外部 exe 需要"由冻结侧解析路径再传进来"
    （worker 非冻结、看不到随包目录）。现在解释器就是 worker 自己，那个坑不复存在 ——
    用这条锁防止有人"为了对称"又把路径发现加回来。
    """
    src = (PROJECT_DIR / "app" / "geouned_worker.py").read_text(encoding="utf-8")
    assert "python_exe = sys.executable" in src
    assert 'face_limit=cut.get("degree")' in src
    assert "adaptive_decompose" in src


def test_converter_sends_cut_section_not_mccad():
    src = (PROJECT_DIR / "app" / "step_importer_geouned.py").read_text(encoding="utf-8")
    assert '"cut": {' in src
    assert 'settings.get("cutSolids"' in src
    assert 'settings.get("cutDegree")' in src
    assert "mccad" not in src.lower()


_SKIP_DIRS = ("__pycache__", "dist", "build", "node_modules", "target",
              ".pytest_cache", "dist_sidecar", "build_sidecar")


def _source_files(*roots):
    for root in roots:
        for p in (PROJECT_DIR / root).rglob("*"):
            if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".spec") \
                    and not any(d in p.parts for d in _SKIP_DIRS):
                yield p


def test_no_source_references_the_removed_mccad_decomposer():
    """MCCAD 已整体移除；残留的 import 会在冻结版变成 ImportError。

    只看**源码树**：`dist_sidecar/`、`gui/dist/` 里是上一次打包的旧副本，
    它们当然还含旧名字，但会被下一次打包覆盖，不算"残留"。
    """
    hits = []
    for p in _source_files("app", "gui/backend", "gui/src"):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "mccad_decompose" in t:
            hits.append(str(p.relative_to(PROJECT_DIR)))
    assert hits == []


def test_nothing_ships_the_mccad_binary():
    """随包分发目录与打包清单里都不该再有 McCAD。"""
    spec = (PROJECT_DIR / "gui" / "mcnp_sidecar.spec").read_text(encoding="utf-8")
    assert "McCAD" not in spec
    assert not (PROJECT_DIR / "vendor" / "mccad").exists()
    assert not (PROJECT_DIR / "app" / "mccad_decompose.py").exists()


def test_worker_bbox_reader_imports_freecad_first():
    """`_bbox_of` 里裸 `import Part` 会让它**永远返回 None** ⇒ 自证判据退化成恒真。"""
    src = (PROJECT_DIR / "app" / "geouned_worker.py").read_text(encoding="utf-8")
    body = src.split("def _bbox_of", 1)[1].split("\ndef ", 1)[0]
    assert "import FreeCAD" in body
    assert body.index("import FreeCAD") < body.index("import Part")


# ── worker 侧自证判据的不对称（刻意设计，锁住它） ──────────────

def _worker(monkeypatch, mapping):
    from app import geouned_worker as W
    monkeypatch.setattr(W, "_bbox_of", mapping)
    return W


def test_selfcheck_falls_back_when_only_the_cut_file_is_unreadable(monkeypatch):
    W = _worker(monkeypatch, lambda p: (1.0, 2.0, 3.0) if p == "orig" else None)
    ok, why = W._cut_selfcheck("orig", "cut")
    assert not ok and "读不出来" in why


def test_selfcheck_passes_when_the_original_is_unreadable(monkeypatch):
    """原文件都读不出来 ⇒ 没有可比对象，放行（读取失败不该阻断导入）。"""
    W = _worker(monkeypatch, lambda p: None)
    assert W._cut_selfcheck("orig", "cut") == (True, "")


def test_selfcheck_detects_bbox_mismatch(monkeypatch):
    W = _worker(monkeypatch, lambda p: (1.0, 2.0, 3.0) if p == "orig" else (10.0, 20.0, 30.0))
    ok, why = W._cut_selfcheck("orig", "cut")
    assert not ok and "包围盒不一致" in why


def test_selfcheck_passes_on_matching_boxes(monkeypatch):
    W = _worker(monkeypatch, lambda p: (1.0, 2.0, 3.0))
    assert W._cut_selfcheck("orig", "cut") == (True, "")


def test_predecompose_is_a_noop_when_disabled(tmp_path, monkeypatch):
    """开关关着 ⇒ 原样返回、一次子进程都不起、也不给任何提示。"""
    from app import geouned_worker as W
    monkeypatch.setattr(W, "_bbox_of", lambda p: None)

    def boom(*a, **kw):
        raise AssertionError("开关关着不该起子进程")

    import app.adaptive_decompose as AD
    monkeypatch.setattr(AD, "decompose", boom)
    assert W._maybe_predecompose("s.step", str(tmp_path), {"enabled": False}) == ("s.step", [])


def _as_workers_dependency(monkeypatch):
    """worker 里的 `import adaptive_decompose` 是**绝对导入**（生产：当脚本跑，
    sys.path[0] 就是 app/）。单测里以 `app.xxx` 的形式导入的是**另一个模块对象**，
    直接 patch 打不中 —— 所以显式把它注册成 worker 会拿到的那一份。"""
    import sys as _sys
    import app.adaptive_decompose as AD
    monkeypatch.setitem(_sys.modules, "adaptive_decompose", AD)
    return AD


def test_predecompose_failure_never_breaks_the_import(tmp_path, monkeypatch):
    """铁律：任何失败都回退原文件，但原因必须变成一条提示传到界面。"""
    from app import geouned_worker as W

    def boom(*a, **kw):
        raise RuntimeError("子进程崩了")

    monkeypatch.setattr(W, "_bbox_of", lambda p: None)
    AD = _as_workers_dependency(monkeypatch)
    monkeypatch.setattr(AD, "unavailable_reason", lambda p="": None)
    monkeypatch.setattr(AD, "decompose", boom)

    path, notes = W._maybe_predecompose("s.step", str(tmp_path),
                                        {"enabled": True, "degree": "medium"})
    assert path == "s.step"
    assert notes and "子进程崩了" in notes[0] and "已跳过" in notes[0]


def test_predecompose_passes_the_degree_and_returns_the_cut_path(tmp_path, monkeypatch):
    from app import geouned_worker as W
    AD = _as_workers_dependency(monkeypatch)
    seen = {}

    class _Cut:
        path, volume_ratio, blocks, faces_max = "cut.step", 1.0, 18, 30
        degraded = False
        def summary(self):
            return "实体预分解已生效：18 块"

    monkeypatch.setattr(W, "_bbox_of", lambda p: (1.0, 2.0, 3.0))
    monkeypatch.setattr(AD, "unavailable_reason", lambda p="": None)

    def fake_decompose(step, out, face_limit=None, python_exe="", **kw):
        seen["face_limit"] = face_limit
        return _Cut()

    monkeypatch.setattr(AD, "decompose", fake_decompose)
    path, notes = W._maybe_predecompose("s.step", str(tmp_path),
                                        {"enabled": True, "degree": "fine"})
    assert path == "cut.step"
    assert seen["face_limit"] == "fine"
    assert notes == ["实体预分解已生效：18 块"]


def test_predecompose_falls_back_when_volume_is_not_conserved(tmp_path, monkeypatch):
    """体积比偏离 1 ⇒ 结果不可信，必须回退（这比"切得不好"严重得多）。"""
    from app import geouned_worker as W
    AD = _as_workers_dependency(monkeypatch)

    class _Cut:
        path, volume_ratio, blocks, faces_max = "cut.step", 0.87, 18, 30
        degraded = False
        def summary(self):
            return "不应该用到这句"

    monkeypatch.setattr(W, "_bbox_of", lambda p: (1.0, 2.0, 3.0))
    monkeypatch.setattr(AD, "unavailable_reason", lambda p="": None)
    monkeypatch.setattr(AD, "decompose", lambda *a, **kw: _Cut())

    path, notes = W._maybe_predecompose("s.step", str(tmp_path),
                                        {"enabled": True, "degree": "medium"})
    assert path == "s.step"
    assert notes and "0.870000" in notes[0]


# ── 真 FreeCAD 端到端（装不上就 skip） ────────────────────────

def _freecad_python():
    from app.freecad_locator import bin_dir
    b = bin_dir()
    if not b:
        return None
    for c in (os.path.join(b, "python.exe"), os.path.join(b, "bin", "python.exe")):
        if os.path.isfile(c):
            return c
    return None


@pytest.fixture(scope="module")
def fc(tmp_path_factory):
    """造一个"6 级台阶"实体：1 个实体、26 个面（实测），面数够多才谈得上"要切"。"""
    exe = _freecad_python()
    if not exe:
        pytest.skip("FreeCAD 不可用，跳过实体预分解真机直验")
    work = tmp_path_factory.mktemp("fc")
    src = work / "stairs.step"
    script = work / "make.py"
    script.write_text(
        "import FreeCAD\n"
        "import Part\n"
        "ss = [Part.makeBox(10, 10, 10, FreeCAD.Vector(i * 5, 0, i * 5)) for i in range(6)]\n"
        "s = ss[0]\n"
        "for t in ss[1:]:\n"
        "    s = s.fuse(t)\n"
        "s = s.removeSplitter()\n"
        "print('solids', len(s.Solids), 'faces', len(s.Faces))\n"
        f"s.exportStep(r'{src}')\n",
        encoding="utf-8")
    p = subprocess.run([exe, str(script)], capture_output=True, text=True, timeout=300)
    if p.returncode != 0 or not src.is_file():
        pytest.skip(f"造测试模型失败：{p.stderr[-200:]}")
    return exe, str(src), work


def test_real_freecad_leaves_a_solid_within_budget_alone(fc):
    """26 面的实体在上限 30 面下**不该被动**：块数守恒、体积守恒、如实报"0 块超限"。"""
    exe, src, work = fc
    cut = A.decompose(src, str(work), face_limit="medium", python_exe=exe)
    assert cut.blocks == 1 and cut.faces_max == 26
    assert cut.over_limit == 0 and not cut.degraded
    assert cut.volume_ratio == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("limit,min_blocks", [(20, 2), (12, 4), (8, 4)])
def test_real_freecad_cut_reaches_the_face_budget(fc, limit, min_blocks):
    """真机收敛性：每块面数必须真的落到上限以内，且体积守恒。"""
    exe, src, work = fc
    cut = A.decompose(src, str(work), face_limit=limit, python_exe=exe)
    assert cut.faces_max <= limit, cut
    assert cut.blocks >= min_blocks, cut
    assert cut.over_limit == 0, cut
    assert cut.volume_ratio == pytest.approx(1.0, abs=1e-6)
    assert os.path.getsize(cut.path) > 0
