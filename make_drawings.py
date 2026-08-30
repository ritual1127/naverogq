"""공개문제 형식을 본뜬 합성 도면을 찍어 낸다.

**사람이 그린 도면이 아니다.** 실기 공개문제(동력전달장치류)의 *형식* —
A3 도면틀 · 표제란 · 부품란 · 제3각법 · 정면/평면/측면과 단면 · 끼워맞춤 ·
표면거칠기 · 데이텀과 기하공차 · 주서 — 을 코드로 만든 것이다.
`bench.py` 의 기준 도면 18장이 너무 단순해서 늘린 것이고,
[P04](plan/문제점/P04-표본도면.md) 의 "실제 수험생 도면" 을 대신하지 못한다.

기준 도면(`ok`)은 우리 검사 24개에서 지적이 0건이 되게 맞춰 놨다.
**그건 우리 검사 기준 만점이지 실기 채점 100점이 아니다.** 투상도 선택이
과제와 맞는지(30점)는 사람과 AI 가 보는 것이고 여기서 보증하지 않는다.

    python make_drawings.py            # 합성도면/ 에 100장 + labels.json
    python bench.py 합성도면/labels.json
"""
import argparse
import json
import math
import os
import random

import ezdxf

SHEET = (420.0, 297.0)          # A3, exam.REQUIRED_SHEET
NOTES = ("1. 일반공차 - 가) 가공부: KS B ISO 2768-m\n"
         "         나) 주조부: KS B ISO 8062-CT12\n"
         "2. 도시되고 지시없는 모떼기는 1x45°, 필렛과 라운드는 R3\n"
         "3. 일반 모떼기는 0.2x45°\n"
         "4. 표면거칠기 기호 비교표 참조 (다듬질 정도 w/x/y/z)\n"
         "5. 전체 열처리 HRC 50±2")

# 공개문제에 자주 나오는 조합. 부품마다 재질과 끼워맞춤이 다르다.
ASSEMBLIES = [
    ("동력전달장치", [("본체", "GC250"), ("축", "SCM415"),
                      ("커버", "GC250"), ("스퍼기어", "SC480")]),
    ("드릴지그", [("지그본체", "GC250"), ("부시", "SM45C"),
                  ("고정판", "SM45C"), ("핸들", "SM45C")]),
    ("바이스", [("바이스본체", "GC250"), ("이동조", "SC480"),
                ("리드스크류", "SM45C"), ("조임핸들", "SM45C")]),
    ("기어박스", [("박스본체", "GC250"), ("피니언축", "SCM415"),
                  ("베어링커버", "GC250"), ("헬리컬기어", "SC480")]),
]
FITS = ["H7", "js5", "g6", "h6", "N9", "K7", "js6", "H8"]
ROUGH = ["w", "x", "y", "z"]


def _sheet(doc, msp, scale="1:1"):
    """도면틀 · 중심마크 · 제3각법 기호 · 척도."""
    w, h = SHEET
    msp.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True)
    msp.add_lwpolyline([(10, 10), (w - 10, 10), (w - 10, h - 10), (10, h - 10)],
                       close=True)
    # 제3각법 기호 — 이게 없으면 채점자가 각법을 못 본다
    msp.add_text("제3각법", height=3.5).set_placement((300, 24))
    msp.add_circle((330, 25), 4)
    msp.add_circle((330, 25), 2)
    msp.add_text(f"척도 {scale}", height=3.5).set_placement((355, 24))


def _title_block(doc, msp, part_no, material, name):
    if "TITLE" not in doc.blocks:
        blk = doc.blocks.new("TITLE")
        for i, tag in enumerate(("PART_NUMBER", "MATERIAL", "DESIGNER",
                                 "DESCRIPTION")):
            blk.add_attdef(tag, (0, -i * 5))
    msp.add_auto_blockref("TITLE", (300, 18), {
        "PART_NUMBER": str(part_no), "MATERIAL": material,
        "DESIGNER": "", "DESCRIPTION": name})
    # 표제란 칸 선
    msp.add_lwpolyline([(295, 12), (410, 12), (410, 40), (295, 40)], close=True)


def _part_list(msp, parts):
    """부품란 — 품번 · 품명 · 재질 · 수량. 칸마다 문자를 따로 쓴다.
    한 줄로 이어 쓰면 우리 파서가 주서로 오인한다(실제 CAD 도 칸마다 문자다)."""
    top = 60.0
    msp.add_lwpolyline([(295, 40), (410, 40), (410, top), (295, top)], close=True)
    cols = (297.0, 312.0, 350.0, 385.0)
    for x, head in zip(cols, ("품번", "품명", "재질", "수량")):
        msp.add_text(head, height=2.5).set_placement((x, top - 4))
    for i, (name, mat) in enumerate(parts):
        y = top - 9 - i * 4
        for x, cell in zip(cols, (str(i + 1), name, mat, "1")):
            msp.add_text(cell, height=2.5).set_placement((x, y))


