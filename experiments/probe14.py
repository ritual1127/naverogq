import os
import math
import win32com.client as w32
import ezdxf
from ezdxf import bbox

FIX = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures")
os.makedirs(FIX, exist_ok=True)
IDW = r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\5커버(2개).idw"
IPT = r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\1본체.ipt"
DXF = os.path.join(FIX, "p14.dxf")

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants

print("=" * 70)
print("A. sheet-cm  ->  dxf-mm ?")
print("=" * 70)
d = w32.CastTo(app.Documents.Open(IDW, False), "DrawingDocument")
sh = d.Sheets.Item(1)
print(f"  sheet {sh.Width} x {sh.Height} cm")

circles = []
for vi in range(1, sh.DrawingViews.Count + 1):
    v = sh.DrawingViews.Item(vi)
    try:
        cs = v.DrawingCurves
    except Exception:
        continue
    for dc in cs:
        try:
            if dc.CurveType != C.kCircleCurve:
                continue
            if dc.EdgeType == getattr(C, "kTangentEdge", -1):
                continue
            if dc.ProjectedCurveType != getattr(C, "kCircleCurve2d", -1):
                continue
            r = dc.ModelGeometry.Geometry.Radius * 10
            circles.append((dc.CenterPoint.X * 10, dc.CenterPoint.Y * 10, r, v.Name))
        except Exception:
            continue
print(f"  face-on circles found: {len(circles)}")
for c in circles[:8]:
    print(f"     sheet_mm=({c[0]:.2f},{c[1]:.2f}) r={c[2]:.3f} view={c[3]}")

try:
    d.SaveAs(DXF, True)
    print("  dxf exported:", os.path.exists(DXF), os.path.getsize(DXF))
except Exception as e:
    print("  dxf export FAIL:", e)
d.Close(True)

doc = ezdxf.readfile(DXF)
msp = doc.modelspace()
bb = bbox.extents(msp)
print(f"  dxf extents: ({bb.extmin.x:.2f},{bb.extmin.y:.2f}) - "
      f"({bb.extmax.x:.2f},{bb.extmax.y:.2f})")


def walk(ents, depth=0, seen=frozenset()):
    for e in ents:
        if e.dxftype() == "INSERT":
            if depth > 4 or e.dxf.name in seen:
                continue
            try:
                yield from walk(e.virtual_entities(), depth + 1, seen | {e.dxf.name})
            except Exception:
                continue
        else:
            yield e


pts = []
for e in walk(msp):
    t = e.dxftype()
    try:
        if t == "CIRCLE":
            pts.append((e.dxf.center.x, e.dxf.center.y, "CIRCLE", e.dxf.radius))
        elif t == "ARC":
            pts.append((e.dxf.center.x, e.dxf.center.y, "ARC", e.dxf.radius))
        elif t == "LINE":
            pts.append((e.dxf.start.x, e.dxf.start.y, "LINE", 0))
        elif t in ("LWPOLYLINE", "POLYLINE"):
            for p in e.vertices() if t == "POLYLINE" else e.get_points():
                xy = (p.dxf.location.x, p.dxf.location.y) if t == "POLYLINE" else (p[0], p[1])
                pts.append((xy[0], xy[1], t, 0))
        elif t == "SPLINE":
            for p in e.control_points:
                pts.append((p.x, p.y, "SPLINE", 0))
    except Exception:
        continue
print(f"  dxf geometry sample points: {len(pts)}")

print("\n  -- prediction test: is there DXF geometry at each predicted spot? --")
hits = 0
for cx, cy, r, vn in circles[:12]:
    near = min(((math.dist((cx, cy), (p[0], p[1])), p) for p in pts),
               default=(1e9, None))
    dist, p = near
    ok = dist < max(2.0, r * 0.35)
    hits += ok
    print(f"     predict({cx:8.2f},{cy:8.2f}) r={r:6.2f} -> nearest {p[2] if p else '-':10} "
          f"at {dist:7.3f} mm  {'HIT' if ok else 'miss'}")
print(f"  hits: {hits}/{min(12, len(circles))}")
print("  VERDICT:", "sheet_cm*10 == dxf_mm  -> markers are safe"
      if hits >= max(1, min(12, len(circles)) * 0.7) else "mapping does NOT hold")

print("\n" + "=" * 70)
print("B. 3D export for a rotatable preview")
print("=" * 70)
part = w32.CastTo(app.Documents.Open(IPT, False), "PartDocument")
for ext in ("stl", "obj"):
    out = os.path.join(FIX, f"p14_part.{ext}")
    if os.path.exists(out):
        os.remove(out)
    try:
        part.SaveAs(out, True)
        ok = os.path.exists(out)
        print(f"  SaveAs .{ext}: {'OK' if ok else 'no file'} "
              f"{os.path.getsize(out) if ok else ''}")
    except Exception as e:
        print(f"  SaveAs .{ext}: FAIL {str(e)[:120]}")

print("\n  -- TranslatorAddIn route --")
for addin in app.ApplicationAddIns:
    try:
        nm = addin.DisplayName
    except Exception:
        continue
    if any(k in nm.upper() for k in ("STL", "OBJ", "JT", "STEP")):
        print(f"     {nm}  ClassId={addin.ClassIdString}")
part.Close(True)
print("\nDONE")

