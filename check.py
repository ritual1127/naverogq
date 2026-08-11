import os
from typing import Any, Iterable

DXF_EXT = {".dxf", ".dwg"}
SUPPORTED = sorted(DXF_EXT)

Facts = dict[str, Any]
Finding = dict[str, Any]
Summary = dict[str, int]


def analyze(path: str, enabled: Iterable[str] | None = None,
            use_ai: bool = True) -> tuple[Facts, list[Finding], Summary]:
    """도면 한 장을 읽어 (facts, findings, summary) 를 돌려준다.

    enabled 가 None 이면 모든 검사를 켠다. use_ai 를 끄면 투상도 배열 판정을
    건너뛰고 그 항목은 '사람 확인 필요'로 남는다.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in DXF_EXT:
        raise ValueError(f"지원하지 않는 확장자: {ext or '(없음)'}. "
                         f"지원 형식: {', '.join(SUPPORTED)}")
    import ai_review
    import dwg
    import exam
    facts = dwg.analyze(path)
    projection = ai_review.judge(facts) if use_ai else None
    findings, scorecard = exam.grade(facts, enabled, projection)
    facts["scorecard"] = scorecard
    return facts, findings, scorecard["summary"]


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

