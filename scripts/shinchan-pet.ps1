[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'show', 'hide', 'state', 'celebrate', 'message', 'status', 'reset-position',
                  'task-add', 'task-update', 'task-complete', 'task-fail', 'task-clear', 'task-list')]
    [string]$Command = 'start',

    [ValidateSet('idle', 'running-right', 'running-left', 'waving', 'jumping', 'failed', 'waiting', 'running', 'review', 'look')]
    [string]$State = 'idle',

    [string]$Message = '',

    # ---- Task params ----
    [string]$TaskName = '',
    [string]$TaskId = '',
    [int]$TaskCurrent = -1,
    [int]$TaskTotal = -1,
    [ValidateSet('pending', 'running', 'completed', 'failed')]
    [string]$TaskStatus = 'running',
    [string]$TaskMessage = ''
)

$ErrorActionPreference = 'Stop'

$runtimeRoot = if ($env:PET_RUNTIME_DIR) { $env:PET_RUNTIME_DIR } else { Join-Path $env:LOCALAPPDATA 'CrayonShinchanPet' }
$statePath = Join-Path $runtimeRoot 'state.json'
$pidPath = Join-Path $runtimeRoot 'host.pid'
$petStartScript = Join-Path $PSScriptRoot 'start-pet.ps1'
$windowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Ensure-RuntimeRoot {
    if (-not (Test-Path -LiteralPath $runtimeRoot)) {
        New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    }
}

function Get-HostProcess {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        return $null
    }
    try {
        $hostPid = [int](Get-Content -LiteralPath $pidPath -Raw)
        return Get-Process -Id $hostPid -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function ConvertTo-OrderedHashtable {
    param($Obj)
    if ($null -eq $Obj) { return $null }
    if ($Obj -is [array] -or ($Obj -is [System.Collections.IList] -and -not ($Obj -is [System.Collections.IDictionary]))) {
        $arr = @()
        foreach ($item in $Obj) { $arr += (ConvertTo-OrderedHashtable $item) }
        return $arr
    }
    if ($Obj -is [System.Management.Automation.PSCustomObject]) {
        $ht = [ordered]@{}
        foreach ($prop in $Obj.PSObject.Properties) {
            $ht[$prop.Name] = (ConvertTo-OrderedHashtable $prop.Value)
        }
        return $ht
    }
    return $Obj
}

function New-DefaultState {
    return [ordered]@{
        state = 'idle'
        visible = $true
        one_shot = $false
        next_state = 'idle'
        command = ''
        reset_position = $false
        message = ''
        tasks = @()
        updated_at_utc = [DateTime]::UtcNow.ToString('o')
    }
}

function Read-FullState {
    if (-not (Test-Path -LiteralPath $statePath)) {
        return New-DefaultState
    }
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
        try {
            $obj = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $ht = ConvertTo-OrderedHashtable $obj
            if ($null -eq $ht) { return New-DefaultState }
            if (-not ($ht -is [System.Collections.IDictionary])) { return New-DefaultState }
            if (-not $ht.Contains('tasks')) { $ht['tasks'] = @() }
            return $ht
        }
        catch {
            if ($attempt -lt 2) { Start-Sleep -Milliseconds 30 }
        }
    }
    return New-DefaultState
}

function Write-StateFile {
    param([string]$Json)
    $tempPath = "$statePath.$PID.$([guid]::NewGuid().ToString('N')).tmp"
    $backupPath = "$statePath.replace-backup"
    [System.IO.File]::WriteAllText($tempPath, $Json, (New-Object System.Text.UTF8Encoding($false)))
    try {
        if (Test-Path -LiteralPath $statePath) {
            Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
            [System.IO.File]::Replace($tempPath, $statePath, $backupPath)
        }
        else {
            [System.IO.File]::Move($tempPath, $statePath)
        }
    }
    finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $backupPath) {
            Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-ProgressMessage {
    param([string]$PetState)
    switch ($PetState) {
        'running' { return '正在执行当前任务…' }
        'review' { return '正在检查任务结果…' }
        'waiting' { return '等待你的确认…' }
        'failed' { return '任务遇到问题，等待处理…' }
        'waving' { return '任务完成，太棒啦！' }
        'jumping' { return '完成啦，开心跳一下！' }
        'running-right' { return '正在赶去处理任务…' }
        'running-left' { return '正在赶去处理任务…' }
        'look' { return '我在看着你哦。' }
        default { return '' }
    }
}

function Write-FullState {
    param([System.Collections.Specialized.OrderedDictionary]$StateData)
    $StateData['updated_at_utc'] = [DateTime]::UtcNow.ToString('o')
    $json = $StateData | ConvertTo-Json -Depth 6
    Write-StateFile -Json $json
}

function Start-Host {
    Ensure-RuntimeRoot
    $existing = Get-HostProcess
    if ($null -ne $existing) {
        return $existing
    }
    if (-not (Test-Path -LiteralPath $petStartScript)) {
        throw "找不到桌宠启动脚本：$petStartScript"
    }
    # 复用 pet-start.py 的启动逻辑（探测解释器 / pythonw / 单实例），
    # 保证与 install-env.ps1、start-pet.ps1 完全一致，不依赖旧 legacy-host.ps1。
    # 等统一启动器返回，避免控制器宣告成功时仍残留启动器进程占用工作目录。
    & $windowsPowerShell -NoProfile -ExecutionPolicy Bypass -File $petStartScript | Out-Null
    if ($LASTEXITCODE -ne 0) { throw '桌宠启动器执行失败。' }
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 100
        $started = Get-HostProcess
        if ($null -ne $started) {
            return $started
        }
    } while ([DateTime]::UtcNow -lt $deadline)
    throw '蜡笔小新桌宠未能在预期时间内启动。'
}

