"""Render actual V4 Qt widgets and exercise dragging/double-click without a live DB."""
from pathlib import Path
from test_pet import GuiTests, gui
from pet_scene_motion import duration
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase

out = Path(__file__).resolve().parents[1] / 'qa'
GuiTests.setUpClass()
for font in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/segoeui.ttf'):
    QFontDatabase.addApplicationFont(font)
test = GuiTests()
test.setUp()
try:
    pet = test.pet
    pet.move(320, 400)
    pet._auto_active = True
    pet._set_state('running')
    pet._show_auto('执行命令', '验证高清角色、任务状态与多会话气泡', state='working', steps=12)
    for _ in range(30):
        pet._tw_tick()
    pet._render_scene(3.2)
    test.app.processEvents()
    pet.grab().save(str(out / 'qt-pet-v4.png'))
    pet._bubble.grab().save(str(out / 'qt-bubble-v4.png'))

    pet._sync_bubbles([
        {'id': 'a', 'name': '透明边缘检查', 'status': 'completed', 'current': 24, 'total': 24,
         'message': '矢量角色透明边缘检查完成'},
        {'id': 'b', 'name': '动作与气泡测试', 'status': 'running', 'current': 2, 'total': 3,
         'message': '展开详情、拖动桌宠、检查屏幕边界'},
    ])
    bubble = pet._task_bubbles['b']
    QTest.mouseClick(bubble, gui.Qt.MouseButton.LeftButton)
    test.app.processEvents()
    assert bubble._expanded
    bubble.grab().save(str(out / 'qt-task-expanded-v4.png'))

    pet._set_state('idle')
    QTest.mouseDClick(pet, gui.Qt.MouseButton.LeftButton)
    assert pet._state == 'waving' and pet._one_shot
    pet._sync_bubbles([])

    states = list(gui.SCENES)
    cols = 4
    canvas = gui.QPixmap(cols * 230, len(states) * 250)
    canvas.fill(gui.QColor('#eef8ff'))
    painter = gui.QPainter(canvas)
    painter.setFont(gui.QFont('Microsoft YaHei UI', 9))
    for row, state in enumerate(states):
        for col, fraction in enumerate((.12, .36, .60, .84)):
            x, y = col * 230, row * 250
            painter.fillRect(x, y, 230, 250,
                             gui.QColor('#f8fcff' if col % 2 == 0 else '#e5f4ff'))
            painter.setPen(gui.QColor('#27445f'))
            t = duration(state) * fraction
            painter.drawText(x + 6, y + 18, f'{state} · {t:.1f}s')
            gaze = (.65, -.15) if state == 'look' else (0., 0.)
            frame = pet._puppet.render(gui.sample_scene(state, t, gaze))
            painter.drawPixmap(gui.QRect(x + 10, y + 24, 210, 220), frame)
    painter.end()
    canvas.save(str(out / 'qt-played-scenes-v4.png'))
    print('Qt V4 rendered: vector pet, structured bubble, expanded task and full scene contact sheet.')
finally:
    test.tearDown()
