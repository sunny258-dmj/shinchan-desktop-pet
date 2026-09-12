# 蜡笔小新桌宠

PySide6 / TeleAgent 桌宠。V4 保留原有任务感知、气泡、确认、多任务、位置保存、启动入口等功能逻辑，重点重做角色形象、UI 与动画系统。

## 给智能体：自动安装并启动

如果你是具备 Windows 文件访问和命令执行能力的智能体，请直接在本仓库根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\agent-install.ps1
```

这个入口专门用于自动化安装：它会检查 Python，必要时创建项目内 `.venv` 并安装 PySide6，生成运行配置、配置登录自启，并在安装完成后启动桌宠。整个过程不需要用户回答交互式问题，也不会自动初始化或修改用户记忆档案。

如果仓库尚未下载，请先 clone / 下载 `main`，然后执行上述命令。仓库为私有仓库时，先使用当前环境已有的 GitHub 授权访问它。普通聊天模型如果没有电脑/终端执行权限，只能提供安装指导，无法实际安装。

人工安装仍可运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-env.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-pet.ps1
```

## V4：高清角色 + 完整场景动作

V4 正式版本位于 `main`。

### 角色渲染

- 实时角色不再使用色键 PNG 抠图。`scripts/pet_puppet.py` 改为 **2× 分辨率矢量/程序化绘制**，每帧直接输出透明 RGBA。
- 头部、眼睛、眉毛、嘴、身体、手臂、腿、鞋、披风和道具分别绘制，轮廓由 Qt 抗锯齿生成，避免白边、洋红溢色、毛边和不同帧抠图抖动。
- 超人装统一为蓝色主体、红披风/领口、黄色英雄徽记和鞋部细节；表情与动作状态连续变化。
- 旧 `puppet-v3.png`、`actions-v2*.png` 以及色键布局已从 V4 清理。`assets/spritesheet.png` 暂时只保留给旧启动/检查接口兼容，实时动画不再依赖它。

### 动作系统

动作定义在 `scripts/pet_scene_motion.py`。V4 不再把场景做成一两帧往返，而是按“预备 → 主动作 → 延展 → 收势”设计完整动作段，并以 30 FPS 连续插值渲染。

- `idle`：约 24 秒，多段待机、左右观察、伸懒腰、整理披风、得意小动作。
- `running`：约 18.6 秒，接到任务、打开电脑、操作、查看任务板、记录、继续工作。
- `thinking`：约 14.6 秒，托腮、换方向思考、抬头、灵光一现、点头确认。
- `review`：约 15.8 秒，拿板、阅读、翻看、做标记、复查、确认。
- `waiting`：约 16.8 秒，注视用户、抬手提示、等待、轻微无聊动作、再次提醒。
- `failed`：约 14.8 秒，愣住、疑惑、检查、摊手、恢复精神。
- `waving`：约 4.9 秒，发现用户、举手、大幅挥手、快速挥手、收势。
- `jumping`：约 4.4 秒，蓄力、起跳、空中展开、落地压缩、回弹、竖拇指。
- `hero-celebrate`：约 6.6 秒，惊喜、蓄力、大跳、英雄落地、竖拇指、整理披风。
- `running-left / running-right`：约 6.4 秒，启动、加速、完整步态、减速、刹车、站稳。
- `look`：眼睛 → 头部 → 身体三级延迟跟随鼠标。

长场景还叠加呼吸、眨眼、披风滞后、手部敲击、脚步起伏等次级运动，减少机械循环感。

### UI

气泡视觉定义在 `scripts/pet_bubble_style.py`，采用已确认的浅色卡通 UI：

- 白色/浅色纸面 + 状态色顶部轻渐变；
- 大圆角、柔和阴影、紧凑气泡尾；
- 工作蓝、思考紫、等待黄、成功绿、异常红；
- 状态图标和右下角轻量网点装饰，不侵入正文区域；
- 单任务、多任务、确认气泡继续复用原有实时内容，不写死消息。

确认窗口、任务卡、右键菜单仍保留原有交互行为，状态颜色与新版气泡保持一致。

## 启动

```powershell
& .\scripts\start-pet.ps1
```

已有 Python + PySide6 时无需额外安装，也不要求预先创建 `config.json`。拖动桌宠会保存位置，双击挥手，右键可切换测试状态；Ctrl+Alt+P 可召回。

## TeleAgent 自动感知

桌宠通过 `scripts/pet_events.py` 增量读取 TeleAgent 会话事件，自动映射到思考、执行、检查、等待、完成和失败状态。事件逻辑与 V4 视觉层解耦，因此本轮重设计不改变原有任务状态判定和多会话行为。

## 气泡确认

通过本技能发起的方案确认可以直接在桌宠气泡中完成：

- **听你的 · 按照推荐来**：提交当前问题指定的推荐选项。
- **我看看 · 我自己确认**：展开问题、选项和说明，自行选择或补充文字，再确认。

没有推荐时快捷提交保持禁用；关闭详情、隐藏桌宠或等待超时都不会默认同意。多个问题继续独立排队。

TeleAgent 应按 [SKILL.md 的交互确认流程](SKILL.md#气泡交互确认) 调用 `pet-confirm.py`。

## V4 测试与视觉检查

回归测试重点检查：

- 所有主要状态都有足够长的完整动作段；
- 一个场景内连续采样应产生大量不同姿态；
- 矢量角色输出为 768×832 透明帧，四角保持透明；
- 不依赖旧 `puppet-v3.png` 也能正常渲染；
- 气泡尾继续跟随人物可见轮廓；
- 原有任务、确认、文件监听、事件状态和启动逻辑继续由既有测试覆盖。

本地运行：

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B tests\render_redesign.py
python -X utf8 -B tests\render_smoke.py
python -X utf8 -B tests\launcher_smoke.py
```

`tests/render_redesign.py` 会生成 `qa/redesign-preview-v4.html`、实际 Qt 组合截图以及各场景采样帧，用于逐帧检查动作连贯性、透明边缘和气泡位置。

## 结构

- `scripts/shinchan_pet_qt.py`：主窗口、状态机接线、任务气泡、事件驱动。
- `scripts/pet_scene_motion.py`：V4 场景动作编排与连续姿态采样。
- `scripts/pet_puppet.py`：V4 2× 矢量角色渲染。
- `scripts/pet_bubble_style.py`：V4 浅色卡通气泡样式。
- `scripts/pet_animation.py`：旧接口兼容层，现在从矢量角色采样，不再加载色键动作图。
- `scripts/pet_events.py`：TeleAgent 会话与任务状态感知。
- `scripts/pet_confirmation_ui.py` / `pet_confirmation.py`：气泡确认交互。
- `scripts/agent-install.ps1`：智能体/自动化无人值守安装入口。
- `tests/`：回归和视觉导出工具。
