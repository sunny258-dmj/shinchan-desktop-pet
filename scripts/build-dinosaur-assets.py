"""Extract existing RGBA artwork into reproducible runtime assets (no redrawing).

Opaque connected components define ownership; original antialiased pixels within
two pixels of each component are retained. This avoids the faint alpha bridges
between neighbouring characters in the source sheets.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHEETS = [('idle', '35'), ('interaction', '51'), ('work', '55'),
          ('walk', '40'), ('run', '12'), ('bubbles', '59')]


def extract(image, count):
    rgba = np.asarray(image)
    n, labels, stats, centers = cv2.connectedComponentsWithStats(
        (rgba[:, :, 3] >= 128).astype('uint8'), connectivity=8)
    major = sorted(range(1, n), key=lambda i: stats[i, 4], reverse=True)[:count]
    # Cluster by row first: decorative elements must not alter row ordering.
    major.sort(key=lambda i: centers[i, 1])
    rows = [major[:6], major[6:]] if count == 12 else [major[:3], major[3:5], major[5:]]
    major = [i for row in rows for i in sorted(row, key=lambda i: centers[i, 0])]
    owners = {i: index for index, i in enumerate(major)}
    for i in range(1, n):
        if i in owners or stats[i, 4] < 40:
            continue
        x, y, w, h, _ = stats[i]
        def distance(j):
            mx, my, mw, mh, _ = stats[j]
            return max(mx-x-w, x-mx-mw, 0)**2 + max(my-y-h, y-my-mh, 0)**2
        nearest = min(major, key=distance)
        if distance(nearest) <= 100**2:
            owners[i] = major.index(nearest)
    results = []
    for index, ident in enumerate(major):
        mask = np.isin(labels, [i for i, owner in owners.items() if owner == index]).astype('uint8')
        mask = cv2.dilate(mask, np.ones((5, 5), dtype='uint8')) > 0
        # Never borrow pixels from an adjacent opaque object.
        mask &= (labels == 0) | np.isin(labels, [i for i, owner in owners.items() if owner == index])
        ys, xs = np.where(mask & (rgba[:, :, 3] > 0))
        box = (int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1))
        l, t, r, b = box
        crop = rgba[t:b, l:r].copy()
        crop[~mask[t:b, l:r]] = 0
        results.append((Image.fromarray(crop), box, stats[ident, :4].tolist()))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--import-from', type=Path)
    args = parser.parse_args()
    source_dir = ROOT / 'assets/dinosaur-source'
    source_dir.mkdir(exist_ok=True)
    if args.import_from:
        for name, suffix in SHEETS:
            matches = list(args.import_from.glob(f'*15_57_{suffix}.png'))
            if len(matches) != 1:
                raise ValueError(f'Expected one source for {name}: {matches}')
            shutil.copy2(matches[0], source_dir / f'{name}.png')
    atlas = Image.new('RGBA', (6*480, 10*480))
    frames, sources, bubbles = [], [], []
    pose_dir = ROOT / 'assets/dinosaur-poses'
    pose_dir.mkdir(exist_ok=True)
    for sheet_index, (name, _) in enumerate(SHEETS):
        path = source_dir / f'{name}.png'
        sources.append(dict(file=f'dinosaur-source/{name}.png', sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        image = Image.open(path).convert('RGBA')
        crops = extract(image, 8 if name == 'bubbles' else 12)
        for index, (crop, box, body) in enumerate(crops):
            if name == 'bubbles':
                theme = ['working', 'blue', 'pink', 'waiting', 'success', 'idea', 'heart', 'thinking'][index]
                crop.save(ROOT / f'assets/dinosaur-bubble-{theme}.png')
                bubbles.append(dict(theme=theme, source_box=box))
                continue
            row, col = sheet_index*2+index//6, index % 6
            w, h = crop.size
            if max(w, h) > 480:
                raise ValueError((name, index, crop.size))
            atlas.paste(crop, (col*480, row*480))
            crop.save(pose_dir / f'{name}-{index+1:02d}.png')
            # Constant scale per sheet prevents face-size pumping between poses.
            factor = {'idle':1.82, 'interaction':1.96, 'work':1.96, 'walk':1.82, 'run':1.82}[name]
            bx, by, bw, bh = body
            x = 384 - (bx-box[0]+bw/2)*factor
            y = 784 - (by-box[1]+bh)*factor
            frames.append(dict(row=row, col=col, sheet=name, source_box=box,
                               source=[col*480,row*480,w,h], target=[x,y,w*factor,h*factor]))
    path = ROOT / 'assets/dinosaur-actions.png'
    atlas.save(path)
    manifest = dict(version=8,image=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    frame_size=[768,832],sources=sources,frames=frames,bubbles=bubbles)
    (ROOT/'assets/dinosaur-actions.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'Extracted {len(frames)} poses and {len(bubbles)} bubbles')


if __name__ == '__main__':
    main()
