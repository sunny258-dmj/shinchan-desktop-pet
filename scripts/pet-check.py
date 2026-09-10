#!/usr/bin/env python3
"""蜡笔小新桌宠 — 部署状态检查（供 agent / 用户在调用技能时自动判断是否需要一键部署）

    python pet-check.py

输出一行状态摘要，供调用方决策：
  [DEPLOYED]  已部署 + 桌宠运行中 → 直接进入任务陪伴
  [READY]     已部署但桌宠未运行 → 只需启动（pet-start.py）
  [NEED_INSTALL] 未部署（缺 config / 缺 PySide6 / 缺 Python）→ 需运行 install-env.ps1
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# 禁止写入 .pyc 字节码缓存（技能目录需纯净，技能广场审核禁止 .pyc）
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pet_config
from pet_runtime import is_running

RUNTIME = Path(os.environ.get("LOCALAPPDATA", "")) / "CrayonShinchanPet"
PID_FILE = RUNTIME / "host.pid"


def pet_running() -> bool:
    return is_running()


def main() -> int:
    cfg = pet_config.load_config()
    configured = bool(cfg) and bool(cfg.get("runtime", {}).get("python"))
    py = pet_config.python_executable()
    pyside = pet_config.has_pyside6(py) if py else False

    if not py or not pyside:
        print(f"[NEED_INSTALL] 技能未配置或依赖缺失（config={'有' if cfg else '无'} python={bool(py)} PySide6={pyside}）")
        print("  请运行: pwsh -NoProfile -ExecutionPolicy Bypass -File <技能目录>\\scripts\\install-env.ps1")
        print("  （无 pwsh 则用 powershell.exe 替代，兼容 PS 5.1）")
        return 2

    if pet_running():
        print("[DEPLOYED] 已部署且桌宠运行中，可直接开始任务陪伴")
        return 0

    print("[READY] 已部署，桌宠未运行 → 启动: python <技能目录>\\scripts\\pet-start.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())
