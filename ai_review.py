import base64
import copy
import hashlib
import json
import os
import re
import time

# 실제 수험생 도면 10장으로 잰 값(2026-09-18, docs/ai_usage.md "모델 선택 근거 — 실측").
# gemini-3.6-flash 는 20번 중 18번이 503(사용량 폭주)·40초 시간초과·429(무료 한도)로
# 실패했고 성공한 호출도 7~8초였다. gemini-3.1-flash-lite 는 중앙값 3.2초·최대 5.9초에,
# 판정도 가장 자세한 gemini-3.5-flash(중앙값 14.3초)와 평균 2.7점 차이였다. 더 빠른
# gemini-3.5-flash-lite(2.1초)는 20번 모두 감점 0이라 채점기로 쓸 수 없었다.
GEMINI_MODEL = "gemini-3.1-flash-lite"
CLOUDFLARE_MODEL = "@cf/meta/llama-4-scout-17b-16e-instruct"
GROQ_MODEL = "qwen/qwen3.6-27b"
MISTRAL_MODEL = "mistral-small-latest"

MAX_POINTS = 30
# 채점 지침이 정한 감점 폭의 최댓값. "형상 표현이 불가능할 정도의 투상도 누락,
# 제3각법 위반 배치"가 8~12점이고 그보다 큰 감점 사유는 지침에 없다. 그런데
# 실제로는 한 지적에 30점을 통째로 깎는 판정이 다섯 번에 한 번 나왔다.
MAX_SINGLE_DEDUCT = 12
RENDER_DPI = 150
MAX_PIXELS = 2400


