"""Compatibility frame sampler backed by the live reference-art renderer."""
from functools import lru_cache
from pet_reference_renderer import Puppet, playback_duration as duration
from pet_scene_motion import sample

CLIP_STATES = (
    'idle', 'running', 'thinking', 'waiting', 'review', 'jumping',
    'hero-celebrate', 'waving', 'failed', 'running-left', 'running-right',
)

CLIPS = {
    state: (row, [duration(state) * 1000 / 8] * 8)
    for row, state in enumerate(CLIP_STATES)
}


@lru_cache(maxsize=2)
def load_actions(directory):
    """Return eight representative transparent frames per clip from the atlas."""
    puppet = Puppet(directory)
    frames = {}
    for row, state in enumerate(CLIP_STATES):
        length = duration(state)
        for col in range(8):
            # Centre samples within each time slice so the first/last frames do not
            # duplicate the neutral endpoints of looping scenes.
            elapsed = length * (col + .5) / 8
            frames[row, col] = puppet.render(sample(state, elapsed))
    return frames
