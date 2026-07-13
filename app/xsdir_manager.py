"""
截面库索引文件 (xsdir) 加载与管理
"""

import os

from app.xsdir_db import DB as xsdir_db


def find_xsdir_from_env() -> str:
    """从环境变量 XSDIR / DATAPATH 自动探测 xsdir 文件路径"""
    for var in ("XSDIR", "xsdir"):
        val = os.environ.get(var, "")
        if val and os.path.isfile(val):
            return val
    datapath = os.environ.get("DATAPATH", "")
    if datapath:
        candidate = os.path.join(datapath, "xsdir")
        if os.path.isfile(candidate):
            return candidate
    return ""


def load_xsdir(saved_path: str = "") -> tuple[bool, int]:
    """
    加载 xsdir 文件。返回 (loaded, count)。
    """
    ok = xsdir_db.load(saved_path) if saved_path else False
    if ok:
        return (True, xsdir_db.count())
    return (False, 0)
