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

| 패키지 | 라이선스 |
|---|---|
| ezdxf | MIT |
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| python-multipart | Apache-2.0 |
| pywin32 (Windows 전용) | PSF |

## 채점 기준 출처

배점(투상도 30 / 치수 15 / 공차 10 / 표면거칠기 10 / 기하공차 10 / 주서·표제란 8 /
재료 7)과 오작(실격) 조건은 **공개된 전산응용기계제도기능사 채점 기준**을 근거로
`exam.py` 상단에 상수로 명시했습니다. 한국산업인력공단의 비공개 채점표를 복제하거나
열람한 바 없으며, **본 도구는 공식 채점이 아닙니다.**
