@echo off
chcp 65001 >nul
setlocal
set "DIR=%~dp0"
set "PYEXE=%DIR%python.exe"

if not exist "%PYEXE%" (
    echo [ERROR] python.exe not found next to this script.
    echo         Please keep 注册MCP.bat and python.exe in the same folder.
    pause
    exit /b 1
)

cd /d "%DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $py=Join-Path $PWD 'python.exe'; $local=Join-Path $PWD '.mcp.json'; $lc=if(Test-Path $local){Get-Content $local -Raw|ConvertFrom-Json}else{[pscustomobject]@{}}; if(-not($lc.PSObject.Properties.Name -contains 'mcpServers')){$lc|Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})}; $lc.mcpServers|Add-Member -NotePropertyName 'inputcard-mcp' -NotePropertyValue ([pscustomobject]@{command=$py;args=@('--mcp-server')}) -Force; $lc|ConvertTo-Json -Depth 20|Set-Content $local -Encoding UTF8; Write-Host ('[OK] wrote ' + $local)"

echo.
echo Registered 'inputcard-mcp' into .mcp.json in this folder:
echo   command: %PYEXE%
echo   args   : ["--mcp-server"]
echo.
echo 说明：本目录 .mcp.json 是 MCP 的通用入口，多数 agent（如 Claude Code 及支持"项目级 mcp.json"的工具）会自动读取。
echo       若你的 agent 用其它配置方式，请打开 AI接入.md 按其中说明复制配置片段放入。
pause
exit /b 0
