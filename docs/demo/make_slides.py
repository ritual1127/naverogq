"""데모데이 발표 슬라이드 그림을 그린다. — 09-08 제출 영상용

    python docs/demo/make_slides.py

1920x1080 PNG 여섯 장이 이 폴더에 `S1_…` ~ `S6_…` 로 나온다. 색과 글꼴은
[`make_boards.py`](make_boards.py) 의 것을 그대로 가져다 쓴다. ③절에 쓰는
`C1_지금위치.png` · `C2_막힌것.png` 는 그쪽에서 만든다.

내용을 고칠 일이 있으면 각 함수 안의 글자만 고친다. 슬라이드에 무슨 말을
얹을지는 [`발표자료.md`](발표자료.md) 에 있다.
"""
import os

from PIL import Image

from make_boards import AMBER, CYAN, HERE, LINE, MINT, MUTED, SOFT, TEXT
from make_boards import board, bullets, font, panel


def s1_표지(path):
    img, d = board()
    d.text((96, 300), "도면을 올리면", font=font(96), fill=TEXT)
    d.text((96, 410), "빠진 것을 도면 위에 찍어 줍니다", font=font(96), fill=CYAN)
    d.text((96, 580), "전산응용기계제도기능사 실기 도면 자동 검사",
           font=font(40, False), fill=MUTED)
    d.line([(96, 720), (900, 720)], fill=LINE, width=2)
    d.text((96, 760), "네이놈  ·  구미전자공업고등학교", font=font(34), fill=SOFT)
    d.text((96, 812), "박지완 · 장우영 · 안대열 · 김승준", font=font(30, False), fill=SOFT)
    d.text((96, 986), "cadlens.onrender.com  ·  github.com/ritual1127/naverogq",
           font=font(24, False), fill=SOFT)
    img.save(path)
    return path


def s2_문제(path):
    img, d = board()
    d.text((96, 216), "5시간, 그리고 11분", font=font(88), fill=TEXT)

    panel(d, [96, 360, 1824, 560], fill="#10243a", outline=CYAN)
    d.text((136, 396), "“낸 날에는 몰랐습니다.", font=font(46, False), fill=TEXT)
    d.text((136, 462), "이틀 뒤 밤에 첨삭해 주는 분이 빨간색으로 표시해 줘서 알았습니다.”",
           font=font(46, False), fill=TEXT)
    d.text((136, 512), "— 인터뷰 대상자 (2026-08-27)", font=font(28, False), fill=SOFT)

    d.text((96, 620), "직접 만난 다섯 명이 말한 것", font=font(34), fill=MUTED)
    bullets(d, 100, 690, [
        "다섯 명 중 세 명은 자기가 아니라 남이 찾아 줘서 알았다",
        "고치는 데 11분 · 11분 · 11분 · 24분 · 1시간 25분",
        "다섯 명 전부 이미 스스로 해결을 시도했다 (넷은 돈을 썼다)",
    ], gap=64, size=40)
    d.text((96, 986), "인터뷰 5건 전문 — docs/interviews.md",
           font=font(24, False), fill=SOFT)
    img.save(path)
    return path


def s3_무엇(path):
    img, d = board()
    d.text((96, 200), "무엇을 만들었나", font=font(76), fill=TEXT)
    d.text((96, 300), "도면 한 장을 100점으로 채점하고, 깎인 자리를 도면 위에 번호로 찍습니다",
           font=font(36, False), fill=MUTED)

    panel(d, [96, 396, 940, 700])
    d.text((136, 430), "규칙 코드 60점", font=font(44), fill=MINT)
    bullets(d, 140, 500, ["검사 24개", "실격 판정 6가지", "AI 를 부르지 않는다"],
            gap=52, size=32, dot=MINT)

    panel(d, [980, 396, 1824, 700])
    d.text((1020, 430), "AI 30점", font=font(44), fill=CYAN)
    bullets(d, 1024, 500, ["투상도 선택과 배열", "조건식으로 못 적는 부분", "확실하지 않으면 사람 확인"],
            gap=52, size=32, dot=CYAN)

    panel(d, [96, 740, 1824, 880], fill="#10243a", outline=CYAN)
    d.text((136, 776), "지적은 글로만 주지 않습니다 — 도면 위 그 자리에 번호로 찍습니다",
           font=font(44), fill=CYAN)
    d.text((96, 986), "채점 배점과 검사 24개 — docs/rule_standards.md",
           font=font(24, False), fill=SOFT)
    img.save(path)
    return path


