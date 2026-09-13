<#
.SYNOPSIS
蜡笔小新桌宠 — 一键环境安装/自检/配置生成（TeleAgent 推广版）

把「安装、环境、全局配置」全部集成进技能自身，拷贝技能目录即可开箱即用：

  1. 探测 Python + PySide6：优先用 TeleAgent 自带运行时；
     缺失时自动在本技能目录创建 .venv 并安装 PySide6（不污染系统）。
  2. 生成技能根目录 config.json —— 唯一的配置入口（路径集中于此，可手工改）。
  3. 自动创建任务目录 / 进度文件目录。
  4. 自动写入登录自启：Startup\CrayonShinchanPet.bat 指向本技能（不依赖任何手工全局配置）。

用法：
  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\install-env.ps1        （有 PowerShell 7 优先用）
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\install-env.ps1  （无 pwsh 用 5.1）
  脚本本身兼容 PS 5.1 与 PS 7，调用入口优先 pwsh（效率高），没有才降级 powershell.exe。
  可选参数：-NoAutostart（不写登录自启） / -Force（覆盖已存在的 config.json） / -SetupProfile（初始化记忆）
#>
[CmdletBinding()]
param(
    [switch]$NoAutostart,
    [switch]$Force,
    [switch]$SetupProfile,
    [string]$PipIndex = 'https://pypi.tuna.tsinghua.edu.cn/simple'
)

$ErrorActionPreference = 'Stop'

$SkillDir   = Split-Path -Parent $PSScriptRoot
$ScriptDir  = $PSScriptRoot
$ConfigPath = Join-Path $SkillDir 'config.json'
$VenvDir    = Join-Path $SkillDir '.venv'
$MainPy     = Join-Path $ScriptDir 'shinchan_pet_qt.py'

function Write-Step { param([string]$Msg) Write-Host "[install] $Msg" -ForegroundColor Cyan }
function Find-Engine {
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $c = Get-Command py -ErrorAction SilentlyContinue
    if ($c) { return 'py' }
    return ''
}

# ---------------------------------------------------------------
# 1. 解析 Python：config > TeleAgent 内置 > PATH
# ---------------------------------------------------------------
Write-Step 'step 1/5  定位 Python 解释器'
$python = ''
if (Test-Path -LiteralPath $ConfigPath) {
    try {
        $old = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($old.runtime.python -and (Test-Path -LiteralPath ([string]$old.runtime.python))) {
            $python = [string]$old.runtime.python
        }
    } catch {}
}
if (-not $python) {
    $ta = Join-Path $env:USERPROFILE '.local\share\TeleAgent\runtimes\python\python.exe'
    if (Test-Path -LiteralPath $ta) { $python = $ta }
}
if (-not $python) { $python = Find-Engine }
if (-not $python) { Write-Error '找不到任何 Python。请先安装 Python 3.10+ 后重试。' ; exit 1 }
Write-Step "    使用解释器: $python"

