@echo off
cd /d "%~dp0"
echo MCNP API 服务启动中...
python api_server.py
if errorlevel 1 (
    echo 启动失败，请确认 Python 已安装并添加到 PATH
    pause
)
