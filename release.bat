@echo off
chcp 65001 >nul
title MCNP 输入卡生成器 - 一键发版
setlocal enabledelayedexpansion

:: =====================================================================
::  MCNP 输入卡生成器 - 一键发版脚本
::  将手工 5 步打包流程固化为一条命令：
::    ① 门禁（pytest + vitest）→ ② 版本号 → ③ 构建 → ④ 部署 → ⑤ 自检
::  用法：双击运行；或命令行 release.bat [新版本号，如 1.6.4]
::  注意：仓库根 build.bat 已过时，请勿再使用；本脚本为其替代。
:: =====================================================================

set "REPO=%~dp0"
set "DEPLOY=D:\MCNP\MCNP输入卡生成器"
set "FAIL_MSG="
set "APP_STARTED="

:: ---------- 读取当前版本号（以 tauri.conf.json 为准） ----------
set "VER_TAURI="
for /f "tokens=2 delims=:," %%a in ('findstr /c:"version" "%REPO%gui\src-tauri\tauri.conf.json"') do set "VER_TAURI=%%a"
set "VER_TAURI=%VER_TAURI: =%"
set "VER_TAURI=%VER_TAURI:"=%"

set "VER_UI="
for /f "tokens=2 delims=:," %%a in ('findstr /c:"version" "%REPO%gui\package.json"') do set "VER_UI=%%a"
set "VER_UI=%VER_UI: =%"
set "VER_UI=%VER_UI:"=%"

if "%VER_TAURI%"=="" (
    set "FAIL_MSG=读取版本号失败：%REPO%gui\src-tauri\tauri.conf.json 中未找到 version"
    goto :fail
)
set "CUR_VER=%VER_TAURI%"
if not "%VER_TAURI%"=="%VER_UI%" (
    echo [警告] tauri.conf.json 版本 %VER_TAURI% 与 package.json 版本 %VER_UI% 不一致，将以 tauri.conf.json 为准
)

echo ============================================================
echo   MCNP 输入卡生成器 - 一键发版脚本
echo   当前版本：%CUR_VER%
echo   部署目标：%DEPLOY%
echo ============================================================
echo.

:: ---------- 环境前置检查 ----------
where python >nul 2>&1
if errorlevel 1 (
    set "FAIL_MSG=未找到 python，请先安装 Python 3 并加入 PATH"
    goto :fail
)
where node >nul 2>&1
if errorlevel 1 (
    set "FAIL_MSG=未找到 node，请先安装 Node.js 18+ 并加入 PATH"
    goto :fail
)
where curl >nul 2>&1
if errorlevel 1 (
    set "FAIL_MSG=未找到 curl（Windows 10 1803+ 自带 curl.exe）"
    goto :fail
)
if not exist "D:\rust\cargo\bin\cargo.exe" (
    set "FAIL_MSG=未找到 Rust 工具链 D:\rust\cargo\bin\cargo.exe，tauri build 需要 Rust"
    goto :fail
)
echo 环境检查通过（python / node / curl / Rust）。
echo.

:: =====================================================================
::  [1/5] 门禁
:: =====================================================================
echo ============================================================
echo   [1/5] 门禁：后端 pytest + 前端 vitest
echo ============================================================
echo.
cd /d "%REPO%"
echo   -- 后端 python -m pytest tests/ -q （基线 271 全绿）...
python -m pytest tests/ -q
if errorlevel 1 (
    set "FAIL_MSG=门禁失败：后端 pytest 有失败用例（基线 271 全绿）。请先修复再发版"
    goto :fail
)
echo   -- 后端 pytest 通过。
echo.
cd /d "%REPO%gui"
echo   -- 前端 npx vitest run （基线 19 全绿）...
call npx vitest run
if errorlevel 1 (
    set "FAIL_MSG=门禁失败：前端 vitest 有失败用例（基线 19 全绿）。请先修复再发版"
    goto :fail
)
echo   -- 前端 vitest 通过。门禁全绿。

:: =====================================================================
::  [2/5] 版本号
:: =====================================================================
echo.
echo ============================================================
echo   [2/5] 版本号（当前 %CUR_VER%，留空则沿用）
echo ============================================================
set "NEWVER=%CUR_VER%"
set "INPUT_VER=%~1"
if "%INPUT_VER%"=="" set /p INPUT_VER=  输入新版本号（直接回车沿用 %CUR_VER%）：
if not "%INPUT_VER%"=="" set "NEWVER=%INPUT_VER%"
echo   [2/5] 本次发版版本号：%NEWVER%

