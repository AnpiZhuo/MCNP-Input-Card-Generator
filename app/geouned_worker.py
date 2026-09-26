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

    # 可选的实体预分解（基本页「启用实体预分解」）。失败一律回退原文件。
    step_path, notes = _maybe_predecompose(step_path, output_dir, data.get("cut") or {})

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
    geo.load_step_file(
        filename=step_path,
        skip_solids=load_step.get("skip_solids", []),
        spline_surfaces=load_step.get("spline_surfaces", "stop"),
    )
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
    # SystemExit: geouned 对 spline 曲面 / 空实体会裸调 exit()
    try:
        main()
    except SystemExit as e:
        print(json.dumps({"status": "error",
                          "message": f"GEOUNED 终止: {e}"}))
        sys.exit(1)
    except Exception as e:
        import traceback
        print(json.dumps({"status": "error",
                          "message": f"{e}\n{traceback.format_exc()}"}))
        sys.exit(1)
