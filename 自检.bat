@echo off
chcp 65001 >nul
title MCNP 输入卡生成器 - 环境自检（跑完自动关闭）
setlocal enabledelayedexpansion
set "DIR=%~dp0"
set "OUT="

rem ══════════════════════════════════════════════════════════════════
rem  设计口径（2026-09-20 定）：
rem   1) 报告**就放在 自检.bat 同目录**（用户在这儿双击的）；仅当该目录不可写
rem      （例如装到 Program Files）才退到桌面 / %TEMP%，且报告里写明实际落点。
rem   2) 窗口**不显示任何内容**，报告写完即自动关闭；只有"报告根本没写出来"
rem      才出声并停住 —— 那种情况用户必须知道，否则会以为自检跑过了。
rem   3) 报告必须是**合法 UTF-8 无 BOM**：子进程与部分系统命令按系统 ANSI 码页写中文，
rem      直接并入会让整份文件不是 UTF-8（实测按 UTF-8 打开会被拒读），故先转码再落盘。
rem ══════════════════════════════════════════════════════════════════

> "%DIR%__w.tmp" echo x 2>nul
if exist "%DIR%__w.tmp" set "OUT=%DIR%MCNP自检报告.txt"
del "%DIR%__w.tmp" >nul 2>&1
if not defined OUT call :try_desktop
if not defined OUT set "OUT=%TEMP%\MCNP自检报告.txt"

call :checks > "%OUT%" 2>&1

