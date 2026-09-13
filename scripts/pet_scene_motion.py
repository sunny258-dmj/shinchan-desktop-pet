"""Scene choreography: long-form motion clips for every pet state.

Each state is a complete mini-performance instead of a 1-2 pose ping-pong:
- neutral-compatible starts and ends for smooth transitions
- anticipation / main action / recovery within each scene
- long loops for frequently-seen states to reduce repetition
- secondary motion and gaze handled separately from the keyed poses
"""
import math

BASE = dict(x=0., y=0., lean=0., head=0., turn=0.,
            lx=-64., ly=317., rx=64., ry=317.,
            flx=-28., fly=378., frx=28., fry=378.,
            cape=0., happy=0., puzzled=0., laptop=0., board=0., pencil=0.,
            board_angle=0., board_y=0., thumb=0., blink=0., eye_x=0., eye_y=0.,
            idea=0., question=0., tear=0., heart=0., cup=0., surprise=0.)


def track(*keys):
    """Each key explicitly overrides a neutral pose, avoiding sticky properties."""
    return [(time, dict(BASE, **pose)) for time, pose in keys]


SCENES = {
    'idle': track(
        (0.0, {}),
        (1.5, {}),
        (2.4, dict(head=-5, turn=-.18, eye_x=-.25)),
        (3.8, dict(head=-6, turn=-.25, eye_x=-.32)),
        (5.0, dict(head=4, turn=.22, eye_x=.18)),
        (6.3, dict(head=5, turn=.28, eye_x=.28)),
        (7.4, {}),
        (8.2, dict(lx=-74, ly=286, rx=74, ry=286, lean=-2, cape=-6)),
        (9.1, dict(lx=-96, ly=227, rx=96, ry=227, y=-4, head=3, happy=.7, cape=10)),
        (10.3, dict(lx=-90, ly=214, rx=90, ry=214, y=-5, happy=.9, cape=12)),
        (11.4, dict(lx=-70, ly=294, rx=70, ry=294, happy=.3, cape=-4)),
        (12.5, {}),
        (13.4, dict(rx=78, ry=254, lx=-58, ly=320, head=-7, turn=.1)),
        (14.4, dict(rx=92, ry=232, lx=-54, ly=312, head=-10, turn=.14, thumb=.3)),
        (15.2, dict(rx=74, ry=260, lx=-60, ly=320, head=-5)),
        (16.1, {}),
        (17.1, dict(lx=-88, ly=296, rx=52, ry=308, lean=-5, head=-3)),
        (18.2, dict(lx=-108, ly=274, rx=36, ry=316, lean=-7, head=-5, puzzled=.15)),
        (19.2, dict(lx=-78, ly=308, rx=56, ry=309, lean=-1)),
        (20.5, dict(lx=-56, ly=294, rx=84, ry=280, head=4, turn=.15, happy=.6)),
        (21.8, dict(lx=-50, ly=286, rx=92, ry=268, head=6, turn=.18, happy=.85)),
        (23.0, dict(lx=-61, ly=309, rx=71, ry=301, happy=.2)),
        (24.0, {})
    ),
    'running': track(
        (0.0, {}),
        (0.5, dict(lean=3, head=-2, happy=.15)),
        (1.0, dict(y=-2, lx=-52, ly=308, rx=52, ry=308, laptop=1)),
        (2.0, dict(laptop=1, lx=-26, ly=352, rx=24, ry=352, lean=5, head=2)),
        (3.2, dict(laptop=1, lx=-18, ly=346, rx=20, ry=344, lean=6, head=-2)),
        (4.2, dict(laptop=1, lx=-35, ly=358, rx=33, ry=356, lean=4, head=4)),
        (5.0, dict(laptop=1, lx=-18, ly=346, rx=18, ry=346, head=-3)),
        (6.0, dict(board=1, pencil=1, lx=-42, ly=306, rx=44, ry=300, board_y=-6, head=5)),
        (7.2, dict(board=1, pencil=1, lx=-38, ly=293, rx=24, ry=278, board_y=-17, board_angle=-10, head=-3)),
        (8.4, dict(board=1, pencil=1, lx=-36, ly=294, rx=51, ry=283, board_y=-12, board_angle=8, head=4)),
        (9.2, dict(board=1, pencil=0, lx=-40, ly=306, rx=40, ry=309, board_y=-5, head=0)),
        (10.0, dict(rx=86, ry=214, lx=-40, ly=304, head=-8, turn=.15, thumb=.55)),
        (11.0, dict(rx=80, ry=228, lx=-32, ly=296, head=8, turn=-.1)),
        (12.0, dict(laptop=1, lx=-28, ly=350, rx=24, ry=348, lean=6, head=3)),
        (13.2, dict(laptop=1, lx=-36, ly=362, rx=35, ry=361, lean=7, head=-5, y=-3)),
        (14.3, dict(laptop=1, lx=-24, ly=346, rx=20, ry=344, lean=5, head=4)),
        (15.2, dict(lx=-36, ly=300, rx=44, ry=296, happy=.35)),
        (16.4, dict(lx=-48, ly=288, rx=50, ry=287, happy=.55, head=-4)),
        (17.8, dict(laptop=1, lx=-26, ly=350, rx=26, ry=350)),
        (23.0, dict(laptop=1, lx=-26, ly=350, rx=26, ry=350, head=4)),
        (24.0, dict(board=1, pencil=1, lx=-40, ly=300, rx=20, ry=281)),
        (28.0, dict(board=1, pencil=1, lx=-40, ly=300, rx=20, ry=281, head=-5)),
        (29.0, dict(cup=1, rx=68, ry=280)),
        (30.0, dict(cup=1, rx=55, ry=240, head=-5)),
        (32.0, dict(cup=1, rx=55, ry=240, head=-5, happy=.3)),
        (33.0, dict(cup=1, rx=68, ry=280)),
        (34.0, {}),
        (35.0, dict(lx=-96, ly=209, rx=96, ry=209, y=-4, happy=.8, cape=12)),
        (37.0, dict(lx=-90, ly=219, rx=90, ry=219, head=6, happy=.8)),
        (38.0, {}),
        (39.0, dict(laptop=1, lx=-26, ly=350, rx=26, ry=350)),
        (44.0, dict(laptop=1, lx=-26, ly=350, rx=26, ry=350, head=-3)),
        (45.0, {})
    ),
    'thinking': track(
        (0.0, {}),
        (0.7, dict(head=-4, turn=.08)),
        (1.6, dict(rx=86, ry=220, lx=-28, ly=293, head=-8, turn=.15, eye_x=.16)),
        (2.8, dict(rx=96, ry=204, lx=-24, ly=286, head=-10, turn=.22, thumb=.35, eye_y=-.14)),
        (4.2, dict(rx=90, ry=215, lx=24, ly=274, head=8, turn=-.18, eye_x=-.22)),
        (5.6, dict(rx=36, ry=232, lx=18, ly=270, head=10, turn=-.2, eye_y=-.2)),
        (6.8, dict(lx=-48, ly=294, rx=92, ry=188, head=-5, turn=.1)),
        (8.0, dict(lx=-22, ly=283, rx=36, ry=226, head=-11, turn=.12)),
        (9.0, dict(y=-3, lx=-72, ly=262, rx=72, ry=218, happy=.45, head=2)),
        (10.2, dict(y=-4, lx=-58, ly=286, rx=84, ry=232, happy=.8, head=5, turn=.18, thumb=.8)),
        (11.4, dict(rx=82, ry=250, lx=-44, ly=304, happy=.55, head=-3)),
        (12.6, dict(rx=68, ry=274, lx=-52, ly=309, happy=.18)),
        (13.8, {}),
        (14.6, {})
    ),
    'review': track(
        (0.0, dict(board=1, pencil=1, lx=-44, ly=311, rx=42, ry=310)),
        (1.0, dict(board=1, pencil=1, lx=-42, ly=294, rx=42, ry=292, board_y=-14, head=6)),
        (2.2, dict(board=1, pencil=1, lx=-42, ly=294, rx=42, ry=292, board_y=-14, head=-6)),
        (3.2, dict(board=1, pencil=1, lx=-40, ly=291, rx=10, ry=281, board_y=-18, head=5)),
        (4.4, dict(board=1, pencil=1, lx=-38, ly=291, rx=10, ry=281, board_y=-18, head=-4)),
        (5.2, dict(board=1, pencil=1, lx=-39, ly=295, rx=44, ry=286, board_y=-11, board_angle=-12, head=3)),
        (6.0, dict(board=1, pencil=1, lx=-39, ly=295, rx=20, ry=270, board_y=-11, board_angle=8, head=-2)),
        (6.9, dict(board=1, pencil=1, lx=-37, ly=294, rx=48, ry=297, board_y=-9, board_angle=-6, head=2)),
        (8.0, dict(board=1, pencil=1, lx=-41, ly=305, rx=46, ry=308, board_y=-3, head=1)),
        (9.1, dict(board=1, pencil=1, lx=-36, ly=296, rx=16, ry=276, board_y=-16, head=7)),
        (10.4, dict(board=1, pencil=1, lx=-36, ly=296, rx=16, ry=276, board_y=-16, head=-5)),
        (11.6, dict(board=1, pencil=1, lx=-38, ly=301, rx=42, ry=284, board_y=-8, board_angle=10, head=5, happy=.35)),
        (12.8, dict(board=1, pencil=0, lx=-40, ly=306, rx=68, ry=246, board_y=-4, board_angle=0, head=-4, thumb=1., happy=.65)),
        (14.0, dict(board=1, pencil=0, lx=-42, ly=309, rx=56, ry=276, happy=.35)),
        (15.0, dict(board=1, pencil=0, lx=-44, ly=311, rx=42, ry=310)),
        (15.8, {})
    ),
    'waiting': track(
        (0.0, {}),
        (1.3, dict(head=-4, turn=.06)),
        (2.3, dict(rx=96, ry=214, lx=-56, ly=311, head=-8, thumb=.45)),
        (3.6, dict(rx=102, ry=204, lx=-54, ly=307, head=-10, thumb=.65)),
        (4.8, dict(rx=82, ry=242, lx=-58, ly=314, head=4, turn=-.06)),
        (5.8, dict(rx=54, ry=303, lx=-52, ly=315, head=1)),
        (6.9, dict(lx=-76, ly=300, rx=48, ry=310, lean=-4, head=-3)),
        (8.0, dict(lx=-86, ly=292, rx=44, ry=312, lean=-6, head=-6, puzzled=.15)),
        (9.2, dict(lx=-54, ly=315, rx=58, ry=312, lean=0, puzzled=0)),
        (10.2, dict(rx=108, ry=224, lx=-52, ly=309, head=-5, turn=.1, thumb=.55)),
        (11.6, dict(rx=90, ry=248, lx=-52, ly=312, head=2, turn=-.08)),
        (12.9, dict(y=2, flx=-25, frx=29, head=-1)),
        (13.8, dict(y=-1, flx=-31, frx=24, head=1)),
        (14.8, dict(rx=84, ry=252, lx=-58, ly=317, head=-4)),
        (16.0, {}),
        (16.8, {})
    ),
    'failed': track(
        (0.0, {}),
        (0.6, dict(y=-2, puzzled=.5)),
        (1.6, dict(lean=7, head=8, lx=-42, ly=292, rx=42, ry=292, puzzled=1.0)),
        (2.8, dict(lean=7, head=8, lx=-42, ly=292, rx=42, ry=292, puzzled=1.0)),
        (3.8, dict(rx=88, ry=216, lx=-52, ly=305, head=-9, puzzled=1.0, thumb=.25)),
        (5.0, dict(rx=64, ry=256, lx=-48, ly=304, head=4, puzzled=1.0)),
        (6.1, dict(lx=-88, ly=273, rx=88, ry=273, head=7, puzzled=1.0)),
        (7.3, dict(lx=-98, ly=268, rx=98, ry=268, head=6, puzzled=1.0)),
        (8.6, dict(lx=-54, ly=305, rx=56, ry=305, head=-5, puzzled=.8)),
        (9.6, dict(y=16, lx=-35, ly=328, rx=35, ry=328, head=10, puzzled=.8, tear=1)),
        (10.8, dict(lx=-44, ly=306, rx=92, ry=236, head=2, thumb=.6, puzzled=.45)),
        (12.0, dict(lx=-52, ly=311, rx=74, ry=278, head=-2, puzzled=.18)),
        (13.2, dict(happy=.08, puzzled=.05)),
        (14.0, {}),
        (14.8, {})
    ),
    'waving': track(
        (0.0, {}),
        (0.4, dict(head=-2, turn=.12, happy=.45)),
        (0.9, dict(rx=102, ry=206, head=-4, happy=.65)),
        (1.2, dict(rx=88, ry=182, head=-4, happy=.8)),
        (1.5, dict(rx=118, ry=198, head=-4, happy=.85)),
        (1.8, dict(rx=88, ry=182, head=-4, happy=.9)),
        (2.1, dict(rx=120, ry=198, head=-4, happy=.95)),
        (2.5, dict(rx=92, ry=187, head=-2, happy=.9)),
        (2.9, dict(rx=110, ry=203, head=-2, happy=.95)),
        (3.3, dict(rx=94, ry=192, happy=.8)),
        (3.8, dict(rx=74, ry=242, happy=.6, head=2)),
        (4.4, dict(happy=.3)),
        (4.9, {})
    ),
    'jumping': track(
        (0.0, {}),
        (0.35, dict(y=12, lx=-46, ly=327, rx=46, ry=327, head=4)),
        (0.65, dict(y=18, lx=-66, ly=334, rx=66, ry=334, cape=-6)),
        (0.95, dict(y=-18, lx=-92, ly=226, rx=92, ry=226, fly=368, fry=368, cape=10, happy=.55)),
        (1.22, dict(y=-48, lx=-102, ly=204, rx=102, ry=204, flx=-42, frx=42, fly=362, fry=362, cape=17, happy=1.0)),
        (1.55, dict(y=-26, lx=-94, ly=222, rx=94, ry=222, happy=1.0, cape=12)),
        (1.9, dict(y=10, lx=-72, ly=305, rx=72, ry=305, cape=-14, happy=.9)),
        (2.25, dict(y=-4, cape=4, happy=.85)),
        (2.6, dict(rx=88, ry=246, thumb=.95, happy=.95, head=-5)),
        (3.2, dict(rx=74, ry=264, happy=.7)),
        (3.8, dict(happy=.35)),
        (4.4, {})
    ),
    'hero-celebrate': track(
        (0.0, {}),
        (0.3, dict(y=-2, head=3, happy=.35)),
        (0.7, dict(y=12, lx=-34, ly=293, rx=34, ry=293, head=5, happy=.6)),
        (1.0, dict(y=18, lx=-44, ly=286, rx=44, ry=286, head=6, cape=-4, happy=.75)),
        (1.3, dict(y=-28, lx=-106, ly=198, rx=106, ry=198, fly=368, fry=368, cape=11, happy=1.0)),
        (1.62, dict(y=-56, lx=-112, ly=180, rx=112, ry=180, flx=-44, frx=44, fly=364, fry=364, cape=16, happy=1.0)),
        (1.96, dict(y=-22, lx=-98, ly=206, rx=98, ry=206, cape=8, happy=1.0)),
        (2.35, dict(y=12, lx=-74, ly=300, rx=74, ry=300, cape=-13, happy=1.0)),
        (2.72, dict(y=0, lx=-54, ly=300, rx=54, ry=300, happy=1.0)),
        (3.15, dict(lx=-42, ly=314, rx=42, ry=314, happy=1.0)),
        (3.55, dict(lx=-52, ly=310, rx=86, ry=248, thumb=1.0, head=-5, happy=1.0)),
        (4.4, dict(lx=-44, ly=311, rx=82, ry=248, thumb=1.0, head=-3, happy=1.0)),
        (5.1, dict(lx=-84, ly=286, rx=54, ry=304, head=4, cape=-7, happy=.95)),
        (5.8, dict(lx=-58, ly=304, rx=62, ry=300, cape=2, happy=.6)),
        (6.6, {})
    ),
    'look': track((0.0, {}), (4.0, {})),
}

