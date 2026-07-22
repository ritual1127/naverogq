# Inventor 도면 설계 오류 자동 검출기 (HTML/CSS/JS + Python)

DXF/PDF/DWG/IPT/IAM/IDW 도면 파일을 업로드하면 치수 누락·공차 미표기·KS 표준 위반 후보를
자동으로 검출해주는 웹앱입니다. 프론트엔드(HTML/CSS/JS)와 백엔드(Python)를 분리해서,
프론트엔드는 Cloudflare Pages에, 백엔드는 Render에 배포합니다.

## 왜 나뉘어 있나

Cloudflare Workers/Pages는 정적 HTML/CSS/JS와 JS 기반 서버리스 함수는 잘 돌리지만,
`PyMuPDF`처럼 C로 컴파일된 파이썬 패키지는 Cloudflare의 Python(Pyodide) 환경에서 못 돌립니다.
그래서 실제 분석 로직(`app.py`)은 일반 Python 서버가 필요한 Render 같은 곳에 배포하고,
Cloudflare에는 그 API를 호출하는 화면(`index.html`/`style.css`/`script.js`)만 올립니다.

## 동작 방식

1. **.dxf** — `ezdxf`로 직접 파싱해 치수/공차/레이어를 추출하고, 로컬 규칙(KS 기준)으로 1차 검사
2. **.pdf** — `PyMuPDF`로 텍스트와 페이지 이미지를 추출
3. **.dwg / .ipt / .iam / .idw** — Autodesk Platform Services(APS)에 업로드 → 변환 → 썸네일 추출
4. 추출된 데이터(+이미지)를 Google AI Studio(Gemini)에 보내 KS 표준 기준으로 최종 검토

프론트엔드가 `/analyze`에 파일을 업로드하면, 백엔드가 규칙 검사 결과 + Gemini 검토 결과를 JSON으로 반환합니다.

## 로컬 실행

백엔드:
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

프론트엔드: `index.html`을 그냥 브라우저로 열면 됩니다 (`script.js`의 `BACKEND_URL`이 기본값 `http://localhost:8000`).

## 환경변수 (백엔드에 설정)

| 변수 | 필수 여부 | 설명 |
|---|---|---|
| `GOOGLE_API_KEY` | 필수 | Google AI Studio에서 발급한 Gemini API 키 |
| `APS_CLIENT_ID` / `APS_CLIENT_SECRET` | DWG/IPT/IAM/IDW 분석 시 필요 | Autodesk Platform Services 앱 자격증명 |

## 배포

### 백엔드 → Render
1. 이 저장소를 GitHub에 push
2. https://render.com → New → Web Service → 이 저장소 연결
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Environment → `GOOGLE_API_KEY`, `APS_CLIENT_ID`, `APS_CLIENT_SECRET` 등록
6. 배포되면 나오는 `https://xxxx.onrender.com` 주소를 `script.js`의 `BACKEND_URL`에 반영

### 프론트엔드 → Cloudflare Pages
1. `script.js`의 `BACKEND_URL`을 실제 Render 주소로 바꾸고 커밋
2. Cloudflare 대시보드 → Workers & Pages → Create → Pages → 이 저장소 연결 (또는 `wrangler pages deploy .`로 직접 배포)
3. Build command 없음 (정적 파일이라 그대로 배포), 출력 디렉터리는 저장소 루트

## 파일 구조

```
app.py                  # FastAPI 백엔드 (추출/규칙 검사/APS 연동/Gemini 검토 + /analyze API)
index.html              # 프론트엔드 페이지
style.css               # 프론트엔드 스타일
script.js               # 업로드 → API 호출 → 결과 렌더링
Data/                   # 테스트용 샘플 도면 (sample_plate.dxf)
Knowledge/              # Gemini 프롬프트에 참고자료로 넣는 KS 표준 요약
requirements.txt        # 백엔드 의존성 목록
.gitignore              # 깃허브에 올리면 안 되는 파일 목록
```

## 이번 버전에서 제외한 것

- DWG/IPT/IAM/IDW의 정밀 치수 추출: 실제로는 Inventor Design Automation AppBundle이 있어야 가능합니다.
- CORS는 데모용으로 전체 허용(`*`)해뒀습니다. 프론트엔드 도메인이 확정되면 그 도메인으로 좁히는 걸 권장합니다.
- 여러 페이지 구성(추가 HTML): 지금은 단일 페이지로 충분해서 만들지 않았습니다. 필요해지면 추가하세요.
