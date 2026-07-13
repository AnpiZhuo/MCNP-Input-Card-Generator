"""
MCNP 版本检测：自动探测已安装的 MCNP 可执行文件
"""

import os
import shutil


CANDIDATES = [
    ("mcnp6.exe", "MCNP6"),
    ("mcnp5.exe", "MCNP5"),
]

SEARCH_PATHS = [
    r"D:\MCNP\MCNP6",
    r"D:\MCNP6",
    r"D:\MCNP\MCNP6.1",
    r"D:\MCNP\MCNP5",
    r"D:\MCNP5",
    r"C:\Program Files\MCNP6",
    r"C:\Program Files (x86)\MCNP6",
    r"C:\Program Files\MCNP5",
    r"C:\Program Files (x86)\MCNP5",
]


def detect_mcnp(saved_exe: str = "") -> tuple[str, str, bool]:
    """
    检测 MCNP 版本，返回 (exe_name, label, found)。
    found=False 表示未检测到任何已知版本。
    """
    # 优先使用用户先前选择
    if saved_exe:
        for exe, label in CANDIDATES:
            if saved_exe == exe or saved_exe == label:
                return (exe, label, True)

    # 查 PATH
    for exe, label in CANDIDATES:
        if shutil.which(exe):
            return (exe, label, True)

    # 查常见安装目录
    for exe, label in CANDIDATES:
        for p in SEARCH_PATHS:
            full = os.path.join(p, exe)
            if os.path.isfile(full):
                return (exe, label, True)

    # 都没找到
    return ("mcnp6.exe", "MCNP?", False)
