import re
from collections.abc import Iterable
from typing import Any

Facts = dict[str, Any]
Finding = dict[str, Any]
Scorecard = dict[str, Any]

_ISO_FIT = re.compile(r"\d\s*[A-Za-z]{1,2}\d{1,2}(?![\d.])")
_EXPLICIT_TOL = re.compile(r"±|\^|[+\-]\s*\d*\.\d+|\bmin\b|\bmax\b", re.I)
_NO_TOL_NEEDED = re.compile(r"^\s*[(\[]|^\s*R[\d.]|^\s*M\s*\d|×|\bTYP\b|\bREF\b", re.I)
# MTEXT formatting: font/height/width/alignment/colour runs and braces. The
# stacked-fraction run (\S...;) is left alone because it carries the tolerance.
_MTEXT_FMT = re.compile(r"\\[fFHWQATCpP][^;]*;|\\[LlOoKkNnXx]|[{}]")


def plain_dim_text(text: str | None) -> str:
    """Strip MTEXT formatting and put a number where CAD hides the measured
    value behind ``<>``. Real drawings write ``Ø<>H7``; only drawings typed by
    hand carry the digits, so the fit symbol was invisible without this."""
    return _MTEXT_FMT.sub("", text or "").replace("<>", "0")


def text_tolerance_state(text: str | None) -> str:
    """Classify a dimension's text: does it already carry a tolerance?
    "fit" = ISO fit symbol (H7), "explicit" = ±0.1 and friends,
    "not_applicable" = radius/thread/reference dims that need none."""
    t = plain_dim_text(text).strip()
    if not t:
        return "plain"
    if _NO_TOL_NEEDED.search(t):
        return "not_applicable"
    if _EXPLICIT_TOL.search(t):
        return "explicit"
    if _ISO_FIT.search(t):
        return "fit"
    return "plain"


# 공개문제 요구사항은 "A2 용지에 제도"이고, 출력만 지급된 A3(420×297)에 한다.
# 그래서 요구 도면 영역은 A2, 출력 크기 A3는 오작이 아니라 경고로 본다.
REQUIRED_SHEET = ("A2", 594.0, 420.0)
PRINT_SHEET = "A3"
REQUIRED_SCALE = "1:1"          # 부품도. 3D 등각투상도는 NS
SHEET_TOL_MM = 3.0
REQUIRED_THIRD_ANGLE = True
# KS A ISO 5455 권장 척도. 배척 2:1·5:1·10:1·20:1·50:1, 현척 1:1,
# 축척 1:2·1:5·1:10·1:20·1:50·1:100·1:200·1:500·1:1000.
# 이 목록으로 오작(DQ_SCALE)을 부르므로 **넓게 잡는다** — 목록에 빠진 척도를
# 쓴 멀쩡한 도면을 실격시키는 쪽이 훨씬 나쁘다. 그래서 관행으로 쓰이는
# 1:2.5·1:2.5 계열과 100:1 도 통과시킨다.
STANDARD_SCALES = {"1:1",
                   "1:2", "1:2.5", "1:5", "1:10", "1:20", "1:50",
                   "1:100", "1:200", "1:500", "1:1000",
                   "2:1", "2.5:1", "5:1", "10:1", "20:1", "50:1", "100:1"}
REQUIRED_NOTE_PATTERNS = [
    ("일반공차", r"일반\s*공차|2768"),
    ("표면거칠기 표기", r"표면\s*거칠기|거칠기|√|Ra|Ry|Rz|다듬질"),
    ("모떼기/라운드", r"모[떼따]기|라운드|필렛|45\s*°|45°"),
]
# 일반공차 선언. 공단 주서(예) 1번이 "일반공차 : 가)가공부 : KS B ISO 2768 - m /
# 나)주조부 : KS B 0250 - CT11" 이다. 둘 중 하나라도 있으면 선언된 것으로 본다.
GENERAL_TOL_RE = r"일반\s*공차|2768|0250|CT\s*1[0-9]"
# 일반공차 선언도 없을 때만 보는 값이다. 근거가 있는 수가 아니라 눈금이라
# 낮게 잡는다 — 실제 도면 30장의 중앙값이 15.8% 였다.
MIN_TOLERANCED_RATIO = 0.10
MIN_SURFACE_SYMBOLS = 3
MIN_FCF = 1

SEV_FAIL, SEV_ERROR, SEV_WARN, SEV_INFO = "fail", "error", "warn", "info"

# 공개된 채점 기준표의 8개 항목과 배점(합계 100점)을 그대로 옮긴 것이다.
# `도면 배치와 외관` 10점은 오래 빠져 있었다 — 그동안 만점이 90점이었고,
# 선 굵기·문자 크기처럼 DXF 에서 바로 읽히는 항목이 통째로 채점되지 않았다.
RUBRIC = [
    ("PROJECTION_LAYOUT", "투상도 선택과 배열", 30, "review"),
    ("DIMENSIONS", "치수 기입", 15, "auto"),
    ("TOLERANCE", "끼워맞춤 공차·치수공차", 10, "auto"),
    ("SURFACE", "표면거칠기", 10, "auto"),
    ("GEOMETRIC", "형상(기하)공차", 10, "auto"),
    ("APPEARANCE", "도면 배치와 외관", 10, "auto"),
    ("NOTES_TITLE", "주서·표제란·부품란", 8, "auto"),
    ("MATERIAL", "재료 선택과 처리", 7, "auto"),
]
RUBRIC_MAX = {c: p for c, _, p, _ in RUBRIC}
RUBRIC_LABEL = {c: label for c, label, _, _ in RUBRIC}
RUBRIC_MODE = {c: m for c, _, _, m in RUBRIC}

