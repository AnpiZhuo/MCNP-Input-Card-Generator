# MCNP 输入卡生成器 - 一键打包部署脚本 (PowerShell)
# 取代已停用的 release.bat（release.bat 依赖 npm/npx, 在 ExecutionPolicy 下被禁;
# 且不处理 6.2 sidecar 时效坑）。本脚本用 node 直接调用 vite/tauri CLI, 并在
# tauri build 后无条件把新 sidecar 覆盖进 target\release (6.2 坑每次必中, 不再人工核对 mtime),
# 随后部署 + 冒烟自检。
#
# 用法 (任选其一):
#   powershell -ExecutionPolicy Bypass -File scripts\release.ps1                 # 沿用当前版本
#   powershell -ExecutionPolicy Bypass -File scripts\release.ps1 -NewVer 1.7.5   # 提升版本
#   powershell -ExecutionPolicy Bypass -File scripts\release.ps1 -SkipGate       # 跳过门禁
#   powershell -ExecutionPolicy Bypass -File scripts\release.ps1 -SkipDeploy     # 只构建不部署
#
# 退出码: 0 = 成功  1 = 失败

[CmdletBinding()]
param(
    [string]$NewVer = "",
    [switch]$SkipGate,
    [switch]$SkipDeploy
)

$ErrorActionPreference = "Stop"
chcp 65001 > $null

$repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $repo "gui"))) {
    Write-Host "[ERR] 找不到 gui 目录, 脚本应位于仓库子目录 scripts\" -ForegroundColor Red
    exit 1
}
$gui = Join-Path $repo "gui"
$deploy = "D:\MCNP\MCNP输入卡生成器"

function Fail([string]$msg) {
    Write-Host ""
    Write-Host "******** 发版失败 ********" -ForegroundColor Red
    Write-Host "  失败原因: $msg" -ForegroundColor Red
    Write-Host "**************************" -ForegroundColor Red
    exit 1
}

# ---------- [0] 环境前置检查 ----------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Fail "未找到 python" }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail "未找到 node" }
foreach ($j in @(
    "vite\bin\vite.js",
    "@tauri-apps\cli\tauri.js",
    "vitest\vitest.mjs",
    "typescript\bin\tsc"
)) {
    if (-not (Test-Path (Join-Path $gui "node_modules\$j"))) {
        Fail "前端 CLI 缺失: gui\node_modules\$j (先 npm install 装依赖)"
    }
}
if (-not (Test-Path "D:\rust\cargo\bin\cargo.exe")) { Fail "未找到 Rust 工具链 D:\rust\cargo\bin\cargo.exe" }
Write-Host "[0/6] 环境检查通过" -ForegroundColor Green

# ---------- [1/6] 版本号 ----------
$tauriConf = Get-Content (Join-Path $gui "src-tauri\tauri.conf.json") -Raw | ConvertFrom-Json
$cur = $tauriConf.package.version
$new = if ($NewVer) { $NewVer } else { $cur }
if ($new -notmatch "^\d+\.\d+\.\d+$") {
    Fail "版本号格式无效: $new (应为 主.次.修订, 例如 1.7.5)"
}
$verMsg = if ($new -eq $cur) { "bug 修复批不升版" } else { "新版本" }
Write-Host "[1/6] 版本号: 当前 $cur -> 本次 $new ($verMsg)"

