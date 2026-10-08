"""
GEOUNED STEP→MCNP 转换 worker。

在 FreeCAD 自带 Python 下运行（geouned 依赖 FreeCAD 模块），
stdin 收 JSON 配置，stdout 回 JSON 结果（与 _freecad_csg_worker 同一协议）。

协议:
    stdin : {"step_path","output_dir","geometry_name","title","geouned_path",
             "cut":{"enabled":bool,"degree":str},   # 实体预分解（流水线开关，非 GEOUNED 参数）
             "settings":{...},      # geouned.Settings 的关键字参数（可选键）
             "options":{...},       # geouned.Options 的关键字参数（可选键）
             "tolerances":{...},    # geouned.Tolerances 的关键字参数（可选键）
             "load_step":{"spline_surfaces","skip_solids"},
             "export":{"volSDEF","UCARD","dummyMat","cellCommentFile","cellSummaryFile"}}
    stdout: {"status":"ok","mcnp_path":...,"warnings":[...]} 或 {"status":"error","message":...}

    五个参数区段都是可选的：**某个键不出现 = 用 GEOUNED 自己的默认值**，worker 不在
    Python 侧重写任何默认值。

    `cut` 是流水线开关（先按面数上限切分实体，再交给 GEOUNED），**任何失败都回退原
    文件、绝不中断导入**，但原因会经 `warnings` 一路传到界面上。

    **唯一的例外是 `load_step.spline_surfaces`**：缺省时本 worker 按「跳过该实体」
    （`remove`）走，而不是 GEOUNED 的默认档「停止转换」（它直接 `exit()`，用户只看到
    一句"GEOUNED 终止: None"）。见 `app/spline_skip.py` 顶部：跳过 + 如实报告哪个实体
    被跳、什么曲面、多少个面。
"""
import os
import re
import sys
import json

# 本文件有两种被加载的方式：**当脚本跑**（生产：FreeCAD 的 python.exe 直接执行它，
# sys.path[0] 就是 app/）与**当模块 import**（单测）。兄弟模块里的 `import
# adaptive_decompose` 是绝对导入，只有第一种方式天然成立 —— 这里补上，让两种都成立。
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)


_NUM_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _fmt_num(match, prec: int = 3) -> str:
    """数值 token：浮点 → prec 位小数；整数（曲面号/栅元引用）保持原样。"""
    tok = match.group(0)
    if re.fullmatch(r"[+-]?\d+", tok):
        return tok
    try:
        v = float(tok)
    except ValueError:
        return tok
    return format(v, f".{prec}f")


def _format_numbers(text: str) -> str:
    """把整个 MCNP 文件里的科学计数法数字换成普通数字（跳过注释行与 $ 注释）。"""
    out = []
    in_gq = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped[0].lower() == "c" or stripped[0] == "$":
            out.append(line)
            continue
        # 新卡行（列 0 起、以数字开头）判断是否 GQ/SQ 卡；GQ 卡跨多行，续行保持 in_gq
        if not line[:1].isspace():
            in_gq = bool(re.match(r"^\s*\d+\s+(GQ|SQ)\b", line, re.I))
        body, sep, comment = line.partition("$")
        if in_gq:
            out.append(line)  # GQ/SQ 系数是几何定义，保留原始精度
        else:
            out.append(_NUM_RE.sub(lambda m: _fmt_num(m, 3), body) + (sep + comment if sep else ""))
    return "\n".join(out)