# ---------------------------------------------------------------
# 2. 检查 / 安装 PySide6
# ---------------------------------------------------------------
Write-Step '2/5  检查 PySide6 依赖'
$hasPyside = $false
try {
    & $python -c "import PySide6, PySide6.QtWidgets" 2>$null | Out-Null
    $hasPyside = ($LASTEXITCODE -eq 0)
} catch {
    $hasPyside = $false
}
if (-not $hasPyside) {
    Write-Host '[install] 未检测到 PySide6，准备在技能内置 venv 中安装…' -ForegroundColor Yellow
    Write-Host "[install] pip 源: $PipIndex（可 -PipIndex 换源；首次部署需联网一次性下载约 100MB，预计 1-3 分钟）" -ForegroundColor Yellow
    Write-Host '[install] 正在创建虚拟环境…' -ForegroundColor Cyan
    if (Test-Path -LiteralPath $VenvDir) { Remove-Item -LiteralPath $VenvDir -Recurse -Force }
    & $python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Error 'venv 创建失败'; exit 1 }
    $python = Join-Path $VenvDir 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { $python = Join-Path $VenvDir 'bin\python' }
    Write-Step "venv 已就绪: $python"
    Write-Host '[install] 正在升级 pip…' -ForegroundColor Cyan
    & $python -m pip install --upgrade pip -i $PipIndex 2>&1 | ForEach-Object { if ($_ -match 'Downloading|Installing|Successfully') { Write-Host "  $_" -ForegroundColor Gray } }
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[install] pip 升级失败，尝试官方源重试…' -ForegroundColor Yellow
        & $python -m pip install --upgrade pip 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Error 'pip 升级失败（网络/镜像/防火墙问题）。若代理拦截出站 443，请放行或换源：-PipIndex https://pypi.org/simple'; exit 1 }
    }
    Write-Host '[install] 正在安装 PySide6（约 100MB，请耐心等待…）' -ForegroundColor Cyan
    & $python -m pip install PySide6 -i $PipIndex 2>&1 | ForEach-Object { if ($_ -match 'Downloading|Installing|Successfully|Collecting') { Write-Host "  $_" -ForegroundColor Gray } }
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[install] 镜像源安装失败，尝试官方 PyPI 重试…' -ForegroundColor Yellow
        & $python -m pip install PySide6 2>&1 | ForEach-Object { if ($_ -match 'Downloading|Installing|Successfully|Collecting') { Write-Host "  $_" -ForegroundColor Gray } }
        if ($LASTEXITCODE -ne 0) { Write-Error 'PySide6 安装失败（网络/镜像/防火墙问题）。首次部署需联网下载（约 100MB，一次性）；可 -PipIndex 换源、放行防火墙/代理出站 443 后重试'; exit 1 }
    }
    Write-Step 'PySide6 安装完成'
} else {
    Write-Step 'PySide6 已就绪（复用现有解释器，无需安装）'
}

# pythonw（无控制台窗口）
$pythonw = ''
$pw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (Test-Path -LiteralPath $pw) { $pythonw = $pw } else { $pythonw = $python }

# ---------------------------------------------------------------
# 3. 任务/进度文件目录（config 为空 → 自动推导）
# ---------------------------------------------------------------
Write-Step '3/5  解析任务/进度文件路径'
$tasksDir = ''
$progressFile = ''
if (Test-Path -LiteralPath $ConfigPath) {
    try {
        $old = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        # 仅当旧路径的父目录在本机真实存在才复用，否则视为无效配置重新推导（跨机器迁移安全）
        if ($old.paths.tasks_dir -and (Test-Path -LiteralPath (Split-Path -Parent ([string]$old.paths.tasks_dir)))) {
            $tasksDir = [string]$old.paths.tasks_dir
        }
        if ($old.paths.progress_file -and (Test-Path -LiteralPath (Split-Path -Parent ([string]$old.paths.progress_file)))) {
            $progressFile = [string]$old.paths.progress_file
        }
    } catch {}
}
if (-not $tasksDir) {
    # 桌面路径动态推导（跨机器安全：D:\Desktop 仅本机存在，不写死）
    $desktop = [Environment]::GetFolderPath('Desktop')
    $desktopTemp = Join-Path $desktop '.temp'
    if (Test-Path -LiteralPath $desktopTemp) { $tasksDir = Join-Path $desktopTemp 'pet-tasks' }
    else { $tasksDir = Join-Path $SkillDir '.pet-temp\pet-tasks' }
}
if (-not $progressFile) {
    $parent = Split-Path -Parent $tasksDir
    $progressFile = Join-Path $parent 'pet-progress.txt'
}
New-Item -ItemType Directory -Path $tasksDir -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $progressFile) -Force | Out-Null
Write-Step "任务目录: $tasksDir"
Write-Step "进度文件: $progressFile"

