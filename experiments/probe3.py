"""Probe 3: the drawing side. Dimensions, tolerances, curves, projection, DXF export.

Builds a real .idw from the user's part so we have a fixture AND verify the API
paths that rules.py will depend on.
"""
import os
import win32com.client as w32

MODEL = r"C:\Users\smile\OneDrive\Documents\부품1.ipt"
TEMPLATE = r"C:\Users\Public\Documents\Autodesk\Inventor 2026\Templates\ko-KR\Metric\ISO.idw"
OUT = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures")
os.makedirs(OUT, exist_ok=True)
IDW = os.path.join(OUT, "probe_drawing.idw")


def sect(n):
    print(f"\n{'=' * 60}\n== {n}\n{'=' * 60}")


def try_(label, fn):
    try:
        v = fn()
        print(f"  OK    {label} = {v!r}")
        return v
    except Exception as e:
        print(f"  FAIL  {label} -> {type(e).__name__}: {str(e)[:140]}")
        return None


app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants

sect("CONSTANT NAME HUNT (projection / view / curve / tolerance)")
# dump every constant whose name hints at what we need
import win32com.client.gencache as gc
mod = gc.GetModuleForProgID("Inventor.Application")
allc = {}
try:
    for name in dir(w32.constants.__dicts__[0] if hasattr(w32.constants, "__dicts__") else {}):
        pass
except Exception:
    pass
d = w32.constants.__dict__.get("__dicts__", [{}])[0]
for k, v in sorted(d.items()):
    lk = k.lower()
    if any(t in lk for t in ("projectiontype", "viewstyle", "vieworientation",
                             "tolerancetype", "curvetype", "dimensiontype")):
        allc[k] = v
for k, v in allc.items():
    print(f"     {k} = {v}")

sect("CREATE DRAWING + BASE VIEW")
model = w32.CastTo(app.Documents.Open(MODEL, False), "PartDocument")
drw = w32.CastTo(app.Documents.Add(C.kDrawingDocumentObject, TEMPLATE, True), "DrawingDocument")
print("  drawing created, sheets =", drw.Sheets.Count)
sheet = drw.Sheets.Item(1)
tg = app.TransientGeometry
view = sheet.DrawingViews.AddBaseView(
    model, tg.CreatePoint2d(20, 20), 1.0,
    C.kFrontViewOrientation, C.kHiddenLineDrawingViewStyle)
print("  base view added")
try_("view.Scale", lambda: view.Scale)
try_("view.ViewType", lambda: view.ViewType)
try_("view.Name", lambda: view.Name)
try_("view.ReferencedDocumentDescriptor.FullDocumentName",
     lambda: view.ReferencedDocumentDescriptor.FullDocumentName)

sect("DRAWING CURVES (basis of the missing-dimension check)")
curves = view.DrawingCurves
print("  DrawingCurves.Count =", curves.Count)
hist = {}
circles = []
for dc in curves:
    try:
        ct = dc.CurveType
        hist[ct] = hist.get(ct, 0) + 1
        if ct in (C.kCircleCurve, C.kCircularArcCurve):
            circles.append(dc)
    except Exception:
        pass
print("  CurveType histogram:", hist)
print("  circle/arc curves found:", len(circles))
if circles:
    dc = circles[0]
    try_("circle.CenterPoint (X,Y)", lambda: (dc.CenterPoint.X, dc.CenterPoint.Y))
    try_("circle.Radius", lambda: dc.Radius)
    try_("circle.ModelGeometry type", lambda: str(dc.ModelGeometry))
    try_("circle.Visible", lambda: dc.Visible)

sect("ADD DIMENSIONS then read them back")
gd = sheet.DrawingDimensions.GeneralDimensions
added = 0
if circles:
    try:
        intent = sheet.CreateGeometryIntent(circles[0])
        dim = gd.AddDiameter(tg.CreatePoint2d(35, 30), intent)
        added += 1
        print("  AddDiameter OK")
    except Exception as e:
        print("  FAIL AddDiameter:", e)
# linear dim between two straight curves
lines = [c for c in curves if c.CurveType == C.kLineSegmentCurve]
print("  line curves:", len(lines))
if len(lines) >= 2:
    try:
        i1 = sheet.CreateGeometryIntent(lines[0])
        i2 = sheet.CreateGeometryIntent(lines[1])
        dim2 = gd.AddLinear(tg.CreatePoint2d(5, 30), i1, i2)
        added += 1
        print("  AddLinear OK")
    except Exception as e:
        print("  FAIL AddLinear:", e)
print("  dims added:", added, "| GeneralDimensions.Count =", gd.Count)

