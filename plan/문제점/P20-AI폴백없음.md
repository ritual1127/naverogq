# P20 · AI 채점기를 넷 붙여 놓고 실제로는 하나만 썼다

| | |
|---|---|
| 상태 | ✅ **해결** — 2026-09-08 |
| 처음 본 날 | 2026-09-08 |
| 무엇에 영향을 주나 | AI 투상도 채점 30점 — 앞 채점기가 막히면 통째로 비었다 |
| 맡은 사람 | 박지완 |
| 목록 | [문제점 전체](README.md) |

## 증상

실제 도면으로 채점을 돌리다 이 로그가 나왔다.

```
[ai] ServerError: 503 UNAVAILABLE. {'error': {'code': 503, 'message':
'This model is currently experiencing high demand...', 'status': 'UNAVAILABLE'}}
```

그리고 그 도면의 투상도 30점이 `사람 확인 필요`로 비었다. Gemini 가 잠깐 막혔을 뿐인데
채점의 3분의 1이 사라진 것이다. **Cloudflare · Mistral · Groq 를 붙여 둔 이유가 바로
이 상황인데 셋 중 아무것도 불리지 않았다.**

## 원인

`ai_review.judge()`가 `provider()`로 **채점기 하나를 고른 뒤 그 하나만** 불렀다.

```python
name = provider()                     # 키가 있는 것 중 첫 번째
ask = {...}[name]
try:
    text = ask(png, prompt, timeout)
except Exception as e:
    print(f"[ai] {type(e).__name__}: ...")
    return None                       # ← 여기서 끝. 다음 채점기로 안 간다
```

`provider()`의 "앞이 막히면 뒤로 넘어간다"는 **키가 없을 때**만 넘어간다는 뜻이었다.
실행 중에 503·429가 나면 넘어갈 코드가 없었다. README와 발표에는 "한쪽 할당량이
끊겨도 서비스가 버틴다"고 적어 뒀는데, 실제로는 **키가 있는 첫 채점기가 죽으면 같이
죽는 구조**였다.

## 조치

- `providers()` — 쓸 수 있는 채점기를 **목록**으로 준다(우선순위 순).
- `judge()` — 그 목록을 돌면서 진짜 요청을 넣고, 예외·빈 응답·JSON 아님이면
  다음 채점기로 넘어간다. 넘어갔으면 어디로 넘어갔는지 로그에 남긴다.
- 다 실패했을 때만 `None`(=사람 확인 필요)을 돌려준다. 이 부분은 그대로다.

## 확인

```
python -m pytest -q test_rules.py -k ai      → 2 passed
```

- `test_ai_moves_to_the_next_grader_when_the_first_one_fails` — Gemini 가 503 을 던지면
  Mistral 로 넘어가 채점이 끝나는지.
- `test_ai_gives_up_only_after_every_grader_failed` — 넷 다 실패했을 때만 포기하는지,
  그리고 네 개를 **전부** 시도했는지(`["gemini","cloudflare","mistral","groq"]`).

실서비스 확인은 아직 못 했다. 이 컴퓨터에는 Gemini 키만 있어서 두 번째 채점기로
넘어가는 것을 실제 API 로는 못 본다. 배포 서버에는 넷 다 있으므로 다음 배포 뒤
로그에서 `→ ...로 채점` 줄이 나오는지 봐야 한다.
