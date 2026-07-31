"""Probe 6: last two unknowns.

A. What does DiameterGeneralDimension actually expose? (dir it, don't guess)
   And what is GeneralDimensionType 72194?
B. Build a 2-part assembly with deliberate overlap -> AnalyzeInterference.
"""
import os
import win32com.client as w32

IDW = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures", "probe_drawing.idw")
FIX = os.path.dirname(IDW)
P1 = r"C:\Users\smile\OneDrive\Documents\부품1.ipt"
P2 = r"C:\Users\smile\OneDrive\Documents\부품2.ipt"
IAM = os.path.join(FIX, "probe_asm.iam")

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants
tg = app.TransientGeometry


def sect(n):
    print(f"\n{'=' * 60}\n== {n}\n{'=' * 60}")


sect("A1. what is GeneralDimensionType 72194?")
d = w32.constants.__dict__.get("__dicts__", [{}])[0]
for k, v in sorted(d.items()):
    if v in (72194, 72193, 72195, 72196, 72197):
        print(f"     {k} = {v}")

sect("A2. dir() the dimension subtypes for real")
drw = w32.CastTo(app.Documents.Open(IDW, False), "DrawingDocument")
sheet = drw.Sheets.Item(1)
dim = sheet.DrawingDimensions.GeneralDimensions.Item(1)
print("  base GeneralDimension type value:", dim.GeneralDimensionType)
for iface in ("DiameterGeneralDimension", "RadiusGeneralDimension",
              "LinearGeneralDimension", "AngularGeneralDimension",
              "DrawingDimension"):
    try:
        sub = w32.CastTo(dim, iface)
        ms = sorted(x for x in dir(sub) if not x.startswith("_") and x[0].isupper())
        print(f"\n  --- {iface} ---\n     {', '.join(ms)}")
    except Exception as e:
        print(f"\n  --- {iface} --- CastTo FAIL: {str(e)[:80]}")

sect("A3. reverse route: does a DrawingCurve know its dimensions?")
view = sheet.DrawingViews.Item(1)
dc = view.DrawingCurves.Item(1)
print("  Sheet.FindUsingPoint exists:", hasattr(sheet, "FindUsingPoint"))
# try locating annotations at a circle's centre
for dcx in view.DrawingCurves:
    if dcx.CurveType == C.kCircleCurve:
        cp = dcx.CenterPoint
        try:
            found = sheet.FindUsingPoint(tg.CreatePoint2d(cp.X, cp.Y), 0.5)
            print(f"  FindUsingPoint near circle centre -> count={found.Count}")
            for i in range(1, found.Count + 1):
                print(f"     {found.Item(i)!r}")
        except Exception as e:
            print("  FindUsingPoint FAIL:", type(e).__name__, str(e)[:120])
        break
drw.Close(True)

sect("B. BUILD ASSEMBLY WITH DELIBERATE OVERLAP -> interference")
tmpl = app.FileManager.GetTemplateFile(C.kAssemblyDocumentObject)
print("  assembly template:", tmpl)
asm = w32.CastTo(app.Documents.Add(C.kAssemblyDocumentObject, tmpl, True), "AssemblyDocument")
acd = asm.ComponentDefinition

m1 = tg.CreateMatrix()  # identity: at origin
occ1 = acd.Occurrences.Add(P1, m1)
print("  occ1 added:", occ1.Name)

m2 = tg.CreateMatrix()
m2.SetTranslation(tg.CreateVector(1.0, 0.0, 0.0))  # +10 mm -> guaranteed overlap
occ2 = acd.Occurrences.Add(P1, m2)
print("  occ2 added:", occ2.Name, "(shifted 10mm, must interfere)")

occ3 = acd.Occurrences.Add(P2, tg.CreateMatrix())
print("  occ3 added:", occ3.Name, "(부품2 at origin)")
print("  Occurrences.Count =", acd.Occurrences.Count)

coll = app.TransientObjects.CreateObjectCollection()
for o in acd.Occurrences:
    coll.Add(o)
print("  collection size:", coll.Count)

try:
    res = acd.AnalyzeInterference(coll, False)
    print("  AnalyzeInterference OK -> results:", res.Count)
    for i in range(1, res.Count + 1):
        r = res.Item(i)
        print(f"     #{i} volume={r.Volume:.4f} cm3  "
              f"({r.OccurrenceOne.Name} <-> {r.OccurrenceTwo.Name})")
        ms = sorted(x for x in dir(r) if not x.startswith("_") and x[0].isupper())
        if i == 1:
            print("       InterferenceResult members:", ", ".join(ms))
            for a in ("CenterOfGravity", "RangeBox"):
                try:
                    o = getattr(r, a)
                    if a == "CenterOfGravity":
                        print(f"       {a} = ({o.X:.3f},{o.Y:.3f},{o.Z:.3f})")
                    else:
                        print(f"       {a} min=({o.MinPoint.X:.3f},{o.MinPoint.Y:.3f},"
                              f"{o.MinPoint.Z:.3f})")
                except Exception as e:
                    print(f"       {a} FAIL {type(e).__name__}")
except Exception as e:
    print("  FAIL AnalyzeInterference:", type(e).__name__, str(e)[:250])

try:
    asm.SaveAs(IAM, False)
    print("  saved fixture:", IAM)
except Exception as e:
    print("  SaveAs FAIL:", str(e)[:150])
asm.Close(True)
print("\nDONE")
