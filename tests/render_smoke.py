"""Render actual Qt widgets and exercise dragging/double-click without a live DB."""
import sys
from pathlib import Path
from unittest.mock import patch
from test_pet import GuiTests, gui
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase

out = Path(__file__).resolve().parents[1] / 'qa'
GuiTests.setUpClass()
# The offscreen plugin does not enumerate Windows fonts automatically.
for font in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/segoeui.ttf'):
    QFontDatabase.addApplicationFont(font)
test = GuiTests()
test.setUp()
try:
    pet = test.pet
    pet.move(320,400)
    pet._auto_active = True
    pet._set_state('running')
    pet._show_auto('执行命令', '验证图片完整性、任务状态与多会话气泡', state='working', steps=12)
    for _ in range(30): pet._tw_tick()
    test.app.processEvents()
    pet.grab().save(str(out/'qt-pet.png'))
    pet._bubble.grab().save(str(out/'qt-bubble.png'))
    pet._sync_bubbles([{'id':'a','name':'图片检查','status':'completed','current':88,'total':88,'message':'图片取帧已校正'},
                       {'id':'b','name':'气泡测试','status':'running','current':2,'total':3,'message':'展开详情、拖动桌宠、检查屏幕边界'}])
    b=pet._task_bubbles['b']
    QTest.mouseClick(b,gui.Qt.MouseButton.LeftButton)
    test.app.processEvents()
    assert b._expanded
    b.grab().save(str(out/'qt-task-expanded.png'))
    pet._set_state('idle')
    QTest.mouseDClick(pet,gui.Qt.MouseButton.LeftButton)
    assert pet._state == 'waving' and pet._one_shot
    pet._sync_bubbles([])
    # Actual frame cache/painter used by the app, on two backgrounds.
    canvas=gui.QPixmap(9*192,len(gui.ANIMATIONS)*232)
    canvas.fill(gui.QColor('#f2f4f7'))
    p=gui.QPainter(canvas)
    p.setFont(gui.QFont('Microsoft YaHei UI',10))
    for r,(state,anim) in enumerate(gui.ANIMATIONS.items()):
        for idx,col in enumerate(anim.get('columns',range(len(anim['durations'])))):
            x,y=idx*192,r*232
            p.fillRect(x,y,192,232,gui.QColor('#f2f4f7' if idx%2==0 else '#253247'))
            p.setPen(gui.QColor('#17243b' if idx%2==0 else 'white'))
            p.drawText(x+5,y+19,f'{state} {col}')
            frame=(pet._action_frames[anim['row'],col] if anim.get('source') == 'v2'
                   else gui.crop_frame(pet.atlas,anim['row'],col))
            p.drawPixmap(gui.QRect(x,y+24,192,208),frame)
    p.end()
    canvas.save(str(out/'qt-played-frames.png'))
    print('Qt rendered: pet, structured bubble, expanded task, all played frames. Click expansion and double-click waving passed.')
finally:
    test.tearDown()