if not "%NEWVER%"=="%CUR_VER%" (
    set "NV_CHK=%NEWVER%"
    python -X utf8 -c "import re,os,sys; v=os.environ['NV_CHK']; sys.exit(0 if re.fullmatch(r'\d+\.\d+\.\d+', v) else 1)"
    if errorlevel 1 (
        set "FAIL_MSG=版本号格式无效：%NEWVER%（应为 主.次.修订，例如 1.6.4）"
        goto :fail
    )
    echo   [2/5] 更新 package.json 与 tauri.conf.json 的 version ...
    set "OLD_VER="version": "%CUR_VER%""
    set "NEW_VER="version": "%NEWVER%""
    python -X utf8 -c "import os; p=r'%REPO%gui\package.json'; o=os.environ['OLD_VER']; n=os.environ['NEW_VER']; s=open(p,encoding='utf-8').read(); assert s.count(o)==1, 'version marker not unique in '+p; open(p,'w',encoding='utf-8',newline='').write(s.replace(o,n)); print('  updated '+p)"
    if errorlevel 1 (
        set "FAIL_MSG=版本号更新失败：package.json"
        goto :fail
    )
    python -X utf8 -c "import os; p=r'%REPO%gui\src-tauri\tauri.conf.json'; o=os.environ['OLD_VER']; n=os.environ['NEW_VER']; s=open(p,encoding='utf-8').read(); assert s.count(o)==1, 'version marker not unique in '+p; open(p,'w',encoding='utf-8',newline='').write(s.replace(o,n)); print('  updated '+p)"
    if errorlevel 1 (
        set "FAIL_MSG=版本号更新失败：tauri.conf.json"
        goto :fail
    )
    echo   [2/5] 版本号已更新为 %NEWVER%（package.json + tauri.conf.json）
    echo   [提示] 版本号改动涉及 git 跟踪文件，请发版后一并提交
)

:: =====================================================================
::  [3/5] 构建
:: =====================================================================
echo.
echo ============================================================
echo   [3/5] 构建：vite → PyInstaller → sidecar 替换 → tauri build
echo ============================================================
cd /d "%REPO%gui"

echo.
echo   [3/5 步骤a] vite 构建前端 ...
call npm run build
if errorlevel 1 (
    set "FAIL_MSG=构建失败：vite build 出错（npm run build）"
    goto :fail
)
if not exist "%REPO%gui\dist\index.html" (
    set "FAIL_MSG=构建失败：vite 产物不存在：%REPO%gui\dist\index.html"
    goto :fail
)
echo   [3/5 步骤a] vite 构建完成。

echo.
echo   [3/5 步骤b] PyInstaller 打包 sidecar（必须在 gui/ 下跑，spec 用 os.getcwd()/.. 定位工程根）...
python -m PyInstaller --noconfirm mcnp_sidecar.spec
if errorlevel 1 (
    set "FAIL_MSG=构建失败：PyInstaller 打包 sidecar 出错"
    goto :fail
)
if not exist "%REPO%gui\dist\python\python.exe" (
    set "FAIL_MSG=构建失败：PyInstaller 产物不存在：%REPO%gui\dist\python\python.exe"
    goto :fail
)
if not exist "%REPO%gui\dist\python\_internal" (
    set "FAIL_MSG=构建失败：PyInstaller 产物不存在：%REPO%gui\dist\python\_internal"
    goto :fail
)
echo   [3/5 步骤b] sidecar onedir 打包完成。

echo.
echo   [3/5 步骤c] 替换 sidecar 到 src-tauri\binaries（保留 onedir 结构）...
if exist "%REPO%gui\src-tauri\binaries" rmdir /s /q "%REPO%gui\src-tauri\binaries"
mkdir "%REPO%gui\src-tauri\binaries"
if errorlevel 1 (
    set "FAIL_MSG=构建失败：无法创建 %REPO%gui\src-tauri\binaries"
    goto :fail
)
copy /y "%REPO%gui\dist\python\python.exe" "%REPO%gui\src-tauri\binaries\python-x86_64-pc-windows-msvc.exe" >nul
if errorlevel 1 (
    set "FAIL_MSG=构建失败：sidecar python.exe 替换失败"
    goto :fail
)
xcopy /e /i /y "%REPO%gui\dist\python\_internal" "%REPO%gui\src-tauri\binaries\_internal" >nul
if errorlevel 1 (
    set "FAIL_MSG=构建失败：sidecar _internal 复制失败"
    goto :fail
)
echo   [3/5 步骤c] sidecar 替换完成。

