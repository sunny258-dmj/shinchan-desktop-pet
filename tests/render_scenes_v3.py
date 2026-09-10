"""Render the exact runtime puppet and time samples for visual animation QA."""
import io
from pathlib import Path
from test_pet import GuiTests, gui
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QBuffer, QIODevice
from PIL import Image

OUT=Path(__file__).resolve().parents[1]/'qa/scenes-v3'
OUT.mkdir(exist_ok=True)
LABELS={'idle':'待机：张望、整理披风、伸展','running':'工作：敲键、看屏幕、点头',
 'thinking':'思考：抱臂、托腮、挠头','review':'检查：扫视、勾选、翻看',
 'waiting':'等待确认：指向气泡、安静等待','hero-celebrate':'完成：蓄力、小跳、竖拇指',
 'jumping':'跳跃：蹲下、腾空、缓冲落地','failed':'问题：查看、疑惑、摊手',
 'waving':'双击：察觉、挥手两次、微笑','look':'跟随：转头观察',
 'running-left':'左跑：起步、摆臂、收步','running-right':'右跑：起步、摆臂、收步'}
GuiTests.setUpClass()
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
test=GuiTests();test.setUp()
try:
    pet=test.pet
    contact=gui.QPixmap(4*260,len(LABELS)*270)
    contact.fill(gui.QColor('#e8eae4'))
    painter=gui.QPainter(contact)
    painter.setFont(gui.QFont('Microsoft YaHei UI',11))
    for row,(state,label) in enumerate(LABELS.items()):
        frames=[]
        length=gui.scene_duration(state)
        for index in range(round(length*15)):
            t=index/15
            gaze=(__import__('math').sin(t*1.5),0) if state=='look' else (0,0)
            frame=pet._puppet.render(gui.sample_scene(state,t,gaze))
            small=frame.scaled(192,208)
            buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            small.save(buffer,'PNG')
            frames.append(Image.open(io.BytesIO(bytes(buffer.data()))).convert('RGBA'))
        frames[0].save(OUT/f'{state}.webp',save_all=True,append_images=frames[1:],
                       duration=67,loop=0,lossless=True)
        moments={'idle':[3,7.5,12.4,16],'running':[1,3.2,5.3,6.1],
                 'waiting':[.5,2,3.5,7],'thinking':[1.5,3,5,8.5]}.get(state,[length*f for f in (.15,.32,.55,.8)])
        for col,t in enumerate(moments):
            frame=pet._puppet.render(gui.sample_scene(state,t,(.6,0) if state=='look' else (0,0)))
            x,y=col*260,row*270
            painter.setPen(gui.QColor('#26364a'))
            painter.drawText(x+8,y+22,f'{label.split("：")[0]}  {t:.1f}s')
            painter.drawPixmap(gui.QRect(x+20,y+30,220,238),frame)
    painter.end()
    contact.save(str(OUT/'contact.png'))
    cards=''.join(f'<section><h2>{label}</h2><img src="{state}.webp"><small>{gui.scene_duration(state):g} 秒完整动作周期</small></section>' for state,label in LABELS.items())
    (OUT/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>小新 · 全场景连续动画</title>
<style>body{margin:32px;background:#e8eae4;color:#26364a;font:16px "Microsoft YaHei"}h1{font-size:26px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:18px}section{border-radius:20px;background:#fffaf0;padding:18px;text-align:center}h2{font-size:15px}img{display:block;width:192px;height:208px;margin:auto}small{color:#647077}button{padding:10px 20px;border:1px solid #68798a;border-radius:10px;margin-bottom:20px}</style>
<h1>小新 · 全场景连续动画</h1><p>全部来自桌宠实际绘制器。预览导出为 15 帧/秒；桌面播放按真实时间以约 30 帧/秒绘制。</p><button onclick="document.querySelectorAll('section').forEach(e=>e.style.background=e.style.background?'':'#283748')">切换深色底</button><main>'''+cards+'</main>',encoding='utf-8')
    print('Exported 12 full scene animations and contact sheet to',OUT)
finally:
    test.tearDown()
