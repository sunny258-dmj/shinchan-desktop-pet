"""Scene choreography: continuous joint targets, independent of rendering FPS.

All tracks start and finish in a compatible resting pose. Large gestures have
anticipation/recovery; quiet states spend most of their time actually waiting.
"""
import math

BASE = dict(x=0., y=0., lean=0., head=0., turn=0.,
            lx=-64., ly=317., rx=64., ry=317.,
            flx=-28., fly=378., frx=28., fry=378.,
            cape=0., happy=0., puzzled=0., laptop=0., board=0., pencil=0.,
            board_angle=0., board_y=0., thumb=0., blink=0., eye_x=0., eye_y=0.)


def track(*keys):
    """Each key explicitly overrides a neutral pose, avoiding sticky properties."""
    return [(time, dict(BASE, **pose)) for time,pose in keys]


SCENES = {
 'idle': track((0,{}),(2.2,{}),(2.8,dict(head=-7,turn=-.2)),
    (3.8,dict(head=-7,turn=-.2)),(4.6,dict(head=7,turn=.3)),(5.5,dict(head=7,turn=.3)),
    (6.1,{}),(7.0,dict(lx=-66,ly=278,lean=-3,cape=-6)),
    (7.5,dict(lx=-73,ly=296,cape=8)),(8.2,{}),(11,{}),
    (11.5,dict(y=4,head=3)),(12.4,dict(lx=-100,ly=219,rx=100,ry=219,y=-3,head=-4,happy=1)),
    (13.3,dict(lx=-90,ly=205,rx=90,ry=205,y=-4,happy=1)),(14.4,{}),(18,{})),
 'running': track((0,dict(laptop=1,lx=-21,ly=350,rx=26,ry=350,lean=3)),
    (2.5,dict(laptop=1,lx=-21,ly=350,rx=26,ry=350,lean=3)),
    (3.0,dict(laptop=1,lx=-42,ly=347,rx=23,ry=350,lean=4,head=3)),
    (4.3,dict(laptop=1,lx=-42,ly=347,rx=23,ry=350,lean=4,head=3)),
    (4.8,dict(laptop=1,lx=-34,ly=360,rx=34,ry=360,head=-5,y=-2)),
    (5.7,dict(laptop=1,lx=-34,ly=360,rx=34,ry=360,head=-5,y=-2)),
    (6.0,dict(laptop=1,lx=-34,ly=360,rx=34,ry=360,head=5,y=2)),
    (6.4,dict(laptop=1,lx=-34,ly=360,rx=34,ry=360,head=-2)),
    (7,dict(laptop=1,lx=-21,ly=350,rx=26,ry=350,lean=3))),
 'thinking': track((0,{}),(1,dict(lx=20,ly=276,rx=-20,ry=291,head=-6)),
    (2.1,dict(lx=20,ly=276,rx=-20,ry=291,head=-6)),
    (2.8,dict(lx=18,ly=272,rx=38,ry=228,head=7)),
    (4,dict(lx=18,ly=272,rx=38,ry=228,head=7)),
    (4.6,dict(lx=-48,ly=294,rx=94,ry=171,head=-5)),
    (5.5,dict(lx=-48,ly=294,rx=94,ry=171,head=-5)),
    (6.2,dict(lx=15,ly=280,rx=34,ry=230,head=-9,turn=.15)),
    (7.8,dict(lx=15,ly=280,rx=34,ry=230,head=-9,turn=.15)),
    (8.3,dict(rx=88,ry=200,head=1,thumb=.5)),(8.9,dict(rx=88,ry=200,head=1,thumb=.5)),
    (9.8,{}),(11,{})),
 'review': track((0,dict(board=1,pencil=1,lx=-35,ly=306,rx=42,ry=309)),
    (1,dict(board=1,pencil=1,lx=-35,ly=290,rx=42,ry=293,board_y=-16,head=5)),
    (2,dict(board=1,pencil=1,lx=-35,ly=290,rx=42,ry=293,board_y=-16,head=-5)),
    (3,dict(board=1,pencil=1,lx=-35,ly=290,rx=42,ry=293,board_y=-16,head=6)),
    (3.5,dict(board=1,pencil=1,lx=-35,ly=290,rx=5,ry=283,board_y=-16,head=4)),
    (4.6,dict(board=1,pencil=1,lx=-35,ly=290,rx=5,ry=283,board_y=-16,head=4)),
    (5.1,dict(board=1,pencil=1,lx=-35,ly=295,rx=40,ry=278,board_y=-11,board_angle=-12)),
    (5.7,dict(board=1,pencil=1,lx=-35,ly=295,rx=40,ry=300,board_y=-11,board_angle=8)),
    (6.4,dict(board=1,pencil=1,lx=-35,ly=306,rx=42,ry=309,head=3)),
    (7,dict(board=1,pencil=1,lx=-35,ly=306,rx=42,ry=309))),
 'waiting': track((0,{}),(1,dict(head=-7,turn=.1)),
    (1.8,dict(rx=104,ry=206,head=-8,thumb=.5)),
    (2.8,dict(rx=104,ry=206,head=-8,thumb=.5)),
    (3.5,dict(rx=88,ry=248,head=3,turn=-.1)),
    (4.2,{}),(12,{})),
 'hero-celebrate': track((0,{}),(.5,dict(y=10,lx=-33,ly=292,rx=33,ry=292,head=4)),
    (.85,dict(y=16,lx=-35,ly=288,rx=35,ry=288,head=5,cape=-5)),
    (1.1,dict(y=-25,lx=-104,ly=199,rx=104,ry=199,fly=369,fry=369,happy=1,cape=10)),
    (1.4,dict(y=-48,lx=-108,ly=184,rx=108,ry=184,flx=-44,frx=44,fly=365,fry=365,happy=1,cape=15)),
    (1.7,dict(y=-22,lx=-98,ly=202,rx=98,ry=202,happy=1,cape=5)),
    (1.95,dict(y=11,lx=-67,ly=291,rx=67,ry=291,happy=1,cape=-12)),
    (2.25,dict(lx=-62,ly=309,rx=63,ry=276,happy=1)),
    (2.8,dict(rx=82,ry=247,thumb=1,head=-5,happy=1)),
    (4,dict(rx=82,ry=247,thumb=1,head=-5,happy=1)),(4.8,{})),
 'jumping': track((0,{}),(.4,dict(y=14,lx=-52,ly=329,rx=52,ry=329,head=4)),
    (.65,dict(y=18,lx=-67,ly=332,rx=67,ry=332,cape=-6)),
    (.9,dict(y=-28,lx=-99,ly=216,rx=99,ry=216,fly=369,fry=369,cape=8)),
    (1.15,dict(y=-55,lx=-103,ly=205,rx=103,ry=205,fly=360,fry=360,happy=1,cape=16)),
    (1.45,dict(y=-25,lx=-100,ly=228,rx=100,ry=228,happy=1,cape=10)),
    (1.7,dict(y=14,lx=-75,ly=309,rx=75,ry=309,cape=-14)),
    (2.1,dict(y=-2,cape=5)),(2.6,{}),(3.5,{})),
 'failed': track((0,{}),(.45,dict(head=0,puzzled=1)),
    (1.2,dict(lean=8,head=9,lx=-42,ly=290,rx=42,ry=290,puzzled=1)),
    (2,dict(lean=8,head=9,lx=-42,ly=290,rx=42,ry=290,puzzled=1)),
    (2.5,dict(lean=-5,head=-8,y=-2,puzzled=1)),
    (3.2,dict(lx=-95,ly=267,rx=95,ry=267,head=6,puzzled=1)),
    (4.3,dict(lx=-95,ly=267,rx=95,ry=267,head=6,puzzled=1)),
    (5.2,dict(puzzled=1)),(10,dict(puzzled=1)),(11,{})),
 'waving': track((0,{}),(.35,dict(head=-3,turn=.12)),
    (.8,dict(rx=112,ry=194,head=-4)),(1.05,dict(rx=91,ry=184,head=-4)),
    (1.3,dict(rx=117,ry=197,head=-4)),(1.55,dict(rx=91,ry=184,head=-4)),
    (1.8,dict(rx=117,ry=197,head=-4)),(2.2,dict(rx=98,ry=209,happy=1)),
    (2.7,dict(happy=1)),(3.3,{})),
 'look': track((0,{}),(4,{})),
}
for direction in ('running-left','running-right'):
    SCENES[direction]=track((0,{}),(.6,dict(lean=8)),(4.0,dict(lean=8)),(4.6,{}),(5.2,{}))


