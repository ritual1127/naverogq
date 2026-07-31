"""Probe 5: the last three unknowns.

1. dimension -> geometry attachment (cast GeneralDimension to its subtype?)
2. thin-wall primitive: planar face pairs + plane geometry
3. interference: AnalyzeInterference on a real assembly
"""
import os
import glob
import win32com.client as w32

IDW = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures", "probe_drawing.idw")
PART = r"C:\Users\smile\OneDrive\Documents\부품1.ipt"


def sect(n):
    print(f"\n{'=' * 60}\n== {n}\n{'=' * 60}")


def try_(label, fn):
    try:
        v = fn()
        print(f"  OK    {label} = {v!r}")
        return v
    except Exception as e:
        print(f"  FAIL  {label} -> {type(e).__name__}: {str(e)[:130]}")
        return None


app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants

sect("1. DIMENSION -> GEOMETRY via subtype cast")
drw = w32.CastTo(app.Documents.Open(IDW, False), "DrawingDocument")
sheet = drw.Sheets.Item(1)
gd = sheet.DrawingDimensions.GeneralDimensions
TYPE_TO_IFACE = {
    C.kDiametricDimensionType: "DiameterGeneralDimension",
    C.kHorizontalDimensionType: "LinearGeneralDimension",
    C.kVerticalDimensionType: "LinearGeneralDimension",
    C.kAlignedDimensionType: "LinearGeneralDimension",
    C.kAngularDimensionType: "AngularGeneralDimension",
}
for dim in gd:
    gdt = dim.GeneralDimensionType
    print(f"  dim GeneralDimensionType={gdt} Attached={dim.Attached!r}")
    iface = TYPE_TO_IFACE.get(gdt)
    print(f"  candidate interface: {iface}")
    for cand in ([iface] if iface else []) + ["DiameterGeneralDimension",
                                              "RadiusGeneralDimension",
                                              "LinearGeneralDimension"]:
        if not cand:
            continue
        try:
            sub = w32.CastTo(dim, cand)
            print(f"    CastTo({cand}) OK")
            for a in ("IntentOne", "IntentTwo"):
                try:
                    it = getattr(sub, a)
                    print(f"      {a} = {it!r}")
                    try:
                        g = it.Geometry
                        print(f"        .Geometry = {g!r} CurveType="
                              f"{getattr(g, 'CurveType', 'n/a')!r}")
                        print(f"        model edge = {getattr(g, 'ModelGeometry', None)!r}")
                    except Exception as e2:
                        print(f"        .Geometry FAIL {type(e2).__name__}")
                except Exception as e:
                    print(f"      {a} FAIL {type(e).__name__}")
            break
        except Exception as e:
            print(f"    CastTo({cand}) FAIL: {str(e)[:90]}")

sect("2. THIN WALL primitive: planar faces + plane geometry")
part = w32.CastTo(app.Documents.Open(PART, False), "PartDocument")
body = part.ComponentDefinition.SurfaceBodies.Item(1)
planes = []
for i in range(1, body.Faces.Count + 1):
    f = body.Faces.Item(i)
    if f.SurfaceType != C.kPlaneSurface:
        continue
    try:
        g = f.Geometry
        n = (g.Normal.X, g.Normal.Y, g.Normal.Z)
        rp = (g.RootPoint.X, g.RootPoint.Y, g.RootPoint.Z)
        rb = f.Evaluator.RangeBox
        planes.append((i, n, rp, f))
        if len(planes) <= 4:
            print(f"  face {i}: Normal={tuple(round(x, 4) for x in n)} "
                  f"RootPoint={tuple(round(x, 4) for x in rp)}")
            print(f"     rangebox min=({rb.MinPoint.X:.3f},{rb.MinPoint.Y:.3f},{rb.MinPoint.Z:.3f}) "
                  f"max=({rb.MaxPoint.X:.3f},{rb.MaxPoint.Y:.3f},{rb.MaxPoint.Z:.3f})")
    except Exception as e:
        print(f"  face {i} geometry FAIL: {type(e).__name__}: {str(e)[:80]}")
print(f"  planar faces: {len(planes)} / {body.Faces.Count}")
try_("face.Evaluator.Area (cm2)", lambda: body.Faces.Item(planes[0][0]).Evaluator.Area)

print("  -- anti-parallel plane pairs (dot < -0.99) and their separation --")
found = 0
for a in range(len(planes)):
    for b in range(a + 1, len(planes)):
        ia, na, pa, _ = planes[a]
        ib, nb, pb, _ = planes[b]
        dot = sum(x * y for x, y in zip(na, nb))
        if dot > -0.99:
            continue
        # distance from plane a to point on plane b, along a's normal
        d = abs(sum(n * (q - p) for n, p, q in zip(na, pa, pb)))
        print(f"     faces {ia}<->{ib}  dot={dot:.4f}  gap={d * 10:.3f} mm")
        found += 1
        if found >= 8:
            break
    if found >= 8:
        break
print(f"  anti-parallel pairs found: {found}")

sect("2b. MeasureTools.GetMinimumDistance (exact, but how slow?)")
if len(planes) >= 2:
    try_("GetMinimumDistance(face0, face1) cm",
         lambda: app.MeasureTools.GetMinimumDistance(
             body.Faces.Item(planes[0][0]), body.Faces.Item(planes[1][0])))

sect("3. INTERFERENCE on a real assembly")
cands = []
for pat in (r"C:\Users\Public\Documents\Autodesk\Inventor 2026\Design Data\**\*.iam",):
    cands += glob.glob(pat, recursive=True)
print("  assembly candidates:", cands[:5])
asm_path = next((c for c in cands if "harness" in c.lower()), cands[0] if cands else None)
if asm_path:
    print("  using:", asm_path)
    try:
        asm = w32.CastTo(app.Documents.Open(asm_path, False), "AssemblyDocument")
        acd = asm.ComponentDefinition
        print("  occurrences:", acd.Occurrences.Count)
        members = [x for x in dir(acd) if "nterferen" in x.lower()]
        print("  interference-related members:", members)
        try:
            occs = acd.Occurrences
            coll = app.TransientObjects.CreateObjectCollection()
            for o in occs:
                coll.Add(o)
            print("  collection size:", coll.Count)
            res = acd.AnalyzeInterference(coll, False)
            print("  AnalyzeInterference OK, results:", res.Count)
            for i in range(1, min(res.Count, 3) + 1):
                r = res.Item(i)
                print(f"     #{i} volume={r.Volume!r} "
                      f"occ1={r.OccurrenceOne.Name!r} occ2={r.OccurrenceTwo.Name!r}")
        except Exception as e:
            print("  FAIL AnalyzeInterference:", type(e).__name__, str(e)[:200])
        asm.Close(True)
    except Exception as e:
        print("  FAIL open assembly:", type(e).__name__, str(e)[:200])

drw.Close(True)
part.Close(True)
print("\nDONE")