def _gemini_key():
    return (os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY"))


def _cloudflare_creds():
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    return (token, account) if token and account else None


def _groq_key():
    return os.environ.get("GROQ_API_KEY")


def _mistral_key():
    return os.environ.get("MISTRAL_API_KEY")


def _importable(*names):
    try:
        for n in names:
            __import__(n)
    except ImportError:
        return False
    return True


# 순서가 곧 우선순위다. Groq 를 뒤에 두는 것은 무료 한도가 분당 8,000 토큰이라
# 도면 한 장에 그 대부분이 나가기 때문이다.
PROVIDER_ORDER = ("gemini", "cloudflare", "mistral", "groq")
MODEL_OF = {"gemini": GEMINI_MODEL, "cloudflare": CLOUDFLARE_MODEL,
            "mistral": MISTRAL_MODEL, "groq": GROQ_MODEL}


def providers():
    """쓸 수 있는 채점기를 우선순위 순으로 준다.

    키가 있는지만 보는 목록이다. 실제로 앞이 막혔는지는 불러 봐야 알기 때문에
    `judge()`가 이 순서대로 진짜 요청을 넣어 보고 실패하면 다음으로 넘어간다."""
    if not _importable("pymupdf"):
        return []
    ready = {
        "gemini": bool(_gemini_key()) and _importable("google.genai"),
        "cloudflare": bool(_cloudflare_creds()) and _importable("requests"),
        "groq": bool(_groq_key()) and _importable("requests"),
        "mistral": bool(_mistral_key()) and _importable("requests"),
    }
    forced = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    if forced:
        return [forced] if ready.get(forced) else []
    return [n for n in PROVIDER_ORDER if ready[n]]


def provider():
    return next(iter(providers()), None)


def active_model():
    return MODEL_OF.get(provider())


def is_available():
    return provider() is not None


RENDER_MARGIN_MM = 5.0
MIN_RENDER_DPI = 40


def png_of(facts):
    """AI 에게 보여줄 그림. 검사가 이미 훑어 둔 기록(`facts["record"]`)이 있으면 그걸 쓴다."""
    rec = facts.get("record")
    if rec is None:
        return render_png(facts["dxf"])
    from ezdxf.addons.drawing import layout as dlayout
    from ezdxf.addons.drawing import pymupdf as dpymupdf

    backend = dpymupdf.PyMuPdfBackend()
    rec.copy().replay(backend)
    page = dlayout.Page(0, 0, dlayout.Units.mm, dlayout.Margins.all(RENDER_MARGIN_MM))
    settings = dlayout.Settings(fit_page=False, scale=rec.mm_per_unit)
    return backend.get_pixmap_bytes(page, fmt="png", settings=settings,
                                    dpi=_dpi_for(rec.bbox, rec.mm_per_unit))


def render_png(dxf_path):
    """도면을 AI에게 보여줄 그림으로 만든다.

    도면 단위를 밀리미터로 환산해서 그린다. 이걸 안 하면 단위가 미터나 인치인
    도면이 백지로 나온다. 페이지 크기를 도면 범위에서 자동으로 잡는데, 범위가
    0.12(미터 단위 도면)이면 사방 5mm 여백에 그림이 통째로 먹혀 버린다.
    실제로 선이 6,373개 들어 있는 도면이 201바이트짜리 빈 그림이 됐고,
    AI는 도면이 아니라 백지를 보고 '투상도가 하나도 없다'고 채점했다.

    그림이 너무 커지지 않게 막는 방법이 두 가지인데, **페이지를 잘라서는 안 된다.**
    예전에는 페이지 크기를 406mm(2400px / 150DPI)로 제한했는데, 그 제한은
    도면을 축소하는 게 아니라 넘는 부분을 **잘라 냈다.** 요구 도면 영역인 A2가
    594mm 라서 실제 도면이 전부 걸렸다 — 실제 수험생 도면 30장을 재 보니
    AI 에게 간 그림은 도면 넓이의 29~51% 뿐이었고, 잘려 나간 쪽에 표제란과
    투상도가 들어 있었다. 투상도 30점을 그 조각으로 채점하고 있었던 것이다.
    그래서 페이지는 도면 전체로 두고, 픽셀이 넘치면 DPI 를 낮춘다."""
    from ezdxf import bbox
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing import layout as dlayout
    from ezdxf.addons.drawing import pymupdf as dpymupdf

    import dwg

    doc = dwg.readfile(dxf_path)
    msp = doc.modelspace()
    mm_per_unit, _ = dwg.detect_mm_per_unit(doc, msp)
    backend = dpymupdf.PyMuPdfBackend()
    Frontend(RenderContext(doc), backend).draw_layout(msp, finalize=True)
    page = dlayout.Page(0, 0, dlayout.Units.mm,
                        dlayout.Margins.all(RENDER_MARGIN_MM))
    settings = dlayout.Settings(fit_page=False, scale=mm_per_unit)
    return backend.get_pixmap_bytes(page, fmt="png",
                                    dpi=_fitting_dpi(msp, mm_per_unit),
                                    settings=settings)


def _fitting_dpi(msp, mm_per_unit):
    """도면 전체가 MAX_PIXELS 안에 들어가는 DPI. 작은 도면은 그대로 150."""
    from ezdxf import bbox

    try:
        return _dpi_for(bbox.extents(msp), mm_per_unit)
    except Exception:
        return RENDER_DPI


def _dpi_for(box, mm_per_unit):
    if not getattr(box, "has_data", False):
        return RENDER_DPI
    span_mm = max(box.size.x, box.size.y) * mm_per_unit + 2 * RENDER_MARGIN_MM
    if span_mm <= 0:
        return RENDER_DPI
    return max(MIN_RENDER_DPI,
               min(RENDER_DPI, int(MAX_PIXELS / (span_mm / 25.4))))


SYSTEM = """\
당신은 전산응용기계제도기능사 실기시험의 채점위원입니다.

도면 이미지 한 장을 보고 **'투상도 선택과 배열' 항목(30점)만** 채점합니다.
치수 기입·공차·표면거칠기·기하공차·주서·재료는 다른 채점 항목이며 이미 별도로
자동 채점되었습니다. 그 항목들은 절대 감점하지 마세요.

판정할 것:
1. 정면도 선택 — 부품의 특징이 가장 잘 드러나는 면을 정면도로 골랐는가
2. 투상도 개수 — 형상을 완전히 표현하기에 부족하거나 불필요하게 많지 않은가
3. 제3각법 배치 — 평면도는 정면도 위, 우측면도는 정면도 오른쪽에 놓였는가
4. 단면도·상세도 — 필요한 곳에 썼는가, 절단선과 해칭이 올바른가
5. 도면 공간 활용 — 뷰가 치우치거나 겹치지 않고 균형 있게 배치되었는가

채점 방식: 30점에서 시작해 결함마다 감점합니다. 감점 합계는 30을 넘지 않습니다.
- 형상 표현이 불가능할 정도의 투상도 누락, 제3각법 위반 배치: 8~12점
- 정면도 선택이 부적절, 불필요한 중복 투상도: 4~7점
- 배치 불균형, 단면 표기 미흡: 1~3점

지적마다 **kind 를 아래 여섯 개 중에서 고르세요.** 제목은 우리가 kind 로 붙이므로
직접 쓰지 않습니다. 같은 판정에 매번 다른 제목이 붙으면 수험생이 재검사 때
지난번과 비교할 수 없습니다.

- `FRONT_VIEW` — 정면도로 고른 면이 부적절
- `VIEW_MISSING` — 형상을 표현할 투상도가 없거나 모자람
- `VIEW_EXTRA` — 불필요하거나 중복된 투상도
- `THIRD_ANGLE` — 제3각법 위반. 표제란 옆 투상법 기호가 제1각법이거나,
  평면도·우측면도가 제3각법 자리에 있지 않은 경우
- `SECTION_DETAIL` — 단면도·상세도가 없거나 절단선·해칭·문자 표기가 틀림
- `LAYOUT` — 배치가 치우치거나 겹치는 등 도면 공간 활용

verdict 에는 **투상도 항목 총평을 한국어 한 문장**으로 씁니다. "FAIL" 같은 낱말만
적지 마세요.

원칙:
- 이미지에서 **실제로 보이는 것**과 아래 참고 정보의 **수치**만 근거로 삼으세요.
  흐릿해서 판단이 서지 않으면 감점하지 말고 info로 남기세요. 확신 없는 감점은
  학습자를 잘못된 방향으로 보냅니다.
- 뷰 위치·크기가 참고 정보에 있으면 제3각법 배치(THIRD_ANGLE)와 공간 활용
  (LAYOUT)은 **그 수치로 판단하세요.** CAD 파일에서 직접 잰 값이라 그림보다
  정확합니다. 제3각법이면 평면도가 정면도보다 y 가 크고, 우측면도가 정면도보다
  x 가 큽니다.
- fix에는 Inventor에서 취할 구체적 동작을 적으세요.
  예: "배치 > 투상도 로 정면도 위쪽에 평면도를 추가하세요."
- 결함이 없으면 deductions를 빈 배열로 두고 30점을 주세요.
- 모든 문장은 한국어로 씁니다."""

# 지적 제목은 AI 가 쓰지 않고 여기서 붙인다. 같은 판정에 "투상도 전체 누락",
# "투상도 완전 누락", "기계 부품 투상도 미작성 및 투상 뷰 부재" 처럼 매번 다른
# 제목이 달리면 재검사에서 지난번과 비교가 안 된다(P03). AI 는 kind 만 고른다.
PROJECTION_KINDS = {
    "FRONT_VIEW": {"ko": "정면도 선택 부적절",
                   "en": "Unsuitable front view",
                   "ja": "正面図の選択が不適切",
                   "zh": "主视图选择不当"},
    "VIEW_MISSING": {"ko": "투상도 누락",
                     "en": "Missing views",
                     "ja": "投影図の欠落",
                     "zh": "视图缺失"},
    "VIEW_EXTRA": {"ko": "불필요한 투상도",
                   "en": "Unnecessary views",
                   "ja": "不要な投影図",
                   "zh": "多余的视图"},
    "THIRD_ANGLE": {"ko": "제3각법 배치 위반",
                    "en": "Third-angle layout violated",
                    "ja": "第三角法の配置違反",
                    "zh": "违反第三角投影布置"},
    "SECTION_DETAIL": {"ko": "단면도·상세도 표기 미흡",
                       "en": "Section or detail view not marked properly",
                       "ja": "断面図・詳細図の表記不備",
                       "zh": "剖视图或详图标注不足"},
    "LAYOUT": {"ko": "투상도 배치 불균형",
               "en": "Unbalanced view layout",
               "ja": "投影図の配置不均衡",
               "zh": "视图布置不均衡"},
}

PROMPT = "이 도면의 투상도 선택과 배열을 채점하세요.\n\n참고 정보(CAD 파일에서 직접 읽은 값):\n"

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string"},
        "deductions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["error", "warn", "info"]},
                    "kind": {"type": "string", "enum": list(PROJECTION_KINDS)},
                    "detail": {"type": "string"},
                    "fix": {"type": "string"},
                    "deduct": {"type": "integer"},
                },
                "required": ["severity", "kind", "detail", "fix", "deduct"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "deductions"],
    "additionalProperties": False,
}


