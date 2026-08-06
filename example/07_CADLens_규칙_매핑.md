# 기계설계산업기사 — CADLens 규칙 매핑

## 현행 검사 함수 (`rules.py`)

| 함수 | 검사 코드 | 대상 |
|---|---|---|
| `check_sketches` | `SKETCH_UNDER_CONSTRAINED`, `SKETCH_OVER_CONSTRAINED` | 3D 스케치 구속 |
| `check_holes` | `HOLE_TOO_SMALL`, `HOLE_TOO_DEEP` | 홀 가공성 |
| `check_walls` | `WALL_TOO_THIN` | 살두께 |
| `check_material` | `MATERIAL_NOT_SET` | 재질 지정 |
| `check_props` | `PROP_MISSING` | 품번·설계자 |
| `check_dimension_tolerances` | `TOL_MISSING`, `TOL_INVERTED`, `TOL_ZERO`, `TOL_TOO_LOOSE` | 치수공차 |
| `check_missing_dimensions` | `DIM_MISSING` | 치수 누락 |
| `check_drawing_meta` | `TITLEBLOCK_MISSING`, `SCALE_NONSTANDARD`, `NO_DIMENSIONS_AT_ALL` | 도면 양식 |
| `check_interference` | `INTERFERENCE` | 부품 간섭 |
| `check_sick_features` | `FEATURE_SICK` | 피처 오류 |
| `check_references` | `REFS_BROKEN` | 참조 무결성 |

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

`rules.py`의 검사는 대부분 KS/ISO 제도 규칙에 근거합니다.

- `TOL_INVERTED` — 공차 상한이 하한보다 작으면 가공 불가. 종목과 무관한 물리적 사실.
- `DIM_MISSING` — 치수 없는 원은 크기를 알 수 없음. 종목과 무관.
- `TITLEBLOCK_MISSING` — 표제란 없는 도면은 출도 불가. 종목과 무관.

반면 `exam.py`의 상수(A3, 최소 기호 3개 등)는 전적으로 종목별 공개문제에서 온 값이라
종목이 바뀌면 반드시 바꿔야 합니다. **이 분리가 종목 확장의 핵심입니다.**

## 재사용되는 코드와 종목별로 새로 필요한 코드의 경계

```
[재사용 — 로직 불변]          [종목별로 값만 교체]         [신규 개발 필요]
rules.py 검사 함수 11개    →  exam.py의 SPECS 상수     →  금형 전용 규칙 등
(TOL_*, DIM_MISSING 등)       (도면 크기, 최소 기호 등)     (draft, 클리어런스 등)
```

이 경계를 명확히 나눠 두면, 새 종목이 추가될 때마다 "이 종목은 왼쪽 칸만 필요한가,
가운데 칸까지 필요한가, 오른쪽 칸까지 필요한가"를 먼저 판단할 수 있습니다. 이
문서의 재사용률 추정치는 사실 이 세 칸 중 몇 번째 칸까지 필요한지를 수치로 바꾼
것입니다.

## 검사 함수 하나를 예로 든 재사용 검증

`check_dimension_tolerances`를 예로 들면, 이 함수는 텍스트에서 공차 표기를
정규식으로 찾아 `TOL_MISSING`/`TOL_INVERTED`/`TOL_ZERO`/`TOL_TOO_LOOSE`를
판정합니다. 이 판정은 "공차의 상한이 하한보다 작으면 가공 불가능하다"는 물리적
사실에 기반하므로, 종목이 기계설계산업기사든 사출금형산업기사든 똑같이 참입니다.
종목이 바뀌어도 이 함수의 코드 한 줄도 바꿀 필요가 없다는 뜻이며, 이런 함수가
`rules.py`의 대부분을 차지합니다.
