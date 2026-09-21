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


def test_feedback_is_saved_and_only_admin_can_read_it(monkeypatch):
    """신고는 누구나 보낼 수 있고, 받은 글은 비밀번호를 아는 사람만 본다."""
    monkeypatch.setenv("CADLENS_ADMIN_PW", "test-pw-1234")
    main._fails.clear()
    main._fails_all.clear()
    sent = client.post("/api/feedback", json={
        "kind": "report", "text": "3번 지적이 틀렸어요. Ø6 에 치수를 넣었는데 없다고 나옵니다.",
        "spot": "3. 구멍 치수 누락", "contact": "open.kakao/abc"})
    assert sent.status_code == 200, sent.text
    assert client.post("/api/feedback", json={"kind": "report", "text": "짧"}).status_code == 400
    assert client.post("/api/feedback", json={"kind": "spam", "text": "다섯 자 넘는 글"}).status_code == 400

    assert client.post("/api/admin/notes", json={"token": "아무 값"}).status_code == 401
    assert client.post("/api/admin/login", json={"pw": "틀린 값"}).status_code == 403
    token = client.post("/api/admin/login", json={"pw": "test-pw-1234"}).json()["token"]
    got = client.post("/api/admin/notes", json={"token": token}).json()["notes"]
    assert got[0]["spot"] == "3. 구멍 치수 누락"
    assert got[0]["contact"] == "open.kakao/abc"
    assert got[0]["file"] == ""          # 도면을 같이 보낸다고 안 했으면 안 남는다


def test_admin_locks_after_repeated_wrong_passwords(monkeypatch):
    """비밀번호가 짧아도 맞혀서는 못 들어가게 한다."""
    monkeypatch.setenv("CADLENS_ADMIN_PW", "test-pw-1234")
    main._fails.clear()
    main._fails_all.clear()
    for _ in range(main.ADMIN_FAIL_MAX):
        assert client.post("/api/admin/login", json={"pw": "nope"}).status_code == 403
    assert client.post("/api/admin/login", json={"pw": "test-pw-1234"}).status_code == 429
    main._fails.clear()
    main._fails_all.clear()


def _proxied(fake, real="10.0.0.5"):
    """Render 처럼 프록시가 뒤에 진짜 접속자를 붙인 모양. 앞의 값은 접속자가 지어낸 것."""
    return {"x-forwarded-for": f"{fake}, {real}"}


def test_feedback_flood_is_stopped_even_with_made_up_ips():
    main._sent.clear()
    main._sent_all.clear()
    body = {"kind": "ask", "text": "사람이 직접 쓴 문의 글"}
    for i in range(main.FEEDBACK_TRUSTED_MAX):
        assert client.post("/api/feedback", json=body,
                           headers=_proxied(f"9.9.9.{i}")).status_code == 200
    # 헤더의 IP 를 바꿔 가며 보내도 프록시가 붙인 값이 같으면 막힌다
    assert client.post("/api/feedback", json=body,
                       headers=_proxied("9.9.9.99")).status_code == 429
    # 한 사람이 같은 값으로 쏟아붓는 것은 더 일찍 막힌다
    main._sent.clear()
    main._sent_all.clear()
    codes = [client.post("/api/feedback", json=body,
                         headers=_proxied("8.8.8.8")).status_code
             for _ in range(main.FEEDBACK_MAX + 1)]
    assert codes[-1] == 429 and codes[0] == 200
    main._sent.clear()
    main._sent_all.clear()


def test_admin_lock_is_not_fooled_by_a_made_up_ip(monkeypatch):
    monkeypatch.setenv("CADLENS_ADMIN_PW", "test-pw-1234")
    main._fails.clear()
    main._fails_all.clear()
    for i in range(main.ADMIN_FAIL_MAX):
        assert client.post("/api/admin/login", json={"pw": "nope"},
                           headers=_proxied(f"1.2.3.{i}")).status_code == 403
    assert client.post("/api/admin/login", json={"pw": "test-pw-1234"},
                       headers=_proxied("1.2.3.50")).status_code == 429
    main._fails.clear()
    main._fails_all.clear()


def test_admin_token_is_bound_and_paths_cannot_escape(monkeypatch):
    monkeypatch.setenv("CADLENS_ADMIN_PW", "test-pw-1234")
    main._fails.clear()
    main._fails_all.clear()
    mine = _proxied("1.1.1.1")
    # 이상한 값을 줘도 500 이 아니라 403 이어야 한다
    for junk in (12345, None, "한글 비밀번호", "x" * 5000):
        assert client.post("/api/admin/login", json={"pw": junk},
                           headers=_proxied("2.2.2.2")).status_code in (403, 429)
    main._fails.clear()
    main._fails_all.clear()
    token = client.post("/api/admin/login", json={"pw": "test-pw-1234"},
                        headers=mine).json()["token"]
    assert client.post("/api/admin/notes", json={"token": token}, headers=mine).status_code == 200
    # 같은 표라도 프록시가 붙인 접속자가 다르면 안 듣는다
    assert client.post("/api/admin/notes", json={"token": token},
                       headers=_proxied("1.1.1.1", real="10.9.9.9")).status_code == 401
    token = client.post("/api/admin/login", json={"pw": "test-pw-1234"},
                        headers=mine).json()["token"]
    for bad in ({"job": "../../etc", "file": "passwd"},
                {"job": "deadbeefcafe", "file": "../../../etc/passwd"},
                {"job": "..", "file": "stats.db"}):
        assert client.post("/api/admin/file", json={"token": token, **bad},
                           headers=mine).status_code == 404
    main._fails.clear()
    main._fails_all.clear()