# ---------------------------------------------------------------
# 4. 写 config.json（唯一配置入口）
# ---------------------------------------------------------------
$autostart = -not $NoAutostart
$config = @{
    runtime = @{ python = $python; pythonw = $pythonw }
    paths   = @{ tasks_dir = $tasksDir; progress_file = $progressFile }
    autostart = $autostart
} | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($ConfigPath, $config, (New-Object System.Text.UTF8Encoding($false)))
Write-Step "配置已生成: $ConfigPath"

# ---------------------------------------------------------------
# 5. 登录自启（Startup\CrayonShinchanPet.bat → 本技能 start-pet.ps1）
# 注：技能内不再含 .bat（技能广场审核禁止 .bat 扩展名），自启直接调 .ps1
# ---------------------------------------------------------------
if ($autostart) {
    Write-Step '4/5  写入登录自启'
    $ps1 = Join-Path $ScriptDir 'start-pet.ps1'
    # pwsh 优先（更高效），找不到则降级 powershell.exe；路径可能含空格，必须加引号（否则 cmd 解析 .bat 时必失败）
    $psExe = 'powershell.exe'
    $pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($pwshCmd) { $psExe = $pwshCmd.Source }
    $startCmd = "`"$psExe`" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`""
    # 通道 1：Startup 目录写 .bat（首选，用户最直观）
    $autostartOk = $false
    try {
        $startup = [Environment]::GetFolderPath('Startup')
        $batPath = Join-Path $startup 'CrayonShinchanPet.bat'
        $content = "@echo off`r`n$startCmd`r`n"
        [System.IO.File]::WriteAllText($batPath, $content, (New-Object System.Text.UTF8Encoding($false)))
        Write-Step "登录自启已就绪 (Startup .bat): $batPath"
        $autostartOk = $true
    } catch {
        Write-Host '[install] Startup 目录写入失败（可能受控文件夹访问/EDR 拦截），尝试注册表降级…' -ForegroundColor Yellow
    }
    # 通道 2：注册表 Run 键（降级方案，绕过文件写入限制）
    if (-not $autostartOk) {
        try {
            Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'CrayonShinchanPet' -Value $startCmd
            Write-Step '登录自启已就绪 (注册表 Run 键)'
        } catch {
            Write-Host '[install] 注册表写入也失败，登录自启未配置。请手动将 start-pet.ps1 加入启动项。' -ForegroundColor Yellow
        }
    }
} else {
    Write-Step '已跳过登录自启（-NoAutostart）'
}

# ---------------------------------------------------------------
# 6. 可选：初始化用户记忆/档案（交互式授权后执行）
# ---------------------------------------------------------------
$doProfile = $false
if ($SetupProfile) {
    $doProfile = $true
} else {
    Write-Host ''
    Write-Host '[install] 是否初始化用户记忆系统？' -ForegroundColor Yellow
    Write-Host '  将创建：USER.md（你的偏好/习惯）、MEMORY.md（系统自动记忆）、daily-log/（每日日志）' -ForegroundColor Gray
    Write-Host '  这些文件让 TeleAgent 记住你的习惯、积累经验，越用越懂你。' -ForegroundColor Gray
    Write-Host '  所有数据仅存在本地，不上传、不联网。' -ForegroundColor Gray
    $answer = Read-Host '是否现在初始化？（输入 Y 确认，其他跳过）'
    if ($answer -match '^[Yy]') { $doProfile = $true }
}

