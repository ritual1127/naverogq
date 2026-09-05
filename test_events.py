"""계측 이벤트가 실제로 세어지는지 본다. 이게 0이면 북극성 지표가 영원히 0이다."""
import os
import tempfile

os.environ["CADLENS_STAT_DB"] = os.path.join(tempfile.mkdtemp(), "stats.db")
os.environ["CADLENS_STAT_SALT"] = "test"

from fastapi.testclient import TestClient      # noqa: E402

import main                                    # noqa: E402

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
