# 기계설계산업기사 — CADLens 규칙 매핑

## 현행 판정 함수 (`exam.py`)

`exam.py`의 `PRODUCERS` 튜플에 등록된 함수 8개가 판정을 담당합니다.
도면 파싱은 `dwg.py`가, 자동 판정이 어려운 투상도 배열은 `ai_review.py`가 맡습니다.

| 함수 | 검사 코드 | 대상 |
|---|---|---|
| `_disqualifiers` | `DQ_NO_SURFACE_SYMBOL`, `DQ_NO_GEOMETRIC_TOL`, `DQ_PROJECTION`, `DQ_SHEET_SIZE`, `DQ_SCALE` | 오작(실격) |
| `_dimensions` | `EX_NO_DIMS`, `EX_DIM_MISSING` | 치수 기입 |
| `_tolerance` | `EX_NO_FIT`, `EX_TOL_FEW` | 끼워맞춤·치수공차 |
| `_surface` | `EX_SURFACE_EMPTY`, `EX_SURFACE_UNIFORM`, `EX_SURFACE_FEW` | 표면거칠기 |
| `_geometric` | `EX_FCF_NO_DATUM`, `EX_FCF_NO_VALUE`, `EX_FCF_FEW` | 기하공차 |
| `_notes` | `EX_NO_NOTES`, `EX_NOTE_ITEM`, `EX_NO_TITLEBLOCK` | 주서·표제란 |
| `_material` | `EX_NO_HEAT` | 재료·열처리 |
| `_projection` | `EX_FEW_VIEWS`, `EX_NO_CENTERLINE`, `EX_VIEW_NO_LABEL`, `EX_VIEW_NO_SCALE` | 투상도 배열 |
| (`ai_review.judge`) | `AI_PROJECTION` | 투상도 선택·배열 30점 |

검사 코드는 전부 24개이며 `exam.py`의 `CHECKS` 목록에서 켜고 끌 수 있습니다.

## 루브릭 항목별 재사용 판정

| 루브릭 항목 | 재사용 | 사유 |
|---|---|---|
| `DIMENSIONS` | 그대로 사용 | 치수 누락·중복 검사 로직이 동일하게 적용된다. |
| `TOLERANCE` | 그대로 사용 | 끼워맞춤 기호(H7/h6/js5) 검출 정규식을 수정 없이 쓸 수 있다. |
| `SURFACE` | 그대로 사용 | 표면거칠기 기호·값 검사 로직이 동일하다. |
| `GEOMETRIC` | 그대로 사용 | 기하공차 데이텀·공차값 검사가 동일하다. |
| `NOTES_TITLE` | 임계값 조정 | 표제란 필수 항목이 기능사보다 많을 수 있다. |
| `MATERIAL` | 그대로 사용 | 재질·열처리 지시 검사가 동일하다. |
| `PROJECTION_LAYOUT` | 임계값 조정 | 부품 수가 늘어 투상도 최소 개수 기준을 올려야 한다. |

## 재사용률 추정

**약 90%**

산출 근거: 위 표에서 "그대로 사용"으로 판정된 항목의 배점 합을 전체 배점으로 나눈
값에, `08_추가개발_필요항목.md`의 신규 개발 부담을 반영해 조정한 수치입니다.
정밀한 수치가 아니라 도입 순서를 정하기 위한 상대 비교용입니다.

## 로직이 종목과 무관한 이유

`exam.py`의 검사는 대부분 KS/ISO 제도 규칙에 근거합니다.

- `EX_DIM_MISSING` — 치수 없는 원은 크기를 알 수 없음. 종목과 무관.
- `EX_NO_TITLEBLOCK` — 표제란 없는 도면은 출도 불가. 종목과 무관.
- `EX_FCF_NO_DATUM` — 데이텀 없는 기하공차는 기준이 없어 의미가 성립하지 않음.

반면 `exam.py`의 상수(A3, 최소 기호 3개 등)는 전적으로 종목별 공개문제에서 온 값이라
종목이 바뀌면 반드시 바꿔야 합니다. **이 분리가 종목 확장의 핵심입니다.**

## 재사용되는 코드와 종목별로 새로 필요한 코드의 경계

```
[재사용 — 로직 불변]          [종목별로 값만 교체]         [신규 개발 필요]
exam.py 판정 함수 8개      →  종목별 SPECS 상수(예정)  →  금형 전용 규칙 등
(EX_*, DQ_* 판정 조건식)      (도면 크기, 최소 기호 등)     (draft, 클리어런스 등)
```

이 경계를 명확히 나눠 두면, 새 종목이 추가될 때마다 "이 종목은 왼쪽 칸만 필요한가,
가운데 칸까지 필요한가, 오른쪽 칸까지 필요한가"를 먼저 판단할 수 있습니다. 이
문서의 재사용률 추정치는 사실 이 세 칸 중 몇 번째 칸까지 필요한지를 수치로 바꾼
것입니다.

## 판정 함수 하나를 예로 든 재사용 검증

`_tolerance`를 예로 들면, 이 함수는 `text_tolerance_state`가 치수 문자열을
`fit`(H7 같은 끼워맞춤 기호) / `explicit`(±0.1) / `not_applicable`(참고치수·나사)
로 분류한 결과를 받아 `EX_NO_FIT`, `EX_TOL_FEW`를 판정합니다. 이 분류는 KS/ISO
공차 표기법 자체에 기반하므로, 종목이 기계설계산업기사든 사출금형산업기사든 똑같이 참입니다.
종목이 바뀌어도 이 함수의 코드 한 줄도 바꿀 필요가 없다는 뜻이며, 이런 함수가
`exam.py`의 대부분을 차지합니다.