function Derive-PetState {
    param([array]$Tasks, [string]$Fallback = 'idle')
    $hasRunning = $false
    $hasFailed = $false
    $allCompleted = $true
    foreach ($t in $Tasks) {
        $status = if ($t -is [System.Collections.IDictionary]) { [string]$t['status'] } else { [string]$t.status }
        switch ($status) {
            'running' { $hasRunning = $true; $allCompleted = $false }
            'failed' { $hasFailed = $true; $allCompleted = $false }
            'pending' { $allCompleted = $false }
        }
    }
    if ($hasFailed) { return 'failed' }
    if ($hasRunning) { return 'running' }
    if ($allCompleted -and $Tasks.Count -gt 0) { return 'review' }
    return $Fallback
}

# ================================================================
# Main
# ================================================================
Ensure-RuntimeRoot
$st = Read-FullState
$petState = if ($st.state) { [string]$st.state } else { 'idle' }
$visible = if ($null -ne $st.visible) { [bool]$st.visible } else { $true }

switch ($Command) {
    'start' {
        $st = New-DefaultState
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'start'; running = $true; pid = $process.Id; state = 'idle' } | ConvertTo-Json -Compress
    }
    'show' {
        $st['visible'] = $true
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'show'; running = $true; pid = $process.Id; state = $petState } | ConvertTo-Json -Compress
    }
    'hide' {
        $st['visible'] = $false
        Write-FullState $st
        [ordered]@{ ok = $true; command = 'hide'; running = ($null -ne (Get-HostProcess)); state = $petState } | ConvertTo-Json -Compress
    }
    'state' {
        $st['state'] = $State
        $st['visible'] = $true
        $st['one_shot'] = $false
        $st['command'] = ''
        $st['message'] = Get-ProgressMessage -PetState $State
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'state'; running = $true; pid = $process.Id; state = $State } | ConvertTo-Json -Compress
    }
    'celebrate' {
        $st['state'] = 'waving'
        $st['visible'] = $true
        $st['one_shot'] = $true
        $st['next_state'] = 'idle'
        $st['command'] = ''
        $st['message'] = '任务完成，太棒啦！'
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'celebrate'; running = $true; pid = $process.Id; state = 'waving'; next_state = 'idle' } | ConvertTo-Json -Compress
    }
    'message' {
        $st['state'] = $State
        $st['visible'] = $true
        $st['message'] = $Message
        $st['one_shot'] = $false
        $st['command'] = ''
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'message'; running = $true; pid = $process.Id; state = $State; message = $Message } | ConvertTo-Json -Compress
    }
    'reset-position' {
        $st['visible'] = $true
        $st['reset_position'] = $true
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'reset-position'; running = $true; pid = $process.Id; state = $petState } | ConvertTo-Json -Compress
    }
    'status' {
        $process = Get-HostProcess
        $taskCount = if ($st.tasks) { @($st.tasks).Count } else { 0 }
        [ordered]@{
            ok = $true
            command = 'status'
            running = ($null -ne $process)
            pid = if ($null -ne $process) { $process.Id } else { $null }
            state = $petState
            visible = $visible
            message = if ($null -ne $st.message) { [string]$st.message } else { '' }
            task_count = $taskCount
            runtime_root = $runtimeRoot
        } | ConvertTo-Json -Compress
    }
    'stop' {
        $process = Get-HostProcess
        if ($null -ne $process) {
            $st['visible'] = $false
            $st['command'] = 'exit'
            Write-FullState $st
            $process.WaitForExit(3000) | Out-Null
        }
        [ordered]@{ ok = $true; command = 'stop'; running = ($null -ne (Get-HostProcess)); state = $petState } | ConvertTo-Json -Compress
    }

    # ==================== Multi-task commands ====================

    'task-add' {
        $tasks = @()
        if ($st.tasks) { $tasks = @($st.tasks) }
        $newId = if ($TaskId) { $TaskId } else { "t$(Get-Date -Format 'HHmmss')$((Get-Random -Maximum 99).ToString('D2'))" }
        $newTask = [ordered]@{
            id      = $newId
            name    = $TaskName
            status  = $TaskStatus
            current = if ($TaskCurrent -ge 0) { $TaskCurrent } else { 0 }
            total   = if ($TaskTotal -ge 0) { $TaskTotal } else { 0 }
            message = $TaskMessage
        }
        $tasks += $newTask
        $st['tasks'] = $tasks
        $st['visible'] = $true
        $derived = Derive-PetState -Tasks $tasks -Fallback $petState
        $st['state'] = $derived
        $st['message'] = if ($TaskMessage) { $TaskMessage } else { Get-ProgressMessage -PetState $derived }
        $st['one_shot'] = $false
        $st['command'] = ''
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'task-add'; task_id = $newId; running = $true; pid = $process.Id; state = $st['state']; task_count = $tasks.Count } | ConvertTo-Json -Compress
    }

    'task-update' {
        $tasks = @($st.tasks)
        $found = $false
        for ($i = 0; $i -lt $tasks.Count; $i++) {
            if ([string]$tasks[$i].id -eq $TaskId) {
                if ($TaskName) { $tasks[$i].name = $TaskName }
                if ($TaskTotal -ge 0) { $tasks[$i].total = $TaskTotal }
                if ($TaskCurrent -ge 0) { $tasks[$i].current = $TaskCurrent }
                $tasks[$i].status = $TaskStatus
                if ($PSBoundParameters.ContainsKey('TaskMessage')) { $tasks[$i].message = $TaskMessage }
                $found = $true
                break
            }
        }
        if (-not $found) {
            [ordered]@{ ok = $false; command = 'task-update'; error = "Task not found: $TaskId" } | ConvertTo-Json -Compress
            return
        }
        $st['tasks'] = $tasks
        $st['visible'] = $true
        $derived = Derive-PetState -Tasks $tasks -Fallback $petState
        $st['state'] = $derived
        $st['message'] = if ($TaskMessage) { $TaskMessage } else { Get-ProgressMessage -PetState $derived }
        $st['one_shot'] = $false
        $st['command'] = ''
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'task-update'; task_id = $TaskId; running = $true; pid = $process.Id; state = $derived; task_count = $tasks.Count } | ConvertTo-Json -Compress
    }

    'task-complete' {
        $tasks = @($st.tasks)
        $found = $false
        for ($i = 0; $i -lt $tasks.Count; $i++) {
            if ([string]$tasks[$i].id -eq $TaskId) {
                $tasks[$i].status = 'completed'
                $total = [int]$tasks[$i].total
                if ($total -gt 0) { $tasks[$i].current = $total }
                if ($TaskMessage) { $tasks[$i].message = $TaskMessage } else { $tasks[$i].message = '已完成' }
                $found = $true
                break
            }
        }
        if (-not $found) {
            [ordered]@{ ok = $false; command = 'task-complete'; error = "Task not found: $TaskId" } | ConvertTo-Json -Compress
            return
        }
        $st['tasks'] = $tasks
        $st['visible'] = $true
        $derived = Derive-PetState -Tasks $tasks -Fallback 'idle'
        $st['state'] = $derived
        $st['message'] = Get-ProgressMessage -PetState $derived
        $st['one_shot'] = $false
        $st['command'] = ''
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'task-complete'; task_id = $TaskId; running = $true; pid = $process.Id; state = $derived; task_count = $tasks.Count } | ConvertTo-Json -Compress
    }

    'task-fail' {
        $tasks = @($st.tasks)
        $found = $false
        for ($i = 0; $i -lt $tasks.Count; $i++) {
            if ([string]$tasks[$i].id -eq $TaskId) {
                $tasks[$i].status = 'failed'
                if ($TaskMessage) { $tasks[$i].message = $TaskMessage } else { $tasks[$i].message = '执行失败' }
                $found = $true
                break
            }
        }
        if (-not $found) {
            [ordered]@{ ok = $false; command = 'task-fail'; error = "Task not found: $TaskId" } | ConvertTo-Json -Compress
            return
        }
        $st['tasks'] = $tasks
        $st['visible'] = $true
        $st['state'] = 'failed'
        $st['message'] = Get-ProgressMessage -PetState 'failed'
        $st['one_shot'] = $false
        $st['command'] = ''
        Write-FullState $st
        $process = Start-Host
        [ordered]@{ ok = $true; command = 'task-fail'; task_id = $TaskId; running = $true; pid = $process.Id; state = 'failed'; task_count = $tasks.Count } | ConvertTo-Json -Compress
    }

    'task-clear' {
        $st['tasks'] = @()
        $st['state'] = 'idle'
        $st['message'] = ''
        $st['one_shot'] = $false
        $st['command'] = ''
        Write-FullState $st
        [ordered]@{ ok = $true; command = 'task-clear'; running = ($null -ne (Get-HostProcess)); state = 'idle'; task_count = 0 } | ConvertTo-Json -Compress
    }

    'task-list' {
        $tasks = @($st.tasks)
        [ordered]@{
            ok = $true
            command = 'task-list'
            task_count = $tasks.Count
            tasks = $tasks
        } | ConvertTo-Json -Depth 4
    }
}
