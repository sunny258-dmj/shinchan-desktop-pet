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

    def test_vector_character_has_clean_transparent_edges(self):
        for state in ('idle', 'running', 'thinking', 'review', 'waiting',
                      'failed', 'hero-celebrate'):
            frames = []
            for fraction in (0.05, .24, .43, .62, .81):
                frame = self.pet._puppet.render(sample(state, duration(state) * fraction))
                self.assertEqual((frame.width(), frame.height()), (768, 832))
                image = frame.toImage()
                for x, y in ((0, 0), (767, 0), (0, 831), (767, 831)):
                    self.assertEqual(image.pixelColor(x, y).alpha(), 0)
                frames.append(bytes(image.constBits()))
            self.assertGreaterEqual(len(set(frames)), 5, state)

    def test_character_render_no_bitmap_cutout_dependency(self):
        # V4 rendering must stay functional even if the legacy puppet PNG is absent.
        frame = self.pet._puppet.render(sample('idle', 3.0))
        self.assertFalse(frame.isNull())
        self.assertGreater(frame.toImage().pixelColor(384, 360).alpha(), 0)

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


if __name__ == '__main__':
    unittest.main()
