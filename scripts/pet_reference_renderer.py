"""Render supplied dinosaur art without synthetic limb meshes."""
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap, QTransform


def sequence(keys, hold):
    return [(key, hold) for key in keys]


TIMELINES = {
    'idle': [((0,0),2.4), ((0,1),.12), ((0,2),1.5), ((0,3),.8),
             ((0,4),1.2), ((0,5),.8), ((1,0),.6), ((1,1),.6),
             ((1,2),.7), ((1,3),1.4), ((1,4),.8), ((1,5),1.5)],
    'running': [((4,0),.7), ((4,1),.4)] + sequence([(4,i) for _ in range(3) for i in (1,2,4,1)],.24)
               + sequence([(4,3),(4,5),(5,0),(5,1),(5,2),(5,3),(5,4),(5,5)],.65),
    # 思考只取鼠标互动图中的托腮、疑惑、灵光与安静注视；绝不混入工作图。
    'thinking': sequence([(2,3),(2,4),(2,5),(3,0),(3,3),(3,4),(3,5)],.75),
    'review': sequence([(4,5),(5,1),(5,2),(4,4),(5,0),(5,3)],.7),
    'waiting': sequence([(2,0),(2,1),(2,2),(2,3),(2,4),(2,5)],.85),
    'failed': sequence([(2,3),(2,4),(2,5),(0,1),(1,4),(3,3)],.75),
    'waving': sequence([(3,3),(3,4),(3,1),(3,2),(3,5),(3,3)],.35),
    'jumping': sequence([(8,0),(8,1),(8,3),(9,0),(9,3),(9,4),(9,5)],.25),
    'hero-celebrate': sequence([(3,0),(3,1),(3,2),(3,4),(3,5),(3,3)],.4),
    'running-left': sequence([(8,i) for i in range(1,6)]+[(9,i) for i in range(4)],.105),
    'walking-left': sequence([(r,c) for r in (6,7) for c in range(6)],.16),
}
TIMELINES['running-right'] = TIMELINES['running-left']
TIMELINES['walking-right'] = TIMELINES['walking-left']
CLIPS = {state: list(dict.fromkeys(key for key, _ in timeline)) for state,timeline in TIMELINES.items()}


def playback_duration(state):
    return 4. if state == 'look' else sum(hold for _, hold in TIMELINES[state])


def select_frame(state, elapsed, gaze=(0.,0.)):
    if state == 'look':
        x,y = gaze
        if abs(x) > .35:
            return (2,0 if x < 0 else 5)
        return (2,1) if y < -.25 else (2,4) if y > .25 else (3,3)
    if state == 'idle' and elapsed >= 120:
        return [(1,0),(1,1),(1,2),(1,5)][min(3,int((elapsed-120)/3))]
    t = max(0.,elapsed) % playback_duration(state)
    for key,hold in TIMELINES[state]:
        if t < hold:
            return key
        t -= hold
    return TIMELINES[state][-1][0]


@lru_cache(maxsize=2)
def _load(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'dinosaur-actions.json').read_text(encoding='utf-8'))
    path = directory/manifest['image']
    if manifest['version'] != 8 or hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('恐龙装动作素材与布局不一致，请重新构建')
    atlas = QPixmap(str(path))
    if atlas.isNull() or not atlas.hasAlphaChannel():
        raise ValueError('动作素材必须是有效的透明 PNG')
    frames = {(cell['row'],cell['col']):(atlas.copy(QRect(*cell['source'])),cell['target']) for cell in manifest['frames']}
    required = {(r,c) for r in range(10) for c in range(6)}
    if frames.keys() != required:
        raise ValueError('恐龙装动作素材必须包含完整的 60 个姿态')
    return frames


class Puppet:
    def __init__(self,directory=None):
        self.frames = _load(str(directory or Path(__file__).resolve().parents[1]/'assets'))
        self._last_key = self._last_frame = None

    def render(self,pose):
        state,elapsed = pose.get('_state','idle'),pose.get('_elapsed',0.)
        row,col = select_frame(state,elapsed,pose.get('_gaze',(0.,0.)))
        # All supplied movement poses face left: mirror only for rightward motion.
        flip = state in ('running-right','walking-right')
        key = row,col,flip
        if key != self._last_key:
            sprite,target = self.frames[row,col]
            frame = QPixmap(768,832)
            frame.fill(Qt.GlobalColor.transparent)
            p = QPainter(frame)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(QRectF(*target),sprite,QRectF(sprite.rect()))
            p.end()
            if flip:
                frame = frame.transformed(QTransform().scale(-1, 1))
            self._last_key,self._last_frame = key,frame
        # Rigid subpixel sway preserves plush texture, eyes, teeth and hands.
        moving = state.startswith(('running-','walking-'))
        dx = 0. if moving else 1.5*math.sin(elapsed*2)
        dy = -8*math.sin(math.pi*(elapsed % playback_duration(state))/playback_duration(state))**2 if state == 'jumping' else 0.
        output = QPixmap(768,832)
        output.fill(Qt.GlobalColor.transparent)
        p = QPainter(output)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(QRectF(dx,dy,768,832),self._last_frame,QRectF(0,0,768,832))
        p.end()
        return output
