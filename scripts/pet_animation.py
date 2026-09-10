"""Choreographed action clips and keyed sprite import for the Qt host."""
import json
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QRegion


CLIPS = {
    'idle': (0, [1250, 260, 360, 220, 400, 240, 360, 900]),
    'running': (1, [200, 180, 180, 180, 240, 300, 380, 260, 220]),
    'thinking': (2, [320, 450, 450, 520, 360, 450, 300, 700]),
    'waiting': (3, [900, 260, 500, 240, 400, 450, 300, 1000]),
    'review': (4, [350, 300, 400, 280, 400, 300, 400, 450]),
    'jumping': (5, [200, 110, 110, 130, 170, 120, 160, 700]),
    'hero-celebrate': (5, [200, 110, 110, 130, 170, 120, 160, 1000]),
    'waving': (3, [200, 170, 200, 170, 230, 220, 180, 350]),
}


@lru_cache(maxsize=2)
def load_actions(directory):
    """Read a color-keyed sheet once. Never treat a painted checkerboard as alpha."""
    directory = Path(directory)
    spec = json.loads((directory / 'actions-v2-layout.json').read_text(encoding='utf-8'))
    image = QImage(str(directory / spec['image'])).convertToFormat(QImage.Format.Format_RGBA8888)
    if [image.width(), image.height()] != spec['size']:
        raise ValueError('动作图尺寸与布局不符')
    pixels = image.bits()
    # Magenta is reserved for the backdrop, never used by the character palette.
    for i in range(0, image.sizeInBytes(), 4):
        r, g, b = pixels[i], pixels[i + 1], pixels[i + 2]
        if r > 170 and b > 150 and g < min(r, b) * .72:
            pixels[i + 3] = 0
        elif min(r, b) > g + 20:
            # Remove key-color spill from antialiased dark outline pixels.
            spill = min(r, b) - g
            pixels[i], pixels[i + 2] = r - spill, b - spill
    atlas = QPixmap.fromImage(image)
    frames = {}
    for row, cells in enumerate(spec['rows']):
        for col, cell in enumerate(cells):
            part = atlas.copy(QRect(*cell))
            # Generated layouts can leave a few pixels of a neighbour in a cell.
            # Remove only tiny disconnected islands, keeping the actual pose.
            pic = part.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            buf = pic.bits()
            width, height = pic.width(), pic.height()
            pending = {i for i in range(width * height) if buf[4*i+3]}
            components = []
            while pending:
                seed = pending.pop()
                component, stack = [seed], [seed]
                while stack:
                    i = stack.pop()
                    x, y = i % width, i // width
                    neighbours = []
                    if x: neighbours.append(i-1)
                    if x+1 < width: neighbours.append(i+1)
                    if y: neighbours.append(i-width)
                    if y+1 < height: neighbours.append(i+width)
                    for j in neighbours:
                        if j in pending:
                            pending.remove(j)
                            component.append(j)
                            stack.append(j)
                components.append(component)
            largest = max(map(len, components), default=0)
            for component in components:
                if len(component) < largest * .015:
                    for i in component: buf[4*i+3] = 0
            part = QPixmap.fromImage(pic)
            bounds = QRegion(part.mask()).boundingRect()
            if bounds.isEmpty():
                raise ValueError(f'空动作帧 {row}/{col}')
            part = part.copy(bounds)
            frame = QPixmap(384, 416)
            frame.fill(Qt.GlobalColor.transparent)
            # One scale for a whole row preserves pose changes and limb lengths.
            scale = spec['scales'][row]
            w, h = round(part.width() * scale), round(part.height() * scale)
            lift = spec.get('lift', {}).get(str(row), [0] * len(cells))[col]
            p = QPainter(frame)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(QRect((384-w)//2, 396-h-lift, w, h), part)
            p.end()
            frames[row, col] = frame
    return frames
