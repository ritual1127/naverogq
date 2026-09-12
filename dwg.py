import collections
import glob
import math
import os
import re
import shutil
import subprocess
import tempfile
import traceback
from typing import Any

import ezdxf
from ezdxf import bbox
from ezdxf import recover
from ezdxf.addons import Importer
from ezdxf.enums import TextEntityAlignment
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing import layout as dlayout
from ezdxf.addons.drawing import svg as dsvg
from ezdxf.addons.drawing.config import Configuration, LineweightPolicy

MARGIN_MM = 5.0
CENTER_TOL = 0.5
ERR_LAYER = "_CHECKER_ERRORS"

DIM_LINEAR, DIM_ALIGNED, DIM_ANGULAR, DIM_DIAMETER, DIM_RADIUS = 0, 1, 2, 3, 4


HERE = os.path.dirname(os.path.abspath(__file__))
LIBREDWG = os.path.join(HERE, "vendor", "libredwg", "dwg2dxf.exe")


def find_libredwg():
    if os.path.exists(LIBREDWG):
        return LIBREDWG
    return shutil.which("dwg2dxf")


def find_oda():
    pats = (r"C:\Program Files\ODA\*\ODAFileConverter.exe",
            r"C:\Program Files\ODA\*\*\ODAFileConverter.exe",
            r"C:\Program Files (x86)\ODA\*\ODAFileConverter.exe")
    for p in pats:
        hits = glob.glob(p)
        if hits:
            return hits[0]
    return None


def dwg_via_libredwg(dwg_path, out_dxf):
    exe = find_libredwg()
    if not exe:
        return False
    r = subprocess.run([exe, "-y", "-o", out_dxf, os.path.abspath(dwg_path)],
                       capture_output=True, timeout=300,
                       cwd=os.path.dirname(exe))
    if r.returncode != 0 or not os.path.exists(out_dxf):
        return False
    if dxf_has_content(out_dxf):
        return True
    return recover_orphaned_paper_views(out_dxf)


REAL_ENTITIES = {"LINE", "CIRCLE", "ARC", "DIMENSION", "POLYLINE", "LWPOLYLINE",
                 "SPLINE", "ELLIPSE", "TEXT", "MTEXT", "INSERT", "HATCH", "LEADER"}


def readfile(path):
    """Open a DXF, falling back to ezdxf's recovery reader.

    Files written by other CAD programs are often slightly malformed and
    ezdxf.readfile() raises on them, while AutoCAD opens them fine. Our own
    synthetic samples are always clean so this never showed up until a
    third-party file was tried (P11)."""
    try:
        return ezdxf.readfile(path)
    except Exception:
        doc, auditor = recover.readfile(path)
        print(f"[dwg] 손상된 DXF 를 복구해서 열었습니다 "
              f"(오류 {len(auditor.errors)} · 고침 {len(auditor.fixes)}): "
              f"{os.path.basename(path)}", flush=True)
        return doc


def dxf_has_content(path):
    try:
        d = readfile(path)
    except Exception:
        return False
    for name in d.layout_names():
        try:
            for e in d.layouts.get(name):
                if e.dxftype() in REAL_ENTITIES:
                    return True
        except Exception:
            continue
    return False


_VIEW_BLOCK_RE = re.compile(r"(?:뷰|view)\s*(\d+)$", re.IGNORECASE)
_ANON_BLOCK_RE = re.compile(r"^\*I\d+$", re.IGNORECASE)


def recover_orphaned_paper_views(path):
    """Restore Inventor drawing views that LibreDWG leaves as orphan blocks."""
    try:
        doc = readfile(path)
    except Exception:
        return False

    viewports = []
    for name in doc.layout_names():
        if name.lower() == "model":
            continue
        try:
            viewports.extend(v for v in doc.layouts.get(name).query("VIEWPORT")
                             if v.dxf.get("id", 0) > 1)
        except Exception:
            continue
    viewports.sort(key=lambda v: v.dxf.get("id", 0))

    view_blocks = []
    annotation_blocks = []
    for block in doc.blocks:
        match = _VIEW_BLOCK_RE.search(block.name)
        if match and any(e.dxftype() in REAL_ENTITIES for e in block):
            view_blocks.append((int(match.group(1)), block))
            continue
        if _ANON_BLOCK_RE.match(block.name) and not list(block.query("INSERT")):
            if any(e.dxftype() in REAL_ENTITIES for e in block):
                annotation_blocks.append(block)

    view_blocks.sort(key=lambda item: item[0])
    if not viewports or not view_blocks:
        return False

    target = ezdxf.new("R2013")
    importer = Importer(doc, target)
    try:
        for _, block in view_blocks:
            importer.import_block(block.name, rename=False)
        for block in annotation_blocks:
            importer.import_block(block.name, rename=False)
        importer.finalize()
    except Exception:
        return False

    model = target.modelspace()
    restored = 0
    for viewport, (_, block) in zip(viewports, view_blocks):
        center = viewport.dxf.center
        view_height = float(viewport.dxf.get("view_height", 0.0) or 0.0)
        scale = float(viewport.dxf.height) / view_height if view_height > 0 else 1.0
        model.add_blockref(block.name, (center.x, center.y), dxfattribs={
            "xscale": scale, "yscale": scale, "zscale": scale})
        restored += 1
    for block in annotation_blocks:
        model.add_blockref(block.name, (0, 0))

    fd, recovered = tempfile.mkstemp(suffix=".dxf", prefix="dwg_recovered_")
    os.close(fd)
    try:
        target.saveas(recovered)
        if not dxf_has_content(recovered):
            return False
        os.replace(recovered, path)
    except Exception:
        return False
    finally:
        if os.path.exists(recovered):
            os.unlink(recovered)
    ok = dxf_has_content(path)
    if ok:
        print(f"[dwg] LibreDWG 종이공간 뷰 {restored}개 복원", flush=True)
    return ok


CLOUDCONVERT_API = "https://api.cloudconvert.com/v2"


def find_cloudconvert():
    return os.environ.get("CLOUDCONVERT_API_KEY") or None


def _cc_check(resp, what):
    if resp.ok:
        return resp
    body = ""
    try:
        j = resp.json()
        body = j.get("message") or j.get("error") or ""
        if j.get("errors"):
            body += " " + str(j["errors"])
    except Exception:
        body = (resp.text or "")[:200]
    raise RuntimeError(f"{what} HTTP {resp.status_code} {body}".strip())


def _cc_post(send, what, attempts=3):
    import time

    import requests

    last = None
    for i in range(attempts):
        try:
            resp = send()
            if resp.status_code < 500 and resp.status_code != 429:
                return _cc_check(resp, what)
            last = RuntimeError(f"{what} HTTP {resp.status_code}")
        except requests.RequestException as e:
            last = RuntimeError(f"{what} {type(e).__name__}: {e}")
        if i < attempts - 1:
            print(f"[dwg] CloudConvert 일시 오류, 재시도 {i + 1}/{attempts - 1}: "
                  f"{last}", flush=True)
            time.sleep(2 * (i + 1))
    raise last


def dwg_via_cloudconvert(dwg_path, out_dxf, timeout=300):
    key = find_cloudconvert()
    if not key:
        return False
    import time

    import requests

    head = {"Authorization": "Bearer " + key}
    job = _cc_post(
        lambda: requests.post(
            f"{CLOUDCONVERT_API}/jobs", headers=head, timeout=60,
            json={"tasks": {
                "up": {"operation": "import/upload"},
                "conv": {"operation": "convert", "input": "up",
                         "input_format": "dwg", "output_format": "dxf"},
                "exp": {"operation": "export/url", "input": "conv"}}}),
        "작업 생성")
    data = job.json()["data"]
    up = next((t for t in data["tasks"] if t["name"] == "up"), None)
    form = (up or {}).get("result", {}) or {}
    form = form.get("form")
    if not form:
        raise RuntimeError("업로드 주소를 받지 못했습니다 "
                           f"(업로드 작업 상태: {(up or {}).get('status')})")

    def upload():
        with open(dwg_path, "rb") as fh:
            return requests.post(
                form["url"], data=form["parameters"], timeout=timeout,
                files={"file": ("input.dwg", fh, "application/acad")})

    _cc_post(upload, "파일 업로드")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = requests.get(f"{CLOUDCONVERT_API}/jobs/{data['id']}",
                             headers=head, timeout=30).json()["data"]
        if state["status"] == "error":
            why = "; ".join(
                f"{t.get('name')}: {t.get('message') or t.get('code')}"
                for t in state["tasks"] if t.get("status") == "error")
            raise RuntimeError("CloudConvert 작업 실패 — " + (why or "사유 불명"))
        if state["status"] == "finished":
            exp = next(t for t in state["tasks"] if t["name"] == "exp")
            url = exp["result"]["files"][0]["url"]
            with requests.get(url, stream=True, timeout=timeout) as resp:
                resp.raise_for_status()
                with open(out_dxf, "wb") as out:
                    for chunk in resp.iter_content(1 << 20):
                        out.write(chunk)
            return dxf_has_content(out_dxf)
        time.sleep(2)
    return False


def dwg_converter_name():
    if find_libredwg():
        return "LibreDWG"
    if find_oda():
        return "ODA File Converter"
    if find_cloudconvert():
        return "CloudConvert (외부 API)"
    return None


def has_dwg_support():
    return dwg_converter_name() is not None


SHORT_NAME = {"dwg_via_libredwg": "LibreDWG",
              "dwg_via_cloudconvert": "CloudConvert"}


