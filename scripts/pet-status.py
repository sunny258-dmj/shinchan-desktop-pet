#!/usr/bin/env python3
"""蜡笔蜡笔小新状态探针 — 看看桌宠"眼里"的 TeleAgent 现在在干嘛。

不依赖 Qt，不启动界面，纯命令行。用来验证自动感知是否正常工作：

    python pet-status.py            # 看一眼当前状态
    python pet-status.py --watch    # 持续跟踪（每 2 秒刷新）
"""

import sys
import os
import time

# 禁止写入 .pyc 字节码缓存（技能目录需保持纯净，技能广场审核禁止 .pyc）
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pet_events import TranscriptWatcher, SessionTracker, STATE_LABEL
import pet_config

# 状态 → 控制台配色（Windows 10+ 支持 ANSI）
COLORS = {
    "thinking": "\033[35m",   # 紫
    "working":  "\033[36m",   # 青
    "review":   "\033[34m",   # 蓝
    "waiting":  "\033[33m",   # 黄
    "done":     "\033[32m",   # 绿
    "failed":   "\033[31m",   # 红
    "idle":     "\033[90m",   # 灰
}
RESET = "\033[0m"

BAR = {
    "thinking": "思索",
    "working":  "执行",
    "review":   "查看",
    "waiting":  "等你",
    "done":     "完成",
    "failed":   "出错",
    "idle":     "待机",
}


def render(tracker: SessionTracker) -> str:
    state, info = tracker.resolve()
    c = COLORS.get(state, "")
    label = info.get("label") or STATE_LABEL.get(state) or ""
    n = info.get("sessions", 0)
    extra = f"  ({n} 个会话)" if n > 1 else ""
    steps = info.get("steps", 0)
    if steps and state in ("working", "review"):
        extra += f"  第 {steps} 步"
    return f"{c}● {BAR.get(state, state):4s}{RESET} {label}{extra}"


def main():
    watch = "--watch" in sys.argv or "-w" in sys.argv
    w = TranscriptWatcher()
    t = SessionTracker()

    print("蜡笔蜡笔小新状态探针 — 读取 TeleAgent 事件库 + 任务文件目录")
    print("=" * 58)

    # 定位任务目录
    try:
        tasks_dir = pet_config.tasks_dir()
    except Exception:
        tasks_dir = None

    def count_task_files():
        """扫描任务文件目录，返回 (总数, 详细列表)。"""
        if not tasks_dir or not tasks_dir.exists():
            return 0, []
        out = []
        for f in tasks_dir.iterdir():
            if f.is_file() and f.suffix in ('.txt', '.json'):
                out.append(f.stem)
        return len(out), out

    # 先跑一轮，对齐当前状态
    w._scan_titles()
    for ev in w.poll():
        t.on_event(ev)

    try:
        while True:
            for ev in w.poll():
                t.on_event(ev)
            titles = w.titles
            tasks = t.resolve_tasks(titles)
            active = len(w._active_sessions() or [])
            # 活跃会话详情：来自会话跟踪器（已过滤系统内部会话）
            sid_names = " ".join(
                f"[{tk['name']}]" for tk in tasks[:3]
            )
            line = render(t)
            task_count, task_names = count_task_files()
            scope = f"  {active} 活跃 / {len(tasks)} 事件气泡"
            if task_count:
                scope += f" / {task_count} 任务气泡"
                if task_names:
                    scope += " " + " ".join(f"[{n}]" for n in task_names[:3])
            if sid_names:
                scope += f"  {sid_names}"
            sys.stdout.write("\r\033[K" + line + scope)
            sys.stdout.flush()
            if not watch:
                break
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())