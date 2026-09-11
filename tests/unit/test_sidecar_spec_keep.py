# -*- coding: utf-8 -*-
"""TD-34（t8）：sidecar 打包白名单自动闸门 —— `mcnp_sidecar.spec` ↔ `api_server` 双向一致。

## 为什么需要这条闸门
`gui/mcnp_sidecar.spec` 的 `_keep_py` / `_keep_dirs` 是**手写白名单**，确定"哪些 `app/` 模块
会被拷进冻结包 `_internal/app/`"。而 `gui/backend/api_server.py` 里有一批模块是
`_import_app("名字")` **动态** import 的（PyInstaller 静态分析看不到），必须显式登记。

**这个缺口历史上已复发两次**：
- `material_library.py` 与 `gpu_pref.py` 曾漏登记 → 打包版 `/api/material-library*`、
  `/api/set-gpu-preference` **ImportError → 端点 500**（PROJECT_MEMORY.md:97 记「spec
  `_keep_py` 加 `material_library.py`」）；
- `diff_inp.py` 也曾漏登记 → 打包版 `/api/diff-inp` 必 500（t2 审计 BE-05）。

**dev 模式永远发现不了**：源码运行时 `APP_DIR` 直接进 `sys.path`，动态 import 一定成功；
只有冻结包会炸。所以此前唯一的防线是"每次打包人工核对 spec"（`docs/手动打包方法.md:506`）
—— 属人因防线。本文件把它换成工程防线。

## 硬约束（务必遵守）
**绝对不要 `import gui.backend.api_server`**（本项目 §5 明令）：它有模块级 pyvista / FreeCAD
探测，import 会污染测试进程。本文件**只读源码文本 + `ast` 解析**。

## 三向集合口径
1. **spec 白名单**：从 spec 文本解析 `_keep_py`（app 顶层文件名）与 `_keep_dirs`（app 子目录名）。
2. **动态 import 名**：`api_server.py` 里 `_import_app("…")` 的字符串实参。
3. **静态 import 边**：`api_server.py` 的模块级 import（含 `from app import lattice` 这类
   **dotted** 形态）—— 这类模块会被 PyInstaller 自动收进 PYZ，无需登记 `_keep_py`。

`被动态 import 的名字` 必须满足：**在 `_keep_py` 里** 或 **在 `_keep_dirs` 覆盖的子包里**
或 **有静态 import 边**。三者皆无 ⇒ 打包版必 500 ⇒ 本闸门红。
"""
import ast
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
SPEC_PATH = PROJECT_DIR / "gui" / "mcnp_sidecar.spec"
API_SERVER = PROJECT_DIR / "gui" / "backend" / "api_server.py"


# ── 1. spec 解析（纯文本，不 exec spec：spec 里会 collect_submodules("pymcnp")）──
def _parse_keep_py(spec_text: str) -> list[str]:
    """取 `_keep_py = [ ... ]` 列表里的字符串字面量（顺序即声明顺序）。"""
    m = re.search(r"^_keep_py\s*=\s*\[(.*?)^\]", spec_text, re.S | re.M)
    assert m, "mcnp_sidecar.spec 中找不到 _keep_py 列表（结构变了？请同步本闸门）"
    return re.findall(r'"([^"]+)"', m.group(1))


def _parse_keep_dirs(spec_text: str) -> list[str]:
    m = re.search(r"^_keep_dirs\s*=\s*\[(.*?)\]", spec_text, re.S | re.M)
    assert m, "mcnp_sidecar.spec 中找不到 _keep_dirs 列表（结构变了？请同步本闸门）"
    return re.findall(r'"([^"]+)"', m.group(1))


def _parse_hidden(spec_text: str) -> list[str]:
    """spec 里出现的全部字符串字面量（用于"该模块名是否被登记进 hiddenimports"这条断言）。

    故意**不**去精确解析 `_hidden` 的语句结构：spec 里既有
    `_hidden = [m for m in collect_submodules("pymcnp") ...]`（推导式，跨行、无静态字面量），
    又有 `_meshtal_mods = [...]` → `_hidden += _meshtal_mods` 的**变量间接**形态，
    精确解析脆而易碎。这里退一步：取全 spec 的字面量集合——
    对"某模块名是否被登记"这类断言足够，且 spec 结构再变也不会失效。
    """
    return re.findall(r'"([^"]+)"', spec_text)


# ── 2. api_server 源码解析（ast，绝不 import）──
def _api_server_ast() -> ast.Module:
    return ast.parse(API_SERVER.read_text(encoding="utf-8"))


