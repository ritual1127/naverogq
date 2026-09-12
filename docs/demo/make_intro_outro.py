"""영상 커버, 시연 시작 화면, 마지막 인사 화면.

    python docs/demo/make_intro_outro.py

`커버.png`(1280x720) · `시연시작.png` · `감사합니다.png` 가 이 폴더에 나온다. 색과 글꼴은
make_boards.py 것을 그대로 쓴다.
"""
import os

from PIL import Image, ImageDraw

from make_boards import BG, CYAN, HERE, LINE, MINT, MUTED, SOFT, TEXT, board, font, panel


LOGO = os.path.join(os.path.dirname(HERE), os.pardir, "static", "logo-readme.png")


def 로고(img, xy, size):
    """왼쪽 위 로고. 파일이 없으면 글자로 대신한다."""
    try:
        mark = Image.open(LOGO).convert("RGBA").resize((size, size), Image.LANCZOS)
        img.paste(mark, xy, mark)
        return xy[0] + size + 18
    except Exception:
        return xy[0]


def 커버(path):
    """유튜브 썸네일 1280x720. 글자 폭을 재서 배치한다 — 눈대중으로 두면
    배지 밖으로 글자가 삐져나온다."""
    W, H = 1280, 720
    M = 72                                     # 사방 여백
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for i in range(220):                       # 위쪽 밝은 기운
        a = int(14 * (1 - i / 220))
        d.line([(0, i), (W, i)], fill=(12 + a, 17 + a, 25 + a))

    def wide(text, f):
        box = d.textbbox((0, 0), text, font=f)
        return box[2] - box[0], box[3] - box[1]

    def 가운데(text, f, cx, cy, fill):
        box = d.textbbox((0, 0), text, font=f)
        d.text((cx - (box[2] - box[0]) / 2 - box[0],
                cy - (box[3] - box[1]) / 2 - box[1]), text, font=f, fill=fill)

    # 머리 — 로고와 이름을 같은 중심선에 둔다
    LOGO_SIZE, top = 60, M - 6
    x = 로고(img, (M, top), LOGO_SIZE)
    f_name, f_sub = font(34), font(19, False)
    nh = wide("CADLens", f_name)[1]
    d.text((x, top + 4), "CADLens", font=f_name, fill=CYAN)
    d.text((x, top + 4 + nh + 12), "전산응용기계제도기능사 실기 도면 자동 검사",
           font=f_sub, fill=SOFT)

    # 시연 영상 배지 — 글자 폭을 재서 테두리를 그린다
    f_badge = font(24)
    label = "시연 영상"
    lw, lh = wide(label, f_badge)
    bx, by, bh = M, 208, 52
    bw = 26 + 22 + 14 + lw + 26                # 여백 + 삼각형 + 사이 + 글자 + 여백
    panel(d, [bx, by, bx + bw, by + bh], fill="#10243a", outline=CYAN, radius=bh // 2)
    tri = by + bh / 2
    d.polygon([(bx + 26, tri - 11), (bx + 26, tri + 11), (bx + 48, tri)], fill=CYAN)
    d.text((bx + 26 + 22 + 14, tri - lh / 2 - 4), label, font=f_badge, fill=TEXT)

    # 문구 — 두 줄. 세로로 가운데 가깝게 둔다
    f_big = font(92)
    d.text((M, 300), "내기 전에", font=f_big, fill=TEXT)
    d.text((M, 300 + 118), "빠진 것 찾기", font=f_big, fill=CYAN)
    d.line([(M, 566), (M + 470, 566)], fill=LINE, width=2)
    d.text((M, 594), "올리면 도면 위에 번호로 찍어 줍니다",
           font=font(26, False), fill=MUTED)

    # 오른쪽 — 실제 화면의 그 장면. 선과 글자가 겹치지 않게 자리를 나눈다
    px0, py0, px1, py1 = 728, 150, W - M, H - M
    panel(d, [px0, py0, px1, py1], fill="#0f1620")
    cap_y = py1 - 62                           # 캡션 띠. 선은 여기까지 안 내려온다
    cx, cy, r = (px0 + px1) // 2 - 20, (py0 + cap_y) // 2, 92
    d.line([(px0 + 40, cy), (px1 - 40, cy)], fill="#5a6879", width=2)
    d.line([(cx, py0 + 40), (cx, cap_y - 18)], fill="#5a6879", width=2)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="#e5484d", width=5)

    bxx, byy, br = px1 - 84, py0 + 84, 56      # 번호 배지 — 패널 안에 완전히 들어온다
    d.line([(cx + 66, cy - 66), (bxx - 40, byy + 40)], fill="#e5484d", width=4)
    d.ellipse([bxx - br, byy - br, bxx + br, byy + br], fill="#e5484d")
    가운데("1", font(74), bxx, byy, "#ffffff")

    d.line([(px0 + 28, cap_y - 6), (px1 - 28, cap_y - 6)], fill=LINE, width=1)
    d.text((px0 + 28, cap_y + 10), "치수 누락 1곳 · 그 자리에 번호",
           font=font(22, False), fill=SOFT)
    img.save(path)
    return path


def 시연시작(path):
    img, d = board()
    d.text((96, 292), "지금부터 실제 화면입니다", font=font(96), fill=TEXT)
    d.text((96, 412), "도면을 올리고, 고치고, 다시 올립니다", font=font(72), fill=CYAN)

    d.line([(96, 560), (1824, 560)], fill=LINE, width=2)

    cards = [
        ("올린다", "DWG · DXF · 가입 없음"),
        ("찾는다", "빠진 것을 도면 위에 번호로"),
        ("고친다", "다시 올려 전과 비교"),
    ]
    x = 96
    for title, sub in cards:
        panel(d, [x, 620, x + 540, 800])
        d.text((x + 40, 662), title, font=font(52), fill=TEXT)
        d.text((x + 40, 730), sub, font=font(30, False), fill=MUTED)
        x += 578

    d.text((96, 900), "naverogq.onrender.com", font=font(32), fill=SOFT)
    img.save(path)
    return path


def 감사합니다(path):
    img, d = board()
    d.text((96, 330), "감사합니다", font=font(140), fill=TEXT)
    d.text((96, 520), "도면을 올리면 빠진 것을 도면 위에 찍어 줍니다",
           font=font(52, False), fill=CYAN)

    d.line([(96, 640), (1180, 640)], fill=LINE, width=2)
    d.text((96, 686), "네이놈  ·  구미전자공업고등학교", font=font(36), fill=TEXT)
    d.text((96, 744), "박지완 · 장우영 · 안대열 · 김승준", font=font(32, False), fill=MUTED)

    panel(d, [1240, 300, 1824, 800])
    d.text((1290, 348), "지금 쓸 수 있습니다", font=font(38), fill=MINT)
    lines = [
        ("naverogq.onrender.com", 34, TEXT),
        ("무료 · 가입 없음", 28, MUTED),
        ("", 20, MUTED),
        ("github.com/ritual1127/naverogq", 28, TEXT),
        ("코드와 기록 전부 공개", 26, MUTED),
        ("", 20, MUTED),
        ("도면은 한 시간 뒤 지웁니다", 26, SOFT),
    ]
    y = 430
    for text, size, color in lines:
        if text:
            d.text((1290, y), text, font=font(size, size > 30), fill=color)
        y += size + 26
    img.save(path)
    return path


if __name__ == "__main__":
    for fn, name in ((커버, "커버.png"), (시연시작, "시연시작.png"),
                     (감사합니다, "감사합니다.png")):
        print(fn(os.path.join(HERE, name)))
