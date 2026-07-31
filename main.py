"""Web server: upload a CAD file, get findings and a viewable drawing.

Runs on the machine that has Inventor -- that is the whole reason it's a local
server rather than a cloud app. Inventor cannot run on Vercel/Render, and the
cloud alternative (APS Design Automation) bills credits.
"""
import os
import shutil
import traceback
import uuid
import zipfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import check

# Uploads live outside OneDrive: Inventor holds file locks while a document is
# open and OneDrive's sync fights it, producing random open failures.
DATA = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "cad-checker")
UPLOADS = os.path.join(DATA, "uploads")
os.makedirs(UPLOADS, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
MAX_BYTES = 200 * 1024 * 1024

app = FastAPI(title="Inventor 도면 검사기")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
_RESULTS = {}


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_local(request):
    """True only for requests that came from this machine.

    A tunnel forwards through cloudflared on localhost, so it would look local
    by client IP alone -- the proxy headers it adds are what give it away.
    """
    if any(h in request.headers for h in
           ("cf-connecting-ip", "x-forwarded-for", "cf-ray")):
        return False
    return (request.client.host if request.client else None) in LOCAL_HOSTS


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as fh:
        return fh.read()


@app.get("/api/health")
def health(request: Request):
    import dwg
    import exam
    import inventor
    inv = inventor.is_available()
    return {"ok": True,
            "supported": check.SUPPORTED if inv else sorted(check.DXF_EXT),
            "inventor": inv,
            "local": _is_local(request),
            "dwg_converter": bool(dwg.find_libredwg()) or bool(dwg.find_oda()),
            "oda": dwg.find_oda(),
            "checks": exam.check_catalog(),
            "exam": {"sheet": exam.REQUIRED_SHEET[0],
                     "third_angle": exam.REQUIRED_THIRD_ANGLE}}


@app.post("/api/analyze-path")
def analyze_path(body: dict, request: Request):
    """Analyse a file where it already sits.

    A .idw resolves its .ipt/.iam by path, so copying it anywhere -- which is
    what an upload does -- breaks every geometry check. Reading it in place is
    the only way to check a real drawing set.

    Local requests only. This endpoint takes an arbitrary filesystem path, so
    once the server is published through a tunnel it would let anyone with the
    link probe and read CAD files anywhere on this machine. Remote users upload
    instead (a .zip keeps the drawing's references intact).
    """
    if not _is_local(request):
        raise HTTPException(
            403, "경로 분석은 이 컴퓨터에서만 사용할 수 있습니다. "
                 "원격에서는 파일을 업로드하세요. 도면(.idw)은 참조가 유지되도록 "
                 "모델 파일과 함께 .zip으로 압축해서 올리면 됩니다.")
    raw = (body or {}).get("path", "").strip().strip('"')
    if not raw:
        raise HTTPException(400, "경로를 입력하세요.")
    path = os.path.abspath(os.path.expandvars(os.path.expanduser(raw)))
    if not os.path.isfile(path):
        raise HTTPException(404, f"파일이 없습니다: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in check.SUPPORTED:
        raise HTTPException(400, f"지원하지 않는 형식입니다: {ext or '(확장자 없음)'}. "
                                 f"지원: {', '.join(check.SUPPORTED)}")
    job = uuid.uuid4().hex[:12]
    os.makedirs(os.path.join(UPLOADS, job), exist_ok=True)
    return _run(job, path, os.path.basename(path), _enabled(body))


def _enabled(src):
    """Selected check ids, or None when the caller didn't specify any.

    An explicitly empty selection must stay empty -- treating it as "all"
    silently re-enabled every check the user had just turned off.
    """
    if not src or "checks" not in src or src["checks"] is None:
        return None
    v = src["checks"]
    if isinstance(v, str):
        v = [x for x in v.split(",") if x.strip()]
    return set(v)


@app.post("/api/analyze")
def analyze(file: UploadFile = File(...), checks: str = Form(None)):
    name = os.path.basename(file.filename or "upload")
    ext = os.path.splitext(name)[1].lower()
    if ext not in check.SUPPORTED and ext != ".zip":
        raise HTTPException(400, f"지원하지 않는 형식입니다: {ext or '(확장자 없음)'}. "
                                 f"지원: {', '.join(check.SUPPORTED)}, .zip")

    job = uuid.uuid4().hex[:12]
    workdir = os.path.join(UPLOADS, job)
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, name)
    size = 0
    with open(path, "wb") as out:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > MAX_BYTES:
                out.close()
                shutil.rmtree(workdir, ignore_errors=True)
                raise HTTPException(413, "파일이 너무 큽니다 (최대 200MB).")
            out.write(chunk)

    if ext == ".zip":
        path, name = _unzip(path, workdir)
    return _run(job, path, name, _enabled({"checks": checks}))


def _unzip(zpath, workdir):
    """Extract an upload and pick the file to analyse.

    A zip is how you ship a drawing WITH the models it references, which is the
    only way an upload can pass the geometry checks.
    """
    root = os.path.join(workdir, "z")
    os.makedirs(root, exist_ok=True)
    with zipfile.ZipFile(zpath) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            # refuse absolute paths and ../ escapes
            dest = os.path.abspath(os.path.join(root, info.filename))
            if not dest.startswith(os.path.abspath(root) + os.sep):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    found = []
    for dirpath, _, files in os.walk(root):
        if "oldversions" in dirpath.lower():
            continue
        for f in files:
            if os.path.splitext(f)[1].lower() in check.SUPPORTED:
                found.append(os.path.join(dirpath, f))
    if not found:
        raise HTTPException(400, "압축 파일 안에 분석할 CAD 파일이 없습니다. "
                                 f"지원: {', '.join(check.SUPPORTED)}")
    # a drawing is the most informative thing to check, then an assembly
    order = {".idw": 0, ".dwg": 1, ".dxf": 1, ".iam": 2, ".ipt": 3}
    found.sort(key=lambda p: (order.get(os.path.splitext(p)[1].lower(), 9), p))
    return found[0], os.path.basename(found[0])


def _run(job, path, name, enabled=None):
    workdir = os.path.join(UPLOADS, job)
    ext = os.path.splitext(path)[1].lower()
    dxf_out = os.path.join(workdir, "view.dxf") if ext == ".idw" else None
    stl_out = os.path.join(workdir, "model.stl") if ext in (".ipt", ".iam") else None
    try:
        facts, findings, summary = check.analyze(path, dxf_out=dxf_out,
                                                stl_out=stl_out, enabled=enabled)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"분석 실패: {type(e).__name__}: {e}")

    svg, marked, marker_index = _render(facts)
    payload = {
        "job": job, "file": name, "kind": facts.get("kind"),
        "props": facts.get("props", {}),
        "standard": facts.get("standard"),
        "first_angle": facts.get("first_angle"),
        "summary": summary, "findings": findings,
        "scorecard": facts.get("scorecard"),
        "notes_text": facts.get("notes_text") or [],
        "stats": _stats(facts),
        "svg": svg, "markers_placed": marked, "marker_index": marker_index,
        "model_url": f"/api/model/{job}" if facts.get("stl") else None,
        "model_error": facts.get("stl_error"),
        "refs_ok": facts.get("refs_ok", True),
        "svg_note": None,
    }
    _RESULTS[job] = payload
    return JSONResponse(payload)


