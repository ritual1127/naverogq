# P18 · 시험을 같이 돌리면 깨지고 따로 돌리면 통과했다

| | |
|---|---|
| 상태 | ✅ **해결** — 2026-09-06 |
| 처음 본 날 | 2026-09-06 |
| 무엇에 영향을 주나 | `test_events.py` · 시험 결과를 믿을 수 있는지 |
| 맡은 사람 | 박지완 |
| 목록 | [문제점 전체](README.md) |

## 증상

`python -m pytest test_rules.py test_prune.py test_events.py -q` 가 깨졌다.

```
FAILED test_events.py::test_visit_and_recheck_counted - assert 2 == 1
```

돌릴 때마다 숫자가 2 → 3 → 4 로 커졌다. `test_events.py` 만 따로 돌리면 통과했다.

## 원인

`test_events.py` 는 자기 파일 맨 위에서 `CADLENS_STAT_DB` 를 임시 폴더로 돌려
진짜 통계 DB 를 안 건드리게 해 뒀다. 그런데 `test_rules.py` 의 통계 시험이
끝나면서 **그 환경변수를 지웠다**(`del os.environ[...]`). 지운 뒤에 오는 시험은
진짜 DB(`LOCALAPPDATA/cad-checker/stats.db`)를 쓰게 되고, 방문자 수가 돌릴 때마다
쌓여서 `visitors == 1` 이 깨졌다.

즉 **시험이 진짜 통계 DB 에 방문 기록을 쓰고 있었다.** 공개된 지표에 시험이
섞여 들어간 것이다.

## 조치

- `conftest.py` 를 새로 만들어 어느 시험 파일보다 먼저 임시 DB 를 깔아 둔다.
- `test_rules.py` 는 환경변수를 지우지 않고 **원래 값으로 되돌린다.**

## 확인

```
python -m pytest -q                                        → 30 passed
python -m pytest test_rules.py test_prune.py test_events.py -q → 30 passed
```

순서를 바꿔도 통과한다.

## 기록

| 날짜 | 무엇 |
|---|---|
| 2026-09-06 | P17 고치고 시험 돌리다 발견. 같은 날 고침 |
