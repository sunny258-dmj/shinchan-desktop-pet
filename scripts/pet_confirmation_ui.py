"""Clickable confirmation cards; detail review never implies consent.

V4 keeps the original confirmation semantics but uses the same airy pastel-card
visual language as the redesigned desktop pet bubbles.
"""
import time
from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QButtonGroup,
                               QScrollArea, QPlainTextEdit)
from pet_confirmation import ConfirmationStore
from pet_config import ui_scale

_UI = ui_scale()


def _ui_font(size, weight=QFont.Weight.Normal):
    f = QFont("Microsoft YaHei UI")
    # 确认是用户必须阅读和选择的内容，不能跟随桌宠缩小到难以辨认。
    f.setPointSizeF(max(9.0, round(size * _UI, 2)))
    f.setWeight(weight)
    return f


def _ui_px(value):
    return max(1, int(round(value * _UI)))


class ChoiceLabel(QLabel):
    def __init__(self, text, radio=None):
        super().__init__(text)
        self.radio = radio
        if radio:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if self.radio and event.button() == Qt.MouseButton.LeftButton:
            self.radio.setChecked(True)
        super().mouseReleaseEvent(event)


def plain_label(text, radio=None):
    label = ChoiceLabel(text, radio)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class ReviewDialog(QDialog):
    def __init__(self, controller, data):
        super().__init__(controller.pet, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.controller, self.data = controller, data
        self.setWindowTitle("小新 · 我自己确认")
        self.setFont(_ui_font(10))
        radius = _ui_px(14)
        self.setStyleSheet(f"""
            QDialog {{
                background: #f4fbff;
                color: #26364a;
            }}
            QLabel {{
                color: #26364a;
                background: transparent;
            }}
            QScrollArea {{
                border: {_ui_px(1)}px solid #d7eaf7;
                border-radius: {radius}px;
                background: #ffffff;
            }}
            QScrollArea > QWidget > QWidget {{
                background: #ffffff;
            }}
            QRadioButton {{
                color: #26364a;
                padding: {_ui_px(8)}px 0;
                spacing: {_ui_px(8)}px;
            }}
            QRadioButton::indicator {{
                width: {_ui_px(17)}px;
                height: {_ui_px(17)}px;
            }}
            QPlainTextEdit {{
                background: #ffffff;
                color: #26364a;
                border: {_ui_px(1)}px solid #c9e0ef;
                border-radius: {_ui_px(11)}px;
                padding: {_ui_px(8)}px;
                selection-background-color: #bfe4ff;
            }}
            QPushButton {{
                min-height: {_ui_px(34)}px;
                padding: {_ui_px(7)}px {_ui_px(16)}px;
                border: {_ui_px(1)}px solid #c7ddec;
                border-radius: {_ui_px(11)}px;
                background: #ffffff;
                color: #36536d;
            }}
            QPushButton:hover {{
                background: #eaf6ff;
                border-color: #98cbea;
            }}
            QPushButton:disabled {{
                color: #91a5b6;
                background: #edf3f7;
                border-color: #dce7ee;
            }}
        """)

        request = data["request"]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(_ui_px(22), _ui_px(18), _ui_px(22), _ui_px(18))
        layout.setSpacing(_ui_px(11))

        title = plain_label(request["title"])
        title.setFont(_ui_font(13, QFont.Weight.Bold))
        title.setStyleSheet("color:#1f4770;")
        layout.addWidget(title)

        question = plain_label(request["question"])
        question.setFont(_ui_font(10))
        question.setStyleSheet(
            f"background:#ffffff;border:{_ui_px(1)}px solid #d9ebf7;"
            f"border-radius:{_ui_px(12)}px;padding:{_ui_px(10)}px;color:#3d5870;")
        layout.addWidget(question)

        area = QScrollArea()
        area.setWidgetResizable(True)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(_ui_px(13), _ui_px(10), _ui_px(13), _ui_px(10))
        body.setSpacing(_ui_px(5))
        self.group = QButtonGroup(self)
        self.choices = []

        for index, option in enumerate(request["options"]):
            row = QHBoxLayout()
            row.setContentsMargins(_ui_px(6), _ui_px(4), _ui_px(6), _ui_px(4))
            row.setSpacing(_ui_px(8))
            radio = QRadioButton()
            radio.setAccessibleName(option["label"])
            self.group.addButton(radio, index)
            self.choices.append((radio, option["id"]))
            row.addWidget(radio, 0, Qt.AlignmentFlag.AlignTop)
            words = QVBoxLayout()
            words.setSpacing(_ui_px(2))
            recommended = option["id"] == request["recommended"]
            option_title = option["label"] + ("  ·  推荐" if recommended else "")
            option_label = plain_label(option_title, radio)
            option_label.setFont(_ui_font(10, QFont.Weight.Bold if recommended else QFont.Weight.Medium))
            option_label.setStyleSheet("color:#177cc1;" if recommended else "color:#26364a;")
            words.addWidget(option_label)
            if option["description"]:
                description = plain_label(option["description"], radio)
                description.setStyleSheet("color:#698096;")
                words.addWidget(description)
            row.addLayout(words, 1)
            body.addLayout(row)

        self.custom = None
        if request["allow_custom"]:
            radio = QRadioButton("我有其他想法")
            self.group.addButton(radio, len(self.choices))
            self.choices.append((radio, "__custom__"))
            body.addWidget(radio)
            self.custom = QPlainTextEdit()
            self.custom.setPlaceholderText("写下你的选择或补充要求")
            self.custom.setMaximumHeight(_ui_px(100))
            self.custom.textChanged.connect(self._selection_changed)
            body.addWidget(self.custom)

        body.addStretch()
        area.setWidget(content)
        layout.addWidget(area, 1)

        self.error_label = plain_label("")
        self.error_label.setStyleSheet("color:#d53b4f;")
        layout.addWidget(self.error_label)

        row = QHBoxLayout()
        later = QPushButton("先不选")
        later.clicked.connect(self.close)
        self.submit = QPushButton("确认选择")
        self.submit.setEnabled(False)
        self.submit.setStyleSheet(f"""
            QPushButton {{
                background:#1687ff;color:white;border:{_ui_px(1)}px solid #0875e9;
                border-radius:{_ui_px(11)}px;padding:{_ui_px(8)}px {_ui_px(18)}px;
                font-weight:600;
            }}
            QPushButton:hover {{ background:#0f79e6; }}
            QPushButton:disabled {{ background:#cddce8;color:#f6f9fb;border-color:#cddce8; }}
        """)
        for button in (later, self.submit):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.submit.clicked.connect(self._submit)
        row.addWidget(later)
        row.addStretch()
        row.addWidget(self.submit)
        layout.addLayout(row)
        self.group.buttonToggled.connect(self._selection_changed)

        screen = controller.pet.screen().availableGeometry()
        # 保持确认窗口独立可读：桌宠可缩小，选择内容不应跟着压成 400px。
        self.resize(min(max(_ui_px(460), 460), screen.width() - 32),
                    min(max(_ui_px(460), 460), screen.height() - 64))
        self.move(max(screen.left(), min(controller.pet.x() - self.width(), screen.right() - self.width())),
                  max(screen.top(), min(controller.pet.y() - self.height(), screen.bottom() - self.height())))

    def _selection_changed(self, *_):
        index = self.group.checkedId()
        valid = index >= 0
        if valid and self.choices[index][1] == "__custom__":
            text = self.custom.toPlainText().strip()
            valid = bool(text) and len(text) <= 4000
        self.submit.setEnabled(valid)

    def _submit(self):
        index = self.group.checkedId()
        if index < 0:
            return
        option = self.choices[index][1]
        text = self.custom.toPlainText().strip() if option == "__custom__" else ""
        self.submit.setEnabled(False)
        error = self.controller.answer(self.data, option, "manual", text)
        if error:
            self.error_label.setText(error)
            self._selection_changed()
        else:
            self.close()


class ConfirmationController(QObject):
    def __init__(self, pet, bubble_class, root):
        super().__init__(pet)
        self.pet = pet
        self.store = ConfirmationStore(root)
        self.bubble_class = bubble_class
        self.bubble = None
        self.dialog = None
        self.current = None
        self.pending = []
        self._signature = None
        self._not_before = 0
        self._resume_state = "idle"
        self.timer = QTimer(pet)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    @property
    def active(self):
        return self.current is not None

    def _make_bubble(self):
        self.bubble = self.bubble_class(self.pet)
        self.bubble.setWindowTitle("小新 · 等你确认")
        self.bubble.setFont(_ui_font(10))
        row = QHBoxLayout()
        row.setSpacing(_ui_px(8))
        self.recommended = QPushButton("听你的\n按照推荐来")
        self.review = QPushButton("我看看\n我自己确认")
        self.recommended.setAccessibleName("听你的，按照推荐来")
        self.review.setAccessibleName("我看看，我自己确认")
        self.recommended.setStyleSheet(
            f"QPushButton{{background:#fff0a8;color:#604817;border:{_ui_px(1)}px solid #edcf65;"
            f"border-radius:{_ui_px(12)}px;padding:{_ui_px(8)}px;font-weight:600;}}"
            f"QPushButton:hover{{background:#ffe77c;border-color:#ddb845;}} "
            f"QPushButton:disabled{{background:#edf3f7;color:#91a5b6;border-color:#dce7ee;}}")
        self.review.setStyleSheet(
            f"QPushButton{{background:#eef8ff;color:#23618f;border:{_ui_px(1)}px solid #b9ddf4;"
            f"border-radius:{_ui_px(12)}px;padding:{_ui_px(8)}px;font-weight:600;}}"
            f"QPushButton:hover{{background:#dff2ff;border-color:#8fc9ed;}}")
        for button in (self.recommended, self.review):
            button.setFont(_ui_font(10, QFont.Weight.DemiBold))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(_ui_px(56))
            row.addWidget(button, 1)
        self.recommended.clicked.connect(self._recommend)
        self.review.clicked.connect(self._review)
        self.bubble._card_layout.addLayout(row)
        self.next_button = QPushButton("查看下一项")
        self.next_button.setStyleSheet(
            f"QPushButton{{background:transparent;color:#5c7893;border:0;padding:{_ui_px(3)}px;}}"
            f"QPushButton:hover{{color:#1687ff;}}")
        self.next_button.clicked.connect(self._next)
        self.bubble._card_layout.addWidget(self.next_button)

    def poll(self):
        had_pending = self.active
        self.pending = self.store.pending()
        previous_id = self.current["id"] if self.current else None
        self.current = next((d for d in self.pending if d["id"] == previous_id),
                            self.pending[0] if self.pending else None)
        if not had_pending and self.active:
            self._resume_state = self.pet._state
        if self.dialog and not any(d["id"] == self.dialog.data["id"] and
                d["fingerprint"] == self.dialog.data["fingerprint"] for d in self.pending):
            self.dialog.close()
            self.dialog.deleteLater()
            self.dialog = None
        if not self.active:
            if self.bubble:
                self.bubble.hide()
            self._signature = None
            if had_pending:
                if self.pet._state == "waiting":
                    self.pet._set_state(self._resume_state if self._resume_state != "look" else "idle")
                self.pet._apply_auto_state(force=True)
                self.pet._layout_task_bubbles()
                if self.pet._bubble:
                    self.pet._bubble.setVisible(self.pet._pet_visible and bool(self.pet._bubble_text))
            return
        if self.bubble is None:
            self._make_bubble()
        data, request = self.current, self.current["request"]
        index = next(i for i, d in enumerate(self.pending) if d["id"] == data["id"])
        sig = (data["id"], data["fingerprint"], index, len(self.pending))
        if sig != self._signature:
            self._signature = sig
            option = next((o for o in request["options"] if o["id"] == request["recommended"]), None)
            short = lambda value, n: value[:n] + "…" if len(value) > n else value
            body = short(request["question"], 80) + "\n" + (
                "推荐：" + short(option["label"], 44) if option else "还没有推荐方案，请点「我看看」自己选")
            self.bubble._last_key = None
            self.bubble.set_structured("等你确认", "#e0a22a",
                                       f"{index + 1}/{len(self.pending)}" if len(self.pending) > 1 else "",
                                       short(request["title"], 24) + "\n" + body,
                                       short(request["title"], 24) + "\n" + body)
            self.bubble.snippet_label.setToolTip(request["title"] + "\n" + request["question"])
            self.recommended.setToolTip("提交：" + option["label"] if option else "未指定推荐方案，请自行选择")
            self.next_button.setVisible(len(self.pending) > 1)
            self.bubble._apply_size(self.bubble.height() - self.bubble.M_T - self.bubble.M_B
                                    + _ui_px(72) + (_ui_px(28) if len(self.pending) > 1 else 0))
        self.recommended.setEnabled(request["recommended"] is not None and time.monotonic() >= self._not_before)
        if self.pet._bubble:
            self.pet._bubble.hide()
        for bubble in self.pet._task_bubbles.values():
            bubble.hide()
        if self.pet._state != "waiting":
            self.pet._auto_active = True
            self.pet._set_state("waiting")
        self.position()

    def position(self):
        if self.bubble:
            self.bubble.position_near_pet()
            self.bubble.setVisible(self.pet._pet_visible and self.active)
        if self.dialog and not self.pet._pet_visible:
            self.dialog.hide()

    def _next(self):
        if len(self.pending) < 2:
            return
        i = next(i for i, d in enumerate(self.pending) if d["id"] == self.current["id"])
        self.current = self.pending[(i + 1) % len(self.pending)]
        self.poll()

    def _recommend(self):
        data = self.current
        if data is None or data["request"]["recommended"] is None or time.monotonic() < self._not_before:
            return
        self.recommended.setEnabled(False)
        error = self.answer(data, data["request"]["recommended"], "recommended")
        if error and self.current and self.current["id"] == data["id"]:
            self.bubble.snippet_label.setText(error)
            self._signature = None

    def _review(self):
        if self.current is None:
            return
        if self.dialog:
            self.dialog.close()
            self.dialog.deleteLater()
        self.dialog = ReviewDialog(self, self.current)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def answer(self, data, option, source, text=""):
        try:
            self.store.answer(data["id"], data["fingerprint"], option, source, text)
        except (OSError, ValueError) as exc:
            return str(exc)
        self._not_before = time.monotonic() + 1
        self.poll()
        return None

    def close(self):
        self.timer.stop()
        if self.dialog:
            self.dialog.close()
        if self.bubble:
            self.bubble.close()
