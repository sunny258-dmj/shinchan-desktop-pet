"""Offline regressions. Only temporary SQLite/state files are written."""
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pet_events as events
import shinchan_pet_qt as gui
from pet_runtime import InstanceLock, is_running


class EventTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'teleagent.db'
        self.conn = sqlite3.connect(self.db)
        self.conn.executescript('''
            CREATE TABLE session(id TEXT PRIMARY KEY, title TEXT, time_updated INTEGER);
            CREATE TABLE message(id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT);
            CREATE TABLE part(id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT);
            INSERT INTO session VALUES('s', 'Test', 1);
            INSERT INTO message VALUES('m', 's', 1, 1, '{"role":"assistant"}');
        ''')
        self.conn.commit()
        self.w = events.TranscriptWatcher()
        self.w.db_path = self.db
        self.w.status_path = Path(self.tmp.name) / 'session-status.json'
        self.w.poll()

    def tearDown(self):
        if self.w._conn:
            self.w._conn.close()
        self.conn.close()
        self.tmp.cleanup()

    def insert(self, ident, data, ts=1000):
        self.conn.execute('INSERT INTO part VALUES(?, ?, ?, ?, ?, ?)',
                          (str(ident), 'm', 's', ts, ts, json.dumps(data)))
        self.conn.commit()

    def test_same_timestamp_across_polls(self):
        self.insert(1, {'type': 'reasoning'})
        self.assertEqual(len(self.w.poll()), 1)
        self.insert(2, {'type': 'reasoning'})
        self.assertEqual(len(self.w.poll()), 1)

    def test_more_than_one_page_same_timestamp(self):
        for i in range(601):
            self.insert(i, {'type': 'reasoning'})
        self.assertEqual(len(self.w.poll()) + len(self.w.poll()), 601)

    def test_tool_failure_update(self):
        self.insert(1, {'type': 'tool', 'tool': 'read', 'state': {'status': 'running'}})
        tracker = events.SessionTracker()
        for ev in self.w.poll():
            tracker.on_event({**ev, 'ts': int(time.time()*1000)})
        self.conn.execute('UPDATE part SET time_updated=?, data=? WHERE id=?',
                          (1001, json.dumps({'type':'tool','tool':'read','state':{'status':'error'}}), '1'))
        self.conn.commit()
        for ev in self.w.poll():
            tracker.on_event({**ev, 'ts': int(time.time()*1000)})
        self.assertEqual(tracker.resolve()[0], 'failed')
        self.assertEqual(tracker.sessions['s']['count'], 1)

    def test_assistant_stream_not_user_prompt(self):
        self.insert(1, {'type': 'text', 'text': 'private body'})
        ev = self.w.poll()[0]
        self.assertNotEqual(ev['event'], 'UserPromptSubmit')
        self.assertNotIn('private body', str(ev))

    def test_non_tool_clears_old_label(self):
        t = events.SessionTracker()
        t.on_event({'event':'PreToolUse','session_id':'s','tool_name':'read','snippet':'old.txt'})
        t.on_event({'event':'Stop','session_id':'s'})
        state, info = t.resolve()
        self.assertEqual(state, 'done')
        self.assertEqual(info['label'], '已完成')
        self.assertEqual(info['snippet'], '')


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = gui.QApplication.instance() or gui.QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(gui, name, value) for name, value in {
            'RUNTIME_ROOT':root, 'STATE_PATH':root/'state.json', 'LOG_PATH':root/'log.txt',
            'POSITION_PATH':root/'position.json',
            'PROGRESS_PATH':root/'progress.txt', 'TASKS_DIR':root/'tasks',
        }.items()]
        for p in self.patches:
            p.start()
        self.pet = gui.PetWindow()
        self.pet.show()

    def tearDown(self):
        for obj in self.pet.findChildren(gui.QTimer):
            obj.stop()
        for b in self.pet._task_bubbles.values():
            b.close()
        if self.pet._bubble:
            self.pet._bubble.close()
        self.pet.close()
        self.pet.deleteLater()
        self.app.processEvents()
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def command(self, **data):
        gui.STATE_PATH.write_text(json.dumps(data), encoding='utf-8')
        self.pet._last_state_mtime = -1
        self.pet._check_state()

    def test_same_state_message_updates(self):
        self.command(state='running', message='first')
        self.command(state='running', message='second')
        self.assertEqual(self.pet._bubble_text, 'second')

    def test_hide_also_hides_bubble(self):
        self.command(state='running', message='first')
        self.command(state='running', visible=False)
        self.assertFalse(self.pet._bubble.isVisible())
        self.pet._show_bubble('background event')
        self.assertFalse(self.pet._bubble.isVisible())

    def test_state_tasks_consumed(self):
        self.command(tasks=[{'id':'t','name':'test','status':'running','current':1,'total':3,'message':'go'}])
        self.assertIn('t', self.pet._task_bubbles)
        self.command(tasks=[])
        self.assertFalse(self.pet._task_bubbles)

    def test_progress_without_state_file(self):
        gui.PROGRESS_PATH.write_text('custom progress', encoding='utf-8')
        self.pet._check_state()
        self.assertEqual(self.pet._bubble_text, 'custom progress')
        self.pet._apply_auto_state(force=True)
        self.assertEqual(self.pet._bubble_text, 'custom progress')

    def test_progress_tasks_deleted(self):
        gui.PROGRESS_PATH.write_text(json.dumps({'tasks':[{'id':'t','name':'test','status':'running','current':1,'total':3,'message':'go'}]}), encoding='utf-8')
        self.pet._check_progress()
        gui.PROGRESS_PATH.unlink()
        self.pet._check_progress()
        self.assertFalse(self.pet._task_bubbles)

    def test_step_only_updates(self):
        self.pet._show_auto('读取文件', '', state='review', steps=1)
        self.pet._show_auto('读取文件', '', state='review', steps=2)
        self.assertEqual(self.pet._auto_steps, 2)

    def test_empty_snippet_clears_previous(self):
        self.pet._show_auto('读取文件', 'old.txt', state='review', steps=1)
        self.pet._show_auto('已完成', '', state='done')
        self.assertEqual(self.pet._auto_snippet, '')

    def test_invalid_atlas_rejected(self):
        bad = Path(self.tmp.name) / 'bad.png'
        bad.write_text('not an image')
        with patch.object(gui, 'ATLAS_PATH', bad), self.assertRaises(ValueError):
            gui.load_atlas()

    def test_bubbles_fit_screen_without_overlap(self):
        self.pet.move(20, 5)
        self.pet._sync_bubbles([{'id':str(i),'name':'test','status':'running','current':0,'total':0,'message':'detail'} for i in range(4)])
        rects = [b.geometry() for b in self.pet._task_bubbles.values() if b.isVisible()]
        screen = self.pet.screen().availableGeometry()
        self.assertTrue(all(screen.contains(r) for r in rects))
        self.assertTrue(all(not a.intersects(b) for i,a in enumerate(rects) for b in rects[i+1:]))

    def test_all_frames_have_clear_edges(self):
        for row in range(11):
            for col in range(8):
                frame = gui.crop_frame(self.pet.atlas,row,col).toImage()
                self.assertEqual((frame.width(),frame.height()),(384,416))
                self.assertTrue(all(frame.pixelColor(x,0).alpha()==0 and frame.pixelColor(x,415).alpha()==0 for x in range(384)))
                self.assertTrue(all(frame.pixelColor(0,y).alpha()==0 and frame.pixelColor(383,y).alpha()==0 for y in range(416)))

    def test_look_directions_use_face_not_back(self):
        self.assertEqual(gui.look_column(-100,0),5)
        self.assertEqual(gui.look_column(100,0),2)
        self.assertEqual(gui.look_column(0,100),0)
        self.assertEqual(gui.look_column(0,-100),0)

    def test_idle_poll_does_not_cancel_mouse_look(self):
        self.pet._set_state('look')
        self.pet._apply_auto_state()
        self.assertEqual(self.pet._state,'look')

    def test_single_instance_lock_released(self):
        root=Path(self.tmp.name)
        lock=InstanceLock(root)
        self.assertTrue(lock.acquire())
        try:
            self.assertTrue(is_running(root))
            other=InstanceLock(root)
            self.assertFalse(other.acquire())
        finally:
            lock.release()
        self.assertFalse(is_running(root))

    def test_done_does_not_restart_celebration(self):
        self.pet._tracker.on_event({'event':'Stop','session_id':'s'})
        self.pet._apply_auto_state(force=True)
        self.pet._done_timer.stop()
        self.pet._confirm_done()
        self.assertEqual(self.pet._state,'hero-celebrate')
        self.pet._set_state('idle')
        self.pet._apply_auto_state()
        self.assertFalse(self.pet._done_timer.isActive())

    def test_task_values_are_normalized(self):
        self.command(tasks=[{'name':'test','total':'3','current':'7','message':None}])
        bubble=self.pet._task_bubbles['test']
        self.assertEqual((bubble._current,bubble._total,bubble._message),(3,3,''))


if __name__ == '__main__':
    unittest.main(verbosity=2)
