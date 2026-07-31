# 배포 — Render

심사위원이 접속할 상시 URL을 만드는 절차입니다. 저장소에 [`render.yaml`](../render.yaml)이
들어 있어서 Render가 설정을 알아서 읽습니다.

## 왜 Render인가

| 후보 | 카드 | 잠듦 | 판단 |
|---|---|---|---|
| **Render 무료** | 등록만 (과금 없음) | 15분 후 정지 | **채택** — Dockerfile 그대로, 설정 파일 지원 |
| Koyeb | ❌ 불필요 | ❌ 항상 켜짐 | UI에서 막힘. 조직당 무료 1개 제한 |
| Hugging Face | PRO $9/월 | — | Docker Space는 유료 전용 |
| Cloudflare Containers | Workers $5/월 | — | 유료 전용 |

Render 무료는 **15분간 요청이 없으면 잠들고, 다시 깨는 데 30~50초** 걸립니다.
심사 기간 대응은 아래 "잠들지 않게 하기"를 보세요.

## 1. 배포

1. https://dashboard.render.com 에서 **GitHub 계정으로 가입**
2. **New +** → **Blueprint** 선택
   (`Web Service`가 아니라 **Blueprint** 입니다. `render.yaml`을 읽는 쪽)
3. `ritual1127/naverogq` 저장소 연결 → **Connect**
4. Render가 `render.yaml`을 읽고 서비스를 보여줍니다.
   `GOOGLE_API_KEY` 값을 물어보면 발급받은 키를 붙여넣으세요.
5. **Apply** → 첫 빌드 5~10분

빌드 로그는 서비스 페이지의 **Logs** 탭에서 실시간으로 보입니다.

배포되면 `https://cad-checker-<임의문자>.onrender.com` 이 나옵니다.
**이게 신청서에 적을 프로덕트 URL입니다.**

> Blueprint가 안 보이면 수동으로도 됩니다:
> **New +** → **Web Service** → 저장소 선택 → **Language**를 `Docker`로 →
> **Instance Type** `Free` → **Environment Variables**에 `GOOGLE_API_KEY` 추가.
> 포트는 Render가 `PORT`를 주입하고 Dockerfile이 그걸 받으므로 건드릴 것 없습니다.

## 2. Google AI Studio 키 (무료)

1. https://aistudio.google.com/apikey → **Create API key**
2. 구글 계정만 있으면 되고 결제 등록 없습니다.

> ⚠️ **무료 티어는 입력 데이터가 모델 개선에 쓰일 수 있습니다.**
> 도면 표제란에는 설계자 이름이 들어갑니다. 심사·시연용 도면은 표제란의
> 개인정보를 지우고 쓰세요. 대회 심사기준의 윤리·안전 항목(P/F)에
> 개인정보가 포함되어 있습니다.

## 3. 확인

```
https://<주소>.onrender.com/api/health
```

```json
{"ok": true, "inventor": false, "ai": true,
 "ai_provider": "gemini", "ai_model": "gemini-3.6-flash"}
```

- `inventor: false` — 정상입니다. 리눅스에는 Inventor가 없습니다.
- `ai: true` — 키가 제대로 들어갔다는 뜻입니다. `false`면 2번을 다시 하세요.

그다음 첫 화면에서 **예제 도면 버튼**을 눌러 채점이 도는지 보세요.
심사위원이 밟을 경로와 똑같습니다.

## 4. 잠들지 않게 하기

무료 인스턴스는 15분 유휴 후 정지합니다. 심사위원이 처음 눌렀을 때 40초쯤
빈 화면이 뜨면 고장으로 오해합니다. 무료 모니터링 서비스로 주기적으로
깨워 두세요.

1. https://cron-job.org 또는 https://uptimerobot.com 가입 (무료)
2. 모니터 추가:
   - URL: `https://<주소>.onrender.com/api/health`
   - 간격: **10분**

`/api/health`는 CAD를 열지 않고 즉시 응답하므로 이 핑은 거의 공짜입니다.
**심사 기간(8월 1~17일) 동안만 켜두면 됩니다.**

## 이 서버가 하는 것과 못 하는 것

| | 로컬 (Windows + Inventor) | Render |
|---|---|---|
| `.dxf` / `.dwg` | ✅ | ✅ |
| `.ipt` / `.idw` / `.iam` | ✅ | ❌ Inventor는 리눅스에서 안 돔 |
| 채점 규칙 23개 | ✅ | ✅ 동일 |
| 투상도 30점 AI 판정 | ✅ | ✅ 동일 |
| 예제 도면 원클릭 | ✅ | ✅ |

README에 이 표가 그대로 들어가 있습니다. 심사위원이 `.idw`를 올렸다 실패해도
버그가 아니라 설계 결정이라는 걸 알 수 있습니다.

## 피치 영상은 로컬로 찍으세요

Render 배포본은 Inventor가 없어서 `.idw`를 못 엽니다. 영상에서 보여줄
**오작 판정·3D 뷰어·화살표**는 전부 Inventor 경로라, 촬영은 로컬에서 하세요:

```powershell
.\run.ps1            # http://127.0.0.1:8000
.\run.ps1 -Tunnel    # 임시 공개 주소까지 (재시작하면 주소가 바뀝니다)
```

## 자주 막히는 곳

**빌드 실패 — `libredwg-tools` 를 못 찾음**
데비안 저장소 이름이 바뀐 경우입니다. Dockerfile의 `apt-get install` 줄을
지워도 됩니다. DWG만 못 읽고 DXF 채점은 그대로 동작합니다.

**빌드가 메모리 부족으로 죽음**
무료는 512MB입니다. `requirements.txt`에서 `anthropic` 줄을 지우세요.
Gemini만 쓸 거면 필요 없습니다.

**`ai: false` 로 뜸**
환경변수 이름을 확인하세요. `GOOGLE_API_KEY` 또는 `GEMINI_API_KEY` 입니다.
Claude를 쓰려면 `ANTHROPIC_API_KEY`를 넣고 `AI_PROVIDER=claude`를 추가합니다.

**첫 분석이 유난히 느림**
잠들어 있다 깨는 중입니다(30~50초) + 무료 인스턴스는 CPU가 약합니다.
도면 한 장에 10~30초는 정상입니다.
