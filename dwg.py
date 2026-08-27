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
MIN_NOTE_LEN = 12


def _is_note(text):
    t = (text or "").strip()
    return bool(t) and ("\n" in t or len(t) >= MIN_NOTE_LEN
                        or _NOTE_KEYWORD_RE.search(t))


def _is_border(entity):
    try:
        if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
            return False
        pts = entity.get_points("xy")
    except Exception:
        return False
    if len(pts) != 4:
        return False
    xs = {round(p[0], 3) for p in pts}
    ys = {round(p[1], 3) for p in pts}
    return len(xs) == 2 and len(ys) == 2


def _surface_symbol(text):
    t = (text or "").strip()
    if not t or len(t) > 40:
        return None
    if _is_note(t):
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


def facts_from_dxf(path: str, source_name: str | None = None) -> dict[str, Any]:
    doc = readfile(path)
    msp = doc.modelspace()
    layouts = [msp] + [doc.layouts.get(n) for n in doc.layout_names()
                       if n.lower() != "model"]
    K, unit_why = detect_mm_per_unit(doc, msp)
    dims, circles, dim_centers, titles, texts = [], [], [], {}, []
    surfaces, geo_tols, rects, centerlines, symbol_zones = [], [], [], 0, []
    short_lines = []

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
                    if math.hypot(o.x - s.x, o.y - s.y) * K <= MAX_SYMBOL_LEG_MM:
                        short_lines.append((s.x, s.y, o.x, o.y))
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
    border = None
    for ins in msp.query("INSERT"):
        name = ins.dxf.name
        if _VIEW_BLOCK_RE.search(name):
            view_names.append(name)
        elif border is None and _ANON_BLOCK_RE.match(name):
            border = name
    if border is None and rects:
        border = "윤곽선"

    title_block = (list(titles) or [None])[0]
    if not title_block:
        hits = sum(1 for t in texts if _TITLE_TEXT_RE.search(t))
        if hits >= MIN_TITLE_TEXT_HITS:
            title_block = "표제란(문자)"

    sheet = {"name": "Model", "title_block": title_block,
             "border": border,
             "views": [{"name": name, "scale": None} for name in view_names],
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
        "first_angle": None, "dxf": path,
        "notes_text": [t for t in texts if _is_note(t)],
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
