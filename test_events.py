"""계측 이벤트가 실제로 세어지는지 본다. 이게 0이면 북극성 지표가 영원히 0이다."""
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_visit_and_recheck_counted():
    client.get("/")
    assert client.post("/api/event", json={"kind": "recheck"}).status_code == 200
    s = client.get("/api/stats").json()
    assert s["today"]["visitors"] == 1
    assert s["week"]["rechecks"] == 1


def test_unknown_event_rejected():
    assert client.post("/api/event", json={"kind": "vote"}).status_code == 400


def test_sample_counts_start_and_done():
    before = client.get("/api/stats").json()["total"]
    r = client.post("/api/analyze-sample", json={"name": "sample_plate.dxf"})
    assert r.status_code == 200, r.text
    after = client.get("/api/stats").json()["total"]
    assert after["samples"] == before["samples"] + 1
    assert after["done"] == before["done"] + 1


def test_info_pages_are_served_but_not_counted_as_visits():
    before = client.get("/api/stats").json()["total"]["visits"]
    for path, page in (("/ks", "ks"), ("/accuracy", "accuracy")):
        r = client.get(path)
        assert r.status_code == 200
        assert f'data-page="{page}"' in r.text
    assert client.get("/api/stats").json()["total"]["visits"] == before


def test_ai_answers_are_fetched_after_the_result():
    import time

    import main

    fake = {"findings": [{"ai_index": 1, "i18n": {"en": {"title": "t"}},
                          "followups": {"ko": ["a", "b", "c"]}}],
            "verdict_i18n": {"en": "v"}}
    assert client.get("/api/ai-extra/nope").status_code == 404
    main._start_extras("job-extra", lambda: (time.sleep(0.2), fake)[1])
    assert client.get("/api/ai-extra/job-extra").json() == {"ready": False}
    for _ in range(50):
        got = client.get("/api/ai-extra/job-extra").json()
        if got["ready"]:
            break
        time.sleep(0.05)
    assert got == {"ready": True, "full": False, "more": False,
                   "findings": fake["findings"], "verdict_i18n": {"en": "v"}}


def test_late_ai_grade_is_sent_after_the_result():
    """AI 채점이 상한 안에 안 끝나면 결과를 먼저 보내고, 채점이 오면 다시 채점해 올려 둔다."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    import main

    facts = {"kind": "dwg", "sheets": [{"name": "Model", "counts": {}, "dims": [],
                                        "undimensioned": [], "views": []}]}
    projection = {"findings": [{"code": "AI_PROJECTION", "severity": "warn", "title": "t",
                                "detail": "d", "fix": "f", "item": "PROJECTION_LAYOUT",
                                "deduct": 4, "where": {}, "ai_index": 0}],
                  "verdict": "v", "score": 26, "model": "m"}
    # 답변·번역까지 채운 판. 실제로는 ai_review.judge 가 넣어 주는 함수다.
    projection["later"] = lambda: {**projection, "verdict_i18n": {"en": "v"}}
    with ThreadPoolExecutor(max_workers=1) as pool:
        main._start_late_ai("job-late", facts, None,
                            pool.submit(lambda: (time.sleep(0.2), projection)[1]))
        for _ in range(60):
            got = client.get("/api/ai-extra/job-late").json()
            if got["ready"] and not got["more"]:
                break
            time.sleep(0.05)
    assert got["ready"] and got["full"] and not got["more"], got
    assert got["scorecard"]["ai_verdict"] == "v"
    assert [f["code"] for f in got["findings"]].count("AI_PROJECTION") == 1
    # 30점짜리 투상도 항목이 '사람 확인'에서 AI 채점으로 바뀐다
    item = next(i for i in got["scorecard"]["items"] if i["code"] == "PROJECTION_LAYOUT")
    assert item["mode"] == "ai" and item["score"] == 26


def test_sample_results_are_reused(monkeypatch):
    """예제 도면은 파일이 안 바뀌니 한 번 검사한 결과를 다시 쓴다. 켠 검사가 다르면 다시 한다."""
    import main

    calls = []

    def fake(job, path, name, enabled=None):
        calls.append(enabled)
        return {"job": job, "file": name, "ai_extra": False,
                "scorecard": {"ai_model": "m"}, "findings": []}

    monkeypatch.setattr(main, "_result", fake)
    monkeypatch.setattr(main, "SAMPLE_RESULTS", {})
    first = client.post("/api/analyze-sample", json={"name": "sample_plate.dxf"}).json()
    again = client.post("/api/analyze-sample", json={"name": "sample_plate.dxf"}).json()
    assert len(calls) == 1 and first["job"] != again["job"]
    client.post("/api/analyze-sample", json={"name": "sample_plate.dxf", "checks": ["EX_NO_DIMS"]})
    assert len(calls) == 2
