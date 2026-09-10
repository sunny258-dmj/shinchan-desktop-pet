"""Read-only sprite audit; writes contact sheets and a local animation review."""
import ast
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'qa'
OUT.mkdir(exist_ok=True)
source = ROOT / 'assets' / 'spritesheet.png'
im = Image.open(source).convert('RGBA')
fw, fh = im.width // 8, im.height // 11
tree = ast.parse((ROOT/'scripts/shinchan_pet_qt.py').read_text(encoding='utf-8'))
animations = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'ANIMATIONS' for t in n.targets))
cells = []
layout = json.loads((ROOT/'assets/spritesheet-layout.json').read_text(encoding='utf-8'))
def rendered_frame(row, col):
    spec = layout['rows'][row][col]
    x,y,w,h = spec['source']; tx,ty,tw,th = spec['target']
    cell = im.crop((x,y,x+w,y+h)).resize((tw,th),Image.Resampling.LANCZOS)
    frame=Image.new('RGBA',(384,416))
    frame.paste(cell,(tx,ty))
    return frame
for row in range(11):
    for col in range(8):
        cell = rendered_frame(row,col)
        alpha = cell.getchannel('A')
        box = alpha.getbbox()
        cells.append({'row': row, 'col': col, 'bounds':box,
                      'edge_contact':bool(box and (box[0] == 0 or box[1] == 0 or box[2] == fw or box[3] == fh)),
                      'transparent_pixels':alpha.histogram()[0],
                      'hash': hashlib.sha256(cell.tobytes()).hexdigest()})
report = {'size':im.size, 'cell_size':[fw,fh], 'alpha_range':im.getchannel('A').getextrema(),
          'empty_cells':[c for c in cells if not c['bounds']],
          'edge_contact_cells':[{'row':c['row'],'col':c['col']} for c in cells if c['edge_contact']],
          'unique_cells':len({c['hash'] for c in cells}), 'cells':cells,
          'limits':'Pixel checks do not prove anatomical or directional correctness. See visual review.'}
(OUT/'asset-audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
font_path = Path('C:/Windows/Fonts/msyh.ttc')
font = ImageFont.truetype(str(font_path), 18) if font_path.exists() else ImageFont.load_default()
sheet = Image.new('RGB', (8*192, 11*238), '#f2f4f7')
draw = ImageDraw.Draw(sheet)
names = [*list(animations)[:9], 'look source', 'hero-celebrate']
for row in range(11):
    for col in range(8):
        cell = rendered_frame(row,col).resize((192,208), Image.Resampling.LANCZOS)
        x,y=col*192,row*238
        draw.rectangle((x,y,x+191,y+237), fill=('#f2f4f7' if col%2 == 0 else '#253247'))
        sheet.paste(cell,(x,y+27),cell)
        draw.text((x+5,y+4),f'{names[row]} {col}',font=font,fill=('#17243b' if col%2 == 0 else '#ffffff'))
sheet.save(OUT/'atlas-contact.png')
cardinals = Image.new('RGB',(5*192,238),'#f2f4f7')
for i,(label,col) in enumerate([('左 / Left',5),('左上 / Up-left',6),('正面 / Neutral',0),('右上 / Up-right',1),('右 / Right',2)]):
    cell=rendered_frame(9,col).resize((192,208),Image.Resampling.LANCZOS)
    cardinals.paste(cell,(i*192,28),cell)
    ImageDraw.Draw(cardinals).text((i*192+4,4),label,font=font,fill='#17243b')
cardinals.save(OUT/'look-review.png')
html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>小新动画检查</title>
<style>body{font:16px system-ui;background:#eef2f7;color:#18233a;margin:36px}button{padding:9px 14px;border:1px solid #b7c4d8;border-radius:8px;margin:4px;cursor:pointer}.grid{display:flex;gap:28px;flex-wrap:wrap}.card{background:white;padding:24px;border-radius:18px;box-shadow:0 8px 25px #22335514}canvas{background:repeating-conic-gradient(#eee 0% 25%,white 0% 50%) 0/20px 20px}.dark{background:#253247}h1{font-size:26px}small{display:block;line-height:1.7;max-width:780px}</style>
<h1>蜡笔小新 · 动画检查</h1><p>点击状态检查循环；左边为原播放，右边为修复后的播放。</p><div id="buttons"></div>
<div class="grid"><div class="card"><h3>原播放</h3><canvas id="before" width="192" height="208"></canvas><p id="a"></p></div><div class="card"><h3>修复后</h3><canvas id="after" width="192" height="208"></canvas><p id="b"></p></div></div>
<p><button onclick="paused=!paused">暂停 / 继续</button><button onclick="document.querySelectorAll('canvas').forEach(c=>c.classList.toggle('dark'))">深色 / 浅色</button></p>
<small>现有素材没有可靠的正上方和正下方凝视帧，因此垂直跟随回到正面。图片保留原样；本次修改播放映射和节奏。动作中的装饰星星、烟雾属于现有美术。</small>
<script>const layout=LAYOUT_DATA;const animations=ANIM_DATA;const original=ORIGINAL_DATA;const img=new Image();img.src='../assets/spritesheet.png';let state='idle',paused=false,ticks=[0,0],indexes=[0,0];
const names={'idle':'待机','running-right':'向右跑','running-left':'向左跑','waving':'挥手','jumping':'跳跃','failed':'失败','waiting':'等待','running':'工作','review':'检查','hero-celebrate':'庆祝'};
for(const s in animations){const b=document.createElement('button');b.textContent=names[s];b.onclick=()=>{state=s;ticks=[0,0];indexes=[0,0]};document.querySelector('#buttons').append(b)}
function loop(now){if(img.complete&&!paused){[original,animations].forEach((map,i)=>{const an=map[state];const durations=an.durations;if(now-ticks[i]>=durations[indexes[i]]){indexes[i]=(indexes[i]+1)%durations.length;ticks[i]=now}const col=(an.columns||durations.map((_,j)=>j))[indexes[i]];const c=document.getElementById(i?'after':'before');const ctx=c.getContext('2d');ctx.clearRect(0,0,192,208);ctx.drawImage(img,col*384,an.row*416,384,416,0,0,192,208);document.getElementById(i?'b':'a').textContent=names[state]+' · 源帧 '+col})}requestAnimationFrame(loop)}requestAnimationFrame(loop);</script></html>'''
import zipfile
with zipfile.ZipFile(OUT/'original-scripts.zip') as z:
    old = next(z.read(n).decode('utf-8-sig') for n in z.namelist() if n.endswith('shinchan_pet_qt.py'))
old_tree=ast.parse(old)
original=next(ast.literal_eval(n.value) for n in old_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ANIMATIONS' for t in n.targets))
html=html.replace("ctx.drawImage(img,col*384,an.row*416,384,416,0,0,192,208)", "if(i){const f=layout.rows[an.row][col];ctx.drawImage(img,...f.source,...f.target.map(v=>v/2))}else{ctx.drawImage(img,col*384,an.row*416,384,416,0,0,192,208)}")
(OUT/'animation-preview.html').write_text(html.replace('LAYOUT_DATA',json.dumps(layout)).replace('ANIM_DATA',json.dumps(animations)).replace('ORIGINAL_DATA',json.dumps(original)),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='cells'},ensure_ascii=False))
