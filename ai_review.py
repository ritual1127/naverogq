import base64
import calendar
import functools
import hashlib
import json
import os
import re
import statistics
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# 2026-10-20 에 Gemini · Mistral · Groq 를 뺐다(P35). Gemini API 약관은 18세 미만을
# 대상으로 하거나 18세 미만이 쓸 가능성이 큰 서비스에 API 를 못 쓰게 하고, Groq 는 계정
# 주인이 18세 이상이어야 하며, Mistral 은 미성년자가 보호자 동의 없이 쓰게 하지 못하게
# 한다. 남은 두 곳은 같은 모델(Llama 4 Scout)을 서로 다른 곳에서 돌린다 — 한 곳이 막혀
# 다른 곳으로 넘어가도 채점 성향이 바뀌지 않는다.
CLOUDFLARE_MODEL = "@cf/meta/llama-4-scout-17b-16e-instruct"
VERCEL_MODEL = "meta/llama-4-scout"

MAX_POINTS = 30
# 채점 지침이 정한 감점 폭의 최댓값. "형상 표현이 불가능할 정도의 투상도 누락,
# 제3각법 위반 배치"가 8~12점이고 그보다 큰 감점 사유는 지침에 없다. 그런데
# 실제로는 한 지적에 30점을 통째로 깎는 판정이 다섯 번에 한 번 나왔다.
MAX_SINGLE_DEDUCT = 12

# 근거 없는 감점은 점수에서 뺀다. 10-20 밤 실제 도면 10장 모두에 "정면도 선택 부적절 4 ~ 5점"이 붙었는데,
# 여러 장의 detail 이 "정면도" 한 낱말이고 fix 는 지시문 예시를 그대로 옮긴 문장이었다(P45).
# 지시문의 원칙("확신 없는 감점은 하지 말고 info 로")을 받은 쪽에서도 지킨다 — 지적은 info 로 남긴다.
MIN_DETAIL_CHARS = 8


def _unfounded(deduction):
    return len(str(deduction.get("detail") or "").strip()) < MIN_DETAIL_CHARS
RENDER_DPI = 150
MAX_PIXELS = 2400


