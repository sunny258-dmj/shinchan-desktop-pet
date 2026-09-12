<#
.SYNOPSIS
蜡笔小新桌宠 V4 — 智能体/自动化无人值守安装入口。

用途：
- 自动调用 install-env.ps1 完成环境检查与依赖安装；
- 自动对“是否初始化用户记忆”回答 N，避免自动化卡住；
- 安装成功后启动桌宠；
- 适合具备 Windows 命令执行能力的智能体直接运行。

运行：
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\agent-install.ps1
#>
[CmdletBinding()]
param(
    [switch]$NoAutostart
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot
$Install = Join-Path $ScriptDir 'install-env.ps1'
$Start = Join-Path $ScriptDir 'start-pet.ps1'

if (-not (Test-Path -LiteralPath $Install)) {
    throw "缺少安装脚本: $Install"
}
if (-not (Test-Path -LiteralPath $Start)) {
    throw "缺少启动脚本: $Start"
}

Write-Host '[agent-install] 正在无人值守安装蜡笔小新桌宠 V4…' -ForegroundColor Cyan

$args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Install)
if ($NoAutostart) { $args += '-NoAutostart' }

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'powershell.exe'
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $false
$psi.RedirectStandardError = $false
$psi.CreateNoWindow = $false
$psi.Arguments = ($args | ForEach-Object {
    if ($_ -match '[\s"]') { '"' + ($_ -replace '"','\"') + '"' } else { $_ }
}) -join ' '

$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $psi
if (-not $proc.Start()) {
    throw '无法启动环境安装进程。'
}

# install-env.ps1 默认唯一需要用户输入的是“是否初始化用户记忆”。
# 自动化安装明确选择 N；不会修改/创建用户记忆档案。
$proc.StandardInput.WriteLine('N')
$proc.StandardInput.Close()
$proc.WaitForExit()

if ($proc.ExitCode -ne 0) {
    throw "环境安装失败，退出代码: $($proc.ExitCode)"
}

Write-Host '[agent-install] 环境安装完成，正在启动桌宠…' -ForegroundColor Green
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Start
if ($LASTEXITCODE -ne 0) {
    throw "桌宠启动失败，退出代码: $LASTEXITCODE"
}

Write-Host '[agent-install] 安装并启动完成。' -ForegroundColor Green
exit 0
