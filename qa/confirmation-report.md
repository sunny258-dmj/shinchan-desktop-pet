# 气泡交互确认检查（2026-09-09）

已新增“听你的 / 我看看”两条交互路径，使用项目现有的本地文件通信模式。

## 实际行为

- “听你的”提交当前题目显式推荐的选项 ID。
- “我看看”展示完整问题、选项说明和可选的自定义输入；用户再点“确认选择”后才提交。
- 关闭详情、隐藏桌宠、等待超时均不视为同意。
- 多个请求独立编号，可切换；提交后的短暂防连点保护避免连续答到下一题。
- 点击时重读并核对请求内容；过期、取消、已作答或内容变化的请求无法再次提交。
- 确认期间收起普通进度气泡；确认结束恢复显示与动画。

## 验证证据

- `confirmation-tests.txt`：34 项全部通过，其中新增 14 项确认测试。
- 跨进程检查：等待脚本收到 Qt 按钮点击返回的对应 ID、选项和来源，退出码为 0。
- 启动入口回归：含空格/单引号路径、重复启动、停止清理及 PowerShell 入口，全部通过。
- `confirmation-bubble.png`、`confirmation-review.png`：真实 Qt 控件渲染，已检查中文文字和按钮布局。
- 最新 `pet-check.py` 返回 `[DEPLOYED]`，新版宿主已运行。
- `confirmation-changes.patch` 和 `before-confirmation.zip` 保存本轮差异和此前脚本。

## 接入范围与限制

TeleAgent 必须按 SKILL.md 调用 `pet-confirm.py create/wait` 来发起并接收这类确认。这是普通方案选择通道，不自动拦截原生 question、工具权限、安全审查、登录或系统权限弹窗。

本机安装包中可查到 `/question/{requestID}/reply` 等接口，但实际读取返回 HTTP 401；应用通过内部会话签名调用。未提取凭据、修改 TeleAgent 或绕过签名。本轮界面工具仅能看到云电脑客户端，未能在 TeleAgent UI 内执行新功能的端到端实测。此前 `teleagent-test.txt` 的 14 项记录属于前一轮，不代表本轮确认功能已获 TeleAgent 实测。

通用 Codex skill 校验器不接受此项目原有的 TeleAgent frontmatter 字段（name_cn、description_cn、create_source）；未把 TeleAgent 技能强改成 Codex 格式。已用 YAML 解析确认文件语法和新增脚本引用。
