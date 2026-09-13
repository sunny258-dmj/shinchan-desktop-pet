"""Build runtime alpha atlas and reviewed frame geometry from generated art.

The supplied color key is absent from the character; white eyes and gray props
remain intact. Complete connected silhouettes determine frame geometry. No
runtime color-keying or external image libraries are needed.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QColor


def cutout(cell):
    cell = cell.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = cell.width(), cell.height()
    bits = cell.bits()
    stride = cell.bytesPerLine()
    magenta = cell.pixelColor(0, 0).red() > 180 and cell.pixelColor(0, 0).green() < 80
    def background(x, y):
        p = y * stride + x * 4
        r, g, b, a = bits[p:p + 4]
        if magenta:
            return a < 16 or (r > 160 and b > 160 and g < 110)
        return a < 16 or (min(r, g, b) > 160 and max(r, g, b) - min(r, g, b) < 14)
    seen = set()
    queue = deque([(x, y) for x in range(w) for y in (0, h - 1)] +
                  [(x, y) for y in range(h) for x in (0, w - 1)])
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        if not background(x, y):
            continue
        bits[y * stride + x * 4 + 3] = 0
        queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    if magenta:
        # This key is absent from the supplied blue/red/yellow costume. Remove
        # enclosed background gaps too, then unmatte antialiased black outlines.
        for y in range(h):
            for x in range(w):
                p = y * stride + x * 4
                if background(x, y):
                    bits[p + 3] = 0
        edge_pixels = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1)
                       if bits[y * stride + x * 4 + 3] and any(bits[ny * stride + nx * 4 + 3] == 0
                       for nx, ny in ((x-1,y), (x+1,y), (x,y-1), (x,y+1)))]
        for x, y in edge_pixels:
            p = y * stride + x * 4
            r, g, b, a = bits[p:p+4]
            spill = max(0, min(r, b) - g)
            if spill > 12:
                alpha = max(.01, 1 - spill / 255)
                bits[p] = max(0, min(255, round((r - spill) / alpha)))
                bits[p + 1] = max(0, min(255, round(g / alpha)))
                bits[p + 2] = max(0, min(255, round((b - spill) / alpha)))
                bits[p + 3] = round(a * alpha)
    # Remove only detached tiny flecks. Props and optional expression marks stay.
    visited = set()
    for y in range(h):
        for x in range(w):
            if (x, y) in visited or bits[y * stride + x * 4 + 3] == 0:
                continue
            group, queue = [], deque([(x, y)])
            visited.add((x, y))
            while queue:
                px, py = queue.popleft()
                group.append((px, py))
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and bits[ny * stride + nx * 4 + 3]:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
            if len(group) < 18:
                for px, py in group:
                    bits[py * stride + px * 4 + 3] = 0
    occupied = [(x, y) for y in range(h) for x in range(w) if bits[y * stride + x * 4 + 3] > 16]
    if not occupied:
        raise ValueError('Empty action cell')
    xs, ys = zip(*occupied)
    return cell, (min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = QImage(str(args.source))
    if source.isNull():
        raise ValueError('Invalid source image')
    atlas, _ = cutout(source)
    w, h, stride = atlas.width(), atlas.height(), atlas.bytesPerLine()
    bits = atlas.bits()
    visited, groups = set(), []
    for y in range(h):
        for x in range(w):
            if (x, y) in visited or bits[y * stride + x * 4 + 3] < 16:
                continue
            queue, group = deque([(x, y)]), []
            visited.add((x, y))
            while queue:
                px, py = queue.popleft()
                group.append((px, py))
                for nx, ny in ((px-1,py), (px+1,py), (px,py-1), (px,py+1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx,ny) not in visited and bits[ny * stride + nx * 4 + 3] >= 16:
                        visited.add((nx,ny))
                        queue.append((nx,ny))
            groups.append(group)
    bodies = [g for g in groups if len(g) > 1000]
    if len(bodies) != 84:
        raise ValueError(f'Expected 84 complete silhouettes, found {len(bodies)}')
    # Generated rows drift by several pixels. Connected silhouettes, rather than
    # equal grid cells, determine source rectangles so no head/foot is sliced.
    body_bounds = []
    for group in bodies:
        xs, ys = zip(*group)
        body_bounds.append((min(xs), min(ys), max(xs), max(ys)))
    combined = [list(g) for g in bodies]
    for group in groups:
        if len(group) > 1000:
            continue
        group_x, group_y = zip(*group)
        # Discard tiny ground/speed dashes between rows; they can otherwise be
        # mistaken for an expression belonging to the next character.
        if max(group_y) - min(group_y) < 5 and max(group_x) - min(group_x) > 10:
            for px, py in group:
                bits[py * stride + px * 4 + 3] = 0
            continue
        gx = sum(p[0] for p in group) / len(group)
        gy = sum(p[1] for p in group) / len(group)
        distances = [((gx-(b[0]+b[2])/2)**2 + (gy-(b[1]+b[3])/2)**2) for b in body_bounds]
        nearest = min(range(84), key=lambda i: distances[i])
        if distances[nearest] < 100**2 and gy <= body_bounds[nearest][3] + 5:
            combined[nearest].extend(group)
        else:
            for px, py in group:
                bits[py * stride + px * 4 + 3] = 0
    cells = []
    for index, group in enumerate(combined):
        xs, ys = zip(*group)
        x, y, right, bottom = min(xs), min(ys), max(xs), max(ys)
        bx, by, br, bb = body_bounds[index]
        col = min(6, int(((bx + br) / 2) / w * 7))
        row = min(11, int(((by + bb) / 2) / h * 12))
        cells.append(dict(row=row, col=col, source=[x, y, right-x+1, bottom-y+1], anchor=[(bx+br)/2, bb]))
    cells.sort(key=lambda cell: (cell['row'], cell['col']))
    if len({(c['row'], c['col']) for c in cells}) != 84:
        raise ValueError('Overlapping action assignments; review atlas layout')
    # Use ONE scale for every pose; crouching must stay shorter than standing.
    standing_height = cells[0]['source'][3]
    scale = 530 / standing_height
    # The hero landing cape is wider than standing poses. Reserve margins for
    # every pose with one shared scale instead of clipping or resizing that pose.
    extent = max(max(c['anchor'][0] - c['source'][0],
                     c['source'][0] + c['source'][2] - c['anchor'][0]) for c in cells)
    scale = min(scale, 354 / extent)
    for cell in cells:
        x, y, w, h = cell['source']
        ax, ay = cell.pop('anchor')
        cell['target'] = [round(384 + (x-ax) * scale), round(784 + (y-ay) * scale), round(w * scale), round(h * scale)]
    path = root / 'assets/reference-actions.png'
    if not atlas.save(str(path)):
        raise RuntimeError('Could not save alpha atlas')
    manifest = dict(version=5, image=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    source_size=[source.width(), source.height()], frame_size=[768, 832], frames=cells)
    (root / 'assets/reference-actions.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Built {len(cells)} reference poses: {path}')


if __name__ == '__main__':
    main()
