"""Pastel comic-card bubble styling for the V4 desktop pet UI.

The visual language matches the approved concept: soft white cards, light state tint,
rounded corners, clear tails, small playful ornaments, and unobstructed text areas.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen


def palette(color):
    hue = QColor(color).hue()
    if 250 <= hue <= 300:
        return 'thinking', '#fbf8ff', '#eee6ff', '想一想'
    if 25 <= hue <= 65:
        return 'waiting', '#fffdf6', '#fff1c7', '等等我'
    if 75 <= hue <= 170:
        return 'success', '#f8fff9', '#dff7e5', '好耶'
    if hue < 25 or hue > 330:
        return 'alert', '#fff9f9', '#ffe2e7', '咦？'
    return 'working', '#f8fcff', '#e2f2ff', '加油'


def outline(width, height, scale, theme, tail_x, tail_up=False, show_tail=True):
    """Rounded speech-card silhouette with a compact, stable tail."""
    s = scale
    top_pad = 12 * s if tail_up and show_tail else 2 * s
    bottom_pad = 12 * s if show_tail and not tail_up else 2 * s
    left, right = 2 * s, width - 2 * s
    top, bottom = top_pad, height - bottom_pad
    radius = 18 * s
    path = QPainterPath()
    path.addRoundedRect(QRectF(left, top, right - left, bottom - top), radius, radius)

    if show_tail:
        tx = max(left + 34 * s, min(tail_x if tail_x >= 0 else width / 2, right - 34 * s))
        tail = QPainterPath()
        if tail_up:
            tail.moveTo(tx - 11 * s, top + 4 * s)
            tail.quadTo(tx - 3 * s, top - 1 * s, tx, 2 * s)
            tail.quadTo(tx + 4 * s, top - 1 * s, tx + 12 * s, top + 5 * s)
        else:
            tail.moveTo(tx - 11 * s, bottom - 4 * s)
            tail.quadTo(tx - 3 * s, bottom + 1 * s, tx, height - 2 * s)
            tail.quadTo(tx + 4 * s, bottom + 1 * s, tx + 12 * s, bottom - 5 * s)
        tail.closeSubpath()
        path = path.united(tail)
    return path, top, bottom


def decorate(p, path, width, top, bottom, color, scale):
    """Subtle state tint and playful ornaments; never intrude into the text block."""
    theme = palette(color)[0]
    s = scale
    accent = QColor(color)

    p.save()
    p.setClipPath(path)

    wash = QColor(accent)
    wash.setAlpha(34)
    p.fillRect(QRectF(0, top, width, 23 * s), wash)

    rail = QColor(accent)
    rail.setAlpha(205)
    p.fillRect(QRectF(14 * s, top + 1.5 * s, max(0, width - 28 * s), 2.4 * s), rail)

    dot = QColor(accent)
    dot.setAlpha(34)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(dot)
    for row in range(3):
        for col in range(5 - row):
            r = (1.1 + .2 * (col % 2)) * s
            x = width - (13 + col * 7) * s
            y = bottom - (8 + row * 7) * s
            p.drawEllipse(QPointF(x, y), r, r)

    p.translate(20 * s, bottom - 9 * s)
    p.scale(s, s)
    p.setPen(QPen(accent, 1.8, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)

    if theme == 'working':
        p.drawRoundedRect(QRectF(-3, -5, 12, 8), 1.5, 1.5)
        p.drawLine(QPointF(-5, 5), QPointF(11, 5))
        p.drawLine(QPointF(17, -5), QPointF(14, 1))
        p.drawLine(QPointF(14, 1), QPointF(19, 1))
        p.drawLine(QPointF(19, 1), QPointF(16, 6))
    elif theme == 'thinking':
        p.drawEllipse(QPointF(0, 0), 4.5, 4.5)
        p.drawEllipse(QPointF(11, -3), 2.3, 2.3)
        p.drawEllipse(QPointF(18, -6), 1.2, 1.2)
    elif theme == 'waiting':
        p.drawEllipse(QPointF(0, 0), 4.5, 4.5)
        p.drawLine(QPointF(0, -3), QPointF(0, 0))
        p.drawLine(QPointF(0, 0), QPointF(2.5, 1.5))
        for x in (13, 21, 29):
            p.drawEllipse(QPointF(x, 1), .8, .8)
    elif theme == 'success':
        for x, r in ((0, 4), (14, 3), (25, 2)):
            p.drawLine(QPointF(x - r, 0), QPointF(x + r, 0))
            p.drawLine(QPointF(x, -r), QPointF(x, r))
    else:
        p.drawLine(QPointF(0, -5), QPointF(0, 1))
        p.drawPoint(QPointF(0, 5))
        p.drawLine(QPointF(10, 0), QPointF(28, 0))

    p.restore()
