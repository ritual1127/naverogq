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
STANDARD_SCALES = {"1:1", "1:2", "1:2.5", "1:5", "1:10", "1:20", "1:50", "1:100",
                   "2:1", "5:1", "10:1", "20:1", "50:1"}
REQUIRED_NOTE_PATTERNS = [
    ("일반공차", r"일반\s*공차|2768"),
    ("표면거칠기 표기", r"표면\s*거칠기|거칠기|√|Ra|Ry|Rz|다듬질"),
    ("모떼기/라운드", r"모[떼따]기|라운드|필렛|45\s*°|45°"),
]
MIN_SURFACE_SYMBOLS = 3
MIN_FCF = 1

SEV_FAIL, SEV_ERROR, SEV_WARN, SEV_INFO = "fail", "error", "warn", "info"

RUBRIC = [
    ("PROJECTION_LAYOUT", "투상도 선택과 배열", 30, "review"),
    ("DIMENSIONS", "치수 기입", 15, "auto"),
    ("TOLERANCE", "끼워맞춤 공차·치수공차", 10, "auto"),
    ("SURFACE", "표면거칠기", 10, "auto"),
    ("GEOMETRIC", "형상(기하)공차", 10, "auto"),
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

    ("EX_NO_DIMS", "치수가 하나도 없음", "DIMENSIONS", True),
    ("EX_DIM_MISSING", "치수 없는 원·구멍", "DIMENSIONS", True),

    ("EX_NO_FIT", "끼워맞춤 공차 기호 없음", "TOLERANCE", True),
    ("EX_TOL_FEW", "공차 지정된 치수가 너무 적음", "TOLERANCE", True),

    ("EX_SURFACE_EMPTY", "거칠기 값이 빈 기호", "SURFACE", True),
    ("EX_SURFACE_UNIFORM", "거칠기가 한 종류뿐(다듬질 구분 없음)", "SURFACE", True),
    ("EX_SURFACE_FEW", "거칠기 기호 수가 부족", "SURFACE", True),

    ("EX_FCF_NO_DATUM", "기하공차에 데이텀 없음", "GEOMETRIC", True),
    ("EX_FCF_NO_VALUE", "기하공차 값이 빔", "GEOMETRIC", True),
    ("EX_FCF_FEW", "기하공차 개수 부족", "GEOMETRIC", True),

    ("EX_NO_NOTES", "주서 없음", "NOTES_TITLE", True),
    ("EX_NOTE_ITEM", "주서 필수 문구 누락", "NOTES_TITLE", True),
    ("EX_NO_TITLEBLOCK", "표제란·도면양식 없음", "NOTES_TITLE", True),
    ("EX_SHEET_SIZE", "도면 영역이 요구 크기와 다름", "NOTES_TITLE", True),
    ("EX_NO_PROJECTION_MARK", "각법 표기 없음", "NOTES_TITLE", True),
    ("EX_NO_SHEET_SCALE", "표제란에 척도 표기 없음", "NOTES_TITLE", True),
    ("EX_SCALE_NOT_ONE", "부품도 척도가 1:1이 아님", "NOTES_TITLE", True),
    ("EX_VIEW_SCALE_MIXED", "뷰마다 척도가 다름", "NOTES_TITLE", True),

    ("EX_NO_HEAT", "열처리·표면처리 지시 없음", "MATERIAL", True),
    ("EX_NO_MATERIAL", "재료 기호 기입 없음", "MATERIAL", True),
    ("EX_NO_MASS", "3D 등각투상도 부품란에 질량 없음", "MATERIAL", True),

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


def _dimensions(facts):
    sh = _sheet_of(facts)
    dims, missing = sh.get("dims", []), sh.get("undimensioned", [])
    if not dims:
        return [_f("EX_NO_DIMS", SEV_ERROR, "치수가 하나도 없음",
                   "도면에 치수가 전혀 기입되지 않았습니다. 치수 기입 15점을 "
                   "전부 잃습니다.",
                   "주석 > 치수 로 주요 치수를 기입하세요.", "DIMENSIONS", 15)]
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
    fits = sum(1 for s in states if s == "fit")
    toleranced = sum(1 for d, s in zip(dims, states)
                     if d.get("tol_type") not in (None, "none") or s in ("explicit", "fit"))
    out = []
    if fits == 0:
        out.append(_f(
            "EX_NO_FIT", SEV_ERROR, "끼워맞춤 공차 기호가 없음",
            "H7, js5, h6 같은 끼워맞춤 공차 기호가 하나도 없습니다. "
            "베어링·축·키홈이 있는 과제에서는 반드시 필요합니다.",
            "결합되는 치수에 끼워맞춤 기호를 넣으세요. "
            "예) 베어링 축 Ø17js5, 커버 구멍 Ø47H7",
            "TOLERANCE", 6))
    if toleranced / len(dims) < 0.2:
        out.append(_f(
            "EX_TOL_FEW", SEV_WARN,
            f"공차 지정 치수가 {toleranced}/{len(dims)}개뿐",
            "공차가 지정된 치수 비율이 낮습니다. 기능 치수에는 공차가 필요합니다.",
            "조립·끼워맞춤에 관여하는 치수부터 공차를 지정하세요.",
            "TOLERANCE", 4))
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


def _projection(facts):
    sh = _sheet_of(facts)
    counts, views = sh.get("counts", {}), sh.get("views", [])
    out = []
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


PRODUCERS = (_disqualifiers, _dimensions, _tolerance, _surface,
             _geometric, _notes, _material, _sheet_form, _projection)
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