def duration(state):
    return SCENES[state][-1][0]


def sample(state, elapsed, gaze=(0.,0.)):
    keys=SCENES[state]
    t=max(0.,elapsed)%keys[-1][0]
    for (a,pa),(b,pb) in zip(keys,keys[1:]):
        if a <= t <= b:
            u=(t-a)/(b-a)
            u=u*u*(3-2*u)
            pose={k:pa[k]+(pb[k]-pa[k])*u for k in BASE}
            break
    else:
        pose=dict(keys[-1][1])
    # Small continuous secondary motion, never the main action.
    pose['head'] += .7*math.sin(2*math.pi*t/keys[-1][0])
    pose['cape'] += 1.2*math.sin(4*math.pi*t/keys[-1][0]-.3)
    if state=='running' and (t<4.4 or t>6.5):
        fade=min(1,max(0,(4.4-t)/.25)) if t<4.4 else min(1,(t-6.5)/.25)
        pose['ly']+=3.5*math.sin(t*19)*fade
        pose['ry']+=3.5*math.sin(t*19+math.pi)*fade
    if state=='running':
        pose['ly']+=22
        pose['ry']+=22
    if state=='thinking' and 4.6<t<5.5:
        pose['ry']+=3*math.sin((t-4.6)*math.pi*8)
    if state=='review' and 3.5<t<4.6:
        pose['rx']+=5*math.sin((t-3.5)*math.pi*4)
        pose['ry']+=3*math.sin((t-3.5)*math.pi*8)
    if state.startswith('running-'):
        envelope=max(0,min(1,t/.6,(4.6-t)/.6))
        cycle=(t-.6)*math.pi*2/0.64
        sign=-1 if state=='running-left' else 1
        pose['lean']=sign*8*envelope
        pose['turn']=sign*.85*envelope
        pose['flx']=-28+24*math.sin(cycle)*envelope
        pose['frx']=28-24*math.sin(cycle)*envelope
        pose['fly']=378-27*max(0,math.cos(cycle))*envelope
        pose['fry']=378-27*max(0,-math.cos(cycle))*envelope
        pose['lx']=-60-18*math.sin(cycle)*envelope
        pose['rx']=60+18*math.sin(cycle)*envelope
        pose['ly']=300+18*math.sin(cycle)*envelope
        pose['ry']=300-18*math.sin(cycle)*envelope
        pose['y']=-4*abs(math.sin(cycle))*envelope
        pose['cape']+=sign*14*envelope+4*math.sin(cycle-.7)*envelope
    if state=='look':
        pose['head']+=gaze[0]*7+gaze[1]*3
        pose['turn']=gaze[0]*.65
        pose['lean']=gaze[0]*2
        pose['eye_x']=gaze[0]
        pose['eye_y']=gaze[1]
    # A blink is a short timed eyelid closure, not a whole pose swap.
    blink_phase=t%4.1
    pose['blink']=max(0,1-abs(blink_phase-3.2)/.095)
    return pose


def mix(a,b,fraction):
    f=max(0.,min(1.,fraction))
    f=f*f*(3-2*f)
    return {k:a[k]+(b[k]-a[k])*f for k in BASE}