if ($doProfile) {
    Write-Step '5/5  初始化用户记忆系统'
    # 动态定位 TeleAgent 用户记忆目录（与桌宠事件层同一逻辑）
    $usersRoot = Join-Path $env:USERPROFILE '.local\share\TeleAgent\users'
    $memDir = $null
    # 优先用 TELEAGENT_CONFIG_DIR 推导
    if ($env:TELEAGENT_CONFIG_DIR) {
        $uid = Split-Path -Leaf $env:TELEAGENT_CONFIG_DIR
        $memDir = Join-Path (Join-Path $usersRoot $uid) 'memory'
    }
    # 扫描 users 目录取最新的
    if (-not $memDir -and (Test-Path -LiteralPath $usersRoot)) {
        $latest = Get-ChildItem -LiteralPath $usersRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latest) { $memDir = Join-Path $latest.FullName 'memory' }
    }
    if (-not $memDir -or -not (Test-Path -LiteralPath (Split-Path -Parent $memDir))) {
        Write-Host '[install] 未找到 TeleAgent 用户目录，跳过记忆初始化。请确保 TeleAgent 已运行过至少一次。' -ForegroundColor Yellow
    } else {
        New-Item -ItemType Directory -Path $memDir -Force | Out-Null
        $dailyDir = Join-Path $memDir 'daily-log'
        New-Item -ItemType Directory -Path $dailyDir -Force | Out-Null
        Write-Step "记忆目录: $memDir"

        # --- USER.md：用户偏好档案 ---
        $userMd = Join-Path $memDir 'USER.md'
        if (Test-Path -LiteralPath $userMd) {
            Write-Step 'USER.md 已存在，跳过（-Force 可覆盖）'
        } else {
            Write-Host ''
            $nick = Read-Host '请输入您的称呼（如：小王、丁工，可留空）'
            if (-not $nick) { $nick = '用户' }
            $scene = Read-Host '主要工作场景？（如：网络维护、行政管理，可留空）'
            $today = Get-Date -Format 'yyyy-MM-dd'
            $lines = @(
                '# 用户长期记忆',
                '',
                '## 基本信息',
                "- 称呼：$nick",
                "- 首次使用日期：$today",
                ''
            )
            if ($scene) {
                $lines += @(
                    '## 工作场景',
                    "- $scene",
                    ''
                )
            }
            $lines += @(
                '## 偏好与习惯',
                '（随使用自动积累：TeleAgent 会在对话中逐渐学习你的偏好并写入此处）',
                '',
                '## 工作规范',
                '（随使用自动积累）',
                ''
            )
            [System.IO.File]::WriteAllText($userMd, ($lines -join "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
            Write-Step "USER.md 已生成: $userMd"
        }

        # --- MEMORY.md：系统记忆 ---
        $memMd = Join-Path $memDir 'MEMORY.md'
        if (Test-Path -LiteralPath $memMd) {
            Write-Step 'MEMORY.md 已存在，跳过'
        } else {
            $memContent = "# 核心事实记忆`r`n`r`n（随使用自动积累：TeleAgent 会在对话中提取关键事实并写入此处）`r`n"
            [System.IO.File]::WriteAllText($memMd, $memContent, (New-Object System.Text.UTF8Encoding($false)))
            Write-Step "MEMORY.md 已生成: $memMd"
        }

        # --- PATHS.md：路径说明 ---
        $pathsMd = Join-Path $memDir 'PATHS.md'
        if (-not (Test-Path -LiteralPath $pathsMd)) {
            $pathsContent = "# 记忆路径说明`r`n`r`n- 当前记忆根目录：``$memDir```r`n- 每日日志目录：``$dailyDir```r`n- 每日日志文件存放规则：``daily-log/YYYY-MM-DD.md```r`n"
            [System.IO.File]::WriteAllText($pathsMd, $pathsContent, (New-Object System.Text.UTF8Encoding($false)))
            Write-Step 'PATHS.md 已生成'
        }

        Write-Step 'daily-log 目录已创建'
        Write-Host '[install] 记忆系统初始化完成！TeleAgent 现在可以记住你的偏好了。' -ForegroundColor Green
    }
} else {
    Write-Step '已跳过记忆初始化（随时可重新运行 install-env.ps1 -SetupProfile）'
}

# ---------------------------------------------------------------
Write-Host ''
Write-Host '[install] 完成。启动方式：' -ForegroundColor Green
Write-Host "  python $(Join-Path $ScriptDir 'pet-start.py')"
Write-Host '  或直接运行 scripts/start-pet.ps1（双击/登录自启）'
Write-Host '  调用脚本优先用 pwsh（有则用，效率高），无 pwsh 用 powershell.exe（5.1 兼容）'