def _assign_default_material(mcnp_path: str, default_mat: int = 1) -> None:
    """GEOUNED 不给实体赋材料（STEP 无材料时全部 material=0），
    app 会把 material=0 当真空跳过 → 无法 3D 预览。
    这里把 SOLID 段（VOID CELLS 之前）栅元的材料 0 改成默认材料 1；
    真空/墓区段不动，已赋材料的也不动。"""
    with open(mcnp_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    out = []
    in_solid = True
    for line in text.splitlines():
        if in_solid and re.search(r"VOID\s*CELLS|GRAVEYARD", line, re.IGNORECASE):
            in_solid = False
        if in_solid:
            m = re.match(r"^(\s*\d+\s+)0(\s+\S.*)$", line)
            if m:
                # 材料 0(真空) 无需密度；改成材料后必须补密度，否则第一个曲面号会被解析器当密度
                line = m.group(1) + str(default_mat) + " -1.0" + m.group(2)
        out.append(line)
    with open(mcnp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def _bbox_of(step_path: str):
    """用 FreeCAD 读 STEP 的包围盒尺寸（mm）。读不了返回 None。

    ⚠️ `import FreeCAD` 必须在前：FreeCAD 的 python.exe 裸跑 `import Part` 会
    ModuleNotFoundError（2026-09-24 实测）。漏了它本函数**永远返回 None**，
    自证判据就退化成一个恒真的空检查 —— 看起来"有保护"，实际什么都没拦。
    """
    try:
        import FreeCAD  # noqa: F401  —— 必须早于 Part（见 docstring）
        import Part
        s = Part.Shape()
        s.read(step_path)
        bb = s.BoundBox
        return (bb.XLength, bb.YLength, bb.ZLength) if bb.isValid() else None
    except Exception:
        return None


def _cut_selfcheck(original: str, decomposed: str):
    """分解自证：比对分解前后的包围盒。返回 (是否通过, 不通过的原因)。

    拦的是"导出悄悄写坏/写空"——读出来尺寸不对就宁可退回原文件。
    （单位不符那一类静默错误在本路径不存在：FreeCAD 直接读同一个 STEP、在同一个内存
    坐标系里切，没有 `units` 声明这一环。）

    判据的不对称是**刻意**的：
      · 原文件都读不出来 → 没有可比对象，放行（FreeCAD 读取失败不该阻断导入）；
      · 原文件读得出来、分解产物读不出来 → 产物坏了，**必须回退**。
    两边一起 None 就放行的话，这个检查会退化成恒真 —— 那正是它上一版的样子。
    """
    import adaptive_decompose
    a = _bbox_of(original)
    if a is None:
        return True, ""
    b = _bbox_of(decomposed)
    if b is None:
        return False, "分解产物读不出来（文件可能写坏了），已回退用原文件"
    if adaptive_decompose.boxes_match(a, b):
        return True, ""
    return False, (f"分解前后包围盒不一致（原 {a} vs 分解后 {b}），已回退用原文件")


def _maybe_predecompose(step_path: str, output_dir: str, cut: dict):
    """按需先做实体预分解。返回 (真正要转换的 step_path, 提示列表)。

    **铁律：任何失败都回退原文件，绝不中断导入**；但提示必须能传到界面上，
    否则用户会以为"开了没用"。
    """
    notes = []
    if not cut.get("enabled"):
        return step_path, notes
    try:
        import adaptive_decompose
    except Exception as e:
        return step_path, [f"实体预分解已跳过：模块导入失败（{e}）"]

    # 本进程就跑在 FreeCAD 的 python.exe 里 ⇒ 它就是能切的那个解释器，
    # 不需要再"发现"一次（外部程序时代的路径发现坑随之消失）。
    python_exe = sys.executable or ""
    reason = adaptive_decompose.unavailable_reason(python_exe)
    if reason:
        return step_path, [f"实体预分解已跳过：{reason}"]

    try:
        result = adaptive_decompose.decompose(step_path, output_dir,
                                              face_limit=cut.get("degree"),
                                              python_exe=python_exe)
    except Exception as e:
        return step_path, [f"实体预分解已跳过：{e}"]

    ok, why = _cut_selfcheck(step_path, result.path)
    if not ok:
        return step_path, [f"实体预分解已跳过：{why}"]
    if not 0.9999 <= result.volume_ratio <= 1.0001:
        return step_path, [f"实体预分解已跳过：分解前后体积比 {result.volume_ratio:.6f} "
                           f"偏离 1，结果不可信"]
    notes.append(result.summary())
    return result.path, notes


def _orient_step_into_mcnp(step_path: str, output_dir: str, spec, notes: list) -> str:
    """按「CAD 上轴/方位」约定把 STEP 的几何**旋进 MCNP 系（Z 朝上）**，返回要转换的路径。

    为什么需要（2026-10-08 用户实测："STEP 数字对得上，但模型躺倒、轴跟预览不一致"）：
    STEP 文件**不带**上轴信息，差别来自源软件默认坐标系（Y 朝上：SolidWorks/Inventor 类；
    Z 朝上：FreeCAD/UG/CATIA 类）。本程序与 MCNP 都是 Z 朝上 ⇒ 导入时按约定转一次，
    导出时按逆变换转回去（见 app/cad_orientation.py），两侧互为逆、往返自洽。

    为什么另写一个 STEP 而**不**去动 GEOUNED：GEOUNED 装进 FreeCAD、是编译过的包，
    不该碰它内部；本文件已有同样的先例（实体预分解也是写临时 STEP 再交给 GEOUNED）。
    读/写方式与 adaptive_cut_freecad.py 一致（FreeCAD python 里的 Part.Shape().read）。

    任何失败都**回退原文件**并留一条提示，绝不中断导入（与实体预分解同一纪律）。
    """
    try:
        from cad_orientation import describe, freecad_steps, parse, translation_for
    except ImportError:
        from app.cad_orientation import describe, freecad_steps, parse, translation_for

    steps = freecad_steps(spec, "cad2mcnp")
    org = parse(spec)["origin"]
    if not steps and org == "keep":
        return step_path
    try:
        import FreeCAD
        import Part

        shape = Part.Shape()
        shape.read(step_path)
        solids = list(getattr(shape, "Solids", []) or [])
        if not solids:
            notes.append("上轴约定：旋转跳过（STEP 里没读到实体），按原样转换")
            return step_path
        out = []
        for sol in solids:
            s = sol.copy()
            for axis, deg in steps:
                s.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(*axis), deg)
            out.append(s)
        # 原点口径：在**目标 MCNP 系（Z 朝上）**里算 ⇒ "坐在底面上" = 坐在 MCNP 的 z=0 上。
        # （up="Y" 时 CAD 的 Y=0 平面经旋转后正是 MCNP 的 z=0，两种说法一致。）
        if org != "keep":
            compound = Part.makeCompound(out)
            bb = compound.BoundBox
            shift = translation_for(((bb.XMin, bb.YMin, bb.ZMin),
                                     (bb.XMax, bb.YMax, bb.ZMax)), org, "Z")
            for s in out:
                s.translate(FreeCAD.Vector(*[float(v) for v in shift]))
        dst = os.path.join(output_dir, "step_oriented_for_mcnp.step")
        Part.makeCompound(out).exportStep(dst)
        notes.append(describe(spec, "cad2mcnp"))
        return dst
    except Exception as e:  # noqa: BLE001 —— 一律回退原文件，但原因要留痕
        notes.append(f"上轴/原点约定处理失败，按原样转换：{type(e).__name__}: {e}")
        return step_path


def _break_tangent_sphere_cylinder(step_path: str, output_dir: str, notes: list) -> str:
    """破除「同轴同半径球面/圆柱面」的退化相切（GEOUNED 会因此丢定界面）。

    根因见 app/tangent_fix.py 顶部：用户文件里**只有**含这种相切的两个实体转错
    （体积大 7.8 / 8.1 倍 + 互相重叠），把球面沿径向外移 0.1% 后体积回到实体值、重叠清零。

    纪律：
      * 只在"半径相等且同轴"时动手 —— 没有这种对的模型**原样返回、绝不重写 STEP**
        （避免 OCCT 往返对本来正确的几何引入副作用）；
      * 每处修复都有体积闸门（>0.5% 放弃），并在 `notes` 里如实回报；
      * 任何失败都回退原文件、不中断导入。
    """
    try:
        try:
            from tangent_fix import describe_actions, dedupe_spheres, is_safe, is_tangent_pair, shift_amount
        except ImportError:
            from app.tangent_fix import (describe_actions, dedupe_spheres, is_safe,
                                         is_tangent_pair, shift_amount)
        import FreeCAD
        import Part

        shape = Part.Shape()
        shape.read(step_path)
        solids = list(getattr(shape, "Solids", []) or [])
        if not solids:
            return step_path

        out, actions, changed = [], [], False
        for idx, sol in enumerate(solids, 1):
            spheres, cyls = [], []
            for f in sol.Faces:
                surf = f.Surface
                cn = surf.__class__.__name__
                if "Sphere" in cn:
                    spheres.append((surf.Center, float(surf.Radius)))
                elif "Cylinder" in cn:
                    ax = getattr(surf, "Axis", None)
                    pt = getattr(surf, "Center", None)
                    if ax is not None and pt is not None:
                        cyls.append((ax, pt, float(surf.Radius)))
            pairs = []
            for c, rs in spheres:
                for ax, pt, rc in cyls:
                    n = FreeCAD.Vector(ax.x, ax.y, ax.z)
                    if n.Length < 1e-12:
                        continue
                    n.normalize()
                    v = FreeCAD.Vector(c.x - pt.x, c.y - pt.y, c.z - pt.z)
                    dist = (v - n * v.dot(n)).Length
                    if is_tangent_pair(rs, rc, dist):
                        pairs.append(([c.x, c.y, c.z], rs, rc))
            if not pairs:
                out.append(sol)
                continue
            new = sol
            for center, rs, rc in dedupe_spheres(pairs):
                try:
                    c = FreeCAD.Vector(*center)
                    sliver = Part.makeSphere(rs, c).cut(Part.makeSphere(rs * (1.0 - 0.001), c))
                    bb = sol.BoundBox
                    clip = Part.makeBox(bb.XLength, bb.YLength, bb.ZLength,
                                        FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMin))
                    cand = new.fuse(sliver.common(clip))
                    dvol = abs(cand.Volume - new.Volume) / max(new.Volume, 1e-9)
                    if bool(cand.isValid()) and is_safe(dvol):
                        new = cand
                        changed = True
                        actions.append({"solid": idx, "sphereR": rs, "cylR": rc,
                                        "shift": shift_amount(rs), "dvol": dvol})
                except Exception as e:  # noqa: BLE001 —— 单处失败不影响其它实体
                    notes.append(f"相切退化修复：实体 {idx} 单处失败，已跳过（{type(e).__name__}: {e}）")
            out.append(new)

        if not changed:
            return step_path
        dst = os.path.join(output_dir, "step_tangent_fixed.step")
        Part.makeCompound(out).exportStep(dst)
        notes.append(describe_actions(actions))
        return dst
    except Exception as e:  # noqa: BLE001 —— 一律回退原文件，但原因要留痕
        notes.append(f"相切退化修复失败，按原样转换：{type(e).__name__}: {e}")
        return step_path


