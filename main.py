import asyncio
import os
import secrets
import shutil
import threading
import time
import traceback
import uuid
import zipfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import check
import ogq
import stats

DATA = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "cad-checker")
UPLOADS = os.path.join(DATA, "uploads")
# 오류 신고에 "도면도 같이 보내기"를 켠 사람의 도면만 여기로 온다. 나머지는 UPLOADS 에서 지워진다.
KEEP = os.path.join(DATA, "keep")
os.makedirs(UPLOADS, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")
MAX_BYTES = 200 * 1024 * 1024

SAMPLE_NOTES = {
    "sample_plate.dxf": "평판 부품도 — 투상도가 1개뿐이라 감점이 나옵니다",
    "sample_autocad.dxf": "AutoCAD 실도면 — 오작(실격) 판정이 나오는 예제",
    "sample_075em07z.dwg": "위 도면의 DWG 원본 — LibreDWG가 있어야 열립니다",
}

PRUNE_EVERY_SEC = 10 * 60


@asynccontextmanager
async def _lifespan(_app):
    """_prune_uploads() is otherwise only reached from _run(), so with no
    traffic an upload outlives the "deleted within an hour" notice we show.
    ponytail: assumes one process; extra workers pruning in parallel is
    harmless because rmtree ignores errors."""
    async def loop():
        while True:
            _prune_uploads()
            await asyncio.sleep(PRUNE_EVERY_SEC)
    task = asyncio.create_task(loop())
    warm = asyncio.create_task(_warm_samples())
    try:
        yield
    finally:
        task.cancel()
        warm.cancel()


WARMUP_AFTER_SEC = float(os.environ.get("CADLENS_WARMUP_AFTER", "20"))


async def _warm_samples():
    """서버가 뜬 뒤 예제 도면을 한 번씩 미리 검사해 둔다.

    예제 결과는 (파일, 켠 검사)가 같으면 다시 쓰므로, 처음 한 번만 느리다. 그런데 그 한 번이
    무료 서버(CPU 0.1)에서 25초였다 — 배포 직후 '예제로 먼저 보기'를 누른 사람이 그걸 다 맞았다.
    들어오는 요청과 CPU 를 다투지 않게 잠깐 기다렸다가, 한 장씩 천천히 돌린다."""
    await asyncio.sleep(WARMUP_AFTER_SEC)
    for name in sorted(SAMPLE_NOTES):
        path = os.path.join(SAMPLES, name)
        if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in _openable():
            continue
        try:
            started = time.monotonic()
            await asyncio.to_thread(_run_sample, "warmup" + uuid.uuid4().hex[:6], path, name, None)
            print(f"[warm] {name} {time.monotonic() - started:.1f}초", flush=True)
        except Exception as e:                                # noqa: BLE001
            print(f"[warm] {name} 실패: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(1)


app = FastAPI(title="CADLens 도면 검사기", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

JOB_TTL_SEC = 60 * 60
JOB_KEEP = 20
# 보내도 된다고 한 도면. 화면에 적은 대로 30일까지만 두고, 그 안이어도 50건을 넘기지 않는다.
KEPT_TTL_SEC = 30 * 24 * 60 * 60
KEPT_KEEP = 50
KEPT_MAX_BYTES = 30 * 1024 * 1024


def _prune(root, keep, ttl):
    """Uploads and their converted DXF stay on disk after the response.
    Bound them by age and count so the disk cannot fill up."""
    try:
        jobs = [os.path.join(root, d) for d in os.listdir(root)]
        jobs = [j for j in jobs if os.path.isdir(j)]
    except OSError:
        return
    def mtime(j):
        try:
            return os.path.getmtime(j)
        except OSError:
            return 0.0

    jobs.sort(key=mtime, reverse=True)
    cutoff = time.time() - ttl
    for i, job in enumerate(jobs):
        if i >= keep or mtime(job) < cutoff:
            shutil.rmtree(job, ignore_errors=True)


def _prune_uploads():
    _prune(UPLOADS, JOB_KEEP, JOB_TTL_SEC)
    _prune(KEEP, KEPT_KEEP, KEPT_TTL_SEC)


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_local(request):
    if any(h in request.headers for h in
           ("cf-connecting-ip", "x-forwarded-for", "cf-ray")):
        return False
    return (request.client.host if request.client else None) in LOCAL_HOSTS


def _page(name):
    with open(os.path.join(HERE, "static", name), encoding="utf-8") as fh:
        return fh.read()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    stats.bump(request, "visit")
    return _page("index.html")


# 안내 페이지는 방문 수에 넣지 않는다. 한 사람이 페이지를 옮겨 다닐 때마다 세면 접속 수가 부푼다.
@app.get("/ks", response_class=HTMLResponse)
def ks_page():
    return _page("ks.html")


@app.get("/accuracy", response_class=HTMLResponse)
def accuracy_page():
    return _page("accuracy.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(os.path.join(HERE, "static", "favicon.ico"),
                        media_type="image/x-icon")


@app.get("/api/health")
def health(request: Request):
    import ai_review
    import dwg
    import exam
    return {"ok": True,
            "supported": sorted(_openable()),
            "ai": ai_review.is_available(),
            "ai_provider": ai_review.provider(),
            "ai_model": ai_review.active_model(),
            "local": _is_local(request),
            "dwg_converter": dwg.has_dwg_support(),
            "stickers": ogq.available(),
            "dwg_via": dwg.dwg_converter_name(),
            "oda": dwg.find_oda(),
            "checks": exam.check_catalog(),
            "exam": {"sheet": exam.REQUIRED_SHEET[0],
                     "third_angle": exam.REQUIRED_THIRD_ANGLE}}


def _openable():
    import dwg
    exts = set(check.SUPPORTED)
    if not dwg.has_dwg_support():
        exts.discard(".dwg")
    return exts


@app.get("/api/sticker/{name}", include_in_schema=False)
def sticker(name: str):
    data = ogq.sticker(name)
    if data is None:
        raise HTTPException(404, "스티커를 쓸 수 없습니다.")
    return Response(data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


@app.get("/api/samples")
def samples():
    usable = _openable()
    if not os.path.isdir(SAMPLES):
        return {"samples": []}
    out = []
    for name in sorted(os.listdir(SAMPLES)):
        path = os.path.join(SAMPLES, name)
        ext = os.path.splitext(name)[1].lower()
        if not os.path.isfile(path) or ext not in usable:
            continue
        out.append({"name": name, "ext": ext,
                    "size": os.path.getsize(path),
                    "note": SAMPLE_NOTES.get(name, "")})
    return {"samples": out}


@app.get("/api/stats")
def site_stats():
    return stats.summary()


def _done(request, response):
    """검사 시작(check/sample)과 결과가 나온 것은 다른 수다. _run 이 예외를
    던지면 여기까지 오지 않으므로 이 수는 실제로 결과를 본 횟수다."""
    stats.bump(request, "done")
    return response


EVENT_KINDS = {"recheck"}


@app.post("/api/event")
def event(body: dict, request: Request):
    """화면이 보내는 이벤트. 지금은 재검사 하나뿐이다. 종류 이름만 받고
    파일명이나 도면 내용은 받지 않는다."""
    kind = (body or {}).get("kind", "")
    if kind not in EVENT_KINDS:
        raise HTTPException(400, "셀 수 없는 이벤트입니다.")
    stats.bump(request, kind)
    return {"ok": True}


NOTE_KINDS = {"report", "ask"}
NOTE_MAX = 2000
CONTACT_MAX = 120
SPOT_MAX = 200


def _job_id(raw):
    """화면이 보낸 검사 번호. 폴더 이름으로 쓰므로 16진수만 받는다."""
    job = os.path.basename(str(raw or "").strip())
    return job if job and len(job) <= 32 and all(c in "0123456789abcdef" for c in job) else ""


def _keep_drawing(job):
    """'도면도 같이 보내기'를 켠 경우에만 부른다. 검사 폴더의 도면을 따로 복사해
    1시간 청소(_prune_uploads)에 같이 지워지지 않게 한다. 돌려주는 값은 파일 이름."""
    src = os.path.join(UPLOADS, job)
    if not job or not os.path.isdir(src):
        return ""
    for name in sorted(os.listdir(src)):
        path = os.path.join(src, name)
        if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in check.SUPPORTED:
            continue
        if os.path.getsize(path) > KEPT_MAX_BYTES:
            return ""
        dest = os.path.join(KEEP, job)
        os.makedirs(dest, exist_ok=True)
        shutil.copy2(path, os.path.join(dest, name))
        return name
    return ""


@app.post("/api/feedback")
def feedback(body: dict, request: Request):
    """오류 신고와 문의. 연락처는 적고 싶은 사람만 적고, 도면은 켠 사람의 것만 남는다."""
    body = body or {}
    kind = body.get("kind")
    text = str(body.get("text") or "").strip()[:NOTE_MAX]
    contact = str(body.get("contact") or "").strip()[:CONTACT_MAX]
    spot = str(body.get("spot") or "").strip()[:SPOT_MAX]
    if kind not in NOTE_KINDS:
        raise HTTPException(400, "받을 수 없는 종류입니다.")
    if len(text) < 5:
        raise HTTPException(400, "내용을 5자 이상 적어 주세요.")
    job = _job_id(body.get("job"))
    kept = _keep_drawing(job) if body.get("share") and job else ""
    try:
        stats.note(kind, text, spot, contact, job, kept)
    except Exception as e:                                    # noqa: BLE001
        print(f"[note] 저장 실패: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(503, "지금은 보낼 수 없습니다. 잠시 뒤 다시 시도해 주세요.") from None
    return {"ok": True, "drawing": bool(kept)}


# 관리자 화면. 비밀번호는 환경변수(CADLENS_ADMIN_PW)로만 받는다 — 저장소가 공개라
# 코드에 적으면 그 순간 누구나 아는 값이 된다. 네 자리 숫자처럼 짧은 값을 쓸 수 있으므로
# 1) 맞히기 시도 수를 접속자별·서버 전체로 묶어 막고, 2) 한 번 맞히면 그 뒤로는
# 비밀번호 대신 임시 표를 쓰고, 3) 화면은 검색에 안 잡히고 캐시에 안 남게 한다.
ADMIN_FAIL_MAX = 5                      # 한 접속자가 15분에 틀릴 수 있는 횟수
ADMIN_FAIL_WINDOW = 15 * 60
ADMIN_GLOBAL_MAX = 20                   # IP 를 바꿔 가며 두드리는 것까지 묶어서 막는다
ADMIN_GLOBAL_WINDOW = 60 * 60
ADMIN_TOKEN_TTL = 2 * 60 * 60
NO_STORE = {"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex, nofollow"}

_fails = {}                 # 접속자 -> (틀린 횟수, 마지막으로 틀린 때)
_fails_all = []             # 서버 전체의 실패 시각
_tokens = {}                # 표 -> (만료 시각, 접속자)


def _locked(who):
    now = time.time()
    n, at = _fails.get(who, (0, 0.0))
    if now - at > ADMIN_FAIL_WINDOW:
        n = 0
    _fails_all[:] = [x for x in _fails_all if now - x < ADMIN_GLOBAL_WINDOW]
    return n >= ADMIN_FAIL_MAX or len(_fails_all) >= ADMIN_GLOBAL_MAX


def _admin_login(request, pw):
    """비밀번호를 한 번만 받고, 그 뒤로는 임시 표로 다닌다.
    ponytail: 실패 수와 표를 프로세스 메모리에 둔다 — 서버가 하나일 때만 맞다.
    여러 대로 늘리면 D1 로 옮긴다."""
    who = stats.client_ip(request)
    if _locked(who):
        raise HTTPException(429, "비밀번호를 너무 여러 번 틀렸습니다. 잠시 뒤에 다시 하세요.")
    want = os.environ.get("CADLENS_ADMIN_PW") or ""
    if not want:
        raise HTTPException(503, "이 서버에는 관리자 비밀번호(CADLENS_ADMIN_PW)가 없습니다.")
    # 한글이 섞인 값이 오면 str 끼리는 비교 자체가 터진다. 바이트로 맞춰 본다.
    if not secrets.compare_digest(str(pw or "").encode(), want.encode()):
        n, at = _fails.get(who, (0, 0.0))
        n = 0 if time.time() - at > ADMIN_FAIL_WINDOW else n
        _fails[who] = (n + 1, time.time())
        _fails_all.append(time.time())
        raise HTTPException(403, "비밀번호가 틀렸습니다.")
    _fails.pop(who, None)
    token = secrets.token_urlsafe(32)
    now = time.time()
    for old in [k for k, (exp, _) in _tokens.items() if exp < now]:
        del _tokens[old]
    _tokens[token] = (now + ADMIN_TOKEN_TTL, who)
    return token


def _admin_check(request, token):
    """표가 맞는지 본다. 표는 받은 그 접속자에게만 듣는다."""
    exp, who = _tokens.get(str(token or ""), (0.0, ""))
    if exp < time.time() or who != stats.client_ip(request):
        _tokens.pop(str(token or ""), None)
        raise HTTPException(401, "다시 로그인하세요.")


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return HTMLResponse(_page("admin.html"), headers=NO_STORE)


@app.post("/api/admin/login")
def admin_login(body: dict, request: Request):
    return JSONResponse({"token": _admin_login(request, (body or {}).get("pw")),
                         "ttl": ADMIN_TOKEN_TTL}, headers=NO_STORE)


@app.post("/api/admin/logout")
def admin_logout(body: dict):
    _tokens.pop(str((body or {}).get("token") or ""), None)
    return JSONResponse({"ok": True}, headers=NO_STORE)


@app.post("/api/admin/notes")
def admin_notes(body: dict, request: Request):
    _admin_check(request, (body or {}).get("token"))
    return JSONResponse({"notes": stats.notes(200), "stats": stats.summary()},
                        headers=NO_STORE)


@app.post("/api/admin/file")
def admin_file(body: dict, request: Request):
    """신고와 함께 받은 도면 내려받기. 보내도 된다고 한 것만 여기에 있다."""
    body = body or {}
    _admin_check(request, body.get("token"))
    job, name = _job_id(body.get("job")), os.path.basename(str(body.get("file") or ""))
    path = os.path.abspath(os.path.join(KEEP, job, name))
    if not job or not name or not path.startswith(os.path.abspath(KEEP) + os.sep)             or not os.path.isfile(path):
        raise HTTPException(404, "그 도면은 이미 지워졌습니다 (최대 30일 · 50건).")
    return FileResponse(path, filename=name, media_type="application/octet-stream",
                        headers=NO_STORE)


@app.post("/api/analyze-sample")
def analyze_sample(body: dict, request: Request):
    name = os.path.basename((body or {}).get("name", ""))
    path = os.path.abspath(os.path.join(SAMPLES, name))
    if not name or not path.startswith(os.path.abspath(SAMPLES) + os.sep) \
            or not os.path.isfile(path):
        raise HTTPException(404, f"그런 예제가 없습니다: {name or '(이름 없음)'}")
    if os.path.splitext(path)[1].lower() not in check.SUPPORTED:
        raise HTTPException(400, "분석할 수 없는 형식입니다.")
    job = uuid.uuid4().hex[:12]
    stats.bump(request, "sample")
    return _done(request, _run_sample(job, path, name, _enabled(body)))


SAMPLE_RESULTS = {}         # (이름, 수정 시각, 켠 검사) -> 결과. 예제 파일은 안 바뀌니 결과도 같다
SAMPLE_KEEP = 16


def _run_sample(job, path, name, enabled):
    import ai_review

    started = time.monotonic()
    key = (name, os.path.getmtime(path), None if enabled is None else tuple(sorted(enabled)))
    hit = SAMPLE_RESULTS.get(key)
    if hit is not None:
        return JSONResponse({**hit, "job": job},
                            headers=_timing({}, time.monotonic() - started))
    os.makedirs(os.path.join(UPLOADS, job), exist_ok=True)
    payload = _result(job, path, name, enabled)
    headers = _timing(payload, time.monotonic() - started)
    # AI 채점이 실패했거나 답변·번역이 아직이면 저장하지 않는다. 반쪽 결과가 굳는다.
    ai_done = (payload["scorecard"] or {}).get("ai_model") or not ai_review.providers() \
        or (enabled is not None and "AI_PROJECTION" not in enabled)
    if ai_done and not payload["ai_extra"]:
        if len(SAMPLE_RESULTS) >= SAMPLE_KEEP:
            SAMPLE_RESULTS.pop(next(iter(SAMPLE_RESULTS)))
        SAMPLE_RESULTS[key] = payload
    return JSONResponse(payload, headers=headers)


@app.post("/api/analyze-path")
def analyze_path(body: dict, request: Request):
    if not _is_local(request):
        raise HTTPException(
            403, "경로 분석은 이 컴퓨터에서만 사용할 수 있습니다. "
                 "원격에서는 파일을 업로드하세요.")
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
    stats.bump(request, "check")
    return _done(request, _run(job, path, os.path.basename(path), _enabled(body)))


def _enabled(src):
    if not src or "checks" not in src or src["checks"] is None:
        return None
    v = src["checks"]
    if isinstance(v, str):
        v = [x for x in v.split(",") if x.strip()]
    return set(v)


@app.post("/api/analyze")
def analyze(request: Request,
            file: UploadFile = File(...),  # noqa: B008 -- FastAPI declares deps this way
            checks: str = Form(None)):
    name = os.path.basename(file.filename or "upload")
    ext = os.path.splitext(name)[1].lower()
    openable = _openable()
    if ext not in openable and ext != ".zip":
        if ext in check.INVENTOR_EXT:
            raise HTTPException(400, check.inventor_help(ext))
        extra = ""
        if ext == ".dwg":
            extra = (" 이 서버에는 DWG 변환기가 없습니다. CAD에서 "
                     "'다른 이름으로 저장 > DXF'로 내보낸 뒤 올리세요.")
        raise HTTPException(400, f"지원하지 않는 형식입니다: {ext or '(확장자 없음)'}. "
                                 f"지원: {', '.join(sorted(openable))}, .zip.{extra}")

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
    stats.bump(request, "check")
    return _done(request, _run(job, path, name, _enabled({"checks": checks})))


class _TooBig(Exception):
    pass


def _extract(zpath, root):
    """Extract into root, skipping entries that escape it. Counts bytes actually
    written -- a zip header can understate the real size, so file_size is not a
    safe limit on its own."""
    written = 0
    with zipfile.ZipFile(zpath) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            dest = os.path.abspath(os.path.join(root, info.filename))
            if not dest.startswith(os.path.abspath(root) + os.sep):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as out:
                while chunk := src.read(1 << 20):
                    written += len(chunk)
                    if written > MAX_BYTES:
                        raise _TooBig
                    out.write(chunk)


def _unzip(zpath, workdir):
    root = os.path.join(workdir, "z")
    os.makedirs(root, exist_ok=True)
    try:
        _extract(zpath, root)
    except _TooBig:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(413, "압축을 풀면 너무 커집니다 (최대 200MB).") from None
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
    found.sort()
    return found[0], os.path.basename(found[0])


EXTRAS = {}                 # job -> [started, 화면에 보낼 몫 or None]
EXTRAS_LOCK = threading.Lock()


def _background(job, work):
    """결과 응답 뒤에 이어지는 일. 화면은 /api/ai-extra/{job} 으로 받아 간다.
    ponytail: 서버 메모리에만 두므로 프로세스가 하나일 때만 맞다. 늘리면 캐시 파일로 옮긴다."""
    def run():
        try:
            work(lambda body: _put_extra(job, body))
        except Exception:                                     # noqa: BLE001
            traceback.print_exc()
            _put_extra(job, {"full": False, "more": False, "findings": []})

    with EXTRAS_LOCK:
        cutoff = time.time() - JOB_TTL_SEC
        for old in [k for k, (started, _) in EXTRAS.items() if started < cutoff]:
            del EXTRAS[old]
        EXTRAS[job] = [time.time(), None]
    threading.Thread(target=run, daemon=True).start()


def _put_extra(job, body):
    with EXTRAS_LOCK:
        if job in EXTRAS:
            EXTRAS[job][1] = body


def _start_extras(job, later):
    """AI 질문 답변·번역을 결과 응답 뒤에 만든다. 점수와 지적은 이미 나가 있고,
    기다리면 호출 하나(실측 13초)만큼 결과가 늦어진다."""
    def work(put):
        put(_extras_body(later()))

    _background(job, work)


def _extras_body(out):
    return {"full": False, "more": False,
            "findings": [{"ai_index": f.get("ai_index"), "i18n": f.get("i18n") or {},
                          "followups": f.get("followups") or {}}
                         for f in (out or {}).get("findings") or []],
            "verdict_i18n": (out or {}).get("verdict_i18n") or {}}


def _start_late_ai(job, facts, enabled, pending):
    """AI 채점이 상한 안에 안 끝났을 때. 결과는 이미 나갔고, 채점이 오면 그 점수까지
    넣어 다시 채점한 판을 올려 둔다. 화면이 받아 점수·지적을 바꿔 그린다."""
    def work(put):
        projection = pending.result()
        later = (projection or {}).pop("later", None)
        put(_regraded(facts, enabled, projection, more=bool(later)))
        if later:
            put(_regraded(facts, enabled, later(), more=False))

    _background(job, work)


def _regraded(facts, enabled, projection, more):
    import exam

    findings, scorecard = exam.grade(facts, enabled, projection)
    facts["scorecard"] = scorecard
    return {"full": True, "more": more, "scorecard": scorecard,
            "summary": scorecard["summary"], "findings": findings,
            "verdict_i18n": (projection or {}).get("verdict_i18n") or {}}


@app.get("/api/ai-extra/{job}")
def ai_extra(job: str):
    with EXTRAS_LOCK:
        item = EXTRAS.get(job)
        body = item[1] if item else None
    if item is None:
        raise HTTPException(404, "그런 검사가 없습니다.")
    if body is None:
        return {"ready": False}
    return {"ready": True, **body}


def _run(job, path, name, enabled=None):
    started = time.monotonic()
    payload = _result(job, path, name, enabled)
    return JSONResponse(payload, headers=_timing(payload, time.monotonic() - started))


def _timing(payload, total):
    """어디서 시간이 갔는지 브라우저 개발자도구와 curl 로 볼 수 있게 남긴다."""
    spent = payload.pop("timing", None) or {}
    parts = [f"{k};dur={v * 1000:.0f}" for k, v in spent.items()]
    return {"Server-Timing": ", ".join([*parts, f"total;dur={total * 1000:.0f}"])}


# 검사 한 번을 이 안에 끝낸다. AI 채점이 늦으면 기다리지 않고 나머지 결과를 먼저 보내고,
# 채점이 오면 화면이 /api/ai-extra 로 받아 채운다.
AI_WAIT_SEC = float(os.environ.get("CADLENS_AI_WAIT", "8"))


def _result(job, path, name, enabled=None):
    _prune_uploads()
    try:
        facts, findings, summary = check.analyze(path, enabled=enabled, alongside=_render,
                                                 defer_extras=True, ai_wait=AI_WAIT_SEC)
    except Exception as e:
        traceback.print_exc()
        # Traceback already went to the log; the client only needs the summary.
        raise HTTPException(500, f"분석 실패: {type(e).__name__}: {e}") from None

    svg, marked, marker_index, svg_note, svg_tf, fix = facts["alongside"]
    later, pending = facts.get("ai_later"), facts.get("ai_late")
    if pending is not None:
        _start_late_ai(job, facts, enabled, pending)
    elif later:
        _start_extras(job, later)
    payload = {
        "ai_extra": bool(later or pending), "ai_pending": pending is not None,
        "job": job, "file": name, "kind": facts.get("kind"),
        "props": facts.get("props", {}),
        "standard": facts.get("standard"),
        "first_angle": facts.get("first_angle"),
        "summary": summary, "findings": findings,
        "scorecard": facts.get("scorecard"),
        "notes_text": facts.get("notes_text") or [],
        "stats": _stats(facts),
        "svg": svg, "markers_placed": marked, "marker_index": marker_index,
        "svg_tf": svg_tf,
        "svg_note": svg_note,
        "fix": _fix_layer(fix, findings),
        "timing": facts.get("timing") or {},
    }
    return payload


DIM_CODES = ("EX_DIM_MISSING", "EX_NO_DIMS")


def _fix_layer(fix, findings):
    """'수정 예시' 로 화면에 얹을 것. 지적이 안 뜬 쪽(검사를 끈 경우)은 뺀다."""
    import fixdraw

    codes = {f["code"] for f in findings}
    return fixdraw.layer(fix, dims=any(c in codes for c in DIM_CODES),
                         centers="EX_NO_CENTERLINE" in codes)


def _render(facts):
    dxf = facts.get("dxf")
    if not dxf or not os.path.exists(dxf):
        return None, False, [], "이 형식은 2D 도면 미리보기를 만들지 않습니다.", None, None
    import dwg
    markers, index = [], []
    for sh in facts.get("sheets", []):
        finding_code = "EX_DIM_MISSING" if sh.get("dims") else "EX_NO_DIMS"
        for c in sh.get("undimensioned", []):
            if c.get("dxf_x") is None:
                continue
            markers.append(c)
            index.append({"n": len(markers), "diameter_mm": c["diameter_mm"],
                          "count": c.get("count", 1),
                          "sheet": sh.get("name"),
                          "finding_code": finding_code,
                          "dxf_x": c["dxf_x"], "dxf_y": c["dxf_y"],
                          "dxf_r": c.get("dxf_r")})
    try:
        rec = facts.get("record") or dwg.record(facts)
        svg, tf, placed = dwg.svg_from(rec, markers)
    except Exception as e:
        traceback.print_exc()
        print(f"[svg] 렌더 실패: {type(e).__name__}: {e}", flush=True)
        return None, False, [], f"도면 미리보기를 만들지 못했습니다 — {type(e).__name__}: {e}", None, None
    return svg, bool(placed), index[:placed], None, tf, _fix_plan(facts, svg, tf)


def _fix_plan(facts, svg, tf):
    """'수정 예시' 로 그릴 것을 미리 계산해 둔다. AI 채점을 기다리는 동안 같이 한다.

    지적이 뜨는지(검사를 껐는지)는 채점이 끝나야 알 수 있어서, 치수와 중심선을 따로
    담아 두고 `_fix_layer` 가 뜬 지적만 골라 얹는다."""
    import exam
    import fixdraw

    sheet = (facts.get("sheets") or [{}])[0]
    try:
        return fixdraw.plan(sheet, facts.get("unit_mm_per_drawing_unit"), svg, tf,
                            centers=exam.lacks_center_lines(sheet))
    except Exception as e:                                    # noqa: BLE001
        traceback.print_exc()
        print(f"[fix] 수정 예시 계산 실패: {type(e).__name__}: {e}", flush=True)
        return None


def _stats(facts):
    s = {"kind": facts.get("kind")}
    sheets = facts.get("sheets") or []
    if sheets:
        s["sheets"] = len(sheets)
        s["dims"] = sum(len(x.get("dims", [])) for x in sheets)
        s["undimensioned"] = sum(len(x.get("undimensioned", [])) for x in sheets)
        s["title_block"] = sheets[0].get("title_block") or sheets[0].get("border")
        s["views"] = sum(len(x.get("views", [])) for x in sheets)
    return s


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("CADCHECK_PORT", "8000"))
    print(f"\n  http://127.0.0.1:{port}  <- 브라우저에서 열기\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