def test_long_and_odd_feedback_is_cut_not_crashed(monkeypatch):
    monkeypatch.setenv("CADLENS_ADMIN_PW", "test-pw-1234")
    main._sent.clear()
    main._sent_all.clear()
    main._fails.clear()
    main._fails_all.clear()
    ok = client.post("/api/feedback", json={
        "kind": "report", "text": "가" * 9000, "contact": "나" * 9000,
        "spot": "다" * 9000, "job": "../../evil", "share": True})
    assert ok.status_code == 200
    # 검사 번호가 아니면 도면도 고른 부분도 안 남는다
    assert ok.json() == {"ok": True, "drawing": False, "shot": False}
    token = client.post("/api/admin/login", json={"pw": "test-pw-1234"}).json()["token"]
    # 같은 초에 들어온 글이 여럿이라 순서로 찾지 않는다
    notes = client.post("/api/admin/notes", json={"token": token}).json()["notes"]
    got = next(n for n in notes if n["text"].startswith("가가"))
    assert len(got["text"]) == main.NOTE_MAX
    assert len(got["contact"]) == main.CONTACT_MAX
    assert len(got["spot"]) == main.SPOT_MAX
    assert got["job"] == "" and got["file"] == ""
    main._sent.clear()
    main._sent_all.clear()


def test_admin_can_delete_a_note_and_its_drawing(monkeypatch):
    """지워 달라는 요청을 받으면 글과 도면이 같이 없어져야 한다."""
    monkeypatch.setenv("CADLENS_ADMIN_PW", "test-pw-1234")
    main._sent.clear()
    main._sent_all.clear()
    main._fails.clear()
    main._fails_all.clear()
    assert client.post("/api/feedback", json={
        "kind": "ask", "text": "이 글은 지워 주세요"}).status_code == 200
    token = client.post("/api/admin/login", json={"pw": "test-pw-1234"}).json()["token"]
    notes = client.post("/api/admin/notes", json={"token": token}).json()["notes"]
    mine = next(n for n in notes if n["text"] == "이 글은 지워 주세요")
    assert client.post("/api/admin/delete", json={"token": token, "id": mine["id"]}).status_code == 200
    left = client.post("/api/admin/notes", json={"token": token}).json()["notes"]
    assert all(n["id"] != mine["id"] for n in left)
    assert client.post("/api/admin/delete", json={"token": token, "id": mine["id"]}).status_code == 404
    assert client.post("/api/admin/delete",
                       json={"token": token, "id": "../../x"}).status_code == 400
    assert client.post("/api/admin/delete", json={"id": mine["id"]}).status_code == 401
    main._sent.clear()
    main._sent_all.clear()


PNG_1PX = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
           "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def test_picked_region_is_kept_as_a_picture_only(monkeypatch):
    """도면에서 끌어 고른 부분. 그림(PNG)만 받고 그 밖의 것은 안 받는다."""
    monkeypatch.setenv("CADLENS_ADMIN_PW", "test-pw-1234")
    main._sent.clear()
    main._sent_all.clear()
    main._fails.clear()
    main._fails_all.clear()
    job = client.post("/api/analyze-sample", json={"name": "sample_plate.dxf"}).json()["job"]
    ok = client.post("/api/feedback", json={
        "kind": "report", "text": "여기가 이상합니다 봐 주세요",
        "job": job, "shot": PNG_1PX}).json()
    assert ok == {"ok": True, "drawing": False, "shot": True}

    # 그림이 아닌 것, 검사 번호 없는 것, 너무 큰 것은 안 남는다
    svg = "data:image/png;base64,PHN2Zz48c2NyaXB0PmFsZXJ0KDEpPC9zY3JpcHQ+PC9zdmc+"
    for bad in ({"job": job, "shot": svg},
                {"job": "", "shot": PNG_1PX},
                {"job": job, "shot": "data:image/png;base64," + "A" * (main.SHOT_MAX + 4)},
                {"job": job, "shot": "<svg onload=alert(1)>"}):
        got = client.post("/api/feedback", json={
            "kind": "ask", "text": "이건 그림이 아닙니다", **bad}).json()
        assert got["shot"] is False, bad

    token = client.post("/api/admin/login", json={"pw": "test-pw-1234"}).json()["token"]
    notes = client.post("/api/admin/notes", json={"token": token}).json()["notes"]
    mine = next(n for n in notes if n["text"] == "여기가 이상합니다 봐 주세요")
    assert mine["shot"].startswith("spot-") and mine["shot"].endswith(".png")
    got = client.post("/api/admin/file",
                      json={"token": token, "job": job, "file": mine["shot"]})
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    assert got.content.startswith(main.PNG_MAGIC)
    main._sent.clear()
    main._sent_all.clear()