for direction in ('running-left', 'running-right'):
    sign = -1 if direction == 'running-left' else 1
    SCENES[direction] = track(
        (0.0, {}),
        (0.4, dict(y=8, lean=sign * 3, turn=sign * .15)),
        (0.9, dict(y=-4, lean=sign * 8, turn=sign * .4,
                   lx=-52, ly=300, rx=52, ry=300, cape=sign * 6)),
        (4.8, dict(y=-4, lean=sign * 8, turn=sign * .82,
                   lx=-60, ly=300, rx=60, ry=300, cape=sign * 11)),
        (5.2, dict(y=4, lean=sign * 4, turn=sign * .3,
                   lx=-54, ly=312, rx=54, ry=312, cape=sign * 4)),
        (5.9, dict(y=0, lean=0, turn=0, cape=0)),
        (6.4, {})
    )


SCENES['walking-left'] = SCENES['running-left']
SCENES['walking-right'] = SCENES['running-right']


def duration(state):
    return SCENES[state][-1][0]


def sample(state, elapsed, gaze=(0., 0.)):
    keys = SCENES[state]
    t = max(0., elapsed) % keys[-1][0]
    for (a, pa), (b, pb) in zip(keys, keys[1:]):
        if a <= t <= b:
            u = (t - a) / (b - a)
            u = u * u * (3 - 2 * u)
            pose = {k: pa[k] + (pb[k] - pa[k]) * u for k in BASE}
            break
    else:
        pose = dict(keys[-1][1])

    scene_len = keys[-1][0]
    pose['head'] += .6 * math.sin(2 * math.pi * t / scene_len)
    pose['cape'] += 1.1 * math.sin(4 * math.pi * t / scene_len - .25)

    if state == 'idle':
        pose['y'] += 1.8 * math.sin(2 * math.pi * t / 5.8)
        pose['eye_x'] += .08 * math.sin(2 * math.pi * t / 8.0)
    if state == 'running':
        if pose['laptop'] > .1:
            pose['ly'] += 3.5 * math.sin(t * 16.0)
            pose['ry'] += 3.5 * math.sin(t * 16.0 + math.pi)
            pose['head'] += 1.4 * math.sin(t * 7.5)
        if pose['board'] > .1:
            pose['rx'] += 3.0 * math.sin(t * 8.0)
            pose['ry'] += 2.0 * math.sin(t * 16.0)
    if state == 'thinking':
        pose['idea'] = max(0., 1 - abs(t - 10.2) / 1.7)
        pose['head'] += 1.5 * math.sin(t * 2.8)
        pose['eye_y'] += -.07 * abs(math.sin(t * 1.6))
    if state == 'review' and pose['pencil'] > .1:
        pose['rx'] += 4.0 * math.sin(t * 8.0)
        pose['ry'] += 2.6 * math.sin(t * 16.0)
    if state == 'waiting':
        pose['question'] = max(0., 1 - abs(t - 14.8) / 1.1)
        pose['surprise'] = pose['question']
        pose['head'] += .8 * math.sin(t * 2.2)
        if 12.2 < t < 14.2:
            pose['fly'] += 3.2 * math.sin((t - 12.2) * math.pi * 3.0)
            pose['fry'] += 3.2 * math.sin((t - 12.2) * math.pi * 3.0 + math.pi)
    if state == 'failed':
        pose['question'] = max(0., 1 - abs(t - 4.2) / 2.3)
        pose['surprise'] = max(0., 1 - abs(t - 1.6) / 1.5)
        pose['head'] += 1.2 * math.sin(t * 1.8)
        pose['puzzled'] = max(pose['puzzled'], .15 * max(0., math.sin(t * 3.2)))
    if state in ('jumping', 'hero-celebrate'):
        pose['heart'] = max(0., 1 - abs(t - (3.1 if state == 'jumping' else 4.4)) / 1.1)
        pose['cape'] += 2.8 * math.sin(t * 6.0)
    if state.startswith('running-'):
        envelope = max(0, min(1, (t - .55) / .35, (5.15 - t) / .45))
        cycle = max(0., t - .78) * math.pi * 2 / 0.62
        sign = -1 if state == 'running-left' else 1
        pose['lean'] = sign * (4 + 4 * envelope)
        pose['turn'] = sign * (.18 + .66 * envelope)
        pose['flx'] = -28 + 25 * math.sin(cycle) * envelope
        pose['frx'] = 28 - 25 * math.sin(cycle) * envelope
        pose['fly'] = 378 - 29 * max(0, math.cos(cycle)) * envelope
        pose['fry'] = 378 - 29 * max(0, -math.cos(cycle)) * envelope
        pose['lx'] = -58 - 18 * math.sin(cycle) * envelope
        pose['rx'] = 58 + 18 * math.sin(cycle) * envelope
        pose['ly'] = 301 + 19 * math.sin(cycle) * envelope
        pose['ry'] = 301 - 19 * math.sin(cycle) * envelope
        pose['y'] += -5 * abs(math.sin(cycle)) * envelope
        pose['cape'] += sign * 12 * envelope + 4 * math.sin(cycle - .7) * envelope
    if state == 'look':
        pose['head'] += gaze[0] * 7 + gaze[1] * 3
        pose['turn'] = gaze[0] * .65
        pose['lean'] = gaze[0] * 2
        pose['eye_x'] = gaze[0]
        pose['eye_y'] = gaze[1]

    blink_phase = t % 4.1
    pose['blink'] = max(0, 1 - abs(blink_phase - 3.2) / .095)
    # Keep reference-atlas selection separate from the continuous legacy rig.
    pose['_state'] = state
    pose['_elapsed'] = max(0., elapsed)
    pose['_gaze'] = gaze
    return pose


def mix(a, b, fraction):
    f = max(0., min(1., fraction))
    f = f * f * (3 - 2 * f)
    result = {k: a[k] + (b[k] - a[k]) * f for k in BASE}
    result.update({k: v for k, v in b.items() if k.startswith('_')})
    return result
