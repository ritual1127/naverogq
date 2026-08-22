"""AI가 매기는 투상도 30점이 얼마나 흔들리는지 재는 도구.

같은 도면을 여러 번 채점해서 점수가 몇 점 폭으로 움직이는지, 어떤 지적이
나왔다 안 나왔다 하는지를 봅니다.

    python variance.py samples/sample_plate.dxf          # 5회
    python variance.py samples/sample_plate.dxf -n 10    # 10회

규칙 채점(60점)은 같은 도면이면 항상 같은 답이 나오므로 여기서 재지 않습니다.
정확도 측정은 bench.py 가 따로 합니다.
"""
import argparse
import json
import statistics

import ai_review
import dwg


def spread(scores):
    """점수 목록의 흔들림을 요약한다."""
    if not scores:
        return None
    ordered = sorted(scores)
    return {
        "n": len(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "spread": ordered[-1] - ordered[0],
        "median": statistics.median(ordered),
        "stdev": statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
    }


def _asker():
    name = ai_review.provider()
    if not name:
        return None, None
    fn = {"cloudflare": ai_review._ask_cloudflare,
          "gemini": ai_review._ask_gemini,
          "groq": ai_review._ask_groq,
          "mistral": ai_review._ask_mistral}[name]
    return fn, ai_review.active_model()


def measure(path, n=5, timeout=120.0):
    """도면 하나를 n번 채점해 (점수 목록, 지적 제목별 등장 횟수) 를 돌려준다.

    ai_review.judge() 를 쓰지 않는 이유는 캐시다. judge 는 도면 그림이 같으면
    저장해 둔 답을 그대로 돌려주므로, 두 번째 호출부터는 늘 같은 점수가 나와
    편차가 0으로 보인다. 여기서는 제공자에게 매번 새로 묻는다."""
    ask, model = _asker()
    if ask is None:
        raise RuntimeError("AI 제공자가 없습니다. GEMINI_API_KEY 를 넣고 다시 돌리세요.")

    facts = dwg.analyze(path)
    target = facts.get("dxf")
    if not target:
        raise RuntimeError(f"도면을 읽지 못했습니다: {path}")
    png = ai_review.render_png(target)
    prompt = ai_review.PROMPT + ai_review._context(facts)

    print(f"=== {facts.get('file')}  ({model}, {n}회)")
    scores, seen = [], {}
    for i in range(1, n + 1):
        text = ask(png, prompt, timeout)
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        result = ai_review._to_findings(data, model)
        scores.append(result["score"])
        titles = [f["title"] for f in result["findings"]]
        for t in titles:
            seen[t] = seen.get(t, 0) + 1
        head = f"  {i}회차  {result['score']:>2}/{ai_review.MAX_POINTS}점"
        print(f"{head}  지적 {len(titles)}건" + (
            "".join(f"\n{'':>10}- {t}" for t in titles) if titles else ""))
    return scores, seen


def report(scores, seen):
    s = spread(scores)
    if not s:
        return
    print(f"\n  점수 {sorted(scores)}")
    print(f"  최소 {s['min']}점 · 최대 {s['max']}점 · 폭 {s['spread']}점 · "
          f"중앙값 {s['median']}점 · 표준편차 {s['stdev']:.2f}점")
    if seen:
        print("\n  지적이 몇 번 나왔나 (제목이 매번 조금씩 달라지므로 "
              "같은 지적도 따로 세어질 수 있음)")
        for title, count in sorted(seen.items(), key=lambda kv: -kv[1]):
            mark = "항상" if count == s["n"] else f"{count}/{s['n']}회"
            print(f"    {mark:>7}  {title}")


def main():
    p = argparse.ArgumentParser(description="AI 채점 점수의 편차를 잰다")
    p.add_argument("files", nargs="+", help="도면 파일 (dxf 또는 dwg)")
    p.add_argument("-n", type=int, default=5, help="도면당 채점 횟수 (기본 5)")
    p.add_argument("--timeout", type=float, default=120.0)
    args = p.parse_args()
    for path in args.files:
        scores, seen = measure(path, args.n, args.timeout)
        report(scores, seen)
        print()


if __name__ == "__main__":
    main()
