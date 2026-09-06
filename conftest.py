"""시험은 진짜 통계 DB를 건드리지 않는다.

`test_events.py` 는 자기 파일 맨 위에서 `CADLENS_STAT_DB` 를 임시 폴더로 돌렸지만,
다른 시험 파일이 먼저 `main` 을 불러오면 그때 이미 진짜 DB(LOCALAPPDATA)가 열린 뒤였다.
그래서 혼자 돌리면 통과하고 `test_rules.py` 와 같이 돌리면 방문자 수가 쌓여
`assert 1 == 1` 이 `assert 3 == 1` 로 깨졌다. conftest 는 어느 시험 파일보다 먼저
읽히므로 여기서 돌려 놓으면 순서와 상관없이 임시 DB만 쓴다.
"""
import os
import tempfile

os.environ.setdefault("CADLENS_STAT_DB",
                      os.path.join(tempfile.mkdtemp(prefix="cadlens-test-"), "stats.db"))
os.environ.setdefault("CADLENS_STAT_SALT", "test")