def _load_shape(step_path: str):
    """读 STEP，返回 (Part 模块, shape, solids 列表)。

    ⚠️ `import FreeCAD` 必须早于 `import Part`（与 `_bbox_of` 同一条实测纪律：
    FreeCAD 的 python.exe 裸跑 `import Part` 会 ModuleNotFoundError）。
    """
    import FreeCAD  # noqa: F401  —— 必须早于 Part
    import Part
    shape = Part.Shape()
    shape.read(step_path)
    return Part, shape, list(getattr(shape, "Solids", []) or [])


def _spline_kinds_per_solid(step_path: str):
    """每个实体的**样条面类型名**（空列表 = 该实体没有样条面）；读不出来返回 None。

    判据与 GEOUNED `loadfile/load_functions.py::spline()` **逐字相同** —— 那才是
    "GEOUNED 会跳过谁"的唯一权威（本函数只负责读，不另立判据）：

        isinstance(f.Surface, (Part.BSplineSurface, Part.SurfaceOfRevolution,
                               Part.SurfaceOfExtrusion))

    报告与决策交给 `app/spline_skip.py`（纯逻辑，可离线单测）。
    """
    try:
        Part, _shape, solids = _load_shape(step_path)
    except Exception:  # noqa: BLE001 —— 读不出来不该阻断导入，调用方按"没检查"处理
        return None
    out = []
    for sol in solids:
        row = []
        for f in sol.Faces:
            surf = f.Surface
            if isinstance(surf, (Part.BSplineSurface, Part.SurfaceOfRevolution,
                                 Part.SurfaceOfExtrusion)):
                row.append(type(surf).__name__)
        out.append(row)
    return out