CHECKS = [
    ("DQ_NO_SURFACE_SYMBOL", "표면거칠기 기호가 아예 없음", "오작", True),
    ("DQ_NO_GEOMETRIC_TOL", "기하공차 기호가 아예 없음", "오작", True),
    ("DQ_PROJECTION", "투상법이 제3각법이 아님", "오작", True),
    ("DQ_SHEET_SIZE", "도면 크기가 요구와 다름", "오작", True),
    ("DQ_SCALE", "비표준 척도 사용", "오작", True),
    ("DQ_NO_FIT", "끼워맞춤 공차 기호가 아예 없음", "오작", True),

    ("EX_NO_DIMS", "치수가 하나도 없음", "DIMENSIONS", True),
    ("EX_DIM_MISSING", "치수 없는 원·구멍", "DIMENSIONS", True),

    ("EX_TOL_FEW", "공차 지정된 치수가 너무 적음", "TOLERANCE", True),

    ("EX_SURFACE_EMPTY", "거칠기 값이 빈 기호", "SURFACE", True),
    ("EX_SURFACE_UNIFORM", "거칠기가 한 종류뿐(다듬질 구분 없음)", "SURFACE", True),
    ("EX_SURFACE_FEW", "거칠기 기호 수가 부족", "SURFACE", True),

    ("EX_FCF_NO_DATUM", "기하공차에 데이텀 없음", "GEOMETRIC", True),
    ("EX_FCF_NO_VALUE", "기하공차 값이 빔", "GEOMETRIC", True),
    ("EX_FCF_FEW", "기하공차 개수 부족", "GEOMETRIC", True),

    ("EX_NO_ROUGH_TABLE", "표면거칠기 비교표 없음", "SURFACE", True),

    ("EX_NO_SPEC_TABLE", "기어·스프링 요목표 없음", "NOTES_TITLE", True),
    ("EX_NO_NOTES", "주서 없음", "NOTES_TITLE", True),
    ("EX_NOTE_ITEM", "주서 필수 문구 누락", "NOTES_TITLE", True),
    ("EX_NO_TITLEBLOCK", "표제란·도면양식 없음", "NOTES_TITLE", True),
    ("EX_SHEET_SIZE", "도면 영역이 요구 크기와 다름", "NOTES_TITLE", True),
    ("EX_NO_PROJECTION_MARK", "각법 표기 없음", "NOTES_TITLE", True),
    ("EX_NO_SHEET_SCALE", "표제란에 척도 표기 없음", "NOTES_TITLE", True),
    ("EX_SCALE_NOT_ONE", "부품도 척도가 1:1이 아님", "NOTES_TITLE", True),
    ("EX_VIEW_SCALE_MIXED", "뷰마다 척도가 다름", "NOTES_TITLE", True),

    ("EX_LINEWEIGHT_FLAT", "용도에 맞는 선 굵기 구분 없음", "APPEARANCE", True),
    ("EX_LINEWEIGHT_NONE", "레이어에 선 굵기가 지정되지 않음", "APPEARANCE", True),
    ("EX_TEXT_SIZE", "문자 크기가 제도 표준과 다름", "APPEARANCE", True),

    ("EX_NO_HEAT", "열처리·표면처리 지시 없음", "MATERIAL", True),
    ("EX_NO_MATERIAL", "재료 기호 기입 없음", "MATERIAL", True),
    ("EX_NO_MASS", "3D 등각투상도 부품란에 질량 없음", "MATERIAL", True),

    ("EX_LAYOUT_FIRST_ANGLE", "뷰 배치가 제1각법으로 보임", "PROJECTION_LAYOUT", True),
    ("EX_FEW_VIEWS", "투상도 개수 부족", "PROJECTION_LAYOUT", True),
    ("EX_NO_CENTERLINE", "중심선·중심마크 없음", "PROJECTION_LAYOUT", True),
    ("EX_VIEW_NO_LABEL", "상세도·단면도에 문자 표기 없음", "PROJECTION_LAYOUT", True),
    ("EX_VIEW_NO_SCALE", "척도 다른 뷰에 척도 표기 없음", "PROJECTION_LAYOUT", True),
    ("AI_PROJECTION", "투상도 선택·배열 AI 판정 (30점)", "PROJECTION_LAYOUT", True),
]
DEFAULT_ENABLED = {cid for cid, _, _, on in CHECKS if on}
ALL_CHECK_IDS = {cid for cid, _, _, _ in CHECKS}


def _f(code, severity, title, detail, fix, item=None, deduct=0, where=None):
    return {"code": code, "severity": severity, "title": title, "detail": detail,
            "fix": fix, "item": item, "deduct": deduct, "where": where or {}}


def _sheet_of(facts):
    sheets = facts.get("sheets") or []
    return sheets[0] if sheets else {}


def _scale_str(v):
    s = (v.get("scale_string") or "").replace(" ", "")
    if s:
        return s
    sc = v.get("scale")
    if not sc:
        return ""
    return f"{int(1 / sc)}:1" if sc < 1 else f"{sc:g}:1"


