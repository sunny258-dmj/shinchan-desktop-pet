"""Clickable confirmation cards; detail review never implies consent."""
import time
from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QButtonGroup,
                               QScrollArea, QPlainTextEdit)
from pet_confirmation import ConfirmationStore
from pet_config import ui_scale

# 与主程序一致的 UI 缩放（config.json 的 ui.scale，默认 0.8）
_UI = ui_scale()


def _ui_font(size, weight=QFont.Weight.Normal):
    f = QFont("Microsoft YaHei UI")
    f.setPointSizeF(max(6.0, round(size * _UI, 2)))
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
        self.setWindowTitle("我看看 · 确认选项")
        self.setFont(_ui_font(10))
        self.setStyleSheet(f"QDialog{{background:#fffdf7;color:#17304f;}}"
                           f"QPushButton{{padding:{_ui_px(9)}px {_ui_px(16)}px;border:1px solid #c9d1db;border-radius:{_ui_px(9)}px;}}"
                           f"QPushButton:enabled{{background:#fff;}}"
                           f"QRadioButton{{padding:{_ui_px(8)}px 0;}} QPlainTextEdit{{background:#fff;}}")
        request = data["request"]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(_ui_px(20), _ui_px(16), _ui_px(20), _ui_px(16))
        layout.addWidget(plain_label(request["title"]))
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setStyleSheet("QScrollArea{border:0;background:#fffdf7;} QScrollArea>QWidget>QWidget{background:#fffdf7;}")
        content = QWidget()
        body = QVBoxLayout(content)
        body.addWidget(plain_label(request["question"]))
        self.group = QButtonGroup(self)
        self.choices = []
        for index, option in enumerate(request["options"]):
            row = QHBoxLayout()
            radio = QRadioButton()
            radio.setAccessibleName(option["label"])
            self.group.addButton(radio, index)
            self.choices.append((radio, option["id"]))
            row.addWidget(radio, 0, Qt.AlignmentFlag.AlignTop)
            words = QVBoxLayout()
            title = option["label"] + ("（推荐）" if option["id"] == request["recommended"] else "")
            words.addWidget(plain_label(title, radio))
            if option["description"]:
                description = plain_label(option["description"], radio)
                description.setStyleSheet("color:#59677a;")
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
        self.error_label.setStyleSheet("color:#b42318;")
        layout.addWidget(self.error_label)
        row = QHBoxLayout()
        later = QPushButton("先不选")
        later.clicked.connect(self.close)
        self.submit = QPushButton("确认选择")
        self.submit.setEnabled(False)
        # Enter/Return must not silently submit the first or recommended option.
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
        self.resize(min(int(490 * _UI), screen.width() - 32), min(int(460 * _UI), screen.height() - 64))
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
        self.recommended = QPushButton("听你的\n按照推荐来")
        self.review = QPushButton("我看看\n我自己确认")
        self.recommended.setAccessibleName("听你的，按照推荐来")
        self.review.setAccessibleName("我看看，我自己确认")
        self.recommended.setStyleSheet(
            f"QPushButton{{background:#f8c94e;color:#342811;border:1px solid #dfa52f;"
            f"border-radius:{_ui_px(10)}px;padding:{_ui_px(7)}px;}}"
            f"QPushButton:hover{{background:#ffdb74;}} "
            f"QPushButton:disabled{{background:#edf0f3;color:#8a949f;border-color:#d9dfe5;}}")
        self.review.setStyleSheet(f"QPushButton{{background:#fff;color:#17304f;border:1px solid #c7d2df;"
                                  f"border-radius:{_ui_px(10)}px;padding:{_ui_px(7)}px;}}"
                                  f"QPushButton:hover{{background:#edf5ff;}}")
        for button in (self.recommended, self.review):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(_ui_px(54))
            row.addWidget(button, 1)
        self.recommended.clicked.connect(self._recommend)
        self.review.clicked.connect(self._review)
        self.bubble._card_layout.addLayout(row)
        self.next_button = QPushButton("查看下一项")
        self.next_button.setStyleSheet(f"background:transparent;color:#536a87;border:0;padding:{_ui_px(2)}px;")
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
            self.bubble.set_structured("等你确认", "#d99a20", f"{index + 1}/{len(self.pending)}" if len(self.pending) > 1 else "",
                                       short(request["title"], 24) + "\n" + body,
                                       short(request["title"], 24) + "\n" + body)
            self.bubble.snippet_label.setToolTip(request["title"] + "\n" + request["question"])
            self.recommended.setToolTip("提交：" + option["label"] if option else "未指定推荐方案，请自行选择")
            self.next_button.setVisible(len(self.pending) > 1)
            self.bubble._apply_size(self.bubble.height() - self.bubble.M_T - self.bubble.M_B
                                    + _ui_px(70) + (_ui_px(28) if len(self.pending) > 1 else 0))
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
