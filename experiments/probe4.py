import os
import win32com.client as w32

IDW = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures", "probe_drawing.idw")


def members(obj, label):
    print(f"\n--- {label} ---")
    try:
        ms = sorted(x for x in dir(obj) if not x.startswith("_") and x[0].isupper())
    except Exception as e:
        print("   dir failed:", e)
        return
    print("   " + ", ".join(ms))


app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants

drw = w32.CastTo(app.Documents.Open(IDW, False), "DrawingDocument")
sheet = drw.Sheets.Item(1)
view = sheet.DrawingViews.Item(1)
gd = sheet.DrawingDimensions.GeneralDimensions
print("dims:", gd.Count, "curves:", view.DrawingCurves.Count)

members(sheet, "Sheet")
members(view, "DrawingView")
members(view.DrawingCurves.Item(1), "DrawingCurve")
members(view.DrawingCurves.Item(1).ModelGeometry, "DrawingCurve.ModelGeometry")
members(sheet.DrawingDimensions, "DrawingDimensions")
members(drw.StylesManager.ActiveStandardStyle, "DrawingStandardStyle")

dim = gd.Item(1)
members(dim, "GeneralDimension")
members(dim.Tolerance, "Tolerance")
members(dim.Text, "DimensionText")

print("\n=== ATTACHMENT HUNT ===")
for attr in ("AttachedEntity", "AttachedEntities", "Geometry", "IntentOne", "IntentTwo",
             "ExtensionLineOneVisible", "DimensionedGeometryOne", "DimensionedGeometryTwo"):
    try:
        print(f"  OK   dim.{attr} = {getattr(dim, attr)!r}")
    except Exception as e:
        print(f"  --   dim.{attr}: {type(e).__name__}")

for meth in ("GetAttachedGeometry", "GetDimensionedGeometry", "GetGeometryIntents"):
    try:
        r = getattr(dim, meth)()
        print(f"  OK   dim.{meth}() -> {r!r}")
    except Exception as e:
        print(f"  --   dim.{meth}(): {type(e).__name__}: {str(e)[:100]}")

print("\n=== CURVE IDENTITY (can we match curves to dims?) ===")
dc = view.DrawingCurves.Item(1)
for attr in ("ModelGeometry", "CurveType", "Parent", "View", "Layer", "StartPoint", "EndPoint"):
    try:
        print(f"  OK   curve.{attr} = {getattr(dc, attr)!r}")
    except Exception as e:
        print(f"  --   curve.{attr}: {type(e).__name__}")

print("\n=== circle radius: which route works? ===")
for dcx in view.DrawingCurves:
    if dcx.CurveType == C.kCircleCurve:
        members(dcx.Evaluator2D, "Evaluator2D")
        for a in ("Radius", "Center"):
            try:
                g = dcx.ModelGeometry.Geometry
                v = getattr(g, a)
                v = (v.X, v.Y, v.Z) if a == "Center" else v
                print(f"  OK   modelEdge.Geometry.{a} = {v!r}")
            except Exception as e:
                print(f"  --   modelEdge.Geometry.{a}: {type(e).__name__}: {str(e)[:80]}")
        try:
            cp, sp = dcx.CenterPoint, dcx.StartPoint
            r = ((cp.X - sp.X) ** 2 + (cp.Y - sp.Y) ** 2) ** 0.5
            print(f"  OK   radius from CenterPoint/StartPoint = {r!r} cm")
        except Exception as e:
            print(f"  --   geometric radius: {e}")
        break

print("\n=== FILLET radius via EdgeSetItem ===")
model = w32.CastTo(app.Documents.Open(r"C:\Users\smile\OneDrive\Documents\부품1.ipt", False), "PartDocument")
fd = model.ComponentDefinition.Features.FilletFeatures.Item(1).FilletDefinition
print("  EdgeSetCount =", fd.EdgeSetCount, "FilletType =", fd.FilletType)
try:
    es = fd.EdgeSetItem(1)
    members(es, "FilletEdgeSet")
    print("  Radius.Value =", es.Radius.Value)
except Exception as e:
    print("  FAIL EdgeSetItem:", e)

print("\n=== SHEET annotation collections (real names) ===")
for m in sorted(x for x in dir(sheet) if not x.startswith("_") and x[0].isupper()):
    if any(t in m.lower() for t in ("note", "symbol", "mark", "line", "leader", "table", "frame")):
        try:
            print(f"  {m}.Count = {getattr(sheet, m).Count}")
        except Exception:
            print(f"  {m} (not a collection)")

drw.Close(True)
model.Close(True)
print("\nDONE")