def _disqualifiers(facts):
    out = []
    sh = _sheet_of(facts)
    counts = sh.get("counts", {})

    if counts.get("SurfaceTextureSymbols", 0) == 0:
        out.append(_f(
            "DQ_NO_SURFACE_SYMBOL", SEV_FAIL, "오작: 표면거칠기 기호 없음",
            "부품도에 표면거칠기 기호가 하나도 없습니다. 공개된 채점 기준에서 "
            "'표면거칠기 기호를 부품도에 기입하지 않은 도면'은 오작(실격)입니다.",
            "주석 > 표면 텍스처 기호 로 가공면마다 기호를 기입하고, "
            "주서에 다듬질 구분(w/x/y 또는 Ra 값)을 정의하세요.",
            "SURFACE"))

    if counts.get("FeatureControlFrames", 0) < MIN_FCF:
        out.append(_f(
            "DQ_NO_GEOMETRIC_TOL", SEV_FAIL, "오작: 기하공차 기호 없음",
            "부품도에 기하공차(형상공차) 기호가 하나도 없습니다. "
            "'기하공차 기호를 부품도에 기입하지 않은 도면'은 오작(실격)입니다.",
            "주석 > 형상 공차 로 데이텀(A, B...)을 먼저 지정하고 "
            "동심도·직각도·평행도 등을 기입하세요.",
            "GEOMETRIC"))

    if REQUIRED_THIRD_ANGLE and facts.get("first_angle") is True:
        out.append(_f(
            "DQ_PROJECTION", SEV_FAIL, "오작: 투상법이 제1각법",
            "요구 투상법은 제3각법인데 도면이 제1각법입니다. "
            "'투상법이 요구사항과 맞지 않은 도면'은 오작입니다.",
            "관리 > 스타일 편집기 > 제도 표준 에서 제3각법으로 바꾸고 "
            "표제란의 투상법 기호도 확인하세요.",
            "PROJECTION_LAYOUT"))

    name, w, h = REQUIRED_SHEET
    got = sh.get("sheet_name")
    sw, shh = sh.get("width_cm"), sh.get("height_cm")
    if got and got != name and got != PRINT_SHEET:
        out.append(_f(
            "DQ_SHEET_SIZE", SEV_FAIL,
            f"오작: 도면 크기 불일치 ({got})",
            f"도면 영역이 {got}로 잡힙니다. 요구 크기는 {name} "
            f"({w:.0f}×{h:.0f} mm)입니다. "
            "'요구한 도면 크기에 제도되지 않은 작품'은 오작입니다.",
            f"시트 우클릭 > 시트 편집 에서 {name}로 바꾸세요.",
            "PROJECTION_LAYOUT"))
    elif got == PRINT_SHEET:
        out.append(_f(
            "EX_SHEET_SIZE", SEV_WARN,
            f"도면 영역이 {PRINT_SHEET}입니다 (요구는 {name})",
            f"공개문제 요구사항은 '{name} 용지에 제도'이고 {PRINT_SHEET}는 "
            "출력 용지 크기입니다. 회차 지시사항이 다를 수 있어 오작으로는 "
            "보지 않지만, 지시사항을 확인하세요.",
            f"시트 크기를 {name}(594×420 mm)로 두고 출력만 "
            f"{PRINT_SHEET}로 하세요.",
            "NOTES_TITLE"))
    elif got is None and sw and shh:
        out.append(_f(
            "EX_SHEET_SIZE", SEV_WARN,
            f"도면 영역이 표준 크기가 아닙니다 ({sw * 10:.0f}×{shh * 10:.0f} mm)",
            f"윤곽선·도면 범위로 잰 크기가 A0~A4 어디에도 맞지 않습니다. "
            f"요구 크기는 {name}입니다.",
            f"시트 크기를 {name}(594×420 mm)로 맞추세요.",
            "NOTES_TITLE"))

    for v in sh.get("views", []):
        s = _scale_str(v)
        if s and s not in STANDARD_SCALES:
            out.append(_f(
                "DQ_SCALE", SEV_FAIL, f"오작 위험: 비표준 척도 {s} ({v.get('name')})",
                f"척도 {s}는 KS 표준 척도가 아닙니다.",
                "뷰 속성에서 1:1, 1:2, 2:1 같은 표준 척도로 변경하세요.",
                "PROJECTION_LAYOUT", 0, {"view": v.get("name")}))
            break
    return out


def _fit_states(facts):
    """치수 문자마다 (원문, 판정). 끼워맞춤 검사 셋이 같이 쓴다."""
    dims = _sheet_of(facts).get("dims", [])
    return [(plain_dim_text(d.get("text")), text_tolerance_state(d.get("text")))
            for d in dims]


# 끼워맞춤 기호의 구멍/축 구분. 대문자는 구멍, 소문자는 축이다.
# 뒤에 붙는 숫자는 IT 등급(01, 0, 1~18)이라 등급까지 봐야 나사(M6x1)와 안 섞인다.
_FIT_SYMBOL = re.compile(
    r"(?<=\d)\s*([A-Za-z]{1,2})(0?[1-9]|1[0-8])(?![\d.])")


def _fit_symbols(facts):
    """치수 문자에서 끼워맞춤 기호만 (기호, 구멍인가) 로 뽑는다."""
    out = []
    for text, state in _fit_states(facts):
        if state != "fit":
            continue
        for letters, grade in _FIT_SYMBOL.findall(text):
            out.append((letters + grade, letters.isupper()))
    return out


def _fits(facts):
    """오작 5·6 — 끼워맞춤 공차 기호.

    공개된 수험자 유의사항의 오작 조건에 두 줄이 따로 있다.
      5. 끼워맞춤 공차 기호를 부품도에 기입하지 않거나 부정확하게 지시한 경우
      6. 끼워맞춤 공차의 구멍 기호(대문자)와 축 기호(소문자)를 구분하지 않은 경우
    전에는 5번을 6점짜리 감점(`EX_NO_FIT`)으로만 다뤘고 6번은 검사가 없었다."""
    if not _sheet_of(facts).get("dims"):
        return []
    symbols = _fit_symbols(facts)
    if not symbols:
        return [_f(
            "DQ_NO_FIT", SEV_FAIL, "오작: 끼워맞춤 공차 기호 없음",
            "H7, js5, h6 같은 끼워맞춤 공차 기호가 하나도 없습니다. "
            "'끼워맞춤 공차 기호를 부품도에 기입하지 않은 도면'은 오작(실격)입니다.",
            "결합되는 치수에 끼워맞춤 기호를 넣으세요. "
            "예) 베어링 축 Ø17js5, 커버 구멍 Ø47H7",
            "TOLERANCE")]
    # 오작 6번(구멍 대문자·축 소문자 미구분)은 검사하지 않는다. 만들어서 실제
    # 도면 30장에 대 봤더니 "기호가 전부 대문자면 구분 안 한 것" 이라는 규칙이
    # 본체만 그린 부품도 3장을 실격시켰다 — 구멍(H8·JS9)만 있는 것이 맞는
    # 도면이었다. 어느 치수가 구멍이고 어느 것이 축인지는 DXF 로 못 가른다.
    # 없는 오작을 만드는 것이 이 서비스에서 가장 나쁜 오류라 검사를 접었다.
    return []


