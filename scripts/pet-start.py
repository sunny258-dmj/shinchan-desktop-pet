#!/usr/bin/env python3
"""蜡笔小新桌宠启动器 — 自动挑一个装了 PySide6 的解释器来跑桌宠。

直接双击或命令行运行均可：

    python scripts/pet-start.py              # 后台启动（已运行则不动）
    python scripts/pet-start.py --foreground # 前台运行，方便看报错
    python scripts/pet-start.py --status     # 只看状态，不启动
    python scripts/pet-start.py --stop       # 退出桌宠

启动后桌宠会常驻。任务进度由任务文件/进度文件驱动（见 SKILL.md），无需再做任何操作。
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path

# 禁止写入 .pyc 缓存（技能目录需保持纯净，技能广场审核禁止 .pyc）
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pet_config
from pet_runtime import runtime_root, is_running as instance_running
MAIN = HERE / "shinchan_pet_qt.py"
RUNTIME = runtime_root()
STATE = RUNTIME / "state.json"
PID_FILE = RUNTIME / "host.pid"


def candidates():
    """按优先级列出可能装了 PySide6 的解释器（统一走 pet_config，见 config.json）"""
    out = []
    # 1) pet_config 解析出的解释器（config > TeleAgent 内置 > 当前解释器 > PATH）
    exe = pet_config.python_executable()
    if exe:
        out.append(Path(exe))
    out.append(Path(sys.executable))
    out.append(HERE.parent / '.venv' / 'Scripts' / 'python.exe')
    # 2) 本机 py 启动器 / PATH 里的 python
    out.append(Path("py"))
    out.append(Path("python"))
    # 3) 常见安装位置
    out += sorted((Path.home() / "AppData" / "Local" / "Programs" / "Python").glob("*/python.exe"), reverse=True)
    return out


def has_pyside6(exe: str) -> bool:
    try:
        r = subprocess.run(
            [exe, "-c", "import PySide6, PySide6.QtWidgets"],
            capture_output=True, timeout=60,
        )
        return r.returncode == 0
    except Exception:
        return False


def pick_interpreter(gui=True):
    seen = set()
    for c in candidates():
        key = str(c).lower()
        if key in seen:
            continue
        seen.add(key)
        exe = str(c)
        if c.is_absolute() and not c.exists():
            continue
        if has_pyside6(exe):
            # GUI 程序用 pythonw 启动，避免桌宠背后跟一个黑色控制台窗口
            pw = c.with_name("pythonw.exe") if c.is_absolute() else None
            if gui and pw is not None and pw.exists():
                return str(pw)
            return exe
    return None


def is_running():
    return instance_running(RUNTIME)


def stop():
    try:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"command": "exit"}), encoding="utf-8")
        print("已发送退出指令")
    except Exception as e:
        print(f"退出失败: {e}")


def main():
    args = sys.argv[1:]
    if "--stop" in args:
        stop()
        return 0

    if "--status" in args:
        print(f"桌宠运行中: {is_running()}")
        return 0

    if is_running():
        print("桌宠已在运行，无需重复启动")
        return 0

    foreground = "--foreground" in args
    exe = pick_interpreter(gui=not foreground)
    if not exe:
        print("没找到装了 PySide6 的 Python。请先安装：")
        print("  pip install PySide6")
        return 1

    print(f"使用解释器: {exe}")
    try:
        if foreground:
            return subprocess.call([exe, '-X', 'utf8', '-B', str(MAIN)])
        if os.name == "nt":
            # Windows：用 Start-Process 派生独立进程，避免进程随 agent 命令
            # 结束被沙箱回收（subprocess.Popen 的子进程会挂在命令进程树上）。
            ps = shutil.which("powershell.exe") or "powershell.exe"
            # Start-Process joins ArgumentList: quote the script as one Windows argument.
            quote = lambda s: "'" + s.replace("'", "''") + "'"
            arguments = subprocess.list2cmdline(['-X', 'utf8', '-B', str(MAIN)])
            start = f"Start-Process -FilePath {quote(exe)} -ArgumentList {quote(arguments)} -WindowStyle Hidden"
            result = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-Command', start],
                                    capture_output=True, timeout=20, creationflags=0x08000000)
            if result.returncode:
                print('桌宠启动命令失败')
                return 1
        else:
            subprocess.Popen(
                [exe, str(MAIN)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        # 等一下确认真的起来了
        for _ in range(20):
            time.sleep(0.25)
            if is_running():
                print("桌宠已启动，等待任务文件驱动进度")
                return 0
        print(f"桌宠未能确认启动，请检查 {RUNTIME / 'host-error.log'}")
        return 1
    except Exception as e:
        print(f"启动失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
