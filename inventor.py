"""Inventor COM extraction: a document in, a plain `facts` dict out.

Every COM path here was verified against a real Inventor 2026 install by
probe1-7.py; the notes below record what the probes proved, because several
obvious-looking paths do NOT exist:

  * Documents.Open returns the generic Document interface -- you MUST CastTo
    PartDocument / DrawingDocument / AssemblyDocument to reach
    ComponentDefinition. Same for dimensions (see _intents).
  * Every length off the API is in CENTIMETRES regardless of what
    Parameter.Units says. CM_TO_MM exists for that reason alone.
  * GeneralDimension has no IntentOne. Diameter/Radius expose `.Intent`,
    Linear/Angular expose `.IntentOne/Two/Three`. Cast first.
  * GeneralDimensionType is projected-vs-true, NOT the shape. Use `.Type`.
  * AnalyzeInterference's 2nd arg is a second ObjectCollection, not a bool.
  * kUpToDateHealth is 11778 (not 41217).
  * Sheet collections use US spelling: Centerlines, Centermarks, DrawingNotes.
"""
import os
import threading

import pythoncom
import win32com.client as w32

CM_TO_MM = 10.0
MAX_WALL_GAP_MM = 15.0   # face pairs farther apart than this aren't a wall
ANTIPARALLEL_DOT = -0.99

# ponytail: Inventor is a single-instance COM server, so all analysis is
# serialised through one lock. Fine for a team tool; if throughput ever matters
# the fix is a queue of worker processes each with its own Inventor, not
# finer-grained locking here.
_LOCK = threading.Lock()
_app = None
_com_ready = set()


def _com_init():
    """CoInitialize once per thread and never uninitialize.

    We cache the Inventor Application object across calls, so tearing the COM
    apartment down after each analyze() would leave that pointer dangling --
    Python then fails releasing it at shutdown (exit code 255).
    """
    tid = threading.get_ident()
    if tid not in _com_ready:
        pythoncom.CoInitialize()
        _com_ready.add(tid)


# Inventor shutting down leaves our cached pointer dangling; every later call
# then fails with one of these until the process restarts.
_DEAD_COM = {
    -2147220995,   # CO_E_OBJNOTCONNECTED  개체가 서버에 연결되지 않았습니다
    -2147417848,   # RPC_E_DISCONNECTED
    -2147023174,   # RPC_S_SERVER_UNAVAILABLE
    -2146959355,   # CO_E_SERVER_EXEC_FAILURE
}


def _is_dead_com(exc):
    return isinstance(exc, pythoncom.com_error) and exc.args and exc.args[0] in _DEAD_COM


