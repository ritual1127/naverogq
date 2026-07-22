import base64
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

import ezdxf
import fitz  # PyMuPDF
import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# DXF / PDF 데이터 추출
# ---------------------------------------------------------------------------


def extract_dxf(path: str) -> dict:
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    dimensions = []
    for dim in msp.query("DIMENSION"):
        text = dim.dxf.get("text", "")
        try:
            measurement = dim.get_measurement()
        except Exception:
            measurement = None
        dimensions.append({
            "text": text if text and text != "<>" else None,
            "measurement": measurement,
            "layer": dim.dxf.layer,
            "style": dim.dxf.dimstyle,
        })

    texts = []
    for e in msp.query("TEXT MTEXT"):
        texts.append(e.plain_text() if hasattr(e, "plain_text") else e.dxf.text)

    layers = [layer.dxf.name for layer in doc.layers]
    geometry_counts = {
        "lines": len(msp.query("LINE")),
        "circles_arcs": len(msp.query("CIRCLE ARC")),
    }

    return {
        "dimensions": dimensions,
        "texts": texts,
        "layers": layers,
        "geometry_counts": geometry_counts,
    }


def extract_pdf(path: str, page_index: int = 0, dpi: int = 150) -> dict:
    doc = fitz.open(path)
    page = doc[page_index]
    text = page.get_text()
    image_bytes = page.get_pixmap(dpi=dpi).tobytes("png")
    return {
        "text": text,
        "image_bytes": image_bytes,
        "page_count": doc.page_count,
    }


# ---------------------------------------------------------------------------
# DWG/IPT/IAM/IDW 처리용 Autodesk Platform Services(APS) 연동
#
# Inventor 네이티브 파일은 순수 파이썬으로 열 수 없어, APS에 업로드 -> 변환(translate)
# -> 썸네일/속성 추출 흐름을 탄다. 실제 치수 단위 검사는 Inventor Design Automation
# AppBundle이 있어야 가능하므로, 이 모듈은 이미지(썸네일) + 변환 상태까지만 제공하고
# 정밀 판단은 Gemini 쪽에 맡긴다.
#
# 필요 환경변수: APS_CLIENT_ID, APS_CLIENT_SECRET
# ---------------------------------------------------------------------------

APS_BASE = "https://developer.api.autodesk.com"


class APSError(RuntimeError):
    pass


def _get_aps_credentials() -> tuple[str, str]:
    client_id = os.environ.get("APS_CLIENT_ID")
    client_secret = os.environ.get("APS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise APSError(
            "APS_CLIENT_ID / APS_CLIENT_SECRET 환경변수가 없습니다. "
            "DWG/IPT/IAM/IDW 분석에는 Autodesk Platform Services 앱 자격증명이 필요합니다."
        )
    return client_id, client_secret


def _default_bucket_key(client_id: str) -> str:
    # OSS 버킷 키는 전체 APS 계정을 통틀어 유일해야 하므로 client_id를 해시해 충돌을 피한다.
    return "cad-err-" + hashlib.sha1(client_id.encode()).hexdigest()[:16]


def _get_aps_token(scope: str = "data:read data:write data:create bucket:create bucket:read") -> str:
    client_id, client_secret = _get_aps_credentials()
    resp = requests.post(
        f"{APS_BASE}/authentication/v2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _ensure_bucket(token: str, bucket_key: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{APS_BASE}/oss/v2/buckets/{bucket_key}/details", headers=headers, timeout=30)
    if resp.status_code == 200:
        return
    if resp.status_code == 403:
        raise APSError(
            f"버킷 이름 '{bucket_key}'을(를) 다른 APS 계정이 이미 사용 중입니다. "
            "bucket_key를 바꿔서 다시 시도하세요."
        )
    resp = requests.post(
        f"{APS_BASE}/oss/v2/buckets",
        headers={**headers, "Content-Type": "application/json"},
        json={"bucketKey": bucket_key, "policyKey": "transient"},
        timeout=30,
    )
    if resp.status_code == 409:
        return  # 이미 우리 계정 소유로 존재함
    resp.raise_for_status()