def dwg_to_dxf(dwg_path: str) -> str:
    """Convert a DWG to DXF and return the new path. Tries LibreDWG, then
    CloudConvert, then ODA, and raises RuntimeError if none of them work.

    The returned DXF lives in a temp directory that the caller owns -- it is read
    again for rendering. Only the temp directories that do not hold the result are
    cleaned up here."""
    # ponytail: the surviving temp dir is left to the OS temp sweep. Deleting it
    # per request means wrapping this call in a context manager at the caller.
    work = tempfile.mkdtemp(prefix="dwg_conv_")
    tried = []
    for fn in (dwg_via_libredwg, dwg_via_cloudconvert):
        label = SHORT_NAME.get(fn.__name__, fn.__name__)
        out = os.path.join(work, f"{fn.__name__}.dxf")
        try:
            if fn(dwg_path, out):
                print(f"[dwg] {label}: 변환 성공", flush=True)
                return out
            print(f"[dwg] {label}: 사용 불가 또는 빈 결과", flush=True)
        except Exception as e:
            reason = f"{label}: {e}".strip()
            tried.append(reason)
            print(f"[dwg] {reason}", flush=True)
            traceback.print_exc()
            continue

    # Past this point nothing in work is used again -- the successful branches
    # above already returned the file they left there.
    shutil.rmtree(work, ignore_errors=True)

    exe = find_oda()
    if not exe:
        if not has_dwg_support():
            raise RuntimeError(
                "이 서버는 DWG를 열 수 없습니다. DWG를 DXF로 바꿔 주는 변환기가 "
                "설치되어 있지 않습니다. CAD에서 '다른 이름으로 저장 > DXF'로 "
                "내보낸 뒤 올리시면 그대로 채점됩니다."
            )
        detail = (" 변환기가 남긴 사유 — " + " | ".join(tried)) if tried else ""
        raise RuntimeError(
            "이 DWG를 변환하지 못했습니다. CAD에서 '다른 이름으로 저장 > DXF'로 "
            "내보낸 뒤 올리시면 그대로 채점됩니다." + detail
        )
    src = tempfile.mkdtemp(prefix="oda_in_")
    dst = tempfile.mkdtemp(prefix="oda_out_")
    base = os.path.basename(dwg_path)
    try:
        with open(dwg_path, "rb") as a, open(os.path.join(src, base), "wb") as b:
            b.write(a.read())
        subprocess.run([exe, src, dst, "ACAD2018", "DXF", "0", "1", "*.DWG"],
                       check=False, timeout=300,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        # The input copy is dead weight once the converter has run. dst is not
        # touched here -- it holds the DXF we are about to return.
        shutil.rmtree(src, ignore_errors=True)
    out = glob.glob(os.path.join(dst, "*.dxf")) + glob.glob(os.path.join(dst, "*.DXF"))
    if not out:
        shutil.rmtree(dst, ignore_errors=True)
        raise RuntimeError("ODA File Converter가 DXF를 생성하지 못했습니다. "
                           "DWG 파일이 손상되었을 수 있습니다.")
    return out[0]


def _walk(entities, depth=0, seen=frozenset()):
    for e in entities:
        if e.dxftype() == "INSERT":
            if depth > 4 or e.dxf.name in seen:
                continue
            try:
                yield from _walk(e.virtual_entities(), depth + 1, seen | {e.dxf.name})
            except Exception:
                continue
        else:
            yield e


def _dim_tolerance(dim):
    try:
        ovr = dim.override()
    except Exception:
        return "none", None, None
    tp = ovr.get("dimtp") or 0.0
    tm = ovr.get("dimtm") or 0.0
    if ovr.get("dimlim"):
        return "limits", tp, -tm
    if ovr.get("dimtol"):
        if tp == tm:
            return "symmetric", tp, -tm
        return "deviation", tp, -tm
    return "none", None, None


def _dim_center(dim):
    try:
        t = dim.dimtype & 7
        if t == DIM_RADIUS:
            p = dim.dxf.defpoint
            return (p.x, p.y)
        if t == DIM_DIAMETER:
            a, b = dim.dxf.defpoint, dim.dxf.defpoint4
            return ((a.x + b.x) / 2, (a.y + b.y) / 2)
    except Exception:
        pass
    return None


_SURFACE_VALUE_RE = re.compile(r"\b(?:Ra|Rz|Ry|Rmax)\s*[:=]?\s*([\d.]+)", re.I)
_SURFACE_MARK_RE = re.compile(r"[√∇]")
_FINISH_LETTER_RE = re.compile(r"^(?:[√∇]\s*([wxyzWXYZ])|([wxyz]))\s*$")
_NO_MACHINING_RE = re.compile(r"주조|흑피|비가공|제거\s*가공\s*안", re.I)
_GDT_CHARS = "⊥∥◎⌭⌖⌒∠⟂⌰⊙⏥⌓↗⌭"
_GDT_TEXT_RE = re.compile(rf"[{_GDT_CHARS}]|\\Fgdt|%%v")
_DATUM_RE = re.compile(r"^[A-Z](?:\s*\(?[MLP]\)?)?$")
_CENTER_RE = re.compile(r"cent|중심|dashdot|1점\s*쇄선|일점\s*쇄선", re.I)
_TITLE_TEXT_RE = re.compile(r"품\s*명|도\s*명|품\s*번|도\s*번|재\s*질|척\s*도|투상법|각법|"
                            r"수\s*량|작성자|설계자|검도|\bSCALE\b|\bMATERIAL\b|"
                            r"\bPART\s*N|\bDRAWN\b", re.I)
MIN_TITLE_TEXT_HITS = 2
_NOTE_KEYWORD_RE = re.compile(r"주서|일반\s*공차|2768|열처리|담금질|침탄|질화|도금|도장|"
                              r"모[떼따]기|라운드|필렛|거칠기|다듬질|HRC|주기", re.I)
# "단면도 A-A (1:1)" 같은 뷰 이름표는 12자가 넘어도 주서가 아니다.
# 이걸 주서로 세면 주서가 통째로 없는 도면에서도 "주서 없음"이 안 뜬다.
_VIEW_LABEL_RE = re.compile(
    r"^(정면도|평면도|배면도|저면도|좌측면도|우측면도|측면도|입면도|등각투상도|"
    r"단면도|부분\s*단면도|회전\s*단면도|상세도|확대도|"
    r"section|detail|view)\b", re.I)
# Inventor 가 붙이는 뷰 이름표는 낱말이 아니라 글자로 시작한다 —
# `A-A ( 1 : 1 ) / .` · `B ( 2 : 1 ) / .` · `단면A-A` · `확대도-B`.
# 위 목록으로는 안 걸리고 12자가 넘어 주서로 세고 있었다. 실제 수험생 도면
# 30장 중 8장에서 이것 때문에 "주서 없음"(8점)을 놓쳤다.
_VIEW_TAG_RE = re.compile(
    r"^(?:단면|상세|확대)?\s*도?\s*-?\s*[A-Z](?:\s*-\s*[A-Z])?\s*"
    r"(?:\(\s*[\d.]+\s*:\s*[\d.]+\s*\))?\s*[/.\s]*$")
# 글자도 숫자도 없이 괄호·쉼표뿐인 것은 주서가 아니다. 표면거칠기 비교표의
# 빈 칸 `(      ,      ,      )` 이 주서로 세어지고 있었다.
_HAS_WORD_RE = re.compile(r"[0-9A-Za-z가-힣]")
MIN_NOTE_LEN = 12


def _is_note(text):
    t = (text or "").strip()
    if not t or not _HAS_WORD_RE.search(t):
        return False
    if _VIEW_LABEL_RE.match(t) or _VIEW_TAG_RE.match(t):
        return False
    if _ROUGH_TABLE_RE.match(t):
        return False        # 거칠기 비교표 `√( √w , √x , √y )` 는 주서가 아니다
    return "\n" in t or len(t) >= MIN_NOTE_LEN or bool(_NOTE_KEYWORD_RE.search(t))


BORDER_MIN_SPAN = 0.6          # 도면에서 제일 큰 사각형의 몇 배 이상이어야 윤곽선인가


def _rect_size(entity):
    """축에 나란한 닫힌 사각형이면 (폭, 높이). 아니면 None."""
    try:
        if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
            return None
        pts = entity.get_points("xy")
    except Exception:
        return None
    if len(pts) != 4:
        return None
    xs = {round(p[0], 3) for p in pts}
    ys = {round(p[1], 3) for p in pts}
    if len(xs) != 2 or len(ys) != 2:
        return None
    return max(xs) - min(xs), max(ys) - min(ys)


def _is_border(entity):
    return _rect_size(entity) is not None


def _rect_box(entity, K):
    """닫힌 사각형 윤곽선의 (x0, y0, x1, y1) mm."""
    try:
        pts = entity.get_points("xy")
    except Exception:
        return None
    xs = [p[0] * K for p in pts]
    ys = [p[1] * K for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


BORDER_MIN_EDGE_MM = 150.0     # 이보다 짧은 변은 윤곽선이 아니다
BORDER_AXIS_TOL_MM = 0.2       # 축에 나란하다고 볼 기울기


def _line_border(lines, K):
    """축에 나란한 선 네 개로 그린 윤곽선의 (폭mm, 높이mm). 아니면 None.

    실기 도면의 윤곽선은 닫힌 폴리선이 아니라 **선 네 개**다. 실제 수험생 도면
    30장에서 닫힌 사각형 윤곽선은 한 장도 없었고, 그 바람에 윤곽선을 못 찾아
    (1) 모든 도면에 "표제란·도면양식 없음"이 떴고 (2) 도면 크기를 아예 재지
    않아 A2 요구 판정이 통째로 빠졌다.

    바깥쪽 끝의 가로선 두 개·세로선 두 개가 실제로 사각형을 이룰 때만 인정한다.
    긴 형상선이 섞여 사각형이 안 맞으면 None 을 돌려 예전처럼 조용히 넘어간다."""
    tol = BORDER_AXIS_TOL_MM / K if K else BORDER_AXIS_TOL_MM
    edge = BORDER_MIN_EDGE_MM / K if K else BORDER_MIN_EDGE_MM
    hor, ver = [], []
    for x1, y1, x2, y2 in lines:
        if abs(y1 - y2) <= tol and abs(x1 - x2) >= edge:
            hor.append((y1, min(x1, x2), max(x1, x2)))
        elif abs(x1 - x2) <= tol and abs(y1 - y2) >= edge:
            ver.append((x1, min(y1, y2), max(y1, y2)))
    if len(hor) < 2 or len(ver) < 2:
        return None
    x0, x1 = min(v[0] for v in ver), max(v[0] for v in ver)
    y0, y1 = min(h[0] for h in hor), max(h[0] for h in hor)

    def spans(edges, at, lo, hi):
        return any(abs(e[0] - at) <= tol and e[1] <= lo + tol and e[2] >= hi - tol
                   for e in edges)

    if not all((spans(hor, y0, x0, x1), spans(hor, y1, x0, x1),
                spans(ver, x0, y0, y1), spans(ver, x1, y0, y1))):
        return None
    return x0 * K, y0 * K, x1 * K, y1 * K


# 채점 기준 '용도에 맞는 선 굵기'. KS B 0001 은 굵기를 절대값으로 못 박지 않고
# 가는 선 : 굵은 선 : 아주 굵은 선 = 1 : 2 : 4 로 정한다. 실기 도면은 보통
# 윤곽선 0.7 · 외형선 0.5 · 은선 0.35 · 중심선/치수선 0.25 · 해치 0.18 이다.
# 절대값이 아니라 비를 보는 이유는 축척이 다른 도면도 통과시켜야 해서다.
_THICK_LAYER_RE = re.compile(r"외형|가시|visible|outline|continuous\s*thick", re.I)
_THIN_LAYER_RE = re.compile(r"치수|중심|해치|가는|숨은|은\s*선|dim|cent|hatch|thin|hidden",
                            re.I)
_BORDER_LAYER_RE = re.compile(r"경계|윤곽|외곽|border|frame", re.I)


def _layer_widths(doc):
    """레이어 이름과 굵기(mm). 굵기를 안 정한 레이어는 뺀다.

    DXF 는 굵기를 1/100 mm 정수로 담고, 음수는 BYLAYER·BYBLOCK·기본값이라
    실제 굵기가 아니다."""
    out = {}
    for lay in doc.layers:
        try:
            w = int(lay.dxf.get("lineweight", -1))
        except Exception:
            continue
        if w > 0:
            out[lay.dxf.name] = w / 100.0
    return out


def _line_widths(doc):
    """굵기 검사에 쓸 값 — 윤곽선 · 외형선 · 가는 선, 그리고 전체 목록."""
    widths = _layer_widths(doc)
    if not widths:
        return None
    pick = lambda rx: [w for n, w in widths.items() if rx.search(n)]
    thick = max(pick(_THICK_LAYER_RE) or [0.0])
    thin = min(pick(_THIN_LAYER_RE) or [0.0])
    border = max(pick(_BORDER_LAYER_RE) or [0.0])
    return {"outline_mm": thick or None, "thin_mm": thin or None,
            "border_mm": border or None,
            "ratio": round(thick / thin, 2) if thick and thin else None,
            "layers": {n: w for n, w in sorted(widths.items())}}


# 도면틀 밖으로 나간 것을 잴 때 빼는 것들.
# - 중심마크는 원래 윤곽선을 넘어 튀어나온다 (도면 양식의 일부다).
# - 문자는 ezdxf 가 세로로 긴 엉뚱한 경계상자를 줄 때가 있어 믿지 않는다
#   (`A-A ( 1 : 1 ) / .` 한 줄이 12x65mm 로 나왔다).
_OUTSIDE_SKIP_TYPES = {"TEXT", "MTEXT", "VIEWPORT", "POINT", "ATTDEF", "INSERT"}
OUTSIDE_TOL_MM = 3.0


def _outside_frame(msp, box, mm_per_unit):
    """도면틀 밖으로 나간 요소 중 가장 많이 나간 것. 없으면 None.

    수험자 유의사항에 "도면 범위 밖 요소가 출력에 섞이지 않게" 가 있다.
    출력 설정은 DXF 에 없지만 **틀 밖에 그려진 요소는 DXF 에 그대로 있다.**
    실제 수험생 도면에서 윤곽선 오른쪽 174mm 바깥까지 뻗은 선이 나왔다."""
    if not box:
        return None
    x0, y0, x1, y1 = box
    worst = None
    for e in _walk(msp):
        if e.dxftype() in _OUTSIDE_SKIP_TYPES:
            continue
        if _BORDER_LAYER_RE.search(e.dxf.get("layer", "") or ""):
            continue
        try:
            b = bbox.extents([e])
        except Exception:
            continue
        if not b.has_data:
            continue
        over = max(x0 - b.extmin.x * mm_per_unit, b.extmax.x * mm_per_unit - x1,
                   y0 - b.extmin.y * mm_per_unit, b.extmax.y * mm_per_unit - y1)
        if over > OUTSIDE_TOL_MM and (worst is None or over > worst["over_mm"]):
            worst = {"over_mm": round(over, 1), "type": e.dxftype(),
                     "layer": e.dxf.get("layer", "")}
    return worst


# 요목표가 필요한 부품. 기어·스프링은 형상만으로 만들 수 없어서 잇수·모듈·
# 압력각 같은 값을 표로 따로 적어야 한다(공개문제 요구사항).
_SPEC_PART_RE = re.compile(
    r"^(?:\d+\s*[-.]?\s*)?[가-힣A-Za-z ]*"
    r"(스퍼\s*어?\s*기어|헬리컬\s*기어|베벨\s*기어|웜\s*휠|웜|래크|피니언|"
    r"스프로킷|기어|압축\s*스프링|인장\s*스프링|스프링)"
    r"[가-힣A-Za-z ]*$")
_SPEC_TABLE_RE = re.compile(r"요\s*목\s*표")
# 거칠기 비교표는 `√( √x , √y , √z )` 모양이라 문자만 보면 괄호와 쉼표만 남는다.
_ROUGH_TABLE_RE = re.compile(r"^[√∇(]\s*[(,\s√∇wxyzWXYZ]*\)$")
MAX_PART_NAME_LEN = 20


# 요목표 칸에 적히는 말. 주서가 아닌데 주서로 세어지던 것들이다 — 실제 도면
# A32 에서 `다듬질 방법` · `KS B ISO 1328-1, 4급` 때문에 "주서 없음"(8점)을
# 놓쳤다. 요목표가 있는 도면에서만 뺀다.
_SPEC_ROW_RE = re.compile(
    r"^(기어\s*치형|치형|모듈|압력각|잇\s*수|피치원\s*지름|전체\s*이\s*높이|"
    r"이\s*두께|다듬질\s*방법|정밀도|재료|호브절삭|표준|보통이|"
    r"총\s*감김\s*수|유효\s*감김\s*수|감김\s*방향|재료의\s*지름|코일\s*평균\s*지름|"
    r"KS\s*B\s*ISO.*)$", re.I)


def _drop_spec_rows(notes, has_table):
    """요목표가 있는 도면에서는 요목표 칸을 주서로 세지 않는다."""
    if not has_table:
        return notes
    return [t for t in notes if not _SPEC_ROW_RE.match(t.strip())]


def _spec_tables(texts):
    """요목표가 필요한 부품과, 실제로 있는 요목표."""
    parts, tables, rough = [], [], False
    for t in texts:
        s = (t or "").strip()
        if not s:
            continue
        if _SPEC_TABLE_RE.search(s):
            tables.append(s)
            continue
        if len(s) <= MAX_PART_NAME_LEN and _SPEC_PART_RE.match(s):
            parts.append(s)
        if not rough and _ROUGH_TABLE_RE.match(s) and "(" in s:
            rough = True
    return {"needs_spec": sorted(set(parts)), "spec_tables": tables,
            "roughness_table": rough}


def _text_sizes(doc, msp, mm_per_unit):
    """문자 높이(mm). 치수 문자는 치수 스타일에, 나머지는 글자마다 들어 있다.

    치수 스타일은 **실제로 치수가 쓰는 것만** 본다. CAD 가 만들어 두는 안 쓰는
    스타일이 수십 개씩 있고 그중에는 높이 0.0025 짜리도 있어서, 전부 훑으면
    도면과 상관없는 값이 나온다."""
    used = collections.Counter(e.dxf.get("dimstyle", "") or ""
                               for e in _walk(msp) if e.dxftype() == "DIMENSION")
    heights = collections.Counter()
    for st in doc.dimstyles:
        n = used.get(st.dxf.name, 0)
        if not n:
            continue
        try:
            h = float(st.dxf.get("dimtxt", 0)) * float(st.dxf.get("dimscale", 1) or 1)
        except Exception:
            continue
        if h > 0:
            heights[round(h * mm_per_unit, 2)] += n
    # 치수 대부분이 쓰는 높이를 그 도면의 치수 문자 크기로 본다. 최솟값을 쓰면
    # 지름 치수 하나가 다른 스타일을 쓰는 것만으로 도면 전체가 틀린 게 된다.
    dim_mm = heights.most_common(1)[0][0] if heights else None
    heights = set()
    for e in _walk(msp):
        t = e.dxftype()
        if t not in ("TEXT", "MTEXT"):
            continue
        try:
            h = float(e.dxf.char_height if t == "MTEXT" else e.dxf.height)
        except Exception:
            continue
        if h > 0:
            heights.add(round(h * mm_per_unit, 2))
    return {"dim_mm": dim_mm, "heights_mm": sorted(heights)}


def _drawn_span(rects, circles):
    """그려진 것이 차지하는 폭과 높이. 윤곽선인지 재는 잣대."""
    xs, ys = [], []
    for r in rects:
        try:
            pts = r.get_points("xy")
        except Exception:
            continue
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    for c in circles:
        xs += [c["x"] - c["r"], c["x"] + c["r"]]
        ys += [c["y"] - c["r"], c["y"] + c["r"]]
    if not xs or not ys:
        return 0.0, 0.0
    return max(xs) - min(xs), max(ys) - min(ys)


def _surface_symbol(text):
    t = (text or "").strip()
    if not t or len(t) > 40:
        return None
    if _is_note(t) or _ROUGH_TABLE_RE.match(t):
        # 비교표 `√( √w , √x , √y )` 는 면에 붙은 기호가 아니라 정의표다.
        # 기호로 세면 값이 빈 기호로 잡혀 없는 감점을 만든다.
        return None
    value = _SURFACE_VALUE_RE.search(t)
    letter = _FINISH_LETTER_RE.match(t)
    if not value and not letter and not _SURFACE_MARK_RE.search(t):
        return None
    mark = (letter.group(1) or letter.group(2)).lower() if letter else None
    return {"max": value.group(1) if value else mark,
            "min": None, "method": None,
            "no_machining": bool(_NO_MACHINING_RE.search(t)), "text": t}


def _geometric_tol(text):
    t = (text or "").strip()
    if not t or not _GDT_TEXT_RE.search(t):
        return None
    body = re.sub(r"\{?\\[A-Za-z][^;}]*;?", "", t).replace("}", "")
    parts = [p.strip() for p in re.split(r"%%v|\|", body) if p.strip()]
    tol = next((p for p in parts if re.search(r"\d", p)), None)
    datums = [p for p in parts if _DATUM_RE.match(p)]
    return {"tolerance": tol, "datums": datums, "text": t}


SYMBOL_ZONE_FACTOR = 4.0
# 투상법 기호는 원 두 개로 그린다. 치수를 넣는 자리가 아닌데 미치수 구멍으로
# 잡히던 것을 막는다. 기호가 문자에서 떨어져 있어도 덮이게 mm 로 크게 잡는다.
# ponytail: 표제란 구석이라 이 반경 안의 진짜 구멍까지 같이 빠진다.
#           오탐을 줄이는 쪽이 낫다고 보고 넓게 뒀다.
PROJECTION_ZONE_MM = 45.0
_PROJECTION_RE = re.compile(r"제?\s*[13]\s*각\s*법|third\s*angle|first\s*angle", re.I)
MIN_HOLE_DIA_MM = 1.0


def _zone(entity, kind, lines=1):
    try:
        p = entity.dxf.insert
        h = float(entity.dxf.char_height if kind == "MTEXT" else entity.dxf.height)
    except Exception:
        return None
    if not h:
        return None
    return (p.x, p.y, h * SYMBOL_ZONE_FACTOR, h * lines)


def _fixed_zone(entity, mm, k):
    """문자 위치에서 mm 만큼을 통째로 기호 자리로 본다."""
    try:
        p = entity.dxf.insert
    except Exception:
        return None
    reach = mm / k if k else mm
    return (p.x, p.y, reach, reach)


def _in_symbol_zone(cx, cy, zones):
    for z in zones:
        if not z:
            continue
        zx, zy, reach, drop = z
        if abs(cx - zx) <= reach and -(reach + drop) <= cy - zy <= reach:
            return True
    return False


TANGENT_TOL = 0.24
MAX_SYMBOL_LEG_MM = 40.0
INSCRIBED_MIN_LINES = 2


def _line_gap(seg, cx, cy):
    x1, y1, x2, y2 = seg
    dx, dy = x2 - x1, y2 - y1
    length2 = dx * dx + dy * dy
    if length2 <= 0:
        return None
    t = ((cx - x1) * dx + (cy - y1) * dy) / length2
    if not -0.25 <= t <= 1.25:
        return None
    return abs((cx - x1) * dy - (cy - y1) * dx) / math.sqrt(length2)


def _is_inscribed(cx, cy, r, grid, cell):
    if r <= 0:
        return False
    seen, hits = set(), 0
    span = int(r * 2 / cell) + 1
    gx, gy = int(cx // cell), int(cy // cell)
    for ix in range(gx - span, gx + span + 1):
        for iy in range(gy - span, gy + span + 1):
            for idx, seg in grid.get((ix, iy), ()):
                if idx in seen:
                    continue
                seen.add(idx)
                gap = _line_gap(seg, cx, cy)
                if gap is not None and abs(gap - r) <= TANGENT_TOL * r:
                    hits += 1
                    if hits >= INSCRIBED_MIN_LINES:
                        return True
    return False


def _short_line_grid(segments, cell):
    grid = {}
    for idx, seg in enumerate(segments):
        x1, y1, x2, y2 = seg
        for px, py in ((x1, y1), (x2, y2), ((x1 + x2) / 2, (y1 + y2) / 2)):
            grid.setdefault((int(px // cell), int(py // cell)), []).append((idx, seg))
    return grid


def _is_centerline(entity):
    try:
        if _CENTER_RE.search(entity.dxf.get("layer", "") or ""):
            return True
        return _CENTER_RE.search(entity.dxf.get("linetype", "") or "") is not None
    except Exception:
        return False


_UNIT_MM = {1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 2.54e-5,
            9: 0.0254, 10: 914.4, 11: 1e-7, 12: 1e-6, 13: 1e-3, 14: 100.0}
PLAUSIBLE_MM = (5.0, 20000.0)


def detect_mm_per_unit(doc, msp):
    try:
        size = max(bbox.extents(msp).size.x, bbox.extents(msp).size.y)
    except Exception:
        size = 0.0
    declared = _UNIT_MM.get(doc.header.get("$INSUNITS", 0))
    lo, hi = PLAUSIBLE_MM
    if declared and size and lo <= size * declared <= hi:
        return declared, f"$INSUNITS ({declared:g} mm/unit)"
    if size:
        for f in (1.0, 10.0, 25.4, 1000.0, 304.8, 0.0254):
            if lo <= size * f <= hi:
                return f, f"도면 크기로 추정 ({f:g} mm/unit)"
    return 1.0, "mm으로 가정"


# 뷰 뭉치를 찾을 때 쓰는 값. 뷰끼리는 이 정도는 떨어져 있고, 이보다 작은
# 덩어리는 뷰가 아니라 주서나 기호로 본다.
VIEW_GAP_MM = 8.0
VIEW_MIN_MM = 30.0
VIEW_MIN_SHAPES = 5
# 도면 윤곽선과 표제란 테두리는 시트를 가로질러서, 그냥 두면 모든 뷰가 한
# 덩어리로 이어진다. 도면 전체의 이만큼을 덮는 형상은 뷰가 아니라 양식으로 본다.
VIEW_FRAME_SPAN = 0.6
# 뷰 하나가 격자를 이만큼 넘게 차지하면 단위 판정이 틀어진 것이다. 세다가
# 멈추지 않도록 그런 형상은 건너뛴다.
VIEW_MAX_CELLS = 4096

_SHAPE_TYPES = {"LINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE", "LWPOLYLINE",
                "POLYLINE", "HATCH", "SOLID"}


def _shape_boxes(msp, gap):
    """뷰가 될 만한 형상들의 경계 상자를 모은다.

    치수선과 문자는 뷰 바깥으로 뻗어 나가 옆 뷰까지 이어 붙이므로 뺀다.
    윤곽선처럼 시트를 가로지르는 것도 뺀다."""
    try:
        sheet = bbox.extents(msp)
        span = max(sheet.size.x, sheet.size.y) if sheet.has_data else 0.0
    except Exception:
        span = 0.0
    out = []
    for e in msp:
        if e.dxftype() not in _SHAPE_TYPES:
            continue
        try:
            b = bbox.extents([e])
        except Exception:
            continue
        if not b.has_data:
            continue
        if span and max(b.size.x, b.size.y) >= span * VIEW_FRAME_SPAN:
            continue
        if (b.size.x / gap + 1) * (b.size.y / gap + 1) > VIEW_MAX_CELLS:
            continue
        out.append((b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
    return out, span


def _cluster_views(msp, mm_per_unit):
    """뷰 블록이 없는 도면에서 형상 뭉치로 뷰 경계를 추정한다.

    Inventor 로 그린 도면은 뷰가 블록으로 나뉘어 있지만, 다른 도구로 그리면
    모델 공간에 형상이 평평하게 깔려서 뷰 경계를 알 방법이 없었다. 실제
    도면 6장 중 뷰를 아는 것이 1장뿐이라 투상도 관련 검사가 대부분 꺼져
    있었다. 뷰끼리는 빈 공간으로 떨어져 있으므로, 격자에 올려 이어진
    덩어리를 세면 뷰가 나온다.

    추정값이라 뷰 블록에서 읽은 것과 섞이지 않게 detected 를 붙여 둔다."""
    gap = VIEW_GAP_MM / mm_per_unit
    if not (gap > 0):
        return []
    boxes, span = _shape_boxes(msp, gap)
    if not boxes:
        return []

    cells = {}
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        for cx in range(int(x0 // gap), int(x1 // gap) + 1):
            for cy in range(int(y0 // gap), int(y1 // gap) + 1):
                cells.setdefault((cx, cy), []).append(i)

    parent = list(range(len(boxes)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # 같은 칸이거나 맞닿은 칸이면 한 뷰로 본다.
    for (cx, cy), ids in cells.items():
        for j in ids[1:]:
            union(ids[0], j)
        for dx, dy in ((0, 1), (1, 0), (1, 1), (1, -1)):
            for j in cells.get((cx + dx, cy + dy), ()):
                union(ids[0], j)

    groups = {}
    for i in range(len(boxes)):
        groups.setdefault(find(i), []).append(boxes[i])

    views = []
    for g in groups.values():
        if len(g) < VIEW_MIN_SHAPES:
            continue
        x0 = min(b[0] for b in g)
        y0 = min(b[1] for b in g)
        x1 = max(b[2] for b in g)
        y1 = max(b[3] for b in g)
        if span and max(x1 - x0, y1 - y0) >= span * VIEW_FRAME_SPAN:
            # 시트를 거의 다 덮는 덩어리는 뷰가 아니다. 형상 몇 개가 도면
            # 곳곳에 흩어져 있으면 격자에서 하나로 이어지는데, 그대로 두면
            # 762mm 짜리 '뷰' 가 AI 참고 정보로 넘어간다.
            continue
        w, h = (x1 - x0) * mm_per_unit, (y1 - y0) * mm_per_unit
        if min(w, h) < VIEW_MIN_MM:
            continue
        views.append({"shapes": len(g),
                      "x_mm": round((x0 + x1) / 2 * mm_per_unit, 1),
                      "y_mm": round((y0 + y1) / 2 * mm_per_unit, 1),
                      "w_mm": round(w, 1), "h_mm": round(h, 1)})
    views.sort(key=lambda v: (-v["y_mm"], v["x_mm"]))
    return [{"name": f"추정 뷰{i}", "scale": None, "detected": "cluster", **v}
            for i, v in enumerate(views, 1)]


# 정면도를 고를 때 쓰는 값. KS 는 "대상물의 형상을 가장 잘 나타내는 주
# 투상도(정면도)에 치수를 집중하여 기입한다" 고 한다. 그래서 치수가 가장
# 많이 붙은 뷰를 정면도로 본다. 다만 표가 갈리면 고르지 않는다 — 정면도를
# 잘못 짚으면 제3각법 판정이 통째로 뒤집힌다.
FRONT_MIN_DIMS = 5
FRONT_MIN_VOTES = 3
FRONT_MARGIN = 2.0


def _mark_front_view(msp, views, mm_per_unit):
    """치수가 가장 많이 붙은 뷰를 정면도로 표시한다.

    형상 개수로 고르면 안 된다. 실제 도면에서 형상이 가장 많은 덩어리는
    등각투상도였고 거기 붙은 치수는 0개였다. 치수 집중은 같은 도면에서
    30개 중 24개를 정면도에 몰아 줬다."""
    if not views:
        return
    votes = [0] * len(views)
    total = 0
    for e in msp:
        if e.dxftype() not in ("DIMENSION", "LEADER"):
            continue
        try:
            b = bbox.extents([e])
        except Exception:
            continue
        if not b.has_data:
            continue
        total += 1
        x, y = b.center.x * mm_per_unit, b.center.y * mm_per_unit
        inside = [i for i, v in enumerate(views)
                  if v.get("x_mm") is not None
                  and abs(x - v["x_mm"]) <= v["w_mm"] / 2
                  and abs(y - v["y_mm"]) <= v["h_mm"] / 2]
        if inside:
            votes[inside[0]] += 1
            continue
        near = [i for i, v in enumerate(views) if v.get("x_mm") is not None]
        if near:
            votes[min(near, key=lambda j: math.hypot(x - views[j]["x_mm"],
                                                     y - views[j]["y_mm"]))] += 1
    for v, c in zip(views, votes):
        v["dim_count"] = c
    if total < FRONT_MIN_DIMS:
        return
    order = sorted(range(len(views)), key=lambda i: -votes[i])
    best = votes[order[0]]
    second = votes[order[1]] if len(order) > 1 else 0
    if best >= FRONT_MIN_VOTES and best >= max(second * FRONT_MARGIN, second + 1):
        views[order[0]]["is_front"] = True


# 두 뷰가 한 줄에 놓였다고 볼 겹침 비율과, 이웃으로 볼 최대 간격(큰 쪽 크기의 배수).
VIEW_ALIGN_OVERLAP = 0.5
VIEW_ALIGN_GAP = 2.5
# 작은 뷰는 배수만으로 재면 이웃을 놓친다 (40mm 뷰 둘이 110mm 떨어져 있으면
# 2.5배인 100mm 를 넘는다). A2 한 장에서 같은 부품의 투상도는 이 안에 모인다.
VIEW_ALIGN_FLOOR = 120.0
_THIRD_SPOTS = {"above", "right"}
_FIRST_SPOTS = {"below", "left"}
# 제3각법에서 그 자리에 놓이는 뷰 이름. 제1각법이면 위아래·좌우가 뒤집힌다.
_SPOT_NAME_THIRD = {"above": "평면도", "below": "저면도",
                    "right": "우측면도", "left": "좌측면도"}


def _span(v, axis):
    c = v["x_mm"] if axis == "x" else v["y_mm"]
    s = v["w_mm"] if axis == "x" else v["h_mm"]
    return c - s / 2, c + s / 2


def _overlap(a, b, axis):
    a0, a1 = _span(a, axis)
    b0, b1 = _span(b, axis)
    inner = min(a1 - a0, b1 - b0)
    if inner <= 0:
        return 0.0
    return max(0.0, min(a1, b1) - max(a0, b0)) / inner


def _spot(front, v):
    """front 기준으로 v 가 어느 자리에 놓였나. 줄이 안 맞으면 None.

    줄이 안 맞는 뷰는 같은 부품의 투상도가 아니다 — 실기 도면은 한 장에
    본체·축·커버를 같이 그리므로 이것을 투상도로 세면 배치 판정이 뒤집힌다."""
    for axis, near, far, plus, minus in (("x", "y", "h", "above", "below"),
                                         ("y", "x", "w", "right", "left")):
        if _overlap(front, v, axis) < VIEW_ALIGN_OVERLAP:
            continue
        if _overlap(front, v, near) >= VIEW_ALIGN_OVERLAP:
            continue
        key = near + "_mm"
        gap = abs(v[key] - front[key]) - (v[far + "_mm"] + front[far + "_mm"]) / 2
        if gap > max(VIEW_ALIGN_GAP * max(v[far + "_mm"], front[far + "_mm"]),
                     VIEW_ALIGN_FLOOR):
            return None
        return plus if v[key] > front[key] else minus
    return None


def analyze_layout(views):
    """뷰 좌표만으로 정면도를 고르고 이웃 뷰가 제3각법 자리에 있는지 본다.

    투상도 30점 중 '제3각법 배치'는 그림을 봐야 아는 게 아니라 좌표를 비교하면
    나오는 값이다. 지금까지는 AI 에게 통째로 맡겨 왔고, 정면도를 못 고르면
    (실제 도면 30장 중 22장이 그랬다) AI 에게 "배치는 판단하지 마세요" 라고
    보내 그 배점이 사실상 비어 있었다.

    정면도는 '줄이 맞는 이웃이 가장 많은 뷰, 같으면 치수가 많은 뷰' 로 고른다.
    치수만으로 고르면 뷰 세 개가 비슷할 때 못 고른다.

    판정은 한쪽으로만 몰릴 때만 한다. 이웃이 제3각법 자리(위·오른쪽)에만 있으면
    `third`, 제1각법 자리(아래·왼쪽)에만 있으면 `first`, 섞여 있으면 `unknown`
    이다. 섞이는 것은 보통 같은 장에 다른 부품이 있거나 저면도를 쓴 도면이라
    단정하면 안 된다. 실제 도면 30장에서 third 24장 · unknown 6장 · first 0장이
    나왔고 멀쩡한 도면을 first 로 부른 적은 없다."""
    placed = [v for v in views if v.get("x_mm") is not None and v.get("w_mm")]
    if len(placed) < 2:
        return None
    ranked = []
    for cand in placed:
        got = {id(v): s for v in placed if v is not cand
               for s in [_spot(cand, v)] if s}
        ranked.append(((len(got), cand.get("dim_count") or 0), cand, got))
    ranked.sort(key=lambda r: r[0], reverse=True)
    (best, front, spots), runner = ranked[0], ranked[1][0]
    # 비기면 정면도를 고르지 않는다. DWG 를 변환한 도면은 DIMENSION 이 하나도
    # 안 남아 뷰가 전부 동점이 되는데, 그때 아무 뷰나 정면도로 찍으면 위아래가
    # 뒤집혀 멀쩡한 제3각법 도면을 제1각법이라고 부르게 된다.
    if not spots or best == runner or best[1] == 0:
        return None
    for v in placed:
        v["spot"] = spots.get(id(v))
    front["is_front"] = True
    for v in placed:
        if v is not front:
            v.pop("is_front", None)
    seen = set(spots.values())
    verdict = ("third" if seen <= _THIRD_SPOTS else
               "first" if seen <= _FIRST_SPOTS else "unknown")
    if verdict == "third":
        for v in placed:
            if v.get("spot"):
                v["role"] = _SPOT_NAME_THIRD[v["spot"]]
        front["role"] = "정면도"
    return {"verdict": verdict, "front": front.get("name"),
            "spots": sorted(seen),
            "aligned": len(spots), "views": len(placed)}


def _view_box(ins, mm_per_unit):
    """뷰 블록이 도면 어디에 얼마만 한 크기로 놓였는지 밀리미터로 잰다.

    제3각법 배치인지, 뷰가 한쪽으로 치우쳤는지는 그림을 봐야 아는 게 아니라
    좌표를 비교하면 나오는 값이다. 이걸 안 넘기면 AI 가 150 DPI 그림을 보고
    위치를 짐작해야 하고, 그래서 같은 도면을 다시 채점할 때마다 배치 판정이
    달라졌다. 블록 안까지 펼쳐 재는 데 실패하면 삽입점만이라도 넘긴다."""
    try:
        box = bbox.extents([ins])
        if box.has_data:
            center = box.center
            return {"x_mm": round(center.x * mm_per_unit, 1),
                    "y_mm": round(center.y * mm_per_unit, 1),
                    "w_mm": round(box.size.x * mm_per_unit, 1),
                    "h_mm": round(box.size.y * mm_per_unit, 1)}
    except Exception:
        pass
    p = ins.dxf.insert
    return {"x_mm": round(p.x * mm_per_unit, 1),
            "y_mm": round(p.y * mm_per_unit, 1),
            "w_mm": None, "h_mm": None}


# 기하공차 기호를 유니코드(⏥ ⊥ ⌭)로 적는 도면도 있지만, 실제 실기 도면은
# GDT 전용 글꼴(gdt.shx · AIGDT___.TTF)로 알파벳 한 글자를 찍어 기호를 만든다.
# 글자만 보면 그냥 'b' 라서 못 알아본다. 그래서 글꼴 이름으로 가려낸다.
GDT_FONT_RE = re.compile(r"gdt", re.I)
# 공차칸(기호 · 값 · 데이텀)은 한 줄에 나란히 놓인다. 같은 줄로 볼 높이 차이와
# 오른쪽으로 훑을 거리 (mm).
FCF_ROW_MM = 2.5
FCF_SPAN_MM = 45.0
_FCF_VALUE_RE = re.compile(r"^[⌀%\w.]*\d")
# 데이텀은 A 한 글자거나 A-B 처럼 두 개를 묶은 공통 데이텀이다.
_FCF_DATUM_RE = re.compile(r"^[A-Z](?:-[A-Z])?$")


def _gdt_styles(doc):
    out = set()
    for st in doc.styles:
        font = f"{st.dxf.get('font', '') or ''} {st.dxf.get('bigfont', '') or ''}"
        if GDT_FONT_RE.search(font):
            out.add(st.dxf.name)
    return out


def _gdt_frames(glyphs, plain, mm_per_unit):
    """GDT 글꼴 글자 옆에 붙은 공차값·데이텀을 모아 공차칸 하나로 만든다.

    글자만 있고 값도 데이텀도 없으면 공차칸이 아니다. 지름(⌀)이나 최대실체
    같은 부가 기호도 같은 글꼴로 찍히기 때문이다."""
    row = FCF_ROW_MM / mm_per_unit if mm_per_unit else FCF_ROW_MM
    span = FCF_SPAN_MM / mm_per_unit if mm_per_unit else FCF_SPAN_MM
    used, frames = set(), []
    for gx, gy, gtext in sorted(glyphs):
        if any(abs(gy - uy) <= row and abs(gx - ux) <= span for ux, uy in used):
            continue
        near = [t for x, y, t in plain
                if abs(y - gy) <= row and gx - row <= x <= gx + span]
        value = next((t for t in near if _FCF_VALUE_RE.match(t)), None)
        datums = [t for t in near if _FCF_DATUM_RE.match(t)]
        if not value and not datums:
            continue
        used.add((gx, gy))
        frames.append({"tolerance": value, "datums": datums,
                       "text": " ".join([gtext] + near)})
    return frames


def facts_from_dxf(path: str, source_name: str | None = None) -> dict[str, Any]:
    doc = readfile(path)
    msp = doc.modelspace()
    layouts = [msp] + [doc.layouts.get(n) for n in doc.layout_names()
                       if n.lower() != "model"]
    K, unit_why = detect_mm_per_unit(doc, msp)
    dims, circles, dim_centers, titles, texts = [], [], [], {}, []
    surfaces, geo_tols, rects, centerlines, symbol_zones = [], [], [], 0, []
    short_lines, long_lines = [], []
    gdt_styles = _gdt_styles(doc)
    gdt_glyphs, plain_texts = [], []

    for lay in layouts:
        try:
            flat = list(_walk(lay))
        except Exception:
            continue
        for e in flat:
            t = e.dxftype()
            if _is_centerline(e):
                centerlines += 1
            if _is_border(e):
                rects.append(e)
            if t == "LINE":
                try:
                    s, o = e.dxf.start, e.dxf.end
                    span = math.hypot(o.x - s.x, o.y - s.y) * K
                    if span <= MAX_SYMBOL_LEG_MM:
                        short_lines.append((s.x, s.y, o.x, o.y))
                    elif span >= BORDER_MIN_EDGE_MM:
                        long_lines.append((s.x, s.y, o.x, o.y))
                except Exception:
                    pass
            if t == "TOLERANCE":
                g = _geometric_tol(e.dxf.get("content", "") or "")
                if g:
                    geo_tols.append(g)
                continue
            if t == "DIMENSION":
                try:
                    meas = e.get_measurement()
                except Exception:
                    continue
                if not isinstance(meas, (int, float)):
                    continue
                tol, up, lo = _dim_tolerance(e)
                dtype = e.dimtype & 7
                if dtype in (DIM_ANGULAR, 5):
                    continue
                try:
                    org = e.dxf.text_midpoint
                    x, y = org.x, org.y
                except Exception:
                    x = y = None
                label = (e.dxf.get("text", "") or "").strip()
                if label in ("<>", ""):
                    label = ""
                dims.append({"value_mm": float(meas) * K, "tol_type": tol,
                             "upper_mm": up * K if up is not None else None,
                             "lower_mm": lo * K if lo is not None else None,
                             "text": label,
                             "x_cm": x * K / 10 if x is not None else None,
                             "y_cm": y * K / 10 if y is not None else None})
                c = _dim_center(e)
                if c:
                    dim_centers.append(c)
            elif t in ("CIRCLE", "ARC"):
                try:
                    c = e.dxf.center
                    circles.append({"x": c.x, "y": c.y, "r": float(e.dxf.radius),
                                    "layer": e.dxf.layer})
                except Exception:
                    continue
            elif t in ("TEXT", "MTEXT"):
                try:
                    value = e.plain_text() if t == "MTEXT" else e.dxf.text
                    if not value or not value.strip():
                        continue
                    value = value.strip()
                    if len(value) <= 12:
                        try:
                            ins = e.dxf.insert
                            spot = (ins.x, ins.y)
                        except Exception:
                            spot = None
                        if spot and e.dxf.get("style", "") in gdt_styles:
                            gdt_glyphs.append((spot[0], spot[1], value))
                            symbol_zones.append(_zone(e, t))
                            continue
                        if spot:
                            plain_texts.append((spot[0], spot[1], value))
                    raw = e.text if t == "MTEXT" else value
                    g = _geometric_tol(raw)
                    if g:
                        geo_tols.append(g)
                        symbol_zones.append(_zone(e, t))
                        continue
                    s = _surface_symbol(value)
                    if s:
                        surfaces.append(s)
                        symbol_zones.append(_zone(e, t))
                        continue
                    if _PROJECTION_RE.search(value):
                        symbol_zones.append(_fixed_zone(e, PROJECTION_ZONE_MM, K))
                    texts.append(value)
                    if _is_note(value):
                        symbol_zones.append(_zone(e, t, value.count("\n") + 1))
                except Exception:
                    continue
        for ins in lay.query("INSERT"):
            try:
                attrs = {a.dxf.tag.upper(): (a.dxf.text or "").strip()
                         for a in ins.attribs}
            except Exception:
                continue
            if attrs:
                titles.setdefault(ins.dxf.name, {}).update(attrs)

    geo_tols += _gdt_frames(gdt_glyphs, plain_texts, K)

    grid_cell = max(10.0 / K, 1e-9)
    line_grid = _short_line_grid(short_lines, grid_cell)
    dimmed_dia = {round(abs(d["value_mm"]), 2) for d in dims}
    tol_units = CENTER_TOL / K if K else CENTER_TOL
    groups = {}
    for c in circles:
        if c["layer"] == ERR_LAYER:
            continue
        if any(abs(c["x"] - dx) <= tol_units and abs(c["y"] - dy) <= tol_units
               for dx, dy in dim_centers):
            continue
        if c["r"] * 2 * K < MIN_HOLE_DIA_MM:
            continue
        if _in_symbol_zone(c["x"], c["y"], symbol_zones):
            continue
        if _is_inscribed(c["x"], c["y"], c["r"], line_grid, grid_cell):
            continue
        dia = round(c["r"] * 2 * K, 2)
        if dia in dimmed_dia or round(c["r"] * K, 2) in dimmed_dia:
            continue
        g = groups.get(dia)
        if g:
            g["count"] += 1
        else:
            groups[dia] = {"id": None, "diameter_mm": c["r"] * 2 * K, "count": 1,
                           "x_cm": c["x"] * K / 10, "y_cm": c["y"] * K / 10,
                           "dxf_x": c["x"], "dxf_y": c["y"], "dxf_r": c["r"]}
    undimensioned = sorted(groups.values(), key=lambda c: -c["diameter_mm"])

    props = _props_from_titles(titles)
    view_names = []
    views = []
    border = None
    border_box = None
    for ins in msp.query("INSERT"):
        name = ins.dxf.name
        if _VIEW_BLOCK_RE.search(name):
            view_names.append(name)
            views.append({"name": name, "scale": None, **_view_box(ins, K)})
        elif border is None and _ANON_BLOCK_RE.match(name):
            border = name
    if border is None and rects:
        # 부품 외형도 닫힌 사각형이다. 그려진 것 전체를 거의 다 감싸야 윤곽선으로 본다.
        # 이 조건이 없으면 뷰 하나짜리 사각형도 도면양식으로 세어 표제란 누락을 놓친다.
        span_x, span_y = _drawn_span(rects, circles)
        wide = [r for r in rects
                for z in [_rect_size(r)]
                if z and z[0] >= span_x * BORDER_MIN_SPAN
                and z[1] >= span_y * BORDER_MIN_SPAN]
        if wide:
            border = "윤곽선"
            border_box = _rect_box(wide[0], K)
    if border_box is None:
        border_box = _line_border(long_lines, K)
        if border is None and border_box:
            border = "윤곽선(선 4개)"

    title_block = (list(titles) or [None])[0]
    if not title_block:
        hits = sum(1 for t in texts if _TITLE_TEXT_RE.search(t))
        if hits >= MIN_TITLE_TEXT_HITS:
            title_block = "표제란(문자)"

    if not views:
        views = _cluster_views(msp, K)
    _mark_front_view(msp, views, K)
    layout = analyze_layout(views)

    fields = _title_fields(plain_texts, K)
    # 도면틀도 표제란도 없으면 그려진 것의 범위가 곧 도면 크기라고 볼 수 없다.
    # 그럴 때는 크기를 재지 않는다 — 모르는 것을 재면 없는 오작을 만든다.
    if border or title_block:
        sheet_name, sheet_w, sheet_h = _sheet_size(doc, rects, K)
    else:
        sheet_name, sheet_w, sheet_h = None, None, None

    spec = _spec_tables(texts + [t for _, _, t in plain_texts])
    sheet = {"name": "Model", "title_block": title_block,
             "border": border,
             "fields": fields,
             "sheet_name": sheet_name,
             "width_cm": sheet_w / 10 if sheet_w else None,
             "height_cm": sheet_h / 10 if sheet_h else None,
             "is_isometric": any(_ISO_3D_RE.search(t) for t in texts),
             "view_scales": _view_scales(texts),
             "views": views,
             "layout": layout,
             "border_box_mm": border_box,
             "outside_frame": _outside_frame(msp, border_box, K),
             **spec,
             "line_widths": _line_widths(doc),
             "text_sizes": _text_sizes(doc, msp, K),
             "views_known": bool(view_names),
             "dims": dims, "undimensioned": undimensioned,
             "surface_symbols": surfaces, "geometric_tols": geo_tols,
             "counts": {"circles": len(circles), "title_blocks": len(titles),
                        "SurfaceTextureSymbols": len(surfaces),
                        "FeatureControlFrames": len(geo_tols),
                        "Centerlines": centerlines, "Centermarks": 0}}
    return {
        "kind": "dwg", "file": source_name or os.path.basename(path),
        "props": props, "sheets": [sheet],
        "first_angle": _first_angle(texts, fields), "dxf": path,
        "notes_text": _drop_spec_rows([t for t in texts if _is_note(t)],
                                     bool(spec["spec_tables"])),
        "title_attributes": titles,
        "unit_mm_per_drawing_unit": K, "unit_source": unit_why,
    }


_TITLE_KEYS = {
    "part_number": ("PART_NUMBER", "PARTNUMBER", "PART NO", "PARTNO", "부품_번호", "품번"),
    "material": ("MATERIAL", "MAT", "재질"),
    "designer": ("DESIGNER", "DRAWN", "DRAWN_BY", "AUTHOR", "작성자", "설계자"),
    "revision": ("REVISION", "REV", "REV_NO", "리비전_번호"),
    "description": ("DESCRIPTION", "TITLE", "제목"),
}


_STD_SHEETS = (("A0", 1189.0, 841.0), ("A1", 841.0, 594.0), ("A2", 594.0, 420.0),
               ("A3", 420.0, 297.0), ("A4", 297.0, 210.0))
SHEET_MATCH_TOL_MM = 3.0
MIN_SHEET_MM = 100.0
FIELD_ROW_MM = 4.0             # 같은 칸으로 볼 수 있는 위아래 차이
FIELD_RIGHT_MM = 60.0          # 라벨 오른쪽 이 안에 값이 있으면 그 라벨의 값이다
FIELD_BELOW_MM = 14.0

_FIELD_LABEL_RE = re.compile(
    r"^(척\s*도|각\s*법|투\s*상\s*법|재\s*질|재\s*료|질\s*량|중\s*량|품\s*명|도\s*명|"
    r"품\s*번|수\s*량|비\s*고|과\s*제\s*명|SCALE|MATERIAL|MASS|WEIGHT)$", re.I)
_FIELD_INLINE_RE = re.compile(
    r"^(척\s*도|각\s*법|투\s*상\s*법|재\s*질|재\s*료|질\s*량|중\s*량|"
    r"SCALE|MATERIAL|MASS|WEIGHT)\s*[:：]?\s*(\S.*)$", re.I)
_FIELD_KEY = {"척도": "scale", "scale": "scale", "각법": "projection",
              "투상법": "projection", "재질": "material", "재료": "material",
              "material": "material", "질량": "mass", "중량": "mass",
              "mass": "mass", "weight": "mass"}
_SCALE_VALUE_RE = re.compile(r"^(\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?|NS)$", re.I)
# 앞에 숫자·콜론·점이 붙은 1은 각법 표기가 아니다 (`1:1 각법`의 그 1).
_FIRST_ANGLE_RE = re.compile(r"(?<![\d:.\-])(?:제\s*)?1\s*각\s*법|first\s*angle", re.I)
_THIRD_ANGLE_RE = re.compile(r"(?<![\d:.\-])(?:제\s*)?3\s*각\s*법|third\s*angle", re.I)
_MASS_VALUE_RE = re.compile(r"^\d+(?:\.\d+)?\s*(?:g|kg|그램)?$", re.I)
# KS 재료 기호. SM45C · GC250 · SCM415 · SS400 · SUS304 · FC250 · PBC2 …
# 한글로 적는 사람도 있어 흔한 재료 이름은 값으로 인정한다(기호로 쓰라는 지적은
# 채점 기준이 할 일이고, 우리는 "칸이 비었다"만 말한다).
_MATERIAL_VALUE_RE = re.compile(
    r"^[A-Z][A-Z0-9\-]{1,11}$|^(주철|주강|황동|청동|연강|탄소강|합금강|"
    r"스테인리스|알루미늄|알루미늄합금|동|강)$")
_ISO_3D_RE = re.compile(r"등\s*각|렌더링|ISOMETRIC", re.I)
# `E-E ( 1 : 1 )`, `단면도 A-A (2:1)` 처럼 뷰 이름표 뒤에 붙는 척도.
_VIEW_SCALE_RE = re.compile(r"\(\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*\)")


def _view_scales(texts):
    """뷰 이름표에 적힌 척도들. `단면도 A-A (2:1)` → `2:1`."""
    out = []
    for text in texts:
        m = _VIEW_SCALE_RE.search(text)
        if m and len(text) <= 40:
            out.append({"label": text.strip(),
                        "scale": f"{float(m.group(1)):g}:{float(m.group(2)):g}"})
    return out


def _norm_label(text):
    return re.sub(r"\s+", "", text).lower()


def _title_fields(plain, K):
    """표제란의 '라벨 - 값' 짝을 읽는다.

    한 문자에 `척도 1:1`로 붙어 있는 도면도 있고, 칸이 나뉘어 `척도`와 `1:1`이
    따로 놓인 도면도 있다(Inventor로 뽑은 실기 도면은 대개 따로다). 둘 다 본다."""
    fields, labels = {}, []
    for x, y, raw in plain:
        text = raw.strip()
        inline = _FIELD_INLINE_RE.match(text)
        if inline:
            key = _FIELD_KEY.get(_norm_label(inline.group(1)))
            if key:
                fields.setdefault(key, inline.group(2).strip())
            continue
        if _FIELD_LABEL_RE.match(text):
            key = _FIELD_KEY.get(_norm_label(text))
            if key:
                labels.append((x, y, key))

    values = [(x, y, t.strip()) for x, y, t in plain
              if t.strip() and not _FIELD_LABEL_RE.match(t.strip())]
    for lx, ly, key in labels:
        if key in fields:
            continue
        best = None
        for vx, vy, val in values:
            dx, dy = (vx - lx) * K, (vy - ly) * K
            if abs(dy) <= FIELD_ROW_MM and 0 < dx <= FIELD_RIGHT_MM:
                dist = dx
            elif abs(dx) <= FIELD_RIGHT_MM / 3 and -FIELD_BELOW_MM <= dy < 0:
                dist = FIELD_RIGHT_MM + abs(dy)
            else:
                continue
            if best is None or dist < best[0]:
                best = (dist, val)
        if best:
            fields[key] = best[1]

    # 값이 그 칸의 값처럼 안 생겼으면 버린다. 옆 칸 글자를 값으로 읽는 것보다
    # 모른다고 두는 편이 낫다.
    if fields.get("scale") and not _SCALE_VALUE_RE.match(fields["scale"]):
        fields.pop("scale")
    if fields.get("mass") and not _MASS_VALUE_RE.match(fields["mass"]):
        fields.pop("mass")
    if fields.get("material") and not _MATERIAL_VALUE_RE.match(fields["material"]):
        # 빈 재질 칸은 아래 칸 글자를 물어 온다. `1:1`을 재료로 읽느니 비워 둔다.
        fields.pop("material")
    return fields


def _first_angle(texts, fields):
    """제1각법이면 True, 제3각법이면 False, 표기를 못 찾으면 None.

    문자를 하나씩 본다. 이어 붙여서 보면 표제란의 `척도` `1:1` `각법`이 한 줄이
    되어 `1 각법`으로 읽히고, 제3각법 도면이 제1각법 오작으로 찍힌다."""
    mark = re.sub(r"\s+", "", fields.get("projection", ""))
    if mark in ("1", "3"):            # 칸에 숫자만 적는 도면틀이 있다
        return mark == "1"
    found = set()
    for text in (mark, *texts):
        if not text:
            continue
        if _THIRD_ANGLE_RE.search(text):
            found.add(3)
        if _FIRST_ANGLE_RE.search(text):
            found.add(1)
    if not found:
        return None
    # 둘 다 보이면 제3각법 표기를 믿는다. 오작을 잘못 붙이는 쪽이 더 위험하다.
    return 3 not in found


def _sheet_size(doc, rects, K):
    """도면 영역 (이름, 폭mm, 높이mm). 표준 크기에 안 맞으면 이름이 None."""
    cands = []
    for rect in rects:
        size = _rect_size(rect)
        if size and size[0] * K >= MIN_SHEET_MM and size[1] * K >= MIN_SHEET_MM:
            cands.append((size[0] * K, size[1] * K))
    # 윤곽선을 찾았으면 그게 도면 크기다. 헤더의 도면 한계·범위는 CAD가 넣어 둔
    # 기본값일 수 있어서(새 도면이면 A3), 윤곽선이 없을 때만 본다.
    if not cands:
        for lo, hi in (("$LIMMIN", "$LIMMAX"), ("$EXTMIN", "$EXTMAX")):
            try:
                a, b = doc.header.get(lo), doc.header.get(hi)
                w, h = (b[0] - a[0]) * K, (b[1] - a[1]) * K
            except Exception:
                continue
            if w >= MIN_SHEET_MM and h >= MIN_SHEET_MM:
                cands.append((w, h))
    cands.sort(key=lambda wh: -wh[0] * wh[1])
    for w, h in cands:
        for name, sw, sh in _STD_SHEETS:
            fit = ((abs(w - sw) <= SHEET_MATCH_TOL_MM
                    and abs(h - sh) <= SHEET_MATCH_TOL_MM)
                   or (abs(w - sh) <= SHEET_MATCH_TOL_MM
                       and abs(h - sw) <= SHEET_MATCH_TOL_MM))
            if fit:
                return name, w, h
    return (None, cands[0][0], cands[0][1]) if cands else (None, None, None)


def _props_from_titles(titles):
    flat = {}
    for attrs in titles.values():
        flat.update(attrs)
    out = {}
    for key, names in _TITLE_KEYS.items():
        val = ""
        for n in names:
            if flat.get(n.upper()):
                val = flat[n.upper()]
                break
        out[key] = val
    out["_has_title_block"] = bool(flat)
    return out


MIN_DRAWABLE = 5


def _drawable_count(space, cap=MIN_DRAWABLE):
    n = 0
    try:
        for e in space:
            if e.dxftype() in REAL_ENTITIES:
                n += 1
                if n >= cap:
                    break
    except Exception:
        return 0
    return n


def drawable_space(doc):
    msp = doc.modelspace()
    if _drawable_count(msp) >= MIN_DRAWABLE:
        return msp, True
    for name in doc.layout_names_in_taborder():
        if name.lower() == "model":
            continue
        try:
            lay = doc.layouts.get(name)
        except Exception:
            continue
        if _drawable_count(lay) >= MIN_DRAWABLE:
            print(f"[dwg] 모델 공간이 비어 배치 '{name}' 을 미리보기로 씁니다",
                  flush=True)
            return lay, False
    return msp, True


def render_svg(dxf_path, markers=()):
    doc = readfile(dxf_path)
    space, is_model = drawable_space(doc)
    if ERR_LAYER not in doc.layers:
        doc.layers.add(ERR_LAYER, color=1)

    placed = 0
    if is_model:
        bb0 = bbox.extents(space)
        span = max(bb0.size.x, bb0.size.y) if bb0.has_data else 100.0
        usable = [(i, m) for i, m in enumerate(markers, 1)
                  if m.get("dxf_x") is not None and m.get("dxf_y") is not None]
        if usable:
            rings = [min(max((m.get("dxf_r") or 0.0) * 1.12, span * 0.006),
                         span * 0.018) for _, m in usable]
            spots = _badge_positions(
                bb0, span, [(m["dxf_x"], m["dxf_y"]) for _, m in usable], rings)
            for (i, m), ring, (bx, by) in zip(usable, rings, spots):
                _arrow(space, m["dxf_x"], m["dxf_y"], ring, span, str(i), bx, by)
                placed += 1
    svg, tf = _finish(doc, space)
    return svg, tf, placed


BADGE_ANGLES = (45, 0, 90, -45, 135, -90, 180, 20, 70, 110, 160, 200, 250, 290, 340)
# Badge radius as a fraction of the drawing's longer side. Big enough to read the
# number, small enough not to bury the feature it points at.
BADGE_R = 0.011


def _badge_positions(bb, span, targets, rings):
    """Put each numbered badge next to the circle it points at, inside the drawing.

    Badges may sit on top of drawing content -- they are drawn as a filled disc
    so they stay readable -- but never on top of each other. Candidates are
    tried nearest-first around the target, and one that fits within the
    drawing's own extents wins over a closer one that would hang off the edge:
    anything outside enlarges the preview canvas and reintroduces the empty
    margin this placement exists to remove.
    """
    badge_r = span * BADGE_R
    clear = badge_r * 2.15
    fits = _fits_inside(bb, badge_r)
    placed = []
    for (x, y), ring in zip(targets, rings):
        gap = ring + badge_r * 1.9
        candidates = [
            (x + radius * math.cos(a), y + radius * math.sin(a))
            for radius in (gap + badge_r * 2.0 * step for step in range(8))
            for a in (math.radians(angle) for angle in BADGE_ANGLES)]

        def room(spot):
            return min((math.hypot(spot[0] - px, spot[1] - py)
                        for px, py in placed), default=math.inf)

        free = [c for c in candidates if room(c) >= clear]
        inside = [c for c in free if fits(c)]
        # nearest free spot inside the drawing; failing that the nearest free one
        # at all; and if everything is taken, whichever leaves the most room
        placed.append(next(iter(inside or free), None) or max(candidates, key=room))
    return placed


def _fits_inside(bb, badge_r):
    if not getattr(bb, "has_data", False):
        return lambda spot: True
    x0, y0 = bb.extmin.x + badge_r, bb.extmin.y + badge_r
    x1, y1 = bb.extmax.x - badge_r, bb.extmax.y - badge_r
    return lambda spot: x0 <= spot[0] <= x1 and y0 <= spot[1] <= y1


def _arrow(msp, x, y, ring, span, label, label_x, label_y):
    a = {"layer": ERR_LAYER, "lineweight": 100}
    msp.add_circle((x, y), ring, dxfattribs=a)

    badge_r = span * BADGE_R
    dx, dy = label_x - x, label_y - y
    length = math.hypot(dx, dy)
    if length > ring + badge_r:
        ux, uy = dx / length, dy / length
        msp.add_line((x + ring * ux, y + ring * uy),
                     (label_x - badge_r * ux, label_y - badge_r * uy),
                     dxfattribs=a)

    # filled disc so the number stays readable over drawing content
    disc = msp.add_hatch(color=1, dxfattribs={"layer": ERR_LAYER})
    disc.paths.add_polyline_path(
        [(label_x + badge_r * math.cos(t), label_y + badge_r * math.sin(t))
         for t in (i * math.tau / 24 for i in range(24))], is_closed=True)
    msp.add_circle((label_x, label_y), badge_r, dxfattribs=a)

    text_h = badge_r * (1.15 if len(label) > 1 else 1.35)
    text_style = {**a, "color": 7}
    msp.add_text(label, height=text_h, dxfattribs=text_style).set_placement(
        (label_x, label_y), align=TextEntityAlignment.MIDDLE_CENTER)


def _finish(doc, msp):
    bb = bbox.extents(msp)
    margin = _drawing_margin(bb)
    _prepare_preview_colors(doc)
    back = dsvg.SVGBackend()
    config = Configuration(lineweight_policy=LineweightPolicy.RELATIVE)
    Frontend(RenderContext(doc), back, config=config).draw_layout(
        msp, filter_func=lambda entity: entity.dxftype() != "POINT")
    s = back.get_string(dlayout.Page(0, 0, dlayout.Units.mm,
                                    dlayout.Margins.all(margin)))
    return s, _transform(s, bb, margin)


def _drawing_margin(bb):
    if not bb.has_data:
        return MARGIN_MM
    span = max(bb.size.x, bb.size.y)
    return min(MARGIN_MM, max(span * 0.05, 1e-6))


def _prepare_preview_colors(doc):
    for layer in doc.layers:
        if layer.dxf.name == ERR_LAYER:
            continue
        layer.dxf.color = 7
        layer.dxf.discard("true_color")
    for entity in doc.entitydb.values():
        try:
            if entity.dxf.get("layer", "0") == ERR_LAYER:
                continue
            if entity.dxf.hasattr("color"):
                entity.dxf.color = 7
            entity.dxf.discard("true_color")
        except (AttributeError, TypeError):
            continue


def _transform(svg_text, bb, margin=MARGIN_MM):
    try:
        vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg_text).group(1).split()]
        w_mm = float(re.search(r'width="([\d.]+)mm"', svg_text).group(1))
        upm = vb[2] / w_mm
        return {"scale": upm, "off_x": (-bb.extmin.x + margin) * upm,
                "off_y": (bb.extmax.y + margin) * upm,
                "view_w": vb[2], "view_h": vb[3]}
    except Exception:
        return None


def analyze(path: str) -> dict[str, Any]:
    """Read one DXF or DWG and return the facts dict the grader consumes.
    A DWG is converted to DXF first."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dwg":
        dxf = dwg_to_dxf(path)
        return facts_from_dxf(dxf, source_name=os.path.basename(path))
    return facts_from_dxf(path)


if __name__ == "__main__":
    import json
    import sys
    f = analyze(sys.argv[1])
    print(json.dumps(f, ensure_ascii=False, indent=2, default=str))