def _cloudflare_creds(suffix=""):
    """suffix "_2" 는 예비 Cloudflare 계정(CLOUDFLARE_API_TOKEN_2 · CLOUDFLARE_ACCOUNT_ID_2)."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN" + suffix)
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID" + suffix)
    return (token, account) if token and account else None


def _vercel_key():
    return os.environ.get("AI_GATEWAY_API_KEY")


def _importable(*names):
    try:
        for n in names:
            __import__(n)
    except ImportError:
        return False
    return True


# 순서가 곧 우선순위다. Cloudflare 무료량(하루 1만 뉴런, 09:00 KST 초기화)이 마르거나
# 막히면 예비 Cloudflare 계정(cloudflare2, 같은 모델 · 무료량 따로)으로, 그다음 Vercel AI Gateway
# 로 넘어간다 — 둘 다 키가 있을 때만이다. Vercel 은 결제 수단을 등록해야 매달 무료 크레딧이
# 열려서(10-20 확인) 공개 서버에는 아직 넣지 않았다.
PROVIDER_ORDER = ("cloudflare", "cloudflare2", "vercel")
MODEL_OF = {"cloudflare": CLOUDFLARE_MODEL, "cloudflare2": CLOUDFLARE_MODEL, "vercel": VERCEL_MODEL}

# 하루 무료량이 떨어진 채점기(3036)와 다시 써도 되는 시각(unix). 그때까지는 부르지 않고 건너뛴다 —
# 불러도 같은 답이 오고, 그동안 화면만 기다린다.
_PAUSED = {}
on_usage = None    # 호출마다 usage 를 받을 곳 — 서버(main.py)가 stats.ai_usage 를 꽂는다. 측정 도구는 비워 둔다.


class QuotaExhausted(RuntimeError):
    pass


def _next_utc_midnight(now=None):
    t = time.gmtime(now if now is not None else time.time())
    return calendar.timegm((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0)) + 86400


def _paused(name, now=None):
    return _PAUSED.get(name, 0) > (now if now is not None else time.time())


def providers():
    """쓸 수 있는 채점기를 우선순위 순으로 준다.

    키가 있는지만 보는 목록이다. 실제로 앞이 막혔는지는 불러 봐야 알기 때문에
    `judge()`가 이 순서대로 진짜 요청을 넣어 보고 실패하면 다음으로 넘어간다."""
    if not _importable("pymupdf"):
        return []
    ready = {
        "cloudflare": bool(_cloudflare_creds()) and _importable("requests"),
        "cloudflare2": bool(_cloudflare_creds("_2")) and _importable("requests"),
        "vercel": bool(_vercel_key()) and _importable("requests"),
    }
    forced = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    if forced:
        return [forced] if ready.get(forced) and not _paused(forced) else []
    return [n for n in PROVIDER_ORDER if ready[n] and not _paused(n)]


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
    from ezdxf.addons.drawing import Frontend
    from ezdxf.addons.drawing import layout as dlayout
    from ezdxf.addons.drawing import pymupdf as dpymupdf

    import dwg

    doc = dwg.readfile(dxf_path)
    msp = doc.modelspace()
    mm_per_unit, _ = dwg.detect_mm_per_unit(doc, msp)
    backend = dpymupdf.PyMuPdfBackend()
    Frontend(dwg.render_context(doc), backend).draw_layout(msp, finalize=True)
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
- detail 에는 **어느 뷰에서 무엇을 봤는지** 도면에 근거해 적으세요. "정면도"처럼 뷰
  이름만 적으면 근거가 아닙니다. 근거를 댈 수 없으면 감점하지 말고 info 로 두세요.
- fix 에는 이 도면에서 Inventor 로 할 동작을 메뉴 이름과 함께 적으세요. 다른 도면에도
  똑같이 쓸 수 있는 문장이면 이 도면의 fix 가 아닙니다.
- 결함이 없으면 deductions를 빈 배열로 두고 30점을 주세요.
- 모든 문장은 한국어로 씁니다."""

# 채점 응답의 출력 상한. 시간 ≈ 0.9초 + 출력 토큰 × 0.05초(10-20 17시 실측 20번)라 길수록 늦다.
# 지금까지 가장 긴 응답이 396 토큰이었고, 같은 말을 되풀이하면 4000 토큰까지 200초를 매달릴 수
# 있어 1000 에서 끊는다. "짧게 쓰라"는 지시도 재 봤지만(10-20 밤, 10장) 출력 중앙값이 166 → 157
# 토큰으로 거의 그대로였다 — 같은 시각 Cloudflare 쪽 속도가 토큰당 0.049 → 0.088초로 더 크게
# 흔들려 지시문은 그대로 두었다(P44).
GRADE_MAX_TOKENS = 1000

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

# 답변 · 번역은 언어마다 따로 부른다(_enrich). 지시문의 앞뒤는 네 언어가 같다.
_FOLLOWUP_HEAD = """\
당신은 전산응용기계제도기능사 실기 도면 채점위원입니다.

받은 JSON은 방금 당신이 매긴 '투상도 선택과 배열' 지적입니다. 지적마다
수험생이 물을 세 가지에 답합니다. answers 배열에 순서대로 넣습니다.

1. 왜 감점인가 — 어느 채점 항목과 어느 KS 제도 규칙에 걸리는지, 감점인지
   오작(실격)인지 밝힙니다.
2. 어디를 눌러야 하나 — Inventor에서 밟을 메뉴 순서를 단계로 적습니다.
3. 고친 뒤 어떻게 확인하나 — 도면에서 무엇을 보면 제대로 고쳐졌는지 적습니다.

"""