LANGS = ("en", "ja", "zh")

# 수험생이 지적을 보고 실제로 하는 질문 세 가지. 자유 입력을 받지 않고 이
# 목록만 쓰기 때문에 답을 채점할 때 미리 만들어 둘 수 있다.
FOLLOWUP_QUESTIONS = ("why", "where", "verify")

FOLLOWUP_SYSTEM = """\
당신은 전산응용기계제도기능사 실기 도면 채점위원입니다.

받은 JSON은 방금 당신이 매긴 '투상도 선택과 배열' 지적입니다. 두 가지를
한꺼번에 만드세요.

**첫째, 지적마다 수험생이 물을 세 가지에 답합니다.** answers 배열에 순서대로
넣습니다.

1. 왜 감점인가 — 어느 채점 항목과 어느 KS 제도 규칙에 걸리는지, 감점인지
   오작(실격)인지 밝힙니다.
2. 어디를 눌러야 하나 — Inventor에서 밟을 메뉴 순서를 단계로 적습니다.
3. 고친 뒤 어떻게 확인하나 — 도면에서 무엇을 보면 제대로 고쳐졌는지 적습니다.

**둘째, 지적과 그 답을 영어(en) · 일본어(ja) · 중국어 간체(zh)로 옮깁니다.**

지켜야 할 것

- 이미 적힌 detail·fix를 그대로 되풀이하지 말고 그다음을 설명하세요.
- 지어내지 마세요. 도면에서 확인되지 않은 치수를 만들면 안 됩니다. 확실하지
  않으면 "그 회차 공개문제와 지시사항에서 확인하세요"라고 쓰세요.
- 규격은 이름까지만 적고 **조·항·장 번호는 쓰지 마세요.** 확인할 수 없는
  번호를 적으면 수험생이 그것을 근거로 믿게 됩니다.
- 답 앞에 번호나 질문을 다시 적지 마세요. 답 내용만 씁니다.
- 각 답은 두세 문장으로 짧게 씁니다.
- 번역은 뜻을 바꾸지 말고, 점수·개수·치수·기호(Ø, Ra, H7, A/B 데이텀)를
  그대로 두세요. fix는 각 언어판 Inventor 메뉴 이름으로 옮기세요.
  예: "배치 > 투상도" → "Place Views > Projected"
- **deductions 배열의 순서와 개수를 네 언어 모두 원문과 똑같이 유지하세요.**"""