def _strip_spline_solids(step_path: str, output_dir: str, indices, notes: list):
    """把含样条面的实体**物理**从 STEP 里删掉；返回 (新文件路径, 被删的原序号列表)。

    什么时候才走到这里：GEOUNED 的 `remove` 档对普通实体够用，但它的 enclosure 路径
    **不看档位**地对"无形状实体"直接 `exit()`（core.py:335-338）—— 当 enclosure 命名
    约定（`enclosureNN_PP_`）恰好落在一个样条实体上时，导入仍会终止。用户要的是
    "跳过而不是终止"，所以这里自己动手删：删完再交给 GEOUNED，它眼里根本没有样条实体，
    也就无从 exit。

    代价（必须如实回报）：实体序号会前移 ⇒ 调用方要重映射 `skip_solids`
    （`spline_skip.remap_skip_solids`），报告里也写明前移。
    """
    Part, _shape, solids = _load_shape(step_path)
    drop = {int(i) for i in indices}
    keep = [s for i, s in enumerate(solids) if i not in drop]
    if not keep:
        raise RuntimeError(f"剔除含样条面的实体（{sorted(drop)}）之后，STEP 里没有剩下任何实体")
    dst = os.path.join(output_dir, "step_without_spline.step")
    Part.makeCompound(keep).exportStep(dst)
    removed = sorted(drop)
    notes.append("样条实体在 enclosure 路径上仍会让 GEOUNED 强制退出，已直接从 STEP 里移除实体 "
                 + "、".join(str(i) for i in removed) + "（其后实体的序号相应前移）")
    return dst, removed


