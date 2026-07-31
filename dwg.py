"""Everything DXF/DWG: parsing to `facts`, and SVG rendering for the viewer.

DWG notes (probe8/9 established these the hard way):
  * Inventor CAN open a .dwg but exposes it as a bare "Model (AutoCAD)" sheet
    with zero DrawingViews/DrawingDimensions, and SaveAs(.dxf) from it writes
    no file. So Inventor is NOT a usable DWG->DXF converter.
  * Therefore .dwg needs ODA File Converter (free). .dxf needs nothing.
  * Inventor's own DXF export turns circles into splines, so a .idw's exported
    DXF is fine to LOOK at but useless to measure -- circle checks for .idw
    come from the COM API, not from here.
"""
import glob
import math
import os
import re
import shutil
import subprocess
import tempfile

import ezdxf
from ezdxf import bbox
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing import layout as dlayout
from ezdxf.addons.drawing import svg as dsvg

MARGIN_MM = 5.0
CENTER_TOL = 0.5      # mm, for matching a diameter/radius dim to its circle
ERR_LAYER = "_CHECKER_ERRORS"

DIM_LINEAR, DIM_ALIGNED, DIM_ANGULAR, DIM_DIAMETER, DIM_RADIUS = 0, 1, 2, 3, 4


# --- DWG -> DXF -------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
LIBREDWG = os.path.join(HERE, "vendor", "libredwg", "dwg2dxf.exe")


def find_libredwg():
    """GNU LibreDWG's dwg2dxf, beside the repo or on PATH.

    This is the converter that actually works on third-party AutoCAD files:
    free, offline, no install and no account, unlike ODA File Converter, and
    unlike Inventor it reads DWGs it did not write.

    The vendored copy is Windows-only and GPL-3.0, so it stays out of the repo
    (see NOTICE.md). On Linux `apt install libredwg-tools` puts dwg2dxf on PATH,
    which is what lets the cloud demo accept DWG at all.
    """
    if os.path.exists(LIBREDWG):
        return LIBREDWG
    return shutil.which("dwg2dxf")


def find_oda():
    """Path to ODAFileConverter.exe, or None."""
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
    """Does this DXF actually contain drawing geometry?

    Inventor happily 'converts' a third-party AutoCAD DWG into a 455 KB DXF
    holding nothing but arrowhead block definitions, so file size proves
    nothing -- the layouts have to be checked.
    """
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
    """Convert with Inventor, which is already installed and free.

    Only works for DWGs Inventor itself wrote (a common case -- exporting a
    .idw to .dwg). For an AutoCAD-authored file Inventor opens an empty shell,
    which is why the result is content-checked rather than trusted.
    """
    import win32com.client as w32
    import inventor as inv
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


