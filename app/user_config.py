"""
用户级配置 config.json — **唯一读写口**。

位置：``%APPDATA%\\mcnp_generator\\config.json``（Web 路径也用它）。

为什么要有这个模块：这份文件是**多个设置共享**的（`freecad_path` / `mcnp_exe` …），
而各定位模块原来各自 `json.dump({自己那个键})` —— **整体覆盖**会把别人的键抹掉
（实测路径：先选 FreeCAD，再在顶栏选 MCNP 版本 ⇒ `freecad_path` 被清空）。
所以写口收敛到这里，只做「读 → 改指定键 → 写回」，不提供"整份写入"。

接口：
    path()            -> str            配置文件绝对路径（目录不存在则创建）
    load()            -> dict           整份配置（读不到/坏了返回 {}，永不抛）
    get(key, default) -> Any            单键读取
    set_values(**kv)  -> None           只覆盖给定键；值为 None 或空串 ⇒ 删除该键
"""

import json
import os
from typing import Any, Optional


def path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "mcnp_generator")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "config.json")


def load() -> dict:
    """整份配置；文件缺失/损坏/不是对象一律返回 {}（配置坏掉不该让功能起不来）。"""
    try:
        with open(path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set_values(**kv: Any) -> None:
    """读-改-写：**只动给定键**，其它键原样保留。

    值是 ``None`` 或空串 ⇒ **删除**该键：对"用户清除了选择"和"从没选过"，
    下游 `get()` 应当给同一个答案，否则会留下 `"mcnp_exe": ""` 这种假选择。
    """
    cfg = load()
    for k, v in kv.items():
        if v is None or (isinstance(v, str) and not v.strip()):
            cfg.pop(k, None)
        else:
            cfg[k] = v
    try:
        with open(path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _value(key: str, default: Optional[str] = None) -> Optional[str]:
    """取一个字符串设置并去空白/引号（粘贴路径常带引号）。"""
    v = get(key)
    if not isinstance(v, str):
        return default
    v = v.strip().strip('"')
    return v or default
