---
name: 蜡笔小新桌宠
description: Desktop pet companion for TeleAgent (蜡笔小新桌宠). Summon and control an animated transparent desktop pet that follows task progress via file-driven bubbles. Use when user mentions 桌宠, 小新, 蜡笔小新, 陪伴, 召唤宠物, 隐藏宠物, 切换桌宠状态, or wants a pet to accompany their work with real-time progress display. Supports idle/working/review/waiting/celebrate/failed states, multi-task independent bubbles (PySide6/Qt), and one-click deployment. Auto-checks deployment status on skill load; installs environment if missing.
name_cn: 蜡笔小新桌宠
description_cn: TeleAgent 蜡笔小新桌宠，多任务动态气泡、实时展示任务进度
create_source: super-agent-skill-creator
---
# 蜡笔小新桌宠

PySide6 (Qt6) 蜡笔小新桌宠，高清透明精灵 + 高频动画状态机 + 漫画风动态气泡 + 自动感知 + 任务文件驱动。所有安装、环境、配置集成在技能内，拷贝即用。

不要下载程序、访问网络或重新生成桌宠素材。使用本 Skill 自带的脚本。

## 自动感知（已恢复）

桌宠常驻后**自动跟随** TeleAgent 工作状态，无需 agent 手动写任务文件。

**原理**：每 250ms 增量读取 `teleagent.db` 的 `part` 表（按 rowid 游标不丢事件），按 `type` 字段映射状态：

运行中的工具还会检查原记录的完成/失败更新；消息角色读取 `message.data.role`，不再通过文本时间字段猜测。`session-status.json` 的 running 保活按会话分别处理，paused / needs_intervention 显示等待。

| part type | 含义 | 桌宠状态 | 气泡内容 |
|---|---|---|---|
| `reasoning` | agent 思考中 | thinking（紫） | 思考中 |
| `tool`（read/grep/glob） | 只读工具 | review（青） | 读取文件/搜索… + 文件名 |
| `tool`（write/edit/powershell） | 写/执行工具 | working（蓝） | 执行命令/编辑文件… + 中文描述或文件名 |
| `step-finish`（reason=stop） | 助手输出完 | done → 招手庆祝 | — |
| `text`（用户消息） | 用户提问 | thinking | 思考中 |

**气泡内容**：气泡外观由 Qt 实时绘制，不使用带固定文字的图片。第一行状态 + 步骤数（如"执行命令 · 第 3 步"），第二行根据实时事件提取具体动作（优先工具 description、文件名或搜索关键词；不显示命令/正文）。只有手动 `state` 命令没有实时事件时，才使用简短的状态兜底文案。

**多会话**：每个会话一个独立气泡（标题 + 状态色），竖向堆叠可折叠，各自独立更新。

**气泡稳定性**：只要 `session-status.json` 中有 running 会话，气泡就不会因短暂无事件而消失；完成/结束后自动回落待机。

**系统内部会话过滤**：标题以 `[skill-evolution]`、`_SYS_` 开头的会话（技能进化 internal、记忆日志等后台系统会话）自动识别并排除——不显示气泡、不参与状态仲裁、不计入活跃会话。

**隐私**：只取结构字段（事件类型、工具名、会话 id、时间戳）+ 工具描述/文件名，命令正文、消息正文一律不读、不存、不显示。

## 气泡交互确认

任务已使用本技能陪伴时，需要用户在普通方案间做选择，可通过
[`scripts/pet-confirm.py`](scripts/pet-confirm.py) 发起本地确认：

- **听你的（按照推荐来）**：只提交当前问题显式指定的推荐选项。
- **我看看（用户自己确认）**：打开完整问题和选项，让用户自行选择并提交；关闭面板不作答。
- 没有明确推荐时，“听你的”不可点；多项确认按 ID 分开，可切换查看。

先确保桌宠运行，再写一个 UTF-8 JSON 问题文件（使用任务自己的临时目录）：

```json
{
  "title": "气泡配色",
  "question": "气泡要用哪种颜色？推荐小新黄，和桌宠更搭。",
  "options": [
    {"id": "yellow", "label": "小新黄", "description": "和角色衣服协调"},
    {"id": "blue", "label": "清爽蓝", "description": "更安静的视觉效果"}
  ],
  "recommended": "yellow",
  "allow_custom": true
}
```

用已有 Python 执行以下脚本，路径按当前技能实际位置展开：

```powershell
python <技能目录>\scripts\pet-confirm.py create --file <问题文件绝对路径> --ttl 600
python <技能目录>\scripts\pet-confirm.py wait --id <create返回的id> --seconds 55
```

`create` 返回 `id/status`。`wait` 最多等待 55 秒，适配工具调用超时；读取 JSON 的 `status`，不要仅凭命令成功推断用户同意：

| status | 退出码 | 后续动作 |
|---|---|---|
| answered | 0 | 按 `answer.option_id` 或自定义 `answer.text` 继续；仅对这个问题有效 |
| pending | 2 | 用户尚未回答；用同一个 ID 继续 wait，依赖该答案的工作暂停 |
| expired / cancelled | 3 | 未获确认；停止依赖操作，需要时重新询问 |
| error | 1 | 说明错误，回到正常提问流程 |