def dwg_to_dxf(dwg_path):
    """DWG -> DXF, trying converters in order of how much they can read.

    LibreDWG first: it handles AutoCAD-authored files, which is most of them.
    Inventor second: only understands DWGs it wrote itself. ODA last, if the
    user happens to have installed it.
    """
    work = tempfile.mkdtemp(prefix="dwg_conv_")
    for fn in (dwg_via_libredwg, dwg_via_inventor):
        out = os.path.join(work, f"{fn.__name__}.dxf")
        try:
            if fn(dwg_path, out):
                return out
        except Exception:
            continue

    exe = find_oda()
    if not exe:
        raise RuntimeError(
            "이 DWG를 읽지 못했습니다. 파일이 손상되었거나 지원하지 않는 버전일 수 "
            "있습니다. AutoCAD에서 DXF로 저장한 뒤 올리면 대부분 해결됩니다."
        )
    src = tempfile.mkdtemp(prefix="oda_in_")
    dst = tempfile.mkdtemp(prefix="oda_out_")
    base = os.path.basename(dwg_path)
    with open(dwg_path, "rb") as a, open(os.path.join(src, base), "wb") as b:
        b.write(a.read())
    # ODAFileConverter <in> <out> <ver> <type> <recurse> <audit> [filter]
    subprocess.run([exe, src, dst, "ACAD2018", "DXF", "0", "1", "*.DWG"],
                   check=False, timeout=300,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = glob.glob(os.path.join(dst, "*.dxf")) + glob.glob(os.path.join(dst, "*.DXF"))
    if not out:
        raise RuntimeError("ODA File Converter가 DXF를 생성하지 못했습니다. "
                           "DWG 파일이 손상되었을 수 있습니다.")
    return out[0]


# --- parsing ----------------------------------------------------------------

def _walk(entities, depth=0, seen=frozenset()):
    """Flatten INSERTs so geometry inside blocks is visible.

    Circles very often live inside a block, so a plain modelspace scan reports
    zero of them.
    """
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
    """(tol_type, upper_mm, lower_mm) from a DXF DIMENSION's effective style.

    DXF convention: dimtp is the PLUS magnitude, dimtm the MINUS magnitude, so
    the deviations are +dimtp and -dimtm.
    """
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
    """Circle centre a diameter/radius dimension refers to, else None."""
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


# $INSUNITS code -> millimetres per drawing unit
_UNIT_MM = {1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 2.54e-5,
            9: 0.0254, 10: 914.4, 11: 1e-7, 12: 1e-6, 13: 1e-3, 14: 100.0}
# A mechanical drawing's overall size, in mm. Used to sanity-check the unit.
PLAUSIBLE_MM = (5.0, 20000.0)


def detect_mm_per_unit(doc, msp):
    """How many millimetres is one drawing unit? -> (factor, why)

    $INSUNITS alone is not trustworthy: a real AutoCAD file here declares 0
    (unitless) while actually being metres, and ezdxf's own `setup=True`
    stamps 6 (metres) on a file authored in millimetres. Either one taken at
    face value turns a 27 mm hole into "0.03 mm" or "27 m". So the declared
    unit is only accepted when it yields a drawing of believable size, and
    otherwise the size decides.
    """
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
    # every length below is in drawing units; K converts to millimetres
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
                    continue  # radians, not a length
                try:
                    org = e.dxf.text_midpoint
                    x, y = org.x, org.y
                except Exception:
                    x = y = None
                # "<>" is the DXF placeholder for "print the measured value",
                # not a label -- treat it as no override text at all.
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
        # title block attributes
        for ins in lay.query("INSERT"):
            try:
                attrs = {a.dxf.tag.upper(): (a.dxf.text or "").strip()
                         for a in ins.attribs}
            except Exception:
                continue
            if attrs:
                titles.setdefault(ins.dxf.name, {}).update(attrs)

    # A circle is "dimensioned" if a diameter/radius dim points at its centre,
    # or if some dimension already states that diameter -- "8xO6" is how you
    # dimension eight identical holes, and flagging the other seven is wrong.
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
        # One entry per distinct diameter. A drawing with no dimensions at all
        # otherwise produces a 173-item list nobody can act on.
        # NOTE: dxf_* stay in DRAWING units -- markers are drawn back into the
        # DXF, so they must not be converted.
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
    # only complain about missing props if the file actually has a title block
    out["_has_title_block"] = bool(flat)
    return out


# --- rendering --------------------------------------------------------------

def render_svg(dxf_path, markers=()):
    """SVG of the drawing with error markers drawn INTO the DXF first.

    Baking the markers means ezdxf applies the same transform to markers and
    geometry, so a marker cannot drift off its feature. The returned transform
    is only for pan/zoom on click, where sub-millimetre error is irrelevant.
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    if ERR_LAYER not in doc.layers:
        doc.layers.add(ERR_LAYER, color=1)

    bb0 = bbox.extents(msp)
    span = max(bb0.size.x, bb0.size.y) if bb0.has_data else 100.0
    for i, m in enumerate(markers, 1):
        x, y = m.get("dxf_x"), m.get("dxf_y")
        if x is None or y is None:
            continue
        r = m.get("dxf_r") or span * 0.01
        _arrow(msp, x, y, max(r * 1.6, span * 0.010), span, str(i))
    return _finish(doc, msp)


def _arrow(msp, x, y, ring, span, label):
    """A ring round the feature plus a leader arrow and number pointing at it."""
    a = {"layer": ERR_LAYER}
    msp.add_circle((x, y), ring, dxfattribs=a)

    # leader comes in at 45 degrees from the upper right
    lead = max(ring * 3.2, span * 0.045)
    d = 0.7071
    tipx, tipy = x + ring * d, y + ring * d           # touches the ring, not the centre
    tailx, taily = x + lead * d, y + lead * d
    msp.add_line((tipx, tipy), (tailx, taily), dxfattribs=a)
    msp.add_line((tailx, taily), (tailx + lead * 0.55, taily), dxfattribs=a)

    # arrowhead: two barbs swept back from the tip along the leader
    head = ring * 0.55
    for ang in (0.4, -0.4):
        ca, sa = math.cos(ang), math.sin(ang)
        dx, dy = d * ca - d * sa, d * sa + d * ca     # rotate the leader direction
        msp.add_line((tipx, tipy), (tipx + head * dx, tipy + head * dy), dxfattribs=a)

    msp.add_text(label, height=max(ring * 1.1, span * 0.011), dxfattribs=a
                 ).set_placement((tailx + lead * 0.62, taily + ring * 0.25))


def _finish(doc, msp):
    """Render the (possibly annotated) modelspace to an SVG string."""
    back = dsvg.SVGBackend()
    Frontend(RenderContext(doc), back).draw_layout(msp)
    s = back.get_string(dlayout.Page(0, 0, dlayout.Units.mm,
                                    dlayout.Margins.all(MARGIN_MM)))
    return s, _transform(s, bbox.extents(msp))


def _transform(svg_text, bb):
    """Approximate DXF->SVG mapping, for click-to-zoom only.

    ponytail: derived from the SVG's page size, which ezdxf rounds to 0.1mm, so
    this drifts by ~0.25mm. Fine for centring a viewport; that is why markers
    are baked into the DXF instead of overlaid using this.
    """
    try:
        vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg_text).group(1).split()]
        w_mm = float(re.search(r'width="([\d.]+)mm"', svg_text).group(1))
        upm = vb[2] / w_mm
        return {"scale": upm, "off_x": (-bb.extmin.x + MARGIN_MM) * upm,
                "off_y": (bb.extmax.y + MARGIN_MM) * upm,
                "view_w": vb[2], "view_h": vb[3]}
    except Exception:
        return None


def analyze(path):
    """.dxf directly; .dwg via ODA File Converter."""
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
