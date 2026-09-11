#!/usr/bin/env python3
"""MCNP 后端启动器 — 打包后由前端 sidecar 拉起，启动完整的 HTTP 后端 (api_server.py)

所有功能（导入/解析/生成/3D/截面/材料校验）都走 http://localhost:5001，
因此 sidecar 的作用是让 api_server 常驻监听 5001，前端关闭时随之终止。

argv 分派：
  --meshtal-worker  以 meshtal 子进程 worker 模式运行（stdin JSON → stdout JSON，
                     完成后退出，不启动 HTTP 服务器）。打包版 sys.executable 传参
                     即走此入口（api_server 的 _meshtal_worker_cmd()），避免带脚本
                     路径再启第二个 5001（端口冲突挂起）。
  --ptrac-worker    以 ptrac 子进程 worker 模式运行（stdin JSON → stdout JSON，
                     照 --meshtal-worker，契约 ptrac-visualization.md v2 §3）。
  --mcp-http        以 inputcard-mcp over HTTP 模式运行（本机环回 8100 /mcp，
                     AI 接入唯一入口，主程序关闭时随之终止）。
"""
import sys, os

_here = os.path.dirname(os.path.abspath(__file__))

# 候选路径：源码开发（gui/backend） / PyInstaller 打包后（_internal 布局）
for _p in [
    _here,                                        # api_server.py 所在
    os.path.join(_here, "..", "..", "app"),       # 源码: 输入卡生成器源码/app（generator/models）
    os.path.join(_here, "app"),                   # PyInstaller: backend 与 app 平级
]:
    _p = os.path.normpath(_p)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# 打包环境：_MEIPASS/app（meshtal 数据落盘目录）也加入路径，供 top-level meshtal import
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _mei_app = os.path.join(sys._MEIPASS, "app")
    if os.path.isdir(_mei_app) and _mei_app not in sys.path:
        sys.path.insert(0, _mei_app)


if __name__ == "__main__":
    if "--meshtal-worker" in sys.argv:
        # meshtal 子进程 worker：stdin JSON → stdout JSON，完成后退出，不启 HTTP
        from meshtal._meshtal_worker import main as _meshtal_worker_main
        _meshtal_worker_main()
        sys.exit(0)

    if "--ptrac-worker" in sys.argv:
        # ptrac 子进程 worker：stdin JSON → stdout JSON，完成后退出，不启 HTTP
        from ptrac._ptrac_worker import main as _ptrac_worker_main
        _ptrac_worker_main()
        sys.exit(0)

    if "--mcp-http" in sys.argv:
        # inputcard-mcp over HTTP（本程序 AI 接入唯一入口）：uvicorn /mcp + /workspace；
        # AI 用 http://127.0.0.1:8100/mcp 连接，可读/改程序当前工作区
        from inputcard_mcp.server import main as _mcp_main
        _mcp_main()
        sys.exit(0)

    if "--mcp-server" in sys.argv:
        # 已废弃（stdio 接入已于 2026-09 移除，统一走 --mcp-http 8100）。
        # 显式拦截：绝不 fallthrough 到 api_server.main()，否则会静默起第二个 5001 后端。
        print("--mcp-server 已废弃：AI 接入统一使用 --mcp-http（本机 http://127.0.0.1:8100/mcp）。",
              file=sys.stderr)
        sys.exit(2)

    import api_server  # noqa: E402
    api_server.main()
