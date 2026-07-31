"""Probe 2: interrogate a real .ipt and report which COM paths actually work.

Every section is guarded so one bad API path doesn't kill the run. Output tells
us exactly what inventor.py is allowed to rely on.
"""
import sys
import win32com.client as w32

PATH = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\smile\OneDrive\Documents\부품1.ipt"


def sect(name):
    print(f"\n{'=' * 60}\n== {name}\n{'=' * 60}")


def try_(label, fn):
    try:
        v = fn()
        print(f"  OK    {label} = {v!r}")
        return v
    except Exception as e:
        print(f"  FAIL  {label} -> {type(e).__name__}: {str(e)[:160]}")
        return None


app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True

sect(f"OPEN {PATH}")
doc = app.Documents.Open(PATH, False)  # False = don't make visible
print("  opened:", doc.DisplayName, "| type:", doc.DocumentType)
# Documents.Open hands back the generic Document interface; must cast to reach
# ComponentDefinition. This is THE pywin32/Inventor gotcha.
doc = w32.CastTo(doc, "PartDocument")
print("  cast to PartDocument OK")
cd = doc.ComponentDefinition

sect("CONSTANTS available from generated typelib?")
for c in ("kPartDocumentObject", "kDrawingDocumentObject", "kAssemblyDocumentObject",
          "kUnderConstrainedConstraintStatus", "kFullyConstrainedConstraintStatus",
          "kOverConstrainedConstraintStatus", "kPlaneSurface", "kCylinderSurface",
          "kUpToDateHealth", "kDefaultTolerance", "kSymmetricTolerance",
          "kFirstAngleProjectionType", "kThirdAngleProjectionType", "kCircleCurve"):
    try_(f"constants.{c}", lambda c=c: getattr(w32.constants, c))

sect("iPROPERTIES / PropertySets")
for setname in ("Design Tracking Properties", "Inventor Summary Information",
                "Inventor Document Summary Information"):
    try:
        ps = doc.PropertySets.Item(setname)
        print(f"  -- {setname} ({ps.Count} props)")
        for p in ps:
            try:
                if p.Value not in (None, ""):
                    print(f"       {p.Name!r} = {p.Value!r}")
            except Exception:
                pass
    except Exception as e:
        print(f"  FAIL  {setname}: {e}")

sect("MATERIAL")
try_("cd.Material.Name", lambda: cd.Material.Name)
try_("doc.ActiveMaterial.Name", lambda: doc.ActiveMaterial.Name)
try_("cd.MassProperties.Mass (kg)", lambda: cd.MassProperties.Mass)
try_("cd.MassProperties.Volume (cm3)", lambda: cd.MassProperties.Volume)

sect("SKETCHES + CONSTRAINT STATUS")
try:
    print("  Sketches.Count =", cd.Sketches.Count)
    for sk in cd.Sketches:
        print(f"  -- sketch {sk.Name!r} entities={sk.SketchEntities.Count}")
        try_("    sketch.ConstraintStatus", lambda sk=sk: sk.ConstraintStatus)
        counts = {}
        for ent in sk.SketchEntities:
            try:
                cs = ent.ConstraintStatus
            except Exception as e:
                cs = f"ERR:{type(e).__name__}"
            counts[cs] = counts.get(cs, 0) + 1
        print("     entity ConstraintStatus histogram:", counts)
        try_("    sk.DimensionConstraints.Count", lambda sk=sk: sk.DimensionConstraints.Count)
        try_("    sk.GeometricConstraints.Count", lambda sk=sk: sk.GeometricConstraints.Count)
except Exception as e:
    print("  FAIL sketches:", e)

sect("FEATURES")
try:
    f = cd.Features
    for coll in ("HoleFeatures", "FilletFeatures", "ExtrudeFeatures", "ChamferFeatures",
                 "RevolveFeatures", "ThreadFeatures", "ShellFeatures"):
        try_(f"Features.{coll}.Count", lambda c=coll: getattr(f, c).Count)
    print("  -- holes in detail (Inventor internal length unit = cm)")
    for h in f.HoleFeatures:
        print(f"     hole {h.Name!r}")
        try_("       HoleDiameter.Value", lambda h=h: h.HoleDiameter.Value)
        try_("       HoleType", lambda h=h: h.HoleType)
        try_("       ExtentType", lambda h=h: h.ExtentType)
        try_("       Depth.Value", lambda h=h: h.Depth.Value)
        try_("       Tapped", lambda h=h: h.Tapped)
        try_("       HealthStatus", lambda h=h: h.HealthStatus)
    print("  -- fillets in detail")
    for fl in f.FilletFeatures:
        print(f"     fillet {fl.Name!r}")
        try_("       FilletDefinition radius",
             lambda fl=fl: fl.FilletDefinition.ConstantRadiusEdgeSets.Item(1).Radius.Value)
except Exception as e:
    print("  FAIL features:", e)

sect("PARAMETERS")
try:
    print("  ModelParameters.Count =", cd.Parameters.ModelParameters.Count)
    for p in cd.Parameters:
        try:
            print(f"     {p.Name!r} = {p.Value!r} ({p.Units}) expr={p.Expression!r}")
        except Exception:
            pass
except Exception as e:
    print("  FAIL params:", e)

sect("BODIES / FACES (for thin-wall analysis)")
try:
    print("  SurfaceBodies.Count =", cd.SurfaceBodies.Count)
    for b in cd.SurfaceBodies:
        print(f"  -- body {b.Name!r} faces={b.Faces.Count} edges={b.Edges.Count}")
        planar = 0
        for fc in b.Faces:
            try:
                if fc.SurfaceType == 51201:  # kPlaneSurface
                    planar += 1
            except Exception:
                pass
        print(f"     surfaceType histogram: planar-ish={planar}")
        st = {}
        for fc in b.Faces:
            try:
                st[fc.SurfaceType] = st.get(fc.SurfaceType, 0) + 1
            except Exception:
                pass
        print("     raw SurfaceType counts:", st)
        try_("     RangeBox min/max (cm)",
             lambda b=b: (tuple(b.RangeBox.MinPoint.asArray()), tuple(b.RangeBox.MaxPoint.asArray())))
except Exception as e:
    print("  FAIL bodies:", e)

sect("MEASURE TOOLS (thin wall primitive)")
try_("app.MeasureTools exists", lambda: str(app.MeasureTools))

sect("DOC HEALTH / SICK FEATURES")
try_("cd.Features.Count", lambda: cd.Features.Count)
for feat in cd.Features:
    try:
        if feat.HealthStatus != 41217:  # kUpToDateHealth
            print(f"  !! {feat.Name!r} HealthStatus={feat.HealthStatus}")
    except Exception:
        pass
print("  (41217 == kUpToDateHealth; anything else is a sick/failed feature)")

doc.Close(True)
print("\nDONE, doc closed.")
