"""Actual Qt style gallery; all examples remain isolated from live task data."""
from pathlib import Path
from test_pet import GuiTests, gui
from PySide6.QtGui import QFontDatabase

GuiTests.setUpClass()
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
test=GuiTests()
test.setUp()
try:
    canvas=gui.QPixmap(870,510)
    canvas.fill(gui.QColor('#e7e8e2'))
    painter=gui.QPainter(canvas)
    examples=[('working','执行中','正在整理资料，马上就好。'),
              ('thinking','思考中','让我想想，还有更好的办法吗？'),
              ('waiting','等你确认','方案准备好了，等你拿主意。'),
              ('completed','完成啦','这件事搞定啦！'),
              ('failed','遇到问题','这里需要再检查一下。')]
    for i,(state,title,message) in enumerate(examples):
        b=gui.BubbleWindow(test.pet)
        b.set_structured(title,gui.STATE_UI_COLORS[state],'',message,message)
        b.show()
        test.app.processEvents()
        x,y=20+(i%3)*285,25+(i//3)*245
        painter.drawPixmap(x,y,b.grab())
        test.pet._set_state({'working':'running','completed':'waving'}.get(state,state))
        frame=test.pet._current_frame
        bounds=gui.QRegion(frame.mask()).boundingRect()
        top=y+b.height()-b.M_B+3-round(bounds.top()*105/frame.width())
        painter.drawPixmap(gui.QRect(x+(b.width()-105)//2,top,105,114),frame)
        b.close()
    painter.end()
    canvas.save(str(Path(__file__).resolve().parents[1]/'qa/bubble-styles.png'))
finally:
    test.tearDown()
