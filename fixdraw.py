"""결과 화면의 '수정 예시' — 빠진 지름 치수와 중심선을 도면 위 어디에 그릴지 정한다.

그림을 지어내지 않고 도면에서 읽은 원의 중심·반지름으로 계산한다. 서버가 미리보기 SVG 와
같은 좌표(viewBox)로 모양을 만들어 보내고, 화면은 그대로 얹기만 한다.

지름 치수 (KS B 0001 치수 기입)
- 지시선은 원의 중심을 향하는 사선이고 화살표 끝이 원 둘레에 닿는다. 끝에 수평선을 꺾어
  붙이고 그 위에 치수 문자를 쓴다. 수평·수직 지시선은 치수선과 헷갈려 쓰지 않는다.
- 같은 뷰의 같은 지름 원은 한 곳에만 개수를 붙여 `4-Ø6` 으로 쓴다.
- 숨은선으로만 그린 원에는 치수를 넣지 않는다. 그 형상이 보이는 뷰에 넣어야 한다.
- 치수끼리, 번호 표시와 겹치지 않고 도면 윤곽선 안에 들어가야 한다. 그 안에서 이미 그려진
  선·문자를 가장 덜 덮는 자리를 고른다. 무엇이 어디 그려져 있는지는 미리보기 SVG 를 실제로
  래스터로 그려서 본다.

중심선 (KS B 0001 선의 종류)
- 가는 1점 쇄선이 중심에서 긴 선끼리 교차하고 외형선 밖으로 3mm 나간다.
- 같은 줄의 이웃 원과 중심선이 겹치면 두 중심 사이 가운데서 끊는다.
- 쇄선 한 마디보다 짧은 작은 원은 가는 실선으로 긋는다.
"""
import math
import re

TEXT_MM = 3.5            # 도면에서 치수 문자 높이를 못 읽었을 때
TEXT_RANGE_MM = (1.8, 12.0)
LINE_MM = 0.25           # 가는 선
EXT_MM = 3.0             # 중심선이 외형선 밖으로 나가는 길이
ARROW_MM = 3.0
ARROW_HALF_DEG = 10.0
GAP_MM = 0.8             # 꺾인 수평선과 문자 사이, 문자 앞뒤 여유
PAD_MM = 0.4             # 문자 칸 위아래 여유
CLEAR_MM = 1.0           # 치수끼리 · 번호 표시와 띄울 거리
FRAME_MM = 2.0           # 윤곽선 안쪽으로 띄울 거리
ROW_MM = 0.3             # 중심이 이만큼 안에 있으면 같은 줄
# 지시선 방향(도, 반시계). 45° 쪽을 먼저 보고, 자리가 없을 때만 눕힌 각도까지 쓴다.
# 수평·수직은 치수선과 헷갈려서 아예 두지 않는다.
ANGLES = (45, 135, 225, 315,
          30, 60, 120, 150, 210, 240, 300, 330,
          15, 75, 105, 165, 195, 255, 285, 345)
ANGLE_TIERS = (4, 12)
LEADER_MM = (5, 8, 12, 17, 24, 33, 45)
MAX_ANCHORS = 4          # 같은 뷰의 같은 지름 원 중 지시선을 붙여 볼 원 수
KEEP = 80                # 치수 하나당 서로 겹치는지 따져 볼 후보 수 (덜 덮는 순)
MAX_CALLOUTS = 12
# ISO 128-20 선 종류 04(1점 쇄선): 긴 선 24d · 틈 3d · 점 0.5d · 틈 3d (d = 선 굵기)
DASH_D = (24, 3, 0.5, 3)
# 글자 폭 / 글자 크기. 화면이 textLength 로 이 폭에 맞춰 그리므로 계산한 칸을 벗어나지 않는다.
CHAR_EM = {"Ø": 0.78, ".": 0.3, "-": 0.42}
DIGIT_EM = 0.6
CAP_EM = 0.72            # 숫자 높이 / 글자 크기
AMBIGUOUS_MM = 0.6       # 화살표 끝이 다른 원 둘레와 이만큼 가까우면 어느 원인지 헷갈린다
INK_MM = 0.35            # 겹침을 볼 래스터 한 칸
# 래스터 크기 상한. 0.35mm 칸이면 A2 가 1,700px 인데, 더 큰 도면까지 그 칸으로 그리면
# 배포 서버(CPU 0.1)에서 1초가 넘는다. 자리를 고르는 데는 이 정도면 충분하다.
INK_PX = (600, 1800)


