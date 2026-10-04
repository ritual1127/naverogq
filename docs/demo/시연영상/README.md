# 시연 영상 — 발표 도우미 3장

`presenter/video/demo.mp4`(1920×1080 · 60fps · 30초 · 소리 있음)를 만드는 도구다. 실제 CADLens 화면을 찍고, 그 위에
커서 · 카메라 · 자막을 얹고, 부분마다 그 사람 목소리(AI 합성)를 넣는다. 도면은 W4 영상의 `../영상시연/1차/본체.dxf`(팀이 만든 도면).

| 부분 | 목소리 | 화면 |
|---|---|---|
| ① | 안대열 | 도면을 끌어다 놓는다 — "놓기만" 이 끝날 때 놓는다 |
| ② | 장우영 | 실격 카드 · 도면 위 번호 · 목록의 번호 |
| ③ | 박지완 | "누르면" 에 번호를 누르고 그 자리로 확대 |
| ④ | 김승준 | "예시는" 에 수정 예시를 누르고, "빠진 치수를" 과 함께 초록 Ø20.5 · "위치와 값이" 에서 값으로 다가간다 |

```bash
# 1. 로컬 서버 — 통계는 임시 DB 로. Cloudflare 값을 비워야 공개 지표에 사람 검사로 안 섞인다
env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID -u CADLENS_D1_STATS CADLENS_STAT_DB="$TEMP/demo_stats.db" \
  .venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010

# 2. 이 폴더에서 (브라우저는 깔린 Chrome 을 쓴다 · ffmpeg 는 PATH 에)
npm i
node capture.js            # 실제 화면을 cap/ 에 3배 해상도로 찍는다 — 약 1분 30초
node render.js             # presenter/video/demo.mp4(목소리를 섞어 넣음) · demo.jpg — 약 3분
node render.js 0 1800 60   # 영상 대신 그 프레임만 check/ 에 PNG 로 (미리 보기)
```

- 콘티(시간 · 커서가 지나는 길)는 `story.js`, 카메라와 자막은 `compose.html` 의 `buildShots` · `CAPS`.
- 앱의 CSS 애니메이션을 멈춰 두고 프레임마다 시간을 맞춰 찍는다(`capture.js` 의 `__vc`). 찍는 속도와 상관없이
  스티커 · 끌어다 놓을 때 테두리 · 번호를 눌렀을 때 확대가 60fps 로 정확하다.
- OGQ 스티커 그림만 공개 서버(`/api/sticker/…` — 통계를 세지 않는 주소)에서 받아 공개 화면과 같게 한다.
- 늦게 오는 AI 답변(`/api/ai-extra`)은 찍는 동안 붙잡아 둔다. 오면 지적 목록을 다시 그려 화면이 바뀐다.
- 검사를 기다리는 몇 초는 "빨리 감기"라고 화면에 표시하고 줄인다.

## 목소리 (`voice/`)

`voice/p1 · p2 · p3 · p4a · p4b.wav` 가 영상에 들어간 대사다(-18 LUFS · 48kHz, 앞뒤 무음 정리). 섞으면 약 -16 LUFS.
놓이는 시각과 대사 글은 `story.js` 의 `VOICE`, 누르는 순간은 낱말 시각(`voice/words.json`)으로 정했다.

만든 법 — 팀원이 7월에 녹음한 소개 영상 음성(각 30초 안팎, 저장소에 넣지 않는다)에서 깨끗한 8~10초를 잘라
참고 목소리로 쓰고, 대사마다 후보를 7개씩 만들어 숫자로 골랐다(`voice/gen.py` · `master.py` · `words.py`, GPU · Python 3.11).

- 후보 A — Chatterbox 다국어 TTS 가 참고 목소리로 바로 읽는다(5개)
- 후보 B — Microsoft 신경망 음성(`ko-KR-InJoonNeural`, 참고 녹음 음높이 99~129Hz 에 맞춰 남성 음성)이 읽고
  Chatterbox VC 가 음색만 그 사람으로 바꾼다(2개, 빠르기 +0% · -6%)
- 고르는 기준 — Whisper 로 받아써 글자 오류율 0, 그다음 WavLM 화자 임베딩 닮음 + UTMOS 자연스러움
- 고른 것 — ① A(닮음 0.967 · UTMOS 3.42) ② A(0.981 · 3.57) ③ B(0.959 · 3.37) ④ B(0.950 · 3.45 / 0.928 · 3.96).
  원본 휴대폰 녹음의 UTMOS 는 2.1~2.6
- 정리한 뒤 다시 받아써서 다섯 개 모두 오류율 0 을 확인했다(첫 정리에서 "실기"의 ㅅ 이 잘려 "시액이"로 들리던 것을 고침)

영상 자막에 "○○ 목소리 · AI 음성"을 적는다(대회 AI 사용 공개 · README 의 AI 표).
