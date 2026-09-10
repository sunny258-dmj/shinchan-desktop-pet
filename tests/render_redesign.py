"""Export the real Qt frames and combined companion layout for visual review."""
import json
from pathlib import Path
from test_pet import GuiTests, gui
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
    for _ in range(50): pet._tw_tick()
    test.app.processEvents()
    bubble = pet._bubble
    bubble.position_near_pet()
    union = pet.geometry().united(bubble.geometry()).adjusted(-16,-16,16,16)
    canvas = gui.QPixmap(union.size())
    canvas.fill(gui.QColor('#dce6e8'))
    painter = gui.QPainter(canvas)
    painter.drawPixmap(pet.pos()-union.topLeft(), pet.grab())
    painter.drawPixmap(bubble.pos()-union.topLeft(), bubble.grab())
    painter.end()
    canvas.save(str(out/'redesign-companion.png'))
    clips = {}
    frame_dir = out/'v2-frames'
    frame_dir.mkdir(exist_ok=True)
    for state, anim in gui.ANIMATIONS.items():
        if anim.get('source') != 'v2': continue
        frames = []
        for i, duration in enumerate(anim['durations']):
            pet._set_state(state)
            pet._frame_index = i
            pet._show_frame()
            path = f'v2-frames/{state}-{i}.png'
            pet._current_frame.save(str(out/path))
            frames.append({'src':path, 'duration':duration})
        clips[state] = frames
    html = '''<!doctype html><meta charset="utf-8"><title>小新 · 动作重设计</title>
<style>body{background:#e0e8e9;color:#3e332c;font:16px "Microsoft YaHei";max-width:940px;margin:45px auto}button,select{font:inherit;padding:10px;border:1px solid #a89b86;border-radius:12px;background:#fff8e5}main{display:flex;align-items:center;gap:60px}.stage{width:384px;height:450px;display:grid;place-items:center;border-radius:28px;background:#fff7e5}.stage img{width:300px}p{line-height:1.8}#counter{font-size:13px}</style>
<h1>小新 · 动作重设计</h1><p>每组动作按独立节奏播放；可暂停逐帧检查。右侧为实际 Qt 气泡与桌宠的组合截图。</p>
<select id="state"></select> <button id="pause">暂停</button> <button id="step">下一帧</button> <button id="bg">切换深色背景</button>
<main><div><div class="stage"><img id="pet"></div><p id="counter"></p></div><img src="redesign-companion.png" style="max-width:350px"></main>
<script>const clips=CLIP_DATA;const names={idle:'待机 · 伸展',running:'工作 · 敲键检查',thinking:'思考 · 托腮挠头',waiting:'等待 · 指向气泡',review:'检查 · 翻看记录',jumping:'跳跃 · 蓄力落地','hero-celebrate':'庆祝 · 竖起拇指',waving:'互动 · 举手招呼'};
const sel=document.querySelector('#state'),img=document.querySelector('#pet');for(const k in clips)sel.add(new Option(names[k],k));let idx=0,paused=false,timer;function draw(){clearTimeout(timer);let f=clips[sel.value][idx];img.src=f.src;document.querySelector('#counter').textContent=`${idx+1} / ${clips[sel.value].length} 帧 · ${f.duration} ms`;if(!paused)timer=setTimeout(()=>{idx=(idx+1)%clips[sel.value].length;draw()},f.duration)}sel.onchange=()=>{idx=0;draw()};document.querySelector('#pause').onclick=e=>{paused=!paused;e.target.textContent=paused?'播放':'暂停';draw()};document.querySelector('#step').onclick=()=>{paused=true;document.querySelector('#pause').textContent='播放';idx=(idx+1)%clips[sel.value].length;draw()};let dark=false;document.querySelector('#bg').onclick=()=>{dark=!dark;document.querySelector('.stage').style.background=dark?'#243246':'#fff7e5'};draw();</script>'''
    (out/'redesign-preview.html').write_text(html.replace('CLIP_DATA',json.dumps(clips)),encoding='utf-8')
    print('Exported actual Qt combined layout and timed action preview.')
finally:
    test.tearDown()
