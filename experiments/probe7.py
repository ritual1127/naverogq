import os
import win32com.client as w32

FIX = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures")
IDW = os.path.join(FIX, "probe_drawing.idw")
IAM = os.path.join(FIX, "probe_asm.iam")

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants
D = w32.constants.__dict__.get("__dicts__", [{}])[0]


def name_of(val):
    return [k for k, v in D.items() if v == val] or val


def sect(n):
    print(f"\n{'=' * 60}\n== {n}\n{'=' * 60}")


sect("1. INTERFERENCE with correct signature")
asm = w32.CastTo(app.Documents.Open(IAM, False), "AssemblyDocument")
acd = asm.ComponentDefinition
print("  occurrences:", acd.Occurrences.Count)
coll = app.TransientObjects.CreateObjectCollection()
for o in acd.Occurrences:
    coll.Add(o)

for label, call in (
    ("AnalyzeInterference(coll)  [single set]", lambda: acd.AnalyzeInterference(coll)),
):
    try:
        res = call()
        print(f"  OK  {label} -> {res.Count} result(s)")
        for i in range(1, res.Count + 1):
            r = res.Item(i)
            print(f"      #{i} volume={r.Volume:.4f} cm3 = {r.Volume * 1000:.1f} mm3"
                  f"  {r.OccurrenceOne.Name} <-> {r.OccurrenceTwo.Name}")
            if i == 1:
                print("      members:", ", ".join(
                    sorted(x for x in dir(r) if not x.startswith("_") and x[0].isupper())))
    except Exception as e:
        print(f"  FAIL {label}: {type(e).__name__} {str(e)[:200]}")
asm.Close(True)

sect("2+3. DIM SUBTYPE via .Type, Intent -> curve, AssociativeID identity")
drw = w32.CastTo(app.Documents.Open(IDW, False), "DrawingDocument")
sheet = drw.Sheets.Item(1)
view = sheet.DrawingViews.Item(1)

SINGLE = ("DiameterGeneralDimension", "RadiusGeneralDimension")
MULTI = ("LinearGeneralDimension", "AngularGeneralDimension")


def intents_of(dim):
    for iface in SINGLE:
        try:
            return [w32.CastTo(dim, iface).Intent]
        except Exception:
            pass
    for iface in MULTI:
        try:
            sub = w32.CastTo(dim, iface)
            out = []
            for a in ("IntentOne", "IntentTwo", "IntentThree"):
                try:
                    v = getattr(sub, a)
                    if v is not None:
                        out.append(v)
                except Exception:
                    pass
            if out:
                return out
        except Exception:
            pass
    return []


dimmed_ids = set()
for dim in sheet.DrawingDimensions.GeneralDimensions:
    print(f"  dim .Type = {dim.Type} -> {name_of(dim.Type)}")
    ints = intents_of(dim)
    print(f"    intents found: {len(ints)}")
    for it in ints:
        try:
            g = it.Geometry
            print(f"      Geometry = {g!r}")
            print(f"      CurveType = {getattr(g, 'CurveType', None)!r}")
            edge = g.ModelGeometry
            aid = edge.AssociativeID
            dimmed_ids.add(aid)
            print(f"      ModelGeometry.AssociativeID = {aid!r}")
        except Exception as e:
            print(f"      intent.Geometry FAIL: {type(e).__name__} {str(e)[:110]}")

print(f"\n  dimensioned AssociativeIDs: {dimmed_ids}")

sect("MISSING-DIMENSION CHECK, end to end")
circles = []
for dc in view.DrawingCurves:
    if dc.CurveType not in (C.kCircleCurve, C.kCircularArcCurve):
        continue
    try:
        edge = dc.ModelGeometry
        aid = edge.AssociativeID
        r_cm = edge.Geometry.Radius
        cp = dc.CenterPoint
        circles.append((aid, r_cm, (cp.X, cp.Y)))
    except Exception:
        pass
uniq = {}
for aid, r, cp in circles:
    uniq.setdefault(aid, (r, cp))
print(f"  circle/arc curves: {len(circles)}, unique model edges: {len(uniq)}")
missing = [(aid, r, cp) for aid, (r, cp) in uniq.items() if aid not in dimmed_ids]
print(f"  dimensioned: {len(uniq) - len(missing)}   MISSING DIMENSION: {len(missing)}")
for aid, r, cp in missing[:10]:
    print(f"     edge {aid}: d={r * 20:.2f} mm at sheet ({cp[0]:.2f}, {cp[1]:.2f}) cm")

sect("projection + title block checks")
st = drw.StylesManager.ActiveStandardStyle
print("  FirstAngleProjection =", st.FirstAngleProjection,
      "->", "제1각법" if st.FirstAngleProjection else "제3각법")
print("  TitleBlock:", sheet.TitleBlock.Name if sheet.TitleBlock else None)
print("  view.Scale:", view.Scale, " ScaleString:", view.ScaleString)
drw.Close(True)
print("\nDONE")

