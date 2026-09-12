"""데모 영상에서 글자만 나오는 두 절의 슬라이드 4장을 pptx 로 만든다.

①절 문제 30초(1·2장)와 ③절 다음 30초(3·4장)다. 가운데 ②절 시연 120초는
화면 녹화라 슬라이드가 없다.

    pip install python-pptx
    python docs/demo/make_intro.py

이 폴더에 `영상슬라이드.pptx` 가 나온다. 한 장이 15초이고 장마다 두 사람이 말한다.
1장은 우리가 겪은 일(../왜_만들었나.md), 2장은 인터뷰, 3장은 아직 못 하는 것,
4장은 4주 뒤 만들 숫자(북극성 지표)다. 장마다 머리글 한 줄과 본문 두 줄만 둔다.
숫자와 설명은 슬라이드가 아니라 말이 옮긴다.
색과 글꼴은 make_boards.py 의 것을 그대로 쓴다.

python-pptx 는 이 문서 도구에만 쓰므로 requirements.txt 에 넣지 않는다.
대본은 문제30초_대본.md 에 있다. 누가 어느 장을 말하는지는 슬라이드에 넣지
않는다 — 영상에 그대로 찍힌다.

한 줄이 상자보다 길면 파워포인트가 알아서 접어 버려서 줄 수가 밀리고 아래 글이
잘린다. 그래서 text() 가 줄 폭을 재서 넘치면 그 자리에서 멈춘다. 글자를 고칠 때
이 검사에 걸리면 폰트를 줄이지 말고 **문장을 짧은 줄로 나눈다.**
"""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

from make_boards import AMBER, BG, CYAN, HERE, LINE, MUTED, SOFT, TEXT

W, H = Inches(13.333), Inches(7.5)


def rgb(hexstr):
    return RGBColor.from_string(hexstr.lstrip("#").upper())


def em(line):
    """줄 하나의 폭을 글자 크기 배수로 어림한다. 한글은 1칸, 아스키는 반 칸."""
    return sum(0.5 if ord(c) < 0x2000 else 1.0 for c in line)


def slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(1, 0, 0, W, H)          # 1 = 사각형
    bg.fill.solid()
    bg.fill.fore_color.rgb = rgb(BG)
    bg.line.fill.background()
    bg.shadow.inherit = False
    return s


def text(s, x, y, w, runs, size=32, bold=True, color=TEXT,
         align=PP_ALIGN.LEFT, space=1.25):
    """runs 는 문자열 하나 또는 (글자, 크기, 굵기, 색) 튜플의 목록.

    상자 높이는 줄 수로 계산한다. 줄이 상자보다 넓으면 멈춘다.
    """
    if isinstance(runs, str):
        runs = [runs]
    runs = [r if isinstance(r, tuple) else (r, size, bold, color) for r in runs]

    limit = (w - 0.2) * 72          # 좌우 안쪽 여백 0.1in 씩
    for line, sz, _, _ in runs:
        assert em(line) * sz <= limit, \
            f"줄이 넘친다 ({em(line) * sz:.0f}pt > {limit:.0f}pt): {line}"

    h = sum(sz * space for _, sz, _, _ in runs) / 72 + 0.2
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    for i, (line, sz, bd, col) in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = space
        r = p.add_run()
        r.text = line
        r.font.size = Pt(sz)
        r.font.bold = bd
        r.font.name = "맑은 고딕"
        r.font.color.rgb = rgb(col)
    return box


def rule(s, x, y, w, color=LINE):
    ln = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Emu(19050))
    ln.fill.solid()
    ln.fill.fore_color.rgb = rgb(color)
    ln.line.fill.background()
    ln.shadow.inherit = False
    return ln


def quote(s, y, lines, who):
    """인용 한 덩어리. 줄은 25자 안쪽으로 끊어 넘긴다.

    출처는 인용 아래로 한 줄 더 띄운다. 붙여 놓으면 인용 마지막 줄처럼 읽힌다.
    """
    box = text(s, 0.9, y, 11.5, [(ln, 31, False, TEXT) for ln in lines])
    gap = len(lines) * 31 * 1.25 / 72 + 0.45
    text(s, 0.9, y + gap, 11.5, [(who, 20, False, SOFT)])
    return box


# ── 1장 · 0:00~0:16 · 장우영 → 김승준 ─────────────────────────────────
# 우리 얘기라 따옴표를 쓰지 않는다. 인용은 2장에만 있다
def s1(prs):
    s = slide(prs)
    text(s, 0.9, 2.05, 11.5, [("다 그린 줄 알았습니다", 55, True, TEXT)])
    rule(s, 0.9, 3.40, 1.25, CYAN)
    text(s, 0.9, 3.95, 11.5, [
        ("치수 하나, 표면거칠기 하나가", 31, False, TEXT),
        ("계속 빠져 있었습니다", 31, False, TEXT),
    ])
    return s


# ── 2장 · 0:16~0:30 · 안대열 → 박지완 ─────────────────────────────────
def s2(prs):
    s = slide(prs)
    text(s, 0.9, 2.05, 11.5, [("저희만 그런 게 아니었습니다", 55, True, AMBER)])
    rule(s, 0.9, 3.40, 1.25, AMBER)
    quote(s, 3.95, [
        "“친구가 ‘여기 베어링 자리인데",
        "거칠기 없어도 돼?’라고 해서 알았어요.”",
    ], "메카트로닉스과 2학년")
    return s


# ── 3장 · 2:30~2:45 · 안대열 → 박지완 ─────────────────────────────────
# ③ 다음 절. 워크샵 필수 두 가지 — 안 되는 것 1가지(3장)와 4주 뒤 숫자(4장)
def s3(prs):
    s = slide(prs)
    text(s, 0.9, 2.05, 11.5, [("아직 못 쟀습니다", 55, True, AMBER)])
    rule(s, 0.9, 3.40, 1.25, AMBER)
    text(s, 0.9, 3.95, 11.5, [
        ("검출률 100% 는 우리가 만든", 31, False, TEXT),
        ("합성 도면 100장에서 나온 숫자입니다", 31, False, TEXT),
    ])
    return s


# ── 4장 · 2:45~3:00 · 장우영 → 김승준 ─────────────────────────────────
def s4(prs):
    s = slide(prs)
    text(s, 0.9, 2.05, 11.5, [("4주 뒤 만들 숫자", 55, True, TEXT)])
    rule(s, 0.9, 3.40, 1.25, CYAN)
    text(s, 0.9, 3.95, 11.5, [("주간 재검사 사용자  0명 → 20명", 38, True, CYAN)])
    text(s, 0.9, 4.85, 11.5, [("고쳐서 다시 올린 사람 수입니다", 24, False, MUTED)])
    return s


if __name__ == "__main__":
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    for build in (s1, s2, s3, s4):
        build(prs)

    # 글상자가 슬라이드 밖으로 나가면 화면에서 잘린다. 그것만 본다
    for i, sld in enumerate(prs.slides, 1):
        for sh in sld.shapes:
            assert sh.left >= 0 and sh.top >= 0, (i, sh.shape_id)
            assert sh.left + sh.width <= W, (i, sh.shape_id, "오른쪽 넘침")
            assert sh.top + sh.height <= H, (i, sh.shape_id, "아래 넘침")

    out = os.path.join(HERE, "영상슬라이드.pptx")
    prs.save(out)
    print(out, "·", len(prs.slides._sldIdLst), "장")
