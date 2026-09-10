import unittest
import test_pet as fixture
gui = fixture.gui


class RedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.GuiTests.setUpClass()
        cls.app = fixture.GuiTests.app

    setUp = fixture.GuiTests.setUp
    tearDown = fixture.GuiTests.tearDown
    def test_action_frames_are_transparent_and_distinct(self):
        for state in ('idle','running','thinking','waiting','review','jumping'):
            anim = gui.ANIMATIONS[state]
            frames = [self.pet._action_frames[anim['row'], i].toImage()
                      for i in range(len(anim['durations']))]
            self.assertGreaterEqual(len(frames), 8)
            self.assertGreaterEqual(len({bytes(f.constBits()) for f in frames}), 8)
            for f in frames:
                self.assertEqual(f.pixelColor(0,0).alpha(), 0)
                self.assertEqual(f.pixelColor(f.width()-1,0).alpha(), 0)

    def test_bubble_tip_tracks_visible_head(self):
        self.pet.move(300,400)
        self.pet._auto_active = True
        self.pet._set_state('waiting')
        self.pet._show_bubble('等待你的选择')
        self.app.processEvents()
        for i in range(8):
            self.pet._frame_index = i
            self.pet._show_frame()
            b = self.pet._bubble
            tip = b.y() + b.height() - b.M_B - 2 * gui.UI_SCALE
            gap = self.pet.visual_geometry().top() - tip
            self.assertGreaterEqual(gap, 0)
            self.assertLessEqual(gap, 7)

if __name__ == '__main__':
    unittest.main()