def _view(msp, ox, oy, w, h, *, holes, label, section=False, rng=None):
    """부품 하나의 뷰. 외형 · 구멍 · 중심선 · (단면이면) 해칭과 문자."""
    msp.add_lwpolyline([(ox, oy), (ox + w, oy), (ox + w, oy + h), (ox, oy + h)],
                       close=True)
    msp.add_text(label, height=3.5).set_placement((ox, oy + h + 3))
    for cx, cy, dia in holes:
        msp.add_circle((cx, cy), dia / 2)
        # 중심선 — 원마다 넣는다. 하나라도 빠지면 KS 위반이다
        msp.add_line((cx - dia, cy), (cx + dia, cy), dxfattribs={"layer": "CENTER"})
        msp.add_line((cx, cy - dia), (cx, cy + dia), dxfattribs={"layer": "CENTER"})
    if section:
        for i in range(6):
            x = ox + 4 + i * (w - 8) / 6
            msp.add_line((x, oy + 2), (x + 8, oy + h - 2),
                         dxfattribs={"layer": "HATCH"})


def _dim_linear(msp, p1, p2, base, text):
    msp.add_linear_dim(base=base, p1=p1, p2=p2, text=text).render()


def _dim_dia(msp, center, dia, text):
    msp.add_diameter_dim(center=center, radius=dia / 2, angle=45, text=text).render()


def _surface_symbol(msp, x, y, value):
    """√ 기호 하나. 값이 비면 EX_SURFACE_EMPTY 가 된다."""
    r = 2.4
    apex = (x, y - r / math.sin(math.radians(30)))
    for ang in (60, 120):
        a = math.radians(ang)
        msp.add_line(apex, (apex[0] + 12 * math.cos(a), apex[1] + 12 * math.sin(a)))
    msp.add_text(f"√{value}", height=3.5).set_placement((x + 2, y))


def _fcf(msp, x, y, symbol, tol, datums):
    """기하공차 프레임. 데이텀이 비면 EX_FCF_NO_DATUM 이다."""
    body = f"{symbol}%%v{tol}"
    if datums:
        body += "%%v" + "%%v".join(datums)
    msp.add_text(body, height=3.5).set_placement((x, y))


def _datum(msp, x, y, letter):
    msp.add_text(f"[{letter}]", height=3.5).set_placement((x, y))
    msp.add_lwpolyline([(x, y), (x + 6, y), (x + 6, y + 6), (x, y + 6)], close=True)