def _upload_file(token: str, bucket_key: str, object_key: str, file_path: str) -> str:
    """OSS v2는 직접 PUT 업로드를 막았고 Signed S3 Upload 3단계만 허용한다:
    1) 서명된 업로드 URL 발급, 2) 그 URL로 원본 바이트 PUT, 3) 완료 처리(finalize).
    """
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(
        f"{APS_BASE}/oss/v2/buckets/{bucket_key}/objects/{object_key}/signeds3upload",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    upload_info = resp.json()
    upload_key = upload_info["uploadKey"]
    upload_url = upload_info["urls"][0]

    with open(file_path, "rb") as f:
        put_resp = requests.put(upload_url, data=f, timeout=300)
    put_resp.raise_for_status()

    finalize_resp = requests.post(
        f"{APS_BASE}/oss/v2/buckets/{bucket_key}/objects/{object_key}/signeds3upload",
        headers={**headers, "Content-Type": "application/json"},
        json={"uploadKey": upload_key},
        timeout=30,
    )
    finalize_resp.raise_for_status()
    return finalize_resp.json()["objectId"]


def _translate(token: str, urn: str, formats=("svf2",)) -> str:
    # 썸네일은 별도 job 포맷이 아니라 변환 완료 후 /thumbnail 엔드포인트로 받는다.
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base64_urn = base64.urlsafe_b64encode(urn.encode()).decode().rstrip("=")
    payload = {
        "input": {"urn": base64_urn},
        "output": {"formats": [{"type": fmt} for fmt in formats]},
    }
    resp = requests.post(f"{APS_BASE}/modelderivative/v2/designdata/job", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return base64_urn


def _wait_for_translation(token: str, base64_urn: str, timeout_s: int = 180, interval_s: int = 5) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    waited = 0
    while waited < timeout_s:
        resp = requests.get(
            f"{APS_BASE}/modelderivative/v2/designdata/{base64_urn}/manifest", headers=headers, timeout=30
        )
        resp.raise_for_status()
        manifest = resp.json()
        if manifest.get("status") in ("success", "failed", "timeout"):
            return manifest
        time.sleep(interval_s)
        waited += interval_s
    raise APSError("APS 변환이 제한 시간 안에 끝나지 않았습니다.")


def _get_thumbnail(token: str, base64_urn: str) -> bytes | None:
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{APS_BASE}/modelderivative/v2/designdata/{base64_urn}/thumbnail",
        headers=headers,
        params={"width": 400, "height": 400},
        timeout=30,
    )
    return resp.content if resp.status_code == 200 else None


def extract_via_aps(file_path: str, bucket_key: str | None = None) -> dict:
    client_id, _ = _get_aps_credentials()
    bucket_key = bucket_key or _default_bucket_key(client_id)
    token = _get_aps_token()
    _ensure_bucket(token, bucket_key)
    object_key = os.path.basename(file_path).replace(" ", "_")
    urn = _upload_file(token, bucket_key, object_key, file_path)
    base64_urn = _translate(token, urn)
    manifest = _wait_for_translation(token, base64_urn)
    thumbnail = _get_thumbnail(token, base64_urn)
    return {
        "manifest_status": manifest.get("status"),
        "derivatives": manifest.get("derivatives", []),
        "image_bytes": thumbnail,
    }


# ---------------------------------------------------------------------------
# KS 기준 로컬 규칙 검사 (DXF처럼 구조화된 데이터가 있을 때만 동작)
# ---------------------------------------------------------------------------

TOLERANCE_MARKERS = ("±", "+/-", "h6", "h7", "h8", "H6", "H7", "H8", "js", "JS")


def check_missing_tolerance(dxf_data: dict) -> list[dict]:
    findings = []
    for dim in dxf_data["dimensions"]:
        text = dim.get("text") or ""
        if not any(marker in text for marker in TOLERANCE_MARKERS):
            findings.append({
                "category": "missing_tolerance",
                "description": f"치수(레이어: {dim.get('layer')})에 공차 표기가 없습니다 (KS B 0412 공차 표기 기준 확인 필요).",
                "severity": "medium",
                "location_hint": dim.get("layer"),
                "source": "rule",
            })
    return findings


def check_missing_dimension(dxf_data: dict) -> list[dict]:
    findings = []
    counts = dxf_data["geometry_counts"]
    geometry_total = counts["lines"] + counts["circles_arcs"]
    dim_count = len(dxf_data["dimensions"])

    if geometry_total > 0 and dim_count == 0:
        findings.append({
            "category": "missing_dimension",
            "description": "도면에 형상 요소는 있지만 치수 기입이 전혀 없습니다.",
            "severity": "high",
            "location_hint": None,
            "source": "rule",
        })
    elif geometry_total > 20 and dim_count < geometry_total * 0.1:
        findings.append({
            "category": "missing_dimension",
            "description": f"형상 요소({geometry_total}개)에 비해 치수({dim_count}개)가 적어 누락 가능성이 있습니다.",
            "severity": "low",
            "location_hint": None,
            "source": "rule",
        })
    return findings


def check_dimstyle_defined(dxf_data: dict) -> list[dict]:
    findings = []
    for dim in dxf_data["dimensions"]:
        if not dim.get("style"):
            findings.append({
                "category": "standard_violation",
                "description": "치수에 도면 스타일(DIMSTYLE)이 지정되지 않았습니다.",
                "severity": "low",
                "location_hint": dim.get("layer"),
                "source": "rule",
            })
    return findings


def run_all_checks(dxf_data: dict) -> list[dict]:
    return (
        check_missing_tolerance(dxf_data)
        + check_missing_dimension(dxf_data)
        + check_dimstyle_defined(dxf_data)
    )


# ---------------------------------------------------------------------------
# Google AI Studio(Gemini) 검토
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-2.5-flash"

FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["missing_dimension", "missing_tolerance", "standard_violation"],
                    },
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "location_hint": {"type": "string"},
                },
                "required": ["category", "description", "severity"],
            },
        }
    },
    "required": ["findings"],
}


