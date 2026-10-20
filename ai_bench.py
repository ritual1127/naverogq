"""투상도 30점 채점기를 실제 도면으로 재는 도구 — docs/ai_usage.md 「10-20 실측」 표를 이걸로 만들었다.

    python ai_bench.py cloudflare 2 A01,A05,A08 결과.jsonl

도면 이름은 `실제도면/원본/<이름>.dxf` 이다(수험생 도면이라 저장소에는 없다). `.dxf` 로 끝나면 경로로 본다.
캐시를 끄고 `ai_review.judge(defer=True)` 를 그대로 부른다 — 채점 호출 하나만 나가고 답변 · 번역은
부르지 않는다. 키는 저장소의 `.env` 에서 읽고 화면에 찍지 않는다. 한 줄에 한 호출씩 결과 파일에 덧붙인다.
"""
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_env():
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


def main(which, runs, names, out_path):
    load_env()
    os.environ["AI_PROVIDER"] = which
    import requests

    usage = []
    post = requests.post

    def counted(*a, **k):
        r = post(*a, **k)
        try:
            body = r.json()
            usage.append(body.get("usage") or (body.get("result") or {}).get("usage"))
        except Exception:
            usage.append(None)
        return r

    requests.post = counted

    import ai_review
    import dwg

    ai_review._cache_get = lambda p: None
    ai_review._cache_put = lambda p, d: None
    clock = {}
    ask = getattr(ai_review, f"_ask_{which}")

    def timed(*a, **k):
        t = time.perf_counter()
        try:
            return ask(*a, **k)
        finally:
            clock["sec"] = time.perf_counter() - t

    setattr(ai_review, f"_ask_{which}", timed)

    rows = []
    with open(out_path, "a", encoding="utf-8") as log:
        for rnd in range(runs):
            for name in names:
                path = name if name.endswith(".dxf") else os.path.join(ROOT, "실제도면", "원본", name + ".dxf")
                facts = dwg.analyze(path)
                clock.clear()
                usage.clear()
                out = ai_review.judge(facts, timeout=40, defer=True)
                row = {"provider": which, "run": rnd, "name": os.path.basename(path), "ok": out is not None,
                       "sec": round(clock.get("sec") or 0, 2), "score": out and out.get("score"),
                       "deducted": out and len([f for f in out["findings"] if f.get("deduct")]),
                       "findings": out and [[f.get("title"), f.get("deduct")] for f in out["findings"]],
                       "usage": usage[-1] if usage else None}
                rows.append(row)
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(json.dumps(row, ensure_ascii=False), flush=True)
                time.sleep(3)

    ok = [r for r in rows if r["ok"]]
    secs = [r["sec"] for r in ok]
    print(f"\n{which}: 호출 {len(rows)} · 실패 {len(rows) - len(ok)}"
          + (f" · 중앙값 {statistics.median(secs):.1f}초 · 최대 {max(secs):.1f}초"
             f" · 감점 0 {sum(1 for r in ok if r['score'] == 30)}/{len(ok)}"
             f" · 평균 점수 {statistics.mean(r['score'] for r in ok):.1f}/30" if ok else ""))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3].split(","), sys.argv[4])
