# ============================================================================
# set-discrete-gpu.ps1 — 让 MCNP 输入卡生成器（Tauri/WebView2）强制使用独立显卡
# ----------------------------------------------------------------------------
# 原理：
#   这个应用是 WebView2 程序，真正的 3D 渲染跑在 msedgewebview2.exe（系统共享
#   进程），而不是你自己的 MCNP输入卡生成器.exe。所以要让电脑用独显，必须把
#   「真正干活的进程」设为高性能图形，而不是只设你的主 exe。
#
#   本脚本做两件事：
#     1) 找到所有 msedgewebview2.exe + 你的应用 exe
#     2) 把它们写入 Windows 的按进程 GPU 偏好注册表
#        HKCU\Software\Microsoft\DirectX\UserGpuPreferences\<exe路径> = GpuPreference=2;
#        （2 = 高性能/独显，1 = 省电/核显，0 = 系统默认）
#   该设置是 per-user（HKCU），普通权限即可写，不需要管理员。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File set-discrete-gpu.ps1
#   可选参数：
#     -AppExe "C:\path\to\App.exe"    手动指定应用 exe（默认自动识别同目录 exe）
#     -AppExeOnly                     只设置应用 exe，不设置共享的 msedgewebview2.exe
#                                     （避免影响所有其它 WebView2 程序）
#     -PrinterOnly                    只"预览"要设置的进程，不真正写注册表
# ============================================================================
param(
    [string]$AppExe = "",
    [switch]$AppExeOnly,
    [switch]$PrinterOnly,
    [switch]$Apply    # 默认即写入；保留该开关仅为语义清晰
)
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
if (-not $Apply -and -not $PrinterOnly) { $Apply = $true }

$BANNER = @"
==============================================
  强制使用独立显卡（高性能）
  MCNP 输入卡生成器 · WebView2
==============================================
"@
Write-Host $BANNER -ForegroundColor Cyan

# ---- 共享的 WebView2 渲染进程（Evergreen 版，系统级共享） --------------------
function Get-WebView2Exes {
    $list = @()
    $roots = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\EdgeWebView\Application'),
        (Join-Path $env:ProgramFiles 'Microsoft\EdgeWebView\Application'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\EdgeWebView\Application')
    )
    foreach ($r in $roots) {
        if (Test-Path $r) {
            Get-ChildItem -Path $r -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^\d+\.' } |
                ForEach-Object {
                    $e = Join-Path $_.FullName 'msedgewebview2.exe'
                    if (Test-Path $e) { $list += $e }
                }
        }
    }
    # 固定版本（Fixed Version）WebView2：紧邻应用目录，只服务于本应用
    try {
        $here = Split-Path -Parent $MyInvocation.MyCommand.Path
        Get-ChildItem -Path $here -Recurse -Filter 'msedgewebview2.exe' -ErrorAction SilentlyContinue |
            ForEach-Object { $list += $_.FullName }
    } catch { }
    return $list | Select-Object -Unique
}

# ---- 应用自己的 exe ----------------------------------------------------------
function Get-AppExe {
    param([string]$explicit)
    if ($explicit) { return $explicit }
    $exclude = 'python\.exe$|msedgewebview2\.exe$|unins|uninstall|crashpad|elevate|reg|setup'
    try {
        $here = Split-Path -Parent $MyInvocation.MyCommand.Path
        $cands = Get-ChildItem -Path $here -Filter '*.exe' -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notmatch $exclude } |
            Sort-Object Length -Descending
        if ($cands) { return $cands[0].FullName }
    } catch { }
    # 兜底：如果正在运行，用进程名
    $proc = Get-Process -Name 'MCNP输入卡生成器' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($proc) { return $proc.Path }
    return $null
}

function Set-HighPerf {
    param([string]$exe)
    if ($PrinterOnly) { Write-Host ("  [预览] 将设置 -> {0}" -f $exe) -ForegroundColor DarkGray; return }
    $key = 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences'
    try {
        if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
        Set-ItemProperty -Path $key -Name $exe -Value 'GpuPreference=2;' -Type String
        Write-Host ("  [已设置] {0}" -f $exe) -ForegroundColor Green
    } catch {
        Write-Host ("  [失败] {0} -> {1}" -f $exe, $_.Exception.Message) -ForegroundColor Red
    }
}

# ---- 检测显卡厂商（用于给提示） ----------------------------------------------
$vendor = "unknown"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { $vendor = "nvidia" }
elseif (Test-Path "$env:ProgramFiles\AMD") { $vendor = "amd" }
elseif (Test-Path "$env:ProgramFiles\NVIDIA Corporation") { $vendor = "nvidia" }

Write-Host ("检测到的显卡厂商: {0}" -f $vendor.ToUpper()) -ForegroundColor Yellow

# ---- 收集目标进程 -------------------------------------------------------------
$app = Get-AppExe -explicit $AppExe
$webviews = if (-not $AppExeOnly) { @(Get-WebView2Exes) } else { @() }
$targets = @()
if ($app) { $targets += $app } else { Write-Host "  [警告] 未找到应用 exe，只会设置 WebView2 渲染进程" -ForegroundColor Yellow }
$targets += $webviews

if ($targets.Count -eq 0) {
    Write-Host "  [错误] 没有找到任何需要设置的进程。" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host ("将设置以下 {0} 个进程为「高性能」：" -f $targets.Count) -ForegroundColor Cyan
$targets | ForEach-Object { Write-Host ("  - {0}" -f $_) -ForegroundColor DarkGray }

if ($PrinterOnly) {
    Write-Host ""
    Write-Host "[预览模式] 未写注册表。去掉 -PrinterOnly 再运行即可真正生效。" -ForegroundColor DarkYellow
    exit 0
}

Write-Host ""
$targets | ForEach-Object { Set-HighPerf -exe $_ }
Write-Host ""

# ---- 完成提示 -----------------------------------------------------------------
Write-Host "已完成。设置需要重启应用（或重启电脑）才会应用到正在运行的 WebView2 进程。" -ForegroundColor Green
Write-Host ""

if ($vendor -eq "nvidia") {
    Write-Host "补充建议（NVIDIA，可选）：" -ForegroundColor Yellow
    Write-Host "  控制台版：NVIDIA 控制面板 -> 管理 3D 设置 -> 程序设置"
    Write-Host "    -> 添加 msedgewebview2.exe -> 首选图形处理器 = 高性能 NVIDIA 处理器"
    Write-Host "    （在驱动层对这个进程强制分配独显，通常比注册表更彻底）"
} elseif ($vendor -eq "amd") {
    Write-Host "补充建议（AMD）：AMD 软件 -> 显卡 -> 兼容性 / 游戏 页签，把应用设为「高性能」。" -ForegroundColor Yellow
} else {
    Write-Host "注意：未检测到独立显卡驱动。" -ForegroundColor Yellow
    Write-Host "  Windows 设置 -> 显示 -> 图形，手动添加 msedgewebview2.exe / 应用 exe 并设为「高性能」。" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "重要说明：" -ForegroundColor Cyan
Write-Host "  Evergreen（系统共享）版 msedgewebview2.exe 被设为高性能后，所有依赖 WebView2 的"
Write-Host "  程序都会一起走独显。若只想影响本应用，请用参数：  -AppExeOnly （只设应用 exe）。"
Write-Host ""
