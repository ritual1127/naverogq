# CADSCAN — Inventor 도면 설계 오류 자동 검출기 (CAD Drawing Error Detector)

> 제4회 NAVER OGQ마켓 AI Competition 출품작 · 트랙: **AI × 산업 혁신**

**CADSCAN**은 DXF / PDF / DWG / IPT / IAM / IDW **CAD 도면 파일**을 업로드하면 **치수 누락
(missing dimension) · 공차 미표기(missing tolerance) · KS 표준 위반(KS standard violation)**
후보를 규칙 기반 검사 + AI(LLM) 검토로 자동 검출하고, 문제 위치를 도면 위에 시각적으로
표시해주는 웹 서비스입니다.

**키워드**: CAD 도면 검사, 설계 오류 자동 검출, Inventor 도면 검토, AutoCAD DXF 파서,
치수 검토 자동화, 공차 검토, KS 표준 검사, 기계설계 QA, 도면 시각화(SVG), Autodesk Platform
Services(APS) 연동, Cloudflare Workers AI, LLM 기반 CAD 리뷰, 제조업 품질관리 AI

**라이브 서비스**: https://inventer-checker.smilepea.workers.dev

## 문제정의

기계설계 실습·현장에서 도면(Inventor/AutoCAD 산출물)에 치수 누락, 공차 미표기, KS 표준
위반이 섞여 나가면 후공정(가공·조립)에서야 발견되어 재작업 비용이 커집니다. 사람이 도면을
한 장씩 눈으로 검토하는 지금 방식은 느리고 놓치기 쉽습니다. 이 프로덕트는 도면 파일을
업로드하는 것만으로 규칙 기반 1차 검사 + AI 2차 검토를 자동으로 수행하고, **문제가 도면의
어느 위치에서 발생했는지 시각적으로 표시**하여 검토 시간을 줄입니다.

## 아키텍처

프론트엔드와 백엔드를 하나의 Cloudflare Worker로 묶어서 배포합니다 (별도 서버 없음).

```
브라우저 ── /              ─▶ Cloudflare Worker Static Assets (public/*)
         └─ /analyze (POST) ─▶ Worker Fetch Handler (src/index.js)
                                 ├─ .dxf            → src/dxf.js (직접 파싱) + src/render.js (SVG 시각화)
                                 ├─ .pdf             → unpdf (텍스트 추출)
                                 ├─ .dwg/.ipt/.iam/.idw → src/aps.js (Autodesk Platform Services)
                                 └─ 규칙 검사 결과 + 원본 요약 → src/ai-review.js
                                                            → Cloudflare Workers AI (Llama 3.3)
```

- DXF는 그룹코드를 직접 태그 파싱해 치수/텍스트/레이어/도형 좌표를 추출하고, 같은 데이터로
  KS 기준 규칙 검사와 문제 위치가 표시된 SVG 도면을 함께 만듭니다.
- DWG/IPT/IAM/IDW는 Inventor 네이티브 포맷이라 순수 코드로 못 열어서, Autodesk Platform
  Services에 업로드 → 변환한 뒤, 프론트엔드에 내장한 **Autodesk APS Viewer**로 실제 모델을
  확대/회전까지 되게 보여줍니다 (`/aps-token`이 뷰어 전용 단기 토큰을 발급). 정밀 치수 판단은
  AI(썸네일 기반)에 맡깁니다.
- AI 검토는 원래 Google Gemini REST API를 직접 호출했으나, **Cloudflare Workers의 이그레스
  IP가 Google 쪽에서 지역 차단(`FAILED_PRECONDITION`)되는 문제**가 있어 Cloudflare Workers AI
  (Llama 3.3 70B, JSON 스키마 구조화 출력)로 교체했습니다. 외부 AI 공급자 호출 자체가 없어져서
  네트워크 경계 문제가 근본적으로 사라집니다.

## 사용 스택

