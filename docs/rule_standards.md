# 검사 항목과 근거

CADLens의 지적은 임의 기준이 아니라 KS 제도 규격과 전산응용기계제도기능사
실기 채점 기준에서 나옵니다. 이 문서는 검사 코드 하나하나가 **어느 규격에서
왔고, 코드 어디에 구현되어 있는지**를 대응시킵니다.

- 검사 코드 목록: `exam.py`의 `CHECKS`
- 배점 항목: `exam.py`의 `RUBRIC`
- 정확도 측정: [accuracy.md](accuracy.md)

규격 번호는 참고용입니다. 시행 시점에 따라 개정판 번호가 다를 수 있으므로
실제 시험에서는 공개문제에 명시된 요구사항이 우선합니다.

## 오작(실격) 판정

공개문제 채점 기준에서 "오작"으로 규정된 항목입니다. 하나라도 걸리면 다른
점수와 무관하게 실격이므로, CADLens는 이 항목을 가장 위에 보여 줍니다.

| 코드 | 지적 내용 | 근거 | 구현 |
|---|---|---|---|
| `DQ_NO_SURFACE_SYMBOL` | 부품도에 표면거칠기 기호가 하나도 없음 | KS B ISO 1302 표면 결 표시, 채점 기준의 오작 조항 | `exam._disqualifiers` |
| `DQ_NO_GEOMETRIC_TOL` | 부품도에 기하공차 기호가 하나도 없음 | KS A ISO 1101 기하공차, 채점 기준의 오작 조항 | `exam._disqualifiers` |
| `DQ_PROJECTION` | 요구된 제3각법이 아님 | KS B ISO 5456-2, KS A ISO 128 투상법 | `exam._disqualifiers` |
| `DQ_SHEET_SIZE` | 요구된 도면 크기(A3)가 아님 | KS B ISO 5457 도면의 크기와 양식 | `exam._disqualifiers` |
| `DQ_SCALE` | 표준 척도가 아닌 값을 사용 | KS A ISO 5455 척도 | `exam._disqualifiers` |

## 치수 기입 (15점)

| 코드 | 지적 내용 | 근거 | 구현 |
|---|---|---|---|
| `EX_NO_DIMS` | 치수가 하나도 없음 | KS B ISO 129-1 치수 기입의 일반 원칙 | `exam._dimensions` |
| `EX_DIM_MISSING` | 치수가 붙지 않은 원·구멍 | KS B ISO 129-1 — 형상을 규정하는 데 필요한 치수는 누락될 수 없음 | `exam._dimensions`, 검출은 `dwg.facts_from_dxf` |

원·구멍은 지름 치수가 붙었는지를 치수 정의점과 원 중심의 일치로 판정합니다.
같은 지름이 여러 개면 묶어서 한 건으로 셉니다(`4-Ø6` 기입 원칙).

## 끼워맞춤 공차·치수공차 (10점)

| 코드 | 지적 내용 | 근거 | 구현 |
|---|---|---|---|
| `EX_NO_FIT` | H7·h6·js5 같은 끼워맞춤 기호가 없음 | KS B 0401 치수공차와 끼워맞춤(ISO 286 계열) | `exam._tolerance` |
| `EX_TOL_FEW` | 공차가 지정된 치수 비율이 낮음 | KS B ISO 2768-1 일반공차 — 기능 치수는 개별 공차 필요 | `exam._tolerance` |

치수 문자 자체에 들어간 공차 표기(`52-0.03^-0.05`, `Ø17js5`)도 공차로 인정합니다.
판정 규칙은 `rules.text_tolerance_state`, 시험은 `test_text_tolerance_state`에 있습니다.
`R3`, `M10`, `(25)` 같은 표기는 공차 대상이 아니므로 지적하지 않습니다.
일반공차 허용치 표(`rules.ISO2768_M`)는 KS B ISO 2768-m 보통급을 씁니다.

## 표면거칠기 (10점)

