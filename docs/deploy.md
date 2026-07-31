# 무료 배포

심사위원이 접속할 상시 URL을 **신용카드 없이** 만드는 절차입니다.

## 왜 Koyeb인가

| 후보 | 카드 | 잠듦 | 판단 |
|---|---|---|---|
| **Koyeb** | ❌ 불필요 | ❌ 항상 켜짐 | **채택** — 512MB / 0.1 vCPU / 2GB, 서비스 1개 무료 |
| Render 무료 | ✅ 필요 | ✅ 15분 후 정지 (기상 30~50초) | 카드도 필요하고 콜드스타트가 심사에 위험 |
| Hugging Face Spaces | ✅ PRO $9/월 | — | **Docker Space는 유료 전용**입니다. 무료는 Static만 |
| Cloudflare Containers | ✅ Workers $5/월 | — | 유료 플랜 전용 |
| Fly.io | ✅ 필요 | — | 무료 할당량에도 카드 등록 |

Koyeb의 0.1 vCPU는 느립니다. 도면 한 장 분석에 **10~30초** 걸릴 수 있습니다.
첫 화면에 "분석에 시간이 걸립니다" 안내가 이미 들어가 있으니 그대로 두세요.

## 1. Koyeb 배포

1. https://www.koyeb.com 에서 **GitHub 계정으로 가입** (카드 불필요)
2. **Create Service** → **GitHub** → `ritual1127/naverogq` 선택
3. 설정:
   - **Builder**: `Dockerfile` (자동 감지됩니다)
   - **Instance**: `Free` (eco-nano)
   - **Port**: `7860`
   - **Region**: `Frankfurt` 또는 `Washington`
4. **Environment variables** 에 키 추가:
   - `GOOGLE_API_KEY` = AI Studio에서 받은 키
5. **Deploy** → 첫 빌드 5~10분

배포되면 `https://<서비스명>-<계정명>.koyeb.app` 이 나옵니다.
**이게 신청서에 적을 프로덕트 URL입니다.**

## 2. Google AI Studio 키 받기 (무료)

1. https://aistudio.google.com/apikey 접속 (구글 계정만 있으면 됨)
2. **Create API key** → 복사
3. 카드 등록·결제 없음. 무료 티어에 분당·일일 요청 제한이 있지만
   심사용 데모에는 충분합니다.

> ⚠️ **무료 티어는 입력 데이터가 모델 개선에 쓰일 수 있습니다.**
> 도면 표제란에는 설계자 이름이 들어갑니다. 심사·시연용 도면은 표제란의
> 개인정보를 지우고 쓰거나, 유료 티어로 올리세요. 대회 심사기준의
> 윤리·안전 항목(P/F)에 개인정보가 포함되어 있습니다.

## 3. 확인

```
https://<서비스명>-<계정명>.koyeb.app/api/health
```

```json
{"ok": true, "inventor": false, "ai": true,
 "ai_provider": "gemini", "ai_model": "gemini-3.6-flash"}
```

- `inventor: false` — 정상입니다. 리눅스에는 Inventor가 없습니다.
- `ai: true` — 키가 제대로 들어갔다는 뜻입니다. `false`면 2번을 다시 하세요.

그다음 첫 화면에서 **예제 도면 버튼**을 눌러 채점이 도는지 보세요.
심사위원이 밟을 경로와 똑같습니다.

## 이 서버가 하는 것과 못 하는 것

| | 로컬 (Windows + Inventor) | Koyeb |
|---|---|---|
| `.dxf` / `.dwg` | ✅ | ✅ |
| `.ipt` / `.idw` / `.iam` | ✅ | ❌ Inventor는 리눅스에서 안 돔 |
| 채점 규칙 23개 | ✅ | ✅ 동일 |
| 투상도 30점 AI 판정 | ✅ | ✅ 동일 |
| 예제 도면 원클릭 | ✅ | ✅ |

README에 이 표가 그대로 들어가 있습니다. 심사위원이 `.idw`를 올렸다 실패해도
버그가 아니라 설계 결정이라는 걸 알 수 있습니다.

## 피치 영상은 로컬로 찍으세요

Koyeb 배포본은 Inventor가 없어서 `.idw`를 못 엽니다. 영상에서 보여줄
**오작 판정·3D 뷰어·화살표**는 전부 Inventor 경로라, 촬영은 로컬에서 하세요:

```powershell
.\run.ps1            # http://127.0.0.1:8000
.\run.ps1 -Tunnel    # 임시 공개 주소까지 (trycloudflare, 재시작하면 주소 바뀜)
```

## 자주 막히는 곳

**빌드 실패 — `libredwg-tools` 를 못 찾음**
데비안 저장소 이름이 바뀐 경우입니다. Dockerfile의 `apt-get install` 줄을
지워도 됩니다. DWG만 못 읽고 DXF 채점은 그대로 동작합니다.

**메모리 부족으로 빌드가 죽음**
Koyeb 무료는 512MB입니다. `requirements.txt`에서 `anthropic` 줄을 지우세요.
Gemini만 쓸 거면 필요 없습니다.

**`ai: false` 로 뜸**
환경변수 이름을 확인하세요. `GOOGLE_API_KEY` 또는 `GEMINI_API_KEY` 입니다.
Claude를 쓰려면 `ANTHROPIC_API_KEY`를 넣고 `AI_PROVIDER=claude`를 추가합니다.
