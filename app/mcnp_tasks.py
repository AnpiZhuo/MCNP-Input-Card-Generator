"""
mcnp_tasks — MCNP 命令行 `tasks N`（OpenMP 线程数）的解析与安全校验（纯 stdlib 深模块）。

**为什么独立成模块**：项目纪律规定 *pytest 进程不得 import gui.backend.api_server*
（会引入 pyvista/FreeCAD 探测污染），所以这段纯逻辑必须住在 `app/` 下才能被单测覆盖。
⚠️ 新增 `app/` 模块必须同步登记进 `gui/mcnp_sidecar.spec` 的 `_keep_py`，否则冻结包里
import 失败 —— 这正是 TD-02（部署版 `/api/diff-inp` 500）的成因，`test_sidecar_spec_keep.py`
是守这条的闸门。

**权威依据**（C810.pdf 页 875）::

    "DBCN(2,3,4), SSW, and PTRAC are incompatible with tasks > 1 (FATAL error)."

⇒ 命中这些卡时必须把 `tasks` 压回 1，否则用户一点「运行 MCNP」就 FATAL。

**实测**（AMD Ryzen 7 4800H，8 物理核 / 16 逻辑核，10M 历史；`tasks N` 加在命令行末尾）::

    tasks=1   wall 22.35s   cpu  22.22s   cpu/wall  0.99
    tasks=4   wall  8.38s   cpu  33.20s   cpu/wall  3.96
    tasks=8   wall  8.36s   cpu  65.50s   cpu/wall  7.83   ← 最优
    tasks=16  wall 15.06s   cpu 205.73s   cpu/wall 13.66   ← 超订，反而最慢

⇒ `tasks` 应取**物理核数**而非逻辑核数（16 个线程挤 8 个物理核，SMT 对计算密集型无
吞吐收益，205s CPU 里大半是自旋等待）。前端滑杆上限给逻辑核数（拿不到物理核）、
推荐值给物理核估算，见 `gui/src/utils/detectedCores.ts`。

另注：`tasks` 只在 **OpenMP 构建**的 MCNP 上生效；判据是输出里出现
"comment.  threading will be used when possible in portions of mcnp6."。
非线程版会**静默忽略** `tasks`（不报错，也不加速）。
"""
import os
import re

__all__ = ["expand_mcnp_numbers", "detect_tasks_conflict", "resolve_mcnp_tasks"]

#: 与 tasks > 1 不兼容的卡（C810 页 875）
_TASKS_EXCLUSIVE = (
    (re.compile(r"^\s*ptrac\b", re.I), "PTRAC 卡"),
    (re.compile(r"^\s*ssw\b", re.I), "SSW 面源卡"),
    (re.compile(r"^\s*ssr\b", re.I), "SSR 面源卡"),
)


def expand_mcnp_numbers(tokens):
    """MCNP 数值串 → 浮点列表，展开 `nJ`/`nj` 跳格（= n 个 0）。非数值项记 None。

    仅用于 DBCN 卡第 2/3/4 项的判定；不追求完整 MCNP 语法（跨行续卡不在此展开，
    缺项按 MCNP 缺省 0 处理）。
    """
    out = []
    for t in tokens:
        m = re.fullmatch(r"(\d+)[jJ]", t or "")
        if m:
            out.extend([0.0] * int(m.group(1)))
            continue
        try:
            out.append(float(t))
        except (TypeError, ValueError):
            out.append(None)
    return out


def detect_tasks_conflict(inp_text):
    """返回与 tasks>1 冲突的卡描述（空串 = 无冲突）。按行扫，跳过 C 注释行与 $ 行内注释。"""
    for raw in (inp_text or "").splitlines():
        line = raw.split("$", 1)[0].strip()
        if not line or line[0] in ("c", "C"):
            continue
        for pat, label in _TASKS_EXCLUSIVE:
            if pat.match(line):
                return label
        m = re.match(r"^\s*dbcn\b(.*)$", line, re.I)
        if m:
            nums = expand_mcnp_numbers([t for t in re.split(r"[\s,]+", m.group(1).strip()) if t])
            # 第 2/3/4 项（0-based 1/2/3）非零即冲突；缺项按 MCNP 缺省 0 处理
            for idx in (1, 2, 3):
                if idx < len(nums) and nums[idx] != 0.0:
                    return "DBCN 卡的第 %d 项" % (idx + 1)
    return ""


def resolve_mcnp_tasks(requested, inp_text):
    """请求的线程数 → ``(tasks, note)``。非法/缺省回退 1；命中排他卡强制 1 并给出原因。

    上限夹到 ``os.cpu_count()``（逻辑核）；**不**主动降到物理核 —— 那是用户的选择，
    前端只在滑杆旁给"推荐值"提示。
    """
    try:
        n = int(requested)
    except (TypeError, ValueError):
        n = 1
    n = max(1, min(int(os.cpu_count() or 1), n))
    if n <= 1:
        return 1, ""
    conflict = detect_tasks_conflict(inp_text)
    if conflict:
        return 1, ("输入卡含 %s：MCNP 规定它与 tasks > 1 不兼容（会 FATAL），已自动改用单线程。"
                   "如需多核请先移除该卡。" % conflict)
    return n, ""