def _dimensions(facts):
    sh = _sheet_of(facts)
    dims, missing = sh.get("dims", []), sh.get("undimensioned", [])
    if not dims:
        return [_f("EX_NO_DIMS", SEV_ERROR, "치수가 하나도 없음",
                   "도면에 치수가 전혀 기입되지 않았습니다. 치수 기입 15점을 "
                   "전부 잃습니다.",
                   "주석 > 치수 로 주요 치수를 기입하세요.", "DIMENSIONS", 15)]
    # 뷰마다 치수가 붙었는지는 보지 않는다. KS B 0001 은 "하나의 치수는 도면 내
    # 단 한 곳에만 기입한다" 가 기본이고, 치수는 주 투상도(정면도)에 모으라고
    # 한다. 우측면도에 치수가 없어도 그 형상의 치수가 정면도에 있으면 기입한
    # 것이다. 아래 미치수 구멍 검사는 **도면 전체의 치수값**과 대보므로 이
    # 원칙을 이미 지킨다 — 다른 뷰에 있는 치수도 찾는다.
    n = sum(c.get("count", 1) for c in missing)
    if not n:
        return []
    return [_f(
        "EX_DIM_MISSING", SEV_ERROR, f"치수 누락 의심 {n}곳",
        "치수가 붙지 않은 원/구멍이 있습니다. 치수 누락은 직접 감점입니다. "
        + ", ".join(f"Ø{c['diameter_mm']:.1f}" for c in missing[:6]),
        "해당 형상에 치수를 추가하세요. 같은 크기 구멍이 여러 개면 "
        "'4-Ø6'처럼 개수를 묶어 한 번만 기입합니다.",
        "DIMENSIONS", min(15, n * 2))]


def _tolerance(facts):
    sh = _sheet_of(facts)
    dims = sh.get("dims", [])
    if not dims:
        return []
    states = [text_tolerance_state(d.get("text")) for d in dims]
    toleranced = sum(1 for d, s in zip(dims, states)
                     if d.get("tol_type") not in (None, "none") or s in ("explicit", "fit"))
    out = []
    # 끼워맞춤 기호가 아예 없는 것은 감점이 아니라 오작이라 `_fits` 가 본다.
    #
    # 공차 비율만으로는 판정하면 안 된다. KS B ISO 2768-1 은 **주서에 일반공차를
    # 적어 두면 개별 공차가 없는 치수는 그 일반공차를 따른다** 고 한다. 그러니
    # 공차가 붙은 치수가 적은 것 자체는 정상이다. 전에 쓰던 "20% 미만" 이라는
    # 값은 근거가 없었고, 실제 수험생 도면 30장 중 27장에서 떴다(중앙값 15.8%).
    #
    # 진짜 문제는 **일반공차 선언도 없고 개별 공차도 거의 없는** 경우다.
    # 그때는 치수에 공차가 아예 정의되지 않는다.
    notes = " ".join(facts.get("notes_text") or [])
    has_general = bool(re.search(GENERAL_TOL_RE, notes))
    if not has_general and toleranced / len(dims) < MIN_TOLERANCED_RATIO:
        out.append(_f(
            "EX_TOL_FEW", SEV_WARN,
            f"공차가 정의되지 않은 치수가 많습니다 ({toleranced}/{len(dims)}개만 지정)",
            "주서에 일반공차(KS B ISO 2768) 선언이 없고, 개별 공차가 붙은 치수도 "
            f"{toleranced}개뿐입니다. 둘 다 없으면 나머지 치수는 공차가 아예 "
            "정해지지 않습니다.",
            "주서에 '1. 일반공차 - 가) 가공부: KS B ISO 2768-m' 을 넣으세요. "
            "그러면 개별 공차가 없는 치수는 일반공차를 따릅니다.",
            "TOLERANCE", 2))
    return out


def _surface(facts):
    sh = _sheet_of(facts)
    syms = sh.get("surface_symbols", [])
    n = sh.get("counts", {}).get("SurfaceTextureSymbols", len(syms))
    if n == 0:
        return []
    out = []
    empty = [s for s in syms if not s.get("no_machining")
             and not (s.get("max") or s.get("min") or s.get("method"))]
    if empty:
        out.append(_f(
            "EX_SURFACE_EMPTY", SEV_ERROR, f"거칠기 값이 비어 있는 기호 {len(empty)}개",
            f"표면거칠기 기호 {n}개 중 {len(empty)}개에 값이 없습니다. "
            "기호만 있고 값이 없으면 가공 지시가 성립하지 않습니다.",
            "기호를 더블클릭해 값을 넣으세요. 예) w/x/y 또는 Ra 1.6, Ra 6.3.",
            "SURFACE", min(5, len(empty))))
    values = {s.get("max") for s in syms if s.get("max")}
    if len(values) == 1 and n >= 3:
        out.append(_f(
            "EX_SURFACE_UNIFORM", SEV_WARN,
            f"거칠기 값이 {next(iter(values))!r} 한 종류뿐",
            "모든 면에 같은 거칠기가 지정되어 있습니다. 끼워맞춤면·베어링 접촉면과 "
            "일반 가공면은 다듬질 정도를 구분해야 합니다.",
            "기능에 따라 나누세요. 예) 끼워맞춤면 y, 일반 가공면 x, 흑피면 제거가공 불가.",
            "SURFACE", 3))
    if n < MIN_SURFACE_SYMBOLS:
        out.append(_f(
            "EX_SURFACE_FEW", SEV_WARN, f"표면거칠기 기호가 {n}개뿐",
            "가공면 대비 기호 수가 적습니다. 기능면마다 기입되어야 합니다.",
            "끼워맞춤면·베어링 접촉면·미끄럼면에 각각 기입하세요.",
            "SURFACE", 4))
    # 기호를 넣고도 비교표를 빠뜨리는 것은 따로 감점된다. 면에 적은 w·x·y 가
    # 각각 어느 거칠기인지는 비교표가 있어야 읽을 수 있다.
    if not sh.get("roughness_table"):
        out.append(_f(
            "EX_NO_ROUGH_TABLE", SEV_WARN, "표면거칠기 비교표가 없습니다",
            f"면에 거칠기 기호 {n}개를 적었는데 다듬질 구분을 정의하는 "
            "비교표를 못 찾았습니다. 비교표가 없으면 w·x·y 가 각각 어느 "
            "거칠기인지 알 수 없습니다.",
            "도면 위쪽 빈 곳에 √( √w , √x , √y ) 형태의 비교표를 넣고, "
            "주서에 다듬질 정도를 정의하세요.",
            "SURFACE", 2))
    return out


