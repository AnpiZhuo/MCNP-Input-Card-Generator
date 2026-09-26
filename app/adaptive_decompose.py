# -*- coding: utf-8 -*-
"""实体预分解：按「每块面数上限」自适应切分（FreeCAD/OCC，**不依赖外部程序**）。

为什么需要它
============
GEOUNED 的实体分解是**必经步骤、没有档位**：一个实体永远出 1 个栅元，分解产生的
全部辅助面被塞进那个栅元的布尔表达式。实测 274 m³ 厂房模型 —— 3 个实体直接转出来
是 3 个栅元，其中一个引用了 **146 个面**；`simplify` 开/关、`minArea`、`distance`、
`splitTolerance` 四档模糊化**一个面都压不掉**（逐位相同的输出）。

先切一刀再喂 GEOUNED，每个块就自成 1 个栅元。切法（最长边二分 + 按结果收敛）与
子进程执行体在 `adaptive_cut_freecad.py`，本模块只管：

    档位 → 面数上限      纯函数，无 IO
    可用性判断           FreeCAD 的 python.exe + 子脚本在不在
    起子进程、超时、收报告
    报告 → `Cutting`     **判据在这里，不在子进程的 stdout 里**

实测（本机 274 m³ / 3 实体 / 原面数 27、41、202）
================================================
    上限 50 面 →  9 块，面数 22–50，体积比 1.000000
    上限 30 面 → 18 块，面数 19–30，体积比 1.000000   ← 默认档
    上限 20 面 → 41 块，面数 6–21（其中 2 块切不动），体积比 1.000000
最终栅元侧（喂 GEOUNED 后）：实体面数总和 194 → 367；不切割时是 194/3 块，
切割后 367/18 块 —— 块数换了单块复杂度，单块最大面数 146 → 25。

**切不动就如实上报，不假装达标**
================================
三轴都切不出两块、或到深度上限的块，原样保留并计入报告 `over_limit`/`unsplit`。
上限 20 面时报告会说"41 块里有 2 块仍是 21 面"，而不是一句"已完成"。

**为什么没有 `units` 参数**（与已删除的 MCCAD 路径的关键差别）
============================================================
MCCAD 走配置文件，`units` 声明与 STEP 实际单位不符时它**不报错**、只会让模型整体
差 10 倍，所以那时必须传 `units` 并做包围盒自证。本路径由 FreeCAD 直接读同一个
STEP、在同一个内存坐标系里切、再写出去，**没有单位声明这一环**，这个失败模式不存在。
自证仍然保留（`boxes_match`），因为它拦的是另一种错：导出悄悄失败/写坏。

**为什么子进程用 `sys.executable`**（与已删除的 MCCAD 路径的第二个关键差别）
==========================================================================
本模块在 **geouned worker 进程内**被调用，而 worker 本来就跑在 FreeCAD 的 python.exe
里 —— 那个解释器 `import Part` / `BOPTools.SplitAPI` 开箱可用（实测）。
所以"用哪个解释器"不需要再发现一次：**跑 worker 的那个，就是能切的那个**。
（MCCAD 那时的坑是它是个独立 exe，worker 是非冻结进程看不到随包目录，路径发现
必须由冻结侧的转换器代做 —— 那个坑随外部程序一起消失了。）
"""
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional

# ── 档位（与界面下拉一一对应）──
# 值是**每块面数上限**，不是"深度"：它是可验证的结果指标，而"深度"是过程参数，
# 同样的深度在不同模型上得到的块复杂度完全不同（MCCAD 的 recurrenceDepth 就是
# 后者：模板默认 20，实测仍切出 188 块、单块最多 8 面）。
FACE_LIMIT_CHOICES = {
    "coarse": 50,
    "medium": 30,
    "fine": 20,
}
DEFAULT_FACE_LIMIT = FACE_LIMIT_CHOICES["medium"]

# 子进程执行体（与父侧解释器不同 ⇒ 必须是独立文件，见模块 docstring）
CHILD_SCRIPT = "adaptive_cut_freecad.py"

DEFAULT_TIMEOUT = 900


