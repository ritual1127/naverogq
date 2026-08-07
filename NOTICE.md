# 서드파티 고지 (Third-Party Notices)

이 프로젝트 본체는 MIT 라이선스입니다([LICENSE](LICENSE)). 아래는 함께 쓰거나
배포에 포함된 외부 구성요소와 그 라이선스입니다.

## 저장소에 포함된 것

| 구성요소 | 용도 | 라이선스 | 위치 |
|---|---|---|---|
| [three.js](https://github.com/mrdoob/three.js) | 브라우저 3D STL 미리보기 | MIT | `static/vendor/three.min.js` |

three.js는 MIT이므로 MIT 저장소에 그대로 포함해도 문제가 없습니다. CDN을 쓰지
않고 로컬에 두는 이유는 외부 네트워크 없이도 뷰어가 동작해야 하기 때문입니다.

## 저장소에 포함하지 **않는** 것 (의도적)

| 구성요소 | 용도 | 라이선스 | 왜 뺐는가 |
|---|---|---|---|
| [GNU LibreDWG](https://www.gnu.org/software/libredwg/) (`dwg2dxf`) | DWG → DXF 변환 | **GPL-3.0-or-later** | GPL-3.0 바이너리를 MIT 저장소에 재배포하면 라이선스가 충돌합니다. 그래서 `vendor/` 를 `.gitignore` 로 제외하고, 설치 시점에 각자 내려받도록 했습니다. |
| Autodesk Inventor | `.ipt`/`.idw`/`.iam` 판독 | 상용 (Autodesk) | 재배포 불가. 사용자가 이미 보유한 설치본을 COM API로 호출만 합니다. |
| ODA File Converter | DWG 변환 (선택) | 상용 무료 | 재배포 불가. 설치되어 있으면 자동으로 찾아 씁니다. |

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
| anthropic | 0.120.2 | MIT |

개발 전용(런타임 미포함): pytest (MIT, 회귀 테스트), fontTools (MIT, `tools_wordmark.py`에서
3D 워드마크 좌표를 오프라인 생성).

### PyMuPDF의 AGPL에 대해

PyMuPDF는 AGPL-3.0입니다. AGPL은 **네트워크로 제공되는 서비스에도** 소스 공개 의무를
지웁니다. 이 프로젝트는 저장소 전체를 공개하고 있으므로 그 의무를 충족합니다.
**비공개 상용 배포로 전환한다면 Artifex의 상용 라이선스를 구매해야 합니다.**

PyMuPDF는 AI 검토용으로 DXF를 PNG로 렌더할 때만 씁니다(`ai_review.py`의 `render_png`).
설치돼 있지 않으면 AI 검토가 자동으로 꺼지고, 나머지 기능은 그대로 동작합니다.

## 폰트

홈 화면의 3D 워드마크는 Segoe UI Black(`C:\Windows\Fonts\seguibl.ttf`, Microsoft 독점 폰트)의
글자 외곽선을 오프라인에서 좌표로 변환한 값입니다. **폰트 파일은 저장소에 포함하지 않습니다.**
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