# title 은 PROJECTION_KINDS 에 언어별로 이미 있어서 번역을 받지 않는다.
_TRANSLATED_DEDUCTION = {
    "type": "object",
    "properties": {
        "detail": {"type": "string"},
        "fix": {"type": "string"},
        "answers": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["detail", "fix", "answers"],
    "additionalProperties": False,
}

FOLLOWUP_SCHEMA = {
    "type": "object",
    "properties": {
        "ko": {
            "type": "object",
            "properties": {
                "deductions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "answers": {"type": "array",
                                        "items": {"type": "string"}},
                        },
                        "required": ["answers"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["deductions"],
            "additionalProperties": False,
        },
        **{lang: {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "deductions": {"type": "array",
                               "items": _TRANSLATED_DEDUCTION},
            },
            "required": ["verdict", "deductions"],
            "additionalProperties": False,
        } for lang in LANGS},
    },
    "required": ["ko", *LANGS],
    "additionalProperties": False,
}


def _without_additional_properties(node):
    if isinstance(node, dict):
        return {k: _without_additional_properties(v) for k, v in node.items()
                if k != "additionalProperties"}
    if isinstance(node, list):
        return [_without_additional_properties(v) for v in node]
    return node


def _projection_line(first_angle):
    """투상법을 아는 척하지 않는다.

    DXF 헤더에는 투상법이 없고 dwg.py 도 이 값을 채우지 못한다. 그런데
    None 이 거짓으로 취급돼서, 모든 도면에 "제3각법" 이라고 AI 에게 단언하고
    있었다. 제1각법으로 그려서 오작인 도면도 제3각법이라고 알려준 셈이다."""
    if first_angle is None:
        return ("투상법(파일 속성): 알 수 없음 — 표제란 옆 투상법 기호"
                "(원뿔 두 개)를 그림에서 직접 확인하세요")
    return "투상법(파일 속성): " + ("제1각법" if first_angle else "제3각법")


def _layout_line(layout, placed):
    """제3각법 배치를 좌표로 이미 판정했으면 그 결과를 못 박아 준다.

    예전에는 정면도를 못 고르면 "판단하지 마세요" 라고만 보냈고, 실제 도면
    30장 중 22장이 그랬다. 배점이 가장 큰 항목의 한 축이 사실상 비어 있었던
    것이다. 지금은 dwg.analyze_layout 이 좌표로 정면도와 이웃 자리를 정하므로,
    AI 가 150DPI 그림을 보고 다시 짐작하게 두지 않는다."""
    if not layout:
        front = next((v for v in placed if v.get("is_front")), None)
        if front:
            return (f"정면도는 치수가 가장 많이 붙은 {front['name']} 로 "
                    "봅니다(추정). 이 뷰를 기준으로 배치를 판단하세요.")
        return ("정면도를 특정하지 못했습니다. 제3각법 배치"
                "(THIRD_ANGLE)는 판단하지 마세요.")
    if layout["verdict"] == "third":
        return ("제3각법 배치 확인됨 — 정면도를 기준으로 평면도가 위, "
                "우측면도가 오른쪽에 놓인 것을 **좌표로 확인했습니다.** "
                "배치는 맞으므로 THIRD_ANGLE 로 감점하지 마세요. "
                "줄이 안 맞는다고 적힌 뷰는 같은 장에 그린 다른 부품이거나 "
                "상세도라서 제3각법 판단 대상이 아닙니다.")
    if layout["verdict"] == "first":
        return ("제1각법 배치로 보입니다 — 정면도에 줄이 맞는 뷰가 아래·왼쪽"
                "에만 있습니다(좌표로 잰 값). 그림에서 표제란 옆 투상법 기호를 "
                "직접 확인하고, 제1각법이 맞으면 THIRD_ANGLE 로 지적하세요.")
    return ("뷰가 정면도 위·아래·좌·우에 섞여 있어 제3각법인지 좌표로는 "
            "가릴 수 없습니다. 같은 장에 다른 부품이 있거나 저면도를 쓴 "
            "도면입니다. 확신이 서지 않으면 THIRD_ANGLE 로 감점하지 마세요.")


