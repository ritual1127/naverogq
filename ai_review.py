"""투상도 선택과 배열(30점)을 비전 모델로 판정한다.

채점 기준 7개 항목 중 6개는 규칙으로 풀린다. 표면거칠기 기호가 있는가, 공차값이
비어 있는가, 주서에 일반공차 문구가 있는가 — 전부 세거나 찾으면 되는 문제다.

'투상도 선택과 배열'만 다르다. "정면도를 제대로 골랐는가", "평면도와 측면도가
제3각법 위치에 놓였는가", "이 형상을 표현하는 데 이 조합으로 충분한가"는 도면을
**보고** 판단해야 한다. 세서 나오는 답이 아니다. 그래서 exam.py는 이 항목을
`score: null` / `mode: "review"`로 비워 두었다. 100점 중 배점이 가장 큰 30점이
자동 채점 불가 영역으로 남아 있었다.

이 모듈이 그 구멍을 채운다. 도면을 이미지로 렌더해서 비전 모델에 넘기고, 배치와
선택의 타당성을 판정받는다. 나머지 70점은 계속 결정론적 규칙이 채점한다 — 같은
도면은 언제나 같은 점수가 나와야 하기 때문이다. AI는 규칙이 닿지 못하는 곳에만 쓴다.

API 키가 없으면 조용히 물러난다. 그 경우 제품은 이 모듈이 없던 때와 똑같이,
투상도 30점을 '사람이 확인'으로 비워 둔 채 동작한다.
"""
import base64
import os

MODEL = "claude-opus-5"
MAX_POINTS = 30
RENDER_DPI = 150

# 도면 한 장이 이 정도면 치수선과 뷰 배치가 또렷하게 보인다. 더 키우면 이미지
# 토큰만 늘고 판정은 나아지지 않는다.
MAX_PIXELS = 2400


def is_available():
    """비전 판정을 쓸 수 있으면 True.

    키가 없는 것은 오류가 아니라 기본 상태다. 이 함수가 False를 돌려주면
    호출부는 규칙 채점만으로 진행한다.
    """
    if not (os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return False
    try:
        import anthropic  # noqa: F401
        import pymupdf  # noqa: F401
    except ImportError:
        return False
    return True


def render_png(dxf_path):
    """도면을 PNG 바이트로. 비전 API는 SVG를 받지 않는다.

    Page(0, 0)은 도면 내용에서 크기를 잡으라는 뜻이고, max_*는 그 결과가 커져도
    이미지 토큰이 폭주하지 않게 잡는 상한이다.
    """
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing import layout as dlayout
    from ezdxf.addons.drawing import pymupdf as dpymupdf

    limit_mm = MAX_PIXELS / RENDER_DPI * 25.4
    doc = ezdxf.readfile(dxf_path)
    backend = dpymupdf.PyMuPdfBackend()
    Frontend(RenderContext(doc), backend).draw_layout(doc.modelspace(),
                                                      finalize=True)
    page = dlayout.Page(0, 0, dlayout.Units.mm, dlayout.Margins.all(5),
                        max_width=limit_mm, max_height=limit_mm)
    return backend.get_pixmap_bytes(page, fmt="png", dpi=RENDER_DPI)


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

원칙:
- 이미지에서 **실제로 보이는 것**만 근거로 삼으세요. 흐릿해서 판단이 서지 않으면
  감점하지 말고 info로 남기세요. 확신 없는 감점은 학습자를 잘못된 방향으로 보냅니다.
- fix에는 Inventor에서 취할 구체적 동작을 적으세요.
  예: "배치 > 투상도 로 정면도 위쪽에 평면도를 추가하세요."
- 결함이 없으면 findings를 빈 배열로 두고 30점을 주세요.
- 모든 문장은 한국어로 씁니다."""

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string",
                    "description": "투상도 배열 전반에 대한 한 문장 총평"},
        "deductions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["error", "warn", "info"]},
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "fix": {"type": "string"},
                    "deduct": {"type": "integer"},
                },
                "required": ["severity", "title", "detail", "fix", "deduct"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "deductions"],
    "additionalProperties": False,
}


def _context(facts):
    """모델이 이미지만으로는 알 수 없는 사실만 넘긴다."""
    sh = (facts.get("sheets") or [{}])[0]
    views = sh.get("views", [])
    bits = [f"파일 종류: {facts.get('kind')}",
            f"투상법(파일 속성): "
            f"{'제1각법' if facts.get('first_angle') else '제3각법'}",
            f"뷰 개수(CAD 판독): {len(views)}"]
    names = [v.get("name") for v in views if v.get("name")]
    if names:
        bits.append("뷰 이름: " + ", ".join(names[:12]))
    return "\n".join(bits)


def judge(facts, timeout=120.0):
    """투상도 30점 판정 결과, 또는 판정할 수 없으면 None.

    실패는 전부 None으로 흡수한다. 채점 도구가 외부 API 때문에 통째로 죽으면
    안 된다 — AI가 빠지면 그 항목만 '사람이 확인'으로 돌아갈 뿐이다.
    """
    dxf = facts.get("dxf")
    if not dxf or not os.path.exists(dxf) or not is_available():
        return None

    try:
        png = render_png(dxf)
    except Exception:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(timeout=timeout)
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": "image/png",
                                "data": base64.standard_b64encode(png).decode()}},
                    {"type": "text",
                     "text": "이 도면의 투상도 선택과 배열을 채점하세요.\n\n"
                             "참고 정보(CAD 파일에서 직접 읽은 값):\n" + _context(facts)},
                ],
            }],
        )
    except Exception:
        return None

    # 안전 분류기가 요청을 거절하면 content가 비어 있다. 인덱싱하기 전에 확인한다.
    if response.stop_reason == "refusal":
        return None

    import json
    try:
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
    except (StopIteration, ValueError):
        return None

    return _to_findings(data)


def _to_findings(data):
    """모델 응답을 exam.py가 이미 쓰는 finding 모양으로 바꾼다.

    deduct를 그대로 실어 보내면 grade()의 '감점 합계' 계산이 이 항목도 똑같이
    처리한다. 점수 계산 경로를 하나 더 만들 필요가 없다.
    """
    findings, total = [], 0
    for d in data.get("deductions", []):
        # 모델이 배점을 벗어난 값을 주더라도 스코어카드가 음수로 깨지지 않게 한다.
        deduct = max(0, min(MAX_POINTS - total, int(d.get("deduct", 0))))
        total += deduct
        findings.append({
            "code": "AI_PROJECTION",
            "severity": d.get("severity", "warn"),
            "title": d.get("title", "투상도 배열 지적"),
            "detail": d.get("detail", ""),
            "fix": d.get("fix", ""),
            "item": "PROJECTION_LAYOUT",
            "deduct": deduct,
            "where": {},
        })
    return {"verdict": data.get("verdict", ""),
            "findings": findings,
            "score": MAX_POINTS - total,
            "model": MODEL}
