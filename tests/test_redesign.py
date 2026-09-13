import unittest
import test_pet as fixture
from pet_scene_motion import SCENES, duration, sample

gui = fixture.gui


class RedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.GuiTests.setUpClass()
        cls.app = fixture.GuiTests.app

    setUp = fixture.GuiTests.setUp
    tearDown = fixture.GuiTests.tearDown

    def test_every_scene_is_a_full_motion_clip(self):
        minimum = {
            'idle': 20, 'running': 15, 'thinking': 12, 'waiting': 14,
            'review': 13, 'failed': 12, 'waving': 4, 'jumping': 4,
            'hero-celebrate': 6, 'running-left': 6, 'running-right': 6,
        }
        for state, seconds in minimum.items():
            self.assertIn(state, SCENES)
            self.assertGreaterEqual(duration(state), seconds)
            self.assertGreaterEqual(len(SCENES[state]), 6)

    def test_scene_samples_are_continuously_distinct(self):
        for state in ('idle', 'running', 'thinking', 'waiting', 'review',
                      'failed', 'waving', 'jumping', 'hero-celebrate'):
            poses = []
            steps = 24
            for i in range(steps):
                pose = sample(state, duration(state) * i / steps)
                poses.append(tuple(round(pose[k], 2) for k in
                                   ('y', 'lean', 'head', 'lx', 'ly', 'rx', 'ry',
                                    'flx', 'fly', 'frx', 'fry', 'cape',
                                    'happy', 'puzzled', 'laptop', 'board')))
            self.assertGreaterEqual(len(set(poses)), 18, state)

    def test_reference_character_has_clean_transparent_edges(self):
        from pet_reference_renderer import playback_duration
        for state in ('idle', 'running', 'thinking', 'review', 'waiting',
                      'failed', 'hero-celebrate'):
            frames = []
            for fraction in (0.05, .24, .43, .62, .81):
                frame = self.pet._puppet.render(sample(state, playback_duration(state) * fraction))
                self.assertEqual((frame.width(), frame.height()), (768, 832))
                image = frame.toImage()
                for x, y in ((0, 0), (767, 0), (0, 831), (767, 831)):
                    self.assertEqual(image.pixelColor(x, y).alpha(), 0)
                frames.append(bytes(image.constBits()))
            self.assertGreaterEqual(len(set(frames)), 4, state)

    def test_character_uses_reference_asset(self):
        self.assertEqual(type(self.pet._puppet).__module__, 'pet_reference_renderer')
        self.assertEqual(len(self.pet._puppet.frames), 60)
        frame = self.pet._puppet.render(sample('idle', 3.0))
        self.assertFalse(frame.isNull())
        self.assertFalse(gui.QRegion(frame.mask()).isEmpty())

    def test_reference_assets_are_complete_and_fit_canvas(self):
        import hashlib
        hashes = set()
        for (row, col), (frame, target) in self.pet._puppet.frames.items():
            image = frame.toImage()
            self.assertTrue(image.hasAlphaChannel())
            self.assertGreater(frame.width(), 40, (row, col))
            self.assertGreater(frame.height(), 40, (row, col))
            x, y, w, h = target
            self.assertGreater(x, 0, (row, col))
            self.assertGreater(y, 24, (row, col))
            self.assertLess(x + w, 768, (row, col))
            self.assertLess(y + h, 830, (row, col))
            hashes.add(hashlib.sha256(bytes(image.constBits())).digest())
        self.assertEqual(len(hashes), 60)

    def test_missing_reference_never_silently_replaces_character(self):
        from pet_reference_renderer import Puppet
        with self.assertRaises(FileNotFoundError):
            Puppet(self.tmp.name)

    def test_long_work_and_mouse_direction_reach_real_art(self):
        from pet_reference_renderer import select_frame
        used = {select_frame('running', i / 10) for i in range(450)}
        self.assertGreaterEqual(len(used), 9)
        self.assertIn((5, 2), used)  # book review is reachable during continuous work
        self.assertNotEqual(select_frame('look', 1, (-1, 0)), select_frame('look', 1, (1, 0)))
        self.assertNotEqual(select_frame('look', 1, (0, -1)), select_frame('look', 1, (0, 1)))

    def test_thinking_never_uses_work_or_typing_art(self):
        from pet_reference_renderer import playback_duration, select_frame
        used = {select_frame('thinking', playback_duration('thinking') * i / 80)
                for i in range(80)}
        self.assertTrue(used)
        # Rows 4–5 are the laptop/desk source sheet and belong only to work/review.
        self.assertTrue(all(row in (2, 3) for row, _column in used))

    def test_bubble_tip_tracks_visible_character(self):
        self.pet.move(300, 400)
        self.pet._auto_active = True
        self.pet._set_state('waiting')
        self.pet._show_bubble('等待你的选择')
        self.app.processEvents()
        self.pet._render_scene(3.0)
        b = self.pet._bubble
        tip = b.y() + b.height() - b.M_B - 2 * gui.UI_SCALE
        gap = self.pet.visual_geometry().top() - tip
        self.assertGreaterEqual(gap, -2)
        self.assertLessEqual(gap, 10)

    def test_rest_is_idle_only_and_movement_has_fast_steps(self):
        from pet_reference_renderer import select_frame
        self.assertEqual(select_frame('idle', 120), (1, 0))
        self.assertEqual(select_frame('idle', 150), (1, 5))
        self.assertNotEqual(select_frame('running', 150)[0], 1)
        self.assertNotEqual(select_frame('running-right', .01),
                            select_frame('running-right', .16))

    def test_action_timing_and_held_frame_cache(self):
        from pet_reference_renderer import playback_duration, select_frame
        self.assertGreater(playback_duration('running'), 8)
        self.assertLess(playback_duration('running-left'), 1.2)
        self.assertGreater(playback_duration('walking-left'), playback_duration('running-left'))
        self.assertEqual(select_frame('idle', 2.41), (0, 1))
        self.assertEqual(select_frame('idle', 2.55), (0, 2))

    def test_every_original_pose_is_reachable(self):
        from pet_reference_renderer import CLIPS
        keys = {key for clip in CLIPS.values() for key in clip}
        self.assertEqual(keys, set(self.pet._puppet.frames))

    def test_right_motion_is_exact_mirror_of_left(self):
        for movement in ('running', 'walking'):
            left = self.pet._puppet.render(sample(movement+'-left', .3)).toImage()
            right = self.pet._puppet.render(sample(movement+'-right', .3)).toImage()
            self.assertEqual(left.flipped(gui.Qt.Orientation.Horizontal), right)

    def test_cutouts_preserve_original_rgba_pixels(self):
        import json
        import numpy as np
        from PIL import Image
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / 'assets'
        manifest = json.loads((root/'dinosaur-actions.json').read_text(encoding='utf-8'))
        atlas = Image.open(root/manifest['image'])
        for frame in manifest['frames']:
            original = np.array(Image.open(root/'dinosaur-source'/f"{frame['sheet']}.png").crop(frame['source_box']))
            x,y,w,h = frame['source']
            cut = np.array(atlas.crop((x,y,x+w,y+h)))
            retained = cut[:,:,3] > 0
            self.assertTrue(np.array_equal(cut[retained], original[retained]))
            self.assertGreater(int(retained.sum()), 25000)

    def test_original_transparent_sources_are_packaged(self):
        import json
        import hashlib
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / 'assets'
        manifest = json.loads((root / 'dinosaur-actions.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['version'], 8)
        self.assertEqual(len(manifest['sources']), 6)
        for source in manifest['sources']:
            path = root / source['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source['sha256'])
            self.assertTrue(gui.QPixmap(str(path)).hasAlphaChannel())

    def test_bubble_fits_full_message_and_theme(self):
        self.pet._show_bubble('好了')
        b = self.pet._bubble
        short_width = b.width()
        b.set_message('发生异常，请检查网络连接后再重试。' * 8)
        self.assertGreater(b.width(), short_width)
        self.assertEqual(b.card.art_theme, 'pink')
        b.set_structured('执行中', '#1687ff', '2/5', '正', '正在处理任务，请稍候。' * 8)
        before = b.size()
        b.set_structured('执行中', '#1687ff', '2/5', '正在处理', '正在处理任务，请稍候。' * 8)
        self.assertEqual(b.size(), before)
        b.set_message('完成')
        self.assertEqual(b.card.art_theme, 'success')
        self.assertLess(b.width(), before.width())


if __name__ == '__main__':
    unittest.main()
