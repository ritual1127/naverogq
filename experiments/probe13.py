"""Probe 13: are the odd-diameter "missing dimension" circles actually tangent
or silhouette edges rather than real holes? DrawingCurve.EdgeType should say.
"""
import win32com.client as w32

PATHS = [r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\2V벨트풀리.idw",
         r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\3축.idw"]

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants
D = w32.constants.__dict__.get("__dicts__", [{}])[0]


def nm(v):
    return ([k for k, x in D.items() if x == v] or [str(v)])[0]



for path in PATHS:
    print(f"\n{'=' * 70}\n{path.split(chr(92))[-1]}\n{'=' * 70}")
    d = w32.CastTo(app.Documents.Open(path, False), "DrawingDocument")
    sh = d.Sheets.Item(1)
    rows = []
    for vi in range(1, sh.DrawingViews.Count + 1):
        v = sh.DrawingViews.Item(vi)
        try:
            curves = v.DrawingCurves
        except Exception:
            continue
        for dc in curves:
            try:
                if dc.CurveType not in (C.kCircleCurve, C.kCircularArcCurve):
                    continue
                dia = dc.ModelGeometry.Geometry.Radius * 2 * 10
                rows.append((round(dia, 2), nm(dc.EdgeType), nm(dc.CurveType),
                             nm(getattr(dc, "ProjectedCurveType", None)), v.Name))
            except Exception as e:
                rows.append((None, f"ERR {type(e).__name__}", "", "", v.Name))
    seen = {}
    for dia, et, ct, pct, vn in rows:
        seen.setdefault((dia, et, pct), 0)
        seen[(dia, et, pct)] += 1
    print(f"  {'dia':>8}  {'EdgeType':32} {'ProjectedCurveType':28} n")
    for (dia, et, pct), n in sorted(seen.items(), key=lambda x: -(x[0][0] or 0)):
        print(f"  {dia!s:>8}  {et:32} {pct:28} {n}")
    d.Close(True)
print("\nDONE")
