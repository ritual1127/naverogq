# CADLens

CADLens는 기계 도면을 올리면 잘못된 부분을 찾아주는 웹 서비스입니다.

DWG와 DXF 파일을 읽고 치수, 공차, 표면거칠기, 기하공차, 표제란, 투상도를 검사합니다. 발견한 문제는 도면 위에 번호로 표시하고, 문제의 이유와 고치는 방법을 함께 보여줍니다.

실행 중인 서비스: [https://naverogq.onrender.com](https://naverogq.onrender.com)

## 주요 기능

- DWG와 DXF 파일 분석
- 도면 미리보기와 문제 위치 표시
- 24개 기준을 사용한 자동 검사
- 실격 조건과 항목별 점수 표시
- Gemini를 이용한 투상도 배치 검토
- 한국어, 영어, 일본어, 중국어 지원
- 화면 크기에 맞춘 반응형 디자인

## 작동 과정

1. 사용자가 DWG 또는 DXF 파일을 올립니다.
2. DWG 파일은 LibreDWG를 이용해 읽을 수 있는 형태로 바꿉니다.
3. ezdxf가 도면의 선, 원, 치수, 문자와 기호를 읽습니다.
4. 검사 규칙이 빠진 항목과 잘못된 항목을 찾습니다.
5. 문제 위치에 번호를 붙이고 결과 화면에 설명을 표시합니다.
6. 투상도 배치는 Gemini가 한 번 더 검토합니다.

## 검사 항목

- 치수 누락
- 끼워맞춤 공차와 치수 공차
- 표면거칠기 기호
- 기하공차와 데이텀
- 주서와 표제란
- 재료와 열처리 표시
- 투상도 개수, 이름, 척도와 배치
- 도면 크기와 투상법 등 실격 조건

검사 기준은 `exam.py`에 모아 두었습니다. 일반 CAD 검사 규칙은 `rules.py`에 있습니다.

## 실행 방법

Python 3.11 이상이 필요합니다.

Windows에서는 다음 두 파일을 차례로 실행합니다.

```bat
setup.cmd
run.cmd
```

브라우저에서 `http://127.0.0.1:8000`을 열면 됩니다.

다른 운영체제에서는 다음 명령으로 실행할 수 있습니다.

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python main.py
```

DWG 분석에는 LibreDWG의 `dwg2dxf`가 필요합니다. Docker로 실행하면 자동으로 설치됩니다.

## 환경 변수

AI 검토를 사용하려면 아래 값 중 하나를 설정합니다.

```text
GOOGLE_API_KEY=Google AI Studio 키
GEMINI_API_KEY=Google AI Studio 키
```

키가 없어도 도면 분석과 규칙 검사는 실행됩니다. 이 경우 투상도 항목만 사람이 확인하는 항목으로 표시됩니다.

선택 사항:

```text
ANTHROPIC_API_KEY=Claude API 키
CLOUDCONVERT_API_KEY=CloudConvert API 키
CADCHECK_PORT=8000
```

## 테스트

```bash
python test_rules.py
```

현재 테스트는 도면 검사 규칙, DWG 복구, 미리보기 번호와 지적사항 연결을 확인합니다.

Docker 이미지도 실제 DWG 예제를 변환하고 미리보기를 만들 수 있는지 확인한 뒤 완성됩니다. GitHub Actions는 코드를 올릴 때마다 Docker 빌드를 검사합니다.

## 배포

이 저장소는 Render에서 Docker로 배포됩니다.

1. Render에서 새 Web Service를 만듭니다.
2. 이 GitHub 저장소를 연결합니다.
3. 환경 변수에 `GOOGLE_API_KEY`를 등록합니다.
4. `render.yaml` 설정으로 배포합니다.

## 프로젝트 구조

```text
main.py                 웹 서버와 파일 업로드
check.py                파일 종류 확인과 분석 시작
dwg.py                  DWG 변환, DXF 읽기, 미리보기 생성
exam.py                 대회 채점 기준 24개
rules.py                일반 CAD 검사 규칙
ai_review.py            투상도 AI 검토
inventor.py             Inventor 파일을 읽는 기능
static/index.html       사용자 화면
static/logo.png         서비스 로고
samples/                실행 확인용 DWG와 DXF 예제
test_rules.py           자동 테스트
Dockerfile              배포용 실행 환경
render.yaml             Render 배포 설정
docs/ks_reference.md    도면 기준 참고 자료
```

## 지원 범위

공개 서비스는 DWG와 DXF를 지원합니다.

Inventor가 설치된 Windows 컴퓨터에서는 IPT, IDW, IAM 파일도 읽을 수 있습니다. 이 기능을 사용하려면 다음 명령을 실행합니다.

```bash
python -m pip install -r requirements-inventor.txt
```

자동 검사는 제출 전 확인을 돕는 기능입니다. 복잡한 도면이나 회사별 규칙은 사람이 마지막으로 확인해야 합니다.

## 사용 기술

- Python, FastAPI
- ezdxf, LibreDWG
- Gemini API
- HTML, CSS, JavaScript, Three.js
- Docker, Render, GitHub Actions

## 라이선스

프로젝트 코드는 MIT 라이선스로 공개합니다. 외부 프로그램과 라이브러리의 라이선스는 `NOTICE.md`에서 확인할 수 있습니다.
