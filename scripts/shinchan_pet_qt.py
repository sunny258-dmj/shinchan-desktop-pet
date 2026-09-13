#!/usr/bin/env python3
"""蜡笔小新桌宠 — PySide6 高清动画版
架构：透明窗口 + 精灵图动画 + 状态机 + 任务文件驱动 + 多任务独立气泡 + 心跳超时
"""
# 禁止写入 .pyc 缓存：技能目录需保持纯净（技能广场审核禁止 .pyc 扩展名）
import sys
sys.dont_write_bytecode = True

import os
import json
import time
import signal
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QFrame, QMenu
)
from PySide6.QtCore import (
    Qt, QTimer, QRect, QRectF, QPoint, QPointF, QByteArray, QPropertyAnimation,
    QEasingCurve, QSize, QPropertyAnimation, Signal, QFileSystemWatcher, QAbstractNativeEventFilter
)
from PySide6.QtGui import (
    QPixmap, QPainter, QImage, QColor, QFont, QCursor, QAction,
    QIcon, QPainterPath, QRegion, QPen, QBrush, QLinearGradient
)
# 事件接入层（TeleAgent 会话事件 → 桌宠状态机）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pet_config import (
    tasks_dir as _pet_tasks_dir, progress_file as _pet_progress_file, ui_scale
)
from pet_runtime import InstanceLock
from pet_confirmation_ui import ConfirmationController
from pet_scene_motion import SCENES, BASE, sample as sample_scene, duration as scene_duration, mix as mix_pose
from pet_reference_renderer import Puppet, playback_duration
from pet_bubble_style import palette as bubble_palette
from pet_art_bubbles import draw_bubble, content_theme, INSETS, artwork
from pet_events import (
    SessionTracker, TranscriptWatcher, STATE_ANIM, STATE_LABEL, TOOL_LABEL as TOOL_LABEL_PET
)

# ============================================================
# 路径常量
# ============================================================
SKILL_DIR = Path(__file__).resolve().parent.parent
ATLAS_PATH = SKILL_DIR / "assets" / "spritesheet.png"
ICON_PATH = SKILL_DIR / "assets" / "avatar.png"
LAYOUT_PATH = SKILL_DIR / "assets" / "spritesheet-layout.json"
_ATLAS_LAYOUTS = {}
RUNTIME_ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "CrayonShinchanPet"
RUNTIME_ROOT = Path(os.environ.get("PET_RUNTIME_DIR", str(RUNTIME_ROOT)))
STATE_PATH = RUNTIME_ROOT / "state.json"
PID_PATH = RUNTIME_ROOT / "host.pid"
LOG_PATH = RUNTIME_ROOT / "host-error.log"
POSITION_PATH = RUNTIME_ROOT / "position.json"
# 任务/进度文件路径：由 pet_config 统一解析（config.json > 环境变量 > 本机约定 > 技能内兜底）
PROGRESS_PATH = _pet_progress_file()
TASKS_DIR = _pet_tasks_dir()

# ============================================================
# 精灵图规格
# ============================================================
ATLAS_COLS = 8
ATLAS_ROWS = 11
FRAME_W = 192
FRAME_H = 208
DISPLAY_SCALE = 1.25  # 角色整体放大，气泡仍按内容独立计算尺寸

# 全局 UI 缩放（气泡/字体/桌宠尺寸），config.json 的 ui.scale 可调（0.5~1.2，默认 0.8）
UI_SCALE = ui_scale()
# 桌宠整体显示缩放 = 基准显示缩放 × UI 缩放
PET_SCALE = DISPLAY_SCALE * UI_SCALE


def _ui_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """按 UI_SCALE 缩放的字号（不小于 6pt，避免缩放后无法阅读）"""
    f = QFont("Microsoft YaHei UI")
    f.setPointSizeF(max(6.0, round(size * UI_SCALE, 2)))
    f.setWeight(weight)
    return f


def _ui_px(value: float) -> int:
    """按 UI_SCALE 缩放的像素值（布局留白/圆角/间距等）"""
    return max(1, int(round(value * UI_SCALE)))

ANIMATIONS = {
    name: {'row': i, 'durations': [1000 / 30] * round(playback_duration(name) * 30), 'source': 'dinosaur-v8'}
    for i, name in enumerate(SCENES)
}

STATE_MESSAGES = {
    "idle": "",
    "running": "正在执行当前任务…",
    "review": "正在检查任务结果…",
    "waiting": "等待你的确认…",
    "failed": "任务遇到问题，等待处理…",
    "waving": "任务完成，太棒啦！",
    "jumping": "完成啦，开心跳一下！",
    "running-right": "正在赶去处理任务…",
    "running-left": "正在赶去处理任务…",
    "walking-left": "散步一下～",
    "walking-right": "散步一下～",
    "look": "我在看着你哦。",
    "thinking": "正在思考…",
    "hero-celebrate": "任务完成！",
}

VALID_STATES = {"idle", "running", "review", "waiting", "failed",
                "waving", "jumping", "running-right", "running-left", "walking-left", "walking-right", "look", "thinking", "hero-celebrate"}

# 任务心跳超时（秒）
TASK_STALE_SEC = 15

# ============================================================
# TeleAgent 自动感知开关
# ============================================================
# TeleAgent 的会话数据在 teleagent.db 的 part 表，含实时 type（reasoning/tool/text/
# step-finish）和 tool 名字。pet_events.py 已适配为增量查 SQLite。
# 自动感知已恢复：桌宠常驻进程每 250ms 增量读 part 表，自动跟随任务状态。
AUTO_PERCEPTION_ENABLED = True

# ============================================================
# 自动感知与轮询参数
# ============================================================
# 手动命令（state.json）优先于自动感知的时长（秒）
MANUAL_GRACE_SEC = 15
# 事件轮询间隔（毫秒）。增量读取，开销极小，250ms 人眼已无感。
TRANSCRIPT_POLL_MS = 250
# "完成"去抖（毫秒）：agent 一轮里常穿插多条消息，延迟确认再庆祝
DONE_DEBOUNCE_MS = 2000
# 打字机节奏：每次推进的间隔与字数
TYPEWRITER_TICK_MS = 24
TYPEWRITER_STEP = 2


def log(msg: str):
    """写错误日志"""
    try:
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
    except Exception:
        pass


def load_atlas() -> QPixmap:
    """加载精灵图（支持 1x=192x208 与 2x=384x416 帧的高清图源）"""
    if not ATLAS_PATH.exists():
        raise FileNotFoundError(f"找不到小新超人精灵图：{ATLAS_PATH}")
    pixmap = QPixmap(str(ATLAS_PATH))
    if pixmap.isNull() or (pixmap.width(), pixmap.height()) not in ((1536, 2288), (3072, 4576)):
        raise ValueError(f"精灵图尺寸错误：{pixmap.width()}x{pixmap.height()}")
    if LAYOUT_PATH.exists():
        import hashlib
        layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
        if layout["source_size"] == [pixmap.width(), pixmap.height()]:
            if layout["source_sha256"] != hashlib.sha256(ATLAS_PATH.read_bytes()).hexdigest():
                raise ValueError("精灵图已更换，请重新校验 spritesheet-layout.json 的取帧区域")
            _ATLAS_LAYOUTS[pixmap.cacheKey()] = layout
    return pixmap


def crop_frame(atlas: QPixmap, row: int, col: int) -> QPixmap:
    """从精灵图中裁剪一帧（帧尺寸 = 图源宽高 / 8x11，自动适配高清版）"""
    if not (0 <= row < ATLAS_ROWS and 0 <= col < ATLAS_COLS):
        raise ValueError(f"非法精灵帧: {row}, {col}")
    layout = _ATLAS_LAYOUTS.get(atlas.cacheKey())
    if layout:
        frame = QPixmap(*layout["frame_size"])
        frame.fill(Qt.GlobalColor.transparent)
        cell = layout["rows"][row][col]
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(QRect(*cell["target"]), atlas, QRect(*cell["source"]))
        painter.end()
        return frame
    fw = atlas.width() // ATLAS_COLS
    fh = atlas.height() // ATLAS_ROWS
    return atlas.copy(col * fw, row * fh, fw, fh)