`recommended` 可省略或为 null；它必须是已有选项 ID，不能靠“第一项”猜推荐。题目最多 4000 字、2–8 个选项。问题只用于展示文本和收集选择，**不支持执行回调或命令**。任务取消/改问时运行 `pet-confirm.py cancel --id <id>` 撤回旧题，不可自动填答案或修改运行目录中的答复文件。每个问题默认 10 分钟有效，过期不默认同意；等待超时不代表用户回答。

**适用范围**：这是本技能的确认通道，需要 agent 主动调用上述脚本；并非自动接管 TeleAgent 的原生 question 工具、工具权限、安全审查、登录或系统权限弹窗。这些继续使用原应用的确认流程，不通过桌宠规避权限检查。当前版本 TeleAgent 的本机 HTTP 回复接口要求应用内部签名，桌宠不读取凭据或修改应用来绕过它。

**隐私补充**：仅在主动发起这类确认时读取、展示并暂存该问题、选项及用户选择，保存在本机运行目录的 `confirmations` 中；普通自动感知仍不读取消息正文。答复记录保留供调用方读取。

## 界面尺寸调节

气泡、气泡内字体与桌宠本体大小通过 `config.json` 的 `ui.scale` 统一缩放（默认 `0.8`，范围 `0.5` ~ `1.2`）：

```json
{ "ui": { "scale": 0.8 } }
```

- 调小（如 `0.6`）：更小巧；调大（如 `1.0`）：回到原始比例
- 修改后需重启桌宠生效（右键桌宠 → 退出，再运行 `scripts/shinchan_pet_qt.py`）
- 气泡尾尖按人物可见轮廓贴近头顶（默认比例约 4px），不再按透明窗口边界定位；随动作帧更新。

## 排查工具

桌宠异常时用以下脚本定位（均只读、不联网）：

- `scripts/pet-status.py`：查看桌宠"眼里"的当前状态（`--watch` 持续跟踪），用于确认自动感知是否正常工作、气泡内容是否正确。
- `scripts/pet-log.py`：查看与桌宠相同的结构化事件、工具描述和文件名（`-n 20` / `--watch`），不打印思考或消息正文。
- `scripts/pet-check.py`：部署状态检查（`DEPLOYED` / `READY` / `NEED_INSTALL` 三态）。

## 自动部署（调用技能时自动执行）

加载本 Skill 即运行 `scripts/pet-check.py` 检查部署状态：

| 状态 | 含义 | 自动动作 |
|---|---|---|
| `DEPLOYED` | 已部署 + 运行中 | 直接进入任务陪伴 |
| `READY` | Python + PySide6 已就绪、未运行（config.json 可选） | 自动启动桌宠 |
| `NEED_INSTALL` | 未部署/依赖缺失 | 询问用户 → 运行 `install-env.ps1` → 启动 |

**权限确认点**（涉及系统级操作时先用提问工具确认）：
- 写登录自启 `Startup\CrayonShinchanPet.bat`（系统级更改）
- 无 PySide6 时在技能 `.venv` 内 `pip install PySide6`（联网安装）
- 其余（生成 config.json、建目录、启动）静默执行

## 一键安装

新机器或 `NEED_INSTALL` 时执行：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File <技能目录>\scripts\install-env.ps1
# 有 PowerShell 7 (pwsh) 优先用（效率高）；没有 pwsh 则用 powershell.exe（兼容 5.1）
# -NoAutostart 跳过登录自启；-Force 覆盖已有配置；-PipIndex https://pypi.org/simple 换 pip 源
# -SetupProfile 跳过交互直接初始化记忆系统
```

自动完成：Python 探测（优先 TeleAgent 内置，缺则建 venv 装 PySide6）→ 生成 config.json → 建任务目录 → 写登录自启。

安装结束后会交互式询问是否初始化用户记忆系统（输入 Y 确认）。授权后自动创建：
- **USER.md**：用户偏好档案（交互输入称呼、工作场景，随使用自动积累习惯和规范）
- **MEMORY.md**：系统核心事实记忆（随对话自动积累）
- **daily-log/**：每日日志目录（TeleAgent 自动写入每日对话摘要）
- **PATHS.md**：记忆路径说明

所有记忆数据仅存在本地，不上传、不联网。跳过后随时可重新运行 `install-env.ps1 -SetupProfile` 补建。

**首次部署说明（全新机器）**：TeleAgent 自带 Python 运行时，但**不带 PySide6**；首次安装需联网一次性下载（约 100MB，默认走清华镜像源）。Windows 防火墙默认放行出站 HTTPS，通常无需配置；若企业防火墙/代理拦截出站 443 导致 pip 失败，放行或换源后重试。安装完成后完全离线运行，不联网、不对外端口。

## 启动

```powershell
python <技能目录>\scripts\pet-start.py
# --status 查状态 / --stop 退出 / --foreground 前台调试
```

已运行则静默跳过（操作系统文件锁保证单实例；host.pid 供诊断）。也可运行 `scripts/start-pet.ps1` 或 `python scripts/pet-start.py`。所有启动入口复用同一启动器，支持带空格的项目路径。

## 状态控制

`shinchan-pet.ps1` 写 state.json 控制桌宠；`-Command start` / `show` 复用同一启动器。`state.json` 中的 `tasks` 数组会同步到独立任务气泡。

```powershell
$Ctl = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\shinchan-pet.ps1'
# 切换状态
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl -Command state -State running
# 庆祝（结束后自动回 idle）
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl -Command celebrate
# 消息气泡
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl -Command message -State running -Message '正在处理（2/4）'
# 显示/隐藏/退出/查询
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl -Command show|hide|stop|status
```

## 多任务命令

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl -Command task-add -TaskName '处理数据' -TaskTotal 4
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl -Command task-update -TaskId 't01...' -TaskCurrent 2 -TaskStatus running -TaskMessage '去重中…'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl -Command task-complete -TaskId 't01...'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl -Command task-clear
```

