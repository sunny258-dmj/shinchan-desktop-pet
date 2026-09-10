# 蜡笔小新桌宠 — 动态启动入口（供登录自启调用，兼容 PS 5.1 / pwsh 7）
# 一切路径按技能自身推导：config.json（install-env.ps1 生成）> TeleAgent 内置 > PATH。
$ErrorActionPreference = 'SilentlyContinue'

$SkillDir  = Split-Path -Parent $PSScriptRoot
$ScriptDir = $PSScriptRoot
$ConfigPath = Join-Path $SkillDir 'config.json'
$MainPy     = Join-Path $ScriptDir 'shinchan_pet_qt.py'

$pythonw = ''
if (Test-Path -LiteralPath $ConfigPath) {
    try {
        $cfg = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($cfg.runtime.pythonw) { $pythonw = [string]$cfg.runtime.pythonw }
        elseif ($cfg.runtime.python) { $pythonw = [string]$cfg.runtime.python }
    } catch {}
}
if (-not $pythonw) {
    $ta = Join-Path $env:USERPROFILE '.local\share\TeleAgent\runtimes\python\pythonw.exe'
    if (Test-Path -LiteralPath $ta) { $pythonw = $ta }
}
if (-not $pythonw) {
    Write-Host '未找到 Python 运行环境。请先运行: powershell.exe -ExecutionPolicy Bypass -File scripts\install-env.ps1'
    exit 1
}

# 所有入口复用启动器的单实例、依赖探测和启动结果检查。
$consolePython = Join-Path (Split-Path -Parent $pythonw) 'python.exe'
if (-not (Test-Path -LiteralPath $consolePython)) { $consolePython = $pythonw }
& $consolePython -X utf8 -B (Join-Path $PSScriptRoot 'pet-start.py')
exit $LASTEXITCODE