if ($new -ne $cur) {
    Write-Host "  .. 同步版本到五处"
    foreach ($f in @(
        (Join-Path $gui "src-tauri\tauri.conf.json"),
        (Join-Path $gui "package.json")
    )) {
        $s = Get-Content $f -Raw
        $s = $s -replace ('"version":\s*"' + [regex]::Escape($cur) + '"'), ("`"version`": `"$new`"")
        Set-Content $f $s -Encoding UTF8 -NoNewline
    }
    $f3 = Join-Path $gui "src-tauri\Cargo.toml"
    $s3 = Get-Content $f3 -Raw
    $s3 = $s3 -replace ('^version\s*=\s*"' + [regex]::Escape($cur) + '"'), ("version = `"$new`"")
    Set-Content $f3 $s3 -Encoding UTF8 -NoNewline
    $f4 = Join-Path $gui "src-tauri\Cargo.lock"
    $s4 = Get-Content $f4 -Raw
    $s4 = $s4 -replace ('name = "mcnp-ui"[\s\S]*?version = "' + [regex]::Escape($cur) + '"'), ("name = `"mcnp-ui`"`nversion = `"$new`"")
    Set-Content $f4 $s4 -Encoding UTF8 -NoNewline
    $f5 = Join-Path $repo "README.md"
    if (Test-Path $f5) {
        $s5 = Get-Content $f5 -Raw
        $s5 = $s5 -replace ([regex]::Escape("Version-$cur"), "Version-$new")
        Set-Content $f5 $s5 -Encoding UTF8 -NoNewline
    }
    Write-Host "  .. 版本已同步" -ForegroundColor Green
}

# ---------- [2/6] 门禁 (可选) ----------
if (-not $SkipGate) {
    Write-Host "[2/6] 门禁: 后端 pytest + 前端 vitest"
    Push-Location $repo
    python -m pytest tests/ -q
    if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "门禁失败: 后端 pytest 有失败用例" }
    Pop-Location
    Push-Location $gui
    node .\node_modules\vitest\vitest.mjs run
    if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "门禁失败: 前端 vitest 有失败用例" }
    Pop-Location
    Write-Host "  门禁全绿" -ForegroundColor Green
} else {
    Write-Host "[2/6] 跳过门禁 (-SkipGate)"
}

# ---------- [3/6] vite 构建前端 ----------
Write-Host "[3/6] vite 构建前端"
Push-Location $gui
node .\node_modules\vite\bin\vite.js build
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "vite build 失败" }
if (-not (Test-Path (Join-Path $gui "dist\index.html"))) { Pop-Location; Fail "vite 产物缺失: gui\dist\index.html" }
Write-Host "  vite 构建完成" -ForegroundColor Green

# ---------- [4/6] PyInstaller sidecar ----------
Write-Host "[4/6] PyInstaller 打包 sidecar"
python -m PyInstaller --noconfirm mcnp_sidecar.spec
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "PyInstaller 打包 sidecar 失败" }
if (-not (Test-Path (Join-Path $gui "dist\python\python.exe"))) { Pop-Location; Fail "PyInstaller 产物缺失: gui\dist\python\python.exe" }
if (-not (Test-Path (Join-Path $gui "dist\python\_internal\app\preview_cache.py"))) {
    Pop-Location; Fail "spec 自检失败: _internal\app\preview_cache.py 缺失 (spec _keep_py 是否含 preview_cache.py?)"
}
Write-Host "  sidecar 打包完成" -ForegroundColor Green
Pop-Location

# ---------- [5/6] sidecar -> binaries ----------
Write-Host "[5/6] sidecar 替换进 binaries"
$bin = Join-Path $gui "src-tauri\binaries"
if (Test-Path $bin) { Remove-Item $bin -Recurse -Force }
New-Item -ItemType Directory -Path $bin | Out-Null
Copy-Item (Join-Path $gui "dist\python\python.exe") (Join-Path $bin "python-x86_64-pc-windows-msvc.exe") -Force
Copy-Item (Join-Path $gui "dist\python\_internal") (Join-Path $bin "_internal") -Recurse -Force
if (-not (Test-Path (Join-Path $bin "_internal\app\preview_cache.py"))) { Fail "binaries 自检失败: preview_cache.py 缺失" }
Write-Host "  binaries 就绪" -ForegroundColor Green

