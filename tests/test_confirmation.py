import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pet_confirmation import ConfirmationStore, fingerprint
import test_pet as base
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest


def request(**changes):
    data = {"title": "配色确认", "question": "气泡使用哪种颜色？",
            "options": [{"id": "yellow", "label": "小新黄", "description": "和角色衣服协调"},
                        {"id": "blue", "label": "清爽蓝", "description": "更安静的视觉效果"}],
            "recommended": "yellow", "allow_custom": True}
    data.update(changes)
    return data


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = ConfirmationStore(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_answer_until_explicit_choice(self):
        data = self.store.create(request())
        self.assertEqual(self.store.read(data["id"])["status"], "pending")
        self.assertNotIn("answer", self.store.read(data["id"]))

    def test_wrong_recommendation_and_duplicate_are_rejected(self):
        data = self.store.create(request())
        with self.assertRaises(ValueError):
            self.store.answer(data["id"], data["fingerprint"], "blue", "recommended")
        self.store.answer(data["id"], data["fingerprint"], "yellow", "recommended")
        with self.assertRaises(ValueError):
            self.store.answer(data["id"], data["fingerprint"], "blue", "manual")
        self.assertEqual(self.store.read(data["id"])["answer"]["option_id"], "yellow")

    def test_expiry_and_cancel_never_select_default(self):
        data = self.store.create(request(), 30)
        with patch("pet_confirmation.time.time", return_value=data["expires_at"] + 1):
            self.assertEqual(self.store.pending(), [])
            with self.assertRaises(ValueError):
                self.store.answer(data["id"], data["fingerprint"], "yellow", "recommended")
        self.store.cancel(data["id"])
        with self.assertRaises(ValueError):
            self.store.answer(data["id"], data["fingerprint"], "yellow", "recommended")
        self.assertNotIn("answer", self.store.read(data["id"]))

    def test_changed_request_requires_new_review(self):
        data = self.store.create(request())
        changed = dict(data)
        changed["request"] = dict(data["request"], question="不同的问题")
        changed["fingerprint"] = fingerprint(changed["request"])
        self.store._write(data["id"], changed)
        with self.assertRaises(ValueError):
            self.store.answer(data["id"], data["fingerprint"], "yellow", "recommended")

    def test_invalid_options_ids_and_files(self):
        for payload in [request(recommended="missing"), request(options=[]),
                        request(options=[{"id":"a","label":"A"},{"id":"a","label":"B"}])]:
            with self.assertRaises(ValueError):
                self.store.create(payload)
        with self.assertRaises(ValueError):
            self.store.read("../state")
        self.store.root.mkdir(exist_ok=True)
        (self.store.root / ("a" * 32 + ".json")).write_text('{"bad":true}')
        self.assertEqual(self.store.pending(), [])

    def test_cli_wait_receives_answer_and_timeout_remains_pending(self):
        cli = Path(__file__).resolve().parents[1] / "scripts" / "pet-confirm.py"
        payload = self.root / "question.json"
        payload.write_text(json.dumps(request(), ensure_ascii=False), encoding="utf-8-sig")
        env = dict(os.environ, PET_RUNTIME_DIR=str(self.root), PYTHONIOENCODING="utf-8")
        run = lambda *args: subprocess.run([sys.executable, "-X", "utf8", "-B", str(cli), *args],
                                           env=env, capture_output=True, encoding="utf-8", timeout=5)
        create = run("create", "--file", str(payload))
        self.assertEqual(create.returncode, 0, create.stderr)
        rid = json.loads(create.stdout)["id"]
        result = run("wait", "--id", rid, "--seconds", "0")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "pending")
        process = subprocess.Popen([sys.executable,"-X","utf8","-B",str(cli),"wait","--id",rid,"--seconds","3"],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            data = self.store.read(rid)
            self.store.answer(rid, data["fingerprint"], "blue", "manual")
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout)["answer"]["option_id"], "blue")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


