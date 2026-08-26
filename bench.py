import argparse
import json
import os
import sys
import tempfile

import ezdxf

import check

MIN_RECALL = 0.90
MIN_PRECISION = 0.90

NOTES_FULL = ("1. 일반공차 - 가) 가공부: KS B ISO 2768-m\n"
              "2. 도시되고 지시없는 모떼기는 1x45°, 필렛과 라운드 R3\n"
              "3. 표면거칠기 기호 비교표 참조, 다듬질 정도 w/x/y\n"
              "4. 전체 열처리 HRC 50±2")
NOTES_NO_CHAMFER = ("1. 일반공차 - 가) 가공부: KS B ISO 2768-m\n"
                    "2. 표면거칠기 다듬질 정도 w/x/y\n"
                    "3. 전체 열처리 HRC 50±2")


def _new():
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.layers.add("CENTER_LINES", linetype="CENTER")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True)
    return doc, msp


def _title_block(doc, msp):
    blk = doc.blocks.new("TITLE")
    blk.add_attdef("PART_NUMBER", (0, 0))
    blk.add_attdef("MATERIAL", (0, -5))
    blk.add_attdef("DESIGNER", (0, -10))
    msp.add_auto_blockref("TITLE", (300, 20), {
        "PART_NUMBER": "1", "MATERIAL": "SM45C", "DESIGNER": "hong"})


def _body(msp, hole_dia=20.0, dimension_hole=True):
    msp.add_lwpolyline([(40, 60), (200, 60), (200, 180), (40, 180)], close=True)
    msp.add_circle((120, 120), hole_dia / 2)
    if dimension_hole:
        dim = msp.add_diameter_dim(center=(120, 120), radius=hole_dia / 2,
                                   angle=45, text=f"%%c{hole_dia:g}H7")
        dim.render()


def _linear(msp, text="160"):
    dim = msp.add_linear_dim(base=(120, 40), p1=(40, 60), p2=(200, 60), text=text)
    dim.render()


def _centerlines(msp):
    msp.add_line((100, 120), (140, 120), dxfattribs={"layer": "CENTER_LINES"})
    msp.add_line((120, 100), (120, 140), dxfattribs={"layer": "CENTER_LINES"})


def _surfaces(msp, values=("y", "x", "w")):
    for i, v in enumerate(values):
        msp.add_text(f"√{v}", height=3.5).set_placement((220 + i * 15, 200))


def _symbol_circles(msp, values=("y", "x", "w"), bare=False):
    import math
    for i, _ in enumerate(values):
        x, y, r = 220 + i * 15, 196.0, 2.4
        apex = (x, y - r / math.sin(math.radians(30)))
        for ang in (60, 120):
            a = math.radians(ang)
            msp.add_line(apex, (apex[0] + 14 * math.cos(a),
                                apex[1] + 14 * math.sin(a)))
        msp.add_circle((x, y), r)
    if bare:
        x, y, r = 200.0, 196.0, 2.4
        apex = (x, y - r / math.sin(math.radians(30)))
        for ang in (60, 120):
            a = math.radians(ang)
            msp.add_line(apex, (apex[0] + 14 * math.cos(a),
                                apex[1] + 14 * math.sin(a)))
        msp.add_circle((x, y), r)


def _fcf(msp, datums=("A",), tol="0.011", count=2):
    for i in range(count):
        msp.add_text(f"⊥%%v{tol}%%v{'%%v'.join(datums)}" if datums
                     else f"⊥%%v{tol}", height=3.5).set_placement((220, 150 - i * 12))


def _notes(msp, text=NOTES_FULL):
    msp.add_mtext(text, dxfattribs={"char_height": 3.5}).set_location((240, 80))


def _write(doc, name, out_dir):
    path = os.path.join(out_dir, name + ".dxf")
    doc.saveas(path)
    return path


def _full(out_dir, name, *, surfaces=("y", "x", "w"), fcf_datums=("A",),
          fcf_count=2, notes=NOTES_FULL, centerlines=True, fit_text="160",
          dimension_hole=True, fcf_tol="0.011", extra_text=(),
          notes_as_lines=False, symbol_circles=False, bare_symbol=False):
    doc, msp = _new()
    _title_block(doc, msp)
    _body(msp, dimension_hole=dimension_hole)
    _linear(msp, fit_text)
    if centerlines:
        _centerlines(msp)
    if surfaces:
        _surfaces(msp, surfaces)
        if symbol_circles:
            _symbol_circles(msp, surfaces, bare_symbol)
    if fcf_count:
        _fcf(msp, fcf_datums, fcf_tol, fcf_count)
    if notes and notes_as_lines:
        for i, line in enumerate(notes.splitlines()):
            msp.add_text(line, height=3.5).set_placement((240, 80 - i * 6))
    elif notes:
        _notes(msp, notes)
    for i, t in enumerate(extra_text):
        msp.add_text(t, height=3.5).set_placement((30, 200 - i * 8))
    return _write(doc, name, out_dir)


