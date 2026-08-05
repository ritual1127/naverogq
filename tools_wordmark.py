import json
import math

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

FONT = r"C:\Windows\Fonts\seguibl.ttf"
WORD = "CADLens"
TRACK = -0.028
FLAT_TOL = 3.0


class Flatten(BasePen):
    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.contours, self.cur, self.pt = [], [], (0, 0)

    def _moveTo(self, p):
        self._flush()
        self.cur = [p]
        self.pt = p

    def _lineTo(self, p):
        self.cur.append(p)
        self.pt = p

    def _curveToOne(self, c1, c2, p):
        a = self.pt
        n = self._steps(a, c1, c2, p)
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self.cur.append((
                u * u * u * a[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p[0],
                u * u * u * a[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p[1]))
        self.pt = p

    @staticmethod
    def _steps(a, c1, c2, p):
        d = (math.dist(a, c1) + math.dist(c1, c2) + math.dist(c2, p))
        return max(3, min(24, int(math.sqrt(d / FLAT_TOL))))

    def _closePath(self):
        self._flush()

    def _flush(self):
        if len(self.cur) > 2:
            if self.cur[0] == self.cur[-1]:
                self.cur.pop()
            self.contours.append(self.cur)
        self.cur = []


def area(poly):
    s = 0.0
    for i, (x, y) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x * y2 - x2 * y
    return s / 2


def inside(pt, poly):
    x, y, hit = pt[0], pt[1], False
    for i, (ax, ay) in enumerate(poly):
        bx, by = poly[(i - 1) % len(poly)]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            hit = not hit
    return hit


def build():
    font = TTFont(FONT)
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    upem = font["head"].unitsPerEm
    hmtx = font["hmtx"]

    glyphs, cursor = [], 0.0
    for ch in WORD:
        name = cmap[ord(ch)]
        pen = Flatten(gs)
        gs[name].draw(pen)
        for c in pen.contours:
            glyphs.append([(x + cursor, y) for x, y in c])
        cursor += hmtx[name][0] + TRACK * upem
    xs = [p[0] for c in glyphs for p in c]
    ys = [p[1] for c in glyphs for p in c]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    k = 1.0 / h
    norm = [[((x - cx) * k, (y - cy) * k) for x, y in c] for c in glyphs]
    def depth(c, others):
        return sum(1 for o in others if o is not c and inside(c[0], o))

    outers = [c for c in norm if depth(c, norm) % 2 == 0]
    holes = [c for c in norm if depth(c, norm) % 2 == 1]

    shapes = []
    for o in outers:
        mine = [hl for hl in holes if inside(hl[0], o)]
        shapes.append({
            "o": [round(v, 3) for p in o for v in p],
            "h": [[round(v, 3) for p in hl for v in p] for hl in mine],
        })
    return shapes, w / h


if __name__ == "__main__":
    shapes, ratio = build()
    pts = sum(len(s["o"]) // 2 + sum(len(x) // 2 for x in s["h"]) for s in shapes)
    blob = json.dumps({"r": round(ratio, 4), "s": shapes}, separators=(",", ":"))
    print(f"윤곽 {len(shapes)}개, 점 {pts}개, {len(blob) / 1024:.1f} KB, 가로세로비 {ratio:.3f}")
    with open("wordmark.json", "w", encoding="utf-8") as fh:
        fh.write(blob)
