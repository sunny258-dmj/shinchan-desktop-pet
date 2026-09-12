"""Reference-locked V5 character renderer.

This renderer intentionally does *not* redraw Shin-chan.  It reconstructs the
approved pose atlas extracted from the user's reference board and displays those
poses directly.  Runtime motion is limited to timing, subtle whole-body
translation/rotation, mirroring for travel direction, and short crossfades.
That keeps the face, proportions, superhero outfit, cape, colours and silhouette
locked to the approved reference.
"""
from __future__ import annotations

import base64
import math
import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap


REFERENCE_LOCKED = True
ATLAS_COLS = 8
ATLAS_ROWS = 12
CELL_W = 192
CELL_H = 208
OUT_W = 768
OUT_H = 832

# Rows follow the user's reference board from top to bottom.
STATE_ROWS = {
    "idle": 0,
    "look": 1,
    "thinking": 2,
    "running": 3,
    "running-left": 4,
    "running-right": 4,
    "review": 5,
    "waiting": 6,
    "failed": 7,
    "waving": 8,
    "jumping": 9,
    "hero-celebrate": 10,
    "long-work": 11,
}
FRAME_COUNTS = {
    "idle": 7,
    "look": 5,
    "thinking": 6,
    "running": 7,
    "running-left": 7,
    "running-right": 7,
    "review": 6,
    "waiting": 7,
    "failed": 7,
    "waving": 6,
    "jumping": 7,
    "hero-celebrate": 6,
    "long-work": 6,
}

# One complete visual story per state.  Travel repeats the gait once so the
# six-second move state reads as actual locomotion rather than a slow slideshow.
VISUAL_DURATIONS = {
    "idle": 24.0,
    "look": 4.0,
    "thinking": 14.6,
    "running": 18.6,
    "running-left": 6.4,
    "running-right": 6.4,
    "review": 15.8,
    "waiting": 16.8,
    "failed": 14.8,
    "waving": 4.9,
    "jumping": 4.4,
    "hero-celebrate": 6.6,
    "long-work": 8.0,
}