def _context(facts):
    sh = (facts.get("sheets") or [{}])[0]
    views = sh.get("views", [])
    bits = [f"파일 종류: {facts.get('kind')}",
            _projection_line(facts.get("first_angle")),
            f"뷰 개수(CAD 판독): {len(views)}"]
    guessed = any(v.get("detected") == "cluster" for v in views)
    if guessed:
        # 뷰 경계를 CAD 가 알려주지 않아 형상 뭉치로 나눈 것이다. 이 사실을
        # 숨기면 AI 가 뷰 개수를 확정된 값으로 믿고 감점한다.
        bits[-1] = (f"뷰 개수(형상 뭉치로 추정, 틀릴 수 있음): {len(views)}")
    # 좌표를 같이 넘긴다. 뷰가 어디에 놓였는지는 CAD 파일에 숫자로 들어 있는데,
    # 이걸 안 주면 AI 가 150 DPI 그림을 보고 배치를 짐작해야 한다.
    placed = [v for v in views if v.get("x_mm") is not None]
    if placed:
        bits.append(("뷰 위치·크기(mm, 형상 뭉치로 추정. " if guessed else
                     "뷰 위치·크기(mm, CAD 에서 직접 잰 값. ")
                    + "x 는 오른쪽이, y 는 위쪽이 큽니다):")
        for v in placed[:12]:
            size = (f", 크기 {v['w_mm']}×{v['h_mm']}" if v.get("w_mm") else "")
            dims = (f", 붙은 치수 {v['dim_count']}개"
                    if v.get("dim_count") else "")
            role = f" ← {v['role']}" if v.get("role") else (
                " ← 정면도로 보임" if v.get("is_front") else
                " ← 정면도와 줄이 안 맞음(다른 부품이거나 상세도)")
            bits.append(f"- {v.get('name') or '이름없음'}: "
                        f"중심 ({v['x_mm']}, {v['y_mm']}){size}{dims}{role}")
        bits.append(_layout_line(sh.get("layout"), placed))
    else:
        names = [v.get("name") for v in views if v.get("name")]
        if names:
            bits.append("뷰 이름: " + ", ".join(names[:12]))
    return "\n".join(bits)


def _ask_cloudflare(png, prompt, timeout, system=SYSTEM, schema=SCHEMA,
                    max_tokens=4000):
    import requests

    token, account = _cloudflare_creds()
    content = [{"type": "text", "text": prompt}]
    if png:
        content.append({"type": "image_url", "image_url": {
            "url": "data:image/png;base64,"
                   + base64.standard_b64encode(png).decode()}})
    response = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}"
        f"/ai/run/{CLOUDFLARE_MODEL}",
        headers={"Authorization": "Bearer " + token},
        json={
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_schema", "json_schema": schema},
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("success"):
        print(f"[ai] cloudflare: {str(body.get('errors'))[:300]}", flush=True)
        return None
    result = body.get("result") or {}
    # Workers AI 는 스키마로 파싱한 결과를 response 에, 원문을 choices 에 준다
    if isinstance(result.get("response"), dict):
        return json.dumps(result["response"])
    if isinstance(result.get("response"), str):
        return result["response"]
    choices = result.get("choices") or [{}]
    return (choices[0].get("message") or {}).get("content")


def _ask_openai_style(api_url, model, key, png, prompt, timeout,
                      system, schema, max_tokens, label):
    """Call an OpenAI-compatible chat endpoint and return the reply text.

    Groq 와 Mistral 은 요청 모양이 같아 한 함수로 부른다. 둘 다 무료 한도가
    분 단위라 429 가 흔한데, 리셋이 곧이면 한 번만 기다렸다 다시 보낸다."""
    import requests

    content = [{"type": "text", "text": prompt}]
    if png:
        content.append({"type": "image_url", "image_url": {
            "url": "data:image/png;base64,"
                   + base64.standard_b64encode(png).decode()}})
    # 두 곳 모두 비전 모델에 json_schema 를 강제하지 못하고 json_object 만
    # 받는다. 스키마는 지시문에 실어 보내고 형식은 받는 쪽에서 확인한다.
    # json_object 모드는 메시지 어딘가에 'json' 이라는 낱말을 요구한다.
    system = (system
              + "\n\nReply with a single json object matching this schema. "
                "스키마에 없는 키를 넣지 마세요.\n"
              + json.dumps(schema, ensure_ascii=False))

    def send():
        return requests.post(
            api_url,
            headers={"Authorization": "Bearer " + key},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                "response_format": {"type": "json_object"},
                # 무료 한도가 분당 토큰이라, max_tokens 가 그 한도를 넘으면
                # 생성해 보기도 전에 요청 자체를 거절당한다(413).
                "max_tokens": min(max_tokens, FREE_TIER_MAX_TOKENS),
            },
            timeout=timeout,
        )

    response = send()
    # 채점(이미지가 있는 요청)만 기다렸다 다시 보낸다. 번역은 없어도 화면이
    # 돌아가므로, 그것 때문에 사용자를 수십 초 세워 둘 이유가 없다.
    if response.status_code == 429 and png:
        wait = _retry_after(response)
        if wait:
            print(f"[ai] {label} 한도 — {wait:.0f}초 뒤 한 번 더 시도", flush=True)
            time.sleep(wait)
            response = send()
    response.raise_for_status()
    choices = response.json().get("choices") or [{}]
    return (choices[0].get("message") or {}).get("content")


