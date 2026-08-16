"""PTRAC 解析子进程 worker（契约 ptrac-visualization.md v2 §2）。

协议：stdin JSON → stdout JSON（{"status":"ok", …} / {"status":"error","message":…}）。

- mode="parse"：读文件 → parse_ptrac → 回传 header/tracks/world_box/stats/truncated。
  大文件在子进程解析，不阻塞 5001。

模块顶**只 import stdlib**（numpy/pymcnp 惰性按需），照 _meshtal_worker 范式。
"""
import json
import os
import sys
import traceback

# 将 app/ 与项目根加入 sys.path（子进程独立，需自带路径引导）
_HERE = os.path.dirname(os.path.abspath(__file__))      # app/ptrac
_APP = os.path.dirname(_HERE)                            # app
_ROOT = os.path.dirname(_APP)                            # 项目根
for _p in (_APP, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _mode_parse(payload: dict) -> dict:
    from ptrac.ptrac_parser import parse_ptrac, PTRACFormatError

    path = payload.get("path", "")
    max_tracks = int(payload.get("maxTracks", 500))
    max_points = int(payload.get("maxPoints", 200000))
    if not path or not os.path.isfile(path):
        return {"status": "error", "message": "文件不存在或路径为空",
                "hint": "请确认是 MCNP 生成的 ASCII PTRAC 文件（FILE=ASC）"}

    result = parse_ptrac(path, max_tracks=max_tracks, max_points=max_points)
    result["status"] = "ok"
    return result


def _run(payload: dict) -> dict:
    """分派 parse；任何异常 → {"status":"error","message":…}（不裸抛）。"""
    try:
        mode = payload.get("mode")
        if mode == "parse":
            return _mode_parse(payload)
        return {"status": "error", "message": f"未知 mode: {mode}"}
    except Exception:
        return {"status": "error", "message": traceback.format_exc()}


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stdout.write(json.dumps({"status": "error", "message": f"stdin JSON 解析失败: {e}"}))
        sys.stdout.flush()
        return
    result = _run(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