def _geometric(facts):
    sh = _sheet_of(facts)
    fcfs = sh.get("geometric_tols", [])
    n = sh.get("counts", {}).get("FeatureControlFrames", len(fcfs))
    if n == 0:
        return []
    out = []
    if fcfs:
        if all(not g.get("datums") for g in fcfs):
            out.append(_f(
                "EX_FCF_NO_DATUM", SEV_ERROR, "기하공차에 데이텀이 하나도 없음",
                f"기하공차 {len(fcfs)}개 모두 데이텀 참조가 비어 있습니다. "
                "직각도·평행도·동심도·위치도·흔들림은 데이텀 없이는 의미가 없습니다.",
                "주요 축이나 면에 데이텀(A, B...)을 지정한 뒤 프레임의 데이텀 칸에 넣으세요.",
                "GEOMETRIC", 5))
        blank = [g for g in fcfs if not g.get("tolerance")]
        if blank:
            out.append(_f(
                "EX_FCF_NO_VALUE", SEV_ERROR, f"공차값이 비어 있는 기하공차 {len(blank)}개",
                "기호만 있고 공차값이 없습니다.",
                "프레임을 더블클릭해 공차값을 입력하세요. 예) 0.011",
                "GEOMETRIC", 3))
    if n < 2:
        out.append(_f(
            "EX_FCF_FEW", SEV_WARN, f"기하공차가 {n}개뿐",
            "보통 데이텀 기준으로 동심도·직각도·평행도 등 2개 이상이 요구됩니다.",
            "데이텀 A 기준 동심도(◎), 단면의 직각도(⊥) 등을 추가하세요.",
            "GEOMETRIC", 4))
    return out


def _notes(facts):
    sh = _sheet_of(facts)
    notes = " ".join(facts.get("notes_text") or [])
    if not notes.strip():
        return [_f(
            "EX_NO_NOTES", SEV_ERROR, "주서 없음",
            "주서(일반 주기)가 없습니다. 일반공차·모떼기·열처리·표면처리를 "
            "명시하지 않으면 감점됩니다.",
            "예) 1. 일반공차 - 가) 가공부: KS B ISO 2768-m ...",
            "NOTES_TITLE", 8)]
    out = []
    for label, pat in REQUIRED_NOTE_PATTERNS:
        if not re.search(pat, notes, re.I):
            out.append(_f(
                "EX_NOTE_ITEM", SEV_WARN, f"주서에 '{label}' 항목이 없음",
                f"주서에서 {label} 관련 문구를 찾지 못했습니다.",
                {"일반공차": "'1. 일반공차 - 가) 가공부: KS B ISO 2768-m'을 추가하세요.",
                 "표면거칠기 표기": "주서에 다듬질 구분(w/x/y 또는 Ra 값)을 정의하세요.",
                 "모떼기/라운드": "'도시되고 지시없는 모떼기는 1×45°, 필렛과 라운드 R3' "
                                  "같은 문구를 추가하세요."}.get(label, "주서를 보완하세요."),
                "NOTES_TITLE", 2))
    if not (sh.get("title_block") or sh.get("border")):
        out.append(_f(
            "EX_NO_TITLEBLOCK", SEV_ERROR, "표제란·도면양식 없음",
            "표제란이나 도면 양식(윤곽선·중심마크 포함)이 확인되지 않습니다.",
            "시트 우클릭 > 표제란 삽입, 윤곽선과 중심마크를 배치하세요.",
            "NOTES_TITLE", 3))
    return out


def _spec_table(facts):
    """기어·스프링 요목표. 주서와 따로 본다 — `_notes` 는 주서가 없으면
    거기서 끝나 버려서 그 안에 두면 주서 없는 도면에서 아예 안 돌았다."""
    sh = _sheet_of(facts)
    needs = sh.get("needs_spec") or []
    if not needs or sh.get("spec_tables"):
        return []
    return [_f(
        "EX_NO_SPEC_TABLE", SEV_ERROR, f"{needs[0]} 요목표가 없습니다",
        f"부품란에 {', '.join(needs[:3])} 가 있는데 요목표를 못 찾았습니다. "
        "기어·스프링은 형상 치수만으로 만들 수 없어서 잇수·모듈·압력각 "
        "같은 값을 요목표로 따로 적어야 합니다.",
        "도면 빈 곳에 요목표를 그리고 기어 치형·모듈·압력각·잇수·"
        "피치원 지름·다듬질 방법·정밀도를 채우세요.",
        "NOTES_TITLE", 3, {"parts": needs})]


def _material(facts):
    notes = " ".join(facts.get("notes_text") or [])
    if re.search(r"열처리|HRC|HB\b|담금질|침탄|질화|도금|도장", notes, re.I):
        return []
    return [_f(
        "EX_NO_HEAT", SEV_WARN, "열처리·표면처리 지시 없음",
        "주서에 열처리나 표면처리 지시가 없습니다. 축·기어 같은 부품은 "
        "'재료 선택과 처리'에서 감점될 수 있습니다.",
        "필요한 부품에 '전체 열처리 HRC 50±0.2' 같은 지시를 추가하세요. "
        "재료 기호(SM45C, SCM415, GC200)는 부품란에 기입합니다.",
        "MATERIAL", 3)]


