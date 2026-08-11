# 기계설계산업기사

CADLens 확장 대상 종목 중 하나. 조사 배경과 5개 종목 비교는
[`../README.md`](../README.md)와 [`../00_종합비교표.md`](../00_종합비교표.md)에 있습니다.

| 항목 | 값 |
|---|---|
| 규칙 재사용 추정 | **약 90%** — 5개 종목 중 가장 높음 |
| 신규 개발 부담 | 중 (신규 3건) |
| 핵심 난관 | 3D 모델 채점 연계 |
| 도입 순서 | **1순위** |

재사용률이 가장 높고, 치공구설계산업기사가 통합된 종목이라 대상 응시자도
가장 많습니다. 대부분 `exam.py`의 상수만 종목값으로 바꾸면 동작합니다.
그래서 검사 함수 11개와 루브릭 7개를 **개별 문서로 하나씩** 확인했고,
이 폴더의 문서 수가 가장 많은 이유입니다.

## 이 폴더의 문서

- [`15_AI도면해석표준_적용.md`](15_AI도면해석표준_적용.md) — AI 도면 해석 표준 적용
- [`16_check_sketches.md`](16_check_sketches.md) — 검사함수 분석 — check_sketches
- [`17_check_holes.md`](17_check_holes.md) — 검사함수 분석 — check_holes
- [`18_check_walls.md`](18_check_walls.md) — 검사함수 분석 — check_walls
- [`19_check_material.md`](19_check_material.md) — 검사함수 분석 — check_material
- [`20_check_props.md`](20_check_props.md) — 검사함수 분석 — check_props
- [`21_check_dimension_tolerances.md`](21_check_dimension_tolerances.md) — 검사함수 분석 — check_dimension_tolerances
- [`22_check_missing_dimensions.md`](22_check_missing_dimensions.md) — 검사함수 분석 — check_missing_dimensions
- [`23_check_drawing_meta.md`](23_check_drawing_meta.md) — 검사함수 분석 — check_drawing_meta
- [`24_check_interference.md`](24_check_interference.md) — 검사함수 분석 — check_interference
- [`25_check_sick_features.md`](25_check_sick_features.md) — 검사함수 분석 — check_sick_features
- [`26_check_references.md`](26_check_references.md) — 검사함수 분석 — check_references
- [`27_오작_DQ_NO_SURFACE_SYMBOL.md`](27_오작_DQ_NO_SURFACE_SYMBOL.md) — 오작 조건 분석 — DQ_NO_SURFACE_SYMBOL
- [`28_오작_DQ_NO_GEOMETRIC_TOL.md`](28_오작_DQ_NO_GEOMETRIC_TOL.md) — 오작 조건 분석 — DQ_NO_GEOMETRIC_TOL
- [`29_오작_DQ_PROJECTION.md`](29_오작_DQ_PROJECTION.md) — 오작 조건 분석 — DQ_PROJECTION
- [`30_오작_DQ_SHEET_SIZE.md`](30_오작_DQ_SHEET_SIZE.md) — 오작 조건 분석 — DQ_SHEET_SIZE
- [`31_오작_DQ_SCALE.md`](31_오작_DQ_SCALE.md) — 오작 조건 분석 — DQ_SCALE
- [`32_루브릭_PROJECTION_LAYOUT.md`](32_루브릭_PROJECTION_LAYOUT.md) — 루브릭 세부 분석 — PROJECTION_LAYOUT (투상도 선택과 배열)
- [`33_루브릭_DIMENSIONS.md`](33_루브릭_DIMENSIONS.md) — 루브릭 세부 분석 — DIMENSIONS (치수 기입)
- [`34_루브릭_TOLERANCE.md`](34_루브릭_TOLERANCE.md) — 루브릭 세부 분석 — TOLERANCE (끼워맞춤 공차·치수공차)
- [`35_루브릭_SURFACE.md`](35_루브릭_SURFACE.md) — 루브릭 세부 분석 — SURFACE (표면거칠기)
- [`36_루브릭_GEOMETRIC.md`](36_루브릭_GEOMETRIC.md) — 루브릭 세부 분석 — GEOMETRIC (형상(기하)공차)
- [`37_루브릭_NOTES_TITLE.md`](37_루브릭_NOTES_TITLE.md) — 루브릭 세부 분석 — NOTES_TITLE (주서·표제란·부품란)
- [`38_루브릭_MATERIAL.md`](38_루브릭_MATERIAL.md) — 루브릭 세부 분석 — MATERIAL (재료 선택과 처리)

전체 47개 중 24개 작성. 번호대별 의미는 [`../README.md`](../README.md)의 구조 표를 보세요.
