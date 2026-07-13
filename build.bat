@echo off
chcp 65001 >nul
title MCNP 输入卡生成器 - 打包

echo ========================================
echo   MCNP 输入卡生成器 v1.4.1 - 打包脚本
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3
    pause
    exit /b 1
)

:: 目标目录
set OUTDIR=D:\MCNP\MCNP输入卡生成器

:: 安装依赖
echo [1/4] 安装依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

:: 清理旧的构建
echo [2/4] 清理旧构建...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

:: PyInstaller 打包（使用 spec 文件）
echo [3/4] 打包 EXE...
pyinstaller --noconfirm --distpath "dist" "MCNP输入卡生成器.spec"

if %errorlevel% neq 0 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

:: 复制到目标目录
echo [4/4] 复制到 %OUTDIR%...
if exist "%OUTDIR%" rmdir /s /q "%OUTDIR%"
xcopy /e /i /y "dist\MCNP输入卡生成器" "%OUTDIR%"

if %errorlevel% neq 0 (
    echo [错误] 复制失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo   ^✓ 打包成功！
echo   输出: %OUTDIR%\MCNP输入卡生成器.exe
echo ========================================
pause
