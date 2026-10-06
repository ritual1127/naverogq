# 발표 슬라이드에 넣을 사진 — capture 가 3배 해상도로 찍은 실제 화면에서 핵심만 잘라 다듬는다.
#   python stills.py        (capture.js · capture2.js 를 먼저 돌려 cap/ · cap2/ 가 있어야 한다)
# 손대는 것은 셋뿐이다 — 자르기, 어두운 도면 칸의 가는 선 굵히기(줄였을 때 선이 사라지지 않게),
# 가리킬 단추에 파란 테두리. 화면 속 글자나 판정은 그대로 둔다. 남의 도면(실제 수험생 도면)은 쓰지 않는다.
import os
from collections import Counter
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "..", "presenter", "img")
K = 3                                  # 찍은 배율 — 앱 화면 1px = 그림 3px
ACCENT = (42, 120, 214)                # 발표 슬라이드의 강조색 --accent


def box(x0, y0, x1, y1):
    return tuple(round(v * K) for v in (x0, y0, x1, y1))


def thicken(im, area, size=3):
    """도면 칸(어두운 바탕)의 밝은 선을 size px 만큼 굵힌다. 칸 밖의 화면은 건드리지 않는다."""
    part = im.crop(area).filter(ImageFilter.MaxFilter(size))
    im.paste(part, area[:2])
    return im


def ring(im, area, pad=10, width=7, radius=40):
    """가리킬 곳에 파란 테두리 — 화면 위에 덧그린 표시라는 게 보이게 바깥으로 띄운다."""
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = area
    d.rounded_rectangle((x0 - pad, y0 - pad, x1 + pad, y1 + pad), radius=radius + pad, outline=ACCENT, width=width)
    return im


def save(im, name, width):
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(os.path.join(OUT, name), optimize=True)
    print(name, im.size)


# 표지 옆 — 수정 예시를 켠 결과 화면의 도면 미리보기. 빠진 Ø20.5 에 번호 1, 초록 치수
res = Image.open(os.path.join(HERE, "cap", "fix_base.png")).convert("RGB")
thicken(res, box(80, 220, 893, 829))
save(res.crop(box(80, 157, 893, 829)), "result.png", 1400)

# 안 된 것 — 첫 화면의 제목과 단추 둘. '예제로 먼저 보기' 에 테두리
home = Image.open(os.path.join(HERE, "cap", "home_base.png")).convert("RGB")
ring(home, box(375, 466, 570, 519), pad=8 * K, width=4 * K, radius=27 * K)
save(home.crop(box(178, 158, 842, 592)), "home.png", 1280)

# 실제 도면 장 — 공개 정확도 페이지의 '실제 수험생 도면' 카드만. 한계 문장("한 학생의 연습 도면")까지 같이 보인다.
# 카드는 화면이 파란 테두리로 강조해 둔 것이라 그 테두리 선(파란 점이 세로 · 가로로 길게 늘어선 줄)으로 자리를 찾는다.
acc = Image.open(os.path.join(HERE, "cap2", "accuracy.png")).convert("RGB")      # 2배로 찍은 전체 페이지
px = acc.load()
blue = [(x, y) for y in range(700, 1500) for x in range(600, 1700)
        if px[x, y][0] < 120 and 100 < px[x, y][1] < 190 and px[x, y][2] > 200]
cols = Counter(x for x, _ in blue)
rows = Counter(y for _, y in blue)
xs = [x for x, n in cols.items() if n > 200]
ys = [y for y, n in rows.items() if n > 400]
pad = 14
card = acc.crop((min(xs) - pad, min(ys) - pad, max(xs) + pad + 1, max(ys) + pad + 1)).convert("RGBA")
mask = Image.new("L", card.size, 0)                          # 카드 바깥(페이지 바탕)은 투명하게 — 카드만 뜬다
ImageDraw.Draw(mask).rounded_rectangle((pad - 3, pad - 3, card.width - pad + 2, card.height - pad + 2), radius=46, fill=255)
card.putalpha(mask)
save(card, "accuracy.png", card.width)