class ConfirmationGuiTests(unittest.TestCase):
    setUpClass = classmethod(base.GuiTests.setUpClass.__func__)
    setUp = base.GuiTests.setUp
    tearDown = base.GuiTests.tearDown

    def show_request(self, **changes):
        controller = self.pet._confirmations
        data = controller.store.create(request(**changes))
        controller.poll()
        self.app.processEvents()
        return controller, data

    def test_recommendation_click_and_double_click_does_not_answer_next(self):
        c, first = self.show_request()
        second = c.store.create(request(title="第二题"))
        c.poll()
        QTest.mouseClick(c.recommended, Qt.MouseButton.LeftButton)
        QTest.mouseClick(c.recommended, Qt.MouseButton.LeftButton)
        self.assertEqual(c.store.read(first["id"])["answer"]["source"], "recommended")
        self.assertEqual(c.store.read(second["id"])["status"], "pending")
        self.assertFalse(c.recommended.isEnabled())

    def test_review_close_does_not_submit_and_other_option_works(self):
        c, data = self.show_request()
        QTest.mouseClick(c.review, Qt.MouseButton.LeftButton)
        self.assertEqual(c.dialog.group.checkedId(), -1)
        self.assertFalse(c.dialog.submit.isEnabled())
        c.dialog.close()
        self.assertEqual(c.store.read(data["id"])["status"], "pending")
        QTest.mouseClick(c.review, Qt.MouseButton.LeftButton)
        QTest.mouseClick(c.dialog.choices[1][0], Qt.MouseButton.LeftButton)
        QTest.mouseClick(c.dialog.submit, Qt.MouseButton.LeftButton)
        answer = c.store.read(data["id"])["answer"]
        self.assertEqual((answer["option_id"], answer["source"]), ("blue", "manual"))
        self.assertFalse(c.active)

    def test_missing_recommendation_custom_answer(self):
        c, data = self.show_request(recommended=None)
        self.assertFalse(c.recommended.isEnabled())
        QTest.mouseClick(c.review, Qt.MouseButton.LeftButton)
        QTest.mouseClick(c.dialog.choices[-1][0], Qt.MouseButton.LeftButton)
        self.assertFalse(c.dialog.submit.isEnabled())
        c.dialog.custom.setPlainText("请保持现在的颜色")
        QTest.mouseClick(c.dialog.submit, Qt.MouseButton.LeftButton)
        self.assertEqual(c.store.read(data["id"])["answer"]["text"], "请保持现在的颜色")

    def test_expired_open_dialog_is_closed_and_cannot_submit(self):
        c, data = self.show_request()
        QTest.mouseClick(c.review, Qt.MouseButton.LeftButton)
        with patch("pet_confirmation.time.time", return_value=data["expires_at"] + 1):
            self.assertIsNotNone(c.answer(data, "yellow", "recommended"))
            c.poll()
            self.assertFalse(c.active)
            self.assertIsNone(c.dialog)

    def test_multiple_questions_route_by_id(self):
        c, first = self.show_request()
        second = c.store.create(request(title="第二题"))
        c.poll()
        QTest.mouseClick(c.next_button, Qt.MouseButton.LeftButton)
        self.assertEqual(c.current["id"], second["id"])
        QTest.mouseClick(c.recommended, Qt.MouseButton.LeftButton)
        self.assertEqual(c.store.read(second["id"])["status"], "answered")
        self.assertEqual(c.store.read(first["id"])["status"], "pending")

    def test_confirmation_stays_visible_during_status_updates_and_hides_with_pet(self):
        c, data = self.show_request(question="很长的问题" * 200)
        self.pet._show_auto("执行命令", "后台进度", state="working", steps=3)
        self.pet._sync_bubbles([{"id":"task", "name":"另一个任务", "status":"running"}])
        self.assertTrue(c.bubble.isVisible())
        self.assertFalse(self.pet._bubble.isVisible())
        self.assertTrue(all(not b.isVisible() for b in self.pet._task_bubbles.values()))
        self.assertTrue(c.bubble.rect().contains(c.recommended.mapTo(c.bubble, c.recommended.rect().bottomRight())))
        self.pet._set_visible(False)
        self.assertFalse(c.bubble.isVisible())
        self.pet._set_visible(True)
        self.assertTrue(c.bubble.isVisible())

    def test_click_returns_answer_to_waiting_agent_process(self):
        c, data = self.show_request()
        cli = Path(__file__).resolve().parents[1] / "scripts" / "pet-confirm.py"
        env = dict(os.environ, PET_RUNTIME_DIR=self.tmp.name, PYTHONIOENCODING="utf-8")
        process = subprocess.Popen([sys.executable,"-X","utf8","-B",str(cli),"wait","--id",data["id"],"--seconds","3"],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            QTest.mouseClick(c.recommended, Qt.MouseButton.LeftButton)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["id"], data["id"])
            self.assertEqual(result["answer"]["option_id"], "yellow")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_manual_progress_animation_is_restored_after_answer(self):
        self.pet._progress_active = True
        self.pet._auto_active = True
        self.pet._set_state("running")
        c, data = self.show_request()
        self.assertEqual(self.pet._state, "waiting")
        QTest.mouseClick(c.recommended, Qt.MouseButton.LeftButton)
        self.assertEqual(self.pet._state, "running")

    def test_review_dialog_keeps_long_chinese_choices_legible(self):
        c, _data = self.show_request(
            title="需要你的选择：确认下一步处理方式",
            question="当前任务已完成初步检查。请查看每个方案的说明，再决定下一步如何处理。",
            options=[
                {"id":"continue", "label":"继续执行当前方案", "description":"按现有步骤继续处理，并由桌宠同步显示后续进度。"},
                {"id":"review", "label":"我先查看详细结果", "description":"保留当前结果，确认细节和风险后再继续。"},
                {"id":"stop", "label":"暂时停止本次任务", "description":"停止这一次任务，不影响已经完成的内容。"},
            ],
            recommended="continue",
        )
        c._review()
        dialog = c.dialog
        self.assertGreaterEqual(dialog.font().pointSizeF(), 9.0)
        self.assertGreaterEqual(dialog.width(), 460)
        self.assertTrue(dialog.rect().contains(dialog.submit.geometry().bottomRight()))
        self.assertTrue(dialog.rect().contains(dialog.choices[-1][0].geometry().bottomRight()))


if __name__ == "__main__":
    unittest.main()

