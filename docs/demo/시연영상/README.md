# 시연 영상 — 발표 도우미 3장

`presenter/video/demo.mp4`(1920×1080 · 60fps · 23초)를 만드는 도구다. 실제 CADLens 화면을 찍고, 그 위에
커서 · 카메라 · 자막을 얹는다. 도면은 W4 영상의 `../영상시연/1차/본체.dxf`(팀이 만든 도면).

```bash
# 1. 로컬 서버 — 통계는 임시 DB 로. Cloudflare 값을 비워야 공개 지표에 사람 검사로 안 섞인다
env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID -u CADLENS_D1_STATS CADLENS_STAT_DB="$TEMP/demo_stats.db" \
  .venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010

# 2. 이 폴더에서 (브라우저는 깔린 Chrome 을 쓴다 · ffmpeg 는 PATH 에)
npm i
node capture.js            # 실제 화면을 cap/ 에 3배 해상도로 찍는다 — 약 1분 30초
node render.js             # presenter/video/demo.mp4 · demo.jpg — 약 2분 30초
node render.js 0 1379 46   # 영상 대신 그 프레임만 check/ 에 PNG 로 (미리 보기)
```

- 콘티(시간 · 커서가 지나는 길)는 `story.js`, 카메라와 자막은 `compose.html` 의 `buildShots` · `CAPS`.
- 앱의 CSS 애니메이션을 멈춰 두고 프레임마다 시간을 맞춰 찍는다(`capture.js` 의 `__vc`). 찍는 속도와 상관없이
  스티커 · 끌어다 놓을 때 테두리 · 번호를 눌렀을 때 확대가 60fps 로 정확하다.
- OGQ 스티커 그림만 공개 서버(`/api/sticker/…` — 통계를 세지 않는 주소)에서 받아 공개 화면과 같게 한다.
- 늦게 오는 AI 답변(`/api/ai-extra`)은 찍는 동안 붙잡아 둔다. 오면 지적 목록을 다시 그려 화면이 바뀐다.
- 검사를 기다리는 몇 초는 "빨리 감기"라고 화면에 표시하고 줄인다.
