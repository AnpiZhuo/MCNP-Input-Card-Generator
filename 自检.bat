@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set "DIR=%~dp0"
set "LOG=%TEMP%\MCNP_selfcheck.log"

call :checks > "%LOG%" 2>&1
type "%LOG%"

echo.
echo ============================================================
echo  请把本窗口截图发回；或把这个文件发回：
echo    %LOG%
echo  中文若显示为乱码不影响判读：
echo    [OK] / [MISS] / [RESULT] 这些英文标记照旧可读。
echo ============================================================
pause
exit /b 0


:checks
echo ============================================================
echo  MCNP 输入卡生成器 — 环境自检 / SELF CHECK
echo  dir  : %DIR%
echo  time : %DATE% %TIME%
echo ============================================================
echo.
echo [1/5] 三件套是否同目录在位
call :fileinfo "MCNP 输入卡生成器.exe" "主程序"
call :fileinfo "python.exe" "后端 sidecar"
if exist "%DIR%_internal" (
  for /f %%C in ('dir /s /b /a-d "%DIR%_internal" 2^>nul ^| find /c /v ""') do set "N=%%C"
  echo   [OK]   _internal 目录 - 文件数 = !N!
) else (
  set "N=0"
  echo   [MISS] _internal 目录不存在   ^<== 后端一闪就没的头号原因
)
echo.
echo [2/5] 关键文件
call :musthave "_internal\python313.dll"    "Python 运行时，缺它必报 Failed to load Python DLL"
call :musthave "_internal\base_library.zip" "标准库归档"
call :musthave "_internal\app\models.py"    "后端模块"
echo.
echo [3/5] 引导自检 - 真实启动一次 sidecar，用完即退，不占端口
set "PROBE=%TEMP%\mcnp_boot_probe.log"
rem 子进程按系统 ANSI 码页写中文（实测 PYTHONIOENCODING/PYTHONUTF8 对冻结版**无效**，
rem 两种设置下输出字节完全相同），而本窗口是 UTF-8 ⇒ 那段中文在窗口里可能显示为乱码。
rem 因此判据**全部走 ASCII 标记**，不依赖中文能否显示；乱码的那份原文会留在 %PROBE%。
rem 喂一个最小载荷让 sidecar 真跑一遍，验的是：引导器 + python313.dll + base_library + PYZ 归档。
rem 注意它**验不到** _internal\app 下的 .py 数据文件 —— 那些模块在 PYZ 里另有一份，
rem 且 Python 的 FrozenImporter 优先命中 PYZ（实测：删掉 _internal\app\meshtal 照样 import 成功）。
rem 那类缺失的表现是**个别端点 500**，不是进程起不来，不属本脚本要抓的症状。
rem 载荷里 path 为空会以 FileNotFoundError 收场（正常）；只认 ModuleNotFoundError/ImportError
rem 来区分"归档损坏 / 模块真缺"。
echo {"mode":"parse"}| "%DIR%python.exe" --meshtal-worker > "%PROBE%" 2>&1
set "RC=!ERRORLEVEL!"
echo   退出码 = !RC!
echo   ---- 程序输出 ----
type "%PROBE%" 2>nul
echo.
echo   -------------------
set "BOOT=OK"
findstr /i /c:"PYI-" /c:"Failed to load Python DLL" /c:"Failed to execute script" "%PROBE%" >nul 2>&1
if not errorlevel 1 set "BOOT=FAIL"
set "IMPORTBAD=0"
findstr /i /c:"ModuleNotFoundError" /c:"ImportError" "%PROBE%" >nul 2>&1
if not errorlevel 1 set "IMPORTBAD=1"
if "!BOOT!"=="OK" if "!IMPORTBAD!"=="1" set "BOOT=IMPORT-ERR"
echo   引导判定 = !BOOT!
echo.
echo [4/5] 端口与进程
call :port 5001 "后端 - 主程序启动时会自动拉起"
call :port 8100 "AI 接入 MCP"
tasklist /fi "imagename eq python.exe" 2>nul | findstr /i "python.exe" >nul
if not errorlevel 1 (echo   [OK]   有 python.exe 进程在跑) else (echo   [--]   没有 python.exe 进程在跑)
echo.
echo [5/5] 结论

set "VERDICT="
if "!BOOT!"=="FAIL" set "VERDICT=PKG-INCOMPLETE-OR-BLOCKED"
if not defined VERDICT if "!N!"=="0" set "VERDICT=PKG-INCOMPLETE"
if not defined VERDICT if "!BOOT!"=="IMPORT-ERR" set "VERDICT=PKG-MODULE-MISSING"
if not defined VERDICT if "!PT5001!"=="1" set "VERDICT=BACKEND-RUNNING"
if not defined VERDICT set "VERDICT=PACKAGE-OK-BACKEND-NOT-UP"

echo   [RESULT] !VERDICT!
echo.
if "!VERDICT!"=="PKG-MODULE-MISSING" (
  echo   后端能起来，但有模块导入失败 - 多半是打包时漏了模块。
  echo   处理：把本窗口连同 %PROBE% 一起发回，上面 Traceback 的模块名就是漏的那个。
)
if "!VERDICT!"=="PKG-INCOMPLETE-OR-BLOCKED" (
  echo   后端引导失败：_internal 没跟过来/不完整，或其中的 dll 被杀软清掉了。
  echo   处理：把 MCNP 输入卡生成器.exe + python.exe + _internal 三件套
  echo         一起重新完整复制到本地磁盘，不要在压缩包或网盘里直接运行；
  echo         再把整个目录加进杀毒软件白名单后重试。
)
if "!VERDICT!"=="PKG-INCOMPLETE" (
  echo   少了 _internal 目录。它和 python.exe 是一套，缺一不可。
  echo   处理：重新完整复制/解压整个目录，不要在压缩包里双击运行。
)
if "!VERDICT!"=="BACKEND-RUNNING" (
  echo   后端已在本机 5001 上监听，包是好的。
  echo   若主程序仍提示后端不可用：先确认没有别的程序抢占 5001，
  echo   再关闭主程序后重新打开，并把本窗口发回。
)
if "!VERDICT!"=="PACKAGE-OK-BACKEND-NOT-UP" (
  echo   包看起来完整、引导也正常，但 5001 上没人监听。
  echo   处理：先打开主程序等 1 到 3 分钟；若仍显示后端不可用，
  echo         多半是杀软拦住了 python.exe 的启动，请把本窗口发回。
)
echo.
echo ============================================================
exit /b 0


:fileinfo
if exist "%DIR%%~1" (
  for %%F in ("%DIR%%~1") do echo   [OK]   %~2 - %~1 - %%~zF bytes
) else (
  echo   [MISS] %~2 - %~1 - 文件不存在
)
exit /b 0


:musthave
if exist "%DIR%%~1" (
  echo   [OK]   %~1
) else (
  echo   [MISS] %~1   ^<== %~2
)
exit /b 0


:port
set "PT%~1=0"
netstat -ano | findstr ":%~1" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 set "PT%~1=1"
if "!PT%~1!"=="1" (
  echo   [OK]   端口 %~1 正在监听 - %~2
) else (
  echo   [--]   端口 %~1 无人监听 - %~2
)
exit /b 0