def look_column(dx, dy):
    """现有底稿是转身图：仅使用可靠的左右姿势，垂直方向回正面。

    row 9 的 3/7 是背影，不能冒充俯视/仰视帧。
    """
    if abs(dx) < 12 or abs(dy) > abs(dx) * 1.8:
        return 0
    if dx > 0:
        return 1 if dy < -abs(dx) * 0.5 else 2
    return 6 if dy < -abs(dx) * 0.5 else 5


# ============================================================
# 气泡窗口（单任务/简单消息）
# ============================================================
# 状态 → 主题色（圆点 / 胶囊 / 描边 / 竖条统一用这套）
STATE_UI_COLORS = {
    "running": "#1687ff", "working": "#1687ff",
    "thinking": "#8a5cf6", "review": "#19b978",
    "waiting": "#f4a623", "completed": "#35c759", "done": "#35c759",
    "cancelled": "#8fa8c4", "failed": "#ff4d5f", "pending": "#8fa8c4", "idle": "#78a8d8",
}


def _hex_rgba(color: str, alpha: int) -> str:
    """'#3b82f6' + 30 → 'rgba(59,130,246,30)'"""
    c = color.lstrip("#")
    return f"rgba({int(c[0:2], 16)},{int(c[2:4], 16)},{int(c[4:6], 16)},{alpha})"