def _render(facts):
    """(svg_or_None, markers_placed, marker_index).

    Arrows are numbered in the same order for every file type, and
    marker_index maps that number back onto the finding so the list and the
    drawing agree. Sheet centimetres map to exported-DXF millimetres by exactly
    x10 (verified to 0.000 mm against 12 known circles), which is what makes
    .idw arrows trustworthy rather than decorative.
    """
    dxf = facts.get("dxf")
    if not dxf or not os.path.exists(dxf):
        return None, False, []
    import dwg
    markers, index = [], []
    for sh in facts.get("sheets", []):
        for c in sh.get("undimensioned", []):
            if c.get("dxf_x") is None:
                continue
            markers.append(c)
            index.append({"n": len(markers), "diameter_mm": c["diameter_mm"],
                          "sheet": sh.get("name")})
    try:
        svg, _ = dwg.render_svg(dxf, markers)
        return svg, bool(markers), index
    except Exception:
        traceback.print_exc()
        return None, False, []


@app.get("/api/model/{job}")
def model(job):
    """Binary STL for the browser's 3D preview."""
    if not job.isalnum():
        raise HTTPException(400, "bad job id")
    path = os.path.join(UPLOADS, job, "model.stl")
    if not os.path.exists(path):
        raise HTTPException(404, "3D 모델이 없습니다.")
    return FileResponse(path, media_type="model/stl", filename="model.stl")


def _stats(facts):
    s = {"kind": facts.get("kind")}
    if facts.get("sketches"):
        s["sketches"] = len(facts["sketches"])
        s["sketches_under"] = sum(1 for x in facts["sketches"] if x["status"] == "under")
    for k in ("holes", "walls", "interferences", "sick_features"):
        if facts.get(k):
            s[k] = len(facts[k])
    for k in ("mass_kg", "volume_cm3", "feature_count", "occurrence_count"):
        if facts.get(k) is not None:
            s[k] = facts[k]
    sheets = facts.get("sheets") or []
    if sheets:
        s["sheets"] = len(sheets)
        s["dims"] = sum(len(x.get("dims", [])) for x in sheets)
        s["undimensioned"] = sum(len(x.get("undimensioned", [])) for x in sheets)
        s["title_block"] = sheets[0].get("title_block") or sheets[0].get("border")
        s["views"] = sum(len(x.get("views", [])) for x in sheets)
    if facts.get("interference_error"):
        s["interference_error"] = facts["interference_error"]
    return s


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("CADCHECK_PORT", "8000"))
    # Binds to localhost only. Public access goes through the Cloudflare tunnel,
    # which keeps the server off the local network and lets _is_local() tell
    # tunnelled requests apart from ones typed on this machine.
    print(f"\n  http://127.0.0.1:{port}  <- 브라우저에서 열기\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
