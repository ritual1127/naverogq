"""samples/ 의 예제 도면에 대한 AI 판정을 미리 받아 aicache/ 에 저장한다.

무료 티어는 하루 요청 수가 적어서, 심사 기간에 방문자가 몰리면 예제 버튼조차
AI 없이 뜬다. 예제는 내용이 고정이므로 판정도 고정이다. 미리 한 번 받아 커밋해
두면 배포본은 할당량을 전혀 쓰지 않고도 AI 채점 결과를 보여준다.

    python prime_aicache.py

받은 결과는 aicache/ 에 생기고, 그대로 커밋하면 된다.
"""
import os
import shutil
import sys

import ai_review
import check

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")


def main():
    if not ai_review.is_available():
        print("AI 제공자가 없습니다. GOOGLE_API_KEY 또는 ANTHROPIC_API_KEY 를 설정하세요.")
        return 1

    model = ai_review.active_model()
    print(f"제공자 {ai_review.provider()} · 모델 {model}")
    os.makedirs(ai_review.SHIPPED_CACHE, exist_ok=True)

    names = sorted(n for n in os.listdir(SAMPLES)
                   if os.path.splitext(n)[1].lower() in check.SUPPORTED)
    if not names:
        print("samples/ 에 분석할 파일이 없습니다.")
        return 1

    failed = 0
    for name in names:
        path = os.path.join(SAMPLES, name)
        print(f"\n{name}")
        try:
            facts, _, _ = check.analyze(path, use_ai=False)
        except Exception as e:
            print(f"  건너뜀 (읽기 실패): {type(e).__name__}: {e}")
            continue
        if not facts.get("dxf"):
            print("  건너뜀 (2D 도면이 아님)")
            continue

        png = ai_review.render_png(facts["dxf"])
        key = ai_review._cache_key(png, model)
        dest = os.path.join(ai_review.SHIPPED_CACHE, key)
        if os.path.exists(dest):
            print(f"  이미 있음 -> {key}")
            continue

        result = ai_review.judge(facts)
        if not result:
            print("  실패 (할당량 소진이거나 API 오류). 잠시 뒤 다시 실행하세요.")
            failed += 1
            continue

        src = ai_review._cache_path(png, model)
        if os.path.exists(src):
            shutil.copy(src, dest)
        print(f"  저장 -> aicache/{key}")
        print(f"  투상도 {result['score']}/30 — {result['verdict'][:70]}")

    print("\naicache/ 를 커밋하면 배포본이 할당량 없이 이 결과를 씁니다.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
