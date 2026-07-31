import base64
import os

MODEL = "claude-opus-5"
MAX_POINTS = 30
RENDER_DPI = 150

MAX_PIXELS = 2400


def is_available():
    if not (os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return False
    try:
        import anthropic
        import pymupdf
    except ImportError:
        return False
    return True


def render_png(dxf_path):
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
    findings, total = [], 0
    for d in data.get("deductions", []):
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

