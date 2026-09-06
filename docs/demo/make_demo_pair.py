"""시연용 도면 두 벌(고치기 전 / 고친 뒤)을 만든다. — 09-06 계획 2번

영상에서 그 자리에서 고칠 시간이 없어 미리 만들어 둔다. 바탕은 우리가 만든
`samples/sample_plate.dxf` 다. 남의 도면을 쓰면 동의 확인이 먼저라서 시연 기본은
우리 도면으로 둔다.

    python docs/demo/make_demo_pair.py

고치기 전은 원본 그대로 복사하고, 고친 뒤에는 지적 6건이 가리키는 것을 넣는다 —
표면거칠기 기호 · 기하공차 · 끼워맞춤 공차 · 주서(열처리 포함) · 빠진 구멍 치수.
"""
import os
import shutil

import ezdxf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "samples", "sample_plate.dxf")
BEFORE = os.path.join(HERE, "시연_고치기전.dxf")
AFTER = os.path.join(HERE, "시연_고친뒤.dxf")

NOTE = ("주서\n"
        "1. 일반공차 - KS B ISO 2768-m\n"
        "2. 도시되고 지시없는 모떼기는 1x45°, 필렛과 라운드 R2\n"
        "3. 전체 열처리 HRC 50±2\n"
        "4. 표면거칠기 x = Ra 3.2")


def fix(doc):
    msp = doc.modelspace()
    msp.add_mtext(NOTE, dxfattribs={"char_height": 3.0}).set_location((5, 95))
    for i, (mark, spot) in enumerate((("w", (20, 80)), ("x", (45, 80)), ("y", (70, 80)))):
        msp.add_text(mark, height=3.5).set_placement((spot[0], spot[1]))
    # 기하공차 — 유니코드 기호로 적어 둔다. 실기 도면은 GDT 글꼴로 찍는 경우가
    # 많은데, 그건 dwg.py 가 글꼴 이름을 보고 따로 읽는다.
    msp.add_text("⏥%%v0.02%%vA", height=3.0).set_placement((20, 70))
    msp.add_text("⌭%%v0.05%%vA%%vB", height=3.0).set_placement((20, 64))
    msp.add_text("A", height=3.0).set_placement((20, 58))
    # 끼워맞춤 — 치수 문자에 ISO 기호를 얹는다
    for dim in msp.query("DIMENSION"):
        dim.dxf.text = "<>H7"
        break
    return doc


def main():
    shutil.copyfile(SRC, BEFORE)
    doc = fix(ezdxf.readfile(SRC))
    doc.saveas(AFTER)

    import sys
    sys.path.insert(0, ROOT)
    import check
    for path in (BEFORE, AFTER):
        facts, findings, _ = check.analyze(path, use_ai=False)
        sc = facts["scorecard"]
        print(f"{os.path.basename(path):22} {sc['auto_score']}/{sc['auto_max']} "
              f"({sc['percent']}%) 실격={sc['disqualified']} 지적={len(findings)}")
        for f in findings:
            print("   ", f["code"], f["title"])


if __name__ == "__main__":
    main()