def build(seed=0, *, defect=None, out_dir=".", name=None):
    """도면 한 장. `defect` 가 None 이면 우리 검사 24개에서 지적 0건이 목표다."""
    rng = random.Random(seed)
    asm_name, parts = ASSEMBLIES[seed % len(ASSEMBLIES)]
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4                       # mm
    doc.layers.add("CENTER", linetype="CENTER")
    doc.layers.add("HATCH")
    msp = doc.modelspace()

    # 표제란·도면양식이 통째로 없는 변형은 도면틀도 그리지 않는다
    if defect != "no_title":
        _sheet(doc, msp)
    if defect != "no_title":
        _title_block(doc, msp, 1, parts[0][1], asm_name)
        _part_list(msp, parts)

    # 네 부품을 사분면에 놓는다. 정면 · 평면 · 측면 · 단면 A-A
    base_w = 70 + rng.randrange(0, 30, 5)
    base_h = 50 + rng.randrange(0, 20, 5)
    dia_a = rng.choice([17.0, 20.0, 25.0, 30.0])
    dia_b = rng.choice([35.0, 40.0, 47.0, 52.0])
    views = [
        (30, 190, base_w, base_h, "정면도", False),
        (140, 190, base_w, base_h, "평면도", False),
        (30, 110, base_w, base_h, "우측면도", False),
        (140, 110, base_w, base_h, "단면도 A-A (1:1)", True),
    ]
    holes_all = []
    for ox, oy, w, h, label, section in views:
        # 다른 뷰에 같은 지름이 치수와 함께 있으면 그 하나로 친다.
        # 미치수 구멍을 만들려면 그 뷰만 지름이 달라야 한다.
        d0 = dia_a + 3.5 if (defect == "undimensioned" and label == "정면도") else dia_a
        holes = [(ox + w / 2, oy + h / 2, d0)]
        if not section:
            holes.append((ox + w - 15, oy + 12, dia_b / 3))
        if defect == "no_center":
            for cx, cy, d in holes:
                msp.add_circle((cx, cy), d / 2)
        else:
            _view(msp, ox, oy, w, h, holes=holes, label=label, section=section)
        holes_all += holes

    # 치수 — 구멍마다 지름 치수를 넣는다. 하나라도 빠지면 EX_DIM_MISSING
    if defect != "no_dims":
        for i, (cx, cy, d) in enumerate(holes_all):
            if defect == "undimensioned" and i == 0:
                continue
            fit = FITS[i % len(FITS)] if defect != "no_fit" else ""
            _dim_dia(msp, (cx, cy), d, f"%%c{d:g}{fit}")
        _dim_linear(msp, (30, 190), (30 + base_w, 190), (30, 180), f"{base_w:g}")
        _dim_linear(msp, (30, 190), (30, 190 + base_h), (20, 190), f"{base_h:g}")
        _dim_linear(msp, (140, 110), (140 + base_w, 110), (140, 100),
                    f"{base_w:g}±0.05")

    # 표면거칠기 — 기능면마다. 세 개 미만이면 EX_SURFACE_FEW
    rough = {"few": ROUGH[:2], "uniform": ["y"] * 4,
             "empty": ["", "x", "y", "z"], "none": []}.get(defect, ROUGH)
    for i, v in enumerate(rough):
        _surface_symbol(msp, 250 + i * 18, 250, v)

    # 데이텀과 기하공차
    if defect != "no_fcf":
        if defect != "no_datum":
            _datum(msp, 240, 200, "A")
            _datum(msp, 240, 185, "B")
        datums = () if defect == "no_datum" else ("A",)
        tol = "" if defect == "no_tolval" else "0.011"
        frames = [("⊥", tol, datums), ("◎", "0.013", datums or ()),
                  ("∥", "0.015", ("B",) if datums else ())]
        if defect == "one_fcf":
            frames = frames[:1]
        for i, (sym, t, dts) in enumerate(frames):
            _fcf(msp, 240, 165 - i * 10, sym, t, dts)

    # 주서
    text = {"no_notes": "", "no_chamfer": "\n".join(
        l for l in NOTES.splitlines() if "모떼기" not in l),
        "no_heat": "\n".join(l for l in NOTES.splitlines()
                             if "열처리" not in l)}.get(defect, NOTES)
    if text:
        msp.add_mtext(text, dxfattribs={"char_height": 3.5}).set_location((20, 90))

    name = name or f"{seed:03d}_{defect or 'ok'}"
    path = os.path.join(out_dir, name + ".dxf")
    doc.saveas(path)
    return path


# 결함 하나마다 잡혀야 하는 코드. bench.py 가 이걸로 검출률을 잰다.
DEFECTS = {
    None: set(),
    "none": {"DQ_NO_SURFACE_SYMBOL"},
    "no_fcf": {"DQ_NO_GEOMETRIC_TOL"},
    # 치수가 하나도 없으면 "미치수 구멍"이 아니라 "치수 없음"이다. 하나만 적는다
    "no_dims": {"EX_NO_DIMS"},
    "undimensioned": {"EX_DIM_MISSING"},
    # 끼워맞춤 기호를 다 빼면 공차 지정 치수 비율도 같이 떨어진다. 둘 다 참이다
    "no_fit": {"EX_NO_FIT", "EX_TOL_FEW"},
    "few": {"EX_SURFACE_FEW"},
    "uniform": {"EX_SURFACE_UNIFORM"},
    "empty": {"EX_SURFACE_EMPTY"},
    "no_datum": {"EX_FCF_NO_DATUM"},
    "no_tolval": {"EX_FCF_NO_VALUE"},
    "one_fcf": {"EX_FCF_FEW"},
    "no_notes": {"EX_NO_NOTES", "EX_NO_HEAT"},
    "no_chamfer": {"EX_NOTE_ITEM"},
    "no_heat": {"EX_NO_HEAT"},
    "no_center": {"EX_NO_CENTERLINE"},
    "no_title": {"EX_NO_TITLEBLOCK"},
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="합성도면")
    ap.add_argument("--count", type=int, default=100)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    kinds = list(DEFECTS)
    labels, i = {}, 0
    while len(labels) < args.count:
        defect = kinds[i % len(kinds)]
        seed = i // len(kinds)
        path = build(seed, defect=defect, out_dir=args.out)
        labels[os.path.basename(path)] = sorted(DEFECTS[defect])
        i += 1
    with open(os.path.join(args.out, "labels.json"), "w", encoding="utf-8") as fh:
        json.dump(labels, fh, ensure_ascii=False, indent=1)
    print(f"{len(labels)}장 · {args.out}/labels.json")


if __name__ == "__main__":
    raise SystemExit(main())
