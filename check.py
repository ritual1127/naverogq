import os
from collections.abc import Iterable
from typing import Any

DXF_EXT = {".dxf", ".dwg"}
SUPPORTED = sorted(DXF_EXT)
# Inventor 원본 파일은 공개된 형식이 아니라 서버에서 못 연다. 무슨 파일인지는
# 알아보고, 어떻게 내보내면 되는지까지 알려 준다.
INVENTOR_EXT = {".idw": "도면", ".ipt": "부품", ".iam": "조립품", ".ipn": "프레젠테이션"}
INVENTOR_HELP = (
    "Inventor {what} 파일({ext})은 그대로 못 읽습니다. {how} "
    "여러 장이면 저장소의 idw2dxf.py 로 한 번에 바꿀 수 있습니다.")
_INVENTOR_HOW = {
    ".idw": ("Inventor 에서 이 도면을 열고 '파일 > 내보내기 > DWG/DXF' 로 "
             "저장한 뒤 그 파일을 올려 주세요."),
}
_INVENTOR_HOW_3D = ("먼저 Inventor 에서 도면(.idw)을 만들고, "
                    "'파일 > 내보내기 > DWG/DXF' 로 저장한 뒤 그 파일을 올려 주세요. "
                    "CADLens 는 3D 모델이 아니라 도면을 채점합니다.")


def inventor_help(ext: str) -> str:
    return INVENTOR_HELP.format(what=INVENTOR_EXT[ext], ext=ext,
                                how=_INVENTOR_HOW.get(ext, _INVENTOR_HOW_3D))


Facts = dict[str, Any]
Finding = dict[str, Any]
Summary = dict[str, int]


def analyze(path: str, enabled: Iterable[str] | None = None,
            use_ai: bool = True) -> tuple[Facts, list[Finding], Summary]:
    """Read one drawing and return (facts, findings, summary).

    enabled=None turns every check on. With use_ai off the projection-layout
    judgement is skipped and that rubric item stays "needs human review"."""
    ext = os.path.splitext(path)[1].lower()
    if ext in INVENTOR_EXT:
        raise ValueError(inventor_help(ext))
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
    import ai_review

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
              "| 투상법:", ai_review._projection_line(
                  facts.get("first_angle")).split(": ", 1)[1])
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

