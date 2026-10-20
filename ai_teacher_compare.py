"""교사 대조 결과를 센다 — AI 지적이 선생님 판단과 얼마나 맞는지.

    python ai_teacher_compare.py 실제도면/교사대조/ai_results_<id>.json 교사결과1.json [교사결과2.json …]

지표
- 지적 정밀도: 선생님이 「맞음」으로 고른 AI 지적 ÷ (맞음 + 틀림). 「애매」는 따로 센다.
- 점수 차: AI 점수 − 선생님 점수의 평균(+면 AI 가 후함)과 절대값 평균, ±3점 안 비율.
- 감점 여부 일치: 둘 다 감점했거나 둘 다 30점인 도면의 비율.
- 지적 종류별 정밀도: 어느 판정이 잘 틀리는지(지시문을 고칠 곳).
- AI 가 놓친 것: 선생님이 「놓친 것」을 적은 도면 수.
"""
import json
import statistics
import sys
from collections import Counter, defaultdict


def metrics(ai, reviews):
    marks, by_title, diffs, agree, missed, seen = Counter(), defaultdict(Counter), [], [], 0, 0
    for review in reviews:
        if review.get("kit") not in (None, ai.get("id")):
            raise ValueError(f"다른 판의 결과다: {review.get('kit')} ≠ {ai.get('id')}")
        for name, mine in (review.get("drawings") or {}).items():
            theirs = ai["drawings"].get(name)
            if not theirs:
                continue
            seen += 1
            for f in mine.get("findings") or []:
                if f.get("mark") in ("right", "wrong", "unsure") and f.get("i", -1) < len(theirs["findings"]):
                    marks[f["mark"]] += 1
                    by_title[theirs["findings"][f["i"]]["title"]][f["mark"]] += 1
            if isinstance(mine.get("score"), (int, float)):
                diffs.append(theirs["score"] - mine["score"])
                agree.append((theirs["score"] < 30) == (mine["score"] < 30))
            if (mine.get("missed") or "").strip():
                missed += 1
    judged = marks["right"] + marks["wrong"]
    return {
        "drawings": seen,
        "marks": dict(marks),
        "precision": marks["right"] / judged if judged else None,
        "bias": statistics.mean(diffs) if diffs else None,
        "mae": statistics.mean(abs(d) for d in diffs) if diffs else None,
        "within3": sum(abs(d) <= 3 for d in diffs) / len(diffs) if diffs else None,
        "deduct_agree": sum(agree) / len(agree) if agree else None,
        "missed": missed,
        "by_title": {t: dict(c) for t, c in sorted(by_title.items())},
    }


def report(m):
    pct = lambda x: "—" if x is None else f"{100 * x:.0f}%"
    num = lambda x: "—" if x is None else f"{x:+.1f}"
    mae = "—" if m["mae"] is None else f"{m['mae']:.1f}"
    lines = [f"검토한 도면 {m['drawings']}장 · 표시한 AI 지적 {sum(m['marks'].values())}개 "
             f"(맞음 {m['marks'].get('right', 0)} · 틀림 {m['marks'].get('wrong', 0)} · 애매 {m['marks'].get('unsure', 0)})",
             "",
             "| 지표 | 값 |", "|---|---|",
             f"| 지적 정밀도(맞음 ÷ 맞음+틀림) | {pct(m['precision'])} |",
             f"| 점수 차 평균(AI − 선생님, +면 AI 가 후함) | {num(m['bias'])}점 |",
             f"| 점수 차 절대값 평균 | {mae}점 |",
             f"| ±3점 안 | {pct(m['within3'])} |",
             f"| 감점 여부 일치 | {pct(m['deduct_agree'])} |",
             f"| AI 가 놓친 것이 적힌 도면 | {m['missed']}장 |",
             "", "| 지적 종류 | 맞음 | 틀림 | 애매 | 정밀도 |", "|---|---|---|---|---|"]
    for title, c in m["by_title"].items():
        judged = c.get("right", 0) + c.get("wrong", 0)
        lines.append(f"| {title} | {c.get('right', 0)} | {c.get('wrong', 0)} | {c.get('unsure', 0)} | "
                     f"{pct(c.get('right', 0) / judged if judged else None)} |")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    with open(sys.argv[1], encoding="utf-8") as fh:
        ai = json.load(fh)
    reviews = []
    for p in sys.argv[2:]:
        with open(p, encoding="utf-8") as fh:
            reviews.append(json.load(fh))
    print(report(metrics(ai, reviews)))
