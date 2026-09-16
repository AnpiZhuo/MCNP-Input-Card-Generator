"""
MCNP 生成器 API 服务 — 桥接 React 前端与 Python 后端
使用标准库 http.server，无需安装 Flask

启动: python api_server.py
监听: http://localhost:5001
"""

import contextlib
import json
import math
import os
import re
import sys
import threading
from http.server import ThreadingHTTPServer as HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# 将 app/ 和项目根目录都加入路径
PROJECT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_DIR = os.path.join(PROJECT_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


def _import_app(module, base_dir=APP_DIR):
    """惰性导入 app/（或指定目录）下模块：先确保目录在 sys.path。

    集中替代 handler 内重复的 ``sys.path.insert(0, ...)`` + 惰性 import；
    保持「不模块级 import 后端污染」语义不变——模块级只 import 核心引擎，
    FreeCAD/step 等重量依赖仍延迟到 handler 内首次调用时导入。
    """
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    return __import__(module)


from models import (
    BasicSettings, CellData, CellRow, FmeshDefinition, MaterialData, MaterialRow,
    PTRACSettings, SourceData, TallySettings, TallyDefinition, AdvancedSettings, DeckData
)
# 注意：inp_generator 在模块顶层 import pymcnp（fail-fast 约定，见 tests/test_tech_debt.py F#7），
# 而 pymcnp/__init__ 会连同 matplotlib/pandas/pyvista 等重依赖一起导入（实测 ~2.4s 拖慢后端拉起）。
# 因此 generate_inp_from_deck 改为在 handler 内按需导入（与下方 _generate_materials 等一致），
# 保持「模块级只 import 核心引擎、重量依赖延迟到 handler」的本文件既有约定。
from generator.parsers import parse_inp_text
from xsdir_db import DB as xsdir_db

PORT = 5001

# 快捷建栅元重合检查：新栅元几乎完全在已有栅元内（重合占比超此阈值）→ 推荐已有让位。
RECOMMEND_EXISTING_HOLE_FRAC = 0.98


def _meshtal_worker_cmd() -> list:
    """返回 meshtal worker 的 spawn 命令。

    - frozen：`[sys.executable, "--meshtal-worker"]` —— sidecar exe 入口
      mcnp_bridge.py 分派到 worker main（stdin JSON → stdout JSON），不传脚本路径，
      避免打包版 sys.executable 带参数运行冻结入口再启第二个 5001（端口冲突挂起）。
    - dev：`[sys.executable, mcnp_bridge.py, "--meshtal-worker"]` —— 同一入口分派，
      dev 真实解释器经 mcnp_bridge 走 worker。
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--meshtal-worker"]
    bridge = os.path.join(PROJECT_DIR, "gui", "backend", "mcnp_bridge.py")
    return [sys.executable, bridge, "--meshtal-worker"]


def _ptrac_worker_cmd() -> list:
    """返回 ptrac worker 的 spawn 命令（照 _meshtal_worker_cmd 打包/开发双模式）。

    - frozen：`[sys.executable, "--ptrac-worker"]` —— sidecar exe 入口分派，
      避免带脚本路径再启第二个 5001。
    - dev：`[sys.executable, mcnp_bridge.py, "--ptrac-worker"]` —— 同一入口分派。
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--ptrac-worker"]
    bridge = os.path.join(PROJECT_DIR, "gui", "backend", "mcnp_bridge.py")
    return [sys.executable, bridge, "--ptrac-worker"]


# ── preview-3d deck 指纹缓存（P0a：同 deck 二次打开免 FreeCAD 子进程）──
# 深模块见 app/preview_cache.py：put 把会话 STL 拷进缓存自有目录，clear-stl 删除
# 的是会话目录，缓存拷贝存活 → 关预览窗口后重开同一 deck 仍命中（≤1s）。
#
# 跨启动复用：缓存目录固定存到 D:\MCNP\memory（用户约定，不存在则创建）而非
# tempfile.mkdtemp 临时目录；配合 preview_cache 写盘的 meta.json，进程重启后
# get 仍能从磁盘恢复 → 同一 deck 只算一次（首次 FreeCAD、之后直接命中）。
from preview_cache import PreviewCache

# 用户约定的可复用内容持久目录：D:\MCNP\memory（不存在则创建）。
MEMORY_DIR = r"D:\MCNP\memory"

def _cache_base(sub: str) -> str:
    d = os.path.join(MEMORY_DIR, sub)
    os.makedirs(d, exist_ok=True)
    return d

_PREVIEW_CACHE = PreviewCache(base_dir=_cache_base("preview_cache"))

# 格阵 universe 裁剪 STL 独立缓存（LRU 2）：键含 u/cellNum/pitch/height（extra 并入指纹），
# 防不同裁剪参数脏命中。与 _PREVIEW_CACHE 分离，不互相驱逐。
_PREVIEW_CACHE_LATTICE = PreviewCache(max_entries=2, base_dir=_cache_base("preview_cache_lattice"))

# ── 3D 预览 STL 会话 ──
# 3D 预览生成的 STL 保留在此（不随请求清理），供截面复用（numpy 切平面）。
# 只在关掉 3D 预览窗口 / 主界面清空时调用 _clear_stl_session() 删除。
_STL_SESSION = {"dir": "", "cells": {}}  # cells: {number: {"material", "path"}}

# TD-20（t5）：服务端是 ThreadingHTTPServer（每请求一线程），而 _STL_SESSION 是模块级 dict 且
# 逐请求整体重绑定；preview 路径是"先 _clear_stl_session() 删上一会话目录、再建新会话" ⇒
# 两个并发 preview-3d 会互删对方刚生成的目录。这里给"会话 + 缓存"操作加一把**可重入深度计数锁**
# （不用 RLock 是因为同一请求路径会嵌套进入，且需要在最外层退出时才释放）。
_PREVIEW_LOCK = threading.Lock()
_PREVIEW_LOCK_DEPTH = 0
_PREVIEW_LOCK_OWNER = None


@contextlib.contextmanager
def _preview_lock():
    """请求级重入锁：保护 `_STL_SESSION` 与两处 `PreviewCache` 的组合操作。

    只在"删旧会话 → 建新会话 → 登记缓存"这组不可分割操作外层进入一次即可；
    嵌套进入按线程身份 + 深度计数放行（同线程重入安全，异线程互斥）。
    """
    global _PREVIEW_LOCK_DEPTH, _PREVIEW_LOCK_OWNER
    me = threading.get_ident()
    if _PREVIEW_LOCK_OWNER == me:
        _PREVIEW_LOCK_DEPTH += 1
        try:
            yield
        finally:
            _PREVIEW_LOCK_DEPTH -= 1
        return
    with _PREVIEW_LOCK:
        _PREVIEW_LOCK_OWNER = me
        _PREVIEW_LOCK_DEPTH = 1
        try:
            yield
        finally:
            _PREVIEW_LOCK_DEPTH = 0
            _PREVIEW_LOCK_OWNER = None


def _clear_stl_session() -> None:
    """删除当前 STL 会话目录（关 3D 预览窗口 / 清空时调用）。

    与 preview_cache 联动：会话目录被清时同步驱逐指向它的缓存项，防悬挂。
    命中路径 _STL_SESSION 指向缓存目录时，本调用驱逐该缓存项并删除其目录，
    之后对已删目录的 rmtree 是无害空操作。
    """
    import shutil
    global _STL_SESSION
    d = _STL_SESSION.get("dir")
    if d:
        _PREVIEW_CACHE.evict_dir(d)
    if d and os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    _STL_SESSION = {"dir": "", "cells": {}}


# ===== 共享曲面解析（preview-3d / export-step / cross-section 共用） =====
# 惰性加载 pymcnp.inp：模块级 `import pymcnp.inp` 会连同 pymcnp/__init__ 的
# Plot/Visualize/outp 等重型子模块（matplotlib/pandas/pyvista）一起被导入，
# 实测把后端「拉起」拖慢约 2.2s。改为首次解析 MCNP 曲面文本时才真正 import，
# 启动立刻可用，成本只挪到第一次曲面请求（后台线程预热兜底）。
_SURF_CLASSES = None
_SURF_CLASSES_LOCK = threading.Lock()


def _surf_classes() -> dict:
    """惰性构建 {MCNP 曲面关键字: pymcnp 曲面类}。

    仅在解析 MCNP 曲面文本（preview-3d / export-step / cross-section /
    栅元覆盖检测）时首次调用；之后复用缓存。线程安全：多请求并发首拉时只构建一次。
    """
    global _SURF_CLASSES
    if _SURF_CLASSES is None:
        with _SURF_CLASSES_LOCK:
            if _SURF_CLASSES is None:
                import pymcnp.inp as _pi
                _d = {}
                for _name in dir(_pi):
                    _obj = getattr(_pi, _name)
                    if hasattr(_obj, '_KEYWORD') and hasattr(_obj, 'from_mcnp') and isinstance(_obj, type):
                        _kw = (_obj._KEYWORD or '').upper()
                        if _kw: _d[_kw] = _obj
                _SURF_CLASSES = _d
    return _SURF_CLASSES

def _plane_coeff_to_points(A: float, B: float, C: float, D: float) -> list:
    """平面 Ax+By+Cz=D → 3 个非共线点（pymcnp 的 P 类只支持三点定义）。

    校正三点法向与 (A,B,C) 同向，否则正侧会被翻转导致几何方向错误。
    """
    if abs(A) >= abs(B) and abs(A) >= abs(C):
        pts = [D / A, 0, 0, (D - B) / A, 1, 0, (D - C) / A, 0, 1]
    elif abs(B) >= abs(C):
        pts = [0, D / B, 0, 1, (D - A) / B, 0, 0, (D - C) / B, 1]
    else:
        pts = [0, 0, D / C, 1, 0, (D - A) / C, 0, 1, (D - B) / C]
    # 三点法向 n=(P2-P1)×(P3-P1)，若与 (A,B,C) 反向则交换 P2/P3 翻转
    import numpy as np
    p1, p2, p3 = np.array(pts[0:3]), np.array(pts[3:6]), np.array(pts[6:9])
    nrm = np.cross(p2 - p1, p3 - p1)
    if np.dot(nrm, np.array([A, B, C])) < 0:
        pts[3:6], pts[6:9] = pts[6:9], pts[3:6]
    return pts


def parse_surfaces(text: str) -> list:
    """将 MCNP 曲面文本解析为 pymcnp 表面对象列表（支持 TR 引用号）"""
    import re
    from freecad_preview import (cone_card_missing_sheet,
                                 box_card_missing_vector)  # 可选尾项判定（纯文本）
    surfs = []
    _cls_map = _surf_classes()  # 惰性构建 pymcnp 曲面类表（拖慢启动的重型 import 只在此触发一次）
    for _line in text.strip().splitlines():
        _l = _line.strip()
        if not _l or _l.startswith("C") or _l.startswith("c"): continue
        _l = _l.split("$")[0].strip()  # 去掉行内注释
        if not _l: continue
        # 提取 TR 引用：后缀 *TRn（GEOUNED 常见）或 100* 前缀（transform=曲面号）
        tr_num = None
        m_tr = re.search(r"\s*\*\s*TR\s*(\d+)\s*$", _l, re.IGNORECASE)
        if m_tr:
            tr_num = int(m_tr.group(1))
            _l = _l[:m_tr.start()].rstrip()
        else:
            m_star = re.match(r"^(\d+)\s*\*\s*", _l)
            if m_star:
                tr_num = int(m_star.group(1))
                _l = _l[m_star.end():].lstrip()
        _p = _l.split()
        if len(_p) < 2: continue
        _kw_idx = 1
        if len(_p) > 2 and _cls_map.get(_p[2].upper()): _kw_idx = 2
        _kw = _p[_kw_idx].upper()
        if _kw == "HEX":
            # MCNP 里 HEX 是 RHP 的同义词；pymcnp 没有 Hex 类 → 不改写就会被静默丢弃
            _p[_kw_idx] = "RHP"
            _l = " ".join(_p)
            _kw = "RHP"
        elif _kw in ("CX", "CY", "CZ") and len(_p) - _kw_idx >= 3:
            # MCNP 的轴对齐圆柱缩写有三项式 `CX y z R`（≡ `C/X y z R`，C810 Table 3.1）。
            # pymcnp 的三种类的接受面**各不相同**（2026-09-17 实测）：
            #   C/X·C/Y·C/Z ← 4 项长式；CX·CY ← **什么都不认**；CZ ← **只认 `CZ R` 两项式**
            # 所以：**三项式必须改写成 C/X 长式**（否则 InpError 被下面 except 吞掉 →
            # 曲面静默丢弃、SDEF SUR=/3D/截面/STEP 全受影响）；
            # 而 `CZ R` 两项式**必须原样保留**（改写成 `C/Z R` 反而少 2 个参数 → 同样被丢）。
            _p[_kw_idx] = "C/" + _kw[1]
            _l = " ".join(_p)
            _kw = _p[_kw_idx]
        elif cone_card_missing_sheet(_p, _kw_idx):
            # 双叶锥（省略最后一项 ±1）pymcnp 解析不了 → 补 0 表示双叶
            # （不补就是静默丢曲面：引用它的栅元在预览里全消失）
            _l = _l + " 0"
            _p = _l.split()
        elif box_card_missing_vector(_p, _kw_idx):
            # BOX 省略第三边向量（9 项）= 某维无限 → 补零向量（quadric.box_params 认无限）
            _l = _l + " 0 0 0"
            _p = _l.split()
        _cls = _cls_map.get(_p[_kw_idx].upper())
        if _cls is None: continue
        try:
            _s = _cls.from_mcnp(_l)
            if tr_num is not None:
                _s.transform = tr_num
            surfs.append(_s)
        except Exception:
            # P A B C D 系数形式：pymcnp 的 P 只支持三点定义，转一下再试
            if _p[_kw_idx].upper() == "P" and len(_p) == 6:
                try:
                    pts = _plane_coeff_to_points(float(_p[2]), float(_p[3]), float(_p[4]), float(_p[5]))
                    _l2 = f"{_p[0]} P " + " ".join(str(v) for v in pts)
                    _s = _cls.from_mcnp(_l2)
                    if tr_num is not None:
                        _s.transform = tr_num
                    surfs.append(_s)
                except Exception:
                    pass
    return surfs

def _model_box_from_cells_surfaces(data: dict):
    """由 cells/surfaces 推算模型包围盒（A1.2 匹配检测，请求未带 modelBox 时的契约分支）。

    契约 §4.6A「modelBox（或 surfaces/cells/tr_cards 由 handler 算）」——此前只实现了
    modelBox 直读，前端只发 cells/surfaces → match 恒 null → 不匹配横幅从未触发
    （绝不静默错位失效，2026-08-15 修复）。

    口径 = 可见外壳：只统计**非真空**栅元引用的曲面（与 preview-3d 实际渲染的 shell
    一致；真空外层球 so 1000/2000 不参与，否则模型盒会被撑成世界盒导致漏报）。
    范围 = model_extent_unpadded 的 max-abs（无 padding，保小模型真实范围）。
    """
    import re
    from freecad_preview import _pymcnp_surf_to_dict, model_extent_unpadded
    surfaces_text = str(data.get("surfaces") or "")
    cells = data.get("cells") or []
    if not surfaces_text or not cells:
        return None
    used = set()
    for c in cells:
        if str(c.get("material", "") or "").strip() == "0":
            continue  # 真空栅元不渲染外壳，不参与模型盒
        for tok in re.findall(r"-?\d+", str(c.get("surface_expr", "") or "")):
            used.add(tok.lstrip("-"))
    if not used:
        return None
    surf_dicts = []
    for s in parse_surfaces(surfaces_text):
        num = str(getattr(s, "number", "") or "").lstrip("-")
        if num in used:
            try:
                surf_dicts.append(_pymcnp_surf_to_dict(s))
            except Exception:
                continue
    ext = model_extent_unpadded(surf_dicts) if surf_dicts else 0.0
    if ext <= 0:
        return None
    return {"min": [-ext, -ext, -ext], "max": [ext, ext, ext]}

def parse_tr_cards(text: str) -> dict:
    """解析 TRn 变换卡文本为 {num: {translate, rotate}}"""
    import re
    tr_cards = {}
    for _line in text.strip().splitlines():
        _ls = _line.strip()
        if not _ls: continue
        m = re.match(r'^\*?TR(\d+)', _ls.upper())
        if not m: continue
        try:
            tn = int(m.group(1))
            if str(tn) in tr_cards: continue
            vals = [float(v) for v in _ls.split()[1:]]
            translate = vals[:3] if len(vals) >= 3 else [0, 0, 0]
            rotate = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            if len(vals) >= 9:
                import numpy as np
                rotate = [[vals[3], vals[4], vals[5]], [vals[6], vals[7], vals[8]]]
                if len(vals) >= 12:
                    rotate.append([vals[9], vals[10], vals[11]])
                else:
                    rotate.append(np.cross(rotate[0], rotate[1]).tolist())
            tr_cards[str(tn)] = {"translate": translate, "rotate": rotate}
        except: pass
    return tr_cards




def build_cells_data(cell_list: list, include_void: bool = True,
                     force_include_numbers: set[int] | None = None) -> list:
    """把前端栅元 JSON（CellRow 判别联合或旧平铺格式）解析为 FreeCAD CSG 需要的
    cells_data（跳过 raw 条件行；同一栅元号多定义只取第一个）。

    两遍处理：
      1. 先收集所有栅元（含真空）的 AST，供 #n 栅元补集引用解析；
      2. 再逐个解析 #n → 栅元 n 的完整几何补集，输出 cells_data。

    include_void=True（3D 预览主路径 / 截面 deck 快照）时保留真空栅元（材料 0），
    前端染成透明色；include_void=False（STEP 导出 / 格阵 universe 裁剪 STL）时跳过
    真空栅元，但 #n 解析仍会用到其几何。pymcnp 几何 AST 解析失败时 ast 置 None
    （预览时该栅元不渲染）。

    force_include_numbers（可选）：强制包含的栅元号集合。水密/缝隙检测需要
    「外部栅元」的 BRep 实体（通常是 imp=0 的 graveyard 外围，项14 规则平时
    不渲染），这些栅元默认被跳过 → 用该参数把它们放行（其余跳过规则不变）。

    项14 cell 分类规则（用户已确认，2026-08-24）：
      - fill 装配容器（fill 非空 或 fill_grid 非空，含 fill="0"）→ 跳过自身 STL，
        无论有没有 u、material 是否 0；内容由 FILL 装配（preview-lattice 路径）。
      - graveyard（impN/impP/impE 任一为 0）→ 不渲染（跳过自身 STL）。
      - render:false → 跳过。
      - 其余实体 cell（material≠0）与纯 void cell（material=0，无 fill 无 u）
        → 参与 STL（include_void=True 时）。
    """
    from pymcnp.types.Geometry import Geometry
    from freecad_preview import resolve_cell_complements, parenthesize_unions

    def _imp_is_zero(c):
        """graveyard 判 0：impN/impP/impE（或 deck 侧 imp_n/imp_p/imp_e）任一非空且
        首个 token 为 "0" → 该粒子重要性 0（MCNP 在该 cell 杀粒子）= graveyard，不渲染。
        MCNP imp 单值语义（每 cell 每粒子一个数字），取首个 token 兼容 "0 0" 等续值。
        """
        for key in ("imp_n", "impN", "imp_p", "impP", "imp_e", "impE"):
            v = c.get(key)
            if v is None:
                continue
            s = str(v).strip()
            if s and s.split()[0] == "0":
                return True
        return False

    entries = []  # (number, mat_val, density, ast_node, render, has_fill, has_fill_grid, is_graveyard)
    seen_numbers = set()
    for cell in cell_list:
        if not isinstance(cell, dict):
            continue
        # CellRow 判别联合：raw 跳过；cell 用嵌套 cell
        if cell.get("kind") == "raw":
            continue
        if cell.get("kind") == "cell":
            cell = cell.get("cell") or {}
        expr = str(cell.get("surface_expr", "") or cell.get("surfaces", "")).strip()
        if not expr:
            continue
        number = cell.get("number", 0) or int(cell.get("num", 0) or 0)
        if number in seen_numbers:
            continue  # #ifdef 分支里同一栅元号两个定义，只取第一个
        seen_numbers.add(number)
        raw_mat_raw = cell.get("material") or cell.get("mat") or ""
        raw_mat = str(raw_mat_raw).strip().split()[0] if raw_mat_raw else ""
        mat_val = raw_mat or raw_mat_raw
        # 第一遍捕获 render / fill / fill_grid / graveyard（第二遍 skip 用）
        render = bool(cell.get("render", True))
        has_fill = bool(str(cell.get("fill", "") or "").strip())
        has_fill_grid = bool(cell.get("fill_grid"))
        is_graveyard = _imp_is_zero(cell)
        try:
            ast = Geometry.from_mcnp(parenthesize_unions(expr))
            ast_node = ast.ast
        except Exception:
            ast_node = None
        entries.append((number, mat_val, cell.get("density", ""), ast_node,
                        render, has_fill, has_fill_grid, is_graveyard))

    # #n 栅元补集引用解析：先建 number → ast_node 映射（含真空/不渲染/格阵栅元）
    cells_by_num = {num: node for num, _, _, node, _, _, _, _ in entries}
    cells_data = []
    for (number, mat_val, density, ast_node, render,
         has_fill, has_fill_grid, is_graveyard) in entries:
        # 水密检测等场景强制包含指定栅元（如 graveyard 外部栅元，imp=0 平时不渲染）
        force = (force_include_numbers is not None
                 and number in force_include_numbers)
        if not include_void and str(mat_val).split()[0] == "0" and not force:
            continue  # STEP 导出跳过真空；其几何已在上面的映射里用于 #n 解析
        if not render and not force:
            continue  # render:false → 跳过（死代码修复：此前前端传 render 但被忽略）
        if (has_fill or has_fill_grid) and not force:
            # 项14：fill 装配容器不产自身 STL——单值 fill=U（含 fill="0"）由
            # FILL 装配 /api/preview-lattice 展开；格阵 fill_grid 同。与有没有 u、
            # material 是否 0 无关。此前只 skip fill_grid、漏掉单值 fill → 用户
            # 看到「大紫方块」（fill cell 自身几何被当实体渲染）。
            continue
        if is_graveyard and not force:
            continue  # 项14：graveyard（imp=0 外围）不渲染
        if ast_node is not None:
            ast_node = resolve_cell_complements(ast_node, cells_by_num)
        # 包回 Geometry 对象（下游 _geometry_ast_to_json 用 c["ast"].ast）
        cells_data.append({
            "number": number,
            "material": mat_val,
            "ast": Geometry(ast_node) if ast_node is not None else None,
            "density": density,
        })
    return cells_data


# ===== 格阵 3D 预览助手（/api/preview-lattice） =====
# 与 app/lattice.py 深模块配合：lattice_cell_extent/expand_positions/compose_lattice_tree
# 纯函数在 lattice.py；本文件负责请求解析、pitch/height 覆盖、TRCL 提取、universe 裁剪 STL。

def _cell_u(c: dict) -> str:
    """CellRow dict → universe 号（cell 判别联合嵌套取 cell.u）。"""
    if c.get("kind") == "cell" and isinstance(c.get("cell"), dict):
        c = c.get("cell") or {}
    return str(c.get("u", "") or "")


def _cell_fill(c: dict) -> str:
    """CellRow dict → fill 字段（cell 判别联合嵌套取 cell.fill）。"""
    if c.get("kind") == "cell" and isinstance(c.get("cell"), dict):
        c = c.get("cell") or {}
    return str(c.get("fill", "") or "")


def _cell_fill_grid(c: dict) -> str:
    if c.get("kind") == "cell" and isinstance(c.get("cell"), dict):
        c = c.get("cell") or {}
    return str(c.get("fill_grid", "") or "")


def _cell_bounded_radius(surface_expr: str, surfaces: dict) -> float:
    """栅元实心外边界半径：表面表达式含负引用（有界）时，取所引用 cz/cy/cx/S 圆柱/球
    的最大半径。无界格（如 pin 外围水 `3` 只有正引用）→ 0（由格元盒裁剪，不参与 fit）。
    """
    has_neg = any(t.startswith("-") for t in str(surface_expr or "").split())
    if not has_neg:
        return 0.0
    max_r = 0.0
    for tok in str(surface_expr).split():
        m = re.match(r"^[+-]?(\d+)$", tok)
        if not m:
            continue
        spec = surfaces.get(int(m.group(1)))
        if not spec:
            continue
        k, params = str(spec[0]).upper(), spec[1]
        try:
            if k in ("CZ", "CY", "CX"):
                max_r = max(max_r, float(params[0]))
            elif k == "S" and len(params) >= 4:
                max_r = max(max_r, float(params[3]))
            elif k in ("SX", "SY", "SZ") and params:
                max_r = max(max_r, float(params[-1]))
        except (ValueError, IndexError):
            pass
    return max_r


def _lattice_pin_fit_overlaps(cell_list, surf_text, lattice) -> list:
    """格阵装配后的真实重叠检测（首版）：实心 pin 几何超出格元盒（半径 > pitch/2）
    会与相邻格元相撞。逐格阵、逐非空格位检查其 universe 实心栅元最大半径 vs 半宽。

    返回 [{a, b, volumeFraction, method:"lattice-fit", reason}]。
    """
    surfaces = lattice._parse_surface_cards(surf_text)
    out = []
    for c in cell_list or []:
        if not isinstance(c, dict) or c.get("kind") == "raw":
            continue
        cell = c.get("cell") if c.get("kind") == "cell" and isinstance(c.get("cell"), dict) else c
        if not isinstance(cell, dict):
            continue
        fg = lattice.FillGrid.from_json(cell.get("fill_grid", "") or "")
        if fg is None or fg.kind != "lattice":
            continue
        ext = lattice.lattice_cell_extent(cell.get("surface_expr", ""), cell.get("lat", ""), surf_text)
        if not ext or ext.get("x_min") is None or ext.get("x_max") is None:
            continue
        half_x = (ext["x_max"] - ext["x_min"]) / 2.0
        half_y = ((ext.get("y_max", ext.get("y_min")) - ext.get("y_min", ext.get("x_min"))) / 2.0
                  if ext.get("y_min") is not None else half_x)
        seen_u = set()
        for e in fg.cells:
            u = str(e.u or "")
            if u in ("0", "") or u in seen_u:
                continue
            seen_u.add(u)
            max_r = 0.0
            for ucell in cell_list or []:
                if not isinstance(ucell, dict):
                    continue
                ucc = ucell.get("cell") if ucell.get("kind") == "cell" and isinstance(ucell.get("cell"), dict) else ucell
                if not isinstance(ucc, dict) or str(ucc.get("u", "") or "").strip() != u:
                    continue
                if str(ucc.get("material", "") or "0").strip() == "0":
                    continue
                r = _cell_bounded_radius(ucc.get("surface_expr", ""), surfaces)
                if r:
                    max_r = max(max_r, r)
            if max_r > 0 and (max_r > half_x or max_r > half_y):
                out.append({
                    "a": int(cell.get("number", 0)), "b": f"格阵U{u}",
                    "volumeFraction": 1.0, "method": "lattice-fit",
                    "reason": (f"universe {u} 实心几何半径 {max_r:.3f} 超出格元盒半宽 "
                               f"{min(half_x, half_y):.3f}（pitch 半宽 {half_x:.3f}/{half_y:.3f}），"
                               f"可能与相邻格元相撞"),
                })
    return out


def _cell_u_of(c: dict) -> str:
    """从 CellRow（{kind,cell} 嵌套 或 平铺）取 u；无 → ""。"""
    if not isinstance(c, dict):
        return ""
    cc = c.get("cell") if c.get("kind") == "cell" and isinstance(c.get("cell"), dict) else c
    return str((cc or {}).get("u", "") or "").strip()


def _imp_any_zero(cell: dict) -> bool:
    """graveyard 判 0（模块级，与 build_cells_data._imp_is_zero 口径一致）：imp_n/imp_p/
    imp_e（或 deck 侧 impN/impP/impE）任一非空且首 token 为 "0" → graveyard。

    项15 规则5：handler 构造 sub_by_u 时过滤 imp=0 的 cell（与项14 排除口径一致）。
    """
    for key in ("imp_n", "impN", "imp_p", "impP", "imp_e", "impE"):
        v = cell.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.split()[0] == "0":
            return True
    return False


def _max_surface_num(surf_text: str) -> int:
    """曲面卡文本最大曲面号（格元盒 RPP clip 曲面编号顺延起点）。"""
    import re
    m = 0
    for line in str(surf_text).splitlines():
        mm = re.match(r'^\s*(\d+)', line)
        if mm:
            m = max(m, int(mm.group(1)))
    return m


def _clip_suffix_and_lines(box: dict, max_surf: int):
    """格元盒 → (RPP 曲面卡行, 盒内半空间表达式后缀)。

    盒 [x_min,x_max]×[y_min,y_max]×[z_min,z_max] 用**一个 RPP 宏体**表达裁剪：
    后缀 `-<num>`（RPP 负侧 = 盒内实体），worker 里对 cell solid ∩ RPP 盒实体做
    solid-solid common。**禁止再合成 6 个 PX/PY/PZ 平面**——FreeCAD/OCC 对
    「圆柱（C/CZ 半空间）∩ 平行于其轴的平面」的布尔 common 恒返回空
    （QA 复现：圆柱+2×PZ 正常 / +2×PX 空 / +6×盒平面空）。RPP 盒实体是闭盒，
    与圆柱做 solid-solid common 正常（与 preview-3d 的 bound 盒裁剪同机制）。
    """
    b = dict(box)
    for ax in "xyz":
        lo, hi = b.get(ax + "_min"), b.get(ax + "_max")
        if lo is None or hi is None:
            b[ax + "_min"], b[ax + "_max"] = -0.5, 0.5
        elif hi - lo < 1e-9:  # 退化盒防御：扩到单位跨度，避免零厚度 RPP
            mid = (float(lo) + float(hi)) / 2.0
            b[ax + "_min"], b[ax + "_max"] = mid - 0.5, mid + 0.5
    num = max_surf + 1
    suffix = f"-{num}"
    lines = (
        f"{num} rpp {b['x_min']:.6g} {b['x_max']:.6g} "
        f"{b['y_min']:.6g} {b['y_max']:.6g} "
        f"{b['z_min']:.6g} {b['z_max']:.6g}"
    )
    return lines, suffix


def _stl_triangle_count(raw: bytes) -> int:
    """STL 字节 → 三角形数（ASCII 'facet' 计数 / 二进制头 offset80 uint32）。

    0 三角形 = 空 STL（FreeCAD 二进制空文件恰 84 字节：80 头 + count=0），
    由 _build_one_universe 显式丢弃，不静默产出。
    """
    if not raw:
        return 0
    if b"facet" in raw:  # ASCII STL：facet 行即三角形
        return raw.count(b"facet")
    if len(raw) >= 84:   # 二进制 STL：offset 80 处 uint32 三角形数
        import struct
        return struct.unpack("<I", raw[80:84])[0]
    return 0


def _stl_recenter_z(raw: bytes) -> bytes:
    """把二进制 STL 整体沿 z 平移，使包围盒 z 中心 = 0（与 compose「叶位置 = 格阵中心」约定一致）。

    _build_one_universe 的格元盒/容器裁剪产生 z∈[zmin,zmax] 的**底锚** STL（如 BEAVRS 全堆芯
    高度 460 → z∈[0,460]，中心在 230）。但前端把几何原点放在叶位置 z（=格阵中心，如 230）→
    底锚 STL 放上去整体上移 height/2（"位置不对/燃料棒与板子浮空"根因）。这里在 STL 层把 z
    居中（每顶点 z -= bbox_z_center），使几何关于 universe 原点对称，与 buildDiscGeometry
    程序化柱（居中）及色块总览（居中 box）的约定一致。
    仅平移 z，不动 x/y（围板等格位几何本就在格元盒内按设计偏移，不能居中）。
    返回新字节；非二进制/解析失败 → 原样返回（安全降级，不加重问题）。
    """
    if not raw or b"facet" in raw:  # 空或 ASCII STL：跳过（ASCII 由跨语言消费少，不影响本项目）
        return raw
    try:
        tris = _import_app("stl_cross_section").parse_binary_stl(raw)
    except Exception:
        return raw
    if tris.size == 0:
        return raw
    zs = tris[..., 2]
    zc = float((float(zs.min()) + float(zs.max())) / 2.0)
    if abs(zc) < 1e-9:
        return raw
    import struct
    n = struct.unpack("<I", raw[80:84])[0]
    out = bytearray(raw[:84])  # 头部 + 三角形数原样
    off = 84
    for i in range(n):
        if off + 50 > len(raw):
            break
        out += raw[off:off + 12]       # 法向原样保留
        tri = tris[i]
        for v in tri:
            out += struct.pack("<fff", float(v[0]), float(v[1]), float(v[2]) - zc)
        out += raw[off + 48:off + 50]  # 属性字节
        off += 50
    return bytes(out)


def _cell_trcl_deg(trcl_field, tr_cards) -> float:
    """trcl 字段（"1"/"TR1"/"*TR1"/""）→ 绕 Z 旋转角（度）。

    只取绕 Z 分量：TR 卡旋转矩阵首行 = 局部 X 轴方向余弦 (cosθ, sinθ, 0)。
    翻译部分忽略（格阵假设居中）。
    """
    if not trcl_field:
        return 0.0
    s = str(trcl_field).strip().lstrip("*").lstrip("Tt").lstrip("Rr")
    if not s or not s.isdigit():
        return 0.0
    card = tr_cards.get(s)
    if not card:
        return 0.0
    rot = card.get("rotate")
    if not rot:
        return 0.0
    try:
        a = float(rot[0][0])
        b = float(rot[0][1])
        return math.degrees(math.atan2(b, a))
    except (TypeError, ValueError, IndexError):
        return 0.0


def _scan_lattice_z(surf_text: str, info: dict, sub_by_u: dict, lattice,
                    _seen: set | None = None, surfaces: dict | None = None) -> tuple:
    """扫描格阵引用的 universe 栅元 PZ 约束 → (z_lower, z_upper)；无 → (None, None)。

    递归进嵌套格阵（全堆芯：根→组件格阵→针 PZ）；并集取全针高度。

    TD-19（t8）：`surfaces` = `lattice._parse_surface_cards(surf_text)` 的**预解析结果**，
    沿递归透传给 `_cell_pz_bounds`。原先每个 cell 都走一次全量 `_parse_surface_cards`
    （正则扫整段曲面卡文本），BEAVRS 量级（数百 universe × 数十 cell）下是确定性叠加延迟；
    `_cell_pz_bounds` 早已为该优化预留 `surfaces` 形参（其 docstring 自述该用途）。
    不传时（外部调用方）保持旧行为：内部自行解析一次并复用。
    """
    if surfaces is None:
        surfaces = lattice._parse_surface_cards(surf_text)
    fg = info.get("fill_grid")
    if fg is None:
        return None, None
    lo, hi = None, None
    seen = set(_seen) if _seen else set()
    for e in fg.cells:
        u = str(e.u or "")
        if u in ("0", "") or u in seen:
            continue
        seen.add(u)
        if _universe_has_lattice(sub_by_u, u):
            # 嵌套格阵：取该 universe 的格阵 fill_grid 递归扫描
            sub_fg = next((c.get("fill_grid") for c in sub_by_u.get(u, [])
                           if c.get("fill_grid") is not None), None)
            if sub_fg is not None:
                clo, chi = _scan_lattice_z(surf_text, {"fill_grid": sub_fg},
                                           sub_by_u, lattice, seen, surfaces)
            else:
                clo, chi = None, None
        else:
            clo, chi = None, None
            for cell in sub_by_u.get(u, []):
                # TD-19（t8）：透传预解析 surfaces（原来未传 → 每 cell 全量解析一次）
                c_lo, c_hi = lattice._cell_pz_bounds(
                    cell.get("surface_expr", ""), surf_text, surfaces)
                # 并集：lo=所有栅元最低 z，hi=最高 z
                if c_lo is not None:
                    clo = c_lo if clo is None else min(clo, c_lo)
                if c_hi is not None:
                    chi = c_hi if chi is None else max(chi, c_hi)
        if clo is not None:
            lo = clo if lo is None else min(lo, clo)
        if chi is not None:
            hi = chi if hi is None else max(hi, chi)
    return lo, hi


def _scan_embedding_z(cell_list, surf_text, lattice_u, lattice):
    """扫描引用该格阵 universe 的嵌入 cell（单值 fill == lattice_u）的 z 跨度。

    2D 格阵（格阵 cell 与 universe 栅元均无 PZ 约束）的 pin 高度由嵌入窗口 cell
    决定——如 owen 17×17：cell 30 `fill=10` RPP z=±182.88，pin 应长 365.76 而非
    默认裁剪成扁平片。→ (zlo, zhi)；无 → (None, None)。
    """
    if not lattice_u:
        return None, None
    lu = str(lattice_u)
    lo, hi = None, None
    for c in cell_list or []:
        if not isinstance(c, dict):
            continue
        cc = c.get("cell") if c.get("kind") == "cell" else c
        if not isinstance(cc, dict):
            continue
        fill = str(cc.get("fill", "") or "").strip()
        if fill != lu:
            continue
        ext = lattice.lattice_cell_extent(cc.get("surface_expr", ""), "1", surf_text)
        if ext:
            zlo, zhi = ext.get("z_min"), ext.get("z_max")
            if zlo is not None and zhi is not None:
                if lo is None or zlo < lo:
                    lo = zlo
                if hi is None or zhi > hi:
                    hi = zhi
    return lo, hi


def _resolved_extent(raw_extent, lat, req_pitch, req_height,
                     surf_text, info, sub_by_u, lattice, cell_list=None) -> dict:
    """格阵 cell 范围 → 解析后 extent（pitch/height 覆盖 + 缺省填充）。

    pitch 覆盖次序：请求 > extent/dims > 默认 1；
    z 高度覆盖次序：请求 > 格阵 cell PZ（extent 已含）> universe 栅元 PZ 扫描 > 默认 1。
    """
    ext = {}
    for ax in "xyz":
        lo = None if raw_extent is None else raw_extent.get(ax + "_min")
        hi = None if raw_extent is None else raw_extent.get(ax + "_max")
        ext[ax + "_min"] = lo
        ext[ax + "_max"] = hi
    lat = str(lat or "1")
    # pitch 覆盖（x/y）
    if req_pitch is not None and str(req_pitch).strip():
        p = float(req_pitch)
        if lat == "2":
            # hex：pitch=中心距；x 跨度=2R=2p/√3，y 跨度=p
            hx = p * 2.0 / math.sqrt(3.0) / 2.0
            ext["x_min"], ext["x_max"] = -hx, hx
            ext["y_min"], ext["y_max"] = -p / 2.0, p / 2.0
        else:
            ext["x_min"], ext["x_max"] = -p / 2.0, p / 2.0
            ext["y_min"], ext["y_max"] = -p / 2.0, p / 2.0
    # z 高度覆盖
    if req_height is not None and str(req_height).strip():
        h = float(req_height)
        ext["z_min"], ext["z_max"] = -h / 2.0, h / 2.0
    else:
        zlo, zhi = ext.get("z_min"), ext.get("z_max")
        if zlo is None or zhi is None:
            slo, shi = _scan_lattice_z(surf_text, info, sub_by_u, lattice)
            if slo is not None and shi is not None:
                ext["z_min"], ext["z_max"] = slo, shi
        if ext.get("z_min") is None or ext.get("z_max") is None:
            # 嵌入窗口 cell（fill == 格阵 universe）的 z 跨度兜底（2D 格阵 pin 高度）
            elo, ehi = _scan_embedding_z(cell_list or [], surf_text,
                                         info.get("u"), lattice)
            if elo is not None and ehi is not None:
                ext["z_min"], ext["z_max"] = elo, ehi
        if ext.get("z_min") is None or ext.get("z_max") is None:
            ext["z_min"], ext["z_max"] = -0.5, 0.5
    return ext


def _clip_box_from_extent(extent: dict | None) -> dict:
    """解析后 extent → 裁剪盒 {x_min..z_max}（缺省用默认 1 跨度）。"""
    box = {}
    for ax in "xyz":
        lo = None if extent is None else extent.get(ax + "_min")
        hi = None if extent is None else extent.get(ax + "_max")
        if lo is None or hi is None:
            box[ax + "_min"], box[ax + "_max"] = -0.5, 0.5
        else:
            box[ax + "_min"], box[ax + "_max"] = float(lo), float(hi)
    return box


def _parse_outer_bound(surface_expr: str, surf_text: str, lattice) -> dict | None:
    """解析最外层容器 cell 的几何边界（供色块总览裁剪超壳格位）。

    支持：CZ 圆柱（径向 ≤ r，轴心 0,0）→ {"shape":"cylinder","r","cx","cy"}；
    6 平面盒 PX/PY/PZ → {"shape":"box","x","y","z"}；无法解析 → None。
    """
    if not surface_expr:
        return None
    try:
        surfaces = lattice._parse_surface_cards(surf_text)
    except Exception:
        surfaces = {}
    px: list[float] = []
    py: list[float] = []
    pz: list[float] = []
    cz_r: float | None = None
    for tok in surface_expr.split():
        if not lattice._INT_RE.match(tok):
            continue
        n = int(tok)
        kw, params = surfaces.get(abs(n), (None, []))
        if not params:
            continue
        try:
            v = float(params[0])
        except (TypeError, ValueError):
            continue
        if kw == "CZ" and v > 0:
            cz_r = v
        elif kw == "PX":
            px.append(v)
        elif kw == "PY":
            py.append(v)
        elif kw == "PZ":
            pz.append(v)
    if cz_r is not None:
        return {"shape": "cylinder", "r": cz_r, "cx": 0.0, "cy": 0.0}
    if px and py:
        return {"shape": "box", "x": sorted(px), "y": sorted(py),
                "z": sorted(pz) if pz else None}
    return None


def _lattice_outer_bound(cell_list, outer_u: str, surf_text: str, lattice) -> dict | None:
    """找 fill 指向 outer_u 的最外层容器 cell（无 u 无 lat 的空 cell），解析其边界。"""
    if not outer_u:
        return None
    for c in cell_list:
        if not isinstance(c, dict) or c.get("kind") == "raw":
            continue
        cell = c.get("cell") if c.get("kind") == "cell" and isinstance(c.get("cell"), dict) else c
        if str(cell.get("u", "") or "") != "":
            continue  # 容器 cell 无 u
        if cell.get("lat"):
            continue  # 容器 cell 无 lat
        if str(cell.get("fill", "") or "").strip() != str(outer_u):
            continue
        expr = str(cell.get("surface_expr", "") or "").strip()
        return _parse_outer_bound(expr, surf_text, lattice) if expr else None
    return None


def _lattice_container_expr(cell_list, outer_u) -> str:
    """找 fill 指向 outer_u 的最外层容器 cell（无 u 无 lat 的空 cell）的 surface_expr。

    容器 cell 几何（如 BEAVRS cell343 `-80 700 -730` = cz 187.96 内 + z∈[0,460]）用于
    方法级 STL 裁剪：STL = universe ∩ 格元盒 ∩ 容器cell。格元与容器 cell 无交集的格位
    （角位 u=30 无限水 `-3:3`）∩ 容器 cell → 空，不产生"圆柱外虚假水块"（此前的 bug：
    把无限 cell 只按格元盒裁剪成有限块，格元盒在圆柱外时该块完全在 cell 343 之外）。
    """
    if not outer_u:
        return ""
    for c in cell_list or []:
        if not isinstance(c, dict) or c.get("kind") == "raw":
            continue
        cell = c.get("cell") if c.get("kind") == "cell" and isinstance(c.get("cell"), dict) else c
        if str(cell.get("u", "") or "") != "":
            continue
        if cell.get("lat"):
            continue
        if str(cell.get("fill", "") or "").strip() != str(outer_u):
            continue
        expr = str(cell.get("surface_expr", "") or "").strip()
        # MCNP cell 补集运算符 `#n`（如 cell20 `10 -16 18 -23 -36 -37 38 39 #15 #16 #17 #18`
        # 挖控制叶片）不是曲面号。`_build_one_universe` 把 container_expr 当作布尔裁剪表达式
        # 追加进 universe pin cell（格元盒后缀 + 容器 cell），FreeCAD 解析不了 `#` → 整次
        # build 失败、所有 universe STL 变空（前端回退方块占位）。容器裁剪只关心容器 cell 的
        # 外边界曲面（`10 -16 18 -23 -36 -37 38 39`），`#` 补集应剥离。
        expr = " ".join(tok for tok in expr.split() if not tok.startswith("#"))
        return expr
    return ""


def _lattice_container_bound(surface_expr: str, surf_text: str, lattice) -> dict | None:
    """解析最外层容器 cell 的几何边界（供 fill 展开判断格元是否在容器内）。

    方法级：格阵里的每个格元（格位中心 ± 格元盒半径）与容器 cell 几何相交，才属于
    容器 cell（如 BEAVRS cell343 圆柱内 z∈[0,460]）。格元盒完全在容器 cell 之外的
    （角位 u=30 无限水）不产实体——这是"查容器 cell 几何"而非"反推超壳结果"，
    换任何外壳皆正确。
    返回 {shape:"cylinder", cx,cy,r,zmin,zmax} 或 {shape:"box", x,y,z}；不可解析 → None。
    """
    if not surface_expr:
        return None
    try:
        surfaces = lattice._parse_surface_cards(surf_text)
    except Exception:
        surfaces = {}
    px = []
    py = []
    pz = []
    cz_r = None
    for tok in surface_expr.split():
        if not lattice._INT_RE.match(tok):
            continue
        n = int(tok)
        kw, params = surfaces.get(abs(n), (None, []))
        if not params:
            continue
        try:
            v = float(params[0])
        except (TypeError, ValueError):
            continue
        if kw == "CZ" and v > 0:
            cz_r = v
        elif kw == "PX":
            px.append(v)
        elif kw == "PY":
            py.append(v)
        elif kw == "PZ":
            pz.append(v)
    if cz_r is not None:
        zlo = min(pz) if pz else None
        zhi = max(pz) if pz else None
        return {"shape": "cylinder", "cx": 0.0, "cy": 0.0, "r": cz_r,
                "zmin": zlo, "zmax": zhi}
    if px and py:
        return {"shape": "box", "x": [min(px), max(px)], "y": [min(py), max(py)],
                "z": [min(pz), max(pz)] if pz else None}
    return None


def _universe_has_lattice(sub_by_u: dict, u: str) -> bool:
    """universe u 是否含格阵 cell（是 → 嵌套子格阵，不由外层直接产 STL）。"""
    for cell in sub_by_u.get(str(u), []):
        fg = cell.get("fill_grid")
        if fg is not None and fg.kind == "lattice":
            return True
    return False


def _stls_base64(cells: dict) -> dict:
    """缓存/会话 cells {num: {path}} → {num: base64}。"""
    import base64
    out = {}
    for num, info in cells.items():
        p = info.get("path")
        if p and os.path.isfile(p):
            try:
                with open(p, "rb") as f:
                    out[str(num)] = base64.b64encode(f.read()).decode()
            except OSError:
                continue
    return out


def _build_one_universe(surf_text, tr_text, cell_list, u, box,
                        cell_num, pitch, height, lattice,
                        container_expr: str = "") -> dict:
    """把 universe u 的实体栅元裁剪到格元盒 → FreeCAD STL（{cellNum: base64}）。

    格元盒用**一个 RPP 宏体**（`-<num>` 盒内半空间）追加进 universe 栅元
    surface_expr，worker 内做 cell solid ∩ RPP 盒实体 的 solid-solid common
    （闭盒实体 ∩ 圆柱正常；「圆柱 ∩ 平行轴平面」FreeCAD/OCC 恒空，QA 复现）。
    **方法级裁剪**：再把容器 cell 343 的几何约束（container_expr，如 `-80 700 -730`
    = cz 187.96 内 + z∈[0,460]）追加 —— STL = universe ∩ 格元盒 ∩ 容器 cell。
    这样格元与容器 cell 无交集的格位（角位 u=30 无限水 `-3:3`，格元盒在圆柱外）∩
    容器 cell = 空，不产生"圆柱外虚假水块"。换任何外壳皆正确（查容器 cell 几何，
    非反推超壳结果）。
    空 STL（0 三角形）显式丢弃不产出——前端对缺失 (u,cellNum) 回退占位盒
    （显式降级，不静默给 84B 空 STL）。按 u/cellNum/pitch/height 指纹缓存。
    """
    # 1. 收集 universe u 的实体栅元（跳过格阵 cell + 单值 fill cell）
    #    项14/15：单值 fill cell（含 fill="0"）= 装配容器，不产自身 STL（规则1/7）；
    #    fill_grid 格阵 cell 同（由嵌套展开负责）。universe 叶 void 格元保留
    #    （include_void=True，规则4 → 透明占位 STL）。
    uni_cells = []
    for c in cell_list:
        if not isinstance(c, dict) or c.get("kind") == "raw":
            continue
        cell = c.get("cell") if c.get("kind") == "cell" and isinstance(c.get("cell"), dict) else c
        if _cell_u(c) != str(u):
            continue
        if _cell_fill(c):
            continue
        if _cell_fill_grid(c):
            continue
        expr = str(cell.get("surface_expr", "") or "").strip()
        if expr:
            uni_cells.append(cell)
    if not uni_cells:
        return {}
    # 2. 合成格元盒 RPP 曲面卡 + 盒内半空间后缀（solid-solid 盒裁剪）
    max_surf = _max_surface_num(surf_text)
    clip_lines, suffix = _clip_suffix_and_lines(box, max_surf)
    new_surf_text = (str(surf_text).rstrip() + "\n" + clip_lines) if str(surf_text).strip() else clip_lines
    mod_cells = []
    for cell in uni_cells:
        m = dict(cell)
        expr = str(cell.get("surface_expr", "") or "").strip()
        # 格元盒（suffix）+ 容器 cell 343 几何（container_expr）裁剪：
        # universe ∩ 格元盒 ∩ 容器cell —— 格元完全在容器外的（角位无限水）交集为空不产出。
        clip = suffix + ((" " + container_expr.strip()) if container_expr.strip() else "")
        m["surface_expr"] = (expr + " " + clip).strip()
        mod_cells.append(m)
    # 3. 指纹缓存（extra 含 pitch/height 防脏命中）
    fp = _PREVIEW_CACHE_LATTICE.fingerprint(
        new_surf_text, mod_cells, tr_text,
        extra={"u": str(u), "cellNum": cell_num,
               "pitch": list(pitch), "height": height})
    cached = _PREVIEW_CACHE_LATTICE.get(fp)
    if cached is not None:
        return _stls_base64(cached["cells"])
    # 4. FreeCAD 构建
    StepImporter = _import_app("step_importer").StepImporter
    freecad_bin = StepImporter.detect_freecad()
    if not freecad_bin:
        return {}
    import tempfile, base64
    surfs = parse_surfaces(new_surf_text)
    tr_cards = parse_tr_cards(tr_text)
    # 格阵 universe 裁剪 STL（_build_one_universe，/api/preview-lattice 内部用）：
    # 项14/15（2026-08-24）：include_void=True——universe 叶 void 格元（material=0
    # 无 fill 无 u）也产透明占位 STL（规则4，前端透明材质渲染）。STEP 导出保持
    # include_void=False（void 无实体可导出，语义正确）。
    cells_data = [cd for cd in build_cells_data(mod_cells, include_void=True)
                  if cd.get("ast") is not None]
    if not surfs or not cells_data:
        return {}
    from freecad_preview import FreeCADEngine
    engine = FreeCADEngine(freecad_bin)
    try:
        result = engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl")
        session_dir = tempfile.mkdtemp(prefix="mcnp_lat_stl_")
        session_cells = {}
        stl_data = {}
        for cd in cells_data:
            num = cd.get("number")
            if num not in result or not os.path.isfile(result[num]):
                continue
            try:
                with open(result[num], "rb") as f:
                    raw = f.read()
                if _stl_triangle_count(raw) == 0:
                    continue  # 空 STL 显式降级：不产出（前端回退占位盒）
                raw = _stl_recenter_z(raw)  # z 居中：前端叶位置=格阵中心约定（修"位置不对/浮空"）
                dst = os.path.join(session_dir, f"cell_{num}.stl")
                with open(dst, "wb") as f:
                    f.write(raw)  # 直接落盘已读字节，避免二次读
                stl_data[str(num)] = base64.b64encode(raw).decode()
            except OSError:
                continue
            session_cells[num] = {"material": cd.get("material", "0"), "path": dst}
        if stl_data:
            _PREVIEW_CACHE_LATTICE.put(
                fp, {"dir": session_dir, "cells": session_cells, "freecad": freecad_bin})
        return stl_data
    finally:
        engine.cleanup()


def _find_lattice_cell_info_by_num(num, lattice_infos, sub_by_u) -> dict:
    for info in lattice_infos:
        if info.get("cellNum") == num:
            return info
    for _u, cells in sub_by_u.items():
        for info in cells:
            if info.get("cellNum") == num:
                return info
    return {}


def _deck_snapshot(surfs, cells_data, tr_cards) -> dict:
    """把预览请求解析出的曲面/栅元/TR 序列化为截面解析切片可用的 deck 快照。

    surfaces: [{number,type,params,transform}]（_pymcnp_surf_to_dict）
    cells:    [{number,material,ast}]（ast 为 _geometry_ast_to_json JSON 列表）
    tr_cards: parse_tr_cards 产出 dict
    """
    from freecad_preview import _pymcnp_surf_to_dict, _geometry_ast_to_json, ast_has_facet
    cells = []
    for c in cells_data:
        ast = None
        if c.get("ast") is not None:
            try:
                ast = _geometry_ast_to_json(c["ast"].ast)
            except Exception:
                ast = None
            if ast is not None and ast_has_facet(ast):
                ast = None   # facet 引用无几何求值支持 → 下游按"不可解析"逐栅元降级
        cells.append({
            "number": c.get("number"),
            "material": c.get("material", "0"),
            "ast": ast,
        })
    return {
        "surfaces": [_pymcnp_surf_to_dict(s) for s in surfs],
        "cells": cells,
        "tr_cards": tr_cards,
    }


# ===== JSON → Dataclass 转换 =====

def _find_mcnp_exe() -> str:
    """查找 MCNP 可执行文件，返回第一个找到的完整路径（未找到返回空串）"""
    try:
        import os, winreg
        found = []; seen = set()
        def _add(p):
            if p and p not in seen: seen.add(p); found.append(p)
        # System PATH from registry
        system_paths = set()
        try:
            h = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
            system_paths.update(winreg.QueryValueEx(h, "Path")[0].split(";"))
            winreg.CloseKey(h)
            try:
                h = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
                up = winreg.QueryValueEx(h, "Path")[0]
                if up: system_paths.update(up.split(";"))
                winreg.CloseKey(h)
            except: pass
        except: pass
        # Search all PATH dirs
        all_paths = set()
        for p in os.environ.get("PATH","").split(os.pathsep):
            all_paths.add(p.strip().strip('"'))
        all_paths.update(p.strip().strip('"') for p in system_paths if p.strip())
        for d in all_paths:
            if not d or not os.path.isdir(d): continue
            for f in os.listdir(d):
                if f.lower() in ("mcnp6.exe","mcnp5.exe","mcnp6","mcnp5"): _add(os.path.join(d, f))
        # Registry
        try:
            for key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for subkey in [r"SOFTWARE\MCNP", r"SOFTWARE\Wow6432Node\MCNP"]:
                    try:
                        h = winreg.OpenKey(key, subkey)
                        pv = winreg.QueryValueEx(h, "InstallPath")[0]
                        for r, dd, ff in os.walk(pv):
                            for fn in ff:
                                if fn.lower() in ("mcnp6.exe","mcnp5.exe"): _add(os.path.join(r, fn))
                        winreg.CloseKey(h)
                    except: pass
        except: pass
        # Recursive search
        for base in ["D:/MCNP", "C:/Program Files/MCNP", "C:/MCNP"]:
            if base and os.path.isdir(base):
                for r, dd, ff in os.walk(base):
                    for fn in ff:
                        if fn.lower() in ("mcnp6.exe","mcnp5.exe","mcnp6","mcnp5"): _add(os.path.join(r, fn))
        return found[0] if found else ""
    except Exception:
        return ""


def _open_in_explorer(path: str) -> None:
    """在文件资源管理器中打开目录（Windows）。失败静默，不打断主流程。"""
    try:
        if not path:
            return
        os.makedirs(path, exist_ok=True)
        if os.path.isdir(path):
            os.startfile(path)  # type: ignore[attr-defined]
    except Exception:
        pass


def _basic_from_dict(d: dict) -> BasicSettings:
    return BasicSettings(
        title=d.get("title", ""), mode_n=d.get("mode_n", False), mode_p=d.get("mode_p", False),
        mode_e=d.get("mode_e", False), mode_h=d.get("mode_h", False), mode_he=d.get("mode_he", False),
        mode_d=d.get("mode_d", False), mode_t=d.get("mode_t", False), mode_a=d.get("mode_a", False),
        nps=d.get("nps", ""), ctme=d.get("ctme", ""), act=d.get("act", ""),
        print_pr=d.get("print_pr", ""), phys_fis=d.get("phys_fis", True),
    )

def _cells_from_list(arr: list) -> list[CellRow]:
    """前端 cells（CellRow 判别联合）→ 后端 CellRow[]。

    CellRow 的字段嵌在 c["cell"] 里（判别联合）；旧平铺格式字段在顶层。
    """
    out = []
    for c in arr:
        if not isinstance(c, dict):
            continue
        if c.get("kind") == "raw":
            out.append(CellRow(kind="raw", text=c.get("text", "")))
            continue
        cell_dict = c.get("cell") if isinstance(c.get("cell"), dict) else c
        out.append(CellRow(kind="cell", cell=CellData(
            number=cell_dict.get("number", 0), material=cell_dict.get("material", "0"), density=cell_dict.get("density", ""),
            surface_expr=cell_dict.get("surface_expr", ""), imp_n=cell_dict.get("imp_n", ""), imp_p=cell_dict.get("imp_p", ""),
            imp_e=cell_dict.get("imp_e", ""), vol=cell_dict.get("vol", ""), pwt=cell_dict.get("pwt", ""), ext=cell_dict.get("ext", ""),
            fcl=cell_dict.get("fcl", ""), u=cell_dict.get("u", ""), fill=cell_dict.get("fill", ""), lat=cell_dict.get("lat", ""),
            trcl=cell_dict.get("trcl", ""), tmp=cell_dict.get("tmp", ""), other_params=cell_dict.get("other_params", ""),
            render=cell_dict.get("render", True), comment=cell_dict.get("comment", ""),
            fill_grid=cell_dict.get("fill_grid", ""),
        )))
    return out

def _materials_from_list(arr: list) -> list[MaterialData]:
    # 前端 deck 统一用 nuclides，导入路径会额外带 rows（api_server 405-407 映射）。
    # 这里兼容两者：rows 优先，nuclides 兜底；行按 kind 判别（nuclide | raw）。
    def _row(r: dict) -> MaterialRow:
        if isinstance(r, dict) and r.get("kind") == "raw":
            return MaterialRow(kind="raw", text=r.get("text", ""))
        return MaterialRow(kind="nuclide", zaid=r.get("zaid", ""), fraction=r.get("fraction", ""))
    return [MaterialData(
        number=m.get("number", 0),
        rows=[_row(r) for r in (m.get("rows") or m.get("nuclides") or [])],
        comment=m.get("comment", ""), options=m.get("options", ""), mt_card=m.get("mt_card", ""),
        formula=m.get("formula", ""),
    ) for m in arr]

def _sources_from_list(arr: list) -> list[SourceData]:
    return [SourceData(
        number=s.get("number", 0), par=s.get("par", ""), erg=s.get("erg", ""),
        pos_x=s.get("pos_x", ""), pos_y=s.get("pos_y", ""), pos_z=s.get("pos_z", ""),
        wgt=s.get("wgt", ""), cel=s.get("cel", ""), dir_=s.get("dir_", ""),
        probability=s.get("prob", ""), tme=s.get("tme", ""), vec=s.get("vec", ""),
        axs=s.get("axs", ""), rad=s.get("rad", ""), ext=s.get("ext", ""),
        sur=s.get("sur", ""), nrm=s.get("nrm", ""), tr=s.get("tr", ""),
        ccc=s.get("ccc", ""), ara=s.get("ara", ""), rate=s.get("rate", ""),
        sdef_extra=s.get("sdef_extra", ""),
    ) for s in arr]

def _fmesh_from_list(arr: list) -> list[FmeshDefinition]:
    """前端 fmesh_defs 列表 → FmeshDefinition（缺 key 容忍，照 FM multiplier 先例）。"""
    return [FmeshDefinition(
        number=f.get("number", 0), kind=f.get("kind", "FMESH"),
        fn_prefix=f.get("fn_prefix", ""),
        particle=f.get("particle", ""), geom=f.get("geom", "xyz"),
        origin=f.get("origin", ""), imesh=f.get("imesh", ""), iints=f.get("iints", ""),
        jmesh=f.get("jmesh", ""), jints=f.get("jints", ""), kmesh=f.get("kmesh", ""),
        kints=f.get("kints", ""), emesh=f.get("emesh", ""),
        emints=f.get("emints", f.get("eints", "")),
        tmesh=f.get("tmesh", ""),
        tmints=f.get("tmints", f.get("t_ints", "")),
        mat=f.get("mat", ""), out=f.get("out", ""),
        factor=f.get("factor", ""),
        axs=f.get("axs", ""), vec=f.get("vec", ""), tr=f.get("tr", ""),
        raw=f.get("raw", ""),
    ) for f in arr]

def _ptrac_from_dict(d) -> PTRACSettings | None:
    """前端 tally.ptrac 对象 → PTRACSettings（缺 key 容忍；无/空 → None）。"""
    if not isinstance(d, dict):
        return None
    types = d.get("types") or d.get("type") or []
    if isinstance(types, str):
        types = [p.strip().upper() for p in types.replace(",", " ").split() if p.strip()]
    else:
        types = [str(p).strip().upper() for p in types if str(p).strip()]
    return PTRACSettings(
        enabled=bool(d.get("enabled", False)),
        file=str(d.get("file", "ASC") or "ASC"),
        write=str(d.get("write", "ALL") or "ALL"),
        max=str(d.get("max", "") or ""),
        types=types,
        nps=str(d.get("nps", "") or ""),
        cell=str(d.get("cell", "") or ""),
        surface=str(d.get("surface", "") or ""),
        value=str(d.get("value", "") or ""),
        event=str(d.get("event", "") or ""),
        buffer=str(d.get("buffer", "") or ""),
        filter=str(d.get("filter", "") or ""),
        tally=str(d.get("tally", "") or ""),
        meph=str(d.get("meph", "") or ""),
    )

def _tally_from_dict(d: dict) -> TallySettings:
    tallies = []
    for t in d.get("tallies", []):
        tallies.append(TallyDefinition(
            type=t.get("type", "F4"), number=t.get("number", 4),
            particles=t.get("particles") if isinstance(t.get("particles"), list) else [p.lower().strip() for p in t.get("particle", "n").replace(",", " ").split() if p.strip()], params=t.get("params", ""),
            generate_en=t.get("generate_en", t.get("enableEn", False)), generate_tn=t.get("generate_tn", t.get("enableTn", False)),
            multiplier=t.get("multiplier", ""),
        ))
    return TallySettings(tallies=tallies,
        fmesh_defs=_fmesh_from_list(d.get("fmesh_defs", [])),
        ptrac=_ptrac_from_dict(d.get("ptrac")),
        e_min=d.get("e_min", ""), e_max=d.get("e_max", ""), e_bins=d.get("e_bins", 0),
        e_log=d.get("e_log", False), e_custom_enabled=d.get("e_custom_enabled", False),
        e_custom_text=d.get("e_custom_text", ""),
        t0_min=d.get("t0_min", ""), t0_max=d.get("t0_max", ""), t0_bins=d.get("t0_bins", 0),
        t0_log=d.get("t0_log", False), t0_custom_enabled=d.get("t0_custom_enabled", False),
        t0_custom_text=d.get("t0_custom_text", ""), e_cards_text=d.get("e_cards_text", ""),
        t_cards_text=d.get("t_cards_text", ""),
        cut_n_t=d.get("cut_n_t", ""), cut_n_e=d.get("cut_n_e", ""), cut_n_wc1=d.get("cut_n_wc1", ""),
        cut_n_wc2=d.get("cut_n_wc2", ""), cut_n_swtm=d.get("cut_n_swtm", ""),
        cut_p_t=d.get("cut_p_t", ""), cut_p_e=d.get("cut_p_e", ""), cut_p_wc1=d.get("cut_p_wc1", ""),
        cut_p_wc2=d.get("cut_p_wc2", ""), cut_p_swtm=d.get("cut_p_swtm", ""),
        cut_e_t=d.get("cut_e_t", ""), cut_e_e=d.get("cut_e_e", ""), cut_e_wc1=d.get("cut_e_wc1", ""),
        cut_e_wc2=d.get("cut_e_wc2", ""), cut_e_swtm=d.get("cut_e_swtm", ""),
        cut_h_t=d.get("cut_h_t", ""), cut_h_e=d.get("cut_h_e", ""), cut_h_wc1=d.get("cut_h_wc1", ""),
        cut_h_wc2=d.get("cut_h_wc2", ""), cut_h_swtm=d.get("cut_h_swtm", ""),
        cut_he_t=d.get("cut_he_t", ""), cut_he_e=d.get("cut_he_e", ""), cut_he_wc1=d.get("cut_he_wc1", ""),
        cut_he_wc2=d.get("cut_he_wc2", ""), cut_he_swtm=d.get("cut_he_swtm", ""),
        cut_d_t=d.get("cut_d_t", ""), cut_d_e=d.get("cut_d_e", ""), cut_d_wc1=d.get("cut_d_wc1", ""),
        cut_d_wc2=d.get("cut_d_wc2", ""), cut_d_swtm=d.get("cut_d_swtm", ""),
        cut_t_t=d.get("cut_t_t", ""), cut_t_e=d.get("cut_t_e", ""), cut_t_wc1=d.get("cut_t_wc1", ""),
        cut_t_wc2=d.get("cut_t_wc2", ""), cut_t_swtm=d.get("cut_t_swtm", ""),
        cut_a_t=d.get("cut_a_t", ""), cut_a_e=d.get("cut_a_e", ""), cut_a_wc1=d.get("cut_a_wc1", ""),
        cut_a_wc2=d.get("cut_a_wc2", ""), cut_a_swtm=d.get("cut_a_swtm", ""),
    )

def _adv_from_dict(d: dict) -> AdvancedSettings:
    return AdvancedSettings(
        other_cards=d.get("other_cards", ""),
        phys_n_emax=d.get("phys_n_emax", ""), phys_n_emcnf=d.get("phys_n_emcnf", ""),
        phys_n_iunr=d.get("phys_n_iunr", ""), phys_n_dnb=d.get("phys_n_dnb", ""),
        phys_n_fisnu=d.get("phys_n_fisnu", ""),
        phys_p_emcpf=d.get("phys_p_emcpf", ""), phys_p_ides=d.get("phys_p_ides", ""),
        phys_p_nocoh=d.get("phys_p_nocoh", ""), phys_p_ispn=d.get("phys_p_ispn", ""),
        phys_p_nodop=d.get("phys_p_nodop", ""),
        phys_e_emax=d.get("phys_e_emax", ""), phys_e_ides=d.get("phys_e_ides", ""),
        phys_e_iphoto=d.get("phys_e_iphoto", ""), phys_e_ibad=d.get("phys_e_ibad", ""),
        phys_e_istrg=d.get("phys_e_istrg", ""), phys_e_bnum=d.get("phys_e_bnum", ""),
        phys_e_xnum=d.get("phys_e_xnum", ""), phys_e_rnok=d.get("phys_e_rnok", ""),
        phys_e_enum=d.get("phys_e_enum", ""), phys_e_numb=d.get("phys_e_numb", ""),
        phys_h_emax=d.get("phys_h_emax", ""), phys_h_ie=d.get("phys_h_ie", ""),
        phys_h_ipr=d.get("phys_h_ipr", ""), phys_h_rgas=d.get("phys_h_rgas", ""),
        phys_h_emin=d.get("phys_h_emin", ""), phys_h_ecut=d.get("phys_h_ecut", ""),
        phys_he_emax=d.get("phys_he_emax", ""), phys_he_ie=d.get("phys_he_ie", ""),
        phys_he_ipr=d.get("phys_he_ipr", ""), phys_he_rgas=d.get("phys_he_rgas", ""),
        phys_he_emin=d.get("phys_he_emin", ""), phys_he_ecut=d.get("phys_he_ecut", ""),
        source_mode=d.get("source_mode", "fixed"),
        sdef_par=d.get("sdef_par", ""), sdef_erg=d.get("sdef_erg", ""),
        sdef_pos_x=d.get("sdef_pos_x", ""), sdef_pos_y=d.get("sdef_pos_y", ""),
        sdef_pos_z=d.get("sdef_pos_z", ""), sdef_wgt=d.get("sdef_wgt", ""),
        sdef_dir=d.get("sdef_dir", ""), sdef_cel=d.get("sdef_cel", ""),
        sdef_tme=d.get("sdef_tme", ""), sdef_vec=d.get("sdef_vec", ""),
        sdef_axs=d.get("sdef_axs", ""), sdef_rad=d.get("sdef_rad", ""),
        sdef_ext=d.get("sdef_ext", ""), sdef_sur=d.get("sdef_sur", ""),
        sdef_nrm=d.get("sdef_nrm", ""), sdef_tr=d.get("sdef_tr", ""),
        sdef_ccc=d.get("sdef_ccc", ""), sdef_ara=d.get("sdef_ara", ""),
        # TD-23（t5）：不再接 sdef_raw_text（旧僵尸字段已退役；唯一权威 = sdef_distributions）
        sdef_rate=d.get("sdef_rate", ""),
        sdef_extra=d.get("sdef_extra", ""),
        kcode_nsrc=d.get("kcode_nsrc", ""), kcode_rkk=d.get("kcode_rkk", ""),
        kcode_ikz=d.get("kcode_ikz", ""), kcode_kct=d.get("kcode_kct", ""),
        kcode_knrm=d.get("kcode_knrm", ""), ksrc_points=d.get("ksrc_points", ""),
        kcode_msrk=d.get("kcode_msrk", ""), kcode_mrkp=d.get("kcode_mrkp", ""),
        kcode_kc8=d.get("kcode_kc8", ""),
        hsrc_enabled=d.get("hsrc_enabled", False), hsrc_text=d.get("hsrc_text", ""),
        sdef_distributions=d.get("sdef_distributions", ""),
        ssw_surf=d.get("ssw_surf", ""), ssw_sym=d.get("ssw_sym", ""),
        ssw_pty=d.get("ssw_pty", ""), ssw_cel=d.get("ssw_cel", ""),
        ssr_surf=d.get("ssr_surf", ""), ssr_mode=d.get("ssr_mode", ""),
        ssr_cel=d.get("ssr_cel", ""), ssr_pty=d.get("ssr_pty", ""),
        ssr_col=d.get("ssr_col", ""), ssr_wgt=d.get("ssr_wgt", ""),
        ssr_tr=d.get("ssr_tr", ""), ssr_psc=d.get("ssr_psc", ""),
    )

def deck_from_json(data: dict) -> DeckData:
    """JSON → DeckData 转换"""
    return DeckData(
        basic=_basic_from_dict(data.get("basic", {})),
        surfaces=data.get("surfaces", ""), tr_cards=data.get("tr_cards", ""),
        cells=_cells_from_list(data.get("cells", [])),
        materials=_materials_from_list(data.get("materials", [])),
        sources=_sources_from_list(data.get("sources", [])),
        tally=_tally_from_dict(data.get("tally", {})),
        adv=_adv_from_dict(data.get("adv", {})),
        universe_comments=(data.get("universe_comments")
                           or data.get("universeComments") or {}),
    )


def _deck_to_frontend_dict(deck: DeckData, include_frontend_aliases: bool = False,
                           include_warnings: bool = False, warnings=None) -> dict:
    """后端 DeckData → 前端 deck JSON。**单一实现**，三个消费者按需开参数。

    TD-22（t5）——原 docstring 自称"与 /api/parse-inp 的序列化一致"，**该声明已不成立**：
    两份实现早已分叉（`/api/parse-inp` 多注入 8 个前端顶层中间态键 + `_warnings`）。
    现改为一份实现 + 两个显式开关，避免"读 docstring 的人把两份当成同一契约改"。

    Args:
        include_frontend_aliases: True 时额外注入前端顶层中间态键——
            `sourceMode`（adv.source_mode → 前端词汇）/ `sdefFields` / `kcodeFields` /
            `ksrcPoints` / `distributions`（adv.sdef_distributions 解析为数组）/
            `sswFields` / `ssrFields`。`/api/parse-inp` 需要；MCP `/workspace` 不需要
            （前端权威是 deck.adv，顶层别名是为旧 UI 过渡保留的）。
        include_warnings: True 时把 warnings 写入 `_warnings`（前端解析提示展示源）。
        warnings: 与 include_warnings 搭配的解析警告列表。

    Note:
        默认（两个开关全 False）即 **窄口径**：不含任何前端顶层别名、也不含 `_warnings`——
        MCP `/workspace`（`deck_to_frontend_dict` 公开别名）与 `/api/text-to-section`
        （只用 materials/cells/tallies 三个子集）都走这个口径。
    """
    import dataclasses
    def to_dict(obj):
        if dataclasses.is_dataclass(obj):
            return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list):
            return [to_dict(x) for x in obj]
        return obj
    deck_dict = to_dict(deck)
    # 项9：backend universe_comments → 前端 universeComments（与 DeckContext 类型同步）
    deck_dict["universeComments"] = deck_dict.pop("universe_comments", {})
    # 后端用 rows，前端用 nuclides → 加入映射（行含 kind 判别）
    for m in deck_dict.get("materials", []):
        if "rows" in m and "nuclides" not in m:
            m["nuclides"] = m["rows"]
    # cells: CellRow 判别联合（raw 行保留 text；cell 行嵌套 CellData，并补 camelCase 字段）
    for c in deck_dict.get("cells", []):
        if c.get("kind") == "raw":
            continue
        cell = c.get("cell") or {}
        cell["num"] = str(cell.get("number", ""))
        cell["surfaces"] = cell.get("surface_expr", "")
        cell["impN"] = cell.get("imp_n", "")
        cell["impP"] = cell.get("imp_p", "")
        cell["impE"] = cell.get("imp_e", "")
        # ⚠️ mat 曾漏补：cellBridge.localToDeckCells 读的正是 num/mat/surfaces/(impN|impP|impE)，
        # 独缺 mat ⇒ 前端拿到 material="" ⇒ getMatColor("") 返回 "transparent" ⇒
        # buildCellMaterial 判为 M0 真空（opacity 0）⇒ 几何外壳整体不可见
        # （2026-09-11 实测：演示源 13 个外壳栅元全透明 invisible）。
        cell["mat"] = cell.get("material", "")
    if include_frontend_aliases:
        # 源项模式：backend 的 adv.source_mode → 顶层 sourceMode（前端词汇）
        adv = deck_dict.get("adv", {})
        deck_dict["sourceMode"] = {
            "distribution": "sdef", "fixed": "fixed",
            "kcode": "kcode", "surface": "surface",
        }.get(adv.get("source_mode", ""), "fixed")
        deck_dict["sdefFields"] = {k: v for k, v in adv.items() if k.startswith("sdef_")}
        deck_dict["kcodeFields"] = {k: v for k, v in adv.items() if k.startswith("kcode_")}
        deck_dict["ksrcPoints"] = adv.get("ksrc_points", "")
        # 结构化分布（v2 JSON 串 → 数组；坏 JSON 降级为 []，与原内联实现一致）
        try:
            deck_dict["distributions"] = json.loads(adv.get("sdef_distributions", "[]"))
        except Exception:
            deck_dict["distributions"] = []
        deck_dict["sswFields"] = {"surf": adv.get("ssw_surf", ""), "sym": adv.get("ssw_sym", ""),
                                  "pty": adv.get("ssw_pty", ""), "cel": adv.get("ssw_cel", "")}
        deck_dict["ssrFields"] = {"surf": adv.get("ssr_surf", ""), "mode": adv.get("ssr_mode", ""),
                                  "cel": adv.get("ssr_cel", ""), "pty": adv.get("ssr_pty", ""),
                                  "col": adv.get("ssr_col", ""), "wgt": adv.get("ssr_wgt", ""),
                                  "tr": adv.get("ssr_tr", ""), "psc": adv.get("ssr_psc", "")}
    # Tally: backend → frontend 字段名映射
    tally_raw = deck_dict.get("tally", {})
    deck_dict["tallies"] = [{
        "type": td.get("type", ""), "number": td.get("number", 0),
        "particle": " ".join(td.get("particles", [])),
        "params": td.get("params", ""),
        "enableEn": td.get("generate_en", False),
        "enableTn": td.get("generate_tn", False),
        "multiplier": td.get("multiplier", ""),
    } for td in tally_raw.get("tallies", [])]
    if include_warnings:
        deck_dict["_warnings"] = warnings or []
    return deck_dict


