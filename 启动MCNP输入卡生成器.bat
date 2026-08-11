@echo off
chcp 65001 >nul
title MCNP 输入卡生成器 — 启动中
echo ========================================
echo   MCNP 输入卡生成器 — 一键启动
echo ========================================
echo.

:: ─── 后端 ───
set PYTHON=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\python3.exe
set BACKEND_DIR=D:\MCNP\输入卡生成器源码\gui\backend
set FRONTEND_DIR=D:\MCNP\输入卡生成器源码\gui

echo [1/3] 启动 Python 后端...
start "MCNP 后端" "%PYTHON%" "%BACKEND_DIR%\api_server.py"
timeout /t 2 /nobreak >nul

echo [2/3] 启动 Vite 前端...
start "MCNP 前端" cmd /c "cd /d "%FRONTEND_DIR%" && npx vite --port 1420 --host"
timeout /t 3 /nobreak >nul

echo [3/3] 打开浏览器...
start http://localhost:1420

echo.
echo ========================================
echo   启动完成！
echo   前端: http://localhost:1420
echo   后端: http://localhost:5001/api/generate
echo.
echo   关闭前先关这两个窗口
echo ========================================
pause