def s4_전후(path):
    img, d = board()
    d.text((96, 190), "고치면 점수가 오릅니다", font=font(76), fill=TEXT)

    for x, name, title in ((96, "도면_시연_고치기전.png", "고치기 전"),
                           (980, "도면_시연_고친뒤.png", "고친 뒤")):
        panel(d, [x, 300, x + 844, 720])
        d.text((x + 40, 326), title, font=font(36), fill=MUTED)
        shot = os.path.join(HERE, name)
        if os.path.exists(shot):
            im = Image.open(shot).convert("RGB")
            im.thumbnail((764, 320))
            img.paste(im, (x + 40 + (764 - im.width) // 2, 386))

    panel(d, [96, 760, 940, 900])
    d.text((136, 790), "41 / 60 점  ·  오작(실격)", font=font(44), fill=AMBER)
    d.text((136, 850), "지적 6건", font=font(34, False), fill=MUTED)

    panel(d, [980, 760, 1824, 900], fill="#0f2a22", outline=MINT)
    d.text((1020, 790), "55 / 60 점  ·  오작 아님", font=font(44), fill=MINT)
    d.text((1020, 850), "지적 2건  ·  검사 1초 미만", font=font(34, False), fill=MUTED)
    d.text((96, 986), "docs/demo/make_demo_pair.py 로 다시 만들 수 있습니다",
           font=font(24, False), fill=SOFT)
    img.save(path)
    return path


def s5_구조(path):
    img, d = board()
    d.text((96, 200), "어떻게 도나", font=font(76), fill=TEXT)

    boxes = [(96, "도면 업로드", "DWG · DXF"),
             (536, "도면 읽기", "DWG 면 DXF 로 변환"),
             (976, "채점", "규칙 60점 + AI 30점"),
             (1416, "결과 화면", "도면 위에 번호")]
    for x, title, sub in boxes:
        panel(d, [x, 380, x + 408, 560])
        d.text((x + 32, 412), title, font=font(40), fill=TEXT)
        d.text((x + 32, 476), sub, font=font(28, False), fill=MUTED)
    for x in (504, 944, 1384):
        d.text((x, 448), "→", font=font(44), fill=SOFT)

    panel(d, [96, 620, 1824, 800], fill="#2a1d10", outline=AMBER)
    d.text((136, 654), "밖으로 나가는 것은 하나뿐입니다", font=font(44), fill=AMBER)
    d.text((136, 716), "AI 채점 때 도면 그림 1장. 원본 파일은 나가지 않습니다. "
                       "표제란 이름은 그림에 함께 찍힙니다", font=font(30, False), fill=TEXT)

    d.text((96, 860), "올린 도면은 최대 1시간 · 최근 20건까지만 두고 지웁니다. "
                      "회원가입도 쿠키도 없습니다", font=font(32, False), fill=MUTED)
    d.text((96, 986), "아키텍처 1장 — docs/architecture.md · 공개 고지 docs/policy.md",
           font=font(24, False), fill=SOFT)
    img.save(path)
    return path


def s6_이번주(path):
    img, d = board()
    d.text((96, 190), "이번 주에 찾은 것", font=font(76), fill=TEXT)

    panel(d, [96, 310, 1824, 470], fill="#2a1d10", outline=AMBER)
    d.text((136, 344), "가지고 있던 도면 9장을 검사했더니 9장이 전부 오작이었습니다",
           font=font(46), fill=AMBER)
    d.text((136, 408), "실기 도면 두 장은 기하공차가 눈으로 보이는데도 못 찾았습니다",
           font=font(32, False), fill=TEXT)

    d.text((96, 530), "왜", font=font(38), fill=MUTED)
    d.text((96, 592), "실기 도면은 기하공차 기호를 전용 글꼴로 알파벳 한 글자를 찍어 만듭니다.",
           font=font(40, False), fill=TEXT)
    d.text((96, 652), "화면에는 기호로 보이지만 파일에 남는 글자는 그냥  b  입니다.",
           font=font(40, False), fill=TEXT)

    panel(d, [96, 750, 940, 900], fill="#0f2a22", outline=MINT)
    d.text((136, 782), "고친 뒤", font=font(32), fill=MUTED)
    d.text((136, 830), "실기 도면 2장 오작에서 빠짐", font=font(38), fill=MINT)

    panel(d, [980, 750, 1824, 900])
    d.text((1020, 782), "합성 도면 100장", font=font(32), fill=MUTED)
    d.text((1020, 830), "100장 완전 일치 — 그대로", font=font(38), fill=TEXT)

    d.text((96, 986), "합성 도면으로는 넉 달 동안 안 보였습니다 — 문제점 P17",
           font=font(24, False), fill=SOFT)
    img.save(path)
    return path


if __name__ == "__main__":
    jobs = ((s1_표지, "S1_표지.png"), (s2_문제, "S2_문제.png"),
            (s3_무엇, "S3_무엇을만들었나.png"), (s4_전후, "S4_고치기전후.png"),
            (s5_구조, "S5_어떻게도나.png"), (s6_이번주, "S6_이번주찾은것.png"))
    for fn, name in jobs:
        print(fn(os.path.join(HERE, name)))
