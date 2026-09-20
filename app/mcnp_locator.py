"""
MCNP 定位模块 — 唯一负责「这台机器上有哪些 MCNP」与「用户选了跑哪一个」的地方。

为什么值得单独立一个模块：

1. **api_server.py 不能被 pytest import**（模块级 FreeCAD/pyvista 探测会污染纯引擎测试），
   所以想被单测覆盖的逻辑必须搬出那个文件；
2. **「MCNP5 和 MCNP6 都装了」是真实用户场景**，而原 `_find_mcnp_exe()` 找到第一个就
   `return` ⇒ 两个版本只会显示其中一个，用户无从选择；版本标签也只是猜
   （"文件名里有 5 就是 MCNP5"）；
3. MCNP5 与 MCNP6 的 xsdir **互不通用**，所以「选了哪个版本」必须能带出
   「这个版本自己的数据目录」，否则切了版本、截面库还是上一个版本的。

搜索来源（**全部候选都收**，按来源可信度排序，不再提前返回）：
    0. 用户上次在下拉里选定的（config.json，见 `app/user_config.py`）
    1. PATH（进程 PATH + 注册表里系统/用户环境变量的 Path）
    2. 注册表 ``SOFTWARE\\MCNP`` / ``Wow6432Node\\MCNP`` 的 ``InstallPath``（递归）
    3. 常见安装根目录递归（``D:\\MCNP`` / ``C:\\Program Files\\MCNP`` / ``C:\\MCNP``）

接口：
    detect_all(force=False) -> list[dict]   全部候选（去重 + 稳定排序）
    label_for(exe)          -> str          "MCNP5" / "MCNP6" / "MCNP?"
    xsdir_for(exe)          -> str | None   该 exe 所属安装自带的 xsdir
    saved()                 -> str | None   用户选定的 exe（文件仍存在才返回）
    save(exe)               -> None         持久化选择（空串 = 清除，回到自动检测）
    selected()              -> str | None   用户选的 > 自动检测第一个
    resolve(hint)           -> str          前端传的 > 用户选的 > 自动检测第一个
    reset_cache()           -> None         清进程内检测缓存

要支持更多可执行文件名（``mcnp6.2.exe`` / ``mcnp602.exe`` / ``mcnp5`` …），
只改 `_EXE_NAMES` 一处即可 —— 其余逻辑都以它为准。
"""

import os
from typing import Optional

# 两种导入路径都得活：api_server 把 app/ 直接挂 sys.path（**顶层名** mcnp_locator），
# 而单测/打包走包路径（app.mcnp_locator）—— 只写一种必在另一条路径上 ImportError。
try:
    import user_config
except ImportError:  # pragma: no cover - 取决于调用方怎么挂 sys.path
    from app import user_config

# 认得出的可执行文件名（小写比较）。与改造前 `_find_mcnp_exe` 的匹配集保持一致：
# 只扩这一处，别在各搜索分支里各写一份。
_EXE_NAMES = ("mcnp6.exe", "mcnp5.exe", "mcnp6", "mcnp5")

# 常见安装根（实测用户机器就这几处）。递归深度**不设上限**：宁可慢一点，
# 也不能因为装得深就报"没装 MCNP"（进程内有缓存，重复请求不会再走一遍）。
_SEARCH_ROOTS = (r"D:\MCNP", r"C:\Program Files\MCNP", r"C:\MCNP")

# xsdir 相对安装根的可能位置：MCNP6 是 <root>\MCNP_DATA\xsdir，
# MCNP5 常见 <root>\DATA\xsdir（大写 DATA），个别安装把 xsdir 直接放根下。
_XSDIR_RELS = ("MCNP_DATA/xsdir", "DATA/xsdir", "data/xsdir", "xsdir")

# 从 exe 所在目录往上找几层：实测 <root>\MCNP_CODE\bin\mcnp6.exe 要上 2 层、
# <root>\bin\mcnp5.exe 要上 1 层；留 4 层余量给"安装根下再套一层"的布局。
_MAX_UP = 4

_cache: Optional[list] = None


# ===================================================================
# 判定：版本标签 / 自带 xsdir
# ===================================================================

def label_for(exe: str) -> str:
    """由可执行文件名判版本标签（契约取值：MCNP6 / MCNP5 / MCNP?）。"""
    if not exe:
        return "MCNP?"
    n = os.path.basename(exe).lower()
    if "5" in n:
        return "MCNP5"
    if "6" in n:
        return "MCNP6"
    return "MCNP?"


def xsdir_for(exe: str) -> Optional[str]:
    """该 exe 所属安装里自带的 xsdir；找不到返回 None。

    逐层往上（最多 `_MAX_UP` 层）在每一层试 `_XSDIR_RELS`，**只认真实存在的文件**：
    宁可回 None（上层再回落到环境变量 / 常见路径），也不猜一个不存在的路径 ——
    猜错会让 ZAID 校验与材料库按错误的库作答，比"没找到"更难查。
    """
    if not exe:
        return None
    d = os.path.dirname(os.path.abspath(exe))
    for _ in range(_MAX_UP):
        for rel in _XSDIR_RELS:
            cand = os.path.join(d, *rel.split("/"))
            if os.path.isfile(cand):
                return cand
        parent = os.path.dirname(d)
        if parent == d:  # 到盘根，停
            break
        d = parent
    return None


# ===================================================================
# 搜索来源
# ===================================================================

