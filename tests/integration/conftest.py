# -*- coding: utf-8 -*-
"""集成测试共享的**后端子进程 fixture**（单一实现 + 防"打到别人后端"的假绿）。

## 历史问题（2026-09-20 实证，见 `PROJECT_MEMORY.md` §6 / S9.6）

四个集成测试文件（`test_api_contract` / `test_api_expand_formula` / `test_meshtal_api` /
`test_ptrac_api`）**各自复制了一份** `backend_base_url`，都把端口**写死 5001**，而用户机器上
打包安装版（`D:\\MCNP\\MCNP输入卡生成器\\python.exe`）**常年占着 5001** ⇒

1. `ThreadingHTTPServer` 默认 `SO_REUSEADDR`，Windows 下两个进程可同时"监听"同一端口
   ⇒ 请求被**分流/劫持**（§6「5001 端口劫持」条目早有记载）；
2. 更糟的是原来探活那一步是 `socket.create_connection(("127.0.0.1", 5001))` ——
   **连上的是别人的后端也照样 `break`**，于是这约 60 条"真实 HTTP 往返"用例
   **跑在装机版的旧代码上还报绿**（新端点才暴露：旧后端没这端点 ⇒ 404/500）。

## 现在的口径（三条，缺一条就会假绿）

1. **挑空闲端口**（`bind(("0.0.0.0", 0))`）并把 `--port N` 传给子进程
   ⇒ 那个端口上只可能是**我们的**后端；
2. 就绪后**核对监听者 PID == 子进程 PID**（`netstat -ano`），不符即 `fail`（不是 skip）；
3. 子进程若在就绪前退出：带上它的 stderr 尾巴 `skip`（缺 pymcnp 等依赖的机器仍可跑），
   但若该端口上**另有监听者**，那是被劫持 ⇒ `fail`。

`--port` 只服务测试/多实例；打包版与前端一律 5001（`gui/src/utils/api.ts` 硬编码），
且**刻意不引入环境变量**——免得用户机器上一个遗留 env 把后端挪走、前端却还在找 5001。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
API_SERVER = PROJECT_DIR / "gui" / "backend" / "api_server.py"

# 首次拉起要 import pymcnp/pyvista 等重依赖并预热曲面类（实测冷启 3~8 s，留足余量）
READY_TIMEOUT = 30.0
POLL_INTERVAL = 0.3


def _free_port() -> int:
    """要一个当前没人监听的端口（与后端同口径绑 0.0.0.0）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return int(s.getsockname()[1])


def _listening_pids(port: int) -> set[int] | None:
    """``netstat -ano`` 里 LISTENING 在该端口上的 PID 集合；探针本身不可用时返回 None。

    返回 None 与"空集合"含义不同：前者是"核不了"（调用方据此降级为"子进程存活"判据），
    后者是"**没人**在听"（那就说明我们的子进程根本没起来）。
    """
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             timeout=30, errors="replace").stdout
    except Exception:
        return None
    if not out or ":" not in out:
        return None
    pids: set[int] = set()
    for line in out.splitlines():
        parts = line.split()
        # 形如：  TCP    127.0.0.1:5001    0.0.0.0:0    LISTENING    12345
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            if parts[1].rsplit(":", 1)[-1] == str(port):
                try:
                    pids.add(int(parts[4]))
                except ValueError:
                    pass
    return pids


def _read_tail(path: Path, lines: int = 12) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(读不到 stderr)"
    return "\n".join(text[-lines:]) or "(空)"


@pytest.fixture(scope="session")
def port_probe():
    """把端口探针暴露给用例（免得跨文件 import conftest）。"""
    return SimpleNamespace(free_port=_free_port, listening_pids=_listening_pids)


@pytest.fixture(scope="module")
def backend_proc(tmp_path_factory):
    """起源码后端子进程（**空闲端口**），就绪并核对归属后交出 ``dict``。

    键：``proc`` / ``pid`` / ``port`` / ``base`` / ``log`` / ``owners``
    （``owners`` 为 None 表示 netstat 探针不可用、归属未核对）。
    """
    port = _free_port()
    log_dir = tmp_path_factory.mktemp("backend")
    log = log_dir / "stderr.log"
    with open(log, "w", encoding="utf-8", errors="replace") as ferr:
        proc = subprocess.Popen(
            [sys.executable, str(API_SERVER), "--port", str(port)],
            cwd=str(PROJECT_DIR), stdout=subprocess.DEVNULL, stderr=ferr,
        )
    base = f"http://127.0.0.1:{port}"
    try:
        ready = False
        deadline = time.time() + READY_TIMEOUT
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    ready = True
                    break
            except OSError:
                time.sleep(POLL_INTERVAL)

        owners = _listening_pids(port)
        if proc.poll() is not None:
            reason = (f"后端子进程提前退出 (code={proc.returncode})，跳过 HTTP 往返；"
                      f"stderr 尾巴：\n{_read_tail(log)}")
            if owners:
                pytest.fail(
                    f"后端子进程已退出，但端口 {port} 上仍有监听者 {sorted(owners)} —— "
                    f"该端口并非我们独占（被劫持？）。{reason}")
            pytest.skip(reason)
        assert ready, (f"后端 {READY_TIMEOUT:.0f}s 内未在端口 {port} 上就绪；"
                       f"stderr 尾巴：\n{_read_tail(log)}")
        assert owners is None or proc.pid in owners, (
            f"防假绿闸门：端口 {port} 的监听者 PID = {sorted(owners or [])}，"
            f"不含我们起的子进程 PID {proc.pid} —— 这批 HTTP 用例会打到**别的后端**"
            f"（2026-09-20 前就是这么在装机版旧代码上假绿的）。")
        yield {"proc": proc, "pid": proc.pid, "port": port, "base": base,
               "log": str(log), "owners": owners}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


@pytest.fixture(scope="module")
def backend_base_url(backend_proc) -> str:
    """源码后端的 base URL（空闲端口；四个集成文件的同名 fixture 已收拢到此处）。"""
    return backend_proc["base"]
