# 서드파티 고지 (Third-Party Notices)

이 프로젝트 본체는 MIT 라이선스입니다([LICENSE](LICENSE)). 아래는 함께 쓰거나
배포에 포함된 외부 구성요소와 그 라이선스입니다.

## 저장소에 포함된 것

| 구성요소 | 용도 | 라이선스 | 위치 |
|---|---|---|---|
| [나눔스퀘어라운드](https://hangeul.naver.com/font) (NAVER) | 웹 화면 글꼴 R·B·EB | SIL OFL 1.1 | `static/fonts/` (라이선스 전문 `static/fonts/OFL.txt`) |

나눔스퀘어라운드는 SIL Open Font License 1.1이라 글꼴 파일을 고치지 않고 라이선스 전문과 함께 두면
재배포할 수 있습니다. 글꼴 CDN을 쓰지 않고 서버에 두는 이유는 접속 정보를 외부 글꼴 서버로 보내지 않기 위해서입니다.

## 저장소에 포함하지 **않는** 것 (의도적)

| 구성요소 | 용도 | 라이선스 | 왜 뺐는가 |
|---|---|---|---|
| [GNU LibreDWG](https://www.gnu.org/software/libredwg/) (`dwg2dxf`) | DWG → DXF 변환 | **GPL-3.0-or-later** | GPL-3.0 바이너리를 MIT 저장소에 재배포하면 라이선스가 충돌합니다. 그래서 `vendor/` 를 `.gitignore` 로 제외하고, 설치 시점에 각자 내려받도록 했습니다. |
| Autodesk Inventor | `.ipt`/`.idw`/`.iam` 판독 | 상용 (Autodesk) | 재배포 불가. 사용자가 이미 보유한 설치본을 COM API로 호출만 합니다. |
| ODA File Converter | DWG 변환 (선택) | 상용 무료 | 재배포 불가. 설치되어 있으면 자동으로 찾아 씁니다. |
| OGQ마켓 스티커 「박하의 힐링타임」 (OGQ 공식계정) | 결과 화면의 캐릭터 스티커 | 대회 사무국이 대회 참여 목적으로 제공 | 무단 배포·복제 금지 조건이라 파일을 저장소에 넣지 않습니다. 서버가 실행 중에 OGQ 마켓 API(키는 환경변수 `OGQ_API_KEY`)로 받아 서버 디스크에만 두고 화면에 보냅니다(`ogq.py`). |

LibreDWG는 별도 프로세스(`dwg2dxf.exe`)로 실행하고 파일만 주고받습니다. 라이브러리를
링크하지 않으므로 본 프로젝트 코드가 GPL로 전염되지 않습니다.

## 파이썬 의존성

`requirements.txt` 전체 목록입니다.

| 패키지 | 버전 | 라이선스 |
|---|---|---|
| ezdxf | 1.4.4 | MIT |
| Pillow | 12.3.0 | MIT-CMU |
| FastAPI | 0.141.1 | MIT |
| Uvicorn | 0.52.0 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| Requests | 2.34.2 | Apache-2.0 |
| PyMuPDF | 1.28.0 | **AGPL-3.0-or-later** 또는 상용 |
| google-genai | 2.16.0 | Apache-2.0 |

개발 전용(런타임 미포함): pytest (MIT, 회귀 테스트), fontTools (MIT, `tools_wordmark.py`에서
예전 홈 화면의 3D 워드마크 좌표를 오프라인 생성. 지금 화면은 워드마크를 쓰지 않음).

### PyMuPDF의 AGPL에 대해

PyMuPDF는 AGPL-3.0입니다. AGPL은 **네트워크로 제공되는 서비스에도** 소스 공개 의무를
지웁니다. 이 프로젝트는 저장소 전체를 공개하고 있으므로 그 의무를 충족합니다.
**비공개 상용 배포로 전환한다면 Artifex의 상용 라이선스를 구매해야 합니다.**

PyMuPDF는 AI 검토용으로 DXF를 PNG로 렌더할 때만 씁니다(`ai_review.py`의 `render_png`).
설치돼 있지 않으면 AI 검토가 자동으로 꺼지고, 나머지 기능은 그대로 동작합니다.

## 폰트

웹 화면 글꼴은 나눔스퀘어라운드(NAVER, SIL OFL 1.1)이고 `static/fonts/`에 woff2 3개와 라이선스 전문(`OFL.txt`)을
함께 둡니다. 일본어·중국어 화면의 가나·한자는 사용자 기기의 시스템 글꼴로 표시합니다.
Docker 이미지에는 도면 텍스트 렌더용으로 `fonts-dejavu-core`(Bitstream Vera / 공개 라이선스)와
`fonts-nanum`(SIL Open Font License 1.1)만 설치합니다.

## 상표

`AutoCAD`, `Inventor`는 Autodesk의 상표이고, `Q-Net`은 한국산업인력공단의 서비스입니다.
호환성과 출처를 설명하기 위한 지시적 표시로만 사용했으며, 각 권리자와 제휴 관계가 없습니다.

## 사용자가 올린 도면

도면의 저작권은 그린 사람에게 있습니다. 검사 목적으로만 일시 처리하며(서버 보관 최대 1시간),
학습 데이터로 쓰거나 재배포하지 않습니다. 자세한 내용은 README의 `개인정보 처리` 절을 보세요.

## 채점 기준 출처

배점(투상도 30 / 치수 15 / 공차 10 / 표면거칠기 10 / 기하공차 10 / 주서·표제란 8 /
재료 7)과 오작(실격) 조건은 **공개된 전산응용기계제도기능사 채점 기준**을 근거로
`exam.py` 상단에 상수로 명시했습니다. 한국산업인력공단의 비공개 채점표를 복제하거나
열람한 바 없으며, **본 도구는 공식 채점이 아닙니다.**
