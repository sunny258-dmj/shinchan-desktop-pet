"""High-resolution vector Shin-chan superhero puppet.

The renderer is intentionally asset-free: every visible edge is drawn with Qt paths
and antialiasing, so animation frames have stable transparent boundaries with no
colour-key spill, matte fringe or cutout jitter.
"""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

INK = QColor('#24201f')
SKIN = QColor('#ffd2a0')
SKIN_SHADE = QColor('#f2ad7c')
SUIT = QColor('#177cc1')
SUIT_DARK = QColor('#0d5f9f')
RED = QColor('#ed394a')
RED_DARK = QColor('#bf2334')
YELLOW = QColor('#ffd43b')
WHITE = QColor('#fffdf5')
HAIR = QColor('#171514')


def _elbow(a, b, side):
    dx, dy = b.x() - a.x(), b.y() - a.y()
    distance = max(.01, math.hypot(dx, dy))
    length = max(30., distance * .54)
    mid = distance / 2
    height = math.sqrt(max(0., length * length - mid * mid))
    return QPointF(a.x() + dx * .5 - side * dy / distance * height,
                   a.y() + dy * .5 + side * dx / distance * height)


def _path(points, closed=True):
    p = QPainterPath()
    if not points:
        return p
    p.moveTo(*points[0])
    for point in points[1:]:
        p.lineTo(*point)
    if closed:
        p.closeSubpath()
    return p


