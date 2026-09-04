@echo off
chcp 65001 >nul
setlocal
title 自动注册 inputcard-mcp 到 MCP 客户端

rem ============================================================
rem  inputcard-mcp 一键自动注册（无硬编码路径）
rem  自动探测「本脚本所在目录」的 python.exe（%~dp0），写入：
rem    1) Claude Desktop 配置  %APPDATA%\Claude\claude_desktop_config.json（若存在）
rem    2) 本目录  .mcp.json（供 Claude Code / 项目级 MCP 客户端使用）
rem  零路径硬编码：你把程序复制/解压到任何目录都能直接用本脚本。
rem ============================================================

set "DIR=%~dp0"
set "PYEXE=%DIR%python.exe"

if not exist "%PYEXE%" (
    echo [错误] 未找到 %PYEXE%
    echo        请确认本脚本与 python.exe 在同一目录，或把程序放在同目录。
    pause
    exit /b 1
)

echo 检测到 python.exe：%PYEXE%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$py='%PYEXE%';" ^
  "$dir='%DIR%';" ^
  "$srv=@{command=$py;args=@('--mcp-server')};" ^
  "" ^
  "# 1) Claude Desktop 配置" ^
  "$desk=Join-Path $env:APPDATA 'Claude\claude_desktop_config.json';" ^
  "$deskDir=Split-Path $desk;" ^
  "if(Test-Path $deskDir){" ^
  "  $cfg=if(Test-Path $desk){ Get-Content $desk -Raw | ConvertFrom-Json } else { [pscustomobject]@{} };" ^
  "  if(-not ($cfg.PSObject.Properties.Name -contains 'mcpServers')){ $cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) };" ^
  "  $cfg.mcpServers | Add-Member -NotePropertyName 'inputcard-mcp' -NotePropertyValue $srv -Force;" ^
  "  $cfg | ConvertTo-Json -Depth 20 | Set-Content $desk -Encoding UTF8;" ^
  "  Write-Host ('[OK] 已写入 Claude Desktop 配置: ' + $desk)" ^
  "} else {" ^
  "  Write-Host '[提示] 未找到 Claude Desktop 配置目录，跳过。'" ^
  "}" ^
  "" ^
  "# 2) 项目级 .mcp.json（本目录，Claude Code 等）" ^
  "$local=Join-Path $dir '.mcp.json';" ^
  "$lc=if(Test-Path $local){ Get-Content $local -Raw | ConvertFrom-Json } else { [pscustomobject]@{} };" ^
  "if(-not ($lc.PSObject.Properties.Name -contains 'mcpServers')){ $lc | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) };" ^
  "$lc.mcpServers | Add-Member -NotePropertyName 'inputcard-mcp' -NotePropertyValue $srv -Force;" ^
  "$lc | ConvertTo-Json -Depth 20 | Set-Content $local -Encoding UTF8;" ^
  "Write-Host ('[OK] 已写入项目级配置: ' + $local)"

echo.
echo 注册完成。以下 MCP server 已可被 AI 客户端发现：
echo   name   : inputcard-mcp
echo   command: %PYEXE%
echo   args   : ["--mcp-server"]
echo.
echo 提示：自 2026-01 起，Claude Desktop 的 mcpServers 需在 JSON 根节点下，
echo      本脚本已按该结构写入；若你的客户端用其它格式，请按 AI接入配置.md 手动调整。
pause
exit /b 0
