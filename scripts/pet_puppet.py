"""Stable cutout character rendered from joint poses, with no whole-body swaps."""
import math
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QRegion


@lru_cache(maxsize=2)
def load_parts(directory):
    image=QImage(str(Path(directory)/'puppet-v3.png')).convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull():
        raise ValueError('缺少 puppet-v3.png 动画部件素材')
    pixels=image.bits()
    for i in range(0,image.sizeInBytes(),4):
        r,g,b=pixels[i],pixels[i+1],pixels[i+2]
        if r>170 and b>150 and g<min(r,b)*.72:
            pixels[i+3]=0
        elif min(r,b)>g+20:
            spill=min(r,b)-g
            pixels[i],pixels[i+2]=r-spill,b-spill
    atlas=QPixmap.fromImage(image)
    names=('head','happy','side','puzzled','body','cape','hand','thumb','shoe','laptop','board','pencil')
    parts={}
    for i,name in enumerate(names):
        x0=round((i%4)*image.width()/4)
        x1=round((i%4+1)*image.width()/4)
        y0=round((i//4)*image.height()/3)
        y1=round((i//4+1)*image.height()/3)
        pix=atlas.copy(x0,y0,x1-x0,y1-y0)
        bounds=QRegion(pix.mask()).boundingRect()
        if bounds.isEmpty(): raise ValueError(f'动画部件为空: {name}')
        parts[name]=pix.copy(bounds)
    return parts


def elbow(a,b,side):
    dx,dy=b.x()-a.x(),b.y()-a.y()
    distance=max(.01,math.hypot(dx,dy))
    length=max(29,distance*.51)
    mid=distance/2
    height=math.sqrt(max(0,length*length-mid*mid))
    return QPointF(a.x()+dx*.5-side*dy/distance*height,
                   a.y()+dy*.5+side*dx/distance*height)


class Puppet:
    def __init__(self,directory):
        self.parts=load_parts(directory)

    def render(self,pose):
        frame=QPixmap(384,416)
        frame.fill(Qt.GlobalColor.transparent)
        p=QPainter(frame)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        x,y=192+pose['x'],pose['y']
        angle=math.radians(pose['lean'])

        def bodypoint(dx,yy):
            return QPointF(x+dx*math.cos(angle)-(yy-330)*math.sin(angle),
                           y+330+dx*math.sin(angle)+(yy-330)*math.cos(angle))

        def art(name,center,w,h,rotation=0,mirror=False,opacity=1):
            p.save()
            p.setOpacity(max(0,min(1,opacity)))
            p.translate(center)
            p.rotate(rotation)
            if mirror:p.scale(-1,1)
            p.drawPixmap(QRectF(-w/2,-h/2,w,h),self.parts[name],QRectF(self.parts[name].rect()))
            p.restore()

        def segment(a,b,width,color):
            p.setPen(QPen(QColor('#242424'),width+4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            p.drawLine(a,b)
            p.setPen(QPen(QColor(color),width,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            p.drawLine(a,b)

        # The cape lags independently behind the torso, pivoting at the collar.
        cape_angle=pose['lean']+pose['cape']
        cape_center=bodypoint(-math.sin(math.radians(pose['cape']))*55,306)
        art('cape',cape_center,159,142,cape_angle)
        for side,fx,fy in ((-1,pose['flx'],pose['fly']),(1,pose['frx'],pose['fry'])):
            hip=bodypoint(side*25,330)
            ankle=QPointF(x+fx,min(0,y)+fy-4)
            knee=QPointF((hip.x()+ankle.x())*.5+side*(3+max(0,y)*.55),
                         (hip.y()+ankle.y())*.5)
            segment(hip,knee,15,'#ffca91')
            segment(knee,ankle,13,'#ffca91')
            art('shoe',QPointF(ankle.x()+side*3,ankle.y()+5),39,20,
                max(-20,min(20,(fy-378)*side*.4)),mirror=side<0)

        hands=[]
        for side,hx,hy in ((-1,pose['lx'],pose['ly']),(1,pose['rx'],pose['ry'])):
            shoulder=bodypoint(side*45,267)
            wrist=bodypoint(hx,hy)
            joint=elbow(shoulder,wrist,-side)
            segment(shoulder,joint,21,'#087dc4')
            segment(joint,wrist,14,'#ffca91')
            rotation=math.degrees(math.atan2(wrist.y()-joint.y(),wrist.x()-joint.x()))+90
            hands.append((side,wrist,rotation))
        art('body',bodypoint(0,291),117,103,pose['lean'])
        head=bodypoint(pose['turn']*7,174)
        # Expression variants share the same bounding box; only expressions change.
        name='happy' if pose['happy']>.5 else 'puzzled' if pose['puzzled']>.5 else 'head'
        if abs(pose['turn'])>.45 and name=='head': name='side'
        head_angle=pose['lean']+pose['head']
        art(name,head,207,183,head_angle,mirror=name=='side' and pose['turn']<0)
        if name=='head':
            p.save()
            p.translate(head)
            p.rotate(head_angle)
            # Pupils lead the head during gaze tracking; eyelids close independently.
            for ex in (-28,28):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#ffdd31'))
                p.drawEllipse(QRectF(ex-21,-14,42,46))
                blink=pose['blink']
                p.setBrush(QColor('#11120b'))
                px=ex+pose['eye_x']*3
                py=9+pose['eye_y']*2
                p.drawEllipse(QRectF(px-15,py-17*(1-blink),30,max(2,34*(1-blink))))
                if blink<.7:
                    p.setBrush(QColor('#fffef1'))
                    p.drawEllipse(QPointF(px-3,py-4),5,5*(1-blink))
            p.restore()
        if pose['board']>.01:
            art('board',bodypoint(-6,306+pose['board_y']),74,99,
                pose['lean']+pose['board_angle'],opacity=pose['board'])
            p.save()
            p.setOpacity(pose['board'])
            p.translate(bodypoint(-6,306+pose['board_y']))
            p.rotate(pose['lean']+pose['board_angle'])
            p.setPen(QPen(QColor('#a1a8aa'),1.5))
            for yy in (-23,-8,7,22): p.drawLine(QPointF(-20,yy),QPointF(22,yy))
            p.restore()
        if pose['laptop']>.01:
            # Desk prop is in world coordinates: no bouncing with the torso.
            art('laptop',QPointF(192,345),151,101,opacity=pose['laptop'])
        for side,wrist,rotation in hands:
            if side==1 and pose['thumb']>.4:
                art('thumb',wrist,34,37,-8)
            elif pose['board']>.5 or pose['laptop']>.5:
                # Closed grip over a prop rather than an outstretched waving palm.
                p.setPen(QPen(QColor('#292321'),2))
                p.setBrush(QColor('#ffca91'))
                p.drawEllipse(wrist,10,8)
                p.drawLine(QPointF(wrist.x()-3,wrist.y()-4),QPointF(wrist.x()-3,wrist.y()+1))
            else:
                art('hand',wrist,26,28,rotation,mirror=side==1)
            if side==1 and pose['pencil']>.01:
                art('pencil',QPointF(wrist.x()-5,wrist.y()-12),8,41,-25,opacity=pose['pencil'])
        p.end()
        return frame