echo.
echo   [3/5 步骤c2] spec 模块清单自检：核对 sidecar _internal\app\preview_cache.py ...
if not exist "%REPO%gui\src-tauri\binaries\_internal\app\preview_cache.py" (
    set "FAIL_MSG=spec 模块清单自检失败：_internal\app\preview_cache.py 缺失！preview_cache.py 曾漏进 spec 导致打包后 exe 启动即崩，请检查 gui\mcnp_sidecar.spec 的 _keep_py 是否包含 preview_cache.py"
    goto :fail
)
echo   [3/5 步骤c2] preview_cache.py 在位，自检通过。

echo.
echo   [3/5 步骤d] tauri build（Rust 增量编译，需 D:\rust 工具链）...
set "RUSTUP_HOME=D:\rust\rustup"
set "CARGO_HOME=D:\rust\cargo"
call npm run tauri build
if errorlevel 1 (
    set "FAIL_MSG=构建失败：tauri build 出错（Rust 编译）"
    goto :fail
)
if not exist "%REPO%gui\src-tauri\target\release\MCNP 输入卡生成器.exe" (
    set "FAIL_MSG=构建失败：tauri 产物不存在：%REPO%gui\src-tauri\target\release\MCNP 输入卡生成器.exe"
    goto :fail
)
if not exist "%REPO%gui\src-tauri\target\release\python.exe" (
    set "FAIL_MSG=构建失败：tauri 产物不存在：%REPO%gui\src-tauri\target\release\python.exe"
    goto :fail
)
if not exist "%REPO%gui\src-tauri\target\release\_internal" (
    set "FAIL_MSG=构建失败：tauri 产物不存在：%REPO%gui\src-tauri\target\release\_internal"
    goto :fail
)
echo   [3/5 步骤d] tauri build 完成。

:: =====================================================================
::  [4/5] 部署
:: =====================================================================
echo.
echo ============================================================
echo   [4/5] 部署：清空并复制产物到 %DEPLOY%
echo ============================================================
echo   [4/5] 若你正在使用已部署的 MCNP 程序，将被关闭以便更新...
call :kill_app
if exist "%DEPLOY%" rmdir /s /q "%DEPLOY%"
if errorlevel 1 (
    set "FAIL_MSG=部署失败：无法清空 %DEPLOY%（可能仍有进程占用），请手动关闭后重试"
    goto :fail
)
mkdir "%DEPLOY%"
if errorlevel 1 (
    set "FAIL_MSG=部署失败：无法创建 %DEPLOY%"
    goto :fail
)
copy /y "%REPO%gui\src-tauri\target\release\MCNP 输入卡生成器.exe" "%DEPLOY%\MCNP 输入卡生成器.exe" >nul
if errorlevel 1 (
    set "FAIL_MSG=部署失败：复制主程序 exe 失败"
    goto :fail
)
copy /y "%REPO%gui\src-tauri\target\release\python.exe" "%DEPLOY%\python.exe" >nul
if errorlevel 1 (
    set "FAIL_MSG=部署失败：复制 sidecar python.exe 失败"
    goto :fail
)
xcopy /e /i /y "%REPO%gui\src-tauri\target\release\_internal" "%DEPLOY%\_internal" >nul
if errorlevel 1 (
    set "FAIL_MSG=部署失败：复制 _internal 目录失败"
    goto :fail
)
if not exist "%DEPLOY%\MCNP 输入卡生成器.exe" (
    set "FAIL_MSG=部署失败：%DEPLOY%\MCNP 输入卡生成器.exe 缺失"
    goto :fail
)
if not exist "%DEPLOY%\python.exe" (
    set "FAIL_MSG=部署失败：%DEPLOY%\python.exe 缺失"
    goto :fail
)
if not exist "%DEPLOY%\_internal\app\preview_cache.py" (
    set "FAIL_MSG=部署后自检失败：%DEPLOY%\_internal\app\preview_cache.py 缺失（onedir 结构不完整）"
    goto :fail
)
echo   [4/5] 部署完成：exe + python.exe + _internal 已就位。