_FOLLOWUP_RULES = """

지켜야 할 것

- 이미 적힌 detail·fix를 그대로 되풀이하지 말고 그다음을 설명하세요.
- 지어내지 마세요. 도면에서 확인되지 않은 치수를 만들면 안 됩니다. 확실하지
  않으면 "그 회차 공개문제와 지시사항에서 확인하세요"라고 쓰세요.
- 규격은 이름까지만 적고 **조·항·장 번호는 쓰지 마세요.** 확인할 수 없는
  번호를 적으면 수험생이 그것을 근거로 믿게 됩니다.
- 답 앞에 번호나 질문을 다시 적지 마세요. 답 내용만 씁니다.
- 각 답은 두세 문장으로 짧게 씁니다.
- **deductions 배열의 순서와 개수를 원문과 똑같이 유지하세요.**"""

_LANG_NAME = {"en": "영어", "ja": "일본어", "zh": "중국어 간체"}

FOLLOWUP_SYSTEM = {
    "ko": _FOLLOWUP_HEAD + "답은 한국어로 씁니다." + _FOLLOWUP_RULES,
    **{lang: _FOLLOWUP_HEAD
       + f"**모든 글을 {name}로 씁니다** — verdict, 지적마다 detail · fix 를 {name}로 "
         f"옮기고, 세 가지 답도 {name}로 씁니다. 번역은 뜻을 바꾸지 말고, 점수·개수·"
         "치수·기호(Ø, Ra, H7, A/B 데이텀)를 그대로 두세요. fix는 그 언어판 Inventor "
         "메뉴 이름으로 옮기세요. 예: \"배치 > 투상도\" → \"Place Views > Projected\""
       + _FOLLOWUP_RULES
       for lang, name in _LANG_NAME.items()},
}

_ANSWERS = {"type": "array", "items": {"type": "string"}}

# title 은 PROJECTION_KINDS 에 언어별로 이미 있어서 번역을 받지 않는다.
_TRANSLATED_DEDUCTION = {
    "type": "object",
    "properties": {
        "detail": {"type": "string"},
        "fix": {"type": "string"},
        "answers": _ANSWERS,
    },
    "required": ["detail", "fix", "answers"],
    "additionalProperties": False,
}

FOLLOWUP_SCHEMA = {
    "ko": {
        "type": "object",
        "properties": {
            "deductions": {"type": "array", "items": {
                "type": "object",
                "properties": {"answers": _ANSWERS},
                "required": ["answers"],
                "additionalProperties": False,
            }},
        },
        "required": ["deductions"],
        "additionalProperties": False,
    },
    **{lang: {
        "type": "object",
        "properties": {
            "verdict": {"type": "string"},
            "deductions": {"type": "array", "items": _TRANSLATED_DEDUCTION},
        },
        "required": ["verdict", "deductions"],
        "additionalProperties": False,
    } for lang in LANGS},
}


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


def _cf_error_codes(response):
    try:
        return {e.get("code") for e in (response.json().get("errors") or []) if isinstance(e, dict)}
    except Exception:                                         # noqa: BLE001
        return set()