class Puppet:
    """Render the approved reference character at 4x logical resolution."""

    def __init__(self, directory=None):
        root = Path(directory) if directory else Path(__file__).resolve().parent.parent / "assets"
        self._asset_dir = root
        self._atlas = self._load_reference_atlas(root)
        self._state = "idle"
        self._state_since = time.monotonic()
        self._candidate = "idle"
        self._candidate_since = self._state_since

    @staticmethod
    def _load_reference_atlas(root: Path) -> QPixmap:
        parts = sorted(root.glob("reference-poses-v5.part*.b64"))
        if not parts:
            raise FileNotFoundError(
                "V5 reference atlas fragments are missing: "
                f"{root / 'reference-poses-v5.part00.b64'}"
            )
        encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
        data = base64.b64decode(encoded)
        atlas = QPixmap()
        if not atlas.loadFromData(data, "PNG"):
            raise ValueError("Unable to decode the V5 approved reference pose atlas")
        expected = (ATLAS_COLS * CELL_W, ATLAS_ROWS * CELL_H)
        if (atlas.width(), atlas.height()) != expected:
            raise ValueError(
                f"V5 atlas size mismatch: {atlas.width()}x{atlas.height()}, "
                f"expected {expected[0]}x{expected[1]}"
            )
        return atlas

    def _classify(self, pose) -> str:
        """Infer the live scene without changing the legacy caller interface.

        The existing main window historically calls ``render(pose)`` only.  V5
        keeps that API so task/event logic stays untouched, while this classifier
        chooses the matching approved reference row from the continuous pose.
        """
        laptop = float(pose.get("laptop", 0.0))
        board = float(pose.get("board", 0.0))
        puzzled = float(pose.get("puzzled", 0.0))
        happy = float(pose.get("happy", 0.0))
        thumb = float(pose.get("thumb", 0.0))
        turn = float(pose.get("turn", 0.0))
        lean = float(pose.get("lean", 0.0))
        y = float(pose.get("y", 0.0))
        lx, ly = float(pose.get("lx", -64)), float(pose.get("ly", 317))
        rx, ry = float(pose.get("rx", 64)), float(pose.get("ry", 317))
        eye_x = float(pose.get("eye_x", 0.0))

        # Strong semantic props first.
        if board > 0.18:
            return "review"
        if laptop > 0.18:
            # After a sustained work session, rotate through the approved
            # long-work variants without inventing a new visual design.
            if self._state == "running" and time.monotonic() - self._state_since > 11.5:
                return "long-work"
            return "running"
        if puzzled > 0.30:
            return "failed"

        # Travel has the strongest body lean/turn combination.
        if abs(lean) > 3.2 and abs(turn) > 0.30:
            return "running-left" if turn < 0 else "running-right"

        # Airborne celebration / jump.
        if y < -10 or (happy > 0.86 and abs(float(pose.get("cape", 0.0))) > 7):
            # Hero celebration tends to finish with a prominent thumbs-up.
            return "hero-celebrate" if thumb > 0.55 else "jumping"

        # Explicit happy arm motion is the wave sequence.
        if happy > 0.58 and max(rx, -lx) > 72 and min(ry, ly) < 260:
            return "waving"

        # Waiting uses a quiet prompt / thumbs-up gesture, not a broad smile.
        if thumb > 0.32 and happy < 0.58:
            return "waiting"

        # Thinking keeps one hand close to the face and the head noticeably tilted.
        if happy < 0.45 and puzzled < 0.25 and abs(float(pose.get("head", 0.0))) > 4.5:
            if ry < 250 or ly < 286:
                return "thinking"

        # Pointer hover: gaze/turn changes while the body remains mostly upright.
        if abs(lean) < 3.0 and (abs(eye_x) > 0.12 or abs(turn) > 0.16):
            return "look"

        return "idle"

    def _stable_state(self, pose) -> str:
        now = time.monotonic()
        candidate = self._classify(pose)
        if candidate != self._candidate:
            self._candidate = candidate
            self._candidate_since = now

        # Avoid flicker from the 350 ms scene-entry blend in the main window.
        hold = 0.12 if candidate in ("running-left", "running-right", "jumping", "hero-celebrate") else 0.20
        if candidate != self._state and now - self._candidate_since >= hold:
            self._state = candidate
            self._state_since = now
        return self._state

    def _look_index(self, pose) -> int:
        gaze = float(pose.get("eye_x", 0.0)) + float(pose.get("turn", 0.0)) * 0.55
        if gaze <= -0.45:
            return 0
        if gaze <= -0.12:
            return 1
        if gaze < 0.14:
            return 2
        if gaze < 0.45:
            return 3
        return 4

    def _frame_phase(self, state: str, elapsed: float):
        count = FRAME_COUNTS[state]
        if state == "look":
            return 0, 0, 0.0

        duration = VISUAL_DURATIONS[state]
        loops = 2.0 if state in ("running-left", "running-right") else 1.0
        position = (elapsed % duration) / duration * count * loops
        base = int(math.floor(position))
        index = base % count
        nxt = (index + 1) % count

        # Keep reference poses crisp most of the time; only blend near the
        # boundary so the transition reads smoothly without ghosting all frames.
        frac = position - math.floor(position)
        if frac < 0.78:
            blend = 0.0
        else:
            u = (frac - 0.78) / 0.22
            blend = u * u * (3.0 - 2.0 * u)
        return index, nxt, blend

    def _cell(self, row: int, col: int, mirror=False) -> QPixmap:
        pix = self._atlas.copy(col * CELL_W, row * CELL_H, CELL_W, CELL_H)
        if mirror:
            from PySide6.QtGui import QTransform
            pix = pix.transformed(
                QTransform().scale(-1, 1),
                Qt.TransformationMode.SmoothTransformation,
            )
        return pix

    def render(self, pose):
        state = self._stable_state(pose)
        elapsed = max(0.0, time.monotonic() - self._state_since)

        # Running-right uses the row as extracted from the reference board;
        # running-left mirrors exactly that approved art instead of redrawing it.
        mirror = state == "running-left"
        row_state = "running-right" if state == "running-left" else state

        if state == "look":
            idx = self._look_index(pose)
            nxt, blend = idx, 0.0
        else:
            idx, nxt, blend = self._frame_phase(row_state, elapsed)

        row = STATE_ROWS[row_state]
        a = self._cell(row, idx, mirror)
        b = self._cell(row, nxt, mirror) if blend > 0 else None

        out = QPixmap(OUT_W, OUT_H)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Small whole-body motion is allowed because it does not change the
        # approved design.  It keeps the desktop pet alive between key poses.
        bob = math.sin(elapsed * 2.2) * (0.8 if state in ("idle", "waiting", "thinking") else 0.35)
        dx = float(pose.get("x", 0.0)) * 0.12
        dy = float(pose.get("y", 0.0)) * 0.08 + bob
        angle = float(pose.get("lean", 0.0)) * 0.10

        p.save()
        p.scale(4.0, 4.0)
        p.translate(CELL_W / 2 + dx, CELL_H / 2 + dy)
        p.rotate(angle)
        p.translate(-CELL_W / 2, -CELL_H / 2)

        p.setOpacity(1.0)
        p.drawPixmap(QRectF(0, 0, CELL_W, CELL_H), a, QRectF(0, 0, CELL_W, CELL_H))
        if b is not None and blend > 0:
            p.setOpacity(blend)
            p.drawPixmap(QRectF(0, 0, CELL_W, CELL_H), b, QRectF(0, 0, CELL_W, CELL_H))
        p.restore()
        p.end()
        return out
