@echo off
chcp 65001 >nul
title MCNP 输入卡生成器 — 启动中
echo ========================================
echo   MCNP 输入卡生成器 — 一键启动
echo ========================================
echo.

:: ─── 环境 ───
set PYTHON=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\python3.exe
set BACKEND_DIR=D:\MCNP\输入卡生成器源码\gui\backend
set FRONTEND_DIR=D:\MCNP\输入卡生成器源码\gui

:: ─── 后端 ───
netstat -ano | findstr ":5001" | findstr "LISTENING" >nul
if %errorlevel%==0 (
  echo [!] 5001 端口已有后端在运行（可能是打包版），直接复用，不再重复启动。
) else (
  echo [1/3] 启动 Python 后端...
  start "MCNP 后端" "%PYTHON%" "%BACKEND_DIR%\api_server.py"
  timeout /t 2 /nobreak >nul
)

:: ─── 前端（每次自动构建，避免旧产物；不再使用 vite dev，vite dev 在此机器上会挂起） ───
echo [2/3] 构建前端（约 3 秒）...
pushd "%FRONTEND_DIR%"
call node node_modules\vite\bin\vite.js build >nul 2>nul
popd
netstat -ano | findstr ":1420" | findstr "LISTENING" >nul
if %errorlevel%==0 (
  echo [!] 1420 端口已有前端服务在运行，直接复用。
) else (
  start "MCNP 前端" "%PYTHON%" -m http.server 1420 --directory "%FRONTEND_DIR%\dist"
  timeout /t 2 /nobreak >nul
)

:: ─── 打开浏览器 ───
echo [3/3] 打开浏览器...
start http://localhost:1420

echo.
echo ========================================
echo   启动完成！
echo   前端: http://localhost:1420
echo   后端: http://localhost:5001
echo.
echo   3D 体积结果在浏览器模式下的查看方式：
echo   输出页 - 解析 MESHTAL - 3D 体积可视化，
echo   然后手动访问 http://localhost:1420/#/volume
echo.
echo   关闭前先关「MCNP 后端」「MCNP 前端」两个窗口
echo ========================================
pause