class _UserFacing(RuntimeError):
    """**预期内**的失败，原因本身就是写给用户看的（例：样条档位 = 停止转换 / 全实体都是样条）。

    为什么要单独一类（2026-10-08 部署版冒烟实测）：`__main__` 的兜底会给任何异常后缀一整段
    traceback，而界面 alert 是**整段原样显示**的 ⇒ 用户会看到"RuntimeError: …"加一堆调用栈，
    真正该读的那句"把「样条曲面处理」改成「跳过该实体」即可继续"被淹掉。
    预期内的失败只回 message；真 bug 走 `Exception` 分支、保留 traceback（那条对排查有用）。
    """


class _StdoutTee:
    """把 GEOUNED 打到 stdout 的东西**同时**写到 stderr 与内存缓冲。

    为什么要改道：本进程的 stdout 是**协议通道**（结尾要写一行 JSON），而 GEOUNED
    会往 stdout 直接 print，例如 `load_step.py:67` 的
    "following solids have Spline surfaces:" —— 混进 JSON 里就是一句
    "GEOUNED 输出非 JSON"，把真实原因盖掉。
    为什么要留缓冲：GEOUNED 有时裸调 `exit()`（`core.py:337`），届时唯一能说明
    "它为什么退"的就是它自己打的那句话。
    """

    def __init__(self, real):
        self._real = real
        self.chunks: list = []

    def write(self, s):
        self.chunks.append(s)
        return self._real.write(s)

    def flush(self):
        return self._real.flush()

    def isatty(self) -> bool:
        return False

    def text(self) -> str:
        return "".join(self.chunks)

    def __getattr__(self, name):        # encoding / errors 等属性转发给真 stderr
        return getattr(self._real, name)