def test_our_notes_do_not_land_in_someone_elses_table():
    """이 D1 은 인터뷰 폼과 같이 쓴다. 거기 `notes` 표가 이미 있어서 우리 글이
    남의 표로 가 INSERT 가 깨진 적이 있다. 우리 표는 `cadlens_notes` 다."""
    import sqlite3

    import stats

    main._sent.clear()
    main._sent_all.clear()
    con = sqlite3.connect(stats.db_path())
    with con:
        con.execute("CREATE TABLE IF NOT EXISTS notes("
                    "answer_id INTEGER, field TEXT, text TEXT)")
        con.execute("DELETE FROM notes")
        con.execute("INSERT INTO notes VALUES(1,'why','남의 표에 이미 있던 글')")
    con.close()

    assert client.post("/api/feedback", json={
        "kind": "ask", "text": "우리 표로 들어가야 합니다"}).status_code == 200

    con = sqlite3.connect(stats.db_path())
    rows = con.execute("SELECT field, text FROM notes").fetchall()
    cols = [r[1] for r in con.execute("PRAGMA table_info(notes)")]
    ours = con.execute("SELECT COUNT(*) FROM cadlens_notes WHERE text=?",
                       ("우리 표로 들어가야 합니다",)).fetchone()[0]
    con.close()
    assert rows == [("why", "남의 표에 이미 있던 글")]   # 남의 글은 그대로
    assert cols == ["answer_id", "field", "text"]       # 칸도 안 늘어남
    assert ours == 1
    main._sent.clear()
    main._sent_all.clear()


def test_conversion_is_counted_by_person_not_by_count():
    """전환율은 사람 단위여야 한다 — 한 사람이 여러 번 올린 것이 여러 명으로 보이면 안 된다."""
    import stats

    here = {"x-forwarded-for": "203.0.113.7"}
    there = {"x-forwarded-for": "203.0.113.8"}
    before = client.get("/api/stats").json()["week"]
    client.get("/", headers=here)
    client.get("/", headers=there)                      # 들어왔지만 검사는 안 한 사람
    for _ in range(3):                                  # 한 사람이 세 번 검사
        client.post("/api/analyze-sample", json={"name": "sample_plate.dxf"}, headers=here)
    week = client.get("/api/stats").json()["week"]
    assert week["visitors"] - before["visitors"] == 2   # 사람 둘
    assert week["checkers"] - before.get("checkers", 0) == 1    # 그중 검사한 사람은 하나
    assert week["finishers"] - before.get("finishers", 0) == 1  # 결과까지 간 사람도 하나
    assert week["checks"] - before["checks"] == 3       # 횟수는 셋
    assert stats.summary()["week"]["checkers"] >= 1


def test_weeks_are_recorded_one_row_per_week():
    """북극성 지표를 주마다 남긴다. 주 안에서만 사람을 셀 수 있으므로 단위는 주다."""
    weeks = client.get("/api/stats").json()["weeks"]
    assert weeks, "주 기록이 비어 있으면 목표 달성 여부를 볼 수 없다"
    first = weeks[0]
    assert set(first) == {"since", "visitors", "checkers", "finishers", "recheckers"}
    assert first["since"] <= __import__("datetime").date.today().isoformat()
    assert first["checkers"] <= first["visitors"] or first["visitors"] == 0
    assert [w["since"] for w in weeks] == sorted((w["since"] for w in weeks), reverse=True)


def test_a_flood_of_checks_is_stopped(monkeypatch):
    """도면 한 장이 CPU 와 AI 호출을 쓴다. 자동으로 반복되면 막아야 한다."""
    main._ran.clear()
    main._ran_all.clear()
    monkeypatch.setattr(main, "CHECK_MAX", 3)
    body = {"name": "sample_plate.dxf"}
    ok = [client.post("/api/analyze-sample", json=body,
                      headers=_proxied("198.51.100.5")).status_code for _ in range(3)]
    assert ok == [200, 200, 200]
    blocked = client.post("/api/analyze-sample", json=body, headers=_proxied("198.51.100.5"))
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == str(main.CHECK_WINDOW)
    # 다른 사람은 그대로 쓸 수 있다
    assert client.post("/api/analyze-sample", json=body,
                       headers=_proxied("198.51.100.9", real="10.0.0.9")).status_code == 200
    main._ran.clear()
    main._ran_all.clear()


def test_link_preview_tags_and_image_exist():
    """링크 미리보기는 깨져도 눈에 안 띈다 — 남이 공유해 봐야 안다. 여기서 잡는다."""
    page = client.get("/").text
    for tag in ('property="og:image"', 'property="og:title"', 'name="twitter:card"'):
        assert tag in page, tag
    shot = client.get("/static/og.png")
    assert shot.status_code == 200
    assert shot.content[:8] == main.PNG_MAGIC
    assert len(shot.content) < 5 * 1024 * 1024        # 카카오톡·트위터가 받는 크기 안
