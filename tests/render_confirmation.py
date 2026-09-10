"""Render the actual widgets with Chinese fonts, in an isolated runtime."""
from pathlib import Path
from PySide6.QtGui import QFontDatabase
from test_confirmation import ConfirmationGuiTests

out = Path(__file__).resolve().parents[1] / "qa"
ConfirmationGuiTests.setUpClass()
for font in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
    QFontDatabase.addApplicationFont(font)
test = ConfirmationGuiTests()
test.setUp()
try:
    c, data = test.show_request(title="气泡配色", question="气泡要用哪种颜色？推荐小新黄，和桌宠更搭。")
    test.app.processEvents()
    assert c.bubble.grab().save(str(out / "confirmation-bubble.png"))
    c._review()
    test.app.processEvents()
    assert c.dialog.grab().save(str(out / "confirmation-review.png"))
    print("Rendered confirmation bubble and full option review with actual Qt widgets.")
finally:
    test.tearDown()