def fixtures(out_dir):
    return [
        ("정상 도면", _full(out_dir, "ok"), set()),
        ("표면거칠기 기호 없음", _full(out_dir, "no_surface", surfaces=()),
         {"DQ_NO_SURFACE_SYMBOL"}),
        ("기하공차 없음", _full(out_dir, "no_fcf", fcf_count=0),
         {"DQ_NO_GEOMETRIC_TOL"}),
        ("기하공차 데이텀 없음", _full(out_dir, "no_datum", fcf_datums=()),
         {"EX_FCF_NO_DATUM"}),
        ("기하공차 값 없음", _full(out_dir, "no_tolval", fcf_tol=""),
         {"EX_FCF_NO_VALUE"}),
        ("기하공차 1개뿐", _full(out_dir, "one_fcf", fcf_count=1),
         {"EX_FCF_FEW"}),
        ("거칠기 값 빈 기호", _full(out_dir, "empty_surface", surfaces=("", "x", "w")),
         {"EX_SURFACE_EMPTY"}),
        ("거칠기 한 종류뿐", _full(out_dir, "uniform_surface", surfaces=("y", "y", "y")),
         {"EX_SURFACE_UNIFORM"}),
        ("거칠기 기호 부족", _full(out_dir, "few_surface", surfaces=("y", "x")),
         {"EX_SURFACE_FEW"}),
        ("치수 없는 구멍", _full(out_dir, "undimensioned", dimension_hole=False),
         {"EX_DIM_MISSING", "EX_NO_FIT", "EX_TOL_FEW"}),
        ("주서 없음", _full(out_dir, "no_notes", notes=""),
         {"EX_NO_NOTES", "EX_NO_HEAT"}),
        ("주서 모떼기 누락", _full(out_dir, "no_chamfer", notes=NOTES_NO_CHAMFER),
         {"EX_NOTE_ITEM"}),
        ("중심선 없음", _full(out_dir, "no_center", centerlines=False),
         {"EX_NO_CENTERLINE"}),
        ("거칠기 없고 축·뷰 문자만 있음",
         _full(out_dir, "axis_labels", surfaces=(),
               extra_text=("X", "Y", "Z", "A", "단면 A-A")),
         {"DQ_NO_SURFACE_SYMBOL"}),
        ("주서가 한 줄씩 따로 적힌 도면",
         _full(out_dir, "notes_lines", notes_as_lines=True), set()),
        ("거칠기 기호에 붙은 원", _full(out_dir, "symbol_circles", symbol_circles=True),
         set()),
        ("문자 없는 거칠기 기호(∇)",
         _full(out_dir, "bare_symbol", symbol_circles=True, bare_symbol=True),
         set()),
        ("주서에만 거칠기 문구, 면에는 기호 없음",
         _full(out_dir, "notes_only_surface", surfaces=()),
         {"DQ_NO_SURFACE_SYMBOL"}),
    ]


def load_labeled(path):
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    base = os.path.dirname(os.path.abspath(path))
    return [(name, os.path.join(base, name), set(codes))
            for name, codes in spec.items()]


def run(cases):
    rows, tp, fp, fn = [], 0, 0, 0
    for name, path, expected in cases:
        try:
            _, findings, _ = check.analyze(path, use_ai=False)
            got = {f["code"] for f in findings} - {"EX_RULE_ERROR"}
            err = None
        except Exception as e:
            got, err = set(), f"{type(e).__name__}: {e}"
        hit, miss, extra = expected & got, expected - got, got - expected
        tp += len(hit)
        fn += len(miss)
        fp += len(extra)
        rows.append({"name": name, "expected": sorted(expected), "miss": sorted(miss),
                     "extra": sorted(extra), "error": err})
    recall = tp / (tp + fn) if tp + fn else 1.0
    precision = tp / (tp + fp) if tp + fp else 1.0
    return rows, {"tp": tp, "fp": fp, "fn": fn, "recall": recall,
                  "precision": precision,
                  "exact": sum(1 for r in rows if not r["miss"] and not r["extra"]),
                  "cases": len(rows),
                  "failed": sum(1 for r in rows if r["error"])}


def markdown(rows, m):
    out = ["| 시험 도면 | 잡아야 할 지적 | 결과 |", "|---|---|---|"]
    for r in rows:
        if r["error"]:
            verdict = f"분석 실패 — {r['error']}"
        elif not r["miss"] and not r["extra"]:
            verdict = "정확"
        else:
            bits = []
            if r["miss"]:
                bits.append("놓침 " + ", ".join(r["miss"]))
            if r["extra"]:
                bits.append("오탐 " + ", ".join(r["extra"]))
            verdict = " / ".join(bits)
        want = ", ".join(r["expected"]) or "지적 없음"
        out.append(f"| {r['name']} | {want} | {verdict} |")
    out += ["",
            f"- 기준 도면 {m['cases']}장 중 완전 일치 {m['exact']}장",]
    if m["failed"]:
        out += [f"- **분석 실패 {m['failed']}장** — 아래 숫자는 이 장들을 뺀 것이다"]
    out += [
            f"- 검출률(recall) {m['recall'] * 100:.1f}% — "
            f"실제 결함 {m['tp'] + m['fn']}건 중 {m['tp']}건 검출",
            f"- 정확도(precision) {m['precision'] * 100:.1f}% — "
            f"지적 {m['tp'] + m['fp']}건 중 {m['tp']}건이 실제 결함"]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="?",
                    help="{파일명: [기대 코드]} 형태의 JSON. 없으면 합성 기준 도면 사용")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        cases = load_labeled(args.labels) if args.labels else fixtures(tmp)
        if not cases:
            print(f"FAIL: {args.labels} 에 도면이 한 장도 없다. "
                  f"0장으로는 정확도를 잴 수 없다.", file=sys.stderr)
            return 1
        rows, m = run(cases)

    report = markdown(rows, m)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")

    if m["failed"]:
        print(f"\nFAIL: {m['failed']}장을 열지 못했다. 파일 이름이 labels.json 과 "
              f"같은지, 파일이 같은 폴더에 있는지 본다.", file=sys.stderr)
        return 1

    if args.check and (m["recall"] < MIN_RECALL or m["precision"] < MIN_PRECISION):
        print(f"\nFAIL: recall {m['recall']:.2f} / precision {m['precision']:.2f} "
              f"below {MIN_RECALL} / {MIN_PRECISION}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