def main():
    data = json.load(sys.stdin)

    step_path = data["step_path"]
    output_dir = data["output_dir"]
    geometry_name = data.get("geometry_name", "csg")
    geouned_path = data.get("geouned_path", "") or os.environ.get("GEOUNED_PATH", "")

    # 五个参数区段（由 step_importer_geouned._map_app_settings_to_geouned 产出）。
    # **只对显式给出的键赋值**，缺什么就留什么空 → 走 GEOUNED 自己的默认值。
    # 不在这里重写默认值：将来 GEOUNED 升版改了默认值，本程序不会被钉死。
    settings = data.get("settings") or {}
    options = data.get("options") or {}
    tolerances = data.get("tolerances") or {}
    load_step = data.get("load_step") or {}
    export = data.get("export") or {}

    os.makedirs(output_dir, exist_ok=True)
    os.chdir(output_dir)

    # CAD 上轴/方位约定：**先**旋进 MCNP 系，后面所有步骤（含预分解）都在 MCNP 系里做。
    notes: list = []
    step_path = _orient_step_into_mcnp(step_path, output_dir,
                                       data.get("cad_orientation"), notes)

    # 相切退化修复（默认开，可用设置关掉）：破除"同轴同半径球面/圆柱面"，
    # 否则 GEOUNED 会丢定界面 ⇒ 栅元体积暴增并与邻居重叠（见 app/tangent_fix.py）。
    if data.get("tangent_fix", True):
        step_path = _break_tangent_sphere_cylinder(step_path, output_dir, notes)

    # 可选的实体预分解（基本页「启用实体预分解」）。失败一律回退原文件。
    step_path, cut_notes = _maybe_predecompose(step_path, output_dir, data.get("cut") or {})
    notes.extend(cut_notes)

    # ── 样条曲面：**跳过而不是终止**，并如实报告（用户指定；见 app/spline_skip.py）──
    # 扫描的是"接下来真要交给 GEOUNED 的那个文件"（预处理之后的），所以报告里的实体序号
    # 与 GEOUNED 的 skip_solids 是**同一口径**。
    try:
        import spline_skip
    except ImportError:
        from app import spline_skip

    policy = spline_skip.normalize_policy(load_step.get("spline_surfaces"))
    spline_report = spline_skip.scan(_spline_kinds_per_solid(step_path))
    if spline_report is None:
        notes.append("样条曲面检查已跳过：这个 STEP 读不出来（按原样交给 GEOUNED）")
    else:
        blocked = spline_skip.blocking_reason(spline_report, policy)
        if blocked:
            # 早失败：与其让 GEOUNED 裸 exit()（用户只看到"GEOUNED 终止: None"），
            # 不如在这里把"哪个实体、什么面、换哪一档能继续"一次说清。
            raise _UserFacing(blocked)
        notes.extend(spline_skip.describe(spline_report, policy))

    # geouned 包所在父目录（打包后为 _internal/vendor；开发环境为安装目录）
    if geouned_path not in sys.path:
        sys.path.insert(0, geouned_path)

    import geouned
    from geouned import CadToCsg, Settings as GeoSettings, Options, Tolerances

    geo_settings = GeoSettings(outPath=output_dir)
    for key, val in settings.items():
        setattr(geo_settings, key, val)      # GEOUNED 的 setter 会做严格类型检查

    geo = CadToCsg(
        settings=geo_settings,
        options=Options(**options),
        tolerances=Tolerances(**tolerances),
    )

    skip_solids = list(load_step.get("skip_solids") or [])
    # GEOUNED 期间把 stdout 改道（见 _StdoutTee）：它的 print 会污染本进程的 JSON 协议。
    real_stdout, tee = sys.stdout, _StdoutTee(sys.stderr)
    sys.stdout = tee
    try:
        try:
            geo.load_step_file(
                filename=step_path,
                skip_solids=skip_solids,
                spline_surfaces=policy,
            )
        except SystemExit:
            # 兜底：enclosure 里含样条实体时，GEOUNED **不看档位**地 exit()
            # （core.py:335-338）⇒ 自己把那些实体物理删掉再来一次。
            text = tee.text()
            if not (policy == "remove" and spline_report and spline_report.solids
                    and "spline" in text.lower()):
                raise _UserFacing(
                    "GEOUNED 在加载 STEP 阶段强制退出（无法继续）。它自己的输出："
                    + (text.strip()[-300:] or "（无）"))
            step_path, removed = _strip_spline_solids(step_path, output_dir,
                                                      spline_report.indices, notes)
            skip_solids, redundant = spline_skip.remap_skip_solids(skip_solids, removed)
            if redundant:
                notes.append("「跳过实体编号」里的 " + "、".join(str(i) for i in redundant)
                             + " 已在样条实体剔除中一并移除，无需再跳")
            try:
                geo.load_step_file(
                    filename=step_path,
                    skip_solids=skip_solids,
                    spline_surfaces="remove",
                )
            except SystemExit:
                raise _UserFacing(
                    "GEOUNED 在剔除含样条面的实体后仍然强制退出。它自己的输出："
                    + (tee.text().strip()[-300:] or "（无）"))
        geo.start()
        geo.export_csg(
            title=data.get("title", "Converted with GEOUNED"),
            geometryName=geometry_name,
            outFormat=("mcnp",),
            volCARD=True,                              # 本程序依赖 VOL 卡，不对外开放
            volSDEF=export.get("volSDEF", False),
            UCARD=export.get("UCARD"),                  # None = 不写宇宙卡
            dummyMat=export.get("dummyMat", False),
            cellCommentFile=export.get("cellCommentFile", False),
            cellSummaryFile=export.get("cellSummaryFile", True),
        )
    finally:
        sys.stdout = real_stdout

    mcnp_output = os.path.join(output_dir, f"{geometry_name}.mcnp")
    if not os.path.isfile(mcnp_output):
        raise RuntimeError(f"GEOUNED 未生成输出文件 {mcnp_output}")

    # 实体栅元默认赋材料（STEP 无材料时 GEOUNED 全为 0，会挡住 3D 预览）
    _assign_default_material(mcnp_output)
    # 科学计数法 → 干净数字（曲面/Vol/数据卡统一）
    with open(mcnp_output, encoding="utf-8", errors="replace") as f:
        _text = f.read()
    with open(mcnp_output, "w", encoding="utf-8") as f:
        f.write(_format_numbers(_text))

    # 提示（含"切割已生效/已跳过"）随结果回传，界面上必须可见 ——
    # 否则用户分不清"切割没生效"和"切割开了但看不出差别"。
    print(json.dumps({"status": "ok", "mcnp_path": mcnp_output, "warnings": notes}))


if __name__ == "__main__":
    # SystemExit: geouned 在若干分支里裸调 exit()（样条/enclosure/空实体）。
    # 样条那条路已经在 main() 里被**具体地**接管（跳过 + 报告），这里只是最后一道兜底。
    try:
        main()
    except _UserFacing as e:
        # 预期内的失败：只回原因，不缀 traceback（界面 alert 会整段给用户看）
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    except SystemExit as e:
        print(json.dumps({"status": "error",
                          "message": f"GEOUNED 终止: {e}"}))
        sys.exit(1)
    except Exception as e:
        import traceback
        print(json.dumps({"status": "error",
                          "message": f"{e}\n{traceback.format_exc()}"}))
        sys.exit(1)