def plan(sheet, mm_per_unit, svg, tf, centers=True):
    """Work out the fix preview for one sheet, or None when there is nothing to show.

    Callouts for undimensioned holes and center marks come back separately so the caller
    can drop a part whose finding is switched off; `layer()` joins what is kept. Center
    marks are only worked out when `centers` is on (the drawing has no center lines)."""
    if not tf or not svg:
        return None
    geo = _Geometry(tf, mm_per_unit or 1.0)
    marks = _center_marks(sheet, geo) if centers else []
    # 이미 중심선이 그어진 원. 그리지 않은 이유를 화면이 한 줄로 알려 준다.
    have = sum(1 for c in sheet.get("hole_circles") or [] if c.get("centered")) if centers else 0
    groups = [g for g in sheet.get("undimensioned") or [] if g.get("view_members")]
    hidden = sorted({_format_mm(g["diameter_mm"]) for g in groups if g.get("hidden_only")}, key=float)
    groups = [g for g in groups if not g.get("hidden_only")]
    placed, skipped = [], 0
    if groups:
        placed, skipped = _callouts(groups, sheet, geo, _Ink.of(svg, geo), marks)
    if not (placed or marks or hidden or skipped):
        return None
    return {"dims": _dims_svg(placed, geo), "centers": _centers_svg(marks, geo),
            "width": max(geo.mm(LINE_MM), geo.w / 2600),
            "dim_count": len(placed), "hole_count": sum(c["count"] for c in placed),
            "center_count": len(marks), "center_have": have,
            "grouped": any(c["count"] > 1 for c in placed),
            "hidden": hidden, "skipped": skipped,
            "_callouts": placed, "_marks": marks}


def layer(p, dims=True, centers=True):
    """What the page needs: one SVG group to lay over the preview, and counts for its note.

    None when nothing would be drawn — a button that shows only a note is not a preview."""
    if not p or not (dims and p["dim_count"] or centers and p["center_count"]):
        return None
    body = (p["dims"] if dims else "") + (p["centers"] if centers else "")
    return {"svg": f'<g class="fixlayer" stroke-width="{p["width"]:.1f}">{body}</g>',
            "dims": p["dim_count"] if dims else 0, "holes": p["hole_count"] if dims else 0,
            "centers": p["center_count"] if centers else 0,
            "center_have": p.get("center_have", 0) if centers else 0,
            "grouped": dims and p["grouped"],
            "hidden": p["hidden"] if dims else [], "skipped": p["skipped"] if dims else 0}


class _Geometry:
    """DXF 좌표 -> 미리보기 SVG 좌표. y 는 SVG 에서 아래로 커진다."""

    def __init__(self, tf, k):
        self.s, self.ox, self.oy = tf["scale"], tf["off_x"], tf["off_y"]
        self.k, self.w, self.h = k, tf["view_w"], tf["view_h"]

    def point(self, x, y):
        return (x * self.s + self.ox, self.oy - y * self.s)

    def length(self, v):                  # DXF 길이 -> SVG 길이
        return v * abs(self.s)

    def mm(self, v):                      # 종이 위 mm -> SVG 길이
        return v / self.k * abs(self.s)


def _format_mm(v):
    return f"{round(v, 2):g}"


def _text_height(sheet):
    dim_mm = (sheet.get("text_sizes") or {}).get("dim_mm")
    lo, hi = TEXT_RANGE_MM
    return dim_mm if dim_mm and lo <= dim_mm <= hi else TEXT_MM