class GeminiConfigError(RuntimeError):
    pass


def _build_gemini_prompt(summary_text: str, ks_reference: str) -> str:
    return (
        "다음은 CAD 도면에서 추출한 데이터입니다:\n"
        f"{summary_text}\n\n"
        "참고할 KS 표준 규칙 요약:\n"
        f"{ks_reference}\n\n"
        "이 도면에서 누락된 치수(missing_dimension), 누락된 공차 표기(missing_tolerance), "
        "KS 표준 위반(standard_violation)을 찾아 findings 배열로 답하세요. "
        "확실하지 않으면 severity를 low로 표시하세요."
    )


def review_drawing(summary_text: str, image_bytes: bytes | None, ks_reference: str) -> list[dict]:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise GeminiConfigError("GOOGLE_API_KEY 환경변수가 없어 AI 검토를 건너뜁니다.")

    client = genai.Client()
    contents = [_build_gemini_prompt(summary_text, ks_reference)]
    if image_bytes:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))

    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FINDING_SCHEMA,
        ),
    )
    data = json.loads(resp.text)
    findings = data.get("findings", [])
    for f in findings:
        f["source"] = "ai"
    return findings


# ---------------------------------------------------------------------------
# FastAPI 백엔드 (Render 등에 배포, 프론트엔드(HTML/CSS/JS)는 Cloudflare Pages에서 이 API를 호출)
# ---------------------------------------------------------------------------

app = FastAPI(title="Inventor 도면 설계 오류 자동 검출기 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ponytail: 데모용 전체 허용, 프론트엔드 도메인 확정되면 그걸로 제한
    allow_methods=["*"],
    allow_headers=["*"],
)

KNOWLEDGE_PATH = Path(__file__).parent / "Knowledge" / "ks_reference.md"
KS_REFERENCE = KNOWLEDGE_PATH.read_text(encoding="utf-8") if KNOWLEDGE_PATH.exists() else ""
APS_EXTENSIONS = {".dwg", ".ipt", ".iam", ".idw"}


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    rule_findings: list[dict] = []
    image_bytes: bytes | None = None
    summary_text = f"파일명: {file.filename}\n"

    try:
        if suffix == ".dxf":
            data = extract_dxf(tmp_path)
            rule_findings = run_all_checks(data)
            summary_text += json.dumps(data, ensure_ascii=False, default=str)[:4000]
        elif suffix == ".pdf":
            data = extract_pdf(tmp_path)
            image_bytes = data["image_bytes"]
            summary_text += data["text"][:4000]
        elif suffix in APS_EXTENSIONS:
            data = extract_via_aps(tmp_path)
            image_bytes = data.get("image_bytes")
            summary_text += json.dumps({"status": data.get("manifest_status")}, ensure_ascii=False)
        else:
            raise HTTPException(400, "지원하지 않는 파일 형식입니다.")
    except APSError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"파일 분석 중 오류가 발생했습니다: {e}")
    finally:
        os.unlink(tmp_path)

    ai_findings: list[dict] = []
    ai_error: str | None = None
    try:
        ai_findings = review_drawing(summary_text, image_bytes, KS_REFERENCE)
    except GeminiConfigError as e:
        ai_error = str(e)
    except Exception as e:
        ai_error = f"AI 검토 중 오류가 발생했습니다: {e}"

    return {
        "rule_findings": rule_findings,
        "ai_findings": ai_findings,
        "ai_error": ai_error,
    }
