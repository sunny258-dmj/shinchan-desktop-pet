"""Export actual V4 Qt frames and combined companion layout for visual review."""
import json
from pathlib import Path
from test_pet import GuiTests, gui
from pet_scene_motion import duration
from PySide6.QtGui import QFontDatabase

out = Path(__file__).resolve().parents[1] / 'qa'
GuiTests.setUpClass()
for font in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/segoeui.ttf'):
    QFontDatabase.addApplicationFont(font)
test = GuiTests()
test.setUp()
try:
    pet = test.pet
    pet.move(320, 430)
    pet._auto_active = True
    pet._set_state('waiting')
    pet._show_auto('等你确认', '方案准备好了，看看我的新动作吧。', state='waiting', steps=3)
    for _ in range(50):
        pet._tw_tick()
    pet._render_scene(3.4)
    test.app.processEvents()
    bubble = pet._bubble
    bubble.position_near_pet()
    union = pet.geometry().united(bubble.geometry()).adjusted(-16, -16, 16, 16)
    canvas = gui.QPixmap(union.size())
    canvas.fill(gui.QColor('#eaf5ff'))
    painter = gui.QPainter(canvas)
    painter.drawPixmap(pet.pos() - union.topLeft(), pet.grab())
    painter.drawPixmap(bubble.pos() - union.topLeft(), bubble.grab())
    painter.end()
    canvas.save(str(out / 'redesign-companion-v4.png'))

    clips = {}
    frame_dir = out / 'v4-frames'
    frame_dir.mkdir(exist_ok=True)
    states = ('idle', 'running', 'thinking', 'review', 'waiting', 'failed',
              'waving', 'jumping', 'hero-celebrate', 'running-left', 'running-right')
    for state in states:
        frames = []
        count = 30 if duration(state) >= 12 else 22
        step_ms = round(duration(state) * 1000 / count)
        for i in range(count):
            elapsed = duration(state) * i / count
            pet._set_state(state)
            pet._render_scene(elapsed)
            path = f'v4-frames/{state}-{i:02d}.png'
            pet._current_frame.save(str(out / path))
            frames.append({'src': path, 'duration': step_ms})
        clips[state] = frames

    html = '''<!doctype html><meta charset="utf-8"><title>小新桌宠 V4 · 动作预览</title>
<style>body{background:#eaf5ff;color:#24324a;font:16px "Microsoft YaHei";max-width:1080px;margin:40px auto}button,select{font:inherit;padding:10px 14px;border:1px solid #b6d7ee;border-radius:14px;background:#fff;box-shadow:0 4px 14px #5b8fb31e}main{display:flex;align-items:center;gap:50px}.stage{width:420px;height:470px;display:grid;place-items:center;border-radius:28px;background:linear-gradient(#fff,#f4fbff);box-shadow:0 14px 40px #35698d22}.stage img{width:330px}p{line-height:1.8}#counter{font-size:13px;color:#60758b}.shot{max-width:400px;border-radius:22px;box-shadow:0 12px 36px #35698d24}</style>
<h1>蜡笔小新桌宠 V4 · 完整动作预览</h1><p>每个场景按完整动作段连续播放，不再使用一两帧往返。角色为 2× 矢量渲染，透明边缘无需色键抠图。</p>
<select id="state"></select> <button id="pause">暂停</button> <button id="step">下一帧</button> <button id="bg">切换背景</button>
<main><div><div class="stage"><img id="pet"></div><p id="counter"></p></div><img class="shot" src="redesign-companion-v4.png"></main>
<script>const clips=CLIP_DATA;const names={idle:'待机 · 多段小动作',running:'执行任务 · 工作流程',thinking:'思考 · 完整思考链',review:'检查结果 · 阅读记录确认',waiting:'等待确认 · 提示与等待',failed:'任务失败 · 疑惑到恢复',waving:'挥手互动 · 完整招呼',jumping:'开心跳跃 · 蓄力落地','hero-celebrate':'英雄庆祝 · 完整庆祝','running-left':'向左移动 · 完整步态','running-right':'向右移动 · 完整步态'};
const sel=document.querySelector('#state'),img=document.querySelector('#pet');for(const k in clips)sel.add(new Option(names[k]||k,k));let idx=0,paused=false,timer;function draw(){clearTimeout(timer);let f=clips[sel.value][idx];img.src=f.src;document.querySelector('#counter').textContent=`${idx+1} / ${clips[sel.value].length} 采样帧 · ${f.duration} ms`;if(!paused)timer=setTimeout(()=>{idx=(idx+1)%clips[sel.value].length;draw()},f.duration)}sel.onchange=()=>{idx=0;draw()};document.querySelector('#pause').onclick=e=>{paused=!paused;e.target.textContent=paused?'播放':'暂停';draw()};document.querySelector('#step').onclick=()=>{paused=true;document.querySelector('#pause').textContent='播放';idx=(idx+1)%clips[sel.value].length;draw()};let dark=false;document.querySelector('#bg').onclick=()=>{dark=!dark;document.querySelector('.stage').style.background=dark?'#25344c':'linear-gradient(#fff,#f4fbff)'};draw();</script>'''
    (out / 'redesign-preview-v4.html').write_text(
        html.replace('CLIP_DATA', json.dumps(clips, ensure_ascii=False)), encoding='utf-8')
    print('Exported V4 vector character, pastel bubble and full-scene motion preview.')
finally:
    test.tearDown()
