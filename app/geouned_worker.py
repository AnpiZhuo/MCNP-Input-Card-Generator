"""
GEOUNED STEP→MCNP 转换 worker。

在 FreeCAD 自带 Python 下运行（geouned 依赖 FreeCAD 模块），
stdin 收 JSON 配置，stdout 回 JSON 结果（与 _freecad_csg_worker 同一协议）。

协议:
    stdin : {"step_path","output_dir","geometry_name","title",
             "geouned_path", "settings":{...}}
    stdout: {"status":"ok","mcnp_path":...} 或 {"status":"error","message":...}
"""
import os
import re
import sys
import json


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


def main():
    data = json.load(sys.stdin)

    step_path = data["step_path"]
    output_dir = data["output_dir"]
    geometry_name = data.get("geometry_name", "csg")
    geouned_path = data.get("geouned_path", "") or os.environ.get("GEOUNED_PATH", "")
    settings = data.get("settings", {})

    os.makedirs(output_dir, exist_ok=True)
    os.chdir(output_dir)

    # geouned 包所在父目录（打包后为 _internal/vendor；开发环境为安装目录）
    if geouned_path not in sys.path:
        sys.path.insert(0, geouned_path)

    import geouned
    from geouned import CadToCsg, Settings as GeoSettings

    geo_settings = GeoSettings(
        outPath=output_dir,
        matFile="",
        voidGen=bool(settings.get("voidGen", True)),
        debug=False,
        compSolids=bool(settings.get("compSolids", False)),
        simplify=settings.get("simplify", "no"),
        exportSolids=None,
        minVoidSize=float(settings.get("minVoidSize", 200.0)),  # mm
        maxSurf=int(settings.get("maxSurf", 50)),
        maxBracket=int(settings.get("maxBracket", 30)),
        voidMat=[],
        voidExclude=[],
        startCell=int(settings.get("startCell", 1)),
        startSurf=int(settings.get("startSurf", 1)),
        sort_enclosure=bool(settings.get("sort_enclosure", False)),
    )

    geo = CadToCsg(settings=geo_settings)
    # spline 曲面默认"停止"；geouned 内部对 spline 会裸调 exit()，由外层兜住
    geo.load_step_file(filename=step_path, spline_surfaces="stop")
    geo.start()
    geo.export_csg(
        title=data.get("title", "Converted with GEOUNED"),
        geometryName=geometry_name,
        outFormat=("mcnp",),
        volSDEF=False,
        volCARD=True,
        UCARD=None,
        dummyMat=False,
        cellCommentFile=False,
        cellSummaryFile=True,
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

    print(json.dumps({"status": "ok", "mcnp_path": mcnp_output}))


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
