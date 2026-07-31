import glob
import math
import os
import re
import shutil
import subprocess
import tempfile
import traceback

import ezdxf
from ezdxf import bbox
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
    return dxf_has_content(out_dxf)


REAL_ENTITIES = {"LINE", "CIRCLE", "ARC", "DIMENSION", "POLYLINE", "LWPOLYLINE",
                 "SPLINE", "ELLIPSE", "TEXT", "MTEXT", "INSERT", "HATCH", "LEADER"}


def dxf_has_content(path):
    try:
        d = ezdxf.readfile(path)
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


def dwg_via_inventor(dwg_path, out_dxf):
    import inventor as inv
    if not inv.is_available():
        return False
    import win32com.client as w32
    with inv._LOCK:
        inv._com_init()
        app = inv._get_app()
        doc = w32.CastTo(app.Documents.Open(os.path.abspath(dwg_path), False),
                         "DrawingDocument")
        try:
            doc.SaveAs(out_dxf, True)
        finally:
            try:
                doc.Close(True)
            except Exception:
                pass
    return os.path.exists(out_dxf) and dxf_has_content(out_dxf)


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
    import inventor
    if find_libredwg():
        return "LibreDWG"
    if inventor.is_available():
        return "Autodesk Inventor"
    if find_oda():
        return "ODA File Converter"
    if find_cloudconvert():
        return "CloudConvert (외부 API)"
    return None


def has_dwg_support():
    return dwg_converter_name() is not None


SHORT_NAME = {"dwg_via_libredwg": "LibreDWG",
              "dwg_via_inventor": "Inventor",
              "dwg_via_cloudconvert": "CloudConvert"}


def dwg_to_dxf(dwg_path):
    work = tempfile.mkdtemp(prefix="dwg_conv_")
    tried = []
    for fn in (dwg_via_libredwg, dwg_via_inventor, dwg_via_cloudconvert):
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
    with open(dwg_path, "rb") as a, open(os.path.join(src, base), "wb") as b:
        b.write(a.read())
    subprocess.run([exe, src, dst, "ACAD2018", "DXF", "0", "1", "*.DWG"],
                   check=False, timeout=300,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = glob.glob(os.path.join(dst, "*.dxf")) + glob.glob(os.path.join(dst, "*.DXF"))
    if not out:
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


def facts_from_dxf(path, source_name=None):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    layouts = [msp] + [doc.layouts.get(n) for n in doc.layout_names()
                       if n.lower() != "model"]
    K, unit_why = detect_mm_per_unit(doc, msp)
    dims, circles, dim_centers, titles = [], [], [], {}

    for lay in layouts:
        try:
            flat = list(_walk(lay))
        except Exception:
            continue
        for e in flat:
            t = e.dxftype()
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
        for ins in lay.query("INSERT"):
            try:
                attrs = {a.dxf.tag.upper(): (a.dxf.text or "").strip()
                         for a in ins.attribs}
            except Exception:
                continue
            if attrs:
                titles.setdefault(ins.dxf.name, {}).update(attrs)

    dimmed_dia = {round(abs(d["value_mm"]), 2) for d in dims}
    tol_units = CENTER_TOL / K if K else CENTER_TOL
    groups = {}
    for c in circles:
        if c["layer"] == ERR_LAYER:
            continue
        if any(abs(c["x"] - dx) <= tol_units and abs(c["y"] - dy) <= tol_units
               for dx, dy in dim_centers):
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
    sheet = {"name": "Model", "title_block": (list(titles) or [None])[0],
             "views": [], "dims": dims, "undimensioned": undimensioned,
             "counts": {"circles": len(circles), "title_blocks": len(titles)}}
    return {
        "kind": "dwg", "file": source_name or os.path.basename(path),
        "props": props, "sheets": [sheet], "sketches": [], "holes": [],
        "walls": [], "interferences": [], "sick_features": [],
        "first_angle": None, "dxf": path,
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
    doc = ezdxf.readfile(dxf_path)
    space, is_model = drawable_space(doc)
    if ERR_LAYER not in doc.layers:
        doc.layers.add(ERR_LAYER, color=1)

    placed = 0
    if is_model:
        bb0 = bbox.extents(space)
        span = max(bb0.size.x, bb0.size.y) if bb0.has_data else 100.0
        for i, m in enumerate(markers, 1):
            x, y = m.get("dxf_x"), m.get("dxf_y")
            if x is None or y is None:
                continue
            r = m.get("dxf_r") or span * 0.01
            _arrow(space, x, y, max(r * 1.6, span * 0.010), span, str(i))
            placed += 1
    svg, tf = _finish(doc, space)
    return svg, tf, placed


def _arrow(msp, x, y, ring, span, label):
    a = {"layer": ERR_LAYER}
    msp.add_circle((x, y), ring, dxfattribs=a)

    lead = max(ring * 3.2, span * 0.045)
    d = 0.7071
    tipx, tipy = x + ring * d, y + ring * d
    tailx, taily = x + lead * d, y + lead * d
    msp.add_line((tipx, tipy), (tailx, taily), dxfattribs=a)
    msp.add_line((tailx, taily), (tailx + lead * 0.55, taily), dxfattribs=a)

    head = ring * 0.55
    for ang in (0.4, -0.4):
        ca, sa = math.cos(ang), math.sin(ang)
        dx, dy = d * ca - d * sa, d * sa + d * ca
        msp.add_line((tipx, tipy), (tipx + head * dx, tipy + head * dy), dxfattribs=a)

    msp.add_text(label, height=max(ring * 1.1, span * 0.011), dxfattribs=a
                 ).set_placement((tailx + lead * 0.62, taily + ring * 0.25))


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


def analyze(path):
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