_DETAIL_LABEL = re.compile(r"상세|확대|DETAIL|^\s*[A-Z]\s*\(", re.I)


def _is_detail_label(view):
    """상세도·확대도는 척도가 달라도 맞다. Inventor 상세도 이름표는 `C ( 5 : 1 )`
    처럼 글자 하나고, 단면도는 `A-A` 처럼 둘이라 그것으로 가른다."""
    label = view.get("label", "")
    if not _DETAIL_LABEL.search(label):
        return False
    try:
        num, den = view["scale"].split(":")
        return float(num) > float(den)          # 확대만 봐준다
    except Exception:
        return False


def _sheet_form(facts):
    """표제란에 적어야 하는 것 — 각법 · 척도 · 재질 · (3D면) 질량.

    표제란 자체가 없으면 EX_NO_TITLEBLOCK 이 이미 말하므로 여기서는 침묵한다."""
    sh = _sheet_of(facts)
    if not sh.get("title_block"):
        return []
    fields = sh.get("fields") or {}
    out = []

    if facts.get("first_angle") is None:
        out.append(_f(
            "EX_NO_PROJECTION_MARK", SEV_WARN, "각법 표기가 없습니다",
            "표제란에서 '제3각법' 표기나 각법 기호를 못 찾았습니다. "
            "투상법 표기는 도면 필수 항목입니다.",
            "표제란 각법 칸에 '제3각법'을 적고 각법 기호도 같이 넣으세요.",
            "NOTES_TITLE"))

    scale = fields.get("scale")
    if not scale:
        out.append(_f(
            "EX_NO_SHEET_SCALE", SEV_WARN, "표제란에 척도 표기가 없습니다",
            "표제란 척도 칸을 못 찾았습니다. 척도는 표제란 필수 항목입니다.",
            f"표제란 척도 칸에 {REQUIRED_SCALE}(3D 등각투상도는 NS)을 적으세요.",
            "NOTES_TITLE"))
    elif not sh.get("is_isometric") and scale.replace(" ", "") != REQUIRED_SCALE:
        out.append(_f(
            "EX_SCALE_NOT_ONE", SEV_WARN, f"부품도 척도가 {scale}입니다",
            f"공개문제는 부품도를 척도 {REQUIRED_SCALE}로 요구합니다. "
            "회차 지시사항이 다르면 그쪽이 우선입니다.",
            f"표제란과 뷰 척도를 {REQUIRED_SCALE}로 맞추세요.",
            "NOTES_TITLE"))

    # 뷰 하나만 척도가 다른 것은 눈으로 잘 안 보인다. 인터뷰에서 실제로 나온 실수다
    # (전체 1:1인데 커버 뷰만 2:1). 2:1도 표준 척도라 DQ_SCALE에는 안 걸린다.
    if not sh.get("is_isometric"):
        odd = [v for v in sh.get("view_scales") or []
               if v.get("scale") != REQUIRED_SCALE and not _is_detail_label(v)]
        if odd:
            names = ", ".join(v["label"] for v in odd[:3])
            out.append(_f(
                "EX_VIEW_SCALE_MIXED", SEV_WARN,
                f"척도가 {REQUIRED_SCALE}가 아닌 뷰 {len(odd)}개",
                f"{names} — 부품도는 척도 {REQUIRED_SCALE} 요구입니다. "
                "확대·상세도로 일부러 다르게 뒀다면 그대로 두세요.",
                "뷰 속성에서 척도를 확인하고, 확대도가 아니면 "
                f"{REQUIRED_SCALE}로 되돌리세요.",
                "NOTES_TITLE", 0, {"labels": [v["label"] for v in odd]}))

    material = fields.get("material") or (facts.get("props") or {}).get("material")
    if not material:
        out.append(_f(
            "EX_NO_MATERIAL", SEV_WARN, "재료 기호가 없습니다",
            "표제란·부품란에서 재료 기호(SM45C, SCM415, GC250 같은 것)를 "
            "못 찾았습니다. 재료 기입은 '재료 선택과 처리' 채점 항목입니다.",
            "부품란 재질 칸에 KS 재료 기호를 부품마다 적으세요.",
            "MATERIAL", 2))

    if sh.get("is_isometric") and not fields.get("mass"):
        out.append(_f(
            "EX_NO_MASS", SEV_WARN, "등각투상도 부품란에 질량이 없습니다",
            "3D 렌더링 등각투상도는 부품란 비고에 질량을 g 단위(소수점 첫째자리 "
            "반올림)로 적어야 합니다.",
            "Inventor: 파일 > iProperties > 물리적 에서 재질을 지정하고 "
            "업데이트한 질량 값을 부품란 비고에 옮겨 적으세요.",
            "MATERIAL", 2))
    return out


# KS B 0001 은 선 굵기를 절대값으로 못 박지 않고 비로 정한다 —
# 가는 선 : 굵은 선 : 아주 굵은 선 = 1 : 2 : 4. 축척이 달라도 통하는 기준이라
# 절대값 대신 비를 본다. 실기 도면은 보통 윤곽선 0.7 · 외형선 0.5 ·
# 은선 0.35 · 중심선/치수선 0.25 · 해치 0.18 이다.
MIN_LINE_RATIO = 2.0
# KS A 0107 문자 크기 호칭. A 계열(2.24·3.15·4.5·6.3·9)과 ISO 계열
# (2.5·3.5·5·7·10)을 둘 다 인정한다. 실기 관행은 3.15~3.5 지만 **7mm 도 규격
# 안에 있는 크기**라 관행과 다르다는 이유로 틀렸다고 하지 않는다. 규격 계열에
# 아예 없는 크기와, 출력하면 못 읽는 크기만 본다.
TEXT_SIZES_MM = (2.24, 2.5, 3.15, 3.5, 4.5, 5.0, 6.3, 7.0, 9.0, 10.0, 14.0, 20.0)
TEXT_SIZE_TOL = 0.15
# KS A ISO 3098 은 도면 문자 최소 높이를 2.5mm 로 둔다. 그보다 작으면 축소
# 출력에서 읽을 수 없다.
MIN_TEXT_MM = 2.5