# 公开别名：DeckData → 前端 deck JSON（inputcard-mcp 等外部接入复用）
deck_to_frontend_dict = _deck_to_frontend_dict


def _fmt_num(v) -> str:
    """pandas 数值 → 显示字符串（None/NaN → 空串）。"""
    if v is None:
        return ""
    try:
        if v != v:  # NaN
            return ""
    except Exception:
        pass
    s = str(v).strip()
    return "" if s in ("", "nan", "None") else s


# ===== HTTP 服务 =====

class MCNPHandler(BaseHTTPRequestHandler):
    """处理所有 API 请求"""

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        # Browser-friendly: handle GET the same as POST for API
        self.do_POST()

    def do_POST(self):
        parsed = urlparse(self.path)
        handlers = {
            "/api/generate": self._handle_generate,
            "/api/expand-formula": self._handle_expand_formula,
            "/api/parse-inp": self._handle_parse_inp,
            "/api/save-inp": self._handle_save_inp,
            "/api/choose-dir": self._handle_choose_dir,
            "/api/choose-file": self._handle_choose_file,
            "/api/run-mcnp": self._handle_run_mcnp,
            "/api/xsdir-check": self._handle_xsdir_check,
            "/api/import-step": self._handle_import_step,
            "/api/mcnp-detect": self._handle_mcnp_detect,
            "/api/check-freecad": self._handle_check_freecad,
            "/api/set-freecad-path": self._handle_set_freecad_path,
            "/api/choose-freecad-path": self._handle_choose_freecad_path,
            "/api/validate-inp": self._handle_validate_inp,
            "/api/validate-zaid": self._handle_validate_zaid,
            "/api/parse-outp": self._handle_parse_outp,
            "/api/parse-keff": self._handle_parse_keff,
            "/api/xsdir-search": self._handle_xsdir_search,
            "/api/export-step": self._handle_export_step,
            "/api/preview-3d": self._handle_preview_3d,
            "/api/serve-file": self._handle_serve_file,
            "/api/cross-section": self._handle_cross_section,
            "/api/clear-stl": self._handle_clear_stl,
            "/api/section-to-text": self._handle_section_to_text,
            "/api/text-to-section": self._handle_text_to_section,
            "/api/meshtal-detect": self._handle_meshtal_detect,
            "/api/meshtal-parse": self._handle_meshtal_parse,
            "/api/meshtal-texture": self._handle_meshtal_texture,
            "/api/ptrac-detect": self._handle_ptrac_detect,
            "/api/ptrac-parse": self._handle_ptrac_parse,
            "/api/sweep-plan": self._handle_sweep_plan,
            "/api/sweep-run": self._handle_sweep_run,
            "/api/sweep-dashboard": self._handle_sweep_dashboard,
            "/api/diff-inp": self._handle_diff_inp,
            "/api/check-overlap": self._handle_check_overlap,
            "/api/check-cell-closure": self._handle_check_cell_closure,
            "/api/quick-add-check": self._handle_quick_add_check,
            "/api/validate-lattice-surfaces": self._handle_validate_lattice_surfaces,
            "/api/lattice-extent": self._handle_lattice_extent,
            "/api/validate-universe-coverage": self._handle_validate_universe_coverage,
            "/api/source-demo-sample": self._handle_source_demo_sample,
            "/api/preview-lattice": self._handle_preview_lattice,
            "/api/set-gpu-preference": self._handle_set_gpu_preference,
            "/api/material-library": self._handle_material_library,
            "/api/material-library/save": self._handle_material_library_save,
            "/api/material-library/delete": self._handle_material_library_delete,
            "/api/material-library/import": self._handle_material_library_import,
            "/api/material-library/export": self._handle_material_library_export,
        }
        handler = handlers.get(parsed.path)
        if handler:
            handler()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_set_gpu_preference(self):
        """设置应用 GPU 偏好（写 HKCU UserGpuPreferences），需重启生效。

        入参 preference ∈ {high(独显), power(核显), default(系统默认)}。对
        msedgewebview2.exe + 应用主 exe 写入 GpuPreference=2/1/0;。非 Windows 返回 changed=0。
        """
        try:
            gpu_pref = _import_app("gpu_pref")
            data = self._read_body() or {}
            pref = str(data.get("preference") or "high")
            if pref not in ("high", "power", "default"):
                pref = "high"
            res = gpu_pref.apply_gpu_preference(pref)
            self._ok({"status": "ok", "preference": pref, **res})
        except Exception as e:
            self._err(str(e))

    # ── 材料库（深化，2026-08）──
    def _handle_material_library(self):
        """返回用户材料库（文件侧 custom + override，不含内置 55+48）。"""
        try:
            ml = _import_app("material_library")
            self._ok({
                "materials": ml.list_materials(),
                "path": ml.library_path(),
            })
        except Exception as e:
            self._err(str(e))

    def _handle_material_library_save(self):
        """upsert 一条材料库条目。返回保存条目 + 组成自洽警告。"""
        try:
            ml = _import_app("material_library")
            data = self._read_body() or {}
            entry = data.get("entry")
            if not entry:
                raise ValueError("缺少 entry")
            saved = ml.save_material(entry)
            self._ok({"entry": saved, "warnings": ml.validate_entry(saved)})
        except Exception as e:
            self._err(str(e))

    def _handle_material_library_delete(self):
        """按 key 删除一条（custom 或 override）。"""
        try:
            ml = _import_app("material_library")
            data = self._read_body() or {}
            key = str(data.get("key") or "")
            if not key:
                raise ValueError("缺少 key")
            deleted = ml.delete_material(key)
            self._ok({"deleted": deleted, "key": key})
        except Exception as e:
            self._err(str(e))

    def _handle_material_library_import(self):
        """导入 JSON/CSV。dry_run=True 只返回预览（不写库）。

        body: {format, content, conflict, existing_keys, dry_run}
        conflict ∈ skip|overwrite|rename；existing_keys 为当前库全量 key（含内置），
        由前端传入；per-entry 校验（validate_entry + check_zaids_xsdir）随预览返回。
        """
        try:
            ml = _import_app("material_library")
            data = self._read_body() or {}
            fmt = str(data.get("format") or "json")
            content = data.get("content") or ""
            conflict = str(data.get("conflict") or "skip")
            existing_keys = data.get("existing_keys") or []
            existing_entries = data.get("existing_entries")
            dry_run = bool(data.get("dry_run"))
            if not content.strip():
                raise ValueError("导入内容为空")
            entries = ml.parse_import(content, fmt)
            preview = []
            for e in entries:
                preview.append({
                    "key": e.get("key"),
                    "name": e.get("name"),
                    "errors": ml.validate_entry(e),
                    "xsdir": ml.check_zaids_xsdir(e),
                })
            result = ml.apply_import(entries, conflict=conflict,
                                     existing_keys=existing_keys,
                                     existing_entries=existing_entries,
                                     dry_run=dry_run)
            self._ok({"result": result, "preview": preview,
                      "dry_run": dry_run, "format": fmt})
        except Exception as e:
            self._err(str(e))

    def _handle_material_library_export(self):
        """导出 JSON/CSV。body: {format, entries?}。未传 entries 用文件内全部材料。

        前端可传已合并（内置 ⊕ 文件）的 entries 以导出含内置的整库；
        不传则导出文件侧（custom+override）。
        """
        try:
            ml = _import_app("material_library")
            data = self._read_body() or {}
            fmt = str(data.get("format") or "json")
            entries = data.get("entries")
            if not entries:
                entries = list(ml.list_materials().values())
            if not entries:
                raise ValueError("没有可导出的材料")
            if fmt == "json":
                content = ml.export_json(entries)
            elif fmt == "csv":
                content = ml.export_csv(entries)
            else:
                raise ValueError("不支持的导出格式: " + str(fmt))
            self._ok({"format": fmt, "content": content})
        except Exception as e:
            self._err(str(e))

    # ── 参数扫描（sweep）──
    def _handle_sweep_plan(self):
        """参数扫描规划：笛卡尔组合 + 应用到 deck 文本（不执行 MCNP）。"""
        try:
            sweep = _import_app("sweep")
            data = self._read_body() or {}
            deck_text = data.get("deck") or ""
            parameters = data.get("parameters") or []
            combos = sweep.cartesian(parameters)
            previews = [
                sweep.apply_parameters(deck_text, c, parameters)
                for c in combos[:3]
            ]
            self._ok({"count": len(combos), "combos": combos, "previews": previews})
        except Exception as e:
            self._err(str(e))

    def _handle_sweep_run(self):
        """参数扫描执行：笛卡尔组合 → 线程池并行（workers 个同时跑）写 INP 调 MCNP →
        提取 keff → 汇总 TSV。

        总时长预算纪律：组合数 × 单次超时 ÷ 并行数 ≤ 预算（默认 30 分钟），超预算/超上限
        直接拒绝（code="budget_exceeded" + 中文消息）；单组合保持 300s 超时。
        每个组合在独立 run_XXX 子目录里以 ``name=sweep-{i:03d}.`` 命名输出
        （sweep-001.o / sweep-001.r …），并发互不覆盖、结果与组合号一一对应。
        临时目录在成功/失败后清理（摘要先拷到稳定目录再删）。
        """
        try:
            import glob
            import math
            import shutil
            import subprocess
            import tempfile
            from concurrent.futures import ThreadPoolExecutor
            sweep = _import_app("sweep")
            data = self._read_body() or {}
            deck_text = data.get("deck") or ""
            parameters = data.get("parameters") or []
            workers = int(data.get("workers") or 1)
            workers = max(1, min(workers, 32))
            combos = sweep.cartesian(parameters)
            budget = sweep.sweep_budget_status(
                len(combos), workers=max(1, workers))
            if budget is not None:
                self._ok({"status": "error", **budget})
                return
            exe = _find_mcnp_exe()
            if not exe:
                self._ok({"status": "error", "message": "未检测到 MCNP 可执行文件"})
                return
            base_dir = tempfile.mkdtemp(prefix="mcnp_sweep_")
            try:
                def run_one(idx: int):
                    """跑第 idx 个组合（1-based）。独立子进程 + 独立子目录，天然可并发。"""
                    i = idx + 1
                    combo = combos[idx]
                    inp = sweep.apply_parameters(deck_text, combo, parameters)
                    run_dir = os.path.join(base_dir, sweep.run_dir_name(i))
                    os.makedirs(run_dir, exist_ok=True)
                    inp_path = os.path.join(run_dir, "sweep.i")
                    with open(inp_path, "w", encoding="utf-8") as f:
                        f.write(inp)
                    rec = {"index": i, "parameters": combo, "inputFile": inp_path,
                           "outputDir": run_dir, "exitCode": None, "keff": None}
                    try:
                        # name=sweep-XXX. → 输出文件 sweep-001.o / sweep-001.r …，
                        # 多组合并行时互不覆盖（与组合序号一一对应）。
                        proc = subprocess.run(
                            [exe, "i=sweep.i", f"name=sweep-{i:03d}."],
                            cwd=run_dir, capture_output=True, text=True, timeout=300,
                        )
                        rec["exitCode"] = proc.returncode
                        rec["keff"] = sweep.parse_keff(
                            (proc.stdout or "") + "\n" + (proc.stderr or ""))
                    except subprocess.TimeoutExpired:
                        # TD-26（t5）：原为裸 `pass` —— 超时后 exitCode 保持 None、无日志、
                        # 无标记，落盘 manifest/TSV 里与"MCNP 无输出"不可区分（都出 n/a）。
                        # 现在显式标记 + 告警，让"超时 / 崩溃 / 无 keff"三者可归因。
                        rec["exitCode"] = "timeout"
                        rec["timedOut"] = True
                        print(f"[sweep] 组合 {i} 超时（{sweep.SWEEP_PER_RUN_TIMEOUT}s）：{run_dir}",
                              file=sys.stderr)
                    # 收敛序列（仪表盘小图）：优先读该组合目录里的 mctal
                    # （name= 前缀可能影响 mctal 命名，故两种 glob 都试）
                    try:
                        mctal_paths = sorted(
                            glob.glob(os.path.join(run_dir, "mctal*")) +
                            glob.glob(os.path.join(run_dir, f"sweep-{i:03d}.m*")))
                        if mctal_paths:
                            with open(mctal_paths[0], "r", encoding="utf-8",
                                      errors="replace") as f:
                                hist = sweep.parse_keff_history(f.read())
                            if hist:
                                rec["convergence"] = hist
                                if hist.get("std"):
                                    rec["keffStd"] = hist["std"][-1]
                    except Exception:
                        pass
                    return rec

                records = []
                if workers > 1 and len(combos) > 1:
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        records = list(pool.map(run_one, range(len(combos))))
                else:
                    records = [run_one(idx) for idx in range(len(combos))]
                records.sort(key=lambda r: r["index"])
                tsv = sweep.build_summary_tsv(parameters, records)
                manifest = sweep.build_manifest("sweep.i", "mcnp", parameters, records)
                # 摘要（manifest + TSV）拷到稳定目录后清理临时目录（T8）
                summary_base, manifest_path, _ = sweep.persist_sweep_summary(
                    base_dir, manifest, tsv)
                self._ok({"status": "ok", "baseDir": summary_base,
                          "records": records, "summaryTsv": tsv,
                          "workers": workers,
                          "manifest": manifest, "manifestPath": manifest_path})
            finally:
                shutil.rmtree(base_dir, ignore_errors=True)
        except Exception as e:
            self._err(str(e))

    def _handle_sweep_dashboard(self):
        """读取历史扫描目录（sweep-manifest.json），补齐缺失的收敛序列后返回。"""
        try:
            data = self._read_body() or {}
            base_dir = data.get("baseDir", "")
            manifest_path = os.path.join(base_dir, "sweep-manifest.json")
            if not os.path.isfile(manifest_path):
                self._err(f"扫描清单不存在：{manifest_path}")
                return
            with open(manifest_path, "r", encoding="utf-8-sig") as f:
                manifest = json.load(f)
            import glob
            sweep = _import_app("sweep")
            for rec in manifest.get("runs", []):
                if rec.get("convergence"):
                    continue
                run_dir = rec.get("outputDir", "")
                if not run_dir or not os.path.isdir(run_dir):
                    continue
                try:
                    mctal_paths = sorted(glob.glob(os.path.join(run_dir, "mctal*")))
                    if not mctal_paths:
                        continue
                    with open(mctal_paths[0], "r", encoding="utf-8",
                              errors="replace") as f:
                        hist = sweep.parse_keff_history(f.read())
                    if hist:
                        rec["convergence"] = hist
                        if hist.get("std"):
                            rec["keffStd"] = hist["std"][-1]
                except Exception:
                    continue
            self._ok({"status": "ok", "baseDir": base_dir, "manifest": manifest})
        except Exception as e:
            self._err(str(e))

    def _handle_diff_inp(self):
        """两段 INP 文本行级 diff（unified 格式 + 增删统计）。"""
        try:
            data = self._read_body() or {}
            _diff = _import_app("diff_inp")
            diff_stats = _diff.diff_stats
            unified_diff_text = _diff.unified_diff_text
            text_a = data.get("text_a", "")
            text_b = data.get("text_b", "")
            diff = unified_diff_text(text_a, text_b)
            self._ok({
                "status": "ok",
                "diff": diff,
                "stats": diff_stats(diff),
            })
        except Exception as e:
            self._err(str(e))

    # ── 3D 重合检测（独立端点，不碰 preview-3d 契约）──
    def _handle_check_overlap(self):
        """重合检测：AABB 空间索引候选 + FreeCAD 精确布尔 + GQ/SQ 解析采样探针。

        入参与 preview-3d 同（surfaces/cells/tr_cards）；真空栅元参与检测。
        结果按 deck 指纹缓存（overlaps.json）。
        """
        try:
            data = self._read_body()
            surf_text = data.get("surfaces", "")
            # 格阵感知：排除 universe 栅元（u 非空）——它们是经 fill 装配的组件，
            # 本地坐标下所有 pin 都在原点 → 会误报假重叠；真实装配位置检查属格阵级。
            cell_list = [c for c in (data.get("cells", []) or [])
                         if not _cell_u_of(c)]
            tr_text = data.get("tr_cards", "")
            fp = _PREVIEW_CACHE.fingerprint(surf_text, cell_list, tr_text)
            cached = _PREVIEW_CACHE.get_overlaps(fp)
            if cached is not None:
                self._ok(cached)
                return

            # 格阵装配后真实重叠（首版，FreeCAD 无关先算）：实心 pin 超出格元盒
            # （半径 > pitch/2 撞邻居）。需完整 cell_list（含格阵 cell 与 universe 栅元）。
            lattice = _import_app("lattice")
            fit = _lattice_pin_fit_overlaps(data.get("cells", []) or [],
                                            surf_text, lattice)

            StepImporter = _import_app("step_importer").StepImporter
            FreeCADEngine = _import_app("freecad_preview").FreeCADEngine
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "ok", "overlaps": fit, "truncated": False,
                          "unresolved": [],
                          "message": "未检测到 FreeCAD（格阵 pin 适配检测已返回）"})
                return
            surfs = parse_surfaces(surf_text)
            if not surfs:
                self._ok({"status": "ok", "overlaps": fit, "truncated": False,
                          "unresolved": [], "message": "未解析到有效曲面"})
                return
            tr_cards = parse_tr_cards(tr_text)
            cells_data = build_cells_data(cell_list, include_void=True)
            if not cells_data:
                self._ok({"status": "ok", "overlaps": fit, "truncated": False,
                          "unresolved": [], "message": "没有可检测的栅元"})
                return
            engine = FreeCADEngine(freecad_bin)
            engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl",
                                  check_overlaps=True)
            engine.cleanup()
            report = {"status": "ok", "overlaps": list(engine.overlaps) + fit,
                      "truncated": engine.overlap_truncated,
                      "unresolved": engine.overlap_unresolved,
                      "zero_volume": engine.zero_volume}
            _PREVIEW_CACHE.put_overlaps(fp, report)
            self._ok(report)
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _handle_check_cell_closure(self):
        """单个栅元封闭性判定：每个 cell 的 BRep 实体是否封闭有界，还是延伸到
        包围盒边界（无限大空间）或空/退化。不需要外部栅元标记。

        Worker 对每个 cell 判定状态：
          - closed: 实体有限体积，AABB 不触及包围盒边界
          - infinite: 实体延伸到包围盒边界（曲面外无限大空间）
          - semi_infinite: 实体在某轴延伸至边界（非全包围的外无限）
          - empty: 体积≈0（空/退化）
          - voxel/unresolvable: GQ/SQ 或解析失败
        """
        try:
            data = self._read_body()
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", []) or []
            tr_text = data.get("tr_cards", "")

            StepImporter = _import_app("step_importer").StepImporter
            FreeCADEngine = _import_app("freecad_preview").FreeCADEngine
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "ok", "closure_report": {},
                          "message": "未检测到 FreeCAD，封闭性检测需要 FreeCAD"})
                return

            surfs = parse_surfaces(surf_text)
            if not surfs:
                self._ok({"status": "ok", "closure_report": {},
                          "message": "未解析到有效曲面"})
                return

            tr_cards = parse_tr_cards(tr_text)
            # 强制包含全部栅元（不跳过 graveyard/fill/void/render:false），
            # 封闭性需要每个栅元都参与检测。收集所有栅元号用于 force_include。
            all_nums = set()
            for c in cell_list:
                if not isinstance(c, dict): continue
                if c.get("kind") == "cell": c = c.get("cell") or {}
                n = c.get("number") or (c.get("num") and int(c["num"])) or 0
                if n > 0: all_nums.add(n)
            cells_data = build_cells_data(cell_list, include_void=True,
                                          force_include_numbers=all_nums)
            if not cells_data:
                self._ok({"status": "ok", "closure_report": {},
                          "message": "没有可检测的栅元"})
                return
            if not cells_data:
                self._ok({"status": "ok", "closure_report": {},
                          "message": "没有可检测的栅元"})
                return

            engine = FreeCADEngine(freecad_bin)
            engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl",
                                  check_closure=True)
            engine.cleanup()

            self._ok({"status": "ok",
                      "closure_report": engine.closure_report})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _handle_quick_add_check(self):
        """快捷建栅元重合检查：新栅元 vs 已有栅元 → 重叠列表 + 推荐补集方向。

        recommended ∈ "new_hole"（新 # 已有）| "existing_hole"（已有 # 新）。
        """
        try:
            data = self._read_body()
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", []) or []
            tr_text = data.get("tr_cards", "")
            new_cell = data.get("new_cell") or {}
            new_cells = data.get("new_cells") or ([new_cell] if new_cell else [])
            new_cells = [c for c in new_cells if c and c.get("surface_expr")]
            if not new_cells:
                self._ok({"status": "ok", "overlaps": [], "recommended": "new_hole",
                          "message": "新栅元缺少几何表达式"})
                return
            new_nums = [int(c.get("number", 0) or 0) for c in new_cells]

            StepImporter = _import_app("step_importer").StepImporter
            FreeCADEngine = _import_app("freecad_preview").FreeCADEngine
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "ok", "overlaps": [], "recommended": "new_hole",
                          "message": "未检测到 FreeCAD，请安装后重试"})
                return
            surfs = parse_surfaces(surf_text)
            tr_cards = parse_tr_cards(tr_text)
            # 与 check-overlap 同口径：排除 universe 栅元（本地坐标会误报假重叠），
            # 真实装配位置检查属格阵级（lattice-fit）。否则快捷建栅元在含 fill 卡
            # 的 deck（尤甚 fill套fill）上会对本地原点 universe 误报重叠。
            all_cells = list(c for c in cell_list if not _cell_u_of(c)) + [
                {"kind": "cell", "cell": c} for c in new_cells]
            cells_data = build_cells_data(all_cells, include_void=True)
            engine = FreeCADEngine(freecad_bin)
            engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl",
                                  check_overlaps=True, focus_nums=new_nums)
            engine.cleanup()
            overlaps = engine.overlaps
            # 任一重合占比超阈值（新栅元几乎完全在已有内）→ 已有让位
            recommended = "existing_hole" if any(
                float(o.get("volumeFraction", 0)) > RECOMMEND_EXISTING_HOLE_FRAC for o in overlaps
            ) else "new_hole"
            self._ok({"status": "ok", "overlaps": overlaps,
                      "recommended": recommended,
                      "truncated": engine.overlap_truncated,
                      "unresolved": engine.overlap_unresolved,
                      "zero_volume": engine.zero_volume})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _read_body(self) -> dict:
        content_len = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(content_len))

    def _ok(self, data: dict):
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", **data}, ensure_ascii=False).encode("utf-8"))

    def _err(self, msg: str, status=500, hint=""):
        import traceback
        tb = traceback.format_exc()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {"status": "error", "message": msg, "traceback": tb}
        # F4：hint 非空才带（对既有 25 端点加性兼容，响应字段零变化）
        if hint:
            payload["hint"] = hint
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    # ── 生成 ──
    def _handle_generate(self):
        try:
            data = self._read_body()
            deck = deck_from_json(data)
            # raw_overrides 是独立参数（DeckData 无此字段），必须单独传给生成器。
            # 按需导入 inp_generator（其模块顶层会 import pymcnp，见上方注释）。
            from generator.inp_generator import generate_inp_from_deck
            inp_text = generate_inp_from_deck(deck, data.get("raw_overrides") or {})
            self._ok({"inp": inp_text})
        except Exception as e:
            self._err(str(e))

    # ── 化学式展开 ──
    def _handle_expand_formula(self):
        try:
            data = self._read_body()
            text = data.get("formula", "").strip()
            if not text: raise ValueError("化学式为空")
            # is_weight：True=质量份额（MCNP 负号约定），False=原子份额（正号）。
            # 默认 True 保持向后兼容（前端未传/传 null 时行为与现状一致）。
            is_weight = data.get("is_weight", True)
            if is_weight is None:
                is_weight = True
            elif isinstance(is_weight, str):
                is_weight = is_weight.strip().lower() not in ("", "0", "false", "no")
            import pymcnp
            formulas = {}
            for line in text.split("\n"):
                for part in line.split(","):
                    part = part.strip()
                    if not part: continue
                    if ":" in part:
                        f, r = part.split(":", 1)
                        formulas[f.strip()] = float(r.strip())
                    else:
                        tok = part.split()
                        formulas[tok[0]] = float(tok[1]) if len(tok) > 1 else 1
            all_rows = []
            for sym, ratio in formulas.items():
                sub = pymcnp.inp.M_0.from_formula({sym: 1}, is_weight=is_weight, cutoff=1e-9)
                parts = str(sub).replace("&", " ").replace("\n", " ").split()
                for k in range(1, len(parts)-1, 2):  # 跳过 m1 标签
                    zaid = parts[k]
                    frac = float(parts[k+1]) * ratio
                    if xsdir_db.loaded and "." in zaid:
                        num = zaid.split(".")[0]
                        matches = [z for z in xsdir_db.zaids if z.split(".")[0] == num]
                        if matches: zaid = matches[0]
                    all_rows.append((zaid, frac))
            if not all_rows: raise ValueError("pymcnp 返回空")
            total = sum(abs(f) for _, f in all_rows)
            if total > 0 and abs(total-1) > 1e-9:
                all_rows = [(z, f/total) for z, f in all_rows]
            nuclides = [{"zaid": z.lstrip("0") or "0", "fraction": f"{frac:.6f}"} for z, frac in all_rows]
            self._ok({"nuclides": nuclides})
        except Exception as e:
            self._err(str(e))

    # ── INP 解析 ──
    def _handle_parse_inp(self):
        try:
            data = self._read_body()
            text = data.get("inp", "")
            if not text: raise ValueError("INP 内容为空")
            deck, warnings = parse_inp_text(text)
            # TD-22（t5）：改调 _deck_to_frontend_dict 的**宽口径**（含前端顶层别名 + _warnings），
            # 与原先内联的 ~55 行逐字等价（本次为纯去重，输出不变）。
            deck_dict = _deck_to_frontend_dict(
                deck, include_frontend_aliases=True,
                include_warnings=True, warnings=warnings)
            self._ok({"deck": deck_dict})
        except Exception as e:
            self._err(str(e))

    # ── 片段互转：表单 → 文本 ──
    def _handle_section_to_text(self):
        """把某模块的表单数据生成该模块的 INP 文本（供切到文本模式时预填）。

        入参: {section: "materials"|"cells"|"tally", deck: {前端 deck}}
        返回: {text}
        """
        try:
            data = self._read_body()
            section = data.get("section", "")
            deck = deck_from_json(data.get("deck") or {})
            from generator.inp_generator import _generate_materials, _generate_cells
            text = ""
            if section == "materials":
                text = "\n".join(_generate_materials(deck.materials))
            elif section == "cells":
                text = "\n".join(_generate_cells(deck.cells))
            elif section == "tally":
                # 复用生成器的 F 卡 + En/Tn 段（与完整生成一致）
                from generator.inp_generator import _generate_tallies, _generate_en_cards, _generate_tn_cards
                text = "\n".join(_generate_tallies(deck.tally) + _generate_en_cards(deck.tally) + _generate_tn_cards(deck.tally))
            else:
                raise ValueError(f"不支持的 section: {section}")
            self._ok({"text": text})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── 片段互转：文本 → 表单 ──
    def _handle_text_to_section(self):
        """把某模块的 INP 文本解析回表单数据（供切回表单时回填）。

        入参: {section: "materials"|"cells"|"tally", text}
        返回: {data: 该模块的结构化数据}
          materials → {materials: [...]}
          cells     → {cells: [...]}
          tally     → {tallies: [...]}
        """
        try:
            data = self._read_body()
            section = data.get("section", "")
            text = data.get("text", "")
            if not text.strip():
                raise ValueError("文本为空")
            # 包最小假 INP 壳：标题 + 空栅元 + 空曲面 + 数据卡段 = 该模块文本
            # cells 的文本必须放入【栅元段】（否则落入数据段被 other_cards 兜底，用户栅元字段全丢）
            if section == "cells":
                shell = f"{text}\n\nC  surf\n1 pz -1e9\n\nMODE N\n"
            else:
                shell = f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"
            deck, _warnings = parse_inp_text(shell)
            d = _deck_to_frontend_dict(deck)
            if section == "materials":
                self._ok({"data": {"materials": d.get("materials", [])}})
            elif section == "cells":
                self._ok({"data": {"cells": d.get("cells", [])}})
            elif section == "tally":
                self._ok({"data": {"tallies": d.get("tallies", [])}})
            else:
                raise ValueError(f"不支持的 section: {section}")
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── MESHTAL：自动探测 ──
    def _handle_meshtal_detect(self):
        """扫描 output_dir 找 meshtal* / MSHT* 文件（大小写不敏感，按 mtime 降序）。"""
        import datetime, re as _re
        try:
            data = self._read_body()
            output_dir = data.get("outputDir", "D:/MCNP/new")
            if not isinstance(output_dir, str) or not output_dir.strip():
                self._err("输出目录非法", hint="请确认输出目录路径正确")
                return
            files = []
            if os.path.isdir(output_dir):
                entries = []
                try:
                    with os.scandir(output_dir) as it:
                        for e in it:
                            if e.is_file() and _re.match(r'(?i)^(meshtal|MSHT)', e.name):
                                st = e.stat()
                                entries.append((st.st_mtime, {
                                    "path": e.path, "name": e.name, "size": st.st_size,
                                    "mtime": datetime.datetime.fromtimestamp(
                                        st.st_mtime, tz=datetime.timezone.utc
                                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                }))
                except OSError:
                    entries = []
                entries.sort(key=lambda x: x[0], reverse=True)
                files = [x[1] for x in entries]
            self._ok({"files": files, "outputDir": output_dir})
        except Exception as e:
            self._err(str(e), hint="扫描 meshtal 文件失败，请确认输出目录存在")

    # ── MESHTAL：解析（子进程 worker，元数据 + grid_bounds + match）──
    def _handle_meshtal_parse(self):
        """子进程 worker 解析 meshtal → 元数据；比对 deck↔meshtal（A1.2）。"""
        try:
            import subprocess
            data = self._read_body()
            path = data.get("path", "")
            if not path or not os.path.isfile(path):
                self._err("不是有效的 meshtal 文件",
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return
            worker = _meshtal_worker_cmd()
            proc = subprocess.run(
                worker,
                input=json.dumps({"mode": "parse", "path": path}),
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                self._err(f"meshtal 解析失败: {proc.stderr[-300:]}",
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return
            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                self._err(f"解析 worker 输出失败: {e}",
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return
            if result.get("status") != "ok":
                self._err(result.get("message", "meshtal 解析失败"),
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return

            # A1.2：deck↔meshtal 比对（纯函数，不阻塞）；两者皆缺 → match:null
            from meshtal.deck_match import AABB, check_match
            grid_box = None
            gb = result.get("grid_bounds")
            if gb:
                grid_box = AABB(tuple(gb["min"]), tuple(gb["max"]))
            model_box = None
            mb = data.get("modelBox")
            if mb is not None and mb.get("min") is not None and mb.get("max") is not None:
                model_box = AABB(tuple(mb["min"]), tuple(mb["max"]))
            else:
                # A1.2 契约缺口修复（2026-08-15）：前端只发 cells/surfaces/tr_cards，
                # 由 handler 推算模型盒（契约「或由 handler 算」分支此前未实现 → match 恒 null）
                mb2 = _model_box_from_cells_surfaces(data)
                if mb2 is not None:
                    model_box = AABB(tuple(mb2["min"]), tuple(mb2["max"]))
            match = None
            if grid_box is not None and model_box is not None:
                rep = check_match(grid_box, model_box)
                match = {
                    "matched": rep.matched,
                    "overlapFraction": rep.overlap_fraction,
                    "centerOffsetFrac": rep.center_offset_frac,
                    "reason": rep.reason,
                    "message": rep.message,
                }

            import datetime
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            self._ok({
                "file": {"path": path, "size": size,
                         "mtime": datetime.datetime.fromtimestamp(
                             mtime, tz=datetime.timezone.utc
                         ).strftime("%Y-%m-%dT%H:%M:%SZ")},
                "header": {"code": result.get("code"), "version": result.get("version"),
                           "histories": result.get("histories")},
                "grid_bounds": gb,
                "match": match,
                "tallies": result.get("tallies", []),
                "warnings": result.get("warnings", []),
            })
        except Exception as e:
            self._err(str(e), hint="解析 meshtal 文件失败，请确认是 MCNP 生成的 meshtal 文件")

    # ── MESHTAL：标量帧纹理（子进程 worker，Uint8 base64）──
    def _handle_meshtal_texture(self):
        """子进程 worker 取 (energy,time) 帧 → 降采样标量帧 Uint8 base64（非 RGBA）。"""
        try:
            import subprocess
            data = self._read_body()
            path = data.get("path", "")
            if not path or not os.path.isfile(path):
                self._err("不是有效的 meshtal 文件",
                          hint="请确认是 MCNP 生成的 meshtal 文件，文件格式不对或版本不兼容")
                return
            worker = _meshtal_worker_cmd()
            proc = subprocess.run(
                worker,
                input=json.dumps({
                    "mode": "texture", "path": path,
                    "tallyNumber": data.get("tallyNumber"),
                    "energyBin": data.get("energyBin", 0),
                    "timeBin": data.get("timeBin", 0),
                    "resolution": data.get("resolution", 128),
                    "normalize": data.get("normalize", "adaptive"),
                }),
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                self._err(f"meshtal 纹理提取失败: {proc.stderr[-300:]}",
                          hint="请重新选择计数与能量/时间范围")
                return
            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                self._err(f"解析 worker 输出失败: {e}",
                          hint="请重新选择计数与能量/时间范围")
                return
            if result.get("status") != "ok":
                self._err(result.get("message", "meshtal 纹理提取失败"),
                          hint="请重新选择计数与能量/时间范围")
                return
            self._ok({"frame": result["frame"]})
        except Exception as e:
            self._err(str(e), hint="提取体积纹理失败，请重新选择计数与能量/时间范围")

    # ── PTRAC：粒子径迹解析（子进程 worker，不阻塞 5001）──
    # ── PTRAC：自动探测（照 meshtal-detect，输出目录扫 ptrac 径迹文件）──
    def _handle_ptrac_detect(self):
        """扫描 output_dir 找 PTRAC 径迹文件（大小写不敏感，按 mtime 降序）。"""
        import datetime, re as _re
        try:
            data = self._read_body()
            output_dir = data.get("outputDir", "D:/MCNP/new")
            if not isinstance(output_dir, str) or not output_dir.strip():
                self._err("输出目录非法", hint="请确认输出目录路径正确")
                return
            files = []
            if os.path.isdir(output_dir):
                entries = []
                try:
                    with os.scandir(output_dir) as it:
                        for e in it:
                            # MCNP 默认径迹文件名为 ptrac（无扩展名），也兼容 ptrac.* 重命名
                            if e.is_file() and _re.match(r'(?i)^ptrac(\..*)?$', e.name):
                                st = e.stat()
                                entries.append((st.st_mtime, {
                                    "path": e.path, "name": e.name, "size": st.st_size,
                                    "mtime": datetime.datetime.fromtimestamp(
                                        st.st_mtime, tz=datetime.timezone.utc
                                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                }))
                except OSError:
                    entries = []
                entries.sort(key=lambda x: x[0], reverse=True)
                files = [x[1] for x in entries]
            self._ok({"files": files, "outputDir": output_dir})
        except Exception as e:
            self._err(str(e), hint="扫描 PTRAC 文件失败，请确认输出目录存在")

    def _handle_ptrac_parse(self):
        """子进程 worker 解析 PTRAC → header/tracks/worldBox/stats/truncated（契约 v2 §3）。"""
        try:
            import subprocess
            data = self._read_body()
            path = data.get("path", "")
            if not path or not os.path.isfile(path):
                self._err("不是有效的 PTRAC 文件",
                          hint="请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")
                return
            worker = _ptrac_worker_cmd()
            proc = subprocess.run(
                worker,
                input=json.dumps({
                    "mode": "parse", "path": path,
                    "maxTracks": data.get("maxTracks", 500),
                    "maxPoints": data.get("maxPoints", 200000),
                }),
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                self._err(f"PTRAC 解析失败: {proc.stderr[-300:]}",
                          hint="请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")
                return
            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                self._err(f"解析 worker 输出失败: {e}",
                          hint="请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")
                return
            if result.get("status") != "ok":
                self._err(result.get("message", "PTRAC 解析失败"),
                          hint="请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")
                return
            self._ok({
                "header": result.get("header", {}),
                "tracks": result.get("tracks", []),
                "worldBox": result.get("world_box"),
                "stats": result.get("stats", {}),
                "truncated": result.get("truncated", False),
            })
        except Exception as e:
            self._err(str(e), hint="解析 PTRAC 文件失败，请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）")

    # ── 保存 INP 到目录 ──
    def _handle_save_inp(self):
        try:
            data = self._read_body()
            inp_text = data.get("inp", "")
            filename = data.get("filename", "output.inp")
            output_dir = data.get("outputDir", "D:/MCNP/new")
            run_bat = data.get("runBat", "")
            os.makedirs(output_dir, exist_ok=True)
            inp_path = os.path.join(output_dir, filename)
            with open(inp_path, "w", encoding="utf-8") as f:
                f.write(inp_text)
            if run_bat:
                bat_name = filename.rsplit(".", 1)[0] + ".bat"
                bat_path = os.path.join(output_dir, bat_name)
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(run_bat)
            self._ok({"path": inp_path})
            _open_in_explorer(output_dir)
        except Exception as e:
            self._err(str(e))

    # ── 选择目录 ──
    def _handle_choose_dir(self):
        """弹出系统原生目录选择窗口，返回所选路径（取消返回 cancelled）"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            data = self._read_body()
            initial = data.get("initialDir", "") or os.getcwd()
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                path = filedialog.askdirectory(title="选择输出目录", initialdir=initial)
            finally:
                root.destroy()
            self._ok({"path": path or "", "cancelled": not path})
        except Exception as e:
            self._err(f"无法打开系统目录选择器: {e}")

    # ── 选择文件（原生打开对话框，返回路径+内容）──
    def _handle_choose_file(self):
        """弹出系统原生文件选择窗口，返回所选文件路径和内容（取消返回 cancelled）"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                path = filedialog.askopenfilename(
                    title="选择 MCNP INP 文件",
                    filetypes=[("MCNP 输入卡", "*.inp *.i *.txt"), ("所有文件", "*.*")],
                )
            finally:
                root.destroy()
            if not path:
                self._ok({"path": "", "cancelled": True})
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self._ok({"path": path, "content": content, "cancelled": False})
        except Exception as e:
            self._err(f"无法打开系统文件选择器: {e}")

    # ── 运行 MCNP ──
    def _handle_run_mcnp(self):
        try:
            import subprocess, threading
            data = self._read_body()
            inp_text = data.get("inp", "")
            filename = data.get("filename", "output.inp")
            output_dir = data.get("outputDir", "D:/MCNP/new")
            exe = data.get("mcnpExe", "") or ""
            if not inp_text.strip():
                raise ValueError("INP 内容为空")
            os.makedirs(output_dir, exist_ok=True)
            # 定位 MCNP 可执行文件（前端传的 > 自动检测）
            if not exe or not os.path.isfile(exe):
                exe = _find_mcnp_exe()
            if not exe or not os.path.isfile(exe):
                raise FileNotFoundError("未找到 mcnp6.exe，请检查 MCNP 安装或手动配置")
            # 保存 inp 和 run.bat（临时，跑完自动删除）
            inp_path = os.path.join(output_dir, filename)
            base = filename.rsplit(".", 1)[0]
            bat_path = os.path.join(output_dir, base + ".bat")
            saved_mtime = os.path.getmtime(inp_path) if os.path.exists(inp_path) else None
            with open(inp_path, "w", encoding="utf-8") as f:
                f.write(inp_text)
            # 显卡选择：本机 GPU0 是核显，GPU1 是独显（CUDA 只认 NVIDIA）。
            # CUDA_VISIBLE_DEVICES=1 让 MCNP 跳过核显直接用独显加速。
            # ── CPU 线程数（tasks N）──
            # C810 页 875：DBCN(2,3,4) / SSW / SSR / PTRAC 与 tasks > 1 不兼容（FATAL error），
            # 故先扫卡；命中即压回单线程并把原因回传前端（前端 alert 显示 tasksNote）。
            # 纯逻辑在 app/mcnp_tasks.py（独立成模块才能被单测覆盖 —— pytest 禁止 import 本文件）。
            tasks, tasks_note = _import_app("mcnp_tasks").resolve_mcnp_tasks(data.get("tasks"), inp_text)
            tasks_arg = f" tasks {tasks}" if tasks > 1 else ""
            gpu_device = os.environ.get("MCNP_GPU_DEVICE", "1")
            run_bat = (f"@echo off\r\nset CUDA_VISIBLE_DEVICES={gpu_device}\r\n"
                       f"call \"{exe}\" inp={filename} outp={base}.o{tasks_arg}\r\npause\r\n")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(run_bat)
            # 后台线程：在新控制台窗口里跑 run.bat（窗口可见，用户能看到 MCNP 在跑，
            # pause 让跑完的窗口停住）；MCNP 结束后自动删除临时 inp + bat。
            def _run_and_cleanup():
                try:
                    proc = subprocess.Popen(
                        ["cmd.exe", "/c", bat_path], cwd=output_dir,
                        creationflags=subprocess.CREATE_NEW_CONSOLE)
                    proc.wait()
                except Exception:
                    pass
                finally:
                    for p in (inp_path, bat_path):
                        try:
                            # 仅当文件没被新一轮运行改写过才删除（防竞态）
                            if not os.path.exists(p):
                                continue
                            if p == inp_path and saved_mtime is not None:
                                if abs(os.path.getmtime(p) - saved_mtime) > 1.0:
                                    continue
                            os.remove(p)
                        except OSError:
                            pass
            threading.Thread(target=_run_and_cleanup, daemon=True).start()
            self._ok({"status": "started", "path": inp_path, "exe": exe,
                      "tasks": tasks, "tasksNote": tasks_note})
            _open_in_explorer(output_dir)
        except Exception as e:
            self._err(str(e))

    # ── xsdir 状态 ──
    def _handle_xsdir_check(self):
        try:
            if not xsdir_db.loaded:
                # Priority 1: environment variables (XSDIR, DATAPATH)
                env_path = ""
                for _var in ("XSDIR", "xsdir"):
                    _val = os.environ.get(_var, "")
                    if _val and os.path.isfile(_val):
                        env_path = _val; break
                if not env_path:
                    _dp = os.environ.get("DATAPATH", "")
                    if _dp:
                        _cand = os.path.join(_dp, "xsdir")
                        if os.path.isfile(_cand): env_path = _cand
                if env_path:
                    xsdir_db.load(env_path)
                else:
                    # Priority 2: hardcoded common paths
                    found = xsdir_db.find_xsdir()
                    if found:
                        xsdir_db.load(found)
            count = xsdir_db.count() if hasattr(xsdir_db, 'count') else 0
            self._ok({"loaded": xsdir_db.loaded, "count": count, "path": getattr(xsdir_db, 'path', None)})
        except Exception as e:
            self._ok({"loaded": False, "count": 0, "error": str(e)})

    # ── STEP 导入 ──
    def _handle_import_step(self):
        try:
            import os, tempfile
            from step_importer import (StepImporter, run_step_converter,
                                       MCNPOutputParser, geometry_deck_response,
                                       StepConversionError)
            data = self._read_body()
            step_data = data.get("data", "")
            step_path = data.get("path", "")
            settings = data.get("settings", {})
            material = settings.get("materialName", "MAT")
            density_val = settings.get("density", "-1.0")
            try:
                density = float(density_val)
            except Exception:
                density = -1.0

            # STEP 数据以文本传入时落盘为临时文件
            if step_data:
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".step", delete=False, mode="w", encoding="utf-8")
                tmp.write(step_data)
                tmp.close()
                step_path = tmp.name
            if not step_path or not os.path.isfile(step_path):
                self._ok({"status": "error", "message": "STEP 文件不存在"})
                return

            # 只走 GEOUNED 通道；失败抛 StepConversionError，真实原因回传给前端
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "error", "message": "需要 FreeCAD 才能导入 STEP"})
                return

            result_path = run_step_converter(
                "geouned", step_path, material, density, settings, freecad_bin)
            deck = MCNPOutputParser.parse(result_path, post_settings=settings)
            if not deck:
                self._ok({"status": "error", "message": "GEOUNED 输出无法解析"})
                return

            self._ok({"status": "ok", "deck": geometry_deck_response(
                deck.surfaces, deck.tr_cards, deck.cells)})
        except StepConversionError as e:
            self._ok({"status": "error", "message": str(e)})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── 导出 STEP（通过 FreeCAD CSG 生成真实几何）──
    def _handle_export_step(self):
        try:
            import os, base64
            from step_importer import StepImporter
            from freecad_preview import FreeCADEngine

            data = self._read_body()
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", [])
            tr_text = data.get("tr_cards", "")

            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"status": "error", "message": "需要 FreeCAD"})
                return

            # 解析曲面（共享 parse_surfaces）
            surfs = parse_surfaces(surf_text)

            # 解析栅元（共享 build_cells_data；导出需几何可解析，剔除 ast=None；
            # 真空栅元不导出为实体——它们只参与 #n 补集解析，不进入 STEP。
            # 项14 边界：STEP 导出保持 include_void=False 不动，仅 3D 预览改 True）
            cells_data = [c for c in build_cells_data(cell_list, include_void=False)
                          if c["ast"] is not None]

            if not surfs or not cells_data:
                self._ok({"status": "error", "message": "没有可导出的栅元"})
                return

            # 解析 TR 卡（共享 parse_tr_cards）
            tr_cards = parse_tr_cards(tr_text)

            # 与 3D 预览同一条路线：build_geometry(fmt="step", single_file=True)
            # bound 用与预览一致的默认值(500)，避免巨大空盒导致几何不一致
            engine = FreeCADEngine(freecad_bin)
            result_map = engine.build_geometry(surfs, cells_data, tr_cards,
                                               bound=500, fmt="step", single_file=True)
            content = b''
            if result_map:
                step_file = list(result_map.values())[0]
                if os.path.isfile(step_file) and os.path.getsize(step_file) > 500:
                    with open(step_file, "rb") as f: content = f.read()
            engine.cleanup()
            if not content:
                self._ok({"status": "error", "message": "STEP 生成失败"})
                return
            b64 = base64.b64encode(content).decode()
            self._ok({"file": "mcnp_export.step", "data": b64, "message": "STEP 文件已导出"})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── MCNP 检测 ──
    def _handle_preview_3d(self):
        """3D 预览：解析曲面/栅元/TR → FreeCAD CSG → STL（同 deck 指纹缓存命中免 FreeCAD）"""
        global _STL_SESSION
        try:
            import tempfile, re, base64, shutil
            data = self._read_body()
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", [])
            tr_text = data.get("tr_cards", "")

            # 0. 指纹缓存：同 deck 命中免 FreeCAD 子进程（二次打开 ≤1s）
            fp = _PREVIEW_CACHE.fingerprint(surf_text, cell_list, tr_text)
            # TD-20（t5）：把「查缓存 → 清旧会话 → 建新会话」整组纳入请求级锁，
            # 防并发 preview-3d 互删对方刚生成的 STL 会话目录。
            with _preview_lock():
                cached = _PREVIEW_CACHE.get(fp)
            if cached is not None:
                with _preview_lock():
                    prev_dir = _STL_SESSION.get("dir")
                    if prev_dir and prev_dir != cached["dir"]:
                        _clear_stl_session()  # 清上一会话（与命中缓存目录不同时）
                    # 缓存目录作为本会话 STL 源（供 serve-file/截面复用）
                    _STL_SESSION = {"dir": cached["dir"], "cells": cached["cells"]}
                    # deck 快照（GQ/SQ 解析截面用）：缓存不存 deck，从请求重建
                    # 注意：本处是 preview-3d 缓存命中分支的截面 deck 快照，并非 STEP 导出。
                    # 项14 后与主路径一致 include_void=True（void 也参与截面），避免缓存
                    # 命中/未命中路径截面行为不一致（第一/二次打开 GQ/SQ void 栅元）。
                    try:
                        surfs_c = parse_surfaces(surf_text)
                        cells_c = build_cells_data(cell_list, include_void=True)
                        if surfs_c and cells_c:
                            _STL_SESSION["deck"] = _deck_snapshot(
                                surfs_c, cells_c, parse_tr_cards(tr_text))
                    except Exception:
                        pass
                stl_files = {}
                stl_data = {}
                for num, info in cached["cells"].items():
                    p = info.get("path")
                    if p and os.path.isfile(p):
                        with open(p, "rb") as _f:
                            stl_data[str(num)] = base64.b64encode(_f.read()).decode()
                        stl_files[str(num)] = p
                self._ok({"stl_files": stl_files, "stl_data": stl_data,
                          "freecad": cached.get("freecad"), "count": len(stl_data)})
                return

            # 1. 检测 FreeCAD
            StepImporter = _import_app("step_importer").StepImporter
            freecad_bin = StepImporter.detect_freecad()
            if not freecad_bin:
                self._ok({"stl_files": {}, "message": "未检测到 FreeCAD，请安装后重试"})
                return

            # 2. 解析曲面（共享 parse_surfaces）
            surfs = parse_surfaces(surf_text)
            if not surfs:
                self._ok({"stl_files": {}, "message": "未解析到有效曲面"})
                return

            # 3. 解析 TR 卡（共享 parse_tr_cards）
            tr_cards = parse_tr_cards(tr_text)

            # 4. 构建栅元（共享 build_cells_data；ast 解析失败的不渲染但保留）
            # 项14（2026-08-24 用户反馈）：真空栅元（材料 0）也产出 STL 参与 3D 预览，
            # include_void=True 不再跳过 void。已知风险：巨型边界 void（如 so 1000）
            # 的 STL 会撑大包围盒，可能把前端相机拉远导致模型缩成针尖——相机适配属
            # 前端项（本批另一 agent 处理），后端本批只保证 void STL 出得来。
            # 格阵 cell（fill_grid）与 render:false 仍跳过（见 build_cells_data 内部过滤）。
            cells_data = build_cells_data(cell_list, include_void=True)
            if not cells_data:
                self._ok({"stl_files": {}, "message": "没有可预览的栅元"})
                return

            # 5. FreeCAD CSG → STL
            from freecad_preview import FreeCADEngine
            engine = FreeCADEngine(freecad_bin)
            result = engine.build_geometry(surfs, cells_data, tr_cards, fmt="stl")

            # STL 复制到会话专用目录（engine 析构会删它自己的临时目录，必须复制走）
            session_dir = tempfile.mkdtemp(prefix="mcnp_stl_session_")
            stl_files = {}
            stl_data = {}
            # TD-20（t5）：清旧会话 + 建新会话 + 登记缓存 = 不可分割的一组，整体持锁。
            with _preview_lock():
                _clear_stl_session()  # 覆盖上一轮预览
                _STL_SESSION = {"dir": session_dir, "cells": {},
                                "deck": _deck_snapshot(surfs, cells_data, tr_cards)}
                # 会话路径 → base64（先读源文件，engine.cleanup() 之前）
                for cd in cells_data:
                    num = cd.get("number")
                    if num in result and os.path.isfile(result[num]):
                        src = result[num]
                        dst = os.path.join(session_dir, f"cell_{num}.stl")
                        try:
                            shutil.copy2(src, dst)
                            with open(src, "rb") as _f:
                                stl_data[str(num)] = base64.b64encode(_f.read()).decode()
                        except OSError:
                            continue
                        stl_files[str(num)] = dst
                        _STL_SESSION["cells"][num] = {
                            "material": cd.get("material", "0"),
                            "path": dst,
                        }
                # 存入指纹缓存：会话 STL 拷入缓存自有目录，clear-stl 删除会话目录不影响缓存
                _PREVIEW_CACHE.put(fp, {"dir": session_dir, "cells": _STL_SESSION["cells"],
                                        "freecad": freecad_bin})
            engine.cleanup()  # 引擎临时目录可删，会话目录已独立
            self._ok({"stl_files": stl_files, "stl_data": stl_data, "freecad": freecad_bin,
                      "count": len(stl_data),
                      "skipped_cells": getattr(engine, "skipped_cells", [])})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _handle_serve_file(self):
        """服务 STL 文件供前端加载"""
        import os, urllib.parse
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        file_path = params.get("path", [None])[0]
        if not file_path or not os.path.exists(file_path):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(file_path)))
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def _handle_cross_section(self):
        """平面截面：从 3D 预览保留的 STL 会话切（numpy），不再调 FreeCAD CSG。

        前端传 cellNums（勾选且非真空的栅元号）+ plane；真空/未勾选栅元的
        STL 不参与。无会话时提示先做 3D 预览。
        """
        try:
            cross_section_from_stl = _import_app("stl_cross_section").cross_section_from_stl
            data = self._read_body()
            cell_nums = data.get("cellNums") or []
            plane = data.get("plane") or {"A": 0, "B": 0, "C": 1, "D": 0}
            A = float(plane.get("A", 0)); B = float(plane.get("B", 0))
            C = float(plane.get("C", 0)); D = float(plane.get("D", 0))

            if not _STL_SESSION.get("dir") or not _STL_SESSION.get("cells"):
                self._ok({"slices": [], "message": "请先生成 3D 预览（STL 会话为空）"})
                return

            # TD-20（t5）：会话快照一次性取走（持锁），后续切面计算不持锁——避免与预览/清空
            # 请求互相阻塞，也避免"取会话中途被 clear-stl 换掉"。
            with _preview_lock():
                session_cells = dict(_STL_SESSION.get("cells") or {})
                deck = _STL_SESSION.get("deck") or {}

            # GQ/SQ 栅元走解析切片（精确轮廓，不依赖 STL 网格分辨率）；
            # deck 快照由 preview-3d 写入会话，缺失时回退 STL 切。
            deck_surfs = {}
            for s in deck.get("surfaces", []):
                try:
                    deck_surfs[int(s["number"])] = s
                except (KeyError, TypeError, ValueError):
                    continue
            deck_cells = {}
            for c in deck.get("cells", []):
                try:
                    deck_cells[int(c["number"])] = c
                except (KeyError, TypeError, ValueError):
                    continue
            deck_tr = deck.get("tr_cards", {})

            slices = []
            for num in cell_nums:
                num = int(num)
                info = session_cells.get(num)
                if not info:
                    continue
                material = info.get("material", "0")
                if str(material).split()[0] == "0":
                    continue  # 真空 STL 不参与截面

                ast = (deck_cells.get(num) or {}).get("ast")
                use_analytic = False
                if ast:
                    try:
                        from voxel_csg import _ast_surf_nums
                        use_analytic = any(
                            str(deck_surfs.get(n, {}).get("type", "")).upper()
                            in ("GQ", "SQ")
                            for n in _ast_surf_nums(ast)
                        )
                    except Exception:
                        use_analytic = False

                polys = []
                if use_analytic:
                    try:
                        from analytic_slice import analytic_cross_section
                        polys = analytic_cross_section(
                            ast, deck_surfs, deck_tr,
                            {"A": A, "B": B, "C": C, "D": D}, bound=500.0)
                    except Exception:
                        polys = []
                if not polys:
                    # 非 GQ/SQ 或解析失败：回退 STL 切（原行为）
                    path = info.get("path")
                    if path and os.path.isfile(path):
                        polys = cross_section_from_stl(path, A, B, C, D)
                if polys:
                    slices.append({"number": num, "material": material, "polygons": polys})
            self._ok({"slices": slices, "count": len(slices)})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    def _handle_clear_stl(self):
        """关 3D 预览窗口 / 主界面清空时调用：删除 STL 会话目录。TD-20（t5）：持预览锁。"""
        try:
            with _preview_lock():
                _clear_stl_session()
            self._ok({"status": "ok"})
        except Exception as e:
            self._err(str(e))

    def _handle_mcnp_detect(self):
        try:
            exe = _find_mcnp_exe()
            label = "MCNP6"
            if exe and "5" in os.path.basename(exe).lower(): label = "MCNP5"
            self._ok({"found": bool(exe), "exe": exe, "label": label if exe else "MCNP?"})
        except Exception as e:
            self._ok({"found": False, "exe": "", "label": "MCNP?", "error": str(e)})

    # ── FreeCAD 检测（统一走 freecad_locator seam）──

    def _handle_set_freecad_path(self):
        """保存用户手动指定的 FreeCAD 路径（校验存在且为 freecad.exe/freecadcmd.exe）"""
        try:
            data = self._read_body() or {}
            p = (data.get("path") or "").strip().strip('"')
            if not p or not os.path.isfile(p):
                self._ok({"status": "error", "message": "文件不存在"})
                return
            if os.path.basename(p).lower() not in ("freecad.exe", "freecadcmd.exe"):
                self._ok({"status": "error", "message": "请选择 FreeCAD.exe 或 FreeCADCmd.exe"})
                return
            from freecad_locator import save
            save(p)  # config.json + QSettings 双写
            self._ok({"status": "ok", "path": p})
        except Exception as e:
            self._ok({"status": "error", "message": str(e)})

    def _handle_choose_freecad_path(self):
        """弹出系统原生文件选择窗口选 FreeCAD.exe（取消返回 cancelled）"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                path = filedialog.askopenfilename(
                    title="选择 FreeCAD.exe",
                    filetypes=[("FreeCAD", "*.exe"), ("所有文件", "*.*")],
                )
            finally:
                root.destroy()
            if not path:
                self._ok({"path": "", "cancelled": True})
                return
            self._ok({"path": path, "cancelled": False})
        except Exception as e:
            self._ok({"path": "", "cancelled": True, "error": str(e)})

    def _handle_check_freecad(self):
        """重新定位 FreeCAD（清缓存后完整搜索），返回 {found, path}"""
        try:
            from freecad_locator import reset_cache, locate
            reset_cache()
            p = locate()
            self._ok({"found": bool(p), "path": p or ""})
        except Exception as e:
            self._ok({"found": False, "path": "", "error": str(e)})

    # ── INP 预校验 ──
    def _handle_validate_inp(self):
        try:
            data = self._read_body()
            from generator.parsers.validator import validate_inp_text
            errors = validate_inp_text(data.get("inp", ""))
            self._ok({"valid": len(errors) == 0, "errors": errors})
        except Exception as e:
            self._err(str(e))

    # ── 格阵曲面预检测（阶段2 LatticeEditDialog 失焦校验）──
    def _handle_validate_lattice_surfaces(self):
        """校验格阵栅元的曲面表达式是否构成合法格元（lat=1 六面体 / lat=2 六棱柱）。

        ok=false 为正常校验结果（不构成格元盒），HTTP 仍 200 返回统一信封。
        """
        try:
            lattice = _import_app("lattice")
            data = self._read_body() or {}
            ok, msg = lattice.validate_lattice_surfaces(
                data.get("surface_expr", ""),
                str(data.get("lat", "")),
                data.get("surfaces_text", ""),
            )
            self._ok({"ok": ok, "msg": msg})
        except Exception as e:
            self._err(str(e))

    # ── 格元范围解析（阶段3 lattice-extent）──
    def _handle_lattice_extent(self):
        """解析格元曲面表达式 → 物理范围（供 pitch/裁剪盒推导）。

        入参 {surface_expr, lat, surfaces_text} → {ok, extent|null, msg}。
        extent = {x_min,x_max,y_min,y_max,z_min,z_max}，z 无界字段为 null。
        """
        try:
            lattice = _import_app("lattice")
            data = self._read_body() or {}
            extent = lattice.lattice_cell_extent(
                data.get("surface_expr", ""),
                str(data.get("lat", "")),
                data.get("surfaces_text", ""),
            )
            if extent is None:
                self._ok({"ok": False, "extent": None,
                          "msg": "无法解析格元范围（需合法 lat=1/2 格元曲面表达式 + 曲面卡定义）"})
            else:
                self._ok({"ok": True, "extent": extent, "msg": ""})
        except Exception as e:
            self._err(str(e))

    # ── universe 覆盖完整性检测（格阵编辑器涂色提示）──
    def _handle_validate_universe_coverage(self):
        """判定 universe `U` 的栅元几何是否完整覆盖格元盒（红框预防）。

        入参 {surfaces, cells, tr_cards, lat, surface_expr, universe}：
          - surfaces / cells / tr_cards：与 preview-lattice 同源（cell 判别联合）。
          - lat / surface_expr：当前格阵格元盒的 lat 与曲面表达式。
          - universe：待检测的 universe 号。
        响应 {status, ...} 见 coverage_check.universe_coverage（kind/covered/
        uncoveredFraction/sampleCount/detailViable/unsupportedCells/message）。
        覆盖判定：格元盒内采样，逐点判定是否落在 universe 任一（叶）栅元内。
        无 FreeCAD 依赖，纯 stdlib+numpy + pymcnp AST。
        """
        try:
            lattice = _import_app("lattice")
            coverage = _import_app("coverage_check")
            data = self._read_body() or {}
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", []) or []
            tr_text = data.get("tr_cards", "")
            lat = str(data.get("lat", ""))
            surface_expr = str(data.get("surface_expr", "") or "")
            universe_u = str(data.get("universe", "") or "").strip()
            if not universe_u:
                self._ok({"status": "ok", "kind": "empty", "covered": False,
                          "uncoveredFraction": 1.0, "sampleCount": 0,
                          "detailViable": False, "unsupportedCells": 0,
                          "message": "未指定 universe 号"})
                return

            # 1. 格元盒范围（无法解析 → detailViable=False，不误判）
            box = lattice.lattice_cell_extent(surface_expr, lat, surf_text)

            # 2. 收集 universe 的叶栅元（跳过 graveyard 与 fill/fill_grid 装配容器），
            #    解析 surface_expr → pymcnp Geometry AST → JSON（覆盖检测消费格式）。
            from freecad_preview import parenthesize_unions, resolve_cell_complements
            from pymcnp.types.Geometry import Geometry
            uni_cells = []
            has_lattice_cell = False
            for c in cell_list:
                if not isinstance(c, dict) or c.get("kind") == "raw":
                    continue
                cell = c.get("cell") if c.get("kind") == "cell" and isinstance(c.get("cell"), dict) else c
                if _cell_u(c) != universe_u:
                    continue
                if _imp_any_zero(cell):
                    continue  # graveyard 不参与
                if _cell_fill_grid(c):
                    fg = lattice.FillGrid.from_json(_cell_fill_grid(c))
                    if fg is not None and fg.kind == "lattice":
                        has_lattice_cell = True
                    continue  # fill 装配容器不产实体几何
                if _cell_fill(c):
                    continue
                expr = str(cell.get("surface_expr", "") or "").strip()
                if not expr:
                    continue
                uni_cells.append((expr, cell))
            if has_lattice_cell:
                # 嵌套格阵 universe：覆盖性由子层格阵整体保证，不在此判定（不误报）。
                self._ok({"status": "ok", "kind": "lattice", "covered": False,
                          "uncoveredFraction": 0.0, "sampleCount": 0,
                          "detailViable": False, "unsupportedCells": 0,
                          "message": f"U={universe_u} 为嵌套格阵，覆盖由子层保证"})
                return
            if not uni_cells:
                self._ok({"status": "ok", "kind": "empty", "covered": False,
                          "uncoveredFraction": 1.0, "sampleCount": 0,
                          "detailViable": False, "unsupportedCells": 0,
                          "message": f"U={universe_u} 尚无栅元定义，无法判定覆盖"})
                return

            # 3. 构造 AST JSON（含 #n 补集展开）+ surfaces_by_num + tr_cards
            all_number_expr = {}
            for expr, cell in uni_cells:
                num = cell.get("number") or 0
                all_number_expr[num] = expr
            cells_by_num = {}
            for num, expr in all_number_expr.items():
                try:
                    ast = Geometry.from_mcnp(parenthesize_unions(expr))
                    cells_by_num[num] = ast.ast
                except Exception:
                    cells_by_num[num] = None
            ast_jsons = []
            for num, expr in all_number_expr.items():
                ref = cells_by_num.get(num)
                if ref is None:
                    continue
                resolved = resolve_cell_complements(ref, cells_by_num)
                try:
                    from freecad_preview import _geometry_ast_to_json
                    ast_jsons.append(_geometry_ast_to_json(resolved))
                except Exception:
                    continue
            if not ast_jsons:
                self._ok({"status": "ok", "kind": "leaf", "covered": False,
                          "uncoveredFraction": 1.0, "sampleCount": 0,
                          "detailViable": False, "unsupportedCells": 0,
                          "message": f"U={universe_u} 全部栅元几何无法解析"})
                return
            surfs = parse_surfaces(surf_text)
            from freecad_preview import _pymcnp_surf_to_dict
            surfaces_by_num = {int(s.number): _pymcnp_surf_to_dict(s)
                               for s in surfs}
            tr_cards = parse_tr_cards(tr_text)
            result = coverage.universe_coverage(
                box, ast_jsons, surfaces_by_num, tr_cards)
            result = dict(result)
            result.setdefault("message", "")
            if result.get("kind") == "leaf":
                result["message"] = (result["message"] or ""
                                     or f"U={universe_u} 覆盖判定")
            self._ok({"status": "ok", **result})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── 源粒子演示抽样（TODO #6 SDEF 源粒子可视化）──
    def _handle_source_demo_sample(self):
        """SDEF 源粒子抽样（source-demo-visualization 契约 §3）。

        入参 {sdefFields, sdefDistributions, surfaces, cells, trCards, nParticles?}。
        响应 {status, particles, energyRange, bounds} 或 {status, error}。
        CEL/SUR 几何判定复用本文件 parse_surfaces / Geometry.from_mcnp /
        resolve_cell_complements / voxel_csg 构造 field 函数，再交 source_sampler 抽样。
        """
        try:
            data = self._read_body() or {}
            sdef_fields = data.get("sdefFields") or {}
            distributions = data.get("sdefDistributions") or []
            n_particles = int(data.get("nParticles") or 500)
            surf_text = str(data.get("surfaces") or "")
            cells = data.get("cells") or []
            tr_text = str(data.get("trCards") or "")
            geometry = self._prepare_source_geometry(surf_text, cells, tr_text)
            from app.generator.source_sampler import sample_source
            result = sample_source(sdef_fields, distributions, geometry,
                                   n_particles=n_particles)
            # 几何解析若有失败，随响应带出（前端可提示），避免"静默无几何"
            errs = geometry.get("geometryErrors") or []
            if errs and isinstance(result, dict):
                result["geometryWarnings"] = errs
            self._ok(result)
        except Exception as e:
            self._err(str(e))

    def _prepare_source_geometry(self, surf_text, cells, tr_text):
        """CEL/SUR 抽样所需几何：{cells:{num:{field,aabb}}, surfaces:{num:{type,params,field}}}。

        field 为 voxel_csg 隐式求值函数（cell → 布尔场；surface → 标量场），
        #n 补集经 resolve_cell_complements 展开；宏体由 voxel_csg.surface_fn 支持。
        """
        import app.voxel_csg as vc
        from freecad_preview import (parenthesize_unions, resolve_cell_complements,
                                     _pymcnp_surf_to_dict, _geometry_ast_to_json)
        from pymcnp.types.Geometry import Geometry

        surfs = parse_surfaces(surf_text)
        tr_cards = parse_tr_cards(tr_text)
        surfaces = {}
        _source_geometry_errors: list[str] = []
        for s in surfs:
            try:
                d = _pymcnp_surf_to_dict(s)
                typ = (d.get("type") or "").upper()
                params = d.get("params") or []
                tr_data = vc._surface_tr(d, tr_cards)
                # ⚠ `vc._surface_transform(tr_data)` 只吃 **TR 数据本身**（1 参）。
                # 旧写法误传 (surface_dict, tr_cards) 两个参数 ⇒ TypeError ⇒ 被下面
                # except 吞掉 ⇒ surfaces 恒为空 ⇒ 任何 `SDEF SUR=` 面源都报
                # 「SUR=n 引用的曲面未定义」（2026-09-16 实测；CEL/体源不受影响）。
                field = vc.surface_fn(typ, params, vc._surface_transform(tr_data))
                # TR 的 rotate/origin 同时交给源抽样侧：面源位置/法线要在世界系里
                # （voxel_csg._surface_transform 是 world→local，这里存 local→world 所需量）
                surfaces[int(s.number)] = {
                    "type": typ, "params": params, "field": field,
                    "rotate": (tr_data or {}).get("rotate"),
                    "origin": (tr_data or {}).get("translate") or (0.0, 0.0, 0.0),
                }
            except Exception as e:
                _source_geometry_errors.append(f"曲面 {getattr(s, 'number', '?')}: {e}")
                continue

        cells_by_num = {}
        for c in cells:
            if not isinstance(c, dict):
                continue
            cell = c.get("cell") if c.get("kind") == "cell" and isinstance(c.get("cell"), dict) else c
            expr = str(cell.get("surface_expr") or "").strip()
            num = cell.get("number") or c.get("num")
            if not expr or num is None:
                continue
            try:
                ast = Geometry.from_mcnp(parenthesize_unions(expr))
                cells_by_num[int(num)] = ast.ast
            except Exception:
                cells_by_num[int(num)] = None

        cell_fields = {}
        cell_volumes: dict[int, float] = {}
        for num, ast in cells_by_num.items():
            if ast is None:
                continue
            try:
                resolved_node = resolve_cell_complements(ast, cells_by_num)
                # ⚠️ 必须转成 list 形式 AST：`vc._ast_surf_nums` / `vc.cell_aabb` /
                # `vc.eval_cell_field` 全部按 `["surf", n]` / `["intersect", a, b]`
                # `/ ["unary", a, "neg"]` 这种 list 结构索引（见 voxel_csg.py:401/516/574），
                # 而 `resolve_cell_complements` 返回的是 **pymcnp 节点对象**
                # （`_Paren`/`_Union`/`_Intersection`）—— 少了这一步就会抛
                # `TypeError: '_Paren' object is not subscriptable`，
                # 被下面的 except 静默吞掉 ⇒ `cells` 恒为空 ⇒ **CEL/SUR 源永远判定不了几何**
                # （2026-09-10 实测：pincell_mcnp.i 的 CEL=1 报"栅元不存在或无法判定"）。
                resolved = _geometry_ast_to_json(resolved_node)
                nums = vc._ast_surf_nums(resolved)
                fns = {}
                for sn in nums:
                    s = surfaces.get(sn)
                    if s is None:
                        raise ValueError(f"栅元 {num} 引用未定义曲面 {sn}")
                    fns[sn] = s["field"]

                def make_field(resolved_ast, fns_map):
                    def field(x, y, z):
                        return vc.eval_cell_field(resolved_ast, fns_map, x, y, z)
                    return field

                aabb = vc.cell_aabb(resolved, {sn: {"type": surfaces[sn]["type"],
                                                    "params": surfaces[sn]["params"]}
                                               for sn in nums}, 1e6)
                cell_fields[num] = {"field": make_field(resolved, fns), "aabb": aabb}
                # 栅元体积（C810 3-64 的 `SP V`：「概率与栅元体积成比例」要用）。
                # 分层 MC、同 seed 可复现；复用上面已算好的紧盒（aabb）。
                # 无界/退化/全不命中 → 不进表（SP V 命中时按 FATAL 报错，不塞假值）。
                vol = vc.cell_volume(resolved, fns, 1e6, aabb=aabb)
                if vol and vol > 0:
                    cell_volumes[num] = vol
            except Exception as e:
                # 不再静默：记录原因（此前 `continue` 让"几何全丢"看起来像"没有栅元"）
                _source_geometry_errors.append(f"栅元 {num}: {e}")
                continue

        return {"cells": cell_fields, "surfaces": surfaces,
                "geometryErrors": _source_geometry_errors,
                # SDEF TR=n（源变换）用：抽出的位置/方向要按该卡变换（C810 Table 3.3）
                "trCards": tr_cards,
                # SP V（按体积加权）用：{栅元号: 体积}（分层 MC 估计，可缺失）
                "cellVolumes": cell_volumes}

    # ── 格阵 3D 预览（阶段3 preview-lattice：universe 实例化 + 嵌套 fill 递归）──
    def _handle_preview_lattice(self):
        """格阵预览：每格阵 positions + 叶 universe 裁剪 STL + 嵌套 tree/leafInstances。

        入参 {surfaces, cells, tr_cards, latticeNum?, pitch?, height?}。
        响应 {lattices:[{num,lat,kind,dims,range,center,pitch,height,trclRotationDeg,
                        positions,universes}], leafInstances, tree, count, detailViable,
              limit}。嵌套 fill 递归在后端 compose_lattice_tree 完成。
        """
        try:
            lattice = _import_app("lattice")
            data = self._read_body() or {}
            surf_text = data.get("surfaces", "")
            cell_list = data.get("cells", []) or []
            tr_text = data.get("tr_cards", "")
            req_lattice = data.get("latticeNum")
            req_pitch = data.get("pitch")
            req_height = data.get("height")

            # 1. 按 u 分组 + 收集全部格阵 cell（含嵌套）
            sub_by_u = {}
            lattice_infos = []
            for c in cell_list:
                if not isinstance(c, dict) or c.get("kind") == "raw":
                    continue
                cell = (c.get("cell") if c.get("kind") == "cell"
                        and isinstance(c.get("cell"), dict) else c)
                if _imp_any_zero(cell):
                    continue  # 项15 规则5：graveyard（imp=0 外围）排除，与项14 口径一致
                u = str(cell.get("u", "") or "")
                fg_json = cell.get("fill_grid", "")
                fg = lattice.FillGrid.from_json(fg_json) if fg_json else None
                info = {
                    "cellNum": cell.get("number"),
                    "u": u,
                    "material": str(cell.get("material", "") or "0"),
                    "fill": str(cell.get("fill", "") or ""),
                    "fill_grid": fg,
                    "surface_expr": str(cell.get("surface_expr", "") or ""),
                    "lat": str(cell.get("lat", "") or ""),
                    "trcl": str(cell.get("trcl", "") or ""),
                }
                if fg is not None and fg.kind == "translated":
                    e = fg.cells[0] if fg.cells else None
                    if e is not None:
                        info["fill"] = str(e.u or "")
                        info["offset"] = (lattice._num(e.dx), lattice._num(e.dy),
                                          lattice._num(e.dz))
                sub_by_u.setdefault(u, []).append(info)
                if fg is not None and fg.kind == "lattice":
                    lattice_infos.append(info)

            if not lattice_infos:
                self._ok({"status": "ok", "lattices": [], "leafInstances": [], "tree": [],
                          "count": 0, "detailViable": True, "limit": "ok",
                          "message": "没有格阵栅元"})
                return
            if req_lattice is not None:
                lattice_infos = [info for info in lattice_infos
                                 if int(info["cellNum"]) == int(req_lattice)]
            if not lattice_infos:
                self._ok({"status": "ok", "lattices": [], "leafInstances": [], "tree": [],
                          "count": 0, "detailViable": True, "limit": "ok",
                          "message": "未找到指定格阵栅元"})
                return

            # 2. 解析 TRCL + 为 sub_by_u 中所有格阵 cell 解析 extent（pitch/height 覆盖）
            tr_cards = parse_tr_cards(tr_text)
            for _u, cells in sub_by_u.items():
                for info in cells:
                    fg = info.get("fill_grid")
                    if fg is None or fg.kind != "lattice":
                        continue
                    info["trcl_deg"] = _cell_trcl_deg(info.get("trcl", ""), tr_cards)
                    info["extent"] = _resolved_extent(
                        lattice.lattice_cell_extent(
                            info.get("surface_expr", ""), info.get("lat", ""), surf_text),
                        info.get("lat", ""), req_pitch, req_height,
                        surf_text, info, sub_by_u, lattice, cell_list)

            # 3. compose 嵌套树/叶/各格阵 positions（outer 的 trcl_deg 已在上面子循环里算好）。
            #    外层格阵 = 未被任何其他格阵 fill 引用的格阵（全堆芯：堆芯 u=100，而非组件 u=201，
            #    否则预览只展开一个组件、整个堆芯缺失）；用户指定 latticeNum 时用指定格阵。
            if req_lattice is None and len(lattice_infos) > 1:
                referenced = set()
                for _info in lattice_infos:
                    _fg = _info.get("fill_grid")
                    if _fg is not None:
                        for _e in _fg.cells:
                            referenced.add(str(_e.u or ""))
                outer = next(
                    (info for info in lattice_infos if str(info.get("u", "")) not in referenced),
                    lattice_infos[0])
            else:
                outer = lattice_infos[0]
            trcl_deg = outer.get("trcl_deg", 0.0)
            # 方法级容器 cell 几何边界：fill 展开时判断格元盒与容器 cell（BEAVRS 圆柱）
            # 是否相交。格元盒完全在容器 cell 外的格位（角位 u=30 无限水）不产实体——
            # 依据"格元与容器 cell 几何关系"，非"超壳结果"，换任何外壳皆正确。
            container_expr = _lattice_container_expr(
                cell_list, str(outer.get("u", "") or ""))
            container_bound = _lattice_container_bound(
                container_expr, surf_text, lattice)
            # 步骤1+2 LOD 预算（OWEN planRender 移植）：先 layers（每径向层/轴向段各一叶），
            # 若 count 超 DETAIL_MAX_INSTANCES 则切 disc（轴向已有折叠 + 每 pin 单盘）。
            # BEAVRS：layers(count=22.6万) 超限 → disc(count=5.6万) 进 InstancedMesh 实例化。
            axial = False
            composed = lattice.compose_lattice_tree(
                outer["fill_grid"], sub_by_u, outer["extent"], trcl_deg,
                lattice.MAX_LATTICE_DEPTH, lattice.MAX_TOTAL_INSTANCES,
                surf_text, axial=axial, detail="layers",
                container_bound=container_bound)
            if (composed.get("count", 0) > lattice.DETAIL_MAX_INSTANCES
                    and composed.get("status") != "too_many"):
                composed = lattice.compose_lattice_tree(
                    outer["fill_grid"], sub_by_u, outer["extent"], trcl_deg,
                    lattice.MAX_LATTICE_DEPTH, lattice.MAX_TOTAL_INSTANCES,
                    surf_text, axial=axial, detail="disc",
                    container_bound=container_bound)
            # 最外层容器 cell（fill 指向根格阵 universe 的空 cell，如 BEAVRS cell 343）
            # 的几何边界 → 供前端色块总览裁剪超外壳格位（17×17 方形格阵 vs 圆柱壳）。
            composed["outer_bound"] = _lattice_outer_bound(
                cell_list, str(outer.get("u", "") or ""), surf_text, lattice)
            limit = composed.pop("status", "ok")
            # 项13 api.yaml：响应恒带 cycle/chain。compose 的 status="cycle" 分支把
            # 循环链放在 `cycle` 键（与 api.yaml 的 `cycle: boolean` 命名冲突）→
            # 转换：cycle=true + chain=链；非 cycle → cycle=false + chain=[]。
            if limit == "cycle":
                composed["chain"] = composed.pop("cycle", [])
                composed["cycle"] = True
            else:
                composed["cycle"] = False
                composed["chain"] = []

            # 4. 每个格阵 → 直接引用叶 universe 的裁剪 STL。
            #    容器 cell（fill 指向根格阵 universe 的空 cell，BEAVRS 343）的几何约束
            #    （`-80 700 -730` = cz 内 + z 界）作为 STL 裁剪的一部分：STL = universe
            #    ∩ 格元盒 ∩ 容器cell —— 方法级，格元完全在容器外的（角位无限水）交集为空，
            #    不产生"圆柱外虚假水块"；换任何外壳皆正确。
            container_expr = _lattice_container_expr(
                cell_list, str(outer.get("u", "") or ""))
            for entry in composed.get("lattices", []):
                info = _find_lattice_cell_info_by_num(
                    entry.get("num"), lattice_infos, sub_by_u)
                fg = info.get("fill_grid")
                box = _clip_box_from_extent(entry.get("extent"))
                universes = {}
                if fg is not None:
                    seen = set()
                    for e in fg.cells:
                        u = str(e.u or "")
                        if u in ("0", "") or u in seen:
                            continue
                        seen.add(u)
                        if _universe_has_lattice(sub_by_u, u):
                            continue  # 嵌套子格阵由自己的 lattices 条目负责
                        pitch = entry.get("pitch", [1, 1, 1])
                        height = entry.get("height", 1.0)
                        stls = _build_one_universe(
                            surf_text, tr_text, cell_list, u, box,
                            entry.get("num"), pitch, height, lattice,
                            container_expr)
                        if stls:
                            universes[u] = stls
                entry["universes"] = universes

            # disc 降级：补建「叶 universe」(径向 pin) 的 STL。每格阵 fill_grid 引用的是
            # 「轴向列 universe」（如 BEAVRS u=116/124/131/…，cell 全带 fill=，被
            # _build_one_universe 的 if _cell_fill: continue 跳过 → 返回空）；但轴向折叠后
            # 叶 universe 是「径向 pin universe」（u=1/2/3/12/5/6，真实燃料棒/导向管/仪表管
            # 几何）。前端 disc 分支按叶 universe 查 universeStl[u][cellNum]，缺失时回退
            # BoxGeometry 占位方块 → 燃料棒显示成方块（"显示与理论出入大"根因）。这里按叶
            # universe（未建 STL 的径向 pin）用 pin 格元盒补建 STL 放进对应格阵，使
            # universeStl[leaf.u][leaf.cellNum] 命中真实 pin 几何。
            if composed.get("detail") == "disc":
                built = set()
                for _entry in composed.get("lattices", []) or []:
                    built.update(str(k) for k in (_entry.get("universes") or {}).keys())
                leaf_us = []
                for _leaf in composed.get("leafInstances", []) or []:
                    _u = str(_leaf.get("u") or "")
                    if _u and _u not in ("0", "") and _u not in built and _u not in leaf_us:
                        leaf_us.append(_u)
                if leaf_us:
                    pin_entry = next(
                        (_e for _e in (composed.get("lattices", []) or [])
                         if str(_e.get("num")) != str(outer.get("cellNum")) and _e.get("extent")),
                        None)
                    if pin_entry is not None:
                        pin_box = _clip_box_from_extent(pin_entry.get("extent"))
                        _pitch = pin_entry.get("pitch", [1, 1, 1])
                        _height = pin_entry.get("height", 1.0)
                        _univ = pin_entry.setdefault("universes", {})
                        for _u in leaf_us:
                            _st = _build_one_universe(
                                surf_text, tr_text, cell_list, _u, pin_box,
                                pin_entry.get("num"), _pitch, _height, lattice,
                                container_expr)
                            if _st:
                                _univ.setdefault(_u, {}).update(_st)

            # 超详细上限（将自动切色块总览）→ 裁掉叶/树，只留 lattices[].positions 供总览，
            # 避免 50 万叶+树节点几十 MB 响应把前端卡死（全堆芯 289×289 场景）。
            # disc 模式（步骤2）：每 pin 1 盘、每 universe 1 几何 —— 实例数已大降
            # （BEAVRS 50 万 → 5.6 万），允许 InstancedMesh 实例化，不再 2 万一刀切裁叶。
            # subPitch = 全部格阵的最小 pitch（OWEN placePin disc 用 min(subPitch*0.47, ...)
            # 定 disc 半径）。BEAVRS 根格阵 21.5（组件间距）但组件内 pin 间距 1.26——若前端
            # 误用根格阵 pitch（21.5）画 disc，半径 ≈5.05cm 远超 1.26cm 格位 → 圆柱互相穿插、
            # 超出外壳、乱面。必须用最小格距（subPitch=1.26）保证 disc 在格位内不重叠。
            # 但单格阵（如 U233 hex 卡只有 1 个 lat=2 格阵）时没有"更小的子格阵"，subPitch
            # 应取该格阵自己的 pitch（1.45034），而不是硬编码 BEAVRS 专属的 1.26。
            _subpitch = None
            for _lt in composed.get("lattices", []) or []:
                _pit = _lt.get("pitch") or []
                if len(_pit) >= 2 and _pit[0] > 0 and _pit[1] > 0:
                    _subpitch = min(_pit[0], _pit[1]) if _subpitch is None \
                        else min(_subpitch, _pit[0], _pit[1])
            if _subpitch is None:
                _subpitch = 1.26  # 无格阵兜底（防御）
            _fid = {
                "detail": "disc" if composed.get("detail") == "disc" else "layers",
                "axial": bool(composed.get("axial")),
                "estimate": composed.get("count", 0),
                "subPitch": _subpitch,
            }
            if composed.get("detail") == "disc":
                # disc 已折叠：只要 ≤ MAX_TOTAL_INSTANCES 就进详细实例化（InstancedMesh 吃 5.6 万）
                if composed.get("count", 0) > lattice.MAX_TOTAL_INSTANCES:
                    composed["leafInstances"] = []
                    composed["tree"] = []
                    composed["detailViable"] = False
                else:
                    composed["detailViable"] = True
            elif composed.get("count", 0) > lattice.DETAIL_MAX_INSTANCES:
                composed["leafInstances"] = []
                composed["tree"] = []
                composed["detailViable"] = False
            composed["fidelity"] = _fid

            self._ok({**composed, "limit": limit})
        except Exception as e:
            import traceback
            self._err(str(e) + " | " + traceback.format_exc())

    # ── ZAID 校验 ──
    def _handle_validate_zaid(self):
        from urllib.parse import parse_qs
        qs = parse_qs(urlparse(self.path).query)
        zaid = qs.get("zaid", [""])[0].strip()
        try:
            if not xsdir_db.loaded:
                env_path = os.environ.get("XSDIR", "") or os.environ.get("DATAPATH", "")
                if env_path and os.path.isfile(env_path):
                    xsdir_db.load(env_path)
                elif os.environ.get("DATAPATH", ""):
                    cand = os.path.join(os.environ["DATAPATH"], "xsdir")
                    if os.path.isfile(cand): xsdir_db.load(cand)
                else:
                    found = xsdir_db.find_xsdir()
                    if found: xsdir_db.load(found)
            in_db = xsdir_db.has_zaid(zaid) if xsdir_db.loaded else None
            self._ok({"zaid": zaid, "in_db": in_db, "loaded": xsdir_db.loaded})
        except Exception as e:
            self._err(str(e))

    # ── OUTP 解析 ──
    def _handle_parse_keff(self):
        """主动解析 mctal 的 keff 收敛序列（目录自动找 mctal* 文件）。"""
        try:
            import glob
            data = self._read_body() or {}
            path = str(data.get("path", "")).strip()
            if not path:
                self._err("缺少 mctal 文件路径或运行目录")
                return
            if os.path.isdir(path):
                candidates = sorted(glob.glob(os.path.join(path, "mctal*")))
                if not candidates:
                    self._err(f"目录中未找到 mctal 文件：{path}")
                    return
                mctal_path = candidates[0]
            else:
                mctal_path = path
            if not os.path.isfile(mctal_path):
                self._err(f"mctal 文件不存在：{mctal_path}")
                return
            parse_mctal = _import_app("mctal_parser").parse_mctal
            with open(mctal_path, "r", encoding="utf-8", errors="replace") as f:
                result = parse_mctal(f.read())
            keff = result.get("keff") or {}
            if not keff.get("mean"):
                self._err(f"未在 mctal 中解析到 keff 收敛序列：{mctal_path}")
                return
            self._ok({
                "status": "ok",
                "path": mctal_path,
                "keff": {
                    "cycles": keff.get("cycles", []),
                    "mean": keff.get("mean", []),
                    "std": keff.get("std", []),
                    "combined": keff.get("combined"),
                },
            })
        except Exception as e:
            self._err(str(e), hint="keff 解析失败，请确认 mctal 文件有效")

    def _handle_parse_outp(self):
        try:
            data = self._read_body()
            text = data.get("outp", "")

            # 优先用内置 pymcnp（正确入口：Outp.from_mcnp(text).to_dataframe()）。
            # 注意：pymcnp.Outp(...) 是构造函数（header, blocks），不是解析入口；
            # 旧代码误用导致该接口恒报错。pymcnp 只覆盖 MCNP6.2 系布局。
            try:
                import pymcnp

                result = pymcnp.Outp.from_mcnp(text)
                df_map = result.to_dataframe()
                if df_map:
                    tallies = {}
                    nps = None
                    for tnum, df in df_map.items():
                        rows = []
                        flux_sum = 0.0
                        for _, row in df.iterrows():
                            try:
                                flux_sum += float(row.get("counts"))
                            except (TypeError, ValueError):
                                pass
                            rows.append({
                                "energy": _fmt_num(row.get("bins")),
                                "flux": _fmt_num(row.get("counts")),
                                "error": _fmt_num(row.get("errors")),
                            })
                        nps = int(df["nps"].iloc[0]) if len(df) else None
                        ttype = str(df["type"].iloc[0]) if len(df) else ""
                        tm = re.match(r"^\s*(\d+)", ttype)
                        tallies[str(tnum)] = {
                            "type": int(tm.group(1)) if tm else 0,
                            "rows": rows,
                            "total": {
                                "energy": "total",
                                "flux": "" if not rows else f"{flux_sum:.6e}",
                                "error": "",
                            },
                        }
                    self._ok({"nps": nps or 0, "tallies": tallies, "warnings": [], "parser": "pymcnp"})
                    return
            except Exception:
                pass  # pymcnp 缺失或布局不兼容 → 走自研容错解析

            # 兜底：格式容错解析（MCNP6.1 紧凑布局等 pymcnp 未覆盖格式）
            from outp_parser import parse_outp

            tallies, nps, warnings = parse_outp(text)
            self._ok({"nps": nps or 0, "tallies": tallies, "warnings": warnings, "parser": "builtin"})
        except Exception as e:
            self._err(str(e))

    # ── xsdir 搜索 ──
    def _handle_xsdir_search(self):
        from urllib.parse import parse_qs
        qs = parse_qs(urlparse(self.path).query)
        q = qs.get("q", [""])[0].strip()
        try:
            if not xsdir_db.loaded:
                self._ok({"loaded": False, "results": []})
                return
            results = []
            q_lower = q.lower()
            for zaid in xsdir_db.zaids:
                if q_lower in zaid.lower():
                    results.append({"zaid": zaid})
                    if len(results) >= 50: break
            if not results:
                from xsdir_db import SYMBOL_TO_Z
                z = SYMBOL_TO_Z.get(q.capitalize())
                if z:
                    for zaid in xsdir_db.zaids:
                        if zaid.startswith(str(z).zfill(3)) or zaid.startswith(str(z)):
                            results.append({"zaid": zaid})
                            if len(results) >= 50: break
            self._ok({"loaded": True, "results": results})
        except Exception as e:
            self._ok({"loaded": False, "results": [], "error": str(e)})

    def log_message(self, fmt, *args):
        if args:
            print(f"[API] {' '.join(str(a) for a in args)}")
        else:
            print(f"[API] {fmt}")


def main():
    server = HTTPServer(("0.0.0.0", PORT), MCNPHandler)
    print(f"[API] MCNP API 服务启动 → http://localhost:{PORT}/api/generate")
    print(f"   Python 后端路径: {APP_DIR}")
    # 后台预热 pymcnp 曲面解析：启动即返回、不阻塞服务，
    # 让第一个曲面请求（preview-3d/export-step/cross-section）不再吃一次 2s 的冷水 import。
    try:
        def _warm():
            try:
                _surf_classes()
            except Exception:
                pass  # 预热失败不影响功能，首次请求时仍会按需 import
        threading.Thread(target=_warm, daemon=True, name="pymcnp-prewarm").start()
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.server_close()


if __name__ == "__main__":
    main()
