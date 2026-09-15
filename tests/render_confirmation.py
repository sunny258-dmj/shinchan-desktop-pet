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
    c, data = test.show_request(
        title="需要你的选择：确认下一步处理方式",
        question="当前任务已完成初步检查。请查看每个方案的说明，再决定下一步如何处理。",
        options=[
            {"id":"continue", "label":"继续执行当前方案", "description":"按现有步骤继续处理，并由桌宠同步显示后续进度。"},
            {"id":"review", "label":"我先查看详细结果", "description":"保留当前结果，确认细节和风险后再继续。"},
            {"id":"stop", "label":"暂时停止本次任务", "description":"停止这一次任务，不影响已经完成的内容。"},
        ],
        recommended="continue",
        allow_custom=True,
    )
    test.app.processEvents()
    assert c.bubble.grab().save(str(out / "confirmation-bubble.png"))
    c._review()
    test.app.processEvents()
    assert c.dialog.grab().save(str(out / "confirmation-review.png"))
    print("Rendered confirmation bubble and full option review with actual Qt widgets.")
finally:
    test.tearDown()
