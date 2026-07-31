import os

import rules

INVENTOR_EXT = {".ipt", ".idw", ".iam", ".idv", ".ipn"}
DXF_EXT = {".dxf", ".dwg"}
SUPPORTED = sorted(INVENTOR_EXT | DXF_EXT)


def analyze(path, dxf_out=None, stl_out=None, mode="exam", enabled=None,
            use_ai=True):
    ext = os.path.splitext(path)[1].lower()
    if ext in INVENTOR_EXT:
        import inventor
        if not inventor.is_available():
            raise RuntimeError(
                f"{ext} 파일을 분석하려면 이 서버가 설치된 컴퓨터에 Autodesk Inventor가 "
                "있어야 합니다. Inventor 파일의 치수·공차·스케치 정보는 Inventor를 통해서만 "
                "읽을 수 있기 때문입니다. "
                "DWG와 DXF 파일은 Inventor 없이도 그대로 분석됩니다.")
        facts = inventor.analyze(path, dxf_out=dxf_out, stl_out=stl_out)
    elif ext in DXF_EXT:
        import dwg
        facts = dwg.analyze(path)
    else:
        raise ValueError(f"지원하지 않는 확장자: {ext or '(없음)'}. "
                         f"지원 형식: {', '.join(SUPPORTED)}")

    if mode == "exam" and facts.get("kind") in ("drawing", "dwg"):
        import ai_review
        import exam
        projection = ai_review.judge(facts) if use_ai else None
        findings, scorecard = exam.grade(facts, enabled, projection)
        facts["scorecard"] = scorecard
        return facts, findings, scorecard["summary"]

    findings, summary = rules.run(facts)
    return facts, findings, summary


def _report(path):
    facts, findings, summary = analyze(path)
    print(f"\n=== {facts.get('file')}  [{facts.get('kind')}] ===")
    sc = facts.get("scorecard")
    if sc:
        if sc["disqualified"]:
            print("  ** 오작(실격) **  " + " / ".join(sc["disqualifiers"]))
        print(f"  자동 채점 {sc['auto_score']}/{sc['auto_max']}점 "
              f"({sc['percent']}%)   사람 확인 필요 {sc['review_points']}점")
        for it in sc["items"]:
            got = "사람확인" if it["score"] is None else f"{it['score']:>2}/{it['max']}"
            print(f"     {it['label']:22} {got}")
    props = facts.get("props", {})
    print("  품번:", props.get("part_number") or "-",
          "| 재질:", props.get("material") or "-",
          "| 설계자:", props.get("designer") or "-")
    if facts.get("standard"):
        print("  표준:", facts["standard"],
              "| 투상법:", "제1각법" if facts.get("first_angle") else "제3각법")
    for sh in facts.get("sheets", []):
        print(f"  [{sh['name']}] 표제란={sh['title_block']} 뷰={len(sh['views'])} "
              f"치수={len(sh['dims'])} 미치수원={len(sh['undimensioned'])}")
    if facts.get("sketches"):
        print(f"  스케치 {len(facts['sketches'])}개, "
              f"미구속 {sum(1 for s in facts['sketches'] if s['status'] == 'under')}개")
    if facts.get("occurrence_count"):
        print(f"  부품 {facts['occurrence_count']}개, 간섭 {len(facts['interferences'])}건")
    if facts.get("interference_error"):
        print("  간섭 분석 오류:", facts["interference_error"])

    bits = [f"총 {summary['total']}건"]
    for key, label in (("fail", "오작"), ("error", "오류"),
                       ("warn", "경고"), ("info", "정보")):
        if summary.get(key):
            bits.append(f"{label} {summary[key]}")
    print("\n  " + "  ".join(bits))
    marks = {"fail": "!!", "error": " X", "warn": " !", "info": " i"}
    for f in findings:
        print(f"   {marks.get(f['severity'], ' ?')} [{f['code']}] {f['title']}")
    return summary


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"usage: python check.py <file> [file ...]   ({', '.join(SUPPORTED)})")
        raise SystemExit(2)
    for p in sys.argv[1:]:
        try:
            _report(p)
        except Exception as e:
            print(f"\n=== {os.path.basename(p)} ===\n  실패: {type(e).__name__}: {e}")