if not exist "%OUT%" (
  echo.
  echo [x] 自检报告没能写出：%OUT%
  echo     请把本窗口截图发回；或把整个程序目录复制到可写位置后再双击本脚本。
  echo.
  pause
  exit /b 1
)
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
echo  脚本版本 : v4 2026-09-29
echo  时间     : %DATE% %TIME%
echo  交付目录 : %DIR%
echo  报告文件 : %OUT%
echo ============================================================
ver
echo.
echo [1/8] 三件套是否同目录在位
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
echo [2/8] 界面运行时 WebView2 - 没有它主程序窗口根本起不来
rem 背景（2026-09-29 实测定稿）：界面是 WebView2 渲染的，而 WebView2 平时由 Edge 附带安装。
rem 精简版 Windows 删掉 Edge 就**连带没有** WebView2 ⇒ 双击 exe 没反应/一闪就没。
rem 现随包分发一份微软官方"固定版运行时"（与本 exe 同级的 WebView2\ 目录），
rem 主程序启动时"有则用、无则退"（见 gui\src-tauri\src\main.rs 的 prefer_bundled_webview2）。
set "WV2=0"
if exist "%DIR%WebView2\msedgewebview2.exe" (
  set "WV2=1"
  echo   [OK]   自带 WebView2 运行时 - WebView2\msedgewebview2.exe 在位（不依赖系统 Edge）
) else (
  echo   [--]   没有自带的 WebView2 运行时 - WebView2\msedgewebview2.exe 不存在
)
rem 系统装的 WebView2：Edge 系版本号写在 EdgeUpdate 的客户端 GUID 下（64 位系统看 WOW6432Node）
set "WV2SYS="
for /f "tokens=3" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv 2^>nul ^| findstr /i "REG_SZ"') do set "WV2SYS=%%A"
if not defined WV2SYS for /f "tokens=3" %%A in ('reg query "HKCU\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv 2^>nul ^| findstr /i "REG_SZ"') do set "WV2SYS=%%A"
if defined WV2SYS (
  set "WV2=1"
  echo   [OK]   系统已安装 WebView2 运行时 - 版本 !WV2SYS!
) else (
  echo   [--]   系统没有安装 WebView2 运行时（精简版 Windows 删掉 Edge 后就是这样）
)
if "!WV2!"=="1" (echo   界面运行时判定 = OK) else (echo   界面运行时判定 = MISSING   ^<== 主程序双击打不开的头号原因)
echo.
echo [3/8] 关键文件
call :musthave "_internal\python313.dll"    "Python 运行时，缺它必报 Failed to load Python DLL"
call :musthave "_internal\base_library.zip" "标准库归档"
call :musthave "_internal\app\models.py"    "后端模块"
echo.
echo [4/8] 引导自检 - 真实启动一次 sidecar，用完即退，不占端口
set "PROBE=%TEMP%\mcnp_boot_probe.log"
rem 喂最小载荷验：引导器 + python313.dll + base_library + PYZ 归档。
rem 验不到 _internal\app 下的 .py 数据文件（PYZ 里另有一份且 FrozenImporter 优先命中）。
rem 载荷 path 为空会以 FileNotFoundError 收场（正常）；只认 ModuleNotFoundError/ImportError。
echo {"mode":"parse"}| "%DIR%python.exe" --meshtal-worker > "%PROBE%" 2>&1
set "RC=!ERRORLEVEL!"
echo   退出码 = !RC!
echo   ---- 程序输出 ----
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
echo [5/8] 端口与进程
call :port 5001 "后端 - 主程序启动时会自动拉起"
call :port 8100 "AI 接入 MCP"
tasklist /fi "imagename eq python.exe" 2>nul | findstr /i "python.exe" >nul
if not errorlevel 1 (echo   [OK]   有 python.exe 进程在跑) else (echo   [--]   没有 python.exe 进程在跑)
echo.
echo [6/8] 后端自述与用户配置（后端在跑才取得到）
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
echo [7/8] 环境变量
echo   注：这是**运行本脚本这个窗口**的环境；主程序拉起的 sidecar 继承的是你登录
echo       会话的环境，两者可能不同（GUI 启动常吃不到新设的变量）—— 对比时注意。
echo   --- 关键项（诊断最需要的几项，原样保留）---
set "ENVALL=%TEMP%\mcnp_env_all.txt"
set > "%ENVALL%" 2>nul
findstr /b /i /c:"PATH=" /c:"PATHEXT=" /c:"DATAPATH=" /c:"XSDIR=" /c:"xsdir=" /c:"MCNP" /c:"PYTHON" /c:"CUDA_VISIBLE_DEVICES=" /c:"TEMP=" /c:"TMP=" /c:"USERPROFILE=" /c:"APPDATA=" /c:"LOCALAPPDATA=" /c:"COMPUTERNAME=" /c:"PROCESSOR_" /c:"NUMBER_OF_PROCESSORS=" /c:"OS=" "%ENVALL%" 2>nul
echo   --- 全部环境变量（已滤掉名字或取值里含 KEY/TOKEN/SECRET/PASSWORD 等敏感词的项）---
findstr /v /i "KEY TOKEN SECRET PASSWORD PASSWD CREDENTIAL COOKIE AUTH" "%ENVALL%" 2>nul
echo.
echo [8/8] 结论

set "VERDICT="
if "!BOOT!"=="FAIL" set "VERDICT=PKG-INCOMPLETE-OR-BLOCKED"
if not defined VERDICT if "!N!"=="0" set "VERDICT=PKG-INCOMPLETE"
if not defined VERDICT if "!BOOT!"=="IMPORT-ERR" set "VERDICT=PKG-MODULE-MISSING"
if not defined VERDICT if "!WV2!"=="0" set "VERDICT=WEBVIEW2-MISSING"
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
if "!VERDICT!"=="WEBVIEW2-MISSING" (
  echo   主程序窗口起不来：界面要靠 WebView2 渲染，而这台机器既没有随包自带的 WebView2 目录，
  echo   系统也没装 WebView2 运行时（精简版 Windows 删掉 Edge 之后就是这样）。
  echo   处理：确认交付目录里 WebView2\ 文件夹与 exe 同级且完整 - 关键是 WebView2\msedgewebview2.exe 必须在。
  echo         若确认缺失或不全，请重新完整解压交付包（不要在压缩包/网盘里直接运行）。
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
