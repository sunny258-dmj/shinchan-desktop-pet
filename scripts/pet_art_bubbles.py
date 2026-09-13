"""Paint only the supplied bubble artwork, with no generated decorations."""
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap, QPainter
from pet_bubble_style import palette

# Fractional safe text rectangles measured inside each supplied frame.
INSETS = {
    'working': (.16, .32, .13, .15), 'blue': (.16, .25, .15, .18),
    'pink': (.21, .30, .20, .24), 'alert': (.21, .30, .20, .24),
    'waiting': (.16, .28, .16, .16), 'success': (.17, .25, .17, .20),
    'thinking': (.20, .20, .23, .29), 'idea': (.24, .40, .18, .17),
}

@lru_cache(maxsize=8)
def artwork(theme):
    theme = {'alert': 'pink'}.get(theme, theme)
    image = QPixmap(str(Path(__file__).resolve().parents[1] / 'assets' / f'dinosaur-bubble-{theme}.png'))
    if image.isNull():
        raise ValueError(f'Missing supplied bubble: {theme}')
    return image

def content_theme(text, accent):
    if any(word in text for word in ('失败', '错误', '异常', '警告')):
        return 'alert' if len(text) <= 12 else 'pink'
    if any(word in text for word in ('等待', '确认', '请选择')):
        return 'waiting'
    if any(word in text for word in ('完成', '成功', '通过')):
        return 'success'
    if any(word in text for word in ('灵感', '想到了')):
        return 'idea'
    if any(word in text for word in ('检查', '核对', '阅读')):
        return 'blue'
    if any(word in text for word in ('？', '?', '思考', '为什么')):
        return 'thinking'
    return palette(accent)[0]


def draw_bubble(painter, rect, accent, tail_up=False, theme=None):
    image = artwork(theme or palette(accent)[0])
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if tail_up:
        painter.translate(0, rect.height())
        painter.scale(1, -1)
    painter.drawPixmap(QRectF(rect), image, QRectF(image.rect()))
    painter.restore()