# ---------------------------------------------------------------- 이미 그려진 것

_STYLE_RE = re.compile(r"\.(C\d+)\s*\{([^}]*)\}")
_CLASS_RE = re.compile(r'class="(C\d+)"')
_BACKGROUND_RE = re.compile(r'<rect fill="[^"]*"')


def _paint(body):
    props = {k.strip(): v.strip() for k, v in
             (p.split(":", 1) for p in body.split(";") if ":" in p)}
    out = [f'stroke="{"none" if props.get("stroke", "none") == "none" else "#fff"}"',
           f'fill="{"none" if props.get("fill", "none") == "none" else "#fff"}"']
    if props.get("stroke-width", "none") != "none":
        out.append(f'stroke-width="{props["stroke-width"]}"')
    return " ".join(out)


class _Ink:
    """미리보기에 이미 그려진 선·문자·번호 표시가 어디 있는지.

    SVG 를 흑백으로 래스터링해 칸마다 잉크가 있는지 본다. MuPDF 는 SVG 의 <style> 클래스를
    읽지 않아 선이 대부분 빠지므로, 클래스를 속성으로 풀어 넣고 그린다."""

    def __init__(self, mask, geo):
        import numpy as np

        self.np = np
        self.mask = mask
        self.rows, self.cols = mask.shape
        self.sx, self.sy = self.cols / geo.w, self.rows / geo.h
        self.px_mm = (geo.w / self.cols) / geo.mm(1.0)
        sat = np.zeros((self.rows + 1, self.cols + 1), dtype=np.int32)
        sat[1:, 1:] = mask.cumsum(0, dtype=np.int32).cumsum(1, dtype=np.int32)
        self.sat = sat
        self.mm_per_unit = 1.0 / geo.mm(1.0)

    @classmethod
    def of(cls, svg, geo):
        import numpy as np

        try:
            import pymupdf

            styles = {name: _paint(body) for name, body in _STYLE_RE.findall(svg)}
            flat = _CLASS_RE.sub(lambda m: styles.get(m.group(1), 'stroke="#fff"'), svg)
            flat = _BACKGROUND_RE.sub('<rect fill="#000"', flat, count=1)
            page = pymupdf.open(stream=flat.encode(), filetype="svg")[0]
            want = min(INK_PX[1], max(INK_PX[0], max(geo.w, geo.h) / geo.mm(INK_MM)))
            zoom = want / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom),
                                  colorspace=pymupdf.csGRAY, alpha=False)
            mask = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width) > 0
        except Exception as e:                                # noqa: BLE001
            # 겹침을 못 봐도 치수끼리·번호 표시와 안 겹치는 것은 그대로 지킨다
            print(f"[fix] 미리보기 래스터 실패: {type(e).__name__}: {e}", flush=True)
            mask = np.zeros((1, 1), dtype=bool)
        return cls(mask, geo)

    def area(self, box):
        """Ink inside an SVG box, in mm² of paper."""
        x0, y0, x1, y1 = box
        c0 = min(self.cols, max(0, int(math.floor(x0 * self.sx))))
        c1 = min(self.cols, max(0, int(math.ceil(x1 * self.sx))))
        r0 = min(self.rows, max(0, int(math.floor(y0 * self.sy))))
        r1 = min(self.rows, max(0, int(math.ceil(y1 * self.sy))))
        s = self.sat
        return float(s[r1, c1] - s[r0, c1] - s[r1, c0] + s[r0, c0]) * self.px_mm ** 2

    def along(self, a, b):
        """Ink crossed by a segment, in mm of paper."""
        np = self.np
        n = int(max(abs(b[0] - a[0]) * self.sx, abs(b[1] - a[1]) * self.sy)) + 1
        xs = (np.linspace(a[0], b[0], n) * self.sx).astype(np.int64)
        ys = (np.linspace(a[1], b[1], n) * self.sy).astype(np.int64)
        keep = (xs >= 0) & (xs < self.cols) & (ys >= 0) & (ys < self.rows)
        hits = int(self.mask[ys[keep], xs[keep]].sum())
        return hits * math.hypot(b[0] - a[0], b[1] - a[1]) * self.mm_per_unit / n