class Puppet:
    """Render a crisp 2x frame from the continuous pose produced by pet_scene_motion."""

    def __init__(self, _directory=None):
        pass

    def render(self, pose):
        frame = QPixmap(768, 832)
        frame.fill(Qt.GlobalColor.transparent)
        p = QPainter(frame)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.scale(2.0, 2.0)

        x, y = 192 + pose['x'], pose['y']
        angle = math.radians(pose['lean'])

        def bodypoint(dx, yy):
            return QPointF(x + dx * math.cos(angle) - (yy - 330) * math.sin(angle),
                           y + 330 + dx * math.sin(angle) + (yy - 330) * math.cos(angle))

        def outlined_path(path, fill, width=3.0, pen=INK):
            p.setPen(QPen(pen, width, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(QBrush(fill))
            p.drawPath(path)

        def limb(a, b, width, fill, outline=4.0):
            p.setPen(QPen(INK, width + outline, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(a, b)
            p.setPen(QPen(fill, width, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(a, b)

        def ellipse(rect, fill, outline=2.4):
            p.setPen(QPen(INK, outline))
            p.setBrush(fill)
            p.drawEllipse(rect)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(28, 37, 58, 28))
        p.drawEllipse(QRectF(x - 62, 389, 124, 16))

        p.save()
        collar = bodypoint(0, 263)
        p.translate(collar)
        p.rotate(pose['lean'] + pose['cape'] * .65)
        cape = QPainterPath()
        cape.moveTo(-42, 4)
        cape.cubicTo(-66, 34, -74 - pose['cape'] * .5, 77, -49 - pose['cape'] * .8, 119)
        cape.cubicTo(-14, 102, 11, 112, 48 + pose['cape'] * .7, 90)
        cape.cubicTo(36, 58, 48, 25, 41, 5)
        cape.lineTo(22, 15)
        cape.lineTo(-20, 15)
        cape.closeSubpath()
        grad = QLinearGradient(-50, 12, 48, 104)
        grad.setColorAt(0, QColor('#ff5263'))
        grad.setColorAt(1, RED_DARK)
        outlined_path(cape, grad, 3.2)
        p.restore()

        for side, fx, fy in ((-1, pose['flx'], pose['fly']), (1, pose['frx'], pose['fry'])):
            hip = bodypoint(side * 24, 329)
            ankle = QPointF(x + fx, min(0, y) + fy - 5)
            knee = QPointF((hip.x() + ankle.x()) * .5 + side * (4 + max(0, y) * .50),
                           (hip.y() + ankle.y()) * .5)
            limb(hip, knee, 15, SKIN)
            limb(knee, ankle, 13, SKIN)
            p.save()
            p.translate(ankle.x() + side * 4, ankle.y() + 4)
            shoe_angle = max(-22, min(22, (fy - 378) * side * .45))
            p.rotate(shoe_angle)
            if side < 0:
                p.scale(-1, 1)
            shoe = QPainterPath()
            shoe.moveTo(-18, -6)
            shoe.cubicTo(-10, -10, 5, -9, 15, -4)
            shoe.cubicTo(22, 0, 21, 8, 11, 10)
            shoe.lineTo(-14, 10)
            shoe.cubicTo(-20, 7, -22, 1, -18, -6)
            outlined_path(shoe, YELLOW, 2.7)
            p.setPen(QPen(RED_DARK, 2.2))
            p.drawLine(QPointF(-9, 5), QPointF(13, 5))
            p.restore()

        hands = []
        for side, hx, hy in ((-1, pose['lx'], pose['ly']), (1, pose['rx'], pose['ry'])):
            shoulder = bodypoint(side * 43, 267)
            wrist = bodypoint(hx, hy)
            joint = _elbow(shoulder, wrist, -side)
            limb(shoulder, joint, 20, SUIT)
            limb(joint, wrist, 13, SKIN)
            rotation = math.degrees(math.atan2(wrist.y() - joint.y(), wrist.x() - joint.x())) + 90
            hands.append((side, wrist, rotation))

        p.save()
        torso = bodypoint(0, 294)
        p.translate(torso)
        p.rotate(pose['lean'])
        body = QPainterPath()
        body.moveTo(-48, -39)
        body.cubicTo(-58, -18, -55, 27, -43, 48)
        body.cubicTo(-24, 58, 24, 58, 43, 48)
        body.cubicTo(55, 27, 58, -18, 48, -39)
        body.cubicTo(25, -50, -25, -50, -48, -39)
        outlined_path(body, SUIT, 3.2)
        p.setPen(QPen(SUIT_DARK, 2.0))
        p.drawArc(QRectF(-44, -37, 88, 74), 208 * 16, 124 * 16)
        collar = _path([(-29, -39), (0, -22), (29, -39), (18, -50), (0, -38), (-18, -50)])
        outlined_path(collar, RED, 2.0)
        p.setPen(QPen(INK, 2.0))
        p.setBrush(YELLOW)
        p.drawRoundedRect(QRectF(-39, 30, 78, 13), 5, 5)
        p.setBrush(RED)
        p.drawRoundedRect(QRectF(-32, 41, 64, 14), 5, 5)
        star = QPainterPath()
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = 13 if i % 2 == 0 else 5.7
            pt = QPointF(math.cos(a) * r, math.sin(a) * r - 1)
            if i == 0:
                star.moveTo(pt)
            else:
                star.lineTo(pt)
        star.closeSubpath()
        outlined_path(star, YELLOW, 2.1, RED_DARK)
        p.restore()

        if pose['laptop'] > .01:
            p.save()
            p.setOpacity(min(1., pose['laptop']))
            screen = QPainterPath()
            screen.addRoundedRect(QRectF(139, 306, 106, 62), 7, 7)
            outlined_path(screen, QColor('#dcecf7'), 3.0)
            p.setPen(QPen(QColor('#87a7bb'), 1.8))
            p.setBrush(QColor('#f8fcff'))
            p.drawRoundedRect(QRectF(148, 314, 88, 44), 4, 4)
            p.setPen(QPen(INK, 2.5))
            p.setBrush(QColor('#b8cbd8'))
            p.drawRoundedRect(QRectF(132, 366, 120, 12), 5, 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(YELLOW)
            p.drawEllipse(QRectF(188, 330, 8, 8))
            p.restore()

        if pose['board'] > .01:
            p.save()
            p.setOpacity(min(1., pose['board']))
            center = bodypoint(-5, 305 + pose['board_y'])
            p.translate(center)
            p.rotate(pose['lean'] + pose['board_angle'])
            board = QPainterPath()
            board.addRoundedRect(QRectF(-38, -50, 76, 100), 7, 7)
            outlined_path(board, QColor('#f7fbff'), 2.8)
            p.setPen(QPen(QColor('#97a8b6'), 1.6))
            for yy in (-27, -10, 7, 24):
                p.drawLine(QPointF(-23, yy), QPointF(23, yy))
            p.setPen(QPen(RED, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(-22, -37), QPointF(-12, -28))
            p.drawLine(QPointF(-12, -28), QPointF(3, -44))
            p.restore()

        head = bodypoint(pose['turn'] * 7, 174)
        p.save()
        p.translate(head)
        p.rotate(pose['lean'] + pose['head'])
        turn = max(-1., min(1., pose['turn']))
        face_scale = 1.0 - .08 * abs(turn)
        p.scale(face_scale, 1.0)

        ear_x = 83 if turn >= 0 else -83
        ellipse(QRectF(ear_x - 14, -4, 29, 42), SKIN, 2.7)
        p.setPen(QPen(SKIN_SHADE, 2.0))
        p.drawArc(QRectF(ear_x - 8, 6, 15, 20), 70 * 16, 205 * 16)

        face = QPainterPath()
        face.moveTo(-72, -62)
        face.cubicTo(-97, -44, -99, 7, -85, 38)
        face.cubicTo(-74, 66, -40, 78, -3, 76)
        face.cubicTo(38, 82, 77, 63, 88, 30)
        face.cubicTo(101, -6, 87, -49, 60, -65)
        face.cubicTo(28, -82, -42, -82, -72, -62)
        outlined_path(face, SKIN, 3.5)

        hair = QPainterPath()
        hair.moveTo(-75, -58)
        hair.cubicTo(-50, -87, 34, -91, 70, -58)
        hair.lineTo(55, -56)
        hair.lineTo(46, -69)
        hair.lineTo(32, -57)
        hair.lineTo(18, -72)
        hair.lineTo(3, -58)
        hair.lineTo(-12, -72)
        hair.lineTo(-28, -56)
        hair.lineTo(-43, -70)
        hair.lineTo(-56, -54)
        hair.closeSubpath()
        outlined_path(hair, HAIR, 2.6)

        brow_raise = -4 * pose['happy'] + 4 * pose['puzzled']
        p.setPen(QPen(HAIR, 7.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-48 + turn * 8, -30 + brow_raise), QPointF(-12 + turn * 5, -34 - pose['puzzled'] * 5))
        if abs(turn) < .72:
            p.drawLine(QPointF(15 + turn * 5, -34 - pose['puzzled'] * 4), QPointF(51 + turn * 7, -29 + brow_raise))

        blink = max(0., min(1., pose['blink']))
        eye_centres = [(-30 + turn * 13, 1)]
        if abs(turn) < .72:
            eye_centres.append((30 + turn * 11, 1))
        for ex, ey in eye_centres:
            p.setPen(QPen(INK, 2.6))
            p.setBrush(WHITE)
            p.drawEllipse(QRectF(ex - 18, ey - 18 * (1 - blink), 36, max(3, 36 * (1 - blink))))
            if blink < .78:
                px = ex + pose['eye_x'] * 5 + turn * 2
                py = ey + pose['eye_y'] * 4 + 4
                p.setBrush(HAIR)
                p.drawEllipse(QRectF(px - 9, py - 10 * (1 - blink), 18, max(3, 20 * (1 - blink))))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(WHITE)
                p.drawEllipse(QRectF(px - 4, py - 6, 5, 5))

        p.setPen(QPen(SKIN_SHADE, 2.0))
        p.drawArc(QRectF(-6 + turn * 14, 8, 18, 15), 220 * 16, 120 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        cheek = QColor(255, 118, 119, int(40 + 75 * pose['happy']))
        p.setBrush(cheek)
        p.drawEllipse(QRectF(-68, 28, 29, 15))
        if abs(turn) < .8:
            p.drawEllipse(QRectF(42, 28, 29, 15))

        p.setPen(QPen(INK, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if pose['happy'] > .45:
            mouth = QPainterPath()
            mouth.moveTo(-22 + turn * 10, 42)
            mouth.cubicTo(-8, 61, 22, 61, 37 + turn * 7, 40)
            mouth.cubicTo(20, 72, -8, 70, -22 + turn * 10, 42)
            mouth.closeSubpath()
            p.setBrush(QColor('#a72c3a'))
            p.drawPath(mouth)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#f47783'))
            p.drawEllipse(QRectF(2, 53, 22, 9))
        elif pose['puzzled'] > .45:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(-13 + turn * 8, 43, 30, 17), 25 * 16, 130 * 16)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(-16 + turn * 8, 38, 34, 20), 205 * 16, 130 * 16)
        p.restore()

        for side, wrist, rotation in hands:
            p.save()
            p.translate(wrist)
            p.rotate(rotation)
            if side == 1 and pose['thumb'] > .4:
                hand = QPainterPath()
                hand.moveTo(-10, 11)
                hand.cubicTo(-15, 4, -13, -5, -7, -8)
                hand.lineTo(-2, -8)
                hand.lineTo(2, -22)
                hand.cubicTo(4, -29, 11, -29, 13, -23)
                hand.lineTo(12, -9)
                hand.cubicTo(22, -8, 24, 0, 19, 7)
                hand.cubicTo(12, 15, -3, 17, -10, 11)
                outlined_path(hand, SKIN, 2.6)
            elif pose['board'] > .5 or pose['laptop'] > .5:
                ellipse(QRectF(-10, -8, 20, 17), SKIN, 2.2)
                p.setPen(QPen(SKIN_SHADE, 1.5))
                p.drawLine(QPointF(-5, -3), QPointF(-5, 3))
            else:
                palm = QPainterPath()
                palm.addEllipse(QRectF(-11, -10, 22, 22))
                outlined_path(palm, SKIN, 2.3)
                p.setPen(QPen(INK, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                for dx in (-7, -2, 3, 8):
                    p.drawLine(QPointF(dx, -6), QPointF(dx + side * 1.5, -13))
            p.restore()
            if side == 1 and pose['pencil'] > .01:
                p.save()
                p.setOpacity(min(1., pose['pencil']))
                p.translate(wrist.x() - 5, wrist.y() - 12)
                p.rotate(-25)
                p.setPen(QPen(INK, 1.4))
                p.setBrush(YELLOW)
                p.drawRoundedRect(QRectF(-3, -20, 6, 37), 2, 2)
                p.setBrush(RED)
                p.drawRect(QRectF(-3, -20, 6, 6))
                p.restore()

        if pose['happy'] > .88:
            p.setPen(QPen(YELLOW, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for sx, sy, r in ((126, 92, 6), (262, 126, 4)):
                p.drawLine(QPointF(sx - r, sy), QPointF(sx + r, sy))
                p.drawLine(QPointF(sx, sy - r), QPointF(sx, sy + r))

        p.end()
        return frame
