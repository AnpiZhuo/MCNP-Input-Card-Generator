# -*- coding: utf-8 -*-
"""回归：inputcard-mcp 默认不把 mcp/依赖的 INFO 刷到 stderr（否则 stdio 客户端不消费 stderr 时
Windows 管道缓冲满 → server 阻塞 → MCP 卡死，见 diagnostics: stderr-hang）。"""
import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for _p in (ROOT, os.path.join(ROOT, "app"), os.path.join(ROOT, "gui", "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from inputcard_mcp import server  # noqa: E402


def _mcp_level():
    return logging.getLogger("mcp").getEffectiveLevel()


def test_default_logging_silent():
    # 默认（未设环境变量）→ mcp/anyio 等 logger 不低于 WARNING，不刷 INFO
    assert _mcp_level() >= logging.WARNING
    assert logging.getLogger("anyio").getEffectiveLevel() >= logging.WARNING


def test_env_override_and_restore():
    # INPUTCARD_MCP_LOG=DEBUG → 放开（能查到 INFO，供排查）
    os.environ["INPUTCARD_MCP_LOG"] = "DEBUG"
    server._configure_logging()
    assert _mcp_level() == logging.DEBUG
    # 还原默认
    del os.environ["INPUTCARD_MCP_LOG"]
    server._configure_logging()
    assert _mcp_level() >= logging.WARNING


def test_bad_env_value_falls_back_to_warning():
    os.environ["INPUTCARD_MCP_LOG"] = "not-a-level"
    server._configure_logging()
    assert _mcp_level() >= logging.WARNING
    del os.environ["INPUTCARD_MCP_LOG"]
    server._configure_logging()
