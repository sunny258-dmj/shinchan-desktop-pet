"""V4 visual audit: inspect vector frames, alpha edges and scene diversity.

This replaces the legacy sprite-sheet audit. It writes only QA output and never
modifies runtime assets.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QBuffer, QIODevice, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from pet_puppet import Puppet
from pet_scene_motion import SCENES, duration, sample

OUT = ROOT / 'qa'
OUT.mkdir(exist_ok=True)
app = QApplication.instance() or QApplication([])
puppet = Puppet(ROOT / 'assets')

states = tuple(SCENES)
report = {'renderer': 'vector-v4', 'frame_size': [768, 832], 'states': {}}
contact_w = 4 * 250
contact_h = len(states) * 285
contact = QPixmap(contact_w, contact_h)
contact.fill(QColor('#eef8ff'))
painter = QPainter(contact)
painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
painter.setFont(QFont('Microsoft YaHei UI', 10))

for row, state in enumerate(states):
    hashes = []
    edge_violations = []
    samples = 24 if duration(state) >= 10 else 16
    moments = [duration(state) * (i + .5) / samples for i in range(samples)]
    chosen = [duration(state) * f for f in (.12, .34, .58, .82)]

    for i, t in enumerate(moments):
        gaze = (.65, -.15) if state == 'look' else (0., 0.)
        frame = puppet.render(sample(state, t, gaze))
        image = frame.toImage()
        corners = [(0, 0), (image.width() - 1, 0),
                   (0, image.height() - 1), (image.width() - 1, image.height() - 1)]
        if any(image.pixelColor(x, y).alpha() != 0 for x, y in corners):
            edge_violations.append(i)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        frame.save(buffer, 'PNG')
        hashes.append(hashlib.sha256(bytes(buffer.data())).hexdigest())

    report['states'][state] = {
        'duration_sec': duration(state),
        'keyframes': len(SCENES[state]),
        'sample_count': samples,
        'unique_samples': len(set(hashes)),
        'corner_alpha_violations': edge_violations,
    }

    for col, t in enumerate(chosen):
        gaze = (.65, -.15) if state == 'look' else (0., 0.)
        frame = puppet.render(sample(state, t, gaze))
        x, y = col * 250, row * 285
        painter.setPen(QColor('#27445f'))
        painter.drawText(x + 8, y + 20, f'{state} · {t:.1f}s')
        painter.drawPixmap(QRect(x + 16, y + 30, 218, 236), frame)

painter.end()
contact.save(str(OUT / 'vector-contact-v4.png'))

report['summary'] = {
    'state_count': len(states),
    'all_corners_clear': all(not s['corner_alpha_violations'] for s in report['states'].values()),
    'all_samples_distinct': all(s['unique_samples'] == s['sample_count'] for s in report['states'].values()),
}
(OUT / 'vector-audit-v4.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

html = '''<!doctype html><meta charset="utf-8"><title>蜡笔小新桌宠 V4 · 矢量审计</title>
<style>body{background:#eef8ff;color:#27445f;font:16px "Microsoft YaHei";max-width:1080px;margin:36px auto}img{max-width:100%;border-radius:24px;box-shadow:0 14px 44px #315f7d25;background:white}code{background:white;padding:2px 6px;border-radius:6px}</style>
<h1>蜡笔小新桌宠 V4 · 矢量角色审计</h1><p>实时角色不再经过色键抠图。检查项包括透明四角、连续场景采样差异、关键姿态数量和每段动作周期。</p>
<p>数据：<code>vector-audit-v4.json</code></p><img src="vector-contact-v4.png">'''
(OUT / 'vector-audit-v4.html').write_text(html, encoding='utf-8')
print(json.dumps(report['summary'], ensure_ascii=False))