# ---------------------------------------------------------------- 도형 계산

def _grow(box, d):
    return (box[0] - d, box[1] - d, box[2] + d, box[3] + d)


def _inside(box, frame):
    return (frame[0] <= box[0] and box[2] <= frame[2]
            and frame[1] <= box[1] and box[3] <= frame[3])


def _boxes_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _point_segment(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    length2 = ax * ax + ay * ay
    t = 0.0 if not length2 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / length2))
    return math.hypot(a[0] + ax * t - p[0], a[1] + ay * t - p[1])


def _cross(p1, p2, q1, q2):
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    return d1 * d2 < 0 and d3 * d4 < 0


def _segment_distance(p1, p2, q1, q2):
    if _cross(p1, p2, q1, q2):
        return 0.0
    return min(_point_segment(p1, q1, q2), _point_segment(p2, q1, q2),
               _point_segment(q1, p1, p2), _point_segment(q2, p1, p2))


def _segment_hits_box(a, b, box):
    x0, y0, x1, y1 = box
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1 or x0 <= b[0] <= x1 and y0 <= b[1] <= y1:
        return True
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return any(_cross(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def _box_near_point(box, p, r):
    dx = max(box[0] - p[0], 0.0, p[0] - box[2])
    dy = max(box[1] - p[1], 0.0, p[1] - box[3])
    return math.hypot(dx, dy) < r


# ---------------------------------------------------------------- 지름 치수

def _callouts(groups, sheet, geo, ink, marks):
    h = geo.mm(_text_height(sheet))
    clear = geo.mm(CLEAR_MM)
    view = (geo.mm(FRAME_MM), geo.mm(FRAME_MM), geo.w - geo.mm(FRAME_MM), geo.h - geo.mm(FRAME_MM))
    border = sheet.get("border_box_mm")
    frames = [view]
    if border and len(border) == 4:
        (ax, ay), (bx, by) = (geo.point(border[0] / geo.k, border[1] / geo.k),
                              geo.point(border[2] / geo.k, border[3] / geo.k))
        inner = _grow((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)), -geo.mm(FRAME_MM))
        if inner[0] < inner[2] and inner[1] < inner[3]:
            frames.insert(0, inner)
    badges = [(geo.point(*g["badge"][:2]), geo.length(g["badge"][2]) + clear)
              for g in sheet.get("undimensioned") or [] if g.get("badge")]
    mark_lines = [line for m in marks for line in m["lines"]]
    circles = [(geo.point(x, y), geo.length(r)) for x, y, r in sheet.get("outline_circles") or []]

    ordered = sorted(groups, key=lambda g: -g["diameter_mm"])
    todo = []
    for g in ordered[:MAX_CALLOUTS]:
        count = len(g["view_members"])
        text = (f"{count}-" if count > 1 else "") + "Ø" + _format_mm(g["diameter_mm"])
        cands = (_candidates(g, text, h, geo, ink, frames, badges, mark_lines, circles)
                 # 윤곽선 가까이라 안에 둘 자리가 없으면 윤곽선 밖 여백이라도 쓴다
                 or _candidates(g, text, h, geo, ink, frames[-1:], badges, mark_lines, circles))
        todo.append((g, text, count, cands[:KEEP]))
    skipped = len(ordered) - len(todo)

    placed = []
    while todo:
        # 둘 자리가 가장 적게 남은 치수부터 놓는다. 큰 원이 먼저 좋은 자리를 가져가 작은 원이
        # 갈 곳을 잃는 일을 막는다.
        options = [(item, [c for c in item[3] if _fits(c, placed, clear)]) for item in todo]
        item, ok = min(options, key=lambda o: (len(o[1]), -o[0][0]["diameter_mm"]))
        todo.remove(item)
        if not ok:
            skipped += 1
            continue
        g, text, count, _ = item
        placed.append({**ok[0], "text": text, "count": count, "diameter_mm": g["diameter_mm"]})
    return placed, skipped


def _candidates(g, text, h, geo, ink, frames, badges, mark_lines, circles):
    r = geo.length(g["dxf_r"])
    font = h / CAP_EM
    width = sum(CHAR_EM.get(ch, DIGIT_EM) for ch in text) * font
    gap, pad = geo.mm(GAP_MM), geo.mm(PAD_MM)
    near = geo.mm(AMBIGUOUS_MM)
    out = []
    for rank, (x, y) in enumerate(g["view_members"][:MAX_ANCHORS]):
        center = geo.point(x, y)
        # 윤곽선 안의 원은 윤곽선 안에 쓴다. 윤곽선 밖에 그린 뷰의 원만 미리보기 전체를 쓴다.
        frame = frames[0] if _inside((*center, *center), frames[0]) else frames[-1]
        others = [(c, cr) for c, cr in circles
                  if abs(cr - r) > near or math.hypot(c[0] - center[0], c[1] - center[1]) > near]
        for turn, angle in enumerate(ANGLES):
            ux, uy = math.cos(math.radians(angle)), -math.sin(math.radians(angle))
            tip = (center[0] + ux * r, center[1] + uy * r)
            ambiguous = any(abs(math.hypot(tip[0] - c[0], tip[1] - c[1]) - cr) < near
                            for c, cr in others)
            for length_mm in LEADER_MM:
                reach = r + geo.mm(length_mm)
                elbow = (center[0] + ux * reach, center[1] + uy * reach)
                side = 1 if ux > 0 else -1
                end = (elbow[0] + side * (width + 2 * gap), elbow[1])
                x0 = elbow[0] + gap if side > 0 else elbow[0] - gap - width
                base = elbow[1] - gap
                box = (x0, base - h - pad, x0 + width, base + pad)
                bounds = (min(tip[0], elbow[0], end[0], box[0]), min(tip[1], elbow[1], box[1]),
                          max(tip[0], elbow[0], end[0], box[2]), max(tip[1], elbow[1], box[3]))
                if not _inside(bounds, frame):
                    continue
                legs = ((tip, elbow), (elbow, end))
                if any(_box_near_point(box, bc, br) or _point_segment(bc, *legs[0]) < br
                       or _point_segment(bc, *legs[1]) < br for bc, br in badges):
                    continue
                if any(_segment_hits_box(a, b, box) for a, b in mark_lines):
                    continue
                # 원 둘레 바로 옆은 그 원 자신의 선이라 지시선 잉크에서 뺀다
                start = (tip[0] + ux * gap, tip[1] + uy * gap)
                tier = sum(turn >= t for t in ANGLE_TIERS)
                cost = (ink.area(_grow(box, pad)) * 6 + ink.along(elbow, end) * 3
                        + ink.along(start, elbow) + length_mm * 0.15
                        + tier + rank * 2.0 + (15 if ambiguous else 0))
                out.append({"cost": cost, "tip": tip, "elbow": elbow, "end": end, "box": box,
                            "legs": legs, "angle": angle, "base": base, "text_x": x0,
                            "width": width, "font": font, "center": center, "radius": r})
    out.sort(key=lambda c: c["cost"])
    return out


def _fits(c, placed, clear):
    box = _grow(c["box"], clear)
    for q in placed:
        qbox = _grow(q["box"], clear)
        if _boxes_overlap(box, q["box"]):
            return False
        if any(_segment_hits_box(a, b, qbox) for a, b in c["legs"]):
            return False
        if any(_segment_hits_box(a, b, box) for a, b in q["legs"]):
            return False
        if any(_segment_distance(a, b, qa, qb) < clear for a, b in c["legs"] for qa, qb in q["legs"]):
            return False
    return True


# ---------------------------------------------------------------- 중심선

def _center_marks(sheet, geo):
    """중심선이 없는 원에만 그린다. 이미 그어 둔 원 위에 덧그리면 도면만 지저분해진다."""
    marks = []
    for c in sheet.get("hole_circles") or []:
        if c.get("centered"):
            continue
        cx, cy = geo.point(c["x"], c["y"])
        reach = geo.length(c["r"]) + geo.mm(EXT_MM)
        marks.append({"c": (cx, cy), "r": geo.length(c["r"]),
                      "left": cx - reach, "right": cx + reach, "up": cy - reach, "down": cy + reach})
    row = geo.mm(ROW_MM)
    for i, a in enumerate(marks):
        for b in marks[i + 1:]:
            _split(a, b, 1, "left", "right", row)
            _split(a, b, 0, "up", "down", row)
    for m in marks:
        cx, cy = m["c"]
        m["lines"] = (((m["left"], cy), (m["right"], cy)), ((cx, m["up"]), (cx, m["down"])))
    return marks


def _split(a, b, axis, lo, hi, row):
    """같은 줄의 두 원에서 중심선이 겹치면 두 중심 사이 가운데서 끊는다.

    axis 는 줄을 가르는 좌표(가로줄이면 y, 세로줄이면 x)다. 가운데가 어느 한 원의 안쪽이면
    (원끼리 겹치면) 끊으면 그 원 밖으로 중심선이 안 나가므로 그대로 둔다."""
    if abs(a["c"][axis] - b["c"][axis]) > row:
        return
    along = 1 - axis
    first, second = (a, b) if a["c"][along] <= b["c"][along] else (b, a)
    if first[hi] <= second[lo]:
        return
    mid = (first["c"][along] + second["c"][along]) / 2
    if first["c"][along] + first["r"] <= mid <= second["c"][along] - second["r"]:
        first[hi] = min(first[hi], mid)
        second[lo] = max(second[lo], mid)


# ---------------------------------------------------------------- SVG

def _n(v):
    return f"{v:.1f}"


def _dims_svg(placed, geo):
    parts = []
    for c in placed:
        tip, elbow, end = c["tip"], c["elbow"], c["end"]
        parts.append(f'<path d="M{_n(tip[0])} {_n(tip[1])}L{_n(elbow[0])} {_n(elbow[1])}'
                     f'L{_n(end[0])} {_n(end[1])}"/>')
        ux, uy = math.cos(math.radians(c["angle"])), -math.sin(math.radians(c["angle"]))
        length = min(geo.mm(ARROW_MM), 0.9 * c["font"] * CAP_EM)
        half = length * math.tan(math.radians(ARROW_HALF_DEG))
        bx, by = tip[0] + ux * length, tip[1] + uy * length
        parts.append(f'<path class="fixfill" d="M{_n(tip[0])} {_n(tip[1])}'
                     f'L{_n(bx - uy * half)} {_n(by + ux * half)}'
                     f'L{_n(bx + uy * half)} {_n(by - ux * half)}Z"/>')
        parts.append(f'<text x="{_n(c["text_x"])}" y="{_n(c["base"])}" font-size="{_n(c["font"])}" '
                     f'textLength="{_n(c["width"])}" lengthAdjust="spacingAndGlyphs" '
                     f'style="stroke-width:{_n(c["font"] * 0.16)}">{c["text"]}</text>')
    return "".join(parts)


def _centers_svg(marks, geo):
    dash = " ".join(_n(geo.mm(v * LINE_MM)) for v in DASH_D)
    long_dash = geo.mm(DASH_D[0] * LINE_MM)
    parts = []
    for m in marks:
        cx, cy = m["c"]
        # 중심에서 바깥으로 따로 그어 긴 선끼리 중심에서 만나게 한다
        for x, y in ((m["left"], cy), (m["right"], cy), (cx, m["up"]), (cx, m["down"])):
            dashed = f' stroke-dasharray="{dash}"' if math.hypot(x - cx, y - cy) > long_dash else ""
            parts.append(f'<path class="fixcenter" d="M{_n(cx)} {_n(cy)}L{_n(x)} {_n(y)}"{dashed}/>')
    return "".join(parts)