def _appearance(facts):
    """채점 항목 '도면 배치와 외관' 10점 중 기계가 잴 수 있는 것.

    '각 부품의 균형 배치' 5점은 여기서 보지 않는다. 실제 도면 30장을 재 보니
    표제란이 오른쪽 아래를 차지해 **멀쩡한 도면이 전부 왼쪽으로 치우쳐** 나왔다
    (x -0.10 ~ -0.31). 치우침만으로는 정상과 불량이 안 갈려서, 그 5점은
    투상도 AI 판정에 남겨 둔다. 없는 규칙을 만들어 붙이지 않는다."""
    sh = _sheet_of(facts)
    out = []

    lw = sh.get("line_widths") or {}
    # 색으로 나누고 출력할 때 펜 설정으로 굵기를 내는 도면은 DXF 에 굵기가
    # 안 들어 있다. 이것을 "굵기를 안 정했다" 와 구별할 수 없으므로 판정하지
    # 않는다 — 실기에서 흔히 쓰는 방식이라 단정하면 멀쩡한 도면을 잡는다.
    if lw.get("by_color"):
        pass
    elif not lw.get("layers"):
        out.append(_f(
            "EX_LINEWEIGHT_NONE", SEV_WARN, "레이어에 선 굵기가 지정되지 않았습니다",
            "레이어 어디에도 선 굵기가 정해져 있지 않고, 색으로 나눈 흔적도 "
            "없습니다. 이대로 출력하면 외형선과 치수선이 같은 굵기로 나옵니다.",
            "레이어 특성에서 윤곽선 0.7, 외형선 0.5, 은선 0.35, "
            "중심선·치수선 0.25, 해칭 0.18 mm 로 지정하세요. "
            "색으로 굵기를 주는 방식이면 출력 펜 설정을 확인하세요.",
            "APPEARANCE", 2))
    elif lw.get("ratio") is not None and lw["ratio"] < MIN_LINE_RATIO:
        out.append(_f(
            "EX_LINEWEIGHT_FLAT", SEV_ERROR,
            f"외형선과 가는 선의 굵기 차이가 작습니다 ({lw['ratio']}배)",
            f"외형선 {lw['outline_mm']}mm, 치수·중심선 {lw['thin_mm']}mm 로 "
            f"비가 {lw['ratio']}배입니다. KS 제도규격은 "
            f"가는 선 : 굵은 선 = 1 : 2 이상을 요구합니다. 굵기가 구분되지 "
            "않으면 도면을 읽을 수 없어 감점됩니다.",
            "외형선을 0.5mm, 치수선·중심선을 0.25mm 로 두면 정확히 2배입니다.",
            "APPEARANCE", 3, {"layers": lw.get("layers")}))

    ts = sh.get("text_sizes") or {}
    dim_mm = ts.get("dim_mm")
    if dim_mm and dim_mm < MIN_TEXT_MM:
        out.append(_f(
            "EX_TEXT_SIZE", SEV_ERROR, f"치수 문자가 {dim_mm}mm 로 너무 작습니다",
            f"도면 문자의 최소 높이는 {MIN_TEXT_MM}mm 입니다. "
            f"{dim_mm}mm 로는 출력했을 때 치수를 읽을 수 없습니다.",
            "치수 스타일 편집에서 문자 높이를 3.15 또는 3.5mm 로 바꾸세요.",
            "APPEARANCE", 2))
    elif dim_mm and not any(abs(dim_mm - k) <= TEXT_SIZE_TOL for k in TEXT_SIZES_MM):
        out.append(_f(
            "EX_TEXT_SIZE", SEV_WARN, f"치수 문자 크기가 {dim_mm}mm 입니다",
            "KS 문자 크기는 정해진 호칭 중에서 고릅니다 — "
            "2.24 · 2.5 · 3.15 · 3.5 · 4.5 · 5 · 6.3 · 7 · 9 · 10mm. "
            f"{dim_mm}mm 는 그 목록에 없습니다. 실기 도면의 치수 문자는 "
            "보통 3.15 또는 3.5mm 입니다.",
            "치수 스타일 편집에서 문자 높이를 3.5mm 로 바꾸세요.",
            "APPEARANCE", 1))

    # 윤곽선 밖은 채점하지 않는다. 채점은 도면 영역(윤곽선 안) 안에서 이뤄지고,
    # 틀 밖에 남은 선은 제출물의 일부가 아니다. 한때 감점으로 넣었다가 뺐다 —
    # 실제 도면에서 걸린 것이 윤곽선을 6mm 넘은 치수선 정도였다.
    return out