class BubbleCard(QWidget):
    """气泡卡片：自绘圆角矩形 + 底部小尾巴（指向桌宠），状态色描边"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tail_x = -1          # 尾巴顶点 x（卡内坐标；-1 = 居中）
        self.tail_up = False      # True = 气泡在桌宠下方，尾巴朝上
        self.show_tail = True
        self._accent = "#3b82f6"
        self.art_theme = None

    def set_accent(self, color: str):
        if color != self._accent:
            self._accent = color
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        draw_bubble(p, self.rect(), self._accent, self.tail_up, self.art_theme)
        p.end()



class BubbleWindow(QWidget):
    """消息气泡 — 白卡 + 状态色 + 指向桌宠的小尾巴 + 柔和投影

    两种形态：
    - set_message()：单段文本（手动消息 / 进度驱动）
    - set_structured()：状态行(圆点+状态词+步数胶囊) + 摘录行(状态色竖条，打字机)
    """
    CARD_W = 300
    M_L, M_R, M_T, M_B = 24, 24, 18, 34   # 窗口四周留白：容纳投影与尾巴

    def __init__(self, parent_pet):
        super().__init__()
        self.pet = parent_pet
        # 实例级缩放尺寸（随 UI_SCALE 收缩）
        self.CARD_W = max(180, int(300 * UI_SCALE))
        self.M_L, self.M_R = _ui_px(10), _ui_px(10)
        self.M_T, self.M_B = _ui_px(8), _ui_px(8)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        self._msg = ""
        self._snippet_full = ""
        self._structured = False
        self._last_key = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.M_L, self.M_T, self.M_R, self.M_B)

        self.card = BubbleCard()
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(int(10 * UI_SCALE))
        shadow.setOffset(0, int(3 * UI_SCALE))
        shadow.setColor(QColor(65, 43, 25, 45))
        self.card.setGraphicsEffect(shadow)

        cl = QVBoxLayout(self.card)
        self._card_layout = cl
        cl.setContentsMargins(_ui_px(34), _ui_px(45), _ui_px(34), _ui_px(30))
        cl.setSpacing(_ui_px(7))

        # 头行：状态圆点 + 状态词 + 步数胶囊
        head = QHBoxLayout()
        head.setSpacing(_ui_px(6))
        self.dot = QLabel()
        self.dot.setFixedSize(_ui_px(10), _ui_px(10))
        self.dot.setStyleSheet("background:#1687ff;border-radius:%dpx;" % _ui_px(5))
        head.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status_label = QLabel()
        self.status_label.setFont(_ui_font(11, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color:#17304f;background:transparent;")
        head.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addStretch(1)
        self.step_pill = QLabel()
        self.step_pill.setFont(_ui_font(9, QFont.Weight.Bold))
        self.step_pill.setVisible(False)
        head.addWidget(self.step_pill, 0, Qt.AlignmentFlag.AlignVCenter)
        cl.addLayout(head)

        # 摘录行：左侧状态色竖条 + 灰色摘录（打字机逐字上屏）
        self.snippet_label = QLabel()
        self.snippet_label.setFont(_ui_font(10))
        self.snippet_label.setWordWrap(True)
        # 顶部对齐：只裁底部，不裁第一行上半截
        self.snippet_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.snippet_label.hide()
        cl.addWidget(self.snippet_label)

        # simple 模式：单段文本
        self.label = QLabel()
        self.label.setFont(_ui_font(11, QFont.Weight.DemiBold))
        self.label.setStyleSheet("color:#17304f;background:transparent;")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.hide()
        cl.addWidget(self.label)

        outer.addWidget(self.card)
        for label in (self.label, self.snippet_label, self.status_label, self.step_pill):
            label.setTextFormat(Qt.TextFormat.PlainText)
        self.setFixedSize(self.CARD_W + self.M_L + self.M_R, 112)

    # ---- 模式 ----
    def _set_mode(self, structured: bool):
        self._structured = structured
        for wgt in (self.dot, self.status_label):
            wgt.setVisible(structured)
        self.snippet_label.setVisible(structured and bool(self._snippet_full))
        self.label.setVisible((not structured) and bool(self._msg))
        if not structured:
            self.step_pill.hide()

    # ---- 尺寸 ----
    def _label_height(self, label: QLabel, text: str, width: int) -> int:
        fm = label.fontMetrics()
        return max(fm.height(), fm.boundingRect(QRect(0, 0, width, 10000), Qt.TextFlag.TextWordWrap, text).height()) + 2

    def _apply_size(self, content_h: int):
        w = self.CARD_W + self.M_L + self.M_R
        left, top, right, bottom = INSETS[self.card.art_theme]
        art = artwork(self.card.art_theme)
        body_h = max(1, content_h - _ui_px(75))
        card_h = max(int(body_h / (1-top-bottom)) + _ui_px(12),
                     round(self.CARD_W * art.height() / art.width()))
        h = card_h + self.M_T + self.M_B
        screen = QApplication.screenAt(self.pet.geometry().center()) or self.pet.screen()
        if screen:
            max_h = int(screen.availableGeometry().height() * 0.55)
            h = min(h, max_h)
        if (w, h) != (self.width(), self.height()):
            self.setFixedSize(w, h)
        self._apply_art_margins()

    def _apply_art_margins(self):
        left, top, right, bottom = INSETS[self.card.art_theme or 'working']
        if self.card.tail_up:
            top, bottom = bottom, top
        card_h = self.height()-self.M_T-self.M_B
        self._card_layout.setContentsMargins(round(self.CARD_W*left), round(card_h*top),
                                            round(self.CARD_W*right), round(card_h*bottom))

    def _body_width(self):
        left, _, right, _ = INSETS[self.card.art_theme or 'working']
        return max(20, int(self.CARD_W * (1-left-right))-4)

    def _fit_content(self, text, accent, structured=False):
        self.card.art_theme = content_theme(text, accent)
        fm = (self.snippet_label if structured else self.label).fontMetrics()
        longest = max((fm.horizontalAdvance(line) for line in text.splitlines()), default=0)
        screen = QApplication.screenAt(self.pet.geometry().center()) or self.pet.screen()
        limit = min(_ui_px(430), screen.availableGeometry().width() - self.M_L - self.M_R - 12)
        minimum = _ui_px(260 if structured else 155)
        # Measure the full message, so the typewriter does not resize every letter.
        left, _, right, _ = INSETS[self.card.art_theme]
        self.CARD_W = min(limit, max(minimum, int((longest+4)/(1-left-right))))
        self.card.update()

    def set_message(self, msg: str, height_hint: str = None, accent: str = "#1687ff"):
        """simple 模式：单段文本。宽度固定、高度完全自适应内容。

        height_hint：按完整文本预计算高度，窗口尺寸稳定不逐字跳动。
        """
        if msg == self._msg and not self._structured and self.isVisible():
            return
        self._msg = msg
        self._snippet_full = ""
        self._last_key = None
        self._set_mode(False)
        self.card.set_accent(accent)
        src = height_hint if height_hint is not None else msg
        self._fit_content(src, accent)
        body = self._label_height(self.label, src, self._body_width()) if msg else 18
        self.label.setText(msg)
        # 21 = 卡片上下边距（10 + 11）
        self._apply_size(body + _ui_px(75))

    def set_structured(self, status: str, color: str, step_text: str, shown: str, full: str):
        """structured 模式：状态行 + 摘录行。

        shown=打字机当前进度文本，full=摘录全文（高度按全文预计算，打字时窗口不跳）。
        """
        key = (status, color, step_text, shown, full)
        if key == self._last_key and self.isVisible():
            return
        self._last_key = key
        self._msg = ""
        self._snippet_full = full or ""
        self._set_mode(True)
        self.card.set_accent(color)
        self._fit_content(status + ' ' + step_text + '\n' + (full or ''), color, True)
        self.dot.setStyleSheet(f"background:{color};border-radius:{_ui_px(4)}px;")
        self.status_label.setText(status)
        self.status_label.setStyleSheet(
            f"color:#26364a;background:{_hex_rgba(color, 24)};"
            f"border:1px solid {_hex_rgba(color, 55)};"
            f"border-radius:{_ui_px(8)}px;padding:{_ui_px(2)}px {_ui_px(7)}px;")
        if step_text:
            self.step_pill.setText(step_text)
            self.step_pill.setStyleSheet(
                f"color:{color};background:{_hex_rgba(color, 28)};"
                f"border-radius:{_ui_px(10)}px;padding:{_ui_px(2)}px {_ui_px(9)}px;"
            )
            self.step_pill.setVisible(True)
        else:
            self.step_pill.setVisible(False)
        if full:
            self.snippet_label.setStyleSheet(
                f"color:#253047;background:transparent;"
                f"border-left:{_ui_px(3)}px solid {color};padding-left:{_ui_px(9)}px;"
            )
            self.snippet_label.setText(shown)
            self.snippet_label.setVisible(True)
        else:
            self.snippet_label.clear()
            self.snippet_label.setVisible(False)
        # 头行高 + 间距(5) + 摘录高 + 卡片上下边距(21)
        head_h = max(_ui_px(26), self.status_label.fontMetrics().height() + _ui_px(6))
        body = self._label_height(self.snippet_label, self._snippet_full,
                                  self._body_width() - _ui_px(12)) if self._snippet_full else 0
        self._apply_size(head_h + (_ui_px(7) if body else 0) + body + _ui_px(75))

    def position_near_pet(self):
        """定位在桌宠上方，尾巴顶点对准桌宠中心"""
        pet_geo = self.pet.visual_geometry()
        gap = _ui_px(3)   # 气泡与桌宠的间距（紧凑贴合）
        x = pet_geo.center().x() - self.M_L - int(self.CARD_W * .94)
        y = pet_geo.top() - self.height() + self.M_B - gap
        # 确保不超出屏幕
        screen = (QApplication.screenAt(pet_geo.center()) or self.pet.screen()).availableGeometry()
        self.card.tail_up = y < screen.top() + 4
        self._apply_art_margins()
        if self.card.tail_up:
            y = pet_geo.bottom() - self.M_T + gap
        y = max(screen.top() + 4, min(y, screen.bottom() - self.height() - 4))
        x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
        self.move(x, y)
        self.card.tail_x = pet_geo.center().x() - x - self.M_L
        self.card.update()


# ============================================================
# 任务卡片气泡（多任务独立气泡）
# ============================================================
class TaskBubble(QWidget):
    """单个任务的独立气泡 — 竖向堆叠，默认折叠只显标题行，点击展开详情"""

    BUBBLE_W = 278                                  # 卡片宽
    M_L, M_R, M_T, M_B = 18, 18, 10, 14             # 窗口留白（容纳投影）

    def __init__(self, task_id: str, name: str):
        super().__init__()
        self.task_id = task_id
        self.task_name = name
        # 实例级缩放尺寸（随 UI_SCALE 收缩）
        self.BUBBLE_W = max(160, int(278 * UI_SCALE))
        self.M_L, self.M_R = _ui_px(18), _ui_px(18)
        self.M_T, self.M_B = _ui_px(10), _ui_px(14)
        self._expanded = False
        self._status = "running"
        self._message = ""
        self._current = 0
        self._total = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.M_L, self.M_T, self.M_R, self.M_B)

        self.frame = BubbleCard()
        self.frame.setObjectName("task-card")
        self.frame.setStyleSheet(f"""
            QFrame#task-card {{
                background: rgba(239, 248, 255, 252);
                border: {_ui_px(2)}px solid rgba(22, 135, 255, 0.70);
                border-radius: {_ui_px(17)}px;
            }}
        """)
        self.frame.setToolTip("点击展开/折叠")
        shadow = QGraphicsDropShadowEffect(self.frame)
        shadow.setBlurRadius(int(32 * UI_SCALE))
        shadow.setOffset(0, int(6 * UI_SCALE))
        shadow.setColor(QColor(45, 75, 135, 50))
        self.frame.setGraphicsEffect(shadow)

        fl = QVBoxLayout(self.frame)
        fl.setContentsMargins(_ui_px(15), _ui_px(15), _ui_px(28), _ui_px(22))
        fl.setSpacing(_ui_px(4))

        # 标题行：状态点 + 任务名 + 进度胶囊 + 展开箭头
        header = QHBoxLayout()
        header.setSpacing(_ui_px(6))

        self.dot = QLabel()
        self.dot.setFixedSize(_ui_px(8), _ui_px(8))
        self.dot.setStyleSheet(f"background:#3b82f6;border-radius:{_ui_px(4)}px;")
        header.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self.name_label = QLabel(name)
        self.name_label.setFont(_ui_font(10, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color:#1f2937;background:transparent;")
        self.name_label.setMaximumWidth(_ui_px(154))
        header.addWidget(self.name_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self.status_label = QLabel()
        self.status_label.setFont(_ui_font(9, QFont.Weight.Bold))
        self.status_label.setVisible(False)
        header.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.arrow_label = QLabel("+")
        self.arrow_label.setFont(_ui_font(9))
        self.arrow_label.setStyleSheet("color:#9ca3af;background:transparent;")
        header.addWidget(self.arrow_label, 0, Qt.AlignmentFlag.AlignVCenter)

        fl.addLayout(header)

        # 详情区（折叠时隐藏）
        self.detail_widget = QWidget()
        dl = QVBoxLayout(self.detail_widget)
        dl.setContentsMargins(0, _ui_px(2), 0, 0)
        dl.setSpacing(1)

        self.msg_label = QLabel()
        self.msg_label.setFont(_ui_font(10))
        self.msg_label.setStyleSheet(
            f"color:#253047;background:transparent;"
            f"border-left:{_ui_px(3)}px solid #1687ff;padding-left:{_ui_px(9)}px;"
        )
        self.msg_label.setWordWrap(True)
        self.msg_label.setMaximumWidth(self.BUBBLE_W - _ui_px(44))
        dl.addWidget(self.msg_label)

        self.detail_widget.hide()
        fl.addWidget(self.detail_widget)

        outer.addWidget(self.frame)
        for label in (self.name_label, self.msg_label, self.status_label):
            label.setTextFormat(Qt.TextFormat.PlainText)
        self.setFixedSize(self.BUBBLE_W + self.M_L + self.M_R, 42)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._expanded = not self._expanded
            if self._expanded:
                self.detail_widget.show()
                self.arrow_label.setText("−")
            else:
                self.detail_widget.hide()
                self.arrow_label.setText("+")
            self._resize_for_state()
            # 通知主窗口重新布局
            if self.window().__class__.__name__ == "PetWindow":
                self.window()._layout_task_bubbles()
            else:
                # 找到 PetWindow
                app = QApplication.instance()
                for w in app.topLevelWidgets():
                    if w.__class__.__name__ == "PetWindow":
                        w._layout_task_bubbles()
                        break

    def _resize_for_state(self):
        fm = self.msg_label.fontMetrics()
        text = self._message if self._expanded and self._message else self.task_name
        measured = max((fm.horizontalAdvance(line) for line in text.splitlines()), default=0)
        screen = self.screen().availableGeometry()
        self.BUBBLE_W = min(_ui_px(420), screen.width() - self.M_L - self.M_R - 12,
                            max(_ui_px(230), measured + _ui_px(90)))
        w = self.BUBBLE_W + self.M_L + self.M_R
        if self._expanded and self._message:
            fm = self.msg_label.fontMetrics()
            msg_h = min(int(screen.height()*.5), fm.boundingRect(QRect(0, 0, self.BUBBLE_W - _ui_px(56), 10000), Qt.TextFlag.TextWordWrap, self._message).height() + _ui_px(4))
            self.setFixedSize(w, _ui_px(24) + _ui_px(4) + msg_h + _ui_px(37) + self.M_T + self.M_B)
        elif self._expanded:
            self.msg_label.setText("(无详细信息)")
            self.setFixedSize(w, _ui_px(24) + _ui_px(4) + _ui_px(18) + _ui_px(37) + self.M_T + self.M_B)
        else:
            self.setFixedSize(w, _ui_px(24) + _ui_px(37) + self.M_T + self.M_B)

    def update_task(self, name: str, status: str, current: int, total: int, message: str):
        self.task_name = name
        self._status = status
        self._message = message
        self._current = current
        self._total = total

        self.name_label.setText(self.name_label.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, _ui_px(140)))
        self.name_label.setToolTip(name)
        self.msg_label.setText(message)

        # 胶囊内容：有进度显示 2/5，否则显示状态词
        status_text = ""
        if total > 0:
            status_text = f"{current}/{total}"
        elif status == "thinking":
            status_text = "思考中"
        elif status in ("running", "working"):
            status_text = "执行中"
        elif status == "review":
            status_text = "检查中"
        elif status == "waiting":
            status_text = "等你确认"
        elif status in ("completed", "done"):
            status_text = "完成"
        elif status == "failed":
            status_text = "失败"
        if status_text:
            self.status_label.setText(status_text)
            self.status_label.setVisible(True)
        else:
            self.status_label.setVisible(False)

        c = STATE_UI_COLORS.get(status, STATE_UI_COLORS["running"])
        self.frame.set_accent(c)
        self.frame.art_theme = content_theme(status_text + ' ' + message, c)
        self.dot.setStyleSheet(f"background:{c};border-radius:{_ui_px(4)}px;")
        self.frame.setStyleSheet(f"""
            QFrame#task-card {{
                background: rgba(248, 250, 253, 248);
                border: {_ui_px(2)}px solid {_hex_rgba(c, 180)};
                border-radius: {_ui_px(17)}px;
            }}
        """)
        self.status_label.setStyleSheet(
            f"color:{c};background:{_hex_rgba(c, 28)};"
            f"border-radius:{_ui_px(10)}px;padding:{_ui_px(2)}px {_ui_px(9)}px;"
        )
        self.msg_label.setStyleSheet(
            f"color:#253047;background:transparent;"
            f"border-left:{_ui_px(3)}px solid {c};padding-left:{_ui_px(9)}px;"
        )
        self.name_label.setStyleSheet("color:#1f2937;background:transparent;")
        self._resize_for_state()


# ============================================================
# 桌宠主窗口
# ============================================================
class PetWindow(QWidget):
    """桌宠主窗口 — 透明窗口 + 精灵图帧动画 + 状态机"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 默认位置（右下角）
        self.setWindowTitle("蜡笔小新桌宠")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self._pet_visible = True
        screen = QApplication.primaryScreen().availableGeometry()
        dw = int(FRAME_W * PET_SCALE)
        dh = int(FRAME_H * PET_SCALE)
        self.setFixedSize(dw, dh)
        self.move(screen.right() - dw - 28, screen.bottom() - dh - 28)
        self._drag_offset = QPoint()
        self._dragging = False

        # 精灵图帧
        self.atlas = None
        self._frames_cache = {}
        self._current_frame = None

        # 动画状态
        self._state = "idle"
        self._frame_index = 0
        self._one_shot = False
        self._next_state = "idle"

        # 简单气泡
        self._bubble = None
        self._confirmations = None

        # 任务气泡
        self._task_bubbles = {}  # id -> TaskBubble
        self._task_last_sig = ""
        self._auto_bubble_sig = ""   # 自动多会话气泡签名（防抖用）

        # ---- 自动感知：增量读取 TeleAgent 事件，无需手动唤醒 ----
        self._tracker = SessionTracker()
        self._watcher_tp = TranscriptWatcher()
        self._auto_state = "idle"
        self._manual_until = 0.0     # 手动命令的优先级保护期
        self._last_state_mtime = 0.0
        self._auto_active = False    # 事件驱动接管气泡时，抑制默认状态文案
        self._bubble_text = ""       # 气泡当前完整文本（去重 + 打字机进度源）
        self._auto_prefix = ""       # 自动气泡第一行：状态文案
        self._auto_snippet = ""      # 自动气泡第二行：最近思考摘录（跨状态保留）
        self._auto_state = None      # 自动气泡当前状态（取主题色用）
        self._auto_steps = 0         # 自动气泡步数（胶囊显示用）
        self._progress_active = False  # 进度文件驱动是否处于激活态
        self._state_tasks = []
        self._file_tasks = []
        self._progress_signature = None
        self._auto_render_signature = None
        self._bubble_owner = None    # 当前气泡归属：None/manual/auto
        self._tw_pos = 0
        self._poll_events = 0         # 1 分钟窗口内处理的事件数（活性自检）
        self._last_alive_log = time.time()
        # 启动时 state.json 若已存在，记下它的 mtime 作为基线——
        # 否则首次检查会把它误判为"新手动命令"，白白抑制自动感知 15 秒
        try:
            self._last_state_mtime = STATE_PATH.stat().st_mtime
        except Exception:
            self._last_state_mtime = 0.0
        # 事件轮询：每 250ms 增量读取，人眼无感，且只读开销可忽略
        self._tp_timer = QTimer(self)
        self._tp_timer.timeout.connect(self._poll_transcripts)
        self._tp_timer.setInterval(250)

        # 完成去抖：agent 一轮里常穿插多条消息，延迟确认避免反复庆祝
        self._done_timer = QTimer(self)
        self._done_timer.setSingleShot(True)
        self._done_timer.setInterval(DONE_DEBOUNCE_MS)
        self._done_timer.timeout.connect(self._confirm_done)

        # 打字机：思考摘录逐字上屏，模拟"输出中"的效果
        self._tw_timer = QTimer(self)
        self._tw_timer.setInterval(TYPEWRITER_TICK_MS)
        self._tw_timer.timeout.connect(self._tw_tick)

        # ---- 文件系统监听：文件一变立即刷新，不再靠轮询 ----
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(lambda _p: self._scan_tasks())
        self._watcher.fileChanged.connect(self._on_watched_file)
        self._init_watcher()

        # 计时器
        self._anim_timer = QTimer(self)
        self._anim_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        # state.json 是低频控制通道，1s 足够
        self._state_check_timer = QTimer(self)
        self._state_check_timer.timeout.connect(self._check_state)
        self._state_check_timer.setInterval(1000)
        # 任务扫描降为兜底 + TTL 衰减检查，主路径已由 watcher 驱动
        self._task_scan_timer = QTimer(self)
        self._task_scan_timer.timeout.connect(self._scan_tasks)
        self._task_scan_timer.setInterval(3000)

        # 初始化精灵图
        self._puppet = Puppet(SKILL_DIR / 'assets')
        self._scene_pose = dict(BASE)
        self._scene_epoch = time.monotonic()
        self._entry_pose = dict(BASE)
        self._gaze = (0., 0.)
        self._gaze_head = (0., 0.)
        frame = self._puppet.render(sample_scene('idle', 0.))
        self._current_frame = frame

        self._mouse_pos = QCursor.pos()
        self._look_timer = QTimer(self)
        self._look_timer.timeout.connect(self._update_look)
        self._look_timer.setInterval(33)

        self._init_label()
        self._init_context_menu()

        self._set_state("idle")
        self._restore_position()
        self._confirmations = ConfirmationController(self, BubbleWindow, RUNTIME_ROOT)

    def _confirmation_active(self):
        return bool(self._confirmations and self._confirmations.active)

    def closeEvent(self, event):
        if self._confirmations:
            self._confirmations.close()
        super().closeEvent(event)

    def _restore_position(self):
        try:
            obj = json.loads(POSITION_PATH.read_text(encoding="utf-8"))
            target = QRect(int(obj["x"]), int(obj["y"]), self.width(), self.height())
            if any(s.availableGeometry().contains(target) for s in QApplication.screens()):
                self.move(target.topLeft())
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def _save_position(self):
        try:
            POSITION_PATH.parent.mkdir(parents=True, exist_ok=True)
            POSITION_PATH.write_text(json.dumps({"x": self.x(), "y": self.y()}), encoding="utf-8")
        except OSError as e:
            log(f"save position: {e}")

    def _reset_position(self):
        screen = (QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()).availableGeometry()
        self.move(screen.right() - self.width() - 28, screen.bottom() - self.height() - 28)
        self._save_position()
        if self._bubble:
            self._bubble.position_near_pet()
        self._layout_task_bubbles()

    def _set_visible(self, visible):
        self._pet_visible = bool(visible)
        self.setVisible(self._pet_visible)
        if self._bubble:
            self._bubble.setVisible(self._pet_visible and bool(self._bubble_text) and not self._confirmation_active())
        self._layout_task_bubbles()
        if self._confirmations:
            self._confirmations.position()
        if self._confirmations:
            self._confirmations.position()

    def _manual_state(self, state):
        self._manual_until = time.time() + MANUAL_GRACE_SEC
        self._auto_active = False
        self._set_state(state)

    def _init_label(self):
        """初始化显示标签"""
        img_label = QLabel(self)
        img_label.setGeometry(0, 0, self.width(), self.height())
        self._img_label = img_label

    def _init_context_menu(self):
        """右键菜单"""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def _init_watcher(self):
        """监听任务目录与进度文件，文件变化即刻刷新（替代轮询）"""
        try:
            if TASKS_DIR.exists():
                self._watcher.addPath(str(TASKS_DIR))
            if PROGRESS_PATH.exists():
                self._watcher.addPath(str(PROGRESS_PATH))
            if STATE_PATH.exists():
                self._watcher.addPath(str(STATE_PATH))
        except Exception as e:
            log(f"watcher init err: {e}")

    def _on_watched_file(self, path: str):
        p = Path(path)
        if p == PROGRESS_PATH or p == STATE_PATH:
            self._check_state()
        else:
            self._scan_tasks()

    def _poll_transcripts(self):
        """主通道：增量读取 teleagent.db part 表，喂给状态机"""
        if not AUTO_PERCEPTION_ENABLED:
            return
        try:
            events = self._watcher_tp.poll()
        except Exception as e:
            log(f"poll_transcripts err: {e}\n{getattr(e, '__traceback__', '')}")
            return
        # 同步系统内部会话集合：新识别出的系统会话由 tracker 立即清除气泡
        self._tracker.set_sys_sids(self._watcher_tp._sys_sids)
        # 同步已结束会话集合：completed 会话延迟 20 秒清除气泡，避免"任务结束还挂着"
        self._tracker.set_completed_sids(self._watcher_tp.completed_sids())
        self._tracker.active_sids = self._watcher_tp._active_sessions() or set()
        self._poll_events += len(events)
        # 活性自检：每 60 秒写一条心跳日志。桌宠若整体冻结（事件循环卡死），
        # 这条日志会停更——留下冻结的时间点和当时的状态快照，可定位。
        now_s = time.time()
        if now_s - self._last_alive_log >= 60:
            st, info = self._tracker.resolve()
            log(f"alive: 1min事件={self._poll_events} 状态={st} 会话={len(self._tracker.sessions)} "
                f"气泡={self._bubble_text[:30]!r}")
            self._poll_events = 0
            self._last_alive_log = now_s
        if not events:
            # 无新事件：交给活性守卫判断——事件仍在写入就保持现状，静默则衰减
            self._apply_auto_state()
            return
        for ev in events:
            try:
                self._tracker.on_event(ev)
            except Exception:
                pass
        self._apply_auto_state(force=True)   # 有新事件：必须应用

    def _confirm_done(self):
        """完成去抖到期：确认仍处于完成态才庆祝"""
        if time.time() < self._manual_until:
            return
        if self._task_bubbles:
            return
        state, _info = self._tracker.resolve()
        if state == "done":
            self._set_state("hero-celebrate", one_shot=True, next_state="idle")

    def _apply_auto_state(self, force: bool = False):
        """把状态机算出的状态应用到桌宠。

        优先级：手动命令（保护期内） > 多任务气泡 > 事件驱动状态。
        force=True：有新事件到达，状态必须应用。
        force=False：纯轮询空转，若 DB 仍在写入则保持现状。
        """
        if self._confirmation_active() or not AUTO_PERCEPTION_ENABLED:
            return
        # 手动控制优先
        if time.time() < self._manual_until:
            return
        if self._progress_active or self._state_tasks or self._file_tasks:
            return
        # 手动/进度任务驱动的气泡在显示时，事件状态只做兜底
        if self._task_bubbles and self._bubble_owner == "manual":
            return

        # 活性守卫：只要有 running 会话在（session-status.json），
        # 即使 DB 暂时无新 part（长工具/长输出），也保持现状，不清气泡。
        # 活性按会话维护；不能因另一个 running 会话而保留已结束的气泡。

        # 事件驱动接管：抑制 _set_state 的默认状态文案，气泡统一由这里出
        self._auto_active = True

        state, info = self._tracker.resolve()

        # 状态没变时：刷新气泡文案（工具名会变，状态不一定变），
        # 并把可能被任务气泡改过的动画对齐回来
        if state == self._auto_state:
            self._update_auto_bubble(state, info)
            anim = STATE_ANIM.get(state, "idle")
            if anim != self._state and not self._one_shot and not (state == "idle" and self._state == "look"):
                self._set_state(anim)
            return

        self._auto_state = state
        self._update_auto_bubble(state, info)

        if state == "done":
            # 不立刻庆祝：一轮里常穿插多条消息，延迟确认后再庆祝，避免反复跳
            self._done_timer.start()
            anim = "idle"
        elif state == "failed":
            self._done_timer.stop()
            anim = "failed"
        else:
            self._done_timer.stop()
            anim = STATE_ANIM.get(state, "idle")

        if anim != self._state and not self._one_shot and not (state == "idle" and self._state == "look"):
            self._set_state(anim)

    def _update_auto_bubble(self, state: str, info: dict):
        """事件驱动气泡：按会话数量自动切换形态。

        单会话 → 两行气泡（状态行 + 具体动作行）
        多会话 → 每会话一个独立气泡（标题/状态色），竖向堆叠可折叠
        """
        if state == "idle":
            self._clear_all_auto_bubbles()
            return

        n = info.get("sessions", 1)
        if n >= 2:
            self._show_auto_multi(state, info)
        else:
            self._show_auto_single(state, info)

    def _clear_all_auto_bubbles(self):
        """清掉两套气泡（回待机时调用）"""
        self._hide_bubble()                 # 两行大气泡
        if self._task_bubbles:
            self._sync_bubbles([], from_auto=True)   # 多气泡全关
        self._bubble_owner = None

    def _show_auto_single(self, state: str, info: dict):
        """单会话：结构化气泡（状态行 + 具体动作行，打字机）"""
        # 多气泡在显示时先收掉，切换干净
        if self._task_bubbles:
            self._sync_bubbles([], from_auto=True)

        if state == "thinking":
            prefix = "思考中"
        else:
            prefix = info.get("label") or STATE_LABEL.get(state, "")
        if not prefix:
            return
        n = info.get("sessions", 1)
        if n > 1:
            prefix = f"{prefix} · {n} 个会话"
        steps = 0
        if state in ("working", "review"):
            steps = info.get("steps", 0)

        # 第二行：优先用 snippet（思考摘录），没有则用工具中文名
        snippet = info.get("snippet") or ""
        if not snippet and state in ("working", "review"):
            tool = info.get("tool", "")
            if tool:
                snippet = TOOL_LABEL_PET.get(tool, tool)
        if state in ("done", "cancelled", "failed"):
            snippet = ""
        self._show_auto(prefix, snippet, state=state, steps=steps)

    def _show_auto_multi(self, state: str, info: dict):
        """多会话：每个会话一个独立气泡（标题/状态色/思考摘录），竖向堆叠"""
        # 两行大气泡在显示时先收掉，切换干净
        self._hide_bubble()
        titles = self._watcher_tp.titles
        self._watcher_tp.poll_titles()
        tasks = self._tracker.resolve_tasks(titles)
        self._sync_bubbles(tasks, from_auto=True)

    # ---- 事件处理 ----
    def visual_geometry(self):
        """Visible character bounds, excluding the atlas cell's transparent padding."""
        frame = self._current_frame
        if frame is None or frame.isNull():
            return self.geometry()
        # Keep only the latest bounds: continuously rendered frames have unique keys.
        key = frame.cacheKey()
        if getattr(self, '_visible_bounds_key', None) != key:
            self._visible_bounds_key = key
            self._visible_bounds = QRegion(frame.mask()).boundingRect()
        bounds = self._visible_bounds
        scale = min(self.width() / frame.width(), self.height() / frame.height())
        return QRect(self.x() + round(bounds.x() * scale),
                     self.y() + round(bounds.y() * scale),
                     round(bounds.width() * scale), round(bounds.height() * scale))

    def _position_companions(self):
        if self._bubble and self._bubble.isVisible():
            self._bubble.position_near_pet()
        self._layout_task_bubbles()
        if self._confirmation_active():
            self._confirmations.position()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._current_frame:
            # 高清渲染：按物理像素 1:1 绘制（2x 图源在高 DPI 屏上不再放大发虚）
            dpr = self.devicePixelRatioF()
            scaled = self._current_frame.scaled(
                round(self.width() * dpr), round(self.height() * dpr),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            scaled.setDevicePixelRatio(dpr)
            painter.drawPixmap(0, 0, scaled)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setFont(_ui_font(9))
        menu.setStyleSheet("""
            QMenu { background: rgba(255,255,255,252); border: 1px solid rgba(148,163,184,0.6); border-radius: 10px; padding: 6px; }
            QMenu::item { padding: 5px 22px; border-radius: 6px; color: #1f2937; }
            QMenu::item:selected { background: rgba(59,130,246,26); color: #1d4ed8; }
            QMenu::separator { height: 1px; background: rgba(148,163,184,0.35); margin: 4px 8px; }
        """)

        # 状态切换
        for s, label in [("idle", "待机"), ("running", "执行中"), ("review", "检查中"),
                         ("waiting", "等待中"), ("waving", "挥手"), ("jumping", "跳跃"),
                         ("hero-celebrate", "开心庆祝"), ("walking-left", "向左走"),
                         ("walking-right", "向右走"), ("running-left", "向左跑"),
                         ("running-right", "向右跑")]:
            act = menu.addAction(label)
            act.triggered.connect(lambda checked, st=s: self._manual_state(st))

        menu.addSeparator()

        act_hide = menu.addAction("隐藏")
        act_hide.triggered.connect(lambda: self._set_visible(False))
        act_exit = menu.addAction("退出")
        act_exit.triggered.connect(self._quit)
        menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            pass  # contextMenuEvent 处理

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            if self._bubble:
                self._bubble.position_near_pet()
            if self._task_bubbles:
                self._layout_task_bubbles()
            if self._confirmations:
                self._confirmations.position()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._save_position()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._set_state("waving", one_shot=True, next_state=self._state if self._state != "waving" else "idle")

    def enterEvent(self, event):
        if self._state == "idle" and not self._one_shot:
            self._saved_state = self._state
            self._set_state("look")

    def leaveEvent(self, event):
        if self._state == "look" and hasattr(self, "_saved_state"):
            self._set_state(self._saved_state)

    # ---- 动画 ----
    def _set_state(self, state: str, one_shot: bool = False, next_state: str = "idle"):
        self._entry_pose = dict(self._scene_pose)
        self._scene_epoch = time.monotonic()
        anim_state = state
        if anim_state not in ANIMATIONS and anim_state != "look":
            anim_state = "idle"
            state = "idle"
        self._state = state
        self._frame_index = 0
        self._one_shot = one_shot
        self._next_state = next_state

        # 更新气泡消息。事件驱动接管时（_auto_active）由 _update_auto_bubble
        # 负责气泡内容，这里不显示默认文案，避免两套文案互相覆盖造成闪烁。
        # look（注视鼠标）绝不显示气泡：悬停时不能覆盖正在展示的任务气泡。
        msg = STATE_MESSAGES.get(state, "")
        if state == "look":
            pass  # 注视动画不碰气泡
        elif msg and not one_shot and not self._auto_active:
            self._show_bubble(msg)
        elif not one_shot and not msg and not self._auto_active:
            self._hide_bubble()

        if state == "look":
            self._look_timer.start()
        else:
            self._look_timer.stop()

        self._show_frame()
        self._set_anim_duration()

    def _set_anim_duration(self):
        if self._state == 'look':
            self._anim_timer.stop()
        else:
            self._anim_timer.start(33)

    def _render_scene(self, elapsed, gaze=(0.,0.)):
        pose = sample_scene(self._state, elapsed, gaze)
        if self._state == 'look':
            pose['eye_x'], pose['eye_y'] = self._gaze
        if elapsed < .35:
            pose = mix_pose(self._entry_pose, pose, elapsed / .35)
        self._scene_pose = pose
        self._current_frame = self._puppet.render(pose)
        self.update()
        self._position_companions()

    def _show_frame(self):
        if self._state == 'look':
            self._update_look()
            return
        elapsed = max(0., time.monotonic() - self._scene_epoch)
        self._render_scene(elapsed)

    def _on_anim_tick(self):
        if self._state == 'look':
            return
        elapsed = max(0., time.monotonic() - self._scene_epoch)
        if self._one_shot and elapsed >= playback_duration(self._state):
            self._set_state(self._next_state)
            return
        self._frame_index = int(elapsed * 30) % len(ANIMATIONS[self._state]['durations'])
        self._render_scene(elapsed)

    def _update_look(self):
        mouse = QCursor.pos()
        center = self.geometry().center()
        target = (max(-1., min(1., (mouse.x()-center.x()) / 150.)),
                  max(-1., min(1., (mouse.y()-center.y()) / 150.)))
        self._gaze = tuple(a + (b-a)*.3 for a,b in zip(self._gaze,target))
        self._gaze_head = tuple(a + (b-a)*.1 for a,b in zip(self._gaze_head,self._gaze))
        self._render_scene(max(0., time.monotonic()-self._scene_epoch), self._gaze_head)

    # ---- 气泡 ----
    def _show_bubble(self, msg: str):
        """手动/单行气泡（不打字）。文本与可见状态均无变化时，一个窗口操作都不做。"""
        if msg == self._bubble_text and self._bubble and self._bubble.isVisible():
            return
        if self._bubble is None:
            self._bubble = BubbleWindow(self)
        self._tw_timer.stop()
        self._bubble_text = msg
        self._bubble.set_message(msg, accent=STATE_UI_COLORS.get(self._state, "#1687ff"))
        self._bubble.position_near_pet()
        self._bubble.setVisible(self._pet_visible and not self._confirmation_active())

    def _hide_bubble(self):
        self._auto_render_signature = None
        self._bubble_text = ""
        self._auto_prefix = ""
        self._auto_snippet = ""
        self._tw_timer.stop()
        if self._bubble:
            self._bubble.hide()

    # ---- 自动气泡：第一行状态，第二行最近思考摘录 ----
    # 摘录跨状态保留：agent "思考→调工具"快速交替时，摘录不会一闪而过，
    # 而是在"执行中"下方继续逐字打完——这正是"流式输出"的观感。
    def _show_auto(self, prefix: str, snippet: str, state: str = None, steps: int = 0):
        # 先按"打完后的完整文本"判断是否真的有变化：
        # 完全无变化且气泡可见时，直接返回——不渲染、不重定位、不置顶，
        # 这是消除闪烁的最后一道闸（此前 render 去重了，但窗口操作仍在反复执行）。
        full = prefix + ("\n" + snippet if snippet else "")
        if (full == self._bubble_text and state == self._auto_state and steps == self._auto_steps
                and self._bubble and self._bubble.isVisible()):
            return
        self._auto_state = state
        self._auto_steps = steps
        if self._bubble is None:
            self._bubble = BubbleWindow(self)
        if snippet != self._auto_snippet:
            self._auto_snippet = snippet
            self._tw_pos = 0
            if snippet:
                self._tw_timer.start()
            else:
                self._tw_timer.stop()
        self._auto_prefix = prefix
        self._auto_render()
        self._bubble.position_near_pet()
        self._bubble.setVisible(self._pet_visible and not self._confirmation_active())

    def _auto_render(self):
        shown = self._auto_snippet[: self._tw_pos]
        if self._bubble is None:
            return
        text = self._auto_prefix + ("\n" + shown if shown else "")
        signature = (text, self._auto_state, self._auto_steps, self._auto_snippet)
        if signature != self._auto_render_signature:
            self._auto_render_signature = signature
            self._bubble_text = text
            color = STATE_UI_COLORS.get(self._auto_state or "running", "#3b82f6")
            step_text = f"第 {self._auto_steps} 步" if self._auto_steps else ""
            self._bubble.set_structured(self._auto_prefix, color, step_text,
                                        shown, self._auto_snippet)

    def _tw_tick(self):
        if self._bubble is None or not self._auto_snippet:
            self._tw_timer.stop()
            return
        if self._tw_pos >= len(self._auto_snippet):
            self._tw_timer.stop()
            return
        self._tw_pos = min(self._tw_pos + TYPEWRITER_STEP, len(self._auto_snippet))
        self._auto_render()

    # ---- 任务气泡 ----
    def _scan_tasks(self):
        """扫描任务目录"""
        import traceback
        # 顺带做一次 TTL 衰减检查：没有新事件时，过期状态自动回落
        try:
            self._apply_auto_state()
        except Exception:
            pass
        try:
            tasks = []
            now = time.time()
            for f in sorted(TASKS_DIR.iterdir()) if TASKS_DIR.exists() else []:
                if not f.is_file() or f.suffix.lower() not in (".txt", ".json"):
                    continue
                name = f.stem
                if not name:
                    continue
                try:
                    age = now - f.stat().st_mtime
                    raw = f.read_text(encoding="utf-8-sig").strip()
                except (OSError, UnicodeError):
                    continue
                if age > TASK_STALE_SEC:
                    continue
                if not raw:
                    continue
                # 解析内容
                status = "running"
                current = 0
                total = 0
                message = raw
                if raw.startswith("{"):
                    try:
                        obj = json.loads(raw)
                        status = obj.get("status", "running")
                        current = obj.get("current", 0)
                        total = obj.get("total", 0)
                        message = obj.get("message", raw)
                    except json.JSONDecodeError:
                        pass
                elif raw.startswith("["):
                    import re
                    m = re.match(r"^\[(完成|失败)\]\s*(.*)$", raw)
                    if m:
                        status = "completed" if m.group(1) == "完成" else "failed"
                        message = m.group(2).strip()
                    else:
                        m = re.match(r"^\[(\d+)/(\d+)\]\s*(.*)$", raw)
                        if m:
                            current = int(m.group(1))
                            total = int(m.group(2))
                            message = m.group(3)
                tasks.append({
                    "id": name, "name": name, "status": status,
                    "current": current, "total": total, "message": message
                })

            # 签名
            sig = "\n".join(
                f"{t['id']}|{t['status']}|{t['current']}|{t['total']}|{t['message']}"
                for t in tasks
            )
            self._file_tasks = tasks
            if sig != self._task_last_sig and not self._progress_active and not self._state_tasks:
                self._task_last_sig = sig
                log(f"scan_tasks: count={len(tasks)} sig={sig[:80]}")
                self._sync_bubbles(tasks)

        except Exception as e:
            log(f"scan_tasks err: {e}\n{traceback.format_exc()}")

    def _sync_bubbles(self, tasks: list, from_auto: bool = False):
        """同步任务气泡。

        from_auto=True：由事件驱动的多会话模式调用——动画仍由 _apply_auto_state
        统一管理，这里不做状态联动，也不退出事件驱动文案。
        from_auto=False：手动/进度任务驱动——接管显示，退出事件驱动文案。
        """
        try:
            tasks = self._normalize_tasks(tasks)
            # 签名防抖：内容没变就不动窗口（多会话高频轮询时避免无谓重建）
            sig = "\n".join(
                f"{t.get('id')}|{t.get('status')}|{t.get('current')}|{t.get('total')}|{t.get('message')}|{t.get('name')}"
                for t in tasks
            )
            if from_auto and sig == self._auto_bubble_sig:
                return
            self._auto_bubble_sig = sig if from_auto else ""

            if from_auto:
                self._bubble_owner = "auto"
            else:
                self._auto_active = False   # 任务气泡接管显示，退出事件驱动文案
                self._bubble_owner = "manual" if tasks else None
            active_ids = {t["id"] for t in tasks}
            # 关闭已不存在的
            for tid in list(self._task_bubbles.keys()):
                if tid not in active_ids:
                    b = self._task_bubbles.pop(tid)
                    b.close()
            # 创建/更新
            for t in tasks:
                tid = t["id"]
                if tid not in self._task_bubbles:
                    self._task_bubbles[tid] = TaskBubble(tid, t["name"])
                    log(f"created bubble for {tid}")
                b = self._task_bubbles[tid]
                b.update_task(t["name"], t["status"], t["current"], t["total"], t["message"])
                b.setVisible(self._pet_visible and not self._confirmation_active())

            # 隐藏简单气泡（多任务时）
            if tasks:
                self._hide_bubble()
                self._layout_task_bubbles()
                log(f"sync_bubbles done: {len(self._task_bubbles)} bubbles visible")
                # 状态联动（仅手动/进度任务驱动；自动模式动画由 _apply_auto_state 统一管）
                if not from_auto:
                    states = {t["status"] for t in tasks}
                    anim = next((a for s, a in (("failed", "failed"), ("waiting", "waiting"),
                        ("working", "running"), ("running", "running"), ("review", "review"),
                        ("thinking", "thinking")) if s in states), "idle")
                    if anim != self._state:
                        self._auto_active = True  # 独立卡片已承载文案
                        self._set_state(anim)
                        self._auto_active = False
            else:
                # 全部结束
                if self._task_bubbles:
                    for b in self._task_bubbles.values():
                        b.close()
                    self._task_bubbles.clear()
                self._bubble_owner = None
                if not from_auto:
                    # 任务清空后回到待机（TeleAgent 下无自动感知兜底，需显式回落）
                    if self._state not in ("idle", "look", "waving", "jumping", "hero-celebrate"):
                        self._set_state("idle")
        except Exception as e:
            import traceback
            log(f"sync_bubbles err: {e}\n{traceback.format_exc()}")

    def _layout_task_bubbles(self):
        """排列任务气泡：竖向堆叠，从桌宠上方自下往上排列"""
        if self._confirmation_active():
            for bubble in self._task_bubbles.values():
                bubble.hide()
            return
        if not self._task_bubbles:
            return
        pet_geo = self.visual_geometry()
        screen = (QApplication.screenAt(pet_geo.center()) or self.screen()).availableGeometry()
        gap = _ui_px(2)
        items = sorted(self._task_bubbles.values(), key=lambda b: b.task_id)

        total_h = sum(b.height() + gap for b in items) - gap
        top_space = pet_geo.top() - screen.top() - gap
        bottom_space = screen.bottom() - pet_geo.bottom() - gap
        if top_space >= total_h:
            cur_y = pet_geo.top() - gap - total_h + items[-1].M_B
        elif bottom_space >= total_h:
            cur_y = pet_geo.bottom() + gap - items[0].M_T
        else:
            cur_y = screen.top() + gap
        center_x = pet_geo.center().x()

        below = cur_y >= pet_geo.bottom() - items[0].M_T
        for index, b in enumerate(items):
            bw = b.width()
            bh = b.height()
            if not self._pet_visible or cur_y + bh > screen.bottom() - gap:
                b.hide()
                continue
            top = cur_y
            left = center_x - bw // 2
            # 不超出屏幕左右
            left = max(screen.left() + 4, min(left, screen.right() - bw - 4))
            b.move(left, top)
            b.frame.show_tail = index == (0 if below else len(items) - 1)
            b.frame.tail_up = below
            b.frame.tail_x = center_x - left - b.M_L
            b.frame.update()
            b.show()
            cur_y = top + bh + gap

    @staticmethod
    def _normalize_tasks(tasks):
        if not isinstance(tasks, list):
            return []
        out = []
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            t = {k: str(task.get(k) or "") for k in ("id", "name", "message", "status")}
            t["id"] = t["id"] or t["name"] or str(i)
            t["name"] = t["name"] or t["id"]
            t["status"] = t["status"] or "running"
            for k in ("current", "total"):
                try:
                    t[k] = max(0, int(task.get(k, 0)))
                except (ValueError, TypeError, OverflowError):
                    t[k] = 0
            if t["total"]:
                t["current"] = min(t["current"], t["total"])
            out.append(t)
        return out

    # ---- state.json 控制 ----
    def _check_state(self):
        try:
            self._read_state()
        finally:
            self._check_progress()

    def _read_state(self):
        """读取 state.json 控制文件。

        state.json 是常驻文件——里面的内容绝不能每秒反复应用，否则手动通道的
        常驻旧值（比如 state:"idle"）会和事件驱动的当前状态打架，
        桌宠动画和气泡每秒被拆一次又装回去。一切以"文件被改动过"为准。
        """
        try:
            if not STATE_PATH.exists():
                return
            raw = STATE_PATH.read_text(encoding="utf-8").strip()
            if not raw:
                return  # 空文件，静默跳过（不写 error 日志，避免噪声）
            try:
                state = json.loads(raw)
            except json.JSONDecodeError:
                return  # 非法 JSON，静默跳过（文件可能被截断/并发写）
            if not isinstance(state, dict):
                return
            cmd = state.get("command", "")
            if cmd == "exit":
                # 先清掉退出指令再退：残留的 exit 会误杀下一次启动的实例
                try:
                    state["command"] = ""
                    with open(STATE_PATH, "w", encoding="utf-8") as f:
                        json.dump(state, f, ensure_ascii=False)
                except Exception:
                    pass
                self._quit()
                return
            new_state = state.get("state", "idle")
            one_shot = state.get("one_shot", False)
            next_state = state.get("next_state", "idle")
            msg = state.get("message", "")
            visible = state.get("visible", True)

            # 只有文件真的被改动过，才视为一次新的手动命令
            try:
                mt = STATE_PATH.stat().st_mtime
            except Exception:
                mt = 0
            file_changed = bool(mt) and mt != self._last_state_mtime
            if file_changed:
                self._last_state_mtime = mt
                self._manual_until = time.time() + MANUAL_GRACE_SEC
                self._auto_state = "idle"   # 保护期结束后允许重新应用
                self._auto_active = False   # 手动命令接管气泡文案

            if not file_changed:
                self._check_progress()      # 文件没变：这一秒什么都不做
                return

            if visible:
                self._set_visible(True)
            else:
                self._set_visible(False)

            if state.get("reset_position"):
                self._reset_position()
                state["reset_position"] = False
                STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                self._last_state_mtime = STATE_PATH.stat().st_mtime

            if "tasks" in state:
                self._state_tasks = self._normalize_tasks(state["tasks"])
                self._sync_bubbles(self._state_tasks or self._file_tasks)

            if new_state in VALID_STATES:
                # 避免重复设置
                if new_state != self._state or one_shot:
                    self._set_state(new_state, one_shot=one_shot, next_state=next_state)
                if not self._state_tasks and not self._file_tasks:
                    if msg:
                        self._show_bubble(str(msg))
                    elif "message" in state:
                        self._hide_bubble()

            # 进度文件驱动
            self._check_progress()

        except Exception as e:
            log(f"check_state err: {e}")

    def _check_progress(self):
        """检查进度文件。

        文件不存在/为空是常态（没人写进度驱动时），绝不能因此每秒隐藏气泡——
        那会把事件驱动的自动气泡拆了又让 250ms 轮询重建，形成周期性刷新。
        只有进度驱动处于激活态（曾读到过内容）时，"消失"才代表退出进度驱动。
        """
        try:
            raw = PROGRESS_PATH.read_text(encoding="utf-8-sig").strip() if PROGRESS_PATH.exists() else ""
            if not raw:
                if self._progress_active:
                    self._progress_active = False
                    self._progress_signature = None
                    self._hide_bubble()
                    self._sync_bubbles(self._state_tasks or self._file_tasks)
                return
            if raw == self._progress_signature:
                return
            obj = json.loads(raw) if raw.startswith("{") else {"message": raw}
            if not isinstance(obj, dict):
                return
            self._progress_active = True
            self._progress_signature = raw
            tasks = self._normalize_tasks(obj.get("tasks", []))
            self._sync_bubbles(tasks)
            p_state = obj.get("state", "running")
            self._auto_active = True
            if p_state in VALID_STATES and p_state != self._state:
                self._set_state(p_state)
            self._auto_active = False
            if not tasks:
                self._show_bubble(str(obj.get("message") or ""))
        except Exception as e:
            log(f"check_progress err: {e}")

    def _quit(self):
        """退出"""
        if self._confirmations:
            self._confirmations.close()
        self._anim_timer.stop()
        self._state_check_timer.stop()
        self._task_scan_timer.stop()
        self._look_timer.stop()
        self._tp_timer.stop()
        self._done_timer.stop()
        if self._bubble:
            self._bubble.close()
        for b in self._task_bubbles.values():
            b.close()
        QApplication.quit()


# ============================================================
# 主入口
# ============================================================

class RecallHotkey(QAbstractNativeEventFilter):
    """Global Ctrl+Alt+P. Registration failure never prevents startup."""
    ID = 0x5348

    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.registered = False
        if os.name == "nt":
            import ctypes
            self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self.ID, 0x4003, ord('P')))
            if not self.registered:
                log("Ctrl+Alt+P 被占用，可用 show/reset-position 命令召回")

    def nativeEventFilter(self, event_type, message):
        if self.registered:
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == self.ID:
                self.pet._reset_position()
                self.pet._set_visible(True)
                return True, 0
        return False, 0

    def close(self):
        if self.registered:
            import ctypes
            ctypes.windll.user32.UnregisterHotKey(None, self.ID)
            self.registered = False

