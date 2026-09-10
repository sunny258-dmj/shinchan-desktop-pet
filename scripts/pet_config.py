#!/usr/bin/env python3
"""蜡笔小新桌宠 — 集中配置模块（TeleAgent 推广版）

所有安装、环境、全局配置全部收敛到技能自身，方便把整个技能目录拷贝推广：

1. **技能根目录 config.json 为唯一配置入口**（由 install-env.ps1 生成，可手工改）：
   {
     "runtime": { "python": "...", "pythonw": "..." },   // 空 = 自动探测
     "paths":   { "tasks_dir": "...", "progress_file": "..." },  // 空 = 自动推导
     "autostart": true
   }
2. **未配置时自动推导**（跨机器兜底）：
   - Python：config > TeleAgent 自带运行时 > 当前解释器 > py/python（PATH）
   - 任务目录/进度文件：config → 环境变量 PET_TASKS_DIR / PET_PROGRESS_FILE
     → 本机约定 D:\\Desktop\\.temp\\...（存在时）→ 技能目录 .pet-temp\\...（兜底）
3. 任何脚本都通过本模块读配置，禁止硬编码本机路径。
"""

import json
import os
import shutil
import sys
from pathlib import Path

# 技能根目录（scripts/ 的上一级）
SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"


def load_config() -> dict:
    """读技能根目录 config.json，失败/不存在返回空 dict。"""
    try:
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(cfg, dict):
                return cfg
    except Exception:
        pass
    return {}


def _cfg_path(cfg: dict, key: str) -> str:
    """从 config 的 paths 段取值（去空白）。"""
    try:
        p = cfg.get("paths", {}).get(key, "")
        return str(p).strip() if p else ""
    except Exception:
        return ""


def _teleagent_runtime() -> Path:
    """TeleAgent 自带 Python 运行时的候选路径（跨用户名推导）。"""
    return Path.home() / ".local" / "share" / "TeleAgent" / "runtimes" / "python"


# ------------------------------------------------------------
# Python 解释器探测
# ------------------------------------------------------------

def python_executable() -> str:
    """返回可用 Python 绝对路径：config > TeleAgent 内置 > 当前解释器 > PATH。"""
    cfg = load_config()
    p = str(cfg.get("runtime", {}).get("python", "")).strip()
    if p and Path(p).exists():
        return p

    # TeleAgent 自带运行时（本机已内置 PySide6 6.x）
    ta = _teleagent_runtime() / "python.exe"
    if ta.exists():
        return str(ta)

    # 当前解释器能用就行（通常就是上面那个）
    try:
        import PySide6  # noqa: F401
        return sys.executable
    except Exception:
        pass

    # PATH 兜底
    for name in ("python", "py"):
        exe = shutil.which(name)
        if exe:
            return exe
    return ""


def pythonw_executable() -> str:
    """pythonw（无控制台窗口）路径；没有则回退到 python。"""
    cfg = load_config()
    p = str(cfg.get("runtime", {}).get("pythonw", "")).strip()
    if p and Path(p).exists():
        return p
    py = python_executable()
    if not py:
        return ""
    pw = Path(py).with_name("pythonw.exe")
    return str(pw) if pw.exists() else py


def has_pyside6(exe: str) -> bool:
    """判断某解释器是否装了 PySide6。"""
    if not exe:
        return False
    try:
        import subprocess
        r = subprocess.run([exe, "-c", "import PySide6, PySide6.QtWidgets"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


# ------------------------------------------------------------
# 任务文件 / 进度文件路径推导
# ------------------------------------------------------------

def _desktop_temp() -> Path:
    """本机约定目录 D:\\Desktop\\.temp（存在才用，不存在回退技能内兜底）。"""
    alt = Path("D:/Desktop/.temp")
    if alt.exists():
        return alt
    return SKILL_DIR / ".pet-temp"


def tasks_dir() -> Path:
    """多任务独立目录（pet-tasks）。"""
    p = _cfg_path(load_config(), "tasks_dir")
    if p:
        return Path(p)
    env = os.environ.get("PET_TASKS_DIR")
    if env:
        return Path(env)
    return _desktop_temp() / "pet-tasks"


def progress_file() -> Path:
    """单气泡进度文件（pet-progress.txt）。"""
    p = _cfg_path(load_config(), "progress_file")
    if p:
        return Path(p)
    env = os.environ.get("PET_PROGRESS_FILE")
    if env:
        return Path(env)
    return _desktop_temp() / "pet-progress.txt"


def autostart_enabled() -> bool:
    cfg = load_config()
    try:
        return bool(cfg.get("autostart", True))
    except Exception:
        return True


# ------------------------------------------------------------
# UI 缩放系数（气泡/字体/桌宠整体尺寸）
# ------------------------------------------------------------

def ui_scale() -> float:
    """UI 缩放系数：config.json 的 ui.scale 字段。

    默认 0.8（比原始 1.0 紧凑，气泡与字体更小）；支持 0.5 ~ 1.2 调节。
    配置示例：{"ui": {"scale": 0.7}}
    """
    cfg = load_config()
    try:
        v = float(cfg.get("ui", {}).get("scale", 0.8))
    except Exception:
        v = 0.8
    if v < 0.5:
        v = 0.5
    if v > 1.2:
        v = 1.2
    return v