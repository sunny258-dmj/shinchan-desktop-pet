# 蜡笔小新桌宠

PySide6 / TeleAgent 桌宠。V8 使用 2026-09-13 提供的六张透明原图重构实时角色，保留任务感知、气泡、确认、多任务、拖动和启动入口。

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

## V8：恐龙装小新原图重构

使用 2026-09-13 15:57 提供的六张 RGBA 原图：待机、鼠标互动、工作、走路、跑步各 12 个姿态，以及 8 个气泡。原文件保存在 `assets/dinosaur-source/`，独立角色 PNG 保存在 `assets/dinosaur-poses/`。

`python -X utf8 -B scripts/build-dinosaur-assets.py` 可从仓库内原图重复构建；开发构建需要 Pillow、NumPy 和 opencv-python，日常运行只需 PySide6。首次导入可加 `--import-from D:/Downloads`。构建器以不透明连通区域区分角色、分配附近表情符号，保留两像素范围内原始半透明边缘，排除远处杂点与跨角色的低透明度连接。保留像素的颜色和透明度不变。

`assets/dinosaur-actions.json` 记录六张原图的校验值、60 个裁切区域和统一画布位置，运行时核对图集哈希。当前渲染入口只读取 dinosaur 系列资源；旧资源留存便于回溯。

- 待机：站立、眨眼、挠头、伸展、揉眼；连续待机 120 秒后进入闭眼休息。
- 工作：平板、敲键盘、思考、记笔记、灵感、整理书本、庆祝和收起电脑。
- 鼠标互动：根据鼠标方向选取疑惑、指向和注视姿态。
- 走路与跑步：独立 12 帧走路序列与快速跑步序列；原图朝左，向右时镜像。右键菜单可分别查看。
- 思考、等待、检查、失败、互动、跳跃和庆祝均引用这次提供的姿态。全部 60 个姿态可被实际动作序列选中。
- 气泡：绿色恐龙边框、蓝色星星、粉色爱心、黄色叶子、绿色叶子、灯泡、爱心图标、紫色思考云。文字区按各素材实际留白计算；爱心图标单独打包作装饰素材。
- 统一每组角色比例与脚底基线，保留原画纹理；仅用轻微整体摆动衔接，不对脸和肢体分条变形。动作仍由原图关键帧切换构成。

预览生成：`python -X utf8 -B tests/render_reference.py`，输出 `qa/dinosaur-v8/index.html`、60 姿态总览、14 组循环动画、气泡总览以及 Qt 角色与气泡组合截图。

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

## 历史 V4 测试与视觉检查

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
- `scripts/pet_reference_renderer.py`：当前 V8 恐龙装原图动作渲染。
- `scripts/pet_puppet.py`：历史 V4 渲染兼容代码。
- `scripts/pet_bubble_style.py`：V4 浅色卡通气泡样式。
- `scripts/pet_animation.py`：旧接口兼容层，现在从矢量角色采样，不再加载色键动作图。
- `scripts/pet_events.py`：TeleAgent 会话与任务状态感知。
- `scripts/pet_confirmation_ui.py` / `pet_confirmation.py`：气泡确认交互。
- `scripts/agent-install.ps1`：智能体/自动化无人值守安装入口。
- `tests/`：回归和视觉导出工具。

气泡按完整文本测量宽高，短句收紧、长文扩展，打字过程中保持尺寸稳定。提醒、疑问、成功等内容自动选图；长错误消息使用圆角粉色气泡，以保留足够文字空间。