def _ask_groq(png, prompt, timeout, system=SYSTEM, schema=SCHEMA,
              max_tokens=4000):
    return _ask_openai_style(
        "https://api.groq.com/openai/v1/chat/completions", GROQ_MODEL,
        _groq_key(), png, prompt, timeout, system, schema, max_tokens, "groq")


def _ask_mistral(png, prompt, timeout, system=SYSTEM, schema=SCHEMA,
                 max_tokens=4000):
    return _ask_openai_style(
        "https://api.mistral.ai/v1/chat/completions", MISTRAL_MODEL,
        _mistral_key(), png, prompt, timeout, system, schema, max_tokens,
        "mistral")


RETRY_MAX_WAIT = 30.0
FREE_TIER_MAX_TOKENS = 4000


def _retry_after(response):
    """Seconds to wait before one retry, or 0 when waiting would not help."""
    raw = (response.headers.get("retry-after")
           or response.headers.get("x-ratelimit-reset-tokens")
           or response.headers.get("x-ratelimit-reset-requests") or "")
    seconds, value = 0.0, ""
    for ch in raw.strip():
        if ch.isdigit() or ch == ".":
            value += ch
            continue
        if value:
            seconds += float(value) * {"m": 60, "s": 1, "h": 3600}.get(ch, 0)
            value = ""
    if value:                       # 단위 없는 "20" 은 초로 본다
        seconds += float(value)
    return seconds if 0 < seconds <= RETRY_MAX_WAIT else 0.0


def _ask_gemini(png, prompt, timeout, system=SYSTEM, schema=SCHEMA,
                max_tokens=None):
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=_gemini_key(),
        http_options=types.HttpOptions(timeout=int(timeout * 1000)),
    )
    parts = [prompt]
    if png:
        parts.insert(0, types.Part.from_bytes(data=png, mime_type="image/png"))
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=_without_additional_properties(
                copy.deepcopy(schema)),
        ),
    )
    return response.text


SHIPPED_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aicache")
CACHE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
    "cad-checker", "aicache")


def _cache_key(blob, model, prompt=""):
    """AI 에게 보낸 것 전부로 열쇠를 만든다.

    프롬프트를 빼고 도면 파일만으로 열면, 우리가 도면에서 더 잘 읽어 내도
    **옛날 답이 그대로 나온다.** 실제로 뷰 이름과 제3각법 판정을 참고 정보에
    실어 보내기 시작했는데 캐시가 그 전 판을 돌려줬다. 참고 정보가 채점 근거로
    들어가는 이상, 그것도 열쇠의 일부여야 한다."""
    h = hashlib.sha256()
    for part in (model, SYSTEM, prompt):
        h.update(part.encode())
        h.update(b"\0")
    h.update(blob)
    return h.hexdigest()[:32] + ".json"


def _cache_path(blob, model, prompt=""):
    return os.path.join(CACHE_DIR, _cache_key(blob, model, prompt))