| 코드 | 지적 내용 | 근거 | 구현 |
|---|---|---|---|
| `EX_SURFACE_EMPTY` | 기호만 있고 거칠기 값이 없음 | KS B ISO 1302 — 기호에는 요구 값이 따라야 함 | `exam._surface` |
| `EX_SURFACE_UNIFORM` | 모든 면이 같은 거칠기 | KS B 0161 — 기능에 따라 다듬질 정도를 구분 | `exam._surface` |
| `EX_SURFACE_FEW` | 가공면 대비 기호 수가 부족 | KS B ISO 1302 — 가공면에는 기호 기입 | `exam._surface` |

DXF에서는 `√`, `Ra/Rz/Ry` 값, 다듬질 기호(w/x/y/z)를 문자에서 인식합니다
(`dwg._surface_symbol`).

## 형상(기하)공차 (10점)

| 코드 | 지적 내용 | 근거 | 구현 |
|---|---|---|---|
| `EX_FCF_NO_DATUM` | 기하공차에 데이텀 참조가 없음 | KS A ISO 5459 데이텀 — 자세·위치·흔들림 공차는 데이텀 필요 | `exam._geometric` |
| `EX_FCF_NO_VALUE` | 공차값이 비어 있음 | KS A ISO 1101 — 공차 기입틀은 기호·공차값·데이텀으로 구성 | `exam._geometric` |
| `EX_FCF_FEW` | 기하공차 개수가 부족 | 채점 기준의 기하공차 배점 | `exam._geometric` |

DXF에서는 `TOLERANCE` 엔티티와 GDT 문자열(`{\Fgdt;…}%%v0.011%%vA`)에서
공차값과 데이텀을 파싱합니다(`dwg._geometric_tol`).

## 주서·표제란·부품란 (8점)

| 코드 | 지적 내용 | 근거 | 구현 |
|---|---|---|---|
| `EX_NO_NOTES` | 주서가 없음 | KS B ISO 2768-1 — 일반공차는 도면에 명시해야 적용됨 | `exam._notes` |
| `EX_NOTE_ITEM` | 주서에 일반공차·표면거칠기·모떼기 문구 누락 | KS B ISO 2768-1, KS B ISO 13715 모서리 지시 | `exam._notes` |
| `EX_NO_TITLEBLOCK` | 표제란·도면 양식이 없음 | KS A ISO 7200 표제란 항목, KS B ISO 5457 도면 양식 | `exam._notes` |

## 재료 선택과 처리 (7점)

| 코드 | 지적 내용 | 근거 | 구현 |
|---|---|---|---|
| `EX_NO_HEAT` | 열처리·표면처리 지시가 없음 | KS D 재료 기호 및 열처리 표기 관행, 채점 기준의 재료 항목 | `exam._material` |

## 투상도 선택과 배열 (30점)

배점이 가장 큰 항목이고, 옳고 그름이 형상에 따라 달라지므로 규칙만으로는
판정하지 않습니다. 규칙으로 확실히 판정되는 것만 지적하고, 배열 자체는
AI 판정으로 따로 다룹니다.

| 코드 | 지적 내용 | 근거 | 구현 |
|---|---|---|---|
| `EX_FEW_VIEWS` | 투상도 개수 부족 | KS A ISO 128-30 투상법 — 형상을 규정할 만큼의 투상도 필요 | `exam._projection` |
| `EX_NO_CENTERLINE` | 원·대칭 형상에 중심선·중심마크 없음 | KS A ISO 128-20/24 선의 종류 — 중심선은 가는 1점 쇄선 | `exam._projection` |
| `EX_VIEW_NO_LABEL` | 단면도·상세도에 문자 표기 없음 | KS A ISO 128-40 단면 표시, 128-34 부분 확대도 | `exam._projection` |
| `EX_VIEW_NO_SCALE` | 전체 척도와 다른 뷰에 척도 표기 없음 | KS A ISO 5455 척도 | `exam._projection` |
| `AI_PROJECTION` | 투상도 선택·배열 AI 판정 | 채점 기준의 투상도 30점 항목 | `ai_review.judge` |

투상도 개수는 판별할 수 있을 때만 지적합니다. Inventor 도면이 아닌 순수 DXF는
뷰 경계를 알 수 없으므로 "0개"로 단정하지 않고 검사를 건너뜁니다
(`sheet.views_known`).

## 규격 원문 요약

검사 규칙을 만들 때 참고한 규격 내용은 [ks_reference.md](ks_reference.md)에
정리해 두었습니다.
