"""Qt comic-paper ornamentation shared by message and task bubbles."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen, QPainterPath


def outline(width, height, scale, theme, tail_x, tail_up=False, show_tail=True):
    """Different silhouettes around a shared, unobstructed text rectangle."""
    s=scale
    left,right=2*s,width-2*s
    top=15*s if tail_up and show_tail else 2*s
    bottom=height-15*s if show_tail and not tail_up else height-2*s
    tx=max(30*s,min(tail_x if tail_x>=0 else width/2,width-30*s))
    path=QPainterPath()
    if theme == 'thinking':
        # Continuous scalloped cloud, rather than dots printed on a rectangle.
        x0,x1=left+9*s,right-9*s
        y0,y1=top+8*s,bottom-8*s
        path.moveTo(x0,y0)
        count=max(4,round((x1-x0)/(42*s)))
        dx=(x1-x0)/count
        for i in range(count):
            x=x0+i*dx
            path.cubicTo(x+dx*.2,top-2*s,x+dx*.8,top-2*s,x+dx,y0)
        count_y=max(2,round((y1-y0)/(32*s)))
        dy=(y1-y0)/count_y
        for i in range(count_y):
            y=y0+i*dy
            path.cubicTo(right+2*s,y+dy*.2,right+2*s,y+dy*.8,x1,y+dy)
        for i in range(count):
            x=x1-i*dx
            path.cubicTo(x-dx*.2,bottom+2*s,x-dx*.8,bottom+2*s,x-dx,y1)
        for i in range(count_y):
            y=y1-i*dy
            path.cubicTo(left-2*s,y-dy*.2,left-2*s,y-dy*.8,x0,y-dy)
    elif theme == 'working':
        # Slanted panel with clipped corners; text stays horizontal.
        path.moveTo(left+13*s,top+4*s)
        for x,y in ((right-7*s,top),(right,bottom-12*s),(right-12*s,bottom),
                    (left,bottom-4*s),(left+5*s,top+14*s)):
            path.lineTo(x,y)
    elif theme == 'waiting':
        # Folded note, with a genuinely cut-away upper-right corner.
        path.moveTo(left+10*s,top)
        path.lineTo(right-22*s,top)
        path.lineTo(right,top+22*s)
        path.lineTo(right,bottom-10*s)
        path.quadTo(right,bottom,right-10*s,bottom)
        path.lineTo(left+10*s,bottom)
        path.quadTo(left,bottom,left,bottom-10*s)
        path.lineTo(left,top+10*s)
        path.quadTo(left,top,left+10*s,top)
    elif theme == 'success':
        # Broad, irregular rays radiate away from the centre (not a sawtooth box).
        w=right-left
        h=bottom-top
        vertices=((0,0),(.17,.10),(.23,0),(.36,.13),(.49,.02),(.56,.12),
                  (.77,0),(.80,.12),(1,.02),(.96,.29),(1,.38),(.96,.57),
                  (1,.76),(.95,.78),(.99,1),(.79,.87),(.71,1),(.57,.86),
                  (.43,1),(.35,.87),(.15,1),(.16,.87),(0,.98),(.035,.69),
                  (0,.59),(.04,.41),(0,.25),(.045,.22))
        path.moveTo(left+vertices[0][0]*w,top+vertices[0][1]*h)
        for x,y in vertices[1:]:
            # Cap vertical intrusion on tall confirmation/task cards.
            yy=top+y*h
            if y<.15: yy=top+min(y*h,9*s)
            if y>.85: yy=bottom-min((1-y)*h,9*s)
            path.lineTo(left+x*w,yy)
    else:
        # Celebration has long rays; a warning uses shallow, irregular teeth.
        depth=(10 if theme=='success' else 5)*s
        n=10 if theme=='success' else 13
        path.moveTo(left+11*s,top+depth)
        span=right-left-22*s
        for i in range(n):
            x=left+11*s+span*i/n
            path.lineTo(x+span*.4/n,top+(0 if i%2==0 else 2*s))
            path.lineTo(x+span/n,top+depth)
        path.lineTo(right,top+6*s)
        for i in range(3):
            y=top+12*s+(bottom-top-24*s)*i/3
            path.lineTo(right-depth,y)
            path.lineTo(right,y+(bottom-top-24*s)/6)
        path.lineTo(right-8*s,bottom-depth)
        for i in range(n):
            x=right-11*s-span*i/n
            path.lineTo(x-span*.4/n,bottom-(0 if i%2==0 else 2*s))
            path.lineTo(x-span/n,bottom-depth)
        path.lineTo(left,bottom-5*s)
        for i in range(3):
            y=bottom-12*s-(bottom-top-24*s)*i/3
            path.lineTo(left+depth,y)
            path.lineTo(left,y-(bottom-top-24*s)/6)
    path.closeSubpath()
    if show_tail:
        edge=top if tail_up else bottom
        direction=-1 if tail_up else 1
        tip=2*s if tail_up else height-2*s
        tail=QPainterPath()
        if theme=='thinking':
            tail.addEllipse(QPointF(tx-3*s,edge+direction*4*s),4*s,2.6*s)
            tail.addEllipse(QPointF(tx,tip-direction*1.5*s),2*s,1.5*s)
        else:
            tail.moveTo(tx-10*s,edge-direction*10*s)
            if theme=='working':
                tail.lineTo(tx+6*s,edge+direction*3*s)
                tail.lineTo(tx+1*s,edge+direction*4*s)
                tail.lineTo(tx,tip)
                tail.lineTo(tx-8*s,edge+direction*3*s)
            else:
                tail.lineTo(tx,tip)
            tail.lineTo(tx+10*s,edge-direction*10*s)
            tail.closeSubpath()
        path=path.united(tail)
    return path,top,bottom


def palette(color):
    hue = QColor(color).hue()
    if 250 <= hue <= 300:
        return 'thinking', '#f5f0ff', '#e5d9fb', '想一想'
    if 25 <= hue <= 65:
        return 'waiting', '#fff9e6', '#ffe7a2', '等你啦'
    if 75 <= hue <= 170:
        return 'success', '#f0fbef', '#d4efcd', '好耶'
    if hue < 25 or hue > 330:
        return 'alert', '#fff4ef', '#ffd9d0', '咦？'
    return 'working', '#f0f8ff', '#d6eafa', '加油'


def decorate(p, path, width, top, bottom, color, scale):
    theme = palette(color)[0]
    p.save()
    p.setClipPath(path)
    # A coloured spine and pale halftone corner keep the centre readable.
    p.fillRect(QRectF(0,top,width,6*scale),QColor(color))
    wash = QColor(color)
    wash.setAlpha(24)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(wash)
    for row in range(4):
        for col in range(7-row):
            p.drawEllipse(QPointF(width-(10+col*7)*scale,bottom-(6+row*7)*scale),
                          1.2*scale,1.2*scale)
    if theme == 'waiting':
        # A visible folded flap, not just a diagonally clipped corner.
        fold=QPainterPath(QPointF(width-24*scale,top))
        fold.lineTo(width-24*scale,top+22*scale)
        fold.lineTo(width-2*scale,top+22*scale)
        fold.closeSubpath()
        p.setPen(QPen(QColor('#8c7545'),scale))
        p.setBrush(QColor('#ffe4a1'))
        p.drawPath(fold)
    # Tiny state illustrations live in the bottom padding, away from controls.
    p.translate(21*scale,bottom-8*scale)
    p.scale(scale,scale)
    p.setPen(QPen(QColor(color),1.6,Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QColor(color))
    if theme == 'working':
        bolt=QPainterPath(QPointF(0,-5))
        for x,y in ((-4,1),(0,1),(-1,5),(5,-2),(1,-2)):
            bolt.lineTo(x,y)
        bolt.closeSubpath()
        p.drawPath(bolt)
        p.drawLine(QPointF(10,0),QPointF(26,0))
        p.drawLine(QPointF(31,0),QPointF(38,0))
    elif theme == 'success':
        for x,size in ((0,4),(16,3),(28,2)):
            p.drawLine(QPointF(x-size,0),QPointF(x+size,0))
            p.drawLine(QPointF(x,-size),QPointF(x,size))
    elif theme == 'waiting':
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0,0),4,4)
        p.drawLine(QPointF(0,-2),QPointF(0,0))
        p.drawLine(QPointF(0,0),QPointF(2,1))
        for x in (14,22,30):
            p.drawLine(QPointF(x,-2),QPointF(x+2,2))
    elif theme == 'alert':
        p.drawLine(QPointF(0,-4),QPointF(0,0))
        p.drawPoint(QPointF(0,4))
        p.drawLine(QPointF(10,0),QPointF(27,0))
    else:
        for x,size in ((0,2.6),(12,2),(22,1.4)):
            p.drawEllipse(QPointF(x,0),size,size)
    p.restore()
