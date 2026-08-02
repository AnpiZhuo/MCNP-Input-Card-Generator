@echo off
chcp 65001 >nul
cd /d "D:/MCNP/输入卡生成器源码/gui"
echo === MCNP FreeCAD 3D 预览 ===
echo.
"D:\FreeCAD\FreeCAD_1.1.1-Windows-x86_64-py311\bin\python.exe" backend/generate_step.py --open
pause