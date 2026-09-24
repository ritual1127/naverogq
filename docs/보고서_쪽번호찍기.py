"""인쇄된 PDF 에 머리글과 쪽 번호를 찍는다.

본문을 자연 흐름으로 두었으므로 쪽 경계를 미리 알 수 없다. 그래서 인쇄한 뒤에
각 쪽의 글을 읽어 그 쪽이 속한 장·절을 알아내고 머리글을 찍는다.
표지에는 찍지 않는다.
"""
import io, json, re, sys
import fitz

src, dst = sys.argv[1], sys.argv[2]
toc_out = sys.argv[3] if len(sys.argv) > 3 else None

FONT = r"C:\Windows\Fonts\malgun.ttf"
DOC = "CADLens 사업보고서"
GRAY = (0.35, 0.35, 0.35)
CH_NAMES = {1: "사업 개요", 2: "수요 조사", 3: "시스템 개요", 4: "도면 해석",
            5: "채점 체계", 6: "정확도 검증", 7: "문제 관리", 8: "이용 현황과 지표",
            9: "준수 사항", 10: "기대효과와 향후 계획"}
KF = fitz.Font(fontfile=FONT)                 # 한글 너비를 재려면 이 글꼴로 재야 한다
RULE = (0.55, 0.55, 0.55)

CH = re.compile(r"제\s?(\d{1,2})\s?장")
SE = re.compile(r"제\s?(\d{1,2})\s?절\s*(.*)")


def headings(page):
    """글자 크기로 장·절 제목을 가려낸다.

    목차에도 '제N장 제N절'이 적혀 있어 글만 보면 구분되지 않는다. 장 제목은 15pt,
    절 제목은 12.4pt 로 찍히므로 크기로 가른다."""
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            txt = "".join(sp["text"] for sp in line["spans"]).strip()
            if not txt:
                continue
            size = max(sp["size"] for sp in line["spans"])
            if size > 14.2:
                out.append(("ch", txt, line["bbox"][1]))
            elif 11.9 < size < 13.0:
                out.append(("se", txt, line["bbox"][1]))
    return sorted(out, key=lambda x: x[2])


doc = fitz.open(src)
chapter = ""
section = ""
found = {}

for i, page in enumerate(doc):
    for kind, txt, _ in headings(page):
        flat = re.sub(r"\s+", " ", txt).strip()
        tight = flat.replace(" ", "")
        if kind == "ch":
            m = CH.search(tight)
            if m:
                no = int(m.group(1))
                chapter = "제%d장 %s" % (no, CH_NAMES.get(no, ""))
                section = ""
                found.setdefault("C%s" % m.group(1), i + 1)
        else:
            m = SE.match(tight)
            if m:
                section = flat
                cm = CH.search(chapter.replace(" ", ""))
                if cm:
                    found.setdefault("C%s-S%s" % (cm.group(1), m.group(1)), i + 1)

    if i == 0:
        continue                                   # 표지에는 찍지 않는다

    w, h = page.rect.width, page.rect.height
    top, bot = 40, h - 30
    page.draw_line((54, top + 9), (w - 54, top + 9), color=RULE, width=.5)
    page.insert_text((54, top + 5), DOC, fontfile=FONT, fontname="mg",
                     fontsize=8.2, color=GRAY)
    right = chapter if chapter else "서두"
    if section:
        right += " " + section.split()[0]
    tw = KF.text_length(right, fontsize=8.2)
    page.insert_text((w - 54 - tw, top + 5), right, fontfile=FONT,
                     fontname="mg", fontsize=8.2, color=GRAY)
    num = "- %d -" % (i + 1)
    nw = KF.text_length(num, fontsize=9.5)
    page.draw_line((54, bot - 13), (w - 54, bot - 13), color=RULE, width=.5)
    page.insert_text(((w - nw) / 2, bot), num, fontfile=FONT, fontname="mg",
                     fontsize=9.5, color=(0.15, 0.15, 0.15))

# 쪽마다 글꼴이 통째로 박히면 파일이 몇 배로 커진다. 쓴 글자만 남긴다.
try:
    doc.subset_fonts(verbose=False)
except Exception:                                    # noqa: BLE001
    pass
doc.save(dst, deflate=True, deflate_images=True, garbage=4, clean=True)
print("찍기 완료:", dst, "· 쪽 수", doc.page_count)
if toc_out:
    io.open(toc_out, "w", encoding="utf-8").write(
        json.dumps(found, ensure_ascii=False, indent=1))
    print("장·절 시작 쪽:", len(found), "건")