def _projection(facts):
    sh = _sheet_of(facts)
    counts, views = sh.get("counts", {}), sh.get("views", [])
    out = []
    layout = sh.get("layout") or {}
    # 배치를 좌표로 재서 제1각법 자리에만 뷰가 있으면 알린다. 표제란 각법 칸이
    # 비어 있어도 잡히는 유일한 경로다. 다만 저면도·좌측면도만 쓴 제3각법
    # 도면도 같은 모양이 되므로 오작(실격)으로는 보지 않는다 — 실격을 잘못
    # 부르는 것이 이 서비스에서 가장 나쁜 오류다.
    if layout.get("verdict") == "first" and facts.get("first_angle") is not False:
        out.append(_f(
            "EX_LAYOUT_FIRST_ANGLE", SEV_ERROR, "뷰 배치가 제1각법으로 보입니다",
            f"정면도({layout.get('front')})에 줄이 맞는 투상도가 "
            f"{', '.join(layout.get('spots') or [])} 쪽에만 있습니다. "
            "제3각법이면 평면도가 위, 우측면도가 오른쪽입니다. "
            "요구 투상법과 다르면 오작(실격)입니다.",
            "배치 > 투상도 로 평면도를 정면도 위, 우측면도를 정면도 오른쪽에 "
            "놓으세요. 저면도·좌측면도만 쓴 것이라면 그대로 두어도 됩니다.",
            "PROJECTION_LAYOUT", 6, {"front": layout.get("front")}))
    if len(views) < 2 and sh.get("views_known", True):
        out.append(_f(
            "EX_FEW_VIEWS", SEV_ERROR, f"투상도가 {len(views)}개뿐",
            "부품 형상을 표현하기에 투상도가 부족해 보입니다.",
            "정면도 기준으로 평면도·측면도, 필요시 단면도·상세도를 배치하세요.",
            "PROJECTION_LAYOUT"))
    if not counts.get("Centerlines", 0) and not counts.get("Centermarks", 0):
        out.append(_f(
            "EX_NO_CENTERLINE", SEV_WARN, "중심선·중심마크 없음",
            "원·구멍에 중심선이나 중심마크가 없습니다. KS 제도규격 위반입니다.",
            "주석 > 중심선/중심 표시 로 모든 원과 대칭 형상에 넣으세요.",
            "PROJECTION_LAYOUT"))
    for v in views:
        if (v.get("is_detail") or v.get("is_section")) and v.get("show_label") is False:
            kind = "상세도" if v.get("is_detail") else "단면도"
            out.append(_f(
                "EX_VIEW_NO_LABEL", SEV_ERROR,
                f"{kind}에 표시 문자가 없음: {v.get('name')}",
                f"{kind}는 어느 부분인지 알 수 있게 문자(A, B...)와 척도를 표기해야 합니다.",
                "뷰 우클릭 > 편집 에서 '레이블 표시'와 '척도 표시'를 켜세요.",
                "PROJECTION_LAYOUT", 0, {"view": v.get("name")}))
    for v in views:
        if v.get("scale") not in (None, 1.0) and v.get("show_scale") is False:
            out.append(_f(
                "EX_VIEW_NO_SCALE", SEV_WARN,
                f"척도 표기 없는 확대/축소 뷰: {v.get('name')} ({_scale_str(v)})",
                "도면 전체 척도와 다른 뷰는 그 옆에 척도를 함께 적어야 합니다.",
                "뷰 편집에서 '척도 표시'를 켜세요.",
                "PROJECTION_LAYOUT", 0, {"view": v.get("name")}))
    return out


PRODUCERS = (_disqualifiers, _fits, _dimensions, _tolerance, _surface,
             _geometric, _notes, _spec_table, _material, _sheet_form, _appearance,
             _projection)
_ORDER = {SEV_FAIL: 0, SEV_ERROR: 1, SEV_WARN: 2, SEV_INFO: 3}


def check_catalog():
    return [{"id": cid, "label": label, "group": grp,
             "group_label": "오작(실격)" if grp == "오작" else RUBRIC_LABEL.get(grp, grp),
             "default": on}
            for cid, label, grp, on in CHECKS]


def grade(facts: Facts, enabled: Iterable[str] | None = None,
          ai_projection: dict[str, Any] | None = None
          ) -> tuple[list[Finding], Scorecard]:
    """Score facts and return (findings, scorecard).

    A check that raises does not stop the rest: the failure is recorded as an
    EX_RULE_ERROR finding, so one bad drawing cannot take the whole grade down."""
    on = ALL_CHECK_IDS if enabled is None else (set(enabled) & ALL_CHECK_IDS)

    findings = []
    for fn in PRODUCERS:
        try:
            findings += fn(facts)
        except Exception as e:
            findings.append(_f("EX_RULE_ERROR", SEV_INFO,
                               f"검사 오류: {fn.__name__}", f"{type(e).__name__}: {e}",
                               "개발자에게 알려주세요."))
    if ai_projection:
        findings += ai_projection["findings"]
    findings = [f for f in findings
                if f["code"] in on or f["code"] == "EX_RULE_ERROR"]

    ai_scored = bool(ai_projection) and "AI_PROJECTION" in on

    items, got, mx_total = [], 0, 0
    for code, label, mx, mode in RUBRIC:
        if mode == "review" and not (ai_scored and code == "PROJECTION_LAYOUT"):
            items.append({"code": code, "label": label, "max": mx,
                          "score": None, "mode": "review"})
            continue
        if mode == "review":
            mode = "ai"
        lost = sum(f["deduct"] for f in findings if f.get("item") == code)
        score = max(0, mx - lost)
        got += score
        mx_total += mx
        items.append({"code": code, "label": label, "max": mx,
                      "score": score, "mode": mode})

    fails = [f for f in findings if f["severity"] == SEV_FAIL]
    findings.sort(key=lambda f: _ORDER.get(f["severity"], 9))
    items.sort(key=lambda i: -i["max"])

    return findings, {
        "auto_score": got, "auto_max": mx_total,
        "percent": round(got / mx_total * 100, 1) if mx_total else 0.0,
        "review_points": sum(i["max"] for i in items if i["mode"] == "review"),
        "ai_verdict": ai_projection["verdict"] if ai_scored else None,
        "ai_verdict_i18n": ai_projection.get("verdict_i18n") if ai_scored else None,
        "ai_model": ai_projection["model"] if ai_scored else None,
        "items": items,
        "disqualified": bool(fails),
        "disqualifiers": [f["title"] for f in fails],
        "enabled_count": len(on), "total_checks": len(ALL_CHECK_IDS),
        "summary": {
            "total": len(findings), "fail": len(fails),
            "error": sum(1 for f in findings if f["severity"] == SEV_ERROR),
            "warn": sum(1 for f in findings if f["severity"] == SEV_WARN),
            "info": sum(1 for f in findings if f["severity"] == SEV_INFO),
        },
    }

