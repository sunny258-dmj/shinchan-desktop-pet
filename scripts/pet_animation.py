"""Compatibility frame sampler for the V4 vector animation system.

Legacy QA helpers used to load colour-keyed sprite sheets through this module.
V4 keeps the public ``CLIPS``/``load_actions`` API but generates clean frames from
the same continuous vector puppet used by the live desktop pet.
"""
from functools import lru_cache
from pet_puppet import Puppet
from pet_scene_motion import duration, sample

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
    """Return eight representative transparent V4 frames per clip.

    ``directory`` is accepted for backwards compatibility; V4 rendering itself is
    asset-free, so missing legacy PNG sprite sheets no longer affect animation.
    """
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