def _iter_path_dirs():
    """进程 PATH + 注册表里的系统/用户 Path（GUI 启动的 sidecar 常吃不到新 PATH）。"""
    dirs = []
    for p in os.environ.get("PATH", "").split(os.pathsep):
        p = p.strip().strip('"')
        if p:
            dirs.append(p)
    try:
        import winreg
        for key, subkey in (
            (winreg.HKEY_LOCAL_MACHINE,
             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        ):
            try:
                with winreg.OpenKey(key, subkey) as h:
                    val = winreg.QueryValueEx(h, "Path")[0]
                for p in str(val).split(";"):
                    p = p.strip().strip('"')
                    if p:
                        dirs.append(p)
            except OSError:
                pass
    except ImportError:  # 非 Windows
        pass
    seen = set()
    for d in dirs:
        k = os.path.normcase(d)
        if k not in seen:
            seen.add(k)
            yield d


def _from_path_env() -> list:
    """PATH 各目录**当层**找可执行文件（不递归：PATH 目录可能极大）。"""
    out = []
    for d in _iter_path_dirs():
        try:
            if not os.path.isdir(d):
                continue
            names = os.listdir(d)
        except OSError:
            continue
        for f in names:
            if f.lower() in _EXE_NAMES:
                out.append(os.path.join(d, f))
    return out


def _from_registry() -> list:
    """注册表 ``SOFTWARE\\MCNP`` 的 InstallPath → 递归找（MCNP 安装器会写它）。"""
    out = []
    try:
        import winreg
    except ImportError:
        return out
    for key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey in (r"SOFTWARE\MCNP", r"SOFTWARE\Wow6432Node\MCNP"):
            try:
                with winreg.OpenKey(key, subkey) as h:
                    install = winreg.QueryValueEx(h, "InstallPath")[0]
            except OSError:
                continue
            if not install or not os.path.isdir(install):
                continue
            for root, _dirs, files in os.walk(install):
                for fn in files:
                    if fn.lower() in _EXE_NAMES:
                        out.append(os.path.join(root, fn))
    return out


def _from_common_roots() -> list:
    """常见安装根递归找（用户把 MCNP 装在 D:\\MCNP 之外也能命中注册表/PATH 两条路）。"""
    out = []
    for base in _SEARCH_ROOTS:
        if not base or not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for fn in files:
                if fn.lower() in _EXE_NAMES:
                    out.append(os.path.join(root, fn))
    return out


# ===================================================================
# 候选清单（去重 + 稳定排序）
# ===================================================================

def _sort_key(c: dict):
    """MCNP6 在前、MCNP5 在后，同版本按路径字典序 —— 保证下拉顺序**稳定可预期**。

    不按"发现顺序"排：os.walk 的顺序随文件系统变化，用户会看到下拉每次不一样。
    """
    rank = {"MCNP6": 0, "MCNP5": 1}.get(c.get("label", ""), 2)
    return (rank, str(c.get("exe", "")).lower())


def detect_all(force: bool = False) -> list:
    """全部 MCNP 候选：[{exe, label, source, xsdir}, …]（进程内缓存，force 重扫）。

    `source` 是这条候选**从哪找到的**（用户选择 / PATH / 注册表 / 常见目录）——
    用户报"检测不到"时，这一列就能直接定位是哪条搜索路断了。
    """
    global _cache
    if _cache is not None and not force:
        return [dict(c) for c in _cache]

    found: dict = {}

    def _add(p: str, source: str) -> None:
        if not p:
            return
        try:
            if not os.path.isfile(p):
                return
        except OSError:
            return
        k = os.path.normcase(os.path.abspath(p))
        if k in found:  # 同一条 exe 被多条来源命中：保留先到的（来源按可信度排序）
            return
        found[k] = {
            "exe": os.path.abspath(p),
            "label": label_for(p),
            "source": source,
            "xsdir": xsdir_for(p) or "",
        }

    _add(saved() or "", "用户选择")
    for p in _from_path_env():
        _add(p, "PATH")
    for p in _from_registry():
        _add(p, "注册表")
    for p in _from_common_roots():
        _add(p, "常见目录")

    _cache = sorted(found.values(), key=_sort_key)
    return [dict(c) for c in _cache]


# ===================================================================
# 用户选择（config.json 的 mcnp_exe 键）
# ===================================================================

def saved() -> Optional[str]:
    """用户在下拉里选定的 exe；**文件已不存在则返回 None**（卸载后不该继续选中它）。"""
    p = user_config._value("mcnp_exe")
    if p and os.path.isfile(p):
        return p
    return None


def save(exe: str) -> None:
    """持久化用户选择（空串/None = 清除，回到自动检测）。"""
    user_config.set_values(mcnp_exe=exe)
    reset_cache()


def selected() -> Optional[str]:
    """用户选的 > 自动检测第一个；一个都没有返回 None。"""
    s = saved()
    if s:
        return s
    all_ = detect_all()
    return all_[0]["exe"] if all_ else None


def resolve(hint: str = "") -> str:
    """前端传的 > 用户选的 > 自动检测第一个；都没有返回空串。

    前端传来的路径**必须真实存在**才采信：localStorage 里的旧存档可能指着一个
    已卸载的版本，直接开跑只会得到一句看不懂的 FileNotFoundError。
    """
    h = (hint or "").strip().strip('"')
    if h and os.path.isfile(h):
        return h
    return selected() or ""


def reset_cache() -> None:
    global _cache
    _cache = None