sect("DIMENSION INTROSPECTION (tolerance!)")
for i, dim in enumerate(gd, 1):
    print(f"  -- dim #{i}")
    try_("     ModelValue (cm)", lambda dim=dim: dim.ModelValue)
    try_("     Text.Text", lambda dim=dim: dim.Text.Text)
    try_("     Text.FormattedText", lambda dim=dim: dim.Text.FormattedText)
    try_("     DimensionType", lambda dim=dim: dim.DimensionType)
    try_("     Tolerance.ToleranceType", lambda dim=dim: dim.Tolerance.ToleranceType)
    try_("     Tolerance.Upper", lambda dim=dim: dim.Tolerance.Upper)
    try_("     Tolerance.Lower", lambda dim=dim: dim.Tolerance.Lower)
    try_("     Tolerance.Precision", lambda dim=dim: dim.Tolerance.Precision)
    try_("     IntentOne.Geometry is a DrawingCurve?",
         lambda dim=dim: str(dim.IntentOne.Geometry))
    try_("     IntentTwo present", lambda dim=dim: str(dim.IntentTwo))
    try_("     Origin/text position", lambda dim=dim: (dim.Text.Origin.X, dim.Text.Origin.Y))

sect("SET a tolerance, read it back (proves we can classify properly)")
if gd.Count:
    d1 = gd.Item(1)
    try_("SetToleranceMethod deviation",
         lambda: d1.Tolerance.SetToDeviation(0.005, -0.005) or "set")
    try_("  -> ToleranceType now", lambda: d1.Tolerance.ToleranceType)
    try_("  -> Upper/Lower now", lambda: (d1.Tolerance.Upper, d1.Tolerance.Lower))

sect("SHEET / TITLE BLOCK / STANDARD")
try_("sheet.Name", lambda: sheet.Name)
try_("sheet.Size", lambda: sheet.Size)
try_("sheet.TitleBlock.Name", lambda: sheet.TitleBlock.Name)
try_("sheet.Border present", lambda: str(sheet.Border))
try_("drw.StylesManager active standard",
     lambda: drw.StylesManager.ActiveStandardStyle.Name)
try_("ActiveStandardStyle.ProjectionType",
     lambda: drw.StylesManager.ActiveStandardStyle.ProjectionType)
try_("sheet.DrawingDimensions.Count", lambda: sheet.DrawingDimensions.Count)
try_("sheet.HoleTables.Count", lambda: sheet.HoleTables.Count)
try_("sheet.Sketches.Count", lambda: sheet.Sketches.Count)
for coll in ("GeneralNotes", "Leaders", "SurfaceTextureSymbols", "DatumIdentifierSymbols",
             "FeatureControlFrames", "CentreMarks", "Centrelines", "Balloons"):
    try_(f"sheet.{coll}.Count", lambda c=coll: getattr(sheet, c).Count)

sect("SAVE + DXF EXPORT (viewer pipeline)")
try_("SaveAs idw", lambda: drw.SaveAs(IDW, False) or IDW)
dxf = IDW.replace(".idw", ".dxf")
try_("SaveAs dxf (copy)", lambda: drw.SaveAs(dxf, True) or dxf)
print("  dxf exists:", os.path.exists(dxf),
      os.path.getsize(dxf) if os.path.exists(dxf) else "")

sect("FIX-UPS from probe2")
cd = model.ComponentDefinition
b = cd.SurfaceBodies.Item(1)
try_("RangeBox via .X/.Y/.Z",
     lambda: ((b.RangeBox.MinPoint.X, b.RangeBox.MinPoint.Y, b.RangeBox.MinPoint.Z),
              (b.RangeBox.MaxPoint.X, b.RangeBox.MaxPoint.Y, b.RangeBox.MaxPoint.Z)))
fl = cd.Features.FilletFeatures.Item(1)
try_("fillet.FilletDefinition dir", lambda: [x for x in dir(fl.FilletDefinition) if not x.startswith("_")])
try_("fillet EdgeSets count", lambda: fl.FilletDefinition.EdgeSets.Count)
try_("fillet EdgeSets(1).Radius.Value", lambda: fl.FilletDefinition.EdgeSets.Item(1).Radius.Value)
f0 = b.Faces.Item(1)
try_("face.SurfaceType", lambda: f0.SurfaceType)
try_("face.Evaluator exists", lambda: str(f0.Evaluator))
try_("face.Geometry (plane) Normal", lambda: (f0.Geometry.Normal.X, f0.Geometry.Normal.Y, f0.Geometry.Normal.Z))

print("\nleaving docs open for inspection is bad; closing")
drw.Close(True)
model.Close(True)
print("DONE")