def _dynamic_import_names() -> set[str]:
    """`_import_app("name")` 的字符串实参（含位置参数 base_dir 的调用）。"""
    names: set[str] = set()
    for node in ast.walk(_api_server_ast()):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_import_app" and node.args):
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                names.add(arg.value)
    return names


def _static_import_edges() -> set[str]:
    """api_server **模块级** import 覆盖到的 app 顶层模块名（去前缀后的顶层名）。

    - `from app import lattice` / `from app.generator import x` → 记 `app`（dotted 形态）；
      另把 `lattice` 也记为「曾被 dotted 引用」以便下面单独作证。
    - `from models import …` / `from xsdir_db import …`（顶层名形态）→ 记该名。
    """
    edges: set[str] = set()
    tree = _api_server_ast()
    for node in tree.body:  # 只看模块级（函数内 import 不算"静态边"）
        if isinstance(node, ast.Import):
            for a in node.names:
                edges.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                edges.add(node.module.split(".")[0])
    return edges


def _dotted_imported_submodules() -> set[str]:
    """模块级 `from app import X` / `from app.X import …` 中被引用的 app 子模块名。"""
    subs: set[str] = set()
    for node in _api_server_ast().body:
        if isinstance(node, ast.ImportFrom) and node.module == "app":
            for a in node.names:
                subs.add(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
            subs.add(node.module.split(".")[1])
    return subs


# ── 3. 闸门本体 ─────────────────────────────────────────────
def test_spec_file_exists_and_parses():
    """spec 与 api_server 都必须存在且可解析（否则下面的断言会静默失去意义）。"""
    assert SPEC_PATH.is_file(), f"缺少 {SPEC_PATH}"
    assert API_SERVER.is_file(), f"缺少 {API_SERVER}"
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    keep_py = _parse_keep_py(spec_text)
    keep_dirs = _parse_keep_dirs(spec_text)
    assert "models.py" in keep_py, f"_keep_py 解析异常（拿到 {keep_py[:5]}…）"
    assert "generator" in keep_dirs, f"_keep_dirs 解析异常（拿到 {keep_dirs}）"
    assert _dynamic_import_names(), "未解析到任何 _import_app(...) 调用（api_server 结构变了？）"


def test_every_dynamic_import_is_reachable_in_frozen_sidecar():
    """**核心闸门**：每个被 `_import_app("…")` 动态 import 的模块，在冻结包里都必须可达。

    可达 = ① 在 `_keep_py` 顶层清单里；或 ② 属于 `_keep_dirs` 覆盖的子包（generator/meshtal/…）；
    或 ③ api_server 有**模块级静态 import 边**（PyInstaller 会自动收进 PYZ）。

    三者皆无 ⇒ 打包版必 ImportError → 端点 500（dev 模式不复现）。
    红时的修法：把该模块加进 `_keep_py`（若是 app 顶层 .py），或确认它确有静态边。
    """
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    keep_py = {f[:-3] for f in _parse_keep_py(spec_text) if f.endswith(".py")}
    keep_dirs = set(_parse_keep_dirs(spec_text))
    static_edges = _static_import_edges()
    dotted_subs = _dotted_imported_submodules()
    dynamic = _dynamic_import_names()

    unreachable = []
    for name in sorted(dynamic):
        if name in keep_py:            # ① 显式白名单
            continue
        if name in keep_dirs:          # ② 子包整目录 _walk_add
            continue
        if name in static_edges:       # ③ 顶层名静态边（from name import …）
            continue
        if name in dotted_subs:        # ③ dotted 边（from app import name）
            continue
        unreachable.append(name)

    assert not unreachable, (
        "以下模块被 api_server 动态 import，但**既不在 spec `_keep_py`、也不被 `_keep_dirs` "
        "覆盖、也无模块级静态 import 边** ⇒ 冻结包（打包版）必 ImportError、端点 500，"
        "而 dev 模式永不复现：\n"
        f"  缺失模块 = {unreachable}\n"
        f"  _keep_py（去 .py）= {sorted(keep_py)}\n"
        f"  _keep_dirs       = {sorted(keep_dirs)}\n"
        f"  静态边顶层名      = {sorted(static_edges)}\n"
        f"  dotted app 子模块 = {sorted(dotted_subs)}\n"
        "修法：把缺失项加进 gui/mcnp_sidecar.spec 的 `_keep_py`"
        "（历史先例：material_library.py / gpu_pref.py / diff_inp.py）")


def test_no_keep_py_entry_is_missing_on_disk():
    """反向方向：`_keep_py` 里每一项都要真的存在，否则 spec 悄悄失效（打进去一个不存在的东西）。"""
    app_src = PROJECT_DIR / "app"
    missing = [f for f in _parse_keep_py(SPEC_PATH.read_text(encoding="utf-8"))
               if not (app_src / f).is_file()]
    assert not missing, f"_keep_py 列了不存在的 app 文件（spec 与源码漂移）：{missing}"


def test_keep_dirs_are_real_directories():
    """`_keep_dirs` 里的每个子目录必须真实存在（否则 `_walk_add` 会直接抛错、打包失败）。"""
    app_src = PROJECT_DIR / "app"
    missing = [d for d in _parse_keep_dirs(SPEC_PATH.read_text(encoding="utf-8"))
               if not (app_src / d).is_dir()]
    assert not missing, f"_keep_dirs 列了不存在的 app 子目录：{missing}"


def test_worker_entries_are_in_spec_literals():
    """worker 分派入口必须在 spec 的登记字面量里（否则冻结版 `--meshtal-worker` /
    `--ptrac-worker` 找不到 `meshtal.*` / `ptrac.*` 子模块）。

    注：断言的是"这些字面量出现在 spec 中"（见 `_parse_hidden` 的取舍说明）。
    """
    spec_literals = _parse_hidden(SPEC_PATH.read_text(encoding="utf-8"))
    for mod in ("meshtal", "meshtal._meshtal_worker", "ptrac", "ptrac._ptrac_worker"):
        assert mod in spec_literals, (
            f"{mod} 未出现在 spec 的任何字面量中 —— 冻结版 worker 入口会 ImportError"
            f"（现有 meshtal/ptrac 相关登记："
            f"{[x for x in spec_literals if x.split('.')[0] in ('meshtal', 'ptrac')]}）")


def test_dotted_import_edge_is_not_equivalent_to_dynamic_top_level_name():
    """证据固化（TD-34 / 审计 §C）：**dotted 边 ≠ 顶层名**。

    `app/generator/inp_generator.py:9` 与 `app/generator/parsers/core.py:18` 有
    `from app import lattice`，它注册/收集的是 **dotted 名 `app.lattice`**（构建 TOC 实证：
    `PYZ-00.toc:782` 只有 `app.lattice`）；而 `api_server._import_app("lattice")` 执行的是
    `__import__("lattice")`，取的是**顶层名 `lattice`** —— 二者在 PYZ 里**不是同一条目**。
    ⇒ 「lattice 有静态边所以一定可用」这一推断**不严格**（t4 已持保留），需 runtime 定论
    （一条 `POST /api/lattice-extent`）。

    本用例把该事实钉住：api_server 自身**没有** `from lattice import …` 形态的顶层边，
    lattice 之所以目前能跑，靠的是 `_keep_py` 显式登记（spec:30）+ `sys.path` 里有 app/。
    """
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    keep_py = {f[:-3] for f in _parse_keep_py(spec_text) if f.endswith(".py")}
    # 前提：lattice 目前是"显式登记"而非"靠顶层静态边"（登记被删即本断言变红 → 提醒复核）
    assert "lattice" in keep_py, (
        "lattice 既未显式登记、又无顶层静态边 ⇒ 冻结版 `_import_app(\"lattice\")` 必 ImportError")
    top_level_edges = _static_import_edges()
    dotted_subs = _dotted_imported_submodules()
    # api_server 自身既无顶层 `lattice` 边、也无 `from app import …` dotted 边：
    # 它只通过 `_import_app("lattice")` 动态取，故"可达性"**完全**依赖上面的 `_keep_py` 登记。
    assert "lattice" not in top_level_edges, (
        "api_server 出现了顶层 `lattice` 静态边（from lattice import …）——"
        "那本闸门的结论要更新：此时顶层形态已被覆盖")
    assert "app" not in top_level_edges or "lattice" not in dotted_subs, (
        "api_server 出现了 `from app import lattice` 形态的 dotted 边 —— "
        "注意 dotted 名 `app.lattice` 与 `_import_app(\"lattice\")` 的顶层名不同条目，"
        "该形态**不能**替代 `_keep_py` 登记（见本用例 docstring）")
    # 交叉事实（仅在 app/ 侧）：dotted 引用确实存在，但那属于 PYZ 收集，不改变上面结论
    app_dotted = []
    for rel in ("app/generator/inp_generator.py", "app/generator/parsers/core.py"):
        src = (PROJECT_DIR / rel).read_text(encoding="utf-8")
        if re.search(r"^from app import lattice\b", src, re.M):
            app_dotted.append(rel)
    assert app_dotted, (
        "app/ 侧 `from app import lattice` 边消失了？——该边是 PYZ 收集 `app.lattice` 的来源；"
        "若确有重构，请同步更新本用例与 spec 说明")
