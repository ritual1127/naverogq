"""데모 영상 ③절에 쓰는 글자 판 두 장을 그린다.

    python docs/demo/make_boards.py

1920x1080 PNG 두 장이 이 폴더에 나온다. 색은 화면 어두운 테마와 같은 값이고,
글자는 맑은 고딕이다. 내용을 고칠 일이 있으면 아래 BOARD1 / BOARD2 만 고친다.
대본은 ../demo_script.md 의 "③ 지금 위치와 막힌 것" 절이다.
"""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = "#0c1119"
PANEL = "#141b25"
LINE = "#26303f"
TEXT = "#e9eff7"
MUTED = "#9fadc0"
SOFT = "#7d8ba0"
CYAN = "#3aa9ff"
MINT = "#2ed9a0"
AMBER = "#f0a020"

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def font(size, bold=True):
    name = "malgunbd.ttf" if bold else "malgun.ttf"
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def board():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 왼쪽 위 밝은 기운. 화면 배경과 같은 느낌을 낸다
    for i in range(260):
        a = int(16 * (1 - i / 260))
        d.line([(0, i), (W, i)], fill=(12 + a, 17 + a, 25 + a))
    d.text((96, 72), "CADLens", font=font(34), fill=CYAN)
    d.text((96, 116), "전산응용기계제도기능사 실기 도면 자동 검사",
           font=font(24, False), fill=SOFT)
    return img, d


def bullets(d, x, y, items, gap=58, size=38, color=TEXT, dot=CYAN):
    f = font(size, False)
    for line in items:
        d.ellipse([x, y + size * 0.42, x + 10, y + size * 0.42 + 10], fill=dot)
        d.text((x + 30, y), line, font=f, fill=color)
        y += gap
    return y


def panel(d, box, fill=PANEL, outline=LINE, width=2, radius=16):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def board1(path):
    img, d = board()
    d.text((96, 216), "8주 중 3주", font=font(104), fill=TEXT)

    d.text((96, 372), "돌아가는 것", font=font(40), fill=MINT)
    bullets(d, 100, 440, [
        "규칙 검사 24개 · 실격 판정 5가지",
        "AI 투상도 채점 30점",
        "지적 위치를 도면 위에 번호로 표시",
        "질문 버튼 3개 · 재검사 비교",
    ])

    panel(d, [96, 700, 1180, 848])
    d.text((132, 726), "합성 기준 도면 100장", font=font(34), fill=MUTED)
    d.text((132, 776), "완전 일치 100장 · 검출률 100%", font=font(46), fill=MINT)

    d.text((1240, 700), "안 만들기로 한 것", font=font(30), fill=SOFT)
    bullets(d, 1244, 754, ["회원가입", "3D 파싱", "다른 종목"],
            gap=44, size=30, color=SOFT, dot=LINE)

    d.line([(96, 960), (1824, 960)], fill=LINE, width=2)
    d.text((96, 986), "MVP 범위표에서 뺀 것 — docs/mvp.md",
           font=font(24, False), fill=SOFT)
    img.save(path)
    return path


def board2(path):
    img, d = board()
    d.text((96, 216), "막힌 것 하나", font=font(104), fill=AMBER)

    lines = [
        "그 100% 는 우리가 만든 도면에서 나온 숫자다.",
        "실제 수험생 도면은 두 장뿐이라",
        "현장 정확도는 아직 못 쟀다.",
    ]
    y = 396
    for line in lines:
        d.text((96, y), line, font=font(52, False), fill=TEXT)
        y += 78

    panel(d, [96, 700, 1620, 836], fill="#10243a", outline=CYAN)
    d.text((136, 742), "학생 도면을 동의받아 모으는 방법을 여쭙고 싶습니다",
           font=font(46), fill=CYAN)

    d.line([(96, 960), (1824, 960)], fill=LINE, width=2)
    d.text((96, 986), "근거 — docs/accuracy.md · 문제점 P04 · P10",
           font=font(24, False), fill=SOFT)
    img.save(path)
    return path


if __name__ == "__main__":
    print(board1(os.path.join(HERE, "C1_지금위치.png")))
    print(board2(os.path.join(HERE, "C2_막힌것.png")))
