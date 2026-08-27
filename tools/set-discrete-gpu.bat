@echo off
rem ============================================================
rem  Force discrete (high-performance) GPU for MCNP generator app.
rem  Double-click this file to run. (writes to HKCU, no admin needed)
rem  Optional args (can be put in a shortcut target):
rem    -AppExeOnly   only set the app exe, skip shared msedgewebview2.exe
rem                    (avoid affecting every other WebView2 program)
rem    -AppExe "C:\path\App.exe"   manually specify the app exe
rem ============================================================
chcp 65001 >nul
setlocal
set "DIR=%~dp0"
echo Forcing high-performance GPU for this app...
echo (Chinese messages below are produced by the PowerShell script)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%DIR%set-discrete-gpu.ps1" %*
echo.
echo Press any key to close...
pause >nul