## 多任务独立文件驱动（推荐）

往任务目录写文件，桌宠自动显示独立气泡。多任务并行各自独立，竖向堆叠，默认折叠。

**目录**：`<config.json paths.tasks_dir>`（默认 `D:\Desktop\.temp\pet-tasks`）

**文件格式**：

```
# 纯文本 <任务名>.txt
正在读取数据…
[2/5]正在归因
[完成]报告已生成

# JSON <任务名>.json
{"status":"running","current":2,"total":4,"message":"正在归因"}
```

状态值：`running`(蓝) `thinking`(紫) `completed`(绿) `failed`(红) `pending`(灰)

**心跳约定**：每完成关键步骤重写文件刷新心跳。正常结束删除文件。>15 秒未更新自动视为中断消失。

```powershell
$dir = 'D:\Desktop\.temp\pet-tasks'  # 以 config.json 为准
[System.IO.File]::WriteAllText((Join-Path $dir '读取CSV.txt'), '正在读取…', (New-Object System.Text.UTF8Encoding($false)))
Remove-Item -LiteralPath (Join-Path $dir '读取CSV.txt') -Force  # 结束
```

## 进度文件驱动（单气泡）

**路径**：`<config.json paths.progress_file>`（默认 `D:\Desktop\.temp\pet-progress.txt`）

纯文本 → 气泡消息；JSON `{state,message,tasks[]}` → 多任务面板。写空或删除即退出驱动回待机。

## 任务联动工作流

**默认：自动感知已恢复，桌宠自动跟随任务状态。** 不需要在提示词里写"先召唤桌宠"，不需要在任务过程中逐条切换状态。

只有以下情况需要主动下命令：
- 桌宠还没启动 → 执行 `start` 召唤一次（之后一直常驻）。
- 想让桌宠做特定动作（庆祝、招手、跳跃）→ 用 `celebrate` / `state`。

### 多步骤任务（推荐）

1. 开始任务前 `start` 召唤桌宠（已运行则跳过）。
2. 桌宠自动从 teleagent.db 增量读取，跟随每一步工具调用。
3. 全部完成后自动 `celebrate`（招手庆祝）回待机。

### 简单任务

1. `start` → 桌宠自动跟随。
2. 需要强制指定状态时：`state -State running/review/waiting/failed`。
3. 成功 → `celebrate`（自动回 idle）。

桌宠控制是陪伴效果，不得替代任务执行或进度说明。不在回复中逐条播报控制命令。

## state 值

`idle` `running` `review` `waiting` `failed` `waving` `jumping` `running-left` `running-right` `look`

## 交互

- 左键拖动改变位置（位置保存）
- 双击招手
- 右键菜单
- `Ctrl+Alt+P` 召回到鼠标所在屏幕
- 仅本机运行，不联网，不读工作区内容

## 图片与验证

- 原始素材保留在 `assets/spritesheet.png`。它的实际人物位置并非等分网格，因此必须同时携带 `assets/spritesheet-layout.json`；宿主按该文件校正取帧、边距与落脚位置，并校验素材哈希。
- 原图缺少可信的正上/正下凝视帧；鼠标处于垂直方向时回到正面。左右跟随已按画面方向修正，不使用背影替代向下看。
- 待机、工作、思考、等待、检查、跳跃采用新绘六组 49 帧动作，读取 `actions-v2-keyed.png` 和 `actions-v2-layout.json`；必须随技能携带。运行时 Qt 去底色。左右跑动、凝视、失败仍用原 PNG。
- 新版预览：`qa/redesign-preview.html`，可暂停逐帧检查；`tests/render_redesign.py` 从实际 Qt 宿主导出预览。
- `qa/animation-preview.html`：原版/修复后的动画对比，可选择动作、暂停、切换背景。
- 测试：使用已装 PySide6 的 Python 执行 `-X utf8 -B -m unittest discover -s tests -v`；`tests/render_smoke.py` 验证 Qt 实际绘制、气泡展开和双击挥手。
- 隔离测试可指定 `PET_RUNTIME_DIR`、`PET_TASKS_DIR`、`PET_PROGRESS_FILE` 与 `TELEAGENT_DB`。正常使用无需设置。