def _ask_cloudflare(png, prompt, timeout, system=SYSTEM, schema=SCHEMA,
                    max_tokens=4000, suffix="", label="cloudflare"):
    """Workers AI 를 한 번 부른다. 429 는 두 가지다(Workers AI errors 문서):
    3036 하루 무료량 소진 — 09:00 KST 까지 이 계정을 쉬게 하고 바로 실패한다(기다려도 같은 답).
    3040 잠깐 용량 부족 — 2초 뒤 한 번만 다시 부른다."""
    import requests

    if _paused(label):
        raise QuotaExhausted(f"{label} 하루 무료량 소진")
    token, account = _cloudflare_creds(suffix)
    content = [{"type": "text", "text": prompt}]
    if png:
        content.append({"type": "image_url", "image_url": {
            "url": "data:image/png;base64,"
                   + base64.standard_b64encode(png).decode()}})
    until = time.monotonic() + timeout
    for attempt in range(2):
        started = time.monotonic()
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
            timeout=max(1.0, until - time.monotonic()),
        )
        if response.status_code != 429:
            break
        codes = _cf_error_codes(response)
        if 3036 in codes:
            _PAUSED[label] = _next_utc_midnight()
            print(f"[ai] {label} 하루 무료량 소진(3036) — 09:00 KST 까지 건너뜀", flush=True)
            raise QuotaExhausted(f"{label} 하루 무료량 소진")
        if attempt or until - time.monotonic() < 10:
            break
        print(f"[ai] {label} 429 {sorted(c for c in codes if c)} — 2초 뒤 한 번 더", flush=True)
        time.sleep(2)
    response.raise_for_status()
    body = response.json()
    if not body.get("success"):
        print(f"[ai] {label}: {str(body.get('errors'))[:300]}", flush=True)
        return None
    result = body.get("result") or {}
    usage = result.get("usage") or body.get("usage") or {}
    if usage.get("completion_tokens"):
        _note(speed=usage["completion_tokens"] / max(0.1, time.monotonic() - started))
    if on_usage:
        try:
            on_usage("grade" if png else "extra", usage)
        except Exception:                                     # noqa: BLE001
            pass
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

    Vercel AI Gateway 가 이 모양으로 받는다. 무료 등급은 모델마다 분당 한도가
    있어 429 가 날 수 있는데, 리셋이 곧이면 한 번만 기다렸다 다시 보낸다."""
    import requests

    content = [{"type": "text", "text": prompt}]
    if png:
        content.append({"type": "image_url", "image_url": {
            "url": "data:image/png;base64,"
                   + base64.standard_b64encode(png).decode()}})
    # json_schema 대신 json_object 로 받는다. 스키마는 지시문에 실어 보내고
    # 형식은 받는 쪽에서 확인한다.
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
                # 무료 한도가 분당 토큰인 곳은 max_tokens 가 그 한도를 넘으면
                # 생성해 보기도 전에 요청 자체를 거절한다(413, Groq 때 겪었다).
                "max_tokens": min(max_tokens, FREE_TIER_MAX_TOKENS),
                # 학습하지 않는다는 계약을 맺은 제공자에게만 보낸다. 쓰는
                # 사람 대부분이 미성년 수험생이다.
                "providerOptions": {"gateway": {"disallowPromptTraining": True}},
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


def _ask_vercel(png, prompt, timeout, system=SYSTEM, schema=SCHEMA,
                max_tokens=4000):
    return _ask_openai_style(
        "https://ai-gateway.vercel.sh/v1/chat/completions", VERCEL_MODEL,
        _vercel_key(), png, prompt, timeout, system, schema, max_tokens,
        "vercel")


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
    때문이다. 그래서 도면 파일 내용으로 연다 — 같은 파일이면 같은 열쇠다.

    줄바꿈은 LF 로 맞춘다. 같은 예제 파일도 Windows 에서는 git 이 CRLF 로, 공개 서버에서는
    LF 로 풀어 바이트가 다르다. 그래서 저장소에 넣어 둔 예제 채점(aicache/)이 서버에서는
    한 번도 안 맞았다(P32). AI 에게 보내는 그림은 줄바꿈과 상관없다."""
    try:
        with open(dxf_path, "rb") as fh:
            return fh.read().replace(b"\r\n", b"\n")
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


# 채점 한 번을 기다리는 최대 시간. 20초였는데 Llama 4 Scout(Workers AI)는 실제 도면 20번 중
# 2번이 20초를 넘었다(20.1 · 26.2초, 10-20 실측은 40초까지 기다려 잼). 공개 서버는 그만큼
# 30점을 비우고 있었다(P43). 화면은 8초 뒤 결과를 먼저 보이고 180초까지 받아 가므로(home.js)
# 길게 기다려도 검사가 멈추지 않는다.
ASK_SEC = 45.0
# 답변·번역은 결과가 나간 뒤 뒤에서 만드니 더 기다려도 된다. Workers AI 의 Llama 4 Scout 는
# 같은 요청에 19초가 걸리기도 40초를 넘기기도 했다(10-20). 화면은 180초까지 받아 간다(home.js).
EXTRA_SEC = 120.0
PART_SEC = 55.0           # 답변 · 번역 한 언어를 한 번 기다리는 시간 — 넘으면 한 번 더 부른다
BUDGET_SEC = 60.0         # 채점기를 차례로 시도하다가 이만큼 넘으면 그만둔다

