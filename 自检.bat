@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set "DIR=%~dp0"
set "OUT="

rem ── 报告落点：**就是 自检.bat 同目录**（用户在这儿双击的，交代路径最省事）──
rem 唯一例外：该目录不可写（例如程序被装到 Program Files 下）才退到桌面 / %TEMP%，
rem 且窗口与报告里都会打印**实际落点** —— 绝不静默换地方。
rem （为何不用固定 %TEMP%：普通用户根本找不到它，而这份报告的唯一用途就是发回给我们。）
> "%DIR%__w.tmp" echo x 2>nul
if exist "%DIR%__w.tmp" set "OUT=%DIR%MCNP自检报告.txt"
del "%DIR%__w.tmp" >nul 2>&1
if not defined OUT call :try_desktop
if not defined OUT set "OUT=%TEMP%\MCNP自检报告.txt"

call :checks > "%OUT%" 2>&1
type "%OUT%"

echo.
echo ============================================================
echo  请把下面这个文件发回（它就是上面这段内容的完整版）：
echo.
echo    %OUT%
echo.
echo  报告里“程序输出”一节若中文是乱码属正常：子进程按系统 ANSI
echo  码页写中文。判据看 ASCII 标记即可 ——
echo    [OK] / [MISS] / [RESULT] / Failed to load Python DLL
echo ============================================================
pause
exit /b 0


:try_desktop
if not exist "%USERPROFILE%\Desktop" exit /b 0
> "%USERPROFILE%\Desktop\__w.tmp" echo x 2>nul
if exist "%USERPROFILE%\Desktop\__w.tmp" set "OUT=%USERPROFILE%\Desktop\MCNP自检报告.txt"
del "%USERPROFILE%\Desktop\__w.tmp" >nul 2>&1
exit /b 0


:checks
echo ============================================================
echo  MCNP 输入卡生成器 — 环境自检报告 / SELF CHECK REPORT
echo  脚本版本 : v2 2026-09-20
echo  时间     : %DATE% %TIME%
echo  交付目录 : %DIR%
echo  报告文件 : %OUT%
echo ============================================================
ver
echo.
echo [1/6] 三件套是否同目录在位
call :fileinfo "MCNP 输入卡生成器.exe" "主程序"
call :fileinfo "python.exe" "后端 sidecar"
call :fileinfo "自检.bat" "本脚本"
if exist "%DIR%_internal" (
  for /f %%C in ('dir /s /b /a-d "%DIR%_internal" 2^>nul ^| find /c /v ""') do set "N=%%C"
  echo   [OK]   _internal 目录 - 文件数 = !N!
) else (
  set "N=0"
  echo   [MISS] _internal 目录不存在   ^<== 后端一闪就没的头号原因
)
echo.
echo [2/6] 关键文件
call :musthave "_internal\python313.dll"    "Python 运行时，缺它必报 Failed to load Python DLL"
call :musthave "_internal\base_library.zip" "标准库归档"
call :musthave "_internal\app\models.py"    "后端模块"
echo.
echo [3/6] 引导自检 - 真实启动一次 sidecar，用完即退，不占端口
set "PROBE=%TEMP%\mcnp_boot_probe.log"
rem 喂最小载荷验：引导器 + python313.dll + base_library + PYZ 归档。
rem 验不到 _internal\app 下的 .py 数据文件（PYZ 里另有一份且 FrozenImporter 优先命中）。
rem 载荷 path 为空会以 FileNotFoundError 收场（正常）；只认 ModuleNotFoundError/ImportError。
echo {"mode":"parse"}| "%DIR%python.exe" --meshtal-worker > "%PROBE%" 2>&1
set "RC=!ERRORLEVEL!"
echo   退出码 = !RC!
echo   ---- 程序输出 ----
rem 子进程按**系统 ANSI 码页**写中文（实测 PYTHONIOENCODING/PYTHONUTF8 对冻结版无效），
rem 若原样并入报告，整份 txt 就不是合法 UTF-8 —— 对方或 AI 打开会乱码甚至读不了（实测踩过）。
rem 故先用 PowerShell 按 ANSI 读、按 UTF-8 **无 BOM** 写一份再贴进来；
rem PowerShell 不可用时退回原样（报告可能含非 UTF-8 段，但判据仍是 ASCII 标记）。
set "PROBE_U8=%TEMP%\mcnp_boot_probe.utf8.txt"
if exist "%PROBE_U8%" del "%PROBE_U8%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=[IO.File]::ReadAllText('%PROBE%',[Text.Encoding]::Default); [IO.File]::WriteAllText('%PROBE_U8%',$t,(New-Object Text.UTF8Encoding($false)))" >nul 2>&1
if exist "%PROBE_U8%" (type "%PROBE_U8%") else (echo   [--]   编码转换不可用，以下为原始字节 & type "%PROBE%")
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
echo [4/6] 端口与进程
call :port 5001 "后端 - 主程序启动时会自动拉起"
call :port 8100 "AI 接入 MCP"
tasklist /fi "imagename eq python.exe" 2>nul | findstr /i "python.exe" >nul
if not errorlevel 1 (echo   [OK]   有 python.exe 进程在跑) else (echo   [--]   没有 python.exe 进程在跑)
echo.
echo [5/6] 后端自述与用户配置（后端在跑才取得到）
if "!PT5001!"=="1" (
  where curl >nul 2>&1
  if errorlevel 1 (
    echo   [--]   本机没有 curl.exe，跳过接口自述
  ) else (
    echo   --- /api/mcnp-detect（候选 MCNP 与各自带的 xsdir）---
    curl -s -X POST --max-time 20 http://127.0.0.1:5001/api/mcnp-detect
    echo.
    echo   --- /api/xsdir-check（本程序当前加载的截面库）---
    curl -s -X POST --max-time 20 http://127.0.0.1:5001/api/xsdir-check
    echo.
  )
) else (
  echo   [--]   5001 未监听，跳过接口自述
)
echo   --- config.json（手动指定过的路径都存在这里）---
if exist "%APPDATA%\mcnp_generator\config.json" (
  type "%APPDATA%\mcnp_generator\config.json"
  echo.
) else (
  echo   [--]   不存在（从未手动指定过 FreeCAD / MCNP 路径）
)
echo.
echo [6/6] 结论

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
  echo   处理：把本报告发回，上面 Traceback 的模块名就是漏的那个。
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
  echo   再关闭主程序后重新打开，并把本报告发回。
)
if "!VERDICT!"=="PACKAGE-OK-BACKEND-NOT-UP" (
  echo   包看起来完整、引导也正常，但 5001 上没人监听。
  echo   处理：先打开主程序等 1 到 3 分钟；若仍显示后端不可用，
  echo         多半是杀软拦住了 python.exe 的启动，请把本报告发回。
)
echo.
echo ============================================================
echo  [RESULT] !VERDICT!   （这一行是关键，发回时别漏）
echo ============================================================
exit /b 0


:fileinfo
if exist "%DIR%%~1" (
  for %%F in ("%DIR%%~1") do echo   [OK]   %~2 - %~1 - %%~zF bytes - %%~tF
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
