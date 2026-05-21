# H AI量化平台 — 环境初始化脚本
# 用法: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== H AI量化平台 — 环境初始化 ===" -ForegroundColor Cyan

# 检查 Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python 未安装或不在 PATH 中" -ForegroundColor Red
    exit 1
}

# 创建虚拟环境
$venvPath = Join-Path $ProjectRoot ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "[INFO] 创建虚拟环境..." -ForegroundColor Yellow
    python -m venv $venvPath
    Write-Host "[OK] 虚拟环境已创建: $venvPath" -ForegroundColor Green
} else {
    Write-Host "[OK] 虚拟环境已存在" -ForegroundColor Green
}

# 激活并安装依赖
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
. $activateScript
pip install -r (Join-Path $ProjectRoot "requirements.txt") --quiet
Write-Host "[OK] 依赖安装完成" -ForegroundColor Green

# 创建必要目录
$dirs = @("data", "data\logs", "data\cache")
foreach ($d in $dirs) {
    $p = Join-Path $ProjectRoot $d
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
}

Write-Host "=== 初始化完成 ===" -ForegroundColor Cyan
