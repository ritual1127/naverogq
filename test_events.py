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
    assert got == {"ready": True, "findings": fake["findings"], "verdict_i18n": {"en": "v"}}
