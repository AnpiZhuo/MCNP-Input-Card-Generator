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
import sys
import json


def main():
    data = json.load(sys.stdin)

    step_path = data["step_path"]
    output_dir = data["output_dir"]
    geometry_name = data.get("geometry_name", "csg")
    geouned_path = data.get("geouned_path", "D:/MCNP/GEOUNED")
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
