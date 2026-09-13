"""Small reference-board props, drawn in the same coordinate system as the pet."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen, QFont


def draw_effects(p, pose, head):
    # Keep effects away from the outer frame even during a jump or a lean.
    x = min(322., max(60., head.x() + 110))
    y = max(36., head.y() - 72)
    for name in ('idea', 'question', 'heart', 'tear'):
        opacity = max(0., min(1., pose.get(name, 0.)))
        if opacity < .01:
            continue
        p.save()
        p.setOpacity(opacity)
        p.translate(x, y)
        p.setPen(QPen(QColor('#25202b'), 2.5))
        if name == 'idea':
            p.setBrush(QColor('#ffe46b'))
            p.drawEllipse(QRectF(-12, -15, 24, 27))
            p.drawLine(QPointF(-6, 12), QPointF(6, 12))
            p.drawLine(QPointF(-5, 17), QPointF(5, 17))
            p.setPen(QPen(QColor('#f6b82b'), 2.7))
            for i in range(7):
                a = i * math.pi / 4
                p.drawLine(QPointF(math.cos(a)*21, math.sin(a)*21-3),
                           QPointF(math.cos(a)*27, math.sin(a)*27-3))
        elif name == 'question':
            p.setBrush(QColor('#f5fbff'))
            bubble = QPainterPath()
            bubble.addRoundedRect(QRectF(-22, -19, 44, 31), 12, 12)
            tail = QPainterPath()
            tail.moveTo(-10, 8)
            tail.lineTo(-16, 23)
            tail.lineTo(0, 10)
            tail.closeSubpath()
            p.drawPath(bubble.united(tail))
            p.setFont(QFont('Segoe UI', 15, QFont.Weight.Bold))
            p.drawText(QRectF(-20, -21, 40, 33), Qt.AlignmentFlag.AlignCenter, '?')
        elif name == 'heart':
            heart = QPainterPath()
            heart.moveTo(0, 14)
            heart.cubicTo(-32, -5, -13, -25, 0, -11)
            heart.cubicTo(13, -25, 32, -5, 0, 14)
            p.setPen(QPen(QColor('#df3e68'), 2))
            p.setBrush(QColor('#ff7998'))
            p.drawPath(heart)
        else:
            p.translate(-75, 83)
            drop = QPainterPath()
            drop.moveTo(0, -10)
            drop.cubicTo(-18, 15, 18, 15, 0, -10)
            p.setBrush(QColor('#9cdefa'))
            p.setPen(QPen(QColor('#448bd0'), 2))
            p.drawPath(drop)
        p.restore()


def draw_cup(p, wrist, amount):
    if amount < .01:
        return
    p.save()
    p.setOpacity(min(1., amount))
    p.translate(wrist.x()-10, wrist.y()-15)
    p.setPen(QPen(QColor('#233c42'), 2.5))
    p.setBrush(QColor('#49b79c'))
    p.drawRoundedRect(QRectF(-12, -16, 28, 37), 5, 5)
    p.setPen(QPen(QColor('#ffe594'), 3))
    p.drawLine(QPointF(0, -14), QPointF(3, -33))
    p.drawLine(QPointF(3, -33), QPointF(12, -36))
    p.setBrush(QColor('#fff2b9'))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(-5, -6, 13, 15))
    p.restore()