def is_available():
    """Is Inventor installed on this machine? (registry only -- doesn't launch it)

    Lets the server run usefully on a PC without Inventor: DXF/DWG checking is
    pure Python and needs nothing installed.
    """
    try:
        import winreg
    except ImportError:
        return False
    for root, key in ((winreg.HKEY_CLASSES_ROOT, "Inventor.Application"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Autodesk\Inventor")):
        try:
            winreg.CloseKey(winreg.OpenKey(root, key))
            return True
        except OSError:
            continue
    return False


def _get_app(force_new=False):
    global _app
    if force_new:
        _app = None
    if _app is None:
        _app = w32.Dispatch("Inventor.Application")
        _app.Visible = False
        _app.SilentOperation = True
    else:
        try:
            _app.SoftwareVersion.DisplayName   # cheap liveness probe
        except Exception as e:
            if not _is_dead_com(e):
                raise
            _app = None
            return _get_app()
    return _app


def _c():
    return w32.constants


def _prop(doc, name, default=""):
    try:
        return doc.PropertySets.Item("Design Tracking Properties").Item(name).Value
    except Exception:
        return default


def _props(doc):
    def s(v):
        return v.strip() if isinstance(v, str) else ("" if v is None else str(v))
    return {
        "part_number": s(_prop(doc, "Part Number")),
        "material": s(_prop(doc, "Material")),
        "designer": s(_prop(doc, "Designer")),
        "description": s(_prop(doc, "Description")),
        "revision": s(_prop(doc, "Revision Number")),
        "project": s(_prop(doc, "Project")),
        "stock_number": s(_prop(doc, "Stock Number")),
    }


# --- part -------------------------------------------------------------------

_STATUS = {}


def _status_map():
    if not _STATUS:
        C = _c()
        _STATUS.update({
            C.kFullyConstrainedConstraintStatus: "full",
            C.kUnderConstrainedConstraintStatus: "under",
            C.kOverConstrainedConstraintStatus: "over",
        })
    return _STATUS


def _sketches(cd):
    out = []
    smap = _status_map()
    for sk in cd.Sketches:
        under = 0
        total = 0
        for ent in sk.SketchEntities:
            total += 1
            try:
                if smap.get(ent.ConstraintStatus) == "under":
                    under += 1
            except Exception:
                pass
        try:
            status = smap.get(sk.ConstraintStatus, "unknown")
        except Exception:
            status = "unknown"
        out.append({"name": sk.Name, "status": status,
                    "entities": total, "under_count": under})
    return out


def _holes(cd):
    out = []
    for h in cd.Features.HoleFeatures:
        rec = {"name": h.Name, "diameter_mm": None, "depth_mm": None, "tapped": False}
        try:
            rec["diameter_mm"] = h.HoleDiameter.Value * CM_TO_MM
        except Exception:
            continue  # a hole whose diameter we can't read is not checkable
        for key, get in (("depth_mm", lambda: h.Depth.Value * CM_TO_MM),
                         ("tapped", lambda: bool(h.Tapped))):
            try:
                rec[key] = get()
            except Exception:
                pass
        out.append(rec)
    return out


def _walls(cd):
    """Thin walls = anti-parallel planar face pairs that overlap laterally.

    ponytail: planar faces only, O(n^2) over them, and a rangebox test instead
    of true surface-overlap. It catches plate/boss/rib walls -- the common real
    cases -- and misses curved walls. It can also flag a narrow *slot* (air
    between the faces) as a thin wall. Upgrade path if that bites: replace the
    rangebox test with MeasureTools.GetMinimumDistance plus a midpoint
    solid-containment test.
    """
    C = _c()
    planes = []
    for body in cd.SurfaceBodies:
        for i in range(1, body.Faces.Count + 1):
            f = body.Faces.Item(i)
            try:
                if f.SurfaceType != C.kPlaneSurface:
                    continue
                g = f.Geometry
                n = (g.Normal.X, g.Normal.Y, g.Normal.Z)
                p = (g.RootPoint.X, g.RootPoint.Y, g.RootPoint.Z)
                rb = f.Evaluator.RangeBox
                box = ((rb.MinPoint.X, rb.MinPoint.Y, rb.MinPoint.Z),
                       (rb.MaxPoint.X, rb.MaxPoint.Y, rb.MaxPoint.Z))
                planes.append((i, n, p, box))
            except Exception:
                continue

    out = []
    seen = set()
    for a in range(len(planes)):
        ia, na, pa, ba = planes[a]
        for b in range(a + 1, len(planes)):
            ib, nb, pb, bb = planes[b]
            if sum(x * y for x, y in zip(na, nb)) > ANTIPARALLEL_DOT:
                continue
            # round before comparing: an exactly-2mm wall computes as
            # 1.999999999999993 and would be a false positive against a 2.0 limit
            gap_mm = round(abs(sum(n * (q - p) for n, p, q in zip(na, pa, pb))) * CM_TO_MM, 3)
            if gap_mm <= 0.001 or gap_mm > MAX_WALL_GAP_MM:
                continue
            # must actually face each other: overlap on the axes across the wall
            if not all(min(ba[1][k], bb[1][k]) >= max(ba[0][k], bb[0][k]) - 1e-6
                       for k in range(3) if abs(na[k]) < 0.9):
                continue
            key = (round(gap_mm, 3), ia, ib)
            if key in seen:
                continue
            seen.add(key)
            out.append({"faces": [ia, ib], "gap_mm": gap_mm})
    out.sort(key=lambda w: w["gap_mm"])
    return out[:50]


def _sick(cd):
    C = _c()
    out = []
    for f in cd.Features:
        try:
            if f.HealthStatus != C.kUpToDateHealth:
                out.append({"name": f.Name, "status": f.HealthStatus})
        except Exception:
            pass
    return out


def _part_facts(doc):
    cd = doc.ComponentDefinition
    facts = {
        "kind": "part",
        "props": _props(doc),
        "sketches": _sketches(cd),
        "holes": _holes(cd),
        "walls": _walls(cd),
        "sick_features": _sick(cd),
        "sheets": [], "interferences": [],
    }
    try:
        facts["props"]["material"] = cd.Material.Name
    except Exception:
        pass
    for key, get in (("mass_kg", lambda: cd.MassProperties.Mass),
                     ("volume_cm3", lambda: cd.MassProperties.Volume),
                     ("feature_count", lambda: cd.Features.Count)):
        try:
            facts[key] = get()
        except Exception:
            pass
    return facts


# --- drawing ----------------------------------------------------------------

_SINGLE_INTENT = ("DiameterGeneralDimension", "RadiusGeneralDimension")
_MULTI_INTENT = ("LinearGeneralDimension", "AngularGeneralDimension")


def _intents(dim):
    """GeometryIntents a dimension attaches to, whichever subtype it really is."""
    for iface in _SINGLE_INTENT:
        try:
            it = w32.CastTo(dim, iface).Intent
            if it is not None:
                return [it]
        except Exception:
            pass
    for iface in _MULTI_INTENT:
        try:
            sub = w32.CastTo(dim, iface)
            out = []
            for attr in ("IntentOne", "IntentTwo", "IntentThree"):
                try:
                    v = getattr(sub, attr)
                    if v is not None:
                        out.append(v)
                except Exception:
                    pass
            if out:
                return out
        except Exception:
            pass
    return []


def _curve_key(curve):
    """Stable identity for a projected model edge.

    AssociativeID alone is not trusted: probe7 saw a legitimate id of 0, so an
    unset id would silently collide. Pairing it with rounded geometry makes a
    collision harmless.
    """
    try:
        edge = curve.ModelGeometry
        aid = edge.AssociativeID
    except Exception:
        return None
    r = None
    try:
        r = round(edge.Geometry.Radius, 6)
    except Exception:
        pass
    cp = None
    try:
        cp = (round(curve.CenterPoint.X, 5), round(curve.CenterPoint.Y, 5))
    except Exception:
        pass
    return (aid, r, cp)


def _is_dimensionable(dc):
    """Is this projected circle something a drafter would actually dimension?

    Two exclusions, both measured against real production drawings where they
    accounted for every single false 'missing dimension':

    * kTangentEdge -- the smooth line where a curved face turns away. Not a
      feature edge, never dimensioned. Every bogus odd diameter (Ø17.60,
      Ø68.69, Ø52.82 ...) was one of these.
    * elliptical projection -- a hole seen at an angle. You dimension it in the
      view where it reads round, so only circular projections count.
    """
    try:
        if dc.EdgeType == _K("kTangentEdge"):
            return False
        if dc.EdgeType == _K("kSilhouetteEdge"):
            return False
    except Exception:
        pass
    try:
        pct = dc.ProjectedCurveType
        circular = {_K("kCircleCurve2d"), _K("kCircularArcCurve2d")} - {None}
        if circular and pct not in circular:
            return False
    except Exception:
        pass
    return True


def _K(name):
    """Constant by name, or None when this Inventor build lacks it."""
    try:
        return getattr(_c(), name)
    except AttributeError:
        return None


_TOL_NAMES = {}


def _tol_type_name(val):
    if not _TOL_NAMES:
        C = _c()
        for label, const in (("none", "kDefaultTolerance"), ("symmetric", "kSymmetricTolerance"),
                             ("deviation", "kDeviationTolerance"), ("limits", "kLimitsTolerance"),
                             ("basic", "kBasicTolerance"), ("reference", "kReferenceTolerance"),
                             ("max", "kMaxTolerance"), ("min", "kMinTolerance"),
                             ("fits", "kFitsTolerance"), ("limits_fits", "kLimitsFitsTolerance"),
                             ("min_max", "kMinMaxTolerance")):
            try:
                _TOL_NAMES[getattr(C, const)] = label
            except AttributeError:
                pass
    return _TOL_NAMES.get(val, f"other({val})")


def _dims_and_missing(sheet):
    """All dimensions on a sheet, plus circles that nothing dimensions.

    Iterates DrawingDimensions (the superset) rather than GeneralDimensions:
    ordinate and baseline set members live outside GeneralDimensions, and the
    DrawingDimension base interface already carries ModelValue/Tolerance/Text.
    """
    C = _c()
    dims, dimmed, dimmed_dia = [], set(), set()
    dd = sheet.DrawingDimensions
    for i in range(1, dd.Count + 1):
        try:
            dim = dd.Item(i)
        except Exception:
            continue
        rec = {"value_mm": None, "tol_type": "none", "upper_mm": None,
               "lower_mm": None, "text": "", "x_cm": None, "y_cm": None}
        try:
            rec["value_mm"] = dim.ModelValue * CM_TO_MM
        except Exception:
            pass
        try:
            rec["text"] = dim.Text.Text
            rec["x_cm"] = dim.Text.Origin.X
            rec["y_cm"] = dim.Text.Origin.Y
        except Exception:
            pass
        try:
            tol = dim.Tolerance
            rec["tol_type"] = _tol_type_name(tol.ToleranceType)
            if rec["tol_type"] != "none":
                rec["upper_mm"] = tol.Upper * CM_TO_MM
                rec["lower_mm"] = tol.Lower * CM_TO_MM
        except Exception:
            pass
        # angular dims are in radians, not cm -- don't pretend they're lengths
        try:
            if dim.Type == C.kAngularGeneralDimensionObject:
                rec["value_mm"] = None
        except Exception:
            pass
        if rec["value_mm"] is not None:
            dims.append(rec)
            dimmed_dia.add(round(abs(rec["value_mm"]), 2))
        for it in _intents(dim):
            try:
                k = _curve_key(it.Geometry)
                if k:
                    dimmed.add(k)
            except Exception:
                pass

    # Circles with nothing dimensioning them.
    #
    # A hole shows up once per view, so identity is the MODEL EDGE (id+radius),
    # never the sheet position -- keying on position reported one finding per
    # view and buried the real ones (160 "missing" on a 7-view drawing).
    uniq = {}
    n_curves = n_resolved = 0
    for view in sheet.DrawingViews:
        try:
            curves = view.DrawingCurves
        except Exception:
            continue
        for dc in curves:
            try:
                n_curves += 1
                if dc.CurveType not in (C.kCircleCurve, C.kCircularArcCurve):
                    continue
                if not _is_dimensionable(dc):
                    continue
                k = _curve_key(dc)
                if k is None:
                    continue
                n_resolved += 1
                edge_key = (k[0], k[1])       # (AssociativeID, radius)
                if edge_key in uniq:
                    uniq[edge_key]["views"] += 1
                    continue
                r_mm = dc.ModelGeometry.Geometry.Radius * CM_TO_MM
                # Sheet centimetres map onto the exported DXF's millimetres by
                # exactly x10 -- verified against 12 known circles at 0.000 mm
                # error -- so marker coordinates are safe to emit here.
                uniq[edge_key] = {
                    "id": k[0], "key": k, "diameter_mm": r_mm * 2,
                    "x_cm": dc.CenterPoint.X, "y_cm": dc.CenterPoint.Y, "views": 1,
                    "dxf_x": dc.CenterPoint.X * CM_TO_MM,
                    "dxf_y": dc.CenterPoint.Y * CM_TO_MM,
                    "dxf_r": r_mm}
            except Exception:
                continue

    # Group what's left by diameter. Dimensioning one of n identical holes and
    # noting "4x Ø6" is correct drafting, so a diameter that appears on any
    # dimension counts as covered rather than flagging the other n-1.
    groups = {}
    for edge_key, c in uniq.items():
        if c["key"] in dimmed:
            continue
        dia = round(c["diameter_mm"], 2)
        if dia in dimmed_dia or round(dia / 2, 2) in dimmed_dia:
            continue
        g = groups.setdefault(dia, dict(c, count=0))
        g["count"] += 1
    missing = sorted(groups.values(), key=lambda c: -c["diameter_mm"])
    # A .idw references its models by path. Copy the .idw on its own (which is
    # what any file upload does) and ModelGeometry stops resolving, so every
    # circle silently vanishes and the sheet looks perfectly dimensioned.
    # Report that rather than passing off a false all-clear.
    refs_ok = not (n_curves > 0 and n_resolved == 0)
    return dims, missing, refs_ok


_TAG_RE = None


def _plain(s):
    """Strip Inventor's inline style markup, e.g.
    "<StyleOverride Font='AIGDT'>n</StyleOverride>0.009" -> "0.009"."""
    global _TAG_RE
    if _TAG_RE is None:
        import re
        _TAG_RE = re.compile(r"<[^>]*>")
    return _TAG_RE.sub("", s or "").strip()


def _surface_symbols(sheet):
    """Roughness symbols with their actual values -- an empty symbol scores 0."""
    out = []
    try:
        coll = sheet.SurfaceTextureSymbols
    except Exception:
        return out
    for i in range(1, coll.Count + 1):
        rec = {"max": "", "min": "", "method": "", "type": None,
               "no_machining": False}
        try:
            s = coll.Item(i)
        except Exception:
            continue
        for key, attr in (("max", "MaximumRoughness"), ("min", "MinimumRoughness"),
                          ("method", "ProductionMethod")):
            try:
                rec[key] = _plain(getattr(s, attr))
            except Exception:
                pass
        try:
            rec["type"] = s.SurfaceTextureType
            # A "material removal prohibited" symbol carries no roughness value
            # by design -- treating that as a missing value is a false positive.
            rec["no_machining"] = \
                s.SurfaceTextureType == _K("kMaterialRemovalProhibitedSurfaceType")
        except Exception:
            pass
        out.append(rec)
    return out


def _feature_control_frames(sheet):
    """Geometric tolerances with their datum references."""
    out = []
    try:
        coll = sheet.FeatureControlFrames
    except Exception:
        return out
    for i in range(1, coll.Count + 1):
        try:
            f = coll.Item(i)
            rows = f.FeatureControlFrameRows
        except Exception:
            continue
        for r in range(1, rows.Count + 1):
            rec = {"tolerance": "", "datums": [], "characteristic": None}
            try:
                row = rows.Item(r)
            except Exception:
                continue
            try:
                rec["tolerance"] = _plain(row.Tolerance)
            except Exception:
                pass
            for attr in ("DatumOne", "DatumTwo", "DatumThree"):
                try:
                    v = _plain(getattr(row, attr))
                    if v:
                        rec["datums"].append(v)
                except Exception:
                    pass
            try:
                rec["characteristic"] = row.GeometricCharacteristic
            except Exception:
                pass
            out.append(rec)
    return out


def _drawing_facts(doc):
    sheets = []
    refs_ok = True
    notes_text = []
    for sh in doc.Sheets:
        views = []
        for v in sh.DrawingViews:
            rec = {"name": v.Name, "scale": None, "scale_string": None,
                   "view_type": None, "show_label": None, "show_scale": None,
                   "is_detail": False, "is_section": False}
            for key, get in (("scale", lambda v=v: v.Scale),
                             ("scale_string", lambda v=v: v.ScaleString),
                             ("view_type", lambda v=v: v.ViewType),
                             ("show_label", lambda v=v: bool(v.ShowLabel)),
                             ("show_scale", lambda v=v: bool(v.ShowScale))):
                try:
                    rec[key] = get()
                except Exception:
                    pass
            rec["is_detail"] = rec["view_type"] == _K("kDetailDrawingViewType")
            rec["is_section"] = rec["view_type"] == _K("kSectionDrawingViewType")
            views.append(rec)
        dims, missing, sheet_refs_ok = _dims_and_missing(sh)
        refs_ok = refs_ok and sheet_refs_ok
        # Real shops often use a custom Border instead of an Inventor
        # TitleBlock object -- every drawing in the sample set does. Record
        # both so the rule doesn't flag a titled drawing as untitled.
        tb = border = None
        try:
            tb = sh.TitleBlock.Name if sh.TitleBlock else None
        except Exception:
            pass
        try:
            border = sh.Border.Name if sh.Border else None
        except Exception:
            pass
        counts = {}
        for coll in ("Centerlines", "Centermarks", "DrawingNotes", "HoleTables",
                     "SurfaceTextureSymbols", "FeatureControlFrames", "PartsLists",
                     "WeldingSymbols", "RevisionTables", "Balloons",
                     "SketchedSymbols", "EdgeSymbols"):
            try:
                counts[coll] = getattr(sh, coll).Count
            except Exception:
                pass
        # 주서 (general notes) is a scored item, so keep the text, not just a count
        for i in range(1, counts.get("DrawingNotes", 0) + 1):
            try:
                t = sh.DrawingNotes.Item(i).Text
                if t and t.strip() not in ("=", ""):
                    notes_text.append(t.replace("\r", " ").replace("\n", " ").strip())
            except Exception:
                pass
        sheets.append({"name": sh.Name, "title_block": tb, "border": border,
                       "views": views,
                       "surface_symbols": _surface_symbols(sh),
                       "geometric_tols": _feature_control_frames(sh),
                       "dims": dims, "undimensioned": missing, "counts": counts,
                       "width_cm": getattr(sh, "Width", None),
                       "height_cm": getattr(sh, "Height", None)})

    facts = {"kind": "drawing", "props": _props(doc), "sheets": sheets,
             "sketches": [], "holes": [], "walls": [], "interferences": [],
             "sick_features": [], "refs_ok": refs_ok, "notes_text": notes_text}
    try:
        facts["first_angle"] = bool(doc.StylesManager.ActiveStandardStyle.FirstAngleProjection)
    except Exception:
        facts["first_angle"] = None
    try:
        st = doc.StylesManager.ActiveStandardStyle
        facts["standard"] = st.Name
        # KS drawings use a period; Inventor's ISO standard defaults to a comma,
        # which is why every sampled drawing showed "30,00".
        facts["decimal_comma"] = st.DecimalMarkerType == _K("kCommaDecimalMarker")
    except Exception:
        pass
    return facts


# --- assembly ---------------------------------------------------------------

def _assembly_facts(app, doc):
    cd = doc.ComponentDefinition
    facts = {"kind": "assembly", "props": _props(doc), "sheets": [], "sketches": [],
             "holes": [], "walls": [], "interferences": [], "sick_features": _sick(cd)}
    try:
        facts["occurrence_count"] = cd.Occurrences.Count
    except Exception:
        facts["occurrence_count"] = 0
    if facts["occurrence_count"] < 2:
        return facts
    try:
        coll = app.TransientObjects.CreateObjectCollection()
        for o in cd.Occurrences:
            coll.Add(o)
        res = cd.AnalyzeInterference(coll)   # 2nd arg is a collection, never a bool
        for i in range(1, res.Count + 1):
            r = res.Item(i)
            facts["interferences"].append({
                "a": r.OccurrenceOne.Name, "b": r.OccurrenceTwo.Name,
                "volume_mm3": r.Volume * 1000.0,   # cm3 -> mm3
            })
        facts["interferences"].sort(key=lambda x: -x["volume_mm3"])
    except Exception as e:
        facts["interference_error"] = f"{type(e).__name__}: {e}"
    return facts


# --- entry point ------------------------------------------------------------

def _export_stl(doc, out, facts):
    """Mesh for the browser's 3D preview. SaveAs(.stl) is enough -- Inventor
    ships the STL translator and writes binary STL straight out."""
    if not out:
        return
    try:
        doc.SaveAs(out, True)          # True = save a copy, don't touch the original
        if os.path.exists(out) and os.path.getsize(out) > 84:
            facts["stl"] = out
        else:
            facts["stl_error"] = "STL 파일이 생성되지 않았습니다."
    except Exception as e:
        facts["stl_error"] = f"{type(e).__name__}: {e}"


def _open_cast(app, path):
    C = _c()
    doc = app.Documents.Open(path, False)
    kinds = {C.kPartDocumentObject: "PartDocument",
             C.kAssemblyDocumentObject: "AssemblyDocument",
             C.kDrawingDocumentObject: "DrawingDocument"}
    iface = kinds.get(doc.DocumentType)
    if iface:
        doc = w32.CastTo(doc, iface)
    return doc, doc.DocumentType


def analyze(path, dxf_out=None, stl_out=None):
    """Open `path` in Inventor, extract facts, optionally export DXF/STL for the viewer."""
    path = os.path.abspath(path)
    with _LOCK:
        _com_init()
        try:
            return _analyze_locked(path, dxf_out, stl_out)
        except Exception as e:
            # Inventor died between requests -- reconnect and try once more so a
            # closed Inventor doesn't brick the server until it's restarted.
            if not _is_dead_com(e):
                raise
            _get_app(force_new=True)
            return _analyze_locked(path, dxf_out, stl_out)


def _analyze_locked(path, dxf_out, stl_out):
    app = _get_app()
    C = _c()
    doc, dtype = _open_cast(app, path)
    try:
        if dtype == C.kPartDocumentObject:
            facts = _part_facts(doc)
            _export_stl(doc, stl_out, facts)
        elif dtype == C.kDrawingDocumentObject:
            facts = _drawing_facts(doc)
            if dxf_out:
                try:
                    doc.SaveAs(dxf_out, True)   # True = save a copy
                    facts["dxf"] = dxf_out
                except Exception as e:
                    facts["dxf_error"] = str(e)
        elif dtype == C.kAssemblyDocumentObject:
            facts = _assembly_facts(app, doc)
            _export_stl(doc, stl_out, facts)
        else:
            facts = {"kind": "unsupported", "document_type": dtype,
                     "sheets": [], "sketches": [], "holes": [], "walls": [],
                     "interferences": [], "sick_features": [], "props": {}}
        facts["file"] = os.path.basename(path)
        return facts
    finally:
        try:
            doc.Close(True)
        except Exception:
            pass


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(analyze(sys.argv[1]), ensure_ascii=False, indent=2, default=str))