def _drawing_blob(dxf_path):
    """캐시 열쇠로 쓸 도면 내용.

    그림(PNG)으로 열쇠를 만들면 캐시가 한 번도 안 맞는다. 같은 도면을 두 번
    그려도 픽셀이 조금씩 달라져서(2,400×1,238 중 1,664픽셀) 해시가 매번 바뀌기
    때문이다. 그래서 도면 파일 내용으로 연다 — 같은 파일이면 같은 열쇠다."""
    try:
        with open(dxf_path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _cache_get(path):
    name = os.path.basename(path)
    for d in (SHIPPED_CACHE, CACHE_DIR):
        try:
            with open(os.path.join(d, name), encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            continue
    return None


def _cache_put(path, data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


ASK_SEC = 20.0            # 채점 한 번을 기다리는 최대 시간
EXTRA_SEC = 40.0          # 답변·번역은 결과가 나간 뒤 뒤에서 만드니 더 기다려도 된다
BUDGET_SEC = 45.0         # 채점기를 차례로 시도하다가 이만큼 넘으면 그만둔다


def judge(facts, timeout=ASK_SEC, defer=False):
    """투상도 30점을 채점한다. 쓸 수 있는 채점기를 우선순위대로 실제로 다
    시도한다 — 앞이 503·429로 막혀도 뒤가 살아 있으면 채점이 이어진다.

    한 곳에 매달리지 않는다. 채점기 하나를 `timeout` 초까지만 기다리고, 다 합쳐
    `BUDGET_SEC` 를 넘으면 남은 곳은 건너뛴다. 예전에는 한 번에 120초까지 기다려
    Gemini 가 503 을 늦게 내는 날이면 검사 전체가 그만큼 멈춰 있었다.

    defer=True 면 질문 답변·번역을 기다리지 않는다. 점수와 지적은 채점 호출
    하나로 다 나오고, 답변·번역은 그 뒤 호출 하나가 더 걸린다(실측 5초 + 13초).
    결과의 "later" 에 그 뒤 호출을 할 함수를 넣어 돌려주니, 부르는 쪽이 따로
    돌린다. 부르면 답변·번역이 채워진 같은 결과를 돌려준다."""
    chain = providers()
    dxf = facts.get("dxf")
    if not chain or not dxf or not os.path.exists(dxf):
        return None

    asks = {"cloudflare": _ask_cloudflare, "gemini": _ask_gemini,
            "groq": _ask_groq, "mistral": _ask_mistral}
    prompt = PROMPT + _context(facts)
    # 그림은 캐시에 없을 때만 그린다. 캐시 열쇠는 도면 파일 내용이라 그림이 필요 없고,
    # 그리는 데 배포 서버에서 몇 초가 걸려 예제를 다시 열 때마다 그만큼 늦었다.
    blob = _drawing_blob(dxf)
    png = None
    if blob is None:
        try:
            png = blob = png_of(facts)
        except Exception:
            return None

    # 같은 도면을 같은 참고 정보로 이미 채점해 뒀으면 그대로 쓴다.
    for name in chain:
        model = MODEL_OF[name]
        cached = _cache_path(blob, model, prompt)
        hit = _cache_get(cached)
        if hit is None:
            continue
        # 채점은 됐는데 답변이나 번역만 실패한 판이 캐시에 남아 있으면 그
        # 상태로 굳는다. 캐시를 쓰되 빠진 부분은 이번에 채워 다시 저장한다.
        if not _needs_extras(hit):
            print(f"[ai] 캐시 사용 ({model}) — 할당량 소모 없음", flush=True)
        return _with_extras(hit, asks[name], timeout, cached, model, defer)

    if png is None:
        try:
            png = png_of(facts)
        except Exception:
            return None
    until = time.monotonic() + BUDGET_SEC
    for name in chain:
        model = MODEL_OF[name]
        ask = asks[name]
        left = until - time.monotonic()
        if left <= 1.0:
            print(f"[ai] {BUDGET_SEC:.0f}초를 넘겨 {name} 은 건너뛴다", flush=True)
            break
        try:
            text = ask(png, prompt, min(timeout, left))
        except Exception as e:
            print(f"[ai] {name} {type(e).__name__}: {str(e)[:300]}", flush=True)
            continue
        if not text:
            print(f"[ai] {name} 빈 응답", flush=True)
            continue
        try:
            data = json.loads(text)
        except ValueError:
            print(f"[ai] {name} 응답이 JSON 이 아님", flush=True)
            continue
        if not isinstance(data, dict):
            continue

        # 빈 자리채움 항목은 여기서 한 번만 걸러낸다. 번역과 화면 표시가 같은
        # 목록을 봐야 항목 순서가 어긋나지 않는다.
        data["deductions"] = [d for d in (data.get("deductions") or [])
                              if isinstance(d, dict) and (d.get("title")
                                                          or d.get("detail"))]
        cached = _cache_path(blob, model, prompt)
        # 답변·번역이 실패해도 채점은 남긴다. 기다리지 않는 경우에도 같은 도면을
        # 곧바로 다시 올리면 채점을 또 부르지 않게 먼저 저장한다.
        _cache_put(cached, data)
        if name != chain[0]:
            print(f"[ai] {chain[0]} 실패 → {name}({model})로 채점", flush=True)
        return _with_extras(data, ask, timeout, cached, model, defer)
    return None


def _needs_extras(data):
    """Answers or translations are missing — they failed on an earlier run or were never made.

    세 단계가 순서대로 이어져 있어 뒤가 실패하면 앞 결과만 남는데, 캐시를 그대로
    쓰면 그 반쪽짜리 판이 영영 굳는다. 다음 검사 때 빠진 것만 다시 부른다."""
    if not isinstance(data.get("deductions"), list) or not data["deductions"]:
        return False
    missing_answers = any("answers" not in d for d in data["deductions"]
                          if isinstance(d, dict))
    return missing_answers or not data.get("i18n")


def _with_extras(data, ask, timeout, cached, model, defer):
    if not _needs_extras(data):
        return _to_findings(data, model)

    def extras():
        if _enrich(data, ask, max(timeout, EXTRA_SEC)):
            _cache_put(cached, data)
        return _to_findings(data, model)

    if not defer:
        return extras()
    # _to_findings 가 새 dict 를 만들어 돌려주므로, 뒤에서 data 를 채워도
    # 지금 돌려주는 결과는 바뀌지 않는다.
    out = _to_findings(data, model)
    out["later"] = extras
    return out


def _enrich(data, ask, timeout):
    """Add Korean answers and the three translations in one call.

    호출 하나에 묶는 이유는 무료 할당량이다. 도면 한 장에 채점·답변·번역으로
    세 번을 부르면 한도가 세 배로 빨리 마르고, 실제로 배포 서버에서 마지막
    번역만 429 로 계속 막혔다. 답변과 번역은 둘 다 채점 결과만 있으면 되므로
    한 번에 받는다. 실패하면 아무것도 채우지 않고 화면이 원래대로 돌아간다."""
    want = len(data["deductions"])
    if not want:
        return False
    source = {"verdict": data.get("verdict", ""),
              "deductions": [{"title": _title(d, "ko"),
                              "detail": d.get("detail", ""),
                              "fix": d.get("fix", "")}
                             for d in data["deductions"]]}
    try:
        text = ask(None, json.dumps(source, ensure_ascii=False), timeout,
                   FOLLOWUP_SYSTEM, FOLLOWUP_SCHEMA, 8000)
        out = json.loads(text) if text else None
    except Exception as e:
        print(f"[ai] 보조 생성 실패 {type(e).__name__}: {str(e)[:200]}", flush=True)
        return False
    if not isinstance(out, dict):
        return False
    for lang in ("ko", *LANGS):
        got = (out.get(lang) or {}).get("deductions")
        if not isinstance(got, list) or len(got) != want:
            print(f"[ai] 보조 생성 {lang} 항목 수가 원문과 달라 버림", flush=True)
            return False

    n = len(FOLLOWUP_QUESTIONS)
    for pos, d in enumerate(data["deductions"]):
        answers = (out["ko"]["deductions"][pos] or {}).get("answers")
        if isinstance(answers, list) and len(answers) == n:
            d["answers"] = [_drop_clause_numbers(a) for a in answers]
    for lang in LANGS:
        for item in out[lang]["deductions"]:
            if isinstance(item, dict) and isinstance(item.get("answers"), list):
                item["answers"] = [_drop_clause_numbers(a)
                                   for a in item["answers"]]
    data["i18n"] = {lang: out[lang] for lang in LANGS}
    return True


# 규격 이름은 확인할 수 있지만 조·항·장 번호는 그렇지 않다. 지시문으로 막아도
# 모델이 "KS B 0001 제3장" 처럼 지어내는 일이 있어 받은 뒤 걷어낸다.
_CLAUSE_RE = re.compile(
    r"\s*(?:[제第]\s*\d+\s*[장절조항章節款条項]"
    r"|\b(?:Chapter|Section|Clause|Article|Part)\s+\d+)",
    re.IGNORECASE)


def _drop_clause_numbers(text):
    return _CLAUSE_RE.sub("", str(text)).replace("  ", " ").strip()


def _followups_by_lang(deduction, i18n, pos):
    """{"ko": [...], "en": [...]} — 답이 다 갖춰진 언어만 담는다."""
    out = {}
    korean = deduction.get("answers")
    if isinstance(korean, list) and len(korean) == len(FOLLOWUP_QUESTIONS):
        out["ko"] = korean
    for lang in i18n:
        items = i18n[lang].get("deductions") or []
        if pos >= len(items):
            continue
        answers = (items[pos] or {}).get("answers")
        if isinstance(answers, list) and len(answers) == len(FOLLOWUP_QUESTIONS):
            out[lang] = [str(a) for a in answers]
    return out


def _title(deduction, lang):
    """제목은 kind 로 정해진 것을 쓴다. kind 가 없으면 AI 가 쓴 옛 제목을 그대로 둔다.

    옛 제목은 `aicache` 에 남아 있는 지난 판이다. 그때 화면에 뜬 문장을
    바꿔 버리면 그 판으로 잰 편차 기록과 대조가 안 된다."""
    fixed = PROJECTION_KINDS.get(deduction.get("kind"))
    if fixed:
        return fixed[lang]
    return deduction.get("title", "") if lang == "ko" else ""


def _to_findings(data, model):
    i18n = data.get("i18n") or {}
    findings, total = [], 0
    for pos, d in enumerate(data.get("deductions") or []):
        if not isinstance(d, dict) or not (d.get("kind") or d.get("title")
                                           or d.get("detail")):
            continue          # 옛 캐시에 남아 있을 수 있는 자리채움 항목
        translated = {
            lang: {"title": _title(d, lang) or (
                       i18n[lang]["deductions"][pos].get("title") or ""),
                   **{k: (i18n[lang]["deductions"][pos].get(k) or "")
                      for k in ("detail", "fix")}}
            for lang in i18n if pos < len(i18n[lang].get("deductions") or [])
        }
        followups = _followups_by_lang(d, i18n, pos)
        try:
            raw = int(d.get("deduct", 0))
        except (TypeError, ValueError):
            raw = 0
        deduct = max(0, min(MAX_SINGLE_DEDUCT, MAX_POINTS - total, raw))
        total += deduct
        findings.append({
            "code": "AI_PROJECTION",
            "severity": d.get("severity", "warn"),
            "title": _title(d, "ko") or "투상도 배열 지적",
            "detail": d.get("detail", ""),
            "fix": d.get("fix", ""),
            "item": "PROJECTION_LAYOUT",
            "deduct": deduct,
            "where": {},
            "i18n": translated,
            "followups": followups,
            # 채점표가 심각도순으로 다시 줄을 세우므로, 뒤늦게 온 답변·번역을
            # 제자리에 붙이려면 원래 순번이 필요하다.
            "ai_index": pos,
        })
    return {"verdict": data.get("verdict", ""),
            "verdict_i18n": {lang: i18n[lang].get("verdict", "")
                             for lang in i18n},
            "findings": findings,
            "score": MAX_POINTS - total,
            "model": model}