# 공개 상태(/api/health)에 싣는 최근 채점 요약. 서버 로그를 못 보는 사람도 지금 AI 채점이
# 실제로 되고 있는지 확인할 수 있게 — 이 프로세스가 뜬 뒤부터, 캐시로 끝난 검사는 뺀다.
# ponytail: 프로세스 메모리라 재시작하면 0 부터 센다. 오래 쌓아야 하면 stats(D1)로 옮긴다.
_RECENT = {"since": time.time(), "graded": 0, "failed": 0, "secs": deque(maxlen=50),
           "speeds": deque(maxlen=50), "extra_parts": 0, "extra_ok": 0, "last_error": None}
_RECENT_LOCK = threading.Lock()


def _note(**kw):
    with _RECENT_LOCK:
        for k, v in kw.items():
            if k in ("sec", "speed"):
                _RECENT.setdefault(k + "s", deque(maxlen=50)).append(v)
            elif k == "last_error":
                _RECENT[k] = v
            else:
                _RECENT[k] += v


def recent():
    with _RECENT_LOCK:
        secs = list(_RECENT["secs"])
        return {"since": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(_RECENT["since"])),
                "graded": _RECENT["graded"], "failed": _RECENT["failed"],
                "median_sec": round(statistics.median(secs), 1) if secs else None,
                "max_sec": round(max(secs), 1) if secs else None,
                # Cloudflare 쪽 출력 속도(토큰/초). 같은 호출도 시각에 따라 20 → 11 로 흔들린다(P44)
                "tok_per_sec": round(statistics.median(_RECENT.get("speeds") or [0]), 1) or None,
                "extras": f"{_RECENT['extra_ok']}/{_RECENT['extra_parts']}",
                "last_error": _RECENT["last_error"],
                "paused_until": {n: time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(t))
                                 for n, t in _PAUSED.items() if t > time.time()}}


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

    asks = {"cloudflare": _ask_cloudflare,
            "cloudflare2": functools.partial(_ask_cloudflare, suffix="_2", label="cloudflare2"),
            "vercel": _ask_vercel}
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
    error = "없음"
    for name in chain:
        model = MODEL_OF[name]
        ask = asks[name]
        left = until - time.monotonic()
        if left <= 1.0:
            print(f"[ai] {BUDGET_SEC:.0f}초를 넘겨 {name} 은 건너뛴다", flush=True)
            break
        started = time.monotonic()
        try:
            text = ask(png, prompt, min(timeout, left), SYSTEM, SCHEMA, GRADE_MAX_TOKENS)
        except Exception as e:
            print(f"[ai] {name} {type(e).__name__}: {str(e)[:300]}", flush=True)
            # 예외 글에는 계정 번호가 든 주소가 섞일 수 있어 공개 상태에는 종류와 상태 코드만 남긴다
            status = getattr(getattr(e, "response", None), "status_code", None)
            error = f"{name} {type(e).__name__}" + (f" {status}" if status else "")
            continue
        if not text:
            print(f"[ai] {name} 빈 응답", flush=True)
            error = f"{name} 빈 응답"
            continue
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            print(f"[ai] {name} 응답이 JSON 이 아님", flush=True)
            error = f"{name} JSON 아님"
            continue
        _note(graded=1, sec=time.monotonic() - started)

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
    _note(failed=1, last_error=f"{error} · {time.strftime('%m-%d %H:%MZ', time.gmtime())}")
    return None


def _missing_answers(data):
    return any("answers" not in d for d in data["deductions"] if isinstance(d, dict))