def main():
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    instance_lock = InstanceLock(RUNTIME_ROOT)
    if not instance_lock.acquire():
        return 0
    # pythonw 下 sys.stdout/stderr 是 None——任何写它们的代码（包括 Qt 的警告
    # 桥接、第三方库的 print）都会抛 AttributeError 且无处可看，进程无声死亡。
    # 全部兜底重定向：stdout 丢弃，stderr 进日志，异常从此可见。
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        try:
            sys.stderr = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")

    # 单实例守卫：已有桌宠在跑，本次启动的重复实例立即静默退出。
    # 必须在创建任何窗口之前拦截。
    # pythonw 下 sys.stdout/stderr 是 None——任何写它们的代码（包括 Qt 的警告
    # 桥接、第三方库的 print）都会抛 AttributeError 且无处可看，进程无声死亡。
    # 全部兜底重定向：stdout 丢弃，stderr 进日志，异常从此可见。
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        try:
            sys.stderr = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")

    def _excepthook(t, v, tb):
        import traceback
        try:
            log("未捕获异常:\n" + "".join(traceback.format_exception(t, v, tb)))
        except Exception:
            pass
    sys.excepthook = _excepthook

    # 确保运行时目录
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    # faulthandler：C++ 层硬崩溃（Qt 段错误）时把 Python 调用栈写盘，否则死得无声无息
    _fh = None
    try:
        import faulthandler
        _fh = open(RUNTIME_ROOT / "crash.log", "w", buffering=1)
        faulthandler.enable(_fh)
    except Exception:
        pass
    # 写 PID
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")

    # 信号处理
    def on_signal(signum, frame):
        QApplication.quit()
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    log("step1: QApplication 就绪")

    pet = PetWindow()
    hotkey = RecallHotkey(pet)
    app.installNativeEventFilter(hotkey)
    pet.show()
    pet._last_state_mtime = -1
    pet._check_state()
    log("step2: PetWindow 创建完成")

    # 启动计时器
    pet._state_check_timer.start()
    pet._task_scan_timer.start()
    pet._anim_timer.start()
    pet._tp_timer.start()
    # 启动时先扫一次，立即对齐当前会话状态，而不是等第一个新事件
    QTimer.singleShot(100, pet._poll_transcripts)

    # 处理 Ctrl+C
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    log("蜡笔小新桌宠 (PySide6) 启动成功")
    try:
        return app.exec()
    finally:
        hotkey.close()
        if _fh is not None:
            faulthandler.disable()
            _fh.close()
        if PID_PATH.exists() and PID_PATH.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_PATH.unlink()
        instance_lock.release()


if __name__ == "__main__":
    sys.exit(main())
