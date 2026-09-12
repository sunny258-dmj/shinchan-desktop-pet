"""Export full V4 scene animations and a contact sheet for visual QA."""
import io
import math
from pathlib import Path
from test_pet import GuiTests, gui
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QBuffer, QIODevice
from PIL import Image

OUT = Path(__file__).resolve().parents[1] / 'qa/scenes-v4'
OUT.mkdir(parents=True, exist_ok=True)
LABELS = {
    'idle': '待机：张望、伸展、整理披风、得意小动作',
    'running': '执行任务：准备、电脑操作、查看资料、记录、继续工作',
    'thinking': '思考：托腮、换方向、抬头、灵光一现、确认',
    'review': '检查：阅读、翻看、记录、复查、确认',
    'waiting': '等待：注视、提示、安静等待、轻微无聊、再次提醒',
    'failed': '失败：愣住、疑惑、检查、摊手、恢复精神',
    'waving': '挥手：察觉、举手、大幅挥、快速挥、收势',
    'jumping': '开心跳跃：蓄力、腾空、落地缓冲、回弹',
    'hero-celebrate': '英雄庆祝：惊喜、蓄力、大跳、英雄落地、竖拇指',
    'look': '鼠标互动：眼睛、头部、身体三级跟随',
    'running-left': '向左移动：启动、加速、完整步态、减速、刹车',
    'running-right': '向右移动：启动、加速、完整步态、减速、刹车',
}

GuiTests.setUpClass()
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
test = GuiTests()
test.setUp()
try:
    pet = test.pet
    contact = gui.QPixmap(4 * 260, len(LABELS) * 270)
    contact.fill(gui.QColor('#eef8ff'))
    painter = gui.QPainter(contact)
    painter.setFont(gui.QFont('Microsoft YaHei UI', 10))

    for row, (state, label) in enumerate(LABELS.items()):
        frames = []
        length = gui.scene_duration(state)
        fps = 15
        for index in range(max(1, round(length * fps))):
            t = index / fps
            gaze = (math.sin(t * 1.5) * .75, math.sin(t * .9) * .2) if state == 'look' else (0, 0)
            frame = pet._puppet.render(gui.sample_scene(state, t, gaze))
            small = frame.scaled(192, 208, gui.Qt.AspectRatioMode.KeepAspectRatio,
                                 gui.Qt.TransformationMode.SmoothTransformation)
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            small.save(buffer, 'PNG')
            frames.append(Image.open(io.BytesIO(bytes(buffer.data()))).convert('RGBA'))
        frames[0].save(OUT / f'{state}.webp', save_all=True, append_images=frames[1:],
                       duration=round(1000 / fps), loop=0, lossless=True)

        moments = [length * f for f in (.12, .34, .58, .82)]
        for col, t in enumerate(moments):
            gaze = (.65, -.15) if state == 'look' else (0, 0)
            frame = pet._puppet.render(gui.sample_scene(state, t, gaze))
            x, y = col * 260, row * 270
            painter.setPen(gui.QColor('#27445f'))
            painter.drawText(x + 8, y + 20, f'{label.split("：")[0]}  {t:.1f}s')
            painter.drawPixmap(gui.QRect(x + 20, y + 28, 220, 238), frame)

    painter.end()
    contact.save(str(OUT / 'contact.png'))
    cards = ''.join(
        f'<section><h2>{label}</h2><img src="{state}.webp"><small>{gui.scene_duration(state):g} 秒完整动作周期</small></section>'
        for state, label in LABELS.items())
    html = '''<!doctype html><meta charset="utf-8"><title>小新 V4 · 全场景连续动画</title>
<style>body{margin:32px;background:#eef8ff;color:#27445f;font:16px "Microsoft YaHei"}h1{font-size:26px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}section{border:1px solid #d7eaf7;border-radius:22px;background:#fff;padding:18px;text-align:center;box-shadow:0 10px 30px #35698d18}h2{font-size:15px;min-height:42px}img{display:block;width:192px;height:208px;margin:auto}small{color:#6b8093}button{padding:10px 20px;border:1px solid #b6d7ee;border-radius:12px;background:white;margin-bottom:20px}</style>
<h1>蜡笔小新桌宠 V4 · 全场景连续动画</h1><p>全部来自实时 2× 矢量绘制器。预览以 15 FPS 导出；桌面实时按约 30 FPS 连续采样。</p><button onclick="document.body.classList.toggle('dark');document.querySelectorAll('section').forEach(e=>e.style.background=document.body.classList.contains('dark')?'#26364a':'#fff')">切换卡片背景</button><main>''' + cards + '</main>'
    (OUT / 'index.html').write_text(html, encoding='utf-8')
    print('Exported V4 full-scene animations and contact sheet to', OUT)
finally:
    test.tearDown()
