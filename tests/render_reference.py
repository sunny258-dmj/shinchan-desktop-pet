"""Export reference V5 action previews using the exact live Qt renderer."""
import io
import math
from pathlib import Path
from test_pet import GuiTests, gui
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QFontDatabase
from PIL import Image
from pet_reference_renderer import playback_duration

OUT = Path(__file__).resolve().parents[1] / 'qa/dinosaur-v8'
OUT.mkdir(parents=True, exist_ok=True)
LABELS = {'idle': '待机', 'look': '鼠标互动', 'thinking': '思考', 'running': '执行任务与长时间工作',
          'walking-left': '向左走路', 'walking-right': '向右走路', 'running-right': '向右跑步', 'running-left': '向左移动', 'review': '检查结果',
          'waiting': '等待确认', 'failed': '任务失败', 'waving': '挥手互动',
          'jumping': '开心跳跃', 'hero-celebrate': '英雄庆祝'}

GuiTests.setUpClass()
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
test = GuiTests()
test.setUp()
try:
    pet = test.pet
    contact = gui.QPixmap(6 * 192, 10 * 228)
    contact.fill(gui.QColor('#eef8ff'))
    painter = gui.QPainter(contact)
    painter.setFont(gui.QFont('Microsoft YaHei UI', 9))
    for (row, col), (sprite, target) in pet._puppet.frames.items():
        x, y = col * 192, row * 228
        painter.fillRect(x, y, 192, 228, gui.QColor('#223044' if col % 2 else '#eef8ff'))
        painter.setPen(gui.QColor('#c6dae8' if col % 2 else '#34546b'))
        painter.drawText(x + 8, y + 17, f'{row + 1:02d} / {col + 1}')
        tx, ty, tw, th = target
        painter.drawPixmap(gui.QRectF(x + tx / 4, y + 20 + ty / 4, tw / 4, th / 4), sprite, gui.QRectF(sprite.rect()))
    painter.end()
    contact.save(str(OUT / 'all-60-poses.png'))
    for state in LABELS:
        frames = []
        length = 4 if state == 'look' else playback_duration(state)
        for index in range(round(length * 30)):
            t = index / 30
            gaze = (math.sin(t * 2), math.cos(t * 2)) if state == 'look' else (0, 0)
            frame = pet._puppet.render(gui.sample_scene(state, t, gaze)).scaled(192, 208,
                gui.Qt.AspectRatioMode.KeepAspectRatio, gui.Qt.TransformationMode.SmoothTransformation)
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            frame.save(buffer, 'PNG')
            frames.append(Image.open(io.BytesIO(bytes(buffer.data()))).convert('RGBA'))
        frames[0].save(OUT / f'{state}.webp', save_all=True, append_images=frames[1:], duration=33, loop=0, lossless=True)
    cards = ''.join(f'<section><h2>{label}</h2><img src="{state}.webp"><small>{(4 if state == "look" else playback_duration(state)):g} 秒</small></section>'
                    for state, label in LABELS.items())
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>蜡笔小新 · 参考图动作版</title><style>
body{margin:32px;background:#eaf6ff;color:#23415d;font:16px "Microsoft YaHei",sans-serif}h1{font-size:28px}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:18px}section{background:white;border:2px solid #cce7ff;border-radius:22px;text-align:center;padding:16px}
h2{font-size:17px}img{display:block;width:192px;height:208px;margin:auto}small{color:#7591a6}button{cursor:pointer;border:1px solid #aacee6;background:white;border-radius:12px;padding:12px 18px;margin-bottom:24px}
.dark section{background:#223044;color:#f3f9ff}.dark small{color:#b0c4d4}</style>
<h1>蜡笔小新 · 参考图动作版</h1><p>恐龙装小新 · 60 个原图姿态 · 8 个原图气泡。点击切换背景，查看透明边缘；每个动作会完整循环播放。</p>
<button onclick="document.body.classList.toggle('dark')">切换深色 / 浅色背景</button><main>''' + cards + '</main></html>'
    (OUT / 'index.html').write_text(html, encoding='utf-8')
    from pet_art_bubbles import artwork
    gallery = gui.QPixmap(1200, 620)
    gallery.fill(gui.QColor('#edf4fa'))
    gp = gui.QPainter(gallery)
    for i, theme in enumerate(('working','blue','pink','waiting','success','idea','heart','thinking')):
        art = artwork(theme).scaled(276,250,gui.Qt.AspectRatioMode.KeepAspectRatio,gui.Qt.TransformationMode.SmoothTransformation)
        gp.drawPixmap((i%4)*300+12, (i//4)*310+24, art)
    gp.end()
    gallery.save(str(OUT/'all-8-bubbles.png'))
    with (OUT/'index.html').open('a',encoding='utf-8') as page:
        page.write('<h2>八款气泡原图</h2><img style="width:100%;height:auto;max-width:1200px" src="all-8-bubbles.png">')
    pet._auto_active = True
    pet.move(320, 400)
    pet._set_state('running')
    pet._show_bubble('我在认真工作，马上就好～')
    pet._render_scene(5)
    pet._bubble.set_message('我在认真工作，马上就好～')
    pet._bubble.position_near_pet()
    test.app.processEvents()
    bounds = pet.geometry().united(pet._bubble.geometry()).adjusted(-24, -24, 24, 24)
    canvas = gui.QPixmap(bounds.size())
    canvas.fill(gui.QColor('#dff2ff'))
    p = gui.QPainter(canvas)
    p.drawPixmap(pet._bubble.pos() - bounds.topLeft(), pet._bubble.grab())
    p.drawPixmap(pet.pos() - bounds.topLeft(), pet.grab())
    p.end()
    canvas.save(str(OUT / 'pet-and-bubble.png'))
    canvas = gui.QPixmap(1000, 700)
    canvas.fill(gui.QColor('#eef7ff'))
    p = gui.QPainter(canvas)
    for i, message in enumerate(('好了', '需要你确认一下？', '任务已完成，检查通过。',
                                  '出现异常，请检查网络连接后重试。' * 5)):
        pet._show_bubble(message)
        test.app.processEvents()
        p.drawPixmap((i % 2) * 500, (i // 2) * 330, pet._bubble.grab())
    p.end()
    canvas.save(str(OUT / 'adaptive-bubbles.png'))
    print('Exported all 60 poses and 14 full animation previews:', OUT)
finally:
    test.tearDown()