@dataclass(frozen=True)
class Cutting:
    """一次成功的预分解。`path` 是要接着喂 GEOUNED 的文件。"""
    path: str
    blocks: int
    face_limit: int
    faces_min: int
    faces_median: int
    faces_max: int
    over_limit: int
    volume_ratio: float
    seconds: float

    @property
    def degraded(self) -> bool:
        """有块没切到上限（切不动或到深度上限）。"""
        return self.over_limit > 0

    def summary(self) -> str:
        """给界面看的一句话（中文，含"没做到"的部分）。"""
        s = (f"实体预分解已生效：{self.blocks} 块，每块 {self.faces_min}–{self.faces_max} 面"
             f"（上限 {self.face_limit}），耗时 {self.seconds:.1f} 秒")
        if self.degraded:
            s += f"；其中 {self.over_limit} 块切不到上限"
        return s


def degree_to_face_limit(degree) -> int:
    """界面档位 → 每块面数上限。认不得的值一律回默认档（**不抛异常**：这是界面输入）。

    直接给数字也接受（便于脚本/测试传具体上限）：0 或负数视为"不限制"→ 返回 0，
    调用方据此跳过切割。
    """
    if degree is None or degree == "":
        return DEFAULT_FACE_LIMIT
    if isinstance(degree, bool):
        return DEFAULT_FACE_LIMIT
    if isinstance(degree, (int, float)):
        return max(0, int(degree))
    key = str(degree).strip().lower()
    if key in FACE_LIMIT_CHOICES:
        return FACE_LIMIT_CHOICES[key]
    try:
        return max(0, int(float(key)))
    except ValueError:
        return DEFAULT_FACE_LIMIT


def child_script_path() -> str:
    """子进程执行体的绝对路径。

    `__file__` 在冻结的 sidecar 里指向 `_MEIPASS/app/`（spec 里该文件被登记进
    `_keep_py` ⇒ 作为**数据文件**落盘，磁盘上真实存在），开发机就是仓库的 `app/`。
    """
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CHILD_SCRIPT)


def find_python(python_exe: str = "") -> str:
    """跑子进程用的解释器：显式指定 → `sys.executable`（worker 自己）→ PATH。"""
    if python_exe and os.path.isfile(python_exe):
        return python_exe
    if sys.executable and os.path.isfile(sys.executable):
        return sys.executable
    import shutil
    return shutil.which("python.exe") or shutil.which("python") or ""


_FREECAD_PROBE_CACHE = {}


def _imports_freecad(python_exe: str) -> bool:
    """该解释器能否用 FreeCAD 的几何模块（`Part` / `BOPTools`）。结果按解释器路径缓存
    —— 起一次子进程约 1 秒，而可用性检查会在每次导入时被问到。

    ⚠️ `import FreeCAD` **必须在 `import Part` 之前**（2026-09-24 实测）：FreeCAD 的
    `python.exe` 裸跑 `import Part` 会 `ModuleNotFoundError`，只有先 import FreeCAD
    才把它自己的 bin 挂上模块搜索路径。漏掉这一句的后果不是报错而是**静默跳过切割**
    （`unavailable_reason` 返回"没有 FreeCAD 模块"）—— 用户看到的就是"开了跟没开一样"。
    """
    if not python_exe:
        return False
    if python_exe in _FREECAD_PROBE_CACHE:
        return _FREECAD_PROBE_CACHE[python_exe]
    try:
        p = subprocess.run([python_exe, "-c", "import FreeCAD, Part, BOPTools.SplitAPI"],
                           capture_output=True, timeout=120)
        ok = p.returncode == 0
    except Exception:
        ok = False
    _FREECAD_PROBE_CACHE[python_exe] = ok
    return ok


def unavailable_reason(python_exe: str = "") -> Optional[str]:
    """不可用的原因（中文、可操作）；可用时返回 None。"""
    exe = find_python(python_exe)
    if not exe:
        return "找不到可用的 Python 解释器"
    if not os.path.isfile(child_script_path()):
        return f"缺少预分解脚本：{child_script_path()}"
    if not _imports_freecad(exe):
        return (f"解释器 {exe} 里没有 FreeCAD 模块（Part/BOPTools），无法做实体预分解。"
                f"请确认 FreeCAD 安装完整。")
    return None


def build_request(src: str, dst: str, face_limit: int, *,
                  max_depth: int = 8, eps_cm3: float = 1e-6,
                  max_pieces: int = 4000) -> dict:
    """子进程的请求体（纯函数，便于测试钉住这份**文件格式接口**）。"""
    return {
        "src": os.path.abspath(src),
        "dst": os.path.abspath(dst),
        "face_limit": int(face_limit),
        "max_depth": int(max_depth),
        "eps_cm3": float(eps_cm3),
        "max_pieces": int(max_pieces),
    }


