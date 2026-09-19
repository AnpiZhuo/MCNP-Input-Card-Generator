"""原生文件选择窗口的**规格**（纯 stdlib，可单测，无 tkinter 依赖）。

`/api/choose-file` 只负责"弹窗"（tkinter 是模态的、无法单测）；"弹什么标题、
给哪些文件类型、默认选哪一类、要不要把文件内容一起读回来"这类**规格**放这里，
由 `gui/backend/api_server.py` 经 `_import_app("file_dialog")` 取用。

为什么 mctal 的默认类型是"无后缀"：MCNP 的 mctal 文件**本体没有扩展名**
（运行目录下就叫 `mctal` / `mctal_001`）。若像 INP 那样默认给 `*.inp *.i *.txt`
或给 `*.o` 过滤，用户打开窗口时**看不见自己的文件**，还得手动把下拉切到
"所有文件"—— 这一卡要消掉的正是这一步。

三种 kind：

- ``inp``（默认，兼容老调用）：MCNP 输入卡 `*.inp *.i *.txt`；
- ``mctal``：**默认无后缀**（首项过滤 = `*`，不加任何扩展名约束）；
- ``outp``：MCNP 输出文件 `*.o *.outp *.out`。
"""

from __future__ import annotations

KIND_INP = "inp"
KIND_MCTAL = "mctal"
KIND_OUTP = "outp"

DEFAULT_KIND = KIND_INP

# kind → {title, filetypes}；filetypes[0] 即**对话框默认选中**的那一类（Tk 约定）
_SPECS: dict[str, dict] = {
    KIND_INP: {
        "title": "选择 MCNP INP 文件",
        "filetypes": [("MCNP 输入卡", "*.inp *.i *.txt"), ("所有文件", "*.*")],
    },
    KIND_MCTAL: {
        "title": "选择 mctal 文件（通常无扩展名）",
        "filetypes": [("mctal（无后缀文件）", "*"), ("所有文件", "*.*")],
    },
    KIND_OUTP: {
        "title": "选择 MCNP 输出文件（.o / .outp / .out）",
        "filetypes": [("MCNP 输出文件", "*.o *.outp *.out"), ("所有文件", "*.*")],
    },
}


def dialog_spec(data: dict | None = None) -> dict:
    """入参 → ``{"kind", "title", "filetypes", "with_content"}``。

    - ``kind`` 缺省/未知 ⇒ ``inp``（老调用方一个字段都不传时行为不变）；
    - ``withContent=false`` ⇒ 只回路径、**不读文件内容**（keff 解析只要路径，
      而 outp 动辄几百 MB，读回内容纯属浪费；缺省 true 兼容既有调用方）；
    - 只认 ``kind``，**不接受调用方自带 filetypes/title** —— 免开注入面。
    """
    data = data or {}
    kind = str(data.get("kind") or DEFAULT_KIND).strip().lower()
    if kind not in _SPECS:
        kind = DEFAULT_KIND
    spec = _SPECS[kind]
    with_content = data.get("withContent", True)
    return {
        "kind": kind,
        "title": spec["title"],
        "filetypes": [list(ft) for ft in spec["filetypes"]],   # 拷贝：别让调用方改到常量
        "with_content": with_content if isinstance(with_content, bool) else True,
    }


__all__ = ["dialog_spec", "KIND_INP", "KIND_MCTAL", "KIND_OUTP", "DEFAULT_KIND"]