| 영역 | 기술 |
|---|---|
| 프론트엔드 | HTML / CSS / Vanilla JS (프레임워크 없음) |
| 백엔드 | Cloudflare Workers (JavaScript, ES Modules) |
| 정적 호스팅 | Cloudflare Workers Static Assets |
| AI 추론 | Cloudflare Workers AI (`@cf/meta/llama-3.3-70b-instruct-fp8-fast`) |
| CAD 연동 | Autodesk Platform Services (Model Derivative API) |
| PDF 파싱 | [`unpdf`](https://github.com/unjs/unpdf) (edge 런타임용 pdf.js 래퍼) |
| 배포 도구 | Wrangler |

## 실행방법

```bash
npm install
npx wrangler dev        # 로컬 개발 서버
npx wrangler deploy     # Cloudflare Workers 배포
```

시크릿 등록 (배포 전 1회):
```bash
npx wrangler secret put APS_CLIENT_ID       # DWG/IPT/IAM/IDW 분석 시에만 필요
npx wrangler secret put APS_CLIENT_SECRET
```
`GOOGLE_API_KEY`는 더 이상 사용하지 않습니다 (Workers AI로 대체). AI 검토는 Workers AI 바인딩
(`wrangler.toml`의 `[ai]`)만 있으면 별도 키 없이 동작합니다.

## 환경변수 / 바인딩

| 이름 | 필수 여부 | 설명 |
|---|---|---|
| `AI` (바인딩) | 필수 | Cloudflare Workers AI — AI 검토 담당 |
| `APS_CLIENT_ID` / `APS_CLIENT_SECRET` | DWG/IPT/IAM/IDW 분석 시에만 | Autodesk Platform Services 앱 자격증명 |

## 파일 구조

```
public/                 # 프론트엔드 정적 파일 (index.html, style.css, script.js, favicon.svg)
src/
  index.js              # Worker 진입점 — /analyze 라우팅
  dxf.js                # DXF 태그 파서 + KS 규칙 검사
  render.js             # DXF → SVG 렌더링 (문제 위치 마커 오버레이)
  aps.js                # Autodesk Platform Services 연동
  ai-review.js          # Cloudflare Workers AI 검토
Knowledge/              # AI 프롬프트에 참고자료로 넣는 KS 표준 요약
Data/                   # 테스트용 샘플 도면
wrangler.toml           # Worker 설정 (assets, AI 바인딩)
docs/brand-guidelines.md  # 디자인 시스템 (컬러/타이포/로고 규칙)
```

## AI 사용 내역 (공개 원칙)

- **개발 보조**: Claude (Anthropic, Claude Code / Sonnet 5) — 코드 작성, 리팩터링, 디버깅 전반
- **런타임 AI 모델**: Cloudflare Workers AI `@cf/meta/llama-3.3-70b-instruct-fp8-fast` — 규칙
  검사로 못 잡는 KS 표준 위반 후보를 도면 데이터 기반으로 2차 검토
- **오픈소스 패키지**: [`unpdf`](https://www.npmjs.com/package/unpdf) (PDF 텍스트 추출),
  [`wrangler`](https://www.npmjs.com/package/wrangler) (배포 도구)
- **외부 API**: Autodesk Platform Services (Model Derivative API) — DWG/IPT/IAM/IDW 변환
- 외부 자문 없음

## 이번 버전에서 제외한 것

- DWG/IPT/IAM/IDW의 정밀 치수 추출: Inventor Design Automation AppBundle이 있어야 가능한
  범위라, 이번 버전은 Autodesk APS Viewer로 모델을 직접 확대/회전해서 보여주고 AI 판단은
  썸네일 이미지 기반까지만 지원합니다. 문제 위치 마커 오버레이(SVG)는 좌표 데이터가 있는
  DXF만 지원합니다.
- PDF 페이지의 이미지 기반 시각 검토: Cloudflare Workers에 canvas가 없어 텍스트 추출만
  지원합니다.

## 라이선스

MIT License — [`LICENSE`](./LICENSE) 참고.