def parse_report(payload: dict, dst: str, face_limit: int) -> Cutting:
    """把子进程写的报告转成 `Cutting`；不成功就抛 RuntimeError（**带原始原因**）。"""
    if not isinstance(payload, dict) or not payload.get("ok"):
        err = (payload or {}).get("error") if isinstance(payload, dict) else str(payload)
        tb = (payload or {}).get("traceback", "") if isinstance(payload, dict) else ""
        raise RuntimeError(f"预分解子进程失败：{err or '报告格式不对'}"
                           + (f"\n{tb}" if tb else ""))
    r = payload.get("report") or {}
    f = r.get("faces") or {}
    return Cutting(
        path=r.get("dst") or dst,
        blocks=int(r.get("blocks") or 0),
        face_limit=int(r.get("face_limit") or face_limit),
        faces_min=int(f.get("min") or 0),
        faces_median=int(f.get("median") or 0),
        faces_max=int(f.get("max") or 0),
        over_limit=int(r.get("over_limit") or 0),
        volume_ratio=float(r.get("volume_ratio") or 0.0),
        seconds=float(r.get("seconds") or 0.0),
    )


def boxes_match(a, b, tol: float = 0.01) -> bool:
    """自证判据：两组包围盒尺寸是否一致（相对差 ≤ tol）。

    拦的是"导出悄悄写坏/写空"。读不到包围盒的调用方不该用本函数下结论（见 worker）。
    """
    if not a or not b or len(a) != len(b):
        return False
    for x, y in zip(a, b):
        x, y = abs(float(x)), abs(float(y))
        scale = max(x, y)
        if scale <= 0:
            continue
        if abs(x - y) / scale > tol:
            return False
    return True


def _tail(text: Optional[str], n: int = 400) -> str:
    t = (text or "").strip()
    return t[-n:] if len(t) > n else t


def decompose(step_path: str, work_dir: str, face_limit=None,
              python_exe: str = "", timeout: int = DEFAULT_TIMEOUT,
              *, _run=subprocess.run) -> Cutting:
    """按面数上限把 STEP 预分解成多实体 STEP。

    `face_limit`：每块面数上限（接受档位名或数字，见 `degree_to_face_limit`）。
    `python_exe`：跑子进程的解释器；默认 `sys.executable`（worker 自己，见模块 docstring）。
    `_run` 是注入点（默认 `subprocess.run`）：测试可传假 runner，无需装 FreeCAD。

    失败一律抛 RuntimeError，message 含子进程的原始报错（**不吞原因**）。
    副作用范围：只在 `work_dir` 内写文件。
    """
    limit = degree_to_face_limit(face_limit)
    if limit <= 0:
        raise RuntimeError("每块面数上限必须为正数")

    exe = find_python(python_exe)
    reason = unavailable_reason(exe)
    if reason:
        raise RuntimeError(reason)

    os.makedirs(work_dir, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix="cut_", dir=work_dir)
    req_path = os.path.join(run_dir, "request.json")
    res_path = os.path.join(run_dir, "result.json")
    dst = os.path.join(run_dir, "decomposed.stp")
    with open(req_path, "w", encoding="utf-8") as f:
        json.dump(build_request(step_path, dst, limit), f, ensure_ascii=False)

    try:
        proc = _run([exe, child_script_path(), req_path, res_path],
                    capture_output=True, text=True, timeout=timeout,
                    env=os.environ.copy())
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"实体预分解超时（>{timeout} 秒）")

    if not os.path.isfile(res_path):
        raise RuntimeError(
            "实体预分解未产出报告。\n"
            f"退出码：{getattr(proc, 'returncode', '?')}\n"
            f"stdout 尾部：{_tail(getattr(proc, 'stdout', ''))}\n"
            f"stderr 尾部：{_tail(getattr(proc, 'stderr', ''))}"
        )
    with open(res_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    cut = parse_report(payload, dst, limit)
    if not os.path.isfile(cut.path) or os.path.getsize(cut.path) == 0:
        raise RuntimeError(f"预分解产出的文件不存在或为空：{cut.path}")
    return cut
