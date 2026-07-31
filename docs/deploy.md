# 무료 배포 — Hugging Face Spaces

심사위원이 접속할 상시 URL을 **신용카드 없이** 만드는 절차입니다.

Cloudflare Containers는 Workers 유료 플랜(월 $5) 전용이라 제외했습니다.
Workers 무료 플랜은 JS/Pyodide만 돌아서 이 앱(`pymupdf` C 확장, `LibreDWG`
네이티브 바이너리)을 실행할 수 없습니다.

| 후보 | 카드 필요 | 판단 |
|---|---|---|
| **Hugging Face Spaces** | ❌ | **채택** — Docker 그대로, 2vCPU/16GB, 상시 URL |
| Render 무료 | ❌ | 15분 유휴 후 정지, 콜드스타트 ~50초 (심사 중 "고장난 줄" 오해 위험) |
| Fly.io | ✅ | 무료 할당량에도 카드 등록 요구 |
| Cloudflare Containers | ✅ | 월 $5 유료 플랜 전용 |

---

## 1. Space 만들기

1. https://huggingface.co/join 에서 가입 (무료, 카드 불필요)
2. https://huggingface.co/new-space 접속
3. 입력:
   - **Space name**: `cad-checker` (원하는 이름)
   - **License**: `mit`
   - **SDK**: **Docker** → **Blank** 선택 ← 반드시 Docker
   - **Hardware**: `CPU basic · 2 vCPU · 16GB` (무료)
   - **Visibility**: **Public** ← 심사위원이 봐야 하므로 Public

생성 후 주소: `https://huggingface.co/spaces/<아이디>/cad-checker`
실제 앱 주소: `https://<아이디>-cad-checker.hf.space`  ← **이게 제출할 프로덕트 URL**

## 2. API 키를 시크릿으로 넣기

Space 페이지 → **Settings** → **Variables and secrets** → **New secret**

- Name: `ANTHROPIC_API_KEY`
- Value: 발급받은 키

키를 넣지 않아도 배포는 되지만, 투상도 30점 AI 판정이 꺼진 채로 뜹니다.

## 3. 코드 올리기

```powershell
git remote add hf https://huggingface.co/spaces/<아이디>/cad-checker
git push hf main
```

푸시할 때 사용자명은 HF 아이디, 비밀번호 자리에는
**Access Token**(Settings → Access Tokens → New token, `write` 권한)을 넣습니다.

푸시하면 Space가 자동으로 Dockerfile을 빌드합니다. **첫 빌드는 5~10분** 걸립니다.
진행 상황은 Space 페이지의 **Logs** 탭에서 볼 수 있습니다.

## 4. 확인

빌드가 끝나면:

```
https://<아이디>-cad-checker.hf.space/api/health
```

`{"ok": true, "inventor": false, "ai": true, ...}` 가 나오면 정상입니다.
- `inventor: false` — 정상입니다. 리눅스에는 Inventor가 없습니다.
- `ai: true` — 시크릿이 제대로 들어갔다는 뜻입니다. `false`면 2번을 다시 확인하세요.

그다음 첫 화면에서 **예제 도면 버튼**을 눌러 채점이 돌아가는지 확인하세요.
이게 심사위원이 밟을 경로와 정확히 같습니다.

---

## 이 서버가 하는 것과 못 하는 것

| | 로컬 (Windows + Inventor) | 이 배포본 |
|---|---|---|
| `.dxf` / `.dwg` | ✅ | ✅ |
| `.ipt` / `.idw` / `.iam` | ✅ | ❌ Inventor는 리눅스에서 안 돔 |
| 채점 규칙 23개 | ✅ | ✅ 동일 |
| 투상도 30점 AI 판정 | ✅ | ✅ 동일 |
| 예제 도면 원클릭 | ✅ | ✅ |

README에 이 표를 그대로 적어두면, 심사위원이 `.idw`를 올렸다가 실패해도
버그가 아니라 설계 결정이라는 걸 압니다.

## 자주 막히는 곳

**빌드 실패 — `libredwg-tools` 를 못 찾음**
데비안 저장소 이름이 바뀐 경우입니다. Dockerfile의 `apt-get install` 줄을
지워도 됩니다. DWG만 못 읽고 DXF 채점은 그대로 동작합니다.

**Space가 계속 `Building`**
Logs 탭을 보세요. `pip install`에서 멈췄다면 무료 티어 메모리 문제일 수 있습니다.
`requirements.txt`에서 `anthropic`과 `pymupdf`를 빼면 가벼워지지만 AI 판정이 꺼집니다.

**한동안 안 쓰면 잠듦**
무료 Space는 유휴 상태로 두면 정지합니다. 다시 접속하면 자동으로 깨어나고
30초쯤 걸립니다. **심사 기간에는 하루 한 번 접속해서 깨워 두세요.**

**푸시가 거부됨 — 파일이 큼**
`samples/` 의 도면이 10MB를 넘으면 HF가 Git LFS를 요구합니다. 지금 파일들은
전부 그보다 작아서 문제없습니다.
