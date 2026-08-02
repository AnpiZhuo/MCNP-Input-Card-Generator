#!/usr/bin/env python3
"""MCNP 后端启动器 — 打包后由前端 sidecar 拉起，启动完整的 HTTP 后端 (api_server.py)

所有功能（导入/解析/生成/3D/截面/材料校验）都走 http://localhost:5001，
因此 sidecar 的作用是让 api_server 常驻监听 5001，前端关闭时随之终止。
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

import api_server  # noqa: E402

if __name__ == "__main__":
    api_server.main()
