# 蜡笔小新桌宠

## 气泡与动作重设计

- 气泡轮廓按状态变化：工作采用倾斜六边框与闪电尾，思考采用连续云朵与圆泡尾，等待确认采用折角便签，完成采用不规则放射轮廓，异常采用细锯齿边。上方空间不足时尾巴翻转；确认按钮和正文保留独立安全区域。绘制逻辑位于 `scripts/pet_bubble_style.py`。

- 气泡新增五套状态主题：工作蓝色闪电、思考淡紫圆点、等待暖黄时钟、完成绿色星光、异常珊瑚红提醒；共享漫画网点、纸面内框、顶部色边和状态胶囊。确认按钮保留原交互。[样式预览](qa/bubble-styles.png)

- 气泡按当前人物的可见轮廓定位，尾尖与头顶相距约 4 像素；消息、确认和多任务统一奶油底与深色漫画描边。每次动作换帧重新对齐，拖动同步跟随。
- 新绘六组动作，共 49 帧：待机伸展、敲键检查、托腮思考、抬手等待、查看记录、蓄力跳跃。每组 8 帧，工作 9 帧；按动作阶段设置停顿。招呼与英雄庆祝复用新动作，左右跑动、凝视、失败暂用原素材。
- [新版动画播放与逐帧检查](qa/redesign-preview.html) / [实际组合截图](qa/redesign-companion.png)。预览使用宿主实际读取的透明帧。
- 原素材保留；新素材为 `assets/actions-v2-keyed.png`，其定位信息在 `assets/actions-v2-layout.json`。运行时去除专用底色和边缘杂色，不增加 Pillow 依赖。


独立的 TeleAgent / PySide6 桌宠。原始形象素材已保留，修复后的程序通过实测，可从以下入口启动：

```powershell
& .\scripts\start-pet.ps1
```

已有 Python + PySide6 时无需安装，也不要求先创建 config.json。拖动保存位置，双击挥手，右键切换状态；Ctrl+Alt+P 召回。如果快捷键被其他软件占用，可使用 `shinchan-pet.ps1 -Command reset-position`。

## 气泡确认按钮

通过本技能发起的方案确认，现在可以直接在气泡里选择：

- **听你的 · 按照推荐来**：提交当前问题指定的推荐选项。
- **我看看 · 我自己确认**：展开问题、选项和说明，自行选择或补充文字，再点“确认选择”。

没有推荐时禁用快捷提交；关掉详情、隐藏桌宠或等待超时都不会默认同意。多个问题独立排队，连续点击不会连答下一题。后台任务气泡在确认期间暂时收起。

需要 TeleAgent 按 [SKILL.md 的交互确认流程](SKILL.md#气泡交互确认) 调用 `pet-confirm.py`。此功能不自动接管 TeleAgent 原生提问或权限弹窗；原生权限仍在原应用确认。

实际 Qt 界面：[气泡](qa/confirmation-bubble.png) / [完整选项](qa/confirmation-review.png)。新增确认测试覆盖点击、手动选择、超时、重复提交、多问题和进程间答复。

## 2026-09-09 修复

- **图片取帧**：原图 3072×4576 的人物位置没有对齐均匀网格，导致切头、串行。新增 `assets/spritesheet-layout.json`，记录 88 帧的实际取图区域与显示位置，运行时绘制到透明帧中。原 PNG 未修改。
- **动画**：修正左右跟随；垂直方向使用正面，避免误用背影。减少待机闪动；工作不再突然站起，等待不再躺倒，循环避开装饰物被切断的源帧。
- **事件**：rowid 分页避免同毫秒事件遗漏；跟踪工具原记录中的完成/失败更新；消息角色使用真实字段；按会话保活，清理完成状态和旧工具文案。
- **气泡与控制**：相同状态也能更新消息和步数；隐藏同步隐藏气泡；接通 state.json 的多任务列表；进度文件独立工作；清空时收回任务卡；多气泡避免重叠，跟随桌宠所在显示器。
- **启动**：统一 Python/PowerShell 入口；使用操作系统文件锁防止双开；修复把 Python 脚本交给 PowerShell 执行的问题；支持空格和单引号路径；退出释放日志和实例锁。
- **显示**：中文文字按完整内容计算高度；任务卡提高背景不透明度；动态内容按纯文本显示；位置保存与召回补齐。

## 测试与检查材料

- [详细检查报告](qa/检查报告.md)
- [动画前后对比](qa/animation-preview.html)（在本地浏览器中打开）
- [修复后的实际播放帧](qa/qt-played-frames.png)
- [本地 20 项回归测试](qa/tests-after.txt)
- [TeleAgent 实际执行记录](qa/teleagent-test.txt)（第一轮 14 项，全部通过）
- [启动入口测试](qa/launcher-test.txt)
- [修改差异](qa/changes.patch) / [原脚本备份](qa/original-scripts.zip)

原素材没有完整、准确的上/下凝视姿势，因此本次不宣称实现完整八方向凝视。多气泡超出屏幕容量时会隐藏放不下的卡片，未增加滚动列表。自动跟随仅接入 TeleAgent。

复测使用已有 PySide6 的 Python：

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B tests\render_smoke.py
python -X utf8 -B tests\launcher_smoke.py
```

图片检查脚本 `scripts/inspect-assets.py` 另需 Pillow，桌宠日常运行不需要 Pillow。
