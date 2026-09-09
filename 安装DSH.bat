@echo off
setlocal

REM ============================================================
REM  DeepSeek Harness (DSH) - install to fixed dir D:\DSH (npx)
REM  Prereq: Node.js LTS is installed (ships npm / npx)
REM
REM  Usage:
REM    double-click           -> launch DSH web UI (auto-init on first run)
REM    script <extra args>    -> forwarded to dsh, e.g.:
REM       install-dsh.bat --profile headless "run tests"
REM       install-dsh.bat web --port 8080
REM ============================================================

set "DSH_HOME=D:\DSH"

echo.
echo ==================================================
echo   DeepSeek Harness (DSH)  -^>  %DSH_HOME%
echo ==================================================

if not exist "%DSH_HOME%" mkdir "%DSH_HOME%"
echo [OK] Directory  %DSH_HOME%

setx DSH_HOME "%DSH_HOME%" >nul 2>nul
echo [OK] Env var    DSH_HOME = %DSH_HOME%

echo.
echo [OK] Launching DSH via npx ...
echo.

if "%~1"=="" (
    call npx --yes @deepseek-ai/dsh web
) else (
    call npx --yes @deepseek-ai/dsh %*
)

endlocal
pause