def _needs_extras(data):
    """Answers or translations are missing — they failed on an earlier run or were never made.

    세 단계가 순서대로 이어져 있어 뒤가 실패하면 앞 결과만 남는데, 캐시를 그대로
    쓰면 그 반쪽짜리 판이 영영 굳는다. 다음 검사 때 빠진 것만 다시 부른다 —
    언어 하나만 빠졌어도 그 언어만."""
    if not isinstance(data.get("deductions"), list) or not data["deductions"]:
        return False
    have = data.get("i18n") or {}
    return _missing_answers(data) or any(lang not in have for lang in LANGS)


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
    """Add Korean answers and the three translations — one call per language, all at once.

    10-20 까지는 네 언어를 호출 하나로 받았다(무료 한도 때문 — Gemini 시절 번역만 429 로 막혔다).
    Workers AI 의 Llama 4 Scout 는 그 호출 하나에 48 ~ 64초가 걸렸고(출력 510 토큰), 한 언어라도
    항목 수가 어긋나면 네 언어를 다 버렸다 — 예제 3장을 만들 때 4번 중 1번, 그날 밤 공개 서버
    확인 때 1번 중 1번 답변이 비었다(P43). 언어마다 따로 동시에 부르면 가장 느린 하나만큼만 걸리고,
    어긋난 언어만 버린다. 버린 언어는 같은 도면을 다시 열 때 그것만 다시 부른다(_needs_extras).
    지시문이 언어마다 붙어 뉴런은 더 든다(지적 1개 도면 52 → 78 ~ 123, 10-20 측정).

    한 언어 호출이 120초 동안 답이 없던 적도 있다(같은 날 중국어). 출력 상한이 3000 토큰이면
    초당 20 토큰 남짓인 이 모델이 같은 말을 되풀이할 때 150초를 넘긴다. 그래서 상한을 지적 수에
    맞추고(지적 하나에 실측 100 ~ 300 토큰), 한 번 기다리는 시간을 PART_SEC 로 끊어 한 번 더 부른다."""
    want = len(data["deductions"])
    if not want:
        return False
    i18n = dict(data.get("i18n") or {})
    parts = (["ko"] if _missing_answers(data) else []) + [lang for lang in LANGS if lang not in i18n]
    if not parts:
        return False
    source = json.dumps({"verdict": data.get("verdict", ""),
                         "deductions": [{"title": _title(d, "ko"),
                                         "detail": d.get("detail", ""),
                                         "fix": d.get("fix", "")}
                                        for d in data["deductions"]]}, ensure_ascii=False)
    tokens = min(3000, 300 + 450 * want)

    def one(lang):
        until = time.monotonic() + timeout
        for attempt in range(2):
            left = until - time.monotonic()
            if attempt and left < 10:
                break
            try:
                text = ask(None, source, max(1.0, min(left, PART_SEC)), FOLLOWUP_SYSTEM[lang],
                           FOLLOWUP_SCHEMA[lang], tokens)
                out = json.loads(text) if text else None
            except Exception as e:
                print(f"[ai] 보조 생성 {lang} 실패 {type(e).__name__}: {str(e)[:200]}", flush=True)
                continue
            got = out.get("deductions") if isinstance(out, dict) else None
            if isinstance(got, list) and len(got) == want:
                return out
            print(f"[ai] 보조 생성 {lang} 항목 수가 원문과 달라 버림", flush=True)
        return None

    with ThreadPoolExecutor(max_workers=len(parts)) as pool:
        got = dict(zip(parts, pool.map(one, parts)))
    _note(extra_parts=len(parts), extra_ok=sum(1 for v in got.values() if v))

    n = len(FOLLOWUP_QUESTIONS)
    changed = False
    for d, item in zip(data["deductions"], (got.get("ko") or {}).get("deductions") or []):
        answers = (item or {}).get("answers")
        if isinstance(answers, list) and len(answers) == n:
            d["answers"] = [_drop_clause_numbers(a) for a in answers]
            changed = True
    for lang in LANGS:
        out = got.get(lang)
        if not out:
            continue
        for item in out["deductions"]:
            if isinstance(item, dict) and isinstance(item.get("answers"), list):
                item["answers"] = [_drop_clause_numbers(a) for a in item["answers"]]
        i18n[lang] = out
        changed = True
    if i18n:
        data["i18n"] = i18n
    return changed


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
        unfounded = _unfounded(d)
        deduct = 0 if unfounded else max(0, min(MAX_SINGLE_DEDUCT, MAX_POINTS - total, raw))
        total += deduct
        findings.append({
            "code": "AI_PROJECTION",
            "severity": "info" if unfounded else d.get("severity", "warn"),
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