:: =====================================================================
::  [5/5] 自检
:: =====================================================================
echo.
echo ============================================================
echo   [5/5] 自检：启动 exe → 5001 探活 → 冒烟生成 → 清理
echo ============================================================
call :kill_app
set "APP_STARTED=1"
start "" "%DEPLOY%\MCNP 输入卡生成器.exe"
echo   [5/5] 已启动 exe，等待 5001 端口就绪（最多 90 秒）...
set /a tries=0
:wait_port
set /a tries+=1
if %tries% gtr 90 (
    set "FAIL_MSG=自检失败：exe 启动 90 秒内 5001 端口未就绪（请检查部署目录是否完整）"
    goto :fail
)
netstat -ano | findstr /c:":5001" | findstr /c:"LISTENING" >nul 2>&1
if not errorlevel 1 goto :port_up
timeout /t 1 /nobreak >nul
goto :wait_port
:port_up
echo   [5/5] 5001 探活成功，执行冒烟生成（/api/generate 最小 deck）...

:: 写最小 deck JSON 到临时文件
python -X utf8 -c "import json,os; d={'basic':{'title':'smoke deck','mode_n':True,'nps':'1000'},'surfaces':'1 rcc 0 0 0 0 10 0 2','cells':[{'kind':'cell','cell':{'number':1,'material':'1','density':'-1.0','surface_expr':'-1'}}],'materials':[{'number':1,'rows':[{'kind':'nuclide','zaid':'92235.06c','fraction':'-0.05'}]}],'sources':[{'number':1,'erg':'14.0','pos_x':'0','pos_y':'0','pos_z':'0'}],'adv':{'source_mode':'fixed'}}; open(os.path.join(os.environ['TEMP'],'mcnp_smoke.json'),'w',encoding='utf-8').write(json.dumps(d))"
if errorlevel 1 (
    set "FAIL_MSG=自检失败：写冒烟 deck 失败"
    goto :fail
)

curl -fsS -m 60 -X POST "http://127.0.0.1:5001/api/generate" -H "Content-Type: application/json" --data-binary "@%TEMP%\mcnp_smoke.json" -o "%TEMP%\mcnp_smoke_resp.json"
if errorlevel 1 (
    set "FAIL_MSG=自检失败：/api/generate 冒烟请求失败（HTTP 非 2xx 或超时）"
    goto :fail
)

python -X utf8 -c "import json,os; r=json.load(open(os.path.join(os.environ['TEMP'],'mcnp_smoke_resp.json'),encoding='utf-8')); assert r.get('status')=='ok', str(r); assert r.get('inp'), 'empty inp'; assert 'SDEF' in r['inp'], 'no SDEF in inp'; print('  冒烟通过：status=ok，inp 长度', len(r['inp']))"
if errorlevel 1 (
    set "FAIL_MSG=自检失败：冒烟响应校验未通过（status 非 ok 或 inp 不含 SDEF）"
    goto :fail
)

echo   [5/5] 冒烟生成通过。
echo   [5/5] 清理自检进程...
call :kill_app

:: =====================================================================
::  成功汇报
:: =====================================================================
echo.
echo ============================================================
echo   发版成功！
echo   版本号：%NEWVER%
echo   部署目录：%DEPLOY%
echo   主程序：%DEPLOY%\MCNP 输入卡生成器.exe
echo   sidecar：%DEPLOY%\python.exe（+ _internal）
echo   自检：5001 探活 + /api/generate 冒烟通过
echo ============================================================
pause
exit /b 0

:: =====================================================================
::  失败处理：打印红字 + 非零退出码
:: =====================================================================
:fail
echo.
echo ============================================================
powershell -NoProfile -Command "Write-Host '************ 发版失败 ************' -ForegroundColor Red" 2>nul
echo   失败原因：%FAIL_MSG%
powershell -NoProfile -Command "Write-Host '失败原因：%FAIL_MSG%' -ForegroundColor Red" 2>nul
echo ============================================================
if defined APP_STARTED call :kill_app
pause
exit /b 1

:: =====================================================================
::  工具子程序：关闭占用 5001 的 sidecar + 已部署主程序 exe
:: =====================================================================
:kill_app
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /c:":5001" ^| findstr /c:"LISTENING"') do taskkill /f /pid %%p >nul 2>&1
taskkill /f /im "MCNP 输入卡生成器.exe" >nul 2>&1
timeout /t 2 /nobreak >nul
exit /b 0