# ---------- [6/6] tauri build + 无条件覆盖 sidecar (6.2 坑) ----------
Write-Host "[6/6] tauri build (Rust 编译)"
$env:RUSTUP_HOME = "D:\rust\rustup"
$env:CARGO_HOME = "D:\rust\cargo"
Push-Location $gui
node .\node_modules\@tauri-apps\cli\tauri.js build
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "tauri build 失败 (Rust 编译)" }
Pop-Location
$rel = Join-Path $gui "src-tauri\target\release"
if (-not (Test-Path (Join-Path $rel "MCNP 输入卡生成器.exe"))) { Fail "tauri 产物缺失: target\release\MCNP 输入卡生成器.exe" }

# 6.2 坑: tauri 增量编译不会刷新 target\release 的 sidecar, 每次必中。
# 直接把 binaries 新 sidecar 无条件覆盖, 不再人工核对 mtime。
Copy-Item (Join-Path $bin "python-x86_64-pc-windows-msvc.exe") (Join-Path $rel "python.exe") -Force
$relInt = Join-Path $rel "_internal"
if (Test-Path $relInt) { Remove-Item $relInt -Recurse -Force }
Copy-Item (Join-Path $bin "_internal") $relInt -Recurse -Force
Write-Host "  6.2 时效坑已自动处理: 新 sidecar 已覆盖进 target\release" -ForegroundColor Green
Pop-Location

if ($SkipDeploy) {
    Write-Host "构建完成 (-SkipDeploy, 未部署): $rel" -ForegroundColor Yellow
    exit 0
}

# ---------- 部署 ----------
Write-Host "[7] 部署到 $deploy"
Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match "MCNP|python" } | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force -ErrorAction Stop } catch { }
}
Start-Sleep -Seconds 2
if (Test-Path $deploy) { Remove-Item $deploy -Recurse -Force }
New-Item -ItemType Directory -Path $deploy | Out-Null
Copy-Item (Join-Path $rel "MCNP 输入卡生成器.exe") (Join-Path $deploy "MCNP 输入卡生成器.exe") -Force
Copy-Item (Join-Path $rel "python.exe") (Join-Path $deploy "python.exe") -Force
Copy-Item $relInt (Join-Path $deploy "_internal") -Recurse -Force
foreach ($chk in @(
    (Join-Path $deploy "MCNP 输入卡生成器.exe"),
    (Join-Path $deploy "python.exe"),
    (Join-Path $deploy "_internal\app\preview_cache.py"),
    (Join-Path $deploy "_internal\vendor\geouned")
)) {
    if (-not (Test-Path $chk)) { Fail "部署后自检失败: $chk 缺失" }
}
Write-Host "  部署完成" -ForegroundColor Green

# ---------- 冒烟: sidecar 直跑后端, 5001 探活 ----------
Write-Host "[8] 冒烟: sidecar 直跑后端 -> 5001 探活"
$py = Join-Path $deploy "python.exe"
$proc = Start-Process -FilePath $py -WorkingDirectory $deploy -PassThru -WindowStyle Hidden
$ok = $false
try {
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 1
        if ($proc.HasExited) { break }
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:5001/api/xsdir-check" -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) { $ok = $true; break }
        } catch { }
    }
}
finally {
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match "python" } | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force -ErrorAction Stop } catch { }
    }
}
if (-not $ok) { Fail "冒烟失败: 5001 在 90 秒内未就绪 (部署目录不完整 / 杀软拦截)" }
Write-Host "  冒烟通过: 5001 就绪" -ForegroundColor Green

Write-Host ""
Write-Host "==== 发版成功 ====" -ForegroundColor Green
Write-Host "  版本号: $new"
Write-Host "  部署目录: $deploy"
Write-Host "  主程序: $deploy\MCNP 输入卡生成器.exe"
Write-Host "  sidecar: $deploy\python.exe (+ _internal)"
Write-Host "  6.2 sidecar 时效坑: 已自动覆盖, 无需人工核对"
Write-Host "  冒烟: 5001 探活通过"
exit 0
