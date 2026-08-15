import base64
import copy
import hashlib
import json
import os

GEMINI_MODEL = "gemini-3.6-flash"
CLOUDFLARE_MODEL = "@cf/meta/llama-4-scout-17b-16e-instruct"

MAX_POINTS = 30
RENDER_DPI = 150
MAX_PIXELS = 2400


def _gemini_key():
    return (os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY"))


def _cloudflare_creds():
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    return (token, account) if token and account else None


def _importable(*names):
    try:
        for n in names:
            __import__(n)
    except ImportError:
        return False
    return True


def provider():
    forced = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    if not _importable("pymupdf"):
        return None
    gemini = _gemini_key() and _importable("google.genai")
    cloudflare = _cloudflare_creds() and _importable("requests")
    if forced == "gemini":
        return "gemini" if gemini else None
    if forced == "cloudflare":
        return "cloudflare" if cloudflare else None
    if gemini:
        return "gemini"
    if cloudflare:
        return "cloudflare"
    return None


def active_model():
    return {"gemini": GEMINI_MODEL,
            "cloudflare": CLOUDFLARE_MODEL}.get(provider())


def is_available():
    return provider() is not None


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
- 결함이 없으면 deductions를 빈 배열로 두고 30점을 주세요.
- 모든 문장은 한국어로 씁니다."""

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


def _without_additional_properties(node):
    if isinstance(node, dict):
        return {k: _without_additional_properties(v) for k, v in node.items()
                if k != "additionalProperties"}
    if isinstance(node, list):
        return [_without_additional_properties(v) for v in node]
    return node


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


def _ask_cloudflare(png, prompt, timeout):
    import requests

    token, account = _cloudflare_creds()
    data_url = "data:image/png;base64," + base64.standard_b64encode(png).decode()
    response = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}"
        f"/ai/run/{CLOUDFLARE_MODEL}",
        headers={"Authorization": "Bearer " + token},
        json={
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]},
            ],
            "response_format": {"type": "json_schema", "json_schema": SCHEMA},
            "max_tokens": 4000,
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


def _ask_gemini(png, prompt, timeout):
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=_gemini_key(),
        http_options=types.HttpOptions(timeout=int(timeout * 1000)),
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=png, mime_type="image/png"), prompt],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
            response_json_schema=_without_additional_properties(
                copy.deepcopy(SCHEMA)),
        ),
    )
    return response.text


SHIPPED_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aicache")
CACHE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
    "cad-checker", "aicache")


def _cache_key(png, model):
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(b"\0")
    h.update(SYSTEM.encode())
    h.update(b"\0")
    h.update(png)
    return h.hexdigest()[:32] + ".json"


def _cache_path(png, model):
    return os.path.join(CACHE_DIR, _cache_key(png, model))


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


def judge(facts, timeout=120.0):
    name = provider()
    dxf = facts.get("dxf")
    if not name or not dxf or not os.path.exists(dxf):
        return None

    try:
        png = render_png(dxf)
    except Exception:
        return None

    model = active_model()
    cached = _cache_path(png, model)
    hit = _cache_get(cached)
    if hit is not None:
        print(f"[ai] 캐시 사용 ({model}) — 할당량 소모 없음", flush=True)
        return _to_findings(hit, model)

    prompt = PROMPT + _context(facts)
    ask = {"cloudflare": _ask_cloudflare, "gemini": _ask_gemini}[name]
    try:
        text = ask(png, prompt, timeout)
    except Exception as e:
        print(f"[ai] {type(e).__name__}: {str(e)[:300]}", flush=True)
        return None
    if not text:
        return None

    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    _cache_put(cached, data)
    return _to_findings(data, model)


def _to_findings(data, model):
    findings, total = [], 0
    for d in data.get("deductions") or []:
        if not isinstance(d, dict):
            continue
        if not (d.get("title") or d.get("detail")):
            continue          # 내용 없는 자리채움 항목은 화면에 올리지 않는다
        try:
            raw = int(d.get("deduct", 0))
        except (TypeError, ValueError):
            raw = 0
        deduct = max(0, min(MAX_POINTS - total, raw))
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
            "model": model}
