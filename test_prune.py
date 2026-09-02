"""업로드 정리가 검사 요청 없이도 도는지 본다 (P15).

`_prune_uploads()` 는 원래 `_run()`(새 검사 요청) 안에서만 불렸다. 그래서 트래픽이
없는 시간대엔 화면에 적어 둔 "최대 1시간 안에 지웁니다" 보다 오래 남을 수 있었다.
지금은 lifespan 이 돌리는 주기 작업이 같이 부른다. 이 테스트는 **요청을 한 번도
보내지 않고** 오래된 폴더가 지워지는지 확인한다.
"""
import os
import shutil
import time

from fastapi.testclient import TestClient

import main


def test_오래된_업로드는_요청_없이도_지워진다(monkeypatch):
    old = os.path.join(main.UPLOADS, "job_prune_old")
    new = os.path.join(main.UPLOADS, "job_prune_new")
    for d in (old, new):
        os.makedirs(d, exist_ok=True)
    past = time.time() - (main.JOB_TTL_SEC + 120)
    os.utime(old, (past, past))
    monkeypatch.setattr(main, "PRUNE_EVERY_SEC", 0.2)

    try:
        with TestClient(main.app):  # 요청은 보내지 않는다. lifespan 만 돈다
            time.sleep(1.0)
            assert not os.path.isdir(old), "1시간 지난 폴더가 남았다"
            assert os.path.isdir(new), "방금 만든 폴더까지 지웠다"
    finally:
        for d in (old, new):
            shutil.rmtree(d, ignore_errors=True)
